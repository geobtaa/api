"""A migrated legacy code remains a non-unique Source attribute."""

import importlib

from app.sources.schemas import SourceCreate, SourceUpdate


def test_exact_note_extraction_and_nullable_field():
    migration = importlib.import_module("migrations.versions.0018_source_legacy_code")
    notes = "Spreadsheet import\nlegacy_code: 20d-0006\nOther original fields"
    assert migration.LEGACY_LINE.findall(notes) == ["20d-0006"]
    assert migration.LEGACY_LINE.findall("legacy_code: A\nlegacy_code: B") == ["A", "B"]
    assert migration.LEGACY_LINE.findall("not legacy_code: 20d-0006") == []
    assert SourceCreate(title="Example", legacy_code="20d-0006").legacy_code == "20d-0006"
    assert SourceUpdate(lock_version=1, legacy_code=None).legacy_code is None
