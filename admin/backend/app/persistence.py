"""Shared relational metadata and actor identities, independent of any domain."""

from sqlalchemy import CheckConstraint, Column, MetaData, Table, Text, UniqueConstraint, Uuid

metadata = MetaData()

actors = Table(
    "actors",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("subject_key", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    UniqueConstraint("kind", "subject_key", name="actors_subject_key"),
    CheckConstraint("kind IN ('user', 'service_account', 'system')", name="actors_kind"),
)
