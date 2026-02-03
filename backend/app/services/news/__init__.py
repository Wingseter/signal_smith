"""
뉴스 분석 서비스 모듈

- NewsMonitor: 네이버 금융 크롤링 + 키워드 감지
- NewsAnalyzer: Gemini 실시간 분석 (빠른 점수 평가)
- DeepAnalyzer: Tavily 심층 분석 (종목 집중 분석)
- NewsTrader: 뉴스 기반 자동매매 + AI 회의 연동
"""

from .monitor import NewsMonitor, news_monitor
from .analyzer import NewsAnalyzer, news_analyzer
from .deep_analyzer import DeepAnalyzer, deep_analyzer
from .trader import NewsTrader, news_trader

__all__ = [
    "NewsMonitor",
    "news_monitor",
    "NewsAnalyzer",
    "news_analyzer",
    "DeepAnalyzer",
    "deep_analyzer",
    "NewsTrader",
    "news_trader",
]
