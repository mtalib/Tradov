# SPY 7 DTE Put Credit Spread Strategy Description (Revised)

**Author:** Manus AI
**Date:** May 29, 2026

## Overview

The SPY 7 DTE Put Credit Spread is an income-generating options strategy designed to collect premium by selling out-of-the-money (OTM) put spreads on the SPDR S&P 500 ETF (SPY) with approximately seven days to expiration (DTE). This strategy capitalizes on time decay (theta) and the tendency of equity markets to drift higher or remain stable over short periods. By using a credit spread rather than a naked put, the strategy strictly defines the maximum risk per trade [1].

This implementation adapts the original SPX case-study template to SPY, adjusting for the live option chain, strike spacing, and position-sizing defaults relevant to the SPY product [1]. This document outlines the specific rules, entry criteria, management techniques, and performance expectations based on the analysis of the provided case study and additional research.

## Core Mechanics

A put credit spread (also known as a bull put spread) involves two simultaneous options transactions:
1.  **Selling a Put Option:** This generates an upfront credit and establishes the level where the trader expects the underlying asset (SPY) to stay above.
2.  **Buying a Put Option (Lower Strike):** This is purchased for a debit and serves as protection, capping the maximum potential loss if the market experiences a severe downturn.

The net result is a credit received into the account. The strategy is profitable if the SPY closes above the short put strike at expiration, allowing both options to expire worthless and the trader to keep the entire initial credit.

## Entry Criteria

The strategy employs a systematic approach to entry, removing emotional decision-making and focusing on high-probability setups [1] [2].

*   **Timing:** Trades are initiated weekly on Fridays. If the market is closed on Friday due to a holiday, the trade is entered on the preceding Thursday [1].
*   **Entry Clock:** Entries are typically taken near the market close, with **3:45 PM ET** as a default implementation time. This timing helps the strategy rely on the session's settled trend and volatility rather than intraday noise [1].
*   **Strike Selection (Delta):** The short put strike is selected at the **10 Delta** level. This implies a roughly 10% probability that the option will expire in-the-money (ITM), providing a high probability of success on the initial setup [1]. Some variations suggest a 15-20 Delta for potentially higher premium capture, though this increases risk [2].
*   **Trend Filter:** A technical filter is applied to ensure trades are only taken in a generally bullish or neutral market environment. The strategy requires SPY to be trading **above its 200-day Simple Moving Average (SMA)**. If the market is below the 200-day SMA, no trade is entered for that week, acting as a proxy for market volatility and trend regime [1].
*   **Spread Width (SPY Specific):** SPY options typically have $1 strike increments. For example, a $5-wide spread would involve a long put five strikes below the short put [2].

## Spread Width and Capital Allocation

The width of the spread (the difference between the short and long put strikes) significantly impacts the risk/reward profile. Wider spreads collect more premium but have a larger maximum loss per contract. Therefore, position sizing must be adjusted to maintain consistent risk across different spread widths [1].

The strategy assumes a total account size of $50,000, with a maximum capital allocation of **$20,000 per trade**. The remaining $30,000 is held in cash (ideally earning a risk-free interest rate) [1].

To maintain the $20,000 risk limit, the number of contracts traded varies based on the chosen spread width:

| Spread Width | Contracts Traded | Max Risk per Contract | Total Capital at Risk |
| :--- | :--- | :--- | :--- |
| **$2.50** | 80 | ~$250 | ~$20,000 |
| **$4.00** | 50 | ~$400 | ~$20,000 |
| **$5.00** | 40 | ~$500 | ~$20,000 |
| **$10.00** | 20 | ~$1,000 | ~$20,000 |
| **$20.00** | 10 | ~$2,000 | ~$20,000 |

*Note: The actual max risk per contract is slightly less than the spread width minus the credit received, but for sizing purposes, the full width is often used as a conservative estimate [1].*

## Trade Management and Exit Rules

Proper management is crucial for long-term success, as taking full maximum losses can severely damage the portfolio. The strategy utilizes a "Hybrid Exit" approach to balance capturing premium with mitigating risk [1].

### 1. Stop Loss
If the SPY market price **closes below the short put strike price** at any point during the life of the trade, the position is closed immediately to prevent further losses [1].

### 2. Hybrid Exit Strategy (1 DTE vs. Expiration)
The decision to hold the trade until expiration or close it early (at 1 DTE, typically Thursday) depends on how far out-of-the-money the short strike is and the width of the spread [1]. This approach specifically addresses gamma risk, which becomes significant in the last 24-48 hours before expiration [2].

*   **For Narrow Spreads ($2.50 and $4.00 Widths):**
    *   Close the trade at 1 DTE unless the SPY price is at least **2.00% Out-of-the-Money (OTM)** relative to the short strike.
    *   If SPY is >2.00% OTM, hold the position through expiration to capture the remaining premium [1].
*   **For Wider Spreads ($5.00, $10.00, and $20.00 Widths):**
    *   Close the trade at 1 DTE unless the SPY price is at least **0.50% OTM** relative to the short strike.
    *   If SPY is >0.50% OTM, hold the position through expiration [1].

This hybrid approach recognizes that wider spreads provide a larger buffer and can tolerate being held closer to expiration with a smaller OTM cushion compared to narrow spreads [1].

### 3. Profit Targets
While the primary backtested strategy focuses on the hybrid exit, an alternative management technique involves taking profits early. Many traders suggest closing winning trades when they have captured **50% of the maximum credit received**. For example, if $0.70 credit was received, the trade would be closed when its value drops to $0.35. This approach allows for quicker redeployment of capital and can lead to higher annualized returns, though it may forgo some potential premium [2].

## Risk Management Nuances

*   **Gamma Risk:** As options approach expiration, their sensitivity to price changes (gamma) increases dramatically. The hybrid exit strategy is designed to mitigate this by closing 
"at-risk" spreads early, typically at 1 DTE [1] [2].
*   **Assignment and Pin Risk:** Because SPY is an Exchange Traded Fund (ETF) with physical delivery, holding options through expiration carries assignment risk. If the spread expires partially in-the-money (between the short and long strikes), the trader may be assigned shares over the weekend, leading to "pin risk." This is a key difference from cash-settled index options like SPX. The hybrid exit is therefore critical for SPY traders to avoid unwanted share assignment [2].

## Performance Characteristics by Width

Based on historical backtesting of the optimized hybrid model (adapted from SPX equivalents), different spread widths exhibit distinct performance profiles [1]:

*   **$2.50 Wide (SPX $25 equivalent):** Generates the highest absolute total profit but experiences the highest volatility and maximum drawdowns (approx. 16.30%).
*   **$5.00 Wide (SPX $50 equivalent):** Identified as the "Best Balance Candidate," offering strong profit potential with slightly improved risk metrics (max drawdown approx. 14.80%).
*   **$20.00 Wide (SPX $200 equivalent):** Identified as the "Best Risk-Adjusted" candidate. While it produces lower absolute profit, it offers a significantly smoother equity curve, the lowest maximum drawdown (approx. 7.83%), and the highest Sharpe and Sortino ratios.

The choice of spread width depends on the trader's individual risk tolerance and preference for absolute return versus portfolio stability.

## References

[1] Income Academy. "Amazing 7 DTE SPX Put Credit Spread Case Study!" YouTube, https://youtu.be/Fip0OY11NGg. Spyder adapts the structure to SPY options for live use.
[2] Options Cafe. "SPY Put Credit Spreads Strategy: Rules and a 91% Win Rate." https://options.cafe/blog/spy-put-credit-spreads-strategy/.
