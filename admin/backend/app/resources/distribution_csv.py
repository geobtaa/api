"""Read the four-column GEOMG Distribution exchange, grouped in file order."""

import csv
import io
import sys

from sqlalchemy import bindparam, delete, insert, select, update

from app.csv_exchange import chunks, csv_line, safe_cell
from app.domain import DomainError
from app.resources.models import distributions, resources
from app.resources.schemas import DistributionEdit
from app.resources.search import resource_visible
from app.resources.validation import VOCABULARY
from app.sets.models import sets

COLUMNS = ("friendlier_id", "reference_type", "distribution_url", "label")
TYPE_IDS = {item["name"]: item["id"] for item in VOCABULARY}


def parse(source):
    csv.field_size_limit(sys.maxsize)
    reader = csv.DictReader(io.StringIO(source.removeprefix("\ufeff"), newline=""), strict=True)
    groups = {}
    try:
        names = reader.fieldnames or []
        if sorted(names) not in [sorted(COLUMNS), sorted((*COLUMNS, "_csv_encoding"))]:
            raise ValueError("Use the Distribution template: " + ", ".join(COLUMNS))
        for number, cells in enumerate(reader, 1):
            if cells.get("_csv_encoding") == "apostrophe-v1":
                cells = {
                    k: v.removeprefix("'") if isinstance(v, str) else v for k, v in cells.items()
                }
            identifier = cells["friendlier_id"]
            if not identifier or not identifier.strip():
                raise ValueError(f"Row {number}: supply a Resource ID before previewing this file")
            row = groups.setdefault(
                identifier,
                dict(
                    row=number,
                    resource_id=identifier,
                    input_rows=[],
                    values={},
                    clear_fields=[],
                    errors=[],
                    distributions=[],
                ),
            )
            row["input_rows"].append(number)
            type_id = TYPE_IDS.get(cells["reference_type"])
            if None in cells or None in cells.values():
                row["errors"].append(f"Row {number}: cell count does not match the template")
            elif cells.get("_csv_encoding", "") not in {"", "apostrophe-v1"}:
                row["errors"].append(f"Row {number}: unsupported CSV encoding")
            elif type_id is None:
                row["errors"].append(f"Row {number}: unknown reference type")
            else:
                try:
                    link = DistributionEdit(
                        distribution_type_id=type_id,
                        url=cells["distribution_url"],
                        label=cells["label"] or None,
                    )
                    row["distributions"].append(link.model_dump())
                except ValueError as exc:
                    row["errors"].append(f"Row {number}: {exc}")
        if not groups:
            raise ValueError("Supply at least one Distribution row")
    except (csv.Error, ValueError) as exc:
        raise DomainError(422, "invalid_csv", str(exc)) from exc
    return list(groups.values())


def desired_links(mode, incoming, existing):
    if mode == "replace_links":
        return incoming
    ordered = {(link["distribution_type_id"], link["url"]): link for link in existing}
    for link in incoming:
        key = (link["distribution_type_id"], link["url"])
        if ordered.setdefault(key, link)["label"] != link["label"]:
            raise ValueError("Conflicting labels for the same Distribution type and URL")
    return list(ordered.values())


def summarize(before, after):
    """Describe removals, additions, label edits and changes in relative order."""

    def labels(links):
        return {(link["distribution_type_id"], link["url"]): link["label"] for link in links}

    old, new = labels(before), labels(after)
    return {
        "added": len(new.keys() - old.keys()),
        "removed": len(old.keys() - new.keys()),
        "relabeled": sum(old[key] != new[key] for key in old.keys() & new.keys()),
        "reordered": [key for key in old if key in new] != [key for key in new if key in old],
    }


async def replace_groups(connection, replacements, key):
    """Retain identity and import provenance of links surviving a replacement."""
    stored = (
        await connection.execute(
            select(distributions).where(distributions.c.resource_id.in_(replacements))
        )
    ).mappings()
    old = {(row["resource_id"], row["distribution_type_id"], row["url"]): row for row in stored}
    inserts, edits = [], []
    for identifier, links in replacements.items():
        for position, link in enumerate(links):
            previous = old.pop((identifier, link["distribution_type_id"], link["url"]), None)
            if previous is None:
                inserts.append(
                    dict(**link, resource_id=identifier, position=position, import_id=str(key))
                )
            elif previous["position"] != position or previous["label"] != link["label"]:
                edits.append(
                    dict(link_id=previous["id"], new_position=position, new_label=link["label"])
                )
    for group in chunks([row["id"] for row in old.values()]):
        await connection.execute(delete(distributions).where(distributions.c.id.in_(group)))
    for group in chunks(edits):
        await connection.execute(
            update(distributions)
            .where(distributions.c.id == bindparam("link_id"))
            .values(position=bindparam("new_position"), label=bindparam("new_label")),
            group,
        )
    for group in chunks(inserts):
        await connection.execute(insert(distributions), group)


async def export(engine, actor, set_id):
    names = {v: k for k, v in TYPE_IDS.items()}
    query = (
        select(distributions)
        .join(resources, resources.c.id == distributions.c.resource_id)
        .outerjoin(sets, sets.c.set_id == resources.c.set_id)
        .where(resource_visible(actor))
        .order_by(distributions.c.resource_id, distributions.c.position, distributions.c.id)
    )
    if set_id:
        query = query.where(resources.c.set_id == set_id)
    yield csv_line([*COLUMNS, "_csv_encoding"])
    async with engine.connect() as connection:
        rows = await connection.stream(query.execution_options(yield_per=500))
        async for row in rows.mappings():
            yield csv_line(
                [
                    safe_cell(row["resource_id"]),
                    names[row["distribution_type_id"]],
                    safe_cell(row["url"]),
                    safe_cell(row["label"] or ""),
                    "apostrophe-v1",
                ]
            )
