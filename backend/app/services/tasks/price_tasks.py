"""Price data collection tasks."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.models.stock import Stock, StockPrice

from ._common import is_market_hours, run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.services.tasks.collect_stock_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def collect_stock_prices(self):
    """Collect real-time stock prices for all tracked symbols."""
    if not is_market_hours():
        logger.info("Market is closed. Skipping price collection.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            stocks = db.execute(select(Stock).where(Stock.is_active == True)).scalars().all()

            if not stocks:
                logger.info("No active stocks to track.")
                return {"status": "skipped", "reason": "no_stocks"}

            symbols = [stock.symbol for stock in stocks]
            logger.info(f"Collecting prices for {len(symbols)} stocks")

            from app.services.kiwoom.rest_client import KiwoomRestClient

            client = KiwoomRestClient()
            collected_count = 0
            errors = []

            for symbol in symbols:
                try:
                    price_data = run_async(client.get_current_price(symbol))

                    if price_data:
                        stock_price = StockPrice(
                            symbol=symbol,
                            date=datetime.utcnow(),
                            open=price_data.get("open", 0),
                            high=price_data.get("high", 0),
                            low=price_data.get("low", 0),
                            close=price_data.get("close", 0),
                            volume=price_data.get("volume", 0),
                            change_percent=price_data.get(
                                "change_percent", price_data.get("change_rate", 0)
                            ),
                        )
                        db.add(stock_price)
                        collected_count += 1
                except Exception as e:
                    errors.append({"symbol": symbol, "error": str(e)})
                    logger.error(f"Error collecting price for {symbol}: {e}")

            db.commit()

            result = {
                "status": "success",
                "collected": collected_count,
                "total": len(symbols),
                "errors": errors[:10] if errors else [],
            }
            logger.info(f"Price collection complete: {result}")
            return result

    except Exception as e:
        logger.error(f"Price collection failed: {e}")
        self.retry(exc=e)


@celery_app.task(name="app.services.tasks.collect_historical_prices")
def collect_historical_prices(symbol: str, days: int = 365):
    """Collect historical price data for a specific stock."""
    try:
        with get_sync_db() as db:
            stock = db.execute(select(Stock).where(Stock.symbol == symbol)).scalar_one_or_none()

            if not stock:
                return {"status": "error", "reason": "stock_not_found"}

            from app.services.kiwoom.rest_client import KiwoomRestClient

            client = KiwoomRestClient()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            history = run_async(
                client.get_price_history(
                    symbol,
                    start_date.strftime("%Y%m%d"),
                    end_date.strftime("%Y%m%d"),
                )
            )

            if not history:
                return {"status": "error", "reason": "no_data"}

            count = 0
            for item in history:
                date_value = item.get("date")
                if isinstance(date_value, str):
                    try:
                        if len(date_value) == 8 and date_value.isdigit():
                            date_value = datetime.strptime(date_value, "%Y%m%d")
                        else:
                            date_value = datetime.fromisoformat(date_value)
                    except ValueError:
                        continue

                existing = db.execute(
                    select(StockPrice).where(
                        StockPrice.symbol == stock.symbol,
                        StockPrice.date == date_value,
                    )
                ).scalar_one_or_none()

                if not existing:
                    price = StockPrice(
                        symbol=stock.symbol,
                        date=date_value,
                        open=item["open"],
                        high=item["high"],
                        low=item["low"],
                        close=item["close"],
                        volume=item["volume"],
                        change_percent=item.get("change_percent", 0),
                    )
                    db.add(price)
                    count += 1

            db.commit()
            return {"status": "success", "symbol": symbol, "records_added": count}

    except Exception as e:
        logger.error(f"Historical price collection failed for {symbol}: {e}")
        return {"status": "error", "error": str(e)}
