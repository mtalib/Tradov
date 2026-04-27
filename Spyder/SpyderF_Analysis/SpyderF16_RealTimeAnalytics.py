#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF16_RealTimeAnalytics.py
Purpose: SPYDER - Autonomous Options Trading System v1.0

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Autonomous Options Trading System v1.0

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import threading
import time
import warnings
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import traceback
import numpy as np
import websockets
from aiohttp import web

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import zmq
    import zmq.asyncio
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False

try:
    import uvloop
    UVLOOP_AVAILABLE = True
except ImportError:
    UVLOOP_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Spyder imports
try:
    from SpyderU01_Logger import SpyderLogger
    from SpyderU02_ErrorHandler import ErrorHandler
except ImportError:
    # Fallback implementations
    SpyderLogger = logging.getLogger
    class ErrorHandler:
        @staticmethod
        def handle_error(error, context=""):
            logging.error("Error in %s: %s", context, error)

# F-series integrations
try:
    from SpyderF13_ModelValidation import ModelValidationEngine  # noqa: F401
    F13_AVAILABLE = True
except ImportError:
    F13_AVAILABLE = False

try:
    from SpyderF14_MarketMicrostructure import MarketMicrostructureEngine  # noqa: F401
    F14_AVAILABLE = True
except ImportError:
    F14_AVAILABLE = False

try:
    from SpyderF_Analysis.SpyderF17_UnifiedPerformanceEngine import UnifiedPerformanceEngine as PerformanceAttributionEngine  # noqa: E501, F401
    F15_AVAILABLE = True
except ImportError:
    F15_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================
# Real-time processing constants
REALTIME_UPDATE_INTERVAL = 0.001  # 1ms update interval
ANALYTICS_BUFFER_SIZE = 10000
MAX_WEBSOCKET_CONNECTIONS = 100
ALERT_COOLDOWN_SECONDS = 5
METRICS_RETENTION_HOURS = 24

# Stream types
STREAM_TYPES = [
    'attribution',
    'factor_exposure',
    'risk_metrics',
    'model_validation',
    'microstructure',
    'alerts',
    'performance',
    'positions'
]

# WebSocket message types
WS_MESSAGE_TYPES = {
    'subscribe': 'stream_subscribe',
    'unsubscribe': 'stream_unsubscribe',
    'data_update': 'stream_data',
    'alert': 'stream_alert',
    'heartbeat': 'heartbeat',
    'status': 'system_status',
    'error': 'error_message'
}

# Performance thresholds for real-time alerts
REALTIME_THRESHOLDS = {
    'latency_warning': 0.005,  # 5ms latency warning
    'latency_critical': 0.020,  # 20ms latency critical
    'memory_warning': 0.80,    # 80% memory usage
    'cpu_warning': 0.85,       # 85% CPU usage
    'queue_warning': 1000,     # 1000 items in queue
    'connection_warning': 80   # 80% of max connections
}

# Dashboard update intervals
UPDATE_INTERVALS = {
    'ultra_fast': 0.001,   # 1ms - for critical metrics
    'fast': 0.010,         # 10ms - for standard metrics
    'medium': 0.100,       # 100ms - for detailed analytics
    'slow': 1.000         # 1s - for historical data
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RealTimeMetric:
    """Container for real-time metric data."""
    metric_id: str
    metric_name: str
    value: float
    timestamp: datetime
    stream_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    alert_triggered: bool = False
    update_interval: float = 0.1

@dataclass
class StreamSubscription:
    """Container for stream subscription information."""
    subscription_id: str
    stream_type: str
    filters: dict[str, Any] = field(default_factory=dict)
    update_interval: float = 0.1
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    websocket: Any = None
    callback: Callable | None = None

@dataclass
class RealTimeAlert:
    """Container for real-time alerts."""
    alert_id: str
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    stream_type: str
    metric_value: float
    threshold: float
    auto_dismiss: bool = True
    dismiss_after: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemStatus:
    """Container for system status information."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    active_connections: int
    processing_latency: float
    queue_size: int
    alerts_active: int
    streams_active: int
    uptime_seconds: float

# ==============================================================================
# MAIN REAL-TIME ANALYTICS ENGINE
# ==============================================================================
class RealTimeAnalyticsEngine:
    """
    Institutional-grade real-time analytics engine for streaming performance analysis.

    Provides ultra-low latency streaming analytics including real-time attribution,
    factor exposure monitoring, live risk calculations, and continuous model validation.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Real-Time Analytics Engine."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = ErrorHandler()

        # Configuration
        self.config = config or {}
        self.websocket_port = self.config.get('websocket_port', 8765)
        self.http_port = self.config.get('http_port', 8766)
        self.update_interval = self.config.get('update_interval', REALTIME_UPDATE_INTERVAL)
        self.enable_redis = self.config.get('enable_redis', False) and REDIS_AVAILABLE
        self.enable_zmq = self.config.get('enable_zmq', False) and ZMQ_AVAILABLE

        # Internal state
        self.start_time = datetime.now(timezone.utc)
        self.running = False
        self.metrics_buffer = {}
        self.active_subscriptions = {}
        self.active_alerts = {}
        self.websocket_connections = set()
        self.processing_queue = asyncio.Queue(maxsize=ANALYTICS_BUFFER_SIZE)

        # Performance tracking
        self.performance_stats = {
            'messages_processed': 0,
            'alerts_generated': 0,
            'websocket_messages_sent': 0,
            'processing_latency': deque(maxlen=1000),
            'memory_usage': deque(maxlen=1000),
            'cpu_usage': deque(maxlen=1000)
        }

        # Integration components
        self.backtesting_engine = None
        self.model_validator = None
        self.microstructure_engine = None
        self.attribution_engine = None

        # External connections
        self.redis_client = None
        self.zmq_context = None
        self.zmq_publisher = None

        # Async components
        self.event_loop = None
        self.websocket_server = None
        self.http_server = None
        self.processing_tasks = []

        # Thread pool for CPU-intensive operations
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

        # Initialize components
        self._initialize_metrics_buffer()
        self._initialize_alert_system()
        self._initialize_stream_processors()

        self.logger.info("Real-Time Analytics Engine initialized")

    async def initialize(self, enable_integrations: bool = True) -> bool:
        """
        Initialize the real-time analytics engine with async components.

        Args:
            enable_integrations: Whether to enable F12-F15 integrations

        Returns:
            bool: True if initialization successful
        """
        try:
            # Set up event loop optimization
            if UVLOOP_AVAILABLE and hasattr(asyncio, 'set_event_loop_policy'):
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

            self.event_loop = asyncio.get_running_loop()

            # Initialize external connections
            if self.enable_redis:
                await self._initialize_redis()

            if self.enable_zmq:
                await self._initialize_zmq()

            # Initialize F-series integrations
            if enable_integrations:
                await self._initialize_f_series_integrations()

            # Start processing tasks
            await self._start_processing_tasks()

            # Start servers
            await self._start_websocket_server()
            await self._start_http_server()

            self.running = True
            self.logger.info("Real-time analytics engine fully initialized")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeAnalyticsEngine.initialize")
            return False

    def _initialize_metrics_buffer(self) -> None:
        """Initialize metrics buffer for each stream type."""
        for stream_type in STREAM_TYPES:
            self.metrics_buffer[stream_type] = deque(maxlen=ANALYTICS_BUFFER_SIZE)

        self.logger.debug("Metrics buffer initialized")

    def _initialize_alert_system(self) -> None:
        """Initialize real-time alert system."""
        self.alert_processors = {
            'latency': self._process_latency_alerts,
            'performance': self._process_performance_alerts,
            'system': self._process_system_alerts,
            'attribution': self._process_attribution_alerts,
            'risk': self._process_risk_alerts
        }

        self.logger.debug("Alert system initialized")

    def _initialize_stream_processors(self) -> None:
        """Initialize stream processing functions."""
        self.stream_processors = {
            'attribution': self._process_attribution_stream,
            'factor_exposure': self._process_factor_exposure_stream,
            'risk_metrics': self._process_risk_metrics_stream,
            'model_validation': self._process_model_validation_stream,
            'microstructure': self._process_microstructure_stream,
            'alerts': self._process_alerts_stream,
            'performance': self._process_performance_stream,
            'positions': self._process_positions_stream
        }

        self.logger.debug("Stream processors initialized")

    async def _initialize_redis(self) -> None:
        """Initialize Redis connection for caching."""
        try:
            self.redis_client = redis.Redis(
                host=self.config.get('redis_host', 'localhost'),
                port=self.config.get('redis_port', 6379),
                decode_responses=True
            )

            # Test connection
            await self.redis_client.ping()
            self.logger.info("Redis connection established")

        except Exception as e:
            self.logger.warning("Redis initialization failed: %s", e)
            self.redis_client = None

    async def _initialize_zmq(self) -> None:
        """Initialize ZeroMQ for high-performance messaging."""
        try:
            self.zmq_context = zmq.asyncio.Context()
            self.zmq_publisher = self.zmq_context.socket(zmq.PUB)

            zmq_port = self.config.get('zmq_port', 5555)
            self.zmq_publisher.bind(f"tcp://*:{zmq_port}")

            self.logger.info("ZeroMQ publisher started on port %s", zmq_port)

        except Exception as e:
            self.logger.warning("ZeroMQ initialization failed: %s", e)
            self.zmq_publisher = None

    async def _initialize_f_series_integrations(self) -> None:
        """Initialize integrations with F13-F15 modules."""
        try:
            # F13 Model Validation integration
            if F13_AVAILABLE:
                self.model_validator = None  # Would get singleton in production
                self.logger.info("F13 model validation integration initialized")

            # F14 Market Microstructure integration
            if F14_AVAILABLE:
                self.microstructure_engine = None  # Would get singleton in production
                self.logger.info("F14 market microstructure integration initialized")

            # F15 Performance Attribution integration
            if F15_AVAILABLE:
                self.attribution_engine = None  # Would get singleton in production
                self.logger.info("F15 performance attribution integration initialized")

        except Exception as e:
            self.logger.warning("F-series integration failed: %s", e)

    async def _start_processing_tasks(self) -> None:
        """Start background processing tasks."""
        try:
            # Main metrics processing task
            self.processing_tasks.append(
                asyncio.create_task(self._metrics_processing_loop())
            )

            # Alert processing task
            self.processing_tasks.append(
                asyncio.create_task(self._alert_processing_loop())
            )

            # System monitoring task
            self.processing_tasks.append(
                asyncio.create_task(self._system_monitoring_loop())
            )

            # Stream broadcasting task
            self.processing_tasks.append(
                asyncio.create_task(self._stream_broadcasting_loop())
            )

            # Cleanup task
            self.processing_tasks.append(
                asyncio.create_task(self._cleanup_loop())
            )

            self.logger.info("Started %s processing tasks", len(self.processing_tasks))

        except Exception as e:
            self.error_handler.handle_error(e, context="_start_processing_tasks")

    async def _start_websocket_server(self) -> None:
        """Start WebSocket server for real-time data streaming."""
        try:
            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                "0.0.0.0",
                self.websocket_port,
                max_size=2**20,  # 1MB max message size
                max_queue=100,
                compression=None  # Disable compression for lower latency
            )

            self.logger.info("WebSocket server started on port %s", self.websocket_port)

        except Exception as e:
            self.error_handler.handle_error(e, context="_start_websocket_server")

    async def _start_http_server(self) -> None:
        """Start HTTP server for REST API endpoints."""
        try:
            app = web.Application()

            # Add routes
            app.router.add_get('/health', self._handle_health_check)
            app.router.add_get('/status', self._handle_status)
            app.router.add_get('/metrics', self._handle_metrics)
            app.router.add_get('/alerts', self._handle_alerts)
            app.router.add_post('/subscribe', self._handle_subscribe)
            app.router.add_post('/unsubscribe', self._handle_unsubscribe)

            # Add CORS headers
            app.router.add_options('/{path:.*}', self._handle_options)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, '0.0.0.0', self.http_port)
            await site.start()

            self.logger.info("HTTP server started on port %s", self.http_port)

        except Exception as e:
            self.error_handler.handle_error(e, context="_start_http_server")

    # ==============================================================================
    # CORE REAL-TIME PROCESSING METHODS
    # ==============================================================================
    async def add_metric(
        self,
        stream_type: str,
        metric_name: str,
        value: float,
        metadata: dict[str, Any] = None
    ) -> bool:
        """
        Add a real-time metric to the processing queue.

        Args:
            stream_type: Type of stream (attribution, risk_metrics, etc.)
            metric_name: Name of the metric
            value: Metric value
            metadata: Additional metadata

        Returns:
            bool: True if metric was queued successfully
        """
        try:
            if not self.running:
                return False

            metric = RealTimeMetric(
                metric_id=str(uuid.uuid4()),
                metric_name=metric_name,
                value=value,
                timestamp=datetime.now(timezone.utc),
                stream_type=stream_type,
                metadata=metadata or {},
                update_interval=UPDATE_INTERVALS.get(stream_type, UPDATE_INTERVALS['medium'])
            )

            # Add to processing queue
            if not self.processing_queue.full():
                await self.processing_queue.put(metric)
                return True
            else:
                self.logger.warning("Processing queue full, dropping metric: %s", metric_name)
                return False

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeAnalyticsEngine.add_metric")
            return False

    async def subscribe_to_stream(
        self,
        stream_type: str,
        websocket: Any = None,
        callback: Callable = None,
        filters: dict[str, Any] = None,
        update_interval: float = 0.1
    ) -> str:
        """
        Subscribe to a real-time data stream.

        Args:
            stream_type: Type of stream to subscribe to
            websocket: WebSocket connection (optional)
            callback: Callback function (optional)
            filters: Stream filters
            update_interval: Update interval in seconds

        Returns:
            str: Subscription ID
        """
        try:
            subscription_id = str(uuid.uuid4())

            subscription = StreamSubscription(
                subscription_id=subscription_id,
                stream_type=stream_type,
                filters=filters or {},
                update_interval=update_interval,
                websocket=websocket,
                callback=callback
            )

            self.active_subscriptions[subscription_id] = subscription

            self.logger.debug("Created subscription %s for stream %s", subscription_id, stream_type)
            return subscription_id

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeAnalyticsEngine.subscribe_to_stream")  # noqa: E501
            return ""

    async def unsubscribe_from_stream(self, subscription_id: str) -> bool:
        """
        Unsubscribe from a real-time data stream.

        Args:
            subscription_id: Subscription ID to remove

        Returns:
            bool: True if unsubscribed successfully
        """
        try:
            if subscription_id in self.active_subscriptions:
                self.active_subscriptions[subscription_id].active = False
                del self.active_subscriptions[subscription_id]
                self.logger.debug("Removed subscription %s", subscription_id)
                return True
            return False

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeAnalyticsEngine.unsubscribe_from_stream")  # noqa: E501
            return False

    # ==============================================================================
    # STREAM PROCESSING METHODS
    # ==============================================================================
    async def _process_attribution_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process attribution stream data."""
        try:
            # Real-time attribution calculation
            attribution_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'attribution_value': metric.value,
                'metric_name': metric.metric_name,
                'stream_type': 'attribution'
            }

            # Add factor contributions if available
            if 'factor_contributions' in metric.metadata:
                attribution_data['factor_contributions'] = metric.metadata['factor_contributions']

            # Check for attribution alerts
            if abs(metric.value) > 0.01:  # 1% threshold
                await self._generate_realtime_alert(
                    'attribution_significant',
                    'info',
                    f"Significant attribution detected: {metric.metric_name} = {metric.value:.4f}",
                    metric.stream_type,
                    metric.value,
                    0.01
                )

            return attribution_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_attribution_stream")
            return {}

    async def _process_factor_exposure_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process factor exposure stream data."""
        try:
            exposure_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'factor_exposure': metric.value,
                'factor_name': metric.metric_name,
                'stream_type': 'factor_exposure'
            }

            # Add exposure statistics
            if 'exposure_stats' in metric.metadata:
                exposure_data.update(metric.metadata['exposure_stats'])

            # Check for extreme exposures
            if abs(metric.value) > 2.0:  # 2 standard deviations
                await self._generate_realtime_alert(
                    'extreme_exposure',
                    'warning',
                    f"Extreme factor exposure: {metric.metric_name} = {metric.value:.2f}",
                    metric.stream_type,
                    metric.value,
                    2.0
                )

            return exposure_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_factor_exposure_stream")
            return {}

    async def _process_risk_metrics_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process risk metrics stream data."""
        try:
            risk_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'risk_value': metric.value,
                'risk_metric': metric.metric_name,
                'stream_type': 'risk_metrics'
            }

            # Add risk breakdown if available
            if 'risk_components' in metric.metadata:
                risk_data['risk_components'] = metric.metadata['risk_components']

            # Check for risk limit breaches
            risk_limits = {
                'var': 0.05,
                'tracking_error': 0.03,
                'max_drawdown': 0.10,
                'leverage': 2.0
            }

            limit = risk_limits.get(metric.metric_name.lower(), float('inf'))
            if metric.value > limit:
                await self._generate_realtime_alert(
                    'risk_limit_breach',
                    'critical',
                    f"Risk limit breach: {metric.metric_name} = {metric.value:.4f} > {limit:.4f}",
                    metric.stream_type,
                    metric.value,
                    limit
                )

            return risk_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_risk_metrics_stream")
            return {}

    async def _process_model_validation_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process model validation stream data."""
        try:
            validation_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'validation_score': metric.value,
                'model_metric': metric.metric_name,
                'stream_type': 'model_validation'
            }

            # Add model diagnostics if available
            if 'model_diagnostics' in metric.metadata:
                validation_data['diagnostics'] = metric.metadata['model_diagnostics']

            # Check for model degradation
            if metric.metric_name == 'accuracy' and metric.value < 0.6:
                await self._generate_realtime_alert(
                    'model_degradation',
                    'warning',
                    f"Model accuracy degraded: {metric.value:.3f} < 0.6",
                    metric.stream_type,
                    metric.value,
                    0.6
                )

            return validation_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_model_validation_stream")
            return {}

    async def _process_microstructure_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process market microstructure stream data."""
        try:
            microstructure_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'microstructure_value': metric.value,
                'microstructure_metric': metric.metric_name,
                'stream_type': 'microstructure'
            }

            # Add order flow data if available
            if 'order_flow' in metric.metadata:
                microstructure_data['order_flow'] = metric.metadata['order_flow']

            # Check for liquidity alerts
            if metric.metric_name == 'bid_ask_spread' and metric.value > 0.005:
                await self._generate_realtime_alert(
                    'wide_spread',
                    'info',
                    f"Wide bid-ask spread detected: {metric.value:.4f}",
                    metric.stream_type,
                    metric.value,
                    0.005
                )

            return microstructure_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_microstructure_stream")
            return {}

    async def _process_alerts_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process alerts stream data."""
        try:
            alert_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'alert_severity': metric.value,
                'alert_type': metric.metric_name,
                'stream_type': 'alerts'
            }

            # Add alert details if available
            if 'alert_details' in metric.metadata:
                alert_data['details'] = metric.metadata['alert_details']

            return alert_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_alerts_stream")
            return {}

    async def _process_performance_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process performance stream data."""
        try:
            performance_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'performance_value': metric.value,
                'performance_metric': metric.metric_name,
                'stream_type': 'performance'
            }

            # Add performance breakdown if available
            if 'performance_components' in metric.metadata:
                performance_data['components'] = metric.metadata['performance_components']

            # Check for performance alerts
            if metric.metric_name == 'daily_return' and abs(metric.value) > 0.05:
                severity = 'critical' if abs(metric.value) > 0.10 else 'warning'
                await self._generate_realtime_alert(
                    'large_daily_move',
                    severity,
                    f"Large daily return: {metric.value:.3f}",
                    metric.stream_type,
                    metric.value,
                    0.05
                )

            return performance_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_performance_stream")
            return {}

    async def _process_positions_stream(self, metric: RealTimeMetric) -> dict[str, Any]:
        """Process positions stream data."""
        try:
            positions_data = {
                'metric_id': metric.metric_id,
                'timestamp': metric.timestamp.isoformat(),
                'position_value': metric.value,
                'position_metric': metric.metric_name,
                'stream_type': 'positions'
            }

            # Add position details if available
            if 'position_details' in metric.metadata:
                positions_data['details'] = metric.metadata['position_details']

            return positions_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_positions_stream")
            return {}

    # ==============================================================================
    # BACKGROUND PROCESSING LOOPS
    # ==============================================================================
    async def _metrics_processing_loop(self) -> None:
        """Main metrics processing loop."""
        self.logger.info("Started metrics processing loop")

        while self.running:
            try:
                # Process metrics from queue
                metric = await asyncio.wait_for(
                    self.processing_queue.get(),
                    timeout=1.0
                )

                start_time = time.time()

                # Process metric through appropriate stream processor
                if metric.stream_type in self.stream_processors:
                    processed_data = await self.stream_processors[metric.stream_type](metric)

                    if processed_data:
                        # Store in buffer
                        self.metrics_buffer[metric.stream_type].append(processed_data)

                        # Cache in Redis if available
                        if self.redis_client:
                            await self._cache_metric(metric.stream_type, processed_data)

                        # Broadcast to ZMQ if available
                        if self.zmq_publisher:
                            await self._broadcast_zmq(metric.stream_type, processed_data)

                # Track performance
                processing_time = time.time() - start_time
                self.performance_stats['processing_latency'].append(processing_time)
                self.performance_stats['messages_processed'] += 1

                # Check processing latency
                if processing_time > REALTIME_THRESHOLDS['latency_warning']:
                    await self._generate_realtime_alert(
                        'high_latency',
                        'warning',
                        f"High processing latency: {processing_time:.4f}s",
                        'system',
                        processing_time,
                        REALTIME_THRESHOLDS['latency_warning']
                    )

            except TimeoutError:
                # No metrics to process, continue
                continue
            except Exception as e:
                self.error_handler.handle_error(e, context="_metrics_processing_loop")
                await asyncio.sleep(0.1)  # Brief pause on error

        self.logger.info("Metrics processing loop stopped")

    async def _alert_processing_loop(self) -> None:
        """Alert processing and management loop."""
        self.logger.info("Started alert processing loop")

        while self.running:
            try:
                current_time = datetime.now(timezone.utc)

                # Process alert dismissal
                expired_alerts = []
                for alert_id, alert in self.active_alerts.items():
                    if (alert.auto_dismiss and
                        current_time - alert.timestamp > alert.dismiss_after):
                        expired_alerts.append(alert_id)

                # Remove expired alerts
                for alert_id in expired_alerts:
                    del self.active_alerts[alert_id]

                # Process alert cooldowns
                # This would implement more sophisticated alert logic in production

                await asyncio.sleep(1.0)  # Check every second

            except Exception as e:
                self.error_handler.handle_error(e, context="_alert_processing_loop")
                await asyncio.sleep(5.0)

        self.logger.info("Alert processing loop stopped")

    async def _system_monitoring_loop(self) -> None:
        """System performance monitoring loop."""
        self.logger.info("Started system monitoring loop")

        while self.running:
            try:
                # Get system metrics
                system_status = await self._get_system_status()

                # Check system thresholds
                if system_status.memory_usage > REALTIME_THRESHOLDS['memory_warning']:
                    await self._generate_realtime_alert(
                        'high_memory',
                        'warning',
                        f"High memory usage: {system_status.memory_usage:.1%}",
                        'system',
                        system_status.memory_usage,
                        REALTIME_THRESHOLDS['memory_warning']
                    )

                if system_status.cpu_usage > REALTIME_THRESHOLDS['cpu_warning']:
                    await self._generate_realtime_alert(
                        'high_cpu',
                        'warning',
                        f"High CPU usage: {system_status.cpu_usage:.1%}",
                        'system',
                        system_status.cpu_usage,
                        REALTIME_THRESHOLDS['cpu_warning']
                    )

                # Store system metrics
                self.performance_stats['memory_usage'].append(system_status.memory_usage)
                self.performance_stats['cpu_usage'].append(system_status.cpu_usage)

                await asyncio.sleep(5.0)  # Check every 5 seconds

            except Exception as e:
                self.error_handler.handle_error(e, context="_system_monitoring_loop")
                await asyncio.sleep(10.0)

        self.logger.info("System monitoring loop stopped")

    async def _stream_broadcasting_loop(self) -> None:
        """Stream broadcasting loop for WebSocket connections."""
        self.logger.info("Started stream broadcasting loop")

        while self.running:
            try:
                current_time = datetime.now(timezone.utc)

                # Broadcast to active subscriptions
                for subscription_id, subscription in list(self.active_subscriptions.items()):
                    if not subscription.active:
                        continue

                    # Check if update interval has passed
                    time_since_update = (current_time - subscription.last_update).total_seconds()
                    if time_since_update < subscription.update_interval:
                        continue

                    # Get latest data for stream type
                    stream_data = await self._get_latest_stream_data(
                        subscription.stream_type,
                        subscription.filters
                    )

                    if stream_data:
                        # Send via WebSocket
                        if subscription.websocket:
                            await self._send_websocket_data(subscription.websocket, stream_data)

                        # Call callback function
                        if subscription.callback:
                            try:
                                await subscription.callback(stream_data)
                            except Exception as e:
                                self.logger.warning("Callback failed for subscription %s: %s", subscription_id, e)  # noqa: E501

                        subscription.last_update = current_time

                await asyncio.sleep(self.update_interval)

            except Exception as e:
                self.error_handler.handle_error(e, context="_stream_broadcasting_loop")
                await asyncio.sleep(1.0)

        self.logger.info("Stream broadcasting loop stopped")

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for removing old data."""
        self.logger.info("Started cleanup loop")

        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                current_time - timedelta(hours=METRICS_RETENTION_HOURS)

                # Clean old metrics from buffers
                for _stream_type, buffer in self.metrics_buffer.items():
                    # Keep only recent metrics
                    # This is a simplified cleanup - in production would be more sophisticated
                    if len(buffer) > ANALYTICS_BUFFER_SIZE * 0.8:
                        # Remove oldest 20% of data
                        remove_count = int(len(buffer) * 0.2)
                        for _ in range(remove_count):
                            buffer.popleft()

                await asyncio.sleep(300)  # Clean every 5 minutes

            except Exception as e:
                self.error_handler.handle_error(e, context="_cleanup_loop")
                await asyncio.sleep(60)

        self.logger.info("Cleanup loop stopped")

    # ==============================================================================
    # WEBSOCKET HANDLERS
    # ==============================================================================
    async def _handle_websocket_connection(self, websocket, path):
        """Handle incoming WebSocket connections."""
        try:
            self.websocket_connections.add(websocket)
            self.logger.debug("WebSocket connection established: %s", websocket.remote_address)

            # Send welcome message
            welcome_msg = {
                'type': WS_MESSAGE_TYPES['status'],
                'message': 'Connected to Spyder Real-Time Analytics',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'available_streams': STREAM_TYPES
            }

            await websocket.send(json.dumps(welcome_msg))

            # Handle messages
            async for message in websocket:
                await self._process_websocket_message(websocket, message)

        except websockets.exceptions.ConnectionClosed:
            self.logger.debug("WebSocket connection closed: %s", websocket.remote_address)
        except Exception as e:
            self.error_handler.handle_error(e, context="_handle_websocket_connection")
        finally:
            self.websocket_connections.discard(websocket)

    async def _process_websocket_message(self, websocket, message: str) -> None:
        """Process incoming WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == WS_MESSAGE_TYPES['subscribe']:
                # Handle subscription request
                stream_type = data.get('stream_type')
                filters = data.get('filters', {})
                update_interval = data.get('update_interval', 0.1)

                if stream_type in STREAM_TYPES:
                    subscription_id = await self.subscribe_to_stream(
                        stream_type=stream_type,
                        websocket=websocket,
                        filters=filters,
                        update_interval=update_interval
                    )

                    response = {
                        'type': WS_MESSAGE_TYPES['status'],
                        'message': f'Subscribed to {stream_type}',
                        'subscription_id': subscription_id,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }

                    await websocket.send(json.dumps(response))

            elif msg_type == WS_MESSAGE_TYPES['unsubscribe']:
                # Handle unsubscription request
                subscription_id = data.get('subscription_id')

                if await self.unsubscribe_from_stream(subscription_id):
                    response = {
                        'type': WS_MESSAGE_TYPES['status'],
                        'message': 'Unsubscribed successfully',
                        'subscription_id': subscription_id,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }

                    await websocket.send(json.dumps(response))

            elif msg_type == WS_MESSAGE_TYPES['heartbeat']:
                # Handle heartbeat
                response = {
                    'type': WS_MESSAGE_TYPES['heartbeat'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }

                await websocket.send(json.dumps(response))

        except json.JSONDecodeError:
            error_response = {
                'type': WS_MESSAGE_TYPES['error'],
                'message': 'Invalid JSON message',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            await websocket.send(json.dumps(error_response))

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_websocket_message")

    async def _send_websocket_data(self, websocket, data: dict[str, Any]) -> None:
        """Send data to WebSocket connection."""
        try:
            message = {
                'type': WS_MESSAGE_TYPES['data_update'],
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            await websocket.send(json.dumps(message))
            self.performance_stats['websocket_messages_sent'] += 1

        except websockets.exceptions.ConnectionClosed:
            # Connection closed, remove from active connections
            self.websocket_connections.discard(websocket)
        except Exception as e:
            self.error_handler.handle_error(e, context="_send_websocket_data")

    # ==============================================================================
    # HTTP HANDLERS
    # ==============================================================================
    async def _handle_health_check(self, request) -> web.Response:
        """Handle health check endpoint."""
        health_status = {
            'status': 'healthy' if self.running else 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            'active_connections': len(self.websocket_connections),
            'active_subscriptions': len(self.active_subscriptions),
            'processing_queue_size': self.processing_queue.qsize()
        }

        return web.json_response(health_status)

    async def _handle_status(self, request) -> web.Response:
        """Handle system status endpoint."""
        system_status = await self._get_system_status()
        return web.json_response(asdict(system_status))

    async def _handle_metrics(self, request) -> web.Response:
        """Handle metrics endpoint."""
        stream_type = request.query.get('stream_type', 'all')
        limit = int(request.query.get('limit', '100'))

        if stream_type == 'all':
            metrics_data = {}
            for st in STREAM_TYPES:
                buffer_data = list(self.metrics_buffer[st])[-limit:]
                metrics_data[st] = buffer_data
        else:
            if stream_type in self.metrics_buffer:
                buffer_data = list(self.metrics_buffer[stream_type])[-limit:]
                metrics_data = {stream_type: buffer_data}
            else:
                metrics_data = {}

        return web.json_response(metrics_data)

    async def _handle_alerts(self, request) -> web.Response:
        """Handle alerts endpoint."""
        alert_data = []
        for alert in self.active_alerts.values():
            alert_data.append({
                'alert_id': alert.alert_id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'stream_type': alert.stream_type,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold
            })

        return web.json_response(alert_data)

    async def _handle_subscribe(self, request) -> web.Response:
        """Handle subscription endpoint."""
        try:
            data = await request.json()
            stream_type = data.get('stream_type')
            filters = data.get('filters', {})
            update_interval = data.get('update_interval', 0.1)

            if stream_type not in STREAM_TYPES:
                return web.json_response(
                    {'error': f'Invalid stream type: {stream_type}'},
                    status=400
                )

            subscription_id = await self.subscribe_to_stream(
                stream_type=stream_type,
                filters=filters,
                update_interval=update_interval
            )

            return web.json_response({
                'subscription_id': subscription_id,
                'stream_type': stream_type,
                'status': 'subscribed'
            })

        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def _handle_unsubscribe(self, request) -> web.Response:
        """Handle unsubscription endpoint."""
        try:
            data = await request.json()
            subscription_id = data.get('subscription_id')

            success = await self.unsubscribe_from_stream(subscription_id)

            if success:
                return web.json_response({
                    'subscription_id': subscription_id,
                    'status': 'unsubscribed'
                })
            else:
                return web.json_response(
                    {'error': 'Subscription not found'},
                    status=404
                )

        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    async def _handle_options(self, request) -> web.Response:
        """Handle CORS preflight requests."""
        return web.Response(
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        )

    # ==============================================================================
    # UTILITY METHODS
    # ==============================================================================
    async def _generate_realtime_alert(
        self,
        alert_type: str,
        severity: str,
        message: str,
        stream_type: str,
        metric_value: float,
        threshold: float
    ) -> None:
        """Generate a real-time alert."""
        try:
            # Check alert cooldown
            alert_key = f"{alert_type}_{stream_type}"
            current_time = datetime.now(timezone.utc)

            # Simple cooldown mechanism
            if hasattr(self, '_last_alert_times'):
                last_time = self._last_alert_times.get(alert_key)
                if (last_time and
                    (current_time - last_time).total_seconds() < ALERT_COOLDOWN_SECONDS):
                    return
            else:
                self._last_alert_times = {}

            self._last_alert_times[alert_key] = current_time

            # Create alert
            alert = RealTimeAlert(
                alert_id=str(uuid.uuid4()),
                alert_type=alert_type,
                severity=severity,
                message=message,
                timestamp=current_time,
                stream_type=stream_type,
                metric_value=metric_value,
                threshold=threshold
            )

            self.active_alerts[alert.alert_id] = alert
            self.performance_stats['alerts_generated'] += 1

            # Broadcast alert to subscribers
            alert_data = {
                'alert_id': alert.alert_id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'timestamp': alert.timestamp.isoformat(),
                'stream_type': alert.stream_type,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold
            }

            # Send to WebSocket subscribers
            for websocket in list(self.websocket_connections):
                try:
                    alert_message = {
                        'type': WS_MESSAGE_TYPES['alert'],
                        'data': alert_data,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    await websocket.send(json.dumps(alert_message))
                except Exception:
                    # Remove failed connection
                    self.websocket_connections.discard(websocket)

            # Log alert
            log_level = {
                'info': self.logger.info,
                'warning': self.logger.warning,
                'critical': self.logger.error,
                'emergency': self.logger.critical
            }.get(severity, self.logger.info)

            log_level(f"Real-time Alert [{severity.upper()}]: {message}")

        except Exception as e:
            self.error_handler.handle_error(e, context="_generate_realtime_alert")

    async def _get_system_status(self) -> SystemStatus:
        """Get current system status."""
        try:
            import psutil

            # Get CPU and memory usage
            cpu_usage = psutil.cpu_percent(interval=0.1) / 100.0
            memory_usage = psutil.virtual_memory().percent / 100.0

            # Calculate uptime
            uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()

            status = SystemStatus(
                timestamp=datetime.now(timezone.utc),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                active_connections=len(self.websocket_connections),
                processing_latency=np.mean(list(self.performance_stats['processing_latency'])) if self.performance_stats['processing_latency'] else 0,  # noqa: E501
                queue_size=self.processing_queue.qsize(),
                alerts_active=len(self.active_alerts),
                streams_active=len(self.active_subscriptions),
                uptime_seconds=uptime_seconds
            )

            return status

        except ImportError:
            # Fallback if psutil not available
            return SystemStatus(
                timestamp=datetime.now(timezone.utc),
                cpu_usage=0.0,
                memory_usage=0.0,
                active_connections=len(self.websocket_connections),
                processing_latency=0.0,
                queue_size=self.processing_queue.qsize(),
                alerts_active=len(self.active_alerts),
                streams_active=len(self.active_subscriptions),
                uptime_seconds=(datetime.now(timezone.utc) - self.start_time).total_seconds()
            )
        except Exception as e:
            self.error_handler.handle_error(e, context="_get_system_status")
            return SystemStatus(
                timestamp=datetime.now(timezone.utc),
                cpu_usage=0.0,
                memory_usage=0.0,
                active_connections=0,
                processing_latency=0.0,
                queue_size=0,
                alerts_active=0,
                streams_active=0,
                uptime_seconds=0.0
            )

    async def _get_latest_stream_data(
        self,
        stream_type: str,
        filters: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Get latest data for a stream type."""
        try:
            if stream_type not in self.metrics_buffer:
                return None

            buffer = self.metrics_buffer[stream_type]
            if not buffer:
                return None

            # Get latest data point
            latest_data = buffer[-1].copy()

            # Apply filters if specified
            if filters:
                for filter_key, filter_value in filters.items():
                    if filter_key in latest_data:
                        if latest_data[filter_key] != filter_value:
                            return None  # Data doesn't match filter

            return latest_data

        except Exception as e:
            self.error_handler.handle_error(e, context="_get_latest_stream_data")
            return None

    async def _cache_metric(self, stream_type: str, data: dict[str, Any]) -> None:
        """Cache metric data in Redis."""
        try:
            if not self.redis_client:
                return

            # Create cache key
            timestamp = data.get('timestamp', datetime.now(timezone.utc).isoformat())
            cache_key = f"spyder:rt_analytics:{stream_type}:{timestamp}"

            # Store data with expiration
            await self.redis_client.setex(
                cache_key,
                timedelta(hours=1),
                json.dumps(data)
            )

        except Exception as e:
            self.error_handler.handle_error(e, context="_cache_metric")

    async def _broadcast_zmq(self, stream_type: str, data: dict[str, Any]) -> None:
        """Broadcast data via ZeroMQ."""
        try:
            if not self.zmq_publisher:
                return

            # Create message
            message = {
                'stream_type': stream_type,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Send multipart message [topic, data]
            await self.zmq_publisher.send_multipart([
                stream_type.encode('utf-8'),
                json.dumps(message).encode('utf-8')
            ])

        except Exception as e:
            self.error_handler.handle_error(e, context="_broadcast_zmq")

    async def shutdown(self) -> None:
        """Shutdown the real-time analytics engine."""
        try:
            self.logger.info("Shutting down real-time analytics engine...")

            self.running = False

            # Cancel processing tasks
            for task in self.processing_tasks:
                task.cancel()

            await asyncio.gather(*self.processing_tasks, return_exceptions=True)

            # Close WebSocket connections
            for websocket in list(self.websocket_connections):
                await websocket.close()

            # Close WebSocket server
            if self.websocket_server:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()

            # Close HTTP server
            if hasattr(self, 'http_runner'):
                await self.http_runner.cleanup()

            # Close external connections
            if self.redis_client:
                await self.redis_client.close()

            if self.zmq_publisher:
                self.zmq_publisher.close()

            if self.zmq_context:
                self.zmq_context.term()

            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)

            self.logger.info("Real-time analytics engine shutdown complete")

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeAnalyticsEngine.shutdown")

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================
async def create_sample_realtime_data(engine: RealTimeAnalyticsEngine, duration_seconds: int = 60) -> None:  # noqa: E501
    """
    Generate sample real-time data for testing.

    Args:
        engine: Real-time analytics engine instance
        duration_seconds: Duration to generate data
    """
    try:
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            # Generate sample attribution metrics
            await engine.add_metric(
                'attribution',
                'factor_alpha',
                np.random.normal(0.0005, 0.002),
                {'factor_contributions': {'market': 0.001, 'size': -0.0005}}
            )

            # Generate factor exposure metrics
            await engine.add_metric(
                'factor_exposure',
                'market_beta',
                np.random.normal(1.0, 0.1),
                {'exposure_stats': {'zscore': np.random.normal(0, 1)}}
            )

            # Generate risk metrics
            await engine.add_metric(
                'risk_metrics',
                'portfolio_var',
                abs(np.random.normal(0.02, 0.005)),
                {'risk_components': {'systematic': 0.015, 'idiosyncratic': 0.005}}
            )

            # Generate performance metrics
            await engine.add_metric(
                'performance',
                'daily_return',
                np.random.normal(0.001, 0.01),
                {'performance_components': {'alpha': 0.0005, 'beta': 0.0008}}
            )

            await asyncio.sleep(0.1)  # 100ms intervals

    except Exception as e:
        logging.error("Error generating sample data: %s", e)

# Global instance for singleton pattern
_realtime_engine_instance = None
_realtime_engine_instance_lock = threading.Lock()


def get_realtime_analytics_engine(config: dict[str, Any] | None = None) -> RealTimeAnalyticsEngine:
    """
    Get global Real-Time Analytics Engine instance (singleton pattern).

    Args:
        config: Optional configuration dictionary

    Returns:
        RealTimeAnalyticsEngine instance
    """
    global _realtime_engine_instance
    if _realtime_engine_instance is None:
        with _realtime_engine_instance_lock:
            if _realtime_engine_instance is None:
                _realtime_engine_instance = RealTimeAnalyticsEngine(config)
    return _realtime_engine_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    logging.info("Real-Time Analytics Engine - Spyder F16")
    logging.info("=" * 80)

    try:
        # Create real-time analytics engine
        config = {
            'websocket_port': 8765,
            'http_port': 8766,
            'update_interval': 0.01,  # 10ms updates
            'enable_redis': False,
            'enable_zmq': False
        }

        engine = RealTimeAnalyticsEngine(config)
        logging.info("Real-Time Analytics Engine initialized")

        # Initialize engine
        if not await engine.initialize(enable_integrations=True):
            logging.info("Failed to initialize real-time analytics engine")
            return False

        logging.info("Integration status:")
        logging.info("   F13 Validation: %s", 'Connected' if getattr(engine, 'model_validator', None) else 'Not available')  # noqa: E501
        logging.info("   F13 Model Validation: %s", 'Connected' if engine.model_validator else 'Not available')  # noqa: E501
        logging.info("   F14 Market Microstructure: %s", 'Connected' if engine.microstructure_engine else 'Not available')  # noqa: E501
        logging.info("   F15 Performance Attribution: %s", 'Connected' if engine.attribution_engine else 'Not available')  # noqa: E501

        logging.info("\nWebSocket server: ws://localhost:%s", config['websocket_port'])
        logging.info("HTTP server: http://localhost:%s", config['http_port'])
        logging.info("\nAvailable streams:")
        for stream in STREAM_TYPES:
            logging.info("   • %s", stream)

        # Generate sample data
        logging.info("\nGenerating sample real-time data...")
        data_task = asyncio.create_task(create_sample_realtime_data(engine, 30))

        # Run for 30 seconds
        logging.info("Running real-time analytics for 30 seconds...")
        await asyncio.sleep(30)

        # Cancel data generation
        data_task.cancel()

        # Get final status
        status = await engine._get_system_status()
        logging.info("\nFinal Statistics:")
        logging.info(f"   Messages Processed: {engine.performance_stats['messages_processed']:,}")
        logging.info("   Alerts Generated: %s", engine.performance_stats['alerts_generated'])
        logging.info(f"   WebSocket Messages Sent: {engine.performance_stats['websocket_messages_sent']:,}")  # noqa: E501
        logging.info("   Active Connections: %s", status.active_connections)
        logging.info("   Active Subscriptions: %s", status.streams_active)
        logging.info("   Active Alerts: %s", status.alerts_active)

        if engine.performance_stats['processing_latency']:
            avg_latency = np.mean(list(engine.performance_stats['processing_latency']))
            logging.info(f"   Average Processing Latency: {avg_latency:.6f}s ({avg_latency*1000:.2f}ms)")  # noqa: E501

        logging.info(f"   System Uptime: {status.uptime_seconds:.1f}s")

        # Demonstrate API endpoints
        logging.info("\nAPI Endpoints:")
        logging.info("   Health: GET http://localhost:%s/health", config['http_port'])
        logging.info("   Status: GET http://localhost:%s/status", config['http_port'])
        logging.info("   Metrics: GET http://localhost:%s/metrics", config['http_port'])
        logging.info("   Alerts: GET http://localhost:%s/alerts", config['http_port'])
        logging.info("   Subscribe: POST http://localhost:%s/subscribe", config['http_port'])

        logging.info("\nSpyder F16 Real-Time Analytics Engine demonstration completed successfully!")  # noqa: E501
        return True

    except Exception as e:
        logging.info("Error in main execution: %s", e)
        traceback.print_exc()
        return False

    finally:
        # Clean up
        if 'engine' in locals():
            await engine.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
