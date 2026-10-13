from app.services.analytics_reporting.popular_momentum import popular_momentum


def test_baselines_include_resources_outside_top_fifty_and_require_calendar_month():
    previous = {
        "collections": [{"id": "collection", "views": 12}],
        "resources": [{"id": str(i), "downloads": i, "sourceClicks": i * 2} for i in range(75)],
    }
    result = popular_momentum({"2026-08": previous, "2026-09": previous, "2026-11": previous})
    assert result["2026-08"] is None
    assert result["2026-09"]["downloads"]["74"] == 74
    assert result["2026-09"]["outlinks"]["74"] == 148
    assert result["2026-09"]["collections"]["collection"] == 12
    assert result["2026-11"] is None


def test_previous_month_crosses_year_boundary():
    report = {"collections": [], "resources": []}
    assert popular_momentum({"2026-12": report, "2027-01": report})["2027-01"] == {
        "collections": {},
        "downloads": {},
        "outlinks": {},
    }
