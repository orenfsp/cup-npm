from app.core.errors import ConflictError
from app.db.models.enums import AppealStatus

_OPERATOR_TRANSITIONS = {
    AppealStatus.NEW: {AppealStatus.ASSIGNED, AppealStatus.REJECTED},
    AppealStatus.RETURNED: {AppealStatus.ASSIGNED, AppealStatus.REJECTED},
}

_EXPERT_TRANSITIONS = {
    AppealStatus.ASSIGNED: {AppealStatus.IN_PROGRESS},
    AppealStatus.IN_PROGRESS: {
        AppealStatus.NEEDS_CLARIFICATION,
        AppealStatus.ANSWER_READY,
    },
    AppealStatus.NEEDS_CLARIFICATION: {
        AppealStatus.IN_PROGRESS,
        AppealStatus.ANSWER_READY,
    },
}

_APPLICANT_TRANSITIONS = {
    AppealStatus.NEEDS_CLARIFICATION: {AppealStatus.IN_PROGRESS},
    AppealStatus.ANSWER_READY: {AppealStatus.COMPLETED, AppealStatus.RETURNED},
}


def _require_transition(
    current: AppealStatus,
    target: AppealStatus,
    allowed: dict[AppealStatus, set[AppealStatus]],
    actor: str,
) -> None:
    if target not in allowed.get(current, set()):
        raise ConflictError(
            f"Appeal cannot transition from {current.value} to {target.value} by {actor}."
        )


def require_operator_transition(current: AppealStatus, target: AppealStatus) -> None:
    _require_transition(current, target, _OPERATOR_TRANSITIONS, "operator")


def require_expert_transition(current: AppealStatus, target: AppealStatus) -> None:
    _require_transition(current, target, _EXPERT_TRANSITIONS, "expert")


def require_applicant_transition(current: AppealStatus, target: AppealStatus) -> None:
    _require_transition(current, target, _APPLICANT_TRANSITIONS, "applicant")


def require_triage_status(current: AppealStatus) -> None:
    if current not in _OPERATOR_TRANSITIONS:
        raise ConflictError("Only new or returned appeals can be triaged by an operator.")
