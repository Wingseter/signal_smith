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
    POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS
)

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """Gemini 기반 뉴스 분석기"""

    ANALYSIS_PROMPT = """당신은 한국 주식시장 전문 애널리스트입니다.
다음 뉴스가 해당 종목의 주가에 미칠 영향을 분석해주세요.

[뉴스 정보]
제목: {title}
출처: {source}
종목: {company_info}
본문: {content}

[분석 요청]
1. 주가 영향 점수 (1-10점, 10점이 가장 긍정적)
2. 감성 분류 (very_positive/positive/neutral/negative/very_negative)
3. 매매 신호 (BUY/SELL/HOLD)
4. 분석 근거 (1-2문장)

[응답 형식] - 반드시 이 형식을 따라주세요
점수: [숫자]
감성: [분류]
신호: [매매신호]
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
            "score": 5,
            "sentiment": "neutral",
            "signal": "HOLD",
            "reason": "분석 결과를 파싱할 수 없습니다"
        }

        try:
            lines = response_text.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("점수:"):
                    score_text = line.replace("점수:", "").strip()
                    # 숫자만 추출
                    import re
                    numbers = re.findall(r"\d+", score_text)
                    if numbers:
                        result["score"] = min(10, max(1, int(numbers[0])))

                elif line.startswith("감성:"):
                    sentiment = line.replace("감성:", "").strip().lower()
                    if sentiment in ["very_positive", "positive", "neutral", "negative", "very_negative"]:
                        result["sentiment"] = sentiment

                elif line.startswith("신호:"):
                    signal = line.replace("신호:", "").strip().upper()
                    if signal in ["BUY", "SELL", "HOLD"]:
                        result["signal"] = signal

                elif line.startswith("근거:"):
                    result["reason"] = line.replace("근거:", "").strip()

        except Exception as e:
            logger.error(f"응답 파싱 오류: {e}")

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
                    temperature=0.3,  # 일관된 분석을 위해 낮은 temperature
                    max_output_tokens=200,
                )
            )

            parsed = self._parse_response(response.text)

            return NewsAnalysisResult(
                article=article,
                score=parsed["score"],
                sentiment=NewsSentiment(parsed["sentiment"]),
                confidence=0.85,
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
