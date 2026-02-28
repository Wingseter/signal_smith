"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-01

Baseline migration capturing existing schema created by Base.metadata.create_all().
For an existing database, run `alembic stamp head` to mark this revision
as applied without executing DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # --- stocks ---
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("market_cap", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stocks_symbol"), "stocks", ["symbol"], unique=True)

    # --- stock_prices ---
    op.create_table(
        "stock_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(15, 2), nullable=False),
        sa.Column("high", sa.Numeric(15, 2), nullable=False),
        sa.Column("low", sa.Numeric(15, 2), nullable=False),
        sa.Column("close", sa.Numeric(15, 2), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("change_percent", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_prices_symbol"), "stock_prices", ["symbol"])
    op.create_index(op.f("ix_stock_prices_date"), "stock_prices", ["date"])

    # --- stock_analyses ---
    op.create_table(
        "stock_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("analysis_type", sa.String(50), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("recommendation", sa.String(20), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stock_analyses_symbol"), "stock_analyses", ["symbol"])

    # --- portfolios ---
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolios_user_id"), "portfolios", ["user_id"])

    # --- portfolio_holdings ---
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_buy_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("current_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("profit_loss", sa.Numeric(15, 2), nullable=True),
        sa.Column("profit_loss_percent", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolio_holdings_portfolio_id"), "portfolio_holdings", ["portfolio_id"])
    op.create_index(op.f("ix_portfolio_holdings_symbol"), "portfolio_holdings", ["symbol"])

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("transaction_type", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(15, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("order_id", sa.String(100), nullable=True),
        sa.Column("filled_quantity", sa.Integer(), nullable=True),
        sa.Column("filled_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("commission", sa.Numeric(15, 2), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("ai_recommendation", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"])
    op.create_index(op.f("ix_transactions_symbol"), "transactions", ["symbol"])

    # --- trading_signals ---
    op.create_table(
        "trading_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("company_name", sa.String(100), nullable=True),
        sa.Column("signal_type", sa.String(10), nullable=False),
        sa.Column("strength", sa.Numeric(5, 2), nullable=False),
        sa.Column("source_agent", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("target_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("stop_loss", sa.Numeric(15, 2), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("signal_status", sa.String(20), nullable=True),
        sa.Column("trigger_details", sa.JSON(), nullable=True),
        sa.Column("holding_deadline", sa.Date(), nullable=True),
        sa.Column("quant_score", sa.Integer(), nullable=True),
        sa.Column("fundamental_score", sa.Integer(), nullable=True),
        sa.Column("allocation_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("suggested_amount", sa.Integer(), nullable=True),
        sa.Column("is_executed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trading_signals_symbol"), "trading_signals", ["symbol"])

    # --- watchlists ---
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("alert_price_above", sa.Numeric(15, 2), nullable=True),
        sa.Column("alert_price_below", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_watchlists_user_id"), "watchlists", ["user_id"])
    op.create_index(op.f("ix_watchlists_symbol"), "watchlists", ["symbol"])

    # --- backtest_results ---
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("strategy_name", sa.String(50), nullable=False),
        sa.Column("strategy_display_name", sa.String(100), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("final_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_return_pct", sa.Numeric(10, 4), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("losing_trades", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("trades", sa.JSON(), nullable=True),
        sa.Column("equity_curve", sa.JSON(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_results_user_id"), "backtest_results", ["user_id"])

    # --- backtest_comparisons ---
    op.create_table(
        "backtest_comparisons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initial_capital", sa.Numeric(18, 2), nullable=False),
        sa.Column("strategies", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("best_strategy", sa.String(50), nullable=True),
        sa.Column("ranking", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_comparisons_user_id"), "backtest_comparisons", ["user_id"])


def downgrade() -> None:
    op.drop_table("backtest_comparisons")
    op.drop_table("backtest_results")
    op.drop_table("watchlists")
    op.drop_table("trading_signals")
    op.drop_table("transactions")
    op.drop_table("portfolio_holdings")
    op.drop_table("portfolios")
    op.drop_table("stock_analyses")
    op.drop_table("stock_prices")
    op.drop_table("stocks")
    op.drop_table("users")
