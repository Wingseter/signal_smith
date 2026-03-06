"""LLM 응답 파싱 및 호출 유틸리티"""

import asyncio
import json
import logging
from typing import Optional

from .models import AnalystRole, CouncilMessage

logger = logging.getLogger(__name__)


def parse_llm_json(response_text: str, defaults: Optional[dict] = None) -> tuple[dict, Optional[str]]:
    """LLM 응답에서 JSON 추출.

    Args:
        response_text: LLM 원본 응답 텍스트
        defaults: 파싱 실패 시 반환할 기본값

    Returns:
        (parsed_dict, error_message) — 성공 시 error_message는 None
    """
    try:
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        else:
            json_str = response_text

        return json.loads(json_str.strip()), None
    except (json.JSONDecodeError, IndexError) as e:
        return defaults or {}, str(e)


async def call_analyst_with_timeout(
    coro,
    *,
    timeout: float = 60.0,
    fallback_role: AnalystRole,
    fallback_speaker: str,
    fallback_content: str,
    fallback_data: Optional[dict] = None,
) -> tuple[CouncilMessage, bool]:
    """분석가 호출 + 타임아웃/에러 시 fallback CouncilMessage 반환.

    Returns:
        (message, success_bool)
    """
    try:
        msg = await asyncio.wait_for(coro, timeout=timeout)
        return msg, True
    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"{fallback_speaker} API 호출 실패 또는 타임아웃: {e}")
        fallback_msg = CouncilMessage(
            role=fallback_role,
            speaker="시스템",
            content=fallback_content,
            data=fallback_data or {},
        )
        return fallback_msg, False
    finally:
        await asyncio.sleep(2)  # rate limit throttle for Google/Antigravity providers
