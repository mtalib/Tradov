#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker [Application Name] [Series Letter] [Series Name] 
Module: SpyderB15_PrometheusMetrics.py [Application Name][Series Letter] [Module Number]_[Purpose].py
Purpose: Prometheus metrics collection and monitoring with ib_async integration (Client ID 9)
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-21 Time: 20:58:00  

Module Description:
    Dedicated Prometheus metrics collection using Client ID 9 with ib_async
    compatibility for IB Gateway 10.37+. This module collects comprehensive 
    metrics from all system components and exposes them for Prometheus scraping. 
    It monitors connection health, trading performance, system resources, and 
    provides alerting capabilities for the entire Spyder trading ecosystem.

Key Features:
    - ib_async integration for IB Gateway 10.37+ compatibility
    - Comprehensive metrics collection for all 9 client connections
    - System performance monitoring (CPU, memory, network)
    - Trading metrics (orders, positions, P&L)
    - Market data metrics (latency, throughput, errors)
    - Prometheus HTTP endpoint on port 9090
    - Real-time dashboard integration

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - prometheus_client: Metrics collection and exposition
    - psutil: System resource monitoring
    - asyncio: Asynchronous operations support

"""

import asyncio
import json
import logging
import threading
# ==============================================================================
# IMPORTS
# ==============================================================================
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import psutil
# Prometheus client
from prometheus_client import (REGISTRY, CollectorRegistry, Counter, Gauge,
                            Histogram, Info, Summary, generate_latest,
                            start_http_server)

# IB API - ib_async integration
try:
    from ib_async import IB, util

    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("⚠️ ib_async not available")

# Local imports
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Client Configuration
PROMETHEUS_CLIENT_ID = 9  # Dedicated client ID for metrics
METRICS_PORT = 9090  # Prometheus scrape port
UPDATE_INTERVAL = 10  # Metrics update interval (seconds)

# Metric Namespaces
NAMESPACE = "spyder"
SUBSYSTEM_GATEWAY = "gateway"
SUBSYSTEM_TRADING = "trading"
SUBSYSTEM_SYSTEM = "system"
SUBSYSTEM_MARKET = "market"

# ==============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ==============================================================================

# System Information
system_info = Info("spyder_system_info", "System information", namespace=NAMESPACE)

# ==============================================================================
# GATEWAY METRICS
# ==============================================================================

# Connection Metrics
gateway_connected = Gauge(
    "gateway_connected",
    "IB Gateway connection status by client",
    ["client_id", "purpose"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

gateway_uptime = Gauge(
    "gateway_uptime_seconds",
    "Gateway uptime in seconds",
    ["client_id"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

gateway_latency = Histogram(
    "gateway_latency_seconds",
    "Gateway API latency by operation",
    ["client_id", "operation"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

gateway_errors = Counter(
    "gateway_errors_total",
    "Total gateway errors by client and type",
    ["client_id", "error_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

gateway_reconnections = Counter(
    "gateway_reconnections_total",
    "Total gateway reconnections by client",
    ["client_id"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

gateway_messages = Counter(
    "gateway_messages_total",
    "Total messages processed by client",
    ["client_id", "message_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

gateway_rate_limit = Gauge(
    "gateway_rate_limit_usage",
    "Gateway rate limit usage percentage",
    ["client_id"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
)

# ==============================================================================
# TRADING METRICS
# ==============================================================================

# Order Metrics
orders_submitted = Counter(
    "orders_submitted_total",
    "Total orders submitted",
    ["symbol", "order_type", "action"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

orders_filled = Counter(
    "orders_filled_total",
    "Total orders filled",
    ["symbol", "order_type", "action"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

orders_rejected = Counter(
    "orders_rejected_total",
    "Total orders rejected",
    ["symbol", "reason"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

order_latency = Histogram(
    "order_latency_seconds",
    "Order execution latency",
    ["operation"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Position Metrics
position_count = Gauge(
    "position_count",
    "Number of open positions",
    ["symbol"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

position_value = Gauge(
    "position_value_usd",
    "Position market value in USD",
    ["symbol"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

unrealized_pnl = Gauge(
    "unrealized_pnl_usd",
    "Unrealized P&L in USD",
    ["symbol"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

realized_pnl = Counter(
    "realized_pnl_usd",
    "Realized P&L in USD",
    ["symbol"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
)

# ==============================================================================
# MARKET DATA METRICS
# ==============================================================================

# Market Data Feed Metrics
market_data_subscriptions = Gauge(
    "market_data_subscriptions",
    "Number of active market data subscriptions",
    ["client_id", "data_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET,
)

market_data_updates = Counter(
    "market_data_updates_total",
    "Total market data updates received",
    ["symbol", "data_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET,
)

market_data_latency = Histogram(
    "market_data_latency_seconds",
    "Market data latency",
    ["data_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET,
    buckets=[0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)

market_data_gaps = Counter(
    "market_data_gaps_total",
    "Market data gaps detected",
    ["symbol", "data_type"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET,
)

# ==============================================================================
# SYSTEM METRICS
# ==============================================================================

# System Resource Metrics
system_cpu_usage = Gauge(
    "system_cpu_usage_percent",
    "System CPU usage percentage",
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

system_memory_usage = Gauge(
    "system_memory_usage_percent",
    "System memory usage percentage",
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

system_disk_usage = Gauge(
    "system_disk_usage_percent",
    "System disk usage percentage",
    ["mount_point"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

system_network_bytes = Counter(
    "system_network_bytes_total",
    "System network bytes",
    ["interface", "direction"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

# Process Metrics
process_cpu_usage = Gauge(
    "process_cpu_usage_percent",
    "Process CPU usage percentage",
    ["process"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

process_memory_usage = Gauge(
    "process_memory_usage_bytes",
    "Process memory usage in bytes",
    ["process"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

process_file_descriptors = Gauge(
    "process_file_descriptors",
    "Number of open file descriptors",
    ["process"],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM,
)

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""
    client_id: int = PROMETHEUS_CLIENT_ID
    port: int = METRICS_PORT
    update_interval: int = UPDATE_INTERVAL
    enable_system_metrics: bool = True
    enable_trading_metrics: bool = True
    enable_market_metrics: bool = True
    enable_gateway_metrics: bool = True

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

# ==============================================================================
# PROMETHEUS METRICS COLLECTOR
# ==============================================================================

class PrometheusMetricsCollector:
    """
    Collects and exposes metrics for Prometheus monitoring using ib_async.
    
    This class provides comprehensive monitoring of the Spyder trading system
    including IB Gateway connections, trading performance, system resources,
    and market data feed health.
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """Initialize metrics collector with ib_async integration"""
        self.config = config or MetricsConfig()
        
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger("PrometheusMetrics")
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger("PrometheusMetrics")
            self.error_handler = None
        
        # IB Connection for metrics using ib_async
        self.ib_client: Optional[IB] = None
        self.connected = False
        
        # Client metrics storage
        self.client_metrics: Dict[int, ClientMetrics] = {}
        self._initialize_client_metrics()
        
        # Threading
        self.stop_event = threading.Event()
        self.update_thread: Optional[threading.Thread] = None
        self.server_started = False
        
        # Statistics
        self.start_time = datetime.now()
        self.total_updates = 0
        
        # Callbacks for external data
        self.metrics_callbacks: Dict[str, Callable] = {}
        
        self.logger.info(f"✅ PrometheusMetricsCollector initialized with ib_async (Client {self.config.client_id})")
    
    def _initialize_client_metrics(self):
        """Initialize metrics for all clients"""
        client_purposes = {
            0: "Administrative",
            1: "Order Execution", 
            2: "Core Market Data",
            3: "SPY Options",
            4: "Volatility",
            5: "Market Internals",
            6: "Major Indices",
            7: "Extended Assets",
            8: "Sector ETFs",
            9: "Prometheus Metrics"
        }
        
        for client_id, purpose in client_purposes.items():
            self.client_metrics[client_id] = ClientMetrics(
                client_id=client_id,
                purpose=purpose
            )
        
        self.logger.info(f"Initialized metrics for {len(client_purposes)} clients")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    async def connect(self):
        """Connect to IB Gateway for metrics collection using ib_async"""
        if not IB_AVAILABLE:
            self.logger.warning("ib_async not available - metrics collection limited")
            return False
        
        try:
            self.ib_client = IB()
            
            # Connect to gateway
            await self.ib_client.connectAsync(
                host='127.0.0.1',
                port=4002,  # TWS/Gateway port
                clientId=self.config.client_id,
                timeout=10
            )
            
            self.connected = True
            self.logger.info(f"✅ Connected to IB Gateway (Client {self.config.client_id})")
            
            # Set up event handlers
            self.ib_client.errorEvent += self._on_error
            self.ib_client.disconnectedEvent += self._on_disconnected
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to IB Gateway: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib_client and self.connected:
            try:
                self.ib_client.disconnect()
                self.connected = False
                self.logger.info("Disconnected from IB Gateway")
            except Exception as e:
                self.logger.error(f"Error disconnecting: {e}")
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB errors for metrics"""
        self.logger.debug(f"IB Error: {errorCode} - {errorString}")
        
        # Update error metrics
        gateway_errors.labels(
            client_id=str(self.config.client_id),
            error_type=str(errorCode)
        ).inc()
    
    def _on_disconnected(self):
        """Handle disconnection events"""
        self.connected = False
        self.logger.warning("IB Gateway disconnected")
        
        # Update reconnection metrics
        gateway_reconnections.labels(
            client_id=str(self.config.client_id)
        ).inc()
    
    # ==========================================================================
    # METRICS COLLECTION
    # ==========================================================================
    
    def _update_system_metrics(self):
        """Update system resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            system_memory_usage.set(memory.percent)
            
            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    disk_usage = psutil.disk_usage(partition.mountpoint)
                    usage_percent = (disk_usage.used / disk_usage.total) * 100
                    system_disk_usage.labels(mount_point=partition.mountpoint).set(usage_percent)
                except PermissionError:
                    continue
            
            # Network statistics
            network = psutil.net_io_counters(pernic=True)
            for interface, stats in network.items():
                system_network_bytes.labels(interface=interface, direction="sent").inc(stats.bytes_sent)
                system_network_bytes.labels(interface=interface, direction="recv").inc(stats.bytes_recv)
            
            # Process metrics
            current_process = psutil.Process()
            process_cpu_usage.labels(process="spyder_metrics").set(current_process.cpu_percent())
            process_memory_usage.labels(process="spyder_metrics").set(current_process.memory_info().rss)
            process_file_descriptors.labels(process="spyder_metrics").set(current_process.num_fds())
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def _update_gateway_metrics(self):
        """Update IB Gateway connection metrics"""
        try:
            for client_id, metrics in self.client_metrics.items():
                # Connection status
                gateway_connected.labels(
                    client_id=str(client_id),
                    purpose=metrics.purpose
                ).set(1 if metrics.connected else 0)
                
                # Uptime
                if metrics.connected:
                    gateway_uptime.labels(client_id=str(client_id)).set(metrics.uptime_seconds)
                
                # Rate limit usage
                gateway_rate_limit.labels(client_id=str(client_id)).set(metrics.rate_limit_usage)
                
        except Exception as e:
            self.logger.error(f"Error updating gateway metrics: {e}")
    
    def _update_trading_metrics(self):
        """Update trading performance metrics"""
        try:
            # This would typically get data from position tracker, order manager, etc.
            # For now, we'll use placeholder logic
            
            if self.ib_client and self.connected:
                # Get positions (example)
                positions = self.ib_client.positions()
                for position in positions:
                    symbol = position.contract.symbol
                    position_count.labels(symbol=symbol).set(abs(position.position))
                    position_value.labels(symbol=symbol).set(position.marketValue or 0)
                    unrealized_pnl.labels(symbol=symbol).set(position.unrealizedPNL or 0)
            
        except Exception as e:
            self.logger.error(f"Error updating trading metrics: {e}")
    
    def _update_market_data_metrics(self):
        """Update market data feed metrics"""
        try:
            # Market data subscriptions and latency would be tracked here
            # This would integrate with the market data managers
            pass
            
        except Exception as e:
            self.logger.error(f"Error updating market data metrics: {e}")
    
    def _update_custom_metrics(self):
        """Update custom metrics from registered callbacks"""
        try:
            for name, callback in self.metrics_callbacks.items():
                try:
                    callback()
                except Exception as e:
                    self.logger.error(f"Error in callback {name}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error updating custom metrics: {e}")
    
    def _update_all_metrics(self):
        """Update all metrics categories"""
        try:
            if self.config.enable_system_metrics:
                self._update_system_metrics()
            
            if self.config.enable_gateway_metrics:
                self._update_gateway_metrics()
            
            if self.config.enable_trading_metrics:
                self._update_trading_metrics()
            
            if self.config.enable_market_metrics:
                self._update_market_data_metrics()
            
            self._update_custom_metrics()
            
            self.total_updates += 1
            
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
    
    # ==========================================================================
    # UPDATE LOOP
    # ==========================================================================
    
    def _update_loop(self):
        """Main metrics update loop"""
        self.logger.info("Starting metrics update loop")
        
        while not self.stop_event.is_set():
            try:
                start_time = time.time()
                
                # Update all metrics
                self._update_all_metrics()
                
                # Calculate update duration
                update_duration = time.time() - start_time
                self.logger.debug(f"Metrics update took {update_duration:.3f}s")
                
                # Wait for next update
                self.stop_event.wait(self.config.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
                time.sleep(5)
        
        self.logger.info("Metrics update loop stopped")
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def start(self):
        """Start the metrics collector"""
        self.logger.info("🚀 Starting Prometheus metrics collector with ib_async")
        
        # Start HTTP server if not already started
        if not self.server_started:
            start_http_server(self.config.port)
            self.server_started = True
            self.logger.info(f"📊 Prometheus metrics server started on port {self.config.port}")
            self.logger.info(f"📈 Metrics available at http://localhost:{self.config.port}/metrics")
        
        # Initialize system info metric
        system_info.info({
            'version': '1.0',
            'ib_api': 'ib_async',
            'start_time': self.start_time.isoformat(),
            'client_id': str(self.config.client_id)
        })
        
        # Start update thread
        self.update_thread = threading.Thread(
            target=self._update_loop, name="MetricsUpdater", daemon=True
        )
        self.update_thread.start()
        
        self.logger.info("✅ Metrics collector started with ib_async integration")
    
    def stop(self):
        """Stop the metrics collector"""
        self.logger.info("Stopping metrics collector...")
        
        # Signal thread to stop
        self.stop_event.set()
        
        # Wait for thread
        if self.update_thread:
            self.update_thread.join(timeout=5)
        
        # Disconnect
        self.disconnect()
        
        self.logger.info("✅ Metrics collector stopped")
    
    def register_callback(self, name: str, callback: Callable):
        """Register a callback for external data"""
        self.metrics_callbacks[name] = callback
        self.logger.info(f"Registered metrics callback: {name}")
    
    def update_client_metrics(self, client_id: int, **kwargs):
        """Update metrics for a specific client"""
        if client_id in self.client_metrics:
            metrics = self.client_metrics[client_id]
            for key, value in kwargs.items():
                if hasattr(metrics, key):
                    setattr(metrics, key, value)
    
    def record_gateway_latency(self, client_id: int, operation: str, latency_ms: float):
        """Record gateway latency measurement"""
        gateway_latency.labels(client_id=str(client_id), operation=operation).observe(latency_ms / 1000.0)
    
    def record_order_latency(self, operation: str, latency_ms: float):
        """Record order execution latency"""
        order_latency.labels(operation=operation).observe(latency_ms / 1000.0)
    
    def record_market_data_update(self, symbol: str, data_type: str, latency_ms: float = None):
        """Record market data update"""
        market_data_updates.labels(symbol=symbol, data_type=data_type).inc()
        
        if latency_ms is not None:
            market_data_latency.labels(data_type=data_type).observe(latency_ms / 1000.0)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics"""
        return {
            'connected': self.connected,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'total_updates': self.total_updates,
            'active_clients': sum(1 for m in self.client_metrics.values() if m.connected),
            'server_port': self.config.port,
            'ib_api': 'ib_async'
        }

# ==============================================================================
# STANDALONE EXECUTION
# ==============================================================================

async def main():
    """Main function for standalone execution"""
    config = MetricsConfig()
    collector = PrometheusMetricsCollector(config)
    
    try:
        # Start metrics collection
        collector.start()
        
        # Try to connect to IB Gateway
        await collector.connect()
        
        print(f"✅ Prometheus metrics collector running on port {config.port}")
        print(f"📈 Metrics endpoint: http://localhost:{config.port}/metrics")
        print("Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping metrics collector...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        collector.stop()

if __name__ == "__main__":
    # Run standalone metrics collector
    asyncio.run(main())