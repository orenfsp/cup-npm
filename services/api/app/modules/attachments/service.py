import asyncio
import hashlib
from uuid import UUID, uuid4

from app.core.config import Settings
from app.core.crypto import ContentCrypto
from app.core.errors import (
    ConflictError,
    InfrastructureError,
    PayloadTooLargeError,
    UnauthorizedError,
    UnsupportedMediaTypeError,
)
from app.db.models import Attachment
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.appeals.crypto_context import attachment_aad
from app.modules.appeals.schemas import AttachmentResponse
from app.modules.attachments.images import ALLOWED_IMAGE_MIME_TYPES, sanitize_image
from app.modules.attachments.storage import PrivateAttachmentStorage


class AttachmentService:
    def __init__(
        self,
        repository: PublicAppealRepository,
        settings: Settings,
        storage: PrivateAttachmentStorage | None = None,
    ) -> None:
        content_key = settings.content_encryption_key
        if content_key is None or not content_key.get_secret_value():
            raise InfrastructureError("Sensitive-content encryption is not configured.")
        self._repository = repository
        self._settings = settings
        self._crypto = ContentCrypto(content_key.get_secret_value())
        self._storage = storage or PrivateAttachmentStorage(settings.attachment_storage_path)

    async def store_image(
        self,
        *,
        appeal_id: UUID,
        data: bytes,
        declared_mime_type: str | None,
    ) -> AttachmentResponse:
        if declared_mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise UnsupportedMediaTypeError("Only JPEG, PNG, and WEBP images are supported.")
        if len(data) > self._settings.attachment_max_bytes:
            raise PayloadTooLargeError("An attachment must not exceed 10 MB.")
        sanitized = await asyncio.to_thread(
            sanitize_image, data, max_pixels=self._settings.attachment_max_pixels
        )
        appeal = await self._repository.lock_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        attachment_count = await self._repository.count_attachments(appeal_id)
        if attachment_count >= self._settings.attachment_max_count:
            raise ConflictError("No more than five attachments are allowed per appeal.")

        attachment_id = uuid4()
        encrypted = self._crypto.encrypt_bytes(
            sanitized.data, aad=attachment_aad(appeal_id, attachment_id)
        )
        storage_key: str | None = None
        try:
            storage_key = await asyncio.to_thread(self._storage.write, encrypted)
            await self._repository.add_attachment(
                Attachment(
                    id=attachment_id,
                    appeal_id=appeal_id,
                    storage_key=storage_key,
                    mime_type=sanitized.mime_type,
                    byte_size=len(encrypted),
                    sha256_digest=hashlib.sha256(encrypted).digest(),
                )
            )
            await self._repository.commit()
        except Exception:
            await self._repository.rollback()
            if storage_key is not None:
                await asyncio.to_thread(self._storage.delete, storage_key)
            raise
        return AttachmentResponse(
            mime_type=sanitized.mime_type,
            byte_size=len(encrypted),
        )
