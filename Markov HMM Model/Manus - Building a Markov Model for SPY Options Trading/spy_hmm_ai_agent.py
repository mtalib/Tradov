#!/usr/bin/env python3
"""
SPY Options HMM Trading AI Agent
A sophisticated autonomous trading agent that uses Hidden Markov Models
for regime detection and adaptive options trading strategies.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import queue
from abc import ABC, abstractmethod
import warnings
warnings.filterwarnings('ignore')

# Core ML and Statistical Libraries
from hmmlearn import hmm
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.stattools import adfuller
import ta

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('spy_hmm_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classifications"""
    LOW_VOLATILITY_TRENDING = 0
    HIGH_VOLATILITY_MEAN_REVERTING = 1
    TRANSITIONAL_NEUTRAL = 2

class MessageType(Enum):
    """Agent communication message types"""
    REGIME_UPDATE = "regime_update"
    SIGNAL_GENERATED = "signal_generated"
    RISK_ALERT = "risk_alert"
    POSITION_UPDATE = "position_update"
    MARKET_DATA_UPDATE = "market_data_update"
    SYSTEM_STATUS = "system_status"

@dataclass
class AgentMessage:
    """Message structure for agent communication"""
    sender: str
    receiver: str
    message_type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 1

    def __post_init__(self):
        self.priority = self._determine_priority()

    def _determine_priority(self) -> int:
        """Determine message priority based on type"""
        priority_map = {
            MessageType.RISK_ALERT: 0,  # Highest priority
            MessageType.REGIME_UPDATE: 1,
            MessageType.SIGNAL_GENERATED: 2,
            MessageType.POSITION_UPDATE: 3,
            MessageType.MARKET_DATA_UPDATE: 4,
            MessageType.SYSTEM_STATUS: 5  # Lowest priority
        }
        return priority_map.get(self.message_type, 5)

@dataclass
class TradingSignal:
    """Trading signal structure"""
    symbol: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float
    regime: MarketRegime
    strategy: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SystemState:
    """Global system state"""
    current_regime: Optional[MarketRegime] = None
    regime_confidence: float = 0.0
    portfolio_positions: Dict[str, Any] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    market_data: Dict[str, Any] = field(default_factory=dict)
    system_status: str = "INITIALIZING"
    last_update: datetime = field(default_factory=datetime.now)

class MessageBus:
    """Central message bus for agent communication"""
    
    def __init__(self):
        self.agents = {}
        self.message_queue = queue.PriorityQueue()
        self.running = False
        self.message_thread = None
        
    def register_agent(self, agent):
        """Register an agent with the message bus"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id}")
        
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
            
    def send_message(self, message: AgentMessage):
        """Send a message through the bus"""
        self.message_queue.put((message.priority, message))
        
    def start(self):
        """Start the message processing thread"""
        self.running = True
        self.message_thread = threading.Thread(target=self._process_messages)
        self.message_thread.daemon = True
        self.message_thread.start()
        logger.info("Message bus started")
        
    def stop(self):
        """Stop the message processing thread"""
        self.running = False
        if self.message_thread:
            self.message_thread.join()
        logger.info("Message bus stopped")
        
    def _process_messages(self):
        """Process messages in the queue"""
        while self.running:
            try:
                if not self.message_queue.empty():
                    priority, message = self.message_queue.get(timeout=1)
                    if message.receiver in self.agents:
                        self.agents[message.receiver].receive_message(message)
                    elif message.receiver == "ALL":
                        for agent in self.agents.values():
                            agent.receive_message(message)
                else:
                    time.sleep(0.1)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_id: str, message_bus: MessageBus):
        self.agent_id = agent_id
        self.message_bus = message_bus
        self.running = False
        self.agent_thread = None
        self.message_queue = queue.Queue()
        
    @abstractmethod
    def process_data(self, data: Any) -> Any:
        """Process data specific to this agent"""
        pass
        
    def receive_message(self, message: AgentMessage):
        """Receive a message from the message bus"""
        self.message_queue.put(message)
        
    def send_message(self, receiver: str, message_type: MessageType, data: Dict[str, Any]):
        """Send a message through the message bus"""
        message = AgentMessage(
            sender=self.agent_id,
            receiver=receiver,
            message_type=message_type,
            data=data
        )
        self.message_bus.send_message(message)
        
    def start(self):
        """Start the agent"""
        self.running = True
        self.agent_thread = threading.Thread(target=self._run)
        self.agent_thread.daemon = True
        self.agent_thread.start()
        logger.info(f"Agent {self.agent_id} started")
        
    def stop(self):
        """Stop the agent"""
        self.running = False
        if self.agent_thread:
            self.agent_thread.join()
        logger.info(f"Agent {self.agent_id} stopped")
        
    @abstractmethod
    def _run(self):
        """Main agent loop"""
        pass

class DataAgent(BaseAgent):
    """Agent responsible for data collection and preprocessing"""
    
    def __init__(self, message_bus: MessageBus, symbols: List[str] = None):
        super().__init__("DataAgent", message_bus)
        self.symbols = symbols or ["SPY"]
        self.data_cache = {}
        self.last_update = {}
        self.update_interval = 60  # seconds
        
    def process_data(self, data: Any) -> Dict[str, pd.DataFrame]:
        """Process and clean market data"""
        processed_data = {}
        
        for symbol in self.symbols:
            try:
                # Download recent data
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="1y", interval="1d")
                
                if df.empty:
                    logger.warning(f"No data received for {symbol}")
                    continue
                    
                # Calculate basic features
                df['returns'] = df['Close'].pct_change()
                df['log_returns'] = np.log(df['Close'] / df['Close'].shift(1))
                df['volatility'] = df['returns'].rolling(window=20).std() * np.sqrt(252)
                
                # Add technical indicators
                df = self._add_technical_indicators(df)
                
                # Clean data
                df = df.dropna()
                
                processed_data[symbol] = df
                self.data_cache[symbol] = df
                self.last_update[symbol] = datetime.now()
                
                logger.info(f"Updated data for {symbol}: {len(df)} records")
                
            except Exception as e:
                logger.error(f"Error processing data for {symbol}: {e}")
                
        return processed_data
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the dataframe"""
        try:
            # RSI
            df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()
            
            # MACD
            macd = ta.trend.MACD(df['Close'])
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['macd_histogram'] = macd.macd_diff()
            
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(df['Close'])
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_lower'] = bb.bollinger_lband()
            df['bb_middle'] = bb.bollinger_mavg()
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            
            # Volume indicators
            df['volume_sma'] = df['Volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['Volume'] / df['volume_sma']
            
            # Price momentum
            df['momentum_5'] = df['Close'] / df['Close'].shift(5) - 1
            df['momentum_10'] = df['Close'] / df['Close'].shift(10) - 1
            df['momentum_20'] = df['Close'] / df['Close'].shift(20) - 1
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            
        return df
    
    def _run(self):
        """Main data agent loop"""
        while self.running:
            try:
                # Process messages
                while not self.message_queue.empty():
                    message = self.message_queue.get()
                    if message.message_type == MessageType.MARKET_DATA_UPDATE:
                        # Handle data update requests
                        pass
                
                # Update data periodically
                current_time = datetime.now()
                should_update = False
                
                for symbol in self.symbols:
                    if (symbol not in self.last_update or 
                        (current_time - self.last_update[symbol]).seconds > self.update_interval):
                        should_update = True
                        break
                
                if should_update:
                    processed_data = self.process_data(None)
                    if processed_data:
                        self.send_message(
                            "ALL",
                            MessageType.MARKET_DATA_UPDATE,
                            {"data": processed_data, "timestamp": current_time}
                        )
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in DataAgent main loop: {e}")
                time.sleep(5)

class HMMAgent(BaseAgent):
    """Agent responsible for HMM regime detection"""
    
    def __init__(self, message_bus: MessageBus, n_components: int = 3):
        super().__init__("HMMAgent", message_bus)
        self.n_components = n_components
        self.hmm_model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.current_regime = None
        self.regime_confidence = 0.0
        self.training_window = 252  # 1 year of daily data
        self.min_training_samples = 100
        
    def process_data(self, data: pd.DataFrame) -> Tuple[MarketRegime, float]:
        """Process data and detect market regime"""
        try:
            if data is None or len(data) < self.min_training_samples:
                return self.current_regime, self.regime_confidence
            
            # Prepare features
            features = self._prepare_features(data)
            if features is None or len(features) < self.min_training_samples:
                return self.current_regime, self.regime_confidence
            
            # Train or update HMM model
            if self.hmm_model is None:
                self._train_hmm_model(features)
            else:
                self._update_hmm_model(features)
            
            # Predict current regime
            if self.hmm_model is not None:
                regime, confidence = self._predict_regime(features)
                self.current_regime = regime
                self.regime_confidence = confidence
                
                logger.info(f"Regime detected: {regime.name}, Confidence: {confidence:.3f}")
                
                return regime, confidence
                
        except Exception as e:
            logger.error(f"Error in HMM regime detection: {e}")
            
        return self.current_regime, self.regime_confidence
    
    def _prepare_features(self, data: pd.DataFrame) -> Optional[np.ndarray]:
        """Prepare features for HMM model"""
        try:
            # Select relevant features for regime detection
            feature_cols = [
                'returns', 'volatility', 'rsi', 'macd', 'macd_histogram',
                'bb_width', 'volume_ratio', 'momentum_5', 'momentum_10'
            ]
            
            # Filter available columns
            available_cols = [col for col in feature_cols if col in data.columns]
            if not available_cols:
                logger.warning("No suitable features found for HMM model")
                return None
            
            # Extract features
            features_df = data[available_cols].copy()
            
            # Handle missing values
            features_df = features_df.fillna(method='ffill').fillna(method='bfill')
            
            # Check for stationarity and transform if needed
            for col in features_df.columns:
                if self._is_non_stationary(features_df[col]):
                    features_df[col] = features_df[col].pct_change().fillna(0)
            
            # Remove any remaining NaN values
            features_df = features_df.dropna()
            
            if len(features_df) < self.min_training_samples:
                return None
            
            # Scale features
            if len(features_df) > 0:
                features_scaled = self.scaler.fit_transform(features_df)
                self.feature_columns = features_df.columns.tolist()
                return features_scaled
                
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            
        return None
    
    def _is_non_stationary(self, series: pd.Series) -> bool:
        """Test for stationarity using Augmented Dickey-Fuller test"""
        try:
            if len(series.dropna()) < 20:
                return False
            result = adfuller(series.dropna())
            return result[1] > 0.05  # p-value > 0.05 indicates non-stationarity
        except:
            return False
    
    def _train_hmm_model(self, features: np.ndarray):
        """Train the HMM model"""
        try:
            self.hmm_model = hmm.GaussianHMM(
                n_components=self.n_components,
                covariance_type="diag",
                n_iter=100,
                random_state=42
            )
            
            # Use recent data for training
            training_data = features[-self.training_window:] if len(features) > self.training_window else features
            
            self.hmm_model.fit(training_data)
            logger.info(f"HMM model trained with {len(training_data)} samples")
            
        except Exception as e:
            logger.error(f"Error training HMM model: {e}")
            self.hmm_model = None
    
    def _update_hmm_model(self, features: np.ndarray):
        """Update the HMM model with new data"""
        try:
            # For simplicity, retrain the model periodically
            # In production, you might want to implement online learning
            if len(features) > self.training_window:
                self._train_hmm_model(features)
                
        except Exception as e:
            logger.error(f"Error updating HMM model: {e}")
    
    def _predict_regime(self, features: np.ndarray) -> Tuple[MarketRegime, float]:
        """Predict the current market regime"""
        try:
            if self.hmm_model is None or len(features) == 0:
                return MarketRegime.TRANSITIONAL_NEUTRAL, 0.0
            
            # Use recent data for prediction
            recent_data = features[-20:] if len(features) > 20 else features
            
            # Get state probabilities
            state_probs = self.hmm_model.predict_proba(recent_data)
            
            # Use the last observation's probabilities
            last_probs = state_probs[-1]
            
            # Map HMM states to market regimes
            regime_mapping = {
                0: MarketRegime.LOW_VOLATILITY_TRENDING,
                1: MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING,
                2: MarketRegime.TRANSITIONAL_NEUTRAL
            }
            
            # Get the most likely regime
            most_likely_state = np.argmax(last_probs)
            confidence = last_probs[most_likely_state]
            
            regime = regime_mapping.get(most_likely_state, MarketRegime.TRANSITIONAL_NEUTRAL)
            
            return regime, confidence
            
        except Exception as e:
            logger.error(f"Error predicting regime: {e}")
            return MarketRegime.TRANSITIONAL_NEUTRAL, 0.0
    
    def _run(self):
        """Main HMM agent loop"""
        while self.running:
            try:
                # Process messages
                while not self.message_queue.empty():
                    message = self.message_queue.get()
                    
                    if message.message_type == MessageType.MARKET_DATA_UPDATE:
                        data = message.data.get("data", {})
                        if "SPY" in data:
                            regime, confidence = self.process_data(data["SPY"])
                            
                            # Send regime update to other agents
                            self.send_message(
                                "ALL",
                                MessageType.REGIME_UPDATE,
                                {
                                    "regime": regime,
                                    "confidence": confidence,
                                    "timestamp": datetime.now()
                                }
                            )
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in HMMAgent main loop: {e}")
                time.sleep(5)

if __name__ == "__main__":
    # Example usage
    print("SPY HMM AI Agent System")
    print("=" * 50)
    
    # Create message bus
    message_bus = MessageBus()
    message_bus.start()
    
    # Create and start agents
    data_agent = DataAgent(message_bus, ["SPY"])
    hmm_agent = HMMAgent(message_bus)
    
    # Register agents
    message_bus.register_agent(data_agent)
    message_bus.register_agent(hmm_agent)
    
    # Start agents
    data_agent.start()
    hmm_agent.start()
    
    try:
        print("Agents started. Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping agents...")
        data_agent.stop()
        hmm_agent.stop()
        message_bus.stop()
        print("System stopped.")

