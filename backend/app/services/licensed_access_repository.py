from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import resource_licensed_accesses

INSTITUTION_CODE_LABELS: dict[str, str] = {
    "01": "Indiana University",
    "02": "University of Illinois Urbana-Champaign",
    "03": "University of Iowa",
    "04": "University of Maryland",
    "05": "University of Minnesota",
    "06": "Michigan State University",
    "07": "University of Michigan",
    "08": "Purdue University",
    "09": "Pennsylvania State University",
    "10": "University of Wisconsin-Madison",
    "11": "The Ohio State University",
    "12": "University of Chicago",
    "13": "University of Nebraska-Lincoln",
    "14": "Rutgers University-New Brunswick",
    "IU": "Indiana University",
    "INDIANA": "Indiana University",
    "UIUC": "University of Illinois Urbana-Champaign",
    "ILLINOIS": "University of Illinois Urbana-Champaign",
    "IOWA": "University of Iowa",
    "UMD": "University of Maryland",
    "MARYLAND": "University of Maryland",
    "UMN": "University of Minnesota",
    "MINN": "University of Minnesota",
    "MSU": "Michigan State University",
    "MICHIGAN_STATE": "Michigan State University",
    "UMICH": "University of Michigan",
    "MICH": "University of Michigan",
    "PURDUE": "Purdue University",
    "PU": "Purdue University",
    "PSU": "Pennsylvania State University",
    "PENN_STATE": "Pennsylvania State University",
    "WISC": "University of Wisconsin-Madison",
    "WISCONSIN": "University of Wisconsin-Madison",
    "OSU": "The Ohio State University",
    "OHIO_STATE": "The Ohio State University",
    "UCHICAGO": "University of Chicago",
    "CHICAGO": "University of Chicago",
    "UNL": "University of Nebraska-Lincoln",
    "NEBRASKA": "University of Nebraska-Lincoln",
    "RUTGERS": "Rutgers University",
    "RUTGERS_NEW_BRUNSWICK": "Rutgers University-New Brunswick",
    "RU": "Rutgers University",
    "NU": "Northwestern University",
    "NORTHWESTERN": "Northwestern University",
    "UO": "University of Oregon",
    "OREGON": "University of Oregon",
    "UWASH": "University of Washington",
    "WASHINGTON": "University of Washington",
}


@dataclass(frozen=True)
class ResourceLicensedAccessRecord:
    id: int
    resource_id: str
    institution_code: str
    access_url: str
    legacy_friendlier_id: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


def institution_name_for_code(institution_code: str | None) -> str | None:
    if not institution_code:
        return None

    normalized = str(institution_code).strip()
    if not normalized:
        return None

    upper = normalized.upper().replace("-", "_").replace(" ", "_")
    return INSTITUTION_CODE_LABELS.get(normalized) or INSTITUTION_CODE_LABELS.get(upper)


async def fetch_resource_licensed_accesses(
    resource_id: str, *, session: AsyncSession
) -> List[ResourceLicensedAccessRecord]:
    accesses_map = await fetch_resource_licensed_accesses_map([resource_id], session=session)
    return accesses_map.get(resource_id, [])


async def fetch_resource_licensed_accesses_map(
    resource_ids: Iterable[str], *, session: AsyncSession
) -> Dict[str, List[ResourceLicensedAccessRecord]]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    stmt = (
        select(resource_licensed_accesses)
        .where(resource_licensed_accesses.c.resource_id.in_(ids))
        .order_by(
            resource_licensed_accesses.c.resource_id,
            resource_licensed_accesses.c.institution_code,
            resource_licensed_accesses.c.id,
        )
    )
    result = await session.execute(stmt)

    accesses_by_resource_id: Dict[str, List[ResourceLicensedAccessRecord]] = {}
    for row in result.fetchall():
        mapping = row._mapping
        access_url = mapping["access_url"]
        institution_code = mapping["institution_code"]
        if not access_url or not institution_code:
            continue

        record = ResourceLicensedAccessRecord(
            id=mapping["id"],
            resource_id=mapping["resource_id"],
            institution_code=institution_code,
            access_url=access_url,
            legacy_friendlier_id=mapping["legacy_friendlier_id"],
            created_at=mapping["created_at"],
            updated_at=mapping["updated_at"],
        )
        accesses_by_resource_id.setdefault(record.resource_id, []).append(record)

    return accesses_by_resource_id


def serialize_resource_licensed_accesses(
    accesses: List[ResourceLicensedAccessRecord],
) -> List[dict]:
    return [
        {
            "institution_code": access.institution_code,
            "institution_name": institution_name_for_code(access.institution_code),
            "access_url": access.access_url,
            "legacy_friendlier_id": access.legacy_friendlier_id,
        }
        for access in accesses
    ]
