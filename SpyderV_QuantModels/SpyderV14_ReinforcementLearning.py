#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV14_ReinforcementLearning.py
Purpose: Deep Reinforcement Learning agent for autonomous options trading.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 14:30:00

Module Description:
    This module implements a sophisticated Deep Reinforcement Learning (DRL) agent
    specifically designed for autonomous SPY options trading. Using Proximal Policy
    Optimization (PPO), the agent learns optimal trading strategies by interacting
    with a realistic market environment. The agent can handle complex multi-asset
    portfolios, dynamic hedging, and risk management while adapting to changing
    market conditions. This represents the cutting edge of algorithmic trading
    technology, where AI agents learn and evolve their strategies through experience.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import warnings
import pickle
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.distributions import Categorical, Normal
import gym
from gym import spaces

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TradingEnvironmentConfig:
    """Configuration for the trading environment."""
    initial_capital: float = 100000.0
    max_position_size: float = 0.2  # Max 20% of capital per position
    transaction_cost: float = 0.001  # 0.1% transaction cost
    max_steps: int = 252  # One trading year
    lookback_window: int = 20  # Days of historical data to observe
    risk_free_rate: float = 0.05
    
@dataclass
class PPOConfig:
    """Configuration for PPO algorithm."""
    learning_rate: float = 3e-4
    gamma: float = 0.99  # Discount factor
    gae_lambda: float = 0.95  # GAE parameter
    clip_epsilon: float = 0.2  # PPO clipping parameter
    entropy_coef: float = 0.01  # Entropy regularization
    value_coef: float = 0.5  # Value function coefficient
    max_grad_norm: float = 0.5  # Gradient clipping
    ppo_epochs: int = 4  # PPO update epochs
    batch_size: int = 64

class OptionsMarketEnvironment(gym.Env):
    """
    Gym environment for options trading simulation.
    
    State space includes:
    - Current portfolio positions
    - Market data (prices, volatilities, Greeks)
    - Technical indicators
    - Risk metrics
    
    Action space includes:
    - Buy/sell options (calls/puts)
    - Position sizing
    - Portfolio rebalancing
    """
    
    def __init__(self, config: TradingEnvironmentConfig, market_data: pd.DataFrame):
        super().__init__()
        self.config = config
        self.market_data = market_data
        self.current_step = 0
        self.initial_capital = config.initial_capital
        self.capital = config.initial_capital
        self.positions = {}  # Track current positions
        self.portfolio_history = []
        
        # Define action and observation spaces
        # Actions: [action_type, strike_selection, expiry_selection, position_size, option_type]
        # action_type: 0=hold, 1=buy, 2=sell, 3=close_position
        # strike_selection: 0-9 (10 strike levels around ATM)
        # expiry_selection: 0-3 (4 expiry dates)
        # position_size: 0-10 (position size as % of capital)
        # option_type: 0=call, 1=put
        self.action_space = spaces.MultiDiscrete([4, 10, 4, 11, 2])
        
        # Observation space: market data + portfolio state
        obs_dim = (config.lookback_window * 8 +  # Market features
                  10 +  # Portfolio state
                  5)    # Risk metrics
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, 
                                          shape=(obs_dim,), dtype=np.float32)
        
        self.reset()
    
    def reset(self) -> np.ndarray:
        """Reset the environment to initial state."""
        self.current_step = self.config.lookback_window
        self.capital = self.initial_capital
        self.positions = {}
        self.portfolio_history = []
        return self._get_observation()
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, Dict]:
        """Execute one trading step."""
        # Parse action
        action_type, strike_idx, expiry_idx, size_idx, option_type = action
        
        # Execute action
        reward = self._execute_action(action_type, strike_idx, expiry_idx, size_idx, option_type)
        
        # Update positions and calculate portfolio value
        self._update_positions()
        portfolio_value = self._calculate_portfolio_value()
        
        # Record portfolio history
        self.portfolio_history.append({
            'step': self.current_step,
            'portfolio_value': portfolio_value,
            'capital': self.capital,
            'positions': len(self.positions),
            'action': action.tolist()
        })
        
        # Move to next step
        self.current_step += 1
        
        # Check if episode is done
        done = (self.current_step >= len(self.market_data) - 1 or 
                portfolio_value <= 0.1 * self.initial_capital)
        
        # Get next observation
        obs = self._get_observation()
        
        # Additional info
        info = {
            'portfolio_value': portfolio_value,
            'total_return': (portfolio_value - self.initial_capital) / self.initial_capital,
            'num_positions': len(self.positions)
        }
        
        return obs, reward, done, info
    
    def _execute_action(self, action_type: int, strike_idx: int, expiry_idx: int, 
                       size_idx: int, option_type: int) -> float:
        """Execute the trading action and return immediate reward."""
        reward = 0.0
        
        if action_type == 0:  # Hold
            reward = 0.0
            
        elif action_type == 1:  # Buy option
            reward = self._buy_option(strike_idx, expiry_idx, size_idx, option_type)
            
        elif action_type == 2:  # Sell option
            reward = self._sell_option(strike_idx, expiry_idx, size_idx, option_type)
            
        elif action_type == 3:  # Close positions
            reward = self._close_positions()
        
        return reward
    
    def _buy_option(self, strike_idx: int, expiry_idx: int, size_idx: int, option_type: int) -> float:
        """Buy an option position."""
        current_price = self.market_data.iloc[self.current_step]['spot_price']
        
        # Determine strike price (around ATM)
        strike_range = np.linspace(0.9 * current_price, 1.1 * current_price, 10)
        strike = strike_range[strike_idx]
        
        # Determine expiry (in days)
        expiry_options = [7, 14, 30, 60]
        expiry_days = expiry_options[expiry_idx]
        
        # Position size as percentage of capital
        position_size = (size_idx + 1) * 0.02  # 2% to 22% of capital
        
        # Calculate option price (simplified Black-Scholes)
        option_price = self._calculate_option_price(current_price, strike, expiry_days/365, option_type)
        
        # Calculate number of contracts
        position_value = self.capital * position_size
        num_contracts = int(position_value / (option_price * 100))  # Options are per 100 shares
        
        if num_contracts > 0 and self.capital >= num_contracts * option_price * 100:
            # Create position
            position_id = f"{option_type}_{strike:.0f}_{expiry_days}_{self.current_step}"
            
            self.positions[position_id] = {
                'type': 'call' if option_type == 0 else 'put',
                'strike': strike,
                'expiry_step': self.current_step + expiry_days,
                'num_contracts': num_contracts,
                'entry_price': option_price,
                'entry_step': self.current_step
            }
            
            # Deduct cost from capital
            total_cost = num_contracts * option_price * 100 * (1 + self.config.transaction_cost)
            self.capital -= total_cost
            
            # Reward based on expected profitability (simplified)
            reward = 0.1  # Small positive reward for taking action
        else:
            reward = -0.05  # Penalty for invalid action
        
        return reward
    
    def _sell_option(self, strike_idx: int, expiry_idx: int, size_idx: int, option_type: int) -> float:
        """Sell (write) an option position."""
        # Similar to buy but with opposite position
        # For simplicity, we'll treat this as closing existing positions
        return self._close_positions()
    
    def _close_positions(self) -> float:
        """Close all current positions."""
        total_pnl = 0.0
        positions_to_remove = []
        
        for position_id, position in self.positions.items():
            # Calculate current option value
            current_price = self.market_data.iloc[self.current_step]['spot_price']
            expiry_remaining = max(0, position['expiry_step'] - self.current_step)
            
            current_option_price = self._calculate_option_price(
                current_price, position['strike'], expiry_remaining/365, 
                0 if position['type'] == 'call' else 1
            )
            
            # Calculate P&L
            pnl = (current_option_price - position['entry_price']) * position['num_contracts'] * 100
            pnl *= (1 - self.config.transaction_cost)  # Transaction costs
            
            total_pnl += pnl
            self.capital += current_option_price * position['num_contracts'] * 100 * (1 - self.config.transaction_cost)
            
            positions_to_remove.append(position_id)
        
        # Remove closed positions
        for position_id in positions_to_remove:
            del self.positions[position_id]
        
        # Reward based on P&L
        reward = total_pnl / self.initial_capital  # Normalized P&L
        return reward
    
    def _update_positions(self):
        """Update positions and handle expirations."""
        expired_positions = []
        
        for position_id, position in self.positions.items():
            if self.current_step >= position['expiry_step']:
                # Handle expiration
                current_price = self.market_data.iloc[self.current_step]['spot_price']
                
                if position['type'] == 'call':
                    intrinsic_value = max(0, current_price - position['strike'])
                else:
                    intrinsic_value = max(0, position['strike'] - current_price)
                
                # Add intrinsic value to capital
                self.capital += intrinsic_value * position['num_contracts'] * 100
                expired_positions.append(position_id)
        
        # Remove expired positions
        for position_id in expired_positions:
            del self.positions[position_id]
    
    def _calculate_option_price(self, spot: float, strike: float, time_to_expiry: float, option_type: int) -> float:
        """Simplified Black-Scholes option pricing."""
        if time_to_expiry <= 0:
            if option_type == 0:  # Call
                return max(0, spot - strike)
            else:  # Put
                return max(0, strike - spot)
        
        # Simplified pricing (in practice, use more sophisticated models)
        volatility = 0.2  # Assume 20% volatility
        r = self.config.risk_free_rate
        
        from scipy.stats import norm
        import math
        
        d1 = (math.log(spot / strike) + (r + 0.5 * volatility**2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
        d2 = d1 - volatility * math.sqrt(time_to_expiry)
        
        if option_type == 0:  # Call
            price = spot * norm.cdf(d1) - strike * math.exp(-r * time_to_expiry) * norm.cdf(d2)
        else:  # Put
            price = strike * math.exp(-r * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
        
        return max(0.01, price)  # Minimum price
    
    def _calculate_portfolio_value(self) -> float:
        """Calculate total portfolio value."""
        total_value = self.capital
        
        for position in self.positions.values():
            current_price = self.market_data.iloc[self.current_step]['spot_price']
            expiry_remaining = max(0, position['expiry_step'] - self.current_step)
            
            option_value = self._calculate_option_price(
                current_price, position['strike'], expiry_remaining/365,
                0 if position['type'] == 'call' else 1
            )
            
            total_value += option_value * position['num_contracts'] * 100
        
        return total_value
    
    def _get_observation(self) -> np.ndarray:
        """Get current state observation."""
        obs = []
        
        # Market data features (lookback window)
        start_idx = max(0, self.current_step - self.config.lookback_window)
        end_idx = self.current_step + 1
        
        market_slice = self.market_data.iloc[start_idx:end_idx]
        
        # Pad if necessary
        if len(market_slice) < self.config.lookback_window:
            padding = self.config.lookback_window - len(market_slice)
            market_slice = pd.concat([market_slice.iloc[:1]] * padding + [market_slice])
        
        # Extract features
        features = ['spot_price', 'volatility', 'volume', 'rsi', 'macd', 'bollinger_pos', 'vix', 'returns']
        for feature in features:
            if feature in market_slice.columns:
                obs.extend(market_slice[feature].values)
            else:
                obs.extend([0.0] * self.config.lookback_window)
        
        # Portfolio state
        portfolio_value = self._calculate_portfolio_value()
        obs.extend([
            self.capital / self.initial_capital,
            portfolio_value / self.initial_capital,
            len(self.positions),
            min(len(self.positions), 10) / 10,  # Normalized position count
            (portfolio_value - self.initial_capital) / self.initial_capital,  # Total return
            self.current_step / self.config.max_steps,  # Time progress
            0.0, 0.0, 0.0, 0.0  # Placeholder for additional portfolio metrics
        ])
        
        # Risk metrics
        if len(self.portfolio_history) > 1:
            returns = [h['portfolio_value'] for h in self.portfolio_history[-20:]]
            returns = np.diff(returns) / returns[:-1] if len(returns) > 1 else [0.0]
            volatility = np.std(returns) if len(returns) > 1 else 0.0
            max_drawdown = self._calculate_max_drawdown()
        else:
            volatility = 0.0
            max_drawdown = 0.0
        
        obs.extend([
            volatility,
            max_drawdown,
            0.0, 0.0, 0.0  # Placeholder for additional risk metrics
        ])
        
        return np.array(obs, dtype=np.float32)
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if len(self.portfolio_history) < 2:
            return 0.0
        
        values = [h['portfolio_value'] for h in self.portfolio_history]
        peak = values[0]
        max_dd = 0.0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)
        
        return max_dd

class PPOAgent:
    """Proximal Policy Optimization agent for options trading."""
    
    def __init__(self, obs_dim: int, action_dims: List[int], config: PPOConfig):
        self.config = config
        self.obs_dim = obs_dim
        self.action_dims = action_dims
        
        # Neural networks
        self.actor = self._build_actor_network()
        self.critic = self._build_critic_network()
        
        # Optimizers
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=config.learning_rate)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=config.learning_rate)
        
        # Storage for training data
        self.memory = []
    
    def _build_actor_network(self) -> nn.Module:
        """Build actor (policy) network."""
        class ActorNetwork(nn.Module):
            def __init__(self, obs_dim, action_dims):
                super().__init__()
                self.shared = nn.Sequential(
                    nn.Linear(obs_dim, 256),
                    nn.ReLU(),
                    nn.Linear(256, 256),
                    nn.ReLU(),
                    nn.Linear(256, 128),
                    nn.ReLU()
                )
                
                # Separate heads for each action dimension
                self.action_heads = nn.ModuleList([
                    nn.Linear(128, dim) for dim in action_dims
                ])
            
            def forward(self, x):
                shared_features = self.shared(x)
                action_logits = [head(shared_features) for head in self.action_heads]
                return action_logits
        
        return ActorNetwork(self.obs_dim, self.action_dims)
    
    def _build_critic_network(self) -> nn.Module:
        """Build critic (value) network."""
        return nn.Sequential(
            nn.Linear(self.obs_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )
    
    def select_action(self, obs: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Select action using current policy."""
        obs_tensor = torch.FloatTensor(obs).unsqueeze(0)
        
        with torch.no_grad():
            action_logits = self.actor(obs_tensor)
            value = self.critic(obs_tensor)
        
        # Sample actions from categorical distributions
        actions = []
        log_probs = []
        
        for logits in action_logits:
            dist = Categorical(logits=logits)
            action = dist.sample()
            log_prob = dist.log_prob(action)
            
            actions.append(action.item())
            log_probs.append(log_prob)
        
        total_log_prob = torch.stack(log_probs).sum()
        
        return np.array(actions), total_log_prob.item(), value.item()
    
    def store_transition(self, obs, action, log_prob, reward, value, done):
        """Store transition in memory."""
        self.memory.append({
            'obs': obs,
            'action': action,
            'log_prob': log_prob,
            'reward': reward,
            'value': value,
            'done': done
        })
    
    def update(self):
        """Update policy using PPO algorithm."""
        if len(self.memory) < self.config.batch_size:
            return
        
        # Convert memory to tensors
        obs = torch.FloatTensor([m['obs'] for m in self.memory])
        actions = [torch.LongTensor([m['action'][i] for m in self.memory]) for i in range(len(self.action_dims))]
        old_log_probs = torch.FloatTensor([m['log_prob'] for m in self.memory])
        rewards = torch.FloatTensor([m['reward'] for m in self.memory])
        values = torch.FloatTensor([m['value'] for m in self.memory])
        dones = torch.BoolTensor([m['done'] for m in self.memory])
        
        # Calculate advantages using GAE
        advantages = self._calculate_gae(rewards, values, dones)
        returns = advantages + values
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        # PPO updates
        for _ in range(self.config.ppo_epochs):
            # Get current policy outputs
            action_logits = self.actor(obs)
            current_values = self.critic(obs).squeeze()
            
            # Calculate current log probabilities
            current_log_probs = []
            entropy_losses = []
            
            for i, (logits, action) in enumerate(zip(action_logits, actions)):
                dist = Categorical(logits=logits)
                log_prob = dist.log_prob(action)
                entropy = dist.entropy()
                
                current_log_probs.append(log_prob)
                entropy_losses.append(entropy.mean())
            
            current_log_probs = torch.stack(current_log_probs).sum(dim=0)
            entropy_loss = torch.stack(entropy_losses).mean()
            
            # PPO loss calculation
            ratio = torch.exp(current_log_probs - old_log_probs)
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon) * advantages
            
            actor_loss = -torch.min(surr1, surr2).mean() - self.config.entropy_coef * entropy_loss
            
            # Value loss
            value_loss = F.mse_loss(current_values, returns)
            
            # Update networks
            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.actor.parameters(), self.config.max_grad_norm)
            self.actor_optimizer.step()
            
            self.critic_optimizer.zero_grad()
            value_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.critic.parameters(), self.config.max_grad_norm)
            self.critic_optimizer.step()
        
        # Clear memory
        self.memory = []
    
    def _calculate_gae(self, rewards, values, dones):
        """Calculate Generalized Advantage Estimation."""
        advantages = torch.zeros_like(rewards)
        advantage = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.config.gamma * next_value * (1 - dones[t]) - values[t]
            advantage = delta + self.config.gamma * self.config.gae_lambda * (1 - dones[t]) * advantage
            advantages[t] = advantage
        
        return advantages

class SpyderReinforcementLearningModel:
    """
    Main interface for the Deep RL trading system.
    
    Features:
    - PPO-based learning agent
    - Realistic options trading environment
    - Portfolio management and risk control
    - Performance tracking and analysis
    """
    
    def __init__(self, env_config: Optional[TradingEnvironmentConfig] = None,
                 ppo_config: Optional[PPOConfig] = None):
        self.env_config = env_config or TradingEnvironmentConfig()
        self.ppo_config = ppo_config or PPOConfig()
        self.env: Optional[OptionsMarketEnvironment] = None
        self.agent: Optional[PPOAgent] = None
        self.training_history = []
    
    def setup_environment(self, market_data: pd.DataFrame):
        """Setup the trading environment with market data."""
        self.env = OptionsMarketEnvironment(self.env_config, market_data)
        
        # Initialize agent
        obs_dim = self.env.observation_space.shape[0]
        action_dims = self.env.action_space.nvec.tolist()
        self.agent = PPOAgent(obs_dim, action_dims, self.ppo_config)
        
        logger.info(f"Environment setup complete. Obs dim: {obs_dim}, Action dims: {action_dims}")
    
    def train(self, num_episodes: int = 1000, save_frequency: int = 100):
        """Train the RL agent."""
        if self.env is None or self.agent is None:
            raise RuntimeError("Environment must be setup before training")
        
        logger.info(f"Starting training for {num_episodes} episodes...")
        
        for episode in range(num_episodes):
            obs = self.env.reset()
            episode_reward = 0
            episode_steps = 0
            
            while True:
                # Select action
                action, log_prob, value = self.agent.select_action(obs)
                
                # Take step
                next_obs, reward, done, info = self.env.step(action)
                
                # Store transition
                self.agent.store_transition(obs, action, log_prob, reward, value, done)
                
                obs = next_obs
                episode_reward += reward
                episode_steps += 1
                
                if done:
                    break
            
            # Update agent
            self.agent.update()
            
            # Record training progress
            self.training_history.append({
                'episode': episode,
                'reward': episode_reward,
                'steps': episode_steps,
                'final_portfolio_value': info.get('portfolio_value', 0),
                'total_return': info.get('total_return', 0)
            })
            
            # Logging
            if episode % 50 == 0:
                avg_reward = np.mean([h['reward'] for h in self.training_history[-50:]])
                avg_return = np.mean([h['total_return'] for h in self.training_history[-50:]])
                logger.info(f"Episode {episode}: Avg Reward = {avg_reward:.4f}, Avg Return = {avg_return:.2%}")
            
            # Save model
            if episode % save_frequency == 0 and episode > 0:
                self.save_model(f"spyder_rl_model_episode_{episode}.pth")
        
        logger.info("Training completed!")
    
    def evaluate(self, num_episodes: int = 10) -> Dict[str, Any]:
        """Evaluate the trained agent."""
        if self.env is None or self.agent is None:
            raise RuntimeError("Model must be trained before evaluation")
        
        evaluation_results = []
        
        for episode in range(num_episodes):
            obs = self.env.reset()
            episode_reward = 0
            
            while True:
                action, _, _ = self.agent.select_action(obs)
                obs, reward, done, info = self.env.step(action)
                episode_reward += reward
                
                if done:
                    evaluation_results.append({
                        'episode_reward': episode_reward,
                        'final_portfolio_value': info['portfolio_value'],
                        'total_return': info['total_return'],
                        'num_positions': info['num_positions']
                    })
                    break
        
        # Calculate statistics
        returns = [r['total_return'] for r in evaluation_results]
        portfolio_values = [r['final_portfolio_value'] for r in evaluation_results]
        
        evaluation_stats = {
            'avg_return': np.mean(returns),
            'std_return': np.std(returns),
            'max_return': np.max(returns),
            'min_return': np.min(returns),
            'avg_portfolio_value': np.mean(portfolio_values),
            'sharpe_ratio': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0,
            'win_rate': np.mean([r > 0 for r in returns])
        }
        
        return evaluation_stats
    
    def save_model(self, filepath: str):
        """Save the trained model."""
        if self.agent is None:
            raise RuntimeError("No model to save")
        
        model_data = {
            'actor_state_dict': self.agent.actor.state_dict(),
            'critic_state_dict': self.agent.critic.state_dict(),
            'env_config': self.env_config,
            'ppo_config': self.ppo_config,
            'training_history': self.training_history
        }
        
        torch.save(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model."""
        model_data = torch.load(filepath, map_location='cpu')
        
        self.env_config = model_data['env_config']
        self.ppo_config = model_data['ppo_config']
        self.training_history = model_data['training_history']
        
        logger.info(f"Model loaded from {filepath}")

def main():
    """Example usage of the SpyderReinforcementLearningModel."""
    print("="*60)
    print(" SPYDER - Deep Reinforcement Learning Trading Agent")
    print("="*60)
    
    # Generate synthetic market data
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=500, freq='D')
    
    # Create realistic market data with trends and volatility
    returns = np.random.normal(0.0005, 0.02, 500)
    # Add some volatility clustering
    for i in range(100, 150):
        returns[i] *= 2.0
    for i in range(300, 350):
        returns[i] *= 1.5
    
    prices = 450 * (1 + returns).cumprod()
    
    market_data = pd.DataFrame({
        'date': dates,
        'spot_price': prices,
        'volatility': np.random.uniform(0.15, 0.35, 500),
        'volume': np.random.lognormal(15, 0.5, 500),
        'rsi': np.random.uniform(20, 80, 500),
        'macd': np.random.normal(0, 1, 500),
        'bollinger_pos': np.random.uniform(0, 1, 500),
        'vix': np.random.uniform(15, 40, 500),
        'returns': returns
    })
    
    print(f"\n--- Generated {len(market_data)} days of market data ---")
    print(f"Price range: ${prices.min():.2f} - ${prices.max():.2f}")
    
    # Initialize RL model
    env_config = TradingEnvironmentConfig(
        initial_capital=100000,
        max_position_size=0.15,
        transaction_cost=0.002,
        max_steps=400
    )
    
    ppo_config = PPOConfig(
        learning_rate=1e-4,
        batch_size=32,
        ppo_epochs=3
    )
    
    rl_model = SpyderReinforcementLearningModel(env_config, ppo_config)
    rl_model.setup_environment(market_data)
    
    # Train the agent (reduced episodes for demo)
    print("\n--- Training RL Agent ---")
    print("Training with reduced episodes for demonstration...")
    rl_model.train(num_episodes=100, save_frequency=50)
    
    # Evaluate performance
    print("\n--- Evaluating Trained Agent ---")
    eval_stats = rl_model.evaluate(num_episodes=5)
    
    print("Evaluation Results:")
    print(f"  Average Return: {eval_stats['avg_return']:.2%}")
    print(f"  Return Volatility: {eval_stats['std_return']:.2%}")
    print(f"  Best Return: {eval_stats['max_return']:.2%}")
    print(f"  Worst Return: {eval_stats['min_return']:.2%}")
    print(f"  Sharpe Ratio: {eval_stats['sharpe_ratio']:.2f}")
    print(f"  Win Rate: {eval_stats['win_rate']:.1%}")
    print(f"  Avg Final Portfolio: ${eval_stats['avg_portfolio_value']:,.2f}")
    
    # Show training progress
    if len(rl_model.training_history) > 10:
        print("\n--- Training Progress ---")
        recent_episodes = rl_model.training_history[-10:]
        avg_recent_return = np.mean([ep['total_return'] for ep in recent_episodes])
        print(f"  Average return (last 10 episodes): {avg_recent_return:.2%}")
        print(f"  Total training episodes: {len(rl_model.training_history)}")
    
    print("="*60)
    print("Note: This is a demonstration with limited training.")
    print("For production use, train for 10,000+ episodes with more market data.")

if __name__ == "__main__":
    main()

