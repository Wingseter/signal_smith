"""
뉴스 모니터링 서비스

네이버 금융 뉴스를 크롤링하고 키워드 기반으로 트리거를 발생시킵니다.
"""

import asyncio
import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Set, Callable, Awaitable
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from .models import (
    NewsArticle, NewsCategory,
    TRIGGER_KEYWORDS, POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS
)

logger = logging.getLogger(__name__)


class NewsMonitor:
    """네이버 금융 뉴스 모니터"""

    # 네이버 금융 뉴스 URL
    NAVER_FINANCE_NEWS_URL = "https://finance.naver.com/news/mainnews.naver"
    NAVER_STOCK_NEWS_URL = "https://finance.naver.com/item/news.naver"

    def __init__(self):
        self._running = False
        self._seen_urls: Set[str] = set()  # 이미 본 뉴스 URL
        self._callbacks: List[Callable[[NewsArticle], Awaitable[None]]] = []
        self._poll_interval = 60  # 폴링 간격 (초)
        self._max_seen_urls = 1000  # 최대 저장 URL 수
        self._analyze_all = True  # 모든 뉴스 분석 (트리거 키워드 무시)

    def add_callback(self, callback: Callable[[NewsArticle], Awaitable[None]]):
        """뉴스 감지 시 호출될 콜백 등록"""
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[NewsArticle], Awaitable[None]]):
        """콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def _notify_callbacks(self, article: NewsArticle):
        """등록된 모든 콜백에 알림"""
        for callback in self._callbacks:
            try:
                await callback(article)
            except Exception as e:
                logger.error(f"콜백 실행 오류: {e}")

    def _detect_category(self, title: str, content: str = "") -> NewsCategory:
        """뉴스 카테고리 감지"""
        text = f"{title} {content}".lower()

        for category, keywords in TRIGGER_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category

        return NewsCategory.OTHER

    def _extract_keywords(self, title: str, content: str = "") -> List[str]:
        """키워드 추출"""
        text = f"{title} {content}"
        found_keywords = []

        # 트리거 키워드 검색
        for keywords in TRIGGER_KEYWORDS.values():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(keyword)

        # 긍정/부정 키워드 검색
        for keyword in POSITIVE_KEYWORDS + NEGATIVE_KEYWORDS:
            if keyword in text:
                found_keywords.append(keyword)

        return list(set(found_keywords))

    def _is_trigger_news(self, title: str) -> bool:
        """트리거 대상 뉴스인지 확인"""
        for keywords in TRIGGER_KEYWORDS.values():
            for keyword in keywords:
                if keyword in title:
                    return True
        return False

    async def fetch_main_news(self) -> List[NewsArticle]:
        """네이버 금융 메인 뉴스 크롤링"""
        articles = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.NAVER_FINANCE_NEWS_URL,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    },
                    timeout=10.0
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # 뉴스 목록 파싱 - 네이버 금융 HTML 구조:
                # <li class="block1">
                #   <dl>
                #     <dt class="thumb"><a href="..."><img></a></dt>
                #     <dd class="articleSubject"><a href="...">제목</a></dd>
                #     <dd class="articleSummary">
                #       요약...
                #       <span class="press">출처</span>
                #       <span class="wdate">2026-01-13 22:01:14</span>
                #     </dd>
                #   </dl>
                # </li>
                news_items = soup.select("ul.newsList li")

                for item in news_items:
                    try:
                        # 제목과 링크 - articleSubject 내의 a 태그에서 추출
                        subject_elem = item.select_one("dd.articleSubject a")
                        if not subject_elem:
                            continue

                        title = subject_elem.get_text(strip=True)
                        url = subject_elem.get("href", "")

                        # 제목이 비어있으면 스킵
                        if not title:
                            continue

                        if not url.startswith("http"):
                            url = f"https://finance.naver.com{url}"

                        # 출처
                        source_elem = item.select_one(".press")
                        source = source_elem.get_text(strip=True) if source_elem else "네이버금융"

                        # 시간 - "2026-01-13 22:01:14" 형식
                        time_elem = item.select_one(".wdate")
                        published_at = datetime.now()
                        if time_elem:
                            time_text = time_elem.get_text(strip=True)
                            # "2026-01-13 22:01:14" 형식 파싱
                            try:
                                published_at = datetime.strptime(time_text, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                # "2024.01.13 15:30" 형식도 지원
                                try:
                                    published_at = datetime.strptime(time_text, "%Y.%m.%d %H:%M")
                                except ValueError:
                                    pass

                        # 종목 추출 (있는 경우)
                        symbol = None
                        company_name = None
                        stock_elem = item.select_one("a[href*='code=']")
                        if stock_elem:
                            href = stock_elem.get("href", "")
                            match = re.search(r"code=(\d{6})", href)
                            if match:
                                symbol = match.group(1)
                            company_name = stock_elem.get_text(strip=True)

                        article = NewsArticle(
                            title=title,
                            url=url,
                            source=source,
                            published_at=published_at,
                            symbol=symbol,
                            company_name=company_name,
                            category=self._detect_category(title),
                            keywords=self._extract_keywords(title),
                        )
                        articles.append(article)

                    except Exception as e:
                        logger.debug(f"뉴스 항목 파싱 오류: {e}")
                        continue

                logger.info(f"메인 뉴스 {len(articles)}건 크롤링 완료")

        except Exception as e:
            logger.error(f"메인 뉴스 크롤링 실패: {e}")

        return articles

    async def fetch_stock_news(self, symbol: str) -> List[NewsArticle]:
        """특정 종목의 뉴스 크롤링"""
        articles = []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.NAVER_STOCK_NEWS_URL,
                    params={"code": symbol},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    },
                    timeout=10.0
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # 종목명 추출
                company_name = ""
                name_elem = soup.select_one(".wrap_company h2 a")
                if name_elem:
                    company_name = name_elem.get_text(strip=True)

                # 뉴스 목록 파싱
                news_table = soup.select("table.type5 tbody tr")

                for row in news_table:
                    try:
                        title_elem = row.select_one("a.tit")
                        if not title_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        url = title_elem.get("href", "")

                        if not url.startswith("http"):
                            url = f"https://finance.naver.com{url}"

                        # 출처와 시간
                        info_elem = row.select_one(".info")
                        source = info_elem.get_text(strip=True) if info_elem else "네이버금융"

                        date_elem = row.select_one(".date")
                        published_at = datetime.now()
                        if date_elem:
                            date_text = date_elem.get_text(strip=True)
                            try:
                                published_at = datetime.strptime(date_text, "%Y.%m.%d %H:%M")
                            except ValueError:
                                pass

                        article = NewsArticle(
                            title=title,
                            url=url,
                            source=source,
                            published_at=published_at,
                            symbol=symbol,
                            company_name=company_name,
                            category=self._detect_category(title),
                            keywords=self._extract_keywords(title),
                        )
                        articles.append(article)

                    except Exception as e:
                        logger.debug(f"종목 뉴스 파싱 오류: {e}")
                        continue

                logger.info(f"종목 {symbol} 뉴스 {len(articles)}건 크롤링 완료")

        except Exception as e:
            logger.error(f"종목 {symbol} 뉴스 크롤링 실패: {e}")

        return articles

    async def _poll_news(self):
        """뉴스 폴링 루프"""
        while self._running:
            try:
                # 메인 뉴스 크롤링
                articles = await self.fetch_main_news()

                for article in articles:
                    # 이미 본 뉴스는 스킵
                    if article.url in self._seen_urls:
                        continue

                    self._seen_urls.add(article.url)

                    # 모든 뉴스 분석 모드이거나, 트리거 키워드가 포함된 뉴스만 콜백
                    if self._analyze_all or self._is_trigger_news(article.title):
                        logger.info(f"뉴스 분석 대상: {article.title[:50]}...")
                        await self._notify_callbacks(article)

                # URL 캐시 정리
                if len(self._seen_urls) > self._max_seen_urls:
                    # 가장 오래된 것들 제거 (set이라 순서 없음, 그냥 절반 제거)
                    urls_list = list(self._seen_urls)
                    self._seen_urls = set(urls_list[len(urls_list)//2:])

            except Exception as e:
                logger.error(f"뉴스 폴링 오류: {e}")

            await asyncio.sleep(self._poll_interval)

    async def start(self, poll_interval: int = 60):
        """모니터링 시작"""
        if self._running:
            logger.warning("뉴스 모니터가 이미 실행 중입니다")
            return

        self._running = True
        self._poll_interval = poll_interval
        logger.info(f"뉴스 모니터 시작 (폴링 간격: {poll_interval}초)")

        asyncio.create_task(self._poll_news())

    async def stop(self):
        """모니터링 중지"""
        self._running = False
        logger.info("뉴스 모니터 중지")

    def is_running(self) -> bool:
        """실행 상태 확인"""
        return self._running


# 싱글톤 인스턴스
news_monitor = NewsMonitor()
