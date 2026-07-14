"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-14

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("account_type", sa.Text(), nullable=False, server_default="individual"),
        sa.Column("tax_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("account_type IN ('individual', 'multiempresa')", name="chk_account_type"),
    )

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "firewalls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("pfsense_version", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "agent_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("processing_status", sa.Text(), nullable=False, server_default="queued"),
    )

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "alert_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=True),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Numeric(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alert_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("operator IN ('gt', 'gte', 'lt', 'lte', 'eq')", name="chk_alert_rule_operator"),
    )

    op.create_table(
        "alert_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=True),
        sa.Column("alert_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(finding_id IS NOT NULL AND alert_rule_id IS NULL) OR "
            "(finding_id IS NULL AND alert_rule_id IS NOT NULL)",
            name="chk_alert_delivery_origin",
        ),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("tier", sa.Text(), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'past_due', 'canceled')", name="chk_subscription_status"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "firewall_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("command_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("preview", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending_confirmation"),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "command_type IN ('create_rule', 'update_rule', 'delete_rule')",
            name="chk_firewall_command_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending_confirmation', 'confirmed', 'sent_to_agent', 'applied', "
            "'failed', 'rolled_back', 'expired')",
            name="chk_firewall_command_status",
        ),
    )

    op.create_table(
        "remote_change_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("firewall_command_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewall_commands.id"), nullable=False, unique=True),
        sa.Column("firewall_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firewalls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("before_state", postgresql.JSONB(), nullable=False),
        sa.Column("after_state", postgresql.JSONB(), nullable=False),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("rolled_back_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rolled_back_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_hash", sa.Text(), nullable=False),
    )

    # Indexes (docs/specs/fase4-banco-de-dados.md secao 4)
    op.create_index("idx_organizations_account_id", "organizations", ["account_id"])
    op.create_index("idx_users_account_id", "users", ["account_id"])
    op.create_index("idx_firewalls_organization_id", "firewalls", ["organization_id"])
    op.create_index("idx_agent_tokens_firewall_id", "agent_tokens", ["firewall_id"])
    op.create_index(
        "idx_snapshots_firewall_id_received_at",
        "snapshots",
        ["firewall_id", sa.text("received_at DESC")],
    )
    op.create_index(
        "idx_snapshots_processing_status",
        "snapshots",
        ["processing_status"],
        postgresql_where=sa.text("processing_status = 'queued'"),
    )
    op.create_index(
        "idx_findings_firewall_id_status_severity",
        "findings",
        ["firewall_id", "status", "severity"],
    )
    op.create_index("idx_findings_snapshot_id", "findings", ["snapshot_id"])
    op.create_index("idx_alert_channels_organization_id", "alert_channels", ["organization_id"])
    op.create_index("idx_alert_rules_organization_id", "alert_rules", ["organization_id"])
    op.create_index("idx_alert_deliveries_alert_channel_id", "alert_deliveries", ["alert_channel_id"])
    op.create_index(
        "idx_firewall_commands_firewall_id_status",
        "firewall_commands",
        ["firewall_id", "status"],
    )
    # Extra index, not in fase4-banco-de-dados.md sec 4 but required by
    # PLANO-DESENVOLVIMENTO.md Fase 1 item 3 (polling/expiry critical path).
    op.create_index(
        "idx_firewall_commands_status_expires_at",
        "firewall_commands",
        ["status", "expires_at"],
        postgresql_where=sa.text("status IN ('pending_confirmation', 'confirmed')"),
    )
    op.create_index("idx_remote_change_logs_firewall_id", "remote_change_logs", ["firewall_id"])
    op.create_index("idx_audit_logs_organization_id", "audit_logs", ["organization_id"])


def downgrade() -> None:
    op.drop_table("remote_change_logs")
    op.drop_table("firewall_commands")
    op.drop_table("audit_logs")
    op.drop_table("subscriptions")
    op.drop_table("alert_deliveries")
    op.drop_table("alert_rules")
    op.drop_table("alert_channels")
    op.drop_table("findings")
    op.drop_table("snapshots")
    op.drop_table("agent_tokens")
    op.drop_table("firewalls")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("accounts")
