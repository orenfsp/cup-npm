import csv
import hashlib
import io
import secrets
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.email import SMTPMailer
from app.core.errors import (
    ConflictError,
    InfrastructureError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security.passwords import hash_password
from app.db.models import (
    AppealParticipant,
    ApplicantTypeConfig,
    AssignmentHistory,
    AuditLog,
    Category,
    CategoryGroupRule,
    CategoryIntakeQuestion,
    CrisisRule,
    CrisisSupportResource,
    ExpertGroupMembership,
    ExpertProfile,
    IntakeQuestion,
    SpecialistGroup,
    StaffInvitation,
    StaffUser,
    StatusHistory,
)
from app.db.models.enums import (
    AppealParticipantRole,
    AppealStatus,
    IntakeFieldType,
    StaffInvitationPurpose,
    StaffRole,
)
from app.db.repositories.admin import AdminRepository
from app.modules.admin.schemas import (
    AdminAppealInterventionRequest,
    AdminAppealItem,
    AdminAppealPage,
    AnalyticsDay,
    AnalyticsPoint,
    AnalyticsResponse,
    ApplicantTypeItem,
    ApplicantTypeRequest,
    ApplicantTypeUpdate,
    AuditItem,
    AuditPage,
    CategoryItem,
    CategoryQuestionMappingRequest,
    CategoryRequest,
    CategoryUpdate,
    CrisisRuleItem,
    CrisisRuleMatch,
    CrisisRuleRequest,
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
    RoutingItem,
    RoutingUpdateRequest,
    SafeSettingItem,
    SafeSettingsResponse,
    StaffAdminItem,
    StaffCreateRequest,
    StaffCreateResult,
    StaffUpdateRequest,
    SupportResourceItem,
    SupportResourceRequest,
    SupportResourceUpdate,
    WorkloadItem,
)
from app.modules.auth.service import normalize_login
from app.modules.crisis.detector import (
    CrisisDetector,
    CrisisRulePattern,
    compact_crisis_phrase,
    normalize_crisis_phrase,
)


class AdminService:
    """Administrator configuration only; this service never queries sensitive appeal data."""

    def __init__(self, repository: AdminRepository, settings: Settings, mailer: SMTPMailer) -> None:
        self._repository = repository
        self._settings = settings
        self._mailer = mailer

    async def list_staff(self) -> list[StaffAdminItem]:
        return [await self._staff_item(item) for item in await self._repository.list_staff()]

    async def create_staff(
        self, payload: StaffCreateRequest, *, admin_id: UUID
    ) -> StaffCreateResult:
        login = normalize_login(payload.login)
        display_name = payload.display_name.strip()
        if not login or not display_name:
            raise ValidationError("Login and display name are required.")
        if await self._repository.get_staff_by_login(login):
            raise ConflictError("Такой логин уже используется.")
        if await self._repository.get_staff_by_email(payload.email):
            raise ConflictError("Сотрудник с таким email уже существует.")
        temporary_password = self._temporary_password()
        staff = StaffUser(
            id=uuid4(),
            login=login,
            email=payload.email,
            password_hash=hash_password(temporary_password),
            role=payload.role,
            is_active=True,
            must_change_password=True,
            display_name=display_name,
        )
        dependent_records: list[object] = []
        if payload.role is StaffRole.EXPERT:
            dependent_records.append(
                ExpertProfile(
                    staff_user_id=staff.id,
                    public_specialist_label=self._clean(payload.public_specialist_label),
                    max_active_appeals=payload.max_active_appeals,
                )
            )
        dependent_records.append(
            self._audit(
                admin_id,
                "admin.staff_created",
                "staff_user",
                staff.id,
                {"role": payload.role.value},
            )
        )
        try:
            # Flush the parent first. Without an ORM relationship SQLAlchemy cannot
            # infer mapper ordering for a transient StaffUser and ExpertProfile
            # passed to the same add_all() call, despite the table-level FK.
            await self._repository.add(staff)
            await self._repository.add_all(dependent_records)
            await self._repository.commit()
        except IntegrityError as exc:
            await self._repository.rollback()
            constraint_name = self._integrity_constraint_name(exc)
            if constraint_name == "staff_users_login":
                raise ConflictError("Такой логин уже используется.") from exc
            if constraint_name == "uq_staff_users_email":
                raise ConflictError("Сотрудник с таким email уже существует.") from exc
            raise InfrastructureError(
                "Не удалось создать сотрудника из-за конфликта целостности данных."
            ) from exc
        return StaffCreateResult(
            staff=await self._staff_item(staff),
            temporary_password=temporary_password,
        )

    async def update_staff(
        self, staff_id: UUID, payload: StaffUpdateRequest, *, admin_id: UUID
    ) -> StaffAdminItem:
        staff = await self._staff(staff_id)
        existing_profile = await self._repository.get_expert_profile(staff.id)
        target_role = payload.role or staff.role
        profile_change_requested = (
            payload.max_active_appeals is not None
            or "public_specialist_label" in payload.model_fields_set
        )
        if target_role is not StaffRole.EXPERT and profile_change_requested:
            raise ValidationError("Expert profile settings require the expert role.")
        if (
            target_role is StaffRole.EXPERT
            and (
                existing_profile is None
                or not self._clean(existing_profile.public_specialist_label)
            )
            and not self._clean(payload.public_specialist_label)
        ):
            raise ValidationError("Expert specialization is required.")
        if staff.id == admin_id:
            if payload.is_active is False:
                raise ValidationError("You cannot deactivate your own account.")
            if payload.role is not None and payload.role is not StaffRole.ADMIN:
                raise ValidationError("You cannot remove your own administrator role.")
        changed_fields: list[str] = []
        if "email" in payload.model_fields_set:
            if payload.email is None:
                raise ValidationError("Staff email is required.")
            existing = await self._repository.get_staff_by_email(payload.email)
            if existing is not None and existing.id != staff.id:
                raise ConflictError("A staff user with this email already exists.")
            staff.email = payload.email
            changed_fields.append("email")
        if payload.display_name is not None:
            staff.display_name = payload.display_name.strip()
            changed_fields.append("display_name")
        now = datetime.now(UTC)
        if payload.role is not None and payload.role is not staff.role:
            if (
                staff.role is StaffRole.EXPERT
                and payload.role is not StaffRole.EXPERT
                and await self._repository.active_workload(staff.id)
            ):
                raise ConflictError("Reassign active appeals before changing the expert role.")
            staff.role = payload.role
            changed_fields.append("role")
            await self._repository.revoke_sessions(staff.id, now)
        if payload.is_active is not None and payload.is_active is not staff.is_active:
            staff.is_active = payload.is_active
            changed_fields.append("is_active")
            if not payload.is_active:
                await self._repository.revoke_sessions(staff.id, now)

        profile = existing_profile
        if profile_change_requested:
            if profile is None:
                profile = ExpertProfile(staff_user_id=staff.id, max_active_appeals=10)
                await self._repository.add(profile)
            if payload.max_active_appeals is not None:
                profile.max_active_appeals = payload.max_active_appeals
                changed_fields.append("max_active_appeals")
            if "public_specialist_label" in payload.model_fields_set:
                profile.public_specialist_label = self._clean(payload.public_specialist_label)
                changed_fields.append("public_specialist_label")
        if changed_fields:
            await self._repository.add_audit(
                self._audit(
                    admin_id,
                    "admin.staff_changed",
                    "staff_user",
                    staff.id,
                    {"fields": changed_fields},
                )
            )
            try:
                await self._repository.commit()
            except IntegrityError as exc:
                await self._repository.rollback()
                raise ConflictError("Staff metadata conflicts with another account.") from exc
        return await self._staff_item(staff)

    async def send_invitation(
        self, staff_id: UUID, *, admin_id: UUID, reset: bool
    ) -> InvitationResult:
        staff = await self._staff(staff_id)
        purpose = (
            StaffInvitationPurpose.PASSWORD_RESET if reset else StaffInvitationPurpose.INVITATION
        )
        return await self._issue_setup(staff, admin_id, purpose)

    async def setup_password(self, raw_token: str, new_password: str) -> None:
        digest = hashlib.sha256(raw_token.encode("utf-8")).digest()
        invitation = await self._repository.invitation_for_update(digest)
        now = datetime.now(UTC)
        if invitation is None or invitation.consumed_at is not None or invitation.expires_at <= now:
            raise UnauthorizedError("The setup link is invalid or expired.")
        staff = await self._repository.get_staff(invitation.staff_user_id)
        if staff is None or not staff.is_active:
            raise UnauthorizedError("The setup link is invalid or expired.")
        staff.password_hash = hash_password(new_password)
        staff.must_change_password = False
        invitation.consumed_at = now
        await self._repository.revoke_sessions(staff.id, now)
        await self._repository.add_audit(
            self._audit(
                None,
                "staff.password_configured",
                "staff_user",
                staff.id,
                {"purpose": invitation.purpose.value},
            )
        )
        await self._repository.commit()

    async def applicant_types(self) -> list[ApplicantTypeItem]:
        return [
            self._applicant_type_item(item)
            for item in await self._repository.list_applicant_types()
        ]

    async def create_applicant_type(
        self, payload: ApplicantTypeRequest, *, admin_id: UUID
    ) -> ApplicantTypeItem:
        if await self._repository.get_applicant_type_by_code(payload.code):
            raise ConflictError("Applicant type code already exists.")
        item = ApplicantTypeConfig(id=uuid4(), **payload.model_dump())
        await self._save_config(item, admin_id, "admin.applicant_type_created", "applicant_type")
        return self._applicant_type_item(item)

    async def update_applicant_type(
        self, item_id: UUID, payload: ApplicantTypeUpdate, *, admin_id: UUID
    ) -> ApplicantTypeItem:
        item = await self._repository.get_applicant_type(item_id)
        if item is None:
            raise NotFoundError("Applicant type not found.")
        self._apply(item, payload)
        await self._save_config(item, admin_id, "admin.applicant_type_changed", "applicant_type")
        return self._applicant_type_item(item)

    async def categories(self) -> list[CategoryItem]:
        return [self._category_item(item) for item in await self._repository.list_categories()]

    async def create_category(self, payload: CategoryRequest, *, admin_id: UUID) -> CategoryItem:
        if await self._repository.category_by_slug(payload.slug):
            raise ConflictError("Category slug already exists.")
        item = Category(id=uuid4(), **payload.model_dump())
        await self._save_config(item, admin_id, "admin.category_created", "category")
        return self._category_item(item)

    async def update_category(
        self, item_id: UUID, payload: CategoryUpdate, *, admin_id: UUID
    ) -> CategoryItem:
        item = await self._repository.get_category(item_id)
        if item is None:
            raise NotFoundError("Category not found.")
        self._apply(item, payload)
        await self._save_config(item, admin_id, "admin.category_changed", "category")
        return self._category_item(item)

    async def questions(self) -> list[IntakeQuestionItem]:
        mappings = await self._repository.question_mappings()
        categories_by_question: dict[UUID, list[UUID]] = {}
        for mapping in mappings:
            categories_by_question.setdefault(mapping.question_id, []).append(mapping.category_id)
        return [
            self._question_item(item, categories_by_question.get(item.id, []))
            for item in await self._repository.list_questions()
        ]

    async def create_question(
        self, payload: IntakeQuestionRequest, *, admin_id: UUID
    ) -> IntakeQuestionItem:
        if await self._repository.question_by_code(payload.code):
            raise ConflictError("Question code already exists.")
        data = payload.model_dump()
        data["options_json"] = data.pop("options")
        item = IntakeQuestion(id=uuid4(), **data)
        await self._save_config(item, admin_id, "admin.question_created", "intake_question")
        return self._question_item(item, [])

    async def update_question(
        self, item_id: UUID, payload: IntakeQuestionUpdate, *, admin_id: UUID
    ) -> IntakeQuestionItem:
        item = await self._repository.get_question(item_id)
        if item is None:
            raise NotFoundError("Question not found.")
        data = payload.model_dump(exclude_unset=True)
        if "options" in data:
            data["options_json"] = data.pop("options")
        for key, value in data.items():
            setattr(item, key, self._clean(value) if isinstance(value, str) else value)
        self._validate_question(item)
        await self._save_config(item, admin_id, "admin.question_changed", "intake_question")
        mappings = await self._repository.question_mappings()
        return self._question_item(
            item, [row.category_id for row in mappings if row.question_id == item.id]
        )

    async def set_category_questions(
        self,
        category_id: UUID,
        payload: CategoryQuestionMappingRequest,
        *,
        admin_id: UUID,
    ) -> None:
        if await self._repository.get_category(category_id) is None:
            raise NotFoundError("Category not found.")
        records: list[CategoryIntakeQuestion] = []
        for value in payload.questions:
            if await self._repository.get_question(value.question_id) is None:
                raise ValidationError("Unknown intake question.")
            records.append(
                CategoryIntakeQuestion(id=uuid4(), category_id=category_id, **value.model_dump())
            )
        await self._repository.replace_category_questions(category_id, records)
        await self._repository.add_audit(
            self._audit(
                admin_id,
                "admin.category_questions_changed",
                "category",
                category_id,
                {"question_ids": [str(item.question_id) for item in records]},
            )
        )
        await self._repository.commit()

    async def groups(self) -> list[GroupItem]:
        return [await self._group_item(item) for item in await self._repository.list_groups()]

    async def create_group(self, payload: GroupRequest, *, admin_id: UUID) -> GroupItem:
        if await self._repository.group_by_slug(payload.slug):
            raise ConflictError("Specialist group slug already exists.")
        item = SpecialistGroup(id=uuid4(), **payload.model_dump())
        await self._save_config(item, admin_id, "admin.group_created", "specialist_group")
        return await self._group_item(item)

    async def update_group(
        self, item_id: UUID, payload: GroupUpdate, *, admin_id: UUID
    ) -> GroupItem:
        item = await self._repository.get_group(item_id)
        if item is None:
            raise NotFoundError("Specialist group not found.")
        self._apply(item, payload)
        await self._save_config(item, admin_id, "admin.group_changed", "specialist_group")
        return await self._group_item(item)

    async def set_group_members(
        self, group_id: UUID, payload: GroupMembershipRequest, *, admin_id: UUID
    ) -> None:
        if await self._repository.get_group(group_id) is None:
            raise NotFoundError("Specialist group not found.")
        records: list[ExpertGroupMembership] = []
        for expert_id in payload.expert_ids:
            staff = await self._repository.get_staff(expert_id)
            if staff is None or staff.role is not StaffRole.EXPERT:
                raise ValidationError("Every group member must be an expert.")
            records.append(
                ExpertGroupMembership(id=uuid4(), expert_id=expert_id, specialist_group_id=group_id)
            )
        await self._repository.replace_group_members(group_id, records)
        await self._repository.add_audit(
            self._audit(
                admin_id,
                "admin.group_membership_changed",
                "specialist_group",
                group_id,
                {"expert_ids": [str(value) for value in payload.expert_ids]},
            )
        )
        await self._repository.commit()

    async def routing(self) -> list[RoutingItem]:
        return [
            RoutingItem(
                category_id=category.id,
                group_ids=await self._repository.routing_group_ids(category.id),
            )
            for category in await self._repository.list_categories()
        ]

    async def set_routing(
        self, category_id: UUID, payload: RoutingUpdateRequest, *, admin_id: UUID
    ) -> None:
        if await self._repository.get_category(category_id) is None:
            raise NotFoundError("Category not found.")
        if len(set(payload.group_ids)) != len(payload.group_ids):
            raise ValidationError("A group may only be selected once.")
        rules: list[CategoryGroupRule] = []
        for group_id in payload.group_ids:
            if await self._repository.get_group(group_id) is None:
                raise ValidationError("Unknown specialist group.")
            rules.append(
                CategoryGroupRule(id=uuid4(), category_id=category_id, specialist_group_id=group_id)
            )
        await self._repository.replace_routing(category_id, rules)
        await self._repository.add_audit(
            self._audit(
                admin_id,
                "admin.routing_changed",
                "category",
                category_id,
                {"group_ids": [str(value) for value in payload.group_ids]},
            )
        )
        await self._repository.commit()

    async def crisis_rules(self) -> list[CrisisRuleItem]:
        return [self._crisis_rule_item(item) for item in await self._repository.list_crisis_rules()]

    async def create_crisis_rule(
        self, payload: CrisisRuleRequest, *, admin_id: UUID
    ) -> CrisisRuleItem:
        phrase, normalized, compact = self._normalized_crisis(payload.phrase)
        if await self._repository.crisis_rule_by_normalized(normalized):
            raise ConflictError("An equivalent crisis phrase already exists.")
        item = CrisisRule(
            id=uuid4(),
            phrase=phrase,
            normalized_phrase=normalized,
            compact_phrase=compact,
            is_active=payload.is_active,
            allow_compact_match=payload.allow_compact_match,
            sort_order=payload.sort_order,
        )
        await self._save_config(item, admin_id, "admin.crisis_rule_created", "crisis_rule")
        return self._crisis_rule_item(item)

    async def update_crisis_rule(
        self, item_id: UUID, payload: CrisisRuleUpdate, *, admin_id: UUID
    ) -> CrisisRuleItem:
        item = await self._repository.get_crisis_rule(item_id)
        if item is None:
            raise NotFoundError("Crisis rule not found.")
        if payload.phrase is not None:
            phrase, normalized, compact = self._normalized_crisis(payload.phrase)
            existing = await self._repository.crisis_rule_by_normalized(normalized)
            if existing is not None and existing.id != item.id:
                raise ConflictError("An equivalent crisis phrase already exists.")
            item.phrase = phrase
            item.normalized_phrase = normalized
            item.compact_phrase = compact
        for field in ("is_active", "allow_compact_match", "sort_order"):
            value = getattr(payload, field)
            if value is not None:
                setattr(item, field, value)
        await self._save_config(item, admin_id, "admin.crisis_rule_changed", "crisis_rule")
        return self._crisis_rule_item(item)

    async def test_crisis_phrase(self, text: str) -> CrisisRuleTestResponse:
        matches: list[CrisisRuleMatch] = []
        for rule in await self._repository.list_crisis_rules(active_only=True):
            pattern = CrisisRulePattern(
                normalized_phrase=rule.normalized_phrase,
                compact_phrase=rule.compact_phrase,
                allow_compact_match=rule.allow_compact_match,
            )
            if CrisisDetector([pattern]).detect([text]):
                matches.append(CrisisRuleMatch(id=rule.id, phrase=rule.phrase))
        return CrisisRuleTestResponse(crisis_detected=bool(matches), matched_rules=matches)

    async def support_resources(self) -> list[SupportResourceItem]:
        return [
            self._support_item(item) for item in await self._repository.list_support_resources()
        ]

    async def create_support_resource(
        self, payload: SupportResourceRequest, *, admin_id: UUID
    ) -> SupportResourceItem:
        item = CrisisSupportResource(id=uuid4(), **payload.model_dump())
        await self._save_config(
            item, admin_id, "admin.support_resource_created", "crisis_support_resource"
        )
        return self._support_item(item)

    async def update_support_resource(
        self, item_id: UUID, payload: SupportResourceUpdate, *, admin_id: UUID
    ) -> SupportResourceItem:
        item = await self._repository.get_support_resource(item_id)
        if item is None:
            raise NotFoundError("Crisis support resource not found.")
        self._apply(item, payload)
        if not self._clean(item.phone) and not self._clean(item.url):
            raise ValidationError("Provide a phone number or URL.")
        await self._save_config(
            item, admin_id, "admin.support_resource_changed", "crisis_support_resource"
        )
        return self._support_item(item)

    def safe_settings(self) -> SafeSettingsResponse:
        return SafeSettingsResponse(
            settings=[
                SafeSettingItem(key="product_display_name", value="Отклик"),
                SafeSettingItem(
                    key="operator_overdue_hours", value=self._settings.operator_overdue_hours
                ),
                SafeSettingItem(
                    key="applicant_max_returns", value=self._settings.applicant_max_returns
                ),
                SafeSettingItem(
                    key="smtp_configured", value=str(self._settings.smtp_configured).lower()
                ),
            ]
        )

    async def appeal_metadata(
        self, *, page: int, page_size: int, status: AppealStatus | None
    ) -> AdminAppealPage:
        rows, total = await self._repository.list_appeal_metadata(
            page=page, page_size=page_size, status=status
        )
        return AdminAppealPage(
            items=[
                AdminAppealItem(
                    id=appeal.id,
                    applicant_type=appeal.applicant_type,
                    category_id=appeal.category_id,
                    category_name=category.name if category else None,
                    status=appeal.status,
                    priority=appeal.priority,
                    crisis_flag=appeal.crisis_flag,
                    assigned_expert_id=appeal.assigned_expert_id,
                    assigned_expert_display_name=expert.display_name if expert else None,
                    created_at=appeal.created_at,
                    updated_at=appeal.updated_at,
                    operator_accepted_at=appeal.operator_accepted_at,
                    first_specialist_response_at=appeal.first_specialist_response_at,
                    answer_ready_at=appeal.answer_ready_at,
                    completed_at=appeal.completed_at,
                )
                for appeal, category, expert in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def intervene_appeal(
        self,
        appeal_id: UUID,
        payload: AdminAppealInterventionRequest,
        *,
        admin_id: UUID,
    ) -> AdminAppealItem:
        appeal = await self._repository.get_appeal_for_update(appeal_id)
        if appeal is None:
            raise NotFoundError("Appeal not found.")
        reason = payload.reason.get_secret_value().strip()
        if not reason:
            raise ValidationError("A safe operational reason is required.")
        allowed_statuses = {
            AppealStatus.NEW,
            AppealStatus.ASSIGNED,
            AppealStatus.IN_PROGRESS,
            AppealStatus.NEEDS_CLARIFICATION,
            AppealStatus.RETURNED,
        }
        target_status = payload.status or appeal.status
        if payload.status is not None and payload.status not in allowed_statuses:
            raise ValidationError("Administrators may only unblock active workflow states.")

        assignment_supplied = "assigned_expert_id" in payload.model_fields_set
        target_expert_id = (
            payload.assigned_expert_id if assignment_supplied else appeal.assigned_expert_id
        )
        if target_status in {
            AppealStatus.ASSIGNED,
            AppealStatus.IN_PROGRESS,
            AppealStatus.NEEDS_CLARIFICATION,
        } and target_expert_id is None:
            raise ValidationError("This workflow state requires an assigned expert.")
        if target_expert_id is not None:
            expert = await self._repository.get_staff(target_expert_id)
            profile = await self._repository.get_expert_profile(target_expert_id)
            if (
                expert is None
                or profile is None
                or expert.role is not StaffRole.EXPERT
                or not expert.is_active
            ):
                raise ValidationError("Choose an active expert.")
            if appeal.category_id is None or not await self._repository.expert_is_eligible(
                target_expert_id, appeal.category_id
            ):
                raise ValidationError("The expert is not eligible for the selected category.")
            if (
                target_expert_id != appeal.assigned_expert_id
                and await self._repository.active_workload(target_expert_id)
                >= profile.max_active_appeals
            ):
                raise ConflictError("The selected expert is at capacity.")

        now = datetime.now(UTC)
        records: list[object] = []
        changes: list[str] = []
        if target_expert_id != appeal.assigned_expert_id:
            old_expert_id = appeal.assigned_expert_id
            primary = await self._repository.active_primary_participant(appeal.id)
            if primary is not None:
                primary.is_active = False
                primary.left_at = now
                await self._repository.flush()
            if target_expert_id is not None:
                participant = await self._repository.active_participant(
                    appeal.id, target_expert_id
                )
                if participant is not None:
                    participant.participant_role = AppealParticipantRole.PRIMARY
                else:
                    records.append(
                        AppealParticipant(
                            id=uuid4(),
                            appeal_id=appeal.id,
                            staff_user_id=target_expert_id,
                            participant_role=AppealParticipantRole.PRIMARY,
                            is_active=True,
                            joined_at=now,
                        )
                    )
            appeal.assigned_expert_id = target_expert_id
            records.append(
                AssignmentHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_expert_id=old_expert_id,
                    to_expert_id=target_expert_id,
                    changed_by_staff_user_id=admin_id,
                    reason=reason,
                    created_at=now,
                )
            )
            changes.append("assigned_expert_id")
        if payload.status is not None and payload.status is not appeal.status:
            records.append(
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=appeal.status,
                    to_status=payload.status,
                    changed_by_staff_user_id=admin_id,
                    reason=reason,
                    created_at=now,
                )
            )
            appeal.status = payload.status
            changes.append("status")
        if payload.priority is not None and payload.priority is not appeal.priority:
            appeal.priority = payload.priority
            changes.append("priority")
        if not changes:
            raise ValidationError("The requested values do not change the appeal.")
        records.append(
            AuditLog(
                id=uuid4(),
                actor_staff_user_id=admin_id,
                action="admin.appeal_intervened",
                entity_type="appeal",
                entity_id=appeal.id,
                reason=reason,
                metadata_json={"fields": changes},
            )
        )
        try:
            await self._repository.add_all(records)
            await self._repository.commit()
        except IntegrityError as exc:
            await self._repository.rollback()
            raise ConflictError("The appeal changed concurrently; reload and retry.") from exc
        row = await self._repository.get_appeal_metadata(appeal.id)
        if row is None:
            raise InfrastructureError("Updated appeal metadata could not be reloaded.")
        row_appeal, category, expert = row
        return AdminAppealItem(
            id=row_appeal.id,
            applicant_type=row_appeal.applicant_type,
            category_id=row_appeal.category_id,
            category_name=category.name if category else None,
            status=row_appeal.status,
            priority=row_appeal.priority,
            crisis_flag=row_appeal.crisis_flag,
            assigned_expert_id=row_appeal.assigned_expert_id,
            assigned_expert_display_name=expert.display_name if expert else None,
            created_at=row_appeal.created_at,
            updated_at=row_appeal.updated_at,
            operator_accepted_at=row_appeal.operator_accepted_at,
            first_specialist_response_at=row_appeal.first_specialist_response_at,
            answer_ready_at=row_appeal.answer_ready_at,
            completed_at=row_appeal.completed_at,
        )

    async def audit_log(
        self,
        *,
        page: int,
        page_size: int,
        action: str | None,
        actor_id: UUID | None,
        entity_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> AuditPage:
        rows, total = await self._repository.list_audit(
            page=page,
            page_size=page_size,
            action=action,
            actor_id=actor_id,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
        )
        return AuditPage(
            items=[
                AuditItem(
                    id=audit.id,
                    actor_staff_user_id=audit.actor_staff_user_id,
                    actor_display_name=display_name,
                    action=audit.action,
                    entity_type=audit.entity_type,
                    entity_id=audit.entity_id,
                    reason=audit.reason,
                    metadata=audit.metadata_json,
                    created_at=audit.created_at,
                )
                for audit, display_name in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def analytics(self, date_from: date, date_to: date) -> AnalyticsResponse:
        start, end = self._date_bounds(date_from, date_to)
        summary = await self._repository.analytics_summary(start, end)
        total = int(summary["total"] or 0)
        point_sets = {}
        for dimension in ("category", "applicant_type", "status"):
            point_sets[dimension] = [
                AnalyticsPoint(key=key, count=count)
                for key, count in await self._repository.analytics_distribution(
                    dimension, start, end
                )
            ]
        workloads = [
            WorkloadItem(
                staff_user_id=row[0],
                display_name=row[1],
                role=row[2],
                active_appeals=int(row[3] or 0),
                capacity=row[4],
            )
            for row in await self._repository.analytics_workloads(start, end)
        ]
        return AnalyticsResponse(
            date_from=date_from,
            date_to=date_to,
            total=total,
            new=int(summary["new"] or 0),
            active=int(summary["active"] or 0),
            completed=int(summary["completed"] or 0),
            urgent_share=(float(summary["urgent"] or 0) / total if total else None),
            returned_share=(float(summary["returned"] or 0) / total if total else None),
            avg_operator_acceptance_seconds=self._optional_float(summary["avg_operator"]),
            avg_first_response_seconds=self._optional_float(summary["avg_response"]),
            avg_resolution_seconds=self._optional_float(summary["avg_resolution"]),
            by_category=point_sets["category"],
            by_applicant_type=point_sets["applicant_type"],
            by_status=point_sets["status"],
            daily=[
                AnalyticsDay(date=day, count=count)
                for day, count in await self._repository.analytics_daily(start, end)
            ],
            workloads=workloads,
        )

    async def analytics_csv(self, date_from: date, date_to: date) -> bytes:
        start, end = self._date_bounds(date_from, date_to)
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "appeal_id",
                "created_at",
                "applicant_type",
                "category",
                "status",
                "priority",
                "crisis_flag",
                "operator_acceptance_seconds",
                "first_specialist_response_seconds",
                "resolution_seconds",
                "return_count",
            ]
        )
        for row in await self._repository.export_appeal_metadata(start, end):
            (
                appeal_id,
                created_at,
                applicant_type,
                category_name,
                status,
                priority,
                crisis_flag,
                operator_accepted_at,
                first_response_at,
                completed_at,
                return_count,
            ) = row
            writer.writerow(
                [
                    appeal_id,
                    created_at.isoformat(),
                    applicant_type,
                    self._csv_safe(category_name or ""),
                    status.value,
                    priority.value,
                    str(crisis_flag).lower(),
                    self._seconds(created_at, operator_accepted_at),
                    self._seconds(created_at, first_response_at),
                    self._seconds(created_at, completed_at),
                    return_count,
                ]
            )
        return output.getvalue().encode("utf-8-sig")

    @staticmethod
    def _date_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
        if date_to < date_from or (date_to - date_from).days > 366:
            raise ValidationError("Choose a valid date range of at most 366 days.")
        return (
            datetime.combine(date_from, time.min, tzinfo=UTC),
            datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _temporary_password(length: int = 16) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _integrity_constraint_name(exc: IntegrityError) -> str | None:
        pending: list[object] = [exc, exc.orig]
        visited: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in visited:
                continue
            visited.add(id(current))
            name = getattr(current, "constraint_name", None)
            if isinstance(name, str):
                return name
            diagnostics = getattr(current, "diag", None)
            diagnostic_name = getattr(diagnostics, "constraint_name", None)
            if isinstance(diagnostic_name, str):
                return diagnostic_name
            for attribute in ("orig", "__cause__", "__context__"):
                nested = getattr(current, attribute, None)
                if nested is not None:
                    pending.append(nested)
        return None

    @staticmethod
    def _seconds(start: datetime, end: datetime | None) -> int | str:
        return int((end - start).total_seconds()) if end is not None else ""

    @staticmethod
    def _csv_safe(value: str) -> str:
        return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value

    async def _issue_setup(
        self,
        staff: StaffUser,
        admin_id: UUID,
        purpose: StaffInvitationPurpose,
    ) -> InvitationResult:
        if not staff.email:
            raise ValidationError("Staff email is required before issuing an invitation.")
        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(48)
        invitation = StaffInvitation(
            id=uuid4(),
            staff_user_id=staff.id,
            issued_by_staff_user_id=admin_id,
            token_digest=hashlib.sha256(raw_token.encode("utf-8")).digest(),
            purpose=purpose,
            expires_at=now + timedelta(hours=self._settings.staff_invite_ttl_hours),
        )
        await self._repository.consume_open_invitations(staff.id, now)
        if purpose is StaffInvitationPurpose.PASSWORD_RESET:
            await self._repository.revoke_sessions(staff.id, now)
        await self._repository.add_all(
            [
                invitation,
                self._audit(
                    admin_id,
                    (
                        "admin.password_reset_issued"
                        if purpose is StaffInvitationPurpose.PASSWORD_RESET
                        else "admin.invitation_issued"
                    ),
                    "staff_user",
                    staff.id,
                    {"purpose": purpose.value},
                ),
            ]
        )
        await self._repository.commit()
        email_sent = True
        message = "Приглашение отправлено."
        try:
            await self._mailer.send_staff_setup(
                recipient=staff.email,
                login=staff.login,
                role=staff.role,
                raw_token=raw_token,
                purpose=purpose,
            )
        except InfrastructureError:
            email_sent = False
            message = (
                "Сотрудник сохранён, но письмо не отправлено: SMTP не настроен или недоступен."
            )
        return InvitationResult(
            staff=await self._staff_item(staff), email_sent=email_sent, message=message
        )

    async def _staff(self, staff_id: UUID) -> StaffUser:
        staff = await self._repository.get_staff(staff_id)
        if staff is None:
            raise NotFoundError("Staff user not found.")
        return staff

    async def _staff_item(self, staff: StaffUser) -> StaffAdminItem:
        profile = (
            await self._repository.get_expert_profile(staff.id)
            if staff.role is StaffRole.EXPERT
            else None
        )
        return StaffAdminItem(
            id=staff.id,
            login=staff.login,
            email=staff.email,
            display_name=staff.display_name,
            role=staff.role,
            is_active=staff.is_active,
            created_at=staff.created_at,
            last_login_at=staff.last_login_at,
            public_specialist_label=(profile.public_specialist_label if profile else None),
            max_active_appeals=(profile.max_active_appeals if profile else None),
            active_appeals=(await self._repository.active_workload(staff.id) if profile else 0),
            group_ids=(
                await self._repository.list_membership_group_ids(staff.id) if profile else []
            ),
            password_configured=staff.password_hash is not None,
        )

    async def _group_item(self, group: SpecialistGroup) -> GroupItem:
        member_ids = await self._repository.group_member_ids(group.id)
        profiles = [await self._repository.get_expert_profile(value) for value in member_ids]
        loads = [await self._repository.active_workload(value) for value in member_ids]
        active_experts = 0
        available_experts = 0
        total_capacity = 0
        active_load = 0
        for member_id, profile, load in zip(member_ids, profiles, loads, strict=True):
            staff = await self._repository.get_staff(member_id)
            if (
                profile is None
                or staff is None
                or not staff.is_active
                or staff.role is not StaffRole.EXPERT
            ):
                continue
            active_experts += 1
            active_load += load
            total_capacity += profile.max_active_appeals
            available_experts += int(load < profile.max_active_appeals)
        return GroupItem(
            id=group.id,
            slug=group.slug,
            name=group.name,
            description=group.description,
            is_active=group.is_active,
            member_ids=member_ids,
            active_experts=active_experts,
            available_experts=available_experts,
            active_load=active_load,
            total_capacity=total_capacity,
        )

    async def _save_config(
        self,
        item: object,
        admin_id: UUID,
        action: str,
        entity_type: str,
    ) -> None:
        item_id = item.id
        try:
            await self._repository.add(item)
            await self._repository.add_audit(self._audit(admin_id, action, entity_type, item_id))
            await self._repository.commit()
        except IntegrityError as exc:
            await self._repository.rollback()
            raise ConflictError("Configuration conflicts with an existing record.") from exc

    @staticmethod
    def _apply(item: object, payload: object) -> None:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value.strip() if isinstance(value, str) else value)

    @staticmethod
    def _clean(value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None

    @staticmethod
    def _validate_question(item: IntakeQuestion) -> None:
        item.options_json = [value.strip() for value in item.options_json]
        if len(item.options_json) > 30:
            raise ValidationError("A question may define at most 30 options.")
        if any(not value or len(value) > 200 for value in item.options_json):
            raise ValidationError("Choice options must be 1–200 characters.")
        if len(set(item.options_json)) != len(item.options_json):
            raise ValidationError("Choice options must be unique.")
        choice = item.field_type in {
            IntakeFieldType.SINGLE_CHOICE,
            IntakeFieldType.MULTI_CHOICE,
        }
        if choice and len(item.options_json) < 2:
            raise ValidationError("Choice questions require at least two options.")
        if not choice and item.options_json:
            raise ValidationError("Only choice questions may define options.")

    @staticmethod
    def _normalized_crisis(phrase: str) -> tuple[str, str, str]:
        cleaned = phrase.strip()
        normalized = normalize_crisis_phrase(cleaned)
        compact = compact_crisis_phrase(cleaned)
        if not normalized or not compact:
            raise ValidationError("Crisis phrase must contain letters or numbers.")
        return cleaned, normalized, compact

    @staticmethod
    def _applicant_type_item(item: ApplicantTypeConfig) -> ApplicantTypeItem:
        return ApplicantTypeItem(
            id=item.id,
            code=item.code,
            label=item.label,
            description=item.description,
            tone=item.tone,
            is_active=item.is_active,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _category_item(item: Category) -> CategoryItem:
        return CategoryItem(
            id=item.id,
            slug=item.slug,
            name=item.name,
            description=item.description,
            is_active=item.is_active,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _question_item(item: IntakeQuestion, category_ids: list[UUID]) -> IntakeQuestionItem:
        return IntakeQuestionItem(
            id=item.id,
            code=item.code,
            label=item.label,
            help_text=item.help_text,
            field_type=item.field_type,
            options=item.options_json,
            required=item.required,
            is_active=item.is_active,
            sort_order=item.sort_order,
            category_ids=category_ids,
        )

    @staticmethod
    def _crisis_rule_item(item: CrisisRule) -> CrisisRuleItem:
        return CrisisRuleItem(
            id=item.id,
            phrase=item.phrase,
            normalized_phrase=item.normalized_phrase,
            is_active=item.is_active,
            allow_compact_match=item.allow_compact_match,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _support_item(item: CrisisSupportResource) -> SupportResourceItem:
        return SupportResourceItem(
            id=item.id,
            title=item.title,
            description=item.description,
            phone=item.phone,
            url=item.url,
            region=item.region,
            is_active=item.is_active,
            sort_order=item.sort_order,
        )

    @staticmethod
    def _audit(
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID,
        metadata: dict[str, object] | None = None,
    ) -> AuditLog:
        return AuditLog(
            id=uuid4(),
            actor_staff_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
