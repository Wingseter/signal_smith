from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import Stock, StockAnalysis, User

router = APIRouter()


class AnalysisRequest(BaseModel):
    symbol: str
    analysis_types: list[str] = ["quant", "fundamental", "news", "technical"]


class AnalysisTaskResponse(BaseModel):
    task_id: str
    symbol: str
    status: str
    message: str


class ConsolidatedAnalysis(BaseModel):
    symbol: str
    overall_score: float
    overall_recommendation: str
    quant_analysis: Optional[dict] = None
    fundamental_analysis: Optional[dict] = None
    news_analysis: Optional[dict] = None
    technical_analysis: Optional[dict] = None


@router.post("/request", response_model=AnalysisTaskResponse)
async def request_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request AI analysis for a stock."""
    result = await db.execute(select(Stock).where(Stock.symbol == request.symbol))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())

    # Queue analysis task
    # background_tasks.add_task(run_analysis, request.symbol, request.analysis_types, task_id)

    return AnalysisTaskResponse(
        task_id=task_id,
        symbol=request.symbol,
        status="queued",
        message=f"Analysis queued for {', '.join(request.analysis_types)}",
    )


@router.get("/consolidated/{symbol}", response_model=ConsolidatedAnalysis)
async def get_consolidated_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get consolidated analysis from all AI agents."""
    result = await db.execute(
        select(StockAnalysis)
        .where(StockAnalysis.symbol == symbol)
        .order_by(StockAnalysis.created_at.desc())
    )
    analyses = result.scalars().all()

    if not analyses:
        raise HTTPException(status_code=404, detail="No analysis found for this stock")

    # Group by analysis type and get latest
    analysis_map = {}
    for analysis in analyses:
        if analysis.analysis_type not in analysis_map:
            analysis_map[analysis.analysis_type] = {
                "agent": analysis.agent_name,
                "summary": analysis.summary,
                "score": float(analysis.score) if analysis.score else None,
                "recommendation": analysis.recommendation,
                "created_at": analysis.created_at.isoformat(),
            }

    # Calculate overall score
    scores = [a["score"] for a in analysis_map.values() if a["score"] is not None]
    overall_score = sum(scores) / len(scores) if scores else 0

    # Determine overall recommendation
    if overall_score > 30:
        overall_recommendation = "buy"
    elif overall_score < -30:
        overall_recommendation = "sell"
    else:
        overall_recommendation = "hold"

    return ConsolidatedAnalysis(
        symbol=symbol,
        overall_score=overall_score,
        overall_recommendation=overall_recommendation,
        quant_analysis=analysis_map.get("quant"),
        fundamental_analysis=analysis_map.get("fundamental"),
        news_analysis=analysis_map.get("news"),
        technical_analysis=analysis_map.get("technical"),
    )


@router.get("/agents/status")
async def get_agents_status(
    current_user: User = Depends(get_current_user),
):
    """Get status of all AI agents."""
    return {
        "agents": [
            {
                "name": "gemini",
                "role": "News Analysis",
                "status": "active",
                "last_run": None,
            },
            {
                "name": "chatgpt",
                "role": "Quant Analysis",
                "status": "active",
                "last_run": None,
            },
            {
                "name": "claude",
                "role": "Fundamental Analysis",
                "status": "active",
                "last_run": None,
            },
            {
                "name": "ml",
                "role": "Technical Analysis",
                "status": "active",
                "last_run": None,
            },
        ],
        "coordinator": {
            "status": "active",
            "workflow": "langgraph",
        },
    }
