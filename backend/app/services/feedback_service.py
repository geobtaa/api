from __future__ import annotations

import os
import re
import smtplib
import subprocess
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

FEEDBACK_TOPICS = {
    "Correction",
    "Question",
    "Comments or Suggestions",
    "Harmful language",
    "Other",
}
DEFAULT_FEEDBACK_RECIPIENTS = "majew030@umn.edu,btaa-gdp@umn.edu,geoportal@btaa.org"


class FeedbackDeliveryUnavailable(RuntimeError):
    """Raised when feedback mail cannot be delivered with current configuration."""


@dataclass(frozen=True)
class FeedbackSubmission:
    name: str
    email_address: str
    topic: str
    description: str
    source_url: str = ""
    user_agent: str = ""
    contact_info: str = ""


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]


def _feedback_delivery() -> str:
    configured = os.getenv("FEEDBACK_DELIVERY") or os.getenv("BRIDGE_SYNC_REPORT_DELIVERY")
    if configured:
        return configured.strip().lower()
    return "sendmail" if os.path.exists("/usr/sbin/sendmail") else "smtp"


def _sender() -> str:
    sender = os.getenv("FEEDBACK_FROM") or os.getenv("SMTP_FROM")
    if sender:
        return sender
    return formataddr(("BTAA Geoportal", "no-reply@geo.btaa.org"))


def _subject(topic: str) -> str:
    prefix = os.getenv("FEEDBACK_SUBJECT_PREFIX", "BTAA Geoportal Feedback")
    return f"{prefix}: {topic}"


def _build_message(submission: FeedbackSubmission, recipients: list[str]) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = _subject(submission.topic)
    message["From"] = _sender()
    message["To"] = ", ".join(recipients)

    if submission.email_address:
        reply_name = submission.name or submission.email_address
        message["Reply-To"] = formataddr((reply_name, submission.email_address))

    submitted_by = submission.name or "Not provided"
    submitted_email = submission.email_address or "Not provided"
    source_url = submission.source_url or "Not provided"
    user_agent = submission.user_agent or "Not provided"

    message.set_content(
        "\n".join(
            [
                "A BTAA Geoportal feedback form was submitted.",
                "",
                f"Topic: {submission.topic}",
                f"Name: {submitted_by}",
                f"Email: {submitted_email}",
                f"Source URL: {source_url}",
                f"User-Agent: {user_agent}",
                "",
                "Description:",
                submission.description,
            ]
        )
    )
    return message


def send_feedback_email(submission: FeedbackSubmission) -> dict:
    if not _env_bool("FEEDBACK_EMAIL_ENABLED", True):
        raise FeedbackDeliveryUnavailable("feedback_email_disabled")

    if submission.contact_info.strip():
        return {"sent": False, "reason": "honeypot"}

    recipients = _split_recipients(os.getenv("FEEDBACK_RECIPIENTS", DEFAULT_FEEDBACK_RECIPIENTS))
    if not recipients:
        raise FeedbackDeliveryUnavailable("no_feedback_recipients")

    delivery = _feedback_delivery()
    message = _build_message(submission, recipients)

    if delivery == "sendmail":
        sendmail_path = os.getenv("SENDMAIL_PATH", "/usr/sbin/sendmail")
        sendmail_args = os.getenv("SENDMAIL_ARGS", "-t -i").split()
        try:
            subprocess.run(
                [sendmail_path, *sendmail_args],
                input=message.as_bytes(),
                check=True,
                timeout=_env_int("SENDMAIL_TIMEOUT_SECONDS", 20),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise FeedbackDeliveryUnavailable("sendmail_failed") from exc
        return {"sent": True, "delivery": "sendmail", "recipients": len(recipients)}

    host = os.getenv("SMTP_HOST")
    if not host:
        raise FeedbackDeliveryUnavailable("no_smtp_host")

    port = _env_int("SMTP_PORT", 587)
    timeout = _env_int("SMTP_TIMEOUT_SECONDS", 20)
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = _env_bool("SMTP_SSL", False)
    use_starttls = _env_bool("SMTP_STARTTLS", not use_ssl)

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    try:
        with smtp_cls(host, port, timeout=timeout) as smtp:
            if use_starttls and not use_ssl:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except OSError as exc:
        raise FeedbackDeliveryUnavailable("smtp_failed") from exc

    return {"sent": True, "delivery": "smtp", "recipients": len(recipients)}
