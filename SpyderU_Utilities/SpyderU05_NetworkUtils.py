#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU05_NetworkUtils.py
Group: U (Utilities)
Purpose: Network connectivity checks

Description:
    This module provides network connectivity utilities for the trading system.
    It monitors internet connectivity, checks broker API endpoints, performs
    latency measurements, and handles network-related issues. The module ensures
    reliable communication with external services and provides failover mechanisms.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import socket
import time
import threading
import subprocess
import platform
import statistics
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Type
from dataclasses import dataclass
from enum import Enum, auto
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
import psutil
import netifaces
import aiohttp

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connectivity check endpoints
class NetworkStatus(Enum):
    """Network connection status"""
    CONNECTED = "connected"
CONNECTIVITY_CHECK_ENDPOINTS = ['https://8.8.8.8', 'https://1.1.1.1']
DISCONNECTED = "disconnected"
DEGRADED = "degraded"
UNKNOWN = "unknown"

class ConnectionType(Enum):
    """Types of connections to check"""
    INTERNET = auto()
IB_GATEWAY = auto()
MARKET_DATA = auto()
DATABASE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class NetworkMetrics:
    """Network performance metrics"""
    status: NetworkStatus
    latency_ms: float
    packet_loss: float
    bandwidth_mbps: Optional[float] = None
    jitter_ms: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class ConnectionInfo:
    """Connection information"""
    name: str
    host: str
    port: Optional[int]
    status: NetworkStatus
    latency_ms: Optional[float]
    last_check: datetime
    error_message: Optional[str] = None

# ==============================================================================
# NETWORK UTILITIES CLASS
# ==============================================================================
class NetworkUtils:
    """
    Network connectivity and monitoring utilities.
    
    Features:
    - Internet connectivity checks
    - IB Gateway connection monitoring
    - Latency measurements
    - Bandwidth estimation
    - Network interface information
    - Automatic reconnection handling
    """
    
    def __init__(self):
        """Initialize network utilities"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Connection states
        self._connection_states: Dict[ConnectionType, NetworkStatus] = {
            ConnectionType.INTERNET: NetworkStatus.UNKNOWN,
            ConnectionType.IB_GATEWAY: NetworkStatus.UNKNOWN,
            ConnectionType.MARKET_DATA: NetworkStatus.UNKNOWN,
            ConnectionType.DATABASE: NetworkStatus.UNKNOWN
        }
        
        # Metrics history
        self._metrics_history: List[NetworkMetrics] = []
        self._max_history = 100
        
        # Callbacks
        self._status_callbacks: Dict[ConnectionType, List[Callable]] = {}
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
        self._monitor_lock = threading.Lock()
        
        self.logger.info("NetworkUtils initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CONNECTIVITY CHECKS
    # ==========================================================================
    def check_internet_connectivity(self) -> bool:
        """
        Check internet connectivity.
        
        Returns:
            True if connected, False otherwise
        """
        for name, host, port in CONNECTIVITY_ENDPOINTS:
            try:
                # Try socket connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECTION_TIMEOUT)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    self._update_status(ConnectionType.INTERNET, NetworkStatus.CONNECTED)
                    return True
                    
            except Exception as e:
                self.logger.debug(f"Connection to {name} failed: {str(e)}")
        
        self._update_status(ConnectionType.INTERNET, NetworkStatus.DISCONNECTED)
        return False
    
    def check_ib_gateway(self, paper_trading: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Check IB Gateway/TWS connection.
        
        Args:
            paper_trading: Check paper trading port
            
        Returns:
            Tuple of (is_connected, error_message)
        """
        port = IB_GATEWAY_PORTS['paper' if paper_trading else 'live']
        
        for host in IB_GATEWAY_HOSTS:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECTION_TIMEOUT)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    self._update_status(ConnectionType.IB_GATEWAY, NetworkStatus.CONNECTED)
                    self.logger.info(f"IB Gateway connected at {host}:{port}")
                    return True, None
                    
            except Exception as e:
                error_msg = f"IB Gateway connection failed: {str(e)}"
                self.logger.error(error_msg)
        
        self._update_status(ConnectionType.IB_GATEWAY, NetworkStatus.DISCONNECTED)
        return False, f"Cannot connect to IB Gateway on port {port}"
    
    def check_market_data_feeds(self) -> Dict[str, bool]:
        """
        Check market data feed availability.
        
        Returns:
            Dictionary of endpoint: availability
        """
        results = {}
        
        for endpoint in MARKET_DATA_ENDPOINTS:
            try:
                response = requests.get(endpoint, timeout=HTTP_TIMEOUT)
                results[endpoint] = response.status_code == 200
            except Exception as e:
                self.logger.debug(f"Market data check failed for {endpoint}: {str(e)}")
                results[endpoint] = False
        
        # Update overall market data status
        if any(results.values()):
            self._update_status(ConnectionType.MARKET_DATA, NetworkStatus.CONNECTED)
        else:
            self._update_status(ConnectionType.MARKET_DATA, NetworkStatus.DISCONNECTED)
        
        return results
    
    # ==========================================================================
    # PUBLIC METHODS - LATENCY MEASUREMENT
    # ==========================================================================
    def measure_latency(self, host: str, port: Optional[int] = None,
                       samples: int = 100) -> Optional[float]:
        """
        Measure latency to a host.
        
        Args:
            host: Target host
            port: Target port (None for ICMP ping)
            samples: Number of samples
            
        Returns:
            Average latency in milliseconds or None
        """
        if port:
            return self._measure_tcp_latency(host, port, samples)
        else:
            return self._measure_icmp_latency(host, samples)
    
    def _measure_tcp_latency(self, host: str, port: int, samples: int) -> Optional[float]:
        """Measure TCP connection latency"""
        latencies = []
        
        for _ in range(samples):
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECTION_TIMEOUT)
                result = sock.connect_ex((host, port))
                end = time.time()
                sock.close()
                
                if result == 0:
                    latency_ms = (end - start) * 1000
                    latencies.append(latency_ms)
                
                time.sleep(0.1)  # Small delay between samples
                
            except Exception as e:
                self.logger.debug(f"TCP latency measurement failed: {str(e)}")
        
        if latencies:
            return statistics.mean(latencies)
        return None
    
    def _measure_icmp_latency(self, host: str, samples: int) -> Optional[float]:
        """Measure ICMP ping latency"""
        system = platform.system().lower()
        
        if system == 'windows':
            cmd = ['ping', '-n', str(samples), host]
        else:
            cmd = ['ping', '-c', str(samples), '-W', str(PING_TIMEOUT), host]
        
        try:
            output = subprocess.check_output(cmd, universal_newlines=True)
            
            # Parse ping output
            if system == 'windows':
                # Windows: "Average = XXms"
                import re
                match = re.search(r'Average = (\d+)ms', output)
                if match:
                    return float(match.group(1))
            else:
                # Unix: "rtt min/avg/max/mdev = X.X/X.X/X.X/X.X ms"
                import re
                match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/', output)
                if match:
                    return float(match.group(1))
                    
        except subprocess.CalledProcessError:
            self.logger.debug(f"ICMP ping to {host} failed")
        except Exception as e:
            self.logger.error(f"Ping measurement error: {str(e)}")
        
        return None
    
    # ==========================================================================
    # PUBLIC METHODS - NETWORK METRICS
    # ==========================================================================
    def get_network_metrics(self) -> NetworkMetrics:
        """
        Get comprehensive network metrics.
        
        Returns:
            NetworkMetrics object
        """
        # Check connectivity
        internet_connected = self.check_internet_connectivity()
        
        # Measure latency to Google DNS
        latency = self.measure_latency('8.8.8.8', 53, samples=5) or 0.0
        
        # Estimate packet loss (simplified)
        packet_loss = 0.0 if internet_connected else 100.0
        
        # Get bandwidth (if possible)
        bandwidth = self._estimate_bandwidth()
        
        # Calculate jitter from recent latencies
        jitter = self._calculate_jitter()
        
        # Determine overall status
        if not internet_connected:
            status = NetworkStatus.DISCONNECTED
        elif latency > 100 or packet_loss > 5:
            status = NetworkStatus.DEGRADED
        else:
            status = NetworkStatus.CONNECTED
        
        metrics = NetworkMetrics(
            status=status,
            latency_ms=latency,
            packet_loss=packet_loss,
            bandwidth_mbps=bandwidth,
            jitter_ms=jitter
        )
        
        # Store in history
        with self._monitor_lock:
            self._metrics_history.append(metrics)
            if len(self._metrics_history) > self._max_history:
                self._metrics_history.pop(0)
        
        return metrics
    
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """
        Get network interface information.
        
        Returns:
            List of interface information dictionaries
        """
        interfaces = []
        
        for interface, addrs in netifaces.interfaces():
            info = {
                'name': interface,
                'addresses': {}
            }
            
            # Get addresses
            iface_addrs = netifaces.ifaddresses(interface)
            
            # IPv4
            if netifaces.AF_INET in iface_addrs:
                ipv4 = iface_addrs[netifaces.AF_INET][0]
                info['addresses']['ipv4'] = ipv4.get('addr')
                info['addresses']['netmask'] = ipv4.get('netmask')
            
            # IPv6
            if netifaces.AF_INET6 in iface_addrs:
                ipv6 = iface_addrs[netifaces.AF_INET6][0]
                info['addresses']['ipv6'] = ipv6.get('addr')
            
            # MAC address
            if netifaces.AF_LINK in iface_addrs:
                mac = iface_addrs[netifaces.AF_LINK][0]
                info['addresses']['mac'] = mac.get('addr')
            
            # Get stats from psutil
            stats = psutil.net_io_counters(pernic=True).get(interface)
            if stats:
                info['stats'] = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv,
                    'errors_in': stats.errin,
                    'errors_out': stats.errout
                }
            
            interfaces.append(info)
        
        return interfaces
    
    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def start_monitoring(self, interval: int = 30) -> None:
        """
        Start network monitoring.
        
        Args:
            interval: Check interval in seconds
        """
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
            name="NetworkMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info(f"Network monitoring started (interval: {interval}s)")
    
    def stop_monitoring(self) -> None:
        """Stop network monitoring"""
        self._monitoring = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Network monitoring stopped")
    
    def register_status_callback(self, connection_type: ConnectionType,
                               callback: Callable[[NetworkStatus], None]) -> None:
        """
        Register callback for connection status changes.
        
        Args:
            connection_type: Type of connection
            callback: Callback function
        """
        if connection_type not in self._status_callbacks:
            self._status_callbacks[connection_type] = []
        
        self._status_callbacks[connection_type].append(callback)
    
    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """
        Resolve hostname to IP address.
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            IP address or None
        """
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            self.logger.error(f"Failed to resolve hostname: {hostname}")
            return None
    
    def is_port_open(self, host: str, port: int) -> bool:
        """
        Check if a port is open.
        
        Args:
            host: Target host
            port: Target port
            
        Returns:
            True if port is open
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECTION_TIMEOUT)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    async def check_http_endpoint_async(self, url: str) -> Tuple[bool, Optional[int]]:
        """
        Asynchronously check HTTP endpoint.
        
        Args:
            url: Endpoint URL
            
        Returns:
            Tuple of (is_available, status_code)
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=HTTP_TIMEOUT) as response:
                    return response.status == 200, response.status
        except Exception as e:
            self.logger.debug(f"Async HTTP check failed for {url}: {str(e)}")
            return False, None
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _monitor_loop(self, interval: int) -> None:
        """Network monitoring loop"""
        while self._monitoring:
            try:
                # Check all connection types
                self.check_internet_connectivity()
                
                # Get network metrics
                metrics = self.get_network_metrics()
                
                # Log if degraded
                if metrics.status == NetworkStatus.DEGRADED:
                    self.logger.warning(
                        f"Network degraded - Latency: {metrics.latency_ms:.1f}ms, "
                        f"Packet loss: {metrics.packet_loss:.1f}%"
                    )
                
                # Sleep
                time.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {str(e)}")
                time.sleep(interval)
    
    def _update_status(self, connection_type: ConnectionType,
                      status: NetworkStatus) -> None:
        """Update connection status and trigger callbacks"""
        old_status = self._connection_states.get(connection_type)
        
        if old_status != status:
            self._connection_states[connection_type] = status
            
            # Trigger callbacks
            for callback in self._status_callbacks.get(connection_type, []):
                try:
                    callback(status)
                except Exception as e:
                    self.logger.error(f"Status callback error: {str(e)}")
    
    def _estimate_bandwidth(self) -> Optional[float]:
        """Estimate network bandwidth (simplified)"""
        # This is a placeholder - actual implementation would
        # perform a bandwidth test
        try:
            stats = psutil.net_io_counters()
            # Very rough estimate based on current usage
            return None  # Would need actual measurement
        except Exception:
            return None
    
    def _calculate_jitter(self) -> Optional[float]:
        """Calculate network jitter from recent latencies"""
        if len(self._metrics_history) < 2:
            return None
        
        recent_latencies = [m.latency_ms for m in self._metrics_history[-10:]]
        
        if len(recent_latencies) < 2:
            return None
        
        # Calculate differences between consecutive latencies
        differences = []
        for i in range(1, len(recent_latencies)):
            diff = abs(recent_latencies[i] - recent_latencies[i-1])
            differences.append(diff)
        
        return statistics.mean(differences) if differences else None

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_network_utils: Optional[NetworkUtils] = None

def get_network_utils() -> NetworkUtils:
    """
    Get singleton instance of network utilities.
    
    Returns:
        NetworkUtils instance
    """
    global _network_utils
    if _network_utils is None:
        _network_utils = NetworkUtils()
    return _network_utils

def wait_for_connection(connection_type: ConnectionType = ConnectionType.INTERNET,
                       timeout: int = 60, check_interval: int = 5) -> bool:
    """
    Wait for network connection.
    
    Args:
        connection_type: Type of connection to wait for
        timeout: Maximum wait time in seconds
        check_interval: Check interval in seconds
        
    Returns:
        True if connected within timeout
    """
    utils = get_network_utils()
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if connection_type == ConnectionType.INTERNET:
            if utils.check_internet_connectivity():
                return True
        elif connection_type == ConnectionType.IB_GATEWAY:
            connected, _ = utils.check_ib_gateway()
            if connected:
                return True
        
        time.sleep(check_interval)
    
    return False

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test network utilities
    utils = get_network_utils()
    
    print("Testing Network Utilities...")
    
    # Check internet
    print(f"\nInternet connected: {utils.check_internet_connectivity()}")
    
    # Check IB Gateway
    connected, error = utils.check_ib_gateway(paper_trading=True)
    print(f"IB Gateway connected: {connected}")
    if error:
        print(f"  Error: {error}")
    
    # Get network metrics
    metrics = utils.get_network_metrics()
    print(f"\nNetwork Metrics:")
    print(f"  Status: {metrics.status.value}")
    print(f"  Latency: {metrics.latency_ms:.1f} ms")
    print(f"  Packet Loss: {metrics.packet_loss:.1f}%")
    
    # List interfaces
    print(f"\nNetwork Interfaces:")
    for iface in utils.get_network_interfaces():
        print(f"  {iface['name']}: {iface['addresses'].get('ipv4', 'No IPv4')}")
    
    # Test port
    print(f"\nPort 80 open on google.com: {utils.is_port_open('google.com', 80)}")
    
    # Start monitoring
    utils.start_monitoring(interval=10)
    
    # Wait a bit
    time.sleep(30)
    
    # Stop monitoring
    utils.stop_monitoring()