"""Celery tasks package.

Re-exports all tasks so that ``celery_app.conf.include`` and
``beat_schedule`` task names (``app.services.tasks.<name>``) remain valid.
"""

from .price_tasks import collect_stock_prices, collect_historical_prices  # noqa: F401
from .analysis_tasks import (  # noqa: F401
    analyze_market_news,
    run_ai_analysis,
    run_single_analysis,
    run_quick_analysis,
)
from .monitoring_tasks import monitor_signals, monitor_holdings_sell  # noqa: F401
from .execution_tasks import (  # noqa: F401
    auto_execute_signal,
    process_council_queue,
    rebalance_holdings,
)
from .scanning_tasks import (  # noqa: F401
    scan_signals,
    refresh_stock_universe,
    refresh_account_summary,
)
from .notification_tasks import send_notification, send_daily_report  # noqa: F401
from .maintenance_tasks import cleanup_old_data  # noqa: F401

# Also export helpers for backward compat with existing test
from ._common import run_async, is_market_hours  # noqa: F401
