#!/usr/bin/env python3
"""
Elasticsearch Health Check Script

This script checks the health and status of Elasticsearch, including:
- Connection status
- Cluster health
- Index existence and document counts
- Index mapping verification
- Common issues and recommendations

Can be run locally or remotely via Kamal:
  python scripts/check_elasticsearch_health.py
  kamal app exec "python scripts/check_elasticsearch_health.py"
"""

import asyncio
import os
import sys
from typing import Dict, Any

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import ConnectionError, NotFoundError

# Load environment variables
load_dotenv()

# Use ELASTICSEARCH_URL from environment or default
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

# Add project root to path for database imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


async def check_elasticsearch_health() -> Dict[str, Any]:
    """Perform comprehensive Elasticsearch health check."""
    results = {
        "connected": False,
        "cluster_info": None,
        "cluster_health": None,
        "index_exists": False,
        "index_stats": None,
        "index_mapping": None,
        "issues": [],
        "recommendations": [],
    }

    print_header("Elasticsearch Health Check")
    print_info(f"Connecting to: {ELASTICSEARCH_URL}")
    print_info(f"Checking index: {INDEX_NAME}\n")

    client = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=30,
        retry_on_timeout=True,
        max_retries=3,
    )

    try:
        # Check 1: Connection
        print_header("1. Connection Test")
        try:
            info = await client.info()
            results["connected"] = True
            results["cluster_info"] = info
            print_success("Successfully connected to Elasticsearch")
            print(f"   Cluster: {info['cluster_name']}")
            print(f"   Version: {info['version']['number']}")
            print(f"   Lucene: {info['version']['lucene_version']}")
        except ConnectionError as e:
            results["issues"].append("Cannot connect to Elasticsearch")
            print_error(f"Cannot connect to Elasticsearch: {str(e)}")
            print_warning("Check if Elasticsearch is running and accessible")
            print_warning(f"URL: {ELASTICSEARCH_URL}")
            await client.close()
            return results
        except Exception as e:
            results["issues"].append(f"Connection error: {str(e)}")
            print_error(f"Unexpected error: {str(e)}")
            await client.close()
            return results

        # Check 2: Cluster Health
        print_header("2. Cluster Health")
        try:
            health = await client.cluster.health()
            results["cluster_health"] = health
            status = health["status"]
            status_colors = {
                "green": Colors.GREEN,
                "yellow": Colors.YELLOW,
                "red": Colors.RED,
            }
            color = status_colors.get(status, Colors.RESET)
            print(f"   Status: {color}{status.upper()}{Colors.RESET}")
            print(f"   Active Shards: {health['active_shards']}")
            print(f"   Relocating Shards: {health['relocating_shards']}")
            print(f"   Initializing Shards: {health['initializing_shards']}")
            print(f"   Unassigned Shards: {health['unassigned_shards']}")
            print(f"   Number of Nodes: {health['number_of_nodes']}")
            print(f"   Number of Data Nodes: {health['number_of_data_nodes']}")

            if status == "red":
                results["issues"].append("Cluster status is RED - critical issues")
                print_error("Cluster is in RED state - immediate action required!")
            elif status == "yellow":
                results["issues"].append("Cluster status is YELLOW - degraded")
                print_warning("Cluster is in YELLOW state - may indicate issues")
            else:
                print_success("Cluster is healthy (GREEN)")
        except Exception as e:
            results["issues"].append(f"Failed to get cluster health: {str(e)}")
            print_error(f"Error getting cluster health: {str(e)}")

        # Check 3: Index Existence
        print_header("3. Index Check")
        try:
            exists = await client.indices.exists(index=INDEX_NAME)
            results["index_exists"] = exists
            if exists:
                print_success(f"Index '{INDEX_NAME}' exists")
            else:
                results["issues"].append(f"Index '{INDEX_NAME}' does not exist")
                print_error(f"Index '{INDEX_NAME}' does not exist")
                print_warning("The index needs to be created before data can be indexed")
                results["recommendations"].append(
                    f"Create the index '{INDEX_NAME}' - it will be auto-created on first index operation"
                )
        except Exception as e:
            results["issues"].append(f"Error checking index existence: {str(e)}")
            print_error(f"Error checking index: {str(e)}")

        # Check 4: Index Stats (if index exists)
        if results["index_exists"]:
            print_header("4. Index Statistics")
            try:
                stats = await client.indices.stats(index=INDEX_NAME)
                index_stats = stats["indices"][INDEX_NAME]
                results["index_stats"] = index_stats

                doc_count = index_stats["total"]["docs"]["count"]
                size_bytes = index_stats["total"]["store"]["size_in_bytes"]
                size_mb = size_bytes / (1024 * 1024)

                print(f"   Document Count: {doc_count:,}")
                print(f"   Index Size: {size_mb:.2f} MB ({size_bytes:,} bytes)")
                print(f"   Deleted Documents: {index_stats['total']['docs']['deleted']:,}")

                if doc_count == 0:
                    results["issues"].append("Index exists but contains no documents")
                    print_warning("Index is empty - no documents indexed")
                    results["recommendations"].append(
                        "Run indexing script to populate the index: python scripts/run_index.py"
                    )
                else:
                    print_success(f"Index contains {doc_count:,} documents")

                # Check for deleted documents (might indicate issues)
                deleted = index_stats["total"]["docs"]["deleted"]
                if deleted > 0:
                    print_warning(f"Found {deleted:,} deleted documents (may need to optimize index)")

            except NotFoundError:
                print_error("Index stats not available")
            except Exception as e:
                results["issues"].append(f"Error getting index stats: {str(e)}")
                print_error(f"Error getting index stats: {str(e)}")

            # Check 5: Index Mapping
            print_header("5. Index Mapping")
            try:
                mapping = await client.indices.get_mapping(index=INDEX_NAME)
                results["index_mapping"] = mapping[INDEX_NAME]
                properties = mapping[INDEX_NAME].get("mappings", {}).get("properties", {})
                print(f"   Mapped Fields: {len(properties)}")

                # Check for some expected fields
                expected_fields = [
                    "dct_title_s",
                    "gbl_resourceClass_sm",
                    "dcat_centroid",
                    "locn_geometry",
                ]
                missing_fields = []
                for field in expected_fields:
                    if field not in properties:
                        missing_fields.append(field)

                if missing_fields:
                    print_warning(f"Some expected fields missing: {', '.join(missing_fields)}")
                else:
                    print_success("Core expected fields are mapped")

            except Exception as e:
                results["issues"].append(f"Error getting index mapping: {str(e)}")
                print_error(f"Error getting index mapping: {str(e)}")

            # Check 6: Database vs Elasticsearch Count Comparison
            print_header("6. Data Synchronization Check")
            try:
                from db.database import database

                await database.connect()
                
                # Get DB count based on published_only setting
                published_only = os.getenv("PUBLISHED_ONLY", "1").strip().lower() in {"1", "true", "t", "yes", "y"}
                use_b1g_pub_state = os.getenv("USE_B1G_PUBLICATION_STATE", "0").strip().lower() in {"1", "true", "t", "yes", "y"}
                
                if published_only:
                    if use_b1g_pub_state:
                        db_count_sql = (
                            "SELECT COUNT(*) FROM resources WHERE "
                            "coalesce(b1g_publication_state_s, '') = 'published'"
                        )
                    else:
                        db_count_sql = (
                            "SELECT COUNT(*) FROM resources WHERE publication_state = 'published'"
                        )
                else:
                    db_count_sql = "SELECT COUNT(*) FROM resources"
                
                db_result = await database.fetch_one(db_count_sql)
                db_count = int(db_result[0]) if db_result else 0
                
                await database.disconnect()
                
                es_count = index_stats["total"]["docs"]["count"]
                remaining = max(0, db_count - es_count)
                progress_pct = (es_count / db_count * 100) if db_count > 0 else 0
                
                print(f"   Database count: {db_count:,}")
                print(f"   Elasticsearch count: {es_count:,}")
                print(f"   Remaining: {remaining:,}")
                
                if db_count == 0:
                    print_warning("Database contains no resources")
                elif es_count == 0:
                    print_error("Elasticsearch index is empty - reindexing needed")
                    results["issues"].append("Index is empty - data needs to be indexed")
                    results["recommendations"].append("Run reindexing script: python scripts/reindex.py")
                elif remaining == 0:
                    print_success(f"Index is fully synchronized ({db_count:,} documents)")
                elif progress_pct >= 95:
                    print_success(f"Index is nearly complete ({progress_pct:.1f}% - {remaining:,} remaining)")
                elif progress_pct >= 50:
                    print_warning(f"Indexing in progress ({progress_pct:.1f}% - {remaining:,} remaining)")
                    results["recommendations"].append(f"Reindexing may be in progress - {remaining:,} documents remaining")
                else:
                    print_warning(f"Index is incomplete ({progress_pct:.1f}% - {remaining:,} remaining)")
                    results["issues"].append(f"Index is incomplete - {remaining:,} documents need to be indexed")
                    results["recommendations"].append("Run reindexing script: python scripts/reindex.py")
                
                results["db_count"] = db_count
                results["es_count"] = es_count
                results["sync_progress"] = progress_pct
                
            except Exception as e:
                print_warning(f"Could not compare DB vs ES counts: {str(e)}")
                # Don't add to issues since DB connection might not be available in all environments

        # Summary
        print_header("Summary")
        if results["issues"]:
            print_error(f"Found {len(results['issues'])} issue(s):")
            for issue in results["issues"]:
                print(f"   • {issue}")
        else:
            print_success("No issues detected!")

        if results["recommendations"]:
            print_warning(f"Recommendations ({len(results['recommendations'])}):")
            for rec in results["recommendations"]:
                print(f"   • {rec}")

        # Final status
        print_header("Overall Status")
        if not results["connected"]:
            print_error("Elasticsearch is NOT reachable")
            print_info("Check if Elasticsearch container is running:")
            print_info("  kamal accessory details elasticsearch")
            print_info("  kamal accessory logs elasticsearch")
        elif results["cluster_health"] and results["cluster_health"]["status"] == "red":
            print_error("Elasticsearch cluster is in RED state")
            print_info("Check cluster logs and disk space")
        elif not results["index_exists"]:
            print_warning("Index does not exist - will be created on first index operation")
        elif results["index_stats"] and results["index_stats"]["total"]["docs"]["count"] == 0:
            print_warning("Index exists but is empty - no data available for search")
            print_info("This is why the API shows no data!")
        else:
            print_success("Elasticsearch is healthy and ready")

    except Exception as e:
        print_error(f"Unexpected error during health check: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

    return results


async def main():
    """Main entry point."""
    results = await check_elasticsearch_health()

    # Exit with appropriate code
    if results["issues"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

