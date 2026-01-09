#!/usr/bin/env python3
"""
Run a command with an optional wall-clock timeout.

Usage:
  WALLCLOCK_TIMEOUT_SECONDS=1800 python scripts/run_with_timeout.py <cmd> [args...]

If the timeout is exceeded:
  - Sends SIGUSR1 (useful with PYTHONFAULTHANDLER=1 to dump tracebacks)
  - Then SIGTERM, and finally SIGKILL if needed
  - Exits with code 124
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


def _parse_timeout_seconds() -> float:
    raw = os.getenv("WALLCLOCK_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        print(
            f"[run_with_timeout] invalid WALLCLOCK_TIMEOUT_SECONDS={raw!r}; treating as no-timeout",
            file=sys.stderr,
        )
        return 0.0


def _tail_lines(path: Path, n: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:
        return []


def _iter_heartbeat_logs() -> Iterable[Path]:
    # When invoked from the Makefile, cwd should be backend/
    log_path = os.getenv("LOG_PATH", "./test_logs")
    base = Path(log_path)
    if not base.exists():
        return []
    return sorted(base.glob("pytest_heartbeat_*.log"))


def _print_last_heartbeat(stderr: bool = True) -> None:
    out = sys.stderr if stderr else sys.stdout
    logs = list(_iter_heartbeat_logs())
    if not logs:
        return
    print("[run_with_timeout] last heartbeat lines:", file=out)
    for p in logs:
        tail = _tail_lines(p, 8)
        if not tail:
            continue
        print(f"[run_with_timeout] --- {p} ---", file=out)
        for line in tail:
            print(f"[run_with_timeout] {line}", file=out)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_grace_seconds() -> float:
    raw = os.getenv("TIMEOUT_GRACE_SECONDS", "").strip()
    if not raw:
        return 30.0
    try:
        return float(raw)
    except ValueError:
        return 30.0


def main() -> int:
    cmd = sys.argv[1:]
    if not cmd:
        print("[run_with_timeout] ERROR: no command provided", file=sys.stderr)
        print(
            "Usage: WALLCLOCK_TIMEOUT_SECONDS=1800 python scripts/run_with_timeout.py <cmd> [args...]",
            file=sys.stderr,
        )
        return 2

    timeout_seconds = _parse_timeout_seconds()
    start = time.time()

    # Put the command in its own process group/session so we can signal the whole tree
    # (useful for pytest-xdist, which spawns worker processes).
    proc = subprocess.Popen(cmd, start_new_session=True)
    try:
        while True:
            try:
                return proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                if timeout_seconds and (time.time() - start) > timeout_seconds:
                    elapsed = time.time() - start
                    print(
                        f"[run_with_timeout] TIMEOUT after {elapsed:.1f}s (limit={timeout_seconds:.1f}s).",
                        file=sys.stderr,
                    )
                    _print_last_heartbeat(stderr=True)

                    # Optional: dump Python stacks if faulthandler is enabled and we want it.
                    if _truthy_env("TIMEOUT_DUMP_STACKS"):
                        try:
                            os.killpg(proc.pid, signal.SIGUSR1)
                            print(
                                "[run_with_timeout] sent SIGUSR1 to process group for traceback dump",
                                file=sys.stderr,
                            )
                        except Exception:
                            try:
                                proc.send_signal(signal.SIGUSR1)
                                print(
                                    "[run_with_timeout] sent SIGUSR1 for traceback dump",
                                    file=sys.stderr,
                                )
                            except Exception:
                                pass
                        time.sleep(2.0)

                    # First try a graceful stop so pytest can print a summary.
                    grace = _parse_grace_seconds()
                    try:
                        os.killpg(proc.pid, signal.SIGINT)
                        print(
                            f"[run_with_timeout] sent SIGINT to process group (grace={grace:.1f}s)",
                            file=sys.stderr,
                        )
                    except Exception:
                        try:
                            proc.send_signal(signal.SIGINT)
                            print(
                                f"[run_with_timeout] sent SIGINT (grace={grace:.1f}s)",
                                file=sys.stderr,
                            )
                        except Exception:
                            pass
                    try:
                        proc.wait(timeout=grace)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(proc.pid, signal.SIGTERM)
                            print(
                                "[run_with_timeout] still running after grace; sent SIGTERM to process group",
                                file=sys.stderr,
                            )
                        except Exception:
                            try:
                                proc.terminate()
                                print("[run_with_timeout] sent SIGTERM", file=sys.stderr)
                            except Exception:
                                pass
                        try:
                            proc.wait(timeout=10.0)
                        except subprocess.TimeoutExpired:
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                                print(
                                    "[run_with_timeout] sent SIGKILL to process group",
                                    file=sys.stderr,
                                )
                            except Exception:
                                try:
                                    proc.kill()
                                    print("[run_with_timeout] sent SIGKILL", file=sys.stderr)
                                except Exception:
                                    pass
                    return 124
    finally:
        # Best-effort cleanup if the wrapper is interrupted.
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())

