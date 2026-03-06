"""Tests for LLM response parsing and call utilities."""

import asyncio
from unittest.mock import AsyncMock

from app.services.council.llm_utils import parse_llm_json, call_analyst_with_timeout
from app.services.council.models import AnalystRole


class TestParseLlmJson:
    def test_json_code_block(self):
        text = '```json\n{"score": 8, "reason": "good"}\n```'
        result, err = parse_llm_json(text)
        assert result == {"score": 8, "reason": "good"}
        assert err is None

    def test_generic_code_block(self):
        text = '```\n{"score": 8}\n```'
        result, err = parse_llm_json(text)
        assert result == {"score": 8}
        assert err is None

    def test_raw_json(self):
        result, err = parse_llm_json('{"score": 8}')
        assert result == {"score": 8}
        assert err is None

    def test_invalid_json_returns_empty(self):
        result, err = parse_llm_json("not json at all")
        assert result == {}
        assert err is not None

    def test_invalid_json_with_defaults(self):
        result, err = parse_llm_json("bad", defaults={"score": 5})
        assert result == {"score": 5}
        assert err is not None

    def test_nested_json(self):
        text = '```json\n{"analysis": {"score": 9, "tags": ["a", "b"]}}\n```'
        result, err = parse_llm_json(text)
        assert result["analysis"]["score"] == 9
        assert err is None


class TestCallAnalystWithTimeout:
    def test_success(self):
        async def _ok():
            return "analyst_result"

        msg, ok = asyncio.run(call_analyst_with_timeout(
            _ok(),
            timeout=5.0,
            fallback_role=AnalystRole.MODERATOR,
            fallback_speaker="test",
            fallback_content="fallback",
        ))
        assert ok is True
        assert msg == "analyst_result"

    def test_timeout(self):
        async def _slow():
            await asyncio.sleep(10)

        msg, ok = asyncio.run(call_analyst_with_timeout(
            _slow(),
            timeout=0.01,
            fallback_role=AnalystRole.MODERATOR,
            fallback_speaker="test",
            fallback_content="timeout fallback",
        ))
        assert ok is False
        assert msg.content == "timeout fallback"
        assert msg.speaker == "시스템"

    def test_exception(self):
        async def _fail():
            raise RuntimeError("boom")

        msg, ok = asyncio.run(call_analyst_with_timeout(
            _fail(),
            timeout=5.0,
            fallback_role=AnalystRole.MODERATOR,
            fallback_speaker="test",
            fallback_content="error fallback",
        ))
        assert ok is False
        assert msg.content == "error fallback"
