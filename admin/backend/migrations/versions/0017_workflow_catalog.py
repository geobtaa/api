"""Shared descriptive workflow catalog from reviewed lookup worksheet."""

from alembic import op

# Seed descriptions mirror the reviewed worksheet and retain its exact wording.
# ruff: noqa: E501

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE workflow_catalog (
        workflow_id VARCHAR(128) PRIMARY KEY,
        label VARCHAR(250) NOT NULL,
        description TEXT NOT NULL,
        acquisition_mode VARCHAR(64) NOT NULL,
        CONSTRAINT workflow_catalog_id_format CHECK (workflow_id ~ '^[A-Za-z0-9_-]{1,128}$'),
        CONSTRAINT workflow_catalog_label CHECK (length(btrim(label)) > 0),
        CONSTRAINT workflow_catalog_mode CHECK (acquisition_mode IN
          ('automated_retrieval', 'mediated_deposit', 'manual_curation'))
    )""")
    op.execute("""INSERT INTO workflow_catalog
      (workflow_id, label, description, acquisition_mode) VALUES
      ('py_arcgis_hub','ArcGIS Hub','Harvest metadata from ArcGIS Hub portals using their DCAT endpoints.','automated_retrieval'),
      ('py_oaipmh','OAI-PMH','Harvest metadata from OAI-PMH repositories using a configured metadata prefix and set, when applicable.','automated_retrieval'),
      ('curation_datasets','Dataset acquisition','Acquire datasets through direct download or provider submission and prepare them for the collection.','mediated_deposit'),
      ('curation_rest_service','Dataset generation from REST service','Retrieve or generate datasets from a REST service endpoint for curation and ingest.','manual_curation'),
      ('py_ckan','CKAN portal','Harvest metadata from CKAN portals using the CKAN API.','automated_retrieval'),
      ('py_mods','MODS metadata','Parse MODS XML files and transform the metadata into the Geoportal metadata profile.','mediated_deposit'),
      ('py_ogm_aardvark','OpenGeoMetadata repository','Harvest OGM Aardvark metadata from OpenGeoMetadata repositories.','automated_retrieval'),
      ('py_pasda','PASDA portal','Harvest PASDA metadata using the custom PASDA HTML-parsing workflow.','automated_retrieval'),
      ('py_pasda_metadata_directory','PASDA Metadata Directory','Retrieve and parse metadata files published through the PASDA Metadata Directory.','automated_retrieval'),
      ('py_socrata','Socrata portal','Harvest metadata from Socrata portals using their DCAT endpoints.','automated_retrieval'),
      ('template_children','Manual website and child records','Author a website record and its child records using the BTAA metadata template.','manual_curation'),
      ('template_csv','Submitted spreadsheet','Transform submitted spreadsheet metadata after review and minor cleanup using the standard template workflow.','mediated_deposit'),
      ('template_json','Submitted JSON','Transform submitted JSON files and perform minor cleanup','mediated_deposit'),
      ('template_website','Standalone websites','Author a standalone website record','manual_curation')""")
    op.execute("""ALTER TABLE lifecycles ADD COLUMN workflow_catalog_id VARCHAR(128)
      REFERENCES workflow_catalog(workflow_id)""")
    op.execute("""ALTER TABLE sets ADD COLUMN workflow_catalog_id VARCHAR(128)
      REFERENCES workflow_catalog(workflow_id)""")
    op.execute("""UPDATE sets SET workflow_catalog_id = workflow
      WHERE workflow IN (SELECT workflow_id FROM workflow_catalog)""")
    op.execute("""UPDATE lifecycles AS l SET workflow_catalog_id = c.workflow_id
      FROM workflow_catalog AS c
      WHERE l.workflow_catalog_id IS NULL
        AND l.admin_notes ~ (E'(^|\\n)workflow: ' || c.workflow_id || E'(\\n|$)')""")


def downgrade():
    op.execute("ALTER TABLE sets DROP COLUMN workflow_catalog_id")
    op.execute("ALTER TABLE lifecycles DROP COLUMN workflow_catalog_id")
    op.execute("DROP TABLE workflow_catalog")
