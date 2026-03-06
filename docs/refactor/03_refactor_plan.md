# 03. Refactoring Plan

## Phase 1: Security & Stability (P0)

**Goal**: Fix security vulnerabilities and event loop blocking issues.
**Risk**: Low - targeted fixes, no architecture changes.

### 1.1 WebSocket Authentication [C1]

**Files to modify**:
- `core/websocket.py` - Add `authenticate_websocket()` helper
- `api/routes/council.py` - Apply to `/ws`
- `api/routes/signals.py` - Apply to `/ws`
- `api/routes/news_monitor.py` - Apply to `/ws`
- `api/websocket/handler.py` - Apply to `/market`, `/analysis`, `/trading`

**Approach**:
```python
# core/websocket.py - New helper
async def authenticate_websocket(websocket: WebSocket) -> Optional[int]:
    """Extract and validate JWT token from query params or first message."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return None
    token_data = decode_token(token)
    if not token_data:
        await websocket.close(code=4003, reason="Invalid token")
        return None
    return token_data.user_id
```

### 1.2 Fix Sync DB in Async Routes [C2]

**Files to modify**: `api/routes/reports.py`, `optimizer.py`, `performance.py`, `sectors.py`, `backtest.py`

**Approach**: Replace `get_sync_db_dep()` with async `get_db()`:
```python
# Before
@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_sync_db_dep)):
    result = db.execute(select(...))

# After
@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(...))
```

### 1.3 Add Health Check & Shutdown Hooks [M7, M10]

**Files to modify**: `main.py`

**Add**:
- `GET /health` endpoint checking DB + Redis
- Shutdown hooks in lifespan for `close_redis()`, pending signal persistence

### 1.4 Fix Error Response Consistency [M8]

**Files to modify**: `core/exceptions.py`, `main.py`

**Add `http_status_code`** to exception hierarchy:
```python
class SignalSmithError(Exception):
    http_status_code: int = 500

class NotFoundError(SignalSmithError):
    http_status_code = 404

class ValidationError(SignalSmithError):
    http_status_code = 422
```

### 1.5 Environment-Based CORS [M9]

**Files to modify**: `config.py`, `main.py`

---

## Phase 2: Service Layer Extraction (P1)

**Goal**: Move business logic from routes into proper service modules.
**Risk**: Medium - changes API handler structure, but not API contracts.

### 2.1 Extract PerformanceService [C3]

**New file**: `services/performance_service.py`

Extract from `api/routes/performance.py`:
- `calculate_equity_curve()` (lines 361-408)
- `calculate_risk_metrics()` (lines 411-451) - Sharpe, Sortino, Calmar, VaR
- `calculate_signal_performance()` (lines 269-318)
- `calculate_drawdown_analysis()`

Route becomes thin controller:
```python
@router.get("/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    return await performance_service.get_dashboard(db)
```

### 2.2 Extract AccountService [H10]

**New file**: `services/account_service.py`

Consolidate from `api/routes/council.py:510-577` and `api/routes/trading.py:196-219`:
- `get_account_summary()` - with Redis caching + 3-min staleness check
- `get_balance()`
- `get_holdings()`
- `get_realized_pnl()`

### 2.3 Extract Route Business Logic [C3]

**Files affected**:

| Route File | Logic to Extract | Target Service |
|-----------|-----------------|----------------|
| `council.py` | Account caching, signal approval flow | `account_service.py`, keep in `council/` |
| `analysis.py` | Multi-agent scoring, task management | `analysis_service.py` |
| `sectors.py` | Sector performance, rotation detection | Already has `sector_analysis.py`, move logic there |
| `optimizer.py` | Optimization algorithms | Already has `portfolio_optimizer.py`, move logic there |

### 2.4 Separate Test Endpoints [H7]

**Move from** `api/routes/council.py`:
- `POST /test/analyze-news`
- `POST /test/force-council`
- `POST /test/mock-council`

**To** `api/routes/council_test.py` (only included when `DEBUG=True`)

### 2.5 Remove Monkey-Patching [H7]

**File**: `api/routes/news_monitor.py:176-202`

Replace with proper callback registration in `news/monitor.py`.

---

## Phase 3: Code Deduplication (P1)

**Goal**: Eliminate duplicated code across modules.
**Risk**: Medium - changes internal interfaces, external API unchanged.

### 3.1 Agent Base Class [H1]

**New file**: `agents/base_agent.py`

```python
class BaseAgent(ABC):
    def __init__(self, provider: str, model_name: str, api_key: Optional[str]):
        self._provider = provider
        self._model_name = model_name
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        """Lazy client initialization."""
        if self._client is None and self._api_key:
            self._client = self._create_client()
        return self._client

    @abstractmethod
    def _create_client(self):
        """Provider-specific client creation."""
        pass

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from LLM response (handles ```json blocks)."""
        # Shared implementation (~30 lines)

    async def _call_with_retry(self, func, *args, max_retries=2, timeout=60):
        """Call with timeout and exponential backoff."""
        # Shared implementation (~20 lines)

    @abstractmethod
    async def analyze(self, **kwargs) -> dict:
        pass
```

**Estimated reduction**: ~400 lines across 4 agent files (from ~2000 to ~1200)

### 3.2 Consolidate Technical Indicators [H2]

**Keep**: `services/signals/indicators.py` as canonical source
**Remove**: `services/council/technical_indicators.py`
**Update**: `agents/chatgpt_agent.py` to import from signals

```python
# council/technical_indicators.py becomes a thin wrapper
from app.services.signals.indicators import IndicatorCalculator
technical_calculator = IndicatorCalculator()
```

### 3.3 Shared Validators [M2]

**New file**: `core/validators.py`

```python
def validate_symbol(symbol: str) -> str:
    """Validate Korean stock symbol (6 digits)."""
    if not symbol or len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"Invalid symbol: {symbol}")
    return symbol

def validate_date_range(start: date, end: date) -> tuple[date, date]:
    if start >= end:
        raise ValueError("start must be before end")
    return start, end
```

### 3.4 LLM Response Parser [M5]

**New file**: `services/council/llm_utils.py`

Extract from `quant_analyst.py:250-295` and `fundamental_analyst.py:179-220`:
```python
def parse_llm_json(response_text: str, defaults: dict = None) -> tuple[dict, str]:
    """Parse JSON from LLM response, handling markdown code blocks."""

async def call_analyst_with_timeout(
    analyst, method_name: str, args: tuple,
    timeout: float = 60.0, fallback_data: dict = None
) -> CouncilMessage:
    """Call analyst method with timeout and fallback."""
```

### 3.5 Standardize Response Models [H6]

**New file**: `schemas/responses.py`

```python
class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    total: int
    page: int = 1
    page_size: int = 50

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
```

### 3.6 Stock Lookup Service [H4]

**New file**: `services/stock_lookup.py`

Consolidate from `news/models.py` (hardcoded map):
- Load stock mapping from DB/Redis on startup
- Provide `lookup_by_name()`, `lookup_by_code()`, `search()`
- Cache with configurable TTL

---

## Phase 4: Architecture Restructure (P2)

**Goal**: Break monoliths, reduce coupling, improve testability.
**Risk**: High - internal architecture changes, requires careful testing.

### 4.1 Split Orchestrator [C4]

**Current**: `services/council/orchestrator.py` (694 lines, 9+ deps)

**Split into**:

```
services/council/
+-- orchestrator.py      (200 lines) Meeting flow coordination only
+-- data_fetcher.py      (100 lines) Technical + financial data retrieval
+-- meeting_runner.py    (200 lines) AI rounds (analyze, respond, consensus)
+-- signal_factory.py    (100 lines) Signal creation from consensus
+-- execution_manager.py (150 lines) Gate checks + auto-execution
```

**orchestrator.py** becomes a thin coordinator:
```python
class CouncilOrchestrator:
    def __init__(self):
        self._data_fetcher = CouncilDataFetcher()
        self._meeting_runner = CouncilMeetingRunner()
        self._signal_factory = SignalFactory()
        self._execution_mgr = ExecutionManager()

    async def start_meeting(self, symbol, news_title, ...):
        meeting = self._create_meeting(symbol, news_title, ...)

        data = await self._data_fetcher.fetch(symbol)
        meeting = await self._meeting_runner.run_rounds(meeting, data, ...)
        signal = self._signal_factory.create(meeting, ...)
        signal = await self._execution_mgr.evaluate_and_execute(signal, ...)

        await self._persist_and_notify(meeting, signal)
        return meeting
```

### 4.2 Split Kiwoom REST Client [H3]

**Current**: `services/kiwoom/rest_client.py` (1073 lines, 30+ methods)

**Split into**:
```
services/kiwoom/
+-- token_manager.py    (150 lines) Token lifecycle, Redis cache
+-- price_client.py     (200 lines) Daily prices, real-time quotes
+-- account_client.py   (200 lines) Balance, holdings, P&L
+-- order_client.py     (200 lines) Place, cancel, status
+-- rest_client.py      (100 lines) Facade re-exporting all clients
+-- base.py             (100 lines) Shared HTTP session, error handling
```

### 4.3 Split Triggers [H5]

**Current**: `services/signals/triggers.py` (976 lines, 42 methods)

**Split into**:
```
services/signals/triggers/
+-- __init__.py         TriggerEngine (orchestrator)
+-- core.py             T01-T06 (6 core triggers)
+-- secondary.py        T07-T22 (16 secondary triggers)
+-- tertiary.py         T23-T42 (20 tertiary triggers)
+-- scoring.py          Composite score calculation
```

### 4.4 Formalize Orchestrator State Interface [H9]

Replace direct state mutation with explicit methods:
```python
class CouncilOrchestrator:
    def add_meeting(self, meeting: CouncilMeeting) -> None:
        self._meetings.append(meeting)

    def add_pending_signal(self, signal: InvestmentSignal) -> None:
        self._pending_signals.append(signal)

    def queue_execution(self, signal: InvestmentSignal) -> None:
        self._queued_executions.append(signal)

    def remove_queued(self, signal: InvestmentSignal) -> None:
        self._queued_executions = [s for s in self._queued_executions if s.id != signal.id]
```

### 4.5 Resolve Circular Dependencies [H8]

**Current**: `tasks -> council -> signals -> kiwoom -> tasks`

**Fix with event-driven pattern**:
```python
# Instead of:
# scanning_tasks.py imports council_orchestrator

# Use:
# scanning_tasks.py publishes event
from app.core.events import event_bus, SCAN_COMPLETE
await event_bus.emit(SCAN_COMPLETE, {"symbol": symbol, "result": result})

# council listens:
event_bus.subscribe(SCAN_COMPLETE, council_orchestrator.on_scan_complete)
```

### 4.6 Split Report Generator [M11]

**Current**: `services/report_generator.py` (926 lines)

**Split into**:
```
services/reports/
+-- __init__.py
+-- base.py             Shared PDF utilities
+-- stock_report.py     Individual stock reports
+-- portfolio_report.py Portfolio reports
+-- trading_report.py   Trading activity reports
+-- market_report.py    Market overview reports
```

---

## Phase 5: Testing & Observability (P2)

**Goal**: Improve test coverage and production monitoring.
**Risk**: Low - additive changes only.

### 5.1 Unit Tests for Extracted Services

**New test files**:
```
tests/
+-- test_performance_service.py
+-- test_account_service.py
+-- test_base_agent.py
+-- test_stock_lookup.py
+-- test_validators.py
+-- test_llm_utils.py
+-- test_meeting_runner.py
+-- test_signal_factory.py
+-- test_execution_manager.py
```

### 5.2 Improve conftest.py [L7]

Replace `sys.modules` mocking with proper pytest fixtures:
```python
@pytest.fixture
def mock_kiwoom():
    with patch("app.services.kiwoom.rest_client.KiwoomClient") as mock:
        mock.get_daily_prices.return_value = [...]
        yield mock

@pytest.fixture
def mock_openai():
    with patch("openai.AsyncOpenAI") as mock:
        yield mock
```

### 5.3 Add Observability [L6]

- Add `prometheus-fastapi-instrumentator` for request metrics
- Add counters for: rate limit hits, WS connections, council meetings, signal executions
- Add health check for DB + Redis + Kiwoom API connectivity
- Structured error logging with correlation IDs

### 5.4 CI/CD Pipeline [L9]

**New file**: `.github/workflows/ci.yml`
```yaml
- pytest with coverage (target: 70%)
- ruff lint + format check
- mypy type checking
- Docker build validation
```

---

## Execution Order & Dependencies

```
Phase 1 (Security)           Phase 2 (Services)
  1.1 WS Auth                  2.1 PerformanceService
  1.2 Async DB Fix     -->     2.2 AccountService
  1.3 Health/Shutdown           2.3 Route Logic Extract
  1.4 Error Responses           2.4 Test Endpoints
  1.5 CORS Config               2.5 Monkey-patch Fix
        |                             |
        v                             v
Phase 3 (Dedup)              Phase 4 (Architecture)
  3.1 Agent Base Class          4.1 Split Orchestrator
  3.2 Indicator Consolidate     4.2 Split Kiwoom Client
  3.3 Shared Validators  -->    4.3 Split Triggers
  3.4 LLM Utils                 4.4 State Interface
  3.5 Response Models           4.5 Circular Deps
  3.6 Stock Lookup              4.6 Split Reports
        |                             |
        +-------------+---------------+
                      |
                      v
              Phase 5 (Testing)
                5.1 Unit Tests
                5.2 Conftest Improve
                5.3 Observability
                5.4 CI/CD
```

## Impact Estimates

| Phase | Files Changed | Files Added | Lines Removed | Lines Added | Net Change |
|-------|--------------|-------------|---------------|-------------|------------|
| Phase 1 | ~12 | 1 | ~50 | ~200 | +150 |
| Phase 2 | ~10 | 3 | ~800 | ~600 | -200 |
| Phase 3 | ~15 | 5 | ~600 | ~400 | -200 |
| Phase 4 | ~10 | 12 | ~2500 | ~2200 | -300 |
| Phase 5 | ~3 | 12 | ~100 | ~1500 | +1400 |
| **Total** | **~50** | **33** | **~4050** | **~4900** | **+850** |

Note: Net increase is from added tests and new module boilerplate. Actual business logic decreases by ~1500 lines through deduplication.

## Success Criteria

| Metric | Current | Target |
|--------|---------|--------|
| Largest file | 1073 lines | < 400 lines |
| Max method length | 470 lines | < 100 lines |
| Agent boilerplate duplication | 70% | < 10% |
| Indicator implementations | 3 copies | 1 canonical |
| Sync DB in async routes | 5 files | 0 files |
| Unauthenticated WebSocket | 6 endpoints | 0 endpoints |
| Test coverage | ~30% est. | > 70% |
| Route avg. LOC | 430 lines | < 200 lines |
