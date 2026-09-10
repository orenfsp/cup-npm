from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.db.models import StaffUser
from app.db.models.enums import AppealPriority, AppealStatus
from app.modules.expert.dependencies import get_current_expert, get_expert_service
from app.modules.expert.schemas import (
    ActionResponse,
    CannotTakeRequest,
    ClarificationRequest,
    CollaborationRequest,
    ComposerLockResponse,
    ExpertAppealDetail,
    ExpertNote,
    ExpertQueueResponse,
    MessageRequest,
    NoteRequest,
    TransferCreateRequest,
)
from app.modules.expert.service import ExpertService

router = APIRouter(prefix="/expert", tags=["expert"])
Expert = Annotated[StaffUser, Depends(get_current_expert)]
Service = Annotated[ExpertService, Depends(get_expert_service)]


@router.get("/appeals", response_model=ExpertQueueResponse)
async def expert_queue(
    expert: Expert,
    service: Service,
    status: AppealStatus | None = None,
    priority: AppealPriority | None = None,
    category: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ExpertQueueResponse:
    return await service.queue(
        expert.id,
        expert_role=expert.role,
        status=status,
        priority=priority,
        category_id=category,
        page=page,
        page_size=page_size,
    )


@router.get("/appeals/{appeal_id}", response_model=ExpertAppealDetail)
async def expert_detail(
    appeal_id: UUID, expert: Expert, service: Service, response: Response
) -> ExpertAppealDetail:
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(appeal_id, expert.id, expert_role=expert.role)


@router.post("/appeals/{appeal_id}/take", response_model=ActionResponse)
async def take_into_work(appeal_id: UUID, expert: Expert, service: Service) -> ActionResponse:
    return await service.take_into_work(appeal_id, expert.id, expert_role=expert.role)


@router.post("/appeals/{appeal_id}/messages", response_model=ActionResponse, status_code=201)
async def send_message(
    appeal_id: UUID,
    payload: MessageRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.send_message(
        appeal_id,
        expert.id,
        payload.body.get_secret_value(),
        expert_role=expert.role,
    )


@router.post("/appeals/{appeal_id}/clarification", response_model=ActionResponse)
async def request_clarification(
    appeal_id: UUID,
    payload: ClarificationRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.request_clarification(
        appeal_id,
        expert.id,
        payload.message.get_secret_value() if payload.message else None,
        expert_role=expert.role,
    )


@router.get("/appeals/{appeal_id}/notes", response_model=list[ExpertNote])
async def list_notes(
    appeal_id: UUID, expert: Expert, service: Service, response: Response
) -> list[ExpertNote]:
    response.headers["Cache-Control"] = "no-store"
    return await service.notes(appeal_id, expert.id, expert_role=expert.role)


@router.post("/appeals/{appeal_id}/notes", response_model=ActionResponse, status_code=201)
async def add_note(
    appeal_id: UUID,
    payload: NoteRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.add_note(
        appeal_id,
        expert.id,
        payload.body.get_secret_value(),
        expert_role=expert.role,
    )


@router.post("/appeals/{appeal_id}/coexecutors", response_model=ActionResponse, status_code=201)
async def add_coexecutor(
    appeal_id: UUID,
    payload: CollaborationRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.add_coexecutor(
        appeal_id,
        expert.id,
        payload.expert_id,
        payload.reason.get_secret_value(),
        expert_role=expert.role,
    )


@router.post(
    "/appeals/{appeal_id}/transfer-requests", response_model=ActionResponse, status_code=201
)
async def request_transfer(
    appeal_id: UUID,
    payload: TransferCreateRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.request_transfer(
        appeal_id,
        expert.id,
        payload.target_expert_id,
        payload.reason.get_secret_value(),
        expert_role=expert.role,
    )


@router.post("/appeals/{appeal_id}/cannot-take", response_model=ActionResponse, status_code=201)
async def cannot_take_appeal(
    appeal_id: UUID,
    payload: CannotTakeRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.request_reassignment(
        appeal_id,
        expert.id,
        payload.reason.get_secret_value(),
        expert_role=expert.role,
    )


@router.post("/appeals/{appeal_id}/recommendations", response_model=ActionResponse)
async def prepare_recommendations(
    appeal_id: UUID,
    payload: MessageRequest,
    expert: Expert,
    service: Service,
) -> ActionResponse:
    return await service.prepare_recommendations(
        appeal_id,
        expert.id,
        payload.body.get_secret_value(),
        expert_role=expert.role,
    )


@router.get("/appeals/{appeal_id}/attachments/{attachment_id}")
async def expert_attachment(
    appeal_id: UUID,
    attachment_id: UUID,
    expert: Expert,
    service: Service,
) -> Response:
    attachment = await service.attachment(
        appeal_id,
        attachment_id,
        expert.id,
        expert_role=expert.role,
    )
    return Response(
        attachment.body,
        media_type=attachment.mime_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{attachment.safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/appeals/{appeal_id}/composer-lock", response_model=ComposerLockResponse)
async def acquire_composer_lock(
    appeal_id: UUID, expert: Expert, service: Service
) -> ComposerLockResponse:
    return await service.acquire_composer_lock(appeal_id, expert.id, expert_role=expert.role)


@router.post("/appeals/{appeal_id}/composer-lock/heartbeat", response_model=ComposerLockResponse)
async def heartbeat_composer_lock(
    appeal_id: UUID, expert: Expert, service: Service
) -> ComposerLockResponse:
    return await service.heartbeat_composer_lock(appeal_id, expert.id, expert_role=expert.role)


@router.delete("/appeals/{appeal_id}/composer-lock", response_model=ActionResponse)
async def release_composer_lock(
    appeal_id: UUID, expert: Expert, service: Service
) -> ActionResponse:
    return await service.release_composer_lock(appeal_id, expert.id, expert_role=expert.role)
