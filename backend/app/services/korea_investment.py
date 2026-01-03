"""
Korea Investment Securities API Client

Handles:
- Authentication and token management
- Real-time stock quotes (WebSocket)
- Stock information queries
- Historical price data
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import json

import httpx
import websockets

from app.config import settings
from app.core.redis import get_redis


class KoreaInvestmentClient:
    """Client for Korea Investment Securities API."""

    def __init__(self):
        self.base_url = settings.kis_base_url
        self.ws_url = settings.kis_ws_url
        self.app_key = settings.kis_app_key
        self.app_secret = settings.kis_app_secret
        self.account_number = settings.kis_account_number
        self.account_product_code = settings.kis_account_product_code
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get or refresh access token."""
        # Check cache first
        redis = await get_redis()
        cached_token = await redis.get("kis:access_token")
        if cached_token:
            return cached_token

        # Check if current token is still valid
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # Request new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth2/tokenP",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "appsecret": self.app_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 86400)  # Default 24 hours
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            # Cache token in Redis
            await redis.set(
                "kis:access_token",
                self._access_token,
                ex=expires_in - 300,  # 5 minutes buffer
            )

            return self._access_token

    def _get_headers(self, token: str, tr_id: str) -> dict:
        """Get common headers for API requests."""
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
        }

    async def get_stock_info(self, symbol: str) -> dict:
        """Get stock basic information."""
        if not self.app_key:
            return {"error": "API not configured"}

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/uapi/domestic-stock/v1/quotations/search-stock-info",
                headers=self._get_headers(token, "CTPF1002R"),
                params={
                    "PRDT_TYPE_CD": "300",  # Stock
                    "PDNO": symbol,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_current_price(self, symbol: str) -> dict:
        """Get current stock price."""
        if not self.app_key:
            return {"error": "API not configured"}

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=self._get_headers(token, "FHKST01010100"),
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",  # Stock market
                    "FID_INPUT_ISCD": symbol,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("output"):
                output = data["output"]
                return {
                    "symbol": symbol,
                    "current_price": float(output.get("stck_prpr", 0)),
                    "change": float(output.get("prdy_vrss", 0)),
                    "change_rate": float(output.get("prdy_ctrt", 0)),
                    "open": float(output.get("stck_oprc", 0)),
                    "high": float(output.get("stck_hgpr", 0)),
                    "low": float(output.get("stck_lwpr", 0)),
                    "volume": int(output.get("acml_vol", 0)),
                }
            return data

    async def get_daily_prices(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> list:
        """Get daily price history."""
        if not self.app_key:
            return []

        token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price",
                headers=self._get_headers(token, "FHKST01010400"),
                params={
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": symbol,
                    "FID_PERIOD_DIV_CODE": "D",  # Daily
                    "FID_ORG_ADJ_PRC": "0",  # Adjusted price
                },
            )
            response.raise_for_status()
            data = response.json()

            prices = []
            for item in data.get("output", []):
                prices.append({
                    "date": item.get("stck_bsop_date"),
                    "open": float(item.get("stck_oprc", 0)),
                    "high": float(item.get("stck_hgpr", 0)),
                    "low": float(item.get("stck_lwpr", 0)),
                    "close": float(item.get("stck_clpr", 0)),
                    "volume": int(item.get("acml_vol", 0)),
                })
            return prices

    async def subscribe_realtime(self, symbols: list, callback):
        """Subscribe to real-time price updates via WebSocket."""
        if not self.app_key:
            return

        approval_key = await self._get_websocket_approval_key()

        async with websockets.connect(self.ws_url) as ws:
            # Send subscription request for each symbol
            for symbol in symbols:
                subscribe_msg = {
                    "header": {
                        "approval_key": approval_key,
                        "custtype": "P",
                        "tr_type": "1",  # Subscribe
                        "content-type": "utf-8",
                    },
                    "body": {
                        "input": {
                            "tr_id": "H0STCNT0",  # Real-time price
                            "tr_key": symbol,
                        }
                    },
                }
                await ws.send(json.dumps(subscribe_msg))

            # Listen for updates
            while True:
                try:
                    message = await ws.recv()
                    data = self._parse_realtime_message(message)
                    if data:
                        await callback(data)
                except websockets.ConnectionClosed:
                    break

    async def _get_websocket_approval_key(self) -> str:
        """Get WebSocket approval key."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth2/Approval",
                json={
                    "grant_type": "client_credentials",
                    "appkey": self.app_key,
                    "secretkey": self.app_secret,
                },
            )
            response.raise_for_status()
            return response.json()["approval_key"]

    def _parse_realtime_message(self, message: str) -> Optional[dict]:
        """Parse real-time WebSocket message."""
        try:
            # KIS sends pipe-separated data
            parts = message.split("|")
            if len(parts) >= 4:
                data_parts = parts[3].split("^")
                if len(data_parts) >= 10:
                    return {
                        "symbol": data_parts[0],
                        "current_price": float(data_parts[2]),
                        "change": float(data_parts[4]),
                        "change_rate": float(data_parts[5]),
                        "volume": int(data_parts[8]),
                        "timestamp": datetime.now().isoformat(),
                    }
        except (ValueError, IndexError):
            pass
        return None


# Singleton instance
kis_client = KoreaInvestmentClient()
