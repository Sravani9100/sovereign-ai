"""Sending email. Console for development, SMTP for everything else.

SMTP covers most providers (Gmail with an app password, Microsoft 365, Brevo, Resend, Postmark,
Mailjet) without adding an SDK per provider.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

from sovereign.config import Settings

log = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleMailer:
    """Development only: prints messages to the API log instead of sending them."""

    def send(self, to: str, subject: str, body: str) -> None:
        log.warning("EMAIL (console backend, not sent) to=%s subject=%r\n%s", to, subject, body)


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.sender = settings.email_from

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        if self.port == 465:
            server = smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=20)
            server.starttls(context=context)
        with server:
            if self.username and self.password:
                server.login(self.username, self.password.get_secret_value())
            server.send_message(message)


@dataclass
class FakeMailer:
    """Tests: keeps what would have been sent."""

    sent: list[tuple[str, str, str]] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def make_mailer(settings: Settings) -> Mailer:
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise ValueError("SOVEREIGN_SMTP_HOST is required when SOVEREIGN_EMAIL_BACKEND=smtp")
        return SmtpMailer(settings)
    return ConsoleMailer()
