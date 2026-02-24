"""
AI 투자 회의 API

실시간 회의 진행 상황을 WebSocket으로 스트리밍하고,
시그널 승인/거부/체결을 처리합니다.
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

from app.services.news import news_trader, news_monitor
from app.services.council import council_orchestrator, CouncilMeeting, InvestmentSignal
from app.services.trading_service import trading_service
from app.core.websocket import BaseConnectionManager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Council"])


# ============ Pydantic Models ============

class CouncilConfig(BaseModel):
    """회의 설정"""
    council_threshold: int = 7
    sell_threshold: int = 3
    auto_execute: bool = True
    max_position_per_stock: int = 5000000
    poll_interval: int = 60


class SignalAction(BaseModel):
    """시그널 액션"""
    signal_id: str


class ManualMeetingRequest(BaseModel):
    """수동 회의 요청"""
    symbol: str
    company_name: str
    news_title: str
    news_score: int = 8


manager = BaseConnectionManager("council")


# ============ 회의 콜백 등록 ============

async def on_meeting_update(meeting: CouncilMeeting):
    """회의 업데이트 시 WebSocket 브로드캐스트"""
    await manager.broadcast({
        "type": "meeting_update",
        "meeting": meeting.to_dict(),
    })


async def on_signal_created(signal: InvestmentSignal):
    """시그널 생성 시 WebSocket 브로드캐스트"""
    await manager.broadcast({
        "type": "signal_created",
        "signal": signal.to_dict(),
    })


# 콜백 등록
council_orchestrator.add_meeting_callback(on_meeting_update)
council_orchestrator.add_signal_callback(on_signal_created)


# ============ REST API ============

@router.get("/status")
async def get_status():
    """시스템 상태 조회"""
    stats = news_trader.get_stats()
    trading_status = council_orchestrator.get_trading_status()
    cost_stats = council_orchestrator.get_cost_stats()

    return {
        "running": stats["running"],
        "auto_execute": stats["auto_execute"],
        "council_threshold": stats["council_threshold"],
        "pending_signals": stats["pending_signals"],
        "total_meetings": stats["total_meetings"],
        "daily_trades": stats["daily_trades"],
        "monitor_running": news_monitor.is_running(),
        "trading": trading_status,
        "cost": cost_stats,
    }


@router.post("/start")
async def start_monitoring(config: Optional[CouncilConfig] = None):
    """뉴스 모니터링 및 AI 회의 시스템 시작"""
    if config:
        news_trader.update_config(
            council_threshold=config.council_threshold,
            sell_threshold=config.sell_threshold,
            auto_execute=config.auto_execute,
            max_position_per_stock=config.max_position_per_stock,
        )

    poll_interval = config.poll_interval if config else 60
    await news_trader.start(poll_interval=poll_interval)

    return {
        "status": "started",
        "config": news_trader.get_stats(),
    }


@router.post("/stop")
async def stop_monitoring():
    """모니터링 중지"""
    await news_trader.stop()
    return {"status": "stopped"}


@router.get("/meetings")
async def get_meetings(limit: int = Query(default=10, le=100)):
    """최근 회의 목록"""
    meetings = news_trader.get_recent_meetings(limit)
    return {
        "meetings": [m.to_dict() for m in meetings],
        "total": len(meetings),
    }


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str):
    """회의 상세 조회"""
    meeting = council_orchestrator.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다")
    return meeting.to_dict()


@router.get("/meetings/{meeting_id}/transcript")
async def get_meeting_transcript(meeting_id: str):
    """회의록 텍스트 조회"""
    meeting = council_orchestrator.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다")
    return {
        "meeting_id": meeting_id,
        "transcript": meeting.get_transcript(),
    }


@router.get("/signals/pending")
async def get_pending_signals():
    """대기 중인 시그널"""
    signals = news_trader.get_pending_signals()
    return {
        "signals": [s.to_dict() for s in signals],
        "total": len(signals),
    }


@router.post("/signals/approve")
async def approve_signal(action: SignalAction):
    """시그널 승인"""
    signal = await news_trader.approve_signal(action.signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="시그널을 찾을 수 없습니다")

    await manager.broadcast({
        "type": "signal_approved",
        "signal": signal.to_dict(),
    })

    return signal.to_dict()


@router.post("/signals/reject")
async def reject_signal(action: SignalAction):
    """시그널 거부"""
    signal = await news_trader.reject_signal(action.signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="시그널을 찾을 수 없습니다")

    await manager.broadcast({
        "type": "signal_rejected",
        "signal": signal.to_dict(),
    })

    return signal.to_dict()


@router.post("/signals/execute")
async def execute_signal(action: SignalAction):
    """시그널 체결"""
    signal = await news_trader.execute_signal(action.signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="시그널을 찾을 수 없거나 승인되지 않았습니다")

    await manager.broadcast({
        "type": "signal_executed",
        "signal": signal.to_dict(),
    })

    return signal.to_dict()


@router.post("/meetings/manual")
async def start_manual_meeting(request: ManualMeetingRequest):
    """수동 회의 시작 (테스트용)"""
    meeting = await council_orchestrator.start_meeting(
        symbol=request.symbol,
        company_name=request.company_name,
        news_title=request.news_title,
        news_score=request.news_score,
        available_amount=news_trader.config.max_position_per_stock,
    )
    return meeting.to_dict()


@router.post("/test/analyze-news")
async def test_analyze_news():
    """뉴스 크롤링 및 분석 테스트 (디버그용)"""
    from app.services.news import news_analyzer

    # 1. 뉴스 크롤링
    articles = await news_monitor.fetch_main_news()

    if not articles:
        return {"error": "뉴스를 가져올 수 없습니다", "articles": []}

    # 2. 첫 번째 뉴스 분석
    article = articles[0]
    analysis = await news_analyzer.analyze(article)

    # 3. 회의 소집 조건 확인
    threshold = news_trader.config.council_threshold
    should_trigger = analysis.score >= threshold

    return {
        "total_news": len(articles),
        "analyzed_article": {
            "title": article.title,
            "source": article.source,
            "symbol": article.symbol,
            "company_name": article.company_name,
        },
        "analysis_result": {
            "score": analysis.score,
            "sentiment": analysis.sentiment.value,
            "confidence": analysis.confidence,
            "trading_signal": analysis.trading_signal,
            "reason": analysis.analysis_reason,
            "extracted_symbol": analysis.article.symbol,
            "extracted_company": analysis.article.company_name,
        },
        "council_threshold": threshold,
        "should_trigger_council": should_trigger,
        "config": {
            "require_symbol": news_trader.config.require_symbol,
            "min_confidence": news_trader.config.min_confidence,
            "analyze_all_news": news_trader.config.analyze_all_news,
        }
    }


@router.post("/test/force-council")
async def test_force_council():
    """강제로 회의 소집 테스트 (종목코드가 있는 뉴스만)"""
    from app.services.news import news_analyzer

    # 1. 뉴스 크롤링
    articles = await news_monitor.fetch_main_news()

    if not articles:
        return {"error": "뉴스를 가져올 수 없습니다", "articles": []}

    # 2. 종목코드가 있는 뉴스 찾기 (최대 5개 분석)
    for i, article in enumerate(articles[:5]):
        analysis = await news_analyzer.analyze(article)

        # 분석 결과에서 종목 정보 업데이트
        if analysis.article.symbol:
            article.symbol = analysis.article.symbol
        if analysis.article.company_name:
            article.company_name = analysis.article.company_name

        # 종목코드가 있으면 회의 소집
        if article.symbol:
            meeting = await council_orchestrator.start_meeting(
                symbol=article.symbol,
                company_name=article.company_name or article.title[:20],
                news_title=article.title,
                news_score=analysis.score,
                available_amount=news_trader.config.max_position_per_stock,
            )

            return {
                "status": "council_started",
                "articles_checked": i + 1,
                "article": {
                    "title": article.title,
                    "symbol": article.symbol,
                    "company_name": article.company_name,
                },
                "analysis": {
                    "score": analysis.score,
                    "confidence": analysis.confidence,
                    "signal": analysis.trading_signal,
                },
                "meeting": meeting.to_dict(),
            }

    # 3. 종목코드 있는 뉴스 없음
    return {
        "error": "종목코드가 있는 뉴스를 찾을 수 없습니다. 회의 소집 불가.",
        "articles_checked": min(5, len(articles)),
        "hint": "뉴스에서 상장사가 언급되어야 회의가 의미있습니다.",
    }


@router.post("/test/mock-council")
async def test_mock_council(symbol: str = "005930", company_name: str = "삼성전자"):
    """알려진 종목으로 회의 소집 테스트 (디버그용)

    기본값: 삼성전자 (005930)
    예시: POST /council/test/mock-council?symbol=035420&company_name=네이버
    """
    # 유효한 6자리 종목코드 확인
    if not symbol or len(symbol) != 6 or not symbol.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 종목코드: {symbol}. 6자리 숫자여야 합니다."
        )

    meeting = await council_orchestrator.start_meeting(
        symbol=symbol,
        company_name=company_name,
        news_title=f"[테스트] {company_name} 관련 뉴스",
        news_score=8,  # 높은 점수로 설정
        available_amount=news_trader.config.max_position_per_stock,
    )

    return {
        "status": "council_started",
        "test_mode": True,
        "article": {
            "title": f"[테스트] {company_name} 관련 뉴스",
            "symbol": symbol,
            "company_name": company_name,
        },
        "meeting": meeting.to_dict(),
    }


@router.put("/config")
async def update_config(config: CouncilConfig):
    """설정 업데이트"""
    news_trader.update_config(
        council_threshold=config.council_threshold,
        sell_threshold=config.sell_threshold,
        auto_execute=config.auto_execute,
        max_position_per_stock=config.max_position_per_stock,
    )
    return {"status": "updated", "config": news_trader.get_stats()}


@router.get("/trading-status")
async def get_trading_status():
    """거래 상태 조회 (거래 시간, 대기 큐 등)"""
    return council_orchestrator.get_trading_status()


@router.get("/cost-stats")
async def get_cost_stats():
    """AI 비용 통계 조회"""
    return council_orchestrator.get_cost_stats()


@router.get("/queued-executions")
async def get_queued_executions():
    """거래 시간 대기 중인 시그널 목록"""
    signals = council_orchestrator.get_queued_executions()
    return {
        "signals": [s.to_dict() for s in signals],
        "total": len(signals),
    }


@router.get("/account/realized-pnl")
async def get_realized_pnl(period: str = Query(default="1m")):
    """실현 수익 조회 (키움 ka10073)

    Args:
        period: 조회 기간 (1w=1주, 1m=1개월, 3m=3개월)
    """
    import json
    from datetime import datetime, timedelta
    from app.core.redis import get_redis
    from app.services.kiwoom.rest_client import kiwoom_client

    # period → 날짜 변환
    end_date = datetime.now().strftime("%Y%m%d")
    if period == "1w":
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    elif period == "3m":
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    else:  # 1m 기본값
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    # Redis 60초 캐시
    cache_key = f"account:realized_pnl:{period}"
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    items = await kiwoom_client.get_realized_pnl(start_date=start_date, end_date=end_date)

    total_profit_loss = sum(i.profit_loss for i in items)
    total_commission = sum(i.commission for i in items)
    total_tax = sum(i.tax for i in items)

    result = {
        "items": [
            {
                "date": i.date,
                "symbol": i.symbol,
                "name": i.name,
                "quantity": i.quantity,
                "buy_price": i.buy_price,
                "sell_price": i.sell_price,
                "profit_loss": i.profit_loss,
                "profit_rate": i.profit_rate,
                "commission": i.commission,
                "tax": i.tax,
            }
            for i in items
        ],
        "summary": {
            "total_profit_loss": total_profit_loss,
            "total_commission": total_commission,
            "total_tax": total_tax,
            "net_profit": total_profit_loss - total_commission - total_tax,
            "trade_count": len(items),
        },
    }

    try:
        redis = await get_redis()
        await redis.set(cache_key, json.dumps(result), ex=60)
    except Exception:
        pass

    return result


@router.get("/account/balance")
async def get_account_balance():
    """키움 계좌 잔고 조회"""
    summary = await _get_account_summary()
    return summary["balance"]


@router.get("/account/holdings")
async def get_account_holdings():
    """키움 보유종목 조회"""
    summary = await _get_account_summary()
    return {"holdings": summary["holdings"], "count": len(summary["holdings"])}


@router.get("/account/summary")
async def get_account_summary():
    """계좌 잔고 + 보유종목 통합 조회 (캐시 적용)"""
    return await _get_account_summary()


async def _get_account_summary() -> dict:
    """계좌 정보 통합 조회 (10초 Redis 캐시)"""
    import json
    from app.core.redis import get_redis

    cache_key = "account:summary"
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # 키움 API 순차 호출 (동시 호출 시 토큰 경쟁 방지)
    balance = await trading_service.get_account_balance()
    holdings = await trading_service.get_holdings()

    result = {
        "balance": balance,
        "holdings": holdings,
        "count": len(holdings),
    }

    try:
        redis = await get_redis()
        await redis.set(cache_key, json.dumps(result), ex=10)
    except Exception:
        pass

    return result


@router.post("/process-queue")
async def process_queued_executions():
    """대기 큐 수동 처리 (거래 시간에만 작동)"""
    executed = await council_orchestrator.process_queued_executions()

    for signal in executed:
        await manager.broadcast({
            "type": "signal_executed",
            "signal": signal.to_dict(),
        })

    return {
        "executed": len(executed),
        "signals": [s.to_dict() for s in executed],
    }


# ============ WebSocket ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 회의 스트리밍 WebSocket"""
    await manager.connect(websocket)

    # 초기 상태 전송
    await websocket.send_json({
        "type": "connected",
        "status": news_trader.get_stats(),
        "pending_signals": [s.to_dict() for s in news_trader.get_pending_signals()],
        "recent_meetings": [m.to_dict() for m in news_trader.get_recent_meetings(5)],
    })

    try:
        while True:
            # 클라이언트 메시지 수신 (ping/pong 등)
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif message.get("type") == "get_status":
                await websocket.send_json({
                    "type": "status",
                    "status": news_trader.get_stats(),
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        manager.disconnect(websocket)
