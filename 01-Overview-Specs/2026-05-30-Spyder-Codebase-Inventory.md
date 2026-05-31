# 2026-05-30 Spyder Codebase Inventory

Date: 2026-05-30

## Scope and Method

- Scope: Python modules under `Spyder/` only.
- Grouping: by series directory (for example `SpyderA_Core`, `SpyderB_Broker`) with `Spyder_root` for package-root modules.
- LOC metric: physical lines per file from direct line count (`wc -l` equivalent).
- Purpose text: module docstring first line when available, otherwise inferred from module name.

## Executive Summary

- Total groups: 26
- Total modules: 916
- Total LOC: 543,371

### Group Totals

| Group | Series | Modules | LOC |
|---|---:|---:|---:|
| SpyderA_Core | A | 8 | 13,416 |
| SpyderB_Broker | B | 11 | 12,570 |
| SpyderC_MarketData | C | 24 | 25,216 |
| SpyderD_Strategies | D | 40 | 52,073 |
| SpyderE_Risk | E | 27 | 30,120 |
| SpyderF_Analysis | F | 22 | 23,671 |
| SpyderG_GUI | G | 133 | 36,681 |
| SpyderH_Storage | H | 8 | 6,338 |
| SpyderI_Integration | I | 13 | 9,745 |
| SpyderJ_Alerts | J | 6 | 5,585 |
| SpyderK_Reports | K | 14 | 13,826 |
| SpyderL_ML | L | 15 | 18,703 |
| SpyderM_Monitoring | M | 8 | 6,598 |
| SpyderN_OptionsAnalytics | N | 16 | 16,926 |
| SpyderO_TradingIntelligence | O | 4 | 4,853 |
| SpyderP_PortfolioMgmt | P | 9 | 10,545 |
| SpyderQ_Scripts | Q | 28 | 11,107 |
| SpyderR_Runtime | R | 15 | 18,719 |
| SpyderS_Signals | S | 19 | 17,066 |
| SpyderT_Testing | T | 410 | 142,448 |
| SpyderU_Utilities | U | 36 | 20,669 |
| SpyderV_QuantModels | V | 10 | 11,245 |
| SpyderX_Agents | X | 17 | 19,189 |
| SpyderY_AutoAgents | Y | 13 | 7,177 |
| SpyderZ_Communication | Z | 9 | 8,791 |
| Spyder_root | - | 1 | 94 |

## Module Inventory

### SpyderA_Core (Series A)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderA_Core/SpyderA01_Main.py | SPYDER - Autonomous Options Trading System v1.0 | 1,609 |
| Spyder/SpyderA_Core/SpyderA02_TradingEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 2,467 |
| Spyder/SpyderA_Core/SpyderA03_Configuration.py | SPYDER - Autonomous Options Trading System v1.0 | 2,030 |
| Spyder/SpyderA_Core/SpyderA04_Scheduler.py | SPYDER - Autonomous Options Trading System v1.0 | 2,383 |
| Spyder/SpyderA_Core/SpyderA05_EventManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,510 |
| Spyder/SpyderA_Core/SpyderA06_MasterController.py | SPYDER - Autonomous Options Trading System v1.0 | 2,061 |
| Spyder/SpyderA_Core/SpyderA08_FSeriesOrchestrator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,233 |
| Spyder/SpyderA_Core/__init__.py | Package initializer for SpyderA_Core. | 123 |
| **Subtotal** | **8 modules** | **13,416** |

### SpyderB_Broker (Series B)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderB_Broker/SpyderB00_OrderTypes.py | SPYDER - Autonomous Options Trading System v1.0 | 951 |
| Spyder/SpyderB_Broker/SpyderB02_OrderManager.py | SPYDER - Autonomous Options Trading System v1.0 | 2,229 |
| Spyder/SpyderB_Broker/SpyderB03_PositionTracker.py | SPYDER - Autonomous Options Trading System v1.0 | 769 |
| Spyder/SpyderB_Broker/SpyderB04_AccountManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,344 |
| Spyder/SpyderB_Broker/SpyderB06_DashboardOrderManager.py | SPYDER - Autonomous Options Trading System v1.0 | 419 |
| Spyder/SpyderB_Broker/SpyderB15_PrometheusMetrics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,465 |
| Spyder/SpyderB_Broker/SpyderB20_IntegratedConnectivityManager.py | SPYDER - Autonomous Options Trading System v1.0 | 190 |
| Spyder/SpyderB_Broker/SpyderB21_BrokerProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 136 |
| Spyder/SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py | Module for spyoptionschainmanager functionality. | 1,015 |
| Spyder/SpyderB_Broker/SpyderB40_TradierClient.py | SPYDER - Autonomous Options Trading System v1.0 | 3,702 |
| Spyder/SpyderB_Broker/__init__.py | SPYDER - Autonomous Options Trading System v2.0 | 350 |
| **Subtotal** | **11 modules** | **12,570** |

### SpyderC_MarketData (Series C)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderC_MarketData/SpyderC00_MarketDataProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 418 |
| Spyder/SpyderC_MarketData/SpyderC01_DataFeed.py | SPYDER - Autonomous Options Trading System v1.0 | 1,357 |
| Spyder/SpyderC_MarketData/SpyderC02_HistoricalData.py | SPYDER - Autonomous Options Trading System v1.0 | 937 |
| Spyder/SpyderC_MarketData/SpyderC03_OptionChain.py | SPYDER - Autonomous Options Trading System v1.0 | 1,100 |
| Spyder/SpyderC_MarketData/SpyderC04_MarketInternals.py | SPYDER - Autonomous Options Trading System v1.0 | 1,070 |
| Spyder/SpyderC_MarketData/SpyderC05_VolumeProfile.py | SPYDER - Autonomous Options Trading System v1.0 | 892 |
| Spyder/SpyderC_MarketData/SpyderC06_DataValidator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,320 |
| Spyder/SpyderC_MarketData/SpyderC08_SPYFeed.py | SPYDER - Autonomous Options Trading System v1.0 | 876 |
| Spyder/SpyderC_MarketData/SpyderC09_NewsManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,034 |
| Spyder/SpyderC_MarketData/SpyderC10_VIXAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,513 |
| Spyder/SpyderC_MarketData/SpyderC12_DarkPoolFlow.py | SPYDER - Autonomous Options Trading System v1.0 | 769 |
| Spyder/SpyderC_MarketData/SpyderC13_IndexComponents.py | SPYDER - Autonomous Options Trading System v1.0 | 1,022 |
| Spyder/SpyderC_MarketData/SpyderC15_MicrostructureAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,288 |
| Spyder/SpyderC_MarketData/SpyderC16_MarketDataCache.py | SPYDER - Autonomous Options Trading System v1.0 | 911 |
| Spyder/SpyderC_MarketData/SpyderC17_MarketConfigManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,018 |
| Spyder/SpyderC_MarketData/SpyderC18_SKEWCalculator.py | SPYDER - Autonomous Options Trading System | 1,286 |
| Spyder/SpyderC_MarketData/SpyderC19_AfterHoursDataManager.py | SPYDER - Autonomous Options Trading System v1.0 | 812 |
| Spyder/SpyderC_MarketData/SpyderC22_FactorDataProvider.py | SPYDER - Autonomous Options Trading System v1.0 | 1,311 |
| Spyder/SpyderC_MarketData/SpyderC23_RealTimeDataOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,218 |
| Spyder/SpyderC_MarketData/SpyderC24_ModelDataPipeline.py | SPYDER - Autonomous Options Trading System v1.0 | 1,520 |
| Spyder/SpyderC_MarketData/SpyderC29_DataProviderRouter.py | SPYDER - Autonomous Options Trading System v1.0 | 264 |
| Spyder/SpyderC_MarketData/SpyderC30_OrderFlowAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,521 |
| Spyder/SpyderC_MarketData/SpyderC35_SentimentAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,519 |
| Spyder/SpyderC_MarketData/__init__.py | SPYDER - Automated SPY Options Trading System | 240 |
| **Subtotal** | **24 modules** | **25,216** |

### SpyderD_Strategies (Series D)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderD_Strategies/SpyderD00_StrategyConstants.py | SPYDER - Autonomous Options Trading System | 355 |
| Spyder/SpyderD_Strategies/SpyderD01_BaseStrategy.py | SPYDER - Autonomous Options Trading System v1.0 | 1,075 |
| Spyder/SpyderD_Strategies/SpyderD02_IronCondor.py | Module for ironcondor functionality. | 1,234 |
| Spyder/SpyderD_Strategies/SpyderD03_CreditSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 1,026 |
| Spyder/SpyderD_Strategies/SpyderD04_ZeroDTE.py | SPYDER - Autonomous Options Trading System v1.0 | 1,555 |
| Spyder/SpyderD_Strategies/SpyderD05_Straddle.py | SPYDER - Autonomous Options Trading System v1.0 | 1,124 |
| Spyder/SpyderD_Strategies/SpyderD06_BullPutSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 175 |
| Spyder/SpyderD_Strategies/SpyderD07_BearCallSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 175 |
| Spyder/SpyderD_Strategies/SpyderD08_OpeningRangeBreakout.py | SPYDER - Autonomous Options Trading System v1.0 | 1,159 |
| Spyder/SpyderD_Strategies/SpyderD09_GreeksBasedStrategy.py | SPYDER - Autonomous Options Trading System v1.0 | 1,543 |
| Spyder/SpyderD_Strategies/SpyderD10_IronButterfly.py | Module for ironbutterfly functionality. | 1,165 |
| Spyder/SpyderD_Strategies/SpyderD11_SpecializedZeroDTE.py | SPYDER - Autonomous Options Trading System v1.0 | 1,308 |
| Spyder/SpyderD_Strategies/SpyderD12_RSIMeanReversion.py | SPYDER - Autonomous Options Trading System v1.0 | 1,097 |
| Spyder/SpyderD_Strategies/SpyderD13_MACrossover.py | SPYDER - Autonomous Options Trading System v1.0 | 1,003 |
| Spyder/SpyderD_Strategies/SpyderD14_CalendarSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 1,388 |
| Spyder/SpyderD_Strategies/SpyderD15_StraddleStrangle.py | SPYDER - Autonomous Options Trading System v1.0 | 1,406 |
| Spyder/SpyderD_Strategies/SpyderD16_RatioSpreads.py | SPYDER - Autonomous Options Trading System v1.0 | 1,477 |
| Spyder/SpyderD_Strategies/SpyderD17_DiagonalSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 1,379 |
| Spyder/SpyderD_Strategies/SpyderD18_EvolvedCreditSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 1,530 |
| Spyder/SpyderD_Strategies/SpyderD19_JadeLizard.py | SPYDER - Autonomous Options Trading System v1.0 | 1,275 |
| Spyder/SpyderD_Strategies/SpyderD20_VerticalSpreadOptimizer.py | SPYDER - Autonomous Options Trading System | 897 |
| Spyder/SpyderD_Strategies/SpyderD21_DoubleCalendar.py | SPYDER - Autonomous Options Trading System v1.0 | 1,422 |
| Spyder/SpyderD_Strategies/SpyderD22_AdaptiveVolatility.py | SPYDER - Autonomous Options Trading System | 1,151 |
| Spyder/SpyderD_Strategies/SpyderD23_BrokenWingButterfly.py | SPYDER - Autonomous Options Trading System v1.0 | 1,105 |
| Spyder/SpyderD_Strategies/SpyderD24_Butterfly.py | SPYDER - Autonomous Options Trading System v1.0 | 1,017 |
| Spyder/SpyderD_Strategies/SpyderD25_UnifiedCreditSpreadEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 1,524 |
| Spyder/SpyderD_Strategies/SpyderD26_GammaScalper.py | SPYDER - Autonomous Options Trading System | 1,174 |
| Spyder/SpyderD_Strategies/SpyderD27_EarningsStrategy.py | SPYDER - Autonomous Options Trading System v1.0 | 1,260 |
| Spyder/SpyderD_Strategies/SpyderD28_VIXHedging.py | SPYDER - Autonomous Options Trading System v1.0 | 1,069 |
| Spyder/SpyderD_Strategies/SpyderD30_RegimeGatedSelector.py | SPYDER - Automated SPY Options Trading System | 1,624 |
| Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py | Module for strategyorchestrator functionality. | 10,126 |
| Spyder/SpyderD_Strategies/SpyderD32_MultiLegStrategyCoordinator.py | SPYDER - Autonomous Options Trading System v1.0 | 2,577 |
| Spyder/SpyderD_Strategies/SpyderD33_RenaissanceMeanReversion.py | SPYDER - Autonomous Options Trading System v1.0 | 742 |
| Spyder/SpyderD_Strategies/SpyderD34_PivotMeanReversion.py | SPYDER - Autonomous Options Trading System v1.0 | 1,039 |
| Spyder/SpyderD_Strategies/SpyderD35_BullCallSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 190 |
| Spyder/SpyderD_Strategies/SpyderD36_BearPutSpread.py | SPYDER - Autonomous Options Trading System v1.0 | 190 |
| Spyder/SpyderD_Strategies/SpyderD37_BullishStrangle.py | SPYDER - Autonomous Options Trading System v1.0 | 328 |
| Spyder/SpyderD_Strategies/SpyderD38_JadeLizardZero.py | Zero/one-DTE Jade Lizard strategy with intraday-safe time handling. | 768 |
| Spyder/SpyderD_Strategies/SpyderD39_PutCreditSpread7.py | SPYDER - Autonomous Options Trading System v1.0 | 1,138 |
| Spyder/SpyderD_Strategies/__init__.py | Package initializer for SpyderD_Strategies. | 283 |
| **Subtotal** | **40 modules** | **52,073** |

### SpyderE_Risk (Series E)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderE_Risk/SpyderE00_RiskProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 264 |
| Spyder/SpyderE_Risk/SpyderE01_RiskManager.py | SPYDER - Autonomous Options Trading System v1.0 | 2,100 |
| Spyder/SpyderE_Risk/SpyderE02_DataFreshnessMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 18 |
| Spyder/SpyderE_Risk/SpyderE02_PositionSizer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,019 |
| Spyder/SpyderE_Risk/SpyderE03_StopLossManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,607 |
| Spyder/SpyderE_Risk/SpyderE04_DrawdownControl.py | SPYDER - Autonomous Options Trading System v1.0 | 903 |
| Spyder/SpyderE_Risk/SpyderE05_AutomaticRebalancer.py | SPYDER - Autonomous Options Trading System v1.0 | 722 |
| Spyder/SpyderE_Risk/SpyderE06_RiskMetrics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,162 |
| Spyder/SpyderE_Risk/SpyderE07_ProbabilisticSharpe.py | SPYDER - Autonomous Options Trading System v1.0 | 702 |
| Spyder/SpyderE_Risk/SpyderE08_PositionGroupValidator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,146 |
| Spyder/SpyderE_Risk/SpyderE09_VolatilityRiskManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,092 |
| Spyder/SpyderE_Risk/SpyderE10_CorrelationRiskManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,943 |
| Spyder/SpyderE_Risk/SpyderE11_MaxLossProtection.py | SPYDER - Autonomous Options Trading System | 937 |
| Spyder/SpyderE_Risk/SpyderE12_PortfolioVaR.py | SPYDER - Autonomous Options Trading System | 1,430 |
| Spyder/SpyderE_Risk/SpyderE13_DayProfitTarget.py | Module for dayprofittarget functionality. | 2,400 |
| Spyder/SpyderE_Risk/SpyderE14_KellyPositionSizer.py | SPYDER - Automated SPY Options Trading System | 715 |
| Spyder/SpyderE_Risk/SpyderE15_GreekLimitsManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,186 |
| Spyder/SpyderE_Risk/SpyderE16_CircuitBreakerProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 507 |
| Spyder/SpyderE_Risk/SpyderE17_RealTimeStressTesting.py | SPYDER - Autonomous Options Trading System v1.0 | 1,617 |
| Spyder/SpyderE_Risk/SpyderE18_FSeriesRiskIntegrator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,345 |
| Spyder/SpyderE_Risk/SpyderE19_UnifiedRiskCoordinator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,188 |
| Spyder/SpyderE_Risk/SpyderE20_FrustrationAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,625 |
| Spyder/SpyderE_Risk/SpyderE21_HMMRegimeDetector.py | SPYDER - Automated SPY Options Trading System | 1,080 |
| Spyder/SpyderE_Risk/SpyderE22_KernelRegression.py | SPYDER - Automated SPY Options Trading System | 832 |
| Spyder/SpyderE_Risk/SpyderE23_PortfolioOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 2,051 |
| Spyder/SpyderE_Risk/SpyderE24_DataFreshnessMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 324 |
| Spyder/SpyderE_Risk/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 205 |
| **Subtotal** | **27 modules** | **30,120** |

### SpyderF_Analysis (Series F)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderF_Analysis/SpyderF00_AnalysisProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 267 |
| Spyder/SpyderF_Analysis/SpyderF01_Indicators.py | SPYDER - Autonomous Options Trading System v1.0 | 900 |
| Spyder/SpyderF_Analysis/SpyderF02_PriceAction.py | SPYDER - Autonomous Options Trading System v1.0 | 872 |
| Spyder/SpyderF_Analysis/SpyderF03_SupportResistance.py | SPYDER - Autonomous Options Trading System v1.0 | 792 |
| Spyder/SpyderF_Analysis/SpyderF04_VolatilityAnalysis.py | SPYDER - Autonomous Options Trading System v1.0 | 922 |
| Spyder/SpyderF_Analysis/SpyderF05_TrendDetection.py | SPYDER - Autonomous Options Trading System v1.0 | 776 |
| Spyder/SpyderF_Analysis/SpyderF06_GreeksCalculator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,013 |
| Spyder/SpyderF_Analysis/SpyderF07_GapAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 758 |
| Spyder/SpyderF_Analysis/SpyderF08_VolatilityRegime.py | SPYDER - Autonomous Options Trading System v1.0 | 999 |
| Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py | SPYDER - Autonomous Options Trading System v1.0 | 2,541 |
| Spyder/SpyderF_Analysis/SpyderF10_MarketRegimeDetector.py | SPYDER - Autonomous Options Trading System v1.0 | 1,517 |
| Spyder/SpyderF_Analysis/SpyderF11_GreeksAggregator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,047 |
| Spyder/SpyderF_Analysis/SpyderF13_ModelValidation.py | SPYDER - Autonomous Options Trading System v1.0 | 1,436 |
| Spyder/SpyderF_Analysis/SpyderF14_MarketMicrostructure.py | SPYDER - Autonomous Options Trading System v1.0 | 1,548 |
| Spyder/SpyderF_Analysis/SpyderF16_RealTimeAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,689 |
| Spyder/SpyderF_Analysis/SpyderF17_UnifiedPerformanceEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 1,532 |
| Spyder/SpyderF_Analysis/SpyderF18_MaxPainCalculator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,072 |
| Spyder/SpyderF_Analysis/SpyderF19_AnchoredVWAP.py | SPYDER - Autonomous Options Trading System v1.0 | 1,184 |
| Spyder/SpyderF_Analysis/SpyderF20_Indicators.py | SPYDER - Autonomous Options Trading System v1.0 | 391 |
| Spyder/SpyderF_Analysis/SpyderF21_RenaissanceIndicators.py | SPYDER - Autonomous Options Trading System v1.0 | 860 |
| Spyder/SpyderF_Analysis/SpyderF22_MLPrediction.py | SPYDER - Autonomous Options Trading System v1.0 | 1,398 |
| Spyder/SpyderF_Analysis/__init__.py | SPYDER - Automated SPY Options Trading System | 157 |
| **Subtotal** | **22 modules** | **23,671** |

### SpyderG_GUI (Series G)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderG_GUI/SpyderG00_ApplicationManager.py | SPYDER - Autonomous Options Trading System v1.0 | 463 |
| Spyder/SpyderG_GUI/SpyderG01_MainWindow.py | SPYDER - Autonomous Options Trading System v1.0 | 96 |
| Spyder/SpyderG_GUI/SpyderG02_GUIEntry.py | SPYDER - Autonomous Options Trading System v1.0 | 128 |
| Spyder/SpyderG_GUI/SpyderG03_OptionChainWidget.py | SPYDER - Autonomous Options Trading System v1.0 | 227 |
| Spyder/SpyderG_GUI/SpyderG04_ChartWidget.py | SPYDER - Autonomous Options Trading System v1.0 | 1,632 |
| Spyder/SpyderG_GUI/SpyderG05_TradingDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 9,190 |
| Spyder/SpyderG_GUI/SpyderG06_DashboardData.py | SPYDER - Autonomous Options Trading System v1.0 | 756 |
| Spyder/SpyderG_GUI/SpyderG09_RiskParametersDialog.py | SPYDER - Autonomous Options Trading System v1.0 | 1,200 |
| Spyder/SpyderG_GUI/SpyderG100_PositionUpdatedEventHelper.py | Pure parsing for dashboard POSITION_UPDATED events. | 19 |
| Spyder/SpyderG_GUI/SpyderG101_RecentDecisionFlowFetchHelper.py | Pure fetch-plan helpers for recent decision-flow diagnostics. | 29 |
| Spyder/SpyderG_GUI/SpyderG102_MetricsOrchestratorStartHelper.py | Pure start-plan helpers for the custom metrics orchestrator. | 34 |
| Spyder/SpyderG_GUI/SpyderG103_LiveToPaperSwitchHelper.py | Pure dialog plans for the LIVE-to-PAPER mode switch. | 54 |
| Spyder/SpyderG_GUI/SpyderG104_MetricsSnapshotProbeHelper.py | Pure snapshot-probe helpers for the custom metrics orchestrator. | 43 |
| Spyder/SpyderG_GUI/SpyderG105_PaperToLiveSwitchHelper.py | Pure dialog and confirmation plans for the PAPER-to-LIVE switch. | 62 |
| Spyder/SpyderG_GUI/SpyderG106_CustomMetricWidgetUpdateHelper.py | Pure widget-update planning for one S07 custom metric entry. | 62 |
| Spyder/SpyderG_GUI/SpyderG107_CustomMetricSignalPanelSyncHelper.py | Pure signal-panel sync planning for S07 custom metrics. | 73 |
| Spyder/SpyderG_GUI/SpyderG108_CustomMetricBreadthDialogSyncHelper.py | Pure breadth-dialog sync planning for S07 custom metrics. | 64 |
| Spyder/SpyderG_GUI/SpyderG109_RegimePillStateHelper.py | Pure regime-pill state planning for dashboard updates. | 143 |
| Spyder/SpyderG_GUI/SpyderG110_RegimePillStatusHelper.py | Pure stance/stress/gate planning for the regime pill bar. | 60 |
| Spyder/SpyderG_GUI/SpyderG111_RegimeDispatchAnnouncementHelper.py | Pure dispatch announcement planning for the regime pill bar. | 66 |
| Spyder/SpyderG_GUI/SpyderG112_CloseStrategyConfirmHelper.py | Pure confirmation dialog planning for close-strategy UX. | 59 |
| Spyder/SpyderG_GUI/SpyderG113_CloseStrategySuccessHelper.py | Pure success-path UX planning for close-strategy actions. | 40 |
| Spyder/SpyderG_GUI/SpyderG114_CloseStrategyFailureHelper.py | Pure failure-path UX planning for close-strategy actions. | 41 |
| Spyder/SpyderG_GUI/SpyderG115_EventSubscriptionPlanHelper.py | Pure subscription planning for dashboard event wiring. | 63 |
| Spyder/SpyderG_GUI/SpyderG116_EventClockRiskEventHelper.py | Pure event-clock risk-event normalization for the dashboard. | 59 |
| Spyder/SpyderG_GUI/SpyderG117_EventClockOverrideHelper.py | Pure manual event-clock override planning for the dashboard. | 38 |
| Spyder/SpyderG_GUI/SpyderG118_PaperRiskLimitMappingHelper.py | Pure mapping from dashboard risk params to E01 risk limits. | 50 |
| Spyder/SpyderG_GUI/SpyderG119_RingLogBufferHelper.py | Pure ring-log buffering and refresh planning for the dashboard. | 71 |
| Spyder/SpyderG_GUI/SpyderG11_SkewMonitorDialog.py | SPYDER - Autonomous Options Trading System | 1,381 |
| Spyder/SpyderG_GUI/SpyderG120_SystemLogSuppressionHelper.py | Pure system-log suppression helpers for dashboard log filtering. | 74 |
| Spyder/SpyderG_GUI/SpyderG121_AutomationLogRoutingHelper.py | Pure routing and formatting for dashboard automation logs. | 36 |
| Spyder/SpyderG_GUI/SpyderG122_SystemLogVerbosityHelper.py | Pure planning for dashboard system-log verbosity state. | 48 |
| Spyder/SpyderG_GUI/SpyderG123_VetoToggleButtonHelper.py | Pure veto toggle button presentation for the dashboard. | 40 |
| Spyder/SpyderG_GUI/SpyderG124_VetoToggleResultHelper.py | Pure veto toggle outcome planning for the dashboard. | 37 |
| Spyder/SpyderG_GUI/SpyderG125_VetoControlsStateHelper.py | Pure veto controls state resolution for the dashboard. | 36 |
| Spyder/SpyderG_GUI/SpyderG126_VetoControlsPersistPlanHelper.py | Pure veto controls persistence planning for the dashboard. | 42 |
| Spyder/SpyderG_GUI/SpyderG127_StartupReadinessStateEnvelopeHelper.py | Pure startup-readiness state envelope shaping for dashboard startup UX. | 42 |
| Spyder/SpyderG_GUI/SpyderG128_DashboardSnapshotPayloadHelper.py | Pure dashboard snapshot payload shaping for cold-start restore. | 58 |
| Spyder/SpyderG_GUI/SpyderG129_MetricsPayloadMergeHelper.py | Pure merge logic for Market Overview metrics payloads. | 42 |
| Spyder/SpyderG_GUI/SpyderG12_SignalInfoDialog.py | SPYDER - Autonomous Options Trading System | 683 |
| Spyder/SpyderG_GUI/SpyderG130_CachedMetricsFallbackHelper.py | Pure fallback payload normalization for cached Market Overview metrics. | 113 |
| Spyder/SpyderG_GUI/SpyderG131_CachedMarketSnapshotMergeHelper.py | Pure merge logic for startup market snapshot restoration. | 33 |
| Spyder/SpyderG_GUI/SpyderG132_CachedChartCandlesHelper.py | Pure selection logic for cached chart candle payloads. | 20 |
| Spyder/SpyderG_GUI/SpyderG133_CachedChartBarSeriesHelper.py | Pure cached chart bar parsing and filtering helpers. | 66 |
| Spyder/SpyderG_GUI/SpyderG13_EnhancedWidgets.py | SPYDER - Autonomous Options Trading System v1.0 | 1,925 |
| Spyder/SpyderG_GUI/SpyderG14_Dashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 128 |
| Spyder/SpyderG_GUI/SpyderG15_ConnectAPIStatus.py | SPYDER - Autonomous Options Trading System v1.0 | 792 |
| Spyder/SpyderG_GUI/SpyderG16_CircuitBreakerMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 311 |
| Spyder/SpyderG_GUI/SpyderG17_MarketInternalsWidget.py | SPYDER - Autonomous Options Trading System v1.0 | 856 |
| Spyder/SpyderG_GUI/SpyderG17_PaperPositionResolver.py | SPYDER - Autonomous Options Trading System v1.0 | 641 |
| Spyder/SpyderG_GUI/SpyderG18_MarketDataWorker.py | SPYDER - Autonomous Options Trading System v1.0 | 1,774 |
| Spyder/SpyderG_GUI/SpyderG19_ChartIndicators.py | SPYDER - Autonomous Options Trading System v1.0 | 188 |
| Spyder/SpyderG_GUI/SpyderG20_DashboardBuilder.py | SPYDER - Autonomous Options Trading System v1.0 | 1,769 |
| Spyder/SpyderG_GUI/SpyderG21_DashboardSignalHandlers.py | Signal-handler helpers for SpyderG05_TradingDashboard. | 169 |
| Spyder/SpyderG_GUI/SpyderG22_TradeAuditDialog.py | SPYDER - Autonomous Options Trading System v1.0 | 350 |
| Spyder/SpyderG_GUI/SpyderG23_DecisionLogDialog.py | SPYDER - Autonomous Options Trading System v1.0 | 461 |
| Spyder/SpyderG_GUI/SpyderG24_PnlMetricsResolver.py | SPYDER - Autonomous Options Trading System v1.0 | 277 |
| Spyder/SpyderG_GUI/SpyderG25_DashboardSessionAdapter.py | SPYDER - Autonomous Options Trading System v1.0 | 109 |
| Spyder/SpyderG_GUI/SpyderG26_RecentTradeFormatter.py | SPYDER - Autonomous Options Trading System v1.0 | 105 |
| Spyder/SpyderG_GUI/SpyderG27_RecentTradesDialog.py | SPYDER - Autonomous Options Trading System v1.0 | 258 |
| Spyder/SpyderG_GUI/SpyderG28_AccountPanelPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 96 |
| Spyder/SpyderG_GUI/SpyderG29_ChartWidgetPlotly.py | SPYDER - Autonomous Options Trading System v1.0 | 856 |
| Spyder/SpyderG_GUI/SpyderG30_PlotlyDataBridge.py | SPYDER - Autonomous Options Trading System v1.0 | 555 |
| Spyder/SpyderG_GUI/SpyderG31_PlotlyTemplates.py | SPYDER - Autonomous Options Trading System v1.0 | 747 |
| Spyder/SpyderG_GUI/SpyderG32_AgentHealthDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 302 |
| Spyder/SpyderG_GUI/SpyderG33_AccountSnapshotSelector.py | SPYDER - Autonomous Options Trading System v1.0 | 30 |
| Spyder/SpyderG_GUI/SpyderG34_AccountCapitalMath.py | SPYDER - Autonomous Options Trading System v1.0 | 95 |
| Spyder/SpyderG_GUI/SpyderG35_PaperSummaryPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 196 |
| Spyder/SpyderG_GUI/SpyderG36_StripMetricsPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 117 |
| Spyder/SpyderG_GUI/SpyderG37_GreekBarPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 64 |
| Spyder/SpyderG_GUI/SpyderG38_LegacySpreadsTablePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 53 |
| Spyder/SpyderG_GUI/SpyderG39_PaperPositionsTreePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 815 |
| Spyder/SpyderG_GUI/SpyderG40_ToolbarIndexPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 262 |
| Spyder/SpyderG_GUI/SpyderG41_RegimeLiquidityPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 125 |
| Spyder/SpyderG_GUI/SpyderG42_PCADetailPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 464 |
| Spyder/SpyderG_GUI/SpyderG43_CustomMetricDialogPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 328 |
| Spyder/SpyderG_GUI/SpyderG44_RecentDecisionFlowPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 66 |
| Spyder/SpyderG_GUI/SpyderG45_ExecutionHealthPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 78 |
| Spyder/SpyderG_GUI/SpyderG46_ReadinessStatusPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 106 |
| Spyder/SpyderG_GUI/SpyderG47_EventClockDisplayPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 55 |
| Spyder/SpyderG_GUI/SpyderG48_TradingArmingPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 71 |
| Spyder/SpyderG_GUI/SpyderG49_TradingWindowBadgePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 38 |
| Spyder/SpyderG_GUI/SpyderG50_EntryBlockCompactPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 85 |
| Spyder/SpyderG_GUI/SpyderG51_ModeTitlePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 39 |
| Spyder/SpyderG_GUI/SpyderG52_RegimePillBarPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 374 |
| Spyder/SpyderG_GUI/SpyderG53_GoNoGoPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 63 |
| Spyder/SpyderG_GUI/SpyderG54_ReadinessResultPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 52 |
| Spyder/SpyderG_GUI/SpyderG55_ReadinessReportPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 46 |
| Spyder/SpyderG_GUI/SpyderG56_ReadinessStartGatePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 68 |
| Spyder/SpyderG_GUI/SpyderG57_StartTradingPrecheckPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 71 |
| Spyder/SpyderG_GUI/SpyderG58_StartTradingLiveGuardPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 52 |
| Spyder/SpyderG_GUI/SpyderG59_StartTradingFailurePresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 31 |
| Spyder/SpyderG_GUI/SpyderG60_ReadinessStartBlockPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 42 |
| Spyder/SpyderG_GUI/SpyderG61_ReadinessAsyncPresenter.py | SPYDER - Autonomous Options Trading System v1.0 | 48 |
| Spyder/SpyderG_GUI/SpyderG62_ReadinessWorkerCleanupHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 39 |
| Spyder/SpyderG_GUI/SpyderG63_ReadinessSnapshotHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 47 |
| Spyder/SpyderG_GUI/SpyderG64_ReadinessConnectionRefreshHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 50 |
| Spyder/SpyderG_GUI/SpyderG65_ReadinessEventClockSnapshotHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 34 |
| Spyder/SpyderG_GUI/SpyderG66_ReadinessStartupStateHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 37 |
| Spyder/SpyderG_GUI/SpyderG67_ReadinessDecisionHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 72 |
| Spyder/SpyderG_GUI/SpyderG68_ReadinessBypassAuditHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 47 |
| Spyder/SpyderG_GUI/SpyderG69_LiveDataStatusHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 29 |
| Spyder/SpyderG_GUI/SpyderG70_ReadinessCacheDecisionHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 43 |
| Spyder/SpyderG_GUI/SpyderG71_ReadinessGateDecisionHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 49 |
| Spyder/SpyderG_GUI/SpyderG72_PaperSessionQueueHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 66 |
| Spyder/SpyderG_GUI/SpyderG73_PaperSessionFinalizeHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 36 |
| Spyder/SpyderG_GUI/SpyderG74_SessionSupervisorStartHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 36 |
| Spyder/SpyderG_GUI/SpyderG75_SessionSupervisorStartAttemptHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 43 |
| Spyder/SpyderG_GUI/SpyderG76_SessionSupervisorAdoptionHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 55 |
| Spyder/SpyderG_GUI/SpyderG77_LoadingTransitionCompletionHelper.py | SPYDER - Autonomous Options Trading System v1.0 | 47 |
| Spyder/SpyderG_GUI/SpyderG78_LoadingTransitionBeginHelper.py | Pure plan builder for beginning the paper loading transition. | 38 |
| Spyder/SpyderG_GUI/SpyderG79_StartButtonReadyStateHelper.py | Pure plan builder for restoring the idle Start Trading button. | 41 |
| Spyder/SpyderG_GUI/SpyderG80_StartButtonActiveStateHelper.py | Pure plan builder for the steady-state active Start Trading button. | 51 |
| Spyder/SpyderG_GUI/SpyderG81_MarketWorkerSlotInvokeHelper.py | Pure plan builder for market-worker slot invocation. | 37 |
| Spyder/SpyderG_GUI/SpyderG82_QThreadShutdownHelper.py | Pure plan builder for Qt thread shutdown outcomes. | 42 |
| Spyder/SpyderG_GUI/SpyderG83_MetricsOrchestratorShutdownHelper.py | Pure plan builder for dashboard metrics orchestrator shutdown. | 38 |
| Spyder/SpyderG_GUI/SpyderG84_MarketWorkerSignalEmitHelper.py | Pure plan builder for market-worker signal emission. | 26 |
| Spyder/SpyderG_GUI/SpyderG85_MarketWorkerSignalDisconnectHelper.py | Pure plan builder for market-worker signal disconnect selection. | 30 |
| Spyder/SpyderG_GUI/SpyderG86_ShutdownTimerStopHelper.py | Pure plan builder for early shutdown timer stop selection. | 31 |
| Spyder/SpyderG_GUI/SpyderG87_PostWorkerShutdownTimerHelper.py | Pure plan builder for late shutdown timer stop selection. | 26 |
| Spyder/SpyderG_GUI/SpyderG88_MarketWorkerShutdownHelper.py | Pure plan builder for market-worker shutdown gating. | 25 |
| Spyder/SpyderG_GUI/SpyderG89_ShutdownMessageHelper.py | Pure shutdown message copy for dashboard close and snapshot save paths. | 25 |
| Spyder/SpyderG_GUI/SpyderG90_CloseEventShutdownSequenceHelper.py | Pure shutdown sequence plan for dashboard closeEvent orchestration. | 58 |
| Spyder/SpyderG_GUI/SpyderG91_StartupReadinessLogHelper.py | Pure startup-readiness log and button presentation for dashboard warmup. | 96 |
| Spyder/SpyderG_GUI/SpyderG92_StartupReadinessBannerHelper.py | Pure startup-readiness banner copy for the dashboard startup ring buffer. | 74 |
| Spyder/SpyderG_GUI/SpyderG93_StartupReadinessStateHelper.py | Pure startup-readiness state assembly for dashboard startup UX. | 62 |
| Spyder/SpyderG_GUI/SpyderG94_StartupReadinessRefreshHelper.py | Pure orchestration plan for post-paint startup-readiness refresh. | 35 |
| Spyder/SpyderG_GUI/SpyderG95_DJIProxyMultiplierHelper.py | Pure normalization helper for the dashboard DJI proxy multiplier. | 19 |
| Spyder/SpyderG_GUI/SpyderG96_RiskAlertDispatchHelper.py | Pure dedupe and dispatch plan for dashboard risk alert events. | 43 |
| Spyder/SpyderG_GUI/SpyderG97_PendingOrdersGateHelper.py | Pure prompt and outcome copy for the dashboard pending-orders gate. | 79 |
| Spyder/SpyderG_GUI/SpyderG98_ExecutionTelemetryEventHelper.py | Pure parsing for dashboard execution-telemetry events. | 33 |
| Spyder/SpyderG_GUI/SpyderG99_GUILogHandler.py | SPYDER - Autonomous Options Trading System v1.0 | 537 |
| Spyder/SpyderG_GUI/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 329 |
| **Subtotal** | **133 modules** | **36,681** |

### SpyderH_Storage (Series H)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderH_Storage/SpyderH01_DataAccessLayer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,090 |
| Spyder/SpyderH_Storage/SpyderH02_DatabaseManager.py | SPYDER - Autonomous Options Trading System | 938 |
| Spyder/SpyderH_Storage/SpyderH03_MarketDataCache.py | SPYDER - Autonomous Options Trading System v1.0 | 692 |
| Spyder/SpyderH_Storage/SpyderH04_TradeRepository.py | SPYDER - Autonomous Options Trading System v1.0 | 777 |
| Spyder/SpyderH_Storage/SpyderH05_TradingSessionDB.py | SPYDER - Autonomous Options Trading System v1.0 | 1,325 |
| Spyder/SpyderH_Storage/SpyderH07_PerformanceAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 856 |
| Spyder/SpyderH_Storage/SpyderH08_TradeJournal.py | SPYDER - Autonomous Options Trading System v1.0 | 575 |
| Spyder/SpyderH_Storage/__init__.py | Package initializer for SpyderH_Storage. | 85 |
| **Subtotal** | **8 modules** | **6,338** |

### SpyderI_Integration (Series I)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderI_Integration/SpyderI01_IntegrationHub.py | SPYDER - Autonomous Options Trading System v1.0 | 829 |
| Spyder/SpyderI_Integration/SpyderI02_EventRouter.py | SPYDER - Autonomous Options Trading System v1.0 | 1,150 |
| Spyder/SpyderI_Integration/SpyderI03_ConfigManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,431 |
| Spyder/SpyderI_Integration/SpyderI04_DiagnosticsEngine_Core.py | SPYDER - Autonomous Options Trading System v1.0 | 596 |
| Spyder/SpyderI_Integration/SpyderI05_DiagnosticsEngine_Analyzers.py | SPYDER - Autonomous Options Trading System v1.0 | 316 |
| Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py | SPYDER - Autonomous Options Trading System | 1,380 |
| Spyder/SpyderI_Integration/SpyderI07_SyntaxValidator.py | SPYDER - Autonomous Options Trading System | 819 |
| Spyder/SpyderI_Integration/SpyderI08_DiagnosticsEngine_DataCollector.py | SPYDER - Autonomous Options Trading System v1.0 | 650 |
| Spyder/SpyderI_Integration/SpyderI09_DiagnosticsEngine_HealthChecks.py | SPYDER - Autonomous Options Trading System v1.0 | 706 |
| Spyder/SpyderI_Integration/SpyderI10_DiagnosticsEngine_Types.py | SPYDER - Autonomous Options Trading System v1.0 | 441 |
| Spyder/SpyderI_Integration/SpyderI11_DiagnosticsEngine_Utils.py | SPYDER - Autonomous Options Trading System v1.0 | 669 |
| Spyder/SpyderI_Integration/SpyderI12_ModuleRegistry.py | SPYDER - Autonomous Options Trading System v1.0 | 452 |
| Spyder/SpyderI_Integration/__init__.py | Package initializer for SpyderI_Integration. | 306 |
| **Subtotal** | **13 modules** | **9,745** |

### SpyderJ_Alerts (Series J)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderJ_Alerts/SpyderJ01_AlertManager.py | SPYDER - Autonomous Options Trading System v1.0 | 784 |
| Spyder/SpyderJ_Alerts/SpyderJ02_EmailNotifier.py | SPYDER - Autonomous Options Trading System v1.0 | 825 |
| Spyder/SpyderJ_Alerts/SpyderJ03_WebhookNotifier.py | SPYDER - Autonomous Options Trading System v1.0 | 384 |
| Spyder/SpyderJ_Alerts/SpyderJ04_DesktopNotifier.py | SPYDER - Autonomous Options Trading System v1.0 | 781 |
| Spyder/SpyderJ_Alerts/SpyderJ05_TelegramBot.py | SPYDER - Autonomous Options Trading System v1.0 | 2,755 |
| Spyder/SpyderJ_Alerts/__init__.py | SPYDER - Automated SPY Options Trading System | 56 |
| **Subtotal** | **6 modules** | **5,585** |

### SpyderK_Reports (Series K)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderK_Reports/SpyderK01_ReportGenerator.py | SPYDER - Autonomous Options Trading System v1.0 | 299 |
| Spyder/SpyderK_Reports/SpyderK02_DailyTradingReport.py | SPYDER - Autonomous Options Trading System v1.0 | 1,868 |
| Spyder/SpyderK_Reports/SpyderK03_PerformanceDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 939 |
| Spyder/SpyderK_Reports/SpyderK04_ExecutionAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,146 |
| Spyder/SpyderK_Reports/SpyderK05_RiskReport.py | SPYDER - Autonomous Options Trading System v1.0 | 805 |
| Spyder/SpyderK_Reports/SpyderK06_PortfolioAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,454 |
| Spyder/SpyderK_Reports/SpyderK07_StrategyComparison.py | SPYDER - Autonomous Options Trading System v1.0 | 895 |
| Spyder/SpyderK_Reports/SpyderK08_MLPerformanceReport.py | SPYDER - Autonomous Options Trading System v1.0 | 1,625 |
| Spyder/SpyderK_Reports/SpyderK09_RegulatoryReports.py | SPYDER - Autonomous Options Trading System v1.0 | 1,417 |
| Spyder/SpyderK_Reports/SpyderK10_RealTimePerformanceAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,103 |
| Spyder/SpyderK_Reports/SpyderK11_UnifiedSharpeDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 957 |
| Spyder/SpyderK_Reports/SpyderK12_InstitutionalTearSheet.py | SPYDER - Autonomous Options Trading System v1.0 | 787 |
| Spyder/SpyderK_Reports/SpyderK13_StrategyPnLLadder.py | SPYDER - Autonomous Options Trading System v1.0 | 404 |
| Spyder/SpyderK_Reports/__init__.py | SPYDER - Automated SPY Options Trading System | 127 |
| **Subtotal** | **14 modules** | **13,826** |

### SpyderL_ML (Series L)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderL_ML/SpyderL01_MLPredictor.py | SPYDER - Autonomous Options Trading System v1.0 | 1,169 |
| Spyder/SpyderL_ML/SpyderL07_PaperTradeLearner.py | SPYDER - Autonomous Options Trading System v1.0 | 1,675 |
| Spyder/SpyderL_ML/SpyderL08_EntryOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,895 |
| Spyder/SpyderL_ML/SpyderL09_UnifiedRegimeEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 2,426 |
| Spyder/SpyderL_ML/SpyderL10_FeatureEngineering.py | SPYDER - Autonomous Options Trading System v1.0 | 1,314 |
| Spyder/SpyderL_ML/SpyderL11_MLModelManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,168 |
| Spyder/SpyderL_ML/SpyderL12_RandomForestEnsemble.py | SPYDER - Autonomous Options Trading System v1.0 | 765 |
| Spyder/SpyderL_ML/SpyderL13_LSTMPricer.py | SPYDER - Autonomous Options Trading System v1.0 | 823 |
| Spyder/SpyderL_ML/SpyderL14_RealTimePredictor.py | SPYDER - Autonomous Options Trading System v1.0 | 827 |
| Spyder/SpyderL_ML/SpyderL15_MomentPredictor.py | SPYDER - Autonomous Options Trading System v1.0 | 753 |
| Spyder/SpyderL_ML/SpyderL16_OptionsAdjustmentRL.py | SPYDER - Autonomous Options Trading System v1.0 | 2,030 |
| Spyder/SpyderL_ML/SpyderL17_FederatedLearning.py | SPYDER - Autonomous Options Trading System v1.0 | 1,683 |
| Spyder/SpyderL_ML/SpyderL18_EnhancedMLIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 1,246 |
| Spyder/SpyderL_ML/SpyderL19_RLTrainingPipeline.py | SPYDER - Autonomous Options Trading System v1.0 | 795 |
| Spyder/SpyderL_ML/__init__.py | SPYDER - Automated SPY Options Trading System | 134 |
| **Subtotal** | **15 modules** | **18,703** |

### SpyderM_Monitoring (Series M)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderM_Monitoring/SpyderM01_SystemMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 962 |
| Spyder/SpyderM_Monitoring/SpyderM03_AIAgentMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 878 |
| Spyder/SpyderM_Monitoring/SpyderM04_TradingMetrics.py | SPYDER - Autonomous Options Trading System v1.0 | 1,125 |
| Spyder/SpyderM_Monitoring/SpyderM05_TransactionCostAnalysis.py | SPYDER - Autonomous Options Trading System | 1,349 |
| Spyder/SpyderM_Monitoring/SpyderM06_HMMRegimeDetector.py | SPYDER - Autonomous Options Trading System | 1,494 |
| Spyder/SpyderM_Monitoring/SpyderM07_MigrationMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 372 |
| Spyder/SpyderM_Monitoring/SpyderM08_HealthEndpoint.py | SPYDER - Autonomous Options Trading System v1.0 | 342 |
| Spyder/SpyderM_Monitoring/__init__.py | SPYDER - Automated SPY Options Trading System | 76 |
| **Subtotal** | **8 modules** | **6,598** |

### SpyderN_OptionsAnalytics (Series N)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderN_OptionsAnalytics/SpyderN01_OptionsPricer.py | SPYDER - Autonomous Options Trading System | 1,219 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN02_ImpliedVolatilityEngine.py | SPYDER - Autonomous Options Trading System | 1,297 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN03_OptionsChainManager.py | SPYDER - Autonomous Options Trading System | 1,280 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN04_OptionsGreeksCalculator.py | SPYDER - Autonomous Options Trading System | 1,705 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN05_OptionsExpirationManager.py | SPYDER - Autonomous Options Trading System | 1,146 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN06_VolatilitySurfaceBuilder.py | SPYDER - Autonomous Options Trading System | 1,209 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN07_OPRAGreeksHandler.py | SPYDER - Autonomous Options Trading System | 125 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN07_OptionsFlowTracker.py | SPYDER - Autonomous Options Trading System | 1,219 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN08_VolatilitySurface.py | SPYDER - Autonomous Options Trading System v1.0 | 1,384 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN09_GammaExposure.py | SPYDER - Autonomous Options Trading System v1.0 | 1,345 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN10_OptionsFlowAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 638 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN11_OptionsGreeksFlow.py | SPYDER - Autonomous Options Trading System v1.0 | 1,238 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN12_VolatilitySurfaceAI.py | SPYDER - Autonomous Options Trading System v1.0 | 1,281 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN13_MarketImpactModel.py | SPYDER - Autonomous Options Trading System | 1,250 |
| Spyder/SpyderN_OptionsAnalytics/SpyderN14_OptionsDataVetter.py | SPYDER - Autonomous Options Trading System v1.0 | 465 |
| Spyder/SpyderN_OptionsAnalytics/__init__.py | SPYDER - Automated SPY Options Trading System | 125 |
| **Subtotal** | **16 modules** | **16,926** |

### SpyderO_TradingIntelligence (Series O)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderO_TradingIntelligence/SpyderO01_CoreTechnicalIndicators.py | SPYDER - Autonomous Options Trading System v1.0 | 1,281 |
| Spyder/SpyderO_TradingIntelligence/SpyderO02_TradingOpportunityScanner.py | SPYDER - Autonomous Options Trading System v1.0 | 1,340 |
| Spyder/SpyderO_TradingIntelligence/SpyderO03_StrategyOptimizers.py | SPYDER - Autonomous Options Trading System v1.0 | 1,883 |
| Spyder/SpyderO_TradingIntelligence/__init__.py | Package initializer for SpyderO_TradingIntelligence. | 349 |
| **Subtotal** | **4 modules** | **4,853** |

### SpyderP_PortfolioMgmt (Series P)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderP_PortfolioMgmt/SpyderP00_GlobalPortfolioRegistry.py | Lightweight global PortfolioManager registry for startup-sensitive paths. | 49 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP01_PortfolioManager.py | SPYDER - Autonomous Options Trading System v1.0 | 2,233 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP02_AllocationOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 2,225 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP03_CorrelationAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 736 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP04_CapitalAllocator.py | SPYDER - Autonomous Options Trading System | 1,638 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP05_MultiStrategyAllocator.py | SPYDER - Autonomous Options Trading System | 1,355 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP06_StrategyRotation.py | SPYDER - Autonomous Options Trading System | 1,314 |
| Spyder/SpyderP_PortfolioMgmt/SpyderP07_RenaissancePositionSizer.py | SPYDER - Autonomous Options Trading System v1.0 | 686 |
| Spyder/SpyderP_PortfolioMgmt/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 309 |
| **Subtotal** | **9 modules** | **10,545** |

### SpyderQ_Scripts (Series Q)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderQ_Scripts/SpyderQ01_FixExceptionHandling.py | SPYDER - Autonomous Options Trading System v1.0 | 485 |
| Spyder/SpyderQ_Scripts/SpyderQ02_ValidateEnv.py | SPYDER - Autonomous Options Trading System v1.0 | 348 |
| Spyder/SpyderQ_Scripts/SpyderQ03_ValidateConfiguration.py | SPYDER - Autonomous Options Trading System v1.0 | 409 |
| Spyder/SpyderQ_Scripts/SpyderQ04_LaunchDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 520 |
| Spyder/SpyderQ_Scripts/SpyderQ05_LaunchDashboardProactive.py | SPYDER - Autonomous Options Trading System v1.0 | 569 |
| Spyder/SpyderQ_Scripts/SpyderQ06_LaunchDashboardDirect.py | SPYDER - Autonomous Options Trading System v1.0 | 589 |
| Spyder/SpyderQ_Scripts/SpyderQ07_TestGUILogging.py | SPYDER - Autonomous Options Trading System v1.0 | 165 |
| Spyder/SpyderQ_Scripts/SpyderQ08_ValidatePackageExports.py | SPYDER - Autonomous Options Trading System v1.0 | 386 |
| Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py | SPYDER - Autonomous Options Trading System v1.0 | 375 |
| Spyder/SpyderQ_Scripts/SpyderQ10_ProtocolComplianceGate.py | SPYDER - Autonomous Options Trading System v1.0 | 498 |
| Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py | SPYDER - Autonomous Options Trading System v1.0 | 891 |
| Spyder/SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py | SPYDER - Autonomous Options Trading System v1.0 | 377 |
| Spyder/SpyderQ_Scripts/SpyderQ25_SystemMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 184 |
| Spyder/SpyderQ_Scripts/SpyderQ45_Diagnostics.py | SPYDER - Autonomous Options Trading System v1.0 | 261 |
| Spyder/SpyderQ_Scripts/SpyderQ80_VerifyDashboardIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 476 |
| Spyder/SpyderQ_Scripts/SpyderQ90_SystemUtilities.py | SPYDER - Autonomous Options Trading System v1.0 | 884 |
| Spyder/SpyderQ_Scripts/SpyderQ92_DiagnosticsUtilities.py | SPYDER - Autonomous Options Trading System v1.0 | 1,658 |
| Spyder/SpyderQ_Scripts/SpyderQ93_RunPaper.py | SPYDER - Autonomous Options Trading System v1.0 | 552 |
| Spyder/SpyderQ_Scripts/SpyderQ96_CollectFinetuneData.py | SPYDER - Autonomous Options Trading System v1.0 | 274 |
| Spyder/SpyderQ_Scripts/SpyderQ98_FinetuneGemma4Spyder.py | SPYDER - Autonomous Options Trading System v1.0 | 335 |
| Spyder/SpyderQ_Scripts/SpyderQ99_ApplyPythonFormatting.py | Script to apply standard Python formatting to all Spyder modules | 326 |
| Spyder/SpyderQ_Scripts/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 303 |
| Spyder/SpyderQ_Scripts/analyze_logs.py | Module for analyze logs functionality. | 56 |
| Spyder/SpyderQ_Scripts/check_quotes.py | Module for check quotes functionality. | 49 |
| Spyder/SpyderQ_Scripts/launch_dashboard_with_proactive_connections.py | Backward-compatible launcher shim. | 35 |
| Spyder/SpyderQ_Scripts/launch_spyder_dashboard_direct.py | Backward-compatible launcher shim. | 35 |
| Spyder/SpyderQ_Scripts/launch_spyder_working_dashboard.py | Backward-compatible launcher shim. | 35 |
| Spyder/SpyderQ_Scripts/restore_script.py | Module for restore script functionality. | 32 |
| **Subtotal** | **28 modules** | **11,107** |

### SpyderR_Runtime (Series R)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderR_Runtime/SpyderR02_PaperEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 818 |
| Spyder/SpyderR_Runtime/SpyderR03_PaperMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 851 |
| Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 4,178 |
| Spyder/SpyderR_Runtime/SpyderR05_LivenessMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 308 |
| Spyder/SpyderR_Runtime/SpyderR06_PaperTradingHarness.py | SPYDER - Autonomous Options Trading System v1.0 | 1,016 |
| Spyder/SpyderR_Runtime/SpyderR07_LiveDashboard.py | SPYDER - Autonomous Options Trading System v1.0 | 542 |
| Spyder/SpyderR_Runtime/SpyderR08_PaperTradingQtWorker.py | SPYDER - Autonomous Options Trading System v1.0 | 2,841 |
| Spyder/SpyderR_Runtime/SpyderR09_ProductionDeploymentManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,807 |
| Spyder/SpyderR_Runtime/SpyderR11_PaperStrategyRunner.py | SPYDER - Autonomous Options Trading System v1.0 | 1,659 |
| Spyder/SpyderR_Runtime/SpyderR12_SessionSupervisor.py | SPYDER - Autonomous Options Trading System v1.0 | 2,214 |
| Spyder/SpyderR_Runtime/SpyderR13_FillReconciler.py | SPYDER - Autonomous Options Trading System v1.0 | 525 |
| Spyder/SpyderR_Runtime/SpyderR14_ExitMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 1,151 |
| Spyder/SpyderR_Runtime/SpyderR15_PaperBroker.py | SPYDER - Autonomous Options Trading System v1.0 | 519 |
| Spyder/SpyderR_Runtime/SpyderR16_PaperSandboxReplay.py | SPYDER - Autonomous Options Trading System v1.0 | 209 |
| Spyder/SpyderR_Runtime/__init__.py | SPYDER - Automated SPY Options Trading System | 81 |
| **Subtotal** | **15 modules** | **18,719** |

### SpyderS_Signals (Series S)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderS_Signals/SpyderS01_DIXCalculator.py | SPYDER - Autonomous Options Trading System v1.0 | 765 |
| Spyder/SpyderS_Signals/SpyderS02_DIXScheduler.py | SPYDER - Autonomous Options Trading System v1.0 | 974 |
| Spyder/SpyderS_Signals/SpyderS03_BlackSwanIndicator.py | SPYDER - Autonomous Options Trading System | 796 |
| Spyder/SpyderS_Signals/SpyderS04_BlackSwanScheduler.py | SPYDER - Autonomous Options Trading System v1.0 | 1,592 |
| Spyder/SpyderS_Signals/SpyderS05_GEXDEXCalculator.py | SPYDER - Autonomous Options Trading System | 648 |
| Spyder/SpyderS_Signals/SpyderS06_SKEWCalculator.py | SPYDER - Autonomous Options Trading System | 1,433 |
| Spyder/SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py | SPYDER - Autonomous Options Trading System v1.0 | 3,480 |
| Spyder/SpyderS_Signals/SpyderS08_PivotMeanReversionSignal.py | SPYDER - Autonomous Options Trading System v1.0 | 381 |
| Spyder/SpyderS_Signals/SpyderS08_ShortSqueezeDetector.py | SPYDER - Autonomous Options Trading System v1.0 | 1,347 |
| Spyder/SpyderS_Signals/SpyderS09_FREDClient.py | SPYDER - Autonomous Options Trading System v1.0 | 338 |
| Spyder/SpyderS_Signals/SpyderS10_SentimentScraper.py | SPYDER - Autonomous Options Trading System v1.0 | 673 |
| Spyder/SpyderS_Signals/SpyderS11_TradingViewInternals.py | SPYDER - Autonomous Options Trading System v1.0 | 551 |
| Spyder/SpyderS_Signals/SpyderS12_WRSSignal.py | SPYDER - Autonomous Options Trading System v1.0 | 1,029 |
| Spyder/SpyderS_Signals/SpyderS13_PSRSignal.py | SPYDER - Autonomous Options Trading System v1.0 | 1,016 |
| Spyder/SpyderS_Signals/SpyderS14_PCASignals.py | SPYDER - Autonomous Options Trading System v1.0 | 943 |
| Spyder/SpyderS_Signals/SpyderS15_MarketIntelClient.py | SPYDER - Autonomous Options Trading System v1.0 | 326 |
| Spyder/SpyderS_Signals/SpyderS16_MarketSnapshotLLM.py | SPYDER - Autonomous Options Trading System v1.0 | 265 |
| Spyder/SpyderS_Signals/SpyderS18_EconomicCalendar.py | SPYDER - Autonomous Options Trading System v1.0 | 418 |
| Spyder/SpyderS_Signals/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 91 |
| **Subtotal** | **19 modules** | **17,066** |

### SpyderT_Testing (Series T)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderT_Testing/SpyderT01_UnitTestFramework.py | SPYDER - Autonomous Options Trading System v1.0 | 1,937 |
| Spyder/SpyderT_Testing/SpyderT03_BlackSwanValidator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,207 |
| Spyder/SpyderT_Testing/SpyderT06_EvolvedStrategyTest.py | SPYDER - Autonomous Options Trading System v1.0 | 874 |
| Spyder/SpyderT_Testing/SpyderT07_AdvancedEvolutionPush.py | SPYDER - Autonomous Options Trading System v1.0 | 366 |
| Spyder/SpyderT_Testing/SpyderT08_FixedSystemIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 432 |
| Spyder/SpyderT_Testing/SpyderT09_TestDashboard.py | SPYDER - Autonomous Options Trading System | 3,369 |
| Spyder/SpyderT_Testing/SpyderT100_OrderExecutionIntegration_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 304 |
| Spyder/SpyderT_Testing/SpyderT100_U13TechnicalIndicators_U15PerformanceMetrics.py | SPYDER - Test Suite T100 | 1,082 |
| Spyder/SpyderT_Testing/SpyderT101_CircuitBreaker_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 284 |
| Spyder/SpyderT_Testing/SpyderT101_U14OptionStrategies_U10TradingCalendar.py | SPYDER - Test Suite T101 | 985 |
| Spyder/SpyderT_Testing/SpyderT102_U18DependencyAnalyzer_U19InteractionMatrix.py | SPYDER - Autonomous Options Trading System v1.0 | 1,174 |
| Spyder/SpyderT_Testing/SpyderT103_U20InstitutionalLibraries.py | SPYDER - Autonomous Options Trading System v1.0 | 768 |
| Spyder/SpyderT_Testing/SpyderT104_U22ETTimeDisplay_U16TechnicalAnalysis.py | SPYDER - Autonomous Options Trading System v1.0 | 767 |
| Spyder/SpyderT_Testing/SpyderT105_U23MemoryMonitor_U27SystemOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 1,082 |
| Spyder/SpyderT_Testing/SpyderT106_ACore.py | SPYDER - Autonomous Options Trading System v1.0 | 1,640 |
| Spyder/SpyderT_Testing/SpyderT107_FSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 1,528 |
| Spyder/SpyderT_Testing/SpyderT108_NSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 1,003 |
| Spyder/SpyderT_Testing/SpyderT109_SSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 745 |
| Spyder/SpyderT_Testing/SpyderT10_DashboardRisk.py | SPYDER - Autonomous Options Trading System v1.0 | 954 |
| Spyder/SpyderT_Testing/SpyderT110_VSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 904 |
| Spyder/SpyderT_Testing/SpyderT111_LSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 1,480 |
| Spyder/SpyderT_Testing/SpyderT112_ESeries.py | SPYDER - Autonomous Options Trading System v1.0 | 1,435 |
| Spyder/SpyderT_Testing/SpyderT113_BSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 838 |
| Spyder/SpyderT_Testing/SpyderT114_DSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 2,004 |
| Spyder/SpyderT_Testing/SpyderT115_HSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 350 |
| Spyder/SpyderT_Testing/SpyderT116_RSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 2,189 |
| Spyder/SpyderT_Testing/SpyderT117_PSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 991 |
| Spyder/SpyderT_Testing/SpyderT118_YSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 620 |
| Spyder/SpyderT_Testing/SpyderT119_CSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 268 |
| Spyder/SpyderT_Testing/SpyderT11_EliteEvolvedStrategyTest.py | SPYDER - Autonomous Options Trading System v1.0 | 512 |
| Spyder/SpyderT_Testing/SpyderT120_GSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 136 |
| Spyder/SpyderT_Testing/SpyderT120_S07OptionsAnalytics.py | SPYDER - Autonomous Options Trading System v1.0 | 535 |
| Spyder/SpyderT_Testing/SpyderT121_ISeries.py | SPYDER - Autonomous Options Trading System v1.0 | 531 |
| Spyder/SpyderT_Testing/SpyderT122_JSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 233 |
| Spyder/SpyderT_Testing/SpyderT123_KSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 162 |
| Spyder/SpyderT_Testing/SpyderT124_MSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 217 |
| Spyder/SpyderT_Testing/SpyderT125_OSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 215 |
| Spyder/SpyderT_Testing/SpyderT126_QSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 159 |
| Spyder/SpyderT_Testing/SpyderT127_XSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 208 |
| Spyder/SpyderT_Testing/SpyderT128_ZSeries.py | SPYDER - Autonomous Options Trading System v1.0 | 233 |
| Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py | SPYDER - Autonomous Options Trading System v1.0 | 2,206 |
| Spyder/SpyderT_Testing/SpyderT12_FullSystemIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 628 |
| Spyder/SpyderT_Testing/SpyderT130_IronCondorSandbox_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 334 |
| Spyder/SpyderT_Testing/SpyderT130_S06SKEWCalculator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,199 |
| Spyder/SpyderT_Testing/SpyderT131_PivotMRSignalTests.py | SPYDER - Autonomous Options Trading System v1.0 | 338 |
| Spyder/SpyderT_Testing/SpyderT132_BrokerProtocolParity.py | SPYDER - Autonomous Options Trading System v1.0 | 104 |
| Spyder/SpyderT_Testing/SpyderT133_BrokerChaos.py | SPYDER - Autonomous Options Trading System v1.0 | 116 |
| Spyder/SpyderT_Testing/SpyderT134_A02_EntryTrustGate.py | Focused tests for A02 direct signal trust gating via F09 controls. | 359 |
| Spyder/SpyderT_Testing/SpyderT135_A04_EventClockFeed.py | Focused tests for A04 event-clock feed transitions. | 221 |
| Spyder/SpyderT_Testing/SpyderT136_B02_ExecutionFeedContract.py | Focused tests for B02 execution telemetry feed contract. | 81 |
| Spyder/SpyderT_Testing/SpyderT137_B02K04_ExecutionTelemetryPipeline.py | Phase 5-C: B02→K04 Execution Telemetry Pipeline Integration Tests | 322 |
| Spyder/SpyderT_Testing/SpyderT138_B02_LiquidityGateContract.py | Focused tests for B02 liquidity gate contract behavior. | 113 |
| Spyder/SpyderT_Testing/SpyderT140_C16_CacheConsolidation.py | Tests for C16/H03 cache consolidation behavior. | 109 |
| Spyder/SpyderT_Testing/SpyderT141_D31_EntryTrustGate.py | Focused tests for D31 entry trust gating via F09 market-structure controls. | 1,031 |
| Spyder/SpyderT_Testing/SpyderT142_D31_StrategyRegistryWiring.py | Focused tests for D31 strategy registry and auto-selection wiring. | 476 |
| Spyder/SpyderT_Testing/SpyderT143_D31_AdmissionGuardrails.py | Focused tests for D31 strategy admission guardrails. | 270 |
| Spyder/SpyderT_Testing/SpyderT143_E00_RiskProtocol.py | Tests for SpyderE00_RiskProtocol | 172 |
| Spyder/SpyderT_Testing/SpyderT144_E16_EventClockRestrictions.py | Focused tests for E16 event-clock order restrictions. | 38 |
| Spyder/SpyderT_Testing/SpyderT145_Test_EventClockPipelineIntegration.py | Integration-style tests for A04 -> F09/E16 event-clock blackout pipeline. | 120 |
| Spyder/SpyderT_Testing/SpyderT146_F00_AnalysisProtocol.py | Tests for SpyderF00_AnalysisProtocol | 135 |
| Spyder/SpyderT_Testing/SpyderT147_F09_DecisionPathControls.py | Focused tests for F09 decision-path market-structure and trust controls. | 180 |
| Spyder/SpyderT_Testing/SpyderT148_F09_EventClockBlackout.py | Focused tests for F09 event-clock blackout behavior. | 59 |
| Spyder/SpyderT_Testing/SpyderT149_F09_LiquidityGate.py | Focused tests for F09 liquidity gate helper. | 394 |
| Spyder/SpyderT_Testing/SpyderT14_RiskSuiteIntegrationTest.py | SPYDER - Autonomous Options Trading System v1.0 | 623 |
| Spyder/SpyderT_Testing/SpyderT150_G05_EventClockDisplay.py | SPYDER - Autonomous Options Trading System v1.0 | 355 |
| Spyder/SpyderT_Testing/SpyderT151_G05_EventClockHandlerIntegration.py | Integration-style tests for A04 event-clock payload consumption by G05. | 88 |
| Spyder/SpyderT_Testing/SpyderT152_G05_ExecutionTelemetryHandler.py | Focused tests for G05 execution telemetry handler wiring. | 117 |
| Spyder/SpyderT_Testing/SpyderT153_G05_GoNoGoCheck.py | Focused tests for G05 pre-open Go/No-Go checklist behavior. | 156 |
| Spyder/SpyderT_Testing/SpyderT154_G13_SignalMonitorStyles.py | Regression tests for G13 Signal Monitor styling integrity. | 102 |
| Spyder/SpyderT_Testing/SpyderT155_G32_AgentHealthDashboard.py | Tests for SpyderG32_AgentHealthDashboard | 77 |
| Spyder/SpyderT_Testing/SpyderT156_J03_WebhookNotifier.py | Tests for SpyderJ03_WebhookNotifier | 110 |
| Spyder/SpyderT_Testing/SpyderT157_K13_StrategyPnlLadder.py | Tests for SpyderK13_StrategyPnLLadder | 131 |
| Spyder/SpyderT_Testing/SpyderT158_N06_TermStructureSnapshot.py | Focused tests for N06 term-structure snapshot generation. | 198 |
| Spyder/SpyderT_Testing/SpyderT159_N09_DealerWallsSnapshot.py | Focused tests for N09 GammaExposureCalculator.get_dealer_walls_snapshot(). | 144 |
| Spyder/SpyderT_Testing/SpyderT15_FullSystemTest.py | SPYDER - Autonomous Options Trading System | 598 |
| Spyder/SpyderT_Testing/SpyderT160_N11_VannaCharmSnapshot.py | Focused tests for N11 OptionsGreeksFlowAnalyzer.get_vanna_charm_snapshot(). | 161 |
| Spyder/SpyderT_Testing/SpyderT161_S07_BreadthQualityFeed.py | Focused tests for S07 sector breadth expansion + data-quality feed (Phases 11/12). | 230 |
| Spyder/SpyderT_Testing/SpyderT162_S07_DealerFlowMetrics.py | Focused tests for S07 dealer-flow metrics update pipeline (Phase 9). | 229 |
| Spyder/SpyderT_Testing/SpyderT164_S07_LiquidityDiagnostics.py | Focused tests for S07 liquidity diagnostics publication. | 223 |
| Spyder/SpyderT_Testing/SpyderT165_S07_VolSurfaceMetrics.py | Focused tests for S07 vol-surface publication. | 137 |
| Spyder/SpyderT_Testing/SpyderT166_Test_SharpeComparison.py | Test script to demonstrate Sharpe Ratio enhancements. | 294 |
| Spyder/SpyderT_Testing/SpyderT167_Test_Stage3DecisionQualitySlo.py | Stage 3 decision-quality SLO tests. | 263 |
| Spyder/SpyderT_Testing/SpyderT168_Test_Stage4OperationalReadiness.py | Stage 4 operational-readiness tests. | 499 |
| Spyder/SpyderT_Testing/SpyderT169_Test_StrategySignalContracts.py | Focused signal-contract tests for legacy D-series strategies. | 379 |
| Spyder/SpyderT_Testing/SpyderT16_SystemHealthMonitor.py | SPYDER - Autonomous Options Trading System | 433 |
| Spyder/SpyderT_Testing/SpyderT170_U46_SecretsManager.py | Tests for SpyderU46_SecretsManager | 97 |
| Spyder/SpyderT_Testing/SpyderT171_V09_IvEngine.py | Tests for SpyderV09_IVEngine | 180 |
| Spyder/SpyderT_Testing/SpyderT172_Z00_BrokerProtocol.py | Tests for SpyderZ00_BrokerProtocol | 151 |
| Spyder/SpyderT_Testing/SpyderT173_R05_U42_Coverage.py | Focused tests for R05 liveness monitor and U42 strategy circuit breaker. | 160 |
| Spyder/SpyderT_Testing/SpyderT174_LowCoverageBatch.py | Focused low-coverage tests for utility and monitoring stubs. | 395 |
| Spyder/SpyderT_Testing/SpyderT175_B06_U47_Coverage.py | Focused coverage tests for B06, B21, U47, and E02 shim modules. | 255 |
| Spyder/SpyderT_Testing/SpyderT176_Q03_Q08_Q09_Coverage.py | Focused coverage tests for Q03, Q08, and Q09 validator scripts. | 260 |
| Spyder/SpyderT_Testing/SpyderT177_Q02_I12_Coverage.py | Coverage tests for Q02 environment validation and I12 module registry. | 193 |
| Spyder/SpyderT_Testing/SpyderT178_Q10_Coverage.py | Coverage tests for SpyderQ10_ProtocolComplianceGate. | 263 |
| Spyder/SpyderT_Testing/SpyderT179_T54_T142_IsolationRegression.py | Deterministic in-process isolation regression for T54/T142. | 46 |
| Spyder/SpyderT_Testing/SpyderT17_ComprehensiveSystemTest.py | Module for comprehensivesystemtest functionality. | 1,323 |
| Spyder/SpyderT_Testing/SpyderT180_E01_AgentVetoObserveOnly.py | Tests for E01 observe-only handling of Y03 agent veto state. | 57 |
| Spyder/SpyderT_Testing/SpyderT181_N14_IvNormalization.py | Regression tests for N14 IV normalization behavior. | 48 |
| Spyder/SpyderT_Testing/SpyderT182_AutonomousDecisionContract.py | Drift guard for autonomous decision and regime input contracts. | 148 |
| Spyder/SpyderT_Testing/SpyderT183_Phase2SymbolCatalog.py | Phase 2 guardrails for canonical symbol governance. | 341 |
| Spyder/SpyderT_Testing/SpyderT184_RegimeV2DeterministicContract.py | Deterministic v2 regime and strategy-gating contract tests. | 489 |
| Spyder/SpyderT_Testing/SpyderT185_D31_MarketDataCacheShape.py | Regression test for D31 market_data_cache shape. | 148 |
| Spyder/SpyderT_Testing/SpyderT186_E01_ColdStartFailClosed.py | SPEC-10 — E01 cold-start fail-closed when tradier_client is missing in live. | 127 |
| Spyder/SpyderT_Testing/SpyderT186_S14_PCASignals.py | Focused tests for the PCA proxy custom metrics. | 435 |
| Spyder/SpyderT_Testing/SpyderT187_D31_ColdStartRegimeUnknown.py | SPEC-5 — D31 must fail-closed to a no-trade regime when SPY/VIX cache is cold. | 185 |
| Spyder/SpyderT_Testing/SpyderT187_G05_PCADetailDialogs.py | Focused tests for G05 PCA detail dialog helpers. | 698 |
| Spyder/SpyderT_Testing/SpyderT188_G05_MarketWorkerThreadSafety.py | Focused tests for G05 market-worker thread handoff behavior. | 219 |
| Spyder/SpyderT_Testing/SpyderT188_R12_OrderManagerWiring.py | SPEC-6 — R12 SessionSupervisor must wire OrderManager in live mode. | 180 |
| Spyder/SpyderT_Testing/SpyderT189_E03_StopLossBrokerRejection.py | SPEC-13 — E03 stop-loss must surface broker rejection, not silently downgrade. | 157 |
| Spyder/SpyderT_Testing/SpyderT189_G05_TradingArmingTransitions.py | Focused tests for G05 REAL/PAPER arming transitions. | 141 |
| Spyder/SpyderT_Testing/SpyderT18_EnhancedSharpeCalculator.py | SPYDER - Automated SPY Options Trading System | 588 |
| Spyder/SpyderT_Testing/SpyderT190_E01_DailyLossFromBrokerPnL.py | SPEC-9 — E01 daily-loss kill switch must read broker P&L, not local zeros. | 189 |
| Spyder/SpyderT_Testing/SpyderT191_B40_RetryIdempotency.py | SPEC-4 — B40 retry layer must NOT auto-retry POST/PUT/DELETE on 5xx. | 229 |
| Spyder/SpyderT_Testing/SpyderT192_TelegramOperatorCommands.py | T192 — Telegram operator command controls for halt/resume/flatten. | 708 |
| Spyder/SpyderT_Testing/SpyderT193_D31_DispatchResultHardening.py | T193 — D31 dispatch is robust when walk_result lacks standard attributes. | 189 |
| Spyder/SpyderT_Testing/SpyderT194_R12_RiskManagerInjection.py | T194 — R12 SessionSupervisor must inject the synced RiskManager into D31. | 128 |
| Spyder/SpyderT_Testing/SpyderT195_D31_DispatchStateBadge.py | T195 — D31 ``get_dispatch_state()`` powers the G05 DISPATCH pill. | 359 |
| Spyder/SpyderT_Testing/SpyderT196_Q92_TradingHealthReport.py | Focused tests for the Q92 trading-health diagnostics report. | 169 |
| Spyder/SpyderT_Testing/SpyderT196_R12_LiveOnlyTradierPolicy.py | T196 - R12 must fail fast on any sandbox Tradier request. | 89 |
| Spyder/SpyderT_Testing/SpyderT197_C29_LiveOnlyPolicy.py | T197 — C29 DataProviderRouter live-only market-data policy tests. | 66 |
| Spyder/SpyderT_Testing/SpyderT198_A03_ConfigManagerCompatibility.py | Regression tests for A03 ConfigManager compatibility APIs. | 32 |
| Spyder/SpyderT_Testing/SpyderT199_C01_DataFeedStartupFailClosed.py | Focused tests for C01 startup fail-closed behavior. | 134 |
| Spyder/SpyderT_Testing/SpyderT19_SharpeRatioCalculator.py | SPYDER - Automated SPY Options Trading System | 361 |
| Spyder/SpyderT_Testing/SpyderT200_A01_ShutdownOrder.py | Focused tests for A01 shutdown ordering around GUI and SessionSupervisor. | 782 |
| Spyder/SpyderT_Testing/SpyderT202_C01_StopIdempotency.py | Focused regression tests for idempotent C01 shutdown behavior. | 33 |
| Spyder/SpyderT_Testing/SpyderT203_G05_ShutdownThreadCleanup.py | Focused tests for G05 shutdown-time thread cleanup helpers. | 514 |
| Spyder/SpyderT_Testing/SpyderT204_I03_ConfigManagerShutdown.py | Focused tests for I03 ConfigManager shutdown cleanup. | 69 |
| Spyder/SpyderT_Testing/SpyderT205_S07_DixStartupNonBlocking.py | Focused tests for non-blocking S07 DIX startup behavior. | 211 |
| Spyder/SpyderT_Testing/SpyderT206_A01_ShutdownBreadthRefresh.py | Launcher-backed regression for shutdown during a live breadth refresh. | 170 |
| Spyder/SpyderT_Testing/SpyderT207_G05_MarketDataReadiness.py | Focused tests for G05 market-data readiness gating. | 2,100 |
| Spyder/SpyderT_Testing/SpyderT208_G05_SessionSupervisorReuse.py | Focused tests for G05 SessionSupervisor reuse. | 564 |
| Spyder/SpyderT_Testing/SpyderT209_G05_RegimePillExecutionTruth.py | Focused regression for G05 stance/gate execution-truth rendering. | 231 |
| Spyder/SpyderT_Testing/SpyderT209_ZPackageLazyExports.py | Focused regressions for lazy SpyderZ_Communication package exports. | 55 |
| Spyder/SpyderT_Testing/SpyderT20_DIXDemo.py | SPYDER - Autonomous Options Trading System v1.0 | 579 |
| Spyder/SpyderT_Testing/SpyderT210_D02_IronCondorNoSignalDiagnostics.py | Focused regressions for D02 Iron Condor no-entry diagnostics. | 182 |
| Spyder/SpyderT_Testing/SpyderT210_PPackageLazyRegistry.py | Focused regressions for lazy SpyderP_PortfolioMgmt package exports. | 65 |
| Spyder/SpyderT_Testing/SpyderT211_D32_IVRankHintIntegration.py | Focused regressions for D32 live IV-rank hint handling. | 143 |
| Spyder/SpyderT_Testing/SpyderT211_R14_LazyPortfolioManager.py | Focused regressions for lazy ExitMonitor portfolio manager resolution. | 159 |
| Spyder/SpyderT_Testing/SpyderT211_S07_CustomMetricsStartup.py | Regression tests for S07 startup behavior. | 72 |
| Spyder/SpyderT_Testing/SpyderT212_D31_StartupDeferral.py | Focused regressions for paper-mode D31 startup deferral. | 382 |
| Spyder/SpyderT_Testing/SpyderT212_G05_PaperPositionFallback.py | Focused regression for paper-mode position fallback in G05. | 752 |
| Spyder/SpyderT_Testing/SpyderT213_A05_AtexitCleanup.py | Focused regressions for quiet EventManager atexit cleanup. | 49 |
| Spyder/SpyderT_Testing/SpyderT213_D31_PaperIronCondorWrappedSignal.py | Regression for wrapped TradingSignal payloads on D31 paper iron-condor dispatch. | 253 |
| Spyder/SpyderT_Testing/SpyderT214_G05_RecentDecisionFlowDiagnostics.py | Focused tests for G05 recent decision-flow diagnostics rendering. | 109 |
| Spyder/SpyderT_Testing/SpyderT215_A05_EventManagerLegacySchema.py | Focused regression for A05 EventManager legacy event_log schema migration. | 65 |
| Spyder/SpyderT_Testing/SpyderT215_Q93_RunPaperPolicy.py | Focused regressions for the Q93 paper-launcher trading-mode gate. | 102 |
| Spyder/SpyderT_Testing/SpyderT215_QDesktopLauncherAutostart.py | Focused regression coverage for desktop-launcher paper autostart defaults. | 33 |
| Spyder/SpyderT_Testing/SpyderT216_B03_PaperStateCarryover.py | Focused tests for paper PositionTracker state carryover handling. | 101 |
| Spyder/SpyderT_Testing/SpyderT216_C17_TradierConnectionPolicy.py | Focused policy regression for C17 Tradier connection defaults. | 15 |
| Spyder/SpyderT_Testing/SpyderT217_G05_OffHoursCacheRestore.py | Focused tests for G05 off-hours cache restore behavior. | 383 |
| Spyder/SpyderT_Testing/SpyderT217_R11_ZeroDTEProfile.py | Focused regressions for the R11 paper-run ZeroDTE profile hook. | 526 |
| Spyder/SpyderT_Testing/SpyderT218_R12_FreshnessMonitorThresholds.py | Focused tests for R12 freshness-monitor threshold resolution. | 133 |
| Spyder/SpyderT_Testing/SpyderT219_D31_ODTEOverlaySlot.py | Scaffold tests for D31 ODTE Pivot overlay slot admission and disable behavior. | 22 |
| Spyder/SpyderT_Testing/SpyderT219_R12_ExitMonitorAuthoritativePositions.py | Focused tests for R12 paper ExitMonitor authoritative-position wiring. | 773 |
| Spyder/SpyderT_Testing/SpyderT21_DIXQuickStart.py | SPYDER - Autonomous Options Trading System v1.0 | 614 |
| Spyder/SpyderT_Testing/SpyderT220_D02_IronCondorExitMonitor.py | Focused regressions for D02 Iron Condor ExitMonitor integration. | 109 |
| Spyder/SpyderT_Testing/SpyderT220_E01_OverlayPretradeVerdict.py | Scaffold tests for E01 overlay pre-trade verdict API contract. | 22 |
| Spyder/SpyderT_Testing/SpyderT221_PaperIronCondorExitSmoke.py | Focused paper-mode smoke for Iron Condor exit flow. | 210 |
| Spyder/SpyderT_Testing/SpyderT222_D31_OverlayAuditSchema.py | Scaffold tests for D31 ODTE overlay audit and telemetry schema. | 22 |
| Spyder/SpyderT_Testing/SpyderT222_G24_PnlMetricsResolver.py | Focused tests for pure dashboard P&L metric helpers. | 107 |
| Spyder/SpyderT_Testing/SpyderT223_G05_PnlTableRefresh.py | Thin regression for G05 P&L table refresh orchestration. | 75 |
| Spyder/SpyderT_Testing/SpyderT224_G26_RecentTradeFormatter.py | Focused regressions for recent-trade formatting extraction. | 157 |
| Spyder/SpyderT_Testing/SpyderT225_G27_RecentTradesDialog.py | Focused regressions for the dedicated recent-trades dialog. | 213 |
| Spyder/SpyderT_Testing/SpyderT226_G28_AccountPanelPresenter.py | Focused regressions for account-panel presentation extraction. | 132 |
| Spyder/SpyderT_Testing/SpyderT227_G33_AccountSnapshotSelector.py | Focused regressions for G33 account snapshot selection. | 47 |
| Spyder/SpyderT_Testing/SpyderT228_G34_AccountCapitalMath.py | Focused regressions for G34 account capital math extraction. | 178 |
| Spyder/SpyderT_Testing/SpyderT229_G35_PaperSummaryPresenter.py | Focused regressions for G35 paper summary presentation extraction. | 123 |
| Spyder/SpyderT_Testing/SpyderT22_FSeriesIntegrationValidator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,076 |
| Spyder/SpyderT_Testing/SpyderT230_G36_StripMetricsPresenter.py | Focused regressions for G36 IV and Greek strip presentation extraction. | 127 |
| Spyder/SpyderT_Testing/SpyderT231_G37_GreekBarPresenter.py | Focused regressions for G37 Greek bar risk mapping extraction. | 90 |
| Spyder/SpyderT_Testing/SpyderT232_G38_LegacySpreadsTablePresenter.py | Focused regressions for G38 legacy spreads table presentation extraction. | 124 |
| Spyder/SpyderT_Testing/SpyderT233_G39_PaperPositionsTreePresenter.py | Focused tests for paper positions tree presentation helpers. | 178 |
| Spyder/SpyderT_Testing/SpyderT234_G39_PaperSpreadTreePresenter.py | Focused tests for paper spread tree presentation helpers. | 154 |
| Spyder/SpyderT_Testing/SpyderT235_G40_ToolbarIndexPresenter.py | Focused tests for toolbar index presentation helpers. | 123 |
| Spyder/SpyderT_Testing/SpyderT236_G41_RegimeLiquidityPresenter.py | Focused tests for regime/liquidity presentation helpers. | 128 |
| Spyder/SpyderT_Testing/SpyderT237_G43_CustomMetricDialogPresenter.py | Focused tests for G43 custom metric detail dialog presenters. | 330 |
| Spyder/SpyderT_Testing/SpyderT238_G44_RecentDecisionFlowPresenter.py | Focused tests for G44 recent decision-flow presenter helpers. | 60 |
| Spyder/SpyderT_Testing/SpyderT239_G45_ExecutionHealthPresenter.py | Focused tests for G45 execution-health presenter helpers. | 56 |
| Spyder/SpyderT_Testing/SpyderT23_SharpeRatioEstimate.py | SPYDER - Autonomous Options Trading System v1.0 | 192 |
| Spyder/SpyderT_Testing/SpyderT240_G46_ReadinessStatusPresenter.py | Focused tests for G46 readiness status presenter helpers. | 100 |
| Spyder/SpyderT_Testing/SpyderT241_G05_ReadinessStatusDisplay.py | Focused tests for G05 readiness status display delegation. | 93 |
| Spyder/SpyderT_Testing/SpyderT242_G47_EventClockDisplayPresenter.py | Focused tests for G47 event-clock display presenter helpers. | 55 |
| Spyder/SpyderT_Testing/SpyderT243_G05_EventClockDisplay.py | Focused tests for G05 event-clock display delegation. | 90 |
| Spyder/SpyderT_Testing/SpyderT244_G48_TradingArmingPresenter.py | Focused tests for G48 REAL/PAPER arming presenter helpers. | 41 |
| Spyder/SpyderT_Testing/SpyderT245_G05_ModeButtons.py | Focused tests for G05 mode-button presentation delegation. | 84 |
| Spyder/SpyderT_Testing/SpyderT246_G49_TradingWindowBadgePresenter.py | Focused tests for G49 compact trading-window badge presenter. | 31 |
| Spyder/SpyderT_Testing/SpyderT247_G05_TradingWindowCompactLabel.py | Focused tests for G05 compact trading-window badge delegation. | 54 |
| Spyder/SpyderT_Testing/SpyderT248_G50_EntryBlockCompactPresenter.py | Focused tests for G50 entry-block presenter helpers. | 62 |
| Spyder/SpyderT_Testing/SpyderT249_G05_EntryBlockCompactLabel.py | Focused tests for G05 compact entry-block label delegation. | 60 |
| Spyder/SpyderT_Testing/SpyderT24_RenaissanceIntegrationTest.py | SPYDER - Automated SPY Options Trading System | 794 |
| Spyder/SpyderT_Testing/SpyderT250_G51_ModeTitlePresenter.py | Focused tests for G51 mode title presenter helpers. | 21 |
| Spyder/SpyderT_Testing/SpyderT251_G05_ModeTitles.py | Focused tests for G05 mode title delegation. | 102 |
| Spyder/SpyderT_Testing/SpyderT252_G52_RegimePillBarPresenter.py | Focused tests for the G52 regime pill bar presenter. | 74 |
| Spyder/SpyderT_Testing/SpyderT253_G05_RiskAlertEvent.py | Focused tests for G05 risk alert event handling. | 134 |
| Spyder/SpyderT_Testing/SpyderT254_G53_GoNoGoPresenter.py | Focused tests for G53 pre-open Go/No-Go presenter. | 52 |
| Spyder/SpyderT_Testing/SpyderT255_G54_ReadinessResultPresenter.py | Focused tests for G54 readiness result presenter. | 41 |
| Spyder/SpyderT_Testing/SpyderT256_G05_ReadinessResultApplication.py | Focused tests for G05 readiness result application. | 51 |
| Spyder/SpyderT_Testing/SpyderT257_G55_ReadinessReportPresenter.py | Focused tests for G55 readiness report export helpers. | 43 |
| Spyder/SpyderT_Testing/SpyderT258_G05_ReadinessReportExport.py | Focused tests for G05 readiness report and audit export helpers. | 140 |
| Spyder/SpyderT_Testing/SpyderT259_G56_ReadinessStartGatePresenter.py | Focused tests for G56 readiness start-gate presenter. | 45 |
| Spyder/SpyderT_Testing/SpyderT260_G57_StartTradingPrecheckPresenter.py | Focused tests for G57 start-trading precheck presenter. | 48 |
| Spyder/SpyderT_Testing/SpyderT261_G58_StartTradingLiveGuardPresenter.py | Focused tests for G58 live start-trading guard presenter. | 38 |
| Spyder/SpyderT_Testing/SpyderT262_G59_StartTradingFailurePresenter.py | Focused tests for G59 start-trading failure presenter. | 16 |
| Spyder/SpyderT_Testing/SpyderT263_G60_ReadinessStartBlockPresenter.py | Focused tests for G60 readiness start-block presenter. | 34 |
| Spyder/SpyderT_Testing/SpyderT264_G61_ReadinessAsyncPresenter.py | Focused tests for G61 async readiness presenter. | 30 |
| Spyder/SpyderT_Testing/SpyderT265_G62_ReadinessWorkerCleanupHelper.py | Focused tests for G62 readiness worker cleanup helper. | 34 |
| Spyder/SpyderT_Testing/SpyderT266_G63_ReadinessSnapshotHelper.py | Focused tests for G63 readiness snapshot helpers. | 58 |
| Spyder/SpyderT_Testing/SpyderT267_G64_ReadinessConnectionRefreshHelper.py | Focused tests for G64 readiness connection refresh helper. | 48 |
| Spyder/SpyderT_Testing/SpyderT268_G65_ReadinessEventClockSnapshotHelper.py | Focused tests for G65 readiness event-clock snapshot helper. | 24 |
| Spyder/SpyderT_Testing/SpyderT269_G66_ReadinessStartupStateHelper.py | Focused tests for G66 readiness startup-state helper. | 25 |
| Spyder/SpyderT_Testing/SpyderT270_G67_ReadinessDecisionHelper.py | Focused tests for G67 readiness decision helper. | 112 |
| Spyder/SpyderT_Testing/SpyderT271_G68_ReadinessBypassAuditHelper.py | Focused tests for G68 readiness bypass-audit helper. | 38 |
| Spyder/SpyderT_Testing/SpyderT272_G69_LiveDataStatusHelper.py | Focused tests for G69 live-data status helper. | 16 |
| Spyder/SpyderT_Testing/SpyderT273_G70_ReadinessCacheDecisionHelper.py | Focused tests for G70 readiness cache-decision helper. | 38 |
| Spyder/SpyderT_Testing/SpyderT274_G71_ReadinessGateDecisionHelper.py | Focused tests for G71 readiness gate-decision helper. | 39 |
| Spyder/SpyderT_Testing/SpyderT275_G72_PaperSessionQueueHelper.py | Focused tests for G72 paper-session queue helper. | 60 |
| Spyder/SpyderT_Testing/SpyderT276_G73_PaperSessionFinalizeHelper.py | Focused tests for G73 delayed paper-session finalization helper. | 39 |
| Spyder/SpyderT_Testing/SpyderT277_G74_SessionSupervisorStartHelper.py | Focused tests for G74 SessionSupervisor start helper. | 46 |
| Spyder/SpyderT_Testing/SpyderT278_G75_SessionSupervisorStartAttemptHelper.py | Focused tests for G75 SessionSupervisor start-attempt helper. | 42 |
| Spyder/SpyderT_Testing/SpyderT279_G76_SessionSupervisorAdoptionHelper.py | Focused tests for G76 SessionSupervisor adoption helper. | 48 |
| Spyder/SpyderT_Testing/SpyderT280_G77_LoadingTransitionCompletionHelper.py | Focused tests for G77 loading-transition completion helper. | 54 |
| Spyder/SpyderT_Testing/SpyderT281_G78_LoadingTransitionBeginHelper.py | Focused tests for G78 loading transition begin helper. | 51 |
| Spyder/SpyderT_Testing/SpyderT282_G79_StartButtonReadyStateHelper.py | Focused tests for G79 start-button ready-state helper. | 66 |
| Spyder/SpyderT_Testing/SpyderT283_G80_StartButtonActiveStateHelper.py | Focused tests for G80 start-button active-state helper. | 66 |
| Spyder/SpyderT_Testing/SpyderT284_G17_PaperPositionResolver.py | Focused tests for G17 paper position resolver selection and grouping policy. | 245 |
| Spyder/SpyderT_Testing/SpyderT285_G81_MarketWorkerSlotInvokeHelper.py | Focused tests for G81 market-worker slot invoke helper. | 54 |
| Spyder/SpyderT_Testing/SpyderT286_G82_QThreadShutdownHelper.py | Focused tests for G82 Qt thread shutdown helper. | 60 |
| Spyder/SpyderT_Testing/SpyderT287_G83_MetricsOrchestratorShutdownHelper.py | Focused tests for G83 metrics orchestrator shutdown helper. | 54 |
| Spyder/SpyderT_Testing/SpyderT288_G84_MarketWorkerSignalEmitHelper.py | Focused tests for G84 market-worker signal emit helper. | 36 |
| Spyder/SpyderT_Testing/SpyderT289_G85_MarketWorkerSignalDisconnectHelper.py | Focused tests for G85 market-worker signal disconnect helper. | 42 |
| Spyder/SpyderT_Testing/SpyderT290_G86_ShutdownTimerStopHelper.py | Focused tests for G86 shutdown timer stop helper. | 50 |
| Spyder/SpyderT_Testing/SpyderT291_G87_PostWorkerShutdownTimerHelper.py | Focused tests for G87 late shutdown timer stop helper. | 39 |
| Spyder/SpyderT_Testing/SpyderT292_G88_MarketWorkerShutdownHelper.py | Focused tests for G88 market-worker shutdown helper. | 33 |
| Spyder/SpyderT_Testing/SpyderT293_G89_ShutdownMessageHelper.py | Focused tests for G89 dashboard shutdown message helper. | 21 |
| Spyder/SpyderT_Testing/SpyderT294_G90_CloseEventShutdownSequenceHelper.py | Focused tests for G90 closeEvent shutdown sequence helper. | 37 |
| Spyder/SpyderT_Testing/SpyderT295_G91_StartupReadinessLogHelper.py | Focused tests for G91 startup-readiness log helper. | 88 |
| Spyder/SpyderT_Testing/SpyderT296_G92_StartupReadinessBannerHelper.py | Focused tests for G92 startup-readiness banner helper. | 81 |
| Spyder/SpyderT_Testing/SpyderT297_G93_StartupReadinessStateHelper.py | Focused tests for G93 startup-readiness state helper. | 75 |
| Spyder/SpyderT_Testing/SpyderT298_G94_StartupReadinessRefreshHelper.py | Focused tests for G94 startup-readiness refresh helper. | 26 |
| Spyder/SpyderT_Testing/SpyderT299_G95_DJIProxyMultiplierHelper.py | Focused tests for G95 DJI proxy multiplier normalization helper. | 22 |
| Spyder/SpyderT_Testing/SpyderT300_G96_RiskAlertDispatchHelper.py | Focused tests for G96 risk alert dispatch helper. | 55 |
| Spyder/SpyderT_Testing/SpyderT301_G05_PendingOrdersGate.py | Focused tests for G05 pending-orders gate behavior. | 99 |
| Spyder/SpyderT_Testing/SpyderT302_G97_PendingOrdersGateHelper.py | Focused tests for G97 pending-orders gate helper. | 47 |
| Spyder/SpyderT_Testing/SpyderT303_G98_ExecutionTelemetryEventHelper.py | Focused tests for G98 execution-telemetry event helper. | 48 |
| Spyder/SpyderT_Testing/SpyderT304_G05_PositionUpdatedEvent.py | Focused tests for G05 POSITION_UPDATED event wiring. | 56 |
| Spyder/SpyderT_Testing/SpyderT305_G100_PositionUpdatedEventHelper.py | Focused tests for G100 POSITION_UPDATED event helper. | 24 |
| Spyder/SpyderT_Testing/SpyderT306_G05_RecentDecisionFlowFetch.py | Focused tests for G05 recent decision-flow fetch wiring. | 72 |
| Spyder/SpyderT_Testing/SpyderT307_G101_RecentDecisionFlowFetchHelper.py | Focused tests for G101 recent decision-flow fetch helper. | 34 |
| Spyder/SpyderT_Testing/SpyderT308_G05_MetricsOrchestratorStart.py | Focused tests for G05 metrics orchestrator startup wiring. | 73 |
| Spyder/SpyderT_Testing/SpyderT309_G102_MetricsOrchestratorStartHelper.py | Focused tests for G102 metrics orchestrator start helper. | 25 |
| Spyder/SpyderT_Testing/SpyderT310_G05_LiveToPaperSwitch.py | Focused tests for G05 LIVE-to-PAPER switch dialog wiring. | 106 |
| Spyder/SpyderT_Testing/SpyderT311_G103_LiveToPaperSwitchHelper.py | Focused tests for G103 LIVE-to-PAPER switch helper. | 31 |
| Spyder/SpyderT_Testing/SpyderT312_G05_MetricsSnapshotHydration.py | Focused tests for G05 metrics snapshot hydration wiring. | 54 |
| Spyder/SpyderT_Testing/SpyderT313_G104_MetricsSnapshotProbeHelper.py | Focused tests for G104 metrics snapshot probe helper. | 60 |
| Spyder/SpyderT_Testing/SpyderT314_G05_PaperToLiveSwitch.py | Focused tests for G05 PAPER-to-LIVE switch dialog wiring. | 142 |
| Spyder/SpyderT_Testing/SpyderT315_G105_PaperToLiveSwitchHelper.py | Focused tests for G105 PAPER-to-LIVE switch helper. | 27 |
| Spyder/SpyderT_Testing/SpyderT316_G05_CustomMetricWidgetFanout.py | Focused tests for G05 custom-metric widget fan-out wiring. | 100 |
| Spyder/SpyderT_Testing/SpyderT317_G106_CustomMetricWidgetUpdateHelper.py | Focused tests for G106 custom-metric widget update helper. | 68 |
| Spyder/SpyderT_Testing/SpyderT318_G05_CustomMetricSignalPanelSync.py | Focused tests for G05 signal-panel sync wiring from custom metrics. | 157 |
| Spyder/SpyderT_Testing/SpyderT319_G107_CustomMetricSignalPanelSyncHelper.py | Focused tests for G107 custom-metric signal-panel sync helper. | 86 |
| Spyder/SpyderT_Testing/SpyderT320_G05_CustomMetricBreadthDialogSync.py | Focused tests for G05 Market Internals dialog sync from custom metrics. | 71 |
| Spyder/SpyderT_Testing/SpyderT321_G108_CustomMetricBreadthDialogSyncHelper.py | Focused tests for G108 custom-metric breadth dialog sync helper. | 69 |
| Spyder/SpyderT_Testing/SpyderT322_G05_RegimePillStatePlan.py | Focused tests for G05 regime-pill state plan wiring. | 128 |
| Spyder/SpyderT_Testing/SpyderT323_G109_RegimePillStateHelper.py | Focused tests for G109 regime-pill state helper. | 123 |
| Spyder/SpyderT_Testing/SpyderT324_G05_RegimePillStatusPlan.py | Focused tests for G05 regime-pill status plan wiring. | 128 |
| Spyder/SpyderT_Testing/SpyderT325_G110_RegimePillStatusHelper.py | Focused tests for G110 regime-pill status helper. | 36 |
| Spyder/SpyderT_Testing/SpyderT326_G05_RegimeDispatchAnnouncement.py | Focused tests for G05 regime dispatch announcement wiring. | 213 |
| Spyder/SpyderT_Testing/SpyderT327_G111_RegimeDispatchAnnouncementHelper.py | Focused tests for G111 regime dispatch announcement helper. | 39 |
| Spyder/SpyderT_Testing/SpyderT330_G05_CloseStrategyConfirm.py | Focused tests for G05 close-strategy confirmation dialog wiring. | 161 |
| Spyder/SpyderT_Testing/SpyderT331_G112_CloseStrategyConfirmHelper.py | Focused tests for G112 close-strategy confirmation helper. | 33 |
| Spyder/SpyderT_Testing/SpyderT332_G05_CloseStrategySuccess.py | Focused tests for G05 close-strategy success-path wiring. | 58 |
| Spyder/SpyderT_Testing/SpyderT333_G113_CloseStrategySuccessHelper.py | Focused tests for G113 close-strategy success helper. | 23 |
| Spyder/SpyderT_Testing/SpyderT334_G05_CloseStrategyFailure.py | Focused tests for G05 close-strategy failure-path wiring. | 55 |
| Spyder/SpyderT_Testing/SpyderT335_G114_CloseStrategyFailureHelper.py | Focused tests for G114 close-strategy failure helper. | 38 |
| Spyder/SpyderT_Testing/SpyderT336_G05_EventSubscriptionPlan.py | Focused tests for G05 event subscription plan wiring. | 70 |
| Spyder/SpyderT_Testing/SpyderT337_G115_EventSubscriptionPlanHelper.py | Focused tests for G115 event subscription plan helper. | 53 |
| Spyder/SpyderT_Testing/SpyderT338_G05_EventClockRiskEvent.py | Focused tests for G05 event-clock risk-event wiring. | 78 |
| Spyder/SpyderT_Testing/SpyderT339_G116_EventClockRiskEventHelper.py | Focused tests for G116 event-clock risk-event helper. | 77 |
| Spyder/SpyderT_Testing/SpyderT340_G05_EventClockOverride.py | Focused tests for G05 manual event-clock override wiring. | 96 |
| Spyder/SpyderT_Testing/SpyderT341_G117_EventClockOverrideHelper.py | Focused tests for G117 manual event-clock override helper. | 28 |
| Spyder/SpyderT_Testing/SpyderT342_G05_PaperRiskManagerLimits.py | Focused tests for G05 paper risk-limit mapping integration. | 115 |
| Spyder/SpyderT_Testing/SpyderT343_G118_PaperRiskLimitMappingHelper.py | Focused tests for G118 paper risk-limit mapping helper. | 41 |
| Spyder/SpyderT_Testing/SpyderT344_G05_RingLogBuffering.py | Focused tests for G05 ring-log buffering and refresh routing. | 110 |
| Spyder/SpyderT_Testing/SpyderT345_G119_RingLogBufferHelper.py | Focused tests for G119 ring-log helper logic. | 59 |
| Spyder/SpyderT_Testing/SpyderT348_G05_AfterHoursSystemLogSuppression.py | Focused tests for G05 system-log suppression wrapper behavior. | 91 |
| Spyder/SpyderT_Testing/SpyderT349_G120_SystemLogSuppressionHelper.py | Focused tests for G120 system-log suppression helper. | 39 |
| Spyder/SpyderT_Testing/SpyderT350_G05_AutomationLogRouting.py | Focused tests for G05 automation-log routing. | 78 |
| Spyder/SpyderT_Testing/SpyderT350_S11_TradingViewInternals.py | Focused tests for the S11 TradingView last-price selector path. | 122 |
| Spyder/SpyderT_Testing/SpyderT351_G121_AutomationLogRoutingHelper.py | Focused tests for G121 automation-log routing helper. | 42 |
| Spyder/SpyderT_Testing/SpyderT352_G05_SystemLogVerbosity.py | Focused tests for G05 system-log verbosity routing. | 93 |
| Spyder/SpyderT_Testing/SpyderT353_G122_SystemLogVerbosityHelper.py | Focused tests for G122 system-log verbosity helper. | 36 |
| Spyder/SpyderT_Testing/SpyderT354_G05_VetoToggleButtonState.py | Focused tests for G05 veto toggle button presentation routing. | 62 |
| Spyder/SpyderT_Testing/SpyderT355_G123_VetoToggleButtonHelper.py | Focused tests for G123 veto toggle button helper. | 24 |
| Spyder/SpyderT_Testing/SpyderT356_G05_VetoToggleControls.py | Focused tests for G05 veto toggle outcome routing. | 64 |
| Spyder/SpyderT_Testing/SpyderT357_G124_VetoToggleResultHelper.py | Focused tests for G124 veto toggle result helper. | 33 |
| Spyder/SpyderT_Testing/SpyderT358_G05_VetoControlsStateLoad.py | Focused tests for G05 veto controls state loading. | 87 |
| Spyder/SpyderT_Testing/SpyderT359_G125_VetoControlsStateHelper.py | Focused tests for G125 veto controls state helper. | 48 |
| Spyder/SpyderT_Testing/SpyderT360_G05_VetoControlsStatePersist.py | Focused tests for G05 veto controls persistence. | 79 |
| Spyder/SpyderT_Testing/SpyderT361_G126_VetoControlsPersistPlanHelper.py | Focused tests for G126 veto controls persistence planning. | 54 |
| Spyder/SpyderT_Testing/SpyderT362_G05_StartupReadinessStateEnvelope.py | Focused tests for G05 startup-readiness state envelope shaping. | 157 |
| Spyder/SpyderT_Testing/SpyderT363_G127_StartupReadinessStateEnvelopeHelper.py | Focused tests for G127 startup-readiness state envelope helper. | 46 |
| Spyder/SpyderT_Testing/SpyderT364_G05_DashboardSnapshotPayload.py | Focused tests for G05 dashboard snapshot payload shaping. | 104 |
| Spyder/SpyderT_Testing/SpyderT365_G128_DashboardSnapshotPayloadHelper.py | Focused tests for G128 dashboard snapshot payload helper. | 52 |
| Spyder/SpyderT_Testing/SpyderT366_G05_MetricsPayloadMerge.py | Focused tests for the G05 metrics payload merge wrapper. | 25 |
| Spyder/SpyderT_Testing/SpyderT367_G129_MetricsPayloadMergeHelper.py | Focused tests for the G129 metrics payload merge helper. | 42 |
| Spyder/SpyderT_Testing/SpyderT368_G05_CachedMetricsFallback.py | Focused tests for G05 cached metrics fallback payload wiring. | 141 |
| Spyder/SpyderT_Testing/SpyderT369_G130_CachedMetricsFallbackHelper.py | Focused tests for G130 cached metrics fallback helper. | 88 |
| Spyder/SpyderT_Testing/SpyderT370_G05_CachedMarketSnapshotMerge.py | Focused tests for G05 cached market snapshot merge wiring. | 62 |
| Spyder/SpyderT_Testing/SpyderT371_G131_CachedMarketSnapshotMergeHelper.py | Focused tests for G131 cached market snapshot merge helper. | 44 |
| Spyder/SpyderT_Testing/SpyderT372_G05_CachedChartCandles.py | Focused tests for G05 cached chart candle loading wiring. | 63 |
| Spyder/SpyderT_Testing/SpyderT372_G18_EODSnapshotPersistence.py | Regression tests for G18 EOD snapshot persistence behavior. | 152 |
| Spyder/SpyderT_Testing/SpyderT373_G132_CachedChartCandlesHelper.py | Focused tests for G132 cached chart candle selection helper. | 38 |
| Spyder/SpyderT_Testing/SpyderT374_G05_CachedChartBarSeries.py | Focused tests for G05 cached chart bar series wiring. | 95 |
| Spyder/SpyderT_Testing/SpyderT375_G133_CachedChartBarSeriesHelper.py | Focused tests for G133 cached chart bar series helper. | 91 |
| Spyder/SpyderT_Testing/SpyderT376_D31_PaperFailClosedGuard.py | Regression for D31 _paper_fail_closed_selector_reason overly broad guard. | 107 |
| Spyder/SpyderT_Testing/SpyderT377_R04_PaperFillGaps.py | Regression for R04 paper-fill gaps: H05 persistence, symbol in event, position tracker. | 306 |
| Spyder/SpyderT_Testing/SpyderT378_G05_PaperCleanSlateStartupGuard.py | Focused tests for G05 paper clean-slate startup guard behavior. | 106 |
| Spyder/SpyderT_Testing/SpyderT378_R12_PaperStartAuthorization.py | Focused regressions for explicit paper-start authorization in R12. | 63 |
| Spyder/SpyderT_Testing/SpyderT379_C10_VIXAnalyzerVXVYahooAlias.py | Regression for C10 VXV Yahoo symbol drift. | 48 |
| Spyder/SpyderT_Testing/SpyderT380_G109_VixFallbackBull.py | Regression tests for G109 VIX-fallback BULL detection (§10.36 P1 fix). | 137 |
| Spyder/SpyderT_Testing/SpyderT381_L09_ColdVixEma50.py | Regression tests for L09 cold-start vix_ema50 guard fix (§10.36 P2 fix). | 135 |
| Spyder/SpyderT_Testing/SpyderT382_G110_GateStartupFallback.py | Regression tests for G110 gate/stance startup fallback (§10.36 P3 fix). | 148 |
| Spyder/SpyderT_Testing/SpyderT383_G12_SignalInfoDialogMetadata.py | Focused regressions for shared SignalInfoDialog metadata. | 66 |
| Spyder/SpyderT_Testing/SpyderT384_G17_MarketInternalsMetadata.py | Focused regressions for shared Market Internals panel copy. | 54 |
| Spyder/SpyderT_Testing/SpyderT385_G11_SkewDialogClose.py | Focused regressions for SKEW dialog close responsiveness. | 61 |
| Spyder/SpyderT_Testing/SpyderT386_D31_LiveOptionsSnapshotAgeGate.py | Focused regressions for D31 live options snapshot freshness gating. | 131 |
| Spyder/SpyderT_Testing/SpyderT387_G17_MarketInternalsStaleBreadth.py | Focused regressions for G17 stale breadth rendering. | 51 |
| Spyder/SpyderT_Testing/SpyderT388_D14_CalendarSpreadSerialization.py | Focused regressions for D14 calendar-spread signal serialization and lifecycle. | 131 |
| Spyder/SpyderT_Testing/SpyderT389_D31_PaperCalendarSpreadRouting.py | Focused regressions for D31 paper calendar-spread routing. | 203 |
| Spyder/SpyderT_Testing/SpyderT390_D23_BrokenWingButterfly.py | Module for d23 brokenwingbutterfly functionality. | 144 |
| Spyder/SpyderT_Testing/SpyderT390_HolidayMarketHoursRegression.py | Regression tests for holiday-aware market-hours helpers across GUI/runtime layers. | 69 |
| Spyder/SpyderT_Testing/SpyderT391_D31_PaperBrokenWingButterflyRouting.py | Focused regressions for D31 paper Broken Wing Butterfly routing. | 157 |
| Spyder/SpyderT_Testing/SpyderT391_F01_TechnicalIndicatorsConfig.py | Focused regressions for F01 config-manager compatibility. | 52 |
| Spyder/SpyderT_Testing/SpyderT392_D24_Butterfly.py | Module for d24 butterfly functionality. | 216 |
| Spyder/SpyderT_Testing/SpyderT393_D31_PaperButterflyRouting.py | Focused regressions for D31 paper Butterfly routing. | 239 |
| Spyder/SpyderT_Testing/SpyderT393_D37_BullishStrangle.py | Focused unit tests for the D37 Bullish Strangle strategy. | 142 |
| Spyder/SpyderT_Testing/SpyderT394_S05_GEXDEXCalculator.py | Module for s05 gexdexcalculator functionality. | 116 |
| Spyder/SpyderT_Testing/SpyderT395_D10_IronButterfly.py | Module for d10 ironbutterfly functionality. | 113 |
| Spyder/SpyderT_Testing/SpyderT396_D31_PaperIronButterflyRouting.py | Focused regressions for D31 paper Iron Butterfly routing. | 178 |
| Spyder/SpyderT_Testing/SpyderT397_D31_PaperBullishStrangleRouting.py | Focused regressions for D31 paper Bullish Strangle routing. | 155 |
| Spyder/SpyderT_Testing/SpyderT397_D31_RegimePolicyButterflyAllowlist.py | Focused regressions for D31 butterfly-family regime allowlists. | 51 |
| Spyder/SpyderT_Testing/SpyderT398_G20_PositionsTableWidths.py | Focused regressions for dashboard positions-table money-column widths. | 42 |
| Spyder/SpyderT_Testing/SpyderT399_R08_AfterHoursSpreadMtm.py | Focused regressions for after-hours spread MTM freezing in R08. | 101 |
| Spyder/SpyderT_Testing/SpyderT400_D31_PinRiskWindowCoverage.py | Focused regressions for D31 post-close pin-risk coverage counting. | 124 |
| Spyder/SpyderT_Testing/SpyderT401_D31_PaperJadeLizardZeroRouting.py | Focused regressions for D31 paper Jade Lizard Zero routing. | 127 |
| Spyder/SpyderT_Testing/SpyderT402_R08_ManualCloseEmbargoEvent.py | Focused regressions for R08 manual-close embargo event emission. | 54 |
| Spyder/SpyderT_Testing/SpyderT403_D39_PutCreditSpread7.py | Focused unit tests for the D39 Put Credit Spread 7 strategy. | 442 |
| Spyder/SpyderT_Testing/SpyderT404_D31_PaperPutCreditSpread7Routing.py | Focused regressions for D31 paper Put Credit Spread 7 routing. | 130 |
| Spyder/SpyderT_Testing/SpyderT40_TradierClient_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 540 |
| Spyder/SpyderT_Testing/SpyderT42_Integration_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 269 |
| Spyder/SpyderT_Testing/SpyderT43_OrderManager_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 805 |
| Spyder/SpyderT_Testing/SpyderT45_ResilienceInfrastructureTest.py | SPYDER - Autonomous Options Trading System v1.0 | 585 |
| Spyder/SpyderT_Testing/SpyderT46_RiskManager_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 564 |
| Spyder/SpyderT_Testing/SpyderT47_StrategyUnit_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 468 |
| Spyder/SpyderT_Testing/SpyderT48_PipelineE2E_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 468 |
| Spyder/SpyderT_Testing/SpyderT50_TradierOrderTests.py | SPYDER - Autonomous Options Trading System v1.0 | 823 |
| Spyder/SpyderT_Testing/SpyderT51_RiskManagerLimits_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 706 |
| Spyder/SpyderT_Testing/SpyderT52_SentimentNewsSourceStub_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 624 |
| Spyder/SpyderT_Testing/SpyderT54_StartupConfigValidation_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 1,008 |
| Spyder/SpyderT_Testing/SpyderT55_PaperTradingHarness_Test.py | SPYDER - Autonomous Options Trading System v1.0 | 749 |
| Spyder/SpyderT_Testing/SpyderT56_StrategyTests.py | SPYDER - Autonomous Options Trading System v1.0 | 894 |
| Spyder/SpyderT_Testing/SpyderT57_OptionsAnalyticsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 574 |
| Spyder/SpyderT_Testing/SpyderT58_RiskManagementTests.py | SPYDER - Autonomous Options Trading System v1.0 | 704 |
| Spyder/SpyderT_Testing/SpyderT59_UtilityTests.py | SPYDER - Autonomous Options Trading System v1.0 | 820 |
| Spyder/SpyderT_Testing/SpyderT60_FSeriesAnalysisTests.py | SPYDER - Autonomous Options Trading System v1.0 | 755 |
| Spyder/SpyderT_Testing/SpyderT61_ResilienceTests.py | SPYDER - Autonomous Options Trading System v1.0 | 800 |
| Spyder/SpyderT_Testing/SpyderT62_MathValidatorTests.py | SPYDER - Autonomous Options Trading System v1.0 | 993 |
| Spyder/SpyderT_Testing/SpyderT63_CalendarFeatureFlagTests.py | SPYDER - Autonomous Options Trading System v1.0 | 957 |
| Spyder/SpyderT_Testing/SpyderT64_OptionStrategyPerformanceTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,195 |
| Spyder/SpyderT_Testing/SpyderT65_ErrorHandlerNetworkTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,243 |
| Spyder/SpyderT_Testing/SpyderT66_MathTechnicalIndicatorTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,061 |
| Spyder/SpyderT_Testing/SpyderT67_RateLimiterCircuitBreakerTests.py | SPYDER - Autonomous Options Trading System v1.0 | 893 |
| Spyder/SpyderT_Testing/SpyderT68_EncryptionValidatorTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,035 |
| Spyder/SpyderT_Testing/SpyderT69_DateTimeUtilsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 707 |
| Spyder/SpyderT_Testing/SpyderT70_DataTypesETTimeTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,005 |
| Spyder/SpyderT_Testing/SpyderT71_PerfMetricsFeatureFlagsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,011 |
| Spyder/SpyderT_Testing/SpyderT72_TechnicalAnalysisTests.py | SPYDER - Autonomous Options Trading System v1.0 | 964 |
| Spyder/SpyderT_Testing/SpyderT73_MathValidatorsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,322 |
| Spyder/SpyderT_Testing/SpyderT74_TechIndicatorsOptionStrategiesTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,132 |
| Spyder/SpyderT_Testing/SpyderT75_DependencyAnalyzerInteractionMatrixTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,055 |
| Spyder/SpyderT_Testing/SpyderT76_MemoryMonitorSystemOptimizerTests.py | SPYDER - Autonomous Options Trading System v1.0 | 977 |
| Spyder/SpyderT_Testing/SpyderT77_CalendarInstitutionalLibrariesTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,160 |
| Spyder/SpyderT_Testing/SpyderT78_ErrorHandlerTechAnalysisNetworkGapTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,268 |
| Spyder/SpyderT_Testing/SpyderT79_StyleManagerMemMonSysOptGapTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,355 |
| Spyder/SpyderT_Testing/SpyderT80_U12U22U13U15U11GapTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,051 |
| Spyder/SpyderT_Testing/SpyderT81_ValidatorsRateLimiterCircuitBreakerDataTypesTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,299 |
| Spyder/SpyderT_Testing/SpyderT82_MathUtilsOptionStrategiesTests.py | SPYDER - Autonomous Options Trading System v1.0 | 884 |
| Spyder/SpyderT_Testing/SpyderT83_ErrorHandlerNetworkUtilsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 607 |
| Spyder/SpyderT_Testing/SpyderT84_FeatureFlagsPerformanceMetricsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 843 |
| Spyder/SpyderT_Testing/SpyderT85_TradingCalendarDependencyAnalyzerTests.py | SPYDER - Autonomous Options Trading System v1.0 | 840 |
| Spyder/SpyderT_Testing/SpyderT86_DateTimeUtilsInteractionMatrixTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,507 |
| Spyder/SpyderT_Testing/SpyderT87_ETTimeDisplayMemoryMonitorTests.py | SPYDER - Autonomous Options Trading System v1.0 | 951 |
| Spyder/SpyderT_Testing/SpyderT88_TechnicalAnalysisSystemOptimizerTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,396 |
| Spyder/SpyderT_Testing/SpyderT89_MathUtilsValidatorsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,561 |
| Spyder/SpyderT_Testing/SpyderT90_TechnicalIndicatorsPerformanceMetricsTests.py | SPYDER - Autonomous Options Trading System v1.0 | 1,200 |
| Spyder/SpyderT_Testing/SpyderT91_RateLimiterCircuitBreakerTests.py | SPYDER - Autonomous Options Trading System v1.0 | 765 |
| Spyder/SpyderT_Testing/SpyderT92_EncryptionOptionStrategiesTests.py | SPYDER - Autonomous Options Trading System v1.0 | 794 |
| Spyder/SpyderT_Testing/SpyderT93_U11FeatureFlags_U09DataTypes.py | SPYDER - Autonomous Options Trading System v1.0 | 1,583 |
| Spyder/SpyderT_Testing/SpyderT94_U02ErrorHandler_U05NetworkUtils.py | SPYDER - Autonomous Options Trading System v1.0 | 1,397 |
| Spyder/SpyderT_Testing/SpyderT95_U03DateTimeUtils_U07Constants_U22ETTimeDisplay.py | T95 — SpyderU03 DateTimeUtils \| SpyderU07 Constants \| SpyderU22 ETTimeDisplay | 1,011 |
| Spyder/SpyderT_Testing/SpyderT96_U12AgentIntegration_U23MemoryMonitor_U24StyleManager.py | T96 — SpyderU12 AgentIntegration \| SpyderU23 MemoryMonitor \| SpyderU24 StyleManager | 849 |
| Spyder/SpyderT_Testing/SpyderT97_U04Encryption_U40RateLimiter_U41CircuitBreaker.py | SPYDER - Autonomous Options Trading System v1.0 | 1,006 |
| Spyder/SpyderT_Testing/SpyderT98_U06MathUtils_U08Validators.py | SPYDER - Autonomous Options Trading System v1.0 | 880 |
| Spyder/SpyderT_Testing/SpyderT99_SystemDiagnostic.py | SPYDER - Autonomous Options Trading System v1.0 | 712 |
| Spyder/SpyderT_Testing/SpyderT99_U16TechnicalAnalysis_U27SystemOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 747 |
| Spyder/SpyderT_Testing/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 367 |
| Spyder/SpyderT_Testing/conftest.py | SPYDER - Autonomous Options Trading System v1.0 | 439 |
| Spyder/SpyderT_Testing/test_no_legacy_spyderu_imports.py | Guardrail test to prevent legacy SpyderU import paths in active code. | 56 |
| Spyder/SpyderT_Testing/test_r12_flatten_request_guard.py | Regression tests for R12 FLATTEN_REQUEST broker-cutoff guard wiring. | 468 |
| Spyder/SpyderT_Testing/test_r12_paper_condor_runtime_smoke.py | Focused runtime smoke for paper iron-condor persistence and rendering. | 245 |
| **Subtotal** | **410 modules** | **142,448** |

### SpyderU_Utilities (Series U)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderU_Utilities/SpyderU01_Logger.py | SPYDER - Autonomous Options Trading System v1.0 | 128 |
| Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py | SPYDER - Autonomous Options Trading System v1.0 | 915 |
| Spyder/SpyderU_Utilities/SpyderU03_DateTimeUtils.py | SPYDER - Autonomous Options Trading System v1.0 | 1,947 |
| Spyder/SpyderU_Utilities/SpyderU04_Encryption.py | SPYDER - Autonomous Options Trading System v1.0 | 230 |
| Spyder/SpyderU_Utilities/SpyderU05_NetworkUtils.py | SPYDER - Autonomous Options Trading System v1.0 | 499 |
| Spyder/SpyderU_Utilities/SpyderU06_MathUtils.py | SPYDER - Autonomous Options Trading System v1.0 | 837 |
| Spyder/SpyderU_Utilities/SpyderU07_Constants.py | Module for constants functionality. | 756 |
| Spyder/SpyderU_Utilities/SpyderU08_Validators.py | SPYDER - Autonomous Options Trading System v1.0 | 884 |
| Spyder/SpyderU_Utilities/SpyderU09_DataTypes.py | SPYDER - Autonomous Options Trading System v1.0 | 708 |
| Spyder/SpyderU_Utilities/SpyderU10_TradingCalendar.py | SPYDER - Autonomous Options Trading System v1.0 | 926 |
| Spyder/SpyderU_Utilities/SpyderU11_FeatureFlags.py | SPYDER - Autonomous Options Trading System v1.0 | 733 |
| Spyder/SpyderU_Utilities/SpyderU12_AgentIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 428 |
| Spyder/SpyderU_Utilities/SpyderU13_TechnicalIndicators.py | SPYDER - Autonomous Options Trading System v1.0 | 782 |
| Spyder/SpyderU_Utilities/SpyderU14_OptionStrategies.py | SPYDER - Autonomous Options Trading System v1.0 | 880 |
| Spyder/SpyderU_Utilities/SpyderU15_PerformanceMetrics.py | SPYDER - Autonomous Options Trading System v1.0 | 794 |
| Spyder/SpyderU_Utilities/SpyderU16_TechnicalAnalysis.py | SPYDER - Autonomous Options Trading System | 690 |
| Spyder/SpyderU_Utilities/SpyderU17_LLMUtils.py | SPYDER - Autonomous Options Trading System v1.0 | 91 |
| Spyder/SpyderU_Utilities/SpyderU18_DependencyAnalyzer.py | SPYDER - Autonomous Options Trading System v1.0 | 749 |
| Spyder/SpyderU_Utilities/SpyderU19_InteractionMatrix.py | SPYDER - Autonomous Options Trading System v1.0 | 923 |
| Spyder/SpyderU_Utilities/SpyderU20_InstitutionalLibraries.py | SPYDER - Autonomous Options Trading System v1.0 | 916 |
| Spyder/SpyderU_Utilities/SpyderU22_ETTimeDisplay.py | SPYDER - Autonomous Options Trading System v1.0 | 146 |
| Spyder/SpyderU_Utilities/SpyderU23_MemoryMonitor.py | SPYDER - Autonomous Options Trading System v1.0 | 644 |
| Spyder/SpyderU_Utilities/SpyderU24_StyleManager.py | SPYDER - Autonomous Options Trading System v1.0 | 716 |
| Spyder/SpyderU_Utilities/SpyderU27_SystemOptimizer.py | SPYDER - Autonomous Options Trading System v1.0 | 465 |
| Spyder/SpyderU_Utilities/SpyderU40_RateLimiter.py | SPYDER - Autonomous Options Trading System v1.0 | 342 |
| Spyder/SpyderU_Utilities/SpyderU41_CircuitBreaker.py | SPYDER - Autonomous Options Trading System v1.0 | 381 |
| Spyder/SpyderU_Utilities/SpyderU42_StrategyCircuitBreaker.py | SPYDER - Autonomous Options Trading System v1.0 | 673 |
| Spyder/SpyderU_Utilities/SpyderU43_CorrelationLogger.py | SPYDER - Autonomous Options Trading System v1.0 | 479 |
| Spyder/SpyderU_Utilities/SpyderU44_ShutdownCoordinator.py | SPYDER - Autonomous Options Trading System v1.0 | 181 |
| Spyder/SpyderU_Utilities/SpyderU45_RetryWithBackoff.py | SPYDER - Autonomous Options Trading System v1.0 | 296 |
| Spyder/SpyderU_Utilities/SpyderU46_SecretsManager.py | SPYDER - Autonomous Options Trading System v1.0 | 372 |
| Spyder/SpyderU_Utilities/SpyderU47_OptionalImport.py | SPYDER - Autonomous Options Trading System v1.0 | 130 |
| Spyder/SpyderU_Utilities/SpyderU48_Money.py | A22/O4 (v14): Decimal-backed Money type for cent-precise accounting. | 103 |
| Spyder/SpyderU_Utilities/SpyderU49_SymbolCatalog.py | SPYDER - Autonomous Options Trading System v1.0 | 358 |
| Spyder/SpyderU_Utilities/SpyderU50_AsyncBridge.py | SpyderU50_AsyncBridge — safe async-from-thread execution helper. | 75 |
| Spyder/SpyderU_Utilities/__init__.py | SPYDER - Automated SPY Options Trading System | 492 |
| **Subtotal** | **36 modules** | **20,669** |

### SpyderV_QuantModels (Series V)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderV_QuantModels/SpyderV01_QuantEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 932 |
| Spyder/SpyderV_QuantModels/SpyderV02_ModelManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,051 |
| Spyder/SpyderV_QuantModels/SpyderV03_DataInterface.py | SPYDER - Autonomous Options Trading System v1.0 | 663 |
| Spyder/SpyderV_QuantModels/SpyderV04_RiskManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,344 |
| Spyder/SpyderV_QuantModels/SpyderV05_PricingEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 1,545 |
| Spyder/SpyderV_QuantModels/SpyderV06_VolatilityEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 1,729 |
| Spyder/SpyderV_QuantModels/SpyderV07_AdvancedModels.py | SPYDER - Autonomous Options Trading System v1.0 | 1,303 |
| Spyder/SpyderV_QuantModels/SpyderV08_AIModels.py | SPYDER - Autonomous Options Trading System v1.0 | 1,208 |
| Spyder/SpyderV_QuantModels/SpyderV09_IVEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 973 |
| Spyder/SpyderV_QuantModels/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 497 |
| **Subtotal** | **10 modules** | **11,245** |

### SpyderX_Agents (Series X)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderX_Agents/SpyderX01_GreeksAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 2,395 |
| Spyder/SpyderX_Agents/SpyderX02_FlowAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,307 |
| Spyder/SpyderX_Agents/SpyderX03_StrategyDirectorAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,228 |
| Spyder/SpyderX_Agents/SpyderX04_RiskGuardianAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 834 |
| Spyder/SpyderX_Agents/SpyderX05_MLResearchAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,478 |
| Spyder/SpyderX_Agents/SpyderX06_BacktestingAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 784 |
| Spyder/SpyderX_Agents/SpyderX07_ExecutionStrategyAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 957 |
| Spyder/SpyderX_Agents/SpyderX08_PerformanceAnalyticsAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 507 |
| Spyder/SpyderX_Agents/SpyderX09_AlertManagerAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,178 |
| Spyder/SpyderX_Agents/SpyderX10_QuantModelsAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,531 |
| Spyder/SpyderX_Agents/SpyderX11_SentimentAnalysisAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,494 |
| Spyder/SpyderX_Agents/SpyderX12_SystemHealthAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,233 |
| Spyder/SpyderX_Agents/SpyderX13_MarketAnalysisAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 885 |
| Spyder/SpyderX_Agents/SpyderX14_OrchestratorAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 1,373 |
| Spyder/SpyderX_Agents/SpyderX15_StrategyGeneratorAgent.py | SPYDER - Autonomous Options Trading System v1.0 | 468 |
| Spyder/SpyderX_Agents/SpyderX16_MetaCoordinator.py | SPYDER - Autonomous Options Trading System | 1,200 |
| Spyder/SpyderX_Agents/__init__.py | SPYDER - Automated SPY Options Trading System | 337 |
| **Subtotal** | **17 modules** | **19,189** |

### SpyderY_AutoAgents (Series Y)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderY_AutoAgents/SpyderY00_BaseAutoAgent.py | SPYDER - Autonomous Options Trading System | 802 |
| Spyder/SpyderY_AutoAgents/SpyderY01_MarketSenseAgent.py | SPYDER - Autonomous Options Trading System | 553 |
| Spyder/SpyderY_AutoAgents/SpyderY02_StrategyPilotAgent.py | SPYDER - Autonomous Options Trading System | 508 |
| Spyder/SpyderY_AutoAgents/SpyderY03_RiskSentinelAgent.py | SPYDER - Autonomous Options Trading System | 636 |
| Spyder/SpyderY_AutoAgents/SpyderY04_AlphaLearnerAgent.py | SPYDER - Autonomous Options Trading System | 547 |
| Spyder/SpyderY_AutoAgents/SpyderY05_ExecutionOptimizerAgent.py | SPYDER - Autonomous Options Trading System | 560 |
| Spyder/SpyderY_AutoAgents/SpyderY06_NewsSentinelAgent.py | SPYDER - Autonomous Options Trading System | 554 |
| Spyder/SpyderY_AutoAgents/SpyderY07_TradeJournalAgent.py | SPYDER - Autonomous Options Trading System | 611 |
| Spyder/SpyderY_AutoAgents/SpyderY08_MetaOrchestratorAgent.py | SPYDER - Autonomous Options Trading System | 760 |
| Spyder/SpyderY_AutoAgents/SpyderY09_CodeReviewerAgent.py | SPYDER - Autonomous Options Trading System | 463 |
| Spyder/SpyderY_AutoAgents/SpyderY10_AgentScheduler.py | SPYDER - Autonomous Options Trading System | 426 |
| Spyder/SpyderY_AutoAgents/SpyderY_InferenceBackends.py | SPYDER - Autonomous Options Trading System v1.0 | 419 |
| Spyder/SpyderY_AutoAgents/__init__.py | SPYDER - Autonomous Options Trading System | 338 |
| **Subtotal** | **13 modules** | **7,177** |

### SpyderZ_Communication (Series Z)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/SpyderZ_Communication/SpyderZ00_BrokerProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 282 |
| Spyder/SpyderZ_Communication/SpyderZ01_ZeroMQIntegration.py | SPYDER - Autonomous Options Trading System v1.0 | 1,264 |
| Spyder/SpyderZ_Communication/SpyderZ02_MessageProtocol.py | SPYDER - Autonomous Options Trading System v1.0 | 1,453 |
| Spyder/SpyderZ_Communication/SpyderZ03_TradingCoordinator.py | SPYDER - Autonomous Options Trading System v1.0 | 1,489 |
| Spyder/SpyderZ_Communication/SpyderZ04_VolatilityEngine.py | SPYDER - Autonomous Options Trading System v1.0 | 802 |
| Spyder/SpyderZ_Communication/SpyderZ05_OrderRouter.py | SPYDER - Autonomous Options Trading System | 1,216 |
| Spyder/SpyderZ_Communication/SpyderZ06_AutoHedger.py | SPYDER - Autonomous Options Trading System v1.0 | 1,209 |
| Spyder/SpyderZ_Communication/SpyderZ07_MultiProcessManager.py | SPYDER - Autonomous Options Trading System v1.0 | 1,003 |
| Spyder/SpyderZ_Communication/__init__.py | SPYDER - Autonomous Options Trading System v1.0 | 73 |
| **Subtotal** | **9 modules** | **8,791** |

### Spyder_root (Series -)

| Module | Purpose | LOC |
|---|---|---:|
| Spyder/__init__.py | Spyder Trading System - Main Package | 94 |
| **Subtotal** | **1 modules** | **94** |

## Final Totals

- Total modules: 916
- Total LOC: 543,371

