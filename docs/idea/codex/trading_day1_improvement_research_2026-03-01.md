# Day1 결과 기반 문제 해결 아이디어 연구 (2026-03-01)

## 1) 요약 결론

`TRADING_RESULT_DAY1.md`의 성과(+2.7%)는 출발이 좋지만, 현재 구조는 "수익률보다 운영 리스크"가 더 큰 상태다.
핵심은 아래 3가지다.

1. **자본 효율 저하**: 소액 포지션이 늘어나 수수료/세금 대비 기대효용이 낮음
2. **리스크 관리 부재**: 현금 버퍼/드리프트 리밸런싱 규칙이 없어 기회 대응력과 방어력이 약함
3. **인프라 안정성 부족**: 뉴스/시세 API 429 시 graceful degradation이 없어 신호 품질이 흔들림

따라서 "종목 선택 개선"보다 먼저, **체결 전 리스크 게이트 + API 복원력**을 우선 도입하는 것이 기대효과가 큼.

## 2) 현재 구조에서의 원인 진단

### A. 소액 포지션 발생 원인
- `orchestrator.py`에서 `suggested_amount = available_amount * final_percent`로 산출
- `final_percent`는 상한(25%)만 존재하고 **최소 포지션 하한 없음**
- `available_amount`는 각 트리거 시점 잔고 기반이므로 후반부로 갈수록 작아져 **2~8만원 포지션이 자연 발생**

관련 코드:
- `backend/app/services/council/orchestrator.py`의 `final_percent` clamp 및 `suggested_amount` 계산 구간
- `backend/app/services/news/trader.py`, `backend/app/services/tasks/signal_tasks.py`의 `available_amount` 전달 구간

### B. 현금 고갈 원인
- 신규 매수 전 **최소 현금 비중 검증 규칙 부재**
- "종목당 상한"은 있으나 "포트폴리오 전체 현금 하한"이 없음

### C. 단일 종목 비중 초과(상승 후 25% 초과)
- 현재 상한은 "매수 시점"에만 적용됨
- 가격 상승으로 발생하는 **사후 드리프트(초과 비중)**를 처리하는 리밸런싱 밴드가 없음

### D. 429 장애 원인
- `rest_client.py` 공통 `_request`에서 토큰 재발급 처리만 있고
- **429 전용 재시도(Backoff/Jitter/Retry-After) 로직이 없음**
- 다수 종목 연속 조회 태스크가 burst 트래픽을 만들어 rate limit을 유발

## 3) 기존 아이디어 대비 강화된 개선안

## P0 (즉시 적용, 저난이도/고효과)

### 3.1 체결 전 "3중 게이트" 도입

1. **최소 포지션 금액 게이트**
- 규칙: `suggested_amount >= max(총자산*8%, 최소주문금액)`
- 조건 미달 시: `HOLD` 전환 (매수 생략)

2. **현금 버퍼 게이트**
- 규칙: 체결 후 현금비중 `< 15%` 예상이면 매수 차단

3. **포지션 수 게이트**
- 500만원 구간: 최대 5종목
- 5종목 초과 신규 매수는 원칙적으로 차단

효과:
- 소액 포지션 제거
- "좋은 기회에 쓸 탄약" 확보
- 포트폴리오 복잡도 감소

### 3.2 드리프트 리밸런싱 밴드

- 현재: 매수 시 25%만 체크
- 개선: 보유 중에는 `20~25%` 밴드 운영

규칙 예시:
- `> 25%`: 부분매도 후보 등록
- `20~25%`: 유지
- `< 20%`: 신규매수 우선순위 대상

핵심은 "즉시 강제 매도"가 아니라, **다음 매수 이벤트 시 자동 교정**하는 방식으로 거래비용을 줄이는 것.

### 3.3 429 복원력 표준화

`rest_client._request`에 다음 순서 적용:

1. 응답 429 또는 본문 rate limit 코드 감지
2. `Retry-After` 헤더 우선 사용
3. 없으면 exponential backoff + jitter
4. 최대 재시도 횟수 초과 시 실패 반환

추가로 태스크 레벨에서:
- 종목 조회 간 base delay
- 동시성 상한(semaphore) 적용

## P1 (중기 적용, 성과 개선)

### 3.4 신호 강도 기반 비선형 사이징

현재는 `%`를 거의 선형으로 해석해 소액/과대가 섞인다.
개선은 계단형 사이징:

- 신뢰도 0.60~0.69: 8%
- 0.70~0.79: 12%
- 0.80~0.89: 16%
- 0.90+: 20%

그리고 다음 보정 추가:
- 변동성 높은 종목: 한 단계 하향
- 기존 보유 종목과 상관도 높은 종목: 한 단계 하향

### 3.5 "교체형 매수" 정식화

보유 종목이 최대치면 신규 매수 대신 교체를 검토:

교체 트리거:
1. 신규 신호 점수 > 보유 최하위 + 임계치
2. 보유 최하위 종목 수익률/보유일/신뢰도 모두 하위권
3. 교체 후 예상 비용(수수료+세금+슬리피지) 감안해도 기대 이익이 양수

이 규칙이 있어야 "현금 부족 = 기회 상실" 문제를 완화할 수 있다.

## P2 (고도화)

### 3.6 데이터 품질 게이트 (AI Council 안정성)

- Gemini/Claude/GPT 중 핵심 입력 소스 실패 시
  - 즉시 매수 금지 또는
  - 신뢰도 강등(예: -0.15) 후 재평가
- "분석 실패 상태에서 체결"을 원천 차단

### 3.7 성과 측정 체계 (2주 단위)

필수 KPI:
- 평균 포지션 금액
- 최소 포지션 미달로 차단된 신호 수
- 현금 비중 평균/최저
- 429 발생률, 재시도 성공률
- 종목수 대비 샤프/손익 기여

## 4) 실행 순서 제안 (현실적인 적용안)

1주차:
1. P0-3중 게이트
2. 429 재시도 + 지터
3. 모니터링 지표 로깅

2주차:
1. 드리프트 밴드 리밸런싱
2. 교체형 매수 룰
3. 신호강도 기반 비선형 사이징

3주차:
1. 데이터 품질 게이트
2. KPI 기반 파라미터 튜닝

## 5) 근거 자료 (Research Notes)

아래 자료를 참고해 규칙 우선순위를 정리했다.

1. 분산투자 기본 원칙 (미국 SEC 투자자 교육):  
https://www.investor.gov/introduction-investing/investing-basics/glossary/diversification

2. 거래비용/수수료의 장기 성과 잠식 (미국 SEC 투자자 교육):  
https://www.investor.gov/additional-resources/information/youth/teachers-classroom-resources/what-compounding

3. 과도한 매매(Churning) 판단 지표 예시, turnover/cost-to-equity 기준 (FINRA):  
https://www.finra.org/investors/insights/six-signs-your-broker-may-be-churning-your-account

4. 변동성 관리(Volatility managed portfolios) 연구 (NBER, Moreira & Muir):  
https://www.nber.org/papers/w22208

5. HTTP 429/Retry-After 표준 (RFC 6585):  
https://www.rfc-editor.org/rfc/rfc6585

6. Backoff + Jitter 권장 패턴 (AWS Architecture Blog):  
https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

## 6) 바로 코드화할 때의 체크리스트

- `orchestrator.py`: 최소 포지션/현금버퍼/최대종목수 게이트 추가
- `signal_tasks.py`, `news/trader.py`: available_amount 계산 시 "현금버퍼 차감 후 주문가능액" 반영
- `rest_client.py`: 429 retry policy + jitter + max_attempt + observability(log fields)
- `settings`: `min_position_pct`, `min_cash_reserve_pct`, `max_positions`, `retry_backoff_base_ms` 추가

---

핵심 포인트: Day1의 문제는 "종목 선정 정확도"보다 "포트폴리오 운영 규율"의 문제다.  
P0만 적용해도 소액 포지션/현금 고갈/429 실매매 리스크를 동시에 크게 줄일 수 있다.
