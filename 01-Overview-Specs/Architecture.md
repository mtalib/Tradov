# CLAUDE.md - AI Assistant Context for Tradov Trading System

## 🚨 CRITICAL RULES

1. **NEVER commit to main branch** - Always use feature branches
2. **NEVER hardcode credentials** - Use .env file for all sensitive data
3. **NEVER execute live trades without explicit confirmation** - Default to TradovBox paper mode with live Tradier data
4. **ALWAYS test Tradier API changes in paper mode first**
5. **ALWAYS verify API connectivity before executing trades**

## 🎯 Project Context

You are working on **Tradov**, a sophisticated algorithmic trading system that:
- Connects to Tradier API through live/production endpoints only
- Processes real-time market data via Databento (OPRA) and Tradier
- Manages risk and positions with real financial implications
- Uses a modular architecture with 24+ specialized components

**Remember**: This system handles REAL MONEY when in live mode. Every change must be thoroughly tested.

## 🏗️ Complete Architecture Overview

### Module Series Structure

**Core System Modules**
- `TradovA_Core` → System orchestration & main entry point
- `TradovB_Broker` → Tradier API connection & order management
- `TradovC_MarketData` → Real-time data processing (Databento + Tradier)
- `TradovD_Strategies` → Trading strategy implementations
- `TradovE_Risk` → Risk management & position sizing

**Analysis & Intelligence**
- `TradovF_Analysis` → Technical analysis & indicators
- `TradovL_ML` → Machine learning models & predictions
- `TradovN_OptionsAnalytics` → Options pricing & Greeks
- `TradovO_TradingIntelligence` → Advanced analytics
- `TradovV_QuantModels` → Quantitative models & backtesting

**User Interface & Reporting**
- `TradovG_GUI` → PyQt6 graphical interface
- `TradovJ_Alerts` → Notification & alert system
- `TradovK_Reports` → Performance reports & analytics

**Infrastructure & Management**
- `TradovH_Storage` → Data persistence & caching
- `TradovI_Integration` → Third-party integrations
- `TradovM_Monitoring` → System health monitoring
- `TradovP_PortfolioMgmt` → Portfolio optimization
- `TradovR_Runtime` → Runtime configuration & management

**Support & Automation**
- `TradovQ_Scripts` → Utility scripts (.sh & .py)
- `TradovS_Signals` → Custom signal generation
- `TradovT_Testing` → Testing framework & utilities
- `TradovU_Utilities` → Shared utilities & helpers
- `TradovX_Agents` → AI agents & automation
- `TradovZ_Communication` → Inter-module messaging

## 📋 Before Starting Any Task

1. **Check current mode**: Verify if system is in PAPER or LIVE mode
2. **Verify API connectivity**: Use TradovB40_TradierClient to check connection status
3. **Review recent logs**: Check logs/ directory for any recent errors
4. **Understand the module**: Each TradovX module has specific responsibilities - respect boundaries

## 🔧 Technology Stack

**Core Environment**
- OS: Ubuntu 25.04 64-bit with GNOME 48
- Python: 3.13.3 with virtual environment (.venv)
- Shell: Bash with custom .bashrc configuration
- IDE: Visual Studio Code + GEDIT

**Trading Infrastructure**
- Broker: Tradier API (REST) — no local gateway required
- Market Data: Databento (OPRA.PILLAR) for real-time options data
- Fallback: Tradier quotes API for testing and redundancy
- Modes: Paper (TradovBox local paper ledger with live Tradier data) / Live (real trading)

**GUI & Visualization**
- Framework: PySide6 with qt6-wayland
- Charts: Matplotlib + Plotly integration
- Real-time Dashboard: Custom PyQt6 components

**Data Processing**
- Primary: Pandas, NumPy, SciPy
- Database: SQLite for persistence
- Time Series: Optimized tick data storage

## 💻 Essential Commands

```bash
# Environment Setup
cd /home/adam/Projects/Tradov
source .venv/bin/activate

# System Operations
python TradovA_Core/TradovA01_Main.py              # Start main system
python Tradov/TradovB_Broker/TradovB40_TradierClient.py  # Test Tradier connection
python TradovM_Monitoring/check_status.py          # Check system health

# Testing & Development
pytest TradovT_Testing/                             # Run all tests
pytest TradovT_Testing/test_specific_module.py     # Run specific tests
tail -f logs/spyder_main.log                       # Monitor logs

# Gateway Management
ps aux | grep -i gateway                            # Check if Gateway running
python TradovB_Broker/TradovB12_GatewayAutomation.py  # Manage Gateway

🔧 Development Workflow

### 1. Feature Development
```bash
git checkout -b feature/your-feature-name
# Make changes following module conventions
git add .
git commit -m "feat(TradovX): description of changes"
```

### 2. Testing Protocol
- **Unit Tests**: `pytest TradovT_Testing/test_your_module.py`
- **Paper Trading**: Test all market interactions in paper mode
- **Integration**: Run system integration tests
- **Log Review**: `tail -f logs/spyder_main.log`

### 3. Pre-Commit Checklist
- ✅ No hardcoded credentials or API keys
- ✅ All tests pass (unit + integration)
- ✅ Paper trading validation complete
- ✅ Log messages are informative, not verbose
- ✅ Type hints added to all new functions
- ✅ Docstrings follow Google format
- ✅ No print() statements (use logging)

## 📝 Code Style & Standards

### Module Structure Template
Follow the pattern from `research/PythonModuleTemplate.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovX_ModuleName
Module: TradovX##_SpecificPurpose.py
Purpose: Brief description of module functionality

Author: [Author Name]
Year Created: 2025
Last Updated: 2025-01-XX Time: HH:MM:SS
"""

# Standard imports
import standard_library_modules

# Third-party imports
import third_party_modules

# Local imports
from TradovU_Utilities.TradovU01_Logger import TradovLogger
```

## 🎯 Development Priorities

### Current Focus (Priority Order)
1. **Stability & Reliability** over new features
2. **Risk Management** over profit optimization
3. **Clear Logging** over performance optimization
4. **Paper Testing** over live deployment
5. **Documentation** over feature additions

---

**⚠️ FINAL REMINDER**: You're working with a financial trading system that can execute real trades with real money. Every change must be thoroughly tested in paper mode first. When in doubt about financial implications, always ask for clarification rather than making assumptions.
