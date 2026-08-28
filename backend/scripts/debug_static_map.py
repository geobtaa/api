#!/usr/bin/env python3
"""
Debug script to test static map generation and diagnose firewall/network issues.

This script tests:
1. Outbound HTTP connectivity to tile servers
2. Static map generation with a test resource
3. Network error handling
"""

import io
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

import staticmaps

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.static_map_service import (  # noqa: E402
    OPENSTREETMAP_TILE_PROVIDER,
    STATIC_MAP_TILE_USER_AGENT,
    StaticMapService,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_tile_server_connectivity():
    """Test if we can reach the configured OpenStreetMap tile server."""
    test_url = OPENSTREETMAP_TILE_PROVIDER.url(1, 0, 0)
    if not test_url:
        logger.error("✗ OpenStreetMap tile provider did not produce a test URL")
        return False
    logger.info(f"Testing connectivity to tile server: {test_url}")

    try:
        req = urllib.request.Request(test_url)
        req.add_header("User-Agent", STATIC_MAP_TILE_USER_AGENT)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            content_length = len(response.read())
            logger.info(
                f"✓ Successfully connected to tile server: HTTP {status}, "
                f"received {content_length} bytes"
            )
            return True
    except urllib.error.URLError as e:
        logger.error(f"✗ Failed to connect to tile server: {e}")
        logger.error("  This suggests outbound HTTP traffic may be blocked by firewall")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error connecting to tile server: {e}")
        return False


def test_static_map_generation():
    """Test static map generation with a sample center and zoom."""
    logger.info("Testing static map generation...")

    try:
        service = StaticMapService()
        context = service._map_context()
        context.set_center(staticmaps.create_latlng(44.9778, -93.2650))
        context.set_zoom(8)
        surface = context.render_cairo(256, 256)
        image_bytes = io.BytesIO()
        surface.write_to_png(image_bytes)

        if image_bytes.tell() > 0:
            logger.info(
                "✓ Successfully rendered an OpenStreetMap static map (%s bytes)",
                image_bytes.tell(),
            )
            return True
        logger.error("✗ Static map rendering produced an empty image")
        return False

    except Exception as e:
        logger.error(f"✗ Error generating static map: {e}", exc_info=True)
        return False


def test_py_staticmaps_import():
    """Test if py-staticmaps can be imported and basic functionality works."""
    logger.info("Testing py-staticmaps import and basic functionality...")

    try:
        import staticmaps

        version = staticmaps.__version__ if hasattr(staticmaps, "__version__") else "unknown"
        logger.info(f"✓ py-staticmaps imported successfully (version: {version})")

        # Try creating a context
        staticmaps.Context()
        logger.info("✓ Created staticmaps.Context()")

        return True
    except ImportError as e:
        logger.error(f"✗ Failed to import py-staticmaps: {e}")
        logger.error("  Install with: pip install py-staticmaps")
        return False
    except Exception as e:
        logger.error(f"✗ Error testing py-staticmaps: {e}")
        return False


def main():
    """Run all diagnostic tests."""
    logger.info("=" * 60)
    logger.info("Static Map Generation Diagnostic Tool")
    logger.info("=" * 60)
    logger.info("")

    results = {}

    # Test 1: Import check
    logger.info("Test 1: Checking py-staticmaps import...")
    results["import"] = test_py_staticmaps_import()
    logger.info("")

    # Test 2: Network connectivity
    logger.info("Test 2: Testing tile server connectivity...")
    results["connectivity"] = test_tile_server_connectivity()
    logger.info("")

    # Test 3: Map generation
    if results["import"]:
        logger.info("Test 3: Testing static map generation...")
        results["generation"] = test_static_map_generation()
        logger.info("")
    else:
        logger.warning("Skipping map generation test (import failed)")
        results["generation"] = False

    # Summary
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"Import check:        {'✓ PASS' if results['import'] else '✗ FAIL'}")
    logger.info(f"Network connectivity: {'✓ PASS' if results['connectivity'] else '✗ FAIL'}")
    logger.info(f"Map generation:       {'✓ PASS' if results['generation'] else '✗ FAIL'}")
    logger.info("")

    if not results["connectivity"]:
        logger.warning("=" * 60)
        logger.warning("NETWORK CONNECTIVITY ISSUE DETECTED")
        logger.warning("=" * 60)
        logger.warning(
            "The tile server connectivity test failed. This suggests that:\n"
            "1. Outbound HTTP traffic may be blocked by a firewall\n"
            "2. The server may not have internet access\n"
            "3. DNS resolution may be failing\n"
            "\n"
            "Solutions:\n"
            "1. Check firewall rules to allow outbound HTTPS traffic\n"
            "2. Verify DNS resolution: nslookup tile.openstreetmap.org\n"
            "3. Test manual connection: curl https://tile.openstreetmap.org/1/0/0.png\n"
            "4. Consider using a proxy server if outbound traffic must be restricted\n"
        )

    if results["connectivity"] and not results["generation"]:
        logger.warning("=" * 60)
        logger.warning("MAP GENERATION ISSUE DETECTED")
        logger.warning("=" * 60)
        logger.warning(
            "Network connectivity works, but map generation failed.\n"
            "Check the error messages above for details.\n"
            "This may be a py-staticmaps configuration issue.\n"
        )

    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
