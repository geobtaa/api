-- psql -XqAt -v ON_ERROR_STOP=1 -f scripts/export_alpha_scope.sql > reviewed-scope.json
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT json_build_object(
  'sources',(SELECT json_agg(json_build_array(source_id,title) ORDER BY source_id) FROM sources),
  'sets',(SELECT json_agg(json_build_array(set_id,source_id,title,status) ORDER BY set_id) FROM sets),
  'members',(SELECT json_agg(json_build_array(resource_id,set_id,target_source_id) ORDER BY resource_id)
             FROM resource_set_cutovers));
COMMIT;
