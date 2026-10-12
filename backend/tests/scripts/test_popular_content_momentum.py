from scripts.export_analytics_design_data import previous_resource_views


def test_previous_views_count_only_resource_view_events():
    def row(source, event, count):
        return {
            "dimensions": {"source": source, "event": event, "resource": "resource-1"},
            "metrics": {"count": count},
        }

    document = {
        "daily": [
            row("analytics_events", "resource_view", 7),
            row("analytics_events", "resource_view", 4),
            row("analytics_events", "download_click", 100),
            row("analytics_searches", "resource_view", 50),
        ]
    }
    assert previous_resource_views(document)["resource-1"] == 11
    assert previous_resource_views(document)["unviewed-resource"] == 0
    assert previous_resource_views(None) is None


def test_all_time_classifications_use_latest_preserved_content_metadata():
    from scripts.export_analytics_design_data import resource_classifications

    older = {"catalog": {"map": {"attributes": {"resourceClasses": ["Maps"]}}}}
    newer = {
        "catalog": {
            "map": {
                "content": {
                    "attributes": {
                        "resourceClasses": ["Maps", "Datasets"],
                        "resourceTypes": ["Raster"],
                    }
                }
            }
        }
    }
    assert resource_classifications("map", [older, newer]) == {
        "resourceClass": "Maps, Datasets",
        "resourceType": "Raster",
    }
    assert resource_classifications("map", [older, {"catalog": {}}]) == {
        "resourceClass": "Maps",
        "resourceType": "",
    }
    assert resource_classifications("missing", [older, newer]) == {
        "resourceClass": "",
        "resourceType": "",
    }
