#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovT_Testing
Module: TradovT199_ConnectionProbe.py
Purpose: Tests for the headless Tradier connectivity probe (C30)

Verifies the probe parses quote payloads, resolves trading mode, and returns
the (connected, mode_label) contract — all without network or GUI.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from Tradov.TradovC_MarketData import TradovC30_ConnectionProbe as probe


# --------------------------------------------------------------------------- #
# runtime_trading_mode
# --------------------------------------------------------------------------- #
def test_mode_from_runtime_context():
    ctx = SimpleNamespace(mode="live")
    assert probe.runtime_trading_mode(ctx) == "live"


def test_mode_from_env_override(monkeypatch):
    monkeypatch.setenv("TRADOV_TRADING_MODE", "live")
    assert probe.runtime_trading_mode() == "live"


def test_mode_defaults_to_paper(monkeypatch):
    monkeypatch.delenv("TRADOV_TRADING_MODE", raising=False)
    monkeypatch.delenv("TRADING_MODE", raising=False)
    assert probe.runtime_trading_mode() == "paper"


# --------------------------------------------------------------------------- #
# market_data_probe_succeeded
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"quotes": {"quote": {"symbol": "TRAD", "last": 9.9}}}, True),  # single dict
        ({"quotes": {"quote": [{"symbol": "TRAD"}, {"symbol": "X"}]}}, True),  # list
        ({"quotes": {"quote": [{"symbol": "X"}]}}, False),
        ({"quotes": {}}, False),
        ("not-a-dict", False),
    ],
)
def test_probe_succeeded(payload, expected):
    assert probe.market_data_probe_succeeded(payload) is expected


# --------------------------------------------------------------------------- #
# check_api_connection (factory mocked — no network)
# --------------------------------------------------------------------------- #
def test_check_connection_success(monkeypatch):
    fake_client = SimpleNamespace(test_connection=lambda: True)
    monkeypatch.setattr(probe, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(probe, "create_tradier_client_from_env", lambda **kw: fake_client)

    # runtime_context is authoritative for mode (env can be clobbered by the
    # probe's load_dotenv(override=True)).
    connected, label = probe.check_api_connection(SimpleNamespace(mode="live"))
    assert connected is True
    assert "LIVE" in label


def test_check_connection_paper_label(monkeypatch):
    fake_client = SimpleNamespace(test_connection=lambda: True)
    monkeypatch.setattr(probe, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(probe, "create_tradier_client_from_env", lambda **kw: fake_client)
    monkeypatch.setattr(probe, "runtime_trading_mode", lambda ctx=None: "paper")

    connected, label = probe.check_api_connection()
    assert connected is True
    assert "PAPER" in label


def test_check_connection_no_quote(monkeypatch):
    fake_client = SimpleNamespace(test_connection=lambda: False)
    monkeypatch.setattr(probe, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(probe, "create_tradier_client_from_env", lambda **kw: fake_client)

    connected, _ = probe.check_api_connection()
    assert connected is False


def test_check_connection_handles_client_error(monkeypatch):
    def boom(**kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(probe, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(probe, "create_tradier_client_from_env", boom)

    connected, label = probe.check_api_connection()
    assert connected is False
    assert "error" in label.lower()


def test_check_connection_unavailable(monkeypatch):
    monkeypatch.setattr(probe, "TRADIER_AVAILABLE", False)
    monkeypatch.setattr(probe, "create_tradier_client_from_env", None)
    connected, label = probe.check_api_connection()
    assert connected is False
    assert "unavailable" in label.lower()
