import json
from dataclasses import replace

import pytest
import test_resources
from test_managing_sets import headers
from test_resource_editor import seed
from test_resources import BASE

from app.resources.validation import TYPES
from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_saved_preview_projects_current_links_and_excludes_internal_data(api):
    client, actors, _, _ = await seed(api)
    response = await client.get(BASE + "/" + encode_id("editor/test") + "/metadata", params={})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    record = response.json()
    assert record["id"] == "editor/test"
    assert record["dct_title_s"] == "Original title"
    assert json.loads(record["dct_references_s"]) == {
        "http://schema.org/url": "https://example.org/original"
    }
    assert (
        not {
            "source_record",
            "import_warnings",
            "publication_state",
            "set_id",
            "lock_version",
        }
        & record.keys()
    )
    links = [
        {
            "distribution_type_id": TYPES["http://schema.org/url"],
            "url": "https://example.org/one",
            "label": "One",
        },
        {
            "distribution_type_id": TYPES["http://schema.org/url"],
            "url": "https://example.org/two",
            "label": "Two",
        },
    ]
    saved = await client.patch(
        BASE + "/" + encode_id("editor/test"),
        params={},
        headers=headers(),
        json={"lock_version": 1, "values": {"dct_title_s": "Saved title"}, "distributions": links},
    )
    assert saved.status_code == 200
    current = (
        await client.get(BASE + "/" + encode_id("editor/test") + "/metadata", params={})
    ).json()
    assert current["dct_title_s"] == "Saved title"
    assert json.loads(current["dct_references_s"])["http://schema.org/url"] == [
        {"url": "https://example.org/one", "label": "One"},
        {"url": "https://example.org/two", "label": "Two"},
    ]
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (
        await client.get(BASE + "/" + encode_id("editor/test") + "/metadata", params={})
    ).status_code == 404
    actors[0] = replace(actors[0], permissions=frozenset())
    assert (
        await client.get(BASE + "/" + encode_id("editor/test") + "/metadata", params={})
    ).status_code == 403
