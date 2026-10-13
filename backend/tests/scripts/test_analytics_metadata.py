from datetime import date

from app.services.analytics_reporting.metadata import content_providers
from app.services.analytics_reporting.pipeline import read_catalog
from app.services.analytics_reporting.reports import build_report
from scripts.refresh_analytics_metadata import refresh


def test_provider_labels_distinguish_empty_fields_from_missing_metadata():
    for value in (None, "", "  ", [], [None, " "]):
        assert content_providers({"provider": value}) == ["Provider not recorded"]
    assert content_providers({}) == ["Provider metadata unavailable"]
    assert content_providers({"provider": ["Penn State", "PASDA"]}) == ["Penn State", "PASDA"]


def test_catalog_export_keeps_ineligible_records_for_content_labels():
    class Connection:
        def execute(self, query):
            assert "WHERE publication_state" not in str(query)
            return self

        def mappings(self):
            return [
                dict(
                    id="pasda-1078",
                    eligible=False,
                    dct_title_s="PennPilot",
                    schema_provider_s=None,
                    b1g_code_s="08a-01",
                    attributes={},
                )
            ]

    record = read_catalog(Connection())["pasda-1078"]
    assert record["title"] == "PennPilot"
    assert record["provider"] is None
    assert record["eligible"] is False


def test_metadata_correction_preserves_counts_and_original_member_eligibility():
    original = {
        "month": "2026-07-01",
        "generation": 1,
        "legacy": None,
        "coverage": {"complete": True},
        "catalogCapturedAt": "2026-08-20",
        "catalog": {
            "eligible": {
                "title": "Original",
                "provider": "Original university",
                "code": "Original code",
            }
        },
        "visits": [],
        "receipts": [],
        "deliveries": [],
        "daily": [
            {
                "metric_date": "2026-07-01",
                "metrics": {"count": count},
                "dimensions": {
                    "source": "analytics_events",
                    "event": event,
                    "resource": identifier,
                    "client": "web",
                    "channel": "browser",
                },
            }
            for identifier, event, count in [
                ("pasda-1078", "resource_view", 36),
                ("eligible", "download_click", 5),
            ]
        ],
    }
    metadata = {
        "capturedAt": "2026-10-10",
        "catalog": {
            "pasda-1078": {"title": "PennPilot", "provider": None},
            "eligible": {"title": "Correct title", "provider": "Correct provider"},
        },
    }
    revised = refresh(original, metadata)
    assert revised["daily"] == original["daily"]
    assert revised["visits"] == original["visits"]
    assert "pasda-1078" not in original["catalog"]
    assert revised["catalog"]["pasda-1078"]["eligible"] is False
    before = build_report("2026-07", date(2026, 8, 1), [original])
    after = build_report("2026-07", date(2026, 8, 1), [revised])
    assert before["totals"] == after["totals"]
    assert before["members"] == after["members"]
    resources = {r["id"]: r for r in after["resources"]}
    assert resources["pasda-1078"]["title"] == "PennPilot"
    assert resources["pasda-1078"]["provider"] == ["Provider not recorded"]
    assert resources["eligible"]["provider"] == ["Correct provider"]
    assert after["downloads"][0]["title"] == "Correct title"
