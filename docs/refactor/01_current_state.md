# 01. Current Architecture State

## Directory Structure

```
backend/app/
+-- main.py                          (80 lines)   FastAPI app + lifespan
+-- config.py                        (220 lines)  Pydantic BaseSettings
+-- __init__.py
|
+-- core/                            (~912 lines total)
|   +-- celery_app.py                (140)  Beat schedule + config
|   +-- database.py                  (105)  Dual async/sync engines
|   +-- redis.py                     (84)   Dual async/sync clients
|   +-- websocket.py                 (127)  Base + Channel connection managers
|   +-- audit.py                     (92)   Structured audit logging
|   +-- security.py                  (105)  JWT + bcrypt
|   +-- events.py                    (55)   In-process event bus
|   +-- logging_config.py            (58)   JSON/text formatters
|   +-- rate_limit.py                (58)   Redis sliding window
|   +-- exceptions.py                (46)   Exception hierarchy
|   +-- constants.py                 (41)   Magic numbers
|   +-- __init__.py                  (1)    Empty
|
+-- models/                          (~700 lines total)
|   +-- user.py                      User + relationships
|   +-- transaction.py               TradingSignal + SignalEvent + Transaction
|   +-- stock.py                     Stock + StockPrice + StockAnalysis
|   +-- portfolio.py                 Portfolio + PortfolioHolding + Watchlist
|   +-- backtest.py                  BacktestResult + BacktestComparison
|   +-- __init__.py                  Re-exports
|
+-- api/
|   +-- routes/                      (~6,000 lines total)
|   |   +-- council.py               (634)  19 endpoints + WebSocket
|   |   +-- backtest.py              (669)  8 endpoints
|   |   +-- analysis.py              (608)  11 endpoints
|   |   +-- optimizer.py             (588)  5 endpoints
|   |   +-- performance.py           (542)  6 endpoints
|   |   +-- sectors.py               (540)  10 endpoints
|   |   +-- reports.py               (498)  5 endpoints
|   |   +-- notifications.py         (416)  10 endpoints
|   |   +-- news_monitor.py          (371)  5 endpoints + WebSocket
|   |   +-- trading.py               (312)  9 endpoints
|   |   +-- stocks.py                (281)  10 endpoints
|   |   +-- portfolio.py             (179)  5 endpoints
|   |   +-- signals.py               (172)  6 endpoints + WebSocket
|   |   +-- auth.py                  (118)  3 endpoints
|   |   +-- __init__.py
|   +-- websocket/
|       +-- handler.py               (263)  3 WebSocket endpoints
|
+-- services/                        (~12,500 lines total)
|   +-- council/                     (~3,450 lines)
|   |   +-- orchestrator.py          (694)  Core meeting flow
|   |   +-- quant_analyst.py         (608)  GPT-based analysis
|   |   +-- technical_indicators.py  (379)  Indicator calculations
|   |   +-- fundamental_analyst.py   (377)  Claude-based analysis
|   |   +-- order_executor.py        (340)  Order lifecycle
|   |   +-- cost_manager.py          (321)  API cost tracking
|   |   +-- portfolio_analyzer.py    (321)  Position analysis
|   |   +-- sell_meeting.py          (308)  Sell decisions
|   |   +-- trading_hours.py         (289)  KRX market sessions
|   |   +-- models.py                (199)  Dataclass models
|   |   +-- risk_gate.py             (192)  3-layer risk gates
|   |   +-- dart_client.py           (9)    Re-export wrapper
|   |   +-- __init__.py              (45)   Public API
|   |
|   +-- signals/                     (~2,100 lines)
|   |   +-- triggers.py              (976)  42 quant triggers
|   |   +-- indicators.py            (531)  50+ technical indicators
|   |   +-- scanner.py               (388)  Scan orchestration
|   |   +-- models.py                (~200) Data models
|   |   +-- __init__.py
|   |
|   +-- tasks/                       (~2,100 lines)
|   |   +-- scanning_tasks.py        (455)  Universe, signal scans
|   |   +-- monitoring_tasks.py      (440)  Signal & holdings monitoring
|   |   +-- execution_tasks.py       (420)  Order execution
|   |   +-- analysis_tasks.py        (~200) AI analysis
|   |   +-- price_tasks.py           (~150) Price updates
|   |   +-- notification_tasks.py    (~150) Alert delivery
|   |   +-- maintenance_tasks.py     (~100) Cleanup
|   |   +-- _common.py               (~80)  Async bridge helpers
|   |   +-- __init__.py              Re-exports
|   |
|   +-- kiwoom/                      (~2,000 lines)
|   |   +-- rest_client.py           (1073) 30+ API methods
|   |   +-- websocket_client.py      (650)  Real-time prices
|   |   +-- base.py                  (220)  Shared utilities
|   |   +-- __init__.py              Singleton exports
|   |
|   +-- news/                        (~1,300 lines)
|   |   +-- trader.py                (351)  News trading orchestration
|   |   +-- models.py                (332)  Hardcoded stock map
|   |   +-- monitor.py               (323)  Naver news polling
|   |   +-- analyzer.py              (281)  Gemini sentiment
|   |   +-- deep_analyzer.py         (210)  Tavily research
|   |   +-- __init__.py
|   |
|   +-- backtesting/                 (~1,700 lines)
|   |   +-- strategies.py            (513)  4 concrete strategies
|   |   +-- engine.py                (506)  Backtest runner
|   |   +-- performance.py           (~400) 30+ metrics
|   |   +-- strategy.py              (~250) ABC + Signal model
|   |   +-- __init__.py
|   |
|   +-- (standalone services)
|       +-- report_generator.py      (926)  PDF reports
|       +-- notification_service.py  (676)  Multi-channel notifications
|       +-- sector_analysis.py       (669)  Sector rotation
|       +-- portfolio_optimizer.py   (659)  Optimization algorithms
|       +-- dart_client.py           (476)  DART financial API
|       +-- trading_service.py       (402)  Order management
|       +-- stock_service.py         (305)  Stock data queries
|       +-- korea_investment.py      (~200) KIS API
|       +-- __init__.py              (1)    Empty
|
+-- agents/                          (~2,400 lines total)
|   +-- claude_agent.py              (581)  Fundamental analysis
|   +-- coordinator.py               (510)  LangGraph orchestrator
|   +-- chatgpt_agent.py             (460)  Quant analysis
|   +-- gemini_agent.py              (400)  News sentiment
|   +-- ml_agent.py                  (~200) Pattern recognition
|   +-- __init__.py
|
+-- schemas/
    +-- __init__.py                  (empty)
```

## Dependency Graph (High-Level)

```
                    +------------------+
                    |     main.py      |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +--------v--------+
     |   API Routes    |          |   Core Layer    |
     | (14 route files)|          | (database, redis|
     +--------+--------+          |  security, etc) |
              |                   +--------+--------+
              |                            |
     +--------v----------------------------v--------+
     |              Service Layer                    |
     |                                               |
     | +----------+  +---------+  +--------+        |
     | | Council   |  | Signals |  | News   |        |
     | | (orch,    |  | (scan,  |  | (mon,  |        |
     | |  risk,    |  |  trig,  |  |  anal, |        |
     | |  exec)    |  |  indic) |  |  trade)|        |
     | +-----+----+  +----+----+  +---+----+        |
     |       |             |           |              |
     | +-----v-------------v-----------v----+        |
     | |         Kiwoom REST Client          |        |
     | |     (prices, orders, account)       |        |
     | +------------------------------------+        |
     |                                               |
     | +--------------------------------------------+|
     | |     Celery Tasks (8 task modules)          ||
     | |  scanning, monitoring, execution, etc.     ||
     | +--------------------------------------------+|
     +-----------------------------------------------+
              |                    |
     +--------v--------+  +------v-------+
     |    MySQL DB      |  |    Redis     |
     | (HeatWave Free)  |  | (cache/queue)|
     +-----------------+  +--------------+
```

## Key Architectural Patterns

### 1. Singleton Service Instances
Services export module-level singletons:
```python
# council/__init__.py
council_orchestrator = CouncilOrchestrator()

# signals/__init__.py
signal_scanner = SignalScanner()
```

### 2. Callback-Based Event Propagation
Services register callbacks for real-time updates:
```python
council_orchestrator.add_signal_callback(ws_broadcast_signal)
council_orchestrator.add_meeting_callback(ws_broadcast_meeting)
signal_scanner.add_scan_callback(ws_broadcast_scan_result)
```

### 3. Dual Async/Sync Architecture
- **Async**: FastAPI routes, WebSocket handlers, council orchestrator
- **Sync**: Celery tasks, report generation
- **Bridge**: `_common.py:run_async()` using `asyncio.run()` (anti-pattern)

### 4. Delegation via First Argument
Council modules pass `orch` instance to delegated functions:
```python
# sell_meeting.py
async def run_sell_meeting(orch, symbol, ...):
    orch._meetings.append(meeting)      # Direct state mutation
    await orch._notify_meeting_update(meeting)
```

### 5. Lazy Imports for Circular Dependency Prevention
```python
# orchestrator.py
async def approve_signal(self, signal_id):
    from .order_executor import approve_signal  # Lazy import
    return await approve_signal(self, signal_id)
```

## Technology Stack

| Component | Technology | Version Pattern |
|-----------|-----------|-----------------|
| Web Framework | FastAPI | Async, lifespan manager |
| ORM | SQLAlchemy 2.0 | Mapped types, async sessions |
| Task Queue | Celery | Redis broker, beat scheduler |
| Cache | Redis | Async + sync dual clients |
| Database | MySQL HeatWave | 9.6.0-cloud (OCI) |
| Migrations | Alembic | Version-controlled |
| Validation | Pydantic 2.x | BaseSettings, BaseModel |
| AI: Quant | OpenAI GPT | Council + Agent |
| AI: Fundamental | Anthropic Claude | Council + Agent |
| AI: News | Google Gemini | Sentiment analysis |
| Securities API | Kiwoom REST | Token auth, real-time WS |
| Financial Data | DART API | Corporate filings |
