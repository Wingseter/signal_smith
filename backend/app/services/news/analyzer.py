"""
뉴스 분석 서비스 (Gemini)

실시간 뉴스 분석을 위한 빠른 Gemini 기반 분석기
"""

import logging
from datetime import datetime
from typing import Optional

import google.generativeai as genai

from app.config import settings
from .models import (
    NewsArticle, NewsAnalysisResult, NewsSentiment,
    POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS, lookup_stock_code
)

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """Gemini 기반 뉴스 분석기"""

    ANALYSIS_PROMPT = """당신은 한국 주식시장 전문 애널리스트입니다.
다음 뉴스가 관련 종목의 주가에 미칠 영향을 분석해주세요.

[뉴스 정보]
제목: {title}
출처: {source}
기존 종목정보: {company_info}
본문: {content}

[분석 요청]
1. 관련 종목 추출 - 뉴스에서 언급된 상장 기업을 찾아주세요
   - 회사명: 정확한 회사명 (예: 삼성전자, LG에너지솔루션)
   - 종목코드: 6자리 숫자 (모르면 "미상")
2. 주가 영향 점수 (1-10점, 10점이 가장 긍정적)
3. 감성 분류 (very_positive/positive/neutral/negative/very_negative)
4. 매매 신호 (BUY/SELL/HOLD) - 반드시 BUY, SELL, HOLD 중 하나만 선택
   - BUY: 점수 8점 이상, 매우 긍정적 (대형 계약, 실적 서프라이즈, 신사업 진출)
   - SELL: 점수 3점 이하, 매우 부정적 (실적 악화, 소송, 규제, 대규모 손실)
   - HOLD: 점수 4-7점, 영향 불분명하거나 중립적인 경우
5. 신뢰도 (0.5-0.95) - 분석의 확신 정도
   - 0.85-0.95: 매우 명확한 영향 (공시, 대규모 M&A, 실적 발표)
   - 0.7-0.85: 명확한 영향 (계약 체결, 신제품 출시)
   - 0.5-0.7: 불확실한 영향 (루머, 전망 기사, 시장 동향)
6. 분석 근거 (1-2문장)

[응답 형식] - 반드시 이 형식을 따라주세요
회사명: [추출된 회사명 또는 "미상"]
종목코드: [6자리 코드 또는 "미상"]
점수: [숫자]
감성: [분류]
신호: [매매신호]
신뢰도: [0.5-0.95 사이 소수]
근거: [설명]
"""

    def __init__(self):
        self._model = None
        self._initialized = False

    def _initialize(self):
        """Gemini 모델 초기화"""
        if self._initialized:
            return

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY가 설정되지 않았습니다")

        genai.configure(api_key=settings.google_api_key)
        self._model = genai.GenerativeModel(settings.gemini_model)
        self._initialized = True
        logger.info(f"Gemini 분석기 초기화 완료 (모델: {settings.gemini_model})")

    def _score_to_sentiment(self, score: int) -> NewsSentiment:
        """점수를 감성으로 변환"""
        if score >= 8:
            return NewsSentiment.VERY_POSITIVE
        elif score >= 6:
            return NewsSentiment.POSITIVE
        elif score >= 4:
            return NewsSentiment.NEUTRAL
        elif score >= 2:
            return NewsSentiment.NEGATIVE
        else:
            return NewsSentiment.VERY_NEGATIVE

    def _quick_sentiment_check(self, title: str) -> Optional[int]:
        """키워드 기반 빠른 감성 체크 (LLM 호출 전 필터링)"""
        positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in title)
        negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in title)

        # 명확한 경우만 반환
        if positive_count >= 2 and negative_count == 0:
            return 8
        elif negative_count >= 2 and positive_count == 0:
            return 2

        return None  # LLM 분석 필요

    def _parse_response(self, response_text: str) -> dict:
        """Gemini 응답 파싱"""
        result = {
            "company_name": None,
            "symbol": None,
            "score": 5,
            "sentiment": "neutral",
            "signal": "HOLD",
            "confidence": 0.7,
            "reason": "분석 결과를 파싱할 수 없습니다"
        }

        try:
            import re
            lines = response_text.strip().split("\n")
            for line in lines:
                line = line.strip()

                if line.startswith("회사명:"):
                    company = line.replace("회사명:", "").strip()
                    if company and company != "미상" and company != "없음":
                        result["company_name"] = company

                elif line.startswith("종목코드:"):
                    code = line.replace("종목코드:", "").strip()
                    # 6자리 숫자 추출
                    code_match = re.search(r"\d{6}", code)
                    if code_match:
                        result["symbol"] = code_match.group()

                elif line.startswith("점수:"):
                    score_text = line.replace("점수:", "").strip()
                    numbers = re.findall(r"\d+", score_text)
                    if numbers:
                        result["score"] = min(10, max(1, int(numbers[0])))

                elif line.startswith("감성:"):
                    sentiment = line.replace("감성:", "").strip().lower()
                    # 한글 감성 매핑
                    sentiment_map = {
                        "매우 긍정": "very_positive", "매우긍정": "very_positive", "매우 긍정적": "very_positive",
                        "긍정": "positive", "긍정적": "positive",
                        "중립": "neutral", "중립적": "neutral",
                        "부정": "negative", "부정적": "negative",
                        "매우 부정": "very_negative", "매우부정": "very_negative", "매우 부정적": "very_negative",
                    }
                    mapped = sentiment_map.get(sentiment, sentiment)
                    if mapped in ["very_positive", "positive", "neutral", "negative", "very_negative"]:
                        result["sentiment"] = mapped

                elif line.startswith("신호:"):
                    signal = line.replace("신호:", "").strip().upper()
                    # 한글 신호 매핑
                    signal_map = {"매수": "BUY", "매도": "SELL", "보유": "HOLD", "관망": "HOLD"}
                    mapped_signal = signal_map.get(signal.replace(" ", ""), signal)
                    if mapped_signal in ["BUY", "SELL", "HOLD"]:
                        result["signal"] = mapped_signal

                elif line.startswith("신뢰도:"):
                    confidence_text = line.replace("신뢰도:", "").strip()
                    # 소수점 숫자 추출
                    conf_numbers = re.findall(r"0?\.\d+|\d+\.\d+", confidence_text)
                    if conf_numbers:
                        conf = float(conf_numbers[0])
                        result["confidence"] = min(0.95, max(0.5, conf))

                elif line.startswith("근거:"):
                    result["reason"] = line.replace("근거:", "").strip()

        except Exception as e:
            logger.error(f"응답 파싱 오류: {e}")

        # 점수와 신호 일관성 보정
        score = result["score"]
        signal = result["signal"]

        # 점수가 낮은데 BUY이면 HOLD로 조정
        if score <= 5 and signal == "BUY":
            result["signal"] = "HOLD"
            logger.warning(f"신호 보정: BUY -> HOLD (점수: {score})")

        # 점수가 높은데 SELL이면 HOLD로 조정
        if score >= 6 and signal == "SELL":
            result["signal"] = "HOLD"
            logger.warning(f"신호 보정: SELL -> HOLD (점수: {score})")

        return result

    async def analyze(self, article: NewsArticle) -> NewsAnalysisResult:
        """뉴스 분석 수행"""
        self._initialize()

        # 빠른 감성 체크
        quick_score = self._quick_sentiment_check(article.title)
        if quick_score is not None:
            logger.debug(f"빠른 분석 적용: {article.title} -> {quick_score}점")
            return NewsAnalysisResult(
                article=article,
                score=quick_score,
                sentiment=self._score_to_sentiment(quick_score),
                confidence=0.7,  # 키워드 기반이므로 신뢰도 낮음
                analysis_reason="키워드 기반 빠른 분석",
                trading_signal="BUY" if quick_score >= 7 else ("SELL" if quick_score <= 3 else "HOLD"),
                analyzer="gemini_quick"
            )

        # Gemini 분석
        try:
            company_info = article.company_name or article.symbol or "미상"
            content = article.content or article.summary or "(본문 없음)"

            prompt = self.ANALYSIS_PROMPT.format(
                title=article.title,
                source=article.source,
                company_info=company_info,
                content=content[:500]  # 토큰 절약
            )

            response = await self._model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                )
            )

            parsed = self._parse_response(response.text)

            # 추출된 종목정보로 article 업데이트
            if parsed["company_name"] and not article.company_name:
                article.company_name = parsed["company_name"]

            # 종목코드 설정 (우선순위: Gemini 추출 > 매핑 테이블 조회)
            if not article.symbol:
                if parsed["symbol"]:
                    article.symbol = parsed["symbol"]
                elif article.company_name:
                    # 회사명으로 종목코드 조회 시도
                    mapped_code = lookup_stock_code(article.company_name)
                    if mapped_code:
                        article.symbol = mapped_code
                        logger.info(f"종목코드 매핑: {article.company_name} -> {mapped_code}")

            return NewsAnalysisResult(
                article=article,
                score=parsed["score"],
                sentiment=NewsSentiment(parsed["sentiment"]),
                confidence=parsed["confidence"],  # 동적 신뢰도 사용
                analysis_reason=parsed["reason"],
                trading_signal=parsed["signal"],
                analyzer="gemini"
            )

        except Exception as e:
            logger.error(f"Gemini 분석 오류: {e}")
            # 실패 시 중립 반환
            return NewsAnalysisResult(
                article=article,
                score=5,
                sentiment=NewsSentiment.NEUTRAL,
                confidence=0.0,
                analysis_reason=f"분석 실패: {str(e)}",
                trading_signal="HOLD",
                analyzer="gemini_error"
            )

    async def analyze_batch(self, articles: list[NewsArticle]) -> list[NewsAnalysisResult]:
        """여러 뉴스 일괄 분석"""
        results = []
        for article in articles:
            result = await self.analyze(article)
            results.append(result)
        return results


# 싱글톤 인스턴스
news_analyzer = NewsAnalyzer()
