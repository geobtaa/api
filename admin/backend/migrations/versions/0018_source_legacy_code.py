"""Make imported Source legacy codes queryable without treating them as identity."""

import re

from alembic import op
from sqlalchemy import text

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

LEGACY_LINE = re.compile(r"^legacy_code: ([^\r\n]+)$", re.MULTILINE)


def upgrade():
    op.execute("ALTER TABLE sources ADD COLUMN legacy_code VARCHAR(128)")
    op.execute("CREATE INDEX sources_legacy_code ON sources (legacy_code, source_id)")
    connection = op.get_bind()
    for source_id, notes in connection.execute(text("SELECT source_id, admin_notes FROM sources")):
        values = LEGACY_LINE.findall(notes)
        if len(values) == 1 and len(values[0]) <= 128:
            connection.execute(
                text("UPDATE sources SET legacy_code = :code WHERE source_id = :source_id"),
                {"code": values[0], "source_id": source_id},
            )


def downgrade():
    op.execute("DROP INDEX sources_legacy_code")
    op.execute("ALTER TABLE sources DROP COLUMN legacy_code")
