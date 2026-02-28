# Signal Smith 프로젝트 전체 분석 및 개선 연구

작성일: 2026-02-28  
대상 경로: `backend`, `frontend`, `docs`, `docker-compose.yml`

---

## 0. 분석 방법

이번 분석은 코드/운영/검증 관점을 함께 보도록 아래 도구를 병행 사용했다.

- MCP `serena`: 심볼 단위 구조 분석 (핵심 서비스/라우트/태스크 흐름)
- Shell 실행: 정적 구조 점검, 빌드/린트/타입체크/컴파일 검증
- Web 리서치: 운영 신뢰성(429/retry, Celery, FastAPI 배포) 기준 보강

실행 검증 결과:

- `frontend`: `npm run lint` 통과
- `frontend`: `npm run type-check` 통과
- `backend`: `python -m compileall backend/app` 통과
- `backend`: `pytest` 미실행 (현재 실행 환경에 `pytest` 미설치)

---

## 1. 현재 시스템 요약

### 1.1 아키텍처

- Backend: FastAPI + SQLAlchemy(Async/Sync 혼용) + Redis + Celery(Worker/Beat)
- Trading Core: Kiwoom REST 연동 + AI Council(뉴스/퀀트/펀더멘털 합의)
- Frontend: React + TypeScript + Zustand + WebSocket 실시간 UI
- 데이터 플로우: 뉴스/퀀트 트리거 -> Council 회의 -> 시그널 DB 저장 -> 자동/수동 체결

### 1.2 코드 규모(대략)

- Python 파일: 102개
- TS/TSX 파일: 59개
- 주요 대형 파일:
- `backend/app/services/council/orchestrator.py` (1390 lines)
- `backend/app/services/tasks/signal_tasks.py` (1130 lines)
- `backend/app/services/kiwoom/rest_client.py` (1057 lines)
- `frontend/src/components/Analysis/AnalysisPanel.tsx` (1231 lines)

현재는 기능 폭이 넓고 실제 매매/신호 로직이 깊게 들어가 있지만, 일부 레거시 코드/운영 취약점이 섞여 있는 상태다.

---

## 2. 핵심 진단 (우선순위 순)

## 2.1 Critical

| 이슈 | 근거(파일:라인) | 영향 |
|---|---|---|
| Price 태스크가 현재 Kiwoom 클라이언트 API와 불일치 | `backend/app/services/tasks/price_tasks.py:48`, `:102` (`get_current_price`, `get_price_history` 호출) / 실제 클라이언트는 `get_stock_price`, `get_daily_prices` (`backend/app/services/kiwoom/rest_client.py`) | 주기 가격수집/히스토리 수집 태스크 런타임 실패 가능성 높음 |
| 데이터 정리 태스크가 존재하지 않는 컬럼 업데이트 | `backend/app/services/tasks/maintenance_tasks.py:28` (`is_active=False`) / `TradingSignal` 모델에 `is_active` 없음 (`backend/app/models/transaction.py`) | 정리 태스크 실행 실패, 운영 중 예외 누적 |
| 자동매매 제어 API가 인증 없이 노출 | `backend/app/api/routes/council.py:99`, `:119`, `:210`, `:225`, `:240`, `:567`, `:586` (모두 `get_current_user` 미적용) | 외부 호출로 모니터링 시작/중지, 시그널 승인/체결 가능 위험 |
| 런타임 스키마 변경(ALTER TABLE) 의존 | `backend/app/main.py:26-39` | 시작 시 DDL 시도, 마이그레이션 거버넌스 붕괴/권한 이슈 |

## 2.2 High

| 이슈 | 근거(파일:라인) | 영향 |
|---|---|---|
| 환경 설정 문서와 실제 설정 키/DB 타입 드리프트 | `.env.example:8-37`(Postgres + KIS 키) vs `backend/app/config.py:27-41`(MySQL + KIWOOM 키) | 신규 셋업 실패, 운영자 혼선 |
| TLS 검증 비활성화 | `backend/app/services/kiwoom/rest_client.py:195` (`verify=False`) | MITM/인증서 관련 보안 리스크 |
| 거래일 캘린더 하드코딩(2025~2026) | `backend/app/services/council/trading_hours.py:55-88` | 2027+ 오작동, 휴장일 오판에 따른 체결 리스크 |
| DB 마이그레이션 실체 부재 | `backend/alembic`에 `env.py`만 존재 (versions 없음) + `init_db`는 연결확인만 수행 (`backend/app/core/database.py:51-60`) | 스키마 이력 관리 불가, 배포 재현성 저하 |
| 테스트가 핵심 로직보다 smoke 중심 | `backend/tests/test_services_smoke.py`, `test_api_smoke.py` 중심. `orchestrator/signal_tasks/trading_service` 행위 검증 거의 없음 | 회귀 버그 사전 차단 어려움 |

## 2.3 Medium

| 이슈 | 근거(파일:라인) | 영향 |
|---|---|---|
| WebSocket 매니저 구현 중복 | `backend/app/core/websocket.py` + 별도 `backend/app/api/websocket/handler.py:25-88` | 유지보수 포인트 분산, 버그 수정 누락 가능 |
| 뉴스 모니터링에서 런타임 monkey patch 사용 | `backend/app/api/routes/news_monitor.py:172-202` | 모듈 로드 순서/테스트 격리 시 부작용 가능 |
| 프론트 재연결 타이머 정리 미흡 가능성 | `frontend/src/components/Layout.tsx:262-287` (`setTimeout(connectWebSockets, 3000)`) | unmount/reload 시 불필요 재연결 시도 가능 |
| Celery sync 태스크에서 공용 이벤트 루프 직접 실행 | `backend/app/services/tasks/_common.py:9-19` | 워커 상황에 따라 루프 충돌/디버깅 난이도 증가 |

---

## 3. 개선 방향 (실행 로드맵)

## Phase 1 (0~2주): 치명 버그/보안 봉합

목표: “실매매 오동작 방지 + 인증 경계 확립”

1. `price_tasks` API mismatch 수정
- `KiwoomRestClient` 직접 호출 제거
- `stock_service` 경유 또는 `kiwoom_client.get_stock_price/get_daily_prices`로 정렬

2. `maintenance_tasks`의 잘못된 `is_active` 업데이트 제거
- 만료 시그널은 `signal_status`(예: `expired`)와 `is_executed` 조합으로 처리

3. `council/news-monitor/signals` 민감 엔드포인트 인증 추가
- 최소 `Depends(get_current_user)` 적용
- 운영용/디버그용 테스트 엔드포인트 분리 또는 비활성화

4. 런타임 ALTER 제거
- `main.py`의 `_ensure_signal_columns` 삭제
- Alembic migration 스크립트로 대체

완료 기준:

- 위 4개 항목에 대한 통합 테스트(성공/실패 케이스) 추가
- 인증 없는 호출 시 401/403 보장

## Phase 2 (2~4주): 데이터/운영 신뢰성 정렬

목표: “재현 가능한 배포 + 데이터 일관성 강화”

1. 마이그레이션 체계 복구
- `backend/alembic/versions` 도입
- 현재 운영 스키마 baseline migration 생성

2. 환경 변수 계약 정리
- `.env.example`을 `config.py` 기준으로 전면 갱신
- “필수/선택/운영전용” 키 문서화

3. 거래일 캘린더 외부화
- KRX 거래일 API 또는 관리 가능한 캘린더 파일 사용
- 연도 경계 자동 갱신

4. WebSocket 계층 통합
- `core/websocket.py` 기준으로 단일 매니저 패턴 확정

완료 기준:

- 신규 개발자가 `.env.example`만으로 로컬 기동 성공
- 스키마 변경이 migration만으로 반영됨

## Phase 3 (4~8주): 구조 리팩터링 + 관측성

목표: “대형 파일 분해 + 장애 원인 추적 강화”

1. `orchestrator.py` 분해
- 회의 진행, 리스크 게이트, 주문 실행, DB 동기화를 모듈 분리

2. `signal_tasks.py` 분해
- 스캔/매도감시/큐처리/리밸런싱을 독립 서비스로 분리

3. 관측성 강화
- 주문/시그널/큐 처리에 `request_id`/`signal_id` 중심 구조화 로그
- 핵심 메트릭: 체결 성공률, 큐 체류 시간, 429 재시도 성공률

4. 태스크 멱등성 점검
- 재시도 가능한 태스크에 대해 idempotency key 도입

완료 기준:

- 장애 리포트 시 “어느 시그널/어느 태스크”인지 1분 내 추적 가능
- 대형 파일 1000+ 라인 구간 축소

## Phase 4 (8주+): 전략 고도화

- 포지션 사이징/리밸런싱 규칙을 KPI 기반 자동 튜닝
- 시그널 품질 회귀 테스트셋(과거 구간) 운영
- Paper/Live 분리 게이트 강화 (실전 계좌 오주문 방지)

---

## 4. 바로 실행 가능한 P0 체크리스트

- [ ] `price_tasks.py` 메서드명 불일치 수정
- [ ] `maintenance_tasks.py` `is_active` 참조 제거
- [ ] `council.py` 민감 API 인증 적용
- [ ] `council/ws`, `news-monitor/ws`, `signals/ws` 인증 전략 정의(토큰/세션)
- [ ] `main.py` 런타임 ALTER 제거 + Alembic migration 추가
- [ ] `.env.example`를 `config.py`와 1:1 동기화
- [ ] `rest_client.py`의 `verify=False` 제거 및 인증서 정책 확정
- [ ] `trading_hours.py` 거래일 소스 외부화
- [ ] `orchestrator approve/reject/execute` 시 DB 상태 동기화 테스트 추가
- [ ] 회귀 테스트 최소 세트(시그널 생성 -> 승인 -> 큐 -> 체결) 구축

---

## 5. MCP/에이전트 활용 권장 운영안

다음 개선 작업을 빠르게 진행하려면 아래 조합을 권장한다.

1. Serena MCP (심볼 단위 리팩터링)
- 대형 파일 분해, 참조 추적, 영향 범위 분석에 최적

2. Pytest MCP (실패군 분석)
- 실패 패턴 그룹화 후 우선순위 디버깅 자동화

3. Playwright/Chrome DevTools MCP (실시간 UI 검증)
- WebSocket 재연결, 알림/상태 반영, 페이지 전환 회귀 확인

4. Web 리서치 MCP (운영 표준 업데이트)
- Celery/FastAPI/HTTP 표준 변경사항 주기 검토

권장 루프:

- 코드 변경 -> pytest smoke/integration -> 웹소켓 UI 회귀 -> 배포 전 체크리스트 자동 검증

---

## 6. 외부 레퍼런스 (운영 기준)

- Celery Task 가이드(멱등성, ack, retry): https://docs.celeryq.dev/en/v5.5.0/userguide/tasks.html
- FastAPI WebSocket 기본 패턴: https://fastapi.tiangolo.com/advanced/websockets/
- FastAPI 배포 개념(멀티 프로세스/메모리 분리): https://fastapi.tiangolo.com/deployment/concepts/
- HTTP 429 표준(Retry-After): https://www.rfc-editor.org/rfc/rfc6585
- Exponential Backoff + Jitter: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- Diversification 기본 원칙: https://www.investor.gov/introduction-investing/investing-basics/glossary/diversification
- SEC 자산배분/리밸런싱 가이드: https://www.sec.gov/investor/pubs/assetallocation.htm
- FINRA 과도매매 예방 가이드: https://www.finra.org/investors/insights/3-ways-guard-against-excessive-trading-your-brokerage-account

---

## 7. 최종 결론

이 프로젝트는 이미 “실매매 가능한 기능 폭”을 갖췄지만, 현재 가장 큰 리스크는 전략 정확도보다 운영 안정성/보안 경계/레거시 불일치다.  
따라서 다음 순서가 가장 효율적이다.

1. Critical 버그 및 인증 취약점 선해결
2. 마이그레이션/환경변수 계약 정렬
3. 대형 오케스트레이션 파일 분해 + 테스트/관측성 강화

이 순서를 따르면 실전 운용 리스크를 크게 줄이면서 전략 고도화로 자연스럽게 넘어갈 수 있다.
