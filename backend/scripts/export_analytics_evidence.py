"""Add screened evidence to existing snapshots without changing report revisions."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analytics_reporting.storage import canonical, checksum  # noqa: E402
from scripts.export_analytics_snapshots import load_archives, write_evidence  # noqa: E402


def export_evidence(directory, check=False, archives=None):
    documents = load_archives(archives) if archives is not None else None
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    for entry in manifest["periods"]:
        folder = directory / entry["id"] / entry["revision"]
        report = json.loads((folder / "report.json").read_bytes())
        if (
            report["revision"] != entry["revision"]
            or report["period"] != entry["id"]
            or checksum(report) != entry["previewChecksum"]
            or report["start"] != entry["start"]
            or report["endExclusive"] != entry["endExclusive"]
            or report["complete"] != entry["complete"]
        ):
            raise ValueError("Manifest does not match report")
        if check:
            # Recompute checks and compare every packet byte before accepting existing evidence.
            with tempfile.TemporaryDirectory() as temp:
                candidate = Path(temp)
                pointer = write_evidence(report, candidate, documents)
                if pointer != entry.get("evidence"):
                    raise ValueError(
                        "Evidence metadata differs; archive-backed packets require original inputs"
                    )
                for path in candidate.iterdir():
                    if path.read_bytes() != (folder / path.name).read_bytes():
                        raise ValueError("Evidence packet differs from reproducible result")
        else:
            if (
                documents is None
                and entry.get("evidence", {}).get("preservedInputReplay") == "passed"
            ):
                raise ValueError(
                    "Do not replace archive-backed evidence without its original inputs"
                )
            entry["evidence"] = write_evidence(report, folder, documents)
        replay = "verified" if documents is not None else "not verified"
        print(f"{entry['id']}: revision and daily totals verified; preserved-input replay {replay}")
    if not check:
        pending = manifest_path.with_suffix(".json.pending")
        pending.write_bytes(canonical(manifest))
        pending.replace(manifest_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--archives", type=Path, nargs="+")
    args = parser.parse_args()
    export_evidence(args.directory, args.check, args.archives)
