#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovZ_Communication
Module: TradovZ10_InboundSignalReceiver.py
Purpose: Inbound webhook/command receiver — external signals -> order proposals

Author: Mohamed Talib (with Claude)
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    A localhost HTTP receiver, modeled on TradovM08_HealthEndpoint's threaded
    ``http.server``, that accepts authenticated POST signals (e.g. TradingView
    alerts, scripts), parses them into a SignalEnvelope, audits every receipt,
    and hands valid signals to an injected handler.

    Phase-3 scope (this module): receive → authenticate → parse → audit →
    hand off. It is **paper-safe**: the default handler only acknowledges
    receipt and executes nothing. Phase 4 injects a handler that runs the signal
    through the readiness gate (R13), the risk stack (E01/E26), and OrderManager
    (B02) — so external signals become *risk-checked proposals*, never direct
    fills.

    Safety:
        - Binds localhost only; never expose directly to the internet.
        - Shared-secret auth via constant-time compare (the secret is carried in
          the path: ``POST /signal/{secret}``).
        - Every request — including rejects — is sent to the audit sink.

    The module has no Tradov or Qt dependencies (stdlib only), so it is fully
    headless and unit-testable without the GUI runtime.
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

_logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8799
MAX_BODY_BYTES = 64 * 1024

VALID_SIDES = frozenset({"buy", "sell"})
VALID_ORDER_TYPES = frozenset({"market", "limit", "stop"})


class SignalValidationError(ValueError):
    """Raised when an inbound signal payload is malformed."""


@dataclass(frozen=True)
class SignalEnvelope:
    """Normalized external trading signal (the receiver boundary type).

    Kept self-contained rather than routed through Z02_MessageProtocol: that is
    a heavyweight internal agent-handoff/bus protocol, whereas this is a small
    external boundary type. Convert to a ProtocolMessage only if a signal later
    needs to traverse the internal bus.
    """

    symbol: str
    side: str
    quantity: int | None = None
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    source: str = "unknown"
    strategy: str = "manual"
    client_tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _opt_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SignalValidationError(f"'{name}' must be a number") from None


def parse_signal_envelope(payload: object) -> SignalEnvelope:
    """Validate and normalize a raw JSON payload into a SignalEnvelope."""
    if not isinstance(payload, dict):
        raise SignalValidationError("payload must be a JSON object")

    symbol = str(payload.get("symbol", "")).strip().upper()
    if not symbol:
        raise SignalValidationError("missing 'symbol'")

    side = str(payload.get("side", "")).strip().lower()
    if side not in VALID_SIDES:
        raise SignalValidationError(f"'side' must be one of {sorted(VALID_SIDES)}")

    order_type = str(payload.get("order_type", "market")).strip().lower()
    if order_type not in VALID_ORDER_TYPES:
        raise SignalValidationError(
            f"'order_type' must be one of {sorted(VALID_ORDER_TYPES)}"
        )

    quantity = payload.get("quantity")
    if quantity is not None:
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            raise SignalValidationError("'quantity' must be an integer") from None
        if quantity <= 0:
            raise SignalValidationError("'quantity' must be positive")

    limit_price = _opt_float(payload.get("limit_price"), "limit_price")
    stop_price = _opt_float(payload.get("stop_price"), "stop_price")
    if order_type == "limit" and limit_price is None:
        raise SignalValidationError("'limit_price' is required for limit orders")
    if order_type == "stop" and stop_price is None:
        raise SignalValidationError("'stop_price' is required for stop orders")

    client_tag = payload.get("client_tag")
    return SignalEnvelope(
        symbol=symbol,
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=stop_price,
        source=str(payload.get("source", "unknown")),
        strategy=str(payload.get("strategy", "manual")),
        client_tag=str(client_tag) if client_tag is not None else None,
    )


def _default_handler(envelope: SignalEnvelope) -> dict[str, Any]:
    """Phase-3 default: acknowledge receipt without executing (paper-safe)."""
    return {"disposition": "received", "executed": False}


class _SignalHandler(BaseHTTPRequestHandler):
    """HTTP request handler — delegates to the owning InboundSignalReceiver."""

    def log_message(self, fmt: str, *args: Any) -> None:
        _logger.debug("InboundSignalReceiver: %s", fmt % args)

    def _send_json(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok"})
        else:
            self._send_json(404, {"error": "not found", "path": self.path})

    def do_POST(self) -> None:
        receiver: InboundSignalReceiver = self.server.receiver  # type: ignore[attr-defined]
        remote = self.client_address[0] if self.client_address else ""

        if not self.path.startswith("/signal/"):
            self._send_json(404, {"error": "not found", "path": self.path})
            return

        provided_secret = self.path[len("/signal/") :]
        if not receiver.secret_ok(provided_secret):
            receiver.audit("rejected", None, {"reason": "bad secret"}, remote=remote)
            self._send_json(403, {"error": "forbidden"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            receiver.audit("rejected", None, {"reason": "missing/oversized body"}, remote=remote)
            self._send_json(400, {"error": "missing or oversized body"})
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            receiver.audit("rejected", None, {"reason": "invalid json"}, remote=remote)
            self._send_json(400, {"error": "invalid JSON"})
            return

        try:
            envelope = parse_signal_envelope(payload)
        except SignalValidationError as exc:
            receiver.audit("rejected", None, {"reason": str(exc)}, remote=remote)
            self._send_json(400, {"error": str(exc)})
            return

        try:
            disposition = receiver.handle(envelope)
        except Exception as exc:  # a handler error must not take the server down
            _logger.exception("InboundSignalReceiver handler error")
            receiver.audit("error", envelope, {"error": str(exc)}, remote=remote)
            self._send_json(500, {"error": "handler failure"})
            return

        receiver.audit("accepted", envelope, disposition, remote=remote)
        self._send_json(200, {"status": "ok", **disposition})


class InboundSignalReceiver:
    """Threaded localhost HTTP receiver for external trading signals.

    Args:
        secret: Shared secret carried in the request path (``/signal/{secret}``).
        host/port: Bind address (localhost; port 0 picks an ephemeral port).
        handler: ``Callable[[SignalEnvelope], dict]`` processing a valid signal
            into a disposition dict. Default acknowledges receipt only.
        audit_sink: ``Callable[[dict], None]`` recording every request +
            disposition. Default logs.
    """

    def __init__(
        self,
        *,
        secret: str,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        handler: Callable[[SignalEnvelope], dict[str, Any]] | None = None,
        audit_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if not secret:
            raise ValueError("secret is required")
        self._secret = str(secret)
        self._host = host
        self._port = port
        self._handler = handler or _default_handler
        self._audit_sink = audit_sink
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    # -- internal hooks used by the request handler --
    def secret_ok(self, provided: str) -> bool:
        return hmac.compare_digest(str(provided), self._secret)

    def handle(self, envelope: SignalEnvelope) -> dict[str, Any]:
        return self._handler(envelope)

    def audit(
        self,
        status: str,
        envelope: SignalEnvelope | None,
        detail: dict[str, Any],
        *,
        remote: str = "",
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "status": status,
            "remote": remote,
            "signal": envelope.to_dict() if envelope is not None else None,
            "detail": detail,
        }
        if self._audit_sink is not None:
            try:
                self._audit_sink(record)
            except Exception:  # auditing must never break request handling
                _logger.exception("InboundSignalReceiver audit sink failed")
        else:
            _logger.info("inbound signal %s: %s", status, record)

    # -- lifecycle --
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            _logger.warning("InboundSignalReceiver already running")
            return
        server = HTTPServer((self._host, self._port), _SignalHandler)
        server.receiver = self  # type: ignore[attr-defined]
        self._server = server
        self._port = server.server_address[1]  # resolve ephemeral (port=0) binds
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="TradovZ10-InboundSignalReceiver",
            daemon=True,
        )
        self._thread.start()
        _logger.info("InboundSignalReceiver started → %s", self.url)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        _logger.info("InboundSignalReceiver stopped")

    @property
    def url(self) -> str:
        return f"http://{self._host}:{self._port}"
