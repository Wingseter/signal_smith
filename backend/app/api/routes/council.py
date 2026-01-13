"""
AI 투자 회의 API

실시간 회의 진행 상황을 WebSocket으로 스트리밍하고,
시그널 승인/거부/체결을 처리합니다.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

from app.services.news import news_trader, news_monitor
from app.services.council import council_orchestrator, CouncilMeeting, InvestmentSignal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/council", tags=["AI Council"])


# ============ Pydantic Models ============

class CouncilConfig(BaseModel):
    """회의 설정"""
    council_threshold: int = 7
    sell_threshold: int = 3
    auto_execute: bool = False
    max_position_per_stock: int = 500000
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


# ============ WebSocket Manager ============

class ConnectionManager:
    """WebSocket 연결 관리"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 연결: {len(self.active_connections)}개 활성")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 해제: {len(self.active_connections)}개 활성")

    async def broadcast(self, message: dict):
        """모든 연결에 메시지 브로드캐스트"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"브로드캐스트 오류: {e}")
                disconnected.append(connection)

        # 끊어진 연결 제거
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


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
    return {
        "running": stats["running"],
        "auto_execute": stats["auto_execute"],
        "council_threshold": stats["council_threshold"],
        "pending_signals": stats["pending_signals"],
        "total_meetings": stats["total_meetings"],
        "daily_trades": stats["daily_trades"],
        "monitor_running": news_monitor.is_running(),
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
