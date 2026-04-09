#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL14_RealTimePredictor.py
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
import time
import threading
import queue
from datetime import datetime
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field
from collections import deque
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import joblib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderL_ML.SpyderL10_FeatureEngineering import FeatureEngineer
from Spyder.SpyderL_ML.SpyderL11_MLModelManager import get_model_manager, ModelStatus
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType
from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import get_data_feed_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Performance settings
MAX_PREDICTION_LATENCY_MS = 10  # Maximum allowed latency
FEATURE_CACHE_SIZE = 1000       # Number of feature sets to cache
PREDICTION_BATCH_SIZE = 10      # Batch size for predictions
CACHE_TTL_SECONDS = 60          # Cache time-to-live

# Warm-up settings
MODEL_WARMUP_SAMPLES = 100      # Samples for model warm-up
WARMUP_INTERVAL_SECONDS = 300   # Re-warm models every 5 minutes

# Performance monitoring
LATENCY_BUCKETS = [1, 2, 5, 10, 20, 50, 100]  # milliseconds
PERFORMANCE_WINDOW = 1000       # Track last N predictions

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PredictionRequest:
    """Real-time prediction request"""
    request_id: str
    timestamp: datetime
    features: dict[str, float]
    model_names: list[str]
    priority: int = 0
    callback: Callable | None = None

@dataclass
class PredictionResult:
    """Real-time prediction result"""
    request_id: str
    timestamp: datetime
    predictions: dict[str, Any]  # model_name -> prediction
    latency_ms: float
    from_cache: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelInstance:
    """Loaded model instance with metadata"""
    model_id: str
    model_name: str
    model: Any  # The actual model object
    feature_names: list[str]
    last_used: datetime
    prediction_count: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0

@dataclass
class FeatureCacheEntry:
    """Cached feature entry"""
    timestamp: datetime
    features: dict[str, float]
    feature_vector: np.ndarray
    hash_key: str

@dataclass
class PerformanceMetrics:
    """Real-time performance metrics"""
    total_predictions: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    errors: int = 0
    latency_histogram: dict[int, int] = field(default_factory=dict)

# ==============================================================================
# REAL-TIME PREDICTOR CLASS
# ==============================================================================
class RealTimePredictor:
    """
    High-performance real-time prediction engine.

    Features:
    - Low-latency predictions (<10ms)
    - Feature caching and reuse
    - Model warm-up and pre-loading
    - Batch prediction support
    - Performance monitoring
    - Automatic failover
    """

    def __init__(self):
        """Initialize real-time predictor"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.model_manager = get_model_manager()
        self.feature_engineer = FeatureEngineer()
        self.data_feed = get_data_feed_manager()

        # Model instances
        self.models: dict[str, ModelInstance] = {}
        self.model_lock = threading.RLock()

        # Feature cache
        self.feature_cache: dict[str, FeatureCacheEntry] = {}
        self.cache_order: deque = deque(maxlen=FEATURE_CACHE_SIZE)
        self.cache_lock = threading.Lock()

        # Prediction queue
        self.prediction_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.result_callbacks: dict[str, Callable] = {}

        # Performance tracking
        self.performance = PerformanceMetrics()
        self.latency_history = deque(maxlen=PERFORMANCE_WINDOW)

        # Thread management
        self._running = False
        self._prediction_thread = None
        self._warmup_thread = None
        self._monitor_thread = None

        # Initialize
        self._load_production_models()
        self._subscribe_to_events()

        self.logger.info("RealTimePredictor initialized")

    # ==========================================================================
    # PUBLIC METHODS - PREDICTIONS
    # ==========================================================================
    def predict(
        self,
        features: dict[str, float],
        model_names: list[str] | None = None,
        use_cache: bool = True
    ) -> PredictionResult:
        """
        Make real-time prediction.

        Args:
            features: Feature dictionary
            model_names: Models to use (None = all active)
            use_cache: Whether to use feature cache

        Returns:
            Prediction result
        """
        start_time = time.time()
        request_id = f"pred_{int(time.time() * 1000000)}"

        try:
            # Check cache first
            if use_cache:
                cached_result = self._check_cache(features)
                if cached_result:
                    self.performance.cache_hits += 1
                    return cached_result
                else:
                    self.performance.cache_misses += 1

            # Get model names
            if not model_names:
                model_names = list(self.models.keys())

            # Make predictions
            predictions = {}

            for model_name in model_names:
                if model_name in self.models:
                    pred = self._predict_single(model_name, features)
                    if pred is not None:
                        predictions[model_name] = pred

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Create result
            result = PredictionResult(
                request_id=request_id,
                timestamp=datetime.now(),
                predictions=predictions,
                latency_ms=latency_ms,
                from_cache=False
            )

            # Cache result
            if use_cache:
                self._cache_result(features, result)

            # Track performance
            self._track_prediction_performance(latency_ms)

            return result

        except Exception as e:
            self.logger.error("Prediction error: %s", e, exc_info=True)
            self.performance.errors += 1

            # Return empty result
            return PredictionResult(
                request_id=request_id,
                timestamp=datetime.now(),
                predictions={},
                latency_ms=(time.time() - start_time) * 1000,
                metadata={'error': str(e)}
            )

    def predict_async(
        self,
        features: dict[str, float],
        callback: Callable[[PredictionResult], None],
        model_names: list[str] | None = None,
        priority: int = 0
    ) -> str:
        """
        Make asynchronous prediction.

        Args:
            features: Feature dictionary
            callback: Callback function for result
            model_names: Models to use
            priority: Request priority (lower = higher priority)

        Returns:
            Request ID
        """
        request_id = f"async_{int(time.time() * 1000000)}"

        request = PredictionRequest(
            request_id=request_id,
            timestamp=datetime.now(),
            features=features,
            model_names=model_names or list(self.models.keys()),
            priority=priority,
            callback=callback
        )

        # Add to queue
        self.prediction_queue.put((priority, request))
        self.result_callbacks[request_id] = callback

        return request_id

    def predict_batch(
        self,
        feature_list: list[dict[str, float]],
        model_names: list[str] | None = None
    ) -> list[PredictionResult]:
        """
        Make batch predictions.

        Args:
            feature_list: List of feature dictionaries
            model_names: Models to use

        Returns:
            List of prediction results
        """
        results = []

        # Process in batches
        for i in range(0, len(feature_list), PREDICTION_BATCH_SIZE):
            batch = feature_list[i:i + PREDICTION_BATCH_SIZE]

            # Predict each item
            for features in batch:
                result = self.predict(features, model_names)
                results.append(result)

        return results

    # ==========================================================================
    # PUBLIC METHODS - MODEL MANAGEMENT
    # ==========================================================================
    def load_model(self, model_name: str, model_id: str | None = None) -> bool:
        """
        Load model for real-time predictions.

        Args:
            model_name: Model name
            model_id: Specific model ID (None = latest production)

        Returns:
            Success status
        """
        try:
            with self.model_lock:
                # Get model ID if not specified
                if not model_id:
                    active_models = self.model_manager.get_active_models()
                    if model_name not in active_models:
                        self.logger.error("No active model found for %s", model_name)
                        return False
                    model_id = active_models[model_name].model_id

                # Get model version
                model_version = self.model_manager.get_model_version(model_id)
                if not model_version:
                    self.logger.error("Model %s not found", model_id)
                    return False

                # Load model file
                model_path = model_version.get_file_path()
                if not model_path.exists():
                    self.logger.error("Model file not found: %s", model_path)
                    return False

                # Load model
                model = joblib.load(model_path)

                # Create model instance
                instance = ModelInstance(
                    model_id=model_id,
                    model_name=model_name,
                    model=model,
                    feature_names=model_version.config.features,
                    last_used=datetime.now()
                )

                # Warm up model
                self._warmup_model(instance)

                # Store instance
                self.models[model_name] = instance

                self.logger.info("Loaded model %s (ID: %s)", model_name, model_id)
                return True

        except Exception as e:
            self.logger.error("Error loading model %s: %s", model_name, e, exc_info=True)
            return False

    def unload_model(self, model_name: str) -> bool:
        """Unload model from memory"""
        try:
            with self.model_lock:
                if model_name in self.models:
                    del self.models[model_name]
                    self.logger.info("Unloaded model %s", model_name)
                    return True
                return False

        except Exception as e:
            self.logger.error("Error unloading model: %s", e, exc_info=True)
            return False

    def reload_models(self) -> int:
        """Reload all production models"""
        count = 0

        try:
            active_models = self.model_manager.get_active_models()

            for model_name, model_version in active_models.items():
                if model_version.status == ModelStatus.PRODUCTION:
                    if self.load_model(model_name, model_version.model_id):
                        count += 1

            self.logger.info("Reloaded %s production models", count)
            return count

        except Exception as e:
            self.logger.error("Error reloading models: %s", e, exc_info=True)
            return count

    # ==========================================================================
    # PUBLIC METHODS - PERFORMANCE
    # ==========================================================================
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        # Update latency percentiles
        if self.latency_history:
            latencies = list(self.latency_history)
            self.performance.p95_latency_ms = np.percentile(latencies, 95)
            self.performance.p99_latency_ms = np.percentile(latencies, 99)

        return self.performance

    def get_model_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for each loaded model"""
        stats = {}

        with self.model_lock:
            for name, instance in self.models.items():
                avg_latency = (
                    instance.total_latency_ms / instance.prediction_count
                    if instance.prediction_count > 0 else 0
                )

                stats[name] = {
                    'model_id': instance.model_id,
                    'prediction_count': instance.prediction_count,
                    'average_latency_ms': avg_latency,
                    'error_count': instance.error_count,
                    'error_rate': (
                        instance.error_count / instance.prediction_count
                        if instance.prediction_count > 0 else 0
                    ),
                    'last_used': instance.last_used.isoformat()
                }

        return stats

    def clear_cache(self) -> None:
        """Clear feature cache"""
        with self.cache_lock:
            self.feature_cache.clear()
            self.cache_order.clear()

        self.logger.info("Feature cache cleared")

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start(self) -> None:
        """Start real-time predictor"""
        if self._running:
            return

        self._running = True

        # Start prediction thread
        self._prediction_thread = threading.Thread(
            target=self._prediction_worker,
            name="RealTimePredictor-Worker",
            daemon=True
        )
        self._prediction_thread.start()

        # Start warmup thread
        self._warmup_thread = threading.Thread(
            target=self._warmup_worker,
            name="RealTimePredictor-Warmup",
            daemon=True
        )
        self._warmup_thread.start()

        # Start monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="RealTimePredictor-Monitor",
            daemon=True
        )
        self._monitor_thread.start()

        self.logger.info("RealTimePredictor started")

    def stop(self) -> None:
        """Stop real-time predictor"""
        self._running = False

        # Wait for threads
        if self._prediction_thread:
            self._prediction_thread.join(timeout=5)
        if self._warmup_thread:
            self._warmup_thread.join(timeout=5)
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

        self.logger.info("RealTimePredictor stopped")

    # ==========================================================================
    # PRIVATE METHODS - PREDICTION
    # ==========================================================================
    def _predict_single(
        self,
        model_name: str,
        features: dict[str, float]
    ) -> Any | None:
        """Make prediction with single model"""
        try:
            start_time = time.time()

            with self.model_lock:
                if model_name not in self.models:
                    return None

                instance = self.models[model_name]

                # Prepare features
                feature_vector = self._prepare_features(features, instance.feature_names)

                # Make prediction
                prediction = instance.model.predict(feature_vector.reshape(1, -1))[0]

                # Update stats
                latency_ms = (time.time() - start_time) * 1000
                instance.prediction_count += 1
                instance.total_latency_ms += latency_ms
                instance.last_used = datetime.now()

                return prediction

        except Exception as e:
            self.logger.error("Error in single prediction: %s", e, exc_info=True)
            if model_name in self.models:
                self.models[model_name].error_count += 1
            return None

    def _prepare_features(
        self,
        features: dict[str, float],
        feature_names: list[str]
    ) -> np.ndarray:
        """Prepare feature vector for model"""
        # Extract features in correct order
        feature_vector = np.zeros(len(feature_names))

        for i, name in enumerate(feature_names):
            feature_vector[i] = features.get(name, 0.0)

        return feature_vector

    # ==========================================================================
    # PRIVATE METHODS - CACHING
    # ==========================================================================
    def _get_cache_key(self, features: dict[str, float]) -> str:
        """Generate cache key from features"""
        # Create stable hash from features
        feature_str = json.dumps(features, sort_keys=True)
        return str(hash(feature_str))

    def _check_cache(
        self,
        features: dict[str, float]
    ) -> PredictionResult | None:
        """Check if prediction exists in cache"""
        cache_key = self._get_cache_key(features)

        with self.cache_lock:
            if cache_key in self.feature_cache:
                entry = self.feature_cache[cache_key]

                # Check TTL
                age = (datetime.now() - entry.timestamp).total_seconds()
                if age < CACHE_TTL_SECONDS:
                    # Make predictions using cached features
                    predictions = {}

                    for model_name, instance in self.models.items():
                        try:
                            pred = instance.model.predict(
                                entry.feature_vector.reshape(1, -1)
                            )[0]
                            predictions[model_name] = pred
                        except Exception as e:
                            self.logger.debug("Prediction failed for %s: %s", model_name, e)

                    return PredictionResult(
                        request_id=f"cache_{int(time.time() * 1000000)}",
                        timestamp=datetime.now(),
                        predictions=predictions,
                        latency_ms=0.1,  # Cache lookup is fast
                        from_cache=True
                    )

        return None

    def _cache_result(
        self,
        features: dict[str, float],
        result: PredictionResult
    ) -> None:
        """Cache prediction result"""
        cache_key = self._get_cache_key(features)

        # Prepare feature vector (using first model's features)
        if self.models:
            first_model = next(iter(self.models.values()))
            feature_vector = self._prepare_features(features, first_model.feature_names)
        else:
            feature_vector = np.array(list(features.values()))

        entry = FeatureCacheEntry(
            timestamp=datetime.now(),
            features=features,
            feature_vector=feature_vector,
            hash_key=cache_key
        )

        with self.cache_lock:
            # Add to cache
            self.feature_cache[cache_key] = entry
            self.cache_order.append(cache_key)

            # Enforce cache size limit
            while len(self.feature_cache) > FEATURE_CACHE_SIZE:
                oldest_key = self.cache_order[0]
                if oldest_key in self.feature_cache:
                    del self.feature_cache[oldest_key]

    # ==========================================================================
    # PRIVATE METHODS - MODEL MANAGEMENT
    # ==========================================================================
    def _load_production_models(self) -> None:
        """Load all production models"""
        try:
            active_models = self.model_manager.get_active_models()

            for model_name, model_version in active_models.items():
                if model_version.status == ModelStatus.PRODUCTION:
                    self.load_model(model_name, model_version.model_id)

            self.logger.info("Loaded %s production models", len(self.models))

        except Exception as e:
            self.logger.error("Error loading production models: %s", e, exc_info=True)

    def _warmup_model(self, instance: ModelInstance) -> None:
        """Warm up model with dummy predictions"""
        try:
            # Generate random features
            n_features = len(instance.feature_names)
            dummy_features = np.random.randn(MODEL_WARMUP_SAMPLES, n_features)

            # Make predictions
            start_time = time.time()
            _ = instance.model.predict(dummy_features)
            warmup_time = time.time() - start_time

            self.logger.info(
                f"Warmed up model {instance.model_name} "
                f"({MODEL_WARMUP_SAMPLES} samples in {warmup_time:.2f}s)"
            )

        except Exception as e:
            self.logger.error("Error warming up model: %s", e, exc_info=True)

    # ==========================================================================
    # PRIVATE METHODS - PERFORMANCE
    # ==========================================================================
    def _track_prediction_performance(self, latency_ms: float) -> None:
        """Track prediction performance"""
        self.performance.total_predictions += 1

        # Update average latency
        self.performance.average_latency_ms = (
            (self.performance.average_latency_ms * (self.performance.total_predictions - 1) +
             latency_ms) / self.performance.total_predictions
        )

        # Add to history
        self.latency_history.append(latency_ms)

        # Update histogram
        for bucket in LATENCY_BUCKETS:
            if latency_ms <= bucket:
                self.performance.latency_histogram[bucket] = (
                    self.performance.latency_histogram.get(bucket, 0) + 1
                )
                break
        else:
            # Over max bucket
            self.performance.latency_histogram[LATENCY_BUCKETS[-1] + 1] = (
                self.performance.latency_histogram.get(LATENCY_BUCKETS[-1] + 1, 0) + 1
            )

        # Check for latency violations
        if latency_ms > MAX_PREDICTION_LATENCY_MS:
            self.logger.warning(
                f"Prediction latency violation: {latency_ms:.1f}ms "
                f"(limit: {MAX_PREDICTION_LATENCY_MS}ms)"
            )

    # ==========================================================================
    # PRIVATE METHODS - WORKERS
    # ==========================================================================
    def _prediction_worker(self) -> None:
        """Process prediction queue"""
        while self._running:
            try:
                # Get request from queue
                priority, request = self.prediction_queue.get(timeout=1)

                # Make prediction
                result = self.predict(
                    request.features,
                    request.model_names
                )

                # Call callback
                if request.callback:
                    try:
                        request.callback(result)
                    except Exception as e:
                        self.logger.error("Callback error: %s", e, exc_info=True)

                # Clean up
                if request.request_id in self.result_callbacks:
                    del self.result_callbacks[request.request_id]

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error("Prediction worker error: %s", e, exc_info=True)

    def _warmup_worker(self) -> None:
        """Periodically warm up models"""
        while self._running:
            try:
                # Wait for interval
                time.sleep(WARMUP_INTERVAL_SECONDS)  # thread-safe: time.sleep() intentional

                # Warm up all models
                with self.model_lock:
                    for instance in self.models.values():
                        self._warmup_model(instance)

            except Exception as e:
                self.logger.error("Warmup worker error: %s", e, exc_info=True)

    def _monitor_worker(self) -> None:
        """Monitor performance and emit metrics"""
        while self._running:
            try:
                # Wait 60 seconds
                time.sleep(60)  # thread-safe: time.sleep() intentional

                # Get metrics
                metrics = self.get_performance_metrics()
                model_stats = self.get_model_stats()

                # Log summary
                self.logger.info(
                    f"Performance: {metrics.total_predictions} predictions, "
                    f"avg latency: {metrics.average_latency_ms:.1f}ms, "
                    f"p95: {metrics.p95_latency_ms:.1f}ms, "
                    f"cache hit rate: {metrics.cache_hits / max(1, metrics.cache_hits + metrics.cache_misses):.1%}"
                )

                # Emit metrics event
                self.event_manager.publish(
                    self.event_manager.create_event(
                        EventType.PERFORMANCE,
                        {
                            'component': 'real_time_predictor',
                            'metrics': {
                                'total_predictions': metrics.total_predictions,
                                'average_latency_ms': metrics.average_latency_ms,
                                'p95_latency_ms': metrics.p95_latency_ms,
                                'p99_latency_ms': metrics.p99_latency_ms,
                                'cache_hit_rate': metrics.cache_hits / max(1, metrics.cache_hits + metrics.cache_misses),
                                'error_rate': metrics.errors / max(1, metrics.total_predictions)
                            },
                            'model_stats': model_stats
                        },
                        source='RealTimePredictor'
                    )
                )

                # Check for issues
                if metrics.average_latency_ms > MAX_PREDICTION_LATENCY_MS:
                    self.logger.warning(
                        f"Average latency ({metrics.average_latency_ms:.1f}ms) "
                        f"exceeds target ({MAX_PREDICTION_LATENCY_MS}ms)"
                    )

            except Exception as e:
                self.logger.error("Monitor worker error: %s", e, exc_info=True)

    # ==========================================================================
    # PRIVATE METHODS - EVENTS
    # ==========================================================================
    def _subscribe_to_events(self) -> None:
        """Subscribe to relevant events"""
        # Subscribe to market data updates
        self.event_manager.subscribe(
            [EventType.DATA],
            self._on_market_data,
            subscriber_id="realtime_predictor"
        )

        # Subscribe to model updates
        self.event_manager.subscribe(
            EventType.MODEL_UPDATE,
            self._on_model_update,
            subscriber_id="realtime_predictor"
        )
