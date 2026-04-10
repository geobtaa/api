#!/usr/bin/env python3
"""Run the BTAA Geospatial API MCP service from the repository root."""

from __future__ import annotations

import os
import sys


def main() -> None:
    mcp_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(mcp_dir)
    backend_dir = os.path.join(project_dir, "backend")

    python_candidates = [
        os.path.join(backend_dir, ".venv", "bin", "python"),
        os.path.join(backend_dir, "venv", "bin", "python"),
        os.path.join(project_dir, ".venv", "bin", "python"),
    ]
    python_executable = next((path for path in python_candidates if os.path.exists(path)), None)
    if python_executable is None:
        python_executable = sys.executable

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        backend_dir
        if not existing_pythonpath
        else os.pathsep.join([backend_dir, existing_pythonpath])
    )

    os.chdir(backend_dir)
    os.execve(
        python_executable,
        [python_executable, "-m", "app.services.mcp_service", *sys.argv[1:]],
        env,
    )


if __name__ == "__main__":
    main()
