import smtplib
import ssl
from email.message import EmailMessage

import pytest

from app.services import smtp_transport as transport


@pytest.fixture
def relay(monkeypatch):
    for name in (
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_SSL",
        "SMTP_STARTTLS",
        "SMTP_ENVELOPE_FROM",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_TIMEOUT_SECONDS", "10")
    calls = []

    class FakeSMTP:
        refused = {}

        def __init__(self, host, port, **options):
            calls.append(("connect", host, port, options))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            calls.append(("quit",))

        def ehlo(self):
            calls.append(("ehlo",))
            return 250, b"hello"

        def starttls(self, *, context):
            assert context.check_hostname
            assert context.verify_mode == ssl.CERT_REQUIRED
            calls.append(("starttls",))

        def login(self, username, password):
            calls.append(("login", username, password))

        def noop(self):
            calls.append(("noop",))
            return 250, b"ok"

        def send_message(self, message, **options):
            calls.append(("send", message, options))
            return self.refused

    monkeypatch.setattr(transport.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(transport.smtplib, "SMTP_SSL", FakeSMTP)
    return calls, FakeSMTP


def message():
    email = EmailMessage()
    email["From"] = "Geoportal <visible@example.edu>"
    email["To"] = "colleague@another-campus.edu"
    email["Reply-To"] = "team@example.edu"
    email.set_content("Synthetic diagnostic message")
    return email


def test_ip_relay_check_uses_tls_without_sending(relay):
    calls, _ = relay
    result = transport.check_relay()
    assert [call[0] for call in calls] == ["connect", "ehlo", "starttls", "ehlo", "noop", "quit"]
    assert result == {
        "connected": True,
        "tls": "starttls",
        "authentication": "none",
        "message_sent": False,
        "external_relay_verified": False,
    }


def test_account_authentication_only_after_verified_tls(relay, monkeypatch):
    calls, _ = relay
    monkeypatch.setenv("SMTP_USERNAME", "department")
    monkeypatch.setenv("SMTP_PASSWORD", "test-only-password")
    result = transport.check_relay()
    assert [call[0] for call in calls] == [
        "connect",
        "ehlo",
        "starttls",
        "ehlo",
        "login",
        "noop",
        "quit",
    ]
    assert result["authentication"] == "account"
    assert "test-only-password" not in repr(transport.SMTPSettings.from_env())
    assert "department" not in repr(transport.SMTPSettings.from_env())


def test_envelope_sender_does_not_change_visible_headers(relay, monkeypatch):
    calls, _ = relay
    monkeypatch.setenv("SMTP_ENVELOPE_FROM", "bounces@example.edu")
    email = message()
    result = transport.send_smtp_message(email)
    send = next(call for call in calls if call[0] == "send")
    assert send[2] == {"from_addr": "bounces@example.edu"}
    assert str(email["From"]) == "Geoportal <visible@example.edu>"
    assert str(email["Reply-To"]) == "team@example.edu"
    assert result["relay_accepted"] is True
    assert result["recipient_delivery_confirmed"] is False


def test_implicit_tls_verifies_certificates(relay, monkeypatch):
    calls, _ = relay
    monkeypatch.setenv("SMTP_SSL", "true")
    transport.check_relay()
    context = calls[0][3]["context"]
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert "starttls" not in [call[0] for call in calls]


@pytest.mark.parametrize(
    "values,error",
    [
        ({"SMTP_HOST": ""}, "no_smtp_host"),
        ({"SMTP_USERNAME": "only-user"}, "incomplete_smtp_credentials"),
        ({"SMTP_PASSWORD": "only-password"}, "incomplete_smtp_credentials"),
        ({"SMTP_SSL": "true", "SMTP_STARTTLS": "true"}, "conflicting_smtp_tls_modes"),
        (
            {"SMTP_STARTTLS": "false", "SMTP_USERNAME": "user", "SMTP_PASSWORD": "secret"},
            "smtp_credentials_require_tls",
        ),
        ({"SMTP_PORT": "bad"}, "invalid_smtp_configuration"),
        ({"SMTP_PORT": "0"}, "invalid_smtp_configuration"),
        ({"SMTP_TIMEOUT_SECONDS": "999"}, "invalid_smtp_configuration"),
        ({"SMTP_STARTTLS": "typo"}, "invalid_smtp_configuration"),
        (
            {"SMTP_ENVELOPE_FROM": "sender@example.edu\r\nBcc: other@example.edu"},
            "invalid_envelope_sender",
        ),
    ],
)
def test_invalid_configuration_never_connects(relay, monkeypatch, values, error):
    calls, _ = relay
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(transport.SMTPDeliveryUnavailable, match=error):
        transport.check_relay()
    assert calls == []


@pytest.mark.parametrize(
    "failure,error",
    [
        (
            smtplib.SMTPNotSupportedError("private server detail"),
            "smtp_required_capability_unavailable",
        ),
        (ssl.SSLError("private certificate detail"), "smtp_tls_failed"),
        (
            smtplib.SMTPAuthenticationError(535, b"private login detail"),
            "smtp_authentication_failed",
        ),
    ],
)
def test_tls_and_auth_failures_do_not_send_or_leak_details(relay, monkeypatch, failure, error):
    calls, smtp_class = relay

    def fail(self, **options):
        raise failure

    monkeypatch.setattr(smtp_class, "starttls", fail)
    with pytest.raises(transport.SMTPDeliveryUnavailable) as caught:
        transport.send_smtp_message(message())
    assert str(caught.value) == error
    assert not any(call[0] == "send" for call in calls)


def test_partial_recipient_refusal_is_not_reported_as_success(relay):
    calls, smtp_class = relay
    smtp_class.refused = {"private@example.edu": (550, b"private detail")}
    with pytest.raises(transport.SMTPDeliveryUnavailable, match="smtp_partial_recipient_refusal"):
        transport.send_smtp_message(message())
    assert sum(call[0] == "send" for call in calls) == 1


@pytest.mark.parametrize("value", ["one@example.edu,two@example.edu", "", "not-an-address"])
def test_sender_is_exactly_one_mailbox(value):
    with pytest.raises(transport.SMTPDeliveryUnavailable, match="invalid_envelope_sender"):
        transport.mailbox(value)
