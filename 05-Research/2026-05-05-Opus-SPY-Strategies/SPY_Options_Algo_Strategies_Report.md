# SPY Options Algorithmic Trading Strategies — Coding Agent Reference

**Document Purpose:** Specification reference for implementing autonomous, algorithmic SPY options trading strategies used by professional and institutional traders.
**Date:** May 2026
**Target:** Python-based autonomous trading system (Tradov project context)

---

## 1. Strategy Landscape Overview

SPY is the single most liquid options product in the world. As of 2025–2026, 0DTE contracts alone account for over 45% of total SPX/SPY options volume on any given day. Algorithmic trading accounts for over 80% of U.S. equity volume. The strategies below are ranked roughly by institutional prevalence and automation suitability.

---

## 2. Tier 1 — High-Frequency Premium Selling (Most Automated)

### 2.1 0DTE Iron Condor (Bread-and-Butter Institutional 0DTE Strategy)

**What it is:** Sell an OTM put spread and an OTM call spread on SPY/SPX with same-day expiration, collecting premium from theta decay in a range-bound market.

**Why institutions love it:** Defined risk, high win rate (~65–70% on typical VIX 15–20 days), resolves in hours, massive liquidity with penny-wide spreads across hundreds of strikes.

**Algo Parameters:**

| Parameter | Typical Value | Notes |
|---|---|---|
| Entry time | 9:35 AM ET | Let opening volatility settle 5 min |
| Short strike delta | 0.10 (each side) | ~85% chance each side expires OTM |
| Spread width | $3–$5 (SPY) or 10-pt (SPX) | Wider = more premium, more risk |
| VIX filter | VIX > 14 (entry), reduce size VIX > 25 | Premiums too thin below 14 |
| Profit target | 25–50% of max credit | Close early, don't hold to expiration |
| Stop loss | 2× credit received (premium-based) | Never use SPY price-based stops |
| Close deadline | 3:00 PM ET | Gamma risk peaks in final 30 min |
| Position sizing | 1–2% of account per trade | Never >5% total 0DTE exposure |
| No-trade filter | FOMC days, CPI release days, VIX > 35 | Avoid known catalysts |

**Variant — Breakeven Iron Condor (Theta Profits method):** Documented over 9,100 trades from April 2021 to February 2026. Win rate is only 40%, but average win is 2.2× the average loss, producing positive expectancy. The key insight: enter at regular intervals (~hourly), aim for roughly equal credit on both sides, and use tight stop-losses that create a favorable win-size-to-loss-size ratio.

**Implementation Notes:**
- Use SPX for cash settlement (no assignment risk, 60/40 tax treatment) or SPY for tighter spreads and more granular strikes.
- Greeks to compute at entry: delta, gamma, theta, vega for all four legs.
- Critical risk: gamma explosion near expiration. A $1 SPY move changes a 0DTE ATM option's delta by 0.15–0.25.

```
PSEUDOCODE:
on_market_open():
    wait_until(09:35 ET)
    vix = get_vix()
    if vix < 14: skip_day()
    if is_catalyst_day(): skip_day()

    chain = get_spy_0dte_chain()
    put_short = find_strike(chain, side='put', target_delta=-0.10)
    put_long  = put_short - spread_width
    call_short = find_strike(chain, side='call', target_delta=0.10)
    call_long  = call_short + spread_width

    credit = sell_iron_condor(put_long, put_short, call_short, call_long)
    set_profit_target(credit * 0.40)
    set_stop_loss(credit * 2.0)
    set_hard_close(15:00 ET)
```

---

### 2.2 Credit Spreads (Directional Bias Variant)

**What it is:** Sell only one side of the iron condor — a bull put spread (bullish bias) or bear call spread (bearish bias).

**Why it matters:** Analysis of 230,000+ 0DTE trades found that profitable traders disproportionately favor short put spreads and short call spreads over full iron condors. This suggests some level of directional bias outperforms pure neutrality.

**Algo Parameters:**

| Parameter | Typical Value |
|---|---|
| Short strike delta | 0.10–0.16 |
| Spread width | $3–$5 |
| Directional filter | SMA(5) of SPY: above = sell puts, below = sell calls |
| Profit target | 50% of credit |
| Stop loss | 2× credit |

**Implementation Notes:**
- Legging into iron condors (selling put spread first, then call spread later based on intraday direction) is an advanced technique used by sophisticated 0DTE traders.
- Iron butterflies (ATM short strikes) are actually the most popular 0DTE structure among profitable Option Alpha autotraders, not iron condors.

---

### 2.3 Short Strangles / Straddles (Higher Risk, Higher Premium)

**What it is:** Sell naked (or loosely hedged) OTM puts and calls simultaneously. Straddle = ATM strikes; strangle = OTM strikes.

**Why institutions use it:** Captures the maximum volatility risk premium. The iron condor is essentially a risk-defined version of this.

**Algo Parameters:**

| Parameter | Typical Value |
|---|---|
| DTE | 30–45 days (sweet spot for theta/gamma balance) |
| Short strike delta | 0.16 (strangle) or 0.50 (straddle) |
| IV Rank filter | >= 50 (ideally >= 70) |
| Profit target | 50% of credit at entry |
| Margin requirement | Significant — portfolio margin account needed |
| Adjustment trigger | Short strike breached, or delta exceeds ±0.30 |

**Risk Warning:** Unlimited risk on naked positions. Requires portfolio margin and robust tail-risk hedging. Not suitable for small accounts.

---

## 3. Tier 2 — Volatility Risk Premium Harvesting

### 3.1 Systematic VRP (Volatility Risk Premium) Capture

**What it is:** The foundational thesis behind nearly all premium-selling strategies. Implied volatility systematically overestimates realized volatility. The spread between IV and HV (the VRP) averages 2–4 points on SPY and has been documented to yield 5–10% annualized returns in stable periods.

**Algo Architecture:**

```
PSEUDOCODE:
daily_signal():
    iv = get_spy_implied_vol(30_day)
    hv = get_spy_realized_vol(20_day)
    vrp = iv - hv

    iv_rank = compute_iv_rank(iv, lookback=252)
    iv_percentile = compute_iv_percentile(iv, lookback=252)

    if vrp > VRP_THRESHOLD and iv_rank > 50:
        signal = SELL_PREMIUM
        # Choose strategy based on VIX regime:
        if vix < 15: sell_narrow_condor_or_skip()
        elif 15 <= vix <= 25: sell_iron_condor_or_strangle()
        elif vix > 25: sell_wide_put_spread_only()
    elif vrp < 0:
        signal = BUY_PREMIUM  # rare, implies realized > implied
        buy_straddle_or_calendar()
```

**Key Metrics to Compute:**
- `IV_Rank = (current_IV - 52wk_low_IV) / (52wk_high_IV - 52wk_low_IV) × 100`
- `IV_Percentile = % of days in past year where IV was below current IV`
- `VRP = IV(30-day) - HV(20-day realized)`
- `VIX term structure slope = VIX_front_month - VIX_back_month` (contango = bullish for selling)

**Data Sources:** CBOE VIX data, options chain IV surfaces, historical OHLCV for realized vol computation.

---

### 3.2 VIX Mean Reversion Strategy

**What it is:** VIX tends to revert to its long-term mean (~20). Buy volatility products when VIX is extremely low (<15), sell when extremely high (>30).

**Algo Parameters:**

| Parameter | Value |
|---|---|
| Buy signal (long vol) | VIX < 13 AND VIX term structure in steep contango |
| Sell signal (short vol) | VIX > 30 AND VIX term structure in backwardation |
| Instruments | SVXY (short vol), VIXY/VXX (long vol), SPY puts/calls |
| Position sizing | Kelly criterion or fixed fractional |
| Hold period | Days to weeks (until mean reversion occurs) |

---

## 4. Tier 3 — Delta-Neutral Volatility Strategies

### 4.1 Gamma Scalping

**What it is:** Buy ATM options (acquiring positive gamma), then continuously delta-hedge the position by trading SPY shares/futures as it moves. Each hedge locks in a small gain. Profitable when realized volatility exceeds implied volatility.

**Why institutions use it:** Core market-making strategy. Citadel and Millennium deploy this as part of their multi-strategy portfolios.

**Algo Architecture:**

```
PSEUDOCODE:
init_position():
    # Find the "gamma-cheapest" straddle
    for each eligible_expiration in [20..45 DTE]:
        for each strike near ATM:
            score = (abs(theta) * THETA_WEIGHT + transaction_cost) / gamma
            track_best(score)

    buy_straddle(best_strike, best_expiration)
    shares_to_hedge = -round(net_delta * 100)
    trade_shares(SPY, shares_to_hedge)  # delta-neutral

monitor_loop():
    while position_open:
        current_delta = compute_portfolio_delta()
        if abs(current_delta) > DELTA_THRESHOLD:
            hedge_shares = -round(current_delta * 100)
            trade_shares(SPY, hedge_shares)
            log_scalp_pnl()

        if days_held > MAX_HOLD or theta_bleed > MAX_LOSS:
            close_all()
```

**Key Parameters:**

| Parameter | Typical Value |
|---|---|
| DTE at entry | 20–45 days |
| Delta hedge threshold | 0.10–0.15 (adaptive preferred) |
| Scalp frequency | 50–100 adjustments over position life |
| Break-even requirement | Realized vol must exceed implied vol |
| SPY ATM straddle theta | ~$12–$18/day (30 DTE) |
| Transaction cost budget | 10–20% of theoretical gamma profits |

**Critical Filter:** Only deploy when you forecast realized vol > implied vol. A volatility prediction model is essential.

---

### 4.2 Calendar Spreads (Horizontal Spreads)

**What it is:** Buy a longer-dated option and sell a shorter-dated option at the same strike. Profits from theta differential and IV changes across the term structure.

**Algo Parameters:**

| Parameter | Value |
|---|---|
| Short leg DTE | 7–14 days |
| Long leg DTE | 30–60 days |
| Strike selection | ATM or slightly OTM |
| Entry filter | IV term structure in contango (short IV > long IV unusual, or flat) |
| Profit target | 25–50% of debit paid |
| Greeks to monitor | Theta (positive), Vega (positive — benefits from IV rise) |

**Use Case:** Best when you expect IV to increase (pre-earnings, pre-FOMC) but don't want directional risk.

---

## 5. Tier 4 — Directional + Income Hybrid Strategies

### 5.1 The Wheel Strategy (Cash-Secured Put → Covered Call Cycle)

**What it is:** Sell cash-secured puts on SPY. If assigned, sell covered calls on the shares. Repeat. Systematic income generation with willingness to own SPY.

**Institutional Enhancement (SpotGamma approach):**
- Use dealer gamma positioning (GEX) to identify optimal put-sell strikes at structural support levels.
- Use Gamma Flip levels to determine if dealers are long gamma (supportive, mean-reverting) or short gamma (destabilizing, trend-accelerating).
- Use IV Rank filtering: only sell puts when IV Rank > 50 for rich premium.
- Align covered call strikes with structural resistance (Call Wall levels).

**Algo Parameters:**

| Parameter | Value |
|---|---|
| Put strike delta | -0.20 to -0.30 |
| DTE | 30–45 days |
| IV Rank filter | > 50 |
| Assignment handling | Auto-transition to covered call mode |
| Covered call delta | 0.20–0.30 (at resistance levels) |
| Exit on CC | If called away, restart with put selling |

```
PSEUDOCODE:
wheel_loop():
    if holding_cash:
        if iv_rank > 50 and dealer_gamma == LONG_GAMMA:
            strike = find_put_strike(delta=-0.25, near_support=True)
            sell_cash_secured_put(SPY, strike, dte=35)
    elif holding_shares:
        strike = find_call_strike(delta=0.25, near_resistance=True)
        sell_covered_call(SPY, strike, dte=35)

    manage_position():
        if put_profit > 50%: buy_to_close()
        if put_tested and dealer_gamma == SHORT_GAMMA: roll_down_and_out()
```

---

### 5.2 Momentum-Based Directional Options

**What it is:** Use technical momentum signals (MACD, RSI, moving average crossovers) to determine directional bias, then express via options for leverage and defined risk.

**Algo Parameters:**

| Signal | Action |
|---|---|
| SPY > SMA(200) AND SMA(50) > SMA(200) | Bull put spreads or long calls |
| SPY < SMA(200) AND SMA(50) < SMA(200) | Bear call spreads or long puts |
| RSI(14) < 30 AND IBS < 0.3 | Mean-reversion long call (short-term) |
| MACD histogram crossover | Momentum entry trigger |
| VIX spike > 30 from < 20 | Buy OTM puts as crash insurance |

**IBS (Internal Bar Strength) Strategy (QuantifiedStrategies.com):**
- IBS = (Close - Low) / (High - Low)
- Long entry: SPY closes below 10-day high minus 25-day average range, AND IBS < 0.3
- Exit: Close ends higher than yesterday's high
- This is a proven mean-reversion signal with decades of backtested data.

---

### 5.3 Straddles / Strangles (Long Volatility — Event-Driven)

**What it is:** Buy ATM straddles or OTM strangles before known catalysts (FOMC, CPI, earnings, NFP) expecting a large move in either direction.

**Algo Parameters:**

| Parameter | Value |
|---|---|
| Entry | 1–3 days before event |
| DTE | Choose expiration just past event date |
| IV filter | Enter when IV has NOT yet spiked (buy before the crowd) |
| Profit target | 50–100% of debit |
| Stop loss | 50% of debit |
| Vega exposure | Positive — benefits from IV expansion |

---

## 6. Regime-Adaptive Framework

The most critical algorithmic insight: **strategy selection must adapt to the volatility regime**. A static strategy will have streaks of losses whenever regime changes.

| VIX Regime | Range | Recommended Strategies | Position Size |
|---|---|---|---|
| Ultra-Low Vol | VIX < 13 | Skip premium selling (thin credits). Buy cheap long-dated puts as hedges. Consider long gamma. | Minimal |
| Low Vol | 13–17 | Narrow iron condors, conservative premium selling. Credits thin but consistent. | Standard |
| Normal Vol | 17–25 | **Sweet spot for premium selling.** Iron condors, strangles, wheel strategy at 16-delta, 45 DTE. VRP at historical average (2–4 pts). | Standard |
| High Vol | 25–35 | Wide put spreads only (bullish bias). Reduce position size 50%. Premium is rich but tail risk elevated. | 50% of standard |
| Crisis Vol | VIX > 35 | No new short premium. Consider long puts, VIX calls. Gamma scalping if realized vol > implied. | Defensive only |

---

## 7. Execution Infrastructure Requirements

### 7.1 Broker API Requirements

| Feature | Requirement |
|---|---|
| Options trading API | Must support multi-leg orders (iron condors as single order) |
| Real-time Greeks | Delta, gamma, theta, vega per contract |
| Options chain streaming | Sub-second quote updates for 0DTE |
| Order types | Limit, stop-limit, OCO (one-cancels-other), bracket |
| Recommended brokers (API) | Interactive Brokers (TWS API / ib_async), Tradier, Alpaca |

### 7.2 Data Requirements

| Data Type | Source Options | Refresh Rate |
|---|---|---|
| SPY OHLCV | Broker API, Polygon.io, Alpha Vantage | Real-time |
| Options chain + Greeks | Broker API, CBOE DataShop | Real-time for 0DTE |
| VIX spot + futures | CBOE, broker API | Real-time |
| IV surface / skew | Compute from chain, or CBOE LiveVol | Per-minute |
| Historical options data | CBOE DataShop, OptionMetrics, Polygon | Daily batch |
| Economic calendar | Tradier API, investing.com, FRED | Daily |

### 7.3 Python Libraries

```python
# Core
ib_async          # Interactive Brokers async API (preferred for TWS)
tradier_api       # Tradier REST API
alpaca_trade_api  # Alpaca broker integration

# Options Pricing & Greeks
py_vollib         # Black-Scholes, implied vol, Greeks computation
mibian            # Options pricing models
QuantLib          # Professional-grade quantitative finance

# Data & Analysis
pandas / numpy    # Core data handling
scipy.stats       # Statistical distributions for probability calcs
arch              # GARCH models for volatility forecasting

# Backtesting
backtrader        # Event-driven backtesting framework
vectorbt          # Vectorized backtesting (fast)

# Scheduling & Automation
apscheduler       # Job scheduling for entry/exit timers
asyncio           # Async event loop for real-time monitoring
```

---

## 8. Risk Management Rules (Universal)

These rules apply across ALL strategies and must be hard-coded as non-overridable constraints:

1. **Max daily loss:** 3–5% of account. Kill switch triggers automatic position closure.
2. **Max single-trade risk:** 1–2% of account.
3. **Max total 0DTE exposure:** 5% of account at any time.
4. **No holding through known catalysts** (FOMC, CPI, NFP) unless the strategy specifically targets them.
5. **Correlation check:** Never run multiple strategies that are all short gamma simultaneously.
6. **Slippage budget:** Model 0.5–1.0% round-trip slippage on each options trade.
7. **Commission budget:** At least $0.65/contract for modeling.
8. **Circuit breaker:** If VIX spikes >40% intraday, close all short-premium positions immediately.
9. **Backtest requirement:** Every strategy must show positive expectancy over 500+ simulated trades before live deployment.
10. **Paper trade period:** Minimum 30 days paper trading before real capital deployment.

---

## 9. Strategy Selection Matrix for Coding Agent

Use this matrix to decide which strategy to implement based on system capabilities:

| Strategy | Complexity | Data Needs | Latency Needs | Capital Needs | Automation Friendliness |
|---|---|---|---|---|---|
| 0DTE Iron Condor | Medium | High (real-time chain) | Medium (seconds OK) | Medium ($25K+) | ★★★★★ |
| Credit Spreads | Low–Medium | Medium | Medium | Low ($5K+) | ★★★★★ |
| VRP Systematic Selling | Medium | Medium (daily IV/HV) | Low (daily signals) | Medium | ★★★★☆ |
| Wheel Strategy | Low | Low–Medium | Low | High (cash-secured) | ★★★★☆ |
| Gamma Scalping | High | Very High (real-time) | High (sub-second) | High | ★★★☆☆ |
| Calendar Spreads | Medium | Medium | Low | Medium | ★★★★☆ |
| Long Straddle/Strangle | Low | Medium | Low | Medium | ★★★★☆ |
| Short Strangles (naked) | Medium | Medium | Medium | Very High (margin) | ★★★☆☆ |
| VIX Mean Reversion | Low–Medium | Medium | Low | Medium | ★★★★★ |

---

## 10. Recommended Implementation Order for Tradov

Given the Tradov project context (SPY options credit spreads, Tradier API):

1. **Phase 1:** VRP signal engine — compute IV Rank, IV Percentile, VRP daily. This is the foundation.
2. **Phase 2:** Credit spread executor — bull put spreads with regime-adaptive strike selection.
3. **Phase 3:** Iron condor executor — add the call spread side, implement profit targets and stop losses.
4. **Phase 4:** Regime classifier — VIX-based regime detection to auto-select strategy parameters.
5. **Phase 5:** 0DTE module — intraday iron condors with time-based entry/exit rules.
6. **Phase 6:** Wheel strategy module — for longer-term income generation alongside short-term 0DTE.
7. **Phase 7:** Gamma scalping module — only after real-time data infrastructure is proven reliable.

---

*This document is a strategy reference for autonomous trading system development. All strategies carry substantial risk of loss. Backtesting results do not guarantee future performance. Professional risk management and regulatory compliance are mandatory.*
