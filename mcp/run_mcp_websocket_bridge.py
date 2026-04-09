#!/usr/bin/env python3
"""Launch the MCP WebSocket bridge with a modern Node executable."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

MIN_NODE_MAJOR = 18


def parse_major(version_text: str) -> int | None:
    match = re.search(r"v(\d+)\.", version_text.strip())
    if not match:
        return None
    return int(match.group(1))


def node_version(node_bin: str) -> int | None:
    try:
        result = subprocess.run(
            [node_bin, "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return parse_major(result.stdout)


def candidate_nodes() -> Iterable[str]:
    env_node = os.environ.get("MCP_NODE_BIN")
    if env_node:
        yield env_node

    which_node = shutil.which("node")
    if which_node:
        yield which_node

    nvm_dir = Path.home() / ".nvm" / "versions" / "node"
    if nvm_dir.exists():
        for candidate in sorted(nvm_dir.glob("v*/bin/node"), reverse=True):
            yield str(candidate)

    for candidate in ("/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"):
        yield candidate


def pick_node() -> str:
    best_candidate = None
    best_version = -1

    for candidate in candidate_nodes():
        if not candidate or not os.path.exists(candidate):
            continue
        major = node_version(candidate)
        if major is None:
            continue
        if major >= MIN_NODE_MAJOR:
            return candidate
        if major > best_version:
            best_candidate = candidate
            best_version = major

    if best_candidate is not None:
        raise RuntimeError(
            f"Found only Node {best_version} at {best_candidate}. "
            f"MCP bridge requires Node {MIN_NODE_MAJOR}+."
        )

    raise RuntimeError(
        "No Node executable found. Install Node 18+ or set MCP_NODE_BIN to a modern node path."
    )


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    project_dir = script_dir.parent
    bridge_script = script_dir / "mcp_websocket_bridge.js"
    node_bin = pick_node()

    os.chdir(project_dir)
    os.execve(node_bin, [node_bin, str(bridge_script), *sys.argv[1:]], os.environ.copy())


if __name__ == "__main__":
    main()
