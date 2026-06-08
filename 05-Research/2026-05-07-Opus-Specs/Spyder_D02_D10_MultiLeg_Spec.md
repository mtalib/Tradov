# Spec: D02 IronCondor + D10 IronButterfly — Multi-Leg Remediation

**Files:**
- `Tradov/TradovD_Strategies/TradovD02_IronCondor.py`
- `Tradov/TradovD_Strategies/TradovD10_IronButterfly.py`

**Status:** Both modules grade C — architectural contract violations, doc drift, silent-data-fabrication bugs, and a mathematically broken strike-scoring function in D02.

**Read first:** `Tradov_Strategy_Audit_Master_Plan.md` — sections "Cross-cutting decisions required" answers all three of the open questions before this spec can be executed.

---

## 1. Issue inventory

### 1.1 Shared issues (apply to both D02 and D10)

| ID | Severity | Description |
|---|---|---|
| MULTILEG-01 | P0 | `generate_signals()` returns `[]` unconditionally — sync `BaseStrategy` contract is dead code |
| MULTILEG-02 | P1 | Header docstring references `D26_MultiLegStrategyCoordinator` but import is `TradovD32_MultiLegStrategyCoordinator` |
| MULTILEG-03 | P0 | Silent fallback to synthetic IV: `market_data.get('iv', pd.Series([0.20]))` and `pd.Series([0.20] * 100)` fabricate "good setup" recommendations from fake data |
| MULTILEG-04 | P2 | Several `except Exception` blocks return defaults that look like real analysis (e.g. `iv_rank: 50.0`, `confidence_score: 0.0`) — production failures masquerade as "neutral analysis" |
| MULTILEG-05 | P2 | `active_setups` list is unbounded; never trimmed |
| MULTILEG-06 | P2 | `analyze_*_opportunity` is `async` but `generate_signals` is sync — calls into the analysis from non-async paths fail silently |

### 1.2 D02-specific issues

| ID | Severity | Description |
|---|---|---|
| IC-01 | P1 | `_select_best_short_strike` scoring formula is dimensionally broken — volume dominates ~10× over the intended "0.4/0.3/0.3" weighting due to no normalisation |
| IC-02 | P3 | `_validate_iron_condor_strikes` has a stranded `try/except` block after a `return` — unreachable code, looks like a merge artifact |

### 1.3 D10-specific issues

| ID | Severity | Description |
|---|---|---|
| IB-01 | P1 | `_analyze_time_decay_potential` uses `estimated_theta = current_iv * 0.1` — a placeholder presented as analysis |
| IB-02 | P2 | `_find_optimal_wing_width` averages upper/lower widths but only validates the average — a 4/16 asymmetric wing passes as a "valid" 10-wide butterfly |
| IB-03 | P2 | `IB_ATM_TOLERANCE = 0.50` doesn't account for SPY's strike grid (0DTE = $1, longer = $5) — legitimate setups can be rejected for being on the grid |

---

## 2. Implementation plan

### 2.1 STEP 1 — Resolve coordinator name (MULTILEG-02)

Per master plan Decision 1, the canonical name is **`TradovD32_MultiLegStrategyCoordinator`**.

#### D02 — find and replace

In `TradovD02_IronCondor.py` header docstring (lines ~17–35):

**Find:**
```
CONSOLIDATION UPDATE:
    Generic multi-leg infrastructure REMOVED and consolidated into D26_MultiLegStrategyCoordinator.
```

**Replace:**
```
CONSOLIDATION UPDATE:
    Generic multi-leg infrastructure REMOVED and consolidated into D32_MultiLegStrategyCoordinator.
```

**Find** (six occurrences of `Now in D26`):
```
    • Generic multi-leg order management - Now in D26
    • Combined Greeks calculations - Now in D26
    • Multi-leg position sizing - Now in D26
    • Generic P&L calculations - Now in D26
    • Position group validation - Now in D26
```

**Replace:**
```
    • Generic multi-leg order management - Now in D32
    • Combined Greeks calculations - Now in D32
    • Multi-leg position sizing - Now in D32
    • Generic P&L calculations - Now in D32
    • Position group validation - Now in D32
```

Also replace any inline references to "D26" inside method docstrings (search the whole file for the literal string `D26` and replace with `D32`).

In the class docstring of `IronCondorStrategy`:

**Find:**
```
    the consolidated multi-leg coordinator (D26) for infrastructure operations.
```

**Replace:**
```
    the consolidated multi-leg coordinator (D32) for infrastructure operations.
```

In `get_strategy_performance()`:

**Find:**
```python
            'consolidation_status': 'Infrastructure moved to D26',
```

**Replace:**
```python
            'consolidation_status': 'Infrastructure moved to D32',
```

#### D10 — apply the identical pattern

Repeat the same six string replacements in `TradovD10_IronButterfly.py`. The string content is identical except where the strategy is named (e.g. `Iron Condor` vs `Iron Butterfly`). Search the whole file for the literal `D26` and replace with `D32`.

### 2.2 STEP 2 — Restore `generate_signals` contract (MULTILEG-01, MULTILEG-06)

Per master plan Decision 2, **Option A** (sync wrapper around async analysis) is the chosen path.

#### D02 — replace the placeholder `generate_signals`

**Find** (the entire current method, lines ~199–207):
```python
    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """Legacy adapter for BaseStrategy contract.

        Iron Condor evaluation currently runs through dedicated async analysis and
        coordinator pathways; this sync hook returns no direct entry signals.
        """
        return []
```

**Replace with:**
```python
    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """
        Sync entry point for the BaseStrategy contract.

        Bridges to the async ``analyze_iron_condor_opportunity`` analysis and
        converts a successful analysis into one or more ``TradingSignal``
        objects. Returns an empty list on insufficient data, unsuitable
        market conditions, or analysis failure.

        The sync bridge uses ``asyncio.run`` when no event loop is running,
        and ``asyncio.run_coroutine_threadsafe`` when invoked from inside a
        running loop (e.g., the live trading engine's main loop).

        Args:
            market_data: OHLCV DataFrame for the underlying. Must contain at
                minimum 'close' and 'iv' columns. An ``option_chain`` is not
                provided through this entry point; for chain-aware analysis
                callers should invoke ``analyze_iron_condor_opportunity``
                directly.

        Returns:
            List of ``TradingSignal`` objects. Empty when conditions are not
            met or when required inputs are missing.
        """
        try:
            if market_data is None or market_data.empty:
                return []

            analysis = self._run_analysis_sync(market_data)
            if analysis is None or not analysis.market_suitable:
                return []

            signal = self._build_signal_from_analysis(analysis, market_data)
            return [signal] if signal is not None else []

        except Exception as e:
            self.logger.error("IronCondor.generate_signals failed: %s", e, exc_info=True)
            return []

    def _run_analysis_sync(self, market_data: pd.DataFrame) -> "IronCondorAnalysis | None":
        """Run the async analysis from a sync context."""
        import asyncio

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            coro = self.analyze_iron_condor_opportunity(market_data, option_chain=None)

            if loop is None:
                return asyncio.run(coro)

            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=5.0)

        except Exception as e:
            self.logger.warning("IronCondor sync-bridge analysis failed: %s", e)
            return None

    def _build_signal_from_analysis(
        self,
        analysis: "IronCondorAnalysis",
        market_data: pd.DataFrame,
    ) -> "TradingSignal | None":
        """
        Convert an ``IronCondorAnalysis`` into a single ``TradingSignal``.

        Returns None if the analysis lacks the data needed to build a signal
        (e.g. no optimal strikes resolved). Strike-level execution detail is
        carried in ``signal.metadata`` for the multi-leg coordinator.
        """
        try:
            from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import (
                SignalStrength,
                SignalType,
                TradingSignal,
            )
            import uuid

            current_price = float(market_data["close"].iloc[-1])
            now = datetime.now(timezone.utc)

            score = analysis.confidence_score
            if score >= 0.8:
                strength = SignalStrength.VERY_STRONG
            elif score >= 0.6:
                strength = SignalStrength.STRONG
            elif score >= 0.4:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            metadata: dict[str, Any] = {
                "strategy_tag": "D02_IronCondor",
                "strategy_type": "iron_condor",
                "confidence_score": score,
                "iv_analysis": analysis.iv_analysis,
                "expected_move_analysis": analysis.expected_move_analysis,
                "trend_analysis": analysis.trend_analysis,
                "optimal_strikes": analysis.optimal_strikes,
                "setup_recommendation": analysis.setup_recommendation,
                "risk_warnings": analysis.risk_warnings,
                "min_dte": self.min_dte,
                "max_dte": self.max_dte,
                "profit_target": self.profit_target,
                "stop_loss_multiplier": self.stop_loss_multiplier,
            }

            return TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.SELL,  # IC is net-credit / short-vol
                symbol="SPY",
                strength=strength,
                confidence=score,
                entry_price=current_price,
                stop_loss=None,
                take_profit=None,
                position_size=1,
                timestamp=now,
                expires_at=None,
                metadata=metadata,
            )

        except Exception as e:
            self.logger.error("IronCondor._build_signal_from_analysis failed: %s", e)
            return None
```

#### D10 — apply the analogous pattern

Repeat the change in `TradovD10_IronButterfly.py`, substituting:

- `analyze_iron_condor_opportunity` → `analyze_iron_butterfly_opportunity`
- `IronCondorAnalysis` → `IronButterflyAnalysis`
- `_run_analysis_sync` body unchanged except the coro call
- `_build_signal_from_analysis` metadata block uses IB-specific fields:
  - `strategy_tag = "D10_IronButterfly"`
  - `strategy_type = "iron_butterfly"`
  - Replace `"trend_analysis"` with `"neutral_outlook_confirmed"` and `"atm_analysis"`
  - Replace `"optimal_strikes"` with `"atm_strike_recommendation"` and `"optimal_wing_width"`
  - Add `"time_decay_analysis": analysis.time_decay_analysis`

### 2.3 STEP 3 — Eliminate synthetic IV fallbacks (MULTILEG-03)

#### D02 — replace `_analyze_iv_for_iron_condor`

**Find** (the entire current method):
```python
    def _analyze_iv_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze implied volatility specifically for Iron Condor strategy"""
        try:
            # Get IV data (assuming it's in the market data)
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]

            # Calculate IV rank (simplified - would need historical IV data)
            iv_history = market_data.get('iv', pd.Series([0.20] * 100)).tail(252)  # 1 year
            iv_rank = (current_iv > iv_history).sum() / len(iv_history) * 100

            # Iron Condor IV analysis
            iv_analysis = {
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_suitable_for_ic': IC_MIN_IV_RANK <= iv_rank <= IC_MAX_IV_RANK,
                'iv_quality_score': self._calculate_iv_quality_score(current_iv, iv_rank),
                'iv_trend': 'rising' if current_iv > iv_history.mean() else 'falling'
            }

            return iv_analysis

        except Exception as e:
            self.logger.error("IV analysis failed: %s", e)
            return {
                'current_iv': 0.20,
                'iv_rank': 50.0,
                'iv_suitable_for_ic': False,
                'iv_quality_score': 0.0,
                'iv_trend': 'unknown'
            }
```

**Replace with:**
```python
    def _analyze_iv_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, float]:
        """
        Analyse implied volatility for Iron Condor entry.

        Returns a dict with ``iv_data_available`` set to False when the
        ``iv`` column is missing, NaN, or has insufficient history. Callers
        must check this flag before treating the rest of the dict as
        meaningful — *no synthetic IV defaults are returned*.
        """
        empty_result = {
            'iv_data_available': False,
            'current_iv': float('nan'),
            'iv_rank': float('nan'),
            'iv_suitable_for_ic': False,
            'iv_quality_score': 0.0,
            'iv_trend': 'unknown',
        }

        if 'iv' not in market_data.columns:
            self.logger.warning("IC IV analysis: 'iv' column missing from market_data")
            return empty_result

        iv_series = market_data['iv'].dropna()
        if iv_series.empty:
            self.logger.warning("IC IV analysis: 'iv' column is all-NaN")
            return empty_result

        try:
            current_iv = float(iv_series.iloc[-1])
            iv_history = iv_series.tail(252)

            # Need at least 20 valid IV samples to compute a meaningful rank
            if len(iv_history) < 20:
                self.logger.info(
                    "IC IV analysis: only %d IV samples — insufficient for rank",
                    len(iv_history),
                )
                return {**empty_result, 'current_iv': current_iv}

            iv_rank = float((current_iv > iv_history).sum() / len(iv_history) * 100)

            return {
                'iv_data_available': True,
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_suitable_for_ic': IC_MIN_IV_RANK <= iv_rank <= IC_MAX_IV_RANK,
                'iv_quality_score': self._calculate_iv_quality_score(current_iv, iv_rank),
                'iv_trend': 'rising' if current_iv > float(iv_history.mean()) else 'falling',
            }

        except Exception as e:
            self.logger.error("IC IV analysis failed: %s", e, exc_info=True)
            return empty_result
```

Then update `_assess_market_suitability_for_ic` to require `iv_data_available`:

**Find:**
```python
            iv_suitable = iv_analysis.get('iv_suitable_for_ic', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ic', False)
            trend_suitable = trend_analysis.get('trend_suitable_for_ic', False)

            return iv_suitable and move_suitable and trend_suitable
```

**Replace:**
```python
            iv_available = iv_analysis.get('iv_data_available', False)
            iv_suitable = iv_analysis.get('iv_suitable_for_ic', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ic', False)
            trend_suitable = trend_analysis.get('trend_suitable_for_ic', False)

            return iv_available and iv_suitable and move_suitable and trend_suitable
```

Apply the same treatment to `_analyze_expected_move_for_ic` — it also reads `market_data.get('iv', pd.Series([0.20]))`. Replace its IV access with the same explicit-check pattern, returning `expected_move_suitable_for_ic=False` when IV is unavailable.

#### D10 — apply the same pattern

Repeat for `TradovD10_IronButterfly.py`:

- Rewrite `_analyze_iv_for_iron_butterfly` using the same `empty_result` / explicit-check structure (substitute `iv_suitable_for_ib` and `IB_MIN_IV_RANK`/`IB_MAX_IV_RANK`).
- Rewrite `_analyze_expected_move_for_ib` to use the explicit IV check.
- Rewrite `_analyze_time_decay_potential` to use the explicit IV check (covered in 2.5 below).
- Update `_assess_market_suitability_for_ib` to require `iv_data_available`.

### 2.4 STEP 4 — Fix D02 strike-scoring formula (IC-01)

**Find** (in `_select_best_short_strike`):
```python
            # Score each candidate based on premium and liquidity
            candidates = candidates.copy()
            candidates['score'] = (
                candidates.get('bid', 0) * 0.4 +  # Premium weight
                candidates.get('volume', 0) * 0.0001 * 0.3 +  # Volume weight
                candidates.get('open_interest', 0) * 0.0001 * 0.3  # OI weight
            )
```

**Replace with:**
```python
            # Score each candidate based on premium and liquidity.
            # Each component is normalised to [0, 1] across candidates so the
            # weights (0.4 / 0.3 / 0.3) reflect actual contribution rather
            # than raw-magnitude domination.
            candidates = candidates.copy()

            def _norm(col: str) -> pd.Series:
                if col not in candidates.columns:
                    return pd.Series(0.0, index=candidates.index)
                values = candidates[col].astype(float).fillna(0.0)
                vmax = float(values.max())
                if vmax <= 0.0:
                    return pd.Series(0.0, index=candidates.index)
                return values / vmax

            bid_n = _norm('bid')
            vol_n = _norm('volume')
            oi_n = _norm('open_interest')

            candidates['score'] = bid_n * 0.4 + vol_n * 0.3 + oi_n * 0.3
```

### 2.5 STEP 5 — Replace D10 placeholder theta (IB-01)

**Find** (the entire current `_analyze_time_decay_potential`):
```python
    def _analyze_time_decay_potential(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze time decay potential for Iron Butterfly"""
        try:
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]

            # Estimate theta decay rate
            estimated_theta = current_iv * 0.1  # Simplified calculation
```

**Replace with:**
```python
    def _analyze_time_decay_potential(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """
        Analyse time-decay (theta) potential for Iron Butterfly.

        Preferred path: aggregate theta from the ATM-centred legs of the
        option chain. Fallback path: estimate from a closed-form Black-76
        approximation using current IV. Returns ``{'theta_data_available':
        False, ...}`` when neither path can produce a value.
        """
        empty_result = {
            'theta_data_available': False,
            'estimated_daily_theta': float('nan'),
            'optimal_close_dte': 15,
            'expected_total_decay': float('nan'),
            'decay_rate_suitable': False,
            'time_decay_quality_score': 0.0,
        }

        if 'iv' not in market_data.columns:
            self.logger.warning("IB time-decay: 'iv' column missing")
            return empty_result

        iv_series = market_data['iv'].dropna()
        if iv_series.empty:
            self.logger.warning("IB time-decay: 'iv' column is all-NaN")
            return empty_result

        try:
            current_iv = float(iv_series.iloc[-1])

            # Preferred: use the option chain's actual theta values for ATM legs.
            estimated_theta: float | None = None
            if option_chain is not None and not option_chain.empty:
                if 'theta' in option_chain.columns and 'delta' in option_chain.columns:
                    # ATM ≈ |delta| within 0.10 of 0.50 for calls / -0.50 for puts.
                    atm_legs = option_chain[
                        (option_chain['delta'].abs() >= 0.40)
                        & (option_chain['delta'].abs() <= 0.60)
                    ]
                    if not atm_legs.empty:
                        # Iron Butterfly is short ATM call + short ATM put;
                        # daily theta benefit ≈ |sum of leg thetas|.
                        leg_theta = float(atm_legs['theta'].abs().mean())
                        if leg_theta > 0.0:
                            estimated_theta = leg_theta

            # Fallback: closed-form approximation (Brenner-Subrahmanyam ATM).
            # ATM theta per day ≈ -S * sigma / (2 * sqrt(2 * pi * T_years))
            # For T=15/365 and S=$1 (normalised), this collapses to a
            # multiplier on sigma. We then scale by the strategy's
            # *fraction-of-underlying* assumption.
            if estimated_theta is None:
                T_years = 15.0 / 365.0
                approx = current_iv / (2.0 * np.sqrt(2.0 * np.pi * T_years))
                # Multiply by 0.01 to convert "fraction of underlying per day"
                # into a per-contract-per-$1-of-stock-price magnitude.
                estimated_theta = float(approx * 0.01)

            optimal_close_dte = 15
            expected_total_decay = estimated_theta * optimal_close_dte

            return {
                'theta_data_available': True,
                'estimated_daily_theta': estimated_theta,
                'optimal_close_dte': optimal_close_dte,
                'expected_total_decay': expected_total_decay,
                'decay_rate_suitable': estimated_theta >= IB_MIN_TIME_DECAY_RATE,
                'time_decay_quality_score': float(min(1.0, estimated_theta / 0.05)),
            }

        except Exception as e:
            self.logger.error("IB time-decay analysis failed: %s", e, exc_info=True)
            return empty_result
```

Then update the call site in `analyze_iron_butterfly_opportunity` to pass `option_chain`:

**Find:**
```python
            time_decay_analysis = self._analyze_time_decay_potential(market_data)
```

**Replace:**
```python
            time_decay_analysis = self._analyze_time_decay_potential(market_data, option_chain)
```

Update `_assess_market_suitability_for_ib` to also require `theta_data_available`:

**Find:**
```python
            outlook_suitable = neutral_outlook
            iv_suitable = iv_analysis.get('iv_suitable_for_ib', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ib', False)
            decay_suitable = time_decay_analysis.get('decay_rate_suitable', False)

            return outlook_suitable and iv_suitable and move_suitable and decay_suitable
```

**Replace:**
```python
            outlook_suitable = neutral_outlook
            iv_available = iv_analysis.get('iv_data_available', False)
            iv_suitable = iv_analysis.get('iv_suitable_for_ib', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ib', False)
            theta_available = time_decay_analysis.get('theta_data_available', False)
            decay_suitable = time_decay_analysis.get('decay_rate_suitable', False)

            return (
                outlook_suitable
                and iv_available
                and iv_suitable
                and move_suitable
                and theta_available
                and decay_suitable
            )
```

### 2.6 STEP 6 — Fix D10 wing-width asymmetry (IB-02)

**Find** (in `_find_optimal_wing_width`):
```python
            # Calculate actual wing width
            actual_upper_width = abs(upper_available - atm_strike)
            actual_lower_width = abs(atm_strike - lower_available)

            # Use symmetric width (average of both sides)
            actual_wing_width = (actual_upper_width + actual_lower_width) / 2

            return actual_wing_width if IB_WING_WIDTH_MIN <= actual_wing_width <= IB_WING_WIDTH_MAX else None  # noqa: E501
```

**Replace:**
```python
            # Calculate actual wing widths.
            actual_upper_width = abs(upper_available - atm_strike)
            actual_lower_width = abs(atm_strike - lower_available)

            # Iron Butterfly *requires* equidistant wings. Reject any
            # selection where upper and lower differ by more than one
            # strike-grid increment (assumed ≤ $1 here; tighten if needed).
            asymmetry = abs(actual_upper_width - actual_lower_width)
            if asymmetry > 1.0:
                self.logger.debug(
                    "IB wing rejected: asymmetric (upper=%.2f, lower=%.2f)",
                    actual_upper_width, actual_lower_width,
                )
                return None

            actual_wing_width = (actual_upper_width + actual_lower_width) / 2.0

            if not (IB_WING_WIDTH_MIN <= actual_wing_width <= IB_WING_WIDTH_MAX):
                return None

            return actual_wing_width
```

### 2.7 STEP 7 — Fix D10 ATM tolerance for variable strike grids (IB-03)

Add a constant and update `_find_optimal_atm_strike` to derive tolerance from grid spacing.

**Find** (in CONSTANTS section near `IB_ATM_TOLERANCE`):
```python
IB_ATM_TOLERANCE = 0.50                # ATM strike tolerance ($0.50)
```

**Replace:**
```python
IB_ATM_TOLERANCE = 0.50                # Default ATM strike tolerance ($0.50)
IB_ATM_TOLERANCE_AS_GRID_FRACTION = 0.6  # If grid > $1, accept up to 60% of grid spacing
```

**Find** (the entire current `_find_optimal_atm_strike`):
```python
    def _find_optimal_atm_strike(self, current_price: float,
                               option_chain: pd.DataFrame) -> float | None:
        """Find optimal ATM strike for Iron Butterfly center"""
        try:
            if option_chain is None or option_chain.empty:
                return None

            # Get available strikes
            available_strikes = sorted(option_chain['strike'].unique())

            # Find closest strike to current price
            closest_strike = min(available_strikes, key=lambda x: abs(x - current_price))

            # Ensure it's within ATM tolerance
            if abs(closest_strike - current_price) <= self.atm_tolerance:
                return closest_strike
            else:
                return None

        except Exception as e:
            self.logger.error("ATM strike selection failed: %s", e)
            return None
```

**Replace:**
```python
    def _find_optimal_atm_strike(
        self,
        current_price: float,
        option_chain: pd.DataFrame,
    ) -> float | None:
        """
        Find the optimal ATM strike for the centre of an Iron Butterfly.

        Tolerance scales with the underlying strike grid: SPY's 0DTE/short-
        dated chains use $1 grids and the default $0.50 tolerance is
        appropriate; longer-dated chains use $5 grids and a fixed $0.50
        tolerance would reject every legitimate ATM strike. The effective
        tolerance is therefore ``max(self.atm_tolerance, grid_spacing *
        IB_ATM_TOLERANCE_AS_GRID_FRACTION)``.
        """
        try:
            if option_chain is None or option_chain.empty:
                return None

            available_strikes = sorted(option_chain['strike'].unique())
            if len(available_strikes) < 2:
                return None

            # Infer grid spacing as the median gap between adjacent strikes
            # near the current price (resilient to occasional missing strikes).
            nearby = sorted(
                available_strikes,
                key=lambda x: abs(x - current_price),
            )[:7]
            nearby.sort()
            gaps = [nearby[i + 1] - nearby[i] for i in range(len(nearby) - 1)]
            grid_spacing = float(np.median(gaps)) if gaps else 1.0

            effective_tolerance = max(
                self.atm_tolerance,
                grid_spacing * IB_ATM_TOLERANCE_AS_GRID_FRACTION,
            )

            closest_strike = min(available_strikes, key=lambda x: abs(x - current_price))

            if abs(closest_strike - current_price) <= effective_tolerance:
                return float(closest_strike)

            self.logger.debug(
                "IB ATM strike rejected: closest=%.2f, price=%.2f, tol=%.2f, grid=%.2f",
                closest_strike, current_price, effective_tolerance, grid_spacing,
            )
            return None

        except Exception as e:
            self.logger.error("ATM strike selection failed: %s", e, exc_info=True)
            return None
```

### 2.8 STEP 8 — Bound `active_setups` (MULTILEG-05)

In both D02 and D10, add a max-length guard and emit a warning log when the cap is hit. The list is currently appended-to in `create_iron_*_position` but never trimmed.

#### Constant additions

D02 — add near other `IC_*` constants:
```python
IC_MAX_ACTIVE_SETUPS = 200             # Soft cap on active_setups list
```

D10 — add near other `IB_*` constants:
```python
IB_MAX_ACTIVE_SETUPS = 200             # Soft cap on active_setups list
```

#### Append-site update

In D02 `create_iron_condor_position`:

**Find:**
```python
            if position_id:
                self.active_setups.append(setup)
                self.strategy_state = IronCondorState.ACTIVE
                self.logger.info("✅ Iron Condor position created: %s", position_id)
```

**Replace:**
```python
            if position_id:
                if len(self.active_setups) >= IC_MAX_ACTIVE_SETUPS:
                    dropped = self.active_setups.pop(0)
                    self.logger.warning(
                        "active_setups cap reached (%d) — dropping oldest setup",
                        IC_MAX_ACTIVE_SETUPS,
                    )
                    del dropped
                self.active_setups.append(setup)
                self.strategy_state = IronCondorState.ACTIVE
                self.logger.info("✅ Iron Condor position created: %s", position_id)
```

D10 — same pattern with `IB_MAX_ACTIVE_SETUPS` and `IronButterflyState.ACTIVE`.

### 2.9 STEP 9 — Remove unreachable code in D02 (IC-02)

**Find** in `_validate_iron_condor_strikes`:
```python
            # Check spread width balance (shouldn't be too imbalanced)
            width_ratio = max(put_width, call_width) / min(put_width, call_width)
            return width_ratio <= 2.0  # Maximum 2:1 ratio


        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("Strike validation failed: %s", e)
            return False
```

**Replace:**
```python
            # Check spread width balance (shouldn't be too imbalanced)
            width_ratio = max(put_width, call_width) / min(put_width, call_width)
            return width_ratio <= 2.0  # Maximum 2:1 ratio

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("Strike validation failed: %s", e)
            return False
```

(The change is purely whitespace — collapses the stranded blank line that visually separated the `return` from the `except`. The original `try` is unbroken; this removes the appearance of unreachable code without changing semantics.)

### 2.10 STEP 10 — Tighten exception messaging on default returns (MULTILEG-04)

Each `except Exception` block in D02 and D10 that returns a "looks-like-real-data" default must additionally set a sentinel field. The pattern is illustrated above in step 2.3 with `iv_data_available`. Apply the same pattern to:

**D02:**
- `_analyze_expected_move_for_ic` → add `'expected_move_data_available': bool`
- `_analyze_trend_for_iron_condor` → add `'trend_data_available': bool`

**D10:**
- `_analyze_atm_conditions` → add `'atm_data_available': bool`
- `_analyze_expected_move_for_ib` → add `'expected_move_data_available': bool`

The `_assess_market_suitability_for_*` methods must consult these flags before returning `True`.

---

## 3. Acceptance criteria

After implementation, **all** of the following must hold for both D02 and D10:

- [ ] `python -m py_compile` passes for both files.
- [ ] `ruff check` reports no new errors versus the pre-change baseline.
- [ ] `mypy --ignore-missing-imports` passes.
- [ ] No occurrence of the literal string `D26` remains in either file (verify with `grep -n D26`).
- [ ] No occurrence of `pd.Series([0.20]` remains in either file.
- [ ] `generate_signals(empty_df)` returns `[]` without raising.
- [ ] `generate_signals(df_without_iv_column)` returns `[]` without raising and logs a warning.
- [ ] `generate_signals(valid_df_with_iv)` returns a list (possibly empty) without raising.
- [ ] In D02, calling `_select_best_short_strike` on a synthetic `DataFrame` where `volume` ranges 0–500k and `bid` ranges 0–5 selects the highest-`bid` candidate when `volume` and `oi` are uniform — verifying the normalisation fix.
- [ ] In D10, `_find_optimal_wing_width` returns `None` when the available strikes produce an asymmetric pair (upper width != lower width by more than $1).
- [ ] In D10, `_find_optimal_atm_strike` accepts an ATM strike within $3 of price when the strike grid is $5.
- [ ] The `active_setups` list never exceeds `IC_MAX_ACTIVE_SETUPS` / `IB_MAX_ACTIVE_SETUPS` after repeated calls to `create_iron_*_position`.

---

## 4. Out of scope for this spec

- Modifying `BaseStrategy` or `MultiLegStrategyCoordinator`.
- Replacing the simplified IV-rank computation with a real historical-IV store. (Tracked separately; see master plan.)
- Backtesting validation of the post-fix strategies.
