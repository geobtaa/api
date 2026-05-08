from app.services.language_service import (
    derive_b1g_language_values,
    ensure_b1g_language,
    normalize_language_values,
)


def test_normalize_language_values_maps_codes_to_labels():
    assert normalize_language_values(["eng", "spa", "fre", "zho"]) == [
        "English",
        "Spanish",
        "French",
        "Chinese",
    ]


def test_normalize_language_values_preserves_unknown_values():
    assert normalize_language_values(["english", "local-code"]) == ["English", "local-code"]


def test_derive_b1g_language_prefers_existing_b1g_values():
    record = {"dct_language_sm": ["spa"], "b1g_language_sm": ["eng"]}

    assert derive_b1g_language_values(record) == ["English"]


def test_ensure_b1g_language_derives_from_dct_language_codes():
    record = {"dct_language_sm": ["eng", "spa"]}

    assert ensure_b1g_language(record)["b1g_language_sm"] == ["English", "Spanish"]
