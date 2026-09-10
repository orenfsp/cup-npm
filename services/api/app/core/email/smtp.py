import asyncio
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.errors import InfrastructureError
from app.db.models.enums import StaffInvitationPurpose, StaffRole


class SMTPMailer:
    """Small server-side SMTP adapter; messages never include appeal data."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_staff_setup(
        self,
        *,
        recipient: str,
        login: str,
        role: StaffRole,
        raw_token: str,
        purpose: StaffInvitationPurpose,
    ) -> None:
        if not self._settings.smtp_configured:
            raise InfrastructureError("SMTP is not configured.")
        query = urlencode({"token": raw_token})
        link = f"{self._settings.staff_frontend_base_url.rstrip('/')}/staff/setup-password?{query}"
        subject = (
            "Настройка доступа в Отклик"
            if purpose is StaffInvitationPurpose.INVITATION
            else "Сброс пароля в Отклик"
        )
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{self._settings.smtp_from_name} <{self._settings.smtp_from_email}>"
        message["To"] = recipient
        message.set_content(
            "Отклик\n\n"
            f"Логин: {login}\n"
            f"Роль: {role.value}\n\n"
            f"Установить новый пароль: {link}\n\n"
            "Ссылка одноразовая и имеет ограниченный срок действия."
        )
        await asyncio.to_thread(self._send, message)

    def _send(self, message: EmailMessage) -> None:
        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as client:
                if self._settings.smtp_use_tls:
                    client.starttls()
                password = self._settings.smtp_password
                if self._settings.smtp_username:
                    if password is None or not password.get_secret_value():
                        raise InfrastructureError("SMTP credentials are incomplete.")
                    client.login(self._settings.smtp_username, password.get_secret_value())
                client.send_message(message)
        except InfrastructureError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            raise InfrastructureError("Invitation email could not be sent.") from exc
