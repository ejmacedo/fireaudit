"""snapshot_indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "agent_tokens_token_hash_idx",
        "agent_tokens",
        ["token_hash"],
    )
    op.create_index(
        "snapshots_queued_idx",
        "snapshots",
        ["received_at"],
        postgresql_where=sa.text("processing_status = 'queued'"),
    )


def downgrade() -> None:
    op.drop_index("snapshots_queued_idx", table_name="snapshots")
    op.drop_index("agent_tokens_token_hash_idx", table_name="agent_tokens")
