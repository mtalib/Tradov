# Copilot Instructions — Spyder Trading System

> **Last Updated:** April 15, 2026 — 00:00 UTC

## Project Overview

**Spyder** is an autonomous algorithmic trading system for SPY (S&P 500 ETF) options. It uses a modular architecture with 24+ Python packages (A–Z series), combining real-time market analysis, multi-strategy execution, ML-driven predictions, and strict risk management.

- **Primary instrument**: SPY options (Iron Condors, Credit Spreads, Straddles, Zero-DTE, etc.)
- **Broker**: Tradier API (Bearer token auth) — `SpyderB40_TradierClient`
- **Market Data**: Massive API — `SpyderC27_MassiveClient`, `SpyderC29_DataProviderRouter`
- **GUI**: PySide6 (LGPL, Qt6)
- **ML**: scikit-learn, PyTorch, TensorFlow, XGBoost, stable-baselines3
- **LLM Agents**: Ollama (local) with 4 model roles: PRIMARY, FAST, CODE, FINANCE
- **Database**: SQLite
- **OS**: Ubuntu 25.04 / Python 3.13.3 / virtualenv (`.venv`)
- **License policy**: No AGPL dependencies allowed

## Critical Rules

1. **NEVER hardcode credentials** — use `.env` for all API keys, tokens, and secrets
2. **NEVER execute live trades without explicit confirmation** — default to sandbox mode
3. **ALWAYS test in sandbox/paper mode first** before any live deployment
4. **ALWAYS use feature branches** — never commit directly to `master`
5. **NEVER use `print()` in production code** — use `SpyderLogger` from `SpyderU01_Logger`
6. **This system handles REAL MONEY** — every change must be thoroughly tested

## Architecture — Module Series

Each module follows the naming pattern `SpyderX_Name/SpyderXNN_Purpose.py`:

| Series | Package | Responsibility |
|--------|---------|---------------|
| **A** | `SpyderA_Core` | System orchestration, main entry point, configuration |
| **B** | `SpyderB_Broker` | Tradier API integration, order management, execution |
| **C** | `SpyderC_MarketData` | Real-time data feeds, historical data, validation |
| **D** | `SpyderD_Strategies` | Strategy implementations (Iron Condor, Credit Spread, Zero-DTE, etc.) |
| **E** | `SpyderE_Risk` | Risk management, position sizing, circuit breakers, drawdown controls |
| **F** | `SpyderF_Analysis` | Technical indicators, price action, volatility regime detection |
| **G** | `SpyderG_GUI` | PySide6 interface, dashboards, charting |
| **H** | `SpyderH_Storage` | SQLite persistence, data access layer, caching |
| **I** | `SpyderI_Integration` | Third-party integrations, event routing, agent message bus |
| **J** | `SpyderJ_Alerts` | Email, desktop, and Telegram notifications |
| **K** | `SpyderK_Reports` | Performance reports, analytics dashboards |
| **L** | `SpyderL_ML` | Machine learning models, feature engineering, predictions |
| **M** | `SpyderM_Monitoring` | System health, metrics, HMM regime detection |
| **N** | `SpyderN_OptionsAnalytics` | Options pricing, Greeks, volatility surfaces |
| **O** | `SpyderO_TradingIntelligence` | Advanced analytics, opportunity scanning |
| **P** | `SpyderP_PortfolioMgmt` | Portfolio optimization, allocation, strategy rotation |
| **Q** | `SpyderQ_Scripts` | Shell scripts, systemd services, utility launchers |
| **R** | `SpyderR_Runtime` | Backtest engine, paper engine, live engine |
| **S** | `SpyderS_Signals` | Custom signal generation and processing |
| **T** | `SpyderT_Testing` | pytest framework, test utilities, mock data providers |
| **U** | `SpyderU_Utilities` | Logger, error handler, date/time utils, constants |
| **V** | `SpyderV_QuantModels` | Quantitative models, statistical analysis |
| **X** | `SpyderX_Agents` | On-demand AI agents (stateless, 16 agents) |
| **Y** | `SpyderY_AutoAgents` | Autonomous LLM-powered agents (24/7, persistent, 9 agents) |
| **Z** | `SpyderZ_Communication` | Inter-module messaging |

---

## Detailed Module Inventory

Each entry: `Module` — lines of code — purpose description.

### SpyderA_Core — System Orchestration (7 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderA01_Main.py` | 744 | Top-level entry point; bootstraps the system, parses CLI args, initialises all subsystems |
| `SpyderA02_TradingEngine.py` | 1,840 | Core trading engine; drives the main loop, routes signals to strategies and risk layer |
| `SpyderA03_Configuration.py` | 1,350 | System-wide configuration management; loads `.env`, merges defaults, validates settings |
| `SpyderA04_Scheduler.py` | 1,546 | Task and cron scheduler; manages timed jobs (pre-market, intraday, EOD) |
| `SpyderA05_EventManager.py` | 1,195 | Central event bus; publishes and dispatches system-wide events |
| `SpyderA06_MasterController.py` | 1,394 | Master controller; coordinates start/stop/pause across all subsystem modules |
| `SpyderA08_FSeriesOrchestrator.py` | 1,237 | Orchestrates the F-Series analysis pipeline from data ingestion to signal output |

### SpyderB_Broker — Tradier API & Order Management (8 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderB00_OrderTypes.py` | 838 | Defines all order type enums, dataclasses, and constants used across the broker layer |
| `SpyderB02_OrderManager.py` | 1,480 | Manages the full order lifecycle: creation, submission, fills, cancellations, and state tracking |
| `SpyderB03_PositionTracker.py` | 259 | Lightweight real-time position-tracking helper; maintains open-position state cache |
| `SpyderB04_AccountManager.py` | 1,203 | Retrieves and caches Tradier account info: balances, buying power, and margin |
| `SpyderB15_PrometheusMetrics.py` | 1,275 | Exposes broker-level Prometheus metrics (latency, fill rate, rejection rate) |
| `SpyderB30_SPYOptionsChainManager.py` | 945 | Manages and refreshes SPY options chain snapshots; handles strike filtering |
| `SpyderB40_TradierClient.py` | 1,917 | Primary Tradier REST/WebSocket client; handles auth, all API calls, retry logic |

### SpyderC_MarketData — Real-Time & Historical Data (25 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderC00_MarketDataProtocol.py` | 128 | Abstract protocol/interface defining the contract for all market data providers |
| `SpyderC01_DataFeed.py` | 1,350 | Primary real-time tick data feed; normalises, validates, and distributes incoming data |
| `SpyderC02_HistoricalData.py` | 1,003 | Historical OHLCV data retrieval, storage, and aggregation |
| `SpyderC03_OptionChain.py` | 1,092 | Options chain snapshot management; strike/expiry filtering for SPY |
| `SpyderC04_MarketInternals.py` | 881 | Tracks market breadth, advance/decline, new highs/lows, TICK, TRIN |
| `SpyderC05_VolumeProfile.py` | 917 | Intraday and session volume profile (VPOC, HVN, LVN) calculations |
| `SpyderC06_DataValidator.py` | 1,269 | Multi-layer validation of all incoming market data; detects stale, invalid, or anomalous ticks |
| `SpyderC08_SPYFeed.py` | 831 | SPY-specific equity feed; handles split-adjusted prices, dividends, and extended hours |
| `SpyderC09_NewsManager.py` | 1,051 | News headline collection and distribution; interfaces with financial news APIs |
| `SpyderC10_VIXAnalyzer.py` | 1,483 | VIX index analysis: term structure, regime classification, and VIX-based signals |
| `SpyderC11_FuturesBasis.py` | 1,435 | ES/SPY futures basis tracking; roll-adjust calculations; cash-futures arbitrage alerts |
| `SpyderC12_DarkPoolFlow.py` | 786 | Tracks and aggregates reported dark pool prints and off-exchange volume |
| `SpyderC13_IndexComponents.py` | 1,051 | S&P 500 constituent data management; sector weights, rebalance events |
| `SpyderC15_MicrostructureAnalyzer.py` | 1,296 | Intraday market microstructure: bid-ask spread, queue depth, order toxicity |
| `SpyderC16_MarketDataCache.py` | 918 | In-memory LRU cache for frequently accessed market data; TTL eviction |
| `SpyderC17_MarketConfigManager.py` | 1,105 | Dynamic market configuration: session times, holiday overrides, circuit-breaker thresholds |
| `SpyderC18_SKEWCalculator.py` | 1,319 | CBOE SKEW index replication; real-time skew surface construction |
| `SpyderC19_AfterHoursDataManager.py` | 836 | Pre/post-market data collection, gap detection, and overnight risk assessment |
| `SpyderC22_FactorDataProvider.py` | 1,271 | Factor data (momentum, value, quality, size) for ML feature pipelines |
| `SpyderC23_RealTimeDataOptimizer.py` | 1,227 | Optimises real-time data throughput: batching, compression, priority queuing |
| `SpyderC24_ModelDataPipeline.py` | 1,457 | End-to-end data pipeline preparing market data for ML model consumption |
| `SpyderC27_MassiveClient.py` | 1,389 | Massive REST/streaming client; primary real-time options and equity data source |
| `SpyderC29_DataProviderRouter.py` | 620 | Routes data requests between market data providers; primary route is Massive |
| `SpyderC30_OrderFlowAnalyzer.py` | 1,745 | Real-time order flow analysis: delta, cumulative delta, imbalance, absorption |
| `SpyderC35_SentimentAnalyzer.py` | 1,472 | Multi-source sentiment analysis: news, social, options flow, put/call ratios |

### SpyderD_Strategies — Strategy Implementations (25 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderD00_StrategyConstants.py` | 331 | Strategy-wide constants, enums, and shared configuration values |
| `SpyderD01_BaseStrategy.py` | 1,078 | Abstract base class for all strategies; defines signal, entry, exit, and sizing interfaces |
| `SpyderD02_IronCondor.py` | 912 | Iron Condor: sell OTM call spread and OTM put spread; premium collection strategy |
| `SpyderD03_CreditSpread.py` | 1,031 | Vertical credit spread (bull put or bear call); defined-risk premium selling |
| `SpyderD04_ZeroDTE.py` | 1,099 | Zero-days-to-expiry strategy; ultra-short-term intraday premium capture |
| `SpyderD05_Straddle.py` | 1,148 | Straddle: simultaneous ATM call and put; profits from large moves in either direction |
| `SpyderD08_OpeningRangeBreakout.py` | 1,182 | Opening Range Breakout: trades breakouts from the first 15-/30-minute session range |
| `SpyderD09_GreeksBasedStrategy.py` | 1,475 | Greeks-driven strategy selection; dynamically targets specific delta/theta/vega profiles |
| `SpyderD10_IronButterfly.py` | 902 | Iron Butterfly: ATM short straddle + OTM wings; maximum premium at target price |
| `SpyderD11_SpecializedZeroDTE.py` | 1,294 | Enhanced Zero-DTE with adaptive strike selection, gamma risk controls, and time filters |
| `SpyderD12_RSIMeanReversion.py` | 1,028 | RSI-triggered mean-reversion strategy; fades extreme readings with options overlays |
| `SpyderD13_MACrossover.py` | 933 | Moving average crossover strategy with options-based directional expression |
| `SpyderD14_CalendarSpread.py` | 1,211 | Calendar (time) spread: sell near-term, buy far-term same strike; benefits from time decay |
| `SpyderD15_StraddleStrangle.py` | 1,382 | Combined straddle and strangle logic with dynamic strike-width optimisation |
| `SpyderD16_RatioSpreads.py` | 1,465 | Ratio spreads (1×2, 1×3): sell more options than bought; complex risk profile |
| `SpyderD17_DiagonalSpread.py` | 1,363 | Diagonal spread: different strikes AND different expirations; blended theta/directional |
| `SpyderD18_EvolvedCreditSpread.py` | 1,433 | ML-enhanced credit spread with adaptive strike and DTE selection via backtested fitness |
| `SpyderD19_JadeLizard.py` | 1,209 | Jade Lizard: short put + short call spread; no upside risk when structured correctly |
| `SpyderD20_VerticalSpreadOptimizer.py` | 847 | Optimises vertical spread parameters (width, delta, DTE) across all available expirations |
| `SpyderD21_DoubleCalendar.py` | 1,408 | Double Calendar: two calendar spreads at different strikes; wider profit zone |
| `SpyderD22_AdaptiveVolatility.py` | 1,111 | Adapts strategy selection and sizing to the detected volatility regime in real time |
| `SpyderD25_UnifiedCreditSpreadEngine.py` | 1,523 | Unified engine consolidating all credit spread variants under one scoring/selection framework |
| `SpyderD26_GammaScalper.py` | 1,155 | Gamma scalping: delta-neutral long-gamma position adjusted by dynamic delta hedges |
| `SpyderD27_EarningsStrategy.py` | 1,289 | Earnings event strategy; positions around implied move ahead of announcements |
| `SpyderD28_VIXHedging.py` | 1,120 | VIX-based portfolio hedge; activates tail-risk protection when VIX signals spike risk |
| `SpyderD30_RegimeGatedSelector.py` | 1,223 | Regime-gated strategy selector; maps detected market regime to best-fit strategy |
| `SpyderD31_StrategyOrchestrator.py` | 2,075 | Strategy orchestrator: coordinates concurrent strategies, manages capital allocation between them |
| `SpyderD32_MultiLegStrategyCoordinator.py` | 1,881 | Coordinates complex multi-leg orders across strategies; prevents leg-risk overlap |
| `SpyderD33_RenaissanceMeanReversion.py` | 786 | Renaissance-inspired statistical mean-reversion using Ornstein-Uhlenbeck process |

### SpyderE_Risk — Risk Management (23 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderE01_RiskManager.py` | 861 | Core entry point for all pre-trade and post-trade risk validation |
| `SpyderE02_PositionSizer.py` | 1,053 | Dynamic position sizing based on volatility, account equity, and risk budget |
| `SpyderE03_StopLossManager.py` | 1,473 | Stop-loss orchestration: fixed, trailing, time-based, and Greeks-based stops |
| `SpyderE04_DrawdownControl.py` | 938 | Monitors intraday and rolling drawdown; escalates alerts and halts trading at limits |
| `SpyderE05_AutomaticRebalancer.py` | 769 | Auto-rebalances portfolio allocations when strategies drift beyond tolerance bands |
| `SpyderE06_RiskMetrics.py` | 1,215 | Computes VaR, CVaR, Sharpe, Sortino, max drawdown, and other risk KPIs |
| `SpyderE07_ProbabilisticSharpe.py` | 747 | Probabilistic Sharpe Ratio calculation with bootstrapped confidence intervals |
| `SpyderE08_PositionGroupValidator.py` | 1,177 | Validates correlated position groups; enforces combined Greeks and notional limits |
| `SpyderE09_VolatilityRiskManager.py` | 1,110 | Volatility-specific risk controls: vega limits, IV crush protection, regime-aware sizing |
| `SpyderE10_CorrelationRiskManager.py` | 1,947 | Cross-position correlation analysis; prevents over-concentration in correlated bets |
| `SpyderE11_MaxLossProtection.py` | 954 | Hard maximum-loss circuit; liquidates positions when P&L breaches configured limit |
| `SpyderE12_PortfolioVaR.py` | 1,488 | Portfolio-level Value at Risk via historical simulation, Monte Carlo, and parametric methods |
| `SpyderE13_DayProfitTarget.py` | 2,263 | Daily profit target management; scales back risk once target achieved |
| `SpyderE14_KellyPositionSizer.py` | 755 | Kelly Criterion position sizing with fractional Kelly for conservative application |
| `SpyderE15_GreekLimitsManager.py` | 1,156 | Enforces portfolio-level Greeks exposure limits (delta, gamma, vega, theta, rho) |
| `SpyderE16_CircuitBreakerProtocol.py` | 470 | Circuit breaker implementation: halts all new orders on trigger conditions |
| `SpyderE17_RealTimeStressTesting.py` | 1,543 | Continuous intraday stress testing using current Greeks against historical shock scenarios |
| `SpyderE18_FSeriesRiskIntegrator.py` | 1,374 | Integrates F-Series analytics signals into risk validation pipeline |
| `SpyderE19_UnifiedRiskCoordinator.py` | 1,223 | Unified coordinator: fans risk checks out to all E-Series modules and aggregates verdicts |
| `SpyderE20_FrustrationAnalyzer.py` | 1,632 | Behavioural/frustration analysis; detects over-trading patterns and revenge-trade conditions |
| `SpyderE21_HMMRegimeDetector.py` | 1,053 | Hidden Markov Model regime detector embedded in the risk layer for defensive mode switching |
| `SpyderE22_KernelRegression.py` | 865 | Kernel regression for non-parametric trend and volatility estimation |
| `SpyderE23_PortfolioOptimizer.py` | 2,020 | Mean-variance and Black-Litterman portfolio optimisation; efficient frontier computation |

### SpyderF_Analysis — Technical & Market Analysis (21 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderF01_Indicators.py` | 875 | Core set of technical indicators (RSI, MACD, Bollinger, ATR, etc.) |
| `SpyderF02_PriceAction.py` | 892 | Price action patterns: candlestick formations, pin bars, engulfing, inside bars |
| `SpyderF03_SupportResistance.py` | 810 | Automated support and resistance level detection via swing pivots and volume clusters |
| `SpyderF04_VolatilityAnalysis.py` | 932 | Historical and realised volatility calculations; HV cone, IV rank, IV percentile |
| `SpyderF05_TrendDetection.py` | 799 | Multi-timeframe trend detection and classification (strong/weak bull/bear/neutral) |
| `SpyderF06_GreeksCalculator.py` | 998 | Options Greeks computation (BSM-based delta, gamma, theta, vega, rho) |
| `SpyderF07_GapAnalyzer.py` | 785 | Market gap detection, classification (common/breakaway/exhaustion), and gap-fill probability |
| `SpyderF08_VolatilityRegime.py` | 1,032 | Volatility regime classification: low/medium/high/extreme using multi-signal consensus |
| `SpyderF09_EntryFilters.py` | 1,113 | Pre-entry signal filters: time-of-day, spread quality, volume, regime, and news guards |
| `SpyderF10_MarketRegimeDetector.py` | 1,458 | Composite market regime detector combining breadth, momentum, and volatility signals |
| `SpyderF11_GreeksAggregator.py` | 1,064 | Aggregates position-level Greeks to portfolio-level exposure with P&L attribution |
| `SpyderF12_AdvancedBacktestingEngine.py` | 1,898 | Advanced vectorised backtesting engine with realistic slippage, commissions, and fills |
| `SpyderF13_ModelValidation.py` | 1,477 | Walk-forward validation, out-of-sample testing, and overfitting detection for ML models |
| `SpyderF14_MarketMicrostructure.py` | 1,567 | Intraday microstructure analytics: trade clustering, VPIN, order-flow imbalance |
| `SpyderF16_RealTimeAnalytics.py` | 1,699 | Streaming real-time analytics pipeline feeding live dashboards and strategy signals |
| `SpyderF17_UnifiedPerformanceEngine.py` | 1,608 | Unified engine computing all performance metrics (Sharpe, Calmar, win rate, edge) |
| `SpyderF18_MaxPainCalculator.py` | 1,101 | Options max pain calculation from open interest data; identifies key gravitational strikes |
| `SpyderF19_AnchoredVWAP.py` | 1,218 | Anchored VWAP from user-defined anchor events; VWAP bands and deviation studies |
| `SpyderF20_Indicators.py` | 393 | Supplementary indicator set; extended library of less-common indicators |
| `SpyderF20_MLPrediction.py` | 1,398 | ML-driven price and volatility prediction integrated into the F-Series signal pipeline |
| `SpyderF21_RenaissanceIndicators.py` | 841 | Renaissance Technologies-inspired quantitative indicators: eigenportfolio momentum, Kalman filters |

### SpyderG_GUI — PySide6 Graphical Interface (21 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderG00_ApplicationManager.py` | 474 | Application lifecycle manager: QApplication setup, theme, exception hooks |
| `SpyderG01_MainWindow.py` | 114 | Main window shell; docking layout, menu bar, status bar |
| `SpyderG02_GUIEntry.py` | 131 | GUI entry point; launches the application in standalone or embedded mode |
| `SpyderG03_OptionChainWidget.py` | 231 | Options chain table widget with strike filtering, IV display, and Greeks columns |
| `SpyderG04_ChartWidget.py` | 1,639 | Primary chart widget (Qt/Matplotlib); OHLCV candlestick with indicator overlays |
| `SpyderG05_TradingDashboard.py` | 4,486 | Main trading dashboard: positions, P&L, Greeks, orders, market status — all in one view |
| `SpyderG06_DashboardData.py` | 540 | Data model layer for the dashboard; normalises and refreshes display data |
| `SpyderG07_PrometheusMetricsDisplay.py` | 658 | Prometheus metrics display panel: latency, throughput, error rates |
| `SpyderG08_DashboardDataBridge.py` | 751 | Thread-safe bridge connecting the data layer to the PySide6 dashboard widgets |
| `SpyderG09_RiskParametersDialog.py` | 1,205 | Risk parameters configuration dialog: delta limits, VaR, daily loss caps |
| `SpyderG10_CustomMetricsIntegration.py` | 658 | Integrates custom metrics (DIX, GEX, SKEW) into the dashboard display |
| `SpyderG11_SkewMonitorDialog.py` | 1,378 | SKEW index monitor dialog with real-time chart and historical percentile display |
| `SpyderG12_SignalInfoDialog.py` | 523 | Signal information popup: source, confidence, Greeks impact, and recommended action |
| `SpyderG13_EnhancedWidgets.py` | 754 | Collection of enhanced UI widgets: gauges, sparklines, heat maps, traffic lights |
| `SpyderG14_Dashboard.py` | 131 | Lightweight legacy/stub dashboard for backward compatibility |
| `SpyderG15_ConnectAPIStatus.py` | 793 | API connectivity status panel; shows live/sandbox mode, latency, and connection health |
| `SpyderG16_CircuitBreakerMonitor.py` | 324 | Circuit breaker status monitor; shows active breakers and breach history |
| `SpyderG29_ChartWidgetPlotly.py` | 863 | Plotly-based interactive chart widget embedded in PySide6 via QWebEngineView |
| `SpyderG30_PlotlyDataBridge.py` | 562 | Converts internal market data structures to Plotly-compatible JSON/trace format |
| `SpyderG31_PlotlyTemplates.py` | 752 | Plotly chart templates and themes (dark mode, branded colours) |
| `SpyderG99_GUILogHandler.py` | 290 | GUI log handler; streams SpyderLogger output to an in-dashboard log console |

### SpyderH_Storage — SQLite Persistence & Caching (5 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderH01_DataAccessLayer.py` | 1,080 | Data access layer (DAL): parameterised SQL, connection pooling, transaction management |
| `SpyderH02_DatabaseManager.py` | 903 | SQLite database manager: schema initialisation, migrations, backup, and integrity checks |
| `SpyderH03_MarketDataCache.py` | 696 | Market data cache layer: in-process + SQLite-backed caching with TTL eviction |
| `SpyderH04_TradeRepository.py` | 780 | Trade history repository: CRUD for trades, fills, positions, and audit records |
| `SpyderH07_PerformanceAnalytics.py` | 854 | Performance analytics storage: persists Sharpe, drawdown, and strategy metrics |

### SpyderI_Integration — Event Routing & Diagnostics (11 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderI01_IntegrationHub.py` | 834 | Central integration hub: registers all modules, manages service discovery |
| `SpyderI02_EventRouter.py` | 1,401 | Event routing system: publish-subscribe, priority queues, async and sync dispatch |
| `SpyderI03_ConfigManager.py` | 1,442 | Runtime configuration manager: hot-reload, env-override, schema validation |
| `SpyderI04_DiagnosticsEngine_Analyzers.py` | 317 | Diagnostic analyser plugins: interprets collected metrics for anomaly detection |
| `SpyderI04_DiagnosticsEngine_Core.py` | 602 | Diagnostics engine core: orchestrates data collection, analysis, and reporting |
| `SpyderI06_AgentMessageBus.py` | 844 | Agent message bus: routes messages between X-Series and Y-Series AI agents |
| `SpyderI07_SyntaxValidator.py` | 826 | Syntax and schema validator for dynamically loaded configs and agent-generated code |
| `SpyderI08_DiagnosticsEngine_DataCollector.py` | 666 | Data collector: gathers CPU, memory, latency, and trade metrics for diagnostics |
| `SpyderI09_DiagnosticsEngine_HealthChecks.py` | 719 | Health check runner: liveness and readiness probes for all system components |
| `SpyderI10_DiagnosticsEngine_Types.py` | 442 | Type definitions for all diagnostics data structures and enums |
| `SpyderI11_DiagnosticsEngine_Utils.py` | 686 | Utility functions shared across all DiagnosticsEngine sub-modules |

### SpyderJ_Alerts — Notifications (4 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderJ01_AlertManager.py` | 798 | Alert management: routing, deduplication, priority, and escalation logic |
| `SpyderJ02_EmailNotifier.py` | 829 | Email notification via SMTP; HTML-formatted trade alerts and daily summaries |
| `SpyderJ04_DesktopNotifier.py` | 785 | Desktop notification integration (libnotify/D-Bus on Linux) |
| `SpyderJ05_TelegramBot.py` | 909 | Telegram bot: sends trade alerts, account updates, and risk warnings via Bot API |

### SpyderK_Reports — Performance Reporting (12 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderK01_ReportGenerator.py` | 81 | Abstract base report generator interface |
| `SpyderK02_DailyTradingReport.py` | 1,535 | Generates comprehensive daily P&L report with trade log, strategy breakdown, Greeks |
| `SpyderK03_PerformanceDashboard.py` | 945 | Performance summary dashboard: equity curve, drawdown, Sharpe, win rate |
| `SpyderK04_ExecutionAnalytics.py` | 1,103 | Execution quality analytics: slippage, fill rate, market impact, and NBBO analysis |
| `SpyderK05_RiskReport.py` | 806 | Daily risk report: VaR, stress test results, Greeks exposure, limit utilisation |
| `SpyderK06_PortfolioAnalytics.py` | 1,471 | Portfolio-level analytics: sector exposure, correlation matrix, return attribution |
| `SpyderK07_StrategyComparison.py` | 896 | Side-by-side strategy comparison: returns, risk-adj metrics, win rates |
| `SpyderK08_MLPerformanceReport.py` | 1,643 | ML model performance report: prediction accuracy, feature importance, drift detection |
| `SpyderK09_RegulatoryReports.py` | 1,436 | Regulatory and compliance reports: trade confirmations, position limits, audit logs |
| `SpyderK10_RealTimePerformanceAnalytics.py` | 1,108 | Streaming real-time performance analytics fed to the GUI dashboards |
| `SpyderK11_UnifiedSharpeDashboard.py` | 971 | Unified Sharpe ratio dashboard: rolling, annualised, and probabilistic Sharpe views |
| `SpyderK12_InstitutionalTearSheet.py` | 786 | Institutional-style tear sheet: full strategy fact sheet with risk metrics |

### SpyderL_ML — Machine Learning (14 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderL01_MLPredictor.py` | 1,075 | Core ML prediction engine; wraps trained models for real-time inference |
| `SpyderL07_PaperTradeLearner.py` | 1,700 | Learns from paper trading results; updates model priors without live capital risk |
| `SpyderL08_EntryOptimizer.py` | 1,712 | ML-driven entry timing optimiser; selects optimal strike, DTE, and entry price |
| `SpyderL09_UnifiedRegimeEngine.py` | 2,069 | Unified ML regime classification engine combining HMM, clustering, and ensemble models |
| `SpyderL10_FeatureEngineering.py` | 1,327 | Automated feature engineering: technical, microstructure, flow, and sentiment features |
| `SpyderL11_MLModelManager.py` | 1,154 | ML model lifecycle: versioning, training, evaluation, deployment, and rollback |
| `SpyderL12_RandomForestEnsemble.py` | 765 | Random forest ensemble model for regime classification and direction probability |
| `SpyderL13_LSTMPricer.py` | 753 | LSTM deep learning model for options pricing and IV surface prediction |
| `SpyderL14_RealTimePredictor.py` | 842 | Low-latency real-time inference wrapper for deployed ML models |
| `SpyderL15_MomentPredictor.py` | 763 | Momentum predictor: ML-based short-term price momentum scoring |
| `SpyderL16_OptionsAdjustmentRL.py` | 1,579 | Reinforcement learning agent for adaptive options position adjustment decisions |
| `SpyderL17_FederatedLearning.py` | 1,705 | Privacy-preserving federated learning framework for multi-strategy model training |
| `SpyderL18_EnhancedMLIntegration.py` | 1,232 | Enhanced integration layer connecting ML models to strategy and risk subsystems |
| `SpyderL19_RLTrainingPipeline.py` | 789 | Reinforcement learning training pipeline: environment, rewards, episode management |

### SpyderM_Monitoring — System Health & Metrics (6 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderM01_SystemMonitor.py` | 966 | System health monitor: CPU, memory, disk, network, and process metrics via psutil |
| `SpyderM03_AIAgentMonitor.py` | 873 | Monitors AI agent health: response time, error rate, task completion rate |
| `SpyderM04_TradingMetrics.py` | 1,123 | Trading metrics collector: real-time P&L, fill rate, order rate, and latency histograms |
| `SpyderM05_TransactionCostAnalysis.py` | 1,378 | Transaction cost analysis (TCA): commissions, slippage, market impact breakdown |
| `SpyderM06_HMMRegimeDetector.py` | 1,421 | Standalone HMM regime detector for system-level market state monitoring |
| `SpyderM07_MigrationMonitor.py` | 374 | Monitors data migration jobs for completeness and data integrity |

### SpyderN_OptionsAnalytics — Options Pricing & Greeks (13 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderN01_OptionsPricer.py` | 1,283 | Options pricing engine: Black-Scholes-Merton, binomial tree, and American option models |
| `SpyderN02_ImpliedVolatilityEngine.py` | 1,342 | IV calculation via Newton-Raphson and bisection; handles complex surfaces and smiles |
| `SpyderN03_OptionsChainManager.py` | 1,285 | Options chain normalisation, gap filling, and chain-level analytics |
| `SpyderN04_OptionsGreeksCalculator.py` | 1,669 | High-precision Greeks (delta, gamma, theta, vega, rho, charm, vanna, volga) |
| `SpyderN05_OptionsExpirationManager.py` | 1,173 | Expiration cycle management: DTE tracking, roll scheduling, pin-risk alerts |
| `SpyderN06_VolatilitySurfaceBuilder.py` | 1,124 | Constructs the full 3-D IV surface from options chain data using interpolation methods |
| `SpyderN07_OptionsFlowTracker.py` | 1,251 | Tracks large unusual options flow: sweep detection, block prints, open interest changes |
| `SpyderN08_VolatilitySurface.py` | 1,409 | Volatility surface model: SVI, SABR, and spline fits for full term-structure coverage |
| `SpyderN09_GammaExposure.py` | 1,295 | Net Gamma Exposure (GEX) calculation: dealer hedging pressure and key GEX flip levels |
| `SpyderN10_OptionsFlowAnalyzer.py` | 637 | Analyses options flow for directional signals: bull/bear skew, premium paid/received |
| `SpyderN11_OptionsGreeksFlow.py` | 1,213 | Greeks-adjusted flow analysis: delta/vega-weighted order flow imbalance |
| `SpyderN12_VolatilitySurfaceAI.py` | 1,288 | AI-enhanced volatility surface: ML corrections to model prices for smile arbitrage |
| `SpyderN13_MarketImpactModel.py` | 1,276 | Market impact model: estimates price impact of options trades for sizing decisions |

### SpyderO_TradingIntelligence — Advanced Analytics (3 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderO01_CoreTechnicalIndicators.py` | 1,338 | Expanded core technical indicator library including institutional-grade indicators |
| `SpyderO02_TradingOpportunityScanner.py` | 1,328 | Scans all available instruments/expirations for high-probability opportunities |
| `SpyderO03_StrategyOptimizers.py` | 1,955 | Strategy parameter optimisation via grid search, Optuna, and genetic algorithms |

### SpyderP_PortfolioMgmt — Portfolio Management (7 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderP01_PortfolioManager.py` | 2,234 | Top-level portfolio manager: tracks all open positions and portfolio-level Greeks |
| `SpyderP02_AllocationOptimizer.py` | 2,263 | Allocation optimisation: mean-variance, risk-parity, and Black-Litterman allocation |
| `SpyderP03_CorrelationAnalyzer.py` | 786 | Cross-strategy and cross-position correlation monitoring and reporting |
| `SpyderP04_CapitalAllocator.py` | 1,606 | Dynamic capital allocation engine: adjusts strategy capital budgets by performance |
| `SpyderP05_MultiStrategyAllocator.py` | 1,389 | Multi-strategy capital allocation with regime-conditional weighting |
| `SpyderP06_StrategyRotation.py` | 1,347 | Strategy rotation engine: schedules strategy activation/deactivation by regime |
| `SpyderP07_RenaissancePositionSizer.py` | 724 | Renaissance-inspired statistical position sizing using eigenportfolio decomposition |

### SpyderQ_Scripts — Utility & Launcher Scripts (11 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderQ14_MainLauncher.py` | 431 | Main system launcher: selects live/paper/backtest mode and starts subsystems |
| `SpyderQ80_VerifyDashboardIntegration.py` | 443 | Verifies dashboard integration: checks all data bridges and widget connections |
| `SpyderQ90_SystemUtilities.py` | 888 | General system utility functions: process management, env checks, log rotation |
| `SpyderQ92_DiagnosticsUtilities.py` | 1,118 | Diagnostics CLI utilities: snapshot, health-dump, and module-status commands |
| `SpyderQ93_RunPaper.py` | 436 | One-command paper trading launcher with pre-flight sanity checks |
| `launch_dashboard_with_proactive_connections.py` | 584 | Launcher that pre-warms API connections before opening the dashboard |
| `launch_spyder_dashboard_direct.py` | 657 | Direct dashboard launcher bypassing the trading engine (display-only mode) |
| `launch_spyder_working_dashboard.py` | 545 | Known-working dashboard launcher with fallback data stubs |
| `validate_configuration.py` | 445 | Validates all configuration keys, types, and required fields against the schema |
| `validate_env.py` | 346 | Validates `.env` file: checks for required vars, non-empty values, and format |
| `test_gui_logging.py` | 166 | Development script: tests GUI log handler by emitting messages at all severity levels |

### SpyderR_Runtime — Runtime Execution Engines (10 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderR01_BacktestEngine.py` | 577 | Basic event-driven backtест engine with OHLCV data replay |
| `SpyderR02_PaperEngine.py` | 941 | Paper trading engine: simulates order execution against live market data |
| `SpyderR03_PaperMonitor.py` | 855 | Monitors paper trading session: tracks virtual P&L and position state |
| `SpyderR04_LiveEngine.py` | 823 | Live trading engine: routes signals to broker, manages real order flow |
| `SpyderR05_WorkingBridge.py` | 512 | Bridge between runtime engines and the data/broker layers |
| `SpyderR06_PaperTradingHarness.py` | 1,008 | Paper trading harness: complete test harness for strategy validation |
| `SpyderR07_LiveDashboard.py` | 577 | Lightweight live-trading status dashboard with real-time P&L and risk display |
| `SpyderR08_EnhancedBacktestEngine.py` | 1,482 | Enhanced backtестengine: realistic fills, commission schedules, margin simulation |
| `SpyderR09_ProductionDeploymentManager.py` | 1,823 | Production deployment manager: health checks, rollout, rollback, and monitoring hooks |
| `SpyderR10_DistributedBacktester.py` | 781 | Distributed backtesting: parallelises walk-forward runs across CPU cores |

### SpyderS_Signals — Custom Signal Generation (7 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderS01_DIXCalculator.py` | 703 | DIX (Dark Index) calculation: ratio of dark pool volume to total volume |
| `SpyderS02_DIXScheduler.py` | 898 | Schedules DIX data collection and caching; manages update frequency |
| `SpyderS03_BlackSwanIndicator.py` | 581 | Black Swan indicator: multi-signal composite flagging extreme tail-risk conditions |
| `SpyderS04_BlackSwanScheduler.py` | 1,287 | Scheduler for Black Swan indicator; manages data polling and alert emission |
| `SpyderS05_GEXDEXCalculator.py` | 68 | GEX/DEX (Gamma/Delta Exposure) stub calculator; placeholder for live integration |
| `SpyderS06_SKEWCalculator.py` | 1,265 | CBOE SKEW index replication from options chain data; real-time and daily computation |
| `SpyderS07_CustomMetricsOrchestrator.py` | 786 | Orchestrates all custom metrics (DIX, GEX, SKEW, Black Swan) into a unified feed |

### SpyderT_Testing — Test Framework & Test Suites (80+ modules)

The T-Series contains the complete pytest test suite. Key structural files:

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderT01_UnitTestFramework.py` | 1,908 | Core test framework: `SpyderTestBase`, fixtures, mock data providers, and helpers |
| `SpyderT02_BrokerTestSuite.py` | 919 | Broker-layer test suite: order types, account management, and Tradier mock |
| `SpyderT03_BlackSwanValidator.py` | 1,209 | Validates Black Swan indicator logic against historical tail-risk events |
| `SpyderT09_TestDashboard.py` | 3,372 | Interactive test dashboard for manual QA of GUI components |
| `SpyderT40_TradierClient_Test.py` | 429 | Unit tests for Tradier API client: auth, orders, quotes, and error handling |
| `SpyderT42_Integration_Test.py` | 351 | Live integration tests (sandbox credentials required; skipped in CI) |
| `SpyderT43_OrderManager_Test.py` | 806 | Order manager tests: lifecycle states, partial fills, cancellations |
| `SpyderT44_DatabentoClient_Test.py` | 547 | Market data client tests: schema validation and streaming requests |
| `SpyderT46_RiskManager_Test.py` | 485 | Risk manager unit tests: position sizing, limits, and circuit breaker triggers |
| `SpyderT47_StrategyUnit_Test.py` | 469 | Strategy unit tests: signal generation, entry/exit logic for all D-Series |
| `SpyderT55_PaperTradingHarness_Test.py` | 750 | Paper trading harness tests: end-to-end scenario validation |
| `SpyderT56_StrategyTests.py` | 706 | Comprehensive strategy tests covering all strategy classes |
| `SpyderT57_OptionsAnalyticsTests.py` | 575 | Options analytics tests: pricing, Greeks, IV surface accuracy |
| `SpyderT58_RiskManagementTests.py` | 706 | Risk management tests: VaR, drawdown, Greeks limits |
| `SpyderT65_ErrorHandlerNetworkTests.py` | 1,288 | Error handler and network utilities tests |
| `SpyderT67_RateLimiterCircuitBreakerTests.py` | 916 | Rate limiter and circuit breaker behaviour tests |
| `SpyderT77_CalendarInstitutionalLibrariesTests.py` | 1,161 | Trading calendar and institutional library tests |
| `SpyderT106_ACore.py` | 1,631 | A-Series (Core) comprehensive test suite |
| `SpyderT107_FSeries.py` | 1,581 | F-Series (Analysis) comprehensive test suite |
| `SpyderT108_NSeries.py` | 1,004 | N-Series (Options Analytics) comprehensive test suite |
| `SpyderT111_LSeries.py` | 1,478 | L-Series (ML) comprehensive test suite |
| `SpyderT112_ESeries.py` | 1,390 | E-Series (Risk) comprehensive test suite |
| `SpyderT113_BSeries.py` | 817 | B-Series (Broker) comprehensive test suite |
| `SpyderT114_DSeries.py` | 1,818 | D-Series (Strategies) comprehensive test suite |
| *(+ 60 additional test modules covering all U-Series utilities and integration scenarios)* | | |

### SpyderU_Utilities — Core Utilities (28 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderU01_Logger.py` | 103 | `SpyderLogger` singleton: thread-safe structured logging with rotating file handler |
| `SpyderU02_ErrorHandler.py` | 919 | `SpyderErrorHandler`: centralised exception handling, retry logic, alerting hooks |
| `SpyderU03_DateTimeUtils.py` | 1,856 | Comprehensive date/time utilities: market hours, session classification, timezone handling |
| `SpyderU04_Encryption.py` | 159 | AES encryption utilities for protecting sensitive data at rest |
| `SpyderU05_NetworkUtils.py` | 545 | Network utilities: connection checks, retry-with-backoff, SSL helpers |
| `SpyderU06_MathUtils.py` | 787 | Mathematical utilities: rolling statistics, interpolation, normalisation, rounding |
| `SpyderU07_Constants.py` | 790 | System-wide constants: tick sizes, lot sizes, sector classifications, API endpoints |
| `SpyderU08_Validators.py` | 917 | Input validators: symbol, price, quantity, date, and config value validators |
| `SpyderU09_DataTypes.py` | 742 | Custom data types and typed dataclasses: `Quote`, `Trade`, `Greeks`, `Position` |
| `SpyderU10_TradingCalendar.py` | 917 | NYSE trading calendar: holiday schedule, session times, early close detection |
| `SpyderU11_FeatureFlags.py` | 745 | Feature flag system: runtime enable/disable of features without code deployment |
| `SpyderU12_AgentIntegration.py` | 70 | Thin utility layer bridging X/Y agent calls with the message bus |
| `SpyderU13_TechnicalIndicators.py` | 806 | Additional technical indicators library (extends F01) |
| `SpyderU14_OptionStrategies.py` | 863 | Options strategy utility functions: payoff, breakeven, max profit/loss calculations |
| `SpyderU15_PerformanceMetrics.py` | 815 | Performance metric computation: CAGR, Sharpe, Sortino, Calmar, max drawdown |
| `SpyderU16_TechnicalAnalysis.py` | 690 | Technical analysis utilities: pattern recognition, pivot detection helpers |
| `SpyderU18_DependencyAnalyzer.py` | 771 | Module dependency analyser: maps import graph, detects circular dependencies |
| `SpyderU19_InteractionMatrix.py` | 948 | Module interaction matrix: tracks and visualises inter-module call patterns |
| `SpyderU20_InstitutionalLibraries.py` | 921 | Wrappers for institutional quantitative libraries: QuantLib, scipy.stats, statsmodels |
| `SpyderU22_ETTimeDisplay.py` | 158 | Eastern Time display helpers: formatted timestamps for UI and logging |
| `SpyderU23_MemoryMonitor.py` | 702 | Process memory monitor: tracks heap usage, detects leaks, triggers GC if needed |
| `SpyderU24_StyleManager.py` | 719 | UI style manager: dark/light theme tokens, colour palettes, font definitions |
| `SpyderU27_SystemOptimizer.py` | 637 | System performance optimizer: CPU affinity, thread-pool tuning, GC schedule |
| `SpyderU40_RateLimiter.py` | 352 | Token-bucket rate limiter for API call throttling |
| `SpyderU41_CircuitBreaker.py` | 381 | Utility-layer circuit breaker; complements `SpyderE16` for non-trading pathways |

### SpyderV_QuantModels — Quantitative Models (8 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderV01_QuantEngine.py` | 945 | Core quantitative engine: coordinates all V-Series model execution |
| `SpyderV02_ModelManager.py` | 1,056 | Quant model lifecycle: registration, parameter storage, performance tracking |
| `SpyderV03_DataInterface.py` | 677 | Data interface for quant models: feeds clean market data into model pipelines |
| `SpyderV04_RiskManager.py` | 1,356 | Quant-layer risk manager: analytic Greeks, scenario analysis, stress testing |
| `SpyderV05_PricingEngine.py` | 1,560 | Advanced pricing engine: Heston, SABR, local-vol, and jump-diffusion models |
| `SpyderV06_VolatilityEngine.py` | 1,698 | Quantitative volatility engine: GARCH, EGARCH, HAR-RV, and realised vol models |
| `SpyderV07_AdvancedModels.py` | 1,320 | Advanced stochastic models: affine jump-diffusion, rough volatility (rBergomi) |
| `SpyderV08_AIModels.py` | 1,215 | AI-enhanced quantitative models: neural network pricing and vol prediction |

### SpyderX_Agents — On-Demand AI Agents (16 modules)

Stateless agents invoked by the system or operator on demand via Ollama LLM.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderX01_GreeksAgent.py` | 2,449 | Analyses options Greeks exposure and recommends adjustments or hedges |
| `SpyderX02_FlowAgent.py` | 1,243 | Interprets order flow data and classifies institutional vs. retail activity |
| `SpyderX03_StrategyDirectorAgent.py` | 1,029 | Recommends strategy selection based on regime, IV rank, and risk budget |
| `SpyderX04_RiskGuardianAgent.py` | 833 | Reviews risk metrics in natural language; alerts on limit breaches |
| `SpyderX05_MLResearchAgent.py` | 1,515 | Proposes and evaluates ML model improvements using research context |
| `SpyderX06_BacktestingAgent.py` | 2,081 | Runs targeted backtests on strategy variants and summarises results |
| `SpyderX07_ExecutionStrategyAgent.py` | 958 | Optimises order execution strategy: timing, limit vs. market, legging order |
| `SpyderX09_AlertManagerAgent.py` | 1,179 | Reviews and triages alerts; suppresses noise and escalates genuine issues |
| `SpyderX10_QuantModelsAgent.py` | 1,532 | Queries V-Series models for analytical insight and model calibration advice |
| `SpyderX11_SentimentAnalysisAgent.py` | 1,479 | Synthesises news and social sentiment into a directional bias score |
| `SpyderX12_SystemHealthAgent.py` | 1,235 | Diagnoses system health issues and recommends remediation actions |
| `SpyderX13_MarketAnalysisAgent.py` | 860 | Provides natural-language market analysis and macro context |
| `SpyderX14_OrchestratorAgent.py` | 1,101 | Coordinates multi-agent workflows; delegates sub-tasks to specialist agents |
| `SpyderX15_StrategyGeneratorAgent.py` | 487 | Generates novel strategy ideas via LLM reasoning over market context |
| `SpyderX16_MetaCoordinator.py` | 1,200 | Meta-coordinator: monitors all X-Series agents and arbitrates conflicting signals |

### SpyderY_AutoAgents — Autonomous 24/7 Agents (11 modules)

Persistent agents running continuously, driven by Ollama LLM.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderY00_BaseAutoAgent.py` | 780 | Abstract base class for all autonomous agents: event loop, heartbeat, state management |
| `SpyderY01_MarketSenseAgent.py` | 522 | Continuously monitors market conditions; emits regime-change and anomaly events |
| `SpyderY02_StrategyPilotAgent.py` | 512 | Autonomous strategy activator/deactivator based on real-time regime signals |
| `SpyderY03_RiskSentinelAgent.py` | 627 | 24/7 risk sentinel; watches for limit breaches and triggers circuit breakers |
| `SpyderY04_AlphaLearnerAgent.py` | 549 | Continuously learns from recent trades; updates alpha scores for strategies |
| `SpyderY05_ExecutionOptimizerAgent.py` | 553 | Optimises execution quality in real time: timing, venue, and order type selection |
| `SpyderY06_NewsSentinelAgent.py` | 556 | Monitors news feeds continuously; flags market-moving events for risk review |
| `SpyderY07_TradeJournalAgent.py` | 542 | Autonomous trade journaling: records rationale, outcome, and lessons learned |
| `SpyderY08_MetaOrchestratorAgent.py` | 619 | Meta-orchestrator for the Y-Series: monitors agent health, restarts failed agents |
| `SpyderY09_CodeReviewerAgent.py` | 467 | Reviews newly generated or modified code for style, security, and correctness |
| `SpyderY10_AgentScheduler.py` | 398 | Schedules Y-Series agent tasks: periodic runs, market-hours gating, priority queuing |

### SpyderZ_Communication — Inter-Module Messaging (7 modules)

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderZ01_ZeroMQIntegration.py` | 1,281 | ZeroMQ (0MQ) integration: PUB/SUB and REQ/REP patterns for inter-process messaging |
| `SpyderZ02_MessageProtocol.py` | 1,026 | Message protocol definitions: schemas, serialisation, versioning, and validation |
| `SpyderZ03_TradingCoordinator.py` | 1,537 | Coordinates trading decisions across processes via the messaging backbone |
| `SpyderZ04_VolatilityEngine.py` | 2,038 | Distributed volatility computation engine: offloads heavy IV calculations to workers |
| `SpyderZ05_OrderRouter.py` | 1,241 | Cross-process order router: fans out orders to broker with deduplication |
| `SpyderZ06_AutoHedger.py` | 1,240 | Automated delta hedger running as a separate supervised process |
| `SpyderZ07_MultiProcessManager.py` | 1,021 | Multi-process manager: spawns, monitors, and restarts worker processes |

---

## Data Flow

```
Massive API WebSocket → SpyderC_MarketData (normalization/validation)
                        ↓
                  SpyderF_Analysis (indicators, regime detection)
                        ↓
                  SpyderD_Strategies (signal generation)
                        ↓
                  SpyderE_Risk (validation, position sizing)
                        ↓
                  SpyderB_Broker/TradierClient (order execution via Tradier API)
```

## API Configuration

### Tradier API (Order Execution)
- **Sandbox**: `https://sandbox.tradier.com/v1`
- **Live**: `https://api.tradier.com/v1`
- **Auth**: Bearer token in `Authorization` header
- **Env vars**: `TRADIER_API_KEY`, `TRADIER_ACCOUNT_ID`, `TRADIER_ENVIRONMENT`

### Massive API (Market Data)
- **Client**: `SpyderC27_MassiveClient`, routed via `SpyderC29_DataProviderRouter`
- **Env vars**: `MASSIVE_API_KEY`
- **Use cases**: Real-time streaming options flow, Greeks, SPY equity data

## Coding Standards

### File Structure Template
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_ModuleName
Module: SpyderXNN_Purpose.py
Purpose: Brief description

Author: [Author Name]
Year Created: 2025
Last Updated: YYYY-MM-DD Time: HH:MM:SS
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_RETRIES = 3

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MyModule:
    """Google-style docstring with Args, Returns, Raises sections."""
    pass
```

### Naming Conventions
- **Modules**: `SpyderX_CategoryName` → `SpyderXNN_Purpose.py`
- **Classes**: `PascalCase` (e.g., `PositionManager`, `IronCondorStrategy`)
- **Functions/methods**: `snake_case` (e.g., `calculate_position_size`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private**: prefix with `_` (e.g., `_validate_config`)
- **Variables**: `snake_case` (e.g., `current_price`, `is_market_open`)

### Type Hints — Mandatory
All function signatures must include type hints for parameters and return values:
```python
def calculate_option_delta(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02
) -> float:
```

Use `Decimal` for precise financial calculations. Use `Optional[T]` for nullable params.

### Docstrings — Google Style
```python
def execute_order(order_data: dict) -> bool:
    """
    Execute a trading order through the Tradier API.

    Args:
        order_data: Dictionary with keys 'symbol', 'quantity', 'side', 'type'.

    Returns:
        True if the order was accepted, False otherwise.

    Raises:
        ConnectionError: If the Tradier API is unreachable.
        ValueError: If order_data is invalid.
    """
```

### Error Handling
- Use specific exception types, not bare `except:`
- Implement retry with exponential backoff for network calls
- Use custom exceptions: `SpyderException`, `TradingError`, `DataValidationError`
- Always log errors with `self.logger.error(...)` and include traceback for unexpected errors

### Design Patterns Used
- **Singleton**: `SpyderLogger`, system-wide config
- **Factory**: `StrategyFactory` for strategy creation
- **Builder**: `ComplexOrderBuilder` for multi-leg orders
- **Observer**: Event-driven via `SpyderI02_EventRouter` and `SpyderI06_AgentMessageBus`
- **Circuit Breaker**: `SpyderE16_CircuitBreakerProtocol` for cascading failure prevention

## Risk Management Principles

- **Capital preservation over profit maximization**
- Max 2% of capital per trade (`MAX_PORTFOLIO_RISK = 0.02`)
- Max 5% of capital at risk per day (`MAX_DAILY_RISK = 0.05`)
- Max 20% allocation per strategy (`MAX_STRATEGY_ALLOCATION = 0.20`)
- Greeks exposure limits enforced (delta, gamma, vega, theta)
- Multi-layer framework: pre-trade → position → strategy → portfolio level
- Circuit breakers halt trading on excessive drawdown or volatility

## Testing Requirements

- **Framework**: pytest with `SpyderTestBase` base class
- **Test files**: `test_SpyderXNN_ModuleName.py` in `SpyderT_Testing/`
- **Coverage target**: >80%
- **Pattern**: Arrange → Act → Assert
- Use `unittest.mock` for external dependencies (broker API, market data)
- All strategies must pass paper trading validation before live deployment
- Run `pytest SpyderT_Testing/` before every commit

## Security

- API keys and tokens in `.env` only — never in source code
- `.env` is in `.gitignore`
- Validate all external inputs and API responses
- Log trading decisions but never log credentials
- Use environment variable `TRADIER_ENVIRONMENT=sandbox|production` to control mode

## Common Commands

```bash
source .venv/bin/activate                          # Activate environment
python SpyderA_Core/SpyderA01_Main.py              # Start system
pytest SpyderT_Testing/                            # Run all tests
tail -f logs/spyder.log                            # Monitor logs
git checkout -b feature/your-feature-name          # New feature branch
```

## Key Files

- Entry point: `SpyderA_Core/SpyderA01_Main.py`
- Broker client: `SpyderB_Broker/SpyderB40_TradierClient.py`
- Risk manager: `SpyderE_Risk/SpyderE01_RiskManager.py`
- Logger: `SpyderU_Utilities/SpyderU01_Logger.py`
- Config: `config/config.py` and `.env`
- Agent message bus: `SpyderI_Integration/SpyderI06_AgentMessageBus.py`
