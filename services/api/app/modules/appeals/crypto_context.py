from uuid import UUID


def appeal_content_aad(appeal_id: UUID) -> bytes:
    return b"otklik:appeal-content:" + appeal_id.bytes


def intake_answers_aad(appeal_id: UUID) -> bytes:
    return b"otklik:intake-answers:" + appeal_id.bytes


def crisis_contact_aad(appeal_id: UUID) -> bytes:
    return b"otklik:crisis-contact:" + appeal_id.bytes


def attachment_aad(appeal_id: UUID, attachment_id: UUID) -> bytes:
    return b"otklik:attachment:" + appeal_id.bytes + attachment_id.bytes


def rejection_reason_aad(appeal_id: UUID) -> bytes:
    return b"otklik:appeal-rejection:" + appeal_id.bytes


def appeal_message_aad(appeal_id: UUID, message_id: UUID) -> bytes:
    return b"otklik:appeal-message:" + appeal_id.bytes + message_id.bytes


def internal_note_aad(appeal_id: UUID, note_id: UUID) -> bytes:
    return b"otklik:internal-note:" + appeal_id.bytes + note_id.bytes


def transfer_reason_aad(appeal_id: UUID, request_id: UUID) -> bytes:
    return b"otklik:transfer-reason:" + appeal_id.bytes + request_id.bytes


def return_explanation_aad(appeal_id: UUID, explanation_id: UUID) -> bytes:
    return b"otklik:return-explanation:" + appeal_id.bytes + explanation_id.bytes


def feedback_comment_aad(appeal_id: UUID, feedback_id: UUID) -> bytes:
    return b"otklik:feedback-comment:" + appeal_id.bytes + feedback_id.bytes


def complaint_body_aad(appeal_id: UUID, complaint_id: UUID) -> bytes:
    return b"otklik:staff-complaint:" + appeal_id.bytes + complaint_id.bytes
