#!/usr/bin/env python3
"""Focused coverage tests for B06, B21, U47, and E02 shim modules."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from Spyder.SpyderB_Broker import SpyderB06_DashboardOrderManager as b06
from Spyder.SpyderB_Broker import SpyderB21_BrokerProtocol as b21
from Spyder.SpyderE_Risk import SpyderE02_DataFreshnessMonitor as e02
from Spyder.SpyderU_Utilities import SpyderU47_OptionalImport as u47


class _StubClient:
    def __init__(self, *, cancel_raises: bool = False, orders_raises: bool = False, positions_raises: bool = False):
        self.cancel_raises = cancel_raises
        self.orders_raises = orders_raises
        self.positions_raises = positions_raises
        self.cancelled = []
        self.multileg_payloads = []

    def get_orders(self):
        if self.orders_raises:
            raise RuntimeError("orders failed")
        return {
            "orders": {
                "order": [
                    {"id": "1", "status": "open"},
                    {"id": "2", "status": "filled"},
                    {"id": "3", "status": "pending"},
                    {"id": "4", "status": "partially_filled"},
                ]
            }
        }

    def get_positions(self):
        if self.positions_raises:
            raise RuntimeError("positions failed")
        return {"positions": {"position": [{"symbol": "SPY", "quantity": 1}]}}

    def cancel_order(self, order_id: int):
        if self.cancel_raises:
            raise RuntimeError("cancel failed")
        self.cancelled.append(order_id)

    def place_multileg_order(self, **kwargs):
        self.multileg_payloads.append(kwargs)
        return {"order": {"id": "abc-123"}}


@dataclass
class _Leg:
    option_symbol: str
    side: str
    quantity: int


class _OrderSide:
    BUY_TO_CLOSE = "BUY_TO_CLOSE"
    SELL_TO_CLOSE = "SELL_TO_CLOSE"


class _OrderDuration:
    DAY = "day"


def test_b21_protocol_runtime_compliance_true_and_false():
    class _Compliant:
        def place_order(self, symbol, side, quantity, order_type, limit_price=None, **kwargs):
            return {"order": {"id": "1"}}

        def get_order(self, order_id):
            return {"order": {"id": order_id}}

        def cancel_order(self, order_id):
            return True

        def get_positions(self):
            return []

        def close_position(self, symbol, urgency="IMMEDIATE", reason="close_position", force=False):
            return {}

        def close_position_verified(self, symbol, timeout_s=10.0, urgency="IMMEDIATE", reason="close_position_verified"):
            return {"status": "verified"}

        def get_account_balances(self):
            return {"balances": {}}

    assert b21.is_broker_compliant(_Compliant()) is True
    assert b21.is_broker_compliant(object()) is False


def test_b06_get_client_for_env_paths(monkeypatch):
    monkeypatch.setattr(b06, "TRADIER_AVAILABLE", False)
    assert b06._get_client_for_env(None, use_live=False) is None

    captured = {}

    monkeypatch.setattr(b06, "TRADIER_AVAILABLE", True)
    monkeypatch.setattr(
        b06,
        "create_tradier_client_from_env",
        lambda environment: captured.setdefault("environment", environment) or "client",
    )
    monkeypatch.setattr(b06, "TradingEnvironment", SimpleNamespace(LIVE="live", SANDBOX="sandbox"))
    assert b06._get_client_for_env(None, use_live=False) == "live"
    assert captured["environment"] == "live"

    captured.clear()
    assert b06._get_client_for_env(None, use_live=True) == "live"
    assert captured["environment"] == "live"

    monkeypatch.setattr(
        b06,
        "create_tradier_client_from_env",
        lambda environment: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert b06._get_client_for_env(None, use_live=True) is None


def test_b06_defaults_to_live_lazy_client_policy():
    mgr = b06.DashboardOrderManager()
    assert mgr._use_live is True


def test_b06_fetch_pending_orders_filters_statuses():
    mgr = b06.DashboardOrderManager(client=_StubClient())
    orders = mgr.fetch_pending_orders()
    ids = {o["id"] for o in orders}
    assert ids == {"1", "3", "4"}


def test_b06_fetch_pending_orders_handles_no_client_and_errors():
    b06_unavailable = pytest.MonkeyPatch()
    b06_unavailable.setattr(b06, "TRADIER_AVAILABLE", False)
    mgr = b06.DashboardOrderManager(client=None)
    assert mgr.fetch_pending_orders() == []
    b06_unavailable.undo()

    mgr.set_client(_StubClient(orders_raises=True))
    assert mgr.fetch_pending_orders() == []


def test_b06_cancel_orders_success_and_fail_paths():
    client = _StubClient()
    mgr = b06.DashboardOrderManager(client=client)

    success, fail = mgr.cancel_orders([{"id": "10"}, {"id": "0"}, {"foo": "bar"}])
    assert success == 1
    assert fail == 2
    assert client.cancelled == [10]

    mgr.set_client(_StubClient(cancel_raises=True))
    success, fail = mgr.cancel_orders([{"id": "20"}])
    assert success == 0
    assert fail == 1


def test_b06_cancel_order_by_id_raises_without_client():
    b06_unavailable = pytest.MonkeyPatch()
    b06_unavailable.setattr(b06, "TRADIER_AVAILABLE", False)
    mgr = b06.DashboardOrderManager(client=None)
    with pytest.raises(RuntimeError):
        mgr.cancel_order_by_id(1)
    b06_unavailable.undo()


def test_b06_fetch_orders_and_positions_happy_and_error_paths():
    mgr = b06.DashboardOrderManager(client=_StubClient())
    payload = mgr.fetch_orders_and_positions()
    assert len(payload["pending_orders"]) == 3
    assert payload["open_positions"][0]["symbol"] == "SPY"

    mgr.set_client(_StubClient(orders_raises=True, positions_raises=True))
    payload = mgr.fetch_orders_and_positions()
    assert payload == {"pending_orders": [], "open_positions": []}


def test_b06_build_close_legs_and_submit(monkeypatch):
    monkeypatch.setattr(b06, "OptionLeg", _Leg)
    monkeypatch.setattr(b06, "OrderSide", _OrderSide)
    monkeypatch.setattr(b06, "OrderDuration", _OrderDuration)
    monkeypatch.setattr(
        b06,
        "build_option_symbol",
        lambda symbol, expiration, opt_type_char, strike: f"{symbol}-{expiration}-{opt_type_char}-{strike}",
    )

    client = _StubClient()
    mgr = b06.DashboardOrderManager(client=client)

    legs = mgr.build_close_legs(
        [
            {"leg": "Sell Put", "strike": "$580P", "cntr": "2", "expiry": "12/20"},
            {"leg": "Buy Call", "strike": "$600C", "cntr": "1", "expiry": "12/20"},
        ]
    )
    assert len(legs) == 2
    assert legs[0].side == _OrderSide.BUY_TO_CLOSE
    assert legs[1].side == _OrderSide.SELL_TO_CLOSE

    resp = mgr.submit_multileg_close("test-strategy", [{"leg": "Sell Put", "strike": "$580P", "cntr": "1", "expiry": "12/20"}])
    assert resp["order"]["id"] == "abc-123"
    assert client.multileg_payloads[0]["duration"] == _OrderDuration.DAY


def test_b06_build_close_legs_validation_errors(monkeypatch):
    monkeypatch.setattr(b06, "OptionLeg", _Leg)
    monkeypatch.setattr(b06, "OrderSide", _OrderSide)
    monkeypatch.setattr(b06, "build_option_symbol", lambda *_args, **_kwargs: "OCC")

    mgr = b06.DashboardOrderManager(client=_StubClient())

    with pytest.raises(ValueError):
        mgr.build_close_legs([{"leg": "Sell Put", "strike": "$580P", "cntr": "0", "expiry": "12/20"}])
    with pytest.raises(ValueError):
        mgr.build_close_legs([{"leg": "Sell Put", "strike": "$580", "cntr": "1", "expiry": "12/20"}])
    with pytest.raises(ValueError):
        mgr.build_close_legs([{"leg": "Sell Put", "strike": "$580P", "cntr": "1", "expiry": "1220"}])
    with pytest.raises(ValueError):
        mgr.build_close_legs([{"leg": "Hold", "strike": "$580P", "cntr": "1", "expiry": "12/20"}])


def test_u47_optional_import_success_and_missing_paths(caplog):
    ok = u47.optional_import("math", purpose="math ops")
    assert ok.available is True
    assert bool(ok) is True
    assert ok.sqrt(4) == 2

    missing = u47.optional_import("spyder_this_module_does_not_exist", purpose="rare feature")
    assert missing.available is False
    assert bool(missing) is False

    with pytest.raises(ImportError):
        _ = missing.some_attr

    with caplog.at_level("WARNING"):
        missing.warn_once("feature-a")
        missing.warn_once("feature-a")
    assert len([r for r in caplog.records if "Optional dependency" in r.message]) == 1


def test_u47_optional_import_required_on_current_platform_raises():
    current = u47.platform.system().lower()
    with pytest.raises(ImportError):
        u47.optional_import("spyder_this_module_does_not_exist", required_on=(current,))


def test_e02_deprecated_shim_exports_symbols():
    assert hasattr(e02, "DataFreshnessMonitor")
    assert hasattr(e02, "create_freshness_monitor")
