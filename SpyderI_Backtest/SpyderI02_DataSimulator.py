#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI02_DataSimulator.py
Group: I (Backtesting)
Purpose: Historical data simulation for LOGIC TESTING ONLY

═══════════════════════════════════════════════════════════════════════
⚠️ ⚠️ ⚠️  CRITICAL WARNING - READ BEFORE USING  ⚠️ ⚠️ ⚠️
═══════════════════════════════════════════════════════════════════════

This module creates UNREALISTIC simulated data for testing strategy logic.
It does NOT represent real options market behavior!

WHAT THIS SIMULATOR CANNOT DO:
❌ Realistic bid-ask spreads (real spreads are often $0.05-$0.50)
❌ Actual liquidity constraints (many strikes have <100 contracts/day)
❌ True volatility surfaces (real IV varies by strike and time)
❌ Market maker behavior (they widen spreads on large orders)
❌ Pin risk near expiration
❌ Early assignment probability
❌ Actual Greeks behavior during fast markets

THIS IS ONLY FOR:
✅ Testing if your code runs without errors
✅ Debugging strategy logic flow
✅ Validating signal generation
✅ Checking risk management triggers

For real market behavior, use PAPER TRADING with live data!

═══════════════════════════════════════════════════════════════════════

Author: Mohamed Talib
Date: 2025-05-30
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import warnings

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Warning message to display
DATA_SIMULATOR_WARNING = """
╔═══════════════════════════════════════════════════════════════════╗
║                    ⚠️  DATA SIMULATOR WARNING ⚠️                    ║
╠═══════════════════════════════════════════════════════════════════╣
║ This simulator generates FAKE data for logic testing only!        ║
║                                                                   ║
║ Real options markets have:                                        ║
║ • Wide, dynamic bid-ask spreads                                   ║
║ • Limited liquidity on most strikes                               ║
║ • Complex volatility surfaces                                     ║
║ • Market maker games                                              ║
║ • Assignment risk                                                 ║
║                                                                   ║
║ Use PAPER TRADING for realistic market simulation!                ║
╚═══════════════════════════════════════════════════════════════════╝
"""

# Unrealistic default parameters
FAKE_BID_ASK_SPREAD = 0.01  # Real spreads are 10-50x larger!
FAKE_LIQUIDITY = 10000  # Most strikes have <1000 volume
PERFECT_FILLS = True  # Never happens in real trading
NO_SLIPPAGE = True  # Always have slippage in reality

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class SimulatedBar:
    """Simulated price bar - NOT REALISTIC"""
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    
    # Fake options data
    fake_bid: float
    fake_ask: float
    fake_iv: float = 0.20  # Real IV varies significantly
    fake_delta: float = 0.50  # Real delta changes constantly
    
    # Warnings
    is_realistic: bool = False
    warning: str = "This data is for LOGIC TESTING ONLY!"

class SimulatedOptionChain:
    """Simulated option chain - COMPLETELY UNREALISTIC"""
    underlying_price: float
    expiration: datetime.date
    strikes: List[float]
    
    # Fake data that doesn't represent reality
    fake_bids: Dict[float, float]
    fake_asks: Dict[float, float]
    fake_volumes: Dict[float, int]
    fake_open_interest: Dict[float, int]
    fake_ivs: Dict[float, float]
    
    # Greeks that don't behave like real options
    fake_deltas: Dict[float, float]
    fake_gammas: Dict[float, float]
    fake_thetas: Dict[float, float]
    fake_vegas: Dict[float, float]
    
    is_realistic: bool = False
    warning: str = "Real option chains have complex, dynamic behavior!"

# ==============================================================================
# DATA SIMULATOR CLASS
# ==============================================================================
class DataSimulator:
    """
    Simulates market data for LOGIC TESTING ONLY.
    
    ⚠️ WARNING: This does NOT simulate realistic market behavior!
    
    Real options markets have:
    - Wide bid-ask spreads that change with market conditions
    - Limited liquidity that affects fill quality
    - Complex volatility surfaces
    - Market makers who adjust prices based on order flow
    
    Use this ONLY to test if your code runs without errors.
    Use PAPER TRADING for performance validation!
    """
    
    def __init__(self, start_date: datetime.date, end_date: datetime.date):
        """
        Initialize data simulator for LOGIC TESTING.
        
        Args:
            start_date: Start date for simulation
            end_date: End date for simulation
        """
        self.start_date = start_date
        self.end_date = end_date
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Print warning immediately
        print(DATA_SIMULATOR_WARNING)
        warnings.warn(
            "DataSimulator creates UNREALISTIC data for logic testing only!",
            UserWarning,
            stacklevel=2
        )
        
        self.logger.warning("DataSimulator initialized - FOR LOGIC TESTING ONLY!")
        self.logger.warning("This does NOT represent real market behavior!")
        
        # Generate fake underlying price series
        self._generate_fake_prices()
    
    # ==========================================================================
    # FAKE DATA GENERATION
    # ==========================================================================
    def _generate_fake_prices(self) -> None:
        """Generate fake price data - NOT REALISTIC!"""
        # Create unrealistic smooth price movement
        dates = pd.date_range(self.start_date, self.end_date, freq='1min')
        
        # Generate fake SPY prices
        np.random.seed(42)  # Reproducible fake data
        base_price = 400
        trend = np.cumsum(np.random.randn(len(dates)) * 0.1)
        noise = np.random.randn(len(dates)) * 0.5
        
        self.fake_prices = pd.DataFrame({
            'timestamp': dates,
            'close': base_price + trend + noise
        })
        
        # Add other OHLC data (unrealistic relationships)
        self.fake_prices['open'] = self.fake_prices['close'] + np.random.randn(len(dates)) * 0.1
        self.fake_prices['high'] = self.fake_prices[['open', 'close']].max(axis=1) + abs(np.random.randn(len(dates)) * 0.2)
        self.fake_prices['low'] = self.fake_prices[['open', 'close']].min(axis=1) - abs(np.random.randn(len(dates)) * 0.2)
        self.fake_prices['volume'] = np.random.randint(1000000, 5000000, len(dates))
        
        self.fake_prices.set_index('timestamp', inplace=True)
    
    def get_fake_bars(
        self,
        symbol: str,
        start: datetime.datetime,
        end: datetime.datetime
    ) -> pd.DataFrame:
        """
        Get fake price bars for LOGIC TESTING.
        
        ⚠️ These prices are NOT realistic!
        
        Args:
            symbol: Symbol (ignored - always returns fake data)
            start: Start time
            end: End time
            
        Returns:
            DataFrame of fake price data
        """
        self.logger.debug(f"Generating FAKE bars for {symbol} - NOT REAL DATA!")
        
        # Filter fake data by date range
        mask = (self.fake_prices.index >= start) & (self.fake_prices.index <= end)
        fake_data = self.fake_prices[mask].copy()
        
        # Add fake bid-ask (unrealistically tight)
        fake_data['fake_bid'] = fake_data['close'] - FAKE_BID_ASK_SPREAD
        fake_data['fake_ask'] = fake_data['close'] + FAKE_BID_ASK_SPREAD
        fake_data['spread_warning'] = "Real options have 10-50x wider spreads!"
        
        return fake_data
    
    def get_fake_option_chain(
        self,
        underlying_symbol: str,
        expiration: datetime.date,
        timestamp: Optional[datetime.datetime] = None
    ) -> SimulatedOptionChain:
        """
        Get fake option chain for LOGIC TESTING.
        
        ⚠️ This is COMPLETELY UNREALISTIC!
        Real option chains have:
        - Wide, asymmetric bid-ask spreads
        - Limited liquidity on most strikes
        - Complex volatility smiles/skews
        - Dynamic Greeks that change rapidly
        
        Args:
            underlying_symbol: Underlying symbol
            expiration: Option expiration
            timestamp: Current time
            
        Returns:
            Fake option chain for testing only
        """
        self.logger.warning("Generating FAKE option chain - NOT REALISTIC!")
        
        # Get fake underlying price
        if timestamp:
            current_price = self._get_fake_price_at(timestamp)
        else:
            current_price = 400.0
        
        # Generate fake strikes (unrealistic spacing)
        strikes = np.arange(
            int(current_price * 0.9),
            int(current_price * 1.1) + 1,
            1.0
        )
        
        # Create fake option data (completely unrealistic)
        fake_chain = SimulatedOptionChain(
            underlying_price=current_price,
            expiration=expiration,
            strikes=list(strikes),
            fake_bids={},
            fake_asks={},
            fake_volumes={},
            fake_open_interest={},
            fake_ivs={},
            fake_deltas={},
            fake_gammas={},
            fake_thetas={},
            fake_vegas={}
        )
        
        # Fill with fake data
        for strike in strikes:
            # Fake intrinsic value
            intrinsic = max(0, current_price - strike)
            
            # Fake option price (ignores time value, volatility, etc.)
            fake_mid = intrinsic + np.random.uniform(0.5, 2.0)
            
            # Unrealistic tight spreads
            fake_chain.fake_bids[strike] = fake_mid - 0.05
            fake_chain.fake_asks[strike] = fake_mid + 0.05
            
            # Fake volume (way too high for most strikes)
            fake_chain.fake_volumes[strike] = np.random.randint(100, 5000)
            fake_chain.fake_open_interest[strike] = np.random.randint(1000, 10000)
            
            # Fake IV (ignores smile/skew)
            fake_chain.fake_ivs[strike] = 0.20 + np.random.uniform(-0.02, 0.02)
            
            # Fake Greeks (don't behave like real options)
            fake_chain.fake_deltas[strike] = 0.5 + (current_price - strike) * 0.01
            fake_chain.fake_gammas[strike] = 0.01
            fake_chain.fake_thetas[strike] = -0.05
            fake_chain.fake_vegas[strike] = 0.10
        
        return fake_chain
    
    def simulate_fake_fill(
        self,
        order_type: str,
        quantity: int,
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Simulate fake order fill for LOGIC TESTING.
        
        ⚠️ Real fills have:
        - Slippage (especially for market orders)
        - Partial fills on large orders
        - Rejection for unmarketable limits
        - Wide spreads eating into profits
        
        Args:
            order_type: Order type (MARKET/LIMIT)
            quantity: Number of contracts
            limit_price: Limit price (ignored mostly)
            
        Returns:
            Fake fill information
        """
        self.logger.warning("Simulating FAKE fill - NOT REALISTIC!")
        
        return {
            'filled': True,  # Always fills - unrealistic!
            'fill_price': limit_price or 1.00,  # Perfect fill - never happens!
            'fill_quantity': quantity,  # Always full fill - rare for large orders!
            'slippage': 0.00,  # No slippage - impossible!
            'commission': 0.65,  # Only realistic part
            'warning': 'This fill is FAKE! Real fills have slippage and may be partial!',
            'is_realistic': False
        }
    
    def _get_fake_price_at(self, timestamp: datetime.datetime) -> float:
        """Get fake price at timestamp"""
        # Find closest timestamp in fake data
        if timestamp in self.fake_prices.index:
            return self.fake_prices.loc[timestamp, 'close']
        else:
            # Return a random price
            return 400.0 + np.random.randn() * 5
    
    # ==========================================================================
    # WARNING METHODS
    # ==========================================================================
    def print_reality_check(self) -> None:
        """Print reality check for users"""
        reality_check = """
        ╔═══════════════════════════════════════════════════════════════╗
        ║                      REALITY CHECK                             ║
        ╠═══════════════════════════════════════════════════════════════╣
        ║ This simulator CANNOT replicate:                               ║
        ║                                                                ║
        ║ 1. Real Bid-Ask Spreads:                                       ║
        ║    - SPY ATM: $0.05-$0.15 typical                             ║
        ║    - SPY OTM: $0.10-$0.50 common                              ║
        ║    - Spreads widen in fast markets                            ║
        ║                                                                ║
        ║ 2. Actual Liquidity:                                           ║
        ║    - Most strikes: <1,000 contracts/day                       ║
        ║    - Large orders move the market                              ║
        ║    - Partial fills are common                                  ║
        ║                                                                ║
        ║ 3. Greeks Behavior:                                            ║
        ║    - Gamma risk near expiration                               ║
        ║    - Vega changes with IV                                     ║
        ║    - Theta acceleration                                        ║
        ║                                                                ║
        ║ 4. Market Realities:                                           ║
        ║    - Pin risk at expiration                                   ║
        ║    - Early assignment on ITM                                   ║
        ║    - Market maker adjustments                                  ║
        ║                                                                ║
        ║ USE PAPER TRADING FOR REAL PERFORMANCE DATA!                  ║
        ╚═══════════════════════════════════════════════════════════════╝
        """
        print(reality_check)
    
    def get_fake_market_internals(self, timestamp: datetime.datetime) -> Dict[str, float]:
        """
        Get fake market internals for LOGIC TESTING.
        
        Returns:
            Dictionary of fake market internal values
        """
        return {
            'ADD': np.random.randint(-2000, 2000),  # Fake advance-decline
            'TICK': np.random.randint(-1000, 1000),  # Fake tick
            'VIX': 15 + np.random.randn() * 2,  # Fake VIX
            'warning': 'These are FAKE values for testing only!',
            'is_realistic': False
        }

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def create_logic_test_data(days: int = 5) -> DataSimulator:
    """
    Create data simulator for logic testing.
    
    Args:
        days: Number of days of fake data
        
    Returns:
        DataSimulator instance
    """
    print("\n" + "="*70)
    print("CREATING FAKE DATA FOR LOGIC TESTING ONLY!")
    print("This does NOT represent real market behavior!")
    print("Use PAPER TRADING for performance validation!")
    print("="*70 + "\n")
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    
    return DataSimulator(start_date, end_date)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Show warnings
    print(DATA_SIMULATOR_WARNING)
    
    # Create simulator
    simulator = create_logic_test_data(days=5)
    
    # Show reality check
    simulator.print_reality_check()
    
    # Example of fake data
    print("\nExample of FAKE data (not realistic):")
    fake_bars = simulator.get_fake_bars('SPY', datetime.datetime.now() - datetime.timedelta(hours=1), datetime.datetime.now())
    print(fake_bars.head())
    
    print("\n⚠️ Remember: Use PAPER TRADING for real performance testing! ⚠️")
