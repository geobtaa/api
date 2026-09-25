"""Generate safe collection counts from private preserved monthly archives."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from app.services.analytics_reporting.collection_searches import collection_searches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    documents = []
    sources = []
    for path in args.archives:
        payload = gzip.decompress(path.read_bytes())
        document = json.loads(payload)
        documents.append(document)
        sources.append({"month": document["month"], "sha256": hashlib.sha256(payload).hexdigest()})
    result = {
        "sources": sorted(sources, key=lambda source: source["month"]),
        "method": (
            "Preserved collection-filter search counts, including exclusions and legacy controls; "
            "each search counts once per collection. Collections may overlap."
        ),
        "collections": collection_searches(documents),
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
