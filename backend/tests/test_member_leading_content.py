from app.services.analytics_reporting.member_content import member_content


def test_member_rankings_use_complete_lists_and_deduplicate_alliance():
    rows = [
        dict(
            grouping="code",
            name="Indiana University",
            id=str(i),
            title=str(i),
            views=100 - i,
            downloads=i,
        )
        for i in range(60)
    ]
    rows.append({**rows[0], "name": "University of Iowa"})
    result = member_content({"memberResources": rows})
    assert len(result["01"]["viewed"]) == 50
    assert len(result["all"]["viewed"]) == 50
    assert result["all"]["viewed"][-1]["id"] == "49"
    assert result["01"]["downloaded"][0]["id"] == "59"
    assert result["03"]["downloaded"] == []

    assert len(result["01"]["downloaded"]) == 25
