"""
뉴스 모니터링 현황 API

크롤링 현황, Gemini 분석 결과를 실시간으로 제공합니다.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass, field, asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

from app.services.news import news_monitor, news_analyzer

logger = logging.getLogger(__name__)
router = APIRouter(tags=["News Monitor"])


# ============ 분석 이력 저장소 ============

@dataclass
class CrawledNewsItem:
    """크롤링된 뉴스 항목"""
    title: str
    url: str
    source: str
    symbol: Optional[str]
    company_name: Optional[str]
    category: str
    keywords: List[str]
    crawled_at: str
    is_trigger: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class AnalysisHistoryItem:
    """Gemini 분석 이력 항목"""
    news_title: str
    symbol: Optional[str]
    company_name: Optional[str]
    score: int
    sentiment: str
    trading_signal: str
    confidence: float
    analysis_reason: str
    analyzer: str
    analyzed_at: str

    def to_dict(self):
        return asdict(self)


class NewsMonitorHistory:
    """뉴스 모니터링 이력 관리"""

    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        self.crawled_news: List[CrawledNewsItem] = []
        self.analysis_history: List[AnalysisHistoryItem] = []
        self.stats = {
            "total_crawled": 0,
            "total_analyzed": 0,
            "total_triggers": 0,
            "last_crawl_at": None,
            "last_analysis_at": None,
        }
        self._callbacks: List = []

    def add_callback(self, callback):
        """업데이트 콜백 등록"""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        """콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _notify_callbacks(self, event_type: str, data: dict):
        """콜백 알림"""
        for callback in self._callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error(f"콜백 오류: {e}")

    def add_crawled_news(self, article, is_trigger: bool = False):
        """크롤링 뉴스 추가"""
        item = CrawledNewsItem(
            title=article.title,
            url=article.url,
            source=article.source,
            symbol=article.symbol,
            company_name=article.company_name,
            category=article.category.value if hasattr(article.category, 'value') else str(article.category),
            keywords=article.keywords,
            crawled_at=datetime.now().isoformat(),
            is_trigger=is_trigger,
        )

        self.crawled_news.insert(0, item)
        if len(self.crawled_news) > self.max_items:
            self.crawled_news = self.crawled_news[:self.max_items]

        self.stats["total_crawled"] += 1
        self.stats["last_crawl_at"] = datetime.now().isoformat()
        if is_trigger:
            self.stats["total_triggers"] += 1

        # 비동기 콜백 호출
        asyncio.create_task(self._notify_callbacks("crawled", item.to_dict()))

    def add_analysis_result(self, result):
        """분석 결과 추가"""
        article = result.article
        item = AnalysisHistoryItem(
            news_title=article.title,
            symbol=article.symbol,
            company_name=article.company_name,
            score=result.score,
            sentiment=result.sentiment.value if hasattr(result.sentiment, 'value') else str(result.sentiment),
            trading_signal=result.trading_signal or "HOLD",
            confidence=result.confidence,
            analysis_reason=result.analysis_reason,
            analyzer=result.analyzer,
            analyzed_at=datetime.now().isoformat(),
        )

        self.analysis_history.insert(0, item)
        if len(self.analysis_history) > self.max_items:
            self.analysis_history = self.analysis_history[:self.max_items]

        self.stats["total_analyzed"] += 1
        self.stats["last_analysis_at"] = datetime.now().isoformat()

        # 비동기 콜백 호출
        asyncio.create_task(self._notify_callbacks("analyzed", item.to_dict()))

    def get_recent_crawled(self, limit: int = 20) -> List[dict]:
        """최근 크롤링 뉴스"""
        return [item.to_dict() for item in self.crawled_news[:limit]]

    def get_recent_analysis(self, limit: int = 20) -> List[dict]:
        """최근 분석 결과"""
        return [item.to_dict() for item in self.analysis_history[:limit]]

    def get_stats(self) -> dict:
        """통계 조회"""
        return {
            **self.stats,
            "crawled_count": len(self.crawled_news),
            "analysis_count": len(self.analysis_history),
        }


# 싱글톤 인스턴스
monitor_history = NewsMonitorHistory()


# ============ 원본 함수 래핑 (이력 추적용) ============

_original_notify_callbacks = None
_original_analyze = None


def setup_tracking():
    """이력 추적 설정"""
    global _original_notify_callbacks, _original_analyze

    # NewsMonitor._notify_callbacks 래핑
    if _original_notify_callbacks is None:
        _original_notify_callbacks = news_monitor._notify_callbacks

        async def wrapped_notify_callbacks(article):
            # 원본 콜백 실행
            await _original_notify_callbacks(article)
            # 이력에 추가 (트리거 뉴스)
            monitor_history.add_crawled_news(article, is_trigger=True)

        news_monitor._notify_callbacks = wrapped_notify_callbacks

    # NewsAnalyzer.analyze 래핑
    if _original_analyze is None:
        _original_analyze = news_analyzer.analyze

        async def wrapped_analyze(article):
            result = await _original_analyze(article)
            # 이력에 추가
            monitor_history.add_analysis_result(result)
            return result

        news_analyzer.analyze = wrapped_analyze


# 모듈 로드 시 설정
setup_tracking()


# ============ WebSocket Manager ============

from app.core.websocket import BaseConnectionManager

ws_manager = BaseConnectionManager("news-monitor")


# 콜백 등록 (WebSocket 브로드캐스트용)
async def on_history_update(event_type: str, data: dict):
    """이력 업데이트 시 WebSocket 브로드캐스트"""
    await ws_manager.broadcast({
        "type": event_type,
        "data": data,
    })


monitor_history.add_callback(on_history_update)


# ============ REST API ============

@router.get("/status")
async def get_monitor_status():
    """모니터링 상태 조회"""
    return {
        "monitor_running": news_monitor.is_running(),
        "stats": monitor_history.get_stats(),
        "poll_interval": news_monitor._poll_interval,
        "seen_urls_count": len(news_monitor._seen_urls),
    }


@router.get("/crawled")
async def get_crawled_news(limit: int = Query(default=20, le=100)):
    """크롤링된 뉴스 목록"""
    return {
        "news": monitor_history.get_recent_crawled(limit),
        "total": len(monitor_history.crawled_news),
    }


@router.get("/analysis")
async def get_analysis_history(limit: int = Query(default=20, le=100)):
    """분석 이력 목록"""
    return {
        "analysis": monitor_history.get_recent_analysis(limit),
        "total": len(monitor_history.analysis_history),
    }


@router.post("/test-crawl")
async def test_crawl(auto_analyze: bool = Query(default=True, description="트리거 뉴스 자동 분석 여부")):
    """테스트용 수동 크롤링 (트리거 뉴스는 자동 Gemini 분석)"""
    articles = await news_monitor.fetch_main_news()

    results = []
    analyzed_count = 0

    for article in articles:
        # 트리거 여부 체크
        is_trigger = news_monitor._is_trigger_news(article.title)

        # 이력에 추가
        monitor_history.add_crawled_news(article, is_trigger=is_trigger)

        article_info = {
            "title": article.title,
            "source": article.source,
            "symbol": article.symbol,
            "category": article.category.value if hasattr(article.category, 'value') else str(article.category),
            "keywords": article.keywords,
            "is_trigger": is_trigger,
        }

        # 트리거 뉴스면 자동 분석
        if is_trigger and auto_analyze:
            try:
                analysis = await news_analyzer.analyze(article)
                article_info["analysis"] = {
                    "score": analysis.score,
                    "sentiment": analysis.sentiment.value,
                    "trading_signal": analysis.trading_signal,
                    "confidence": analysis.confidence,
                    "reason": analysis.analysis_reason[:100] + "..." if len(analysis.analysis_reason) > 100 else analysis.analysis_reason,
                }
                analyzed_count += 1
            except Exception as e:
                logger.error(f"자동 분석 오류: {e}")
                article_info["analysis_error"] = str(e)

        results.append(article_info)

    return {
        "crawled_count": len(articles),
        "trigger_count": sum(1 for a in results if a.get("is_trigger")),
        "analyzed_count": analyzed_count,
        "articles": results[:20],  # 최대 20개만 반환
    }


@router.post("/test-analyze")
async def test_analyze(title: str = Query(...), symbol: Optional[str] = None):
    """테스트용 수동 분석"""
    from app.services.news.models import NewsArticle

    article = NewsArticle(
        title=title,
        url="test://manual",
        source="Manual Test",
        published_at=datetime.now(),
        symbol=symbol,
    )

    result = await news_analyzer.analyze(article)

    return {
        "title": title,
        "score": result.score,
        "sentiment": result.sentiment.value,
        "trading_signal": result.trading_signal,
        "confidence": result.confidence,
        "reason": result.analysis_reason,
        "analyzer": result.analyzer,
    }


# ============ WebSocket ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 모니터링 WebSocket"""
    await ws_manager.connect(websocket)

    # 초기 상태 전송
    await websocket.send_json({
        "type": "connected",
        "status": {
            "monitor_running": news_monitor.is_running(),
            "stats": monitor_history.get_stats(),
        },
        "recent_crawled": monitor_history.get_recent_crawled(10),
        "recent_analysis": monitor_history.get_recent_analysis(10),
    })

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif message.get("type") == "get_status":
                await websocket.send_json({
                    "type": "status",
                    "status": {
                        "monitor_running": news_monitor.is_running(),
                        "stats": monitor_history.get_stats(),
                    },
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        ws_manager.disconnect(websocket)
