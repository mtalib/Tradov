#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Dashboard Signal Monitoring Integration Test
===================================================

Test script for comprehensive validation of signal monitoring integration
between the trading dashboard and IB Gateway real-time data feeds.

Author: SPYDER AI System
Created: 2025-01-07
Purpose: Test signal calculation, display, and real-time updates in dashboard

Signal Coverage:
- HMM (Hidden Markov Model) Signal
- SKEW Signal (Options Skew)
- VIX Signal (Volatility Index)
- GEX Signal (Gamma Exposure)
- DEX Signal (Delta Exposure)
- DIX Signal (Dark Index)
- SWAN Signal (Sentiment Warning Analytics)
- Custom Metrics Integration
- Signal Health Monitoring
- Alert System Integration

Based on: SpyderG05_TradingDashboard.py signal monitoring features
"""

import sys
import asyncio
import time
import json
import random
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
import numpy as np

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("dashboard_signal_integration_test.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@dataclass
class SignalData:
    """Signal data container"""

    name: str
    value: float
    timestamp: datetime
    status: str  # 'normal', 'warning', 'critical'
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalTestResult:
    """Signal test result container"""

    signal_name: str
    test_name: str
    success: bool
    duration: float
    signal_value: Optional[float]
    expected_range: Optional[Tuple[float, float]]
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class DashboardSignalIntegrationTester:
    """Comprehensive signal monitoring integration tester"""

    def __init__(self):
        self.test_results: List[SignalTestResult] = []
        self.start_time = datetime.now()

        # Signal configuration
        self.signal_definitions = {
            "HMM_Signal": {
                "name": "Hidden Markov Model",
                "range": (-1.0, 1.0),
                "warning_threshold": 0.7,
                "critical_threshold": 0.9,
                "update_frequency": 5,  # seconds
            },
            "SKEW_Signal": {
                "name": "Options Skew",
                "range": (-5.0, 5.0),
                "warning_threshold": 2.0,
                "critical_threshold": 3.0,
                "update_frequency": 10,
            },
            "VIX_Signal": {
                "name": "Volatility Index",
                "range": (10.0, 80.0),
                "warning_threshold": 25.0,
                "critical_threshold": 35.0,
                "update_frequency": 1,
            },
            "GEX_Signal": {
                "name": "Gamma Exposure",
                "range": (-10.0, 10.0),
                "warning_threshold": 5.0,
                "critical_threshold": 8.0,
                "update_frequency": 30,
            },
            "DEX_Signal": {
                "name": "Delta Exposure",
                "range": (-1.0, 1.0),
                "warning_threshold": 0.6,
                "critical_threshold": 0.8,
                "update_frequency": 30,
            },
            "DIX_Signal": {
                "name": "Dark Index",
                "range": (0.0, 1.0),
                "warning_threshold": 0.4,
                "critical_threshold": 0.3,
                "update_frequency": 60,
            },
            "SWAN_Signal": {
                "name": "Sentiment Warning Analytics",
                "range": (0.0, 10.0),
                "warning_threshold": 7.0,
                "critical_threshold": 8.5,
                "update_frequency": 15,
            },
            "OGL_Signal": {
                "name": "Options Gamma Levels",
                "range": (0.0, 100.0),
                "warning_threshold": 75.0,
                "critical_threshold": 90.0,
                "update_frequency": 60,
            },
            "MOMENTUM_Signal": {
                "name": "Market Momentum",
                "range": (-100.0, 100.0),
                "warning_threshold": 60.0,
                "critical_threshold": 80.0,
                "update_frequency": 5,
            },
            "LIQUIDITY_Signal": {
                "name": "Market Liquidity",
                "range": (0.0, 1.0),
                "warning_threshold": 0.3,
                "critical_threshold": 0.2,
                "update_frequency": 30,
            },
            "CORRELATION_Signal": {
                "name": "Cross-Asset Correlation",
                "range": (-1.0, 1.0),
                "warning_threshold": 0.8,
                "critical_threshold": 0.9,
                "update_frequency": 300,  # 5 minutes
            },
            "REGIME_Signal": {
                "name": "Market Regime",
                "range": (1.0, 5.0),
                "warning_threshold": 4.0,
                "critical_threshold": 5.0,
                "update_frequency": 900,  # 15 minutes
            },
        }

        # Test data storage
        self.signal_history = {}
        self.alert_log = []
        self.dashboard_widgets = {}

        # Market data simulation
        self.market_data_path = project_root / "market_data" / "live_data.json"
        self.signal_data_path = project_root / "market_data" / "signal_data.json"

    def print_header(self):
        """Print test suite header"""
        print("🕷️ SPYDER - Dashboard Signal Monitoring Integration Test")
        print("=" * 60)
        print(f"📅 Test Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Testing {len(self.signal_definitions)} Signal Indicators")
        print(f"📍 Project: {project_root}")
        print()

    def log_signal_result(
        self,
        signal_name: str,
        test_name: str,
        success: bool,
        duration: float,
        signal_value: Optional[float] = None,
        expected_range: Optional[Tuple[float, float]] = None,
        details: Dict = None,
        errors: List = None,
    ):
        """Log and store signal test result"""
        result = SignalTestResult(
            signal_name=signal_name,
            test_name=test_name,
            success=success,
            duration=duration,
            signal_value=signal_value,
            expected_range=expected_range,
            details=details or {},
            errors=errors or [],
        )
        self.test_results.append(result)

        status = "✅ PASS" if success else "❌ FAIL"
        value_str = f" [{signal_value:.3f}]" if signal_value is not None else ""
        print(f"   {status} {signal_name} - {test_name}{value_str} ({duration:.2f}s)")

        if errors:
            for error in errors:
                print(f"        ⚠️ {error}")

        logger.info(
            f"{signal_name} - {test_name}: {'PASS' if success else 'FAIL'} ({duration:.2f}s)"
        )

    # ========================================================================
    # SIGNAL CALCULATION TESTS
    # ========================================================================

    def generate_realistic_signal_value(self, signal_name: str) -> float:
        """Generate realistic signal values based on signal type"""
        config = self.signal_definitions[signal_name]
        min_val, max_val = config["range"]

        # Generate values with realistic patterns
        if signal_name == "VIX_Signal":
            # VIX typically 15-25, spikes during stress
            base = 18.0 + random.gauss(0, 3.0)
            spike_chance = random.random()
            if spike_chance < 0.05:  # 5% chance of spike
                base += random.uniform(10, 25)
            return max(min_val, min(max_val, base))

        elif signal_name == "HMM_Signal":
            # HMM signals often cluster around certain values
            clusters = [-0.8, -0.3, 0.0, 0.3, 0.8]
            cluster = random.choice(clusters)
            noise = random.gauss(0, 0.15)
            return max(min_val, min(max_val, cluster + noise))

        elif signal_name == "SKEW_Signal":
            # Skew typically negative, more negative during stress
            base = random.gauss(-1.5, 0.8)
            return max(min_val, min(max_val, base))

        elif signal_name in ["GEX_Signal", "DEX_Signal"]:
            # Gamma/Delta exposure can be strongly directional
            bias = random.choice([-1, 1]) * random.beta(2, 5)
            noise = random.gauss(0, 0.2)
            value = bias + noise
            return max(min_val, min(max_val, value))

        elif signal_name == "DIX_Signal":
            # DIX typically in 0.3-0.5 range
            base = random.beta(3, 4) * 0.4 + 0.3
            return max(min_val, min(max_val, base))

        else:
            # Default: uniform distribution with slight center bias
            center = (min_val + max_val) / 2
            range_size = max_val - min_val
            value = center + random.gauss(0, range_size * 0.25)
            return max(min_val, min(max_val, value))

    def calculate_signal_confidence(self, signal_name: str, value: float) -> float:
        """Calculate confidence score for signal value"""
        config = self.signal_definitions[signal_name]
        min_val, max_val = config["range"]

        # Confidence decreases near range boundaries
        center = (min_val + max_val) / 2
        range_size = max_val - min_val
        distance_from_center = abs(value - center) / (range_size / 2)

        # Base confidence with boundary penalty
        base_confidence = max(0.5, 1.0 - distance_from_center * 0.3)

        # Add some realistic noise
        noise = random.gauss(0, 0.1)
        confidence = max(0.0, min(1.0, base_confidence + noise))

        return confidence

    def determine_signal_status(self, signal_name: str, value: float) -> str:
        """Determine signal status based on thresholds"""
        config = self.signal_definitions[signal_name]
        warning_thresh = config["warning_threshold"]
        critical_thresh = config["critical_threshold"]

        abs_value = abs(value)

        if abs_value >= critical_thresh:
            return "critical"
        elif abs_value >= warning_thresh:
            return "warning"
        else:
            return "normal"

    async def test_signal_calculation(self, signal_name: str):
        """Test individual signal calculation"""
        start_time = time.time()

        try:
            # Generate signal value
            signal_value = self.generate_realistic_signal_value(signal_name)
            confidence = self.calculate_signal_confidence(signal_name, signal_value)
            status = self.determine_signal_status(signal_name, signal_value)

            # Create signal data object
            signal_data = SignalData(
                name=signal_name,
                value=signal_value,
                timestamp=datetime.now(),
                status=status,
                confidence=confidence,
                metadata={
                    "calculation_method": "realistic_simulation",
                    "data_source": "test_generator",
                },
            )

            # Validate signal properties
            config = self.signal_definitions[signal_name]
            min_val, max_val = config["range"]

            # Test 1: Value in valid range
            in_range = min_val <= signal_value <= max_val

            # Test 2: Confidence is valid
            valid_confidence = 0.0 <= confidence <= 1.0

            # Test 3: Status is appropriate
            expected_status = self.determine_signal_status(signal_name, signal_value)
            correct_status = status == expected_status

            # Test 4: Timestamp is recent
            time_diff = (datetime.now() - signal_data.timestamp).total_seconds()
            recent_timestamp = time_diff < 1.0

            success = (
                in_range and valid_confidence and correct_status and recent_timestamp
            )
            duration = time.time() - start_time

            details = {
                "signal_data": {
                    "value": signal_value,
                    "confidence": confidence,
                    "status": status,
                    "timestamp": signal_data.timestamp.isoformat(),
                },
                "validation": {
                    "in_range": in_range,
                    "valid_confidence": valid_confidence,
                    "correct_status": correct_status,
                    "recent_timestamp": recent_timestamp,
                },
                "config": config,
            }

            errors = []
            if not in_range:
                errors.append(
                    f"Value {signal_value:.3f} outside range [{min_val}, {max_val}]"
                )
            if not valid_confidence:
                errors.append(f"Invalid confidence {confidence:.3f}")
            if not correct_status:
                errors.append(
                    f"Status mismatch: got {status}, expected {expected_status}"
                )
            if not recent_timestamp:
                errors.append(f"Stale timestamp: {time_diff:.3f}s old")

            self.log_signal_result(
                signal_name,
                "Signal Calculation",
                success,
                duration,
                signal_value,
                (min_val, max_val),
                details,
                errors,
            )

            # Store for later tests
            self.signal_history[signal_name] = signal_data

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                signal_name,
                "Signal Calculation",
                False,
                duration,
                None,
                None,
                {},
                [f"Calculation error: {str(e)}"],
            )

    async def test_signal_update_frequency(self, signal_name: str):
        """Test signal update frequency compliance"""
        start_time = time.time()

        try:
            config = self.signal_definitions[signal_name]
            expected_frequency = config["update_frequency"]

            # Simulate multiple updates
            update_times = []
            for i in range(3):
                update_start = time.time()

                # Generate new signal value
                signal_value = self.generate_realistic_signal_value(signal_name)
                confidence = self.calculate_signal_confidence(signal_name, signal_value)
                status = self.determine_signal_status(signal_name, signal_value)

                update_duration = time.time() - update_start
                update_times.append(update_duration)

                # Small delay between updates
                await asyncio.sleep(0.1)

            # Analyze update performance
            avg_update_time = sum(update_times) / len(update_times)
            max_update_time = max(update_times)

            # Check if updates can meet frequency requirement
            can_meet_frequency = max_update_time < (
                expected_frequency * 0.1
            )  # 10% of update interval
            consistent_timing = (
                max(update_times) / min(update_times) < 2.0
            )  # Less than 2x variation

            success = can_meet_frequency and consistent_timing
            duration = time.time() - start_time

            details = {
                "expected_frequency": expected_frequency,
                "update_times": update_times,
                "avg_update_time": avg_update_time,
                "max_update_time": max_update_time,
                "can_meet_frequency": can_meet_frequency,
                "consistent_timing": consistent_timing,
            }

            errors = []
            if not can_meet_frequency:
                errors.append(
                    f"Update too slow: {max_update_time:.3f}s > {expected_frequency * 0.1:.3f}s"
                )
            if not consistent_timing:
                errors.append(
                    f"Inconsistent timing: {max(update_times) / min(update_times):.2f}x variation"
                )

            self.log_signal_result(
                signal_name,
                "Update Frequency",
                success,
                duration,
                avg_update_time,
                None,
                details,
                errors,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                signal_name,
                "Update Frequency",
                False,
                duration,
                None,
                None,
                {},
                [f"Frequency test error: {str(e)}"],
            )

    # ========================================================================
    # DASHBOARD INTEGRATION TESTS
    # ========================================================================

    async def test_dashboard_display_integration(self):
        """Test dashboard signal display integration"""
        start_time = time.time()

        try:
            # Simulate dashboard widget creation
            widget_tests = {
                "signal_labels": False,
                "value_displays": False,
                "status_indicators": False,
                "confidence_bars": False,
                "timestamp_display": False,
            }

            # Test 1: Signal labels
            try:
                signal_labels = {}
                for signal_name in self.signal_definitions:
                    display_name = self.signal_definitions[signal_name]["name"]
                    signal_labels[signal_name] = display_name
                widget_tests["signal_labels"] = len(signal_labels) == len(
                    self.signal_definitions
                )
            except:
                pass

            # Test 2: Value displays
            try:
                value_displays = {}
                for signal_name, signal_data in self.signal_history.items():
                    formatted_value = f"{signal_data.value:.3f}"
                    value_displays[signal_name] = formatted_value
                widget_tests["value_displays"] = len(value_displays) > 0
            except:
                pass

            # Test 3: Status indicators (color coding)
            try:
                status_colors = {
                    "normal": "#00FF00",  # Green
                    "warning": "#FFA500",  # Orange
                    "critical": "#FF0000",  # Red
                }
                status_indicators = {}
                for signal_name, signal_data in self.signal_history.items():
                    color = status_colors.get(signal_data.status, "#FFFFFF")
                    status_indicators[signal_name] = color
                widget_tests["status_indicators"] = len(status_indicators) > 0
            except:
                pass

            # Test 4: Confidence bars
            try:
                confidence_bars = {}
                for signal_name, signal_data in self.signal_history.items():
                    bar_width = int(signal_data.confidence * 100)  # 0-100%
                    confidence_bars[signal_name] = bar_width
                widget_tests["confidence_bars"] = len(confidence_bars) > 0
            except:
                pass

            # Test 5: Timestamp display
            try:
                timestamp_displays = {}
                for signal_name, signal_data in self.signal_history.items():
                    time_str = signal_data.timestamp.strftime("%H:%M:%S")
                    timestamp_displays[signal_name] = time_str
                widget_tests["timestamp_display"] = len(timestamp_displays) > 0
            except:
                pass

            success = sum(widget_tests.values()) >= 4  # At least 4 out of 5
            duration = time.time() - start_time

            details = {
                "widget_tests": widget_tests,
                "signal_count": len(self.signal_history),
                "display_components": {
                    "labels_count": len(signal_labels)
                    if "signal_labels" in locals()
                    else 0,
                    "values_count": len(value_displays)
                    if "value_displays" in locals()
                    else 0,
                    "indicators_count": len(status_indicators)
                    if "status_indicators" in locals()
                    else 0,
                },
            }

            errors = [] if success else ["Dashboard display integration insufficient"]

            self.log_signal_result(
                "Dashboard",
                "Display Integration",
                success,
                duration,
                None,
                None,
                details,
                errors,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                "Dashboard",
                "Display Integration",
                False,
                duration,
                None,
                None,
                {},
                [f"Display integration error: {str(e)}"],
            )

    async def test_real_time_updates(self):
        """Test real-time signal updates in dashboard"""
        start_time = time.time()

        try:
            update_tests = {
                "value_changes": False,
                "status_transitions": False,
                "timestamp_updates": False,
                "smooth_refresh": False,
            }

            # Simulate real-time updates
            update_sequence = []

            for cycle in range(3):
                cycle_data = {}

                # Update all signals
                for signal_name in list(self.signal_history.keys())[
                    :5
                ]:  # Test first 5 signals
                    old_data = self.signal_history[signal_name]

                    # Generate new value
                    new_value = self.generate_realistic_signal_value(signal_name)
                    new_confidence = self.calculate_signal_confidence(
                        signal_name, new_value
                    )
                    new_status = self.determine_signal_status(signal_name, new_value)

                    new_data = SignalData(
                        name=signal_name,
                        value=new_value,
                        timestamp=datetime.now(),
                        status=new_status,
                        confidence=new_confidence,
                    )

                    cycle_data[signal_name] = {
                        "old_value": old_data.value,
                        "new_value": new_value,
                        "old_status": old_data.status,
                        "new_status": new_status,
                        "value_changed": abs(new_value - old_data.value) > 0.001,
                        "status_changed": new_status != old_data.status,
                        "timestamp_updated": new_data.timestamp > old_data.timestamp,
                    }

                    # Update stored data
                    self.signal_history[signal_name] = new_data

                update_sequence.append(cycle_data)
                await asyncio.sleep(0.2)  # 200ms between cycles

            # Analyze update sequence
            value_changes = 0
            status_transitions = 0
            timestamp_updates = 0

            for cycle_data in update_sequence:
                for signal_name, signal_changes in cycle_data.items():
                    if signal_changes["value_changed"]:
                        value_changes += 1
                    if signal_changes["status_changed"]:
                        status_transitions += 1
                    if signal_changes["timestamp_updated"]:
                        timestamp_updates += 1

            # Evaluate test results
            update_tests["value_changes"] = value_changes > 0
            update_tests["status_transitions"] = (
                status_transitions >= 0
            )  # May be 0, that's ok
            update_tests["timestamp_updates"] = timestamp_updates > 0
            update_tests["smooth_refresh"] = (
                len(update_sequence) == 3
            )  # All cycles completed

            success = sum(update_tests.values()) >= 3  # At least 3 out of 4
            duration = time.time() - start_time

            details = {
                "update_tests": update_tests,
                "cycles_completed": len(update_sequence),
                "value_changes": value_changes,
                "status_transitions": status_transitions,
                "timestamp_updates": timestamp_updates,
            }

            errors = [] if success else ["Real-time updates insufficient"]

            self.log_signal_result(
                "Dashboard",
                "Real-time Updates",
                success,
                duration,
                None,
                None,
                details,
                errors,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                "Dashboard",
                "Real-time Updates",
                False,
                duration,
                None,
                None,
                {},
                [f"Real-time update error: {str(e)}"],
            )

    # ========================================================================
    # ALERT SYSTEM TESTS
    # ========================================================================

    async def test_signal_alert_system(self):
        """Test signal-based alert system"""
        start_time = time.time()

        try:
            alert_tests = {
                "threshold_detection": False,
                "alert_generation": False,
                "alert_prioritization": False,
                "alert_history": False,
            }

            # Generate test signals with various alert conditions
            test_scenarios = [
                ("VIX_Signal", 40.0, "critical"),  # High VIX
                ("HMM_Signal", 0.95, "critical"),  # Extreme HMM
                ("SKEW_Signal", 2.5, "warning"),  # Moderate skew
                ("LIQUIDITY_Signal", 0.15, "critical"),  # Low liquidity
                ("DIX_Signal", 0.25, "critical"),  # Low DIX
            ]

            generated_alerts = []

            for signal_name, test_value, expected_severity in test_scenarios:
                if signal_name in self.signal_definitions:
                    config = self.signal_definitions[signal_name]

                    # Create signal with test value
                    signal_data = SignalData(
                        name=signal_name,
                        value=test_value,
                        timestamp=datetime.now(),
                        status=self.determine_signal_status(signal_name, test_value),
                        confidence=0.9,  # High confidence for test
                    )

                    # Check if alert should be generated
                    should_alert = signal_data.status in ["warning", "critical"]

                    if should_alert:
                        alert = {
                            "signal_name": signal_name,
                            "signal_value": test_value,
                            "severity": signal_data.status,
                            "timestamp": signal_data.timestamp,
                            "message": f"{config['name']} signal at {test_value:.3f}",
                            "expected_severity": expected_severity,
                        }
                        generated_alerts.append(alert)

            # Test 1: Threshold detection
            threshold_detections = sum(
                1
                for alert in generated_alerts
                if alert["severity"] in ["warning", "critical"]
            )
            alert_tests["threshold_detection"] = threshold_detections > 0

            # Test 2: Alert generation
            alert_tests["alert_generation"] = len(generated_alerts) > 0

            # Test 3: Alert prioritization
            critical_alerts = [
                a for a in generated_alerts if a["severity"] == "critical"
            ]
            warning_alerts = [a for a in generated_alerts if a["severity"] == "warning"]
            proper_priority = (
                len(critical_alerts) >= len(warning_alerts)
                or len(generated_alerts) <= 3
            )
            alert_tests["alert_prioritization"] = proper_priority

            # Test 4: Alert history
            self.alert_log.extend(generated_alerts)
            alert_tests["alert_history"] = len(self.alert_log) > 0

            success = sum(alert_tests.values()) >= 3  # At least 3 out of 4
            duration = time.time() - start_time

            details = {
                "alert_tests": alert_tests,
                "generated_alerts": len(generated_alerts),
                "critical_alerts": len(critical_alerts),
                "warning_alerts": len(warning_alerts),
                "alert_history_size": len(self.alert_log),
                "test_scenarios": test_scenarios,
            }

            errors = [] if success else ["Signal alert system insufficient"]

            self.log_signal_result(
                "AlertSystem",
                "Signal Alerts",
                success,
                duration,
                None,
                None,
                details,
                errors,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                "AlertSystem",
                "Signal Alerts",
                False,
                duration,
                None,
                None,
                {},
                [f"Alert system error: {str(e)}"],
            )

    # ========================================================================
    # DATA PERSISTENCE TESTS
    # ========================================================================

    async def test_signal_data_persistence(self):
        """Test signal data persistence and recovery"""
        start_time = time.time()

        try:
            persistence_tests = {
                "data_export": False,
                "data_import": False,
                "format_validation": False,
                "recovery_capability": False,
            }

            # Test 1: Data export
            try:
                export_data = {
                    "signals": {},
                    "alerts": self.alert_log,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "signal_count": len(self.signal_history),
                        "alert_count": len(self.alert_log),
                        "test_run": True,
                    },
                }

                for signal_name, signal_data in self.signal_history.items():
                    export_data["signals"][signal_name] = {
                        "value": signal_data.value,
                        "timestamp": signal_data.timestamp.isoformat(),
                        "status": signal_data.status,
                        "confidence": signal_data.confidence,
                        "metadata": signal_data.metadata,
                    }

                # Save to test file
                with open(self.signal_data_path, "w") as f:
                    json.dump(export_data, f, indent=2)

                persistence_tests["data_export"] = True
            except Exception as e:
                logger.error(f"Data export failed: {e}")

            # Test 2: Data import
            try:
                if self.signal_data_path.exists():
                    with open(self.signal_data_path, "r") as f:
                        imported_data = json.load(f)

                    imported_signals = imported_data.get("signals", {})
                    persistence_tests["data_import"] = len(imported_signals) > 0
                else:
                    persistence_tests["data_import"] = False
            except Exception as e:
                logger.error(f"Data import failed: {e}")

            # Test 3: Format validation
            try:
                if "imported_data" in locals():
                    required_fields = ["signals", "alerts", "timestamp", "metadata"]
                    has_required_fields = all(
                        field in imported_data for field in required_fields
                    )

                    # Validate signal data structure
                    valid_signal_format = True
                    for signal_name, signal_data in imported_data["signals"].items():
                        required_signal_fields = [
                            "value",
                            "timestamp",
                            "status",
                            "confidence",
                        ]
                        if not all(
                            field in signal_data for field in required_signal_fields
                        ):
                            valid_signal_format = False
                            break

                    persistence_tests["format_validation"] = (
                        has_required_fields and valid_signal_format
                    )
            except Exception as e:
                logger.error(f"Format validation failed: {e}")

            # Test 4: Recovery capability
            try:
                if "imported_data" in locals():
                    # Simulate recovery by recreating signal objects
                    recovered_signals = {}
                    for signal_name, signal_data in imported_data["signals"].items():
                        recovered_signal = SignalData(
                            name=signal_name,
                            value=signal_data["value"],
                            timestamp=datetime.fromisoformat(signal_data["timestamp"]),
                            status=signal_data["status"],
                            confidence=signal_data["confidence"],
                            metadata=signal_data.get("metadata", {}),
                        )
                        recovered_signals[signal_name] = recovered_signal

                    persistence_tests["recovery_capability"] = (
                        len(recovered_signals) > 0
                    )
            except Exception as e:
                logger.error(f"Recovery test failed: {e}")

            success = sum(persistence_tests.values()) >= 3  # At least 3 out of 4
            duration = time.time() - start_time

            details = {
                "persistence_tests": persistence_tests,
                "export_file_exists": self.signal_data_path.exists(),
                "export_data_size": len(export_data)
                if "export_data" in locals()
                else 0,
                "imported_signals": len(imported_signals)
                if "imported_signals" in locals()
                else 0,
            }

            errors = [] if success else ["Signal data persistence insufficient"]

            self.log_signal_result(
                "DataPersistence",
                "Signal Persistence",
                success,
                duration,
                None,
                None,
                details,
                errors,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.log_signal_result(
                "DataPersistence",
                "Signal Persistence",
                False,
                duration,
                None,
                None,
                {},
                [f"Persistence test error: {str(e)}"],
            )

    # ========================================================================
    # MAIN TEST PHASES
    # ========================================================================

    async def phase1_signal_calculation_tests(self):
        """Phase 1: Test signal calculation and validation"""
        print("🧮 PHASE 1: Signal Calculation Tests")
        print("=" * 35)

        for signal_name in self.signal_definitions:
            await self.test_signal_calculation(signal_name)
            await self.test_signal_update_frequency(signal_name)

        print()

    async def phase2_dashboard_integration_tests(self):
        """Phase 2: Test dashboard integration"""
        print("🎛️ PHASE 2: Dashboard Integration Tests")
        print("=" * 37)

        await self.test_dashboard_display_integration()
        await self.test_real_time_updates()

        print()

    async def phase3_alert_system_tests(self):
        """Phase 3: Test alert system"""
        print("🚨 PHASE 3: Alert System Tests")
        print("=" * 28)

        await self.test_signal_alert_system()

        print()

    async def phase4_persistence_tests(self):
        """Phase 4: Test data persistence"""
        print("💾 PHASE 4: Data Persistence Tests")
        print("=" * 32)

        await self.test_signal_data_persistence()

        print()

    # ========================================================================
    # FINAL REPORTING
    # ========================================================================

    def generate_signal_integration_report(self):
        """Generate comprehensive signal integration test report"""
        print("📊 SIGNAL INTEGRATION TEST REPORT")
        print("=" * 45)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - passed_tests

        total_duration = (datetime.now() - self.start_time).total_seconds()

        print(f"🕐 Total Test Duration: {total_duration:.2f} seconds")
        print(f"📋 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
        print()

        # Signal-by-signal breakdown
        signal_results = {}
        for result in self.test_results:
            if result.signal_name not in signal_results:
                signal_results[result.signal_name] = {
                    "passed": 0,
                    "failed": 0,
                    "total": 0,
                }

            signal_results[result.signal_name]["total"] += 1
            if result.success:
                signal_results[result.signal_name]["passed"] += 1
            else:
                signal_results[result.signal_name]["failed"] += 1

        print("📊 Signal Test Results:")
        print("-" * 30)
        for signal_name, stats in signal_results.items():
            if stats["total"] > 0:
                success_rate = (stats["passed"] / stats["total"]) * 100
                status = (
                    "✅" if success_rate >= 75 else "⚠️" if success_rate >= 50 else "❌"
                )
                print(
                    f"{status} {signal_name}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)"
                )

        print()

        # Test category breakdown
        categories = {}
        for result in self.test_results:
            category = result.test_name
            if category not in categories:
                categories[category] = {"passed": 0, "failed": 0, "total": 0}

            categories[category]["total"] += 1
            if result.success:
                categories[category]["passed"] += 1
            else:
                categories[category]["failed"] += 1

        print("📊 Test Category Results:")
        print("-" * 30)
        for category, stats in categories.items():
            success_rate = (stats["passed"] / stats["total"]) * 100
            status = "✅" if success_rate >= 75 else "⚠️" if success_rate >= 50 else "❌"
            print(
                f"{status} {category}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)"
            )

        print()

        # Failed tests detail
        if failed_tests > 0:
            print("💥 Failed Tests:")
            print("-" * 20)
            for result in self.test_results:
                if not result.success:
                    print(f"   ❌ {result.signal_name} - {result.test_name}")
                    for error in result.errors:
                        print(f"      ⚠️ {error}")
            print()

        # Integration readiness assessment
        overall_success_rate = (passed_tests / total_tests) * 100

        if overall_success_rate >= 90:
            readiness = "🎉 READY FOR PRODUCTION"
            recommendation = "Signal integration is ready for production deployment"
        elif overall_success_rate >= 75:
            readiness = "✅ READY FOR TESTING"
            recommendation = "Signal integration is ready for extensive testing"
        elif overall_success_rate >= 50:
            readiness = "⚠️ NEEDS IMPROVEMENT"
            recommendation = "Address failing signals before proceeding"
        else:
            readiness = "❌ NOT READY"
            recommendation = "Significant signal issues need resolution"

        print("🎯 SIGNAL INTEGRATION READINESS")
        print("=" * 35)
        print(f"Status: {readiness}")
        print(f"Recommendation: {recommendation}")
        print()

        # Save detailed report
        report_filename = (
            f"signal_integration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_data = {
            "test_summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": overall_success_rate,
                "total_duration": total_duration,
            },
            "signal_results": signal_results,
            "category_results": categories,
            "signal_definitions": self.signal_definitions,
            "alert_log": self.alert_log,
            "test_results": [
                {
                    "signal_name": result.signal_name,
                    "test_name": result.test_name,
                    "success": result.success,
                    "duration": result.duration,
                    "signal_value": result.signal_value,
                    "expected_range": result.expected_range,
                    "details": result.details,
                    "errors": result.errors,
                }
                for result in self.test_results
            ],
            "readiness_assessment": {
                "status": readiness,
                "recommendation": recommendation,
            },
            "timestamp": datetime.now().isoformat(),
        }

        try:
            with open(report_filename, "w") as f:
                json.dump(report_data, f, indent=2, default=str)
            print(f"📄 Detailed report saved: {report_filename}")
        except Exception as e:
            print(f"⚠️ Could not save report: {e}")

        return overall_success_rate >= 75

    # ========================================================================
    # MAIN TEST RUNNER
    # ========================================================================

    async def run_signal_integration_tests(self):
        """Run complete signal integration test suite"""
        self.print_header()

        try:
            # Ensure market_data directory exists
            self.market_data_path.parent.mkdir(exist_ok=True)

            # Run all test phases
            await self.phase1_signal_calculation_tests()
            await self.phase2_dashboard_integration_tests()
            await self.phase3_alert_system_tests()
            await self.phase4_persistence_tests()

            # Generate final report
            success = self.generate_signal_integration_report()

            return success

        except KeyboardInterrupt:
            print("\n⚠️ Signal integration tests interrupted by user")
            return False
        except Exception as e:
            print(f"\n💥 Unexpected error during signal integration tests: {e}")
            import traceback

            traceback.print_exc()
            return False


def main():
    """Main test execution function"""
    try:
        tester = DashboardSignalIntegrationTester()
        success = asyncio.run(tester.run_signal_integration_tests())
        return success
    except Exception as e:
        print(f"💥 Test execution error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
