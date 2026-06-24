from __future__ import annotations

import pytest


def test_b40_factory_defaults_to_live_when_env_unset(monkeypatch):
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TRADIER_LIVE_URL,
        TradingEnvironment,
        create_tradier_client_from_env,
    )

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct")
    monkeypatch.delenv("TRADIER_ENVIRONMENT", raising=False)

    client = create_tradier_client_from_env()

    assert client.environment is TradingEnvironment.LIVE
    assert client.base_url == TRADIER_LIVE_URL


def test_b40_factory_prefers_live_specific_credentials(monkeypatch):
    from Tradov.TradovB_Broker.TradovB40_TradierClient import create_tradier_client_from_env

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "legacy-token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "legacy-acct")
    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "live-token")
    monkeypatch.setenv("TRADIER_LIVE_ACCOUNT_ID", "live-acct")

    client = create_tradier_client_from_env()

    assert client.api_key == "live-token"
    assert client.account_id == "live-acct"


def test_client_prefers_profile_account_id_when_resolving(monkeypatch):
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TradierClient,
        TradingEnvironment,
    )

    client = TradierClient(
        api_key="token",
        account_id="wrong-acct",
        environment=TradingEnvironment.LIVE,
    )

    monkeypatch.setattr(
        TradierClient,
        "get_user_profile",
        lambda self: {"profile": {"account": {"account_number": "profile-acct"}}},
    )

    captured = {}

    def _fake_make_request(method, endpoint, **kwargs):
        captured["method"] = method
        captured["endpoint"] = endpoint
        return {"balances": {}}

    monkeypatch.setattr(client, "_make_request", _fake_make_request)

    client.get_account_balances()

    assert client._resolved_account_id == "profile-acct"
    assert captured["endpoint"] == "/accounts/profile-acct/balances"


@pytest.mark.parametrize("raw_env", ["", "live", "production"])
def test_b40_factory_accepts_only_live_tokens(monkeypatch, raw_env):
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TradingEnvironment,
        create_tradier_client_from_env,
    )

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", raw_env)

    assert create_tradier_client_from_env().environment is TradingEnvironment.LIVE


@pytest.mark.parametrize("raw_env", ["sandbox", "paper", "dev", "invalid"])
def test_b40_factory_rejects_non_live_tokens(monkeypatch, raw_env):
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        create_tradier_client_from_env,
    )

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", raw_env)

    with pytest.raises(ValueError, match="TRADIER_ENVIRONMENT"):
        create_tradier_client_from_env()


def test_startup_validation_accepts_live_specific_credentials(monkeypatch):
    pytest.importorskip("dotenv")

    from config.config import validate_startup_config

    monkeypatch.delenv("TRADIER_LIVE_API_KEY", raising=False)
    monkeypatch.delenv("TRADIER_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "live-token")
    monkeypatch.setenv("TRADIER_LIVE_ACCOUNT_ID", "live-acct")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")

    validate_startup_config()


@pytest.mark.parametrize(
    ("broker_env", "market_data_env", "allow_sandbox", "expected_ok"),
    [
        ("live", "live", None, True),
        ("production", "production", None, True),
        ("sandbox", "live", None, False),
        ("live", "sandbox", None, False),
        ("live", "live", "true", False),
    ],
)
def test_r12_live_only_policy(monkeypatch, broker_env, market_data_env, allow_sandbox, expected_ok):
    from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import SessionSupervisor

    monkeypatch.setenv("TRADIER_ENVIRONMENT", broker_env)
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", market_data_env)
    if allow_sandbox is None:
        monkeypatch.delenv("TRADOV_ALLOW_SANDBOX_MARKET_DATA", raising=False)
    else:
        monkeypatch.setenv("TRADOV_ALLOW_SANDBOX_MARKET_DATA", allow_sandbox)

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    ok, violation = supervisor._validate_live_only_tradier_policy()

    assert ok is expected_ok
    if expected_ok:
        assert violation == ""
    else:
        assert violation


def test_c29_rejects_sandbox_market_data(monkeypatch):
    from Tradov.TradovC_MarketData.TradovC29_DataProviderRouter import DataProviderRouter

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "sandbox")
    monkeypatch.delenv("TRADOV_ALLOW_SANDBOX_MARKET_DATA", raising=False)

    with pytest.raises(ValueError, match="Live-only market-data policy"):
        DataProviderRouter().get_client()


def test_c29_rejects_sandbox_override(monkeypatch):
    from Tradov.TradovC_MarketData.TradovC29_DataProviderRouter import DataProviderRouter

    monkeypatch.setenv("TRADIER_LIVE_API_KEY", "token")
    monkeypatch.setenv("TRADIER_ACCOUNT_ID", "acct")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADOV_ALLOW_SANDBOX_MARKET_DATA", "true")

    with pytest.raises(ValueError, match="TRADOV_ALLOW_SANDBOX_MARKET_DATA"):
        DataProviderRouter().get_client()
