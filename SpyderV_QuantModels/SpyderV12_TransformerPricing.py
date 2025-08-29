#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV12_TransformerPricing.py
Purpose: Transformer-based neural network for options pricing using attention mechanisms.
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 14:00:00

Module Description:
    This module implements a state-of-the-art Transformer neural network for options
    pricing, leveraging attention mechanisms to capture long-term dependencies in
    market data. The model can learn complex non-linear relationships between market
    variables and option prices, potentially outperforming traditional closed-form
    solutions. It incorporates market microstructure features, volatility surfaces,
    and temporal patterns to provide superior pricing accuracy for American-style
    SPY options.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import warnings
import pickle
import os

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TransformerConfig:
    """Configuration parameters for the Transformer model."""
    d_model: int = 128          # Model dimension
    nhead: int = 8              # Number of attention heads
    num_layers: int = 6         # Number of transformer layers
    dim_feedforward: int = 512  # Feedforward network dimension
    dropout: float = 0.1        # Dropout rate
    max_seq_length: int = 60    # Maximum sequence length (trading days)
    
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

class PositionalEncoding(nn.Module):
    """Positional encoding for transformer input."""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        self.dropout = nn.Dropout(p=0.1)
        
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * 
                           (-np.log(10000.0) / d_model))
        
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
        # x shape: (batch_size, seq_length, input_dim)
        batch_size, seq_length, _ = x.shape
        
        # Project input to model dimension
        x = self.input_projection(x)  # (batch_size, seq_length, d_model)
        
        # Add positional encoding
        x = x.transpose(0, 1)  # (seq_length, batch_size, d_model)
        x = self.pos_encoder(x)
        x = x.transpose(0, 1)  # (batch_size, seq_length, d_model)
        
        # Apply transformer
        transformer_output = self.transformer(x)  # (batch_size, seq_length, d_model)
        
        # Use the last time step for prediction
        last_output = transformer_output[:, -1, :]  # (batch_size, d_model)
        
        # Generate final prediction
        price = self.output_layers(last_output)  # (batch_size, 1)
        
        return price.squeeze(-1)

class SpyderTransformerPricingModel:
    """
    Advanced Transformer-based options pricing model.
    
    Features:
    - Attention-based neural network architecture
    - Learns from historical market data and option prices
    - Captures long-term dependencies and complex patterns
    - Supports real-time pricing and Greeks calculation
    - Model persistence and incremental learning
    """
    
    def __init__(self, config: Optional[TransformerConfig] = None):
        self.config = config or TransformerConfig()
        self.model: Optional[TransformerOptionsPricer] = None
        self.scaler_features = StandardScaler()
        self.scaler_targets = StandardScaler()
        self.feature_columns: List[str] = []
        self.is_trained = False
        self.training_history: Dict[str, List[float]] = {'train_loss': [], 'val_loss': []}
        
    def _prepare_features(self, market_data: pd.DataFrame) -> np.ndarray:
        """
        Prepare input features from market data.
        
        Expected columns in market_data:
        - spot_price, strike_price, time_to_expiry, risk_free_rate, volatility
        - volume, open_interest, bid_ask_spread, delta, gamma, theta, vega
        - vix, term_structure_slope, skew, market_regime
        """
        features = []
        
        # Core option parameters
        features.extend([
            'spot_price', 'strike_price', 'time_to_expiry', 'risk_free_rate',
            'volatility', 'dividend_yield'
        ])
        
        # Market microstructure
        features.extend([
            'volume', 'open_interest', 'bid_ask_spread', 'bid_size', 'ask_size'
        ])
        
        # Greeks (if available)
        greek_columns = ['delta', 'gamma', 'theta', 'vega', 'rho']
        for col in greek_columns:
            if col in market_data.columns:
                features.append(col)
        
        # Market environment indicators
        env_columns = ['vix', 'term_structure_slope', 'skew', 'market_regime']
        for col in env_columns:
            if col in market_data.columns:
                features.append(col)
        
        # Technical indicators
        tech_columns = ['rsi', 'macd', 'bollinger_position', 'volume_ratio']
        for col in tech_columns:
            if col in market_data.columns:
                features.append(col)
        
        # Filter to available columns
        available_features = [col for col in features if col in market_data.columns]
        self.feature_columns = available_features
        
        return market_data[available_features].values
    
    def train(self, 
              market_data: pd.DataFrame, 
              option_prices: pd.Series,
              validation_split: float = 0.2,
              epochs: int = 100,
              batch_size: int = 32,
              learning_rate: float = 0.001):
        """
        Train the Transformer model on historical data.
        
        Args:
            market_data: DataFrame with market features
            option_prices: Series with corresponding option prices
            validation_split: Fraction of data for validation
            epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate for optimizer
        """
        logger.info("Preparing training data...")
        
        # Prepare features and targets
        features = self._prepare_features(market_data)
        targets = option_prices.values.reshape(-1, 1)
        
        # Scale features and targets
        features_scaled = self.scaler_features.fit_transform(features)
        targets_scaled = self.scaler_targets.fit_transform(targets)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            features_scaled, targets_scaled.ravel(), 
            test_size=validation_split, random_state=42, shuffle=False
        )
        
        # Create datasets
        train_dataset = OptionsDataset(X_train, y_train, self.config.max_seq_length)
        val_dataset = OptionsDataset(X_val, y_val, self.config.max_seq_length)
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        # Initialize model
        input_dim = len(self.feature_columns)
        self.model = TransformerOptionsPricer(self.config, input_dim)
        
        # Setup training
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10, factor=0.5)
        
        logger.info(f"Starting training for {epochs} epochs...")
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # Training phase
            self.model.train()
            train_losses = []
            
            for batch_features, batch_targets in train_loader:
                optimizer.zero_grad()
                predictions = self.model(batch_features)
                loss = criterion(predictions, batch_targets)
                loss.backward()
                optimizer.step()
                train_losses.append(loss.item())
            
            # Validation phase
            self.model.eval()
            val_losses = []
            
            with torch.no_grad():
                for batch_features, batch_targets in val_loader:
                    predictions = self.model(batch_features)
                    loss = criterion(predictions, batch_targets)
                    val_losses.append(loss.item())
            
            train_loss = np.mean(train_losses)
            val_loss = np.mean(val_losses)
            
            self.training_history['train_loss'].append(train_loss)
            self.training_history['val_loss'].append(val_loss)
            
            scheduler.step(val_loss)
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}: Train Loss = {train_loss:.6f}, Val Loss = {val_loss:.6f}")
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= 20:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break
        
        self.is_trained = True
        logger.info("Training completed successfully!")
    
    def predict(self, market_data: pd.DataFrame) -> np.ndarray:
        """Predict option prices for given market data."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model must be trained before making predictions")
        
        features = self._prepare_features(market_data)
        features_scaled = self.scaler_features.transform(features)
        
        # Create sequences for prediction
        seq_length = self.config.max_seq_length
        if len(features_scaled) < seq_length:
            # Pad with the first row if insufficient data
            padding = np.repeat(features_scaled[:1], seq_length - len(features_scaled), axis=0)
            features_scaled = np.vstack([padding, features_scaled])
        
        self.model.eval()
        predictions = []
        
        with torch.no_grad():
            for i in range(len(features_scaled) - seq_length + 1):
                sequence = torch.FloatTensor(features_scaled[i:i + seq_length]).unsqueeze(0)
                pred = self.model(sequence)
                predictions.append(pred.item())
        
        # Scale back to original price range
        predictions = np.array(predictions).reshape(-1, 1)
        predictions_scaled = self.scaler_targets.inverse_transform(predictions)
        
        return predictions_scaled.ravel()
    
    def calculate_greeks(self, market_data: pd.DataFrame, epsilon: float = 0.01) -> Dict[str, np.ndarray]:
        """Calculate Greeks using finite differences."""
        base_prices = self.predict(market_data)
        
        greeks = {'price': base_prices}
        
        # Delta (sensitivity to spot price)
        if 'spot_price' in market_data.columns:
            market_data_up = market_data.copy()
            market_data_up['spot_price'] *= (1 + epsilon)
            prices_up = self.predict(market_data_up)
            
            market_data_down = market_data.copy()
            market_data_down['spot_price'] *= (1 - epsilon)
            prices_down = self.predict(market_data_down)
            
            greeks['delta'] = (prices_up - prices_down) / (2 * epsilon * market_data['spot_price'].values)
            greeks['gamma'] = (prices_up - 2 * base_prices + prices_down) / ((epsilon * market_data['spot_price'].values) ** 2)
        
        # Vega (sensitivity to volatility)
        if 'volatility' in market_data.columns:
            market_data_vol_up = market_data.copy()
            market_data_vol_up['volatility'] += epsilon
            prices_vol_up = self.predict(market_data_vol_up)
            greeks['vega'] = (prices_vol_up - base_prices) / epsilon
        
        # Theta (time decay)
        if 'time_to_expiry' in market_data.columns:
            market_data_time = market_data.copy()
            market_data_time['time_to_expiry'] -= 1/365  # One day
            prices_time = self.predict(market_data_time)
            greeks['theta'] = prices_time - base_prices
        
        return greeks
    
    def save_model(self, filepath: str):
        """Save the trained model to disk."""
        if not self.is_trained:
            raise RuntimeError("Cannot save untrained model")
        
        model_data = {
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'scaler_features': self.scaler_features,
            'scaler_targets': self.scaler_targets,
            'feature_columns': self.feature_columns,
            'training_history': self.training_history
        }
        
        torch.save(model_data, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load a trained model from disk."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        model_data = torch.load(filepath, map_location='cpu')
        
        self.config = model_data['config']
        self.scaler_features = model_data['scaler_features']
        self.scaler_targets = model_data['scaler_targets']
        self.feature_columns = model_data['feature_columns']
        self.training_history = model_data['training_history']
        
        # Reconstruct model
        input_dim = len(self.feature_columns)
        self.model = TransformerOptionsPricer(self.config, input_dim)
        self.model.load_state_dict(model_data['model_state_dict'])
        self.model.eval()
        
        self.is_trained = True
        logger.info(f"Model loaded from {filepath}")

def main():
    """Example usage of the SpyderTransformerPricingModel."""
    print("="*60)
    print(" SPYDER - Transformer Options Pricing Model Demonstration")
    print("="*60)
    
    # Generate synthetic training data
    np.random.seed(42)
    n_samples = 5000
    
    # Create synthetic market data
    data = {
        'spot_price': np.random.normal(450, 50, n_samples),
        'strike_price': np.random.normal(450, 60, n_samples),
        'time_to_expiry': np.random.uniform(0.01, 1.0, n_samples),
        'risk_free_rate': np.random.uniform(0.01, 0.06, n_samples),
        'volatility': np.random.uniform(0.1, 0.4, n_samples),
        'dividend_yield': np.random.uniform(0.0, 0.03, n_samples),
        'volume': np.random.lognormal(10, 1, n_samples),
        'open_interest': np.random.lognormal(8, 1, n_samples),
        'bid_ask_spread': np.random.uniform(0.01, 0.5, n_samples),
        'vix': np.random.uniform(12, 35, n_samples)
    }
    
    market_data = pd.DataFrame(data)
    
    # Generate synthetic option prices (simplified Black-Scholes-like)
    from scipy.stats import norm
    
    d1 = (np.log(market_data['spot_price'] / market_data['strike_price']) + 
          (market_data['risk_free_rate'] + 0.5 * market_data['volatility']**2) * market_data['time_to_expiry']) / \
         (market_data['volatility'] * np.sqrt(market_data['time_to_expiry']))
    d2 = d1 - market_data['volatility'] * np.sqrt(market_data['time_to_expiry'])
    
    option_prices = (market_data['spot_price'] * norm.cdf(d1) - 
                    market_data['strike_price'] * np.exp(-market_data['risk_free_rate'] * market_data['time_to_expiry']) * norm.cdf(d2))
    
    # Add some noise to make it more realistic
    option_prices += np.random.normal(0, option_prices * 0.05)
    option_prices = np.maximum(option_prices, 0.01)  # Ensure positive prices
    
    print(f"\n--- Generated {n_samples} synthetic training samples ---")
    print(f"Price range: ${option_prices.min():.2f} - ${option_prices.max():.2f}")
    
    # Initialize and train model
    config = TransformerConfig(
        d_model=64,
        nhead=4,
        num_layers=3,
        dim_feedforward=256,
        max_seq_length=30
    )
    
    model = SpyderTransformerPricingModel(config)
    
    print("\n--- Training Transformer Model ---")
    print("This may take several minutes...")
    
    model.train(
        market_data=market_data,
        option_prices=pd.Series(option_prices),
        epochs=50,
        batch_size=64,
        learning_rate=0.001
    )
    
    # Test predictions
    test_data = market_data.iloc[-100:].copy()
    test_prices_actual = option_prices[-100:]
    
    print("\n--- Testing Model Predictions ---")
    predicted_prices = model.predict(test_data)
    
    mse = np.mean((predicted_prices - test_prices_actual)**2)
    mae = np.mean(np.abs(predicted_prices - test_prices_actual))
    mape = np.mean(np.abs((predicted_prices - test_prices_actual) / test_prices_actual)) * 100
    
    print(f"Test Results:")
    print(f"  Mean Squared Error: {mse:.4f}")
    print(f"  Mean Absolute Error: {mae:.4f}")
    print(f"  Mean Absolute Percentage Error: {mape:.2f}%")
    
    # Calculate Greeks for a sample
    sample_data = test_data.iloc[:5]
    greeks = model.calculate_greeks(sample_data)
    
    print("\n--- Sample Greeks Calculation ---")
    for i in range(5):
        print(f"Option {i+1}:")
        print(f"  Price: ${greeks['price'][i]:.4f}")
        if 'delta' in greeks:
            print(f"  Delta: {greeks['delta'][i]:.4f}")
        if 'vega' in greeks:
            print(f"  Vega: {greeks['vega'][i]:.4f}")
        if 'theta' in greeks:
            print(f"  Theta: {greeks['theta'][i]:.4f}")
    
    print("="*60)

if __name__ == "__main__":
    main()

