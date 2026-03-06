# 02. Identified Issues

## Critical (Must Fix)

### C1. WebSocket Authentication Missing
- **Impact**: Unauthenticated access to real-time trading data
- **Files**: `api/routes/council.py:599`, `api/routes/signals.py:128`, `api/routes/news_monitor.py:333`, `api/websocket/handler.py` (3 endpoints)
- **Fix**: Add token-based handshake authentication middleware for all 6 WebSocket endpoints

### C2. Sync DB in Async Routes (Event Loop Blocking)
- **Impact**: Blocks FastAPI event loop, degrades all concurrent request performance
- **Files**: `api/routes/reports.py`, `api/routes/optimizer.py`, `api/routes/performance.py`, `api/routes/sectors.py`, `api/routes/backtest.py`
- **Pattern**: These use `get_sync_db_dep()` in async route handlers
- **Fix**: Migrate to async session (`get_db()`) or use `run_in_executor()`

### C3. Business Logic in Route Handlers
- **Impact**: Untestable, duplicated logic; routes should be thin controllers
- **Locations**:
  - `api/routes/council.py:530-577` - Account summary caching with staleness check
  - `api/routes/performance.py:269-451` - Equity curve + risk metrics calculation
  - `api/routes/analysis.py:261-350` - Multi-agent weighted scoring
  - `api/routes/sectors.py:113-365` - Sector performance analysis
  - `api/routes/optimizer.py:162-527` - Portfolio optimization logic
- **Fix**: Extract to dedicated service modules

### C4. Orchestrator God Object (694 lines)
- **Impact**: Hard to test, maintain, and extend; 9+ direct module dependencies
- **File**: `services/council/orchestrator.py`
- **Root cause**: `start_meeting()` is 470 lines handling data fetch, AI rounds, gates, execution
- **Fix**: Split into `CouncilDataFetcher`, `CouncilMeetingRunner`, `CouncilExecutor`

### C5. No Global Error Handler Consistency
- **Impact**: Inconsistent error responses across endpoints
- **Pattern**: Mix of `HTTPException`, service result dicts, silent failures
- **Files**: All route files
- **Fix**: Implement FastAPI exception middleware with structured error responses

---

## High (Should Fix)

### H1. Agent Code Duplication (~70% boilerplate)
- **Impact**: 4 agents repeat constructor, client init, JSON parsing, error handling
- **Files**: `agents/claude_agent.py`, `agents/chatgpt_agent.py`, `agents/gemini_agent.py`, `agents/ml_agent.py`
- **Fix**: Extract `BaseAgent` ABC with shared `_get_client()`, `_parse_json_response()`, `_call_with_retry()`

### H2. Technical Indicator Triple Implementation
- **Impact**: Same calculations in 3 places, diverge over time
- **Files**: `services/signals/indicators.py` (531 lines), `services/council/technical_indicators.py` (379 lines), `agents/chatgpt_agent.py` (inline calculations)
- **Fix**: Single canonical `indicators` module, imported by council and agents

### H3. Kiwoom REST Client Monolith (1073 lines)
- **Impact**: 30+ methods, mixed concerns (auth, prices, orders, account)
- **File**: `services/kiwoom/rest_client.py`
- **Fix**: Split into `TokenManager`, `PriceClient`, `AccountClient`, `OrderClient`

### H4. Hardcoded Stock Symbol Map (200+ lines)
- **Impact**: Stale data, not maintainable, duplicated lookup logic
- **File**: `services/news/models.py`
- **Fix**: Move to database table or Redis cache, provide single lookup service

### H5. Triggers Monolith (976 lines, 42 methods)
- **Impact**: High cyclomatic complexity, hard to test individual triggers
- **File**: `services/signals/triggers.py`
- **Fix**: Extract trigger families into separate modules (core, secondary, tertiary)

### H6. Response Format Inconsistency
- **Impact**: Frontend must handle different list wrappers per endpoint
- **Pattern**: `{"items": [...]}` vs `{"results": [...]}` vs `{"signals": [...]}` vs `{"meetings": [...]}`
- **Fix**: Standardize to `{"data": [...], "total": N}` or use consistent Pydantic response models

### H7. Monkey-Patching in news_monitor.py
- **Impact**: Runtime behavior modification, hard to debug
- **File**: `api/routes/news_monitor.py:176-202`
- **Fix**: Use proper dependency injection or callback registration

### H8. Circular Dependencies in Tasks
- **Impact**: Import order matters, fragile module loading
- **Path**: `scanning_tasks -> council.orchestrator -> signals.scanner -> kiwoom -> tasks`
- **Fix**: Invert dependencies with event/queue pattern, or use lazy imports consistently

### H9. Orchestrator State Mutation by Delegates
- **Impact**: sell_meeting and order_executor directly mutate `orch._meetings`, `orch._pending_signals`
- **Files**: `services/council/sell_meeting.py`, `services/council/order_executor.py`
- **Fix**: Add explicit interface methods: `orch.append_meeting()`, `orch.append_signal()`

### H10. Account Query Duplication
- **Impact**: Same account balance/holdings fetched in multiple places
- **Files**: `api/routes/council.py:510-577`, `api/routes/trading.py:196-219`, various task files
- **Fix**: Create `AccountService` with caching

---

## Medium (Should Consider)

### M1. Dual Signal Model Representation
- **Impact**: Manual `to_dict()` conversions, potential serialization bugs
- **Files**: `services/council/models.py` (dataclass) vs `models/transaction.py` (SQLAlchemy)
- **Fix**: Unify with Pydantic models for both in-memory and API serialization

### M2. Input Validation Duplication
- **Impact**: Symbol validation (6-digit check) repeated in 4+ route files
- **Files**: `api/routes/stocks.py`, `api/routes/signals.py`, `api/routes/council.py`, etc.
- **Fix**: Create shared Pydantic validator or FastAPI dependency

### M3. WebSocket Connection Manager Redundancy
- **Impact**: Each WS route creates own `BaseConnectionManager` instance
- **Files**: `api/routes/council.py`, `api/routes/signals.py`, `api/routes/news_monitor.py`
- **Fix**: Centralize into single `WebSocketHub` with channel multiplexing

### M4. Async/Sync Bridge Anti-Pattern
- **Impact**: `asyncio.run()` creates new event loop in Celery tasks
- **File**: `services/tasks/_common.py`
- **Fix**: Use `asgiref.sync_to_async` or dedicated async Celery worker

### M5. LLM JSON Parsing Duplication
- **Impact**: Same markdown-JSON extraction in quant_analyst and fundamental_analyst
- **Files**: `services/council/quant_analyst.py:250-295`, `services/council/fundamental_analyst.py:179-220`
- **Fix**: Extract `parse_llm_json_response()` utility

### M6. Timeout Handling Repeated 6x
- **Impact**: Duplicated ~30 lines per analyst call in orchestrator
- **File**: `services/council/orchestrator.py`
- **Fix**: Extract `_call_analyst_with_timeout(analyst, method, args, fallback)`

### M7. No Lifespan Shutdown Hooks
- **Impact**: No graceful cleanup on app shutdown (connections, queues)
- **File**: `main.py` lifespan context manager
- **Fix**: Add `close_redis()`, flush queued signals, close DB pools

### M8. Error Handlers Return 500 for All Errors
- **Impact**: Client errors (validation, not found) return 500 instead of 4xx
- **File**: `main.py` exception handlers
- **Fix**: Add `http_status_code` to `SignalSmithError`, distinguish client vs server errors

### M9. CORS Hardcoded to Localhost
- **Impact**: Production deployment requires code change
- **File**: `main.py:71-75`
- **Fix**: Move to environment-based CORS origins in config.py

### M10. No Health Check Endpoint
- **Impact**: No way to monitor app liveness
- **Fix**: Add `GET /health` that checks DB + Redis connectivity

### M11. Report Generator Size (926 lines)
- **File**: `services/report_generator.py`
- **Fix**: Split into report type modules (stock, portfolio, trading, market)

### M12. Cost Manager Cooldown Not Enforced
- **Impact**: `is_in_cooldown()` returns True but orchestrator ignores it
- **Files**: `services/council/cost_manager.py`, `services/council/orchestrator.py`
- **Fix**: Check cooldown at start_meeting() entry point

---

## Low (Nice to Have)

### L1. Core `__init__.py` Has No Exports
- **File**: `core/__init__.py`
- **Fix**: Add common re-exports for convenience imports

### L2. Type Annotation Issues
- `security.py:86` - `email: str` should be `Optional[str]`
- `backtest.py:74` - `float` type hint with `Numeric` column, should be `Decimal`

### L3. Awkward Import in database.py
- **Line 59**: `__import__("sqlalchemy").text("SELECT 1")`
- **Fix**: Use `from sqlalchemy import text`

### L4. Audit.py Code Duplication (sync/async)
- **Impact**: ~15 lines duplicated between sync and async functions
- **Fix**: Extract `_build_audit_extra()` helper

### L5. WebSocket Channel Tracking Edge Case
- **File**: `core/websocket.py:115`
- **Impact**: `disconnect()` uses default channel during symbol broadcast cleanup
- **Fix**: Track websocket-to-channel mapping

### L6. No Prometheus Metrics
- **Impact**: No observability for rate limit hits, WS connections, event emissions
- **Fix**: Add prometheus-fastapi-instrumentator

### L7. Test Conftest Fragility
- **Impact**: Pre-mocking via `sys.modules` is order-dependent
- **File**: `tests/conftest.py`
- **Fix**: Consider pytest plugins or docker-based test environment

### L8. TODO Comments in Production
- **File**: `api/routes/council.py:602` - WebSocket auth TODO
- **File**: `api/routes/notifications.py` - User settings storage TODO

### L9. No CI/CD Pipeline
- **Impact**: No automated testing or deployment
- **Fix**: Add GitHub Actions with test + lint + deploy stages

### L10. Backtesting Missing Features
- No benchmark comparison by default
- No drawdown-based stop trading
- No trailing stops
- No dividend handling

---

## Issue Distribution Summary

| Severity | Count | Primary Area |
|----------|-------|-------------|
| Critical | 5 | Security, async, architecture |
| High | 10 | Duplication, coupling, consistency |
| Medium | 12 | Models, validation, error handling |
| Low | 10 | Style, testing, observability |
| **Total** | **37** | |

### By Component

| Component | Critical | High | Medium | Low | Total |
|-----------|----------|------|--------|-----|-------|
| API Routes | 2 | 2 | 3 | 1 | 8 |
| Council Service | 1 | 2 | 3 | 0 | 6 |
| Core Layer | 0 | 0 | 3 | 4 | 7 |
| Services (other) | 0 | 3 | 2 | 1 | 6 |
| Agents | 0 | 1 | 0 | 0 | 1 |
| Tasks | 0 | 1 | 1 | 0 | 2 |
| Models/Config | 0 | 0 | 1 | 1 | 2 |
| Testing/Infra | 0 | 0 | 1 | 3 | 4 |
| Cross-cutting | 2 | 1 | 0 | 0 | 3 |
