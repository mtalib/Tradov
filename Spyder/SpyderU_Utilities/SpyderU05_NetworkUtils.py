#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU05_NetworkUtils.py
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
from typing import Any
from dataclasses import dataclass
from enum import Enum
import concurrent.futures

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import socket
import requests

try:
    import ping3
    PING3_AVAILABLE = True
except ImportError:
    PING3_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

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
    error_message: str | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class NetworkUtils:
    """
    Network utilities for connectivity and performance monitoring.

    This class provides comprehensive network utilities including internet
    connectivity checking, API endpoint validation, latency measurement,
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

        self.logger.info("%s initialized", self.__class__.__name__)

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
                    self.logger.debug("Internet connection confirmed via %s", host)
                    return True

            # Fallback to HTTP test
            return self._test_http_connection(timeout)

        except Exception as e:
            self.logger.error("Internet connection check failed: %s", e, exc_info=True)
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
                    except (OSError, TimeoutError) as e:
                        # Ping failed, continue to next attempt
                        self.logger.debug("Ping attempt failed: %s", e)
                        continue
            else:
                # Fallback to socket connection timing
                for _ in range(count):
                    try:
                        start_time = time.time()
                        socket.create_connection((host, 53), timeout=PING_TIMEOUT)
                        latency = (time.time() - start_time) * 1000
                        latencies.append(latency)
                    except (OSError, TimeoutError) as e:
                        # Connection attempt failed, continue to next attempt
                        self.logger.debug("Socket connection failed: %s", e)
                        continue

            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                self.logger.debug(f"Average latency to {host}: {avg_latency:.2f}ms")
                return round(avg_latency, 2)
            else:
                self.logger.warning("Could not measure latency to %s", host)
                return -1.0

        except Exception as e:
            self.logger.error("Latency measurement failed: %s", e, exc_info=True)
            return -1.0

    def test_multiple_connections(self, endpoints: list[tuple[str, int]]) -> list[ConnectionTest]:
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
            self.logger.error("Multiple connection test failed: %s", e, exc_info=True)
            return []

    # ==========================================================================
    # PUBLIC METHODS - NETWORK MONITORING
    # ==========================================================================
    def get_network_status(self) -> dict[str, Any]:
        """
        Get comprehensive network status.

        Returns:
            Dictionary with network status information
        """
        try:
            status = {
                "internet_connected": self.check_internet_connection(),
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
            self.logger.error("Network status check failed: %s", e, exc_info=True)
            return {
                "internet_connected": False,
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

                    time.sleep(interval)  # thread-safe: time.sleep() intentional

                except Exception as e:
                    self.logger.error("Network monitoring error: %s", e, exc_info=True)
                    time.sleep(interval)  # thread-safe: time.sleep() intentional

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        self.logger.info("Network monitoring started (interval: %ss)", interval)

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _test_host_connection(self, host: str, port: int, timeout: int) -> bool:
        """Test connection to a specific host and port."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (TimeoutError, OSError):
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
                except (requests.RequestException, OSError, TimeoutError) as e:
                    # URL check failed, try next URL
                    self.logger.debug("HTTP check failed for %s: %s", url, e)
                    continue
            return False
        except (requests.RequestException, OSError) as e:
            self.logger.warning("Internet connectivity check failed: %s", e, exc_info=True)
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
_network_utils_instance: NetworkUtils | None = None

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

    net_utils = NetworkUtils()

    # Test internet connection
    internet_ok = net_utils.check_internet_connection()

    # Test latency
    latency = net_utils.measure_latency("8.8.8.8")

    # Test network status
    status = net_utils.get_network_status()
    for key, _value in status.items():
        if key != "timestamp":
            pass

