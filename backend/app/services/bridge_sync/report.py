# ruff: noqa: E501

from __future__ import annotations

import html
import logging
import os
import smtplib
import subprocess
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Iterable, Optional

from app.services.bridge_sync.repository import BridgeSyncRepository
from db.database import database

logger = logging.getLogger(__name__)

BRAND_BLUE = "#003C5B"
ACTIVE_BLUE = "#2563EB"
INK = "#111827"
MUTED = "#4B5563"
LINE = "#D1D5DB"
SOFT = "#F3F4F6"
GOOD = "#047857"
WARN = "#B45309"
BAD = "#B91C1C"
DEFAULT_REPORT_RECIPIENTS = "ewlarson@gmail.com,majew030@umn.edu"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default=%s", name, value, default)
        return default


def _split_recipients(value: str | None) -> list[str]:
    if not value:
        return []
    cleaned = value.replace(";", ",").replace("\n", ",")
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def _allowed_report_destinations() -> set[str]:
    raw = os.getenv("BRIDGE_SYNC_REPORT_DESTINATIONS", "prd")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _current_destination() -> str:
    return (
        os.getenv("KAMAL_DEST")
        or os.getenv("APP_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("RAILS_ENV")
        or ""
    ).strip()


def _destination_allows_report() -> bool:
    allowed = _allowed_report_destinations()
    if "*" in allowed:
        return True
    destination = _current_destination().lower()
    return bool(destination and destination in allowed)


def _stats_for_run(run: dict[str, Any]) -> dict[str, Any]:
    stats = run.get("bridge_stats_json") or {}
    return stats if isinstance(stats, dict) else {}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        dt = value
    elif value:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_datetime(value: Any) -> str:
    dt = _parse_datetime(value)
    if not dt:
        return "Unknown"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_duration(started: Any, completed: Any) -> str:
    start_dt = _parse_datetime(started)
    end_dt = _parse_datetime(completed) or datetime.now(timezone.utc)
    if not start_dt:
        return "Unknown"
    seconds = max(0, int(round((end_dt - start_dt).total_seconds())))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _scope_label(stats: dict[str, Any]) -> str:
    resource_id = str(stats.get("resource_id") or "").strip()
    if resource_id:
        return f"Single resource: {resource_id}"
    if stats.get("changed_since"):
        return "Delta sync"
    return "Full sync"


def _status_color(status: str, stats: dict[str, Any]) -> str:
    status_norm = status.lower()
    if status_norm == "success" and _coerce_int(stats.get("errors")) == 0:
        return GOOD
    if status_norm == "success":
        return WARN
    if status_norm in {"failed", "cancelled"}:
        return BAD
    return WARN


def _status_label(status: str, stats: dict[str, Any]) -> str:
    status_norm = status.lower()
    errors = _coerce_int(stats.get("errors"))
    if status_norm == "success" and errors == 0:
        return "Sync completed cleanly"
    if status_norm == "success":
        return f"Sync completed with {errors:,} importer error{'' if errors == 1 else 's'}"
    if status_norm:
        return f"Sync {status_norm}"
    return "Sync status unknown"


def _html_escape(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _metric(label: str, value: Any, accent: str = BRAND_BLUE) -> str:
    return f"""
      <td style="width:25%; padding:8px;">
        <div style="border:1px solid {LINE}; background:#ffffff; padding:16px 14px;">
          <div style="font-size:11px; line-height:1.3; color:{MUTED}; text-transform:uppercase; font-weight:700;">{_html_escape(label)}</div>
          <div style="margin-top:6px; font-size:28px; line-height:1.05; color:{accent}; font-weight:800;">{_html_escape(value)}</div>
        </div>
      </td>
    """


def _panel(title: str, body: str, accent: str = BRAND_BLUE) -> str:
    return f"""
      <div style="border:1px solid {LINE}; background:#ffffff; margin-top:14px;">
        <div style="border-left:5px solid {accent}; padding:14px 16px 4px;">
          <h2 style="margin:0; font-size:18px; line-height:1.3; color:{INK};">{_html_escape(title)}</h2>
        </div>
        <div style="padding:8px 16px 16px; font-size:14px; line-height:1.55; color:{MUTED};">
          {body}
        </div>
      </div>
    """


def _key_value_rows(items: Iterable[tuple[str, Any]]) -> str:
    rows = []
    for label, value in items:
        rows.append(
            f"""
              <tr>
                <td style="padding:8px 0; color:{MUTED}; width:42%;">{_html_escape(label)}</td>
                <td style="padding:8px 0; color:{INK}; font-weight:700;">{_html_escape(value)}</td>
              </tr>
            """
        )
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'


def _recent_run_rows(runs: list[dict[str, Any]]) -> str:
    rows = []
    for run in runs[:6]:
        stats = _stats_for_run(run)
        status = str(run.get("bridge_status") or "unknown")
        color = _status_color(status, stats)
        rows.append(
            f"""
              <tr>
                <td style="padding:9px 8px; border-top:1px solid {LINE}; color:{INK}; font-weight:700;">#{_html_escape(run.get("bridge_id"))}</td>
                <td style="padding:9px 8px; border-top:1px solid {LINE}; color:{color}; font-weight:800;">{_html_escape(status)}</td>
                <td style="padding:9px 8px; border-top:1px solid {LINE}; color:{MUTED};">{_html_escape(run.get("bridge_trigger") or "unknown")}</td>
                <td style="padding:9px 8px; border-top:1px solid {LINE}; color:{MUTED};">{_html_escape(_scope_label(stats))}</td>
                <td style="padding:9px 8px; border-top:1px solid {LINE}; color:{INK}; font-weight:700; text-align:right;">{_coerce_int(stats.get("processed")):,}</td>
              </tr>
            """
        )
    if not rows:
        return f'<p style="margin:0; color:{MUTED};">No recent bridge runs found.</p>'
    return f"""
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse; font-size:13px;">
        <tr>
          <th align="left" style="padding:0 8px 8px; color:{MUTED}; text-transform:uppercase; font-size:11px;">Run</th>
          <th align="left" style="padding:0 8px 8px; color:{MUTED}; text-transform:uppercase; font-size:11px;">Status</th>
          <th align="left" style="padding:0 8px 8px; color:{MUTED}; text-transform:uppercase; font-size:11px;">Trigger</th>
          <th align="left" style="padding:0 8px 8px; color:{MUTED}; text-transform:uppercase; font-size:11px;">Scope</th>
          <th align="right" style="padding:0 8px 8px; color:{MUTED}; text-transform:uppercase; font-size:11px;">Processed</th>
        </tr>
        {"".join(rows)}
      </table>
    """


def _alert_items(run: dict[str, Any], recent_runs: list[dict[str, Any]]) -> list[str]:
    stats = _stats_for_run(run)
    alerts: list[str] = []
    status = str(run.get("bridge_status") or "").lower()
    if status != "success":
        alerts.append(f"Run ended with status: {status or 'unknown'}.")
    errors = _coerce_int(stats.get("errors"))
    if errors:
        alerts.append(f"Importer recorded {errors:,} error{'' if errors == 1 else 's'}.")
    if stats.get("changed_since") and not stats.get("resource_id"):
        minimum = _env_int("BRIDGE_SYNC_REPORT_MIN_DELTA_PROCESSED", 10)
        processed = _coerce_int(stats.get("processed"))
        if processed < minimum:
            alerts.append(
                f"Delta processed only {processed:,} resource{'' if processed == 1 else 's'}; "
                f"threshold is {minimum:,}."
            )
    running_runs = [
        r for r in recent_runs if str(r.get("bridge_status") or "").lower() == "running"
    ]
    if running_runs:
        alerts.append(
            f"{len(running_runs):,} bridge run{'' if len(running_runs) == 1 else 's'} still marked running."
        )
    return alerts


def build_bridge_sync_report_html(
    run: dict[str, Any],
    *,
    recent_runs: Optional[list[dict[str, Any]]] = None,
    environment: Optional[str] = None,
) -> str:
    stats = _stats_for_run(run)
    recent_runs = recent_runs or []
    status = str(run.get("bridge_status") or "unknown")
    status_color = _status_color(status, stats)
    processed = _coerce_int(stats.get("processed"))
    imported = _coerce_int(stats.get("imported"))
    skipped = _coerce_int(stats.get("skipped"))
    errors = _coerce_int(stats.get("errors"))
    changed_resources = _coerce_int(stats.get("changed_resources"), processed)
    cache_stats = stats.get("cache_refresh") if isinstance(stats.get("cache_refresh"), dict) else {}
    index_stats = (
        stats.get("search_index_refresh")
        if isinstance(stats.get("search_index_refresh"), dict)
        else {}
    )
    base_url = os.getenv("BRIDGE_SYNC_REPORT_BASE_URL") or os.getenv("APPLICATION_URL") or ""
    run_url = (
        f"{base_url.rstrip('/')}/api/v1/admin/bridge/sync/runs/{run.get('bridge_id')}"
        if base_url
        else ""
    )

    alerts = _alert_items(run, recent_runs)
    alert_body = "".join(
        f'<li style="margin:0 0 7px;">{_html_escape(item)}</li>' for item in alerts
    )
    if not alert_body:
        alert_body = '<li style="margin:0;">No warning conditions tripped for this run.</li>'

    error_samples = (
        stats.get("error_samples") if isinstance(stats.get("error_samples"), list) else []
    )
    sample_items = "".join(
        f"""
          <li style="margin:0 0 8px;">
            <strong>{_html_escape(sample.get("resource_id") or sample.get("stage") or "sample")}</strong>
            <span style="color:{MUTED};"> - {_html_escape(sample.get("error") or "")}</span>
          </li>
        """
        for sample in error_samples[:5]
        if isinstance(sample, dict)
    )

    return f"""<!doctype html>
<html>
  <body style="margin:0; padding:0; background:{SOFT}; font-family:Arial, Helvetica, sans-serif;">
    <div style="display:none; max-height:0; overflow:hidden;">
      {_html_escape(_status_label(status, stats))}: {processed:,} processed, {imported:,} imported.
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{
        SOFT
    }; padding:28px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellspacing="0" cellpadding="0" style="max-width:720px; width:100%; background:#ffffff; border:1px solid {
        LINE
    };">
            <tr>
              <td style="background:{BRAND_BLUE}; padding:30px 32px 26px;">
                <div style="color:#BFD8E8; font-size:12px; text-transform:uppercase; font-weight:800;">BTAA Geoportal</div>
                <h1 style="margin:8px 0 0; color:#ffffff; font-size:30px; line-height:1.15;">Nightly Bridge Sync Report</h1>
                <p style="margin:10px 0 0; color:#E5F1F7; font-size:15px; line-height:1.5;">
                  {
        environment or os.getenv("KAMAL_DEST") or os.getenv("APP_ENV") or "Kamal"
    } · Run #{_html_escape(run.get("bridge_id"))} · {
        _html_escape(
            _format_datetime(run.get("bridge_completed_at") or run.get("bridge_started_at"))
        )
    }
                </p>
              </td>
            </tr>
            <tr>
              <td style="padding:22px 32px 30px;">
                <div style="border-left:6px solid {
        status_color
    }; background:#F9FAFB; padding:16px 18px;">
                  <div style="font-size:12px; text-transform:uppercase; font-weight:800; color:{
        status_color
    };">{_html_escape(status)}</div>
                  <div style="margin-top:4px; font-size:22px; line-height:1.25; color:{
        INK
    }; font-weight:800;">{_html_escape(_status_label(status, stats))}</div>
                  <div style="margin-top:7px; color:{MUTED}; font-size:14px; line-height:1.5;">{
        _html_escape(_scope_label(stats))
    }</div>
                </div>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:14px -8px 4px;">
                  <tr>
                    {_metric("Processed", f"{processed:,}", BRAND_BLUE)}
                    {_metric("Imported", f"{imported:,}", GOOD)}
                    {_metric("Skipped", f"{skipped:,}", WARN if skipped else BRAND_BLUE)}
                    {_metric("Errors", f"{errors:,}", BAD if errors else GOOD)}
                  </tr>
                </table>

                {
        _panel(
            "Run Details",
            _key_value_rows(
                [
                    ("Trigger", run.get("bridge_trigger") or "unknown"),
                    ("Scope", _scope_label(stats)),
                    ("Started", _format_datetime(run.get("bridge_started_at"))),
                    ("Completed", _format_datetime(run.get("bridge_completed_at"))),
                    (
                        "Duration",
                        _format_duration(
                            run.get("bridge_started_at"), run.get("bridge_completed_at")
                        ),
                    ),
                    ("Changed since", stats.get("changed_since") or "Not limited"),
                    ("Changed resources", f"{changed_resources:,}"),
                    ("Pages processed", f"{_coerce_int(stats.get('pages_processed')):,}"),
                    (
                        "Missing / retired",
                        f"{_coerce_int(stats.get('missing')):,} / {_coerce_int(stats.get('retired')):,}",
                    ),
                ]
            ),
            BRAND_BLUE,
        )
    }

                {
        _panel(
            "Post-Sync Publishing",
            _key_value_rows(
                [
                    (
                        "Elasticsearch refresh",
                        "disabled"
                        if index_stats.get("enabled") is False
                        else f"{_coerce_int(index_stats.get('indexed')):,} indexed, {_coerce_int(index_stats.get('errors')):,} errors",
                    ),
                    (
                        "Search cache invalidation",
                        "disabled"
                        if cache_stats.get("enabled") is False
                        else f"{_coerce_int(cache_stats.get('invalidated')):,} entries invalidated",
                    ),
                    (
                        "Search/resource cache re-warm",
                        "disabled"
                        if cache_stats.get("enabled") is False
                        else f"{_coerce_int(cache_stats.get('warmed')):,} URLs warmed, {_coerce_int(cache_stats.get('errors')):,} errors",
                    ),
                ]
            ),
            ACTIVE_BLUE,
        )
    }

                {
        _panel(
            "Watchlist",
            f'<ul style="margin:0; padding-left:18px; color:{MUTED};">{alert_body}</ul>',
            WARN if alerts else GOOD,
        )
    }

                {_panel("Recent Runs", _recent_run_rows(recent_runs), BRAND_BLUE)}

                {
        _panel(
            "Error Samples",
            f'<ul style="margin:0; padding-left:18px;">{sample_items}</ul>'
            if sample_items
            else f'<p style="margin:0; color:{MUTED};">No importer error samples were recorded.</p>',
            BAD if sample_items else GOOD,
        )
    }

                {
        f'<p style="margin:20px 0 0;"><a href="{_html_escape(run_url)}" style="display:inline-block; background:{BRAND_BLUE}; color:#ffffff; text-decoration:none; font-weight:800; padding:12px 16px;">Open run JSON</a></p>'
        if run_url
        else ""
    }

                <p style="margin:24px 0 0; color:#6B7280; font-size:12px; line-height:1.5;">
                  Sent automatically after the bridge sync task finalized. Colors and visual rhythm follow the BTAA Geoportal interface: deep BTAA blue, active blue, white panels, and quiet slate metadata.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def build_bridge_sync_report_text(
    run: dict[str, Any],
    *,
    recent_runs: Optional[list[dict[str, Any]]] = None,
) -> str:
    stats = _stats_for_run(run)
    alerts = _alert_items(run, recent_runs or [])
    lines = [
        "BTAA Geoportal Nightly Bridge Sync Report",
        f"Run: #{run.get('bridge_id')}",
        f"Status: {run.get('bridge_status') or 'unknown'}",
        f"Trigger: {run.get('bridge_trigger') or 'unknown'}",
        f"Scope: {_scope_label(stats)}",
        f"Started: {_format_datetime(run.get('bridge_started_at'))}",
        f"Completed: {_format_datetime(run.get('bridge_completed_at'))}",
        f"Duration: {_format_duration(run.get('bridge_started_at'), run.get('bridge_completed_at'))}",
        f"Processed: {_coerce_int(stats.get('processed')):,}",
        f"Imported: {_coerce_int(stats.get('imported')):,}",
        f"Skipped: {_coerce_int(stats.get('skipped')):,}",
        f"Errors: {_coerce_int(stats.get('errors')):,}",
        f"Changed since: {stats.get('changed_since') or 'Not limited'}",
        "",
        "Watchlist:",
    ]
    lines.extend(f"- {item}" for item in alerts)
    if not alerts:
        lines.append("- No warning conditions tripped for this run.")
    return "\n".join(lines)


def _build_message(
    run: dict[str, Any],
    *,
    recent_runs: Optional[list[dict[str, Any]]] = None,
    recipients: list[str],
) -> EmailMessage:
    stats = _stats_for_run(run)
    status = str(run.get("bridge_status") or "unknown").upper()
    subject_prefix = os.getenv("BRIDGE_SYNC_REPORT_SUBJECT_PREFIX", "BTAA Geoportal")
    environment = os.getenv("KAMAL_DEST") or os.getenv("APP_ENV") or os.getenv("RAILS_ENV")
    subject_env = f" [{environment}]" if environment else ""
    subject = (
        f"{subject_prefix}{subject_env} bridge sync {status}: "
        f"{_coerce_int(stats.get('processed')):,} processed"
    )

    sender = os.getenv("BRIDGE_SYNC_REPORT_FROM") or os.getenv("SMTP_FROM")
    if not sender:
        sender = "BTAA Geoportal <no-reply@geo.btaa.org>"
    if "<" not in sender and ">" not in sender:
        sender = formataddr(("BTAA Geoportal", sender))

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Message-ID"] = make_msgid(domain="geo.btaa.org")
    message.set_content(build_bridge_sync_report_text(run, recent_runs=recent_runs))
    message.add_alternative(
        build_bridge_sync_report_html(run, recent_runs=recent_runs, environment=environment),
        subtype="html",
    )
    return message


def send_bridge_sync_report_email(
    run: dict[str, Any],
    *,
    recent_runs: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    if not _env_bool("BRIDGE_SYNC_REPORT_ENABLED", False):
        return {"enabled": False, "sent": False, "reason": "disabled"}

    if not _destination_allows_report():
        return {
            "enabled": True,
            "sent": False,
            "reason": "destination_not_enabled",
            "destination": _current_destination() or None,
        }

    recipients = _split_recipients(
        os.getenv("BRIDGE_SYNC_REPORT_RECIPIENTS", DEFAULT_REPORT_RECIPIENTS)
    )
    if not recipients:
        return {"enabled": True, "sent": False, "reason": "no_recipients"}

    delivery = os.getenv("BRIDGE_SYNC_REPORT_DELIVERY", "smtp").strip().lower()
    if delivery == "sendmail":
        sendmail_path = os.getenv("SENDMAIL_PATH", "/usr/sbin/sendmail")
        sendmail_args = os.getenv("SENDMAIL_ARGS", "-t -i").split()
        message = _build_message(run, recent_runs=recent_runs, recipients=recipients)
        subprocess.run(
            [sendmail_path, *sendmail_args],
            input=message.as_bytes(),
            check=True,
            timeout=_env_int("SENDMAIL_TIMEOUT_SECONDS", 20),
        )
        return {
            "enabled": True,
            "sent": True,
            "delivery": "sendmail",
            "recipients": len(recipients),
        }

    if delivery != "smtp":
        return {"enabled": True, "sent": False, "reason": f"unknown_delivery:{delivery}"}

    host = os.getenv("SMTP_HOST")
    if not host:
        return {"enabled": True, "sent": False, "reason": "no_smtp_host"}

    port = _env_int("SMTP_PORT", 587)
    timeout = _env_int("SMTP_TIMEOUT_SECONDS", 20)
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = _env_bool("SMTP_SSL", False)
    use_starttls = _env_bool("SMTP_STARTTLS", not use_ssl)

    message = _build_message(run, recent_runs=recent_runs, recipients=recipients)

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port, timeout=timeout) as smtp:
        if use_starttls and not use_ssl:
            smtp.starttls()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)

    return {"enabled": True, "sent": True, "recipients": len(recipients)}


async def send_bridge_sync_report_for_run(run_id: int) -> dict[str, Any]:
    if not _env_bool("BRIDGE_SYNC_REPORT_ENABLED", False):
        return {"enabled": False, "sent": False, "reason": "disabled"}

    if not database.is_connected:
        await database.connect()

    repo = BridgeSyncRepository()
    run = await repo.get_sync_run(run_id)
    if not run:
        return {"enabled": True, "sent": False, "reason": "run_not_found", "run_id": run_id}
    recent_runs = await repo.list_sync_runs(limit=8)
    return send_bridge_sync_report_email(run, recent_runs=recent_runs)
