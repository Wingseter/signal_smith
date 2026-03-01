# Signal Smith 최종 개선 플랜

작성일: 2026-03-01
근거: 3개 분석 문서 종합 + 코드 실사 검증

---

## 0. 현재 상태 (이미 완료된 항목)

| 항목 | 커밋 | 상태 |
|------|------|------|
| 3중 게이트 (최소포지션/현금버퍼/최대종목수) | `6101484` | ✅ 완료 |
| 429 재시도 (Retry-After + exponential backoff + jitter) | `6101484` | ✅ 완료 |
| 데이터 품질 게이트 (AI 분석 2개 이상 실패 시 차단) | `6101484` | ✅ 완료 |
| AI 클라이언트 OpenAI-compatible SDK 전환 | `64a33c2` | ✅ 완료 |
| AnalystRole Enum (CLAUDE_FUNDAMENTAL 정상) | - | ✅ 확인 |
| Signal DB 동기화 함수 (`_update_signal_status_in_db`) 존재 | - | ✅ 확인 |

---

## 1. Phase 1: 코드 버그 및 보안 봉합 (1주)

> 목표: "실매매 오동작 방지 + 인증 경계 확립"

### 1.1 [P0-BUG] price_tasks API 메서드명 불일치 수정

**문제**: `price_tasks.py`가 존재하지 않는 메서드를 호출
**영향**: 주기적 가격수집/히스토리수집 태스크 런타임 실패

| 파일:라인 | 현재(잘못됨) | 수정 |
|---|---|---|
| `price_tasks.py:48` | `client.get_current_price(symbol)` | `client.get_stock_price(symbol)` |
| `price_tasks.py:102` | `client.get_price_history(symbol, start, end)` | `client.get_daily_prices(symbol)` |

- `get_daily_prices`는 파라미터가 `symbol`만 받으므로 start/end 로직도 조정 필요
- 반환값이 역순(최신→과거)이므로 `reversed()` 처리 확인

### 1.2 [P0-BUG] maintenance_tasks 존재하지 않는 컬럼 참조 제거

**문제**: `TradingSignal` 모델에 `is_active` 컬럼 없음
**영향**: cleanup 태스크 실행 시 SQL 예외

| 파일:라인 | 현재(잘못됨) | 수정 |
|---|---|---|
| `maintenance_tasks.py:28` | `.values(is_active=False)` | `.values(signal_status='expired')` 또는 `is_executed=True` |

### 1.3 [P0-BUG] abs(final_percent)로 인한 SELL 판단 무력화

**문제**: `abs()`가 음수 비중을 양수로 변환하여 `final_percent < 0` 분기가 절대 실행되지 않음
**영향**: AI가 매도 권고(음수 비중)해도 매수로 처리될 가능성

| 파일:라인 | 현재 | 수정 방향 |
|---|---|---|
| `orchestrator.py:391` | `final_percent = min(25, abs(final_percent))` | `sign` 보존 후 buy/sell 별도 처리 |
| `orchestrator.py:871-873` | `final_percent < 0` 분기 | `abs()` 제거, 부호 기반 action 결정 |

```python
# 수정안
raw_percent = final_percent
final_percent_capped = min(25, abs(raw_percent))
action = "sell" if raw_percent < 0 else "buy"
```

### 1.4 [P0-BUG] PARTIAL_SELL 생명주기 불일치

**문제**: 매도 회의는 `PARTIAL_SELL` 생성하지만, 큐 조회/API 필터가 `buy/sell`만 허용
**영향**: 부분매도 시그널이 큐/조회에서 누락

| 위치 | 수정 |
|---|---|
| `signal_tasks.py:573` (큐 조회 필터) | `partial_sell` 추가 |
| `council.py:169` (API 필터) | `partial_sell` 추가 |
| `models/transaction.py` (signal_type) | `partial_sell` 허용 확인 |

**대안**: `PARTIAL_SELL`을 폐기하고 `SELL` + `sell_percent` 메타 필드로 단순화

### 1.5 [P0-BUG] approve/reject/execute 경로 DB 동기화 누락

**문제**: `_update_signal_status_in_db` 함수는 존재하지만 approve/reject/execute 경로에서 호출 안 됨
**영향**: 서버 재시작 시 메모리 상태와 DB 불일치

| 파일:라인 | 수정 |
|---|---|
| `orchestrator.py:706-800` (approve/reject/execute) | 각 경로 끝에 `_update_signal_status_in_db()` 호출 추가 |

### 1.6 [P0-BUG] stop/target 트리거 시 조기 is_executed=True

**문제**: 실제 매도 주문 체결 전에 `is_executed=True`로 마킹
**영향**: 매도 실패 시 재시도/재평가 누락

| 파일:라인 | 수정 |
|---|---|
| `signal_tasks.py:70-98` | 매도 주문 제출 성공 확인 후에만 `is_executed=True` 설정 |

### 1.7 [P0-BUG] avg_buy_price=0 전달로 인한 0 나누기 위험

**문제**: `_trigger_sell_for_signal`이 `avg_buy_price=0` 전달
**영향**: 수익률 계산 시 ZeroDivisionError

| 파일:라인 | 수정 |
|---|---|
| `signal_tasks.py:799-806` | 실제 보유 평단가 조회 fallback |
| `orchestrator.py:1045` | `avg_buy_price <= 0` 보호 조건 추가 |

### 1.8 [P0-SEC] Council API 인증 적용

**문제**: 모든 council 엔드포인트에 `get_current_user` 미적용
**영향**: 인증 없이 모니터링 시작/중지, 시그널 승인/체결 가능

수정 대상 (`council.py`):
- `POST /start`, `POST /stop` → 인증 필수
- `POST /signals/approve`, `POST /signals/reject`, `POST /signals/execute` → 인증 필수
- `GET /meetings`, `GET /signals/pending` → 인증 필수 (또는 읽기전용은 선택)

```python
# 최소 적용 패턴
@router.post("/start")
async def start_monitoring(user=Depends(get_current_user)):
    ...
```

동일하게 `news_monitor.py`, `signals.py` 민감 엔드포인트에도 적용.

### 1.9 [P0-SEC] 런타임 ALTER TABLE 제거

**문제**: `main.py:26-39`에서 앱 시작 시 DDL 직접 실행
**영향**: 마이그레이션 거버넌스 붕괴, 권한 이슈

| 수정 |
|---|
| `_ensure_signal_columns()` 함수 삭제 |
| `lifespan()`에서 `await _ensure_signal_columns()` 호출 제거 |
| 해당 컬럼이 이미 존재하는지 DB에서 확인, 없으면 Alembic migration으로 추가 |

### Phase 1 완료 기준
- [ ] 위 9개 항목에 대한 수정 + 단위테스트
- [ ] 인증 없는 민감 API 호출 시 401/403 반환 확인
- [ ] `price_tasks`, `maintenance_tasks` 정상 실행 확인
- [ ] PARTIAL_SELL 시그널이 큐/API에서 조회 가능 확인

---

## 2. Phase 2: 운영 신뢰성 정렬 (2주)

> 목표: "재현 가능한 배포 + 데이터 일관성 강화 + 매매 논리 안정화"

### 2.1 Alembic 마이그레이션 체계 구축

**현재**: `alembic/versions/` 디렉토리 비어있음

| 작업 | 세부 |
|---|---|
| baseline migration 생성 | 현재 운영 스키마를 `alembic revision --autogenerate`로 캡처 |
| `main.py` DDL 제거 후 migration으로 대체 | Phase 1.9와 연계 |
| CI에 `alembic upgrade head` 검증 추가 | 배포 전 마이그레이션 자동 실행 |

### 2.2 환경 변수 계약 정리

**현재 드리프트**:
| 항목 | `.env.example` | `config.py` | 심각도 |
|---|---|---|---|
| DB 타입 | `postgresql+asyncpg://` | `mysql+aiomysql://` | 🔴 CRITICAL |
| Kiwoom 키 | `KIS_*` | `kiwoom_*` | 🔴 불일치 |
| AI 모델 | `gpt-4-turbo-preview` | `gpt-4o-mini` | 🟡 |

**수정**: `.env.example`을 `config.py` 기준으로 전면 동기화. 필수/선택/운영전용 키 구분 주석 추가.

### 2.3 거래일 캘린더 외부화

**현재**: `trading_hours.py:56-88`에 2025-2026 휴일 하드코딩
**2027년부터 오작동 확정**

| 방안 | 장단점 |
|---|---|
| A. KRX 공개 캘린더 JSON 파일 | 연 1회 수동 갱신, 간단 |
| B. KRX API 조회 | 자동화되나 API 의존성 추가 |

**권장**: A안 (JSON 파일) + 연초 자동 알림

### 2.4 시그널 상태머신 명시화

**현재 문제**: 상태 전이가 코드 곳곳에 분산되어 있어 회귀 위험 높음

```
PENDING → APPROVED → QUEUED → AUTO_EXECUTED → FILLED
                  ↘ REJECTED
                  ↘ CANCELLED
```

| 수정 |
|---|
| `SignalStatus` Enum 정의 + 허용 전이 매트릭스 |
| 상태 전이 함수를 단일 모듈로 집중 (상태 전이 시 자동 DB 동기화) |
| PARTIAL_SELL을 공식 상태/액션으로 포함 |

### 2.5 거래시간 정책 일원화

**현재 불일치**:
- `_common.py:22-27` (`is_market_hours`): 정규장만 허용
- `trading_hours.py:147-153` (`can_execute_order`): 장전/장후 허용

**수정**: 단일 정책 모듈로 통합, 태스크와 주문 실행이 동일한 세션 판정 사용

### 2.6 WebSocket 매니저 통합

**현재**: `core/websocket.py` + `api/websocket/handler.py`에 중복 구현

**수정**: `core/websocket.py`의 `ChannelConnectionManager`를 표준으로 확정, `handler.py`는 이를 import하여 사용

### 2.7 TLS 검증 정책 확정

**현재**: `rest_client.py:195` — `verify=False`

| 환경 | 정책 |
|---|---|
| Mock API (개발) | `verify=False` 허용 (config 분기) |
| Production | `verify=True` 강제 |

`config.py`에 `kiwoom_verify_ssl: bool` 설정 추가

### 2.8 Celery 이벤트 루프 처리 개선

**현재**: `_common.py:9-19`의 `run_async()`가 Celery 워커 스레드에서 불안정

```python
# 수정안: 항상 새 루프 생성
def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

### Phase 2 완료 기준
- [ ] `.env.example`만으로 신규 개발자 로컬 기동 성공
- [ ] 스키마 변경이 Alembic migration으로만 반영
- [ ] 시그널 상태 전이가 단일 모듈에서 관리됨
- [ ] WebSocket 매니저가 단일 구현체로 통합됨

---

## 3. Phase 3: 구조 리팩터링 + 관측성 (3~4주)

> 목표: "대형 파일 분해 + 장애 원인 1분 내 추적"

### 3.1 orchestrator.py 분해 (1390줄 → 4 모듈)

| 모듈 | 책임 | 예상 줄수 |
|---|---|---|
| `orchestrator.py` | 회의 진행 + 라운드 관리 (코어) | ~400 |
| `risk_gate.py` | 3중 게이트 + 데이터 품질 게이트 | ~200 |
| `order_executor.py` | 주문 실행 + 큐 관리 + DB 동기화 | ~400 |
| `sell_meeting.py` | 매도 회의 전용 로직 | ~300 |

### 3.2 signal_tasks.py 분해 (1130줄 → 3 모듈)

| 모듈 | 태스크 | 예상 줄수 |
|---|---|---|
| `monitoring_tasks.py` | `monitor_signals`, `monitor_holdings_sell` | ~350 |
| `execution_tasks.py` | `auto_execute_signal`, `process_council_queue`, `rebalance_holdings` | ~400 |
| `scanning_tasks.py` | `scan_signals`, `refresh_stock_universe`, `refresh_account_summary` | ~350 |

### 3.3 관측성 강화

| 항목 | 세부 |
|---|---|
| 구조화 로그 | 모든 주문/시그널/큐 처리에 `signal_id`, `symbol`, `action` 필드 포함 |
| 감사 로그 | 게이트 차단/조기 return 사유를 DB `signal_events` 테이블에 기록 |
| 핵심 메트릭 | 체결 성공률, 큐 체류 시간, 429 재시도 성공률, 게이트 차단률 |

### 3.4 태스크 멱등성

| 대상 | 방법 |
|---|---|
| `process_council_queue` | `signal_id` 기반 idempotency key (중복 실행 방지) |
| `auto_execute_signal` | 주문 제출 전 기존 주문 존재 여부 확인 |
| `collect_stock_prices` | 동일 시각 중복 가격 방지 (UNIQUE constraint) |

### 3.5 테스트 보강

**현재**: smoke 테스트 9개만 존재, 핵심 비즈니스 로직 검증 없음

| 우선순위 | 테스트 범위 |
|---|---|
| P0 | 3중 게이트 동작 검증 (경계값 테스트) |
| P0 | 시그널 상태 전이 정합성 |
| P0 | PARTIAL_SELL 큐/조회 포함 확인 |
| P1 | 매도 트리거 → 회의 → 주문 E2E |
| P1 | 429 재시도 동작 검증 (mock) |
| P2 | 백테스트 엔진 ↔ 실거래 전략 파라미터 일치 |

### Phase 3 완료 기준
- [ ] 1000줄 이상 파일 없음
- [ ] 장애 발생 시 "어느 시그널/어느 태스크"인지 로그만으로 1분 내 추적 가능
- [ ] 핵심 매매 로직 테스트 커버리지 > 70%

---

## 4. Phase 4: 전략 고도화 (지속)

> 목표: "수익률 개선 + 포트폴리오 효율 극대화"

### 4.1 신호 강도 기반 비선형 사이징

현재 AI가 자유롭게 제안한 `%`를 그대로 사용 → 소액/과대 포지션 혼재

| 신뢰도 구간 | 기본 배분 | 보정 |
|---|---|---|
| 0.60~0.69 | 8% | 고변동성 종목: -1단계 |
| 0.70~0.79 | 12% | 기존 보유 상관 높은 종목: -1단계 |
| 0.80~0.89 | 16% | - |
| 0.90+ | 20% | - |

### 4.2 드리프트 리밸런싱 밴드

현재 매수 시 25% 상한만 체크, 가격 상승 후 초과 비중 방치

| 비중 | 행동 |
|---|---|
| > 25% | 부분매도 후보 등록 (다음 리밸런싱 시 자동 교정) |
| 20~25% | 유지 |
| < 20% | 신규매수 우선순위 대상 |

핵심: 즉시 강제매도가 아니라 **다음 이벤트 시 자동 교정** (거래비용 절감)

### 4.3 교체형 매수 로직

보유 종목이 최대치일 때 신규 매수 대신 교체 검토:

```
교체 조건:
1. 신규 신호 점수 > 보유 최하위 + 임계치(예: 15점)
2. 보유 최하위 종목: 수익률/보유일/신뢰도 모두 하위권
3. 교체 후 예상 비용(수수료+세금) 감안해도 기대이익 양수
```

### 4.4 시장 레짐 필터

| 레짐 | 판단 기준 | 정책 조정 |
|---|---|---|
| 강세장 (VIX < 15) | 지수 20일선 위 + 거래량 증가 | 최대종목 +2, 현금버퍼 -5% |
| 보통장 | 기본 | 기본 설정 유지 |
| 약세장 (VIX > 25) | 지수 20일선 아래 + 거래량 감소 | 최대종목 -2, 현금버퍼 +10% |

### 4.5 KPI 기반 파라미터 자동 튜닝

2주 단위 측정:
- 평균 포지션 금액 / 최소 포지션 미달 차단 수
- 현금 비중 평균/최저
- 429 발생률 / 재시도 성공률
- 종목수 대비 샤프비율 기여

→ 측정 결과에 따라 게이트 파라미터 자동 조정 또는 운영자 알림

### 4.6 백테스트-실거래 동기화

현재 백테스트 엔진과 실거래 전략의 파라미터가 독립적으로 존재

| 수정 |
|---|
| 전략 파라미터를 공유 config로 통합 |
| 새 전략 적용 전 백테스트 통과 게이트 |
| 실거래 결과 vs 백테스트 예측 차이 리포트 |

---

## 5. 실행 우선순위 종합

```
Week 1:  Phase 1 (P0 버그 9개 + 보안)
         ├─ price_tasks 메서드명 수정
         ├─ maintenance_tasks is_active 제거
         ├─ abs(final_percent) 부호 보존
         ├─ PARTIAL_SELL 필터 통합
         ├─ DB 동기화 호출 추가
         ├─ is_executed 조기 마킹 수정
         ├─ avg_buy_price=0 보호
         ├─ Council API 인증
         └─ 런타임 ALTER 제거

Week 2-3: Phase 2 (운영 신뢰성)
         ├─ Alembic migration 체계
         ├─ .env.example 동기화
         ├─ 거래일 캘린더 외부화
         ├─ 시그널 상태머신
         ├─ 거래시간 정책 통합
         ├─ WebSocket 통합
         ├─ TLS 정책
         └─ Celery 이벤트 루프

Week 4-6: Phase 3 (구조 리팩터링)
         ├─ orchestrator.py 분해
         ├─ signal_tasks.py 분해
         ├─ 관측성 강화
         ├─ 멱등성 도입
         └─ 테스트 보강

Week 7+: Phase 4 (전략 고도화)
         ├─ 비선형 사이징
         ├─ 드리프트 리밸런싱
         ├─ 교체형 매수
         ├─ 시장 레짐 필터
         └─ KPI 자동 튜닝
```

---

## 6. 현재 config 파라미터 조정 권고

분석 문서의 원래 제안값과 현재 설정 비교:

| 파라미터 | 현재값 | 제안값 | 근거 |
|---|---|---|---|
| `min_position_pct` | 8.0% | 8.0% | ✅ 적정 |
| `min_cash_reserve_pct` | 5.0% | **15.0%** | 5%는 1종목 추가매수도 못할 수준. 방어력 확보 위해 15% 권장 |
| `max_positions` | 10 | **5~7** | 500만원대 포트폴리오에서 10종목은 소액 분산 과다. 자산 규모별 조정 |

---

## 7. 리스크 매트릭스

| 리스크 | 확률 | 영향 | 현재 대응 | Phase |
|---|---|---|---|---|
| 인증 없는 매매 조작 | 높음 | 🔴 치명 | 없음 | 1 |
| price_tasks 실패로 데이터 수집 중단 | 높음 | 🟡 높음 | 없음 | 1 |
| PARTIAL_SELL 누락으로 매도 미실행 | 중간 | 🔴 치명 | 없음 | 1 |
| DB-메모리 상태 불일치 (재시작 후) | 중간 | 🟡 높음 | 부분 대응 | 1 |
| 2027년 거래일 오판 | 확정 | 🟡 높음 | 없음 | 2 |
| 스키마 변경 추적 불가 | 높음 | 🟡 중간 | 없음 | 2 |
| 장애 원인 추적 불가 | 중간 | 🟡 중간 | 약함 | 3 |
| 소액 포지션 비효율 | 중간 | 🟢 낮음 | 게이트 존재 | 4 |

---

## 8. 기술 부채 추적

| 항목 | 현재 상태 | 목표 | 담당 Phase |
|---|---|---|---|
| 1000줄+ 파일 | 4개 | 0개 | Phase 3 |
| 테스트 커버리지 | smoke만 | 핵심 로직 70%+ | Phase 3 |
| Alembic migration | 0개 | baseline + 이후 변경분 | Phase 2 |
| 인증 누락 엔드포인트 | ~20개 | 0개 | Phase 1 |
| 중복 코드 (WebSocket) | 2곳 | 1곳 | Phase 2 |
