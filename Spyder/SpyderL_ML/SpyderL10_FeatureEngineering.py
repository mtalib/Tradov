#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderL10_FeatureEngineering.py
Group: L (Machine Learning)
Purpose: Advanced feature engineering for ML models

Description:
    This module creates sophisticated features for machine learning models
    by combining price action, Greeks, volume profiles, market internals,
    and temporal patterns. It provides both real-time and historical
    feature extraction with caching for performance optimization.

Author: Mohamed Talib
Date: 2024-12-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import deque
import json
import pickle
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats
from scipy.signal import find_peaks
from sklearn.preprocessing import StandardScaler, RobustScaler
import talib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingCalendar
from Spyder.SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from Spyder.SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Feature categories
PRICE_FEATURES = [
    'returns_1m', 'returns_5m', 'returns_15m', 'returns_30m', 'returns_60m',
    'log_returns_5m', 'volatility_5m', 'volatility_15m', 'volatility_30m',
    'price_momentum', 'price_acceleration', 'price_efficiency',
    'high_low_range', 'close_to_high', 'close_to_low', 'body_size',
    'upper_shadow', 'lower_shadow', 'price_position_daily'
]

VOLUME_FEATURES = [
    'volume_ratio_5m', 'volume_ratio_15m', 'volume_ratio_30m',
    'volume_momentum', 'volume_concentration', 'large_trade_ratio',
    'buy_sell_imbalance', 'volume_weighted_price', 'volume_profile_poc'
]

GREEKS_FEATURES = [
    'atm_iv', 'iv_skew', 'iv_term_structure', 'put_call_iv_spread',
    'delta_exposure', 'gamma_exposure', 'vanna_exposure', 'charm_exposure',
    'weighted_delta', 'weighted_gamma', 'weighted_theta', 'weighted_vega',
    'max_pain_distance', 'gamma_flip_level'
]

MARKET_FEATURES = [
    'vix_level', 'vix_change', 'vix_percentile', 'term_structure',
    'put_call_ratio', 'put_call_volume', 'advance_decline',
    'tick_index', 'trin_index', 'market_breadth'
]

MICROSTRUCTURE_FEATURES = [
    'bid_ask_spread', 'spread_volatility', 'quote_intensity',
    'trade_intensity', 'order_flow_imbalance', 'effective_spread',
    'realized_spread', 'price_impact', 'liquidity_ratio'
]

TIME_FEATURES = [
    'hour_sin', 'hour_cos', 'minute_sin', 'minute_cos',
    'day_of_week', 'day_of_month', 'week_of_month', 'month_of_year',
    'is_opening_30m', 'is_closing_30m', 'is_lunch_hour',
    'time_to_expiry', 'is_expiry_day', 'is_fomc_day'
]

# Feature windows
FEATURE_WINDOWS = [1, 5, 15, 30, 60]  # minutes
LOOKBACK_PERIODS = [5, 10, 20, 50, 100]  # bars

# Cache settings
CACHE_SIZE = 10000
CACHE_TTL = 300  # 5 minutes

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FeatureSet:
    """Complete feature set for ML models"""
    timestamp: datetime
    symbol: str
    features: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_array(self, feature_names: List[str]) -> np.ndarray:
        """Convert to numpy array with specified features"""
        return np.array([self.features.get(name, np.nan) for name in feature_names])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'features': self.features,
            'metadata': self.metadata
        }

@dataclass
class FeatureConfig:
    """Feature engineering configuration"""
    price_features: bool = True
    volume_features: bool = True
    greeks_features: bool = True
    market_features: bool = True
    microstructure_features: bool = True
    time_features: bool = True
    
    # Advanced features
    pattern_features: bool = True
    regime_features: bool = True
    correlation_features: bool = True
    
    # Feature parameters
    normalize: bool = True
    handle_missing: str = 'forward_fill'  # 'forward_fill', 'interpolate', 'drop'
    outlier_method: str = 'clip'  # 'clip', 'remove', 'none'
    outlier_threshold: float = 3.0  # standard deviations

# ==============================================================================
# FEATURE ENGINEERING CLASS
# ==============================================================================
class FeatureEngineer:
    """
    Advanced feature engineering for options trading ML models.
    
    Creates hundreds of features from multiple data sources including
    price action, Greeks, volume, market internals, and microstructure.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """Initialize feature engineer"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or FeatureConfig()
        
        # Initialize components
        self.indicators = TechnicalIndicators()
        self.greeks_calc = GreeksCalculator()
        self.calendar = TradingCalendar()
        
        # Feature cache
        self.feature_cache = deque(maxlen=CACHE_SIZE)
        self.cache_index = {}  # timestamp -> cache position
        
        # Scalers for normalization
        self.scalers = {
            'standard': StandardScaler(),
            'robust': RobustScaler()
        }
        self.scaler_fitted = False
        
        # Feature statistics
        self.feature_stats = {}
        self.feature_importance = {}
        
        # Market data buffers
        self.price_buffer = deque(maxlen=max(LOOKBACK_PERIODS))
        self.volume_buffer = deque(maxlen=max(LOOKBACK_PERIODS))
        self.greeks_buffer = deque(maxlen=max(LOOKBACK_PERIODS))
        
        self.logger.info("FeatureEngineer initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def extract_features(
        self,
        market_data: Dict[str, Any],
        option_chain: Optional[Any] = None,
        market_internals: Optional[Dict[str, float]] = None
    ) -> FeatureSet:
        """
        Extract all features from current market data.
        
        Args:
            market_data: Current market data (price, volume, etc.)
            option_chain: Option chain data
            market_internals: Market internals (VIX, breadth, etc.)
            
        Returns:
            Complete feature set
        """
        try:
            timestamp = market_data.get('timestamp', datetime.now())
            
            # Check cache
            cached = self._get_cached_features(timestamp)
            if cached:
                return cached
            
            features = {}
            
            # Extract feature groups
            if self.config.price_features:
                features.update(self._extract_price_features(market_data))
            
            if self.config.volume_features:
                features.update(self._extract_volume_features(market_data))
            
            if self.config.greeks_features and option_chain:
                features.update(self._extract_greeks_features(option_chain))
            
            if self.config.market_features and market_internals:
                features.update(self._extract_market_features(market_internals))
            
            if self.config.microstructure_features:
                features.update(self._extract_microstructure_features(market_data))
            
            if self.config.time_features:
                features.update(self._extract_time_features(timestamp))
            
            # Advanced features
            if self.config.pattern_features:
                features.update(self._extract_pattern_features(market_data))
            
            if self.config.regime_features:
                features.update(self._extract_regime_features())
            
            if self.config.correlation_features:
                features.update(self._extract_correlation_features())
            
            # Handle missing values
            features = self._handle_missing_values(features)
            
            # Normalize if configured
            if self.config.normalize:
                features = self._normalize_features(features)
            
            # Create feature set
            feature_set = FeatureSet(
                timestamp=timestamp,
                symbol=market_data.get('symbol', 'SPY'),
                features=features,
                metadata={
                    'feature_count': len(features),
                    'extraction_time': datetime.now()
                }
            )
            
            # Cache features
            self._cache_features(feature_set)
            
            # Update buffers
            self._update_buffers(market_data, option_chain)
            
            return feature_set
            
        except Exception as e:
            self.logger.error(f"Error extracting features: {e}")
            self.error_handler.handle_error(e, "extract_features")
            return self._get_empty_feature_set(timestamp)
    
    def extract_features_batch(
        self,
        historical_data: pd.DataFrame,
        option_data: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Extract features for historical data batch.
        
        Args:
            historical_data: Historical price/volume data
            option_data: Historical option data
            
        Returns:
            DataFrame with all features
        """
        try:
            feature_list = []
            
            for idx, row in historical_data.iterrows():
                market_data = row.to_dict()
                market_data['timestamp'] = idx
                
                # Get corresponding option data if available
                option_chain = None
                if option_data is not None and idx in option_data.index:
                    option_chain = option_data.loc[idx]
                
                # Extract features
                feature_set = self.extract_features(market_data, option_chain)
                
                # Add to list
                features_dict = feature_set.features.copy()
                features_dict['timestamp'] = feature_set.timestamp
                feature_list.append(features_dict)
            
            # Convert to DataFrame
            features_df = pd.DataFrame(feature_list)
            features_df.set_index('timestamp', inplace=True)
            
            # Calculate rolling features
            features_df = self._add_rolling_features(features_df)
            
            # Calculate feature statistics
            self._calculate_feature_statistics(features_df)
            
            return features_df
            
        except Exception as e:
            self.logger.error(f"Error in batch feature extraction: {e}")
            return pd.DataFrame()
    
    # ==========================================================================
    # PRICE FEATURES
    # ==========================================================================
    def _extract_price_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract price-based features"""
        features = {}
        
        try:
            price = market_data.get('close', 0)
            open_price = market_data.get('open', price)
            high = market_data.get('high', price)
            low = market_data.get('low', price)
            
            # Returns at different intervals
            if len(self.price_buffer) > 0:
                for window in FEATURE_WINDOWS:
                    if len(self.price_buffer) >= window:
                        past_price = self.price_buffer[-window]['close']
                        features[f'returns_{window}m'] = (price - past_price) / past_price
                        features[f'log_returns_{window}m'] = np.log(price / past_price)
            
            # Volatility estimates
            if len(self.price_buffer) >= 20:
                returns = [self.price_buffer[i]['close'] / self.price_buffer[i-1]['close'] - 1 
                          for i in range(1, len(self.price_buffer))]
                
                features['volatility_5m'] = np.std(returns[-5:]) * np.sqrt(252 * 78)  # Annualized
                features['volatility_15m'] = np.std(returns[-15:]) * np.sqrt(252 * 26)
                features['volatility_30m'] = np.std(returns) * np.sqrt(252 * 13)
            
            # Price momentum and acceleration
            if len(self.price_buffer) >= 10:
                prices = [p['close'] for p in self.price_buffer]
                features['price_momentum'] = (prices[-1] - prices[-5]) / prices[-5]
                features['price_acceleration'] = (
                    (prices[-1] - prices[-5]) - (prices[-5] - prices[-10])
                ) / prices[-10]
            
            # Price efficiency (deviation from linear trend)
            if len(self.price_buffer) >= 20:
                prices = np.array([p['close'] for p in self.price_buffer[-20:]])
                x = np.arange(len(prices))
                slope, intercept = np.polyfit(x, prices, 1)
                predicted = slope * x + intercept
                features['price_efficiency'] = 1 - np.std(prices - predicted) / np.std(prices)
            
            # Candlestick features
            features['high_low_range'] = (high - low) / price
            features['close_to_high'] = (high - price) / (high - low) if high > low else 0.5
            features['close_to_low'] = (price - low) / (high - low) if high > low else 0.5
            features['body_size'] = abs(price - open_price) / price
            features['upper_shadow'] = (high - max(price, open_price)) / price
            features['lower_shadow'] = (min(price, open_price) - low) / price
            
            # Price position in daily range
            if len(self.price_buffer) >= 78:  # Full trading day
                daily_high = max(p['high'] for p in self.price_buffer[-78:])
                daily_low = min(p['low'] for p in self.price_buffer[-78:])
                features['price_position_daily'] = (
                    (price - daily_low) / (daily_high - daily_low) 
                    if daily_high > daily_low else 0.5
                )
            
            # Technical indicators
            if len(self.price_buffer) >= 20:
                prices_series = pd.Series([p['close'] for p in self.price_buffer])
                
                # RSI
                features['rsi_14'] = self.indicators.rsi(prices_series, period=14).iloc[-1]
                
                # MACD
                macd_result = self.indicators.macd(prices_series)
                features['macd_signal'] = (
                    macd_result['macd'].iloc[-1] - macd_result['signal'].iloc[-1]
                )
                features['macd_histogram'] = macd_result['histogram'].iloc[-1]
                
                # Bollinger Bands
                bb_result = self.indicators.bollinger_bands(prices_series, period=20)
                features['bb_position'] = (
                    (price - bb_result['lower'].iloc[-1]) / 
                    (bb_result['upper'].iloc[-1] - bb_result['lower'].iloc[-1])
                )
                features['bb_width'] = (
                    (bb_result['upper'].iloc[-1] - bb_result['lower'].iloc[-1]) / 
                    bb_result['middle'].iloc[-1]
                )
            
            # Support/Resistance levels
            if len(self.price_buffer) >= 50:
                prices = [p['high'] for p in self.price_buffer[-50:]]
                lows = [p['low'] for p in self.price_buffer[-50:]]
                
                # Find peaks and troughs
                peaks, _ = find_peaks(prices, distance=5)
                troughs, _ = find_peaks([-p for p in lows], distance=5)
                
                if len(peaks) > 0:
                    nearest_resistance = min(prices[p] for p in peaks if prices[p] > price)
                    features['distance_to_resistance'] = (nearest_resistance - price) / price
                
                if len(troughs) > 0:
                    nearest_support = max(lows[t] for t in troughs if lows[t] < price)
                    features['distance_to_support'] = (price - nearest_support) / price
                
        except Exception as e:
            self.logger.error(f"Error extracting price features: {e}")
        
        return features
    
    # ==========================================================================
    # VOLUME FEATURES
    # ==========================================================================
    def _extract_volume_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract volume-based features"""
        features = {}
        
        try:
            volume = market_data.get('volume', 0)
            
            # Volume ratios
            if len(self.volume_buffer) >= 20:
                volumes = [v['volume'] for v in self.volume_buffer]
                avg_volume_5m = np.mean(volumes[-5:])
                avg_volume_15m = np.mean(volumes[-15:])
                avg_volume_30m = np.mean(volumes)
                
                features['volume_ratio_5m'] = volume / avg_volume_5m if avg_volume_5m > 0 else 1
                features['volume_ratio_15m'] = volume / avg_volume_15m if avg_volume_15m > 0 else 1
                features['volume_ratio_30m'] = volume / avg_volume_30m if avg_volume_30m > 0 else 1
                
                # Volume momentum
                features['volume_momentum'] = (
                    (avg_volume_5m - avg_volume_15m) / avg_volume_15m 
                    if avg_volume_15m > 0 else 0
                )
            
            # Volume concentration (how much volume in recent bars)
            if len(self.volume_buffer) >= 10:
                recent_volume = sum(v['volume'] for v in self.volume_buffer[-3:])
                total_volume = sum(v['volume'] for v in self.volume_buffer[-10:])
                features['volume_concentration'] = (
                    recent_volume / total_volume if total_volume > 0 else 0.3
                )
            
            # Large trade detection
            if 'trade_count' in market_data and market_data['trade_count'] > 0:
                avg_trade_size = volume / market_data['trade_count']
                features['avg_trade_size'] = avg_trade_size
                
                # Estimate large trades (>2x average)
                if len(self.volume_buffer) >= 20:
                    historical_avg = np.mean([
                        v['volume'] / v.get('trade_count', 1) 
                        for v in self.volume_buffer if v.get('trade_count', 0) > 0
                    ])
                    features['large_trade_ratio'] = avg_trade_size / historical_avg
            
            # Buy/Sell imbalance (if tick data available)
            if 'buy_volume' in market_data and 'sell_volume' in market_data:
                total_directed = market_data['buy_volume'] + market_data['sell_volume']
                if total_directed > 0:
                    features['buy_sell_imbalance'] = (
                        (market_data['buy_volume'] - market_data['sell_volume']) / total_directed
                    )
            
            # Volume-weighted price
            if len(self.price_buffer) >= 10:
                vwap_sum = sum(
                    p['close'] * p['volume'] 
                    for p in self.price_buffer[-10:] 
                    if 'volume' in p
                )
                volume_sum = sum(
                    p['volume'] 
                    for p in self.price_buffer[-10:] 
                    if 'volume' in p
                )
                if volume_sum > 0:
                    vwap = vwap_sum / volume_sum
                    current_price = market_data.get('close', 0)
                    features['price_to_vwap'] = current_price / vwap if vwap > 0 else 1
            
            # On-Balance Volume trend
            if len(self.price_buffer) >= 20:
                obv_values = []
                obv = 0
                for i in range(1, len(self.price_buffer)):
                    if self.price_buffer[i]['close'] > self.price_buffer[i-1]['close']:
                        obv += self.price_buffer[i]['volume']
                    elif self.price_buffer[i]['close'] < self.price_buffer[i-1]['close']:
                        obv -= self.price_buffer[i]['volume']
                    obv_values.append(obv)
                
                if len(obv_values) >= 10:
                    # OBV trend (linear regression slope)
                    x = np.arange(len(obv_values[-10:]))
                    slope, _ = np.polyfit(x, obv_values[-10:], 1)
                    features['obv_trend'] = slope
            
        except Exception as e:
            self.logger.error(f"Error extracting volume features: {e}")
        
        return features
    
    # ==========================================================================
    # GREEKS FEATURES
    # ==========================================================================
    def _extract_greeks_features(self, option_chain: Any) -> Dict[str, float]:
        """Extract Greeks-based features"""
        features = {}
        
        try:
            # ATM implied volatility
            atm_call = option_chain.get_atm_option('CALL')
            atm_put = option_chain.get_atm_option('PUT')
            
            if atm_call and atm_put:
                features['atm_iv'] = (atm_call.implied_volatility + atm_put.implied_volatility) / 2
                features['put_call_iv_spread'] = atm_put.implied_volatility - atm_call.implied_volatility
            
            # IV skew (25-delta put IV - 25-delta call IV)
            put_25d = option_chain.get_option_by_delta(-0.25, 'PUT')
            call_25d = option_chain.get_option_by_delta(0.25, 'CALL')
            
            if put_25d and call_25d:
                features['iv_skew'] = put_25d.implied_volatility - call_25d.implied_volatility
            
            # Term structure (front month vs back month IV)
            if hasattr(option_chain, 'get_term_structure'):
                term_structure = option_chain.get_term_structure()
                if len(term_structure) >= 2:
                    features['iv_term_structure'] = (
                        term_structure[1]['iv'] - term_structure[0]['iv']
                    )
            
            # Greeks exposure
            all_options = option_chain.get_all_options()
            
            total_delta = sum(opt.delta * opt.open_interest for opt in all_options)
            total_gamma = sum(opt.gamma * opt.open_interest for opt in all_options)
            total_vanna = sum(opt.vanna * opt.open_interest for opt in all_options)
            total_charm = sum(opt.charm * opt.open_interest for opt in all_options)
            
            features['delta_exposure'] = total_delta / 1000  # Normalize
            features['gamma_exposure'] = total_gamma / 1000
            features['vanna_exposure'] = total_vanna / 1000
            features['charm_exposure'] = total_charm / 1000
            
            # Weighted Greeks (by volume)
            total_volume = sum(opt.volume for opt in all_options if opt.volume > 0)
            
            if total_volume > 0:
                features['weighted_delta'] = sum(
                    opt.delta * opt.volume / total_volume 
                    for opt in all_options if opt.volume > 0
                )
                features['weighted_gamma'] = sum(
                    opt.gamma * opt.volume / total_volume 
                    for opt in all_options if opt.volume > 0
                )
                features['weighted_theta'] = sum(
                    opt.theta * opt.volume / total_volume 
                    for opt in all_options if opt.volume > 0
                )
                features['weighted_vega'] = sum(
                    opt.vega * opt.volume / total_volume 
                    for opt in all_options if opt.volume > 0
                )
            
            # Max pain analysis
            max_pain = option_chain.calculate_max_pain()
            current_price = option_chain.underlying_price
            
            if max_pain and current_price:
                features['max_pain_distance'] = (current_price - max_pain) / current_price
            
            # Gamma flip level (where gamma exposure changes sign)
            gamma_profile = option_chain.get_gamma_profile()
            if gamma_profile:
                # Find zero crossing
                for i in range(1, len(gamma_profile)):
                    if gamma_profile[i-1]['gamma'] * gamma_profile[i]['gamma'] < 0:
                        gamma_flip = gamma_profile[i]['strike']
                        features['gamma_flip_distance'] = (
                            (current_price - gamma_flip) / current_price
                        )
                        break
            
            # Put/Call ratios
            features['put_call_oi_ratio'] = option_chain.put_call_oi_ratio
            features['put_call_volume_ratio'] = option_chain.put_call_volume_ratio
            
            # IV percentile
            if len(self.greeks_buffer) >= 20:
                historical_ivs = [g.get('atm_iv', 0) for g in self.greeks_buffer]
                current_iv = features.get('atm_iv', 0)
                if historical_ivs and current_iv:
                    features['iv_percentile'] = stats.percentileofscore(historical_ivs, current_iv) / 100
            
        except Exception as e:
            self.logger.error(f"Error extracting Greeks features: {e}")
        
        return features
    
    # ==========================================================================
    # MARKET INTERNALS FEATURES
    # ==========================================================================
    def _extract_market_features(self, market_internals: Dict[str, float]) -> Dict[str, float]:
        """Extract market internals features"""
        features = {}
        
        try:
            # VIX features
            vix = market_internals.get('VIX', 16)
            features['vix_level'] = vix
            
            if len(self.greeks_buffer) >= 5:
                vix_5m_ago = self.greeks_buffer[-5].get('vix', vix)
                features['vix_change_5m'] = (vix - vix_5m_ago) / vix_5m_ago
            
            # VIX percentile
            if len(self.greeks_buffer) >= 100:
                historical_vix = [g.get('vix', 16) for g in self.greeks_buffer]
                features['vix_percentile'] = stats.percentileofscore(historical_vix, vix) / 100
            
            # Term structure (VIX vs VIX3M)
            vix3m = market_internals.get('VIX3M', vix * 1.1)
            features['vix_term_structure'] = (vix3m - vix) / vix
            
            # Market breadth
            features['advance_decline'] = market_internals.get('advance_decline_ratio', 1.0)
            features['percent_above_ma'] = market_internals.get('percent_above_50ma', 0.5)
            
            # TICK index
            tick = market_internals.get('TICK', 0)
            features['tick_index'] = tick / 1000  # Normalize
            
            # TRIN (Arms Index)
            features['trin_index'] = market_internals.get('TRIN', 1.0)
            
            # High-Low index
            new_highs = market_internals.get('new_highs', 100)
            new_lows = market_internals.get('new_lows', 100)
            features['high_low_ratio'] = new_highs / (new_highs + new_lows) if (new_highs + new_lows) > 0 else 0.5
            
            # McClellan Oscillator
            features['mcclellan_oscillator'] = market_internals.get('mcclellan', 0) / 100
            
            # Put/Call ratio
            features['equity_put_call'] = market_internals.get('equity_put_call_ratio', 0.7)
            features['index_put_call'] = market_internals.get('index_put_call_ratio', 1.2)
            
            # Volume indicators
            features['up_volume_ratio'] = market_internals.get('up_volume_ratio', 0.5)
            features['volume_thrust'] = market_internals.get('volume_thrust', 0)
            
        except Exception as e:
            self.logger.error(f"Error extracting market features: {e}")
        
        return features
    
    # ==========================================================================
    # MICROSTRUCTURE FEATURES
    # ==========================================================================
    def _extract_microstructure_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract market microstructure features"""
        features = {}
        
        try:
            bid = market_data.get('bid', 0)
            ask = market_data.get('ask', 0)
            price = market_data.get('close', (bid + ask) / 2)
            
            # Bid-ask spread
            if bid > 0 and ask > 0:
                features['bid_ask_spread'] = (ask - bid) / price
                features['bid_ask_midpoint'] = (bid + ask) / 2
                
                # Spread volatility
                if len(self.price_buffer) >= 10:
                    spreads = [
                        (p.get('ask', 0) - p.get('bid', 0)) / p.get('close', 1)
                        for p in self.price_buffer[-10:]
                        if p.get('bid', 0) > 0 and p.get('ask', 0) > 0
                    ]
                    if spreads:
                        features['spread_volatility'] = np.std(spreads)
            
            # Quote intensity
            quote_count = market_data.get('quote_count', 0)
            features['quote_intensity'] = quote_count / 60  # Per second
            
            # Trade intensity
            trade_count = market_data.get('trade_count', 0)
            features['trade_intensity'] = trade_count / 60  # Per second
            
            # Order flow imbalance
            bid_volume = market_data.get('bid_volume', 0)
            ask_volume = market_data.get('ask_volume', 0)
            total_quote_volume = bid_volume + ask_volume
            
            if total_quote_volume > 0:
                features['order_flow_imbalance'] = (bid_volume - ask_volume) / total_quote_volume
            
            # Effective spread (if trade data available)
            if 'trade_price' in market_data and bid > 0 and ask > 0:
                trade_price = market_data['trade_price']
                midpoint = (bid + ask) / 2
                features['effective_spread'] = 2 * abs(trade_price - midpoint) / midpoint
            
            # Price impact (temporary)
            if len(self.price_buffer) >= 3 and 'trade_price' in market_data:
                pre_trade_mid = (self.price_buffer[-2].get('bid', 0) + self.price_buffer[-2].get('ask', 0)) / 2
                post_trade_mid = (bid + ask) / 2
                if pre_trade_mid > 0:
                    features['price_impact'] = (post_trade_mid - pre_trade_mid) / pre_trade_mid
            
            # Liquidity ratio (volume / spread)
            if features.get('bid_ask_spread', 0) > 0:
                features['liquidity_ratio'] = market_data.get('volume', 0) / features['bid_ask_spread']
            
            # Kyle's lambda (if order flow data available)
            if len(self.price_buffer) >= 20 and 'net_order_flow' in market_data:
                price_changes = [
                    self.price_buffer[i]['close'] / self.price_buffer[i-1]['close'] - 1
                    for i in range(1, len(self.price_buffer))
                ]
                order_flows = [
                    p.get('net_order_flow', 0) 
                    for p in self.price_buffer[1:]
                ]
                
                if len(price_changes) == len(order_flows) and np.std(order_flows) > 0:
                    # Simple regression
                    kyle_lambda = np.cov(price_changes, order_flows)[0, 1] / np.var(order_flows)
                    features['kyle_lambda'] = kyle_lambda
            
        except Exception as e:
            self.logger.error(f"Error extracting microstructure features: {e}")
        
        return features
    
    # ==========================================================================
    # TIME FEATURES
    # ==========================================================================
    def _extract_time_features(self, timestamp: datetime) -> Dict[str, float]:
        """Extract time-based features"""
        features = {}
        
        try:
            # Cyclical encoding of time
            hour = timestamp.hour + timestamp.minute / 60
            features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
            features['hour_cos'] = np.cos(2 * np.pi * hour / 24)
            
            minute = timestamp.minute
            features['minute_sin'] = np.sin(2 * np.pi * minute / 60)
            features['minute_cos'] = np.cos(2 * np.pi * minute / 60)
            
            # Day features
            features['day_of_week'] = timestamp.weekday() / 4  # Normalize to [0,1]
            features['day_of_month'] = timestamp.day / 31
            features['week_of_month'] = (timestamp.day - 1) // 7 / 4
            features['month_of_year'] = timestamp.month / 12
            
            # Trading session features
            market_open = timestamp.replace(hour=9, minute=30)
            market_close = timestamp.replace(hour=16, minute=0)
            
            features['is_opening_30m'] = 1 if timestamp <= market_open + timedelta(minutes=30) else 0
            features['is_closing_30m'] = 1 if timestamp >= market_close - timedelta(minutes=30) else 0
            features['is_lunch_hour'] = 1 if 12 <= timestamp.hour < 13 else 0
            
            # Time since market open
            if timestamp >= market_open:
                minutes_since_open = (timestamp - market_open).total_seconds() / 60
                features['time_since_open'] = minutes_since_open / 390  # Normalize by trading day
            
            # Options expiry features
            next_expiry = self.calendar.get_next_expiry(timestamp)
            if next_expiry:
                days_to_expiry = (next_expiry - timestamp.date()).days
                features['days_to_expiry'] = days_to_expiry / 30  # Normalize by month
                features['is_expiry_week'] = 1 if days_to_expiry <= 5 else 0
                features['is_expiry_day'] = 1 if days_to_expiry == 0 else 0
            
            # Economic events
            features['is_fomc_day'] = 1 if self.calendar.is_fomc_day(timestamp.date()) else 0
            features['is_jobs_day'] = 1 if self.calendar.is_jobs_report_day(timestamp.date()) else 0
            features['is_cpi_day'] = 1 if self.calendar.is_cpi_day(timestamp.date()) else 0
            
            # Holiday effects
            features['days_to_holiday'] = self.calendar.days_to_next_holiday(timestamp.date()) / 30
            
            # Quarter-end effects
            features['is_quarter_end'] = 1 if timestamp.month in [3, 6, 9, 12] and timestamp.day >= 25 else 0
            features['is_month_end'] = 1 if timestamp.day >= 25 else 0
            
        except Exception as e:
            self.logger.error(f"Error extracting time features: {e}")
        
        return features
    
    # ==========================================================================
    # PATTERN FEATURES
    # ==========================================================================
    def _extract_pattern_features(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract price pattern features"""
        features = {}
        
        try:
            if len(self.price_buffer) < 20:
                return features
            
            prices = [p['close'] for p in self.price_buffer]
            highs = [p['high'] for p in self.price_buffer]
            lows = [p['low'] for p in self.price_buffer]
            
            # Trend strength (R-squared of linear fit)
            x = np.arange(len(prices))
            slope, intercept = np.polyfit(x, prices, 1)
            predicted = slope * x + intercept
            ss_res = np.sum((prices - predicted) ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            features['trend_strength'] = r_squared
            features['trend_slope'] = slope / prices[-1]  # Normalize
            
            # Channel detection
            upper_slope, upper_intercept = np.polyfit(x, highs, 1)
            lower_slope, lower_intercept = np.polyfit(x, lows, 1)
            
            channel_width = np.mean([highs[i] - lows[i] for i in range(len(highs))])
            current_channel_pos = (prices[-1] - (lower_slope * x[-1] + lower_intercept)) / channel_width
            
            features['channel_position'] = np.clip(current_channel_pos, 0, 1)
            features['channel_slope_diff'] = (upper_slope - lower_slope) / prices[-1]
            
            # Breakout detection
            recent_high = max(highs[-10:])
            recent_low = min(lows[-10:])
            prior_high = max(highs[-20:-10])
            prior_low = min(lows[-20:-10])
            
            features['breakout_up'] = 1 if prices[-1] > prior_high else 0
            features['breakout_down'] = 1 if prices[-1] < prior_low else 0
            features['near_resistance'] = 1 if (recent_high - prices[-1]) / prices[-1] < 0.002 else 0
            features['near_support'] = 1 if (prices[-1] - recent_low) / prices[-1] < 0.002 else 0
            
            # Pattern recognition (simplified)
            # Double top/bottom
            peaks, _ = find_peaks(prices, distance=5)
            troughs, _ = find_peaks([-p for p in prices], distance=5)
            
            if len(peaks) >= 2:
                last_two_peaks = [prices[p] for p in peaks[-2:]]
                if abs(last_two_peaks[0] - last_two_peaks[1]) / last_two_peaks[0] < 0.01:
                    features['double_top'] = 1
                else:
                    features['double_top'] = 0
            
            # Head and shoulders (simplified)
            if len(peaks) >= 3:
                last_three_peaks = [prices[p] for p in peaks[-3:]]
                if (last_three_peaks[1] > last_three_peaks[0] and 
                    last_three_peaks[1] > last_three_peaks[2]):
                    features['head_shoulders'] = 1
                else:
                    features['head_shoulders'] = 0
            
            # Flag/Pennant detection
            if len(prices) >= 30:
                # Strong move followed by consolidation
                move_period = prices[-30:-15]
                consolidation_period = prices[-15:]
                
                move_return = (move_period[-1] - move_period[0]) / move_period[0]
                consolidation_vol = np.std(consolidation_period) / np.mean(consolidation_period)
                
                if abs(move_return) > 0.02 and consolidation_vol < 0.005:
                    features['flag_pattern'] = np.sign(move_return)
                else:
                    features['flag_pattern'] = 0
            
        except Exception as e:
            self.logger.error(f"Error extracting pattern features: {e}")
        
        return features
    
    # ==========================================================================
    # REGIME FEATURES
    # ==========================================================================
    def _extract_regime_features(self) -> Dict[str, float]:
        """Extract market regime features"""
        features = {}
        
        try:
            if len(self.price_buffer) < 50:
                return features
            
            prices = [p['close'] for p in self.price_buffer]
            returns = np.diff(prices) / prices[:-1]
            
            # Volatility regime
            short_vol = np.std(returns[-10:]) * np.sqrt(252 * 78)
            long_vol = np.std(returns[-30:]) * np.sqrt(252 * 78)
            
            features['vol_regime_expanding'] = 1 if short_vol > long_vol * 1.2 else 0
            features['vol_regime_contracting'] = 1 if short_vol < long_vol * 0.8 else 0
            features['vol_regime_level'] = short_vol
            
            # Trend regime
            sma_10 = np.mean(prices[-10:])
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:])
            
            features['trend_regime_strong_up'] = 1 if sma_10 > sma_20 > sma_50 else 0
            features['trend_regime_strong_down'] = 1 if sma_10 < sma_20 < sma_50 else 0
            features['trend_regime_choppy'] = 1 if abs(sma_10 - sma_50) / sma_50 < 0.01 else 0
            
            # Mean reversion vs trending
            # Hurst exponent approximation
            if len(returns) >= 40:
                lags = range(2, 20)
                tau = []
                
                for lag in lags:
                    pp = np.sqrt(np.std(np.subtract(returns[lag:], returns[:-lag])))
                    tau.append(pp)
                
                reg = np.polyfit(np.log(lags), np.log(tau), 1)
                hurst = reg[0] * 2
                
                features['hurst_exponent'] = hurst
                features['mean_reverting'] = 1 if hurst < 0.4 else 0
                features['trending'] = 1 if hurst > 0.6 else 0
            
            # Correlation regime
            if len(self.greeks_buffer) >= 20:
                # SPY-VIX correlation
                spy_returns = returns[-20:]
                vix_values = [g.get('vix', 16) for g in self.greeks_buffer[-21:]]
                vix_returns = np.diff(vix_values) / vix_values[:-1]
                
                if len(spy_returns) == len(vix_returns):
                    correlation = np.corrcoef(spy_returns, vix_returns)[0, 1]
                    features['spy_vix_correlation'] = correlation
                    features['correlation_regime_normal'] = 1 if correlation < -0.5 else 0
            
        except Exception as e:
            self.logger.error(f"Error extracting regime features: {e}")
        
        return features
    
    # ==========================================================================
    # CORRELATION FEATURES
    # ==========================================================================
    def _extract_correlation_features(self) -> Dict[str, float]:
        """Extract correlation-based features"""
        features = {}
        
        try:
            if len(self.price_buffer) < 20:
                return features
            
            # Get various time series
            prices = [p['close'] for p in self.price_buffer[-20:]]
            volumes = [p['volume'] for p in self.price_buffer[-20:]]
            
            price_returns = np.diff(prices) / prices[:-1]
            volume_changes = np.diff(volumes) / np.array(volumes[:-1])
            
            # Price-volume correlation
            if len(price_returns) == len(volume_changes):
                features['price_volume_corr'] = np.corrcoef(price_returns, volume_changes)[0, 1]
            
            # Auto-correlations
            if len(price_returns) >= 10:
                features['returns_autocorr_1'] = np.corrcoef(price_returns[:-1], price_returns[1:])[0, 1]
                features['returns_autocorr_5'] = np.corrcoef(price_returns[:-5], price_returns[5:])[0, 1]
                
                # Volume autocorrelation
                features['volume_autocorr_1'] = np.corrcoef(volumes[:-1], volumes[1:])[0, 1]
            
            # Cross-asset correlations (if available)
            if hasattr(self, 'market_data') and 'sector_returns' in self.market_data:
                spy_returns = price_returns
                
                for sector, sector_returns in self.market_data['sector_returns'].items():
                    if len(sector_returns) == len(spy_returns):
                        features[f'{sector}_correlation'] = np.corrcoef(spy_returns, sector_returns)[0, 1]
            
            # Rolling correlation stability
            if len(price_returns) >= 15:
                corr_5 = np.corrcoef(price_returns[-10:-5], volume_changes[-10:-5])[0, 1]
                corr_10 = np.corrcoef(price_returns[-15:-10], volume_changes[-15:-10])[0, 1]
                features['correlation_stability'] = 1 - abs(corr_5 - corr_10)
            
        except Exception as e:
            self.logger.error(f"Error extracting correlation features: {e}")
        
        return features
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _handle_missing_values(self, features: Dict[str, float]) -> Dict[str, float]:
        """Handle missing values in features"""
        if self.config.handle_missing == 'forward_fill':
            # Use last known values
            for key, value in features.items():
                if np.isnan(value) or np.isinf(value):
                    # Try to get from cache
                    if self.feature_cache:
                        for cached_set in reversed(self.feature_cache):
                            if key in cached_set.features and not np.isnan(cached_set.features[key]):
                                features[key] = cached_set.features[key]
                                break
                        else:
                            features[key] = 0  # Default
                    else:
                        features[key] = 0
        
        elif self.config.handle_missing == 'interpolate':
            # Linear interpolation (simplified)
            for key, value in features.items():
                if np.isnan(value) or np.isinf(value):
                    features[key] = 0  # Simplified
        
        elif self.config.handle_missing == 'drop':
            # Remove features with missing values
            features = {k: v for k, v in features.items() if not (np.isnan(v) or np.isinf(v))}
        
        return features
    
    def _normalize_features(self, features: Dict[str, float]) -> Dict[str, float]:
        """Normalize features"""
        # Convert to array for scaling
        feature_names = sorted(features.keys())
        feature_array = np.array([features[name] for name in feature_names]).reshape(1, -1)
        
        # Fit scaler if needed
        if not self.scaler_fitted and len(self.feature_cache) > 100:
            # Collect historical features
            historical_features = []
            for cached_set in self.feature_cache:
                hist_array = [cached_set.features.get(name, 0) for name in feature_names]
                historical_features.append(hist_array)
            
            historical_array = np.array(historical_features)
            self.scalers['robust'].fit(historical_array)
            self.scaler_fitted = True
        
        # Scale features
        if self.scaler_fitted:
            scaled_array = self.scalers['robust'].transform(feature_array)[0]
            features = {name: scaled_array[i] for i, name in enumerate(feature_names)}
        
        # Clip outliers
        if self.config.outlier_method == 'clip':
            for key, value in features.items():
                features[key] = np.clip(value, -self.config.outlier_threshold, self.config.outlier_threshold)
        
        return features
    
    def _add_rolling_features(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Add rolling window features"""
        # Rolling statistics
        for col in features_df.select_dtypes(include=[np.number]).columns:
            # Skip if column has too many NaN values
            if features_df[col].notna().sum() < 20:
                continue
            
            # Rolling mean and std
            features_df[f'{col}_roll_mean_5'] = features_df[col].rolling(5).mean()
            features_df[f'{col}_roll_std_5'] = features_df[col].rolling(5).std()
            
            # Rolling z-score
            roll_mean = features_df[col].rolling(20).mean()
            roll_std = features_df[col].rolling(20).std()
            features_df[f'{col}_zscore'] = (features_df[col] - roll_mean) / roll_std
            
            # Exponential moving averages
            features_df[f'{col}_ema_5'] = features_df[col].ewm(span=5).mean()
            features_df[f'{col}_ema_20'] = features_df[col].ewm(span=20).mean()
        
        return features_df
    
    def _calculate_feature_statistics(self, features_df: pd.DataFrame) -> None:
        """Calculate and store feature statistics"""
        self.feature_stats = {
            'mean': features_df.mean().to_dict(),
            'std': features_df.std().to_dict(),
            'min': features_df.min().to_dict(),
            'max': features_df.max().to_dict(),
            'quantiles': {
                '25%': features_df.quantile(0.25).to_dict(),
                '50%': features_df.quantile(0.50).to_dict(),
                '75%': features_df.quantile(0.75).to_dict()
            }
        }
    
    def _update_buffers(self, market_data: Dict[str, Any], option_chain: Any) -> None:
        """Update internal data buffers"""
        # Update price buffer
        self.price_buffer.append({
            'timestamp': market_data.get('timestamp', datetime.now()),
            'open': market_data.get('open', 0),
            'high': market_data.get('high', 0),
            'low': market_data.get('low', 0),
            'close': market_data.get('close', 0),
            'volume': market_data.get('volume', 0),
            'bid': market_data.get('bid', 0),
            'ask': market_data.get('ask', 0)
        })
        
        # Update volume buffer
        self.volume_buffer.append({
            'timestamp': market_data.get('timestamp', datetime.now()),
            'volume': market_data.get('volume', 0),
            'trade_count': market_data.get('trade_count', 0),
            'buy_volume': market_data.get('buy_volume', 0),
            'sell_volume': market_data.get('sell_volume', 0)
        })
        
        # Update Greeks buffer
        if option_chain:
            greeks_data = {
                'timestamp': market_data.get('timestamp', datetime.now()),
                'atm_iv': getattr(option_chain, 'atm_iv', 0),
                'vix': market_data.get('vix', 16),
                'put_call_ratio': getattr(option_chain, 'put_call_volume_ratio', 1)
            }
            self.greeks_buffer.append(greeks_data)
    
    def _cache_features(self, feature_set: FeatureSet) -> None:
        """Cache extracted features"""
        self.feature_cache.append(feature_set)
        self.cache_index[feature_set.timestamp] = len(self.feature_cache) - 1
    
    def _get_cached_features(self, timestamp: datetime) -> Optional[FeatureSet]:
        """Get features from cache"""
        if timestamp in self.cache_index:
            idx = self.cache_index[timestamp]
            if 0 <= idx < len(self.feature_cache):
                cached = self.feature_cache[idx]
                # Check TTL
                if (datetime.now() - cached.metadata['extraction_time']).seconds < CACHE_TTL:
                    return cached
        return None
    
    def _get_empty_feature_set(self, timestamp: datetime) -> FeatureSet:
        """Get empty feature set for error cases"""
        empty_features = {name: 0.0 for name in PRICE_FEATURES + VOLUME_FEATURES + 
                         GREEKS_FEATURES + MARKET_FEATURES + MICROSTRUCTURE_FEATURES + TIME_FEATURES}
        
        return FeatureSet(
            timestamp=timestamp,
            symbol='SPY',
            features=empty_features,
            metadata={'error': True}
        )
    
    # ==========================================================================
    # FEATURE SELECTION AND IMPORTANCE
    # ==========================================================================
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores"""
        return self.feature_importance.copy()
    
    def set_feature_importance(self, importance_scores: Dict[str, float]) -> None:
        """Set feature importance from ML model"""
        self.feature_importance = importance_scores
    
    def get_top_features(self, n: int = 50) -> List[str]:
        """Get top N most important features"""
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [f[0] for f in sorted_features[:n]]
    
    def get_feature_names(self) -> List[str]:
        """Get all available feature names"""
        all_features = []
        
        if self.config.price_features:
            all_features.extend(PRICE_FEATURES)
        if self.config.volume_features:
            all_features.extend(VOLUME_FEATURES)
        if self.config.greeks_features:
            all_features.extend(GREEKS_FEATURES)
        if self.config.market_features:
            all_features.extend(MARKET_FEATURES)
        if self.config.microstructure_features:
            all_features.extend(MICROSTRUCTURE_FEATURES)
        if self.config.time_features:
            all_features.extend(TIME_FEATURES)
        
        # Add dynamic features
        if self.feature_cache:
            sample_features = self.feature_cache[-1].features
            for feature_name in sample_features:
                if feature_name not in all_features:
                    all_features.append(feature_name)
        
        return sorted(all_features)
    
    def save_feature_config(self, filepath: Path) -> None:
        """Save feature configuration and statistics"""
        config_data = {
            'config': {
                'price_features': self.config.price_features,
                'volume_features': self.config.volume_features,
                'greeks_features': self.config.greeks_features,
                'market_features': self.config.market_features,
                'microstructure_features': self.config.microstructure_features,
                'time_features': self.config.time_features,
                'normalize': self.config.normalize,
                'handle_missing': self.config.handle_missing,
                'outlier_method': self.config.outlier_method,
                'outlier_threshold': self.config.outlier_threshold
            },
            'feature_stats': self.feature_stats,
            'feature_importance': self.feature_importance,
            'feature_names': self.get_feature_names()
        }
        
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)
    
    def load_feature_config(self, filepath: Path) -> None:
        """Load feature configuration and statistics"""
        with open(filepath, 'r') as f:
            config_data = json.load(f)
        
        # Update configuration
        for key, value in config_data['config'].items():
            setattr(self.config, key, value)
        
        # Load statistics and importance
        self.feature_stats = config_data.get('feature_stats', {})
        self.feature_importance = config_data.get('feature_importance', {})

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_feature_engineer(config: Optional[FeatureConfig] = None) -> FeatureEngineer:
    """Create feature engineer instance"""
    return FeatureEngineer(config)

def get_default_feature_config() -> FeatureConfig:
    """Get default feature configuration"""
    return FeatureConfig()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test feature engineering
    engineer = create_feature_engineer()
    
    # Create sample market data
    market_data = {
        'timestamp': datetime.now(),
        'symbol': 'SPY',
        'open': 450.0,
        'high': 451.5,
        'low': 449.5,
        'close': 450.8,
        'volume': 1000000,
        'bid': 450.75,
        'ask': 450.85,
        'trade_count': 500,
        'quote_count': 2000
    }
    
    # Extract features
    feature_set = engineer.extract_features(market_data)
    
    print(f"Extracted {len(feature_set.features)} features")
    print("\nSample features:")
    for i, (name, value) in enumerate(feature_set.features.items()):
        if i < 10:
            print(f"  {name}: {value:.4f}")
    
    print(f"\nFeature categories enabled:")
    print(f"  Price features: {engineer.config.price_features}")
    print(f"  Volume features: {engineer.config.volume_features}")
    print(f"  Greeks features: {engineer.config.greeks_features}")
    print(f"  Market features: {engineer.config.market_features}")
    print(f"  Microstructure features: {engineer.config.microstructure_features}")
    print(f"  Time features: {engineer.config.time_features}")
