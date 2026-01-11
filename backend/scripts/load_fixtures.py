#!/usr/bin/env python3
import csv
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.elasticsearch.index import index_resources
from db.models import resources

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def truncate_resources_table(engine):
    """Truncate the resources table."""
    logger.info("Truncating resources table...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE resources CASCADE"))
        conn.commit()


def load_csv_data(engine, csv_file_path):
    """Load data from CSV file into resources table."""
    logger.info(f"Loading data from {csv_file_path}")

    with engine.connect() as conn:
        # Read CSV file
        with open(csv_file_path, "r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)

            # Process each row
            for row_num, record in enumerate(csv_reader, start=1):
                try:
                    # Clean the record data
                    cleaned_record = {}
                    for key, value in record.items():
                        if value == "":
                            cleaned_record[key] = None
                        elif key in [
                            "dct_alternative_sm",
                            "dct_description_sm",
                            "dct_language_sm",
                            "gbl_displaynote_sm",
                            "dct_creator_sm",
                            "dct_publisher_sm",
                            "gbl_resourceclass_sm",
                            "gbl_resourcetype_sm",
                            "dct_subject_sm",
                            "dcat_theme_sm",
                            "dcat_keyword_sm",
                            "dct_temporal_sm",
                            "gbl_indexyear_im",
                            "gbl_daterange_drsim",
                            "dct_spatial_sm",
                            "dct_relation_sm",
                            "pcdm_memberof_sm",
                            "dct_ispartof_sm",
                            "dct_source_sm",
                            "dct_isversionof_sm",
                            "dct_replaces_sm",
                            "dct_isreplacedby_sm",
                            "dct_rights_sm",
                            "dct_rightsholder_sm",
                            "dct_license_sm",
                            "dct_identifier_sm",
                        ]:
                            # Handle array fields
                            if value and value.strip():
                                # Split by semicolon and clean each value
                                values = [v.strip() for v in value.split(";") if v.strip()]
                                cleaned_record[key] = values if values else None
                            else:
                                cleaned_record[key] = None
                        elif key in ["gbl_suppressed_b", "gbl_georeferenced_b"]:
                            # Handle boolean fields
                            if value and value.lower() in ["true", "1", "yes"]:
                                cleaned_record[key] = True
                            elif value and value.lower() in ["false", "0", "no"]:
                                cleaned_record[key] = False
                            else:
                                cleaned_record[key] = None
                        else:
                            cleaned_record[key] = value.strip() if value else None

                    # Insert the record
                    conn.execute(resources.insert(), cleaned_record)

                    if row_num % 100 == 0:
                        logger.info(f"Processed {row_num} records")

                except Exception as e:
                    logger.error(f"Error processing row {row_num}: {e}")
                    logger.error(f"Record: {record}")
                    continue

        conn.commit()
        logger.info("Data loading completed")


def load_relationships(engine, csv_file_path):
    """Load relationships from CSV file."""
    logger.info(f"Loading relationships from {csv_file_path}")

    with engine.connect() as conn:
        # Truncate existing relationships
        conn.execute(text("TRUNCATE TABLE resource_relationships"))

        # Read CSV file
        with open(csv_file_path, "r", encoding="utf-8") as file:
            csv_reader = csv.DictReader(file)

            for row_num, record in enumerate(csv_reader, start=1):
                try:
                    # Extract relationship data
                    subject_id = record.get("subject_id")
                    predicate = record.get("predicate")
                    object_id = record.get("object_id")

                    if subject_id and predicate and object_id:
                        # Insert relationship
                        conn.execute(
                            text("""
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """),
                            {
                                "subject_id": subject_id,
                                "predicate": predicate,
                                "object_id": object_id,
                            },
                        )

                    if row_num % 100 == 0:
                        logger.info(f"Processed {row_num} relationship records")

                except Exception as e:
                    logger.error(f"Error processing relationship row {row_num}: {e}")
                    continue

        conn.commit()
        logger.info("Relationship loading completed")


async def main():
    """Main function to load fixtures and reindex."""
    try:
        # Get database URL from environment
        database_url = os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test"
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        # Create engine
        engine = create_engine(sync_database_url)

        # Check if CSV file exists
        csv_file_path = "data/fixtures/gbl_fixtures_data.csv"
        if not os.path.exists(csv_file_path):
            logger.error(f"CSV file not found: {csv_file_path}")
            return

        # Truncate resources table
        truncate_resources_table(engine)

        # Load data from CSV
        load_csv_data(engine, csv_file_path)

        # Load relationships if the file exists
        relationships_file = "data/fixtures/relationships.csv"
        if os.path.exists(relationships_file):
            load_relationships(engine, relationships_file)

        # Reindex in Elasticsearch
        logger.info("Starting Elasticsearch indexing...")
        result = await index_resources()
        logger.info(f"Indexing result: {result}")

        logger.info("Fixture loading completed successfully!")

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
