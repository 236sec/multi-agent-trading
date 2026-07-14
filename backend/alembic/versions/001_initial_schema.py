"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tables with no FK dependencies ---
    op.create_table(
        "watchlist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("added_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "market_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("returns", sa.Float(), nullable=True),
        sa.UniqueConstraint("ticker", "date"),
    )

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("quantity", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "portfolio_nav",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("drawdown_pct", sa.Float(), nullable=True),
    )

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),  # BUY, SELL, HOLD
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),  # pending, processed
    )

    op.create_table(
        "event_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "message_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_type", sa.String(50), nullable=False, index=True),
        sa.Column("strategy_id", sa.String(50), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("retries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Tables with FK dependencies (signals must exist first) ---
    op.create_table(
        "risk_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("position_check_pct", sa.Float(), nullable=True),
        sa.Column("sector_check_pct", sa.Float(), nullable=True),
        sa.Column("drawdown_check_pct", sa.Float(), nullable=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),  # BUY, SELL
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("order_type", sa.String(20), nullable=False, server_default=sa.text("'MARKET'")),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'approved_pending_human'")),
        sa.Column("webull_order_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop FK-dependent tables first, then parent tables
    op.drop_table("orders")
    op.drop_table("risk_decisions")
    op.drop_table("message_queue")
    op.drop_table("event_log")
    op.drop_table("signals")
    op.drop_table("portfolio_nav")
    op.drop_table("positions")
    op.drop_table("market_data")
    op.drop_table("watchlist")
