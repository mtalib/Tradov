# TRADOV - Multi-Agent Stock Trading System v1.0

## Project Overview
Tradov is a multi-agent LLM-powered stock trading platform built on the TradingAgents architecture with Tradier broker connectivity. It combines a LangGraph-based multi-agent pipeline (Market Analyst, Sentiment Analyst, News Analyst, Fundamentals Analyst, Bull/Bear Debate, Research Manager, Trader, Risk Debate, Portfolio Manager) with algorithmic trading, machine learning, and institutional-grade risk management.

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
**Last Updated: April 15, 2026**

### TradovA_Core/
**System Core & Trading Engine**
```
__init__.py
TradovA01_Main.py
TradovA02_TradingEngine.py
TradovA03_Configuration.py
TradovA04_Scheduler.py
TradovA05_EventManager.py
TradovA06_MasterController.py
TradovA08_FSeriesOrchestrator.py
```

### TradovB_Broker/
**Trading Execution & Broker Integration**
```
__init__.py
TradovB00_OrderTypes.py
TradovB02_OrderManager.py
TradovB03_PositionTracker.py
TradovB04_AccountManager.py
TradovB15_PrometheusMetrics.py
TradovB30_SPYOptionsChainManager.py
TradovB40_TradierClient.py             # Primary Tradier API client
```

### TradovC_MarketData/
**Market Data & Real-time Feeds**
```
__init__.py
TradovC00_MarketDataProtocol.py
TradovC01_DataFeed.py
TradovC02_HistoricalData.py
TradovC03_OptionChain.py
TradovC04_MarketInternals.py
TradovC05_VolumeProfile.py
TradovC06_DataValidator.py
TradovC08_SPYFeed.py
TradovC09_NewsManager.py
TradovC10_VIXAnalyzer.py
TradovC12_DarkPoolFlow.py
TradovC13_IndexComponents.py
TradovC15_MicrostructureAnalyzer.py
TradovC16_MarketDataCache.py
TradovC17_MarketConfigManager.py
TradovC18_SKEWCalculator.py
TradovC19_AfterHoursDataManager.py
TradovC22_FactorDataProvider.py
TradovC23_RealTimeDataOptimizer.py
TradovC24_ModelDataPipeline.py
TradovC27_MassiveClient.py             # Massive market data API client
TradovC29_DataProviderRouter.py        # Routes between market data providers
TradovC30_OrderFlowAnalyzer.py
TradovC35_SentimentAnalyzer.py
```

### TradovD_Strategies/
**Trading Strategies & Algorithms**
```
__init__.py
TradovD00_StrategyConstants.py
TradovD01_BaseStrategy.py
TradovD02_IronCondor.py
TradovD03_CreditSpread.py
TradovD04_ZeroDTE.py
TradovD05_Straddle.py
TradovD06_BullPutSpread.py
TradovD07_BearCallSpread.py
TradovD08_OpeningRangeBreakout.py
TradovD09_GreeksBasedStrategy.py
TradovD10_IronButterfly.py
TradovD11_SpecializedZeroDTE.py
TradovD12_RSIMeanReversion.py
TradovD13_MACrossover.py
TradovD14_CalendarSpread.py
TradovD15_StraddleStrangle.py
TradovD16_RatioSpreads.py
TradovD17_DiagonalSpread.py
TradovD18_EvolvedCreditSpread.py
TradovD19_JadeLizard.py
TradovD20_VerticalSpreadOptimizer.py
TradovD21_DoubleCalendar.py
TradovD22_AdaptiveVolatility.py
TradovD25_UnifiedCreditSpreadEngine.py
TradovD26_GammaScalper.py
TradovD27_EarningsStrategy.py
TradovD28_VIXHedging.py
TradovD30_RegimeGatedSelector.py
TradovD31_StrategyOrchestrator.py
TradovD32_MultiLegStrategyCoordinator.py
TradovD33_RenaissanceMeanReversion.py
```

### TradovE_Risk/
**Risk Management & Position Control**
```
__init__.py
TradovE00_RiskProtocol.py
TradovE01_RiskManager.py
TradovE02_PositionSizer.py
TradovE03_StopLossManager.py
TradovE04_DrawdownControl.py
TradovE05_AutomaticRebalancer.py
TradovE06_RiskMetrics.py
TradovE07_ProbabilisticSharpe.py
TradovE08_PositionGroupValidator.py
TradovE09_VolatilityRiskManager.py
TradovE10_CorrelationRiskManager.py
TradovE11_MaxLossProtection.py
TradovE12_PortfolioVaR.py
TradovE13_DayProfitTarget.py
TradovE14_KellyPositionSizer.py
TradovE15_GreekLimitsManager.py
TradovE16_CircuitBreakerProtocol.py
TradovE17_RealTimeStressTesting.py
TradovE18_FSeriesRiskIntegrator.py
TradovE19_UnifiedRiskCoordinator.py
TradovE20_FrustrationAnalyzer.py
TradovE21_HMMRegimeDetector.py
TradovE22_KernelRegression.py
TradovE23_PortfolioOptimizer.py
```

### TradovF_Analysis/
**Technical Analysis & Indicators**
```
__init__.py
TradovF00_AnalysisProtocol.py
TradovF01_Indicators.py
TradovF02_PriceAction.py
TradovF03_SupportResistance.py
TradovF04_VolatilityAnalysis.py
TradovF05_TrendDetection.py
TradovF06_GreeksCalculator.py
TradovF07_GapAnalyzer.py
TradovF08_VolatilityRegime.py
TradovF09_EntryFilters.py
TradovF10_MarketRegimeDetector.py
TradovF11_GreeksAggregator.py
TradovF13_ModelValidation.py
TradovF14_MarketMicrostructure.py
TradovF16_RealTimeAnalytics.py
TradovF17_UnifiedPerformanceEngine.py
TradovF18_MaxPainCalculator.py
TradovF19_AnchoredVWAP.py
TradovF20_Indicators.py
TradovF21_RenaissanceIndicators.py
TradovF22_MLPrediction.py
```

### TradovG_GUI/
**PySide6 Dashboard & User Interface**
```
__init__.py
TradovG00_ApplicationManager.py
TradovG01_MainWindow.py
TradovG02_GUIEntry.py
TradovG03_OptionChainWidget.py
TradovG04_ChartWidget.py
TradovG05_TradingDashboard.py
TradovG06_DashboardData.py
TradovG09_RiskParametersDialog.py
TradovG11_SkewMonitorDialog.py
TradovG12_SignalInfoDialog.py
TradovG13_EnhancedWidgets.py
TradovG14_Dashboard.py
TradovG15_ConnectAPIStatus.py
TradovG16_CircuitBreakerMonitor.py
TradovG17_MarketInternalsWidget.py
TradovG29_ChartWidgetPlotly.py
TradovG30_PlotlyDataBridge.py
TradovG31_PlotlyTemplates.py
TradovG32_AgentHealthDashboard.py
TradovG99_GUILogHandler.py
```

### TradovH_Storage/
**Database & Data Persistence**
```
__init__.py
TradovH01_DataAccessLayer.py
TradovH02_DatabaseManager.py
TradovH03_MarketDataCache.py
TradovH04_TradeRepository.py
TradovH07_PerformanceAnalytics.py
TradovH08_TradeJournal.py
```

### TradovI_Integration/
**System Integration & Diagnostics**
```
__init__.py
TradovI01_IntegrationHub.py
TradovI02_EventRouter.py
TradovI03_ConfigManager.py
TradovI04_DiagnosticsEngine_Core.py
TradovI05_DiagnosticsEngine_Analyzers.py
TradovI06_AgentMessageBus.py
TradovI07_SyntaxValidator.py
TradovI08_DiagnosticsEngine_DataCollector.py
TradovI09_DiagnosticsEngine_HealthChecks.py
TradovI10_DiagnosticsEngine_Types.py
TradovI11_DiagnosticsEngine_Utils.py
TradovI12_ModuleRegistry.py
```

### TradovJ_Alerts/
**Notifications & Alerts**
```
__init__.py
TradovJ01_AlertManager.py
TradovJ02_EmailNotifier.py
TradovJ03_WebhookNotifier.py
TradovJ04_DesktopNotifier.py
TradovJ05_TelegramBot.py
```

### TradovK_Reports/
**Performance Reports & Analytics**
```
__init__.py
TradovK01_ReportGenerator.py
TradovK02_DailyTradingReport.py
TradovK03_PerformanceDashboard.py
TradovK04_ExecutionAnalytics.py
TradovK05_RiskReport.py
TradovK06_PortfolioAnalytics.py
TradovK07_StrategyComparison.py
TradovK08_MLPerformanceReport.py
TradovK09_RegulatoryReports.py
TradovK10_RealTimePerformanceAnalytics.py
TradovK11_UnifiedSharpeDashboard.py
TradovK12_InstitutionalTearSheet.py
TradovK13_StrategyPnLLadder.py
```

### TradovL_ML/
**Machine Learning & AI Models**
```
__init__.py
TradovL01_MLPredictor.py
TradovL07_PaperTradeLearner.py
TradovL08_EntryOptimizer.py
TradovL09_UnifiedRegimeEngine.py
TradovL10_FeatureEngineering.py
TradovL11_MLModelManager.py
TradovL12_RandomForestEnsemble.py
TradovL13_LSTMPricer.py
TradovL14_RealTimePredictor.py
TradovL15_MomentPredictor.py
TradovL16_OptionsAdjustmentRL.py
TradovL17_FederatedLearning.py
TradovL18_EnhancedMLIntegration.py
TradovL19_RLTrainingPipeline.py
```

### TradovM_Monitoring/
**System Monitoring & Metrics**
```
__init__.py
TradovM01_SystemMonitor.py
TradovM03_AIAgentMonitor.py
TradovM04_TradingMetrics.py
TradovM05_TransactionCostAnalysis.py
TradovM06_HMMRegimeDetector.py
TradovM07_MigrationMonitor.py
TradovM08_HealthEndpoint.py
```

### TradovN_OptionsAnalytics/
**Advanced Options Pricing & Greeks**
```
__init__.py
TradovN01_OptionsPricer.py
TradovN02_ImpliedVolatilityEngine.py
TradovN03_OptionsChainManager.py
TradovN04_OptionsGreeksCalculator.py
TradovN05_OptionsExpirationManager.py
TradovN06_VolatilitySurfaceBuilder.py
TradovN07_OptionsFlowTracker.py
TradovN08_VolatilitySurface.py
TradovN09_GammaExposure.py
TradovN10_OptionsFlowAnalyzer.py
TradovN11_OptionsGreeksFlow.py
TradovN12_VolatilitySurfaceAI.py
TradovN13_MarketImpactModel.py
```

### TradovO_TradingIntelligence/
**Trading Intelligence & Opportunity Scanning**
```
__init__.py
TradovO01_CoreTechnicalIndicators.py
TradovO02_TradingOpportunityScanner.py
TradovO03_StrategyOptimizers.py
```

### TradovP_PortfolioMgmt/
**Portfolio Management & Optimization**
```
__init__.py
TradovP01_PortfolioManager.py
TradovP02_AllocationOptimizer.py
TradovP03_CorrelationAnalyzer.py
TradovP04_CapitalAllocator.py
TradovP05_MultiStrategyAllocator.py
TradovP06_StrategyRotation.py
TradovP07_RenaissancePositionSizer.py
```

### TradovQ_Scripts/
**Production Scripts & Launchers**
```
__init__.py
TradovQ01_FixExceptionHandling.py
TradovQ02_ValidateEnv.py
TradovQ03_ValidateConfiguration.py
TradovQ04_LaunchDashboard.py
TradovQ05_LaunchDashboardProactive.py
TradovQ06_LaunchDashboardDirect.py
TradovQ07_TestGUILogging.py
TradovQ08_ValidatePackageExports.py
TradovQ09_ValidateMissingExports.py
TradovQ10_ProtocolComplianceGate.py
TradovQ14_MainLauncher.py
TradovQ24_ProductionWatchdog.py
TradovQ25_SystemMonitor.py
TradovQ45_Diagnostics.py
TradovQ80_VerifyDashboardIntegration.py
TradovQ90_SystemUtilities.py
TradovQ92_DiagnosticsUtilities.py
TradovQ93_RunPaper.py
TradovQ96_CollectFinetuneData.py
TradovQ98_FinetuneGemma4Tradov.py
TradovQ99_ApplyPythonFormatting.py
```

### TradovR_Runtime/
**Backtest & Live Trading Engines**
```
__init__.py
TradovR02_PaperEngine.py
TradovR03_PaperMonitor.py
TradovR04_LiveEngine.py
TradovR06_PaperTradingHarness.py
TradovR07_LiveDashboard.py
TradovR09_ProductionDeploymentManager.py
```

### TradovS_Signals/
**Market Signals & Custom Metrics**
```
__init__.py
TradovS01_DIXCalculator.py
TradovS02_DIXScheduler.py
TradovS03_BlackSwanIndicator.py
TradovS04_BlackSwanScheduler.py
TradovS05_GEXDEXCalculator.py
TradovS06_SKEWCalculator.py
TradovS07_CustomMetricsOrchestrator.py
TradovS08_ShortSqueezeDetector.py
TradovS09_FREDClient.py
TradovS10_SentimentScraper.py
TradovS11_BarchartInternals.py
```

### TradovT_Testing/
**Test Suites & System Validation**
```
__init__.py
conftest.py
TradovT01_UnitTestFramework.py
TradovT03_BlackSwanValidator.py
TradovT09_TestDashboard.py
TradovT10_DashboardRisk.py
TradovT40_TradierClient_Test.py
TradovT42_Integration_Test.py
TradovT43_OrderManager_Test.py
TradovT44_DatabentoClient_Test.py
TradovT46_RiskManager_Test.py
TradovT47_StrategyUnit_Test.py
TradovT55_PaperTradingHarness_Test.py
TradovT56_StrategyTests.py
TradovT57_OptionsAnalyticsTests.py
TradovT58_RiskManagementTests.py
TradovT77_CalendarInstitutionalLibrariesTests.py
TradovT106_ACore.py
TradovT107_FSeries.py ... TradovT128_ZSeries.py  # Full A–Z series test suites
TradovT129_ProtocolCompliance.py
TradovT130 manual legacy Tradier order test
(80+ total test modules)
```

### TradovU_Utilities/
**Core Utilities & Helpers**
```
__init__.py
TradovU01_Logger.py
TradovU02_ErrorHandler.py
TradovU03_DateTimeUtils.py
TradovU04_Encryption.py
TradovU05_NetworkUtils.py
TradovU06_MathUtils.py
TradovU07_Constants.py
TradovU08_Validators.py
TradovU09_DataTypes.py
TradovU10_TradingCalendar.py
TradovU11_FeatureFlags.py
TradovU12_AgentIntegration.py
TradovU13_TechnicalIndicators.py
TradovU14_OptionStrategies.py
TradovU15_PerformanceMetrics.py
TradovU16_TechnicalAnalysis.py
TradovU17_LLMUtils.py
TradovU18_DependencyAnalyzer.py
TradovU19_InteractionMatrix.py
TradovU20_InstitutionalLibraries.py
TradovU22_ETTimeDisplay.py
TradovU23_MemoryMonitor.py
TradovU24_StyleManager.py
TradovU27_SystemOptimizer.py
TradovU40_RateLimiter.py
TradovU41_CircuitBreaker.py
TradovU42_StrategyCircuitBreaker.py
TradovU43_CorrelationLogger.py
TradovU44_ShutdownCoordinator.py
TradovU45_RetryWithBackoff.py
TradovU46_SecretsManager.py
TradovU47_OptionalImport.py
```

### TradovV_QuantModels/
**Quantitative Models & Pricing**
```
__init__.py
TradovV01_QuantEngine.py
TradovV02_ModelManager.py
TradovV03_DataInterface.py
TradovV04_RiskManager.py
TradovV05_PricingEngine.py
TradovV06_VolatilityEngine.py
TradovV07_AdvancedModels.py
TradovV08_AIModels.py
TradovV09_IVEngine.py
```

### TradovX_Agents/
**On-Demand AI Agents (Stateless)**
```
__init__.py
TradovX01_GreeksAgent.py
TradovX02_FlowAgent.py
TradovX03_StrategyDirectorAgent.py
TradovX04_RiskGuardianAgent.py
TradovX05_MLResearchAgent.py
TradovX06_BacktestingAgent.py
TradovX07_ExecutionStrategyAgent.py
TradovX08_PerformanceAnalyticsAgent.py
TradovX09_AlertManagerAgent.py
TradovX10_QuantModelsAgent.py
TradovX11_SentimentAnalysisAgent.py
TradovX12_SystemHealthAgent.py
TradovX13_MarketAnalysisAgent.py
TradovX14_OrchestratorAgent.py
TradovX15_StrategyGeneratorAgent.py
TradovX16_MetaCoordinator.py
```

### TradovY_AutoAgents/
**Autonomous 24/7 AI Agents**
```
__init__.py
TradovY00_BaseAutoAgent.py
TradovY01_MarketSenseAgent.py
TradovY02_StrategyPilotAgent.py
TradovY03_RiskSentinelAgent.py
TradovY04_AlphaLearnerAgent.py
TradovY05_ExecutionOptimizerAgent.py
TradovY06_NewsSentinelAgent.py
TradovY07_TradeJournalAgent.py
TradovY08_MetaOrchestratorAgent.py
TradovY09_CodeReviewerAgent.py
TradovY10_AgentScheduler.py
TradovY_InferenceBackends.py
```

### TradovZ_Communication/
**Inter-Process Communication**
```
__init__.py
TradovZ00_BrokerProtocol.py
TradovZ01_ZeroMQIntegration.py
TradovZ02_MessageProtocol.py
TradovZ03_TradingCoordinator.py
TradovZ04_VolatilityEngine.py
TradovZ05_OrderRouter.py
TradovZ06_AutoHedger.py
TradovZ07_MultiProcessManager.py
```

---

## Getting Started

### Launch Dashboard
```bash
python Tradov/TradovQ_Scripts/TradovQ04_LaunchDashboard.py
```

### Launch Main Trading System
```bash
python Tradov/TradovA_Core/TradovA01_Main.py
```

### Run Paper Trading
```bash
python Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py
```

### Run Tests
```bash
pytest TradovT_Testing/
```

## Key Features

- **Real-time Market Data**: Massive API WebSocket streaming
- **Advanced Options Analytics**: Greeks, volatility surface, flow analysis
- **Multiple Trading Strategies**: 30+ pre-built options strategies
- **AI-Powered Agents**: 16 on-demand (X-Series) + 10 autonomous 24/7 (Y-Series) agents
- **Risk Management**: Multi-layered risk controls and circuit breakers
- **PySide6 Dashboard**: Professional trading interface with Wayland support
- **Paper & Live Trading**: Tradier integration for both modes
- **Comprehensive Testing**: 80+ test modules covering all series (A–Z)

## Documentation

See [01-Overview-Specs](01-Overview-Specs) for architecture docs and overview specs.  
See [02-Standards-Instructions](02-Standards-Instructions) for coding standards and guides.

---

**Version**: 2.0.0  
**Last Updated**: April 15, 2026  
**Author**: Mohamed Talib




