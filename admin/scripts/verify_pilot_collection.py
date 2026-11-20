"""Capture or verify public P2-pilot membership without modifying either catalog."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def membership(origin):
    ids = set()
    page = 1
    expected = None
    while True:
        query = urlencode({"q": "P2-pilot", "page": page, "per_page": 100})
        with urlopen(f"{origin.rstrip('/')}/api/v1/search?{query}", timeout=30) as response:
            body = json.load(response)
        meta = body["meta"]
        if expected is None:
            expected = meta["totalCount"]
        rows = [item["id"] for item in body["data"]]
        if (not rows or meta["currentPage"] != page or meta["totalCount"] != expected
                or len(set(rows)) != len(rows) or ids.intersection(rows)):
            raise ValueError("Unstable or empty pilot membership")
        ids.update(rows)
        if page == meta["totalPages"]:
            break
        page += 1
    if len(ids) != expected:
        raise ValueError("Incomplete pilot membership")
    return sorted(ids)


def checksum(ids):
    return hashlib.sha256("\n".join(ids).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    ids = membership(args.origin)
    if args.capture:
        with args.capture.open("x") as stream:
            json.dump({"query": "P2-pilot", "ids": ids, "sha256": checksum(ids)}, stream, indent=2)
    else:
        baseline = json.loads(args.verify.read_text())
        if baseline["sha256"] != checksum(baseline["ids"]):
            raise SystemExit("Invalid baseline checksum")
        missing = set(baseline["ids"]) - set(ids)
        if missing:
            raise SystemExit(f"{len(missing)} missing pilot IDs: {', '.join(sorted(missing))}")
    print(f"{len(ids)} public P2-pilot IDs; SHA-256 {checksum(ids)}")


if __name__ == "__main__":
    main()
