"""
심층 분석 서비스 (Tavily)

종목 집중 분석을 위한 Tavily 웹 검색 기반 심층 분석기
"""

import logging
from datetime import datetime
from typing import List, Optional

import httpx

from app.config import settings
from .models import DeepAnalysisResult

logger = logging.getLogger(__name__)


class DeepAnalyzer:
    """Tavily 기반 심층 분석기"""

    TAVILY_API_URL = "https://api.tavily.com/search"

    def __init__(self):
        self._api_key: Optional[str] = None

    def _get_api_key(self) -> str:
        """Tavily API 키 가져오기"""
        if self._api_key:
            return self._api_key

        # 환경변수에서 TAVILY_API_KEY 확인
        import os
        self._api_key = os.getenv("TAVILY_API_KEY")

        if not self._api_key:
            raise ValueError("TAVILY_API_KEY가 설정되지 않았습니다")

        return self._api_key

    async def search_news(
        self,
        query: str,
        max_results: int = 10,
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
    ) -> dict:
        """Tavily로 뉴스 검색"""
        try:
            api_key = self._get_api_key()

            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False,
            }

            if include_domains:
                payload["include_domains"] = include_domains

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.TAVILY_API_URL,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Tavily 검색 오류: {e}")
            return {"results": [], "answer": ""}

    async def analyze_stock(
        self,
        symbol: str,
        company_name: str,
        focus_topics: Optional[List[str]] = None
    ) -> DeepAnalysisResult:
        """종목 심층 분석

        Args:
            symbol: 종목코드
            company_name: 회사명
            focus_topics: 집중 분석할 토픽 (예: ["실적", "계약", "경쟁사"])
        """
        all_results = []
        sources = []

        # 기본 검색 쿼리들
        queries = [
            f"{company_name} 주식 뉴스 최신",
            f"{company_name} 실적 전망 2024",
            f"{company_name} 투자 의견",
        ]

        # 집중 토픽 추가
        if focus_topics:
            for topic in focus_topics:
                queries.append(f"{company_name} {topic}")

        # 병렬로 검색 수행
        for query in queries[:5]:  # 최대 5개 쿼리
            result = await self.search_news(
                query=query,
                max_results=5,
                include_domains=[
                    "news.naver.com",
                    "finance.naver.com",
                    "sedaily.com",
                    "hankyung.com",
                    "mk.co.kr",
                    "edaily.co.kr"
                ]
            )

            if result.get("results"):
                all_results.extend(result["results"])

            # 출처 수집
            for r in result.get("results", []):
                if r.get("url"):
                    sources.append(r["url"])

        # 결과 분석 및 종합
        key_findings = []
        risk_factors = []
        opportunity_factors = []

        positive_count = 0
        negative_count = 0

        for result in all_results:
            title = result.get("title", "")
            content = result.get("content", "")
            text = f"{title} {content}".lower()

            # 긍정/부정 신호 수집
            positive_keywords = ["호재", "상승", "성장", "흑자", "수주", "계약", "돌파"]
            negative_keywords = ["악재", "하락", "적자", "감소", "위기", "손실"]

            for kw in positive_keywords:
                if kw in text:
                    positive_count += 1
                    if len(key_findings) < 5:
                        key_findings.append(f"[호재] {title[:50]}")
                    if "성장" in text or "수주" in text or "계약" in text:
                        opportunity_factors.append(title[:50])
                    break

            for kw in negative_keywords:
                if kw in text:
                    negative_count += 1
                    if len(risk_factors) < 5:
                        risk_factors.append(title[:50])
                    break

        # 감성 점수 계산 (1-10)
        total = positive_count + negative_count
        if total == 0:
            sentiment_score = 5  # 중립
        else:
            ratio = positive_count / total
            sentiment_score = round(1 + ratio * 9)  # 1-10 스케일

        # 투자 권고
        if sentiment_score >= 7:
            recommendation = "매수 고려 - 긍정적 뉴스 다수 확인"
        elif sentiment_score >= 5:
            recommendation = "관망 - 혼재된 신호, 추가 모니터링 필요"
        else:
            recommendation = "주의 - 부정적 뉴스 다수 확인"

        # 뉴스 요약 생성
        news_summary = f"{company_name}({symbol})에 대해 {len(all_results)}개의 관련 기사를 분석했습니다. "
        news_summary += f"긍정적 신호 {positive_count}건, 부정적 신호 {negative_count}건이 감지되었습니다."

        return DeepAnalysisResult(
            symbol=symbol,
            company_name=company_name,
            news_summary=news_summary,
            sentiment_score=sentiment_score,
            key_findings=key_findings[:5],
            risk_factors=risk_factors[:5],
            opportunity_factors=opportunity_factors[:5],
            recommendation=recommendation,
            sources=list(set(sources))[:10],  # 중복 제거 후 최대 10개
            analyzed_at=datetime.now()
        )

    async def compare_stocks(
        self,
        stocks: List[tuple[str, str]]  # [(symbol, company_name), ...]
    ) -> List[DeepAnalysisResult]:
        """여러 종목 비교 분석"""
        results = []
        for symbol, company_name in stocks:
            result = await self.analyze_stock(symbol, company_name)
            results.append(result)

        # 점수순 정렬
        results.sort(key=lambda x: x.sentiment_score, reverse=True)
        return results


# 싱글톤 인스턴스
deep_analyzer = DeepAnalyzer()
