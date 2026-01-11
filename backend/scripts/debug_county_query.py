#!/usr/bin/env python3
"""
Debug script to investigate the county query issue.
"""

import asyncio
import os
import sys

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def debug_county_query():
    """Debug the county query to see why we're getting so few results."""

    # Database connection
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:2345/btaa_ogm_api"
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session() as session:
            # Test with the same bbox as the working resource
            xmin, ymin, xmax, ymax = -97.017, 39.867, -87.017, 48.867

            print(f"Testing with bbox: xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}")
            print(f"Centroid: lon={(xmin + xmax) / 2}, lat={(ymin + ymax) / 2}")

            # First, let's check what counties we have in the overlapping states
            print("\n=== Checking counties in overlapping states ===")
            overlapping_states = [
                "Minnesota",
                "Wisconsin",
                "Iowa",
                "Illinois",
                "Michigan",
                "Missouri",
                "Nebraska",
                "South Dakota",
                "Indiana",
                "North Dakota",
                "Kansas",
            ]

            for state in overlapping_states[:3]:  # Check first 3 states
                result = await session.execute(
                    text("""
                    SELECT COUNT(*) as count
                    FROM gazetteer_wof_spr wof
                    JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
                    WHERE wof.placetype = 'county'
                      AND wof.country = 'US'
                      AND wof.name = :state_name
                      AND geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                """),
                    {"state_name": state},
                )
                count = result.fetchone()
                print(f"Counties in {state}: {count[0] if count else 0}")

            # Check what counties intersect with the bbox (without threshold)
            print("\n=== Counties that intersect with bbox (no threshold) ===")
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            )
            SELECT wof.name, wof.parent_id
            FROM gazetteer_wof_spr wof
            JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
            CROSS JOIN bbox
            WHERE wof.placetype = 'county'
              AND wof.country = 'US'
              AND geojson.source = 'quattroshapes'
              AND geojson.alt_label IS NULL
              AND ST_Intersects(ST_GeomFromGeoJSON(geojson.body::jsonb->>'geometry'), bbox.geom)
            ORDER BY wof.name
            LIMIT 20;
            """

            result = await session.execute(
                text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
            )
            rows = result.fetchall()
            print(f"Counties that intersect (first 20): {len(rows)}")
            for row in rows:
                print(f"  {row[0]} (parent_id: {row[1]})")

            # Check the overlap areas for these counties
            print("\n=== County overlap areas ===")
            query = """
            WITH bbox AS (
                SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
            ),
            bbox_area AS (
                SELECT ST_Area(bbox.geom::geography) AS total_area
                FROM bbox
            ),
            overlap_areas AS (
                SELECT wof.name,
                       ST_Area(
                           ST_Intersection(
                               ST_GeomFromGeoJSON(geojson.body::jsonb->>'geometry'),
                               bbox.geom
                           )::geography
                       ) AS overlap_area
                FROM gazetteer_wof_spr wof
                JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
                CROSS JOIN bbox
                WHERE wof.placetype = 'county'
                  AND wof.country = 'US'
                  AND geojson.source = 'quattroshapes'
                  AND geojson.alt_label IS NULL
                  AND ST_Intersects(
                      ST_GeomFromGeoJSON(geojson.body::jsonb->>'geometry'),
                      bbox.geom
                  )
            )
            SELECT o.name, o.overlap_area, ba.total_area,
                   o.overlap_area / ba.total_area as overlap_ratio
            FROM overlap_areas o, bbox_area ba
            ORDER BY o.overlap_area DESC
            LIMIT 20;
            """

            result = await session.execute(
                text(query), {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}
            )
            rows = result.fetchall()
            print("County overlap areas (first 20):")
            for row in rows:
                print(f"  {row[0]}: {row[3]:.4f} ({row[3] * 100:.2f}%)")

            # Check how many counties meet different thresholds
            print("\n=== Counties meeting different thresholds ===")
            thresholds = [0.01, 0.005, 0.002, 0.001]
            for threshold in thresholds:
                query = """
                WITH bbox AS (
                    SELECT ST_SetSRID(ST_MakeEnvelope(:xmin, :ymin, :xmax, :ymax), 4326) AS geom
                ),
                bbox_area AS (
                    SELECT ST_Area(bbox.geom::geography) AS total_area
                    FROM bbox
                ),
                overlap_areas AS (
                    SELECT wof.name,
                           ST_Area(
                               ST_Intersection(
                                   ST_GeomFromGeoJSON(geojson.body::jsonb->>'geometry'),
                                   bbox.geom
                               )::geography
                           ) AS overlap_area
                    FROM gazetteer_wof_spr wof
                    JOIN gazetteer_wof_geojson geojson ON wof.wok_id = geojson.wok_id
                    CROSS JOIN bbox
                    WHERE wof.placetype = 'county'
                      AND wof.country = 'US'
                      AND geojson.source = 'quattroshapes'
                      AND geojson.alt_label IS NULL
                      AND ST_Intersects(
                          ST_GeomFromGeoJSON(geojson.body::jsonb->>'geometry'),
                          bbox.geom
                      )
                )
                SELECT COUNT(*)
                FROM overlap_areas o, bbox_area ba
                WHERE o.overlap_area / ba.total_area >= :threshold;
                """

                result = await session.execute(
                    text(query),
                    {
                        "xmin": xmin,
                        "ymin": ymin,
                        "xmax": xmax,
                        "ymax": ymax,
                        "threshold": threshold,
                    },
                )
                count = result.fetchone()
                print(
                    f"Counties meeting {threshold * 100:.1f}% threshold: {count[0] if count else 0}"
                )

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(debug_county_query())
