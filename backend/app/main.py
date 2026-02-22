import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    auth, stocks, portfolio, trading, analysis, notifications,
    backtest, performance, optimizer, sectors, reports, council,
    news_monitor, signals,
)
from app.api.websocket.handler import router as ws_router
from app.config import settings
from app.core.database import init_db
from app.core.exceptions import SignalSmithError
from app.core.logging_config import configure_logging

configure_logging(
    json_output=settings.is_production,
    level="INFO" if settings.is_production else "DEBUG",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Stock Analysis and Trading Agent System",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)


# ── Global exception handlers ──


@app.exception_handler(SignalSmithError)
async def signal_smith_error_handler(request: Request, exc: SignalSmithError):
    logger.error("SignalSmithError [%s]: %s", exc.code, exc.message, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": exc.code, "detail": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "detail": "An unexpected error occurred."},
    )


# ── CORS Middleware ──

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Routers ──

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["Stocks"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["Portfolio"])
app.include_router(trading.router, prefix="/api/v1/trading", tags=["Trading"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["Analysis"])
app.include_router(notifications.router, prefix="/api/v1", tags=["Notifications"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["Backtesting"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["Performance"])
app.include_router(optimizer.router, prefix="/api/v1/optimizer", tags=["Portfolio Optimization"])
app.include_router(sectors.router, prefix="/api/v1/sectors", tags=["Sector Analysis"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(council.router, prefix="/api/v1/council", tags=["AI Council"])
app.include_router(news_monitor.router, prefix="/api/v1/news-monitor", tags=["News Monitor"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["Quant Signals"])
app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
