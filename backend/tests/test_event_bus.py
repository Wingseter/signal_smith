"""Tests for EventBus."""

import pytest

from app.core.events import EventBus, SIGNAL_CREATED, MEETING_UPDATED


@pytest.fixture
def bus():
    return EventBus()


class TestOn:
    @pytest.mark.asyncio
    async def test_listener_called(self, bus):
        received = []

        async def listener(data):
            received.append(data)

        bus.on("test.event", listener)
        await bus.emit("test.event", {"key": "value"})
        assert received == [{"key": "value"}]

    @pytest.mark.asyncio
    async def test_multiple_listeners(self, bus):
        calls = []

        async def l1(data):
            calls.append("l1")

        async def l2(data):
            calls.append("l2")

        bus.on("evt", l1)
        bus.on("evt", l2)
        await bus.emit("evt", {})
        assert calls == ["l1", "l2"]


class TestOff:
    @pytest.mark.asyncio
    async def test_unregistered_listener_not_called(self, bus):
        called = False

        async def listener():
            nonlocal called
            called = True

        bus.on("evt", listener)
        bus.off("evt", listener)
        await bus.emit("evt")
        assert not called

    @pytest.mark.asyncio
    async def test_off_unknown_event_safe(self, bus):
        async def listener():
            pass

        bus.off("nonexistent", listener)  # no error


class TestEmit:
    @pytest.mark.asyncio
    async def test_no_listeners_is_safe(self, bus):
        await bus.emit("unknown.event", "data")  # no error

    @pytest.mark.asyncio
    async def test_error_in_listener_does_not_propagate(self, bus):
        async def bad_listener(data):
            raise ValueError("boom")

        received = []

        async def good_listener(data):
            received.append(data)

        bus.on("evt", bad_listener)
        bus.on("evt", good_listener)
        await bus.emit("evt", "hello")

        # good_listener should still have been called
        assert received == ["hello"]


class TestEventConstants:
    def test_constants_are_strings(self):
        assert isinstance(SIGNAL_CREATED, str)
        assert isinstance(MEETING_UPDATED, str)

    def test_constants_are_dotted(self):
        assert "." in SIGNAL_CREATED
        assert "." in MEETING_UPDATED
