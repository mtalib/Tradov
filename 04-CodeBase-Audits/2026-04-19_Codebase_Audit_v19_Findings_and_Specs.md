# Spyder Codebase Audit v19 — Findings & Coding Agent Specs

> **Date:** 2026-04-19  
> **Branch audited:** `fix/audit-v14-all`  
> **Scope:** Full system readiness review — trade trigger/close wiring, N04 exploitation, anomalies, improvements.

---

## 1. Trade Signal Flow — Confirmed Architecture

The complete signal-to-execution path is working as follows. **This flow is intact and correct.**

```
C27_MassiveClient  (WebSocket stream)
  └─► C01_DataFeed.normalise()
       └─► EventType.MARKET_DATA  (published)
            └─► D31._on_market_data_event()
                 ├─ stores event.data → market_data_cache
                 └─ for each strategy: strategy.process_market_data(market_df)
                       └─ [strategy internal logic emits EventType.STRATEGY_SIGNAL]
                            └─► D31._on_strategy_signal()
                                 ├─ gate: _paused_kill / _paused_stale → drop
                                 ├─ dry_run self-test short-circuit
                                 ├─ builds RiskValidationRequest (E00 typed boundary)
                                 ├─ calls E01.validate_signal() → Y03 veto
                                 └─ if approved → D31._dispatch_approved_signal()
                                       ├─ Path A: _live_engine.execute_order()
                                       │    └─ R04: regime gate → B02.submit_order()
                                       │         └─ B40 TradierClient (live API)
                                       └─ Path B: _order_manager.submit_order() (fallback)
```

**Trade close paths:**
- **E11 MaxLossProtection**: publishes `EMERGENCY` → R04 bridges to `KILL_SWITCH` → halt
- **E13 DayProfitTarget**: publishes `EMERGENCY` on catastrophic loss; issues close signals via `process_signal()`
- **E03 StopLossManager**: time/P&L-based → calls `_close_position_for_risk()` in A02 → `process_signal(MARKET, CLOSE)`
- **E16 CircuitBreakerProtocol**: halts new entries; does NOT auto-close existing positions
- **Y03 RiskSentinelAgent**: veto wired into E01 `validate_signal()` — blocks new entries only

---

## 2. Critical Bugs Found

### BUG-01 — VIX Hardcoded to 20.0 in D31 Regime Detection [CRITICAL]

**File:** `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`  
**Method:** `_update_market_regime()` (approx. line 1780)

```python
current_vix = 20.0  # Would get from market data   ← HARDCODED FOREVER
vix_percentile = self._calculate_vix_percentile(current_vix)
```

The VIX value used for regime classification is **permanently 20.0**. `C10_VIXAnalyzer` exists but is never queried. This means regime detection always starts from "normal vol" before any L09/Y01 override arrives, and the heuristic fallback path will never detect high-vol or crisis regimes.

**Impact:** Incorrect regime → wrong strategy selected → wrong capital allocation during actual volatility spikes.

---

### BUG-02 — D31 `_dispatch_approved_signal()` Not Shown; `_live_engine` May Be None [HIGH]

**File:** `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py` line 2186

```python
if self._live_engine is None and self._order_manager is None:
    # signal is dropped silently — no log, no counter
```

If `set_live_engine()` is never called before orchestration starts, all approved signals are silently discarded. This is only observable via the Prometheus drop counter if prometheus_client is installed. There is no startup assertion or warning log that `_live_engine` is None.

---

### BUG-03 — D09 GreeksBasedStrategy Does Not Use N04 [HIGH]

**File:** `SpyderD_Strategies/SpyderD09_GreeksBasedStrategy.py`

The strategy whose entire purpose is Greeks-based trading imports `N07_OPRAGreeksHandler` and `N11_OptionsGreeksFlow` — flow analysis tools — but NOT `N04_OptionsGreeksCalculator`. The position-level portfolio Greeks (delta, gamma exposure, charm, vanna) that drive hedge decisions are computed from raw chain data rather than N04's precise BSM kernel + second-order Greeks.

---

### BUG-04 — D31 Strategy Registry Registers Only 5 of 25+ D-Series Strategies [HIGH]

**File:** `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`  
**Method:** `_initialize_strategy_registry()`

```python
self.available_strategies = {
    'IronCondor': IronCondorStrategy,
    'CreditSpread': CreditSpreadStrategy,
    'ZeroDTE': ZeroDTEStrategy,
    'Straddle': StraddleStrategy,
    'SpecializedZeroDTE': SpecializedZeroDTEStrategy
}
```

D10 IronButterfly, D14 CalendarSpread, D15 StraddleStrangle, D16 RatioSpreads, D17 DiagonalSpread, D19 JadeLizard, D21 DoubleCalendar, D22 AdaptiveVolatility, D25 UnifiedCreditSpreadEngine, D26 GammaScalper, D27 EarningsStrategy, D28 VIXHedging, and D30 RegimeGatedSelector are all absent. The regime weight map references `IronButterfly` but it is never instantiable.

---

### BUG-05 — E-Series Risk Has Zero N04 Integration [HIGH]

**Files affected:** `SpyderE01_RiskManager.py`, `SpyderE15_GreekLimitsManager.py`, `SpyderE17_RealTimeStressTesting.py`

`E15_GreekLimitsManager` defines limits for `delta_limit`, `gamma_limit`, `vega_limit` but **checks them against values passed in by the caller** — it does not pull live portfolio Greeks from N04. `E01.validate_signal()` validates notional size, daily P&L, margin usage — but never queries portfolio-level delta/vega exposure before approving a new trade.

A short Iron Condor opened on top of an already-short-gamma portfolio could push the portfolio past its gamma limit without triggering any E01 rejection.

---

### BUG-06 — `_on_strategy_signal` Calls `get_risk_manager()` on Every Signal [MEDIUM]

**File:** `SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py` (~line 2040)

On every `STRATEGY_SIGNAL` event, D31 does:
```python
risk_manager = getattr(self, "risk_manager", None)
if risk_manager is None:
    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
    risk_manager = get_risk_manager()
```

This import-and-lookup happens on the hot path at signal frequency (potentially tens per second). The risk manager should be injected once at startup and cached as `self.risk_manager`.

---

### BUG-07 — No Greeks-Based Position Exit Triggers [MEDIUM]

No strategy module subscribes to N04's monitoring thread output for delta-drift or charm-based exit conditions. Current exit triggers are:
- P&L target reached (% of premium collected)
- DTE threshold (e.g., 21 DTE → close)
- Stop-loss on underlying move

Missing exit conditions that N04 already supports:
- **Charm-triggered exit**: daily delta drift from charm exceeds threshold (especially critical for calendar spreads near expiry)
- **Gamma spike exit**: gamma doubles from entry value (short-gamma positions become unmanageable)
- **Vomma-triggered exit**: vomma spikes during IV crush on short vega positions

---

### BUG-08 — D31 `_update_market_regime()` Never Reads Live VIX from C10 [MEDIUM]

Even with L09 injected, L09's `MarketConditions` is built with `vix_level=20.0` (hardcoded in BUG-01). The L09 model may compensate from ML features, but the fallback path always uses wrong VIX.

---

## 3. Architecture Deficiencies

### DEF-01 — Two Parallel Greeks Systems with No Coordination

`SpyderF06_GreeksCalculator` and `SpyderN04_OptionsGreeksCalculator` coexist without coordination:
- D-series strategies that import F06 get BSM Greeks computed on demand per option, with `cachetools` caching, American option support via binomial tree
- Only D20, D22 (optional), O02, L16 use N04
- D09 (the dedicated Greeks strategy) uses neither — it uses N07/N11 flow Greeks

**Risk:** Two strategies may calculate contradictory delta values for the same position.

### DEF-02 — D31 Regime Weights Reference Unregistered Strategy Types

The `_get_regime_strategy_weights()` map includes `'IronButterfly': 0.2` under multiple regimes. `IronButterfly` is never registered in `available_strategies`. This means the weight is silently ignored, and allocations are redistributed to the 5 registered types — but normalization makes this invisible.

### DEF-03 — C10 VIXAnalyzer Is Isolated from Core Signal Path

`C10_VIXAnalyzer` (1,483 lines) computes VIX term structure, regime classification, and VIX-based signals but is not wired to D31, E01, or the main event bus. It must be explicitly queried; no module calls it proactively.

### DEF-04 — No Shared N04 Instance; Risk of Stale Portfolio State

Each module that could use N04 would instantiate its own `OptionsGreeksCalculator`. N04's `PortfolioGreeks` tracking via `add_position()` / `_update_portfolio_greeks()` is only useful if a single shared instance tracks all positions across strategies. No singleton or shared-instance pattern exists for N04.

### DEF-05 — D31 VIX-in-Regime-Detection Always Uses Heuristic-Only path

`_calculate_vix_percentile()` uses hardcoded percentile bands (e.g., VIX ≤ 20 → 50th percentile). This ignores rolling 52-week IV ranks that C10 and C18 maintain.

---

## 4. Improvement Opportunities

### OPP-01 — Wire N04 Portfolio Greeks into E01 Pre-Trade Validation
N04's `get_portfolio_greeks()` could provide real-time total_delta, total_gamma, total_vega at signal time. E01 could reject trades that would push the portfolio over Greeks limits before execution.

### OPP-02 — Feed C10 Live VIX into D31 Regime Detection
Replace the hardcoded `current_vix = 20.0` with a live read from `C10_VIXAnalyzer.get_current_vix()` or from the market_data_cache (VIX tick from Massive feed).

### OPP-03 — Add Charm-Based Exit to E03 StopLossManager
N04 computes `charm` (delta decay per day). For calendar spreads and short-dated options, a charm threshold (e.g., delta moves >0.05 in one day) should trigger an exit signal. This is currently calculated nowhere.

### OPP-04 — Register All D-Series Strategy Types in D31
The 13+ missing D-series strategies should be added to `_initialize_strategy_registry()` and the regime weight map expanded.

### OPP-05 — Create a Singleton N04 Instance via A06 MasterController
A06 should instantiate one `OptionsGreeksCalculator`, inject it into D09, E15, E17, and make it available via a module-level `get_n04_calculator()` function.

### OPP-06 — N04 Scenario Analysis for E17 Stress Testing
`E17_RealTimeStressTesting` runs stress scenarios — currently without Greeks-aware P&L estimation. N04's `run_scenario_analysis()` produces Taylor-expansion P&L estimates for spot moves and vol changes. This would make E17 stress scenarios quantitatively meaningful.

### OPP-07 — Cache risk_manager Reference in D31
D31 should resolve `risk_manager` once at startup in `__init__` (or via a setter called by A02), not on every signal event.

### OPP-08 — Wire N04 Real-Time Greeks to G05 Dashboard
The `G05_TradingDashboard` has a Greeks display section. Currently it reads Greeks from broker positions (Tradier delta from chain). N04's portfolio Greeks (including second-order) could be surfaced in the dashboard for richer risk visibility.

### OPP-09 — N04 Hedge Recommendations → D09 Execution
N04's `calculate_hedge_recommendation()` returns `HedgeRecommendation` dataclasses specifying `HedgeType`, hedge_quantity, and target_delta. D09 could consume these directly as actionable signals rather than computing its own hedges from flow data.

### OPP-010 — D31 `_update_market_regime()` → Live VIX Percentile from C18 SKEW + C10
C10 maintains a rolling IV term structure. C18 computes the live SKEW index. Both can feed D31's regime classification for more accurate low/high/crisis detection than VIX bands alone.

---

## 5. Coding Agent Fix Specifications

Instructions are ordered by priority (P1 = critical, P2 = high, P3 = medium).

---

### [SPEC-P1-01] Fix VIX Hardcode in D31 `_update_market_regime()`

**File:** `Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`  
**Method:** `_update_market_regime()`

**Current code (approx. line 1785):**
```python
current_vix = 20.0  # Would get from market data
```

**Required change:**

1. Add a `_vix_analyzer` optional attribute in `__init__`:
```python
self._vix_analyzer: Any | None = None  # Set via set_vix_analyzer() or lazy-loaded
```

2. Add a `set_vix_analyzer(vix_analyzer)` public method:
```python
def set_vix_analyzer(self, vix_analyzer: Any) -> None:
    """Inject C10 VIXAnalyzer for live VIX reads."""
    self._vix_analyzer = vix_analyzer
    self.logger.info("D31: C10 VIXAnalyzer wired for live VIX in regime detection")
```

3. Replace the hardcoded `current_vix = 20.0` with:
```python
# Try live VIX from injected C10 VIXAnalyzer
current_vix = 20.0  # safe default
if self._vix_analyzer is not None:
    try:
        _vix_val = self._vix_analyzer.get_current_vix()
        if _vix_val and _vix_val > 0:
            current_vix = float(_vix_val)
    except Exception as _e:
        self.logger.debug("VIXAnalyzer.get_current_vix() failed: %s", _e)
else:
    # Fallback: read VIX from market_data_cache if a VIX tick was received
    _vix_cache = self.market_data_cache.get("VIX") or self.market_data_cache.get("^VIX")
    if isinstance(_vix_cache, list) and _vix_cache:
        _last_tick = _vix_cache[-1]
        _vix_val = (
            _last_tick.get("close") or _last_tick.get("price") or _last_tick.get("last")
            if isinstance(_last_tick, dict) else None
        )
        if _vix_val and float(_vix_val) > 0:
            current_vix = float(_vix_val)
    elif isinstance(_vix_cache, dict):
        _vix_val = _vix_cache.get("close") or _vix_cache.get("price") or _vix_cache.get("last")
        if _vix_val and float(_vix_val) > 0:
            current_vix = float(_vix_val)
```

4. In `A06_MasterController` or `A01_Main`, after constructing D31 and C10, call:
```python
orchestrator.set_vix_analyzer(vix_analyzer)
```

**Tests to add:** `SpyderT_Testing/test_SpyderD31_VixRegime.py`
- Test that when `_vix_analyzer.get_current_vix()` returns 35.0, regime is classified as `BEAR_HIGH_VOL` or `SIDEWAYS_HIGH_VOL` (not `SIDEWAYS_LOW_VOL`).
- Test fallback when VIXAnalyzer raises → uses cache → uses 20.0 default.

---

### [SPEC-P1-02] Assert `_live_engine` Wired Before Orchestration Starts

**File:** `Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`  
**Method:** `start_orchestration()`

**Required change:** Add a guard at the top of `start_orchestration()` (before the connectivity check):

```python
if self._live_engine is None and self._order_manager is None:
    self.logger.critical(
        "D31: Neither _live_engine nor _order_manager is wired. "
        "All approved signals will be silently dropped. "
        "Call set_live_engine() or set_order_manager() before start_orchestration()."
    )
    # Do NOT return False — allow orchestration for monitoring/paper mode,
    # but emit an event so operators are alerted.
    if self.event_manager:
        try:
            self.event_manager.emit(
                EventType.RISK_ALERT,
                {"severity": "critical", "reason": "no_execution_engine_wired",
                 "message": "D31 orchestration started without execution engine"},
                source="StrategyOrchestrator",
            )
        except Exception:
            pass
```

Also add a log in `_dispatch_approved_signal()` (if it silently drops):
```python
if self._live_engine is None and self._order_manager is None:
    self.logger.error(
        "D31: Approved signal dropped — no execution engine. signal=%s", signal
    )
    _count_drop("dispatch", "no_execution_engine")
    return
```

---

### [SPEC-P1-03] Cache `risk_manager` Reference in D31 `__init__`

**File:** `Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`

**Required change:**

In `__init__`, add:
```python
self.risk_manager: Any | None = None  # Set via set_risk_manager() or lazy-loaded once
```

Add public setter:
```python
def set_risk_manager(self, risk_manager: Any) -> None:
    """Wire E01 RiskManager for signal validation."""
    self.risk_manager = risk_manager
    self.logger.info("D31: RiskManager wired")
```

In `_on_strategy_signal()`, replace the per-call lazy-import block:
```python
# BEFORE (per-call import):
risk_manager = getattr(self, "risk_manager", None)
if risk_manager is None:
    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
    risk_manager = get_risk_manager()

# AFTER (cached, with lazy-load once):
if self.risk_manager is None:
    try:
        from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
        self.risk_manager = get_risk_manager()
    except Exception:
        self.risk_manager = None
risk_manager = self.risk_manager
```

In `A06_MasterController` or `A02_TradingEngine`, call `orchestrator.set_risk_manager(risk_manager)` after both are constructed.

---

### [SPEC-P1-04] Create Singleton N04 OptionsGreeksCalculator via A06

**Files:** `Spyder/SpyderA_Core/SpyderA06_MasterController.py`

**Required change:**

In `A06_MasterController.__init__()` or its `initialize()` method, add:

```python
# N04 shared Greeks calculator — single instance for the entire system
self._n04_calculator: Any | None = None
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
        OptionsGreeksCalculator,
    )
    self._n04_calculator = OptionsGreeksCalculator()
    self.logger.info("A06: N04 OptionsGreeksCalculator singleton instantiated")
except Exception as e:
    self.logger.warning("A06: N04 not available: %s", e)
```

Add a module-level accessor function at the bottom of `A06_MasterController.py`:
```python
_MASTER_CONTROLLER_INSTANCE: "MasterController | None" = None

def get_n04_calculator() -> Any:
    """Return the shared N04 OptionsGreeksCalculator instance, or None."""
    if _MASTER_CONTROLLER_INSTANCE is not None:
        return _MASTER_CONTROLLER_INSTANCE._n04_calculator
    return None
```

Set `_MASTER_CONTROLLER_INSTANCE = self` at the end of `__init__`.

Then inject into dependent modules:
- `E15_GreekLimitsManager.set_n04_calculator(calculator)`
- `E17_RealTimeStressTesting.set_n04_calculator(calculator)`
- `D09_GreeksBasedStrategy.set_n04_calculator(calculator)` (set on instance, not class)

---

### [SPEC-P2-01] Wire N04 Portfolio Greeks into E01 Pre-Trade Validation

**File:** `Spyder/SpyderE_Risk/SpyderE01_RiskManager.py`  
**Method:** `validate_signal()`

**Required change:**

Add optional N04 attribute:
```python
self._n04_calculator: Any | None = None

def set_n04_calculator(self, calculator: Any) -> None:
    """Wire N04 for portfolio-level Greeks validation."""
    self._n04_calculator = calculator
    self.logger.info("E01: N04 OptionsGreeksCalculator wired for Greeks-aware validation")
```

Add a new private method:
```python
def _check_portfolio_greeks_limits(self, signal: Any) -> tuple[bool, str]:
    """
    Check if adding the proposed trade would breach portfolio Greeks limits.

    Args:
        signal: RiskValidationRequest

    Returns:
        (approved: bool, rejection_reason: str)
    """
    if self._n04_calculator is None:
        return True, ""  # No N04 available — skip Greeks check

    try:
        portfolio_greeks = self._n04_calculator.get_portfolio_greeks()
        if portfolio_greeks is None:
            return True, ""

        # E15 limits (hardcoded conservative defaults matching E15 constants)
        MAX_PORTFOLIO_DELTA = float(os.environ.get("MAX_PORTFOLIO_DELTA", "500"))
        MAX_PORTFOLIO_GAMMA = float(os.environ.get("MAX_PORTFOLIO_GAMMA", "200"))
        MAX_PORTFOLIO_VEGA = float(os.environ.get("MAX_PORTFOLIO_VEGA", "50000"))

        abs_delta = abs(getattr(portfolio_greeks, "total_delta", 0.0))
        abs_gamma = abs(getattr(portfolio_greeks, "total_gamma", 0.0))
        abs_vega = abs(getattr(portfolio_greeks, "total_vega", 0.0))

        if abs_delta > MAX_PORTFOLIO_DELTA:
            return False, f"portfolio_delta_limit_breach: {abs_delta:.1f} > {MAX_PORTFOLIO_DELTA}"
        if abs_gamma > MAX_PORTFOLIO_GAMMA:
            return False, f"portfolio_gamma_limit_breach: {abs_gamma:.3f} > {MAX_PORTFOLIO_GAMMA}"
        if abs_vega > MAX_PORTFOLIO_VEGA:
            return False, f"portfolio_vega_limit_breach: {abs_vega:.0f} > {MAX_PORTFOLIO_VEGA}"

        return True, ""

    except Exception as e:
        self.logger.warning("Greeks limits check failed (permissive fallback): %s", e)
        return True, ""  # Fail-open — do not block trades on analytics error
```

In `validate_signal()`, add this call after the existing notional/margin checks:
```python
greeks_ok, greeks_reason = self._check_portfolio_greeks_limits(request)
if not greeks_ok:
    return RiskValidationResult(
        approved=False,
        rejection_reason=greeks_reason,
        risk_score=1.0,
    )
```

**Tests to add:** `SpyderT_Testing/test_SpyderE01_GreeksValidation.py`
- Mock N04 `get_portfolio_greeks()` returning delta=600 → signal rejected with `portfolio_delta_limit_breach`
- Mock N04 returning delta=100 → signal approved
- Mock N04 raising exception → signal approved (fail-open)

---

### [SPEC-P2-02] Register Missing D-Series Strategies in D31

**File:** `Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py`  
**Method:** `_initialize_strategy_registry()`

**Required change:**

Extend the soft-import block at the top of the file to include missing strategy classes. Add after the existing D02/D03/D04/D05/D11 imports:

```python
try:
    from Spyder.SpyderD_Strategies.SpyderD10_IronButterfly import IronButterflyStrategy
    _d10_available = True
except ImportError:
    IronButterflyStrategy = None  # type: ignore[assignment,misc]
    _d10_available = False

try:
    from Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread import CalendarSpreadStrategy
    _d14_available = True
except ImportError:
    CalendarSpreadStrategy = None  # type: ignore[assignment,misc]
    _d14_available = False

try:
    from Spyder.SpyderD_Strategies.SpyderD19_JadeLizard import JadeLizardStrategy
    _d19_available = True
except ImportError:
    JadeLizardStrategy = None  # type: ignore[assignment,misc]
    _d19_available = False

try:
    from Spyder.SpyderD_Strategies.SpyderD26_GammaScalper import GammaScalperStrategy
    _d26_available = True
except ImportError:
    GammaScalperStrategy = None  # type: ignore[assignment,misc]
    _d26_available = False

try:
    from Spyder.SpyderD_Strategies.SpyderD28_VIXHedging import VIXHedgingStrategy
    _d28_available = True
except ImportError:
    VIXHedgingStrategy = None  # type: ignore[assignment,misc]
    _d28_available = False
```

In `_initialize_strategy_registry()`, extend the dict:
```python
if SPYDER_MODULES_AVAILABLE:
    self.available_strategies = {
        'IronCondor': IronCondorStrategy,
        'CreditSpread': CreditSpreadStrategy,
        'ZeroDTE': ZeroDTEStrategy,
        'Straddle': StraddleStrategy,
        'SpecializedZeroDTE': SpecializedZeroDTEStrategy,
    }
    # Conditionally register additional strategies
    if _d10_available and IronButterflyStrategy:
        self.available_strategies['IronButterfly'] = IronButterflyStrategy
    if _d14_available and CalendarSpreadStrategy:
        self.available_strategies['CalendarSpread'] = CalendarSpreadStrategy
    if _d19_available and JadeLizardStrategy:
        self.available_strategies['JadeLizard'] = JadeLizardStrategy
    if _d26_available and GammaScalperStrategy:
        self.available_strategies['GammaScalper'] = GammaScalperStrategy
    if _d28_available and VIXHedgingStrategy:
        self.available_strategies['VIXHedging'] = VIXHedgingStrategy
```

Also update `_get_regime_strategy_weights()` to add regime weights for the new types (use conservative defaults):
```python
MarketRegime.BULL_LOW_VOL: {
    'IronCondor': 0.25, 'CreditSpread': 0.20, 'IronButterfly': 0.15,
    'ZeroDTE': 0.15, 'Straddle': 0.10, 'CalendarSpread': 0.10, 'JadeLizard': 0.05
},
MarketRegime.CRISIS: {
    'VIXHedging': 0.40, 'CreditSpread': 0.40, 'Straddle': 0.20
},
# Add GammaScalper to high-vol regimes where gamma scalping is most valuable
MarketRegime.BULL_HIGH_VOL: {
    'CreditSpread': 0.30, 'Straddle': 0.25, 'ZeroDTE': 0.20,
    'GammaScalper': 0.15, 'IronCondor': 0.10
},
```

---

### [SPEC-P2-03] Wire N04 into D09 GreeksBasedStrategy

**File:** `Spyder/SpyderD_Strategies/SpyderD09_GreeksBasedStrategy.py`

**Required change:**

Add N04 optional dependency at the top:
```python
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
        OptionsGreeksCalculator as _N04Calculator,
        PositionGreeks as _N04PositionGreeks,
    )
    _N04_AVAILABLE = True
except ImportError:
    _N04Calculator = None  # type: ignore[assignment,misc]
    _N04_AVAILABLE = False
```

In `GreeksBasedStrategy.__init__()`:
```python
self._n04: Any | None = None  # Injected via set_n04_calculator()

def set_n04_calculator(self, calculator: Any) -> None:
    """Inject shared N04 OptionsGreeksCalculator instance."""
    self._n04 = calculator
    self.logger.info("D09: N04 OptionsGreeksCalculator wired")
```

Replace the inline delta/gamma computation in the delta-neutral rebalancing logic with N04 calls:
```python
def _get_portfolio_greeks_from_n04(self) -> dict[str, float]:
    """Get current portfolio Greeks from N04, with fallback to zeros."""
    if self._n04 is None:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    try:
        pg = self._n04.get_portfolio_greeks()
        return {
            "delta": float(getattr(pg, "total_delta", 0.0)),
            "gamma": float(getattr(pg, "total_gamma", 0.0)),
            "vega": float(getattr(pg, "total_vega", 0.0)),
            "theta": float(getattr(pg, "total_theta", 0.0)),
            "charm": float(getattr(pg, "total_charm", 0.0)),
            "vomma": float(getattr(pg, "total_vomma", 0.0)),
        }
    except Exception as e:
        self.logger.warning("N04 portfolio Greeks unavailable: %s", e)
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
```

Use this dict wherever D09 currently manually sums option deltas from chain data.

Also use N04's hedge recommendation:
```python
def _get_n04_hedge_recommendation(self) -> Any | None:
    """Get N04 HedgeRecommendation for current portfolio."""
    if self._n04 is None:
        return None
    try:
        return self._n04.calculate_hedge_recommendation()
    except Exception:
        return None
```

In the strategy's main signal generation, check N04 recommendation before emitting a signal:
```python
hedge_rec = self._get_n04_hedge_recommendation()
if hedge_rec is not None and getattr(hedge_rec, "hedge_quantity", 0) != 0:
    # Emit a hedge signal using the N04 recommendation
    self._emit_hedge_signal(hedge_rec)
```

---

### [SPEC-P2-04] Add Charm-Based Exit Trigger to E03 StopLossManager

**File:** `Spyder/SpyderE_Risk/SpyderE03_StopLossManager.py`

**Required change:**

Add N04 optional dependency and injector (same pattern as SPEC-P2-03).

Add constants (load from env):
```python
CHARM_EXIT_THRESHOLD = float(os.environ.get("CHARM_EXIT_THRESHOLD", "0.05"))
# Close position if daily delta drift from charm exceeds 5 cents (0.05 delta)
GAMMA_SPIKE_EXIT_MULTIPLIER = float(os.environ.get("GAMMA_SPIKE_EXIT_MULTIPLIER", "2.0"))
# Close position if gamma doubles from entry value
```

Add a new method:
```python
def check_greeks_based_exits(self, positions: dict[str, Any]) -> list[str]:
    """
    Check each position for second-order Greek exit conditions.

    Args:
        positions: Dict mapping position_id → position data (must include entry_gamma).

    Returns:
        List of position_ids that should be closed.
    """
    if self._n04 is None:
        return []

    positions_to_close = []
    try:
        pg = self._n04.get_portfolio_greeks()
        if pg is None:
            return []

        # Check per-position Greeks if available
        for pos_id, pos_data in positions.items():
            try:
                # Charm-based exit: too much daily delta drift
                pos_charm = abs(float(getattr(pg, "total_charm", 0.0)))
                if pos_charm > CHARM_EXIT_THRESHOLD:
                    self.logger.warning(
                        "Charm exit triggered for %s: charm=%.4f > threshold=%.4f",
                        pos_id, pos_charm, CHARM_EXIT_THRESHOLD,
                    )
                    positions_to_close.append(pos_id)
                    continue

                # Gamma-spike exit: gamma doubled from entry
                entry_gamma = float(pos_data.get("entry_gamma", 0.0))
                current_gamma = abs(float(getattr(pg, "total_gamma", 0.0)))
                if entry_gamma > 0 and current_gamma > entry_gamma * GAMMA_SPIKE_EXIT_MULTIPLIER:
                    self.logger.warning(
                        "Gamma spike exit triggered for %s: gamma=%.4f > entry=%.4f × %.1f",
                        pos_id, current_gamma, entry_gamma, GAMMA_SPIKE_EXIT_MULTIPLIER,
                    )
                    positions_to_close.append(pos_id)

            except Exception as e:
                self.logger.debug("Greeks exit check failed for %s: %s", pos_id, e)

    except Exception as e:
        self.logger.warning("check_greeks_based_exits failed: %s", e)

    return positions_to_close
```

Call `check_greeks_based_exits()` from E03's main monitoring loop, and for each returned position_id emit a CLOSE signal via `_close_position_for_risk()`.

---

### [SPEC-P2-05] Wire N04 Portfolio Greeks into E15 GreekLimitsManager

**File:** `Spyder/SpyderE_Risk/SpyderE15_GreekLimitsManager.py`

**Required change:**

Add N04 attribute and setter (same pattern as above).

Find the existing `check_greeks_limits()` or equivalent method that validates incoming trade Greeks. Replace the caller-supplied portfolio Greeks values with live N04 values when available:

```python
def get_live_portfolio_greeks(self) -> dict[str, float]:
    """Get live portfolio Greeks from N04, with zero fallback."""
    if self._n04 is None:
        return {}
    try:
        pg = self._n04.get_portfolio_greeks()
        if pg is None:
            return {}
        return {
            "total_delta": float(getattr(pg, "total_delta", 0.0)),
            "total_gamma": float(getattr(pg, "total_gamma", 0.0)),
            "total_vega": float(getattr(pg, "total_vega", 0.0)),
            "total_theta": float(getattr(pg, "total_theta", 0.0)),
            "total_charm": float(getattr(pg, "total_charm", 0.0)),
            "dollar_delta": float(getattr(pg, "dollar_delta", 0.0)),
            "dollar_vega": float(getattr(pg, "dollar_vega", 0.0)),
        }
    except Exception as e:
        self.logger.warning("E15: N04 live Greeks unavailable: %s", e)
        return {}
```

Any method in E15 that checks limits against portfolio-level Greeks (delta/gamma/vega limits enforcement) should call `get_live_portfolio_greeks()` to get the current state before adding the proposed trade's Greeks to check headroom.

---

### [SPEC-P3-01] Wire N04 Scenario Analysis into E17 RealTimeStressTesting

**File:** `Spyder/SpyderE_Risk/SpyderE17_RealTimeStressTesting.py`

**Required change:**

Add N04 attribute and setter.

Add a new stress scenario runner:
```python
def run_n04_stress_scenarios(self, spot_moves: list[float] | None = None,
                              vol_changes: list[float] | None = None) -> dict[str, Any]:
    """
    Run N04 Taylor-expansion stress scenarios on current portfolio.

    Args:
        spot_moves: List of spot price changes (e.g., [-0.10, -0.05, 0.0, 0.05, 0.10]).
        vol_changes: List of IV change fractions (e.g., [-0.2, 0.0, 0.2, 0.5]).

    Returns:
        Dict of scenario_name → estimated_pnl
    """
    if self._n04 is None:
        return {}

    spot_moves = spot_moves or [-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10]
    vol_changes = vol_changes or [-0.3, -0.15, 0.0, 0.15, 0.3, 0.5]

    results = {}
    try:
        scenarios = self._n04.run_scenario_analysis(
            spot_moves=spot_moves,
            vol_changes=vol_changes,
        )
        for scenario in (scenarios or []):
            key = f"spot{scenario.spot_move:+.0%}_vol{scenario.vol_change:+.0%}"
            results[key] = float(getattr(scenario, "pnl_estimate", 0.0))
    except Exception as e:
        self.logger.warning("E17: N04 scenario analysis failed: %s", e)

    return results
```

Call this from E17's main stress test run and include the results in the stress report published to the event bus.

---

### [SPEC-P3-02] Wire N04 Portfolio Greeks into G05 TradingDashboard

**File:** `Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py`

**Required change:**

Add N04 attribute and setter.

Add a refresh method:
```python
def _refresh_n04_portfolio_greeks(self) -> None:
    """Refresh the portfolio Greeks display from N04."""
    if self._n04 is None:
        return
    try:
        pg = self._n04.get_portfolio_greeks()
        if pg is None:
            return
        # Update the Greeks labels in the risk panel
        # Find the existing label widgets for delta/gamma/theta/vega
        # (search for widget names matching Greeks labels in the dashboard)
        self._update_greeks_display({
            "Delta": f"{getattr(pg, 'total_delta', 0.0):.2f}",
            "Gamma": f"{getattr(pg, 'total_gamma', 0.0):.4f}",
            "Theta": f"{getattr(pg, 'total_theta', 0.0):.2f}",
            "Vega": f"{getattr(pg, 'total_vega', 0.0):.2f}",
            "Charm": f"{getattr(pg, 'total_charm', 0.0):.4f}",
            "Vomma": f"{getattr(pg, 'total_vomma', 0.0):.2f}",
            "$ Delta": f"${getattr(pg, 'dollar_delta', 0.0):,.0f}",
            "$ Vega": f"${getattr(pg, 'dollar_vega', 0.0):,.0f}",
        })
    except Exception as e:
        self.logger.debug("G05: N04 Greeks refresh failed: %s", e)
```

Wire this method to the dashboard's refresh timer (typically every 1–5 seconds via QTimer). The method should emit to the main Qt thread via a signal if called from a background thread.

---

## 6. Summary Priority Matrix

| Spec ID | File(s) | Severity | Risk if Not Fixed | Complexity |
|---------|---------|----------|-------------------|------------|
| SPEC-P1-01 | D31 | CRITICAL | Wrong strategy selected during vol spikes | Low |
| SPEC-P1-02 | D31 | HIGH | Silent signal discard on startup misconfiguration | Low |
| SPEC-P1-03 | D31 | MEDIUM | Import overhead on hot signal path | Low |
| SPEC-P1-04 | A06 | HIGH | N04 cannot track portfolio; all downstream specs depend on this | Medium |
| SPEC-P2-01 | E01 | HIGH | Greeks limits never enforced pre-trade | Medium |
| SPEC-P2-02 | D31 | HIGH | 13+ strategies unreachable; IronButterfly regime weights wasted | Medium |
| SPEC-P2-03 | D09 | HIGH | Greeks strategy uses inferior flow-only data | Medium |
| SPEC-P2-04 | E03 | MEDIUM | No charm/gamma spike exits — theta burn unmanaged near expiry | Medium |
| SPEC-P2-05 | E15 | MEDIUM | GreekLimitsManager has no live portfolio state | Medium |
| SPEC-P3-01 | E17 | LOW | Stress scenarios lack quantitative P&L estimates | Medium |
| SPEC-P3-02 | G05 | LOW | Dashboard shows broker-chain Greeks not portfolio Greeks | Low |

---

## 7. Recommended Implementation Order

1. **SPEC-P1-04** first — creates the shared N04 singleton that all other specs depend on.
2. **SPEC-P1-01** — fix the VIX hardcode so regime detection is live.
3. **SPEC-P1-02** — add the live_engine guard.
4. **SPEC-P1-03** — cache risk_manager.
5. **SPEC-P2-01** — Greeks-aware E01 validation (requires P1-04).
6. **SPEC-P2-03** — D09 N04 wiring (requires P1-04).
7. **SPEC-P2-02** — register missing strategies.
8. **SPEC-P2-04** — charm-based exits in E03 (requires P1-04).
9. **SPEC-P2-05** — E15 live Greeks (requires P1-04).
10. **SPEC-P3-01**, **SPEC-P3-02** — stress scenarios and dashboard (can be done independently after P1-04).

---

## 8. New Ideas

### IDEA-01 — N04 Real-Time Charm Monitor Thread
N04's monitoring thread already updates `PortfolioGreeks` every N seconds. Add a callback hook `on_greeks_updated(portfolio_greeks)` that strategies can register. This avoids polling and lets E03 react to charm/gamma changes within the monitoring interval rather than waiting for the next market data tick.

### IDEA-02 — Regime Confidence Gate for New Entries
When D31's `market_regime.regime_confidence < 0.5` (regime is uncertain), inhibit new entries for strategies with `strategy_type in ('ZeroDTE', 'SpecializedZeroDTE')` — these have the highest gamma risk in undefined regimes. Log a drop with reason `low_regime_confidence`.

### IDEA-03 — N04 Scenario Heat Map in G05
Add a heat map panel to G05 showing the Taylor-expansion P&L across a grid of spot moves (x-axis: -10% to +10%) vs. IV changes (y-axis: -30% to +50%). This gives the operator instant visual intuition for the portfolio's sensitivity surface.

### IDEA-04 — Automated IronButterfly/IronCondor Rotation via N04 GEX
Wire N04's `PortfolioGreeks.total_gamma` to the strategy selector. When net gamma exposure is near zero (market neutral), prefer IronButterfly. When net gamma is short by >50 contracts, prefer IronCondor to reduce concentration. This is a regime-within-regime refinement.

### IDEA-05 — Persistence of Entry Greeks in H04 TradeRepository
Store `entry_delta`, `entry_gamma`, `entry_vega` alongside each fill in H04's trade records. This enables SPEC-P2-04's gamma-spike exit check (which needs entry_gamma) without relying on in-memory state that is lost on restart.
