#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL13_LSTMPricer.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import inspect
import logging
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from scipy.stats import norm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from torch.utils.data import DataLoader, TensorDataset

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info("Using device: %s", device)


def _secure_torch_load(
    checkpoint_path: str,
    *,
    map_location: Any = None,
) -> Any:
    """Load a PyTorch checkpoint with weights-only deserialization."""
    if "weights_only" not in inspect.signature(torch.load).parameters:
        raise RuntimeError(
            "Secure checkpoint loading requires a PyTorch version with weights_only support"
        )

    load_kwargs: dict[str, Any] = {"weights_only": True}
    if map_location is not None:
        load_kwargs["map_location"] = map_location

    return torch.load(checkpoint_path, **load_kwargs)  # nosec B614


def _serialize_scaler_state(scaler: RobustScaler) -> dict[str, Any]:
    """Serialize fitted RobustScaler state using weights-only-safe types."""
    payload: dict[str, Any] = {}

    for attr_name in ("center_", "scale_"):
        attr_value = getattr(scaler, attr_name, None)
        if attr_value is not None:
            payload[attr_name] = np.asarray(attr_value, dtype=float).tolist()

    for attr_name in ("n_features_in_", "n_samples_seen_"):
        if hasattr(scaler, attr_name):
            payload[attr_name] = int(getattr(scaler, attr_name))

    feature_names = getattr(scaler, "feature_names_in_", None)
    if feature_names is not None:
        payload["feature_names_in_"] = [str(value) for value in feature_names]

    return payload


def _deserialize_scaler_state(payload: dict[str, Any]) -> RobustScaler:
    """Rebuild a fitted RobustScaler from serialized safe state."""
    scaler = RobustScaler()

    for attr_name in ("center_", "scale_"):
        if attr_name in payload:
            setattr(scaler, attr_name, np.asarray(payload[attr_name], dtype=float))

    for attr_name in ("n_features_in_", "n_samples_seen_"):
        if attr_name in payload:
            setattr(scaler, attr_name, int(payload[attr_name]))

    if "feature_names_in_" in payload:
        scaler.feature_names_in_ = np.asarray(payload["feature_names_in_"], dtype=object)

    return scaler


@dataclass
class LSTMConfig:
    """LSTM model configuration."""

    input_features: int = 15
    hidden_size: int = 160
    num_layers: int = 3
    dropout: float = 0.2
    bidirectional: bool = True
    sequence_length: int = 20
    batch_size: int = 64
    learning_rate: float = 0.001
    weight_decay: float = 1e-5
    max_epochs: int = 100
    early_stopping_patience: int = 10
    gradient_clip: float = 1.0


@dataclass
class TrainingMetrics:
    """Training performance metrics."""

    epoch: int
    train_loss: float
    val_loss: float
    train_rmse: float
    val_rmse: float
    improvement_vs_bs: float  # vs Black-Scholes
    training_time: float


class OptionsLSTM(nn.Module):
    """
    LSTM network for options pricing.
    Architecture:
    - Multi-layer bidirectional LSTM
    - Dropout regularization
    - Batch normalization
    - Residual connections
    """

    def __init__(self, config: LSTMConfig):
        super().__init__()
        self.config = config
        # Input batch normalization
        self.input_bn = nn.BatchNorm1d(config.input_features)
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=config.input_features,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            batch_first=True,
            dropout=config.dropout if config.num_layers > 1 else 0,
            bidirectional=config.bidirectional,
        )
        # Calculate output size
        lstm_output_size = config.hidden_size * (2 if config.bidirectional else 1)
        # Attention mechanism
        self.attention = nn.Sequential(
            nn.Linear(lstm_output_size, config.hidden_size),
            nn.Tanh(),
            nn.Linear(config.hidden_size, 1),
        )
        # Output layers
        self.fc1 = nn.Linear(lstm_output_size, config.hidden_size)
        self.bn1 = nn.BatchNorm1d(config.hidden_size)
        self.dropout1 = nn.Dropout(config.dropout)
        self.fc2 = nn.Linear(config.hidden_size, config.hidden_size // 2)
        self.bn2 = nn.BatchNorm1d(config.hidden_size // 2)
        self.dropout2 = nn.Dropout(config.dropout)
        self.fc3 = nn.Linear(config.hidden_size // 2, 1)
        # Activation functions
        self.relu = nn.ReLU()
        self.elu = nn.ELU()
        # Initialize weights
        self._initialize_weights()

    def _initialize_weights(self):
        """Initialize weights using Xavier initialization."""
        for name, param in self.named_parameters():
            if "weight" in name and len(param.shape) >= 2:
                nn.init.xavier_uniform_(param)
            elif "bias" in name:
                nn.init.zeros_(param)

    def forward(self, x):
        """
        Forward pass through the network.
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_features)
        Returns:
            Option prices tensor of shape (batch_size, 1)
        """
        batch_size = x.size(0)
        # Apply batch normalization to each time step
        x_reshaped = x.view(-1, x.size(-1))
        x_normed = self.input_bn(x_reshaped)
        x = x_normed.view(batch_size, -1, x.size(-1))
        # LSTM forward pass
        lstm_out, (h_n, c_n) = self.lstm(x)
        # Apply attention mechanism
        attention_weights = self.attention(lstm_out)
        attention_weights = torch.softmax(attention_weights, dim=1)
        # Weighted sum of LSTM outputs
        context = torch.sum(attention_weights * lstm_out, dim=1)
        # Fully connected layers
        out = self.fc1(context)
        out = self.bn1(out)
        out = self.elu(out)
        out = self.dropout1(out)
        out = self.fc2(out)
        out = self.bn2(out)
        out = self.elu(out)
        out = self.dropout2(out)
        # Output layer (ensure positive prices)
        out = self.fc3(out)
        out = torch.abs(out)  # Ensure positive prices
        return out

    def predict_with_uncertainty(self, x, n_samples=100):
        """
        Predict with uncertainty estimation using dropout.
        Args:
            x: Input tensor
            n_samples: Number of forward passes
        Returns:
            mean_prediction, std_prediction
        """
        self.train()  # Enable dropout
        predictions = []
        with torch.no_grad():
            for _ in range(n_samples):
                pred = self.forward(x)
                predictions.append(pred)
        predictions = torch.stack(predictions)
        mean_pred = predictions.mean(dim=0)
        std_pred = predictions.std(dim=0)
        self.eval()  # Disable dropout
        return mean_pred, std_pred


class SpyderLSTMPricer:
    """
    LSTM-based options pricer with professional features.
    Features:
    - Automated feature engineering
    - Rolling window training
    - Model versioning and persistence
    - Real-time inference optimization
    - Performance comparison vs traditional models
    """

    def __init__(self, config: LSTMConfig | None = None):
        """Initialize LSTM pricer."""
        self.config = config or LSTMConfig()
        self.model = OptionsLSTM(self.config).to(device)
        self.scaler = RobustScaler()  # Robust to outliers
        # Feature configuration based on research
        self.FEATURE_CONFIG = {
            "price_features": ["moneyness", "log_moneyness", "moneyness_squared"],
            "time_features": ["time_to_expiry", "sqrt_time", "time_squared"],
            "volatility_features": ["implied_vol", "historical_vol", "vol_spread"],
            "greek_features": ["delta", "gamma", "vega", "theta"],
            "microstructure_features": ["bid_ask_spread", "volume", "open_interest"],
        }
        # Model state
        self.is_trained = False
        self.training_history = []
        self.feature_importance = {}
        self.model_version = "1.0"
        self.last_training_date = None
        # Performance tracking
        self.inference_times = []
        self.prediction_errors = []

    def prepare_features(self, raw_data: pd.DataFrame) -> np.ndarray:
        """
        Prepare features for LSTM model.
        Args:
            raw_data: DataFrame with option data
        Returns:
            Feature array ready for model input
        """
        features = []
        # Price features
        features.append(raw_data["spot_price"] / raw_data["strike"])  # Moneyness
        features.append(np.log(raw_data["spot_price"] / raw_data["strike"]))
        features.append((raw_data["spot_price"] / raw_data["strike"]) ** 2)
        # Time features
        features.append(raw_data["days_to_expiry"] / 365)
        features.append(np.sqrt(raw_data["days_to_expiry"] / 365))
        features.append((raw_data["days_to_expiry"] / 365) ** 2)
        # Volatility features
        features.append(raw_data["implied_volatility"])
        features.append(raw_data.get("historical_volatility", raw_data["implied_volatility"]))
        features.append(
            raw_data["implied_volatility"]
            - raw_data.get("historical_volatility", raw_data["implied_volatility"])
        )
        # Greeks (if available)
        for greek in ["delta", "gamma", "vega", "theta"]:
            if greek in raw_data.columns:
                features.append(raw_data[greek])
            else:
                # Approximate if not available
                features.append(self._approximate_greek(raw_data, greek))
        # Microstructure features
        features.append(raw_data.get("bid_ask_spread", 0.02))
        features.append(np.log1p(raw_data.get("volume", 1000)))
        features.append(np.log1p(raw_data.get("open_interest", 100)))
        # Option type encoding
        features.append((raw_data["option_type"] == "call").astype(float))
        # Stack features
        feature_array = np.column_stack(features)
        return feature_array

    def create_sequences(
        self, features: np.ndarray, targets: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for LSTM training.
        Args:
            features: Feature array
            targets: Target prices
        Returns:
            Sequences and corresponding targets
        """
        seq_length = self.config.sequence_length
        sequences = []
        sequence_targets = []
        for i in range(len(features) - seq_length):
            seq = features[i : i + seq_length]
            target = targets[i + seq_length]
            sequences.append(seq)
            sequence_targets.append(target)
        return np.array(sequences), np.array(sequence_targets)

    async def train(
        self, training_data: pd.DataFrame, validation_split: float = 0.2
    ) -> TrainingMetrics:
        """
        Train LSTM model on options data.
        Args:
            training_data: DataFrame with option prices and features
            validation_split: Fraction for validation
        Returns:
            Training metrics
        """
        logger.info("Starting LSTM training")
        start_time = datetime.now(UTC)
        # Prepare features
        features = self.prepare_features(training_data)
        targets = training_data["option_price"].values
        # Normalize features
        features_scaled = self.scaler.fit_transform(features)
        # Create sequences
        X_seq, y_seq = self.create_sequences(features_scaled, targets)
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X_seq, y_seq, test_size=validation_split, shuffle=False
        )
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train).to(device)
        y_train_tensor = torch.FloatTensor(y_train).unsqueeze(1).to(device)
        X_val_tensor = torch.FloatTensor(X_val).to(device)
        y_val_tensor = torch.FloatTensor(y_val).unsqueeze(1).to(device)
        # Create data loaders
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
        train_loader = DataLoader(train_dataset, batch_size=self.config.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=self.config.batch_size, shuffle=False)
        # Initialize optimizer and loss
        optimizer = optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        # Learning rate scheduler
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", patience=5, factor=0.5
        )
        # Custom loss function for options
        criterion = self._options_loss_function()
        # Training loop
        best_val_loss = float("inf")
        patience_counter = 0
        for epoch in range(self.config.max_epochs):
            # Training phase
            self.model.train()
            train_losses = []
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                # Forward pass
                predictions = self.model(batch_X)
                loss = criterion(predictions, batch_y)
                # Backward pass
                loss.backward()
                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.gradient_clip)
                optimizer.step()
                train_losses.append(loss.item())
            # Validation phase
            self.model.eval()
            val_losses = []
            val_predictions = []
            val_actuals = []
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    predictions = self.model(batch_X)
                    loss = criterion(predictions, batch_y)
                    val_losses.append(loss.item())
                    val_predictions.extend(predictions.cpu().numpy())
                    val_actuals.extend(batch_y.cpu().numpy())
            # Calculate metrics
            train_loss = np.mean(train_losses)
            val_loss = np.mean(val_losses)
            train_rmse = np.sqrt(train_loss)
            val_rmse = np.sqrt(val_loss)
            # Calculate improvement vs Black-Scholes
            bs_rmse = self._calculate_black_scholes_rmse(training_data)
            improvement = (bs_rmse - val_rmse) / bs_rmse * 100
            # Update learning rate
            scheduler.step(val_loss)
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model
                self._save_checkpoint("best_model.pth")
            else:
                patience_counter += 1
            if patience_counter >= self.config.early_stopping_patience:
                logger.info("Early stopping at epoch %s", epoch)
                break
            # Log progress
            if epoch % 10 == 0:
                logger.info(
                    f"Epoch {epoch}: Train Loss={train_loss:.4f}, "
                    f"Val Loss={val_loss:.4f}, "
                    f"Improvement vs BS={improvement:.1f}%"
                )
        # Load best model
        self._load_checkpoint("best_model.pth")
        # Final metrics
        training_time = (datetime.now(UTC) - start_time).total_seconds()
        final_metrics = TrainingMetrics(
            epoch=epoch,
            train_loss=train_loss,
            val_loss=val_loss,
            train_rmse=train_rmse,
            val_rmse=val_rmse,
            improvement_vs_bs=improvement,
            training_time=training_time,
        )
        # Update model state
        self.is_trained = True
        self.last_training_date = datetime.now(UTC)
        self.training_history.append(final_metrics)
        logger.info(
            f"Training complete - Val RMSE: {val_rmse:.4f}, " f"Improvement: {improvement:.1f}%"
        )
        return final_metrics

    def predict(self, option_data: pd.DataFrame, return_uncertainty: bool = False) -> np.ndarray:
        """
        Predict option prices using trained model.
        Args:
            option_data: DataFrame with option features
            return_uncertainty: Whether to return uncertainty estimates
        Returns:
            Predicted prices (and uncertainties if requested)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        start_time = datetime.now(UTC)
        # Prepare features
        features = self.prepare_features(option_data)
        features_scaled = self.scaler.transform(features)
        # Create sequences (use last sequence_length points)
        if len(features_scaled) >= self.config.sequence_length:
            sequences = []
            for i in range(len(features_scaled) - self.config.sequence_length + 1):
                seq = features_scaled[i : i + self.config.sequence_length]
                sequences.append(seq)
            sequences = np.array(sequences)
        else:
            # Pad if necessary
            padding = self.config.sequence_length - len(features_scaled)
            sequences = np.pad(features_scaled, ((padding, 0), (0, 0)), mode="edge").reshape(
                1, self.config.sequence_length, -1
            )
        # Convert to tensor
        X_tensor = torch.FloatTensor(sequences).to(device)
        # Predict
        self.model.eval()
        if return_uncertainty:
            with torch.no_grad():
                predictions, uncertainties = self.model.predict_with_uncertainty(X_tensor)
                predictions = predictions.cpu().numpy().flatten()
                uncertainties = uncertainties.cpu().numpy().flatten()
            # Track inference time
            inference_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            self.inference_times.append(inference_time)
            return predictions, uncertainties
        else:
            with torch.no_grad():
                predictions = self.model(X_tensor)
                predictions = predictions.cpu().numpy().flatten()
            # Track inference time
            inference_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
            self.inference_times.append(inference_time)
            return predictions

    def _options_loss_function(self):
        """
        Custom loss function for options pricing.
        Combines:
        - MSE for accurate pricing
        - Asymmetric penalty for underpricing
        - Moneyness-weighted errors
        """

        def loss_fn(predictions, targets):
            # Basic MSE
            mse = torch.mean((predictions - targets) ** 2)
            # Asymmetric penalty (underpricing is worse)
            errors = predictions - targets
            underpricing_penalty = torch.mean(torch.where(errors < 0, errors**2 * 1.5, errors**2))
            # Combine losses
            total_loss = 0.7 * mse + 0.3 * underpricing_penalty
            return total_loss

        return loss_fn

    def _approximate_greek(self, data: pd.DataFrame, greek: str) -> np.ndarray:
        """Approximate Greeks if not provided."""
        # Simplified approximations
        moneyness = data["spot_price"] / data["strike"]
        time_to_expiry = data["days_to_expiry"] / 365
        if greek == "delta":
            # Rough delta approximation
            if "option_type" in data.columns:
                call_mask = data["option_type"] == "call"
                delta = np.where(
                    call_mask,
                    np.clip(0.5 + 0.5 * (moneyness - 1), 0, 1),
                    np.clip(-0.5 + 0.5 * (1 - moneyness), -1, 0),
                )
            else:
                delta = np.clip(0.5 + 0.5 * (moneyness - 1), 0, 1)
            return delta
        elif greek == "gamma":
            # Peak gamma at ATM
            return 0.4 * np.exp(-2 * (moneyness - 1) ** 2) / np.sqrt(time_to_expiry)
        elif greek == "vega":
            # Vega proportional to time and ATM-ness
            return 0.3 * np.sqrt(time_to_expiry) * np.exp(-((moneyness - 1) ** 2))
        elif greek == "theta":
            # Theta decay
            return -0.1 / np.sqrt(time_to_expiry)
        return np.zeros(len(data))

    def _calculate_black_scholes_rmse(self, data: pd.DataFrame) -> float:
        """Calculate RMSE for Black-Scholes baseline."""
        bs_prices = []
        actual_prices = data["option_price"].values
        for _, row in data.iterrows():
            S = row["spot_price"]
            K = row["strike"]
            T = row["days_to_expiry"] / 365
            r = 0.05  # Risk-free rate
            sigma = row["implied_volatility"]
            # Black-Scholes formula
            if T > 0:
                d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
                d2 = d1 - sigma * np.sqrt(T)
                if row.get("option_type", "call") == "call":
                    price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
                else:
                    price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            else:
                # At expiration
                if row.get("option_type", "call") == "call":
                    price = max(S - K, 0)
                else:
                    price = max(K - S, 0)
            bs_prices.append(price)
        bs_prices = np.array(bs_prices)
        rmse = np.sqrt(np.mean((bs_prices - actual_prices) ** 2))
        return rmse

    def _save_checkpoint(self, filename: str):
        """Save model checkpoint."""
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "config": asdict(self.config),
            "scaler_state": _serialize_scaler_state(self.scaler),
            "is_trained": self.is_trained,
            "model_version": self.model_version,
            "training_history": [asdict(metrics) for metrics in self.training_history],
        }
        torch.save(checkpoint, filename)

    def _load_checkpoint(self, filename: str):
        """Load model checkpoint."""
        checkpoint = _secure_torch_load(filename, map_location=device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        config_payload = checkpoint.get("config", {})
        if not isinstance(config_payload, dict):
            raise ValueError("Unsupported checkpoint config format")
        self.config = LSTMConfig(**config_payload)

        scaler_payload = checkpoint.get("scaler_state", {})
        if not isinstance(scaler_payload, dict):
            raise ValueError("Unsupported checkpoint scaler format")
        self.scaler = _deserialize_scaler_state(scaler_payload)

        self.is_trained = bool(checkpoint.get("is_trained", False))
        self.model_version = str(checkpoint.get("model_version", self.model_version))

        history_payload = checkpoint.get("training_history", [])
        if not isinstance(history_payload, list):
            raise ValueError("Unsupported checkpoint training history format")
        self.training_history = [
            TrainingMetrics(**item)
            for item in history_payload
            if isinstance(item, dict)
        ]

    def analyze_feature_importance(self, validation_data: pd.DataFrame) -> dict[str, float]:
        """
        Analyze feature importance using permutation.
        Args:
            validation_data: Validation dataset
        Returns:
            Feature importance scores
        """
        if not self.is_trained:
            raise ValueError("Model must be trained first")
        # Get baseline performance
        baseline_predictions = self.predict(validation_data)
        baseline_rmse = np.sqrt(
            np.mean((baseline_predictions - validation_data["option_price"].values) ** 2)
        )
        feature_importance = {}
        feature_names = list(self.FEATURE_CONFIG.values())
        feature_names = [item for sublist in feature_names for item in sublist]
        # Permutation importance
        for _i, feature_group in enumerate(self.FEATURE_CONFIG.keys()):
            # Permute feature group
            permuted_data = validation_data.copy()
            # Shuffle relevant columns
            for col in self.FEATURE_CONFIG[feature_group]:
                if col in permuted_data.columns:
                    permuted_data[col] = np.random.permutation(permuted_data[col])
            # Get new predictions
            permuted_predictions = self.predict(permuted_data)
            permuted_rmse = np.sqrt(
                np.mean((permuted_predictions - validation_data["option_price"].values) ** 2)
            )
            # Calculate importance
            importance = (permuted_rmse - baseline_rmse) / baseline_rmse
            feature_importance[feature_group] = importance
        # Normalize to sum to 1
        total_importance = sum(feature_importance.values())
        if total_importance > 0:
            feature_importance = {k: v / total_importance for k, v in feature_importance.items()}
        self.feature_importance = feature_importance
        return feature_importance

    def get_model_diagnostics(self) -> dict[str, Any]:
        """Get comprehensive model diagnostics."""
        diagnostics = {
            "model_info": {
                "version": self.model_version,
                "is_trained": self.is_trained,
                "last_training": self.last_training_date,
                "total_parameters": sum(p.numel() for p in self.model.parameters()),
                "device": str(device),
            },
            "performance": {
                "avg_inference_time_ms": (
                    np.mean(self.inference_times[-100:]) if self.inference_times else 0
                ),
                "feature_importance": self.feature_importance,
            },
            "architecture": {
                "input_features": self.config.input_features,
                "hidden_size": self.config.hidden_size,
                "num_layers": self.config.num_layers,
                "sequence_length": self.config.sequence_length,
            },
        }
        if self.training_history:
            latest = self.training_history[-1]
            diagnostics["training"] = {
                "final_val_rmse": latest.val_rmse,
                "improvement_vs_bs": latest.improvement_vs_bs,
                "training_time_seconds": latest.training_time,
                "epochs_trained": latest.epoch,
            }
        return diagnostics

    async def incremental_update(self, new_data: pd.DataFrame):
        """
        Incrementally update model with new data.
        Args:
            new_data: New option data for updating
        """
        logger.info("Incremental update with %s new samples", len(new_data))
        # Simple fine-tuning approach
        # In production, would use more sophisticated online learning
        # Reduce learning rate for fine-tuning
        original_lr = self.config.learning_rate
        self.config.learning_rate = original_lr * 0.1
        # Train for fewer epochs
        original_epochs = self.config.max_epochs
        self.config.max_epochs = 10
        # Fine-tune
        await self.train(new_data, validation_split=0.1)
        # Restore original config
        self.config.learning_rate = original_lr
        self.config.max_epochs = original_epochs
        logger.info("Incremental update complete")


async def main():
    """Example usage of LSTM pricer."""
    # Initialize LSTM pricer
    lstm_pricer = SpyderLSTMPricer()
    # Generate synthetic training data
    np.random.seed(42)
    n_samples = 10000
    # Create realistic option data
    training_data = pd.DataFrame(
        {
            "spot_price": np.random.uniform(440, 460, n_samples),
            "strike": np.random.choice(np.arange(430, 470, 5), n_samples),
            "days_to_expiry": np.random.choice([7, 14, 30, 45, 60], n_samples),
            "implied_volatility": np.random.uniform(0.15, 0.35, n_samples),
            "option_type": np.random.choice(["call", "put"], n_samples),
            "volume": np.random.lognormal(8, 1.5, n_samples),
            "open_interest": np.random.lognormal(7, 1.5, n_samples),
            "bid_ask_spread": np.random.uniform(0.01, 0.05, n_samples),
        }
    )
    # Calculate synthetic option prices (Black-Scholes + noise)
    option_prices = []
    for _, row in training_data.iterrows():
        S = row["spot_price"]
        K = row["strike"]
        T = row["days_to_expiry"] / 365
        r = 0.05
        sigma = row["implied_volatility"]
        # Black-Scholes
        d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if row["option_type"] == "call":
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        # Add realistic noise
        noise = np.random.normal(0, price * 0.05)  # 5% noise
        option_prices.append(max(0.01, price + noise))
    training_data["option_price"] = option_prices
    logging.info("=== LSTM Options Pricer ===")
    logging.info("Training samples: %s", len(training_data))
    logging.info("Device: %s", device)
    # Train model
    logging.info("\n=== Training Model ===")
    metrics = await lstm_pricer.train(training_data, validation_split=0.2)
    logging.info("\nTraining Results:")
    logging.info(f"Final Validation RMSE: ${metrics.val_rmse:.3f}")
    logging.info(f"Improvement vs Black-Scholes: {metrics.improvement_vs_bs:.1f}%")
    logging.info(f"Training Time: {metrics.training_time:.1f} seconds")
    # Test predictions
    logging.info("\n=== Testing Predictions ===")
    # Create test data
    test_data = pd.DataFrame(
        {
            "spot_price": [450, 450, 450],
            "strike": [445, 450, 455],
            "days_to_expiry": [30, 30, 30],
            "implied_volatility": [0.20, 0.20, 0.20],
            "option_type": ["put", "call", "call"],
            "volume": [1000, 2000, 1500],
            "open_interest": [5000, 10000, 7500],
            "bid_ask_spread": [0.02, 0.02, 0.02],
        }
    )
    # Make predictions
    predictions, uncertainties = lstm_pricer.predict(test_data, return_uncertainty=True)
    logging.info("\nPredictions:")
    for i, row in test_data.iterrows():
        logging.info(
            f"{row['option_type'].upper()} Strike {row['strike']}: "
            f"${predictions[i]:.2f} ± ${uncertainties[i]:.2f}"
        )
    # Analyze feature importance
    logging.info("\n=== Feature Importance ===")
    importance = lstm_pricer.analyze_feature_importance(training_data.iloc[:1000])
    for feature, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
        logging.info(f"{feature}: {score:.1%}")
    # Get model diagnostics
    logging.info("\n=== Model Diagnostics ===")
    diagnostics = lstm_pricer.get_model_diagnostics()
    logging.info("Model Version: %s", diagnostics['model_info']['version'])
    logging.info(f"Total Parameters: {diagnostics['model_info']['total_parameters']:,}")
    logging.info(f"Average Inference Time: {diagnostics['performance']['avg_inference_time_ms']:.1f} ms")  # noqa: E501
    if "training" in diagnostics:
        logging.info(f"Final Validation RMSE: ${diagnostics['training']['final_val_rmse']:.3f}")
        logging.info(f"Improvement vs BS: {diagnostics['training']['improvement_vs_bs']:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
