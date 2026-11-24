"""Install the locked OGM Viewer browser modules for an API-only image."""

import base64
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen


def install(lockfile: Path, destination: Path) -> None:
    package = json.loads(lockfile.read_text())["packages"]["node_modules/ogm-viewer"]
    with urlopen(package["resolved"], timeout=90) as response:
        archive = response.read()
    integrity = base64.b64encode(hashlib.sha512(archive).digest()).decode("ascii")
    if package["integrity"] != f"sha512-{integrity}":
        raise ValueError("OGM Viewer archive does not match the frontend lockfile")

    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if member.isfile() and path.parent == PurePosixPath("package/dist/components"):
                with tar.extractfile(member) as source:
                    (destination / path.name).write_bytes(source.read())


if __name__ == "__main__":
    install(Path(sys.argv[1]), Path(sys.argv[2]))
