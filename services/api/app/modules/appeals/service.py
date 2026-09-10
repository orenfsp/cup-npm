from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.crypto import ContentCrypto, track_lookup_digest
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security.appeal_access import AppealAccessTokenService
from app.db.models import (
    Appeal,
    AppealContent,
    AppealFeedback,
    AppealIntakeAnswer,
    AppealMessage,
    AppealReturnExplanation,
    Category,
    CrisisContact,
    StaffComplaint,
    StatusHistory,
)
from app.db.models.enums import AppealPriority, AppealStatus, MessageAuthorType
from app.db.repositories.public_appeals import PublicAppealRepository
from app.modules.appeals.crypto_context import (
    appeal_content_aad,
    appeal_message_aad,
    complaint_body_aad,
    crisis_contact_aad,
    feedback_comment_aad,
    intake_answers_aad,
    rejection_reason_aad,
    return_explanation_aad,
)
from app.modules.appeals.schemas import (
    AppealCreatedResponse,
    AppealCreateRequest,
    ApplicantTypePublic,
    CategoryPublic,
    CrisisSupportResourcePublic,
    CurrentAppealResponse,
    FeedbackRequest,
    IntakeQuestionPublic,
    PublicMessage,
    PublicMessagesResponse,
    PublicReferenceResponse,
    StatusTimelineItem,
)
from app.modules.appeals.status import applicant_status_text
from app.modules.appeals.track import generate_track_number, normalize_track_number
from app.modules.appeals.transitions import require_applicant_transition
from app.modules.categories.reference_data import UNKNOWN_CATEGORY_SLUG
from app.modules.crisis.detector import CrisisDetector
from app.modules.crisis.service import CrisisRuleService

INVALID_TRACK_MESSAGE = "The track number is invalid or unavailable."
_INVALID_TRACK_PLACEHOLDER = "ОТК-2222-2222"


@dataclass(frozen=True, slots=True)
class AppealAccessResult:
    appeal_id: UUID
    access_token: str


@dataclass(frozen=True, slots=True)
class CreatedAppealResult:
    response: AppealCreatedResponse
    access_token: str


class PublicAppealService:
    def __init__(
        self,
        repository: PublicAppealRepository,
        settings: Settings,
        crisis_rule_service: CrisisRuleService | None = None,
    ) -> None:
        content_key = settings.content_encryption_key
        track_secret = settings.track_hmac_secret
        if content_key is None or not content_key.get_secret_value():
            raise InfrastructureError("Sensitive-content encryption is not configured.")
        if track_secret is None or not track_secret.get_secret_value():
            raise InfrastructureError("Track lookup is not configured.")
        self._repository = repository
        self._settings = settings
        self._crypto = ContentCrypto(content_key.get_secret_value())
        self._track_secret = track_secret.get_secret_value()
        self._access_tokens = AppealAccessTokenService(settings)
        self._crisis_rules = crisis_rule_service

    async def public_reference(self) -> PublicReferenceResponse:
        categories = await self._repository.list_active_categories()
        applicant_types = await self._repository.list_active_applicant_types()
        questions = await self._repository.list_active_intake_questions()
        mappings = await self._repository.list_question_mappings()
        category_ids: dict[UUID, list[UUID]] = {}
        required_category_ids: dict[UUID, list[UUID]] = {}
        for mapping in mappings:
            category_ids.setdefault(mapping.question_id, []).append(mapping.category_id)
            if mapping.required_override is True:
                required_category_ids.setdefault(mapping.question_id, []).append(
                    mapping.category_id
                )
        return PublicReferenceResponse(
            applicant_types=[
                ApplicantTypePublic(
                    code=item.code,
                    label=item.label,
                    description=item.description,
                    tone=item.tone,
                )
                for item in applicant_types
            ],
            categories=[self._category_public(category) for category in categories],
            intake_questions=[
                IntakeQuestionPublic(
                    id=question.code,
                    prompt_student=question.label,
                    prompt_formal=question.label,
                    label=question.label,
                    help_text=question.help_text,
                    field_type=question.field_type,
                    options=question.options_json,
                    required=question.required,
                    optional=not question.required,
                    category_ids=category_ids.get(question.id, []),
                    required_category_ids=required_category_ids.get(question.id, []),
                    max_length=(500 if question.field_type.value == "short_text" else 2000),
                )
                for question in questions
            ],
            crisis_support_resources=await self._crisis_resources(),
        )

    async def create_appeal(self, payload: AppealCreateRequest) -> CreatedAppealResult:
        description = payload.description.get_secret_value().strip() if payload.description else ""
        applicant_type = await self._repository.get_active_applicant_type(payload.applicant_type)
        if applicant_type is None:
            raise ValidationError("Choose an available applicant type.")
        intake_answers = self._plain_intake_answers(payload.intake_answers or {})
        category = None
        if payload.category_id is not None:
            category = await self._repository.get_category(payload.category_id)
            if category is None or not category.is_active:
                raise ValidationError("Choose an available category.")
            if category.slug == UNKNOWN_CATEGORY_SLUG and not description:
                raise ValidationError("Please describe the situation in your own words.")
        if category is None and not description:
            raise ValidationError("Choose a category or describe the situation.")

        intake_answers = await self._validated_intake_answers(
            intake_answers, category_id=category.id if category else None
        )

        patterns = (
            await self._crisis_rules.active_patterns() if self._crisis_rules is not None else None
        )
        detector = CrisisDetector(patterns) if patterns is not None else CrisisDetector()
        crisis_flag = detector.detect([description, *self._answer_text_values(intake_answers)])
        crisis_resources = await self._crisis_resources()
        for _attempt in range(5):
            track_number = generate_track_number()
            track_digest = track_lookup_digest(self._track_secret, track_number)
            if await self._repository.track_digest_exists(track_digest):
                continue
            appeal_id = uuid4()
            appeal = Appeal(
                id=appeal_id,
                track_digest=track_digest,
                applicant_type=applicant_type.code,
                category_id=category.id if category else None,
                status=AppealStatus.NEW,
                priority=AppealPriority.STANDARD,
                crisis_flag=crisis_flag,
                return_count=0,
            )
            content = (
                AppealContent(
                    appeal_id=appeal_id,
                    encrypted_content=self._crypto.encrypt_text(
                        description, aad=appeal_content_aad(appeal_id)
                    ),
                    key_version=self._crypto.key_version,
                )
                if description
                else None
            )
            answers = (
                AppealIntakeAnswer(
                    appeal_id=appeal_id,
                    encrypted_payload=self._crypto.encrypt_json(
                        intake_answers, aad=intake_answers_aad(appeal_id)
                    ),
                    key_version=self._crypto.key_version,
                )
                if intake_answers
                else None
            )
            initial_history = StatusHistory(
                id=uuid4(),
                appeal_id=appeal_id,
                from_status=None,
                to_status=AppealStatus.NEW,
                changed_by_staff_user_id=None,
            )
            try:
                await self._repository.add_appeal_bundle(appeal, content, answers, initial_history)
                await self._repository.commit()
            except IntegrityError:
                await self._repository.rollback()
                continue
            response = AppealCreatedResponse(
                track_number=track_number,
                status=AppealStatus.NEW,
                status_text=applicant_status_text(
                    AppealStatus.NEW, applicant_type.code, applicant_type.tone
                ),
                crisis_flag=crisis_flag,
                show_crisis_support=crisis_flag,
                crisis_support_resources=crisis_resources,
            )
            return CreatedAppealResult(
                response=response,
                access_token=self._access_tokens.issue(appeal_id),
            )
        raise InfrastructureError("A unique appeal track number could not be allocated.")

    async def access_appeal(self, supplied_track_number: str) -> AppealAccessResult:
        valid_format = True
        try:
            normalized = normalize_track_number(supplied_track_number)
        except ValueError:
            normalized = _INVALID_TRACK_PLACEHOLDER
            valid_format = False
        digest = track_lookup_digest(self._track_secret, normalized)
        appeal = await self._repository.get_appeal_by_digest(digest)
        if not valid_format or appeal is None:
            raise UnauthorizedError(INVALID_TRACK_MESSAGE)
        return AppealAccessResult(
            appeal_id=appeal.id,
            access_token=self._access_tokens.issue(appeal.id),
        )

    def decode_access_token(self, token: str) -> UUID:
        return self._access_tokens.decode(token).appeal_id

    async def current_appeal(self, appeal_id: UUID) -> CurrentAppealResponse:
        record = await self._repository.get_appeal_with_category(appeal_id)
        if record is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        appeal = record.appeal
        applicant_type = await self._repository.get_applicant_type_by_code(appeal.applicant_type)
        tone = applicant_type.tone if applicant_type else None
        history = await self._repository.list_status_history(appeal_id)
        rejection = (
            await self._repository.get_rejection(appeal_id)
            if appeal.status is AppealStatus.REJECTED
            else None
        )
        return CurrentAppealResponse(
            applicant_type=appeal.applicant_type,
            category=self._category_public(record.category) if record.category else None,
            status=appeal.status,
            status_text=applicant_status_text(appeal.status, appeal.applicant_type, tone),
            crisis_flag=appeal.crisis_flag,
            show_crisis_support=appeal.crisis_flag,
            crisis_support_resources=await self._crisis_resources(),
            created_at=appeal.created_at,
            updated_at=appeal.updated_at,
            timeline=[
                StatusTimelineItem(
                    status=item.to_status,
                    text=applicant_status_text(item.to_status, appeal.applicant_type, tone),
                    occurred_at=item.created_at,
                )
                for item in history
            ],
            rejection_reason=(
                self._crypto.decrypt_text(
                    rejection.encrypted_reason, aad=rejection_reason_aad(appeal_id)
                )
                if rejection
                else None
            ),
            return_count=appeal.return_count,
            max_returns=self._settings.applicant_max_returns,
        )

    async def messages(self, appeal_id: UUID) -> PublicMessagesResponse:
        if await self._repository.get_appeal(appeal_id) is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        messages = await self._repository.list_messages(appeal_id)
        return PublicMessagesResponse(
            messages=[
                PublicMessage(
                    id=message.id,
                    author_type=message.author_type,
                    author_label=(
                        "Специалист"
                        if message.author_type is MessageAuthorType.SPECIALIST
                        else "Вы"
                    ),
                    body=self._crypto.decrypt_text(
                        message.encrypted_body,
                        aad=appeal_message_aad(appeal_id, message.id),
                    ),
                    created_at=message.created_at,
                )
                for message in messages
            ]
        )

    async def send_message(
        self, appeal_id: UUID, body: str, *, now: datetime | None = None
    ) -> None:
        appeal = await self._repository.lock_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        if appeal.status not in {
            AppealStatus.ASSIGNED,
            AppealStatus.IN_PROGRESS,
            AppealStatus.NEEDS_CLARIFICATION,
        }:
            raise ConflictError("A message cannot be sent in the current appeal status.")
        normalized = body.strip()
        if not normalized:
            raise ValidationError("Message cannot be blank.")
        message_id = uuid4()
        records: list[object] = [
            AppealMessage(
                id=message_id,
                appeal_id=appeal.id,
                author_type=MessageAuthorType.APPLICANT,
                author_staff_user_id=None,
                encrypted_body=self._crypto.encrypt_text(
                    normalized, aad=appeal_message_aad(appeal.id, message_id)
                ),
                key_version=self._crypto.key_version,
            )
        ]
        if appeal.status is AppealStatus.NEEDS_CLARIFICATION:
            require_applicant_transition(appeal.status, AppealStatus.IN_PROGRESS)
            previous = appeal.status
            appeal.status = AppealStatus.IN_PROGRESS
            records.append(
                StatusHistory(
                    id=uuid4(),
                    appeal_id=appeal.id,
                    from_status=previous,
                    to_status=AppealStatus.IN_PROGRESS,
                    changed_by_staff_user_id=None,
                )
            )
        await self._repository.add_records(records)
        await self._repository.commit()

    async def resolve(
        self,
        appeal_id: UUID,
        *,
        choice: str,
        explanation: str | None,
        now: datetime | None = None,
    ) -> None:
        appeal = await self._repository.lock_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        current_time = now or datetime.now(UTC)
        target = AppealStatus.COMPLETED if choice == "helped" else AppealStatus.RETURNED
        require_applicant_transition(appeal.status, target)
        records: list[object] = []
        if target is AppealStatus.COMPLETED:
            appeal.completed_at = current_time
        else:
            if appeal.return_count >= self._settings.applicant_max_returns:
                raise ConflictError(
                    "The appeal has reached its return limit. Please use the complaint form "
                    "if you still need to report a problem."
                )
            normalized = explanation.strip() if explanation else ""
            if not normalized:
                raise ValidationError("Please explain what was missing.")
            explanation_id = uuid4()
            return_number = appeal.return_count + 1
            records.append(
                AppealReturnExplanation(
                    id=explanation_id,
                    appeal_id=appeal.id,
                    return_number=return_number,
                    encrypted_body=self._crypto.encrypt_text(
                        normalized,
                        aad=return_explanation_aad(appeal.id, explanation_id),
                    ),
                    key_version=self._crypto.key_version,
                )
            )
            appeal.return_count = return_number
            appeal.assigned_expert_id = None
            await self._repository.deactivate_participants(appeal.id, left_at=current_time)
        previous = appeal.status
        appeal.status = target
        records.append(
            StatusHistory(
                id=uuid4(),
                appeal_id=appeal.id,
                from_status=previous,
                to_status=target,
                changed_by_staff_user_id=None,
            )
        )
        await self._repository.add_records(records)
        await self._repository.commit()

    async def submit_feedback(self, appeal_id: UUID, payload: FeedbackRequest) -> None:
        appeal = await self._repository.get_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        if appeal.status not in {
            AppealStatus.ANSWER_READY,
            AppealStatus.COMPLETED,
            AppealStatus.RETURNED,
        }:
            raise ConflictError("Feedback is available after recommendations are ready.")
        feedback_id = uuid4()
        comment = payload.comment.get_secret_value().strip() if payload.comment else ""
        await self._repository.add_feedback(
            AppealFeedback(
                id=feedback_id,
                appeal_id=appeal.id,
                rating=payload.rating,
                encrypted_comment=(
                    self._crypto.encrypt_text(
                        comment, aad=feedback_comment_aad(appeal.id, feedback_id)
                    )
                    if comment
                    else None
                ),
                key_version=self._crypto.key_version if comment else None,
            )
        )
        await self._repository.commit()

    async def submit_complaint(self, appeal_id: UUID, body: str) -> None:
        if await self._repository.get_appeal(appeal_id) is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        normalized = body.strip()
        if not normalized:
            raise ValidationError("Complaint cannot be blank.")
        complaint_id = uuid4()
        await self._repository.add_complaint(
            StaffComplaint(
                id=complaint_id,
                appeal_id=appeal_id,
                encrypted_body=self._crypto.encrypt_text(
                    normalized, aad=complaint_body_aad(appeal_id, complaint_id)
                ),
                key_version=self._crypto.key_version,
            )
        )
        await self._repository.commit()

    async def save_crisis_contact(self, appeal_id: UUID, contact: str) -> None:
        appeal = await self._repository.get_appeal(appeal_id)
        if appeal is None:
            raise UnauthorizedError("Appeal access is invalid or expired.")
        if not appeal.crisis_flag:
            raise ForbiddenError("A crisis contact is only available for a crisis appeal.")
        normalized_contact = contact.strip()
        if not normalized_contact:
            raise ValidationError("Contact information cannot be blank.")
        await self._repository.upsert_crisis_contact(
            CrisisContact(
                appeal_id=appeal_id,
                encrypted_contact=self._crypto.encrypt_text(
                    normalized_contact, aad=crisis_contact_aad(appeal_id)
                ),
                key_version=self._crypto.key_version,
            )
        )
        await self._repository.commit()

    async def _crisis_resources(self) -> list[CrisisSupportResourcePublic]:
        configured = await self._repository.list_active_crisis_support_resources()
        if configured:
            return [
                CrisisSupportResourcePublic(
                    title=item.title,
                    message=item.description,
                    phone=item.phone,
                    url=item.url,
                    requires_organizer_verification=False,
                )
                for item in configured
            ]
        return [
            CrisisSupportResourcePublic(
                title=self._settings.crisis_support_title,
                message=self._settings.crisis_support_message,
                phone=self._settings.crisis_support_phone or None,
                url=self._settings.crisis_support_url or None,
                requires_organizer_verification=(
                    self._settings.crisis_support_requires_organizer_verification
                ),
            )
        ]

    async def _validated_intake_answers(
        self,
        answers: dict[str, str | bool | list[str]],
        *,
        category_id: UUID | None,
    ) -> dict[str, str | bool | list[str]]:
        questions = await self._repository.list_active_intake_questions()
        mappings = await self._repository.list_question_mappings()
        mapped = {
            row.question_id: row
            for row in mappings
            if category_id is not None and row.category_id == category_id
        }
        allowed = {
            question.code: (question, mapped.get(question.id))
            for question in questions
            if category_id is None or question.id in mapped
        }
        if not set(answers).issubset(allowed):
            raise ValidationError("One or more intake answers are not available.")
        for code, (question, mapping) in allowed.items():
            required = (
                mapping.required_override
                if mapping is not None and mapping.required_override is not None
                else question.required
            )
            value = answers.get(code)
            if required and self._answer_is_empty(value):
                raise ValidationError(f"Answer the required question: {question.label}")
            if value is not None:
                self._validate_answer(question, value)
        return answers

    @staticmethod
    def _plain_intake_answers(
        answers: dict[str, Any],
    ) -> dict[str, str | bool | list[str]]:
        result: dict[str, str | bool | list[str]] = {}
        for code, value in answers.items():
            if isinstance(value, bool):
                result[code] = value
            elif isinstance(value, list):
                cleaned = [item.get_secret_value().strip() for item in value]
                if cleaned:
                    result[code] = cleaned
            else:
                cleaned = value.get_secret_value().strip()
                if cleaned:
                    result[code] = cleaned
        return result

    @staticmethod
    def _answer_text_values(
        answers: dict[str, str | bool | list[str]],
    ) -> list[str]:
        values: list[str] = []
        for value in answers.values():
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                values.extend(value)
        return values

    @staticmethod
    def _answer_is_empty(value: str | bool | list[str] | None) -> bool:
        return value is None or value == "" or value == []

    @staticmethod
    def _validate_answer(question, value: str | bool | list[str]) -> None:
        field_type = question.field_type.value
        if field_type in {"short_text", "long_text"}:
            maximum = 500 if field_type == "short_text" else 2000
            if not isinstance(value, str) or len(value) > maximum:
                raise ValidationError("An intake text answer has an invalid value.")
            return
        if field_type == "boolean":
            if not isinstance(value, bool):
                raise ValidationError("A boolean intake answer has an invalid value.")
            return
        if field_type == "single_choice":
            if not isinstance(value, str) or value not in question.options_json:
                raise ValidationError("A choice answer has an invalid option.")
            return
        if (
            not isinstance(value, list)
            or not value
            or any(item not in question.options_json for item in value)
            or len(set(value)) != len(value)
        ):
            raise ValidationError("A multiple-choice answer has invalid options.")

    @staticmethod
    def _category_public(category: Category) -> CategoryPublic:
        return CategoryPublic(
            id=category.id,
            slug=category.slug,
            name=category.name,
            description=category.description,
            requires_description=category.slug == UNKNOWN_CATEGORY_SLUG,
        )
