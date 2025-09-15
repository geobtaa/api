#!/usr/bin/env python
"""
This script processes resource relationships from the resources table
and populates the resource_relationships table with both primary and inverse relationships.

The script:
1. Reads the resources table
2. Extracts relationship information from dct_relation_sm field
3. Populates the resource_relationships table with relationships from resources.
4. Creates inverse relationships for bidirectional navigation
5. Handles different relationship types and formats

Usage:
    python scripts/populate_relationships.py

Requirements:
    - PostgreSQL database with resources table
    - resource_relationships table created
    - DATABASE_URL environment variable set
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.database import database

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def populate_relationships():
    """Populate the resource_relationships table with relationships from resources."""
    try:
        # Connect to database
        await database.connect()
        logger.info("Connected to database")

        # Clear existing relationships
        await database.execute("TRUNCATE TABLE resource_relationships")
        logger.info("Cleared existing relationships")

        # Fetch all resources with relationship fields
        logger.info("Fetching resources...")
        resources_query = """
            SELECT id, dct_relation_sm, dct_ispartof_sm, pcdm_memberof_sm, dct_source_sm, 
                   dct_isversionof_sm, dct_replaces_sm, dct_isreplacedby_sm
            FROM resources
            WHERE dct_relation_sm IS NOT NULL 
               OR dct_ispartof_sm IS NOT NULL 
               OR pcdm_memberof_sm IS NOT NULL
               OR dct_source_sm IS NOT NULL
               OR dct_isversionof_sm IS NOT NULL
               OR dct_replaces_sm IS NOT NULL
               OR dct_isreplacedby_sm IS NOT NULL
        """
        resources = await database.fetch_all(resources_query)
        logger.info(f"Found {len(resources)} resources with relationships")

        # Process each resource
        total_relationships = 0
        for resource in resources:
            resource_id = resource["id"]
            relationships_added = 0

            # Process dct_relation_sm (general relationships)
            if resource["dct_relation_sm"]:
                for related_id in resource["dct_relation_sm"]:
                    if related_id and related_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:relation",
                                "object_id": related_id,
                            },
                        )
                        relationships_added += 1

            # Process dct_ispartof_sm (is part of)
            if resource["dct_ispartof_sm"]:
                for parent_id in resource["dct_ispartof_sm"]:
                    if parent_id and parent_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:isPartOf",
                                "object_id": parent_id,
                            },
                        )
                        relationships_added += 1

            # Process pcdm_memberof_sm (member of)
            if resource["pcdm_memberof_sm"]:
                for collection_id in resource["pcdm_memberof_sm"]:
                    if collection_id and collection_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "pcdm:memberOf",
                                "object_id": collection_id,
                            },
                        )
                        relationships_added += 1

            # Process dct_source_sm (source)
            if resource["dct_source_sm"]:
                for source_id in resource["dct_source_sm"]:
                    if source_id and source_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:source",
                                "object_id": source_id,
                            },
                        )
                        relationships_added += 1

            # Process dct_isversionof_sm (is version of)
            if resource["dct_isversionof_sm"]:
                for version_id in resource["dct_isversionof_sm"]:
                    if version_id and version_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:isVersionOf",
                                "object_id": version_id,
                            },
                        )
                        relationships_added += 1

            # Process dct_replaces_sm (replaces)
            if resource["dct_replaces_sm"]:
                for replaced_id in resource["dct_replaces_sm"]:
                    if replaced_id and replaced_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:replaces",
                                "object_id": replaced_id,
                            },
                        )
                        relationships_added += 1

            # Process dct_isreplacedby_sm (is replaced by)
            if resource["dct_isreplacedby_sm"]:
                for replacement_id in resource["dct_isreplacedby_sm"]:
                    if replacement_id and replacement_id != resource_id:
                        await database.execute(
                            """
                            INSERT INTO resource_relationships (subject_id, predicate, object_id)
                            VALUES (:subject_id, :predicate, :object_id)
                        """,
                            {
                                "subject_id": resource_id,
                                "predicate": "dct:isReplacedBy",
                                "object_id": replacement_id,
                            },
                        )
                        relationships_added += 1

            total_relationships += relationships_added
            if relationships_added > 0:
                logger.info(f"Added {relationships_added} relationships for resource {resource_id}")

        logger.info(f"Total relationships added: {total_relationships}")

        # Create inverse relationships for bidirectional navigation
        logger.info("Creating inverse relationships...")
        inverse_relationships = await database.fetch_all("""
            SELECT subject_id, predicate, object_id FROM resource_relationships
        """)

        inverse_count = 0
        for rel in inverse_relationships:
            # Create inverse relationship
            inverse_predicate = get_inverse_predicate(rel["predicate"])
            if inverse_predicate:
                # Check if inverse relationship already exists
                existing = await database.fetch_one(
                    """
                    SELECT id FROM resource_relationships 
                    WHERE subject_id = :subject_id 
                    AND predicate = :predicate 
                    AND object_id = :object_id
                """,
                    {
                        "subject_id": rel["object_id"],
                        "predicate": inverse_predicate,
                        "object_id": rel["subject_id"],
                    },
                )

                if not existing:
                    await database.execute(
                        """
                        INSERT INTO resource_relationships (subject_id, predicate, object_id)
                        VALUES (:subject_id, :predicate, :object_id)
                    """,
                        {
                            "subject_id": rel["object_id"],
                            "predicate": inverse_predicate,
                            "object_id": rel["subject_id"],
                        },
                    )
                    inverse_count += 1

        logger.info(f"Added {inverse_count} inverse relationships")

        logger.info("Relationship population completed successfully!")

    except Exception as e:
        logger.error(f"Error populating relationships: {e}", exc_info=True)
        raise
    finally:
        await database.disconnect()
        logger.info("Disconnected from database")


def get_inverse_predicate(predicate):
    """Get the inverse predicate for a given relationship."""
    inverse_mapping = {
        "dct:relation": "dct:relation",
        "dct:isPartOf": "dct:hasPart",
        "dct:hasPart": "dct:isPartOf",
        "pcdm:memberOf": "pcdm:hasMember",
        "pcdm:hasMember": "pcdm:memberOf",
        "dct:source": "dct:isSourceOf",
        "dct:isSourceOf": "dct:source",
        "dct:isVersionOf": "dct:hasVersion",
        "dct:hasVersion": "dct:isVersionOf",
        "dct:replaces": "dct:isReplacedBy",
        "dct:isReplacedBy": "dct:replaces",
    }
    return inverse_mapping.get(predicate)


if __name__ == "__main__":
    asyncio.run(populate_relationships())
