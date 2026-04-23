import logging

from dotenv import load_dotenv

from db.migrations.add_enrichment_type import add_enrichment_type_column
from db.migrations.add_fast_gazetteer import add_fast_gazetteer
from db.migrations.api_rate_limiting import init_api_rate_limiting
from db.migrations.create_ai_enrichments import create_ai_enrichments_table
from db.migrations.create_fast_embeddings import create_fast_embeddings_table
from db.migrations.create_gazetteer_tables import create_gazetteer_tables
from db.migrations.create_item_allmaps_table import create_item_allmaps_table
from db.migrations.create_resource_relationships import create_relationships_table
from db.migrations.rename_ai_enrichments import rename_ai_enrichments_table
from db.migrations.rename_all_item_tables import rename_all_item_tables
from db.migrations.rename_document_id_to_item_id import rename_document_id_to_item_id
from db.migrations.rename_indexes import rename_indexes
from db.migrations.rename_item_id_to_resource_id import rename_item_id_to_resource_id
from db.migrations.rename_remaining_constraints import rename_remaining_constraints
from db.migrations.update_fast_gazetteer import update_fast_gazetteer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run all database migrations."""
    logger.info("Running database migrations...")

    try:
        # Create gazetteer tables
        logger.info("Creating gazetteer tables...")
        create_gazetteer_tables()

        # Create item relationships table
        logger.info("Creating item relationships table...")
        create_relationships_table()

        # Create FAST embeddings table
        logger.info("Creating FAST embeddings table...")
        create_fast_embeddings_table()

        # Create AI enrichments table
        logger.info("Creating AI enrichments table...")
        create_ai_enrichments_table()

        # Add enrichment type column
        logger.info("Adding enrichment type column...")
        add_enrichment_type_column()

        # Add FAST gazetteer
        logger.info("Adding FAST gazetteer...")
        add_fast_gazetteer()

        # Update FAST gazetteer
        logger.info("Updating FAST gazetteer...")
        update_fast_gazetteer()

        # Rename AI enrichments table
        logger.info("Renaming AI enrichments table...")
        rename_ai_enrichments_table()

        # Rename document_id to item_id in item_ai_enrichments table
        logger.info("Renaming document_id to item_id in item_ai_enrichments table...")
        rename_document_id_to_item_id()

        # Create item_allmaps table
        logger.info("Creating item_allmaps table...")
        create_item_allmaps_table()

        # Rename all item_* tables to resource_* tables
        logger.info("Renaming all item_* tables to resource_* tables...")
        rename_all_item_tables()

        # Rename item_id columns to resource_id in relevant tables
        logger.info("Renaming item_id columns to resource_id...")
        rename_item_id_to_resource_id()

        # Rename indexes that still reference old item_ naming
        logger.info("Renaming indexes to match new naming...")
        rename_indexes()

        # Rename remaining constraints and indexes
        logger.info("Renaming remaining constraints and indexes...")
        rename_remaining_constraints()

        # Initialize API rate limiting schema and tiers (idempotent)
        logger.info("Initializing API rate limiting schema and tiers...")
        init_api_rate_limiting()

    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        raise


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Run migrations
    run_migrations()
