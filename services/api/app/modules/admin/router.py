from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.db.models.enums import AppealStatus
from app.modules.admin.dependencies import AdminServiceDependency, CurrentAdmin
from app.modules.admin.schemas import (
    AdminAppealInterventionRequest,
    AdminAppealItem,
    AdminAppealPage,
    AnalyticsResponse,
    ApplicantTypeItem,
    ApplicantTypeRequest,
    ApplicantTypeUpdate,
    AuditPage,
    CategoryItem,
    CategoryQuestionMappingRequest,
    CategoryRequest,
    CategoryUpdate,
    CrisisRuleItem,
    CrisisRuleRequest,
    CrisisRuleTestRequest,
    CrisisRuleTestResponse,
    CrisisRuleUpdate,
    GroupItem,
    GroupMembershipRequest,
    GroupRequest,
    GroupUpdate,
    IntakeQuestionItem,
    IntakeQuestionRequest,
    IntakeQuestionUpdate,
    InvitationResult,
    PasswordSetupRequest,
    PasswordSetupResponse,
    RoutingItem,
    RoutingUpdateRequest,
    SafeSettingsResponse,
    SavedResponse,
    StaffAdminItem,
    StaffCreateRequest,
    StaffCreateResult,
    StaffUpdateRequest,
    SupportResourceItem,
    SupportResourceRequest,
    SupportResourceUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin-configuration"])
setup_router = APIRouter(prefix="/auth", tags=["staff-auth"])


@router.get("/staff", response_model=list[StaffAdminItem])
async def list_staff(admin: CurrentAdmin, service: AdminServiceDependency) -> list[StaffAdminItem]:
    del admin
    return await service.list_staff()


@router.post("/staff", response_model=StaffCreateResult)
async def create_staff(
    payload: StaffCreateRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> StaffCreateResult:
    return await service.create_staff(payload, admin_id=admin.id)


@router.patch("/staff/{staff_id}", response_model=StaffAdminItem)
async def update_staff(
    staff_id: UUID,
    payload: StaffUpdateRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> StaffAdminItem:
    return await service.update_staff(staff_id, payload, admin_id=admin.id)


@router.post("/staff/{staff_id}/invitation", response_model=InvitationResult)
async def resend_invitation(
    staff_id: UUID, admin: CurrentAdmin, service: AdminServiceDependency
) -> InvitationResult:
    return await service.send_invitation(staff_id, admin_id=admin.id, reset=False)


@router.post("/staff/{staff_id}/password-reset", response_model=InvitationResult)
async def password_reset(
    staff_id: UUID, admin: CurrentAdmin, service: AdminServiceDependency
) -> InvitationResult:
    return await service.send_invitation(staff_id, admin_id=admin.id, reset=True)


@setup_router.post("/setup-password", response_model=PasswordSetupResponse)
async def setup_password(
    payload: PasswordSetupRequest, service: AdminServiceDependency
) -> PasswordSetupResponse:
    await service.setup_password(
        payload.token.get_secret_value(), payload.password.get_secret_value()
    )
    return PasswordSetupResponse()


@router.get("/applicant-types", response_model=list[ApplicantTypeItem])
async def applicant_types(
    admin: CurrentAdmin, service: AdminServiceDependency
) -> list[ApplicantTypeItem]:
    del admin
    return await service.applicant_types()


@router.post("/applicant-types", response_model=ApplicantTypeItem)
async def create_applicant_type(
    payload: ApplicantTypeRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> ApplicantTypeItem:
    return await service.create_applicant_type(payload, admin_id=admin.id)


@router.patch("/applicant-types/{item_id}", response_model=ApplicantTypeItem)
async def update_applicant_type(
    item_id: UUID,
    payload: ApplicantTypeUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> ApplicantTypeItem:
    return await service.update_applicant_type(item_id, payload, admin_id=admin.id)


@router.get("/categories", response_model=list[CategoryItem])
async def categories(admin: CurrentAdmin, service: AdminServiceDependency) -> list[CategoryItem]:
    del admin
    return await service.categories()


@router.post("/categories", response_model=CategoryItem)
async def create_category(
    payload: CategoryRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> CategoryItem:
    return await service.create_category(payload, admin_id=admin.id)


@router.patch("/categories/{item_id}", response_model=CategoryItem)
async def update_category(
    item_id: UUID,
    payload: CategoryUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> CategoryItem:
    return await service.update_category(item_id, payload, admin_id=admin.id)


@router.put("/categories/{category_id}/questions", response_model=SavedResponse)
async def set_category_questions(
    category_id: UUID,
    payload: CategoryQuestionMappingRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> SavedResponse:
    await service.set_category_questions(category_id, payload, admin_id=admin.id)
    return SavedResponse()


@router.get("/questions", response_model=list[IntakeQuestionItem])
async def questions(
    admin: CurrentAdmin, service: AdminServiceDependency
) -> list[IntakeQuestionItem]:
    del admin
    return await service.questions()


@router.post("/questions", response_model=IntakeQuestionItem)
async def create_question(
    payload: IntakeQuestionRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> IntakeQuestionItem:
    return await service.create_question(payload, admin_id=admin.id)


@router.patch("/questions/{item_id}", response_model=IntakeQuestionItem)
async def update_question(
    item_id: UUID,
    payload: IntakeQuestionUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> IntakeQuestionItem:
    return await service.update_question(item_id, payload, admin_id=admin.id)


@router.get("/groups", response_model=list[GroupItem])
async def groups(admin: CurrentAdmin, service: AdminServiceDependency) -> list[GroupItem]:
    del admin
    return await service.groups()


@router.post("/groups", response_model=GroupItem)
async def create_group(
    payload: GroupRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> GroupItem:
    return await service.create_group(payload, admin_id=admin.id)


@router.patch("/groups/{item_id}", response_model=GroupItem)
async def update_group(
    item_id: UUID,
    payload: GroupUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> GroupItem:
    return await service.update_group(item_id, payload, admin_id=admin.id)


@router.put("/groups/{group_id}/members", response_model=SavedResponse)
async def set_group_members(
    group_id: UUID,
    payload: GroupMembershipRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> SavedResponse:
    await service.set_group_members(group_id, payload, admin_id=admin.id)
    return SavedResponse()


@router.get("/routing", response_model=list[RoutingItem])
async def routing(admin: CurrentAdmin, service: AdminServiceDependency) -> list[RoutingItem]:
    del admin
    return await service.routing()


@router.put("/routing/{category_id}", response_model=SavedResponse)
async def set_routing(
    category_id: UUID,
    payload: RoutingUpdateRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> SavedResponse:
    await service.set_routing(category_id, payload, admin_id=admin.id)
    return SavedResponse()


@router.get("/crisis-rules", response_model=list[CrisisRuleItem])
async def crisis_rules(
    admin: CurrentAdmin, service: AdminServiceDependency
) -> list[CrisisRuleItem]:
    del admin
    return await service.crisis_rules()


@router.post("/crisis-rules/test", response_model=CrisisRuleTestResponse)
async def test_crisis_rule(
    payload: CrisisRuleTestRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> CrisisRuleTestResponse:
    del admin
    return await service.test_crisis_phrase(payload.text.get_secret_value())


@router.post("/crisis-rules", response_model=CrisisRuleItem)
async def create_crisis_rule(
    payload: CrisisRuleRequest, admin: CurrentAdmin, service: AdminServiceDependency
) -> CrisisRuleItem:
    return await service.create_crisis_rule(payload, admin_id=admin.id)


@router.patch("/crisis-rules/{item_id}", response_model=CrisisRuleItem)
async def update_crisis_rule(
    item_id: UUID,
    payload: CrisisRuleUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> CrisisRuleItem:
    return await service.update_crisis_rule(item_id, payload, admin_id=admin.id)


@router.get("/support-resources", response_model=list[SupportResourceItem])
async def support_resources(
    admin: CurrentAdmin, service: AdminServiceDependency
) -> list[SupportResourceItem]:
    del admin
    return await service.support_resources()


@router.post("/support-resources", response_model=SupportResourceItem)
async def create_support_resource(
    payload: SupportResourceRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> SupportResourceItem:
    return await service.create_support_resource(payload, admin_id=admin.id)


@router.patch("/support-resources/{item_id}", response_model=SupportResourceItem)
async def update_support_resource(
    item_id: UUID,
    payload: SupportResourceUpdate,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> SupportResourceItem:
    return await service.update_support_resource(item_id, payload, admin_id=admin.id)


@router.get("/settings", response_model=SafeSettingsResponse)
async def safe_settings(
    admin: CurrentAdmin, service: AdminServiceDependency
) -> SafeSettingsResponse:
    del admin
    return service.safe_settings()


@router.get("/appeals", response_model=AdminAppealPage)
async def appeal_metadata(
    admin: CurrentAdmin,
    service: AdminServiceDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    status: AppealStatus | None = None,
) -> AdminAppealPage:
    del admin
    return await service.appeal_metadata(page=page, page_size=page_size, status=status)


@router.patch("/appeals/{appeal_id}", response_model=AdminAppealItem)
async def intervene_appeal(
    appeal_id: UUID,
    payload: AdminAppealInterventionRequest,
    admin: CurrentAdmin,
    service: AdminServiceDependency,
) -> AdminAppealItem:
    return await service.intervene_appeal(appeal_id, payload, admin_id=admin.id)


@router.get("/audit", response_model=AuditPage)
async def audit_log(
    admin: CurrentAdmin,
    service: AdminServiceDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    action: str | None = None,
    actor_id: UUID | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditPage:
    del admin
    return await service.audit_log(
        page=page,
        page_size=page_size,
        action=action,
        actor_id=actor_id,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
    )


def _default_dates(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or datetime.now(UTC).date()
    return date_from or (end - timedelta(days=29)), end


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    admin: CurrentAdmin,
    service: AdminServiceDependency,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AnalyticsResponse:
    del admin
    start, end = _default_dates(date_from, date_to)
    return await service.analytics(start, end)


@router.get("/analytics/export")
async def analytics_export(
    admin: CurrentAdmin,
    service: AdminServiceDependency,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    del admin
    start, end = _default_dates(date_from, date_to)
    body = await service.analytics_csv(start, end)
    return Response(
        body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=otklik-appeals.csv",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
