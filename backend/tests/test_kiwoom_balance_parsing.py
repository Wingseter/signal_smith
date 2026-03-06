import pytest

from app.services.kiwoom.rest_client import KiwoomRestClient


@pytest.mark.asyncio
async def test_get_balance_prefers_d2_estimated_deposit_for_total_deposit(monkeypatch):
    client = KiwoomRestClient(is_mock=True)

    async def fake_request(method, endpoint, data=None, api_id=None, **kwargs):
        if api_id == "kt00001":
            return {
                "return_code": 0,
                "entr": "000000001049666",
                "d2_entra": "000000005000000",
                "ord_alow_amt": "000000001049666",
            }
        if api_id == "kt00018":
            return {
                "return_code": 0,
                "tot_pur_amt": "000000000513000",
                "tot_evlt_amt": "000000000619000",
                "tot_evlt_pl": "000000000104603",
                "tot_prft_rt": "20.39",
            }
        return {"return_code": 0}

    monkeypatch.setattr(client._http, "_request", fake_request)

    balance = await client.get_balance()

    assert balance.total_deposit == 5_000_000
    assert balance.available_amount == 1_049_666
    assert balance.total_purchase == 513_000
    assert balance.total_evaluation == 619_000
    assert balance.total_profit_loss == 104_603
    assert balance.profit_rate == 20.39


@pytest.mark.asyncio
async def test_get_balance_prefers_largest_among_entr_d1_d2(monkeypatch):
    client = KiwoomRestClient(is_mock=True)

    async def fake_request(method, endpoint, data=None, api_id=None, **kwargs):
        if api_id == "kt00001":
            return {
                "return_code": 0,
                "entr": "000000001049666",
                "d1_entra": "000000004431946",
                "d2_entra": "000000004410006",
                "ord_alow_amt": "000000001049666",
            }
        if api_id == "kt00018":
            return {"return_code": 0}
        return {"return_code": 0}

    monkeypatch.setattr(client._http, "_request", fake_request)

    balance = await client.get_balance()

    assert balance.total_deposit == 4_431_946
    assert balance.available_amount == 1_049_666


@pytest.mark.asyncio
async def test_get_balance_uses_entr_when_d2_missing(monkeypatch):
    client = KiwoomRestClient(is_mock=True)

    async def fake_request(method, endpoint, data=None, api_id=None, **kwargs):
        if api_id == "kt00001":
            return {
                "return_code": 0,
                "entr": "000000001500000",
                "ord_alow_amt": "000000001300000",
            }
        if api_id == "kt00018":
            return {"return_code": 0}
        return {"return_code": 0}

    monkeypatch.setattr(client._http, "_request", fake_request)

    balance = await client.get_balance()

    assert balance.total_deposit == 1_500_000
    assert balance.available_amount == 1_300_000
