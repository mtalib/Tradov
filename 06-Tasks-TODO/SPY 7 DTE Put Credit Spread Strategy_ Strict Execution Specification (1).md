# SPY 7 DTE Put Credit Spread Strategy: Strict Execution Specification

**Author:** Manus AI
**Date:** May 29, 2026

## Overview

This document serves as the strict execution specification for the SPY 7 DTE Put Credit Spread strategy. It defines the exact, deterministic parameters required for automated or systematic trading, eliminating ambiguity in entry, management, and exit rules. The strategy involves selling out-of-the-money (OTM) put spreads on the SPDR S&P 500 ETF (SPY) with approximately seven days to expiration (DTE) to capture theta decay in a defined-risk framework [1].

## Core Mechanics

A put credit spread consists of two simultaneous options transactions:
1.  **Selling a Put Option:** Generates an upfront credit and establishes the price level above which SPY is expected to remain.
2.  **Buying a Put Option (Lower Strike):** Purchased for a debit to cap the maximum potential loss.

The strategy is profitable if SPY closes above the short put strike at expiration, allowing both options to expire worthless.

## Entry Criteria (Strict Parameters)

The strategy employs a deterministic approach to entry [1] [2].

*   **Timing:** Trades are initiated weekly on Fridays. Should Friday be a market holiday, the trade will be entered on the preceding Thursday [1].
*   **Entry Clock:** Entries are executed at exactly **3:45 PM ET** [1].
*   **Trend Filter (SMA200 Buffer):** The strategy strictly requires SPY to be trading above its 200-day Simple Moving Average (SMA) plus a **0.50% buffer**.
    *   **Formula:** `Price > SMA200 * 1.005`
    *   *Rationale:* A 0.5% buffer acts as a standard institutional noise filter to prevent frequent whipsaws while maintaining responsiveness to trend shifts [1].
*   **Strike Selection (Deterministic Fallback Logic):** The system shall follow this strict hierarchy for selecting the short strike:
    1.  **Primary:** Select the strike with a Delta closest to **-0.10** (10 Delta) [1].
    2.  **Fallback 1 (Liquidity Check & Search):** If the primary 10-delta strike does not meet the liquidity thresholds, the system will search within a range of **+/- 2 strikes** from the initial 10-delta target. Among all strikes within this range that meet the liquidity thresholds, the system will select the one whose delta is closest to -0.10. If multiple strikes have the same 'closest delta' and meet liquidity, the system will prefer the strike that is further Out-of-the-Money (i.e., a lower strike for a put option).
    3.  **Fallback 2 (Volatility/Z-score):** If no liquid strike is found within the +/- 2 strike range, calculate the theoretical strike using: `Strike = Current Price * (1 - (7-day IV / sqrt(365)) * 1.28)`. Select the nearest available strike to this calculated value.
    4.  **Fallback 3 (Safety):** If Fallback 2 fails (e.g., missing IV data), the system must **Fail-Closed** (no trade entered).
*   **Liquidity Thresholds:** A strike is considered "sufficiently liquid" for automated entry if it meets ALL of the following criteria at the time of entry:
    *   **Bid-Ask Spread:** ≤ 10% of the mid-price.
    *   **Open Interest:** ≥ 500 contracts.
    *   **Daily Volume:** ≥ 100 contracts.
*   **Spread Width:** SPY options typically feature $1 strike increments. The long put is purchased at a defined width below the short put (e.g., $5 wide) [2].

## Spread Width and Capital Allocation

Position sizing is dynamically adjusted to maintain consistent risk across varying spread widths [1].

*   **Account Size:** Assumed $50,000.
*   **Max Risk Per Trade:** $20,000.
*   **Dynamic Sizing Formula:** `Contracts = floor(MaxRiskBucket / (SpreadWidth * 100))`

| Spread Width | Contracts Traded | Max Risk per Contract | Total Capital at Risk |
| :--- | :--- | :--- | :--- |
| **$2.50** | 80 | ~$250 | ~$20,000 |
| **$4.00** | 50 | ~$400 | ~$20,000 |
| **$5.00** | 40 | ~$500 | ~$20,000 |
| **$10.00** | 20 | ~$1,000 | ~$20,000 |
| **$20.00** | 10 | ~$2,000 | ~$20,000 |

## Trade Management and Exit Rules

The strategy employs a strict hierarchy for exits to balance premium capture with risk mitigation [1].

### Exit Precedence Rule
The system evaluates exits in the following strict order:
`Stop-Loss > Profit Target (if enabled) > Time-Based Exit (1 DTE / 0 DTE)`

### 1. Stop Loss (Highest Precedence)
An immediate exit is triggered if the SPY market price experiences a **5-minute bar close below the short put strike price** at any point during the trade's duration. This rule is always active [1].

### 2. Profit Target (Optional Configuration)
If the optional profit target flag is enabled, trades will be closed immediately when they have captured **50% of the maximum credit received**. If this target is hit, it overrides the time-based exits [2].

### 3. Expiration Handling and Hybrid Exit Strategy
If neither the stop-loss nor the profit target is triggered, the strategy follows the time-based hybrid exit logic [1]:

*   **1 DTE Decision (Thursday Close):** The decision to hold a trade from Thursday (1 DTE) to Friday (0 DTE) is based on the following criteria:
    *   **For Narrow Spreads ($2.50 and $4.00 Widths):** Hold to Friday (0 DTE) only if SPY is at least **2.00% Out-of-the-Money (OTM)** relative to the short strike at the Thursday close. Otherwise, close on Thursday.
    *   **For Wider Spreads ($5.00, $10.00, and $20.00 Widths):** Hold to Friday (0 DTE) only if SPY is at least **0.50% OTM** relative to the short strike at the Thursday close. Otherwise, close on Thursday.
*   **Mandatory Close for 0 DTE:** Any spread held until Friday (0 DTE) **MUST be closed by 3:55 PM ET**, regardless of its out-of-the-money status. This strictly prevents physical assignment and pin risk associated with SPY options [2].

## Holiday and Target Expiry Handling

When the exact 7 DTE target expiration is unavailable:
*   **Step Logic:** The system will step to the nearest valid weekly expiration within a range of **+/- 2 days** from the original 7 DTE target.
*   **Tie-Breaking Rule:** If two valid weekly expirations are equidistant from the 7 DTE target (e.g., 5 DTE and 9 DTE), the system shall prefer the **Later Expiry** (e.g., 9 DTE). This provides more time for theta decay and avoids the accelerated gamma risk of the shorter-dated contract.
*   **Fail-Closed:** If no valid expiration exists within the +/- 2 day window, the system will fail-closed (no trade entered).

## Performance Claims and Deployment Path

Performance claims (e.g., highest P&L, best risk-adjusted) are **External Research Context** derived from historical backtesting on SPX equivalents [1].

The intended deployment path is **Paper-First**. Live deployment to the decision stack requires a minimum of four consecutive weeks of paper trading execution that consistently matches this strict specification without significant slippage anomalies.

## References

[1] Income Academy. "Amazing 7 DTE SPX Put Credit Spread Case Study!" YouTube, https://youtu.be/Fip0OY11NGg. Spyder adapts the structure to SPY options for live use.
[2] Options Cafe. "SPY Put Credit Spreads Strategy: Rules and a 91% Win Rate." https://options.cafe/blog/spy-put-credit-spreads-strategy/.
