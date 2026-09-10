from io import BytesIO
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from PIL import Image

from app.core.crypto import ContentCrypto
from app.core.errors import (
    ConflictError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from app.db.models import Appeal, Attachment
from app.db.models.enums import AppealPriority, AppealStatus, ApplicantType
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.appeals.crypto_context import attachment_aad
from app.modules.attachments.images import sanitize_image
from app.modules.attachments.service import AttachmentService
from app.modules.attachments.storage import PrivateAttachmentStorage


class FakeAttachmentRepository:
    def __init__(self, appeal: Appeal, *, count: int = 0) -> None:
        self.appeal = appeal
        self.count = count
        self.attachment: Attachment | None = None
        self.committed = False

    async def lock_appeal(self, appeal_id: UUID) -> Appeal | None:
        return self.appeal if appeal_id == self.appeal.id else None

    async def count_attachments(self, appeal_id: UUID) -> int:
        assert appeal_id == self.appeal.id
        return self.count

    async def add_attachment(self, attachment: Attachment) -> None:
        self.attachment = attachment

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None


def _appeal() -> Appeal:
    return Appeal(
        id=uuid4(),
        track_digest=b"t" * 32,
        applicant_type=ApplicantType.STUDENT,
        status=AppealStatus.NEW,
        priority=AppealPriority.STANDARD,
        crisis_flag=False,
        return_count=0,
    )


def _image_bytes(image_format: str = "PNG", *, exif: Image.Exif | None = None) -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 12), (42, 110, 170)).save(output, format=image_format, exif=exif)
    return output.getvalue()


async def test_valid_image_is_sanitized_encrypted_and_stored_privately(
    test_settings, tmp_path: Path
) -> None:
    appeal = _appeal()
    repository = FakeAttachmentRepository(appeal)
    storage = PrivateAttachmentStorage(tmp_path / "private")
    service = AttachmentService(cast(PublicAppealRepository, repository), test_settings, storage)

    result = await service.store_image(
        appeal_id=appeal.id,
        data=_image_bytes(),
        declared_mime_type="image/png",
    )
    metadata = repository.attachment
    assert metadata is not None
    stored = (tmp_path / "private" / metadata.storage_key).read_bytes()
    crypto = ContentCrypto(test_settings.content_encryption_key.get_secret_value())
    sanitized = crypto.decrypt_bytes(stored, aad=attachment_aad(appeal.id, metadata.id))

    assert result.mime_type == "image/png"
    assert result.byte_size == len(stored) == metadata.byte_size
    assert stored != sanitized
    assert "." not in metadata.storage_key
    assert repository.committed
    with Image.open(BytesIO(sanitized)) as decoded:
        assert decoded.format == "PNG"
        assert not decoded.getexif()
        assert not decoded.info


async def test_attachment_larger_than_limit_is_rejected(test_settings, tmp_path: Path) -> None:
    appeal = _appeal()
    service = AttachmentService(
        cast(PublicAppealRepository, FakeAttachmentRepository(appeal)),
        test_settings,
        PrivateAttachmentStorage(tmp_path),
    )
    with pytest.raises(PayloadTooLargeError):
        await service.store_image(
            appeal_id=appeal.id,
            data=b"x" * (10 * 1024 * 1024 + 1),
            declared_mime_type="image/png",
        )


async def test_unsupported_and_corrupt_images_are_rejected(test_settings, tmp_path: Path) -> None:
    appeal = _appeal()
    service = AttachmentService(
        cast(PublicAppealRepository, FakeAttachmentRepository(appeal)),
        test_settings,
        PrivateAttachmentStorage(tmp_path),
    )
    with pytest.raises(UnsupportedMediaTypeError):
        await service.store_image(
            appeal_id=appeal.id,
            data=b"GIF89a",
            declared_mime_type="image/gif",
        )
    with pytest.raises(ValidationError):
        await service.store_image(
            appeal_id=appeal.id,
            data=b"\xff\xd8\xffcorrupt",
            declared_mime_type="image/jpeg",
        )


async def test_maximum_five_attachments_is_enforced(test_settings, tmp_path: Path) -> None:
    appeal = _appeal()
    repository = FakeAttachmentRepository(appeal, count=5)
    service = AttachmentService(
        cast(PublicAppealRepository, repository),
        test_settings,
        PrivateAttachmentStorage(tmp_path),
    )
    with pytest.raises(ConflictError):
        await service.store_image(
            appeal_id=appeal.id,
            data=_image_bytes(),
            declared_mime_type="image/png",
        )
    assert repository.attachment is None


def test_exif_and_geolocation_metadata_are_stripped() -> None:
    exif = Image.Exif()
    exif[0x010E] = "identifying description"
    exif[0x0132] = "2026:09:09 12:00:00"
    original = _image_bytes("JPEG", exif=exif)

    sanitized = sanitize_image(original, max_pixels=1_000_000)

    assert b"identifying description" not in sanitized.data
    with Image.open(BytesIO(sanitized.data)) as decoded:
        assert not decoded.getexif()
        assert 0x8825 not in decoded.getexif()


def test_attachment_schema_has_no_original_filename_or_public_url() -> None:
    assert {"original_filename", "filename", "public_url"}.isdisjoint(
        Attachment.__table__.columns.keys()
    )
