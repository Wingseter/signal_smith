from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "signal_smith",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.services.tasks",
        "app.services.tasks.price_tasks",
        "app.services.tasks.analysis_tasks",
        "app.services.tasks.signal_tasks",
        "app.services.tasks.notification_tasks",
        "app.services.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,  # Use local timezone
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes (soft limit)
    worker_prefetch_multiplier=1,
    result_expires=3600,  # 1 hour
    task_acks_late=True,  # Acknowledge after completion
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # 가격 데이터 수집 - 장중 1분마다
    "collect-stock-prices": {
        "task": "app.services.tasks.collect_stock_prices",
        "schedule": 60.0,  # Every minute
        "options": {"queue": "high_priority"},
    },

    # 시장 뉴스 분석 - 5분마다
    "analyze-market-news": {
        "task": "app.services.tasks.analyze_market_news",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"queue": "default"},
    },

    # AI 분석 실행 - 15분마다
    "run-ai-analysis": {
        "task": "app.services.tasks.run_ai_analysis",
        "schedule": 900.0,  # Every 15 minutes
        "options": {"queue": "default"},
    },

    # 신호 모니터링 - 30초마다
    "monitor-signals": {
        "task": "app.services.tasks.monitor_signals",
        "schedule": 30.0,  # Every 30 seconds
        "options": {"queue": "high_priority"},
    },

    # 일간 리포트 - 매일 오후 4시 (장 마감 후)
    "send-daily-report": {
        "task": "app.services.tasks.send_daily_report",
        "schedule": crontab(hour=16, minute=0),
        "options": {"queue": "low_priority"},
    },

    # 데이터 정리 - 매일 새벽 3시
    "cleanup-old-data": {
        "task": "app.services.tasks.cleanup_old_data",
        "schedule": crontab(hour=3, minute=0),
        "args": (90,),  # Keep 90 days
        "options": {"queue": "low_priority"},
    },

    # 퀀트 시그널 스캔 - 15분마다 (상위 500종목)
    "scan-signals": {
        "task": "app.services.tasks.scan_signals",
        "schedule": 900.0,  # Every 15 minutes
        "options": {"queue": "default"},
    },

    # 보유 종목 매도 감시 - 5분마다 (손절/익절/기술 악화)
    "monitor-holdings-sell": {
        "task": "app.services.tasks.monitor_holdings_sell",
        "schedule": 300.0,  # Every 5 minutes
        "options": {"queue": "default"},
    },

    # Council 대기큐 처리 - 2분마다 (장 시작 후 자동 체결)
    "process-council-queue": {
        "task": "app.services.tasks.process_council_queue",
        "schedule": 120.0,  # Every 2 minutes
        "options": {"queue": "high_priority"},
    },

    # 종목 유니버스 갱신 - 매일 08:50 (장 시작 전)
    "refresh-stock-universe": {
        "task": "app.services.tasks.refresh_stock_universe",
        "schedule": crontab(hour=8, minute=50),
        "options": {"queue": "default"},
    },
}

# Queue routing
celery_app.conf.task_routes = {
    "app.services.tasks.collect_stock_prices": {"queue": "high_priority"},
    "app.services.tasks.monitor_signals": {"queue": "high_priority"},
    "app.services.tasks.auto_execute_signal": {"queue": "high_priority"},
    "app.services.tasks.process_council_queue": {"queue": "high_priority"},
    "app.services.tasks.send_notification": {"queue": "high_priority"},
    "app.services.tasks.run_ai_analysis": {"queue": "default"},
    "app.services.tasks.run_single_analysis": {"queue": "default"},
    "app.services.tasks.run_quick_analysis": {"queue": "default"},
    "app.services.tasks.analyze_market_news": {"queue": "default"},
    "app.services.tasks.send_daily_report": {"queue": "low_priority"},
    "app.services.tasks.cleanup_old_data": {"queue": "low_priority"},
    "app.services.tasks.collect_historical_prices": {"queue": "low_priority"},
    "app.services.tasks.scan_signals": {"queue": "default"},
    "app.services.tasks.monitor_holdings_sell": {"queue": "default"},
    "app.services.tasks.refresh_stock_universe": {"queue": "default"},
}
