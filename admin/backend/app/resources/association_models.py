"""Resource association compatibility models for local construction.

Preserves data-api field shapes. DEC-005 production reconciliation remains open;
Resource endpoint IDs deliberately have no blanket FK/cascade policy.
"""

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

from app.persistence import metadata

resource_relationships = Table(
    "resource_relationships",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("subject_id", String, nullable=False),
    Column("predicate", String, nullable=False),
    Column("object_id", String, nullable=False),
)

resource_downloads = Table(
    "resource_downloads",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String(255), nullable=False, index=True),
    Column("label", String(255), nullable=True),
    Column("value", Text, nullable=True),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("import_download_id", String(255), nullable=True, index=True),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

# Resource licensed accesses table
resource_licensed_accesses = Table(
    "resource_licensed_accesses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String(255), nullable=False, index=True),
    Column("institution_code", String(255), nullable=False, index=True),
    Column("access_url", Text, nullable=False),
    Column("legacy_friendlier_id", String(255), nullable=True, index=True),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
)

# Resource assets table
resource_assets = Table(
    "resource_assets",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("resource_id", String(255), nullable=False, index=True),
    Column("bridge_asset_id", String(255), nullable=True, index=True),
    Column("bridge_parent_id", String(255), nullable=True, index=True),
    Column("friendlier_id", String(255), nullable=True, index=True),
    Column("title", String(500), nullable=True),
    Column("label", String(255), nullable=True),
    Column("thumbnail", Boolean, nullable=False, server_default="false", index=True),
    Column("dct_references_uri_key", String(255), nullable=True),
    Column("position", Integer, nullable=False, server_default="0"),
    Column("file_url", Text, nullable=True),
    Column("file_mime_type", String(255), nullable=True),
    Column("file_size", Integer, nullable=True),
    Column("file_width", Integer, nullable=True),
    Column("file_height", Integer, nullable=True),
    Column("file_md5", String(64), nullable=True),
    Column("file_sha1", String(64), nullable=True),
    Column("file_sha512", String(128), nullable=True),
    Column("created_at", TIMESTAMP, nullable=False, server_default=func.now()),
    Column("updated_at", TIMESTAMP, nullable=False, server_default=func.now()),
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


Index(
    "resource_relationships_subject_predicate",
    resource_relationships.c.subject_id,
    resource_relationships.c.predicate,
)
Index("resource_relationships_object", resource_relationships.c.object_id)

FAMILIES = {
    "relationships": resource_relationships,
    "downloads": resource_downloads,
    "licensed-accesses": resource_licensed_accesses,
    "assets": resource_assets,
    "data-dictionaries": resource_data_dictionaries,
    "dictionary-entries": resource_data_dictionary_entries,
}
