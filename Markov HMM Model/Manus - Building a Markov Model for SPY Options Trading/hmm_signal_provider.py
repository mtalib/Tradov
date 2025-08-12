#!/usr/bin/env python3
"""
SPY HMM Trading Signal Provider
A streamlined version of the HMM trading system optimized for signal generation
without GUI dependencies. Perfect for integration with existing PyQt6 dashboards.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
import threading
import time
import queue
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# Core ML libraries
from hmmlearn import hmm
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import ta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime enumeration"""
    LOW_VOLATILITY_TRENDING = "LOW_VOLATILITY_TRENDING"
    HIGH_VOLATILITY_MEAN_REVERTING = "HIGH_VOLATILITY_MEAN_REVERTING"
    TRANSITIONAL_NEUTRAL = "TRANSITIONAL_NEUTRAL"

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    symbol: str
    signal_type: str  # "BUY", "SELL", "HOLD"
    confidence: float
    regime: MarketRegime
    strategy: str
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RegimeUpdate:
    """Market regime update data structure"""
    regime: MarketRegime
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)
    regime_probabilities: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarketData:
    """Market data container"""
    symbol: str
    data: pd.DataFrame
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class HMMSignalProvider:
    """
    Core HMM-based trading signal provider
    Streamlined for integration with existing systems
    """
    
    def __init__(self, 
                 symbols: List[str] = None,
                 config: Dict[str, Any] = None,
                 data_callback: Callable = None,
                 regime_callback: Callable = None,
                 signal_callback: Callable = None):
        """
        Initialize the HMM Signal Provider
        
        Args:
            symbols: List of symbols to track (default: ["SPY"])
            config: Configuration dictionary
            data_callback: Callback function for market data updates
            regime_callback: Callback function for regime updates
            signal_callback: Callback function for trading signals
        """
        self.symbols = symbols or ["SPY"]
        self.config = config or self._default_config()
        
        # Callback functions for integration
        self.data_callback = data_callback
        self.regime_callback = regime_callback
        self.signal_callback = signal_callback
        
        # Core components
        self.hmm_model = None
        self.strategy_models = {}
        self.scaler = StandardScaler()
        
        # Current state
        self.current_regime = None
        self.regime_confidence = 0.0
        self.regime_probabilities = None
        self.market_data = {}
        self.last_update = None
        
        # Threading
        self.running = False
        self.update_thread = None
        self.data_lock = threading.Lock()
        
        # Signal history
        self.signal_history = []
        self.regime_history = []
        
        # Initialize components
        self._initialize_models()
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            # HMM Configuration
            "hmm": {
                "n_components": 3,
                "covariance_type": "diag",
                "n_iter": 100,
                "random_state": 42,
                "training_window": 252,
                "min_training_samples": 100,
                "retrain_frequency": 50
            },
            
            # Data Configuration
            "data": {
                "update_interval": 60,  # seconds
                "lookback_period": 252,  # days
                "technical_indicators": True,
                "data_source": "yahoo"
            },
            
            # Strategy Configuration
            "strategy": {
                "min_confidence_threshold": 0.6,
                "signal_strength_threshold": 0.53,
                "max_signals_per_day": 5,
                "regime_strategies": {
                    MarketRegime.LOW_VOLATILITY_TRENDING: {
                        "strategy_type": "momentum",
                        "features": ["momentum_5", "momentum_10", "rsi", "macd"],
                        "signal_threshold": 0.55
                    },
                    MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: {
                        "strategy_type": "mean_reversion",
                        "features": ["rsi", "bb_width", "volatility", "returns"],
                        "signal_threshold": 0.60
                    },
                    MarketRegime.TRANSITIONAL_NEUTRAL: {
                        "strategy_type": "conservative",
                        "features": ["volatility", "volume_ratio", "rsi"],
                        "signal_threshold": 0.65
                    }
                }
            },
            
            # Risk Configuration
            "risk": {
                "max_position_size": 0.05,
                "volatility_scaling": True,
                "position_limits": {
                    MarketRegime.LOW_VOLATILITY_TRENDING: 0.80,
                    MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 0.60,
                    MarketRegime.TRANSITIONAL_NEUTRAL: 0.40
                }
            }
        }
    
    def _initialize_models(self):
        """Initialize HMM and strategy models"""
        # Initialize HMM
        hmm_config = self.config["hmm"]
        self.hmm_model = hmm.GaussianHMM(
            n_components=hmm_config["n_components"],
            covariance_type=hmm_config["covariance_type"],
            n_iter=hmm_config["n_iter"],
            random_state=hmm_config["random_state"]
        )
        
        # Initialize strategy models for each regime
        for regime in MarketRegime:
            self.strategy_models[regime] = {
                "model": RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
                ),
                "scaler": StandardScaler(),
                "trained": False,
                "last_training": None
            }
    
    def start(self):
        """Start the signal provider"""
        if self.running:
            logger.warning("Signal provider already running")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        logger.info("HMM Signal Provider started")
    
    def stop(self):
        """Stop the signal provider"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        logger.info("HMM Signal Provider stopped")
    
    def _update_loop(self):
        """Main update loop"""
        while self.running:
            try:
                # Update market data
                self._update_market_data()
                
                # Update regime detection
                self._update_regime_detection()
                
                # Generate signals
                self._generate_signals()
                
                # Sleep until next update
                time.sleep(self.config["data"]["update_interval"])
                
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                time.sleep(10)  # Wait before retrying
    
    def _update_market_data(self):
        """Update market data for all symbols"""
        with self.data_lock:
            for symbol in self.symbols:
                try:
                    # Download recent data
                    data = yf.download(
                        symbol,
                        period=f"{self.config['data']['lookback_period']}d",
                        interval="1d",
                        progress=False
                    )
                    
                    if data.empty:
                        logger.warning(f"No data received for {symbol}")
                        continue
                    
                    # Add technical indicators
                    if self.config["data"]["technical_indicators"]:
                        data = self._add_technical_indicators(data)
                    
                    # Store data
                    self.market_data[symbol] = data
                    self.last_update = datetime.now()
                    
                    # Call data callback if provided
                    if self.data_callback:
                        market_data_obj = MarketData(symbol=symbol, data=data)
                        self.data_callback(market_data_obj)
                    
                    logger.debug(f"Updated data for {symbol}: {len(data)} records")
                    
                except Exception as e:
                    logger.error(f"Error updating data for {symbol}: {e}")
    
    def _add_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to market data"""
        try:
            # Returns and volatility
            data['returns'] = data['Close'].pct_change()
            data['volatility'] = data['returns'].rolling(20).std() * np.sqrt(252)
            
            # Momentum indicators
            data['rsi'] = ta.momentum.RSIIndicator(data['Close']).rsi()
            macd = ta.trend.MACD(data['Close'])
            data['macd'] = macd.macd()
            data['macd_histogram'] = macd.macd_diff()
            
            # Volatility indicators
            bb = ta.volatility.BollingerBands(data['Close'])
            data['bb_upper'] = bb.bollinger_hband()
            data['bb_lower'] = bb.bollinger_lband()
            data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['Close']
            
            # Volume indicators
            data['volume_ratio'] = data['Volume'] / data['Volume'].rolling(20).mean()
            
            # Momentum features
            data['momentum_5'] = data['Close'].pct_change(5)
            data['momentum_10'] = data['Close'].pct_change(10)
            
            # Fill NaN values
            data = data.fillna(method='ffill').fillna(method='bfill')
            
            return data
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            return data
    
    def _update_regime_detection(self):
        """Update HMM regime detection"""
        if not self.market_data or "SPY" not in self.market_data:
            return
        
        try:
            spy_data = self.market_data["SPY"]
            
            # Prepare features for HMM
            features = self._prepare_hmm_features(spy_data)
            if features is None or len(features) < self.config["hmm"]["min_training_samples"]:
                return
            
            # Train or update HMM model
            self._train_hmm_model(features)
            
            # Predict current regime
            regime, confidence, probabilities = self._predict_regime(features)
            
            if regime is not None:
                # Update current state
                self.current_regime = regime
                self.regime_confidence = confidence
                self.regime_probabilities = probabilities
                
                # Add to history
                regime_update = RegimeUpdate(
                    regime=regime,
                    confidence=confidence,
                    regime_probabilities=probabilities
                )
                self.regime_history.append(regime_update)
                
                # Keep only recent history
                if len(self.regime_history) > 1000:
                    self.regime_history = self.regime_history[-1000:]
                
                # Call regime callback if provided
                if self.regime_callback:
                    self.regime_callback(regime_update)
                
                logger.info(f"Regime detected: {regime.name}, Confidence: {confidence:.3f}")
                
        except Exception as e:
            logger.error(f"Error in regime detection: {e}")
    
    def _prepare_hmm_features(self, data: pd.DataFrame) -> Optional[np.ndarray]:
        """Prepare features for HMM model"""
        try:
            feature_columns = [
                'returns', 'volatility', 'rsi', 'macd', 'macd_histogram',
                'bb_width', 'volume_ratio', 'momentum_5', 'momentum_10'
            ]
            
            # Filter available features
            available_features = [col for col in feature_columns if col in data.columns]
            if not available_features:
                return None
            
            # Extract features
            features_df = data[available_features].copy()
            features_df = features_df.dropna()
            
            if len(features_df) < self.config["hmm"]["min_training_samples"]:
                return None
            
            return features_df.values
            
        except Exception as e:
            logger.error(f"Error preparing HMM features: {e}")
            return None
    
    def _train_hmm_model(self, features: np.ndarray):
        """Train the HMM model"""
        try:
            # Scale features
            features_scaled = self.scaler.fit_transform(features)
            
            # Train HMM
            self.hmm_model.fit(features_scaled)
            
            logger.info(f"HMM model trained with {len(features)} samples")
            
        except Exception as e:
            logger.error(f"Error training HMM model: {e}")
    
    def _predict_regime(self, features: np.ndarray) -> tuple:
        """Predict current market regime"""
        try:
            if self.hmm_model is None:
                return None, 0.0, None
            
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Get state probabilities
            log_probabilities = self.hmm_model.score_samples(features_scaled)
            state_sequence = self.hmm_model.predict(features_scaled)
            
            # Get current state
            current_state = state_sequence[-1]
            
            # Calculate state probabilities for the last observation
            state_probs = np.exp(self.hmm_model.predict_proba(features_scaled[-1:]))[0]
            
            # Calculate confidence (1 - entropy)
            entropy = -np.sum(state_probs * np.log(state_probs + 1e-10))
            max_entropy = np.log(len(state_probs))
            confidence = 1 - (entropy / max_entropy)
            
            # Map state to regime based on characteristics
            regime = self._map_state_to_regime(current_state, features_scaled)
            
            return regime, confidence, state_probs
            
        except Exception as e:
            logger.error(f"Error predicting regime: {e}")
            return None, 0.0, None
    
    def _map_state_to_regime(self, state: int, features: np.ndarray) -> MarketRegime:
        """Map HMM state to market regime based on feature characteristics"""
        try:
            # Get recent features for analysis
            recent_features = features[-20:]  # Last 20 observations
            
            # Calculate characteristics
            volatility_idx = 1  # Assuming volatility is the second feature
            returns_idx = 0     # Assuming returns is the first feature
            
            avg_volatility = np.mean(recent_features[:, volatility_idx])
            returns_autocorr = np.corrcoef(recent_features[:-1, returns_idx], 
                                         recent_features[1:, returns_idx])[0, 1]
            
            # Map based on volatility and autocorrelation
            if avg_volatility < -0.5:  # Low volatility (standardized)
                return MarketRegime.LOW_VOLATILITY_TRENDING
            elif avg_volatility > 0.5:  # High volatility (standardized)
                return MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING
            else:
                return MarketRegime.TRANSITIONAL_NEUTRAL
                
        except Exception as e:
            logger.error(f"Error mapping state to regime: {e}")
            return MarketRegime.TRANSITIONAL_NEUTRAL
    
    def _generate_signals(self):
        """Generate trading signals based on current regime"""
        if (self.current_regime is None or 
            self.regime_confidence < self.config["strategy"]["min_confidence_threshold"]):
            return
        
        try:
            for symbol in self.symbols:
                if symbol not in self.market_data:
                    continue
                
                signal = self._generate_symbol_signal(symbol)
                if signal:
                    self.signal_history.append(signal)
                    
                    # Keep only recent signals
                    if len(self.signal_history) > 1000:
                        self.signal_history = self.signal_history[-1000:]
                    
                    # Call signal callback if provided
                    if self.signal_callback:
                        self.signal_callback(signal)
                    
                    logger.info(f"Generated {signal.signal_type} signal for {symbol} "
                              f"with confidence {signal.confidence:.3f}")
                    
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
    
    def _generate_symbol_signal(self, symbol: str) -> Optional[TradingSignal]:
        """Generate trading signal for a specific symbol"""
        try:
            data = self.market_data[symbol]
            regime_config = self.config["strategy"]["regime_strategies"][self.current_regime]
            
            # Prepare features for signal generation
            features = self._prepare_signal_features(data, regime_config["features"])
            if features is None:
                return None
            
            # Train strategy model if needed
            model_info = self.strategy_models[self.current_regime]
            if not model_info["trained"]:
                self._train_strategy_model(data, self.current_regime)
                if not model_info["trained"]:
                    return None
            
            # Generate signal
            model = model_info["model"]
            scaler = model_info["scaler"]
            
            # Get latest features
            latest_features = features[-1:].reshape(1, -1)
            latest_features_scaled = scaler.transform(latest_features)
            
            # Predict signal
            signal_proba = model.predict_proba(latest_features_scaled)[0]
            signal_strength = max(signal_proba)
            
            if signal_strength >= regime_config["signal_threshold"]:
                # Determine signal direction
                signal_class = model.predict(latest_features_scaled)[0]
                signal_type = "BUY" if signal_class == 1 else "SELL"
                
                # Calculate position size
                position_size = self._calculate_position_size(signal_strength)
                
                # Create signal
                signal = TradingSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    confidence=signal_strength,
                    regime=self.current_regime,
                    strategy=regime_config["strategy_type"],
                    entry_price=data['Close'].iloc[-1],
                    position_size=position_size,
                    metadata={
                        "regime_confidence": self.regime_confidence,
                        "features_used": regime_config["features"]
                    }
                )
                
                return signal
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
        
        return None
    
    def _prepare_signal_features(self, data: pd.DataFrame, feature_names: List[str]) -> Optional[np.ndarray]:
        """Prepare features for signal generation"""
        try:
            available_features = [f for f in feature_names if f in data.columns]
            if not available_features:
                return None
            
            features_df = data[available_features].copy()
            features_df = features_df.fillna(method='ffill').fillna(method='bfill')
            features_df = features_df.dropna()
            
            if len(features_df) < 20:
                return None
            
            return features_df.values
            
        except Exception as e:
            logger.error(f"Error preparing signal features: {e}")
            return None
    
    def _train_strategy_model(self, data: pd.DataFrame, regime: MarketRegime):
        """Train strategy model for specific regime"""
        try:
            regime_config = self.config["strategy"]["regime_strategies"][regime]
            model_info = self.strategy_models[regime]
            
            # Prepare features
            features = self._prepare_signal_features(data, regime_config["features"])
            if features is None or len(features) < 50:
                return
            
            # Create target variable (future returns)
            returns = data['returns'].shift(-1).dropna()
            
            # Align features and targets
            min_length = min(len(features), len(returns))
            X = features[:min_length]
            y = (returns[:min_length] > 0).astype(int)
            
            if len(X) < 30:
                return
            
            # Scale and train
            X_scaled = model_info["scaler"].fit_transform(X)
            model_info["model"].fit(X_scaled, y)
            model_info["trained"] = True
            model_info["last_training"] = datetime.now()
            
            logger.info(f"Trained {regime.name} strategy model with {len(X)} samples")
            
        except Exception as e:
            logger.error(f"Error training strategy model: {e}")
    
    def _calculate_position_size(self, signal_strength: float) -> float:
        """Calculate position size based on signal strength and risk parameters"""
        base_size = 0.02  # 2% base position
        
        # Adjust for signal strength
        strength_multiplier = signal_strength / 0.5
        
        # Adjust for regime
        regime_limits = self.config["risk"]["position_limits"]
        regime_multiplier = regime_limits.get(self.current_regime, 1.0)
        
        position_size = base_size * strength_multiplier * regime_multiplier
        
        # Cap at maximum
        max_size = self.config["risk"]["max_position_size"]
        return min(position_size, max_size)
    
    # Public API methods for integration
    
    def get_current_regime(self) -> Optional[RegimeUpdate]:
        """Get current market regime information"""
        if self.current_regime is None:
            return None
        
        return RegimeUpdate(
            regime=self.current_regime,
            confidence=self.regime_confidence,
            regime_probabilities=self.regime_probabilities,
            metadata={
                "last_update": self.last_update,
                "model_trained": self.hmm_model is not None
            }
        )
    
    def get_latest_signals(self, count: int = 10) -> List[TradingSignal]:
        """Get latest trading signals"""
        return self.signal_history[-count:] if self.signal_history else []
    
    def get_regime_history(self, count: int = 100) -> List[RegimeUpdate]:
        """Get regime history"""
        return self.regime_history[-count:] if self.regime_history else []
    
    def get_market_data(self, symbol: str = None) -> Dict[str, pd.DataFrame]:
        """Get current market data"""
        with self.data_lock:
            if symbol:
                return {symbol: self.market_data.get(symbol)} if symbol in self.market_data else {}
            return self.market_data.copy()
    
    def force_update(self):
        """Force an immediate update of data and signals"""
        try:
            self._update_market_data()
            self._update_regime_detection()
            self._generate_signals()
        except Exception as e:
            logger.error(f"Error in force update: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "running": self.running,
            "last_update": self.last_update,
            "current_regime": self.current_regime.name if self.current_regime else None,
            "regime_confidence": self.regime_confidence,
            "symbols_tracked": self.symbols,
            "signals_generated": len(self.signal_history),
            "regime_changes": len(self.regime_history),
            "models_trained": sum(1 for model in self.strategy_models.values() if model["trained"])
        }

# Convenience function for quick setup
def create_signal_provider(symbols: List[str] = None, 
                          config: Dict[str, Any] = None,
                          callbacks: Dict[str, Callable] = None) -> HMMSignalProvider:
    """
    Create and configure an HMM Signal Provider
    
    Args:
        symbols: List of symbols to track
        config: Configuration dictionary
        callbacks: Dictionary of callback functions
    
    Returns:
        Configured HMMSignalProvider instance
    """
    callback_dict = callbacks or {}
    
    return HMMSignalProvider(
        symbols=symbols,
        config=config,
        data_callback=callback_dict.get("data"),
        regime_callback=callback_dict.get("regime"),
        signal_callback=callback_dict.get("signal")
    )

if __name__ == "__main__":
    # Example usage
    def on_regime_update(regime_update: RegimeUpdate):
        print(f"Regime Update: {regime_update.regime.name} (Confidence: {regime_update.confidence:.3f})")
    
    def on_signal_generated(signal: TradingSignal):
        print(f"Signal: {signal.signal_type} {signal.symbol} @ ${signal.entry_price:.2f} "
              f"(Confidence: {signal.confidence:.3f}, Regime: {signal.regime.name})")
    
    # Create signal provider
    provider = create_signal_provider(
        symbols=["SPY"],
        callbacks={
            "regime": on_regime_update,
            "signal": on_signal_generated
        }
    )
    
    # Start the provider
    provider.start()
    
    try:
        # Run for demonstration
        print("HMM Signal Provider running... Press Ctrl+C to stop")
        while True:
            time.sleep(10)
            status = provider.get_status()
            print(f"Status: {status}")
    except KeyboardInterrupt:
        print("\nStopping signal provider...")
        provider.stop()
        print("Signal provider stopped.")

