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
SpyderA_Core/
  __init__.py
  SpyderA01_Main.py
  SpyderA02_TradingEngine.py
  SpyderA03_Configuration.py
  SpyderA04_Scheduler.py
  SpyderA05_EventManager.py
SpyderB_Broker/
  __init__.py
  SpyderB01_IBClient.py
  SpyderB02_OrderManager.py
  SpyderB03_PositionTracker.py
  SpyderB04_AccountManager.py
  SpyderB05_ConnectionManager.py
  SpyderB06_ContractBuilder.py
  SpyderB07_IBConnectionManager.py
  SpyderB08_IBGatewayConnection.py
  SpyderB09_IBClientPortal.py
  SpyderB10_IBDataTypes.py
SpyderC_MarketData/
  __init__.py
  SpyderC01_DataFeed.py
  SpyderC02_HistoricalData.py
  SpyderC03_OptionChain.py
  SpyderC04_MarketInternals.py
  SpyderC05_VolumeProfile.py
  SpyderC06_DataValidator.py
  SpyderC07_OPRAFeed.py
  SpyderC08_SPYFeed.py
SpyderD_Strategies/
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
SpyderE_Risk/
  __init__.py
  SpyderE01_RiskManager.py
  SpyderE02_PositionSizer.py
  SpyderE03_StopLossManager.py
  SpyderE04_DrawdownControl.py
  SpyderE06_RiskMetrics.py
SpyderG_GUI/
  __init__.py
  SpyderG01_MainWindow.py
  SpyderG02_Dashboard.py
  SpyderG03_GUIEntry.py
  SpyderG04_OptionChainWidget.py
  SpyderG05_ChartWidget.py
  SpyderG06_TradingDashboard.py
SpyderH_Storage/
  __init__.py
  SpyderH01_DataAccessLayer.py
SpyderM_Monitoring/
  __init__.py
  SpyderM01_SystemMonitor.py
  SpyderM03_AIAgentMonitor.py
  SpyderM04_TradingMetrics.py
SpyderN_OptionsAnalytics/
  __init__.py
  SpyderN08_VolatilitySurface.py
SpyderO_RiskControl/
  __init__.py
  SpyderO01_GreekLimitsManager.py
  SpyderO02_CircuitBreakerProtocol.py
  SpyderO03_AutomaticRebalancer.py
SpyderR_Runtime/
  __init__.py
  SpyderR01_BacktestEngine.py
  SpyderR02_PaperEngine.py
  SpyderR03_PaperMonitor.py
  SpyderR04_LiveEngine.py
SpyderU_Utilities/
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
SpyderX_Agents/
  __init__.py
  SpyderX01_StrategyDirectorAgent.py
  SpyderX02_MarketAnalysisAgent.py
  SpyderX03_GreeksCalculatorAgent.py
  SpyderX04_RiskGuardianAgent.py
  SpyderX05_MLResearchAgent.py
  SpyderX06_BacktestingAgent.py
  SpyderX07_ExecutionStrategyAgent.py
  SpyderX08_PerformanceAnalyticsAgent.py
  SpyderX09_AlertManagerAgent.py
  SpyderX10_QuantModelsAgent.py
  SpyderX11_SentimentAnalysisAgent.py
  SpyderX12_SystemHealthAgent.py

Key Features

Technology Stack

Language: Python 3.8+
GUI: PyQt5
Database: SQLite
Broker: Interactive Brokers API
ML: TensorFlow, scikit-learn, PyTorch
Analysis: pandas, numpy, TA-Lib
Notifications: Email, SMS (Twilio), Slack

This is a professional-grade trading system designed for serious algorithmic options trading with a focus on risk management and automation.
