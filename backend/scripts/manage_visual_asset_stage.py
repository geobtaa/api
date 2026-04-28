#!/usr/bin/env python3
"""Prepare, verify, and promote staged durable visual asset tables."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).parent.parent))

from db.config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LIVE_ASSETS_TABLE = "generated_visual_assets"
LIVE_LINKS_TABLE = "generated_visual_asset_links"
DEFAULT_STAGE_SUFFIX = "_stage"
DEFAULT_BACKUP_SCHEMA = "visual_asset_backup"


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def _validate_identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _qident(identifier: str) -> str:
    return f'"{identifier}"'


@dataclass(frozen=True)
class StageNames:
    stage_suffix: str
    backup_schema: str

    @property
    def live_assets(self) -> str:
        return LIVE_ASSETS_TABLE

    @property
    def live_links(self) -> str:
        return LIVE_LINKS_TABLE

    @property
    def stage_assets(self) -> str:
        return f"{self.live_assets}{self.stage_suffix}"

    @property
    def stage_links(self) -> str:
        return f"{self.live_links}{self.stage_suffix}"

    @property
    def stage_links_seq(self) -> str:
        return f"{self.stage_links}_id_seq"

    @property
    def stage_assets_pkey(self) -> str:
        return f"{self.stage_assets}_pkey"

    @property
    def stage_assets_asset_kind_idx(self) -> str:
        return f"ix_{self.stage_assets}_asset_kind"

    @property
    def stage_links_pkey(self) -> str:
        return f"{self.stage_links}_pkey"

    @property
    def stage_links_asset_hash_idx(self) -> str:
        return f"ix_{self.stage_links}_asset_hash"

    @property
    def stage_links_asset_kind_idx(self) -> str:
        return f"ix_{self.stage_links}_asset_kind"

    @property
    def stage_links_resource_id_idx(self) -> str:
        return f"ix_{self.stage_links}_resource_id"

    @property
    def stage_links_source_signature_idx(self) -> str:
        return f"ix_{self.stage_links}_source_signature"

    @property
    def stage_links_unique(self) -> str:
        return f"uq_{self.stage_links}_resource_kind_signature"

    @property
    def stage_links_asset_fk(self) -> str:
        return f"{self.stage_links}_asset_hash_fkey"

    @property
    def stage_links_resource_fk(self) -> str:
        return f"{self.stage_links}_resource_id_fkey"

    @property
    def live_assets_pkey(self) -> str:
        return f"{self.live_assets}_pkey"

    @property
    def live_assets_asset_kind_idx(self) -> str:
        return f"ix_{self.live_assets}_asset_kind"

    @property
    def live_links_seq(self) -> str:
        return f"{self.live_links}_id_seq"

    @property
    def live_links_pkey(self) -> str:
        return f"{self.live_links}_pkey"

    @property
    def live_links_asset_hash_idx(self) -> str:
        return f"ix_{self.live_links}_asset_hash"

    @property
    def live_links_asset_kind_idx(self) -> str:
        return f"ix_{self.live_links}_asset_kind"

    @property
    def live_links_resource_id_idx(self) -> str:
        return f"ix_{self.live_links}_resource_id"

    @property
    def live_links_source_signature_idx(self) -> str:
        return f"ix_{self.live_links}_source_signature"

    @property
    def live_links_unique(self) -> str:
        return "uq_generated_visual_asset_links_resource_kind_signature"

    @property
    def live_links_asset_fk(self) -> str:
        return f"{self.live_links}_asset_hash_fkey"

    @property
    def live_links_resource_fk(self) -> str:
        return f"{self.live_links}_resource_id_fkey"


def _build_names(stage_suffix: str, backup_schema: str) -> StageNames:
    stage_suffix = _validate_identifier(stage_suffix, label="stage suffix")
    if not stage_suffix.startswith("_"):
        raise ValueError("Stage suffix must begin with '_' to avoid name collisions.")
    backup_schema = _validate_identifier(backup_schema, label="backup schema")
    names = StageNames(stage_suffix=stage_suffix, backup_schema=backup_schema)
    if names.stage_assets == names.live_assets or names.stage_links == names.live_links:
        raise ValueError("Stage table names must differ from live table names.")
    if backup_schema == "public":
        raise ValueError("Backup schema must not be public.")
    return names


def _stage_stats(conn, names: StageNames) -> dict[str, int]:
    asset_stats = conn.execute(
        text(
            f"""
            SELECT
                COUNT(*)::bigint AS asset_count,
                COALESCE(SUM(byte_size), 0)::bigint AS asset_byte_sum
            FROM public.{_qident(names.stage_assets)}
            """
        )
    ).one()
    link_count = conn.execute(
        text(
            f"""
            SELECT COUNT(*)::bigint
            FROM public.{_qident(names.stage_links)}
            """
        )
    ).scalar_one()
    dangling_links = conn.execute(
        text(
            f"""
            SELECT COUNT(*)::bigint
            FROM public.{_qident(names.stage_links)} links
            LEFT JOIN public.{_qident(names.stage_assets)} assets
                ON assets.asset_hash = links.asset_hash
            WHERE assets.asset_hash IS NULL
            """
        )
    ).scalar_one()
    return {
        "asset_count": int(asset_stats.asset_count),
        "asset_byte_sum": int(asset_stats.asset_byte_sum),
        "link_count": int(link_count),
        "dangling_links": int(dangling_links),
    }


def _validate_stage(
    conn,
    names: StageNames,
    *,
    expected_asset_count: int,
    expected_asset_byte_sum: int,
    expected_link_count: int,
) -> dict[str, int]:
    stats = _stage_stats(conn, names)
    if stats["asset_count"] != expected_asset_count:
        raise RuntimeError(
            f"Stage asset count mismatch: expected {expected_asset_count}, got {stats['asset_count']}"
        )
    if stats["asset_byte_sum"] != expected_asset_byte_sum:
        raise RuntimeError(
            "Stage asset byte sum mismatch: "
            f"expected {expected_asset_byte_sum}, got {stats['asset_byte_sum']}"
        )
    if stats["link_count"] != expected_link_count:
        raise RuntimeError(
            f"Stage link count mismatch: expected {expected_link_count}, got {stats['link_count']}"
        )
    if stats["dangling_links"] != 0:
        raise RuntimeError(f"Stage link integrity check failed: {stats['dangling_links']} dangling rows")
    return stats


def _ensure_assets_trigger(conn) -> None:
    conn.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION update_generated_visual_assets_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE 'plpgsql';
            """
        )
    )
    conn.execute(
        text(
            f"""
            DROP TRIGGER IF EXISTS trigger_update_generated_visual_assets_updated_at
            ON public.{_qident(LIVE_ASSETS_TABLE)};
            """
        )
    )
    conn.execute(
        text(
            f"""
            CREATE TRIGGER trigger_update_generated_visual_assets_updated_at
                BEFORE UPDATE ON public.{_qident(LIVE_ASSETS_TABLE)}
                FOR EACH ROW
                EXECUTE FUNCTION update_generated_visual_assets_updated_at();
            """
        )
    )


def prepare_stage(engine, names: StageNames) -> None:
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS public.{_qident(names.stage_links)} CASCADE'))
        conn.execute(text(f'DROP TABLE IF EXISTS public.{_qident(names.stage_assets)} CASCADE'))
        conn.execute(text(f'DROP SEQUENCE IF EXISTS public.{_qident(names.stage_links_seq)} CASCADE'))
        conn.execute(
            text(
                f"""
                CREATE TABLE public.{_qident(names.stage_assets)} (
                    asset_hash VARCHAR(64) PRIMARY KEY,
                    asset_kind VARCHAR(64) NOT NULL,
                    content_type VARCHAR(255) NOT NULL,
                    body BYTEA NOT NULL,
                    byte_size INTEGER NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
                );
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE INDEX {_qident(names.stage_assets_asset_kind_idx)}
                ON public.{_qident(names.stage_assets)} (asset_kind);
                """
            )
        )
        conn.execute(text(f'CREATE SEQUENCE public.{_qident(names.stage_links_seq)} AS INTEGER'))
        conn.execute(
            text(
                f"""
                CREATE TABLE public.{_qident(names.stage_links)} (
                    id INTEGER NOT NULL DEFAULT nextval('public.{names.stage_links_seq}'::regclass),
                    resource_id VARCHAR(255) NOT NULL,
                    asset_hash VARCHAR(64) NOT NULL,
                    asset_kind VARCHAR(64) NOT NULL,
                    source_signature VARCHAR(64) NOT NULL DEFAULT '',
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                    CONSTRAINT {_qident(names.stage_links_pkey)} PRIMARY KEY (id),
                    CONSTRAINT {_qident(names.stage_links_unique)}
                        UNIQUE (resource_id, asset_kind, source_signature),
                    CONSTRAINT {_qident(names.stage_links_resource_fk)}
                        FOREIGN KEY (resource_id)
                        REFERENCES public.resources(id)
                        ON DELETE CASCADE,
                    CONSTRAINT {_qident(names.stage_links_asset_fk)}
                        FOREIGN KEY (asset_hash)
                        REFERENCES public.{_qident(names.stage_assets)}(asset_hash)
                        ON DELETE CASCADE
                );
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER SEQUENCE public.{_qident(names.stage_links_seq)}
                OWNED BY public.{_qident(names.stage_links)}.id;
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE INDEX {_qident(names.stage_links_asset_hash_idx)}
                ON public.{_qident(names.stage_links)} (asset_hash);
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE INDEX {_qident(names.stage_links_asset_kind_idx)}
                ON public.{_qident(names.stage_links)} (asset_kind);
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE INDEX {_qident(names.stage_links_resource_id_idx)}
                ON public.{_qident(names.stage_links)} (resource_id);
                """
            )
        )
        conn.execute(
            text(
                f"""
                CREATE INDEX {_qident(names.stage_links_source_signature_idx)}
                ON public.{_qident(names.stage_links)} (source_signature);
                """
            )
        )
    logger.info(
        "Prepared staged visual asset tables: public.%s, public.%s",
        names.stage_assets,
        names.stage_links,
    )


def verify_stage(
    engine,
    names: StageNames,
    *,
    expected_asset_count: int,
    expected_asset_byte_sum: int,
    expected_link_count: int,
) -> None:
    with engine.connect() as conn:
        stats = _validate_stage(
            conn,
            names,
            expected_asset_count=expected_asset_count,
            expected_asset_byte_sum=expected_asset_byte_sum,
            expected_link_count=expected_link_count,
        )
    logger.info(
        "Stage verified: assets=%s asset_bytes=%s links=%s",
        stats["asset_count"],
        stats["asset_byte_sum"],
        stats["link_count"],
    )


def cutover_stage(
    engine,
    names: StageNames,
    *,
    expected_asset_count: int,
    expected_asset_byte_sum: int,
    expected_link_count: int,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                LOCK TABLE
                    public.{_qident(names.live_links)},
                    public.{_qident(names.live_assets)},
                    public.{_qident(names.stage_links)},
                    public.{_qident(names.stage_assets)}
                IN ACCESS EXCLUSIVE MODE;
                """
            )
        )
        stats = _validate_stage(
            conn,
            names,
            expected_asset_count=expected_asset_count,
            expected_asset_byte_sum=expected_asset_byte_sum,
            expected_link_count=expected_link_count,
        )
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {_qident(names.backup_schema)}'))
        conn.execute(
            text(f'DROP TABLE IF EXISTS {_qident(names.backup_schema)}.{_qident(names.live_links)} CASCADE')
        )
        conn.execute(
            text(f'DROP TABLE IF EXISTS {_qident(names.backup_schema)}.{_qident(names.live_assets)} CASCADE')
        )
        conn.execute(
            text(
                f'ALTER TABLE public.{_qident(names.live_links)} SET SCHEMA {_qident(names.backup_schema)}'
            )
        )
        conn.execute(
            text(
                f'ALTER TABLE public.{_qident(names.live_assets)} SET SCHEMA {_qident(names.backup_schema)}'
            )
        )
        conn.execute(
            text(
                f'ALTER TABLE public.{_qident(names.stage_assets)} RENAME TO {_qident(names.live_assets)}'
            )
        )
        conn.execute(
            text(
                f'ALTER TABLE public.{_qident(names.stage_links)} RENAME TO {_qident(names.live_links)}'
            )
        )
        conn.execute(
            text(
                f'ALTER SEQUENCE public.{_qident(names.stage_links_seq)} RENAME TO {_qident(names.live_links_seq)}'
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE public.{_qident(names.live_assets)}
                RENAME CONSTRAINT {_qident(names.stage_assets_pkey)}
                TO {_qident(names.live_assets_pkey)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER INDEX public.{_qident(names.stage_assets_asset_kind_idx)}
                RENAME TO {_qident(names.live_assets_asset_kind_idx)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE public.{_qident(names.live_links)}
                RENAME CONSTRAINT {_qident(names.stage_links_pkey)}
                TO {_qident(names.live_links_pkey)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE public.{_qident(names.live_links)}
                RENAME CONSTRAINT {_qident(names.stage_links_unique)}
                TO {_qident(names.live_links_unique)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE public.{_qident(names.live_links)}
                RENAME CONSTRAINT {_qident(names.stage_links_asset_fk)}
                TO {_qident(names.live_links_asset_fk)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER TABLE public.{_qident(names.live_links)}
                RENAME CONSTRAINT {_qident(names.stage_links_resource_fk)}
                TO {_qident(names.live_links_resource_fk)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER INDEX public.{_qident(names.stage_links_asset_hash_idx)}
                RENAME TO {_qident(names.live_links_asset_hash_idx)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER INDEX public.{_qident(names.stage_links_asset_kind_idx)}
                RENAME TO {_qident(names.live_links_asset_kind_idx)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER INDEX public.{_qident(names.stage_links_resource_id_idx)}
                RENAME TO {_qident(names.live_links_resource_id_idx)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                ALTER INDEX public.{_qident(names.stage_links_source_signature_idx)}
                RENAME TO {_qident(names.live_links_source_signature_idx)};
                """
            )
        )
        conn.execute(
            text(
                f"""
                SELECT setval(
                    'public.{names.live_links_seq}'::regclass,
                    COALESCE((SELECT MAX(id) FROM public.{_qident(names.live_links)}), 1),
                    EXISTS(SELECT 1 FROM public.{_qident(names.live_links)})
                );
                """
            )
        )
        _ensure_assets_trigger(conn)
        conn.execute(text(f'ANALYZE public.{_qident(names.live_assets)}'))
        conn.execute(text(f'ANALYZE public.{_qident(names.live_links)}'))
    logger.info(
        "Cutover complete: live assets=%s live links=%s backup schema=%s",
        stats["asset_count"],
        stats["link_count"],
        names.backup_schema,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage staged durable visual asset imports before live cutover."
    )
    parser.add_argument(
        "command",
        choices=("prepare", "verify", "cutover"),
        help="Stage management action to run.",
    )
    parser.add_argument(
        "--stage-suffix",
        default=DEFAULT_STAGE_SUFFIX,
        help=f"Suffix appended to live table names for staging (default: {DEFAULT_STAGE_SUFFIX}).",
    )
    parser.add_argument(
        "--backup-schema",
        default=DEFAULT_BACKUP_SCHEMA,
        help=f"Schema that keeps the prior live tables after cutover (default: {DEFAULT_BACKUP_SCHEMA}).",
    )
    parser.add_argument("--expected-asset-count", type=int, help="Expected staged asset row count.")
    parser.add_argument(
        "--expected-asset-byte-sum",
        type=int,
        help="Expected staged SUM(byte_size) for asset rows.",
    )
    parser.add_argument("--expected-link-count", type=int, help="Expected staged link row count.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    names = _build_names(args.stage_suffix, args.backup_schema)
    engine = create_engine(_sync_database_url(), pool_pre_ping=True)

    if args.command == "prepare":
        prepare_stage(engine, names)
        return 0

    if args.expected_asset_count is None or args.expected_asset_byte_sum is None or args.expected_link_count is None:
        raise SystemExit(
            "verify and cutover require --expected-asset-count, "
            "--expected-asset-byte-sum, and --expected-link-count"
        )

    if args.command == "verify":
        verify_stage(
            engine,
            names,
            expected_asset_count=args.expected_asset_count,
            expected_asset_byte_sum=args.expected_asset_byte_sum,
            expected_link_count=args.expected_link_count,
        )
        return 0

    cutover_stage(
        engine,
        names,
        expected_asset_count=args.expected_asset_count,
        expected_asset_byte_sum=args.expected_asset_byte_sum,
        expected_link_count=args.expected_link_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
