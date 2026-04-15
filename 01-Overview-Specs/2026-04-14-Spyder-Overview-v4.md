# Spyder Trading System — Codebase Review v17 (v4)
**Date:** April 14, 2026
**Scope:** Current-state inventory of the Spyder codebase
**Prepared by:** Claude Opus 4.6

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Series Summary Table](#2-series-summary-table)
3. [Series A — Core Infrastructure](#3-series-a--core-infrastructure)
4. [Series B — Broker Integration](#4-series-b--broker-integration)
5. [Series C — Market Data](#5-series-c--market-data)
6. [Series D — Strategies](#6-series-d--strategies)
7. [Series E — Risk Management](#7-series-e--risk-management)
8. [Series F — Analysis & Analytics](#8-series-f--analysis--analytics)
9. [Series G — GUI & Dashboard](#9-series-g--gui--dashboard)
10. [Series H — Storage & Persistence](#10-series-h--storage--persistence)
11. [Series I — Integration & Diagnostics](#11-series-i--integration--diagnostics)
12. [Series J — Alerts & Notifications](#12-series-j--alerts--notifications)
13. [Series K — Reports & Analytics](#13-series-k--reports--analytics)
14. [Series L — Machine Learning](#14-series-l--machine-learning)
15. [Series M — Monitoring](#15-series-m--monitoring)
16. [Series N — Options Analytics](#16-series-n--options-analytics)
17. [Series O — Trading Intelligence](#17-series-o--trading-intelligence)
18. [Series P — Portfolio Management](#18-series-p--portfolio-management)
19. [Series Q — Scripts & Launchers](#19-series-q--scripts--launchers)
20. [Series R — Runtime Engines](#20-series-r--runtime-engines)
21. [Series S — Signals](#21-series-s--signals)
22. [Series T — Test Suite](#22-series-t--test-suite)
23. [Series U — Utilities](#23-series-u--utilities)
24. [Series V — Quantitative Models](#24-series-v--quantitative-models)
25. [Series X — On-Demand AI Agents](#25-series-x--on-demand-ai-agents)
26. [Series Y — Autonomous Agents](#26-series-y--autonomous-agents)
27. [Series Z — Communication & IPC](#27-series-z--communication--ipc)

---

## 1. Executive Summary

Spyder is an autonomous algorithmic trading system targeting SPY (S&P 500 ETF) options. The system uses the **Tradier API** for order execution and active runtime market-data access, with **Massive** (formerly Polygon.io) retained as a supported market-data path and fallback. It is structured as 25 distinct Python packages (series A–Z, excluding W), each handling a well-defined domain.

### Codebase Metrics

| Metric | Count |
|--------|------:|
| Total Python files | **475** |
| Production files (A–Z, excluding T) | **353** |
| Test files (T-series) | **122** |
| Total lines of code | **424,200** |
| Production LOC | **330,180** |
| Test LOC | **94,020** |
| Series (packages) | **25** |

### Technology Stack

- **Language:** Python 3.13.3
- **Broker:** Tradier API (REST + WebSocket, Bearer token auth)
- **Market Data:** Tradier (runtime and execution), Massive SDK (supported market-data path / fallback)
- **GUI:** PySide6 (Qt6)
- **ML/AI:** scikit-learn, PyTorch, TensorFlow, XGBoost, stable-baselines3
- **LLM:** Ollama (local inference) — 4 model roles: PRIMARY, FAST, CODE, FINANCE
- **Database:** SQLite
- **Observability:** Prometheus metrics, structured JSON logging
- **Messaging:** ZeroMQ (inter-process), internal pub/sub event bus
- **OS / Platform:** Ubuntu 25.04 / virtualenv (`.venv`)

### Architectural Notes

- **Canonical regime engine:** `SpyderL09_UnifiedRegimeEngine` is the single source of truth for market regime classification. E21, F10, M06, and V02's embedded regime detector are retained as internal/legacy components.
- **Canonical IV engine:** `SpyderV09_IVEngine` is the designated synchronous BSM pricing, IV solver, and Greeks interface.
- **Protocol boundaries:** C00 (market data), E00 (risk), F00 (analysis), Z00 (broker) define typed `Protocol` interfaces enforced at runtime via the T129 protocol-compliance suite and the Q10 CI gate.
- **Risk gate:** E01 `validate_signal()` is the pre-submit risk entry point, wired into D31 `StrategyOrchestrator` for every strategy signal.
- **Optional-dependency handling:** `SpyderU47_OptionalImport.optional_import()` is the canonical helper for platform-specific and optional libraries (`fcntl`, `torch`, `hmmlearn`, `stable_baselines3`, QuantLib, etc.).

---

## 2. Series Summary Table

| Series | Package | Files | LOC | Responsibility |
|--------|---------|------:|----:|----------------|
| A | `SpyderA_Core` | 8 | 9,712 | System orchestration, main entry point, configuration |
| B | `SpyderB_Broker` | 8 | 10,247 | Tradier API integration, order management, execution |
| C | `SpyderC_MarketData` | 26 | 28,172 | Real-time and historical market data, validation, routing |
| D | `SpyderD_Strategies` | 32 | 35,313 | Strategy implementations (Iron Condor, Credit Spread, Zero-DTE, etc.) |
| E | `SpyderE_Risk` | 25 | 28,388 | Risk management, position sizing, circuit breakers, drawdown |
| F | `SpyderF_Analysis` | 22 | 22,320 | Technical indicators, price action, volatility regime, ML prediction |
| G | `SpyderG_GUI` | 20 | 17,825 | PySide6 interface, dashboards, charts, widgets |
| H | `SpyderH_Storage` | 7 | 4,974 | SQLite persistence, data access layer, trade journal |
| I | `SpyderI_Integration` | 13 | 9,164 | Event routing, agent message bus, diagnostics, module registry |
| J | `SpyderJ_Alerts` | 6 | 3,831 | Email, desktop, Telegram, webhook notifications |
| K | `SpyderK_Reports` | 14 | 13,466 | Performance reports, strategy comparison, regulatory filings |
| L | `SpyderL_ML` | 15 | 18,333 | ML models, feature engineering, RL, regime classification |
| M | `SpyderM_Monitoring` | 8 | 6,594 | System health, trading metrics, HMM regime, HTTP health endpoint |
| N | `SpyderN_OptionsAnalytics` | 14 | 15,996 | Options pricing, Greeks, IV surface, flow analysis, GEX |
| O | `SpyderO_TradingIntelligence` | 4 | 4,853 | Advanced indicators, opportunity scanner, strategy optimizers |
| P | `SpyderP_PortfolioMgmt` | 8 | 10,402 | Portfolio optimization, capital allocation, strategy rotation |
| Q | `SpyderQ_Scripts` | 22 | 9,360 | Launchers, validators, utilities, fine-tuning scripts, CI gates |
| R | `SpyderR_Runtime` | 7 | 6,487 | Paper engine, live engine, backtest harness, production deployment |
| S | `SpyderS_Signals` | 12 | 9,556 | Custom signals: DIX, GEX, SKEW, Black Swan, short squeeze, macros |
| T | `SpyderT_Testing` | 122 | 94,020 | Full pytest test suite covering all series |
| U | `SpyderU_Utilities` | 33 | 19,901 | Logger, error handler, date/time, math, encryption, resilience utils |
| V | `SpyderV_QuantModels` | 10 | 11,228 | Quant models, Heston/SABR pricing, GARCH volatility, IV engine |
| X | `SpyderX_Agents` | 17 | 18,645 | On-demand stateless AI agents (16 specialist agents) |
| Y | `SpyderY_AutoAgents` | 13 | 6,944 | Autonomous 24/7 persistent agents + inference backends |
| Z | `SpyderZ_Communication` | 9 | 8,407 | ZeroMQ IPC, message protocol, order routing, auto-hedger |
| **Total** | | **475** | **424,200** | |

---

## 3. Series A — Core Infrastructure

**Package:** `SpyderA_Core` | **8 files** | **9,710 LOC**

The A-Series is the top-level orchestration layer. It bootstraps and coordinates every other subsystem, defines the main event loop, manages configuration, schedules timed jobs, and routes system-wide events.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderA01_Main.py` | 874 | Top-level entry point. Parses CLI arguments, initialises logging, loads configuration, starts all subsystems in dependency order, and manages graceful shutdown. |
| `SpyderA02_TradingEngine.py` | 1,817 | Core trading loop. Drives the main cycle: polls market data, runs analysis, dispatches signals to strategies, validates through risk, submits orders, and updates portfolio state. |
| `SpyderA03_Configuration.py` | 1,337 | System-wide configuration manager. Loads `.env`, merges defaults and YAML overrides, validates types and required fields, and exposes a thread-safe config accessor singleton. |
| `SpyderA04_Scheduler.py` | 1,524 | Task and cron scheduler. Manages timed jobs including pre-market prep, intraday data refreshes, EOD reporting, and regulatory housekeeping with jitter and backoff. |
| `SpyderA05_EventManager.py` | 1,205 | Central synchronous event bus. Publishes and dispatches typed system-wide events (market open, signal triggered, risk breach, order fill) to registered handlers. |
| `SpyderA06_MasterController.py` | 1,599 | Master controller. Coordinates start, pause, resume, and stop sequences across all subsystem modules, with health-check polling and escalation on failures. |
| `SpyderA08_FSeriesOrchestrator.py` | 1,233 | F-Series analysis pipeline orchestrator. Sequences data ingestion → indicator computation → regime detection → signal output, managing inter-step data contracts. |
| `__init__.py` | 123 | Package init with public API exports for core classes. |

---

## 4. Series B — Broker Integration

**Package:** `SpyderB_Broker` | **8 files** | **10,247 LOC**

The B-Series handles all broker-facing concerns: authentication, order lifecycle, position tracking, account information, and Prometheus metric exposure for the broker layer.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderB00_OrderTypes.py` | 827 | Defines all order-type enums (`OrderType`, `OrderSide`, `OrderStatus`), dataclasses (`Order`, `Fill`, `Position`), and constants used across the broker layer. |
| `SpyderB02_OrderManager.py` | 1,665 | Manages the full order lifecycle: creation, validation, submission, partial fills, full fills, cancellations, and state-machine transitions with persistent audit trail. |
| `SpyderB03_PositionTracker.py` | 447 | Real-time position cache. Maintains an in-memory map of open positions keyed by symbol and expiry, updated on every fill event received from the broker. Position lookups and cleanup side determination run inside the `_position_lock` to prevent fill-race inconsistencies. |
| `SpyderB04_AccountManager.py` | 1,344 | Retrieves and caches Tradier account data: balances, buying power, margin utilisation, and option level permissions. Refreshes on configurable TTL. |
| `SpyderB15_PrometheusMetrics.py` | 1,423 | Exposes broker-layer Prometheus metrics including order latency histograms, fill rates, rejection rates, and websocket disconnect counters. |
| `SpyderB30_SPYOptionsChainManager.py` | 955 | Manages SPY options chain snapshots. Fetches, caches, and filters strike/expiry data from the Massive SDK, with configurable delta and DTE bounds. |
| `SpyderB40_TradierClient.py` | 3,236 | Primary Tradier REST and WebSocket client. Handles Bearer token auth, all API endpoints (quotes, options, orders, accounts), retry with exponential backoff, rate limiting, and sandbox/live mode switching. Exposes `get_positions_async()` and `get_account_balances_async()` consumed by the E01 risk manager. |
| `__init__.py` | 350 | Package init exporting `SpyderB40_TradierClient`, order types, and account manager. |

---

## 5. Series C — Market Data

**Package:** `SpyderC_MarketData` | **26 files** | **28,172 LOC**

The C-Series provides all market data ingestion, normalisation, validation, caching, and distribution. The active architecture is Tradier + Massive only. C27 provides the Massive client, while C29 exposes provider-agnostic routing.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderC00_MarketDataProtocol.py` | 660 | Abstract typed Protocol classes defining the interface contract (methods, return types) that all market data providers must satisfy. |
| `SpyderC01_DataFeed.py` | 1,068 | Primary real-time tick data feed. Normalises incoming raw ticks, validates completeness, applies subscriptions, and fans out to all registered consumers. |
| `SpyderC02_HistoricalData.py` | 937 | Historical OHLCV data retrieval, local caching to SQLite, and aggregation across timeframes (1m, 5m, 15m, 1h, daily). |
| `SpyderC03_OptionChain.py` | 1,082 | Options chain snapshot management. Maintains strike/expiry matrices for SPY, applies DTE and delta filters, and provides sorted strike ladders. |
| `SpyderC04_MarketInternals.py` | 981 | Tracks market breadth indicators: advancing/declining issues, new highs/lows, NYSE TICK, TRIN, and Arms Index. |
| `SpyderC05_VolumeProfile.py` | 892 | Intraday and session volume profile calculations: VPOC, High Volume Node (HVN), Low Volume Node (LVN), and Point of Control (POC). |
| `SpyderC06_DataValidator.py` | 1,320 | Multi-layer validation of all incoming market data. Detects stale quotes, out-of-range prices, crossed markets, anomalous IV spikes, and missing legs. |
| `SpyderC08_SPYFeed.py` | 876 | SPY-specific equity feed. Handles split-adjusted prices, dividend adjustments, extended-hours data, and real-time NBBO quote streaming. |
| `SpyderC09_NewsManager.py` | 1,034 | News headline collection and timestamped distribution. Interfaces with financial news APIs and tags events by sector and relevance score. |
| `SpyderC10_VIXAnalyzer.py` | 1,512 | VIX index analysis: term structure (VIX9D, VIX, VIX3M, VIX6M), contango/backwardation classification, and VIX-based regime signals. |
| `SpyderC11_FuturesBasis.py` | 1,361 | ES/SPY futures basis tracking. Computes fair value, roll-adjusted basis, and cash-futures convergence; alerts on arbitrage anomalies. |
| `SpyderC12_DarkPoolFlow.py` | 769 | Tracks and aggregates reported dark pool prints and off-exchange volume; computes dark pool percentage for SPY and related symbols. |
| `SpyderC13_IndexComponents.py` | 1,022 | S&P 500 constituent data management. Provides sector weights, rebalance event tracking, and component-level attribution data. |
| `SpyderC15_MicrostructureAnalyzer.py` | 1,288 | Intraday market microstructure analysis: bid-ask spread evolution, queue depth, order flow toxicity (VPIN estimation), and adverse selection metrics. |
| `SpyderC16_MarketDataCache.py` | 905 | In-memory LRU cache for frequently accessed market data with TTL eviction, size limits, and thread-safe access patterns. |
| `SpyderC17_MarketConfigManager.py` | 1,082 | Dynamic market configuration management: trading session times, holiday schedule overrides, circuit-breaker thresholds, and tick-size tables. |
| `SpyderC18_SKEWCalculator.py` | 1,286 | CBOE SKEW index replication from live options chain data; constructs real-time skew surface and tracks historical percentiles. |
| `SpyderC19_AfterHoursDataManager.py` | 812 | Pre-market and post-market data collection, overnight gap detection, and after-hours risk assessment for open positions. |
| `SpyderC22_FactorDataProvider.py` | 1,311 | Factor data provider for ML pipelines: momentum, value, quality, and size factors computed from market data and fundamentals. |
| `SpyderC23_RealTimeDataOptimizer.py` | 1,218 | Optimises real-time data throughput via batching, compression, priority queuing, and consumer back-pressure management. |
| `SpyderC24_ModelDataPipeline.py` | 1,520 | End-to-end data pipeline preparing raw market data for ML model consumption: feature extraction, normalisation, windowing, and labelling. |
| `SpyderC27_MassiveClient.py` | 1,673 | Massive (formerly Polygon.io) REST and WebSocket client. Provides SPY NBBO quotes, options chain snapshots with Greeks, historical OHLCV bars, VIX, and market status; includes retry logic and rate limiting. |
| `SpyderC29_DataProviderRouter.py` | 278 | Provider-agnostic data routing layer. Reads the active provider configuration and returns the appropriate client instance, decoupling strategy code from data sources. |
| `SpyderC30_OrderFlowAnalyzer.py` | 1,521 | Real-time order flow analysis: trade delta, cumulative delta, buy/sell imbalance, absorption signals, and institutional block detection. |
| `SpyderC35_SentimentAnalyzer.py` | 1,519 | Multi-source sentiment analysis combining news headlines, social mentions, options put/call ratios, and flow-based directional bias scoring. |
| `__init__.py` | 245 | Package init exporting primary feed, Massive client, router, and validator. |

---

## 6. Series D — Strategies

**Package:** `SpyderD_Strategies` | **32 files** | **35,313 LOC**

The D-Series contains all trading strategy implementations. Each strategy extends `SpyderD01_BaseStrategy` and implements signal generation, entry/exit logic, and position sizing callbacks. The orchestrator (D31) and multi-leg coordinator (D32) manage concurrent strategy execution. D31 runs every emitted strategy signal through the E01 `validate_signal()` gate before order submission.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderD00_StrategyConstants.py` | 330 | Strategy-wide constants, enums (`StrategyState`, `SignalType`, `ExitReason`), and shared configuration defaults for all D-Series strategies. |
| `SpyderD01_BaseStrategy.py` | 1,064 | Abstract base class for all strategies. Defines the interface: `generate_signal()`, `enter_position()`, `exit_position()`, `size_position()`, and lifecycle hooks. |
| `SpyderD02_IronCondor.py` | 859 | Iron Condor: simultaneously sells an OTM call spread and an OTM put spread; collects premium from both sides with a defined profit zone. |
| `SpyderD03_CreditSpread.py` | 1,008 | Vertical credit spread (bull put or bear call). Defined-risk premium-selling strategy with adaptive delta targeting and DTE selection. |
| `SpyderD04_ZeroDTE.py` | 1,070 | Zero-days-to-expiry strategy. Captures intraday premium decay on same-day expiring SPY options with aggressive gamma-risk controls and time filters. |
| `SpyderD05_Straddle.py` | 1,117 | Straddle: simultaneous ATM call and put purchase. Profits from large directional moves in either direction; sized to implied move. |
| `SpyderD06_BullPutSpread.py` | 158 | Bull Put Spread: bullish credit spread selling OTM put verticals. Lightweight implementation for direct strategy selection workflow. |
| `SpyderD07_BearCallSpread.py` | 158 | Bear Call Spread: bearish credit spread selling OTM call verticals. Companion to D06 for direct strategy selection. |
| `SpyderD08_OpeningRangeBreakout.py` | 1,159 | Opening Range Breakout. Identifies the first 15- or 30-minute session range and trades confirmed breakouts with options overlays. |
| `SpyderD09_GreeksBasedStrategy.py` | 1,454 | Greeks-driven strategy that dynamically targets specific delta, theta, and vega profiles based on current portfolio exposure and regime signals. |
| `SpyderD10_IronButterfly.py` | 851 | Iron Butterfly: short ATM straddle plus OTM wings. Maximises premium at the target strike with defined upside and downside risk. |
| `SpyderD11_SpecializedZeroDTE.py` | 1,288 | Enhanced Zero-DTE with adaptive strike selection, tighter gamma risk controls, volatility regime gating, and intraday time-of-day filters. |
| `SpyderD12_RSIMeanReversion.py` | 1,019 | RSI-triggered mean-reversion strategy. Fades extreme RSI readings (oversold/overbought) with options-based directional overlays. |
| `SpyderD13_MACrossover.py` | 931 | Moving average crossover strategy. Expresses directional bias from MA crossovers using defined-risk options positions rather than equity. |
| `SpyderD14_CalendarSpread.py` | 1,206 | Calendar (time) spread: sells near-term option and buys same-strike far-term option. Profits from time decay differential and IV term structure. |
| `SpyderD15_StraddleStrangle.py` | 1,381 | Combined straddle and strangle logic with dynamic strike-width optimisation based on IV percentile and expected move. |
| `SpyderD16_RatioSpreads.py` | 1,457 | Ratio spreads (1×2, 1×3): sells more contracts than purchased. Manages complex risk profiles including potential unlimited risk for call ratios. |
| `SpyderD17_DiagonalSpread.py` | 1,359 | Diagonal spread: different strikes and different expirations. Blends theta capture with a directional bias component. |
| `SpyderD18_EvolvedCreditSpread.py` | 1,530 | ML-enhanced credit spread with adaptive strike and DTE selection driven by backtested fitness scores and regime-based parameter evolution. |
| `SpyderD19_JadeLizard.py` | 1,205 | Jade Lizard: short OTM put combined with a short OTM call spread. Structured to eliminate upside loss while collecting net credit. |
| `SpyderD20_VerticalSpreadOptimizer.py` | 841 | Optimises vertical spread parameters (width, delta, DTE) across all available SPY expirations using a scoring function over risk/reward metrics. |
| `SpyderD21_DoubleCalendar.py` | 1,402 | Double Calendar: two calendar spreads at different strikes. Widens the profit zone versus a single calendar while maintaining theta advantage. |
| `SpyderD22_AdaptiveVolatility.py` | 1,109 | Adapts strategy selection and position sizing in real time based on the detected volatility regime (low/medium/high/extreme). |
| `SpyderD25_UnifiedCreditSpreadEngine.py` | 1,454 | Unified engine consolidating all credit spread variants under a single scoring and selection framework for consistent risk-adjusted strike choice. |
| `SpyderD26_GammaScalper.py` | 1,132 | Gamma scalping: maintains delta-neutral long-gamma positions and dynamically hedges via underlying or near-ATM options as delta drifts. |
| `SpyderD27_EarningsStrategy.py` | 1,260 | Earnings event strategy. Positions ahead of implied move windows around scheduled announcements; manages IV crush risk on expiry. |
| `SpyderD28_VIXHedging.py` | 1,069 | VIX-based portfolio tail hedge. Activates protective positions when VIX signals elevated spike risk; manages cost via spread structures. |
| `SpyderD30_RegimeGatedSelector.py` | 1,308 | Regime-gated strategy selector. Maps the current market regime (from L09) to the best-fit strategy set and activates accordingly. |
| `SpyderD31_StrategyOrchestrator.py` | 2,080 | Strategy orchestrator. Coordinates concurrent strategy execution, manages capital budgeting between active strategies, and arbitrates signal conflicts. All emitted signals are routed through E01 `validate_signal()` and rejected signals publish a `RISK_ALERT` event. |
| `SpyderD32_MultiLegStrategyCoordinator.py` | 2,074 | Multi-leg order coordinator. Sequences leg submissions, manages legging risk, prevents overlapping position exposure, and rolls complex multi-leg structures. |
| `SpyderD33_RenaissanceMeanReversion.py` | 742 | Renaissance-inspired mean-reversion using the Ornstein-Uhlenbeck process to model price as a mean-reverting diffusion and size positions accordingly. |
| `__init__.py` | 253 | Package init exporting all strategy classes and the orchestrator. |

---

## 7. Series E — Risk Management

**Package:** `SpyderE_Risk` | **25 files** | **28,275 LOC**

The E-Series implements all risk management logic in a multi-layer framework: pre-trade validation, real-time position monitoring, portfolio-level Greeks enforcement, drawdown controls, and circuit breakers. E01 is the entry point for all pre-submit strategy signal validation via `validate_signal()` and pulls live position and account data from the Tradier client.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderE00_RiskProtocol.py` | 228 | Typed Protocol interfaces defining the E-Series ↔ D-Series boundary. Specifies pre-trade check, position-size approval, and risk-verdict return types. |
| `SpyderE01_RiskManager.py` | 1,280 | Core risk manager entry point. Routes all pre-trade and post-trade risk checks to the appropriate E-Series sub-modules and aggregates verdicts. Consumes live positions and account balances from the Tradier client via `_request_positions()` and `_request_account_summary()`. Exposes `validate_signal()` as the authoritative pre-submit gate. |
| `SpyderE02_PositionSizer.py` | 1,019 | Dynamic position sizing. Computes contract quantities based on volatility, account equity, Greeks budget, and per-trade risk percentage limits. |
| `SpyderE03_StopLossManager.py` | 1,449 | Stop-loss orchestration: fixed percentage, trailing, time-based (theta decay), and Greeks-based (vega blowup) stop triggers. |
| `SpyderE04_DrawdownControl.py` | 903 | Monitors intraday and rolling drawdown against configurable limits. Escalates alerts, reduces position sizing, and halts trading at hard limits. |
| `SpyderE05_AutomaticRebalancer.py` | 767 | Auto-rebalances portfolio allocations when individual strategies drift beyond their tolerance bands relative to target weights. |
| `SpyderE06_RiskMetrics.py` | 1,162 | Computes core risk KPIs: VaR, CVaR, Sharpe ratio, Sortino ratio, maximum drawdown, Calmar ratio, and win/loss statistics. |
| `SpyderE07_ProbabilisticSharpe.py` | 702 | Probabilistic Sharpe Ratio with bootstrapped confidence intervals using the Ledoit-Wolf estimator for covariance shrinkage. |
| `SpyderE08_PositionGroupValidator.py` | 1,146 | Validates correlated position groups. Enforces combined Greeks limits and notional exposure caps for positions that share identical underlying risk factors. |
| `SpyderE09_VolatilityRiskManager.py` | 1,092 | Volatility-specific risk controls: portfolio vega limits, IV crush protection for long positions, and regime-aware sizing adjustments. |
| `SpyderE10_CorrelationRiskManager.py` | 1,939 | Cross-position correlation analysis via rolling covariance matrices. Prevents over-concentration in correlated directional bets. |
| `SpyderE11_MaxLossProtection.py` | 937 | Hard maximum-loss circuit. Liquidates all positions when realised P&L breaches the configured absolute or percentage maximum loss threshold. |
| `SpyderE12_PortfolioVaR.py` | 1,432 | Portfolio-level VaR via historical simulation, parametric (delta-gamma), and Monte Carlo methods with configurable confidence intervals. |
| `SpyderE13_DayProfitTarget.py` | 2,243 | Daily profit target management. Scales back risk exposure once the daily target is met; implements graduated risk reduction tiers. |
| `SpyderE14_KellyPositionSizer.py` | 715 | Kelly Criterion position sizing with fractional Kelly (typically 25–50%) applied for conservative capital compounding. |
| `SpyderE15_GreekLimitsManager.py` | 1,126 | Enforces portfolio-level Greeks exposure limits: delta, gamma, vega, theta, and rho with configurable per-strategy and aggregate hard caps. |
| `SpyderE16_CircuitBreakerProtocol.py` | 476 | Trading-layer circuit breaker. Halts all new order submissions on trigger conditions (excessive loss, volatility spike, data anomaly) with manual reset. |
| `SpyderE17_RealTimeStressTesting.py` | 1,537 | Continuous intraday stress testing. Applies historical shock scenarios (2020-03, 2022-01, flash crashes) to current Greeks in real time. |
| `SpyderE18_FSeriesRiskIntegrator.py` | 1,345 | Integrates F-Series analysis signals (regime, trend, volatility) into the risk validation pipeline to adjust limits dynamically by market state. |
| `SpyderE19_UnifiedRiskCoordinator.py` | 1,165 | Unified coordinator that fans risk check requests out to all E-Series modules in parallel and aggregates verdicts with priority ordering. |
| `SpyderE20_FrustrationAnalyzer.py` | 1,625 | Behavioural risk analysis. Detects over-trading patterns, revenge-trade conditions, and systematic decision drift; provides cooling-off recommendations. |
| `SpyderE21_HMMRegimeDetector.py` | 1,041 | Legacy HMM regime detector retained as an internal component. The canonical regime signal is supplied by `SpyderL09_UnifiedRegimeEngine`. |
| `SpyderE22_KernelRegression.py` | 832 | Non-parametric kernel regression for trend and volatility estimation; used as a signal component within E21 and E17. |
| `SpyderE23_PortfolioOptimizer.py` | 2,051 | Mean-variance and Black-Litterman portfolio optimisation. Computes efficient frontier, risk parity weights, and optimal strategy allocations. |
| `__init__.py` | 203 | Package init exporting the risk coordinator, manager, and metrics classes. |

---

## 8. Series F — Analysis & Analytics

**Package:** `SpyderF_Analysis` | **22 files** | **22,320 LOC**

The F-Series provides the analytical backbone: technical indicators, price action patterns, volatility analysis, trend detection, Greeks computation, and the ML prediction integration layer. F01 `IndicatorEngine` is the canonical indicator source; F09 entry filters include portfolio-level Greek projection checks against configurable `max_portfolio_{delta,gamma,vega}` limits.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderF00_AnalysisProtocol.py` | 267 | Typed Protocol interfaces defining the F-Series ↔ X-Series boundary for passing analysis results to AI agents. `AnalyticsProviderProtocol` exposes `calculate_all_indicators` as its primary indicator method. |
| `SpyderF01_Indicators.py` | 871 | Core technical indicator library: RSI, MACD, Bollinger Bands, ATR, EMA, SMA, Stochastic, and Williams %R with configurable periods. Canonical indicator engine — all analytics callers should route indicator requests here. |
| `SpyderF02_PriceAction.py` | 872 | Price action pattern recognition: candlestick formations (doji, hammer, engulfing, pin bars), inside bars, and multi-bar structures. |
| `SpyderF03_SupportResistance.py` | 791 | Automated support and resistance level detection via swing pivots, volume clusters, and round-number proximity scoring. |
| `SpyderF04_VolatilityAnalysis.py` | 922 | Historical and realised volatility calculations: HV cone, IV rank, IV percentile, GARCH(1,1) short-term vol estimation. |
| `SpyderF05_TrendDetection.py` | 772 | Multi-timeframe trend detection and classification into strong bull, weak bull, neutral, weak bear, and strong bear states. |
| `SpyderF06_GreeksCalculator.py` | 991 | Black-Scholes-Merton Greeks computation: delta, gamma, theta, vega, rho, with dividend yield and discrete dividend adjustments. |
| `SpyderF07_GapAnalyzer.py` | 758 | Market gap detection, classification (common, breakaway, runaway, exhaustion), gap fill probability estimation, and overnight gap tracking. |
| `SpyderF08_VolatilityRegime.py` | 999 | Volatility regime classification (low / medium / high / extreme) using multi-signal consensus: IV percentile, HV ratio, VIX level, ATR normalised. |
| `SpyderF09_EntryFilters.py` | 1,310 | Pre-entry signal filters: time-of-day restrictions, bid-ask spread quality, volume thresholds, regime guards, news blackout windows, and portfolio-level Greek projection checks against `max_portfolio_{delta,gamma,vega}` bands. |
| `SpyderF10_MarketRegimeDetector.py` | 1,511 | Legacy composite regime detector. Retained as an internal component; `calculate_all_indicators()` returns `None` so callers are forced to route to F01. The canonical regime signal is supplied by `SpyderL09_UnifiedRegimeEngine`. |
| `SpyderF11_GreeksAggregator.py` | 1,047 | Aggregates position-level Greeks to portfolio-level net exposure with P&L attribution by Greeks component. Source of `portfolio_greeks` consumed by F09 entry filters. |
| `SpyderF13_ModelValidation.py` | 1,436 | Walk-forward validation, out-of-sample testing, information ratio decomposition, and overfitting detection (Deflated Sharpe Ratio). |
| `SpyderF14_MarketMicrostructure.py` | 1,539 | Advanced microstructure analytics: intraday trade clustering, volume-synchronised VPIN, order-flow imbalance, and toxic flow detection. |
| `SpyderF16_RealTimeAnalytics.py` | 1,687 | Streaming real-time analytics pipeline. Feeds live dashboards, strategy signal triggers, and risk monitors with sub-second latency. |
| `SpyderF17_UnifiedPerformanceEngine.py` | 1,532 | Unified performance metric engine: Sharpe, Calmar, Sortino, MAR, win rate, profit factor, edge ratio, and attribution across all strategies. |
| `SpyderF18_MaxPainCalculator.py` | 1,072 | Options max pain level calculation from open interest data. Identifies gravitational strike levels for SPY at each expiration. |
| `SpyderF19_AnchoredVWAP.py` | 1,184 | Anchored VWAP from user-defined anchor events (market open, gap fill, earnings). Computes VWAP bands and standard deviation channels. |
| `SpyderF20_Indicators.py` | 391 | Supplementary indicator set: less-common indicators including Elder Ray, Chande Momentum Oscillator, and Market Facilitation Index. |
| `SpyderF21_RenaissanceIndicators.py` | 860 | Renaissance Technologies-inspired quantitative indicators: eigenportfolio momentum decomposition and Kalman-filtered trend estimation. |
| `SpyderF22_MLPrediction.py` | 1,374 | ML-driven price direction and volatility prediction engine integrated into the F-Series pipeline. Wraps L-Series models with real-time inference. |
| `__init__.py` | 157 | Package init exporting indicator libraries, regime detector, and performance engine. |

---

## 9. Series G — GUI & Dashboard

**Package:** `SpyderG_GUI` | **20 files** | **17,823 LOC**

The G-Series implements the PySide6 (Qt6) graphical interface. The central component is G05 (`SpyderG05_TradingDashboard.py` at 6,595 LOC), which integrates positions, P&L, Greeks, orders, signals, and market status into a single view.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderG00_ApplicationManager.py` | 463 | QApplication lifecycle manager. Sets up dark theme, registers exception hooks, configures high-DPI display, and manages application-level events. |
| `SpyderG01_MainWindow.py` | 96 | Main window shell. Defines the docking layout, menu bar, status bar, and tab structure hosting all dashboard widgets. |
| `SpyderG02_GUIEntry.py` | 128 | GUI entry point. Launches the application in standalone mode or embedded within the trading engine process. |
| `SpyderG03_OptionChainWidget.py` | 227 | Options chain table widget. Displays strike grid with bid/ask, IV, delta, gamma, open interest, and volume with live updates. |
| `SpyderG04_ChartWidget.py` | 1,632 | Primary OHLCV candlestick chart widget built with Qt/Matplotlib. Supports indicator overlays, volume bars, VWAP, and regime colouring. |
| `SpyderG05_TradingDashboard.py` | 6,595 | Main trading dashboard — the largest module in the G-Series. Integrates positions, P&L, Greeks exposure, open orders, market internals, agent status, and signal feeds in a unified tabbed view with live data refresh. |
| `SpyderG06_DashboardData.py` | 521 | Data model layer for the dashboard. Normalises raw broker and market data into display-ready structures; manages refresh timing. |
| `SpyderG09_RiskParametersDialog.py` | 1,198 | Risk parameters configuration dialog. Allows operator adjustment of delta limits, VaR caps, daily loss thresholds, and Greeks limits at runtime. |
| `SpyderG11_SkewMonitorDialog.py` | 1,371 | SKEW index monitor dialog. Shows real-time CBOE SKEW chart, historical percentile, term structure, and put/call skew surface. |
| `SpyderG12_SignalInfoDialog.py` | 521 | Signal information popup. Displays signal source, confidence score, Greeks impact, recommended action, and contributing indicators. |
| `SpyderG13_EnhancedWidgets.py` | 749 | Enhanced UI widget collection: circular gauges, sparkline charts, heat-map grids, traffic-light indicators, and progress rings. |
| `SpyderG14_Dashboard.py` | 128 | Lightweight legacy stub dashboard for backward compatibility with older launch scripts. |
| `SpyderG15_ConnectAPIStatus.py` | 792 | API connectivity status panel. Displays live/sandbox mode indicator, Tradier latency, Massive data stream health, and connection uptime. |
| `SpyderG16_CircuitBreakerMonitor.py` | 323 | Circuit breaker status monitor. Shows currently active breakers, trigger conditions, breach history, and manual reset controls. |
| `SpyderG29_ChartWidgetPlotly.py` | 856 | Plotly-based interactive chart widget embedded in PySide6 via `QWebEngineView`. Supports pan, zoom, and hover tooltips. |
| `SpyderG30_PlotlyDataBridge.py` | 555 | Converts internal OHLCV and indicator structures into Plotly-compatible JSON trace format for G29 rendering. |
| `SpyderG31_PlotlyTemplates.py` | 747 | Plotly chart templates and dark-mode themes with branded colour palettes, font definitions, and layout presets. |
| `SpyderG32_AgentHealthDashboard.py` | 302 | Real-time agent health dashboard panel. Displays heartbeat status, last-activity timestamps, error rates, and task completion rates for all X-Series and Y-Series agents. |
| `SpyderG99_GUILogHandler.py` | 284 | GUI log handler. Streams `SpyderLogger` output to an in-dashboard scrollable log console with colour-coded severity levels. |
| `__init__.py` | 335 | Package init exporting the application manager, main window, and trading dashboard. |

---

## 10. Series H — Storage & Persistence

**Package:** `SpyderH_Storage` | **7 files** | **4,974 LOC**

The H-Series manages all SQLite-backed persistence: schema management, parameterised data access, trade history, market data caching, performance analytics storage, and trade journaling.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderH01_DataAccessLayer.py` | 1,079 | Data access layer (DAL). Provides parameterised SQL execution, connection pooling, transaction management, and schema-migration versioning. |
| `SpyderH02_DatabaseManager.py` | 925 | SQLite database manager. Handles schema initialisation, incremental migrations, VACUUM scheduling, integrity checks, and automated daily backups. |
| `SpyderH03_MarketDataCache.py` | 692 | Market data cache layer. Combines in-process LRU cache with SQLite-backed persistence for ticks, bars, and option chains with TTL eviction. |
| `SpyderH04_TradeRepository.py` | 777 | Trade history repository. Full CRUD operations for trades, fills, positions, and audit records with time-range query support. |
| `SpyderH07_PerformanceAnalytics.py` | 852 | Performance analytics storage. Persists and retrieves Sharpe, Sortino, max drawdown, strategy-level win rates, and equity curves. |
| `SpyderH08_TradeJournal.py` | 575 | Trade journaling system. Records trade decision rationale, market context at entry, outcome notes, and lessons-learned tags for post-trade review. |
| `__init__.py` | 74 | Package init exporting the DAL, database manager, and trade repository. |

---

## 11. Series I — Integration & Diagnostics

**Package:** `SpyderI_Integration` | **13 files** | **9,167 LOC**

The I-Series handles all cross-system integration concerns: the central event bus, agent message routing, runtime configuration management, system diagnostics, and a module registry.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderI01_IntegrationHub.py` | 829 | Central integration hub. Registers all subsystems, manages service discovery, and provides a unified interface for cross-series communication. |
| `SpyderI02_EventRouter.py` | 1,150 | Event routing system. Implements publish-subscribe with priority queues, dead-letter handling, and both synchronous and async dispatch modes. |
| `SpyderI03_ConfigManager.py` | 1,394 | Runtime configuration manager. Supports hot-reload of config changes without restart, environment variable overrides, and JSON Schema validation. |
| `SpyderI04_DiagnosticsEngine_Core.py` | 596 | Diagnostics engine core. Orchestrates data collection, analysis, and report generation across all subsystems on demand. |
| `SpyderI05_DiagnosticsEngine_Analyzers.py` | 316 | Diagnostic analyser plugins. Interprets collected metrics for anomaly detection, threshold violations, and degradation patterns. |
| `SpyderI06_AgentMessageBus.py` | 836 | Agent message bus. Routes typed messages between X-Series on-demand agents and Y-Series autonomous agents with priority and delivery guarantees. |
| `SpyderI07_SyntaxValidator.py` | 819 | Syntax and schema validator for dynamically loaded configuration files and agent-generated code snippets before execution. |
| `SpyderI08_DiagnosticsEngine_DataCollector.py` | 650 | Data collector. Gathers CPU, memory, network latency, and trade-flow metrics at configurable intervals for the diagnostics engine. |
| `SpyderI09_DiagnosticsEngine_HealthChecks.py` | 706 | Health check runner. Executes liveness and readiness probes for all registered system components; returns structured health verdicts. |
| `SpyderI10_DiagnosticsEngine_Types.py` | 441 | Type definitions for all diagnostics data structures, enums (`HealthStatus`, `SeverityLevel`), and typed result containers. |
| `SpyderI11_DiagnosticsEngine_Utils.py` | 669 | Utility functions shared across all DiagnosticsEngine sub-modules: time formatting, metric aggregation, and threshold comparison helpers. |
| `SpyderI12_ModuleRegistry.py` | 455 | Central registry of all Spyder modules. Records series, class name, status, dependencies, and version metadata for discovery and validation. |
| `__init__.py` | 306 | Package init exporting the integration hub, event router, message bus, and config manager. |

---

## 12. Series J — Alerts & Notifications

**Package:** `SpyderJ_Alerts` | **6 files** | **3,831 LOC**

The J-Series handles all outbound notifications across multiple channels: email (SMTP), desktop (libnotify), Telegram (Bot API), and HTTP webhooks (Slack, Teams, Discord).

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderJ01_AlertManager.py` | 784 | Alert management hub. Handles routing, deduplication within configurable windows, priority escalation, and rate limiting per alert type. |
| `SpyderJ02_EmailNotifier.py` | 825 | Email notification via SMTP with TLS. Sends HTML-formatted trade alerts, daily P&L summaries, and risk breach notifications with attachment support. |
| `SpyderJ03_WebhookNotifier.py` | 356 | HTTP webhook notifications. Sends formatted messages to Slack, Microsoft Teams, and Discord via their respective webhook payload schemas. |
| `SpyderJ04_DesktopNotifier.py` | 781 | Desktop notification integration using libnotify/D-Bus on Linux. Supports urgency levels, action buttons, and icon badges. |
| `SpyderJ05_TelegramBot.py` | 1,029 | Telegram bot notifier. Sends trade alerts, account balance updates, and risk warnings via the Telegram Bot API with markdown formatting. |
| `__init__.py` | 56 | Package init exporting the alert manager and all notifier classes. |

---

## 13. Series K — Reports & Analytics

**Package:** `SpyderK_Reports` | **14 files** | **13,466 LOC**

The K-Series generates all performance, risk, and regulatory reports, ranging from daily P&L summaries to institutional-grade tearsheets and live per-strategy P&L attribution.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderK01_ReportGenerator.py` | 299 | Abstract base report generator. Defines the report interface: `generate()`, `export_pdf()`, `export_csv()`, and report metadata standards. |
| `SpyderK02_DailyTradingReport.py` | 1,568 | Comprehensive daily P&L report. Includes trade log, strategy breakdown, Greeks exposure at close, commissions, slippage, and next-day outlook. |
| `SpyderK03_PerformanceDashboard.py` | 938 | Performance summary dashboard. Renders equity curve, rolling drawdown chart, rolling Sharpe, win rate trend, and best/worst trade analysis. |
| `SpyderK04_ExecutionAnalytics.py` | 1,087 | Execution quality analytics. Measures slippage vs. mid-market, fill-rate statistics, market impact estimation, and NBBO comparison. |
| `SpyderK05_RiskReport.py` | 805 | Daily risk report. Covers VaR at multiple confidence levels, stress test scenario results, Greeks exposure heat map, and limit utilisation percentage. |
| `SpyderK06_PortfolioAnalytics.py` | 1,454 | Portfolio-level analytics. Generates sector exposure breakdown, cross-strategy correlation matrix, return attribution, and factor contribution analysis. |
| `SpyderK07_StrategyComparison.py` | 895 | Side-by-side strategy comparison report. Ranks all active strategies by risk-adjusted return, win rate, maximum drawdown, and information ratio. |
| `SpyderK08_MLPerformanceReport.py` | 1,625 | ML model performance report. Tracks prediction accuracy per model, feature importance rankings, model drift detection, and retrain triggers. |
| `SpyderK09_RegulatoryReports.py` | 1,417 | Regulatory and compliance reports. Generates trade confirmations, position limit utilisation logs, and audit trails in exchange-compatible formats. |
| `SpyderK10_RealTimePerformanceAnalytics.py` | 1,103 | Streaming real-time performance analytics. Feeds live intraday P&L, trade count, realised Sharpe, and strategy metrics to GUI dashboards. |
| `SpyderK11_UnifiedSharpeDashboard.py` | 957 | Unified Sharpe ratio dashboard. Displays rolling (20d, 60d), annualised, and Probabilistic Sharpe views across all strategies simultaneously. |
| `SpyderK12_InstitutionalTearSheet.py` | 787 | Institutional-style strategy tearsheet. Full fact sheet including CAGR, Sharpe, Sortino, Calmar, skewness, kurtosis, and monthly returns grid. |
| `SpyderK13_StrategyPnLLadder.py` | 404 | Live per-strategy P&L attribution ladder during market hours. Shows real-time contribution of each active strategy to total portfolio P&L. |
| `__init__.py` | 127 | Package init exporting the report generator base class and all K-Series report classes. |

---

## 14. Series L — Machine Learning

**Package:** `SpyderL_ML` | **15 files** | **18,333 LOC**

The L-Series implements all machine learning infrastructure: model management, feature engineering, inference wrappers, reinforcement learning for options adjustment, regime classification, and federated learning. L09 is the canonical regime engine for the entire system.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderL01_MLPredictor.py` | 1,169 | Core ML prediction engine. Loads and manages trained model artifacts, handles real-time inference requests, and caches predictions with TTL. |
| `SpyderL07_PaperTradeLearner.py` | 1,675 | Learns from paper trading outcomes. Updates model priors, tracks strategy alpha decay, and adjusts feature weights based on recent trade results. |
| `SpyderL08_EntryOptimizer.py` | 1,895 | ML-driven entry timing optimiser. Uses gradient-boosted trees to select optimal strike, DTE, and entry price given current market features. |
| `SpyderL09_UnifiedRegimeEngine.py` | 2,200 | **Canonical regime engine.** Unified ML regime classification combining Hidden Markov Models, k-means clustering, and ensemble voting to output a consensus regime label. Designated single source of truth for market regime signals across the entire Spyder system. |
| `SpyderL10_FeatureEngineering.py` | 1,314 | Automated feature engineering pipeline. Generates technical, microstructure, order-flow, and sentiment features; handles normalisation and lag construction. |
| `SpyderL11_MLModelManager.py` | 1,168 | ML model lifecycle manager. Handles versioning, training job dispatch, evaluation, deployment promotion, rollback, and model registry. |
| `SpyderL12_RandomForestEnsemble.py` | 765 | Random forest ensemble model for regime classification and next-period direction probability scoring. Includes feature importance reporting. |
| `SpyderL13_LSTMPricer.py` | 750 | LSTM-based deep learning model for options pricing and IV surface prediction across strikes and tenors. |
| `SpyderL14_RealTimePredictor.py` | 827 | Low-latency real-time inference wrapper. Batches feature vectors, routes to deployed model endpoints, and returns predictions within single-digit milliseconds. |
| `SpyderL15_MomentPredictor.py` | 753 | Short-term price momentum predictor. Scores momentum strength on a 0–1 scale using ML over a configurable lookback window. |
| `SpyderL16_OptionsAdjustmentRL.py` | 1,984 | Reinforcement learning agent for adaptive options position adjustments. Defines an abstract environment base class overridden by concrete strategy environments (e.g. `IronCondorEnvironment`); trained with PPO via stable-baselines3. Manages roll, close, or hold decisions. |
| `SpyderL17_FederatedLearning.py` | 1,683 | Privacy-preserving federated learning framework. Aggregates model updates across multiple strategy instances without sharing raw trade data. |
| `SpyderL18_EnhancedMLIntegration.py` | 1,221 | Enhanced integration layer connecting L-Series ML models to the D-Series strategy and E-Series risk subsystems via typed signal objects. |
| `SpyderL19_RLTrainingPipeline.py` | 795 | RL training pipeline. Manages environment setup, reward function configuration, episode management, and checkpoint saving for L16. |
| `__init__.py` | 134 | Package init exporting the ML predictor, regime engine, model manager, and RL pipeline. |

---

## 15. Series M — Monitoring

**Package:** `SpyderM_Monitoring` | **8 files** | **6,594 LOC**

The M-Series provides system health monitoring, trading metrics collection, transaction cost analysis, HMM regime detection for system-level state tracking, and an HTTP health endpoint.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderM01_SystemMonitor.py` | 962 | System health monitor. Tracks CPU, memory, disk, network, and process metrics via psutil; alerts on threshold breaches. |
| `SpyderM03_AIAgentMonitor.py` | 878 | AI agent health monitor. Tracks X-Series and Y-Series agent response times, error rates, task completion rates, and heartbeat liveness. |
| `SpyderM04_TradingMetrics.py` | 1,125 | Trading metrics collector. Captures real-time P&L, fill count, order rejection rate, execution latency histograms, and Prometheus metric exports. |
| `SpyderM05_TransactionCostAnalysis.py` | 1,349 | Transaction cost analysis (TCA). Breaks down total trade cost into commission, bid-ask spread capture, and market impact components per trade. |
| `SpyderM06_HMMRegimeDetector.py` | 1,490 | Legacy standalone HMM regime detector. Retained as an internal component; the canonical regime signal is supplied by `SpyderL09_UnifiedRegimeEngine`. |
| `SpyderM07_MigrationMonitor.py` | 372 | Monitors market-data migration and provider-cutover jobs for completeness, validation, and row-count reconciliation. |
| `SpyderM08_HealthEndpoint.py` | 342 | Lightweight HTTP health-check endpoint. Exposes `/health` (liveness) and `/metrics` (Prometheus scrape target) for load balancer and monitoring integration. |
| `__init__.py` | 76 | Package init exporting the system monitor, trading metrics, and health endpoint. |

---

## 16. Series N — Options Analytics

**Package:** `SpyderN_OptionsAnalytics` | **14 files** | **15,996 LOC**

The N-Series is the dedicated options analytics engine, covering pricing (BSM, binomial, American), Greeks computation, IV surface construction, flow tracking, gamma exposure, and market impact modelling.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderN01_OptionsPricer.py` | 1,218 | Options pricing engine implementing Black-Scholes-Merton, Cox-Ross-Rubinstein binomial tree, and Barone-Adesi-Whaley American option models. |
| `SpyderN02_ImpliedVolatilityEngine.py` | 1,285 | IV solver using Newton-Raphson with bisection fallback. Handles both European and American options; reconstructs full IV surface from chain data. |
| `SpyderN03_OptionsChainManager.py` | 1,275 | Options chain normalisation. Fills gaps in sparse chains, validates strikes for arbitrage violations, and computes chain-level analytics (skew slope, term structure). |
| `SpyderN04_OptionsGreeksCalculator.py` | 1,671 | High-precision Greeks calculator. Computes delta, gamma, theta, vega, rho, and second-order Greeks (charm, vanna, volga, vomma) for full chain coverage. |
| `SpyderN05_OptionsExpirationManager.py` | 1,141 | Expiration cycle manager. Tracks DTE for all open positions, schedules roll alerts, detects pin risk, and manages early-expiry checks. |
| `SpyderN06_VolatilitySurfaceBuilder.py` | 1,087 | Constructs the full 3-D implied volatility surface using SVI, SABR, and cubic spline interpolation across strikes and tenors. |
| `SpyderN07_OptionsFlowTracker.py` | 1,219 | Tracks unusual options flow: sweep detection, block print identification, open interest changes, and call/put skew shifts. |
| `SpyderN08_VolatilitySurface.py` | 1,384 | Volatility surface model storage and querying layer. Fits SVI, SABR, and local-vol models; provides point-in-time IV lookups by strike and expiry. |
| `SpyderN09_GammaExposure.py` | 1,266 | Net Gamma Exposure (GEX) calculation from SPY open interest data. Identifies dealer hedging pressure levels and GEX flip points by strike. |
| `SpyderN10_OptionsFlowAnalyzer.py` | 632 | Analyses recent options flow for directional signals: bull/bear skew, net premium paid vs. received, and institutional sweep patterns. |
| `SpyderN11_OptionsGreeksFlow.py` | 1,177 | Greeks-adjusted flow analysis. Computes delta-weighted and vega-weighted order flow imbalance for directional and volatility bias signals. |
| `SpyderN12_VolatilitySurfaceAI.py` | 1,281 | AI-enhanced volatility surface. Applies ML corrections to model-implied prices, detecting and pricing smile arbitrage and surface anomalies. |
| `SpyderN13_MarketImpactModel.py` | 1,250 | Market impact model. Estimates the price impact of options trade sizes; used by E-Series for realistic fill-cost modelling. |
| `__init__.py` | 110 | Package init exporting the pricing engine, Greeks calculator, IV engine, and surface builder. |

---

## 17. Series O — Trading Intelligence

**Package:** `SpyderO_TradingIntelligence` | **4 files** | **4,853 LOC**

The O-Series provides advanced analytical capabilities beyond the core F-Series: an extended institutional-grade indicator library, opportunity scanning across all SPY expirations, and strategy parameter optimisation.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderO01_CoreTechnicalIndicators.py` | 1,281 | Extended institutional-grade technical indicator library. Includes Elder Impulse System, Connors RSI, Heikin-Ashi derived signals, and market-breadth composites. |
| `SpyderO02_TradingOpportunityScanner.py` | 1,340 | Scans all SPY strike/expiry combinations for high-probability opportunities meeting configurable IV rank, delta, and credit criteria in real time. |
| `SpyderO03_StrategyOptimizers.py` | 1,883 | Strategy parameter optimisation engine. Uses Optuna (Bayesian optimisation), grid search, and genetic algorithms to find optimal parameters per regime. |
| `__init__.py` | 349 | Package init exporting the scanner, indicator library, and optimiser with strategy configuration integration. |

---

## 18. Series P — Portfolio Management

**Package:** `SpyderP_PortfolioMgmt` | **8 files** | **10,402 LOC**

The P-Series handles portfolio-level management: tracking all open positions, optimising capital allocation across strategies, managing correlation, dynamically rotating strategy weights by regime, and Renaissance-style position sizing. P01–P03 expose their global singletons through RLock-guarded factories to keep bootstrap and agent initialisation thread-safe.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderP01_PortfolioManager.py` | 2,183 | Top-level portfolio manager. Tracks all open positions, computes portfolio-level Greeks, P&L attribution, and provides the authoritative position state. Global singleton accessors guarded by `threading.RLock`. |
| `SpyderP02_AllocationOptimizer.py` | 2,221 | Capital allocation optimiser. Implements mean-variance, risk-parity, and Black-Litterman optimisation; computes efficient frontier and target weights. Global singleton accessors guarded by `threading.RLock`. |
| `SpyderP03_CorrelationAnalyzer.py` | 730 | Cross-strategy and cross-position correlation monitoring. Generates correlation matrix reports and flags concentration risk from correlated bets. Global singleton accessors guarded by `threading.RLock`. |
| `SpyderP04_CapitalAllocator.py` | 1,582 | Dynamic capital allocation engine. Adjusts per-strategy capital budgets based on recent performance, Sharpe, and drawdown metrics. |
| `SpyderP05_MultiStrategyAllocator.py` | 1,356 | Multi-strategy capital allocator with regime-conditional weighting. Increases allocation to regime-fitted strategies; reduces degraded ones. |
| `SpyderP06_StrategyRotation.py` | 1,315 | Strategy rotation engine. Schedules activation and deactivation of strategies based on detected regime, seasonal patterns, and performance thresholds. |
| `SpyderP07_RenaissancePositionSizer.py` | 686 | Renaissance-inspired statistical position sizing. Decomposes portfolio risk into eigenportfolios and sizes each position to its contribution to systematic risk. |
| `__init__.py` | 329 | Package init exporting the portfolio manager, allocators, and rotation engine. |

---

## 19. Series Q — Scripts & Launchers

**Package:** `SpyderQ_Scripts` | **22 files** | **9,360 LOC**

The Q-Series contains all operational scripts: system launchers, validators, diagnostic utilities, production watchdog, GUI testing tools, CI gates, and AI fine-tuning scripts.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderQ01_FixExceptionHandling.py` | 485 | Scans the codebase for bare `except:` clauses and anti-patterns; reports and optionally fixes insecure exception handling. |
| `SpyderQ02_ValidateEnv.py` | 326 | Validates `.env` file: checks for all required variables, non-empty values, token format patterns, and environment mode consistency. |
| `SpyderQ03_ValidateConfiguration.py` | 443 | Validates all configuration keys, types, and required fields against the JSON Schema; reports missing or malformed entries. |
| `SpyderQ04_LaunchDashboard.py` | 520 | Dashboard launcher. Pre-warms API connections, validates broker connectivity, and opens the G05 trading dashboard. |
| `SpyderQ05_LaunchDashboardProactive.py` | 576 | Proactive dashboard launcher. Establishes all data feed subscriptions and agent connections before rendering the dashboard window. |
| `SpyderQ06_LaunchDashboardDirect.py` | 597 | Direct dashboard launcher. Bypasses the trading engine entirely for display-only mode; uses stub data providers when live data is unavailable. |
| `SpyderQ07_TestGUILogging.py` | 165 | GUI logging test script. Emits log messages at all severity levels (DEBUG → CRITICAL) to verify the G99 GUI log handler display. |
| `SpyderQ08_ValidatePackageExports.py` | 386 | Validates that all series `__init__.py` files export their documented public API members consistently. |
| `SpyderQ09_ValidateMissingExports.py` | 375 | Checks for production modules not referenced in any `__init__.py`; identifies orphaned or undiscoverable modules. |
| `SpyderQ10_ProtocolComplianceGate.py` | 61 | CI gate runner for the T129 protocol-compliance suite. Loads and executes the T129 unittest module; exits 0 on pass, 1 on failure, 2 on harness error. Intended as a pre-merge check: `python -m Spyder.SpyderQ_Scripts.SpyderQ10_ProtocolComplianceGate`. |
| `SpyderQ14_MainLauncher.py` | 499 | Main system launcher. Presents mode selection (live / paper / backtest) and bootstraps the appropriate engine and dashboard. |
| `SpyderQ24_ProductionWatchdog.py` | 339 | Production environment watchdog. Monitors system health, detects process crashes, and initiates configurable restart procedures. |
| `SpyderQ25_SystemMonitor.py` | 184 | Lightweight CLI system monitor. Prints real-time CPU, memory, and connection status to terminal for quick health checks. |
| `SpyderQ45_Diagnostics.py` | 261 | Diagnostics CLI. Runs I-Series DiagnosticsEngine and prints a structured snapshot of system health and module status. |
| `SpyderQ80_VerifyDashboardIntegration.py` | 476 | Dashboard integration verifier. Checks that all data bridge connections, widget subscriptions, and callback registrations are active and functional. |
| `SpyderQ90_SystemUtilities.py` | 884 | General system utility functions: process management, environment checks, log rotation, temporary file cleanup, and disk usage reporting. |
| `SpyderQ92_DiagnosticsUtilities.py` | 1,117 | Diagnostics CLI utilities. Provides snapshot, health-dump, module-status, and import-graph commands via argparse interface. |
| `SpyderQ93_RunPaper.py` | 427 | One-command paper trading launcher. Runs pre-flight sanity checks (env, config, broker connectivity) before starting the R02 paper engine. |
| `SpyderQ96_CollectFinetuneData.py` | 274 | Collects trade decision examples from the trade repository and formats them as supervised fine-tuning (SFT) examples for LLM training. |
| `SpyderQ98_FinetuneGemma4Spyder.py` | 335 | QLoRA fine-tuning script for Gemma 4 (4B e4b) on Spyder trade decision data. Uses PEFT adapters for efficient parameter update. |
| `SpyderQ99_ApplyPythonFormatting.py` | 326 | Applies `ruff` formatting and import sorting across the entire codebase; reports diff before applying. |
| `__init__.py` | 304 | Package init listing all Q-Series script entry points. |

---

## 20. Series R — Runtime Engines

**Package:** `SpyderR_Runtime` | **7 files** | **6,487 LOC**

The R-Series contains the execution engines for paper trading, live trading, and production deployment management. Each engine mode runs independently and shares the same strategy/risk interfaces. R04 API Panic Mode resets its counter on any successful broker round-trip (quote, account, chain, or fill).

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderR02_PaperEngine.py` | 818 | Paper trading engine. Simulates order execution against live Massive market data with realistic fill assumptions; tracks virtual P&L and positions. |
| `SpyderR03_PaperMonitor.py` | 851 | Paper session monitor. Tracks virtual P&L, position state, and strategy performance during paper trading; feeds G07 live dashboard. |
| `SpyderR04_LiveEngine.py` | 1,385 | Live trading engine. Routes validated strategy signals to B40 Tradier client, manages real order flow, confirmations, and error recovery. `CLOSE_POSITIONS_ON_EMERGENCY` defaults to `false` (opt-in); API Panic Mode counter resets on any successful broker round-trip. |
| `SpyderR06_PaperTradingHarness.py` | 1,006 | Paper trading harness for strategy validation. Provides a complete end-to-end test environment for strategy sign-off before live deployment. |
| `SpyderR07_LiveDashboard.py` | 542 | Lightweight live-trading terminal dashboard. Prints real-time P&L, position summary, and risk metrics to the console for headless deployments. |
| `SpyderR09_ProductionDeploymentManager.py` | 1,807 | Production deployment manager. Handles pre-flight health checks, rolling restarts, rollback procedures, and deployment monitoring hooks. |
| `__init__.py` | 81 | Package init exporting the paper and live engine classes. |

---

## 21. Series S — Signals

**Package:** `SpyderS_Signals` | **12 files** | **9,556 LOC**

The S-Series generates custom proprietary signals beyond standard technical analysis: dark pool indices, gamma/delta exposure, SKEW, Black Swan risk indicators, short squeeze detection, and macro economic data integration.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderS01_DIXCalculator.py` | 760 | DIX (Dark Index) calculation. Computes the ratio of dark pool volume to total volume as a proxy for institutional accumulation or distribution. Uses platform-aware `fcntl` file locking on POSIX with a clean no-op fallback on platforms without `fcntl`. |
| `SpyderS02_DIXScheduler.py` | 945 | DIX data collection scheduler. Manages update frequency, data caching, historical DIX storage, and alert emission on threshold crossings. |
| `SpyderS03_BlackSwanIndicator.py` | 727 | Black Swan Indicator. Multi-signal composite flagging extreme tail-risk conditions using VIX, SKEW, put/call ratios, and credit spreads. |
| `SpyderS04_BlackSwanScheduler.py` | 1,448 | Black Swan scheduler. Manages data polling cadence, cooling-off periods, and alert routing when the indicator reaches critical thresholds. |
| `SpyderS05_GEXDEXCalculator.py` | 546 | GEX/DEX (Gamma Exposure / Delta Exposure) calculator. Computes dealer net gamma and delta from SPY open interest for hedging flow analysis. |
| `SpyderS06_SKEWCalculator.py` | 1,423 | CBOE SKEW index replication from SPY options chain. Computes real-time SKEW, tracks historical percentiles, and signals tail-risk elevation. |
| `SpyderS07_CustomMetricsOrchestrator.py` | 1,149 | Orchestrates all custom metrics (DIX, GEX, SKEW, Black Swan) into a unified real-time signal feed consumed by strategies and risk modules. |
| `SpyderS08_ShortSqueezeDetector.py` | 1,330 | Short squeeze detector. Identifies rapid market spike patterns driven by short-covering dynamics using volume, price velocity, and short interest data. |
| `SpyderS09_FREDClient.py` | 314 | FRED (Federal Reserve Economic Data) API client. Fetches macro and yield curve data (Fed Funds rate, 2Y/10Y spread, CPI) for strategy conditioning. |
| `SpyderS10_SentimentScraper.py` | 413 | Weekly sentiment data scrapers. Collects AAII individual investor survey and NAAIM exposure index for contrarian positioning signals. |
| `SpyderS11_BarchartInternals.py` | 407 | Market breadth internals via Barchart API. Retrieves $TICK, $ADD, $TRIN, and $NYMO (McClellan Oscillator) for intraday market health signals. |
| `__init__.py` | 98 | Package init exporting the custom metrics orchestrator and all S-Series signal classes. |

---

## 22. Series T — Test Suite

**Package:** `SpyderT_Testing` | **122 files** | **94,020 LOC**

The T-Series is the complete pytest test suite covering all 24 production series. It includes unit tests, integration tests, system tests, scenario validators, protocol-compliance tests, and a full interactive test dashboard.

### Test Infrastructure

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderT01_UnitTestFramework.py` | 1,937 | Core test framework. Provides `SpyderTestBase`, fixtures, mock data providers, fake Tradier responses, and market data stubs. |
| `SpyderT09_TestDashboard.py` | 3,370 | Interactive manual QA dashboard for visual testing of all G-Series GUI components with live interaction. |
| `conftest.py` | 413 | Global pytest conftest. Registers fixtures, configures logging for tests, and defines shared test marks. |
| `__init__.py` | 367 | Package init. |

### Series Integration Tests (T100–T129 range)

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderT106_ACore.py` | 1,639 | Comprehensive A-Series (Core) integration test suite. |
| `SpyderT107_FSeries.py` | 1,528 | Comprehensive F-Series (Analysis) integration test suite. |
| `SpyderT108_NSeries.py` | 1,003 | Comprehensive N-Series (Options Analytics) integration test suite. |
| `SpyderT109_SSeries.py` | 666 | S-Series (Signals) integration test suite. |
| `SpyderT110_VSeries.py` | 904 | V-Series (Quant Models) integration test suite. |
| `SpyderT111_LSeries.py` | 1,481 | L-Series (ML) comprehensive integration test suite. |
| `SpyderT112_ESeries.py` | 1,382 | E-Series (Risk) comprehensive integration test suite. |
| `SpyderT113_BSeries.py` | 776 | B-Series (Broker) integration test suite. |
| `SpyderT114_DSeries.py` | 2,001 | D-Series (Strategies) comprehensive test suite — largest test file. |
| `SpyderT115_HSeries.py` | 350 | H-Series (Storage) test suite. |
| `SpyderT116_RSeries.py` | 328 | R-Series (Runtime) test suite. |
| `SpyderT117_PSeries.py` | 999 | P-Series (Portfolio) test suite. |
| `SpyderT118_YSeries.py` | 501 | Y-Series (Auto Agents) test suite. |
| `SpyderT119_CSeries.py` | 266 | C-Series (MarketData) test suite. |
| `SpyderT120_GSeries.py` | 136 | G-Series (GUI) test suite. |
| `SpyderT121_ISeries.py` | 228 | I-Series (Integration) test suite. |
| `SpyderT122_JSeries.py` | 233 | J-Series (Alerts) test suite. |
| `SpyderT123_KSeries.py` | 162 | K-Series (Reports) test suite. |
| `SpyderT124_MSeries.py` | 217 | M-Series (Monitoring) test suite. |
| `SpyderT125_OSeries.py` | 215 | O-Series (Trading Intelligence) test suite. |
| `SpyderT126_QSeries.py` | 159 | Q-Series (Scripts) test suite. |
| `SpyderT127_XSeries.py` | 208 | X-Series (Agents) test suite. |
| `SpyderT128_ZSeries.py` | 233 | Z-Series (Communication) test suite. |
| `SpyderT129_ProtocolCompliance.py` | 92 | Runtime protocol-compliance suite. Verifies E01 exposes `validate_signal()` and accepts `tradier_client`; F10 returns `None` from `calculate_all_indicators`; C04 `get_current_condition()` returns a valid `MarketCondition` member; and F00 `AnalyticsProviderProtocol` exports `calculate_all_indicators`. Executed by the Q10 CI gate. |

### Broker & Order Tests

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderT40_TradierClient_Test.py` | 428 | Tradier API client unit tests: auth, quote fetch, options chain, order submission, error handling. |
| `SpyderT42_Integration_Test.py` | 346 | Live integration tests requiring sandbox credentials (skipped in CI when credentials are invalid or unavailable). |
| `SpyderT43_OrderManager_Test.py` | 805 | Order manager tests: lifecycle state machine, partial fills, cancellations. |
| `SpyderT44_DatabentoClient_Test.py` | 305 | Massive client tests: data classes, connection state, stream lifecycle, and mock responses (legacy filename retained). |
| `SpyderT50_TradierOrderTests.py` | 795 | Extended Tradier order tests covering multi-leg options orders. |

### Risk & Strategy Tests

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderT46_RiskManager_Test.py` | 467 | Risk manager unit tests: position sizing, limit validation, circuit breaker triggers. |
| `SpyderT47_StrategyUnit_Test.py` | 468 | Strategy unit tests: signal generation and entry/exit logic for all D-Series strategies. |
| `SpyderT51_RiskManagerLimits_Test.py` | 701 | Extended risk limit tests: Greeks limits, drawdown caps, VaR threshold enforcement. |
| `SpyderT55_PaperTradingHarness_Test.py` | 749 | Paper trading harness tests: full end-to-end scenario validation. |
| `SpyderT56_StrategyTests.py` | 705 | Comprehensive strategy tests covering all D-Series implementations. |
| `SpyderT57_OptionsAnalyticsTests.py` | 574 | Options analytics tests: pricing accuracy, Greeks computation, IV surface construction. |
| `SpyderT58_RiskManagementTests.py` | 704 | Risk management scenario tests: VaR, drawdown, Greeks limit enforcement. |

### Utilities Coverage Tests (T59–T99 range)

This range covers comprehensive unit test coverage for all U-Series utilities, including date/time utilities, encryption, math functions, technical indicators, performance metrics, feature flags, rate limiters, circuit breakers, option strategy calculations, dependency analysis, and memory monitoring. Individual test files range from 707 to 1,561 LOC.

### Focused Unit Tests

| Module | LOC | Description |
|--------|----:|-------------|
| `test_c16_cache_consolidation.py` | 94 | Cache consolidation behaviour test for C16. |
| `test_e00_risk_protocol.py` | 137 | Protocol interface compliance test for E00. |
| `test_f00_analysis_protocol.py` | 135 | Protocol interface compliance test for F00. |
| `test_g32_agent_health_dashboard.py` | 77 | Agent health dashboard widget smoke test. |
| `test_j03_webhook_notifier.py` | 110 | Webhook notifier payload format tests. |
| `test_k13_strategy_pnl_ladder.py` | 131 | Strategy P&L ladder computation test. |
| `test_sharpe_comparison.py` | 294 | Sharpe ratio implementation consistency test across all computing modules. |
| `test_u46_secrets_manager.py` | 94 | Secrets manager test: env var, encrypted YAML, and Vault fallback paths. |
| `test_v09_iv_engine.py` | 180 | V09 canonical IV engine: BSM pricing and IV solver accuracy tests. |
| `test_z00_broker_protocol.py` | 151 | Z00 broker protocol interface compliance test. |

---

## 23. Series U — Utilities

**Package:** `SpyderU_Utilities` | **33 files** | **19,901 LOC**

The U-Series provides all shared infrastructure utilities used across every other series: logging, error handling, date/time, encryption, math, validation, constants, trading calendar, feature flags, technical indicators, resilience patterns, secrets management, and optional-dependency handling.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderU01_Logger.py` | 101 | `SpyderLogger` singleton. Thread-safe structured logging with rotating file handler, configurable levels, and JSON output mode. |
| `SpyderU02_ErrorHandler.py` | 899 | Centralised exception handler. Provides retry-with-backoff decorator, error categorisation, alerting hooks, and traceback sanitisation. |
| `SpyderU03_DateTimeUtils.py` | 1,841 | Comprehensive date/time utilities. Market hours detection, session classification (pre/regular/post), timezone conversion, and trading day arithmetic. |
| `SpyderU04_Encryption.py` | 230 | AES-256 encryption utilities. Protects sensitive data (API keys, tokens) at rest using Fernet symmetric encryption. |
| `SpyderU05_NetworkUtils.py` | 491 | Network utilities. Connection health checks, retry-with-backoff for HTTP calls, SSL certificate validation helpers, and timeout wrappers. |
| `SpyderU06_MathUtils.py` | 835 | Mathematical utilities. Rolling statistics, interpolation, normalisation, rounding for financial precision, and statistical test helpers. |
| `SpyderU07_Constants.py` | 756 | System-wide constants. Tick sizes, lot sizes, sector classification maps, API endpoint URLs, and default risk parameter values. |
| `SpyderU08_Validators.py` | 884 | Input validators. Symbol format, price range, quantity bounds, date format, and configuration value type validators. |
| `SpyderU09_DataTypes.py` | 708 | Custom typed dataclasses: `Quote`, `Trade`, `Greeks`, `Position`, `Signal`, `Fill` with validation and serialisation methods. |
| `SpyderU10_TradingCalendar.py` | 893 | NYSE trading calendar. Full holiday schedule, session open/close times, early-close detection, and next/previous trading day calculation. |
| `SpyderU11_FeatureFlags.py` | 724 | Feature flag system. Enables/disables named features at runtime without code deployment; supports percentage rollout and environment gating. |
| `SpyderU12_AgentIntegration.py` | 428 | Thin bridge utility layer. Provides helper functions for X-Series and Y-Series agent calls via the I06 agent message bus. |
| `SpyderU13_TechnicalIndicators.py` | 782 | Extended technical indicator library (complements F01). Includes Chaikin Money Flow, MFI, DPO, TRIX, and Ulcer Index. |
| `SpyderU14_OptionStrategies.py` | 833 | Options strategy utility functions. Payoff diagrams, breakeven calculation, max profit/loss, and theoretical edge estimation for standard structures. |
| `SpyderU15_PerformanceMetrics.py` | 794 | Performance metric computation. CAGR, annualised Sharpe, Sortino, Calmar, max drawdown, and win/loss streak statistics. |
| `SpyderU16_TechnicalAnalysis.py` | 690 | Technical analysis utilities. Pattern recognition helpers, pivot high/low detection, and divergence detection for RSI and MACD. |
| `SpyderU17_LLMUtils.py` | 91 | Shared LLM utilities. Ollama client wrapper, prompt templating, and response parsing helpers shared across X-Series and Y-Series agents. |
| `SpyderU18_DependencyAnalyzer.py` | 749 | Module dependency analyser. Builds the full import graph, detects circular dependencies, and reports coupling metrics. |
| `SpyderU19_InteractionMatrix.py` | 923 | Module interaction matrix. Tracks and visualises inter-module call patterns; used for architecture review and refactoring planning. |
| `SpyderU20_InstitutionalLibraries.py` | 916 | Wrappers for institutional quantitative libraries. Provides consistent interfaces for QuantLib, scipy.stats, and statsmodels functions. |
| `SpyderU22_ETTimeDisplay.py` | 146 | Eastern Time display utilities. Formatted ET timestamps for GUI widgets and log output with DST-aware formatting. |
| `SpyderU23_MemoryMonitor.py` | 644 | Process memory monitor. Tracks heap usage over time, detects memory leaks via growth trending, and triggers GC when threshold exceeded. |
| `SpyderU24_StyleManager.py` | 716 | UI style manager. Manages dark/light theme tokens, colour palettes, font definitions, and dynamic style sheet generation for PySide6. |
| `SpyderU27_SystemOptimizer.py` | 465 | System performance optimiser. Sets CPU affinity for trading threads, configures thread-pool sizes, and schedules GC to avoid trading-hour pauses. |
| `SpyderU40_RateLimiter.py` | 349 | Token-bucket rate limiter. Controls API call throughput for all external services with per-endpoint bucket configuration. |
| `SpyderU41_CircuitBreaker.py` | 381 | Utility-layer circuit breaker. Implements open/half-open/closed state machine for non-trading code paths (API calls, data feeds). |
| `SpyderU42_StrategyCircuitBreaker.py` | 673 | Strategy-specific circuit breaker. Halts individual strategies on consecutive loss streaks or Greeks limit violations without affecting the rest. |
| `SpyderU43_CorrelationLogger.py` | 479 | Correlation logger. Records pairwise position correlation matrices at configurable intervals for historical concentration analysis. |
| `SpyderU44_ShutdownCoordinator.py` | 181 | Graceful shutdown coordinator. Ensures all subsystems flush state, close connections, and save checkpoints before process exit. |
| `SpyderU45_RetryWithBackoff.py` | 296 | Configurable retry-with-exponential-backoff decorator. Supports jitter, max-retries, exception filtering, and per-attempt timeout. |
| `SpyderU46_SecretsManager.py` | 380 | Unified secrets management. Reads from environment variables, encrypted YAML files, or HashiCorp Vault with transparent fallback chain. |
| `SpyderU47_OptionalImport.py` | 131 | Canonical helper for optional imports. Provides `optional_import(name, *, purpose, required_on)` returning an `OptionalImport` wrapper that is truthy on success, raises a loud `ImportError` on attribute access when missing, and re-raises unconditionally when the current platform is in `required_on`. Includes `warn_once()` for graceful-degradation logging. |
| `__init__.py` | 492 | Package init exporting all utility classes with lazy loading for heavy dependencies. |

---

## 24. Series V — Quantitative Models

**Package:** `SpyderV_QuantModels` | **10 files** | **11,228 LOC**

The V-Series contains the quantitative finance model layer: advanced pricing models (Heston, SABR, local-vol, jump-diffusion), GARCH/HAR-RV volatility models, quant-layer risk analysis, and the canonical synchronous IV engine.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderV01_QuantEngine.py` | 932 | Core quantitative engine. Coordinates all V-Series model execution, manages model state, and routes pricing/vol requests to appropriate sub-models. |
| `SpyderV02_ModelManager.py` | 1,046 | Quant model lifecycle manager. Handles model registration, parameter storage, calibration scheduling, and performance tracking. Contains a legacy internal `MarketRegimeDetector` class; the canonical regime signal is supplied by `SpyderL09_UnifiedRegimeEngine`. |
| `SpyderV03_DataInterface.py` | 663 | Data interface for quant models. Fetches and transforms clean market data (rates, spots, vols) into the format required by calibration routines. |
| `SpyderV04_RiskManager.py` | 1,344 | Quant-layer risk manager. Computes analytic scenario Greeks, runs instantaneous shock analysis, and provides stress-test results to E-Series. |
| `SpyderV05_PricingEngine.py` | 1,545 | Advanced pricing engine. Implements Heston stochastic volatility, SABR, local-volatility (Dupire), and Merton jump-diffusion models. |
| `SpyderV06_VolatilityEngine.py` | 1,729 | Quantitative volatility engine. Implements GARCH(1,1), EGARCH, GJR-GARCH, HAR-Realised Volatility, and MIDAS-RV models. |
| `SpyderV07_AdvancedModels.py` | 1,303 | Advanced stochastic models. Covers affine jump-diffusion (Bates), rough volatility (rBergomi via Mandelbrot-van Ness kernel), and Variance Gamma models. |
| `SpyderV08_AIModels.py` | 1,204 | AI-enhanced quant models. Neural network options pricing (feedforward MLP correction to BSM) and vol surface prediction via transformer architecture. |
| `SpyderV09_IVEngine.py` | 973 | **Canonical IV engine.** Synchronous BSM pricing, IV solver (Newton-Raphson with bisection fallback), and full Greeks computation. Designated single source of truth for IV calculations across the system; wraps all pricer access behind a consistent interface. |
| `__init__.py` | 489 | Package init exporting all V-Series model classes with calibration utilities. |

---

## 25. Series X — On-Demand AI Agents

**Package:** `SpyderX_Agents` | **17 files** | **18,645 LOC**

The X-Series contains 16 stateless, on-demand AI agents powered by Ollama local LLMs. Each agent is invoked by the system or operator for a specific analytical task, processes context, and returns a structured response.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderX01_GreeksAgent.py` | 2,383 | Analyses the current portfolio's Greeks exposure. Identifies imbalances, recommends hedges or adjustments, and explains risks in natural language. |
| `SpyderX02_FlowAgent.py` | 1,307 | Interprets order flow and dark pool data. Classifies institutional vs. retail activity and identifies directional bias from flow patterns. |
| `SpyderX03_StrategyDirectorAgent.py` | 1,029 | Recommends strategy selection based on current regime, IV rank, put/call skew, and remaining risk budget. |
| `SpyderX04_RiskGuardianAgent.py` | 834 | Reviews risk metrics in natural language. Alerts on limit utilisation, drawdown trajectory, and suggests defensive actions. |
| `SpyderX05_MLResearchAgent.py` | 1,478 | Proposes and evaluates ML model improvements based on recent prediction accuracy, feature drift, and backtested alpha decay. |
| `SpyderX06_BacktestingAgent.py` | 784 | Runs targeted backtests on strategy parameter variants and summarises results with statistical significance tests. |
| `SpyderX07_ExecutionStrategyAgent.py` | 957 | Optimises order execution: recommends timing, limit vs. market order, legging strategy, and venue for each multi-leg structure. |
| `SpyderX08_PerformanceAnalyticsAgent.py` | 507 | AI-enhanced performance analytics and P&L attribution. Explains performance drivers and identifies behavioural patterns. |
| `SpyderX09_AlertManagerAgent.py` | 1,178 | Reviews and triages incoming alerts. Suppresses known-false-positive noise and escalates genuine risk issues to the operator. |
| `SpyderX10_QuantModelsAgent.py` | 1,531 | Queries V-Series quantitative models for analytical insight and advises on model calibration, surface anomalies, and parameter updates. |
| `SpyderX11_SentimentAnalysisAgent.py` | 1,464 | Synthesises news, social, and options-flow sentiment into a directional bias score with confidence interval and key driver explanation. |
| `SpyderX12_SystemHealthAgent.py` | 1,233 | Diagnoses system health issues (latency spikes, memory growth, connection drops) and recommends remediation actions. |
| `SpyderX13_MarketAnalysisAgent.py` | 885 | Provides natural-language market analysis: macro context, regime characterisation, and inter-market relationship commentary. |
| `SpyderX14_OrchestratorAgent.py` | 1,104 | Multi-agent workflow coordinator. Delegates sub-tasks to specialist X-Series agents, aggregates responses, and synthesises a unified recommendation. |
| `SpyderX15_StrategyGeneratorAgent.py` | 468 | Generates novel strategy ideas via LLM reasoning over current market context, regime, and historical performance patterns. |
| `SpyderX16_MetaCoordinator.py` | 1,200 | Meta-coordinator. Monitors all X-Series agents, arbitrates conflicting signals from multiple agents, and assigns agent priority. |
| `__init__.py` | 303 | Package init exporting all X-Series agent classes. |

---

## 26. Series Y — Autonomous Agents

**Package:** `SpyderY_AutoAgents` | **13 files** | **6,944 LOC**

The Y-Series contains 10 persistent autonomous agents that run continuously (24/7), each with its own event loop, heartbeat, and state management. They communicate via I06 AgentMessageBus. A pluggable inference backend module (`SpyderY_InferenceBackends`) supports Ollama and other LLM providers.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderY00_BaseAutoAgent.py` | 793 | Abstract base class for all autonomous agents. Implements event loop, heartbeat monitoring, error recovery, state persistence, and graceful shutdown hooks. |
| `SpyderY01_MarketSenseAgent.py` | 524 | Continuously monitors market conditions. Emits typed regime-change and anomaly events when the detected market state shifts. |
| `SpyderY02_StrategyPilotAgent.py` | 507 | Autonomously activates and deactivates strategies based on real-time regime signals from Y01 and D30 RegimeGatedSelector. |
| `SpyderY03_RiskSentinelAgent.py` | 624 | 24/7 risk sentinel. Watches for position limit breaches, drawdown threshold crossings, and VaR exceedances; triggers E16 circuit breakers. |
| `SpyderY04_AlphaLearnerAgent.py` | 546 | Continuously learns from recent trades. Updates alpha decay scores for each strategy and adjusts L-Series model feature weights. |
| `SpyderY05_ExecutionOptimizerAgent.py` | 558 | Optimises order execution quality in real time: recommends timing windows, order type selection, and venue routing adjustments. |
| `SpyderY06_NewsSentinelAgent.py` | 553 | Monitors news and macro data feeds continuously. Flags market-moving events and forwards high-priority alerts to J01 and E-Series. |
| `SpyderY07_TradeJournalAgent.py` | 540 | Autonomous trade journaling. Records entry rationale, market context, exit outcome, and lessons-learned tags to H08 TradeJournal. |
| `SpyderY08_MetaOrchestratorAgent.py` | 653 | Meta-orchestrator for the Y-Series. Monitors agent liveness, restarts failed agents, and manages inter-agent message priority. |
| `SpyderY09_CodeReviewerAgent.py` | 463 | Reviews newly generated or modified code for coding standards, security issues, and logical correctness using the LLM CODE model role. |
| `SpyderY10_AgentScheduler.py` | 426 | Schedules Y-Series agent tasks. Manages periodic execution, market-hours gating, and task priority queuing. |
| `SpyderY_InferenceBackends.py` | 419 | Pluggable LLM inference backend registry. Supports Ollama (primary), stub backends for testing, and extensible interface for future providers. |
| `__init__.py` | 338 | Package init exporting the base agent and all Y-Series agent classes. |

---

## 27. Series Z — Communication & IPC

**Package:** `SpyderZ_Communication` | **9 files** | **8,407 LOC**

The Z-Series handles all inter-process communication: ZeroMQ messaging (PUB/SUB, REQ/REP), message protocol definitions, cross-process trading coordination, distributed volatility computation, order routing, automated delta hedging, and multi-process lifecycle management.

| Module | LOC | Description |
|--------|----:|-------------|
| `SpyderZ00_BrokerProtocol.py` | 282 | Typed Protocol interfaces defining the B-Series ↔ Z-Series series boundary for order routing and execution confirmation. |
| `SpyderZ01_ZeroMQIntegration.py` | 1,264 | ZeroMQ (0MQ) integration layer. Implements PUB/SUB for market data broadcast and REQ/REP for order execution across processes. |
| `SpyderZ02_MessageProtocol.py` | 1,035 | Message protocol definitions. Schemas, serialisation (msgpack/JSON), versioning, and validation for all Z-Series message types. |
| `SpyderZ03_TradingCoordinator.py` | 1,491 | Cross-process trading decision coordinator. Routes strategy signals to the appropriate execution process via the ZeroMQ backbone. |
| `SpyderZ04_VolatilityEngine.py` | 802 | Distributed volatility computation engine. Offloads heavy IV recalculation jobs to worker processes and collects results via ZeroMQ. |
| `SpyderZ05_OrderRouter.py` | 1,216 | Cross-process order router. Fans out order submission requests to the broker process with deduplication and sequence numbering. |
| `SpyderZ06_AutoHedger.py` | 1,210 | Automated delta hedger running as a separate supervised process. Continuously calculates net portfolio delta and submits hedging orders. |
| `SpyderZ07_MultiProcessManager.py` | 1,003 | Multi-process manager. Spawns, monitors, and restarts Z-Series worker processes; handles IPC setup and teardown. |
| `__init__.py` | 104 | Package init exporting the ZeroMQ integration, coordinator, and auto-hedger. |

---

*End of Spyder Codebase Review v17 (v4) — April 14, 2026*
