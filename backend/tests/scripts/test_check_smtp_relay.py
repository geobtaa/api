from unittest.mock import Mock

import pytest

from scripts import check_smtp_relay as cli


def test_default_command_cannot_send(monkeypatch, capsys):
    send = Mock()
    check = Mock(return_value={"message_sent": False, "external_relay_verified": False})
    monkeypatch.setattr(cli, "check_relay", check)
    monkeypatch.setattr(cli, "send_smtp_message", send)
    assert cli.main([]) == 0
    check.assert_called_once()
    send.assert_not_called()
    assert '"message_sent": false' in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--send"], ["--to", "test@example.edu"]])
def test_send_requires_explicit_recipient_and_flag(monkeypatch, args):
    send = Mock()
    monkeypatch.setattr(cli, "send_smtp_message", send)
    with pytest.raises(SystemExit):
        cli.main(args)
    send.assert_not_called()


def test_test_send_uses_only_explicit_recipient(monkeypatch, capsys):
    send = Mock(return_value={"relay_accepted": True, "recipient_delivery_confirmed": False})
    monkeypatch.setattr(cli, "send_smtp_message", send)
    assert (
        cli.main(
            ["--send", "--to", "colleague@campus.example", "--from-address", "team@example.edu"]
        )
        == 0
    )
    email = send.call_args.args[0]
    assert str(email["To"]) == "colleague@campus.example"
    assert email["Message-ID"]
    assert "recipient_delivery_confirmed" in capsys.readouterr().out


def test_check_failure_has_nonzero_exit(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "check_relay", Mock(side_effect=cli.SMTPDeliveryUnavailable("smtp_tls_failed"))
    )
    assert cli.main([]) == 1
    assert "smtp_tls_failed" in capsys.readouterr().out
