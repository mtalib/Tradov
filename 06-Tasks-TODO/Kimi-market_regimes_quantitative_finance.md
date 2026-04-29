# Market Regimes in Quantitative Finance

## Overview

In trading and quantitative finance, **"macro regime" and "micro regime" are not official, standardized terms** in the academic or practitioner literature. The field instead uses a well-defined taxonomy based on **what is switching** (the dimension of the regime) and **how the switching is modeled**. However, the concepts you are asking about do map onto real distinctions—just under different names.

---

## 1. The Core Distinction: What Is Switching?

Regimes are defined by persistent states in which the **statistical properties** of market data change. According to Hamilton's foundational work and the broader literature, the key dimensions are:

| Dimension | What Switches | Official Terminology |
|-----------|-------------|---------------------|
| **Trend / Mean** | Expected returns, drift | Mean-switching regime |
| **Volatility** | Variance, standard deviation | Volatility regime (heteroscedastic) |
| **Correlation** | Cross-asset relationships | Correlation regime |
| **Economic State** | GDP growth, business cycle | Macroeconomic regime |
| **Policy** | Interest rates, monetary/fiscal stance | Policy regime |

A regime is therefore **not a single label** like "bull market"—it is a **multivariate state** where several of the above properties shift simultaneously and persist for a period of time.

---

## 2. The "Macro" vs. "Micro" Mapping

While not official terms, your intuition about scale maps onto the literature as follows:

### Macro-Level Regimes (Economy-Wide, Persistent)

These are the regimes most commonly studied in academic macroeconomics and asset allocation. They are driven by structural economic forces and typically last months to years.

**Official names and types:**
- **Expansion / Contraction** (Hamilton's original 2-state business cycle model)
- **Bull Market / Bear Market** (trend regimes in equity markets)
- **High-Volatility / Low-Volatility** (volatility clustering regimes)
- **Risk-On / Risk-Off** (cross-asset sentiment regimes)
- **Easing / Tightening** (monetary policy regimes)

Two Sigma's quantitative research, using Gaussian Mixture Models on factor data, identified four macro-level regimes with these labels:
1. **Crisis** — extreme drawdowns, flight to quality (bonds rally)
2. **Steady State** — normal, healthy markets; most factors perform well
3. **Inflation** — inflation factors dominate; equities and bonds underperform
4. **Walking on Ice** — risk-on bubble-like conditions; equities rally with elevated volatility

### Micro-Level Regimes (Market Structure, Short-Term)

These are not typically called "micro-regimes" in papers, but they describe short-term, structural states of market functioning. They are relevant to execution, high-frequency trading, and market making.

**Official names and types:**
- **Liquidity regimes** — deep vs. thin order books
- **Adverse selection regimes** — informed vs. uninformed order flow dominance
- **Fragmentation regimes** — concentrated vs. dispersed trading across venues
- **Auction vs. Continuous trading regimes** (market mechanism regimes)

These are studied under **market microstructure** theory, not regime-switching models. The statistical tools here are different—often involving point processes, queueing models, and order-book dynamics rather than Hamilton-style Markov switching.

---

## 3. Official Regime-Switching Model Taxonomy

The econometrics literature has precise names for how regimes are modeled:

| Model Type | How Regimes Switch | Key Feature |
|------------|-------------------|-------------|
| **Markov-Switching (MS)** | Unobserved latent state following a Markov chain | Gold standard; used by Hamilton (1989) |
| **Threshold Autoregressive (TAR/SETAR)** | Observed variable crosses a threshold | Deterministic switching |
| **Smooth Transition (STAR)** | Gradual, continuous transition between regimes | Avoids abrupt jumps |
| **Structural Break** | One-time, permanent regime change | Not recurrent |
| **Hidden Markov Model (HMM)** | Same as MS, often used in ML contexts | Emphasis on inference of hidden states |

Within Markov-switching models, there are further official sub-types based on what parameters switch:
- **MSM-VAR**: Mean switches
- **MSI-VAR**: Intercept switches
- **MSH-VAR**: Variance (heteroscedasticity) switches
- **MSA-VAR**: Autoregressive coefficients switch
- **Combinations**: MSMH, MSIA, etc.

---

## 4. Timeframe as a Regime Dimension

The closest the literature comes to your macro/micro distinction is the recognition that **regimes are relative to the observation frequency**:

- A **swing trader** on daily charts sees a 3-month bull trend as a single macro regime.
- An **intraday scalper** on 1-minute charts sees that same period as a sequence of micro-choppy, micro-trending, and micro-volatile sub-regimes.

This is not formalized as "macro regime" vs. "micro regime" in papers. Instead, practitioners speak of:
- **Regime persistence** — how long a state lasts (a property, not a type)
- **Multi-scale regime analysis** — applying regime detection at different time aggregations

---

## Summary

| Your Term | Official Equivalent | Scale | Typical Duration |
|-----------|---------------------|-------|-----------------|
| **Macro Regime** | Macroeconomic / business cycle regime; Trend-volatility regime | Economy-wide, multi-asset | Months to years |
| **Micro Regime** | Market microstructure state; Short-term volatility/liquidity condition | Single asset, intraday | Seconds to days |

**There is no official "micro-regime" classification** in the quantitative finance literature. If you encounter this term, it is likely either:
1. A practitioner's informal label for short-term market states, or
2. A confusion with **market microstructure** analysis.

For systematic trading, the robust framework is to define regimes by **trend direction × volatility × correlation**, detect them using Markov-switching or clustering models, and match your strategy to the detected state.

---

## References

- Hamilton, J.D. (1989). A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle. *Econometrica*.
- Hamilton, J.D. (2005). What's Real About the Business Cycle? *Federal Reserve Bank of St. Louis Review*.
- Two Sigma. (2021). Understanding Regime Shifts in Factor Investing.
- State Street. Quantitative Research on Market Regimes.
- Ang, A. & Timmermann, A. (2012). Regime Changes and Financial Markets. *Annual Review of Financial Economics*.
- Market Microstructure literature (O'Hara, 1995; Hasbrouck, 2007).
