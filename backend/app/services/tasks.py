"""
Celery tasks for background processing.
"""

from app.core.celery_app import celery_app


@celery_app.task(name="app.services.tasks.collect_stock_prices")
def collect_stock_prices():
    """Collect stock prices for tracked symbols."""
    # This would be implemented with actual API calls
    pass


@celery_app.task(name="app.services.tasks.analyze_market_news")
def analyze_market_news():
    """Analyze market news using Gemini agent."""
    # This would trigger the Gemini news analysis
    pass


@celery_app.task(name="app.services.tasks.run_ai_analysis")
def run_ai_analysis():
    """Run full AI analysis on watchlist stocks."""
    # This would trigger the coordinator to analyze stocks
    pass
