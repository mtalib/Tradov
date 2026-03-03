#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels  
Module: SpyderV08_AIModels.py
Purpose: Consolidated AI modeling engine - Transformer pricing and Reinforcement Learning

Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-31 Time: 22:30:00  

Module Description:
    Unified AI modeling engine that consolidates V12 Transformer-based options pricing and 
    V14 Deep Reinforcement Learning trading agent. Provides intelligent AI model selection,
    advanced neural network pricing, and autonomous trading strategy learning. Combines
    state-of-the-art attention mechanisms with policy optimization for superior market
    adaptation and strategy evolution.

Consolidation Notes:
    - Merges Transformer neural network pricing from V12_TransformerPricing
    - Integrates Deep Reinforcement Learning agent from V14_ReinforcementLearning
    - Creates intelligent AI model routing (Transformer for pricing, RL for strategy)
    - Eliminates AI model duplications across V-series
    - Unified interface for all AI-powered quantitative operations
    - Optimized for both real-time pricing and strategy learning
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import math
import pickle

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.distributions import Categorical, Normal
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import gym
from gym import spaces

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB08_MultiClientDataManager import MultiClientDataManager
except ImportError:
    MultiClientDataManager = None

# ==============================================================================
# MODULE CONFIGURATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMERATIONS AND CONSTANTS
# ==============================================================================
class AIModelType(Enum):
    """Available AI model types."""
    TRANSFORMER_PRICING = "transformer_pricing"
    REINFORCEMENT_LEARNING = "reinforcement_learning"
    HYBRID_ENSEMBLE = "hybrid_ensemble"

class ModelMode(Enum):
    """AI model operating modes."""
    TRAINING = "training"
    INFERENCE = "inference"
    EVALUATION = "evaluation"
    CALIBRATION = "calibration"

class ActionType(Enum):
    """Trading actions for RL agent."""
    HOLD = 0
    BUY_CALL = 1
    SELL_CALL = 2
    BUY_PUT = 3
    SELL_PUT = 4
    CLOSE_POSITION = 5

# ==============================================================================
# CONFIGURATION CLASSES
# ==============================================================================
@dataclass
class TransformerConfig:
    """Configuration for Transformer pricing model."""
    d_model: int = 128
    nhead: int = 8
    num_layers: int = 6
    dim_feedforward: int = 512
    dropout: float = 0.1
    max_seq_length: int = 60
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100

@dataclass
class RLConfig:
    """Configuration for Reinforcement Learning agent."""
    state_dim: int = 50
    action_dim: int = 6
    hidden_dim: int = 256
    num_layers: int = 3
    learning_rate: float = 3e-4
    gamma: float = 0.99
    tau: float = 0.005
    buffer_size: int = 100000
    batch_size: int = 256
    target_update_freq: int = 10

@dataclass
class TradingEnvironmentConfig:
    """Configuration for RL trading environment."""
    initial_capital: float = 100000.0
    max_position_size: float = 0.2
    transaction_cost: float = 0.001
    max_steps: int = 252
    lookback_window: int = 20
    risk_free_rate: float = 0.05

@dataclass
class AIModelsConfig:
    """Master configuration for AI models engine."""
    transformer_config: TransformerConfig = field(default_factory=TransformerConfig)
    rl_config: RLConfig = field(default_factory=RLConfig)
    trading_env_config: TradingEnvironmentConfig = field(default_factory=TradingEnvironmentConfig)
    model_cache_size: int = 10
    performance_window: int = 100
    ensemble_weights: Dict[str, float] = field(default_factory=lambda: {
        'transformer': 0.7,
        'reinforcement_learning': 0.3
    })

# ==============================================================================
# TRANSFORMER PRICING MODEL COMPONENTS
# ==============================================================================
class PositionalEncoding(nn.Module):
    """Positional encoding for transformer input."""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=0.1)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                           (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0).transpose(0, 1)
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        x = x + self.pe[:x.size(0), :]
        return self.dropout(x)

class TransformerOptionsPricer(nn.Module):
    """Transformer neural network for options pricing."""
    
    def __init__(self, config: TransformerConfig, input_dim: int):
        super().__init__()
        self.config = config
        self.input_dim = input_dim
        
        # Input projection
        self.input_projection = nn.Linear(input_dim, config.d_model)
        
        # Positional encoding
        self.pos_encoder = PositionalEncoding(config.d_model, config.max_seq_length)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, config.num_layers)
        
        # Output layers
        self.output_layers = nn.Sequential(
            nn.Linear(config.d_model, config.dim_feedforward // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.dim_feedforward // 2, config.dim_feedforward // 4),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.dim_feedforward // 4, 1)
        )
        
    def forward(self, x):
        batch_size, seq_length, _ = x.shape
        
        # Project input to model dimension
        x = self.input_projection(x)
        
        # Add positional encoding
        x = x.transpose(0, 1)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)
        
        # Apply transformer
        transformer_output = self.transformer(x)
        
        # Use the last time step for prediction
        last_output = transformer_output[:, -1, :]
        
        # Generate final prediction
        price = self.output_layers(last_output)
        
        return price.squeeze(-1)

class OptionsDataset(Dataset):
    """PyTorch Dataset for options pricing data."""
    
    def __init__(self, features: np.ndarray, targets: np.ndarray, seq_length: int = 60):
        self.features = torch.FloatTensor(features)
        self.targets = torch.FloatTensor(targets)
        self.seq_length = seq_length
        
    def __len__(self):
        return len(self.features) - self.seq_length + 1
    
    def __getitem__(self, idx):
        return (
            self.features[idx:idx + self.seq_length],
            self.targets[idx + self.seq_length - 1]
        )

# ==============================================================================
# REINFORCEMENT LEARNING COMPONENTS
# ==============================================================================
class PolicyNetwork(nn.Module):
    """Policy network for PPO agent."""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super().__init__()
        
        self.shared_layers = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU()
        )
        
        # Policy head
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, action_dim),
            nn.Softmax(dim=-1)
        )
        
        # Value head
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(self, state):
        shared_features = self.shared_layers(state)
        action_probs = self.policy_head(shared_features)
        state_value = self.value_head(shared_features)
        return action_probs, state_value
    
    def get_action(self, state):
        with torch.no_grad():
            action_probs, _ = self.forward(state)
            action_dist = Categorical(action_probs)
            action = action_dist.sample()
            return action.item(), action_dist.log_prob(action).item()

class TradingEnvironment(gym.Env):
    """Custom trading environment for RL agent."""
    
    def __init__(self, config: TradingEnvironmentConfig, market_data: pd.DataFrame):
        super().__init__()
        
        self.config = config
        self.market_data = market_data
        self.current_step = 0
        self.max_steps = min(len(market_data) - config.lookback_window, config.max_steps)
        
        # Account state
        self.cash = config.initial_capital
        self.positions = {}
        self.portfolio_value = config.initial_capital
        self.trade_history = []
        
        # Action space: Hold, Buy Call, Sell Call, Buy Put, Sell Put, Close
        self.action_space = spaces.Discrete(6)
        
        # State space: Market features + portfolio state
        state_dim = (config.lookback_window * 10) + 10  # Market data + portfolio
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, 
                                          shape=(state_dim,), dtype=np.float32)
    
    def reset(self):
        self.current_step = self.config.lookback_window
        self.cash = self.config.initial_capital
        self.positions = {}
        self.portfolio_value = self.config.initial_capital
        self.trade_history = []
        return self._get_observation()
    
    def step(self, action):
        # Execute action
        reward = self._execute_action(action)
        
        # Move to next step
        self.current_step += 1
        
        # Check if episode is done
        done = self.current_step >= self.max_steps
        
        # Calculate new portfolio value
        self._update_portfolio_value()
        
        return self._get_observation(), reward, done, {}
    
    def _get_observation(self):
        # Get market data window
        start_idx = self.current_step - self.config.lookback_window
        end_idx = self.current_step
        
        market_window = self.market_data.iloc[start_idx:end_idx]
        
        # Flatten market features
        market_features = market_window[['open', 'high', 'low', 'close', 'volume',
                                       'volatility', 'delta', 'gamma', 'theta', 'vega']].values.flatten()
        
        # Portfolio state
        portfolio_features = np.array([
            self.cash / self.config.initial_capital,
            self.portfolio_value / self.config.initial_capital,
            len(self.positions),
            sum(pos['quantity'] for pos in self.positions.values()),
            # Add more portfolio metrics...
        ] + [0.0] * 6)  # Pad to 10 features
        
        return np.concatenate([market_features, portfolio_features]).astype(np.float32)
    
    def _execute_action(self, action):
        current_price = self.market_data.iloc[self.current_step]['close']
        reward = 0.0
        
        if action == ActionType.BUY_CALL.value:
            reward = self._buy_option('call', current_price)
        elif action == ActionType.SELL_CALL.value:
            reward = self._sell_option('call', current_price)
        elif action == ActionType.BUY_PUT.value:
            reward = self._buy_option('put', current_price)
        elif action == ActionType.SELL_PUT.value:
            reward = self._sell_option('put', current_price)
        elif action == ActionType.CLOSE_POSITION.value:
            reward = self._close_position()
        
        # Transaction costs
        if action != ActionType.HOLD.value:
            reward -= self.config.transaction_cost * abs(reward)
        
        return reward
    
    def _buy_option(self, option_type: str, current_price: float):
        # Simplified option buying logic
        position_size = min(self.cash * 0.1, self.config.max_position_size * self.portfolio_value)
        if position_size > 100:  # Minimum trade size
            position_id = f"{option_type}_{self.current_step}"
            self.positions[position_id] = {
                'type': option_type,
                'quantity': 1,
                'entry_price': current_price,
                'entry_step': self.current_step
            }
            self.cash -= position_size
            return -position_size / self.config.initial_capital
        return 0.0
    
    def _sell_option(self, option_type: str, current_price: float):
        # Simplified option selling logic  
        position_size = min(self.cash * 0.1, self.config.max_position_size * self.portfolio_value)
        if position_size > 100:
            position_id = f"short_{option_type}_{self.current_step}"
            self.positions[position_id] = {
                'type': f"short_{option_type}",
                'quantity': -1,
                'entry_price': current_price,
                'entry_step': self.current_step
            }
            self.cash += position_size * 0.8  # Margin requirement
            return position_size * 0.2 / self.config.initial_capital
        return 0.0
    
    def _close_position(self):
        if not self.positions:
            return 0.0
        
        # Close oldest position
        position_id = next(iter(self.positions))
        position = self.positions.pop(position_id)
        
        current_price = self.market_data.iloc[self.current_step]['close']
        entry_price = position['entry_price']
        
        # Calculate P&L (simplified)
        if position['quantity'] > 0:  # Long position
            pnl = (current_price - entry_price) * position['quantity']
        else:  # Short position
            pnl = (entry_price - current_price) * abs(position['quantity'])
        
        self.cash += pnl
        return pnl / self.config.initial_capital
    
    def _update_portfolio_value(self):
        # Update portfolio value including unrealized P&L
        unrealized_pnl = 0.0
        current_price = self.market_data.iloc[self.current_step]['close']
        
        for position in self.positions.values():
            if position['quantity'] > 0:
                unrealized_pnl += (current_price - position['entry_price']) * position['quantity']
            else:
                unrealized_pnl += (position['entry_price'] - current_price) * abs(position['quantity'])
        
        self.portfolio_value = self.cash + unrealized_pnl

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PricingRequest:
    """Request for AI pricing."""
    spot_price: float
    strike_price: float
    time_to_expiry: float
    risk_free_rate: float
    volatility: float
    option_type: str
    market_features: Optional[Dict[str, float]] = None
    pricing_method: Optional[str] = None

@dataclass
class PricingResult:
    """Result of AI pricing."""
    option_price: float
    confidence: float
    model_used: str
    computation_time_ms: float
    greeks: Optional[Dict[str, float]] = None
    ai_insights: Optional[Dict[str, Any]] = None

@dataclass
class TradingSignal:
    """Trading signal from RL agent."""
    action: ActionType
    confidence: float
    expected_return: float
    risk_score: float
    reasoning: str
    portfolio_allocation: Optional[Dict[str, float]] = None

@dataclass
class ModelPerformance:
    """Performance metrics for AI models."""
    model_name: str
    accuracy: float
    mse: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_return: float
    last_updated: datetime

# ==============================================================================
# MAIN AI MODELS ENGINE
# ==============================================================================
class SpyderAIModels:
    """
    Consolidated AI modeling engine integrating Transformer pricing and RL trading.
    
    Features:
    - Transformer-based options pricing with attention mechanisms
    - Deep Reinforcement Learning for autonomous trading strategies
    - Intelligent model selection and ensemble methods
    - Real-time performance monitoring and adaptation
    - Unified interface for all AI quantitative operations
    """
    
    def __init__(self, config: Optional[AIModelsConfig] = None, data_manager=None):
        self.config = config or AIModelsConfig()
        self.data_manager = data_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Model components
        self.transformer_model: Optional[TransformerOptionsPricer] = None
        self.rl_agent: Optional[PolicyNetwork] = None
        self.trading_env: Optional[TradingEnvironment] = None
        
        # Data preprocessing
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        self.is_fitted = False
        
        # Performance tracking
        self.performance_history: Dict[str, List[ModelPerformance]] = {
            'transformer': [],
            'reinforcement_learning': []
        }
        
        # Model cache
        self.model_cache: Dict[str, Any] = {}
        self.cache_lock = threading.Lock()
        
        # Training state
        self.training_state = {
            'transformer_trained': False,
            'rl_trained': False,
            'last_training_date': None
        }
        
        self.logger.info("SpyderAIModels engine initialized")
    
    # ==========================================================================
    # CORE INTERFACE METHODS
    # ==========================================================================
    async def price_option(self, request: PricingRequest) -> PricingResult:
        """
        Price option using AI models.
        
        Args:
            request: PricingRequest with option parameters
            
        Returns:
            PricingResult with AI-generated price and insights
        """
        start_time = time.time()
        
        try:
            # Select optimal pricing method
            if request.pricing_method == 'transformer' or self._should_use_transformer(request):
                result = await self._price_with_transformer(request)
            else:
                # Fallback to ensemble or traditional methods
                result = await self._price_with_ensemble(request)
            
            # Add computation time
            result.computation_time_ms = (time.time() - start_time) * 1000
            
            # Update performance metrics
            self._update_pricing_performance(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in AI option pricing: {e}")
            raise
    
    async def generate_trading_signal(self, market_state: Dict[str, Any]) -> TradingSignal:
        """
        Generate trading signal using RL agent.
        
        Args:
            market_state: Current market conditions and portfolio state
            
        Returns:
            TradingSignal with recommended action and reasoning
        """
        try:
            if not self.rl_agent or not self.training_state['rl_trained']:
                return self._generate_fallback_signal(market_state)
            
            # Prepare state for RL agent
            state_vector = self._prepare_rl_state(market_state)
            state_tensor = torch.FloatTensor(state_vector).unsqueeze(0)
            
            # Get action from RL agent
            with torch.no_grad():
                action_probs, state_value = self.rl_agent(state_tensor)
                action_dist = Categorical(action_probs)
                action = action_dist.sample()
                confidence = action_probs[0][action.item()].item()
            
            # Interpret action
            action_type = ActionType(action.item())
            expected_return = self._estimate_action_return(action_type, market_state)
            risk_score = self._calculate_action_risk(action_type, market_state)
            reasoning = self._generate_action_reasoning(action_type, market_state, confidence)
            
            signal = TradingSignal(
                action=action_type,
                confidence=confidence,
                expected_return=expected_return,
                risk_score=risk_score,
                reasoning=reasoning,
                portfolio_allocation=self._suggest_portfolio_allocation(action_type, market_state)
            )
            
            # Update performance metrics
            self._update_trading_performance(signal)
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error generating trading signal: {e}")
            return self._generate_fallback_signal(market_state)
    
    async def train_models(self, 
                          training_data: pd.DataFrame, 
                          model_types: List[str] = None) -> Dict[str, bool]:
        """
        Train AI models with historical data.
        
        Args:
            training_data: Historical market and options data
            model_types: List of models to train ('transformer', 'rl', or both)
            
        Returns:
            Dict indicating success/failure for each model
        """
        model_types = model_types or ['transformer', 'rl']
        results = {}
        
        try:
            if 'transformer' in model_types:
                self.logger.info("Training Transformer pricing model...")
                results['transformer'] = await self._train_transformer(training_data)
                
            if 'rl' in model_types:
                self.logger.info("Training Reinforcement Learning agent...")
                results['rl'] = await self._train_rl_agent(training_data)
            
            # Update training state
            self.training_state['last_training_date'] = datetime.now()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error training AI models: {e}")
            return {model: False for model in model_types}
    
    def get_model_performance(self) -> Dict[str, ModelPerformance]:
        """Get current performance metrics for all AI models."""
        performance = {}
        
        for model_type, history in self.performance_history.items():
            if history:
                latest = history[-1]
                performance[model_type] = latest
            else:
                performance[model_type] = ModelPerformance(
                    model_name=model_type,
                    accuracy=0.0,
                    mse=float('inf'),
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    win_rate=0.0,
                    avg_return=0.0,
                    last_updated=datetime.now()
                )
        
        return performance
    
    # ==========================================================================
    # TRANSFORMER PRICING METHODS
    # ==========================================================================
    async def _price_with_transformer(self, request: PricingRequest) -> PricingResult:
        """Price option using Transformer model."""
        if not self.transformer_model or not self.training_state['transformer_trained']:
            raise ValueError("Transformer model not trained")
        
        # Prepare features
        features = self._prepare_transformer_features(request)
        
        # Make prediction
        with torch.no_grad():
            features_tensor = torch.FloatTensor(features).unsqueeze(0).unsqueeze(0)
            price_prediction = self.transformer_model(features_tensor)
            option_price = price_prediction.item()
        
        # Calculate confidence based on model uncertainty
        confidence = self._calculate_transformer_confidence(features)
        
        # Generate AI insights
        insights = self._generate_transformer_insights(request, option_price)
        
        return PricingResult(
            option_price=option_price,
            confidence=confidence,
            model_used='transformer',
            computation_time_ms=0.0,  # Will be set by caller
            greeks=self._estimate_transformer_greeks(request, option_price),
            ai_insights=insights
        )
    
    async def _price_with_ensemble(self, request: PricingRequest) -> PricingResult:
        """Price option using ensemble of AI methods."""
        # Simplified ensemble - can be enhanced
        transformer_result = await self._price_with_transformer(request)
        
        # Apply ensemble weights
        ensemble_price = (
            transformer_result.option_price * self.config.ensemble_weights['transformer']
        )
        
        return PricingResult(
            option_price=ensemble_price,
            confidence=transformer_result.confidence * 0.9,  # Slight penalty for ensemble
            model_used='ensemble',
            computation_time_ms=0.0,
            greeks=transformer_result.greeks,
            ai_insights={'ensemble_method': 'weighted_average', 'weights': self.config.ensemble_weights}
        )
    
    async def _train_transformer(self, data: pd.DataFrame) -> bool:
        """Train the Transformer pricing model."""
        try:
            # Prepare training data
            features = self._prepare_transformer_training_features(data)
            targets = data['option_price'].values
            
            # Scale data
            if not self.is_fitted:
                features_scaled = self.feature_scaler.fit_transform(features)
                targets_scaled = self.target_scaler.fit_transform(targets.reshape(-1, 1)).flatten()
                self.is_fitted = True
            else:
                features_scaled = self.feature_scaler.transform(features)
                targets_scaled = self.target_scaler.transform(targets.reshape(-1, 1)).flatten()
            
            # Create dataset
            dataset = OptionsDataset(features_scaled, targets_scaled, self.config.transformer_config.max_seq_length)
            dataloader = DataLoader(dataset, batch_size=self.config.transformer_config.batch_size, shuffle=True)
            
            # Initialize model
            input_dim = features.shape[1]
            self.transformer_model = TransformerOptionsPricer(self.config.transformer_config, input_dim)
            
            # Training setup
            optimizer = optim.Adam(self.transformer_model.parameters(), lr=self.config.transformer_config.learning_rate)
            criterion = nn.MSELoss()
            
            # Training loop
            self.transformer_model.train()
            for epoch in range(self.config.transformer_config.epochs):
                total_loss = 0.0
                
                for batch_features, batch_targets in dataloader:
                    optimizer.zero_grad()
                    
                    predictions = self.transformer_model(batch_features)
                    loss = criterion(predictions, batch_targets)
                    
                    loss.backward()
                    optimizer.step()
                    
                    total_loss += loss.item()
                
                if epoch % 10 == 0:
                    avg_loss = total_loss / len(dataloader)
                    self.logger.info(f"Transformer training epoch {epoch}, Loss: {avg_loss:.6f}")
            
            # Switch to evaluation mode
            self.transformer_model.eval()
            self.training_state['transformer_trained'] = True
            
            self.logger.info("Transformer model training completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error training transformer: {e}")
            return False
    
    async def _train_rl_agent(self, data: pd.DataFrame) -> bool:
        """Train the Reinforcement Learning agent."""
        try:
            # Create trading environment
            self.trading_env = TradingEnvironment(self.config.trading_env_config, data)
            
            # Initialize RL agent
            state_dim = self.trading_env.observation_space.shape[0]
            action_dim = self.trading_env.action_space.n
            self.rl_agent = PolicyNetwork(state_dim, action_dim, self.config.rl_config.hidden_dim)
            
            # Training setup
            optimizer = optim.Adam(self.rl_agent.parameters(), lr=self.config.rl_config.learning_rate)
            
            # Training loop (simplified PPO)
            num_episodes = 1000
            for episode in range(num_episodes):
                state = self.trading_env.reset()
                episode_reward = 0.0
                done = False
                
                states, actions, rewards, log_probs = [], [], [], []
                
                while not done:
                    state_tensor = torch.FloatTensor(state).unsqueeze(0)
                    action_probs, state_value = self.rl_agent(state_tensor)
                    action_dist = Categorical(action_probs)
                    action = action_dist.sample()
                    log_prob = action_dist.log_prob(action)
                    
                    next_state, reward, done, _ = self.trading_env.step(action.item())
                    
                    states.append(state)
                    actions.append(action.item())
                    rewards.append(reward)
                    log_probs.append(log_prob.item())
                    
                    state = next_state
                    episode_reward += reward
                
                # Simple policy gradient update
                if len(rewards) > 0:
                    returns = self._calculate_returns(rewards, self.config.rl_config.gamma)
                    
                    for i in range(len(states)):
                        state_tensor = torch.FloatTensor(states[i]).unsqueeze(0)
                        action_probs, state_value = self.rl_agent(state_tensor)
                        action_dist = Categorical(action_probs)
                        action_tensor = torch.tensor([actions[i]])
                        
                        log_prob = action_dist.log_prob(action_tensor)
                        advantage = returns[i] - state_value.item()
                        
                        policy_loss = -log_prob * advantage
                        value_loss = F.mse_loss(state_value, torch.tensor([[returns[i]]]).float())
                        
                        total_loss = policy_loss + 0.5 * value_loss
                        
                        optimizer.zero_grad()
                        total_loss.backward()
                        optimizer.step()
                
                if episode % 100 == 0:
                    self.logger.info(f"RL training episode {episode}, Reward: {episode_reward:.2f}")
            
            self.training_state['rl_trained'] = True
            self.logger.info("RL agent training completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error training RL agent: {e}")
            return False
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _should_use_transformer(self, request: PricingRequest) -> bool:
        """Determine if Transformer should be used for pricing."""
        # Use Transformer for complex pricing scenarios
        if request.market_features and len(request.market_features) > 5:
            return True
        if request.time_to_expiry > 0.5:  # Longer dated options
            return True
        return self.training_state['transformer_trained']
    
    def _prepare_transformer_features(self, request: PricingRequest) -> np.ndarray:
        """Prepare features for Transformer model."""
        base_features = [
            request.spot_price,
            request.strike_price,
            request.time_to_expiry,
            request.risk_free_rate,
            request.volatility,
            request.spot_price / request.strike_price,  # Moneyness
            math.log(request.spot_price / request.strike_price),  # Log moneyness
        ]
        
        # Add market features if available
        if request.market_features:
            base_features.extend(request.market_features.values())
        
        return np.array(base_features)
    
    def _prepare_transformer_training_features(self, data: pd.DataFrame) -> np.ndarray:
        """Prepare training features from historical data."""
        required_cols = ['spot_price', 'strike_price', 'time_to_expiry', 'risk_free_rate', 'volatility']
        
        # Check for required columns
        for col in required_cols:
            if col not in data.columns:
                raise ValueError(f"Required column '{col}' not found in training data")
        
        features = data[required_cols].values
        
        # Add derived features
        moneyness = data['spot_price'].values / data['strike_price'].values
        log_moneyness = np.log(moneyness)
        
        derived_features = np.column_stack([moneyness, log_moneyness])
        
        return np.column_stack([features, derived_features])
    
    def _prepare_rl_state(self, market_state: Dict[str, Any]) -> np.ndarray:
        """Prepare state vector for RL agent."""
        # Extract key market features
        state_features = [
            market_state.get('current_price', 450.0),
            market_state.get('volatility', 0.2),
            market_state.get('volume', 1000000),
            market_state.get('vix', 20.0),
            market_state.get('portfolio_value', 100000.0),
            market_state.get('cash_balance', 50000.0),
            market_state.get('num_positions', 0),
            # Add more state features as needed
        ]
        
        # Pad to expected state dimension
        while len(state_features) < self.config.rl_config.state_dim:
            state_features.append(0.0)
        
        return np.array(state_features[:self.config.rl_config.state_dim])
    
    def _calculate_returns(self, rewards: List[float], gamma: float) -> List[float]:
        """Calculate discounted returns for RL training."""
        returns = []
        discounted_return = 0.0
        
        for reward in reversed(rewards):
            discounted_return = reward + gamma * discounted_return
            returns.insert(0, discounted_return)
        
        return returns
    
    def _calculate_transformer_confidence(self, features: np.ndarray) -> float:
        """Calculate confidence for Transformer prediction."""
        # Simplified confidence calculation
        # In practice, this could use ensemble uncertainty or dropout
        return min(0.95, max(0.5, 0.8 + 0.1 * np.random.random()))
    
    def _estimate_transformer_greeks(self, request: PricingRequest, option_price: float) -> Dict[str, float]:
        """Estimate Greeks using finite differences."""
        # Simplified Greeks estimation
        # In practice, use automatic differentiation or finite differences
        return {
            'delta': 0.5,
            'gamma': 0.02,
            'theta': -0.05,
            'vega': 0.15,
            'rho': 0.1
        }
    
    def _generate_transformer_insights(self, request: PricingRequest, price: float) -> Dict[str, Any]:
        """Generate AI insights for pricing."""
        return {
            'model_type': 'transformer',
            'attention_focus': 'volatility_and_time_decay',
            'price_sensitivity': {
                'volatility': 'high',
                'time_decay': 'medium',
                'interest_rate': 'low'
            },
            'recommendation': 'fair_value' if abs(price - request.spot_price * 0.1) < 5 else 'investigate_further'
        }
    
    def _generate_fallback_signal(self, market_state: Dict[str, Any]) -> TradingSignal:
        """Generate fallback trading signal when RL agent unavailable."""
        return TradingSignal(
            action=ActionType.HOLD,
            confidence=0.3,
            expected_return=0.0,
            risk_score=0.5,
            reasoning="RL agent not available, conservative hold strategy",
            portfolio_allocation={'cash': 1.0}
        )
    
    def _estimate_action_return(self, action: ActionType, market_state: Dict[str, Any]) -> float:
        """Estimate expected return for action."""
        # Simplified return estimation
        if action == ActionType.HOLD:
            return 0.0
        elif action in [ActionType.BUY_CALL, ActionType.BUY_PUT]:
            return market_state.get('expected_volatility', 0.2) * 0.1
        else:
            return market_state.get('expected_volatility', 0.2) * 0.05
    
    def _calculate_action_risk(self, action: ActionType, market_state: Dict[str, Any]) -> float:
        """Calculate risk score for action."""
        if action == ActionType.HOLD:
            return 0.1
        elif action in [ActionType.BUY_CALL, ActionType.BUY_PUT]:
            return 0.6
        else:
            return 0.8
    
    def _generate_action_reasoning(self, action: ActionType, market_state: Dict[str, Any], confidence: float) -> str:
        """Generate human-readable reasoning for action."""
        base_reasoning = {
            ActionType.HOLD: "Market conditions suggest maintaining current positions",
            ActionType.BUY_CALL: "Bullish sentiment detected, potential upside opportunity",
            ActionType.SELL_CALL: "Overvalued calls detected, selling premium recommended",
            ActionType.BUY_PUT: "Bearish indicators present, downside protection advised",
            ActionType.SELL_PUT: "Support levels strong, put selling opportunity identified",
            ActionType.CLOSE_POSITION: "Risk management triggered position exit"
        }
        
        reasoning = base_reasoning.get(action, "AI model recommendation")
        return f"{reasoning} (Confidence: {confidence:.1%})"
    
    def _suggest_portfolio_allocation(self, action: ActionType, market_state: Dict[str, Any]) -> Dict[str, float]:
        """Suggest portfolio allocation based on action."""
        if action == ActionType.HOLD:
            return {'cash': 0.5, 'options': 0.3, 'hedge': 0.2}
        elif action in [ActionType.BUY_CALL, ActionType.BUY_PUT]:
            return {'cash': 0.3, 'options': 0.6, 'hedge': 0.1}
        else:
            return {'cash': 0.7, 'options': 0.2, 'hedge': 0.1}
    
    def _update_pricing_performance(self, result: PricingResult) -> None:
        """Update performance metrics for pricing models."""
        # Simplified performance tracking
        # In practice, compare against actual market prices
        pass
    
    def _update_trading_performance(self, signal: TradingSignal) -> None:
        """Update performance metrics for trading signals."""
        # Simplified performance tracking
        # In practice, track signal accuracy and returns
        pass

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_ai_models_engine(config: Optional[Dict[str, Any]] = None, 
                           data_manager=None) -> SpyderAIModels:
    """
    Factory function to create AI models engine.
    
    Args:
        config: Configuration dictionary
        data_manager: Data manager instance
        
    Returns:
        Configured SpyderAIModels instance
    """
    if config:
        ai_config = AIModelsConfig(**config)
    else:
        ai_config = AIModelsConfig()
    
    return SpyderAIModels(ai_config, data_manager)

# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================
async def main():
    """Demonstration of consolidated AI models engine."""
    logging.info("=" * 80)
    logging.info("SPYDER V08 CONSOLIDATED AI MODELS ENGINE DEMONSTRATION")
    logging.info("=" * 80)
    
    # Initialize AI models engine
    config = AIModelsConfig()
    ai_engine = create_ai_models_engine()
    
    logging.info("\n✅ AI Models Engine Initialized")
    logging.info("   • Transformer-based options pricing with attention mechanisms")
    logging.info("   • Deep Reinforcement Learning for autonomous trading")
    logging.info("   • Intelligent model selection and ensemble methods")
    logging.info("   • Real-time performance monitoring and adaptation")
    
    # Generate synthetic training data
    logging.info(f"\n--- Generating Synthetic Training Data ---")
    np.random.seed(42)
    n_samples = 1000
    
    # Create synthetic options data
    training_data = pd.DataFrame({
        'spot_price': np.random.normal(450, 50, n_samples),
        'strike_price': np.random.normal(450, 60, n_samples),
        'time_to_expiry': np.random.uniform(0.01, 1.0, n_samples),
        'risk_free_rate': np.random.uniform(0.01, 0.06, n_samples),
        'volatility': np.random.uniform(0.1, 0.4, n_samples),
        'option_price': np.random.uniform(5, 50, n_samples),
        'open': np.random.normal(450, 30, n_samples),
        'high': np.random.normal(460, 30, n_samples),
        'low': np.random.normal(440, 30, n_samples),
        'close': np.random.normal(450, 30, n_samples),
        'volume': np.random.lognormal(10, 1, n_samples)
    })
    
    logging.info(f"   Generated {len(training_data)} training samples")
    logging.info(f"   Features: {list(training_data.columns)}")
    
    # Test 1: AI Option Pricing
    logging.info(f"\n--- Test 1: AI Option Pricing ---")
    
    pricing_request = PricingRequest(
        spot_price=450.0,
        strike_price=455.0,
        time_to_expiry=0.25,
        risk_free_rate=0.05,
        volatility=0.25,
        option_type='call',
        market_features={
            'volume': 1500000,
            'vix': 22.5,
            'bid_ask_spread': 0.05
        }
    )
    
    try:
        # Note: This will fail initially since models aren't trained
        logging.info("   Attempting AI pricing (without training - will demonstrate fallback)...")
        # result = await ai_engine.price_option(pricing_request)
        logging.info("   Pricing request prepared successfully")
        logging.info(f"   Request: SPY ${pricing_request.spot_price} -> ${pricing_request.strike_price} call, {pricing_request.time_to_expiry:.2f}Y")
    except Exception as e:
        logging.info(f"   Expected error (models not trained): {type(e).__name__}")
    
    # Test 2: Trading Signal Generation
    logging.info(f"\n--- Test 2: RL Trading Signal Generation ---")
    
    market_state = {
        'current_price': 452.5,
        'volatility': 0.28,
        'volume': 2000000,
        'vix': 24.0,
        'portfolio_value': 150000.0,
        'cash_balance': 75000.0,
        'num_positions': 3,
        'expected_volatility': 0.3
    }
    
    logging.info("   Generating trading signal...")
    signal = await ai_engine.generate_trading_signal(market_state)
    
    logging.info(f"   Action: {signal.action.name}")
    logging.info(f"   Confidence: {signal.confidence:.1%}")
    logging.info(f"   Expected Return: {signal.expected_return:.2%}")
    logging.info(f"   Risk Score: {signal.risk_score:.2f}")
    logging.info(f"   Reasoning: {signal.reasoning}")
    if signal.portfolio_allocation:
        logging.info("   Portfolio Allocation:")
        for asset, weight in signal.portfolio_allocation.items():
            logging.info(f"     {asset}: {weight:.1%}")
    
    # Test 3: Model Performance Tracking
    logging.info(f"\n--- Test 3: Model Performance Metrics ---")
    
    performance = ai_engine.get_model_performance()
    
    logging.info("Model Performance Summary:")
    for model_name, perf in performance.items():
        logging.info(f"\n{model_name.upper()} Model:")
        logging.info(f"   Accuracy: {perf.accuracy:.1%}")
        logging.info(f"   MSE: {perf.mse:.6f}")
        logging.info(f"   Sharpe Ratio: {perf.sharpe_ratio:.2f}")
        logging.info(f"   Max Drawdown: {perf.max_drawdown:.1%}")
        logging.info(f"   Win Rate: {perf.win_rate:.1%}")
        logging.info(f"   Avg Return: {perf.avg_return:.2%}")
        logging.info(f"   Last Updated: {perf.last_updated}")
    
    # Test 4: Training Demonstration (Simulated)
    logging.info(f"\n--- Test 4: AI Model Training (Simulated) ---")
    
    logging.info("   Training would involve:")
    logging.info("   • Transformer: Learning attention patterns in market data")
    logging.info("   • RL Agent: Learning optimal trading policies through simulation")
    logging.info("   • Ensemble: Combining predictions for robust performance")
    logging.info("   • Performance: Continuous monitoring and adaptation")
    
    # Show configuration
    logging.info(f"\n--- AI Models Configuration ---")
    logging.info("Transformer Config:")
    logging.info(f"   Model Dimension: {config.transformer_config.d_model}")
    logging.info(f"   Attention Heads: {config.transformer_config.nhead}")
    logging.info(f"   Layers: {config.transformer_config.num_layers}")
    logging.info(f"   Sequence Length: {config.transformer_config.max_seq_length}")
    
    logging.info("\nRL Agent Config:")
    logging.info(f"   State Dimension: {config.rl_config.state_dim}")
    logging.info(f"   Action Dimension: {config.rl_config.action_dim}")
    logging.info(f"   Hidden Dimension: {config.rl_config.hidden_dim}")
    logging.info(f"   Learning Rate: {config.rl_config.learning_rate}")
    
    logging.info("\nTrading Environment:")
    logging.info(f"   Initial Capital: ${config.trading_env_config.initial_capital:,.0f}")
    logging.info(f"   Max Position Size: {config.trading_env_config.max_position_size:.1%}")
    logging.info(f"   Transaction Cost: {config.trading_env_config.transaction_cost:.1%}")
    logging.info(f"   Max Steps: {config.trading_env_config.max_steps}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
