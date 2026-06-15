"""
Celery tasks for processing Allmaps data.

This module contains background tasks for fetching IIIF manifests,
checking Allmaps annotations, and populating the resource_allmaps table.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

import aiohttp
from celery import Task, shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.security_utils import stable_hex_digest
from db.async_engine import create_app_async_engine
from db.config import DATABASE_URL
from db.models import distribution_types, resource_allmaps, resource_distributions, resources

logger = logging.getLogger(__name__)

# Create async engine and session
engine = create_app_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def generate_allmaps_id(manifest: str) -> Optional[str]:
    """Generate an Allmaps ID from a IIIF manifest.

    Args:
        manifest: The IIIF manifest JSON as a string

    Returns:
        str: The generated Allmaps ID (first 16 chars of a stable secure digest)
    """
    try:
        manifest_json = json.loads(manifest)

        # Get the manifest ID from either @id (v2) or id (v3) field
        manifest_id = manifest_json.get("@id") or manifest_json.get("id")

        if not manifest_id:
            logger.error("No manifest ID found in IIIF manifest")
            return None

        return stable_hex_digest(manifest_id, digest_size=8)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in IIIF manifest")
        return None
    except Exception as e:
        logger.error(f"Error generating Allmaps ID: {e}")
        return None


async def fetch_manifest(session: aiohttp.ClientSession, manifest_url: str) -> Optional[str]:
    """Fetch and validate a IIIF manifest (v2 or v3)."""
    try:
        async with session.get(manifest_url) as response:
            if response.status == 200:
                manifest = await response.text()
                try:
                    manifest_json = json.loads(manifest)

                    # Basic validation
                    if not isinstance(manifest_json, dict):
                        raise ValueError("Manifest must be a JSON object")

                    # Check for IIIF v2 or v3
                    has_context = "@context" in manifest_json or "context" in manifest_json
                    if not has_context:
                        raise ValueError("Manifest missing @context")

                    # IIIF v2 uses @type with "sc:Manifest"
                    # IIIF v3 uses type with "Manifest"
                    type_field = manifest_json.get("@type") or manifest_json.get("type")
                    if not type_field:
                        raise ValueError("Manifest missing type field")

                    # Validate it's a manifest (v2 or v3)
                    if type_field not in ["sc:Manifest", "Manifest"]:
                        raise ValueError(f"Not a valid IIIF manifest (type: {type_field})")

                    return manifest

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response for manifest {manifest_url}")
                    return None
                except ValueError as e:
                    logger.error(f"Invalid IIIF manifest {manifest_url}: {e}")
                    return None
            else:
                logger.warning(
                    f"Failed to fetch manifest {manifest_url} (status: {response.status})"
                )
                return None
    except Exception as e:
        logger.error(f"Error fetching manifest {manifest_url}: {e}")
        return None


async def check_allmaps_annotation(
    session: aiohttp.ClientSession, manifest_url: str
) -> Optional[str]:
    """Check if Allmaps has an annotation for the given manifest URL."""
    annotation_url = f"https://annotations.allmaps.org/?url={manifest_url}"

    try:
        async with session.get(annotation_url, allow_redirects=True) as response:
            if response.status == 200:
                annotation = await response.text()
                try:
                    json.loads(annotation)
                    return annotation
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON response from Allmaps for {manifest_url}")
                    return None
            else:
                logger.debug(
                    f"No Allmaps annotation found for {manifest_url} (status: {response.status})"
                )
                return None
    except Exception as e:
        logger.error(f"Error checking Allmaps annotation for {manifest_url}: {e}")
        return None


async def process_resource(resource_id: str, manifest_url: str) -> bool:
    """Process a single resource and store its Allmaps data.

    Args:
        resource_id: The resource ID to process
        manifest_url: The IIIF manifest URL

    Returns:
        bool: True if the resource was processed successfully, False otherwise
    """
    # Create a new engine and session for this task to avoid concurrency issues
    task_engine = create_app_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async_session_factory = sessionmaker(
            task_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session_factory() as session:
            async with aiohttp.ClientSession() as http_session:
                # Fetch manifest and check for Allmaps annotation concurrently
                manifest_task = fetch_manifest(http_session, manifest_url)
                annotation_task = check_allmaps_annotation(http_session, manifest_url)

                manifest, annotation = await asyncio.gather(manifest_task, annotation_task)

                if not manifest:
                    logger.warning(f"Could not fetch manifest for {resource_id}. Skipping.")
                    return False

                # Generate Allmaps ID from the manifest
                allmaps_id = generate_allmaps_id(manifest)
                if not allmaps_id:
                    logger.error(f"Could not generate Allmaps ID for {resource_id}. Skipping.")
                    return False

                # Delete any existing record for this resource
                await session.execute(
                    resource_allmaps.delete().where(resource_allmaps.c.resource_id == resource_id)
                )
                await session.commit()

                # Create new resource_allmaps record
                now = datetime.now()
                new_record = {
                    "resource_id": resource_id,
                    "allmaps_id": allmaps_id,
                    "iiif_manifest_uri": manifest_url,
                    "annotated": bool(annotation),
                    "iiif_manifest": manifest,
                    "allmaps_annotation": annotation,
                    "created_at": now,
                    "updated_at": now,
                }

                await session.execute(resource_allmaps.insert(), new_record)
                await session.commit()

                logger.info(f"Processed resource {resource_id} - Annotated: {bool(annotation)}")
                return True

    except Exception as e:
        logger.error(f"Error processing resource {resource_id}: {e}")
        return False
    finally:
        # Dispose of the engine to clean up connections
        await task_engine.dispose()


@shared_task(bind=True, name="process_allmaps_resource")
def process_allmaps_resource(self: Task, resource_id: str, manifest_url: str) -> dict:
    """
    Celery task to process a single resource's Allmaps data.

    Args:
        resource_id: The resource ID
        manifest_url: The IIIF manifest URL

    Returns:
        dict: Result with success status
    """
    try:
        success = asyncio.run(process_resource(resource_id, manifest_url))
        return {
            "resource_id": resource_id,
            "success": success,
            "annotated": success,  # Will be updated with actual value later
        }
    except Exception as e:
        logger.error(f"Error in Celery task for resource {resource_id}: {e}")
        return {"resource_id": resource_id, "success": False, "error": str(e)}


@shared_task(bind=True, name="index_all_allmaps")
def index_all_allmaps(self: Task, batch_size: int = 100) -> dict:
    """
    Celery task to submit all resources with IIIF manifests for Allmaps processing.

    Args:
        batch_size: Number of resources to process per batch

    Returns:
        dict: Summary of submitted jobs
    """

    async def get_resources_with_manifests():
        """Get all resources with IIIF manifests."""
        # Create a new engine and session for this operation
        task_engine = create_app_async_engine(DATABASE_URL, pool_pre_ping=True)
        try:
            async_session_factory = sessionmaker(
                task_engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session_factory() as session:
                manifest_uri = "http://iiif.io/api/presentation#manifest"
                query = (
                    select(resources.c.id, resource_distributions.c.url)
                    .select_from(
                        resources.join(
                            resource_distributions,
                            resources.c.id == resource_distributions.c.resource_id,
                        ).join(
                            distribution_types,
                            resource_distributions.c.distribution_type_id
                            == distribution_types.c.id,
                        )
                    )
                    .where(distribution_types.c.distribution_uri == manifest_uri)
                )
                results = await session.execute(query)
                return results.fetchall()
        finally:
            await task_engine.dispose()

    try:
        # Get all resources with IIIF manifests
        resource_list = asyncio.run(get_resources_with_manifests())
        total = len(resource_list)

        logger.info(f"Found {total} resources with IIIF manifests")

        if total == 0:
            return {
                "status": "completed",
                "total_resources": 0,
                "jobs_submitted": 0,
                "message": "No resources with IIIF manifests found",
            }

        # Submit jobs for each resource
        jobs_submitted = 0
        for resource in resource_list:
            try:
                manifest_url = resource.url
                if manifest_url:
                    process_allmaps_resource.delay(resource.id, manifest_url)
                    jobs_submitted += 1

            except Exception as e:
                logger.error(f"Error submitting job for resource {resource.id}: {e}")
                continue

        logger.info(f"Submitted {jobs_submitted} Allmaps processing jobs to queue")

        return {
            "status": "completed",
            "total_resources": total,
            "jobs_submitted": jobs_submitted,
            "message": f"Successfully submitted {jobs_submitted} jobs for processing",
        }

    except Exception as e:
        logger.error(f"Error in index_all_allmaps task: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "message": "Failed to submit Allmaps processing jobs",
        }
