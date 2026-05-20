#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG25_DashboardSessionAdapter.py
Purpose: Read-only H05 session DB adapter for dashboard views
"""

from __future__ import annotations

from typing import Any
from collections.abc import Callable


class DashboardSessionAdapter:
    """Own session DB init, caching, and read helpers for the dashboard."""

    def __init__(self) -> None:
        self._db_by_mode: dict[str, Any] = {}
        self._init_failed_by_mode: dict[str, bool] = {
            "PAPER": False,
            "LIVE": False,
        }

    @staticmethod
    def _mode_key(mode: Any) -> str:
        raw_value = getattr(mode, "value", mode)
        text = str(raw_value or "").strip().upper()
        return text or "UNKNOWN"

    @classmethod
    def _is_paper_mode(cls, mode: Any) -> bool:
        return cls._mode_key(mode) == "PAPER"

    def has_init_failed(self, mode: Any) -> bool:
        return bool(self._init_failed_by_mode.get(self._mode_key(mode), False))

    def get_mode_session_db(
        self,
        mode: Any,
        *,
        log_error: Callable[[str], None] | None = None,
    ) -> Any | None:
        """Return a cached H05 DB handle for the requested mode."""
        mode_key = self._mode_key(mode)
        if self.has_init_failed(mode):
            return None

        cached = self._db_by_mode.get(mode_key)
        if cached is not None:
            return cached

        try:
            from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import (
                TradingSessionDB,
            )

            db = TradingSessionDB.for_paper() if self._is_paper_mode(mode) else TradingSessionDB.for_live()
        except ImportError:
            self._init_failed_by_mode[mode_key] = True
            return None
        except Exception as exc:  # noqa: BLE001
            self._init_failed_by_mode[mode_key] = True
            if log_error is not None:
                log_error(f"⚠️ Could not initialise session DB for dashboard reads: {exc}")
            return None

        self._db_by_mode[mode_key] = db
        return db

    @staticmethod
    def fetch_recent_trades(
        session_db: Any | None,
        *,
        limit: int,
        log_error: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """Fetch recent trades from an existing H05 DB handle."""
        if session_db is None:
            return []

        try:
            trades = session_db.get_recent_trades(limit=max(1, int(limit)))
        except Exception as exc:  # noqa: BLE001
            if log_error is not None:
                log_error(f"⚠️ Could not load recent trades: {exc}")
            return []

        return trades if isinstance(trades, list) else []

    @staticmethod
    def fetch_pnl_summary(
        session_db: Any | None,
        *,
        log_error: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Fetch date-bucketed P&L summary data from an existing H05 DB handle."""
        if session_db is None:
            return {}

        try:
            summary = session_db.get_pnl_summary()
        except Exception as exc:  # noqa: BLE001
            if log_error is not None:
                log_error(f"H05 get_pnl_summary skipped: {exc}")
            return {}

        return summary if isinstance(summary, dict) else {}
