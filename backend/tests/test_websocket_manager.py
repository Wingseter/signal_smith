"""Tests for BaseConnectionManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.websocket import BaseConnectionManager


@pytest.fixture
def manager():
    return BaseConnectionManager("test")


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnect:
    @pytest.mark.asyncio
    async def test_accept_and_add(self, manager, mock_ws):
        await manager.connect(mock_ws)
        mock_ws.accept.assert_awaited_once()
        assert mock_ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager):
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)
        assert len(manager.active_connections) == 2


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_removes_connection(self, manager, mock_ws):
        await manager.connect(mock_ws)
        manager.disconnect(mock_ws)
        assert mock_ws not in manager.active_connections

    def test_disconnect_unknown_is_safe(self, manager, mock_ws):
        """Disconnecting a WebSocket that was never connected should not raise."""
        manager.disconnect(mock_ws)  # no error


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_sends_to_all(self, manager):
        ws1, ws2 = AsyncMock(), AsyncMock()
        await manager.connect(ws1)
        await manager.connect(ws2)

        msg = {"type": "test", "data": "hello"}
        await manager.broadcast(msg)

        ws1.send_json.assert_awaited_once_with(msg)
        ws2.send_json.assert_awaited_once_with(msg)

    @pytest.mark.asyncio
    async def test_removes_broken_connections(self, manager):
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send_json.side_effect = RuntimeError("closed")

        await manager.connect(good_ws)
        await manager.connect(bad_ws)

        await manager.broadcast({"type": "test"})

        # bad_ws should be removed
        assert bad_ws not in manager.active_connections
        assert good_ws in manager.active_connections

    @pytest.mark.asyncio
    async def test_empty_broadcast_is_safe(self, manager):
        await manager.broadcast({"type": "test"})  # no connections, no error
