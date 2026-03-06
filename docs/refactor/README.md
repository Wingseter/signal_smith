# Signal Smith Refactoring Plan

**Date**: 2026-03-06
**Scope**: Full backend codebase (`backend/app/`)
**Total LOC**: ~29,400 lines across 97 Python files

## Documents

| File | Description |
|------|-------------|
| [01_current_state.md](./01_current_state.md) | Architecture overview, module map, dependency graph |
| [02_issues.md](./02_issues.md) | All identified issues (Critical / High / Medium / Low) |
| [03_refactor_plan.md](./03_refactor_plan.md) | Phase-by-phase refactoring plan with priorities |

## Quick Summary

### Top 5 Critical Issues

1. **WebSocket authentication missing** - 6 endpoints accept unauthenticated connections
2. **Sync DB in async routes** - 5 route files block the event loop with synchronous DB calls
3. **God Object orchestrator** - `start_meeting()` is 470 lines, 9+ module dependencies
4. **Agent code duplication** - 4 agents share 70% identical boilerplate (no base class)
5. **Business logic in routes** - council.py, performance.py, analysis.py contain service-level logic

### Refactoring Phases

| Phase | Focus | Estimated Files | Risk |
|-------|-------|-----------------|------|
| **Phase 1** | Security & Stability | ~10 files | Low |
| **Phase 2** | Service Layer Extraction | ~15 files | Medium |
| **Phase 3** | Code Deduplication | ~20 files | Medium |
| **Phase 4** | Architecture Restructure | ~25 files | High |
| **Phase 5** | Testing & Observability | ~15 files | Low |

### Codebase Health Score

| Area | Score | Notes |
|------|-------|-------|
| Core Layer | 8.2/10 | Well-designed, minor fixes needed |
| Models | 8.0/10 | Modern SQLAlchemy 2.0, clean relationships |
| Config | 7.5/10 | Pydantic 2.x validators, hardcoded CORS |
| API Routes | 5.5/10 | Heavy business logic, inconsistent patterns |
| Council Service | 6.0/10 | Sophisticated but tightly coupled |
| Signals Service | 6.5/10 | Functional but monolithic triggers |
| News Service | 6.0/10 | Hardcoded stock map, fragile parsing |
| Kiwoom Client | 5.5/10 | 1073-line monolith, needs splitting |
| Agents | 5.0/10 | Massive duplication, no abstraction |
| Tasks | 6.0/10 | Circular deps, async/sync bridge issues |
| Backtesting | 7.5/10 | Good framework, missing advanced features |
| Testing | 6.0/10 | Clever mocking, fragile setup, no CI |
