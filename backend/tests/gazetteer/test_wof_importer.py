"""WOF cleaning preserves the base importer contract and table conversions."""

import logging
from datetime import datetime

import pytest

from app.gazetteer.importers.wof_importer import WofImporter


@pytest.fixture
def importer():
    # Record cleaning does not need an engine or a database connection.
    importer = WofImporter.__new__(WofImporter)
    importer.logger = logging.getLogger(__name__)
    return importer


def test_common_cleaning_accepts_a_record_without_a_table_type(importer):
    record = importer.clean_record({"name": "", "wok_id": "123"})

    assert record["name"] is None
    assert record["wok_id"] == "123"
    assert isinstance(record["created_at"], datetime)
    assert record["created_at"] == record["updated_at"]


def test_spr_cleaning_converts_fields_and_supplies_a_missing_name(importer):
    record = importer.clean_wof_record(
        {"wok_id": "123", "name": "", "placetype": "locality", "latitude": "45.5"},
        "spr",
    )

    assert record["wok_id"] == 123
    assert record["latitude"] == 45.5
    assert record["name"] == "Unnamed locality #123"
    assert isinstance(record["created_at"], datetime)


def test_geojson_cleaning_converts_boolean_values(importer):
    record = importer.clean_wof_record(
        {"wok_id": "123", "body": '{"type":"Point"}', "is_alt": "false"}, "geojson"
    )

    assert record["wok_id"] == 123
    assert record["is_alt"] is False


@pytest.mark.parametrize(
    ("record", "table_type"),
    [
        ({"wok_id": "id"}, "spr"),
        ({"wok_id": "123", "other_id": ""}, "concordances"),
        ({"wok_id": "123", "body": ""}, "geojson"),
    ],
)
def test_cleaning_skips_headers_and_records_missing_required_fields(importer, record, table_type):
    assert importer.clean_wof_record(record, table_type) is None
