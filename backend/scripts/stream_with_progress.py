#!/usr/bin/env python3
"""
Pass stdin to stdout while printing a lightweight progress meter to stderr.

Designed for long-running dump/restore streams where we want visible transfer
progress without introducing an external dependency like `pv`.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Optional


def _format_bytes(num_bytes: float) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{value:.1f}TiB"


def _format_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _render_status(
    *,
    label: str,
    transferred: int,
    elapsed_seconds: float,
    expected_bytes: Optional[int],
    finished: bool,
) -> str:
    rate = transferred / elapsed_seconds if elapsed_seconds > 0 else 0.0
    base = (
        f"{label}: {_format_bytes(transferred)} transferred"
        f" at {_format_bytes(rate)}/s"
        f" elapsed {_format_duration(elapsed_seconds)}"
    )

    if expected_bytes and expected_bytes > 0:
        pct = min(100.0, (transferred / expected_bytes) * 100.0)
        remaining = max(0, expected_bytes - transferred)
        eta = remaining / rate if rate > 0 else 0.0
        base += (
            f" | approx {pct:5.1f}%"
            f" of {_format_bytes(expected_bytes)}"
            f" | eta {_format_duration(eta)}"
        )

    if finished:
        base += " | done"
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="stream", help="Short label for the progress line")
    parser.add_argument(
        "--expected-bytes",
        type=int,
        default=None,
        help="Approximate total bytes expected in the stream",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Read/write chunk size in bytes (default: 1 MiB)",
    )
    parser.add_argument(
        "--update-interval",
        type=float,
        default=1.0,
        help="Seconds between progress updates (default: 1.0)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    stderr = sys.stderr

    transferred = 0
    started = time.monotonic()
    last_update = started

    while True:
        chunk = stdin.read(args.chunk_size)
        if not chunk:
            break

        stdout.write(chunk)
        stdout.flush()
        transferred += len(chunk)

        now = time.monotonic()
        if now - last_update >= args.update_interval:
            status = _render_status(
                label=args.label,
                transferred=transferred,
                elapsed_seconds=now - started,
                expected_bytes=args.expected_bytes,
                finished=False,
            )
            print(f"\r{status}", end="", file=stderr, flush=True)
            last_update = now

    elapsed = time.monotonic() - started
    status = _render_status(
        label=args.label,
        transferred=transferred,
        elapsed_seconds=elapsed,
        expected_bytes=args.expected_bytes,
        finished=True,
    )
    print(f"\r{status}", file=stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
