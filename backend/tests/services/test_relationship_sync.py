from app.services.relationship_sync import (
    ALL_RELATIONSHIP_PREDICATES,
    RELATIONSHIP_FAMILIES,
    _build_relationship_rows,
)


def test_source_relationships_use_canonical_parent_and_child_predicates():
    source_family = next(family for family in RELATIONSHIP_FAMILIES if family[0] == "dct_source_sm")

    rows = _build_relationship_rows(
        {
            source_family: [
                {
                    "id": "child-record",
                    "dct_source_sm": ["parent-record"],
                }
            ]
        },
        ["child-record", "parent-record"],
    )

    assert rows == [
        {
            "subject_id": "child-record",
            "predicate": "dct:source",
            "object_id": "parent-record",
        },
        {
            "subject_id": "parent-record",
            "predicate": "dct:isSourceOf",
            "object_id": "child-record",
        },
    ]
    assert "dct:sourceOf" in ALL_RELATIONSHIP_PREDICATES
