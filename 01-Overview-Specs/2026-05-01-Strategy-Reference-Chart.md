# Spyder — Approved Strategy Reference Chart
**Last Updated:** 2026-05-01

---

## ✅ LIVE / PAPER APPROVED — Lean Mode Allowlist (4 strategies)

These are the **only strategies that can execute trades** in the current paper/live system.
D31 runs exactly **one strategy at a time** mapped from the detected market regime.

| Strategy | Module | Structure | Holding Period | Regime Gate | IV Rank | VIX Gate | Signal / Entry Trigger | Other Conditions |
|---|---|---|---|---|---|---|---|---|
| **Iron Condor** | D02 | Short OTM call spread + short OTM put spread | 21–45 DTE (target 30 DTE) | Sideways Low Vol only | 40–80 (optimal 60) | Not gated | Neutral directional bias; expected-move ratio 0.8–1.2; vol skew < 5% | Min credit $0.30; max spread width $10; delta target ±0.16 |
| **Iron Butterfly** | D10 | Short ATM straddle + OTM wings | 10–35 DTE (target 25 DTE) | Sideways High Vol only | 30–75 (optimal 50) | Not gated | Neutral; price expected to pin near ATM | Min credit $0.50; wing width 5–15 pts; expected-move ratio < 0.8; max delta ±0.05 |
| **Bull Put Spread** | D06 | Short higher-strike put + long lower-strike put | 20–45 DTE | Bull regime (any vol) | Inherits CreditSpread (D03) | Not gated | **RSI < 50** (not overbought) + upward momentum > 0.1% | Min premium $0.50; min P(profit) 65%; delta targets −0.30 / −0.15; max 5 positions |
| **Bear Call Spread** | D07 | Short lower-strike call + long higher-strike call | 20–45 DTE | Bear regime (any vol) | Inherits CreditSpread (D03) | Not gated | **RSI > 50** (not oversold) + downward momentum < −0.1% | Min premium $0.50; min P(profit) 65%; delta targets 0.30 / 0.15; max 5 positions |

### Regime → Active Strategy (lean mode)

| Market Regime | Active Strategy |
|---|---|
| Bull Low Vol | Bull Put Spread |
| Bull High Vol | Bull Put Spread |
| Bear Low Vol | Bear Call Spread |
| Bear High Vol | Bear Call Spread |
| Sideways Low Vol | Iron Condor |
| Sideways High Vol | Iron Butterfly |
| Crisis / Event Transition | **HARD HALT — no new entries** |

### Holding Period Breakdown

| Strategy | Entry DTE | Typical Exit Trigger | Effective Hold Time |
|---|---|---|---|
| **Iron Condor** | 21–45 DTE (target 30) | Close at 21 DTE remaining **or** 25–50% of max credit collected | **~1–3 weeks** |
| **Iron Butterfly** | 10–35 DTE (target 25) | Close at 10–15 DTE remaining **or** 25% profit target | **~1–2 weeks** |
| **Bull Put Spread** | 20–45 DTE | Close ≤ 5 DTE remaining **or** 25% profit; stop at 2× credit received | **~2–5 weeks** |
| **Bear Call Spread** | 20–45 DTE | Close ≤ 5 DTE remaining **or** 25% profit; stop at 2× credit received | **~2–5 weeks** |

> All 4 strategies are **premium-selling, multi-week holds** — none are intraday or single-day positions.
> Profit targets typically close positions in **1–3 weeks**. The outer bound (45 DTE entry held near expiry) is ~5–6 weeks.

### Universal Pre-Trade Gates (all 4 strategies)

All strategies must pass every gate before any order is submitted:

1. Market is open — RTH only (9:30 AM – 4:00 PM ET)
2. Kill switch is OFF
3. No active `DATA_STALE` event on the SPY feed
4. Strategy state is `STRATEGY_ACTIVE` (D31 calls `start()` after `orchestration_active = True`)
5. Risk manager approval — `SpyderE01_RiskManager.validate_order()`
6. Daily drawdown limit not breached — `SpyderE04_DrawdownControl`
7. Portfolio Greek limits not exceeded — `SpyderE15_GreekLimitsManager`
8. Daily trade limit not exceeded — `BaseStrategy._can_trade()`
9. Total exposure within `risk_profile.max_portfolio_risk`

---

## 🔬 REGISTERED BUT NOT YET APPROVED — Phase 1 / 2 (original 9)

Implemented, tested, and registered in D31. Will be enabled in full-mode once backtesting validates them for live capital. Not in the lean allowlist.

| Strategy | Module | Structure | Holding Period | IV Rank Required | VIX Gate | Signal / Entry Trigger |
|---|---|---|---|---|---|---|
| **Credit Spread** | D03 | Bull-put or bear-call vertical (parent of D06/D07) | 20–45 DTE | RSI-gated (no fixed IV rank) | Not gated | RSI oversold < 30 (bull) or overbought > 70 (bear); volume 1.5× average |
| **Zero-DTE** | D04 | 0-DTE spread or straddle | Same-day (entry 9:31 → exit 15:50) | IVR ≥ 30 | VIX < 30 | SPY volume ≥ 50 M; max 2 concurrent positions |
| **Straddle** | D05 | Long ATM call + put | 7–45 DTE; close ≤ 3 DTE remaining | 20–50 (long vol) | Not gated | Expects large move; min expected move 1.5%; vega ≥ 0.10 |
| **Opening Range Breakout** | D08 | Long call or put (directional) | Intraday — close same day | Not used | Not gated | Mon/Tue only; price breaks opening range (0.50–3.00 pts); max 2 trades/day |
| **Greeks-Based** | D09 | Dynamic — fills portfolio Greeks gap | 0DTE (≤ 1 DTE) or swing (30–60 DTE) | Regime-dependent | Not gated | Targets specific delta/gamma/vega gap in portfolio; gamma > 0.05 triggers 0DTE |
| **Specialized Zero-DTE** | D11 | 0-DTE condor or spread | Same-day (entry 10:15 → last entry 14:30 → close 15:45) | Not fixed | VIX 12–35 | Opening volume ≥ 1 M; overnight gap < 1.5%; delta ≤ 50; gamma ≤ 100 |

---

## 🏗️ REGISTERED BUT NOT YET APPROVED — Phase 3 (added later)

Added to the registry to align with the full regime-weight map. Not in the lean allowlist; require further backtesting before enabling.

| Strategy | Module | Structure | Holding Period | IV Rank Required | Regime Best-Fit |
|---|---|---|---|---|---|
| **RSI Mean Reversion** | D12 | Short-term directional options | ~7 DTE; entry 11 AM–2 PM only | Not fixed | Bull High Vol / Bear High Vol |
| **MA Crossover** | D13 | Directional call or put | Swing (days–weeks; trend-dependent) | Not fixed | Bull Low Vol |
| **Calendar Spread** | D14 | Sell near / buy far same strike | Near 7–35 DTE; far 14–60 DTE | 30–70 | Sideways Low Vol / Bear Low Vol |
| **Straddle/Strangle** | D15 | Long straddle (low IV) or short strangle (high IV) | ~14–30 DTE | Long < 30; Short 50–90 | Pre-event / Sideways High Vol |
| **Ratio Spreads** | D16 | 1×2 or 1×3 vertical | 20–50 DTE (target 35 DTE) | 40–80 | Mild directional + high IV |
| **Diagonal Spread** | D17 | Short near / long far different strikes | Short 30 DTE / long 60 DTE | ≥ 30 | Trending (any direction) |
| **Jade Lizard** | D19 | Short put + short call spread | 25–50 DTE (target 45 DTE) | 40–85 | Bull Low Vol / Sideways Low Vol |
| **Vertical Spread Optimizer** | D20 | Scored bull-put or bear-call | 7–45 DTE | ≥ 30 | Regime-adaptive |
| **Double Calendar** | D21 | Two calendar spreads at different strikes | Near 20–35 DTE; far 41–70 DTE | 30–70 | Sideways |
| **Adaptive Volatility** | D22 | ML-selected by vol regime | 15–60 DTE | ML model | Regime-adaptive |
| **Gamma Scalper** | D26 | Delta-neutral long-gamma + share hedges | Intraday to multi-day | Not fixed (IV level used) | Bull High Vol / Bear High Vol |
| **Evolved Credit Spread** | D18 | ML-enhanced bull-put or bear-call | 20–45 DTE | AI-selected (confidence ≥ 70%) | Favorable regime |
| **VIX Hedging** | D28 | VIX calls / term structure play | Open until VIX normalises | N/A | Crisis / tail-risk |
| **Renaissance Mean Reversion** | D33 | OU-process statistical mean reversion | Short swing | Not fixed | Bear Low Vol |
| **Pivot Mean Reversion** | — | Pivot-based mean reversion | Short swing | Not fixed | Sideways (both) |
| **Earnings Strategy** | D27 | Straddle/strangle sized to implied move | Enter 1–7 days pre-earnings; close at announcement | IV percentile ≥ 60 | Event-driven |
