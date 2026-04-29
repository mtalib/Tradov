# Best Practices Report: Building an Autonomous SPY Options Trading System on Ubuntu, Wayland, PySide6, and Python

**Author:** Manus AI  
**Date:** April 29, 2026  
**Scope:** Autonomous decision-support and trade-execution architecture for SPY options, with emphasis on minimum market inputs, indicators, signal design, regime classification, risk controls, and desktop engineering practices.  

> **Important notice:** This report is for engineering, quantitative-research, and risk-management design purposes only. It is not investment advice, a recommendation to buy or sell securities or options, or a substitute for professional legal, tax, compliance, or financial advice. Options involve significant risk; OCC states that investors should read the **Characteristics and Risks of Standardized Options** before buying or selling options.[^1]

## Executive Summary

An autonomous SPY options trading system should not begin with a large library of indicators. It should begin with a **small, auditable, regime-aware signal stack** that measures four things reliably: the direction of SPY, the volatility state of the market, the liquidity and microstructure state of the selected option contracts, and the portfolio’s Greek exposure. SPY is a liquid ETF designed to track the S&P 500 Index before expenses, and State Street notes that SPY options are available.[^2] Because options embed nonlinear exposure, the minimum viable system must monitor both the underlying ETF and the option chain, including implied volatility, Greeks, spreads, volume, open interest, expiration, and strike selection.

The minimum practical symbol universe is **SPY**, **SPY option chain**, **SPX or ES futures as optional cross-checks**, **VIX**, **VIX term structure**, **risk-free rate proxy**, and an **economic/event calendar**. The minimum indicator set should cover **trend**, **range**, **realized volatility**, **implied volatility**, **volatility risk premium**, **liquidity**, **skew**, **term structure**, and **portfolio Greeks**. The minimum signal set should include a **trade-entry signal**, **position-selection signal**, **risk-sizing signal**, **exit signal**, **kill-switch signal**, and **regime-gating signal**.

In quantitative finance, there is **no single canonical number of regimes**. The most useful answer for SPY options is that regimes can be represented at several levels of granularity. A two-regime model distinguishes **risk-on versus risk-off**. A four-regime model distinguishes **bull, bear, sideways/calm, and crisis/turbulent**. A six-regime model adds **reversal/transition** and **event-driven/illiquidity** states. For an autonomous SPY options system, the **six-regime taxonomy** is the most practical minimum because options strategies depend not only on direction but also on volatility, skew, liquidity, and time decay.

### Competitive Advantage Summary

A well-built autonomous SPY options platform earns its advantage from **discipline, observability, latency-aware execution, regime-aware strategy gating, and hard risk controls**, not from adding more indicators. On a 10-point engineering maturity scale, a production-quality design target is **8/10 or higher** before live trading: data integrity, simulation fidelity, automated tests, observability, fail-safe order handling, and post-trade analytics must all be present. **This detailed report will show how the scores were determined** by mapping symbols, indicators, signals, regimes, architecture, and controls into a practical implementation blueprint.

## 1. Minimum Symbols and Data Inputs

The minimum symbol list should be intentionally small. SPY options already express exposure to U.S. large-cap equity direction, implied volatility, skew, gamma, liquidity, and event risk. Adding too many symbols can create false precision unless each input has a defined purpose in the decision process.

| Capability / Input | Minimum Symbol or Feed | Why It Is Needed | Typical Frequency | Required for Live Trading |
|---|---|---|---|---|
| Underlying price state | **SPY** OHLCV, bid/ask, last, NBBO | Defines direction, realized volatility, support/resistance, and option moneyness. | Tick to 1-minute | Yes |
| Tradable contracts | **SPY option chain** | Provides strike, expiry, bid/ask, volume, open interest, implied volatility, and Greeks. | Tick to 1-minute | Yes |
| Broad index confirmation | **SPX** or **ES futures** | Confirms whether SPY movement reflects broad index movement or ETF-specific noise. | 1-minute | Recommended |
| Volatility regime | **VIX** | Cboe describes VIX as a leading measure of near-term volatility expectations from S&P 500 option prices.[^3] | 1-minute to 5-minute | Yes |
| Volatility term structure | VIX futures or VIX9D/VIX/VIX3M/VIX6M | Distinguishes calm contango from stress backwardation and supports volatility-risk-premium signals. | 5-minute to daily | Strongly recommended |
| Risk-free rate | SOFR, Treasury bill yield, or broker-provided rate | Required for theoretical option valuation and rho-sensitive models. | Daily | Yes |
| Dividends and distributions | SPY dividend calendar | Needed for pricing, early-exercise risk, and expiry behavior. | Daily/event | Yes |
| Market hours and events | Exchange calendar, FOMC, CPI, payrolls, earnings-heavy days | Event days can change volatility, spreads, and gamma behavior. | Daily/event | Yes |
| Account state | Cash, buying power, margin, current positions, realized/unrealized P&L | Required for position sizing, loss limits, and kill switches. | Tick to 1-minute | Yes |
| Broker/order state | Orders, fills, rejects, cancels, partial fills | Required for reconciliation and autonomous safety. | Real time | Yes |

A minimum viable system should refuse to trade if any required data source is missing, stale, internally inconsistent, or delayed beyond a preconfigured threshold. For example, if the option chain is fresh but the underlying quote is stale, the system should not select contracts because delta and moneyness may be wrong.

## 2. Minimum Indicators

Indicators should be selected by **decision role**, not by popularity. An autonomous system needs indicators that answer a specific question: whether to trade, what strategy type to use, which contract to choose, how much risk to allocate, when to exit, and when to halt.

| Capability / Indicator Group | Minimum Indicators | Practical Interpretation | Used By |
|---|---|---|---|
| Trend and market direction | EMA 20/50, session VWAP, higher-timeframe slope, SPY return over 1/5/20 bars | Determines directional bias and whether long calls, long puts, spreads, or no trade are eligible. | Entry, regime, sizing |
| Market structure | Dynamic pivot points, prior day high/low, opening range, support/resistance, gap status | Determines whether SPY is trending, mean-reverting, or breaking structure. | Entry and exits |
| Realized volatility | Rolling standard deviation, ATR, Parkinson/Garman-Klass estimator where available | Measures actual movement and helps compare realized volatility to implied volatility. | Regime and sizing |
| Implied volatility | ATM IV, IV rank/percentile, option-chain IV surface | Measures option market expectation of movement. OIC defines implied volatility as the volatility implied by option prices.[^4] | Contract selection |
| Volatility risk premium | IV minus realized volatility, VIX versus realized SPY volatility | Helps decide whether long-volatility or short-volatility structures are favored. | Strategy gating |
| Skew and smile | Put/call IV skew, 25-delta risk reversal, vertical skew | Measures downside demand and tail-risk pricing. | Strategy selection |
| Term structure | VIX9D/VIX/VIX3M slope or VIX futures front-month slope | Identifies calm, stress, and event-volatility states. Cboe notes that volatility is mean-reverting and this helps shape the VIX futures term structure.[^3] | Regime gating |
| Liquidity | Bid/ask spread, spread as percentage of mid, volume, open interest, quote age, crossed/locked quote checks | Prevents trading poor contracts and controls slippage. | Contract filter |
| Greeks | Delta, gamma, theta, vega, rho, portfolio net Greeks | OIC describes Greeks as sensitivity measures for option values.[^4] | Sizing and risk |
| Time-to-expiry | DTE, session time remaining, theta acceleration zone | Prevents unintended 0DTE or near-expiry gamma risk. | Strategy filter |
| Execution quality | Fill slippage, cancel/reject rate, queue time, order-to-fill ratio | Detects broker/API/exchange degradation. | Execution control |

For the PySide6 dashboard, the chart should focus on indicators that are both useful to a human operator and directly consumed by the autonomous logic. The recommended visible dashboard set is **VWAP with deviation bands**, **multi-timeframe dynamic pivots**, **Bollinger Bands with squeeze detection**, **enhanced multi-timeframe RSI**, **MACD with volume confirmation**, and a **VIX term-structure panel**. The panel does not need to sit on the price chart; it only needs to make the volatility regime obvious to the operator and machine-readable for the strategy engine.

## 3. Minimum Signals

A signal is not the same as an indicator. An indicator measures a state; a signal produces an action or constraint. For autonomous trading, every signal should have an owner, a time horizon, a confidence score, and a failure behavior.

| Signal Type | Minimum Definition | Example Decision | Required Safeguard |
|---|---|---|---|
| Regime-gating signal | Classifies the current market into a finite regime set. | Allows only long-gamma trades in crisis or event states. | If uncertain, downgrade to no-trade. |
| Directional entry signal | Combines trend, structure, and confirmation. | Buy call spread only if SPY breaks opening range above VWAP with trend confirmation. | Require minimum liquidity and max spread. |
| Volatility-entry signal | Compares IV, realized volatility, VIX, and term structure. | Prefer long volatility when realized volatility is rising and term structure is stressed. | Avoid short volatility during stress. |
| Contract-selection signal | Selects expiry, strike, delta, and structure. | Choose 20–45 DTE 0.35–0.55 delta options for directional trades, or defined-risk spreads. | Exclude stale quotes and wide spreads. |
| Sizing signal | Converts confidence and risk budget into contracts. | Allocate smaller size in high VIX/high gamma regimes. | Enforce max loss, max contracts, and buying-power checks. |
| Exit signal | Defines profit-taking, stop-loss, time stop, regime exit, and Greek exit. | Exit if delta thesis fails, IV collapses, spread widens, or time stop triggers. | Exits must not depend on one indicator only. |
| Execution signal | Determines order type and price improvement rules. | Start at mid, work toward limit, cancel if quote deteriorates. | Never send naked market orders by default. |
| Kill-switch signal | Halts strategy and optionally cancels open orders. | Halt on stale data, broker disconnect, excessive slippage, daily loss limit, or volatility shock. | Must be independent of strategy logic. |
| Reconciliation signal | Compares expected positions with broker positions. | Stop trading if local book and broker book differ. | Manual review before resuming. |

The minimum autonomous rule is: **the system must be more eager to stop trading than to trade**. Every trade should pass through four gates: **data gate**, **regime gate**, **risk gate**, and **execution gate**. A trade that fails any one gate should not be submitted.

## 4. How Many Regimes Exist in Quantitative Finance?

There is no universal number of market regimes in quantitative finance. Macrosynergy defines market regimes as **clusters of persistent market conditions** that affect factor relevance and strategy success.[^5] The number of regimes depends on the model, asset class, time horizon, and trading objective. A hidden Markov model, Gaussian mixture model, clustering approach, or supervised classifier may identify different numbers of states from the same data because each method optimizes a different statistical objective.[^5]

> “Market regimes are clusters of persistent market conditions. They affect the relevance of investment factors and the success of trading strategies.” — Macrosynergy[^5]

For an SPY options system, the best practical answer is to define regimes at three levels.

| Regime Granularity | Number of Regimes | Names | Use Case |
|---|---:|---|---|
| Minimal | 2 | Risk-on, risk-off | Coarse portfolio exposure and kill-switch logic. |
| Standard | 4 | Bull trend, bear trend, sideways/calm, crisis/turbulent | Basic strategy gating for directional versus volatility trades. |
| Recommended for SPY options | 6 | Bull trend, bear trend, range/calm, high-volatility mean reversion, crisis/turbulent, event/transition | Minimum practical taxonomy for options because direction, volatility, skew, liquidity, and time decay matter simultaneously. |
| Advanced | 8–12+ | Adds liquidity, macro, dispersion, dealer-gamma, and intraday microstructure states | Useful only after enough live and historical data support stable classification. |

The six-regime taxonomy is recommended because options are sensitive to **directional exposure, convexity, implied volatility, realized volatility, skew, liquidity, and time-to-expiry**. A two-regime model can be acceptable for high-level exposure control, but it is too blunt for contract selection. A 10-regime model can be useful in research but may overfit if the system does not have enough observations per regime.

## 5. Recommended Six-Regime Taxonomy for SPY Options

The following taxonomy is intentionally practical. It can be implemented with simple thresholds first and replaced later by a probabilistic classifier.

| Regime | Market Description | Typical Indicator Pattern | Suitable Strategy Bias | Avoid |
|---|---|---|---|---|
| **1. Bull trend / low-to-moderate volatility** | SPY trends upward with contained volatility and healthy liquidity. | SPY above VWAP and rising moving averages; VIX stable or falling; positive breadth; normal spreads. | Defined-risk bullish call spreads, long calls on breakouts, put-credit spreads only if risk controls are mature. | Aggressive long volatility without event catalyst. |
| **2. Bear trend / rising volatility** | SPY trends downward while implied volatility rises. | SPY below VWAP and falling averages; VIX rising; put skew increasing; wider spreads. | Put spreads, collars, limited-risk bearish structures, smaller position sizes. | Short naked puts, large short-vega exposure. |
| **3. Range / calm / mean-reverting** | Price oscillates around VWAP with low realized volatility. | Low ATR; flat moving averages; Bollinger squeeze; VIX low/stable; tight spreads. | Mean-reversion scalps, iron condors only with defined risk, small theta trades. | Paying high premiums for direction without breakout confirmation. |
| **4. High-volatility mean reversion** | Volatility is elevated but price swings are two-sided rather than directional. | High ATR; VIX elevated but not accelerating; failed breakouts; wide intraday ranges. | Gamma-aware defined-risk spreads, volatility-scaled directional trades, shorter holding periods. | Static stops too close to noise; oversized positions. |
| **5. Crisis / turbulent / gap-risk** | Market sells off or gaps with unstable quotes and correlation spikes. | VIX spike or backwardation; large gaps; spreads widen; liquidity deteriorates; SPY moves quickly through pivots. | No-trade, hedging, very small long-gamma exposure if execution quality is reliable. | Short volatility, market orders, averaging down. |
| **6. Event / transition / model-uncertain** | Scheduled or unscheduled event changes the distribution. | CPI/FOMC/payrolls; sudden term-structure shift; classifier confidence low; quote instability. | Predefined event playbooks, reduced size, post-event reclassification. | Letting stale pre-event signals remain active. |

## 6. How Symbols, Indicators, and Signals Fit Into Regimes

The system should treat regimes as a **routing layer**. The regime classifier does not necessarily trade by itself. Instead, it decides which strategies, indicators, risk budgets, expirations, and execution rules are allowed.

| Regime | Symbols Emphasized | Indicators Emphasized | Signals Activated | Risk Posture |
|---|---|---|---|---|
| Bull trend | SPY, SPX/ES, option chain, VIX | VWAP, EMA slope, call-side liquidity, IV rank, delta | Directional bullish entry, call-spread selection, trend exit | Normal size if spreads are tight; avoid excessive theta. |
| Bear trend | SPY, VIX, put skew, option chain | VWAP, downside pivots, VIX slope, put/call IV skew, gamma | Bearish entry, put-spread selection, volatility-aware sizing | Reduced size; strict max loss; avoid short-vega. |
| Range/calm | SPY, option chain, VIX term structure | Bollinger squeeze, ATR, VWAP deviations, realized/IV spread | Mean-reversion entry, theta/defined-risk selection, tight time stop | Small size; avoid trades near breakout triggers. |
| High-vol mean reversion | SPY, VIX, VIX term structure, option chain | ATR, realized volatility, IV rank, skew, quote spread | Volatility-scaled entry, gamma-aware exits, slippage guard | Smaller size; wider stops; shorter holding period. |
| Crisis/turbulent | SPY, VIX, VIX futures, broker/account state | VIX spike, backwardation, bid/ask widening, stale quote detection | Kill switch, hedge-only mode, cancel open orders | No new discretionary trades unless explicitly whitelisted. |
| Event/transition | Calendar, SPY, VIX9D/VIX, option chain | Event proximity, term-structure kink, IV crush risk, classifier uncertainty | Event gate, pre-event halt, post-event reclassification | Reduced size or no-trade until regime confidence recovers. |

This mapping is the core of the autonomous design. A bullish signal in a crisis regime should not behave the same way as a bullish signal in a calm bull trend. In calm regimes, a breakout may justify a directional spread. In crisis regimes, the same breakout may be a false bounce in unstable liquidity.

## 7. Strategy Architecture: From Data to Orders

The architecture should be modular and deterministic at every boundary. The GUI should never be the strategy engine. PySide6 should observe, visualize, and allow controlled operator intervention, while the strategy engine, risk engine, and execution engine run as separable services or modules.

| Layer | Responsibility | Best Practice |
|---|---|---|
| Data ingestion | Pull market data, option chains, broker state, calendar, account data. | Normalize timestamps, reject stale data, store raw and normalized data. |
| Feature engine | Compute indicators, Greeks, spreads, volatility metrics, and regime features. | Use reproducible feature definitions and version them. |
| Regime engine | Classify market state and confidence. | Start with transparent rules; later compare HMM, GMM, random forest, or gradient models. |
| Strategy engine | Generate candidate trades. | Strategy must output intent, not directly submit orders. |
| Risk engine | Approve, resize, reject, or halt trades. | Enforce risk independent of strategy. |
| Execution engine | Convert approved intent into broker orders. | Use limit orders, price collars, retry budgets, cancel rules, and reconciliation. |
| Persistence layer | Store quotes, features, decisions, orders, fills, logs. | Use append-only event logs for auditability. |
| PySide6 dashboard | Display state and receive operator commands. | Dashboard should not be a single point of failure. |

A good pattern is an **event-sourced architecture**. Every market snapshot, feature computation, regime classification, trade proposal, risk decision, order submission, fill, cancel, and error is written as an immutable event. This makes debugging and post-trade analysis possible.

## 8. Risk Management and Autonomous Safety Controls

Automated options systems fail most often from stale data, incorrect position state, bad assumptions about liquidity, excessive leverage, broken broker connections, or uncontrolled feedback loops. Regulatory and industry discussions of automated trading controls emphasize order throttles, execution throttles, volatility alerts, price collars, maximum order size limits, trading pauses, and credit-risk controls.[^6]

| Control | Minimum Implementation | Why It Matters |
|---|---|---|
| Data freshness halt | Stop trading if underlying, option chain, or broker state exceeds max age. | Prevents trading on stale quotes. |
| Price collar | Reject orders too far from mid, NBBO, theoretical value, or recent fills. | Prevents accidental extreme fills. |
| Max order size | Hard cap by contracts, premium, max loss, and portfolio exposure. | Limits catastrophic order errors. |
| Message throttle | Limit orders, cancels, and replaces per second/minute. | Prevents runaway loops. |
| Execution throttle | Limit fills per direction and per strategy per time interval. | Prevents rapid unintended accumulation. |
| Daily loss limit | Halt new trades after realized/unrealized loss threshold. | Prevents compounding losses. |
| Greek exposure limits | Cap net delta, gamma, theta, vega by account size and regime. | Controls nonlinear risk. |
| Liquidity filter | Reject contracts with wide spreads, low volume, stale quotes, or low open interest. | Reduces slippage and bad fills. |
| Event halt | Pause around CPI, FOMC, payrolls, major market halts, or broker outages. | Avoids distribution shifts. |
| Reconciliation halt | Stop if local positions differ from broker positions. | Prevents trading against a false book. |
| Manual kill switch | Operator can cancel orders and disable strategies instantly. | Essential human override. |

The kill switch must be independent of the strategy engine. It should be callable from the PySide6 dashboard, command line, and a watchdog service. The safest design is **fail-closed**: if the watchdog, broker heartbeat, data feed, or persistence layer fails, the system cancels open orders and prevents new orders.

## 9. Backtesting, Simulation, and Research Best Practices

A SPY options backtest is only useful if it includes realistic option-chain behavior. Backtesting only the underlying and then assuming option fills is misleading because options are path-dependent, spread-sensitive, and volatility-sensitive.

| Requirement | Minimum Standard |
|---|---|
| Historical option chain | Use bid/ask, IV, Greeks, volume, open interest, and quote timestamps. |
| Fill model | Simulate limit-order fills using bid/ask and quote movement, not last price alone. |
| Slippage model | Scale slippage by spread, VIX regime, time of day, and contract liquidity. |
| Commission and fees | Include broker commission, exchange/regulatory fees, and assignment/exercise assumptions. |
| Corporate actions and dividends | Include SPY distributions and early-exercise risk around dividends. |
| Walk-forward testing | Train/calibrate on one period, test on subsequent unseen periods. |
| Regime coverage | Ensure performance is evaluated separately in bull, bear, calm, high-vol, crisis, and event regimes. |
| Survivorship and look-ahead controls | Use only data known at decision time. |
| Replay testing | Replay historical market events through the live engine before production. |

The research workflow should progress from **rules**, to **paper trading**, to **small live trading**, to **scaled trading**. A model that works only in backtest but fails in paper trading is usually exploiting unrealistic fills, stale labels, or future information.

## 10. Engineering Best Practices for Ubuntu, Wayland, PySide6, and Python

Ubuntu and Wayland are suitable for a professional trading workstation, but the application should be designed so that GUI failures do not affect trading safety. PySide6 should be used for observability, controls, and workflow, while trading logic runs in tested backend modules.

| Engineering Area | Recommendation |
|---|---|
| Python environment | Use `uv` or virtual environments, pinned dependencies, and reproducible lock files. |
| GUI architecture | Use PySide6 `QThread`, `QTimer`, or signal/slot boundaries carefully; never block the UI thread with network calls. |
| Wayland considerations | Test multi-monitor behavior, scaling, clipboard, screenshots, and system-tray behavior because Wayland differs from X11. |
| Process model | Run strategy, execution, data, and GUI as separable processes or services where practical. |
| Persistence | Use SQLite/PostgreSQL for structured events; use Parquet for historical market data. |
| Messaging | Use ZeroMQ, Redis Streams, NATS, or local queues for decoupling if the system grows. |
| Time | Use monotonic clocks for latency and NTP/chrony for wall-clock synchronization. |
| Logging | Use structured JSON logs with correlation IDs for every decision and order. |
| Testing | Unit-test indicators, integration-test broker adapters, replay-test strategies, and chaos-test disconnections. |
| Security | Store broker credentials in an OS keyring or encrypted secret store; never hard-code keys. |
| Deployment | Use systemd services for watchdogs, automatic restart policies, and status monitoring. |
| Observability | Expose metrics for data age, quote latency, orders/minute, fills, P&L, Greeks, and active regime. |

A practical project layout is shown below.

```text
spy_options_system/
  app_gui/                  # PySide6 dashboard only
  core/
    data/                   # feeds, normalization, calendars
    features/               # indicators, greeks, volatility metrics
    regimes/                # regime rules and models
    strategies/             # candidate trade generation
    risk/                   # independent risk approval and kill switch
    execution/              # broker adapters and order state machine
    persistence/            # event store and market data storage
  research/                 # notebooks, experiments, walk-forward studies
  tests/                    # unit, integration, replay, simulation tests
  config/                   # typed configs, no secrets
  scripts/                  # operational scripts
```

## 11. Minimum Viable Production Checklist

The following checklist is a practical readiness standard. If any mandatory item is missing, the system should remain in research or paper-trading mode.

| Capability / Requirement | Minimum Production Standard | Status Target |
|---|---|---|
| Data integrity | Freshness checks, timestamp normalization, and missing-data halt. | Mandatory |
| Option-chain filtering | Spread, volume, open-interest, quote-age, and theoretical-value checks. | Mandatory |
| Regime classification | Transparent six-regime classifier with confidence and no-trade state. | Mandatory |
| Risk engine | Independent limits for loss, contracts, Greeks, buying power, and order count. | Mandatory |
| Execution safety | Limit orders, price collars, cancel/retry budgets, and no default market orders. | Mandatory |
| Kill switch | GUI, CLI, and watchdog-triggered halt/cancel capability. | Mandatory |
| Broker reconciliation | Continuous comparison of local and broker positions/orders. | Mandatory |
| Backtest realism | Option bid/ask, slippage, fees, dividends, and regime-segmented reporting. | Mandatory |
| Paper trading | At least several weeks across multiple volatility states before live trading. | Mandatory |
| Logging and audit | Immutable decision log from data snapshot through fill. | Mandatory |
| Monitoring | Live metrics for data age, P&L, Greeks, quote quality, and active regime. | Mandatory |
| Manual playbook | Written procedures for halt, resume, broker outage, and data outage. | Mandatory |

## 12. Recommended Implementation Roadmap

The best sequence is to build the safety infrastructure before the strategy complexity. A profitable-looking strategy without safety controls is not production-ready.

| Phase | Objective | Deliverable |
|---|---|---|
| Phase 1 | Data and event store | SPY, option chain, VIX, account state, order state, and calendar stored with timestamps. |
| Phase 2 | Indicator engine | Deterministic indicators, IV/RV metrics, Greeks, liquidity filters, and dashboard plots. |
| Phase 3 | Regime engine | Six-regime rules with confidence scoring and no-trade state. |
| Phase 4 | Risk engine | Independent approval/rejection with limits and kill-switch integration. |
| Phase 5 | Paper execution | Broker sandbox or paper account with reconciliation and replay testing. |
| Phase 6 | Strategy MVP | One or two defined-risk strategies only, gated by regime. |
| Phase 7 | Live micro-size | Very small position sizes, strict logs, and daily reviews. |
| Phase 8 | Iterative scaling | Scale only after live slippage, fills, and risk behavior match assumptions. |

## 13. Final Recommendations

The minimum viable autonomous SPY options system should start with a **small symbol universe**, a **six-regime classifier**, a **limited indicator set**, and a **strict risk/execution gate**. The most important design choice is not which indicator to add next; it is whether the system can correctly decide **not to trade**.

For SPY options, the recommended minimum regime taxonomy is **six regimes**: bull trend, bear trend, range/calm, high-volatility mean reversion, crisis/turbulent, and event/transition. The system should map every symbol, indicator, and signal into these regimes so that contract selection, strategy eligibility, sizing, and exits change automatically with market conditions. A calm-market theta strategy should not survive unchanged into a crisis regime, and a directional breakout signal should not bypass liquidity and volatility controls.

The production standard should be: **no stale data, no unmanaged Greeks, no wide-spread contracts, no unbounded order loops, no unreconciled positions, no strategy without a kill switch, and no live trading before realistic option-chain simulation and paper trading**.

## References

[^1]: [OCC, “Characteristics and Risks of Standardized Options”](https://www.theocc.com/company-information/documents-and-archives/options-disclosure-document).  
[^2]: [State Street, “SPY: State Street SPDR S&P 500 ETF Trust”](https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-sp-500-etf-trust-spy).  
[^3]: [Cboe, “Cboe Volatility Index (VIX)”](https://www.cboe.com/tradable_products/vix/).  
[^4]: [Options Industry Council, “Volatility & the Greeks”](https://www.optionseducation.org/advancedconcepts/volatility-the-greeks).  
[^5]: [Macrosynergy, “Classifying market regimes”](https://macrosynergy.com/research/classifying-market-regimes/).  
[^6]: [Federal Register, “Concept Release on Risk Controls and System Safeguards for Automated Trading Environments”](https://www.federalregister.gov/documents/2013/09/12/2013-22185/concept-release-on-risk-controls-and-system-safeguards-for-automated-trading-environments).  
