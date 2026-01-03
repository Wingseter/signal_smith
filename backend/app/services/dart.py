"""
DART (Data Analysis, Retrieval and Transfer System) API Client

Korean Financial Supervisory Service's electronic disclosure system.
Provides access to:
- Financial statements
- Corporate disclosures
- Business reports
"""

from typing import Optional
from datetime import datetime
import xml.etree.ElementTree as ET

import httpx

from app.config import settings


class DartClient:
    """Client for DART API."""

    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self):
        self.api_key = settings.dart_api_key

    async def get_corp_code(self, stock_code: str) -> Optional[str]:
        """
        Get DART corporation code from stock code.

        Args:
            stock_code: Stock symbol (e.g., '005930' for Samsung)

        Returns:
            DART corp code or None
        """
        if not self.api_key:
            return None

        # Note: In production, you'd cache the corp code list
        # DART provides a zip file with all corp codes
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/corpCode.xml",
                params={"crtfc_key": self.api_key},
            )
            if response.status_code == 200:
                # Parse XML to find matching corp code
                # This is simplified - actual implementation would parse the full list
                pass
        return None

    async def get_financial_statements(
        self,
        corp_code: str,
        year: int,
        report_code: str = "11011",  # Annual report
    ) -> dict:
        """
        Get financial statements.

        Args:
            corp_code: DART corporation code
            year: Business year
            report_code: Report type
                - 11011: Annual
                - 11012: Semi-annual
                - 11013: 1st Quarter
                - 11014: 3rd Quarter

        Returns:
            Financial statement data
        """
        if not self.api_key:
            return {"error": "API not configured"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/fnlttSinglAcntAll.json",
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": report_code,
                    "fs_div": "CFS",  # Consolidated
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "000":
                return self._parse_financial_data(data.get("list", []))
            return {"error": data.get("message", "Unknown error")}

    async def get_disclosure_list(
        self,
        corp_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_count: int = 10,
    ) -> list:
        """
        Get list of corporate disclosures.

        Args:
            corp_code: Filter by corporation (optional)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            page_count: Number of results per page

        Returns:
            List of disclosures
        """
        if not self.api_key:
            return []

        params = {
            "crtfc_key": self.api_key,
            "page_count": str(page_count),
        }

        if corp_code:
            params["corp_code"] = corp_code
        if start_date:
            params["bgn_de"] = start_date
        if end_date:
            params["end_de"] = end_date

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/list.json",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "000":
                return [
                    {
                        "corp_name": item.get("corp_name"),
                        "report_name": item.get("report_nm"),
                        "receipt_number": item.get("rcept_no"),
                        "receipt_date": item.get("rcept_dt"),
                        "corp_code": item.get("corp_code"),
                    }
                    for item in data.get("list", [])
                ]
            return []

    async def get_disclosure_document(self, receipt_number: str) -> str:
        """
        Get full disclosure document.

        Args:
            receipt_number: Disclosure receipt number

        Returns:
            Document content as text
        """
        if not self.api_key:
            return ""

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/document.xml",
                params={
                    "crtfc_key": self.api_key,
                    "rcept_no": receipt_number,
                },
            )
            if response.status_code == 200:
                return response.text
            return ""

    async def get_major_shareholders(self, corp_code: str) -> list:
        """Get major shareholder information."""
        if not self.api_key:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/hyslrSttus.json",
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "000":
                return [
                    {
                        "shareholder_name": item.get("nm"),
                        "relationship": item.get("relate"),
                        "shares": item.get("stock_qy"),
                        "percentage": item.get("trmend_posesn_stock_qota_rt"),
                    }
                    for item in data.get("list", [])
                ]
            return []

    def _parse_financial_data(self, data_list: list) -> dict:
        """Parse financial statement data into structured format."""
        result = {
            "balance_sheet": {},
            "income_statement": {},
            "cash_flow": {},
        }

        for item in data_list:
            account_name = item.get("account_nm", "")
            amount = item.get("thstrm_amount", "0")
            fs_nm = item.get("sj_nm", "")

            try:
                amount = float(amount.replace(",", "")) if amount else 0
            except ValueError:
                amount = 0

            if "재무상태표" in fs_nm:
                result["balance_sheet"][account_name] = amount
            elif "손익계산서" in fs_nm or "포괄손익" in fs_nm:
                result["income_statement"][account_name] = amount
            elif "현금흐름" in fs_nm:
                result["cash_flow"][account_name] = amount

        return result


# Singleton instance
dart_client = DartClient()
