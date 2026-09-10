from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.core.config import Settings
from app.modules.appeals.dependencies import (
    get_attachment_service,
    get_current_appeal_id,
    get_public_appeal_rate_limiter,
    get_public_appeal_service,
)
from app.modules.appeals.rate_limit import PublicAppealRateLimiter
from app.modules.appeals.schemas import (
    AppealAccessRequest,
    AppealAccessResponse,
    AppealCreatedResponse,
    AppealCreateRequest,
    AttachmentResponse,
    ComplaintRequest,
    CrisisContactRequest,
    CurrentAppealResponse,
    FeedbackRequest,
    LeaveResponse,
    PublicMessageRequest,
    PublicMessagesResponse,
    PublicReferenceResponse,
    ResolveAppealRequest,
    SavedResponse,
)
from app.modules.appeals.service import PublicAppealService
from app.modules.attachments.service import AttachmentService

router = APIRouter(prefix="/public", tags=["public-appeals"])


def _set_access_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.applicant_access_cookie_name,
        value=token,
        max_age=settings.applicant_access_ttl_minutes * 60,
        httponly=True,
        secure=settings.applicant_access_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/public/appeals",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_access_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.applicant_access_cookie_name,
        httponly=True,
        secure=settings.applicant_access_cookie_secure,
        samesite="lax",
        path=f"{settings.api_prefix}/public/appeals",
    )
    response.headers["Cache-Control"] = "no-store"


def _transient_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


@router.get("/reference", response_model=PublicReferenceResponse)
async def public_reference(
    response: Response,
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> PublicReferenceResponse:
    response.headers["Cache-Control"] = "public, max-age=60"
    return await service.public_reference()


@router.post("/appeals", response_model=AppealCreatedResponse, status_code=201)
async def create_appeal(
    payload: AppealCreateRequest,
    request: Request,
    response: Response,
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
    rate_limiter: Annotated[PublicAppealRateLimiter, Depends(get_public_appeal_rate_limiter)],
) -> AppealCreatedResponse:
    await rate_limiter.check("submission", transient_ip=_transient_ip(request))
    result = await service.create_appeal(payload)
    settings = cast(Settings, request.app.state.settings)
    _set_access_cookie(response, settings, result.access_token)
    return result.response


@router.post("/appeals/access", response_model=AppealAccessResponse)
async def access_appeal(
    payload: AppealAccessRequest,
    request: Request,
    response: Response,
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
    rate_limiter: Annotated[PublicAppealRateLimiter, Depends(get_public_appeal_rate_limiter)],
) -> AppealAccessResponse:
    await rate_limiter.check("track-access", transient_ip=_transient_ip(request))
    result = await service.access_appeal(payload.track_number.get_secret_value())
    settings = cast(Settings, request.app.state.settings)
    _set_access_cookie(response, settings, result.access_token)
    return AppealAccessResponse()


@router.get("/appeals/current", response_model=CurrentAppealResponse)
async def current_appeal(
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> CurrentAppealResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.current_appeal(appeal_id)


@router.get("/appeals/current/messages", response_model=PublicMessagesResponse)
async def current_messages(
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> PublicMessagesResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.messages(appeal_id)


@router.post("/appeals/current/messages", response_model=SavedResponse, status_code=201)
async def send_current_message(
    payload: PublicMessageRequest,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> SavedResponse:
    await service.send_message(appeal_id, payload.body.get_secret_value())
    response.headers["Cache-Control"] = "no-store"
    return SavedResponse()


@router.post("/appeals/current/resolve", response_model=SavedResponse)
async def resolve_current_appeal(
    payload: ResolveAppealRequest,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> SavedResponse:
    await service.resolve(
        appeal_id,
        choice=payload.choice,
        explanation=(payload.explanation.get_secret_value() if payload.explanation else None),
    )
    response.headers["Cache-Control"] = "no-store"
    return SavedResponse()


@router.post("/appeals/current/feedback", response_model=SavedResponse, status_code=201)
async def submit_feedback(
    payload: FeedbackRequest,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> SavedResponse:
    await service.submit_feedback(appeal_id, payload)
    response.headers["Cache-Control"] = "no-store"
    return SavedResponse()


@router.post("/appeals/current/complaints", response_model=SavedResponse, status_code=201)
async def submit_complaint(
    payload: ComplaintRequest,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> SavedResponse:
    await service.submit_complaint(appeal_id, payload.body.get_secret_value())
    response.headers["Cache-Control"] = "no-store"
    return SavedResponse()


@router.post("/appeals/leave", response_model=LeaveResponse)
async def leave_appeal(request: Request, response: Response) -> LeaveResponse:
    settings = cast(Settings, request.app.state.settings)
    _clear_access_cookie(response, settings)
    return LeaveResponse()


@router.put("/appeals/current/crisis-contact", response_model=SavedResponse)
async def save_crisis_contact(
    payload: CrisisContactRequest,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    service: Annotated[PublicAppealService, Depends(get_public_appeal_service)],
) -> SavedResponse:
    await service.save_crisis_contact(appeal_id, payload.contact.get_secret_value())
    response.headers["Cache-Control"] = "no-store"
    return SavedResponse()


@router.post("/appeals/current/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    request: Request,
    response: Response,
    appeal_id: Annotated[UUID, Depends(get_current_appeal_id)],
    attachment_service: Annotated[AttachmentService, Depends(get_attachment_service)],
    file: Annotated[UploadFile, File()],
) -> AttachmentResponse:
    settings = cast(Settings, request.app.state.settings)
    declared_mime_type = file.content_type
    try:
        data = await file.read(settings.attachment_max_bytes + 1)
    finally:
        await file.close()
    result = await attachment_service.store_image(
        appeal_id=appeal_id,
        data=data,
        declared_mime_type=declared_mime_type,
    )
    response.headers["Cache-Control"] = "no-store"
    return result
