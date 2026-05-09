# Spec: D06 BullPutSpread + D07 BearCallSpread — Vertical Credit Spread Remediation

**Files:**
- `Spyder/SpyderD_Strategies/SpyderD06_BullPutSpread.py`
- `Spyder/SpyderD_Strategies/SpyderD07_BearCallSpread.py`

**Status:** Both modules grade B− — small but real bugs and a misleading docstring claim. They are mirror images of each other; every fix in D06 has a symmetric counterpart in D07.

**Read first:** `Spyder_Strategy_Audit_Master_Plan.md`.

---

## 1. Issue inventory (applies symmetrically to both modules)

| ID | Severity | Description |
|---|---|---|
| VS-01 | P1 | Docstring claims "tightens delta selection to the bullish/bearish range" but no delta-selection logic is implemented |
| VS-02 | P1 | 1-bar momentum filter with 0.001 threshold is essentially noise — coin-flip-grade signal rejection |
| VS-03 | P2 | `BULL_PUT_MAX_RSI` / `BEAR_CALL_MIN_RSI` and momentum thresholds are module constants but `create()` accepts kwargs that go unread |
| VS-04 | P3 | Divide-by-zero risk: `closes.iloc[-2]` is denominator with no zero-check |
| VS-05 | P3 | No NaN guard on `rsi.iloc[-1]` — a NaN reads as both `> 50` and `< 50` False, silently disabling the filter |
| VS-06 | P3 | Magic-number momentum threshold `0.001` is unitless and applies to whatever bar timeframe the data happens to have |

---

## 2. Implementation plan — D06 BullPutSpread

### 2.1 STEP 1 — Replace constants with parameterised, multi-bar momentum

**Find:**
```python
# ==============================================================================
# CONSTANTS
# ==============================================================================
BULL_PUT_MAX_RSI = 50          # Only enter when RSI is below neutral
BULL_PUT_MIN_MOMENTUM = 0.001  # Minimum upward price momentum (%)
```

**Replace:**
```python
# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default filter thresholds — overridable per-instance via config.
BULL_PUT_DEFAULT_MAX_RSI = 50           # Skip entry when RSI is overbought
BULL_PUT_DEFAULT_MIN_MOMENTUM = 0.0015  # Min cumulative return over lookback
BULL_PUT_DEFAULT_MOMENTUM_LOOKBACK = 5  # Bars over which to measure momentum
BULL_PUT_DEFAULT_TARGET_DELTA_RANGE = (-0.30, -0.15)  # Short-put delta range
```

### 2.2 STEP 2 — Read filter parameters from config in `__init__`

**Find:**
```python
        # Force bull-put-only mode
        config = {**config, "use_bull_puts": True, "use_bear_calls": False}
        super().__init__(event_manager, risk_profile, config)
        self.logger.info("BullPutSpreadStrategy initialized (bull-put-only mode)")
```

**Replace:**
```python
        # Force bull-put-only mode and merge user-supplied filter overrides.
        config = {**config, "use_bull_puts": True, "use_bear_calls": False}
        super().__init__(event_manager, risk_profile, config)

        self._max_rsi: float = float(
            config.get("max_rsi", BULL_PUT_DEFAULT_MAX_RSI)
        )
        self._min_momentum: float = float(
            config.get("min_momentum", BULL_PUT_DEFAULT_MIN_MOMENTUM)
        )
        self._momentum_lookback: int = max(
            2, int(config.get("momentum_lookback", BULL_PUT_DEFAULT_MOMENTUM_LOOKBACK))
        )
        # Tighter short-put delta range for a directional bull bias.
        # Forwarded to the parent strike-selection layer via config.
        self._target_delta_range: tuple[float, float] = tuple(  # type: ignore[assignment]
            config.get("target_delta_range", BULL_PUT_DEFAULT_TARGET_DELTA_RANGE)
        )
        # Make the parent see the bullish-bias delta range. Parent reads this
        # key during strike selection (CreditSpreadStrategy.STRIKE_DELTA_KEY).
        self.config["short_put_delta_range"] = self._target_delta_range

        self.logger.info(
            "BullPutSpreadStrategy initialized (bull-put-only mode) | "
            "max_rsi=%.1f, min_momentum=%.4f over %d bars, delta_range=%s",
            self._max_rsi, self._min_momentum, self._momentum_lookback,
            self._target_delta_range,
        )
```

> **Note for the implementer:** the line `self.config["short_put_delta_range"] = self._target_delta_range` assumes `CreditSpreadStrategy` reads this key during strike selection. If the parent uses a different key name, substitute it. If the parent has no such hook today, leave the key in place and a P1 follow-up TODO comment so the parent can be extended in a separate spec — do **not** modify `D03_CreditSpread` as part of this spec (it's out of scope per the master plan).

### 2.3 STEP 3 — Replace 1-bar momentum filter with NaN-safe multi-bar filter

**Find** the entire `generate_signals` method body up to the `super().generate_signals(market_data)` call:
```python
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bullish pre-filter ---
            if "rsi" in market_data.columns:
                latest_rsi = float(market_data["rsi"].iloc[-1])
                if latest_rsi > BULL_PUT_MAX_RSI:
                    self.logger.debug(
                        f"BullPutSpread: skipping — RSI {latest_rsi:.1f} > {BULL_PUT_MAX_RSI}"
                    )
                    return []

            if "close" in market_data.columns and len(market_data) >= 2:
                closes = market_data["close"]
                momentum = (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2])  # noqa: E501
                if momentum < BULL_PUT_MIN_MOMENTUM:
                    self.logger.debug(
                        f"BullPutSpread: skipping — momentum {momentum:.4f} below threshold"
                    )
                    return []

            # Delegate to parent which is restricted to bull-puts via config
            return super().generate_signals(market_data)
```

**Replace:**
```python
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bullish pre-filter: RSI gate ---
            if "rsi" in market_data.columns:
                rsi_raw = market_data["rsi"].iloc[-1]
                if pd.isna(rsi_raw):
                    self.logger.debug("BullPutSpread: skipping — RSI is NaN")
                    return []
                latest_rsi = float(rsi_raw)
                if latest_rsi > self._max_rsi:
                    self.logger.debug(
                        "BullPutSpread: skipping — RSI %.1f > %.1f",
                        latest_rsi, self._max_rsi,
                    )
                    return []

            # --- Bullish pre-filter: multi-bar momentum gate ---
            if "close" in market_data.columns:
                closes = market_data["close"].dropna()
                if len(closes) < self._momentum_lookback + 1:
                    self.logger.debug(
                        "BullPutSpread: skipping — only %d closes, need %d",
                        len(closes), self._momentum_lookback + 1,
                    )
                    return []

                base = float(closes.iloc[-(self._momentum_lookback + 1)])
                if base == 0.0:
                    self.logger.debug("BullPutSpread: skipping — base close is zero")
                    return []

                latest = float(closes.iloc[-1])
                momentum = (latest - base) / base
                if momentum < self._min_momentum:
                    self.logger.debug(
                        "BullPutSpread: skipping — %d-bar momentum %.4f < %.4f",
                        self._momentum_lookback, momentum, self._min_momentum,
                    )
                    return []

            # Delegate to parent which is restricted to bull-puts via config.
            return super().generate_signals(market_data)
```

### 2.4 STEP 4 — Update header docstring to reflect actual behaviour

**Find:**
```python
    Extends CreditSpreadStrategy with bull-put-only logic:
    - Disables bear call spread generation.
    - Tightens delta selection to the bullish range.
    - Requires RSI < 50 and positive price momentum for entry.
```

**Replace:**
```python
    Extends CreditSpreadStrategy with bull-put-only logic:
    - Disables bear call spread generation by forcing ``use_bear_calls=False``.
    - Forwards a bullish-bias short-put delta range
      (``BULL_PUT_DEFAULT_TARGET_DELTA_RANGE``) to the parent strike selector
      via the ``short_put_delta_range`` config key.
    - Requires RSI < ``max_rsi`` (default 50) and positive cumulative return
      over the configurable ``momentum_lookback`` (default 5 bars) above
      ``min_momentum`` (default 0.0015) for entry.
```

---

## 3. Implementation plan — D07 BearCallSpread (mirror)

Apply the same five steps to D07 with these substitutions:

| D06 → | D07 |
|---|---|
| `BULL_PUT_DEFAULT_MAX_RSI = 50` | `BEAR_CALL_DEFAULT_MIN_RSI = 50` |
| `BULL_PUT_DEFAULT_MIN_MOMENTUM = 0.0015` | `BEAR_CALL_DEFAULT_MAX_MOMENTUM = -0.0015` |
| `BULL_PUT_DEFAULT_MOMENTUM_LOOKBACK = 5` | `BEAR_CALL_DEFAULT_MOMENTUM_LOOKBACK = 5` |
| `BULL_PUT_DEFAULT_TARGET_DELTA_RANGE = (-0.30, -0.15)` | `BEAR_CALL_DEFAULT_TARGET_DELTA_RANGE = (0.15, 0.30)` |
| `self._max_rsi` | `self._min_rsi` |
| `self._min_momentum` | `self._max_momentum` |
| Config key `short_put_delta_range` | `short_call_delta_range` |
| Filter clause `latest_rsi > self._max_rsi` | `latest_rsi < self._min_rsi` |
| Filter clause `momentum < self._min_momentum` | `momentum > self._max_momentum` |
| Log strings | `"BearCallSpread: ..."` |

### 3.1 D07 STEP 1 — Constants

**Find:**
```python
# ==============================================================================
# CONSTANTS
# ==============================================================================
BEAR_CALL_MIN_RSI = 50          # Only enter when RSI is above neutral
BEAR_CALL_MAX_MOMENTUM = -0.001  # Maximum upward momentum (must be declining)
```

**Replace:**
```python
# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default filter thresholds — overridable per-instance via config.
BEAR_CALL_DEFAULT_MIN_RSI = 50           # Skip entry when RSI is oversold
BEAR_CALL_DEFAULT_MAX_MOMENTUM = -0.0015 # Max cumulative return over lookback
BEAR_CALL_DEFAULT_MOMENTUM_LOOKBACK = 5  # Bars over which to measure momentum
BEAR_CALL_DEFAULT_TARGET_DELTA_RANGE = (0.15, 0.30)  # Short-call delta range
```

### 3.2 D07 STEP 2 — `__init__`

**Find:**
```python
        # Force bear-call-only mode
        config = {**config, "use_bull_puts": False, "use_bear_calls": True}
        super().__init__(event_manager, risk_profile, config)
        self.logger.info("BearCallSpreadStrategy initialized (bear-call-only mode)")
```

**Replace:**
```python
        # Force bear-call-only mode and merge user-supplied filter overrides.
        config = {**config, "use_bull_puts": False, "use_bear_calls": True}
        super().__init__(event_manager, risk_profile, config)

        self._min_rsi: float = float(
            config.get("min_rsi", BEAR_CALL_DEFAULT_MIN_RSI)
        )
        self._max_momentum: float = float(
            config.get("max_momentum", BEAR_CALL_DEFAULT_MAX_MOMENTUM)
        )
        self._momentum_lookback: int = max(
            2, int(config.get("momentum_lookback", BEAR_CALL_DEFAULT_MOMENTUM_LOOKBACK))
        )
        self._target_delta_range: tuple[float, float] = tuple(  # type: ignore[assignment]
            config.get("target_delta_range", BEAR_CALL_DEFAULT_TARGET_DELTA_RANGE)
        )
        # Forwarded to the parent strike-selection layer.
        self.config["short_call_delta_range"] = self._target_delta_range

        self.logger.info(
            "BearCallSpreadStrategy initialized (bear-call-only mode) | "
            "min_rsi=%.1f, max_momentum=%.4f over %d bars, delta_range=%s",
            self._min_rsi, self._max_momentum, self._momentum_lookback,
            self._target_delta_range,
        )
```

### 3.3 D07 STEP 3 — `generate_signals` body

**Find:**
```python
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bearish pre-filter ---
            if "rsi" in market_data.columns:
                latest_rsi = float(market_data["rsi"].iloc[-1])
                if latest_rsi < BEAR_CALL_MIN_RSI:
                    self.logger.debug(
                        f"BearCallSpread: skipping — RSI {latest_rsi:.1f} < {BEAR_CALL_MIN_RSI}"
                    )
                    return []

            if "close" in market_data.columns and len(market_data) >= 2:
                closes = market_data["close"]
                momentum = (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2])  # noqa: E501
                if momentum > BEAR_CALL_MAX_MOMENTUM:
                    self.logger.debug(
                        f"BearCallSpread: skipping — momentum {momentum:.4f} above threshold"
                    )
                    return []

            # Delegate to parent which is restricted to bear-calls via config
            return super().generate_signals(market_data)
```

**Replace:**
```python
        try:
            if market_data is None or market_data.empty:
                return []

            # --- Bearish pre-filter: RSI gate ---
            if "rsi" in market_data.columns:
                rsi_raw = market_data["rsi"].iloc[-1]
                if pd.isna(rsi_raw):
                    self.logger.debug("BearCallSpread: skipping — RSI is NaN")
                    return []
                latest_rsi = float(rsi_raw)
                if latest_rsi < self._min_rsi:
                    self.logger.debug(
                        "BearCallSpread: skipping — RSI %.1f < %.1f",
                        latest_rsi, self._min_rsi,
                    )
                    return []

            # --- Bearish pre-filter: multi-bar momentum gate ---
            if "close" in market_data.columns:
                closes = market_data["close"].dropna()
                if len(closes) < self._momentum_lookback + 1:
                    self.logger.debug(
                        "BearCallSpread: skipping — only %d closes, need %d",
                        len(closes), self._momentum_lookback + 1,
                    )
                    return []

                base = float(closes.iloc[-(self._momentum_lookback + 1)])
                if base == 0.0:
                    self.logger.debug("BearCallSpread: skipping — base close is zero")
                    return []

                latest = float(closes.iloc[-1])
                momentum = (latest - base) / base
                if momentum > self._max_momentum:
                    self.logger.debug(
                        "BearCallSpread: skipping — %d-bar momentum %.4f > %.4f",
                        self._momentum_lookback, momentum, self._max_momentum,
                    )
                    return []

            # Delegate to parent which is restricted to bear-calls via config.
            return super().generate_signals(market_data)
```

### 3.4 D07 STEP 4 — Header docstring

**Find:**
```python
    Extends CreditSpreadStrategy with bear-call-only logic:
    - Disables bull put spread generation.
    - Tightens delta selection to the bearish range.
    - Requires RSI > 50 and negative price momentum for entry.
```

**Replace:**
```python
    Extends CreditSpreadStrategy with bear-call-only logic:
    - Disables bull put spread generation by forcing ``use_bull_puts=False``.
    - Forwards a bearish-bias short-call delta range
      (``BEAR_CALL_DEFAULT_TARGET_DELTA_RANGE``) to the parent strike selector
      via the ``short_call_delta_range`` config key.
    - Requires RSI > ``min_rsi`` (default 50) and negative cumulative return
      over the configurable ``momentum_lookback`` (default 5 bars) below
      ``max_momentum`` (default -0.0015) for entry.
```

---

## 4. Acceptance criteria

After implementation, **all** of the following must hold for both D06 and D07:

- [ ] `python -m py_compile` passes for both files.
- [ ] `ruff check` reports no new errors.
- [ ] `mypy --ignore-missing-imports` passes.
- [ ] `generate_signals(empty_df)` returns `[]` without raising.
- [ ] `generate_signals(df_with_nan_rsi)` returns `[]` without raising and logs a `"RSI is NaN"` debug message.
- [ ] `generate_signals(df_where_close_lookback_is_zero)` returns `[]` without raising — no `ZeroDivisionError`.
- [ ] `generate_signals(df_with_only_3_closes)` and `momentum_lookback=5` returns `[]` without raising — insufficient-history path covered.
- [ ] Module-level constants `BULL_PUT_MAX_RSI`, `BULL_PUT_MIN_MOMENTUM`, `BEAR_CALL_MIN_RSI`, `BEAR_CALL_MAX_MOMENTUM` no longer exist; they are replaced by `*_DEFAULT_*` constants.
- [ ] After construction with `cls.create(em, rp, max_rsi=45, min_momentum=0.005, momentum_lookback=10)` (D06) the corresponding instance attributes reflect the supplied values.
- [ ] Header docstring text in each module is updated and no longer claims behaviour the code does not implement.

---

## 5. Out of scope for this spec

- Changes to `SpyderD03_CreditSpread` (the parent). If the parent does not honour `short_put_delta_range` / `short_call_delta_range`, that is a separate D03 spec.
- Persistence of overrides to a config file.
- Backtesting validation of the new momentum thresholds.
