from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stats_for_run(run: Dict[str, Any]) -> Dict[str, Any]:
    stats = run.get("bridge_stats_json") or {}
    if isinstance(stats, dict):
        return stats
    if isinstance(stats, str):
        try:
            parsed = json.loads(stats)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _scope_for_stats(stats: Dict[str, Any]) -> str:
    if stats.get("scope") == "batched_full":
        resource_scope = str(stats.get("resource_scope") or "all").strip() or "all"
        return f"batched:{resource_scope}"
    resource_id = (stats.get("resource_id") or "").strip()
    if resource_id:
        return f"single:{resource_id}"
    if stats.get("changed_since"):
        return "delta"
    return "full"


def _is_successful_full_run(run: Dict[str, Any]) -> bool:
    status = (run.get("bridge_status") or "").lower()
    if status != "success":
        return False
    stats = _stats_for_run(run)
    return _scope_for_stats(stats) == "full" and (_coerce_int(stats.get("processed")) or 0) > 0


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _format_rate(rate: Optional[float]) -> str:
    if rate is None or rate <= 0:
        return "unknown"
    if rate >= 10:
        return f"{rate:.0f}/s"
    if rate >= 1:
        return f"{rate:.1f}/s"
    return f"{rate:.2f}/s"


def _truncate_error(value: Any, max_chars: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _estimate_total(
    run: Dict[str, Any],
    runs: Sequence[Dict[str, Any]],
) -> Tuple[Optional[int], Optional[str]]:
    stats = _stats_for_run(run)
    estimated_total = _coerce_int(stats.get("estimated_total"))
    estimated_total_source = stats.get("estimated_total_source")
    if estimated_total and estimated_total > 0:
        return estimated_total, str(estimated_total_source or "run_stats")

    if _scope_for_stats(stats) != "full":
        if (stats.get("resource_id") or "").strip():
            return 1, "requested_resource"
        return None, None

    for candidate in runs:
        if candidate == run:
            continue
        if not _is_successful_full_run(candidate):
            continue
        candidate_total = _coerce_int(_stats_for_run(candidate).get("processed"))
        if candidate_total and candidate_total > 0:
            return candidate_total, "last_successful_full_run"
    return None, None


def _elapsed_seconds(
    run: Dict[str, Any],
    now: Optional[datetime],
) -> Optional[float]:
    started_at = _parse_datetime(run.get("bridge_started_at"))
    completed_at = _parse_datetime(run.get("bridge_completed_at"))
    if not started_at:
        return None
    if completed_at:
        return max(0.0, (completed_at - started_at).total_seconds())
    reference_now = now or datetime.now(timezone.utc)
    return max(0.0, (reference_now - started_at).total_seconds())


def summarize_run(
    run: Dict[str, Any],
    *,
    runs: Optional[Sequence[Dict[str, Any]]] = None,
    label: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    if not run:
        prefix = f"{label}: " if label else ""
        return prefix + "(none)"

    stats = _stats_for_run(run)
    scope = _scope_for_stats(stats)
    status = str(run.get("bridge_status") or "")
    stage = stats.get("stage") or ("complete" if status.lower() == "success" else "import")
    processed = _coerce_int(stats.get("processed")) or 0
    imported = _coerce_int(stats.get("imported")) or 0
    skipped = _coerce_int(stats.get("skipped")) or 0
    errors = _coerce_int(stats.get("errors")) or 0
    pages = _coerce_int(stats.get("pages_processed"))
    last_page_size = _coerce_int(stats.get("last_page_size"))
    matched_page_size = _coerce_int(stats.get("matched_page_size"))
    missing = _coerce_int(stats.get("missing"))
    retired = _coerce_int(stats.get("retired"))
    batches_completed = _coerce_int(stats.get("batches_completed"))
    batches_failed = _coerce_int(stats.get("batches_failed"))
    batches_queued = _coerce_int(stats.get("batches_queued"))
    total_batches = _coerce_int(stats.get("total_batches"))
    started_at = run.get("bridge_started_at")
    elapsed_seconds = _elapsed_seconds(run, now)
    rate = (
        (processed / elapsed_seconds)
        if elapsed_seconds is not None and elapsed_seconds > 0 and processed > 0
        else None
    )

    estimated_total, estimated_total_source = _estimate_total(run, runs or [run])
    progress_pct: Optional[float] = None
    eta_seconds: Optional[float] = None
    if (
        status.lower() == "running"
        and (scope == "full" or scope.startswith("batched:"))
        and estimated_total
        and estimated_total > 0
        and processed > 0
    ):
        progress_pct = min(999.0, (processed / estimated_total) * 100.0)
        remaining = estimated_total - processed
        if remaining > 0 and rate and rate > 0:
            eta_seconds = remaining / rate

    parts = [
        f"bridge_id={run.get('bridge_id')}",
        f"status={status or 'unknown'}",
        f"trigger={run.get('bridge_trigger') or 'unknown'}",
        f"scope={scope}",
        f"stage={stage}",
    ]
    if started_at:
        parts.append(f"started_at={started_at}")
    if elapsed_seconds is not None:
        elapsed_label = "elapsed" if status.lower() == "running" else "duration"
        parts.append(f"{elapsed_label}={_format_duration(elapsed_seconds)}")
    parts.extend(
        [
            f"processed={processed}",
            f"imported={imported}",
            f"skipped={skipped}",
            f"errors={errors}",
        ]
    )
    if pages is not None:
        parts.append(f"pages={pages}")
    if last_page_size is not None:
        parts.append(f"last_page={last_page_size}")
    if matched_page_size is not None and matched_page_size != last_page_size:
        parts.append(f"matched_page={matched_page_size}")
    if rate is not None:
        parts.append(f"rate={_format_rate(rate)}")
    if missing is not None:
        parts.append(f"missing={missing}")
    if retired is not None:
        parts.append(f"retired={retired}")
    if total_batches is not None:
        batches_done = (batches_completed or 0) + (batches_failed or 0)
        parts.append(f"batches={batches_done}/{total_batches}")
        if batches_queued is not None:
            parts.append(f"queued={batches_queued}/{total_batches}")
    if batches_failed:
        parts.append(f"batch_failures={batches_failed}")
    if estimated_total is not None and estimated_total > 0:
        parts.append(f"est_total~={estimated_total}")
    if progress_pct is not None:
        parts.append(f"progress~={progress_pct:.1f}%")
    if eta_seconds is not None:
        parts.append(f"eta~={_format_duration(eta_seconds)}")
    if estimated_total_source:
        parts.append(f"estimate_source={estimated_total_source}")

    error_text = _truncate_error(run.get("bridge_error"))
    if error_text:
        parts.append(f"error={error_text}")

    prefix = ""
    if label:
        prefix = f"{label}: "
        if len(label) < 7:
            prefix = prefix.ljust(8)
    return prefix + " ".join(parts)


def _select_runs_for_current_last(
    runs: Sequence[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    if not runs:
        return [("current", {})]

    current = next(
        (run for run in runs if (run.get("bridge_status") or "").lower() == "running"),
        runs[0],
    )
    last = next((run for run in runs if run != current), {})
    selected = [("current", current)]
    if last:
        selected.append(("last", last))
    return selected


def _select_runs_for_current_only(
    runs: Sequence[Dict[str, Any]],
) -> List[Tuple[str, Dict[str, Any]]]:
    if not runs:
        return [("current", {})]

    current = next(
        (run for run in runs if (run.get("bridge_status") or "").lower() == "running"),
        runs[0],
    )
    return [("current", current)]


def render_payload(
    payload: Dict[str, Any],
    *,
    current_only: bool = False,
    current_last: bool = False,
    now: Optional[datetime] = None,
) -> str:
    if isinstance(payload.get("run"), dict):
        run = payload["run"]
        runs = [run]
        return summarize_run(run, runs=runs, now=now)

    runs = payload.get("runs") or []
    if not isinstance(runs, list):
        raise ValueError("Expected payload with `run` or `runs`")

    if current_only:
        return "\n".join(
            summarize_run(run, runs=runs, label=label, now=now)
            for label, run in _select_runs_for_current_only(runs)
        )

    if current_last:
        return "\n".join(
            summarize_run(run, runs=runs, label=label, now=now)
            for label, run in _select_runs_for_current_last(runs)
        )

    if not runs:
        return "(none)"
    return "\n".join(summarize_run(run, runs=runs, now=now) for run in runs)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render bridge sync status JSON as a summary.")
    parser.add_argument(
        "--current-only",
        action="store_true",
        help="Only render the current running run (or the most recent run if none are running).",
    )
    parser.add_argument(
        "--current-last",
        action="store_true",
        help="Only render the current running run and the most recent other run.",
    )
    args = parser.parse_args(argv)

    payload = json.load(sys.stdin)
    print(
        render_payload(
            payload,
            current_only=args.current_only,
            current_last=args.current_last,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
