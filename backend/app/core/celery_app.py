from celery import Celery

from app.config import settings

celery_app = Celery(
    "signal_smith",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.services.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    worker_prefetch_multiplier=1,
    result_expires=3600,  # 1 hour
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "collect-stock-prices": {
        "task": "app.services.tasks.collect_stock_prices",
        "schedule": 60.0,  # Every minute during market hours
    },
    "analyze-market-news": {
        "task": "app.services.tasks.analyze_market_news",
        "schedule": 300.0,  # Every 5 minutes
    },
    "run-ai-analysis": {
        "task": "app.services.tasks.run_ai_analysis",
        "schedule": 900.0,  # Every 15 minutes
    },
}
