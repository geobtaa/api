from sqlalchemy import (
    ARRAY,
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

metadata = MetaData()

resources = Table(
    "resources",
    metadata,
    Column("id", String, primary_key=True),
    Column("dct_title_s", String),
    Column("dct_alternative_sm", ARRAY(String)),
    Column("dct_description_sm", ARRAY(Text)),
    Column("dct_language_sm", ARRAY(String)),
    Column("gbl_displayNote_sm", ARRAY(Text)),
    Column("dct_creator_sm", ARRAY(String)),
    Column("dct_publisher_sm", ARRAY(String)),
    Column("schema_provider_s", String),
    Column("gbl_resourceClass_sm", ARRAY(String)),
    Column("gbl_resourceType_sm", ARRAY(String)),
    Column("dct_subject_sm", ARRAY(String)),
    Column("dcat_theme_sm", ARRAY(String)),
    Column("dcat_keyword_sm", ARRAY(String)),
    Column("dct_temporal_sm", ARRAY(String)),
    Column("dct_issued_s", String),
    Column("gbl_indexYear_im", ARRAY(Integer)),
    Column("gbl_dateRange_drsim", ARRAY(String)),
    Column("dct_spatial_sm", ARRAY(String)),
    Column("locn_geometry", Text),
    Column("dcat_bbox", String),
    Column("dcat_centroid", String),
    Column("dct_relation_sm", ARRAY(String)),
    Column("pcdm_memberOf_sm", ARRAY(String)),
    Column("dct_isPartOf_sm", ARRAY(String)),
    Column("dct_source_sm", ARRAY(String)),
    Column("dct_isVersionOf_sm", ARRAY(String)),
    Column("dct_replaces_sm", ARRAY(String)),
    Column("dct_isReplacedBy_sm", ARRAY(String)),
    Column("dct_rights_sm", ARRAY(String)),
    Column("dct_rightsHolder_sm", ARRAY(String)),
    Column("dct_license_sm", ARRAY(Text)),
    Column("dct_accessRights_s", String),
    Column("dct_format_s", String),
    Column("gbl_fileSize_s", String),
    Column("gbl_wxsIdentifier_s", String),
    Column("dct_references_s", Text),
    Column("dct_identifier_sm", ARRAY(String)),
    Column("gbl_mdModified_dt", TIMESTAMP),
    Column("gbl_mdVersion_s", String),
    Column("gbl_suppressed_b", Boolean),
    Column("gbl_georeferenced_b", Boolean),
    
    # BTAA-specific fields for OGM Aardvark compliance
    Column("b1g_code_s", String),
    Column("b1g_status_s", String),
    Column("b1g_dct_accrualMethod_s", String),
    Column("b1g_dct_accrualPeriodicity_s", String),
    Column("b1g_dateAccessioned_s", Date),
    Column("b1g_dateRetired_s", Date),
    Column("b1g_child_record_b", Boolean),
    Column("b1g_dct_mediator_sm", ARRAY(String)),
    Column("b1g_access_s", JSON),  # Object with additionalProperties
    Column("b1g_image_ss", String),
    Column("b1g_geonames_sm", ARRAY(String)),
    Column("b1g_publication_state_s", String),
    Column("b1g_language_sm", ARRAY(String)),
    Column("b1g_creatorID_sm", ARRAY(String)),
    Column("b1g_dct_conformsTo_sm", ARRAY(String)),
    Column("b1g_dcat_spatialResolutionInMeters_sm", ARRAY(String)),
    Column("b1g_geodcat_spatialResolutionAsText_sm", ARRAY(String)),
    Column("b1g_dct_provenanceStatement_sm", ARRAY(String)),
    Column("b1g_adminTags_sm", ARRAY(String)),
    # Latest BTAA schema compatibility fields
    Column("b1g_adminNote_sm", ARRAY(String)),
    Column("b1g_dateAccessioned_dt", TIMESTAMP),
    Column("b1g_dateRetired_dt", TIMESTAMP),
    Column("b1g_deprioritized_b", Boolean),
    Column("b1g_harvestWorkflow_s", String),
    Column("b1g_isHarvested_b", Boolean),
    Column("b1g_lastHarvested_dt", TIMESTAMP),
    Column("b1g_dct_provenance_sm", ARRAY(String)),
    Column("b1g_dcat_spatialResolutionInMeters_s", String),
    Column("b1g_websitePlatform_s", String),
    
    # Additional BTAA fields for old database migration
    Column("b1g_adms_supportedSchema_sm", ARRAY(String)),
    Column("b1g_dateAccessioned_sm", ARRAY(String)),  # Note: array version for migration
    Column("b1g_dcat_endpointDescription_s", String),
    Column("b1g_dcat_endpointURL_s", String),
    Column("b1g_dcat_inSeries_sm", ARRAY(String)),
    Column("b1g_localCollectionLabel_sm", ARRAY(String)),
    Column("b1g_prov_softwareAgent_sm", ARRAY(String)),
    Column("b1g_prov_wasGeneratedBy_sm", ARRAY(String)),
    Column("date_created_dtsi", TIMESTAMP),
    Column("date_modified_dtsi", TIMESTAMP),
    Column("geomg_id_s", String),
    Column("publication_state", String),
    Column("import_id", String),
)

resource_relationships = Table(
    "resource_relationships",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("subject_id", String, nullable=False),
    Column("predicate", String, nullable=False),
    Column("object_id", String, nullable=False),
)

# Gazetteer Models

# GeoNames gazetteer
gazetteer_geonames = Table(
    "gazetteer_geonames",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("geonameid", BigInteger, nullable=False, unique=True, index=True),
    Column("name", String, nullable=False),
    Column("asciiname", String, nullable=False),
    Column("alternatenames", Text),
    Column("latitude", Numeric(10, 7), nullable=False),
    Column("longitude", Numeric(10, 7), nullable=False),
    Column("feature_class", String(1)),
    Column("feature_code", String(10)),
    Column("country_code", String(2)),
    Column("cc2", String(200)),
    Column("admin1_code", String(20)),
    Column("admin2_code", String(80)),
    Column("admin3_code", String(20)),
    Column("admin4_code", String(20)),
    Column("population", BigInteger),
    Column("elevation", Integer),
    Column("dem", Integer),
    Column("timezone", String(40)),
    Column("modification_date", Date),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

# Who's on First gazetteer tables
gazetteer_wof_spr = Table(
    "gazetteer_wof_spr",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("wok_id", BigInteger, nullable=False, unique=True, index=True),
    Column("parent_id", BigInteger),
    Column("name", String, nullable=False),
    Column("placetype", String),
    Column("country", String(2)),
    Column("repo", String),
    Column("latitude", Numeric(10, 7)),
    Column("longitude", Numeric(10, 7)),
    Column("min_latitude", Numeric(10, 7)),
    Column("min_longitude", Numeric(10, 7)),
    Column("max_latitude", Numeric(10, 7)),
    Column("max_longitude", Numeric(10, 7)),
    Column("is_current", Integer),
    Column("is_deprecated", Integer),
    Column("is_ceased", Integer),
    Column("is_superseded", Integer),
    Column("is_superseding", Integer),
    Column("superseded_by", Integer),
    Column("supersedes", Integer),
    Column("lastmodified", Integer),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

gazetteer_wof_ancestors = Table(
    "gazetteer_wof_ancestors",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("wok_id", BigInteger, nullable=False, index=True),
    Column("ancestor_id", Integer, nullable=False),
    Column("ancestor_placetype", String),
    Column("lastmodified", Integer),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

gazetteer_wof_concordances = Table(
    "gazetteer_wof_concordances",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("wok_id", BigInteger, nullable=False, index=True),
    Column("other_id", String, nullable=False),
    Column("other_source", String, nullable=False),
    Column("lastmodified", Integer),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

gazetteer_wof_geojson = Table(
    "gazetteer_wof_geojson",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("wok_id", BigInteger, nullable=False, index=True),
    Column("body", Text, nullable=False),
    Column("source", String),
    Column("alt_label", String),
    Column("is_alt", Boolean),
    Column("lastmodified", Integer),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

gazetteer_wof_names = Table(
    "gazetteer_wof_names",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("wok_id", BigInteger, nullable=False, index=True),
    Column("placetype", String),
    Column("country", String(2)),
    Column("language", String),
    Column("extlang", String),
    Column("script", String),
    Column("region", String),
    Column("variant", String),
    Column("extension", String),
    Column("privateuse", String),
    Column("name", String, nullable=False),
    Column("lastmodified", Integer),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

# BTAA gazetteer
gazetteer_btaa = Table(
    "gazetteer_btaa",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("fast_area", String, nullable=False, index=True),
    Column("bounding_box", String),
    Column("geometry", Text),
    Column("geonames_id", String),
    Column("state_abbv", String(2), index=True),
    Column("state_name", String),
    Column("county_fips", String, index=True),
    Column("statefp", String),
    Column("namelsad", String),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

# FAST gazetteer
# Data source: OCLC ResearchWorks (https://researchworks.oclc.org/researchdata/fast/)
# Attribution: OCLC FAST data is provided by OCLC under the OCLC ResearchWorks license.
gazetteer_fast = Table(
    "gazetteer_fast",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("fast_id", String, nullable=False, unique=True, index=True),
    Column("uri", String, nullable=False),
    Column("type", String, nullable=False),
    Column("label", String, nullable=False),
    Column("geoname_id", String),
    Column("viaf_id", String),
    Column("wikipedia_id", String),
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

# FAST gazetteer embeddings
# Stores vector embeddings for FAST gazetteer entries
gazetteer_fast_embeddings = Table(
    "gazetteer_fast_embeddings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("fast_id", String, nullable=False, unique=True, index=True),
    Column("label", String, nullable=False),
    Column("geoname_id", String),
    Column("viaf_id", String),
    Column("wikipedia_id", String),
    Column("embeddings", String, nullable=False),  # Will be cast to vector(1536) in the database
    Column("created_at", TIMESTAMP),
    Column("updated_at", TIMESTAMP),
)

# AI Enrichments table
resource_ai_enrichments = Table(
    "resource_ai_enrichments",
    metadata,
    Column("enrichment_id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String, nullable=False, index=True),
    Column("ai_provider", String, nullable=False),
    Column("model", String, nullable=False),
    Column("enrichment_type", String(50), nullable=False),
    Column("prompt", JSON, nullable=True),
    Column("output_parser", JSON, nullable=True),
    Column("response", JSON, nullable=True),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# Allmaps annotation table
resource_allmaps = Table(
    "resource_allmaps",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String, nullable=False, index=True),
    Column("allmaps_id", String, nullable=True, index=True),
    Column("iiif_manifest_uri", String, nullable=True),
    Column("annotated", Boolean, server_default="false", nullable=False),
    Column("iiif_manifest", Text, nullable=True),
    Column("allmaps_annotation", Text, nullable=True),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# Distribution types lookup table
distribution_types = Table(
    "distribution_types",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("distribution_type", String(255), nullable=False),
    Column("distribution_uri", String(500), nullable=False),
    Column("label", Boolean, server_default="false", nullable=False),
    Column("note", Text, nullable=True),
    Column("position", Integer, server_default="0", nullable=False),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# Resource distributions table
resource_distributions = Table(
    "resource_distributions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String(255), nullable=False, index=True),
    Column("distribution_type_id", Integer, nullable=False),
    Column("url", Text, nullable=False),
    Column("label", String(255), nullable=True),
    Column("position", Integer, server_default="0", nullable=False),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
    Column("import_distribution_id", String(255), nullable=True),
)

# Read-only data dictionary tables imported from legacy Rails app.
document_data_dictionaries = Table(
    "document_data_dictionaries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("friendlier_id", String(255), nullable=False, index=True),
    Column("name", String(255), nullable=True),
    Column("description", Text, nullable=True),
    Column("staff_notes", Text, nullable=True),
    Column("tags", String(4096), nullable=False, server_default=""),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

document_data_dictionary_entries = Table(
    "document_data_dictionary_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "document_data_dictionary_id",
        Integer,
        ForeignKey("document_data_dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("friendlier_id", String(255), nullable=False),
    Column("field_name", String(255), nullable=False),
    Column("field_type", String(255), nullable=True),
    Column("values", Text, nullable=True),
    Column("definition", Text, nullable=True),
    Column("definition_source", Text, nullable=True),
    Column("parent_field_name", String(255), nullable=True),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
    UniqueConstraint(
        "document_data_dictionary_id",
        "friendlier_id",
        "field_name",
        name="uq_document_data_dictionary_entries_dict_friendlier_field",
    ),
)

# Resource-scoped data dictionary tables (new naming).
resource_data_dictionaries = Table(
    "resource_data_dictionaries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String(255), nullable=False, index=True),
    Column("legacy_document_data_dictionary_id", Integer, nullable=True, unique=True, index=True),
    Column("name", String(255), nullable=True),
    Column("description", Text, nullable=True),
    Column("staff_notes", Text, nullable=True),
    Column("tags", String(4096), nullable=False, server_default=""),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

resource_data_dictionary_entries = Table(
    "resource_data_dictionary_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "resource_data_dictionary_id",
        Integer,
        ForeignKey("resource_data_dictionaries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "legacy_document_data_dictionary_entry_id",
        Integer,
        nullable=True,
        unique=True,
        index=True,
    ),
    Column("field_name", String(255), nullable=False),
    Column("field_type", String(255), nullable=True),
    Column("values", Text, nullable=True),
    Column("definition", Text, nullable=True),
    Column("definition_source", Text, nullable=True),
    Column("parent_field_name", String(255), nullable=True),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
    UniqueConstraint(
        "resource_data_dictionary_id",
        "field_name",
        "parent_field_name",
        "position",
        name="uq_resource_data_dictionary_entries_dict_field_position",
    ),
)

# API Rate Limiting tables

# API service tiers table
api_service_tiers = Table(
    "api_service_tiers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tier_name", String(100), nullable=False, unique=True, index=True),
    Column("display_name", String(255), nullable=False),
    Column("requests_per_minute", Integer, nullable=True),  # NULL = unlimited
    Column("description", Text, nullable=True),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
)

# API keys table
api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("key_hash", String(64), nullable=False, unique=True, index=True),  # SHA-256 hash
    Column("tier_id", Integer, nullable=False, index=True),
    Column("name", String(255), nullable=True),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("created_at", TIMESTAMP, nullable=False),
    Column("updated_at", TIMESTAMP, nullable=False),
    Column("last_used_at", TIMESTAMP, nullable=True),
    Column("allowed_ips", JSON, nullable=True),  # JSON array of allowed IP addresses
)

# API usage logs table (for future analytics, inspired by Ahoy's comprehensive tracking)
api_usage_logs = Table(
    "api_usage_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("api_key_id", Integer, nullable=True, index=True),  # Nullable for anonymous requests
    Column("tier_id", Integer, nullable=False, index=True),
    # Unique identifier to group requests from same session/visit
    Column("visit_token", String(255), nullable=True, index=True),
    Column("endpoint", String(500), nullable=False),
    Column("method", String(10), nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("requested_at", TIMESTAMP, nullable=False, index=True),
    Column("response_time_ms", Integer, nullable=True),  # Response time in milliseconds
    Column("ip_address", String(45), nullable=True),  # IPv6 max length
    Column("user_agent", String(500), nullable=True),
    # Traffic Source (Ahoy-inspired)
    Column("referrer", String(500), nullable=True),  # HTTP Referer header
    Column("referring_domain", String(255), nullable=True),  # Extracted from referrer
    Column("landing_page", String(500), nullable=True),  # First endpoint in visit
    # Technology (Ahoy-inspired, parsed from user_agent)
    Column("browser", String(100), nullable=True),  # Browser name
    Column("os", String(100), nullable=True),  # Operating system
    Column("device_type", String(50), nullable=True),  # mobile, tablet, desktop, bot, etc.
    # UTM Parameters (Ahoy-inspired)
    Column("utm_source", String(255), nullable=True),
    Column("utm_medium", String(255), nullable=True),
    Column("utm_term", String(255), nullable=True),
    Column("utm_content", String(255), nullable=True),
    Column("utm_campaign", String(255), nullable=True),
    # Custom properties/metadata for the request (Ahoy-inspired event properties)
    Column("properties", JSON, nullable=True),
)

# OpenGeoMetadata Harvesting / Admin tables

ogm_repos = Table(
    "ogm_repos",
    metadata,
    Column("ogm_repo_name", String(255), primary_key=True),
    Column("ogm_enabled", Boolean, nullable=False, server_default="true"),
    Column("ogm_watch_mode", String(20), nullable=False, server_default="weekly"),
    Column("ogm_last_harvest_started_at", TIMESTAMP, nullable=True),
    Column("ogm_last_harvest_completed_at", TIMESTAMP, nullable=True),
    Column("ogm_last_harvest_status", String(20), nullable=True),
    Column("ogm_last_commit_sha", String(64), nullable=True),
    Column("ogm_notes", Text, nullable=True),
    Column("ogm_tags", JSON, nullable=True),
    Column("ogm_created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("ogm_updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

ogm_harvest_runs = Table(
    "ogm_harvest_runs",
    metadata,
    Column("ogm_id", Integer, primary_key=True, autoincrement=True),
    Column("ogm_repo_name", String(255), nullable=False, index=True),
    Column("ogm_trigger", String(20), nullable=False),
    Column("ogm_started_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("ogm_completed_at", TIMESTAMP, nullable=True),
    Column("ogm_status", String(20), nullable=True),
    Column("ogm_stats_json", JSON, nullable=True),
    Column("ogm_dump_dir", Text, nullable=True),
    Column("ogm_error", Text, nullable=True),
    Column("ogm_created_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

ogm_resource_state = Table(
    "ogm_resource_state",
    metadata,
    Column("ogm_repo_name", String(255), primary_key=True, index=True),
    Column("ogm_resource_id", String(255), primary_key=True, index=True),
    Column("ogm_first_seen_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("ogm_last_seen_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("ogm_missing_since", TIMESTAMP, nullable=True),
    Column("ogm_source_path", Text, nullable=True),
    Column("ogm_source_commit_sha", String(64), nullable=True),
    Column("ogm_created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("ogm_updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

# Homepage content ingest tables
gin_blog_posts = Table(
    "gin_blog_posts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("slug", String(255), nullable=False, index=True),
    Column("source_path", String(500), nullable=False, unique=True, index=True),
    Column("url", String(500), nullable=False),
    Column("title", String(500), nullable=False),
    Column("excerpt", Text, nullable=False),
    Column("published_at", TIMESTAMP, nullable=False, index=True),
    Column("category", String(20), nullable=False, index=True),  # post|update
    Column("authors_json", JSON, nullable=False),
    Column("tags_json", JSON, nullable=False),
    Column("image_url", String(1000), nullable=True),
    Column("image_alt", Text, nullable=True),
    Column("source_sha", String(64), nullable=True),
    Column("synced_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("is_active", Boolean, nullable=False, server_default="true", index=True),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
    UniqueConstraint("slug", name="uq_gin_blog_posts_slug"),
)
