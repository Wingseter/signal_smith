"""
Analysis API Routes

AI 분석 요청 및 결과 조회 API.
LangGraph 코디네이터를 통해 멀티 에이전트 분석을 수행합니다.
"""

from typing import Optional, List
from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.core.redis import get_redis
from app.models import Stock, StockAnalysis, TradingSignal, User
from app.agents.coordinator import coordinator, analyze_stock, quick_analyze_stock
from app.services.stock_service import stock_service

router = APIRouter()


# ========== Request/Response Models ==========

class AnalysisRequest(BaseModel):
    symbol: str
    analysis_types: List[str] = Field(
        default=["quant", "fundamental", "news", "technical"],
        description="분석 유형 선택: quant, fundamental, news, technical"
    )
    include_price_data: bool = Field(default=True, description="가격 데이터 포함 여부")
    save_to_db: bool = Field(default=True, description="결과 DB 저장 여부")


class QuickAnalysisRequest(BaseModel):
    symbol: str


class AnalysisTaskResponse(BaseModel):
    task_id: str
    symbol: str
    status: str
    message: str


class AgentAnalysis(BaseModel):
    agent: str
    analysis_type: str
    score: Optional[float] = None
    summary: Optional[str] = None
    recommendation: Optional[str] = None
    confidence: Optional[float] = None
    analyzed_at: Optional[str] = None


class FullAnalysisResponse(BaseModel):
    symbol: str
    news_analysis: Optional[dict] = None
    quant_analysis: Optional[dict] = None
    fundamental_analysis: Optional[dict] = None
    technical_analysis: Optional[dict] = None
    final_recommendation: Optional[dict] = None
    trading_signal: Optional[dict] = None
    error: Optional[str] = None


class ConsolidatedAnalysis(BaseModel):
    symbol: str
    overall_score: float
    overall_recommendation: str
    confidence: float
    quant_analysis: Optional[dict] = None
    fundamental_analysis: Optional[dict] = None
    news_analysis: Optional[dict] = None
    technical_analysis: Optional[dict] = None
    key_points: Optional[List[str]] = None
    risks: Optional[List[str]] = None
    last_updated: Optional[str] = None


class MarketSentimentResponse(BaseModel):
    market: str
    overall_sentiment: str
    sentiment_score: float
    key_drivers: Optional[List[str]] = None
    sector_outlook: Optional[dict] = None
    analyzed_at: str


class AgentStatusResponse(BaseModel):
    name: str
    role: str
    status: str
    last_run: Optional[str] = None
    success_rate: Optional[float] = None


# ========== 분석 실행 API ==========

@router.post("/run", response_model=FullAnalysisResponse)
async def run_full_analysis(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """
    전체 AI 분석 실행

    모든 에이전트(Gemini, ChatGPT, Claude, ML)를 활용하여
    종합적인 분석을 수행합니다.
    """
    # 가격 데이터 조회
    price_data = None
    if request.include_price_data:
        price_data = await stock_service.get_price_history(
            request.symbol, "daily", 100
        )

    # 분석 실행
    result = await coordinator.run_analysis(
        symbol=request.symbol,
        price_data=price_data,
        save_to_db=request.save_to_db,
    )

    return FullAnalysisResponse(**result)


@router.post("/quick", response_model=dict)
async def run_quick_analysis(
    request: QuickAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """
    빠른 분석 실행

    기술적 분석과 퀀트 분석만 수행하여 빠른 결과를 제공합니다.
    """
    # 가격 데이터 조회
    price_data = await stock_service.get_price_history(
        request.symbol, "daily", 50
    )

    result = await quick_analyze_stock(request.symbol, price_data)
    return result


@router.post("/request", response_model=AnalysisTaskResponse)
async def request_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    백그라운드 분석 요청

    분석을 백그라운드에서 실행하고 task_id를 반환합니다.
    결과는 /analysis/task/{task_id}에서 조회할 수 있습니다.
    """
    # 종목 존재 확인
    result = await db.execute(
        select(Stock).where(Stock.symbol == request.symbol)
    )
    stock = result.scalar_one_or_none()
    if not stock:
        # 종목이 없으면 기본 정보로 생성 시도
        pass  # 실제로는 API에서 조회하여 생성

    # 태스크 ID 생성
    task_id = str(uuid.uuid4())

    # Redis에 태스크 상태 저장
    redis = await get_redis()
    await redis.set(
        f"analysis_task:{task_id}",
        "processing",
        ex=3600  # 1시간 후 만료
    )

    # 백그라운드 태스크 실행
    async def run_background_analysis():
        try:
            price_data = None
            if request.include_price_data:
                price_data = await stock_service.get_price_history(
                    request.symbol, "daily", 100
                )

            result = await coordinator.run_analysis(
                symbol=request.symbol,
                price_data=price_data,
                save_to_db=request.save_to_db,
            )

            # 결과를 Redis에 저장
            import json
            await redis.set(
                f"analysis_result:{task_id}",
                json.dumps(result, ensure_ascii=False, default=str),
                ex=3600
            )
            await redis.set(f"analysis_task:{task_id}", "completed", ex=3600)

        except Exception as e:
            await redis.set(f"analysis_task:{task_id}", f"failed:{str(e)}", ex=3600)

    background_tasks.add_task(run_background_analysis)

    return AnalysisTaskResponse(
        task_id=task_id,
        symbol=request.symbol,
        status="processing",
        message=f"분석이 시작되었습니다. 완료 시 /analysis/task/{task_id}에서 결과를 확인하세요.",
    )


@router.get("/task/{task_id}")
async def get_analysis_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    백그라운드 분석 결과 조회
    """
    redis = await get_redis()

    # 태스크 상태 확인
    status = await redis.get(f"analysis_task:{task_id}")
    if not status:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")

    status = status.decode() if isinstance(status, bytes) else status

    if status == "processing":
        return {"task_id": task_id, "status": "processing", "message": "분석 진행 중..."}

    if status.startswith("failed:"):
        error = status.replace("failed:", "")
        return {"task_id": task_id, "status": "failed", "error": error}

    if status == "completed":
        result = await redis.get(f"analysis_result:{task_id}")
        if result:
            import json
            result = result.decode() if isinstance(result, bytes) else result
            return {
                "task_id": task_id,
                "status": "completed",
                "result": json.loads(result),
            }

    return {"task_id": task_id, "status": status}


# ========== 분석 결과 조회 API ==========

@router.get("/consolidated/{symbol}", response_model=ConsolidatedAnalysis)
async def get_consolidated_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    종합 분석 결과 조회

    가장 최근의 각 분석 유형별 결과를 종합하여 반환합니다.
    """
    result = await db.execute(
        select(StockAnalysis)
        .where(StockAnalysis.symbol == symbol)
        .order_by(StockAnalysis.created_at.desc())
    )
    analyses = result.scalars().all()

    if not analyses:
        raise HTTPException(status_code=404, detail="분석 결과가 없습니다.")

    # 유형별 최신 분석 그룹화
    analysis_map = {}
    for analysis in analyses:
        if analysis.analysis_type not in analysis_map:
            analysis_map[analysis.analysis_type] = {
                "agent": analysis.agent_name,
                "summary": analysis.summary,
                "score": float(analysis.score) if analysis.score else None,
                "recommendation": analysis.recommendation,
                "created_at": analysis.created_at.isoformat(),
                "raw_data": analysis.raw_data,
            }

    # 점수 계산
    scores = []
    weights = {"news": 0.15, "quant": 0.30, "fundamental": 0.30, "technical": 0.25}
    total_weight = 0

    for atype, data in analysis_map.items():
        if data["score"] is not None and atype in weights:
            scores.append(data["score"] * weights[atype])
            total_weight += weights[atype]

    overall_score = sum(scores) / total_weight if total_weight > 0 else 0

    # 추천 결정
    if overall_score >= 40:
        overall_recommendation = "strong_buy"
    elif overall_score >= 20:
        overall_recommendation = "buy"
    elif overall_score <= -40:
        overall_recommendation = "strong_sell"
    elif overall_score <= -20:
        overall_recommendation = "sell"
    else:
        overall_recommendation = "hold"

    # 신뢰도 계산
    confidence = (len(analysis_map) / 4) * 100

    # 핵심 포인트 및 리스크 수집
    key_points = []
    risks = []
    for atype, data in analysis_map.items():
        if data.get("summary"):
            key_points.append(f"[{atype}] {data['summary'][:80]}")
        if data.get("raw_data"):
            raw = data["raw_data"]
            if raw.get("key_risks"):
                risks.extend(raw["key_risks"][:2])
            if raw.get("negative_factors"):
                risks.extend(raw["negative_factors"][:2])

    # 최신 업데이트 시간
    last_updated = analyses[0].created_at.isoformat() if analyses else None

    return ConsolidatedAnalysis(
        symbol=symbol,
        overall_score=round(overall_score, 2),
        overall_recommendation=overall_recommendation,
        confidence=round(confidence, 2),
        quant_analysis=analysis_map.get("quant"),
        fundamental_analysis=analysis_map.get("fundamental"),
        news_analysis=analysis_map.get("news"),
        technical_analysis=analysis_map.get("technical"),
        key_points=key_points[:5],
        risks=list(set(risks))[:5],
        last_updated=last_updated,
    )


@router.get("/history/{symbol}", response_model=List[AgentAnalysis])
async def get_analysis_history(
    symbol: str,
    analysis_type: Optional[str] = Query(None, description="분석 유형 필터"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    분석 이력 조회
    """
    query = select(StockAnalysis).where(StockAnalysis.symbol == symbol)

    if analysis_type:
        query = query.where(StockAnalysis.analysis_type == analysis_type)

    query = query.order_by(StockAnalysis.created_at.desc()).limit(limit)

    result = await db.execute(query)
    analyses = result.scalars().all()

    return [
        AgentAnalysis(
            agent=a.agent_name,
            analysis_type=a.analysis_type,
            score=float(a.score) if a.score else None,
            summary=a.summary,
            recommendation=a.recommendation,
            confidence=a.raw_data.get("confidence") if a.raw_data else None,
            analyzed_at=a.created_at.isoformat(),
        )
        for a in analyses
    ]


# ========== 시장 분석 API ==========

@router.get("/market/sentiment", response_model=MarketSentimentResponse)
async def get_market_sentiment(
    market: str = Query("KOSPI", description="시장 선택: KOSPI 또는 KOSDAQ"),
    current_user: User = Depends(get_current_user),
):
    """
    시장 전반 센티먼트 분석

    Gemini 에이전트를 활용하여 시장 전반의 분위기를 분석합니다.
    API 키가 설정되지 않은 경우 기본값을 반환합니다.
    """
    try:
        from app.agents.gemini_agent import GeminiNewsAgent
        from app.config import settings

        # API 키가 없으면 기본값 반환
        if not settings.google_api_key or settings.google_api_key == "your-google-api-key":
            return MarketSentimentResponse(
                market=market,
                overall_sentiment="neutral",
                sentiment_score=50,
                key_drivers=["API 키가 설정되지 않아 분석을 수행할 수 없습니다"],
                sector_outlook=None,
                analyzed_at=datetime.utcnow().isoformat(),
            )

        agent = GeminiNewsAgent()
        result = await agent.get_market_sentiment(market)

        if "error" in result:
            # 에러 발생 시 기본값 반환 (500 에러 대신)
            return MarketSentimentResponse(
                market=market,
                overall_sentiment="neutral",
                sentiment_score=50,
                key_drivers=[f"분석 오류: {result.get('error', '알 수 없는 오류')[:100]}"],
                sector_outlook=None,
                analyzed_at=datetime.utcnow().isoformat(),
            )

        return MarketSentimentResponse(
            market=result.get("market", market),
            overall_sentiment=result.get("overall_sentiment", "neutral"),
            sentiment_score=result.get("sentiment_score", 0),
            key_drivers=result.get("key_drivers", []),
            sector_outlook=result.get("sector_outlook"),
            analyzed_at=result.get("analyzed_at", datetime.utcnow().isoformat()),
        )
    except Exception as e:
        # 예외 발생 시에도 기본값 반환
        return MarketSentimentResponse(
            market=market,
            overall_sentiment="neutral",
            sentiment_score=50,
            key_drivers=[f"서비스 오류: {str(e)[:100]}"],
            sector_outlook=None,
            analyzed_at=datetime.utcnow().isoformat(),
        )


# ========== 에이전트 상태 API ==========

@router.get("/agents/status", response_model=List[AgentStatusResponse])
async def get_agents_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    모든 AI 에이전트 상태 조회
    """
    # 각 에이전트별 최근 분석 조회
    agents_info = [
        {"name": "gemini", "role": "뉴스/센티먼트 분석", "type": "news"},
        {"name": "chatgpt", "role": "퀀트 분석", "type": "quant"},
        {"name": "claude", "role": "펀더멘털 분석", "type": "fundamental"},
        {"name": "ml", "role": "기술적 분석", "type": "technical"},
    ]

    result_list = []

    for agent in agents_info:
        # 최근 분석 조회
        result = await db.execute(
            select(StockAnalysis)
            .where(StockAnalysis.agent_name == agent["name"])
            .order_by(StockAnalysis.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        # 성공률 계산 (최근 100개 기준)
        total_result = await db.execute(
            select(func.count(StockAnalysis.id))
            .where(StockAnalysis.agent_name == agent["name"])
        )
        total = total_result.scalar() or 0

        success_result = await db.execute(
            select(func.count(StockAnalysis.id))
            .where(
                StockAnalysis.agent_name == agent["name"],
                StockAnalysis.score.isnot(None)
            )
        )
        success = success_result.scalar() or 0

        success_rate = (success / total * 100) if total > 0 else None

        result_list.append(AgentStatusResponse(
            name=agent["name"],
            role=agent["role"],
            status="active",
            last_run=latest.created_at.isoformat() if latest else None,
            success_rate=round(success_rate, 2) if success_rate else None,
        ))

    return result_list


@router.get("/agents/coordinator")
async def get_coordinator_status(
    current_user: User = Depends(get_current_user),
):
    """
    코디네이터 상태 조회
    """
    return {
        "status": "active",
        "workflow": "langgraph",
        "agents": ["gemini", "chatgpt", "claude", "ml"],
        "weights": coordinator.AGENT_WEIGHTS,
        "features": [
            "parallel_execution",
            "weighted_scoring",
            "auto_signal_generation",
            "db_persistence",
        ],
    }


# ========== 시그널 API ==========

@router.get("/signals/latest", response_model=List[dict])
async def get_latest_signals(
    limit: int = Query(10, ge=1, le=50),
    signal_type: Optional[str] = Query(None, description="buy 또는 sell"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    최신 트레이딩 시그널 조회
    """
    query = select(TradingSignal).where(TradingSignal.is_executed == False)

    if signal_type:
        query = query.where(TradingSignal.signal_type == signal_type)

    query = query.order_by(TradingSignal.created_at.desc()).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()

    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "signal_type": s.signal_type,
            "strength": float(s.strength),
            "source_agent": s.source_agent,
            "reason": s.reason,
            "target_price": float(s.target_price) if s.target_price else None,
            "stop_loss": float(s.stop_loss) if s.stop_loss else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in signals
    ]


@router.get("/signals/stats")
async def get_signals_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    시그널 통계
    """
    # 전체 시그널 수
    total_result = await db.execute(select(func.count(TradingSignal.id)))
    total = total_result.scalar() or 0

    # 미실행 시그널
    pending_result = await db.execute(
        select(func.count(TradingSignal.id))
        .where(TradingSignal.is_executed == False)
    )
    pending = pending_result.scalar() or 0

    # 유형별 분포
    buy_result = await db.execute(
        select(func.count(TradingSignal.id))
        .where(TradingSignal.signal_type == "buy")
    )
    buy_count = buy_result.scalar() or 0

    sell_result = await db.execute(
        select(func.count(TradingSignal.id))
        .where(TradingSignal.signal_type == "sell")
    )
    sell_count = sell_result.scalar() or 0

    return {
        "total_signals": total,
        "pending_signals": pending,
        "executed_signals": total - pending,
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "buy_ratio": round(buy_count / total * 100, 2) if total > 0 else 0,
    }
