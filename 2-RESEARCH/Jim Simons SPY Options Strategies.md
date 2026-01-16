# **The Architecture of Alpha: Deconstructing Renaissance Technologies’ Quantitative Frameworks for SPY Options Markets**

## **1\. Executive Abstract: The Renaissance Paradigm**

The history of financial markets is bifurcated by the emergence of Renaissance Technologies (RenTec) and its flagship Medallion Fund. Founded by James Simons, a geometer and codebreaker who transitioned from academia to finance, RenTec dismantled the prevailing orthodoxy of fundamental analysis. While the broader market operated on narratives—earnings reports, geopolitical tensions, and macroeconomic forecasts—RenTec operated on the premise that markets are complex, noisy systems governed by hidden probabilistic states and recurring statistical anomalies. The firm’s success, characterized by an average annualized return of approximately 66% before fees (39% net) from 1988 to 2018, serves as empirical validation of the quantitative hypothesis: that price movements are not random walks, but decipherable signals obscured by stochastic noise.1

For the institutional or sophisticated retail practitioner focusing on the SPDR S\&P 500 ETF Trust (SPY), the objective is not to replicate Medallion’s infrastructure—which relies on nanosecond latency and proprietary dark pool access—but to adopt its *architectural meta-strategies*. The "Simons Approach" is not a single trading setup but a comprehensive epistemological framework that prioritizes data integrity, statistical significance over causal logic, and the systematic exploitation of structural market inefficiencies like volatility dispersion and mean reversion.3

This report provides an exhaustive technical analysis of how Simons’ foundational principles can be translated into the liquid, leverage-accessible domain of SPY options. By deconstructing the mathematical pillars attributed to RenTec—specifically Hidden Markov Models (HMM) for regime detection, Kernel Regression for non-parametric trend estimation, and Volatility Dispersion Arbitrage for correlation trading—we establish a rigorous methodology for extracting alpha from the S\&P 500 volatility surface. The analysis moves beyond surface-level technical analysis to explore the physics of financial time series, the optimization of position sizing via the Kelly Criterion, and the algorithmic execution required to capture the elusive "50.75%" edge that compounds into geometric wealth.5

## ---

**2\. Epistemological Foundations of Quantitative Trading**

To implement a trading system derived from Renaissance Technologies, one must first dismantle the cognitive biases that plague human decision-making. Simons did not view the market as a battle of bulls and bears, but as a physics problem involving signal processing. The transition from a "fundamental" mindset to a "quantitative" mindset is the prerequisite for applying these strategies effectively.

### **2.1 The "Black Box" and the Rejection of Narrative Causality**

The most radical departure in Simons' philosophy is the rejection of the "why." Traditional asset management seeks to understand the driver of a price move: "Stocks are up because the Federal Reserve paused rates." RenTec’s researchers, many of whom were astronomers and physicists, viewed this as a distraction. Their approach assumes that if a pattern is statistically significant—meaning it has a p-value below 0.01 and creates a profit probability distinct from 50/50—it is valid, regardless of the underlying economic rationale.6

This "Black Box" epistemology is critical for SPY options trading. The pricing of an option is derived from the interaction of spot price, time, volatility, and interest rates. These variables interact in non-linear ways (Gamma, Vanna, Charm). A trader seeking a narrative explanation for a shift in the volatility skew will often arrive too late to exploit it. The quantitative trader simply observes the skew deviation, calculates the z-score relative to historical norms, and executes the reversion trade. The model is the authority; the trader is merely the executioner. This discipline eliminates emotional interference, a core tenant of the Simons strategy.5

### **2.2 The Law of Large Numbers: The 50.75% Edge**

A pervasive myth in retail trading is the necessity of a high win rate (e.g., 90%). Simons explicitly debunked this, revealing that Medallion’s win rate was often barely above a coin flip—approximately 50.75%.3 The mathematical lever that transforms a 0.75% edge into billions of dollars is the Law of Large Numbers.

$$E \= N \\times (P\_{win} \\times \\text{Avg}\_{win} \- P\_{loss} \\times \\text{Avg}\_{loss})$$  
In this equation, $N$ (the number of occurrences) is as important as the edge itself. RenTec executes hundreds of thousands of trades per day. For the SPY options trader, this implies a structural shift away from "conviction trades"—where a large percentage of capital is bet on a single outcome—toward a high-frequency (in the manual sense) engagement with the market. Instead of holding one large position for a month, the strategy dictates holding dozens of smaller, uncorrelated positions (e.g., laddered Iron Condors, calendar spreads across different expiries) to allow the statistical expectancy to manifest over time.5 The "edge" in options trading often comes from the Variance Risk Premium (VRP)—the tendency of Implied Volatility (IV) to overstate Realized Volatility (RV). This premium is small and noisy; capturing it requires volume and consistency, mirroring Simons' industrial approach to profit generation.

### **2.3 Intellectual Arbitrage: Importing Tools from Physics and Cryptography**

RenTec’s hiring policy was notorious for excluding Wall Street veterans. Simons hired cryptographers, speech recognition experts, and astronomers.2 The logic was that financial data is simply a noisy signal, similar to the background radiation of the universe or a garbled audio transmission.

* **Speech Recognition:** Leonard Baum, a RenTec pioneer, developed the Baum-Welch algorithm for Hidden Markov Models (HMM) to decipher speech patterns. In finance, "speech" is the market regime (Bull, Bear, Chop), and the "audio signal" is the price returns.  
* **Astronomy:** Astronomers specialize in filtering weak signals from massive noise. In options trading, the "signal" might be a slight mispricing in the OTM put skew, buried under the "noise" of general market panic.  
* **Cryptography:** Codebreakers look for non-random distributions in seemingly random cyphertext. The market often acts randomly, but subtle correlations (e.g., between SPY and XLK) reveal the "key" to the next move.

By adopting these tools, we move the analysis of SPY options out of the realm of "technical analysis" (lines on a chart) and into the realm of "statistical learning".1

## ---

**3\. Data Infrastructure: The Prerequisite for Analysis**

Before a single model can be run, the data environment must be established. Simons emphasized "cleaning the data" as a primary competitive advantage. In the 1980s, this meant digitizing paper tapes. Today, it means normalizing the vast flow of tick data and option chains.

### **3.1 The Reality of Financial Time Series**

SPY prices are not normally distributed; they exhibit fat tails (excess kurtosis) and volatility clustering (heteroskedasticity). Standard models like Black-Scholes assume a log-normal distribution, which leads to the severe underpricing of tail risk (crashes). A Simons-inspired infrastructure must account for this.

* **Log-Returns vs. Simple Returns:** Algorithms must ingest log-returns ($ln(P\_t / P\_{t-1})$) to ensure time-additivity and stationarity, crucial for HMM and Kernel methods.  
* **Volatility Surface Data:** The "price" of SPY is less important than the "price of risk" embedded in the options chain. The infrastructure must track the **Implied Volatility Surface**—a 3D matrix of IV across strikes and expirations. Anomalies in this surface (e.g., a "kink" in the smile) are often the signals for arbitrage.11

### **3.2 Signal Construction: From Raw Data to Features**

The "Simons Strategy" involves transforming raw data into predictive features. For SPY options, key features include:

* **VIX Term Structure:** The ratio of short-term VIX (VIX9D) to medium-term VIX (VIX). A ratio \> 1.0 suggests backwardation (panic), a signal for specific option strategies.  
* **Skew Index:** The relative price of OTM puts versus OTM calls. Changes in skew often precede changes in price direction.  
* **Dark Pool Signatures:** While retail traders lack direct access to proprietary RenTec feeds, analyzing volume profile and "block trade" data on SPY can serve as a proxy for institutional flow.13

## ---

**4\. Mathematical Pillar I: Hidden Markov Models (HMM) for Regime Detection**

The central challenge in quantitative trading is "stationarity." Financial data is non-stationary; its statistical properties (mean, variance) change over time. A moving average crossover that works in a trend fails in a chop. RenTec solved this by modeling the market not as a single process, but as a system that switches between distinct "hidden" states or regimes. The tool for this is the Hidden Markov Model (HMM).9

### **4.1 Theoretical Mechanics of HMM**

An HMM assumes that the observable data (SPY returns, VIX levels) is generated by a latent (hidden) variable—the market state. We cannot see the state, but we can infer it.

#### **4.1.1 The Architecture of the State Space**

We define a market model with $K$ states. For SPY options, a 3-state model is robust:

1. **State 0 (Low Volatility / Bull):** Characterized by positive mean returns ($\\mu \> 0$) and low variance ($\\sigma^2 \\approx low$).  
2. **State 1 (High Volatility / Correction):** Characterized by mixed returns ($\\mu \\approx 0$) and high variance ($\\sigma^2 \\approx high$).  
3. **State 2 (Crisis / Crash):** Characterized by highly negative returns ($\\mu \\ll 0$) and extreme variance ($\\sigma^2 \\approx extreme$).

#### **4.1.2 The Transition Matrix**

The model calculates a Transition Probability Matrix $A$, where $a\_{ij}$ is the probability of moving from State $i$ to State $j$.

$$A \= \\begin{pmatrix} P(0 \\to 0\) & P(0 \\to 1\) & P(0 \\to 2\) \\\\ P(1 \\to 0\) & P(1 \\to 1\) & P(1 \\to 2\) \\\\ P(2 \\to 0\) & P(2 \\to 1\) & P(2 \\to 2\) \\end{pmatrix}$$

Crucially, markets exhibit "stickiness." If the market is in State 0 today, it is highly likely ($P \> 0.9$) to be in State 0 tomorrow. However, when it transitions to State 1, the volatility dynamics shift instantly. The HMM detects this shift faster than a lagging moving average.16

#### **4.1.3 The Baum-Welch Algorithm**

The model is trained using the **Baum-Welch Algorithm**, a specialized case of the Expectation-Maximization (EM) algorithm.

* **E-Step:** Estimate the probability of being in each state at each time step given the current parameters.  
* M-Step: Update the parameters (means, variances, transition probabilities) to maximize the likelihood of the observed data.  
  This iterative process allows the model to "learn" the definitions of Bull, Bear, and Chop directly from the data without human labeling.18

### **4.2 Application to SPY Option Strategy Selection**

The output of the HMM is a vector of probabilities (e.g., \[0.85, 0.10, 0.05\]) representing the likelihood of each regime. This is the **Strategy Selector**.

| Detected Regime | Market Characteristics | Optimal SPY Option Strategy | Greeks Profile |
| :---- | :---- | :---- | :---- |
| **State 0 (Bull)** | Low Vol, Slow Grind Up | **Short Put Spreads / Calendars** | Positive Delta, Short Vega (or neutral), Positive Theta |
| **State 1 (Chop)** | High Vol, Mean Reverting | **Iron Condors / Short Strangles** | Neutral Delta, Short Vega, Positive Theta |
| **State 2 (Crisis)** | Extreme Vol, Crash | **Long Puts / Long Volatility** | Negative Delta, Long Vega, Negative Theta |

**The Alpha:** By filtering trades through the HMM, the trader avoids the "strategy mismatch" error—such as selling Iron Condors (a low-vol strategy) during a regime transition to high volatility. The HMM provides a probabilistic "weather forecast" for the market, allowing the trader to dress the portfolio appropriately.20

## ---

**5\. Mathematical Pillar II: Kernel Regression for Trend Estimation**

While HMM handles the "state," Kernel Regression handles the "signal." Simons utilized kernel methods to smooth data in non-parametric ways, avoiding the lag and rigidity of simple moving averages. The **Nadaraya-Watson Estimator** is the primary tool here, creating a dynamic "envelope" around price that identifies statistical extremes.22

### **5.1 The Nadaraya-Watson Estimator**

Standard regression assumes a linear relationship ($y \= mx \+ b$). Kernel regression assumes no specific shape. It estimates the value of SPY at time $t$ by taking a weighted average of surrounding points, where the weights are determined by a kernel function (usually Gaussian).

$$\\hat{y}\_h(x) \= \\frac{\\sum\_{i=1}^{n} K\_h(x \- x\_i) y\_i}{\\sum\_{i=1}^{n} K\_h(x \- x\_i)}$$

* **Bandwidth ($h$):** This parameter controls the smoothness. A small bandwidth fits the noise (overfitting); a large bandwidth misses the turns (underfitting). The quantitative trader optimizes $h$ using cross-validation to maximize predictive power over a specific timeframe (e.g., 5 days).24

### **5.2 The Envelope Strategy: Mean Reversion Trading**

The Nadaraya-Watson estimator produces a smooth curve that tracks the center of gravity of price. By calculating the Mean Absolute Deviation (MAD) or Standard Deviation around this curve, we construct an **Envelope**.

* **The Statistical Edge:** Price action in SPY is mean-reverting on short timeframes. When price pushes 2 or 3 standard deviations away from the Kernel Estimator, it is statistically stretched. The probability of a "snap-back" to the kernel line increases significantly.  
* **Implementation:**  
  1. **Upper Band Breach:** Price $\> \\text{Kernel} \+ 3\\sigma$. Signal: **Overbought**.  
  2. **Lower Band Breach:** Price $\< \\text{Kernel} \- 3\\sigma$. Signal: **Oversold**.  
  3. **Execution:** Use short-duration options (0DTE to 3DTE) to fade the move.  
     * *Signal:* Sell Call Credit Spreads (Bearish) or Sell Put Credit Spreads (Bullish).  
     * *Rationale:* High-frequency mean reversion combined with rapid Theta decay in short-dated options creates a "double edge."

### **5.3 Error Correction and Lag Reduction**

Unlike an Exponential Moving Average (EMA), which relies only on past data, the Nadaraya-Watson estimator (in a repainting context) uses future data to smooth the past. For *trading* (where we don't have future data), we use the "Rational Quadratic Kernel" or similar variations that prioritize recent data while maintaining smoothness. This reduces the "lag" associated with traditional indicators, allowing the trader to enter reversals earlier, capturing a larger portion of the move.25

## ---

**6\. Strategy Architecture I: Volatility Dispersion Arbitrage**

Dispersion trading is perhaps the strategy most closely associated with the "black box" institutional edge. It exploits the mathematical relationship between an index (SPY) and its constituents (the 500 stocks or the 11 sectors). It is a bet on **correlation** rather than direction.27

### **6.1 The Mathematical Principle of Dispersion**

The variance of an index is defined as:

$$\\sigma^2\_{index} \= \\sum w\_i^2 \\sigma^2\_i \+ \\sum\_{i \\neq j} w\_i w\_j \\sigma\_i \\sigma\_j \\rho\_{ij}$$

Where:

* $w\_i$ is the weight of stock $i$.  
* $\\sigma\_i$ is the volatility of stock $i$.  
* $\\rho\_{ij}$ is the correlation between stock $i$ and stock $j$.

**Key Insight:** If correlation ($\\rho$) is low, the terms in the second summation cancel out (or are small), and the index volatility is low, even if individual stock volatilities ($\\sigma\_i$) are high.

* **The Trade:** Short Index Volatility (Sell SPY Options) vs. Long Component Volatility (Buy Options on XLK, XLE, XLF, etc.).  
* **The Setup:** This is a "Long Dispersion" trade. It profits when individual sectors move violently in opposite directions (e.g., Tech crashes, Energy rallies), causing the SPY to remain flat.

### **6.2 Retail Implementation: SPY vs. Sector Basket**

Executing this on 500 single stocks is transaction-cost prohibitive for retail. The efficient implementation uses the Sector ETFs (Select Sector SPDRs).

#### **6.2.1 Portfolio Construction**

1. **Short Leg:** Sell ATM Straddle on SPY. (Captures the "dampening" effect of the index).  
2. **Long Leg:** Buy ATM Straddles on the top weighted sectors (Technology-XLK, Financials-XLF, Healthcare-XLV).  
3. **Weighting (Beta-Adjusted):** You cannot just buy 1 contract of each. You must **Vega-weight** or **Delta-weight** the package to be neutral.  
   * Calculate the beta ($\\beta$) of each sector relative to SPY.  
   * Allocate capital such that the weighted vegas of the long legs equal the vega of the short SPY leg.

#### **6.2.2 The "Stock Picker's Market" Alpha**

This strategy thrives in environments where macroeconomic data is ambiguous (keeping the index range-bound) but sector-specific narratives are strong (driving rotation).

* *Simons Connection:* This strategy relies on identifying mispriced *implied correlation*. If index options are priced as if correlation is high (panic pricing), but the HMM predicts low correlation (rotation), the Dispersion trade offers a massive statistical edge. It extracts alpha from the *structure* of the market construction rather than price direction.29

## ---

**7\. Strategy Architecture II: Dynamic Gamma Scalping**

Simons’ Medallion Fund is famously "market neutral." They do not bet on the market going up or down; they bet on the relationships between assets. Gamma Scalping is the primary mechanism for monetizing volatility while remaining delta-neutral.7

### **7.1 The Mechanics of Gamma**

Gamma ($\\Gamma$) measures the rate of change of Delta ($\\Delta$) with respect to price.

* **Long Straddle:** Buying a Call and a Put.  
  * Initial Delta: $\\approx 0$.  
  * Gamma: Positive.  
  * Theta: Negative (You pay daily rent).  
* **The Scalp:** As SPY moves up, the Call delta increases (e.g., to \+0.20) and Put delta decreases (to \-0.30, net \+0.20). The position becomes Long Delta.  
  * *Adjustment:* **Sell** underlying shares (or sell SPY futures/synthetic short) to flatten the delta back to 0\.  
  * *Result:* You sold into strength.  
* As SPY moves down, the position becomes Short Delta.  
  * *Adjustment:* **Buy** underlying shares to flatten delta.  
  * *Result:* You bought into weakness.

### **7.2 The Profit Engine: Volatility \> Theta**

The profit from Gamma Scalping comes from the cumulative PnL of these "buy low, sell high" adjustments.

$$\\text{Profit} \= \\sum (\\text{Scalp PnL}) \- \\text{Total Theta Cost}$$

If the market is volatile enough, the scalps exceed the rent.

### **7.3 HMM Integration for Timing**

The fatal flaw of retail gamma scalping is "Theta Burn" during quiet markets. Institutional desks can weather this; retail cannot.

* **The Optimization:** Use the **HMM Regime Detector**.  
  * *Only* initiate the Long Straddle / Gamma Scalping engine when the HMM transitions to **Regime 1 (High Volatility)** or **Regime 2 (Crisis)**.  
  * When HMM detects **Regime 0 (Calm)**, close the strategy.  
* This "Regime-Gated" approach drastically improves the Sharpe Ratio of the strategy by avoiding the periods where the "cost of carry" (Theta) outweighs the "opportunity for scalp" (Gamma).20

## ---

**8\. Strategy Architecture III: Machine Learning for Volatility Prediction**

The pricing of options via Black-Scholes requires an input for volatility. The market provides **Implied Volatility (IV)**, which is essentially the market's consensus guess. RenTec’s edge often comes from having a *better guess*—a superior forecast of **Realized Volatility (RV)**.11

### **8.1 The Model: XGBoost / LSTM**

We can train a Machine Learning model (e.g., XGBoost) to predict the RV of SPY over the next 5 days.

* **Features:**  
  * Lagged RV (10-day, 20-day).  
  * GARCH(1,1) estimates.  
  * VIX, VIX9D, VVIX.  
  * Put/Call Ratios, Volume, Skew.  
* **Target:** The actual 5-day Realized Volatility of SPY.

### **8.2 The Arbitrage Logic**

Once the model is trained and validated (using Walk-Forward optimization to prevent lookahead bias), we compare the **Predicted RV** to the current **Implied Volatility** of ATM options.

* **Signal A (Short Vol):** Model predicts RV \= 12%. Market IV \= 18%.  
  * *Logic:* Options are overpriced. The market is pricing in fear that the model says is unjustified.  
  * *Trade:* **Iron Condors** or **Short Straddles**.  
* **Signal B (Long Vol):** Model predicts RV \= 25%. Market IV \= 15%.  
  * *Logic:* Options are cheap. A move is coming that the market hasn't priced in (e.g., an HMM regime shift).  
  * *Trade:* **Long Straddles** or **Backspreads**.

This methodology replaces "gut feel" about cheap/expensive options with a quantifiable, back-tested statistical probability.11

## ---

**9\. Risk Management: The Mathematics of Survival**

The most dangerous misconception about RenTec is that their high returns come from high risk. In reality, their risk management is draconian. They use leverage, but they apply it to strategies with mathematically bounded risk. For the SPY trader, two concepts are paramount: The Kelly Criterion and Volatility Targeting.

### **9.1 The Kelly Criterion: Optimal Position Sizing**

John Kelly, a Bell Labs colleague of Simons' associates, derived a formula for the optimal bet size to maximize the logarithm of wealth.

$$f^\* \= \\frac{p(b+1) \- 1}{b}$$

Where:

* $f^\*$ \= Fraction of capital to bet.  
* $p$ \= Probability of winning (from our HMM/ML backtests).  
* $b$ \= Odds received (Net Profit / Net Loss).

**The "Fractional Kelly" Adjustment:** Full Kelly betting is optimal mathematically but psychically impossible—it leads to massive drawdowns. Practitioners use **Half-Kelly** or **Quarter-Kelly**.

* *Application:* If our HMM Short Put strategy has a 65% win rate and 1:1 odds, Full Kelly is 30%. A Simons-style risk manager allocates \~7% (Quarter Kelly). This dramatically smooths the equity curve and virtually eliminates the risk of ruin (probability of hitting 0).35

### **9.2 Volatility Targeting**

Most traders keep position sizes static (e.g., "I always trade 5 contracts"). Quantitative trading demands **Volatility Targeting**.

* **Concept:** The portfolio should have a constant annualized volatility (e.g., 15%).  
* **Mechanism:** If the VIX doubles (market risk doubles), the position size must be cut in half to maintain the same portfolio risk contribution.  
* **Formula:** $\\text{Target Position} \= \\frac{\\text{Target Vol}}{\\text{Current Asset Vol}} \\times \\text{Capital}$.  
* This approach automatically forces the trader to "de-lever" in crises (preserving capital) and "lever up" in calm markets (maximizing efficiency). It counters the human tendency to panic-sell at the bottom and FOMO-buy at the top.38

## ---

**10\. Implementation Roadmap: Execution and Infrastructure**

The final hurdle is execution. A model is useless if slippage eats the alpha.

### **10.1 Execution Algorithms**

Institutions do not use "Market Orders." They use TWAP (Time-Weighted Average Price) or VWAP (Volume-Weighted Average Price) to minimize market impact.

* *Retail Adaptation:* When entering complex multi-leg positions (like Dispersion trades), use **Limit Orders** placed at the mid-price. Use "Leg-In" logic if liquidity is thin on specific strikes, but prioritize "Complex Order" tickets to ensure simultaneous fill and avoid "leg risk" (where one side fills and the market moves against the other).

### **10.2 The Python Stack**

To build this "Medallion-Lite" engine, the following open-source stack is recommended, mirroring the tools used in quantitative research:

* **Data Ingestion:** yfinance (price), ib\_insync (options chains/Interactive Brokers).  
* **Mathematical Modeling:** statsmodels (HMM), scikit-learn (Kernel Regression, Random Forest), hmmlearn.  
* **Backtesting:** Backtrader or VectorBT (crucial for validating the HMM logic on historical data).  
* **Risk Engine:** Custom Python script to calculate real-time Kelly fractions and Volatility Targets based on live portfolio NAV.

## ---

**11\. Conclusion**

The "Jim Simons Trading Strategy" is not a magic formula but a rigorous scientific process. It demands the abandonment of narrative, the embrace of probability, and the relentless application of statistical methods. By implementing **Hidden Markov Models** to identify market regimes, **Kernel Regression** to capitalize on mean reversion, and **Dispersion Arbitrage** to exploit correlation inefficiencies, the SPY options trader moves closer to the Renaissance ideal.

This architecture does not guarantee a 66% return—that requires the proprietary data and zero-cost leverage of Medallion. However, it does provide a robust, mathematically sound framework for extracting consistent alpha from the S\&P 500, transforming trading from a game of guessing to a discipline of statistical execution. The edge lies not in being right every time, but in being "100% right, 50.75% of the time," and letting the Law of Large Numbers do the rest.

## ---

**12\. Technical Appendices**

### **12.1 Table: Strategy vs. Regime Matrix**

| Regime (HMM State) | Volatility Characteristics | Signal Condition (ML) | Optimal Strategy Structure | Primary Greek Edge |
| :---- | :---- | :---- | :---- | :---- |
| **0: Bull / Calm** | Low RV, Low IV | Predicted RV \< Implied IV | **Calendar Spreads** / **Short Put Spread** | Theta, Delta |
| **1: Chop / Correction** | Med RV, Med IV | Predicted RV \< Implied IV | **Iron Condors** / **Short Strangles** | Vega (Short), Theta |
| **2: Crisis / Crash** | High RV, High IV | Predicted RV \> Implied IV | **Gamma Scalping** / **Long Straddle** | Gamma, Vega (Long) |
| **3: Dispersion** | Low Index Vol, High Stock Vol | Index IV \< Component IV | **Dispersion Arb** (Short SPY, Long XLK/XLE) | Correlation ($\\rho$) |

### **12.2 Mathematical Formulas**

Weighted Beta for Dispersion:

$$\\beta\_{portfolio} \= \\sum\_{i=1}^{n} w\_i \\beta\_i$$

To hedge the Short SPY Straddle ($S$), the notional value of the Sector Straddles ($L$) must satisfy:

$$\\text{Notional}\_L \= \\text{Notional}\_S \\times \\frac{1}{\\beta\_{sector}}$$  
Baum-Welch Update (Simplified):  
The re-estimation of the transition probability $a\_{ij}$ is:

$$\\bar{a}\_{ij} \= \\frac{\\sum\_{t=1}^{T-1} \\xi\_t(i,j)}{\\sum\_{t=1}^{T-1} \\gamma\_t(i)}$$

Where $\\xi$ is the probability of being in state $i$ at time $t$ and state $j$ at time $t+1$, and $\\gamma$ is the probability of being in state $i$ at time $t$.  
3

#### **Works cited**

1. Renaissance Technologies: The $100 Billion Built on Statistical Arbitrage \- Navnoor Bawa, accessed January 4, 2026, [https://navnoorbawa.substack.com/p/renaissance-technologies-the-100](https://navnoorbawa.substack.com/p/renaissance-technologies-the-100)  
2. How Jim Simons' Trading Strategies Achieved 66% Annual Returns (Medallion Fund Algorithm) \- QuantifiedStrategies.com, accessed January 4, 2026, [https://www.quantifiedstrategies.com/jim-simons/](https://www.quantifiedstrategies.com/jim-simons/)  
3. Jim Simons Trading Strategy – Renaissance Technologies \- QuantVPS, accessed January 4, 2026, [https://www.quantvps.com/blog/jim-simons-trading-strategy](https://www.quantvps.com/blog/jim-simons-trading-strategy)  
4. Jim Simons: The "Quant King" Behind Renaissance Technologies \- Investopedia, accessed January 4, 2026, [https://www.investopedia.com/articles/investing/030516/jim-simons-success-story-net-worth-education-top-quotes.asp](https://www.investopedia.com/articles/investing/030516/jim-simons-success-story-net-worth-education-top-quotes.asp)  
5. jim simons trading strategy: systematic approach that made $100+ billion | stay sharp blog, accessed January 4, 2026, [https://www.edgeful.com/blog/posts/jim-simons-trading-strategy-systematic-approach](https://www.edgeful.com/blog/posts/jim-simons-trading-strategy-systematic-approach)  
6. Uncovering the Mathematics behind the World's most Profitable Hedge Fund, accessed January 4, 2026, [https://acontinuallearner.medium.com/uncovering-the-mathematics-behind-the-worlds-most-profitable-hedge-fund-79770d772997](https://acontinuallearner.medium.com/uncovering-the-mathematics-behind-the-worlds-most-profitable-hedge-fund-79770d772997)  
7. Simons' Strategies: Renaissance Trading Unpacked \- LuxAlgo, accessed January 4, 2026, [https://www.luxalgo.com/blog/simons-strategies-renaissance-trading-unpacked/](https://www.luxalgo.com/blog/simons-strategies-renaissance-trading-unpacked/)  
8. Jim Simons' Options Strategy: A Hidden Advantage Retail Traders Miss \- YouTube, accessed January 4, 2026, [https://www.youtube.com/watch?v=VbOmv8QB2fE](https://www.youtube.com/watch?v=VbOmv8QB2fE)  
9. Strategy of Renaissance Technologies Medallion fund: Holy Grail or next Madoff?, accessed January 4, 2026, [https://quant.stackexchange.com/questions/998/strategy-of-renaissance-technologies-medallion-fund-holy-grail-or-next-madoff](https://quant.stackexchange.com/questions/998/strategy-of-renaissance-technologies-medallion-fund-holy-grail-or-next-madoff)  
10. The Power of Quants: How Simons Built a Team of Non-Finance Geniuses \- QuantifiedStrategies.com, accessed January 4, 2026, [https://www.quantifiedstrategies.com/the-power-of-quants-how-simons-built-a-team-of-non-finance-geniuses/](https://www.quantifiedstrategies.com/the-power-of-quants-how-simons-built-a-team-of-non-finance-geniuses/)  
11. USING MACHINE LEARNING TO PREDICT REALIZED VARIANCE \- NYU Tandon School of Engineering, accessed January 4, 2026, [https://engineering.nyu.edu/sites/default/files/2020-05/P0639\_ZZ-JOI\_0.pdf](https://engineering.nyu.edu/sites/default/files/2020-05/P0639_ZZ-JOI_0.pdf)  
12. Using Machine Learning Methods to Predict Implied Volatility Surfaces for SPX Options, accessed January 4, 2026, [https://dataspace-staging.princeton.edu/handle/88435/dsp01hm50tv48n](https://dataspace-staging.princeton.edu/handle/88435/dsp01hm50tv48n)  
13. SPY liquidity: Flexibility to navigate any market \- State Street Global Advisors, accessed January 4, 2026, [https://www.ssga.com/us/en/institutional/insights/spy-liquidity-flexibility-to-navigate-any-market](https://www.ssga.com/us/en/institutional/insights/spy-liquidity-flexibility-to-navigate-any-market)  
14. Renaissance Technologies Medallion Fund: An Exception to the Indexing Rule, accessed January 4, 2026, [https://pwlcapital.com/renaissance-technologies-medallion-fund-an-exception-to-the-indexing-rule/](https://pwlcapital.com/renaissance-technologies-medallion-fund-an-exception-to-the-indexing-rule/)  
15. Market Regime Detection Using Hidden Markov Models \- QuestDB, accessed January 4, 2026, [https://questdb.com/glossary/market-regime-detection-using-hidden-markov-models/](https://questdb.com/glossary/market-regime-detection-using-hidden-markov-models/)  
16. A forest of opinions: A multi-model ensemble-HMM voting framework for market regime shift detection and trading \- AIMS Press, accessed January 4, 2026, [https://www.aimspress.com/article/id/69045d2fba35de34708adb5d](https://www.aimspress.com/article/id/69045d2fba35de34708adb5d)  
17. Market Regime using Hidden Markov Model \- QuantInsti Blog, accessed January 4, 2026, [https://blog.quantinsti.com/regime-adaptive-trading-python/](https://blog.quantinsti.com/regime-adaptive-trading-python/)  
18. The Application of Baum-Welch Algorithm in Multistep Attack \- PMC \- NIH, accessed January 4, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC4058473/](https://pmc.ncbi.nlm.nih.gov/articles/PMC4058473/)  
19. Baum–Welch algorithm \- Wikipedia, accessed January 4, 2026, [https://en.wikipedia.org/wiki/Baum%E2%80%93Welch\_algorithm](https://en.wikipedia.org/wiki/Baum%E2%80%93Welch_algorithm)  
20. Intraday Application of Hidden Markov Models \- QuantConnect.com, accessed January 4, 2026, [https://www.quantconnect.com/research/17900/intraday-application-of-hidden-markov-models/](https://www.quantconnect.com/research/17900/intraday-application-of-hidden-markov-models/)  
21. Market Regime Detection using Hidden Markov Models in QSTrader | QuantStart, accessed January 4, 2026, [https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/)  
22. Notes on The Man Who Solved The Market (Jim Simons) \- Some Ben?, accessed January 4, 2026, [https://blog.someben.com/2019/11/notes-on-man-who-solved-the-market-jim-simons/](https://blog.someben.com/2019/11/notes-on-man-who-solved-the-market-jim-simons/)  
23. Multivariate and Online Prediction of Closing Price Using Kernel Adaptive Filtering \- PMC, accessed January 4, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC8709756/](https://pmc.ncbi.nlm.nih.gov/articles/PMC8709756/)  
24. A Multivariate Kernel Approach to Forecasting the Variance Covariance of Stock Market Returns \- MDPI, accessed January 4, 2026, [https://www.mdpi.com/2225-1146/6/1/7](https://www.mdpi.com/2225-1146/6/1/7)  
25. Nadaraya Watson Envelope Trading Strategy | Complete Beginner's Guide \- TradeSearcher, accessed January 4, 2026, [https://tradesearcher.ai/blog/nadaraya-watson-envelope-trading-strategy-guide](https://tradesearcher.ai/blog/nadaraya-watson-envelope-trading-strategy-guide)  
26. Trend Following Strategy Based on Nadaraya-Watson Regression and ATR Channel | by FMZQuant | Medium, accessed January 4, 2026, [https://medium.com/@FMZQuant/trend-following-strategy-based-on-nadaraya-watson-regression-and-atr-channel-787192031432](https://medium.com/@FMZQuant/trend-following-strategy-based-on-nadaraya-watson-regression-and-atr-channel-787192031432)  
27. Options Talk \- Episode 24 \- the dispersion trade and how to handle it \- Saxo Bank, accessed January 4, 2026, [https://www.home.saxo/content/articles/options/options-talk---episode-24---the-dispersion-trade-and-how-to-handle-it-31072024](https://www.home.saxo/content/articles/options/options-talk---episode-24---the-dispersion-trade-and-how-to-handle-it-31072024)  
28. Dispersion Trading \- Quantpedia, accessed January 4, 2026, [https://quantpedia.com/strategies/dispersion-trading](https://quantpedia.com/strategies/dispersion-trading)  
29. Almost Everything You Wanted to Know About Dispersion Trading (But Were Afraid to Ask) : r/quant \- Reddit, accessed January 4, 2026, [https://www.reddit.com/r/quant/comments/1nmxdef/almost\_everything\_you\_wanted\_to\_know\_about/](https://www.reddit.com/r/quant/comments/1nmxdef/almost_everything_you_wanted_to_know_about/)  
30. ETF Trading Guide: How Sector Funds Beat SPY for Options Income | tastylive, accessed January 4, 2026, [https://www.tastylive.com/news-insights/etf-trading-guide-how-sector-funds-beat-spy-options-income](https://www.tastylive.com/news-insights/etf-trading-guide-how-sector-funds-beat-spy-options-income)  
31. Gamma Scalping: Building an Options Strategy with Python and Alpaca's Trading API, accessed January 4, 2026, [https://alpaca.markets/learn/gamma-scalping](https://alpaca.markets/learn/gamma-scalping)  
32. Regime-Aware Short-Term Trading Strategy Using Hidden Markov Models and Monte Carlo Simulation \- Communications on Applied Nonlinear Analysis (ISSN: 1074-133X), accessed January 4, 2026, [https://internationalpubls.com/index.php/cana/article/view/6029](https://internationalpubls.com/index.php/cana/article/view/6029)  
33. Predicting implied volatility using deep learning for option pricing | Sciety, accessed January 4, 2026, [https://sciety.org/articles/activity/10.21203/rs.3.rs-6620528/v1](https://sciety.org/articles/activity/10.21203/rs.3.rs-6620528/v1)  
34. Predicting Volatility: GARCH vs XGBoost \- Kaggle, accessed January 4, 2026, [https://www.kaggle.com/code/lucastrenzado/predicting-volatility-garch-vs-xgboost](https://www.kaggle.com/code/lucastrenzado/predicting-volatility-garch-vs-xgboost)  
35. Kelly's Criterion – \- Zerodha, accessed January 4, 2026, [https://zerodha.com/varsity/chapter/kellys-criterion/](https://zerodha.com/varsity/chapter/kellys-criterion/)  
36. Kelly's Criterion \- The Growth Formula \- Market Measures \- tastylive, accessed January 4, 2026, [https://www.tastylive.com/shows/market-measures/episodes/kellys-criterion-the-growth-formula-04-25-2025](https://www.tastylive.com/shows/market-measures/episodes/kellys-criterion-the-growth-formula-04-25-2025)  
37. Beware of Excessive Leverage – Introduction to Kelly and Optimal F \- QuantPedia, accessed January 4, 2026, [https://quantpedia.com/beware-of-excessive-leverage-introduction-to-kelly-and-optimal-f/](https://quantpedia.com/beware-of-excessive-leverage-introduction-to-kelly-and-optimal-f/)  
38. Volatility-Based Position Sizing with Python: How to Adjust Your Trades | by SR | Medium, accessed January 4, 2026, [https://medium.com/@deepml1818/volatility-based-position-sizing-with-python-how-to-adjust-your-trades-1f88efc8b228](https://medium.com/@deepml1818/volatility-based-position-sizing-with-python-how-to-adjust-your-trades-1f88efc8b228)  
39. Volatility Targeting vs Buy & Hold: Python Backtest Reveals the Truth \- YouTube, accessed January 4, 2026, [https://www.youtube.com/watch?v=BwvE3TzwzXs](https://www.youtube.com/watch?v=BwvE3TzwzXs)  
40. Beta Weighting a Portfolio | Formula & How It Works | Britannica Money, accessed January 4, 2026, [https://www.britannica.com/money/portfolio-beta-weighting](https://www.britannica.com/money/portfolio-beta-weighting)