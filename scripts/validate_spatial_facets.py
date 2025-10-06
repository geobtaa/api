#!/usr/bin/env python3
"""
Script to validate spatial facet indexing.

This script validates that the spatial facets indexed in Elasticsearch
match the computed spatial facets in the database.

Usage:
    python scripts/validate_spatial_facets.py [options]

Options:
    --sample-size: Number of resources to sample for validation (default: 100)
    --verbose: Show detailed validation results
"""

import argparse
import asyncio
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


async def validate_spatial_facets(sample_size: int = 100, verbose: bool = False):
    """Validate spatial facet indexing by comparing database and Elasticsearch data."""
    try:
        # Import here to avoid circular imports
        from app.elasticsearch.client import es
        from db.database import database

        # Initialize database connection
        await database.connect()

        try:
            # Get a sample of resources with spatial facets
            query = """
                SELECT r.id, r.dcat_bbox, rsf.geo_country, rsf.geo_region, rsf.geo_county
                FROM resources r
                JOIN resource_spatial_facets rsf ON r.id = rsf.resource_id
                WHERE r.dcat_bbox IS NOT NULL
                ORDER BY RANDOM()
                LIMIT :sample_size
            """

            result = await database.fetch_all(query, {"sample_size": sample_size})
            resources = [dict(row) for row in result]

            logger.info(f"Validating {len(resources)} resources...")

            validation_results = {
                "total_checked": len(resources),
                "matches": 0,
                "mismatches": 0,
                "errors": 0,
                "details": [],
            }

            for resource in resources:
                try:
                    # Get the resource from Elasticsearch
                    es_response = await es.get(index="btaa_ogm_api", id=resource["id"])

                    es_doc = es_response["_source"]

                    # Compare spatial facets
                    db_country = resource["geo_country"]
                    db_region = resource["geo_region"]
                    db_county = resource["geo_county"]

                    es_country = es_doc.get("geo_country")
                    es_region = es_doc.get("geo_region")
                    es_county = es_doc.get("geo_county")

                    # Parse JSON fields from database
                    import json

                    if db_region:
                        try:
                            db_region = (
                                json.loads(db_region) if isinstance(db_region, str) else db_region
                            )
                        except (json.JSONDecodeError, TypeError):
                            db_region = None

                    if db_county:
                        try:
                            db_county = (
                                json.loads(db_county) if isinstance(db_county, str) else db_county
                            )
                        except (json.JSONDecodeError, TypeError):
                            db_county = None

                    # Compare the values
                    country_match = db_country == es_country
                    region_match = db_region == es_region
                    county_match = db_county == es_county

                    if country_match and region_match and county_match:
                        validation_results["matches"] += 1
                        if verbose:
                            logger.info(f"✅ {resource['id']}: All facets match")
                    else:
                        validation_results["mismatches"] += 1
                        mismatch_details = {
                            "resource_id": resource["id"],
                            "country_match": country_match,
                            "region_match": region_match,
                            "county_match": county_match,
                            "db_country": db_country,
                            "es_country": es_country,
                            "db_region": db_region,
                            "es_region": es_region,
                            "db_county": db_county,
                            "es_county": es_county,
                        }
                        validation_results["details"].append(mismatch_details)

                        if verbose:
                            logger.warning(f"❌ {resource['id']}: Mismatch detected")
                            if not country_match:
                                logger.warning(f"  Country: DB='{db_country}' vs ES='{es_country}'")
                            if not region_match:
                                logger.warning(f"  Region: DB='{db_region}' vs ES='{es_region}'")
                            if not county_match:
                                logger.warning(f"  County: DB='{db_county}' vs ES='{es_county}'")

                except Exception as e:
                    validation_results["errors"] += 1
                    logger.error(f"Error validating {resource['id']}: {e}")
                    if verbose:
                        logger.error(f"  Error details: {str(e)}")

            # Print summary
            logger.info("=== Validation Summary ===")
            logger.info(f"Total resources checked: {validation_results['total_checked']}")
            logger.info(f"Matches: {validation_results['matches']}")
            logger.info(f"Mismatches: {validation_results['mismatches']}")
            logger.info(f"Errors: {validation_results['errors']}")

            if validation_results["total_checked"] > 0:
                match_rate = (
                    validation_results["matches"] / validation_results["total_checked"]
                ) * 100
                logger.info(f"Match rate: {match_rate:.1f}%")

            if validation_results["mismatches"] > 0:
                logger.warning(f"⚠️ Found {validation_results['mismatches']} mismatches")
                if verbose:
                    logger.info("Mismatch details:")
                    for detail in validation_results["details"]:
                        logger.info(
                            f"  {detail['resource_id']}: Country={detail['country_match']}, Region={detail['region_match']}, County={detail['county_match']}"
                        )
            else:
                logger.info("✅ All spatial facets match between database and Elasticsearch!")

            return validation_results

        finally:
            await database.disconnect()

    except Exception as e:
        logger.error(f"Error during validation: {e}", exc_info=True)
        return {"error": str(e)}


async def main():
    """Main function to handle command line arguments and run validation."""
    parser = argparse.ArgumentParser(
        description="Validate spatial facet indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate with default sample size
  python scripts/validate_spatial_facets.py
  
  # Validate with custom sample size and verbose output
  python scripts/validate_spatial_facets.py --sample-size 50 --verbose
        """,
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Number of resources to sample for validation (default: 100)",
    )

    parser.add_argument("--verbose", action="store_true", help="Show detailed validation results")

    args = parser.parse_args()

    try:
        logger.info(f"Starting spatial facet validation with sample size: {args.sample_size}")

        result = await validate_spatial_facets(args.sample_size, args.verbose)

        if "error" in result:
            logger.error(f"Validation failed: {result['error']}")
            return 1

        if result.get("mismatches", 0) > 0:
            logger.warning("Validation completed with mismatches found")
            return 1
        else:
            logger.info("✅ Validation completed successfully!")
            return 0

    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error during validation: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
