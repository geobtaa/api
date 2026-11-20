-- DEC-005 read-only data-api contract audit.
--
-- Run this file only through approved read-only production access. Store its
-- output in the authorized operations repository; do not commit output here.
-- The transaction is explicitly read-only and emits catalog metadata,
-- controlled vocabulary, and aggregate counts rather than Resource contents.

\set ON_ERROR_STOP on
\pset format unaligned
\pset fieldsep '|'
\pset null '<NULL>'

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '5s';

\echo audit_metadata
SELECT
    current_setting('server_version') AS server_version,
    current_setting('transaction_isolation') AS transaction_isolation,
    current_setting('transaction_read_only') AS transaction_read_only
;

\echo columns
SELECT
    table_name,
    ordinal_position,
    column_name,
    data_type,
    udt_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
      'resources',
      'distribution_types',
      'resource_distributions',
      'resource_relationships',
      'resource_downloads',
      'resource_licensed_accesses',
      'resource_assets',
      'resource_data_dictionaries',
      'resource_data_dictionary_entries'
  )
ORDER BY table_name, ordinal_position;

\echo constraints
SELECT
    conrelid::regclass::text AS table_name,
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid, true) AS definition
FROM pg_constraint
WHERE conrelid IN (
    'resources'::regclass,
    'distribution_types'::regclass,
    'resource_distributions'::regclass,
    'resource_relationships'::regclass,
    'resource_downloads'::regclass,
    'resource_licensed_accesses'::regclass,
    'resource_assets'::regclass,
    'resource_data_dictionaries'::regclass,
    'resource_data_dictionary_entries'::regclass
)
ORDER BY table_name, constraint_type, constraint_name;

\echo indexes
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
      'resources',
      'distribution_types',
      'resource_distributions',
      'resource_relationships',
      'resource_downloads',
      'resource_licensed_accesses',
      'resource_assets',
      'resource_data_dictionaries',
      'resource_data_dictionary_entries'
  )
ORDER BY tablename, indexname;

\echo triggers
SELECT event_object_table, trigger_name, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_schema = 'public'
  AND event_object_table IN (
      'resources',
      'distribution_types',
      'resource_distributions',
      'resource_relationships',
      'resource_downloads',
      'resource_licensed_accesses',
      'resource_assets',
      'resource_data_dictionaries',
      'resource_data_dictionary_entries'
  )
ORDER BY event_object_table, trigger_name, event_manipulation;

\echo row_counts
SELECT 'resources' AS table_name, count(*) AS row_count FROM resources
UNION ALL SELECT 'distribution_types', count(*) FROM distribution_types
UNION ALL SELECT 'resource_distributions', count(*) FROM resource_distributions
UNION ALL SELECT 'resource_relationships', count(*) FROM resource_relationships
UNION ALL SELECT 'resource_downloads', count(*) FROM resource_downloads
UNION ALL SELECT 'resource_licensed_accesses', count(*) FROM resource_licensed_accesses
UNION ALL SELECT 'resource_assets', count(*) FROM resource_assets
UNION ALL SELECT 'resource_data_dictionaries', count(*) FROM resource_data_dictionaries
UNION ALL SELECT 'resource_data_dictionary_entries', count(*) FROM resource_data_dictionary_entries
ORDER BY table_name;

\echo publication_state_pairs
SELECT
    publication_state,
    "b1g_publication_state_s",
    gbl_suppressed_b,
    count(*) AS row_count
FROM resources
GROUP BY publication_state, "b1g_publication_state_s", gbl_suppressed_b
ORDER BY publication_state, "b1g_publication_state_s", gbl_suppressed_b;

\echo identifier_coverage
SELECT
    count(*) AS resource_count,
    count(geomg_id_s) AS geomg_id_nonnull,
    count(DISTINCT geomg_id_s) AS geomg_id_distinct,
    count(import_id) AS import_id_nonnull,
    count(DISTINCT import_id) AS import_id_distinct
FROM resources;

\echo distribution_vocabulary
SELECT
    id,
    name,
    distribution_type,
    distribution_uri,
    label,
    position
FROM distribution_types
ORDER BY position NULLS LAST, id;

\echo legacy_reference_uris
WITH reference_uris AS (
    SELECT jsonb_object_keys(
        CASE
            WHEN dct_references_s IS JSON OBJECT THEN dct_references_s::jsonb
            ELSE '{}'::jsonb
        END
    ) AS distribution_uri
    FROM resources
)
SELECT
    reference_uris.distribution_uri,
    distribution_types.name AS normalized_type_name,
    count(*) AS occurrence_count
FROM reference_uris
LEFT JOIN distribution_types
  ON distribution_types.distribution_uri = reference_uris.distribution_uri
GROUP BY reference_uris.distribution_uri, distribution_types.name
ORDER BY reference_uris.distribution_uri;

\echo orphan_counts
SELECT 'resource_distributions.resource_id' AS relationship, count(*) AS orphan_count
FROM resource_distributions child
LEFT JOIN resources parent ON parent.id = child.resource_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_distributions.distribution_type_id', count(*)
FROM resource_distributions child
LEFT JOIN distribution_types parent ON parent.id = child.distribution_type_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_relationships.subject_id', count(*)
FROM resource_relationships child
LEFT JOIN resources parent ON parent.id = child.subject_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_relationships.object_id', count(*)
FROM resource_relationships child
LEFT JOIN resources parent ON parent.id = child.object_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_downloads.resource_id', count(*)
FROM resource_downloads child
LEFT JOIN resources parent ON parent.id = child.resource_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_licensed_accesses.resource_id', count(*)
FROM resource_licensed_accesses child
LEFT JOIN resources parent ON parent.id = child.resource_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_assets.resource_id', count(*)
FROM resource_assets child
LEFT JOIN resources parent ON parent.id = child.resource_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_data_dictionaries.resource_id', count(*)
FROM resource_data_dictionaries child
LEFT JOIN resources parent ON parent.id = child.resource_id
WHERE parent.id IS NULL
UNION ALL
SELECT 'resource_data_dictionary_entries.resource_data_dictionary_id', count(*)
FROM resource_data_dictionary_entries child
LEFT JOIN resource_data_dictionaries parent
  ON parent.id = child.resource_data_dictionary_id
WHERE parent.id IS NULL
ORDER BY relationship;

\echo duplicate_counts
SELECT 'resource_distributions.resource_type_url' AS identity, count(*) AS duplicate_group_count
FROM (
    SELECT resource_id, distribution_type_id, url
    FROM resource_distributions
    GROUP BY resource_id, distribution_type_id, url
    HAVING count(*) > 1
) duplicate_groups
UNION ALL
SELECT 'resources.id', count(*)
FROM (
    SELECT id
    FROM resources
    GROUP BY id
    HAVING count(*) > 1
) duplicate_groups
ORDER BY identity;

\echo relationship_predicates_and_missing_endpoints
SELECT
    rr.predicate,
    count(*) AS relationship_count,
    count(*) FILTER (WHERE subject.id IS NULL) AS missing_subject_count,
    count(*) FILTER (WHERE object.id IS NULL) AS missing_object_count
FROM resource_relationships rr
LEFT JOIN resources subject ON subject.id = rr.subject_id
LEFT JOIN resources object ON object.id = rr.object_id
GROUP BY rr.predicate
ORDER BY rr.predicate;

COMMIT;
