# Slackbot

The BTAA Geoportal Slackbot exposes a Slack slash-command endpoint backed by the
existing API search service.

## Endpoint

Configure the Slack slash command request URL as:

```text
https://<host>/api/v1/slack/commands
```

The API also exposes a small local status endpoint:

```text
GET /api/v1/slack
```

## Environment

- `SLACK_SIGNING_SECRET`
  Required. Used to verify Slack's `X-Slack-Signature` header.
- `SLACK_BOT_COMMAND`
  Optional. Command name shown in help text. Defaults to `/btaa`.
- `GEOPORTAL_BASE_URL`
  Optional. Base URL used when building resource and search links. Falls back to
  `APPLICATION_URL`, `BTAA_GEOSPATIAL_API_BASE_URL`, then
  `https://geoportal.btaa.org`.

For Kamal deployments, add `SLACK_SIGNING_SECRET` under `env.secret` in the
destination config before enabling the Slack app, then set it in that
destination's secrets file. Production currently does this in
`config/deploy.prd.yml`; dev destinations leave Slack unconfigured.

## Commands

The command parser is intentionally compact:

```text
/btaa
/btaa help
/btaa search minnesota lakes
/btaa sanborn maps
```

Bare text is treated as a search query. Responses are ephemeral by default and
include the first five matching resources plus a button to open the full search.

## Local Testing

With the API running and `SLACK_SIGNING_SECRET` set, POST a signed
`application/x-www-form-urlencoded` Slack payload to `/api/v1/slack/commands`.
Unsigned requests are rejected with `401`; if the signing secret is missing, the
endpoint returns `503`.
