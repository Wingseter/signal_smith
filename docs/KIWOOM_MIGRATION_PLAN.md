# 키움증권 REST API 마이그레이션 계획

## 개요

현재 백엔드가 한국투자증권(KIS) API 엔드포인트를 사용하고 있으나,
실제 API 키는 키움증권 REST API용입니다.
키움증권 REST API로 코드를 변경해야 합니다.

## 변경 대상

### 1. 도메인 및 URL 변경

| 항목 | 현재 (한국투자증권) | 변경 (키움증권) |
|------|-------------------|----------------|
| 운영 서버 | `https://openapi.koreainvestment.com:9443` | `https://api.kiwoom.com` |
| 모의투자 서버 | `https://openapivts.koreainvestment.com:29443` | `https://mockapi.kiwoom.com` |
| WebSocket 운영 | `ws://ops.koreainvestment.com:21000` | `wss://api.kiwoom.com:10000` |
| WebSocket 모의 | `ws://ops.koreainvestment.com:31000` | `wss://mockapi.kiwoom.com:10000` |

### 2. 토큰 발급 API 변경

**현재 (한국투자증권):**
```python
POST /oauth2/tokenP
{
    "grant_type": "client_credentials",
    "appkey": "...",
    "appsecret": "..."
}
# 응답: { "access_token": "...", "expires_in": 86400 }
```

**변경 (키움증권):**
```python
POST /oauth2/token
{
    "grant_type": "client_credentials",
    "appkey": "...",
    "secretkey": "..."  # appsecret → secretkey
}
# 응답: { "token": "...", "expires_dt": "..." }
```

### 3. TR 코드 매핑

| 기능 | 한국투자증권 TR | 키움증권 TR |
|------|----------------|------------|
| 현재가 조회 | FHKST01010100 | ka10001 (주식기본정보요청) |
| 일봉 조회 | FHKST01010400 | ka10081 (주식일봉차트조회요청) |
| 분봉 조회 | FHKST01010500 | ka10080 (주식분봉차트조회요청) |
| 틱 조회 | - | ka10079 (주식틱차트조회요청) |
| 체결잔고 | TTTC8434R | kt00004 (체결잔고요청) |
| 계좌평가 | TTTC8434R | kt00017 (계좌평가잔고내역요청) |
| 현금매수 | TTTC0802U | kt10000 (주식 매수주문) |
| 현금매도 | TTTC0801U | kt10001 (주식 매도주문) |
| 정정주문 | TTTC0803U | kt10002 (주식 정정주문) |
| 취소주문 | TTTC0803U | kt10003 (주식 취소주문) |
| 예수금 조회 | - | kt00001 (예수금상세현황요청) |
| 미체결 조회 | - | ka10088 (미체결 분할주문 상세) |

### 4. 환경변수 변경

**현재 (.env):**
```env
KIS_APP_KEY=55cTqr36W15npixPwgF_avbrW9BIJlwRr6Rga88EgLE
KIS_APP_SECRET=7A-SQcd_OV-DM5kptJXx-in2Iouon5qN2fAoN8ud9lM
KIS_ACCOUNT_NUMBER=81175471
KIS_BASE_URL=https://openapivts.koreainvestment.com:29443
KIS_WS_URL=ws://ops.koreainvestment.com:31000
```

**변경 (.env):**
```env
KIWOOM_APP_KEY=55cTqr36W15npixPwgF_avbrW9BIJlwRr6Rga88EgLE
KIWOOM_SECRET_KEY=7A-SQcd_OV-DM5kptJXx-in2Iouon5qN2fAoN8ud9lM
KIWOOM_ACCOUNT_NUMBER=81175471
KIWOOM_BASE_URL=https://mockapi.kiwoom.com
KIWOOM_WS_URL=wss://mockapi.kiwoom.com:10000
KIWOOM_IS_MOCK=true
```

---

## 수정 대상 파일

### Phase 1: 설정 파일 (예상 소요: 30분)

| 파일 | 작업 |
|------|------|
| `backend/.env` | 환경변수 이름 및 URL 변경 |
| `backend/app/config.py` | 설정 변수명 변경 |

### Phase 2: REST 클라이언트 (예상 소요: 3-4시간)

| 파일 | 작업 |
|------|------|
| `backend/app/services/kiwoom/rest_client.py` | 전면 재작성 (688 LOC) |
| `backend/app/services/kiwoom/base.py` | 일부 수정 (enum, dataclass) |

### Phase 3: WebSocket 클라이언트 (예상 소요: 2시간)

| 파일 | 작업 |
|------|------|
| `backend/app/services/kiwoom/websocket_client.py` | 전면 재작성 (296 LOC) |

### Phase 4: 서비스 레이어 (예상 소요: 1시간)

| 파일 | 작업 |
|------|------|
| `backend/app/services/trading_service.py` | 응답 매핑 수정 |
| `backend/app/services/stock_service.py` | 응답 매핑 수정 |
| `backend/app/services/tasks.py` | import 및 호출 수정 |

---

## 키움증권 REST API 주요 엔드포인트

### 인증
```
POST /oauth2/token
```

### 시세 조회
```
POST /api/dostk/stkinfo      # 주식기본정보 (ka10001)
POST /api/dostk/chart        # 차트 데이터 (ka10079~ka10083)
```

### 주문
```
POST /api/dostk/order        # 주문 (kt10000~kt10003)
```

### 계좌
```
POST /api/dostk/acnt         # 계좌 정보 (kt00001~kt00017)
```

### WebSocket (실시간)
```
WSS /api/dostk/websocket     # 실시간 데이터
```

---

## 구현 순서

### 1단계: 인증 구현 (필수)
- [x] 토큰 발급 API 연동
- [x] 토큰 캐싱 (Redis)
- [x] 자동 갱신

### 2단계: 시세 조회 (필수)
- [ ] 현재가 조회 (ka10001)
- [ ] 일봉 조회 (ka10081)
- [ ] 분봉 조회 (ka10080)

### 3단계: 계좌 조회 (필수)
- [ ] 예수금 조회 (kt00001)
- [ ] 체결잔고 조회 (kt00004)
- [ ] 계좌평가 조회 (kt00017)

### 4단계: 주문 (핵심)
- [ ] 매수 주문 (kt10000)
- [ ] 매도 주문 (kt10001)
- [ ] 정정 주문 (kt10002)
- [ ] 취소 주문 (kt10003)

### 5단계: 실시간 (부가)
- [ ] WebSocket 연결
- [ ] 실시간 시세 구독
- [ ] 실시간 체결 구독

---

## 키움 REST API 요청 형식

### 공통 헤더
```python
headers = {
    "Content-Type": "application/json;charset=UTF-8",
    "authorization": f"Bearer {token}",
    "appkey": app_key,
    "secretkey": secret_key,
}
```

### 요청 본문 형식
```python
{
    "trnm": "TR명",  # 예: "ka10001"
    "acnt": "계좌번호",
    # ... TR별 파라미터
}
```

### 응답 형식
```python
{
    "return_code": 0,  # 0이면 성공
    "return_msg": "",
    "trnm": "TR명",
    "data": { ... }  # 실제 데이터
}
```

---

## 주의사항

1. **모의투자 제한**: 키움 모의투자는 KRX(코스피/코스닥)만 지원
2. **Rate Limit**: 초당 요청 수 제한 있음 (정확한 수치 확인 필요)
3. **토큰 만료**: `expires_dt` 필드로 만료일시 관리
4. **장시간 미접속**: 3개월 미접속 시 자동 해지 (재등록 필요)

---

## 테스트 체크리스트

- [ ] 토큰 발급 테스트
- [ ] 토큰 갱신 테스트
- [ ] 현재가 조회 테스트
- [ ] 일봉 데이터 조회 테스트
- [ ] 계좌 잔고 조회 테스트
- [ ] 보유 종목 조회 테스트
- [ ] 매수 주문 테스트 (모의투자)
- [ ] 매도 주문 테스트 (모의투자)
- [ ] 주문 취소 테스트 (모의투자)
- [ ] WebSocket 연결 테스트
- [ ] 실시간 시세 수신 테스트

---

## 참고 자료

- 키움증권 REST API 포털: https://openapi.kiwoom.com
- API 가이드: https://openapi.kiwoom.com/m/guide/apiguide
- Python 라이브러리: `pip install kiwoom-restful`
