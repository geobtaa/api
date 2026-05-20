from app.services.licensed_access_repository import (
    ResourceLicensedAccessRecord,
    institution_name_for_code,
    serialize_resource_licensed_accesses,
)


def test_institution_name_for_legacy_numeric_code():
    assert institution_name_for_code("01") == "Indiana University"
    assert institution_name_for_code("11") == "The Ohio State University"
    assert institution_name_for_code("14") == "Rutgers University-New Brunswick"


def test_institution_name_for_short_code():
    assert institution_name_for_code("MSU") == "Michigan State University"
    assert institution_name_for_code("rutgers") == "Rutgers University"


def test_serialize_resource_licensed_accesses_includes_school_name():
    payload = serialize_resource_licensed_accesses(
        [
            ResourceLicensedAccessRecord(
                id=1,
                resource_id="999-0001",
                institution_code="01",
                access_url="https://example.com/iu",
                legacy_friendlier_id="999-0001",
                created_at=None,
                updated_at=None,
            )
        ]
    )

    assert payload == [
        {
            "institution_code": "01",
            "institution_name": "Indiana University",
            "access_url": "https://example.com/iu",
            "legacy_friendlier_id": "999-0001",
        }
    ]
