"""rollback_command_type

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-10

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("chk_firewall_command_type", "firewall_commands", type_="check")
    op.create_check_constraint(
        "chk_firewall_command_type",
        "firewall_commands",
        "command_type IN ('create_rule', 'update_rule', 'delete_rule', 'rollback')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_firewall_command_type", "firewall_commands", type_="check")
    op.create_check_constraint(
        "chk_firewall_command_type",
        "firewall_commands",
        "command_type IN ('create_rule', 'update_rule', 'delete_rule')",
    )
