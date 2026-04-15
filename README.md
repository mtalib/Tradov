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
**Last Updated: April 15, 2026**

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
SpyderA08_FSeriesOrchestrator.py
```

### SpyderB_Broker/
**Trading Execution & Broker Integration**
```
__init__.py
SpyderB00_OrderTypes.py
SpyderB02_OrderManager.py
SpyderB03_PositionTracker.py
SpyderB04_AccountManager.py
SpyderB15_PrometheusMetrics.py
SpyderB30_SPYOptionsChainManager.py
SpyderB40_TradierClient.py             # Primary Tradier API client
```

### SpyderC_MarketData/
**Market Data & Real-time Feeds**
```
__init__.py
SpyderC00_MarketDataProtocol.py
SpyderC01_DataFeed.py
SpyderC02_HistoricalData.py
SpyderC03_OptionChain.py
SpyderC04_MarketInternals.py
SpyderC05_VolumeProfile.py
SpyderC06_DataValidator.py
SpyderC08_SPYFeed.py
SpyderC09_NewsManager.py
SpyderC10_VIXAnalyzer.py
SpyderC11_FuturesBasis.py
SpyderC12_DarkPoolFlow.py
SpyderC13_IndexComponents.py
SpyderC15_MicrostructureAnalyzer.py
SpyderC16_MarketDataCache.py
SpyderC17_MarketConfigManager.py
SpyderC18_SKEWCalculator.py
SpyderC19_AfterHoursDataManager.py
SpyderC22_FactorDataProvider.py
SpyderC23_RealTimeDataOptimizer.py
SpyderC24_ModelDataPipeline.py
SpyderC27_MassiveClient.py             # Massive market data API client
SpyderC29_DataProviderRouter.py        # Routes between market data providers
SpyderC30_OrderFlowAnalyzer.py
SpyderC35_SentimentAnalyzer.py
```

### SpyderD_Strategies/
**Trading Strategies & Algorithms**
```
__init__.py
SpyderD00_StrategyConstants.py
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
SpyderD25_UnifiedCreditSpreadEngine.py
SpyderD26_GammaScalper.py
SpyderD27_EarningsStrategy.py
SpyderD28_VIXHedging.py
SpyderD30_RegimeGatedSelector.py
SpyderD31_StrategyOrchestrator.py
SpyderD32_MultiLegStrategyCoordinator.py
SpyderD33_RenaissanceMeanReversion.py
```

### SpyderE_Risk/
**Risk Management & Position Control**
```
__init__.py
SpyderE00_RiskProtocol.py
SpyderE01_RiskManager.py
SpyderE02_PositionSizer.py
SpyderE03_StopLossManager.py
SpyderE04_DrawdownControl.py
SpyderE05_AutomaticRebalancer.py
SpyderE06_RiskMetrics.py
SpyderE07_ProbabilisticSharpe.py
SpyderE08_PositionGroupValidator.py
SpyderE09_VolatilityRiskManager.py
SpyderE10_CorrelationRiskManager.py
SpyderE11_MaxLossProtection.py
SpyderE12_PortfolioVaR.py
SpyderE13_DayProfitTarget.py
SpyderE14_KellyPositionSizer.py
SpyderE15_GreekLimitsManager.py
SpyderE16_CircuitBreakerProtocol.py
SpyderE17_RealTimeStressTesting.py
SpyderE18_FSeriesRiskIntegrator.py
SpyderE19_UnifiedRiskCoordinator.py
SpyderE20_FrustrationAnalyzer.py
SpyderE21_HMMRegimeDetector.py
SpyderE22_KernelRegression.py
SpyderE23_PortfolioOptimizer.py
```

### SpyderF_Analysis/
**Technical Analysis & Indicators**
```
__init__.py
SpyderF00_AnalysisProtocol.py
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
SpyderF13_ModelValidation.py
SpyderF14_MarketMicrostructure.py
SpyderF16_RealTimeAnalytics.py
SpyderF17_UnifiedPerformanceEngine.py
SpyderF18_MaxPainCalculator.py
SpyderF19_AnchoredVWAP.py
SpyderF20_Indicators.py
SpyderF21_RenaissanceIndicators.py
SpyderF22_MLPrediction.py
```

### SpyderG_GUI/
**PySide6 Dashboard & User Interface**
```
__init__.py
SpyderG00_ApplicationManager.py
SpyderG01_MainWindow.py
SpyderG02_GUIEntry.py
SpyderG03_OptionChainWidget.py
SpyderG04_ChartWidget.py
SpyderG05_TradingDashboard.py
SpyderG06_DashboardData.py
SpyderG09_RiskParametersDialog.py
SpyderG11_SkewMonitorDialog.py
SpyderG12_SignalInfoDialog.py
SpyderG13_EnhancedWidgets.py
SpyderG14_Dashboard.py
SpyderG15_ConnectAPIStatus.py
SpyderG16_CircuitBreakerMonitor.py
SpyderG17_MarketInternalsWidget.py
SpyderG29_ChartWidgetPlotly.py
SpyderG30_PlotlyDataBridge.py
SpyderG31_PlotlyTemplates.py
SpyderG32_AgentHealthDashboard.py
SpyderG99_GUILogHandler.py
```

### SpyderH_Storage/
**Database & Data Persistence**
```
__init__.py
SpyderH01_DataAccessLayer.py
SpyderH02_DatabaseManager.py
SpyderH03_MarketDataCache.py
SpyderH04_TradeRepository.py
SpyderH07_PerformanceAnalytics.py
SpyderH08_TradeJournal.py
```

### SpyderI_Integration/
**System Integration & Diagnostics**
```
__init__.py
SpyderI01_IntegrationHub.py
SpyderI02_EventRouter.py
SpyderI03_ConfigManager.py
SpyderI04_DiagnosticsEngine_Core.py
SpyderI05_DiagnosticsEngine_Analyzers.py
SpyderI06_AgentMessageBus.py
SpyderI07_SyntaxValidator.py
SpyderI08_DiagnosticsEngine_DataCollector.py
SpyderI09_DiagnosticsEngine_HealthChecks.py
SpyderI10_DiagnosticsEngine_Types.py
SpyderI11_DiagnosticsEngine_Utils.py
SpyderI12_ModuleRegistry.py
```

### SpyderJ_Alerts/
**Notifications & Alerts**
```
__init__.py
SpyderJ01_AlertManager.py
SpyderJ02_EmailNotifier.py
SpyderJ03_WebhookNotifier.py
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
SpyderK11_UnifiedSharpeDashboard.py
SpyderK12_InstitutionalTearSheet.py
SpyderK13_StrategyPnLLadder.py
```

### SpyderL_ML/
**Machine Learning & AI Models**
```
__init__.py
SpyderL01_MLPredictor.py
SpyderL07_PaperTradeLearner.py
SpyderL08_EntryOptimizer.py
SpyderL09_UnifiedRegimeEngine.py
SpyderL10_FeatureEngineering.py
SpyderL11_MLModelManager.py
SpyderL12_RandomForestEnsemble.py
SpyderL13_LSTMPricer.py
SpyderL14_RealTimePredictor.py
SpyderL15_MomentPredictor.py
SpyderL16_OptionsAdjustmentRL.py
SpyderL17_FederatedLearning.py
SpyderL18_EnhancedMLIntegration.py
SpyderL19_RLTrainingPipeline.py
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
SpyderM07_MigrationMonitor.py
SpyderM08_HealthEndpoint.py
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

### SpyderO_TradingIntelligence/
**Trading Intelligence & Opportunity Scanning**
```
__init__.py
SpyderO01_CoreTechnicalIndicators.py
SpyderO02_TradingOpportunityScanner.py
SpyderO03_StrategyOptimizers.py
```

### SpyderP_PortfolioMgmt/
**Portfolio Management & Optimization**
```
__init__.py
SpyderP01_PortfolioManager.py
SpyderP02_AllocationOptimizer.py
SpyderP03_CorrelationAnalyzer.py
SpyderP04_CapitalAllocator.py
SpyderP05_MultiStrategyAllocator.py
SpyderP06_StrategyRotation.py
SpyderP07_RenaissancePositionSizer.py
```

### SpyderQ_Scripts/
**Production Scripts & Launchers**
```
__init__.py
SpyderQ01_FixExceptionHandling.py
SpyderQ02_ValidateEnv.py
SpyderQ03_ValidateConfiguration.py
SpyderQ04_LaunchDashboard.py
SpyderQ05_LaunchDashboardProactive.py
SpyderQ06_LaunchDashboardDirect.py
SpyderQ07_TestGUILogging.py
SpyderQ08_ValidatePackageExports.py
SpyderQ09_ValidateMissingExports.py
SpyderQ10_ProtocolComplianceGate.py
SpyderQ14_MainLauncher.py
SpyderQ24_ProductionWatchdog.py
SpyderQ25_SystemMonitor.py
SpyderQ45_Diagnostics.py
SpyderQ80_VerifyDashboardIntegration.py
SpyderQ90_SystemUtilities.py
SpyderQ92_DiagnosticsUtilities.py
SpyderQ93_RunPaper.py
SpyderQ96_CollectFinetuneData.py
SpyderQ98_FinetuneGemma4Spyder.py
SpyderQ99_ApplyPythonFormatting.py
```

### SpyderR_Runtime/
**Backtest & Live Trading Engines**
```
__init__.py
SpyderR02_PaperEngine.py
SpyderR03_PaperMonitor.py
SpyderR04_LiveEngine.py
SpyderR06_PaperTradingHarness.py
SpyderR07_LiveDashboard.py
SpyderR09_ProductionDeploymentManager.py
```

### SpyderS_Signals/
**Market Signals & Custom Metrics**
```
__init__.py
SpyderS01_DIXCalculator.py
SpyderS02_DIXScheduler.py
SpyderS03_BlackSwanIndicator.py
SpyderS04_BlackSwanScheduler.py
SpyderS05_GEXDEXCalculator.py
SpyderS06_SKEWCalculator.py
SpyderS07_CustomMetricsOrchestrator.py
SpyderS08_ShortSqueezeDetector.py
SpyderS09_FREDClient.py
SpyderS10_SentimentScraper.py
SpyderS11_BarchartInternals.py
```

### SpyderT_Testing/
**Test Suites & System Validation**
```
__init__.py
conftest.py
SpyderT01_UnitTestFramework.py
SpyderT03_BlackSwanValidator.py
SpyderT09_TestDashboard.py
SpyderT10_DashboardRisk.py
SpyderT40_TradierClient_Test.py
SpyderT42_Integration_Test.py
SpyderT43_OrderManager_Test.py
SpyderT44_DatabentoClient_Test.py
SpyderT46_RiskManager_Test.py
SpyderT47_StrategyUnit_Test.py
SpyderT55_PaperTradingHarness_Test.py
SpyderT56_StrategyTests.py
SpyderT57_OptionsAnalyticsTests.py
SpyderT58_RiskManagementTests.py
SpyderT77_CalendarInstitutionalLibrariesTests.py
SpyderT106_ACore.py
SpyderT107_FSeries.py ... SpyderT128_ZSeries.py  # Full A–Z series test suites
SpyderT129_ProtocolCompliance.py
SpyderT130_IronCondorSandbox_Test.py
(80+ total test modules)
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
SpyderU12_AgentIntegration.py
SpyderU13_TechnicalIndicators.py
SpyderU14_OptionStrategies.py
SpyderU15_PerformanceMetrics.py
SpyderU16_TechnicalAnalysis.py
SpyderU17_LLMUtils.py
SpyderU18_DependencyAnalyzer.py
SpyderU19_InteractionMatrix.py
SpyderU20_InstitutionalLibraries.py
SpyderU22_ETTimeDisplay.py
SpyderU23_MemoryMonitor.py
SpyderU24_StyleManager.py
SpyderU27_SystemOptimizer.py
SpyderU40_RateLimiter.py
SpyderU41_CircuitBreaker.py
SpyderU42_StrategyCircuitBreaker.py
SpyderU43_CorrelationLogger.py
SpyderU44_ShutdownCoordinator.py
SpyderU45_RetryWithBackoff.py
SpyderU46_SecretsManager.py
SpyderU47_OptionalImport.py
```

### SpyderV_QuantModels/
**Quantitative Models & Pricing**
```
__init__.py
SpyderV01_QuantEngine.py
SpyderV02_ModelManager.py
SpyderV03_DataInterface.py
SpyderV04_RiskManager.py
SpyderV05_PricingEngine.py
SpyderV06_VolatilityEngine.py
SpyderV07_AdvancedModels.py
SpyderV08_AIModels.py
SpyderV09_IVEngine.py
```

### SpyderX_Agents/
**On-Demand AI Agents (Stateless)**
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

### SpyderY_AutoAgents/
**Autonomous 24/7 AI Agents**
```
__init__.py
SpyderY00_BaseAutoAgent.py
SpyderY01_MarketSenseAgent.py
SpyderY02_StrategyPilotAgent.py
SpyderY03_RiskSentinelAgent.py
SpyderY04_AlphaLearnerAgent.py
SpyderY05_ExecutionOptimizerAgent.py
SpyderY06_NewsSentinelAgent.py
SpyderY07_TradeJournalAgent.py
SpyderY08_MetaOrchestratorAgent.py
SpyderY09_CodeReviewerAgent.py
SpyderY10_AgentScheduler.py
SpyderY_InferenceBackends.py
```

### SpyderZ_Communication/
**Inter-Process Communication**
```
__init__.py
SpyderZ00_BrokerProtocol.py
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
python Spyder/SpyderQ_Scripts/SpyderQ04_LaunchDashboard.py
```

### Launch Main Trading System
```bash
python Spyder/SpyderA_Core/SpyderA01_Main.py
```

### Run Paper Trading
```bash
python Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py
```

### Run Tests
```bash
pytest SpyderT_Testing/
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




