from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.resources.schemas import ImportRequest
from app.resources.validation import normalize, object_pairs


@pytest.mark.parametrize(
    "patch",
    [
        {"id": None},
        {"id": "\n"},
        {"id": "x" * 513},
        {"dct_title_s": " "},
        {"gbl_suppressed_b": "false"},
        {"dct_description_sm": None},
        {"gbl_indexYear_im": [True]},
        {"gbl_indexYear_im": [2**31]},
        {"gbl_mdModified_dt": "bad"},
        {"dct_references_s": "[]"},
        {"dct_references_s": '{"x":1,"x":2}'},
        {"dct_references_s": '{"http://schema.org/url":false}'},
        {"dct_references_s": '{"http://schema.org/url":["https://x","https://x"]}'},
        {"dct_title_s": 42},
    ],
)
def test_invalid_field_values(patch):
    assert normalize({"id": "test", "dct_title_s": "Test", **patch})[2]


def test_draft_metadata_preserves_evidence_and_normalizes_timestamp():
    values, _, errors, warnings = normalize(
        {
            "id": "test",
            "dct_title_s": "Test",
            "gbl_mdModified_dt": "2026-01-02T03:00:00+03:00",
            "unexpected": 42,
            "b1g_adminNote_sm": ["staff legacy"],
            "gbl_mdVersion_s": "1.0",
        }
    )
    assert not errors
    assert values["gbl_mdModified_dt"].hour == 0
    assert "b1g_adminNote_sm" not in values and "unexpected" not in values
    assert any("publication schema" in warning for warning in warnings)
    assert len(warnings) >= 3
    with pytest.raises(ValueError):
        object_pairs([("x", 1), ("x", 2)])


@pytest.mark.parametrize(
    "records", [[], [{}] * 101, [{"id": "x", "value": "x" * 1_000_001}], [{"value": float("nan")}]]
)
def test_bounded_request(records):
    with pytest.raises(ValidationError):
        ImportRequest(set_id=uuid4(), records=records)
