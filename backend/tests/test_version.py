import json
import re
from datetime import date

from app.version import APP_VERSION, RELEASE_METADATA, RELEASE_METADATA_FILE


def test_release_metadata_is_complete():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
    assert date.fromisoformat(RELEASE_METADATA["release_date"])
    assert RELEASE_METADATA["summary"].strip()


def test_app_version_comes_from_release_metadata_file():
    metadata = json.loads(RELEASE_METADATA_FILE.read_text(encoding="utf-8"))

    assert APP_VERSION == metadata["version"]
