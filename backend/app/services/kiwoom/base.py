"""
Kiwoom API Base Client - Common interface for both REST and Open API+
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class OrderType(str, Enum):
    """주문 유형"""
    LIMIT = "00"  # 지정가
    MARKET = "03"  # 시장가
    CONDITIONAL = "05"  # 조건부지정가
    BEST_LIMIT = "06"  # 최유리지정가
    PRIORITY_LIMIT = "07"  # 최우선지정가
    IOC_LIMIT = "10"  # 지정가IOC
    FOK_LIMIT = "13"  # 지정가FOK
    IOC_MARKET = "16"  # 시장가IOC
    FOK_MARKET = "19"  # 시장가FOK


class OrderSide(str, Enum):
    """매수/매도 구분"""
    BUY = "1"  # 매수
    SELL = "2"  # 매도


@dataclass
class StockPrice:
    """주식 시세 정보"""
    symbol: str
    name: str
    current_price: int
    change: int
    change_rate: float
    open_price: int
    high_price: int
    low_price: int
    volume: int
    trade_amount: int
    timestamp: datetime


@dataclass
class OrderResult:
    """주문 결과"""
    order_no: str
    symbol: str
    order_type: str
    side: str
    quantity: int
    price: int
    status: str
    message: str
    timestamp: datetime


@dataclass
class Balance:
    """계좌 잔고"""
    total_deposit: int  # 예수금총액
    available_amount: int  # 주문가능금액
    total_purchase: int  # 총매입금액
    total_evaluation: int  # 총평가금액
    total_profit_loss: int  # 총손익금액
    profit_rate: float  # 수익률


@dataclass
class Holding:
    """보유 종목"""
    symbol: str
    name: str
    quantity: int
    avg_price: int
    current_price: int
    evaluation: int
    profit_loss: int
    profit_rate: float


class KiwoomBaseClient(ABC):
    """키움증권 API 기본 인터페이스"""

    @abstractmethod
    async def connect(self) -> bool:
        """API 연결"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """API 연결 해제"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """연결 상태 확인"""
        pass

    # ========== 시세 조회 ==========

    @abstractmethod
    async def get_stock_price(self, symbol: str) -> Optional[StockPrice]:
        """현재가 조회"""
        pass

    @abstractmethod
    async def get_stock_prices(self, symbols: List[str]) -> List[StockPrice]:
        """복수 종목 현재가 조회"""
        pass

    @abstractmethod
    async def get_daily_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """일봉 데이터 조회"""
        pass

    @abstractmethod
    async def get_minute_prices(
        self,
        symbol: str,
        interval: int = 1,
    ) -> List[Dict[str, Any]]:
        """분봉 데이터 조회"""
        pass

    # ========== 주문 ==========

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: int = 0,
        order_type: OrderType = OrderType.LIMIT,
    ) -> OrderResult:
        """주문 실행"""
        pass

    @abstractmethod
    async def cancel_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
    ) -> OrderResult:
        """주문 취소"""
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
        price: int,
    ) -> OrderResult:
        """주문 정정"""
        pass

    # ========== 계좌 ==========

    @abstractmethod
    async def get_balance(self) -> Balance:
        """계좌 잔고 조회"""
        pass

    @abstractmethod
    async def get_holdings(self) -> List[Holding]:
        """보유 종목 조회"""
        pass

    @abstractmethod
    async def get_order_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """주문 내역 조회"""
        pass

    # ========== 종목 정보 ==========

    @abstractmethod
    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """종목 기본 정보 조회"""
        pass

    @abstractmethod
    async def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        """종목 검색"""
        pass

    @abstractmethod
    async def get_market_stocks(self, market: str = "KOSPI") -> List[Dict[str, Any]]:
        """시장별 종목 리스트 조회"""
        pass
