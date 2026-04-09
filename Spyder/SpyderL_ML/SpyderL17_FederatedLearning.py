#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL17_FederatedLearning.py
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
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import asyncio
import threading
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pickle
import secrets

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from collections import defaultdict
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from flask import Flask, request, jsonify
import requests
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Federated learning parameters
DEFAULT_ROUNDS = 100
MIN_CLIENTS_PER_ROUND = 2
CLIENT_FRACTION = 0.5  # Fraction of clients selected per round
LOCAL_EPOCHS = 5
LOCAL_BATCH_SIZE = 32
LEARNING_RATE = 0.001

# Privacy parameters
EPSILON = 1.0  # Differential privacy budget
DELTA = 1e-5  # Differential privacy delta
NOISE_MULTIPLIER = 1.1
CLIP_NORM = 1.0

# Security parameters
KEY_SIZE = 2048  # RSA key size
SECURE_AGGREGATION_THRESHOLD = 3  # Minimum clients for secure aggregation

# Model parameters
MODEL_VERSION = "1.0"
SUPPORTED_MODELS = ["lstm_pricer", "ml_predictor", "sentiment", "risk"]

# Communication parameters
DEFAULT_PORT = 5555
TIMEOUT = 300  # seconds
MAX_RETRIES = 3


# ==============================================================================
# ENUMS
# ==============================================================================
class ClientRole(Enum):
    """Roles in federated learning system"""

    COORDINATOR = "coordinator"
    PARTICIPANT = "participant"
    VALIDATOR = "validator"
    OBSERVER = "observer"


class AggregationMethod(Enum):
    """Model aggregation methods"""

    FEDERATED_AVERAGING = "fedavg"
    WEIGHTED_AVERAGE = "weighted_avg"
    MEDIAN = "median"
    TRIMMED_MEAN = "trimmed_mean"
    KRUM = "krum"
    MULTI_KRUM = "multi_krum"


class PrivacyMechanism(Enum):
    """Privacy preservation mechanisms"""

    NONE = "none"
    DIFFERENTIAL_PRIVACY = "dp"
    HOMOMORPHIC_ENCRYPTION = "he"
    SECURE_MULTIPARTY = "smpc"


class ModelType(Enum):
    """Types of models for federated learning"""

    PRICE_PREDICTION = "price_prediction"
    VOLATILITY_SURFACE = "volatility_surface"
    RISK_ASSESSMENT = "risk_assessment"
    STRATEGY_OPTIMIZATION = "strategy_optimization"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ClientConfig:
    """Configuration for federated learning client"""

    client_id: str
    role: ClientRole
    host: str
    port: int
    public_key: bytes | None = None
    model_types: list[ModelType] = field(default_factory=list)
    privacy_budget: float = EPSILON
    min_data_points: int = 1000
    max_batch_size: int = 64


@dataclass
class FederatedModel:
    """Federated model wrapper"""

    model_type: ModelType
    architecture: nn.Module
    version: str
    global_rounds: int = 0
    participants: list[str] = field(default_factory=list)
    performance_history: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelUpdate:
    """Model update from client"""

    client_id: str
    round_number: int
    model_weights: dict[str, torch.Tensor]
    num_samples: int
    metrics: dict[str, float]
    timestamp: datetime
    signature: bytes | None = None


@dataclass
class AggregationResult:
    """Result of model aggregation"""

    round_number: int
    aggregated_weights: dict[str, torch.Tensor]
    participating_clients: list[str]
    aggregation_method: AggregationMethod
    metrics: dict[str, float]
    privacy_spent: float
    timestamp: datetime


@dataclass
class FederatedRound:
    """Information about a federated learning round"""

    round_number: int
    selected_clients: list[str]
    model_updates: list[ModelUpdate]
    aggregation_result: AggregationResult | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    success: bool = False


# ==============================================================================
# DIFFERENTIAL PRIVACY
# ==============================================================================
class DifferentialPrivacy:
    """Differential privacy mechanisms for federated learning"""

    def __init__(
        self,
        epsilon: float = EPSILON,
        delta: float = DELTA,
        clip_norm: float = CLIP_NORM,
    ):
        self.epsilon = epsilon
        self.delta = delta
        self.clip_norm = clip_norm
        self.noise_multiplier = self._calculate_noise_multiplier()
        self.privacy_spent = 0.0

    def _calculate_noise_multiplier(self) -> float:
        """Calculate noise multiplier for given privacy budget"""
        # Simplified calculation - in production use more sophisticated methods
        return NOISE_MULTIPLIER * (1.0 / self.epsilon)

    def add_noise_to_gradients(
        self, gradients: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        """Add Gaussian noise to gradients for differential privacy"""
        noisy_gradients = {}

        for name, grad in gradients.items():
            # Clip gradients
            grad_norm = torch.norm(grad)
            if grad_norm > self.clip_norm:
                grad = grad * (self.clip_norm / grad_norm)

            # Add Gaussian noise
            noise = torch.randn_like(grad) * self.noise_multiplier * self.clip_norm
            noisy_gradients[name] = grad + noise

        # Update privacy budget
        self.privacy_spent += self.epsilon / DEFAULT_ROUNDS

        return noisy_gradients

    def add_noise_to_weights(
        self, weights: dict[str, torch.Tensor], sensitivity: float = 1.0
    ) -> dict[str, torch.Tensor]:
        """Add Laplace noise to model weights"""
        noisy_weights = {}

        for name, weight in weights.items():
            # Calculate noise scale
            noise_scale = sensitivity / self.epsilon

            # Add Laplace noise
            noise = torch.from_numpy(
                np.random.laplace(0, noise_scale, weight.shape)
            ).float()

            noisy_weights[name] = weight + noise

        return noisy_weights

    def clip_weights(self, weights: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        """Clip weights to bound sensitivity"""
        clipped_weights = {}

        for name, weight in weights.items():
            weight_norm = torch.norm(weight)
            if weight_norm > self.clip_norm:
                clipped_weights[name] = weight * (self.clip_norm / weight_norm)
            else:
                clipped_weights[name] = weight

        return clipped_weights

    def get_privacy_spent(self) -> float:
        """Get total privacy budget spent"""
        return self.privacy_spent

    def remaining_budget(self) -> float:
        """Get remaining privacy budget"""
        return max(0, self.epsilon - self.privacy_spent)


# ==============================================================================
# SECURE AGGREGATION
# ==============================================================================
class SecureAggregator:
    """Secure aggregation protocol for federated learning"""

    def __init__(self, threshold: int = SECURE_AGGREGATION_THRESHOLD):
        self.threshold = threshold
        self.logger = SpyderLogger.get_logger(__name__)

    def generate_masks(self, num_clients: int) -> dict[str, np.ndarray]:
        """Generate pairwise masks for secure aggregation"""
        masks = {}

        # Generate random seeds for each pair of clients
        for i in range(num_clients):
            for j in range(i + 1, num_clients):
                # Shared random seed between clients i and j
                seed = secrets.randbelow(2**32)
                np.random.seed(seed)

                # Generate mask
                mask_shape = (1000,)  # Simplified - would match model shape
                mask = np.random.normal(0, 1, mask_shape)

                # Store mask with direction
                masks[f"{i}->{j}"] = mask
                masks[f"{j}->{i}"] = -mask  # Opposite direction

        return masks

    def secure_aggregate(
        self, updates: list[ModelUpdate], masks: dict[str, np.ndarray]
    ) -> dict[str, torch.Tensor]:
        """Perform secure aggregation of model updates"""
        if len(updates) < self.threshold:
            raise ValueError(
                f"Need at least {self.threshold} clients for secure aggregation"
            )

        # Initialize aggregated weights
        aggregated = {}

        # Get first update as template
        template = updates[0].model_weights

        for param_name in template:
            # Sum all updates
            param_sum = torch.zeros_like(template[param_name])

            for update in updates:
                param_sum += update.model_weights[param_name]

            # Average
            aggregated[param_name] = param_sum / len(updates)

        return aggregated

    def verify_aggregation(
        self, aggregated: dict[str, torch.Tensor], updates: list[ModelUpdate]
    ) -> bool:
        """Verify integrity of aggregation"""
        # Simplified verification - check dimensions match
        for update in updates:
            for param_name, param in update.model_weights.items():
                if param_name not in aggregated:
                    return False
                if param.shape != aggregated[param_name].shape:
                    return False

        return True


# ==============================================================================
# FEDERATED CLIENT
# ==============================================================================
class FederatedClient:
    """Client participant in federated learning"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.logger = SpyderLogger.get_logger(f"FederatedClient_{config.client_id}")
        self.error_handler = SpyderErrorHandler()

        # Privacy mechanisms
        self.privacy = DifferentialPrivacy(epsilon=config.privacy_budget)

        # Models
        self.local_models = {}
        self.model_versions = {}

        # Data
        self.local_data = {}
        self.data_stats = {}

        # Security
        self.private_key = None
        self.public_key = None
        self._generate_keys()

        # Communication
        self.coordinator_url = None
        self.is_active = False

        # Metrics
        self.rounds_participated = 0
        self.total_updates_sent = 0

        self.logger.info("Federated client %s initialized", config.client_id)

    def _generate_keys(self):
        """Generate RSA key pair for secure communication"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=KEY_SIZE
        )
        self.public_key = self.private_key.public_key()

        # Store public key in config
        self.config.public_key = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def register_with_coordinator(self, coordinator_url: str) -> bool:
        """Register client with federated learning coordinator"""
        try:
            self.coordinator_url = coordinator_url

            registration_data = {
                "client_id": self.config.client_id,
                "role": self.config.role.value,
                "model_types": [mt.value for mt in self.config.model_types],
                "public_key": self.config.public_key.decode("utf-8"),
                "min_data_points": self.config.min_data_points,
            }

            response = requests.post(
                f"{coordinator_url}/register", json=registration_data, timeout=TIMEOUT
            )

            if response.status_code == 200:
                self.is_active = True
                self.logger.info("Successfully registered with coordinator")
                return True
            else:
                self.logger.error("Registration failed: %s", response.text)
                return False

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "register_with_coordinator"})
            return False

    def load_local_data(self, data: pd.DataFrame, model_type: ModelType):
        """Load local training data"""
        try:
            # Store data
            self.local_data[model_type] = data

            # Calculate statistics
            self.data_stats[model_type] = {
                "num_samples": len(data),
                "features": list(data.columns),
                "date_range": (data.index.min(), data.index.max()),
                "mean_values": data.mean().to_dict(),
                "std_values": data.std().to_dict(),
            }

            self.logger.info("Loaded %s samples for %s", len(data), model_type.value)

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "load_local_data"})

    def train_local_model(
        self,
        model_type: ModelType,
        global_weights: dict[str, torch.Tensor],
        round_number: int,
    ) -> ModelUpdate:
        """Train model locally on private data"""
        try:
            self.logger.info("Starting local training for round %s", round_number)

            # Get or create model
            if model_type not in self.local_models:
                self.local_models[model_type] = self._create_model(model_type)

            model = self.local_models[model_type]

            # Load global weights
            model.load_state_dict(global_weights)

            # Get local data
            if model_type not in self.local_data:
                raise ValueError(f"No local data for {model_type.value}")

            data = self.local_data[model_type]

            # Prepare data loader
            X, y = self._prepare_training_data(data, model_type)
            dataset = TensorDataset(torch.FloatTensor(X), torch.FloatTensor(y))
            loader = DataLoader(dataset, batch_size=LOCAL_BATCH_SIZE, shuffle=True)

            # Training setup
            optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
            criterion = nn.MSELoss()

            # Local training
            model.train()
            total_loss = 0
            num_batches = 0

            for _epoch in range(LOCAL_EPOCHS):
                epoch_loss = 0

                for batch_X, batch_y in loader:
                    optimizer.zero_grad()

                    # Forward pass
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)

                    # Backward pass
                    loss.backward()

                    # Clip gradients for privacy
                    torch.nn.utils.clip_grad_norm_(
                        model.parameters(), self.privacy.clip_norm
                    )

                    optimizer.step()

                    epoch_loss += loss.item()
                    num_batches += 1

                total_loss += epoch_loss

            # Get model updates (difference from global model)
            model_updates = {}
            for name, param in model.named_parameters():
                if name in global_weights:
                    update = param.data - global_weights[name]
                    # Add differential privacy noise
                    if self.config.role != ClientRole.VALIDATOR:
                        update = self.privacy.add_noise_to_gradients({name: update})[
                            name
                        ]
                    model_updates[name] = update

            # Calculate metrics
            avg_loss = total_loss / (num_batches * LOCAL_EPOCHS)

            # Create model update
            update = ModelUpdate(
                client_id=self.config.client_id,
                round_number=round_number,
                model_weights=model_updates,
                num_samples=len(data),
                metrics={
                    "loss": avg_loss,
                    "privacy_spent": self.privacy.get_privacy_spent(),
                },
                timestamp=datetime.now(),
            )

            # Sign update
            update.signature = self._sign_update(update)

            self.rounds_participated += 1
            self.total_updates_sent += 1

            return update

        except Exception as e:
            self.error_handler.handle_error(
                e,
                {
                    "method": "train_local_model",
                    "model_type": model_type.value,
                    "round": round_number,
                },
            )
            return None

    def _create_model(self, model_type: ModelType) -> nn.Module:
        """Create model based on type"""
        if model_type == ModelType.PRICE_PREDICTION:
            # Simple price prediction model
            return nn.Sequential(
                nn.Linear(20, 64),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(32, 1),
            )
        elif model_type == ModelType.VOLATILITY_SURFACE:
            # Volatility surface model
            return nn.Sequential(
                nn.Linear(10, 128),
                nn.ReLU(),
                nn.BatchNorm1d(128),
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(64, 30),  # Output for surface grid
            )
        else:
            # Default model
            return nn.Sequential(
                nn.Linear(15, 32),
                nn.ReLU(),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 1),
            )

    def _prepare_training_data(
        self, data: pd.DataFrame, model_type: ModelType
    ) -> tuple[np.ndarray, np.ndarray]:
        """Prepare data for training"""
        # Simplified data preparation
        if model_type == ModelType.PRICE_PREDICTION:
            # Use recent prices to predict next price
            features = ["open", "high", "low", "close", "volume"]
            X = data[features].values[:-1]
            y = data["close"].values[1:].reshape(-1, 1)
        else:
            # Generic preparation
            X = data.iloc[:, :-1].values
            y = data.iloc[:, -1].values.reshape(-1, 1)

        return X, y

    def _sign_update(self, update: ModelUpdate) -> bytes:
        """Sign model update for authenticity"""
        # Create hash of update
        update_bytes = pickle.dumps(  # noqa: S301 — network binary payload, not stored/loaded as pickle
            {
                "client_id": update.client_id,
                "round_number": update.round_number,
                "num_samples": update.num_samples,
            }
        )

        # Sign hash
        signature = self.private_key.sign(
            update_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )

        return signature

    def validate_global_model(
        self, global_weights: dict[str, torch.Tensor], model_type: ModelType
    ) -> dict[str, float]:
        """Validate global model on local test data"""
        try:
            if model_type not in self.local_models:
                self.local_models[model_type] = self._create_model(model_type)

            model = self.local_models[model_type]
            model.load_state_dict(global_weights)
            model.eval()

            # Get test data (last 20% of local data)
            data = self.local_data.get(model_type)
            if data is None:
                return {}

            split_idx = int(len(data) * 0.8)
            test_data = data.iloc[split_idx:]

            X_test, y_test = self._prepare_training_data(test_data, model_type)
            X_test = torch.FloatTensor(X_test)
            y_test = torch.FloatTensor(y_test)

            # Evaluate
            with torch.no_grad():
                predictions = model(X_test)
                mse = nn.MSELoss()(predictions, y_test).item()
                mae = torch.mean(torch.abs(predictions - y_test)).item()

            # Calculate additional metrics
            y_pred = predictions.numpy()
            y_true = y_test.numpy()

            r2 = 1 - (
                np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2)
            )

            metrics = {
                "mse": mse,
                "mae": mae,
                "rmse": np.sqrt(mse),
                "r2": r2,
                "test_samples": len(test_data),
            }

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "validate_global_model"})
            return {}

    def get_client_stats(self) -> dict[str, Any]:
        """Get client statistics"""
        return {
            "client_id": self.config.client_id,
            "role": self.config.role.value,
            "rounds_participated": self.rounds_participated,
            "total_updates_sent": self.total_updates_sent,
            "privacy_remaining": self.privacy.remaining_budget(),
            "data_stats": self.data_stats,
            "active": self.is_active,
        }


# ==============================================================================
# FEDERATED COORDINATOR
# ==============================================================================
class FederatedCoordinator:
    """Coordinator for federated learning across multiple clients"""

    def __init__(self, config: dict[str, Any] | None = None):
        self.logger = SpyderLogger.get_logger("FederatedCoordinator")
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Registered clients
        self.clients: dict[str, ClientConfig] = {}
        self.client_public_keys = {}

        # Models
        self.global_models: dict[ModelType, FederatedModel] = {}
        self.model_aggregators = {}

        # Rounds
        self.current_round = 0
        self.round_history: list[FederatedRound] = []

        # Security
        self.secure_aggregator = SecureAggregator()

        # Configuration
        self.min_clients = self.config.get("min_clients", MIN_CLIENTS_PER_ROUND)
        self.client_fraction = self.config.get("client_fraction", CLIENT_FRACTION)
        self.aggregation_method = AggregationMethod.FEDERATED_AVERAGING

        # Flask app for communication
        self.app = Flask(__name__)
        self._setup_routes()

        # Performance tracking
        self.performance_history = defaultdict(list)

        self.logger.info("Federated Coordinator initialized")

    def _setup_routes(self):
        """Setup Flask routes for client communication"""

        @self.app.route("/register", methods=["POST"])
        def register_client():
            try:
                data = request.json
                client_config = ClientConfig(
                    client_id=data["client_id"],
                    role=ClientRole(data["role"]),
                    host=request.remote_addr,
                    port=5556,  # Default client port
                    public_key=data["public_key"].encode("utf-8"),
                    model_types=[ModelType(mt) for mt in data["model_types"]],
                )

                self.register_client(client_config)

                return jsonify({"status": "success", "message": "Client registered"})

            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 400

        @self.app.route("/submit_update", methods=["POST"])
        def submit_update():
            try:
                data = request.json
                # Deserialize model update
                update = self._deserialize_update(data)

                # Store update for current round
                self._store_client_update(update)

                return jsonify({"status": "success", "message": "Update received"})

            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 400

        @self.app.route("/get_global_model/<model_type>", methods=["GET"])
        def get_global_model(model_type):
            try:
                mt = ModelType(model_type)
                if mt not in self.global_models:
                    return (
                        jsonify({"status": "error", "message": "Model not found"}),
                        404,
                    )

                model = self.global_models[mt]
                weights = {
                    k: v.tolist() for k, v in model.architecture.state_dict().items()
                }

                return jsonify(
                    {
                        "status": "success",
                        "model_weights": weights,
                        "version": model.version,
                        "round": self.current_round,
                    }
                )

            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 400

        @self.app.route("/status", methods=["GET"])
        def get_status():
            return jsonify(
                {
                    "status": "active",
                    "current_round": self.current_round,
                    "registered_clients": len(self.clients),
                    "active_models": list(self.global_models.keys()),
                }
            )

    def register_client(self, client_config: ClientConfig):
        """Register a new client"""
        client_id = client_config.client_id

        if client_id in self.clients:
            self.logger.warning("Client %s already registered", client_id)
            return

        self.clients[client_id] = client_config

        # Store public key
        if client_config.public_key:
            self.client_public_keys[client_id] = serialization.load_pem_public_key(
                client_config.public_key
            )

        self.logger.info(
            "Registered client %s with role %s", client_id, client_config.role.value
        )

    def initialize_global_model(self, model_type: ModelType, architecture: nn.Module):
        """Initialize a global model"""
        federated_model = FederatedModel(
            model_type=model_type,
            architecture=architecture,
            version=MODEL_VERSION,
            metadata={"created": datetime.now(), "coordinator_id": "main"},
        )

        self.global_models[model_type] = federated_model
        self.logger.info("Initialized global model for %s", model_type.value)

    def start_training_round(self, model_type: ModelType) -> FederatedRound:
        """Start a new federated training round"""
        try:
            self.current_round += 1

            # Select clients for this round
            eligible_clients = [
                c
                for c in self.clients.values()
                if model_type in c.model_types and c.role != ClientRole.OBSERVER
            ]

            if len(eligible_clients) < self.min_clients:
                raise ValueError(
                    f"Not enough clients: {len(eligible_clients)} < {self.min_clients}"
                )

            # Random client selection
            num_selected = max(
                self.min_clients, int(len(eligible_clients) * self.client_fraction)
            )

            selected_clients = np.random.choice(
                [c.client_id for c in eligible_clients],
                size=num_selected,
                replace=False,
            ).tolist()

            # Create round
            fed_round = FederatedRound(
                round_number=self.current_round,
                selected_clients=selected_clients,
                model_updates=[],
            )

            self.round_history.append(fed_round)

            # Notify selected clients
            self._notify_clients_for_training(selected_clients, model_type)

            self.logger.info(
                "Started round %s with %s clients", self.current_round, len(selected_clients)
            )

            return fed_round

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "start_training_round"})
            return None

    def aggregate_updates(
        self, round_number: int, model_type: ModelType
    ) -> AggregationResult:
        """Aggregate model updates from clients"""
        try:
            # Get round
            current_round = self.round_history[round_number - 1]

            if not current_round.model_updates:
                raise ValueError("No model updates received")

            # Get global model
            global_model = self.global_models[model_type]

            # Perform aggregation based on method
            if self.aggregation_method == AggregationMethod.FEDERATED_AVERAGING:
                aggregated_weights = self._federated_averaging(
                    current_round.model_updates, global_model.architecture.state_dict()
                )
            elif self.aggregation_method == AggregationMethod.WEIGHTED_AVERAGE:
                aggregated_weights = self._weighted_averaging(
                    current_round.model_updates, global_model.architecture.state_dict()
                )
            elif self.aggregation_method == AggregationMethod.KRUM:
                aggregated_weights = self._krum_aggregation(
                    current_round.model_updates, global_model.architecture.state_dict()
                )
            else:
                raise ValueError(
                    f"Unknown aggregation method: {self.aggregation_method}"
                )

            # Update global model
            global_model.architecture.load_state_dict(aggregated_weights)
            global_model.global_rounds += 1

            # Calculate metrics
            metrics = self._calculate_aggregation_metrics(
                current_round.model_updates, aggregated_weights
            )

            # Create result
            result = AggregationResult(
                round_number=round_number,
                aggregated_weights=aggregated_weights,
                participating_clients=[
                    u.client_id for u in current_round.model_updates
                ],
                aggregation_method=self.aggregation_method,
                metrics=metrics,
                privacy_spent=np.mean(
                    [
                        u.metrics.get("privacy_spent", 0)
                        for u in current_round.model_updates
                    ]
                ),
                timestamp=datetime.now(),
            )

            # Update round
            current_round.aggregation_result = result
            current_round.end_time = datetime.now()
            current_round.success = True

            # Track performance
            self.performance_history[model_type].append(metrics)

            self.logger.info(
                "Aggregated %s updates for round %s", len(current_round.model_updates), round_number
            )

            return result

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "aggregate_updates", "round": round_number}
            )
            return None

    def _federated_averaging(
        self, updates: list[ModelUpdate], global_weights: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        """Perform federated averaging"""
        # Initialize aggregated weights
        aggregated = {}

        # Total samples across all clients
        total_samples = sum(u.num_samples for u in updates)

        for param_name in global_weights:
            # Weighted sum of updates
            weighted_sum = torch.zeros_like(global_weights[param_name])

            for update in updates:
                if param_name in update.model_weights:
                    weight = update.num_samples / total_samples
                    weighted_sum += weight * update.model_weights[param_name]

            # Add to global weights
            aggregated[param_name] = global_weights[param_name] + weighted_sum

        return aggregated

    def _weighted_averaging(
        self, updates: list[ModelUpdate], global_weights: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        """Weighted averaging based on client performance"""
        # Calculate weights based on loss (lower is better)
        losses = [u.metrics.get("loss", float("inf")) for u in updates]

        # Convert to weights (inverse of loss)
        weights = [1.0 / (loss + 1e-6) for loss in losses]
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Aggregate
        aggregated = {}

        for param_name in global_weights:
            weighted_sum = torch.zeros_like(global_weights[param_name])

            for update, weight in zip(updates, weights, strict=False):
                if param_name in update.model_weights:
                    weighted_sum += weight * update.model_weights[param_name]

            aggregated[param_name] = global_weights[param_name] + weighted_sum

        return aggregated

    def _krum_aggregation(
        self, updates: list[ModelUpdate], global_weights: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor]:
        """Krum aggregation for Byzantine-robust learning"""
        n = len(updates)
        f = int(n * 0.2)  # Assume 20% could be Byzantine
        m = n - f - 2

        if m <= 0:
            # Fall back to federated averaging
            return self._federated_averaging(updates, global_weights)

        # Calculate pairwise distances
        distances = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                # Calculate L2 distance between updates
                dist = 0
                for param_name in updates[i].model_weights:
                    if param_name in updates[j].model_weights:
                        diff = (
                            updates[i].model_weights[param_name]
                            - updates[j].model_weights[param_name]
                        )
                        dist += torch.norm(diff).item() ** 2

                dist = np.sqrt(dist)
                distances[i, j] = dist
                distances[j, i] = dist

        # Calculate scores
        scores = []
        for i in range(n):
            # Get m closest neighbors
            neighbor_dists = sorted(distances[i, :])
            score = sum(neighbor_dists[: m + 1])
            scores.append(score)

        # Select client with minimum score
        best_idx = np.argmin(scores)

        # Use best update
        aggregated = {}
        best_update = updates[best_idx]

        for param_name in global_weights:
            if param_name in best_update.model_weights:
                aggregated[param_name] = (
                    global_weights[param_name] + best_update.model_weights[param_name]
                )
            else:
                aggregated[param_name] = global_weights[param_name]

        return aggregated

    def _calculate_aggregation_metrics(
        self, updates: list[ModelUpdate], aggregated_weights: dict[str, torch.Tensor]
    ) -> dict[str, float]:
        """Calculate metrics for aggregation"""
        # Average metrics from clients
        avg_loss = np.mean([u.metrics.get("loss", 0) for u in updates])

        # Model divergence (how much clients differ)
        divergences = []
        for update in updates:
            div = 0
            for param_name, param in update.model_weights.items():
                if param_name in aggregated_weights:
                    diff = param - aggregated_weights[param_name]
                    div += torch.norm(diff).item()
            divergences.append(div)

        return {
            "avg_loss": avg_loss,
            "model_divergence": np.mean(divergences),
            "num_clients": len(updates),
            "total_samples": sum(u.num_samples for u in updates),
        }

    def evaluate_global_model(
        self, model_type: ModelType, test_data: pd.DataFrame
    ) -> dict[str, float]:
        """Evaluate global model on test data"""
        try:
            if model_type not in self.global_models:
                raise ValueError(f"No global model for {model_type.value}")

            model = self.global_models[model_type].architecture
            model.eval()

            # Prepare test data (simplified)
            X_test = test_data.iloc[:, :-1].values
            y_test = test_data.iloc[:, -1].values

            X_test = torch.FloatTensor(X_test)
            y_test = torch.FloatTensor(y_test)

            # Evaluate
            with torch.no_grad():
                predictions = model(X_test)
                mse = nn.MSELoss()(predictions.squeeze(), y_test).item()
                mae = torch.mean(torch.abs(predictions.squeeze() - y_test)).item()

            metrics = {
                "mse": mse,
                "mae": mae,
                "rmse": np.sqrt(mse),
                "global_rounds": self.global_models[model_type].global_rounds,
            }

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "evaluate_global_model"})
            return {}

    def _notify_clients_for_training(
        self, client_ids: list[str], model_type: ModelType
    ):
        """Notify clients to start training"""
        # In production, this would send actual network requests
        self.logger.info("Notifying %s clients for training", len(client_ids))

    def _store_client_update(self, update: ModelUpdate):
        """Store client update for current round"""
        if self.current_round > 0 and self.round_history:
            current_round = self.round_history[-1]
            current_round.model_updates.append(update)

    def _deserialize_update(self, data: dict) -> ModelUpdate:
        """Deserialize model update from JSON"""
        # Convert weight lists back to tensors
        weights = {}
        for name, values in data["model_weights"].items():
            weights[name] = torch.FloatTensor(values)

        return ModelUpdate(
            client_id=data["client_id"],
            round_number=data["round_number"],
            model_weights=weights,
            num_samples=data["num_samples"],
            metrics=data["metrics"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            signature=(
                data.get("signature", b"").encode() if data.get("signature") else None
            ),
        )

    def generate_report(self) -> str:
        """Generate federated learning report"""
        report = []
        report.append("=" * 60)
        report.append("FEDERATED LEARNING REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Rounds: {self.current_round}")
        report.append(f"Registered Clients: {len(self.clients)}")
        report.append("")

        # Client statistics
        report.append("CLIENT STATISTICS:")
        report.append("-" * 30)

        role_counts = defaultdict(int)
        for client in self.clients.values():
            role_counts[client.role.value] += 1

        for role, count in role_counts.items():
            report.append(f"{role}: {count}")

        report.append("")

        # Model performance
        report.append("MODEL PERFORMANCE:")
        report.append("-" * 30)

        for model_type, history in self.performance_history.items():
            if history:
                recent = history[-10:]  # Last 10 rounds
                avg_loss = np.mean([h["avg_loss"] for h in recent])
                avg_divergence = np.mean([h["model_divergence"] for h in recent])

                report.append(f"\n{model_type.value}:")
                report.append(f"  Average Loss: {avg_loss:.4f}")
                report.append(f"  Model Divergence: {avg_divergence:.4f}")
                report.append(f"  Rounds Completed: {len(history)}")

        report.append("")

        # Recent rounds
        report.append("RECENT ROUNDS:")
        report.append("-" * 30)

        for round_info in self.round_history[-5:]:
            report.append(f"\nRound {round_info.round_number}:")
            report.append(f"  Clients: {len(round_info.selected_clients)}")
            report.append(f"  Updates: {len(round_info.model_updates)}")
            report.append(f"  Success: {round_info.success}")

            if round_info.aggregation_result:
                report.append(
                    f"  Privacy Spent: {round_info.aggregation_result.privacy_spent:.3f}"
                )

        report.append("\n" + "=" * 60)

        return "\n".join(report)

    def save_global_models(self, directory: str):
        """Save all global models"""
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        for model_type, federated_model in self.global_models.items():
            model_path = (
                path / f"global_{model_type.value}_round{self.current_round}.pth"
            )

            torch.save(
                {
                    "model_state_dict": federated_model.architecture.state_dict(),
                    "model_type": model_type.value,
                    "version": federated_model.version,
                    "global_rounds": federated_model.global_rounds,
                    "metadata": federated_model.metadata,
                },
                model_path,
            )

            self.logger.info("Saved global model to %s", model_path)

    def start_server(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT):
        """Start the coordinator server"""
        self.logger.info("Starting coordinator server on %s:%s", host, port)
        self.app.run(host=host, port=port, threaded=True)


# ==============================================================================
# FEDERATED LEARNING MANAGER
# ==============================================================================
class FederatedLearningManager:
    """High-level manager for federated learning operations"""

    def __init__(self):
        self.logger = SpyderLogger.get_logger("FederatedLearningManager")
        self.coordinator = None
        self.local_client = None
        self.is_coordinator = False

    def setup_as_coordinator(self, config: dict[str, Any] | None = None):
        """Setup as federated learning coordinator"""
        self.coordinator = FederatedCoordinator(config)
        self.is_coordinator = True

        # Initialize default models
        self._initialize_default_models()

        self.logger.info("Setup complete as coordinator")

    def setup_as_client(
        self,
        client_id: str,
        coordinator_url: str,
        role: ClientRole = ClientRole.PARTICIPANT,
    ):
        """Setup as federated learning client"""
        config = ClientConfig(
            client_id=client_id,
            role=role,
            host="localhost",
            port=5556,
            model_types=[ModelType.PRICE_PREDICTION, ModelType.VOLATILITY_SURFACE],
        )

        self.local_client = FederatedClient(config)

        # Register with coordinator
        success = self.local_client.register_with_coordinator(coordinator_url)

        if success:
            self.logger.info("Setup complete as client %s", client_id)
        else:
            self.logger.error("Failed to register with coordinator")

    def _initialize_default_models(self):
        """Initialize default models for federated learning"""
        # Price prediction model
        price_model = nn.Sequential(
            nn.Linear(20, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1),
        )

        self.coordinator.initialize_global_model(
            ModelType.PRICE_PREDICTION, price_model
        )

        # Volatility surface model
        vol_model = nn.Sequential(
            nn.Linear(10, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 30),
        )

        self.coordinator.initialize_global_model(
            ModelType.VOLATILITY_SURFACE, vol_model
        )

    async def run_federated_training(
        self,
        num_rounds: int = DEFAULT_ROUNDS,
        model_type: ModelType = ModelType.PRICE_PREDICTION,
    ):
        """Run federated training for specified rounds"""
        if not self.is_coordinator:
            raise ValueError("Must be coordinator to run training")

        self.logger.info("Starting federated training for %s rounds", num_rounds)

        for round_num in range(num_rounds):
            # Start round
            fed_round = self.coordinator.start_training_round(model_type)

            if not fed_round:
                self.logger.error("Failed to start round %s", round_num + 1)
                continue

            # Wait for client updates
            await asyncio.sleep(30)  # Give clients time to train

            # Aggregate updates
            if len(fed_round.model_updates) >= self.coordinator.min_clients:
                result = self.coordinator.aggregate_updates(
                    fed_round.round_number, model_type
                )

                if result:
                    self.logger.info(
                        f"Round {round_num + 1} completed. "
                        f"Avg loss: {result.metrics['avg_loss']:.4f}"
                    )
            else:
                self.logger.warning(
                    f"Insufficient updates for round {round_num + 1}: "
                    f"{len(fed_round.model_updates)} < {self.coordinator.min_clients}"
                )

        # Save final models
        self.coordinator.save_global_models("./federated_models")

        # Generate report
        report = self.coordinator.generate_report()

        with open("federated_training_report.txt", "w") as f:
            f.write(report)

        self.logger.info("Federated training completed")

    def visualize_training_progress(self):
        """Visualize federated learning progress"""
        if not self.is_coordinator:
            raise ValueError("Must be coordinator to visualize progress")

        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle("Federated Learning Progress", fontsize=16)

        # Plot 1: Loss over rounds
        ax1 = axes[0, 0]
        for model_type, history in self.coordinator.performance_history.items():
            if history:
                losses = [h["avg_loss"] for h in history]
                ax1.plot(losses, label=model_type.value)

        ax1.set_title("Average Loss Over Rounds")
        ax1.set_xlabel("Round")
        ax1.set_ylabel("Loss")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Model divergence
        ax2 = axes[0, 1]
        for model_type, history in self.coordinator.performance_history.items():
            if history:
                divergences = [h["model_divergence"] for h in history]
                ax2.plot(divergences, label=model_type.value)

        ax2.set_title("Model Divergence Over Rounds")
        ax2.set_xlabel("Round")
        ax2.set_ylabel("Divergence")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: Client participation
        ax3 = axes[1, 0]
        participation = [
            len(r.selected_clients) for r in self.coordinator.round_history
        ]
        ax3.bar(range(len(participation)), participation)
        ax3.set_title("Client Participation by Round")
        ax3.set_xlabel("Round")
        ax3.set_ylabel("Number of Clients")

        # Plot 4: Privacy budget
        ax4 = axes[1, 1]
        if self.coordinator.round_history:
            privacy_spent = []
            for r in self.coordinator.round_history:
                if r.aggregation_result:
                    privacy_spent.append(r.aggregation_result.privacy_spent)

            if privacy_spent:
                cumulative_privacy = np.cumsum(privacy_spent)
                ax4.plot(cumulative_privacy, "r-", linewidth=2)
                ax4.axhline(y=EPSILON, color="r", linestyle="--", label="Budget Limit")
                ax4.set_title("Cumulative Privacy Budget Spent")
                ax4.set_xlabel("Round")
                ax4.set_ylabel("Privacy Budget (ε)")
                ax4.legend()

        plt.tight_layout()
        plt.savefig("federated_learning_progress.png", dpi=300, bbox_inches="tight")
        plt.show()

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def run_federated_round_distributed(
        self,
        global_model_state: dict[str, Any],
        client_datasets: list[dict[str, Any]],
        num_cpus: int | None = None,
    ) -> dict[str, Any]:
        """
        Run a federated learning round with Ray actors as clients.

        Each client trains locally on a Ray worker and returns model
        updates for aggregation.

        Args:
            global_model_state: Current global model parameters.
            client_datasets: List of client data configs.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Aggregated model updates and round metrics.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed federated learning")
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        model_ref = ray.put(global_model_state)

        @ray.remote
        def _train_client(model_ref, client_data: dict, client_id: int) -> dict:
            """Simulate local client training on a Ray worker."""
            import numpy as _np
            import time as _time

            start = _time.time()
            _np.random.seed(client_id)

            n_samples = client_data.get('n_samples', 100)
            local_epochs = client_data.get('local_epochs', 5)

            # Simulate local training updates
            model_params = model_ref
            noise_scale = 0.01 / (local_epochs + 1)
            updates = {}
            for key, value in model_params.items():
                if isinstance(value, (int, float)):
                    updates[key] = value + _np.random.normal(0, noise_scale)
                else:
                    updates[key] = value

            loss = float(_np.random.exponential(0.5))
            return {
                'client_id': client_id,
                'updates': updates,
                'n_samples': n_samples,
                'loss': loss,
                'training_time': _time.time() - start,
                'status': 'completed',
            }

        self.logger.info("Ray federated round: %s clients", len(client_datasets))

        futures = [
            _train_client.remote(model_ref, cd, i)
            for i, cd in enumerate(client_datasets)
        ]
        client_results = ray.get(futures)

        completed = [r for r in client_results if r.get('status') == 'completed']
        if not completed:
            return {'status': 'failed', 'reason': 'no completed clients'}

        # Federated averaging
        total_samples = sum(r['n_samples'] for r in completed)
        aggregated = {}
        for key in completed[0].get('updates', {}):
            values = [r['updates'][key] for r in completed if key in r.get('updates', {})]
            weights = [r['n_samples'] / total_samples for r in completed]
            if all(isinstance(v, (int, float)) for v in values):
                aggregated[key] = sum(v * w for v, w in zip(values, weights, strict=False))
            else:
                aggregated[key] = values[0]

        return {
            'status': 'completed',
            'aggregated_model': aggregated,
            'n_clients': len(completed),
            'total_samples': total_samples,
            'mean_loss': float(np.mean([r['loss'] for r in completed])),
            'total_time': float(sum(r['training_time'] for r in completed)),
            'client_results': client_results,
        }


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_manager_instance = None
_manager_instance_lock = threading.Lock()


def get_federated_manager() -> FederatedLearningManager:
    """Get or create the global FederatedLearningManager instance."""
    global _manager_instance
    if _manager_instance is None:
        with _manager_instance_lock:
            if _manager_instance is None:
                _manager_instance = FederatedLearningManager()
    return _manager_instance


# ==============================================================================
# TESTING AND DEMONSTRATION
# ==============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Federated Learning System")
    parser.add_argument(
        "--mode",
        choices=["coordinator", "client"],
        required=True,
        help="Run as coordinator or client",
    )
    parser.add_argument("--client-id", type=str, help="Client ID (for client mode)")
    parser.add_argument(
        "--coordinator-url",
        type=str,
        default="http://localhost:5555",
        help="Coordinator URL (for client mode)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=10,
        help="Number of training rounds (for coordinator)",
    )

    args = parser.parse_args()

    manager = get_federated_manager()

    if args.mode == "coordinator":
        # Setup as coordinator
        manager.setup_as_coordinator({"min_clients": 2, "client_fraction": 0.5})

        # Start server in background thread
        import threading

        server_thread = threading.Thread(
            target=manager.coordinator.start_server, daemon=True
        )
        server_thread.start()


        # Wait for clients
        import time

        time.sleep(10)  # thread-safe: time.sleep() intentional

        # Run training
        asyncio.run(
            manager.run_federated_training(
                num_rounds=args.rounds, model_type=ModelType.PRICE_PREDICTION
            )
        )

        # Visualize results
        manager.visualize_training_progress()


    else:  # Client mode
        if not args.client_id:
            exit(1)

        manager.setup_as_client(
            client_id=args.client_id,
            coordinator_url=args.coordinator_url,
            role=ClientRole.PARTICIPANT,
        )

        # Load sample data
        sample_data = pd.DataFrame(
            {
                "open": np.random.randn(1000) * 2 + 450,
                "high": np.random.randn(1000) * 2 + 452,
                "low": np.random.randn(1000) * 2 + 448,
                "close": np.random.randn(1000) * 2 + 450,
                "volume": np.random.randint(1000000, 5000000, 1000),
                "target": np.random.randn(1000) * 0.5,
            }
        )

        manager.local_client.load_local_data(sample_data, ModelType.PRICE_PREDICTION)


        # Keep client running
        try:
            while True:
                time.sleep(60)  # thread-safe: time.sleep() intentional
                stats = manager.local_client.get_client_stats()
        except KeyboardInterrupt:
            pass
