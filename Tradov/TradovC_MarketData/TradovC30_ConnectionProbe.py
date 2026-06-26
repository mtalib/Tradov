#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovC_MarketData
Module: TradovC30_ConnectionProbe.py
Purpose: Headless Tradier connectivity probe (no GUI dependency)

Author: Mohamed Talib (with Claude)
Year Created: 2026
Last Updated: 2026-06-26

Module Description:
    Headless equivalent of G18.check_api_connection. The dashboard's probe lives
    in TradovG18_MarketDataWorker, which imports PySide6 — so non-GUI callers
    (the readiness coordinator R13, the inbound signal receiver Z10, scripts)
    cannot reuse it without dragging in Qt. This module provides the same
    live-endpoint quote probe with zero GUI dependency, reusing the canonical
    ``create_tradier_client_from_env`` factory (B40) so no credential-loading
    logic is duplicated.

    Market data is always read from the LIVE endpoint, for both paper and live
    trading modes (paper execution still consumes real quotes).

    Intended use: pass ``check_api_connection`` as the ``connection_probe`` to
    ``TradovR13_ReadinessGateCoordinator.gather_inputs``.

    Note: G18 retains its own copy for now (it has unrelated in-flight changes);
    point it at this module in a later cleanup to remove the duplication.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from Tradov.TradovU_Utilities.TradovU51_RuntimeContext import RuntimeContext

try:
    from Tradov.TradovB_Broker.TradovB40_TradierClient import (
        TradingEnvironment,
        create_tradier_client_from_env,
    )

    TRADIER_AVAILABLE = True
except Exception:  # pragma: no cover - import guard for partial environments
    TradingEnvironment = None  # type: ignore[assignment]
    create_tradier_client_from_env = None  # type: ignore[assignment]
    TRADIER_AVAILABLE = False

_logger = logging.getLogger(__name__)

PROBE_SYMBOL = "TRAD"


def runtime_trading_mode(runtime_context: RuntimeContext | None = None) -> str:
    """Return the normalized runtime trading mode ('paper' | 'live')."""
    if runtime_context is not None:
        return runtime_context.mode
    override = str(os.environ.get("TRADOV_TRADING_MODE", "")).strip().lower()
    if override:
        return override
    return str(os.environ.get("TRADING_MODE", "paper")).strip().lower()


def market_data_probe_succeeded(payload: Any) -> bool:
    """Return True when a lightweight quote probe returns the probe symbol."""
    quotes_raw = (
        payload.get("quotes", {}).get("quote", []) if isinstance(payload, dict) else []
    )
    if isinstance(quotes_raw, dict):
        quotes_raw = [quotes_raw]
    return any(
        isinstance(quote, dict) and str(quote.get("symbol", "")).upper() == PROBE_SYMBOL
        for quote in quotes_raw
    )


def check_api_connection(
    runtime_context: RuntimeContext | None = None,
) -> tuple[bool, str]:
    """Probe the Tradier live market-data endpoint.

    Returns ``(connected, mode_label)`` — the same contract G18 exposes and the
    shape R13.gather_inputs expects from its ``connection_probe``.
    """
    if not TRADIER_AVAILABLE or create_tradier_client_from_env is None:
        return False, "Tradier unavailable"
    try:
        try:
            from dotenv import load_dotenv  # noqa: PLC0415

            load_dotenv(override=True)
        except ImportError:
            pass

        client = create_tradier_client_from_env(
            environment=TradingEnvironment.LIVE,
            runtime_context=runtime_context,
        )
        payload = client.get_quotes([PROBE_SYMBOL])
        if market_data_probe_succeeded(payload):
            mode = runtime_trading_mode(runtime_context)
            mode_label = "PAPER" if mode == "paper" else "LIVE"
            return True, f"Tradier API ({mode_label})"
        return False, "Tradier API (no quote)"
    except Exception as exc:  # network/credential failure -> not connected
        _logger.warning("check_api_connection failed: %s", exc)
        return False, f"Tradier API error: {exc}"
