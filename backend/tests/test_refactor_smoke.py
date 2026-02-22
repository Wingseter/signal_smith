import inspect


def test_trading_signal_has_expected_fields():
    from app.models.transaction import TradingSignal

    columns = set(TradingSignal.__table__.columns.keys())
    assert "is_executed" in columns
    assert "signal_type" in columns
    assert "strength" in columns


def test_tasks_do_not_use_legacy_signal_fields():
    from app.services import tasks

    source = inspect.getsource(tasks)
    assert "signal.executed" not in source
    assert "signal.entry_price" not in source
    assert "signal.executed_at" not in source
    assert "StockPrice.stock_id" not in source


def test_performance_route_imports():
    # Import smoke: should not raise on module import
    import app.api.routes.performance as performance_route

    assert performance_route.router is not None
