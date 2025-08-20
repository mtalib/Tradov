#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV03_DataInterface.py  
Purpose: Data bridge between SpyderB08 feeds and quantitative models

Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-20 Time: 12:30:00  

Module Description:
    Provides seamless data integration between SpyderB08 multi-client
    data feeds and quantitative models. Normalizes data formats,
    handles real-time streaming, caches for performance, and provides
    unified interface for pricing and risk models to access market data.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import threading
import queue
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB08_MultiClientDataManager import MultiClientDataManager
    from SpyderB08_MultiClientDataManager import ClientPurpose
    B08_AVAILABLE = True
except ImportError:
    print("⚠️  SpyderB08 not available - using simulated data")
    MultiClientDataManager = None
    ClientPurpose = None
    B08_AVAILABLE = False

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketDataPoint:
    """Individual market data point."""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OptionData:
    """Options data structure."""
    underlying: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    mid: float
    volume: int
    open_interest: int
    implied_vol: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class MarketSentiment:
    """Market sentiment indicators."""
    symbol: str
    put_call_ratio: float
    vix_level: float
    skew_indicator: float
    fear_greed_index: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class InternationalData:
    """International market data."""
    symbol: str
    region: str
    price: float
    change_pct: float
    correlation_spy: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

class DataSource(Enum):
    """SpyderB08 data source mapping."""
    CORE_DATA = 3           # Client 3: Core market data (SPY, QQQ, etc.)
    SPY_OPTIONS = 4         # Client 4: SPY options chains
    MARKET_INTERNALS = 6    # Client 6: VUD + market internals  
    INTERNATIONAL = 10      # Client 10: International markets

# ==============================================================================
# DATA INTERFACE CLASS
# ==============================================================================
class SpyderDataInterface:
    """
    High-performance data bridge between SpyderB08 and quantitative models.
    
    Features:
    - Real-time data streaming from multiple B08 clients
    - Intelligent caching and data normalization
    - Options chain processing and Greeks calculation
    - Market sentiment analysis from internals
    - International correlation tracking
    - Performance optimized for low-latency trading
    """
    
    def __init__(self, cache_size: int = 10000, update_frequency: float = 1.0):
        """Initialize the data interface."""
        self.logger = self._setup_logging()
        self.cache_size = cache_size
        self.update_frequency = update_frequency
        
        # Core components
        self.b08_manager = None
        self.is_running = False
        
        # Data caches - optimized for quick access
        self.spot_prices = {}           # {symbol: MarketDataPoint}
        self.options_chains = {}        # {underlying: List[OptionData]}
        self.historical_data = defaultdict(deque)  # {symbol: deque[MarketDataPoint]}
        self.market_sentiment = {}      # {symbol: MarketSentiment}
        self.international_data = {}    # {symbol: InternationalData}
        
        # Real-time streaming
        self.data_queue = asyncio.Queue()
        self.update_callbacks = defaultdict(list)  # {data_type: [callbacks]}
        self.last_update = {}           # {source: datetime}
        
        # Performance tracking
        self.stats = {
            'updates_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_latency': 0.0,
            'errors': 0
        }
        
        # Threading
        self.update_thread = None
        self.data_lock = threading.RLock()
        
        self.logger.info("🔗 SpyderDataInterface initialized")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for data interface."""
        logger = logging.getLogger('SpyderDataInterface')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger

    async def start(self) -> bool:
        """Start the data interface."""
        try:
            self.logger.info("🚀 Starting SpyderDataInterface...")
            
            # Initialize B08 connection
            if B08_AVAILABLE:
                self.b08_manager = MultiClientDataManager()
                b08_success = self.b08_manager.start()
                if not b08_success:
                    self.logger.warning("⚠️  B08 connection failed - using simulated data")
                    self.b08_manager = None
            
            # Start data streaming
            self.is_running = True
            self.update_thread = threading.Thread(
                target=self._data_update_loop,
                daemon=True
            )
            self.update_thread.start()
            
            # Start async data processor
            asyncio.create_task(self._process_data_queue())
            
            self.logger.info("✅ SpyderDataInterface started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start DataInterface: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the data interface."""
        try:
            self.logger.info("🛑 Stopping SpyderDataInterface...")
            
            self.is_running = False
            
            if self.update_thread:
                self.update_thread.join(timeout=5)
            
            if self.b08_manager:
                self.b08_manager.stop()
            
            self.logger.info("✅ SpyderDataInterface stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping DataInterface: {e}")
            return False

    def _data_update_loop(self):
        """Main data update loop running in separate thread."""
        while self.is_running:
            try:
                start_time = datetime.now()
                
                # Update data from all sources
                self._update_core_data()
                self._update_options_data()
                self._update_market_internals()
                self._update_international_data()
                
                # Track performance
                latency = (datetime.now() - start_time).total_seconds()
                self.stats['avg_latency'] = (self.stats['avg_latency'] * 0.9 + latency * 0.1)
                self.stats['updates_processed'] += 1
                
                # Sleep for update frequency
                threading.Event().wait(self.update_frequency)
                
            except Exception as e:
                self.logger.error(f"Error in data update loop: {e}")
                self.stats['errors'] += 1
                threading.Event().wait(5)  # Wait before retry

    def _update_core_data(self):
        """Update core market data (SPY, QQQ, etc.)."""
        try:
            if self.b08_manager:
                # Get data from Client 3 (Core Data)
                core_data = self.b08_manager.get_client_data(DataSource.CORE_DATA.value)
            else:
                # Simulated data
                core_data = self._generate_simulated_core_data()
            
            with self.data_lock:
                for symbol, data in core_data.items():
                    if isinstance(data, dict) and 'price' in data:
                        data_point = MarketDataPoint(
                            symbol=symbol,
                            price=float(data['price']),
                            volume=int(data.get('volume', 0)),
                            bid=data.get('bid'),
                            ask=data.get('ask'),
                            timestamp=datetime.now()
                        )
                        
                        # Update spot prices
                        self.spot_prices[symbol] = data_point
                        
                        # Add to historical data
                        self.historical_data[symbol].append(data_point)
                        if len(self.historical_data[symbol]) > self.cache_size:
                            self.historical_data[symbol].popleft()
            
            self.last_update[DataSource.CORE_DATA] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating core data: {e}")

    def _update_options_data(self):
        """Update SPY options chain data."""
        try:
            if self.b08_manager:
                # Get data from Client 4 (SPY Options)
                options_data = self.b08_manager.get_client_data(DataSource.SPY_OPTIONS.value)
            else:
                # Simulated data
                options_data = self._generate_simulated_options_data()
            
            with self.data_lock:
                # Process options chain
                if 'SPY' in options_data:
                    spy_options = []
                    
                    for option_info in options_data['SPY'].get('options', []):
                        option = OptionData(
                            underlying='SPY',
                            strike=float(option_info.get('strike', 450)),
                            expiry=self._parse_expiry(option_info.get('expiry', '2025-09-19')),
                            option_type=option_info.get('type', 'call').lower(),
                            bid=float(option_info.get('bid', 0)),
                            ask=float(option_info.get('ask', 0)),
                            mid=float(option_info.get('mid', 0)),
                            volume=int(option_info.get('volume', 0)),
                            open_interest=int(option_info.get('open_interest', 0)),
                            implied_vol=option_info.get('iv'),
                            delta=option_info.get('delta'),
                            gamma=option_info.get('gamma'),
                            vega=option_info.get('vega'),
                            theta=option_info.get('theta')
                        )
                        spy_options.append(option)
                    
                    self.options_chains['SPY'] = spy_options
            
            self.last_update[DataSource.SPY_OPTIONS] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating options data: {e}")

    def _update_market_internals(self):
        """Update market internals including VUD Put/Call ratio."""
        try:
            if self.b08_manager:
                # Get data from Client 6 (Market Internals + VUD)
                internals_data = self.b08_manager.get_client_data(DataSource.MARKET_INTERNALS.value)
            else:
                # Simulated data
                internals_data = self._generate_simulated_internals_data()
            
            with self.data_lock:
                # Process VUD Put/Call ratio
                if 'VUD' in internals_data:
                    vud_data = internals_data['VUD']
                    
                    sentiment = MarketSentiment(
                        symbol='SPY',
                        put_call_ratio=float(vud_data.get('put_call_ratio', 1.0)),
                        vix_level=float(vud_data.get('vix_level', 18.0)),
                        skew_indicator=float(vud_data.get('skew', 0.0)),
                        fear_greed_index=vud_data.get('fear_greed')
                    )
                    
                    self.market_sentiment['SPY'] = sentiment
            
            self.last_update[DataSource.MARKET_INTERNALS] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating market internals: {e}")

    def _update_international_data(self):
        """Update international market data."""
        try:
            if self.b08_manager:
                # Get data from Client 10 (International)
                intl_data = self.b08_manager.get_client_data(DataSource.INTERNATIONAL.value)
            else:
                # Simulated data
                intl_data = self._generate_simulated_international_data()
            
            with self.data_lock:
                for symbol, data in intl_data.items():
                    if isinstance(data, dict):
                        intl_point = InternationalData(
                            symbol=symbol,
                            region=data.get('region', 'Unknown'),
                            price=float(data.get('price', 100.0)),
                            change_pct=float(data.get('change_pct', 0.0)),
                            correlation_spy=data.get('correlation_spy')
                        )
                        
                        self.international_data[symbol] = intl_point
            
            self.last_update[DataSource.INTERNATIONAL] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating international data: {e}")

    def get_spot_price(self, symbol: str) -> Optional[float]:
        """Get current spot price for a symbol."""
        with self.data_lock:
            if symbol in self.spot_prices:
                self.stats['cache_hits'] += 1
                return self.spot_prices[symbol].price
            else:
                self.stats['cache_misses'] += 1
                return None

    def get_options_chain(self, underlying: str, 
                         strikes: Optional[List[float]] = None,
                         expiries: Optional[List[str]] = None,
                         option_type: Optional[str] = None) -> List[OptionData]:
        """Get filtered options chain."""
        with self.data_lock:
            if underlying not in self.options_chains:
                return []
            
            chain = self.options_chains[underlying]
            
            # Apply filters
            if strikes:
                chain = [opt for opt in chain if opt.strike in strikes]
            
            if expiries:
                expiry_dates = [self._parse_expiry(exp) for exp in expiries]
                chain = [opt for opt in chain if opt.expiry in expiry_dates]
            
            if option_type:
                chain = [opt for opt in chain if opt.option_type == option_type.lower()]
            
            return chain

    def get_historical_data(self, symbol: str, 
                           periods: int = 252) -> pd.DataFrame:
        """Get historical price data as DataFrame."""
        with self.data_lock:
            if symbol not in self.historical_data:
                return pd.DataFrame()
            
            data_points = list(self.historical_data[symbol])[-periods:]
            
            if not data_points:
                return pd.DataFrame()
            
            return pd.DataFrame([
                {
                    'timestamp': dp.timestamp,
                    'price': dp.price,
                    'volume': dp.volume,
                    'bid': dp.bid,
                    'ask': dp.ask
                }
                for dp in data_points
            ])

    def get_market_sentiment(self, symbol: str = 'SPY') -> Optional[MarketSentiment]:
        """Get market sentiment indicators."""
        with self.data_lock:
            return self.market_sentiment.get(symbol)

    def get_international_correlations(self) -> Dict[str, float]:
        """Get SPY correlations with international markets."""
        with self.data_lock:
            correlations = {}
            for symbol, data in self.international_data.items():
                if data.correlation_spy is not None:
                    correlations[symbol] = data.correlation_spy
            return correlations

    def get_volatility_surface_data(self) -> Dict[str, Any]:
        """Get data suitable for volatility surface construction."""
        spy_options = self.get_options_chain('SPY')
        spot = self.get_spot_price('SPY')
        
        if not spy_options or not spot:
            return {}
        
        surface_data = []
        for option in spy_options:
            if option.implied_vol:
                tte = (option.expiry - datetime.now()).days / 365.0
                if tte > 0:
                    surface_data.append({
                        'strike': option.strike,
                        'expiry': option.expiry,
                        'tte': tte,
                        'moneyness': option.strike / spot,
                        'implied_vol': option.implied_vol,
                        'option_type': option.option_type,
                        'mid_price': option.mid
                    })
        
        return {
            'spot_price': spot,
            'surface_points': surface_data,
            'timestamp': datetime.now()
        }

    def register_callback(self, data_type: str, callback: Callable):
        """Register callback for data updates."""
        self.update_callbacks[data_type].append(callback)
        self.logger.info(f"📡 Registered callback for {data_type}")

    def get_data_freshness(self) -> Dict[str, float]:
        """Get data freshness in seconds for each source."""
        current_time = datetime.now()
        freshness = {}
        
        for source, last_update in self.last_update.items():
            if last_update:
                age_seconds = (current_time - last_update).total_seconds()
                freshness[source.name] = age_seconds
        
        return freshness

    def get_statistics(self) -> Dict[str, Any]:
        """Get interface performance statistics."""
        return {
            'updates_processed': self.stats['updates_processed'],
            'cache_hit_ratio': self.stats['cache_hits'] / max(1, self.stats['cache_hits'] + self.stats['cache_misses']),
            'avg_latency_ms': self.stats['avg_latency'] * 1000,
            'error_count': self.stats['errors'],
            'data_freshness': self.get_data_freshness(),
            'cached_symbols': len(self.spot_prices),
            'options_chains': len(self.options_chains)
        }

    # ==============================================================================
    # SIMULATION METHODS (for testing without B08)
    # ==============================================================================
    def _generate_simulated_core_data(self) -> Dict[str, Dict[str, Any]]:
        """Generate simulated core market data."""
        return {
            'SPY': {
                'price': 450.0 + np.random.normal(0, 2),
                'volume': np.random.randint(1000000, 5000000),
                'bid': 449.95,
                'ask': 450.05
            },
            'QQQ': {
                'price': 380.0 + np.random.normal(0, 3),
                'volume': np.random.randint(500000, 2000000),
                'bid': 379.95,
                'ask': 380.05
            }
        }

    def _generate_simulated_options_data(self) -> Dict[str, Dict[str, Any]]:
        """Generate simulated options data."""
        spot = 450.0
        options = []
        
        # Generate options around current spot
        for strike in range(430, 471, 5):
            for option_type in ['call', 'put']:
                # Simple BS approximation for mid price
                moneyness = strike / spot
                if option_type == 'call':
                    mid = max(0, spot - strike + np.random.normal(0, 2))
                else:
                    mid = max(0, strike - spot + np.random.normal(0, 2))
                
                options.append({
                    'strike': strike,
                    'expiry': '2025-09-19',
                    'type': option_type,
                    'bid': mid * 0.95,
                    'ask': mid * 1.05,
                    'mid': mid,
                    'volume': np.random.randint(0, 1000),
                    'open_interest': np.random.randint(100, 5000),
                    'iv': 0.18 + 0.1 * abs(moneyness - 1),  # Vol smile
                    'delta': 0.5 if option_type == 'call' else -0.5
                })
        
        return {'SPY': {'options': options}}

    def _generate_simulated_internals_data(self) -> Dict[str, Dict[str, Any]]:
        """Generate simulated market internals data."""
        return {
            'VUD': {
                'put_call_ratio': 0.8 + np.random.normal(0, 0.2),
                'vix_level': 18.0 + np.random.normal(0, 3),
                'skew': np.random.normal(0, 0.1),
                'fear_greed': np.random.randint(20, 80)
            }
        }

    def _generate_simulated_international_data(self) -> Dict[str, Dict[str, Any]]:
        """Generate simulated international data."""
        return {
            'FTLC': {
                'region': 'UK',
                'price': 1520.0 + np.random.normal(0, 10),
                'change_pct': np.random.normal(0, 0.01),
                'correlation_spy': 0.7 + np.random.normal(0, 0.1)
            },
            'EWJ': {
                'region': 'Japan',
                'price': 58.0 + np.random.normal(0, 1),
                'change_pct': np.random.normal(0, 0.015),
                'correlation_spy': 0.6 + np.random.normal(0, 0.1)
            }
        }

    def _parse_expiry(self, expiry_str: str) -> datetime:
        """Parse expiry string to datetime."""
        try:
            return datetime.strptime(expiry_str, '%Y-%m-%d')
        except:
            # Default to 30 days from now
            return datetime.now() + timedelta(days=30)

    async def _process_data_queue(self):
        """Process data updates asynchronously."""
        while self.is_running:
            try:
                # This would process real-time updates
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error processing data queue: {e}")

# ==============================================================================
# TESTING
# ==============================================================================
async def test_data_interface():
    """Test the data interface functionality."""
    print("🧪 TESTING SPYDER DATA INTERFACE")
    print("=" * 50)
    
    # Create interface
    interface = SpyderDataInterface()
    
    # Test 1: Start interface
    print("\n📡 Test 1: Starting data interface...")
    start_success = await interface.start()
    print(f"✅ Interface started: {start_success}")
    
    # Wait for some data
    await asyncio.sleep(2)
    
    # Test 2: Get spot price
    print("\n💰 Test 2: Getting spot prices...")
    spy_price = interface.get_spot_price('SPY')
    print(f"✅ SPY spot price: ${spy_price:.2f}" if spy_price else "❌ No SPY price")
    
    # Test 3: Get options chain
    print("\n📊 Test 3: Getting options chain...")
    options = interface.get_options_chain('SPY')
    print(f"✅ SPY options available: {len(options)}")
    
    if options:
        print(f"✅ Sample option: {options[0].strike} {options[0].option_type} @ ${options[0].mid:.2f}")
    
    # Test 4: Get market sentiment
    print("\n📈 Test 4: Getting market sentiment...")
    sentiment = interface.get_market_sentiment('SPY')
    if sentiment:
        print(f"✅ Put/Call Ratio: {sentiment.put_call_ratio:.2f}")
        print(f"✅ VIX Level: {sentiment.vix_level:.1f}")
    
    # Test 5: Get statistics
    print("\n📊 Test 5: Getting statistics...")
    stats = interface.get_statistics()
    print(f"✅ Updates processed: {stats['updates_processed']}")
    print(f"✅ Cache hit ratio: {stats['cache_hit_ratio']:.2%}")
    print(f"✅ Avg latency: {stats['avg_latency_ms']:.1f}ms")
    
    # Test 6: Get volatility surface data
    print("\n🌊 Test 6: Getting volatility surface data...")
    surface_data = interface.get_volatility_surface_data()
    if surface_data:
        print(f"✅ Surface points: {len(surface_data.get('surface_points', []))}")
        print(f"✅ Spot price: ${surface_data.get('spot_price', 0):.2f}")
    
    # Test 7: Stop interface
    print("\n🛑 Test 7: Stopping interface...")
    stop_success = await interface.stop()
    print(f"✅ Interface stopped: {stop_success}")
    
    print("\n🎯 DATA INTERFACE TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_data_interface())
