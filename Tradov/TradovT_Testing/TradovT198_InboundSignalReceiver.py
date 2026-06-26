#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovT_Testing
Module: TradovT198_InboundSignalReceiver.py
Purpose: Tests for the inbound webhook/command receiver (Z10)

Exercises envelope parsing plus the live threaded HTTP server end-to-end:
auth, parse, audit-on-receive, and handler hand-off.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from Tradov.TradovZ_Communication.TradovZ10_InboundSignalReceiver import (
    InboundSignalReceiver,
    SignalValidationError,
    parse_signal_envelope,
)

SECRET = "test-secret"


# --------------------------------------------------------------------------- #
# Envelope parsing (pure)
# --------------------------------------------------------------------------- #
def test_parse_valid_market_order():
    env = parse_signal_envelope(
        {"symbol": "spy", "side": "BUY", "quantity": 10, "order_type": "market"}
    )
    assert env.symbol == "SPY"  # normalized upper
    assert env.side == "buy"  # normalized lower
    assert env.quantity == 10
    assert env.order_type == "market"


@pytest.mark.parametrize(
    "payload, msg",
    [
        ({}, "symbol"),
        ({"symbol": "SPY"}, "side"),
        ({"symbol": "SPY", "side": "hodl"}, "side"),
        ({"symbol": "SPY", "side": "buy", "order_type": "teleport"}, "order_type"),
        ({"symbol": "SPY", "side": "buy", "quantity": 0}, "positive"),
        ({"symbol": "SPY", "side": "buy", "quantity": "ten"}, "integer"),
        ({"symbol": "SPY", "side": "buy", "order_type": "limit"}, "limit_price"),
        ({"symbol": "SPY", "side": "buy", "order_type": "stop"}, "stop_price"),
    ],
)
def test_parse_rejects_bad_payloads(payload, msg):
    with pytest.raises(SignalValidationError) as exc:
        parse_signal_envelope(payload)
    assert msg in str(exc.value)


# --------------------------------------------------------------------------- #
# Live server end-to-end
# --------------------------------------------------------------------------- #
def _post(url: str, body: object) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


def _get(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code


@pytest.fixture()
def server():
    captured: dict = {"signals": [], "audit": []}

    def handler(envelope):
        captured["signals"].append(envelope)
        return {"disposition": "proposed", "executed": False, "symbol": envelope.symbol}

    receiver = InboundSignalReceiver(
        secret=SECRET,
        host="127.0.0.1",
        port=0,  # ephemeral
        handler=handler,
        audit_sink=lambda rec: captured["audit"].append(rec),
    )
    receiver.start()
    try:
        yield receiver, captured
    finally:
        receiver.stop()


def test_healthz_ok(server):
    receiver, _ = server
    assert _get(f"{receiver.url}/healthz") == 200


def test_valid_signal_accepted_and_audited(server):
    receiver, captured = server
    status, body = _post(
        f"{receiver.url}/signal/{SECRET}",
        {"symbol": "SPY", "side": "buy", "quantity": 5, "order_type": "market"},
    )
    assert status == 200
    assert body["disposition"] == "proposed"
    assert body["symbol"] == "SPY"
    # handler received the parsed envelope
    assert captured["signals"][0].symbol == "SPY"
    # audit recorded an 'accepted' entry
    assert captured["audit"][-1]["status"] == "accepted"


def test_bad_secret_forbidden_and_audited(server):
    receiver, captured = server
    status, _ = _post(
        f"{receiver.url}/signal/wrong-secret",
        {"symbol": "SPY", "side": "buy", "quantity": 5},
    )
    assert status == 403
    assert captured["signals"] == []  # handler never invoked
    assert captured["audit"][-1]["status"] == "rejected"


def test_invalid_json_rejected(server):
    receiver, _ = server
    req = urllib.request.Request(
        f"{receiver.url}/signal/{SECRET}", data=b"{not json", method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
    except urllib.error.HTTPError as err:
        status = err.code
    assert status == 400


def test_invalid_envelope_rejected(server):
    receiver, captured = server
    status, body = _post(f"{receiver.url}/signal/{SECRET}", {"side": "buy"})
    assert status == 400
    assert "symbol" in body["error"]
    assert captured["signals"] == []


def test_unknown_post_path_404(server):
    receiver, _ = server
    status, _ = _post(f"{receiver.url}/nope", {"x": 1})
    assert status == 404
