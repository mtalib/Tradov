#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovR_Runtime
Module: TradovR08_PaperTradingQtWorker.py
Purpose: Qt-threaded paper trading worker (extracted from TradovG05)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-15

Module Description:
    Background QThread worker that runs a simple paper trading loop against
    live Tradier market data. Relocated from TradovG05_TradingDashboard.py
    per audit §4 so the dashboard layer no longer owns trading-engine logic.
    Behavior is preserved exactly — this is a mechanical move, not a rewrite.

    The deeper goal of wrapping TradovR02_PaperEngine with a Qt adapter is
    deferred until R02's API is aligned with this worker's needs (R02 uses
    plain threading and different dataclasses; converging the two requires
    contract negotiation beyond a GUI-scoped extraction).
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import os
import time
from datetime import datetime, UTC
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, Signal, Slot

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovB_Broker.TradovB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
    build_option_symbol,  # noqa: F401
)
from Tradov.TradovD_Strategies.TradovD00_StrategyConstants import (
    StrategyLifecycleState,
)
from Tradov.TradovU_Utilities.TradovU03_DateTimeUtils import TradingHours

# Optional pivot mean-reversion signal (S08). When the module is missing we
# leave PIVOT_MR_SIGNAL_AVAILABLE = False and the worker silently falls back
# to the regime-bias path. Keeps the runtime resilient to partial deploys.
try:
    from Tradov.TradovS_Signals.TradovS08_PivotMeanReversionSignal import (
        PivotMeanReversionSignal,
        PivotMRInputs,
        PivotMRSignal,
        PivotDirection,
    )
    PIVOT_MR_SIGNAL_AVAILABLE = True
except ImportError:  # noqa: BLE001
    PivotMeanReversionSignal = None  # type: ignore[assignment]
    PivotMRInputs = None  # type: ignore[assignment]
    PivotMRSignal = None  # type: ignore[assignment]
    PivotDirection = None  # type: ignore[assignment]
    PIVOT_MR_SIGNAL_AVAILABLE = False


class PaperTradingQtWorker(QObject):
    """Runs paper trading with real Tradier market data in a background QThread.

    Polls underlying quotes from Tradier live endpoint every poll_interval seconds,
    maintains a price history buffer, runs a simple momentum strategy, and
    tracks paper positions and P&L.  Emits Qt signals for the dashboard to
    display status, positions, and metrics in real time.
    """

    status_update = Signal(str)       # log messages for the system log
    position_update = Signal(dict)    # current positions + account state
    metrics_update = Signal(dict)     # P&L metrics for the paper P&L widget
    error = Signal(str)               # error messages
    stopped = Signal()                # emitted when the loop exits
    connection_ready = Signal(bool)   # True when Tradier connection verified
    pivot_signal_updated = Signal(dict)  # S08 pivot mean-reversion state for left panel

    POLL_INTERVAL = 30
    HISTORY_SIZE = 100
    MOMENTUM_THRESHOLD = 0.0002  # 0.02% — achievable in normal intraday index trading
    SHORT_MA_WINDOW = 5     # 5 x 30s = 2.5 min
    LONG_MA_WINDOW = 20     # 20 x 30s = 10 min
    UNDERLYING_SYMBOL = (
        os.environ.get("TRADOV_UNDERLYING_SYMBOL", "SPX").strip().upper() or "SPX"
    )

    # Phase 2 IV-rank gating (see 2026-04-17 overview v6).
    #
    # With only in-memory samples we can't compute a true 252-session IV rank,
    # so we do a two-tier gate: absolute IV floor first, then rolling percentile
    # once we have at least MIN_IV_HISTORY observations. Both thresholds are
    # tunable via env.
    IV_HISTORY_MAXLEN = 1024   # ≈ 1 trading week of 30s polls (390 bars/day × 5)
    MIN_IV_HISTORY = 60        # ≈ 30 minutes of samples before rank is trusted

    # Phase 2 commission model. Tradier Pro ($10/mo) charges $0 per contract
    # on equity & ETF options — SPX/SPXW paper paths default to zero here.
    # zero. Overridable via TRADOV_COMMISSION_PER_CONTRACT for what-if tests
    # or to model a future tier change without a code edit.
    DEFAULT_COMMISSION_PER_CONTRACT = 0.0
    SPREAD_LEG_COUNT = 2  # bull-put spread = 1 short + 1 long = 2 legs

    # Persistent state file: survives dashboard restarts so open positions and
    # account balance are restored on the next session.  Stored next to the
    # live market data files so a single `market_data/` directory cleanup wipes
    # everything consistently.
    STATE_FILE = (
        Path.home() / "Projects/Tradov/market_data/paper_trading_state.json"
    )

    # Kelly sizing window: number of recent closed-spread P&Ls retained for
    # win-rate / payoff-ratio estimation. ~30 trades is the smallest window
    # that produces a stable Kelly fraction without lagging regime changes.
    KELLY_HISTORY_MAX = 100
    KELLY_MIN_SAMPLES = 20

    # Audit log retention — closed-trade rows kept in memory for the Trade
    # Audit dialog. Each row is ~500 bytes so 500 entries ≈ 250 KB.
    CLOSED_TRADES_MAX = 500

    # Armed-candidate TTL: how long (seconds) a blocked setup is held before
    # being discarded as stale. 120 s = 2 minutes; after that the market
    # conditions that produced the signal are assumed to have changed.
    ARMED_CANDIDATE_TTL_SECONDS = 120

    def __init__(self, initial_capital: float = 100_000.0):
        super().__init__()
        self._running = False
        self._initial_capital = initial_capital

        self._cash = initial_capital
        self._position_qty = 0
        self._position_avg_price = 0.0
        self._total_commissions = 0.0
        self._trades_executed = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._total_realized_pnl = 0.0
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0

        self._price_history: list[float] = []
        self._session_start_equity = initial_capital  # for daily loss check

        self._client = None
        self._risk_params: dict = {}  # populated by set_risk_params() before/during run

        # Phase 1 wiring (see 2026-04-17 overview v6): real E-series risk
        # validation + S07 regime metrics. Both are injected from the
        # dashboard before run() is invoked. When absent, the worker falls
        # back to the local _get_risk_limit() checks only.
        self._risk_manager = None      # TradovE01_RiskManager | None
        self._regime_metrics: dict = {}  # Latest S07 metrics snapshot

        # Phase 2: open bull-put credit spreads opened in paper mode when
        # TRADOV_OPTIONS_LIVE_PAPER=1. Each entry is a dict:
        #   {"id", "expiration", "short_strike", "long_strike",
        #    "option_type", "credit", "qty", "opened_at",
        #    "wing_width", "max_loss_per_contract"}
        self._open_spreads: list[dict] = []
        self._spread_seq: int = 0  # monotonic id for spreads

        # Consecutive-loss cooldown: after N back-to-back losing closes the
        # worker pauses NEW entries for a wall-clock interval. Exits (TP /
        # stop-loss / DTE force-close) are always permitted. Controls:
        #   TRADOV_LOSS_COOLDOWN_COUNT   (default 3)  0 disables feature
        #   TRADOV_LOSS_COOLDOWN_SECONDS (default 1800 = 30 min)
        self._consecutive_losses: int = 0
        self._cooldown_until_ts: float = 0.0

        # Rolling history of realized spread P&Ls (most recent at the end).
        # Used by _kelly_fraction() to compute fractional Kelly sizing when
        # ``TRADOV_KELLY_SIZING=1``. Capped at KELLY_HISTORY_MAX entries to
        # bound memory and keep the estimate reactive to recent regimes.
        self._spread_pnl_history: list[float] = []

        # Closed-spread audit log: full snapshot of every closed paper spread
        # for the Trade Audit dialog (also useful for ML training datasets).
        # Capped at CLOSED_TRADES_MAX entries; oldest entries dropped first.
        # Each row is a self-contained dict — no references into _open_spreads.
        self._closed_trades: list[dict] = []

        # H05 TradingSessionDB — paper database (identical schema to live DB).
        # Persists trades, positions, and account snapshots so paper history
        # survives restarts and can be compared against live performance.
        try:
            from Tradov.TradovH_Storage.TradovH05_TradingSessionDB import TradingSessionDB
            self._session_db = TradingSessionDB.for_paper()
        except Exception as _h05_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "H05 TradingSessionDB unavailable for paper DB: %s", _h05_err
            )
            self._session_db = None

        # Decision audit log: monotonic poll counter used as a sequence number
        # in logs/decisions/YYYY-MM-DD.jsonl for EOD gate-by-gate review.
        self._poll_seq: int = 0

        # Track quote staleness for underlying quote.last and preserve the latest
        # spread-entry rejection reason for decision-log observability.
        self._last_quote_last: float | None = None
        self._last_quote_mid: float | None = None
        self._stale_last_counter: int = 0
        self._last_spread_reject_reason: str = ""

        # Phase 2 IV-rank gate: rolling ATM IV history keyed by nothing (just
        # a flat deque of the ATM short-put IVs observed across polls). Used
        # by _iv_gate_allows_entry() to decide whether premium is rich enough.
        from collections import deque as _deque
        self._atm_iv_history: _deque = _deque(maxlen=self.IV_HISTORY_MAXLEN)
        self._last_atm_iv: float | None = None
        self._last_iv_rank: float | None = None

        # Pivot mean-reversion signal (S08) caches. Pivots derive from the
        # prior trading day's H/L/C and are stable for the whole session, so
        # we fetch them lazily once per UTC date and cache the result.
        # ``_last_pivot_signal`` carries the most recent evaluation so the
        # spread-open path can stamp it onto the audit row without re-running.
        self._pivots_cache: dict[str, float] | None = None
        self._pivots_cache_date: str | None = None  # YYYY-MM-DD UTC
        self._pivot_signal_engine = (
            PivotMeanReversionSignal() if PIVOT_MR_SIGNAL_AVAILABLE else None
        )
        self._last_pivot_signal = None  # PivotMRSignal | None

        # Armed-candidate: a single setup that passed signal + regime gates
        # but was blocked by IV or Greeks. Persists across poll cycles until
        # the blocking gate clears (→ ENTERED_BY_AI) or the TTL expires.
        # Only IV-gate and Greeks-gate blocks produce an armed candidate;
        # cooldown / cap / dedup blocks do not (they self-resolve next poll).
        self._armed_candidate: dict | None = None

    def set_risk_params(self, params: dict) -> None:
        """Update risk limits from the G09 Risk Levels dialog.

        Safe to call from any thread — dict assignment is atomic under the GIL.
        Accepted dict layout (nested, from G09.get_parameters):
            params["global"]["max_buying_power"]  → % of capital cap (0-100)
            params["global"]["max_daily_loss"]    → % max daily drawdown (0-100)
        Also accepts the legacy flat layout from load_default_risk_parameters.
        """
        self._risk_params = params if isinstance(params, dict) else {}

    def set_risk_manager(self, risk_manager) -> None:
        """Inject a TradovE01_RiskManager instance for pre-trade validation.

        When set, every proposed entry is routed through
        ``risk_manager.validate_signal(RiskValidationRequest)`` before the
        paper fill is booked. Rejections are logged and the trade is skipped.
        Passing ``None`` disables the E-series path and reverts to local-only
        checks.
        """
        self._risk_manager = risk_manager

    def set_regime_metrics(self, metrics: dict) -> None:
        """Receive the latest S07 custom-metrics snapshot (regime context).

        Called on every S07 emit. The worker reads SWAN (tail-risk index)
        from this dict before taking new entries. Safe to call from any
        thread — the snapshot is replaced atomically.
        """
        if isinstance(metrics, dict):
            self._regime_metrics = metrics

    def _regime_allows_entry(self) -> tuple[bool, str]:
        """Check whether current market regime permits opening a new position.

        Returns (allowed, reason). Reason is "" when allowed.
        Currently blocks entries when SWAN tail-risk index ≥ 2.0.
        """
        swan_entry = self._regime_metrics.get("SWAN")
        if isinstance(swan_entry, dict):
            swan = swan_entry.get("value")
            try:
                if swan is not None and float(swan) >= 2.0:
                    return False, f"SWAN={float(swan):.2f} ≥ 2.0 (extreme tail-risk regime)"
            except (TypeError, ValueError):
                pass
        return True, ""

    @staticmethod
    def _regime_scalar(entry) -> float | None:
        """Extract a numeric value from an S07 metric entry (dict or scalar)."""
        if entry is None:
            return None
        if isinstance(entry, dict):
            entry = entry.get("value")
        try:
            return float(entry)
        except (TypeError, ValueError):
            return None

    def _write_decision_log(self, record: dict) -> None:
        """Append *record* as a JSON line to logs/decisions/YYYY-MM-DD.jsonl.

        Creates the directory on first write. Silently swallows all I/O errors
        so a disk issue never halts the trading loop. One file per calendar
        day (UTC); query with ``jq`` or ``pandas.read_json(lines=True)``.
        """
        try:
            log_dir = Path("logs") / "decisions"
            log_dir.mkdir(parents=True, exist_ok=True)
            day = datetime.now(UTC).strftime("%Y-%m-%d")
            path = log_dir / f"{day}.jsonl"
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except Exception:  # noqa: BLE001
            pass  # never interrupt trading for a log write failure

    def _regime_preferred_direction(self) -> str | None:
        """Infer a preferred spread direction from the S07 regime snapshot.

        Heuristic (only fires when ``TRADOV_REGIME_STRUCTURE=1``):

        - **DIX** > 0.45  → hidden bullish accumulation → ``"bullish"``
          (sell bull-put).
        - **DIX** < 0.35  → hidden distribution → ``"bearish"`` (sell bear-call).
        - **GEX** strongly positive and SWAN low → range-bound → ``"neutral"``
          (condor candidate, caller decides).
        - Otherwise → ``None`` (no clear regime bias).

        Only used as a tiebreaker when the MA signal is neutral. Returns
        ``None`` if the feature flag is off or data is missing.
        """
        if os.environ.get("TRADOV_REGIME_STRUCTURE", "1") != "1":
            return None

        dix = self._regime_scalar(self._regime_metrics.get("DIX"))
        gex = self._regime_scalar(self._regime_metrics.get("GEX"))
        swan = self._regime_scalar(self._regime_metrics.get("SWAN"))

        if dix is not None:
            if dix > 0.45:
                return "bullish"
            if dix < 0.35:
                return "bearish"

        # Only consider condor hint when tail-risk is quiet AND dealers are
        # long gamma (positive GEX suppresses realised vol).
        if (
            gex is not None
            and gex > 0
            and (swan is None or swan < 1.0)
        ):
            return "neutral"

        return None

    # ------------------------------------------------------------------
    # Pivot mean-reversion signal (S08) producer
    # ------------------------------------------------------------------
    def _get_session_pivots(self) -> dict[str, float] | None:
        """Lazy-load classic pivots from the prior trading day's H/L/C.

        Cached for the entire UTC day. Returns ``None`` when historical data
        is unavailable (e.g., client missing, network error, weekend with no
        prior bar). Pivot formula:

            P  = (H + L + C) / 3
            R1 = 2P - L      ; S1 = 2P - H
            R2 = P + (H - L) ; S2 = P - (H - L)
            R3 = H + 2(P - L); S3 = L - 2(H - P)
        """
        from datetime import date as _date, timedelta as _timedelta

        today_iso = _date.today().isoformat()
        if (
            self._pivots_cache is not None
            and self._pivots_cache_date == today_iso
        ):
            return self._pivots_cache

        if self._client is None:
            return None

        # Fetch the last ~10 daily bars and use the most recent one strictly
        # before today as the prior session. 10-day window covers weekends
        # and exchange holidays without resorting to a calendar lookup.
        try:
            start = (_date.today() - _timedelta(days=10)).isoformat()
            end = _date.today().isoformat()
            resp = self._client.get_historical_quotes(
                self.UNDERLYING_SYMBOL,
                interval="daily",
                start=start,
                end=end,
            )
        except Exception:  # noqa: BLE001
            return None

        history = (resp or {}).get("history") or {}
        days = history.get("day") if isinstance(history, dict) else None
        if isinstance(days, dict):
            days = [days]
        if not days:
            return None

        prior = None
        for bar in reversed(days):
            try:
                if bar.get("date") and bar["date"] < today_iso:
                    prior = bar
                    break
            except (TypeError, AttributeError):
                continue
        if prior is None:
            return None

        try:
            high = float(prior["high"])
            low = float(prior["low"])
            close = float(prior["close"])
        except (KeyError, TypeError, ValueError):
            return None

        p = (high + low + close) / 3.0
        rng = high - low
        pivots = {
            "P": p,
            "R1": 2 * p - low,
            "S1": 2 * p - high,
            "R2": p + rng,
            "S2": p - rng,
            "R3": high + 2 * (p - low),
            "S3": low - 2 * (high - p),
        }
        self._pivots_cache = pivots
        self._pivots_cache_date = today_iso
        return pivots

    @staticmethod
    def _rsi_from_prices(prices: list[float], period: int = 14) -> float | None:
        """Wilder RSI(period). Returns None when fewer than period+1 samples."""
        if len(prices) < period + 1:
            return None
        gains = 0.0
        losses = 0.0
        for i in range(1, period + 1):
            delta = prices[i] - prices[i - 1]
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
        avg_gain = gains / period
        avg_loss = losses / period
        for i in range(period + 1, len(prices)):
            delta = prices[i] - prices[i - 1]
            gain = max(delta, 0.0)
            loss = max(-delta, 0.0)
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _atr_proxy_from_prices(
        prices: list[float], window: int = 20
    ) -> float | None:
        """Cheap intraday ATR proxy: max-min range over the last ``window`` bars.

        Real ATR needs OHLC per bar; we only have closes from the poll loop.
        For S08's purpose (computing ATR-distance to a pivot level) the rolling
        range is a reasonable substitute at the 30-second cadence.
        """
        if len(prices) < window:
            return None
        window_slice = prices[-window:]
        return max(window_slice) - min(window_slice)

    def _pivot_regime_label(self) -> str:
        """Map S07 regime metrics → S08 regime label string.

        S08 awards +25 when the regime is in MEAN_REVERTING_REGIMES =
        {LOW_VOL, RANGE, LOW, NORMAL}. We map:
          - SWAN >= 1.5            → "" (no bonus — tail-risk active)
          - GEX > 0 and SWAN < 1.0 → "RANGE" (long-gamma pinning)
          - DIX in [0.40, 0.45]    → "NORMAL"
          - otherwise              → ""
        """
        swan = self._regime_scalar(self._regime_metrics.get("SWAN"))
        gex = self._regime_scalar(self._regime_metrics.get("GEX"))
        dix = self._regime_scalar(self._regime_metrics.get("DIX"))
        if swan is not None and swan >= 1.5:
            return ""
        if gex is not None and gex > 0 and (swan is None or swan < 1.0):
            return "RANGE"
        if dix is not None and 0.40 <= dix <= 0.45:
            return "NORMAL"
        return ""

    def _compute_pivot_signal(self, spy_price: float):
        """Build PivotMRInputs from current state and evaluate the S08 signal.

        Returns a ``PivotMRSignal`` or ``None`` when the module is missing or
        a required input cannot be built (no pivots, no RSI, no ATR proxy).
        Caches the most recent result on ``self._last_pivot_signal`` so the
        spread-open path can stamp it onto the audit row.
        """
        if not PIVOT_MR_SIGNAL_AVAILABLE or self._pivot_signal_engine is None:
            return None
        if spy_price <= 0:
            return None

        pivots = self._get_session_pivots()
        if not pivots:
            return None

        rsi = self._rsi_from_prices(self._price_history, period=14)
        atr = self._atr_proxy_from_prices(self._price_history, window=20)
        if rsi is None or atr is None or atr <= 0:
            return None

        # Optional: GEX scaled to dollar-equivalent so S08's $1B threshold is
        # comparable. S07's GEX scalar is bounded ~[-1, 1]; multiplying by
        # 2e9 maps the strong-positive zone (>0.5) above the threshold.
        gex_scalar = self._regime_scalar(self._regime_metrics.get("GEX"))
        net_gex = gex_scalar * 2e9 if gex_scalar is not None else None

        try:
            inputs = PivotMRInputs(
                spot_price=float(spy_price),
                pivots=pivots,
                atr=float(atr),
                rsi=float(rsi),
                regime_label=self._pivot_regime_label(),
                net_gex=net_gex,
            )
            signal = self._pivot_signal_engine.evaluate(inputs)
        except Exception:  # noqa: BLE001
            return None

        self._last_pivot_signal = signal
        return signal

    def _pivot_preferred_direction(self, spy_price: float) -> str | None:
        """Return ``"bullish"`` / ``"bearish"`` when S08 fires, else ``None``.

        Gated by ``TRADOV_PIVOT_MR_ENABLED=1`` so the producer is opt-in for
        the first paper-trading sessions. Defaults off for safety.
        """
        if os.environ.get("TRADOV_PIVOT_MR_ENABLED", "0") != "1":
            return None
        signal = self._compute_pivot_signal(spy_price)
        if signal is None or not signal.fired:
            return None
        # FADE_RESISTANCE → sell call spread above price → bearish
        # FADE_SUPPORT    → sell put spread below price  → bullish
        if signal.direction == PivotDirection.FADE_RESISTANCE:
            return "bearish"
        if signal.direction == PivotDirection.FADE_SUPPORT:
            return "bullish"
        return None

    def _snapshot_pivot_signal(self) -> dict | None:
        """Serialise the most recent fired PivotMRSignal for audit storage.

        Returns ``None`` when no signal has fired (or the module is missing).
        Output is a plain dict so JSON / sqlite / pandas can all consume it.
        """
        ps = self._last_pivot_signal
        if ps is None or not getattr(ps, "fired", False):
            return None
        try:
            return {
                "direction": ps.direction.value,
                "score": float(ps.score),
                "confidence": float(ps.confidence),
                "fired": True,
                "level_name": ps.nearest_level_name,
                "level_price": float(ps.nearest_level_price),
                "atr_distance": float(ps.atr_distance),
                "reasons": list(ps.reasons),
                "penalties": list(ps.penalties),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    def _emit_pivot_signal_state(self, spy_price: float) -> None:
        """Compute the S08 PMR signal and emit a state dict for the dashboard.

        The dict is consumed by the left-panel ``PMR`` row so the operator
        sees live signal state every poll. Always emits, even when the
        producer is disabled or the signal hasn't fired -- the widget
        renders ``DIS`` / ``ARMED`` / fired states from the same payload.

        Payload keys: enabled, available, fired, direction, score,
        level_name, level_price, atr_distance, reasons, penalties.
        """
        enabled = os.environ.get("TRADOV_PIVOT_MR_ENABLED", "0") == "1"
        payload: dict = {
            "enabled": enabled,
            "available": PIVOT_MR_SIGNAL_AVAILABLE,
            "fired": False,
            "direction": None,
            "score": None,
            "level_name": None,
            "level_price": None,
            "atr_distance": None,
            "reasons": [],
            "penalties": [],
        }

        if enabled and PIVOT_MR_SIGNAL_AVAILABLE:
            signal = self._compute_pivot_signal(spy_price)
            if signal is not None:
                try:
                    payload.update({
                        "fired": bool(signal.fired),
                        "direction": (
                            signal.direction.value if signal.direction else None
                        ),
                        "score": float(signal.score),
                        "level_name": signal.nearest_level_name,
                        "level_price": (
                            float(signal.nearest_level_price)
                            if signal.nearest_level_price is not None else None
                        ),
                        "atr_distance": (
                            float(signal.atr_distance)
                            if signal.atr_distance is not None else None
                        ),
                        "reasons": list(signal.reasons),
                        "penalties": list(signal.penalties),
                    })
                except (AttributeError, TypeError, ValueError):
                    pass  # leave payload at its defaults

        try:
            self.pivot_signal_updated.emit(payload)
        except RuntimeError:
            # Receiver gone (Qt object deleted) — safe to ignore.
            pass

    def _validate_with_risk_manager(
        self, side: str, quantity: int, price: float
    ) -> tuple[bool, str]:
        """Route a proposed trade through TradovE01_RiskManager.validate_signal.

        Returns (approved, reason). When no risk manager is injected, returns
        (True, "") so the worker's local checks remain the sole gate.
        """
        if self._risk_manager is None:
            return True, ""
        try:
            from Tradov.TradovE_Risk.TradovE00_RiskProtocol import (
                BoundarySignalType,
                RiskValidationRequest,
            )
        except ImportError:
            return True, ""  # Protocol missing — skip rather than block trading

        try:
            signal_type = (
                BoundarySignalType.SELL if side.upper() == "SELL"
                else BoundarySignalType.BUY
            )
            request = RiskValidationRequest(
                symbol=self.UNDERLYING_SYMBOL,
                quantity=int(quantity),
                signal_type=signal_type,
                strategy_id="R08_PaperWorker.MA_Crossover",
                entry_price=float(price),
                confidence=0.5,
                metadata={"source": "TradovR08", "instrument": "stock"},
            )
            result = self._risk_manager.validate_signal(request)
            approved = bool(getattr(result, "approved", False))
            reason = str(getattr(result, "rejection_reason", "") or "")
            return approved, reason
        except Exception as exc:
            # Never let a risk-manager bug halt the worker — log and fall
            # through to local checks.
            self.status_update.emit(f"⚠️ Risk manager error: {exc} — using local checks")
            return True, ""

    # -------------------------------------------------------------------------
    # Session persistence — save / restore open positions across restarts
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        """Persist worker state to STATE_FILE so restarts can resume open trades."""
        try:
            self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "_schema": 1,
                "_saved_at": time.time(),
                "_cash": self._cash,
                "_initial_capital": self._initial_capital,
                "_total_realized_pnl": self._total_realized_pnl,
                "_total_commissions": self._total_commissions,
                "_trades_executed": self._trades_executed,
                "_winning_trades": self._winning_trades,
                "_losing_trades": self._losing_trades,
                "_peak_equity": self._peak_equity,
                "_max_drawdown": self._max_drawdown,
                "_spread_seq": self._spread_seq,
                "_consecutive_losses": self._consecutive_losses,
                "_cooldown_until_ts": self._cooldown_until_ts,
                "_spread_pnl_history": list(self._spread_pnl_history),
                "_open_spreads": list(self._open_spreads),
                "_closed_trades": list(self._closed_trades),
            }
            tmp = self.STATE_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, default=str)
            tmp.replace(self.STATE_FILE)

            # Mirror account snapshot to paper DB (H05) for parity with live DB.
            if self._session_db is not None:
                try:
                    spreads_unrealized = self._spreads_unrealized_pnl()
                    equity = self._cash + self._position_qty * 0.0 + spreads_unrealized
                    self._session_db.record_account_snapshot(
                        cash=float(state["_cash"]),
                        equity=equity,
                        buying_power=float(state["_cash"]),
                        realized_pnl=float(state["_total_realized_pnl"]),
                        unrealized_pnl=spreads_unrealized,
                        total_trades=int(state["_trades_executed"]),
                        winning_trades=int(state["_winning_trades"]),
                        losing_trades=int(state["_losing_trades"]),
                        max_drawdown=float(state["_max_drawdown"]),
                    )
                except Exception as _snap_err:
                    self.status_update.emit(f"⚠️ DB snapshot failed: {_snap_err}")
        except Exception as exc:
            self.status_update.emit(f"⚠️ State save failed: {exc}")

    def _load_state(self) -> bool:
        """Restore worker state from STATE_FILE.  Returns True if state was loaded.

        Only loads if the file exists *and* contains open spreads that have not
        yet expired (DTE > 0) as of today.  Stale files (all spreads past
        expiry, or saved from a different calendar date with no open spreads)
        are silently discarded.
        """
        if not self.STATE_FILE.exists():
            return False
        try:
            with open(self.STATE_FILE, encoding="utf-8") as fh:
                state = json.load(fh)
        except Exception as exc:
            self.status_update.emit(f"⚠️ Could not read state file: {exc}")
            return False

        open_spreads: list[dict] = state.get("_open_spreads", [])
        today = datetime.now(UTC).date().isoformat()

        # Drop spreads that have already expired.
        live_spreads = [
            s for s in open_spreads
            if str(s.get("expiration", "")) >= today
        ]

        # Determine whether there is any meaningful accounting to restore.
        has_history = (
            int(state.get("_trades_executed", 0)) > 0
            or float(state.get("_total_realized_pnl", 0.0)) != 0.0
            or len(state.get("_closed_trades", [])) > 0
        )

        if not live_spreads and not has_history:
            # Truly empty state — nothing to restore.
            return False

        if not live_spreads and open_spreads:
            # All saved spreads are past expiry — keep accounting but clear open positions.
            self.status_update.emit(
                "⚠️ Saved spreads are all past expiry — positions cleared, accounting retained"
            )

        # Restore scalars.
        self._cash                  = float(state.get("_cash", self._initial_capital))
        self._initial_capital       = float(state.get("_initial_capital", self._initial_capital))
        self._total_realized_pnl    = float(state.get("_total_realized_pnl", 0.0))
        self._total_commissions     = float(state.get("_total_commissions", 0.0))
        self._trades_executed       = int(state.get("_trades_executed", 0))
        self._winning_trades        = int(state.get("_winning_trades", 0))
        self._losing_trades         = int(state.get("_losing_trades", 0))
        self._peak_equity           = float(state.get("_peak_equity", self._initial_capital))
        self._max_drawdown          = float(state.get("_max_drawdown", 0.0))
        self._spread_seq            = int(state.get("_spread_seq", 0))
        self._consecutive_losses    = int(state.get("_consecutive_losses", 0))
        self._cooldown_until_ts     = float(state.get("_cooldown_until_ts", 0.0))
        self._spread_pnl_history    = list(state.get("_spread_pnl_history", []))
        self._open_spreads          = live_spreads
        self._closed_trades         = list(state.get("_closed_trades", []))

        saved_at = state.get("_saved_at", 0)
        saved_ts = (
            datetime.fromtimestamp(float(saved_at)).strftime("%H:%M:%S")
            if saved_at else "unknown"
        )
        count = len(live_spreads)
        trades = self._trades_executed
        pnl    = self._total_realized_pnl
        if count > 0:
            spread_ids = ", ".join(f"#{s['id']}" for s in live_spreads)
            self.status_update.emit(
                f"♻️ Restored {count} open spread(s) from previous session "
                f"(saved {saved_ts}): {spread_ids}"
            )
        else:
            self.status_update.emit(
                f"♻️ Restored paper session (saved {saved_ts}) — "
                f"{trades} trade(s) | realised P&L ${pnl:+.2f} | cash ${self._cash:,.2f}"
            )
        return True

    def _clear_state(self) -> None:
        """Delete the persisted state file (call when paper trading stops normally)."""
        try:
            if self.STATE_FILE.exists():
                self.STATE_FILE.unlink()
        except Exception:
            pass  # Non-critical; silently swallow

    def run(self):
        """Main paper trading loop — called when QThread starts."""
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            env = (
                os.environ.get("TRADIER_MARKET_DATA_ENVIRONMENT")
                or os.environ.get("TRADIER_ENVIRONMENT")
                or "live"
            ).strip().lower()

            is_live_env = env in {"live", "production"}
            if not is_live_env:
                self.status_update.emit(
                    "⚠️ Forcing LIVE market-data endpoint "
                    f"(TRADIER_MARKET_DATA_ENVIRONMENT={env or '<empty>'} ignored)",
                )

            api_key = (
                os.environ.get("TRADIER_LIVE_API_KEY", "")
            )
            account_id = (
                os.environ.get("TRADIER_LIVE_ACCOUNT_ID", "")
                or os.environ.get("TRADIER_ACCOUNT_ID", "")
            )
            env = "live"

            if not api_key or not account_id:
                self.error.emit(
                    "TRADIER_LIVE_API_KEY and TRADIER_ACCOUNT_ID must be set in .env\n"
                    "Paper trading requires Tradier market-data credentials.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.status_update.emit(f"Connecting to Tradier ({env})…")

            env_enum = TradingEnvironment.LIVE
            self._client = TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=env_enum,
            )

            if not self._client.test_connection():
                self.error.emit(
                    f"Failed to connect to Tradier API ({env}).\n"
                    "Check your API key and account ID.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.connection_ready.emit(True)
            self.status_update.emit("✅ Connected to Tradier (LIVE)")

            # Restore any open positions from the previous session before
            # printing the "started" banner so the UI immediately shows the
            # correct capital and equity figures on startup.
            restored = self._load_state()
            if restored:
                # Emit a snapshot immediately so the dashboard can render open
                # spreads even when market quotes are temporarily unavailable
                # (e.g., pre-market/off-hours where last=0 on first polls).
                self._emit_position_update(0.0, 0.0, 0.0)
                self._emit_metrics()
                self.status_update.emit("♻️ Emitted startup snapshot from saved paper state")
            else:
                # Emit an explicit empty-session snapshot so the dashboard can
                # replace its startup placeholder before the first successful
                # quote poll arrives.
                self._emit_position_update(0.0, 0.0, 0.0)
                self._emit_metrics()
                self.status_update.emit("📭 Emitted startup snapshot for empty paper session")

            self.status_update.emit(
                f"Paper trading started — ${self._initial_capital:,.0f} capital | "
                f"Polling every {self.POLL_INTERVAL}s",
            )

            self._running = True
            self._price_history = []

            while self._running:
                try:
                    self._poll_and_trade()
                except Exception as e:
                    self.status_update.emit(f"⚠️ Poll error: {e}")

                # Sleep in small increments so stop() is responsive
                for _ in range(self.POLL_INTERVAL * 10):
                    if not self._running:
                        break
                    time.sleep(0.1)

            self._emit_metrics()
            self.status_update.emit("Paper trading stopped")
            # Always save state on clean shutdown so accounting history
            # (cash, realized P&L, trade count) survives restarts even when
            # there are no open spreads.  Only delete the file when the user
            # explicitly resets the paper session.
            self._save_state()
            self.stopped.emit()

        except Exception as e:
            self.error.emit(f"Paper trading failed: {e}")
            self.stopped.emit()

    def stop(self):
        """Signal the trading loop to stop."""
        self._running = False

    def _poll_and_trade(self):
        """Fetch current underlying quote, run strategy, execute paper trades."""
        if not self._client:
            return

        try:
            resp = self._client.get_quotes([self.UNDERLYING_SYMBOL])
            quote = resp.get("quotes", {}).get("quote", {})
            if isinstance(quote, list):
                quote = quote[0]
        except Exception as e:
            self.status_update.emit(f"⚠️ Quote fetch failed: {e}")
            return

        last_price = float(quote.get("last", 0))
        bid = float(quote.get("bid", 0))
        ask = float(quote.get("ask", 0))

        mid_price = 0.0
        if bid > 0 and ask > 0:
            mid_price = (bid + ask) / 2.0

        # Quote hygiene:
        # 1) if last is missing/non-positive, fall back to NBBO mid.
        # 2) if last is unchanged for multiple polls while mid keeps moving,
        #    treat last as stale and switch to mid for signal generation.
        if last_price <= 0 and mid_price > 0:
            last_price = mid_price

        if last_price > 0 and mid_price > 0:
            if (
                self._last_quote_last is not None
                and abs(last_price - self._last_quote_last) < 1e-9
                and self._last_quote_mid is not None
                and abs(mid_price - self._last_quote_mid) > 1e-6
            ):
                self._stale_last_counter += 1
            else:
                self._stale_last_counter = 0

            if self._stale_last_counter >= 3:
                last_price = mid_price

        self._last_quote_last = float(quote.get("last", 0) or 0.0)
        self._last_quote_mid = mid_price if mid_price > 0 else None

        if last_price <= 0:
            return

        self._price_history.append(last_price)
        if len(self._price_history) > self.HISTORY_SIZE:
            self._price_history = self._price_history[-self.HISTORY_SIZE:]

        # Phase 2: MTM any open spreads first so _update_position_mtm and the
        # emitters see fresh debit caches. Auto-closes at 50%-max-profit or
        # DTE ≤ 1. No-op when _open_spreads is empty.
        self._mark_spreads_mtm()
        self._update_position_mtm(last_price)

        # S08 Pivot MR — compute every poll for the dashboard left-panel row,
        # independent of whether a spread will be opened this tick. The signal
        # itself stays gated by TRADOV_PIVOT_MR_ENABLED inside the entry path.
        self._emit_pivot_signal_state(last_price)

        # Armed-candidate promotion: re-check a previously parked setup before
        # running the normal signal logic. If it fires, the open_spreads count
        # will naturally block new entries via the position cap check.
        self._poll_armed_candidate(last_price)

        # ---- Decision audit record (written at end of every poll) -----------
        self._poll_seq += 1
        _dec: dict = {
            "ts": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
            "seq": self._poll_seq,
            "spy": round(last_price, 4),
            "bid": round(bid, 4),
            "ask": round(ask, 4),
            "options_mode": os.environ.get("TRADOV_OPTIONS_LIVE_PAPER", "0") == "1",
            "open_spreads": len(self._open_spreads),
            "signal": None,
            "ma5": None,
            "ma20": None,
            "ma_gap_pct": None,
            "daily_loss_pct": None,
            "daily_loss_ok": None,
            "regime_ok": None,
            "regime_reason": None,
            "selector_feature_flag": None,
            "swan": self._regime_scalar(self._regime_metrics.get("SWAN")),
            "dix": self._regime_scalar(self._regime_metrics.get("DIX")),
            "gex": self._regime_scalar(self._regime_metrics.get("GEX")),
            "s08_enabled": os.environ.get("TRADOV_PIVOT_MR_ENABLED", "0") == "1",
            "s08_score": None,
            "s08_fired": False,
            "s08_direction": None,
            "action": "NO_HISTORY",
            "action_detail": (
                f"need {self.LONG_MA_WINDOW} bars, have {len(self._price_history)}"
            ),
            "spread_id": None,
        }

        if len(self._price_history) >= self.LONG_MA_WINDOW:
            signal = self._generate_signal()

            # Risk check: daily loss limit — block new entries if breached
            current_equity = self._cash + self._position_qty * last_price
            daily_loss_pct = self._get_risk_limit("max_daily_loss", 100.0)
            daily_loss_limit = self._session_start_equity * (daily_loss_pct / 100.0)
            daily_loss_actual = self._session_start_equity - current_equity

            # ---- Decision log: MA + RSI + signal + S08 snapshot --------
            _p = self._price_history
            _sma = sum(_p[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
            _lma = sum(_p[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW
            _rsi_val = self._rsi_from_prices(_p)
            _dec.update({
                "signal": signal,
                "ma5": round(_sma, 4),
                "ma20": round(_lma, 4),
                "ma_gap_pct": round(
                    ((_sma - _lma) / _lma) * 100 if _lma else 0, 4
                ),
                "rsi": round(_rsi_val, 2) if _rsi_val is not None else None,
                "daily_loss_pct": round(
                    (daily_loss_actual / self._session_start_equity) * 100, 4
                ) if self._session_start_equity else 0.0,
                "daily_loss_ok": daily_loss_actual < daily_loss_limit,
                "action": "NO_TRADE",
                "action_detail": "no_signal",
            })
            if self._last_pivot_signal is not None:
                _ps = self._last_pivot_signal
                _dec.update({
                    "s08_score": getattr(_ps, "score", None),
                    "s08_fired": bool(getattr(_ps, "fired", False)),
                    "s08_direction": (
                        _ps.direction.value
                        if getattr(_ps, "direction", None) is not None
                        else None
                    ),
                })

            if signal == "BUY" and self._position_qty == 0:
                if os.environ.get("TRADOV_ENABLE_BULL_CALL_SPREAD", "0") == "1":
                    _dec["selector_feature_flag"] = "TRADOV_ENABLE_BULL_CALL_SPREAD"
                if daily_loss_actual >= daily_loss_limit:
                    self.status_update.emit(
                        f"⛔ BUY blocked — daily loss ${daily_loss_actual:,.2f} "
                        f"exceeds {daily_loss_pct:.0f}% limit (${daily_loss_limit:,.2f})"
                    )
                    _dec["action_detail"] = "daily_loss_limit"
                else:
                    # Phase 1 gate: regime guard
                    regime_ok, regime_reason = self._regime_allows_entry()
                    _dec["regime_ok"] = regime_ok
                    _dec["regime_reason"] = regime_reason
                    if not regime_ok:
                        self.status_update.emit(f"⛔ BUY blocked — {regime_reason}")
                        _dec["action_detail"] = "regime_blocked"
                    else:
                        # Phase 1 gate: E-series risk validation
                        entry_price = ask if ask > 0 else last_price
                        rm_ok, rm_reason = self._validate_with_risk_manager(
                            "BUY", 100, entry_price
                        )
                        if not rm_ok:
                            self.status_update.emit(
                                f"⛔ BUY blocked by RiskManager — {rm_reason}"
                            )
                            _dec["action_detail"] = f"risk_manager: {rm_reason}"
                        else:
                            # Phase 2: when TRADOV_OPTIONS_LIVE_PAPER=1 the
                            # worker trades bull-put credit spreads instead
                            # of underlying shares. Default (0) keeps the legacy
                            # share-based flow with optional shadow logging.
                            if os.environ.get("TRADOV_OPTIONS_LIVE_PAPER", "0") == "1":
                                _opened = self._try_open_spread("bullish", last_price)
                                _dec["action"] = "SPREAD_OPENED" if _opened else "SPREAD_REJECTED"
                                _dec["action_detail"] = (
                                    "bull_put"
                                    if _opened
                                    else f"bull_put:{self._last_spread_reject_reason or 'unknown'}"
                                )
                            else:
                                self._shadow_log_credit_spread(last_price)
                                self._execute_paper_buy(entry_price)
                                _dec["action"] = "BUY_SHARE"
            elif signal == "SELL" and os.environ.get(
                "TRADOV_OPTIONS_LIVE_PAPER", "0"
            ) == "1":
                if os.environ.get("TRADOV_ENABLE_BEAR_PUT_SPREAD", "0") == "1":
                    _dec["selector_feature_flag"] = "TRADOV_ENABLE_BEAR_PUT_SPREAD"
                # Phase 4: in live-paper options mode, SELL signal is a
                # bearish opinion → open a bear-call credit spread (subject
                # to all the same gates). Shares are never traded in this mode.
                if daily_loss_actual >= daily_loss_limit:
                    self.status_update.emit(
                        f"⛔ SELL blocked — daily loss ${daily_loss_actual:,.2f} "
                        f"exceeds {daily_loss_pct:.0f}% limit (${daily_loss_limit:,.2f})"
                    )
                    _dec["action_detail"] = "daily_loss_limit"
                else:
                    regime_ok, regime_reason = self._regime_allows_entry()
                    _dec["regime_ok"] = regime_ok
                    _dec["regime_reason"] = regime_reason
                    if not regime_ok:
                        self.status_update.emit(f"⛔ SELL blocked — {regime_reason}")
                        _dec["action_detail"] = "regime_blocked"
                    else:
                        rm_ok, rm_reason = self._validate_with_risk_manager(
                            "SELL", 100, bid if bid > 0 else last_price
                        )
                        if not rm_ok:
                            self.status_update.emit(
                                f"⛔ SELL blocked by RiskManager — {rm_reason}"
                            )
                            _dec["action_detail"] = f"risk_manager: {rm_reason}"
                        else:
                            _opened = self._try_open_spread("bearish", last_price)
                            _dec["action"] = "SPREAD_OPENED" if _opened else "SPREAD_REJECTED"
                            _dec["action_detail"] = (
                                "bear_call"
                                if _opened
                                else f"bear_call:{self._last_spread_reject_reason or 'unknown'}"
                            )
            elif signal == "SELL" and self._position_qty > 0:
                # Legacy share mode: exits always permitted — only reduce risk.
                self._execute_paper_sell(bid if bid > 0 else last_price)
                _dec["action"] = "SELL_SHARE"
            else:
                # Neutral signal. In live-paper mode with the iron-condor
                # flag set, try opening a two-sided condor (bull-put +
                # bear-call). Each leg runs through all existing gates
                # independently, so concurrency cap / Greeks / IV limits
                # still apply. Partial fill (one side only) is tolerated.
                condor_opened = False
                regime_entry_opened = False
                if (
                    signal is None
                    and os.environ.get("TRADOV_OPTIONS_LIVE_PAPER", "0") == "1"
                    and daily_loss_actual < daily_loss_limit
                ):
                    regime_ok, regime_reason = self._regime_allows_entry()
                    _dec["regime_ok"] = regime_ok
                    _dec["regime_reason"] = regime_reason
                    if not regime_ok:
                        # Only warn once per poll and only if either regime
                        # path was actually attempted — kept simple for now.
                        _dec["action_detail"] = "regime_blocked"
                    else:
                        # S08 pivot mean-reversion signal — highest-precedence
                        # neutral-path producer. Only fires when TRADOV_PIVOT_MR_ENABLED=1
                        # AND the composite score clears MIN_FIRE_SCORE. When it
                        # fires, the directional spread aligned with the fade
                        # direction is opened (FADE_RESISTANCE → bear-call,
                        # FADE_SUPPORT → bull-put). Falls through to the legacy
                        # DIX/GEX regime bias when not fired.
                        pivot_bias = self._pivot_preferred_direction(last_price)
                        if pivot_bias is not None:
                            ps = self._last_pivot_signal
                            self.status_update.emit(
                                f"🎯 Pivot MR signal fired — "
                                f"{ps.direction.value} @ "
                                f"{ps.nearest_level_name}={ps.nearest_level_price:.2f} "
                                f"score={ps.score:.0f} → {pivot_bias}"
                            )
                            regime_entry_opened = self._try_open_spread(
                                pivot_bias, last_price
                            )
                        else:
                            # Prefer explicit regime-structure bias (if enabled).
                            bias = self._regime_preferred_direction()
                            if bias == "bullish":
                                regime_entry_opened = self._try_open_spread(
                                    "bullish", last_price
                                )
                            elif bias == "bearish":
                                regime_entry_opened = self._try_open_spread(
                                    "bearish", last_price
                                )
                            elif (
                                os.environ.get("TRADOV_IRON_CONDOR_ENABLED", "0")
                                == "1"
                            ):
                                # Neutral bias or flag disabled — condor path.
                                condor_opened = self._try_open_iron_condor(
                                    last_price
                                )

                if not (condor_opened or regime_entry_opened):
                    # Emit MA diagnostic so user can see why no trade fired
                    prices = self._price_history
                    short_ma = sum(prices[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
                    long_ma = sum(prices[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW
                    ratio_pct = ((short_ma - long_ma) / long_ma) * 100 if long_ma else 0
                    sig_label = signal if signal else "—"
                    self.status_update.emit(
                        f"📊 MA({self.SHORT_MA_WINDOW})={short_ma:.2f} "
                        f"MA({self.LONG_MA_WINDOW})={long_ma:.2f} "
                        f"Δ={ratio_pct:+.3f}% signal={sig_label}",
                    )
                    if _dec.get("action_detail") == "no_signal":
                        _dec["action_detail"] = f"no_trigger signal={sig_label}"
                else:
                    _dec["action"] = "CONDOR_OPENED" if condor_opened else "SPREAD_OPENED"

        self._write_decision_log(_dec)
        self._emit_position_update(last_price, bid, ask)
        self._emit_metrics()

    def _generate_signal(self) -> str | None:
        """Dual moving average crossover with RSI confirmation.

        BUY  requires MA crossover AND RSI ≤ 72 (not overbought).
        SELL requires MA crossover AND RSI ≥ 28 (not oversold).
        """
        prices = self._price_history
        if len(prices) < self.LONG_MA_WINDOW:
            return None

        short_ma = sum(prices[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
        long_ma = sum(prices[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW

        if long_ma <= 0:
            return None

        ratio = (short_ma - long_ma) / long_ma
        rsi = self._rsi_from_prices(prices)

        if ratio > self.MOMENTUM_THRESHOLD:
            # Suppress BUY when overbought (RSI > 72)
            if rsi is None or rsi <= 72:
                return "BUY"
            return None
        if ratio < -self.MOMENTUM_THRESHOLD:
            # Suppress SELL when oversold (RSI < 28)
            if rsi is None or rsi >= 28:
                return "SELL"
            return None
        return None

    def _get_risk_limit(self, key: str, default: float) -> float:
        """Extract a risk limit from the (possibly nested) _risk_params dict."""
        value = float(default)
        # Nested layout from G09.get_parameters: params["global"][key]
        global_block = self._risk_params.get("global", {})
        if isinstance(global_block, dict) and key in global_block:
            value = float(global_block[key])
        # Flat layout from load_default_risk_parameters
        elif key in self._risk_params:
            value = float(self._risk_params[key])

        # Never allow more than 2 concurrent spreads in paper mode.
        if key == "max_open_positions":
            return float(max(1, min(2, int(value))))

        return value

    def _fetch_leg_mids(
        self,
        expiration: str,
        option_type: str,
        short_strike: float,
        long_strike: float,
    ) -> tuple[float | None, float | None]:
        """Return (short_leg_mid, long_leg_mid) for the given legs.

        *option_type* is ``"put"`` (bull-put spread) or ``"call"`` (bear-call
        spread). Returns (None, None) if either strike is missing or bids/asks
        are zero.
        """
        if not self._client:
            return (None, None)
        try:
            rows = self._client.get_option_chain_with_greeks(
                self.UNDERLYING_SYMBOL,
                expiration,
                option_type=option_type,
            )
        except Exception:  # noqa: BLE001
            return (None, None)
        if not rows:
            return (None, None)

        short_mid: float | None = None
        long_mid: float | None = None
        for row in rows:
            if str(getattr(row, "option_type", "")).lower() != option_type.lower():
                continue
            try:
                strike = float(getattr(row, "strike", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            bid = float(getattr(row, "bid", 0.0) or 0.0)
            ask = float(getattr(row, "ask", 0.0) or 0.0)
            if bid <= 0 or ask <= 0:
                continue
            mid = (bid + ask) / 2.0
            if strike == short_strike:
                short_mid = mid
            elif strike == long_strike:
                long_mid = mid
        return (short_mid, long_mid)

    def _fetch_put_mids(
        self, expiration: str, short_strike: float, long_strike: float
    ) -> tuple[float | None, float | None]:
        """Back-compat shim: delegate to ``_fetch_leg_mids`` with puts."""
        return self._fetch_leg_mids(expiration, "put", short_strike, long_strike)

    def _fetch_atm_put_iv(self, expiration: str, spy_price: float) -> float | None:
        """Return the implied volatility of the ATM put for *expiration*.

        Uses Tradier's greeks-enabled chain (``get_option_chain_with_greeks``).
        ATM = the listed put whose strike is closest to *spy_price*. Returns
        None if the chain is empty or the call fails. Safe to call every poll;
        caller is expected to rate-limit via the outer POLL_INTERVAL.
        """
        if not self._client or spy_price <= 0:
            return None
        try:
            rows = self._client.get_option_chain_with_greeks(
                self.UNDERLYING_SYMBOL,
                expiration,
                option_type="put",
            )
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None

        best = None
        best_dist = float("inf")
        for g in rows:
            try:
                dist = abs(float(g.strike) - spy_price)
            except (TypeError, ValueError):
                continue
            iv = float(getattr(g, "iv", 0) or 0)
            if iv <= 0:
                continue
            if dist < best_dist:
                best_dist = dist
                best = iv
        return best

    def _fetch_spread_greeks(
        self,
        expiration: str,
        short_strike: float,
        long_strike: float,
        option_type: str = "put",
    ) -> dict | None:
        """Return per-contract Greeks for both legs of a credit spread.

        Works for both ``option_type="put"`` (bull-put) and ``"call"``
        (bear-call). Issues a single ``get_option_chain_with_greeks`` call and
        extracts the rows matching *short_strike* and *long_strike*. Returns a
        dict with ``short_delta / short_gamma / short_vega / long_delta /
        long_gamma / long_vega`` (all raw per-contract values — NOT multiplied
        by 100 or signed). Returns None if either strike is missing or the API
        call fails.
        """
        if not self._client:
            return None
        try:
            rows = self._client.get_option_chain_with_greeks(
                self.UNDERLYING_SYMBOL,
                expiration,
                option_type=option_type,
            )
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None

        short = long_ = None
        for g in rows:
            try:
                strike = float(g.strike)
            except (TypeError, ValueError):
                continue
            if strike == short_strike:
                short = g
            elif strike == long_strike:
                long_ = g
        if short is None or long_ is None:
            return None
        return {
            "short_delta": float(getattr(short, "delta", 0.0) or 0.0),
            "short_gamma": float(getattr(short, "gamma", 0.0) or 0.0),
            "short_theta": float(getattr(short, "theta", 0.0) or 0.0),
            "short_vega": float(getattr(short, "vega", 0.0) or 0.0),
            "long_delta": float(getattr(long_, "delta", 0.0) or 0.0),
            "long_gamma": float(getattr(long_, "gamma", 0.0) or 0.0),
            "long_theta": float(getattr(long_, "theta", 0.0) or 0.0),
            "long_vega": float(getattr(long_, "vega", 0.0) or 0.0),
        }

    def _pick_strike_by_target_delta(
        self,
        expiration: str,
        option_type: str,
        target_delta: float,
    ) -> float | None:
        """Return the strike whose |delta| is closest to *target_delta*.

        Calls ``get_option_chain_with_greeks`` once, then scans every row
        with a valid delta and picks the minimum absolute-error match. Only
        considers strikes that would form a credit spread: OTM puts
        (delta < 0) for puts, OTM calls (delta > 0) for calls — ITM legs
        are filtered out because they produce negative or near-zero credit.

        Returns None if the chain cannot be loaded or no valid strike is
        found, in which case the caller falls back to the fixed heuristic.
        """
        if not self._client:
            return None
        try:
            rows = self._client.get_option_chain_with_greeks(
                self.UNDERLYING_SYMBOL,
                expiration,
                option_type=option_type,
            )
        except Exception:  # noqa: BLE001
            return None
        if not rows:
            return None

        best_strike: float | None = None
        best_err = float("inf")
        for g in rows:
            try:
                strike = float(g.strike)
                delta = float(getattr(g, "delta", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            # Skip ITM — we only sell OTM premium.
            if option_type == "put" and delta >= 0:
                continue
            if option_type == "call" and delta <= 0:
                continue
            err = abs(abs(delta) - target_delta)
            if err < best_err:
                best_err = err
                best_strike = strike
        return best_strike

    @staticmethod
    def _spread_position_greeks(leg_greeks: dict, qty: int) -> dict:
        """Convert per-contract leg Greeks into a spread's position Greeks.

        For a bull-put credit spread:
          - Short put leg contributes ``-raw × qty × 100`` to each Greek.
          - Long  put leg contributes ``+raw × qty × 100``.

        Returns a dict with ``delta / gamma / vega`` already multiplied by
        the standard options contract multiplier (100) and scaled by qty.
        Puts have negative raw delta; short-put position delta therefore comes
        out positive (bullish), which matches intuition for a bull-put.
        """
        mult = 100.0 * max(0, int(qty))
        return {
            "delta": (leg_greeks["long_delta"] - leg_greeks["short_delta"]) * mult,
            "gamma": (leg_greeks["long_gamma"] - leg_greeks["short_gamma"]) * mult,
            "theta": (leg_greeks.get("long_theta", 0.0) - leg_greeks.get("short_theta", 0.0)) * mult,  # noqa: E501
            "vega": (leg_greeks["long_vega"] - leg_greeks["short_vega"]) * mult,
        }

    def _portfolio_greeks(self) -> dict:
        """Aggregate position Greeks across all currently-open spreads."""
        agg = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        for p in self._open_spreads:
            lg = p.get("leg_greeks")
            if not lg:
                continue
            g = self._spread_position_greeks(lg, int(p.get("qty", 0)))
            agg["delta"] += g["delta"]
            agg["gamma"] += g["gamma"]
            agg["theta"] += g.get("theta", 0.0)
            agg["vega"] += g["vega"]
        return agg

    def _greeks_gate_allows_entry(
        self, spread: dict, qty: int
    ) -> tuple[bool, str]:
        """Reject entry if it would push portfolio Greeks past G09 caps.

        G09 convention (mirrored here):
          - ``max_delta`` (abs cap, e.g. 100) — violated when
            ``|portfolio delta after add|`` exceeds the cap.
          - ``max_gamma`` (abs cap, e.g. 10)  — same abs-value semantics.
          - ``max_vega``  (floor, typically negative, e.g. -200) — violated
            when portfolio vega after add is *below* the floor.

        Never raises; returns (allowed, reason). Disabled via
        ``TRADOV_GREEKS_GATE_DISABLED=1``.
        """
        if os.environ.get("TRADOV_GREEKS_GATE_DISABLED", "0") == "1":
            return True, ""

        lg = spread.get("leg_greeks")
        if not lg:
            # No Greeks available → fail open; IV gate already ensures we
            # have reasonable option data. Worst case: no delta protection.
            return True, ""

        added = self._spread_position_greeks(lg, qty)
        port = self._portfolio_greeks()
        projected = {
            "delta": port["delta"] + added["delta"],
            "gamma": port["gamma"] + added["gamma"],
            "vega": port["vega"] + added["vega"],
        }

        max_delta = float(self._get_risk_limit("max_delta", 500.0))
        max_gamma = float(self._get_risk_limit("max_gamma", 50.0))
        max_vega = float(self._get_risk_limit("max_vega", -2000.0))

        if abs(projected["delta"]) > max_delta:
            return (
                False,
                f"|delta| {projected['delta']:+.1f} would exceed cap "
                f"{max_delta:.0f}",
            )
        if abs(projected["gamma"]) > max_gamma:
            return (
                False,
                f"|gamma| {projected['gamma']:+.2f} would exceed cap "
                f"{max_gamma:.1f}",
            )
        if projected["vega"] < max_vega:
            return (
                False,
                f"vega {projected['vega']:+.1f} would fall below floor "
                f"{max_vega:.0f}",
            )
        return True, ""

    def _update_iv_history(self, expiration: str, spy_price: float) -> None:
        """Append the current ATM put IV to the rolling window (best-effort)."""
        iv = self._fetch_atm_put_iv(expiration, spy_price)
        if iv is None:
            return
        self._last_atm_iv = iv
        self._atm_iv_history.append(iv)

    def _current_iv_rank(self) -> float | None:
        """Current IV rank (0..100) vs the in-memory window.

        Returns None when history has fewer than ``MIN_IV_HISTORY`` samples
        (caller should then fall back to an absolute-IV floor). Rank is
        computed as ``(current − min) / (max − min) × 100``.
        """
        if self._last_atm_iv is None:
            return None
        if len(self._atm_iv_history) < self.MIN_IV_HISTORY:
            return None
        lo = min(self._atm_iv_history)
        hi = max(self._atm_iv_history)
        if hi <= lo:
            return 50.0
        rank = (self._last_atm_iv - lo) / (hi - lo) * 100.0
        self._last_iv_rank = rank
        return rank

    def _iv_gate_allows_entry(self, expiration: str, spy_price: float) -> tuple[bool, str]:
        """Two-tier premium-richness gate for credit spreads.

        Controlled by env:
          - ``TRADOV_IV_GATE_DISABLED=1`` → always allow (useful in tests)
          - ``TRADOV_MIN_IV_ABS`` (float, default 0.12) → absolute IV floor
          - ``TRADOV_MIN_IV_RANK`` (float, default 30.0) → percentile floor once
            we have enough samples

        Returns (allowed, reason). Never raises.
        """
        if os.environ.get("TRADOV_IV_GATE_DISABLED", "0") == "1":
            return True, ""
        # Refresh history for the chosen expiration.
        self._update_iv_history(expiration, spy_price)
        if self._last_atm_iv is None:
            # Data unavailable — fail open so the rest of the pipeline can run.
            return True, ""

        try:
            min_iv_abs = float(os.environ.get("TRADOV_MIN_IV_ABS", "0.12"))
        except ValueError:
            min_iv_abs = 0.12
        try:
            min_iv_rank = float(os.environ.get("TRADOV_MIN_IV_RANK", "30.0"))
        except ValueError:
            min_iv_rank = 30.0

        if self._last_atm_iv < min_iv_abs:
            return (
                False,
                f"ATM IV {self._last_atm_iv:.1%} < floor {min_iv_abs:.1%} "
                f"(premium too cheap)",
            )

        rank = self._current_iv_rank()
        if rank is None:
            # Not enough history yet — absolute floor already passed, allow.
            return True, ""
        if rank < min_iv_rank:
            return (
                False,
                f"IV rank {rank:.0f} < floor {min_iv_rank:.0f} (n={len(self._atm_iv_history)})",
            )
        return True, ""

    def _select_wing_width(self) -> float:
        """Choose the spread wing width in points.

        Default: ``TRADOV_SPREAD_WING_WIDTH`` (env, default 5.0). When
        ``TRADOV_DYNAMIC_WING=1`` and IV rank is available, the wing scales
        with IV regime to keep risk-adjusted credit consistent:

          - IV rank >= 70  -> 8 pts (wide wings: rich premium, more buffer)
          - IV rank >= 40  -> 5 pts (default)
          - IV rank <  40  -> 3 pts (tight wings: low credit, cap loss)

        Falls back to the static env value when IV rank is unavailable.
        """
        try:
            base = float(os.environ.get("TRADOV_SPREAD_WING_WIDTH", "5"))
        except (TypeError, ValueError):
            base = 5.0
        if os.environ.get("TRADOV_DYNAMIC_WING", "0") != "1":
            return base
        rank = self._current_iv_rank()
        if rank is None:
            return base
        if rank >= 70:
            return 8.0
        if rank >= 40:
            return 5.0
        return 3.0

    def _select_credit_spread(
        self, spy_price: float, direction: str = "bullish"
    ) -> dict | None:
        """Pick a credit spread near *spy_price* from the live chain.

        *direction* chooses the structure:
          - "bullish" (default) -> bull-put spread below spot:
              short put = floor(spy) - 5 (~1% OTM), long = short - 5.
          - "bearish" -> bear-call spread above spot:
              short call = ceil(spy) + 5 (~1% OTM), long = short + 5.

        Expiration: nearest listed underlying date with 5 <= DTE <= 14, else the
        first available. Credit = short_mid - long_mid.

        Returns a dict with keys: expiration, direction, option_type ("P"
        or "C"), short_strike, long_strike, wing_width, credit,
        max_loss_per_contract, dte, leg_greeks (may be None).
        Returns None if the chain cannot be resolved.
        """
        if not self._client or spy_price <= 0:
            return None

        try:
            exps_resp = self._client.get_option_expirations(self.UNDERLYING_SYMBOL)
        except Exception:  # noqa: BLE001
            return None
        raw = (exps_resp or {}).get("expirations", {})
        dates = raw.get("date") if isinstance(raw, dict) else raw
        if isinstance(dates, str):
            dates = [dates]
        if not dates:
            return None

        from datetime import date as _date
        today = _date.today()
        chosen_exp: str | None = None
        chosen_dte: int = 0
        for d in dates:
            try:
                y, m, dd = d.split("-")
                exp_dt = _date(int(y), int(m), int(dd))
                dte = (exp_dt - today).days
            except (ValueError, AttributeError):
                continue
            if 5 <= dte <= 14:
                chosen_exp = d
                chosen_dte = dte
                break
        if chosen_exp is None:
            # Fallback: first expiration in the list.
            chosen_exp = dates[0]
            try:
                y, m, dd = chosen_exp.split("-")
                chosen_dte = (_date(int(y), int(m), int(dd)) - today).days
            except (ValueError, AttributeError):
                chosen_dte = 0

        wing_width = self._select_wing_width()
        # --- Strike selection ---------------------------------------------
        # Default: fixed 5-point OTM heuristic (keeps legacy behaviour).
        # When TRADOV_TARGET_SHORT_DELTA is set (e.g., 0.20), pick the short
        # strike whose |delta| is closest to the target, then the long wing
        # ``wing_width`` points further OTM. Target-delta selection is more
        # principled because it auto-adapts to IV: in high-IV regimes the
        # 0.20Δ strike moves further OTM; in low IV it tightens in.
        target_delta_env = os.environ.get("TRADOV_TARGET_SHORT_DELTA", "")
        target_delta: float | None = None
        if target_delta_env:
            try:
                target_delta = abs(float(target_delta_env))
                if not (0.05 <= target_delta <= 0.45):
                    target_delta = None  # guard against nonsense values
            except (TypeError, ValueError):
                target_delta = None

        if direction == "bearish":
            option_type_full = "call"
            option_type_short = "C"
        else:
            option_type_full = "put"
            option_type_short = "P"

        short_strike: float | None = None
        long_strike: float | None = None
        if target_delta is not None:
            short_strike = self._pick_strike_by_target_delta(
                chosen_exp, option_type_full, target_delta
            )
            if short_strike is not None:
                long_strike = (
                    short_strike + wing_width
                    if direction == "bearish"
                    else short_strike - wing_width
                )
        if short_strike is None or long_strike is None:
            # Fallback to the fixed-$5 heuristic.
            if direction == "bearish":
                short_strike = float(int(spy_price) + 5)
                long_strike = short_strike + wing_width
            else:
                short_strike = float(int(spy_price) - 5)
                long_strike = short_strike - wing_width

        short_mid, long_mid = self._fetch_leg_mids(
            chosen_exp, option_type_full, short_strike, long_strike
        )
        if short_mid is None or long_mid is None:
            return None

        credit = short_mid - long_mid
        if credit <= 0:
            return None  # Structure isn't actually a credit — skip.

        max_loss_per_contract = max(0.0, wing_width - credit) * 100.0
        # Phase 3: attach per-contract Greeks for the Greeks-limits gate. Best
        # effort — returns None (leg_greeks absent) if data is unavailable, in
        # which case the gate fails open.
        leg_greeks = self._fetch_spread_greeks(
            chosen_exp, short_strike, long_strike, option_type=option_type_full
        )
        return {
            "expiration": chosen_exp,
            "dte": chosen_dte,
            "direction": direction,
            "option_type": option_type_short,
            "short_strike": short_strike,
            "long_strike": long_strike,
            "wing_width": wing_width,
            "credit": credit,
            "short_entry_mid": short_mid,   # individual leg entry prices for P&L display
            "long_entry_mid": long_mid,
            "max_loss_per_contract": max_loss_per_contract,
            "leg_greeks": leg_greeks,
        }

    def _kelly_fraction(self) -> float | None:
        """Fractional Kelly capital fraction from recent realized P&Ls.

        Formula: ``f* = (W * b - L) / b`` where W = win rate, L = 1-W,
        b = avg_win / avg_loss (both positive magnitudes). Returns None
        when we have fewer than ``KELLY_MIN_SAMPLES`` closed trades, or
        when avg_loss is zero (no risk basis to scale against).

        The raw Kelly is multiplied by ``TRADOV_KELLY_FRACTION`` (default
        0.25 = quarter-Kelly) for safety margin against estimation error,
        then clamped to ``[0, TRADOV_KELLY_MAX]`` (default 0.05 = 5% of
        capital per trade).
        """
        history = self._spread_pnl_history
        if len(history) < self.KELLY_MIN_SAMPLES:
            return None
        wins = [p for p in history if p > 0]
        losses = [-p for p in history if p < 0]  # store as positive magnitudes
        if not losses:
            # No losers in window — Kelly is undefined (b is infinite).
            # Be conservative and skip; caller falls back to fixed-fractional.
            return None
        if not wins:
            return 0.0  # All losers — sit out
        win_rate = len(wins) / len(history)
        loss_rate = 1.0 - win_rate
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        if avg_loss <= 0:
            return None
        b = avg_win / avg_loss
        f_raw = (win_rate * b - loss_rate) / b
        if f_raw <= 0:
            return 0.0  # Negative edge — don't size up
        try:
            scaling = float(os.environ.get("TRADOV_KELLY_FRACTION", "0.25"))
        except (TypeError, ValueError):
            scaling = 0.25
        try:
            cap = float(os.environ.get("TRADOV_KELLY_MAX", "0.05"))
        except (TypeError, ValueError):
            cap = 0.05
        return max(0.0, min(f_raw * scaling, cap))

    def _size_spread_qty(self, spread: dict) -> int:
        """Derive contract quantity from G09 risk_per_trade and max_contracts.

        Default sizing model (fixed-fractional):
            qty = floor(initial_capital × risk_per_trade%  /  max_loss_per_contract)

        When ``TRADOV_KELLY_SIZING=1`` and enough trade history exists
        (``KELLY_MIN_SAMPLES``), the risk-per-trade fraction is replaced
        with the (scaled, capped) Kelly fraction from recent realized P&Ls.
        Falls back to fixed-fractional automatically when Kelly is undefined.

        Then clamped to [1, max_contracts]. When ``max_loss_per_contract`` is
        zero (can't happen with a real credit spread but guarded anyway) or
        the dialog hasn't been applied yet, returns 1 as a safe default.
        """
        max_loss = float(spread.get("max_loss_per_contract", 0.0))
        if max_loss <= 0:
            return 1

        rpt_pct = self._get_risk_limit("risk_per_trade", 1.0)
        # Hard ceiling from the dialog (default 10 if unset).
        max_contracts = int(self._get_risk_limit("max_contracts", 10))

        # Kelly override (opt-in).
        if os.environ.get("TRADOV_KELLY_SIZING", "0") == "1":
            kelly_f = self._kelly_fraction()
            if kelly_f is not None:
                # kelly_f is a 0..1 capital fraction — convert to percent
                # so the rest of the math is identical.
                rpt_pct = kelly_f * 100.0

        budget = float(self._initial_capital) * (rpt_pct / 100.0)
        qty = int(budget // max_loss)
        if qty < 1:
            qty = 1
        if qty > max_contracts:
            qty = max_contracts
        return qty

    def _spread_commission(self, qty: int) -> float:
        """Commission for one side (open OR close) of a spread position.

        Tradier Pro: $0 for many equity & ETF options. The default
        remains zero; override via ``TRADOV_COMMISSION_PER_CONTRACT`` to model
        a different tier without a code change.
        """
        try:
            per_contract = float(
                os.environ.get(
                    "TRADOV_COMMISSION_PER_CONTRACT",
                    self.DEFAULT_COMMISSION_PER_CONTRACT,
                )
            )
        except (TypeError, ValueError):
            per_contract = self.DEFAULT_COMMISSION_PER_CONTRACT
        return per_contract * self.SPREAD_LEG_COUNT * max(0, qty)

    def _try_open_spread(self, direction: str, spy_price: float) -> bool:
        """Run all entry gates then open a directional credit spread.

        *direction* is ``"bullish"`` (bull-put) or ``"bearish"`` (bear-call).
        Returns True if a spread was opened. Each gate failure emits a
        status update explaining the block — callers do not need to log.
        """
        label = "bull-put" if direction == "bullish" else "bear-call"
        self._last_spread_reject_reason = ""

        # Time-of-day gate: block new entries after 3:45 PM ET (no point
        # opening a multi-day position in the final 15 min of the session).
        try:
            from zoneinfo import ZoneInfo
            et_now = datetime.now(ZoneInfo("America/New_York"))
            entry_cutoff = et_now.replace(hour=15, minute=45, second=0, microsecond=0)
            # Only apply during regular market hours (9:30–16:00 window)
            market_open = et_now.replace(hour=9, minute=30, second=0, microsecond=0)
            if market_open <= et_now >= entry_cutoff:
                self.status_update.emit(
                    f"⛔ {label} blocked — no new entries after 3:45 PM ET "
                    f"(current {et_now.strftime('%H:%M')} ET)"
                )
                self._last_spread_reject_reason = "outside_entry_window"
                return False
        except Exception:
            pass  # ZoneInfo unavailable — skip time gate

        # Consecutive-loss cooldown: refuse new entries while active. Exits
        # are not routed through this helper, so they are unaffected.
        if self._cooldown_until_ts and time.time() < self._cooldown_until_ts:
            remaining = int(self._cooldown_until_ts - time.time())
            self.status_update.emit(
                f"⛔ {label} blocked — entry cooldown "
                f"({remaining}s remaining)"
            )
            self._last_spread_reject_reason = "entry_cooldown_active"
            return False

        spread = self._select_credit_spread(spy_price, direction=direction)
        if spread is None:
            self.status_update.emit(
                f"⛔ {label} blocked — could not resolve a valid "
                "spread from chain"
            )
            self._last_spread_reject_reason = "spread_resolution_failed"
            return False

        iv_ok, iv_reason = self._iv_gate_allows_entry(
            spread["expiration"], spy_price
        )
        if not iv_ok:
            self.status_update.emit(
                f"⛔ {label} blocked by IV gate — {iv_reason}"
            )
            self._arm_candidate(direction, spread, f"IV: {iv_reason}")
            self._last_spread_reject_reason = "iv_gate_failed"
            return False

        max_open = int(self._get_risk_limit("max_open_positions", 2))
        if len(self._open_spreads) >= max_open:
            self.status_update.emit(
                f"⛔ {label} blocked — {len(self._open_spreads)}/{max_open} "
                "open spread cap reached"
            )
            self._last_spread_reject_reason = "max_open_spreads_reached"
            return False

        if self._spread_already_open(spread):
            leg = spread["option_type"]
            self.status_update.emit(
                f"⛔ {label} blocked — identical {spread['expiration']} "
                f"{leg}{spread['short_strike']:.0f}/{spread['long_strike']:.0f} "
                "already open"
            )
            self._last_spread_reject_reason = "duplicate_spread"
            return False

        sized_qty = self._size_spread_qty(spread)
        greeks_ok, greeks_reason = self._greeks_gate_allows_entry(
            spread, sized_qty
        )
        if not greeks_ok:
            self.status_update.emit(
                f"⛔ {label} blocked by Greeks gate — {greeks_reason}"
            )
            self._arm_candidate(direction, spread, f"Greeks: {greeks_reason}")
            self._last_spread_reject_reason = "greeks_gate_failed"
            return False

        # All gates passed — any parked armed candidate is superseded.
        self._armed_candidate = None
        self._last_spread_reject_reason = ""
        return self._execute_paper_credit_spread(spread, qty=sized_qty)

    def _arm_candidate(self, direction: str, spread: dict, reason: str) -> None:
        """Park a gate-blocked spread entry as an ARMED_BY_AI candidate.

        Called by ``_try_open_spread`` when only the IV or Greeks gate blocks
        an otherwise-valid setup. The candidate is held across poll cycles and
        re-evaluated by ``_poll_armed_candidate`` each tick.

        If a candidate for a *different* direction already exists it is
        discarded first (conflicting market opinion — stale signal).
        If a candidate for the *same* direction exists it is refreshed with
        the current spread and reset timestamp so the TTL restarts.
        """
        existing = self._armed_candidate
        if existing is not None and existing["direction"] != direction:
            self.status_update.emit(
                f"🔄 ARMED {existing['direction']} candidate discarded — "
                f"new {direction} signal conflicts"
            )

        is_new = existing is None or existing["direction"] != direction
        self._armed_candidate = {
            "direction": direction,
            "spread": dict(spread),
            "blocked_reason": reason,
            "armed_at": time.time(),
            "lifecycle_state": StrategyLifecycleState.ARMED_BY_AI.value,
        }
        if is_new:
            label = "bull-put" if direction == "bullish" else "bear-call"
            self.status_update.emit(
                f"🎯 ARMED BY AI — {label} parked ({reason}), "
                "re-checking each poll"
            )

    def _poll_armed_candidate(self, spy_price: float) -> bool:
        """Re-evaluate the parked ARMED_BY_AI candidate; promote or discard.

        Returns True if the candidate was promoted and a spread opened.
        Called once per poll cycle, before the normal signal logic, so a
        clearing gate triggers entry without waiting for the next MA crossover.
        """
        if self._armed_candidate is None:
            return False

        elapsed = time.time() - self._armed_candidate["armed_at"]
        direction = self._armed_candidate["direction"]
        spread = self._armed_candidate["spread"]
        label = "bull-put" if direction == "bullish" else "bear-call"

        if elapsed > self.ARMED_CANDIDATE_TTL_SECONDS:
            self.status_update.emit(
                f"⏱ ARMED {label} expired — discarded after "
                f"{int(elapsed)}s (TTL={self.ARMED_CANDIDATE_TTL_SECONDS}s)"
            )
            self._armed_candidate = None
            return False

        # Re-check the two gates that triggered the arm.
        iv_ok, iv_reason = self._iv_gate_allows_entry(
            spread["expiration"], spy_price
        )
        if not iv_ok:
            self.status_update.emit(
                f"⏳ ARMED {label} waiting — IV gate: {iv_reason} "
                f"({int(elapsed)}s elapsed)"
            )
            return False

        sized_qty = self._size_spread_qty(spread)
        greeks_ok, greeks_reason = self._greeks_gate_allows_entry(
            spread, sized_qty
        )
        if not greeks_ok:
            self.status_update.emit(
                f"⏳ ARMED {label} waiting — Greeks gate: {greeks_reason} "
                f"({int(elapsed)}s elapsed)"
            )
            return False

        # Also guard the position cap — a different path may have filled it.
        max_open = int(self._get_risk_limit("max_open_positions", 2))
        if len(self._open_spreads) >= max_open:
            self.status_update.emit(
                f"⏳ ARMED {label} waiting — position cap "
                f"({len(self._open_spreads)}/{max_open})"
            )
            return False

        # All gates clear — promote to ENTERED_BY_AI.
        self.status_update.emit(
            f"🚀 ARMED → ENTERED — {label} gates cleared after "
            f"{int(elapsed)}s, opening spread"
        )
        self._armed_candidate = None
        return self._execute_paper_credit_spread(spread, qty=sized_qty)

    def _try_open_iron_condor(self, spy_price: float) -> bool:
        """Open a two-sided condor: bull-put + bear-call at *spy_price*.

        Each leg is booked as an independent credit spread (reusing
        ``_try_open_spread``) so the existing gate chain — IV, concurrency,
        dedup, sizing, Greeks — applies per side. A partial condor (only one
        side opened) is tolerated and returns True if at least one side
        filled. Intended for neutral/range-bound regimes; caller is
        responsible for confirming the neutral signal + regime.
        """
        put_opened = self._try_open_spread("bullish", spy_price)
        call_opened = self._try_open_spread("bearish", spy_price)
        if put_opened and call_opened:
            self.status_update.emit(
                f"🦋 Iron condor opened around {self.UNDERLYING_SYMBOL} ${spy_price:.2f}"
            )
        elif put_opened or call_opened:
            side = "bull-put only" if put_opened else "bear-call only"
            self.status_update.emit(
                f"⚠️ Partial condor — {side} around {self.UNDERLYING_SYMBOL} ${spy_price:.2f}"
            )
        return put_opened or call_opened

    def _spread_already_open(self, spread: dict) -> bool:
        """True if an open spread has the same expiration, type & both strikes.

        Prevents stacking identical exposure when the MA signal fires again
        on a subsequent poll before the existing spread has exited. Includes
        ``option_type`` in the match so a 510P/505P bull-put is not treated
        as duplicate of a 510C/515C bear-call.
        """
        exp = spread["expiration"]
        short_k = float(spread["short_strike"])
        long_k = float(spread["long_strike"])
        otype = spread.get("option_type", "P")
        for p in self._open_spreads:
            if (
                p["expiration"] == exp
                and p.get("option_type", "P") == otype
                and float(p["short_strike"]) == short_k
                and float(p["long_strike"]) == long_k
            ):
                return True
        return False

    def _execute_paper_credit_spread(self, spread: dict, qty: int = 1) -> bool:
        """Book a paper bull-put credit spread. Returns True on success.

        Credit is added to cash immediately. Max loss is tracked per position
        and checked against the daily-loss risk limit. No margin reservation
        beyond that — keeping the paper accounting simple.
        """
        credit_dollars = spread["credit"] * 100.0 * qty
        max_loss_dollars = spread["max_loss_per_contract"] * qty

        # Risk check: don't open a spread whose max loss (combined with the
        # max loss of all currently-open spreads) would blow the remaining
        # daily-loss budget. Aggregate so concurrent spreads can't stack
        # beyond the configured limit.
        daily_loss_pct = self._get_risk_limit("max_daily_loss", 100.0)
        daily_budget = self._session_start_equity * (daily_loss_pct / 100.0)
        open_spread_max_loss = sum(
            float(p["max_loss_per_contract"]) * int(p["qty"])
            for p in self._open_spreads
        )
        already_down = max(0.0, self._session_start_equity - self._cash)
        if already_down + open_spread_max_loss + max_loss_dollars > daily_budget:
            self.status_update.emit(
                f"⛔ Spread blocked — max loss ${max_loss_dollars:,.0f} "
                f"would exceed remaining daily budget"
            )
            return False

        self._spread_seq += 1
        position = {
            "id": self._spread_seq,
            "expiration": spread["expiration"],
            "short_strike": spread["short_strike"],
            "long_strike": spread["long_strike"],
            "option_type": spread["option_type"],
            "direction": spread.get("direction", "bullish"),
            "credit": spread["credit"],
            "qty": qty,
            "opened_at": time.time(),
            "wing_width": spread["wing_width"],
            "max_loss_per_contract": spread["max_loss_per_contract"],
            # Per-leg entry prices for the Orders & Positions panel COST column.
            "short_entry_mid": spread.get("short_entry_mid"),
            "long_entry_mid": spread.get("long_entry_mid"),
            # Phase 3: snapshot per-contract Greeks so _portfolio_greeks() can
            # aggregate without re-fetching the chain every poll.
            "leg_greeks": spread.get("leg_greeks"),
            # Phase 5 (audit): provenance + entry-context snapshot for the
            # Trade Audit dialog and ML feature reconstruction.
            "structure": spread.get(
                "structure",
                "BULL_PUT" if spread["option_type"] == "P" else "BEAR_CALL",
            ),
            "origin": spread.get("origin", "AI"),
            "lifecycle_state": StrategyLifecycleState.ENTERED_BY_AI.value,
            "entry_atm_iv": self._last_atm_iv,
            "entry_iv_rank": self._last_iv_rank,
            "entry_spy": self._price_history[-1] if self._price_history else None,
            # Pivot mean-reversion signal snapshot (S08). None when the
            # signal didn't fire this entry — preserved on the audit row
            # for ML training and post-trade attribution.
            "pivot_signal": self._snapshot_pivot_signal(),
        }
        open_commission = self._spread_commission(qty)
        self._open_spreads.append(position)
        self._cash += credit_dollars - open_commission
        self._total_commissions += open_commission
        # NOTE: _trades_executed is incremented at CLOSE, not here, so that
        # win_rate = winning_trades / trades_executed is always meaningful
        # and total_trades matches the count in the Trade Audit.

        commission_note = (
            f" commission=${open_commission:.2f}" if open_commission > 0 else ""
        )
        label = (
            "bull-put" if position["option_type"] == "P" else "bear-call"
        )
        leg_letter = position["option_type"]
        self.status_update.emit(
            f"📈 OPEN {label} spread #{position['id']} {self.UNDERLYING_SYMBOL} {spread['expiration']} "
            f"{leg_letter}{spread['short_strike']:.0f}/{spread['long_strike']:.0f} "
            f"×{qty} credit=${credit_dollars:,.2f} max_loss=${max_loss_dollars:,.0f}"
            f"{commission_note}"
        )
        self._save_state()
        return True

    def _close_paper_credit_spread(
        self,
        position: dict,
        debit_to_close: float,
        reason: str,
        closer: str = "",
    ) -> None:
        """Close an open spread at *debit_to_close* (per contract, dollars)."""
        qty = position["qty"]
        credit_received = position["credit"] * 100.0 * qty
        debit_paid = debit_to_close * 100.0 * qty
        close_commission = self._spread_commission(qty)
        # Realised P&L net of the closing-side commission. The opening-side
        # commission was already deducted from cash at open, so it's baked
        # into the cash balance (not double-counted here).
        realized = credit_received - debit_paid - close_commission

        self._cash -= debit_paid + close_commission
        self._total_realized_pnl += realized
        self._total_commissions += close_commission
        # Record into rolling history for Kelly sizing (cap by KELLY_HISTORY_MAX).
        self._spread_pnl_history.append(realized)
        if len(self._spread_pnl_history) > self.KELLY_HISTORY_MAX:
            self._spread_pnl_history.pop(0)
        self._trades_executed += 1
        if realized > 0:
            self._winning_trades += 1
            self._consecutive_losses = 0
        else:
            self._losing_trades += 1
            self._consecutive_losses += 1
            try:
                threshold = int(
                    os.environ.get("TRADOV_LOSS_COOLDOWN_COUNT", "3")
                )
                cooldown_secs = float(
                    os.environ.get("TRADOV_LOSS_COOLDOWN_SECONDS", "1800")
                )
            except (TypeError, ValueError):
                threshold, cooldown_secs = 3, 1800.0
            if threshold > 0 and self._consecutive_losses >= threshold:
                self._cooldown_until_ts = time.time() + cooldown_secs
                self.status_update.emit(
                    f"⏸️ Entry cooldown engaged — {self._consecutive_losses} "
                    f"consecutive losses, paused "
                    f"{cooldown_secs / 60:.0f} min"
                )
                self._consecutive_losses = 0  # reset after engaging

        self._open_spreads = [s for s in self._open_spreads if s["id"] != position["id"]]

        # Audit log entry — full lifecycle snapshot for the Trade Audit dialog.
        # Captures everything needed to reconstruct the trade decision and to
        # train ML models on actual realised outcomes (entry context, sizing,
        # close reason, P&L, hold time).
        opened_at = float(position.get("opened_at") or time.time())
        closed_at = time.time()
        hold_seconds = max(0.0, closed_at - opened_at)
        max_loss_dollars = (
            float(position["max_loss_per_contract"]) * 100.0 * qty
        )
        return_on_credit_pct = (
            (realized / credit_received * 100.0) if credit_received > 0 else 0.0
        )
        return_on_risk_pct = (
            (realized / max_loss_dollars * 100.0) if max_loss_dollars > 0 else 0.0
        )
        structure = position.get("structure") or (
            "BULL_PUT" if position.get("option_type") == "P" else "BEAR_CALL"
        )
        self._closed_trades.append({
            "id": position["id"],
            "structure": structure,
            "origin": position.get("origin", "AI"),
            "expiration": position["expiration"],
            "short_strike": float(position["short_strike"]),
            "long_strike": float(position["long_strike"]),
            "option_type": position.get("option_type", "P"),
            "direction": position.get("direction", "bullish"),
            "qty": qty,
            "credit": float(position["credit"]),
            "credit_received": credit_received,
            "debit_to_close": float(debit_to_close),
            "debit_paid": debit_paid,
            "wing_width": float(position.get("wing_width", 0.0)),
            "max_loss_per_contract": float(position["max_loss_per_contract"]),
            "max_loss_dollars": max_loss_dollars,
            "open_commission": self._spread_commission(qty),
            "close_commission": close_commission,
            "realized_pnl": realized,
            "return_on_credit_pct": return_on_credit_pct,
            "return_on_risk_pct": return_on_risk_pct,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "hold_seconds": hold_seconds,
            "close_reason": reason,
            "lifecycle_state": (
                closer
                if closer
                else (
                    StrategyLifecycleState.CLOSED_BY_RISK.value
                    if "stop-loss" in reason
                    else StrategyLifecycleState.CLOSED_BY_AI.value
                )
            ),
            "entry_atm_iv": position.get("entry_atm_iv"),
            "entry_iv_rank": position.get("entry_iv_rank"),
            "entry_spy": position.get("entry_spy"),
            "pivot_signal": position.get("pivot_signal"),
        })
        if len(self._closed_trades) > self.CLOSED_TRADES_MAX:
            self._closed_trades.pop(0)

        # Persist closed spread to paper DB (H05).
        if self._session_db is not None:
            try:
                self._session_db.record_trade(
                    symbol=self.UNDERLYING_SYMBOL,
                    trade_type="BTC",
                    side="buy",
                    quantity=int(qty),
                    price=float(debit_to_close),
                    commission=float(close_commission),
                    realized_pnl=float(realized),
                    strategy=structure,
                    expiration=str(position.get("expiration", "")),
                    strike=float(position.get("short_strike", 0.0)),
                    option_type=str(position.get("option_type", "P")).lower(),
                    notes=reason,
                )
            except Exception as _db_err:
                self.status_update.emit(f"⚠️ DB trade record failed: {_db_err}")

        commission_note = (
            f" commission=${close_commission:.2f}" if close_commission > 0 else ""
        )
        leg_letter = position.get("option_type", "P")
        self.status_update.emit(
            f"📉 CLOSE spread #{position['id']} {reason} "
            f"{leg_letter}{position['short_strike']:.0f}/{position['long_strike']:.0f} "
            f"P&L=${realized:+,.2f}{commission_note}"
        )
        self._save_state()
        self._emit_manual_close_position_updated(position, reason=reason, closer=closer)

    def _emit_manual_close_position_updated(
        self,
        position: dict,
        *,
        reason: str,
        closer: str,
    ) -> None:
        """Publish a manual-close POSITION_UPDATED event for D31 reentry embargoes."""
        if str(reason or "").strip().upper() != "MANUAL_CLOSE":
            return
        if str(closer or "").strip().upper() != "USER":
            return

        symbol = str(
            position.get("symbol")
            or position.get("underlying_symbol")
            or self.UNDERLYING_SYMBOL
        ).strip().upper()
        strategy_id = str(
            position.get("strategy_id")
            or position.get("strategy")
            or position.get("structure")
            or ""
        ).strip().lower()
        if not symbol or not strategy_id:
            return

        try:
            from Tradov.TradovA_Core.TradovA05_EventManager import (  # noqa: PLC0415
                EventType,
                get_event_manager,
            )

            get_event_manager().emit(
                EventType.POSITION_UPDATED,
                {
                    "symbol": symbol,
                    "strategy_id": strategy_id,
                    "strategy": strategy_id,
                    "status": "CLOSED",
                    "reason": "manual_close_dashboard",
                },
                source="TradovR08",
            )
        except Exception:
            pass

    def _mark_spreads_mtm(self) -> None:
        """MTM all open spreads against live mids; auto-close on exit rules.

        Exit rules (first to trigger wins):
          1. Take profit at >= 50% of max profit (credit).
          2. Stop loss when current debit >= ``TRADOV_SPREAD_STOP_LOSS_MULT``
             times the received credit (default 2.0 = -1x credit realized).
             Disable by setting the env var to 0.
          3. Defensive roll: when ``TRADOV_SPREAD_ROLL_ENABLED=1`` and the
             position is underwater with ``DTE <= TRADOV_SPREAD_ROLL_DTE``
             (default 2), close the current spread and attempt to open a new
             same-direction spread at the next listed expiration.
          4. EOD force-close: any 0-DTE spread still open at or after 3:55 PM
             ET on its expiry day is closed immediately to avoid pin risk and
             automatic exercise/assignment at the 4:15 PM options close.
          5. Force close when DTE <= 1 to avoid expiration risk (calendar guard
             that catches any position that survived through overnight).
        """
        if not self._open_spreads:
            return
        # Preserve the last in-session spread mark after the regular cash close.
        if not self._is_spy_mtm_marking_hours():
            return
        try:
            stop_mult = float(
                os.environ.get("TRADOV_SPREAD_STOP_LOSS_MULT", "2.0")
            )
        except (TypeError, ValueError):
            stop_mult = 2.0
        roll_enabled = (
            os.environ.get("TRADOV_SPREAD_ROLL_ENABLED", "0") == "1"
        )
        try:
            roll_dte = int(os.environ.get("TRADOV_SPREAD_ROLL_DTE", "2"))
        except (TypeError, ValueError):
            roll_dte = 2
        from datetime import date as _date
        today = _date.today()
        # Snapshot the list since we may mutate it during iteration.
        for position in list(self._open_spreads):
            exp = position["expiration"]
            try:
                y, m, dd = exp.split("-")
                dte = (_date(int(y), int(m), int(dd)) - today).days
            except (ValueError, AttributeError):
                dte = 0

            short_mid, long_mid = self._fetch_leg_mids(
                exp,
                "call" if position.get("option_type") == "C" else "put",
                position["short_strike"],
                position["long_strike"],
            )
            if short_mid is None or long_mid is None:
                continue  # skip this cycle, try again next poll

            debit_to_close = max(0.0, short_mid - long_mid)
            # Cache so _spreads_unrealized_pnl() can report without a refetch.
            position["last_debit"] = debit_to_close
            # Cache individual leg current mids for per-leg P&L in the display.
            position["last_short_mid"] = short_mid
            position["last_long_mid"] = long_mid
            # Transition ENTERED → MANAGED after first successful MTM cycle.
            if (
                position.get("lifecycle_state")
                == StrategyLifecycleState.ENTERED_BY_AI.value
            ):
                position["lifecycle_state"] = StrategyLifecycleState.MANAGED_BY_AI.value
            unrealized_per_contract = position["credit"] - debit_to_close
            take_profit_threshold = 0.5 * position["credit"]
            stop_loss_threshold = (
                stop_mult * position["credit"] if stop_mult > 0 else None
            )

            if unrealized_per_contract >= take_profit_threshold:
                self._close_paper_credit_spread(
                    position, debit_to_close, reason="(take-profit 50%)"
                )
            elif (
                stop_loss_threshold is not None
                and debit_to_close >= stop_loss_threshold
            ):
                self._close_paper_credit_spread(
                    position,
                    debit_to_close,
                    reason=f"(stop-loss {stop_mult:.1f}x credit)",
                )
            elif (
                roll_enabled
                and dte <= roll_dte
                and unrealized_per_contract < 0
            ):
                # Roll the losing position forward: close at current debit,
                # then attempt to open a same-direction spread at the next
                # listed expiration. Rolling routes through _try_open_spread
                # so every gate (IV / regime / Greeks / cooldown) still
                # applies — caller is responsible for observing refusals.
                direction = position.get("direction") or (
                    "bullish" if position.get("option_type") == "P" else "bearish"
                )
                self._close_paper_credit_spread(
                    position,
                    debit_to_close,
                    reason=f"(roll DTE={dte})",
                )
                # Need a fresh spot for re-entry. Reuse last price history.
                if self._price_history:
                    spy_spot = self._price_history[-1]
                    reopened = self._try_open_spread(direction, spy_spot)
                    if reopened:
                        self.status_update.emit(
                            f"🔁 Rolled {direction} spread forward from "
                            f"DTE={dte}"
                        )
            elif dte <= 1:
                # EOD intraday guard for 0-DTE: force-close by 3:55 PM ET on
                # expiry day to avoid pin risk and auto exercise at 4:15 PM.
                # For 1-DTE positions (expiring tomorrow) this remains a
                # calendar-day guard — they are not affected by the time check.
                if dte == 0:
                    from zoneinfo import ZoneInfo
                    et_now = datetime.now(ZoneInfo("America/New_York"))
                    eod_cutoff = et_now.replace(hour=15, minute=55, second=0, microsecond=0)
                    if et_now >= eod_cutoff:
                        self._close_paper_credit_spread(
                            position,
                            debit_to_close,
                            reason=f"(0-DTE EOD force-close {et_now.strftime('%H:%M')} ET)",
                        )
                    # Before 3:55 PM the position is allowed to keep running.
                else:
                    self._close_paper_credit_spread(
                        position, debit_to_close, reason=f"(DTE={dte} force-close)"
                    )

    def _is_spy_mtm_marking_hours(self, now: datetime | None = None) -> bool:
        """Return whether paper spread MTM should keep updating."""
        try:
            current_dt = now if now is not None else datetime.now(UTC)
            return bool(TradingHours().is_regular_hours(current_dt))
        except Exception:
            return True

    def _spreads_unrealized_pnl(self) -> float:
        """Best-effort unrealized P&L across all open spreads (last MTM refs)."""
        # Uses the ``last_debit`` cached by _mark_spreads_mtm(). Positions that
        # have not yet been MTM'd this session contribute 0.
        total = 0.0
        for p in self._open_spreads:
            debit = p.get("last_debit")
            if debit is None:
                continue
            total += (p["credit"] - debit) * 100.0 * p["qty"]
        return total

    def _shadow_log_credit_spread(self, spy_price: float) -> None:
        """Phase 2 shadow: log the spread we *would* open. No orders placed.

        Controlled by ``TRADOV_OPTIONS_SHADOW=1`` (default off). Disabled
        automatically when ``TRADOV_OPTIONS_LIVE_PAPER=1`` (redundant then).
        """
        if os.environ.get("TRADOV_OPTIONS_SHADOW", "0") != "1":
            return
        if os.environ.get("TRADOV_OPTIONS_LIVE_PAPER", "0") == "1":
            return
        spread = self._select_credit_spread(spy_price)
        if spread is None:
            return
        max_loss = spread["max_loss_per_contract"]
        self.status_update.emit(
            f"🔎 [SHADOW] Bull-put spread {self.UNDERLYING_SYMBOL} {spread['expiration']} "
            f"P{spread['short_strike']:.0f}/{spread['long_strike']:.0f} "
            f"credit≈${spread['credit']:.2f} max_loss≈${max_loss:.0f}/contract "
            f"(DTE={spread['dte']})"
        )

    def _execute_paper_buy(self, fill_price: float):
        """Execute a paper buy — up to 100 shares of the configured underlying."""
        shares = 100
        cost = shares * fill_price
        commission = 0.0

        # Risk check: max buying power % of initial capital
        max_bp_pct = self._get_risk_limit("max_buying_power", 100.0)
        max_spend = self._initial_capital * (max_bp_pct / 100.0)
        if cost > max_spend:
            shares = int(max_spend / fill_price)
            if shares <= 0:
                self.status_update.emit(
                    f"⛔ BUY blocked — position size exceeds {max_bp_pct:.0f}% buying-power limit"
                )
                return
            cost = shares * fill_price

        if cost > self._cash:
            shares = int(self._cash / fill_price)
            if shares <= 0:
                return
            cost = shares * fill_price

        self._cash -= cost + commission
        self._position_qty += shares
        self._position_avg_price = fill_price
        self._total_commissions += commission
        self._trades_executed += 1

        self.status_update.emit(
            f"📈 BUY {shares} {self.UNDERLYING_SYMBOL} @ ${fill_price:.2f} | "
            f"Cost: ${cost:,.2f} | Cash: ${self._cash:,.2f}",
        )

    def _execute_paper_sell(self, fill_price: float):
        """Execute a paper sell — close entire position."""
        if self._position_qty <= 0:
            return

        shares = self._position_qty
        proceeds = shares * fill_price
        commission = 0.0

        pnl = (fill_price - self._position_avg_price) * shares - commission
        self._total_realized_pnl += pnl
        self._cash += proceeds - commission
        self._total_commissions += commission
        self._trades_executed += 1

        if pnl > 0:
            self._winning_trades += 1
        else:
            self._losing_trades += 1

        # Persist equity sell to paper DB (H05).
        if self._session_db is not None:
            try:
                self._session_db.record_trade(
                    symbol=self.UNDERLYING_SYMBOL,
                    trade_type="SELL",
                    side="sell",
                    quantity=shares,
                    price=fill_price,
                    commission=commission,
                    realized_pnl=pnl,
                    strategy="EquityMA",
                )
            except Exception as _db_err:
                pass  # Non-critical; do not interrupt execution flow

        self.status_update.emit(
            f"📉 SELL {shares} {self.UNDERLYING_SYMBOL} @ ${fill_price:.2f} | "
            f"P&L: ${pnl:+,.2f} | Cash: ${self._cash:,.2f}",
        )

        self._position_qty = 0
        self._position_avg_price = 0.0

    def _update_position_mtm(self, current_price: float):
        """Update peak equity and max drawdown."""
        equity = (
            self._cash
            + self._position_qty * current_price
            + self._spreads_unrealized_pnl()
        )
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        self._max_drawdown = max(self._max_drawdown, drawdown)

    def _emit_position_update(self, last: float, bid: float, ask: float):
        """Emit current position state to the dashboard."""
        unrealized_pnl = 0.0
        if self._position_qty > 0:
            unrealized_pnl = (last - self._position_avg_price) * self._position_qty

        # Phase 2: include MTM P&L of open credit spreads (cash already holds
        # the received credit; this is the premium-decay component).
        spreads_unrealized = self._spreads_unrealized_pnl()
        unrealized_pnl += spreads_unrealized
        equity = self._cash + self._position_qty * last + spreads_unrealized

        # Per-spread detail rows for the dashboard "Spreads & Vol" widget.
        spreads_detail = []
        for p in self._open_spreads:
            qty = int(p["qty"])
            credit_per = float(p["credit"])
            debit_per = float(p.get("last_debit", credit_per))  # if never MTM'd, shows $0 MTM
            mtm_pnl = (credit_per - debit_per) * 100.0 * qty
            spreads_detail.append({
                "id": p["id"],
                "expiration": p["expiration"],
                "short_strike": float(p["short_strike"]),
                "long_strike": float(p["long_strike"]),
                "qty": qty,
                "credit": credit_per,
                "debit": debit_per,
                "mtm_pnl": mtm_pnl,
                "max_loss_per_contract": float(p["max_loss_per_contract"]),
                "structure": p.get(
                    "structure",
                    "BULL_PUT" if p.get("option_type") == "P" else "BEAR_CALL",
                ),
                "origin": p.get("origin", "AI"),
                "lifecycle_state": p.get(
                    "lifecycle_state",
                    StrategyLifecycleState.MANAGED_BY_AI.value,
                ),
                "opened_at": float(p.get("opened_at") or 0.0),
                "option_type": p.get("option_type", "P"),
                "direction": p.get("direction", "bullish"),
                # Per-leg entry/current mids for the Orders & Positions COST/P&L columns.
                "short_entry_mid": p.get("short_entry_mid"),
                "long_entry_mid": p.get("long_entry_mid"),
                "last_short_mid": p.get("last_short_mid"),
                "last_long_mid": p.get("last_long_mid"),
            })

        self.position_update.emit({
            "spy_last": last,
            "spy_bid": bid,
            "spy_ask": ask,
            "position_qty": self._position_qty,
            "position_avg_price": self._position_avg_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": self._total_realized_pnl,
            "cash": self._cash,
            "equity": equity,
            "initial_capital": self._initial_capital,
            "open_spreads": len(self._open_spreads),
            "open_spreads_detail": spreads_detail,
            "spreads_unrealized_pnl": spreads_unrealized,
            "atm_iv": self._last_atm_iv,
            "iv_rank": self._last_iv_rank,
            # Phase 3: portfolio-aggregate Greeks across open spreads.
            "portfolio_greeks": self._portfolio_greeks(),
            # Phase 5: closed-trade audit log (full lifecycle snapshots).
            # The dashboard caches the latest copy and offers it via the
            # Trade Audit dialog. Capped at CLOSED_TRADES_MAX entries.
            "closed_trades": list(self._closed_trades),
            "closed_trades_count": len(self._closed_trades),
            # Armed-candidate: a blocked-but-waiting setup shown in the
            # dashboard as ARMED BY AI until gates clear or TTL expires.
            "armed_candidate": (
                {
                    "direction": self._armed_candidate["direction"],
                    "structure": (
                        "BULL_PUT"
                        if self._armed_candidate["direction"] == "bullish"
                        else "BEAR_CALL"
                    ),
                    "spread": dict(self._armed_candidate["spread"]),
                    "blocked_reason": self._armed_candidate["blocked_reason"],
                    "armed_at": self._armed_candidate["armed_at"],
                    "lifecycle_state": StrategyLifecycleState.ARMED_BY_AI.value,
                }
                if self._armed_candidate is not None
                else None
            ),
        })

    @Slot(str)
    def request_close_spread(self, spread_id: str) -> None:
        """Close an open spread by ID on request from the GUI (manual close).

        Finds the spread with the matching ID and closes it at the current
        last-mid debit (best estimate of cost-to-close).  Emits a status
        update so the operator can see the manual close in the log.

        This method is called via Qt's invokeMethod / direct connection from
        the dashboard; it runs in the worker's thread because the worker lives
        in its own QThread.
        """
        target = next(
            (s for s in self._open_spreads if str(s.get("id", "")) == str(spread_id)),
            None,
        )
        if target is None:
            self.status_update.emit(f"⚠️ Manual close: spread {spread_id} not found")
            return
        # Estimate debit to close as last_short_mid + last_long_mid (buy back short,
        # sell back long).  Fall back to credit * 0.5 if marks are unavailable.
        last_short = target.get("last_short_mid") or 0.0
        last_long  = target.get("last_long_mid")  or 0.0
        debit = last_short - last_long if (last_short > 0 and last_long > 0) else (
            float(target.get("credit", 0.0)) * 0.50
        )
        debit = max(0.0, debit)
        structure = str(target.get("structure") or "SPREAD")
        self.status_update.emit(
            f"🖱️ Manual close requested — {structure} id={spread_id} debit=${debit:.2f}"
        )
        self._close_paper_credit_spread(target, debit, reason="MANUAL_CLOSE", closer="USER")

    def _emit_metrics(self):
        """Emit performance metrics for the paper P&L widget."""
        equity = self._cash
        if self._position_qty > 0 and self._price_history:
            equity += self._position_qty * self._price_history[-1]
        equity += self._spreads_unrealized_pnl()

        total_return = equity - self._initial_capital
        return_pct = (total_return / self._initial_capital) * 100 if self._initial_capital > 0 else 0  # noqa: E501
        win_rate = (
            self._winning_trades / self._trades_executed
            if self._trades_executed > 0 else 0
        )

        self.metrics_update.emit({
            "total_return": f"{return_pct:.2f}%",
            "max_drawdown": f"{self._max_drawdown:.4f}",
            "win_rate": f"{win_rate:.4f}",
            "total_trades": str(self._trades_executed),
            "winning_trades": str(self._winning_trades),
            "losing_trades": str(self._losing_trades),
            "realized_pnl": f"${self._total_realized_pnl:+,.2f}",
            "initial_capital": f"{self._initial_capital:.2f}",
            "equity": f"${equity:,.2f}",
        })


__all__ = ["PaperTradingQtWorker"]
