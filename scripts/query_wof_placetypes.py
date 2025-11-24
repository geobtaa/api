#!/usr/bin/env python3
"""Query WOF placetypes from database to understand what's available."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from sqlalchemy import func, select

from db.database import database
from db.models import gazetteer_wof_spr

load_dotenv()


async def main():
    """Query distinct placetypes and their counts."""
    await database.connect()
    
    try:
        # Get distinct placetypes with counts
        query = (
            select(
                gazetteer_wof_spr.c.placetype,
                func.count().label("count")
            )
            .group_by(gazetteer_wof_spr.c.placetype)
            .order_by(func.count().desc())
        )
        
        results = await database.fetch_all(query)
        
        print("Who's On First Placetypes:")
        print("=" * 60)
        print(f"{'Placetype':<30} {'Count':>15}")
        print("-" * 60)
        
        total = 0
        for row in results:
            placetype = row["placetype"] or "(null)"
            count = row["count"]
            total += count
            print(f"{placetype:<30} {count:>15,}")
        
        print("-" * 60)
        print(f"{'TOTAL':<30} {total:>15,}")
        print()
        
        # Also check for "Duluth" specifically to see what placetypes it has
        print("\nDuluth placetypes:")
        print("=" * 60)
        duluth_query = (
            select(
                gazetteer_wof_spr.c.placetype,
                gazetteer_wof_spr.c.country,
                gazetteer_wof_spr.c.wok_id,
                func.count().label("count")
            )
            .where(gazetteer_wof_spr.c.name.ilike("%Duluth%"))
            .group_by(
                gazetteer_wof_spr.c.placetype,
                gazetteer_wof_spr.c.country,
                gazetteer_wof_spr.c.wok_id
            )
            .order_by(gazetteer_wof_spr.c.placetype)
        )
        
        duluth_results = await database.fetch_all(duluth_query)
        print(f"{'Placetype':<20} {'Country':<10} {'WOK ID':<15} {'Count':>10}")
        print("-" * 60)
        for row in duluth_results:
            print(
                f"{row['placetype'] or '(null)':<20} "
                f"{row['country'] or '(null)':<10} "
                f"{row['wok_id']:<15} "
                f"{row['count']:>10}"
            )
        
    finally:
        await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

