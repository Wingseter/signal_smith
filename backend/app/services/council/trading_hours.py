"""
거래 시간 체크 유틸리티

한국 주식시장(KRX) 거래 시간:
- 정규장: 09:00 - 15:30
- 시간외 단일가: 15:40 - 16:00, 18:00 - 18:30, 08:30 - 09:00
- 휴일: 토/일, 공휴일
"""

import logging
from datetime import datetime, time, date
from typing import Tuple, Optional
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class MarketSession(str, Enum):
    """시장 세션"""
    CLOSED = "closed"                    # 장 마감
    PRE_MARKET = "pre_market"           # 장전 (08:30-09:00)
    REGULAR = "regular"                  # 정규장 (09:00-15:30)
    POST_MARKET = "post_market"          # 장후 (15:40-18:30)
    AFTER_HOURS = "after_hours"          # 시간외 (휴일 등)


class TradingHoursChecker:
    """거래 시간 체크 및 관리"""

    # 정규 거래 시간
    REGULAR_OPEN = time(9, 0)
    REGULAR_CLOSE = time(15, 30)

    # 시간외 거래 시간
    PRE_MARKET_OPEN = time(8, 30)
    PRE_MARKET_CLOSE = time(9, 0)

    POST_MARKET_1_OPEN = time(15, 40)
    POST_MARKET_1_CLOSE = time(16, 0)

    POST_MARKET_2_OPEN = time(18, 0)
    POST_MARKET_2_CLOSE = time(18, 30)

    # 2025-2026 한국 공휴일 (매년 업데이트 필요)
    HOLIDAYS_2025 = {
        date(2025, 1, 1),   # 신정
        date(2025, 1, 28),  # 설날 연휴
        date(2025, 1, 29),  # 설날
        date(2025, 1, 30),  # 설날 연휴
        date(2025, 3, 1),   # 삼일절
        date(2025, 5, 5),   # 어린이날
        date(2025, 5, 6),   # 부처님오신날
        date(2025, 6, 6),   # 현충일
        date(2025, 8, 15),  # 광복절
        date(2025, 10, 5),  # 추석 연휴
        date(2025, 10, 6),  # 추석
        date(2025, 10, 7),  # 추석 연휴
        date(2025, 10, 9),  # 한글날
        date(2025, 12, 25), # 크리스마스
    }

    HOLIDAYS_2026 = {
        date(2026, 1, 1),   # 신정
        date(2026, 2, 16),  # 설날 연휴
        date(2026, 2, 17),  # 설날
        date(2026, 2, 18),  # 설날 연휴
        date(2026, 3, 1),   # 삼일절
        date(2026, 5, 5),   # 어린이날
        date(2026, 5, 24),  # 부처님오신날
        date(2026, 6, 6),   # 현충일
        date(2026, 8, 15),  # 광복절
        date(2026, 9, 24),  # 추석 연휴
        date(2026, 9, 25),  # 추석
        date(2026, 9, 26),  # 추석 연휴
        date(2026, 10, 9),  # 한글날
        date(2026, 12, 25), # 크리스마스
    }

    def __init__(self):
        self._holidays = self.HOLIDAYS_2025 | self.HOLIDAYS_2026

    def is_holiday(self, dt: Optional[datetime] = None) -> bool:
        """공휴일 여부 확인"""
        if dt is None:
            dt = datetime.now()
        return dt.date() in self._holidays

    def is_weekend(self, dt: Optional[datetime] = None) -> bool:
        """주말 여부 확인"""
        if dt is None:
            dt = datetime.now()
        return dt.weekday() >= 5  # 토(5), 일(6)

    def is_trading_day(self, dt: Optional[datetime] = None) -> bool:
        """거래일 여부 확인"""
        if dt is None:
            dt = datetime.now()
        return not self.is_weekend(dt) and not self.is_holiday(dt)

    def get_market_session(self, dt: Optional[datetime] = None) -> MarketSession:
        """현재 시장 세션 확인"""
        if dt is None:
            dt = datetime.now()

        # 거래일이 아니면 마감
        if not self.is_trading_day(dt):
            return MarketSession.CLOSED

        current_time = dt.time()

        # 정규장
        if self.REGULAR_OPEN <= current_time < self.REGULAR_CLOSE:
            return MarketSession.REGULAR

        # 장전
        if self.PRE_MARKET_OPEN <= current_time < self.PRE_MARKET_CLOSE:
            return MarketSession.PRE_MARKET

        # 장후 1 (15:40-16:00)
        if self.POST_MARKET_1_OPEN <= current_time < self.POST_MARKET_1_CLOSE:
            return MarketSession.POST_MARKET

        # 장후 2 (18:00-18:30)
        if self.POST_MARKET_2_OPEN <= current_time < self.POST_MARKET_2_CLOSE:
            return MarketSession.POST_MARKET

        return MarketSession.CLOSED

    def can_execute_order(self, dt: Optional[datetime] = None) -> Tuple[bool, str]:
        """주문 실행 가능 여부 확인"""
        if dt is None:
            dt = datetime.now()

        session = self.get_market_session(dt)

        if session == MarketSession.REGULAR:
            return True, "정규장 시간입니다"
        elif session == MarketSession.PRE_MARKET:
            return True, "시간외 단일가(장전) 시간입니다"
        elif session == MarketSession.POST_MARKET:
            return True, "시간외 단일가(장후) 시간입니다"
        elif not self.is_trading_day(dt):
            if self.is_weekend(dt):
                return False, "주말에는 거래할 수 없습니다"
            else:
                return False, "공휴일에는 거래할 수 없습니다"
        else:
            return False, "장 마감 시간입니다"

    def get_next_trading_session(self, dt: Optional[datetime] = None) -> Tuple[datetime, MarketSession]:
        """다음 거래 세션 시작 시간 반환"""
        if dt is None:
            dt = datetime.now()

        current_date = dt.date()
        current_time = dt.time()

        # 오늘이 거래일인 경우
        if self.is_trading_day(dt):
            # 정규장 전
            if current_time < self.REGULAR_OPEN:
                # 장전 시간 체크
                if current_time < self.PRE_MARKET_OPEN:
                    return datetime.combine(current_date, self.PRE_MARKET_OPEN), MarketSession.PRE_MARKET
                elif current_time < self.PRE_MARKET_CLOSE:
                    return dt, MarketSession.PRE_MARKET  # 현재 장전
                else:
                    return datetime.combine(current_date, self.REGULAR_OPEN), MarketSession.REGULAR

            # 정규장 시간
            elif current_time < self.REGULAR_CLOSE:
                return dt, MarketSession.REGULAR

            # 장후
            elif current_time < self.POST_MARKET_1_CLOSE:
                if current_time < self.POST_MARKET_1_OPEN:
                    return datetime.combine(current_date, self.POST_MARKET_1_OPEN), MarketSession.POST_MARKET
                return dt, MarketSession.POST_MARKET

            elif current_time < self.POST_MARKET_2_CLOSE:
                if current_time < self.POST_MARKET_2_OPEN:
                    return datetime.combine(current_date, self.POST_MARKET_2_OPEN), MarketSession.POST_MARKET
                return dt, MarketSession.POST_MARKET

        # 다음 거래일 찾기
        from datetime import timedelta
        next_date = current_date + timedelta(days=1)
        while not self.is_trading_day(datetime.combine(next_date, time(12, 0))):
            next_date += timedelta(days=1)
            if (next_date - current_date).days > 30:  # 안전장치
                break

        return datetime.combine(next_date, self.PRE_MARKET_OPEN), MarketSession.PRE_MARKET

    def time_until_market_open(self, dt: Optional[datetime] = None) -> Optional[int]:
        """시장 오픈까지 남은 시간(초) 반환, 이미 열려있으면 None"""
        if dt is None:
            dt = datetime.now()

        can_trade, _ = self.can_execute_order(dt)
        if can_trade:
            return None

        next_session, _ = self.get_next_trading_session(dt)
        delta = next_session - dt
        return int(delta.total_seconds())

    def get_status_message(self, dt: Optional[datetime] = None) -> str:
        """현재 거래 상태 메시지"""
        if dt is None:
            dt = datetime.now()

        session = self.get_market_session(dt)
        can_trade, reason = self.can_execute_order(dt)

        if can_trade:
            if session == MarketSession.REGULAR:
                remaining = datetime.combine(dt.date(), self.REGULAR_CLOSE) - dt
                minutes = int(remaining.total_seconds() // 60)
                return f"🟢 정규장 진행 중 (마감까지 {minutes}분)"
            else:
                return f"🟡 {reason}"
        else:
            next_session, next_type = self.get_next_trading_session(dt)
            delta = next_session - dt
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)

            if hours > 0:
                return f"🔴 {reason} - 다음 거래: {next_session.strftime('%m/%d %H:%M')} ({hours}시간 {minutes}분 후)"
            else:
                return f"🔴 {reason} - 다음 거래: {next_session.strftime('%H:%M')} ({minutes}분 후)"


# 싱글톤 인스턴스
trading_hours = TradingHoursChecker()


async def wait_for_market_open():
    """시장 오픈까지 대기 (비동기)"""
    while True:
        can_trade, reason = trading_hours.can_execute_order()
        if can_trade:
            return

        # 다음 체크까지 대기 (1분 또는 남은 시간)
        wait_seconds = min(60, trading_hours.time_until_market_open() or 60)
        logger.info(f"시장 대기 중: {reason} - {wait_seconds}초 후 재확인")
        await asyncio.sleep(wait_seconds)
