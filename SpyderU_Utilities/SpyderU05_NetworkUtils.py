#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU05_NetworkUtils.py
Group: U (Utilities)
Purpose: Network connectivity and communication utilities

Description:
    This module provides comprehensive network utilities for the Spyder trading
    system including internet connectivity checking, IB Gateway connection
    validation, latency measurement, and network health monitoring. It ensures
    reliable network communications for trading operations and provides
    diagnostics for connection issues.

Author: Mohamed Talib
Date Created: 2025-07-18
Last Updated: 2025-07-18 Time: 10:30:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import socket
import subprocess
import platform
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import requests
from urllib.parse import urlparse
import concurrent.futures

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import ping3
    PING3_AVAILABLE = True
except ImportError:
    PING3_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Network timeouts
DEFAULT_TIMEOUT = 10  # seconds
PING_TIMEOUT = 5      # seconds
CONNECTION_RETRIES = 3

# Test endpoints
INTERNET_TEST_HOSTS = [
    "8.8.8.8",           # Google DNS
    "1.1.1.1",           # Cloudflare DNS
    "208.67.222.222"     # OpenDNS
]

IB_ENDPOINTS = {
    "TWS": {"host": "127.0.0.1", "port": 7497},
    "GATEWAY": {"host": "127.0.0.1", "port": 4001},
    "PAPER": {"host": "127.0.0.1", "port": 7497}
}

# HTTP test URLs
HTTP_TEST_URLS = [
    "https://www.google.com",
    "https://www.interactivebrokers.com",
    "https://httpbin.org/get"
]

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionStatus(Enum):
    """Network connection status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SLOW = "slow"
    UNSTABLE = "unstable"
    UNKNOWN = "unknown"

class NetworkType(Enum):
    """Network connection type"""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    CELLULAR = "cellular"
    VPN = "vpn"
    UNKNOWN = "unknown"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class NetworkStats:
    """Network statistics data structure"""
    latency_ms: float
    packet_loss: float
    bandwidth_mbps: float
    connection_type: NetworkType
    status: ConnectionStatus
    timestamp: float

@dataclass
class ConnectionTest:
    """Connection test result"""
    host: str
    port: int
    success: bool
    latency_ms: float
    error_message: Optional[str] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class NetworkUtils:
    """
    Network utilities for connectivity and performance monitoring.
    
    This class provides comprehensive network utilities including internet
    connectivity checking, IB Gateway validation, latency measurement,
    and network health monitoring for the Spyder trading system.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        stats: Current network statistics
        
    Example:
        >>> net_utils = NetworkUtils()
        >>> if net_utils.check_internet_connection():
        ...     print("Internet connected")
        >>> latency = net_utils.measure_latency("8.8.8.8")
        >>> print(f"Latency: {latency}ms")
    """
    
    def __init__(self):
        """Initialize the network utilities."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.stats = NetworkStats(
            latency_ms=0.0,
            packet_loss=0.0,
            bandwidth_mbps=0.0,
            connection_type=NetworkType.UNKNOWN,
            status=ConnectionStatus.UNKNOWN,
            timestamp=time.time()
        )
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - CONNECTIVITY CHECKING
    # ==========================================================================
    def check_internet_connection(self, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """
        Check if internet connection is available.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if internet is available
            
        Example:
            >>> net_utils = NetworkUtils()
            >>> connected = net_utils.check_internet_connection()
            >>> print(f"Internet: {connected}")
        """
        try:
            # Test multiple hosts for reliability
            for host in INTERNET_TEST_HOSTS:
                if self._test_host_connection(host, 53, timeout):
                    self.logger.debug(f"Internet connection confirmed via {host}")
                    return True
            
            # Fallback to HTTP test
            return self._test_http_connection(timeout)
            
        except Exception as e:
            self.logger.error(f"Internet connection check failed: {e}")
            return False
    
    def check_ib_connection(self, connection_type: str = "GATEWAY") -> bool:
        """
        Check Interactive Brokers connection.
        
        Args:
            connection_type: Type of IB connection (TWS, GATEWAY, PAPER)
            
        Returns:
            bool: True if IB connection is available
        """
        try:
            if connection_type not in IB_ENDPOINTS:
                self.logger.error(f"Unknown IB connection type: {connection_type}")
                return False
            
            endpoint = IB_ENDPOINTS[connection_type]
            result = self._test_host_connection(
                endpoint["host"], 
                endpoint["port"], 
                DEFAULT_TIMEOUT
            )
            
            if result:
                self.logger.info(f"IB {connection_type} connection confirmed")
            else:
                self.logger.warning(f"IB {connection_type} connection failed")
            
            return result
            
        except Exception as e:
            self.logger.error(f"IB connection check failed: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - PERFORMANCE MEASUREMENT
    # ==========================================================================
    def measure_latency(self, host: str = "8.8.8.8", count: int = 3) -> float:
        """
        Measure network latency to a host.
        
        Args:
            host: Target host for latency measurement
            count: Number of ping attempts
            
        Returns:
            float: Average latency in milliseconds
        """
        try:
            latencies = []
            
            if PING3_AVAILABLE:
                # Use ping3 if available
                for _ in range(count):
                    try:
                        latency = ping3.ping(host, timeout=PING_TIMEOUT)
                        if latency is not None:
                            latencies.append(latency * 1000)  # Convert to ms
                    except Exception:
                        continue
            else:
                # Fallback to socket connection timing
                for _ in range(count):
                    try:
                        start_time = time.time()
                        socket.create_connection((host, 53), timeout=PING_TIMEOUT)
                        latency = (time.time() - start_time) * 1000
                        latencies.append(latency)
                    except Exception:
                        continue
            
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                self.logger.debug(f"Average latency to {host}: {avg_latency:.2f}ms")
                return round(avg_latency, 2)
            else:
                self.logger.warning(f"Could not measure latency to {host}")
                return -1.0
                
        except Exception as e:
            self.logger.error(f"Latency measurement failed: {e}")
            return -1.0
    
    def test_multiple_connections(self, endpoints: List[Tuple[str, int]]) -> List[ConnectionTest]:
        """
        Test multiple network endpoints concurrently.
        
        Args:
            endpoints: List of (host, port) tuples to test
            
        Returns:
            List of ConnectionTest results
        """
        results = []
        
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {
                    executor.submit(self._test_endpoint, host, port): (host, port)
                    for host, port in endpoints
                }
                
                for future in concurrent.futures.as_completed(futures):
                    host, port = futures[future]
                    try:
                        result = future.result(timeout=DEFAULT_TIMEOUT)
                        results.append(result)
                    except Exception as e:
                        results.append(ConnectionTest(
                            host=host,
                            port=port,
                            success=False,
                            latency_ms=-1.0,
                            error_message=str(e)
                        ))
            
            return results
            
        except Exception as e:
            self.logger.error(f"Multiple connection test failed: {e}")
            return []
    
    # ==========================================================================
    # PUBLIC METHODS - NETWORK MONITORING
    # ==========================================================================
    def get_network_status(self) -> Dict[str, Any]:
        """
        Get comprehensive network status.
        
        Returns:
            Dictionary with network status information
        """
        try:
            status = {
                "internet_connected": self.check_internet_connection(),
                "ib_gateway_connected": self.check_ib_connection("GATEWAY"),
                "latency_ms": self.measure_latency(),
                "timestamp": time.time(),
                "dns_resolution": self._test_dns_resolution(),
                "http_connectivity": self._test_http_connection()
            }
            
            # Update internal stats
            self.stats.latency_ms = status["latency_ms"]
            self.stats.timestamp = status["timestamp"]
            self.stats.status = (
                ConnectionStatus.CONNECTED if status["internet_connected"] 
                else ConnectionStatus.DISCONNECTED
            )
            
            return status
            
        except Exception as e:
            self.logger.error(f"Network status check failed: {e}")
            return {
                "internet_connected": False,
                "ib_gateway_connected": False,
                "latency_ms": -1.0,
                "timestamp": time.time(),
                "error": str(e)
            }
    
    def monitor_connection(self, interval: int = 30, callback=None) -> None:
        """
        Start continuous network monitoring.
        
        Args:
            interval: Monitoring interval in seconds
            callback: Optional callback function for status updates
        """
        def monitor_loop():
            while True:
                try:
                    status = self.get_network_status()
                    
                    if callback:
                        callback(status)
                    
                    # Log significant changes
                    if not status.get("internet_connected", False):
                        self.logger.warning("Internet connection lost")
                    elif not status.get("ib_gateway_connected", False):
                        self.logger.warning("IB Gateway connection lost")
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    self.logger.error(f"Network monitoring error: {e}")
                    time.sleep(interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        self.logger.info(f"Network monitoring started (interval: {interval}s)")
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _test_host_connection(self, host: str, port: int, timeout: int) -> bool:
        """Test connection to a specific host and port."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.error, socket.timeout):
            return False
    
    def _test_endpoint(self, host: str, port: int) -> ConnectionTest:
        """Test a single endpoint and return detailed results."""
        start_time = time.time()
        
        try:
            with socket.create_connection((host, port), timeout=DEFAULT_TIMEOUT):
                latency = (time.time() - start_time) * 1000
                return ConnectionTest(
                    host=host,
                    port=port,
                    success=True,
                    latency_ms=round(latency, 2)
                )
        except Exception as e:
            return ConnectionTest(
                host=host,
                port=port,
                success=False,
                latency_ms=-1.0,
                error_message=str(e)
            )
    
    def _test_dns_resolution(self) -> bool:
        """Test DNS resolution capability."""
        try:
            socket.gethostbyname("www.google.com")
            return True
        except socket.gaierror:
            return False
    
    def _test_http_connection(self, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Test HTTP connectivity."""
        try:
            for url in HTTP_TEST_URLS:
                try:
                    response = requests.get(url, timeout=timeout)
                    if response.status_code == 200:
                        return True
                except:
                    continue
            return False
        except Exception:
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def check_internet_connection(timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Quick check for internet connectivity.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        bool: True if internet is available
    """
    net_utils = NetworkUtils()
    return net_utils.check_internet_connection(timeout)

def check_connection(host: str, port: int, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """
    Check connection to specific host and port.
    
    Args:
        host: Target host
        port: Target port
        timeout: Connection timeout
        
    Returns:
        bool: True if connection successful
    """
    net_utils = NetworkUtils()
    return net_utils._test_host_connection(host, port, timeout)

def measure_latency(host: str = "8.8.8.8") -> float:
    """
    Measure latency to a host.
    
    Args:
        host: Target host
        
    Returns:
        float: Latency in milliseconds
    """
    net_utils = NetworkUtils()
    return net_utils.measure_latency(host)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_network_utils_instance: Optional[NetworkUtils] = None

def get_network_utils() -> NetworkUtils:
    """
    Get singleton instance of network utilities.
    
    Returns:
        NetworkUtils instance
    """
    global _network_utils_instance
    if _network_utils_instance is None:
        _network_utils_instance = NetworkUtils()
    return _network_utils_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER U05 - Network Utils Test")
    print("=" * 80)
    
    net_utils = NetworkUtils()
    
    # Test internet connection
    print("\n1. Testing internet connection...")
    internet_ok = net_utils.check_internet_connection()
    print(f"   Internet connected: {internet_ok}")
    
    # Test IB connections
    print("\n2. Testing IB connections...")
    gateway_ok = net_utils.check_ib_connection("GATEWAY")
    print(f"   IB Gateway connected: {gateway_ok}")
    
    # Test latency
    print("\n3. Testing latency...")
    latency = net_utils.measure_latency("8.8.8.8")
    print(f"   Latency to 8.8.8.8: {latency}ms")
    
    # Test network status
    print("\n4. Getting network status...")
    status = net_utils.get_network_status()
    for key, value in status.items():
        if key != "timestamp":
            print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("✅ Network Utils test completed!")
