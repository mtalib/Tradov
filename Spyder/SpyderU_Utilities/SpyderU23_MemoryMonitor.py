#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU23_MemoryMonitor.py
Purpose: Memory management and monitoring utilities for system stability
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-13 Time: 15:45:00

Module Description:
    This module provides comprehensive memory monitoring and management utilities
    for the Spyder trading system. It tracks memory usage patterns, detects leaks,
    triggers garbage collection, and monitors system resource usage to ensure
    system stability during extended trading sessions.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import logging
import gc
import time
import threading
import datetime
from typing import Any
from collections.abc import Callable
from collections import deque
from dataclasses import dataclass
from pathlib import Path

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.info("Warning: psutil not available. Install with: pip install psutil")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Memory thresholds (in bytes)
MEMORY_WARNING_THRESHOLD = 1e9    # 1GB
MEMORY_CRITICAL_THRESHOLD = 2e9   # 2GB
MEMORY_EMERGENCY_THRESHOLD = 4e9  # 4GB

# Monitoring intervals (in seconds)
MEMORY_CHECK_INTERVAL = 30        # Check every 30 seconds
GC_INTERVAL = 60                  # Force GC every minute
DEEP_MONITORING_INTERVAL = 300    # Deep analysis every 5 minutes

# Data retention
MAX_MEMORY_HISTORY = 1000         # Keep last 1000 measurements
MAX_PROCESS_HISTORY = 100         # Keep last 100 process snapshots

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MemorySnapshot:
    """Single memory measurement snapshot."""
    timestamp: datetime.datetime
    rss: float              # Resident Set Size (actual physical memory)
    vms: float              # Virtual Memory Size
    percent: float          # Memory percentage of system
    available: float        # Available system memory
    process_count: int      # Number of threads/processes
    gc_count: int          # Garbage collection count

@dataclass
class ProcessInfo:
    """Information about a specific process."""
    pid: int
    name: str
    memory_rss: float
    memory_percent: float
    cpu_percent: float
    status: str
    create_time: datetime.datetime

@dataclass
class MemoryAlert:
    """Memory alert/warning information."""
    level: str              # 'info', 'warning', 'critical', 'emergency'
    message: str
    memory_usage: float
    recommended_action: str
    timestamp: datetime.datetime

@dataclass
class MemoryStats:
    """Aggregated memory statistics."""
    current_usage: float
    peak_usage: float
    average_usage: float
    trend_direction: str    # 'increasing', 'decreasing', 'stable'
    leak_detected: bool
    time_period: str
    measurements_count: int

# ==============================================================================
# MAIN MEMORY MONITOR CLASS
# ==============================================================================
class SpyderMemoryMonitor:
    """
    Comprehensive memory monitoring and management system.

    Features:
    - Real-time memory usage tracking
    - Memory leak detection
    - Automatic garbage collection
    - System process monitoring
    - Performance impact analysis
    - Alert system for memory issues
    """

    def __init__(self, enable_auto_gc: bool = True, enable_deep_monitoring: bool = True):
        """Initialize the memory monitor."""
        # Setup logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.enable_auto_gc = enable_auto_gc
        self.enable_deep_monitoring = enable_deep_monitoring
        self.monitoring_active = False

        # Data storage
        self.memory_history: deque = deque(maxlen=MAX_MEMORY_HISTORY)
        self.process_history: deque = deque(maxlen=MAX_PROCESS_HISTORY)
        self.alerts: deque = deque(maxlen=100)

        # Process tracking
        self.main_process = None
        self.tracked_processes: dict[int, ProcessInfo] = {}

        # Statistics
        self.last_gc_time = time.time()
        self.total_gc_triggered = 0
        self.peak_memory_usage = 0.0
        self.baseline_memory = 0.0

        # Threading
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()

        # Callbacks
        self.alert_callbacks: list[Callable] = []
        self.stats_callbacks: list[Callable] = []

        # Initialize
        if PSUTIL_AVAILABLE:
            self.main_process = psutil.Process()
            self.baseline_memory = self.main_process.memory_info().rss

        self.logger.info("Memory monitor initialized")

    # ==========================================================================
    # MONITORING CONTROL
    # ==========================================================================
    def start_monitoring(self):
        """Start continuous memory monitoring."""
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available - memory monitoring disabled")
            return False

        if self.monitoring_active:
            return True

        self.monitoring_active = True
        self.stop_monitoring.clear()

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="SpyderMemoryMonitor",
            daemon=True
        )
        self.monitor_thread.start()

        self.logger.info("Memory monitoring started")
        return True

    def stop_monitoring(self):
        """Stop memory monitoring."""
        if not self.monitoring_active:
            return

        self.monitoring_active = False
        self.stop_monitoring.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)

        self.logger.info("Memory monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop running in separate thread."""
        last_check = 0
        last_gc = 0
        last_deep_check = 0

        while not self.stop_monitoring.is_set():
            try:
                current_time = time.time()

                # Regular memory check
                if current_time - last_check >= MEMORY_CHECK_INTERVAL:
                    self._perform_memory_check()
                    last_check = current_time

                # Garbage collection
                if (self.enable_auto_gc and
                    current_time - last_gc >= GC_INTERVAL):
                    self._perform_garbage_collection()
                    last_gc = current_time

                # Deep monitoring
                if (self.enable_deep_monitoring and
                    current_time - last_deep_check >= DEEP_MONITORING_INTERVAL):
                    self._perform_deep_analysis()
                    last_deep_check = current_time

                # Sleep for a short interval
                self.stop_monitoring.wait(timeout=5.0)

            except Exception as e:
                self.error_handler.handle_error(e, "Memory monitoring loop error")
                time.sleep(10)  # thread-safe: time.sleep() intentional

    # ==========================================================================
    # MEMORY MEASUREMENT
    # ==========================================================================
    def _perform_memory_check(self):
        """Perform a single memory measurement."""
        try:
            if not self.main_process:
                return

            # Get memory information
            memory_info = self.main_process.memory_info()
            memory_percent = self.main_process.memory_percent()
            system_memory = psutil.virtual_memory()

            # Get garbage collection stats
            gc_stats = gc.get_stats()
            gc_count = sum(stat['collections'] for stat in gc_stats)

            # Create snapshot
            snapshot = MemorySnapshot(
                timestamp=datetime.datetime.now(),
                rss=memory_info.rss,
                vms=memory_info.vms,
                percent=memory_percent,
                available=system_memory.available,
                process_count=self.main_process.num_threads(),
                gc_count=gc_count
            )

            # Store snapshot
            self.memory_history.append(snapshot)

            # Update peak usage
            if memory_info.rss > self.peak_memory_usage:
                self.peak_memory_usage = memory_info.rss

            # Check for alerts
            self._check_memory_alerts(snapshot)

            # Notify callbacks
            for callback in self.stats_callbacks:
                try:
                    callback(snapshot)
                except Exception as e:
                    self.logger.error("Stats callback error: %s", e, exc_info=True)

        except Exception as e:
            self.error_handler.handle_error(e, "Memory check failed")

    def _check_memory_alerts(self, snapshot: MemorySnapshot):
        """Check if memory usage requires alerts."""
        rss = snapshot.rss

        alert = None

        if rss > MEMORY_EMERGENCY_THRESHOLD:
            alert = MemoryAlert(
                level='emergency',
                message=f"Emergency memory usage: {rss/1e9:.2f}GB",
                memory_usage=rss,
                recommended_action="Immediate restart recommended",
                timestamp=snapshot.timestamp
            )
        elif rss > MEMORY_CRITICAL_THRESHOLD:
            alert = MemoryAlert(
                level='critical',
                message=f"Critical memory usage: {rss/1e9:.2f}GB",
                memory_usage=rss,
                recommended_action="Stop non-essential processes",
                timestamp=snapshot.timestamp
            )
        elif rss > MEMORY_WARNING_THRESHOLD:
            alert = MemoryAlert(
                level='warning',
                message=f"High memory usage: {rss/1e9:.2f}GB",
                memory_usage=rss,
                recommended_action="Monitor closely",
                timestamp=snapshot.timestamp
            )

        if alert:
            self.alerts.append(alert)
            self._notify_alert(alert)

    def _notify_alert(self, alert: MemoryAlert):
        """Notify all registered alert callbacks."""
        self.logger.warning("Memory Alert: %s", alert.message)

        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error("Alert callback error: %s", e, exc_info=True)

    # ==========================================================================
    # GARBAGE COLLECTION MANAGEMENT
    # ==========================================================================
    def _perform_garbage_collection(self):
        """Perform strategic garbage collection."""
        try:
            before_memory = self.main_process.memory_info().rss if self.main_process else 0

            # Force garbage collection
            collected = gc.collect()

            after_memory = self.main_process.memory_info().rss if self.main_process else 0
            freed_memory = before_memory - after_memory

            self.total_gc_triggered += 1
            self.last_gc_time = time.time()

            if freed_memory > 0:
                self.logger.info(f"GC freed {freed_memory/1e6:.1f}MB, collected {collected} objects")

        except Exception as e:
            self.error_handler.handle_error(e, "Garbage collection failed")

    def force_garbage_collection(self) -> dict[str, Any]:
        """Force immediate garbage collection and return results."""
        try:
            before_memory = self.main_process.memory_info().rss if self.main_process else 0
            before_objects = len(gc.get_objects())

            # Perform collection
            collected = gc.collect()

            after_memory = self.main_process.memory_info().rss if self.main_process else 0
            after_objects = len(gc.get_objects())

            freed_memory = before_memory - after_memory
            freed_objects = before_objects - after_objects

            results = {
                'memory_before_mb': before_memory / 1e6,
                'memory_after_mb': after_memory / 1e6,
                'memory_freed_mb': freed_memory / 1e6,
                'objects_before': before_objects,
                'objects_after': after_objects,
                'objects_freed': freed_objects,
                'collections_performed': collected
            }

            self.logger.info(f"Manual GC: freed {freed_memory/1e6:.1f}MB and {freed_objects} objects")
            return results

        except Exception as e:
            self.error_handler.handle_error(e, "Manual garbage collection failed")
            return {}

    # ==========================================================================
    # PROCESS MONITORING
    # ==========================================================================
    def _perform_deep_analysis(self):
        """Perform deep memory and process analysis."""
        try:
            # Analyze memory trends
            self._analyze_memory_trends()

            # Check for memory leaks
            leak_detected = self._detect_memory_leaks()

            if leak_detected:
                self.logger.warning("Potential memory leak detected")

        except Exception as e:
            self.error_handler.handle_error(e, "Deep analysis failed")

    def _analyze_memory_trends(self):
        """Analyze memory usage trends."""
        if len(self.memory_history) < 10:
            return

        try:
            recent_snapshots = list(self.memory_history)[-10:]
            memory_values = [s.rss for s in recent_snapshots]

            # Calculate trend
            if len(memory_values) >= 2:
                start_memory = memory_values[0]
                end_memory = memory_values[-1]
                trend_change = (end_memory - start_memory) / start_memory * 100

                if abs(trend_change) > 10:  # More than 10% change
                    direction = "increasing" if trend_change > 0 else "decreasing"
                    self.logger.info(f"Memory trend: {direction} by {abs(trend_change):.1f}%")

        except Exception as e:
            self.logger.error("Trend analysis failed: %s", e, exc_info=True)

    def _detect_memory_leaks(self) -> bool:
        """Detect potential memory leaks."""
        if len(self.memory_history) < 20:
            return False

        try:
            # Get memory values from last 20 measurements
            recent_memory = [s.rss for s in list(self.memory_history)[-20:]]

            # Check for consistent upward trend
            increases = 0
            for i in range(1, len(recent_memory)):
                if recent_memory[i] > recent_memory[i-1]:
                    increases += 1

            # If memory increased in >80% of measurements, likely a leak
            increase_ratio = increases / (len(recent_memory) - 1)

            if increase_ratio > 0.8:
                current_memory = recent_memory[-1]
                baseline_diff = (current_memory - self.baseline_memory) / self.baseline_memory

                # Only consider it a leak if memory has grown significantly
                if baseline_diff > 0.5:  # 50% increase from baseline
                    return True

        except Exception as e:
            self.logger.error("Leak detection failed: %s", e, exc_info=True)

        return False

    # ==========================================================================
    # STATISTICS AND REPORTING
    # ==========================================================================
    def get_current_stats(self) -> dict[str, Any]:
        """Get current memory statistics."""
        if not self.memory_history:
            return {}

        try:
            current = self.memory_history[-1]

            # Calculate statistics from recent history
            recent_snapshots = list(self.memory_history)[-50:]  # Last 50 measurements
            memory_values = [s.rss for s in recent_snapshots]

            avg_memory = sum(memory_values) / len(memory_values)

            return {
                'current_memory_gb': current.rss / 1e9,
                'current_memory_percent': current.percent,
                'peak_memory_gb': self.peak_memory_usage / 1e9,
                'average_memory_gb': avg_memory / 1e9,
                'baseline_memory_gb': self.baseline_memory / 1e9,
                'memory_growth_percent': ((current.rss - self.baseline_memory) / self.baseline_memory) * 100,
                'available_memory_gb': current.available / 1e9,
                'process_count': current.process_count,
                'gc_collections': current.gc_count,
                'total_gc_triggered': self.total_gc_triggered,
                'monitoring_duration_hours': len(self.memory_history) * MEMORY_CHECK_INTERVAL / 3600,
                'last_updated': current.timestamp.isoformat()
            }

        except Exception as e:
            self.error_handler.handle_error(e, "Stats calculation failed")
            return {}

    def get_recent_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent memory alerts."""
        alerts = []
        for alert in list(self.alerts)[-limit:]:
            alerts.append({
                'level': alert.level,
                'message': alert.message,
                'memory_gb': alert.memory_usage / 1e9,
                'recommended_action': alert.recommended_action,
                'timestamp': alert.timestamp.isoformat()
            })
        return alerts

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    def add_alert_callback(self, callback: Callable):
        """Add callback for memory alerts."""
        self.alert_callbacks.append(callback)

    def add_stats_callback(self, callback: Callable):
        """Add callback for memory statistics updates."""
        self.stats_callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """Remove a callback."""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
        if callback in self.stats_callbacks:
            self.stats_callbacks.remove(callback)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def is_monitoring_active(self) -> bool:
        """Check if monitoring is currently active."""
        return self.monitoring_active

    def get_memory_history_csv(self) -> str:
        """Export memory history as CSV format."""
        if not self.memory_history:
            return ""

        csv_lines = ["timestamp,rss_gb,vms_gb,percent,available_gb,process_count,gc_count"]

        for snapshot in self.memory_history:
            line = f"{snapshot.timestamp.isoformat()},"
            line += f"{snapshot.rss/1e9:.3f},"
            line += f"{snapshot.vms/1e9:.3f},"
            line += f"{snapshot.percent:.2f},"
            line += f"{snapshot.available/1e9:.3f},"
            line += f"{snapshot.process_count},"
            line += f"{snapshot.gc_count}"
            csv_lines.append(line)

        return "\n".join(csv_lines)

    def clear_history(self):
        """Clear all monitoring history."""
        self.memory_history.clear()
        self.process_history.clear()
        self.alerts.clear()
        self.peak_memory_usage = 0.0
        if self.main_process:
            self.baseline_memory = self.main_process.memory_info().rss

# ==============================================================================
# GLOBAL MEMORY MONITOR INSTANCE
# ==============================================================================
# Create a global instance for easy access throughout the application
_global_memory_monitor = None

def get_memory_monitor() -> SpyderMemoryMonitor:
    """Get the global memory monitor instance."""
    global _global_memory_monitor
    if _global_memory_monitor is None:
        _global_memory_monitor = SpyderMemoryMonitor()
    return _global_memory_monitor

def start_global_monitoring():
    """Start global memory monitoring."""
    monitor = get_memory_monitor()
    return monitor.start_monitoring()

def stop_global_monitoring():
    """Stop global memory monitoring."""
    monitor = get_memory_monitor()
    monitor.stop_monitoring()

# ==============================================================================
# TESTING AND DEMONSTRATION
# ==============================================================================
def main():
    """Demonstrate memory monitoring capabilities."""
    logging.info("Spyder Memory Monitor Demo")
    logging.info("=" * 50)

    # Create monitor
    monitor = SpyderMemoryMonitor()

    # Add callbacks
    def alert_handler(alert):
        logging.info("ALERT [%s]: %s", alert.level.upper(), alert.message)

    def stats_handler(snapshot):
        logging.info(f"Memory: {snapshot.rss/1e6:.1f}MB ({snapshot.percent:.1f}%)")

    monitor.add_alert_callback(alert_handler)
    monitor.add_stats_callback(stats_handler)

    # Start monitoring
    if monitor.start_monitoring():
        logging.info("Monitoring started...")

        try:
            time.sleep(10)  # thread-safe: time.sleep() intentional

            # Show current stats
            stats = monitor.get_current_stats()
            logging.info("\nCurrent Statistics:")
            for key, value in stats.items():
                logging.info("  %s: %s", key, value)

            # Test garbage collection
            logging.info("\nTesting garbage collection...")
            gc_results = monitor.force_garbage_collection()
            for key, value in gc_results.items():
                logging.info("  %s: %s", key, value)

        except KeyboardInterrupt:
            logging.info("\nShutting down...")
        finally:
            monitor.stop_monitoring()
    else:
        logging.info("Failed to start monitoring (psutil not available)")

if __name__ == "__main__":
    main()
