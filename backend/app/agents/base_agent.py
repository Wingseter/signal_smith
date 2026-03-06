"""LLM 에이전트 공통 베이스 클래스"""

from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMAgent(ABC):
    """LLM 에이전트 공통 패턴: lazy client init + JSON 파싱"""

    def __init__(self, model_name: str, api_key: Optional[str], base_url: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """Lazy initialization of API client."""
        if self._client is None and self.api_key:
            self._client = self._create_client()
        return self._client

    @abstractmethod
    def _create_client(self):
        """Provider-specific client creation. Subclass must implement."""
        ...

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        from app.services.council.llm_utils import parse_llm_json
        data, _ = parse_llm_json(text)
        return data
