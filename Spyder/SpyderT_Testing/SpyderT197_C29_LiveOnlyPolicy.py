"""T197 — C29 DataProviderRouter live-only market-data policy tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from Spyder.SpyderC_MarketData.SpyderC29_DataProviderRouter import DataProviderRouter


class _FakeTradingEnvironment:
    LIVE = SimpleNamespace(value="live")
    SANDBOX = SimpleNamespace(value="sandbox")


@pytest.fixture(autouse=True)
def _baseline_env(monkeypatch):
    monkeypatch.setenv("DATA_PROVIDER", "tradier")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.delenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA", raising=False)


class TestC29LiveOnlyPolicy:
    def test_builds_live_client_when_env_is_live(self, monkeypatch):
        captured = {}

        class _FakeTradierClient:
            def __init__(self, api_key, account_id, environment, **kwargs):
                captured["api_key"] = api_key
                captured["account_id"] = account_id
                captured["environment"] = environment
                captured["kwargs"] = kwargs

        fake_module = SimpleNamespace(
            TradierClient=_FakeTradierClient,
            TradingEnvironment=_FakeTradingEnvironment,
        )

        monkeypatch.setenv("TRADIER_LIVE_API_KEY", "live-key")
        monkeypatch.setenv("TRADIER_LIVE_ACCOUNT_ID", "live-account")

        with pytest.MonkeyPatch.context() as mp:
            mp.setitem(sys.modules, "SpyderB_Broker.SpyderB40_TradierClient", fake_module)
            router = DataProviderRouter()
            router.get_client()

        assert captured["api_key"] == "live-key"
        assert captured["account_id"] == "live-account"
        assert captured["environment"] == _FakeTradingEnvironment.LIVE

    def test_rejects_sandbox_market_data_environment(self, monkeypatch):
        monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "sandbox")
        router = DataProviderRouter()

        with pytest.raises(ValueError, match="Live-only market-data policy violation"):
            router.get_client()

    def test_rejects_sandbox_override_flag(self, monkeypatch):
        monkeypatch.setenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA", "true")
        router = DataProviderRouter()

        with pytest.raises(ValueError, match="not permitted"):
            router.get_client()
