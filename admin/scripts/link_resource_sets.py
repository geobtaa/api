"""Replay reviewed local Resource-to-Set mappings through protected commands.

The manifest pins current Source membership, Resource version/code, origin Set,
and explicit target Set. Dry run is the default. No identities are inferred.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid4, uuid5

from local_admin_api import Api, ApiError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.url_ids import encode_id


def validate(plan):
    if plan.get("schema_version") != 3:
        raise ValueError("Expected Set mapping manifest schema_version 3")
    sets = {}
    for row in plan["sets"]:
        identity = row["set_id"]
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identity):
            raise ValueError("Invalid Set ID")
        if identity in sets:
            raise ValueError("Duplicate Set")
        if row["legacy_code"] is not None and not isinstance(row["legacy_code"], str):
            raise ValueError("Expected legacy code must be a string or null")
        if type(row["lock_version"]) is not int or row["lock_version"] < 1:
            raise ValueError("Invalid Set version")
        if not isinstance(row["source_id"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", row["source_id"]
        ):
            raise ValueError("Invalid Set Source ID")
        sets[identity] = row
    assignments = {}
    for row in plan["assignments"]:
        if not isinstance(row["id"], str) or not row["id"] or row["id"] in assignments:
            raise ValueError("Invalid or duplicate Resource ID")
        for key in ("source_set_id", "target_set_id"):
            if row[key] not in sets:
                raise ValueError("Every origin and target Set needs an explicit definition")
        if row["source_set_id"] == row["target_set_id"]:
            raise ValueError("Origin and target Set must differ")
        if type(row["resource_version"]) is not int or row["resource_version"] < 1:
            raise ValueError("Invalid Resource version")
        if row["source_id"] != sets[row["source_set_id"]]["source_id"]:
            raise ValueError("Expected Source ID must match the origin Set")
        if row["expected_code"] is not None and not isinstance(row["expected_code"], str):
            raise ValueError("Expected legacy code must be a string or null")
        if not isinstance(row["reason"], str) or not 1 <= len(row["reason"].strip()) <= 1000:
            raise ValueError("Every assignment requires a reason of 1–1000 characters")
        assignments[row["id"]] = row
    if not assignments:
        raise ValueError("Empty assignment manifest")
    return sets, assignments


def classify(current, assignment, sets):
    if (
        current["source_id"]
        != (
            sets[assignment["target_set_id"]]["source_id"]
            if current["set_id"] == assignment["target_set_id"]
            else assignment["source_id"]
        )
        or current["b1g_code_s"] != assignment["expected_code"]
    ):
        return "changed_source_or_code"
    if current["set_id"] == assignment["target_set_id"]:
        return "already_assigned"
    if current["set_id"] != assignment["source_set_id"]:
        return "changed_set"
    if current["lock_version"] != assignment["resource_version"]:
        return "stale_version"
    return "candidate"


def command(assignment):
    return {
        key: assignment[key]
        for key in ("source_set_id", "target_set_id", "resource_version", "reason")
    } | {"confirmed": True}


def run(api, plan, output, *, apply=False):
    sets, assignments = validate(plan)
    output.mkdir(parents=True, exist_ok=False)
    counts = Counter()
    summary = {
        "apply": apply,
        "complete": False,
        "counts": counts,
        "manifest_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
    }
    try:
        for identity, expected in sets.items():
            current = api.request("/sets/" + identity)
            if (
                current["source_id"] != expected["source_id"]
                or current["legacy_code"] != expected["legacy_code"]
                or current["lock_version"] != expected["lock_version"]
                or current["status"] == "retired"
            ):
                raise ValueError(f"Set changed or retired: {identity}")
        pending, found, after = [], set(), None
        with (output / "preflight.jsonl").open("w") as log:
            while True:
                page = api.request(
                    "/resources/source-candidates?"
                    + urlencode({"limit": 500, **({"after": after} if after else {})})
                )
                for current in page["items"]:
                    identity = current["id"]
                    if identity not in assignments:
                        continue
                    if identity in found:
                        raise ValueError("Duplicate Resource in API scan")
                    found.add(identity)
                    assignment = assignments[identity]
                    outcome = classify(current, assignment, sets)
                    log.write(json.dumps({**assignment, "outcome": outcome}) + "\n")
                    if outcome == "candidate":
                        pending.append(assignment)
                    else:
                        counts[outcome] += 1
                cursor = page["next_cursor"]
                if cursor is None:
                    break
                if not page["items"] or cursor == after or cursor != page["items"][-1]["id"]:
                    raise ValueError("Resource pagination did not advance")
                after = cursor
        summary["missing_resource_ids"] = sorted(assignments.keys() - found)
        if summary["missing_resource_ids"] or any(
            count and key != "already_assigned" for key, count in counts.items()
        ):
            raise ValueError("Set preflight failed; inspect the run reports")
        print(json.dumps({"candidates": len(pending), "counts": counts}), flush=True)
        if not apply:
            counts["would_assign"] = len(pending)
        else:
            with (output / "outcomes.jsonl").open("w") as log:
                for number, assignment in enumerate(pending, 1):
                    path = "/resources/" + encode_id(assignment["id"]) + "/set"
                    body = command(assignment)
                    key = uuid5(
                        NAMESPACE_URL,
                        api.base + path + json.dumps(body, sort_keys=True),
                    )
                    try:
                        result = api.request(path, body, key, method="PUT")
                        if result != {
                            "resource_id": assignment["id"],
                            "source_id": sets[assignment["target_set_id"]]["source_id"],
                            "set_id": assignment["target_set_id"],
                            "lock_version": assignment["resource_version"] + 1,
                        }:
                            raise ValueError(
                                "Association response did not match the requested move"
                            )
                    except (ApiError, ValueError) as exc:
                        counts["failed"] += 1
                        log.write(
                            json.dumps(
                                {
                                    **assignment,
                                    "outcome": "failed",
                                    "error": str(exc),
                                    "idempotency_key": str(key),
                                }
                            )
                            + "\n"
                        )
                        log.flush()
                        raise
                    counts["assigned"] += 1
                    log.write(
                        json.dumps(
                            {
                                **assignment,
                                "outcome": "assigned",
                                "idempotency_key": str(key),
                                "result": result,
                            }
                        )
                        + "\n"
                    )
                    log.flush()
                    if number % 250 == 0:
                        print(
                            json.dumps({"processed": number, "counts": counts}),
                            flush=True,
                        )
        summary["complete"] = True
        return summary
    finally:
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--cookie-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        api = Api(args.api, args.cookie_file.read_text().strip() if args.cookie_file else None)
        plan = json.loads(args.manifest.read_text())
        name = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        output = args.output / name
        print(f"Set mapping report: {output}", flush=True)
        print(json.dumps(run(api, plan, output, apply=args.apply), indent=2))
        return 0
    except (ApiError, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Set mapping stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
