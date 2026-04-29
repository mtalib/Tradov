# Autonomous Decision Contract

Last Updated: 2026-04-29

Purpose:
- Define the authoritative inputs for autonomous decision making.
- Separate active trust-gate inputs from broader regime inputs.
- Make wiring gaps explicit so they are not mistaken for active controls.

## 1) Active Entry Trust-Gate Inputs (A02 and D31)

Primary call sites:
- Spyder/SpyderA_Core/SpyderA02_TradingEngine.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py

Filter implementation source:
- Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py

### 1.1 Effective symbol inputs (currently wired)

These are effective because A02/D31 pass S07 market_conditions and F09 reads these keys directly:

- SPY (spy_change_pct baseline)
- QQQ (qqq_change_pct confirmation)
- IWM (iwm_change_pct confirmation)
- XLK (xlk_change_pct confirmation)
- XLF (xlf_change_pct confirmation)
- VIX (short-term vol stress ratio denominator)
- VIX9D (short-term vol stress ratio numerator)
- VVIX (vol-of-vol stress)
- CPC (put/call sentiment)
- RVOL (participation)

### 1.2 Effective custom metric inputs (currently wired)

- data_quality_feed (hard SLO gate)
- surface_confidence
- surface_age_ms
- term_slope_0_7
- rr_25d
- fly_25d
- dealer_flow
- wall_confidence
- flow_imbalance

### 1.3 Called but currently analyzer-dependent (not effective unless injected)

These checks are called in A02/D31, but EntryFilters is currently instantiated without analyzer dependencies:

- VIX term structure check (requires injected C10 VIXAnalyzer)
  - Symbol dependency when wired: VIX, VXV
- CBOE SKEW check (requires injected S06 SKEWCalculator)
  - Symbol dependency when wired: SKEW
- Market internals check (requires injected C04 MarketInternals)
  - Symbol dependency when wired: $TICK, $TRIN, $ADD

Current wiring status:
- A02 builds EntryFilters(config_manager) with no analyzer injection.
- D31 builds EntryFilters(config_manager) with no analyzer injection.

Interpretation:
- They are callable hooks but not authoritative gates in the current runtime unless dependency injection is added.

## 2) Overall Market Regime Inputs

Canonical regime engine:
- Spyder/SpyderL_ML/SpyderL09_UnifiedRegimeEngine.py

Market condition provider:
- Spyder/SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py

### 2.1 Regime symbol inputs

- SPY
- VIX
- $TICK
- $ADD
- $TRIN
- NYMO
- SKEW (OPT_SKEW feed path)

### 2.2 Regime custom metrics and macro inputs

- DIX
- GEX
- SWAN
- VEX
- CHEX
- BREADTH_REGIME
- YIELD_SLOPE
- YIELD_INVERTED
- YIELD_10Y
- AAII_BULLISH
- AAII_BEARISH
- NAAIM_EXPOSURE

### 2.3 Slow macro proxies (repo-tracked, not yet authoritative regime inputs)

Total slow macro items: **8** (6 indicators above + 2 proxies below)

- WRS — Walmart Recession Signal (consumer rotation / recession-risk proxy; producer: SpyderS12_WRSSignal)
- PSR — Pawn Shop Ratio (working-class credit-stress proxy; producer: SpyderS13_PSRSignal)

Note: WRS and PSR exist in the canonical symbol catalog and are visible in the dashboard. They must not drive short-term regime transitions. If they are later wired into S07/L09, move them to Section 2.2 and update drift tests.

### 2.4 Six-Regime Symbol/Metric Mapping (policy-aligned)

This mapping aligns to the six keys in `config/regime_policy.json`:

- bull_trend
- bear_trend
- range_calm
- high_vol_mean_reversion
- crisis_turbulent
- event_transition

The table below is a decision-contract mapping of already-declared inputs. It does not introduce new runtime inputs by itself.

| Regime | Primary symbols to weight | Primary metrics to weight | Typical gate emphasis |
|---|---|---|---|
| bull_trend | SPY, QQQ, XLK, VIX, VIX9D | BREADTH_REGIME, GEX, DIX, dealer_flow, flow_imbalance | Confirm SPY-relative leadership (QQQ/XLK), reject weak participation (RVOL), guard against short-term vol stress (VIX9D/VIX) |
| bear_trend | SPY, IWM, XLF, VIX, VVIX | BREADTH_REGIME, SWAN, CHEX, wall_confidence, dealer_flow | Confirm downside breadth/financial weakness (IWM/XLF), tighten CPC/VVIX stress checks, require strong data_quality_feed |
| range_calm | SPY, VIX, VIX9D, CPC | GEX, DIX, BREADTH_REGIME, rr_25d, fly_25d | Favor neutral participation and stable vol-of-vol; block if cross-index confirmation or surface quality deteriorates |
| high_vol_mean_reversion | SPY, VIX, VIX9D, VVIX, SKEW | SWAN, VEX, CHEX, rr_25d, fly_25d, term_slope_0_7 | Emphasize vol-shock containment, skew/term-structure quality, and stricter surface_confidence/surface_age_ms thresholds |
| crisis_turbulent | SPY, VIX, VVIX, $TICK, $ADD, $TRIN | SWAN, CHEX, BREADTH_REGIME, YIELD_INVERTED, YIELD_SLOPE | Prefer hard-block posture; strongest dependence on data_quality_feed, stress metrics, and internals where available |
| event_transition | SPY, VIX, VIX9D, QQQ, IWM, XLK, XLF | BREADTH_REGIME, DIX, GEX, YIELD_10Y, AAII_BULLISH, AAII_BEARISH, NAAIM_EXPOSURE | Event-clock style caution: maintain confirmation gates, reduce trust in stale/aging surface inputs, and avoid over-reliance on any single macro print |

Interpretation:

- Section 1 inputs remain the active A02/D31 entry trust-gate contract.
- Section 2 inputs remain the broader regime-classification contract.
- This mapping defines weighting intent by regime, not an additional gate list.

## 3) Governance Rules

1. Any change to active trust-gate input symbols requires updating this contract.
2. Any change to regime input symbols/metrics requires updating this contract.
3. Drift tests in SpyderT_Testing must fail if wiring semantics change without contract updates.

## 4) Notes on Regime Mapping

- `BREADTH_REGIME` is a regime-level classifier and should be treated as a composite context key, not a standalone trade trigger.
- Analyzer-dependent checks in Section 1.3 remain non-authoritative until dependencies are injected; this mapping does not change that status.
- WRS and PSR remain supervisory-only and outside short-horizon regime switching unless explicitly promoted and tested.
- HMM and other regime-switching models (Markov-switching, STAR) are internal inference methods; they are not authoritative contract inputs unless an explicit output key is exported to and consumed by decision logic.

