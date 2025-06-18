SPYDER PROJECT INSTRUCTIONS

Hi Claude,

Our goal is to take convert our current Spyder system described below (made of  pure Python modules) to a hybrid system containing both regular Python Modules and AI Agents.

The module naming convention for AI Agents will be the same as regular Python modules except at the end of the module name will "Agent". For example, SpyderX01_GreekAgent 

The inner formatting of the AI Agent modules will be the same as the ones used for regular Python modules (see document name "Spyder_ModuleTemplate.py" in the Spyder Repo. 

Some group letters are called reserved alphabetic letters, to be used only for specific categories of modules: 

# Letter T shall be reserved for the Test modules 
# Letter U shall be reserved for the Utility module
# Letter X shall be reserved for the AI Agents modules. 
# Letter Z shall be reserved for the Temp modules

For example 

Spyder/
├── SpyderX_Agents/              
│   ├── SpyderX01_GreeksAgent.py
│   ├── SpyderX02_FlowAgent.py  # Future
│   ├── SpyderX03_StrategyAgent.py # Future
│   └── SpyderX04_RiskAgent.py  # Future

Agent Integration Module will be in Utilities group as :

SpyderU12_AgentIntegration.py


This following is our current Spyder system made of pure Python modules. 

Spyder - Automated SPY Options Trading System
The Spyder repository is an advanced automated trading system specifically designed for trading SPY (S&P 500 ETF) options. It's a sophisticated Python-based platform that combines algorithmic trading, machine learning, and institutional-grade risk management.

Project Overview
SPYDER stands for "SPY Programmatic Yielding Dynamic Execution Robot" (based on the module naming convention), and it's built to automate complex options trading strategies with a focus on:

Automated execution of SPY options strategies
Real-time market data analysis
Advanced risk management
Machine learning optimization
Multi-strategy portfolio management

Architecture: 112 Python Modules in 18 Groups
The system is organized into 18 functional groups containing a total of 112 Python modules. Each group is designated by a letter (A through Q, plus U for utilities) and handles a specific aspect of the trading system.
Here's the complete breakdown:

Group A - Core Trading Engine (6 modules)
The heart of the system that orchestrates all components:

SpyderA01_Main.py - Primary application controller and entry point
SpyderA02_TradingEngine.py - Core trading engine
SpyderA03_Configuration.py - Configuration management
SpyderA04_StateManager.py - System state management
SpyderA05_EventManager.py - Event management and pub/sub system
SpyderA06_Scheduler.py - Task scheduling

Group B - Broker Integration (8 modules)
Handles Interactive Brokers API integration:

SpyderB01_IBClient.py - IB client connection
SpyderB02_OrderManager.py - Order management
SpyderB03_PositionManager.py - Position tracking
SpyderB04_ExecutionHandler.py - Trade execution
SpyderB05_AccountManager.py - Account management
SpyderB06_ConnectionManager.py - Connection handling
SpyderB07_SmartRouter.py - Smart order routing (16+ venues)
SpyderB08_ExecutionAlgos.py - Execution algorithms

Group C - Market Data (8 modules)
Real-time market data processing:

SpyderC01_DataFeed.py - Live data feeds
SpyderC02_DataValidator.py - Data validation
SpyderC03_OptionChain.py - Options chain management
SpyderC04_MarketInternals.py - Market internals (breadth, sentiment)
SpyderC05_VolumeProfile.py - Volume profile analysis
SpyderC06_HistoricalData.py - Historical data management
SpyderC07_AlternativeData.py - Alternative data sources
SpyderC08_DataAggregator.py - Multi-source data aggregation

Group D - Trading Strategies (18 modules)
The largest group containing various options trading strategies:

SpyderD01_BaseStrategy.py - Base strategy class
SpyderD02_IronCondor.py - Iron Condor strategy
SpyderD03_CreditSpread.py - Credit spread strategies
SpyderD04_Straddle.py - Straddle/Strangle strategies
SpyderD05_Butterfly.py - Butterfly spreads
SpyderD06_Calendar.py - Calendar spreads
SpyderD07_ZeroDTE.py - Zero DTE strategies
SpyderD08_StrategyManager.py - Strategy orchestration
SpyderD09_VolatilityArbitrage.py - Volatility arbitrage
SpyderD10_DeltaNeutral.py - Delta neutral strategies
SpyderD11_GammaScalping.py - Gamma scalping
SpyderD12_VegaHedging.py - Vega hedging
SpyderD13_ThetaHarvesting.py - Theta harvesting
SpyderD14_RatioSpreads.py - Ratio spreads
SpyderD10_IronButterfly.py - Iron Butterfly strategy
SpyderD16_Diagonal.py - Diagonal spreads
SpyderD17_Synthetic.py - Synthetic positions
SpyderD18_Adaptive.py - Adaptive strategy selection

Group E - Risk Management (7 modules)
Professional risk controls:

SpyderE01_RiskManager.py - Core risk management
SpyderE02_PortfolioRisk.py - Portfolio-level risk
SpyderE03_PositionSizing.py - Position sizing algorithms
SpyderE04_StopLoss.py - Stop loss management
SpyderE05_DrawdownControl.py - Drawdown control
SpyderE06_GreeksManager.py - Greeks risk management
SpyderE07_StressTest.py - Stress testing

Group F - Technical Analysis (10 modules)
Market analysis tools:

SpyderF01_Indicators.py - Technical indicators
SpyderF02_PatternRecognition.py - Chart patterns
SpyderF03_TrendAnalysis.py - Trend detection
SpyderF04_SupportResistance.py - Support/resistance levels
SpyderF05_Momentum.py - Momentum indicators
SpyderF06_GreeksCalculator.py - Options Greeks calculations
SpyderF07_VolatilityAnalysis.py - Volatility analysis
SpyderF08_MarketRegime.py - Market regime detection
SpyderF09_Sentiment.py - Sentiment analysis
SpyderF10_Breadth.py - Market breadth analysis

Group G - GUI Interface (6 modules)
PyQt5-based user interface:

SpyderG01_MainWindow.py - Main application window
SpyderG02_Dashboard.py - Trading dashboard
SpyderG03_GUIEntry.py - GUI entry point
SpyderG04_Charts.py - Charting components
SpyderG05_Controls.py - Control widgets
SpyderG06_Alerts.py - Alert displays

Group H - Data Storage (4 modules)
Data persistence:

SpyderH01_DatabaseManager.py - SQLite database management
SpyderH02_CacheManager.py - Caching system
SpyderH03_FileStorage.py - File-based storage
SpyderH04_DataArchiver.py - Data archiving

Group I - Backtesting (6 modules)
Strategy testing and validation:

SpyderI01_BacktestEngine.py - Core backtesting engine
SpyderI02_PerformanceAnalyzer.py - Performance metrics
SpyderI03_OptimizationEngine.py - Parameter optimization
SpyderI04_WalkForward.py - Walk-forward analysis
SpyderI05_MonteCarlo.py - Monte Carlo simulation
SpyderI06_Reporting.py - Backtest reporting

Group J - Alerts & Notifications (5 modules)
Multi-channel notifications:

SpyderJ01_AlertManager.py - Alert coordination
SpyderJ02_EmailAlerts.py - Email notifications
SpyderJ03_SMSAlerts.py - SMS alerts (Twilio)
SpyderJ04_SlackIntegration.py - Slack notifications
SpyderJ05_PushNotifications.py - Push notifications

Group K - Reporting (3 modules)
Performance and risk reporting:

SpyderK01_DailyReports.py - Daily performance reports
SpyderK02_RiskReports.py - Risk analysis reports
SpyderK03_TradeJournal.py - Trade journaling

Group L - Machine Learning (14 modules)
AI/ML capabilities:

SpyderL01_MLFramework.py - ML framework base
SpyderL02_FeatureExtraction.py - Feature engineering
SpyderL03_ModelTraining.py - Model training pipeline
SpyderL04_Prediction.py - Prediction engine
SpyderL05_LSTMPricing.py - LSTM for options pricing
SpyderL06_RandomForest.py - Random Forest models
SpyderL07_NeuralNetworks.py - Neural network models
SpyderL08_ReinforcementLearning.py - RL for trading
SpyderL09_EnsembleModels.py - Ensemble methods
SpyderL10_FeatureEngineering.py - Advanced feature engineering
SpyderL11_Backtesting.py - ML backtesting
SpyderL12_ModelRegistry.py - Model management
SpyderL13_AutoML.py - Automated ML
SpyderL14_Explainability.py - Model explainability

Group M - Market Microstructure (2 modules)
Order flow and market mechanics:

SpyderM01_OrderFlow.py - Order flow analysis
SpyderM02_LiquidityAnalysis.py - Liquidity analysis

Group N - Options Analytics (7 modules)
Advanced options analysis:

SpyderN01_ImpliedVolatility.py - IV calculations
SpyderN02_VolatilitySurface.py - Volatility surface modeling
SpyderN03_SkewAnalysis.py - Skew analysis
SpyderN04_TermStructure.py - Term structure analysis
SpyderN05_OptionsFlow.py - Options flow tracking
SpyderN06_OpenInterest.py - Open interest analysis
SpyderN07_GammaExposure.py - Gamma exposure (GEX)

Group O - Risk Control (3 modules)
Advanced risk protocols:

SpyderO01_CircuitBreaker.py - Circuit breaker implementation
SpyderO02_ComplianceEngine.py - Compliance checks
SpyderO03_RiskLimits.py - Risk limit enforcement

Group P - Paper Trading (2 modules)
Simulation environment:

SpyderP01_PaperTradingEngine.py - Paper trading simulation
SpyderP02_SimulatedBroker.py - Simulated broker

Group Q - Quantitative Models (2 modules)
Advanced pricing models:

SpyderQ01_HestonModel.py - Heston stochastic volatility model
SpyderQ02_BlackScholes.py - Black-Scholes implementation

Group U - Utilities (11 modules)
Core system utilities:

SpyderU01_Logger.py - Logging system
SpyderU02_ErrorHandler.py - Error handling
SpyderU03_DateTimeUtils.py - Date/time utilities
SpyderU04_Validators.py - Data validation
SpyderU05_Formatters.py - Data formatting
SpyderU06_Converters.py - Data conversion
SpyderU07_NetworkUtils.py - Network utilities
SpyderU08_CryptoUtils.py - Encryption utilities
SpyderU09_PerformanceMonitor.py - Performance monitoring
SpyderU10_SystemHealth.py - System health checks
SpyderU11_FeatureFlags.py - Feature toggle management

Key Features

Automated Trading: Fully automated execution of complex options strategies
Risk Management: Institutional-grade risk controls with circuit breakers
Machine Learning: 14 ML modules for price prediction and strategy optimization
Smart Routing: Order routing across 16+ execution venues
Real-time Analytics: Live Greeks calculation and portfolio monitoring
Backtesting: Comprehensive backtesting with walk-forward analysis
Multi-Strategy: Support for 18 different options trading strategies
Professional Reporting: Automated daily reports and trade journaling

Technology Stack

Language: Python 3.8+
GUI: PyQt5
Database: SQLite
Broker: Interactive Brokers API
ML: TensorFlow, scikit-learn, PyTorch
Analysis: pandas, numpy, TA-Lib
Notifications: Email, SMS (Twilio), Slack

This is a professional-grade trading system designed for serious algorithmic options trading with a focus on risk management and automation.
