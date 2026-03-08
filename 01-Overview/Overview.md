2. SpyderProject/Overview.md

> **Last Updated:** March 8, 2026 — 01:46 UTC

```markdown
# Spyder Trading System - Project Overview

## System Introduction

**Spyder** is an advanced, autonomous algorithmic trading system specifically designed for trading SPY (S&P 500 ETF) options. Built with institutional-grade architecture, it combines sophisticated risk management, real-time market analysis, and automated execution through Interactive Brokers.

## Core Mission

To provide a reliable, scalable, and profitable automated trading platform that can:
- Execute complex options strategies with minimal human intervention
- Adapt to changing market conditions through machine learning
- Maintain strict risk controls to protect capital
- Provide comprehensive performance analytics and reporting

## System Architecture Philosophy

### Modular Design Principles

**Separation of Concerns**: Each module has a single, well-defined responsibility
- `SpyderA_Core`: System orchestration and lifecycle management
- `SpyderB_Broker`: All broker interactions isolated to one module
- `SpyderC_MarketData`: Clean data pipeline with validation
- `SpyderD_Strategies`: Strategy logic separated from execution
- `SpyderE_Risk`: Independent risk validation layer

**Loose Coupling**: Modules communicate through well-defined interfaces
- Event-driven architecture via `SpyderI_Integration`
- Standardized data types in `SpyderU_Utilities`
- Configuration-driven behavior
- Dependency injection where appropriate

**High Cohesion**: Related functionality grouped together
- Options-specific calculations in `SpyderN_OptionsAnalytics`
- All GUI components in `SpyderG_GUI`
- Machine learning models in `SpyderL_ML`
- Testing utilities in `SpyderT_Testing`

## Key System Capabilities

### Trading Operations
- **Multi-Strategy Execution**: Iron Condors, Credit Spreads, Straddles, Zero-DTE strategies
- **Real-Time Decision Making**: Sub-second market data processing and trade decisions
- **Risk-Adjusted Position Sizing**: Dynamic position sizing based on market conditions
- **Automated Order Management**: Smart order routing with partial fills handling

### Market Analysis
- **Technical Indicators**: 50+ indicators with custom implementations
- **Volatility Analysis**: Implied volatility surfaces and regime detection
- **Greeks Monitoring**: Real-time Greeks calculation and exposure tracking
- **Market Microstructure**: Order flow analysis and dark pool detection

### Risk Management
- **Multi-Layer Protection**: Position limits, portfolio VaR, drawdown controls
- **Real-Time Monitoring**: Continuous risk metric calculation
- **Circuit Breakers**: Automatic trading halt on unusual market conditions
- **Correlation Analysis**: Portfolio-level risk assessment

### Machine Learning
- **Predictive Models**: Random Forest, LSTM, and ensemble methods
- **Feature Engineering**: Automated feature selection and creation
- **Model Validation**: Comprehensive backtesting and walk-forward analysis
- **Adaptive Learning**: Models that adjust to market regime changes

## Technology Stack Overview

### Core Technologies
- **Python 3.13.3**: Primary development language
- **Interactive Brokers API**: Direct market access and execution
- **SQLite**: High-performance local data storage
- **PySide6**: Professional-grade GUI framework

### Data Processing
- **Pandas**: Advanced data manipulation and analysis
- **NumPy**: High-performance numerical computing
- **SciPy**: Scientific computing and statistical analysis
- **TA-Lib**: Technical analysis indicators

### Machine Learning
- **scikit-learn**: General machine learning algorithms
- **TensorFlow/PyTorch**: Deep learning models (optional modules)
- **Optuna**: Hyperparameter optimization
- **Backtrader**: Strategy backtesting framework

## System Environment

### Operating Environment
- **OS**: Ubuntu 25.04 64-bit
- **Desktop**: GNOME 48 with Wayland
- **Python Environment**: Virtual environment (.venv)
- **Time Zone**: America/New_York (synchronized with market hours)

### External Dependencies
- **Interactive Brokers Gateway**: Standalone application for API access
- **Market Data Subscriptions**: Real-time and historical data feeds
- **VPN Connection**: Secure connection to IBKR servers
- **System Monitoring**: Prometheus metrics and custom dashboards

## Development Approach

### Coding Standards
- **PEP 8 Compliance**: Consistent code formatting
- **Type Annotations**: Complete type hinting for better code reliability
- **Docstring Standards**: Google-style documentation
- **Error Handling**: Comprehensive exception handling with logging

### Testing Strategy
- **Unit Testing**: pytest framework with >80% code coverage
- **Integration Testing**: End-to-end system testing
- **Paper Trading**: All strategies tested in simulation before live deployment
- **Performance Testing**: Latency and throughput benchmarking

### Security Measures
- **Environment Variables**: All sensitive data in .env files
- **Input Validation**: Comprehensive validation of all external inputs
- **Audit Logging**: Complete audit trail of all trading decisions
- **Access Controls**: Role-based access to different system components

## Performance Characteristics

### Latency Requirements
- **Market Data Processing**: <100ms end-to-end
- **Strategy Decision Making**: <500ms from signal to order
- **Order Execution**: <1 second average order acknowledgment
- **Risk Checks**: <50ms for position validation

### Scalability Features
- **Multi-Threading**: Concurrent processing of market data and strategies
- **Asynchronous Operations**: Non-blocking I/O for external API calls
- **Memory Management**: Efficient data structures and garbage collection
- **Database Optimization**: Indexed queries and connection pooling

## Module Responsibilities

### Core System (A-E Series)
- **SpyderA_Core**: Main entry point, system orchestration, configuration management
- **SpyderB_Broker**: IBKR API integration, connection management, order execution
- **SpyderC_MarketData**: Real-time data feeds, historical data, data validation
- **SpyderD_Strategies**: Strategy implementations, backtesting, signal generation
- **SpyderE_Risk**: Risk management, position limits, drawdown controls

### Analysis & Intelligence (F, L, N, O, V Series)
- **SpyderF_Analysis**: Technical indicators, price action analysis, trend detection
- **SpyderL_ML**: Machine learning models, predictive analytics, model training
- **SpyderN_OptionsAnalytics**: Options pricing, Greeks calculation, volatility surfaces
- **SpyderO_TradingIntelligence**: Advanced analytics, market intelligence
- **SpyderV_QuantModels**: Quantitative models, statistical analysis, backtesting

### User Interface & Communication (G, J, K Series)
- **SpyderG_GUI**: PyQt6 interface, dashboards, visualization components
- **SpyderJ_Alerts**: Notification system, email alerts, desktop notifications
- **SpyderK_Reports**: Performance reporting, analytics dashboards, trade analysis

### Infrastructure & Support (H, I, M, P, R Series)
- **SpyderH_Storage**: Database management, data persistence, caching
- **SpyderI_Integration**: Third-party integrations, API management
- **SpyderM_Monitoring**: System health monitoring, performance metrics
- **SpyderP_PortfolioMgmt**: Portfolio optimization, allocation management
- **SpyderR_Runtime**: Runtime configuration, deployment management

### Utilities & Testing (Q, S, T, U, X, Z Series)
- **SpyderQ_Scripts**: Utility scripts, automation tools, system management
- **SpyderS_Signals**: Custom signal generation, market indicators
- **SpyderT_Testing**: Testing framework, unit tests, integration tests
- **SpyderU_Utilities**: Shared utilities, common functions, helpers
- **SpyderX_Agents**: AI agents, autonomous decision making
- **SpyderZ_Communication**: Inter-module communication, message passing

## Future Development Vision

### Short-Term Goals (3-6 months)
- Enhanced machine learning model integration
- Improved real-time performance dashboards
- Advanced options strategy implementations
- Expanded market data sources and validation

### Medium-Term Goals (6-12 months)
- Multi-asset class support (futures, forex)
- Cloud deployment capabilities with containerization
- Advanced portfolio optimization algorithms
- Institutional client interfaces and APIs

### Long-Term Vision (1-2 years)
- Distributed architecture for horizontal scalability
- AI-driven strategy generation and optimization
- Real-time collaboration and sharing features
- Comprehensive regulatory compliance framework

## Risk Management Philosophy

### Capital Preservation Principles
- **Position Limits**: Maximum exposure per strategy and overall portfolio
- **Stop-Loss Management**: Automated position closure on adverse price movements
- **Drawdown Controls**: System-wide trading halt on excessive losses
- **Correlation Monitoring**: Diversification requirements and limits

### Operational Risk Controls
- **System Redundancy**: Backup systems and failover mechanisms
- **Data Validation**: Multiple layers of data integrity verification
- **Order Validation**: Pre-trade risk checks and position limits
- **Audit Trails**: Complete logging of all system decisions and trades

---

This overview provides the foundational understanding of Spyder's architecture, capabilities, and development philosophy. Each module's detailed documentation can be found in their respective directories within the codebase.

---

## Complete Module Inventory

All production Python modules listed by series, with actual line counts verified March 8, 2026.

### SpyderA_Core — System Orchestration

The A-Series is the backbone of the entire system. It bootstraps all other series, owns the trading loop, and coordinates lifecycle across every subsystem.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderA01_Main.py` | 744 | Top-level entry point; parses CLI args, initialises all subsystems, hands off to engine |
| `SpyderA02_TradingEngine.py` | 1,840 | Core trading engine: drives the main loop, routes signals to strategies and risk layer |
| `SpyderA03_Configuration.py` | 1,350 | System-wide configuration management; loads `.env`, merges defaults, validates settings |
| `SpyderA04_Scheduler.py` | 1,546 | Task and cron scheduler; manages timed jobs (pre-market, intraday, EOD) |
| `SpyderA05_EventManager.py` | 1,195 | Central event bus; publishes and dispatches system-wide events |
| `SpyderA06_MasterController.py` | 1,394 | Master controller; coordinates start/stop/pause across all subsystem modules |
| `SpyderA08_FSeriesOrchestrator.py` | 1,237 | Orchestrates the F-Series analysis pipeline from data ingestion to signal output |

### SpyderB_Broker — Tradier API & Order Management

All broker interaction is isolated to the B-Series. No other series communicates directly with Tradier; they call B-Series APIs instead.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderB00_OrderTypes.py` | 838 | Order type enums, dataclasses, and constants used across the broker layer |
| `SpyderB02_OrderManager.py` | 1,480 | Full order lifecycle: creation, submission, fills, cancellations, and state tracking |
| `SpyderB03_PositionTracker.py` | 259 | Lightweight real-time position-tracking helper; maintains open-position state cache |
| `SpyderB04_AccountManager.py` | 1,203 | Retrieves and caches Tradier account info: balances, buying power, and margin |
| `SpyderB15_PrometheusMetrics.py` | 1,275 | Exposes broker-level Prometheus metrics (latency, fill rate, rejection rate) |
| `SpyderB26_PySideAsyncBridge.py` | 877 | Thread-safe bridge between the async broker I/O layer and PySide6 UI thread |
| `SpyderB30_SPYOptionsChainManager.py` | 945 | Manages and refreshes SPY options chain snapshots; handles strike filtering |
| `SpyderB40_TradierClient.py` | 1,917 | Primary Tradier REST/WebSocket client; handles auth, all API calls, retry logic |

### SpyderC_MarketData — Real-Time & Historical Data

The C-Series forms the data pipeline. Every price, quote, and news item consumed by the system flows through C-Series modules before reaching analysis or strategy layers.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderC00_MarketDataProtocol.py` | 128 | Abstract protocol/interface defining the contract for all market data providers |
| `SpyderC01_DataFeed.py` | 1,350 | Primary real-time tick data feed; normalises, validates, and distributes incoming data |
| `SpyderC02_HistoricalData.py` | 1,003 | Historical OHLCV data retrieval, storage, and aggregation |
| `SpyderC03_OptionChain.py` | 1,092 | Options chain snapshot management; strike/expiry filtering for SPY |
| `SpyderC04_MarketInternals.py` | 881 | Tracks market breadth, advance/decline, new highs/lows, TICK, TRIN |
| `SpyderC05_VolumeProfile.py` | 917 | Intraday and session volume profile (VPOC, HVN, LVN) calculations |
| `SpyderC06_DataValidator.py` | 1,269 | Multi-layer validation of all incoming market data; detects stale or anomalous ticks |
| `SpyderC07_OPRAFeed.py` | 1,466 | OPRA-compliant options data feed; processes high-volume options quote streams |
| `SpyderC08_SPYFeed.py` | 831 | SPY-specific equity feed; handles split-adjusted prices and extended hours |
| `SpyderC09_NewsManager.py` | 1,051 | News headline collection and distribution; interfaces with financial news APIs |
| `SpyderC10_VIXAnalyzer.py` | 1,483 | VIX index analysis: term structure, regime classification, and VIX-based signals |
| `SpyderC11_FuturesBasis.py` | 1,435 | ES/SPY futures basis tracking; roll-adjust calculations; cash-futures arbitrage alerts |
| `SpyderC12_DarkPoolFlow.py` | 786 | Tracks and aggregates reported dark pool prints and off-exchange volume |
| `SpyderC13_IndexComponents.py` | 1,051 | S&P 500 constituent data management; sector weights, rebalance events |
| `SpyderC14_UltraLowLatencyFeed.py` | 839 | Ultra-low-latency tick feed with lock-free ring buffer; minimum-copy path |
| `SpyderC15_MicrostructureAnalyzer.py` | 1,296 | Intraday market microstructure: bid-ask spread, queue depth, order toxicity |
| `SpyderC16_MarketDataCache.py` | 918 | In-memory LRU cache for frequently accessed market data; TTL eviction |
| `SpyderC17_MarketConfigManager.py` | 1,105 | Dynamic market configuration: session times, holiday overrides, circuit-breaker thresholds |
| `SpyderC18_SKEWCalculator.py` | 1,319 | CBOE SKEW index replication; real-time skew surface construction |
| `SpyderC19_AfterHoursDataManager.py` | 836 | Pre/post-market data collection, gap detection, and overnight risk assessment |
| `SpyderC20_MarketDataHub.py` | 908 | Central data hub/aggregator; fan-out architecture routing data to all subscribers |
| `SpyderC21_MarketDataFeed.py` | 687 | Secondary market data feed; fallback provider and redundancy layer |
| `SpyderC22_FactorDataProvider.py` | 1,271 | Factor data (momentum, value, quality, size) for ML feature pipelines |
| `SpyderC23_RealTimeDataOptimizer.py` | 1,227 | Optimises real-time data throughput: batching, compression, priority queuing |
| `SpyderC24_ModelDataPipeline.py` | 1,457 | End-to-end data pipeline preparing market data for ML model consumption |
| `SpyderC26_DatabentooClient.py` | 1,389 | Databento REST/streaming client; supports MBO, MBP, TBBO, OHLCV schemas |
| `SpyderC30_OrderFlowAnalyzer.py` | 1,745 | Real-time order flow analysis: delta, cumulative delta, imbalance, absorption |
| `SpyderC35_SentimentAnalyzer.py` | 1,472 | Multi-source sentiment analysis: news, social, options flow, put/call ratios |

### SpyderD_Strategies — Strategy Implementations

Every options strategy implemented in Spyder lives in the D-Series. All strategies inherit from `SpyderD01_BaseStrategy` and communicate with the risk layer before any order is placed.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderD00_StrategyConstants.py` | 331 | Strategy-wide constants, enums, and shared configuration values |
| `SpyderD01_BaseStrategy.py` | 1,078 | Abstract base class; defines signal, entry, exit, and sizing interfaces |
| `SpyderD02_IronCondor.py` | 912 | Iron Condor: sell OTM call + put spreads; premium collection in range-bound market |
| `SpyderD03_CreditSpread.py` | 1,031 | Vertical credit spread (bull put or bear call); defined-risk premium selling |
| `SpyderD04_ZeroDTE.py` | 1,099 | Zero-days-to-expiry: ultra-short-term intraday premium capture |
| `SpyderD05_Straddle.py` | 1,148 | Straddle: simultaneous ATM call and put; profits from large moves either direction |
| `SpyderD08_OpeningRangeBreakout.py` | 1,182 | Opening Range Breakout: trades breakouts from the first 15-/30-minute session range |
| `SpyderD09_GreeksBasedStrategy.py` | 1,475 | Greeks-driven strategy selection; dynamically targets specific delta/theta/vega profiles |
| `SpyderD10_IronButterfly.py` | 902 | Iron Butterfly: ATM short straddle + OTM wings; maximum premium at target price |
| `SpyderD11_SpecializedZeroDTE.py` | 1,294 | Enhanced Zero-DTE with adaptive strike selection, gamma controls, and time filters |
| `SpyderD12_RSIMeanReversion.py` | 1,028 | RSI-triggered mean-reversion; fades extreme RSI readings with options overlays |
| `SpyderD13_MACrossover.py` | 933 | Moving average crossover with options-based directional expression |
| `SpyderD14_CalendarSpread.py` | 1,211 | Calendar spread: sell near-term, buy far-term same strike; benefits from time decay |
| `SpyderD15_StraddleStrangle.py` | 1,382 | Combined straddle and strangle logic with dynamic strike-width optimisation |
| `SpyderD16_RatioSpreads.py` | 1,465 | Ratio spreads (1×2, 1×3): sell more options than bought; complex risk profile |
| `SpyderD17_DiagonalSpread.py` | 1,363 | Diagonal spread: different strikes AND expirations; blended theta/directional |
| `SpyderD18_EvolvedCreditSpread.py` | 1,433 | ML-enhanced credit spread with adaptive strike and DTE selection |
| `SpyderD19_JadeLizard.py` | 1,209 | Jade Lizard: short put + short call spread; no upside risk when structured correctly |
| `SpyderD20_VerticalSpreadOptimizer.py` | 847 | Optimises vertical spread parameters (width, delta, DTE) across all expirations |
| `SpyderD21_DoubleCalendar.py` | 1,408 | Double Calendar: two calendar spreads at different strikes; wider profit zone |
| `SpyderD22_AdaptiveVolatility.py` | 1,111 | Adapts strategy selection and sizing to the detected volatility regime in real time |
| `SpyderD25_UnifiedCreditSpreadEngine.py` | 1,523 | Unified engine consolidating all credit spread variants under one scoring framework |
| `SpyderD26_GammaScalper.py` | 1,155 | Gamma scalping: delta-neutral long-gamma adjusted by dynamic delta hedges |
| `SpyderD27_EarningsStrategy.py` | 1,289 | Earnings event strategy; positions around implied move ahead of announcements |
| `SpyderD28_VIXHedging.py` | 1,120 | VIX-based portfolio hedge; activates tail-risk protection when VIX spikes |
| `SpyderD30_RegimeGatedSelector.py` | 1,223 | Regime-gated selector; maps detected market regime to best-fit strategy |
| `SpyderD31_StrategyOrchestrator.py` | 2,075 | Coordinates concurrent strategies and manages capital allocation between them |
| `SpyderD32_MultiLegStrategyCoordinator.py` | 1,881 | Coordinates complex multi-leg orders; prevents leg-risk overlap |
| `SpyderD33_RenaissanceMeanReversion.py` | 786 | Renaissance-inspired statistical mean-reversion using Ornstein-Uhlenbeck process |

### SpyderE_Risk — Risk Management

The E-Series is the guardian of capital. Every order proposed by D-Series must pass through E-Series validation before execution. No trade bypasses this layer.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderE01_RiskManager.py` | 861 | Core entry point for all pre-trade and post-trade risk validation |
| `SpyderE02_PositionSizer.py` | 1,053 | Dynamic position sizing based on volatility, account equity, and risk budget |
| `SpyderE03_StopLossManager.py` | 1,473 | Stop-loss orchestration: fixed, trailing, time-based, and Greeks-based stops |
| `SpyderE04_DrawdownControl.py` | 938 | Monitors intraday and rolling drawdown; escalates alerts and halts trading at limits |
| `SpyderE05_AutomaticRebalancer.py` | 769 | Auto-rebalances portfolio allocations when strategies drift beyond tolerance bands |
| `SpyderE06_RiskMetrics.py` | 1,215 | Computes VaR, CVaR, Sharpe, Sortino, max drawdown, and other risk KPIs |
| `SpyderE07_ProbabilisticSharpe.py` | 747 | Probabilistic Sharpe Ratio with bootstrapped confidence intervals |
| `SpyderE08_PositionGroupValidator.py` | 1,177 | Validates correlated position groups; enforces combined Greeks and notional limits |
| `SpyderE09_VolatilityRiskManager.py` | 1,110 | Volatility-specific risk controls: vega limits, IV crush protection, regime sizing |
| `SpyderE10_CorrelationRiskManager.py` | 1,947 | Cross-position correlation analysis; prevents over-concentration in correlated bets |
| `SpyderE11_MaxLossProtection.py` | 954 | Hard maximum-loss circuit; liquidates positions when P&L breaches configured limit |
| `SpyderE12_PortfolioVaR.py` | 1,488 | Portfolio-level VaR via historical simulation, Monte Carlo, and parametric methods |
| `SpyderE13_DayProfitTarget.py` | 2,263 | Daily profit target management; scales back risk once target is achieved |
| `SpyderE14_KellyPositionSizer.py` | 755 | Kelly Criterion position sizing with fractional Kelly for conservative application |
| `SpyderE15_GreekLimitsManager.py` | 1,156 | Enforces portfolio-level Greeks exposure limits (delta, gamma, vega, theta, rho) |
| `SpyderE16_CircuitBreakerProtocol.py` | 470 | Circuit breaker: halts all new orders on trigger conditions |
| `SpyderE17_RealTimeStressTesting.py` | 1,543 | Continuous intraday stress testing against historical shock scenarios |
| `SpyderE18_FSeriesRiskIntegrator.py` | 1,374 | Integrates F-Series analytics signals into risk validation pipeline |
| `SpyderE19_UnifiedRiskCoordinator.py` | 1,223 | Fans risk checks out to all E-Series modules and aggregates verdicts |
| `SpyderE20_FrustrationAnalyzer.py` | 1,632 | Behavioural analysis; detects over-trading patterns and revenge-trade conditions |
| `SpyderE21_HMMRegimeDetector.py` | 1,053 | HMM regime detector embedded in the risk layer for defensive mode switching |
| `SpyderE22_KernelRegression.py` | 865 | Non-parametric trend and volatility estimation via kernel regression |
| `SpyderE23_PortfolioOptimizer.py` | 2,020 | Mean-variance and Black-Litterman optimisation; efficient frontier computation |

### SpyderF_Analysis — Technical & Market Analysis

The F-Series transforms raw market data into actionable analytical signals. Its output feeds both the strategy layer (D-Series) and the risk layer (E-Series).

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderF01_Indicators.py` | 875 | Core technical indicators: RSI, MACD, Bollinger Bands, ATR, EMA, etc. |
| `SpyderF02_PriceAction.py` | 892 | Price action patterns: candlestick formations, pin bars, engulfing, inside bars |
| `SpyderF03_SupportResistance.py` | 810 | Automated S/R detection via swing pivots and volume clusters |
| `SpyderF04_VolatilityAnalysis.py` | 932 | Historical and realised volatility: HV cone, IV rank, IV percentile |
| `SpyderF05_TrendDetection.py` | 799 | Multi-timeframe trend detection and classification (bull/bear/neutral) |
| `SpyderF06_GreeksCalculator.py` | 998 | BSM-based Greeks computation (delta, gamma, theta, vega, rho) |
| `SpyderF07_GapAnalyzer.py` | 785 | Gap detection, classification (common/breakaway/exhaustion), gap-fill probability |
| `SpyderF08_VolatilityRegime.py` | 1,032 | Volatility regime classification: low/medium/high/extreme via multi-signal consensus |
| `SpyderF09_EntryFilters.py` | 1,113 | Pre-entry signal filters: time-of-day, spread quality, volume, regime, news guards |
| `SpyderF10_MarketRegimeDetector.py` | 1,458 | Composite regime detector combining breadth, momentum, and volatility signals |
| `SpyderF11_GreeksAggregator.py` | 1,064 | Aggregates position-level Greeks to portfolio-level exposure with P&L attribution |
| `SpyderF12_AdvancedBacktestingEngine.py` | 1,898 | Vectorised backtesting engine with realistic slippage, commissions, and fills |
| `SpyderF13_ModelValidation.py` | 1,477 | Walk-forward validation, out-of-sample testing, overfitting detection for ML models |
| `SpyderF14_MarketMicrostructure.py` | 1,567 | Microstructure analytics: trade clustering, VPIN, order-flow imbalance |
| `SpyderF16_RealTimeAnalytics.py` | 1,699 | Streaming real-time analytics pipeline feeding dashboards and strategy signals |
| `SpyderF17_UnifiedPerformanceEngine.py` | 1,608 | Unified engine computing all performance metrics (Sharpe, Calmar, win rate, edge) |
| `SpyderF18_MaxPainCalculator.py` | 1,101 | Options max pain from open interest data; identifies key gravitational strikes |
| `SpyderF19_AnchoredVWAP.py` | 1,218 | Anchored VWAP with user-defined anchor events; VWAP bands and deviation studies |
| `SpyderF20_Indicators.py` | 393 | Supplementary indicator set; extended library of less-common indicators |
| `SpyderF20_MLPrediction.py` | 1,398 | ML-driven price and volatility prediction integrated into the F-Series pipeline |
| `SpyderF21_RenaissanceIndicators.py` | 841 | Renaissance Technologies-inspired indicators: eigenportfolio momentum, Kalman filters |

### SpyderG_GUI — PySide6 Graphical Interface

All user-facing UI components live in the G-Series. Built entirely with PySide6 (Qt6, LGPL). No AGPL widgets are used.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderG00_ApplicationManager.py` | 474 | QApplication setup, theme initialisation, unhandled exception hooks |
| `SpyderG01_MainWindow.py` | 114 | Main window shell; docking layout, menu bar, status bar |
| `SpyderG02_GUIEntry.py` | 131 | GUI entry point; launches in standalone or trading-engine-embedded mode |
| `SpyderG03_OptionChainWidget.py` | 231 | Options chain table widget with strike filtering, IV display, and Greeks columns |
| `SpyderG04_ChartWidget.py` | 1,639 | Primary OHLCV candlestick chart widget with indicator overlays (Qt/Matplotlib) |
| `SpyderG05_TradingDashboard.py` | 4,486 | Main trading dashboard: positions, P&L, Greeks, orders, market status |
| `SpyderG06_DashboardData.py` | 540 | Data model for the dashboard; normalises and refreshes display data |
| `SpyderG07_PrometheusMetricsDisplay.py` | 658 | Prometheus metrics panel: latency, throughput, error rates |
| `SpyderG08_DashboardDataBridge.py` | 751 | Thread-safe bridge connecting data layer to PySide6 dashboard widgets |
| `SpyderG09_RiskParametersDialog.py` | 1,205 | Risk parameters configuration dialog: delta limits, VaR, daily loss caps |
| `SpyderG10_CustomMetricsIntegration.py` | 658 | Integrates custom metrics (DIX, GEX, SKEW) into the dashboard display |
| `SpyderG11_SkewMonitorDialog.py` | 1,378 | SKEW index monitor dialog with real-time chart and historical percentile display |
| `SpyderG12_SignalInfoDialog.py` | 523 | Signal information popup: source, confidence, Greeks impact, recommended action |
| `SpyderG13_EnhancedWidgets.py` | 754 | Enhanced UI widgets: gauges, sparklines, heat maps, traffic lights |
| `SpyderG14_Dashboard.py` | 131 | Lightweight legacy/stub dashboard for backward compatibility |
| `SpyderG15_ConnectAPIStatus.py` | 793 | API connectivity status panel: live/sandbox mode, latency, connection health |
| `SpyderG16_CircuitBreakerMonitor.py` | 324 | Circuit breaker status monitor; shows active breakers and breach history |
| `SpyderG29_ChartWidgetPlotly.py` | 863 | Plotly-based interactive chart widget embedded via QWebEngineView |
| `SpyderG30_PlotlyDataBridge.py` | 562 | Converts internal market data structures to Plotly-compatible JSON/trace format |
| `SpyderG31_PlotlyTemplates.py` | 752 | Plotly chart templates and themes (dark mode, branded colours) |
| `SpyderG99_GUILogHandler.py` | 290 | Streams SpyderLogger output to an in-dashboard log console widget |

### SpyderH_Storage — SQLite Persistence & Caching

All persistent storage goes through H-Series. Direct database access from other series is prohibited; they call H-Series APIs.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderH01_DataAccessLayer.py` | 1,080 | Data access layer (DAL): parameterised SQL, connection pooling, transactions |
| `SpyderH02_DatabaseManager.py` | 903 | SQLite database manager: schema init, migrations, backup, integrity checks |
| `SpyderH03_MarketDataCache.py` | 696 | Market data cache: in-process + SQLite-backed caching with TTL eviction |
| `SpyderH04_TradeRepository.py` | 780 | Trade history repository: CRUD for trades, fills, positions, and audit records |
| `SpyderH07_PerformanceAnalytics.py` | 854 | Performance analytics storage: persists Sharpe, drawdown, and strategy metrics |

### SpyderI_Integration — Event Routing & Diagnostics

The I-Series is the nervous system: events flow through it, configs are managed by it, and all cross-module diagnostics run through it.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderI01_IntegrationHub.py` | 834 | Central integration hub: registers all modules, manages service discovery |
| `SpyderI02_EventRouter.py` | 1,401 | Event routing: publish-subscribe, priority queues, async and sync dispatch |
| `SpyderI03_ConfigManager.py` | 1,442 | Runtime config manager: hot-reload, env-override, schema validation |
| `SpyderI04_DiagnosticsEngine_Analyzers.py` | 317 | Diagnostic analyser plugins: interprets collected metrics for anomaly detection |
| `SpyderI04_DiagnosticsEngine_Core.py` | 602 | Diagnostics engine core: orchestrates data collection, analysis, and reporting |
| `SpyderI06_AgentMessageBus.py` | 844 | Agent message bus: routes messages between X-Series and Y-Series AI agents |
| `SpyderI07_SyntaxValidator.py` | 826 | Syntax and schema validator for dynamically loaded configs and agent-generated code |
| `SpyderI08_DiagnosticsEngine_DataCollector.py` | 666 | Gathers CPU, memory, latency, and trade metrics for diagnostics |
| `SpyderI09_DiagnosticsEngine_HealthChecks.py` | 719 | Liveness and readiness probes for all system components |
| `SpyderI10_DiagnosticsEngine_Types.py` | 442 | Type definitions for all diagnostics data structures and enums |
| `SpyderI11_DiagnosticsEngine_Utils.py` | 686 | Utility functions shared across all DiagnosticsEngine sub-modules |

### SpyderJ_Alerts — Notifications

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderJ01_AlertManager.py` | 798 | Alert routing, deduplication, priority, and escalation logic |
| `SpyderJ02_EmailNotifier.py` | 829 | Email notifications via SMTP; HTML-formatted trade alerts and daily summaries |
| `SpyderJ04_DesktopNotifier.py` | 785 | Desktop notification integration (libnotify/D-Bus on Linux) |
| `SpyderJ05_TelegramBot.py` | 909 | Telegram bot: trade alerts, account updates, and risk warnings via Bot API |

### SpyderK_Reports — Performance Reporting

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderK01_ReportGenerator.py` | 81 | Abstract base report generator interface |
| `SpyderK02_DailyTradingReport.py` | 1,535 | Comprehensive daily P&L report: trade log, strategy breakdown, Greeks |
| `SpyderK03_PerformanceDashboard.py` | 945 | Performance summary: equity curve, drawdown, Sharpe, win rate |
| `SpyderK04_ExecutionAnalytics.py` | 1,103 | Execution quality: slippage, fill rate, market impact, NBBO analysis |
| `SpyderK05_RiskReport.py` | 806 | Daily risk report: VaR, stress test results, Greeks exposure, limit utilisation |
| `SpyderK06_PortfolioAnalytics.py` | 1,471 | Portfolio analytics: sector exposure, correlation matrix, return attribution |
| `SpyderK07_StrategyComparison.py` | 896 | Side-by-side strategy comparison: returns, risk-adjusted metrics, win rates |
| `SpyderK08_MLPerformanceReport.py` | 1,643 | ML model report: prediction accuracy, feature importance, drift detection |
| `SpyderK09_RegulatoryReports.py` | 1,436 | Regulatory/compliance reports: trade confirmations, position limits, audit logs |
| `SpyderK10_RealTimePerformanceAnalytics.py` | 1,108 | Streaming real-time performance analytics fed to GUI dashboards |
| `SpyderK11_UnifiedSharpeDashboard.py` | 971 | Unified Sharpe dashboard: rolling, annualised, and probabilistic Sharpe views |
| `SpyderK12_InstitutionalTearSheet.py` | 786 | Institutional-style tear sheet: full strategy fact sheet with risk metrics |

### SpyderL_ML — Machine Learning

The L-Series houses all ML model training, inference, and lifecycle management. Models trained here are deployed into both the F-Series analytics pipeline and the D-Series strategies.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderL01_MLPredictor.py` | 1,075 | Core ML prediction engine; wraps trained models for real-time inference |
| `SpyderL07_PaperTradeLearner.py` | 1,700 | Learns from paper trading results; updates model priors without live capital risk |
| `SpyderL08_EntryOptimizer.py` | 1,712 | ML-driven entry timing optimiser; selects optimal strike, DTE, and entry price |
| `SpyderL09_UnifiedRegimeEngine.py` | 2,069 | Unified ML regime classification combining HMM, clustering, and ensemble models |
| `SpyderL10_FeatureEngineering.py` | 1,327 | Automated feature engineering: technical, microstructure, flow, and sentiment |
| `SpyderL11_MLModelManager.py` | 1,154 | ML model lifecycle: versioning, training, evaluation, deployment, rollback |
| `SpyderL12_RandomForestEnsemble.py` | 765 | Random forest ensemble for regime classification and direction probability |
| `SpyderL13_LSTMPricer.py` | 753 | LSTM deep learning model for options pricing and IV surface prediction |
| `SpyderL14_RealTimePredictor.py` | 842 | Low-latency real-time inference wrapper for deployed ML models |
| `SpyderL15_MomentPredictor.py` | 763 | ML-based short-term price momentum scoring |
| `SpyderL16_OptionsAdjustmentRL.py` | 1,579 | Reinforcement learning agent for adaptive options position adjustment |
| `SpyderL17_FederatedLearning.py` | 1,705 | Privacy-preserving federated learning framework for multi-strategy model training |
| `SpyderL18_EnhancedMLIntegration.py` | 1,232 | Enhanced integration layer connecting ML models to strategy and risk subsystems |
| `SpyderL19_RLTrainingPipeline.py` | 789 | RL training pipeline: environment, rewards, episode management |

### SpyderM_Monitoring — System Health & Metrics

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderM01_SystemMonitor.py` | 966 | System health: CPU, memory, disk, network, and process metrics via psutil |
| `SpyderM03_AIAgentMonitor.py` | 873 | AI agent health: response time, error rate, task completion rate |
| `SpyderM04_TradingMetrics.py` | 1,123 | Real-time P&L, fill rate, order rate, and latency histograms |
| `SpyderM05_TransactionCostAnalysis.py` | 1,378 | TCA: commissions, slippage, and market impact breakdown |
| `SpyderM06_HMMRegimeDetector.py` | 1,421 | Standalone HMM regime detector for system-level market state monitoring |
| `SpyderM07_MigrationMonitor.py` | 374 | Monitors data migration jobs (Polygon.io → Databento) for completeness |

### SpyderN_OptionsAnalytics — Options Pricing & Greeks

The N-Series is the options mathematics engine. It provides pricing, Greeks, and volatility surface data consumed by strategies, risk management, and signal generation.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderN01_OptionsPricer.py` | 1,283 | Options pricing: Black-Scholes-Merton, binomial tree, and American option models |
| `SpyderN02_ImpliedVolatilityEngine.py` | 1,342 | IV calculation via Newton-Raphson and bisection; handles surfaces and smiles |
| `SpyderN03_OptionsChainManager.py` | 1,285 | Options chain normalisation, gap filling, and chain-level analytics |
| `SpyderN04_OptionsGreeksCalculator.py` | 1,669 | High-precision Greeks (delta, gamma, theta, vega, rho, charm, vanna, volga) |
| `SpyderN05_OptionsExpirationManager.py` | 1,173 | Expiration cycle management: DTE tracking, roll scheduling, pin-risk alerts |
| `SpyderN06_VolatilitySurfaceBuilder.py` | 1,124 | Constructs the full 3-D IV surface from options chain data |
| `SpyderN07_OptionsFlowTracker.py` | 1,251 | Tracks unusual options flow: sweep detection, block prints, OI changes |
| `SpyderN08_VolatilitySurface.py` | 1,409 | Volatility surface model: SVI, SABR, and spline fits for full term structure |
| `SpyderN09_GammaExposure.py` | 1,295 | Net Gamma Exposure (GEX): dealer hedging pressure and GEX flip levels |
| `SpyderN10_OptionsFlowAnalyzer.py` | 637 | Options flow directional signals: bull/bear skew, premium paid/received |
| `SpyderN11_OptionsGreeksFlow.py` | 1,213 | Greeks-adjusted flow: delta/vega-weighted order flow imbalance |
| `SpyderN12_VolatilitySurfaceAI.py` | 1,288 | AI-enhanced volatility surface: ML corrections to model prices |
| `SpyderN13_MarketImpactModel.py` | 1,276 | Market impact model: estimates price impact of options trades |

### SpyderO_TradingIntelligence — Advanced Analytics

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderO01_CoreTechnicalIndicators.py` | 1,338 | Expanded institutional-grade technical indicator library |
| `SpyderO02_TradingOpportunityScanner.py` | 1,328 | Scans all instruments/expirations for high-probability opportunities |
| `SpyderO03_StrategyOptimizers.py` | 1,955 | Strategy parameter optimisation via grid search, Optuna, and genetic algorithms |

### SpyderP_PortfolioMgmt — Portfolio Management

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderP01_PortfolioManager.py` | 2,234 | Top-level portfolio manager: tracks all open positions and portfolio Greeks |
| `SpyderP02_AllocationOptimizer.py` | 2,263 | Allocation optimisation: mean-variance, risk-parity, and Black-Litterman |
| `SpyderP03_CorrelationAnalyzer.py` | 786 | Cross-strategy and cross-position correlation monitoring and reporting |
| `SpyderP04_CapitalAllocator.py` | 1,606 | Dynamic capital allocation: adjusts strategy budgets by performance |
| `SpyderP05_MultiStrategyAllocator.py` | 1,389 | Multi-strategy capital allocation with regime-conditional weighting |
| `SpyderP06_StrategyRotation.py` | 1,347 | Strategy rotation: schedules activation/deactivation by regime |
| `SpyderP07_RenaissancePositionSizer.py` | 724 | Renaissance-inspired statistical position sizing via eigenportfolio decomposition |

### SpyderQ_Scripts — Utility & Launcher Scripts

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderQ14_MainLauncher.py` | 431 | Main launcher: selects live/paper/backtest mode and starts all subsystems |
| `SpyderQ80_VerifyDashboardIntegration.py` | 443 | Verifies dashboard integration: checks data bridges and widget connections |
| `SpyderQ90_SystemUtilities.py` | 888 | General utilities: process management, env checks, log rotation |
| `SpyderQ92_DiagnosticsUtilities.py` | 1,118 | Diagnostics CLI: snapshot, health-dump, and module-status commands |
| `SpyderQ93_RunPaper.py` | 436 | One-command paper trading launcher with pre-flight sanity checks |
| `launch_dashboard_with_proactive_connections.py` | 584 | Launcher that pre-warms API connections before opening the dashboard |
| `launch_spyder_dashboard_direct.py` | 657 | Direct dashboard launcher bypassing the trading engine (display-only) |
| `launch_spyder_working_dashboard.py` | 545 | Known-working dashboard launcher with fallback data stubs |
| `validate_configuration.py` | 445 | Validates all configuration keys, types, and required fields against schema |
| `validate_env.py` | 346 | Validates `.env` file: required vars, non-empty values, format |
| `test_gui_logging.py` | 166 | Tests GUI log handler by emitting messages at all severity levels |

### SpyderR_Runtime — Runtime Execution Engines

The R-Series provides the three runtime modes: backtest, paper, and live. All share the same strategy and risk interfaces, enabling seamless transition from backtest to live.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderR01_BacktestEngine.py` | 577 | Basic event-driven backtest engine with OHLCV data replay |
| `SpyderR02_PaperEngine.py` | 941 | Paper trading engine: simulates order execution against live market data |
| `SpyderR03_PaperMonitor.py` | 855 | Monitors paper trading session: tracks virtual P&L and position state |
| `SpyderR04_LiveEngine.py` | 823 | Live trading engine: routes signals to broker, manages real order flow |
| `SpyderR05_WorkingBridge.py` | 512 | Bridge between runtime engines and the data/broker layers |
| `SpyderR06_PaperTradingHarness.py` | 1,008 | Complete paper trading harness for strategy end-to-end validation |
| `SpyderR07_LiveDashboard.py` | 577 | Lightweight live-trading status dashboard with real-time P&L and risk |
| `SpyderR08_EnhancedBacktestEngine.py` | 1,482 | Enhanced backtest engine: realistic fills, commission schedules, margin simulation |
| `SpyderR09_ProductionDeploymentManager.py` | 1,823 | Production deployment: health checks, rollout, rollback, and monitoring hooks |
| `SpyderR10_DistributedBacktester.py` | 781 | Distributed backtesting: parallelises walk-forward runs across CPU cores |

### SpyderS_Signals — Custom Signal Generation

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderS01_DIXCalculator.py` | 703 | DIX (Dark Index) calculation: ratio of dark pool volume to total volume |
| `SpyderS02_DIXScheduler.py` | 898 | Schedules DIX data collection and caching; manages update frequency |
| `SpyderS03_BlackSwanIndicator.py` | 581 | Black Swan indicator: multi-signal composite flagging extreme tail-risk conditions |
| `SpyderS04_BlackSwanScheduler.py` | 1,287 | Scheduler for Black Swan indicator; manages data polling and alert emission |
| `SpyderS05_GEXDEXCalculator.py` | 68 | GEX/DEX (Gamma/Delta Exposure) stub calculator; placeholder for live integration |
| `SpyderS06_SKEWCalculator.py` | 1,265 | CBOE SKEW replication from options chain data; real-time and daily computation |
| `SpyderS07_CustomMetricsOrchestrator.py` | 786 | Orchestrates DIX, GEX, SKEW, Black Swan into a unified signal feed |

### SpyderT_Testing — Test Framework & Test Suites (80+ modules)

The T-Series is the complete pytest test suite. All 9,235+ tests run against mocked external dependencies. Target coverage: >80%.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderT01_UnitTestFramework.py` | 1,908 | Core framework: `SpyderTestBase`, fixtures, mock data providers, helpers |
| `SpyderT02_BrokerTestSuite.py` | 919 | Broker tests: order types, account management, Tradier mock |
| `SpyderT03_BlackSwanValidator.py` | 1,209 | Validates Black Swan indicator against historical tail-risk events |
| `SpyderT09_TestDashboard.py` | 3,372 | Interactive test dashboard for manual QA of GUI components |
| `SpyderT40_TradierClient_Test.py` | 429 | Tradier API client tests: auth, orders, quotes, error handling |
| `SpyderT42_Integration_Test.py` | 351 | Live integration tests (sandbox credentials required; skipped in CI) |
| `SpyderT43_OrderManager_Test.py` | 806 | Order manager: lifecycle states, partial fills, cancellations |
| `SpyderT44_DatabentoClient_Test.py` | 547 | Databento client: schema validation, streaming, historical requests |
| `SpyderT46_RiskManager_Test.py` | 485 | Risk manager: position sizing, limits, circuit breaker triggers |
| `SpyderT47_StrategyUnit_Test.py` | 469 | Strategy units: signal generation, entry/exit logic for all D-Series |
| `SpyderT55_PaperTradingHarness_Test.py` | 750 | Paper trading harness: end-to-end scenario validation |
| `SpyderT56_StrategyTests.py` | 706 | Comprehensive strategy tests covering all strategy classes |
| `SpyderT57_OptionsAnalyticsTests.py` | 575 | Options analytics: pricing, Greeks, IV surface accuracy |
| `SpyderT58_RiskManagementTests.py` | 706 | Risk management: VaR, drawdown, Greeks limits |
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
| *(+ 60 additional test modules covering all U-Series and integration scenarios)* | | |

### SpyderU_Utilities — Core Utilities

The U-Series provides the foundational building blocks used by every other series. These modules are non-optional dependencies for the rest of the system.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderU01_Logger.py` | 103 | `SpyderLogger` singleton: thread-safe structured logging with rotating file handler |
| `SpyderU02_ErrorHandler.py` | 919 | `SpyderErrorHandler`: centralised exception handling, retry logic, alerting hooks |
| `SpyderU03_DateTimeUtils.py` | 1,856 | Comprehensive date/time utilities: market hours, session classification, timezone handling |
| `SpyderU04_Encryption.py` | 159 | AES encryption utilities for protecting sensitive data at rest |
| `SpyderU05_NetworkUtils.py` | 545 | Network utilities: connection checks, retry-with-backoff, SSL helpers |
| `SpyderU06_MathUtils.py` | 787 | Mathematical utilities: rolling statistics, interpolation, normalisation |
| `SpyderU07_Constants.py` | 790 | System-wide constants: tick sizes, lot sizes, sector classifications, API endpoints |
| `SpyderU08_Validators.py` | 917 | Input validators: symbol, price, quantity, date, and config value validators |
| `SpyderU09_DataTypes.py` | 742 | Custom typed dataclasses: `Quote`, `Trade`, `Greeks`, `Position` |
| `SpyderU10_TradingCalendar.py` | 917 | NYSE trading calendar: holiday schedule, session times, early close detection |
| `SpyderU11_FeatureFlags.py` | 745 | Feature flag system: runtime enable/disable of features without code deployment |
| `SpyderU12_AgentIntegration.py` | 70 | Thin utility layer bridging X/Y agent calls with the message bus |
| `SpyderU13_TechnicalIndicators.py` | 806 | Additional technical indicators library (extends F01) |
| `SpyderU14_OptionStrategies.py` | 863 | Options strategy utilities: payoff, breakeven, max profit/loss calculations |
| `SpyderU15_PerformanceMetrics.py` | 815 | Performance metrics: CAGR, Sharpe, Sortino, Calmar, max drawdown |
| `SpyderU16_TechnicalAnalysis.py` | 690 | Technical analysis utilities: pattern recognition, pivot detection |
| `SpyderU18_DependencyAnalyzer.py` | 771 | Module dependency analyser: maps import graph, detects circular dependencies |
| `SpyderU19_InteractionMatrix.py` | 948 | Module interaction matrix: tracks and visualises inter-module call patterns |
| `SpyderU20_InstitutionalLibraries.py` | 921 | Wrappers for institutional libraries: QuantLib, scipy.stats, statsmodels |
| `SpyderU22_ETTimeDisplay.py` | 158 | Eastern Time display helpers: formatted timestamps for UI and logging |
| `SpyderU23_MemoryMonitor.py` | 702 | Process memory monitor: tracks heap usage, detects leaks, triggers GC |
| `SpyderU24_StyleManager.py` | 719 | UI style manager: dark/light theme tokens, colour palettes, font definitions |
| `SpyderU27_SystemOptimizer.py` | 637 | System performance optimizer: CPU affinity, thread-pool tuning, GC schedule |
| `SpyderU40_RateLimiter.py` | 352 | Token-bucket rate limiter for API call throttling |
| `SpyderU41_CircuitBreaker.py` | 381 | Utility-layer circuit breaker; complements E16 for non-trading pathways |

### SpyderV_QuantModels — Quantitative Models

The V-Series implements institutional-grade quantitative models beyond standard BSM. These are used for advanced pricing, volatility modelling, and stress testing.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderV01_QuantEngine.py` | 945 | Core quantitative engine: coordinates all V-Series model execution |
| `SpyderV02_ModelManager.py` | 1,056 | Quant model lifecycle: registration, parameter storage, performance tracking |
| `SpyderV03_DataInterface.py` | 677 | Data interface for quant models: feeds clean market data into model pipelines |
| `SpyderV04_RiskManager.py` | 1,356 | Quant-layer risk manager: analytic Greeks, scenario analysis, stress testing |
| `SpyderV05_PricingEngine.py` | 1,560 | Advanced pricing: Heston, SABR, local-vol, and jump-diffusion models |
| `SpyderV06_VolatilityEngine.py` | 1,698 | Quantitative volatility: GARCH, EGARCH, HAR-RV, and realised vol models |
| `SpyderV07_AdvancedModels.py` | 1,320 | Advanced stochastic models: affine jump-diffusion, rough volatility (rBergomi) |
| `SpyderV08_AIModels.py` | 1,215 | AI-enhanced quant models: neural network pricing and vol prediction |

### SpyderX_Agents — On-Demand AI Agents

Stateless agents invoked on demand via the Ollama LLM backend. Each agent takes a context snapshot, reasons over it, and returns a recommendation or action.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderX01_GreeksAgent.py` | 2,449 | Analyses options Greeks exposure and recommends adjustments or hedges |
| `SpyderX02_FlowAgent.py` | 1,243 | Interprets order flow data; classifies institutional vs. retail activity |
| `SpyderX03_StrategyDirectorAgent.py` | 1,029 | Recommends strategy selection based on regime, IV rank, and risk budget |
| `SpyderX04_RiskGuardianAgent.py` | 833 | Reviews risk metrics in natural language; alerts on limit breaches |
| `SpyderX05_MLResearchAgent.py` | 1,515 | Proposes and evaluates ML model improvements using research context |
| `SpyderX06_BacktestingAgent.py` | 2,081 | Runs targeted backtests on strategy variants and summarises results |
| `SpyderX07_ExecutionStrategyAgent.py` | 958 | Optimises order execution: timing, limit vs. market, legging order |
| `SpyderX09_AlertManagerAgent.py` | 1,179 | Reviews and triages alerts; suppresses noise, escalates genuine issues |
| `SpyderX10_QuantModelsAgent.py` | 1,532 | Queries V-Series models for analytical insight and calibration advice |
| `SpyderX11_SentimentAnalysisAgent.py` | 1,479 | Synthesises news and social sentiment into a directional bias score |
| `SpyderX12_SystemHealthAgent.py` | 1,235 | Diagnoses system health issues and recommends remediation actions |
| `SpyderX13_MarketAnalysisAgent.py` | 860 | Provides natural-language market analysis and macro context |
| `SpyderX14_OrchestratorAgent.py` | 1,101 | Coordinates multi-agent workflows; delegates sub-tasks to specialists |
| `SpyderX15_StrategyGeneratorAgent.py` | 487 | Generates novel strategy ideas via LLM reasoning over market context |
| `SpyderX16_MetaCoordinator.py` | 1,200 | Meta-coordinator: monitors all X-Series agents, arbitrates conflicting signals |

### SpyderY_AutoAgents — Autonomous 24/7 Agents

Persistent agents with their own event loops, running continuously alongside the trading engine. They monitor, learn, and act without human prompting.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderY00_BaseAutoAgent.py` | 780 | Abstract base class: event loop, heartbeat, state management |
| `SpyderY01_MarketSenseAgent.py` | 522 | Continuously monitors market conditions; emits regime-change and anomaly events |
| `SpyderY02_StrategyPilotAgent.py` | 512 | Autonomous strategy activator/deactivator based on real-time regime signals |
| `SpyderY03_RiskSentinelAgent.py` | 627 | 24/7 risk sentinel; watches for limit breaches and triggers circuit breakers |
| `SpyderY04_AlphaLearnerAgent.py` | 549 | Continuously learns from recent trades; updates alpha scores for strategies |
| `SpyderY05_ExecutionOptimizerAgent.py` | 553 | Optimises execution quality in real time: timing, venue, order type |
| `SpyderY06_NewsSentinelAgent.py` | 556 | Monitors news feeds continuously; flags market-moving events for risk review |
| `SpyderY07_TradeJournalAgent.py` | 542 | Autonomous journaling: records rationale, outcome, and lessons learned |
| `SpyderY08_MetaOrchestratorAgent.py` | 619 | Meta-orchestrator: monitors Y-Series agent health, restarts failed agents |
| `SpyderY09_CodeReviewerAgent.py` | 467 | Reviews modified code for style, security, and correctness |
| `SpyderY10_AgentScheduler.py` | 398 | Schedules Y-Series tasks: periodic runs, market-hours gating, priority queuing |

### SpyderZ_Communication — Inter-Process Messaging

The Z-Series provides the messaging backbone for distributed and multi-process deployments. When a single-process setup is insufficient, Z-Series modules handle cross-process communication.

| Module | Lines | Purpose |
|--------|------:|--------|
| `SpyderZ01_ZeroMQIntegration.py` | 1,281 | ZeroMQ (0MQ) integration: PUB/SUB and REQ/REP patterns for inter-process messaging |
| `SpyderZ02_MessageProtocol.py` | 1,026 | Message protocol definitions: schemas, serialisation, versioning, and validation |
| `SpyderZ03_TradingCoordinator.py` | 1,537 | Coordinates trading decisions across processes via the messaging backbone |
| `SpyderZ04_VolatilityEngine.py` | 2,038 | Distributed volatility computation: offloads heavy IV calculations to workers |
| `SpyderZ05_OrderRouter.py` | 1,241 | Cross-process order router: fans orders to broker with deduplication |
| `SpyderZ06_AutoHedger.py` | 1,240 | Automated delta hedger running as a separate supervised process |
| `SpyderZ07_MultiProcessManager.py` | 1,021 | Multi-process manager: spawns, monitors, and restarts worker processes |
