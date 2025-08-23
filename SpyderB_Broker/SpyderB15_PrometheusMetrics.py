#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker [Application Name] [Series Letter] [Series Name] 
Module: SpyderB15_PrometheusMetrics.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: Prometheus metrics collection and HTTP endpoint without IB Client dependency
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-20 Time: 14:30:00  

Module Description:
    Centralized Prometheus metrics collection and HTTP endpoint for the Spyder
    trading system. Collects metrics from all system components through callback
    registration without requiring dedicated IB Client connections. Provides
    thread-safe metrics aggregation, professional HTTP endpoint on port 9090,
    and seamless integration with existing dashboard and monitoring infrastructure.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import time
import queue
import json
import sys
import os
from typing import Dict, List, Optional, Callable, Any, Protocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# Prometheus client
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    start_http_server, CollectorRegistry, 
    generate_latest, CONTENT_TYPE_LATEST
)
import psutil

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Local imports
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    print("⚠️ Local utilities not available - using standard logging")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default configuration
DEFAULT_METRICS_PORT = 9090
DEFAULT_COLLECTION_INTERVAL = 5.0  # seconds
DEFAULT_MAX_QUEUE_SIZE = 10000
DEFAULT_HOST = "0.0.0.0"

# Metric namespaces
NAMESPACE = "spyder"
SUBSYSTEM_GATEWAY = "gateway"
SUBSYSTEM_TRADING = "trading"
SUBSYSTEM_SYSTEM = "system"
SUBSYSTEM_MARKET = "market"

# Update intervals
UPDATE_INTERVAL = 10  # Metrics update interval (seconds)
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

# ==============================================================================
# ENUMS
# ==============================================================================
class MetricsState(Enum):
    """Metrics collector state enumeration"""
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class MetricType(Enum):
    """Prometheus metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

class ComponentHealth(Enum):
    """Component health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_METRICS_PORT
    collection_interval: float = DEFAULT_COLLECTION_INTERVAL
    max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE
    enable_system_metrics: bool = True
    enable_trading_metrics: bool = True
    enable_market_metrics: bool = True
    enable_gateway_metrics: bool = True
    enable_debug_logging: bool = False

@dataclass
class MetricEvent:
    """Immutable metric event for thread-safe processing"""
    component: str
    metric_type: str
    metric_name: str
    value: float
    labels: Dict[str, str]
    timestamp: float = field(default_factory=time.time)

@dataclass
class ClientMetrics:
    """Metrics for a specific client"""
    client_id: int
    purpose: str
    connected: bool = False
    uptime_seconds: float = 0.0
    latency_ms: float = 0.0
    error_count: int = 0
    reconnection_count: int = 0
    messages_processed: int = 0
    rate_limit_usage: float = 0.0

@dataclass
class ComponentStatus:
    """Status information for system components"""
    name: str
    health: ComponentHealth
    last_update: datetime
    error_message: Optional[str] = None
    metrics_data: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ==============================================================================
class SpyderMetrics:
    """Centralized Prometheus metrics definitions"""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics with optional custom registry"""
        self.registry = registry or CollectorRegistry()
        self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Initialize all Prometheus metrics"""
        
        # System Information
        self.system_info = Info(
            "spyder_system_info", 
            "System information", 
            namespace=NAMESPACE, 
            registry=self.registry
        )
        
        # ==================================================================
        # GATEWAY METRICS
        # ==================================================================
        self.gateway_connected = Gauge(
            "gateway_connected",
            "IB Gateway connection status by client",
            ["client_id", "purpose"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_GATEWAY,
            registry=self.registry
        )
        
        self.gateway_uptime = Gauge(
            "gateway_uptime_seconds",
            "Gateway uptime in seconds",
            ["client_id"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_GATEWAY,
            registry=self.registry
        )
        
        self.gateway_latency = Histogram(
            "gateway_latency_seconds",
            "Gateway API latency by operation",
            ["client_id", "operation"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_GATEWAY,
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )
        
        self.gateway_errors = Counter(
            "gateway_errors_total",
            "Total gateway errors by client and type",
            ["client_id", "error_type"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_GATEWAY,
            registry=self.registry
        )
        
        # ==================================================================
        # TRADING METRICS
        # ==================================================================
        self.orders_submitted = Counter(
            "orders_submitted_total",
            "Total orders submitted",
            ["symbol", "order_type", "action"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_TRADING,
            registry=self.registry
        )
        
        self.orders_filled = Counter(
            "orders_filled_total",
            "Total orders filled",
            ["symbol", "order_type", "action"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_TRADING,
            registry=self.registry
        )
        
        self.position_count = Gauge(
            "position_count",
            "Number of open positions",
            ["symbol"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_TRADING,
            registry=self.registry
        )
        
        self.position_value = Gauge(
            "position_value_usd",
            "Position market value in USD",
            ["symbol"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_TRADING,
            registry=self.registry
        )
        
        # ==================================================================
        # SYSTEM METRICS
        # ==================================================================
        self.system_cpu_usage = Gauge(
            "system_cpu_usage_percent",
            "System CPU usage percentage",
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_SYSTEM,
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            "system_memory_usage_percent",
            "System memory usage percentage",
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_SYSTEM,
            registry=self.registry
        )
        
        self.component_health = Gauge(
            "component_health_status",
            "Component health status (1=healthy, 0=unhealthy)",
            ["component_name"],
            namespace=NAMESPACE,
            subsystem=SUBSYSTEM_SYSTEM,
            registry=self.registry
        )
        
        # ==================================================================
        # MODULE PERFORMANCE METRICS
        # ==================================================================
        self.metrics_collection_duration = Histogram(
            "metrics_collection_duration_seconds",
            "Time spent collecting metrics",
            ["component"],
            namespace=NAMESPACE,
            registry=self.registry
        )
        
        self.metrics_queue_size = Gauge(
            "metrics_queue_size",
            "Current metrics queue size",
            namespace=NAMESPACE,
            registry=self.registry
        )

# ==============================================================================
# METRICS PROVIDER INTERFACES
# ==============================================================================
class MetricsProvider(Protocol):
    """Protocol for components that provide metrics"""
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return current metrics as dictionary"""
        ...
    
    def get_component_name(self) -> str:
        """Return component identifier"""
        ...

class CallbackMetricsProvider:
    """Wrapper for callback-based metrics providers"""
    
    def __init__(self, component_name: str, callback: Callable[[], Dict[str, Any]]):
        self.component_name = component_name
        self.callback = callback
    
    def get_metrics(self) -> Dict[str, Any]:
        """Execute callback to get metrics"""
        try:
            return self.callback()
        except Exception as e:
            # Use module logger if available
            if hasattr(self, 'logger'):
                self.logger.error(f"Error collecting metrics from {self.component_name}: {e}")
            return {}
    
    def get_component_name(self) -> str:
        return self.component_name

# ==============================================================================
# THREAD-SAFE METRICS QUEUE
# ==============================================================================
class ThreadSafeMetricsQueue:
    """Thread-safe queue for metric events"""
    
    def __init__(self, max_size: int = DEFAULT_MAX_QUEUE_SIZE):
        self._queue = queue.Queue(maxsize=max_size)
        self._dropped_count = 0
        self._lock = threading.Lock()
    
    def put_metric(self, event: MetricEvent) -> bool:
        """Add metric event to queue"""
        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            with self._lock:
                self._dropped_count += 1
            return False
    
    def get_metric(self, timeout: float = 1.0) -> Optional[MetricEvent]:
        """Get metric event from queue"""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return self._queue.qsize()
    
    def get_dropped_count(self) -> int:
        """Get number of dropped metrics"""
        with self._lock:
            return self._dropped_count

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PrometheusMetricsCollector:
    """
    Prometheus metrics collection without IB Client dependency.
    
    This class provides centralized metrics collection from all Spyder system
    components through callback registration. It exposes metrics via HTTP endpoint
    for Prometheus scraping and integrates seamlessly with existing dashboard
    and monitoring infrastructure.
    
    Attributes:
        config: Configuration settings
        logger: Module logger instance
        error_handler: Error handling instance
        state: Current module state
        registry: Prometheus metrics registry
        metrics: Prometheus metrics definitions
        
    Example:
        >>> collector = PrometheusMetricsCollector()
        >>> collector.initialize()
        >>> collector.register_component('SystemMonitor', callback_func)
        >>> collector.start()
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """Initialize the Prometheus metrics collector"""
        
        # Configuration
        self.config = config or MetricsConfig()
        
        # Logging setup
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
        
        # State management
        self.state = MetricsState.INITIALIZED
        self.start_time = datetime.now()
        
        # Prometheus setup
        self.registry = CollectorRegistry()
        self.metrics = SpyderMetrics(registry=self.registry)
        
        # Component management
        self.providers: Dict[str, MetricsProvider] = {}
        self.component_statuses: Dict[str, ComponentStatus] = {}
        self.callbacks: List[Callable] = []
        
        # Threading
        self._running = False
        self._collection_thread: Optional[threading.Thread] = None
        self._http_server = None
        self._lock = threading.RLock()
        
        # Metrics queue
        self.metrics_queue = ThreadSafeMetricsQueue(self.config.max_queue_size)
        
        # Client metrics storage
        self.client_metrics: Dict[int, ClientMetrics] = {}
        self._initialize_client_metrics()
        
        # Statistics
        self.total_updates = 0
        
        self.logger.info(f"✅ PrometheusMetricsCollector initialized without IB Client dependency")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize module components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Initialize system info metric
            self.metrics.system_info.info({
                'version': '2.0.0',
                'api': 'callback_based',
                'start_time': self.start_time.isoformat(),
                'no_ib_dependency': 'true'
            })
            
            self.state = MetricsState.RUNNING
            self.logger.info("✅ Prometheus metrics collector initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            self.state = MetricsState.ERROR
            if self.error_handler:
                self.error_handler.handle_error(e, "PrometheusMetrics.initialize")
            return False
    
    def register_component(self, component_name: str, 
                          metrics_callback: Callable[[], Dict[str, Any]]) -> bool:
        """
        Register a component for metrics collection.
        
        Args:
            component_name: Name of the component
            metrics_callback: Callback function that returns metrics dict
            
        Returns:
            bool: True if registration successful
        """
        try:
            with self._lock:
                provider = CallbackMetricsProvider(component_name, metrics_callback)
                self.providers[component_name] = provider
                
                # Initialize component status
                self.component_statuses[component_name] = ComponentStatus(
                    name=component_name,
                    health=ComponentHealth.UNKNOWN,
                    last_update=datetime.now()
                )
                
                self.logger.info(f"📊 Registered metrics provider: {component_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Failed to register component {component_name}: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, f"PrometheusMetrics.register_component.{component_name}")
            return False
    
    def unregister_component(self, component_name: str) -> bool:
        """
        Unregister a component from metrics collection.
        
        Args:
            component_name: Name of the component to unregister
            
        Returns:
            bool: True if unregistration successful
        """
        try:
            with self._lock:
                if component_name in self.providers:
                    del self.providers[component_name]
                    if component_name in self.component_statuses:
                        del self.component_statuses[component_name]
                    
                    self.logger.info(f"📊 Unregistered metrics provider: {component_name}")
                    return True
                else:
                    self.logger.warning(f"⚠️ Component {component_name} not found for unregistration")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to unregister component {component_name}: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, f"PrometheusMetrics.unregister_component.{component_name}")
            return False
    
    def record_order(self, symbol: str, order_type: str, action: str, status: str = "submitted"):
        """
        Record order metrics.
        
        Args:
            symbol: Trading symbol
            order_type: Type of order
            action: Buy/Sell action
            status: Order status
        """
        try:
            if status == "submitted":
                self.metrics.orders_submitted.labels(
                    symbol=symbol,
                    order_type=order_type,
                    action=action
                ).inc()
            elif status == "filled":
                self.metrics.orders_filled.labels(
                    symbol=symbol,
                    order_type=order_type,
                    action=action
                ).inc()
                
        except Exception as e:
            self.logger.error(f"❌ Error recording order metric: {e}")
    
    def update_connection_status(self, client_id: int, connected: bool, purpose: str = ""):
        """
        Update connection status for a client.
        
        Args:
            client_id: IB Client ID (1-10)
            connected: Connection status
            purpose: Purpose description
        """
        try:
            if client_id in self.client_metrics:
                self.client_metrics[client_id].connected = connected
                if purpose:
                    self.client_metrics[client_id].purpose = purpose
                
                self.metrics.gateway_connected.labels(
                    client_id=str(client_id),
                    purpose=self.client_metrics[client_id].purpose
                ).set(1 if connected else 0)
                
        except Exception as e:
            self.logger.error(f"❌ Error updating connection status: {e}")
    
    def record_latency(self, client_id: int, operation: str, latency_seconds: float):
        """
        Record latency measurement.
        
        Args:
            client_id: IB Client ID
            operation: Operation type
            latency_seconds: Latency in seconds
        """
        try:
            self.metrics.gateway_latency.labels(
                client_id=str(client_id),
                operation=operation
            ).observe(latency_seconds)
            
        except Exception as e:
            self.logger.error(f"❌ Error recording latency: {e}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of current metrics for debugging.
        
        Returns:
            Dict with metrics summary
        """
        with self._lock:
            return {
                'state': self.state.value,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'total_updates': self.total_updates,
                'registered_components': list(self.providers.keys()),
                'queue_size': self.metrics_queue.get_queue_size(),
                'dropped_metrics': self.metrics_queue.get_dropped_count(),
                'http_endpoint': f"http://{self.config.host}:{self.config.port}/metrics",
                'ib_dependency': False,
                'integration_method': 'callback_based'
            }
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _initialize_client_metrics(self):
        """Initialize metrics for all IB clients (1-10)"""
        client_purposes = {
            1: "Order Execution",
            2: "Administrative", 
            3: "Core Market Data",
            4: "SPY Options",
            5: "Volatility",
            6: "Market Internals",
            7: "Major Indices",
            8: "Extended Assets",
            9: "Sector ETFs",
            10: "International"
        }
        
        for client_id, purpose in client_purposes.items():
            self.client_metrics[client_id] = ClientMetrics(
                client_id=client_id,
                purpose=purpose
            )
        
        self.logger.info(f"📊 Initialized metrics for {len(client_purposes)} IB clients")
    
    def _collect_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Collect metrics from all registered providers"""
        all_metrics = {}
        
        with self._lock:
            for component_name, provider in self.providers.items():
                try:
                    start_time = time.time()
                    metrics_data = provider.get_metrics()
                    collection_duration = time.time() - start_time
                    
                    # Record collection performance
                    self.metrics.metrics_collection_duration.labels(
                        component=component_name
                    ).observe(collection_duration)
                    
                    if metrics_data:
                        all_metrics[component_name] = metrics_data
                        self._update_component_status(component_name, ComponentHealth.HEALTHY)
                        self._update_prometheus_metrics(component_name, metrics_data)
                    else:
                        self._update_component_status(component_name, ComponentHealth.WARNING, "No metrics data")
                        
                except Exception as e:
                    self.logger.error(f"❌ Error collecting metrics from {component_name}: {e}")
                    self._update_component_status(component_name, ComponentHealth.CRITICAL, str(e))
                    
        return all_metrics
    
    def _update_component_status(self, component_name: str, health: ComponentHealth, 
                                error_message: Optional[str] = None):
        """Update component health status"""
        if component_name in self.component_statuses:
            status = self.component_statuses[component_name]
            status.health = health
            status.last_update = datetime.now()
            status.error_message = error_message
            
            # Update Prometheus metric
            health_value = 1 if health == ComponentHealth.HEALTHY else 0
            self.metrics.component_health.labels(
                component_name=component_name
            ).set(health_value)
    
    def _update_prometheus_metrics(self, component_name: str, metrics_data: Dict[str, Any]):
        """Update Prometheus metrics based on collected data"""
        try:
            # System health metrics
            if 'system_health' in metrics_data:
                health_data = metrics_data['system_health']
                if 'cpu_percent' in health_data:
                    self.metrics.system_cpu_usage.set(health_data['cpu_percent'])
                if 'memory_percent' in health_data:
                    self.metrics.system_memory_usage.set(health_data['memory_percent'])
            
            # Connection metrics
            if 'connections' in metrics_data:
                for conn_id, conn_data in metrics_data['connections'].items():
                    if isinstance(conn_data, dict) and 'status' in conn_data:
                        client_id = conn_id.replace('client_', '')
                        is_connected = conn_data['status'] == 'connected'
                        purpose = conn_data.get('type', 'unknown')
                        
                        self.metrics.gateway_connected.labels(
                            client_id=client_id,
                            purpose=purpose
                        ).set(1 if is_connected else 0)
            
            # Position metrics
            if 'positions' in metrics_data:
                positions = metrics_data['positions']
                if 'count' in positions:
                    self.metrics.position_count.labels(symbol='SPY').set(positions['count'])
                if 'total_value' in positions:
                    self.metrics.position_value.labels(symbol='SPY').set(positions['total_value'])
                    
        except Exception as e:
            self.logger.error(f"❌ Error updating Prometheus metrics: {e}")
    
    def _collection_loop(self):
        """Main collection loop running in separate thread"""
        self.logger.info("🔄 Starting metrics collection loop")
        
        while self._running:
            try:
                # Update queue size metric
                self.metrics.metrics_queue_size.set(self.metrics_queue.get_queue_size())
                
                # Collect system metrics if enabled
                if self.config.enable_system_metrics:
                    self._collect_system_metrics()
                
                # Collect all registered metrics
                start_time = time.time()
                metrics_data = self._collect_all_metrics()
                collection_time = time.time() - start_time
                
                # Update performance stats
                self.total_updates += 1
                
                # Notify dashboard callbacks
                for callback in self.callbacks:
                    try:
                        callback(metrics_data)
                    except Exception as e:
                        self.logger.error(f"❌ Error in dashboard callback: {e}")
                
                # Sleep until next collection interval
                time.sleep(self.config.collection_interval)
                
            except Exception as e:
                self.logger.error(f"❌ Error in collection loop: {e}")
                if self.error_handler:
                    self.error_handler.handle_error(e, "PrometheusMetrics._collection_loop")
                time.sleep(1.0)  # Brief pause before retry
    
    def _collect_system_metrics(self):
        """Collect basic system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.metrics.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.system_memory_usage.set(memory.percent)
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting system metrics: {e}")
    
    def _start_http_server(self):
        """Start Prometheus HTTP server"""
        try:
            self._http_server = start_http_server(
                port=self.config.port,
                addr=self.config.host,
                registry=self.registry
            )
            self.logger.info(
                f"🌐 Prometheus HTTP server started on "
                f"http://{self.config.host}:{self.config.port}/metrics"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start HTTP server: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "PrometheusMetrics._start_http_server")
            raise
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the metrics collector.
        
        Returns:
            bool: True if started successfully
        """
        if self.state != MetricsState.INITIALIZED and self.state != MetricsState.STOPPED:
            self.logger.warning(f"⚠️ Cannot start from state: {self.state}")
            return False
        
        try:
            with self._lock:
                if self._running:
                    self.logger.warning("⚠️ Prometheus metrics already running")
                    return True
                
                self._running = True
                
                # Start HTTP server
                self._start_http_server()
                
                # Start collection thread
                self._collection_thread = threading.Thread(
                    target=self._collection_loop,
                    daemon=True,
                    name="PrometheusMetricsCollector"
                )
                self._collection_thread.start()
                
                self.state = MetricsState.RUNNING
                self.logger.info("🚀 Prometheus metrics collector started successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start metrics collector: {e}")
            self.state = MetricsState.ERROR
            if self.error_handler:
                self.error_handler.handle_error(e, "PrometheusMetrics.start")
            return False
    
    def stop(self) -> bool:
        """
        Stop the metrics collector.
        
        Returns:
            bool: True if stopped successfully
        """
        if self.state != MetricsState.RUNNING:
            self.logger.warning(f"⚠️ Cannot stop from state: {self.state}")
            return False
        
        try:
            with self._lock:
                if not self._running:
                    return True
                
                self._running = False
                
                # Stop collection thread
                if self._collection_thread and self._collection_thread.is_alive():
                    self._collection_thread.join(timeout=5.0)
                    if self._collection_thread.is_alive():
                        self.logger.warning("⚠️ Collection thread did not stop gracefully")
                
                # Stop HTTP server (note: prometheus_client doesn't provide direct server stop)
                # The server will stop when the process exits
                
                self.state = MetricsState.STOPPED
                self.logger.info("⏹️ Prometheus metrics collector stopped")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Error stopping metrics collector: {e}")
            self.state = MetricsState.ERROR
            if self.error_handler:
                self.error_handler.handle_error(e, "PrometheusMetrics.stop")
            return False
    
    def cleanup(self) -> None:
        """Clean up module resources"""
        try:
            # Stop if running
            if self.state == MetricsState.RUNNING:
                self.stop()
            
            # Clear providers and callbacks
            with self._lock:
                self.providers.clear()
                self.component_statuses.clear()
                self.callbacks.clear()
                self.client_metrics.clear()
            
            self.logger.info("🧹 Prometheus metrics collector cleanup completed")
            
        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "PrometheusMetrics.cleanup")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_default_config() -> MetricsConfig:
    """
    Create default metrics configuration.
    
    Returns:
        Default MetricsConfig instance
    """
    return MetricsConfig(
        host=DEFAULT_HOST,
        port=DEFAULT_METRICS_PORT,
        collection_interval=DEFAULT_COLLECTION_INTERVAL,
        max_queue_size=DEFAULT_MAX_QUEUE_SIZE
    )

def get_system_metrics() -> Dict[str, Any]:
    """
    Get current system metrics for dashboard integration.
    
    Returns:
        Dictionary with system metrics
    """
    try:
        return {
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        return {'error': str(e), 'timestamp': datetime.now().isoformat()}

def get_client_status() -> Dict[str, Any]:
    """
    Get IB client status for dashboard integration.
    
    Returns:
        Dictionary with client status information
    """
    # This is a placeholder for dashboard integration
    # In actual implementation, this would query connection managers
    clients_status = {}
    for client_id in range(1, 11):
        clients_status[f'client_{client_id}'] = {
            'connected': False,  # Would be updated by actual connection managers
            'purpose': f'Client {client_id}',
            'last_update': datetime.now().isoformat()
        }
    return clients_status

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level instance management
_prometheus_instance: Optional[PrometheusMetricsCollector] = None
_instance_lock = threading.Lock()

def get_prometheus_instance() -> Optional[PrometheusMetricsCollector]:
    """
    Get singleton instance of the Prometheus metrics collector.
    
    Returns:
        PrometheusMetricsCollector instance or None if not initialized
    """
    with _instance_lock:
        return _prometheus_instance

def initialize_prometheus_metrics(config: Optional[MetricsConfig] = None) -> PrometheusMetricsCollector:
    """
    Initialize and start the global Prometheus metrics instance.
    
    Args:
        config: Optional configuration object
    
    Returns:
        Initialized PrometheusMetricsCollector instance
    """
    global _prometheus_instance
    
    with _instance_lock:
        if _prometheus_instance is not None:
            return _prometheus_instance
        
        _prometheus_instance = PrometheusMetricsCollector(config)
        
        if _prometheus_instance.initialize():
            if _prometheus_instance.start():
                return _prometheus_instance
            else:
                _prometheus_instance = None
                raise RuntimeError("Failed to start Prometheus metrics collector")
        else:
            _prometheus_instance = None
            raise RuntimeError("Failed to initialize Prometheus metrics collector")

def shutdown_prometheus_metrics():
    """Shutdown the global Prometheus metrics instance"""
    global _prometheus_instance
    
    with _instance_lock:
        if _prometheus_instance is not None:
            _prometheus_instance.stop()
            _prometheus_instance.cleanup()
            _prometheus_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("🚀 SpyderB15_PrometheusMetrics - Refactored Version Test")
    print("=" * 60)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create test configuration
        test_config = MetricsConfig(
            port=9091,  # Use different port for testing
            collection_interval=2.0,
            enable_debug_logging=True
        )
        
        # Initialize metrics collector
        collector = initialize_prometheus_metrics(test_config)
        
        # Register test component
        def test_component_metrics():
            return {
                'system_health': {
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'status': 'healthy'
                },
                'connections': {
                    'client_1': {
                        'status': 'connected',
                        'type': 'test_client',
                        'latency_ms': 15.3
                    }
                },
                'module_status': 'running'
            }
        
        collector.register_component('TestComponent', test_component_metrics)
        
        # Test metrics recording
        collector.record_order('SPY', 'MKT', 'BUY', 'submitted')
        collector.update_connection_status(1, True, 'Order Execution')
        collector.record_latency(1, 'heartbeat', 0.015)
        
        # Print status
        summary = collector.get_metrics_summary()
        print("\n📊 Metrics Summary:")
        for key, value in summary.items():
            print(f"   {key}: {value}")
        
        print(f"\n🌐 Metrics available at: http://localhost:{test_config.port}/metrics")
        print("🔄 Metrics collection running...")
        print("Press Ctrl+C to stop...")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping test...")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        shutdown_prometheus_metrics()
        print("✅ Test cleanup completed")
        print("\n🎉 SpyderB15_PrometheusMetrics refactoring test completed!")
