# Runtime analytics reporting

The runtime reporting implementation is in shadow validation. The checked-in
July/August dashboard remains the default until historical reconciliation,
report parity, and deployed preservation checks pass. PR #343 must remain unmerged
until the gates in [the reporting audit](analytics-merge-readiness.md) are closed.

## Contract and data flow

Accepted raw inserts transactionally create reporting outbox entries. The consumer
updates daily dimension aggregates and mergeable visit sketches, retains processing
receipts, and clears temporary payloads. Counts are preserved before ranking limits
are applied. The archive validator reconciles each dimension against its receipts.

Report schema version 1 has UTC start/inclusive and end/exclusive bounds, calculation
and disclosure versions, coverage, a content-derived revision, source explanations,
and report tables. Queries use saved constraints when available, falling back to URL
controls. Facet counts deduplicate categories within each search. Recorded zero-result
flags and original result-total distributions remain separate evidence.

`all` means since July 1, 2026. `ay-2026` means July 2026 through June 2027, restricted
to completed months. Monthly reports use `YYYY-MM`. Dates, defaults and available
periods come from the manifest, not imports or frontend date constants. Tracked visits
are HLL estimates of tab-scoped tokens, not unique people. Their standard relative
error is about 0.81%. Unsupported historical audience coverage is unavailable.

Catalog metadata is captured once per reporting month and its actual capture date
is preserved. It must not be presented as month-end metadata unless captured then.
Code and Provider attribution are different dimensions. Unknown contribution codes
remain explicit; never infer a university from geography. Four-digit federal codes are not interpreted as two-digit university codes.
Curated, OpenGeoMetadata, licensed and other code groups remain visible. Any future
multi-valued Provider representation must use an explicit mapping and disclose overlaps.

Public query output applies a repeated-context threshold and sensitive-text rules.
Suppressed searches remain in totals. Automated text screening is not a guarantee
that all personal information is detected. Neither raw tokens nor arbitrary URL
parameters are part of public artifacts. CSV downloads neutralize formula prefixes.

## Public read interfaces

- `GET /api/v1/analytics/reports/manifest`: available period revisions and latest
  complete month; revalidated rather than permanently cached.
- `GET /api/v1/analytics/reports/{period}/{revision}`: immutable public report JSON.
- `GET /api/v1/analytics/reports/{period}/{revision}/download/{table}?format=csv|json`:
  approved table downloads from that exact revision.

The API returns 503 while runtime reporting is in shadow mode. Unknown periods or
revisions return 404. The preview route `/analytics?runtime=1` selects the runtime
renderer; it does not bypass the API's publication gate. The original renderer and
saved snapshots remain available during migration.

## Local development

Use only an isolated local database for lifecycle experiments. Install the raw
analytics schema first. `backend/scripts/manage_analytics_reporting.py --help`
describes installation, bounded historical backfill, baseline verification,
publication, legacy snapshot import, health inspection, and clean-period restore.
Historical backfill does not automatically certify completeness. Independent expected
counts cover all four sources, with null explicitly meaning unavailable. Source
coverage determines which metrics can be reported; missing raw API distributions do
not erase independently preserved additive monthly totals. The legacy baseline fixture
retains original July/August request totals and daily counts.

`manage_analytics_storage.py` runs preservation/publication before retention in its
maintenance mode. Missing preservation dependencies cause a failed run. The separate
retention guard also refuses deletion without verified reporting evidence.

Tests in `test_reporting_contract.py`, `test_reporting_storage.py` and
`test_reporting_publication.py` cover calendar boundaries, privacy, sketches,
transactional rollback, duplicate capture, concurrent expiry, revisions, archive
corruption, clean-period restore, next-day publication and preservation of the previous manifest on failure.
The PostgreSQL tests use isolated schemas and require `ANALYTICS_TEST_DATABASE_URL`;
CI must configure it rather than skip these tests.

## Remaining release verification

- Reconcile full historical source evidence with every existing report, including
  outcomes, client inference and all member-detail presentations.
- Complete production-sized backfill and UI parity checks, including all original
  member-detail presentations and historical impression attribution.
- Verify deployed archival storage, independent recovery, scheduler timing, actionable
  notification delivery and the isolated restore drill on deployed infrastructure before enabling cutover.
  Local preservation now requires a successful restore into a disposable database schema.

Deployment configuration, storage policy, alerts and recovery procedures belong in
restricted operations documentation. The maintainer must update those runbooks as
part of rollout; public docs intentionally contain no deployed locations or credentials.

## Historical inventory checked during implementation

A read-only source inventory on September 11, 2026 confirmed July searches (6,457)
and events (16,824), and all four August sources against the saved baselines. July
raw API logs and raw impressions were no longer present. Original published files
remain unchanged. The approved read-only July/August exports have now been saved privately and
validated against their processing receipts. July's existing daily resource-impression
rollups reconcile to all 99,482 saved impressions. Search, event, view, download,
source-click, zero-result, request and impression totals match the saved baselines;
monthly p95 values also match. July retains its saved API totals without claiming
that the expired API distributions can be reconstructed.

The visit estimates differ from the original exact tracked-visit baselines by 0.14%
for July, 0.24% for August, and 0.52% for the combined period. These are sketch
estimates, not counts of people. All 17 original snapshot files were also preserved
byte-for-byte in the private migration workspace. Deployed independent archive
verification remains outstanding; local copies do not satisfy that release gate.
The runtime cutover remains disabled.

## Calculation revision 2

The runtime generator normalizes legacy daily request labels into UTC calendar
dates and verifies their sum against the saved monthly total. Original archive
bytes remain unchanged. July's daily API chart therefore reconciles with its
613,131-request total, rather than showing missing days behind a correct total.

Daily tracked visits use each day's preserved sketch; period visits union sketches
and never sum daily estimates. Download and source-click rankings are independent
of view rankings, with full rankings available through versioned downloads.
Download characteristics use sealed catalog values and disclose overlapping
categories. Provider arrays use deduplicated memberships and explicitly overlap;
unmapped resource activity remains visible. Incomplete client request coverage is
unavailable, not a recorded zero. Public zero-result context shows allowlisted
parameters, original result totals, and repeat-search links.

The publication shortcut checks both calculation and disclosure versions. A new
calculation version regenerates reports even when no source records changed,
creating new public revisions while retaining the previous artifacts. This does
not silently modify the archived reporting inputs.

Daily maintenance also rotates through archive revisions whose last restore check
is at least seven days old, verifying one oldest revision per run. Both independent
copies must pass checksum validation and an isolated database restore. This audit
runs even when publication has no changes. A failed check records an actionable
health transition and leaves the previous publication intact; successful recovery
clears the failure. Larger histories take correspondingly longer to complete a
rotation, which must be included in operational monitoring.

Archive authentication can use an explicitly selected profile or an explicitly
supplied project credential pair, including a session token when required. Mixing
both sources, providing an incomplete pair, or omitting a credential source fails
closed. The adapter never chooses an ambient local profile. Reusing project
credentials does not bypass bucket privacy/versioning checks or the independent
recovery ownership check. Deployed credential wiring remains restricted material.

## Public downloads and internal preservation

Public delivery includes versioned report JSON and complete CSV/JSON tables for
monthly, academic-year, and cumulative periods. These are the aggregate reports
exposed by the dashboard, with the query-publication policy applied. A delivery
manifest is published only after all referenced files have passed readback
verification. Public download access can be checked independently of authenticated
storage access.

Internal preservation archives additionally contain low-frequency query/context
dimensions, processing receipts, source-record identities, and mergeable visit
sketches. They are not part of public table downloads. Publishing aggregate files
through an existing delivery bucket does not certify the durability of these
internal archives or authorize raw-data expiration. Those preservation checks
remain separate release gates.

Deployment destinations, credentials, and upload procedures belong in restricted
operations documentation; they are intentionally absent from this public guide.
