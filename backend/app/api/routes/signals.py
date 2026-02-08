"""
퀀트 시그널 API

실시간 시그널 스캐닝 결과를 REST/WebSocket으로 제공
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel

from app.services.signals import signal_scanner, SignalResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Quant Signals"])


# ============ Pydantic Models ============

class ScanRequest(BaseModel):
    """스캔 요청"""
    symbols: List[str]


# ============ WebSocket Manager ============

class SignalConnectionManager:
    """시그널 WebSocket 연결 관리"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"시그널 WebSocket 연결: {len(self.active_connections)}개 활성")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"시그널 WebSocket 해제: {len(self.active_connections)}개 활성")

    async def broadcast(self, message: dict):
        """모든 연결에 메시지 브로드캐스트"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"브로드캐스트 오류: {e}")
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


signal_manager = SignalConnectionManager()


# ============ 콜백 등록 ============

async def on_signal_result(result: SignalResult):
    """시그널 결과 WebSocket 브로드캐스트"""
    await signal_manager.broadcast({
        "type": "signal_result",
        "signal": result.to_dict(),
    })


async def on_scan_update(update: dict):
    """스캔 상태 WebSocket 브로드캐스트"""
    await signal_manager.broadcast({
        "type": "scan_update",
        **update,
    })


# 콜백 등록
signal_scanner.add_signal_callback(on_signal_result)
signal_scanner.add_scan_callback(on_scan_update)


# ============ REST API ============

@router.get("/status")
async def get_status():
    """스캐너 상태 조회"""
    return signal_scanner.get_status()


@router.get("/results")
async def get_results(limit: int = Query(default=50, le=200)):
    """최근 스캔 결과"""
    results = signal_scanner.get_recent_results(limit)
    return {
        "results": [r.to_dict() for r in results],
        "total": len(results),
    }


@router.get("/scan/{symbol}")
async def scan_stock(symbol: str):
    """단일 종목 스캔"""
    if not symbol or len(symbol) != 6 or not symbol.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 종목코드: {symbol}. 6자리 숫자여야 합니다."
        )

    result = await signal_scanner.scan_stock(symbol)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"종목 {symbol} 스캔 실패 (데이터 없음 또는 API 오류)"
        )

    return result.to_dict()


@router.post("/scan")
async def scan_watchlist(request: ScanRequest):
    """워치리스트 스캔 실행"""
    if not request.symbols:
        raise HTTPException(status_code=400, detail="종목코드 리스트가 비어있습니다")

    if len(request.symbols) > 50:
        raise HTTPException(status_code=400, detail="최대 50종목까지 스캔 가능합니다")

    # 유효성 검사
    for sym in request.symbols:
        if not sym or len(sym) != 6 or not sym.isdigit():
            raise HTTPException(
                status_code=400,
                detail=f"유효하지 않은 종목코드: {sym}"
            )

    results = await signal_scanner.scan_watchlist(request.symbols)
    return {
        "results": [r.to_dict() for r in results],
        "total_scanned": len(request.symbols),
        "total_results": len(results),
    }


@router.get("/top")
async def get_top_signals(limit: int = Query(default=20, le=50)):
    """상위 시그널 종목"""
    results = await signal_scanner.get_top_signals(limit)
    return {
        "signals": [r.to_dict() for r in results],
        "total": len(results),
    }


# ============ WebSocket ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 시그널 스트리밍 WebSocket"""
    await signal_manager.connect(websocket)

    # 초기 상태 전송
    await websocket.send_json({
        "type": "connected",
        "status": signal_scanner.get_status(),
        "recent_results": [
            r.to_dict() for r in signal_scanner.get_recent_results(10)
        ],
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
                    "status": signal_scanner.get_status(),
                })

            elif message.get("type") == "scan":
                # WebSocket을 통한 스캔 요청
                symbol = message.get("symbol")
                if symbol:
                    result = await signal_scanner.scan_stock(symbol)
                    if result:
                        await websocket.send_json({
                            "type": "signal_result",
                            "signal": result.to_dict(),
                        })

    except WebSocketDisconnect:
        signal_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"시그널 WebSocket 오류: {e}")
        signal_manager.disconnect(websocket)
