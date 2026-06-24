#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovU_Utilities
Module: TradovU50_RegimeOverrideStore.py
Purpose: Persistent store for the user-selectable market-regime override

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-15 Time: 00:00:00

Module Description:
    Tiny, dependency-free JSON store for the user's market-regime override.
    It is the shared backbone between the GUI (which writes the user's choice)
    and the D31 StrategyOrchestrator (which reads it on start-up and re-syncs
    each detection cycle), so the override:

      * survives restarts, and
      * works even when no trading session is running (no live orchestrator),
        taking effect the next time the orchestrator reads the file.

    The file lives alongside the other runtime snapshots in ``market_data/``:
        market_data/regime_override.json
    Format:
        {"regime": "crisis", "updated_at": "2026-06-15T18:00:00+00:00"}
        {"regime": null,    "updated_at": "..."}   # auto-detection

    This module is value-agnostic (it stores/loads a string token); validation
    against the canonical regime set is done by D31. ``REGIME_OPTIONS`` mirrors
    D31's MarketRegime enum and is provided for building the GUI selector
    without importing the (heavy) orchestrator module.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from pathlib import Path

logger = logging.getLogger("RegimeOverrideStore")

# Canonical UI options: (token, human label). ``None``/"auto" means
# auto-detection. The tokens mirror D31 MarketRegime values; a drift check
# lives in the test-suite. Keep in sync with TradovD31 ``MarketRegime``.
REGIME_OPTIONS: tuple[tuple[str | None, str], ...] = (
    (None, "Auto (detect)"),
    ("bull_low_vol", "Bull · Low Vol"),
    ("bull_high_vol", "Bull · High Vol"),
    ("bear_low_vol", "Bear · Low Vol"),
    ("bear_high_vol", "Bear · High Vol"),
    ("sideways_low_vol", "Sideways · Low Vol"),
    ("sideways_high_vol", "Sideways · High Vol"),
    ("crisis", "Crisis"),
    ("recovery", "Recovery"),
    ("event_transition", "Event Transition"),
)


def default_override_path() -> Path:
    """Default location of the override file (sibling of live_data.json)."""
    return Path.home() / "Projects" / "Tradov" / "market_data" / "regime_override.json"


def load_regime_override(path: Path | str | None = None) -> str | None:
    """Return the persisted regime token, or None for auto / missing / invalid.

    Never raises: a missing or corrupt file is treated as "auto".
    """
    target = Path(path) if path is not None else default_override_path()
    try:
        if not target.exists():
            return None
        with open(target, encoding="utf-8") as fh:
            payload = json.load(fh)
        regime = payload.get("regime") if isinstance(payload, dict) else None
        if regime is None:
            return None
        token = str(regime).strip().lower()
        return token or None
    except Exception as exc:  # corrupt file, permissions, etc.
        logger.warning("Failed to read regime override from %s: %s", target, exc)
        return None


def save_regime_override(
    regime: str | None, path: Path | str | None = None
) -> bool:
    """Persist the regime override token (None / "auto" clears it).

    Returns True on success, False on failure (never raises).
    """
    target = Path(path) if path is not None else default_override_path()
    token = None
    if regime is not None:
        token = str(regime).strip().lower()
        if token in ("", "auto", "none"):
            token = None
    payload = {
        "regime": token,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish write: tmp then replace, so a reader never sees a partial file.
        tmp = target.with_suffix(target.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        tmp.replace(target)
        return True
    except Exception as exc:
        logger.warning("Failed to write regime override to %s: %s", target, exc)
        return False


def clear_regime_override(path: Path | str | None = None) -> bool:
    """Clear the override (equivalent to ``save_regime_override(None)``)."""
    return save_regime_override(None, path)


__all__ = [
    "REGIME_OPTIONS",
    "default_override_path",
    "load_regime_override",
    "save_regime_override",
    "clear_regime_override",
]
