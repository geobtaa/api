# Public Source reads

Sources are independent originating-environment groupings maintained in GEOMG.
They are separate from Lifecycle administration and Aardvark Resource documents.
The API reads GEOMG's version-one public projection directly; it does not import
Source records or cache their responses.

| GET endpoint | Result |
| --- | --- |
| `/api/v1/sources` | Source cards, including Sources with no eligible Resources. Optional `q` searches Source title/ID. |
| `/api/v1/sources/{source_id}` | One Source's public fields and eligible Resource count. |
| `/api/v1/sources/{source_id}/resources` | Public Resource ID/title references belonging to that Source. |

Lists accept `offset` (0–1,000,000, default 0) and `limit` (1–500, default 100).
Source search accepts up to 200 characters. IDs are case-sensitive. Responses
include `schema_version: "1"`; pages include `total`, `offset`, and `limit`.
The checked-in consumer fixture is
[`source-projection-v1.example.json`](../../backend/tests/fixtures/source-projection-v1.example.json),
copied from GEOMG's version-one contract in PR #40.

A Source exposes only `source_id`, `title`, `description`, `landing_page`, and
`resource_count`. Resource references expose only `id` and `title`. Counts and
references use GEOMG's published-and-not-suppressed predicate. Restricted data
may still have public catalog metadata. References do not attest that a Resource
has been delivered to this API, and are not hydrated through local Resource
endpoints. Each page reflects one upstream request; multiple pages can change
as GEOMG is edited.

The server owns the upstream authentication context. Public caller credentials
are never forwarded. The adapter requires GEOMG's separate Source projection
read grant; administrative notes and permissions are not part of the contract.
Credential provisioning is outside this code increment.

Responses use `Cache-Control: no-store`. Missing Sources return 404; unavailable
server configuration returns 503; upstream timeouts return 504; upstream denial,
redirects, unsupported versions, malformed responses, and inconsistent pagination
return 502. Failures never become successful empty pages. Error messages omit
upstream response bodies and credentials. Requests have a ten-second overall
deadline and a 32 MiB response limit. A subsequent request retries against current
GEOMG state; no stale fallback is served.

Tests in `backend/tests/source_adapter` use an in-process API and mock upstream
transport, covering the contract, authentication boundary, edits, visibility and
membership changes, pagination, validation, failures, and recovery.
