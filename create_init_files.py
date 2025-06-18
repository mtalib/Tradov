#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to create/update all __init__.py files in the Spyder repository
"""

import os
from pathlib import Path
from datetime import datetime

# Define the content for each __init__.py file
INIT_FILES = {
    "SpyderA_Core": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderA_Core
Purpose: Core Trading Engine

This package contains the core components of the Spyder trading system,
including the main application, trading engine, configuration, scheduling,
and event management.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderA01_Main import SpyderApplication, main
from .SpyderA02_TradingEngine import TradingEngine, get_trading_engine
from .SpyderA03_Configuration import Configuration, get_config
from .SpyderA04_Scheduler import Scheduler, get_scheduler
from .SpyderA05_EventManager import EventManager, Event, EventType, get_event_manager

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Main application
    "SpyderApplication",
    "main",
    
    # Trading engine
    "TradingEngine",
    "get_trading_engine",
    
    # Configuration
    "Configuration",
    "get_config",
    
    # Scheduler
    "Scheduler", 
    "get_scheduler",
    
    # Event management
    "EventManager",
    "Event",
    "EventType",
    "get_event_manager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderA_Core"
__description__ = "Core Trading Engine Components"
__version__ = "1.4.0"''',

    "SpyderB_Broker": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderB_Broker
Purpose: Interactive Brokers Integration

This package provides comprehensive integration with Interactive Brokers,
including client connections, order management, position tracking, and
smart order routing.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderB01_IBClient import IBClient, get_ib_client
from .SpyderB02_OrderManager import OrderManager, Order, OrderStatus
from .SpyderB03_PositionTracker import PositionTracker, Position
from .SpyderB04_AccountManager import AccountManager, AccountInfo
from .SpyderB05_ConnectionManager import ConnectionManager
from .SpyderB06_ContractBuilder import ContractBuilder, create_option_contract
from .SpyderB07_IBConnectionManager import IBConnectionManager
from .SpyderB08_IBGatewayConnection import IBGatewayConnection
from .SpyderB09_IBClientPortal import IBClientPortal
from .SpyderB10_IBDataTypes import IBDataTypes, ContractDetails

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # IB Client
    "IBClient",
    "get_ib_client",
    
    # Order management
    "OrderManager",
    "Order",
    "OrderStatus",
    
    # Position tracking
    "PositionTracker",
    "Position",
    
    # Account management
    "AccountManager",
    "AccountInfo",
    
    # Connection management
    "ConnectionManager",
    "IBConnectionManager",
    "IBGatewayConnection",
    "IBClientPortal",
    
    # Contract building
    "ContractBuilder",
    "create_option_contract",
    
    # Data types
    "IBDataTypes",
    "ContractDetails",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderB_Broker"
__description__ = "Interactive Brokers Integration"
__version__ = "1.4.0"''',

    "SpyderC_MarketData": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderC_MarketData
Purpose: Market Data Management

This package handles all market data operations including real-time feeds,
historical data, options chains, and market internals.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderC01_DataFeed import DataFeed, get_data_feed
from .SpyderC02_HistoricalData import HistoricalDataManager
from .SpyderC03_OptionChain import OptionChainManager, OptionChain
from .SpyderC04_MarketInternals import MarketInternals, Breadth
from .SpyderC05_VolumeProfile import VolumeProfile, VolumeAnalysis
from .SpyderC06_DataValidator import DataValidator
from .SpyderC07_OPRAFeed import OPRAFeed
from .SpyderC08_SPYFeed import SPYFeed

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Data feeds
    "DataFeed",
    "get_data_feed",
    "OPRAFeed",
    "SPYFeed",
    
    # Historical data
    "HistoricalDataManager",
    
    # Options data
    "OptionChainManager",
    "OptionChain",
    
    # Market internals
    "MarketInternals",
    "Breadth",
    
    # Volume analysis
    "VolumeProfile",
    "VolumeAnalysis",
    
    # Data validation
    "DataValidator",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderC_MarketData"
__description__ = "Market Data Management"
__version__ = "1.4.0"''',

    "SpyderD_Strategies": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderD_Strategies
Purpose: Trading Strategies

This package contains all trading strategy implementations including
various options strategies, entry/exit logic, and strategy management.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderD01_BaseStrategy import BaseStrategy, StrategySignal
from .SpyderD02_IronCondor import IronCondorStrategy
from .SpyderD03_CreditSpread import CreditSpreadStrategy
from .SpyderD04_ZeroDTE import ZeroDTEStrategy
from .SpyderD05_Straddle import StraddleStrategy
from .SpyderD06_BullPutSpread import BullPutSpreadStrategy
from .SpyderD07_BearCallSpread import BearCallSpreadStrategy
from .SpyderD08_OpeningRangeBreakout import OpeningRangeBreakoutStrategy
from .SpyderD09_GreeksBasedStrategy import GreeksBasedStrategy
from .SpyderD10_IronButterfly import IronButterflyStrategy
from .SpyderD11_SpecializedZeroDTE import SpecializedZeroDTEStrategy
from .SpyderD12_RSIMeanReversion import RSIMeanReversionStrategy
from .SpyderD13_MACrossover import MACrossoverStrategy

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Base strategy
    "BaseStrategy",
    "StrategySignal",
    
    # Options strategies
    "IronCondorStrategy",
    "CreditSpreadStrategy",
    "ZeroDTEStrategy",
    "StraddleStrategy",
    "BullPutSpreadStrategy",
    "BearCallSpreadStrategy",
    "IronButterflyStrategy",
    "SpecializedZeroDTEStrategy",
    
    # Technical strategies
    "OpeningRangeBreakoutStrategy",
    "GreeksBasedStrategy",
    "RSIMeanReversionStrategy",
    "MACrossoverStrategy",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderD_Strategies"
__description__ = "Trading Strategy Implementations"
__version__ = "1.4.0"''',

    "SpyderE_Risk": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderE_Risk
Purpose: Risk Management

This package provides comprehensive risk management functionality including
position sizing, stop loss management, and drawdown control.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderE01_RiskManager import RiskManager, get_risk_manager
from .SpyderE02_PositionSizer import PositionSizer, SizingMethod
from .SpyderE03_StopLossManager import StopLossManager, StopLossType
from .SpyderE04_DrawdownControl import DrawdownController
from .SpyderE06_RiskMetrics import RiskMetrics, PortfolioRisk

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Risk management
    "RiskManager",
    "get_risk_manager",
    
    # Position sizing
    "PositionSizer",
    "SizingMethod",
    
    # Stop loss
    "StopLossManager",
    "StopLossType",
    
    # Drawdown control
    "DrawdownController",
    
    # Risk metrics
    "RiskMetrics",
    "PortfolioRisk",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderE_Risk"
__description__ = "Risk Management Systems"
__version__ = "1.4.0"''',

    "SpyderG_GUI": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderG_GUI
Purpose: Graphical User Interface

This package provides the graphical user interface components for the
Spyder trading system.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderG01_MainWindow import MainWindow
from .SpyderG02_Dashboard import Dashboard, DashboardWidget
from .SpyderG03_GUIEntry import start_gui, SpyderGUI
from .SpyderG04_OptionChainWidget import OptionChainWidget
from .SpyderG05_ChartWidget import ChartWidget
from .SpyderG06_TradingDashboard import TradingDashboard

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Main window
    "MainWindow",
    
    # Dashboard
    "Dashboard",
    "DashboardWidget",
    "TradingDashboard",
    
    # GUI entry
    "start_gui",
    "SpyderGUI",
    
    # Widgets
    "OptionChainWidget",
    "ChartWidget",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderG_GUI"
__description__ = "Graphical User Interface"
__version__ = "1.4.0"''',

    "SpyderH_Storage": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderH_Storage
Purpose: Data Persistence

This package provides data persistence functionality for the Spyder trading system.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderH01_DataAccessLayer import DataAccessLayer, get_dal

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "DataAccessLayer",
    "get_dal",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderH_Storage"
__description__ = "Data Persistence Layer"
__version__ = "1.4.0"''',

    "SpyderM_Monitoring": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderM_Monitoring
Purpose: System Monitoring

This package provides monitoring capabilities for the Spyder system including
system health, AI agents, and trading metrics.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderM01_SystemMonitor import SystemMonitor, get_system_monitor
from .SpyderM03_AIAgentMonitor import AIAgentMonitor
from .SpyderM04_TradingMetrics import TradingMetrics, MetricsCollector

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # System monitoring
    "SystemMonitor",
    "get_system_monitor",
    
    # AI monitoring
    "AIAgentMonitor",
    
    # Trading metrics
    "TradingMetrics",
    "MetricsCollector",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderM_Monitoring"
__description__ = "System Monitoring and Analytics"
__version__ = "1.4.0"''',

    "SpyderN_OptionsAnalytics": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderN_OptionsAnalytics
Purpose: Options Analytics

This package provides advanced options analytics including volatility analysis.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderN08_VolatilitySurface import VolatilitySurface, VolAnalytics

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "VolatilitySurface",
    "VolAnalytics",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderN_OptionsAnalytics"
__description__ = "Advanced Options Analytics"
__version__ = "1.4.0"''',

    "SpyderO_RiskControl": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderO_RiskControl
Purpose: Risk Control Systems

This package provides advanced risk control mechanisms including Greek limits,
circuit breakers, and automatic rebalancing.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderO01_GreekLimitsManager import GreekLimitsManager, GreekLimits
from .SpyderO02_CircuitBreakerProtocol import CircuitBreaker, BreakerStatus
from .SpyderO03_AutomaticRebalancer import AutomaticRebalancer

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Greek limits
    "GreekLimitsManager",
    "GreekLimits",
    
    # Circuit breaker
    "CircuitBreaker",
    "BreakerStatus",
    
    # Rebalancing
    "AutomaticRebalancer",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderO_RiskControl"
__description__ = "Advanced Risk Control Systems"
__version__ = "1.4.0"''',

    "SpyderR_Runtime": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderR_Runtime
Purpose: Runtime Operations

This package contains runtime execution engines for backtesting, paper trading,
and live trading operations.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderR01_BacktestEngine import BacktestEngine, BacktestResults
from .SpyderR02_PaperEngine import PaperTradingEngine
from .SpyderR03_PaperMonitor import PaperTradingMonitor
from .SpyderR04_LiveEngine import LiveTradingEngine

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Backtesting
    "BacktestEngine",
    "BacktestResults",
    
    # Paper trading
    "PaperTradingEngine",
    "PaperTradingMonitor",
    
    # Live trading
    "LiveTradingEngine",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderR_Runtime"
__description__ = "Runtime Execution Engines"
__version__ = "1.4.0"''',

    "SpyderU_Utilities": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderU_Utilities
Purpose: Core Utilities

This package provides core utility functions and classes used throughout
the Spyder system.

Author: Mohamed Talib
Date: {date}
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderU01_Logger import SpyderLogger, get_logger
from .SpyderU02_ErrorHandler import SpyderErrorHandler, ErrorType
from .SpyderU03_DateTimeUtils import DateTimeUtils, TradingCalendar
from .SpyderU04_Encryption import Encryption, encrypt, decrypt
from .SpyderU05_NetworkUtils import NetworkUtils, check_connection
from .SpyderU06_MathUtils import MathUtils, calculate_sharpe
from .SpyderU07_Constants import *  # Import all constants
from .SpyderU08_Validators import Validators, validate_order
from .SpyderU09_DataTypes import SpyderDataTypes
from .SpyderU10_TradingCalendar import TradingCalendar as Calendar
from .SpyderU11_FeatureFlags import FeatureFlags, is_feature_enabled
from .SpyderU12_AgentIntegration import AIAgentManager, AgentStatus
from .SpyderU13_TechnicalIndicators import TechnicalIndicators

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Logging
    "SpyderLogger",
    "get_logger",
    
    # Error handling
    "SpyderErrorHandler",
    "ErrorType",
    
    # Date/Time utilities
    "DateTimeUtils",
    "TradingCalendar",
    "Calendar",
    
    # Encryption
    "Encryption",
    "encrypt",
    "decrypt",
    
    # Network utilities
    "NetworkUtils",
    "check_connection",
    
    # Math utilities
    "MathUtils",
    "calculate_sharpe",
    
    # Validation
    "Validators",
    "validate_order",
    
    # Data types
    "SpyderDataTypes",
    
    # Feature flags
    "FeatureFlags",
    "is_feature_enabled",
    
    # AI Integration
    "AIAgentManager",
    "AgentStatus",
    
    # Technical indicators
    "TechnicalIndicators",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderU_Utilities"
__description__ = "Core Utility Functions"
__version__ = "1.4.0"''',

    "SpyderX_Agents": '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderX_Agents
Purpose: AI Agent Modules

This package contains AI-enhanced agents that augment or replace traditional
modules with intelligent, adaptive functionality.

Author: Mohamed Talib
Date: {date}
Version: 1.0
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderX01_StrategyDirectorAgent import StrategyDirectorAgent
from .SpyderX02_MarketAnalysisAgent import MarketAnalysisAgent
from .SpyderX03_GreeksCalculatorAgent import GreeksCalculatorAgent
from .SpyderX04_RiskGuardianAgent import RiskGuardianAgent
from .SpyderX05_MLResearchAgent import MLResearchAgent
from .SpyderX06_BacktestingAgent import BacktestingAgent
from .SpyderX07_ExecutionStrategyAgent import ExecutionStrategyAgent
from .SpyderX08_PerformanceAnalyticsAgent import PerformanceAnalyticsAgent
from .SpyderX09_AlertManagerAgent import AlertManagerAgent
from .SpyderX10_QuantModelsAgent import QuantModelsAgent
from .SpyderX11_SentimentAnalysisAgent import SentimentAnalysisAgent
from .SpyderX12_SystemHealthAgent import SystemHealthAgent

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Strategy management
    "StrategyDirectorAgent",
    
    # Market analysis
    "MarketAnalysisAgent",
    "SentimentAnalysisAgent",
    
    # Options analytics
    "GreeksCalculatorAgent",
    
    # Risk management
    "RiskGuardianAgent",
    
    # Machine learning
    "MLResearchAgent",
    
    # Backtesting
    "BacktestingAgent",
    
    # Execution
    "ExecutionStrategyAgent",
    
    # Performance
    "PerformanceAnalyticsAgent",
    
    # Alerts
    "AlertManagerAgent",
    
    # Quantitative models
    "QuantModelsAgent",
    
    # System health
    "SystemHealthAgent",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderX_Agents"
__description__ = "AI-Enhanced Agent Modules"
__version__ = "1.0.0"'''
}

def create_init_files(base_path: str = "."):
    """Create all __init__.py files in the Spyder directory structure"""
    
    print("🚀 Creating/Updating __init__.py files for Spyder...")
    print("=" * 60)
    
    created_count = 0
    updated_count = 0
    
    # Get current date for the files
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for folder, content in INIT_FILES.items():
        folder_path = Path(base_path) / folder
        init_file_path = folder_path / "__init__.py"
        
        # Create folder if it doesn't exist
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created folder: {folder}")
        
        # Format content with current date
        formatted_content = content.format(date=current_date)
        
        # Check if file exists
        if init_file_path.exists():
            # Read existing content
            with open(init_file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # Only update if content is different
            if existing_content != formatted_content:
                with open(init_file_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_content)
                print(f"✅ Updated: {init_file_path}")
                updated_count += 1
            else:
                print(f"⏭️  Skipped (no changes): {init_file_path}")
        else:
            # Create new file
            with open(init_file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            print(f"✅ Created: {init_file_path}")
            created_count += 1
    
    # Create root __init__.py
    root_init_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Main package initialization.

Author: Mohamed Talib
Date: {current_date}
Version: 1.4
"""

__version__ = "1.4.0"
__author__ = "Mohamed Talib"
__description__ = "Automated SPY Options Trading System"

# Core imports for easy access
try:
    from SpyderA_Core.SpyderA01_Main import SpyderApplication
    from SpyderA_Core.SpyderA03_Configuration import get_config
    from SpyderA_Core.SpyderA05_EventManager import get_event_manager
    from SpyderB_Broker.SpyderB01_IBClient import get_ib_client
    from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    
    __all__ = [
        "SpyderApplication",
        "get_config",
        "get_event_manager",
        "get_ib_client",
        "get_risk_manager",
        "SpyderLogger",
    ]
    
except ImportError as e:
    # Handle missing modules gracefully during development
    print(f"Warning: Some Spyder modules not available: {{e}}")
    __all__ = []
'''
    
    root_init_path = Path(base_path) / "__init__.py"
    with open(root_init_path, 'w', encoding='utf-8') as f:
        f.write(root_init_content)
    print(f"✅ Created/Updated root __init__.py")
    
    print("=" * 60)
    print(f"📊 Summary:")
    print(f"   Created: {created_count} files")
    print(f"   Updated: {updated_count} files")
    print(f"   Total: {len(INIT_FILES) + 1} __init__.py files")
    print("=" * 60)
    print("✅ All __init__.py files have been created/updated!")
    
    # Additional instructions
    print("\n📝 Next Steps:")
    print("1. Review the imports in each __init__.py file")
    print("2. Adjust based on actual module exports")
    print("3. Test imports: python -c 'import SpyderA_Core'")
    print("4. Run pylint to check for import issues")

if __name__ == "__main__":
    import sys
    
    # Allow passing a custom base path
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    create_init_files(base_path)
