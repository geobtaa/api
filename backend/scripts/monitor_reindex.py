#!/usr/bin/env python3
"""
Monitor Elasticsearch Reindexing Progress

This script monitors the reindex.py script progress and Elasticsearch health.
It can watch logs, compare DB vs ES counts, and check for issues.

Usage:
    python scripts/monitor_reindex.py [--watch] [--check-only]

Options:
    --watch: Continuously monitor (refresh every 10 seconds)
    --check-only: One-time check without watching logs
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import database

load_dotenv()

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
FAILURE_LOG = os.getenv("FAILURE_LOG", "logs/reindex_failures.log")
PUBLISHED_ONLY = os.getenv("PUBLISHED_ONLY", "1").strip().lower() in {"1", "true", "t", "yes", "y"}
USE_B1G_PUB_STATE = os.getenv("USE_B1G_PUBLICATION_STATE", "0").strip().lower() in {
    "1",
    "true",
    "t",
    "yes",
    "y",
}


class Colors:
    """ANSI color codes."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_section(text: str):
    """Print section divider."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'-' * len(text)}{Colors.RESET}")


async def get_db_count() -> int:
    """Get count of resources from database."""
    try:
        await database.connect()
        if PUBLISHED_ONLY:
            if USE_B1G_PUB_STATE:
                sql = (
                    "SELECT COUNT(*) FROM resources WHERE "
                    "coalesce(b1g_publication_state_s, '') = 'published'"
                )
            else:
                sql = "SELECT COUNT(*) FROM resources WHERE publication_state = 'published'"
        else:
            sql = "SELECT COUNT(*) FROM resources"
        result = await database.fetch_one(sql)
        count = result[0] if result else 0
        await database.disconnect()
        return int(count)
    except Exception as e:
        print(f"{Colors.RED}✗ Error getting DB count: {e}{Colors.RESET}")
        return 0


async def get_es_count(client: AsyncElasticsearch) -> int:
    """Get count of documents in Elasticsearch index."""
    try:
        response = await client.count(index=INDEX_NAME)
        return int(response.get("count", 0))
    except Exception as e:
        print(f"{Colors.RED}✗ Error getting ES count: {e}{Colors.RESET}")
        return 0


async def check_elasticsearch_health(client: AsyncElasticsearch) -> Dict[str, Any]:
    """Check Elasticsearch cluster health."""
    try:
        health = await client.cluster.health()
        return {
            "status": health["status"],
            "active_shards": health["active_shards"],
            "unassigned_shards": health["unassigned_shards"],
            "number_of_nodes": health["number_of_nodes"],
        }
    except Exception as e:
        return {"error": str(e)}


def check_reindex_process() -> Dict[str, Any]:
    """Check if reindex.py is currently running."""
    import subprocess

    try:
        # Check for python process running reindex.py
        result = subprocess.run(
            ["pgrep", "-f", "reindex.py"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            return {"running": True, "pids": [pid for pid in pids if pid]}
        return {"running": False}
    except FileNotFoundError:
        # pgrep not available (Windows?)
        # Try alternative method
        try:
            result = subprocess.run(
                ["ps", "aux"] if os.name != "nt" else ["tasklist"],
                capture_output=True,
                text=True,
            )
            if "reindex.py" in result.stdout:
                return {"running": True}
            return {"running": False}
        except Exception:
            return {"running": None, "error": "Cannot determine process status"}


def get_failure_log_stats() -> Dict[str, Any]:
    """Get statistics from failure log."""
    log_path = Path(FAILURE_LOG)
    if not log_path.exists():
        return {"exists": False, "count": 0}

    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        failure_count = len([line for line in lines if line.strip()])
        return {"exists": True, "count": failure_count, "path": str(log_path)}
    except Exception as e:
        return {"exists": True, "error": str(e)}


def tail_log(log_path: str, lines: int = 20) -> list:
    """Get last N lines from a log file."""
    try:
        path = Path(log_path)
        if not path.exists():
            return []
        with open(path, "r") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception:
        return []


async def get_reindex_status() -> Dict[str, Any]:
    """Get comprehensive reindex status."""
    client = AsyncElasticsearch(
        hosts=[ELASTICSEARCH_URL],
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=30,
        retry_on_timeout=True,
        max_retries=3,
    )

    try:
        # Check ES connection
        await client.info()

        # Get counts
        db_count = await get_db_count()
        es_count = await get_es_count(client)

        # Check health
        health = await check_elasticsearch_health(client)

        # Check process
        process_info = check_reindex_process()

        # Check failures
        failure_stats = get_failure_log_stats()

        # Calculate progress
        progress_pct = (es_count / db_count * 100) if db_count > 0 else 0
        remaining = max(0, db_count - es_count)

        return {
            "db_count": db_count,
            "es_count": es_count,
            "remaining": remaining,
            "progress_pct": progress_pct,
            "health": health,
            "process": process_info,
            "failures": failure_stats,
            "connected": True,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
    finally:
        await client.close()


def format_status(status: Dict[str, Any]) -> str:
    """Format status information for display."""
    output = []

    # Connection status
    if not status.get("connected"):
        output.append(f"{Colors.RED}✗ Cannot connect to Elasticsearch{Colors.RESET}")
        if "error" in status:
            output.append(f"  Error: {status['error']}")
        return "\n".join(output)

    # Progress
    output.append(f"{Colors.BOLD}Progress:{Colors.RESET}")
    output.append(f"  Database count: {status['db_count']:,}")
    output.append(f"  Elasticsearch count: {status['es_count']:,}")
    output.append(f"  Remaining: {status['remaining']:,}")

    progress = status["progress_pct"]
    if progress >= 100:
        color = Colors.GREEN
        symbol = "✓"
    elif progress >= 50:
        color = Colors.YELLOW
        symbol = "→"
    else:
        color = Colors.RED
        symbol = "⚠"

    output.append(f"  {symbol} Progress: {color}{progress:.1f}%{Colors.RESET}")

    # Health
    health = status.get("health", {})
    if "error" in health:
        output.append(f"\n{Colors.RED}✗ Health check error: {health['error']}{Colors.RESET}")
    else:
        health_status = health.get("status", "unknown")
        status_colors = {"green": Colors.GREEN, "yellow": Colors.YELLOW, "red": Colors.RED}
        color = status_colors.get(health_status, Colors.RESET)
        output.append(f"\n{Colors.BOLD}Cluster Health:{Colors.RESET}")
        output.append(f"  Status: {color}{health_status.upper()}{Colors.RESET}")
        output.append(f"  Nodes: {health.get('number_of_nodes', '?')}")
        output.append(f"  Active Shards: {health.get('active_shards', '?')}")
        if health.get("unassigned_shards", 0) > 0:
            output.append(
                f"  {Colors.YELLOW}⚠ Unassigned Shards: {health['unassigned_shards']}{Colors.RESET}"
            )

    # Process status
    process = status.get("process", {})
    if process.get("running"):
        pids = process.get("pids", [])
        pid_str = ", ".join(pids) if pids else "?"
        output.append(f"\n{Colors.GREEN}✓{Colors.RESET} reindex.py is running (PID: {pid_str})")
    elif process.get("running") is False:
        output.append(f"{Colors.YELLOW}⚠{Colors.RESET} reindex.py is not running")
    else:
        output.append(f"{Colors.YELLOW}?{Colors.RESET} Cannot determine if reindex.py is running")

    # Failures
    failures = status.get("failures", {})
    if failures.get("exists"):
        count = failures.get("count", 0)
        if count > 0:
            output.append(
                f"\n{Colors.YELLOW}⚠ Failures logged: {count:,} entries in "
                f"{failures.get('path', FAILURE_LOG)}{Colors.RESET}"
            )
        else:
            output.append(f"{Colors.GREEN}✓{Colors.RESET} No failures logged")

    return "\n".join(output)


async def main():
    """Main monitoring function."""
    parser = argparse.ArgumentParser(description="Monitor Elasticsearch reindexing progress")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously monitor (refresh every 10 seconds)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="One-time check without watching logs",
    )
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                clear_screen()
                print_header(
                    f"Elasticsearch Reindex Monitor - "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                status = await get_reindex_status()
                print(format_status(status))

                # Show recent log entries if available
                log_path = "logs/app.log"
                if Path(log_path).exists():
                    print_section("Recent Log Entries")
                    recent_logs = tail_log(log_path, 10)
                    for line in recent_logs[-5:]:  # Last 5 lines
                        if "reindex" in line.lower() or "index" in line.lower():
                            print(f"  {line.rstrip()}")

                print(f"\n{Colors.CYAN}Refreshing in 10 seconds... (Ctrl+C to stop){Colors.RESET}")
                time.sleep(10)
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Monitoring stopped{Colors.RESET}")
    else:
        print_header("Elasticsearch Reindex Status Check")
        status = await get_reindex_status()
        print(format_status(status))

        if not args.check_only:
            print_section("Recent Activity")
            print("To watch continuously, use: python scripts/monitor_reindex.py --watch")


if __name__ == "__main__":
    asyncio.run(main())
