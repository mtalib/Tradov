# SPYDER - Autonomous Options Trading System

## Project Overview
Spyder is an advanced automated trading system specifically designed for trading SPY (S&P 500 ETF) options. It's a sophisticated Python-based platform that combines algorithmic trading, machine learning, and institutional-grade risk management with real-time market data and execution capabilities.

## Technology Stack

**Platform:**
- OS: Ubuntu 24.04+ (Wayland)
- Language: Python 3.13+
- GUI Framework: PySide6
- Database: SQLite

**Trading Infrastructure:**
- Broker: Tradier Brokerage
- Market Data: Massve (formerly Polygon.io)
- Data Streaming: Real-time options flow, greeks, and SPY market data

## Module Architecture
**Last Updated: December 28th, 2025**

### SpyderA_Core/
**System Core & Trading Engine**
```
__init__.py
SpyderA01_Main.py
SpyderA02_TradingEngine.py
SpyderA03_Configuration.py
SpyderA04_Scheduler.py
SpyderA05_EventManager.py
SpyderA06_MasterController.py
```
### SpyderB_Broker/
**Trading Execution & Broker Integration**
```
__init__.py
SpyderB00_OrderTypes.py
SpyderB01_TradierClient.py              # Tradier API integration
SpyderB02_OrderManager.py
SpyderB03_PositionTracker.py
SpyderB04_AccountManager.py
SpyderB05_ConnectionManager.py
SpyderB06_ContractBuilder.py
SpyderB07_MarketDataManager.py
SpyderB17_SPYOptionsChainManager.py
```
### SpyderC_MarketData/
**Market Data & Real-time Feeds**
```
__init__.py
SpyderC01_MassveDataFeed.py            # Massve (Polygon) integration
SpyderC02_HistoricalData.py
SpyderC03_OptionChain.py
SpyderC04_MarketInternals.py
SpyderC05_VolumeProfile.py
SpyderC06_DataValidator.py
SpyderC07_MarketDataHub.py
SpyderC08_SPYFeed.py
SpyderC09_NewsManager.py
SpyderC10_VIXAnalyzer.py
SpyderC12_DarkPoolFlow.py
SpyderC13_IndexComponents.py
SpyderC14_UltraLowLatencyFeed.py
SpyderC15_MicrostructureAnalyzer.py
SpyderC16_MarketDataCache.py
SpyderC17_MarketConfigManager.py
SpyderC18_SKEWCalculator.py
```
### SpyderD_Strategies/
**Trading Strategies & Algorithms**
```
__init__.py
SpyderD01_BaseStrategy.py
SpyderD02_IronCondor.py
SpyderD03_CreditSpread.py
SpyderD04_ZeroDTE.py
SpyderD05_Straddle.py
SpyderD06_BullPutSpread.py
SpyderD07_BearCallSpread.py
SpyderD08_OpeningRangeBreakout.py
SpyderD09_GreeksBasedStrategy.py
SpyderD10_IronButterfly.py
SpyderD11_SpecializedZeroDTE.py
SpyderD12_RSIMeanReversion.py
SpyderD13_MACrossover.py
SpyderD14_CalendarSpread.py
SpyderD15_StraddleStrangle.py
SpyderD16_RatioSpreads.py
SpyderD17_DiagonalSpread.py
SpyderD18_EvolvedCreditSpread.py
SpyderD19_JadeLizard.py
SpyderD20_VerticalSpreadOptimizer.py
SpyderD21_DoubleCalendar.py
SpyderD22_AdaptiveVolatility.py
SpyderD26_GammaScalper.py
```
### SpyderE_Risk/
**Risk Management & Position Control**
```
__init__.py
SpyderE01_RiskManager.py
SpyderE02_PositionSizer.py
SpyderE03_GreekLimitsManager.py
SpyderE03_StopLossManager.py
SpyderE04_CircuitBreakerProtocol.py
SpyderE04_DrawdownControl.py
SpyderE05_AutomaticRebalancer.py
SpyderE06_RiskMetrics.py
SpyderE08_PositionGroupValidator.py
SpyderE09_VolatilityRiskManager.py
SpyderE11_MaxLossProtection.py
SpyderE12_PortfolioVaR.py
```
### SpyderF_Analysis/
**Technical Analysis & Indicators**
```
__init__.py
SpyderF01_Indicators.py
SpyderF02_PriceAction.py
SpyderF03_SupportResistance.py
SpyderF04_VolatilityAnalysis.py
SpyderF05_TrendDetection.py
SpyderF06_GreeksCalculator.py
SpyderF07_GapAnalyzer.py
SpyderF08_VolatilityRegime.py
SpyderF09_EntryFilters.py
SpyderF10_MarketRegimeDetector.py
SpyderF11_GreeksAggregator.py
```

### SpyderG_GUI/
**PySide6 Dashboard & User Interface**
```
__init__.py
SpyderG01_MainWindow.py
SpyderG02_GUIEntry.py
SpyderG03_OptionChainWidget.py
SpyderG04_ChartWidget.py
SpyderG05_TradingDashboard.py
SpyderG06_MonitorPanel.py
SpyderG09_RiskParametersDialog.py
SpyderG11_SkewMonitorDialog.py
SpyderG12_SignalInfoDialog.py
```
### SpyderH_Storage/
**Database & Data Persistence**
```
__init__.py
SpyderH01_DataAccessLayer.py
SpyderH02_DatabaseManager.py
```

### SpyderI_Integration/
**System Integration & Diagnostics**
```
SpyderI01_IntegrationHub.py
SpyderI02_EventRouter.py
SpyderI03_ConfigManager.py
SpyderI04_DiagnosticsEngine_Core.py
SpyderI04_DiagnosticsEngine_DataCollector.py
SpyderI04_DiagnosticsEngine_HealthChecks.py
SpyderI04_DiagnosticsEngine_Types.py
SpyderI04_DiagnosticsEngine_Utils.py
SpyderI04_SyntaxValidator.py
SpyderI06_AgentMessageBus.py
syntax_error_detector.py
```

### SpyderJ_Alerts/
**Notifications & Alerts**
```
__init__.py
SpyderJ01_AlertManager.py
SpyderJ02_EmailNotifier.py
SpyderJ04_DesktopNotifier.py
SpyderJ05_TelegramBot.py
```
### SpyderK_Reports/
**Performance Reports & Analytics**
```
__init__.py
SpyderK01_ReportGenerator.py
SpyderK02_DailyTradingReport.py
SpyderK03_PerformanceDashboard.py
SpyderK04_ExecutionAnalytics.py
SpyderK05_RiskReport.py
SpyderK06_PortfolioAnalytics.py
SpyderK07_StrategyComparison.py
SpyderK08_MLPerformanceReport.py
SpyderK09_RegulatoryReports.py
SpyderK10_RealTimePerformanceAnalytics.py
```

### SpyderL_ML/
**Machine Learning & AI Models**
```
__init__.py
SpyderD00_StrategyConstants.py
SpyderL01_MLPredictor.py
SpyderL07_PaperTradeLearner.py
SpyderL08_EntryOptimizer.py
SpyderL09_RegimeClassifier.py
SpyderL10_FeatureEngineering.py
SpyderL11_MLModelManager.py
SpyderL12_RandomForestEnsemble.py
SpyderL13_LSTMPricer.py
SpyderL14_RealTimePredictor.py
SpyderL15_MOmentPredictor.py
SpyderL16_OptionsAdjustmentRL.py
SpyderL17_FederatedLearning.py
SpyderL18_EnhancedMLIntegration.py
```

### SpyderM_Monitoring/
**System Monitoring & Metrics**
```
__init__.py
SpyderM01_SystemMonitor.py
SpyderM03_AIAgentMonitor.py
SpyderM04_TradingMetrics.py
SpyderM05_TransactionCostAnalysis.py
SpyderM06_HMMRegimeDetector.py
```
### SpyderN_OptionsAnalytics/
**Advanced Options Pricing & Greeks**
```
__init__.py
SpyderN01_OptionsPricer.py
SpyderN02_ImpliedVolatilityEngine.py
SpyderN03_OptionsChainManager.py
SpyderN04_OptionsGreeksCalculator.py
SpyderN05_OptionsExpirationManager.py
SpyderN06_VolatilitySurfaceBuilder.py
SpyderN07_OptionsFlowTracker.py
SpyderN08_VolatilitySurface.py
SpyderN09_GammaExposure.py
SpyderN10_OptionsFlowAnalyzer.py
SpyderN11_OptionsGreeksFlow.py
SpyderN12_VolatilitySurfaceAI.py
SpyderN13_MarketImpactModel.py
```

### SpyderP_PortfolioMgmt/
**Portfolio Management & Optimization**
```
SpyderP01_PortfolioManager.py
SpyderP02_AllocationOptimizer.py
SpyderP03_CorrelationAnalyzer.py
SpyderP04_CapitalAllocator.py
SpyderP05_MultiStrategyAllocator.py
SpyderP06_StrategyRotation.py
```

### SpyderQ_Scripts/
**Production Scripts & Launchers**
```
launch_dashboard_production.py          # Main dashboard launcher
launch_dashboard_with_proactive_connections.py
SpyderQ01_Setup.sh
SpyderQ10_StartAll.sh
SpyderQ11_StopAll.sh
SpyderQ14_MainLauncher.py
SpyderQ20_Status.sh
SpyderQ21_Monitor.sh
SpyderQ24_ProductionWatchdog.py
SpyderQ25_SystemMonitor.py
SpyderQ30_Diagnostics.sh
SpyderQ35_VerifySystem.sh
SpyderQ40_Cleanup.sh
SpyderQ41_Backup.sh
SpyderQ45_Diagnostics.py
SpyderQ50_ExportData.sh
```
### SpyderR_Runtime/
**Backtest & Live Trading Engines**
```
__init__.py
SpyderR01_BacktestEngine.py
SpyderR02_PaperEngine.py
SpyderR03_PaperMonitor.py
SpyderR04_LiveEngine.py
SpyderR05_LiveDashboard.py
SpyderR06_EnhancedBacktestEngine.py
```

### SpyderS_Signals/
**Market Signals & Indicators**
```
SpyderS01_DIXCalculator.py
SpyderS02_DIXScheduler.py
SpyderS03_BlackSwanIndicator.py
SpyderS04_BlackSwanScheduler.py
SpyderS05_GEXDEXCalculator.py
SpyderS06_SKEWCalculator.py
SpyderS07_CustomMetricsOrchestrator.py
```

### SpyderT_Technical/
**Pure Python Technical Indicators**
```
pure_python_indicators.py
```

### SpyderT_Testing/
**Test Suites & System Validation**
```
SpyderT01_UnitTestFramework.py
SpyderT02_BrokerTestSuite.py
SpyderT03_BlackSwanValidator.py
SpyderT06_EvolvedStrategyTest.py
SpyderT09_TestDashboard.py
SpyderT10_DashboardRisk.py
SpyderT11_EliteEvolvedStrategyTest.py
SpyderT12_FullSystemIntegration.py
SpyderT14_RiskSuiteIntegrationTest.py
SpyderT15_FullSystemTest.py
SpyderT16_SystemHealthMonitor.py
SpyderT20_DIXDemo.py
SpyderT21_DIXQuickStart.py
```
### SpyderU_Utilities/
**Core Utilities & Helpers**
```
__init__.py
SpyderU01_Logger.py
SpyderU02_ErrorHandler.py
SpyderU03_DateTimeUtils.py
SpyderU04_Encryption.py
SpyderU05_NetworkUtils.py
SpyderU06_MathUtils.py
SpyderU07_Constants.py
SpyderU08_Validators.py
SpyderU09_DataTypes.py
SpyderU10_TradingCalendar.py
SpyderU11_FeatureFlags.py
SpyderU13_TechnicalIndicators.py
SpyderU14_OptionStrategies.py
SpyderU15_PerformanceMetrics.py
SpyderU16_TechnicalAnalysis.py
SpyderU18_DependencyAnalyzer.py
SpyderU19_InteractionMatrix.py
SpyderU20_InstitutionalLibraries.py
```

### SpyderX_Agents/
**AI Agents & Autonomous Trading**
```
__init__.py
SpyderX01_GreeksAgent.py
SpyderX02_FlowAgent.py
SpyderX03_StrategyDirectorAgent.py
SpyderX04_RiskGuardianAgent.py
SpyderX05_MLResearchAgent.py
SpyderX06_BacktestingAgent.py
SpyderX07_ExecutionStrategyAgent.py
SpyderX08_PerformanceAnalyticsAgent.py
SpyderX09_AlertManagerAgent.py
SpyderX10_QuantModelsAgent.py
SpyderX11_SentimentAnalysisAgent.py
SpyderX12_SystemHealthAgent.py
SpyderX13_MarketAnalysisAgent.py
SpyderX14_OrchestratorAgent.py
SpyderX15_StrategyGeneratorAgent.py
SpyderX16_MetaCoordinator.py
```

### SpyderZ_Communication/
**Inter-Process Communication**
```
__init__.py
SpyderZ01_ZeroMQIntegration.py
SpyderZ02_MessageProtocol.py
SpyderZ03_TradingCoordinator.py
SpyderZ04_VolatilityEngine.py
SpyderZ05_OrderRouter.py
SpyderZ06_AutoHedger.py
SpyderZ07_MultiProcessManager.py
```

---

## Getting Started

### Launch Dashboard
```bash
python Spyder/SpyderQ_Scripts/launch_dashboard_production.py
```

### Launch Main Trading System
```bash
python Spyder/SpyderA_Core/SpyderA01_Main.py
```

## Key Features

- **Real-time Market Data**: Massve (Polygon) WebSocket streaming
- **Advanced Options Analytics**: Greeks, volatility surface, flow analysis
- **Multiple Trading Strategies**: 20+ pre-built options strategies
- **AI-Powered Agents**: Autonomous trading agents with ML capabilities
- **Risk Management**: Multi-layered risk controls and circuit breakers
- **PySide6 Dashboard**: Professional trading interface with Wayland support
- **Paper & Live Trading**: Tradier integration for both modes
- **Comprehensive Testing**: Full test suite with integration tests

## Documentation

See [1-DOCUMENTATION](1-DOCUMENTATION) for detailed guides and API documentation.

---

**Version**: 1.4.0  
**Last Updated**: December 28, 2025  
**Author**: Mohamed Talib




