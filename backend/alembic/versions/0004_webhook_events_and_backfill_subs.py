"""webhook_events table + backfill subscriptions for existing accounts

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20

Fase 8 (billing) prerequisites:
- New `webhook_events` table for Stripe webhook idempotency (dedup by event_id).
- Backfill: any pre-existing account without a `subscriptions` row gets a
  default free/active subscription. From Fase 8 onwards, `RegisterIndividualAccount`
  and `RegisterMultiempresaAccount` create the row at register time, so this
  backfill is only needed for accounts created before this migration ran.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("event_id", sa.Text, nullable=False, unique=True),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        """
        INSERT INTO subscriptions (account_id, tier, status)
        SELECT id, 'free', 'active'
        FROM accounts
        WHERE id NOT IN (SELECT account_id FROM subscriptions)
        """
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    # Backfill is not reversible without knowing which rows we inserted;
    # leaving subscriptions in place on downgrade is safe (they don't break anything).
