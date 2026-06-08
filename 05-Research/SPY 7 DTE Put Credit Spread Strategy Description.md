# SPY 7 DTE Put Credit Spread Strategy Description

**Author:** Manus AI
**Date:** May 28, 2026

## Overview

The SPY 7 DTE Put Credit Spread is an income-generating options strategy designed to collect premium by selling out-of-the-money (OTM) put spreads on the SPDR S&P 500 ETF (SPY) with approximately seven days to expiration (DTE). This strategy capitalizes on time decay (theta) and the tendency of equity markets to drift higher or remain stable over short periods. By using a credit spread rather than a naked put, the strategy strictly defines the maximum risk per trade.

This Tradov implementation adapts the original SPX case-study template to SPY so the live option chain, strike spacing, and position-sizing defaults match the product we intend to trade.

This document outlines the specific rules, entry criteria, management techniques, and performance expectations based on the analysis of the provided case study [1].

## Core Mechanics

A put credit spread (also known as a bull put spread) involves two simultaneous options transactions:
1.  **Selling a Put Option:** This generates an upfront credit and establishes the level where the trader expects the underlying asset (SPY) to stay above.
2.  **Buying a Put Option (Lower Strike):** This is purchased for a debit and serves as protection, capping the maximum potential loss if the market experiences a severe downturn.

The net result is a credit received into the account. The strategy is profitable if the SPY closes above the short put strike at expiration, allowing both options to expire worthless and the trader to keep the entire initial credit.

## Entry Criteria

The strategy employs a systematic approach to entry, removing emotional decision-making:

*   **Timing:** Trades are initiated weekly on Fridays. If the market is closed on Friday due to a holiday, the trade is entered on the preceding Thursday.
*   **Entry Clock:** Entries are taken near the market close, with **3:45 PM ET** as the default implementation time. This helps the strategy rely on the session's settled trend and volatility instead of intraday noise.
*   **Strike Selection (Delta):** The short put strike is selected at the **10 Delta** level. This means there is roughly a 10% probability that the option will expire in-the-money (ITM), providing a high probability of success on the initial setup.
*   **Trend Filter:** A technical filter is applied to ensure trades are only taken in a generally bullish or neutral market environment. The strategy requires SPY to be trading **above its 200-day Simple Moving Average (SMA)**. If the market is below the 200-day SMA, no trade is entered for that week.

## Spread Width and Capital Allocation

The width of the spread (the difference between the short and long put strikes) significantly impacts the risk/reward profile. Wider spreads collect more premium but have a larger maximum loss per contract. Therefore, position sizing must be adjusted to maintain consistent risk across different spread widths.

The strategy assumes a total account size of $50,000, with a maximum capital allocation of **$20,000 per trade**. The remaining $30,000 is held in cash (ideally earning a risk-free interest rate).

To maintain the $20,000 risk limit, the number of contracts traded varies based on the chosen spread width:

| Spread Width | Contracts Traded | Max Risk per Contract | Total Capital at Risk |
| :--- | :--- | :--- | :--- |
| **$2.50** | 80 | ~$250 | ~$20,000 |
| **$4.00** | 50 | ~$400 | ~$20,000 |
| **$5.00** | 40 | ~$500 | ~$20,000 |
| **$10.00** | 20 | ~$1,000 | ~$20,000 |
| **$20.00** | 10 | ~$2,000 | ~$20,000 |

*Note: The actual max risk per contract is slightly less than the spread width minus the credit received, but for sizing purposes, the full width is often used as a conservative estimate.*

## Trade Management and Exit Rules

Proper management is crucial for long-term success, as taking full maximum losses can severely damage the portfolio. The strategy utilizes a "Hybrid Exit" approach to balance capturing premium with mitigating risk.

### 1. Stop Loss (The "Tested" Rule)
If the SPY market price closes below the short put strike price at any point during the life of the trade, the position is closed immediately to prevent further losses.

### 2. Hybrid Exit Strategy (1 DTE vs. Expiration)
The decision to hold the trade until expiration or close it early (at 1 DTE, typically Thursday) depends on how far out-of-the-money the short strike is and the width of the spread.

*   **For Narrow Spreads ($2.50 and $4.00 Widths):**
    *   Close the trade at 1 DTE unless the SPY price is at least **2.00% Out-of-the-Money (OTM)** relative to the short strike.
    *   If SPY is >2.00% OTM, hold the position through expiration to capture the remaining premium.
*   **For Wider Spreads ($5.00, $10.00, and $20.00 Widths):**
    *   Close the trade at 1 DTE unless the SPY price is at least **0.50% OTM** relative to the short strike.
    *   If SPY is >0.50% OTM, hold the position through expiration.

This hybrid approach recognizes that wider spreads provide a larger buffer and can tolerate being held closer to expiration with a smaller OTM cushion compared to narrow spreads.

## Performance Characteristics by Width

Based on historical backtesting of the optimized hybrid model, different spread widths exhibit distinct performance profiles:

*   **$25 Wide:** Generates the highest absolute total profit but experiences the highest volatility and maximum drawdowns (approx. 16.30%).
*   **$50 Wide:** Identified as the "Best Balance Candidate," offering strong profit potential with slightly improved risk metrics (max drawdown approx. 14.80%).
*   **$200 Wide:** Identified as the "Best Risk-Adjusted" candidate. While it produces lower absolute profit, it offers a significantly smoother equity curve, the lowest maximum drawdown (approx. 7.83%), and the highest Sharpe and Sortino ratios.

The choice of spread width depends on the trader's individual risk tolerance and preference for absolute return versus portfolio stability.

## References

[1] Income Academy. "Amazing 7 DTE SPX Put Credit Spread Case Study!" YouTube, https://youtu.be/Fip0OY11NGg?si=K5AwQF49QCsUk7v9. Tradov adapts the structure to SPY options for live use.
