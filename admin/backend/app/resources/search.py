"""Shared, authorized Resource predicates for results, facets, and export."""

import json
import re
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import ARRAY, Date, String, and_, case, cast, func, null, or_, select, true

from app.domain import DomainError
from app.persistence import actors
from app.resources.models import evidence, imports, resources
from app.sets.models import sets
from app.sets.service import visible

FILTER_DESCRIPTION = (
    "JSON facet map. Each field accepts a value array (include any), or an object with "
    'include/exclude arrays and operator "or" (default) or "and" for includes. '
    "Fields combine with AND; exclusions retain missing metadata. "
    "Date fields also accept {from: YYYY-MM-DD, to: YYYY-MM-DD} inclusive ranges."
)

FACETS = {
    "imports": ("Imports", "import_id"),
    "publication": ("Publication state", "publication_state"),
    "resource_class": ("Resource class", "gbl_resourceClass_sm"),
    "resource_type": ("Resource type", "gbl_resourceType_sm"),
    "is_harvested": ("Is harvested", "b1g_isHarvested_b"),
    "last_harvested": ("Last harvested", "b1g_lastHarvested_dt"),
    "accrual_method": ("Accrual method", "b1g_dct_accrualMethod_s"),
    "accrual_periodicity": ("Accrual periodicity", "b1g_dct_accrualPeriodicity_s"),
    "website_platform": ("Website platform", "b1g_websitePlatform_s"),
    "endpoint_description": ("Endpoint description", "b1g_dcat_endpointDescription_s"),
    "harvest_workflow": ("Harvest workflow", "b1g_harvestWorkflow_s"),
    "date_accessioned": ("Date accessioned", "b1g_dateAccessioned_dt"),
    "date_retired": ("Date retired", "b1g_dateRetired_dt"),
    "date_created": ("Date created", "date_created_dtsi"),
    "access": ("Public / Restricted", "dct_accessRights_s"),
    "provider": ("Provider", "schema_provider_s"),
    "place": ("Place", "dct_spatial_sm"),
    "subject": ("Subject", "dct_subject_sm"),
    "theme": ("Theme", "dcat_theme_sm"),
    "language": ("Language", "dct_language_sm"),
    "format": ("Format", "dct_format_s"),
    "year": ("Year", "gbl_indexYear_im"),
    "set": ("Set", "set_id"),
    "source": ("Source ID", "source_id"),
}

# Sidebar vocabulary follows the GEOMGv1 list. Retain other supported predicates
# for existing links, scoped navigation, exports, and saved selections.
SIDEBAR_FACETS = (
    "imports",
    "resource_class",
    "resource_type",
    "is_harvested",
    "last_harvested",
    "accrual_method",
    "accrual_periodicity",
    "website_platform",
    "endpoint_description",
    "harvest_workflow",
    "date_accessioned",
    "date_retired",
    "date_created",
    "access",
)

DATE_FACETS = {"last_harvested", "date_accessioned", "date_retired", "date_created"}


def facet_column(field):
    if field == "source":
        return sets.c.source_id
    if field == "imports":
        local_import = (
            select(cast(evidence.c.import_id, String))
            .where(evidence.c.resource_id == resources.c.id)
            .scalar_subquery()
        )
        return func.coalesce(func.nullif(resources.c.import_id, ""), local_import)
    if field in {"date_accessioned", "date_retired"}:
        suffix = "Accessioned" if field == "date_accessioned" else "Retired"
        return func.coalesce(
            resources.c[f"b1g_date{suffix}_dt"], resources.c[f"b1g_date{suffix}_s"]
        )
    return resources.c[FACETS[field][1]]


class FacetDefinition(BaseModel):
    field: str
    label: str


class FacetValue(BaseModel):
    value: str
    label: str
    count: int
    timestamp: datetime | None = None


FacetSort = Literal["count_desc", "count_asc", "alpha_asc", "alpha_desc", "recent"]


class FacetPage(BaseModel):
    field: str
    label: str
    items: list[FacetValue]
    more: bool
    offset: int
    total: int


def parse_filters(raw):
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw or {}
        if not isinstance(value, dict) or set(value) - FACETS.keys():
            raise ValueError()
        for name, selection in value.items():
            if isinstance(selection, dict) and ({"from", "to"} & selection.keys()):
                if name not in DATE_FACETS or set(selection) - {"from", "to"}:
                    raise ValueError()
                for boundary in selection.values():
                    if not isinstance(boundary, str) or not re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}", boundary
                    ):
                        raise ValueError()
                    if date.fromisoformat(boundary) == date.max:
                        raise ValueError()
                if selection.get("from", "0000") > selection.get("to", "9999"):
                    raise ValueError()
                continue
            if isinstance(selection, dict):
                if set(selection) - {"include", "exclude", "operator"} or selection.get(
                    "operator", "or"
                ) not in {"or", "and"}:
                    raise ValueError()
                include, exclude = selection.get("include", []), selection.get("exclude", [])
                if not isinstance(include, list) or not isinstance(exclude, list):
                    raise ValueError()
                values = include + exclude
                if any(item in exclude for item in include):
                    raise ValueError()
            else:
                values = selection
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ValueError()
            if name in DATE_FACETS:
                for item in values:
                    date.fromisoformat(item)
            if name == "is_harvested" and set(values) - {"true", "false"}:
                raise ValueError()
            if name == "source" and any(
                item != "" and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item) for item in values
            ):
                raise ValueError()
            if name == "year":
                for item in values:
                    if not item.lstrip("-").isdigit() or not -(2**31) <= int(item) < 2**31:
                        raise ValueError()
            if name == "set" and any(
                not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item) for item in values
            ):
                raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError) as exc:
        raise DomainError(
            422,
            "invalid_filters",
            "Use supported facets with value arrays or include/exclude arrays and operator or/and; "
            "selections must not overlap",
        ) from exc


def resource_visible(actor):
    assigned = resources.c.set_id.is_not(None) & visible(actor)
    if actor.kind != "user":
        return assigned
    unassigned = resources.c.set_id.is_(None)
    if "resources:intake-manage" not in actor.permissions:
        unassigned &= resources.c.created_by_actor_id.in_(
            select(actors.c.id).where(
                actors.c.kind == actor.kind, actors.c.subject_key == actor.actor_id
            )
        )
    return assigned | unassigned


def predicate(actor, q="", set_id=None, filters=None, ids=None):
    condition = resource_visible(actor)
    if q:
        condition &= or_(
            resources.c.id.icontains(q, autoescape=True),
            resources.c.dct_title_s.icontains(q, autoescape=True),
        )
    if set_id:
        condition &= resources.c.set_id == set_id
    if ids:
        condition &= resources.c.id.in_(ids)
    for name, selection in parse_filters(filters).items():
        if isinstance(selection, dict) and ({"from", "to"} & selection.keys()):
            column = facet_column(name)
            if selection.get("from"):
                condition &= column >= date.fromisoformat(selection["from"])
            if selection.get("to"):
                condition &= column < date.fromisoformat(selection["to"]) + timedelta(days=1)
            continue
        include = selection.get("include", []) if isinstance(selection, dict) else selection
        exclude = selection.get("exclude", []) if isinstance(selection, dict) else []
        operator = selection.get("operator", "or") if isinstance(selection, dict) else "or"
        if not include and not exclude:
            continue
        column = facet_column(name)
        if name in DATE_FACETS:
            column = cast(column, Date)

        def match(values, operator="or", name=name, column=column):
            if name == "source":
                choices = [column.is_(None) if value == "" else column == value for value in values]
                return and_(*choices) if operator == "and" else or_(*choices)
            typed = (
                [value == "true" for value in values]
                if name == "is_harvested"
                else [date.fromisoformat(value) for value in values]
                if name in DATE_FACETS
                else [int(value) for value in values]
                if name == "year"
                else values
            )
            if isinstance(column.type, ARRAY):
                return column.op("@>" if operator == "and" else "&&")(typed)
            return (
                and_(*(column == item for item in typed))
                if operator == "and"
                else column.in_(typed)
            )

        if include:
            condition &= match(include, operator)
        if exclude:
            # SQL NULL means no matching metadata, so it must survive exclusion.
            condition &= match(exclude).is_not(True)
    return condition


async def facets(
    engine,
    actor,
    field,
    q="",
    set_id=None,
    filters=None,
    term="",
    offset=0,
    limit=20,
    sort: FacetSort = "count_desc",
):
    if field not in FACETS:
        raise DomainError(422, "invalid_facet", "Choose a supported facet")
    selected = parse_filters(filters)
    # Disjunctive faceting: retain other fields but exclude this facet's selections.
    selected.pop(field, None)
    column = facet_column(field)
    if field in DATE_FACETS:
        column = cast(column, Date)
    value = (
        func.coalesce(column, "")
        if field == "source"
        else func.unnest(column)
        if isinstance(column.type, ARRAY)
        else column
    )
    source = (
        select(
            resources.c.id,
            cast(value, String).label("value"),
            sets.c.title.label("set_title"),
            (
                select(imports.c.created_at)
                .join(evidence, evidence.c.import_id == imports.c.id)
                .where(evidence.c.resource_id == resources.c.id)
                .scalar_subquery()
                if field == "imports"
                else cast(null(), imports.c.created_at.type)
            ).label("imported_at"),
        )
        .outerjoin(sets, resources.c.set_id == sets.c.set_id)
        .where(predicate(actor, q, set_id, selected))
        .subquery()
    )
    label = (
        source.c.set_title
        if field == "set"
        else case((source.c.value == "", "Unmapped"), else_=source.c.value)
        if field == "source"
        else case((source.c.value == "true", "Yes"), else_="No")
        if field == "is_harvested"
        else source.c.value
    )
    query = select(
        source.c.value,
        label.label("label"),
        func.count(func.distinct(source.c.id)).label("count"),
        func.max(source.c.imported_at).label("timestamp"),
    ).where(source.c.value.is_not(None))
    if field != "source":
        query = query.where(source.c.value != "")
    if term:
        query = query.where(label.icontains(term, autoescape=True))
    grouped = query.group_by(source.c.value, label).cte("facet_counts")
    ordering = {
        "count_desc": grouped.c.count.desc(),
        "count_asc": grouped.c.count.asc(),
        "alpha_asc": grouped.c.label.asc(),
        "alpha_desc": grouped.c.label.desc(),
        "recent": grouped.c.timestamp.desc().nulls_last()
        if field == "imports"
        else grouped.c.value.desc(),
    }
    # Return total and page from one statement/snapshot, including empty pages.
    totals = select(func.count().label("total")).select_from(grouped).subquery()
    page = (
        select(grouped)
        .order_by(ordering[sort], grouped.c.label, grouped.c.value)
        .offset(offset)
        .limit(limit + 1)
        .subquery()
    )
    query = select(totals.c.total, page).select_from(totals.outerjoin(page, true()))
    page_order = {
        "count_desc": page.c.count.desc(),
        "count_asc": page.c.count.asc(),
        "alpha_asc": page.c.label.asc(),
        "alpha_desc": page.c.label.desc(),
        "recent": page.c.timestamp.desc().nulls_last()
        if field == "imports"
        else page.c.value.desc(),
    }
    query = query.order_by(page_order[sort], page.c.label, page.c.value)
    async with engine.connect() as connection:
        rows = (await connection.execute(query)).mappings().all()
    items = [
        dict(
            value=row["value"],
            label=row["label"],
            count=row["count"],
            timestamp=row["timestamp"] if field == "imports" else None,
        )
        for row in rows
        if row["value"] is not None
    ]
    return {
        "field": field,
        "label": FACETS[field][0],
        "items": items[:limit],
        "more": len(items) > limit,
        "offset": offset,
        "total": rows[0]["total"],
    }
