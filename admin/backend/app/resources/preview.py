"""Read-only OGM projection of saved descriptive metadata and Distributions."""

import json

from app.resources import editor, service
from app.resources.validation import VOCABULARY


async def record(engine, actor, identifier):
    item = await service.detail(engine, actor, identifier)
    metadata = {name: value for name, value in item["metadata"].items() if name in editor.EDITABLE}
    metadata["id"] = item["id"]
    types = {entry["id"]: entry["uri"] for entry in VOCABULARY}
    grouped = {}
    for link in item["distributions"]:
        grouped.setdefault(types[link["distribution_type_id"]], []).append(
            {"url": link["url"], **({"label": link["label"]} if link["label"] else {})}
        )
    references = {
        uri: links[0]["url"] if len(links) == 1 and "label" not in links[0] else links
        for uri, links in grouped.items()
    }
    metadata["dct_references_s"] = json.dumps(references)
    return metadata
