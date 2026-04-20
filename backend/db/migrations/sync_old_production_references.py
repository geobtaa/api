#!/usr/bin/env python3
# ruff: noqa: I001
"""Sync old-production legacy references, downloads, and assets into the API DB.

This migration fills the gaps left by the old `kithe_to_resources_bridge` materialized
view for curated BTAA-GIN datasets. In old production, critical download/PMTiles
references often live on child Kithe asset rows rather than in the parent
`json_attributes['dct_references_s']` blob or `document_distributions`.

The script rebuilds canonical references for imported resources by combining:
- parent `kithe_models.json_attributes['dct_references_s']`
- legacy `document_distributions`
- legacy `document_downloads`
- child `kithe_models` rows with `file_data`

It then updates:
- `resources.dct_references_s`
- `resource_distributions`
- `resource_downloads`
- `resource_assets`
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

# Ensure project root is importable.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.services.reference_reconstruction import (  # noqa: E402
    build_asset_record_from_kithe_model,
    build_distribution_rows_from_payload,
    build_effective_reference_payload,
    serialize_reference_payload,
)
from db.models import (  # noqa: E402
    resource_assets,
    resource_distributions,
    resource_downloads,
)


logger = logging.getLogger(__name__)

DEFAULT_ASSET_BASE_URL = "https://geobtaa-assets-prod.s3.us-east-2.amazonaws.com"


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_env(key: str, default: str) -> str:
    return os.getenv(key, default)


def get_old_engine() -> Engine:
    db_user = get_env("DB_USER", "postgres")
    db_password = get_env("DB_PASSWORD", "postgres")
    db_host = get_env("DB_HOST", "localhost")
    db_port = get_env("DB_PORT", "2345")
    old_db_name = get_env("OLD_DB_NAME", "geoportal_production_20251030")
    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{old_db_name}"
    logger.info("Connecting to old database: %s", old_db_name)
    return create_engine(url)


def get_new_engine() -> Engine:
    db_user = get_env("DB_USER", "postgres")
    db_password = get_env("DB_PASSWORD", "postgres")
    db_host = get_env("DB_HOST", "localhost")
    db_port = get_env("DB_PORT", "2345")
    db_name = get_env("DB_NAME", "btaa_geospatial_api")
    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info("Connecting to new database: %s", db_name)
    return create_engine(url)


def load_reference_type_id_to_uri(old_engine: Engine) -> Dict[int, str]:
    with old_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, reference_uri
                FROM reference_types
                ORDER BY id
                """
            )
        ).fetchall()
    return {int(row.id): str(row.reference_uri) for row in rows}


def load_distribution_uri_to_type_id(new_engine: Engine) -> Dict[str, int]:
    with new_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, distribution_uri
                FROM distribution_types
                ORDER BY id
                """
            )
        ).fetchall()
    return {str(row.distribution_uri): int(row.id) for row in rows}


def fetch_parent_batch(
    old_engine: Engine,
    *,
    batch_size: int,
    after_resource_id: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    clauses = [
        "type = 'Document'",
        "publication_state = 'published'",
        "friendlier_id IS NOT NULL",
    ]
    params: Dict[str, Any] = {"limit": batch_size}

    if resource_id:
        clauses.append("friendlier_id = :resource_id")
        params["resource_id"] = resource_id
    elif after_resource_id:
        clauses.append("friendlier_id > :after_resource_id")
        params["after_resource_id"] = after_resource_id

    stmt = text(
        f"""
        SELECT
            id AS model_id,
            friendlier_id AS resource_id,
            json_attributes->'dct_references_s' AS dct_references_s
        FROM kithe_models
        WHERE {" AND ".join(clauses)}
        ORDER BY friendlier_id
        LIMIT :limit
        """
    )

    with old_engine.connect() as conn:
        rows = conn.execute(stmt, params).fetchall()
    return [dict(row._mapping) for row in rows]


def fetch_existing_resource_ids(new_engine: Engine, resource_ids: Sequence[str]) -> set[str]:
    if not resource_ids:
        return set()

    stmt = text("SELECT id FROM resources WHERE id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    with new_engine.connect() as conn:
        rows = conn.execute(stmt, {"ids": list(resource_ids)}).fetchall()
    return {str(row.id) for row in rows}


def fetch_document_distributions(
    old_engine: Engine, resource_ids: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    if not resource_ids:
        return {}

    stmt = text(
        """
        SELECT
            id,
            friendlier_id,
            reference_type_id,
            url,
            label,
            COALESCE(position, 0) AS position,
            created_at,
            updated_at
        FROM document_distributions
        WHERE friendlier_id IN :ids
        ORDER BY friendlier_id, position, id
        """
    ).bindparams(bindparam("ids", expanding=True))

    with old_engine.connect() as conn:
        rows = conn.execute(stmt, {"ids": list(resource_ids)}).fetchall()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row._mapping)
        grouped.setdefault(str(payload["friendlier_id"]), []).append(payload)
    return grouped


def fetch_document_downloads(
    old_engine: Engine, resource_ids: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    if not resource_ids:
        return {}

    stmt = text(
        """
        SELECT
            id,
            friendlier_id,
            label,
            value,
            COALESCE(position, 0) AS position,
            created_at,
            updated_at
        FROM document_downloads
        WHERE friendlier_id IN :ids
        ORDER BY friendlier_id, position, id
        """
    ).bindparams(bindparam("ids", expanding=True))

    with old_engine.connect() as conn:
        rows = conn.execute(stmt, {"ids": list(resource_ids)}).fetchall()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row._mapping)
        grouped.setdefault(str(payload["friendlier_id"]), []).append(payload)
    return grouped


def fetch_child_assets(
    old_engine: Engine, parent_model_ids: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    if not parent_model_ids:
        return {}

    stmt = text(
        """
        SELECT
            id,
            parent_id,
            friendlier_id,
            title,
            COALESCE(position, 0) AS position,
            created_at,
            updated_at,
            file_data,
            NULLIF(json_attributes->>'label', '') AS label,
            NULLIF(json_attributes->>'dct_references_uri_key', '') AS dct_references_uri_key,
            CASE
                WHEN json_attributes->>'thumbnail' IN ('true', 'false')
                THEN (json_attributes->>'thumbnail')::boolean
                ELSE false
            END AS thumbnail
        FROM kithe_models
        WHERE parent_id IN :parent_ids
          AND file_data IS NOT NULL
        ORDER BY parent_id, position, id
        """
    ).bindparams(bindparam("parent_ids", expanding=True))

    with old_engine.connect() as conn:
        rows = conn.execute(stmt, {"parent_ids": list(parent_model_ids)}).fetchall()

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row._mapping)
        grouped.setdefault(str(payload["parent_id"]), []).append(payload)
    return grouped


def sync_batch(
    new_engine: Engine,
    *,
    parents: Sequence[Dict[str, Any]],
    document_distributions_by_resource: Mapping[str, Sequence[Mapping[str, Any]]],
    document_downloads_by_resource: Mapping[str, Sequence[Mapping[str, Any]]],
    child_assets_by_parent: Mapping[str, Sequence[Mapping[str, Any]]],
    reference_type_id_to_uri: Mapping[int, str],
    uri_to_type_id: Mapping[str, int],
    asset_base_url: str,
) -> Dict[str, int]:
    stats = {
        "resources": 0,
        "distribution_rows": 0,
        "download_rows": 0,
        "asset_rows": 0,
    }
    if not parents:
        return stats

    resource_ids = [str(parent["resource_id"]) for parent in parents]
    resource_updates: List[Dict[str, Any]] = []
    distribution_rows: List[Dict[str, Any]] = []
    download_rows: List[Dict[str, Any]] = []
    asset_rows: List[Dict[str, Any]] = []

    for parent in parents:
        resource_id = str(parent["resource_id"])
        parent_model_id = str(parent["model_id"])
        asset_records = []

        for raw_asset in child_assets_by_parent.get(parent_model_id, []):
            asset_record = build_asset_record_from_kithe_model(
                raw_asset,
                resource_id=resource_id,
                asset_base_url=asset_base_url,
            )
            if not asset_record:
                continue
            asset_records.append(asset_record)
            asset_rows.append(
                {
                    "resource_id": resource_id,
                    "bridge_asset_id": asset_record["id"],
                    "bridge_parent_id": asset_record["parent_id"],
                    "friendlier_id": asset_record["friendlier_id"],
                    "title": asset_record["title"],
                    "label": asset_record["label"],
                    "thumbnail": asset_record["thumbnail"],
                    "dct_references_uri_key": asset_record["dct_references_uri_key"],
                    "position": asset_record["position"],
                    "file_url": asset_record["file_url"],
                    "file_mime_type": asset_record["file_mime_type"],
                    "file_size": asset_record["file_size"],
                    "file_width": asset_record["file_width"],
                    "file_height": asset_record["file_height"],
                    "file_md5": asset_record["file_md5"],
                    "file_sha1": asset_record["file_sha1"],
                    "file_sha512": asset_record["file_sha512"],
                    "created_at": asset_record["created_at"],
                    "updated_at": asset_record["updated_at"],
                }
            )

        for raw_download in document_downloads_by_resource.get(resource_id, []):
            download_rows.append(
                {
                    "resource_id": resource_id,
                    "label": raw_download.get("label"),
                    "value": raw_download.get("value"),
                    "position": raw_download.get("position") or 0,
                    "import_download_id": str(raw_download.get("id")),
                    "created_at": raw_download.get("created_at"),
                    "updated_at": raw_download.get("updated_at"),
                }
            )

        reference_payload = build_effective_reference_payload(
            parent.get("dct_references_s"),
            document_distributions=document_distributions_by_resource.get(resource_id) or [],
            document_downloads=document_downloads_by_resource.get(resource_id) or [],
            assets=asset_records,
            reference_type_id_to_uri=reference_type_id_to_uri,
        )
        resource_updates.append(
            {
                "resource_id": resource_id,
                "dct_references_s": serialize_reference_payload(reference_payload),
            }
        )
        distribution_rows.extend(
            build_distribution_rows_from_payload(
                resource_id,
                reference_payload,
                uri_to_type_id=uri_to_type_id,
            )
        )

    with new_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE resources
                SET dct_references_s = :dct_references_s
                WHERE id = :resource_id
                """
            ),
            resource_updates,
        )

        conn.execute(
            resource_distributions.delete().where(
                resource_distributions.c.resource_id.in_(resource_ids)
            )
        )
        conn.execute(
            resource_downloads.delete().where(resource_downloads.c.resource_id.in_(resource_ids))
        )
        conn.execute(
            resource_assets.delete().where(resource_assets.c.resource_id.in_(resource_ids))
        )

        if distribution_rows:
            conn.execute(resource_distributions.insert(), distribution_rows)
        if download_rows:
            conn.execute(resource_downloads.insert(), download_rows)
        if asset_rows:
            conn.execute(resource_assets.insert(), asset_rows)

    stats["resources"] = len(resource_updates)
    stats["distribution_rows"] = len(distribution_rows)
    stats["download_rows"] = len(download_rows)
    stats["asset_rows"] = len(asset_rows)
    return stats


def run_sync(
    *,
    batch_size: int,
    resource_id: Optional[str] = None,
    asset_base_url: str = DEFAULT_ASSET_BASE_URL,
) -> Dict[str, int]:
    old_engine = get_old_engine()
    new_engine = get_new_engine()
    reference_type_id_to_uri = load_reference_type_id_to_uri(old_engine)
    uri_to_type_id = load_distribution_uri_to_type_id(new_engine)

    totals = {
        "resources": 0,
        "distribution_rows": 0,
        "download_rows": 0,
        "asset_rows": 0,
    }

    after_resource_id: Optional[str] = None
    while True:
        raw_parent_batch = fetch_parent_batch(
            old_engine,
            batch_size=batch_size,
            after_resource_id=after_resource_id,
            resource_id=resource_id,
        )
        if not raw_parent_batch:
            break

        existing_ids = fetch_existing_resource_ids(
            new_engine, [str(parent["resource_id"]) for parent in raw_parent_batch]
        )
        parent_batch = [
            parent for parent in raw_parent_batch if str(parent["resource_id"]) in existing_ids
        ]
        if not parent_batch:
            logger.info("Skipping batch with no matching imported resources in the new database")
            if resource_id:
                break
            after_resource_id = str(raw_parent_batch[-1]["resource_id"])
            continue

        resource_ids = [str(parent["resource_id"]) for parent in parent_batch]
        parent_model_ids = [str(parent["model_id"]) for parent in parent_batch]

        batch_stats = sync_batch(
            new_engine,
            parents=parent_batch,
            document_distributions_by_resource=fetch_document_distributions(
                old_engine, resource_ids
            ),
            document_downloads_by_resource=fetch_document_downloads(old_engine, resource_ids),
            child_assets_by_parent=fetch_child_assets(old_engine, parent_model_ids),
            reference_type_id_to_uri=reference_type_id_to_uri,
            uri_to_type_id=uri_to_type_id,
            asset_base_url=asset_base_url,
        )

        for key, value in batch_stats.items():
            totals[key] += value

        logger.info(
            "Synced %s resources (%s distributions, %s downloads, %s assets) in this batch",
            batch_stats["resources"],
            batch_stats["distribution_rows"],
            batch_stats["download_rows"],
            batch_stats["asset_rows"],
        )

        if resource_id:
            break

        after_resource_id = str(parent_batch[-1]["resource_id"])

    logger.info(
        (
            "Old-production reference sync complete: %s resources, %s distributions, "
            "%s downloads, %s assets"
        ),
        totals["resources"],
        totals["distribution_rows"],
        totals["download_rows"],
        totals["asset_rows"],
    )
    if resource_id and totals["resources"] == 0:
        raise RuntimeError(
            "Requested resource_id="
            f"{resource_id} was not synced from old production into the API database"
        )
    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync old-production references/assets into the new API database"
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--resource-id", type=str, default=None)
    parser.add_argument("--asset-base-url", type=str, default=DEFAULT_ASSET_BASE_URL)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    run_sync(
        batch_size=args.batch_size,
        resource_id=args.resource_id,
        asset_base_url=args.asset_base_url,
    )


if __name__ == "__main__":
    main()
