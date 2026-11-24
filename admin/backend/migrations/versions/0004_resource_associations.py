"""Add local Resource association compatibility tables; production gates remain open."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE resource_relationships (
	id SERIAL NOT NULL,
	subject_id VARCHAR NOT NULL,
	predicate VARCHAR NOT NULL,
	object_id VARCHAR NOT NULL,
	PRIMARY KEY (id)
)
""")
    op.execute("""
CREATE INDEX resource_relationships_object ON resource_relationships (object_id)
""")
    op.execute("""
CREATE INDEX resource_relationships_subject_predicate ON resource_relationships (subject_id,
predicate)
""")
    op.execute("""
CREATE TABLE resource_downloads (
	id SERIAL NOT NULL,
	resource_id VARCHAR(255) NOT NULL,
	label VARCHAR(255),
	value TEXT,
	position INTEGER DEFAULT '0' NOT NULL,
	import_download_id VARCHAR(255),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)
""")
    op.execute("""
CREATE INDEX ix_resource_downloads_import_download_id ON resource_downloads (import_download_id)
""")
    op.execute("""
CREATE INDEX ix_resource_downloads_resource_id ON resource_downloads (resource_id)
""")
    op.execute("""
CREATE TABLE resource_licensed_accesses (
	id SERIAL NOT NULL,
	resource_id VARCHAR(255) NOT NULL,
	institution_code VARCHAR(255) NOT NULL,
	access_url TEXT NOT NULL,
	legacy_friendlier_id VARCHAR(255),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)
""")
    op.execute("""
CREATE INDEX ix_resource_licensed_accesses_institution_code ON resource_licensed_accesses
(institution_code)
""")
    op.execute("""
CREATE INDEX ix_resource_licensed_accesses_legacy_friendlier_id ON resource_licensed_accesses
(legacy_friendlier_id)
""")
    op.execute("""
CREATE INDEX ix_resource_licensed_accesses_resource_id ON resource_licensed_accesses (resource_id)
""")
    op.execute("""
CREATE TABLE resource_assets (
	id SERIAL NOT NULL,
	resource_id VARCHAR(255) NOT NULL,
	bridge_asset_id VARCHAR(255),
	bridge_parent_id VARCHAR(255),
	friendlier_id VARCHAR(255),
	title VARCHAR(500),
	label VARCHAR(255),
	thumbnail BOOLEAN DEFAULT 'false' NOT NULL,
	dct_references_uri_key VARCHAR(255),
	position INTEGER DEFAULT '0' NOT NULL,
	file_url TEXT,
	file_mime_type VARCHAR(255),
	file_size INTEGER,
	file_width INTEGER,
	file_height INTEGER,
	file_md5 VARCHAR(64),
	file_sha1 VARCHAR(64),
	file_sha512 VARCHAR(128),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)
""")
    op.execute("""
CREATE INDEX ix_resource_assets_bridge_asset_id ON resource_assets (bridge_asset_id)
""")
    op.execute("""
CREATE INDEX ix_resource_assets_bridge_parent_id ON resource_assets (bridge_parent_id)
""")
    op.execute("""
CREATE INDEX ix_resource_assets_friendlier_id ON resource_assets (friendlier_id)
""")
    op.execute("""
CREATE INDEX ix_resource_assets_resource_id ON resource_assets (resource_id)
""")
    op.execute("""
CREATE INDEX ix_resource_assets_thumbnail ON resource_assets (thumbnail)
""")
    op.execute("""
CREATE TABLE resource_data_dictionaries (
	id SERIAL NOT NULL,
	resource_id VARCHAR(255) NOT NULL,
	legacy_document_data_dictionary_id INTEGER,
	name VARCHAR(255),
	description TEXT,
	staff_notes TEXT,
	tags VARCHAR(4096) DEFAULT '' NOT NULL,
	position INTEGER DEFAULT '0' NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)
""")
    op.execute("""
CREATE UNIQUE INDEX ix_resource_data_dictionaries_legacy_document_data_dict_d34e ON
resource_data_dictionaries (legacy_document_data_dictionary_id)
""")
    op.execute("""
CREATE INDEX ix_resource_data_dictionaries_resource_id ON resource_data_dictionaries (resource_id)
""")
    op.execute("""
CREATE TABLE resource_data_dictionary_entries (
	id SERIAL NOT NULL,
	resource_data_dictionary_id INTEGER NOT NULL,
	legacy_document_data_dictionary_entry_id INTEGER,
	field_name VARCHAR(255) NOT NULL,
	field_type VARCHAR(255),
	values TEXT,
	definition TEXT,
	definition_source TEXT,
	parent_field_name VARCHAR(255),
	position INTEGER DEFAULT '0' NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
        CONSTRAINT uq_resource_data_dictionary_entries_dict_field_position UNIQUE
(resource_data_dictionary_id, field_name, parent_field_name, position),
        FOREIGN KEY(resource_data_dictionary_id) REFERENCES resource_data_dictionaries (id) ON
DELETE CASCADE
)
""")
    op.execute("""
CREATE UNIQUE INDEX ix_resource_data_dictionary_entries_legacy_document_dat_36f1 ON
resource_data_dictionary_entries (legacy_document_data_dictionary_entry_id)
""")
    op.execute("""
CREATE INDEX ix_resource_data_dictionary_entries_resource_data_dictionary_id ON
resource_data_dictionary_entries (resource_data_dictionary_id)
""")


def downgrade():
    op.drop_table("resource_data_dictionary_entries")
    op.drop_table("resource_data_dictionaries")
    op.drop_table("resource_assets")
    op.drop_table("resource_licensed_accesses")
    op.drop_table("resource_downloads")
    op.drop_table("resource_relationships")
