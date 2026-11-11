#!/usr/bin/env python3
"""Check application SMTP configuration; sending requires --send and an explicit recipient."""

import argparse
import json
import os
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from app.services.smtp_transport import (  # noqa: E402
    SMTPDeliveryUnavailable,
    check_relay,
    mailbox,
    send_smtp_message,
)


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Send one diagnostic message")
    parser.add_argument("--to", help="Explicit consenting test recipient")
    parser.add_argument("--from-address", help="Visible From address (otherwise SMTP_FROM)")
    parser.add_argument("--label", default="local", help="Non-sensitive environment label")
    args = parser.parse_args(argv)
    if args.to and not args.send:
        parser.error("--to requires --send; checks do not send email")
    if args.send and not args.to:
        parser.error("--send requires --to")
    try:
        if not args.send:
            result = check_relay()
        else:
            recipient = mailbox(args.to)
            sender = mailbox(args.from_address or os.getenv("SMTP_FROM", ""))
            if any(c in args.label for c in "\r\n"):
                raise SMTPDeliveryUnavailable("invalid_test_label")
            message = EmailMessage()
            message["From"], message["To"] = sender, recipient
            message["Date"] = formatdate(localtime=False, usegmt=True)
            message["Message-ID"] = make_msgid(domain=sender.split("@", 1)[1])
            message["Subject"] = f"Geoportal SMTP delivery test ({args.label})"
            message.set_content(
                "This is an explicitly requested SMTP delivery test.\n"
                "Please confirm receipt and inspect the delivery/authentication headers.\n"
                "Relay acceptance alone does not confirm inbox delivery.\n"
            )
            result = {**send_smtp_message(message), "message_id": str(message["Message-ID"])}
    except SMTPDeliveryUnavailable as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
