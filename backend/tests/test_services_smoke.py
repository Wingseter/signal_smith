"""Smoke tests: verify all service singletons import without errors."""

import importlib


def test_council_orchestrator_imports():
    from app.services.council import council_orchestrator
    assert council_orchestrator is not None


def test_signal_scanner_imports():
    from app.services.signals import signal_scanner
    assert signal_scanner is not None


def test_trading_service_imports():
    from app.services.trading_service import trading_service
    assert trading_service is not None


def test_stock_service_imports():
    from app.services.stock_service import stock_service
    assert stock_service is not None


def test_kiwoom_client_imports():
    from app.services.kiwoom.rest_client import kiwoom_client
    assert kiwoom_client is not None


def test_celery_app_imports():
    from app.core.celery_app import celery_app
    assert celery_app is not None


def test_database_base_imports():
    from app.core.database import Base, engine, async_session_maker
    assert Base is not None
    assert engine is not None
    assert async_session_maker is not None
