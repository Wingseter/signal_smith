"""
Kiwoom Securities REST API Client -- Facade

Delegates to domain-specific sub-clients while maintaining
backward-compatible interface.
"""

from typing import Optional, List, Dict, Any

from app.config import settings
from app.services.kiwoom.base import (
    KiwoomBaseClient,
    StockPrice,
    OrderResult,
    Balance,
    Holding,
    RealizedPnlItem,
    OrderType,
    OrderSide,
)
from .token_manager import TokenManager
from .price_client import PriceClient
from .order_client import OrderClient
from .account_client import AccountClient
from .stock_info_client import StockInfoClient


class KiwoomRestClient(KiwoomBaseClient):
    """Kiwoom REST API facade -- delegates to domain sub-clients."""

    def __init__(self, is_mock: bool = True):
        self._http = TokenManager(is_mock)
        self._price = PriceClient(self._http)
        self._order = OrderClient(self._http)
        self._account = AccountClient(self._http)
        self._stock_info = StockInfoClient(self._http)

    # ── Token / Connection ──────────────────────────

    async def connect(self) -> bool:
        return await self._http.connect()

    async def disconnect(self) -> None:
        return await self._http.disconnect()

    async def is_connected(self) -> bool:
        return await self._http.is_connected()

    # ── Price ────────────────────────────────────────

    async def get_stock_price(self, symbol: str) -> Optional[StockPrice]:
        return await self._price.get_stock_price(symbol)

    async def get_stock_prices(self, symbols: List[str]) -> List[StockPrice]:
        return await self._price.get_stock_prices(symbols)

    async def get_daily_prices(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._price.get_daily_prices(symbol, start_date, end_date)

    async def get_minute_prices(
        self,
        symbol: str,
        interval: int = 1,
    ) -> List[Dict[str, Any]]:
        return await self._price.get_minute_prices(symbol, interval)

    # ── Order ────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: int = 0,
        order_type: OrderType = OrderType.LIMIT,
    ) -> OrderResult:
        return await self._order.place_order(symbol, side, quantity, price, order_type)

    async def cancel_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
    ) -> OrderResult:
        return await self._order.cancel_order(order_no, symbol, quantity)

    async def modify_order(
        self,
        order_no: str,
        symbol: str,
        quantity: int,
        price: int,
    ) -> OrderResult:
        return await self._order.modify_order(order_no, symbol, quantity, price)

    # ── Account ──────────────────────────────────────

    async def get_balance(self) -> Balance:
        return await self._account.get_balance()

    async def get_holdings(self) -> List[Holding]:
        return await self._account.get_holdings()

    async def get_realized_pnl(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[RealizedPnlItem]:
        return await self._account.get_realized_pnl(start_date, end_date)

    async def get_order_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return await self._account.get_order_history(start_date, end_date)

    # ── Stock Info ───────────────────────────────────

    async def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        return await self._stock_info.get_stock_info(symbol)

    async def search_stocks(self, keyword: str) -> List[Dict[str, Any]]:
        return await self._stock_info.search_stocks(keyword)

    async def get_market_stocks(self, market: str = "KOSPI") -> List[Dict[str, Any]]:
        return await self._stock_info.get_market_stocks(market)


# Singleton
kiwoom_client = KiwoomRestClient(is_mock=settings.kiwoom_is_mock)
