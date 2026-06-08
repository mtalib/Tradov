# Autonomous Decision Contract — Overview

Last Updated: 2026-05-02
Status: Current state — all v8 PMR fixes applied

---

## What the system does

Tradov is a fully autonomous SPY options trading system. Each bar it classifies the market into one of six regimes and dispatches the single permitted strategy for that regime through a chain of risk and entry gates before placing an order.

---

## Six-Regime Map

| Regime | Trigger (first-match, top-down) | Strategy |
|---|---|---|
| **EVENT** | Calendar proximity to high-impact event (±30 min) | 🚫 NO TRADE |
| **CRISIS** | VIX9D > VIX inversion, or VIX ≥ 35, or SPY shock + vol spike | 🚫 KILL-SWITCH |
| **BULL** | SPY > EMA50 AND VIX < EMA50 | D06 BullPutSpread |
| **BEAR** | SPY < EMA50 AND VIX > EMA50 | D07 BearCallSpread |
| **RANGE** | SPY within 1 ATR of EMA50 AND term structure not stressed | D02 IronCondor ¹ |
| **VOLATILE** | ATR% ≥ 1.5% AND VIX ≥ 80th pctl | D10 IronButterfly |
| Fallback | No rule matched | RANGE → D02 IronCondor |

¹ When `TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true` and the S08 pivot signal fires, RANGE maps to **D34 PivotMeanReversion** instead.

**Concurrency cap: 1 strategy open at a time.**

---

## Decision Pipeline (per bar)

```
S07 Market Snapshot
  → L09 Regime Classifier
    → D30/D31 Strategy Selector (regime → strategy, env-flag swaps)
      → F09 Entry Trust Gate (time, vol surface, data quality)
        → E01 Risk Validation (position size, Greeks limits, drawdown)
          → B02 Order Manager → B40 Tradier API
```

Anything rejected at F09 or E01 is logged with a reason; no order is placed.

---

## Active Inputs

**Price series**: SPY, VIX, VIX9D (VXV optional)
**Market internals**: $TICK, $ADD, $TRIN, NYMO
**Flow/dealer signals**: DIX, GEX, dealer_flow, flow_imbalance
**Vol surface**: surface_confidence, surface_age_ms, rr_25d, fly_25d, term_slope_0_7
**Macro**: BREADTH_REGIME, SWAN, VEX, CHEX, YIELD_SLOPE

---

## D34 Pivot Mean Reversion (currently active)

- **Signal source**: `TradovS08_PivotMeanReversionSignal` — scores the nearest tested pivot level (P, R1–R3, S1–S3) and fires when score ≥ 60.
- **Trade structure**: single-leg long ITM option, delta ≈ 0.60, 0–1 DTE.
  - At resistance → buy ITM put (fade rejection)
  - At support → buy ITM call (fade bounce)
- **Risk**: defined by premium paid. Exit at VWAP cross, 12-min time stop, or 0.15% adverse pivot break.
- **Gate**: only activates in RANGE regime when `TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true`.

---

## Safety Defaults

- CRISIS and EVENT hard-halt all new entries — no exceptions.
- Missing or stale required data (SPY/VIX series < 50 samples) → DATA_STALE event → entries halted.
- All regime transitions, strategy selections, and gate decisions are timestamped and logged.
- System defaults to paper mode with the TradovBox local ledger; live requires explicit confirmation.
