"""add signal_events audit table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("action", sa.String(20), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["trading_signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_events_signal_id", "signal_events", ["signal_id"])
    op.create_index("ix_signal_events_event_type", "signal_events", ["event_type"])
    op.create_index("ix_signal_events_symbol", "signal_events", ["symbol"])
    op.create_index("ix_signal_events_created_at", "signal_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_signal_events_created_at", table_name="signal_events")
    op.drop_index("ix_signal_events_symbol", table_name="signal_events")
    op.drop_index("ix_signal_events_event_type", table_name="signal_events")
    op.drop_index("ix_signal_events_signal_id", table_name="signal_events")
    op.drop_table("signal_events")
