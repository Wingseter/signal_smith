"""
DART API 클라이언트

금융감독원 전자공시시스템(DART) API를 통해 재무제표 데이터를 조회합니다.
- 기업 개황 조회
- 재무제표 조회 (PER, PBR, ROE 등)
- 주요 재무비율 계산

API 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import zipfile
import io
import xml.etree.ElementTree as ET
import json

import httpx

from app.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass
class CompanyInfo:
    """기업 기본 정보"""
    corp_code: str          # DART 고유번호
    corp_name: str          # 회사명
    stock_code: str         # 종목코드
    corp_cls: str           # 법인구분 (Y: 유가, K: 코스닥, N: 코넥스, E: 기타)
    industry: str           # 업종
    established_date: str   # 설립일
    ceo_name: str           # 대표이사
    homepage: str           # 홈페이지
    employees: int          # 직원수


@dataclass
class FinancialData:
    """재무제표 데이터"""
    corp_code: str
    corp_name: str
    stock_code: str
    fiscal_year: str        # 사업연도

    # 손익계산서
    revenue: Optional[int] = None              # 매출액
    operating_income: Optional[int] = None     # 영업이익
    net_income: Optional[int] = None           # 당기순이익

    # 재무상태표
    total_assets: Optional[int] = None         # 자산총계
    total_liabilities: Optional[int] = None    # 부채총계
    total_equity: Optional[int] = None         # 자본총계

    # 주요 재무비율
    per: Optional[float] = None                # PER (주가수익비율)
    pbr: Optional[float] = None                # PBR (주가순자산비율)
    roe: Optional[float] = None                # ROE (자기자본이익률)
    debt_ratio: Optional[float] = None         # 부채비율
    operating_margin: Optional[float] = None   # 영업이익률

    # 성장성
    revenue_growth: Optional[float] = None     # 매출 성장률 (전년 대비)
    income_growth: Optional[float] = None      # 순이익 성장률 (전년 대비)

    def to_prompt_text(self) -> str:
        """Claude 프롬프트용 텍스트 생성"""
        def fmt_num(val: Optional[int]) -> str:
            if val is None:
                return "N/A"
            if abs(val) >= 1_000_000_000_000:  # 조
                return f"{val / 1_000_000_000_000:.1f}조원"
            elif abs(val) >= 100_000_000:  # 억
                return f"{val / 100_000_000:.0f}억원"
            else:
                return f"{val:,}원"

        def fmt_pct(val: Optional[float]) -> str:
            if val is None:
                return "N/A"
            return f"{val:.1f}%"

        def fmt_ratio(val: Optional[float]) -> str:
            if val is None:
                return "N/A"
            return f"{val:.2f}"

        lines = [
            f"📊 {self.corp_name} ({self.stock_code}) - {self.fiscal_year} 재무제표",
            "",
            "【손익계산서】",
            f"- 매출액: {fmt_num(self.revenue)}",
            f"- 영업이익: {fmt_num(self.operating_income)}",
            f"- 당기순이익: {fmt_num(self.net_income)}",
            "",
            "【재무상태표】",
            f"- 자산총계: {fmt_num(self.total_assets)}",
            f"- 부채총계: {fmt_num(self.total_liabilities)}",
            f"- 자본총계: {fmt_num(self.total_equity)}",
            "",
            "【주요 재무비율】",
            f"- PER: {fmt_ratio(self.per)}배",
            f"- PBR: {fmt_ratio(self.pbr)}배",
            f"- ROE: {fmt_pct(self.roe)}",
            f"- 부채비율: {fmt_pct(self.debt_ratio)}",
            f"- 영업이익률: {fmt_pct(self.operating_margin)}",
            "",
            "【성장성】",
            f"- 매출 성장률: {fmt_pct(self.revenue_growth)}",
            f"- 순이익 성장률: {fmt_pct(self.income_growth)}",
        ]
        return "\n".join(lines)


class DartClient:
    """DART API 클라이언트"""

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        self._api_key = settings.dart_api_key
        self._corp_code_cache: Dict[str, str] = {}  # 종목코드 -> DART 고유번호 캐시

    async def _request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """API 요청"""
        if not self._api_key:
            raise ValueError("DART_API_KEY가 설정되지 않았습니다")

        url = f"{self.BASE_URL}/{endpoint}"
        request_params = {"crtfc_key": self._api_key}
        if params:
            request_params.update(params)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=request_params)
            response.raise_for_status()

            # JSON 응답
            if "json" in response.headers.get("content-type", ""):
                data = response.json()
                if data.get("status") != "000":
                    logger.warning(f"DART API 오류: {data.get('message')}")
                return data

            # XML 응답 (고유번호 조회 등)
            return {"content": response.content}

    async def _load_corp_codes(self) -> bool:
        """DART 기업 고유번호 전체 목록 로드 (ZIP 파일)"""
        try:
            # API 키 확인
            if not self._api_key:
                logger.error("DART_API_KEY가 설정되지 않았습니다")
                return False

            # Redis 캐시 확인
            redis = await get_redis()
            cache_key = "dart:corp_codes"
            cached = await redis.get(cache_key)

            if cached:
                self._corp_code_cache = json.loads(cached)
                logger.info(f"DART 고유번호 캐시 로드: {len(self._corp_code_cache)}개 기업")
                return True

            # DART API에서 ZIP 파일 다운로드
            url = f"{self.BASE_URL}/corpCode.xml"
            params = {"crtfc_key": self._api_key}

            logger.info(f"DART 고유번호 목록 다운로드 시작...")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                # 응답이 JSON 에러인지 확인 (DART는 에러시 JSON 반환)
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or response.content[:1] == b'{':
                    try:
                        error_data = response.json()
                        logger.error(f"DART API 에러: {error_data.get('message', error_data)}")
                        return False
                    except json.JSONDecodeError:
                        pass

                # XML 에러 응답 확인 (시스템 점검 등)
                if response.content[:5] == b'<?xml':
                    try:
                        error_root = ET.fromstring(response.content)
                        status = error_root.findtext('status', '')
                        message = error_root.findtext('message', '')
                        logger.error(f"DART API XML 에러 (status={status}): {message}")
                    except ET.ParseError:
                        logger.error(f"DART 응답 XML 파싱 실패: {response.content[:200]}")
                    return False

                # ZIP 파일인지 확인 (ZIP 매직 넘버: PK)
                if response.content[:2] != b'PK':
                    logger.error(f"DART 응답이 ZIP 파일이 아닙니다. 처음 100바이트: {response.content[:100]}")
                    return False

                # ZIP 파일 처리
                zip_buffer = io.BytesIO(response.content)
                with zipfile.ZipFile(zip_buffer, 'r') as zip_file:
                    # CORPCODE.xml 파일 읽기
                    xml_content = zip_file.read('CORPCODE.xml')

                    # XML 파싱
                    root = ET.fromstring(xml_content)
                    for corp in root.findall('.//list'):
                        corp_code = corp.findtext('corp_code', '')
                        stock_code = corp.findtext('stock_code', '')

                        # 상장기업만 (종목코드가 있는 경우)
                        if stock_code and stock_code.strip():
                            self._corp_code_cache[stock_code.strip()] = corp_code

                logger.info(f"DART 고유번호 로드 완료: {len(self._corp_code_cache)}개 상장기업")

                # Redis 캐시 저장 (7일 — 상장기업 목록은 자주 변하지 않음)
                await redis.set(cache_key, json.dumps(self._corp_code_cache), ex=604800)

                return True

        except zipfile.BadZipFile as e:
            logger.error(f"DART ZIP 파일 파싱 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"DART 고유번호 목록 로드 실패: {e}")
            return False

    async def get_corp_code(self, stock_code: str) -> Optional[str]:
        """종목코드로 DART 고유번호 조회"""
        # 캐시 확인
        if stock_code in self._corp_code_cache:
            return self._corp_code_cache[stock_code]

        # 캐시가 비어있으면 전체 목록 로드 (최대 2회 시도)
        if not self._corp_code_cache:
            for attempt in range(2):
                success = await self._load_corp_codes()
                if success:
                    break
                if attempt == 0:
                    logger.info("DART 기업코드 로드 재시도 (3초 후)...")
                    await asyncio.sleep(3)

        return self._corp_code_cache.get(stock_code)

    async def get_company_info(self, corp_code: str) -> Optional[CompanyInfo]:
        """기업 개황 조회"""
        try:
            data = await self._request("company.json", {"corp_code": corp_code})

            if data.get("status") != "000":
                return None

            return CompanyInfo(
                corp_code=corp_code,
                corp_name=data.get("corp_name", ""),
                stock_code=data.get("stock_code", ""),
                corp_cls=data.get("corp_cls", ""),
                industry=data.get("induty_code", ""),
                established_date=data.get("est_dt", ""),
                ceo_name=data.get("ceo_nm", ""),
                homepage=data.get("hm_url", ""),
                employees=int(data.get("emp_cnt", 0) or 0),
            )

        except Exception as e:
            logger.error(f"기업 개황 조회 실패: {e}")
            return None

    async def get_financial_statements(
        self,
        corp_code: str,
        year: str = None,
        report_code: str = None
    ) -> Optional[FinancialData]:
        """재무제표 조회

        보고서 코드:
        - 11011: 사업보고서 (연간)
        - 11012: 반기보고서
        - 11013: 1분기보고서
        - 11014: 3분기보고서
        """
        current_year = datetime.now().year
        current_month = datetime.now().month

        # 보고서 유형 순서 결정 (가장 최신 데이터부터)
        # 1월: 전년도 3분기 → 반기 → 전전년도 사업보고서
        # 4월 이후: 올해 1분기 → 전년도 사업보고서 등
        report_attempts = []

        if current_month <= 3:
            # 1~3월: 전년도 3분기 → 반기 → 1분기 → 전전년도 사업보고서
            report_attempts = [
                (str(current_year - 1), "11014"),  # 전년도 3분기
                (str(current_year - 1), "11012"),  # 전년도 반기
                (str(current_year - 1), "11013"),  # 전년도 1분기
                (str(current_year - 2), "11011"),  # 전전년도 사업보고서
            ]
        elif current_month <= 5:
            # 4~5월: 전년도 사업보고서 → 전년도 3분기
            report_attempts = [
                (str(current_year - 1), "11011"),  # 전년도 사업보고서
                (str(current_year - 1), "11014"),  # 전년도 3분기
                (str(current_year - 1), "11012"),  # 전년도 반기
            ]
        elif current_month <= 8:
            # 6~8월: 올해 1분기 → 전년도 사업보고서
            report_attempts = [
                (str(current_year), "11013"),      # 올해 1분기
                (str(current_year - 1), "11011"),  # 전년도 사업보고서
                (str(current_year - 1), "11014"),  # 전년도 3분기
            ]
        elif current_month <= 11:
            # 9~11월: 올해 반기 → 1분기 → 전년도 사업보고서
            report_attempts = [
                (str(current_year), "11012"),      # 올해 반기
                (str(current_year), "11013"),      # 올해 1분기
                (str(current_year - 1), "11011"),  # 전년도 사업보고서
            ]
        else:
            # 12월: 올해 3분기 → 반기 → 전년도 사업보고서
            report_attempts = [
                (str(current_year), "11014"),      # 올해 3분기
                (str(current_year), "11012"),      # 올해 반기
                (str(current_year - 1), "11011"),  # 전년도 사업보고서
            ]

        # 특정 연도/보고서가 지정된 경우 우선 시도
        if year and report_code:
            report_attempts.insert(0, (year, report_code))

        for try_year, try_report_code in report_attempts:
            try:
                # 단일회사 주요계정 조회 API
                data = await self._request("fnlttSinglAcnt.json", {
                    "corp_code": corp_code,
                    "bsns_year": try_year,
                    "reprt_code": try_report_code,
                })

                if data.get("status") == "000" and data.get("list"):
                    logger.info(f"DART 재무제표 조회 성공: {try_year}년 보고서({try_report_code})")
                    break
            except Exception as e:
                logger.debug(f"DART 재무제표 시도 실패 ({try_year}, {try_report_code}): {e}")
                continue
        else:
            # 모든 시도 실패
            logger.warning(f"재무제표 조회 실패: 모든 보고서 유형 시도 완료")
            return None

        try:
            # 재무 데이터 파싱
            accounts = data.get("list", [])

            financial = FinancialData(
                corp_code=corp_code,
                corp_name="",
                stock_code="",
                fiscal_year=try_year,
            )

            for item in accounts:
                account_nm = item.get("account_nm", "")
                # 당기 금액 (thstrm_amount)
                amount_str = item.get("thstrm_amount", "").replace(",", "")
                amount = int(amount_str) if amount_str and amount_str != "-" else None

                # 전기 금액 (frmtrm_amount) - 성장률 계산용
                prev_str = item.get("frmtrm_amount", "").replace(",", "")
                prev_amount = int(prev_str) if prev_str and prev_str != "-" else None

                if not financial.corp_name:
                    financial.corp_name = item.get("corp_code", "")
                if not financial.stock_code:
                    financial.stock_code = item.get("stock_code", "")

                # 계정과목 매핑
                if "매출액" in account_nm or "수익(매출액)" in account_nm:
                    financial.revenue = amount
                    if amount and prev_amount and prev_amount != 0:
                        financial.revenue_growth = ((amount - prev_amount) / abs(prev_amount)) * 100

                elif "영업이익" in account_nm:
                    financial.operating_income = amount

                elif "당기순이익" in account_nm or "당기순손익" in account_nm:
                    financial.net_income = amount
                    if amount and prev_amount and prev_amount != 0:
                        financial.income_growth = ((amount - prev_amount) / abs(prev_amount)) * 100

                elif "자산총계" in account_nm:
                    financial.total_assets = amount

                elif "부채총계" in account_nm:
                    financial.total_liabilities = amount

                elif "자본총계" in account_nm:
                    financial.total_equity = amount

            # 재무비율 계산
            if financial.revenue and financial.operating_income:
                financial.operating_margin = (financial.operating_income / financial.revenue) * 100

            if financial.total_equity and financial.total_liabilities:
                financial.debt_ratio = (financial.total_liabilities / financial.total_equity) * 100

            if financial.total_equity and financial.net_income:
                financial.roe = (financial.net_income / financial.total_equity) * 100

            return financial

        except Exception as e:
            logger.error(f"재무제표 파싱 실패: {e}")
            return None

    async def get_financial_ratios(
        self,
        corp_code: str,
        year: str = None
    ) -> Dict[str, float]:
        """주요 재무비율 조회 (별도 API)"""
        if not year:
            year = str(datetime.now().year - 1)

        try:
            # 주요재무비율 API (fnlttCmpnyIndx.json)
            data = await self._request("fnlttCmpnyIndx.json", {
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": "11011",
                "idx_cl_code": "M210000",  # 수익성지표
            })

            ratios = {}

            if data.get("status") == "000":
                for item in data.get("list", []):
                    idx_nm = item.get("idx_nm", "")
                    idx_val = item.get("idx_val", "")

                    if idx_val and idx_val != "-":
                        try:
                            val = float(idx_val.replace(",", ""))
                            ratios[idx_nm] = val
                        except ValueError:
                            pass

            return ratios

        except Exception as e:
            logger.error(f"재무비율 조회 실패: {e}")
            return {}

    async def search_company(self, keyword: str) -> List[Dict[str, str]]:
        """기업명으로 검색"""
        # DART API는 직접 검색 기능이 제한적
        # 전체 기업 목록에서 검색하거나 별도 DB 필요
        logger.warning("DART API 기업 검색은 제한적입니다. 전체 기업 목록 로드 필요")
        return []

    async def get_financial_data_by_stock_code(
        self,
        stock_code: str
    ) -> Optional[FinancialData]:
        """종목코드로 재무제표 조회 (편의 메서드)"""
        # 종목코드 → DART 고유번호 변환
        corp_code = await self.get_corp_code(stock_code)

        if not corp_code:
            logger.warning(f"종목코드 {stock_code}의 DART 고유번호를 찾을 수 없습니다")
            return None

        return await self.get_financial_statements(corp_code)


# 싱글톤 인스턴스
dart_client = DartClient()
