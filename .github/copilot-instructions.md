# Copilot Instructions — Spyder Trading System

## Project Overview

**Spyder** is an autonomous algorithmic trading system for SPY (S&P 500 ETF) options. It uses a modular architecture with 24+ Python packages (A–Z series), combining real-time market analysis, multi-strategy execution, ML-driven predictions, and strict risk management.

- **Primary instrument**: SPY options (Iron Condors, Credit Spreads, Straddles, Zero-DTE, etc.)
- **Broker**: Tradier API (Bearer token auth) — `SpyderB40_TradierClient`
- **Market Data**: Databento (real-time + historical) — migrating from Polygon.io
- **GUI**: PySide6 (LGPL, Qt6)
- **ML**: scikit-learn, PyTorch, TensorFlow, XGBoost, stable-baselines3
- **LLM Agents**: Ollama (local) with 4 model roles: PRIMARY, FAST, CODE, FINANCE
- **Database**: SQLite
- **OS**: Ubuntu 25.04 / Python 3.13.3 / virtualenv (`.venv`)
- **License policy**: No AGPL dependencies allowed

## Critical Rules

1. **NEVER hardcode credentials** — use `.env` for all API keys, tokens, and secrets
2. **NEVER execute live trades without explicit confirmation** — default to sandbox mode
3. **ALWAYS test in sandbox/paper mode first** before any live deployment
4. **ALWAYS use feature branches** — never commit directly to `master`
5. **NEVER use `print()` in production code** — use `SpyderLogger` from `SpyderU01_Logger`
6. **This system handles REAL MONEY** — every change must be thoroughly tested

## Architecture — Module Series

Each module follows the naming pattern `SpyderX_Name/SpyderXNN_Purpose.py`:

| Series | Package | Responsibility |
|--------|---------|---------------|
| **A** | `SpyderA_Core` | System orchestration, main entry point, configuration |
| **B** | `SpyderB_Broker` | Tradier API integration, order management, execution |
| **C** | `SpyderC_MarketData` | Real-time data feeds, historical data, validation |
| **D** | `SpyderD_Strategies` | Strategy implementations (Iron Condor, Credit Spread, Zero-DTE, etc.) |
| **E** | `SpyderE_Risk` | Risk management, position sizing, circuit breakers, drawdown controls |
| **F** | `SpyderF_Analysis` | Technical indicators, price action, volatility regime detection |
| **G** | `SpyderG_GUI` | PySide6 interface, dashboards, charting |
| **H** | `SpyderH_Storage` | SQLite persistence, data access layer, caching |
| **I** | `SpyderI_Integration` | Third-party integrations, event routing, agent message bus |
| **J** | `SpyderJ_Alerts` | Email, desktop, and Telegram notifications |
| **K** | `SpyderK_Reports` | Performance reports, analytics dashboards |
| **L** | `SpyderL_ML` | Machine learning models, feature engineering, predictions |
| **M** | `SpyderM_Monitoring` | System health, metrics, HMM regime detection |
| **N** | `SpyderN_OptionsAnalytics` | Options pricing, Greeks, volatility surfaces |
| **O** | `SpyderO_TradingIntelligence` | Advanced analytics, opportunity scanning |
| **P** | `SpyderP_PortfolioMgmt` | Portfolio optimization, allocation, strategy rotation |
| **Q** | `SpyderQ_Scripts` | Shell scripts, systemd services, utility launchers |
| **R** | `SpyderR_Runtime` | Backtest engine, paper engine, live engine |
| **S** | `SpyderS_Signals` | Custom signal generation and processing |
| **T** | `SpyderT_Testing` | pytest framework, test utilities, mock data providers |
| **U** | `SpyderU_Utilities` | Logger, error handler, date/time utils, constants |
| **V** | `SpyderV_QuantModels` | Quantitative models, statistical analysis |
| **X** | `SpyderX_Agents` | On-demand AI agents (stateless, 16 agents) |
| **Y** | `SpyderY_AutoAgents` | Autonomous LLM-powered agents (24/7, persistent, 9 agents) |
| **Z** | `SpyderZ_Communication` | Inter-module messaging |

## Data Flow

```
Databento WebSocket → SpyderC_MarketData (normalization/validation)
                        ↓
                  SpyderF_Analysis (indicators, regime detection)
                        ↓
                  SpyderD_Strategies (signal generation)
                        ↓
                  SpyderE_Risk (validation, position sizing)
                        ↓
                  SpyderB_Broker/TradierClient (order execution via Tradier API)
```

## API Configuration

### Tradier API (Order Execution)
- **Sandbox**: `https://sandbox.tradier.com/v1`
- **Live**: `https://api.tradier.com/v1`
- **Auth**: Bearer token in `Authorization` header
- **Env vars**: `TRADIER_API_KEY`, `TRADIER_ACCOUNT_ID`, `TRADIER_ENVIRONMENT`

### Databento (Market Data)
- **Auth**: API key
- **Env vars**: `DATABENTO_API_KEY`
- **Schemas**: MBO (L3), MBP-1/MBP-10 (L1/L2 book), TBBO, OHLCV, trades, definition
- **Use cases**: Real-time streaming, historical bars, options chains, replay

## Coding Standards

### File Structure Template
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_ModuleName
Module: SpyderXNN_Purpose.py
Purpose: Brief description

Author: [Author Name]
Year Created: 2025
Last Updated: YYYY-MM-DD Time: HH:MM:SS
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_RETRIES = 3

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MyModule:
    """Google-style docstring with Args, Returns, Raises sections."""
    pass
```

### Naming Conventions
- **Modules**: `SpyderX_CategoryName` → `SpyderXNN_Purpose.py`
- **Classes**: `PascalCase` (e.g., `PositionManager`, `IronCondorStrategy`)
- **Functions/methods**: `snake_case` (e.g., `calculate_position_size`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- **Private**: prefix with `_` (e.g., `_validate_config`)
- **Variables**: `snake_case` (e.g., `current_price`, `is_market_open`)

### Type Hints — Mandatory
All function signatures must include type hints for parameters and return values:
```python
def calculate_option_delta(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02
) -> float:
```

Use `Decimal` for precise financial calculations. Use `Optional[T]` for nullable params.

### Docstrings — Google Style
```python
def execute_order(order_data: dict) -> bool:
    """
    Execute a trading order through the Tradier API.

    Args:
        order_data: Dictionary with keys 'symbol', 'quantity', 'side', 'type'.

    Returns:
        True if the order was accepted, False otherwise.

    Raises:
        ConnectionError: If the Tradier API is unreachable.
        ValueError: If order_data is invalid.
    """
```

### Error Handling
- Use specific exception types, not bare `except:`
- Implement retry with exponential backoff for network calls
- Use custom exceptions: `SpyderException`, `TradingError`, `DataValidationError`
- Always log errors with `self.logger.error(...)` and include traceback for unexpected errors

### Design Patterns Used
- **Singleton**: `SpyderLogger`, system-wide config
- **Factory**: `StrategyFactory` for strategy creation
- **Builder**: `ComplexOrderBuilder` for multi-leg orders
- **Observer**: Event-driven via `SpyderI02_EventRouter` and `SpyderI06_AgentMessageBus`
- **Circuit Breaker**: `SpyderE16_CircuitBreakerProtocol` for cascading failure prevention

## Risk Management Principles

- **Capital preservation over profit maximization**
- Max 2% of capital per trade (`MAX_PORTFOLIO_RISK = 0.02`)
- Max 5% of capital at risk per day (`MAX_DAILY_RISK = 0.05`)
- Max 20% allocation per strategy (`MAX_STRATEGY_ALLOCATION = 0.20`)
- Greeks exposure limits enforced (delta, gamma, vega, theta)
- Multi-layer framework: pre-trade → position → strategy → portfolio level
- Circuit breakers halt trading on excessive drawdown or volatility

## Testing Requirements

- **Framework**: pytest with `SpyderTestBase` base class
- **Test files**: `test_SpyderXNN_ModuleName.py` in `SpyderT_Testing/`
- **Coverage target**: >80%
- **Pattern**: Arrange → Act → Assert
- Use `unittest.mock` for external dependencies (broker API, market data)
- All strategies must pass paper trading validation before live deployment
- Run `pytest SpyderT_Testing/` before every commit

## Security

- API keys and tokens in `.env` only — never in source code
- `.env` is in `.gitignore`
- Validate all external inputs and API responses
- Log trading decisions but never log credentials
- Use environment variable `TRADIER_ENVIRONMENT=sandbox|production` to control mode

## Common Commands

```bash
source .venv/bin/activate                          # Activate environment
python SpyderA_Core/SpyderA01_Main.py              # Start system
pytest SpyderT_Testing/                            # Run all tests
tail -f logs/spyder.log                            # Monitor logs
git checkout -b feature/your-feature-name          # New feature branch
```

## Key Files

- Entry point: `SpyderA_Core/SpyderA01_Main.py`
- Broker client: `SpyderB_Broker/SpyderB40_TradierClient.py`
- Risk manager: `SpyderE_Risk/SpyderE01_RiskManager.py`
- Logger: `SpyderU_Utilities/SpyderU01_Logger.py`
- Config: `config/config.py` and `.env`
- Agent message bus: `SpyderI_Integration/SpyderI06_AgentMessageBus.py`
