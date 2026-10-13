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


def test_member_collections_follow_saved_eligibility_and_monthly_attribution():
    from app.services.analytics_reporting.collection_views import member_collection_views

    def document(month, code, memberships, count):
        return {
            "month": month,
            "catalog": {
                "resource": {
                    "code": code,
                    "eligible": True,
                    "content": {"attributes": {"collections": memberships}},
                },
                "excluded": {"code": code, "eligible": False, "attributes": {"collections": ["a"]}},
                "other": {"code": "Other", "attributes": {"collections": ["a"]}},
                "a": {"title": "Collection A"},
                "b": {"title": "Collection B"},
            },
            "daily": [
                {
                    "dimensions": {
                        "source": "analytics_events",
                        "event": event,
                        "resource": resource,
                    },
                    "metrics": {"count": value},
                }
                for resource, event, value in [
                    ("resource", "resource_view", count),
                    ("excluded", "resource_view", 999),
                    ("other", "resource_view", 999),
                    ("resource", "download_click", 999),
                ]
            ],
        }

    rows = member_collection_views(
        [
            document("2026-07-01", "University of Chicago", ["a", "a", "b"], 5),
            document("2026-08-01", "The Ohio State University", ["b"], 7),
        ]
    )
    assert rows["12"] == [
        {"id": "a", "title": "Collection A", "views": 5},
        {"id": "b", "title": "Collection B", "views": 5},
    ]
    assert rows["11"] == [{"id": "b", "title": "Collection B", "views": 7}]
    assert rows["all"] == [
        {"id": "b", "title": "Collection B", "views": 12},
        {"id": "a", "title": "Collection A", "views": 5},
    ]
    assert rows["01"] == []
