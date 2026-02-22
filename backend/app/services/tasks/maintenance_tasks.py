"""Data cleanup and maintenance tasks."""

import logging
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.stock import StockAnalysis
from app.models.transaction import TradingSignal

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.tasks.cleanup_old_data")
def cleanup_old_data(days: int = 90):
    """Clean up old analysis data and expired signals."""
    try:
        with get_sync_db() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            deleted_analyses = db.execute(
                StockAnalysis.__table__.delete().where(StockAnalysis.created_at < cutoff_date)
            )

            db.execute(
                TradingSignal.__table__.update()
                .where(TradingSignal.created_at < cutoff_date)
                .values(is_active=False)
            )

            db.commit()

            return {
                "status": "success",
                "deleted_analyses": deleted_analyses.rowcount,
                "cutoff_date": cutoff_date.isoformat(),
            }

    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        return {"status": "error", "error": str(e)}
