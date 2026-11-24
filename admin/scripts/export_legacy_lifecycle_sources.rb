# frozen_string_literal: true

# DEC-009 read-only GeoBlacklight Admin source export.
#
# Run through the approved production Rails environment:
#
#   RAILS_ENV=production bundle exec rails runner scripts/export_legacy_lifecycle_sources.rb
#
# The script emits one JSON document to stdout. It contains only the legacy
# fields needed to reconcile Website and harvest-record identities. Keep the
# output in the authorized operations repository; do not commit it here.

require "json"

connection = ActiveRecord::Base.connection
transaction_started = false

begin
  # Enforce read-only behavior at both the connection and transaction levels.
  connection.execute("SET default_transaction_read_only = on")
  connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
  transaction_started = true
  connection.execute("SET LOCAL statement_timeout = '120s'")
  connection.execute("SET LOCAL lock_timeout = '5s'")

  metadata = connection.exec_query(<<~SQL).first
    SELECT
      current_database() AS database_name,
      current_timestamp AS captured_at,
      current_setting('server_version') AS server_version,
      current_setting('transaction_isolation') AS transaction_isolation,
      current_setting('transaction_read_only') AS transaction_read_only
  SQL

  records = connection.exec_query(<<~SQL).to_a
    SELECT
      CASE
        WHEN publication_state = 'published' THEN 'website'
        ELSE 'harvest_record'
      END AS legacy_record_kind,
      id::text AS legacy_uuid,
      friendlier_id AS legacy_record_id,
      title,
      publication_state,
      created_at,
      updated_at,
      json_attributes -> 'gbl_resourceClass_sm' AS resource_class,
      json_attributes -> 'schema_provider_s' AS provider,
      json_attributes -> 'b1g_code_s' AS legacy_code,
      json_attributes -> 'dct_identifier_sm' AS legacy_identifier,
      json_attributes -> 'b1g_dcat_endpointURL_s' AS endpoint_url,
      json_attributes -> 'b1g_dcat_endpointDescription_s' AS endpoint_description,
      json_attributes -> 'b1g_websitePlatform_s' AS website_platform,
      json_attributes -> 'b1g_harvestWorkflow_s' AS harvest_workflow,
      json_attributes -> 'b1g_dct_accrualMethod_s' AS accrual_method,
      json_attributes -> 'b1g_dct_accrualPeriodicity_s' AS accrual_periodicity,
      json_attributes -> 'b1g_isHarvested_b' AS is_harvested,
      json_attributes -> 'b1g_lastHarvested_dt' AS last_harvested,
      json_attributes -> 'b1g_adminTags_sm' AS admin_tags,
      json_attributes -> 'b1g_adminNote_sm' AS admin_notes,
      json_attributes -> 'pcdm_memberOf_sm' AS member_of,
      json_attributes -> 'dct_isPartOf_sm' AS is_part_of,
      json_attributes -> 'b1g_localCollectionLabel_sm' AS local_collection,
      json_attributes -> 'dct_source_sm' AS source,
      json_attributes -> 'dct_relation_sm' AS relation
    FROM kithe_models
    WHERE type = 'Document'
      AND (
        (
          publication_state = 'draft'
          AND COALESCE(json_attributes -> 'gbl_resourceClass_sm', '[]'::jsonb)
              @> '["Series"]'::jsonb
        )
        OR
        (
          publication_state = 'published'
          AND COALESCE(json_attributes -> 'gbl_resourceClass_sm', '[]'::jsonb)
              @> '["Websites"]'::jsonb
        )
      )
    ORDER BY legacy_record_kind, legacy_record_id, legacy_uuid
  SQL

  json_fields = %w[
    resource_class
    provider
    legacy_code
    legacy_identifier
    endpoint_url
    endpoint_description
    website_platform
    harvest_workflow
    accrual_method
    accrual_periodicity
    is_harvested
    last_harvested
    admin_tags
    admin_notes
    member_of
    is_part_of
    local_collection
    source
    relation
  ]
  records.each do |record|
    json_fields.each do |field|
      value = record[field]
      record[field] = JSON.parse(value) if value.is_a?(String)
    end
  end

  counts = records.group_by { |record| record.fetch("legacy_record_kind") }
                  .transform_values(&:length)

  STDOUT.write(
    JSON.pretty_generate(
      "audit_metadata" => metadata,
      "record_counts" => counts,
      "records" => records
    )
  )
  STDOUT.write("\n")
ensure
  connection.execute("ROLLBACK") if transaction_started
end
