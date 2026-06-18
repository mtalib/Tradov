# ArbitrageLab: Comprehensive Pairs Trading & Statistical Arbitrage Strategy Reference

**Source:** [Hudson & Thames ArbitrageLab Documentation](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/index.html)
**Compiled by:** Manus AI
**Coverage:** All successfully extracted strategy modules with full mathematical derivations

---

## Table of Contents

### Cointegration
1. [Half-life of Mean-Reversion](#half-life-of-mean-reversion)
### Machine Learning, Pairs Trading, Cointegration
2. [ML Based Pairs Selection](#ml-based-pairs-selection)
### Cointegration
3. [Minimum Profit Optimization](#minimum-profit-optimization)
### Cointegration, Pairs Trading
4. [Minimum Profit Strategy](#minimum-profit-strategy)
### Cointegration
5. [Multivariate Cointegration Framework](#multivariate-cointegration-framework)
6. [Multivariate Cointegration Strategy](#multivariate-cointegration-strategy)
### Stochastic Control, Cointegration
7. [Optimal Convergence](#optimal-convergence)
### Cointegration
8. [Sparse Mean-reverting Portfolio Selection](#sparse-mean-reverting-portfolio-selection)
9. [Tests for Cointegration](#tests-for-cointegration)
### Copula
10. [A Deeper Intro to Copulas](#a-deeper-intro-to-copulas)
11. [A Practical Introduction to Copula](#a-practical-introduction-to-copula)
### Copula, Pairs Trading
12. [Basic Copula Trading Strategy](#basic-copula-trading-strategy)
### Copula
13. [C-vine Copula Strategy](#c-vine-copula-strategy)
14. [Copula-Based Metrics](#copula-based-metrics)
### Copula, Pairs Trading
15. [Mispricing Index Copula Trading Strategy](#mispricing-index-copula-trading-strategy)
### Codependence Measures, Copulas, Optimal Transport
16. [Optimal Copula Transport Dependence](#optimal-copula-transport-dependence)
### Copula
17. [Vine Copula Partner Selection](#vine-copula-partner-selection)
### Stochastic Control Approach, Mean Reversion, Arbitrage
18. [OU Model Jurek](#ou-model-jurek)
### OU Model, Stochastic Control, Pairs Trading
19. [OU Model Mudchanatongsuk (Optimal Pairs Trading: A Stochastic Control Approach)](#ou-model-mudchanatongsuk-optimal-pairs-trading-a-stochastic-control-approach)
### Optimal Mean Reversion
20. [Cox-Ingersoll-Ross (CIR) Model](#cox-ingersoll-ross-cir-model)
### Pairs Trading, Time Series Analysis
21. [H-Strategy](#h-strategy)
### Time Series Analysis, Pairs Trading
22. [Quantile Time Series Strategy](#quantile-time-series-strategy)
### Codependence
23. [Information Theory Metrics](#information-theory-metrics)
### OU Model
24. [A closed-form solution for optimal mean-reverting trading strategies](#a-closed-form-solution-for-optimal-mean-reverting-trading-strategies)
### Mean Reversion
25. [Bollinger Bands Strategy](#bollinger-bands-strategy)
### Statistical Arbitrage, Distance
26. [Distance Approach Pairs Trading Strategy](#distance-approach-pairs-trading-strategy)
### Pairs Trading, Mean Reversion
27. [Kalman Filter Strategy](#kalman-filter-strategy)
### OU Model
28. [OU Model Optimal Trading Thresholds Bertram](#ou-model-optimal-trading-thresholds-bertram)
### OU Model, Pairs Trading
29. [OU Model Optimal Trading Thresholds Zeng](#ou-model-optimal-trading-thresholds-zeng)
### Statistical Arbitrage
30. [PCA Approach](#pca-approach)
### Distance
31. [Pearson Approach](#pearson-approach)
### Regime Switching, Statistical Arbitrage
32. [Regime-Switching Arbitrage Rule](#regime-switching-arbitrage-rule)
### OU Model
33. [Trading Under the Ornstein-Uhlenbeck Model](#trading-under-the-ornstein-uhlenbeck-model)

---

# Cointegration

## 1. Half-life of Mean-Reversion

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/half_life.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/half_life.html)

The module calculates the half-life of a mean-reversion process, assuming the data follows an Ornstein-Uhlenbeck (OU) process. The Ornstein-Uhlenbeck process is described by the stochastic differential equation:

$$dy(t) = ( \lambda y(t-1) + \mu ) dt + d \varepsilon$$

Where:
*   $y(t)$ represents the value of the process at time $t$.
*   $\lambda$ is the rate of mean reversion.
*   $\mu$ is the long-term mean of the process.
*   $dt$ is an infinitesimal time increment.
*   $d \varepsilon$ represents Gaussian noise, typically modeled as $ \sigma dW(t)$, where $ \sigma$ is the volatility and $dW(t)$ is a Wiener process (standard Brownian motion).

The function `get_half_life_of_mean_reversion` from `arbitragelab.cointegration_approach.utils` is used to compute this half-life.

### Key Formulas Summary

1.  **Ornstein-Uhlenbeck Process:**
    $$dy(t) = ( \lambda y(t-1) + \mu ) dt + d \varepsilon$$
    Where:
    *   $y(t)$: Value of the process at time $t$.
    *   $\lambda$: Rate of mean reversion.
    *   $\mu$: Long-term mean of the process.
    *   $d \varepsilon$: Gaussian noise.

---

# Machine Learning, Pairs Trading, Cointegration

## 2. ML Based Pairs Selection

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/ml_approach/ml_based_pairs_selection.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/ml_approach/ml_based_pairs_selection.html)

The document describes an **ML Based Pairs Selection** strategy, which leverages Unsupervised Learning to identify suitable pairs for trading. The core idea is to group relevant securities into clusters and detect rewarding pairs within these clusters.

### Dimensionality Reduction

This step aims to extract common underlying risk factors from securities returns and produce a compact representation for each security, stored in a 'feature_vector'. The number of features, denoted as $k$, needs to be defined. A common approach involves analyzing the proportion of total variance explained by each principal component (PCA). However, due to the 'curse of dimensionality' as described by Bellman (1966), which causes an exponential increase in volume with added dimensions, the number of PCA dimensions is empirically upper-bounded at 15. This is to ensure the final representation remains dense enough for effective clustering, as high dimensionality can make clustering ineffective (Berkhin, 2006).

### Unsupervised Learning

The objective here is to identify the optimal cluster structure from the compact representations. The framework prioritizes methods that do not require specifying the number of clusters in advance, do not necessitate grouping all securities, and make no assumptions about cluster shapes.

Two primary clustering algorithms are mentioned:

1.  **OPTICS Clustering Algorithm:** This method allows for the built-in automatic procedure to select the most suitable $\epsilon$ (epsilon) for each cluster.
2.  **DBSCAN Clustering Algorithm:** This is used when domain-specific knowledge can enhance results, given the algorithm's parameter sensitivity. A possible approach to finding $\epsilon$ is to inspect the knee plot and fix a suitable $\epsilon$ by observing the global curve turning point (Rahmah N, Sitanggang S, 2016).

### Select Spreads

After clustering, the generated pairs are processed through a set of rules to select suitable spreads. These rules are:

1.  **Cointegration:** The pair's constituents must be cointegrated. The Engle-Granger test is proposed for its simplicity. To mitigate its sensitivity to variable ordering (Armstrong, 2001), the test is run for both possible selections of the dependent variable, and the combination yielding the lowest t-statistic is selected. A more robust solution, based on Gregory et al. (2011), involves using **orthogonal regression** (Total Least Squares - TLS). TLS accounts for residuals of both dependent and independent variables, incorporating the volatility of both legs of the spread, ensuring consistent hedge ratios and cointegration estimates unaffected by variable ordering.

    Optimal hedge ratios can also be obtained by minimizing the spread's half-life of mean-reversion. Other hedge ratio calculation methods include OLS, Johansen Test Eigenvector, Box-Tiao Canonical Decomposition, Minimum Half-Life, and Minimum ADF Test T-statistic Value.

2.  **Mean-Reversion Character (Hurst Exponent):** The Hurst exponent associated with the spread of a given pair must be **smaller than 0.5**, indicating a mean-reverting process.

3.  **Spread Movement (Half-Life):** The pair's spread movement is constrained by its half-life of mean-reversion. Spreads with very short ( $< 1$ day) or very long ( $> 365$ days) mean-reversion periods are considered unsuitable for medium-term price movements.

4.  **Liquidity (Mean Crossings):** Every spread must cross its mean at least **once per month** to ensure sufficient liquidity and trading opportunities.

### Implementation Details (Code Snippets)

The document provides Python code demonstrating the usage of `OPTICSDBSCANPairsClustering` and `CointegrationSpreadSelector` classes from the `arbitragelab` library.

```python
import pandas as pd
import numpy as np
from arbitragelab.ml_approach import OPTICSDBSCANPairsClustering
from arbitragelab.spread_selection import CointegrationSpreadSelector

# Getting the dataframe with time series of asset returns
data = pd.read_csv('X_FILE_PATH.csv', index_col=0, parse_dates = [0])

pairs_clusterer = OPTICSDBSCANPairsClustering(data)

# Price data is reduced to its component features using PCA
pairs_clusterer.dimensionality_reduction_by_components(5)

# Clustering is performed over feature vector
clustered_pairs = pairs_clusterer.cluster_using_optics(min_samples=3)

# Removing duplicates
clustered_pairs = list(set(clustered_pairs))

# Generated Pairs are processed through the rules mentioned above
spreads_selector = CointegrationSpreadSelector(prices_df=data,
                                               baskets_to_filter=clustered_pairs)
filtered_spreads = spreads_selector.select_spreads()

# Checking the resulting spreads
print(filtered_spreads)

# Generate a plot of the selected spread
spreads_selector.spreads_dict['AAL_FTI'].plot(figsize=(12,6))

# Generate detailed spread statistics
spreads_selector.selection_logs.loc[['AAL_FTI']].T
```

This code demonstrates the workflow: dimensionality reduction using PCA (with 5 components in the example), clustering using OPTICS, and then filtering spreads based on the defined cointegration and mean-reversion rules.

### Key Formulas Summary

1.  **Hurst Exponent Condition:** $H < 0.5$
    *   $H$: Hurst Exponent, a measure of the long-term memory of a time series. A value less than 0.5 indicates mean-reverting behavior.

2.  **Half-Life of Mean-Reversion Constraint:** $1 \text{ day} < T_{1/2} < 365 \text{ days}$
    *   $T_{1/2}$: Half-life of mean-reversion, representing the time it takes for a deviation from the mean to halve.

3.  **Mean Crossings Frequency:** At least one mean crossing per month.

4.  **PCA Dimensions Upper Bound:** $k \le 15$
    *   $k$: Number of PCA dimensions, chosen empirically to balance variance explained and density for clustering.

### References

Sarmento, S.M. and Horta, N., A Machine Learning based Pairs Trading Investment Strategy.
Avellaneda, M. and Lee, J.H., 2010. Statistical arbitrage in the US equities market. Quantitative Finance, 10(7), pp.761-782.
Bellman, R., 1966. Dynamic programming. Science, 153(3731), pp.34-37.
Berkhin, P., 2006. A survey of clustering data mining techniques. In Grouping multidimensional data (pp. 25-71). Springer, Berlin, Heidelberg.
Rahmah, N. and Sitanggang, I.S., 2016, January. Determination of optimal epsilon (eps) value on dbscan algorithm to clustering data on peatland hotspots in sumatra. In IOP Conference Series: Earth and Environmental Science (Vol. 31, No. 1, p. 012012). IOP Publishing.
Armstrong, J.S. ed., 2001. Principles of forecasting: a handbook for researchers and practitioners (Vol. 30). Springer Science & Business Media.
Hoel, C.H., 2013. Statistical arbitrage pairs: can cointegration capture market neutral profits? (Master’s thesis).
Gregory, I., Ewald, C.O. and Knox, P., 2010, November. Analytical pairs trading under different assumptions on the spread and ratio dynamics. In 23rd Australasian Finance and Banking Conference.

---

# Cointegration

## 3. Minimum Profit Optimization

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/minimum_profit.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/minimum_profit.html)

## Introduction

A common pairs trading strategy is to “fade the spread”, i.e. to open a trade when the spread is sufficiently far away from its equilibrium in anticipation of the spread reverting to the mean. Within the context of cointegration, the spread refers to cointegration error, and in the remainder of this documentation “spread” and “cointegration error” will be used interchangeably.

In this strategy, the following assumptions are made:

*   The price of two assets ($S_1$ and $S_2$) are cointegrated over the relevant time period, which includes both in-sample and out-of-sample (trading) period.
*   The cointegration error follows a stationary AR(1) process.
*   The cointegration error is symmetrically distributed so that the optimal boundary could be applied on both sides of the mean.
*   Short sales are permitted or possible through a broker and there is no interest charged for the short sales and no cost for trading.
*   The cointegration coefficient $\beta > 0$, where a cointegration relationship is defined as:

    $$P_{S_1,t} - \beta P_{S_2,t} = \varepsilon_t$$

    *   $P_{S_1,t}$: Price of asset $S_1$ at time $t$
    *   $P_{S_2,t}$: Price of asset $S_2$ at time $t$
    *   $\beta$: Cointegration coefficient
    *   $\varepsilon_t$: Cointegration error (spread)

## Minimum Profit per Trade

Denote a trade opened when the cointegration error $\varepsilon_t$ overshoots the pre-set upper boundary $U$ as a **U-trade**, and similarly a trade opened when $\varepsilon_t$ falls through the pre-set lower boundary $L$ as an **L-trade**. Without loss of generality, it can be assumed that the mean of $\varepsilon_t$ equals 0. Then the minimum profit per U-trade can be derived from the following trade setup.

*   **U-trade entry signal**: When $\varepsilon_t \geq U$ at $t_o$, open a trade by selling $N$ of asset $S_1$ and buying $\beta N$ of asset $S_2$.
*   **U-trade exit signal**: When $\varepsilon_t \leq 0$ at $t_c$, close the trade.

The profit per trade would thus be:

$$P = N (P_{S_1, t_o} - P_{S_1, t_c}) + \beta N (P_{S_2, t_c} - P_{S_2, t_o})$$

*   $N$: Number of units of asset $S_1$ (and $\beta N$ of asset $S_2$)
*   $P_{S_1, t_o}$: Price of asset $S_1$ at trade opening time $t_o$
*   $P_{S_1, t_c}$: Price of asset $S_1$ at trade closing time $t_c$
*   $P_{S_2, t_o}$: Price of asset $S_2$ at trade opening time $t_o$
*   $P_{S_2, t_c}$: Price of asset $S_2$ at trade closing time $t_c$
*   $\beta$: Cointegration coefficient

Since the two assets are cointegrated during the trade period, the cointegration relationship can be substituted into the above equation and derive the following:

$$\begin{align*} P & = N (P_{S_1, t_o} - P_{S_1, t_c}) + \beta N (P_{S_2, t_c} - P_{S_2, t_o}) \\ & = N (\beta P_{S_2, t_c} - P_{S_1, t_c}) + N (P_{S_1, t_o} - \beta P_{S_2, t_o}) \\ & = -N \varepsilon_{t_c} + N \varepsilon_{t_o} \\ & \geq N U \end{align*}$$

Thus, by trading the asset pair with the weight as a proportion of the cointegration coefficient, the profit per U-trade is at least $U$ dollars when trading one unit of the pair. Should the required minimum profit be higher, then the strategy can trade multiple units of the pair weighted by the cointegration coefficient.

According to the assumptions in the Introduction section, the lower boundary will be set at $-U$ due to the symmetric distribution of the cointegration error. The profit of an L-trade can thus be derived from the following trade setup.

*   **L-trade entry signal**: When $\varepsilon_t \leq -U$ at $t_o$, open a trade by buying $N$ of asset $S_1$ and selling $\beta N$ of asset $S_2$.
*   **L-trade exit signal**: When $\varepsilon_t \geq 0$ at $t_c$, close the trade.

Using the same derivation above, it can be shown that the profit per L-trade is also at least $U$ dollars per unit. Therefore, the boundary is exactly the minimum profit per trade, where the strategy only trade one unit of the cointegrated pair weighted by the cointegration coefficient.

## Mean First-passage Time of an AR(1) Process

Consider a stationary AR(1) process:

$$Y_t = \phi Y_{t-1} + \xi_t$$

where $-1 < \phi < 1$, and $\xi_t \sim N(0, \sigma_{\xi}^2) \quad \mathrm{i.i.d}$. The mean first-passage time over interval $[a, b]$ of $Y_t$, starting at initial state $y_0 \in [a, b]$, which is denoted by $E(\mathcal{T}_{a,b}(y_0))$, is given by

$$E(\mathcal{T}_{a,b}(y_0)) = \frac{1}{\sqrt{2 \pi}\sigma_{\xi}}\int_a^b E(\mathcal{T}_{a,b}(u)) \> \mathrm{exp} \Big( - \frac{(u-\phi y_0)^2}{2 \sigma_{\xi}^2} \Big) du + 1$$

*   $Y_t$: Value of the AR(1) process at time $t$
*   $\phi$: AR(1) coefficient
*   $\xi_t$: White noise error term
*   $\sigma_{\xi}^2$: Variance of the error term
*   $a, b$: Interval boundaries
*   $y_0$: Initial state
*   $E(\mathcal{T}_{a,b}(y_0))$: Mean first-passage time from $y_0$ to outside $[a,b]$

This integral equation can be solved numerically using the Nyström method, i.e. by solving the following linear equations:

$$\begin{split}\begin{pmatrix} 1 - K(u_0, u_0) & -K(u_0, u_1) & \ldots & -K(u_0, u_n) \\ -K(u_1, u_0) & 1 - K(u_1, u_1) & \ldots & -K(u_1, u_n) \\ \vdots & \vdots & \vdots & \vdots \\ -K(u_n, u_0) & -K(u_n, u_1) & \ldots & 1-K(u_n, u_n) \end{pmatrix} \begin{pmatrix} E_n(\mathcal{T}_{a,b}(u_0)) \\ E_n(\mathcal{T}_{a,b}(u_1)) \\ \vdots \\ E_n(\mathcal{T}_{a,b}(u_n)) \\ \end{pmatrix} = \begin{pmatrix} 1 \\ 1 \\ \vdots \\ 1 \\ \end{pmatrix}\end{split}$$

where $E_n(\mathcal{T}_{a,b}(u_0))$ is a discretized estimate of the integral, and the Gaussian kernel function $K(u_i, u_j)$ is defined as:

$$K(u_i, u_j) = \frac{h}{2 \sqrt{2 \pi} \sigma_{\xi}} w_j \> \mathrm{exp} \Big( - \frac{(u_j - \phi u_i)^2}{2 \sigma_{\xi}^2} \Big)$$

*   $E_n(\mathcal{T}_{a,b}(u_0))$: Discretized estimate of the mean first-passage time
*   $K(u_i, u_j)$: Gaussian kernel function
*   $h$: Step size for discretization
*   $w_j$: Weight for trapezoid integration rule

and the weight $w_j$ is defined by the trapezoid integration rule:

$$\begin{split}w_j = \begin{cases} 1 & j = 0 \quad \mathrm{and} \quad j = n \\ 2 & 0 < j < n, j \in \mathbb{N} \end{cases}\end{split}$$

The time complexity for solving the above linear equation system is $O(n^3)$.

## Minimum Total Profit (MTP)

The MTP of U-trades within a specific trading horizon $[0, T]$ is defined by:

$$MTP(U) = \Big( \frac{T}{TD_U + I_U} - 1 \Big) U$$

where $TD_U$ is the trade duration and $I_U$ is the inter-trade interval.

*   $MTP(U)$: Minimum total profit for a given boundary $U$
*   $T$: Trading horizon
*   $TD_U$: Trade duration for boundary $U$
*   $I_U$: Inter-trade interval for boundary $U$
*   $U$: Pre-set upper boundary

From the definition, the MTP is simultaneously determined by $TD_U$ and $I_U$, both of which can be derived from the mean first-passage time. Also, it is already known that $U$ is the minimum profit per U-trade, so $\frac{T}{TD_U + I_U} - 1$ can be used to estimate the number of U-trades. Following the assumption that the de-meaned cointegration error follows an AR(1) process:

$$\varepsilon_t = \phi \varepsilon_{t-1} + a_t \qquad a_t \sim N(0, \sigma_a^2) \> \mathrm{i.i.d}$$

*   $\varepsilon_t$: Cointegration error at time $t$
*   $\phi$: AR(1) coefficient
*   $a_t$: White noise error term, $a_t \sim N(0, \sigma_a^2)$ i.i.d.
*   $\sigma_a^2$: Variance of the error term

Since the core idea of the approach is to “fade the spread” at $U$, the trade duration can be defined as the average time of the cointegration error to pass 0 for the first time given that its initial value is $U$. Thus using the definition of the mean first-passage time of the cointegration error process:

$$TD_U = E(\mathcal{T}_{0, \infty}(U)) = \lim_{b \to \infty} \frac{1}{\sqrt{2 \pi} \sigma_a} \int_0^b E(\mathcal{T}_{0, b}(s)) \> \mathrm{exp} \Big( - \frac{(s- \phi U)^2}{2 \sigma_a^2} \Big) ds + 1$$

*   $TD_U$: Trade duration
*   $E(\mathcal{T}_{0, \infty}(U))$: Mean first-passage time from $U$ to 0
*   $\sigma_a$: Standard deviation of the fitted residual
*   $\phi$: AR(1) coefficient
*   $U$: Initial value of cointegration error

The inter-trade interval is defined as the average time of the de-meaned cointegration error to pass $U$ the first time given its initial value is 0.

$$I_U = E(\mathcal{T}_{- \infty, U}(0)) = \lim_{-b \to - \infty} \frac{1}{\sqrt{2 \pi} \sigma_a} \int_{-b}^U E(\mathcal{T}_{-b, U}(s)) \> \mathrm{exp} \Big( - \frac{s^2}{2 \sigma_a^2} \Big) ds + 1$$

*   $I_U$: Inter-trade interval
*   $E(\mathcal{T}_{- \infty, U}(0))$: Mean first-passage time from 0 to $U$
*   $\sigma_a$: Standard deviation of the fitted residual

Under the assumption that the cointegration error follows a stationary AR(1) process, the standard deviation of the fitted residual $\sigma_a$ and the standard deviation of the cointegration error $\sigma_{\varepsilon}$ has the following relationship:

$$\sigma_a = \sqrt{1 - \phi^2} \sigma_{\varepsilon}$$

*   $\sigma_a$: Standard deviation of the fitted residual
*   $\phi$: AR(1) coefficient
*   $\sigma_{\varepsilon}$: Standard deviation of the cointegration error

The following stylized fact helped approximate the infinity limit for both integrals: for a stationary AR(1) process $\{ \varepsilon_t \}$, the probability that the absolute value of the process $| \varepsilon_t |$ is greater than 5 times the standard deviation of the process $5 \sigma_{\varepsilon}$ is close to 0. Therefore, $5 \sigma_{\varepsilon}$ will be used as an approximation of the infinity limit in the integrals.

## Optimize the Pre-Set Boundaries that Maximizes MTP

Based on the above definitions, the numerical algorithm to optimize the pre-set boundaries that maximize MTP could be given as follows.

1.  Perform **Engle-Granger or Johansen test** to derive the cointegration coefficient $\beta$.
2.  Fit the cointegration error $\varepsilon_t$ to an AR(1) process and retrieve the AR(1) coefficient ($\phi$) and the fitted residual (with standard deviation $\sigma_a$).
3.  Calculate the standard deviation of cointegration error ($\sigma_{\varepsilon}$) and the fitted residual ($\sigma_a$).
4.  Generate a sequence of pre-set upper bounds $U_i$, where $U_i = i \times 0.01, \> i = 0, \ldots, b/0.01$, and $b = 5 \sigma_{\varepsilon}$.
5.  For each $U_i$,
    1.  Calculate $TD_{U_i}$.
    2.  Calculate $I_{U_i}$.
    3.  Calculate $MTP(U_i)$.
6.  Find $U^{\*}$ such that $MTP(U^{\*})$ is the maximum.
7.  Set a desired minimum profit $K \geq U^{\*}$ and calculate the number of assets to trade according to the following equations:

    $$\begin{align}\begin{aligned}N_{S_2} = \Big \lceil \frac{K \beta}{U^{\*}} \Big \rceil\\N_{S_1} = \Big \lceil \frac{N_{S_2}}{\beta} \Big \rceil\end{aligned}\end{align}$$

    *   $N_{S_2}$: Number of units of asset $S_2$
    *   $N_{S_1}$: Number of units of asset $S_1$
    *   $K$: Desired minimum profit
    *   $\beta$: Cointegration coefficient
    *   $U^{\*}$: Optimal pre-set boundary that maximizes MTP

### Key Formulas Summary

1. Cointegration relationship: $P_{S_1,t} - \beta P_{S_2,t} = \varepsilon_t$
   - $P_{S_1,t}$: Price of asset $S_1$ at time $t$
   - $P_{S_2,t}$: Price of asset $S_2$ at time $t$
   - $\beta$: Cointegration coefficient
   - $\varepsilon_t$: Cointegration error (spread)
2. Profit per trade (derived): $P \geq N U$
   - $P$: Profit per trade
   - $N$: Number of units traded
   - $U$: Pre-set upper boundary (minimum profit per unit)
3. Stationary AR(1) process: $Y_t = \phi Y_{t-1} + \xi_t$
   - $Y_t$: Value of the AR(1) process at time $t$
   - $\phi$: AR(1) coefficient, where $-1 < \phi < 1$
   - $\xi_t$: White noise error term, $\xi_t \sim N(0, \sigma_{\xi}^2)$ i.i.d.
   - $\sigma_{\xi}^2$: Variance of the error term
4. Minimum Total Profit (MTP): $MTP(U) = \Big( \frac{T}{TD_U + I_U} - 1 \Big) U$
   - $MTP(U)$: Minimum total profit for a given boundary $U$
   - $T$: Trading horizon
   - $TD_U$: Trade duration for boundary $U$
   - $I_U$: Inter-trade interval for boundary $U$
   - $U$: Pre-set upper boundary
5. Relationship between standard deviations: $\sigma_a = \sqrt{1 - \phi^2} \sigma_{\varepsilon}$
   - $\sigma_a$: Standard deviation of the fitted residual of the AR(1) process for cointegration error
   - $\phi$: AR(1) coefficient
   - $\sigma_{\varepsilon}$: Standard deviation of the cointegration error

### References

Lin, Y.-X., McCrae, M., and Gulati, C. (2006) - Loss protection in pairs trading through minimum profit bounds: a cointegration approach
Puspaningrum, H., Lin, Y.-X., and Gulati, C. M. (2010) - Finding the optimal pre-set boundaries for pairs trading strategy based on cointegration technique

---

# Cointegration, Pairs Trading

## 4. Minimum Profit Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/minimum_profit.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/minimum_profit.html)

\
# Minimum Profit Strategy

## Introduction

This trading strategy takes new spread values one by one and allows checking if the conditions to open a position are fulfilled with each new timestamp and value provided. This allows for easier integration of these strategies into an existing data pipeline. Also, the strategy object keeps track of open and closed trades and the supporting information related to them.

## Minimum Profit Strategy

The Minimum Profit class from the [Cointegration Approach](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration%5Fapproach/minimum%5Fprofit.html) generates optimal entry and exit levels (`buy_level`, `close_level`, `sell_level`) as well as number of shares (`shares_A`, `shares_B`) to trade per asset in a cointegrated pair. The strategy described in this section of the documentation can be used to trade those generated signals.

The signal generation process relies on the performance of the spread, which is calculated as:

$$Spread = PriceA + \beta \cdot PriceB$$

Where the $\beta$ parameter is given by the Minimum Profit class. If the spread value drops below the `buy_level`, a buy trade should be opened, meaning we should go `shares_A` long and `shares_B` short. If the spread value rises above the `sell_level`, a sell trade should be opened, so we short `shares_B` and go long `shares_A`. Upon reaching the `close_level`, a buy or a sell trade should be closed. This strategy assumes only one open trade at a time.

### Entry/Exit Signal Rules:

*   **Buy Signal**: If $Spread < buy\_level$, open a buy trade. This involves going long `shares_A` of asset A and short `shares_B` of asset B.
*   **Sell Signal**: If $Spread > sell\_level$, open a sell trade. This involves going short `shares_B` of asset B and long `shares_A` of asset A.
*   **Close Trade Signal**: If $Spread$ reaches $close\_level$, close the currently open trade (either buy or sell).

### Implementation Details from Code Example:

The provided Python code snippet illustrates the implementation of the strategy:

```python
# Importing packages
import pandas as pd
import numpy as np

# Importing ArbitrageLab tools
from arbitragelab.cointegration_approach.minimum_profit import MinimumProfit
from arbitragelab.trading import MinimumProfitTradingRule

# Using MinimumProfit as optimizer ...

# Generate optimal trading levels and number of shares to trade
num_of_shares, optimal_levels = optimizer.get_optimal_levels(optimal_ub,\
                                                             minimum_profit,\
                                                             beta_eg,\
                                                             epsilon_t_eg)

# Calculating spread
spread = optimizer.construct_spread(data, beta_eg)

# Creating a strategy
strategy = MinimumProfitTradingRule(num_of_shares, optimal_levels)

# Adding initial spread value
strategy.update_spread_value(spread[0])

# Feeding spread values to the strategy one by one
for time, value in spread.iteritems():
    strategy.update_spread_value(value)

    # Checking if logic for opening a trade is triggered
    trade, side = strategy.check_entry_signal()

    # Adding a trade if we decide to trade signal
    if trade:
        strategy.add_trade(start_timestamp=time, side_prediction=side)

    # Update trades, close if logic is triggered
    close = strategy.update_trades(update_timestamp=time)

# Checking currently open trades
open_trades = strategy.open_trades

# Checking all closed trades
closed_trades = strategy.closed_trades
```

This code demonstrates how `MinimumProfit` is used to generate `num_of_shares` and `optimal_levels` (which include `buy_level`, `sell_level`, `close_level`). The `construct_spread` method calculates the spread using `data` and `beta_eg`. The `MinimumProfitTradingRule` then uses these to manage trades by updating spread values, checking entry signals, adding trades, and updating/closing trades.

### Key Formulas Summary

1.  **Spread Calculation**:
    $$Spread = PriceA + \beta \cdot PriceB$$
    Where:
    *   $PriceA$: Price of asset A
    *   $PriceB$: Price of asset B
    *   $\beta$: Beta parameter, determined by the Minimum Profit class from the cointegration approach.

2.  **Buy Entry Condition**:
    $Spread < buy\_level$

3.  **Sell Entry Condition**:
    $Spread > sell\_level$

4.  **Trade Close Condition**:
    $Spread = close\_level$

### References

Lin, Y.-X., McCrae, M., and Gulati, C., 2006. Loss protection in pairs trading through minimum profit bounds: a cointegration approach
Puspaningrum, H., Lin, Y.-X., and Gulati, C. M. 2010. Finding the optimal pre-set boundaries for pairs trading strategy based on cointegration technique

---

# Cointegration

## 5. Multivariate Cointegration Framework

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/multivariate_cointegration.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/multivariate_cointegration.html)

The Multivariate Cointegration Framework extends the Minimum Profit Optimization framework to three or more cointegrated assets, forming the basis of a pairs trading strategy. The core idea is to capitalize on the mean-reverting nature of cointegrated time series, where assets might drift apart temporarily but are expected to re-converge.

**1. Log-returns:**
Let $P_i$ denote the price of $N$ assets, where $i = 1, 2, \ldots, N$. The continuously compounded asset returns (log-returns) at time $t > 0$ are defined as:

$r_t^i = \ln{P_t^i} - \ln{P_{t-1}^i}$

**2. Linear Combination of Asset Prices:**
A process $Y_t$ is constructed as a linear combination of the $N$ asset prices:

$Y_t = \sum_{i=1}^N b^i \ln{P_t^i}$

Here, $b^i$ represents the $i$-th element of a finite vector $\mathbf{b}$.

**3. Asset Returns Series:**
The corresponding asset returns series $Z_t$ is defined as the difference in $Y_t$ over time:

$Z_t = Y_t - Y_{t-1} = \sum_{i=1}^N b^i r_t^i$

**4. Autocovariance of $Y_t$ (Memory Assumption):**
For the process $Y_t$ to be stationary, its memory should not extend into the infinite past, which is expressed by the following condition on its autocovariance:

$\lim_{p \to \infty} \text{Cov} [ Y_t, Y_{t-p} ] = 0$

**5. Conditions for Stationarity of $Y_t$ (Log-Price Process) based on $Z_t$ (Log-Returns Process):**
The log-price process $Y_t$ is stationary if and only if the following three conditions on the log-returns process $Z_t$ are satisfied:

$E[Z_t] = 0$
$\text{Var }Z_t = -2 \sum_{p=1}^{\infty} \text{Cov} [ Z_t, Z_{t-p} ]$
$\sum_{p=1}^{\infty} p \text{ Cov} [ Z_t, Z_{t-p} ] < \infty$

When these conditions hold, the log-price series of the assets are considered cointegrated. For empirical applications in equity markets, the log-returns time series are often assumed stationary, allowing the Johansen test to be directly applied to the log-price series to derive the cointegration vector $\mathbf{b}$.

**6. Trading Strategy (Notional Value of Asset $i$ to Trade):**
The strategy involves betting on the spread formed by cointegrated assets that have diverged but are expected to mean revert. For each time period, the notional value of asset $i$ to trade is:

$-b^i C \sum_{p=1}^{\infty} Z_{t-p}$

where $C$ is a positive scale factor.

**7. Profit of the Strategy:**
The profit $\pi_t$ of this strategy can be calculated as:

$\pi_t = \sum_{i=1}^N -b^i C \bigg[ \sum_{p=1}^{\infty} Z_{t-p} \bigg] r_t^i = -C \sum_{p=1}^{\infty} Z_{t-p} Z_t$

**8. Expectation of the Profit:**
The expectation of the profit $E[\pi_t]$ is derived as follows:

$E[\pi_t] = E \bigg[ -C \sum_{p=1}^{\infty} Z_{t-p} Z_t \bigg]$
$= -C \sum_{p=1}^{\infty} (Z_{t-p} - E[Z_t])(Z_t - E[Z_t])$ (assuming $E[Z_t]=0$)
$= -C \sum_{p=1}^{\infty} \text{Cov} [Z_t, Z_{t-p}]$
$= 0.5 : C \text{ Var} Z_t > 0$

This derivation utilizes the conditions $E[Z_t] = 0$ and $\text{Var }Z_t = -2 \sum_{p=1}^{\infty} \text{Cov} [ Z_t, Z_{t-p} ]$. Since $C$ and $\text{Var } Z_t$ are positive, the expected profit of this strategy is positive. However, this portfolio is not dollar-neutral.

**9. Partitioning Assets for Dollar-Neutral Portfolio:**
To construct a dollar-neutral portfolio, assets are partitioned into two disjoint sets, $L$ and $S$, based on the sign of their cointegration coefficient $b^i$:

$i \in L \iff b^i \geq 0$
$i \in S \iff b^i < 0$

*   $L$: set of assets with non-negative cointegration coefficients.
*   $S$: set of assets with negative cointegration coefficients.

**10. Notional of Each Asset for Dollar-Neutral Portfolio:**
The notional of each asset to be traded in a dollar-neutral portfolio is calculated as:

$\frac{-b^i C \text{ sgn} \bigg( \sum_{p=1}^{\infty} Z_{t-p} \bigg)}{\sum_{j \in L} b^j}$, for $i \in L$

$\frac{b^i C \text{ sgn} \bigg( \sum_{p=1}^{\infty} Z_{t-p} \bigg)}{\sum_{j \in L} b^j}$, for $i \in S$

where $\text{sgn(x)}$ is the sign function that returns the sign of $x$. This ensures that the resulting portfolio has $C$ dollars invested in long positions and $C$ dollars in short positions, making it dollar-neutral. The expected profit remains unchanged as it is defined by log-returns.

**11. Finite Summation for Practical Implementation:**
In real-world implementation, the infinite summation $\sum_{p=1}^\infty Z_{t-p}$ cannot be obtained due to finite price history. Given the assumption that returns from further history do not predict current returns (i.e., $\lim_{p \to \infty} \text{Cov} [ Y_t, Y_{t-p} ] = 0$), a lag parameter $P$ is introduced, replacing the infinite sum with a finite sum:

$\sum_{p=1}^P Z_{t-p}$

**Implementation Details:**
The `MultivariateCointegration` class in ArbitrageLab can be used to generate the cointegration vector. This vector is then used to generate trading signals (number of shares to long/short per asset) using the Multivariate Cointegration Trading Rule. The strategy is designed for daily frequency trading and is always in the market.

**Code Example (Python):**
```python
import pandas as pd
from arbitragelab.cointegration_approach.multi_coint import MultivariateCointegration

# Read price series data, set date as index
data = pd.read_csv('X_FILE_PATH.csv', parse_dates=['Date'])
data.set_index('Date', inplace=True)

# Initialize the optimizer
optimizer = MultivariateCointegration()

# Set the training dataset
optimizer = optimizer.set_train_dataset(data)

# Fill NaN values
optimizer.fillna_inplace(nan_method='ffill')

# Generating the cointegration vector to later use in a trading strategy
coint_vec = optimizer.get_coint_vec()
```

### Key Formulas Summary

1. **Log-returns:** $r_t^i = \ln{P_t^i} - \ln{P_{t-1}^i}$
   *   $P_i$: price of $N$ assets
   *   $r_t^i$: continuously compounded asset returns (log-returns) at time $t$

2. **Linear combination of asset prices:** $Y_t = \sum_{i=1}^N b^i \ln{P_t^i}$
   *   $Y_t$: linear combination of $N$ asset prices
   *   $b^i$: $i$-th element for a finite vector $\mathbf{b}$

3. **Conditions for stationarity of $Y_t$:**
   $E[Z_t] = 0$
   $\text{Var }Z_t = -2 \sum_{p=1}^{\infty} \text{Cov} [ Z_t, Z_{t-p} ]$
   $\sum_{p=1}^{\infty} p \text{ Cov} [ Z_t, Z_{t-p} ] < \infty$
   *   $Z_t$: asset returns series, $Z_t = Y_t - Y_{t-1} = \sum_{i=1}^N b^i r_t^i$

4. **Expected Profit of the Strategy:** $E[\pi_t] = 0.5 : C \text{ Var} Z_t > 0$
   *   $\pi_t$: profit at time $t$
   *   $C$: a positive scale factor
   *   $Z_t$: asset returns series

5. **Notional of Each Asset for Dollar-Neutral Portfolio (for $i \in L$):** $\frac{-b^i C \text{ sgn} \bigg( \sum_{p=1}^{\infty} Z_{t-p} \bigg)}{\sum_{j \in L} b^j}$
   *   $L$: set of assets with non-negative cointegration coefficient ($b^i \geq 0$)
   *   $\text{sgn(x)}$: sign function

### References

Galenko, A., Popova, E., and Popova, I. (2012) - Trading in the presence of cointegration. The Journal of Alternative Investments, 15(1):85–97.

---

## 6. Multivariate Cointegration Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/multi_coint.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/multi_coint.html)

## Introduction
This trading strategy takes new spread values one by one and allows checking if the conditions to open a position are fulfilled with each new timestamp and value provided. This allows for easier integration of these strategies into an existing data pipeline. Also, the strategy object keeps track of open and closed trades and the supporting information related to them.

## Multivariate Cointegration Strategy

The trading strategy logic is described in more detail in the [Multivariate Cointegration Framework](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration%5Fapproach/multivariate%5Fcointegration.html) section of the documentation.

**The trading strategy itself works as follows:**

1.  **Estimate the cointegration vector** \(\hat{\mathbf{b}}\) with Johansen test using training data. This step is done by the `MultivariateCointegration` class.
2.  **Construct the realization** \(\hat{Y}_t\) of the process \(Y_t\) by calculating \(\hat{\mathbf{b}}^T \ln P_t\), and calculate \(\hat{Z}_t = \hat{Y}_t - \hat{Y}_{t-1}\).
    *   \(\hat{\mathbf{b}}\) : Estimated cointegration vector.
    *   \(P_t\) : Price vector at time \(t\).
    *   \(\ln P_t\) : Log of the price vector at time \(t\).
    *   \(\hat{Y}_t\) : Realization of the cointegrated process at time \(t\).
    *   \(\hat{Z}_t\) : Difference in the realization of the cointegrated process between time \(t\) and \(t-1\).
3.  **Compute the finite sum** \(\sum_{p=1}^P \hat{Z}_{t-p}\), where the lag \(P\) is the length of a data set.
4.  **Partition the assets** into two sets \(L\) and \(S\) according to the sign of the element in the cointegration vector \(\hat{\mathbf{b}}\\).
    *   \(L\) : Set of assets where the corresponding element in \(\hat{\mathbf{b}}\) is positive.
    *   \(S\) : Set of assets where the corresponding element in \(\hat{\mathbf{b}}\) is negative.
5.  **Calculate the number of assets to trade** so that the notional of the positions would equal to \(C\). The formulas are:

    For assets \(i \in L\):
    \[ \Bigg \lfloor \frac{-b^i C \text{ sgn} \bigg( \sum_{p=1}^{P} Z_{t-p} \bigg)}{P_t^i \sum_{j \in L} b^j} \Bigg \rfloor \]

    For assets \(i \in S\):
    \[ \Bigg \lfloor \frac{b^i C \text{ sgn} \bigg( \sum_{p=1}^{P} Z_{t-p} \bigg)}{P_t^i \sum_{j \in L} b^j} \Bigg \rfloor \]

    Where:
    *   \(b^i\) : The \(i\)-th element of the cointegration vector \(\hat{\mathbf{b}}\\).
    *   \(C\) : The target notional value for the positions.
    *   \(\text{sgn}(\cdot)\) : The sign function.
    *   \(\sum_{p=1}^{P} Z_{t-p}\) : The finite sum computed in step 3, which determines the trading signal.
    *   \(P_t^i\) : The price of asset \(i\) at time \(t\).
    *   \(\sum_{j \in L} b^j\) : The sum of the positive elements of the cointegration vector, used for normalization.

    Note: The trading signal is determined by \(\sum_{p=1}^{\infty} Z_{t-p}\), which sums to time period \(t-1\). The price used to convert the notional to the number of shares/contracts to trade is the closing price of time \(t\). This ensures that no look-ahead bias will be introduced.

6.  **Open the positions** on time \(t\) and close the positions on time \(t+1\).
7.  **Re-estimate the cointegration vector** once per month (e.g., every 22 trading days). If it is time for a re-estimate, go to step 1; otherwise, go to step 2.

The strategy is trading at daily frequency and always in the market.

The strategy object is initialized with the cointegration vector.

The `update_price_values` method allows adding new price values one by one - when they are available. At each stage, the `get_signal` method generates the number of shares to trade per asset according to the above-described logic. A new trade can be added to the internal dictionary using the `add_trade` method.

As well, the `update_trades` method can be used to close the previously opened trade. If so, the internal dictionaries are updated, and the list of the closed trades at this stage is returned.

### Implementation

### Example

```python
# Importing packages
import pandas as pd
import numpy as np

# Importing ArbitrageLab tools
from arbitragelab.cointegration_approach.multi_coint import MultivariateCointegration
from arbitragelab.trading.multi_coint import MultivariateCointegrationTradingRule

# Using MultivariateCointegration as optimizer ...

# Generating the cointegration vector to later use in a trading strategy
coint_vec = optimizer.get_coint_vec()

# Creating a strategy
strategy = MultivariateCointegrationTradingRule(coint_vec)

# Adding initial price values
strategy.update_price_values(data.iloc[0])

# Feeding price values to the strategy one by one
for ind in range(data.shape[0]):

    time = spread.index[ind]
    value = spread.iloc[ind]

    strategy.update_price_values(value)

    # Getting signal - number of shares to trade per asset
    pos_shares, neg_shares, pos_notional, neg_notional = strategy.get_signal()

    # Close previous trade
    strategy.update_trades(update_timestamp=time)

    # Add a new trade
    strategy.add_trade(start_timestamp=time, pos_shares=pos_shares, neg_shares=neg_shares)

# Checking currently open trades
open_trades = strategy.open_trades

# Checking all closed trades
closed_trades = strategy.closed_trades
```

## Research Notebooks

The following research notebook can be used to better understand the Strategy described above.

*   [Multivariate Cointegration Strategy](https://hudsonthames.org/notebooks/arblab/multivariate%5Fcointegration.html)
    [Download Notebook](https://hudsonthames.org/notebooks%5Fzip/arblab/multivariate%5Fcointegration.zip) [Download Sample Data](https://hudsonthames.org/notebooks%5Fzip/arblab/Sample-Data.zip)

### Key Formulas Summary

1.  **Realization of the cointegrated process:**
    \(\hat{Y}_t = \hat{\mathbf{b}}^T \ln P_t\)
    Where:
    *   \(\hat{\mathbf{b}}\) is the estimated cointegration vector.
    *   \(P_t\) is the price vector at time \(t\).

2.  **Difference in the realization:**
    \(\hat{Z}_t = \hat{Y}_t - \hat{Y}_{t-1}\)
    Where:
    *   \(\hat{Y}_t\) is the realization of the cointegrated process at time \(t\).
    *   \(\hat{Y}_{t-1}\) is the realization of the cointegrated process at time \(t-1\).

3.  **Trading signal sum:**
    \(\sum_{p=1}^P \hat{Z}_{t-p}\)
    Where:
    *   \(\hat{Z}_{t-p}\) is the difference in the realization at lag \(p\).
    *   \(P\) is the length of the data set (lag).

4.  **Number of assets to trade for assets in set L (long positions):**
    \[ \Bigg \lfloor \frac{-b^i C \text{ sgn} \bigg( \sum_{p=1}^{P} Z_{t-p} \bigg)}{P_t^i \sum_{j \in L} b^j} \Bigg \rfloor \]
    Where:
    *   \(b^i\) is the \(i\)-th element of the cointegration vector.
    *   \(C\) is the target notional value.
    *   \(\text{sgn}(\cdot)\) is the sign function.
    *   \(P_t^i\) is the price of asset \(i\) at time \(t\).
    *   \(\sum_{j \in L} b^j\) is the sum of positive elements of the cointegration vector.

5.  **Number of assets to trade for assets in set S (short positions):**
    \[ \Bigg \lfloor \frac{b^i C \text{ sgn} \bigg( \sum_{p=1}^{P} Z_{t-p} \bigg)}{P_t^i \sum_{j \in L} b^j} \Bigg \rfloor \]
    Where:
    *   \(b^i\) is the \(i\)-th element of the cointegration vector.
    *   \(C\) is the target notional value.
    *   \(\text{sgn}(\cdot)\) is the sign function.
    *   \(P_t^i\) is the price of asset \(i\) at time \(t\).
    *   \(\sum_{j \in L} b^j\) is the sum of positive elements of the cointegration vector.

### References

Lin, Y.-X., McCrae, M., and Gulati, C., 2006 - Loss protection in pairs trading through minimum profit bounds: a cointegration approach
Puspaningrum, H., Lin, Y.-X., and Gulati, C. M. 2010 - Finding the optimal pre-set boundaries for pairs trading strategy based on cointegration technique

---

# Stochastic Control, Cointegration

## 7. Optimal Convergence

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/optimal_convergence.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/optimal_convergence.html)

## Modelling

In the paper, the authors assume that there is a riskless asset that pays a constant rate of return, $r$. A risky asset trading at the price $P_{mt}$ represents the market index. This follows a geometric random walk process:

$\frac{d P_{m t}}{P_{m l}}=\left(r+\mu_{m}\right) d t+\sigma_{m} d B_{t}$

where:
- $P_{mt}$: price of the market index at time $t$
- $r$: constant riskless asset return rate
- $\mu_{m}$: market risk premium (constant)
- $\sigma_{m}$: market volatility (constant)
- $B_t$: standard Brownian motion

In addition to the risk-free asset and the market index, the authors assume the presence of two risky assets whose prices $P_{it}, i = 1,2$, evolve according to the equations:

$\begin{split}\begin{array}{l} \frac{d P_{1 t}}{P_{1 t}}=\left(r+\beta \mu_{m}\right) d t+\beta \sigma_{m} d B_{t}+\sigma d Z_{t}+b d Z_{1 t} -\lambda_{1} x_{t} d t \\ \frac{d P_{2 t}}{P_{2 t}}=\left(r+\beta \mu_{m}\right) d t+\beta \sigma_{m} d B_{t}+\sigma d Z_{t}+b d Z_{2 t} +\lambda_{2} x_{t} d t \end{array}\end{split}$

where:
- $P_{it}$: price of risky asset $i$ at time $t$
- $\lambda_1, \lambda_2, \beta, b, \sigma$: constant parameters
- $Z_t, Z_{it}$: standard Brownian motions
- $B_t, Z_t, Z_{it}$: all mutually independent for $i = 1,2$

In the above equations, $\beta \sigma_m d B_t$ represents exposure to the market risk, whereas $\sigma d Z_{t}+b d Z_{t}$ represents idiosyncratic risks.

$x_t$ represents pricing errors in our model and is the difference between the logarithms of the two asset prices, $p_{it} = \ln P_{it}$:

$x_t = p_{1t} - p_{2t} =\ln\bigg(\frac{P_{1t}}{P_{2t}}\bigg)$

The authors make a key assumption here, that $\lambda_1 + \lambda_2 > 0$. This implies that $x_t$ is stationary and the logarithms of the prices are cointegrated with cointegrating vector $(1,-1)$.

$-\lambda_1 x_t$ and $\lambda_2 x_t$ capture the absolute mispricing of each asset relative to CAPM.

### Cointegration and relative mispricing

$x_t$ represents the relative mispricing between both assets. This is considered stationary and the dynamics of this term is given by:

$d x_{t}=-\lambda_{x} x_{t} d t+b_{x} d Z_{x t}$

where:

$\begin{split}\begin{array}{c} \lambda_{x}=\lambda_{1}+\lambda_{2}, \\ b_{x} d Z_{x t}=b d Z_{1 t}-b d Z_{2 t}, \\ b_x = \sqrt{2} b \end{array}\end{split}$

In the absence of intermediate consumption, the investor’s wealth, $W_t$, evolves according to the process:

$\begin{split}\begin{aligned} d W_{t}=& W_{t}\left(r d t+\phi_{m t}\left(\frac{d P_{m t}}{P_{m t}}-r d t\right)+\phi_{1 t} \left(\frac{d P_{1 t}}{P_{1 t}}-r d t\right)+\phi_{2 t}\left(\frac{d P_{2 t}}{P_{2 t}}-r d t\right)\right) \\ =& W_{t}\left(r d t+\left(\phi_{m t}+\beta\left(\phi_{1 t}+\phi_{2 t}\right)\right)\left(\mu_{m} d t+\sigma_{m} d B_{t}\right)\right.\\ &+\phi_{1 t}\left(\sigma d Z_{t}+b d Z_{1 t}-\lambda_{1} x_{t} d t\right) \\ &\left.+\phi_{2 t}\left(\sigma d Z_{t}+b d Z_{2 t}+\lambda_{2} x_{t} d t\right)\right) . \end{aligned}\end{split}$

We assume that the investor maximizes the expected value of a power utility function defined over terminal wealth, $W_T$. The investor’s value function is given by:

$J(t, x, W)=\frac{1}{1-\gamma} \mathrm{E}_{t}\left[W_{T}^{\*(1-\gamma)}\right]$

where $W^*_T$ is the wealth at time $T$ obtained by the optimal trading strategy with $W_t = W$ and $x_t = x$ at time $t$.

### Unconstrained Optimal Investment Strategies

For the continuing cointegrated price process (recurring arbitrage opportunities), we get closed-form solutions for the optimal portfolio weights.

The optimal weights on the market portfolio, $\phi_{m t}^{\*}$, and the individual assets, $(\phi_{1 t}^{\*}, \phi_{2 t}^{\*})$ are given by:

$\begin{split}\begin{array}{c} \phi_{m t}^{\*}=\frac{\mu_{m}}{\gamma \sigma_{m}^{2}}-\left(\phi_{1 t}^{\*}+\phi_{2 t}^{\*}\right) \beta \\ \left(\begin{array}{c} \phi_{1 t}^{\*} \\ \phi_{2 t}^{\*} \end{array}\right)=\frac{1}{\gamma\left(2 \sigma^{2}+b^{2}\right) b^{2}}\left(\begin{array}{cc} \sigma^{2}+b^{2} & -\sigma^{2} \\ -\sigma^{2} & \sigma^{2}+b^{2} \end{array}\right)\left(\begin{array}{c} -\lambda_{1}+b^{2} C(t) \\ \lambda_{2}-b^{2} C(t) \end{array}\right) \ln \left(\frac{P_{1 t}}{P_{2 t}}\right) \end{array}\end{split}$

### Delta Neutral Strategy

In the model considered in the paper, where the two stocks are assumed to have identical market betas, delta neutrality directly translates into the constraint $\phi_{1t} = -\phi_{2t}$.

For the continuing cointegrated price process (recurring arbitrage opportunities), we get closed-form solutions:

$\begin{split}\begin{array}{l} \check{\phi}_{m t}^{\*}=\frac{\mu_{m}}{\gamma \sigma_{m}^{2}}, \\ \check{\phi}_{1 t}^{\*}=\frac{-\left(\lambda_{1}+\lambda_{2}\right) \ln \left(\frac{P_{1 t}}{P_{2 t}}\right)+2 b^{2} D(t) \ln \left(\frac{P_{1 t}}{P_{2 t}}\right)}{2 \gamma b^{2}} \end{array}\end{split}$

Note: The optimal strategy is delta neutral if $\lambda_1 = \lambda_2$.

### Key Formulas Summary

1. Geometric Random Walk for Market Index: $\frac{d P_{m t}}{P_{m l}}=\left(r+\mu_{m}\right) d t+\sigma_{m} d B_{t}$
   - $P_{mt}$: market index price
   - $r$: riskless asset return rate
   - $\mu_{m}$: market risk premium
   - $\sigma_{m}$: market volatility
   - $B_t$: standard Brownian motion

2. Pricing Error (Spread): $x_t = p_{1t} - p_{2t} = \ln\left(\frac{P_{1t}}{P_{2t}}\right)$
   - $x_t$: pricing error/spread
   - $p_{it}$: logarithm of asset price $i$
   - $P_{it}$: price of asset $i$

3. Dynamics of Relative Mispricing: $d x_{t}=-\lambda_{x} x_{t} d t+b_{x} d Z_{x t}$
   - $x_t$: relative mispricing
   - $\lambda_x = \lambda_1 + \lambda_2$: mean-reversion rate
   - $b_x = \sqrt{2}b$: volatility of the mispricing process
   - $Z_{xt}$: standard Brownian motion

4. Investor's Value Function: $J(t, x, W)=\frac{1}{1-\gamma} \mathrm{E}_{t}\left[W_{T}^{\*(1-\gamma)}\right]$
   - $J(t, x, W)$: investor's value function
   - $t$: current time
   - $x$: current mispricing
   - $W$: current wealth
   - $\gamma$: utility function parameter (risk aversion)
   - $W_T^*$: optimal wealth at terminal time $T$

5. Optimal Market Portfolio Weight (Unconstrained): $\phi_{m t}^{\*}=\frac{\mu_{m}}{\gamma \sigma_{m}^{2}}-\left(\phi_{1 t}^{\*}+\phi_{2 t}^{\*}\right) \beta$
   - $\phi_{m t}^*$: optimal weight on the market portfolio
   - $\mu_m$: market risk premium
   - $\gamma$: utility function parameter
   - $\sigma_m$: market volatility
   - $\phi_{1t}^*, \phi_{2t}^*$: optimal weights on individual assets
   - $\beta$: market exposure parameter

### References

Liu, J. and Timmermann, A., 2013. Optimal convergence trade strategies.

---

# Cointegration

## 8. Sparse Mean-reverting Portfolio Selection

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/sparse_mr_portfolio.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/sparse_mr_portfolio.html)

## Sparse Mean-reverting Portfolio Selection

### Introduction

The problem of sparse mean-reverting portfolio selection aims to maximize the mean-reversion strength while trading a limited number of assets ($k \ll n$).

### Mean-reversion Strength Metrics and Proxies

One approach to measure mean-reversion strength is to assume the portfolio value follows an Ornstein-Uhlenbeck (OU) process:

$$dP_t = \lambda (\bar{P} - P_t)dt + \sigma dZ_t$$
$$P_t = \sum_{i=1}^n x_i S_{ti}$$
$$\lambda > 0$$

Where:
* $P_t$: Portfolio value at time $t$
* $\lambda$: Mean-reversion speed parameter
* $\bar{P}$: Long-term mean of the portfolio value
* $\sigma$: Volatility
* $dZ_t$: Wiener process
* $x_i$: Weight of asset $i$ in the portfolio
* $S_{ti}$: Price of asset $i$ at time $t$

Since optimizing $\lambda$ directly is challenging, three proxies are used:
1. Predictability based on Box-Tiao canonical decomposition.
2. Portmanteau statistic.
3. Crossing statistic.

#### Predictability and Box-Tiao Canonical Decomposition

##### Univariate Case

Assume the portfolio value $P$ follows the univariate recursion:

$$P_t = \hat{P}_{t-1} + \varepsilon_t$$

Where:
* $\hat{P}_{t-1}$: Predictor of $P_t$ based on past values
* $\varepsilon_t$: i.i.d. Gaussian noise, $\varepsilon_t \sim N(0, \Sigma)$

The variance relationship is:

$$\mathbf{E}[P_t^2] = \mathbf{E}[\hat{P}_{t-1}^2] + \mathbf{E}[\varepsilon_t^2]$$

Denoting $\sigma^2 = \mathbf{E}[P_t^2]$ and $\hat{\sigma}^2 = \mathbf{E}[\hat{P}_{t-1}^2]$, we have:

$$\sigma^2 = \hat{\sigma}^2 + \Sigma$$
$$1 = \frac{\hat{\sigma}^2}{\sigma^2} + \frac{\Sigma}{\sigma^2}$$

The predictability $\nu$ is defined as:

$$\nu \equiv \frac{\hat{\sigma}^2}{\sigma^2}$$

A small $\nu$ indicates stronger mean-reversion.

##### Multivariate Case

The portfolio value is $\mathbf{x}^T S_t$, where $\mathbf{x}$ is the weight vector and $S_t$ is the asset price vector. The recursion becomes:

$$\mathbf{x}^T S_t = \mathbf{x}^T \hat{S}_{t-1} + \mathbf{x}^T \varepsilon_t$$

Assuming zero mean for asset prices, predictability is:

$$\nu = \frac{\mathbf{x}^T \hat{\Gamma}_0 \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}}$$

Where:
* $\hat{\Gamma}_0$: Covariance matrix of $\hat{S}_{t-1}$
* $\Gamma_0$: Covariance matrix of $S_t$

Using a VAR(1) model, $S_t$ is:

$$S_t = S_{t-1} A + Z_t$$

Where:
* $A$: $n \times n$ square matrix
* $Z_t$: i.i.d. Gaussian noise, $Z_t \sim N(0, \Sigma)$, independent of $S_{t-1}$

Estimates for $A$ can be obtained via:
*   **Ordinary Least Square (OLS) estimate:**
    $$\hat{A} = (S_{t-1}^T S_{t-1})^{-1} S_{t-1}^T S_t$$
*   **Yule-Walker estimate:**
    $$\hat{A} = \gamma_0^{-1} \gamma_1$$

Where $\gamma_k$ is the sample lag-$k$ autocovariance matrix:

$$\gamma_k \equiv \frac{1}{T-k-1} \sum_{t=1}^{T-k}\tilde{S}_t \tilde{S}_{t+k}^T$$
$$\tilde{S}_t \equiv S_t - \frac{1}{T} \sum_{t=1}^T S_t$$

The predictability under VAR(1) is:

$$\nu = \frac{\mathbf{x}^T A^T \Gamma_0 A \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}}$$

Minimizing predictability is equivalent to finding the minimum generalized eigenvalue $\lambda_{\text{min}}$ by solving:

$$\det (\lambda_{\text{min}} \Gamma_0 - A^T \Gamma_0 A) = 0$$

The portfolio weight is the eigenvector corresponding to the smallest eigenvalue $\lambda_{\text{min}}$ of the matrix $\Gamma_0^{-1} A \Gamma_0 A^T$.

#### Portmanteau Statistic

The Portmanteau statistic of order $p$ (Ljung and Box, 1978) tests if a process is white noise. Maximizing mean-reversion strength is equivalent to minimizing this statistic. The estimate is:

$$\hat{\phi}_p(y) = \frac{1}{p} \sum_{i=1}^p \Big( \frac{\mathbf{x}^T \gamma_i \mathbf{x}}{\mathbf{x}^T \gamma_0 \mathbf{x}} \Big)^2$$

#### Crossing Statistic

Kedem and Yakowitz (1994) define the crossing statistic $\xi(x_t)$ as the expected number of crosses around 0 per unit of time:

$$\xi(x_t) = \mathbf{E} \Bigg[ \frac{\sum_{t=2}^T \unicode{x1D7D9}_{\{x_t x_{t-1} \leq 0 \}}}{T-1} \Bigg]$$

For a stationary AR(1) process, it can be reformulated with the cosine formula:

$$\xi(x_t) = \frac{\arccos (a)}{\pi}$$

Where $a$ is the first-order autocorrelation, with $|a| < 1$. Stronger mean-reversion implies a greater crossing statistic, which means a smaller first-order autocorrelation. For the multivariate case, Cuturi (2015) proposed minimizing $\mathbf{x}^T \gamma_1 \mathbf{x}$ and ensuring small absolute higher-order autocorrelations $|\mathbf{x}^T \gamma_k \mathbf{x}|, \, k > 1$.

### Covariance Selection via Graphical LASSO and Structured VAR(1) Estimate via Penalized Regression

#### Covariance Selection

Covariance selection uses an $\ell_1$-penalty to obtain sparse estimates of the inverse covariance matrix $\Gamma_0^{-1}$. The optimization problem is:

$$\max_X \log \det X - \mathbf{Tr} (\Sigma X) - \alpha \lVert X \rVert_1$$

Where:
* $X$: Inverse covariance matrix
* $\Sigma = \gamma_0$: Sample covariance matrix
* $\alpha > 0$: $\ell_1$-regularization parameter
* $\lVert X \rVert_1$: Sum of the absolute values of all matrix elements

#### Structured VAR(1) Model Estimate

For the VAR(1) model $S_t = S_{t-1} A + Z_t$, a structured (penalized) estimate of $A$ can be obtained column-wise via LASSO regression by minimizing:

$$a_i = \arg\min_x \lVert S_t^i - S_{t-1} x \rVert_2^2 + \lambda \lVert x \rVert_1$$

Where $a_i$ is a column of $A$, and $S_t^i$ is the price of asset $i$.

Alternatively, a multi-task LASSO model can be used, minimizing:

$$\arg\min_A \lVert S_t - S_{t-1} A \rVert_2^2 + \alpha \sum_i \sum_j a_{ij}^2$$

Where $a_{ij}$ is an element of matrix $A$.

#### Pinpoint the Clusters

If the Gaussian noise in the VAR(1) model is uncorrelated ($Z_t \sim N(0, \sigma I)$, $\sigma > 0$), then the graph of $\Gamma_0^{-1}$ and $A^T A$ share the same structure.

### Greedy Search

The Box-Tiao canonical decomposition can find a dense mean-reverting portfolio by solving the generalized eigenvalue problem:

$$\det (\lambda_{\text{min}} \Gamma_0 - A^T \Gamma_0 A) = 0$$

This can also be written in variational form:

$$\lambda_{\text{min}}(A^T \Gamma_0 A, \Gamma_0) = \min_{x \in \mathbb{R}^n} \frac{\mathbf{x}^T A^T \Gamma_0 A \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}}$$

To obtain a sparse portfolio, a cardinality constraint is added:

$$\begin{aligned} \text{minimize} \quad & \frac{\mathbf{x}^T A^T \Gamma_0 A \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}} \\ \text{subject to} \quad & \lVert \mathbf{x} \rVert_0 \leq k \\ & \lVert \mathbf{x} \rVert_2 = 1 \end{aligned}$$

Where $\lVert \mathbf{x} \rVert_0$ denotes the number of non-zero coefficients in $\mathbf{x}$. This is an NP-hard problem, so a greedy search is used.

**Algorithm Description:**
Let $A = A^T \Gamma_0 A$ and $B = \Gamma_0$. The support of the solution vector $x$ is $I_k = \{i \in [1, n]: x_i \neq 0\}$.

For $k=1$, $I_1 = \arg\min_{i \in [1, n]} \frac{A_{ii}}{B_{ii}}$.

Given an approximate solution with support $I_k$, the next asset is chosen by scanning assets not in $I_k$ for the one that produces the smallest increase in predictability.

$$\mathbf{x}_k = \arg\min_{x \in \mathbb{R}^n: x_{I_k^c} = 0} \frac{\mathbf{x}^T A \mathbf{x}}{\mathbf{x}^T B \mathbf{x}}$$

### Semidefinite Programming (SDP) Approach

An alternative to greedy search is to relax the cardinality constraint and reformulate the non-convex problem into a convex one. The original problem is:

$$\begin{aligned} \text{minimize} \quad & \frac{\mathbf{x}^T A \mathbf{x}}{\mathbf{x}^T B \mathbf{x}} \\ \text{subject to} \quad & \lVert \mathbf{x} \rVert_0 \leq k \\ & \lVert \mathbf{x} \rVert_2 = 1 \end{aligned}$$

This is reformulated in terms of the symmetric matrix $X = \mathbf{x} \mathbf{x}^T$:

$$\begin{aligned} \text{minimize} \quad & \frac{\mathbf{Tr} (A X)}{\mathbf{Tr} (B X)} \\ \text{subject to} \quad & \frac{1}{T} |X|_1 \leq k \\ & \mathbf{Tr} (X) = 1 \\ & X \succeq 0 \end{aligned}$$

Using change of variables $Y = \frac{X}{\mathbf{Tr} (B X)}$ and $z = \frac{1}{\mathbf{Tr} (B X)}$, the problem becomes convex:

$$\begin{aligned} \text{minimize} \quad & \mathbf{Tr} (A Y) \\ \text{subject to} \quad & \frac{1}{T} |Y|_1 \leq k \mathbf{Tr} (Y) \\ & \mathbf{Tr} (B Y) = 1 \\ & \mathbf{Tr} (Y) \geq 0 \\ & Y \succeq 0 \end{aligned}$$

This module follows the regularizer form of the SDP proposed by Cuturi (2015).

**Predictability optimization SDP:**

$$\begin{aligned} \text{minimize} \quad & \mathbf{Tr} (\gamma_1 \gamma_0^{-1} \gamma_1^T X) + \rho \lVert X \rVert_1 \\ \text{subject to} \quad & \mathbf{Tr} (\gamma_0 X) \geq V \\ & \mathbf{Tr} (X) = 1 \\ & X \succeq 0 \end{aligned}$$

**Portmanteau statistic optimization SDP:**

$$\begin{aligned} \text{minimize} \quad & \sum_{i=1}^p \mathbf{Tr} (\gamma_i X)^2 + \rho \lVert X \rVert_1 \\ \text{subject to} \quad & \mathbf{Tr} (\gamma_0 X) \geq V \\ & \mathbf{Tr} (X) = 1 \\ & X \succeq 0 \end{aligned}$$

**Crossing statistic optimization SDP:**

$$\begin{aligned} \text{minimize} \quad & \mathbf{Tr} (\gamma_1 X) + \mu \sum_{i=2}^p \mathbf{Tr} (\gamma_i X)^2 + \rho \lVert X \rVert_1 \\ \text{subject to} \quad & \mathbf{Tr} (\gamma_0 X) \geq V \\ & \mathbf{Tr} (X) = 1 \\ & X \succeq 0 \end{aligned}$$

Where:
* $\rho > 0$: $\ell_1$-regularization parameter
* $\mu > 0$: Specific regularization parameter for crossing statistic optimization
* $V > 0$: Portfolio variance lower threshold

This module uses the Truncated Power method (Yuan and Zhang, 2013) as the deflation method to retrieve the leading sparse vector of the optimal solution $X^*$ that has $k$ non-zero elements.

### Implementation

Code examples demonstrate the usage of `SparseMeanReversionPortfolio` class for:
*   Box-Tiao canonical decomposition (`box_tiao()`)
*   Covariance selection (`covar_sparse_tuning()`, `covar_sparse_fit()`)
*   Structured VAR estimate (`LASSO_VAR_tuning()`, `LASSO_VAR_fit()`)
*   Finding clusters (`find_clusters()`)
*   Greedy search (`greedy_search()`)
*   SDP for predictability (`sdp_predictability_vol()`)
*   SDP for Portmanteau statistic (`sdp_portmanteau_vol()`)
*   SDP for Crossing statistic (`sdp_crossing_vol()`)
*   Deflating SDP solution (`sparse_eigen_deflate()`)
*   Calculating mean-reversion coefficient and half-life (`mean_rev_coeff()`)

Example parameters include `alpha_min`, `alpha_max`, `n_alphas`, `clusters`, `max_iter`, `rho`, `variance`, `nlags`, `mu`, and `cardinality`.

### Key Formulas Summary

1. Ornstein-Uhlenbeck (OU) Process: $dP_t = \lambda (\bar{P} - P_t)dt + \sigma dZ_t$, where $P_t = \sum_{i=1}^n x_i S_{ti}$ and $\lambda > 0$. $P_t$ is the portfolio value, $\lambda$ is the mean-reversion speed, $\bar{P}$ is the long-term mean, $\sigma$ is the volatility, and $dZ_t$ is a Wiener process. $x_i$ are portfolio weights and $S_{ti}$ are asset prices.
2. Predictability (Univariate Case): $\nu \equiv \frac{\hat{\sigma}^2}{\sigma^2}$. $\nu$ is predictability, $\hat{\sigma}^2$ is the variance of the predicted value, and $\sigma^2$ is the variance of the actual value. A smaller $\nu$ indicates stronger mean-reversion.
3. Predictability (Multivariate Case): $\nu = \frac{\mathbf{x}^T A^T \Gamma_0 A \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}}$. $\mathbf{x}$ is the portfolio weight vector, $A$ is the VAR(1) coefficient matrix, and $\Gamma_0$ is the covariance matrix of asset prices. Minimizing $\nu$ finds a strongly mean-reverting portfolio.
4. Graphical LASSO Optimization for Covariance Selection: $\max_X \log \det X - \mathbf{Tr} (\Sigma X) - \alpha \lVert X \rVert_1$. $X$ is the inverse covariance matrix, $\Sigma$ is the sample covariance matrix, $\alpha > 0$ is the $\ell_1$-regularization parameter, and $\lVert X \rVert_1$ is the sum of the absolute values of all matrix elements.
5. Sparse Generalized Eigenvalue Problem (Greedy Search Objective): $\min_{x \in \mathbb{R}^n: \lVert x \rVert_0 \leq k, \lVert x \rVert_2 = 1} \frac{\mathbf{x}^T A^T \Gamma_0 A \mathbf{x}}{\mathbf{x}^T \Gamma_0 \mathbf{x}}$. This objective minimizes predictability subject to a cardinality constraint ($k$ non-zero assets) and a normalization constraint.

### References

d’Aspremont, A. (2011). Identifying small mean-reverting portfolios. Quantitative Finance, 11(3), pp.351-364.
Cuturi, M. and d’Aspremont, A. (2015). Mean-reverting portfolios: Tradeoffs between sparsity and volatility. arXiv preprint arXiv:1509.05954.
Fogarasi, N. and Levendovszky, J. (2012). Improved parameter estimation and simple trading algorithm for sparse, mean-reverting portfolios. In Annales Univ. Sci. Budapest., Sect. Comp, 37, pp. 121-144.
Gilbert, J.R. (1994). Predicting structure in sparse matrix computations. SIAM Journal on Matrix Analysis and Applications, 15(1), pp.62-79.
Kedem, B. and Yakowitz, S. (1994). Time series analysis by higher order crossings (pp. 115-143). New York: IEEE press.
Ljung, G.M. and Box, G.E. (1978). On a measure of lack of fit in time series models. Biometrika, 65(2), pp.297-303.
Natarajan, B.K. (1995). Sparse approximate solutions to linear systems. SIAM journal on computing, 24(2), pp.227-234.
Yuan, X.T. and Zhang, T. (2013). Truncated Power Method for Sparse Eigenvalue Problems. Journal of Machine Learning Research, 14(4).

---

## 9. Tests for Cointegration

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/cointegration_tests.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/cointegration_approach/cointegration_tests.html)

The Augmented Dickey–Fuller (ADF) test is based on the idea that the current price level gives us information about the future price level. The ADF test uses the linear model that describes the price changes as follows:

$\Delta y(t) = \lambda y(t-1) + \mu + \beta t + \alpha_1 \Delta y(t-1) + ... + \alpha_k \Delta y(t-k) + \epsilon_t$

where $\Delta y(t) \equiv y(t) - y(t-1)$ and $\Delta y(t-1) \equiv y(t-1) - y(t-2)$.

The hypothesis being tested is $\lambda = 0$. If this hypothesis is rejected, it means that the next price move depends on the current price level. The drift term $\beta t$ is often assumed to be zero for simplicity.

The half-life, which indicates how long it takes for a price to mean revert, can be calculated using the measure $\lambda$:

$\text{Half-life} = -log(2) / \lambda$

If $\lambda$ is positive, the price series are not mean-reverting. If $\lambda$ is close to zero, the half-life is very long, indicating slow mean reversion.


## Johansen Cointegration Test

The Johansen test can be applied to multiple price series. To understand how to test the cointegration of more than two variables, the equation used in the ADF test is transformed to a vector form. $Y(t)$ represents vectors of multiple price series, and $\Lambda$ and $A$ are matrices. The drift term $\beta t$ is assumed to be zero. The equation is rewritten as follows:

$\Delta Y(t) = \Lambda Y(t-1) + M + A_1 \Delta Y(t-1) + ... + A_k \Delta Y(t-k) + \epsilon_t$

Here, the hypothesis tested is $\Lambda = 0$, which implies no cointegration. Denoting the rank of the obtained matrix $\Lambda$ as $r$ and the number of price series as $n$, the number of independent portfolios that can be formed is equal to $r$.

The Johansen test calculates $r$ and tests the hypotheses of $r = 0$ (a cointegrating relationship exists), $r \le 1$, …, $r \le n - 1$. If all these hypotheses are rejected, the result is that $r = n$, and the eigenvectors of $\Lambda$ can be used as hedge ratios to construct a mean-reverting portfolio.

Implementation in ArbitrageLab involves the `JohansenPortfolio` class. After fitting data, one can access `johansen_trace_statistic`, `johansen_eigen_statistic`, `cointegration_vectors`, and `hedge_ratios`.


## Engle-Granger Cointegration Test

The Engle-Granger cointegration test determines whether two or more price series are cointegrated of a given order. The process involves three main steps:

1.  Determine the order of integration of variables $x$ and $y$. If they are integrated of the same order, the cointegration test can be applied.
2.  If the variables are integrated of order one, the following regressions are performed:

    $x_t = a_0 + a_1 y_t + e_{1,t}$

    $y_t = b_0 + b_1 x_t + e_{2,t}$

3.  Finally, the following regressions are run, and a unit root test is performed for each equation:

    $\Delta e_{1,t} = a_1 e_{1, t-1} + v_{1, t}$

    $\Delta e_{2,t} = a_2 e_{2, t-1} + v_{2, t}$

If the null hypotheses that $|a_1| = 0$ and $|a_2| = 0$ cannot be rejected, then the hypothesis that the variables are not cointegrated cannot be rejected. The hedge ratios for constructing a mean-reverting portfolio in the case of the Engle-Granger test are set to $1$ for the $x$ variable and the coefficient $-a_1$ for the $y$ variable (or $-a_1, -a_2, ...$ in case of multiple $y_i$ price series).

Implementation in ArbitrageLab involves the `EngleGrangerPortfolio` class. After fitting data, one can access `adf_statistics`, `cointegration_vectors`, and `hedge_ratios`.

### Key Formulas Summary

1. **Augmented Dickey–Fuller (ADF) Test Model:**
   $\Delta y(t) = \lambda y(t-1) + \mu + \beta t + \alpha_1 \Delta y(t-1) + ... + \alpha_k \Delta y(t-k) + \epsilon_t$
   *   $\Delta y(t)$: Change in price at time $t$
   *   $y(t-1)$: Price at time $t-1$
   *   $\lambda$: Proportionality constant (coefficient of interest for mean reversion)
   *   $\mu$: Constant term
   *   $\beta t$: Deterministic trend term
   *   $\alpha_i$: Coefficients for lagged changes in price
   *   $\epsilon_t$: White noise error term

2. **Half-life of Mean Reversion:**
   $\text{Half-life} = -log(2) / \lambda$
   *   $\lambda$: Proportionality constant from the ADF test model

3. **Johansen Cointegration Test (Vector Error Correction Model - VECM form):**
   $\Delta Y(t) = \Lambda Y(t-1) + M + A_1 \Delta Y(t-1) + ... + A_k \Delta Y(t-k) + \epsilon_t$
   *   $Y(t)$: Vector of multiple price series at time $t$
   *   $\Lambda$: Long-run coefficient matrix (rank determines cointegration relationships)
   *   $M$: Constant vector
   *   $A_i$: Short-run adjustment matrices
   *   $\epsilon_t$: Vector of error terms

4. **Engle-Granger Cointegration Test (Regression 1):**
   $x_t = a_0 + a_1 y_t + e_{1,t}$
   *   $x_t$: Price series 1 at time $t$
   *   $y_t$: Price series 2 at time $t$
   *   $a_0, a_1$: Regression coefficients
   *   $e_{1,t}$: Residuals from the regression

5. **Engle-Granger Cointegration Test (Unit Root Test on Residuals):**
   $\Delta e_{1,t} = a_1 e_{1, t-1} + v_{1, t}$
   *   $\Delta e_{1,t}$: Change in residuals at time $t$
   *   $e_{1, t-1}$: Residuals at time $t-1$
   *   $a_1$: Coefficient to test for unit root (null hypothesis is $a_1 = 0$)

### References

Chan, E., 2013. Algorithmic trading: winning strategies and their rationale (Vol. 625). John Wiley & Sons.
Bilgili, F., 1998. Stationarity and cointegration tests: Comparison of Engle-Granger and Johansen methodologies.

---

# Copula

## 10. A Deeper Intro to Copulas

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/copula_deeper_intro.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/copula_deeper_intro.html)

## A Deeper Intro to Copulas

This document provides a deeper insight into copulas, covering their origins, computational challenges, and underlying mathematical intuition. It is recommended to first review "A Practical Introduction to Copula" for foundational concepts.

### Formal Definition of Bivariate Copula

A two-dimensional copula is formally defined as a function $C: \mathbf{I}^2 \rightarrow \mathbf{I}$, where $\mathbf{I} = [0, 1]$. This function must satisfy the following properties:

*   **(C1)** Boundary Conditions: $C(0, x) = C(x, 0) = 0$ and $C(1, x) = C(x, 1) = x$ for all $x \in \mathbf{I}$.
*   **(C2)** 2-Increasing Property: For any $a, b, c, d \in \mathbf{I}$ with $a \le b$ and $c \le d$, the $C$-volume of the rectangle $[a,b]\times[c,d]$ must be non-negative:
    $$V_c \left( [a,b]\times[c,d] \right) := C(b, d) - C(a, d) - C(b, c) + C(a, c) \ge 0.$$

This definition of a copula $C$ represents the joint cumulative density on the quantiles of each marginal random variable (r.v.). That is:
$$C(u_1, u_2) = \mathbb{P}(U_1 \le u_1, U_2 \le u_2).$$
The properties (C1) and (C2) naturally derive from the properties of a joint Cumulative Distribution Function (CDF). Specifically, (C2) corresponds to the probability:
$$\mathbb{P}(a \le U_1 \le b, c \le U_2 \le d).$$

### Tail Dependence

Tail dependence describes the dependency between random variables in the extreme tails of their distributions. The coefficients of lower and upper tail dependence are defined as follows:

*   **Lower Tail Dependence** ($\lambda_l$): The probability that $U_2$ is small given that $U_1$ is small.
    $$\lambda_l := \lim_{q \rightarrow 0^+} \mathbb{P}(U_2 \le q \mid U_1 \le q),$$
*   **Upper Tail Dependence** ($\lambda_u$): The probability that $U_2$ is large given that $U_1$ is large.
    $$\lambda_u := \lim_{q \rightarrow 1^-} \mathbb{P}(U_2 > q \mid U_1 > q).$$

These coefficients can be derived directly from the copula function:

*   For lower tail dependence:
    $$\lambda_l = \lim_{q \rightarrow 0^+} \frac{\mathbb{P}(U_2 \le q, U_1 \le q)}{\mathbb{P}(U_1 \le q)} = \lim_{q \rightarrow 0^+} \frac{C(q,q)}{q},$$
*   For upper tail dependence:
    $$\lambda_u = \lim_{q \rightarrow 1^-} \frac{\mathbb{P}(U_2 > q, U_1 > q)}{\mathbb{P}(U_1 > q)} = \lim_{q \rightarrow 1^-} \frac{\hat{C}(q,q)}{q},$$
    where $\hat{C}(u_1, u_2) = u_1 + u_2 - 1 + C(1 - u_1, 1 - u_2)$ is the **reflected copula**. If $\lambda_l > 0$, there is lower tail dependence. If $\lambda_u > 0$, there is upper tail dependence.

For a Gumbel copula, it can be calculated that $\lambda_l=0$ and $\lambda_u=1$.

### Fréchet–Hoeffding Bounds

These bounds provide limits for all bivariate copulas:

*   **Theorem** (Fréchet–Hoeffding Bounds for bivariate copulas): For a bivariate copula $C(u_1, u_2)$ and $u_j \in \mathbf{I}$:
    $$\max \{ u_1 + u_2 - 1 \} \le C(u_1, u_2) \le \min\{u_1, u_2\}.$$

The lower bound corresponds to **counter-monotonicity copulas** (perfect negative dependence, e.g., $X_2 = -5 X_1$), while the upper bound corresponds to **co-monotonicity copulas** (perfect positive dependence, e.g., $X_2 = 3 X_1$). For co-monotonic variables, their quantiles are identical, leading to:
$$C(u_1, u_2) = \mathbb{P}(U_1 \le u_1, U_2 \le u_2) = \mathbb{P}(U_1 \le u_1, U_1 \le u_2) = \mathbb{P}(U_1 \le \min\{u_1, u_2\}).$$

### Empirical Copula

For two continuous random variables $X_1, X_2$, a copula always exists, as guaranteed by Sklar’s theorem. Given sufficient observations, the implied bivariate empirical copula $\tilde{C}_n$ is defined as:
$$\tilde{C}_n(\frac{i}{n}, \frac{j}{n}) = \frac{1}{n} ||\{ (X_1, X_2) \mid X_1 \le X_1(i), X_2 \le X_2(j) \}||,$$
where $X_1(i)$ is the $i$-th largest element for $X_1$, and similarly for $X_2(j)$. The term $|| \cdot ||$ denotes the cardinality of the set. This means counting the number of observations where $X_1$ and $X_2$ are not greater than their respective $i$-th and $j$-th ranks.

Alternatively, the empirical copula can be defined parametrically using marginal CDFs $F_1, F_2$:
$$\tilde{C}_n(u_1, u_2) = \frac{1}{n} ||\{ (X_1, X_2) \mid F_1^{-1}(X_1) \le u_1, F_2^{-1}(X_2) \le u_2 \}||.$$
If empirical CDFs are used, this definition is identical to the first one.

**Note on Empirical Copulas for Trading:** Using empirical copulas for time series data may not be ideal due to the assumption of independent draws and time-invariant dependency structures. A non-parametric empirical copula might "downscale" a strategy to a rank-based distance method, potentially limiting alpha generation and the ability to model tail dependencies precisely.

### "Pure" Copulas

This term refers to Archimedean and elliptical copulas. Key results regarding tail dependencies for various copulas:

1.  **Upper tail dependency**: Random variables are likely to have large values together (e.g., large gains in stock returns).
2.  **Lower tail dependency**: Random variables are likely to have small values together (e.g., stocks more likely to go down together).
3.  **No tail dependencies**: Frank and Gaussian copulas. Gaussian copula's lack of tail dependence was a factor in the 2008 financial crisis. Frank copula exhibits stronger central dependence than Gaussian.
4.  **Student-t copula**: Often performs well for fitting prices and returns data and does not yield probabilities far from an empirical copula.
5.  **Risk calculations**: Gaussian copula is overly optimistic for Value-at-Risk, while Gumbel is too pessimistic.
6.  **Copulas with upper tail dependency**: Gumbel, Joe, N13, N14, Student-t.
7.  **Copulas with lower tail dependency**: Clayton, N14 (weaker), Student-t.
8.  **Copulas with no tail dependency**: Gaussian, Frank.

**Tail Dependency for Bivariate Student-t Copula** (from Demarta, McNeil, The t Copula and Related Copulas, 2005):

| $\nu \downarrow, \rho \rightarrow$ | -0.5 | 0    | 0.5  | 0.9  | 1 |
| ------------------------------------------ | ----- | ---- | ---- | ---- | - |
| 2                                          | 0.06  | 0.18 | 0.39 | 0.72 | 1 |
| 4                                          | 0.01  | 0.08 | 0.25 | 0.63 | 1 |
| 10                                         | 0     | 0.01 | 0.08 | 0.46 | 1 |
| $\infty$                              | 0     | 0    | 0    | 0    | 1 |

As the degrees of freedom ($\nu$) increase, the Student-t copula converges to a Gaussian copula, and its tail dependence (which is symmetric for Student-t) changes.

### Creating Own Copulas

Users can create Archimedean or elliptical copula objects. All copula classes share basic public methods for calculating CDF, PDF, conditional CDF, sampling, and fitting to data.

**Example Code Snippet (Gumbel Copula):**
```python
from arbitragelab.copula_approach.archimedean import Gumbel
from arbitragelab.copula_approach.elliptical import StudentCopula, fit_nu_for_t_copula

cop = Gumbel(theta=2)
descr = cop.describe()

cdf = cop.get_cop_density(0.5, 0.7)
pdf = cop.get_cop_eval(0.5, 0.7)
cond_cdf = cop.get_condi_prob(0.5, 0.7)

sample = cop.sample(num=100)

cop.fit([0.5, 0.2, 0.3, 0.2, 0.1, 0.99],
        [0.1, 0.02, 0.9, 0.22, 0.11, 0.79])
print(cop.theta)

cop.plot_scatter(200)
cop.plot_pdf('3d')
cop.plot_pdf('contour')
cop.plot_cdf('3d')
cop.plot_cdf('contour')
```

**Example Code Snippet (Student Copula):**
```python
nu = fit_nu_for_t_copula([0.5, 0.2, 0.3, 0.2, 0.1, 0.99],
                         [0.1, 0.02, 0.9, 0.22, 0.11, 0.79])
student_cop = StudentCopula(nu=nu, cov=None)
student_cop.fit([0.5, 0.2, 0.3, 0.2, 0.1, 0.99],
                [0.1, 0.02, 0.9, 0.22, 0.11, 0.79])
```

### Applying Copula to Empirical Data

To use copulas with empirical data, one must fit the copula to the data to find its parameters (e.g., $\theta$ for Archimedean, $\rho$/cov for elliptical). Copulas require pseudo-observations distributed in $[0, 1]$. This can be achieved using `statsmodels.distributions.empirical_distribution.ECDF` or ArbitrageLab's `construct_ecdf_lin` (a modified ECDF with linear interpolation).

To select the best-fitting copula for empirical data, information criteria are commonly used:

*   Akaike Information Criterion (AIC)
*   Schwarz Information Criterion (SIC)
*   Hannan-Quinn Information Criterion (HQIC)

These criteria use the `log_likelihood` from the `get_log_likelihood_sum` function. The copula yielding the minimum AIC, SIC, or HQIC value is considered the best fit.

ArbitrageLab provides a function `fit_copula_to_empirical_data` that takes empirical data, constructs ECDFs, fits copulas, and returns the fitted copula object, ECDF functions, and information criterion values.

**Example Code Snippet (Fitting Copulas):**
```python
import pandas as pd
from arbitragelab.copula_approach import fit_copula_to_empirical_data
from arbitragelab.copula_approach.archimedean import (Gumbel, Clayton, Frank,
                                                      Joe, N13, N14)
from arbitragelab.copula_approach.elliptical import (StudentCopula,
                                                     GaussianCopula)

bkd_prices = pd.read_csv('BKD.csv', index_col=0)
esc_prices = pd.read_csv('ECS.csv', index_col=0)

bkd_returns = bkd_prices.pct_change().dropna()
esc_returns = esc_prices.pct_change().dropna()

copulas = [Gumbel, Clayton, Frank, Joe, N13, N14, GaussianCopula, StudentCopula]
aics = dict()

for cop in copulas:
    info_crit_logs, fit_copula, ecdf_x, ecdf_y = fit_copula_to_empirical_data(x=bkd_prices,
                                                                              y=esc_returns,
                                                                              copula=cop)
    aics[info_crit_logs['Copula Name']] = info_crit_logs['AIC']

print(aics)
```

### Mixed Copulas

ArbitrageLab supports mixed copula classes like `CFGMixCop` (Clayton-Frank-Gumbel mix) and `CTGMixCop` (Clayton-Student-Gumbel mix), inspired by [da Silva et al. 2017].

A mixed copula, such as the Clayton-Frank-Gumbel (CFG) mixed copula, is defined by the dependency parameters ($\theta$) for each component copula and their respective weights ($w$), which sum to 1. For CFG, there are 5 parameters in total. The weights represent the probability of an observation originating from each component.

**Clayton-Frank-Gumbel Mixed Copula:**
$$C_{mix}(u_1, u_2; \theta, w) := w_C C_C(u_1, u_2; \theta_C) + w_F C_F(u_1, u_2; \theta_F) + w_G C_G(u_1, u_2; \theta_G)$$

Mixed copulas offer greater flexibility in calibrating upper and lower tail dependencies compared to "pure" copulas. However, fitting them to data is complex and can be unstable with generic maximization algorithms due to:

*   High instability and sensitivity to the choice of maximization algorithm.
*   Tendency to settle on suboptimal results, sometimes worse than individual component copulas.
*   Convergence issues.
*   Numerical instability of derivative computations for some copulas.
*   Unreasonably small weights for some components, indicating poor modeling.

### EM Fitting Algorithm

To address the challenges of fitting mixed copulas, a two-step Expectation-Maximization (EM) algorithm, adapted from [Cai, Wang 2014], is adopted. This algorithm aims to maximize an objective function $Q$ for copula parameters $\theta$ and weights $w$.

**Objective Function for a three-component mixed copula:**
$$Q(\theta, w) = \sum_{t=1}^T \log \left[ \sum_{k=1}^3 w_k c_k(u_{1,t}, u_{2,t}; \theta_k) \right] - T \sum_{k=1}^3 p_{\gamma,a}(w_k) + \delta (\sum_{k=1}^s w_k - 1),$$
where:

*   $T$ is the length of the training set (number of observations).
*   $k$ is the dummy variable for each copula component.
*   $p_{\gamma,a}(\cdot)$ is the smoothly clipped absolute deviation (SCAD) penalty term with tuning parameters $\gamma$ and $a$. This term drives small copula component weights to 0.
*   $\delta$ is the Lagrange multiplier term used in the E-step.

**Lagrange Multiplier ($\delta$):**
$$\delta = T p_{\gamma,a}'(w_k) - \sum_{t=1}^T \frac{c_k(u_{1,t}, u_{2,t}; \theta_k)}{\sum_{j=1}^3 w_j c_j(u_{1,t}, u_{2,t}; \theta_j)}$$

**E-step (Expectation Step):** Iteratively calculate the new weights $w_k^{new}$ using the old $\theta$ and $w$ until convergence:
$$w_k^{new} = \left[ w_k p_{\gamma,a}'(w_k) - \frac{1}{T} \sum_{t=1}^T \frac{c_k(u_{1,t}, u_{2,t}; \theta_k)}{\sum_{j=1}^3 w_j c_j(u_{1,t}, u_{2,t}; \theta_j)} \right] \times \left[ \sum_{j=1}^3 w_j p_{\gamma,a}'(w_j) \right]^{-1}$$

**M-step (Maximization Step):** Use the updated weights to find new $\theta$ values that maximize $Q$. This can be done using optimization methods like truncated Newton or Newton-Raphson. This step is more stable than simultaneously estimating all parameters.

The EM algorithm iterates between the E-step and M-step until convergence. It is considered oracle (good asymptotic properties) and sparse (trims small weights).

**Limitations of EM Algorithm:**

*   Can be slow for some datasets (e.g., CTG copula due to Student-t component).
*   May struggle to differentiate component weights if copulas in the mixture are very similar (e.g., Gaussian and Frank).
*   SCAD parameters $\gamma$ and $a$ may require tuning, although default values are provided.
*   Optimization algorithms may occasionally throw warnings if they do not strictly adhere to prescribed bounds, which usually does not compromise the result.

### Interesting Open Problems

*   Parametric fitting of Student-t and mixed copulas.
*   Establishing statistical properties to justify Archimedean copulas for random variables.
*   Adapting copulas to time series to account for time-varying dependencies.
*   Analyzing copulas in time series contexts, particularly regarding the average $\mu$.
*   Developing copulas that model time-varying dependency structures.
*   Analyzing asymmetric pairs using copulas.

### Key Formulas Summary

1. Bivariate Copula Definition (C1): $C(0, x) = C(x, 0) = 0$ and $C(1, x) = C(x, 1) = x$ for all $x \in \mathbf{I}$.
2. Bivariate Copula Definition (C2): $V_c \left( [a,b]\times[c,d] \right) := C(b, d) - C(a, d) - C(b, c) + C(a, c) \ge 0$.
3. Joint Cumulative Density: $C(u_1, u_2) = \mathbb{P}(U_1 \le u_1, U_2 \le u_2)$.
4. Lower Tail Dependence: $\lambda_l = \lim_{q \rightarrow 0^+} \frac{C(q,q)}{q}$.
5. Fréchet–Hoeffding Bounds: $\max \{ u_1 + u_2 - 1 \} \le C(u_1, u_2) \le \min\{u_1, u_2\}$.

### References

Nelsen, Roger B. (2007) - An introduction to copulas
Nelsen, Roger B. (2003) - “Properties and applications of copulas: A brief survey.”
Chang, Bo. - Copula: A Very Short Introduction
Andy Jones. - SCAD penalty
Demarta, S. and McNeil, A.J. (2005) - The t Copula and Related Copulas
Liew, R.Q. and Wu, Y. (2013) - Pairs trading: A copula approach
Stander, Y., Marais, D. and Botha, I. (2013) - Trading strategies with copulas
Schmid, F., Schmidt, R., Blumentritt, T., Gaißer, S. and Ruppert, M. (2010) - Copula-based measures of multivariate association
Huard, D., Évin, G. and Favre, A.C. (2006) - Bayesian copula selection
Kole, E., Koedijk, K. and Verbeek, M. (2007) - Selecting copulas for risk management
Nelsen, R.B. (2003) - Properties and applications of copulas: A brief survey
Cai, Z. and Wang, X. (2014) - Selection of mixed copula model via penalized likelihood
Liu, B.Y., Ji, Q. and Fan, Y. (2017) - A new time-varying optimal copula model identifying the dependence across markets
Demarta, S. and McNeil, A.J. (2005) - The t copula and related copulas

---

## 11. A Practical Introduction to Copula

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/copula_brief_intro.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/copula_brief_intro.html)

This document provides a practical introduction to copulas, focusing on their definition, types, generators, and methods for density calculation and sample generation. The core idea behind copulas is to separate the modeling of marginal distributions from the dependence structure between random variables.

**Definition of Bivariate Copula (Sklar’s Theorem)**

For two random variables $S_1, S_2 \in [-\infty, \infty]$ with continuous CDFs $F_1, F_2$, their (cumulative) joint distribution is $H(s_1, s_2) := P(S_1 \le s_1, S_2 \le s_2)$. The bivariate copula $C: [0, 1] \times [0, 1] \rightarrow [0, 1]$ is defined as:

$$C(u_1, u_2) = P(U_1 \le u_1, U_2 \le u_2) \\ = P(S_1 \le F_1^{-1}(u_1), S_2 \le F_2^{-1}(u_2)) \\ = H(F_1^{-1}(u_1), F_2^{-1}(u_2))$$

where $F_1^{-1}$ and $F_2^{-1}$ are quasi-inverses of the marginal CDFs $F_1$ and $F_2$. $U_1$ and $U_2$ are uniformly distributed quantile random variables.

**Cumulative Conditional Probabilities**

The cumulative conditional probabilities are defined as:

$$P(U_1\le u_1 | U_2 = u_2) := \frac{\partial C(u_1, u_2)}{\partial u_2}$$

$$P(U_2\le u_2 | U_1 = u_1) := \frac{\partial C(u_1, u_2)}{\partial u_1}$$

**Copula Density**

The copula density $c(u_1, u_2)$ is given by:

$$c(u_1 , u_2) := \frac{\partial^2 C(u_1, u_2)}{\partial u_1 \partial u_2}$$

This density is crucial for sampling and maximum likelihood estimation, and conditional probabilities are used in trading signal formation.

**Archimedean Copulas**

A bivariate copula $C$ is Archimedean if it can be represented as:

$$C(u_1, u_2; \theta) = \phi^{[-1]}(\phi(u_1; \theta), \phi(u_2; \theta))$$

where $\phi: [0,1] \times \Theta \rightarrow [0, + \infty)$ is the generator for the copula, and $\phi^{[-1]}$ is its pseudo-inverse. $\theta$ is the parameter measuring the relationship between the two random variables.

**Generators for Archimedean Copulas:**

*   **Gumbel**: $\phi(t; \theta) = (- \ln t)^\theta$, $\theta \in [1, +\infty)$
*   **Frank**: $\phi(t; \theta) = - \ln \left(\frac{e^{-\theta t}-1}{e^{-\theta}-1} \right)$, $\theta \in [-\infty, \infty)\backslash\{0\}$
*   **Clayton**: $\phi(t; \theta) = \frac{t^{-\theta}-1}{\theta}$, $\theta \in [-1, +\infty)\backslash\{0\}$
*   **Joe**: $\phi(t; \theta) = -\ln(1-(1-t)^\theta)$, $\theta \in [1, +\infty)$
*   **N13**: $\phi(t; \theta) = (1- \ln t)^\theta - 1$, $\theta \in [0, +\infty)$
*   **N14**: $\phi(t; \theta) = (t^{-1/\theta}- 1)^\theta$, $\theta \in [1, +\infty)$

**Gaussian Copula**

For a correlation matrix $R \in [-1, 1]^{d \times d}$, the multi-variate Gaussian copula with parameter matrix $R$ is defined as:

$$C_R(\mathbf{u}) := \Phi_R(\Phi^{-1}(u_1),\dots, \Phi^{-1}(u_d))$$

where $\Phi_R$ is the joint Gaussian CDF with $R$ being its covariance matrix, and $\Phi^{-1}$ is the inverse of the CDF of a standard normal.

**Student-t Copula**

The Student-t copula is defined similarly, with $\nu$ being the degrees of freedom:

$$C_{R,\nu}(\mathbf{u}) := \Phi_{R,\nu}(\Phi_{\nu}^{-1}(u_1),\dots, \Phi_{\nu}^{-1}(u_d))$$

Gaussian and Student-t copulas belong to the family of **Elliptical copulas**.

**Densities and Conditional Probabilities for Gaussian and Student-t Copulas:**

*   **Gaussian:**

    Conditional Probability:
    $$P(U_1 \le u_1 \mid U_2 = u_2) = \Phi\left(\frac{\Phi^{-1}(u_1) - \rho \Phi^{-1}(u_2)}{\sqrt{1 - \rho^2}} \right)$$

    Density:
    $$c(u_1, u_2) = \frac{1}{\sqrt{1-\rho^2}} \exp \left[ \frac{ \rho(-2\Phi^{-1}(u_1) \Phi^{-1}(u_2) + (\Phi^{-1}(u_1))^2 \rho + (\Phi^{-1}(u_2))^2 \rho)} {2(\rho^2 - 1)} \right]$$

*   **Student-t:**

    Conditional Probability:
    $$P(U_1 \le u_1 \mid U_2 = u_2) = \Phi_{\nu + 1}\left( (\Phi_{\nu}^{-1}(u_1) - \rho \Phi_{\nu}^{-1}(u_2)) \sqrt{\frac{\nu + 1}{(\nu + \Phi_{\nu}^{-1}(u_2))(1-\rho^2)}} \right)$$

    Density:
    $$c(u_1, u_2) = \frac{f_{R,\nu}(\Phi_{\nu}^{-1}(u_1), \Phi_{\nu}^{-1}(u_2))} {f_{\nu}(\Phi_{\nu}^{-1}(u_1)) f_{\nu}(\Phi_{\nu}^{-1}(u_2))}$$

    where $f_{R, \nu}$ is the PDF for bivariate Student-t distribution with degrees of freedom $\nu$ and covariance matrix being the correlation matrix $R$, and $f_{\nu}$ is the univariate Student-t PDF. $\rho \in [-1, 1]$ is the correlation parameter.

**Sample Generation from a Copula**

For Archimedean copulas, the general methodology for sampling or simulation comes from (Nelsen, 2006):

1.  Generate two uniform in $[0, 1]$ i.i.d.’s $(v_1, v_2)$.
2.  Calculate $w = K_c^{-1}(v_2)$, where $K_c(t) = t - \frac{\phi(t)}{\phi'(t)}$.
3.  Calculate $u_1 = \phi^{-1}[v_1 \phi(w)]$ and $u_2 = \phi^{-1}[(1-v_1) \phi(w)]$.
4.  Return $(u_1, u_2)$.

For Gaussian and Student-t copulas, the procedure is:

1.  Generate a pair $(v_1, v_2)$ using a bivariate Gaussian/Student-t distribution with desired correlation (and degrees of freedom).
2.  Transform those into quantiles using CDF $\Phi$ from standard Gaussian or Student-t distribution (with desired degrees of freedom). i.e., $u_1 = \Phi(v_1)$, $u_2 = \Phi(v_2)$.
3.  Return $(u_1, u_2)$.

### Key Formulas Summary

1.  **Bivariate Copula Definition (Sklar's Theorem)**:
    $$C(u_1, u_2) = H(F_1^{-1}(u_1), F_2^{-1}(u_2))$$
    where $C$ is the copula, $u_1, u_2$ are quantiles, $H$ is the joint CDF, and $F_1^{-1}, F_2^{-1}$ are the quasi-inverses of the marginal CDFs.

2.  **Copula Density**:
    $$c(u_1 , u_2) := \frac{\partial^2 C(u_1, u_2)}{\partial u_1 \partial u_2}$$
    This defines the probability density of the copula.

3.  **Archimedean Copula Representation**:
    $$C(u_1, u_2; \theta) = \phi^{[-1]}(\phi(u_1; \theta), \phi(u_2; \theta))$$
    where $\phi$ is the generator function and $\theta$ is the parameter.

4.  **Gaussian Copula**:
    $$C_R(\mathbf{u}) := \Phi_R(\Phi^{-1}(u_1),\dots, \Phi^{-1}(u_d))$$
    where $\Phi_R$ is the joint Gaussian CDF with correlation matrix $R$, and $\Phi^{-1}$ is the inverse of the standard normal CDF.

5.  **Student-t Copula Conditional Probability**:
    $$P(U_1 \le u_1 \mid U_2 = u_2) = \Phi_{\nu + 1}\left( (\Phi_{\nu}^{-1}(u_1) - \rho \Phi_{\nu}^{-1}(u_2)) \sqrt{\frac{\nu + 1}{(\nu + \Phi_{\nu}^{-1}(u_2))(1-\rho^2)}} \right)$$
    This formula gives the conditional probability for a Student-t copula, with $\nu$ degrees of freedom and correlation parameter $\rho$.

### References

Nelsen, Roger B. (2007) - An introduction to copulas
Nelsen, Roger B. (2003) - “Properties and applications of copulas: A brief survey.”
Chang, Bo. - Copula: A Very Short Introduction
Wiecki, Thomas. - An intuitive, visual guide to copulas
Liew et al. (2013) - (referenced for trading signal formation)
Nelsen (2006) - (referenced for Archimedean copula sampling methodology for sampling/simulation)

---

# Copula, Pairs Trading

## 12. Basic Copula Trading Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/basic_copula.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/basic_copula.html)

The Basic Copula Trading Strategy is a long-short pairs trading scheme that utilizes copulas to model the relationship between two stocks, \(S_1\) and \(S_2\). The strategy involves fitting a copula to the price data of the stocks during a training/formation period and then using conditional probabilities derived from this copula to generate trading signals during a trading/testing period.

**Conditional Probabilities:**

For a pair of stocks \(S_1\) and \(S_2\), the strategy calculates conditional probabilities using trading period data. These probabilities are based on quantiles \(u_i \in [0, 1]\) of the trading period data, mapped by a Cumulative Distribution Function (CDF) formed in the training period. The key conditional probabilities are:

\[\begin{split}\begin{align} P(U_1\le u_1 | U_2 = u_2), \\ P(U_2\le u_2 | U_1 = u_1). \end{align}\end{split}\]

Where:
* \(u_i\) represents the quantile of trading period data for stock \(i\).
* \(U_i\) represents the random variable for the quantile of stock \(i\).

**Interpretation of Conditional Probabilities:**

*   If \(P(U_1\le u_1 | U_2 = u_2) < 0.5\), then stock 1 is considered **under-valued**.
*   If \(P(U_1\le u_1 | U_2 = u_2) > 0.5\), then stock 1 is considered **over-valued**.

**Trading Logic (Signal Rules):**

The strategy defines an upper threshold \(b_{up}\) (e.g., 0.95) and a lower threshold \(b_{lo}\) (e.g., 0.05) for generating trading signals.

*   **Long the Spread (Buy \(S_1\) and/or Sell \(S_2\)):**
    If \(P(U_1\le u_1 | U_2 = u_2) \le b_{lo}\) **and** \(P(U_2\le u_2 | U_1 = u_1) \ge b_{up}\), then stock 1 is undervalued, and stock 2 is overvalued. The position is \(1\) (long).

*   **Short the Spread (Sell \(S_1\) and/or Buy \(S_2\)):**
    If \(P(U_2\le u_2 | U_1 = u_1) \le b_{lo}\) **and** \(P(U_1\le u_1 | U_2 = u_2) \ge b_{up}\), then stock 2 is undervalued, and stock 1 is overvalued. The position is \(-1\) (short).

*   **Exit Position:**
    If both/either conditional probabilities cross the boundary of \(0.5\), the position is exited. The position becomes \(0\).

    The authors originally proposed an **'and'** logic for exiting: Both conditional probabilities need to cross \(0.5\). However, an **'or'** logic is also provided: At least one of the conditional probabilities crosses \(0.5\).

**Ambiguities and Comments on Trading Logic:**

1.  **Open signal and an exit signal:** Exit signal overrides open signal.
2.  **Open signal with an existing position:** Flip the position to the signal’s suggestion (e.g., short position receives a long signal, position becomes long).
3.  **Long and short signal together:** This should not happen with default logic. If it does, no opening signal is generated, and positions do not change unless an exit signal resets the position to 0.

**Model Parameters and Estimation:**

The strategy involves a pseudo-MLE (Maximum Likelihood Estimation) fit to establish a copula that reflects the relationship between the two stocks during the training/formation period. The specific copula type (e.g., Gumbel, Student-t, N13, N14) is chosen, and its parameters are estimated from the training data. The example code demonstrates fitting a Gumbel copula using `fit_copula_to_empirical_data` function.

Information criteria such as AIC, SIC, and HQIC, along with log-likelihood, are used to evaluate the fit of the copula.

**Implementation Details:**

The `BasicCopulaTradingRule` class is used for on-the-go generation of trading signals. It takes `exit_rule` (e.g., 'and'), `open_probabilities` (e.g., \((0.5, 0.95)\)), and `exit_probabilities` (e.g., \((0.9, 0.5)\)) as parameters. It requires setting the fitted copula and the CDFs for the individual stock series.

### Key Formulas Summary

1.  **Conditional Probability of \(U_1\) given \(U_2\):**
    \(P(U_1\le u_1 | U_2 = u_2)\)
    *   \(u_1\): Quantile of trading period data for stock 1.
    *   \(u_2\): Quantile of trading period data for stock 2.
    *   \(U_1, U_2\): Random variables representing the quantiles of stock 1 and stock 2, respectively.

2.  **Conditional Probability of \(U_2\) given \(U_1\):**
    \(P(U_2\le u_2 | U_1 = u_1)\)
    *   \(u_1\): Quantile of trading period data for stock 1.
    *   \(u_2\): Quantile of trading period data for stock 2.
    *   \(U_1, U_2\): Random variables representing the quantiles of stock 1 and stock 2, respectively.

3.  **Long Spread Entry Condition:**
    \(P(U_1\le u_1 | U_2 = u_2) \le b_{lo}\) **and** \(P(U_2\le u_2 | U_1 = u_1) \ge b_{up}\)
    *   \(b_{lo}\): Lower threshold (e.g., 0.05).
    *   \(b_{up}\): Upper threshold (e.g., 0.95).

4.  **Short Spread Entry Condition:**
    \(P(U_2\le u_2 | U_1 = u_1) \le b_{lo}\) **and** \(P(U_1\le u_1 | U_2 = u_2) \ge b_{up}\)
    *   \(b_{lo}\): Lower threshold (e.g., 0.05).
    *   \(b_{up}\): Upper threshold (e.g., 0.95).

5.  **Exit Condition (Example using 'and' logic):**
    \(P(U_1\le u_1 | U_2 = u_2) \text{ crosses } 0.5\) **and** \(P(U_2\le u_2 | U_1 = u_1) \text{ crosses } 0.5\)
    *   A 'cross' implies moving from below to above, or above to below the threshold.

### References

Liew, R.Q. and Wu, Y., 2013. Pairs trading: A copula approach. Journal of Derivatives & Hedge Funds, 19(1), pp.12-30.
Stander, Y., Marais, D. and Botha, I., 2013. Trading strategies with copulas. Journal of Economic and Financial Sciences, 6(1), pp.83-107.

---

# Copula

## 13. C-vine Copula Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/cvine_copula_strategy.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/cvine_copula_strategy.html)

Note

This document is an implementation of:

Stübinger, J., Mangold, B. and Krauss, C.
Quantitative Finance, 2018.


## C-vine Copula Strategy


With the power of vine copula, we are able to model the relation among several random variables. Speficifally
we aim to trade based on the information generated from the vine copula model.
Similar to traditional bivariate approaches, we use the conditional (cumulative) probability to gauge whether
the target stock is underpriced or overpriced against other stocks, and generate trading signal based on them
from a mean-reversion bet.

We aim to cover the following topics:

Idea and typical workflow of the C-vine copula approach

Strategy details

Comments for this approach


## Overview of the C-vine Stategy


At first, vine copula is a very flexible model for dealing with multi-variate dependencies. It decomposes
joint probability density into bivariate copula densities and marginal densities in a tree structure.
R-vine is the most generic structure that is shared by all vine copulas, and in application people use C-vine
and D-vine more often as special cases of a generic R-vine.

Note

With $N$ random variables, there are $N (N - 1)(N - 2)! 2^{(N - 2)(N - 3)/2}/2$ many possible
structures for R-vines. Therefore numerically fitting an R-vine structure directly from data becomes a
burn, and even if such a method exists and can be calculated in a reasonable time, it is likely subject to
overfit using financial market data.
In contrast, for a C-vine there are “only” $N!$ possible structures, and it has much better interpretability.

Since C-vine has the star-like structure at each level of the tree, it is ideal for modeling dependencies where one
specific random variable is key.
Hence, although we are squeezing statistical arbitrage from an $N$ stocks cohort, we are using the “1-vs-the rest”
type of framework.
The D-vine or more general R-vine strategy handling mispricings all together, that dynamically trades every stock
based on the mispricing info, to the best of our knowlegde, is not yet developed, at least not available in literature.

We have the workflow as follows:

Get data

Figure out the C-vine structure

Calculate probability density

Calculate the conditional probability

Generate signals and trade

We will dive into the details for each part of the workflow.


## C-vine Copula Strategy Workflow


For ease of demontration, assuming we are trading 4 stocks.


## Step 1: Get data


We work with stocks’ **daily returns data** exclusively.

Note

Selecting trading candidates is a serious topic, and can largely determine if a strategy is profitable or
not.
There are 4 methods proposed in [Stübinger et al. 2018]:

pairwise Spearman’s rho,

multi-dimensional Spearman’s rho,

sum of distance in quantile plots to hyper-diagonal

copula-chi-square test for dependence.

Loosely speaking, the goal is to find stocks cohorts that are heavily dependent, such that a mean-reversion bet
on relative mispricings is profitable.
For more details in implementation, please refer to Vine Copula Partner Selection.

Suppose we have chosen a few cohorts and in each cohort it has a key stock element. We then need to turn the translate
the stocks’ returns data into its quantiles (pseudo-observations) using empirical CDFs (ECDFs).
We denote the pseudo-observations as $u_i$’s, and they are all uniform in $[0, 1]$.


## Step 2: Figure out the C-vine Structure


To start with, there are $4! = 24$ many possible C-vine structures. Without loss of generality assuming the stock 1
is our target stock. In the end, we aim to come up with this conditional density that indicates relative mispricing for
stock 1 against 3 other stocks in this cohort:

$$\mathbb{P}(U_1 \le u_1 | U_2=u_2, U_3=u_3, U_4=u_4)$$

If $h(u_1 | u_2, u_3, u_4) < 0.5$ then that day’s return for stock 1 is considered lower than the mean of what the
history tells and vice versa, similar to the “traditional” copula approaches with Mispricing Index.

In [Stübinger et al. 2018], the authors claimed that in order to calculate $h(u_1 | u_2, u_3, u_4)$, stock 1 must never be
at the center of every level of the tree.
Remember that C-vine can be fully characterized by an ordered tuple $(c_4, c_3, c_2, c_1)$ where $c_1$ is the
center for the level-1 tree, $c_2$ for level-2 and so on.
Therefore, to make stock 1 never at the center (except at the tree root), it is equivalent to check each possibility generated by
$(1, c_3, c_2, c_1)$, where $(c_3, c_2, c_1)$ is a permutation of ${2, 3, 4}$. Obviously there are $3! = 6$ many ways available.

Note

Disclaimer: I do not fully agree with the authors’ argument here, because **all** vine copula allows one to calculate
the joint probability density $f(u_1, u_2, u_3, u_4)$, for any given quantities $(u_1, u_2, u_3, u_4)$ in
order to calculate $h$ for any target stock, simply integrate along that marginal variable and then normalize by a
full integration in that direction. For example:

$$\left( \int_0^{u_1} f(u, u_2, u_3, u_4) du \right) / \left( \int_0^{1} f(u, u_2, u_3, u_4) du \right)$$

Moreover, I think if we treat stock 1 as the key stock, it should be **at the center of every level of the tree**,
because it makes intuitive sense to model all other stocks’ and their bivariate copula densities relation given the stock 1’s information.
Stock 1 is the object of interest, and therefore should be the governing quantity here.
C-vine structure intrinsically orders the marginal variables by their importance of interdependencies from its ordered tuple representation,
and the target stock should be the most important (therefore at the end of the tuple).
It is strange to argue that the least important stock in terms of interdependencies should become the target stock.
I.e., 1 should be put at the end of the tuple, not at the beginning, and there are still 6 many possible structures for
4 stocks.

Currently we provide the implementation in [Stübinger et al. 2018] and the alternative method that puts the target stock at the center.

After chosen the 6 possible vine structures, we then fit everyone of them and calculate the associated AIC value. We choose
the final C-vine structure among candidates with the lowest AIC value.
It is equivalent in this case to directly comparing the log-likelihood and choose the one that constitutes the largest
log-likelihood value.
The exact fitting includes figuring out what type of (parametric) bivariate copula to use for every node, and the parameter(s)
value that fits best the data.


## Step 3: Probability Density


We aim to calculate $f(u_1, u_2, u_3, u_4)$.
This is straightforward once we fit the C-vine to training data. Now we are working on the trading priod data. At first
we should map them into quantiles using the ECDFs trained in the training period. Then we can calculate directly the probability
density for pseudo-observations, say $(u_1, u_2, u_3, u_4)$, by calculating every node at every level of the tree.
Note that each node constitues a probability density, either marginal density (top of the tree) or the copula density (not
top of the tree). And the final probability density is their product.


## Step 4: Conditional Probability


We aim to calculate $h(u_1| u_2, u_3, u_4)$, given that stock 1 is the target stock. Similarly we can compute for
other stocks if they are the target.
Here we use numerical integration for this value:

$$\begin{split}\begin{align} h(u_1 | u_2, u_3, u_4) &= \mathbb{P}(U_1 \le u_1 | U_2=u_2, U_3=u_3, U_4=u_4) \\ &= \left( \int_0^{u_1} f(u, u_2, u_3, u_4) du \right) / \left( \int_0^{1} f(u, u_2, u_3, u_4) du \right) \end{align}\end{split}$$

Keep in mind that this value is model dependent: it depends on which vine structure we are using, and the types of bivariate
copulas and their parameters in each node. Some people denote the conditional probability as $h_C$ to indicate that it
depends on a copula.

Note

Here we computed $h$ from the “bottom up” by marginal integration. The authors suggested computing from “top down”
by taking partial differentiations from the copula definition $C(u_1, u_2, u_3, u_4)$ (cumulative density):

$$\frac{\partial^3 C(u_1, u_2, u_3, u_4)}{\partial u_1 \partial u_2 \partial u_3}$$

I do not agree with the author’s approach for the following reason:
Mathematically speaking it is the same. However vine copula only allows one to compute the joint density $f$, and
unlike “traditional” copula models where $C$ is defined by definition. For vine copula $C$ is found by
Monte-Carlo integrations from $f$.
Also even if $C$ can be found analytically, taking 3 numerical partial
differentiations will likely yield more issues compared to numerically integrating just along 1 marginal variable.


## Step 5: Generate Signals and Trade


For simplificaition say we have 2 cohorts after the stocks selection, each cohort has a target stock.
And we have fitted 2 C-vine copulas respectively for the 2 cohorts with their own target stock.
Without loss of generality, let us fix stock 1 for each cohort as its target stock.
For conditional probability $h$:

If $h > 0.5$, stock 1’s return that day is higher than the historical average compared to other 3 stocks
in the cohort.

If $h < 0.5$, stock 1’s return that day is higher than the historical average compared to other 3 stocks
in the cohort.

Therefore, we adopt the cumulative mispricing index framework. For each cohort we calculate the **de-meaned** cumulative sum
of $h$ as $CMPI$, and formulate the trading signal using a Bollinger band:
Denote the running average of $CMPI$ in the fixed-length, moving time window as $\hat{\mu}(t)$, the running
standard deviation in the time window as $\hat{\sigma}(t)$, and some positive constant $k$ to control the
Bollinger band’s width.

Short signal: When $CMPI > \hat{\mu}(t) + k \hat{\sigma}(t)$.

Long signal: When $CMPI < \hat{\mu}(t) - k \hat{\sigma}(t)$.

Exit signal: When $CMPI$ crosses with $\hat{\mu}(t)$.

Do nothing: Else.

Now we total net positions for each key stock in each cohort. Then we formulate our dollar-neutral strategy by trading
against a cheap broad-based market index such as SPY, similar to the method used in [Avellaneda and Lee, 2010].

Note

It is totally possible that different cohorts can share the same key stock. The cohort and key stock information
is generated from the stocks cohort selection methods.

It is no surprise that $CMPI$ looks reasonably similar to cumulative log-returns of the target stock. This can be
used as a sanity check on whether our vine copula model is off.


## Comments


Vine copula provides a very flexible approach in modeling multi-variate dependencies. The C-vine structure specifically
highlights a dominant component at every level of the tree, ideal for our “1-vs-the rest” trading strategy for capturing
statistical arbitrage among multiple stocks, which non-quant strategies often omit or are still primative.

As promising as it looks, just like any other methods it inevitably bears the some drawbacks:

High start-up cost: to understand this method, the user needs to understand copula modeling from scratch, and
also how to interprete vine copula models from end to end.

High computation cost: For a cohort of 4 stocks and 3 years of daily training data + 1 year of test data, it takes about
30 seconds to fit and generate positions. This can hardly be optimized further since the fitting algorithm is already
written in an optimized C++ library. And the compuation time should scale up in $O(N!)$. This is just for fitting and
generating positions without factoring into the time for stocks selection.

Interpretability: Since the exact fitting algorithms are quite complicated, the interpretability may suffer in
back tracking possible fitting issues and how to evaluate each fits. Also the high dimension makes it difficult
to produce an intuitive plot just to visually check if the model is correct, unlike bivariate copulas.


## Implementation



## Example



## Research Notebooks


The following research notebook can be used to better understand the C-Vine copula strategy.


## Research Article



## Presentation Slides



## References

### Key Formulas Summary

1. Conditional probability definition: $h(u_1 | u_2, u_3, u_4) = \mathbb{P}(U_1 \le u_1 | U_2=u_2, U_3=u_3, U_4=u_4)$ where $h$ is the conditional probability of stock 1's quantile $u_1$ given the quantiles of other stocks $u_2, u_3, u_4$.
2. Numerical integration for conditional probability: $h(u_1 | u_2, u_3, u_4) = \left( \int_0^{u_1} f(u, u_2, u_3, u_4) du \right) / \left( \int_0^{1} f(u, u_2, u_3, u_4) du \right)$ where $f$ is the joint probability density function of the pseudo-observations $(u, u_2, u_3, u_4)$.
3. Short signal rule: $CMPI > \hat{\mu}(t) + k \hat{\sigma}(t)$ where $CMPI$ is the de-meaned cumulative sum of $h$, $\hat{\mu}(t)$ is the running average of $CMPI$, $\hat{\sigma}(t)$ is the running standard deviation of $CMPI$, and $k$ is a positive constant for Bollinger band width.
4. Long signal rule: $CMPI < \hat{\mu}(t) - k \hat{\sigma}(t)$ where $CMPI$ is the de-meaned cumulative sum of $h$, $\hat{\mu}(t)$ is the running average of $CMPI$, $\hat{\sigma}(t)$ is the running standard deviation of $CMPI$, and $k$ is a positive constant for Bollinger band width.

### References

Stübinger, J., Mangold, B. and Krauss, C. (2018) - Statistical arbitrage with vine copulas
Joe, H. and Kurowicka, D. eds. (2011) - Dependence modeling: vine copula handbook
Yu, R., Yang, R., Zhang, C., Špoljar, M., Kuczyńska-Kippen, N. and Sang, G. (2020) - A Vine Copula-Based Modeling for Identification of Multivariate Water Pollution Risk in an Interconnected River System Network
Dissmann, J., Brechmann, E.C., Czado, C. and Kurowicka, D. (2013) - Selecting and estimating regular vine copulae and application to financial returns
Avellaneda, M. and Lee, J.H. (2010) - Statistical arbitrage in the US equities market

---

## 14. Copula-Based Metrics

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/codependence_marti.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/codependence_marti.html)

The document introduces a new approach to representing random variables that separates dependency and distribution. It also presents a distance metric between two financial time series.

**Spearman's Rho**

Spearman's rho is a copula-based dependence measure, more robust than Pearson correlation coefficient. It is defined as:

$$\rho_{S}(X, Y) = 12 E[F_{X}(X), F_{Y}(Y)] - 3 \\ = \rho(F_{X}(X), F_{Y}(Y))$$

And its statistical estimate is:

$$\hat{\rho}_{S}(X, Y) = 1 - \frac{6}{T(T^2-1)}\sum_{t=1}^{T}(X^{(t)}- Y^{(t)})^2$$

Where:
*   $X$ and $Y$ are univariate random variables.
*   $F_{X}(X)$ is the cumulative distribution function of $X$.
*   $X^{(t)}$ is the $t$-th sorted observation of $X$.
*   $T$ is the total number of observations.

**Generic Parametric Representation (GPR) distance**

Marti defines the distance $d_{\Theta}$ between two random variables as:

Let $\theta \in [0, 1]$. Let $(X, Y) \in \nu^{2}$, where $\nu$ is the space of all continuous real-valued random variables. Let $G = (G_{X}, G_{Y})$, where $G_{X}$ and $G_{Y}$ are respectively $X$ and $Y$ marginal cdfs. We define the following distance:

$$d_{\Theta}^{2}(X, Y) = \Theta d_{1}^{2}(G_{X}(X), G_{Y}(Y)) + (1 - \Theta) d_{0}^{2}(G_{X}, G_{Y})$$

Where:

$$d_{1}^{2}(G_{X}(X), G_{Y}(Y)) = 3 \mathbb{E}[|G_{X}(X) - G_{Y}(Y)|^{2}]$$

And:

$$d_{0}^{2}(G_{X}, G_{Y}) = \frac{1}{2} \int_{R} (\sqrt{\frac{d G_{X}}{d \lambda}} - \sqrt{\frac{d G_{Y}}{d \lambda}})^{2} d \lambda$$

For two Gaussian random variables, the distance $d_{\Theta}$ is defined as:

Let $(X, Y)$ be a bivariate Gaussian vector, with $X \sim \mathcal{N}(\mu_{X}, \sigma_{X}^{2})$, $Y \sim \mathcal{N}(\mu_{Y}, \sigma_{Y}^{2})$ and $\rho (X,Y)$. We obtain:

$$d_{\Theta}^{2}(X, Y) = \Theta \frac{1 - \rho_{S}}{2} + (1 - \Theta) (1 - \sqrt{\frac{2 \sigma_{X} \sigma_{Y}}{\sigma_{X}^{2} + \sigma_{Y}^{2}}} e^{ - \frac{1}{4} \frac{(\mu_{X} - \mu_{Y})^{2}}{\sigma_{X}^{2} + \sigma_{Y}^{2}}})$$

**Generic Non-Parametric Representation (GNPR) distance**

The statistical estimate of the distance $\tilde{d}_{\Theta}$ working on realizations of the i.i.d. random variables is defined as:

Let $(X^{t})_{t=1}^{T}$ and $(Y^{t})_{t=1}^{T}$ be $T$ realizations of real-valued random variables $X, Y \in \nu$ respectively. An empirical distance between realizations of random variables can be defined by:

$$\tilde{d}_{\Theta}^{2}((X^{t})_{t=1}^{T}, (Y^{t})_{t=1}^{T}) \stackrel{\text{a.s.}}{=} \Theta \tilde{d}_{1}^{2} + (1 - \Theta) \tilde{d}_{0}^{2}$$

Where:

$$\tilde{d}_{1}^{2} = \frac{3}{T(T^{2} - 1)} \sum_{t = 1}^{T} (X^{(t)} - Y^{(t)}) ^ {2}$$

And:

$$\tilde{d}_{0}^{2} = \frac{1}{2} \sum_{k = - \infty}^{+ \infty} (\sqrt{g_{X}^{h}(hk)} - \sqrt{g_{Y}^{h}(hk)})^{2}$$

Where $h$ is a suitable bandwidth, and $g_{X}^{h}(x) = \frac{1}{T} \sum_{t = 1}^{T} \mathbf{1}(\lfloor \frac{x}{h} \rfloor h \le X^{t} < (\lfloor \frac{x}{h} \rfloor + 1)h)$ is a density histogram estimating dpf $g_{X}$ from $(X^{t})_{t=1}^{T}$, $T$ realization of a random variable $X \in \nu$.

For the GNPR implementation in ArbitrageLab, $\tilde{d}_{0}^{2}$ (dependence information distance) is calculated using the 1D Optimal Transport Distance:

$$\tilde{d}_{0}^{2} = tr (OT^{T} \* M)$$

Where $tr( \cdot )$ is the trace of a matrix and $\cdot^{T}$ is a transposed matrix. $OT$ is the Optimal Transportation Matrix and $M$ is the Loss Matrix.

**Optimization of $\Theta$**

To use $d_{\Theta}$ and its statistical estimate effectively, a particular value for $\Theta$ must be selected. The document suggests an exploratory approach where one can test:
1.  Distribution information ($\Theta = 0$)
2.  Dependence information ($\Theta = 1$)
3.  A mix of both information ($\Theta = 0.5$)

In a supervised setting, $\hat{\Theta}$ could be selected by optimizing a loss function using techniques like cross-validation. However, the lack of a clear loss function makes the estimation of $\Theta^{\*}$ difficult in an unsupervised setting.

**Code Examples**

Python code demonstrating the usage of these metrics:

```python
import pandas as pd
from arbitragelab.codependence import (spearmans_rho, gpr_distance, gnpr_distance,
                                       get_dependence_matrix)

data = pd.read_csv(\'X_FILE_PATH.csv\', index_col=0, parse_dates = [0])

element_x = \'SPY\'
element_y = \'TLT\'

rho = spearmans_rho(data[element_x], data[element_y])
gpr_dist = gpr_distance(data[element_x], data[element_y], theta=0.5)
gnpr_dist = gnpr_distance(data[element_x], data[element_y], theta=1)
gnpr_matrix = get_dependence_matrix(data, dependence_method=\'gnpr_distance\',
                                    theta=0.5)
```

### Key Formulas Summary

1.  **Spearman's Rho (Statistical Estimate)**: $\hat{\rho}_{S}(X, Y) = 1 - \frac{6}{T(T^2-1)}\sum_{t=1}^{T}(X^{(t)}- Y^{(t)})^2$
    *   $X, Y$: univariate random variables
    *   $X^{(t)}$: $t$-th sorted observation of $X$
    *   $T$: total number of observations

2.  **Generic Parametric Representation (GPR) Distance**: $d_{\Theta}^{2}(X, Y) = \Theta d_{1}^{2}(G_{X}(X), G_{Y}(Y)) + (1 - \Theta) d_{0}^{2}(G_{X}, G_{Y})$
    *   $\Theta \in [0, 1]$: weighting parameter
    *   $G_{X}, G_{Y}$: marginal cumulative distribution functions of $X, Y$
    *   $d_{1}^{2}$: dependence distance component
    *   $d_{0}^{2}$: distributional distance component

3.  **GPR Distance for Gaussian Variables**: $d_{\Theta}^{2}(X, Y) = \Theta \frac{1 - \rho_{S}}{2} + (1 - \Theta) (1 - \sqrt{\frac{2 \sigma_{X} \sigma_{Y}}{\sigma_{X}^{2} + \sigma_{Y}^{2}}} e^{ - \frac{1}{4} \frac{(\mu_{X} - \mu_{Y})^{2}}{\sigma_{X}^{2} + \sigma_{Y}^{2}}})$
    *   $\mu_{X}, \mu_{Y}$: means of $X, Y$
    *   $\sigma_{X}^{2}, \sigma_{Y}^{2}$: variances of $X, Y$
    *   $\rho_{S}$: Spearman's Rho

4.  **Generic Non-Parametric Representation (GNPR) Distance (Empirical)**: $\tilde{d}_{\Theta}^{2}((X^{t})_{t=1}^{T}, (Y^{t})_{t=1}^{T}) \stackrel{\text{a.s.}}{=} \Theta \tilde{d}_{1}^{2} + (1 - \Theta) \tilde{d}_{0}^{2}$
    *   $(X^{t})_{t=1}^{T}, (Y^{t})_{t=1}^{T}$: $T$ realizations of $X, Y$
    *   $\tilde{d}_{1}^{2}$: empirical dependence distance component
    *   $\tilde{d}_{0}^{2}$: empirical distributional distance component

5.  **GNPR Distributional Distance (Optimal Transport)**: $\tilde{d}_{0}^{2} = tr (OT^{T} \* M)$
    *   $tr(\cdot)$: trace of a matrix
    *   $OT$: Optimal Transportation Matrix
    *   $M$: Loss Matrix

### References

Marti, G., 2017. Some contributions to the clustering of financial time series and applications to credit default swaps (Doctoral dissertation, Université Paris-Saclay (ComUE)).
Marti Gautier, 2020. Measuring non-linear dependence with Optimal Transport. Available at personal blog.

---

# Copula, Pairs Trading

## 15. Mispricing Index Copula Trading Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/mispricing_index_strategy.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/mispricing_index_strategy.html)

The **Mispricing Index Copula Trading Strategy** (MPI Strategy) is a quantitative trading strategy that utilizes copulas to identify mispricing between pairs of stocks. It builds upon the basic copula strategy by addressing the non-stationarity of price series by working with returns.

### Mispricing Index (MPI)

The **Mispricing Index (MPI)** is defined as the conditional probability of returns. For a pair of stocks $(X, Y)$ with returns random variables $(R_t^X, R_t^Y)$ and realized returns values $(r_t^X, r_t^Y)$ at day $t$, the MPIs are given by:

$MI_t^{X|Y} = P(R_t^X < r_t^X | R_t^Y = r_t^Y)$

$MI_t^{Y|X} = P(R_t^Y < r_t^Y | R_t^X = r_t^X)$

These two values indicate how mispriced each stock is based on that day's return.

### Flag and Raw Flag

To cumulatively use returns to gauge mispricing, the concept of a **flag** series is introduced. The **raw flag** series (denoted with a star) is the cumulative sum of daily MPIs minus 0.5. The recursive definition is:

$FlagX^*(t) = FlagX^*(t-1) + (MI_t^{X|Y} - 0.5)$, with $FlagX^*(0) = 0$.

$FlagY^*(t) = FlagY^*(t-1) + (MI_t^{Y|X} - 0.5)$, with $FlagY^*(0) = 0$.

Equivalently, the raw flag series can be expressed as a summation:

$FlagX^*(t) = \sum_{s=0}^t (MI_s^{X|Y} - 0.5)$

$FlagY^*(t) = \sum_{s=0}^t (MI_s^{Y|X} - 0.5)$

The **real flag** series (without a star, $FlagX(t)$, $FlagY(t)$) is similar to the raw flag series but is reset to 0 whenever an exiting signal occurs.

### Trading Logic

The strategy proposes a **dollar-neutral** trade scheme. Let $D$ be the opening trigger threshold (e.g., $D = 0.6$ as in the paper) and $S$ be the stop-loss position (e.g., $S = 2$ as in the paper).

**Opening Rules:**

*   When $FlagX$ reaches $D$, short stock $X$ and buy stock $Y$ in equal amounts (Position: -1).
*   When $FlagX$ reaches $-D$, short stock $Y$ and buy stock $X$ in equal amounts (Position: 1).
*   When $FlagY$ reaches $D$, short stock $Y$ and buy stock $X$ in equal amounts (Position: 1).
*   When $FlagY$ reaches $-D$, short stock $X$ and buy stock $Y$ in equal amounts (Position: -1).

**Exiting Rules:**

*   If trades were opened based on $FlagX$, they are closed if $FlagX$ returns to zero or reaches stop-loss position $S$ or $-S$.
*   If trades were opened based on $FlagY$, they are closed if $FlagY$ returns to zero or reaches stop-loss position $S$ or $-S$.
*   After trades are closed, both $FlagX$ and $FlagY$ are reset to $0$.

### Ambiguities and Resolutions

The original paper did not specify behavior for certain ambiguous situations. The ArbitrageLab implementation resolves these as follows:

1.  **Simultaneous triggers:** If $FlagX$ reaches $D$ (or $-D$) and $FlagY$ reaches $D$ (or $-D$) together, do nothing.
2.  **Opposite triggers while in position:** If in a long position, and a short trigger is received, the position changes to short.
3.  **Simultaneous opening and exiting signals:** Prioritize the exiting signal.
4.  **Cross-flag stop-loss:** If a position was opened based on $FlagX$ (or $FlagY$), and the other flag ($FlagY$ or $FlagX$) reaches $S$ or $-S$, do nothing.

### Open and Exit Logic Choices

The default logic in the original paper is an OR-OR logic for opening and exiting (at least one condition satisfied triggers the action). However, other combinations are possible:

*   **OR-OR:** Default, as suggested by Xie et al. 2014.
*   **AND-OR:** Suggested by Rad et al. 2016, where all opening conditions must be met, but only one exiting condition is needed. This is generally found to be more robust.

These rules can be configured in the `get_positions_and_flags` method by setting `open_rule` and `exit_rule` parameters (e.g., `open_rule='and'`, `exit_rule='or'`).

### Implementation Example (Python Code Snippets)

The strategy is implemented in the `MPICopulaTradingRule` module. Key steps include:

1.  **Instantiation:**
    ```python
    CSMPI = MPICopulaTradingRule(opening_triggers=(-0.6, 0.6), stop_loss_positions=(-2, 2))
    ```
2.  **Data Preparation:** Convert prices to returns.
    ```python
    returns = CSMPI.to_returns(prices)
    ```
3.  **Copula Fitting and CDF Construction:** A copula (e.g., N14 Archimedean copula) is set, and empirical cumulative distribution functions (ECDFs) for the returns are constructed.
    ```python
    cop = N14(theta=2)
    CSMPI.set_copula(cop)
    cdf_x = construct_ecdf_lin(returns['BKD'])
    cdf_y = construct_ecdf_lin(returns['ESC'])
    CSMPI.set_cdf(cdf_x, cdf_y)
    ```
4.  **Position and Flag Generation:**
    ```python
    positions, flags = CSMPI.get_positions_and_flags(returns=returns_test)
    # Example with AND-OR logic:
    positions_and_or, flags_and_or = CSMPI.get_positions_and_flags(returns=returns_test,
                                                                   open_rule='and',
                                                                   exit_rule='or')
    ```
5.  **Unit Calculation for Dollar-Neutral Strategy:**
    ```python
    units = CSMPI.positions_to_units_dollar_neutral(prices_df=prices_test,
                                                    positions=positions,
                                                    multiplier=10000)
    ```

### Key Formulas Summary

1. Mispricing Index for stock X given Y: $MI_t^{X|Y} = P(R_t^X < r_t^X | R_t^Y = r_t^Y)$
   - $R_t^X, R_t^Y$: Returns random variables for stock X and Y at day $t$.
   - $r_t^X, r_t^Y$: Realized returns values for stock X and Y at day $t$.
2. Mispricing Index for stock Y given X: $MI_t^{Y|X} = P(R_t^Y < r_t^Y | R_t^X = r_t^X)$
   - $R_t^X, R_t^Y$: Returns random variables for stock X and Y at day $t$.
   - $r_t^X, r_t^Y$: Realized returns values for stock X and Y at day $t$.
3. Raw Flag Series for stock X: $FlagX^*(t) = FlagX^*(t-1) + (MI_t^{X|Y} - 0.5)$, with $FlagX^*(0) = 0$.
   - $FlagX^*(t)$: Raw flag series for stock X at time $t$.
   - $MI_t^{X|Y}$: Mispricing Index for stock X given Y at time $t$.
4. Raw Flag Series for stock Y: $FlagY^*(t) = FlagY^*(t-1) + (MI_t^{Y|X} - 0.5)$, with $FlagY^*(0) = 0$.
   - $FlagY^*(t)$: Raw flag series for stock Y at time $t$.
   - $MI_t^{Y|X}$: Mispricing Index for stock Y given X at time $t$.
5. Cumulative Raw Flag Series for stock X: $FlagX^*(t) = \sum_{s=0}^t (MI_s^{X|Y} - 0.5)$
   - $FlagX^*(t)$: Raw flag series for stock X at time $t$.
   - $MI_s^{X|Y}$: Mispricing Index for stock X given Y at time $s$.

### References

Xie, W., Liew, R.Q., Wu, Y. and Zou, X. (2014) - Pairs trading with copulas.
Rad, H., Low, R.K.Y. and Faff, R. (2016) - The profitability of pairs trading strategies: distance, cointegration and copula methods.
Liew et al. (2013) - (Cited in text, full title not provided on page)

---

# Codependence Measures, Copulas, Optimal Transport

## 16. Optimal Copula Transport Dependence

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/optimal_transport.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/optimal_transport.html)

The core idea of Optimal Copula Transport dependence revolves around leveraging copulas and a geometrical perspective to measure dependence between random variables. Dependence is quantified as the relative distance from independence to target dependencies like comonotonicity or countermonotonicity.

**Theorem 1 (Sklar’s Theorem)**
Let $X = (X_i, X_j)$ be a random vector with a joint cumulative distribution function $F$, and having continuous marginal cumulative distribution functions $F_i, F_j$ respectively. Then, there exists a unique distribution $C$ such that:

$F(X_i, X_j) = C(F_i(X_i), F_j(X_j))$

$C$, the copula of $X$, is the bivariate distribution of uniform marginals $U_i, U_j := F_i(X_i), F_j(X_j)$.

**Proposition 1 (Frechet-Hoeffding copula bounds)**
For any copula $C: [0, 1]^2 \rightarrow [0, 1]$ and any $(u_i, u_j) \in [0, 1]^2$ the following bounds hold:

$\mathcal{W} (u_i, u_j) \le C(u_i, u_j) \le \mathcal{M} (u_i, u_j)$

where $\mathcal{W} (u_i, u_j) = \max \{u_i + u_j − 1, 0 \}$ is the copula for countermonotonic random variables and $\mathcal{M} (u_i, u_j) = \min \{ u_i, u_j \}$ is the copula for comonotonic random variables.

**Definition 1 (Empirical Copula Transform)**
Let $(X^t_i, X^t_j), t = 1, ..., T$, be $T$ observations from a random vector $(X_i, X_j)$ with continuous margins. Since one cannot directly obtain the corresponding copula observations $(U^t_i, U^t_j) := (F_i(X^t_i), F_j(X^t_j))$, where $t = 1, ..., T$, without knowing a priori $F_i$, one can instead estimate the empirical margins:

$F^T_i(x) = \frac{1}{T} \sum^T_{t=1} I(X^t_i \le x)$

to obtain the $T$ empirical observations $(\widetilde{U}^t_i, \widetilde{U}^t_j) := (F^T_i(X^t_i), F^T_j(X^t_j))$. Equivalently, since $U^t_i = R^t_i / T$, $R^t_i$ being the rank of observation $X^t_i$, the empirical copula transform can be considered as the normalized rank transform.

**Definition 2 (Optimal Transport)**
Given a $m \times m$ cost matrix $M$, the cost of mapping $r$ to $c$ using a transportation matrix $P$ can be quantified as $\langle P, M \rangle_F$, where $\langle ·, ·\rangle_F$ is the Frobenius dot-product. The optimal transport between $r$ and $c$ given transportation cost $M$ is thus:

$d_M(r, c) := \min_{P \in U (r, c)} \langle P, M \rangle_F$

where $r, c$ are two histograms in the probability simplex $\sum_m = \{x \in R^m_+ : x^T 1_m = 1\}$ and $U(r, c) = \{ P \in R^{m \times m}_+ | P1_m = r, P^T 1_m = c\}$ is the transportation polytope of $r$ and $c$.

**Definition 3 (Target/Forget Dependence Coefficient)**
Let $\{C^−_l\}_l$ be the set of forget-dependence copulas. Let $\{C^+_k\}_k$ be the set of target-dependence copulas. Let $C$ be the copula of $(X_i, X_j)$. Let $d_M$ be an optimal transport distance parameterized by a ground metric $M$. We define the Target/Forget Dependence Coefficient as:

$TFDC(X_i, X_j; \{C^+_k\}_k, \{C^−_l\}_l) := \frac{\min_l d_M(C^−_l, C)}{\min_l d_M(C^−_l, C) + \min_k d_M(C, C^+_k)} \in [0, 1]$

Using this definition, we obtain:

$TFDC (X_i, X_j; \{C^+_k\}_k, \{C^−_l\}_l) = 0 \Leftrightarrow C \in \{C^−_l\}_l$

$TFDC(X_i ,X_j; \{C^+_k\}_k, \{C^−_l\}_l) = 1 \Leftrightarrow C \in \{C^+_k\}_k$

### Key Formulas Summary

1. **Sklar's Theorem**: $F(X_i, X_j) = C(F_i(X_i), F_j(X_j))$, where $F$ is the joint CDF, $F_i, F_j$ are marginal CDFs, and $C$ is the copula of $X$.
2. **Frechet-Hoeffding Copula Bounds**: $\mathcal{W} (u_i, u_j) \le C(u_i, u_j) \le \mathcal{M} (u_i, u_j)$, where $\mathcal{W} (u_i, u_j) = \max \{u_i + u_j − 1, 0 \}$ (countermonotonic) and $\mathcal{M} (u_i, u_j) = \min \{ u_i, u_j \}$ (comonotonic).
3. **Empirical Margins**: $F^T_i(x) = \frac{1}{T} \sum^T_{t=1} I(X^t_i \le x)$, used to estimate uniform marginals for empirical copula transform.
4. **Optimal Transport Distance**: $d_M(r, c) := \min_{P \in U (r, c)} \langle P, M \rangle_F$, where $M$ is the cost matrix, $r, c$ are histograms, and $U(r, c)$ is the transportation polytope.
5. **Target/Forget Dependence Coefficient (TFDC)**: $TFDC(X_i, X_j; \{C^+_k\}_k, \{C^−_l\}_l) := \frac{\min_l d_M(C^−_l, C)}{\min_l d_M(C^−_l, C) + \min_k d_M(C, C^+_k)}$, which measures dependence based on distances to target and forget copulas.

### References

Marti, G., Andler, S., Nielsen, F. and Donnat, P. (2017) - Exploring and measuring non-linear correlations: Copulas, Lightspeed Transportation and Clustering
Marti Gautier (2020) - Measuring non-linear dependence with Optimal Transport

---

# Copula

## 17. Vine Copula Partner Selection

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/partner_selection.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/copula_approach/partner_selection.html)

This module implements four partner selection approaches for multivariate statistical arbitrage strategies based on vine copulas. The approaches are Traditional, Extended, Geometric, and Extremal. All measures of association are calculated using the ranks of daily discrete returns, providing robustness against outliers.

### Extended Approach

This approach generalizes Spearman’s $\rho$ to arbitrary dimensions. For $d$ stocks with daily returns $X_i$ observed from day $1$ to day $n$, the empirical cumulative density function (ECDF) $\hat{F}_i$ for stock $i$ is calculated. Quantile data for each $X_i$ is then obtained by:

$$\hat{U}_i = \frac{1}{n} (\text{rank of } X_i) = \hat{F}_i(X_i)$$

The formula for the three estimators of multivariate Spearman's $\rho$ are:

$$\begin{align*}
\hat{\rho}_1 &= h(d) \times \Bigg\{-1 + \frac{2^d}{n} \sum_{j=1}^n \prod_{i=1}^d (1 - \hat{U}_{ij}) \Bigg\}\\
\hat{\rho}_2 &= h(d) \times \Bigg\{-1 + \frac{2^d}{n} \sum_{j=1}^n \prod_{i=1}^d \hat{U}_{ij} \Bigg\}\\
\hat{\rho}_3 &= -3 + \frac{12}{n {d \choose 2}} \times \sum_{k<l} \sum_{j=1}^n (1-\hat{U}_{kj})(1-\hat{U}_{lj})
\end{align*}$$

Where $h(d)$ is defined as:

$$h(d) = \frac{d+1}{2^d - d -1}$$

The final measure is the mean of these three estimators.

### Geometric Approach

This approach measures the geometric relation between stocks in a quadruple by calculating the sum of Euclidean distances from the 4-dimensional hyper-diagonal. The diagonal measure in four-dimensional space is calculated using the following equation:

$$\sum_{i=1}^{n} | (P - P_{1}) - \frac{(P - P_{1}) \cdot (P_{2} - P_{1})}{| P_{2} -P_{1} |^{2}} (P_{2} - P_{1}) |$$

Where:
*   $P_1 = (0,0,0,0)$ and $P_2 = (1,1,1,1)$ are points on the hyper-diagonal.
*   $P = (u_1,u_2,u_3,u_4)$ where $u_i$ represents the ranked returns of stock $i$ in the quadruple.

### Extremal Approach

This approach uses a nonparametric test for multivariate independence based on Mangold (2015). The resulting $\chi^2$ test statistic measures the degree of deviation from independence. The steps to calculate the $\chi^2$ test statistic for a 4-dimensional input are:

1.  **4-dimensional Nelsen copula**: Analytically calculate the 4-dimensional Nelsen copula $C_{\theta}(u_1, u_2, u_3, u_4)$ from Definition 2.4 in Mangold (2015):

    $$\begin{align*} C_{\theta}(u_1, u_2, u_3, u_4) = u_1u_2u_3u_4 \times (1 + ((1- u_1)(1- u_2)(1- u_3)(1- u_4)) \times \\ &(\theta_1 ((1- u_1)(1- u_2)(1- u_3)(1- u_4)) + \theta_2 ((1- u_1)(1- u_2)(1- u_3)u_4) + \\ &\theta_3 ((1- u_1)(1- u_2)u_3(1- u_4)) + \theta_4 ((1- u_1)(1- u_2)u_3u_4) + \\ &\theta_5 ((1- u_1)u_2(1- u_3)(1- u_4)) + \theta_6 ((1- u_1)u_2(1- u_3)u_4) + \\ &\theta_7 ((1- u_1)u_2u_3(1- u_4)) + \theta_8 ((1- u_1)u_2u_3u_4) + \\ &\theta_9 (u_1(1- u_2)(1- u_3)(1- u_4)) + \theta_{10} (u_1(1- u_2)(1- u_3)u_4) + \\ &\theta_{11} (u_1(1- u_2)u_3(1- u_4)) + \theta_{12} (u_1(1- u_2)u_3u_4) + \\ &\theta_{13} (u_1u_2(1- u_3)(1- u_4)) + \theta_{14} (u_1u_2(1- u_3)u_4) + \\ &\theta_{15} (u_1(1- u_2)u_3(1- u_4)) + \theta_{16} (u_1u_2u_3u_4) )) \end{align*}$$

    Where $\theta_1, \theta_2, ..., \theta_{16}$ are parameters involved in the copula formula.

2.  **Density function**: Analytically calculate the corresponding density function of the 4-dimensional copula:

    $$c_{\theta}(u_1, u_2, u_3, u_4) = \frac{\partial^{4}}{\partial u_1 \partial u_2 \partial u_3\partial u_4}C_{\theta}(u_1, u_2, u_3, u_4)$$

    The form of each $u_i$ beside $\theta_i$ is either $u_i(1- u_i)^2$ or $u_i^2(1 - u_i)$, and their corresponding partial derivatives are $(u_i - 1)(3u_i - 1)$ or $u_i(2 - 3u_i)$ respectively.

3.  **Partial Derivative of density function**: Calculate the partial derivative of the density function with respect to $\theta$:

    $$\dot{c_{\theta}} = \frac{\partial c_{\theta}(u_1, u_2, u_3, u_4)}{\partial \theta}$$

4.  **Test Statistic**: Calculate the Test Statistic for p-dimensional rank test:

    $$T=n \boldsymbol{T}_{p, n}^{\prime} \Sigma\left(\dot{c}_{\theta_{0}}\right)^{-1} \boldsymbol{T}_{p, n} \stackrel{a}{\sim} \chi^{2}(q)$$

    Where:

    $$\boldsymbol{T}_{p, n}=\mathbb{E}\left[\left.\frac{\partial}{\partial \theta} \log c_{\theta}(B)\right|_{\theta=\theta_{0}}\right]$$

    $$\Sigma\left(\dot{c}_{0}\right)_{i, j}=\int_{\[0,1\]^{p}}\left(\left.\frac{\partial c_{\theta}(\boldsymbol{u})} {\partial \theta_{i}}\right| \_{\boldsymbol{\theta}=\mathbf{0}}\right) \times\left(\left.\frac{\partial c_{\theta}(\boldsymbol{u})} {\partial \theta_{j}}\right |_{\theta=0}\right) \mathrm{d} \boldsymbol{u}$$

### Code Example

The document provides Python code snippets for implementing these approaches using the `arbitragelab` library:

```python
from arbitragelab.copula_approach.vine_copula_partner_selection import PartnerSelection
import pandas as pd

df = pd.read_csv(DATA_PATH, parse_dates=True, index_col='Date').dropna()

ps = PartnerSelection(df)

# Traditional Approach
Q = ps.traditional(20)
print(Q)
ps.plot_selected_pairs(Q)

# Extended Approach
Q = ps.extended(20)
print(Q)
ps.plot_selected_pairs(Q)

# Geometric Approach
Q = ps.geometric(20)
print(Q)
ps.plot_selected_pairs(Q)

# Extremal Approach
Q = ps.extremal(20)
print(Q)
ps.plot_selected_pairs(Q)
```

### Key Formulas Summary

1.  **Quantile Data for Extended Approach**: $\hat{U}_i = \frac{1}{n} (\text{rank of } X_i) = \hat{F}_i(X_i)$
    *   $\hat{U}_i$: Quantile data for stock $i$
    *   $n$: Number of daily returns observations
    *   $X_i$: $i$-th stock's return
    *   $\hat{F}_i$: Empirical cumulative density function for stock $i$

2.  **Multivariate Spearman's $\rho$ Estimator (Extended Approach)**: $\hat{\rho}_1 = h(d) \times \Bigg\{-1 + \frac{2^d}{n} \sum_{j=1}^n \prod_{i=1}^d (1 - \hat{U}_{ij}) \Bigg\}$
    *   $\hat{\rho}_1$: First estimator of multivariate Spearman's $\rho$
    *   $h(d)$: Scaling factor dependent on dimension $d$
    *   $d$: Number of stocks
    *   $n$: Number of observations
    *   $\hat{U}_{ij}$: Quantile data for stock $i$ at observation $j$

3.  **Geometric Diagonal Measure**: $\sum_{i=1}^{n} | (P - P_{1}) - \frac{(P - P_{1}) \cdot (P_{2} - P_{1})}{| P_{2} -P_{1} |^{2}} (P_{2} - P_{1}) |$
    *   $P$: Vector of ranked returns $(u_1,u_2,u_3,u_4)$
    *   $P_1 = (0,0,0,0)$, $P_2 = (1,1,1,1)$: Points on the hyper-diagonal

4.  **4-dimensional Nelsen Copula (Extremal Approach)**: $C_{\theta}(u_1, u_2, u_3, u_4) = u_1u_2u_3u_4 \times (1 + ((1- u_1)(1- u_2)(1- u_3)(1- u_4)) \times (\theta_1 ((1- u_1)(1- u_2)(1- u_3)(1- u_4)) + \dots + \theta_{16} (u_1u_2u_3u_4) ))$
    *   $C_{\theta}$: Nelsen copula
    *   $u_i$: Ranked returns of stock $i$
    *   $\theta_i$: Copula parameters

5.  **Test Statistic for p-dimensional rank test (Extremal Approach)**: $T=n \boldsymbol{T}_{p, n}^{\prime} \Sigma\left(\dot{c}_{\theta_{0}}\right)^{-1} \boldsymbol{T}_{p, n} \stackrel{a}{\sim} \chi^{2}(q)$
    *   $T$: Test statistic
    *   $n$: Number of observations
    *   $\boldsymbol{T}_{p, n}$: Expectation of the partial derivative of log-likelihood
    *   $\Sigma$: Covariance matrix
    *   $\dot{c}_{\theta_{0}}$: Partial derivative of the copula density function with respect to $\theta$ at $\theta_0$
    *   $\chi^{2}(q)$: Chi-squared distribution with $q$ degrees of freedom

### References

Stübinger, Johannes; Mangold, Benedikt; Krauss, Christopher; 2016. Statistical Arbitrage with Vine Copulas.
Schmid, F., Schmidt, R., 2007. Multivariate extensions of Spearman’s rho and related statis-tics. Statistics & Probability Letters 77 (4), 407–416.
Mangold, B., 2015. A multivariate linear rank test of independence based on a multipara-metric copula with cubic sections. IWQW Discussion Paper Series, University of Erlangen-N ̈urnberg.

---

# Stochastic Control Approach, Mean Reversion, Arbitrage

## 18. OU Model Jurek

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/ou_model_jurek.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/ou_model_jurek.html)

## Introduction
In the paper corresponding to this module, the authors derive the optimal dynamic strategy for arbitrageurs with a finite horizon and non-myopic preferences facing a mean-reverting arbitrage opportunity (e.g. an equity pairs trade).

## Modelling
In this module and the corresponding paper, $\kappa$ denotes the rate of mean reversion of the spread, $\mu$ denotes the long run mean and, $\sigma$ denotes the standard deviation of the spread.

To capture the presence of horizon and divergence risk, the authors model the dynamics of the mispricing using a mean-reverting stochastic process. The central assumption of our model is that the arbitrage opportunity is described by an Ornstein-Uhlenbeck process (henceforth OU).

### Investor Preferences
The authors considered two alternative preferences structures for the arbitrageur in our continuous-time model. In the first, the authors assumed that the agent has constant relative risk aversion and maximizes the discounted utility of terminal wealth. The arbitrageur’s value function at time $t$ - denoted by $V_t$ - takes the form:

$$V_{t}=\sup E_{t}\left[e^{-\beta(T-t)} \frac{W_{T}^{1-\gamma}}{1-\gamma}\right]$$

The second preference structure they considered is the recursive utility of Epstein and Zin (1989, 1991). Under this preference specification, the value function of the arbitrageur is given by:

$$V_{t}=\sup E_{t}\left[\int_{t}^{T} f\left(C_{s}, J_{s}\right) d s\right]$$

where $f\left(C_{s}, J_{s}\right)$ is the normalized aggregator for the continuous-time Epstein-Zin utility function:

$$f\left(C_{t}, J_{t}\right)=\beta(1-\gamma) \cdot J_{t} \cdot\left[\log C_{t}-\frac{1}{1-\gamma} \log \left((1-\gamma) J_{t}\right)\right]$$

Here the authors considered the special case of a unit elasticity of intertemporal substitution ($\psi = 1$).

Here $C_t$ denotes the instantaneous consumption (e.g. cash flow). $\beta$ is the rate of time preference, and $\gamma$ is the coefficient of relative risk aversion.

### Spread Construction
To construct the spread for the portfolio, firstly the authors calculated the total return index for each asset $i$ in the spread.

$$P_{i, t}=\left(\frac{1}{P_{i, 1}}\right) \cdot\left(P_{i, 1} \cdot \prod_{j=1}^{t-1}\left(1+R_{i, j+1}\right)\right)$$

The price spread is then constructed by taking a linear combination of the total return indices. These weights are estimated by using a co-integrating regression technique such as Engle Granger.

### Optimal Portfolio Strategy
The portfolio consists of a riskless asset and the mean reverting spread. The authors denote the prices of the two assets by $B_t$ and $S_t$, respectively. Their dynamics are given by,

$$\begin{split}\begin{aligned} d B_{t} &=r B_{t} d t \\ d S_{t} &=\kappa\left(\bar{S}-S_{t}\right) d t+\sigma d Z \end{aligned}\end{split}$$

The evolution of wealth which determines the budget constraints is written as,

$$d W_{t}=N_{t} d S_{t}+M_{t} d B_{t}-C_{t} 1\left[C_{t}>0\right] d t$$

where $N_t$ denotes the number of units of spread, $M_t$ denotes the number of riskless assets and, $1\left[C_{t}>0\right]$ is an indicator variable for whether intermediate consumption is taking place.

For the terminal wealth problem, the optimal portfolio allocation is given by:

$$\begin{split}N(W, S, \tau)=\left\{\begin{array}{cc} \left(\frac{\kappa(\bar{S}-S)-r S}{\sigma^{2}}\right) W & \gamma=1 \\ \left(\frac{\kappa(\bar{S}-S)-r S}{\gamma \sigma^{2}}+\frac{2 A(\tau) S+B(\tau)}{\gamma}\right) W & \gamma \neq 1 \end{array}\right.\end{split}$$

The functions $A(\tau)$ and $B(\tau)$ depend on the time remaining to the horizon and the parameters of the underlying model.

For the intermediate consumption problem, the optimal portfolio allocation has the same form as the corresponding equation for terminal wealth problem.

### Stabilization Region
To characterize the conditions under which arbitrageurs cease to trade against the mispricing, the authors derived precise, analytical conditions for the time-varying envelope within which arbitrageurs trade against the mispricing.

In the general case when $\bar{S} \neq 0$ the range of values of $S$ for which the arbitrageur’s response to an adverse shock is stabilizing - i.e. the agent trades against the spread, increasing his position as the spread widens - is determined by a time-varying envelope determined by both $A(\tau)$ and $B(\tau)$. The boundary of the stabilization region is determined by the following inequality:

$$\left| \phi(\tau) S+\frac{\kappa \bar{S}+\sigma^{2} B(\tau)}{\gamma \sigma^{2}}\right |<\sqrt{-\phi(\tau)}$$

where,

$$\phi(\tau) = \left(\frac{2 A(\tau)}{\gamma}-\frac{\kappa+r}{\gamma \sigma^{2}}\right)$$

As long as the spread is within the stabilization region, the improvement in investment opportunities from a divergence of the spread away from its long-run mean outweighs the negative wealth effect and the arbitrageur increases his position, $N$, in the mean-reverting asset. When the spread is outside of the stabilization region, the wealth effect dominates, leading the agent to curb his position despite an improvement in investment opportunities.

### Fund Flows
This section deals with the inclusion of fund flows. Delegated managers are not only exposed to the financial fluctuations of asset prices but also to their client’s desires to contribute or withdraw funds. Paradoxically, clients are most likely to withdraw funds after performance has been poor (i.e. spreads have been widening) and investment opportunities are the best.

### Key Formulas Summary

1. **CRRA Utility Value Function:** $V_{t}=\sup E_{t}\left[e^{-\beta(T-t)} \frac{W_{T}^{1-\gamma}}{1-\gamma}\right]$
   - $V_t$: Arbitrageur's value function at time $t$
   - $E_t$: Expectation at time $t$
   - $\beta$: Rate of time preference
   - $T$: Terminal time horizon
   - $W_T$: Wealth at terminal time $T$
   - $\gamma$: Coefficient of relative risk aversion

2. **Epstein-Zin Utility Value Function:** $V_{t}=\sup E_{t}\left[\int_{t}^{T} f\left(C_{s}, J_{s}\right) d s\right]$
   - $V_t$: Arbitrageur's value function at time $t$
   - $E_t$: Expectation at time $t$
   - $f(C_s, J_s)$: Normalized aggregator for continuous-time Epstein-Zin utility
   - $C_s$: Instantaneous consumption at time $s$
   - $J_s$: Value function at time $s$

3. **Epstein-Zin Normalized Aggregator:** $f\left(C_{t}, J_{t}\right)=\beta(1-\gamma) \cdot J_{t} \cdot\left[\log C_{t}-\frac{1}{1-\gamma} \log \left((1-\gamma) J_{t}\right)\right]$
   - $f(C_t, J_t)$: Normalized aggregator
   - $\beta$: Rate of time preference
   - $\gamma$: Coefficient of relative risk aversion
   - $C_t$: Instantaneous consumption at time $t$
   - $J_t$: Value function at time $t$

4. **Total Return Index:** $P_{i, t}=\left(\frac{1}{P_{i, 1}}\right) \cdot\left(P_{i, 1} \cdot \prod_{j=1}^{t-1}\left(1+R_{i, j+1}\right)\right)$
   - $P_{i,t}$: Total return index for asset $i$ at time $t$
   - $P_{i,1}$: Initial price of asset $i$
   - $R_{i,j+1}$: Return of asset $i$ at time $j+1$

5. **Spread Dynamics (Ornstein-Uhlenbeck Process):** $d S_{t} =\kappa\left(\bar{S}-S_{t}\right) d t+\sigma d Z$
   - $S_t$: Price of the spread at time $t$
   - $\kappa$: Rate of mean reversion of the spread
   - $\bar{S}$: Long-run mean of the spread
   - $\sigma$: Standard deviation of the spread
   - $dZ$: Wiener process increment

6. **Optimal Portfolio Allocation (for $\gamma \neq 1$):** $N(W, S, \tau) = \left(\frac{\kappa(\bar{S}-S)-r S}{\gamma \sigma^{2}}+\frac{2 A(\tau) S+B(\tau)}{\gamma}\right) W$
   - $N(W, S, \tau)$: Optimal allocation to the spread
   - $W$: Wealth
   - $S$: Spread value
   - $\tau$: Time remaining to the horizon
   - $\kappa$: Rate of mean reversion
   - $\bar{S}$: Long-run mean of the spread
   - $r$: Risk-free rate
   - $\sigma$: Standard deviation of the spread
   - $\gamma$: Coefficient of relative risk aversion
   - $A(\tau)$, $B(\tau)$: Functions depending on time to horizon and model parameters

7. **Stabilization Region Boundary:** $\left| \phi(\tau) S+\frac{\kappa \bar{S}+\sigma^{2} B(\tau)}{\gamma \sigma^{2}}\right |<\sqrt{-\phi(\tau)}$
   - $\phi(\tau)$: Defined as $\left(\frac{2 A(\tau)}{\gamma}-\frac{\kappa+r}{\gamma \sigma^{2}}\right)$
   - Other variables as defined above.

### References

Jurek, J.W. and Yang, H., 2007, April. Dynamic portfolio selection in arbitrage.

---

# OU Model, Stochastic Control, Pairs Trading

## 19. OU Model Mudchanatongsuk (Optimal Pairs Trading: A Stochastic Control Approach)

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/ou_model_mudchanatongsuk.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/stochastic_control_approach/ou_model_mudchanatongsuk.html)

## Modelling

In this module and the corresponding paper,

$k$ denotes the rate of mean reversion of the spread,

$\theta$ denotes the long run mean and,

$\eta$ denotes the standard deviation of the spread.

Let $A(t)$ and $B(t)$ denote respectively the prices of the pair of stocks $A$ and $B$ at time $t$. The authors assume that stock $B$ follows a geometric Brownian motion,

$$d B(t)=\mu B(t) d t+\sigma B(t) d Z(t)$$

where $\mu$ is the drift, $\sigma$ is the volatility, and $Z(t)$ is a standard Brownian motion.

Let $X(t)$ denote the spread of the two stocks at time $t$, defined as

$$X(t) = \ln(A(t)) - \ln(B(t))$$

The authors assume that the spread follows an Ornstein-Uhlenbeck process

$$d X(t)=k(\theta-X(t)) d t+\eta d W(t)$$

where $k$ is the rate of reversion, $\eta$ is the standard deviation and $\theta$ is the long-term equilibrium level to which the spread reverts.

$\rho$ denotes the instantaneous correlation coefficient between $Z(t)$ and $W(t)$.

Let $V(t)$ be the value of a self-financing pairs-trading portfolio and let $h(t)$ and $-h(t)$ denote respectively the portfolio weights for stocks $A$ and $B$ at time $t$.

The wealth dynamics of the portfolio value is given by,

$$d V(t)= V(t)\left\{ \left[h(t)\left(k(\theta-X(t))+\frac{1}{2} \eta^{2}+\rho \sigma \eta\right)+ r\right] d t+\eta d W(t)\right\}$$

Given below is the formulation of the portfolio optimization pair-trading problem as a stochastic optimal control problem. The authors assume that an investor’s preference can be represented by the utility function $U(x) = \frac{1}{\gamma} x^\gamma$ with $x \ge 0$ and $\gamma < 1$. In this formulation, our objective is to maximize expected utility at the final time $T$. Thus, the authors seek to solve

$$\begin{split}\begin{aligned} \sup \_{h(t)} \quad & E\left[\frac{1}{\gamma}(V(T))^\gamma\right] \\\\ \text { subject to: } \quad & V(0)=v_{0}, \quad X(0)=x_{0} \\\\ d X(t)=& k(\theta-X(t)) d t+\eta d W(t) \\\\ d V(t)=& V(t)((h(t)(k(\theta-X(t))+\frac{1}{2} \eta^{2}\\\\ &+\rho \sigma \eta)+r) d t+\eta d W(t)) \end{aligned}\end{split}$$

Finally, the optimal weights are given by,

$$h^{\*}(t, x)=\frac{1}{1-\gamma}\left[\beta(t)+2 x \alpha(t)-\frac{k(x-\theta)}{\eta^{2}}+ \frac{\rho \sigma}{\eta}+\frac{1}{2}\right]$$

### Step 1: Model fitting

We input the training data to the fit method which calculates the spread and the estimators of the parameters of the model.

#### Implementation

Although the paper provides closed form solutions for parameter estimation, this module uses log-likelihood maximization to estimate the parameters as we found the closed form solutions provided to be unstable.

### Key Formulas Summary

1. **Geometric Brownian Motion for Stock B:**
   $d B(t)=\mu B(t) d t+\sigma B(t) d Z(t)$
   where $B(t)$ is the price of stock B, $\mu$ is the drift, $\sigma$ is the volatility, and $Z(t)$ is a standard Brownian motion.

2. **Spread Definition:**
   $X(t) = \ln(A(t)) - \ln(B(t))$
   where $X(t)$ is the spread, $A(t)$ and $B(t)$ are the prices of stocks A and B respectively.

3. **Ornstein-Uhlenbeck Process for Spread:**
   $d X(t)=k(\theta-X(t)) d t+\eta d W(t)$
   where $k$ is the rate of reversion, $\theta$ is the long-term equilibrium level, $\eta$ is the standard deviation, and $W(t)$ is a Wiener process.

4. **Wealth Dynamics of the Portfolio:**
   $d V(t)= V(t)\left\{ \left[h(t)\left(k(\theta-X(t))+\frac{1}{2} \eta^{2}+\rho \sigma \eta\right)+ r\right] d t+\eta d W(t)\right\}$
   where $V(t)$ is the portfolio value, $h(t)$ are portfolio weights, $r$ is the risk-free rate, and $\rho$ is the correlation between $Z(t)$ and $W(t)$.

5. **Optimal Weights Formula:**
   $h^{\*}(t, x)=\frac{1}{1-\gamma}\left[\beta(t)+2 x \alpha(t)-\frac{k(x-\theta)}{\eta^{2}}+ \frac{\rho \sigma}{\eta}+\frac{1}{2}\right]$
   where $h^*(t,x)$ are the optimal weights, $\gamma$ is the utility function parameter, and $\alpha(t)$ and $\beta(t)$ are functions derived from the Hamilton-Jacobi-Bellman equation.

### References

Mudchanatongsuk, S., Primbs, J.A. and Wong, W., 2008, June. Optimal pairs trading: A stochastic control approach.

---

# Optimal Mean Reversion

## 20. Cox-Ingersoll-Ross (CIR) Model

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/cir_model.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/cir_model.html)

### Strategy Name and Description
**Strategy Name:** Trading Under the Cox-Ingersoll-Ross Model
**Description:** This strategy solves the optimal stopping problem for a mean-reverting portfolio constructed by holding a risky asset and shorting another. It models the portfolio value using a Cox-Ingersoll-Ross (CIR) process and finds the optimal timing of trades using optimal stopping and optimal switching approaches.

### Model Definition
The portfolio value is constructed by holding $\alpha = \frac{A}{S_0^{(1)}}$ of a risky asset $S^{(1)}$ and shorting $\beta = \frac{B}{S_0^{(2)}}$ of another risky asset $S^{(2)}$, yielding:
$$Y_t^{\alpha,\beta} = \alpha S^{(1)} - \beta S^{(2)}, t \geq 0$$
Setting $\alpha = const$ and $A = \$1$, we vary $\beta$ to find the optimal strategy $(\alpha,\beta^*)$.

The portfolio value follows a **Cox-Ingersoll-Ross (CIR) process** driven by the Stochastic Differential Equation (SDE):
$$dY_t = \mu(\theta - Y_t)dt + \sigma \sqrt{Y_t} dB_t$$
where:
- $\theta > 0$: long-term mean level.
- $\mu > 0$: speed of mean reversion.
- $\sigma > 0$: instantaneous volatility.
- $B_t$: a standard Brownian motion.

### Model Fitting
The parameters are estimated using Maximum Likelihood Estimation (MLE). The average log-likelihood function is defined as:
$$\ell (\theta,\mu,\sigma|y_0^{\alpha\beta},y_1^{\alpha\beta},\cdots,y_n^{\alpha\beta}) := \frac{1}{n}\sum_{i=1}^{n} \ln f^{CIR}(y_i|y_{i-1};\theta,\mu,\sigma)$$
$$= -\ln(\tilde{\sigma}) - \frac{1}{n\tilde{\sigma}}\sum_{i=1}^{n} [y_i +y_{i-1}e^{-\mu \Delta t}] - \frac{1}{n} \sum_{i=1}^{n} \left[\frac{q}{2}\ln\left(\frac{y_i}{y_{i-1}e^{-\mu\Delta t}}\right) - \ln I_q\left(\frac{2}{\tilde{\sigma}^2}\sqrt{y_i y_{i-1}e^{-\mu\Delta t}}\right) \right]$$
The optimal $\beta^*$ is chosen to maximize the log-likelihood:
$$\beta^* = \underset{\beta}{\arg\max}\ \hat{\ell}(\theta^*,\mu^*,\sigma^*|y_0^{\alpha\beta},y_1^{\alpha\beta},\cdots, y_n^{\alpha\beta})$$

### Optimal Stopping Problem
To maximize the expected discounted value of closing the position, the optimal stopping problem is:
$$V^{\chi}(y) = \underset{\tau \in T}{\sup} \mathbb{E}({e^{-r \tau} (Y_{\tau} - c_s)| Y_0 = y})$$
where $T$ is the set of all possible stopping times, $r > 0$ is the discount rate, and $c_s$ is the transaction cost for selling.

The optimal entry problem is formalized as:
$$J^{\chi}(y) = \underset{\nu \in T}{\sup} \mathbb{E}({e^{-\hat{r} \tau} (V^{\chi}(Y_{\nu}) - Y_{\nu} - c_b)| Y_0 = y})$$
where $\hat{r}>0$ and $c_b$ is the transaction cost for buying.

The CIR process infinitesimal generator is:
$$L = \frac{\sigma^2y}{2} \frac{d^2}{dy^2} + \mu(\theta - y) \frac{d}{dy}$$
The classical solution to the differential equation $L u(y) = ru(y)$ involves:
$$F^{\chi}(y) = M\left(\frac{r}{\mu},\frac{2\mu\theta}{\sigma^2},\frac{2\mu y}{\sigma^2}\right)$$
$$G^{\chi}(y) = U\left(\frac{r}{\mu},\frac{2\mu\theta}{\sigma^2},\frac{2\mu y}{\sigma^2}\right)$$
where $M(a,b,z)$ and $U(a,b,z)$ are confluent hypergeometric functions:
$$M(a,b,z) = \sum_{n=0}^{\infty}\frac{a_n z^n}{b_n n!},\ \ a_0=1, a_n=a(a+1)(a+2)...(a+n-1)$$
$$U(a,b,z) = \frac{\Gamma(1-b)}{\Gamma(a-b+1)}M(a,b,z) + \frac{\Gamma(b-1)}{\Gamma(a)}z^{1-b}M(a-b+1,2-b,z)$$

**Optimal Liquidation Solution:**
$$V^{\chi}(x) = \begin{cases} (b^{\chi*} - c_s) \frac{F^{\chi}(x)}{F^{\chi}(b^{\chi*})} , & \mbox{if } x \in [0,b^{\chi*})\\ x - c_s, & \mbox{ otherwise} \end{cases}$$
The optimal liquidation level $b^{\chi*}$ is found from:
$$F^{\chi} (b^{\chi}) - (b^{\chi} - c_s)F'^{\chi}(b^{\chi}) = 0$$
The optimal liquidation time is:
$$\tau^{\chi*} = \inf [t\geq0:Y_t \geq b^{\chi*}]$$

**Optimal Entry Solution:**
$$J(x) = \begin{cases} V^{\chi}(x) - x - c_b, & \mbox{if } x \in [0,d^{\chi*})\\ \frac{V^{\chi}(d^{\chi*}) - d^{\chi*} - c_b}{\hat{G^{\chi}}(d^{\chi*})}, & \mbox{if } x \in (d^{\chi*}, \infty) \end{cases}$$
The optimal entry level $d^{\chi*}$ is found from:
$$\hat{G}^{\chi}(d^{\chi})(V'^{\chi}(d^{\chi}) - 1) - \hat{G}'^{\chi}(d^{\chi})(V^{\chi}(d^{\chi}) - d^{\chi} - c_b) = 0$$

### Optimal Switching Problem
Two critical constants are defined:
$$y_s:=\frac{\mu\theta+rc_s}{\mu+r}$$
$$y_b:=\frac{\mu\theta-rc_b}{\mu+r}$$
It is optimal to re-enter the market if and only if:
1. $y_b > 0$
2. $c_b < \frac{b^{\chi*}-c_s}{F^{\chi}(b^{\chi*})}$

### Code Example
```python
import numpy as np
from arbitragelab.optimal_mean_reversion import CoxIngersollRoss

example = CoxIngersollRoss()
delta_t = 1/252
np.random.seed(30)
cir_example =  example.cir_model_simulation(n=1000, theta_given=0.2, mu_given=0.2,
                                            sigma_given=0.3, delta_t_given=delta_t)
example.fit(cir_example, data_frequency="D", discount_rate=0.05,
            transaction_cost=[0.001, 0.001])

b = example.optimal_liquidation_level()
d = example.optimal_entry_level()
d_switch, b_switch = example.optimal_switching_levels()
```

### Key Formulas Summary

1. **Cox-Ingersoll-Ross (CIR) Process SDE**:
   $$dY_t = \mu(\theta - Y_t)dt + \sigma \sqrt{Y_t} dB_t$$
   where $Y_t$ is the portfolio value, $\theta$ is the long-term mean, $\mu$ is the speed of mean reversion, $\sigma$ is the instantaneous volatility, and $B_t$ is a standard Brownian motion.

2. **Optimal Liquidation Level Equation**:
   $$F^{\chi} (b^{\chi}) - (b^{\chi} - c_s)F'^{\chi}(b^{\chi}) = 0$$
   where $b^{\chi}$ is the optimal liquidation level, $c_s$ is the transaction cost for selling, and $F^{\chi}(y)$ is a function involving the confluent hypergeometric function $M$.

3. **Optimal Entry Level Equation**:
   $$\hat{G}^{\chi}(d^{\chi})(V'^{\chi}(d^{\chi}) - 1) - \hat{G}'^{\chi}(d^{\chi})(V^{\chi}(d^{\chi}) - d^{\chi} - c_b) = 0$$
   where $d^{\chi}$ is the optimal entry level, $c_b$ is the transaction cost for buying, $V^{\chi}$ is the expected liquidation value, and $\hat{G}^{\chi}$ is a function involving the confluent hypergeometric function $U$.

4. **Optimal Switching Condition**:
   $$c_b < \frac{b^{\chi*}-c_s}{F^{\chi}(b^{\chi*})}$$
   where $c_b$ and $c_s$ are transaction costs, $b^{\chi*}$ is the optimal liquidation level, and $F^{\chi}$ is the defined hypergeometric function. Re-entering the market is optimal only if this condition and $y_b > 0$ hold.

### References

Tim Leung and Xin Li (2015) - Optimal Mean reversion Trading: Mathematical Analysis and Practical Applications
Borodin and Salminen (2002) - Handbook of Brownian Motion - Facts and Formulae

---

# Pairs Trading, Time Series Analysis

## 21. H-Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/h_strategy.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/h_strategy.html)

The H-Strategy is a non-parametric approach to pairs trading that utilizes statistical information about the variability of a tradable process. Unlike traditional methods that seek a long-run mean, this strategy focuses on determining how far a process should move in one direction before a reversal trade becomes profitable, by measuring its variability.

### H-construction

Suppose $P(t)$ is a continuous time series on the time interval $[0, T]$.

#### Renko construction

**Step 1: Generate the Renko Process**

The Renko process $X(i)$ is defined as:

$$X(i) : X(i) = P(\tau_i), i = 0, 1, ..., N$$

where $\tau_i$, $i = 0, 1, ..., N$ is an increasing sequence of time moments such that for some arbitrary $H > 0$, $\tau_0 = 0$ and $P(\tau_0) = P(0)$.

$$H \leq \max \limits_{t \in [0,T]} P(t) - \min \limits_{t \in [0,T]} P(t)$$

$$\tau_i = inf\{u \in [\tau_{i - 1}, T] : |P(u) - P(\tau_{i - 1})| = H\}$$

**Step 2: Determine Turning Points**

A sequence of time moments ${(\tau^a_n, \tau^b_n), n = 0, 1, ..., M}$ is created based on ${\tau_i}$. The sequence ${\tau^a_n}$ defines time moments when the Renko process $X(i)$ has a local maximum or minimum (changes direction), and ${\tau^b_n}$ defines when these are detected.

Specifically, $\tau^a_0 = \tau_0$ and $\tau^b_0 = \tau_1$. Then:

$$\tau^b_n = min\{\tau_i > \tau^b_{n-1}: (P(\tau_i) - P(\tau_{i-1}))(P(\tau_{i-1}) - P(\tau_{i-2})) < 0\}$$

$$\tau^a_n = \{\tau_{i - 1} : \tau^b_n = \tau_i\}$$

#### Kagi construction

The Kagi construction is similar, but uses local maximums and minimums of the process $P(t)$ directly. ${\tau^a_n}$ defines when $P(t)$ has a local maximum or minimum, and ${\tau^b_n}$ defines when it's recognized (i.e., $P(t)$ moves away from its last local extremum by $H$).

Initially, $\tau^a_0$, $\tau^b_0$ and $S_0$ are defined as:

$$\tau^b_0 = inf\{u \in [0, T] : \max \limits_{t \in [0,u]} P(t) - \min \limits_{t \in [0,u]} P(t) = H\}$$

$$\tau^a_0 = inf\{u < \tau^b_0: |P(u) - P(\tau^b_0)| = H\}$$

$$S_0 = sign(P(\tau^a_0) - P(\tau^b_0))$$

where $S_0$ is $1$ for a local maximum and $-1$ for a local minimum.

For $n > 0$, $(\tau^a_n, \tau^b_n)$ and $S_n$ are defined recursively by alternating cases:

**Case 1: $S_{n-1} = -1$**

$$\tau^b_n = inf\{u \in [\tau^a_{n-1}, T] : P(u) - \min \limits_{t \in [\tau^a_{n-1}, u]} P(t) = H\}$$

$$\tau^a_n = inf\{u < \tau^b_n: P(u) = \min \limits_{t \in [\tau^a_{n-1}, \tau^b_n]} P(t)\}$$

$$S_n = 1$$

**Case 2: $S_{n-1} = 1$**

$$\tau^b_n = inf\{u \in [\tau^a_{n-1}, T] : \max \limits_{t \in [\tau^a_{n-1}, u]} P(t) - P(u) = H\}$$

$$\tau^a_n = inf\{u < \tau^b_n: P(u) = \max \limits_{t \in [\tau^a_{n-1}, \tau^b_n]} P(t)\}$$

$$S_n = -1$$

### H-statistics

**H-inversion**

H-inversion counts the number of times the process $P(t)$ changes its direction for selected $H$, $T$ and $P(t)$.

$$N_T (H, P) = \max \{n : \tau^{b}_{n} = T\} = N$$

where $H$ is the threshold of the H-construction, and $P$ is the process $P(t)$.

**H-distances**

H-distances counts the sum of vertical distances between local maximums and minimums to the power $p$.

$$V^p_T (H, P) = \sum_{n = 1}^{N}|P(\tau^a_n) - P(\tau^a_{n-1})|^p$$

**H-volatility**

H-volatility of order $p$ measures the variability of the process $P(t)$ for selected $H$ and $T$.

$$\xi^p_T = \frac{V^p_T (H, P)}{N_T (H, P)}$$

### Strategies

**Momentum Strategy**

The investor buys (sells) an asset at a stopping time $\tau^b_n$ when the process passes its previous local minimum (maximum) and continuation is expected. The signal $s_t$ is:

$$\begin{split}s_t = \left\{\begin{array}{l} +1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) > 0\\ -1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) < 0\\ 0,\ otherwise \end{array}\right.\end{split}$$

where $+1$ indicates opening a long trade or closing a short trade, $-1$ indicates opening a short trade or closing a long trade, and $0$ indicates holding the previous position.

The profit from one trade according to the momentum H-strategy over time from $\tau^b_{n-1}$ to $\tau^b_{n}$ is:

$$Y_{\tau^b_n} = (P(\tau^b_n) - P(\tau^b_{n-1})) \cdot sign(P(\tau^a_n) - P(\tau^a_{n-1}))$$

And the total profit from time $0$ till time $T$ is:

$$Y_T(H, P) = (\xi^1_T (H, P) - 2H) \cdot N_T (H, P)$$

**Contrarian Strategy**

The investor sells (buys) an asset at a stopping time $\tau^b_n$ when the process has moved far enough from its previous local minimum (maximum), and a movement reversion is expected. The signal $s_t$ is:

$$\begin{split}s_t = \left\{\begin{array}{l} +1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) < 0\\ -1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) > 0\\ 0,\ otherwise \end{array}\right.\end{split}$$

where $+1$ indicates opening a long trade or closing a short trade, $-1$ indicates opening a short trade or closing a long trade, and $0$ indicates holding the previous position.

The profit from one trade according to the contrarian H-strategy over time from $\tau^b_{n-1}$ to $\tau^b_{n}$ is:

$$Y_{\tau^b_n} = (P(\tau^b_n) - P(\tau^b_{n-1})) \cdot sign(P(\tau^a_{n-1}) - P(\tau^a_n))$$

And the total profit from time $0$ till time $T$ is:

$$Y_T(H, P) = (2H - \xi^1_T (H, P)) \cdot N_T (H, P)$$

### Properties

If $\xi^1_T > 2H$, a momentum H-strategy is profitable. If $\xi^1_T < 2H$, a contrarian H-strategy is profitable.

For a Wiener process, $\xi^1_T = 2H$, implying no profit. H-volatility $\xi^1_T = 2H$ is a property of a martingale. $\xi^1_T > 2H$ could be a property of a sub-martingale or a super-martingale or a process that regularly switches back-and-forth over time between a sub-martingale and a super-martingale.

For any mean-reverting process, $\xi^1_T < 2H$, making the contrarian H-strategy profitable for any $H$.

### Pairs Selection

**Algorithm:**

1.  Determine the assets pool and the length of historical data.
2.  Take log-prices of all assets, combine them in all possible pairs, and build a spread process for each pair:
    $$spread_{ij} = log(P_i) - log(P_j)$$
3.  For each spread process, calculate its standard deviation and set it as the threshold $H$ of the H-construction.
4.  Determine the construction type of the H-construction (Renko or Kagi).
5.  Build the H-construction on the spread series for each pair.
6.  The top N pairs with the highest/lowest H-inversion are used for pairs trading. Mean-reverting processes tend to have higher H-inversion.

### Code Examples (Illustrative of mathematical concepts)

**HConstruction Example:**

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from arbitragelab.time_series_approach.h_strategy import HConstruction

data = yf.download("KO PEP", start="2019-01-01", end="2020-12-31", progress=False)["Adj Close"]
# Construct spread series
series = np.log(data["KO"]) - np.log(data["PEP"])
threshold = series["2019"].std()
hc = HConstruction(series["2020"], threshold, "Kagi")
# Get H-statistics
hc.h_inversion() # Example output: 19
hc.h_distances() # Example output: 1.475...
hc.h_volatility() # Example output: 0.0776...
# Extract signals
signals = hc.get_signals("contrarian")
# A quick backtest
positions = signals.replace(0, np.nan).ffill()
returns = data["KO"]["2020"].pct_change() - data["PEP"]["2020"].pct_change()
total_returns = ((positions.shift(1) * returns).dropna() + 1).cumprod()
```

**HSelection Example:**

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from arbitragelab.time_series_approach.h_strategy import HSelection

tickers = "AAPL MSFT AMZN META GOOGL GOOG TSLA NVDA JPM"
data = yf.download(tickers, start="2019-01-01", end="2020-12-31", progress=False)["Adj Close"]
hs = HSelection(data)
hs.select()  # Calculate H-inversion statistic
pairs = hs.get_pairs(5, "highest", False)
# Inspect the first pair
# Each pair contains [H-inversion statistic, H-construction threshold, Asset pair]
pairs[0] # Example output: [34, 0.0034..., ('GOOG', 'GOOGL')]
# Inspect another pair
pairs[1] # Example output: [12, 0.132..., ('AAPL', 'NVDA')]
```

### Key Formulas Summary

1.  **Renko Process Definition:** $X(i) : X(i) = P(\tau_i), i = 0, 1, ..., N$
    *   $X(i)$: Renko process value at index $i$
    *   $P(\tau_i)$: Price at time $\tau_i$
    *   $\tau_i$: Increasing sequence of time moments

2.  **H-volatility:** $\xi^p_T = \frac{V^p_T (H, P)}{N_T (H, P)}$
    *   $\xi^p_T$: H-volatility of order $p$
    *   $V^p_T (H, P)$: H-distances of order $p$
    *   $N_T (H, P)$: H-inversion

3.  **Momentum Strategy Signal:**
    $$\begin{split}s_t = \left\{\begin{array}{l} +1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) > 0\\ -1,\ if\ t = \tau^b_n\ and\ P(\tau^b_n) - P(\tau^a_n) < 0\\ 0,\ otherwise \end{array}\right.\end{split}$$
    *   $s_t$: Trading signal at time $t$
    *   $+1$: Long trade or close short
    *   $-1$: Short trade or close long
    *   $0$: Hold position
    *   $\tau^b_n$: Time of signal recognition
    *   $\tau^a_n$: Time of local extremum

4.  **Total Profit for Momentum Strategy:** $Y_T(H, P) = (\xi^1_T (H, P) - 2H) \cdot N_T (H, P)$
    *   $Y_T(H, P)$: Total profit from time $0$ to $T$
    *   $\xi^1_T (H, P)$: H-volatility of order 1
    *   $H$: Threshold of H-construction
    *   $N_T (H, P)$: H-inversion

5.  **Spread Process for Pairs Selection:** $spread_{ij} = log(P_i) - log(P_j)$
    *   $spread_{ij}$: Spread between asset $i$ and asset $j$
    *   $P_i$: Price of asset $i$
    *   $P_j$: Price of asset $j$

### References

Bogomolov, T. (2013) - Pairs trading based on statistical variability of the spread process. Quantitative Finance, 13(9): 1411–1430.

---

# Time Series Analysis, Pairs Trading

## 22. Quantile Time Series Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/quantile_time_series_strategy.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/quantile_time_series_strategy.html)

The Quantile Time Series Strategy is based on forecasting future spread values and generating trading signals from the difference between forecasted and actual values. The strategy utilizes an Auto ARIMA model for forecasting.

### Auto ARIMA Model

The ARIMA(p,d,q) model describes a stochastic process as a composition of polynomials. The autoregression (AR) part regresses the variable at time $t$ on its own lagged values. The moving average (MA) part models the prediction error as a linear combination of lagged error terms and a time series expected value. The integrated (I) part denotes the differences of series for stationarity. For this strategy, the input series are assumed to be stationary due to cointegration.

The ARIMA(p,d,q) model can be represented as:

$$x_{t} = c + \epsilon_{t} + \sum_{i=1}^{p} \phi_{i} x_{t-1} + \sum_{i=1}^{q} \Theta_{i} \epsilon_{t-i}$$

Where:
- $x_{t}$: The time series value at time $t$.
- $c$: A constant term, including a mean value of the $x_{t}$ series.
- $\epsilon_{t}, \epsilon_{t-1}, ..., \epsilon_{t-q}$: Random variables corresponding to white noise error terms at respective time instances.
- $\phi_{t}, ..., \phi_{p}$: Autoregressive parameters.
- $\Theta_{1}, ..., \Theta_{q}$: Moving average parameters.

If the input series are cointegrated of order zero, then $x_{t} = X_{t}$, where $X_{t}$ is the input time series. If the cointegration order is one, then $x_{t} = X_{t} - X_{t-1}$, and so on.

The best fitting ARIMA model is chosen using the Akaike Information Criterion (AIC):

$$AIC = 2k - 2ln(L)$$

Where:
- $k$: The number of model parameters.
- $L$: The likelihood function.

### Signal Generation

Let $S_{t}$ be the true value of the spread at time $t$, and $S^{*}_{t}$ be the predicted value of the spread at time $t$. The signals generation is based on the predicted percentage change:

$$\delta_{t+1} = \frac{S^{*}_{t+1} - S_{t}}{S_{t}} \times 100$$

Market entry conditions are based on predefined thresholds, $\alpha_{L}$ for long positions and $\alpha_{S}$ for short positions:

$$\begin{split}Position = \begin{cases} Long &\text{, if } \Delta_{t+1} \ge \alpha_{L} \\ Short &\text{, if } \Delta_{t+1} \le \alpha_{S} \\ No Position &\text{, otherwise.} \end{cases}\end{split}$$

The thresholds $\alpha_{L}$ and $\alpha_{S}$ are determined by picking quantiles of the percentage change distribution during a formation period. The spread percentages at any time $t$ are calculated as:

$$x_{t} = \frac{S_{t} - S_{t-1}}{S_{t-1}} \times 100$$

For $f(x)$, the distribution of percentage changes, the negative and positive changes are considered separately to get the needed quantile values. The authors recommend picking either 10% or 20% quantiles for thresholds.

### Key Formulas Summary

1. **ARIMA(p,d,q) Model**: $x_{t} = c + \epsilon_{t} + \sum_{i=1}^{p} \phi_{i} x_{t-1} + \sum_{i=1}^{q} \Theta_{i} \epsilon_{t-i}$
   - $x_{t}$: time series value at time $t$
   - $c$: constant term
   - $\epsilon_{t}$: white noise error term
   - $\phi_{i}$: autoregressive parameters
   - $\Theta_{i}$: moving average parameters

2. **Akaike Information Criterion (AIC)**: $AIC = 2k - 2ln(L)$
   - $k$: number of model parameters
   - $L$: likelihood function

3. **Predicted Percentage Change**: $\delta_{t+1} = \frac{S^{*}_{t+1} - S_{t}}{S_{t}} \times 100$
   - $\delta_{t+1}$: predicted percentage change at $t+1$
   - $S^{*}_{t+1}$: predicted spread value at $t+1$
   - $S_{t}$: true spread value at $t$

4. **Market Entry Conditions**: $\begin{split}Position = \begin{cases} Long &\text{, if } \Delta_{t+1} \ge \alpha_{L} \\ Short &\text{, if } \Delta_{t+1} \le \alpha_{S} \\ No Position &\text{, otherwise.} \end{cases}\end{split}$
   - $\Delta_{t+1}$: predicted percentage change
   - $\alpha_{L}$: long position threshold
   - $\alpha_{S}$: short position threshold

5. **Spread Percentage Change**: $x_{t} = \frac{S_{t} - S_{t-1}}{S_{t-1}} \times 100$
   - $x_{t}$: spread percentage change at time $t$
   - $S_{t}$: spread value at time $t$
   - $S_{t-1}$: spread value at time $t-1$

### References

Sarmento, S.M. and Horta, N. (2020) - A Machine Learning based Pairs Trading Investment Strategy

---

# Codependence

## 23. Information Theory Metrics

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/information_theory_metrics.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/codependence/information_theory_metrics.html)

## Information Theory Metrics

We can gauge the codependence from the information theory perspective. In information theory, (Shannon’s) entropy is a measure of information (uncertainty). As described in the Cornell lecture slides, p.13, entropy is calculated as:

$H[X] = -\sum_{x \in S_{X}}p[x]log[p[x]]$

Where $X$ is a discrete random variable that takes a value $x$ from the set $S_{X}$ with probability $p[x]$.

In short, we can say that entropy is the expectation of the amount of information when we sample from a particular probability distribution or the number of bits to transmit to the target. So, if there is a correspondence between random variables, the correspondence will be reflected in entropy. For example, if two random variables are associated, the amount of information in the joint probability distribution of the two random variables will be less than the sum of the information in each random variable. This is because knowing a correspondence means knowing one random variable can reduce uncertainty about the other random variable.

$H[X+Y] = H[X] + H[Y]$, where $X \perp Y$ (X and Y are independent).

This module presents two ways of measuring correspondence:

1. Mutual Information
2. Variation of Information

## Mutual Information

According to Lopez de Prado: “**Mutual Information** is defined as the decrease in uncertainty (or informational gain) in $X$ that results from knowing the value of $Y$. Mutual information is not a metric as it doesn’t satisfy the triangle inequality”. The properties of non-negativity and symmetry are satisfied. Mutual information is calculated as:

$I[X, Y] = H[X] - H[X|Y]$
$I[X, Y] = H[X] + H[Y] - H[X,Y]$
$I[X, Y] = \sum_{x \in S_{X}} \sum_{y \in S_{Y}}p[x,y]log[\frac{p[x,y]}{p[x]p[y]}]$

Mutual information has a grouping property:

$I[X, Y, Z] = I[X, Y] + I[(X, Y), Z]$

where $(X, Y)$ is a joint distribution of $X$ and $Y$.

It can also be normalized using a known upper boundary:

$I[X, Y] \le min\{H[X] + H[Y]\}$

An alternative way of estimating the Mutual information is through using copulas. A link between Mutual information and copula entropy was presented in the paper by Ma, Jian & Sun, Zengqi. (2008). Mutual information is copula entropy.

A blog post by Gautier Marti includes descriptions of two alternative estimators of copula entropy:

*   First, estimate the copula (as a normalized ranking of the observations). Then apply the standard mutual information estimator on the normalized rankings of the observations.

$X_{unif} = \frac{X_{ranked}}{N}$
$Y_{unif} = \frac{Y_{ranked}}{N}$
$I[X, Y] = \sum_{x \in S_{X_{unif}}} \sum_{y \in S_{Y_{unif}}}p[x,y]log[\frac{p[x,y]}{p[x]p[y]}]$

*   First, estimate the copula (as a normalized ranking of the observations). Then and calculate the entropy of a copula. Estimator of the Mutual Information would be equal to negative copula entropy:

$X_{unif} = \frac{X_{ranked}}{N}$
$Y_{unif} = \frac{Y_{ranked}}{N}$
$I[X, Y] = (-1) * H[C(X, Y)]$

According to Gautier Marti, these two estimators have some advantages over the standard approach:

*   First, continuous marginals (think the distribution of returns of each stock) have a potentially unbounded support making it hard to bin properly.
*   Second, the discretization process to estimate the density used to compute the entropy, may introduce biases in the mutual information estimate due to a rather difficult and arbitrary binning of the support.

Using their copula $C(X,Y)$, allows to bypass the estimation of the margins. The copula has compact support in $[0, 1]$, and its margins are uniform.

## Variation of Information

According to Lopez de Prado: “**Variation of Information** can be interpreted as the uncertainty we expect in one variable if we are told the value of another”. The variation of information is a true metric and satisfies the axioms from the introduction.

$VI[X,Y] = H[X|Y] + H[Y|X]$
$VI[X,Y] = H[X] + H[Y]-2I[X,Y]$
$VI[X,Y] = 2H[X,Y]-H[X]-H[Y]$

The upper bound of Variation of information is not firm as it depends on the sizes of the population which is problematic when comparing variations of information across different population sizes, as described in Cornell lecture slides, p.21.

## Discretization

Both mutual information and variation of information are using random variables that are discrete. To use these tools for continuous random variables the discretization approach can be used.

For the continuous case, we can quantize the values to estimate $H[X]$. Following the Cornell lecture slides, p.26:

$H[X] = \int_{\infty}^{\infty}f_{X}[x]log[f_{X}[x]]dx \approx -\sum_{i=1}^{B_{X}}f_{X}[x_{i}]log[f_{X}[x_{i}]]\Delta_{x}$

where the observed values $\{x\}$ are divided into $B_{X}$ bins of equal size $\Delta_{X}$, $\Delta_{X} = \frac{max\{x\} - min\{x\}}{B_{X}}$, and $f_{X}[x_{i}]$ is the frequency of observations within the i-th bin.

So, the discretized estimator of entropy is:

$\hat{H}[X]=-\sum_{i=1}^{B_{X}}\frac{N_{i}}{N}log[\frac{N_{i}}{N}]+log[\Delta_{X}]$

where $N_{i}$ is the number of observations within the i-th bin, $N = \sum_{i=1}^{B_{X}}N_{i}$.

From the above equations, the size of the bins should be chosen. The results of the entropy estimation will depend on the binning. The works by Hacine-Gharbi et al. (2012) and Hacine-Gharbi and Ravier (2018) present optimal binning for marginal and joint entropy.

This optimal binning method is used in the mutual information and variation of information functions.

## Examples

The following example highlights how the various metrics behave under various variable dependencies:

1. Linear
2. Squared
3. $Y = abs(X)$
4. Independent variables

Code examples:

```python
import numpy as np
import matplotlib.pyplot as plt
from ace import model  # The ace package is used for max correlation estimation

from arbitragelab.codependence import distance_correlation, get_mutual_info, variation_of_information_score
from ace import model # ace package is used for max correlation estimation

def max_correlation(x: np.array, y: np.array) -> float:
    """
    Get max correlation using ace package.
    """

    x_input = [x]
    y_input = y
    ace_model = model.Model()
    ace_model.build_model_from_xy(x_input, y_input)

    return np.corrcoef(ace_model.ace.x_transforms[0], ace_model.ace.y_transform)[0][1]

# Creating variables
state = np.random.RandomState(42)
x = state.normal(size=1000)
y_1 = 2 * x + state.normal(size=1000) / 5 # linear
y_2 = x ** 2 + state.normal(size=1000) / 5 # squared
y_3 = abs(x) + state.normal(size=1000) / 5 # Abs
# independent
y_4 = np.random.RandomState(0).normal(size=1000) * np.random.RandomState(5).normal(size=1000)

for y, dependency in zip([y_1, y_2, y_3, y_4], ['linear', 'squared', 'y=|x|', 'independent']):
    text = "Pearson corr: {:0.2f} " + \
           "\nNorm.mutual info: {:0.2f} " + \
           "\nDistance correlation: {:0.2f} " + \
           "\nInformation variation: {:0.2f} " + \
           "\nMax correlation: {:0.2f}"

    text = text.format(np.corrcoef(x, y)[0, 1],
                       get_mutual_info(x, y, normalize=True),
                       distance_correlation(x, y),
                       variation_of_information_score(x, y, normalize=True),
                       max_correlation(x, y))

    # Plot relationships
    fig, ax = plt.subplots(figsize=(8,7))
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=14, verticalalignment='top', bbox=props)
    plt.title(dependency)
    ax.plot(x, y, 'ro')
    plt.savefig('{}.png'.format(dependency))
```

### Key Formulas Summary

1. Shannon's Entropy: $H[X] = -\sum_{x \in S_{X}}p[x]log[p[x]]$ where $X$ is a discrete random variable that takes a value $x$ from the set $S_{X}$ with probability $p[x]$.
2. Mutual Information: $I[X, Y] = H[X] - H[X|Y] = H[X] + H[Y] - H[X,Y] = \sum_{x \in S_{X}} \sum_{y \in S_{Y}}p[x,y]log[\frac{p[x,y]}{p[x]p[y]}]$ where $H[X]$ is the entropy of $X$, $H[X|Y]$ is the conditional entropy of $X$ given $Y$, and $p[x,y]$ is the joint probability of $X$ and $Y$.
3. Variation of Information: $VI[X,Y] = H[X|Y] + H[Y|X] = H[X] + H[Y]-2I[X,Y] = 2H[X,Y]-H[X]-H[Y]$ where $H[X|Y]$ and $H[Y|X]$ are conditional entropies, and $I[X,Y]$ is the mutual information.
4. Discretized Estimator of Entropy: $\hat{H}[X]=-\sum_{i=1}^{B_{X}}\frac{N_{i}}{N}log[\frac{N_{i}}{N}]+log[\Delta_{X}]$ where $N_{i}$ is the number of observations within the i-th bin, $N = \sum_{i=1}^{B_{X}}N_{i}$, $B_{X}$ is the number of bins, and $\Delta_{X} = \frac{max\{x\} - min\{x\}}{B_{X}}$ is the bin size.

### References

de Prado, M.L., 2020. Codependence (Presentation Slides). Available at SSRN 3512994.
Ma, J. and Sun, Z., 2011. Mutual information is copula entropy. Tsinghua Science & Technology, 16(1), pp.51-54.
Hacine-Gharbi, A., Ravier, P., Harba, R. and Mohamadi, T., 2012. Low bias histogram-based estimation of mutual information for feature selection. Pattern recognition letters, 33(10), pp.1302-1308.
Hacine-Gharbi, A. and Ravier, P., 2018. A binning formula of bi-histogram for joint entropy estimation using mean square error minimization. Pattern Recognition Letters, 101, pp.21-28.

---

# OU Model

## 24. A closed-form solution for optimal mean-reverting trading strategies

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/heat_potentials.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/heat_potentials.html)

The documentation describes a strategy for optimal mean-reverting trading strategies, primarily utilizing the Ornstein-Uhlenbeck (OU) process and the method of heat potentials to maximize the Sharpe ratio. The core idea is to monetize price oscillations around an equilibrium level.

**Problem Definition:**
An investment strategy S invests in $i = 1,...I$ opportunities. For each opportunity $i$, S takes a position of $m_i$ units of security X, where $m_i \in (-\infty; +\infty)$. The transaction is priced at $m_i P_{i,0}$, where $P_{i,0}$ is the average price per unit. The mark-to-market (MtM) value of opportunity $i$ after $t$ observed transactions is $m_i P_{1,t}$. The MtM p/l of opportunity $i$ after $t$ transactions is given by:

$\pi_{i,T_i}=m(P_{i,t}-P_{i,0})$

Exiting opportunities arise under these scenarios:
* Profit-taking: $\pi_{i,T_i} \geq \bar{\pi}$, where $\bar{\pi}>0$ is a profit-taking threshold.
* Stop-loss: $\pi_{i,T_i} \leq \underline{\pi}$, where $\underline{\pi}<0$ is a stop-loss level.

The price series $P_i$ is modeled by an Ornstein-Uhlenbeck (OU) process:

$P_{i,t} - \mathbb{E}_0[P_{i,t}] = \mu(\mathbb{E}_0 - P_{i,t-1}) + \sigma\epsilon_{i,t}$

To apply the heat potentials method, the problem is reformulated. Consider a long investment strategy with p/l driven by the OU process:

$dx' = \mu'(\theta'-x')dt'+\sigma'dW_{t'}, x'(0) = 0$

with a trading rule $R = \{ \bar{\pi}',\underline{\pi}',T' \}$. This is then scaled to remove superfluous parameters and use its steady-state:

$t = \mu't'$
$T = \mu'T'$
$x = \frac{\sqrt{\mu'}}{\sigma'} x'$
$\theta = \frac{\sqrt{\mu'}}{\sigma'} \theta'$
$\bar{\pi} = \frac{\sqrt{\mu'}}{\sigma'} \bar{\pi}'$
$\underline{\pi} = \frac{\sqrt{\mu'}}{\sigma'} \underline{\pi}'$

This transformation leads to the simplified OU process:

$dx = (\theta-x)dt + dW_t, \bar{\pi}' \leq x \leq \underline{\pi}, 0 \leq t \leq T$

where $\theta$ is an expected value and its standard deviation is $\Omega=\frac{1}{\sqrt{2}}$.

**Sharpe Ratio Calculation:**
The approximate Sharpe Ratio (SR) is calculated in four steps:

**Step 1: Define a calculation grid**

$0=\upsilon_0<\upsilon_1<...<\upsilon_n=\Upsilon, \upsilon(t) = \frac{1 - e^{-2(T-t)}}{2}$

**Step 2: Numerically calculate helper functions** $\bar{\epsilon}, \underline{\epsilon}, \bar{\phi}, \underline{\phi}$
These are solved using the trapezoidal rule for Volterra equations.

**Step 3: Calculate the values of** $\hat{E}(\Upsilon,\bar{\omega})$ **and** $\hat{F}(\Upsilon,\bar{\omega})$
These functions are computed by approximating integrals using the trapezoidal rule:

$\hat{E}(\Upsilon,\bar{\omega}) = \frac{1}{2} \sum_{i=1}^k(\underline{w}_{n,i}\underline{\epsilon}_i + \underline{w}_{n,i-1}\underline{\epsilon}_{i-1} + \bar{w}_{n,i}\bar{\epsilon}_i + \bar{w}_{n,i-1}\bar{\epsilon}_{i-1})(\upsilon_i - \upsilon_{i-1})$

$\hat{F}(\Upsilon,\bar{\omega}) = \frac{1}{2} \sum_{i=1}^k(\underline{w}_{n,i}\underline{\phi}_i + \underline{w}_{n,i-1}\underline{\phi}_{i-1} + \bar{w}_{n,i}\bar{\phi}_i + \bar{w}_{n,i-1}\bar{\phi}_{i-1})(\upsilon_i - \upsilon_{i-1})$

Where $w$ are the weights.

**Step 4: Calculate the SR using the obtained values**

$SR = \frac{\hat{E}(\Upsilon,\bar{\omega}) - \frac{2 (\bar{\omega}-\theta)}{ln(1-2\Upsilon)}}{\sqrt{\hat{F}(\Upsilon,\bar{\omega}) - (\hat{E}(\Upsilon,\bar{\omega}))^2 + \frac{4(\Upsilon + ln(1-2\Upsilon)(\bar{\omega}+\theta)\hat{E}(\Upsilon,\bar{\omega})}{(ln(1-2\Upsilon))^2}}}$

To find the optimal thresholds, the SR is maximized with respect to $\bar{\pi}\geq0,\underline{\pi}\leq0$:

${\bar{\pi}^*,\underline{\pi}^*}=\underset{\bar{\pi}\geq0,\underline{\pi}\leq0}{\arg\max} SR$

**Implementation Details:**
The `HeatPotentials` module handles internal transformations for steady-state solutions and reverse transformations for optimal threshold values. The `fit` method scales parameters and sets up the grid. `optimal_levels` performs the optimization, and `sharpe_calculation` computes the SR for given levels. `description` scales results back to initial parameters.

**Code Example (Parameters from OU Model Simulation):**
`theta_given=0.03711`
`mu_given=65.3333`
`sigma_given=0.3`
`delta_t_given=1/255`

Model fitting: `ou_data.fit_to_portfolio(data)` results in `theta, mu, sigma = ou_data.theta, ou_data.mu, np.sqrt(ou_data.sigma_square)`.

### Key Formulas Summary

1. **Profit/Loss (P/L) of opportunity $i$:** $\pi_{i,T_i}=m(P_{i,t}-P_{i,0})$
   - $m$: units of security X
   - $P_{i,t}$: price at time $t$
   - $P_{i,0}$: initial price

2. **Ornstein-Uhlenbeck (OU) Process (Original):** $dx' = \mu'(\theta'-x')dt'+\sigma'dW_{t'}$
   - $x'$: price series
   - $\mu'$: speed of reversion
   - $\theta'$: long-term mean
   - $\sigma'$: volatility
   - $dW_{t'}$: Wiener process

3. **Ornstein-Uhlenbeck (OU) Process (Scaled):** $dx = (\theta-x)dt + dW_t$
   - $x$: scaled price series
   - $\theta$: scaled long-term mean
   - $dW_t$: Wiener process

4. **Sharpe Ratio (SR) Formula:** $SR = \frac{\hat{E}(\Upsilon,\bar{\omega}) - \frac{2 (\bar{\omega}-\theta)}{ln(1-2\Upsilon)}}{\sqrt{\hat{F}(\Upsilon,\bar{\omega}) - (\hat{E}(\Upsilon,\bar{\omega}))^2 + \frac{4(\Upsilon + ln(1-2\Upsilon)(\bar{\omega}+\theta)\hat{E}(\Upsilon,\bar{\omega})}{(ln(1-2\Upsilon))^2}}}$
   - $\hat{E}(\Upsilon,\bar{\omega})$ and $\hat{F}(\Upsilon,\bar{\omega})$: helper functions calculated in previous steps
   - $\Upsilon$: maximum duration of the trade
   - $\bar{\omega}$: profit-taking threshold
   - $\theta$: scaled long-term mean

5. **Optimal Thresholds Maximization:** ${\bar{\pi}^*,\underline{\pi}^*}=\underset{\bar{\pi}\geq0,\underline{\pi}\leq0}{\arg\max} SR$
   - $\bar{\pi}^*$: optimal profit-taking threshold
   - $\underline{\pi}^*$: optimal stop-loss level

### References

Lipton, A. and de Prado, M.L., 2020. A closed-form solution for optimal mean-reverting trading strategies. arXiv preprint arXiv:2003.10502.
De Prado, M.L., 2018. Advances in financial machine learning. John Wiley & Sons.

---

# Mean Reversion

## 25. Bollinger Bands Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/z_score.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/trading/z_score.html)

The Bollinger Bands Strategy utilizes Z-scores to generate trading signals for a given spread. The Z-score quantifies the normalized deviation of the spread value from its moving average. The formula for the Z-score at time $t$ is defined as:

$$Zscore_{t} = \frac{S_{t} - MA(S_{t}, T_{MA})}{std(S_{t}, T_{std})}$$

Where:
* $S_{t}$ represents the spread value at time $t$.
* $MA(S_{t}, T_{MA})$ denotes the moving average of the spread, calculated over a backward-looking window of $T_{MA}$ periods.
* $std(S_{t}, T_{std})$ signifies the rolling standard deviation of the spread, computed over a backward-looking window of $T_{std}$ periods.

**Entry Signal Rules:**
A position is entered when the absolute value of the Z-score exceeds a predefined entry threshold, `entryZscore`. Mathematically, this condition is expressed as:

$$|Zscore_{t}| \ge |entryZscore|$$

The `entryZscore` parameter can be optimized using a training dataset. The look-back windows for the moving average ($T_{MA}$) and standard deviation ($T_{std}$) are also optimizable parameters.

**Exit Signal Rules:**
The strategy is exited when the spread's Z-score changes its value by more than `exitZscore_delta` from the `entryZscore` in the opposite direction. This condition is given by:

$$|Zscore_{t}| \le |entryZscore + exitZscore\_delta|$$

If the look-back window is short and both `entryZscore` and `exitZscore_delta` are small, the holding period for trades tends to be shorter, leading to a higher frequency of round-trip trades and potentially increased profits.

**Implementation Parameters:**
The strategy object is initialized with the following key parameters:
* `sma_window`: The window size for the simple moving average.
* `std_window`: The window size for the simple moving standard deviation.
* `entry_z_score`: The Z-score threshold for entering a trade.
* `exit_z_score_delta`: The delta value used in conjunction with the entry Z-score to determine the exit threshold.

**Code Example Snippet (Illustrating Parameter Usage):**
```python
strategy = BollingerBandsTradingRule(sma_window=20, std_window=20,
                                     entry_z_score=2.5, exit_z_score_delta=3)
```
This snippet demonstrates how the `BollingerBandsTradingRule` is instantiated with specific values for the moving average window, standard deviation window, entry Z-score, and exit Z-score delta.

### Key Formulas Summary

1. **Z-score Calculation:**
   $Zscore_{t} = \frac{S_{t} - MA(S_{t}, T_{MA})}{std(S_{t}, T_{std})}$
   Where:
   * $S_{t}$: Spread value at time $t$.
   * $MA(S_{t}, T_{MA})$: Moving average of the spread over $T_{MA}$ periods.
   * $std(S_{t}, T_{std})$: Rolling standard deviation of the spread over $T_{std}$ periods.

2. **Entry Condition:**
   $|Zscore_{t}| \ge |entryZscore|$
   A position is entered when the absolute Z-score is greater than or equal to the absolute `entryZscore`.

3. **Exit Condition:**
   $|Zscore_{t}| \le |entryZscore + exitZscore\_delta|$
   A position is exited when the absolute Z-score is less than or equal to the absolute sum of `entryZscore` and `exitZscore_delta`.

### References

Chan, Ernie. (2013) - Algorithmic Trading: Winning Strategies and Their Rationale.

---

# Statistical Arbitrage, Distance

## 26. Distance Approach Pairs Trading Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/distance_approach/distance_approach.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/distance_approach/distance_approach.html)

The Distance Approach is a pairs trading strategy that relies on the historical price relationship between two assets. It does not involve cointegration tests, distinguishing it from mean-reversion approaches. The core idea is to identify pairs of assets whose normalized price series have historically moved closely together.

**Pairs Formation**

1.  **Normalization of the input data:**
    To use the Euclidean square distance, the training price time series are normalized using the following formula:
    $$P_{normalized} = \frac{P - \min(P)}{\max(P) - \min(P)}$$
    Where:
    *   $P$ is the training price series of an asset.
    *   $\min(P)$ represents the minimum value from the price series.
    *   $\max(P)$ represents the maximum value from the price series.

2.  **Finding pairs:**
    After normalization, the Euclidean square distance (SSD) is calculated between each pair of assets. The SSD is defined as:
    $$SSD = \sum_{t=1}^{N} (P^1_t - P^2_t)^2$$
    Where:
    *   $P^1_t$ and $P^2_t$ are the normalized prices at time $t$ for the first and the second elements in a pair, respectively.
    *   $N$ is the number of observations in the time series.
    The pairs are then sorted by their SSD in ascending order, and the $n$ closest pairs are selected.

3.  **Calculating historical volatility:**
    For the selected pairs, a portfolio is constructed by taking the difference between their normalized price series. The historical standard deviation of these portfolios is calculated, which will later be used to generate trading signals.

**Pair Selection Criteria**

Beyond the basic distance approach, refined pair selection criteria can be applied:

1.  **Pairs within the same industry group:** Securities are matched only if they belong to the same industry group, reducing spurious dependencies.
2.  **Pairs with a higher number of zero-crossings:** Pairs with a higher number of zero-crossings in their spread during the formation period are preferred, as this indicates a stronger mean-reverting tendency.
3.  **Pairs with a higher historical standard deviation:** Selecting pairs with higher historical standard deviation in their spread can potentially increase profitability, as a small SSD tends to decrease the variance of the spread.

**Trading Signals Generation**

Once pairs are formed, trading signals are generated based on the portfolio value (difference between normalized prices) and its historical standard deviation:

*   **Sell signal:** A sell signal is generated if the portfolio value exceeds two historical standard deviations. This implies an expectation that the price of the first element will decrease and the price of the second element will increase, leading to convergence.
*   **Buy signal:** A buy signal is generated if the portfolio value is below minus two historical standard deviations. This implies an expectation that the price of the first element will increase and the price of the second element will decrease, also leading to convergence.
*   **Closing positions:** An open position is closed when the portfolio value crosses the zero mark or when the normalized prices of the elements in a pair cross. The resulting trading signals are target quantities of -1 (short), 0 (flat), or +1 (long) for each pair.

### Key Formulas Summary

1. Normalization of Price Series:
   $P_{normalized} = \frac{P - \min(P)}{\max(P) - \min(P)}$
   Where:
   - $P$: training price series of an asset.
   - $\min(P)$: minimum value from the price series.
   - $\max(P)$: maximum value from the price series.

2. Euclidean Square Distance (SSD):
   $SSD = \sum_{t=1}^{N} (P^1_t - P^2_t)^2$
   Where:
   - $P^1_t$: normalized price at time $t$ for the first element in a pair.
   - $P^2_t$: normalized price at time $t$ for the second element in a pair.
   - $N$: number of observations in the time series.

### References

Do, B. and Faff, R., 2010. Does simple pairs trading still work?. Financial Analysts Journal, 66(4), pp.83-95.
Do, B., and Faff, R. (2012). Are pairs trading profits robust to trading costs? Journal of Financial Research, 35(2):261–287.
Gatev, E., Goetzmann, W.N. and Rouwenhorst, K.G., 2006. Pairs trading: Performance of a relative-value arbitrage rule. The Review of Financial Studies, 19(3), pp.797-827.
Krauss, C., 2017. Statistical arbitrage pairs trading strategies: Review and outlook. Journal of Economic Surveys, 31(2), pp.513-545.

---

# Pairs Trading, Mean Reversion

## 27. Kalman Filter Strategy

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/other_approaches/kalman_filter.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/other_approaches/kalman_filter.html)

\\[y(t) = x(t) \\beta(t) + \\epsilon(t)\\\]

Where:
* \\(y(t)\\) and \\(x(t)\\) are price series of the first and second asset at time \\(t\\).
* \\(\\beta(t)\\) is the hedge ratio at time \\(t\\).
* \\(\\epsilon(t)\\) is the Gaussian noise with variance \\(V\_{\\epsilon}\\).

\\(\\beta\\) is a vector of size \\((2, 1)\\) denoting both the intercept and the slope of the linear relation between \\(x\\) and \\(y\\). For this, \\(x(t)\\) is augmented with a vector of ones to create an array of size \\((N, 2)\\).

Regression coefficient changes over time as:

\\[\\beta(t) = \\beta(t-1) + \\omega(t-1)\\\]

Where:
* \\(\\beta(t)\\) is the regression coefficient at time \\(t\\).
* \\(\\beta(t-1)\\) is the regression coefficient at time \\(t-1\\).
* \\(\\omega(t-1)\\) is a Gaussian noise with covariance \\(V\_{\\omega}\\).

Kalman filter also generates an estimate of the standard deviation of the forecast error of the observable variable. This can be used as the moving standard deviation of a Bollinger band.

**Trading Signals based on Forecast Error \\(e(t)\\) and its standard deviation \\(\\sqrt{Q(t)}\\):**

*   **Long Position Entry**: If \\(e(t) < - entry\\\_std\\\_score \* \\sqrt{Q(t)}\\), take a long position on the spread (Long \\(N\\) units of \\(y\\) asset and short \\(N\*\\beta\\) units of \\(x\\) asset).
*   **Long Position Exit**: If \\(e(t) \\ge - exit\\\_std\\\_score \* \\sqrt{Q(t)}\\), close the long position on the spread.
*   **Short Position Entry**: If \\(e(t) > entry\\\_std\\\_score \* \\sqrt{Q(t)}\\), take a short position on the spread (Short \\(N\\) units of \\(y\\) asset and long \\(N\*\\beta\\) units of \\(x\\) asset).
*   **Short Position Exit**: If \\(e(t) \\le exit\\\_std\\\_score \* \\sqrt{Q(t)}\\), close the short position on the spread.

**Python Code Snippets for Implementation:**

```python
import pandas as pd
from arbitragelab.other_approaches.kalman_filter import KalmanFilterStrategy

# Getting the dataframe with time series of asset prices
data = pd.read_csv(\'X_FILE_PATH.csv\', index_col=0, parse_dates = [0])

# Running the Kalman Filter to find the slope, forecast error, etc.
filter_strategy = KalmanFilterStrategy()

# We assume the first element is X and the second is Y
for observations in data.values:
   filter_strategy.update(observations[0], observations[1])

# Getting a list of the hedge ratios
hedge_ratios = filter_strategy.hedge_ratios

# Getting a list of intercepts
intercepts = filter_strategy.intercepts

# Getting a list of forecast errors
forecast_errors = filter_strategy.spread_series

# Getting a list of forecast error standard deviations
error_st_dev = filter_strategy.spread_std_series

# Getting a DataFrame with trading signals
target_quantities = filter_strategy.trading_signals(self,
                                                    entry_std_score=3,
                                                    exit_std_score=-3)
```

### Key Formulas Summary

1.  **Observation Equation**: \\\[y(t) = x(t) \\beta(t) + \\epsilon(t)\\\]
    *   \\(y(t)\\) and \\(x(t)\\) are price series of the first and second asset at time \\(t\\).
    *   \\(\\beta(t)\\) is the hedge ratio at time \\(t\\).
    *   \\(\\epsilon(t)\\) is the Gaussian noise with variance \\(V\_{\\epsilon}\\).
2.  **State Transition Equation**: \\\[\\beta(t) = \\beta(t-1) + \\omega(t-1)\\\]
    *   \\(\\beta(t)\\) is the regression coefficient at time \\(t\\).
    *   \\(\\beta(t-1)\\) is the regression coefficient at time \\(t-1\\).
    *   \\(\\omega(t-1)\\) is a Gaussian noise with covariance \\(V\_{\\omega}\\).
3.  **Long Entry Signal**: \\(e(t) < - entry\\\_std\\\_score \* \\sqrt{Q(t)}\\)
    *   \\(e(t)\\) is the forecast error.
    *   \\(\\sqrt{Q(t)}\\) is the standard deviation of the forecast error.
    *   \\(entry\\\_std\\\_score\\) is a user-defined threshold.
4.  **Short Entry Signal**: \\(e(t) > entry\\\_std\\\_score \* \\sqrt{Q(t)}\\)
    *   \\(e(t)\\) is the forecast error.
    *   \\(\\sqrt{Q(t)}\\) is the standard deviation of the forecast error.
    *   \\(entry\\\_std\\\_score\\) is a user-defined threshold.

### References

Chan, E. (2013). Algorithmic trading: winning strategies and their rationale (Vol. 625). John Wiley & Sons.

---

# OU Model

## 28. OU Model Optimal Trading Thresholds Bertram

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/ou_optimal_threshold_bertram.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/ou_optimal_threshold_bertram.html)

The document describes a statistical arbitrage strategy where the security price follows an exponential Ornstein-Uhlenbeck process.

**Assumptions:**

*   **Price of the Traded Security**:
    The price of the traded security $p_t$ is modeled as:
    $$p_t = e^{X_t}; \quad X_{t_0} = x_0$$
    where $X_t$ satisfies the stochastic differential equation:
    $$dX_t = {\mu}({\theta} - X_t)dt + {\sigma}dW_t$$
    Here, $\theta$ is the long-term mean, $\mu$ is the speed at which the values will regroup around the long-term mean (mean-reversion speed), and $\sigma$ is the amplitude of randomness of the O-U process. $dW_t$ is a Wiener process.

*   **Trading Strategy**:
    A trade is entered when $X_t = a$ and exited at $X_t = m$, where $a < m$.

*   **Trading Cycle**:
    A trading cycle is completed as $X_t$ changes from $a$ to $m$, then back to $a$. The trade length $T$ is the time needed to complete a trading cycle.

**Analytic Formulae:**

*   **Mean of the Trade Length**:
    $$E[T] = \frac{\pi}{\mu} (Erfi(\frac{(m - \theta)\sqrt{\mu}}{\sigma}) - Erfi(\frac{(a - \theta)\sqrt{\mu}}{\sigma}))$$
    where $Erfi(x) = iErf(ix)$ is the imaginary error function.

*   **Variance of the Trade Length**:
    $$V[T] = \frac{{w_1(\frac{(m - \theta)\sqrt{2\mu}}{\sigma})} - {w_1(\frac{(a - \theta)\sqrt{2\mu}}{\sigma})} - {w_2(\frac{(m - \theta)\sqrt{2\mu}}{\sigma})} + {w_2(\frac{(a - \theta)\sqrt{2\mu}}{\sigma})}}{{{\mu}^2}}$$
    where:
    $w_1(z) = (\frac{1}{2} \sum_{k=1}^{\infty} \Gamma(\frac{k}{2}) (\sqrt{2}z)^k / k! )^2 - (\frac{1}{2} \sum_{n=1}^{\infty} (-1)^k \Gamma(\frac{k}{2}) (\sqrt{2}z)^k / k! )^2$
    $w_2(z) = \sum_{k=1}^{\infty} \Gamma(\frac{2k - 1}{2}) \Psi(\frac{2k - 1}{2}) (\sqrt{2}z)^{2k - 1} / (2k - 1)!$
    Here, $\Psi(x) = \psi(x) - \psi(1)$ and $\psi(x)$ is the digamma function.

*   **Mean and Variance of the Return per Unit of Time**:
    The continuously compounded rate of return for a single trade, accounting for transaction cost, is given by:
    $r(a, m, c) = (m - a - c)$
    The mean return per unit of time is:
    $$\mu_s(a, m, c) = \frac{r(a, m, c)}{E [T]}$$
    The variance of return per unit of time is:
    $$\sigma_s(a, m, c) = \frac{{r(a, m, c)}^2{V[T]}}{{E[T]}^3}$$

**Optimal Strategies:**

To calculate an optimal trading strategy, the goal is to choose optimal entry and exit thresholds that maximize the expected return or the Sharpe ratio per unit of time for a given transaction cost/risk-free rate.

The paper shows that the maximum expected return/Sharpe ratio occurs when $(m - \theta)^2 = (a - \theta)^2$. Since $a < m$, this implies that $m = 2\theta - a$. Therefore, for a given transaction cost/risk-free rate, the following equations can be maximized to find optimal $a$ and $m$.

*   **Maximizing Expected Return**:
    $$\mu^*_s(a, c) = \frac{r(a, 2\theta - a, c)}{E [T]}$$

*   **Maximizing Sharpe Ratio**:
    $$S^*(a, c, r_f) = \frac{\mu_s(a, 2\theta - a, c) - r^*}{\sigma_s(a, 2\theta - a, c)}$$
    where $r^* = \frac{r_f}{E[T]}$ and $r_f$ is the risk-free rate.

**Implementation Details:**

*   **Initializing OU-Process Parameters**:
    Parameters can be set directly or by fitting the process to data. The fitting method can refer to pp. 12-13 in the book: Tim Leung and Xin Li, Optimal Mean reversion Trading: Mathematical Analysis and Practical Applications.

*   **Getting Optimal Thresholds**:
    The optimal entry threshold $a$ and exit threshold $m$ are obtained by maximizing either the expected return or the Sharpe ratio. An `initial_guess` parameter is used to speed up the optimization process and ensure `scipy.optimize` can solve the target equation. The default value for `initial_guess` is $\theta - c - 10^{-2}$.

**Code Example (Python):**

```python
import numpy as np
import matplotlib.pyplot as plt
from arbitragelab.time_series_approach.ou_optimal_threshold_bertram import (
    OUModelOptimalThresholdBertram,
)
OUOTB = OUModelOptimalThresholdBertram()
# Init the OU-process parameter
OUOTB.construct_ou_model_from_given_parameters(theta=0, mu=180.9670, sigma=0.1538)
# Get optimal thresholds by maximizing the expected return
a, m = OUOTB.get_threshold_by_maximize_expected_return(c=0.001)
# Threshold when we enter a trade
# a = -0.004...
# Threshold when we exit the trade
# m = 0.004...
# Get the expected return and the variance
expected_return = OUOTB.expected_return(a=a, m=m, c=0.001)
# expected_return = 0.492...
return_variance = OUOTB.return_variance(a=a, m=m, c=0.001)
# return_variance = 0.0021...
# Get optimal thresholds by maximizing the Sharpe ratio
a, m = OUOTB.get_threshold_by_maximize_sharpe_ratio(c=0.001, rf=0.01)
# a = -0.01125...
# m = 0.01125...
# Get the Sharpe ratio
S = OUOTB.sharpe_ratio(a=a, m=m, c=0.001, rf=0.01)
# S = 3.862...
# Set an array of transaction costs
c_list = np.linspace(0, 0.01, 30)
# Plot the impact of transaction costs on the optimal entry threshold
OUOTB.plot_target_vs_c(
    target="a", method="maximize_expected_return", c_list=c_list
)
# Set an array containing risk-free rates.
rf_list = np.linspace(0, 0.05, 30)
# Plot the impact of risk-free rates on the optimal entry threshold
OUOTB.plot_target_vs_rf(
    target="a", method="maximize_sharpe_ratio", rf_list=rf_list, c=0.001
)
```

### Key Formulas Summary

1.  **Price of the Traded Security:** $p_t = e^{X_t}$ where $dX_t = {\mu}({\theta} - X_t)dt + {\sigma}dW_t$. Here, $p_t$ is the security price, $X_t$ is the underlying Ornstein-Uhlenbeck process, $\theta$ is the long-term mean, $\mu$ is the mean-reversion speed, and $\sigma$ is the amplitude of randomness.
2.  **Mean of the Trade Length:** $E[T] = \frac{\pi}{\mu} (Erfi(\frac{(m - \theta)\sqrt{\mu}}{\sigma}) - Erfi(\frac{(a - \theta)\sqrt{\mu}}{\sigma}))$. This formula calculates the expected time $T$ to complete a trading cycle, given entry threshold $a$ and exit threshold $m$.
3.  **Mean Return per Unit of Time:** $\mu_s(a, m, c) = \frac{r(a, m, c)}{E [T]}$, where $r(a, m, c) = (m - a - c)$ is the continuously compounded rate of return for a single trade, accounting for transaction cost $c$.
4.  **Optimal Threshold Condition:** $(m - \theta)^2 = (a - \theta)^2$, which simplifies to $m = 2\theta - a$ for $a < m$. This condition is used to find the optimal entry and exit thresholds that maximize expected return or Sharpe ratio.
5.  **Sharpe Ratio for Optimal Strategy:** $S^*(a, c, r_f) = \frac{\mu_s(a, 2\theta - a, c) - r^*}{\sigma_s(a, 2\theta - a, c)}$, where $r^* = \frac{r_f}{E[T]}$ and $r_f$ is the risk-free rate. This formula is used to calculate the Sharpe ratio for the optimal trading strategy.

### References

Bertram, W. K. (2009) - Analytic solutions for optimal statistical arbitrage trading. Physica A: Statistical Mechanics and its Applications, 389(11): 2234–2243.

---

# OU Model, Pairs Trading

## 29. OU Model Optimal Trading Thresholds Zeng

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/ou_optimal_threshold_zeng.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/ou_optimal_threshold_zeng.html)

The document describes an enhancement to the work by Bertram (2010) regarding optimal trading thresholds for pairs trading, specifically addressing the assumption of no short selling of the synthetic asset. The authors derive a polynomial expression for the expectation of the first-passage time of an Ornstein-Uhlenbeck (O-U) process with a two-sided boundary and simplify the problem of optimizing the expected return per unit of time.

**Assumptions:**

**Price of the Traded Security:**

The price of the traded security $p_t$ is modeled as:

$$p_t = e^{X_t};\quad X_{t_0} = x_0$$

where $X_t$ satisfies the following stochastic differential equation:

$$dX_t = {\mu}({\theta} - X_t)dt + {\sigma}dW_t$$

Here, $\theta$ is the long-term mean, $\mu$ is the speed at which values revert to the long-term mean, and $\sigma$ is the amplitude of randomness of the O-U process. (Note: The document states that its notation for $\theta$, $\mu$, and $\sigma$ differs from the reference paper).

**Trading Strategy:**

The trading strategy is defined by entry and exit thresholds for a dimensionless series $Y_t$, transformed from the original time series $X_t$:

$$\begin{split}\left\{ \begin{array}{**lr**} Open\ a\ short\ trade\ when\ Y_t = a_d\ and\ close\ the\ exiting\ short\ trade\ at\ Y_t = b_d.\\ Open\ a\ long\ trade\ when\ Y_t = -a_d\ and\ close\ the\ exiting\ long\ trade\ at\ Y_t = -b_d.\\ \end{array} \right.\end{split}$$

where $a_d$ and $b_d$ are the entry and exit thresholds in the dimensionless system, respectively.

**Trading Cycle:**

A trading cycle is completed when $Y_t$ changes from $a_d$ to $b_d$, then back to $a_d$ or $-a_d$. The trade length $T$ is the time required to complete a trading cycle.

**Analytic Formulae:**

**Mean and Variance of the Trade Length:**

The expected trade length $E[T]$ is given by:

$$E[T] = \frac{1}{2\mu}\sum_{k=0}^{\infty} \Gamma(\frac{2k + 1}{2})((\sqrt{2}a_d)^{2k + 1} - (\sqrt{2}b_d)^{2k + 1})/ (2k + 1)!$$

The variance of the trade length $V[T]$ is given by:

$$V[T] = \frac{1}{\mu^2}(V[T_{a_d,\ b_d}] + V[T_{-a_d,\ a_d,\ b_d}])$$

where:
*   $V[T_{a_d,\ b_d}]$ is the variance of the time taken for the O-U process to travel from $a_d$ to $b_d$.
*   $V[T_{-a_d,\ a_d,\ b_d}]$ is the variance of the time taken for the O-U process to travel from $b_d$ to $a_d$ or $-a_d$.

These variances are further defined as:

$$V[T_{a_d,\ b_d}] = {w_1(a_d)} - {w_1(b_d)} - {w_2(a_d)} + {w_2(b_d)}$$

where:

$$w_1(z) = (\frac{1}{2} \sum_{k=1}^{\infty} \Gamma(\frac{k}{2}) (\sqrt{2}z)^k / k! )^2 - (\frac{1}{2} \sum_{n=1}^{\infty} (-1)^k \Gamma(\frac{k}{2}) (\sqrt{2}z)^k / k! )^2$$

$$w_2(z) = \sum_{k=1}^{\infty} \Gamma(\frac{2k - 1}{2}) \Psi(\frac{2k - 1}{2}) (\sqrt{2}z)^{2k - 1} / (2k - 1)!$$

And:

$$V[T_{-a_d,\ a_d,\ b_d}] = E[T^{2}_{-a_d,\ a_d,\ b_d}] - E[T_{-a_d,\ a_d,\ b_d}]^2$$

where:

$$E[T_{-a_d,\ a_d,\ b_d}] = \frac{1}{2}\sum_{k=1}^{\infty} \Gamma(k)((\sqrt{2}a_d)^{2k} - (\sqrt{2}b_d)^{2k})/ (2k)!$$

$$E[T^{2}_{-a_d,\ a_d,\ b_d}] = e^{(b^2_d - a^2_d)/4}[g_1(a_d,\ b_d) - g_2(a_d,\ b_d)]$$

with:

$$g_1(a_d,\ b_d) = [\frac{(m^{\'\'}(\lambda,\ b_d)\ m(\lambda,\ a_d) - m^{\'}(\lambda,\ a_d)\ m^{\'}(\lambda,\ b_d))}{m^2(\lambda,\ a_d)}]|\_{\lambda = 0}$$

$$g_2(a_d,\ b_d) = [\frac{(m^{\'\'}(\lambda,\ a_d)\ m(\lambda,\ b_d) + m^{\'}(\lambda,\ a_d)\ m^{\'}(\lambda,\ b_d))}{m^2(\lambda,\ a_d)} - 2\frac{(m^{\'}(\lambda,\ a_d))^2\ m(\lambda,\ b_d)}{m^3(\lambda,\ a_d)}]|\_{\lambda = 0}$$

and $m(\lambda, x) = D_{-\lambda}(x) + D_{-\lambda}(−x)$, where $D_{-\lambda}(x)$ is the parabolic cylinder function:

$$D_{-\lambda}(x) = \sqrt{\frac{2}{\pi}} e^{x^2/4} \int_{0}^{\infty} t^{-\lambda} e^{-t^2/2} \cos(xt + \frac{\lambda\pi}{2})dt$$

**Mean and Variance of the Return per Unit of Time:**

The mean return per unit of time $\mu_s(a,\ b,\ c)$ is:

$$\mu_s(a,\ b,\ c) = \frac{r(a,\ b,\ c)}{E [T]}$$

The variance of the return per unit of time $\sigma_s(a,\ b,\ c)$ is:

$$\sigma_s(a,\ b,\ c) = \frac{{r(a,\ b,\ c)}^2{V[T]}}{{E[T]}^3}$$

where $r(a,\ b,\ c) = (|a − b| − c)$ represents the continuously compounded rate of return for a single trade, accounting for transaction cost $c$. Here, $a$ and $b$ denote the entry and exit thresholds, respectively.

**Optimal Strategies:**

To find an optimal trading strategy, the goal is to maximize the expected return per unit of time by choosing optimal entry and exit thresholds for a given transaction cost.

**Get Optimal Thresholds by Maximizing the Expected Return:**

*   **Case 1: $0 \leqslant b_d \leqslant a_d$**
    The maximum expected return occurs when $b_d = 0$. The optimal $a_d$ is found by solving the equation:

    $$\frac{1}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k + 1}{2})((\sqrt{2}a_d)^{2k + 1} / (2k + 1)! = (a - c) \frac{\sqrt{2}}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k}{2})((\sqrt{2}a_d)^{2k} / (2k + 1)!$$

*   **Case 2: $-a_d \leqslant b_d \leqslant 0$**
    The maximum expected return occurs when $b_d = -a_d$. The optimal $a_d$ is found by solving the equation:

    $$\frac{1}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k + 1}{2})((\sqrt{2}a_d)^{2k + 1} / (2k + 1)! = (a - \frac{c}{2}) \frac{\sqrt{2}}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k}{2})((\sqrt{2}a_d)^{2k} / (2k + 1)!$$

**Back Transform from the Dimensionless System:**

After calculating optimal thresholds in the dimensionless system, they are transformed back to the original system using the formula:

$$k = k_d \frac{\sigma}{\sqrt{2\mu}} + \theta$$

where $k_d$ can be $a_d$, $b_d$, $-a_d$, or $-b_d$, and $k$ corresponds to $a_s$, $b_s$, $a_l$, or $b_l$.

*   $a_s$, $b_s$ denote the entry and exit thresholds for a short position.
*   $a_l$, $b_l$ denote the entry and exit thresholds for a long position.

**Implementation Notes:**

*   **Initializing OU-Process Parameters:** Parameters can be set directly or fitted to data. The fitting method refers to pp. 12-13 in "Optimal Mean reversion Trading: Mathematical Analysis and Practical Applications" by Tim Leung and Xin Li.
*   **Getting Optimal Thresholds:** The `get_threshold_by_conventional_optimal_rule` and `get_threshold_by_new_optimal_rule` functions return a tuple $(a_s, b_s, a_l, b_l)$. An `initial_guess` parameter is used to aid `scipy.optimize` in solving the target equation, with a default value of $(c + 10^{-2})\sqrt{2\mu} / \sigma$.
*   **Calculating Metrics:** Functions are available to calculate performance metrics for the trading strategy.
*   **Plotting Comparison:** Functions allow observing the impact of transaction costs and risk-free rates on optimal thresholds and performance metrics.

**Code Examples (Illustrative):**

```python
import numpy as np
import matplotlib.pyplot as plt
from arbitragelab.time_series_approach.ou_optimal_threshold_zeng import (
    OUModelOptimalThresholdZeng,
)

ouotz = OUModelOptimalThresholdZeng()
# Init OU-process parameter
ouotz.construct_ou_ou_model_from_given_parameters(theta=3.4241, mu=0.0237, sigma=0.0081)

# Getting optimal thresholds by Conventional Optimal Rule.
a_s, b_s, a_l, b_l = ouotz.get_threshold_by_conventional_optimal_rule(c=0.02)
# a_s: 3.47...
# b_s: 3.42...
# a_l: 3.37...
# b_l: 3.42...

# Get the expected return and the variance for both long and short trades
# Short
ouotz.expected_return(a=a_s, b=b_s, c=0.02) # 0.0003...
ouotz.return_variance(a=a_s, b=b_s, c=0.02) # 2.54...e-05
# Long
ouotz.expected_return(a=a_l, b=b_l, c=0.02) # 0.0003...
ouotz.return_variance(a=a_l, b=b_l, c=0.02) # 2.207...e-05

# Getting optimal thresholds by New Optimal Rule.
a_s, b_s, a_l, b_l = ouotz.get_threshold_by_new_optimal_rule(c=0.02)
# a_s: 3.460...
# b_s: 3.38...
# a_l: 3.38...
# b_l: 3.460...

# Get the expected return and the variance for both long and short trade
# Short
ouotz.expected_return(a=a_s, b=b_s, c=0.02) # 0.00043...
ouotz.return_variance(a=a_s, b=b_s, c=0.02) # 3.467...e-05
# Long
ouotz.expected_return(a=a_l, b=b_l, c=0.02) # 0.00043...
ouotz.return_variance(a=a_l, b=b_l, c=0.02) # 3.467...e-05

# Setting a array contains transaction costs
c_list = np.linspace(0, 0.02, 30)
# Comparison of the expected return between the Conventional Optimal Rule and New Optimal Rule.
fig_con = ouotz.plot_target_vs_c(
    target="expected_return", method="conventional_optimal_rule", c_list=c_list
)
fig_new = ouotz.plot_target_vs_c(
    target="expected_return", method="new_optimal_rule", c_list=c_list
)
```

### Key Formulas Summary

1.  **Price of the Traded Security:**
    $p_t = e^{X_t};\quad X_{t_0} = x_0$
    where $X_t$ follows $dX_t = {\mu}({\theta} - X_t)dt + {\sigma}dW_t$.
    ($p_t$: price of traded security, $X_t$: log-price, $\theta$: long-term mean, $\mu$: mean-reversion speed, $\sigma$: amplitude of randomness, $W_t$: Wiener process).

2.  **Expected Trade Length:**
    $E[T] = \frac{1}{2\mu}\sum_{k=0}^{\infty} \Gamma(\frac{2k + 1}{2})((\sqrt{2}a_d)^{2k + 1} - (\sqrt{2}b_d)^{2k + 1})/ (2k + 1)!$
    ($E[T]$: expected trade length, $\mu$: mean-reversion speed, $\Gamma$: Gamma function, $a_d$: entry threshold, $b_d$: exit threshold in dimensionless system).

3.  **Mean Return per Unit of Time:**
    $\mu_s(a,\ b,\ c) = \frac{r(a,\ b,\ c)}{E [T]}$
    where $r(a,\ b,\ c) = (|a − b| − c)$.
    ($\mu_s$: mean return per unit of time, $r$: continuously compounded return, $E[T]$: expected trade length, $a$: entry threshold, $b$: exit threshold, $c$: transaction cost).

4.  **Back Transformation to Original System:**
    $k = k_d \frac{\sigma}{\sqrt{2\mu}} + \theta$
    ($k$: threshold in original system, $k_d$: threshold in dimensionless system, $\sigma$: amplitude of randomness, $\mu$: mean-reversion speed, $\theta$: long-term mean).

5.  **Optimal $a_d$ for Case 1 ($b_d=0$):**
    $\frac{1}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k + 1}{2})((\sqrt{2}a_d)^{2k + 1} / (2k + 1)! = (a - c) \frac{\sqrt{2}}{2}\sum_{k=0}^{\infty} \Gamma(\frac{2k}{2})((\sqrt{2}a_d)^{2k} / (2k + 1)!$
    ($a_d$: optimal entry threshold, $a$: entry threshold in original system, $c$: transaction cost, $\Gamma$: Gamma function).

### References

Zeng, Z. and Lee, C.-G., Pairs trading: optimal thresholds and profitability. Quantitative Finance, 14(11): 1881–1893.

---

# Statistical Arbitrage

## 30. PCA Approach

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/other_approaches/pca_approach.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/other_approaches/pca_approach.html)

This module describes how Principal Component Analysis (PCA) can be utilized to construct mean-reverting portfolios and generate trading signals. The core idea involves analyzing residuals or idiosyncratic components of returns and modeling them as mean-reverting processes. The methodology is largely based on the paper "Statistical Arbitrage in the U.S. Equities Market" by Marco Avellaneda and Jeong-Hyun Lee.

### Stock Return Decomposition

Stock returns ($R_i$) are decomposed into a systematic component and an idiosyncratic component. In a single-factor model, this is represented as:

$R_i = \beta_i F + \widetilde{R_i}$

Where:
*   $R_i$: Return for stock $i$
*   $\beta_i$: Beta of stock $i$
*   $F$: Return of a "market portfolio" (systematic factor)
*   $\widetilde{R_i}$: Idiosyncratic component of return for stock $i$

This can be extended to a multi-factor model with $m$ systematic factors:

$R_i = \sum^{m}_{j=1} \beta_{ij} F_j + \widetilde{R_i}$

Where:
*   $R_i$: Return for stock $i$
*   $\beta_{ij}$: Factor loading of stock $i$ on factor $j$
*   $F_j$: $j$-th systematic factor
*   $\widetilde{R_i}$: Idiosyncratic component of return for stock $i$
*   $m$: Number of systematic factors

### Market-Neutral Portfolio

A trading portfolio is considered market-neutral if the amounts ($Q_i$) invested in each of the $N$ stocks satisfy the following condition:

$\bar{\beta}_j = \sum^{N}_{i=1} \beta_{ij} Q_i = 0, j = 1, 2, ..., m.$

Where:
*   $\bar{\beta}_j$: Portfolio beta for factor $j$
*   $Q_i$: Amount invested in stock $i$
*   $N$: Number of stocks in the universe
*   $m$: Number of systematic factors

Consequently, a market-neutral portfolio is only affected by idiosyncratic returns:

$\sum^{N}_{i=1} Q_i R_i = \sum^{N}_{i=1} Q_i \widetilde{R_i}$

### PCA Approach Details

This approach, initially proposed by Jolliffe (2002), uses historical share price data for $N$ stocks over $M$ days. The stock return data ($R_{ik}$) on a date $t_0$ going back $M+1$ days is defined as:

$R_{ik} = \frac{S_{i(t_0 - (k - 1) \Delta t)} - S_{i(t_0 - k \Delta t)}}{S_{i(t_0 - k \Delta t)}}; k = 1, ..., M; i = 1, ..., N.$

Where:
*   $R_{ik}$: Return of stock $i$ at time $k$
*   $S_{it}$: Price of stock $i$ at time $t$ adjusted for dividends
*   $t_0$: Current date
*   $\Delta t$: Time interval (e.g., $1/252$ for daily observations)
*   $M$: Number of days in history (estimation window)
*   $N$: Number of stocks

Returns are standardized to account for varying volatilities:

$Y_{ik} = \frac{R_{ik} - \bar{R_i}}{\bar{\sigma_i}}$

Where:
*   $Y_{ik}$: Standardized return of stock $i$ at time $k$
*   $R_{ik}$: Return of stock $i$ at time $k$
*   $\bar{R_i}$: Mean return of stock $i$, calculated as $\bar{R_i} = \frac{1}{M} \sum^{M}_{k=1}R_{ik}$
*   $\bar{\sigma_i}$: Standard deviation of returns for stock $i$, calculated as $\bar{\sigma_i}^{2} = \frac{1}{M-1} \sum^{M}_{k=1} (R_{ik} - \bar{R_i})^{2}$

The empirical correlation matrix ($\rho_{ij}$) is then defined by:

$\rho_{ij} = \frac{1}{M-1} \sum^{M}_{k=1} Y_{ik} Y_{jk}$

It is crucial to standardize data before PCA, as PCA maximizes the variance of each component. The estimation window for the correlation matrix is typically fixed at 1 year (252 trading days).

### Eigenvalues and Eigenvectors

The eigenvalues of the correlation matrix are ranked in decreasing order:

$N \ge \lambda_1 \ge \lambda_2 \ge \lambda_3 \ge ... \ge \lambda_N \ge 0.$

And the corresponding eigenvectors are:

$v^{(j)} = ( v^{(j)}_1, ..., v^{(j)}_N ); j = 1, ..., N.$

For each index $j$, an "eigen portfolio" is constructed by investing amounts ($Q^{(j)}_i$) in each stock as:

$Q^{(j)}_i = \frac{v^{(j)}_i}{\bar{\sigma_i}}$

And the eigen portfolio returns ($F_{jk}$) are:

$F_{jk} = \sum^{N}_{i=1} \frac{v^{(j)}_i}{\bar{\sigma_i}} R_{ik}; j = 1, 2, ..., m.$

### Stochastic Differential Equation Model

In a multi-factor model, stock returns are assumed to satisfy the system of stochastic differential equations:

$\frac{dS_i(t)}{S_i(t)} = \alpha_i dt + \sum^{N}_{j=1} \beta_{ij} \frac{dI_j(t)}{I_j(t)} + dX_i(t),$

Where:
*   $S_i(t)$: Price of stock $i$ at time $t$
*   $\alpha_i$: Drift term for stock $i$
*   $\beta_{ij}$: Factor loadings
*   $I_j(t)$: $j$-th market index at time $t$
*   $dX_i(t)$: Idiosyncratic component of return for stock $i$

The idiosyncratic component of the return with drift ($\widetilde{X_i}(t)$) is:

$d \widetilde{X_i}(t) = \alpha_i dt + d X_i (t).$

### Ornstein-Uhlenbeck Process

The model for $X_i(t)$ is estimated as an Ornstein-Uhlenbeck (OU) process:

$dX_i(t) = \kappa_i (m_i - X_i(t))dt + \sigma_i dW_i(t), \kappa_i > 0.$

Where:
*   $X_i(t)$: Idiosyncratic component of return for stock $i$
*   $\kappa_i$: Speed of mean-reversion for stock $i$
*   $m_i$: Long-term mean of $X_i(t)$
*   $\sigma_i$: Volatility of $X_i(t)$
*   $dW_i(t)$: Wiener process (Brownian motion increment)

The parameters $\alpha_i, \kappa_i, m_i, \sigma_i$ are specific to each stock and are assumed to vary slowly over a chosen time-window (e.g., 60 days).

The expected 1-day return of a market long-short portfolio is:

$\alpha_i dt + \kappa_i (m_i - X_i(t))dt$

For fast mean-reversion, the condition is:

$\frac{1}{\kappa_i} \ll T_1$

Where $T_1$ is the estimation window to estimate residuals in years.

### PCA Trading Strategy

The strategy uses a default estimation window of 252 days for the correlation matrix and 60 days for residual estimation ($T_1 = 60/252$). A threshold for mean reversion speed is set such that the reversion time is less than $1/2$ period, implying $\kappa > 252/30 = 8.4$.

The equilibrium variance ($\sigma_{eq,i}$) for the process $X_i(t)$ is defined as:

$\sigma_{eq,i} = \frac{\sigma_i}{\sqrt{2 \kappa_i}}$

And the S-score ($s_i$) is defined as:

$s_i = \frac{X_i(t)-m_i}{\sigma_{eq,i}}$

The S-score measures the distance to the equilibrium of the cointegrated residual in units of standard deviations.

### Trading Signals

Trading signals are generated from the S-scores using the following rules:

*   Open a long position if $s_i < - \bar{s_{bo}}$
*   Close a long position if $s_i < + \bar{s_{bc}}$
*   Open a short position if $s_i > + \bar{s_{so}}$
*   Close a short position if $s_i > - \bar{s_{sc}}$

Empirical analysis suggests the following cutoffs:

*   $\bar{s_{bo}} = \bar{s_{so}} = 1.25$
*   $\bar{s_{bc}} = 0.75$
*   $\bar{s_{sc}} = 0.50$

### Implementation Example (Python Code Snippets)

```python
import pandas as pd
import numpy as np
from arbitragelab.other_approaches.pca_approach import PCAStrategy

# Getting the dataframe with time series of asset returns
data = pd.read_csv('X_FILE_PATH.csv', index_col=0, parse_dates = [0])

# The PCA Strategy class that contains all needed methods
pca_strategy = PCAStrategy()

# Simply applying the PCAStrategy with standard parameters
target_weights = pca_strategy.get_signals(data, k=8.4, corr_window=252,
                                          residual_window=60, sbo=1.25,
                                          sso=1.25, ssc=0.5, sbc=0.75,
                                          size=1)

# Or we can do individual actions from the PCA approach
# Standardizing the dataset
data_standardized, data_std = pca_strategy.standardize_data(data)

# Getting factor weights using the first 252 observations
data_252days = data[:252]
factorweights = pca_strategy.get_factorweights(data_252days)

# Calculating factor returns for a 60-day window from our factor weights
data_60days = data[(252-60):252]
factorret = pd.DataFrame(np.dot(data_60days, factorweights.transpose()),
                         index=data_60days.index)

# Calculating residuals for a set 60-day window
residual, coefficient = pca_strategy.get_residuals(data_60days, factorret)

# Calculating S-scores for each eigen portfolio for a set 60-day window
s_scores = pca_strategy.get_sscores(residual, k=8)
```

### Key Formulas Summary

1.  **Stock Return Decomposition (Multi-Factor Model):**
    $R_i = \sum^{m}_{j=1} \beta_{ij} F_j + \widetilde{R_i}$
    *   $R_i$: Returns for stock $i$
    *   $\beta_{ij}$: Factor loading of stock $i$ on factor $j$
    *   $F_j$: $j$-th systematic factor
    *   $\widetilde{R_i}$: Idiosyncratic component of return for stock $i$
    *   $m$: Number of systematic factors

2.  **Standardized Returns:**
    $Y_{ik} = \frac{R_{ik} - \bar{R_i}}{\bar{\sigma_i}}$
    *   $Y_{ik}$: Standardized return of stock $i$ at time $k$
    *   $R_{ik}$: Return of stock $i$ at time $k$
    *   $\bar{R_i}$: Mean return of stock $i$
    *   $\bar{\sigma_i}$: Standard deviation of returns for stock $i$

3.  **Ornstein-Uhlenbeck Process for Idiosyncratic Component:**
    $dX_i(t) = \kappa_i (m_i - X_i(t))dt + \sigma_i dW_i(t), \kappa_i > 0.$
    *   $X_i(t)$: Idiosyncratic component of return for stock $i$
    *   $\kappa_i$: Speed of mean-reversion for stock $i$
    *   $m_i$: Long-term mean of $X_i(t)$
    *   $\sigma_i$: Volatility of $X_i(t)$
    *   $dW_i(t)$: Wiener process

4.  **S-score:**
    $s_i = \frac{X_i(t)-m_i}{\sigma_{eq,i}}$
    *   $s_i$: S-score for stock $i$
    *   $X_i(t)$: Idiosyncratic component of return for stock $i$
    *   $m_i$: Long-term mean of $X_i(t)$
    *   $\sigma_{eq,i}$: Equilibrium variance for $X_i(t)$, defined as $\sigma_{eq,i} = \frac{\sigma_i}{\sqrt{2 \kappa_i}}$

5.  **Trading Signal for Opening Long Position:**
    Open a long position if $s_i < - \bar{s_{bo}}$
    *   $s_i$: S-score for stock $i$
    *   $\bar{s_{bo}}$: Cutoff for opening a long position (e.g., 1.25)

### References

Avellaneda, M. and Lee, J.H., 2010. Statistical arbitrage in the US equities market. Quantitative Finance, 10(7), pp.761-782.
Jolliffe, I. T., Principal Components Analysis, Springer Series in Statistics, Springer-Verlag, Heidelberg, 2002.

---

# Distance

## 31. Pearson Approach

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/distance_approach/pearson_approach.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/distance_approach/pearson_approach.html)

The Pearson Approach is an adjustment to the original distance approach for pairs trading, proposed by Chen et al. (2012). This method utilizes Pearson correlation on return levels for forming pairs. The core idea is to identify return divergence between a single stock's return and its pairs-portfolio returns, with the hypothesis that such divergence is expected to reverse in the subsequent period.

### Return Divergence

The **Return Divergence** (\\(D\_{i j t}\\)) is a key variable capturing the difference between a stock's return and its pairs-portfolio return. It is defined by the following equation:

$$D_{i j t}=\beta\left(R_{i t}-R_{f}\right)-\left(R_{j t}-R_{f}\right)$$

Where:
*   \\(D\_{i j t}\\) represents the return divergence between stock \\(i\\) and its pairs-portfolio \\(j\\) at time \\(t\\).
*   \\(\beta\\) denotes the regression coefficient of stock's monthly return \\(R\_{i t}\\) on its pairs-portfolio return \\(R\_{j t}\\).
*   \\(R\_{i t}\\) is the monthly return of stock \\(i\\) at time \\(t\\).
*   \\(R\_{j t}\\) is the monthly return of pairs-portfolio \\(j\\) at time \\(t\\).
*   \\(R\_{f}\\) is the risk-free rate.

### Pairs Portfolio Formation

In the formation period, pairwise return correlations are calculated for all possible pairs. To reduce computational burden, monthly stock returns data is used. For each stock, \\(n\\) stocks with the highest correlations are selected as its pairs. The returns of these pairs, referred to as pairs portfolios, are calculated using two weighting metrics:

1.  **Equal-weighted portfolio**: The returns are computed as the equal-weighted average returns of the top \\(n\\) pairs of stocks.
2.  **Correlation-weighted portfolio**: The weights are calculated based on the stock's correlation values to each of the pairs using the formula:

$$w_{k}=\frac{\rho_{k}}{\sum_{i=1}^{n} \rho_{i}}$$

Where:
*   \\(w\_{k}\\) is the weight of stock \\(k\\) in the portfolio.
*   \\(\rho\_{k}\\) is the correlation of stock \\(k\\) and one of its pairs.
*   \\(\sum_{i=1}^{n} \rho_{i}\\) is the sum of correlations for \\(n\\) pairs.

### Beta Calculation

The \\(\beta\\) coefficient, used in the return divergence formula, is derived from the monthly return of the stock and its pairs portfolio. This is achieved through linear regression, where the stock return is the independent variable and the pairs portfolio return is the dependent variable. The \\(\beta\\) is then stored for future use in trading.

### Trading Signal Generation

Trading signals are generated by calculating the return divergence for each stock. Stocks are sorted in descending order based on their previous month’s return divergence. Trading signals are then determined as follows:

*   **Long Position**: The top \\(p\\%\\) of the sorted stocks are chosen for a long position (signal: 1).
*   **Short Position**: The bottom \\(q\\%\\) of the sorted stocks are chosen for a short position (signal: -1).
*   **No Position**: Stocks not selected for long or short positions (signal: 0).

For a dollar-neutral portfolio, \\(p\\%\\) and \\(q\\%\\) should be equal.

### Results Output

The `PearsonStrategy` class provides methods to retrieve results:
*   `get_trading_signal()`: Outputs trading signals on a monthly basis (1 for long, -1 for short, 0 for closed).
*   `get_beta_dict()`: Outputs the calculated \\(\beta\\) (regression coefficients) for each stock during the formation period.
*   `get_pairs_dict()`: Outputs the top \\(n\\) pairs selected for each stock during the formation period.

### Key Formulas Summary

1.  **Return Divergence**:
    $$D_{i j t}=\beta\left(R_{i t}-R_{f}\right)-\left(R_{j t}-R_{f}\right)$$
    Where:
    *   \\(D\_{i j t}\\) = Return Divergence
    *   \\(\beta\\) = Regression coefficient
    *   \\(R\_{i t}\\) = Monthly return of stock \\(i\\)
    *   \\(R\_{j t}\\) = Monthly return of pairs-portfolio \\(j\\)
    *   \\(R\_{f}\\) = Risk-free rate

2.  **Correlation-Weighted Portfolio Weight**:
    $$w_{k}=\frac{\rho_{k}}{\sum_{i=1}^{n} \rho_{i}}$$
    Where:
    *   \\(w\_{k}\\) = Weight of stock \\(k\\) in the portfolio
    *   \\(\rho\_{k}\\) = Correlation of stock \\(k\\) and one of its pairs
    *   \\(\sum_{i=1}^{n} \rho_{i}\\) = Sum of correlations for \\(n\\) pairs

### References

Chen, H., Chen, S., Chen, Z. and Li, F., 2019. Empirical investigation of an equity pairs trading strategy. Management Science, 65(1), pp.370-389.
Perlin, M.S., 2009. Evaluation of pairs-trading strategy at the Brazilian financial market. Journal of Derivatives & Hedge Funds, 15(2), pp.122-136.
Krauss, C., 2017. Statistical arbitrage pairs trading strategies: Review and outlook. Journal of Economic Surveys, 31(2), pp.513-545.

---

# Regime Switching, Statistical Arbitrage

## 32. Regime-Switching Arbitrage Rule

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/regime_switching_arbitrage_rule.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/time_series_approach/regime_switching_arbitrage_rule.html)

The strategy models the series $X_t$ formed by the trading pair as:

$$X_t = \mu_{s_t} + \epsilon_t$$

where $E[\epsilon_t] = 0$ and $\sigma^2_{\epsilon_t} = \sigma^2_{s_t}$. Here, $s_t$ denotes the current regime.

A two-state, first-order Markov-switching process for $s_t$ is considered with the following transition probabilities:

$$\begin{split}\Bigg\{ \begin{matrix} prob[s_t = 1 | s_{t-1} = 1] = p \\ prob[s_t = 2 | s_{t-1} = 2] = q \\ \end{matrix}\end{split}$$

where regime $1$ indicates a regime with a higher mean ($\mu_1$) and regime $2$ indicates a regime with a lower mean ($\mu_2$).

The trading signal $z_t$ is determined as follows:

**Case 1: current regime = 1**

$$\begin{split}z_t = \left\{\begin{array}{l} -1,\\ if\\ X_t \geq \mu_1 + \delta \cdot \sigma_1 \\ +1,\\ if\\ X_t \leq \mu_1 - \delta \cdot \sigma_1 \wedge P(s_t = 1 | X_t) \geq \rho \\ 0,\\ otherwise \end{array}\right.\end{split}$$

**Case 2: current regime = 2**

$$\begin{split}z_t = \left\{\begin{array}{l} -1,\\ if\\ X_t \geq \mu_2 + \delta \cdot \sigma_2 \wedge P(s_t = 2 | X_t) \geq \rho\\ +1,\\ if\\ X_t \leq \mu_2 - \delta \cdot \sigma_2 \\ 0,\\ otherwise \end{array}\right.\end{split}$$

Here, $P(\cdot)$ denotes the smoothed probabilities for each state, $\delta$ is the standard deviation sensitivity parameter, and $\rho$ is the probability threshold of the trading strategy.

More specifically, the trading signal rules are:

**Case 1: current regime = 1**

$$\begin{split}\left\{\begin{array}{l} Open\\ a\\ long\\ trade,\\ if\\ X_t \leq \mu_1 - \delta \cdot \sigma_1 \wedge P(s_t = 1 | X_t) \geq \rho \\ Close\\ a\\ long\\ trade,\\ if\\ X_t \geq \mu_1 + \delta \cdot \sigma_1 \\ Open\\ a\\ short\\ trade,\\ if\\ X_t \geq \mu_1 + \delta \cdot \sigma_1 \\ Close\\ a\\ short\\ trade,\\ if\\ X_t \leq \mu_1 - \delta \cdot \sigma_1 \wedge P(s_t = 1 | X_t) \geq \rho \\ Do\\ nothing,\\ otherwise \end{array}\right.\end{split}$$

**Case 2: current regime = 2**

$$\begin{split}\left\{\begin{array}{l} Open\\ a\\ long\\ trade,\\ if\\ X_t \leq \mu_2 - \delta \cdot \sigma_2 \\ Close\\ a\\ long\\ trade,\\ if\\ X_t \geq \mu_2 + \delta \cdot \sigma_2 \wedge P(s_t = 2 | X_t) \geq \rho\\ Open\\ a\\ short\\ trade,\\ if\\ X_t \geq \mu_2 + \delta \cdot \sigma_2 \wedge P(s_t = 2 | X_t) \geq \rho\\ Close\\ a\\ short\\ trade,\\ if\\ X_t \leq \mu_2 - \delta \cdot \sigma_2 \\ Do\\ nothing,\\ otherwise \end{array}\right.\end{split}$$

**Spread Series Construction**

The paper suggests using $\frac{P^A_t}{P^B_t}$ as the spread series. Other formulae for constructing the spread series include $(P^A_t/P^A_0) - \beta \cdot (P^B_t/P^B_0)$ and $ln(P^A_t/P^A_0) - \beta \cdot ln(P^B_t/P^B_0)$.

**Parameter Estimation**

The parameters $\mu_1$, $\mu_2$, $\sigma_1$, $\sigma_2$ and the current regime are estimated by fitting the Markov regime-switching model to the spread series with a rolling time window.

### Key Formulas Summary

1. **Series Formed by the Trading Pair**: $X_t = \mu_{s_t} + \epsilon_t$
   - $X_t$: series formed by the trading pair
   - $\mu_{s_t}$: mean of the series in regime $s_t$
   - $\epsilon_t$: error term with $E[\epsilon_t] = 0$ and variance $\sigma^2_{\epsilon_t} = \sigma^2_{s_t}$
   - $s_t$: current regime

2. **Markov Regime-Switching Transition Probabilities**:
   $$\begin{split}\Bigg\{ \begin{matrix} prob[s_t = 1 | s_{t-1} = 1] = p \\ prob[s_t = 2 | s_{t-1} = 2] = q \\ \end{matrix}\end{split}$$
   - $p$: probability of staying in regime 1
   - $q$: probability of staying in regime 2
   - Regime 1: higher mean ($\mu_1$)
   - Regime 2: lower mean ($\mu_2$)

3. **Trading Signal $z_t$ (Case 1: current regime = 1)**:
   $$\begin{split}z_t = \left\{\begin{array}{l} -1,\\ if\\ X_t \geq \mu_1 + \delta \cdot \sigma_1 \\ +1,\\ if\\ X_t \leq \mu_1 - \delta \cdot \sigma_1 \wedge P(s_t = 1 | X_t) \geq \rho \\ 0,\\ otherwise \end{array}\right.\end{split}$$
   - $P(\cdot)$: smoothed probabilities for each state
   - $\delta$: standard deviation sensitivity parameter
   - $\rho$: probability threshold

4. **Trading Signal $z_t$ (Case 2: current regime = 2)**:
   $$\begin{split}z_t = \left\{\begin{array}{l} -1,\\ if\\ X_t \geq \mu_2 + \delta \cdot \sigma_2 \wedge P(s_t = 2 | X_t) \geq \rho\\ +1,\\ if\\ X_t \leq \mu_2 - \delta \cdot \sigma_2 \\ 0,\\ otherwise \end{array}\right.\end{split}$$
   - $P(\cdot)$: smoothed probabilities for each state
   - $\delta$: standard deviation sensitivity parameter
   - $\rho$: probability threshold

### References

Bock, M. and Mestel, R. (2008) - A regime-switching relative value arbitrage rule. Operations Research Proceedings 2008, pages 9–14. Springer.

---

# OU Model

## 33. Trading Under the Ornstein-Uhlenbeck Model

*Documentation:* [https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/ou_model.html](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/optimal_mean_reversion/ou_model.html)

The document "Trading Under the Ornstein-Uhlenbeck Model" from ArbitrageLab provides a detailed mathematical framework for optimal mean-reversion trading strategies. The core of the strategy relies on modeling a mean-reverting portfolio using the Ornstein-Uhlenbeck (OU) process.

**1. Portfolio Definition**
The portfolio value $X_t^{\alpha,\beta}$ is constructed by holding $\alpha = \frac{A}{S_0^{(1)}}$ of a risky asset $S^{(1)}$ and shorting $\beta = \frac{B}{S_0^{(2)}}$ of another risky asset $S^{(2)}$. The portfolio value at time $t$ is given by:
$$X_t^{\alpha,\beta} = \alpha S^{(1)} - \beta S^{(2)}, t \geq 0$$
Here, $A$ and $B$ represent initial investment amounts, and $S_0^{(1)}$ and $S_0^{(2)}$ are the initial prices of the respective assets. For mean-reversion analysis, the ratio between $\alpha$ and $\beta$ is crucial. Without loss of generality, $\alpha$ can be set to a constant (e.g., A = $1), and $\beta$ is varied to find the optimal strategy $(\alpha,\beta^*)$.

**2. Ornstein-Uhlenbeck Process**
The Ornstein-Uhlenbeck process is established through the following Stochastic Differential Equation (SDE):
$$dX_t = \mu(\theta - X_t)dt + \sigma dB_t, \quad \mu, \sigma > 0, \quad \theta \in \mathbb{R}, \quad B \text{ - a standard Brownian motion}$$
Where:
*   $\theta$: Represents the **long-term mean level** around which future trajectories of $X$ will evolve.
*   $\mu$: Denotes the **speed of reversion**, characterizing how quickly trajectories regroup around $\theta$.
*   $\sigma$: Is the **instantaneous volatility**, measuring the amplitude of randomness in the system. Higher values indicate more randomness.
*   $B_t$: A standard Brownian motion.

**3. Probability Density Function (PDF) of the OU Process**
Under the OU model, the probability density function of $X_t$ for an increment $\Delta t = t_i - t_{i-1}$ is given by:
$$f^{OU} (x_i|x_{i-1};\theta,\mu,\sigma) = \frac{1}{\sqrt{2\pi\tilde{\sigma}^2}} \exp\left(-\frac{(x_i - x_{i-1} e^{-\mu\Delta t} - \theta (1 - e^{-\mu \Delta t}))^2}{2 \tilde{\sigma}^2}\right)$$
with the constant $\tilde{\sigma}^2$ defined as:
$$\tilde{\sigma}^2 = \sigma^2 \frac{1 - e^{-2\mu\Delta t}}{2\mu}$$

**4. Model Fitting and Maximum Likelihood Estimation (MLE)**
To fit the OU model to observed portfolio values $(x_i^{\alpha\beta})_{i = 0,1,\cdots,n}$ over an $n$-day period, the average log-likelihood function is defined as:
$$\ell (\theta,\mu,\sigma|x_0^{\alpha\beta},x_1^{\alpha\beta},\cdots,x_n^{\alpha\beta}) := \frac{1}{n}\sum_{i=1}^{n} \ln f^{OU}(x_i|x_{i-1};\theta,\mu,\sigma)$$
This expands to:
$$= -\frac{1}{2} \ln(2 \pi) - \ln(\tilde{\sigma}) - \frac{1}{2\pi\tilde{\sigma}^2}\sum_{i=1}^{n} \[x_i^{\alpha\beta} - x_{i-1}^{\alpha\beta} e^{-\mu \Delta t} - \theta (1 - e^{-\mu \Delta t})\]^2$$
Maximizing this log-likelihood function using MLE allows for the determination of optimal model parameters $(\theta^*, \mu^*, \sigma^*)$. For every $\alpha$, the optimal $\beta^*$ is chosen by:
$$\beta^* = \underset{\beta}{\arg\max}\ \hat{\ell}(\theta^*,\mu^*,\sigma^*|x_0^{\alpha\beta},x_1^{\alpha\beta},\cdots, x_n^{\alpha\beta})$$

**5. Optimal Timing of Trades - Optimal Stopping Problem**

**a. Optimal Liquidation Problem (Default)**
For an investor with a position following an OU process $(X_t)_{t>0}$, the goal is to maximize the expected discounted value upon closing the position at time $\tau$, receiving $X_\tau$ and paying a transaction cost $c_s \in \mathbb{R}$. The optimal stopping problem is:
$$V(x) = \underset{\tau \in T}{\sup} \mathbb{E}_x({e^{-r \tau} (X_\tau - c_s)| X_0 = x})$$
Where $T$ is the set of all possible stopping times, and $r > 0$ is the constant discount rate. $V(x)$ is the expected liquidation value.

Theorem 2.6 (p.23) provides the solution:
$$V(x) = \begin{cases} (b^* - c_s) \frac{F(x)}{F(b^*)} , & \mbox{if } x \in (-\infty,b^*)\\ x - c_s, & \mbox{ otherwise} \end{cases}$$
The optimal liquidation level $b^*$ is found from the equation:
$$F(b) - (b - c_s)F'(b) = 0$$
The corresponding optimal liquidation time is:
$$\tau^* = \inf \[t\geq0:X_t \geq b^*\]$$

**b. Optimal Entry Timing Problem (Default)**
Combining the current price and transaction cost $c_b$ with $V(x)$, the optimal entry problem is formalized as:
$$J(x) = \underset{\nu \in T}{\sup} \mathbb{E}_x({e^{-\hat{r} \tau} (V(X_\nu) - X_\nu - c_b)| X_0 = x})$$
with $\hat{r}>0$ and $c_b \in \mathbb{R}$. The investor aims to maximize the expected difference between the current position price $x_\nu$ and its expected liquidation value $V(X_\nu)$, minus the transaction cost $c_b$.

Theorem 2.10 (p.27) provides the solution:
$$J(x) = \begin{cases} V(x) - x - c_b, & \mbox{if } x \in (-\infty,d^*)\\ \frac{V(d^*) - d^* - c_b}{\hat{G}(d^*)}, & \mbox{if } x \in (d^*, \infty) \end{cases}$$
The optimal entry level $d^*$ is found from the equation:
$$\hat{G}(d)(V'(d) - 1) - \hat{G}'(d)(V(d) - d - c_b) = 0$$
Where "$\hat{\ }$" indicates the use of transaction cost and discount rate for entering.

**c. OU Process Infinitesimal Generator and Classical Solutions**
To solve these optimal stopping problems, the OU process infinitesimal generator is defined as:
$$L = \frac{\sigma^2}{2} \frac{d^2}{dx^2} + \mu(\theta - x) \frac{d}{dx}$$
And the classical solution of the differential equation $L u(x) = ru(x)$ involves functions $F(x)$ and $G(x)$:
$$\begin{align*}
F(x) &= \int_{0}^{\infty} u^{ \frac{r}{\mu} - 1} e^{\sqrt{\frac{2\mu}{\sigma^2}}(x - \theta)u - \frac{u^2}{2}}du\\
G(x) &= \int_{0}^{\infty} u^{\frac{r}{\mu} - 1} e^{\sqrt{\frac{2\mu}{\sigma^2}} (\theta - x)u - \frac{u^2}{2}}du
\end{align*}$$

**6. Optimal Stopping Problem with Stop-Loss**

**a. Optimal Liquidation Problem with Stop-Loss**
When a stop-loss level $L$ is included, Theorem 2.13 (p.31) gives the solution for the optimal liquidation problem:
$$V(x) = \begin{cases} C F(x)+D G(x) , & \mbox{if } x \in (-\infty,b^*)\\ x - c_s, & \mbox{ otherwise} \end{cases}$$
The optimal liquidation level $b_L^*$ is found from the equation:
$$\begin{gather*}
F'(b) \[(L - c_s) G(b) - (b - c_s) G(L)\]\\
+ G'(b) \[(b - c_s) F(L) - (L - c_s) F(b)\]\\
- G(b) F(L) - G(L)F(b) = 0
\end{gather*}$$
The corresponding optimal liquidation time is:
$$\tau^* = \inf \[t\geq0:X_t \geq b^*\]$$
Helper functions $C$ and $D$ are defined as:
$$\begin{align*}
C &= \frac{(b_L^* - c_s) G(L) - ( L - c_s) G(b^*)}{F(b_L^*)G(L) - F(L)G(b_L^*)}\\
D &= \frac{(L - c_s) F(L) - ( b_L^* - c_s) F(b^*)}{F(b_L^*)G(L) - F(L)G(b_L^*)}
\end{align*}$$

**b. Optimal Entry Timing Problem with Stop-Loss**
Theorem 2.42 (p.35) provides the solution for the optimal entry timing problem with a stop-loss:
$$J_L(x) = \begin{cases} P\hat{F}(x), & \mbox{if } x \in (-\infty,a_L^*)\\ V_L(x) - x - c_b, & \mbox{if } x \in (a_L^*, d_L^*)\\ Q\hat{G}(x), & \mbox{if } x \in (d_L^*, \infty)\end{cases}$$
The optimal entry interval $(a_L^*,d_L^*)$ is found using the respective equations:
$$\begin{gather*}
\hat{G}(d)(V_L'(d) - 1) - \hat{G}'(d)(V_L(d) - d - c_b) = 0\\
\hat{F}(a)(V_L'(a) - 1) - \hat{F}'(a)(V_L(a) - a - c_b) = 0
\end{gather*}$$

**7. Signal Rules**
General rule for the use of the optimal levels:
*   If not bought, buy the portfolio as soon as portfolio price reaches the optimal entry level (enters the interval).
*   If bought, liquidate the position as soon as portfolio price reaches the optimal liquidation level.

### Key Formulas Summary

1. Ornstein-Uhlenbeck Process SDE:
   $dX_t = \mu(\theta - X_t)dt + \sigma dB_t$
   Where:
   - $\theta$: long-term mean level
   - $\mu$: speed of reversion
   - $\sigma$: instantaneous volatility
   - $B_t$: standard Brownian motion

2. Probability Density Function (PDF) of $X_t$ under OU model:
   $f^{OU} (x_i|x_{i-1};\theta,\mu,\sigma) = \frac{1}{\sqrt{2\pi\tilde{\sigma}^2}} \exp\left(-\frac{(x_i - x_{i-1} e^{-\mu\Delta t} - \theta (1 - e^{-\mu \Delta t}))^2}{2 \tilde{\sigma}^2}\right)$
   with $\tilde{\sigma}^2 = \sigma^2 \frac{1 - e^{-2\mu\Delta t}}{2\mu}$

3. Average Log-Likelihood Function:
   $\ell (\theta,\mu,\sigma|x_0^{\alpha\beta},x_1^{\alpha\beta},\cdots,x_n^{\alpha\beta}) := \frac{1}{n}\sum_{i=1}^{n} \ln f^{OU}(x_i|x_{i-1};\theta,\mu,\sigma)$

4. Optimal Liquidation Problem (Default):
   $V(x) = \begin{cases} (b^* - c_s) \frac{F(x)}{F(b^*)} , & \mbox{if } x \in (-\infty,b^*)\\ x - c_s, & \mbox{ otherwise} \end{cases}$
   The optimal liquidation level $b^*$ is found from: $F(b) - (b - c_s)F'(b) = 0$

5. Optimal Entry Timing Problem (Default):
   $J(x) = \begin{cases} V(x) - x - c_b, & \mbox{if } x \in (-\infty,d^*)\\ \frac{V(d^*) - d^* - c_b}{\hat{G}(d^*)}, & \mbox{if } x \in (d^*, \infty) \end{cases}$
   The optimal entry level $d^*$ is found from: $\hat{G}(d)(V'(d) - 1) - \hat{G}'(d)(V(d) - d - c_b) = 0

### References

Leung, T.S.T. and Li, X., 2015. Optimal mean reversion trading: Mathematical analysis and practical applications (Vol. 1). World Scientific.

---
