#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System

Tradov Version: 1.0
Module: TradovT16_SystemHealthMonitor.py
Group: T (Testing)
Purpose: Real-time system health monitoring and diagnostics
Author: Mohamed Talib
Date Created: 2025-08-13
Last Updated: 2026-06-26 Time: 13:25:07

Description:
    Real-time monitoring dashboard that continuously checks system health,
    signal values, connectivity status, and performance metrics. Provides
    alerts for anomalies and maintains health history.
"""

import json
import os
import signal
# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional
# Terminal colors
from colorama import Back, Fore, Style, init

init(autoreset=True)

# ==============================================================================
# MONITORING CONFIGURATION
# ==============================================================================


@dataclass
class MonitorConfig:
    """Configuration for system monitor"""

    update_interval: int = 5  # seconds
    history_size: int = 100  # number of samples to keep
    alert_thresholds: dict = None

    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                "GEX": {"min": -10, "max": 10},  # Billions
                "DIX": {"min": 20, "max": 70},  # Percentage
                "SWAN": {"min": 1, "max": 5},  # Score
                "SKEW": {"min": 100, "max": 150},  # Index
            }


# ==============================================================================
# HEALTH METRICS
# ==============================================================================


@dataclass
class SystemHealth:
    """System health snapshot"""

    timestamp: datetime
    components: dict[str, bool]
    signals: dict[str, float]
    performance: dict[str, float]
    alerts: list[str]
    overall_status: str


# ==============================================================================
# SYSTEM HEALTH MONITOR
# ==============================================================================


class SystemHealthMonitor:
    """
    Real-time system health monitoring
    """

    def __init__(self, config: MonitorConfig = None):
        self.config = config or MonitorConfig()
        self.running = False
        self.monitor_thread = None
        self.health_history = deque(maxlen=self.config.history_size)
        self.current_health = None

        # Component status
        self.components = {
            "Core": False,
            "Broker": False,
            "MarketData": False,
            "Signals": False,
            "Risk": False,
            "GUI": False,
        }

        # Signal values
        self.signals = {"GEX": 0.0, "DIX": 0.0, "SWAN": 0.0, "SKEW": 0.0}

        # Performance metrics
        self.performance = {"cpu_usage": 0.0, "memory_usage": 0.0, "latency": 0.0}

        # Try to import components
        self._check_imports()

    def _check_imports(self):
        """Check which components are available"""
        try:
            from TradovS_Signals.TradovS07_CustomMetricsOrchestrator import \
                CustomMetricsOrchestrator

            self.orchestrator = CustomMetricsOrchestrator()
            self.components["Signals"] = True
        except ImportError:
            self.orchestrator = None
            self.components["Signals"] = False

        try:
            from TradovA_Core.TradovA03_Configuration import \
                TradovConfiguration

            self.components["Core"] = True
        except ImportError:
            self.components["Core"] = False

        try:
            from TradovB_Broker.TradovB05_ConnectionManager import \
                ConnectionManager

            self.components["Broker"] = True
        except ImportError:
            self.components["Broker"] = False

    def start(self):
        """Start monitoring"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print(f"{Fore.GREEN}✅ System monitor started")

    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print(f"{Fore.YELLOW}⏹️  System monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect health data
                health = self._collect_health_data()
                self.current_health = health
                self.health_history.append(health)

                # Display status
                self._display_status(health)

                # Check for alerts
                self._check_alerts(health)

            except Exception as e:
                print(f"{Fore.RED}❌ Monitor error: {e}")

            time.sleep(self.config.update_interval)

    def _collect_health_data(self) -> SystemHealth:
        """Collect current system health data"""
        alerts = []

        # Update signal values
        if self.orchestrator and self.components["Signals"]:
            try:
                self.orchestrator.update_all_metrics()
                metrics = self.orchestrator.get_all_metrics()
                self.signals["GEX"] = metrics.get("GEX", 0)
                self.signals["DIX"] = metrics.get("DIX", 0)
                self.signals["SWAN"] = metrics.get("SWAN", 0)
                self.signals["OPT_SKEW"] = metrics.get("OPT_SKEW", 0)
            except Exception as e:
                alerts.append(f"Signal update failed: {e}")
        else:
            # Simulate values for testing
            import random

            self.signals["GEX"] = -2.5 + random.gauss(0, 0.5)
            self.signals["DIX"] = 42.5 + random.gauss(0, 2)
            self.signals["SWAN"] = 1.85 + random.gauss(0, 0.2)
            self.signals["SKEW"] = 125 + random.gauss(0, 5)

        # Update performance metrics
        try:
            import psutil

            self.performance["cpu_usage"] = psutil.cpu_percent(interval=0.1)
            self.performance["memory_usage"] = psutil.virtual_memory().percent
        except ImportError:
            self.performance["cpu_usage"] = 10.5
            self.performance["memory_usage"] = 45.2

        # Determine overall status
        active_components = sum(1 for v in self.components.values() if v)
        total_components = len(self.components)

        if active_components == total_components:
            overall_status = "HEALTHY"
        elif active_components >= total_components * 0.7:
            overall_status = "DEGRADED"
        else:
            overall_status = "CRITICAL"

        return SystemHealth(
            timestamp=datetime.now(),
            components=self.components.copy(),
            signals=self.signals.copy(),
            performance=self.performance.copy(),
            alerts=alerts,
            overall_status=overall_status,
        )

    def _display_status(self, health: SystemHealth):
        """Display current status"""
        # Clear screen (platform-specific)
        os.system("cls" if os.name == "nt" else "clear")

        # Header
        print(f"{Style.BRIGHT}{Fore.CYAN}╔{'═'*78}╗")
        print(f"{Style.BRIGHT}{Fore.CYAN}║{' '*20}TRADOV SYSTEM HEALTH MONITOR{' '*30}║")
        print(f"{Style.BRIGHT}{Fore.CYAN}╚{'═'*78}╝")
        print(f"\n{Fore.WHITE}Timestamp: {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Overall status
        status_color = {"HEALTHY": Fore.GREEN, "DEGRADED": Fore.YELLOW, "CRITICAL": Fore.RED}.get(
            health.overall_status, Fore.WHITE
        )

        print(f"\n{Style.BRIGHT}Overall Status: {status_color}● {health.overall_status}")

        # Components
        print(f"\n{Style.BRIGHT}{Fore.CYAN}Components:")
        for component, status in health.components.items():
            symbol = "✅" if status else "❌"
            color = Fore.GREEN if status else Fore.RED
            print(f"  {color}{symbol} {component}")

        # Signals
        print(f"\n{Style.BRIGHT}{Fore.CYAN}Market Signals:")

        # GEX with color coding
        gex_val = health.signals["GEX"]
        gex_color = Fore.RED if gex_val < -3 else Fore.GREEN if gex_val > 0 else Fore.YELLOW
        print(f"  {gex_color}GEX:  {gex_val:>7.2f}B {self._get_trend_arrow('GEX')}")

        # DIX with color coding
        dix_val = health.signals["DIX"]
        dix_color = Fore.GREEN if dix_val > 45 else Fore.RED if dix_val < 40 else Fore.YELLOW
        print(f"  {dix_color}DIX:  {dix_val:>7.1f}% {self._get_trend_arrow('DIX')}")

        # SWAN with color coding
        swan_val = health.signals["SWAN"]
        swan_color = Fore.RED if swan_val > 3 else Fore.GREEN if swan_val < 2 else Fore.YELLOW
        print(f"  {swan_color}SWAN: {swan_val:>7.2f}  {self._get_trend_arrow('SWAN')}")

        # SKEW with color coding
        skew_val = health.signals["SKEW"]
        skew_color = Fore.RED if skew_val > 135 else Fore.GREEN if skew_val < 120 else Fore.YELLOW
        print(f"  {skew_color}SKEW: {skew_val:>7.1f}  {self._get_trend_arrow('SKEW')}")

        # Performance
        print(f"\n{Style.BRIGHT}{Fore.CYAN}System Performance:")
        cpu_color = Fore.RED if health.performance["cpu_usage"] > 80 else Fore.GREEN
        mem_color = Fore.RED if health.performance["memory_usage"] > 80 else Fore.GREEN
        print(f"  {cpu_color}CPU Usage:    {health.performance['cpu_usage']:>5.1f}%")
        print(f"  {mem_color}Memory Usage: {health.performance['memory_usage']:>5.1f}%")

        # Alerts
        if health.alerts:
            print(f"\n{Style.BRIGHT}{Fore.RED}⚠️  Alerts:")
            for alert in health.alerts:
                print(f"  • {alert}")

        # Footer
        print(f"\n{Fore.CYAN}{'─'*80}")
        print(f"{Fore.WHITE}Press Ctrl+C to stop monitoring")

    def _get_trend_arrow(self, signal: str) -> str:
        """Get trend arrow for signal"""
        if len(self.health_history) < 2:
            return "→"

        current = self.current_health.signals.get(signal, 0)
        previous = self.health_history[-2].signals.get(signal, 0)

        if current > previous * 1.01:
            return "↑"
        elif current < previous * 0.99:
            return "↓"
        else:
            return "→"

    def _check_alerts(self, health: SystemHealth):
        """Check for alert conditions"""
        alerts = []

        # Check signal thresholds
        for sig_name, value in health.signals.items():
            thresholds = self.config.alert_thresholds.get(sig_name, {})
            if "min" in thresholds and value < thresholds["min"]:
                alerts.append(f"{sig_name} below minimum: {value:.2f} < {thresholds['min']}")
            if "max" in thresholds and value > thresholds["max"]:
                alerts.append(f"{sig_name} above maximum: {value:.2f} > {thresholds['max']}")

        # Check component failures
        failed_components = [k for k, v in health.components.items() if not v]
        if failed_components:
            alerts.append(f"Components offline: {', '.join(failed_components)}")

        # Check performance
        if health.performance["cpu_usage"] > 90:
            alerts.append(f"High CPU usage: {health.performance['cpu_usage']:.1f}%")
        if health.performance["memory_usage"] > 90:
            alerts.append(f"High memory usage: {health.performance['memory_usage']:.1f}%")

        # Log alerts
        for alert in alerts:
            self._log_alert(alert)

    def _log_alert(self, alert: str):
        """Log alert to file"""
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/health_alerts.log", "a") as f:
                f.write(f"{datetime.now().isoformat()} - {alert}\n")
        except Exception as e:
            print(f"{Fore.RED}Failed to log alert: {e}")

    def get_health_summary(self) -> dict:
        """Get health summary"""
        if not self.health_history:
            return {}

        # Calculate statistics
        recent_health = list(self.health_history)[-10:]  # Last 10 samples

        avg_signals = {}
        for sig_name in self.signals:
            values = [h.signals[sig_name] for h in recent_health]
            avg_signals[sig_name] = {
                "current": self.signals[sig_name],
                "average": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": (
                self.current_health.overall_status if self.current_health else "UNKNOWN"
            ),
            "components": self.components,
            "signals": avg_signals,
            "performance": self.performance,
            "sample_count": len(self.health_history),
        }

    def export_health_report(self, filepath: str = None):
        """Export health report to file"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"health_report_{timestamp}.json"

        summary = self.get_health_summary()

        # Add historical data
        summary["history"] = [
            {"timestamp": h.timestamp.isoformat(), "status": h.overall_status, "signals": h.signals}
            for h in list(self.health_history)[-20:]  # Last 20 samples
        ]

        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"{Fore.GREEN}✅ Health report exported to: {filepath}")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print(f"\n{Fore.YELLOW}Stopping monitor...")
    monitor.stop()
    monitor.export_health_report()
    sys.exit(0)


def main():
    """Main execution"""
    global monitor

    print(f"{Style.BRIGHT}{Fore.CYAN}Starting Tradov System Health Monitor...")
    print(f"{Fore.WHITE}This will continuously monitor system health.")
    print(f"{Fore.WHITE}Press Ctrl+C to stop.\n")

    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Create and start monitor
    config = MonitorConfig(update_interval=5)
    monitor = SystemHealthMonitor(config)
    monitor.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
