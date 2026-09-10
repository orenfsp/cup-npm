from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.db.models import StaffUser
from app.db.models.enums import AppealPriority, AppealStatus
from app.modules.operator.dependencies import get_current_operator, get_operator_service
from app.modules.operator.schemas import (
    ActionResponse,
    AssignmentRequest,
    CrisisContactResponse,
    OperatorAppealDetail,
    OperatorComplaintItem,
    OperatorQueueResponse,
    OperatorReferenceResponse,
    OperatorTransferRequestItem,
    OperatorTriageRequest,
    RejectionRequest,
    TransferResolutionRequest,
)
from app.modules.operator.service import OperatorService

router = APIRouter(prefix="/operator", tags=["operator"])
Operator = Annotated[StaffUser, Depends(get_current_operator)]
Service = Annotated[OperatorService, Depends(get_operator_service)]


@router.get("/reference", response_model=OperatorReferenceResponse)
async def operator_reference(operator: Operator, service: Service) -> OperatorReferenceResponse:
    return await service.reference(operator_role=operator.role)


@router.get("/appeals", response_model=OperatorQueueResponse)
async def operator_queue(
    operator: Operator,
    service: Service,
    status: AppealStatus | None = None,
    priority: AppealPriority | None = None,
    category: UUID | None = None,
    crisis: bool | None = None,
    assigned: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> OperatorQueueResponse:
    return await service.queue(
        operator_role=operator.role,
        status=status,
        priority=priority,
        category_id=category,
        crisis=crisis,
        assigned=assigned,
        page=page,
        page_size=page_size,
    )


@router.get("/appeals/{appeal_id}", response_model=OperatorAppealDetail)
async def operator_detail(
    appeal_id: UUID, operator: Operator, service: Service, response: Response
) -> OperatorAppealDetail:
    response.headers["Cache-Control"] = "no-store"
    return await service.detail(appeal_id, operator_role=operator.role)


@router.patch("/appeals/{appeal_id}/triage", response_model=ActionResponse)
async def operator_triage(
    appeal_id: UUID,
    payload: OperatorTriageRequest,
    operator: Operator,
    service: Service,
) -> ActionResponse:
    return await service.triage(
        appeal_id,
        payload,
        operator_id=operator.id,
        operator_role=operator.role,
    )


@router.post("/appeals/{appeal_id}/assign", response_model=ActionResponse)
async def operator_assign(
    appeal_id: UUID,
    payload: AssignmentRequest,
    operator: Operator,
    service: Service,
) -> ActionResponse:
    return await service.assign(
        appeal_id,
        payload.expert_id,
        operator_id=operator.id,
        operator_role=operator.role,
    )


@router.post("/appeals/{appeal_id}/reject", response_model=ActionResponse)
async def operator_reject(
    appeal_id: UUID,
    payload: RejectionRequest,
    operator: Operator,
    service: Service,
) -> ActionResponse:
    return await service.reject(
        appeal_id,
        kind=payload.kind,
        reason=payload.reason.get_secret_value(),
        operator_id=operator.id,
        operator_role=operator.role,
    )


@router.get("/appeals/{appeal_id}/crisis-contact", response_model=CrisisContactResponse)
async def operator_crisis_contact(
    appeal_id: UUID,
    operator: Operator,
    service: Service,
    response: Response,
) -> CrisisContactResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.crisis_contact(
        appeal_id,
        operator_id=operator.id,
        operator_role=operator.role,
    )


@router.get("/appeals/{appeal_id}/attachments/{attachment_id}")
async def operator_attachment(
    appeal_id: UUID,
    attachment_id: UUID,
    operator: Operator,
    service: Service,
) -> Response:
    attachment = await service.attachment(
        appeal_id,
        attachment_id,
        operator_role=operator.role,
    )
    return Response(
        content=attachment.body,
        media_type=attachment.mime_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{attachment.safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/transfer-requests", response_model=list[OperatorTransferRequestItem])
async def operator_transfer_requests(
    operator: Operator, service: Service, response: Response
) -> list[OperatorTransferRequestItem]:
    response.headers["Cache-Control"] = "no-store"
    return await service.transfer_requests(operator_role=operator.role)


@router.post("/transfer-requests/{transfer_id}/resolve", response_model=ActionResponse)
async def operator_resolve_transfer(
    transfer_id: UUID,
    payload: TransferResolutionRequest,
    operator: Operator,
    service: Service,
) -> ActionResponse:
    return await service.resolve_transfer(
        transfer_id,
        approve=payload.decision == "approve",
        replacement_expert_id=payload.replacement_expert_id,
        operator_id=operator.id,
        operator_role=operator.role,
    )


@router.get("/appeals/{appeal_id}/complaints", response_model=list[OperatorComplaintItem])
async def operator_complaints(
    appeal_id: UUID,
    operator: Operator,
    service: Service,
    response: Response,
) -> list[OperatorComplaintItem]:
    response.headers["Cache-Control"] = "no-store"
    return await service.complaints(appeal_id, operator_role=operator.role)
