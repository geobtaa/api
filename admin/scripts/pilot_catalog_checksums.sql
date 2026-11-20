-- psql: supply pilot_ids as a JSON array of the reviewed public IDs.
-- Emits only aggregate counts and SHA-256 digests of the canonical catalog rows.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '90s';
WITH ids AS (SELECT jsonb_array_elements_text(:'pilot_ids'::jsonb) AS id),
pilot AS (SELECT r.* FROM resources r JOIN ids USING (id)),
dictionaries AS (SELECT d.* FROM resource_data_dictionaries d JOIN ids ON d.resource_id=ids.id),
rows_to_check(family,row_data) AS (
 SELECT 'resources', to_jsonb(p) - ARRAY['created_at','updated_at','created_by_actor_id','lock_version','legacy_source_id','lifecycle_id','set_id'] FROM pilot p
 UNION ALL SELECT 'distributions', to_jsonb(d) FROM resource_distributions d JOIN ids ON d.resource_id=ids.id
 UNION ALL SELECT 'distribution_types', to_jsonb(t) FROM distribution_types t
 UNION ALL SELECT 'relationships', to_jsonb(r) FROM resource_relationships r WHERE r.subject_id IN (SELECT id FROM ids) OR r.object_id IN (SELECT id FROM ids)
 UNION ALL SELECT 'assets', to_jsonb(a) FROM resource_assets a JOIN ids ON a.resource_id=ids.id
 UNION ALL SELECT 'downloads', to_jsonb(d) FROM resource_downloads d JOIN ids ON d.resource_id=ids.id
 UNION ALL SELECT 'licensed_accesses', to_jsonb(a) FROM resource_licensed_accesses a JOIN ids ON a.resource_id=ids.id
 UNION ALL SELECT 'dictionaries', to_jsonb(d) FROM dictionaries d
 UNION ALL SELECT 'dictionary_entries', to_jsonb(e) FROM resource_data_dictionary_entries e JOIN dictionaries d ON d.id=e.resource_data_dictionary_id
), digests AS (
 SELECT family, encode(sha256(convert_to(row_data::text,'UTF8')),'hex') AS digest FROM rows_to_check
)
SELECT family, count(*), encode(sha256(convert_to(string_agg(digest,'' ORDER BY digest),'UTF8')),'hex')
FROM digests GROUP BY family ORDER BY family;
COMMIT;
