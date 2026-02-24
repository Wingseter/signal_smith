"""AI analysis tasks."""

import logging
from typing import List, Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_sync_db
from app.config import settings

from ._common import is_market_hours, run_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.services.tasks.analyze_market_news",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def analyze_market_news(self):
    """Analyze market news using Gemini agent."""

    async def _analyze():
        from app.agents.gemini_agent import GeminiNewsAgent

        agent = GeminiNewsAgent()
        market_sentiment = await agent.get_market_sentiment("KOSPI")

        logger.info(f"Market sentiment analysis: {market_sentiment.get('overall_sentiment', 'unknown')}")

        from app.core.redis import get_redis
        import json

        redis = await get_redis()
        if redis:
            await redis.setex("market_sentiment:KOSPI", 300, json.dumps(market_sentiment))

        return market_sentiment

    try:
        market_sentiment = run_async(_analyze())
        return {
            "status": "success",
            "sentiment": market_sentiment.get("overall_sentiment"),
            "score": market_sentiment.get("sentiment_score"),
        }
    except Exception as e:
        logger.error(f"Market news analysis failed: {e}")
        self.retry(exc=e)


@celery_app.task(
    name="app.services.tasks.run_ai_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def run_ai_analysis(self):
    """Run full AI analysis on watchlist stocks."""
    if not is_market_hours():
        logger.info("Market is closed. Skipping AI analysis.")
        return {"status": "skipped", "reason": "market_closed"}

    try:
        with get_sync_db() as db:
            from app.models.portfolio import Watchlist

            watchlist_items = db.execute(select(Watchlist.symbol).distinct()).scalars().all()

            if not watchlist_items:
                watchlist_items = ["005930", "000660", "035420", "035720", "051910"]

            logger.info(f"Running AI analysis for {len(watchlist_items)} stocks")

            from app.agents.coordinator import AgentCoordinator

            coordinator = AgentCoordinator()
            results = []
            signals_generated = 0

            for symbol in watchlist_items[:10]:
                try:
                    result = run_async(coordinator.run_analysis(symbol=symbol, save_to_db=True))
                    final = result.get("final_recommendation") or {}
                    results.append({
                        "symbol": symbol,
                        "score": final.get("overall_score"),
                        "recommendation": final.get("recommendation"),
                    })
                    if result.get("trading_signal"):
                        signals_generated += 1
                except Exception as e:
                    logger.error(f"Analysis failed for {symbol}: {e}")
                    results.append({"symbol": symbol, "error": str(e)})

            return {
                "status": "success",
                "analyzed": len(results),
                "signals_generated": signals_generated,
                "results": results,
            }

    except Exception as e:
        logger.error(f"AI analysis task failed: {e}")
        self.retry(exc=e)


@celery_app.task(name="app.services.tasks.run_single_analysis")
def run_single_analysis(symbol: str, analysis_types: Optional[List[str]] = None):
    """Run AI analysis for a single stock (background task)."""
    try:
        from app.agents.coordinator import AgentCoordinator

        coordinator = AgentCoordinator()
        result = run_async(coordinator.run_analysis(symbol=symbol, save_to_db=True))
        final = result.get("final_recommendation") or {}
        confidence = final.get("confidence")
        if analysis_types:
            logger.info(
                "run_single_analysis received analysis_types=%s (currently ignored by coordinator)",
                analysis_types,
            )

        return {
            "status": "success",
            "symbol": symbol,
            "final_score": final.get("overall_score"),
            "recommendation": final.get("recommendation"),
            "confidence": confidence,
            "signal_generated": result.get("trading_signal") is not None,
        }

    except Exception as e:
        logger.error(f"Single analysis failed for {symbol}: {e}")
        return {"status": "error", "symbol": symbol, "error": str(e)}


@celery_app.task(name="app.services.tasks.run_quick_analysis")
def run_quick_analysis(symbol: str):
    """Run quick analysis (technical + quant only) for faster results."""
    try:
        from app.agents.coordinator import AgentCoordinator

        coordinator = AgentCoordinator()
        result = run_async(coordinator.run_quick_analysis(symbol))

        return {
            "status": "success",
            "symbol": symbol,
            "final_score": result.get("overall_score"),
            "recommendation": result.get("recommendation"),
        }

    except Exception as e:
        logger.error(f"Quick analysis failed for {symbol}: {e}")
        return {"status": "error", "symbol": symbol, "error": str(e)}
