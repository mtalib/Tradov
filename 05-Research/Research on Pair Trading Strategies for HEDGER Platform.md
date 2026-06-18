# Research on Pair Trading Strategies for HEDGER Platform

## 1. Introduction

This document presents a comprehensive overview of pair trading strategies, drawing insights from leading open-source GitHub repositories and commercial applications. The goal is to identify effective strategies, key concepts, and Python implementation patterns to inform the development of the HEDGER platform, a new pair trading system.

Pair trading is a market-neutral statistical arbitrage strategy that exploits temporary divergences in the prices of two historically correlated or cointegrated assets. The core idea involves simultaneously buying the underperforming asset and selling the overperforming asset, betting on the convergence of their prices back to their historical relationship. This approach aims to generate profits regardless of overall market direction, making it an attractive strategy for risk-averse traders.

## 2. Commercial Pair Trading Applications

Commercial pair trading platforms offer sophisticated tools for pair selection, backtesting, and automated execution. Two prominent examples are PairTrade Finder® and Pair Trading Lab.

### 2.1. PairTrade Finder® (PTF) Ultimate Alpha 3 (UA3)

PairTrade Finder® UA3 is a leading commercial platform that employs a systematic approach to stock pair trading. Its methodology is built upon several layers of analysis to identify high-probability trades [1].

**Key Features and Strategies:**

*   **Cointegration and Correlation:** PTF UA3 emphasizes selecting pairs that exhibit strong cointegration and correlation, ensuring a stable long-term relationship between their prices. This is a fundamental statistical validation step [2].
*   **Sector and Business Fit:** Beyond statistical measures, the platform incorporates qualitative filters such as sector and business fit, ensuring that the paired assets are fundamentally related and likely to maintain their relationship [2].
*   **News Shock Score:** To mitigate risks from sudden, unpredictable events, PTF UA3 includes a
News Shock Score to avoid signals driven by fundamental corporate events that could disrupt the pair's relationship [2].
*   **Relative Edge Score:** This feature provides dynamic, regime-sensitive technical confirmation on each leg of the pair, enhancing the timing and accuracy of trades [2].
*   **Ornstein-Uhlenbeck (OU) Half-Life Filter:** A crucial innovation, this filter measures the speed at which a spread reverts to its mean. It helps in selecting only those pairs that revert quickly enough to be profitable, discarding statistically valid but economically unviable pairs. Pairs with a half-life greater than 45 days are typically filtered out [2].
*   **Entry and Exit Rules:** A common strategy involves entering trades when the spread's Z-score deviates significantly (e.g., Z > 2.0 for shorting the spread, Z < -2.0 for longing the spread) and exiting when the Z-score returns to the mean (0.0) or a narrower band (e.g., 0.5) [3].
*   **Portfolio Approach:** PTF UA3 advocates for trading a portfolio of 50+ pairs to maintain market neutrality and diversify risk [2].

### 2.2. Pair Trading Lab

Pair Trading Lab offers a suite of tools for setting up and managing pair trading portfolios, including a vast database of pre-analyzed pairs and an automated trading platform called PTL Trader [4].

**Key Features:**

*   **Extensive Pair Database:** The platform boasts a database of up to 10 million pre-analyzed pairs, providing a rich source for pair selection [4].
*   **Online Backtester and Cointegration Analyzer:** These tools allow users to verify pair trading ideas, inspect behavior, and analyze cointegration residuals [4].
*   **PTL Trader:** This lightweight, cross-platform application facilitates automated or semi-automated trading of U.S. equity pair strategy portfolios, primarily supporting Interactive Brokers as a data and execution backend. Notably, PTL Trader became free and open-source software in 2021 (version 1.6.0) and is licensed under GNU GPL v3 [5].

## 3. Open-Source GitHub Repositories and Python Implementations

Several open-source projects on GitHub provide valuable insights into implementing pair trading strategies in Python. These repositories often demonstrate the application of statistical tests and trading logic.

### 3.1. QuantConnect Research

QuantConnect's research repository includes a Jupyter Notebook (`05 Pairs Trading Strategy Based on Cointegration.ipynb`) that illustrates a cointegration-based pair trading strategy. This example often uses highly correlated assets like ExxonMobil (XOM) and Chevron (CVX) due to their presence in the same industry [6].

**Key Implementation Aspects:**

*   **Cointegration Testing:** The notebook demonstrates the use of the Augmented Dickey-Fuller (ADF) test to check for cointegration between asset prices. The `statsmodels` library in Python is commonly used for this purpose [6].
*   **Hedge Ratio Calculation:** Linear regression, typically Ordinary Least Squares (OLS), is applied to determine the hedge ratio between the two assets. This ratio is crucial for constructing a dollar-neutral or beta-neutral spread [6].
*   **Spread Calculation and Z-score:** The spread is calculated based on the hedge ratio, and its stationarity is confirmed through cointegration. The Z-score of this spread is then used to identify entry and exit points for trades.

### 3.2. `quantverse/ptltrader`

While the PTL Trader application itself is primarily Java-based, its open-source nature under the GNU GPL v3 license allows for examination of its underlying logic for portfolio-based automated trading. Although the core application is not in Python, the principles of managing a portfolio of pair trades and interacting with brokers are highly relevant [5].

### 3.3. `AJeanis/Pairs-Trading` and `arnavkohli/statistical-arbitrage-pairs-trading`

These repositories, among others, provide Python implementations focusing on statistical arbitrage and cointegration. They often feature:

*   **`statsmodels` for Cointegration:** Extensive use of `statsmodels.tsa.stattools.coint` for Engle-Granger two-step cointegration tests and `adfuller` for stationarity checks on residuals.
*   **Data Acquisition:** Libraries like `yfinance` are commonly used to fetch historical stock data.
*   **Spread and Z-score Calculation:** Python code for calculating the spread and its rolling Z-score, which is central to generating trading signals.

## 4. Pair Trading Strategies and Python Implementation Techniques

Effective pair trading relies on a combination of robust statistical analysis and well-defined trading rules. The following sections detail key strategies and their Python implementation.

### 4.1. Cointegration-Based Strategy

**Concept:** Cointegration is a statistical property indicating that two or more time series have a long-term, stable relationship, even if they are individually non-stationary. Their linear combination (the spread) is stationary and mean-reverting. This is a stronger condition than mere correlation [7].

**Python Implementation:**

*   **Data Collection:** Obtain historical price data for potential pairs using libraries like `yfinance`.
*   **Cointegration Test:** Apply the Engle-Granger two-step cointegration test using `statsmodels.tsa.stattools.coint`. A low p-value (e.g., < 0.05) suggests cointegration.
*   **Hedge Ratio:** Perform an Ordinary Least Squares (OLS) regression of one asset's price on the other to determine the hedge ratio. This ratio represents the number of units of the second asset needed to hedge one unit of the first asset.
*   **Spread Calculation:** Construct the spread as `Spread = Price_A - Hedge_Ratio * Price_B`.
*   **Stationarity Check:** Verify the stationarity of the spread using the Augmented Dickey-Fuller (ADF) test (`statsmodels.tsa.stattools.adfuller`).

### 4.2. Z-score for Entry and Exit Signals

**Concept:** The Z-score measures how many standard deviations an observation is from the mean. In pair trading, it quantifies the deviation of the spread from its historical average, indicating overextension or undervaluation [3].

**Python Implementation:**

*   **Rolling Mean and Standard Deviation:** Calculate the rolling mean and standard deviation of the spread over a defined look-back window (e.g., 60 or 120 days).
*   **Z-score Calculation:** `Z-score = (Current_Spread - Rolling_Mean) / Rolling_Std_Dev`.
*   **Trading Signals:**
    *   **Entry Long (Spread):** When Z-score falls below a negative threshold (e.g., -2.0), indicating the spread is significantly undervalued. Long the undervalued asset, short the overvalued asset.
    *   **Entry Short (Spread):** When Z-score rises above a positive threshold (e.g., 2.0), indicating the spread is significantly overvalued. Short the overvalued asset, long the undervalued asset.
    *   **Exit:** When the Z-score reverts to a neutral level (e.g., between -0.5 and 0.5) or crosses zero, indicating the spread has converged.

### 4.3. Ornstein-Uhlenbeck (OU) Process for Mean Reversion

**Concept:** The Ornstein-Uhlenbeck process is a continuous-time stochastic process that models mean-reverting behavior. It is particularly useful for understanding the dynamics of the spread and estimating its mean reversion speed [8].

**Python Implementation:**

*   **Parameter Estimation:** The OU process parameters (mean reversion speed `lambda`, long-term mean `mu`, and volatility `sigma`) can be estimated by fitting an Autoregressive (AR(1)) model to the spread series. The half-life of mean reversion can then be calculated as `ln(2) / lambda`.
*   **Trading Decisions:** The half-life provides a quantitative measure of how quickly the spread is expected to revert. This can be used as a filter for pair selection (e.g., only trade pairs with a half-life below a certain threshold) or to dynamically adjust position sizing and holding periods [2].

### 4.4. Kalman Filter for Dynamic Hedge Ratio

**Concept:** Traditional OLS regression assumes a constant hedge ratio, which may not hold true in dynamic market conditions. The Kalman filter provides a recursive, online method to estimate the hedge ratio dynamically, adapting to changing relationships between assets [9].

**Python Implementation:**

*   **State-Space Model:** The Kalman filter models the hedge ratio as a hidden state that evolves over time. The observation equation relates the observed prices to this hidden state.
*   **Dynamic Hedge Ratio:** Libraries like `pykalman` can be used to implement the Kalman filter, which continuously updates the estimated hedge ratio. This dynamic adjustment can lead to a more stationary spread and improved trading performance [9].
*   **Trading Signals:** The forecast error (residual) from the Kalman filter can be used similarly to the Z-score to generate entry and exit signals, with thresholds based on the standard deviation of the forecast error [9].

## 5. Best Pairs and Strategies

Identifying the
best pairs for pair trading is crucial for the strategy's success. While specific pairs can vary over time due to market dynamics, certain characteristics and approaches consistently yield promising results.

### 5.1. Characteristics of Good Pairs

*   **High Cointegration:** The most critical factor is a strong, stable cointegrating relationship between the two assets. This ensures that their spread is mean-reverting.
*   **Economic Linkage:** Pairs should ideally belong to the same industry or sector, or have a strong economic rationale for moving together. Examples include competitors, companies with similar business models, or those affected by the same macroeconomic factors [3].
*   **Similar Market Capitalization and Liquidity:** Assets with comparable market capitalization and liquidity tend to exhibit more stable relationships and are easier to trade without significant market impact.
*   **Low Fundamental Event Risk:** Avoid pairs where one or both assets are prone to significant, unpredictable fundamental events (e.g., regulatory changes, product recalls, M&A rumors) that could permanently alter their relationship.

### 5.2. Examples of Common Pair Types

*   **Sector-Specific Pairs:** Two companies within the same sector, such as Coca-Cola (KO) and PepsiCo (PEP) in consumer goods, or ExxonMobil (XOM) and Chevron (CVX) in energy [3].
*   **Index Components:** Two stocks that are components of the same index and have similar industry classifications.
*   **ETFs:** Exchange-Traded Funds (ETFs) tracking similar sectors or asset classes can also form effective pairs, such as TLT (20+ Year Treasury Bond ETF) and IEI (3-7 Year Treasury Bond ETF) [9].

### 5.3. Strategy Summary for PAIRY

For the PAIRY platform, a robust pair trading system should incorporate the following elements:

1.  **Dynamic Pair Selection:** Implement a systematic process to scan a universe of assets (e.g., S&P 500 components) and identify potential pairs based on sector, market capitalization, and liquidity filters.
2.  **Statistical Validation:** Utilize both Engle-Granger and Johansen cointegration tests to rigorously assess the long-term relationship between potential pairs. The ADF test should be applied to the spread to confirm stationarity.
3.  **Dynamic Hedge Ratio:** Employ a Kalman Filter to continuously estimate and adjust the hedge ratio between the assets. This will allow the system to adapt to evolving market conditions and maintain a more stationary spread.
4.  **Mean Reversion Analysis:** Model the spread using an Ornstein-Uhlenbeck process to quantify its mean reversion speed (half-life). This metric can serve as a critical filter for selecting tradable pairs and optimizing trade duration.
5.  **Z-score Based Entry/Exit:** Generate trading signals based on the Z-score of the dynamically adjusted spread. Establish clear thresholds for entering long/short spread positions and for exiting trades as the spread reverts to its mean.
6.  **Risk Management:** Incorporate stop-loss mechanisms based on extreme Z-score deviations or maximum holding periods to limit potential losses when a pair's relationship breaks down.
7.  **Portfolio Diversification:** Design PAIRY to manage multiple pair trades simultaneously, diversifying across different sectors and pair types to reduce overall portfolio risk and enhance stability.

## 6. References

[1] PairTrade Finder®. (n.d.). *Leading Statistical Arbitrage Software for Online Traders*. Retrieved from [https://pairtradefinder.com/](https://pairtradefinder.com/)

[2] PairTrade Finder®. (2026, May 11). *Market-Neutral Pair Trading in Action: May 2026 Top 50 USA Stock Pair Stars*. Retrieved from [https://pairtradefinder.com/blog/blog-market-neutral-pair-trading-may-2026-top-50/](https://pairtradefinder.com/blog/blog-market-neutral-pair-trading-may-2026-top-50/)

[3] Quantified Strategies. (2024, September 17). *Pairs Trading Strategy With Logic And Rules*. Retrieved from [https://www.quantifiedstrategies.com/pairs-trading-strategy/](https://www.quantifiedstrategies.com/pairs-trading-strategy/)

[4] Pair Trading Lab. (n.d.). *Ultimate Pair Trading Tools*. Retrieved from [https://www.pairtradinglab.com/](https://www.pairtradinglab.com/)

[5] quantverse. (n.d.). *quantverse/ptltrader: Trade your pair trading strategy portfolios automatically.* GitHub. Retrieved from [https://github.com/quantverse/ptltrader](https://github.com/quantverse/ptltrader)

[6] QuantConnect. (n.d.). *Research/Analysis/05 Pairs Trading Strategy Based on Cointegration.ipynb*. GitHub. Retrieved from [https://github.com/QuantConnect/Research/blob/master/Analysis/05%20Pairs%20Trading%20Strategy%20Based%20on%20Cointegration.ipynb](https://github.com/QuantConnect/Research/blob/master/Analysis/05%20Pairs%20Trading%20Strategy%20Based%20on%20Cointegration.ipynb)

[7] Letian, Z. (2018, March 24). *Cointegration and Pairs Trading*. Retrieved from [https://letianzj.github.io/cointegration-pairs-trading.html](https://letianzj.github.io/cointegration-pairs-trading.html)

[8] QuantStart. (n.d.). *Ornstein-Uhlenbeck Simulation with Python*. Retrieved from [https://www.quantstart.com/articles/ornstein-uhlenbeck-simulation-with-python/](https://www.quantstart.com/articles/ornstein-uhlenbeck-simulation-with-python/)

[9] QuantStart. (n.d.). *Kalman Filter-Based Pairs Trading Strategy In QSTrader*. Retrieved from [https://www.quantstart.com/articles/kalman-filter-based-pairs-trading-strategy-in-qstrader/](https://www.quantstart.com/articles/kalman-filter-based-pairs-trading-strategy-in-qstrader/)
