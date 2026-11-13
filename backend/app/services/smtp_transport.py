"""Shared SMTP relay transport; errors never include credentials or message contents."""

from __future__ import annotations

import os
import smtplib
import ssl
from contextlib import contextmanager
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses


class SMTPDeliveryUnavailable(RuntimeError):
    """Stable, non-sensitive error code for a relay operation."""


def mailbox(value: str) -> str:
    if any(c in value for c in "\r\n"):
        raise SMTPDeliveryUnavailable("invalid_envelope_sender")
    addresses = getaddresses([value])
    if len(addresses) != 1:
        raise SMTPDeliveryUnavailable("invalid_envelope_sender")
    _, address = addresses[0]
    if not address or "@" not in address or any(c in address for c in " ,;<>"):
        raise SMTPDeliveryUnavailable("invalid_envelope_sender")
    return address


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise SMTPDeliveryUnavailable("invalid_smtp_configuration")
    return value.lower() in {"true", "1", "yes", "on"}


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    timeout: int
    tls: str
    username: str | None = field(repr=False)
    password: str | None = field(repr=False)
    envelope_from: str | None

    @classmethod
    def from_env(cls):
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            raise SMTPDeliveryUnavailable("no_smtp_host")
        try:
            port = int(os.getenv("SMTP_PORT", "587"))
            timeout = int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))
        except ValueError:
            raise SMTPDeliveryUnavailable("invalid_smtp_configuration") from None
        if not 1 <= port <= 65535 or not 1 <= timeout <= 120:
            raise SMTPDeliveryUnavailable("invalid_smtp_configuration")
        implicit = _boolean("SMTP_SSL", False)
        starttls = _boolean("SMTP_STARTTLS", not implicit)
        if implicit and starttls:
            raise SMTPDeliveryUnavailable("conflicting_smtp_tls_modes")
        username = os.getenv("SMTP_USERNAME") or None
        password = os.getenv("SMTP_PASSWORD") or None
        if bool(username) != bool(password):
            raise SMTPDeliveryUnavailable("incomplete_smtp_credentials")
        if username and not (implicit or starttls):
            raise SMTPDeliveryUnavailable("smtp_credentials_require_tls")
        sender = os.getenv("SMTP_ENVELOPE_FROM", "").strip()
        return cls(
            host,
            port,
            timeout,
            "ssl" if implicit else "starttls" if starttls else "none",
            username,
            password,
            mailbox(sender) if sender else None,
        )


@contextmanager
def relay_connection(settings: SMTPSettings):
    smtp_cls = smtplib.SMTP_SSL if settings.tls == "ssl" else smtplib.SMTP
    options = {"context": ssl.create_default_context()} if settings.tls == "ssl" else {}
    try:
        with smtp_cls(settings.host, settings.port, timeout=settings.timeout, **options) as smtp:
            status, _ = smtp.ehlo()
            if status != 250:
                raise SMTPDeliveryUnavailable("smtp_ehlo_failed")
            if settings.tls == "starttls":
                smtp.starttls(context=ssl.create_default_context())
                status, _ = smtp.ehlo()
                if status != 250:
                    raise SMTPDeliveryUnavailable("smtp_ehlo_failed")
            if settings.username:
                smtp.login(settings.username, settings.password)
            yield smtp
    except SMTPDeliveryUnavailable:
        raise
    except smtplib.SMTPAuthenticationError:
        raise SMTPDeliveryUnavailable("smtp_authentication_failed") from None
    except smtplib.SMTPNotSupportedError:
        raise SMTPDeliveryUnavailable("smtp_required_capability_unavailable") from None
    except ssl.SSLError:
        raise SMTPDeliveryUnavailable("smtp_tls_failed") from None
    except (smtplib.SMTPException, OSError):
        raise SMTPDeliveryUnavailable("smtp_failed") from None


def check_relay() -> dict:
    """Check connection/TLS/auth only; never issue MAIL, RCPT, or DATA commands."""
    settings = SMTPSettings.from_env()
    with relay_connection(settings) as smtp:
        status, _ = smtp.noop()
        if status != 250:
            raise SMTPDeliveryUnavailable("smtp_noop_failed")
    return {
        "connected": True,
        "tls": settings.tls,
        "authentication": "account" if settings.username else "none",
        "message_sent": False,
        "external_relay_verified": False,
    }


def send_smtp_message(message: EmailMessage) -> dict:
    settings = SMTPSettings.from_env()
    with relay_connection(settings) as smtp:
        # Explicitly separate MAIL FROM (bounce address) from visible From/Reply-To.
        options = {"from_addr": settings.envelope_from} if settings.envelope_from else {}
        refused = smtp.send_message(message, **options)
        if refused:
            # Some recipients may already have been accepted; do not automatically retry.
            raise SMTPDeliveryUnavailable("smtp_partial_recipient_refusal")
    return {
        "sent": True,
        "delivery": "smtp",
        "relay_accepted": True,
        "recipient_delivery_confirmed": False,
    }
