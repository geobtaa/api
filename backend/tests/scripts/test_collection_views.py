from app.services.analytics_reporting.collection_views import collection_views


def test_collection_views_use_all_members_and_month_specific_membership():
    def document(month, memberships, count):
        return {
            "month": month,
            "catalog": {
                "resource": {"content": {"attributes": {"collections": memberships}}},
                "a": {"title": "Collection A"},
                "b": {"title": "Collection B"},
            },
            "daily": [
                {
                    "dimensions": {
                        "source": "analytics_events",
                        "event": "resource_view",
                        "resource": "resource",
                    },
                    "metrics": {"count": count},
                },
                {
                    "dimensions": {
                        "source": "analytics_events",
                        "event": "download_click",
                        "resource": "resource",
                    },
                    "metrics": {"count": 999},
                },
                {
                    "dimensions": {"source": "analytics_searches", "resource": "resource"},
                    "metrics": {"count": 999},
                },
                {
                    "dimensions": {
                        "source": "analytics_events",
                        "event": "resource_view",
                        "resource": "missing",
                    },
                    "metrics": {"count": 999},
                },
            ],
        }

    july = document("2026-07-01", ["a", "a", "b"], 5)
    august = document("2026-08-01", ["b"], 7)
    assert collection_views([july, august]) == [
        {"id": "b", "title": "Collection B", "views": 12},
        {"id": "a", "title": "Collection A", "views": 5},
    ]


def test_titles_use_verified_fallbacks_without_replacing_saved_titles():
    document = {
        "month": "2026-09-01",
        "catalog": {
            "resource": {"attributes": {"collections": ["stanford-example", "named"]}},
            "stanford-example": {"title": "stanford-example"},
            "named": {"title": "Saved title"},
        },
        "daily": [
            {
                "dimensions": {
                    "source": "analytics_events",
                    "event": "resource_view",
                    "resource": "resource",
                },
                "metrics": {"count": 3},
            }
        ],
    }
    rows = collection_views([document], {"stanford-example": "Global Map", "named": "Fallback"})
    assert {row["id"]: row["title"] for row in rows} == {
        "named": "Saved title",
        "stanford-example": "Global Map",
    }
    assert all(row["views"] == 3 for row in rows)
