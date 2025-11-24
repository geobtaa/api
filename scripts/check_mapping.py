#!/usr/bin/env python3
"""Check actual Elasticsearch mapping for geo fields."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from app.elasticsearch.client import es

load_dotenv()

async def main():
    mapping = await es.indices.get_mapping(index="btaa_geospatial_api")
    props = mapping["btaa_geospatial_api"]["mappings"]["properties"]
    
    print("geo_country:")
    print(json.dumps(props.get("geo_country", {}), indent=2))
    print("\ngeo_region:")
    print(json.dumps(props.get("geo_region", {}), indent=2))
    print("\ngeo_county:")
    print(json.dumps(props.get("geo_county", {}), indent=2))
    
    await es.close()

if __name__ == "__main__":
    asyncio.run(main())

