"""Envío de emails con fallback simulado."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path

from app.config import get_settings


@dataclass(frozen=True, slots=True)
class EmailResult:
    success: bool
    simulated: bool
    message: str


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send_invoice_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        attachment_path: str | Path | None = None,
    ) -> EmailResult:
        if not recipient.strip():
            return EmailResult(False, False, "El cliente no tiene email configurado.")

        if not self.settings.smtp_configured:
            return EmailResult(True, True, "SMTP no configurado. Se ha simulado el envío correctamente.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_sender
        message["To"] = recipient
        message.set_content(body)

        if attachment_path is not None:
            path = Path(attachment_path)
            with path.open("rb") as handle:
                message.add_attachment(
                    handle.read(),
                    maintype="application",
                    subtype="pdf",
                    filename=path.name,
                )

        try:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.settings.smtp_username, self.settings.smtp_password)
                server.send_message(message)
        except Exception as exc:
            return EmailResult(False, False, f"No se pudo enviar el email: {exc}")

        return EmailResult(True, False, "Email enviado correctamente.")
