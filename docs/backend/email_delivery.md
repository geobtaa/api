# Application email delivery

Feedback and bridge reports share the SMTP transport in
`app/services/smtp_transport.py`. Invitation email can reuse the feedback service's
`deliver_email` entry point. The transport supports verified STARTTLS, implicit
TLS, and registered-IP relays without account authentication. Credentials must be
complete and cannot be sent over an unencrypted connection.

The SMTP envelope sender controls the bounce address and may differ from visible
`From` and `Reply-To` headers. Set `SMTP_ENVELOPE_FROM` when the relay requires a
specific envelope sender. This setting applies to the direct SMTP transport;
sendmail-compatible delivery continues to use the configured sendmail transport.

A successful send means the relay accepted the message. It does not prove inbox
delivery, sender authentication alignment, or authorization to relay externally.
Partial recipient refusals are errors and are not automatically retried, because
some recipients may already have received the message.

## Local checks

Configure a local test SMTP server in the developer environment using `SMTP_HOST`,
`SMTP_PORT`, and the appropriate TLS settings. Real credentials must never be
committed. `SMTP_SSL` and `SMTP_STARTTLS` cannot both be enabled. Timeouts must be
between one and 120 seconds. `SMTP_USERNAME` and `SMTP_PASSWORD` must either both
be set or both be absent.

```bash
# Connection, EHLO, TLS, optional login, and NOOP only; no message is sent.
make smtp-check

# Send a synthetic message only to an explicitly designated test recipient.
make smtp-check SMTP_ARGS='--send --to recipient@example.edu --from-address sender@example.edu --label local'

# Fully mocked SMTP tests; no database or email service required.
make test-smtp
```

The diagnostic never uses the application's normal recipient list. It returns a
message ID for an explicit test send and distinguishes relay acceptance from
confirmed recipient delivery. Errors report stable codes rather than server
responses, credentials, or message contents.

## Deployed relay registration

Provider registration, permitted sender addresses, source network identities,
server configuration, delivery-verification evidence, and cutover procedures are
restricted operations material. Maintainers must update those records alongside
any relay rollout. This public page documents only the application interface and
local workflows; see [deployment documentation](../deploying.md).
