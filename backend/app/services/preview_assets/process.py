"""Execute geospatial tools in a bounded child process, without shell expansion."""

import json
import os
import signal
import subprocess
import sys
import time

from .models import Outcome, PreviewError


def run_tool(args: list[str], budget) -> str:
    budget.check()
    environment = {
        **os.environ,
        "GDAL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "GDAL_CACHEMAX": "128",
        "PROJ_NETWORK": "OFF",
        # Inputs are extracted into a bounded local job directory. TIFF world
        # files/PAM metadata and shapefile companions are part of the source.
        "GDAL_DISABLE_READDIR_ON_OPEN": "FALSE",
        "OGR_SQLITE_LOAD_EXTENSIONS": "",
        "GDAL_PAM_ENABLED": "YES",
    }
    log = budget.directory / "tool.log"
    own_group = not os.getenv("PREVIEW_CHILD_JOB")

    def check_log():
        if log.stat().st_size > 8 << 20:
            raise PreviewError(Outcome.OVER_LIMIT, "Tool output limit exceeded")

    with log.open("wb") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.services.preview_assets.process",
                str(budget.limits.memory_bytes),
                json.dumps(args),
            ],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=own_group,
            env=environment,
        )
        try:
            while process.poll() is None:
                budget.check()
                check_log()
                time.sleep(0.1)
            check_log()
            if process.returncode:
                with log.open("rb") as diagnostic:
                    diagnostic.seek(max(0, log.stat().st_size - 1500))
                    tail = diagnostic.read(1500).decode(errors="replace")
                raise PreviewError(Outcome.INVALID, f"{args[0]} failed: {tail}")
        finally:
            if own_group:
                # A failed launcher can exit while descendants keep running.
                # Always reap its process group, including after normal exit.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait()
    return log.read_text(errors="replace")


def main():
    import resource

    memory = int(sys.argv[1])
    # Linux enforces the whole tool address space. macOS has a very large shared
    # address region; production limits are enforced by the Linux worker.
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.environ["PREVIEW_CHILD_JOB"] = "true"
    args = json.loads(sys.argv[2])
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
