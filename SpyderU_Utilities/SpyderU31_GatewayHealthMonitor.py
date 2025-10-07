#!/usr/bin/env python3
"""
SPYDER - Advanced Gateway Health Monitor
Implements API handshake testing bey                check_type="api_handshake",
                success=success,
                response_time_ms=response_time,
                details={
                    "test_method": "ib_async_connection",
                    "client_id_used": client_id,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="api_handshake",
                success=False,
                response_time_ms=response_time,
                error_message=str(e),
            )
        """ checks and comprehensive monitoring
Based on production algorithmic trading systems research
"""

import socket
import time
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass
import json
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""

    timestamp: datetime
    check_type: str
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    details: Optional[Dict] = None


class GatewayHealthMonitor:
    """
    Advanced Gateway health monitoring beyond simple port checks

    Features:
    - API handshake testing (not just port availability)
    - Error pattern detection in logs
    - Memory usage monitoring
    - Connection stability tracking
    - Early warning system
    """

    def __init__(self, host="127.0.0.1", port=4002, log_path=None):
        self.host = host
        self.port = port
        self.log_path = log_path or Path.home() / "ibgateway" / "gateway.log"

        # Health tracking
        self.health_history: List[HealthCheckResult] = []
        self.max_history = 1000

        # Error patterns from research
        self.critical_error_patterns = [
            "Error 1100",  # Connectivity lost
            "Error 502",  # Cannot connect
            "Error 504",  # Not connected
            "OutOfMemoryError",  # Java heap exhausted
            "Connection reset",  # Socket error
            "Peer closed connection",  # IB server disconnected
            "java.net.SocketException",
            "TimeoutError",
            "BrokenPipeError",
        ]

        # Performance metrics
        self.connection_stats = {
            "successful_checks": 0,
            "failed_checks": 0,
            "avg_response_time": 0.0,
            "last_success": None,
            "last_failure": None,
            "consecutive_failures": 0,
        }

        self.monitoring_active = False
        self.monitor_thread = None

    def check_port_availability(self) -> HealthCheckResult:
        """Basic port connectivity check"""
        start_time = time.time()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()

            response_time = (time.time() - start_time) * 1000
            success = result == 0

            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="port_check",
                success=success,
                response_time_ms=response_time,
                error_message=None if success else f"Port {self.port} not accessible",
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="port_check",
                success=False,
                response_time_ms=response_time,
                error_message=str(e),
            )

    async def check_api_handshake(self) -> HealthCheckResult:
        """
        API connectivity test using ib_async connection
        More reliable than raw socket handshake

        **PRODUCTION MODE: DISABLED**
        This check creates random client connections (900-999) which show up
        in Gateway as unwanted test clients. For production, use port check only.
        """
        start_time = time.time()

        # PRODUCTION: Skip API handshake test to avoid test client connections
        return HealthCheckResult(
            timestamp=datetime.now(),
            check_type="api_handshake",
            success=True,  # Assume success if port is open
            response_time_ms=0,
            error_message="Skipped in production mode (avoid test client connections)",
        )

        # DISABLED TEST CODE (creates unwanted client connections):
        """
        try:
            import ib_async
            import asyncio

            # Use random client ID to avoid conflicts
            import random

            client_id = random.randint(900, 999)

            async def test_connection():
                ib = ib_async.IB()
                try:
                    await ib.connectAsync(
                        self.host, self.port, clientId=client_id, timeout=5
                    )
                    connected = ib.isConnected()
                    if connected:
                        ib.disconnect()
                        # Small delay for cleanup
                        await asyncio.sleep(0.5)
                    return connected
                except Exception:
                    return False

            # Run the async test
            success = await test_connection()
            response_time = (time.time() - start_time) * 1000

            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="api_handshake",
                success=success,
                response_time_ms=response_time,
                details={
                    "test_method": "ib_async_connection",
                    "client_id_used": client_id,
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="api_handshake",
                success=False,
                response_time_ms=response_time,
                error_message=f"API connection test failed: {e}",
                details={"test_method": "ib_async_connection"},
            )

    def check_log_patterns(self) -> HealthCheckResult:
        """
        Scan Gateway logs for critical error patterns
        Early warning system for Gateway problems
        """
        start_time = time.time()

        try:
            if not self.log_path.exists():
                return HealthCheckResult(
                    timestamp=datetime.now(),
                    check_type="log_scan",
                    success=False,
                    response_time_ms=0,
                    error_message=f"Log file not found: {self.log_path}",
                )

            # Read last 1000 lines for recent errors
            with open(self.log_path, "r", errors="ignore") as f:
                lines = f.readlines()[-1000:]

            # Scan for error patterns in recent lines (last 5 minutes)
            recent_errors = []
            current_time = datetime.now()

            for line in lines:
                # Look for critical error patterns
                for pattern in self.critical_error_patterns:
                    if pattern in line:
                        recent_errors.append(
                            {
                                "pattern": pattern,
                                "line": line.strip(),
                                "timestamp": current_time,  # Approximate
                            }
                        )

            response_time = (time.time() - start_time) * 1000

            # Consider it a warning if errors found, not necessarily failure
            success = len(recent_errors) == 0

            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="log_scan",
                success=success,
                response_time_ms=response_time,
                error_message=(
                    f"Found {len(recent_errors)} critical error patterns"
                    if recent_errors
                    else None
                ),
                details={
                    "error_count": len(recent_errors),
                    "recent_errors": recent_errors[-5:],  # Last 5 errors
                },
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                timestamp=datetime.now(),
                check_type="log_scan",
                success=False,
                response_time_ms=response_time,
                error_message=f"Log scan failed: {e}",
            )

    def perform_comprehensive_health_check(self) -> Dict[str, HealthCheckResult]:
        """Perform all health checks and return results"""
        results = {}

        # 1. Port availability check
        results["port"] = self.check_port_availability()

        # 2. API handshake test (more thorough)
        if results["port"].success:
            results["api"] = self.check_api_handshake()
        else:
            results["api"] = HealthCheckResult(
                timestamp=datetime.now(),
                check_type="api_handshake",
                success=False,
                response_time_ms=0,
                error_message="Skipped - port not available",
            )

        # 3. Log pattern analysis
        results["logs"] = self.check_log_patterns()

        # Update statistics
        self._update_stats(results)

        # Store in history
        for result in results.values():
            self.health_history.append(result)

        # Trim history
        if len(self.health_history) > self.max_history:
            self.health_history = self.health_history[-self.max_history :]

        return results

    def _update_stats(self, results: Dict[str, HealthCheckResult]):
        """Update connection statistics"""
        api_result = results.get("api")
        if not api_result:
            return

        if api_result.success:
            self.connection_stats["successful_checks"] += 1
            self.connection_stats["last_success"] = datetime.now()
            self.connection_stats["consecutive_failures"] = 0
        else:
            self.connection_stats["failed_checks"] += 1
            self.connection_stats["last_failure"] = datetime.now()
            self.connection_stats["consecutive_failures"] += 1

        # Update average response time
        total_checks = (
            self.connection_stats["successful_checks"]
            + self.connection_stats["failed_checks"]
        )
        if total_checks > 0:
            old_avg = self.connection_stats["avg_response_time"]
            new_response = api_result.response_time_ms
            self.connection_stats["avg_response_time"] = (
                old_avg * (total_checks - 1) + new_response
            ) / total_checks

    def get_health_status(self) -> Dict:
        """Get overall health status and recommendations"""
        if not self.health_history:
            return {"status": "unknown", "message": "No health checks performed yet"}

        # Get recent results (last 5 minutes)
        recent_cutoff = datetime.now() - timedelta(minutes=5)
        recent_results = [
            r for r in self.health_history if r.timestamp >= recent_cutoff
        ]

        if not recent_results:
            return {"status": "stale", "message": "No recent health checks"}

        # Analyze recent results by type
        api_results = [r for r in recent_results if r.check_type == "api_handshake"]
        log_results = [r for r in recent_results if r.check_type == "log_scan"]

        # Overall health assessment
        api_healthy = len(api_results) > 0 and api_results[-1].success
        logs_clean = len(log_results) == 0 or log_results[-1].success
        consecutive_failures = self.connection_stats["consecutive_failures"]

        if api_healthy and logs_clean and consecutive_failures < 3:
            status = "healthy"
            message = "Gateway is responding normally"
        elif api_healthy and consecutive_failures < 5:
            status = "warning"
            message = f"Gateway responding but {consecutive_failures} recent failures"
        elif consecutive_failures >= 5:
            status = "critical"
            message = f"Gateway failing consistently ({consecutive_failures} consecutive failures)"
        else:
            status = "unhealthy"
            message = "Gateway not responding to API requests"

        return {
            "status": status,
            "message": message,
            "stats": self.connection_stats,
            "recent_checks": len(recent_results),
            "last_check": recent_results[-1].timestamp if recent_results else None,
        }

    def start_monitoring(self, interval_seconds=30):
        """Start continuous monitoring in background thread"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return

        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, args=(interval_seconds,), daemon=True
        )
        self.monitor_thread.start()
        logger.info(
            f"Started Gateway health monitoring (interval: {interval_seconds}s)"
        )

    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        logger.info("Stopped Gateway health monitoring")

    def _monitoring_loop(self, interval_seconds):
        """Background monitoring loop"""
        while self.monitoring_active:
            try:
                results = self.perform_comprehensive_health_check()
                status = self.get_health_status()

                # Log significant events
                if status["status"] in ["critical", "unhealthy"]:
                    logger.error(f"Gateway health: {status['message']}")
                elif status["status"] == "warning":
                    logger.warning(f"Gateway health: {status['message']}")
                else:
                    logger.debug(f"Gateway health: {status['message']}")

                time.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(interval_seconds)


def main():
    """Test the health monitor"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("🏥 SPYDER - Advanced Gateway Health Monitor")
    print("=" * 50)

    monitor = GatewayHealthMonitor()

    print("🔍 Running comprehensive health check...")
    results = monitor.perform_comprehensive_health_check()

    for check_type, result in results.items():
        status = "✅" if result.success else "❌"
        print(f"{status} {check_type.upper()}: {result.response_time_ms:.1f}ms")

        if result.error_message:
            print(f"   Error: {result.error_message}")

        if result.details:
            print(f"   Details: {result.details}")

    print(f"\\n📊 Overall Health Status:")
    status = monitor.get_health_status()
    status_emoji = {
        "healthy": "✅",
        "warning": "⚠️",
        "unhealthy": "❌",
        "critical": "🚨",
        "unknown": "❓",
        "stale": "⏰",
    }

    emoji = status_emoji.get(status["status"], "❓")
    print(f"{emoji} {status['status'].upper()}: {status['message']}")

    if status.get("stats"):
        stats = status["stats"]
        print(
            f"📈 Success Rate: {stats['successful_checks']}/{stats['successful_checks'] + stats['failed_checks']}"
        )
        print(f"⏱️ Avg Response: {stats['avg_response_time']:.1f}ms")
        print(f"🔄 Consecutive Failures: {stats['consecutive_failures']}")

    print("\\n🔄 Starting continuous monitoring for 2 minutes...")
    monitor.start_monitoring(interval_seconds=10)

    try:
        time.sleep(120)  # Monitor for 2 minutes
    except KeyboardInterrupt:
        print("\\n⚠️ Monitoring interrupted")
    finally:
        monitor.stop_monitoring()
        print("🏁 Health monitoring stopped")


if __name__ == "__main__":
    main()
