-- DEC-009 read-only data-api Resource/Distribution count export.
--
-- Run only through approved read-only production access. Store the JSON output
-- in the authorized operations repository; do not commit it here. The export
-- contains aggregate counts by legacy source code/provider and no Resource
-- contents.

\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '5s';

WITH distribution_counts AS (
    SELECT resource_id, count(*) AS distribution_count
    FROM resource_distributions
    GROUP BY resource_id
), grouped_counts AS (
    SELECT
        COALESCE(NULLIF(btrim(resource.b1g_code_s), ''), '<blank>') AS legacy_code,
        COALESCE(NULLIF(btrim(resource.schema_provider_s), ''), '<blank>') AS provider,
        count(*) AS resource_count,
        count(*) FILTER (WHERE resource.publication_state = 'draft') AS draft_count,
        count(*) FILTER (WHERE resource.publication_state = 'published') AS published_count,
        count(*) FILTER (WHERE resource.publication_state = 'unpublished') AS unpublished_count,
        count(*) FILTER (WHERE resource.publication_state = 'retired') AS retired_count,
        count(*) FILTER (WHERE resource.gbl_suppressed_b IS TRUE) AS suppressed_count,
        COALESCE(sum(distribution_counts.distribution_count), 0) AS distribution_count
    FROM resources resource
    LEFT JOIN distribution_counts ON distribution_counts.resource_id = resource.id
    GROUP BY legacy_code, provider
    ORDER BY legacy_code, provider
)
SELECT jsonb_pretty(
    jsonb_build_object(
        'audit_metadata', jsonb_build_object(
            'captured_at', current_timestamp,
            'server_version', current_setting('server_version'),
            'transaction_isolation', current_setting('transaction_isolation'),
            'transaction_read_only', current_setting('transaction_read_only')
        ),
        'counts', COALESCE(jsonb_agg(to_jsonb(grouped_counts)), '[]'::jsonb)
    )
)
FROM grouped_counts;

ROLLBACK;
