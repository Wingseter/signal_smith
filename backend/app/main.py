from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, stocks, portfolio, trading, analysis, notifications, backtest, performance, optimizer, sectors
from app.api.websocket.handler import router as ws_router
from app.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    description="Stock Analysis and Trading Agent System",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
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
