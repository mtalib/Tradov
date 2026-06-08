# 2026-05-30 Tradov Codebase Inventory

Date: 2026-05-30

## Scope and Method

- Scope: Python modules under `Tradov/` only.
- Grouping: by series directory (for example `TradovA_Core`, `TradovB_Broker`) with `Tradov_root` for package-root modules.
- LOC metric: physical lines per file from direct line count (`wc -l` equivalent).
- Purpose text: module docstring first line when available, otherwise inferred from module name.

## Executive Summary

- Total groups: 26
- Total modules: 916
- Total LOC: 543,371

### Group Totals

| Group | Series | Modules | LOC |
|---|---:|---:|---:|
| TradovA_Core | A | 8 | 13,416 |
| TradovB_Broker | B | 11 | 12,570 |
| TradovC_MarketData | C | 24 | 25,216 |
| TradovD_Strategies | D | 40 | 52,073 |
| TradovE_Risk | E | 27 | 30,120 |
| TradovF_Analysis | F | 22 | 23,671 |
| TradovG_GUI | G | 133 | 36,681 |
| TradovH_Storage | H | 8 | 6,338 |
| TradovI_Integration | I | 13 | 9,745 |
| TradovJ_Alerts | J | 6 | 5,585 |
| TradovK_Reports | K | 14 | 13,826 |
| TradovL_ML | L | 15 | 18,703 |
| TradovM_Monitoring | M | 8 | 6,598 |
| TradovN_OptionsAnalytics | N | 16 | 16,926 |
| TradovO_TradingIntelligence | O | 4 | 4,853 |
| TradovP_PortfolioMgmt | P | 9 | 10,545 |
| TradovQ_Scripts | Q | 28 | 11,107 |
| TradovR_Runtime | R | 15 | 18,719 |
| TradovS_Signals | S | 19 | 17,066 |
| TradovT_Testing | T | 410 | 142,448 |
| TradovU_Utilities | U | 36 | 20,669 |
| TradovV_QuantModels | V | 10 | 11,245 |
| TradovX_Agents | X | 17 | 19,189 |
| TradovY_AutoAgents | Y | 13 | 7,177 |
| TradovZ_Communication | Z | 9 | 8,791 |
| Tradov_root | - | 1 | 94 |

## Module Inventory

### TradovA_Core (Series A)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovA_Core/TradovA01_Main.py | TRADOV - Autonomous Options Trading System v1.0 | 1,609 |
| Tradov/TradovA_Core/TradovA02_TradingEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 2,467 |
| Tradov/TradovA_Core/TradovA03_Configuration.py | TRADOV - Autonomous Options Trading System v1.0 | 2,030 |
| Tradov/TradovA_Core/TradovA04_Scheduler.py | TRADOV - Autonomous Options Trading System v1.0 | 2,383 |
| Tradov/TradovA_Core/TradovA05_EventManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,510 |
| Tradov/TradovA_Core/TradovA06_MasterController.py | TRADOV - Autonomous Options Trading System v1.0 | 2,061 |
| Tradov/TradovA_Core/TradovA08_FSeriesOrchestrator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,233 |
| Tradov/TradovA_Core/__init__.py | Package initializer for TradovA_Core. | 123 |
| **Subtotal** | **8 modules** | **13,416** |

### TradovB_Broker (Series B)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovB_Broker/TradovB00_OrderTypes.py | TRADOV - Autonomous Options Trading System v1.0 | 951 |
| Tradov/TradovB_Broker/TradovB02_OrderManager.py | TRADOV - Autonomous Options Trading System v1.0 | 2,229 |
| Tradov/TradovB_Broker/TradovB03_PositionTracker.py | TRADOV - Autonomous Options Trading System v1.0 | 769 |
| Tradov/TradovB_Broker/TradovB04_AccountManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,344 |
| Tradov/TradovB_Broker/TradovB06_DashboardOrderManager.py | TRADOV - Autonomous Options Trading System v1.0 | 419 |
| Tradov/TradovB_Broker/TradovB15_PrometheusMetrics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,465 |
| Tradov/TradovB_Broker/TradovB20_IntegratedConnectivityManager.py | TRADOV - Autonomous Options Trading System v1.0 | 190 |
| Tradov/TradovB_Broker/TradovB21_BrokerProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 136 |
| Tradov/TradovB_Broker/TradovB30_SPYOptionsChainManager.py | Module for spyoptionschainmanager functionality. | 1,015 |
| Tradov/TradovB_Broker/TradovB40_TradierClient.py | TRADOV - Autonomous Options Trading System v1.0 | 3,702 |
| Tradov/TradovB_Broker/__init__.py | TRADOV - Autonomous Options Trading System v2.0 | 350 |
| **Subtotal** | **11 modules** | **12,570** |

### TradovC_MarketData (Series C)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovC_MarketData/TradovC00_MarketDataProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 418 |
| Tradov/TradovC_MarketData/TradovC01_DataFeed.py | TRADOV - Autonomous Options Trading System v1.0 | 1,357 |
| Tradov/TradovC_MarketData/TradovC02_HistoricalData.py | TRADOV - Autonomous Options Trading System v1.0 | 937 |
| Tradov/TradovC_MarketData/TradovC03_OptionChain.py | TRADOV - Autonomous Options Trading System v1.0 | 1,100 |
| Tradov/TradovC_MarketData/TradovC04_MarketInternals.py | TRADOV - Autonomous Options Trading System v1.0 | 1,070 |
| Tradov/TradovC_MarketData/TradovC05_VolumeProfile.py | TRADOV - Autonomous Options Trading System v1.0 | 892 |
| Tradov/TradovC_MarketData/TradovC06_DataValidator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,320 |
| Tradov/TradovC_MarketData/TradovC08_SPYFeed.py | TRADOV - Autonomous Options Trading System v1.0 | 876 |
| Tradov/TradovC_MarketData/TradovC09_NewsManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,034 |
| Tradov/TradovC_MarketData/TradovC10_VIXAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,513 |
| Tradov/TradovC_MarketData/TradovC12_DarkPoolFlow.py | TRADOV - Autonomous Options Trading System v1.0 | 769 |
| Tradov/TradovC_MarketData/TradovC13_IndexComponents.py | TRADOV - Autonomous Options Trading System v1.0 | 1,022 |
| Tradov/TradovC_MarketData/TradovC15_MicrostructureAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,288 |
| Tradov/TradovC_MarketData/TradovC16_MarketDataCache.py | TRADOV - Autonomous Options Trading System v1.0 | 911 |
| Tradov/TradovC_MarketData/TradovC17_MarketConfigManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,018 |
| Tradov/TradovC_MarketData/TradovC18_SKEWCalculator.py | TRADOV - Autonomous Options Trading System | 1,286 |
| Tradov/TradovC_MarketData/TradovC19_AfterHoursDataManager.py | TRADOV - Autonomous Options Trading System v1.0 | 812 |
| Tradov/TradovC_MarketData/TradovC22_FactorDataProvider.py | TRADOV - Autonomous Options Trading System v1.0 | 1,311 |
| Tradov/TradovC_MarketData/TradovC23_RealTimeDataOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,218 |
| Tradov/TradovC_MarketData/TradovC24_ModelDataPipeline.py | TRADOV - Autonomous Options Trading System v1.0 | 1,520 |
| Tradov/TradovC_MarketData/TradovC29_DataProviderRouter.py | TRADOV - Autonomous Options Trading System v1.0 | 264 |
| Tradov/TradovC_MarketData/TradovC30_OrderFlowAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,521 |
| Tradov/TradovC_MarketData/TradovC35_SentimentAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,519 |
| Tradov/TradovC_MarketData/__init__.py | TRADOV - Automated SPY Options Trading System | 240 |
| **Subtotal** | **24 modules** | **25,216** |

### TradovD_Strategies (Series D)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovD_Strategies/TradovD00_StrategyConstants.py | TRADOV - Autonomous Options Trading System | 355 |
| Tradov/TradovD_Strategies/TradovD01_BaseStrategy.py | TRADOV - Autonomous Options Trading System v1.0 | 1,075 |
| Tradov/TradovD_Strategies/TradovD02_IronCondor.py | Module for ironcondor functionality. | 1,234 |
| Tradov/TradovD_Strategies/TradovD03_CreditSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 1,026 |
| Tradov/TradovD_Strategies/TradovD04_ZeroDTE.py | TRADOV - Autonomous Options Trading System v1.0 | 1,555 |
| Tradov/TradovD_Strategies/TradovD05_Straddle.py | TRADOV - Autonomous Options Trading System v1.0 | 1,124 |
| Tradov/TradovD_Strategies/TradovD06_BullPutSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 175 |
| Tradov/TradovD_Strategies/TradovD07_BearCallSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 175 |
| Tradov/TradovD_Strategies/TradovD08_OpeningRangeBreakout.py | TRADOV - Autonomous Options Trading System v1.0 | 1,159 |
| Tradov/TradovD_Strategies/TradovD09_GreeksBasedStrategy.py | TRADOV - Autonomous Options Trading System v1.0 | 1,543 |
| Tradov/TradovD_Strategies/TradovD10_IronButterfly.py | Module for ironbutterfly functionality. | 1,165 |
| Tradov/TradovD_Strategies/TradovD11_SpecializedZeroDTE.py | TRADOV - Autonomous Options Trading System v1.0 | 1,308 |
| Tradov/TradovD_Strategies/TradovD12_RSIMeanReversion.py | TRADOV - Autonomous Options Trading System v1.0 | 1,097 |
| Tradov/TradovD_Strategies/TradovD13_MACrossover.py | TRADOV - Autonomous Options Trading System v1.0 | 1,003 |
| Tradov/TradovD_Strategies/TradovD14_CalendarSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 1,388 |
| Tradov/TradovD_Strategies/TradovD15_StraddleStrangle.py | TRADOV - Autonomous Options Trading System v1.0 | 1,406 |
| Tradov/TradovD_Strategies/TradovD16_RatioSpreads.py | TRADOV - Autonomous Options Trading System v1.0 | 1,477 |
| Tradov/TradovD_Strategies/TradovD17_DiagonalSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 1,379 |
| Tradov/TradovD_Strategies/TradovD18_EvolvedCreditSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 1,530 |
| Tradov/TradovD_Strategies/TradovD19_JadeLizard.py | TRADOV - Autonomous Options Trading System v1.0 | 1,275 |
| Tradov/TradovD_Strategies/TradovD20_VerticalSpreadOptimizer.py | TRADOV - Autonomous Options Trading System | 897 |
| Tradov/TradovD_Strategies/TradovD21_DoubleCalendar.py | TRADOV - Autonomous Options Trading System v1.0 | 1,422 |
| Tradov/TradovD_Strategies/TradovD22_AdaptiveVolatility.py | TRADOV - Autonomous Options Trading System | 1,151 |
| Tradov/TradovD_Strategies/TradovD23_BrokenWingButterfly.py | TRADOV - Autonomous Options Trading System v1.0 | 1,105 |
| Tradov/TradovD_Strategies/TradovD24_Butterfly.py | TRADOV - Autonomous Options Trading System v1.0 | 1,017 |
| Tradov/TradovD_Strategies/TradovD25_UnifiedCreditSpreadEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 1,524 |
| Tradov/TradovD_Strategies/TradovD26_GammaScalper.py | TRADOV - Autonomous Options Trading System | 1,174 |
| Tradov/TradovD_Strategies/TradovD27_EarningsStrategy.py | TRADOV - Autonomous Options Trading System v1.0 | 1,260 |
| Tradov/TradovD_Strategies/TradovD28_VIXHedging.py | TRADOV - Autonomous Options Trading System v1.0 | 1,069 |
| Tradov/TradovD_Strategies/TradovD30_RegimeGatedSelector.py | TRADOV - Automated SPY Options Trading System | 1,624 |
| Tradov/TradovD_Strategies/TradovD31_StrategyOrchestrator.py | Module for strategyorchestrator functionality. | 10,126 |
| Tradov/TradovD_Strategies/TradovD32_MultiLegStrategyCoordinator.py | TRADOV - Autonomous Options Trading System v1.0 | 2,577 |
| Tradov/TradovD_Strategies/TradovD33_RenaissanceMeanReversion.py | TRADOV - Autonomous Options Trading System v1.0 | 742 |
| Tradov/TradovD_Strategies/TradovD34_PivotMeanReversion.py | TRADOV - Autonomous Options Trading System v1.0 | 1,039 |
| Tradov/TradovD_Strategies/TradovD35_BullCallSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 190 |
| Tradov/TradovD_Strategies/TradovD36_BearPutSpread.py | TRADOV - Autonomous Options Trading System v1.0 | 190 |
| Tradov/TradovD_Strategies/TradovD37_BullishStrangle.py | TRADOV - Autonomous Options Trading System v1.0 | 328 |
| Tradov/TradovD_Strategies/TradovD38_JadeLizardZero.py | Zero/one-DTE Jade Lizard strategy with intraday-safe time handling. | 768 |
| Tradov/TradovD_Strategies/TradovD39_PutCreditSpread7.py | TRADOV - Autonomous Options Trading System v1.0 | 1,138 |
| Tradov/TradovD_Strategies/__init__.py | Package initializer for TradovD_Strategies. | 283 |
| **Subtotal** | **40 modules** | **52,073** |

### TradovE_Risk (Series E)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovE_Risk/TradovE00_RiskProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 264 |
| Tradov/TradovE_Risk/TradovE01_RiskManager.py | TRADOV - Autonomous Options Trading System v1.0 | 2,100 |
| Tradov/TradovE_Risk/TradovE02_DataFreshnessMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 18 |
| Tradov/TradovE_Risk/TradovE02_PositionSizer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,019 |
| Tradov/TradovE_Risk/TradovE03_StopLossManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,607 |
| Tradov/TradovE_Risk/TradovE04_DrawdownControl.py | TRADOV - Autonomous Options Trading System v1.0 | 903 |
| Tradov/TradovE_Risk/TradovE05_AutomaticRebalancer.py | TRADOV - Autonomous Options Trading System v1.0 | 722 |
| Tradov/TradovE_Risk/TradovE06_RiskMetrics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,162 |
| Tradov/TradovE_Risk/TradovE07_ProbabilisticSharpe.py | TRADOV - Autonomous Options Trading System v1.0 | 702 |
| Tradov/TradovE_Risk/TradovE08_PositionGroupValidator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,146 |
| Tradov/TradovE_Risk/TradovE09_VolatilityRiskManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,092 |
| Tradov/TradovE_Risk/TradovE10_CorrelationRiskManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,943 |
| Tradov/TradovE_Risk/TradovE11_MaxLossProtection.py | TRADOV - Autonomous Options Trading System | 937 |
| Tradov/TradovE_Risk/TradovE12_PortfolioVaR.py | TRADOV - Autonomous Options Trading System | 1,430 |
| Tradov/TradovE_Risk/TradovE13_DayProfitTarget.py | Module for dayprofittarget functionality. | 2,400 |
| Tradov/TradovE_Risk/TradovE14_KellyPositionSizer.py | TRADOV - Automated SPY Options Trading System | 715 |
| Tradov/TradovE_Risk/TradovE15_GreekLimitsManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,186 |
| Tradov/TradovE_Risk/TradovE16_CircuitBreakerProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 507 |
| Tradov/TradovE_Risk/TradovE17_RealTimeStressTesting.py | TRADOV - Autonomous Options Trading System v1.0 | 1,617 |
| Tradov/TradovE_Risk/TradovE18_FSeriesRiskIntegrator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,345 |
| Tradov/TradovE_Risk/TradovE19_UnifiedRiskCoordinator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,188 |
| Tradov/TradovE_Risk/TradovE20_FrustrationAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,625 |
| Tradov/TradovE_Risk/TradovE21_HMMRegimeDetector.py | TRADOV - Automated SPY Options Trading System | 1,080 |
| Tradov/TradovE_Risk/TradovE22_KernelRegression.py | TRADOV - Automated SPY Options Trading System | 832 |
| Tradov/TradovE_Risk/TradovE23_PortfolioOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 2,051 |
| Tradov/TradovE_Risk/TradovE24_DataFreshnessMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 324 |
| Tradov/TradovE_Risk/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 205 |
| **Subtotal** | **27 modules** | **30,120** |

### TradovF_Analysis (Series F)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovF_Analysis/TradovF00_AnalysisProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 267 |
| Tradov/TradovF_Analysis/TradovF01_Indicators.py | TRADOV - Autonomous Options Trading System v1.0 | 900 |
| Tradov/TradovF_Analysis/TradovF02_PriceAction.py | TRADOV - Autonomous Options Trading System v1.0 | 872 |
| Tradov/TradovF_Analysis/TradovF03_SupportResistance.py | TRADOV - Autonomous Options Trading System v1.0 | 792 |
| Tradov/TradovF_Analysis/TradovF04_VolatilityAnalysis.py | TRADOV - Autonomous Options Trading System v1.0 | 922 |
| Tradov/TradovF_Analysis/TradovF05_TrendDetection.py | TRADOV - Autonomous Options Trading System v1.0 | 776 |
| Tradov/TradovF_Analysis/TradovF06_GreeksCalculator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,013 |
| Tradov/TradovF_Analysis/TradovF07_GapAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 758 |
| Tradov/TradovF_Analysis/TradovF08_VolatilityRegime.py | TRADOV - Autonomous Options Trading System v1.0 | 999 |
| Tradov/TradovF_Analysis/TradovF09_EntryFilters.py | TRADOV - Autonomous Options Trading System v1.0 | 2,541 |
| Tradov/TradovF_Analysis/TradovF10_MarketRegimeDetector.py | TRADOV - Autonomous Options Trading System v1.0 | 1,517 |
| Tradov/TradovF_Analysis/TradovF11_GreeksAggregator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,047 |
| Tradov/TradovF_Analysis/TradovF13_ModelValidation.py | TRADOV - Autonomous Options Trading System v1.0 | 1,436 |
| Tradov/TradovF_Analysis/TradovF14_MarketMicrostructure.py | TRADOV - Autonomous Options Trading System v1.0 | 1,548 |
| Tradov/TradovF_Analysis/TradovF16_RealTimeAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,689 |
| Tradov/TradovF_Analysis/TradovF17_UnifiedPerformanceEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 1,532 |
| Tradov/TradovF_Analysis/TradovF18_MaxPainCalculator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,072 |
| Tradov/TradovF_Analysis/TradovF19_AnchoredVWAP.py | TRADOV - Autonomous Options Trading System v1.0 | 1,184 |
| Tradov/TradovF_Analysis/TradovF20_Indicators.py | TRADOV - Autonomous Options Trading System v1.0 | 391 |
| Tradov/TradovF_Analysis/TradovF21_RenaissanceIndicators.py | TRADOV - Autonomous Options Trading System v1.0 | 860 |
| Tradov/TradovF_Analysis/TradovF22_MLPrediction.py | TRADOV - Autonomous Options Trading System v1.0 | 1,398 |
| Tradov/TradovF_Analysis/__init__.py | TRADOV - Automated SPY Options Trading System | 157 |
| **Subtotal** | **22 modules** | **23,671** |

### TradovG_GUI (Series G)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovG_GUI/TradovG00_ApplicationManager.py | TRADOV - Autonomous Options Trading System v1.0 | 463 |
| Tradov/TradovG_GUI/TradovG01_MainWindow.py | TRADOV - Autonomous Options Trading System v1.0 | 96 |
| Tradov/TradovG_GUI/TradovG02_GUIEntry.py | TRADOV - Autonomous Options Trading System v1.0 | 128 |
| Tradov/TradovG_GUI/TradovG03_OptionChainWidget.py | TRADOV - Autonomous Options Trading System v1.0 | 227 |
| Tradov/TradovG_GUI/TradovG04_ChartWidget.py | TRADOV - Autonomous Options Trading System v1.0 | 1,632 |
| Tradov/TradovG_GUI/TradovG05_TradingDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 9,190 |
| Tradov/TradovG_GUI/TradovG06_DashboardData.py | TRADOV - Autonomous Options Trading System v1.0 | 756 |
| Tradov/TradovG_GUI/TradovG09_RiskParametersDialog.py | TRADOV - Autonomous Options Trading System v1.0 | 1,200 |
| Tradov/TradovG_GUI/TradovG100_PositionUpdatedEventHelper.py | Pure parsing for dashboard POSITION_UPDATED events. | 19 |
| Tradov/TradovG_GUI/TradovG101_RecentDecisionFlowFetchHelper.py | Pure fetch-plan helpers for recent decision-flow diagnostics. | 29 |
| Tradov/TradovG_GUI/TradovG102_MetricsOrchestratorStartHelper.py | Pure start-plan helpers for the custom metrics orchestrator. | 34 |
| Tradov/TradovG_GUI/TradovG103_LiveToPaperSwitchHelper.py | Pure dialog plans for the LIVE-to-PAPER mode switch. | 54 |
| Tradov/TradovG_GUI/TradovG104_MetricsSnapshotProbeHelper.py | Pure snapshot-probe helpers for the custom metrics orchestrator. | 43 |
| Tradov/TradovG_GUI/TradovG105_PaperToLiveSwitchHelper.py | Pure dialog and confirmation plans for the PAPER-to-LIVE switch. | 62 |
| Tradov/TradovG_GUI/TradovG106_CustomMetricWidgetUpdateHelper.py | Pure widget-update planning for one S07 custom metric entry. | 62 |
| Tradov/TradovG_GUI/TradovG107_CustomMetricSignalPanelSyncHelper.py | Pure signal-panel sync planning for S07 custom metrics. | 73 |
| Tradov/TradovG_GUI/TradovG108_CustomMetricBreadthDialogSyncHelper.py | Pure breadth-dialog sync planning for S07 custom metrics. | 64 |
| Tradov/TradovG_GUI/TradovG109_RegimePillStateHelper.py | Pure regime-pill state planning for dashboard updates. | 143 |
| Tradov/TradovG_GUI/TradovG110_RegimePillStatusHelper.py | Pure stance/stress/gate planning for the regime pill bar. | 60 |
| Tradov/TradovG_GUI/TradovG111_RegimeDispatchAnnouncementHelper.py | Pure dispatch announcement planning for the regime pill bar. | 66 |
| Tradov/TradovG_GUI/TradovG112_CloseStrategyConfirmHelper.py | Pure confirmation dialog planning for close-strategy UX. | 59 |
| Tradov/TradovG_GUI/TradovG113_CloseStrategySuccessHelper.py | Pure success-path UX planning for close-strategy actions. | 40 |
| Tradov/TradovG_GUI/TradovG114_CloseStrategyFailureHelper.py | Pure failure-path UX planning for close-strategy actions. | 41 |
| Tradov/TradovG_GUI/TradovG115_EventSubscriptionPlanHelper.py | Pure subscription planning for dashboard event wiring. | 63 |
| Tradov/TradovG_GUI/TradovG116_EventClockRiskEventHelper.py | Pure event-clock risk-event normalization for the dashboard. | 59 |
| Tradov/TradovG_GUI/TradovG117_EventClockOverrideHelper.py | Pure manual event-clock override planning for the dashboard. | 38 |
| Tradov/TradovG_GUI/TradovG118_PaperRiskLimitMappingHelper.py | Pure mapping from dashboard risk params to E01 risk limits. | 50 |
| Tradov/TradovG_GUI/TradovG119_RingLogBufferHelper.py | Pure ring-log buffering and refresh planning for the dashboard. | 71 |
| Tradov/TradovG_GUI/TradovG11_SkewMonitorDialog.py | TRADOV - Autonomous Options Trading System | 1,381 |
| Tradov/TradovG_GUI/TradovG120_SystemLogSuppressionHelper.py | Pure system-log suppression helpers for dashboard log filtering. | 74 |
| Tradov/TradovG_GUI/TradovG121_AutomationLogRoutingHelper.py | Pure routing and formatting for dashboard automation logs. | 36 |
| Tradov/TradovG_GUI/TradovG122_SystemLogVerbosityHelper.py | Pure planning for dashboard system-log verbosity state. | 48 |
| Tradov/TradovG_GUI/TradovG123_VetoToggleButtonHelper.py | Pure veto toggle button presentation for the dashboard. | 40 |
| Tradov/TradovG_GUI/TradovG124_VetoToggleResultHelper.py | Pure veto toggle outcome planning for the dashboard. | 37 |
| Tradov/TradovG_GUI/TradovG125_VetoControlsStateHelper.py | Pure veto controls state resolution for the dashboard. | 36 |
| Tradov/TradovG_GUI/TradovG126_VetoControlsPersistPlanHelper.py | Pure veto controls persistence planning for the dashboard. | 42 |
| Tradov/TradovG_GUI/TradovG127_StartupReadinessStateEnvelopeHelper.py | Pure startup-readiness state envelope shaping for dashboard startup UX. | 42 |
| Tradov/TradovG_GUI/TradovG128_DashboardSnapshotPayloadHelper.py | Pure dashboard snapshot payload shaping for cold-start restore. | 58 |
| Tradov/TradovG_GUI/TradovG129_MetricsPayloadMergeHelper.py | Pure merge logic for Market Overview metrics payloads. | 42 |
| Tradov/TradovG_GUI/TradovG12_SignalInfoDialog.py | TRADOV - Autonomous Options Trading System | 683 |
| Tradov/TradovG_GUI/TradovG130_CachedMetricsFallbackHelper.py | Pure fallback payload normalization for cached Market Overview metrics. | 113 |
| Tradov/TradovG_GUI/TradovG131_CachedMarketSnapshotMergeHelper.py | Pure merge logic for startup market snapshot restoration. | 33 |
| Tradov/TradovG_GUI/TradovG132_CachedChartCandlesHelper.py | Pure selection logic for cached chart candle payloads. | 20 |
| Tradov/TradovG_GUI/TradovG133_CachedChartBarSeriesHelper.py | Pure cached chart bar parsing and filtering helpers. | 66 |
| Tradov/TradovG_GUI/TradovG13_EnhancedWidgets.py | TRADOV - Autonomous Options Trading System v1.0 | 1,925 |
| Tradov/TradovG_GUI/TradovG14_Dashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 128 |
| Tradov/TradovG_GUI/TradovG15_ConnectAPIStatus.py | TRADOV - Autonomous Options Trading System v1.0 | 792 |
| Tradov/TradovG_GUI/TradovG16_CircuitBreakerMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 311 |
| Tradov/TradovG_GUI/TradovG17_MarketInternalsWidget.py | TRADOV - Autonomous Options Trading System v1.0 | 856 |
| Tradov/TradovG_GUI/TradovG17_PaperPositionResolver.py | TRADOV - Autonomous Options Trading System v1.0 | 641 |
| Tradov/TradovG_GUI/TradovG18_MarketDataWorker.py | TRADOV - Autonomous Options Trading System v1.0 | 1,774 |
| Tradov/TradovG_GUI/TradovG19_ChartIndicators.py | TRADOV - Autonomous Options Trading System v1.0 | 188 |
| Tradov/TradovG_GUI/TradovG20_DashboardBuilder.py | TRADOV - Autonomous Options Trading System v1.0 | 1,769 |
| Tradov/TradovG_GUI/TradovG21_DashboardSignalHandlers.py | Signal-handler helpers for TradovG05_TradingDashboard. | 169 |
| Tradov/TradovG_GUI/TradovG22_TradeAuditDialog.py | TRADOV - Autonomous Options Trading System v1.0 | 350 |
| Tradov/TradovG_GUI/TradovG23_DecisionLogDialog.py | TRADOV - Autonomous Options Trading System v1.0 | 461 |
| Tradov/TradovG_GUI/TradovG24_PnlMetricsResolver.py | TRADOV - Autonomous Options Trading System v1.0 | 277 |
| Tradov/TradovG_GUI/TradovG25_DashboardSessionAdapter.py | TRADOV - Autonomous Options Trading System v1.0 | 109 |
| Tradov/TradovG_GUI/TradovG26_RecentTradeFormatter.py | TRADOV - Autonomous Options Trading System v1.0 | 105 |
| Tradov/TradovG_GUI/TradovG27_RecentTradesDialog.py | TRADOV - Autonomous Options Trading System v1.0 | 258 |
| Tradov/TradovG_GUI/TradovG28_AccountPanelPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 96 |
| Tradov/TradovG_GUI/TradovG29_ChartWidgetPlotly.py | TRADOV - Autonomous Options Trading System v1.0 | 856 |
| Tradov/TradovG_GUI/TradovG30_PlotlyDataBridge.py | TRADOV - Autonomous Options Trading System v1.0 | 555 |
| Tradov/TradovG_GUI/TradovG31_PlotlyTemplates.py | TRADOV - Autonomous Options Trading System v1.0 | 747 |
| Tradov/TradovG_GUI/TradovG32_AgentHealthDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 302 |
| Tradov/TradovG_GUI/TradovG33_AccountSnapshotSelector.py | TRADOV - Autonomous Options Trading System v1.0 | 30 |
| Tradov/TradovG_GUI/TradovG34_AccountCapitalMath.py | TRADOV - Autonomous Options Trading System v1.0 | 95 |
| Tradov/TradovG_GUI/TradovG35_PaperSummaryPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 196 |
| Tradov/TradovG_GUI/TradovG36_StripMetricsPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 117 |
| Tradov/TradovG_GUI/TradovG37_GreekBarPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 64 |
| Tradov/TradovG_GUI/TradovG38_LegacySpreadsTablePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 53 |
| Tradov/TradovG_GUI/TradovG39_PaperPositionsTreePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 815 |
| Tradov/TradovG_GUI/TradovG40_ToolbarIndexPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 262 |
| Tradov/TradovG_GUI/TradovG41_RegimeLiquidityPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 125 |
| Tradov/TradovG_GUI/TradovG42_PCADetailPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 464 |
| Tradov/TradovG_GUI/TradovG43_CustomMetricDialogPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 328 |
| Tradov/TradovG_GUI/TradovG44_RecentDecisionFlowPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 66 |
| Tradov/TradovG_GUI/TradovG45_ExecutionHealthPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 78 |
| Tradov/TradovG_GUI/TradovG46_ReadinessStatusPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 106 |
| Tradov/TradovG_GUI/TradovG47_EventClockDisplayPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 55 |
| Tradov/TradovG_GUI/TradovG48_TradingArmingPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 71 |
| Tradov/TradovG_GUI/TradovG49_TradingWindowBadgePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 38 |
| Tradov/TradovG_GUI/TradovG50_EntryBlockCompactPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 85 |
| Tradov/TradovG_GUI/TradovG51_ModeTitlePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 39 |
| Tradov/TradovG_GUI/TradovG52_RegimePillBarPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 374 |
| Tradov/TradovG_GUI/TradovG53_GoNoGoPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 63 |
| Tradov/TradovG_GUI/TradovG54_ReadinessResultPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 52 |
| Tradov/TradovG_GUI/TradovG55_ReadinessReportPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 46 |
| Tradov/TradovG_GUI/TradovG56_ReadinessStartGatePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 68 |
| Tradov/TradovG_GUI/TradovG57_StartTradingPrecheckPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 71 |
| Tradov/TradovG_GUI/TradovG58_StartTradingLiveGuardPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 52 |
| Tradov/TradovG_GUI/TradovG59_StartTradingFailurePresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 31 |
| Tradov/TradovG_GUI/TradovG60_ReadinessStartBlockPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 42 |
| Tradov/TradovG_GUI/TradovG61_ReadinessAsyncPresenter.py | TRADOV - Autonomous Options Trading System v1.0 | 48 |
| Tradov/TradovG_GUI/TradovG62_ReadinessWorkerCleanupHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 39 |
| Tradov/TradovG_GUI/TradovG63_ReadinessSnapshotHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 47 |
| Tradov/TradovG_GUI/TradovG64_ReadinessConnectionRefreshHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 50 |
| Tradov/TradovG_GUI/TradovG65_ReadinessEventClockSnapshotHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 34 |
| Tradov/TradovG_GUI/TradovG66_ReadinessStartupStateHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 37 |
| Tradov/TradovG_GUI/TradovG67_ReadinessDecisionHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 72 |
| Tradov/TradovG_GUI/TradovG68_ReadinessBypassAuditHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 47 |
| Tradov/TradovG_GUI/TradovG69_LiveDataStatusHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 29 |
| Tradov/TradovG_GUI/TradovG70_ReadinessCacheDecisionHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 43 |
| Tradov/TradovG_GUI/TradovG71_ReadinessGateDecisionHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 49 |
| Tradov/TradovG_GUI/TradovG72_PaperSessionQueueHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 66 |
| Tradov/TradovG_GUI/TradovG73_PaperSessionFinalizeHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 36 |
| Tradov/TradovG_GUI/TradovG74_SessionSupervisorStartHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 36 |
| Tradov/TradovG_GUI/TradovG75_SessionSupervisorStartAttemptHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 43 |
| Tradov/TradovG_GUI/TradovG76_SessionSupervisorAdoptionHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 55 |
| Tradov/TradovG_GUI/TradovG77_LoadingTransitionCompletionHelper.py | TRADOV - Autonomous Options Trading System v1.0 | 47 |
| Tradov/TradovG_GUI/TradovG78_LoadingTransitionBeginHelper.py | Pure plan builder for beginning the paper loading transition. | 38 |
| Tradov/TradovG_GUI/TradovG79_StartButtonReadyStateHelper.py | Pure plan builder for restoring the idle Start Trading button. | 41 |
| Tradov/TradovG_GUI/TradovG80_StartButtonActiveStateHelper.py | Pure plan builder for the steady-state active Start Trading button. | 51 |
| Tradov/TradovG_GUI/TradovG81_MarketWorkerSlotInvokeHelper.py | Pure plan builder for market-worker slot invocation. | 37 |
| Tradov/TradovG_GUI/TradovG82_QThreadShutdownHelper.py | Pure plan builder for Qt thread shutdown outcomes. | 42 |
| Tradov/TradovG_GUI/TradovG83_MetricsOrchestratorShutdownHelper.py | Pure plan builder for dashboard metrics orchestrator shutdown. | 38 |
| Tradov/TradovG_GUI/TradovG84_MarketWorkerSignalEmitHelper.py | Pure plan builder for market-worker signal emission. | 26 |
| Tradov/TradovG_GUI/TradovG85_MarketWorkerSignalDisconnectHelper.py | Pure plan builder for market-worker signal disconnect selection. | 30 |
| Tradov/TradovG_GUI/TradovG86_ShutdownTimerStopHelper.py | Pure plan builder for early shutdown timer stop selection. | 31 |
| Tradov/TradovG_GUI/TradovG87_PostWorkerShutdownTimerHelper.py | Pure plan builder for late shutdown timer stop selection. | 26 |
| Tradov/TradovG_GUI/TradovG88_MarketWorkerShutdownHelper.py | Pure plan builder for market-worker shutdown gating. | 25 |
| Tradov/TradovG_GUI/TradovG89_ShutdownMessageHelper.py | Pure shutdown message copy for dashboard close and snapshot save paths. | 25 |
| Tradov/TradovG_GUI/TradovG90_CloseEventShutdownSequenceHelper.py | Pure shutdown sequence plan for dashboard closeEvent orchestration. | 58 |
| Tradov/TradovG_GUI/TradovG91_StartupReadinessLogHelper.py | Pure startup-readiness log and button presentation for dashboard warmup. | 96 |
| Tradov/TradovG_GUI/TradovG92_StartupReadinessBannerHelper.py | Pure startup-readiness banner copy for the dashboard startup ring buffer. | 74 |
| Tradov/TradovG_GUI/TradovG93_StartupReadinessStateHelper.py | Pure startup-readiness state assembly for dashboard startup UX. | 62 |
| Tradov/TradovG_GUI/TradovG94_StartupReadinessRefreshHelper.py | Pure orchestration plan for post-paint startup-readiness refresh. | 35 |
| Tradov/TradovG_GUI/TradovG95_DJIProxyMultiplierHelper.py | Pure normalization helper for the dashboard DJI proxy multiplier. | 19 |
| Tradov/TradovG_GUI/TradovG96_RiskAlertDispatchHelper.py | Pure dedupe and dispatch plan for dashboard risk alert events. | 43 |
| Tradov/TradovG_GUI/TradovG97_PendingOrdersGateHelper.py | Pure prompt and outcome copy for the dashboard pending-orders gate. | 79 |
| Tradov/TradovG_GUI/TradovG98_ExecutionTelemetryEventHelper.py | Pure parsing for dashboard execution-telemetry events. | 33 |
| Tradov/TradovG_GUI/TradovG99_GUILogHandler.py | TRADOV - Autonomous Options Trading System v1.0 | 537 |
| Tradov/TradovG_GUI/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 329 |
| **Subtotal** | **133 modules** | **36,681** |

### TradovH_Storage (Series H)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovH_Storage/TradovH01_DataAccessLayer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,090 |
| Tradov/TradovH_Storage/TradovH02_DatabaseManager.py | TRADOV - Autonomous Options Trading System | 938 |
| Tradov/TradovH_Storage/TradovH03_MarketDataCache.py | TRADOV - Autonomous Options Trading System v1.0 | 692 |
| Tradov/TradovH_Storage/TradovH04_TradeRepository.py | TRADOV - Autonomous Options Trading System v1.0 | 777 |
| Tradov/TradovH_Storage/TradovH05_TradingSessionDB.py | TRADOV - Autonomous Options Trading System v1.0 | 1,325 |
| Tradov/TradovH_Storage/TradovH07_PerformanceAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 856 |
| Tradov/TradovH_Storage/TradovH08_TradeJournal.py | TRADOV - Autonomous Options Trading System v1.0 | 575 |
| Tradov/TradovH_Storage/__init__.py | Package initializer for TradovH_Storage. | 85 |
| **Subtotal** | **8 modules** | **6,338** |

### TradovI_Integration (Series I)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovI_Integration/TradovI01_IntegrationHub.py | TRADOV - Autonomous Options Trading System v1.0 | 829 |
| Tradov/TradovI_Integration/TradovI02_EventRouter.py | TRADOV - Autonomous Options Trading System v1.0 | 1,150 |
| Tradov/TradovI_Integration/TradovI03_ConfigManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,431 |
| Tradov/TradovI_Integration/TradovI04_DiagnosticsEngine_Core.py | TRADOV - Autonomous Options Trading System v1.0 | 596 |
| Tradov/TradovI_Integration/TradovI05_DiagnosticsEngine_Analyzers.py | TRADOV - Autonomous Options Trading System v1.0 | 316 |
| Tradov/TradovI_Integration/TradovI06_AgentMessageBus.py | TRADOV - Autonomous Options Trading System | 1,380 |
| Tradov/TradovI_Integration/TradovI07_SyntaxValidator.py | TRADOV - Autonomous Options Trading System | 819 |
| Tradov/TradovI_Integration/TradovI08_DiagnosticsEngine_DataCollector.py | TRADOV - Autonomous Options Trading System v1.0 | 650 |
| Tradov/TradovI_Integration/TradovI09_DiagnosticsEngine_HealthChecks.py | TRADOV - Autonomous Options Trading System v1.0 | 706 |
| Tradov/TradovI_Integration/TradovI10_DiagnosticsEngine_Types.py | TRADOV - Autonomous Options Trading System v1.0 | 441 |
| Tradov/TradovI_Integration/TradovI11_DiagnosticsEngine_Utils.py | TRADOV - Autonomous Options Trading System v1.0 | 669 |
| Tradov/TradovI_Integration/TradovI12_ModuleRegistry.py | TRADOV - Autonomous Options Trading System v1.0 | 452 |
| Tradov/TradovI_Integration/__init__.py | Package initializer for TradovI_Integration. | 306 |
| **Subtotal** | **13 modules** | **9,745** |

### TradovJ_Alerts (Series J)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovJ_Alerts/TradovJ01_AlertManager.py | TRADOV - Autonomous Options Trading System v1.0 | 784 |
| Tradov/TradovJ_Alerts/TradovJ02_EmailNotifier.py | TRADOV - Autonomous Options Trading System v1.0 | 825 |
| Tradov/TradovJ_Alerts/TradovJ03_WebhookNotifier.py | TRADOV - Autonomous Options Trading System v1.0 | 384 |
| Tradov/TradovJ_Alerts/TradovJ04_DesktopNotifier.py | TRADOV - Autonomous Options Trading System v1.0 | 781 |
| Tradov/TradovJ_Alerts/TradovJ05_TelegramBot.py | TRADOV - Autonomous Options Trading System v1.0 | 2,755 |
| Tradov/TradovJ_Alerts/__init__.py | TRADOV - Automated SPY Options Trading System | 56 |
| **Subtotal** | **6 modules** | **5,585** |

### TradovK_Reports (Series K)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovK_Reports/TradovK01_ReportGenerator.py | TRADOV - Autonomous Options Trading System v1.0 | 299 |
| Tradov/TradovK_Reports/TradovK02_DailyTradingReport.py | TRADOV - Autonomous Options Trading System v1.0 | 1,868 |
| Tradov/TradovK_Reports/TradovK03_PerformanceDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 939 |
| Tradov/TradovK_Reports/TradovK04_ExecutionAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,146 |
| Tradov/TradovK_Reports/TradovK05_RiskReport.py | TRADOV - Autonomous Options Trading System v1.0 | 805 |
| Tradov/TradovK_Reports/TradovK06_PortfolioAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,454 |
| Tradov/TradovK_Reports/TradovK07_StrategyComparison.py | TRADOV - Autonomous Options Trading System v1.0 | 895 |
| Tradov/TradovK_Reports/TradovK08_MLPerformanceReport.py | TRADOV - Autonomous Options Trading System v1.0 | 1,625 |
| Tradov/TradovK_Reports/TradovK09_RegulatoryReports.py | TRADOV - Autonomous Options Trading System v1.0 | 1,417 |
| Tradov/TradovK_Reports/TradovK10_RealTimePerformanceAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,103 |
| Tradov/TradovK_Reports/TradovK11_UnifiedSharpeDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 957 |
| Tradov/TradovK_Reports/TradovK12_InstitutionalTearSheet.py | TRADOV - Autonomous Options Trading System v1.0 | 787 |
| Tradov/TradovK_Reports/TradovK13_StrategyPnLLadder.py | TRADOV - Autonomous Options Trading System v1.0 | 404 |
| Tradov/TradovK_Reports/__init__.py | TRADOV - Automated SPY Options Trading System | 127 |
| **Subtotal** | **14 modules** | **13,826** |

### TradovL_ML (Series L)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovL_ML/TradovL01_MLPredictor.py | TRADOV - Autonomous Options Trading System v1.0 | 1,169 |
| Tradov/TradovL_ML/TradovL07_PaperTradeLearner.py | TRADOV - Autonomous Options Trading System v1.0 | 1,675 |
| Tradov/TradovL_ML/TradovL08_EntryOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,895 |
| Tradov/TradovL_ML/TradovL09_UnifiedRegimeEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 2,426 |
| Tradov/TradovL_ML/TradovL10_FeatureEngineering.py | TRADOV - Autonomous Options Trading System v1.0 | 1,314 |
| Tradov/TradovL_ML/TradovL11_MLModelManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,168 |
| Tradov/TradovL_ML/TradovL12_RandomForestEnsemble.py | TRADOV - Autonomous Options Trading System v1.0 | 765 |
| Tradov/TradovL_ML/TradovL13_LSTMPricer.py | TRADOV - Autonomous Options Trading System v1.0 | 823 |
| Tradov/TradovL_ML/TradovL14_RealTimePredictor.py | TRADOV - Autonomous Options Trading System v1.0 | 827 |
| Tradov/TradovL_ML/TradovL15_MomentPredictor.py | TRADOV - Autonomous Options Trading System v1.0 | 753 |
| Tradov/TradovL_ML/TradovL16_OptionsAdjustmentRL.py | TRADOV - Autonomous Options Trading System v1.0 | 2,030 |
| Tradov/TradovL_ML/TradovL17_FederatedLearning.py | TRADOV - Autonomous Options Trading System v1.0 | 1,683 |
| Tradov/TradovL_ML/TradovL18_EnhancedMLIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 1,246 |
| Tradov/TradovL_ML/TradovL19_RLTrainingPipeline.py | TRADOV - Autonomous Options Trading System v1.0 | 795 |
| Tradov/TradovL_ML/__init__.py | TRADOV - Automated SPY Options Trading System | 134 |
| **Subtotal** | **15 modules** | **18,703** |

### TradovM_Monitoring (Series M)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovM_Monitoring/TradovM01_SystemMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 962 |
| Tradov/TradovM_Monitoring/TradovM03_AIAgentMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 878 |
| Tradov/TradovM_Monitoring/TradovM04_TradingMetrics.py | TRADOV - Autonomous Options Trading System v1.0 | 1,125 |
| Tradov/TradovM_Monitoring/TradovM05_TransactionCostAnalysis.py | TRADOV - Autonomous Options Trading System | 1,349 |
| Tradov/TradovM_Monitoring/TradovM06_HMMRegimeDetector.py | TRADOV - Autonomous Options Trading System | 1,494 |
| Tradov/TradovM_Monitoring/TradovM07_MigrationMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 372 |
| Tradov/TradovM_Monitoring/TradovM08_HealthEndpoint.py | TRADOV - Autonomous Options Trading System v1.0 | 342 |
| Tradov/TradovM_Monitoring/__init__.py | TRADOV - Automated SPY Options Trading System | 76 |
| **Subtotal** | **8 modules** | **6,598** |

### TradovN_OptionsAnalytics (Series N)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovN_OptionsAnalytics/TradovN01_OptionsPricer.py | TRADOV - Autonomous Options Trading System | 1,219 |
| Tradov/TradovN_OptionsAnalytics/TradovN02_ImpliedVolatilityEngine.py | TRADOV - Autonomous Options Trading System | 1,297 |
| Tradov/TradovN_OptionsAnalytics/TradovN03_OptionsChainManager.py | TRADOV - Autonomous Options Trading System | 1,280 |
| Tradov/TradovN_OptionsAnalytics/TradovN04_OptionsGreeksCalculator.py | TRADOV - Autonomous Options Trading System | 1,705 |
| Tradov/TradovN_OptionsAnalytics/TradovN05_OptionsExpirationManager.py | TRADOV - Autonomous Options Trading System | 1,146 |
| Tradov/TradovN_OptionsAnalytics/TradovN06_VolatilitySurfaceBuilder.py | TRADOV - Autonomous Options Trading System | 1,209 |
| Tradov/TradovN_OptionsAnalytics/TradovN07_OPRAGreeksHandler.py | TRADOV - Autonomous Options Trading System | 125 |
| Tradov/TradovN_OptionsAnalytics/TradovN07_OptionsFlowTracker.py | TRADOV - Autonomous Options Trading System | 1,219 |
| Tradov/TradovN_OptionsAnalytics/TradovN08_VolatilitySurface.py | TRADOV - Autonomous Options Trading System v1.0 | 1,384 |
| Tradov/TradovN_OptionsAnalytics/TradovN09_GammaExposure.py | TRADOV - Autonomous Options Trading System v1.0 | 1,345 |
| Tradov/TradovN_OptionsAnalytics/TradovN10_OptionsFlowAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 638 |
| Tradov/TradovN_OptionsAnalytics/TradovN11_OptionsGreeksFlow.py | TRADOV - Autonomous Options Trading System v1.0 | 1,238 |
| Tradov/TradovN_OptionsAnalytics/TradovN12_VolatilitySurfaceAI.py | TRADOV - Autonomous Options Trading System v1.0 | 1,281 |
| Tradov/TradovN_OptionsAnalytics/TradovN13_MarketImpactModel.py | TRADOV - Autonomous Options Trading System | 1,250 |
| Tradov/TradovN_OptionsAnalytics/TradovN14_OptionsDataVetter.py | TRADOV - Autonomous Options Trading System v1.0 | 465 |
| Tradov/TradovN_OptionsAnalytics/__init__.py | TRADOV - Automated SPY Options Trading System | 125 |
| **Subtotal** | **16 modules** | **16,926** |

### TradovO_TradingIntelligence (Series O)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovO_TradingIntelligence/TradovO01_CoreTechnicalIndicators.py | TRADOV - Autonomous Options Trading System v1.0 | 1,281 |
| Tradov/TradovO_TradingIntelligence/TradovO02_TradingOpportunityScanner.py | TRADOV - Autonomous Options Trading System v1.0 | 1,340 |
| Tradov/TradovO_TradingIntelligence/TradovO03_StrategyOptimizers.py | TRADOV - Autonomous Options Trading System v1.0 | 1,883 |
| Tradov/TradovO_TradingIntelligence/__init__.py | Package initializer for TradovO_TradingIntelligence. | 349 |
| **Subtotal** | **4 modules** | **4,853** |

### TradovP_PortfolioMgmt (Series P)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovP_PortfolioMgmt/TradovP00_GlobalPortfolioRegistry.py | Lightweight global PortfolioManager registry for startup-sensitive paths. | 49 |
| Tradov/TradovP_PortfolioMgmt/TradovP01_PortfolioManager.py | TRADOV - Autonomous Options Trading System v1.0 | 2,233 |
| Tradov/TradovP_PortfolioMgmt/TradovP02_AllocationOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 2,225 |
| Tradov/TradovP_PortfolioMgmt/TradovP03_CorrelationAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 736 |
| Tradov/TradovP_PortfolioMgmt/TradovP04_CapitalAllocator.py | TRADOV - Autonomous Options Trading System | 1,638 |
| Tradov/TradovP_PortfolioMgmt/TradovP05_MultiStrategyAllocator.py | TRADOV - Autonomous Options Trading System | 1,355 |
| Tradov/TradovP_PortfolioMgmt/TradovP06_StrategyRotation.py | TRADOV - Autonomous Options Trading System | 1,314 |
| Tradov/TradovP_PortfolioMgmt/TradovP07_RenaissancePositionSizer.py | TRADOV - Autonomous Options Trading System v1.0 | 686 |
| Tradov/TradovP_PortfolioMgmt/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 309 |
| **Subtotal** | **9 modules** | **10,545** |

### TradovQ_Scripts (Series Q)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovQ_Scripts/TradovQ01_FixExceptionHandling.py | TRADOV - Autonomous Options Trading System v1.0 | 485 |
| Tradov/TradovQ_Scripts/TradovQ02_ValidateEnv.py | TRADOV - Autonomous Options Trading System v1.0 | 348 |
| Tradov/TradovQ_Scripts/TradovQ03_ValidateConfiguration.py | TRADOV - Autonomous Options Trading System v1.0 | 409 |
| Tradov/TradovQ_Scripts/TradovQ04_LaunchDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 520 |
| Tradov/TradovQ_Scripts/TradovQ05_LaunchDashboardProactive.py | TRADOV - Autonomous Options Trading System v1.0 | 569 |
| Tradov/TradovQ_Scripts/TradovQ06_LaunchDashboardDirect.py | TRADOV - Autonomous Options Trading System v1.0 | 589 |
| Tradov/TradovQ_Scripts/TradovQ07_TestGUILogging.py | TRADOV - Autonomous Options Trading System v1.0 | 165 |
| Tradov/TradovQ_Scripts/TradovQ08_ValidatePackageExports.py | TRADOV - Autonomous Options Trading System v1.0 | 386 |
| Tradov/TradovQ_Scripts/TradovQ09_ValidateMissingExports.py | TRADOV - Autonomous Options Trading System v1.0 | 375 |
| Tradov/TradovQ_Scripts/TradovQ10_ProtocolComplianceGate.py | TRADOV - Autonomous Options Trading System v1.0 | 498 |
| Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py | TRADOV - Autonomous Options Trading System v1.0 | 891 |
| Tradov/TradovQ_Scripts/TradovQ24_ProductionWatchdog.py | TRADOV - Autonomous Options Trading System v1.0 | 377 |
| Tradov/TradovQ_Scripts/TradovQ25_SystemMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 184 |
| Tradov/TradovQ_Scripts/TradovQ45_Diagnostics.py | TRADOV - Autonomous Options Trading System v1.0 | 261 |
| Tradov/TradovQ_Scripts/TradovQ80_VerifyDashboardIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 476 |
| Tradov/TradovQ_Scripts/TradovQ90_SystemUtilities.py | TRADOV - Autonomous Options Trading System v1.0 | 884 |
| Tradov/TradovQ_Scripts/TradovQ92_DiagnosticsUtilities.py | TRADOV - Autonomous Options Trading System v1.0 | 1,658 |
| Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py | TRADOV - Autonomous Options Trading System v1.0 | 552 |
| Tradov/TradovQ_Scripts/TradovQ96_CollectFinetuneData.py | TRADOV - Autonomous Options Trading System v1.0 | 274 |
| Tradov/TradovQ_Scripts/TradovQ98_FinetuneGemma4Tradov.py | TRADOV - Autonomous Options Trading System v1.0 | 335 |
| Tradov/TradovQ_Scripts/TradovQ99_ApplyPythonFormatting.py | Script to apply standard Python formatting to all Tradov modules | 326 |
| Tradov/TradovQ_Scripts/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 303 |
| Tradov/TradovQ_Scripts/analyze_logs.py | Module for analyze logs functionality. | 56 |
| Tradov/TradovQ_Scripts/check_quotes.py | Module for check quotes functionality. | 49 |
| Tradov/TradovQ_Scripts/launch_dashboard_with_proactive_connections.py | Backward-compatible launcher shim. | 35 |
| Tradov/TradovQ_Scripts/launch_spyder_dashboard_direct.py | Backward-compatible launcher shim. | 35 |
| Tradov/TradovQ_Scripts/launch_spyder_working_dashboard.py | Backward-compatible launcher shim. | 35 |
| Tradov/TradovQ_Scripts/restore_script.py | Module for restore script functionality. | 32 |
| **Subtotal** | **28 modules** | **11,107** |

### TradovR_Runtime (Series R)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovR_Runtime/TradovR02_PaperEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 818 |
| Tradov/TradovR_Runtime/TradovR03_PaperMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 851 |
| Tradov/TradovR_Runtime/TradovR04_LiveEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 4,178 |
| Tradov/TradovR_Runtime/TradovR05_LivenessMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 308 |
| Tradov/TradovR_Runtime/TradovR06_PaperTradingHarness.py | TRADOV - Autonomous Options Trading System v1.0 | 1,016 |
| Tradov/TradovR_Runtime/TradovR07_LiveDashboard.py | TRADOV - Autonomous Options Trading System v1.0 | 542 |
| Tradov/TradovR_Runtime/TradovR08_PaperTradingQtWorker.py | TRADOV - Autonomous Options Trading System v1.0 | 2,841 |
| Tradov/TradovR_Runtime/TradovR09_ProductionDeploymentManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,807 |
| Tradov/TradovR_Runtime/TradovR11_PaperStrategyRunner.py | TRADOV - Autonomous Options Trading System v1.0 | 1,659 |
| Tradov/TradovR_Runtime/TradovR12_SessionSupervisor.py | TRADOV - Autonomous Options Trading System v1.0 | 2,214 |
| Tradov/TradovR_Runtime/TradovR13_FillReconciler.py | TRADOV - Autonomous Options Trading System v1.0 | 525 |
| Tradov/TradovR_Runtime/TradovR14_ExitMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 1,151 |
| Tradov/TradovR_Runtime/TradovR15_PaperBroker.py | TRADOV - Autonomous Options Trading System v1.0 | 519 |
| Tradov/TradovR_Runtime/TradovR16_PaperSandboxReplay.py | TRADOV - Autonomous Options Trading System v1.0 | 209 |
| Tradov/TradovR_Runtime/__init__.py | TRADOV - Automated SPY Options Trading System | 81 |
| **Subtotal** | **15 modules** | **18,719** |

### TradovS_Signals (Series S)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovS_Signals/TradovS01_DIXCalculator.py | TRADOV - Autonomous Options Trading System v1.0 | 765 |
| Tradov/TradovS_Signals/TradovS02_DIXScheduler.py | TRADOV - Autonomous Options Trading System v1.0 | 974 |
| Tradov/TradovS_Signals/TradovS03_BlackSwanIndicator.py | TRADOV - Autonomous Options Trading System | 796 |
| Tradov/TradovS_Signals/TradovS04_BlackSwanScheduler.py | TRADOV - Autonomous Options Trading System v1.0 | 1,592 |
| Tradov/TradovS_Signals/TradovS05_GEXDEXCalculator.py | TRADOV - Autonomous Options Trading System | 648 |
| Tradov/TradovS_Signals/TradovS06_SKEWCalculator.py | TRADOV - Autonomous Options Trading System | 1,433 |
| Tradov/TradovS_Signals/TradovS07_CustomMetricsOrchestrator.py | TRADOV - Autonomous Options Trading System v1.0 | 3,480 |
| Tradov/TradovS_Signals/TradovS08_PivotMeanReversionSignal.py | TRADOV - Autonomous Options Trading System v1.0 | 381 |
| Tradov/TradovS_Signals/TradovS08_ShortSqueezeDetector.py | TRADOV - Autonomous Options Trading System v1.0 | 1,347 |
| Tradov/TradovS_Signals/TradovS09_FREDClient.py | TRADOV - Autonomous Options Trading System v1.0 | 338 |
| Tradov/TradovS_Signals/TradovS10_SentimentScraper.py | TRADOV - Autonomous Options Trading System v1.0 | 673 |
| Tradov/TradovS_Signals/TradovS11_TradingViewInternals.py | TRADOV - Autonomous Options Trading System v1.0 | 551 |
| Tradov/TradovS_Signals/TradovS12_WRSSignal.py | TRADOV - Autonomous Options Trading System v1.0 | 1,029 |
| Tradov/TradovS_Signals/TradovS13_PSRSignal.py | TRADOV - Autonomous Options Trading System v1.0 | 1,016 |
| Tradov/TradovS_Signals/TradovS14_PCASignals.py | TRADOV - Autonomous Options Trading System v1.0 | 943 |
| Tradov/TradovS_Signals/TradovS15_MarketIntelClient.py | TRADOV - Autonomous Options Trading System v1.0 | 326 |
| Tradov/TradovS_Signals/TradovS16_MarketSnapshotLLM.py | TRADOV - Autonomous Options Trading System v1.0 | 265 |
| Tradov/TradovS_Signals/TradovS18_EconomicCalendar.py | TRADOV - Autonomous Options Trading System v1.0 | 418 |
| Tradov/TradovS_Signals/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 91 |
| **Subtotal** | **19 modules** | **17,066** |

### TradovT_Testing (Series T)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovT_Testing/TradovT01_UnitTestFramework.py | TRADOV - Autonomous Options Trading System v1.0 | 1,937 |
| Tradov/TradovT_Testing/TradovT03_BlackSwanValidator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,207 |
| Tradov/TradovT_Testing/TradovT06_EvolvedStrategyTest.py | TRADOV - Autonomous Options Trading System v1.0 | 874 |
| Tradov/TradovT_Testing/TradovT07_AdvancedEvolutionPush.py | TRADOV - Autonomous Options Trading System v1.0 | 366 |
| Tradov/TradovT_Testing/TradovT08_FixedSystemIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 432 |
| Tradov/TradovT_Testing/TradovT09_TestDashboard.py | TRADOV - Autonomous Options Trading System | 3,369 |
| Tradov/TradovT_Testing/TradovT100_OrderExecutionIntegration_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 304 |
| Tradov/TradovT_Testing/TradovT100_U13TechnicalIndicators_U15PerformanceMetrics.py | TRADOV - Test Suite T100 | 1,082 |
| Tradov/TradovT_Testing/TradovT101_CircuitBreaker_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 284 |
| Tradov/TradovT_Testing/TradovT101_U14OptionStrategies_U10TradingCalendar.py | TRADOV - Test Suite T101 | 985 |
| Tradov/TradovT_Testing/TradovT102_U18DependencyAnalyzer_U19InteractionMatrix.py | TRADOV - Autonomous Options Trading System v1.0 | 1,174 |
| Tradov/TradovT_Testing/TradovT103_U20InstitutionalLibraries.py | TRADOV - Autonomous Options Trading System v1.0 | 768 |
| Tradov/TradovT_Testing/TradovT104_U22ETTimeDisplay_U16TechnicalAnalysis.py | TRADOV - Autonomous Options Trading System v1.0 | 767 |
| Tradov/TradovT_Testing/TradovT105_U23MemoryMonitor_U27SystemOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 1,082 |
| Tradov/TradovT_Testing/TradovT106_ACore.py | TRADOV - Autonomous Options Trading System v1.0 | 1,640 |
| Tradov/TradovT_Testing/TradovT107_FSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 1,528 |
| Tradov/TradovT_Testing/TradovT108_NSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 1,003 |
| Tradov/TradovT_Testing/TradovT109_SSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 745 |
| Tradov/TradovT_Testing/TradovT10_DashboardRisk.py | TRADOV - Autonomous Options Trading System v1.0 | 954 |
| Tradov/TradovT_Testing/TradovT110_VSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 904 |
| Tradov/TradovT_Testing/TradovT111_LSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 1,480 |
| Tradov/TradovT_Testing/TradovT112_ESeries.py | TRADOV - Autonomous Options Trading System v1.0 | 1,435 |
| Tradov/TradovT_Testing/TradovT113_BSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 838 |
| Tradov/TradovT_Testing/TradovT114_DSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 2,004 |
| Tradov/TradovT_Testing/TradovT115_HSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 350 |
| Tradov/TradovT_Testing/TradovT116_RSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 2,189 |
| Tradov/TradovT_Testing/TradovT117_PSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 991 |
| Tradov/TradovT_Testing/TradovT118_YSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 620 |
| Tradov/TradovT_Testing/TradovT119_CSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 268 |
| Tradov/TradovT_Testing/TradovT11_EliteEvolvedStrategyTest.py | TRADOV - Autonomous Options Trading System v1.0 | 512 |
| Tradov/TradovT_Testing/TradovT120_GSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 136 |
| Tradov/TradovT_Testing/TradovT120_S07OptionsAnalytics.py | TRADOV - Autonomous Options Trading System v1.0 | 535 |
| Tradov/TradovT_Testing/TradovT121_ISeries.py | TRADOV - Autonomous Options Trading System v1.0 | 531 |
| Tradov/TradovT_Testing/TradovT122_JSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 233 |
| Tradov/TradovT_Testing/TradovT123_KSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 162 |
| Tradov/TradovT_Testing/TradovT124_MSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 217 |
| Tradov/TradovT_Testing/TradovT125_OSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 215 |
| Tradov/TradovT_Testing/TradovT126_QSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 159 |
| Tradov/TradovT_Testing/TradovT127_XSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 208 |
| Tradov/TradovT_Testing/TradovT128_ZSeries.py | TRADOV - Autonomous Options Trading System v1.0 | 233 |
| Tradov/TradovT_Testing/TradovT129_ProtocolCompliance.py | TRADOV - Autonomous Options Trading System v1.0 | 2,206 |
| Tradov/TradovT_Testing/TradovT12_FullSystemIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 628 |
| Tradov/TradovT_Testing/TradovT130_IronCondorSandbox_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 334 |
| Tradov/TradovT_Testing/TradovT130_S06SKEWCalculator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,199 |
| Tradov/TradovT_Testing/TradovT131_PivotMRSignalTests.py | TRADOV - Autonomous Options Trading System v1.0 | 338 |
| Tradov/TradovT_Testing/TradovT132_BrokerProtocolParity.py | TRADOV - Autonomous Options Trading System v1.0 | 104 |
| Tradov/TradovT_Testing/TradovT133_BrokerChaos.py | TRADOV - Autonomous Options Trading System v1.0 | 116 |
| Tradov/TradovT_Testing/TradovT134_A02_EntryTrustGate.py | Focused tests for A02 direct signal trust gating via F09 controls. | 359 |
| Tradov/TradovT_Testing/TradovT135_A04_EventClockFeed.py | Focused tests for A04 event-clock feed transitions. | 221 |
| Tradov/TradovT_Testing/TradovT136_B02_ExecutionFeedContract.py | Focused tests for B02 execution telemetry feed contract. | 81 |
| Tradov/TradovT_Testing/TradovT137_B02K04_ExecutionTelemetryPipeline.py | Phase 5-C: B02→K04 Execution Telemetry Pipeline Integration Tests | 322 |
| Tradov/TradovT_Testing/TradovT138_B02_LiquidityGateContract.py | Focused tests for B02 liquidity gate contract behavior. | 113 |
| Tradov/TradovT_Testing/TradovT140_C16_CacheConsolidation.py | Tests for C16/H03 cache consolidation behavior. | 109 |
| Tradov/TradovT_Testing/TradovT141_D31_EntryTrustGate.py | Focused tests for D31 entry trust gating via F09 market-structure controls. | 1,031 |
| Tradov/TradovT_Testing/TradovT142_D31_StrategyRegistryWiring.py | Focused tests for D31 strategy registry and auto-selection wiring. | 476 |
| Tradov/TradovT_Testing/TradovT143_D31_AdmissionGuardrails.py | Focused tests for D31 strategy admission guardrails. | 270 |
| Tradov/TradovT_Testing/TradovT143_E00_RiskProtocol.py | Tests for TradovE00_RiskProtocol | 172 |
| Tradov/TradovT_Testing/TradovT144_E16_EventClockRestrictions.py | Focused tests for E16 event-clock order restrictions. | 38 |
| Tradov/TradovT_Testing/TradovT145_Test_EventClockPipelineIntegration.py | Integration-style tests for A04 -> F09/E16 event-clock blackout pipeline. | 120 |
| Tradov/TradovT_Testing/TradovT146_F00_AnalysisProtocol.py | Tests for TradovF00_AnalysisProtocol | 135 |
| Tradov/TradovT_Testing/TradovT147_F09_DecisionPathControls.py | Focused tests for F09 decision-path market-structure and trust controls. | 180 |
| Tradov/TradovT_Testing/TradovT148_F09_EventClockBlackout.py | Focused tests for F09 event-clock blackout behavior. | 59 |
| Tradov/TradovT_Testing/TradovT149_F09_LiquidityGate.py | Focused tests for F09 liquidity gate helper. | 394 |
| Tradov/TradovT_Testing/TradovT14_RiskSuiteIntegrationTest.py | TRADOV - Autonomous Options Trading System v1.0 | 623 |
| Tradov/TradovT_Testing/TradovT150_G05_EventClockDisplay.py | TRADOV - Autonomous Options Trading System v1.0 | 355 |
| Tradov/TradovT_Testing/TradovT151_G05_EventClockHandlerIntegration.py | Integration-style tests for A04 event-clock payload consumption by G05. | 88 |
| Tradov/TradovT_Testing/TradovT152_G05_ExecutionTelemetryHandler.py | Focused tests for G05 execution telemetry handler wiring. | 117 |
| Tradov/TradovT_Testing/TradovT153_G05_GoNoGoCheck.py | Focused tests for G05 pre-open Go/No-Go checklist behavior. | 156 |
| Tradov/TradovT_Testing/TradovT154_G13_SignalMonitorStyles.py | Regression tests for G13 Signal Monitor styling integrity. | 102 |
| Tradov/TradovT_Testing/TradovT155_G32_AgentHealthDashboard.py | Tests for TradovG32_AgentHealthDashboard | 77 |
| Tradov/TradovT_Testing/TradovT156_J03_WebhookNotifier.py | Tests for TradovJ03_WebhookNotifier | 110 |
| Tradov/TradovT_Testing/TradovT157_K13_StrategyPnlLadder.py | Tests for TradovK13_StrategyPnLLadder | 131 |
| Tradov/TradovT_Testing/TradovT158_N06_TermStructureSnapshot.py | Focused tests for N06 term-structure snapshot generation. | 198 |
| Tradov/TradovT_Testing/TradovT159_N09_DealerWallsSnapshot.py | Focused tests for N09 GammaExposureCalculator.get_dealer_walls_snapshot(). | 144 |
| Tradov/TradovT_Testing/TradovT15_FullSystemTest.py | TRADOV - Autonomous Options Trading System | 598 |
| Tradov/TradovT_Testing/TradovT160_N11_VannaCharmSnapshot.py | Focused tests for N11 OptionsGreeksFlowAnalyzer.get_vanna_charm_snapshot(). | 161 |
| Tradov/TradovT_Testing/TradovT161_S07_BreadthQualityFeed.py | Focused tests for S07 sector breadth expansion + data-quality feed (Phases 11/12). | 230 |
| Tradov/TradovT_Testing/TradovT162_S07_DealerFlowMetrics.py | Focused tests for S07 dealer-flow metrics update pipeline (Phase 9). | 229 |
| Tradov/TradovT_Testing/TradovT164_S07_LiquidityDiagnostics.py | Focused tests for S07 liquidity diagnostics publication. | 223 |
| Tradov/TradovT_Testing/TradovT165_S07_VolSurfaceMetrics.py | Focused tests for S07 vol-surface publication. | 137 |
| Tradov/TradovT_Testing/TradovT166_Test_SharpeComparison.py | Test script to demonstrate Sharpe Ratio enhancements. | 294 |
| Tradov/TradovT_Testing/TradovT167_Test_Stage3DecisionQualitySlo.py | Stage 3 decision-quality SLO tests. | 263 |
| Tradov/TradovT_Testing/TradovT168_Test_Stage4OperationalReadiness.py | Stage 4 operational-readiness tests. | 499 |
| Tradov/TradovT_Testing/TradovT169_Test_StrategySignalContracts.py | Focused signal-contract tests for legacy D-series strategies. | 379 |
| Tradov/TradovT_Testing/TradovT16_SystemHealthMonitor.py | TRADOV - Autonomous Options Trading System | 433 |
| Tradov/TradovT_Testing/TradovT170_U46_SecretsManager.py | Tests for TradovU46_SecretsManager | 97 |
| Tradov/TradovT_Testing/TradovT171_V09_IvEngine.py | Tests for TradovV09_IVEngine | 180 |
| Tradov/TradovT_Testing/TradovT172_Z00_BrokerProtocol.py | Tests for TradovZ00_BrokerProtocol | 151 |
| Tradov/TradovT_Testing/TradovT173_R05_U42_Coverage.py | Focused tests for R05 liveness monitor and U42 strategy circuit breaker. | 160 |
| Tradov/TradovT_Testing/TradovT174_LowCoverageBatch.py | Focused low-coverage tests for utility and monitoring stubs. | 395 |
| Tradov/TradovT_Testing/TradovT175_B06_U47_Coverage.py | Focused coverage tests for B06, B21, U47, and E02 shim modules. | 255 |
| Tradov/TradovT_Testing/TradovT176_Q03_Q08_Q09_Coverage.py | Focused coverage tests for Q03, Q08, and Q09 validator scripts. | 260 |
| Tradov/TradovT_Testing/TradovT177_Q02_I12_Coverage.py | Coverage tests for Q02 environment validation and I12 module registry. | 193 |
| Tradov/TradovT_Testing/TradovT178_Q10_Coverage.py | Coverage tests for TradovQ10_ProtocolComplianceGate. | 263 |
| Tradov/TradovT_Testing/TradovT179_T54_T142_IsolationRegression.py | Deterministic in-process isolation regression for T54/T142. | 46 |
| Tradov/TradovT_Testing/TradovT17_ComprehensiveSystemTest.py | Module for comprehensivesystemtest functionality. | 1,323 |
| Tradov/TradovT_Testing/TradovT180_E01_AgentVetoObserveOnly.py | Tests for E01 observe-only handling of Y03 agent veto state. | 57 |
| Tradov/TradovT_Testing/TradovT181_N14_IvNormalization.py | Regression tests for N14 IV normalization behavior. | 48 |
| Tradov/TradovT_Testing/TradovT182_AutonomousDecisionContract.py | Drift guard for autonomous decision and regime input contracts. | 148 |
| Tradov/TradovT_Testing/TradovT183_Phase2SymbolCatalog.py | Phase 2 guardrails for canonical symbol governance. | 341 |
| Tradov/TradovT_Testing/TradovT184_RegimeV2DeterministicContract.py | Deterministic v2 regime and strategy-gating contract tests. | 489 |
| Tradov/TradovT_Testing/TradovT185_D31_MarketDataCacheShape.py | Regression test for D31 market_data_cache shape. | 148 |
| Tradov/TradovT_Testing/TradovT186_E01_ColdStartFailClosed.py | SPEC-10 — E01 cold-start fail-closed when tradier_client is missing in live. | 127 |
| Tradov/TradovT_Testing/TradovT186_S14_PCASignals.py | Focused tests for the PCA proxy custom metrics. | 435 |
| Tradov/TradovT_Testing/TradovT187_D31_ColdStartRegimeUnknown.py | SPEC-5 — D31 must fail-closed to a no-trade regime when SPY/VIX cache is cold. | 185 |
| Tradov/TradovT_Testing/TradovT187_G05_PCADetailDialogs.py | Focused tests for G05 PCA detail dialog helpers. | 698 |
| Tradov/TradovT_Testing/TradovT188_G05_MarketWorkerThreadSafety.py | Focused tests for G05 market-worker thread handoff behavior. | 219 |
| Tradov/TradovT_Testing/TradovT188_R12_OrderManagerWiring.py | SPEC-6 — R12 SessionSupervisor must wire OrderManager in live mode. | 180 |
| Tradov/TradovT_Testing/TradovT189_E03_StopLossBrokerRejection.py | SPEC-13 — E03 stop-loss must surface broker rejection, not silently downgrade. | 157 |
| Tradov/TradovT_Testing/TradovT189_G05_TradingArmingTransitions.py | Focused tests for G05 REAL/PAPER arming transitions. | 141 |
| Tradov/TradovT_Testing/TradovT18_EnhancedSharpeCalculator.py | TRADOV - Automated SPY Options Trading System | 588 |
| Tradov/TradovT_Testing/TradovT190_E01_DailyLossFromBrokerPnL.py | SPEC-9 — E01 daily-loss kill switch must read broker P&L, not local zeros. | 189 |
| Tradov/TradovT_Testing/TradovT191_B40_RetryIdempotency.py | SPEC-4 — B40 retry layer must NOT auto-retry POST/PUT/DELETE on 5xx. | 229 |
| Tradov/TradovT_Testing/TradovT192_TelegramOperatorCommands.py | T192 — Telegram operator command controls for halt/resume/flatten. | 708 |
| Tradov/TradovT_Testing/TradovT193_D31_DispatchResultHardening.py | T193 — D31 dispatch is robust when walk_result lacks standard attributes. | 189 |
| Tradov/TradovT_Testing/TradovT194_R12_RiskManagerInjection.py | T194 — R12 SessionSupervisor must inject the synced RiskManager into D31. | 128 |
| Tradov/TradovT_Testing/TradovT195_D31_DispatchStateBadge.py | T195 — D31 ``get_dispatch_state()`` powers the G05 DISPATCH pill. | 359 |
| Tradov/TradovT_Testing/TradovT196_Q92_TradingHealthReport.py | Focused tests for the Q92 trading-health diagnostics report. | 169 |
| Tradov/TradovT_Testing/TradovT196_R12_LiveOnlyTradierPolicy.py | T196 - R12 must fail fast on any sandbox Tradier request. | 89 |
| Tradov/TradovT_Testing/TradovT197_C29_LiveOnlyPolicy.py | T197 — C29 DataProviderRouter live-only market-data policy tests. | 66 |
| Tradov/TradovT_Testing/TradovT198_A03_ConfigManagerCompatibility.py | Regression tests for A03 ConfigManager compatibility APIs. | 32 |
| Tradov/TradovT_Testing/TradovT199_C01_DataFeedStartupFailClosed.py | Focused tests for C01 startup fail-closed behavior. | 134 |
| Tradov/TradovT_Testing/TradovT19_SharpeRatioCalculator.py | TRADOV - Automated SPY Options Trading System | 361 |
| Tradov/TradovT_Testing/TradovT200_A01_ShutdownOrder.py | Focused tests for A01 shutdown ordering around GUI and SessionSupervisor. | 782 |
| Tradov/TradovT_Testing/TradovT202_C01_StopIdempotency.py | Focused regression tests for idempotent C01 shutdown behavior. | 33 |
| Tradov/TradovT_Testing/TradovT203_G05_ShutdownThreadCleanup.py | Focused tests for G05 shutdown-time thread cleanup helpers. | 514 |
| Tradov/TradovT_Testing/TradovT204_I03_ConfigManagerShutdown.py | Focused tests for I03 ConfigManager shutdown cleanup. | 69 |
| Tradov/TradovT_Testing/TradovT205_S07_DixStartupNonBlocking.py | Focused tests for non-blocking S07 DIX startup behavior. | 211 |
| Tradov/TradovT_Testing/TradovT206_A01_ShutdownBreadthRefresh.py | Launcher-backed regression for shutdown during a live breadth refresh. | 170 |
| Tradov/TradovT_Testing/TradovT207_G05_MarketDataReadiness.py | Focused tests for G05 market-data readiness gating. | 2,100 |
| Tradov/TradovT_Testing/TradovT208_G05_SessionSupervisorReuse.py | Focused tests for G05 SessionSupervisor reuse. | 564 |
| Tradov/TradovT_Testing/TradovT209_G05_RegimePillExecutionTruth.py | Focused regression for G05 stance/gate execution-truth rendering. | 231 |
| Tradov/TradovT_Testing/TradovT209_ZPackageLazyExports.py | Focused regressions for lazy TradovZ_Communication package exports. | 55 |
| Tradov/TradovT_Testing/TradovT20_DIXDemo.py | TRADOV - Autonomous Options Trading System v1.0 | 579 |
| Tradov/TradovT_Testing/TradovT210_D02_IronCondorNoSignalDiagnostics.py | Focused regressions for D02 Iron Condor no-entry diagnostics. | 182 |
| Tradov/TradovT_Testing/TradovT210_PPackageLazyRegistry.py | Focused regressions for lazy TradovP_PortfolioMgmt package exports. | 65 |
| Tradov/TradovT_Testing/TradovT211_D32_IVRankHintIntegration.py | Focused regressions for D32 live IV-rank hint handling. | 143 |
| Tradov/TradovT_Testing/TradovT211_R14_LazyPortfolioManager.py | Focused regressions for lazy ExitMonitor portfolio manager resolution. | 159 |
| Tradov/TradovT_Testing/TradovT211_S07_CustomMetricsStartup.py | Regression tests for S07 startup behavior. | 72 |
| Tradov/TradovT_Testing/TradovT212_D31_StartupDeferral.py | Focused regressions for paper-mode D31 startup deferral. | 382 |
| Tradov/TradovT_Testing/TradovT212_G05_PaperPositionFallback.py | Focused regression for paper-mode position fallback in G05. | 752 |
| Tradov/TradovT_Testing/TradovT213_A05_AtexitCleanup.py | Focused regressions for quiet EventManager atexit cleanup. | 49 |
| Tradov/TradovT_Testing/TradovT213_D31_PaperIronCondorWrappedSignal.py | Regression for wrapped TradingSignal payloads on D31 paper iron-condor dispatch. | 253 |
| Tradov/TradovT_Testing/TradovT214_G05_RecentDecisionFlowDiagnostics.py | Focused tests for G05 recent decision-flow diagnostics rendering. | 109 |
| Tradov/TradovT_Testing/TradovT215_A05_EventManagerLegacySchema.py | Focused regression for A05 EventManager legacy event_log schema migration. | 65 |
| Tradov/TradovT_Testing/TradovT215_Q93_RunPaperPolicy.py | Focused regressions for the Q93 paper-launcher trading-mode gate. | 102 |
| Tradov/TradovT_Testing/TradovT215_QDesktopLauncherAutostart.py | Focused regression coverage for desktop-launcher paper autostart defaults. | 33 |
| Tradov/TradovT_Testing/TradovT216_B03_PaperStateCarryover.py | Focused tests for paper PositionTracker state carryover handling. | 101 |
| Tradov/TradovT_Testing/TradovT216_C17_TradierConnectionPolicy.py | Focused policy regression for C17 Tradier connection defaults. | 15 |
| Tradov/TradovT_Testing/TradovT217_G05_OffHoursCacheRestore.py | Focused tests for G05 off-hours cache restore behavior. | 383 |
| Tradov/TradovT_Testing/TradovT217_R11_ZeroDTEProfile.py | Focused regressions for the R11 paper-run ZeroDTE profile hook. | 526 |
| Tradov/TradovT_Testing/TradovT218_R12_FreshnessMonitorThresholds.py | Focused tests for R12 freshness-monitor threshold resolution. | 133 |
| Tradov/TradovT_Testing/TradovT219_D31_ODTEOverlaySlot.py | Scaffold tests for D31 ODTE Pivot overlay slot admission and disable behavior. | 22 |
| Tradov/TradovT_Testing/TradovT219_R12_ExitMonitorAuthoritativePositions.py | Focused tests for R12 paper ExitMonitor authoritative-position wiring. | 773 |
| Tradov/TradovT_Testing/TradovT21_DIXQuickStart.py | TRADOV - Autonomous Options Trading System v1.0 | 614 |
| Tradov/TradovT_Testing/TradovT220_D02_IronCondorExitMonitor.py | Focused regressions for D02 Iron Condor ExitMonitor integration. | 109 |
| Tradov/TradovT_Testing/TradovT220_E01_OverlayPretradeVerdict.py | Scaffold tests for E01 overlay pre-trade verdict API contract. | 22 |
| Tradov/TradovT_Testing/TradovT221_PaperIronCondorExitSmoke.py | Focused paper-mode smoke for Iron Condor exit flow. | 210 |
| Tradov/TradovT_Testing/TradovT222_D31_OverlayAuditSchema.py | Scaffold tests for D31 ODTE overlay audit and telemetry schema. | 22 |
| Tradov/TradovT_Testing/TradovT222_G24_PnlMetricsResolver.py | Focused tests for pure dashboard P&L metric helpers. | 107 |
| Tradov/TradovT_Testing/TradovT223_G05_PnlTableRefresh.py | Thin regression for G05 P&L table refresh orchestration. | 75 |
| Tradov/TradovT_Testing/TradovT224_G26_RecentTradeFormatter.py | Focused regressions for recent-trade formatting extraction. | 157 |
| Tradov/TradovT_Testing/TradovT225_G27_RecentTradesDialog.py | Focused regressions for the dedicated recent-trades dialog. | 213 |
| Tradov/TradovT_Testing/TradovT226_G28_AccountPanelPresenter.py | Focused regressions for account-panel presentation extraction. | 132 |
| Tradov/TradovT_Testing/TradovT227_G33_AccountSnapshotSelector.py | Focused regressions for G33 account snapshot selection. | 47 |
| Tradov/TradovT_Testing/TradovT228_G34_AccountCapitalMath.py | Focused regressions for G34 account capital math extraction. | 178 |
| Tradov/TradovT_Testing/TradovT229_G35_PaperSummaryPresenter.py | Focused regressions for G35 paper summary presentation extraction. | 123 |
| Tradov/TradovT_Testing/TradovT22_FSeriesIntegrationValidator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,076 |
| Tradov/TradovT_Testing/TradovT230_G36_StripMetricsPresenter.py | Focused regressions for G36 IV and Greek strip presentation extraction. | 127 |
| Tradov/TradovT_Testing/TradovT231_G37_GreekBarPresenter.py | Focused regressions for G37 Greek bar risk mapping extraction. | 90 |
| Tradov/TradovT_Testing/TradovT232_G38_LegacySpreadsTablePresenter.py | Focused regressions for G38 legacy spreads table presentation extraction. | 124 |
| Tradov/TradovT_Testing/TradovT233_G39_PaperPositionsTreePresenter.py | Focused tests for paper positions tree presentation helpers. | 178 |
| Tradov/TradovT_Testing/TradovT234_G39_PaperSpreadTreePresenter.py | Focused tests for paper spread tree presentation helpers. | 154 |
| Tradov/TradovT_Testing/TradovT235_G40_ToolbarIndexPresenter.py | Focused tests for toolbar index presentation helpers. | 123 |
| Tradov/TradovT_Testing/TradovT236_G41_RegimeLiquidityPresenter.py | Focused tests for regime/liquidity presentation helpers. | 128 |
| Tradov/TradovT_Testing/TradovT237_G43_CustomMetricDialogPresenter.py | Focused tests for G43 custom metric detail dialog presenters. | 330 |
| Tradov/TradovT_Testing/TradovT238_G44_RecentDecisionFlowPresenter.py | Focused tests for G44 recent decision-flow presenter helpers. | 60 |
| Tradov/TradovT_Testing/TradovT239_G45_ExecutionHealthPresenter.py | Focused tests for G45 execution-health presenter helpers. | 56 |
| Tradov/TradovT_Testing/TradovT23_SharpeRatioEstimate.py | TRADOV - Autonomous Options Trading System v1.0 | 192 |
| Tradov/TradovT_Testing/TradovT240_G46_ReadinessStatusPresenter.py | Focused tests for G46 readiness status presenter helpers. | 100 |
| Tradov/TradovT_Testing/TradovT241_G05_ReadinessStatusDisplay.py | Focused tests for G05 readiness status display delegation. | 93 |
| Tradov/TradovT_Testing/TradovT242_G47_EventClockDisplayPresenter.py | Focused tests for G47 event-clock display presenter helpers. | 55 |
| Tradov/TradovT_Testing/TradovT243_G05_EventClockDisplay.py | Focused tests for G05 event-clock display delegation. | 90 |
| Tradov/TradovT_Testing/TradovT244_G48_TradingArmingPresenter.py | Focused tests for G48 REAL/PAPER arming presenter helpers. | 41 |
| Tradov/TradovT_Testing/TradovT245_G05_ModeButtons.py | Focused tests for G05 mode-button presentation delegation. | 84 |
| Tradov/TradovT_Testing/TradovT246_G49_TradingWindowBadgePresenter.py | Focused tests for G49 compact trading-window badge presenter. | 31 |
| Tradov/TradovT_Testing/TradovT247_G05_TradingWindowCompactLabel.py | Focused tests for G05 compact trading-window badge delegation. | 54 |
| Tradov/TradovT_Testing/TradovT248_G50_EntryBlockCompactPresenter.py | Focused tests for G50 entry-block presenter helpers. | 62 |
| Tradov/TradovT_Testing/TradovT249_G05_EntryBlockCompactLabel.py | Focused tests for G05 compact entry-block label delegation. | 60 |
| Tradov/TradovT_Testing/TradovT24_RenaissanceIntegrationTest.py | TRADOV - Automated SPY Options Trading System | 794 |
| Tradov/TradovT_Testing/TradovT250_G51_ModeTitlePresenter.py | Focused tests for G51 mode title presenter helpers. | 21 |
| Tradov/TradovT_Testing/TradovT251_G05_ModeTitles.py | Focused tests for G05 mode title delegation. | 102 |
| Tradov/TradovT_Testing/TradovT252_G52_RegimePillBarPresenter.py | Focused tests for the G52 regime pill bar presenter. | 74 |
| Tradov/TradovT_Testing/TradovT253_G05_RiskAlertEvent.py | Focused tests for G05 risk alert event handling. | 134 |
| Tradov/TradovT_Testing/TradovT254_G53_GoNoGoPresenter.py | Focused tests for G53 pre-open Go/No-Go presenter. | 52 |
| Tradov/TradovT_Testing/TradovT255_G54_ReadinessResultPresenter.py | Focused tests for G54 readiness result presenter. | 41 |
| Tradov/TradovT_Testing/TradovT256_G05_ReadinessResultApplication.py | Focused tests for G05 readiness result application. | 51 |
| Tradov/TradovT_Testing/TradovT257_G55_ReadinessReportPresenter.py | Focused tests for G55 readiness report export helpers. | 43 |
| Tradov/TradovT_Testing/TradovT258_G05_ReadinessReportExport.py | Focused tests for G05 readiness report and audit export helpers. | 140 |
| Tradov/TradovT_Testing/TradovT259_G56_ReadinessStartGatePresenter.py | Focused tests for G56 readiness start-gate presenter. | 45 |
| Tradov/TradovT_Testing/TradovT260_G57_StartTradingPrecheckPresenter.py | Focused tests for G57 start-trading precheck presenter. | 48 |
| Tradov/TradovT_Testing/TradovT261_G58_StartTradingLiveGuardPresenter.py | Focused tests for G58 live start-trading guard presenter. | 38 |
| Tradov/TradovT_Testing/TradovT262_G59_StartTradingFailurePresenter.py | Focused tests for G59 start-trading failure presenter. | 16 |
| Tradov/TradovT_Testing/TradovT263_G60_ReadinessStartBlockPresenter.py | Focused tests for G60 readiness start-block presenter. | 34 |
| Tradov/TradovT_Testing/TradovT264_G61_ReadinessAsyncPresenter.py | Focused tests for G61 async readiness presenter. | 30 |
| Tradov/TradovT_Testing/TradovT265_G62_ReadinessWorkerCleanupHelper.py | Focused tests for G62 readiness worker cleanup helper. | 34 |
| Tradov/TradovT_Testing/TradovT266_G63_ReadinessSnapshotHelper.py | Focused tests for G63 readiness snapshot helpers. | 58 |
| Tradov/TradovT_Testing/TradovT267_G64_ReadinessConnectionRefreshHelper.py | Focused tests for G64 readiness connection refresh helper. | 48 |
| Tradov/TradovT_Testing/TradovT268_G65_ReadinessEventClockSnapshotHelper.py | Focused tests for G65 readiness event-clock snapshot helper. | 24 |
| Tradov/TradovT_Testing/TradovT269_G66_ReadinessStartupStateHelper.py | Focused tests for G66 readiness startup-state helper. | 25 |
| Tradov/TradovT_Testing/TradovT270_G67_ReadinessDecisionHelper.py | Focused tests for G67 readiness decision helper. | 112 |
| Tradov/TradovT_Testing/TradovT271_G68_ReadinessBypassAuditHelper.py | Focused tests for G68 readiness bypass-audit helper. | 38 |
| Tradov/TradovT_Testing/TradovT272_G69_LiveDataStatusHelper.py | Focused tests for G69 live-data status helper. | 16 |
| Tradov/TradovT_Testing/TradovT273_G70_ReadinessCacheDecisionHelper.py | Focused tests for G70 readiness cache-decision helper. | 38 |
| Tradov/TradovT_Testing/TradovT274_G71_ReadinessGateDecisionHelper.py | Focused tests for G71 readiness gate-decision helper. | 39 |
| Tradov/TradovT_Testing/TradovT275_G72_PaperSessionQueueHelper.py | Focused tests for G72 paper-session queue helper. | 60 |
| Tradov/TradovT_Testing/TradovT276_G73_PaperSessionFinalizeHelper.py | Focused tests for G73 delayed paper-session finalization helper. | 39 |
| Tradov/TradovT_Testing/TradovT277_G74_SessionSupervisorStartHelper.py | Focused tests for G74 SessionSupervisor start helper. | 46 |
| Tradov/TradovT_Testing/TradovT278_G75_SessionSupervisorStartAttemptHelper.py | Focused tests for G75 SessionSupervisor start-attempt helper. | 42 |
| Tradov/TradovT_Testing/TradovT279_G76_SessionSupervisorAdoptionHelper.py | Focused tests for G76 SessionSupervisor adoption helper. | 48 |
| Tradov/TradovT_Testing/TradovT280_G77_LoadingTransitionCompletionHelper.py | Focused tests for G77 loading-transition completion helper. | 54 |
| Tradov/TradovT_Testing/TradovT281_G78_LoadingTransitionBeginHelper.py | Focused tests for G78 loading transition begin helper. | 51 |
| Tradov/TradovT_Testing/TradovT282_G79_StartButtonReadyStateHelper.py | Focused tests for G79 start-button ready-state helper. | 66 |
| Tradov/TradovT_Testing/TradovT283_G80_StartButtonActiveStateHelper.py | Focused tests for G80 start-button active-state helper. | 66 |
| Tradov/TradovT_Testing/TradovT284_G17_PaperPositionResolver.py | Focused tests for G17 paper position resolver selection and grouping policy. | 245 |
| Tradov/TradovT_Testing/TradovT285_G81_MarketWorkerSlotInvokeHelper.py | Focused tests for G81 market-worker slot invoke helper. | 54 |
| Tradov/TradovT_Testing/TradovT286_G82_QThreadShutdownHelper.py | Focused tests for G82 Qt thread shutdown helper. | 60 |
| Tradov/TradovT_Testing/TradovT287_G83_MetricsOrchestratorShutdownHelper.py | Focused tests for G83 metrics orchestrator shutdown helper. | 54 |
| Tradov/TradovT_Testing/TradovT288_G84_MarketWorkerSignalEmitHelper.py | Focused tests for G84 market-worker signal emit helper. | 36 |
| Tradov/TradovT_Testing/TradovT289_G85_MarketWorkerSignalDisconnectHelper.py | Focused tests for G85 market-worker signal disconnect helper. | 42 |
| Tradov/TradovT_Testing/TradovT290_G86_ShutdownTimerStopHelper.py | Focused tests for G86 shutdown timer stop helper. | 50 |
| Tradov/TradovT_Testing/TradovT291_G87_PostWorkerShutdownTimerHelper.py | Focused tests for G87 late shutdown timer stop helper. | 39 |
| Tradov/TradovT_Testing/TradovT292_G88_MarketWorkerShutdownHelper.py | Focused tests for G88 market-worker shutdown helper. | 33 |
| Tradov/TradovT_Testing/TradovT293_G89_ShutdownMessageHelper.py | Focused tests for G89 dashboard shutdown message helper. | 21 |
| Tradov/TradovT_Testing/TradovT294_G90_CloseEventShutdownSequenceHelper.py | Focused tests for G90 closeEvent shutdown sequence helper. | 37 |
| Tradov/TradovT_Testing/TradovT295_G91_StartupReadinessLogHelper.py | Focused tests for G91 startup-readiness log helper. | 88 |
| Tradov/TradovT_Testing/TradovT296_G92_StartupReadinessBannerHelper.py | Focused tests for G92 startup-readiness banner helper. | 81 |
| Tradov/TradovT_Testing/TradovT297_G93_StartupReadinessStateHelper.py | Focused tests for G93 startup-readiness state helper. | 75 |
| Tradov/TradovT_Testing/TradovT298_G94_StartupReadinessRefreshHelper.py | Focused tests for G94 startup-readiness refresh helper. | 26 |
| Tradov/TradovT_Testing/TradovT299_G95_DJIProxyMultiplierHelper.py | Focused tests for G95 DJI proxy multiplier normalization helper. | 22 |
| Tradov/TradovT_Testing/TradovT300_G96_RiskAlertDispatchHelper.py | Focused tests for G96 risk alert dispatch helper. | 55 |
| Tradov/TradovT_Testing/TradovT301_G05_PendingOrdersGate.py | Focused tests for G05 pending-orders gate behavior. | 99 |
| Tradov/TradovT_Testing/TradovT302_G97_PendingOrdersGateHelper.py | Focused tests for G97 pending-orders gate helper. | 47 |
| Tradov/TradovT_Testing/TradovT303_G98_ExecutionTelemetryEventHelper.py | Focused tests for G98 execution-telemetry event helper. | 48 |
| Tradov/TradovT_Testing/TradovT304_G05_PositionUpdatedEvent.py | Focused tests for G05 POSITION_UPDATED event wiring. | 56 |
| Tradov/TradovT_Testing/TradovT305_G100_PositionUpdatedEventHelper.py | Focused tests for G100 POSITION_UPDATED event helper. | 24 |
| Tradov/TradovT_Testing/TradovT306_G05_RecentDecisionFlowFetch.py | Focused tests for G05 recent decision-flow fetch wiring. | 72 |
| Tradov/TradovT_Testing/TradovT307_G101_RecentDecisionFlowFetchHelper.py | Focused tests for G101 recent decision-flow fetch helper. | 34 |
| Tradov/TradovT_Testing/TradovT308_G05_MetricsOrchestratorStart.py | Focused tests for G05 metrics orchestrator startup wiring. | 73 |
| Tradov/TradovT_Testing/TradovT309_G102_MetricsOrchestratorStartHelper.py | Focused tests for G102 metrics orchestrator start helper. | 25 |
| Tradov/TradovT_Testing/TradovT310_G05_LiveToPaperSwitch.py | Focused tests for G05 LIVE-to-PAPER switch dialog wiring. | 106 |
| Tradov/TradovT_Testing/TradovT311_G103_LiveToPaperSwitchHelper.py | Focused tests for G103 LIVE-to-PAPER switch helper. | 31 |
| Tradov/TradovT_Testing/TradovT312_G05_MetricsSnapshotHydration.py | Focused tests for G05 metrics snapshot hydration wiring. | 54 |
| Tradov/TradovT_Testing/TradovT313_G104_MetricsSnapshotProbeHelper.py | Focused tests for G104 metrics snapshot probe helper. | 60 |
| Tradov/TradovT_Testing/TradovT314_G05_PaperToLiveSwitch.py | Focused tests for G05 PAPER-to-LIVE switch dialog wiring. | 142 |
| Tradov/TradovT_Testing/TradovT315_G105_PaperToLiveSwitchHelper.py | Focused tests for G105 PAPER-to-LIVE switch helper. | 27 |
| Tradov/TradovT_Testing/TradovT316_G05_CustomMetricWidgetFanout.py | Focused tests for G05 custom-metric widget fan-out wiring. | 100 |
| Tradov/TradovT_Testing/TradovT317_G106_CustomMetricWidgetUpdateHelper.py | Focused tests for G106 custom-metric widget update helper. | 68 |
| Tradov/TradovT_Testing/TradovT318_G05_CustomMetricSignalPanelSync.py | Focused tests for G05 signal-panel sync wiring from custom metrics. | 157 |
| Tradov/TradovT_Testing/TradovT319_G107_CustomMetricSignalPanelSyncHelper.py | Focused tests for G107 custom-metric signal-panel sync helper. | 86 |
| Tradov/TradovT_Testing/TradovT320_G05_CustomMetricBreadthDialogSync.py | Focused tests for G05 Market Internals dialog sync from custom metrics. | 71 |
| Tradov/TradovT_Testing/TradovT321_G108_CustomMetricBreadthDialogSyncHelper.py | Focused tests for G108 custom-metric breadth dialog sync helper. | 69 |
| Tradov/TradovT_Testing/TradovT322_G05_RegimePillStatePlan.py | Focused tests for G05 regime-pill state plan wiring. | 128 |
| Tradov/TradovT_Testing/TradovT323_G109_RegimePillStateHelper.py | Focused tests for G109 regime-pill state helper. | 123 |
| Tradov/TradovT_Testing/TradovT324_G05_RegimePillStatusPlan.py | Focused tests for G05 regime-pill status plan wiring. | 128 |
| Tradov/TradovT_Testing/TradovT325_G110_RegimePillStatusHelper.py | Focused tests for G110 regime-pill status helper. | 36 |
| Tradov/TradovT_Testing/TradovT326_G05_RegimeDispatchAnnouncement.py | Focused tests for G05 regime dispatch announcement wiring. | 213 |
| Tradov/TradovT_Testing/TradovT327_G111_RegimeDispatchAnnouncementHelper.py | Focused tests for G111 regime dispatch announcement helper. | 39 |
| Tradov/TradovT_Testing/TradovT330_G05_CloseStrategyConfirm.py | Focused tests for G05 close-strategy confirmation dialog wiring. | 161 |
| Tradov/TradovT_Testing/TradovT331_G112_CloseStrategyConfirmHelper.py | Focused tests for G112 close-strategy confirmation helper. | 33 |
| Tradov/TradovT_Testing/TradovT332_G05_CloseStrategySuccess.py | Focused tests for G05 close-strategy success-path wiring. | 58 |
| Tradov/TradovT_Testing/TradovT333_G113_CloseStrategySuccessHelper.py | Focused tests for G113 close-strategy success helper. | 23 |
| Tradov/TradovT_Testing/TradovT334_G05_CloseStrategyFailure.py | Focused tests for G05 close-strategy failure-path wiring. | 55 |
| Tradov/TradovT_Testing/TradovT335_G114_CloseStrategyFailureHelper.py | Focused tests for G114 close-strategy failure helper. | 38 |
| Tradov/TradovT_Testing/TradovT336_G05_EventSubscriptionPlan.py | Focused tests for G05 event subscription plan wiring. | 70 |
| Tradov/TradovT_Testing/TradovT337_G115_EventSubscriptionPlanHelper.py | Focused tests for G115 event subscription plan helper. | 53 |
| Tradov/TradovT_Testing/TradovT338_G05_EventClockRiskEvent.py | Focused tests for G05 event-clock risk-event wiring. | 78 |
| Tradov/TradovT_Testing/TradovT339_G116_EventClockRiskEventHelper.py | Focused tests for G116 event-clock risk-event helper. | 77 |
| Tradov/TradovT_Testing/TradovT340_G05_EventClockOverride.py | Focused tests for G05 manual event-clock override wiring. | 96 |
| Tradov/TradovT_Testing/TradovT341_G117_EventClockOverrideHelper.py | Focused tests for G117 manual event-clock override helper. | 28 |
| Tradov/TradovT_Testing/TradovT342_G05_PaperRiskManagerLimits.py | Focused tests for G05 paper risk-limit mapping integration. | 115 |
| Tradov/TradovT_Testing/TradovT343_G118_PaperRiskLimitMappingHelper.py | Focused tests for G118 paper risk-limit mapping helper. | 41 |
| Tradov/TradovT_Testing/TradovT344_G05_RingLogBuffering.py | Focused tests for G05 ring-log buffering and refresh routing. | 110 |
| Tradov/TradovT_Testing/TradovT345_G119_RingLogBufferHelper.py | Focused tests for G119 ring-log helper logic. | 59 |
| Tradov/TradovT_Testing/TradovT348_G05_AfterHoursSystemLogSuppression.py | Focused tests for G05 system-log suppression wrapper behavior. | 91 |
| Tradov/TradovT_Testing/TradovT349_G120_SystemLogSuppressionHelper.py | Focused tests for G120 system-log suppression helper. | 39 |
| Tradov/TradovT_Testing/TradovT350_G05_AutomationLogRouting.py | Focused tests for G05 automation-log routing. | 78 |
| Tradov/TradovT_Testing/TradovT350_S11_TradingViewInternals.py | Focused tests for the S11 TradingView last-price selector path. | 122 |
| Tradov/TradovT_Testing/TradovT351_G121_AutomationLogRoutingHelper.py | Focused tests for G121 automation-log routing helper. | 42 |
| Tradov/TradovT_Testing/TradovT352_G05_SystemLogVerbosity.py | Focused tests for G05 system-log verbosity routing. | 93 |
| Tradov/TradovT_Testing/TradovT353_G122_SystemLogVerbosityHelper.py | Focused tests for G122 system-log verbosity helper. | 36 |
| Tradov/TradovT_Testing/TradovT354_G05_VetoToggleButtonState.py | Focused tests for G05 veto toggle button presentation routing. | 62 |
| Tradov/TradovT_Testing/TradovT355_G123_VetoToggleButtonHelper.py | Focused tests for G123 veto toggle button helper. | 24 |
| Tradov/TradovT_Testing/TradovT356_G05_VetoToggleControls.py | Focused tests for G05 veto toggle outcome routing. | 64 |
| Tradov/TradovT_Testing/TradovT357_G124_VetoToggleResultHelper.py | Focused tests for G124 veto toggle result helper. | 33 |
| Tradov/TradovT_Testing/TradovT358_G05_VetoControlsStateLoad.py | Focused tests for G05 veto controls state loading. | 87 |
| Tradov/TradovT_Testing/TradovT359_G125_VetoControlsStateHelper.py | Focused tests for G125 veto controls state helper. | 48 |
| Tradov/TradovT_Testing/TradovT360_G05_VetoControlsStatePersist.py | Focused tests for G05 veto controls persistence. | 79 |
| Tradov/TradovT_Testing/TradovT361_G126_VetoControlsPersistPlanHelper.py | Focused tests for G126 veto controls persistence planning. | 54 |
| Tradov/TradovT_Testing/TradovT362_G05_StartupReadinessStateEnvelope.py | Focused tests for G05 startup-readiness state envelope shaping. | 157 |
| Tradov/TradovT_Testing/TradovT363_G127_StartupReadinessStateEnvelopeHelper.py | Focused tests for G127 startup-readiness state envelope helper. | 46 |
| Tradov/TradovT_Testing/TradovT364_G05_DashboardSnapshotPayload.py | Focused tests for G05 dashboard snapshot payload shaping. | 104 |
| Tradov/TradovT_Testing/TradovT365_G128_DashboardSnapshotPayloadHelper.py | Focused tests for G128 dashboard snapshot payload helper. | 52 |
| Tradov/TradovT_Testing/TradovT366_G05_MetricsPayloadMerge.py | Focused tests for the G05 metrics payload merge wrapper. | 25 |
| Tradov/TradovT_Testing/TradovT367_G129_MetricsPayloadMergeHelper.py | Focused tests for the G129 metrics payload merge helper. | 42 |
| Tradov/TradovT_Testing/TradovT368_G05_CachedMetricsFallback.py | Focused tests for G05 cached metrics fallback payload wiring. | 141 |
| Tradov/TradovT_Testing/TradovT369_G130_CachedMetricsFallbackHelper.py | Focused tests for G130 cached metrics fallback helper. | 88 |
| Tradov/TradovT_Testing/TradovT370_G05_CachedMarketSnapshotMerge.py | Focused tests for G05 cached market snapshot merge wiring. | 62 |
| Tradov/TradovT_Testing/TradovT371_G131_CachedMarketSnapshotMergeHelper.py | Focused tests for G131 cached market snapshot merge helper. | 44 |
| Tradov/TradovT_Testing/TradovT372_G05_CachedChartCandles.py | Focused tests for G05 cached chart candle loading wiring. | 63 |
| Tradov/TradovT_Testing/TradovT372_G18_EODSnapshotPersistence.py | Regression tests for G18 EOD snapshot persistence behavior. | 152 |
| Tradov/TradovT_Testing/TradovT373_G132_CachedChartCandlesHelper.py | Focused tests for G132 cached chart candle selection helper. | 38 |
| Tradov/TradovT_Testing/TradovT374_G05_CachedChartBarSeries.py | Focused tests for G05 cached chart bar series wiring. | 95 |
| Tradov/TradovT_Testing/TradovT375_G133_CachedChartBarSeriesHelper.py | Focused tests for G133 cached chart bar series helper. | 91 |
| Tradov/TradovT_Testing/TradovT376_D31_PaperFailClosedGuard.py | Regression for D31 _paper_fail_closed_selector_reason overly broad guard. | 107 |
| Tradov/TradovT_Testing/TradovT377_R04_PaperFillGaps.py | Regression for R04 paper-fill gaps: H05 persistence, symbol in event, position tracker. | 306 |
| Tradov/TradovT_Testing/TradovT378_G05_PaperCleanSlateStartupGuard.py | Focused tests for G05 paper clean-slate startup guard behavior. | 106 |
| Tradov/TradovT_Testing/TradovT378_R12_PaperStartAuthorization.py | Focused regressions for explicit paper-start authorization in R12. | 63 |
| Tradov/TradovT_Testing/TradovT379_C10_VIXAnalyzerVXVYahooAlias.py | Regression for C10 VXV Yahoo symbol drift. | 48 |
| Tradov/TradovT_Testing/TradovT380_G109_VixFallbackBull.py | Regression tests for G109 VIX-fallback BULL detection (§10.36 P1 fix). | 137 |
| Tradov/TradovT_Testing/TradovT381_L09_ColdVixEma50.py | Regression tests for L09 cold-start vix_ema50 guard fix (§10.36 P2 fix). | 135 |
| Tradov/TradovT_Testing/TradovT382_G110_GateStartupFallback.py | Regression tests for G110 gate/stance startup fallback (§10.36 P3 fix). | 148 |
| Tradov/TradovT_Testing/TradovT383_G12_SignalInfoDialogMetadata.py | Focused regressions for shared SignalInfoDialog metadata. | 66 |
| Tradov/TradovT_Testing/TradovT384_G17_MarketInternalsMetadata.py | Focused regressions for shared Market Internals panel copy. | 54 |
| Tradov/TradovT_Testing/TradovT385_G11_SkewDialogClose.py | Focused regressions for SKEW dialog close responsiveness. | 61 |
| Tradov/TradovT_Testing/TradovT386_D31_LiveOptionsSnapshotAgeGate.py | Focused regressions for D31 live options snapshot freshness gating. | 131 |
| Tradov/TradovT_Testing/TradovT387_G17_MarketInternalsStaleBreadth.py | Focused regressions for G17 stale breadth rendering. | 51 |
| Tradov/TradovT_Testing/TradovT388_D14_CalendarSpreadSerialization.py | Focused regressions for D14 calendar-spread signal serialization and lifecycle. | 131 |
| Tradov/TradovT_Testing/TradovT389_D31_PaperCalendarSpreadRouting.py | Focused regressions for D31 paper calendar-spread routing. | 203 |
| Tradov/TradovT_Testing/TradovT390_D23_BrokenWingButterfly.py | Module for d23 brokenwingbutterfly functionality. | 144 |
| Tradov/TradovT_Testing/TradovT390_HolidayMarketHoursRegression.py | Regression tests for holiday-aware market-hours helpers across GUI/runtime layers. | 69 |
| Tradov/TradovT_Testing/TradovT391_D31_PaperBrokenWingButterflyRouting.py | Focused regressions for D31 paper Broken Wing Butterfly routing. | 157 |
| Tradov/TradovT_Testing/TradovT391_F01_TechnicalIndicatorsConfig.py | Focused regressions for F01 config-manager compatibility. | 52 |
| Tradov/TradovT_Testing/TradovT392_D24_Butterfly.py | Module for d24 butterfly functionality. | 216 |
| Tradov/TradovT_Testing/TradovT393_D31_PaperButterflyRouting.py | Focused regressions for D31 paper Butterfly routing. | 239 |
| Tradov/TradovT_Testing/TradovT393_D37_BullishStrangle.py | Focused unit tests for the D37 Bullish Strangle strategy. | 142 |
| Tradov/TradovT_Testing/TradovT394_S05_GEXDEXCalculator.py | Module for s05 gexdexcalculator functionality. | 116 |
| Tradov/TradovT_Testing/TradovT395_D10_IronButterfly.py | Module for d10 ironbutterfly functionality. | 113 |
| Tradov/TradovT_Testing/TradovT396_D31_PaperIronButterflyRouting.py | Focused regressions for D31 paper Iron Butterfly routing. | 178 |
| Tradov/TradovT_Testing/TradovT397_D31_PaperBullishStrangleRouting.py | Focused regressions for D31 paper Bullish Strangle routing. | 155 |
| Tradov/TradovT_Testing/TradovT397_D31_RegimePolicyButterflyAllowlist.py | Focused regressions for D31 butterfly-family regime allowlists. | 51 |
| Tradov/TradovT_Testing/TradovT398_G20_PositionsTableWidths.py | Focused regressions for dashboard positions-table money-column widths. | 42 |
| Tradov/TradovT_Testing/TradovT399_R08_AfterHoursSpreadMtm.py | Focused regressions for after-hours spread MTM freezing in R08. | 101 |
| Tradov/TradovT_Testing/TradovT400_D31_PinRiskWindowCoverage.py | Focused regressions for D31 post-close pin-risk coverage counting. | 124 |
| Tradov/TradovT_Testing/TradovT401_D31_PaperJadeLizardZeroRouting.py | Focused regressions for D31 paper Jade Lizard Zero routing. | 127 |
| Tradov/TradovT_Testing/TradovT402_R08_ManualCloseEmbargoEvent.py | Focused regressions for R08 manual-close embargo event emission. | 54 |
| Tradov/TradovT_Testing/TradovT403_D39_PutCreditSpread7.py | Focused unit tests for the D39 Put Credit Spread 7 strategy. | 442 |
| Tradov/TradovT_Testing/TradovT404_D31_PaperPutCreditSpread7Routing.py | Focused regressions for D31 paper Put Credit Spread 7 routing. | 130 |
| Tradov/TradovT_Testing/TradovT40_TradierClient_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 540 |
| Tradov/TradovT_Testing/TradovT42_Integration_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 269 |
| Tradov/TradovT_Testing/TradovT43_OrderManager_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 805 |
| Tradov/TradovT_Testing/TradovT45_ResilienceInfrastructureTest.py | TRADOV - Autonomous Options Trading System v1.0 | 585 |
| Tradov/TradovT_Testing/TradovT46_RiskManager_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 564 |
| Tradov/TradovT_Testing/TradovT47_StrategyUnit_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 468 |
| Tradov/TradovT_Testing/TradovT48_PipelineE2E_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 468 |
| Tradov/TradovT_Testing/TradovT50_TradierOrderTests.py | TRADOV - Autonomous Options Trading System v1.0 | 823 |
| Tradov/TradovT_Testing/TradovT51_RiskManagerLimits_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 706 |
| Tradov/TradovT_Testing/TradovT52_SentimentNewsSourceStub_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 624 |
| Tradov/TradovT_Testing/TradovT54_StartupConfigValidation_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 1,008 |
| Tradov/TradovT_Testing/TradovT55_PaperTradingHarness_Test.py | TRADOV - Autonomous Options Trading System v1.0 | 749 |
| Tradov/TradovT_Testing/TradovT56_StrategyTests.py | TRADOV - Autonomous Options Trading System v1.0 | 894 |
| Tradov/TradovT_Testing/TradovT57_OptionsAnalyticsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 574 |
| Tradov/TradovT_Testing/TradovT58_RiskManagementTests.py | TRADOV - Autonomous Options Trading System v1.0 | 704 |
| Tradov/TradovT_Testing/TradovT59_UtilityTests.py | TRADOV - Autonomous Options Trading System v1.0 | 820 |
| Tradov/TradovT_Testing/TradovT60_FSeriesAnalysisTests.py | TRADOV - Autonomous Options Trading System v1.0 | 755 |
| Tradov/TradovT_Testing/TradovT61_ResilienceTests.py | TRADOV - Autonomous Options Trading System v1.0 | 800 |
| Tradov/TradovT_Testing/TradovT62_MathValidatorTests.py | TRADOV - Autonomous Options Trading System v1.0 | 993 |
| Tradov/TradovT_Testing/TradovT63_CalendarFeatureFlagTests.py | TRADOV - Autonomous Options Trading System v1.0 | 957 |
| Tradov/TradovT_Testing/TradovT64_OptionStrategyPerformanceTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,195 |
| Tradov/TradovT_Testing/TradovT65_ErrorHandlerNetworkTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,243 |
| Tradov/TradovT_Testing/TradovT66_MathTechnicalIndicatorTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,061 |
| Tradov/TradovT_Testing/TradovT67_RateLimiterCircuitBreakerTests.py | TRADOV - Autonomous Options Trading System v1.0 | 893 |
| Tradov/TradovT_Testing/TradovT68_EncryptionValidatorTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,035 |
| Tradov/TradovT_Testing/TradovT69_DateTimeUtilsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 707 |
| Tradov/TradovT_Testing/TradovT70_DataTypesETTimeTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,005 |
| Tradov/TradovT_Testing/TradovT71_PerfMetricsFeatureFlagsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,011 |
| Tradov/TradovT_Testing/TradovT72_TechnicalAnalysisTests.py | TRADOV - Autonomous Options Trading System v1.0 | 964 |
| Tradov/TradovT_Testing/TradovT73_MathValidatorsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,322 |
| Tradov/TradovT_Testing/TradovT74_TechIndicatorsOptionStrategiesTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,132 |
| Tradov/TradovT_Testing/TradovT75_DependencyAnalyzerInteractionMatrixTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,055 |
| Tradov/TradovT_Testing/TradovT76_MemoryMonitorSystemOptimizerTests.py | TRADOV - Autonomous Options Trading System v1.0 | 977 |
| Tradov/TradovT_Testing/TradovT77_CalendarInstitutionalLibrariesTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,160 |
| Tradov/TradovT_Testing/TradovT78_ErrorHandlerTechAnalysisNetworkGapTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,268 |
| Tradov/TradovT_Testing/TradovT79_StyleManagerMemMonSysOptGapTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,355 |
| Tradov/TradovT_Testing/TradovT80_U12U22U13U15U11GapTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,051 |
| Tradov/TradovT_Testing/TradovT81_ValidatorsRateLimiterCircuitBreakerDataTypesTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,299 |
| Tradov/TradovT_Testing/TradovT82_MathUtilsOptionStrategiesTests.py | TRADOV - Autonomous Options Trading System v1.0 | 884 |
| Tradov/TradovT_Testing/TradovT83_ErrorHandlerNetworkUtilsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 607 |
| Tradov/TradovT_Testing/TradovT84_FeatureFlagsPerformanceMetricsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 843 |
| Tradov/TradovT_Testing/TradovT85_TradingCalendarDependencyAnalyzerTests.py | TRADOV - Autonomous Options Trading System v1.0 | 840 |
| Tradov/TradovT_Testing/TradovT86_DateTimeUtilsInteractionMatrixTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,507 |
| Tradov/TradovT_Testing/TradovT87_ETTimeDisplayMemoryMonitorTests.py | TRADOV - Autonomous Options Trading System v1.0 | 951 |
| Tradov/TradovT_Testing/TradovT88_TechnicalAnalysisSystemOptimizerTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,396 |
| Tradov/TradovT_Testing/TradovT89_MathUtilsValidatorsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,561 |
| Tradov/TradovT_Testing/TradovT90_TechnicalIndicatorsPerformanceMetricsTests.py | TRADOV - Autonomous Options Trading System v1.0 | 1,200 |
| Tradov/TradovT_Testing/TradovT91_RateLimiterCircuitBreakerTests.py | TRADOV - Autonomous Options Trading System v1.0 | 765 |
| Tradov/TradovT_Testing/TradovT92_EncryptionOptionStrategiesTests.py | TRADOV - Autonomous Options Trading System v1.0 | 794 |
| Tradov/TradovT_Testing/TradovT93_U11FeatureFlags_U09DataTypes.py | TRADOV - Autonomous Options Trading System v1.0 | 1,583 |
| Tradov/TradovT_Testing/TradovT94_U02ErrorHandler_U05NetworkUtils.py | TRADOV - Autonomous Options Trading System v1.0 | 1,397 |
| Tradov/TradovT_Testing/TradovT95_U03DateTimeUtils_U07Constants_U22ETTimeDisplay.py | T95 — TradovU03 DateTimeUtils \| TradovU07 Constants \| TradovU22 ETTimeDisplay | 1,011 |
| Tradov/TradovT_Testing/TradovT96_U12AgentIntegration_U23MemoryMonitor_U24StyleManager.py | T96 — TradovU12 AgentIntegration \| TradovU23 MemoryMonitor \| TradovU24 StyleManager | 849 |
| Tradov/TradovT_Testing/TradovT97_U04Encryption_U40RateLimiter_U41CircuitBreaker.py | TRADOV - Autonomous Options Trading System v1.0 | 1,006 |
| Tradov/TradovT_Testing/TradovT98_U06MathUtils_U08Validators.py | TRADOV - Autonomous Options Trading System v1.0 | 880 |
| Tradov/TradovT_Testing/TradovT99_SystemDiagnostic.py | TRADOV - Autonomous Options Trading System v1.0 | 712 |
| Tradov/TradovT_Testing/TradovT99_U16TechnicalAnalysis_U27SystemOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 747 |
| Tradov/TradovT_Testing/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 367 |
| Tradov/TradovT_Testing/conftest.py | TRADOV - Autonomous Options Trading System v1.0 | 439 |
| Tradov/TradovT_Testing/test_no_legacy_spyderu_imports.py | Guardrail test to prevent legacy TradovU import paths in active code. | 56 |
| Tradov/TradovT_Testing/test_r12_flatten_request_guard.py | Regression tests for R12 FLATTEN_REQUEST broker-cutoff guard wiring. | 468 |
| Tradov/TradovT_Testing/test_r12_paper_condor_runtime_smoke.py | Focused runtime smoke for paper iron-condor persistence and rendering. | 245 |
| **Subtotal** | **410 modules** | **142,448** |

### TradovU_Utilities (Series U)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovU_Utilities/TradovU01_Logger.py | TRADOV - Autonomous Options Trading System v1.0 | 128 |
| Tradov/TradovU_Utilities/TradovU02_ErrorHandler.py | TRADOV - Autonomous Options Trading System v1.0 | 915 |
| Tradov/TradovU_Utilities/TradovU03_DateTimeUtils.py | TRADOV - Autonomous Options Trading System v1.0 | 1,947 |
| Tradov/TradovU_Utilities/TradovU04_Encryption.py | TRADOV - Autonomous Options Trading System v1.0 | 230 |
| Tradov/TradovU_Utilities/TradovU05_NetworkUtils.py | TRADOV - Autonomous Options Trading System v1.0 | 499 |
| Tradov/TradovU_Utilities/TradovU06_MathUtils.py | TRADOV - Autonomous Options Trading System v1.0 | 837 |
| Tradov/TradovU_Utilities/TradovU07_Constants.py | Module for constants functionality. | 756 |
| Tradov/TradovU_Utilities/TradovU08_Validators.py | TRADOV - Autonomous Options Trading System v1.0 | 884 |
| Tradov/TradovU_Utilities/TradovU09_DataTypes.py | TRADOV - Autonomous Options Trading System v1.0 | 708 |
| Tradov/TradovU_Utilities/TradovU10_TradingCalendar.py | TRADOV - Autonomous Options Trading System v1.0 | 926 |
| Tradov/TradovU_Utilities/TradovU11_FeatureFlags.py | TRADOV - Autonomous Options Trading System v1.0 | 733 |
| Tradov/TradovU_Utilities/TradovU12_AgentIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 428 |
| Tradov/TradovU_Utilities/TradovU13_TechnicalIndicators.py | TRADOV - Autonomous Options Trading System v1.0 | 782 |
| Tradov/TradovU_Utilities/TradovU14_OptionStrategies.py | TRADOV - Autonomous Options Trading System v1.0 | 880 |
| Tradov/TradovU_Utilities/TradovU15_PerformanceMetrics.py | TRADOV - Autonomous Options Trading System v1.0 | 794 |
| Tradov/TradovU_Utilities/TradovU16_TechnicalAnalysis.py | TRADOV - Autonomous Options Trading System | 690 |
| Tradov/TradovU_Utilities/TradovU17_LLMUtils.py | TRADOV - Autonomous Options Trading System v1.0 | 91 |
| Tradov/TradovU_Utilities/TradovU18_DependencyAnalyzer.py | TRADOV - Autonomous Options Trading System v1.0 | 749 |
| Tradov/TradovU_Utilities/TradovU19_InteractionMatrix.py | TRADOV - Autonomous Options Trading System v1.0 | 923 |
| Tradov/TradovU_Utilities/TradovU20_InstitutionalLibraries.py | TRADOV - Autonomous Options Trading System v1.0 | 916 |
| Tradov/TradovU_Utilities/TradovU22_ETTimeDisplay.py | TRADOV - Autonomous Options Trading System v1.0 | 146 |
| Tradov/TradovU_Utilities/TradovU23_MemoryMonitor.py | TRADOV - Autonomous Options Trading System v1.0 | 644 |
| Tradov/TradovU_Utilities/TradovU24_StyleManager.py | TRADOV - Autonomous Options Trading System v1.0 | 716 |
| Tradov/TradovU_Utilities/TradovU27_SystemOptimizer.py | TRADOV - Autonomous Options Trading System v1.0 | 465 |
| Tradov/TradovU_Utilities/TradovU40_RateLimiter.py | TRADOV - Autonomous Options Trading System v1.0 | 342 |
| Tradov/TradovU_Utilities/TradovU41_CircuitBreaker.py | TRADOV - Autonomous Options Trading System v1.0 | 381 |
| Tradov/TradovU_Utilities/TradovU42_StrategyCircuitBreaker.py | TRADOV - Autonomous Options Trading System v1.0 | 673 |
| Tradov/TradovU_Utilities/TradovU43_CorrelationLogger.py | TRADOV - Autonomous Options Trading System v1.0 | 479 |
| Tradov/TradovU_Utilities/TradovU44_ShutdownCoordinator.py | TRADOV - Autonomous Options Trading System v1.0 | 181 |
| Tradov/TradovU_Utilities/TradovU45_RetryWithBackoff.py | TRADOV - Autonomous Options Trading System v1.0 | 296 |
| Tradov/TradovU_Utilities/TradovU46_SecretsManager.py | TRADOV - Autonomous Options Trading System v1.0 | 372 |
| Tradov/TradovU_Utilities/TradovU47_OptionalImport.py | TRADOV - Autonomous Options Trading System v1.0 | 130 |
| Tradov/TradovU_Utilities/TradovU48_Money.py | A22/O4 (v14): Decimal-backed Money type for cent-precise accounting. | 103 |
| Tradov/TradovU_Utilities/TradovU49_SymbolCatalog.py | TRADOV - Autonomous Options Trading System v1.0 | 358 |
| Tradov/TradovU_Utilities/TradovU50_AsyncBridge.py | TradovU50_AsyncBridge — safe async-from-thread execution helper. | 75 |
| Tradov/TradovU_Utilities/__init__.py | TRADOV - Automated SPY Options Trading System | 492 |
| **Subtotal** | **36 modules** | **20,669** |

### TradovV_QuantModels (Series V)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovV_QuantModels/TradovV01_QuantEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 932 |
| Tradov/TradovV_QuantModels/TradovV02_ModelManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,051 |
| Tradov/TradovV_QuantModels/TradovV03_DataInterface.py | TRADOV - Autonomous Options Trading System v1.0 | 663 |
| Tradov/TradovV_QuantModels/TradovV04_RiskManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,344 |
| Tradov/TradovV_QuantModels/TradovV05_PricingEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 1,545 |
| Tradov/TradovV_QuantModels/TradovV06_VolatilityEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 1,729 |
| Tradov/TradovV_QuantModels/TradovV07_AdvancedModels.py | TRADOV - Autonomous Options Trading System v1.0 | 1,303 |
| Tradov/TradovV_QuantModels/TradovV08_AIModels.py | TRADOV - Autonomous Options Trading System v1.0 | 1,208 |
| Tradov/TradovV_QuantModels/TradovV09_IVEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 973 |
| Tradov/TradovV_QuantModels/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 497 |
| **Subtotal** | **10 modules** | **11,245** |

### TradovX_Agents (Series X)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovX_Agents/TradovX01_GreeksAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 2,395 |
| Tradov/TradovX_Agents/TradovX02_FlowAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,307 |
| Tradov/TradovX_Agents/TradovX03_StrategyDirectorAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,228 |
| Tradov/TradovX_Agents/TradovX04_RiskGuardianAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 834 |
| Tradov/TradovX_Agents/TradovX05_MLResearchAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,478 |
| Tradov/TradovX_Agents/TradovX06_BacktestingAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 784 |
| Tradov/TradovX_Agents/TradovX07_ExecutionStrategyAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 957 |
| Tradov/TradovX_Agents/TradovX08_PerformanceAnalyticsAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 507 |
| Tradov/TradovX_Agents/TradovX09_AlertManagerAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,178 |
| Tradov/TradovX_Agents/TradovX10_QuantModelsAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,531 |
| Tradov/TradovX_Agents/TradovX11_SentimentAnalysisAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,494 |
| Tradov/TradovX_Agents/TradovX12_SystemHealthAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,233 |
| Tradov/TradovX_Agents/TradovX13_MarketAnalysisAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 885 |
| Tradov/TradovX_Agents/TradovX14_OrchestratorAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 1,373 |
| Tradov/TradovX_Agents/TradovX15_StrategyGeneratorAgent.py | TRADOV - Autonomous Options Trading System v1.0 | 468 |
| Tradov/TradovX_Agents/TradovX16_MetaCoordinator.py | TRADOV - Autonomous Options Trading System | 1,200 |
| Tradov/TradovX_Agents/__init__.py | TRADOV - Automated SPY Options Trading System | 337 |
| **Subtotal** | **17 modules** | **19,189** |

### TradovY_AutoAgents (Series Y)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovY_AutoAgents/TradovY00_BaseAutoAgent.py | TRADOV - Autonomous Options Trading System | 802 |
| Tradov/TradovY_AutoAgents/TradovY01_MarketSenseAgent.py | TRADOV - Autonomous Options Trading System | 553 |
| Tradov/TradovY_AutoAgents/TradovY02_StrategyPilotAgent.py | TRADOV - Autonomous Options Trading System | 508 |
| Tradov/TradovY_AutoAgents/TradovY03_RiskSentinelAgent.py | TRADOV - Autonomous Options Trading System | 636 |
| Tradov/TradovY_AutoAgents/TradovY04_AlphaLearnerAgent.py | TRADOV - Autonomous Options Trading System | 547 |
| Tradov/TradovY_AutoAgents/TradovY05_ExecutionOptimizerAgent.py | TRADOV - Autonomous Options Trading System | 560 |
| Tradov/TradovY_AutoAgents/TradovY06_NewsSentinelAgent.py | TRADOV - Autonomous Options Trading System | 554 |
| Tradov/TradovY_AutoAgents/TradovY07_TradeJournalAgent.py | TRADOV - Autonomous Options Trading System | 611 |
| Tradov/TradovY_AutoAgents/TradovY08_MetaOrchestratorAgent.py | TRADOV - Autonomous Options Trading System | 760 |
| Tradov/TradovY_AutoAgents/TradovY09_CodeReviewerAgent.py | TRADOV - Autonomous Options Trading System | 463 |
| Tradov/TradovY_AutoAgents/TradovY10_AgentScheduler.py | TRADOV - Autonomous Options Trading System | 426 |
| Tradov/TradovY_AutoAgents/TradovY_InferenceBackends.py | TRADOV - Autonomous Options Trading System v1.0 | 419 |
| Tradov/TradovY_AutoAgents/__init__.py | TRADOV - Autonomous Options Trading System | 338 |
| **Subtotal** | **13 modules** | **7,177** |

### TradovZ_Communication (Series Z)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/TradovZ_Communication/TradovZ00_BrokerProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 282 |
| Tradov/TradovZ_Communication/TradovZ01_ZeroMQIntegration.py | TRADOV - Autonomous Options Trading System v1.0 | 1,264 |
| Tradov/TradovZ_Communication/TradovZ02_MessageProtocol.py | TRADOV - Autonomous Options Trading System v1.0 | 1,453 |
| Tradov/TradovZ_Communication/TradovZ03_TradingCoordinator.py | TRADOV - Autonomous Options Trading System v1.0 | 1,489 |
| Tradov/TradovZ_Communication/TradovZ04_VolatilityEngine.py | TRADOV - Autonomous Options Trading System v1.0 | 802 |
| Tradov/TradovZ_Communication/TradovZ05_OrderRouter.py | TRADOV - Autonomous Options Trading System | 1,216 |
| Tradov/TradovZ_Communication/TradovZ06_AutoHedger.py | TRADOV - Autonomous Options Trading System v1.0 | 1,209 |
| Tradov/TradovZ_Communication/TradovZ07_MultiProcessManager.py | TRADOV - Autonomous Options Trading System v1.0 | 1,003 |
| Tradov/TradovZ_Communication/__init__.py | TRADOV - Autonomous Options Trading System v1.0 | 73 |
| **Subtotal** | **9 modules** | **8,791** |

### Tradov_root (Series -)

| Module | Purpose | LOC |
|---|---|---:|
| Tradov/__init__.py | Tradov Trading System - Main Package | 94 |
| **Subtotal** | **1 modules** | **94** |

## Final Totals

- Total modules: 916
- Total LOC: 543,371

