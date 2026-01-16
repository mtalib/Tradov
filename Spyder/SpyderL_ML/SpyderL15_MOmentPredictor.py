#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL15_MOmentPredictor.py
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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import json
from pathlib import Path
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import pickle

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from moment import MOMENT

    MOMENT_AVAILABLE = True
except ImportError:
    MOMENT_AVAILABLE = False
    warnings.warn(
        "MOMENT library not installed. Install with: pip install moment-timeseries"
    )

import torch
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    MAX_PREDICTION_LATENCY_MS,
    FEATURE_CACHE_SIZE,
    MODEL_CONFIDENCE_THRESHOLD,
)
from Spyder.SpyderL_ML.SpyderL10_FeatureEngineering import FeatureEngineer
from Spyder.SpyderL_ML.SpyderL13_LSTMPricer import LSTMPricer
from Spyder.SpyderL_ML.SpyderL11_MLModelManager import MLModelManager

# ==============================================================================
# CONSTANTS
# ==============================================================================
MOMENT_MODEL_PATH = "models/moment/pretrained"
ENSEMBLE_WEIGHTS_PATH = "models/moment/ensemble_weights.pkl"
MAX_FORECAST_HORIZON = 10
MIN_CONFIDENCE_THRESHOLD = 0.6
ANOMALY_THRESHOLD = 0.85


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MomentTask(Enum):
    """MOMENT model task types"""

    FORECAST = auto()
    CLASSIFICATION = auto()
    ANOMALY_DETECTION = auto()
    IMPUTATION = auto()


@dataclass
class MultiTaskResult:
    """Results from MOMENT multi-task prediction"""

    price_forecast: np.ndarray
    forecast_confidence: float
    regime_classification: str
    regime_probability: float
    anomaly_score: float
    is_anomaly: bool
    imputed_values: Optional[Dict[str, float]] = None
    feature_importance: Optional[Dict[str, float]] = None
    processing_time_ms: float = 0.0


@dataclass
class EnsemblePrediction:
    """Combined prediction from MOMENT and LSTM ensemble"""

    option_prices: Dict[str, float]
    price_direction: str  # 'bullish', 'bearish', 'neutral'
    price_magnitude: float
    volatility_forecast: float
    regime_state: str
    external_risks: List[str]
    confidence_score: float
    moment_result: MultiTaskResult
    lstm_confidence: float
    ensemble_weights: Dict[str, float]


# ==============================================================================
# MOMENT PREDICTOR CLASS
# ==============================================================================
class MOmentPredictor:
    """
    MOMENT foundation model integration for multi-task time series analysis.

    This class provides state-of-the-art time series capabilities including
    forecasting, classification, anomaly detection, and missing data imputation.
    It creates an ensemble with existing LSTM models for robust predictions.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize MOMENT predictor with configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.model_path = self.config.get("model_path", MOMENT_MODEL_PATH)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Components
        self.moment_model = None
        self.feature_engineer = FeatureEngineer()
        self.lstm_pricer = LSTMPricer()
        self.model_manager = MLModelManager()

        # State tracking
        self.is_initialized = False
        self.performance_history = []
        self.ensemble_weights = {"moment": 0.5, "lstm": 0.5}

        # Initialize
        self._initialize_models()

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================

    def _initialize_models(self) -> None:
        """Initialize MOMENT and load pre-trained weights."""
        try:
            if not MOMENT_AVAILABLE:
                self.logger.warning("MOMENT not available, using fallback mode")
                return

            # Load MOMENT model
            self.logger.info("Loading MOMENT foundation model...")
            self.moment_model = self._load_moment_model()

            # Load ensemble weights if available
            self._load_ensemble_weights()

            # Warm up models
            self._warmup_models()

            self.is_initialized = True
            self.logger.info("✅ MOMENT predictor initialized successfully")

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_initialize_models", "model_path": self.model_path}
            )

    def _load_moment_model(self):
        """Load pre-trained MOMENT model."""
        if MOMENT_AVAILABLE:
            model = MOMENT.load_pretrained()
            model.to(self.device)
            model.eval()
            return model
        return None

    def _load_ensemble_weights(self) -> None:
        """Load saved ensemble weights."""
        weights_path = Path(ENSEMBLE_WEIGHTS_PATH)
        if weights_path.exists():
            try:
                with open(weights_path, "rb") as f:
                    self.ensemble_weights = pickle.load(f)
                self.logger.info(f"Loaded ensemble weights: {self.ensemble_weights}")
            except Exception as e:
                self.logger.warning(f"Could not load ensemble weights: {e}")

    def _warmup_models(self) -> None:
        """Warm up models with dummy data."""
        try:
            # Create dummy data
            dummy_data = pd.DataFrame(
                {
                    "price": np.random.randn(100),
                    "volume": np.random.randn(100),
                    "volatility": np.random.randn(100),
                }
            )

            # Run dummy prediction
            _ = asyncio.run(self.predict_dummy(dummy_data))

        except Exception as e:
            self.logger.warning(f"Model warmup failed: {e}")

    # ==========================================================================
    # MULTI-TASK PREDICTION METHODS
    # ==========================================================================

    async def multi_task_forecast(
        self,
        market_data: pd.DataFrame,
        external_features: Optional[Dict[str, Any]] = None,
        tasks: Optional[List[MomentTask]] = None,
    ) -> MultiTaskResult:
        """
        Perform multi-task prediction using MOMENT.

        Args:
            market_data: DataFrame with price, volume, volatility data
            external_features: Optional external features (Fed, earnings, etc.)
            tasks: List of tasks to perform (default: all)

        Returns:
            MultiTaskResult with all predictions
        """
        try:
            start_time = datetime.now()

            # Default to all tasks
            if tasks is None:
                tasks = list(MomentTask)

            # Prepare features
            features = await self._prepare_features(market_data, external_features)

            # Execute tasks in parallel
            task_coroutines = []
            if MomentTask.FORECAST in tasks:
                task_coroutines.append(self._forecast_task(features))
            if MomentTask.CLASSIFICATION in tasks:
                task_coroutines.append(self._classification_task(features))
            if MomentTask.ANOMALY_DETECTION in tasks:
                task_coroutines.append(self._anomaly_task(features))
            if MomentTask.IMPUTATION in tasks:
                task_coroutines.append(self._imputation_task(features))

            # Gather results
            results = await asyncio.gather(*task_coroutines)

            # Combine results
            multi_result = self._combine_task_results(results, tasks)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            multi_result.processing_time_ms = processing_time

            return multi_result

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "multi_task_forecast", "tasks": [t.name for t in tasks]}
            )
            return self._create_fallback_result()

    async def _prepare_features(
        self,
        market_data: pd.DataFrame,
        external_features: Optional[Dict[str, Any]] = None,
    ) -> torch.Tensor:
        """Prepare features for MOMENT model."""
        # Use existing feature engineering
        engineered_features = await self.feature_engineer.create_features(
            price_data=market_data.get("spy_prices"),
            volume_data=market_data.get("spy_volume"),
            volatility_data=market_data.get("vix_history"),
            additional_features=external_features,
        )

        # Convert to tensor
        feature_tensor = torch.tensor(
            engineered_features.values, dtype=torch.float32, device=self.device
        )

        return feature_tensor

    async def _forecast_task(self, features: torch.Tensor) -> Dict[str, Any]:
        """Execute forecasting task."""
        if self.moment_model is None:
            return self._lstm_fallback_forecast(features)

        with torch.no_grad():
            forecast = self.moment_model.forecast(
                features, horizon=MAX_FORECAST_HORIZON
            )

        return {
            "type": "forecast",
            "predictions": forecast.cpu().numpy(),
            "confidence": self._calculate_forecast_confidence(forecast),
        }

    async def _classification_task(self, features: torch.Tensor) -> Dict[str, Any]:
        """Execute regime classification task."""
        if self.moment_model is None:
            return {"type": "classification", "regime": "unknown", "probability": 0.5}

        with torch.no_grad():
            classification = self.moment_model.classify(features)

        regimes = ["trending_up", "trending_down", "ranging", "volatile"]
        regime_idx = classification.argmax().item()

        return {
            "type": "classification",
            "regime": regimes[regime_idx],
            "probability": classification[0, regime_idx].item(),
        }

    async def _anomaly_task(self, features: torch.Tensor) -> Dict[str, Any]:
        """Execute anomaly detection task."""
        if self.moment_model is None:
            return {"type": "anomaly", "score": 0.0, "is_anomaly": False}

        with torch.no_grad():
            anomaly_score = self.moment_model.detect_anomalies(features)

        score = anomaly_score.item()
        is_anomaly = score > ANOMALY_THRESHOLD

        return {"type": "anomaly", "score": score, "is_anomaly": is_anomaly}

    async def _imputation_task(self, features: torch.Tensor) -> Dict[str, Any]:
        """Execute missing value imputation task."""
        if self.moment_model is None:
            return {"type": "imputation", "imputed_values": {}}

        # Identify missing values
        missing_mask = torch.isnan(features)

        if not missing_mask.any():
            return {"type": "imputation", "imputed_values": {}}

        with torch.no_grad():
            imputed = self.moment_model.impute_missing(features, missing_mask)

        # Extract imputed values
        imputed_values = {}
        missing_indices = torch.where(missing_mask)
        for i, j in zip(missing_indices[0], missing_indices[1]):
            imputed_values[f"feature_{j}_time_{i}"] = imputed[i, j].item()

        return {"type": "imputation", "imputed_values": imputed_values}

    # ==========================================================================
    # ENSEMBLE PREDICTION METHODS
    # ==========================================================================

    async def ensemble_forecast(
        self,
        market_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None,
        external_features: Optional[Dict[str, Any]] = None,
    ) -> EnsemblePrediction:
        """
        Generate ensemble prediction combining MOMENT and LSTM.

        Args:
            market_data: Market data including prices, volume, volatility
            options_data: Optional options chain data
            external_features: External features (Fed calendar, earnings, etc.)

        Returns:
            EnsemblePrediction with combined forecasts
        """
        try:
            # Get MOMENT multi-task predictions
            moment_result = await self.multi_task_forecast(
                market_data, external_features
            )

            # Get LSTM predictions
            lstm_predictions = await self.lstm_pricer.predict_option_prices(
                underlying_forecast=moment_result.price_forecast,
                market_data=market_data,
                options_data=options_data,
            )

            # Calculate dynamic weights based on recent performance
            weights = await self._calculate_dynamic_weights(
                moment_confidence=moment_result.forecast_confidence,
                lstm_confidence=lstm_predictions.confidence,
                market_regime=moment_result.regime_classification,
            )

            # Combine predictions
            ensemble_pred = self._create_ensemble_prediction(
                moment_result=moment_result,
                lstm_predictions=lstm_predictions,
                weights=weights,
                external_features=external_features,
            )

            # Track performance
            self._update_performance_tracking(ensemble_pred)

            return ensemble_pred

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "ensemble_forecast"})
            return self._create_fallback_ensemble()

    async def _calculate_dynamic_weights(
        self, moment_confidence: float, lstm_confidence: float, market_regime: str
    ) -> Dict[str, float]:
        """Calculate dynamic ensemble weights based on confidence and regime."""
        # Base weights
        weights = self.ensemble_weights.copy()

        # Adjust based on confidence
        total_confidence = moment_confidence + lstm_confidence
        if total_confidence > 0:
            weights["moment"] = moment_confidence / total_confidence
            weights["lstm"] = lstm_confidence / total_confidence

        # Regime-based adjustments
        regime_adjustments = {
            "trending_up": {"moment": 0.6, "lstm": 0.4},
            "trending_down": {"moment": 0.6, "lstm": 0.4},
            "ranging": {"moment": 0.4, "lstm": 0.6},
            "volatile": {"moment": 0.5, "lstm": 0.5},
        }

        if market_regime in regime_adjustments:
            regime_weights = regime_adjustments[market_regime]
            # Blend with confidence weights
            for model in weights:
                weights[model] = 0.7 * weights[model] + 0.3 * regime_weights.get(
                    model, 0.5
                )

        # Normalize
        total = sum(weights.values())
        for model in weights:
            weights[model] /= total

        return weights

    def _create_ensemble_prediction(
        self,
        moment_result: MultiTaskResult,
        lstm_predictions: Any,
        weights: Dict[str, float],
        external_features: Optional[Dict[str, Any]],
    ) -> EnsemblePrediction:
        """Create final ensemble prediction."""
        # Determine price direction and magnitude
        price_forecast = moment_result.price_forecast
        price_direction = "bullish" if price_forecast[-1] > 0 else "bearish"
        price_magnitude = abs(price_forecast[-1])

        # Extract external risks
        external_risks = []
        if external_features:
            if external_features.get("fed_meeting_today"):
                external_risks.append("Fed Meeting Risk")
            if external_features.get("earnings_announcement"):
                external_risks.append("Earnings Risk")
            if moment_result.is_anomaly:
                external_risks.append("Market Anomaly Detected")

        # Calculate ensemble confidence
        ensemble_confidence = (
            weights["moment"] * moment_result.forecast_confidence
            + weights["lstm"] * lstm_predictions.confidence
        )

        return EnsemblePrediction(
            option_prices=lstm_predictions.prices,
            price_direction=price_direction,
            price_magnitude=price_magnitude,
            volatility_forecast=lstm_predictions.volatility_forecast,
            regime_state=moment_result.regime_classification,
            external_risks=external_risks,
            confidence_score=ensemble_confidence,
            moment_result=moment_result,
            lstm_confidence=lstm_predictions.confidence,
            ensemble_weights=weights,
        )

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _combine_task_results(
        self, results: List[Dict], tasks: List[MomentTask]
    ) -> MultiTaskResult:
        """Combine results from multiple tasks."""
        combined = MultiTaskResult(
            price_forecast=np.array([0.0]),
            forecast_confidence=0.0,
            regime_classification="unknown",
            regime_probability=0.0,
            anomaly_score=0.0,
            is_anomaly=False,
        )

        for result in results:
            if result["type"] == "forecast":
                combined.price_forecast = result["predictions"]
                combined.forecast_confidence = result["confidence"]
            elif result["type"] == "classification":
                combined.regime_classification = result["regime"]
                combined.regime_probability = result["probability"]
            elif result["type"] == "anomaly":
                combined.anomaly_score = result["score"]
                combined.is_anomaly = result["is_anomaly"]
            elif result["type"] == "imputation":
                combined.imputed_values = result["imputed_values"]

        return combined

    def _calculate_forecast_confidence(self, forecast: torch.Tensor) -> float:
        """Calculate confidence score for forecast."""
        # Simple confidence based on forecast variance
        variance = torch.var(forecast).item()
        confidence = 1.0 / (1.0 + variance)
        return max(MIN_CONFIDENCE_THRESHOLD, min(confidence, 1.0))

    def _update_performance_tracking(self, prediction: EnsemblePrediction) -> None:
        """Track prediction performance for weight optimization."""
        self.performance_history.append(
            {
                "timestamp": datetime.now(),
                "confidence": prediction.confidence_score,
                "regime": prediction.regime_state,
                "weights": prediction.ensemble_weights.copy(),
            }
        )

        # Keep only recent history
        max_history = 1000
        if len(self.performance_history) > max_history:
            self.performance_history = self.performance_history[-max_history:]

    def _create_fallback_result(self) -> MultiTaskResult:
        """Create fallback result when MOMENT is unavailable."""
        return MultiTaskResult(
            price_forecast=np.zeros(MAX_FORECAST_HORIZON),
            forecast_confidence=0.5,
            regime_classification="unknown",
            regime_probability=0.5,
            anomaly_score=0.0,
            is_anomaly=False,
        )

    def _create_fallback_ensemble(self) -> EnsemblePrediction:
        """Create fallback ensemble prediction."""
        return EnsemblePrediction(
            option_prices={},
            price_direction="neutral",
            price_magnitude=0.0,
            volatility_forecast=0.0,
            regime_state="unknown",
            external_risks=["Model Unavailable"],
            confidence_score=0.0,
            moment_result=self._create_fallback_result(),
            lstm_confidence=0.0,
            ensemble_weights={"moment": 0.0, "lstm": 1.0},
        )

    def _lstm_fallback_forecast(self, features: torch.Tensor) -> Dict[str, Any]:
        """Fallback to LSTM when MOMENT unavailable."""
        # Convert tensor back to DataFrame for LSTM
        feature_df = pd.DataFrame(features.cpu().numpy())

        # Use LSTM for prediction
        predictions = self.lstm_pricer.predict_simple(feature_df)

        return {
            "type": "forecast",
            "predictions": predictions,
            "confidence": 0.7,  # Lower confidence for fallback
        }

    async def predict_dummy(self, dummy_data: pd.DataFrame) -> Any:
        """Dummy prediction for warmup."""
        return await self.multi_task_forecast(dummy_data)

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    async def predict(
        self,
        market_data: pd.DataFrame,
        options_data: Optional[pd.DataFrame] = None,
        external_features: Optional[Dict[str, Any]] = None,
        use_ensemble: bool = True,
    ) -> Union[MultiTaskResult, EnsemblePrediction]:
        """
        Main prediction interface.

        Args:
            market_data: Market data DataFrame
            options_data: Optional options chain data
            external_features: External features dictionary
            use_ensemble: Whether to use ensemble (True) or MOMENT only (False)

        Returns:
            MultiTaskResult or EnsemblePrediction based on use_ensemble
        """
        if use_ensemble:
            return await self.ensemble_forecast(
                market_data, options_data, external_features
            )
        else:
            return await self.multi_task_forecast(market_data, external_features)

    def save_ensemble_weights(self) -> None:
        """Save current ensemble weights."""
        try:
            weights_path = Path(ENSEMBLE_WEIGHTS_PATH)
            weights_path.parent.mkdir(parents=True, exist_ok=True)

            with open(weights_path, "wb") as f:
                pickle.dump(self.ensemble_weights, f)

            self.logger.info(f"Saved ensemble weights: {self.ensemble_weights}")

        except Exception as e:
            self.logger.error(f"Failed to save weights: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models."""
        return {
            "moment_available": MOMENT_AVAILABLE,
            "moment_loaded": self.moment_model is not None,
            "lstm_loaded": self.lstm_pricer is not None,
            "device": str(self.device),
            "ensemble_weights": self.ensemble_weights,
            "performance_history_size": len(self.performance_history),
            "is_initialized": self.is_initialized,
        }


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: Optional[MOmentPredictor] = None


def create_moment_predictor(config: Optional[Dict[str, Any]] = None) -> MOmentPredictor:
    """
    Factory function to create MOmentPredictor instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        MOmentPredictor instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = MOmentPredictor(config)
    return _module_instance


def get_moment_predictor() -> Optional[MOmentPredictor]:
    """Get existing MOmentPredictor instance."""
    return _module_instance


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test and demonstrate MOMENT predictor functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="MOMENT Predictor Testing")
    parser.add_argument("--test", action="store_true", help="Run test predictions")
    parser.add_argument("--info", action="store_true", help="Show model information")
    args = parser.parse_args()

    # Create predictor
    predictor = create_moment_predictor()

    if args.info:
        info = predictor.get_model_info()
        print("\n=== MOMENT Predictor Information ===")
        for key, value in info.items():
            print(f"{key}: {value}")

    if args.test:
        print("\n=== Running Test Predictions ===")

        # Create test data
        test_data = pd.DataFrame(
            {
                "spy_prices": np.random.randn(100).cumsum() + 400,
                "spy_volume": np.random.randint(1000000, 5000000, 100),
                "vix_history": np.random.uniform(15, 25, 100),
            }
        )

        # Test external features
        external_features = {
            "fed_meeting_today": True,
            "earnings_announcement": False,
            "economic_data_release": True,
        }

        # Run prediction
        result = await predictor.predict(
            market_data=test_data,
            external_features=external_features,
            use_ensemble=True,
        )

        if isinstance(result, EnsemblePrediction):
            print(f"\nPrice Direction: {result.price_direction}")
            print(f"Price Magnitude: {result.price_magnitude:.2f}")
            print(f"Regime State: {result.regime_state}")
            print(f"Confidence Score: {result.confidence_score:.2%}")
            print(f"External Risks: {result.external_risks}")
            print(f"Ensemble Weights: {result.ensemble_weights}")
            print(f"Processing Time: {result.moment_result.processing_time_ms:.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
