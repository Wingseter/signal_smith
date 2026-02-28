# Signal Smith 아키텍처 분석 및 시스템 고도화 제안 (V2)

본 문서는 `Signal Smith` 프로젝트의 전체 코드베이스(Backend/Frontend) 및 기존 기획 문서(`TRADING_RESULT_DAY1.md`, `IMPROVEMENT_PLAN_V1.md`, `gemini.md`)를 종합적으로 분석하고, 최신 LLM 알고리즘 트레이딩 트렌드(2025~2026년도)를 반영하여 차세대 시스템으로 나아가기 위한 아키텍처 개선 및 전략 아이디어를 제안합니다.

---

## 1. 현재 시스템 아키텍처 진단

### 1-1. Backend Architecture (FastAPI 기반)
현재 백엔드는 **AI Council(투자 위원회)** 패턴을 매우 성공적으로 구현하고 있습니다.
*   **Orchestrator (`services/council/orchestrator.py`)**: 시스템의 심장부로, 실시간 차트(키움증권)와 재무 데이터(DART)를 수집한 후 다중 AI 에이전트(Gemini, GPT, Claude)에게 분석을 위임하고 만장일치 및 논조를 바탕으로 매매를 결정합니다.
*   **Data Sources**: 키움증권 Open API(시세, 주문)와 DART(재무제표)를 조합하여 하이브리드(기술적+기본적) 분석의 토대를 마련해 두었습니다.
*   **Risk Management (초기형)**: `IMPROVEMENT_PLAN_V1`에 따라 3중 게이트(부분 익절, 최대 종목 수 제한, 현금 비중 유지, 최소 포지션 크기)가 도입되거나 구조가 잡혀있습니다.

**[진단 포인트]**
*   **강점**: 다중 LLM을 이용한 "크로스 체크(상호 검토)" 구조는 단일 모델의 환각(Hallucination)을 막는 훌륭한 설계입니다. 
*   **보완점**: 백엔드에서 키움 API 호출의 Rate Limit(429) 처리나 여러 종목을 병렬 모니터링할 때의 이벤트 루프(Event Loop) 블로킹 문제, 그리고 AI 분석 에이전트들의 독립적인 Task Queue(Celery/Redis 등) 처리가 부족해 보입니다.

### 1-2. Frontend Architecture (React/Vite 기반)
*   React + TypeScript 스택을 사용하여 관리자 대시보드(Dashboard) 역할을 수행하도록 구성되었습니다.
*   컴포넌트 단위(`components/`) 구분과 상태 관리(`store/`)가 나뉘어 있어 확장성이 좋습니다.

**[진단 포인트]**
*   현재는 '매매 결과 디스플레이'와 '수동 승인(Pending)'에 머물러 있을 가능성이 높습니다. AI 모델들이 회의하는 과정(Thought Process)을 시각적으로 어떻게 보여줄 것인지(실시간 소켓 연동 등)가 UX의 핵심이 될 것입니다.

---

## 2. 최신 LLM 트레이딩 트렌드(2026) 기반의 고도화 방향 (Better Ideas)

웹 서치 및 MCP 도구(Tavily 등)를 통해 조사한 최근 LLM 트레이딩 및 포트폴리오 최적화 트렌드를 적용한 개선안입니다.

### 아이디어 1: LLM Agent와 강화학습(RL)의 결합 (RLHF for Trading)
최근 연구에 따르면 LLM 단독 판단보다는 **RL(Reinforcement Learning) 에이전트를 행동 주체로 두고, LLM을 "고급 피쳐(Feature) 생성기" 및 "시장 감정 분석기"로 사용하는 하이브리드 접근**이 대세입니다.
*   **방향**: 현재는 AI Council이 직접 "사라/팔아라"를 결정합니다. 이를 한 단계 업그레이드하여, AI Council은 [시장 센티먼트 점수, 펀더멘털 스코어, 기술적 지표 해석]만을 벡터 형태로 출력하고, **실제 매매 비중 결정은 PPO(Proximal Policy Optimization) 같은 강화학습 모델이 담당**하게 합니다.
*   **효과**: 켈리 방정식(Kelly Criterion)을 수동으로 계산할 필요 없이, 강화학습 모델이 누적된 손익 데이터를 바탕으로 최적의 투자 비중을 스스로 학습합니다.

### 아이디어 2: 자율형 자가 수정 에이전트 (Self-Reflective Trading Agents)
현재 AI Council은 주어진 한 번의 회의(Round 1~3)로 결론을 내리고 끝냅니다.
*   **방향**: 매매가 종료(익절/손절)된 후, **"사후 회고(Post-mortem) 회의"**를 시스템화합니다. 
*   **구현**: `TRADING_RESULT` 데이터를 읽는 별도의 **Reviewer Agent**를 둡니다. "지난주 삼성전자를 21만원에 샀던 GPT의 판단 근거는 A였으나, 실제 시장은 B로 움직여 5% 익절로 끝났다. 다음엔 A 지표의 가중치를 낮춰라" 형태의 피드백 텍스트를 생성하고, 이를 AI Council의 다음번 프롬프트 Context(System Prompt 메모리)에 동적으로 주입(RAG 형식)합니다.

### 아이디어 3: 다중 소스 기반의 '내러티브(Narrative) 필터링'
단순 뉴스와 차트뿐만 아니라 비정형 데이터의 폭을 넓힙니다.
*   **방향**: 실시간 텔레그램 속보 채널, 증권사 리포트 PDF 파싱, Reddit/StockTwits 등의 소셜 미디어 크롤링 데이터를 추가 파이프라인으로 구축합니다.
*   **구현**: 너무 많은 텍스트는 토큰 초과 및 지연을 유발하므로, 가벼운 SLM(Small Language Model)이나 임베딩 모델을 앞단에 두어 "진짜 영향을 줄 만한 트리거"인지 1차 필터링한 후, 통과한 정보만 메인 AI Council에 회부합니다.

### 아이디어 4: 포트폴리오 차원의 헷징 (Macro & ESG)
V1 계획의 **'매크로 환경 기반 유동적 현금 비중'**의 연장선입니다.
*   **방향**: 상승장/보합/하락장에 따른 현금 조절뿐만 아니라, **인버스(Inverse) ETF나 달러/금 관련 자산 편입**을 AI가 제안할 수 있도록 종목 풀을 확장합니다. 하락장 패턴 인식 시 개별 주식을 전량 매도하고 KODEX 인버스로 스위칭하는 기능을 오케스트레이터에 추가합니다.

---

## 3. 백엔드 아키텍처 리팩토링 제안 (System Scalability)

위의 고급 로직들을 소화하기 위해 백엔드 구조를 다음과 같이 강화해야 합니다.

1.  **비동기 큐 (Message Broker 도입)**:
    *   현재 Python `asyncio.wait_for`로 타임아웃을 관리하지만, 종목 수가 늘어나면 한계가 옵니다.
    *   **Celery + Redis** 또는 **RabbitMQ** 아키텍처를 도입하여, `News_Analysis_Task`, `Quant_Analysis_Task` 등을 분산 처리합니다. AI API 지연 시에도 메인 시스템(키움 API 모니터링 등)이 블로킹되지 않게 합니다.
2.  **API Rate Limiter 중앙 집중화 (Token Bucket)**:
    *   `rest_client.py` 내부의 단순 `asyncio.sleep` 대신, Redis 기반의 전역 Rate Limiter를 두어 프론트엔드 요청, 스케줄러 요청, 백그라운드 태스크 요청이 모두 키움증권 조회 횟수(초당 5회 등)를 공유하고 초과 시 큐 시스템으로 넘어가게 설계합니다.
3.  **LLM Routing & Fallback (LiteLLM 도입 검토)**:
    *   현재 GPT, Claude, Gemini를 직접 호출하는 코드가 하드코딩 되어 있을 수 있습니다. `LiteLLM`과 같은 프록시 라이브러리를 도입하면, GPT-4가 Rate Limit에 걸릴 경우 자동으로 Claude 3.5 Sonnet으로 Fallback 하는 로직을 1줄의 코드로 구현할 수 있어 `CLIProxiAPI` 이슈를 완벽히 해결할 수 있습니다.

---

## 4. 최종 종합 및 다음 단계 (Next Actions)

기존 `IMPROVEMENT_PLAN_V1.md`의 Phase 1~3가 "기본 트레이딩 규율과 안정화"에 초점을 맞추었다면, 본 문서는 **"AI의 지능적 진화와 시스템 확장성"**에 초점을 두었습니다.

**[실행 권장 로드맵]**
1.  **우선 순위 1**: `IMPROVEMENT_PLAN_V1`의 3중 게이트 적용 및 버그 수정 완료하기 (현재 작업 중)
2.  **우선 순위 2**: LiteLLM 도입으로 다중 LLM API 관리 일원화 및 Rate Limit 방어막(Fallback) 치기
3.  **우선 순위 3**: RAG 기반 메모리 시스템(벡터 DB 구축)을 구현하여, 지난 주/지난 달의 매매 실수와 성공 요인을 AI Council이 매 회의 전 "참고 문헌"으로 읽게 만들기 (Self-Reflective Agent 도입)
4.  **우선 순위 4**: 단순 주식 매매를 넘어선 포트폴리오 차원의 헷징(인버스, 국채 ETF 등) 유니버스 확장

이러한 로드맵을 통해 Signal Smith는 단순한 '주식 추천 봇'을 넘어, 스스로 학습하고 시장을 방어하는 완벽한 퀀트 로보어드바이저 펀드로 성장할 수 있을 것입니다.
