Pairs trading is a market-neutral statistical arbitrage strategy. Instead of betting on the market's direction, it relies on the historical relationship—specifically **cointegration**—between two highly correlated assets.

When the price ratio (the spread) between these two assets diverges beyond a certain threshold (usually measured by a Z-score), a trader shorts the overperforming asset and goes long on the underperforming one. The profit is realized when the historical relationship reasserts itself and the spread converges back to the mean.

Here is a look at the mechanics of this strategy in action.

To execute this effectively, institutional and algorithmic traders focus on assets that share underlying fundamental drivers—meaning they are exposed to the exact same macroeconomic forces, supply chains, or regulatory environments.

Here are the most popular instruments used for pairs trading across equities and ETFs.

## Minimum Viable Corpus for v1

Before expanding into a broad universe, keep the corpus deliberately small so the system can prove the full pipeline end to end:

1. **Start with three live pairs.** Use a small, highly liquid set of pairs that already appears in this note.
2. **Use one negative-control pair.** Add one unrelated pair whose spread should usually fail cointegration so the rejection path is tested.
3. **Keep one rolling window.** Do not maintain multiple lookback regimes until the baseline path is stable.
4. **Keep one signal rule set.** Use one ADF threshold and one Z-score entry/exit configuration.
5. **Delay portfolio logic.** Do not add pair portfolios, sector baskets, or ranking systems until the three-pair workflow is working reliably.

Recommended v1 corpus:

- **Live pair 1:** `SPY` / `IWM`
- **Live pair 2:** `KO` / `PEP`
- **Live pair 3:** `XOM` / `CVX`
- **Negative control:** one unrelated cross-sector pair selected to fail or weaken cointegration

Related artifacts:

- [Pair-Trading-Corpus-v1-Checklist.md](/home/adam/Projects/Tradov/05-Research/Pair-Trading-Corpus-v1-Checklist.md)
- [pair_trading_corpus_v1.json](/home/adam/Projects/Tradov/config/pair_trading_corpus_v1.json)

Selection rules for v1:

- Prefer liquid, widely traded instruments with stable data quality.
- Prefer pairs already justified by the note's sector or macro linkage.
- Exclude pairs with obvious event risk, thin liquidity, or ambiguous economic linkage.
- Exclude any pair that only looks good by correlation and has not passed cointegration testing.

Exit criteria for moving beyond v1:

- The data ingestion path works without manual intervention.
- Cointegration testing produces consistent, explainable results.
- Spread construction and Z-score signals are reproducible.
- Rejection logic correctly blocks the negative-control pair.
- Nightly or rolling revalidation does not break the workflow.

## Most Popular Stock Pairs

Stock pairs are almost always selected from within the same sector. Traders look for companies with similar market capitalizations, identical business models, and comparable sensitivities to input costs.

| Sector | Ticker Pair | The Rationale |
| --- | --- | --- |
| **Consumer Staples** | **KO** (Coca-Cola) vs **PEP** (PepsiCo) | The classic statistical arbitrage pair. Both are global beverage giants driven by identical consumer spending cycles and input costs (corn syrup, aluminum). |
| **Technology** | **V** (Visa) vs **MA** (Mastercard) | Nearly identical payment processing business models and regulatory environments. A highly favored pair for tight spread trading. |
| **Energy** | **XOM** (ExxonMobil) vs **CVX** (Chevron) | Both are integrated oil majors whose revenues are heavily dictated by the global spot price of crude oil. |
| **Financials** | **JPM** (JPMorgan) vs **BAC** (Bank of America) | Large-cap banking pairs react uniformly to Federal Reserve interest rate changes and yield curve shifts. |
| **Retail** | **WMT** (Walmart) vs **TGT** (Target) | Both dominate big-box retail and face the exact same consumer sentiment and supply chain pressures. |

## Most Popular ETF Pairs

ETFs are often preferred over individual stocks for pairs trading because they eliminate single-company risk (like an unexpected CEO departure or a poor earnings report) and generally have lower borrow costs for shorting.

| Category | Ticker Pair | The Rationale |
| --- | --- | --- |
| **Broad Market Index** | **SPY** (S&P 500) vs **QQQ** (Nasdaq 100) | Exploits the relative performance difference between tech-heavy growth (QQQ) and broader market exposure (SPY). |
| **Cap-Size Index** | **SPY** (S&P 500) vs **IWM** (Russell 2000) | A classic macro trade betting on the relative strength of large-cap multinationals versus domestic small-cap companies. |
| **Sector Rotation** | **XLK** (Tech) vs **XLU** (Utilities) | A common "risk-on / risk-off" trade. When markets surge, tech outpaces utilities; during a flight to safety, the spread reverses. |
| **Intra-Sector Size** | **XLF** (Large Financials) vs **PSCF** (Small Financials) | Trades the spread between massive institutional banks and regional banks while remaining perfectly hedged against the broader financial sector. |
| **Commodity vs Equity** | **GLD** (Gold) vs **GDX** (Gold Miners) | Gold miners typically trade at a premium to physical gold due to operating leverage. If that premium collapses, traders will buy miners and short physical gold. |

> **Key insight:** The most common mistake in pairs trading is confusing *correlation* with *cointegration*. Two tech stocks might be highly correlated because the whole market is going up, but if they aren't cointegrated, the spread between them may never revert to the mean, leaving you trapped in the trade.


To build a robust algorithmic trading engine, proving cointegration mathematically is the mandatory first step before routing any actual orders. Relying purely on correlation is a common trap; highly correlated assets can still drift infinitely far apart over time, which will blow up a market-neutral portfolio.

Cointegration, on the other hand, guarantees that the spread between the two assets is **stationary**—meaning it has a constant mean and variance, and predictably reverts to that mean.

Here is the statistical framework and the Python logic used to prove it, relying on the **Engle-Granger two-step method** and the **Augmented Dickey-Fuller (ADF) test**.

### The Statistical Framework

The Engle-Granger method works by creating a synthetic asset (the spread) and testing its properties.

**1. Ordinary Least Squares (OLS) Regression**
First, we run a linear regression between the price of Asset $Y$ and Asset $X$ to find the hedge ratio ($\beta$).

$Y_t = \beta X_t + \alpha + \epsilon_t$

* $Y_t$ and $X_t$ are the asset prices.
* $\beta$ is the hedge ratio (how much of $X$ to short for every share of $Y$ you buy).
* $\epsilon_t$ is the residual error (the spread).

**2. The Spread Calculation**
We isolate the residual error to create our time-series spread:

$\epsilon_t = Y_t - \beta X_t - \alpha$

**3. Augmented Dickey-Fuller (ADF) Test**
We apply the ADF test to the spread ($\epsilon_t$). The ADF test checks for the presence of a "unit root."

* **Null Hypothesis ($H_0$):** The spread has a unit root (it is non-stationary and wanders randomly).
* **Alternative Hypothesis ($H_1$):** The spread does not have a unit root (it is stationary and mean-reverting).

If the resulting p-value is less than your significance level (typically $0.05$), you reject the null hypothesis and confirm the pair is mathematically cointegrated.

---

### The Python Implementation

To run this in a Python backend, you will need `pandas`, `numpy`, and `statsmodels`. This script assumes you have historical daily close data for two tickers, like SPY and a comparable index ETF.

```python
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

def test_cointegration(asset_y: pd.Series, asset_x: pd.Series) -> dict:
    """
    Tests two price series for cointegration using the Engle-Granger method.
    
    Parameters:
    asset_y (pd.Series): Time series data for Asset Y (Dependent variable)
    asset_x (pd.Series): Time series data for Asset X (Independent variable)
    
    Returns:
    dict: A dictionary containing the hedge ratio, spread, ADF statistic, and p-value.
    """
    
    # Step 1: Run OLS Regression to find the hedge ratio
    # We add a constant to Asset X to account for the intercept (alpha)
    x_with_constant = sm.add_constant(asset_x)
    model = sm.OLS(asset_y, x_with_constant).fit()
    
    # The slope coefficient is our hedge ratio
    hedge_ratio = model.params.iloc[1]
    
    # Step 2: Calculate the historical spread (the residuals)
    # Spread = Y - (Hedge Ratio * X)
    spread = asset_y - (hedge_ratio * asset_x)
    
    # Step 3: Run the Augmented Dickey-Fuller test on the spread
    adf_result = adfuller(spread, autolag='AIC')
    adf_statistic = adf_result[0]
    p_value = adf_result[1]
    critical_values = adf_result[4]
    
    # Determine if cointegrated (using 95% confidence / 0.05 alpha)
    is_cointegrated = p_value < 0.05
    
    return {
        "is_cointegrated": is_cointegrated,
        "hedge_ratio": hedge_ratio,
        "adf_statistic": adf_statistic,
        "p_value": p_value,
        "critical_values": critical_values,
        "spread_series": spread
    }

# --- Example Usage ---

# Simulating historical data retrieval for SPY and IWM
# In production, this data would stream from a provider like Polygon or Tradier
np.random.seed(42)
dates = pd.date_range(start='2025-01-01', periods=252)

# Creating a synthetic cointegrated relationship for demonstration
spy_prices = pd.Series(np.cumsum(np.random.randn(252)) + 500, index=dates, name="SPY")
# IWM walks with SPY but adds some stationary noise
iwm_prices = pd.Series(spy_prices * 0.45 + np.random.randn(252) * 2, index=dates, name="IWM") 

# Run the test
results = test_cointegration(spy_prices, iwm_prices)

print(f"Cointegrated: {results['is_cointegrated']}")
print(f"Hedge Ratio (Beta): {results['hedge_ratio']:.4f}")
print(f"ADF P-Value: {results['p_value']:.4f}")

# Next Step: Calculate Z-Score of the spread to generate trading signals
def calculate_zscore(spread: pd.Series) -> pd.Series:
    return (spread - spread.mean()) / spread.std()

z_score_series = calculate_zscore(results['spread_series'])

```

### Translating the Math into Trading Logic

Once `is_cointegrated` returns `True`, the execution module of your system can take over:

1. **Sizing:** The `hedge_ratio` tells your execution logic exactly how to balance the legs. If the ratio is $0.45$, for every $100$ shares of SPY you short, you buy $45$ shares of the opposing ETF.
2. **Signals:** You stream live data into the `calculate_zscore` function. When the live Z-score crosses a threshold (e.g., $> 2.0$), your system fires a short signal for the spread. When it crosses back to $0.0$, it sends the closing orders.
3. **Validation:** Because market dynamics shift, cointegration is not permanent. Systems should automatically re-run the ADF test on a rolling window (e.g., the last $60$ or $90$ days) every single night. If a pair's p-value slips above $0.05$, the system should halt trading on that pair until the structural relationship re-establishes itself.
