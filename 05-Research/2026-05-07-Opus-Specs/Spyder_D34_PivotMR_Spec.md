# Spec: D34 PivotMeanReversion — Correctness & Performance Remediation

**File:** `Tradov/TradovD_Strategies/TradovD34_PivotMeanReversion.py`

**Status:** Module grade B+ — strongest of the five audited strategies. Issues are smaller but a couple are real correctness/perf bugs that will degrade behaviour in production.

**Read first:** `Tradov_Strategy_Audit_Master_Plan.md`.

---

## 1. Issue inventory

| ID | Severity | Description |
|---|---|---|
| PMR-01 | P1 | RSI curl confirmation is O(n²) per bar — recomputes full RSI 15× per candidate signal |
| PMR-02 | P1 | `update_five_min_close` is misleadingly named — called every bar with current close, not only on 5-minute boundaries |
| PMR-03 | P1 | VWAP NaN propagates silently into `check_vwap_target` — disables take-profit branch when no session bars exist |
| PMR-04 | P2 | Local reimplementations of RSI / ATR / VWAP duplicate functionality that exists (or should exist) in `TradovF20_Indicators` |
| PMR-05 | P2 | `_open_trade_states` cleanup depends entirely on `on_position_closed` being called — state leaks if the broker callback is missed |
| PMR-06 | P3 | `SIGNAL_EXPIRY_S = 120` represents ~17% of the 12-minute time-stop life; consider tightening |

---

## 2. Implementation plan

### 2.1 STEP 1 — Add a rolling RSI cache (PMR-01)

The current `_rsi_curl_confirms` calls `_compute_rsi(closes[:i])` 15 times per signal-candidate bar; each call is O(n). Replace with a single full-series RSI computation cached on the instance and refreshed once per `_refresh_bar_buffer`.

Add a new instance attribute alongside `self._bar_buffer` in `__init__`:

**Find:**
```python
        # --- State ---
        self._bar_buffer: list[IntradayBar] = []
        self._daily_pivots: Optional[DailyPivots] = None
        self._open_trade_states: dict[str, OpenTradeState] = {}
        self._trade_lock = threading.Lock()
```

**Replace:**
```python
        # --- State ---
        self._bar_buffer: list[IntradayBar] = []
        self._rsi_series: np.ndarray = np.array([], dtype=float)  # parallel to _bar_buffer
        self._daily_pivots: Optional[DailyPivots] = None
        self._open_trade_states: dict[str, OpenTradeState] = {}
        self._trade_lock = threading.Lock()
```

Add a new helper after `_compute_rsi`:

```python
def _rolling_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Compute Wilder's RSI as a full series aligned 1:1 with ``closes``.

    Returns ``np.nan`` for indices < period; valid values from index
    ``period`` onwards. O(n) — replaces the O(n²) per-bar recomputation
    pattern in ``_rsi_curl_confirms``.
    """
    n = len(closes)
    out = np.full(n, np.nan, dtype=float)
    if n < period + 1:
        return out

    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())

    # Wilder smoothing for the remainder.
    for i in range(period, n):
        if i == period:
            g, ll = avg_gain, avg_loss
        else:
            g = (avg_gain * (period - 1) + gains[i - 1]) / period
            ll = (avg_loss * (period - 1) + losses[i - 1]) / period
            avg_gain, avg_loss = g, ll
        if ll == 0:
            out[i] = 100.0
        else:
            rs = g / ll
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out
```

> **Implementer note:** validate against the existing `_compute_rsi` for at least three known inputs to ensure they agree at the final element. RSI implementations vary subtly (Wilder vs simple-MA); aim for parity with the current scalar function so existing trades' RSI values don't shift.

Update `_refresh_bar_buffer` to populate the cache:

**Find:**
```python
    def _refresh_bar_buffer(self, market_data: pd.DataFrame) -> None:
        """Rebuild _bar_buffer from market_data, keeping last 200 bars."""
        bars: list[IntradayBar] = []
        for ts, row in market_data.iterrows():
            dt = ts if isinstance(ts, datetime) else pd.Timestamp(ts).to_pydatetime()
            bars.append(IntradayBar(
                timestamp = dt,
                open      = float(row.get("open",  row.get("close", 0))),
                high      = float(row.get("high",  row.get("close", 0))),
                low       = float(row.get("low",   row.get("close", 0))),
                close     = float(row["close"]),
                volume    = float(row.get("volume", 1.0)),
            ))
        self._bar_buffer = bars[-200:]
```

**Replace:**
```python
    def _refresh_bar_buffer(self, market_data: pd.DataFrame) -> None:
        """
        Rebuild ``_bar_buffer`` from ``market_data``, keeping the last 200
        bars, and refresh the parallel ``_rsi_series`` cache.
        """
        bars: list[IntradayBar] = []
        for ts, row in market_data.iterrows():
            dt = ts if isinstance(ts, datetime) else pd.Timestamp(ts).to_pydatetime()
            bars.append(IntradayBar(
                timestamp=dt,
                open=float(row.get("open", row.get("close", 0))),
                high=float(row.get("high", row.get("close", 0))),
                low=float(row.get("low", row.get("close", 0))),
                close=float(row["close"]),
                volume=float(row.get("volume", 1.0)),
            ))
        self._bar_buffer = bars[-200:]

        # Refresh rolling RSI in O(n) — drives _rsi_curl_confirms in O(1)/bar.
        if self._bar_buffer:
            closes_arr = np.array([b.close for b in self._bar_buffer], dtype=float)
            self._rsi_series = _rolling_rsi(closes_arr, period=14)
        else:
            self._rsi_series = np.array([], dtype=float)
```

Replace `_rsi_curl_confirms` to use the cache:

**Find** (the entire current method body):
```python
    def _rsi_curl_confirms(self, direction: PivotDirection, rsi: float) -> bool:
        """
        Confirm RSI has reached an extreme AND is now curling back.

        For a fade-support (long) signal: RSI must have been ≤ 30 at some
        recent bar and is now reading > 30 (the curl-back confirmation).
        For a fade-resistance (short) signal: RSI must have reached ≥ 70 and
        is now < 70.

        Current bar-level implementation: the simplest proxy is to check
        whether RSI is within the "just-curled" band (30–38 for longs,
        62–70 for shorts).  A more rigorous implementation would track
        the RSI low/high across the last N bars using `_bar_buffer`.
        """
        if direction == PivotDirection.FADE_SUPPORT:
            # Oversold reached; now curling above 30
            closes = [b.close for b in self._bar_buffer]
            if len(closes) < 16:
                return rsi <= 38        # insufficient history — relax
            rsi_series = [_compute_rsi(closes[:i]) for i in range(len(closes) - 15, len(closes))]
            rsi_series = [r for r in rsi_series if not np.isnan(r)]
            was_oversold = any(r <= 30 for r in rsi_series)
            return was_oversold and rsi > 30

        if direction == PivotDirection.FADE_RESISTANCE:
            closes = [b.close for b in self._bar_buffer]
            if len(closes) < 16:
                return rsi >= 62
            rsi_series = [_compute_rsi(closes[:i]) for i in range(len(closes) - 15, len(closes))]
            rsi_series = [r for r in rsi_series if not np.isnan(r)]
            was_overbought = any(r >= 70 for r in rsi_series)
            return was_overbought and rsi < 70

        return False
```

**Replace:**
```python
    def _rsi_curl_confirms(self, direction: PivotDirection, rsi: float) -> bool:
        """
        Confirm RSI has reached an extreme AND is now curling back.

        - FADE_SUPPORT (long): RSI must have been ≤ 30 within the last 15
          bars and now reads > 30.
        - FADE_RESISTANCE (short): RSI must have been ≥ 70 within the last
          15 bars and now reads < 70.

        Backed by the ``_rsi_series`` cache populated in
        ``_refresh_bar_buffer``; O(1) per call.
        """
        if direction == PivotDirection.NONE:
            return False

        if self._rsi_series.size < 16:
            # Insufficient history — fall back to relaxed band proxy.
            if direction == PivotDirection.FADE_SUPPORT:
                return rsi <= 38
            return rsi >= 62

        # Last 15 bars (excluding current); strip NaNs.
        recent = self._rsi_series[-16:-1]
        recent = recent[~np.isnan(recent)]
        if recent.size == 0:
            return False

        if direction == PivotDirection.FADE_SUPPORT:
            return bool((recent <= 30).any()) and rsi > 30

        # FADE_RESISTANCE
        return bool((recent >= 70).any()) and rsi < 70
```

### 2.2 STEP 2 — Rename `update_five_min_close` and document semantics (PMR-02)

The method is called every bar with the current close. The current name implies it's only fed completed 5-minute bars. Rename to match the actual semantics and remove the misleading "5-min" naming throughout `OpenTradeState`.

**Find** in `OpenTradeState` dataclass:
```python
    # Current bars for 5-min close tracking
    _five_min_bar_close: float = 0.0

    def update_five_min_close(self, close: float) -> None:
        self._five_min_bar_close = close

    def check_time_stop(self, current_price: float, now: datetime) -> Optional[str]:
```

**Replace:**
```python
    # Most recent close observed by the exit-monitor; updated every bar.
    # Named generically because the orchestrator does not currently batch
    # to 5-minute boundaries — the underlying-stop check evaluates on
    # every bar's close. Tighten the cadence here if/when the caller
    # batches to true 5-minute closes.
    _last_close: float = 0.0

    def update_last_close(self, close: float) -> None:
        """Record the most recent close for downstream stop checks."""
        self._last_close = close

    def check_time_stop(self, current_price: float, now: datetime) -> Optional[str]:
```

**Find:**
```python
    def check_underlying_stop(self) -> Optional[str]:
        """Return exit reason if underlying price stop triggered, else None."""
        if self._five_min_bar_close == 0.0:
            return None
        close = self._five_min_bar_close
```

**Replace:**
```python
    def check_underlying_stop(self) -> Optional[str]:
        """
        Return an exit reason if the most-recent close has breached the
        underlying-price stop, else None.

        Note: the underlying stop is currently evaluated on every bar's
        close, *not* exclusively on completed 5-minute bars. This is
        defensible for SPY 1-minute data but be aware that the original
        spec language ("5-min close") is aspirational.
        """
        if self._last_close == 0.0:
            return None
        close = self._last_close
```

Update the two call sites in `should_exit_position` and `check_exit`:

**Find** (in `should_exit_position`):
```python
        # --- Exit C: Underlying price stop (5-min close) ---
        state.update_five_min_close(spot)   # every bar; strategy caller may batch
        reason = state.check_underlying_stop()
```

**Replace:**
```python
        # --- Exit C: Underlying price stop (most-recent close) ---
        state.update_last_close(spot)
        reason = state.check_underlying_stop()
```

**Find** (in `check_exit`):
```python
        spot = float(position.current_price)
        now  = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        state.update_five_min_close(spot)
```

**Replace:**
```python
        spot = float(position.current_price)
        now = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        state.update_last_close(spot)
```

### 2.3 STEP 3 — Guard VWAP NaN in exit checks (PMR-03)

When `_bar_session_bars()` returns empty (very early in the session, or any path that loses session bars), `_compute_session_vwap` returns NaN. `state.check_vwap_target(spot, NaN)` then silently disables the take-profit branch because both directional comparisons (`spot <= NaN` and `spot >= NaN`) are False.

**Find** (in `OpenTradeState.check_vwap_target`):
```python
    def check_vwap_target(self, current_spot: float, current_vwap: float) -> Optional[str]:
        """Return exit reason when SPY crosses the intraday VWAP (take-profit)."""
        if self.direction == PivotDirection.FADE_RESISTANCE:
            # We want spot to fall toward VWAP from above
            if current_spot <= current_vwap:
                return "vwap_take_profit"
        else:
            # We want spot to rise toward VWAP from below
            if current_spot >= current_vwap:
                return "vwap_take_profit"
        return None
```

**Replace:**
```python
    def check_vwap_target(self, current_spot: float, current_vwap: float) -> Optional[str]:
        """
        Return an exit reason when SPY crosses the intraday VWAP
        (take-profit), else None.

        If ``current_vwap`` is NaN (e.g. no session bars available) the
        check returns None explicitly — silently treating NaN as "no
        cross" would disable the take-profit branch without any log
        signal that it had been disabled.
        """
        import math
        if math.isnan(current_vwap):
            return None

        if self.direction == PivotDirection.FADE_RESISTANCE:
            # We want spot to fall toward VWAP from above
            if current_spot <= current_vwap:
                return "vwap_take_profit"
        else:
            # We want spot to rise toward VWAP from below
            if current_spot >= current_vwap:
                return "vwap_take_profit"
        return None
```

Add a single warning log at the call site so operators can detect the condition. In `should_exit_position`:

**Find:**
```python
        spot = market_data["close"].iloc[-1]
        now  = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())

        # --- Exit A: VWAP take-profit ---
        reason = state.check_vwap_target(spot, vwap)
```

**Replace:**
```python
        spot = market_data["close"].iloc[-1]
        now = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())

        if np.isnan(vwap):
            # Take-profit branch is disabled this bar; log once per minute
            # to avoid log spam.
            self.logger.debug(
                "PMR exit-check: VWAP unavailable for position %s — "
                "TP branch skipped this bar",
                state.position_id[:8],
            )

        # --- Exit A: VWAP take-profit ---
        reason = state.check_vwap_target(spot, vwap)
```

Apply the same guard in `check_exit`:

**Find:**
```python
        spot = float(position.current_price)
        now = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        state.update_last_close(spot)
```

**Replace:**
```python
        spot = float(position.current_price)
        now = datetime.now(tz=ET)
        vwap = _compute_session_vwap(self._bar_session_bars())
        if np.isnan(vwap):
            self.logger.debug(
                "PMR check_exit: VWAP unavailable for position %s — "
                "TP branch skipped this bar",
                state.position_id[:8],
            )
        state.update_last_close(spot)
```

### 2.4 STEP 4 — Consolidate indicators onto F20 (PMR-04)

The local `_compute_rsi`, `_compute_atr`, `_compute_session_vwap`, and `_compute_vwap_slope_bps_per_min` should ultimately live in `TradovF20_Indicators`. This is a two-phase change. **This spec performs Phase 1 only**; Phase 2 is a separate F20 spec.

**Phase 1 — wrap and re-export:** keep the local implementations as private aliases but mark them deprecated and route new code through F20 where F20 already provides an equivalent. ADX is already routed correctly; verify that `TradovF20_Indicators` exposes `RSI`, `ATR`, `VWAP`, `VWAPSlope`. If it does, add the import:

**Find** (in the `LOCAL IMPORTS` block):
```python
from Tradov.TradovF_Analysis.TradovF20_Indicators import ADX as _f20_adx
```

**Replace:**
```python
from Tradov.TradovF_Analysis.TradovF20_Indicators import ADX as _f20_adx

# Optional: prefer F20 for shared indicators when available. Falls back
# to local implementations to keep this module standalone-runnable.
try:
    from Tradov.TradovF_Analysis.TradovF20_Indicators import (  # noqa: F401
        RSI as _f20_rsi,
        ATR as _f20_atr,
    )
    _F20_INDICATORS_AVAILABLE = True
except ImportError:
    _F20_INDICATORS_AVAILABLE = False
```

> **Implementer note:** if `TradovF20_Indicators` does not currently export `RSI` and `ATR`, leave `_F20_INDICATORS_AVAILABLE = False` and the local implementations stay primary. Do **not** modify F20 as part of this spec.

Add a deprecation comment above each local implementation:

**Find:**
```python
def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI(period) from a sequence of close prices. Returns NaN if insufficient."""
```

**Replace:**
```python
# Deprecated local indicator implementation — kept for module standalone use.
# When TradovF20_Indicators.RSI is available, the rolling cache in
# `_refresh_bar_buffer` is the preferred path. This scalar helper is retained
# only for ad-hoc callers (e.g. debug scripts).
def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Compute RSI(period) from a sequence of close prices. Returns NaN if insufficient."""
```

Apply the same deprecation comment pattern to `_compute_atr`, `_compute_session_vwap`, and `_compute_vwap_slope_bps_per_min`.

### 2.5 STEP 5 — Add a state reaper (PMR-05)

`_open_trade_states` only shrinks via `on_position_closed`. If the broker callback is dropped, state leaks for the rest of the session. Add a reaper that runs at the top of each `generate_signals` call and evicts states older than a configurable horizon.

Add a constant near the others:

**Find:**
```python
# --- Position ---
DEFAULT_DTE_MAX  = 1          # prefer 0-DTE; fall back to 1-DTE
SIGNAL_EXPIRY_S  = 120        # signal valid for 2 minutes
```

**Replace:**
```python
# --- Position ---
DEFAULT_DTE_MAX  = 1          # prefer 0-DTE; fall back to 1-DTE
SIGNAL_EXPIRY_S  = 120        # signal valid for 2 minutes

# --- State hygiene ---
TRADE_STATE_REAP_HORIZON_MIN = 90   # evict OpenTradeState older than 90 min
```

Add a reaper method on `PivotMeanReversionStrategy`:

```python
    def _reap_stale_trade_states(self) -> None:
        """
        Evict ``OpenTradeState`` entries older than
        ``TRADE_STATE_REAP_HORIZON_MIN`` minutes.

        Defensive cleanup for the case where ``on_position_closed`` is not
        called by the broker callback chain. The reaper logs a warning per
        eviction so operators can investigate missed close callbacks.
        """
        now = datetime.now(tz=ET)
        horizon = timedelta(minutes=TRADE_STATE_REAP_HORIZON_MIN)

        with self._trade_lock:
            stale = [
                pid for pid, st in self._open_trade_states.items()
                if (now - st.entry_time) > horizon
            ]
            for pid in stale:
                self._open_trade_states.pop(pid, None)

        for pid in stale:
            self.logger.warning(
                "PMR state reaper: evicted stale trade state %s "
                "(>%d min since entry — close callback likely missed)",
                pid[:8], TRADE_STATE_REAP_HORIZON_MIN,
            )
```

Call the reaper from the top of `generate_signals`:

**Find:**
```python
    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate pivot mean-reversion signals from intraday bars.

        Args:
            market_data: DataFrame with columns (open, high, low, close, volume)
                         and a timezone-aware DatetimeIndex (UTC preferred).

        Returns:
            List of TradingSignal (may be empty).
        """
        if market_data.empty or len(market_data) < 2:
            return []
```

**Replace:**
```python
    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate pivot mean-reversion signals from intraday bars.

        Args:
            market_data: DataFrame with columns (open, high, low, close, volume)
                         and a timezone-aware DatetimeIndex (UTC preferred).

        Returns:
            List of TradingSignal (may be empty).
        """
        # Cleanup pass — evict any trade state whose close callback
        # was missed.
        self._reap_stale_trade_states()

        if market_data.empty or len(market_data) < 2:
            return []
```

### 2.6 STEP 6 — Adjust signal expiry (PMR-06)

Tighten signal expiry to a smaller fraction of the time-stop life. The current 120 s out of 720 s (12 min) means a signal can sit unactioned for ~17% of its useful life.

**Find:**
```python
SIGNAL_EXPIRY_S  = 120        # signal valid for 2 minutes
```

**Replace:**
```python
# Signal valid window. A PMR signal whose action lag exceeds ~10% of the
# time-stop life is materially stale. With a 12-min time stop, 60 s caps
# action lag at 8.3% of strategy life.
SIGNAL_EXPIRY_S  = 60         # signal valid for 1 minute
```

> **Implementer note:** if the engine routinely takes more than 60 s from signal emission to fill (e.g. multi-leg combos with wide quotes), revert this constant or make it config-driven. This change is conservative; flag it in the PR description for review.

---

## 3. Acceptance criteria

After implementation, **all** of the following must hold:

- [ ] `python -m py_compile TradovD34_PivotMeanReversion.py` passes.
- [ ] `ruff check TradovD34_PivotMeanReversion.py` reports no new errors.
- [ ] `mypy --ignore-missing-imports` passes.
- [ ] `_rsi_curl_confirms` no longer calls `_compute_rsi` in a loop. `grep -c "_compute_rsi" TradovD34_PivotMeanReversion.py` returns ≤ 1 (the function definition itself).
- [ ] No occurrence of the literal string `update_five_min_close` or `_five_min_bar_close` remains.
- [ ] `OpenTradeState.check_vwap_target(spot, float('nan'))` returns `None` for both directions.
- [ ] `should_exit_position` and `check_exit` both log a debug message when VWAP is NaN (verified by capturing logs in a synthetic test).
- [ ] `_reap_stale_trade_states` is called from the top of `generate_signals` (verified by reading the source).
- [ ] After registering a fake `OpenTradeState` with `entry_time = now - 91 minutes` and calling `generate_signals(empty_df)`, the state is removed and a warning is logged.
- [ ] `SIGNAL_EXPIRY_S == 60`.
- [ ] Performance smoke test: 1000 sequential `generate_signals` calls on a 200-bar buffer complete in < 1.0 s wall-clock on a typical workstation (was likely 3–5 s pre-fix due to RSI O(n²)).

---

## 4. Out of scope for this spec

- Modifying `TradovF20_Indicators` to expose RSI/ATR/VWAP if not already present. (Phase 2; separate F20 spec.)
- Modifying `TradovS08_PivotMeanReversionSignal`.
- Changing the time-stop or underlying-stop thresholds.
- Backtesting validation of the post-fix strategy.
