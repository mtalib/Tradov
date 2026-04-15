# Spyder Trading System — Codebase Review
**Date:** April 1, 2026
**Scope:** Full codebase module-by-module analysis, LOC inventory, status assessment, anomalies, and improvement opportunities
**Prepared by:** Claude Code (claude-sonnet-4-6)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Inventory](#2-system-inventory)
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
14. [Series L — Machine Learning & AI](#14-series-l--machine-learning--ai)
15. [Series M — Monitoring](#15-series-m--monitoring)
16. [Series N — Options Analytics](#16-series-n--options-analytics)
17. [Series O — Trading Intelligence](#17-series-o--trading-intelligence)
18. [Series P — Portfolio Management](#18-series-p--portfolio-management)
19. [Series Q — Scripts & Launchers](#19-series-q--scripts--launchers)
20. [Series R — Runtime Engines](#20-series-r--runtime-engines)
21. [Series S — Signals & Indicators](#21-series-s--signals--indicators)
22. [Series T — Testing](#22-series-t--testing)
23. [Series U — Utilities](#23-series-u--utilities)
24. [Series V — Quantitative Models](#24-series-v--quantitative-models)
25. [Series X — AI Agents (On-Demand)](#25-series-x--ai-agents-on-demand)
26. [Series Y — Autonomous Agents (Daemon)](#26-series-y--autonomous-agents-daemon)
27. [Series Z — Communication & IPC](#27-series-z--communication--ipc)
28. [Anomalies & Deficiencies](#28-anomalies--deficiencies)
29. [Opportunities for Improvement](#29-opportunities-for-improvement)

---

## 1. Executive Summary

Spyder is a production-grade autonomous options trading system spanning **25 series (A–Z)**, **441 total files**, and **418,153 total lines of code** — of which approximately **327,074 lines** are production code and **91,079 lines** are tests. The system targets SPY options trading via the Tradier brokerage API and Massive (formerly Polygon.io) market data.

**Since the February 25, 2026 review, the following major changes have occurred:**

- **Provider migration complete:** Databento (C26) deprecated in favour of the Massive SDK (C27/C28). C26 retained for rollback only.
- **Consolidation push:** Regime detection unified to L09. Multi-leg strategy coordination centralised to D32. Performance attribution consolidated to F17. Risk calculations consolidated to V04/V05.
- **New series added:** SpyderO (Trading Intelligence), SpyderY (Autonomous Daemon Agents), SpyderQ (Scripts), SpyderR (Runtime Engines) have expanded significantly.
- **Test suite expansion:** SpyderT grew from ~10 files to **101 test files** covering all series.
- **New resilience utilities:** U42 (StrategyCircuitBreaker), U43 (CorrelationLogger), U44 (ShutdownCoordinator), U45 (RetryWithBackoff) added.

**Remaining concerns:**
1. Several deprecated modules retained without clear deletion schedule (C07, C14, C21, G07, G08, G10, R05).
2. Legacy broker references (IB/ConnectAPI/B10) still appear in stale code paths.
3. Numbering gaps across multiple series indicate iterative development without renumbering.
4. SpyderB30 still imports the removed `SpyderB10_IBDataTypes`.
5. SpyderP06 has a broken import on line 55.

---

## 2. System Inventory

### Series Summary

| Series | Name | Files | LOC | Status |
|--------|------|------:|----:|--------|
| A | Core Infrastructure | 7 | 9,324 | ✅ Solid |
| B | Broker Integration | 7 | 9,839 | ⚠️ B30 stale import |
| C | Market Data | 29 | 33,916 | ⚠️ Provider migration; 3 deprecated |
| D | Strategies | 29 | 34,730 | ✅ Comprehensive |
| E | Risk Management | 23 | 27,601 | ✅ Strong |
| F | Analysis & Analytics | 21 | 23,922 | ✅ Best-in-class |
| G | GUI & Dashboard | 21 | 18,613 | ⚠️ 3 deprecated; Plotly renumbering gap |
| H | Storage & Persistence | 6 | 4,894 | ✅ Solid |
| I | Integration & Diagnostics | 11 | 8,633 | ✅ Solid |
| J | Alerts & Notifications | 4 | 3,291 | ⚠️ J03 missing |
| K | Reports | 12 | 12,720 | ✅ Comprehensive |
| L | Machine Learning | 14 | 17,705 | ✅ Strong; L09 now present |
| M | Monitoring | 6 | 6,175 | ✅ Solid |
| N | Options Analytics | 13 | 15,864 | ✅ Complete |
| O | Trading Intelligence | 3 | 4,504 | ✅ New, solid |
| P | Portfolio Management | 7 | 10,050 | ⚠️ P06 broken import |
| Q | Scripts & Launchers | 12 | 6,306 | ⚠️ Irregular naming |
| R | Runtime Engines | 10 | 9,271 | ⚠️ R05 stub/deprecated |
| S | Signals & Indicators | 8 | 7,139 | ✅ Good |
| T | Testing | 101 | 91,079 | ✅ Extensive |
| U | Utilities | 29 | 18,390 | ✅ Foundational |
| V | Quantitative Models | 8 | 9,770 | ✅ Consolidated |
| X | AI Agents (on-demand) | 16 | 19,513 | ⚠️ X14/X16 tight coupling |
| Y | Autonomous Agents | 11 | 6,097 | ✅ New, solid |
| Z | Communication & IPC | 7 | 9,214 | ✅ Solid |
| **TOTAL** | | **441** | **418,153** | |

### LOC Breakdown

| Category | LOC | % of Total |
|----------|----:|----------:|
| Production code (excl. testing) | 327,074 | 78.2% |
| Test code (SpyderT) | 91,079 | 21.8% |
| **Grand Total** | **418,153** | **100%** |

---

## 3. Series A — Core Infrastructure

**7 files · 9,324 LOC · Status: ✅ Solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| A01 | 870 | `Main` | Application entry point, asyncio event loop (uvloop), Qt GUI initialisation, startup race-condition fixes |
| A02 | 1,817 | `TradingEngine` | Core trading orchestration: strategy lifecycle, order execution, position tracking, risk integration, automated error recovery |
| A03 | 1,336 | `ConfigManager` | YAML/TOML/JSON configuration with Fernet encryption, file watching, schema validation, multi-source merging |
| A04 | 1,523 | `SchedulerManager` | APScheduler-based job scheduling with market calendar awareness, holiday handling, state persistence |
| A05 | 1,180 | `EventManager` | Centralised async pub/sub event bus with priority queues, persistence, filtering, and metrics |
| A06 | 1,366 | `MasterController` | System lifecycle orchestration: initialisation, shutdown, health monitoring, resource limits |
| A08 | 1,232 | `FSeriesOrchestrator` | Coordinates F12–F16 analytics modules with resource allocation, priority management, and conflict prevention |

**Numbering gap:** A07 is absent. No documentation of its removal found.

**Key dependencies:** `uvloop`, `apscheduler`, `watchdog`, `jsonschema`, `cryptography`, `PySide6` (optional).

---

## 4. Series B — Broker Integration

**7 files · 9,839 LOC · Status: ⚠️ B30 stale import**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| B00 | 827 | `OrderRequest`, `OrderAction`, `OrderType` | Canonical order data structures, order types, multi-leg strategy payloads, serialisation |
| B02 | 1,664 | `OrderManager` | Order state tracking, SSE-stream fill processing, persistence; delegates execution to B40 |
| B03 | 351 | `PositionTracker` | Real-time position tracking, P&L calculation, Greeks monitoring; threading stubs present |
| B04 | 1,343 | `AccountManager` | Account balance, margin, buying power, risk alerts, PDT and margin-call circuit breakers |
| B15 | 1,422 | `PrometheusMetrics` | Prometheus HTTP metrics endpoint for trading performance, health, and risk metrics |
| B30 | 1,006 | `SPYOptionsChainManager` | SPY options chain management: dynamic strike selection, 0DTE/1DTE/weekly/monthly expirations |
| B40 | 3,226 | `TradierClient` | Production Tradier REST+SSE client: bearer auth, order execution, multileg, option chains with Greeks, rate limiting, circuit breaker |

**Numbering gaps:** B01, B05–B14, B16–B29, B31–B39 absent. Most were legacy broker (IB/IBKR) modules removed during the Tradier migration.

**Critical issue in B30:** Imports `SpyderB10_IBDataTypes` which was removed during the IBKR migration. Module will fail at import if that path is on `sys.path`.

---

## 5. Series C — Market Data

**29 files · 33,916 LOC · Status: ⚠️ Provider transition; 3 deprecated modules**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| C00 | 900 | `NormalizedQuote`, `NormalizedTrade`, Protocol ABCs | Provider-agnostic structural Protocols and canonical data types; enables pluggable provider swapping |
| C01 | 1,550 | `DataFeed` | Central data orchestrator: providers → cache → subscribers → EventManager; Databento/Massive providers wired in |
| C02 | 938 | `HistoricalDataManager` | Historical data retrieval and storage (Databento/Massive-compatible), caching, preprocessing |
| C03 | 1,083 | `OptionChain` | Options chain data from Tradier, Greeks calculations, strike selection utilities |
| C04 | 942 | `MarketInternals` | $TICK, $ADD, VIX, SKEW breadth calculations and trend detection |
| C05 | 892 | `VolumeProfile` | Volume profile construction, VWAP, point-of-control, institutional flow detection |
| C06 | 1,216 | `DataValidator` | Real-time data validation: z-score, isolation forest, outlier detection, data quality assurance |
| C07 | 1,420 | `OPRAFeed` | **DEPRECATED** — Legacy OPRA options feed; replaced by C27 (Massive). Retained for reference only |
| C08 | 876 | `SPYFeed` | SPY-specific data feed with VWAP, stub implementations for low-dependency operation |
| C09 | 1,034 | `NewsManager` | RSS feed aggregation with TextBlob/VADER sentiment analysis for trading signals |
| C10 | 1,499 | `VIXAnalyzer` | VIX historical data, technical indicators (SMA, EMA, Bollinger), volatility regime detection |
| C11 | 1,361 | `FuturesBasis` | ES/SPY futures basis calculation, contract specifications, calendar spreads |
| C12 | 769 | `DarkPoolFlow` | Dark pool flow analysis, DIX/GEX correlation, institutional block trade detection |
| C13 | 1,022 | `IndexComponents` | S&P 500 component tracking, breadth calculations, sector rotation analysis |
| C14 | 789 | `UltraLowLatencyFeed` | **DEPRECATED** — HFT sub-5ms feed; over-engineering for current needs. Use C27 instead |
| C15 | 1,285 | `MicrostructureAnalyzer` | Order flow microstructure: sweeps, imbalances, quote stuffing, hidden liquidity detection |
| C16 | 914 | `MarketDataCache` | Multi-tier cache (memory → Redis → SQLite) for streaming data with EventManager integration |
| C17 | 1,081 | `MarketConfigManager` | Market configuration with YAML/TOML schema validation and file watching |
| C18 | 1,286 | `SKEWCalculator` | CBOE SKEW index calculation from option chains using CBOE methodology |
| C19 | 813 | `AfterHoursDataManager` | After-hours data handling, closing snapshots, market closure price management |
| C21 | 669 | `MarketDataFeed` | **DEPRECATED** — Legacy ConnectAPI feed abstraction. ConnectAPI removed; references stale |
| C22 | 1,274 | `FactorDataProvider` | Factor data (yfinance, FRED) for macro-economic indicator retrieval |
| C23 | 1,221 | `RealTimeDataOptimizer` | Real-time optimisation with Numba JIT, memory-mapped I/O, multiprocessing |
| C24 | 1,518 | `ModelDataPipeline` | ML data pipeline: feature engineering, sklearn/polars transforms, MLflow integration |
| C26 | 1,549 | `DatabentoClient` | **DEPRECATED (2026-03-18)** — Databento OPRA client; replaced by C27. Retained for rollback |
| C27 | 1,593 | `MassiveClient` | **Current primary provider** — Massive REST+WebSocket client for SPY equity/options with Greeks |
| C28 | 1,193 | `MassiveHistoricalDownloader` | Bulk historical SPY options/equity downloader from Massive REST API with Parquet/checkpoint resume |
| C30 | 1,783 | `OrderFlowAnalyzer` | Institutional order flow: GEX, UOA, dark pools, Put/Call ratio, max pain |
| C35 | 1,446 | `SentimentAnalyzer` | Multi-source sentiment: FinBERT NLP, social media, SEC filings |

**Numbering gaps:** C20, C25, C29, C31–C34 absent.

---

## 6. Series D — Strategies

**29 files · 34,730 LOC · Status: ✅ Comprehensive**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| D00 | 330 | *(constants)* | Centralised strategy parameters: risk limits, position sizing, entry/exit thresholds |
| D01 | 1,063 | `BaseStrategy` (ABC) | Abstract base defining strategy lifecycle, signal generation, position management |
| D02 | 859 | `IronCondor` | Iron Condor: entry/exit logic, strike selection; multi-leg execution delegated to D32 |
| D03 | 1,008 | `CreditSpread` | Bull/bear credit spreads with strike selection, profit targets, stop loss |
| D04 | 1,070 | `ZeroDTE` | Same-day expiration strategy with market-open entry timing and LEAN-based parameters |
| D05 | 1,117 | `Straddle` | ATM straddle with IV rank filtering and expected move calculations |
| D08 | 1,159 | `OpeningRangeBreakout` | 15/30-minute range breakout with volume profile analysis |
| D09 | 1,454 | `GreeksBasedStrategy` | Position sizing and entry based on real-time Greeks exposure targets |
| D10 | 851 | `IronButterfly` | Iron Butterfly: ATM-focused; multi-leg execution delegated to D32 |
| D11 | 1,285 | `SpecializedZeroDTE` | Enhanced 0DTE with volatility/regime analysis via F04 and F10 |
| D12 | 1,019 | `RSIMeanReversion` | RSI oversold/overbought mean reversion with options overlays |
| D13 | 931 | `MACrossover` | MA crossover strategy with options-based position expression |
| D14 | 1,205 | `CalendarSpread` | Calendar spread: time decay capitalisation with expiration roll logic |
| D15 | 1,381 | `StraddleStrangle` | Straddle/strangle composite with dynamic width selection |
| D16 | 1,457 | `RatioSpreads` | Ratio spread strategies (call/put) with back-ratio variants |
| D17 | 1,359 | `DiagonalSpread` | Diagonal spread: combined calendar + vertical with strike selection |
| D18 | 1,531 | `EvolvedCreditSpread` | Adaptive credit spread evolved from D03 with ML-driven parameter tuning |
| D19 | 1,205 | `JadeLizard` | Jade Lizard (short put + call spread) with upside cap and premium target |
| D20 | 841 | `VerticalSpreadOptimizer` | Spread width and strike optimiser across delta targets |
| D21 | 1,402 | `DoubleCalendar` | Double calendar spread across two expirations |
| D22 | 1,109 | `AdaptiveVolatility` | Volatility-adaptive strategy selection switching between premium-selling and hedging |
| D25 | 1,454 | `UnifiedCreditSpreadEngine` | Unified engine consolidating D03/D18 spread logic with shared parameter set |
| D26 | 1,132 | `GammaScalper` | Gamma scalping with delta-neutral maintenance and rebalancing triggers |
| D27 | 1,260 | `EarningsStrategy` | Earnings event-driven options strategies with IV crush timing |
| D28 | 1,069 | `VIXHedging` | VIX-based tail hedge strategies; activates during elevated volatility regimes |
| D30 | 1,308 | `RegimeGatedSelector` | Regime-gated strategy selection using market regime detection |
| D31 | 2,055 | `StrategyOrchestrator` | Master coordination: dynamic allocation, regime detection, PySide6 dashboard integration |
| D32 | 2,074 | `MultiLegStrategyCoordinator` | Consolidated multi-leg execution (Iron Condor, Butterfly, Jade Lizard) with unified leg construction and Greeks management |
| D33 | 742 | `RenaissanceMeanReversion` | Renaissance-style statistical mean reversion with z-score entry/exit |

**Numbering gaps:** D06, D07, D23, D24, D29 absent.

---

## 7. Series E — Risk Management

**23 files · 27,601 LOC · Status: ✅ Strong**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| E01 | 926 | `RiskManager` | Core risk monitoring, position exposure, enforcement; legacy broker references removed |
| E02 | 1,019 | `PositionSizer` | Kelly criterion, fractional Kelly, risk-adjusted position sizing |
| E03 | 1,449 | `StopLossManager` | Stop loss management: trailing stops, emergency triggers, position closing |
| E04 | 903 | `DrawdownControl` | Tiered drawdown thresholds: warning → caution → critical → emergency |
| E05 | 768 | `AutomaticRebalancer` | Portfolio rebalancing: delta hedge, gamma scalp, vega hedge, theta roll, emergency modes |
| E06 | 1,162 | `RiskMetrics` | Portfolio metrics: Sharpe, Sortino, max drawdown, VaR, CVaR, information ratio |
| E07 | 702 | `ProbabilisticSharpeRatio` | PSR, deflated Sharpe, bootstrap confidence intervals |
| E08 | 1,146 | `PositionGroupValidator` | Multi-leg position validation: Greeks bounds checking, correlation analysis |
| E09 | 1,057 | `VolatilityRiskManager` | VIX-based risk adjustment, volatility regime monitoring |
| E10 | 1,939 | `CorrelationRiskManager` | Portfolio correlation analysis, diversification monitoring, tail correlation detection |
| E11 | 937 | `MaxLossProtection` | Multi-timeframe loss limits (daily/weekly/monthly/yearly) with auto-suspension |
| E12 | 1,432 | `PortfolioVaR` | Portfolio Value-at-Risk: historical, parametric, Monte Carlo methodologies |
| E13 | 2,229 | `DayProfitTarget` | Intraday profit target management with partial close, lock-in, and trailing logic |
| E14 | 715 | `KellyPositionSizer` | Full/half/quarter Kelly position sizing with confidence-scaled allocation |
| E15 | 1,126 | `GreekLimitsManager` | Real-time Greeks limits enforcement across delta, gamma, theta, vega at portfolio level |
| E16 | 477 | `CircuitBreakerProtocol` | Strategy-level circuit breaker with loss-streak and error-rate triggers |
| E17 | 1,534 | `RealTimeStressTesting` | Scenario-based stress testing: VIX spike, flash crash, interest rate shock |
| E18 | 1,369 | `FSeriesRiskIntegrator` | Bridge between E-series risk modules and F-series analytics |
| E19 | 1,165 | `UnifiedRiskCoordinator` | Central risk coordinator eliminating E-series overlap; delegates to V04 and X04 |
| E20 | 1,625 | `FrustrationAnalyzer` | Detects adverse market regimes causing systematic strategy underperformance |
| E21 | 1,041 | `HMMRegimeDetector` | Hidden Markov Model regime detection for 3-state market classification |
| E22 | 832 | `KernelRegression` | Kernel regression for non-parametric P&L and Greeks surface estimation |
| E23 | 2,048 | `PortfolioOptimizer` | Mean-variance, Black-Litterman, risk parity portfolio optimisation |

---

## 8. Series F — Analysis & Analytics

**21 files · 23,922 LOC · Status: ✅ Best-in-class**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| F01 | 857 | `TrendDirection`, `MarketRegime` | Technical indicator library with enum-based trend and market regime classification |
| F02 | 872 | `PatternType` | Price action pattern recognition: candlestick patterns, doji, hammer, engulfing, morning star |
| F03 | 791 | `LevelType`, `LevelStrength` | Support/resistance detection via DBSCAN clustering, volume analysis, psychological levels |
| F04 | 922 | *(constants)* | Core volatility calculations: ARCH/GARCH models, volatility regime classification (LOW/NORMAL/HIGH/EXTREME) |
| F05 | 772 | `TrendDirection`, `TrendPhase` | Multi-method trend detection: regression, MA crossovers, phase identification |
| F06 | 987 | `PricingModel`, `OptionStyle` | Complete Greeks engine (delta, gamma, vega, theta, rho) via Black-Scholes/Binomial; Numba JIT + cachetools |
| F07 | 758 | `GapType`, `GapDirection` | Gap detection and classification: breakaway, runaway, exhaustion, overnight |
| F08 | 1,001 | `VolatilityRegime`, `RegimeStrength` | Volatility regime classification via Gaussian Mixture Models with sliding window |
| F09 | 1,287 | `FilterResult`, `EntryQuality` | Multi-filter entry validation: comprehensive quality scoring for entry signal gating |
| F10 | 1,486 | *(thresholds)* | Market regime detection: VIX, GARCH, trend analysis; optional `ruptures` for change-point detection |
| F11 | 1,046 | `GreeksValidationLevel` | Portfolio Greeks aggregation: Redis caching, TTL caching, thread-safe real-time monitoring |
| F12 | 2,033 | *(constants)* | Institutional-grade backtesting: Monte Carlo, walk-forward optimisation, scenario analysis |
| F13 | 1,458 | *(thresholds)* | AI/ML model validation: drift detection, accuracy tracking, ensemble management, A/B testing |
| F14 | 1,546 | *(constants)* | Tick-by-tick microstructure analysis, order flow dynamics, market depth, institutional patterns |
| F16 | 1,693 | *(streaming constants)* | Real-time analytics engine: WebSocket, async processing, optional Redis/ZMQ, uvloop support |
| F17 | 1,532 | *(consolidation constants)* | Unified performance analytics: consolidates F15 attribution + X08 AI insights |
| F18 | 1,072 | *(max pain constants)* | Advanced max pain: price gravity analysis, historical accuracy tracking, signal generation |
| F19 | 1,184 | *(anchoring constants)* | Anchored VWAP from significant events (earnings, breakouts) with multi-timeframe bands |
| F20 | 391 | `_arr()` helper | Pure numpy/pandas TA-Lib replacement (no C extensions): SMA, EMA, RSI, MACD, ATR, Stoch, ADX |
| F21 | 860 | `ZSCORE_OVERBOUGHT` | Renaissance-style advanced indicators with optional Kalman filter (pykalman) and IV-based scoring |
| F22 | 1,374 | *(ML prediction constants)* | LSTM/GRU deep learning for price direction and volatility prediction; joblib persistence |

**Numbering gaps:** F15 absent (consolidated into F17). F16 is present; numbering is otherwise sequential.

---

## 9. Series G — GUI & Dashboard

**21 files · 18,613 LOC · Status: ⚠️ 3 deprecated; Plotly numbering jump**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| G00 | 456 | `ApplicationManager` | Qt application lifecycle: QApplication creation before widgets, headless fallback |
| G01 | 96 | `SpyderMainWindow` | Bridge module → redirects to G05 TradingDashboard for backward compatibility |
| G02 | 128 | *(entry)* | GUI entry point; launches G05 with environment setup |
| G03 | 227 | *(option chain widget)* | Interactive options chain table: real-time Greeks, colour-coded ITM/OTM, configurable strike range |
| G04 | 1,632 | *(chart widget)* | Real-time price charting with pyqtgraph, technical indicators, Wayland compatibility |
| G05 | 6,009 | `SpyderTradingDashboard` | **Flagship dashboard** — Three trading modes (BACKTEST/PAPER/LIVE), 12 real-time signal monitors, connection health, TradierClient+DataFeed integration |
| G06 | 527 | *(data models)* | Shared data structures (MarketData, GreekRisk, Position, Order) and dark-theme styling constants |
| G07 | 633 | *(metrics display)* | **DEPRECATED** (Feb 2026) — Legacy Prometheus metrics display; replaced by G15 |
| G08 | 728 | *(data bridge)* | **DEPRECATED** (Feb 2026) — Legacy MarketDataManager bridge; replaced by C01+C27 |
| G09 | 1,198 | `RiskParametersDialog` | Interactive risk parameter configuration with preset profiles (Conservative/Moderate/Aggressive) |
| G10 | 652 | *(custom metrics)* | **DEPRECATED** (Feb 2026) — Legacy custom metrics dashboard; replaced by SpyderN series |
| G11 | 1,371 | *(SKEW monitor)* | Real-time SKEW monitoring with regime analysis and pyQtGraph charting |
| G12 | 521 | `SignalInfoDialog` | Standardised popup dialogs for 12 signal monitor buttons; auto-close, dark theme |
| G13 | 749 | *(enhanced widgets)* | Multi-handle sliders (superqt), searchable combos, collapsible groups, enhanced tooltips |
| G14 | 128 | *(launcher)* | Application entry point: launches G05 with GNOME/Wayland desktop integration |
| G15 | 792 | *(connection status)* | Real-time Tradier broker and Massive data feed status display; replaces legacy ConnectAPI display |
| G16 | 320 | *(circuit breaker monitor)* | Real-time monitoring of Tradier/Massive circuit breaker states (CLOSED/OPEN/HALF_OPEN) |
| G29 | 856 | *(Plotly chart widget)* | High-performance interactive financial charts via Plotly+QWebEngineView; superior Wayland support |
| G30 | 555 | *(Plotly data bridge)* | Converts Spyder market data to Plotly JSON with real-time JS callback updates |
| G31 | 747 | *(Plotly templates)* | Reusable Plotly chart templates (candlestick, indicators, volume) matching Spyder dark theme |
| G99 | 288 | `GUILogHandler` | Custom logging handler sending log records to GUI via Qt signals; thread-safe |

**Numbering gap:** G17–G28 absent. G29/G30/G31 were renumbered from G04 variants during Plotly integration. G07, G08, G10 are deprecated but not deleted.

---

## 10. Series H — Storage & Persistence

**6 files · 4,894 LOC · Status: ✅ Solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| H01 | 1,076 | `DataAccessLayer` | Unified SQLite data access: connection pooling, transactions, schema creation, migration tracking |
| H02 | 913 | `DatabaseManager` | Comprehensive SQLite management: thread-safe, automatic backup/recovery, compression, audit trail |
| H03 | 690 | `MarketDataCache` | Thread-safe in-memory market data cache with TTL presets (quotes/trades/options), LRU eviction |
| H04 | 777 | `TradeRepository` | Trade data CRUD persistence, pagination, batch operations; interfaces with H01 |
| H07 | 852 | *(performance constants)* | Performance analytics: daily/monthly/yearly aggregation, Sharpe, max drawdown, Sortino |
| H08 | 586 | `TradeOutcome` | Comprehensive trade journaling: decision rationale, risk checks, execution details, outcome analysis |

**Numbering gaps:** H05, H06 absent.

---

## 11. Series I — Integration & Diagnostics

**11 files · 8,633 LOC · Status: ✅ Solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| I01 | 828 | `IntegrationHub` | Module dependency graph via NetworkX, health-check orchestration, module lifecycle management |
| I02 | 1,381 | `EventRouter` | Pattern-based event routing with fnmatch topic matching, batch processing, request/reply patterns |
| I03 | 1,393 | `ConfigManager` | Multi-format config management (JSON/YAML/TOML) with file watching, schema validation, hot-reload |
| I04 | 596 | `DiagnosticsEngine` (core) | Centralised diagnostics coordinator: health checks, data collection, analysis, reporting orchestration |
| I05 | 316 | `AnalysisManager` | Performance analysis and pattern detection using psutil: CPU, memory pressure, latency spikes |
| I06 | 835 | `AgentMessageBus` | High-performance pub/sub for inter-agent communication: priority queuing, dead-letter, circuit breaker |
| I07 | 819 | *(syntax validator)* | Automated syntax validation and fixing: autopep8/black/isort integration, indentation/bracket errors |
| I08 | 650 | `DataCollector` | System metrics collection (CPU/memory/disk/network/threads) with time-series deque history |
| I09 | 705 | `HealthCheckManager` | Comprehensive health checks: CPU, memory, disk, network, dependencies, module availability |
| I10 | 441 | *(enum types)* | Diagnostic data types: `HealthStatus`, `DiagnosticCategory`, `ProblemSeverity`, metric dataclasses |
| I11 | 669 | `DiagnosticUtils` | Health score calculation, recommendation generation, summary creation, statistical analysis |

---

## 12. Series J — Alerts & Notifications

**4 files · 3,291 LOC · Status: ⚠️ J03 missing**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| J01 | 784 | `AlertManager` | Centralised alert management with ML-based anomaly detection for fatigue reduction, deduplication, routing |
| J02 | 825 | `EmailNotifier` | SMTP email alerts: Gmail/Outlook/custom, Jinja2 templates, attachments, TLS/SSL, retry logic |
| J04 | 780 | `DesktopNotifier` | Desktop notifications: Windows toast, Linux plyer, macOS; platform-specific sound alerts |
| J05 | 902 | `TelegramBot` | Telegram bot alerts with rate limiting, exponential backoff, message queueing |

**Numbering gap:** J03 absent. Likely a webhook or Slack notifier that was planned but never implemented.

---

## 13. Series K — Reports

**12 files · 12,720 LOC · Status: ✅ Comprehensive**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| K01 | 80 | `ReportGenerator` | Base report generator interface — very thin; foundation for specialised reports |
| K02 | 1,569 | *(daily report)* | Daily trading report: quantstats integration, Plotly charts, PDF export via fpdf |
| K03 | 938 | *(dashboard)* | Interactive Dash-based performance monitoring with real-time updates and lookback selection |
| K04 | 1,087 | *(execution analytics)* | Execution quality: slippage tracking, intraday binning, venue comparison, fill metrics |
| K05 | 805 | *(risk report)* | Risk reporting: VaR, CVaR, expected shortfall, concentration risk, stress scenarios |
| K06 | 1,454 | *(portfolio analytics)* | Portfolio correlation matrices, concentration metrics, diversification scoring, stress testing |
| K07 | 895 | *(strategy comparison)* | Cross-strategy performance comparison, statistical significance testing, equity curve analysis |
| K08 | 1,625 | *(ML performance)* | ML model performance reporting: accuracy, precision, recall, F1, ROC-AUC, feature importance |
| K09 | 1,417 | *(regulatory reports)* | Regulatory compliance: position/risk limits, net capital, daily volume caps, SHA256 audit trail |
| K10 | 1,106 | *(real-time analytics)* | Real-time performance tracking: async updates, rolling Sharpe, streaming statistics |
| K11 | 957 | *(Sharpe dashboard)* | Unified Sharpe monitoring consolidating standard, probabilistic, and options-adjusted Sharpe |
| K12 | 787 | *(tear sheet)* | PyFolio/empyrical-based institutional tear sheet: full risk/return analysis |

---

## 14. Series L — Machine Learning & AI

**14 files · 17,705 LOC · Status: ✅ Strong**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| L01 | 1,169 | *(ML prediction interface)* | ML framework for price direction/volatility prediction: LSTM/GRU optional, feature scaling, persistence |
| L07 | 1,675 | *(learner constants)* | ML feature importance learning from paper trading; RandomForest predictive feature identification |
| L08 | 1,897 | *(optimiser constants)* | Entry optimisation: RandomForest/XGBoost/LightGBM ensemble, Optuna hyperparameter search |
| L09 | 2,110 | `UnifiedRegimeEngine` | **Central regime engine** — Consolidates market regime detection from S07, V07; ML models + signal analysis + quant attribution |
| L10 | 1,314 | *(feature list)* | Comprehensive feature engineering: price, volume, Greeks, IV, microstructure features; scaling |
| L11 | 1,168 | `MLModelManager` | Model lifecycle: training, evaluation, versioning, persistence; optional MLflow integration |
| L12 | 766 | `EnsembleConfig` | Random Forest/GBM ensemble with SHAP explainability, hyperparameter search, async evaluation |
| L13 | 751 | `LSTMConfig` | Bidirectional LSTM for options pricing via PyTorch; dropout regularisation; CUDA support |
| L14 | 826 | *(real-time prediction)* | Real-time ML predictions: feature caching, batch processing, model warm-up, latency optimisation |
| L15 | 755 | *(MOMENT integration)* | MOMENT foundation model for time-series forecasting; sklearn fallback if unavailable |
| L16 | 1,575 | *(RL environment)* | Options adjustment RL via Stable-Baselines3 (PPO/SAC/TD3), vectorised environments, curriculum learning |
| L17 | 1,680 | *(federated coordinator)* | Federated learning: distributed training across nodes, RSA encryption, differential privacy |
| L18 | 1,224 | *(integration orchestrator)* | Multi-model integration (RF/GBM/LSTM) with voting/stacking ensemble; unified inference |
| L19 | 795 | `RLTrainingPipeline` | Unified RL training orchestration: PPO/SAC/TD3/A2C, evaluation, checkpointing, best-model tracking |

**Numbering gaps:** L02–L06 absent (likely earlier ML iterations superseded by the current suite).

---

## 15. Series M — Monitoring

**6 files · 6,175 LOC · Status: ✅ Solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| M01 | 961 | `SystemMonitor` | Real-time system health: CPU, memory, disk, latency, error rates; aggregation windows, alerts |
| M03 | 878 | *(agent health)* | AI agent performance monitoring: latency, error rates, success rates; statistical aggregation |
| M04 | 1,125 | `MetricPeriod` | Trading metrics across granularities (real-time/1m/5m/15m/hourly/daily); P&L tracking, Sharpe |
| M05 | 1,349 | *(cost model)* | Transaction cost analysis: slippage, cost decomposition, VWAP/TWAP/arrival benchmarking, anomaly detection |
| M06 | 1,490 | *(HMM wrapper)* | HMM-based regime detection: 3 regimes (Low-Vol Trending, High-Vol Mean-Reverting, Transitional); lazy-loaded hmmlearn |
| M07 | 372 | *(migration tracker)* | Migration monitoring from SpyderF to SpyderX: divergence detection, performance comparison |

**Numbering gap:** M02 absent.

---

## 16. Series N — Options Analytics

**13 files · 15,864 LOC · Status: ✅ Complete**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| N01 | 1,218 | `PricingModel` | Options pricing: Black-Scholes, Binomial, Monte Carlo; full Greeks + second-order Greeks; IV solving |
| N02 | 1,285 | *(IV calculation engine)* | Real-time IV from chains, IV rank/percentile, term structure, volatility smile/skew, forecasting |
| N03 | 1,275 | `OptionsChainManager` | Options chain data management: efficient data structures, strike selection, expiration cycles |
| N04 | 1,663 | `OptionsGreeksCalculator` | Advanced Greeks (delta/gamma/vega/theta/rho/vanna/charm/vomma), scenario analysis, stress testing |
| N05 | 1,141 | *(expiration management)* | Pin risk analysis, auto-exercise decisions, roll automation, assignment risk, expiration-day strategies |
| N06 | 1,087 | *(surface fitting)* | 3D volatility surface: RBF interpolation, arbitrage detection, term structure, real-time updates |
| N07 | 1,219 | *(flow constants)* | Real-time options flow: UOA detection, sweep identification, smart money, sentiment, flow toxicity |
| N08 | 1,376 | *(surface representation)* | Volatility surface data structure: interpolation, gridding, Plotly/matplotlib visualisation, SVI calibration |
| N09 | 1,266 | *(GEX engine)* | Gamma exposure: spot range profiles, dealer hedging assumptions, GEX pinning probability |
| N10 | 624 | *(flow analysis engine)* | Advanced options flow: smart money detection, institutional block tracking, exchange-level sentiment |
| N11 | 1,177 | *(Greeks flow tracking)* | Real-time Greeks flow analysis: gamma flips, vanna thresholds, charm decay, flow-based signals |
| N12 | 1,283 | *(AI-enhanced surface)* | ML-enhanced volatility surface: LSTM/NN predictions, ML-based arbitrage detection, evolution forecasting |
| N13 | 1,250 | *(impact models)* | Market impact modelling: linear, square-root, Almgren-Chriss, ML-based; options-specific with Greeks |

---

## 17. Series O — Trading Intelligence

**3 files · 4,504 LOC · Status: ✅ New, solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| O01 | 1,281 | `TechnicalIndicatorEngine` | Pure-Python technical indicators with signal generation; eliminates TA-Lib C dependency |
| O02 | 1,340 | `OpportunityScannerEngine` | Multi-strategy opportunity identification, ranking, and cross-strategy analysis; alphalens optional |
| O03 | 1,883 | `StrategyOptimizationEngine` | Pin risk calculators, liquidity scoring, skew anomaly detection, efficiency optimisation |

---

## 18. Series P — Portfolio Management

**7 files · 10,050 LOC · Status: ⚠️ P06 broken import**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| P01 | 2,168 | `PortfolioManager` | Central portfolio lifecycle: position tracking, rebalancing, integration with E/D/S series |
| P02 | 2,213 | `AllocationOptimizer` | Dynamic capital allocation: Kelly, risk parity, ML; optional riskfolio/cvxpy/cvxopt |
| P03 | 730 | `CorrelationAnalyzer` | Correlation tracking, hierarchical clustering, diversification analysis |
| P04 | 1,582 | `CapitalAllocator` | Dynamic Kelly-based position sizing with risk parity; sklearn Ledoit-Wolf optional |
| P05 | 1,356 | `MultiStrategyAllocator` | Cross-strategy allocation with correlation management and regime adaptation |
| P06 | 1,315 | `StrategyRotator` | Regime-based strategy rotation and performance attribution. **Broken import on line ~55**: `import SpyderF_Analysis.SpyderF20_Indicators as talib` — must be `from SpyderF_Analysis import SpyderF20_Indicators as talib` |
| P07 | 686 | `PositionSizer` | Renaissance-style Kelly-based position sizing with confidence-scaled contract calculation |

---

## 19. Series Q — Scripts & Launchers

**12 files · 6,306 LOC · Status: ⚠️ Irregular naming**

| Module | LOC | Name/Purpose |
|--------|----:|--------------|
| Q14 | 475 | `SpyderQ14_MainLauncher` — Fixed main launcher; uses A06 fallback when I05 (non-existent) unavailable |
| Q80 | 423 | `SpyderQ80_VerifyDashboardIntegration` — Validates dashboard integration with system components |
| Q90 | 884 | `SpyderQ90_SystemUtilities` — Cleanup, backup, and data export consolidation |
| Q92 | 1,117 | `SpyderQ92_DiagnosticsUtilities` — Module verification, dependency checking, benchmarking |
| Q93 | 432 | `SpyderQ93_RunPaper` — 30-day paper trading harness launcher with market-aware scheduling |
| — | 165 | `test_gui_logging.py` — GUI logging test script (not following Q naming convention) |
| — | 302 | `fix_exception_handling.py` — Exception handling fix script (not following Q naming) |
| — | 322 | `validate_env.py` — Environment validation script |
| — | 443 | `validate_configuration.py` — Configuration validation script |
| — | 520 | `launch_spyder_working_dashboard.py` — Dashboard launcher |
| — | 576 | `launch_dashboard_with_proactive_connections.py` — Dashboard with auto-connect |
| — | 647 | `launch_spyder_dashboard_direct.py` — Direct dashboard launcher |

**Issues:** Six scripts do not follow the `SpyderQNN_` naming convention. Q numbering has large gaps (Q01–Q13, Q15–Q79, Q81–Q89, Q91 absent).

---

## 20. Series R — Runtime Engines

**10 files · 9,271 LOC · Status: ⚠️ R05 is a stub**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| R01 | 575 | `BacktestEngine` | Basic strategy logic testing. **Explicit warning in docstring: backtesting is UNREALISTIC for options** |
| R02 | 820 | `PaperEngine` | Paper trading engine with Tradier sandbox integration and realistic order simulation |
| R03 | 851 | `PaperMonitor` | Paper trading performance monitoring with thresholds and metrics |
| R04 | 1,255 | `LiveEngine` | Live trading engine: market hours enforcement, safety limits, confirmation logic |
| R05 | 44 | *(stubs only)* | **DEPRECATED** — Legacy IBKR bridge; all functions return `False`/`-1`. Dead code |
| R06 | 1,006 | `PaperTradingHarness` | 30-day paper trading validation with drawdown alerts and session snapshots |
| R07 | 542 | *(launcher)* | Runtime launcher for G05 TradingDashboard with startup sequence |
| R08 | 1,632 | `EnhancedBacktestEngine` | Advanced backtest: multiprocessing, walk-forward analysis, institutional analytics |
| R09 | 1,783 | `ProductionDeploymentManager` | Institutional-grade deployment, health monitoring, failover; Docker/Kubernetes optional |
| R10 | 763 | `DistributedBacktester` | Ray-powered distributed parameter sweep and walk-forward optimisation |

---

## 21. Series S — Signals & Indicators

**8 files · 7,139 LOC · Status: ✅ Good**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| S01 | 598 | `SpyderDIXCalculator` | DIX (Dark Index) calculation from FINRA short volume data; yfinance integration |
| S02 | 887 | `DIXScheduler` | APScheduler-driven DIX updates with email/alert dispatch; some imports reference missing modules |
| S03 | 701 | `BlackSwanIndicator` | Composite tail-risk score (1–5 scale) from VIX, credit spreads, DXY, market internals |
| S04 | 1,437 | `BlackSwanScheduler` | Automated Black Swan monitoring, alerting, daily reports; Slack/Telegram notifications stubbed |
| S05 | 264 | `GexDexCalculator` | Net Gamma Exposure (GEX) and Delta Exposure (DEX) from live options chain |
| S06 | 1,226 | `SKEWCalculator` | CBOE SKEW Index from SPY options chain; threading, caching, CBOE methodology |
| S07 | 744 | `CustomMetricsOrchestrator` | Unified orchestrator for all S-series signals (GEX, DIX, SKEW, Black Swan); regime detection removed to L09 |
| S08 | 1,282 | `ShortSqueezeDetector` | Multi-signal composite detector for short covering and gamma squeezes |

---

## 22. Series T — Testing

**101 files · 91,079 LOC · Status: ✅ Extensive**

The testing suite is one of the system's strongest assets — 101 test files covering all 25 production series. Tests are organised by coverage target, not alphabetically.

| Group | Files | LOC | Coverage Target |
|-------|------:|----:|----------------|
| Framework tests | T01 | 1,936 | Unit test framework itself |
| System integration | T03, T08, T12, T14–T17 | ~5,000 | Black Swan validation, full-system, risk suite, comprehensive |
| Strategy evolution | T06, T07, T11 | ~1,150 | Evolved strategies, advanced evolution, elite strategies |
| Sharpe / F-Series | T18–T24 | ~6,000 | Sharpe calculators, DIX demo, F-series integration, Renaissance |
| Dashboard / UI | T09, T10 | ~4,300 | Dashboard, risk display |
| Tradier / Broker | T40, T43, T44, T45, T50 | ~3,400 | TradierClient, OrderManager, Databento, resilience, order tests |
| Component tests | T42, T46–T59 | ~8,000 | Integration, risk manager, strategy units, pipeline, paper trading, options analytics |
| F-Series analysis | T60 | 755 | F-series analysis module tests |
| Resilience | T61, T65 | ~2,000 | Resilience infrastructure, error handler, network |
| Math/Validation | T62, T63, T73, T74 | ~3,500 | Math, calendar/feature flags, math validators, TA/option strategies |
| U-Series detailed | T66–T105 | ~50,000 | All utility modules; gap-filling tests for U12–U45 |
| Cross-series | T106–T119 | ~15,000 | A-Core, F-Series, N-Series, V-Series, E-Series, B-Series, D-Series, H-Series, L-Series, P-Series, R-Series, Y-Series, Z-Series |
| System diagnostic | T99 | 713 | Full system diagnostic runner |

**Test strategy strengths:**
- Gap-filling test groups (T76–T104) explicitly target the U-series numbering gaps.
- Cross-series integration tests (T106–T119) validate end-to-end module interactions.
- All major external dependencies mocked or have graceful fallback paths.

---

## 23. Series U — Utilities

**29 files · 18,390 LOC · Status: ✅ Foundational**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| U01 | 101 | `SpyderLogger` | Centralised logging with console/file handlers; used by virtually every module |
| U02 | 898 | `SpyderErrorHandler` | Error classification, rate limiting, strategy/system shutdown thresholds |
| U03 | 1,841 | `DateTimeUtils` | Market hours, holiday calendars, ET/UTC timezone conversions |
| U04 | 230 | *(module functions)* | Fernet symmetric encryption and Argon2id password hashing |
| U05 | 491 | `NetworkUtils` | Connectivity testing, retry logic, DNS/ping checks; ping3 optional |
| U06 | 771 | *(utility functions)* | Price rounding, percentile calculations, implied vol helpers |
| U07 | 772 | *(constants only)* | System-wide configuration: symbols, contract specs, risk limits, API endpoints |
| U08 | 883 | *(validation functions)* | Regex/type validation: symbols, emails, prices, orders |
| U09 | 708 | *(Enum classes)* | Standard enums: `OptionRight`, `OrderStatus`, `StrategyType`, etc. |
| U10 | 893 | `TradingCalendar` | Holiday management, market hours, early closures |
| U11 | 725 | `FeatureFlags` | Runtime feature toggles with caching and dynamic refresh |
| U12 | 69 | `AgentMetrics` | Agent health metrics and status tracking. **Very sparse — 69 lines; likely incomplete stub** |
| U13 | 782 | *(indicator functions)* | MA, RSI, MACD, Bollinger Bands, Stochastic, ATR, ADX helpers |
| U14 | 834 | *(options strategies)* | Options strategy payoff calculations, spread utilities |
| U15 | 794 | `PerformanceCalculator` | Sharpe, Sortino, Calmar, Information ratios; drawdown analysis |
| U16 | 690 | *(analysis functions)* | Support/resistance, trend analysis, chart pattern helpers |
| U18 | 749 | `DependencyAnalyzer` | Module import analysis and cross-module dependency mapping via AST |
| U19 | 923 | `InteractionMatrix` | Track dependencies between modules for architecture analysis |
| U20 | 911 | *(library integrations)* | Wrapper functions for riskfolio, empyrical, pyfolio, quantlib; all gracefully degraded |
| U22 | 146 | *(utility functions)* | ET time formatting for dashboard display |
| U23 | 643 | `MemoryMonitor` | Memory usage tracking, leak detection, GC optimisation |
| U24 | 716 | `StyleManager` | Qt stylesheet management and dark theme support |
| U27 | 465 | `SystemOptimizer` | CPU/memory optimisation, process management |
| U40 | 349 | `TokenBucket`, `RateLimiter` | Token bucket algorithm for API/broker rate limiting |
| U41 | 380 | `CircuitBreaker` | Standard circuit breaker pattern (CLOSED/OPEN/HALF_OPEN) |
| U42 | 673 | `StrategyCircuitBreaker` | Strategy-level circuit breaker with loss-streak and error-rate triggers |
| U43 | 479 | `CorrelationLogger` | Log inter-module call patterns and correlation data |
| U44 | 181 | `ShutdownCoordinator` | Graceful daemon thread shutdown with stop events; added 2026-03-31 |
| U45 | 293 | `RetryPolicy`, `BackoffStrategy` | Exponential backoff retry logic for transient failures |

**Numbering gaps:** U17, U21, U25, U26 absent. U28–U39 absent (large gap between utility and resilience ranges).

---

## 24. Series V — Quantitative Models

**8 files · 9,770 LOC · Status: ✅ Consolidated**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| V01 | 932 | `QuantEngine` | **Orchestration only** — delegates pricing to V05, risk to V04; eliminates calculation duplication |
| V02 | 1,047 | `ModelManager` | Intelligent routing across V04–V08 with performance-based model selection |
| V03 | 662 | `DataInterface` | **Stale module** — data bridge originally for removed B08 (MultiClientDataManager); provides fallback stub |
| V04 | 1,345 | `SpyderRiskManager` | Consolidated risk calculations: VaR, CVaR, stress tests, Greeks risk |
| V05 | 1,546 | `SpyderPricingEngine` | Consolidated options pricing: Black-Scholes, Binomial, Longstaff-Schwartz, BAW |
| V06 | 1,730 | `SpyderVolatilityEngine` | Consolidated volatility models: Heston, GARCH, Rough Volatility; delegates pricing to V05 |
| V07 | 1,303 | `AdvancedModelsEngine` | Merton Jump-Diffusion, crisis detection; regime switching removed to L09 |
| V08 | 1,205 | `AIModelEngine` | Transformer pricing neural network + Deep RL trading agent via PyTorch/Stable-Baselines3 |

---

## 25. Series X — AI Agents (On-Demand)

**16 files · 19,513 LOC · Status: ⚠️ Tight coupling in X14/X16**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| X01 | 2,383 | `GreeksAgent` | Real-time Greeks calculation and monitoring; sklearn/tensorflow optional ML enhancement |
| X02 | 1,300 | `FlowAgent` | Order flow analysis and market microstructure insights |
| X03 | 1,009 | `StrategyDirectorAgent` | LLM-powered strategy selection via Ollama local inference |
| X04 | 827 | `RiskGuardianAgent` | Risk monitoring with veto authority; AI-enhanced risk assessment |
| X05 | 1,478 | `MLResearchAgent` | ML model training, AutoML feature engineering, backtesting |
| X06 | 2,055 | `BacktestingAgent` | Agent-orchestrated backtesting with AI insights |
| X07 | 951 | `ExecutionStrategyAgent` | Order execution optimisation: timing, routing, slippage minimisation |
| X08 | 501 | `PerformanceAnalyticsAgent` | Real-time performance tracking and attribution |
| X09 | 1,171 | `AlertManagerAgent` | Intelligent alert dispatch and escalation |
| X10 | 1,525 | `QuantModelsAgent` | Quantitative model coordination and inference |
| X11 | 1,464 | `SentimentAnalysisAgent` | Multi-source NLP sentiment: FinBERT, RoBERTa |
| X12 | 1,227 | `SystemHealthAgent` | System monitoring, diagnostics, and self-healing |
| X13 | 878 | `MarketAnalysisAgent` | Market regime and condition analysis |
| X14 | 1,089 | `OrchestratorAgent` | On-demand coordination of X01–X13; PyTorch/PPO RL; imports all X agents directly |
| X15 | 470 | `StrategyGeneratorAgent` | Automated strategy generation and genetic optimisation |
| X16 | 1,185 | `MetaCoordinator` | Higher-level orchestration with conflict resolution and voting; imports all X01–X15 directly |

**Coupling concern:** X14 and X16 both import all sibling X-series agents at module level, creating a star-dependency that makes individual agent isolation impossible and risks circular imports.

---

## 26. Series Y — Autonomous Agents (Daemon)

**11 files · 6,097 LOC · Status: ✅ New, solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| Y00 | 778 | `BaseAutoAgent` | Abstract base for all Y-series daemon agents: lifecycle (start/stop/pause), Ollama LLM integration, message bus, scheduling |
| Y01 | 524 | `MarketSenseAgent` | Continuous market condition monitoring daemon |
| Y02 | 507 | `StrategyPilotAgent` | 24/7 strategy recommendation generation daemon |
| Y03 | 624 | `RiskSentinelAgent` | Continuous risk monitoring and veto authority daemon |
| Y04 | 546 | `AlphaLearnerAgent` | Continuous strategy learning from market data daemon |
| Y05 | 552 | `ExecutionOptimizerAgent` | 24/7 order execution optimisation daemon |
| Y06 | 553 | `NewsSentinelAgent` | Continuous news monitoring and sentiment tracking daemon |
| Y07 | 540 | `TradeJournalAgent` | Continuous trade logging and outcome analysis daemon |
| Y08 | 617 | `MetaOrchestratorAgent` | High-level daemon orchestration of Y01–Y07 with conflict resolution |
| Y09 | 463 | `CodeReviewerAgent` | Autonomous code quality and drift monitoring daemon |
| Y10 | 393 | `AgentScheduler` | Central control plane for starting/stopping/monitoring all Y-series daemons |

**Note:** Y-series (always-on, Ollama-powered) complements X-series (on-demand, per-task invocation). Y08 and Y10 provide two layers of coordination, which may be excessive.

---

## 27. Series Z — Communication & IPC

**7 files · 9,214 LOC · Status: ✅ Solid**

| Module | LOC | Primary Class | Purpose |
|--------|----:|---------------|---------|
| Z01 | 1,263 | `ZeroMQBroker`, `CircuitBreaker` | ZMQ message broker: heartbeat, reconnection, circuit breaker resilience |
| Z02 | 1,035 | `ProtocolManager` | Message serialisation (JSON/MessagePack), compression, validation; orjson optional |
| Z03 | 1,491 | `TradingCoordinator` | Engine coordination via ZMQ with priority queues |
| Z04 | 1,996 | `VolatilityEngine` | Volatility data broadcasting via ZMQ to subscribers |
| Z05 | 1,216 | `OrderRouter` | Intelligent order routing with venue selection and dark pool support |
| Z06 | 1,210 | `AutoHedger` | Automated hedging with dynamic hedge rebalancing logic |
| Z07 | 1,003 | `MultiProcessManager` | Multi-process lifecycle management with shared memory and ZMQ coordination |

---

## 28. Anomalies & Deficiencies

### 🔴 Critical (likely to cause runtime failures)

| # | Location | Issue |
|---|----------|-------|
| 1 | `SpyderB30_SPYOptionsChainManager.py` | Imports `SpyderB10_IBDataTypes` which was deleted during the IBKR migration. Module will fail at import. |
| 2 | `SpyderP06_StrategyRotation.py:~55` | `import SpyderF_Analysis.SpyderF20_Indicators as talib` is syntactically invalid as a top-level import statement. Should be `from SpyderF_Analysis import SpyderF20_Indicators as talib`. Module fails at import. |
| 3 | `SpyderR05_WorkingBridge.py` | 44-line file containing only deprecated stubs returning `False`/`-1`. No guard against it being accidentally used in a code path expecting real functionality. |

### 🟡 Moderate (degraded functionality or technical debt)

| # | Location | Issue |
|---|----------|-------|
| 4 | `SpyderC07_OPRAFeed`, `C14_UltraLowLatencyFeed`, `C21_MarketDataFeed`, `C26_DatabentoClient` | Four modules explicitly deprecated but not removed. They occupy ~4,638 LOC and will confuse contributors. |
| 5 | `SpyderG07_PrometheusMetricsDisplay`, `G08_DashboardDataBridge`, `G10_CustomMetricsIntegration` | Three GUI modules deprecated February 2026 but retained; risk of accidental reference. |
| 6 | `SpyderV03_DataInterface` | References removed `SpyderB08_MultiClientDataManager`; provides stub interface. The stub may silently succeed where real data is expected. |
| 7 | `SpyderU12_AgentIntegration` | Only 69 lines with no substantive implementation. Named as if it integrates agents but contains only a metrics dataclass. |
| 8 | `SpyderS02_DIXScheduler` | Imports `SpyderS02_DIXDemo`, `SpyderS03_DIXVisualizer`, and `SpyderZ01_EmailSender` — none of these modules exist in the codebase. |
| 9 | `SpyderS04_BlackSwanScheduler` | Slack and Telegram notification channels marked "not yet implemented" in docstring but no `NotImplementedError` raised — silently does nothing. |
| 10 | `SpyderX14_OrchestratorAgent`, `X16_MetaCoordinator` | Both import all 15 sibling X-series agents at module load time, creating a monolithic import chain. Any single X-agent failure will break both orchestrators. |
| 11 | `SpyderB03_PositionTracker` | References `_sync_thread`, `_greeks_thread`, `_pnl_thread` that are never initialised. Position tracker threading infrastructure is incomplete. |
| 12 | `SpyderK01_ReportGenerator` | Only 80 lines — a thin interface with no meaningful implementation. All report types depend on specialised K02–K12 modules, making K01 effectively vestigial. |
| 13 | Multiple E-series modules (E02–E09) | Extensive `try/except ImportError` fallback patterns creating inline mock implementations for Logger, ErrorHandler, Constants. Masks import failures in production. |

### 🟢 Minor (code quality / housekeeping)

| # | Location | Issue |
|---|----------|-------|
| 14 | SpyderQ series | Six scripts (`test_gui_logging.py`, `fix_exception_handling.py`, `validate_env.py`, `validate_configuration.py`, `launch_*.py`) do not follow the `SpyderQNN_` naming convention. |
| 15 | SpyderA07, B01, D06/D07, G17–G28, H05/H06, J03, L02–L06, M02, U17/U21/U25/U26 | Multiple numbering gaps across series. Not inherently harmful but signals iterative development without renumbering — makes discovery harder for new contributors. |
| 16 | `SpyderA06_MasterController` | `logging.basicConfig()` called at module level may interfere with child logger configuration across the system. |
| 17 | `SpyderD31_StrategyOrchestrator` | Imports PySide6 (Qt) as a hard dependency. Will fail in headless environments (CI, Docker, cron-triggered runs). |
| 18 | SpyderC16 vs SpyderH03 | Two market data caches exist. C16 is a multi-tier Redis/SQLite cache; H03 is a simpler in-memory cache. Comments suggest preferring H03, but C16 is also actively used, creating potential cache coherence issues. |
| 19 | `SpyderY08_MetaOrchestratorAgent` + `SpyderY10_AgentScheduler` | Two layers of Y-series control plane coordination. The division of responsibility between "orchestration" (Y08) and "scheduling" (Y10) is not clearly defined. |
| 20 | `SpyderZ04_VolatilityEngine` | At 1,996 lines, this is a very large module for what is described as a "broadcasting" concern. May contain business logic that belongs in the V-series. |

---

## 29. Opportunities for Improvement

### High Priority

**1. Delete deprecated modules**
Remove C07, C14, C21, C26, G07, G08, G10, R05. These 7 modules represent ~8,000 LOC of dead code. Each has a documented replacement. Retaining them indefinitely adds confusion and maintenance surface.

**2. Fix the two critical import failures**
- B30: Replace `from SpyderB10_IBDataTypes import ...` with the equivalent types from B00 or define them locally.
- P06: Change `import SpyderF_Analysis.SpyderF20_Indicators as talib` to `from SpyderF_Analysis import SpyderF20_Indicators as talib`.

**3. Decouple X14 and X16 from sibling X-agents**
Replace direct module-level imports of all X-agents with lazy imports or a registry pattern. This would allow individual agents to fail independently without bringing down the orchestrators.

**4. Implement J03 (missing notifier)**
The gap between J02 (email) and J04 (desktop) suggests a webhook or Slack notifier was planned. S04 has stubbed Slack/Telegram channels. Implementing J03 as a `WebhookNotifier` (Slack, Teams, Discord) would complete the notification stack and fix S04's silent no-ops.

**5. Complete SpyderB03 threading infrastructure**
The `_sync_thread`, `_greeks_thread`, `_pnl_thread` references in B03 indicate an incomplete threading model. Either implement them or remove the references and document that synchronisation happens in the caller.

### Medium Priority

**6. Consolidate the two market data caches**
Decide between C16 (multi-tier Redis/SQLite) and H03 (simple in-memory LRU). Recommend: use H03 for hot in-process data and C16 only when Redis is available and cross-process sharing is needed. Document the distinction clearly.

**7. Expand U12 to a real agent integration utility**
At 69 lines, U12 is a stub. Given that the system now has 27 X-series agents and 11 Y-series agents, a proper agent registry, health aggregator, and lifecycle manager in U12 would provide genuine value.

**8. Rename Q-series scripts to follow convention**
Rename the six non-standard Q scripts to `SpyderQNN_` format, filling the Q numbering gaps (Q01–Q13, Q15–Q79, etc.). Even if many Q slots remain empty, consistent naming is important for codebase navigation.

**9. Add headless guard to D31**
`SpyderD31_StrategyOrchestrator` imports PySide6 unconditionally. Add a `HAS_QT` guard so it can instantiate without a display, enabling CI testing and server-side strategy orchestration.

**10. Clarify Y08 vs Y10 division of responsibility**
Define explicit ownership: Y10 should manage only scheduling/timing, while Y08 handles conflict resolution and cross-agent coordination. Document the boundary to prevent future duplication.

### Ideas & New Directions

**11. Agent observability dashboard**
The Y-series now runs 10 persistent daemon agents. A dedicated G-series panel (e.g. G32_AgentHealthDashboard) showing real-time daemon status, LLM call latency, message bus throughput, and per-agent decision logs would dramatically improve operational visibility.

**12. Strategy contribution analytics**
D31/D32 coordinate many strategies but there is no per-strategy attribution in the live system. A new K13 module integrating with D31's runtime and F17's attribution engine could provide a live "strategy P&L ladder" during market hours.

**13. Centralised secrets management**
Configuration (A03) supports Fernet encryption and U04 provides encryption primitives, but secrets handling is inconsistent (some modules read from env vars, some from config files, some from encrypted YAML). A unified `SpyderU46_SecretsManager` wrapping HashiCorp Vault or AWS Secrets Manager would reduce the attack surface.

**14. Inter-series API contracts**
With 25 series and 441 files, the implicit API contracts between series are only enforced by convention. Introducing typed Protocol classes (extending the approach in C00) for the boundaries between major series (E↔D, F↔X, B↔Z) would enable static analysis and reduce integration bugs.

**15. Backtesting realism improvement for R01**
R01 includes its own warning that it is unrealistic for options. The R08 enhanced engine is better but still lacks: realistic bid/ask spread simulation, options liquidity constraints, early assignment probability, and pin-risk-at-expiry handling. These gaps are all modelled in N05 and F18 but not wired into R08.

**16. Federated learning activation (L17)**
L17 implements a full federated learning system but there is no evidence it is wired to a real multi-node deployment. Defining a reference network topology (even a two-process local test) and connecting L17 to L11's model lifecycle would move this from aspirational to functional.

---

*End of report — 418,153 total lines across 441 files as of April 1, 2026*
