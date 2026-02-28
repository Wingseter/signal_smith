# 주식 매수/매도 전략 및 실행 프로세스 심층 분석

작성일: 2026-02-28
대상 프로젝트: `signal_smith`

## 1) 분석 목적
이 문서는 프로젝트 내 "매수/매도 전략"과 "실행 과정"을 코드 기준으로 전수 정리하고, 현재 구조의 장점/단점/문제점과 우선순위 기반 개선 방향을 제시한다.

## 2) 분석 범위 및 근거 파일
다음 소스 기준으로 분석했다.

- `backend/app/services/news/trader.py`
- `backend/app/services/signals/triggers.py`
- `backend/app/services/signals/scanner.py`
- `backend/app/services/tasks/signal_tasks.py`
- `backend/app/services/council/orchestrator.py`
- `backend/app/services/council/models.py`
- `backend/app/services/council/trading_hours.py`
- `backend/app/services/trading_service.py`
- `backend/app/api/routes/council.py`
- `backend/app/services/backtesting/strategies.py`
- `backend/app/services/backtesting/engine.py`
- `backend/app/models/transaction.py`

## 3) 현재 매수 전략 전체

### 3.1 뉴스 기반 매수
- 진입 조건: `analysis.score >= council_threshold` (기본 6)
- 추가 필터: 종목코드 존재, 최소 신뢰도(`min_confidence`, 기본 0.6), 종목별 쿨다운, 일일 거래 제한
- 실행: AI Council `start_meeting(...)` 호출 후 BUY/HOLD/SELL 결정

근거:
- `backend/app/services/news/trader.py:150-178`
- `backend/app/services/news/trader.py:90-106`

### 3.2 퀀트 스캔 기반 매수
- 스캔 대상: 상위 500 종목
- 트리거 엔진: 42개 트리거 + 가중치 종합점수(1~100)
- 행동 결정: `>=80 strong_buy`, `>=65 buy`, `>=40 hold`, `>=25 sell`, else `strong_sell`
- 회의 소집 조건: `BUY/STRONG_BUY` 및 `composite_score >= 65`, 상위 3개

근거:
- `backend/app/services/tasks/signal_tasks.py:179-210`
- `backend/app/services/tasks/signal_tasks.py:687-776`
- `backend/app/services/signals/triggers.py:22-127`
- `backend/app/services/signals/scanner.py:155-223`

### 3.3 AI Council 내부 매수 의사결정
- 분석 라운드: GPT 퀀트 + Claude 펀더멘털 + 상호검토 + 합의
- 리스크 게이트: 최소 포지션, 최소 현금보유, 최대 종목 수
- 최종 액션: `_determine_action`에서 BUY/SELL/HOLD
- 자동 실행: 거래 가능 시간이면 즉시 주문, 아니면 QUEUED

근거:
- `backend/app/services/council/orchestrator.py:137-689`
- `backend/app/services/council/orchestrator.py:834-895`
- `backend/app/services/council/orchestrator.py:466-537`

## 4) 현재 매도 전략 전체

### 4.1 뉴스 기반 매도
- 조건: `analysis.score <= sell_threshold` (기본 4)
- 보유 종목일 때 `start_sell_meeting(...)` 실행

근거:
- `backend/app/services/news/trader.py:196-230`

### 4.2 퀀트 스캔 기반 매도
- 조건: `SELL/STRONG_SELL` 시그널 + 실제 보유 종목
- 쿨다운 적용 후 매도 회의 실행

근거:
- `backend/app/services/tasks/signal_tasks.py:629-680`

### 4.3 보유 종목 모니터 기반 매도
- 우선순위: GPT stop/target 가격 -> % 손절/익절 -> 기술점수 악화(<=3)
- 트리거되면 매도 회의 실행

근거:
- `backend/app/services/tasks/signal_tasks.py:223-279`
- `backend/app/services/tasks/signal_tasks.py:836-888`

### 4.4 리밸런싱/보유기한 기반 매도
- 장마감 후 재평가에서 score <= 3이면 매도 회의 에스컬레이션
- 보유 기한 만료 + 목표가 미달이면 매도 회의 실행

근거:
- `backend/app/services/tasks/signal_tasks.py:897-1085`

### 4.5 매도 회의 액션
- 손절 구간: 전량 SELL
- 익절 구간: PARTIAL_SELL(50%)
- 그 외: 점수 기반 SELL/PARTIAL_SELL

근거:
- `backend/app/services/council/orchestrator.py:1026-1185`

## 5) 실행 프로세스(엔드투엔드)

### 5.1 매수 프로세스
1. 뉴스 또는 퀀트 스캔이 후보를 생성한다.
2. AI Council이 기술/재무/상호검토/합의를 수행한다.
3. 포트폴리오 게이트(A/B/C)로 BUY를 재검증한다.
4. BUY 신호 생성 후 자동체결 또는 큐 적재 또는 PENDING 처리한다.
5. DB 시그널 저장, 이후 모니터링/큐처리 태스크가 후속 실행한다.

### 5.2 매도 프로세스
1. 뉴스/퀀트/가격트리거/리밸런싱/기한만료 중 하나가 매도 사유를 만든다.
2. 매도 회의에서 SELL 또는 PARTIAL_SELL 비율을 결정한다.
3. 자동체결 가능 시 주문 실행, 불가 시 큐로 이관한다.
4. 상태 업데이트 후 DB 저장 및 후속 큐체결 태스크가 처리한다.

## 6) 강점
- 다중 알파 소스 결합: 뉴스 + 42개 퀀트 트리거 + AI 합의 구조
- 리스크 게이트 존재: 최소 포지션/현금비율/최대 보유종목 수 제한
- 큐 기반 주문 재시도 구조: 거래시간 외 주문을 대기 처리
- 리밸런싱/보유기한 만료 로직으로 포지션 수명 관리 포함
- 백테스트 엔진이 별도로 존재하여 전략 실험 기반이 있음

## 7) 단점 및 핵심 문제점

아래는 실제 장애/오동작 가능성이 높은 항목부터 정리했다.

### P0 (즉시 수정 필요)

1. Enum 불일치로 예외 발생 가능
- 문제: `AnalystRole.FUNDAMENTAL` 사용하지만 Enum에는 `CLAUDE_FUNDAMENTAL`만 존재
- 영향: 타임아웃/예외 fallback 경로에서 런타임 오류 가능
- 근거:
  - `backend/app/services/council/models.py:21-26`
  - `backend/app/services/council/orchestrator.py:284,348,380`

2. 부호 손실로 SELL 판단 분기 무력화
- 문제: `final_percent = min(25, abs(final_percent))` 이후 `_determine_action`에서 `final_percent < 0` 분기 확인
- 영향: "AI가 음수 비중으로 매도 권고" 시나리오가 사실상 동작 불가
- 근거:
  - `backend/app/services/council/orchestrator.py:391`
  - `backend/app/services/council/orchestrator.py:871-873`

3. `PARTIAL_SELL` 생명주기 불일치
- 문제: 매도 회의는 `PARTIAL_SELL` 생성하지만, 큐 조회/API 조회는 `buy/sell`만 허용
- 영향: DB 큐 체결/대기 조회/운영 모니터에서 일부 매도 신호 누락 가능
- 근거:
  - 생성: `backend/app/services/council/orchestrator.py:1111,1114`
  - DB 큐 필터: `backend/app/services/tasks/signal_tasks.py:573`
  - API 필터: `backend/app/api/routes/council.py:169`

4. 시그널 상태 DB 동기화 누락
- 문제: approve/reject/execute 경로에서 DB 상태 업데이트 함수 미호출
- 영향: 재시작/분산 worker 환경에서 메모리 상태와 DB 상태 불일치
- 근거:
  - 승인/거부/체결: `backend/app/services/council/orchestrator.py:706-800`
  - DB 상태 업데이트 함수: `backend/app/services/council/orchestrator.py:1366-1386`

5. stop/target 트리거 시 조기 `is_executed=True`
- 문제: 실제 매도 체결 전인데 모니터 태스크가 실행완료로 마킹
- 영향: 매도 실패 시 재시도/재평가 누락 가능
- 근거:
  - `backend/app/services/tasks/signal_tasks.py:70-98`

6. 매도 회의 호출 파라미터 충돌(0으로 전달)
- 문제: `_trigger_sell_for_signal`이 `avg_buy_price=0` 전달, `start_sell_meeting`은 즉시 수익률 계산(0으로 나눗셈 가능)
- 영향: stop-loss/target 트리거 경로에서 매도 회의 실패 가능
- 근거:
  - 호출: `backend/app/services/tasks/signal_tasks.py:799-806`
  - 계산: `backend/app/services/council/orchestrator.py:1045`

### P1 (단기 개선)

7. 거래시간 정책 불일치
- 문제: 태스크 게이트(`is_market_hours`)는 정규장만 허용, 주문 가능 판단(`can_execute_order`)은 장전/장후 허용
- 영향: 시간외 체결 가능한 주문 기회가 스케줄 태스크에서 스킵됨
- 근거:
  - `backend/app/services/tasks/_common.py:22-27`
  - `backend/app/services/council/trading_hours.py:147-153`

8. 조기 return 경로의 감사 추적 약함
- 문제: 잔고 부족/신뢰도 미달 경로에서 회의/시그널 persist 이전 return
- 영향: 운영 관점에서 "왜 버려졌는지" 사후 감사 어려움
- 근거:
  - `backend/app/services/council/orchestrator.py:574-580`
  - `backend/app/services/council/orchestrator.py:621-624`

9. 매도 수량 0 검증 부재
- 문제: `PARTIAL_SELL` 계산 시 소수 보유 수량에서 0주 가능
- 영향: 주문 실패/큐 적체 가능
- 근거:
  - `backend/app/services/council/orchestrator.py:1116`

### P2 (중기 개선)

10. 전략/실행/상태 모델의 단일 표준 부족
- 문제: 액션/상태가 메모리, DB, 태스크 필터에서 다르게 해석됨
- 영향: 기능 확장 시 회귀 위험 증가

## 8) 개선 방향 (우선순위 로드맵)

### 8.1 P0 핫픽스 (1주 내)
1. Enum 통일
- `AnalystRole.FUNDAMENTAL` -> `AnalystRole.CLAUDE_FUNDAMENTAL` 전면 교체

2. 액션 체계 통일
- `PARTIAL_SELL`를 공식 액션으로 모델/DB/API/큐 필터에 반영
- 또는 `SELL` + `sell_percent` 메타 구조로 단순화

3. 상태 동기화 강제
- approve/reject/execute/queue enqueue 시점마다 `_update_signal_status_in_db` 호출
- DB를 source of truth로 고정

4. stop/target 체결 완료 후 상태 전이
- 매도 주문 제출 성공 전까지 `is_executed` 변경 금지

5. `avg_buy_price=0` 보호
- sell meeting 내부에서 0이면 실제 보유 조회 fallback
- 0 분모 방지 및 필수 값 검증 추가

6. final_percent 부호 유지
- `abs()` 제거 또는 buy/sell 별 변수 분리

### 8.2 P1 구조 개선 (2~4주)
1. 상태머신 명시화
- 상태 전이를 enum/state diagram으로 강제: `pending -> approved -> queued -> auto_executed|cancelled`

2. 주문 정책 분리
- 시장가 대체 지정가 정책(`place_order`)을 전략별로 선택 가능하게 분리

3. 거래시간 정책 일원화
- 태스크 게이트와 주문 가능 세션 판정을 동일 정책 모듈로 통합

4. 관측성 강화
- 모든 탈락/차단 이유를 DB event log에 기록

### 8.3 P2 전략 연구 (지속)
1. 매수/매도 정책에 시장 레짐 필터(변동성/추세) 추가
2. `PARTIAL_SELL` 다단계 청산(예: 30/30/40) 실험
3. 백테스트 엔진과 실거래 정책의 파라미터 동기화

## 9) MCP 활용 연구 방식 권장안

다음 순서로 MCP를 사용하면 "코드 분석 -> 가설 -> 검증" 루프를 빠르게 반복할 수 있다.

1. Serena MCP (정적 코드 연구)
- 목표: 전략/실행 경로를 심볼 단위로 완전 추적
- 방법:
  - `find_symbol`로 핵심 함수 트리 추출
  - `find_referencing_symbols`로 상태 전이 호출지 수집
  - `search_for_pattern`으로 액션/상태 문자열(`buy/sell/partial_sell/queued`) 전수 검사

2. Pytest MCP (결함 재현/회귀 방지)
- 목표: 위 P0 이슈를 테스트로 고정
- 권장 테스트:
  - Enum fallback 경로 예외 테스트
  - partial_sell이 큐/조회/API에서 누락되지 않는지 통합 테스트
  - stop/target 이벤트 시 실제 주문 성공 전 `is_executed` 미변경 테스트

3. Tavily MCP (외부 기준 리서치)
- 목표: 거래세션/주문정책/리스크관리의 업계 기준 비교
- 리서치 주제:
  - 국내 증권사 시간외 체결 정책
  - 자동매매 상태머신/주문 재시도 베스트프랙티스
  - 포트폴리오 게이트(현금비율/최대종목수) 표준 범위

4. Playwright/Chrome DevTools MCP (운영 화면 검증)
- 목표: `/council/signals/pending` 등 운영 UI/API에서 상태 누락 여부 확인
- 포인트: partial_sell/queued/approved 케이스가 정상 노출되는지 검증

## 10) 결론
현재 시스템은 "뉴스 + 퀀트 + AI 합의 + 리스크 게이트"라는 강한 구조를 이미 갖췄다. 다만 실제 운영 안정성을 해치는 핵심 결함(P0)이 존재한다. 먼저 상태/액션 표준화와 DB 동기화, stop/target 실행 상태 전이 문제를 수정하면, 이후 전략 고도화(P1/P2)의 성과가 안정적으로 누적될 구조가 된다.
