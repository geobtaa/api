"""Create new private archive revisions with refreshed content labels, preserving statistics."""

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.analytics_reporting.archive import validate_document  # noqa: E402
from app.services.analytics_reporting.storage import canonical, checksum  # noqa: E402


def refresh(document, metadata):
    # JSON round-trip leaves the caller's sealed original untouched.
    revised = json.loads(json.dumps(document))
    identifiers = set(document["catalog"])
    identifiers.update(
        row["dimensions"]["resource"]
        for row in document["daily"]
        if row["dimensions"].get("resource")
    )
    for record in metadata["catalog"].values():
        identifiers.update((record.get("attributes") or {}).get("collections") or [])
    for identifier in sorted(identifiers):
        current = metadata["catalog"].get(identifier)
        if current is None:
            continue
        record = revised["catalog"].setdefault(identifier, {"eligible": False})
        record["content"] = current
    revised["contentCatalogCapturedAt"] = metadata["capturedAt"]
    revised["metadataSourceRevision"] = checksum(metadata)
    revised["previousRevision"] = checksum(document)
    revised["generation"] += 1
    return revised


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    metadata = json.loads(gzip.decompress(args.metadata.read_bytes()))
    args.output.mkdir(parents=True, exist_ok=True)
    for path in args.archives:
        document = json.loads(gzip.decompress(path.read_bytes()))
        validate_document(document)
        if checksum(document) != path.name.split("-", 2)[-1].split(".")[0]:
            raise ValueError("Archive checksum mismatch")
        revised = refresh(document, metadata)
        validate_document(revised)
        name = f"{document['month'][:7]}-{checksum(revised)}.json.gz"
        (args.output / name).write_bytes(gzip.compress(canonical(revised), mtime=0))
        print(f"Refreshed {document['month'][:7]} content labels; statistics preserved.")


if __name__ == "__main__":
    main()
