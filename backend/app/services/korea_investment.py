"""
Korea Investment Securities API Client (Legacy Wrapper)

이 모듈은 레거시 호환성을 위해 유지됩니다.
실제 구현은 Kiwoom REST API 클라이언트로 이전되었습니다.

새로운 코드는 다음을 사용하세요:
    from app.services.kiwoom import KiwoomRestClient
"""

from app.services.kiwoom.rest_client import KiwoomRestClient, kiwoom_client

# Legacy alias for backward compatibility
# 기존 코드에서 kis_client를 사용하는 경우를 위한 호환성 유지
KoreaInvestmentClient = KiwoomRestClient
kis_client = kiwoom_client
