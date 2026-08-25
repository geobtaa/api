import json
from pathlib import Path

RELEASE_METADATA_FILE = Path(__file__).with_name("_release") / "release.json"


def _load_release_metadata() -> dict[str, str]:
    metadata = json.loads(RELEASE_METADATA_FILE.read_text(encoding="utf-8"))
    version = str(metadata.get("version", "")).strip()
    if not version:
        raise RuntimeError(f"Missing version in {RELEASE_METADATA_FILE}")
    return {key: str(value) for key, value in metadata.items()}


RELEASE_METADATA = _load_release_metadata()
APP_VERSION = RELEASE_METADATA["version"]
