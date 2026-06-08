#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovR_Runtime
Module: TradovR14_ExitMonitor.py
Purpose: Periodic sweep of open positions; emits close signals and orphan alerts

Author: TRADOV Trading System
Year Created: 2026
Last Updated: 2026-04-18 Time: 12:30:00

Module Description:
    ExitMonitor runs a 1-second background sweep over all positions held in
    P01 PortfolioManager.  For every open position it:

      1. Resolves the owning strategy from the registered strategy map.
      2. Calls ``strategy.check_exit(position)`` → ``ExitDecision | None``.
         - ``None``           → nothing to do
         - ``ExitDecision.CLOSE`` → emit STRATEGY_SIGNAL (action='close')
      3. If no owning strategy is found → emit RISK_VIOLATION (orphan alert).

    The monitor is started/stopped by SessionSupervisor and shares the
    singleton EventManager.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import re
import threading
import time
import uuid
from datetime import date, datetime
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from collections.abc import Callable  # noqa: F401
from zoneinfo import ZoneInfo

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovA_Core.TradovA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_SWEEP_INTERVAL_S: float = 1.0
_PENDING_GROUP_FLATTEN_TTL_S: float = 15.0
_ZERO_DTE_EOD_FORCE_CLOSE_HOUR: int = 15
_ZERO_DTE_EOD_FORCE_CLOSE_MINUTE: int = 55
_ZERO_DTE_EOD_FORCE_CLOSE_REASON: str = "zero_dte_eod_force_close"
_ZERO_DTE_EOD_FORCE_CLOSE_CUTOFF_LABEL: str = "15:55 ET"
_BUTTERFLY_FAMILY_STRATEGY_TOKENS: frozenset[str] = frozenset({
    "butterfly",
    "broken_wing_butterfly",
    "iron_butterfly",
})


# ==============================================================================
# TYPES
# ==============================================================================

class ExitDecision(StrEnum):
    """Possible decisions returned by ``strategy.check_exit(position)``."""
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class _PositionView:
    """Minimal position snapshot passed to ``check_exit``."""
    symbol: str
    strategy_id: str
    quantity: float
    cost_basis: float
    current_price: float
    unrealized_pnl: float
    raw: dict[str, Any]


# ==============================================================================
# EXIT MONITOR
# ==============================================================================

class ExitMonitor:
    """Periodic position sweep that enforces exit rules and detects orphans.

    Args:
        portfolio_manager: P01 PortfolioManager (or compatible object with a
            ``portfolio_positions`` dict attribute).
        strategy_map: Dict mapping ``strategy_id → strategy`` instance.
            Each strategy must implement
            ``check_exit(position: _PositionView) -> ExitDecision | None``.
        event_manager: Shared EventManager.  If ``None``, the singleton is
            used.
        portfolio_manager_provider: Optional callable used to lazily resolve a
            PortfolioManager after startup if one was not available initially.
        positions_provider: Optional callable returning authoritative runtime
            positions for the current sweep.
        sweep_interval_s: Seconds between sweeps.  Default 1.0.
    """

    def __init__(
        self,
        portfolio_manager: Any,
        strategy_map: dict[str, Any] | None = None,
        event_manager: Any = None,
        portfolio_manager_provider: Callable[[], Any | None] | None = None,
        positions_provider: Callable[[], dict[str, Any] | None] | None = None,
        sweep_interval_s: float = _DEFAULT_SWEEP_INTERVAL_S,
    ) -> None:
        self.portfolio_manager = portfolio_manager
        self.strategy_map: dict[str, Any] = {}
        self._strategy_aliases_by_primary: dict[str, set[str]] = {}
        self.em = event_manager or get_event_manager()
        self._portfolio_manager_provider = portfolio_manager_provider
        self._positions_provider = positions_provider
        self.sweep_interval_s = sweep_interval_s

        self.logger = TradovLogger.get_logger(__name__)
        self._running = False
        self._thread: threading.Thread | None = None

        # Track which orphan symbols we have already alerted on to avoid spam
        self._orphan_alerted: set[str] = set()
        # C5 (v18): protect _orphan_alerted against concurrent reads/writes
        # from the sweep thread vs. register_strategy/unregister_strategy.
        self._orphan_lock = threading.Lock()
        self._pending_group_flatten_lock = threading.Lock()
        self._pending_group_flatten_reservations: dict[str, float] = {}

        # Prometheus metrics — soft-import; silently disabled if unavailable.
        self._prom: Any = None
        try:
            from Tradov.TradovB_Broker.TradovB15_PrometheusMetrics import PrometheusMetrics
            self._prom = PrometheusMetrics.get_instance()
        except Exception:
            pass

        for registered_strategy_id, strategy in (strategy_map or {}).items():
            self.register_strategy(str(registered_strategy_id), strategy)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start the background sweep thread."""
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(
            target=self._sweep_loop,
            name="ExitMonitor",
            daemon=True,
        )
        self._thread.start()
        self.logger.debug("ExitMonitor started (interval=%.1fs)", self.sweep_interval_s)
        return True

    def stop(self) -> None:
        """Stop the background sweep thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.sweep_interval_s + 1.0)
        self._thread = None
        self.logger.info("ExitMonitor stopped")

    def register_strategy(self, strategy_id: str, strategy: Any) -> None:
        """Register (or update) a strategy so positions can be attributed."""
        primary_id = str(strategy_id or "").strip()
        if not primary_id:
            return

        self._clear_strategy_registration(primary_id)

        aliases = self._strategy_lookup_aliases(primary_id, strategy)
        for alias in aliases:
            self.strategy_map[alias] = strategy
        self._strategy_aliases_by_primary[primary_id] = aliases

    def unregister_strategy(self, strategy_id: str) -> None:
        """Remove a strategy from the map (positions become orphans)."""
        primary_id = str(strategy_id or "").strip()
        aliases = self._clear_strategy_registration(primary_id)
        # Reset orphan alert cache so a fresh alert fires
        # C5 (v18): acquire lock before mutating the shared set.
        with self._orphan_lock:
            for alias in aliases or ({primary_id} if primary_id else set()):
                self._orphan_alerted.discard(alias)

    @staticmethod
    def _normalize_strategy_token(value: Any) -> str:
        """Return a semantic strategy token suitable for cross-component matching."""
        text = str(value or "").strip()
        if not text:
            return ""

        text = re.sub(r"_[0-9a-f]{8,}$", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<!^)(?=[A-Z])", "_", text)
        text = re.sub(r"[\s\-]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        text = re.sub(r"(_adapter|_strategy)+$", "", text, flags=re.IGNORECASE)
        return text.lower()

    def _strategy_lookup_aliases(
        self,
        primary_id: str,
        strategy: Any,
    ) -> set[str]:
        """Return all lookup keys that should resolve to the same strategy."""
        aliases: set[str] = set()
        candidates = [
            primary_id,
            getattr(strategy, "strategy_id", None),
            getattr(strategy, "strategy_type", None),
            getattr(strategy, "name", None),
            getattr(getattr(strategy, "__class__", None), "__name__", None),
        ]

        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            aliases.add(text)
            normalized = self._normalize_strategy_token(text)
            if normalized:
                aliases.add(normalized)

        aliases.add(primary_id)
        return aliases

    def _clear_strategy_registration(self, primary_id: str) -> set[str]:
        """Remove a strategy's primary and alias keys from the lookup map."""
        aliases = self._strategy_aliases_by_primary.pop(primary_id, set())
        aliases.add(primary_id)
        for alias in aliases:
            self.strategy_map.pop(alias, None)
        return aliases

    def _resolve_strategy(self, strategy_id: str) -> Any | None:
        """Resolve a strategy by exact key or normalized semantic alias."""
        text = str(strategy_id or "").strip()
        if not text:
            return None

        strategy = self.strategy_map.get(text)
        if strategy is not None:
            return strategy

        normalized = self._normalize_strategy_token(text)
        if normalized and normalized != text:
            return self.strategy_map.get(normalized)
        return None

    def _reserve_pending_group_flatten(self, strategy_id: str) -> None:
        """Suppress duplicate exit checks while a grouped carryover flatten is in flight."""
        strategy_token = self._normalize_strategy_token(strategy_id)
        if not strategy_token:
            return

        with self._pending_group_flatten_lock:
            self._pending_group_flatten_reservations[strategy_token] = (
                time.monotonic() + _PENDING_GROUP_FLATTEN_TTL_S
            )

    def _reserve_pending_symbol_flatten(self, symbols: list[str]) -> None:
        """Suppress duplicate symbol-level flatten requests while one is in flight."""
        reservation_until = time.monotonic() + _PENDING_GROUP_FLATTEN_TTL_S
        with self._pending_group_flatten_lock:
            for symbol in symbols:
                normalized_symbol = str(symbol or "").strip().upper()
                if normalized_symbol:
                    self._pending_group_flatten_reservations[
                        f"symbol::{normalized_symbol}"
                    ] = reservation_until

    def _has_pending_group_flatten(self, view: _PositionView) -> bool:
        """Return True when a grouped flatten is already in flight."""
        strategy_token = self._normalize_strategy_token(view.strategy_id)
        if not strategy_token:
            return False

        now_monotonic = time.monotonic()
        with self._pending_group_flatten_lock:
            expiry = self._pending_group_flatten_reservations.get(strategy_token)
            if expiry is None:
                return False
            if expiry <= now_monotonic:
                self._pending_group_flatten_reservations.pop(strategy_token, None)
                return False
            return True

    def _has_pending_symbol_flatten(self, symbol: str) -> bool:
        """Return True when a targeted symbol flatten is already in flight."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return False

        reservation_key = f"symbol::{normalized_symbol}"
        now_monotonic = time.monotonic()
        with self._pending_group_flatten_lock:
            expiry = self._pending_group_flatten_reservations.get(reservation_key)
            if expiry is None:
                return False
            if expiry <= now_monotonic:
                self._pending_group_flatten_reservations.pop(reservation_key, None)
                return False
            return True

    def _should_flatten_orphaned_paper_strategy(
        self,
        strategy_id: str,
        view: _PositionView,
    ) -> bool:
        """Return True when a restored paper carryover should be closed as a group."""
        raw = view.raw if isinstance(view.raw, dict) else {}
        if not self._is_hydrated_carryover_position(raw):
            return False

        strategy_token = self._normalize_strategy_token(strategy_id)
        if strategy_token == "iron_condor":
            symbol = str(view.symbol or raw.get("symbol") or "").strip().upper()
            return bool(symbol) and len(symbol) >= 15 and ("C" in symbol or "P" in symbol)

        if strategy_token in {
            "butterfly",
            "broken_wing_butterfly",
            "iron_butterfly",
        }:
            expiration = self._resolve_position_expiration(raw, view.symbol)
            if expiration is None:
                return False
            return expiration <= self._now_et().date()

        return False

    def _should_ignore_expected_paper_carryover_orphan(
        self,
        strategy_id: str,
        view: _PositionView,
    ) -> bool:
        """Return True for valid butterfly-family carryovers restored from H05.

        Butterfly-family paper positions are expected to persist across restart
        without a live strategy instance. Those carryovers should remain visible
        and duplicate-entry-protected, but should not raise startup orphan alerts.
        """
        raw = view.raw if isinstance(view.raw, dict) else {}
        if self._is_hydrated_active_session_position(raw):
            return True

        if not self._is_hydrated_carryover_position(raw):
            return False

        strategy_token = self._normalize_strategy_token(strategy_id)
        if strategy_token not in {
            "butterfly",
            "broken_wing_butterfly",
            "iron_butterfly",
        }:
            return False

        expiration = self._resolve_position_expiration(raw, view.symbol)
        if expiration is None:
            return True

        return expiration > self._now_et().date()

    @staticmethod
    def _resolve_paper_open_origin(raw: dict[str, Any]) -> str:
        """Return the normalized paper restart origin label when present."""
        return str(raw.get("_paper_open_origin") or "").strip().lower()

    def _is_hydrated_active_session_position(self, raw: dict[str, Any]) -> bool:
        """Return True for paper positions restored from the current active session."""
        if str(raw.get("position_source") or "").strip() != "session_db_hydration":
            return False
        return self._resolve_paper_open_origin(raw) == "active_session"

    def _is_hydrated_carryover_position(self, raw: dict[str, Any]) -> bool:
        """Return True for paper restart rows that represent true carryover.

        Legacy hydration rows may not have `_paper_open_origin`; keep treating
        those as carryover so older persisted data preserves prior behavior.
        """
        if str(raw.get("position_source") or "").strip() != "session_db_hydration":
            return False

        origin = self._resolve_paper_open_origin(raw)
        if origin:
            return origin == "carryover"
        return True

    @staticmethod
    def _now_et() -> datetime:
        """Return the current time in US/Eastern."""
        return datetime.now(ZoneInfo("America/New_York"))

    @staticmethod
    def _resolve_position_expiration(raw: dict[str, Any], symbol: str) -> date | None:
        """Best-effort expiration date from persisted fields or OCC symbol."""
        expiration_text = str(
            raw.get("expiration")
            or raw.get("expiration_date")
            or ""
        ).strip()
        if expiration_text:
            for fmt in ("%Y-%m-%d", "%Y%m%d"):
                try:
                    return datetime.strptime(expiration_text, fmt).date()
                except ValueError:
                    continue

        normalized_symbol = str(symbol or "").strip().upper()
        match = re.match(r"^[A-Z]{1,6}(\d{6})[CP]\d{8}$", normalized_symbol)
        if match is None:
            return None

        try:
            return datetime.strptime(match.group(1), "%y%m%d").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_occ_option_contract(symbol: str) -> dict[str, Any]:
        """Parse an OCC option symbol into underlying, expiration, strike, and type."""
        normalized = str(symbol or "").strip().upper()
        match = re.match(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", normalized)
        if match is None:
            return {}

        try:
            expiration = datetime.strptime(match.group(2), "%y%m%d").date().isoformat()
        except ValueError:
            expiration = ""

        return {
            "underlying": match.group(1),
            "expiration": expiration,
            "option_type": "call" if match.group(3) == "C" else "put",
            "strike": int(match.group(4)) / 1000.0,
        }

    def _build_position_view(self, symbol: str, raw_pos: Any) -> _PositionView:
        """Normalize one raw position row into the ExitMonitor view shape."""
        strategy_id: str = (
            getattr(raw_pos, "strategy_id", None)
            or (raw_pos.get("strategy_id") if isinstance(raw_pos, dict) else None)
            or (raw_pos.get("strategy") if isinstance(raw_pos, dict) else None)
            or (raw_pos.get("strategy_name") if isinstance(raw_pos, dict) else None)
            or ""
        )

        return _PositionView(
            symbol=symbol,
            strategy_id=strategy_id,
            quantity=float(
                getattr(raw_pos, "quantity", None)
                or (raw_pos.get("quantity", 0) if isinstance(raw_pos, dict) else 0)
            ),
            cost_basis=float(
                getattr(raw_pos, "cost_basis", None)
                or (raw_pos.get("cost_basis", 0.0) if isinstance(raw_pos, dict) else 0.0)
                or (raw_pos.get("entry_price", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            current_price=float(
                getattr(raw_pos, "current_price", None)
                or (raw_pos.get("current_price", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            unrealized_pnl=float(
                getattr(raw_pos, "unrealized_pnl", None)
                or (raw_pos.get("unrealized_pnl", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            raw=raw_pos if isinstance(raw_pos, dict) else {},
        )

    def _should_force_flatten_zero_dte_option(
        self,
        view: _PositionView,
        *,
        now_et: datetime | None = None,
    ) -> bool:
        """Return True when a same-day option must be force-flattened at 15:55 ET."""
        if abs(float(view.quantity or 0.0)) <= 0.0:
            return False

        if not self._parse_occ_option_contract(view.symbol):
            return False

        current_time = now_et or self._now_et()
        cutoff = current_time.replace(
            hour=_ZERO_DTE_EOD_FORCE_CLOSE_HOUR,
            minute=_ZERO_DTE_EOD_FORCE_CLOSE_MINUTE,
            second=0,
            microsecond=0,
        )
        if current_time < cutoff:
            return False

        expiration = self._resolve_position_expiration(view.raw, view.symbol)
        if expiration is not None:
            return expiration <= current_time.date()

        raw_days_to_expiry = view.raw.get("days_to_expiry") if isinstance(view.raw, dict) else None
        try:
            return int(raw_days_to_expiry) <= 0
        except (TypeError, ValueError):
            return False

    def _collect_zero_dte_force_flatten_symbols(
        self,
        positions: dict[str, Any],
    ) -> list[str]:
        """Return same-day option symbols that must be force-flattened now."""
        if not positions:
            return []

        now_et = self._now_et()
        target_symbols: list[str] = []
        for symbol, raw_pos in positions.items():
            view = self._build_position_view(str(symbol), raw_pos)
            if self._has_pending_group_flatten(view):
                continue
            if self._has_pending_symbol_flatten(view.symbol):
                continue
            if self._should_force_flatten_zero_dte_option(view, now_et=now_et):
                target_symbols.append(view.symbol)
        return target_symbols

    def _resolve_butterfly_family_group_key(
        self,
        symbol: str,
        raw_pos: dict[str, Any],
    ) -> tuple[str, str, str, str] | None:
        """Return a stable grouping key for butterfly-family option legs.

        Hydrated paper carryovers still need grouped exit evaluation when a live
        strategy instance is registered; if no strategy resolves, the orphan
        cleanup path in ``_check_position`` remains responsible for them.
        """

        strategy_id = str(
            raw_pos.get("strategy_id")
            or raw_pos.get("strategy")
            or raw_pos.get("strategy_name")
            or ""
        ).strip()
        strategy_token = self._normalize_strategy_token(strategy_id)
        if strategy_token not in _BUTTERFLY_FAMILY_STRATEGY_TOKENS:
            return None

        contract = self._parse_occ_option_contract(symbol)
        if not contract:
            return None

        underlying = str(
            raw_pos.get("underlying_symbol")
            or contract.get("underlying")
            or ""
        ).strip().upper()
        expiration = str(
            raw_pos.get("expiration")
            or raw_pos.get("expiration_date")
            or contract.get("expiration")
            or ""
        ).strip()
        if not underlying or not expiration:
            return None

        return (
            strategy_id or strategy_token,
            strategy_token,
            underlying,
            expiration,
        )

    def _build_butterfly_family_group_data(
        self,
        strategy_token: str,
        views: list[_PositionView],
    ) -> dict[str, Any] | None:
        """Build group-level exit inputs for butterfly-family paper structures."""
        expected_count = 4 if strategy_token == "iron_butterfly" else 3
        if len(views) != expected_count:
            return None

        leg_rows: list[dict[str, Any]] = []
        for view in views:
            contract = self._parse_occ_option_contract(view.symbol)
            if not contract:
                return None
            leg_rows.append(
                {
                    "view": view,
                    "symbol": view.symbol,
                    "quantity": int(view.quantity or 0),
                    "entry_price": float(view.cost_basis or 0.0),
                    "unrealized_pnl": float(view.unrealized_pnl or 0.0),
                    "strike": float(
                        view.raw.get("strike")
                        or contract.get("strike")
                        or 0.0
                    ),
                    "option_type": str(
                        view.raw.get("option_type")
                        or contract.get("option_type")
                        or ""
                    ).strip().lower(),
                    "expiration": str(
                        view.raw.get("expiration")
                        or view.raw.get("expiration_date")
                        or contract.get("expiration")
                        or ""
                    ).strip(),
                }
            )

        if len({row["symbol"] for row in leg_rows}) != expected_count:
            return None

        total_unrealized_pnl = sum(row["unrealized_pnl"] for row in leg_rows)
        entry_notional = abs(
            sum(row["quantity"] * row["entry_price"] * 100.0 for row in leg_rows)
        )
        pnl_percent = (total_unrealized_pnl / entry_notional) if entry_notional > 0.0 else 0.0
        expiration = self._resolve_position_expiration(views[0].raw, views[0].symbol)
        if expiration is None:
            return None

        is_hydrated_carryover = all(
            self._is_hydrated_carryover_position(view.raw)
            for view in views
        )

        group_data: dict[str, Any] = {
            "symbols": [row["symbol"] for row in leg_rows],
            "entry_notional": entry_notional,
            "unrealized_pnl": total_unrealized_pnl,
            "pnl_percent": pnl_percent,
            "days_to_expiry": max(0, (expiration - self._now_et().date()).days),
            "days_held": 0,
            "position_delta": 0.0,
            "is_hydrated_carryover": is_hydrated_carryover,
        }

        if strategy_token in {"butterfly", "broken_wing_butterfly"}:
            option_types = {row["option_type"] for row in leg_rows}
            if len(option_types) != 1:
                return None

            long_rows = [row for row in leg_rows if row["quantity"] > 0]
            short_rows = [row for row in leg_rows if row["quantity"] < 0]
            if len(long_rows) != 2 or len(short_rows) != 1:
                return None

            body_row = short_rows[0]
            body_qty = abs(body_row["quantity"])
            if body_qty <= 0 or body_qty % 2 != 0:
                return None
            spread_qty = body_qty // 2
            if any(abs(row["quantity"]) != spread_qty for row in long_rows):
                return None

            ascending = sorted(leg_rows, key=lambda row: row["strike"])
            lower_row, middle_row, upper_row = ascending
            if middle_row is not body_row:
                return None

            group_data.update(
                {
                    "quantity": spread_qty,
                    "body_strike": middle_row["strike"],
                    "lower_strike": lower_row["strike"],
                    "upper_strike": upper_row["strike"],
                    "option_type": middle_row["option_type"],
                }
            )
            return group_data

        grouped: dict[str, list[dict[str, Any]]] = {"put": [], "call": []}
        for row in leg_rows:
            option_type = row["option_type"]
            if option_type not in grouped:
                return None
            grouped[option_type].append(row)

        if len(grouped["put"]) != 2 or len(grouped["call"]) != 2:
            return None

        long_put = next((row for row in grouped["put"] if row["quantity"] > 0), None)
        short_put = next((row for row in grouped["put"] if row["quantity"] < 0), None)
        short_call = next((row for row in grouped["call"] if row["quantity"] < 0), None)
        long_call = next((row for row in grouped["call"] if row["quantity"] > 0), None)
        if any(row is None for row in (long_put, short_put, short_call, long_call)):
            return None

        spread_qty = abs(int(short_put["quantity"]))
        if spread_qty <= 0:
            return None
        if any(abs(int(row["quantity"])) != spread_qty for row in leg_rows):
            return None
        if short_put["strike"] != short_call["strike"]:
            return None

        group_data.update(
            {
                "quantity": spread_qty,
                "body_strike": short_put["strike"],
                "atm_strike": short_put["strike"],
                "long_put_strike": long_put["strike"],
                "long_call_strike": long_call["strike"],
            }
        )
        return group_data

    def _should_close_butterfly_family_group(
        self,
        strategy_token: str,
        strategy: Any,
        group_data: dict[str, Any],
    ) -> str | None:
        """Return the flatten reason for a butterfly-family group when it should close."""
        if (
            bool(group_data.get("is_hydrated_carryover"))
            and int(group_data.get("days_to_expiry", 0) or 0) <= 0
            and float(group_data.get("unrealized_pnl", 0.0) or 0.0) > 0.0
        ):
            return "pre_carryover_profit_take"

        evaluator = None
        if strategy_token == "broken_wing_butterfly":
            evaluator = getattr(strategy, "should_close_broken_wing_butterfly", None)
        elif strategy_token == "iron_butterfly":
            evaluator = getattr(strategy, "should_close_iron_butterfly", None)
        elif strategy_token == "butterfly":
            evaluator = getattr(strategy, "should_close_butterfly", None)

        if not callable(evaluator):
            return None

        try:
            should_close, reason = evaluator(group_data)
        except Exception as exc:
            self.logger.warning(
                "butterfly-family group exit evaluation raised for %s: %s",
                strategy_token,
                exc,
            )
            return None

        if not should_close:
            return None
        return str(reason or "exit_monitor_group_close")

    def _emit_symbols_flatten_request(
        self,
        symbols: list[str],
        *,
        reason: str,
    ) -> None:
        """Request a runtime close of a specific set of open symbols."""
        target_symbols = [
            str(symbol).strip() for symbol in symbols if str(symbol or "").strip()
        ]
        if not target_symbols:
            return

        self.logger.info(
            "ExitMonitor: requesting symbols flatten for %s (reason=%s)",
            target_symbols,
            reason,
        )
        self.em.emit(
            event_type=EventType.FLATTEN_REQUEST,
            data={
                "type": "symbols_flatten",
                "reason": reason,
                "symbols": target_symbols,
            },
            source="ExitMonitor",
        )

    def _emit_zero_dte_force_close_risk_alert(self, symbols: list[str]) -> None:
        """Emit an operator-visible alert when 0DTE paper options remain open after cutoff."""
        target_symbols = [
            str(symbol).strip() for symbol in symbols if str(symbol or "").strip()
        ]
        if not target_symbols:
            return

        symbol_count = len(target_symbols)
        risk_alert_event_type = getattr(EventType, "RISK_ALERT", EventType.ALERT)
        message = (
            f"0DTE paper option{'s' if symbol_count != 1 else ''} still open after "
            f"{_ZERO_DTE_EOD_FORCE_CLOSE_CUTOFF_LABEL} ({symbol_count})"
        )

        try:
            self.em.emit(
                event_type=risk_alert_event_type,
                data={
                    "severity": "warning",
                    "reason": _ZERO_DTE_EOD_FORCE_CLOSE_REASON,
                    "message": message,
                    "detail": ", ".join(target_symbols),
                    "symbols": target_symbols,
                    "cutoff_et": _ZERO_DTE_EOD_FORCE_CLOSE_CUTOFF_LABEL,
                },
                source="ExitMonitor",
            )
        except Exception as exc:
            self.logger.warning(
                "ExitMonitor: failed to emit zero-DTE cutoff risk alert for %s: %s",
                target_symbols,
                exc,
            )

    def _handle_butterfly_family_groups(
        self,
        positions: dict[str, Any],
    ) -> set[str]:
        """Evaluate complete active butterfly-family groups before per-leg checks."""
        grouped_views: dict[tuple[str, str, str, str], list[_PositionView]] = {}
        for symbol, raw_pos in positions.items():
            if not isinstance(raw_pos, dict):
                continue
            group_key = self._resolve_butterfly_family_group_key(str(symbol), raw_pos)
            if group_key is None:
                continue
            grouped_views.setdefault(group_key, []).append(
                self._build_position_view(str(symbol), raw_pos)
            )

        handled_symbols: set[str] = set()
        for (_strategy_id, strategy_token, _underlying, _expiration), views in grouped_views.items():
            strategy = self._resolve_strategy(views[0].strategy_id)
            if strategy is None:
                continue

            group_data = self._build_butterfly_family_group_data(strategy_token, views)
            if group_data is None:
                continue

            handled_symbols.update(group_data.get("symbols", []))
            if any(self._has_pending_group_flatten(view) for view in views):
                continue

            reason = self._should_close_butterfly_family_group(
                strategy_token,
                strategy,
                group_data,
            )
            if reason is None:
                continue

            self._reserve_pending_group_flatten(views[0].strategy_id)
            self._emit_symbols_flatten_request(
                list(group_data.get("symbols", [])),
                reason=reason,
            )

        return handled_symbols

    def _sweep_positions_snapshot(self, positions: dict[str, Any]) -> None:
        """Sweep one normalized position snapshot."""
        handled_symbols: set[str] = {
            str(symbol)
            for symbol in positions
            if self._has_pending_symbol_flatten(str(symbol))
        }

        zero_dte_symbols = self._collect_zero_dte_force_flatten_symbols(
            {
                symbol: raw_pos
                for symbol, raw_pos in positions.items()
                if str(symbol) not in handled_symbols
            }
        )
        if zero_dte_symbols:
            self._reserve_pending_symbol_flatten(zero_dte_symbols)
            self._emit_zero_dte_force_close_risk_alert(zero_dte_symbols)
            self._emit_symbols_flatten_request(
                zero_dte_symbols,
                reason=_ZERO_DTE_EOD_FORCE_CLOSE_REASON,
            )
            handled_symbols.update(zero_dte_symbols)

        remaining_positions = {
            symbol: raw_pos
            for symbol, raw_pos in positions.items()
            if str(symbol) not in handled_symbols
        }
        handled_symbols.update(self._handle_butterfly_family_groups(remaining_positions))
        for symbol, raw_pos in list(remaining_positions.items()):
            if str(symbol) in handled_symbols:
                continue
            try:
                self._check_position(symbol, raw_pos)
            except Exception as exc:
                self.logger.warning(
                    "ExitMonitor: error processing position %s: %s", symbol, exc
                )

    def _emit_strategy_group_flatten_request(
        self,
        strategy_id: str,
        symbol: str,
    ) -> None:
        """Request a runtime close of all positions associated with a strategy."""
        self._reserve_pending_group_flatten(strategy_id)
        self.logger.warning(
            "ExitMonitor: requesting grouped paper cleanup for orphan carryover %s "
            "(strategy_id=%r)",
            symbol,
            strategy_id,
        )
        self.em.emit(
            event_type=EventType.FLATTEN_REQUEST,
            data={
                "type": "strategy_group_flatten",
                "reason": "paper_orphan_carryover_strategy",
                "strategy_id": strategy_id,
            },
            source="ExitMonitor",
        )

    # ------------------------------------------------------------------
    # Internal sweep
    # ------------------------------------------------------------------

    def _sweep_loop(self) -> None:
        """Background thread: sweep positions every ``sweep_interval_s``."""
        while self._running:
            try:
                self._sweep_once()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("ExitMonitor sweep error: %s", exc, exc_info=True)
            time.sleep(self.sweep_interval_s)

    def _sweep_once(self) -> None:
        """Single sweep pass — called from the background thread."""
        positions: dict[str, Any] | None = None
        if self._positions_provider is not None:
            try:
                provided_positions = self._positions_provider()
            except Exception as exc:
                self.logger.warning(
                    "ExitMonitor: could not resolve authoritative positions: %s", exc
                )
                provided_positions = None

            if isinstance(provided_positions, dict):
                positions = provided_positions
            elif provided_positions is not None:
                self.logger.warning(
                    "ExitMonitor: authoritative positions provider returned %s; "
                    "expected dict or None",
                    type(provided_positions).__name__,
                )

        if positions is not None:
            if not positions:
                return

            self._sweep_positions_snapshot(positions)
            return

        if (
            self.portfolio_manager is None
            and self._portfolio_manager_provider is not None
        ):
            try:
                portfolio_manager = self._portfolio_manager_provider()
            except Exception as exc:
                self.logger.warning(
                    "ExitMonitor: could not resolve PortfolioManager lazily: %s",
                    exc,
                )
                return

            if portfolio_manager is None:
                return

            self.portfolio_manager = portfolio_manager

        try:
            positions: dict[str, Any] = getattr(
                self.portfolio_manager, "portfolio_positions", {}
            )
        except Exception as exc:
            self.logger.warning("Could not read portfolio_positions: %s", exc)
            return

        if not positions:
            return

        self._sweep_positions_snapshot(positions)

    def _check_position(self, symbol: str, raw_pos: Any) -> None:
        """Evaluate a single position for exit conditions."""
        view = self._build_position_view(symbol, raw_pos)
        strategy_id = view.strategy_id

        if self._has_pending_symbol_flatten(view.symbol):
            return

        if self._has_pending_group_flatten(view):
            return

        strategy = self._resolve_strategy(strategy_id)

        if strategy is None:
            if self._should_ignore_expected_paper_carryover_orphan(strategy_id, view):
                return
            self._handle_orphan(symbol, strategy_id, view)
            return

        # Reset orphan alert if the strategy reappeared
        # C5 (v18): acquire lock before mutating the shared set.
        with self._orphan_lock:
            self._orphan_alerted.discard(strategy_id)

        decision: ExitDecision | None = None
        try:
            raw_decision = strategy.check_exit(view)
            if raw_decision is not None:
                decision = ExitDecision(raw_decision) if not isinstance(raw_decision, ExitDecision) else raw_decision  # noqa: E501
        except AttributeError:
            # Strategy doesn't implement check_exit — skip silently
            return
        except Exception as exc:
            self.logger.warning(
                "strategy.check_exit(%s) raised: %s", symbol, exc
            )
            return

        if decision == ExitDecision.CLOSE:
            self._emit_close_signal(view, strategy_id)

    def _handle_orphan(self, symbol: str, strategy_id: str, view: _PositionView) -> None:
        """Alert once per strategy_id when a position has no owning strategy."""
        alert_key = strategy_id or symbol
        # C5 (v18): acquire lock for both the membership test and the add so
        # no two threads can race through the guard simultaneously.
        with self._orphan_lock:
            if alert_key in self._orphan_alerted:
                return
            self._orphan_alerted.add(alert_key)
        self.logger.warning(
            "ExitMonitor: ORPHAN position %s (strategy_id=%r, qty=%.0f)",
            symbol, strategy_id, view.quantity,
        )
        self._inc_counter("tradov_orphans_detected_total")
        self.em.emit(
            event_type=EventType.RISK_VIOLATION,
            data={
                "type": "ORPHAN_POSITION",
                "symbol": symbol,
                "strategy_id": strategy_id,
                "quantity": view.quantity,
                "unrealized_pnl": view.unrealized_pnl,
                "message": (
                    f"Position {symbol} has no registered owning strategy "
                    f"(strategy_id={strategy_id!r})"
                ),
            },
            source="ExitMonitor",
        )
        if self._should_flatten_orphaned_paper_strategy(strategy_id, view):
            self._emit_strategy_group_flatten_request(strategy_id, symbol)

    def _emit_close_signal(self, view: _PositionView, strategy_id: str) -> None:
        """Emit a STRATEGY_SIGNAL to close a position."""
        signal_id = f"exit-{view.symbol}-{uuid.uuid4().hex[:8]}"
        self.logger.info(
            "ExitMonitor: closing position %s (strategy=%s, pnl=%.2f)",
            view.symbol, strategy_id, view.unrealized_pnl,
        )
        # Resolve close direction from position sign so downstream consumers
        # (R04 _broker_submit) do not default to SELL unconditionally.
        # Long position (qty > 0) → sell-to-close; Short (qty < 0) → buy-to-close.
        close_side = "sell" if (view.quantity or 0) > 0 else "buy"
        self.em.emit(
            event_type=EventType.STRATEGY_SIGNAL,
            data={
                "signal_id": signal_id,
                "action": "close",
                "side": close_side,
                "symbol": view.symbol,
                "strategy_id": strategy_id,
                "quantity": abs(view.quantity),
                "reason": "exit_monitor",
                "unrealized_pnl": view.unrealized_pnl,
            },
            source="ExitMonitor",
        )
        self._inc_counter("tradov_exits_emitted_total")

    def _inc_counter(self, name: str) -> None:
        if self._prom:
            try:
                self._prom.increment(name)
            except Exception:
                pass


# ==============================================================================
# FACTORY
# ==============================================================================

def create_exit_monitor(
    portfolio_manager: Any,
    strategy_map: dict[str, Any] | None = None,
    event_manager: Any = None,
    portfolio_manager_provider: Callable[[], Any | None] | None = None,
    positions_provider: Callable[[], dict[str, Any] | None] | None = None,
    sweep_interval_s: float = _DEFAULT_SWEEP_INTERVAL_S,
) -> ExitMonitor:
    """Factory function for :class:`ExitMonitor`.

    Args:
        portfolio_manager: P01 PortfolioManager or compatible object.
        strategy_map: Optional pre-populated strategy map.
        event_manager: Shared EventManager (uses singleton if omitted).
        portfolio_manager_provider: Optional callable used to lazily resolve a
            PortfolioManager after startup.
        positions_provider: Optional callable returning authoritative runtime
            positions. When it returns a dict, that snapshot takes precedence
            over the portfolio-manager view for the current sweep.
        sweep_interval_s: Seconds between position sweeps.

    Returns:
        A new :class:`ExitMonitor` instance (not yet started).
    """
    monitor = ExitMonitor(
        portfolio_manager=portfolio_manager,
        strategy_map=strategy_map,
        event_manager=event_manager,
        portfolio_manager_provider=portfolio_manager_provider,
        positions_provider=positions_provider,
        sweep_interval_s=sweep_interval_s,
    )
    TradovLogger.get_logger(__name__).debug(
        "ExitMonitor created (interval=%.1fs)", sweep_interval_s
    )
    return monitor
