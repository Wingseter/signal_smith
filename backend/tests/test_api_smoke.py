"""Smoke tests: verify all route modules import without errors."""

import importlib
import pytest


ROUTE_MODULES = [
    "app.api.routes.auth",
    "app.api.routes.stocks",
    "app.api.routes.portfolio",
    "app.api.routes.trading",
    "app.api.routes.analysis",
    "app.api.routes.notifications",
    "app.api.routes.backtest",
    "app.api.routes.performance",
    "app.api.routes.optimizer",
    "app.api.routes.sectors",
    "app.api.routes.reports",
    "app.api.routes.council",
    "app.api.routes.news_monitor",
    "app.api.routes.signals",
]


@pytest.mark.parametrize("module_path", ROUTE_MODULES)
def test_route_module_imports(module_path):
    """Each route module should import and expose a ``router``."""
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "router"), f"{module_path} missing 'router'"


def test_websocket_handler_imports():
    import app.api.websocket.handler as ws
    assert hasattr(ws, "router")
