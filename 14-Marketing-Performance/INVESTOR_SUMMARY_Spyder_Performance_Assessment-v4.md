# TRADOV TRADING SYSTEM
## Performance Assessment & Current Validation Snapshot - v4

**Prepared for Institutional Review**
**Date:** May 27, 2026
**Codebase Snapshot:** master @ current workspace state
**Status:** Phase 4 - Active Paper Trading Validation
**Classification:** Confidential

---

## EXECUTIVE SUMMARY

This v4 report aligns the performance narrative with the current checked-in production surface and the updated `TradovT06_EvolvedStrategyTest` harness.

The current harness now validates two things together:

1. **Performance math and pricing** through `TradovU20_InstitutionalLibraries` using the checked-in D18 evolved baseline.
2. **Current PMR routing and risk controls** across `D30 RegimeGatedSelector`, `D31 StrategyOrchestrator`, `D34 PivotMeanReversion`, `S08 PivotMeanReversionSignal`, and `E01 RiskManager.validate_overlay_slot()`.

On the current checked-in D18 parameter set, the deterministic 252-day synthetic return stream used by T06 produces the following institutional metrics:

| Metric | Current v4 Value | Interpretation |
|--------|------------------|----------------|
| **Sharpe Ratio** | **2.66** | Strong risk-adjusted return in the current synthetic harness |
| **Sortino Ratio** | **5.04** | Downside volatility remains tightly controlled in the harness |
| **Calmar Ratio** | **5.25** | Return remains high relative to modeled drawdown |
| **Annualized Return** | **31.19%** | High modeled return for the current parameter set |
| **Volatility** | **10.04%** | Controlled annualized volatility in the synthetic stream |
| **Max Drawdown** | **-5.94%** | Shallow modeled drawdown |
| **VaR (95%)** | **-0.87%** | One-day modeled downside threshold |
| **Evolution Fitness** | **0.799** | Current checked-in D18 baseline |
| **Generation** | **15** | Current checked-in D18 baseline |
| **Risk Factor** | **0.212** | Current checked-in D18 baseline |

These figures are **not live trading results** and **not historical market replay results**. They are the direct output of the current T06 harness methodology described below.

---

## WHAT CHANGED IN v4

This version replaces the stale D25-centric PMR narrative with the current routing contract that is actually present in code:

- **PMR strategy routing now reflects the D30/D31/D34 path.**
- **E01 overlay-slot validation is now part of the documented control surface.**
- **R08 still uses the legacy producer gate `TRADOV_PIVOT_MR_ENABLED=1` for paper-mode PMR signal production.**
- **D30 strategy selection uses `TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true` to swap RANGE/SIDEWAYS selections to `pivot_mean_reversion` when S08 fires.**
- **D31 normalizes PMR aliases and builds overlay metadata for `E01.validate_overlay_slot()`.**

The updated T06 regression passed on this workspace snapshot with:

- **71 passed**
- **5 skipped**

---

## CURRENT VALIDATION METHODOLOGY

### 1. Evolved baseline used by the harness

The current T06 harness pulls its baseline from `TradovD18_EvolvedCreditSpread`:

| Field | Current Value |
|-------|---------------|
| Generation | 15 |
| Fitness Score | 0.799 |
| Risk Factor | 0.212 |
| Improvement Marker | 0.67 |
| Strategy Type | `credit_spread` |

### 2. Return-stream construction

The institutional metrics in T06 come from a deterministic synthetic series with the following current logic:

- Random seed = `42`
- Trading horizon = `252` periods
- Base daily return = `fitness_score * 0.00138`
- Daily volatility scale = `0.0083 * (1 - risk_factor)`
- Daily returns sampled from a normal distribution and clipped to `[-3%, +3%]`

This means the performance numbers in this document are **parameterized synthetic outputs**, not brokerage fills, not paper-trade journal PnL, and not historical bar-by-bar backtests.

### 3. Institutional metric engine

T06 uses `TradovU20_InstitutionalLibraries` to calculate:

- Annualized return
- Volatility
- Sharpe ratio
- Sortino ratio
- Calmar ratio
- Max drawdown
- VaR

On the current environment snapshot, the institutional library bundle reported **4 / 8** optional institutional dependencies available, with QuantLib available and used.

---

## CURRENT STACK REFLECTED IN v4

| Capability | Current Production Surface Reflected in T06 |
|------------|---------------------------------------------|
| Regime-based strategy selection | **D30 RegimeGatedSelector** |
| Strategy admission and alias normalization | **D31 StrategyOrchestrator** |
| Evolved credit-spread baseline parameters | **D18 EvolvedCreditSpread** |
| Pivot mean-reversion strategy path | **D34 PivotMeanReversion** |
| Pivot signal scoring | **S08 PivotMeanReversionSignal** |
| Regime classification | **L09 UnifiedRegimeEngine** |
| Hard risk gate | **E01 RiskManager** |
| Overlay-slot gate | **E01 validate_overlay_slot()** |
| Institutional pricing and analytics | **U20 InstitutionalLibraries** |

### Current PMR control contract

| Layer | Current Behavior |
|-------|------------------|
| R08 paper producer | PMR production remains gated by `TRADOV_PIVOT_MR_ENABLED=1` |
| D30 selector | `TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true` allows RANGE/SIDEWAYS to select `pivot_mean_reversion` when S08 fires |
| D31 orchestrator | Normalizes aliases like `PivotMeanReversion`, `pivot_mr`, and `D34_PivotMR` to `pivot_mean_reversion` |
| E01 risk | `validate_overlay_slot()` evaluates narrow PMR overlay admission when the optional overlay path is requested |

---

## PERFORMANCE METRICS DEEP DIVE

### Institutional metrics from the current T06 run logic

| Metric | Value |
|--------|-------|
| Annualized Return | 31.19% |
| Average Daily Return | 0.108% |
| Annualized Volatility | 10.04% |
| Sharpe Ratio | 2.66 |
| Sortino Ratio | 5.04 |
| Calmar Ratio | 5.25 |
| Max Drawdown | -5.94% |
| VaR (95%) | -0.87% |
| Best Period Return | +2.63% |
| Worst Period Return | -1.60% |

### Interpretation

- The current harness still produces a strong modeled Sharpe profile.
- The drawdown profile remains shallow inside the synthetic return envelope.
- The downside metrics remain favorable because the clipped return construction limits tail magnitude by design.
- These values should be treated as **signal-quality and parameter-quality indicators**, not as realized trading expectations.

---

## SAMPLE CREDIT-SPREAD SNAPSHOT

T06 also prices a representative SPY bull-put spread through U20.

| Field | Current Value |
|-------|---------------|
| Spot | $400.00 |
| Short Put / Long Put | $393 / $388 |
| Net Credit | $0.944 |
| Max Loss | $4.056 |
| Return on Risk | 23.27% |
| Net Delta | -0.1190 |
| Net Theta | -0.0538 / day |
| Net Gamma | +0.0095 |

This sample remains consistent with a defined-risk premium-selling profile, but it is a pricing snapshot only and not a recorded trade outcome.

---

## COMPARISON TO v3 NARRATIVE

The primary purpose of v4 is alignment with the current codebase.

| Area | v3 Narrative | v4 Current-Code Alignment |
|------|--------------|---------------------------|
| PMR architecture | D25-centric PMR override framing | D30 selector + D31 orchestrator + D34 PMR + E01 overlay gate |
| Evolved baseline | Reported as Gen 22 / fitness 0.834 / risk factor 0.160 | Current checked-in D18 baseline is Gen 15 / fitness 0.799 / risk factor 0.212 |
| Validation framing | Broad investor-performance framing | Explicit T06 harness framing with current code references |
| Disclosure | Simulated results disclosed, but methodology was summarized loosely | Synthetic seeded return-stream construction stated explicitly |

The v4 numbers above are the values that can be reproduced directly from the current checked-in T06 methodology.

---

## RISK DISCLOSURES AND LIMITATIONS

### What this report is

- A code-aligned performance assessment based on the current T06 validation harness.
- A control-surface summary of the current PMR routing and overlay-risk boundaries.

### What this report is not

- Not live trading performance.
- Not a Tradier execution report.
- Not a historical backtest over recorded market data.
- Not a transaction-cost-complete brokerage PnL analysis.

### Current limitations

1. **Synthetic returns**: the T06 performance series is generated parametrically from D18 constants and a seeded normal distribution.
2. **Execution friction omitted**: commissions, spread crossing, partial fills, exchange fees, and market impact are not represented in the T06 return stream.
3. **Tail behavior is clipped**: the current harness caps single-period returns at +/-3.0%, which suppresses extreme-tail outcomes.
4. **Architecture validation is broader than PnL validation**: T06 now covers current PMR routing contracts, but that does not by itself prove live execution profitability.

---

## CONCLUSION

The current checked-in Tradov stack continues to show strong modeled risk-adjusted metrics in the T06 institutional harness while now reflecting the actual D30/D31/D34 PMR routing contract and the E01 overlay-slot risk boundary.

The most important v4 change is not a marketing claim; it is **alignment**. This document now matches the current code, current T06 test surface, and current checked-in D18 baseline.

---

*Confidential. Generated from the current workspace state on May 27, 2026 using the updated `TradovT06_EvolvedStrategyTest` harness, the checked-in `TradovD18_EvolvedCreditSpread` constants, and `TradovU20_InstitutionalLibraries` pricing/metric calculations.*