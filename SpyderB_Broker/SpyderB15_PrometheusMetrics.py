#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB15_PrometheusMetrics.py
Group: B (Broker/Connection)
Purpose: Prometheus metrics collection and monitoring (Client ID 9)
Author: Mohamed Talib
Date Created: 2025-08-06
Last Updated: 2025-08-06 Time: 13:30:00

Description:
    Dedicated Prometheus metrics collection using Client ID 9. This module
    collects comprehensive metrics from all system components and exposes
    them for Prometheus scraping. It monitors connection health, trading
    performance, system resources, and provides alerting capabilities.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import time
import threading
import logging
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import asyncio

# Prometheus client
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    start_http_server, generate_latest,
    CollectorRegistry, REGISTRY
)

# IB API
try:
    from ib_insync import IB, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("⚠️ ib_insync not available")

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
METRICS_PORT = 9090       # Prometheus scrape port
UPDATE_INTERVAL = 10      # Metrics update interval (seconds)

# Metric Namespaces
NAMESPACE = 'spyder'
SUBSYSTEM_GATEWAY = 'gateway'
SUBSYSTEM_TRADING = 'trading'
SUBSYSTEM_SYSTEM = 'system'
SUBSYSTEM_MARKET = 'market'

# ==============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ==============================================================================

# System Information
system_info = Info(
    'spyder_system_info',
    'System information',
    namespace=NAMESPACE
)

# ==============================================================================
# GATEWAY METRICS
# ==============================================================================

# Connection Metrics
gateway_connected = Gauge(
    'gateway_connected',
    'IB Gateway connection status by client',
    ['client_id', 'purpose'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

gateway_uptime = Gauge(
    'gateway_uptime_seconds',
    'Gateway uptime in seconds',
    ['client_id'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

gateway_latency = Histogram(
    'gateway_latency_milliseconds',
    'Gateway latency in milliseconds',
    ['client_id', 'operation'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY,
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)

gateway_reconnections = Counter(
    'gateway_reconnections_total',
    'Total number of reconnections',
    ['client_id'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

gateway_errors = Counter(
    'gateway_errors_total',
    'Total gateway errors',
    ['client_id', 'error_type'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

# Rate Limiting Metrics
rate_limit_usage = Gauge(
    'rate_limit_usage_percent',
    'Rate limit usage percentage',
    ['client_id'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

rate_limit_violations = Counter(
    'rate_limit_violations_total',
    'Total rate limit violations',
    ['client_id'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_GATEWAY
)

# ==============================================================================
# TRADING METRICS
# ==============================================================================

# Order Metrics
orders_submitted = Counter(
    'orders_submitted_total',
    'Total orders submitted',
    ['symbol', 'order_type', 'side'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

orders_filled = Counter(
    'orders_filled_total',
    'Total orders filled',
    ['symbol', 'order_type', 'side'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

orders_cancelled = Counter(
    'orders_cancelled_total',
    'Total orders cancelled',
    ['symbol', 'reason'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

order_latency = Histogram(
    'order_latency_milliseconds',
    'Order execution latency',
    ['operation'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING,
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)

# Position Metrics
open_positions = Gauge(
    'open_positions',
    'Number of open positions',
    ['symbol', 'position_type'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

position_pnl = Gauge(
    'position_pnl_dollars',
    'Position P&L in dollars',
    ['symbol', 'position_type'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

total_pnl = Gauge(
    'total_pnl_dollars',
    'Total P&L in dollars',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

# Risk Metrics
portfolio_var = Gauge(
    'portfolio_var',
    'Portfolio Value at Risk',
    ['confidence_level'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

sharpe_ratio = Gauge(
    'sharpe_ratio',
    'Portfolio Sharpe ratio',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

max_drawdown = Gauge(
    'max_drawdown_percent',
    'Maximum drawdown percentage',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_TRADING
)

# ==============================================================================
# MARKET DATA METRICS
# ==============================================================================

market_data_updates = Counter(
    'market_data_updates_total',
    'Total market data updates received',
    ['symbol', 'data_type'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET
)

market_data_lag = Histogram(
    'market_data_lag_milliseconds',
    'Market data lag in milliseconds',
    ['symbol', 'data_type'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET,
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000]
)

bid_ask_spread = Gauge(
    'bid_ask_spread',
    'Current bid-ask spread',
    ['symbol'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_MARKET
)

# ==============================================================================
# SYSTEM METRICS
# ==============================================================================

system_cpu_usage = Gauge(
    'system_cpu_percent',
    'System CPU usage percentage',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
)

system_memory_usage = Gauge(
    'system_memory_percent',
    'System memory usage percentage',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
)

system_disk_usage = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage',
    ['mount_point'],
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
)

process_cpu_usage = Gauge(
    'process_cpu_percent',
    'Process CPU usage percentage',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
)

process_memory_usage = Gauge(
    'process_memory_mb',
    'Process memory usage in MB',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
)

process_threads = Gauge(
    'process_threads',
    'Number of process threads',
    namespace=NAMESPACE,
    subsystem=SUBSYSTEM_SYSTEM
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
    """Collects and exposes metrics for Prometheus monitoring"""
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """Initialize metrics collector"""
        self.config = config or MetricsConfig()
        
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger('PrometheusMetrics')
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger('PrometheusMetrics')
            self.error_handler = None
        
        # IB Connection for metrics
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
        
        self.logger.info(f"✅ PrometheusMetricsCollector initialized (Client {self.config.client_id})")
    
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
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    async def connect(self) -> bool:
        """Connect to IB Gateway using Client ID 9"""
        try:
            if not IB_AVAILABLE:
                self.logger.warning("IB API not available - running in simulation mode")
                self.connected = True
                return True
            
            self.logger.info(f"Connecting Prometheus client (ID: {self.config.client_id})...")
            
            self.ib_client = IB()
            
            # Connect with Client ID 9
            await self.ib_client.connectAsync(
                host='127.0.0.1',
                port=4002,  # Paper trading port
                clientId=self.config.client_id,
                timeout=30
            )
            
            if self.ib_client.isConnected():
                self.connected = True
                self.logger.info(f"✅ Prometheus client connected (ID: {self.config.client_id})")
                
                # Update system info
                system_info.info({
                    'version': '1.0',
                    'client_id': str(self.config.client_id),
                    'start_time': self.start_time.isoformat(),
                    'mode': 'production' if IB_AVAILABLE else 'simulation'
                })
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to connect Prometheus client: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.ib_client and IB_AVAILABLE:
            try:
                self.ib_client.disconnect()
            except:
                pass
        self.connected = False
        self.logger.info("Prometheus client disconnected")
    
    # ==========================================================================
    # METRICS COLLECTION
    # ==========================================================================
    
    def update_gateway_metrics(self):
        """Update gateway connection metrics"""
        try:
            for client_id, metrics in self.client_metrics.items():
                # Update connection status
                gateway_connected.labels(
                    client_id=str(client_id),
                    purpose=metrics.purpose
                ).set(1 if metrics.connected else 0)
                
                # Update uptime
                if metrics.connected:
                    gateway_uptime.labels(
                        client_id=str(client_id)
                    ).set(metrics.uptime_seconds)
                
                # Update rate limit usage
                rate_limit_usage.labels(
                    client_id=str(client_id)
                ).set(metrics.rate_limit_usage)
                
        except Exception as e:
            self.logger.error(f"Error updating gateway metrics: {e}")
    
    def update_system_metrics(self):
        """Update system resource metrics"""
        if not self.config.enable_system_metrics:
            return
        
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
                    usage = psutil.disk_usage(partition.mountpoint)
                    system_disk_usage.labels(
                        mount_point=partition.mountpoint
                    ).set(usage.percent)
                except:
                    pass
            
            # Process metrics
            process = psutil.Process()
            process_cpu_usage.set(process.cpu_percent(interval=0.1))
            process_memory_usage.set(process.memory_info().rss / 1024 / 1024)  # MB
            process_threads.set(process.num_threads())
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def update_trading_metrics(self, trading_data: Optional[Dict] = None):
        """Update trading-related metrics"""
        if not self.config.enable_trading_metrics:
            return
        
        try:
            if trading_data:
                # Update from provided data
                if 'total_pnl' in trading_data:
                    total_pnl.set(trading_data['total_pnl'])
                
                if 'positions' in trading_data:
                    for position in trading_data['positions']:
                        open_positions.labels(
                            symbol=position['symbol'],
                            position_type=position['type']
                        ).set(position['quantity'])
                        
                        if 'pnl' in position:
                            position_pnl.labels(
                                symbol=position['symbol'],
                                position_type=position['type']
                            ).set(position['pnl'])
                
                if 'risk_metrics' in trading_data:
                    risk = trading_data['risk_metrics']
                    if 'var' in risk:
                        portfolio_var.labels(confidence_level='95').set(risk['var'])
                    if 'sharpe' in risk:
                        sharpe_ratio.set(risk['sharpe'])
                    if 'max_drawdown' in risk:
                        max_drawdown.set(risk['max_drawdown'])
            
        except Exception as e:
            self.logger.error(f"Error updating trading metrics: {e}")
    
    def update_market_metrics(self, market_data: Optional[Dict] = None):
        """Update market data metrics"""
        if not self.config.enable_market_metrics:
            return
        
        try:
            if market_data:
                for symbol, data in market_data.items():
                    if 'bid' in data and 'ask' in data:
                        spread = data['ask'] - data['bid']
                        bid_ask_spread.labels(symbol=symbol).set(spread)
                    
                    if 'updates' in data:
                        market_data_updates.labels(
                            symbol=symbol,
                            data_type='quote'
                        ).inc(data['updates'])
            
        except Exception as e:
            self.logger.error(f"Error updating market metrics: {e}")
    
    # ==========================================================================
    # METRICS UPDATE LOOP
    # ==========================================================================
    
    def _update_loop(self):
        """Main metrics update loop"""
        self.logger.info("📊 Metrics update loop started")
        
        while not self.stop_event.is_set():
            try:
                # Update all metrics
                self.update_gateway_metrics()
                self.update_system_metrics()
                
                # Call external callbacks for additional data
                if 'trading' in self.metrics_callbacks:
                    trading_data = self.metrics_callbacks['trading']()
                    self.update_trading_metrics(trading_data)
                
                if 'market' in self.metrics_callbacks:
                    market_data = self.metrics_callbacks['market']()
                    self.update_market_metrics(market_data)
                
                self.total_updates += 1
                
                # Sleep
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
        self.logger.info("🚀 Starting Prometheus metrics collector")
        
        # Start HTTP server if not already started
        if not self.server_started:
            start_http_server(self.config.port)
            self.server_started = True
            self.logger.info(f"📊 Prometheus metrics server started on port {self.config.port}")
            self.logger.info(f"📈 Metrics available at http://localhost:{self.config.port}/metrics")
        
        # Start update thread
        self.update_thread = threading.Thread(
            target=self._update_loop,
            name="MetricsUpdater",
            daemon=True
        )
        self.update_thread.start()
        
        self.logger.info("✅ Metrics collector started")
    
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
        gateway_latency.labels(
            client_id=str(client_id),
            operation=operation
        ).observe(latency_ms)
    
    def record_order_latency(self, operation: str, latency_ms: float):
        """Record order execution latency"""
        order_latency.labels(operation=operation).observe(latency_ms)
    
    def increment_error(self, client_id: int, error_type: str):
        """Increment error counter"""
        gateway_errors.labels(
            client_id=str(client_id),
            error_type=error_type
        ).inc()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'uptime_hours': uptime / 3600,
            'total_updates': self.total_updates,
            'connected': self.connected,
            'client_id': self.config.client_id,
            'metrics_port': self.config.port,
            'metrics_url': f'http://localhost:{self.config.port}/metrics'
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_metrics_collector(config: Optional[MetricsConfig] = None) -> PrometheusMetricsCollector:
    """Create and configure metrics collector"""
    return PrometheusMetricsCollector(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("📊 PROMETHEUS METRICS COLLECTOR - CLIENT 9")
    print("=" * 80)
    
    # Create collector
    collector = create_metrics_collector()
    
    try:
        # Connect
        print(f"\n🔌 Connecting Client {PROMETHEUS_CLIENT_ID} for metrics...")
        asyncio.run(collector.connect())
        
        # Start collection
        print("\n📊 Starting metrics collection...")
        collector.start()
        
        # Display info
        summary = collector.get_metrics_summary()
        print("\n📈 Metrics Summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        print(f"\n✅ Metrics available at: {summary['metrics_url']}")
        print("\n📊 Sample metrics queries:")
        print("  - rate(spyder_gateway_errors_total[5m])")
        print("  - histogram_quantile(0.95, spyder_gateway_latency_milliseconds)")
        print("  - spyder_trading_total_pnl_dollars")
        print("  - spyder_system_cpu_percent")
        
        print("\n✨ Collector is running. Press Ctrl+C to stop...")
        
        # Keep running
        try:
            while True:
                time.sleep(30)
                # Print periodic status
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Updates: {collector.total_updates}, "
                      f"Connected: {collector.connected}")
        except KeyboardInterrupt:
            print("\n\n🛑 Shutdown requested...")
            
    finally:
        # Clean shutdown
        collector.stop()
        print("\n👋 Metrics collector stopped. Goodbye!")
