from app.db.models.enums import AppealStatus, ApplicantTone, ApplicantType

_STATUS_TEXT: dict[AppealStatus, tuple[str, str]] = {
    AppealStatus.NEW: (
        "Мы получили твоё обращение. Скоро его посмотрит специалист.",
        "Мы получили ваше обращение. Скоро его посмотрит специалист.",
    ),
    AppealStatus.ASSIGNED: (
        "Мы передали обращение специалисту.",
        "Мы передали обращение специалисту.",
    ),
    AppealStatus.IN_PROGRESS: (
        "Специалист разбирается в ситуации.",
        "Специалист разбирается в ситуации.",
    ),
    AppealStatus.NEEDS_CLARIFICATION: (
        "Специалист задал вопрос — посмотри, пожалуйста.",
        "Специалист задал вопрос — посмотрите, пожалуйста.",
    ),
    AppealStatus.ANSWER_READY: (
        "Мы подготовили рекомендации.",
        "Мы подготовили рекомендации.",
    ),
    AppealStatus.RETURNED: (
        "Обращение уточняют, чтобы подобрать подходящую помощь.",
        "Обращение уточняют, чтобы подобрать подходящую помощь.",
    ),
    AppealStatus.COMPLETED: (
        "Работа с обращением завершена.",
        "Работа с обращением завершена.",
    ),
    AppealStatus.REJECTED: (
        "Сейчас обращение не может быть принято в работу.",
        "Сейчас обращение не может быть принято в работу.",
    ),
    AppealStatus.CLOSED_NO_RESPONSE: (
        "Обращение закрыто после ожидания ответа.",
        "Обращение закрыто после ожидания ответа.",
    ),
}


def applicant_status_text(
    status: AppealStatus,
    applicant_type: str,
    tone: ApplicantTone | None = None,
) -> str:
    student_text, formal_text = _STATUS_TEXT[status]
    informal = tone is ApplicantTone.INFORMAL or applicant_type == ApplicantType.STUDENT
    return student_text if informal else formal_text
