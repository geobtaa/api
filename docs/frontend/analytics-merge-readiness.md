# Analytics reporting: pre-merge audit

Reviewed against PR #343, September 10, 2026. **Not ready to merge as an
automatic, sustainable monthly reporting system.** The existing July/August
reports are useful static deliverables, but they are not that system yet.

## Findings

### P1: New months do not publish automatically

`analyticsReports.ts` accepts only July and August 2026. The page imports separate
month-specific modules, assumes 31 days, and uses hard-coded dates and selectors.
The exporters likewise embed 2026 dates and known July/August totals. A September
file alone cannot extend the dashboard. Daily storage maintenance does not run
these exporters, publish snapshots, rebuild the application or advance a manifest.

**Merge gate:** one versioned report schema; parameterized month/date ranges;
a manifest driving available periods and latest complete default; every report
consuming the same period contract. Test September, February, leap-year February,
December/January, and the July academic-year rollover without editing components.

### P1: All time cannot be regenerated once raw history expires

`export_published_analytics_2026.py`, the Provider exporter and the outcomes
exporter still read raw searches/events. Their baseline checks appropriately
reject incomplete history, but cannot recreate it. Checked-in monthly top-50/100
lists are insufficient to calculate later academic-year rankings. Distinct visit
counts cannot be summed across months; July plus August already demonstrates this.

**Merge gate:** durable full query/facet/context counts and resource/event counts,
not only top-N lists. Define cross-period distinct-visit support explicitly: a
mergeable approximate sketch with an honest label, or unavailable when exact
source evidence no longer exists. Do not silently sum distinct counts or retain
visitor identifiers indefinitely to evade this design decision. Replay publication
from preserved inputs after removing raw partitions in an isolated test database.

### P1: Checkpoints do not protect all late-arriving data

`_rollup_job_window` starts after its checkpoint. Only impression expiry takes a
final partition lock, rerolls and reconciles immediately before deletion. Late
searches, events or API logs can fall behind other checkpoints and be deleted
without appearing in their old daily aggregates. This is an existing maintenance
limitation on which the new reporting system depends.

**Merge gate:** bounded replay/correction policy plus final reconciliation for all
retained reporting dimensions before expiry. Preserve impression aggregates when
refreshing searches whose raw impressions have already expired. Refuse unsafe
expiry, expose the blocked condition, and test late inserts and retry behavior.

### P1: Green CI had not exercised the retention integration tests

The PostgreSQL retention fixture skipped tests when `ANALYTICS_TEST_DATABASE_URL`
was absent; the CI job did not set it. Local integration tests had been run, but
that did not provide continuing CI protection.

**Addressed in this review:** configure CI's existing isolated test database,
fail instead of skip when CI lacks that configuration, and freeze the retention
test clock so the fixed July fixtures have a deterministic expiry date. The seven
retention/recovery tests pass against isolated local PostgreSQL.

### P2: Rerunning an export does not reproduce its historical catalog

Provider/code attribution, eligibility, titles and inventory come from the
current `resources` table. Identical event history can produce different results
after catalog edits or suppression/deletion. Export timestamps disclose this but
do not preserve the original join inputs. Independent exporters can also use
different catalog states.

**Merge gate:** immutable, versioned aggregate snapshots with schema/exporter
version, exact bounds, catalog attribution version, reconciliation results and
checksums. Historical reads use sealed snapshots. Corrections create explicit
revisions; a later catalog must not silently overwrite a published report.

### P2: Publication has no completeness/freshness workflow

The UI's latest month is hard-coded; there is no reporting manifest, publication
state machine, overdue-report indicator or scheduler retry/backfill contract.
Existing exporters use known historical constants, not a generic month-completion
check. Seeing a successful maintenance task is not proof that all report panels
are complete or published.

**Merge gate:** scheduled closed-month generation after a defined grace period;
idempotent retries; validation across every panel; atomic publication of a
complete manifest; retained previous versions on failure; visible reporting
through-date and overdue/failure notification. Public query/context output needs
an explicit publication policy because query text can contain user-entered names
and addresses even when visitor IDs and unknown URL parameters are removed.

## What survives expiration today?

| Evidence | Preserved? | Limitation |
| --- | --- | --- |
| Checked-in July/August report JSON/TypeScript | Yes, in Git history | Only the exported fields and ranked subsets; not a complete recomputation source |
| Daily resource impression counts | Yes, independent durable table | No query, visit, client or search-context attribution in this table |
| API daily counts and averages | Yes, daily rollups | Raw user agents and exact response-time distributions/percentiles are lost |
| Search daily totals | Yes, daily rollups | Query terms and saved facet/context combinations are not retained there |
| Resource-scoped event totals | Yes, daily rollups | Events without resource IDs, visitor identity and some event details are excluded |
| Complete search terms and failed-query context | Only current raw history plus exported subsets | Raw searches default to 90-day retention |
| Exact cross-month tracked visits | Only current raw history and already exported period totals | Raw searches/events default to 90 days; period distinct counts are not additive |
| Historical catalog attribution | Only fields already exported | Rejoining current metadata changes historical results |

Raw API logs and impressions default to 30 days; searches/events to 90 days.
Expiry drops entire monthly partitions, not individual rows exactly at that age.
Under those defaults, August API/impression partitions become eligible October 1;
July searches/events October 30; August searches/events November 30, 2026.
These dates assume completed checkpoints and default settings, not a verification
of deployed environment overrides or backup coverage. Saved Git snapshots do not
expire on these dates. Database backups are not a substitute for tested reporting
archives; deployed backup/restore procedures belong in restricted operations docs.

## Maintenance after the merge gates are implemented

Routine monthly work should be reviewing an automated completeness/privacy report,
not editing dates or writing SQL. A successful run should collect, reconcile, seal
and atomically publish the next period; retries must not duplicate or replace
history. Data capture must continue independently if publication is delayed.

Ongoing ownership remains necessary for failed/late ingestion, intentional
historical corrections, schema/event changes, query-category improvements,
privacy review, archive growth monitoring and periodic restore drills. Catalog
attribution policy and supported client definitions must be versioned. A July
rollover should start a new academic year while leaving past years addressable.

## Required end-to-end acceptance test

1. Generate two complete fixture months and their academic-year report.
2. Generate a third month without changing frontend code or exporter constants.
3. Interrupt generation; retry it; prove no partial publication or duplicates.
4. Insert late activity; verify correction/finalization behavior is explicit.
5. Expire raw tables and rebuild the same supported reports from durable inputs.
6. Change current catalog metadata and prove sealed historical reports stay fixed.
7. Verify non-additive metrics remain correct or explicitly unavailable.
8. Verify the actual CI job runs the storage tests and that publication failures
   retain the previous complete manifest and expose an actionable status.

Passing the current UI suite is necessary, but does not satisfy these gates.
