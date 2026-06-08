# SPY 7 DTE Put Credit Spread Strategy: Execution Contract

**Author:** Manus AI
**Date:** May 29, 2026

## Overview

This document serves as a precise execution contract for the SPY 7 DTE Put Credit Spread strategy, building upon the initial strategy description and addressing specific implementation details and technical considerations. The strategy is an income-generating options approach that involves selling out-of-the-money (OTM) put spreads on the SPDR S&P 500 ETF (SPY) with approximately seven days to expiration (DTE). It leverages time decay (theta) and the general upward bias or stability of equity markets over short periods. By utilizing a credit spread, the strategy ensures a defined maximum risk per trade [1].

This contract specifies the exact rules for entry, trade management, and exit, including detailed handling of potential edge cases such as noisy market data, holiday weeks, and ETF-specific risks like assignment. It aims to translate the conceptual strategy into a robust, automatable framework for consistent execution.

## Core Mechanics

A put credit spread (also known as a bull put spread) consists of two simultaneous options transactions:
1.  **Selling a Put Option:** This action generates an upfront credit and establishes the price level above which the underlying asset (SPY) is expected to remain.
2.  **Buying a Put Option (Lower Strike):** This option is purchased for a debit and acts as protection, capping the maximum potential loss in the event of a significant market downturn.

The net outcome is a credit received into the trading account. The strategy is profitable if SPY closes above the short put strike at expiration, allowing both options to expire worthless and the trader to retain the entire initial credit.

## Entry Criteria

The strategy employs a systematic and rule-based approach to entry, designed to minimize emotional decision-making and identify high-probability setups [1] [2].

*   **Timing:** Trades are initiated weekly on Fridays. Should Friday be a market holiday, the trade will be entered on the preceding Thursday [1].
*   **Entry Clock:** Entries are executed near the market close, with **3:45 PM ET** designated as the default implementation time. This timing allows the strategy to leverage the session's established trend and volatility, reducing susceptibility to intraday noise [1].
*   **Strike Selection (Delta):** The short put strike is selected to be the strike with a Delta **closest to 10**. This target delta implies an approximate 10% probability of the option expiring in-the-money (ITM), thereby offering a high probability of success at the initial setup [1]. In instances where delta data is missing or noisy (e.g., bid/ask spread exceeding 10% of the premium), the system will fall back to selecting a strike based on a calculated expected 7-day volatility and Z-score, or by choosing the nearest strike with sufficient volume and open interest to ensure liquidity and reliable pricing.
*   **Trend Filter (200-day SMA with Buffer):** A technical filter is applied to ensure trades are only initiated within a generally bullish or neutral market environment. The strategy strictly requires SPY to be trading **above its 200-day Simple Moving Average (SMA) plus a defined buffer**. This is formally expressed as `Price > SMA200 * (1 + Buffer)`. A common buffer, such as 0.5% or 1.0%, is utilized to prevent entries based on minor oscillations around the average line, ensuring alignment with a stronger long-term bullish trend [1].
*   **Spread Width (SPY Specific):** SPY options typically feature $1 strike increments. Consequently, a $5-wide spread, for example, would involve purchasing a long put five strikes below the short put [2].

## Spread Width and Capital Allocation

The spread width, defined as the difference between the short and long put strikes, directly influences the risk/reward profile. Wider spreads generally collect more premium but also entail a larger maximum potential loss per contract. To maintain consistent risk across varying spread widths, position sizing is dynamically adjusted [1].

The strategy operates with an assumed total account size of $50,000, allocating a maximum of **$20,000 per trade**. The remaining $30,000 is held in cash, ideally earning a risk-free interest rate [1].

To adhere to the $20,000 risk limit, the number of contracts traded is determined by a **Dynamic Formula**: `Contracts = floor(MaxRiskBucket / (SpreadWidth * 100))`. The examples provided in the table below are specific instances derived from this formula, assuming a `MaxRiskBucket` of $20,000:

| Spread Width | Contracts Traded | Max Risk per Contract | Total Capital at Risk |
| :--- | :--- | :--- | :--- |
| **$2.50** | 80 | ~$250 | ~$20,000 |
| **$4.00** | 50 | ~$400 | ~$20,000 |
| **$5.00** | 40 | ~$500 | ~$20,000 |
| **$10.00** | 20 | ~$1,000 | ~$20,000 |
| **$20.00** | 10 | ~$2,000 | ~$20,000 |

*Note: The actual maximum risk per contract is slightly less than the spread width minus the credit received, but for sizing purposes, the full width is often used as a conservative estimate [1].*

## Trade Management and Exit Rules

Effective trade management is paramount for long-term success, as allowing trades to reach maximum loss can significantly impair portfolio performance. The strategy employs a "Hybrid Exit" approach, balancing premium capture with proactive risk mitigation [1].

### 1. Stop Loss
An immediate exit is triggered if the SPY market price experiences a **5-minute bar close below the short put strike price** at any point during the trade's duration. This rule is designed to filter out transient price fluctuations while ensuring a timely exit to prevent further losses [1].

### 2. Expiration Handling and Hybrid Exit Strategy
Due to SPY being an Exchange Traded Fund (ETF) with physical share delivery upon assignment, holding options through expiration carries significant "pin risk"—the possibility of being assigned shares over the weekend due to after-hours price movements, even if the option was OTM at market close [2]. To explicitly mitigate this, the strategy implements the following:

*   **Mandatory Close for 0 DTE:** Any spread held until Friday (0 DTE) **MUST be closed by 3:55 PM ET**, regardless of its out-of-the-money status. This ensures avoidance of physical assignment and pin risk associated with SPY options [2].
*   **1 DTE Decision (Thursday Close):** The decision to hold a trade from Thursday (1 DTE) to Friday (0 DTE) is based on the following criteria:
    *   **For Narrow Spreads ($2.50 and $4.00 Widths):** Hold to Friday (0 DTE) only if SPY is at least **2.00% Out-of-the-Money (OTM)** relative to the short strike at the Thursday close. Otherwise, the trade is closed on Thursday [1].
    *   **For Wider Spreads ($5.00, $10.00, and $20.00 Widths):** Hold to Friday (0 DTE) only if SPY is at least **0.50% OTM** relative to the short strike at the Thursday close. Otherwise, the trade is closed on Thursday [1].

This modified hybrid approach acknowledges that wider spreads offer a larger buffer and can tolerate being held closer to expiration with a smaller OTM cushion compared to narrow spreads, while strictly preventing exposure to physical assignment risk on Friday close [1].

### 3. Profit Target (Optional Configuration)
An **optional configuration flag** allows for an early profit-taking mechanism. If enabled, trades will be closed when they have captured **50% of the maximum credit received**. This profit target takes precedence over the time-based exits (1 DTE/0 DTE). Implementing this rule can increase trade turnover and potentially the win rate, though it may result in capturing less than the full potential premium on some trades [2].

## Holiday and Target Expiry Handling

When the exact 7 DTE target expiration is unavailable due to market holidays or other factors, the strategy will adjust by stepping to the **nearest valid weekly expiration** within a range of +/- 2 days from the original 7 DTE target. If no such valid expiration exists within this window, the strategy will 
fail-closed, meaning no trade will be entered for that week. This approach balances safety with flexibility around market schedules.

## Performance Claims and Deployment Path

Performance claims presented in the initial research (e.g., highest P&L, best risk-adjusted) are to be treated as **External Research Context** derived from historical backtesting on SPX equivalents [1]. These figures are indicative of potential outcomes under specific historical conditions and are not guarantees of future performance for the SPY implementation.

The intended deployment path for this strategy is **Paper-First**. Live deployment to the decision stack will only be considered after a minimum of four consecutive weeks of paper trading execution that consistently matches the expected logic and performance, without significant "slippage anomalies" or unexpected behaviors. This phased approach ensures thorough validation in a simulated live environment before committing real capital.

## References

[1] Income Academy. "Amazing 7 DTE SPX Put Credit Spread Case Study!" YouTube, https://youtu.be/Fip0OY11NGg. Tradov adapts the structure to SPY options for live use.
[2] Options Cafe. "SPY Put Credit Spreads Strategy: Rules and a 91% Win Rate." https://options.cafe/blog/spy-put-credit-spreads-strategy/.
