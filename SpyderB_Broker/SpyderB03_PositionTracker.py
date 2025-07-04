#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB03_PositionTracker.py
Group: B (Broker Integration)
Purpose: Comprehensive position tracking with real-time P&L and Greeks

Description:
    This module provides real-time position tracking, P&L calculation, and Greeks
    monitoring for all active positions. It maintains accurate position records,
    handles partial fills, tracks cost basis, and provides comprehensive portfolio
    analytics. The module integrates with Interactive Brokers for live position
    data and includes sophisticated risk metrics calculation.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 17:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# Options pricing imports
try:
    from py_vollib.black_scholes import black_scholes
    from py_vollib.black_scholes.greeks import delta, gamma, theta, vega, rho
    HAS_VOLLIB = True
except ImportError:
    HAS_VOLLIB = False
    print("WARNING: py_vollib not found. Greeks calculation will be limited.")

# IB Integration
try:
    from ib_insync import IB, Stock, Option, Contract, Portfolio
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not found. Running in simulation mode.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderAction
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# Conditional imports
try:
    from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
    HAS_GREEKS_CALCULATOR = True
except ImportError:
    HAS_GREEKS_CALCULATOR = False

try:
    from SpyderC_MarketData.SpyderC01_DataFeed import get_data_feed
    HAS_DATA_FEED = True
except ImportError:
    HAS_DATA_FEED = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Position Tracking Configuration
POSITION_UPDATE_INTERVAL = 5.0  # seconds
PNL_CALCULATION_INTERVAL = 1.0  # seconds
GREEKS_UPDATE_INTERVAL = 10.0   # seconds

# Risk Metrics
MAX_PORTFOLIO_DELTA = 1000
MAX_SINGLE_POSITION_SIZE = 50000  # USD
POSITION_WARNING_THRESHOLD = 0.8  # 80% of limit

# Greeks Calculation
DEFAULT_RISK_FREE_RATE = 0.05  # 5%
DEFAULT_DIVIDEND_YIELD = 0.02   # 2%

# Performance Limits
MAX_POSITIONS_TRACKED = 1000
POSITION_HISTORY_DAYS = 30

# ==============================================================================
# ENUMS
# ==============================================================================
class PositionType(Enum):
    """Position type enumeration"""
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"
    COMBO = "combo"

class PositionStatus(Enum):
    """Position status enumeration"""
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    ASSIGNED = "assigned"
    EXERCISED = "exercised"

class GreeksQuality(Enum):
    """Greeks calculation quality"""
    HIGH = "high"          # Real-time from broker
    MEDIUM = "medium"      # Calculated with current data
    LOW = "low"           # Estimated/stale data
    UNKNOWN = "unknown"    # No data available

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionGreeks:
    """Position Greeks data structure"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_volatility: float = 0.0
    quality: GreeksQuality = GreeksQuality.UNKNOWN
    calculation_time: datetime = field(default_factory=datetime.now)
    underlying_price: float = 0.0
    time_to_expiry: float = 0.0

@dataclass
class PositionPnL:
    """Position P&L data structure"""
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    percentage_return: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class PositionEntry:
    """Individual position entry"""
    position_id: str
    symbol: str
    position_type: PositionType
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    pnl_data: PositionPnL
    greeks: Optional[PositionGreeks] = None
    contract_details: Optional[Dict[str, Any]] = None
    strategy_id: Optional[str] = None
    entry_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    status: PositionStatus = PositionStatus.OPEN
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PortfolioSummary:
    """Portfolio summary data"""
    total_positions: int = 0
    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    max_position_size: float = 0.0
    concentration_risk: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class PositionRisk:
    """Position risk metrics"""
    position_size_ratio: float = 0.0  # % of portfolio
    delta_contribution: float = 0.0   # % of portfolio delta
    concentration_score: float = 0.0  # Risk concentration
    liquidity_score: float = 0.0     # Liquidity assessment
    risk_level: str = "LOW"          # LOW, MEDIUM, HIGH, CRITICAL


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PositionTracker:
    """
    Comprehensive Position Tracking System.
    
    This class provides real-time position tracking, P&L calculation, and risk
    monitoring for all portfolio positions. It maintains accurate position records,
    calculates Greeks, and provides comprehensive portfolio analytics.
    
    Key Features:
    - Real-time position tracking and P&L calculation
    - Options Greeks calculation and monitoring
    - Portfolio risk metrics and concentration analysis
    - Integration with broker APIs for live data
    - Historical position tracking and analytics
    - Multi-threaded updates for performance
    
    Attributes:
        logger: Module logger instance
        config: Position tracker configuration
        positions: Active position tracking
        portfolio_summary: Current portfolio metrics
        
    Example:
        >>> tracker = PositionTracker(config, spyder_client)
        >>> tracker.initialize()
        >>> positions = tracker.get_all_positions()
    """
    
    def __init__(self, config: Dict[str, Any], spyder_client):
        """
        Initialize the Position Tracker.
        
        Args:
            config: Configuration dictionary
            spyder_client: Spyder broker client instance
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        self.spyder_client = spyder_client
        
        # Position tracking
        self.positions: Dict[str, PositionEntry] = {}
        self.position_history: deque = deque(maxlen=10000)
        self.portfolio_summary = PortfolioSummary()
        self._position_lock = RLock()
        
        # Threading infrastructure
        self.worker_threads: Dict[str, threading.Thread] = {}
        self._shutdown_event = ThreadEvent()
        
        # Market data integration
        self.market_data_cache: Dict[str, Dict[str, Any]] = {}
        self._market_data_lock = RLock()
        
        # Greeks calculation
        if HAS_GREEKS_CALCULATOR:
            try:
                self.greeks_calculator = GreeksCalculator()
                self.has_greeks_calculator = True
            except Exception as e:
                self.logger.warning(f"Greeks calculator initialization failed: {e}")
                self.greeks_calculator = None
                self.has_greeks_calculator = False
        else:
            self.greeks_calculator = None
            self.has_greeks_calculator = False
        
        # Data feed integration
        if HAS_DATA_FEED:
            try:
                self.data_feed = get_data_feed()
                self.has_data_feed = True
            except Exception as e:
                self.logger.warning(f"Data feed initialization failed: {e}")
                self.data_feed = None
                self.has_data_feed = False
        else:
            self.data_feed = None
            self.has_data_feed = False
        
        # IB Integration
        self.ib_connection = None
        self.has_ib_connection = False
        
        # Event manager integration
        try:
            from SpyderA_Core.SpyderA05_EventManager import get_event_manager
            self.event_manager = get_event_manager()
            self.has_event_manager = True
        except Exception as e:
            self.logger.warning(f"Event manager not available: {e}")
            self.event_manager = None
            self.has_event_manager = False
        
        # Performance tracking
        self.last_position_update = datetime.now()
        self.last_pnl_update = datetime.now()
        self.last_greeks_update = datetime.now()
        self.update_count = 0
        
        self.logger.info("PositionTracker initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the position tracker.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing PositionTracker...")
            
            # Initialize IB connection if available
            if HAS_IB_INSYNC and self.spyder_client:
                try:
                    if hasattr(self.spyder_client, 'ib') and self.spyder_client.ib:
                        self.ib_connection = self.spyder_client.ib
                        self.has_ib_connection = True
                        self.logger.info("IB connection available for position tracking")
                    else:
                        self.logger.warning("IB connection not available in spyder_client")
                except Exception as e:
                    self.logger.warning(f"IB connection setup failed: {e}")
            
            # Initialize market data subscriptions
            self._initialize_market_data()
            
            # Perform initial position sync
            if not self._sync_positions():
                self.logger.warning("Initial position sync failed")
            
            # Start worker threads
            self._start_worker_threads()
            
            self.logger.info("PositionTracker initialization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"PositionTracker initialization failed: {e}")
            self.error_handler.handle_broker_error(e, "PositionTracker", "initialize")
            return False
    
    def start(self) -> bool:
        """
        Start the position tracker.
        
        Returns:
            bool: True if start successful
        """
        try:
            self.logger.info("Starting PositionTracker...")
            
            # Validate connection
            if self.has_ib_connection and self.ib_connection:
                if not self.ib_connection.isConnected():
                    self.logger.warning("IB connection not established")
            
            self.logger.info("PositionTracker started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"PositionTracker start failed: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the position tracker gracefully.
        
        Returns:
            bool: True if stop successful
        """
        try:
            self.logger.info("Stopping PositionTracker...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Stop worker threads
            self._stop_worker_threads()
            
            # Save final position snapshot
            self._save_position_snapshot()
            
            self.logger.info("PositionTracker stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"PositionTracker stop failed: {e}")
            return False
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    def update_positions(self) -> bool:
        """
        Update all position data from broker.
        
        Returns:
            bool: True if update successful
        """
        try:
            update_start = time.time()
            
            # Sync positions from broker
            if not self._sync_positions():
                return False
            
            # Update market data
            self._update_market_data()
            
            # Recalculate P&L
            self._calculate_portfolio_pnl()
            
            # Update Greeks
            self._update_portfolio_greeks()
            
            # Update portfolio summary
            self._update_portfolio_summary()
            
            # Check risk limits
            self._check_risk_limits()
            
            # Update timestamps
            self.last_position_update = datetime.now()
            self.update_count += 1
            
            update_time = (time.time() - update_start) * 1000
            self.logger.debug(f"Position update completed in {update_time:.2f}ms")
            
            # Emit update event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.POSITIONS_UPDATED,
                    {
                        'timestamp': self.last_position_update,
                        'position_count': len(self.positions),
                        'portfolio_value': self.portfolio_summary.total_market_value,
                        'update_time_ms': update_time
                    }
                )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Position update failed: {e}")
            self.error_handler.handle_position_error(e, "PositionTracker", "update_positions")
            return False
    
    def _sync_positions(self) -> bool:
        """Sync positions from broker."""
        try:
            if self.has_ib_connection and self.ib_connection:
                return self._sync_from_ib()
            else:
                # Simulation mode
                return self._simulate_positions()
                
        except Exception as e:
            self.logger.error(f"Position sync failed: {e}")
            return False
    
    def _sync_from_ib(self) -> bool:
        """Sync positions from Interactive Brokers."""
        try:
            # Get portfolio from IB
            portfolio = self.ib_connection.portfolio()
            
            # Clear existing positions for fresh sync
            with self._position_lock:
                # Keep track of existing position IDs
                existing_positions = set(self.positions.keys())
                updated_positions = set()
                
                for item in portfolio:
                    if item.position == 0:
                        continue  # Skip zero positions
                    
                    # Generate position ID
                    position_id = self._generate_position_id(item.contract)
                    updated_positions.add(position_id)
                    
                    # Determine position type
                    if hasattr(item.contract, 'secType'):
                        if item.contract.secType == 'STK':
                            pos_type = PositionType.STOCK
                        elif item.contract.secType == 'OPT':
                            pos_type = PositionType.OPTION
                        elif item.contract.secType == 'FUT':
                            pos_type = PositionType.FUTURE
                        else:
                            pos_type = PositionType.COMBO
                    else:
                        pos_type = PositionType.STOCK
                    
                    # Create or update position
                    if position_id in self.positions:
                        position = self.positions[position_id]
                        position.quantity = int(item.position)
                        position.avg_cost = float(item.averageCost) if item.averageCost else 0.0
                        position.market_value = float(item.marketValue) if item.marketValue else 0.0
                        position.last_update = datetime.now()
                    else:
                        # Create new position
                        position = PositionEntry(
                            position_id=position_id,
                            symbol=item.contract.symbol,
                            position_type=pos_type,
                            quantity=int(item.position),
                            avg_cost=float(item.averageCost) if item.averageCost else 0.0,
                            current_price=0.0,  # Will be updated with market data
                            market_value=float(item.marketValue) if item.marketValue else 0.0,
                            cost_basis=float(item.position * item.averageCost) if item.averageCost else 0.0,
                            pnl_data=PositionPnL(),
                            contract_details=self._extract_contract_details(item.contract)
                        )
                        
                        self.positions[position_id] = position
                
                # Remove positions that are no longer in the portfolio
                closed_positions = existing_positions - updated_positions
                for position_id in closed_positions:
                    if position_id in self.positions:
                        self.positions[position_id].status = PositionStatus.CLOSED
                        # Move to history
                        self.position_history.append(copy.deepcopy(self.positions[position_id]))
                        del self.positions[position_id]
                
                self.logger.debug(f"Synced {len(updated_positions)} positions from IB")
                return True
                
        except Exception as e:
            self.logger.error(f"IB position sync failed: {e}")
            return False
    
    def _simulate_positions(self) -> bool:
        """Simulate positions for testing."""
        try:
            import random
            
            # Create some mock positions if none exist
            if not self.positions:
                mock_positions = [
                    {
                        'symbol': 'SPY',
                        'quantity': 100,
                        'avg_cost': 450.0,
                        'position_type': PositionType.STOCK
                    },
                    {
                        'symbol': 'SPY_230719C00460000',
                        'quantity': -2,
                        'avg_cost': 5.50,
                        'position_type': PositionType.OPTION
                    }
                ]
                
                with self._position_lock:
                    for mock_pos in mock_positions:
                        position_id = str(uuid.uuid4())
                        
                        # Simulate current price
                        price_change = random.uniform(-0.05, 0.05)  # ±5%
                        current_price = mock_pos['avg_cost'] * (1 + price_change)
                        
                        position = PositionEntry(
                            position_id=position_id,
                            symbol=mock_pos['symbol'],
                            position_type=mock_pos['position_type'],
                            quantity=mock_pos['quantity'],
                            avg_cost=mock_pos['avg_cost'],
                            current_price=current_price,
                            market_value=mock_pos['quantity'] * current_price,
                            cost_basis=mock_pos['quantity'] * mock_pos['avg_cost'],
                            pnl_data=PositionPnL()
                        )
                        
                        self.positions[position_id] = position
            else:
                # Update existing positions with simulated price changes
                with self._position_lock:
                    for position in self.positions.values():
                        price_change = random.uniform(-0.02, 0.02)  # ±2%
                        position.current_price *= (1 + price_change)
                        position.market_value = position.quantity * position.current_price
                        position.last_update = datetime.now()
            
            self.logger.debug("Simulated position update completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Position simulation failed: {e}")
            return False
    
    # ==========================================================================
    # P&L CALCULATION
    # ==========================================================================
    
    def _calculate_portfolio_pnl(self):
        """Calculate P&L for all positions."""
        try:
            with self._position_lock:
                for position in self.positions.values():
                    self._calculate_position_pnl(position)
            
            self.last_pnl_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Portfolio P&L calculation failed: {e}")
    
    def _calculate_position_pnl(self, position: PositionEntry):
        """Calculate P&L for a single position."""
        try:
            # Update market value
            position.market_value = position.quantity * position.current_price
            
            # Calculate unrealized P&L
            position.pnl_data.unrealized_pnl = position.market_value - position.cost_basis
            
            # Calculate percentage return
            if position.cost_basis != 0:
                position.pnl_data.percentage_return = (
                    position.pnl_data.unrealized_pnl / abs(position.cost_basis) * 100
                )
            else:
                position.pnl_data.percentage_return = 0.0
            
            # Update market value and cost basis in P&L data
            position.pnl_data.market_value = position.market_value
            position.pnl_data.cost_basis = position.cost_basis
            position.pnl_data.total_pnl = position.pnl_data.unrealized_pnl + position.pnl_data.realized_pnl
            position.pnl_data.last_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Position P&L calculation failed for {position.position_id}: {e}")
    
    # ==========================================================================
    # GREEKS CALCULATION
    # ==========================================================================
    
    def _update_portfolio_greeks(self):
        """Update Greeks for all option positions."""
        try:
            with self._position_lock:
                for position in self.positions.values():
                    if position.position_type == PositionType.OPTION:
                        self._calculate_position_greeks(position)
            
            self.last_greeks_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Portfolio Greeks update failed: {e}")
    
    def _calculate_position_greeks(self, position: PositionEntry):
        """Calculate Greeks for an option position."""
        try:
            if not position.contract_details:
                self.logger.warning(f"No contract details for Greeks calculation: {position.symbol}")
                return
            
            # Extract option details
            contract = position.contract_details
            underlying_price = self._get_underlying_price(position.symbol)
            
            if underlying_price == 0:
                self.logger.warning(f"No underlying price for {position.symbol}")
                return
            
            # Use professional Greeks calculator if available
            if self.has_greeks_calculator:
                greeks = self._calculate_with_professional_greeks(position, underlying_price)
            elif HAS_VOLLIB:
                greeks = self._calculate_with_vollib(position, underlying_price, contract)
            else:
                greeks = self._calculate_basic_greeks(position, underlying_price, contract)
            
            position.greeks = greeks
            
        except Exception as e:
            self.logger.error(f"Greeks calculation failed for {position.position_id}: {e}")
    
    def _calculate_with_professional_greeks(self, position: PositionEntry, underlying_price: float) -> PositionGreeks:
        """Calculate Greeks using professional Greeks calculator."""
        try:
            # This would integrate with SpyderF06_GreeksCalculator
            option_data = {
                'symbol': position.symbol,
                'underlying_price': underlying_price,
                'strike': position.contract_details.get('strike', 0),
                'expiry': position.contract_details.get('expiry'),
                'option_type': position.contract_details.get('right', 'C'),
                'current_price': position.current_price
            }
            
            greeks_result = self.greeks_calculator.calculate_greeks(option_data)
            
            return PositionGreeks(
                delta=greeks_result.get('delta', 0.0),
                gamma=greeks_result.get('gamma', 0.0),
                theta=greeks_result.get('theta', 0.0),
                vega=greeks_result.get('vega', 0.0),
                rho=greeks_result.get('rho', 0.0),
                implied_volatility=greeks_result.get('iv', 0.0),
                quality=GreeksQuality.HIGH,
                underlying_price=underlying_price,
                time_to_expiry=greeks_result.get('tte', 0.0)
            )
            
        except Exception as e:
            self.logger.error(f"Professional Greeks calculation failed: {e}")
            return PositionGreeks(quality=GreeksQuality.UNKNOWN)
    
    def _calculate_with_vollib(self, position: PositionEntry, underlying_price: float, contract: Dict) -> PositionGreeks:
        """Calculate Greeks using py_vollib."""
        try:
            # Extract contract details
            strike = contract.get('strike', 0)
            expiry_date = contract.get('expiry')
            option_type = 'c' if contract.get('right') == 'C' else 'p'
            
            if not all([strike, expiry_date]):
                return PositionGreeks(quality=GreeksQuality.UNKNOWN)
            
            # Calculate time to expiry
            if isinstance(expiry_date, str):
                expiry_dt = datetime.strptime(expiry_date, '%Y%m%d')
            else:
                expiry_dt = expiry_date
            
            time_to_expiry = (expiry_dt - datetime.now()).days / 365.0
            
            if time_to_expiry <= 0:
                return PositionGreeks(quality=GreeksQuality.UNKNOWN)
            
            # Estimate implied volatility (simplified)
            implied_vol = 0.25  # Default 25%
            
            # Use current option price to estimate IV if available
            if position.current_price > 0:
                try:
                    # This is a simplified IV estimation
                    intrinsic_value = max(0, underlying_price - strike) if option_type == 'c' else max(0, strike - underlying_price)
                    time_value = position.current_price - intrinsic_value
                    
                    if time_value > 0:
                        # Rough IV estimation
                        implied_vol = min(2.0, max(0.05, time_value / (underlying_price * math.sqrt(time_to_expiry))))
                
                except:
                    pass
            
            # Calculate Greeks
            greeks_delta = delta(option_type, underlying_price, strike, time_to_expiry, DEFAULT_RISK_FREE_RATE, implied_vol)
            greeks_gamma = gamma(option_type, underlying_price, strike, time_to_expiry, DEFAULT_RISK_FREE_RATE, implied_vol)
            greeks_theta = theta(option_type, underlying_price, strike, time_to_expiry, DEFAULT_RISK_FREE_RATE, implied_vol)
            greeks_vega = vega(option_type, underlying_price, strike, time_to_expiry, DEFAULT_RISK_FREE_RATE, implied_vol)
            greeks_rho = rho(option_type, underlying_price, strike, time_to_expiry, DEFAULT_RISK_FREE_RATE, implied_vol)
            
            return PositionGreeks(
                delta=greeks_delta * position.quantity,
                gamma=greeks_gamma * position.quantity,
                theta=greeks_theta * position.quantity,
                vega=greeks_vega * position.quantity,
                rho=greeks_rho * position.quantity,
                implied_volatility=implied_vol,
                quality=GreeksQuality.MEDIUM,
                underlying_price=underlying_price,
                time_to_expiry=time_to_expiry
            )
            
        except Exception as e:
            self.logger.error(f"py_vollib Greeks calculation failed: {e}")
            return PositionGreeks(quality=GreeksQuality.UNKNOWN)
    
    def _calculate_basic_greeks(self, position: PositionEntry, underlying_price: float, contract: Dict) -> PositionGreeks:
        """Calculate basic Greeks estimation."""
        try:
            # Very basic Greeks estimation for when no other options available
            strike = contract.get('strike', underlying_price)
            option_type = contract.get('right', 'C')
            
            # Simple delta approximation
            moneyness = underlying_price / strike if strike > 0 else 1.0
            
            if option_type == 'C':
                estimated_delta = min(1.0, max(0.0, (moneyness - 0.9) * 5))
            else:
                estimated_delta = max(-1.0, min(0.0, (0.9 - moneyness) * 5))
            
            return PositionGreeks(
                delta=estimated_delta * position.quantity,
                gamma=0.1 * position.quantity,  # Rough estimate
                theta=-0.05 * position.quantity,  # Rough estimate
                vega=0.1 * position.quantity,   # Rough estimate
                rho=0.01 * position.quantity,   # Rough estimate
                implied_volatility=0.25,        # Default
                quality=GreeksQuality.LOW,
                underlying_price=underlying_price,
                time_to_expiry=0.0
            )
            
        except Exception as e:
            self.logger.error(f"Basic Greeks calculation failed: {e}")
            return PositionGreeks(quality=GreeksQuality.UNKNOWN)
    
    # ==========================================================================
    # PORTFOLIO SUMMARY
    # ==========================================================================
    
    def _update_portfolio_summary(self):
        """Update portfolio summary metrics."""
        try:
            with self._position_lock:
                summary = PortfolioSummary()
                
                total_delta = 0.0
                total_gamma = 0.0
                total_theta = 0.0
                total_vega = 0.0
                max_position_value = 0.0
                
                for position in self.positions.values():
                    summary.total_positions += 1
                    summary.total_market_value += position.market_value
                    summary.total_cost_basis += position.cost_basis
                    summary.total_unrealized_pnl += position.pnl_data.unrealized_pnl
                    summary.total_realized_pnl += position.pnl_data.realized_pnl
                    summary.daily_pnl += position.pnl_data.daily_pnl
                    
                    # Track largest position
                    position_value = abs(position.market_value)
                    if position_value > max_position_value:
                        max_position_value = position_value
                    
                    # Aggregate Greeks
                    if position.greeks:
                        total_delta += position.greeks.delta
                        total_gamma += position.greeks.gamma
                        total_theta += position.greeks.theta
                        total_vega += position.greeks.vega
                
                summary.portfolio_delta = total_delta
                summary.portfolio_gamma = total_gamma
                summary.portfolio_theta = total_theta
                summary.portfolio_vega = total_vega
                summary.max_position_size = max_position_value
                
                # Calculate concentration risk
                if summary.total_market_value > 0:
                    summary.concentration_risk = max_position_value / summary.total_market_value
                
                summary.last_update = datetime.now()
                self.portfolio_summary = summary
                
        except Exception as e:
            self.logger.error(f"Portfolio summary update failed: {e}")
    
    # ==========================================================================
    # MARKET DATA INTEGRATION
    # ==========================================================================
    
    def _initialize_market_data(self):
        """Initialize market data subscriptions."""
        try:
            if self.has_data_feed:
                # Subscribe to market data for position symbols
                symbols = set()
                for position in self.positions.values():
                    symbols.add(position.symbol)
                    # Add underlying symbols for options
                    if position.position_type == PositionType.OPTION:
                        underlying = self._extract_underlying_symbol(position.symbol)
                        if underlying:
                            symbols.add(underlying)
                
                for symbol in symbols:
                    try:
                        self.data_feed.subscribe(symbol, self._on_market_data_update)
                    except Exception as e:
                        self.logger.warning(f"Failed to subscribe to {symbol}: {e}")
            
        except Exception as e:
            self.logger.error(f"Market data initialization failed: {e}")
    
    def _update_market_data(self):
        """Update market data for all positions."""
        try:
            with self._position_lock:
                for position in self.positions.values():
                    # Get current price
                    current_price = self._get_current_price(position.symbol)
                    if current_price > 0:
                        position.current_price = current_price
            
        except Exception as e:
            self.logger.error(f"Market data update failed: {e}")
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        try:
            # Check cache first
            with self._market_data_lock:
                if symbol in self.market_data_cache:
                    data = self.market_data_cache[symbol]
                    if 'price' in data:
                        return data['price']
            
            # Fallback to simulation
            return self._simulate_price(symbol)
            
        except Exception as e:
            self.logger.error(f"Failed to get current price for {symbol}: {e}")
            return 0.0
    
    def _get_underlying_price(self, option_symbol: str) -> float:
        """Get underlying price for an option."""
        underlying_symbol = self._extract_underlying_symbol(option_symbol)
        if underlying_symbol:
            return self._get_current_price(underlying_symbol)
        return 0.0
    
    def _simulate_price(self, symbol: str) -> float:
        """Simulate price for testing."""
        import random
        
        if 'SPY' in symbol.upper():
            base_price = 450.0
        else:
            base_price = 100.0
        
        # Add some randomness
        price_change = random.uniform(-0.01, 0.01)  # ±1%
        return base_price * (1 + price_change)
    
    def _on_market_data_update(self, symbol: str, data: Dict[str, Any]):
        """Handle market data updates."""
        try:
            with self._market_data_lock:
                self.market_data_cache[symbol] = data
            
        except Exception as e:
            self.logger.error(f"Market data update handling failed: {e}")
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _generate_position_id(self, contract) -> str:
        """Generate unique position ID from contract."""
        try:
            if hasattr(contract, 'symbol') and hasattr(contract, 'secType'):
                if contract.secType == 'OPT':
                    # Include strike and expiry for options
                    strike = getattr(contract, 'strike', '')
                    expiry = getattr(contract, 'lastTradeDateOrContractMonth', '')
                    right = getattr(contract, 'right', '')
                    return f"{contract.symbol}_{expiry}_{right}_{strike}"
                else:
                    return f"{contract.symbol}_{contract.secType}"
            else:
                return str(uuid.uuid4())
                
        except Exception as e:
            self.logger.error(f"Position ID generation failed: {e}")
            return str(uuid.uuid4())
    
    def _extract_contract_details(self, contract) -> Dict[str, Any]:
        """Extract contract details for storage."""
        try:
            details = {}
            
            if hasattr(contract, 'symbol'):
                details['symbol'] = contract.symbol
            if hasattr(contract, 'secType'):
                details['secType'] = contract.secType
            if hasattr(contract, 'exchange'):
                details['exchange'] = contract.exchange
            if hasattr(contract, 'currency'):
                details['currency'] = contract.currency
            
            # Option-specific details
            if hasattr(contract, 'strike'):
                details['strike'] = float(contract.strike)
            if hasattr(contract, 'right'):
                details['right'] = contract.right
            if hasattr(contract, 'lastTradeDateOrContractMonth'):
                details['expiry'] = contract.lastTradeDateOrContractMonth
            
            return details
            
        except Exception as e:
            self.logger.error(f"Contract details extraction failed: {e}")
            return {}
    
    def _extract_underlying_symbol(self, option_symbol: str) -> Optional[str]:
        """Extract underlying symbol from option symbol."""
        try:
            # Handle standard option naming conventions
            if '_' in option_symbol:
                parts = option_symbol.split('_')
                return parts[0]
            elif len(option_symbol) > 3:
                # Assume first 3-4 characters are the underlying
                return option_symbol[:3] if option_symbol[:3].isalpha() else option_symbol[:4]
            else:
                return option_symbol
                
        except Exception as e:
            self.logger.error(f"Underlying symbol extraction failed: {e}")
            return None
    
    def _check_risk_limits(self):
        """Check portfolio risk limits."""
        try:
            # Check portfolio delta limit
            if abs(self.portfolio_summary.portfolio_delta) > MAX_PORTFOLIO_DELTA:
                self.logger.warning(f"Portfolio delta exceeds limit: {self.portfolio_summary.portfolio_delta}")
                
                if self.has_event_manager:
                    self.event_manager.emit_event(
                        EventType.RISK_LIMIT_EXCEEDED,
                        {
                            'type': 'portfolio_delta',
                            'current_value': self.portfolio_summary.portfolio_delta,
                            'limit': MAX_PORTFOLIO_DELTA,
                            'timestamp': datetime.now()
                        }
                    )
            
            # Check individual position sizes
            for position in self.positions.values():
                position_value = abs(position.market_value)
                if position_value > MAX_SINGLE_POSITION_SIZE:
                    self.logger.warning(f"Position size exceeds limit: {position.symbol} = ${position_value:,.2f}")
                    
                    if self.has_event_manager:
                        self.event_manager.emit_event(
                            EventType.RISK_LIMIT_EXCEEDED,
                            {
                                'type': 'position_size',
                                'symbol': position.symbol,
                                'current_value': position_value,
                                'limit': MAX_SINGLE_POSITION_SIZE,
                                'timestamp': datetime.now()
                            }
                        )
            
            # Check concentration risk
            if self.portfolio_summary.concentration_risk > POSITION_WARNING_THRESHOLD:
                self.logger.warning(f"High concentration risk: {self.portfolio_summary.concentration_risk:.1%}")
            
        except Exception as e:
            self.logger.error(f"Risk limit check failed: {e}")
    
    def _start_worker_threads(self):
        """Start worker threads."""
        try:
            # Position update thread
            position_thread = threading.Thread(
                target=self._position_update_worker,
                name="PositionUpdater",
                daemon=True
            )
            position_thread.start()
            self.worker_threads['position_updater'] = position_thread
            
            # P&L calculation thread
            pnl_thread = threading.Thread(
                target=self._pnl_calculation_worker,
                name="PnLCalculator",
                daemon=True
            )
            pnl_thread.start()
            self.worker_threads['pnl_calculator'] = pnl_thread
            
            # Greeks update thread
            greeks_thread = threading.Thread(
                target=self._greeks_update_worker,
                name="GreeksUpdater",
                daemon=True
            )
            greeks_thread.start()
            self.worker_threads['greeks_updater'] = greeks_thread
            
            self.logger.info("Position tracker worker threads started")
            
        except Exception as e:
            self.logger.error(f"Failed to start worker threads: {e}")
    
    def _stop_worker_threads(self):
        """Stop worker threads."""
        try:
            # Wait for threads to finish
            for name, thread in self.worker_threads.items():
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    if thread.is_alive():
                        self.logger.warning(f"Thread {name} did not stop gracefully")
            
            self.worker_threads.clear()
            self.logger.info("Position tracker worker threads stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping worker threads: {e}")
    
    def _position_update_worker(self):
        """Worker thread for position updates."""
        while not self._shutdown_event.is_set():
            try:
                self._sync_positions()
                self._update_market_data()
                self._shutdown_event.wait(POSITION_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Position update worker error: {e}")
                self._shutdown_event.wait(5.0)
    
    def _pnl_calculation_worker(self):
        """Worker thread for P&L calculations."""
        while not self._shutdown_event.is_set():
            try:
                self._calculate_portfolio_pnl()
                self._update_portfolio_summary()
                self._shutdown_event.wait(PNL_CALCULATION_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"P&L calculation worker error: {e}")
                self._shutdown_event.wait(5.0)
    
    def _greeks_update_worker(self):
        """Worker thread for Greeks updates."""
        while not self._shutdown_event.is_set():
            try:
                self._update_portfolio_greeks()
                self._shutdown_event.wait(GREEKS_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Greeks update worker error: {e}")
                self._shutdown_event.wait(10.0)
    
    def _save_position_snapshot(self):
        """Save position snapshot for historical tracking."""
        try:
            snapshot = {
                'timestamp': datetime.now(),
                'positions': copy.deepcopy(self.positions),
                'portfolio_summary': copy.deepcopy(self.portfolio_summary)
            }
            
            self.position_history.append(snapshot)
            self.logger.debug("Position snapshot saved")
            
        except Exception as e:
            self.logger.error(f"Position snapshot save failed: {e}")
    
    # ==========================================================================
    # PUBLIC QUERY METHODS
    # ==========================================================================
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        Get all current positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            positions = []
            
            with self._position_lock:
                for position in self.positions.values():
                    position_dict = {
                        'position_id': position.position_id,
                        'symbol': position.symbol,
                        'position_type': position.position_type.value,
                        'quantity': position.quantity,
                        'avg_cost': position.avg_cost,
                        'current_price': position.current_price,
                        'market_value': position.market_value,
                        'cost_basis': position.cost_basis,
                        'unrealized_pnl': position.pnl_data.unrealized_pnl,
                        'percentage_return': position.pnl_data.percentage_return,
                        'entry_time': position.entry_time.isoformat(),
                        'last_update': position.last_update.isoformat(),
                        'status': position.status.value
                    }
                    
                    # Add Greeks if available
                    if position.greeks:
                        position_dict['greeks'] = {
                            'delta': position.greeks.delta,
                            'gamma': position.greeks.gamma,
                            'theta': position.greeks.theta,
                            'vega': position.greeks.vega,
                            'rho': position.greeks.rho,
                            'iv': position.greeks.implied_volatility,
                            'quality': position.greeks.quality.value
                        }
                    
                    # Add contract details if available
                    if position.contract_details:
                        position_dict['contract_details'] = position.contract_details
                    
                    positions.append(position_dict)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting all positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for specific symbol.
        
        Args:
            symbol: Symbol to look up
            
        Returns:
            Position dictionary or None if not found
        """
        try:
            with self._position_lock:
                for position in self.positions.values():
                    if position.symbol == symbol:
                        return self._position_to_dict(position)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary metrics.
        
        Returns:
            Portfolio summary dictionary
        """
        try:
            return {
                'total_positions': self.portfolio_summary.total_positions,
                'total_market_value': self.portfolio_summary.total_market_value,
                'total_cost_basis': self.portfolio_summary.total_cost_basis,
                'total_unrealized_pnl': self.portfolio_summary.total_unrealized_pnl,
                'total_realized_pnl': self.portfolio_summary.total_realized_pnl,
                'daily_pnl': self.portfolio_summary.daily_pnl,
                'portfolio_delta': self.portfolio_summary.portfolio_delta,
                'portfolio_gamma': self.portfolio_summary.portfolio_gamma,
                'portfolio_theta': self.portfolio_summary.portfolio_theta,
                'portfolio_vega': self.portfolio_summary.portfolio_vega,
                'max_position_size': self.portfolio_summary.max_position_size,
                'concentration_risk': self.portfolio_summary.concentration_risk,
                'last_update': self.portfolio_summary.last_update.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio summary: {e}")
            return {}
    
    def get_portfolio_greeks(self) -> Dict[str, float]:
        """
        Get aggregated portfolio Greeks.
        
        Returns:
            Dictionary of portfolio Greeks
        """
        try:
            return {
                'delta': self.portfolio_summary.portfolio_delta,
                'gamma': self.portfolio_summary.portfolio_gamma,
                'theta': self.portfolio_summary.portfolio_theta,
                'vega': self.portfolio_summary.portfolio_vega,
                'last_update': self.portfolio_summary.last_update.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio Greeks: {e}")
            return {}
    
    def get_position_risk_metrics(self) -> List[Dict[str, Any]]:
        """
        Get risk metrics for all positions.
        
        Returns:
            List of position risk metrics
        """
        try:
            risk_metrics = []
            total_portfolio_value = self.portfolio_summary.total_market_value
            
            with self._position_lock:
                for position in self.positions.values():
                    position_value = abs(position.market_value)
                    
                    # Calculate risk metrics
                    risk = PositionRisk()
                    
                    if total_portfolio_value > 0:
                        risk.position_size_ratio = position_value / total_portfolio_value
                    
                    if self.portfolio_summary.portfolio_delta != 0:
                        if position.greeks and position.greeks.delta != 0:
                            risk.delta_contribution = abs(position.greeks.delta) / abs(self.portfolio_summary.portfolio_delta)
                    
                    risk.concentration_score = risk.position_size_ratio
                    
                    # Determine risk level
                    if risk.position_size_ratio > 0.3:
                        risk.risk_level = "CRITICAL"
                    elif risk.position_size_ratio > 0.2:
                        risk.risk_level = "HIGH"
                    elif risk.position_size_ratio > 0.1:
                        risk.risk_level = "MEDIUM"
                    else:
                        risk.risk_level = "LOW"
                    
                    risk_metrics.append({
                        'symbol': position.symbol,
                        'position_size_ratio': risk.position_size_ratio,
                        'delta_contribution': risk.delta_contribution,
                        'concentration_score': risk.concentration_score,
                        'risk_level': risk.risk_level,
                        'position_value': position_value
                    })
            
            # Sort by risk level
            risk_metrics.sort(key=lambda x: x['position_size_ratio'], reverse=True)
            return risk_metrics
            
        except Exception as e:
            self.logger.error(f"Error getting position risk metrics: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get position tracker performance metrics.
        
        Returns:
            Performance metrics dictionary
        """
        try:
            return {
                'update_count': self.update_count,
                'last_position_update': self.last_position_update.isoformat(),
                'last_pnl_update': self.last_pnl_update.isoformat(),
                'last_greeks_update': self.last_greeks_update.isoformat(),
                'positions_tracked': len(self.positions),
                'history_entries': len(self.position_history),
                'has_ib_connection': self.has_ib_connection,
                'has_greeks_calculator': self.has_greeks_calculator,
                'has_data_feed': self.has_data_feed
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def _position_to_dict(self, position: PositionEntry) -> Dict[str, Any]:
        """Convert position entry to dictionary."""
        position_dict = {
            'position_id': position.position_id,
            'symbol': position.symbol,
            'position_type': position.position_type.value,
            'quantity': position.quantity,
            'avg_cost': position.avg_cost,
            'current_price': position.current_price,
            'market_value': position.market_value,
            'cost_basis': position.cost_basis,
            'pnl_data': asdict(position.pnl_data),
            'entry_time': position.entry_time.isoformat(),
            'last_update': position.last_update.isoformat(),
            'status': position.status.value,
            'metadata': position.metadata
        }
        
        if position.greeks:
            position_dict['greeks'] = asdict(position.greeks)
        
        if position.contract_details:
            position_dict['contract_details'] = position.contract_details
        
        return position_dict

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_position_tracker(config: Dict[str, Any], spyder_client) -> PositionTracker:
    """
    Factory function to create a PositionTracker instance.
    
    Args:
        config: Position tracker configuration
        spyder_client: Spyder client instance
        
    Returns:
        PositionTracker instance
    """
    return PositionTracker(config, spyder_client)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance
_position_tracker_instance: Optional[PositionTracker] = None
_position_tracker_lock = Lock()

def get_position_tracker(config: Dict[str, Any] = None, spyder_client=None) -> PositionTracker:
    """
    Get singleton PositionTracker instance.
    
    Args:
        config: Configuration (required for first call)
        spyder_client: Spyder client (required for first call)
        
    Returns:
        PositionTracker instance
    """
    global _position_tracker_instance
    
    with _position_tracker_lock:
        if _position_tracker_instance is None:
            if not all([config, spyder_client]):
                raise ValueError("Config and spyder_client required for first position tracker creation")
            _position_tracker_instance = PositionTracker(config, spyder_client)
        
        return _position_tracker_instance

def reset_position_tracker():
    """Reset the singleton position tracker instance (for testing)."""
    global _position_tracker_instance
    with _position_tracker_lock:
        if _position_tracker_instance:
            _position_tracker_instance.stop()
        _position_tracker_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing PositionTracker...")
    
    # Mock configuration
    test_config = {
        'position_update_interval': 5.0,
        'pnl_calculation_interval': 1.0
    }
    
    # Mock spyder client
    class MockSpyderClient:
        def __init__(self):
            self.ib = None
        
        def is_connected(self):
            return True
    
    # Create position tracker
    mock_client = MockSpyderClient()
    position_tracker = PositionTracker(test_config, mock_client)
    
    if position_tracker.initialize():
        print("✅ PositionTracker initialized successfully")
        
        if position_tracker.start():
            print("✅ PositionTracker started successfully")
            
            # Test position updates
            if position_tracker.update_positions():
                print("✅ Position update successful")
            
            # Get positions
            positions = position_tracker.get_all_positions()
            print(f"📊 Found {len(positions)} positions")
            
            # Get portfolio summary
            summary = position_tracker.get_portfolio_summary()
            print(f"💰 Portfolio value: ${summary.get('total_market_value', 0):,.2f}")
            
            # Get portfolio Greeks
            greeks = position_tracker.get_portfolio_greeks()
            print(f"🔢 Portfolio Delta: {greeks.get('delta', 0):.2f}")
            
            # Brief operation
            time.sleep(2)
            
            # Check performance metrics
            metrics = position_tracker.get_performance_metrics()
            print(f"📈 Performance metrics: {metrics}")
            
            if position_tracker.stop():
                print("✅ PositionTracker stopped successfully")
            else:
                print("❌ PositionTracker stop failed")
        else:
            print("❌ PositionTracker start failed")
    else:
        print("❌ PositionTracker initialization failed")
    
    print("PositionTracker testing completed.")#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB03_PositionTracker.py
Group: B (Broker Integration)
Purpose: Comprehensive position tracking with real-time P&L and Greeks

Description:
    This module provides real-time position tracking, P&L calculation, and Greeks
    monitoring for all active positions. It maintains accurate position records,
    handles partial fills, tracks cost basis, and provides comprehensive portfolio
    analytics. The module integrates with Interactive Brokers for live position
    data and includes sophisticated risk metrics calculation.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 17:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# Options pricing imports
try:
    from py_vollib.black_scholes import black_scholes
    from py_vollib.black_scholes.greeks import delta, gamma, theta, vega, rho
    HAS_VOLLIB = True
except ImportError:
    HAS_VOLLIB = False
    print("WARNING: py_vollib not found. Greeks calculation will be limited.")

# IB Integration
try:
    from ib_insync import IB, Stock, Option, Contract, Portfolio
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("WARNING: ib_insync not found. Running in simulation mode.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderAction
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# Conditional imports
try:
    from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
    HAS_GREEKS_CALCULATOR = True
except ImportError:
    HAS_GREEKS_CALCULATOR = False

try:
    from SpyderC_MarketData.SpyderC01_DataFeed import get_data_feed
    HAS_DATA_FEED = True
except ImportError:
    HAS_DATA_FEED = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Position Tracking Configuration
POSITION_UPDATE_INTERVAL = 5.0  # seconds
PNL_CALCULATION_INTERVAL = 1.0  # seconds
GREEKS_UPDATE_INTERVAL = 10.0   # seconds

# Risk Metrics
MAX_PORTFOLIO_DELTA = 1000
MAX_SINGLE_POSITION_SIZE = 50000  # USD
POSITION_WARNING_THRESHOLD = 0.8  # 80% of limit

# Greeks Calculation
DEFAULT_RISK_FREE_RATE = 0.05  # 5%
DEFAULT_DIVIDEND_YIELD = 0.02   # 2%

# Performance Limits
MAX_POSITIONS_TRACKED = 1000
POSITION_HISTORY_DAYS = 30

# ==============================================================================
# ENUMS
# ==============================================================================
class PositionType(Enum):
    """Position type enumeration"""
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"
    COMBO = "combo"

class PositionStatus(Enum):
    """Position status enumeration"""
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"
    ASSIGNED = "assigned"
    EXERCISED = "exercised"

class GreeksQuality(Enum):
    """Greeks calculation quality"""
    HIGH = "high"          # Real-time from broker
    MEDIUM = "medium"      # Calculated with current data
    LOW = "low"           # Estimated/stale data
    UNKNOWN = "unknown"    # No data available

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionGreeks:
    """Position Greeks data structure"""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    implied_volatility: float = 0.0
    quality: GreeksQuality = GreeksQuality.UNKNOWN
    calculation_time: datetime = field(default_factory=datetime.now)
    underlying_price: float = 0.0
    time_to_expiry: float = 0.0

@dataclass
class PositionPnL:
    """Position P&L data structure"""
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    percentage_return: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class PositionEntry:
    """Individual position entry"""
    position_id: str
    symbol: str
    position_type: PositionType
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    cost_basis: float
    pnl_data: PositionPnL
    greeks: Optional[PositionGreeks] = None
    contract_details: Optional[Dict[str, Any]] = None
    strategy_id: Optional[str] = None
    entry_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    status: PositionStatus = PositionStatus.OPEN
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PortfolioSummary:
    """Portfolio summary data"""
    total_positions: int = 0
    total_market_value: float = 0.0
    total_cost_basis: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    max_position_size: float = 0.0
    concentration_risk: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class PositionRisk:
    """Position risk metrics"""
    position_size_ratio: float = 0.0  # % of portfolio
    delta_contribution: float = 0.0   # % of portfolio delta
    concentration_score: float = 0.0  # Risk concentration
    liquidity_score: float = 0.0     # Liquidity assessment
    risk_level: str = "LOW"          # LOW, MEDIUM, HIGH, CRITICAL

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PositionTracker:
