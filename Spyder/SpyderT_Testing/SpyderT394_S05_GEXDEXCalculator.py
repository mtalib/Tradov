from __future__ import annotations

from datetime import date
import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

from Spyder.SpyderB_Broker import SpyderB40_TradierClient as b40
from Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator import GEXDEXCalculator


pytestmark = pytest.mark.unit


def test_compute_from_internal_sources_retries_spy_expirations_once(monkeypatch) -> None:
    calc = GEXDEXCalculator()
    listed_expiration = "2099-12-19"
    expiration_calls: list[str] = []

    n09_module = ModuleType("SpyderN_OptionsAnalytics.SpyderN09_GammaExposure")
    n09_module.GammaExposureCalculator = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        get_spy_gex_summary=lambda: {"num_strikes": 0},
    )
    monkeypatch.setitem(sys.modules, n09_module.__name__, n09_module)

    n03_module = ModuleType("SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager")
    n03_module.OptionsChainManager = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        get_chain=lambda _symbol: __import__("pandas").DataFrame(),
    )
    monkeypatch.setitem(sys.modules, n03_module.__name__, n03_module)

    def _get_option_expirations(symbol: str) -> dict[str, object]:
        expiration_calls.append(symbol)
        if len(expiration_calls) == 1:
            raise b40.TradierAPIError(
                "Connection error on /markets/options/expirations: RemoteDisconnected"
            )
        return {"expirations": {"date": [listed_expiration]}}

    fake_client = SimpleNamespace(
        get_option_expirations=_get_option_expirations,
        get_option_chain_with_greeks=lambda _symbol, _expiration: [
            SimpleNamespace(
                strike=499.0,
                option_type="call",
                open_interest=120,
                gamma=0.012,
                delta=0.55,
                iv=0.18,
                expiration=listed_expiration,
            ),
            SimpleNamespace(
                strike=501.0,
                option_type="put",
                open_interest=140,
                gamma=0.011,
                delta=-0.45,
                iv=0.19,
                expiration=listed_expiration,
            ),
        ],
    )
    monkeypatch.setattr(b40, "create_tradier_client_from_env", lambda: fake_client)

    result = calc._compute_from_internal_sources(spot_price=500.0)

    assert expiration_calls == ["SPY", "SPY"]
    assert calc._cached_expirations == [listed_expiration]
    assert calc._expirations_cache_date == str(date.today())
    assert result["data_source"] == "SpyderB40_TradierClient"
    assert result["num_strikes"] == 2


def test_compute_from_internal_sources_skips_n09_without_summary_method(monkeypatch) -> None:
    calc = GEXDEXCalculator()
    init_calls: list[str] = []

    class _NoSummaryGammaExposureCalculator:
        def __init__(self) -> None:
            init_calls.append("init")

    n09_module = ModuleType("SpyderN_OptionsAnalytics.SpyderN09_GammaExposure")
    n09_module.GammaExposureCalculator = _NoSummaryGammaExposureCalculator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, n09_module.__name__, n09_module)

    chain_df = pd.DataFrame(
        [
            {
                "strike": 499.0,
                "option_type": "call",
                "open_interest": 120,
                "gamma": 0.012,
                "delta": 0.55,
            },
            {
                "strike": 501.0,
                "option_type": "put",
                "open_interest": 140,
                "gamma": 0.011,
                "delta": -0.45,
            },
        ]
    )
    n03_module = ModuleType("SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager")
    n03_module.OptionsChainManager = lambda: SimpleNamespace(  # type: ignore[attr-defined]
        get_chain=lambda _symbol: chain_df.copy(),
    )
    monkeypatch.setitem(sys.modules, n03_module.__name__, n03_module)

    result = calc._compute_from_internal_sources(spot_price=500.0)

    assert init_calls == []
    assert result["data_source"] == "live_chain"
    assert result["num_strikes"] == 2
