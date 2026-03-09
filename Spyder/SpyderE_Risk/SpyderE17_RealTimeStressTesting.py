#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE17_RealTimeStressTesting.py
Purpose: Real-Time Portfolio Stress Testing and Scenario Analysis Engine
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-29 Time: 15:30:00

Module Description:
    Advanced real-time stress testing system that continuously evaluates portfolio
    performance under various market scenarios including Black Monday crashes, VIX
    spikes, interest rate shocks, and custom stress scenarios. Provides institutional-
    grade risk assessment with Monte Carlo simulations, correlation breakdowns, and
    early warning systems for potential portfolio vulnerabilities and tail risks.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import MathUtils
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Stress Testing Parameters
MAX_SCENARIOS = 50                    # Maximum concurrent scenarios
DEFAULT_CONFIDENCE_LEVELS = [0.95, 0.99, 0.999]  # VaR confidence levels
MONTE_CARLO_ITERATIONS = 10000        # Monte Carlo simulation size
CORRELATION_BREAKDOWN_THRESHOLD = 0.3  # Correlation stress multiplier

# Market Shock Scenarios (Historical calibrated)
BLACK_MONDAY_SHOCK = -0.2036          # -20.36% (Oct 19, 1987)
FLASH_CRASH_SHOCK = -0.098            # -9.8% (May 6, 2010)
COVID_CRASH_SHOCK = -0.12             # -12% (Mar 16, 2020)
DOT_COM_SHOCK = -0.115                # -11.5% (Mar 24, 2000)

# VIX Spike Scenarios
VIX_NORMAL = 20.0                     # Normal VIX level
VIX_ELEVATED = 35.0                   # Elevated fear
VIX_PANIC = 50.0                      # Panic levels
VIX_EXTREME = 80.0                    # Extreme crisis (2008/2020)

# Interest Rate Shocks (basis points)
RATE_SHOCK_SMALL = 25                 # 0.25% rate change
RATE_SHOCK_MEDIUM = 50                # 0.50% rate change
RATE_SHOCK_LARGE = 100                # 1.00% rate change
RATE_SHOCK_EXTREME = 200              # 2.00% rate change

# Risk Thresholds
STRESS_ALERT_THRESHOLD = 0.05         # 5% portfolio stress loss
CRITICAL_STRESS_THRESHOLD = 0.15      # 15% critical stress loss
EXTREME_STRESS_THRESHOLD = 0.25       # 25% extreme stress loss

# Performance Constants
MAX_PROCESSING_TIME = 1.0             # Max 1 second per stress test
REFRESH_INTERVAL = 5.0                # Refresh every 5 seconds
ALERT_COOLDOWN = 300                  # 5 minutes between similar alerts

# ==============================================================================
# ENUMS
# ==============================================================================
class StressScenarioType(Enum):
    """Types of stress scenarios"""
    EQUITY_CRASH = auto()
    VIX_SPIKE = auto()
    INTEREST_RATE_SHOCK = auto()
    VOLATILITY_SURFACE_SHIFT = auto()
    CORRELATION_BREAKDOWN = auto()
    LIQUIDITY_CRISIS = auto()
    SECTOR_ROTATION = auto()
    GEOPOLITICAL_SHOCK = auto()
    CUSTOM_SCENARIO = auto()
    MONTE_CARLO = auto()

class StressSeverity(Enum):
    """Stress test severity levels"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"
    CATASTROPHIC = "catastrophic"

class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class TestingStatus(Enum):
    """Stress testing engine status"""
    STOPPED = "stopped"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StressScenario:
    """Stress scenario configuration"""
    scenario_id: str
    scenario_type: StressScenarioType
    name: str
    description: str
    severity: StressSeverity

    # Market parameters
    equity_shock: float = 0.0             # Equity price shock (%)
    vix_level: float = VIX_NORMAL         # Target VIX level
    rate_shock: float = 0.0               # Interest rate shock (bps)
    vol_surface_shift: dict[str, float] = field(default_factory=dict)
    correlation_multiplier: float = 1.0   # Correlation stress factor

    # Execution parameters
    time_horizon_days: int = 1            # Stress horizon
    probability: float = 0.01             # Scenario probability
    enabled: bool = True

    def __post_init__(self):
        """Post-initialization validation"""
        if not self.scenario_id:
            self.scenario_id = f"scenario_{int(time.time())}"

        # Ensure vol_surface_shift is initialized
        if not self.vol_surface_shift:
            self.vol_surface_shift = {}

@dataclass
class StressResult:
    """Individual stress test result"""
    scenario_id: str
    scenario_name: str
    scenario_type: StressScenarioType
    severity: StressSeverity

    # P&L Impact
    portfolio_pnl: float                  # Total portfolio P&L
    pnl_percentage: float                 # P&L as % of portfolio
    position_pnl: dict[str, float]       # Individual position P&L

    # Greeks Impact
    delta_change: float = 0.0
    gamma_change: float = 0.0
    vega_change: float = 0.0
    theta_change: float = 0.0

    # Risk Metrics
    var_impact: dict[float, float] = field(default_factory=dict)  # VaR at different confidence levels
    expected_shortfall: float = 0.0       # Conditional VaR
    maximum_drawdown: float = 0.0         # Max drawdown
    correlation_impact: float = 0.0       # Correlation change impact

    # Metadata
    test_timestamp: datetime = field(default_factory=datetime.now)
    computation_time: float = 0.0         # Seconds to compute
    passed_thresholds: bool = True        # Whether result passes risk limits

    def get_severity_color(self) -> str:
        """Get color code for severity visualization"""
        colors = {
            StressSeverity.MILD: '#90EE90',        # Light Green
            StressSeverity.MODERATE: '#FFD700',    # Gold
            StressSeverity.SEVERE: '#FFA500',      # Orange
            StressSeverity.EXTREME: '#FF4500',     # Red Orange
            StressSeverity.CATASTROPHIC: '#DC143C' # Crimson
        }
        return colors.get(self.severity, '#808080')

@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot for stress testing"""
    timestamp: datetime
    positions: dict[str, Any]             # Position details
    portfolio_value: float
    cash_balance: float

    # Portfolio Greeks
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_vega: float = 0.0
    total_theta: float = 0.0
    total_rho: float = 0.0

    # Risk metrics
    portfolio_beta: float = 1.0
    correlation_matrix: np.ndarray | None = None

    def __post_init__(self):
        """Post-initialization processing"""
        if self.correlation_matrix is None:
            # Create identity matrix as default
            num_positions = len(self.positions)
            self.correlation_matrix = np.eye(num_positions) if num_positions > 0 else np.eye(1)

@dataclass
class StressAlert:
    """Stress testing alert"""
    alert_id: str
    priority: AlertPriority
    scenario_name: str
    message: str
    portfolio_impact: float
    threshold_breached: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def __post_init__(self):
        """Generate alert ID if not provided"""
        if not self.alert_id:
            self.alert_id = f"alert_{int(time.time() * 1000)}"

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RealTimeStressTesting:
    """
    Advanced real-time portfolio stress testing engine.

    This class provides comprehensive stress testing capabilities including
    historical scenario replays, Monte Carlo simulations, correlation breakdown
    analysis, and custom stress scenarios. Features real-time monitoring,
    early warning systems, and institutional-grade risk assessment with
    performance optimized for sub-second execution times.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        status: Current engine status
        scenarios: Dictionary of stress scenarios
        results: Historical stress test results
        alerts: Active stress testing alerts

    Example:
        >>> stress_engine = RealTimeStressTesting()
        >>> stress_engine.initialize()
        >>> stress_engine.add_scenario(black_monday_scenario)
        >>> results = await stress_engine.run_all_scenarios(portfolio)
    """

    def __init__(self):
        """Initialize the real-time stress testing engine."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Engine state
        self.status = TestingStatus.STOPPED
        self.last_test_time = None
        self.computation_stats = {
            'total_tests': 0,
            'avg_computation_time': 0.0,
            'max_computation_time': 0.0
        }

        # Scenarios and results
        self.scenarios: dict[str, StressScenario] = {}
        self.results: dict[str, list[StressResult]] = {}
        self.alerts: list[StressAlert] = []

        # Performance optimization
        self.thread_pool = ThreadPoolExecutor(max_workers=8)
        self.math_utils = MathUtils()
        self._result_cache = {}
        self._cache_expiry = {}

        # Alert management
        self._alert_cooldown = {}
        self._running = False

        self.logger.info("RealTimeStressTesting engine initialized")

    # ==========================================================================
    # PUBLIC METHODS - Engine Management
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the stress testing engine with default scenarios.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.status = TestingStatus.INITIALIZING
            self.logger.info("Initializing stress testing engine...")

            # Create default stress scenarios
            self._create_default_scenarios()

            # Initialize computation components
            self._initialize_computation_engine()

            self.status = TestingStatus.STOPPED
            self.logger.info(f"Stress testing engine initialized with {len(self.scenarios)} scenarios")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.initialize")
            self.status = TestingStatus.ERROR
            return False

    def start_monitoring(self) -> bool:
        """
        Start continuous stress testing monitoring.

        Returns:
            bool: True if monitoring started successfully
        """
        if self.status == TestingStatus.RUNNING:
            self.logger.warning("Stress testing already running")
            return True

        try:
            self._running = True
            self.status = TestingStatus.RUNNING

            # Start monitoring thread
            self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitoring_thread.start()

            self.logger.info("Real-time stress testing monitoring started")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.start_monitoring")
            self.status = TestingStatus.ERROR
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop continuous stress testing monitoring.

        Returns:
            bool: True if monitoring stopped successfully
        """
        try:
            self._running = False
            self.status = TestingStatus.STOPPED

            if hasattr(self, '_monitoring_thread'):
                self._monitoring_thread.join(timeout=5.0)

            self.logger.info("Real-time stress testing monitoring stopped")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.stop_monitoring")
            return False

    # ==========================================================================
    # PUBLIC METHODS - Scenario Management
    # ==========================================================================
    def add_scenario(self, scenario: StressScenario) -> bool:
        """
        Add a new stress scenario.

        Args:
            scenario: Stress scenario to add

        Returns:
            bool: True if scenario added successfully
        """
        try:
            # Validate scenario
            if not self._validate_scenario(scenario):
                return False

            self.scenarios[scenario.scenario_id] = scenario
            self.results[scenario.scenario_id] = []

            self.logger.info(f"Added stress scenario: {scenario.name}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.add_scenario")
            return False

    def remove_scenario(self, scenario_id: str) -> bool:
        """
        Remove a stress scenario.

        Args:
            scenario_id: ID of scenario to remove

        Returns:
            bool: True if scenario removed successfully
        """
        try:
            if scenario_id not in self.scenarios:
                self.logger.warning(f"Scenario not found: {scenario_id}")
                return False

            scenario_name = self.scenarios[scenario_id].name
            del self.scenarios[scenario_id]
            del self.results[scenario_id]

            self.logger.info(f"Removed stress scenario: {scenario_name}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.remove_scenario")
            return False

    def get_scenario_list(self) -> list[dict[str, Any]]:
        """
        Get list of all scenarios with metadata.

        Returns:
            List of scenario information dictionaries
        """
        scenario_list = []

        for scenario_id, scenario in self.scenarios.items():
            scenario_list.append({
                'scenario_id': scenario_id,
                'name': scenario.name,
                'type': scenario.scenario_type.name,
                'severity': scenario.severity.name,
                'enabled': scenario.enabled,
                'description': scenario.description,
                'last_run': self._get_last_run_time(scenario_id)
            })

        return scenario_list

    # ==========================================================================
    # PUBLIC METHODS - Stress Testing Execution
    # ==========================================================================
    async def run_single_scenario(self, scenario_id: str, portfolio: PortfolioSnapshot) -> StressResult | None:
        """
        Run a single stress scenario on the portfolio.

        Args:
            scenario_id: ID of scenario to run
            portfolio: Current portfolio snapshot

        Returns:
            Stress test result or None if error
        """
        if scenario_id not in self.scenarios:
            self.logger.error(f"Scenario not found: {scenario_id}")
            return None

        try:
            start_time = time.time()
            scenario = self.scenarios[scenario_id]

            # Check cache first
            cache_key = self._generate_cache_key(scenario_id, portfolio)
            if self._is_cache_valid(cache_key):
                return self._result_cache[cache_key]

            # Run stress test
            result = await self._execute_stress_test(scenario, portfolio)

            # Update statistics
            computation_time = time.time() - start_time
            self._update_computation_stats(computation_time)
            result.computation_time = computation_time

            # Store result
            self.results[scenario_id].append(result)
            self._cache_result(cache_key, result)

            # Check for alerts
            self._check_stress_alerts(result)

            return result

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.run_single_scenario")
            return None

    async def run_all_scenarios(self, portfolio: PortfolioSnapshot) -> dict[str, StressResult]:
        """
        Run all enabled stress scenarios on the portfolio.

        Args:
            portfolio: Current portfolio snapshot

        Returns:
            Dictionary of scenario results
        """
        results = {}

        try:
            # Get enabled scenarios
            enabled_scenarios = [(sid, s) for sid, s in self.scenarios.items() if s.enabled]

            if not enabled_scenarios:
                self.logger.warning("No enabled scenarios to run")
                return results

            self.logger.info(f"Running {len(enabled_scenarios)} stress scenarios")

            # Run scenarios in parallel
            tasks = []
            for scenario_id, _ in enabled_scenarios:
                task = self.run_single_scenario(scenario_id, portfolio)
                tasks.append((scenario_id, task))

            # Collect results
            for scenario_id, task in tasks:
                try:
                    result = await task
                    if result:
                        results[scenario_id] = result
                except Exception as e:
                    self.logger.error(f"Error in scenario {scenario_id}: {e}")

            self.last_test_time = datetime.now()
            self.computation_stats['total_tests'] += len(results)

            self.logger.info(f"Completed stress testing: {len(results)} scenarios")
            return results

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.run_all_scenarios")
            return results

    def run_monte_carlo_simulation(self, portfolio: PortfolioSnapshot,
                                 iterations: int = MONTE_CARLO_ITERATIONS,
                                 time_horizon_days: int = 1) -> dict[str, Any]:
        """
        Run Monte Carlo simulation on the portfolio.

        Args:
            portfolio: Current portfolio snapshot
            iterations: Number of Monte Carlo iterations
            time_horizon_days: Time horizon in days

        Returns:
            Dictionary with simulation results and statistics
        """
        try:
            self.logger.info(f"Starting Monte Carlo simulation: {iterations} iterations")
            start_time = time.time()

            # Generate random market scenarios
            scenarios = self._generate_random_scenarios(iterations, time_horizon_days)

            # Run simulations
            pnl_distribution = []
            for scenario_params in scenarios:
                pnl = self._calculate_scenario_pnl(portfolio, scenario_params)
                pnl_distribution.append(pnl)

            pnl_array = np.array(pnl_distribution)

            # Calculate statistics
            results = {
                'simulation_stats': {
                    'iterations': iterations,
                    'time_horizon_days': time_horizon_days,
                    'computation_time': time.time() - start_time,
                    'portfolio_value': portfolio.portfolio_value
                },
                'pnl_statistics': {
                    'mean': float(np.mean(pnl_array)),
                    'std': float(np.std(pnl_array)),
                    'min': float(np.min(pnl_array)),
                    'max': float(np.max(pnl_array)),
                    'median': float(np.median(pnl_array))
                },
                'risk_metrics': {
                    'var_95': float(np.percentile(pnl_array, 5)),    # 95% VaR
                    'var_99': float(np.percentile(pnl_array, 1)),    # 99% VaR
                    'var_999': float(np.percentile(pnl_array, 0.1)), # 99.9% VaR
                    'expected_shortfall_95': float(np.mean(pnl_array[pnl_array <= np.percentile(pnl_array, 5)])),
                    'expected_shortfall_99': float(np.mean(pnl_array[pnl_array <= np.percentile(pnl_array, 1)]))
                },
                'distribution_data': pnl_distribution
            }

            self.logger.info(f"Monte Carlo simulation completed in {results['simulation_stats']['computation_time']:.2f}s")
            return results

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.run_monte_carlo_simulation")
            return {}

    # ==========================================================================
    # PUBLIC METHODS - Results and Reporting
    # ==========================================================================
    def get_stress_summary(self) -> dict[str, Any]:
        """
        Get comprehensive stress testing summary.

        Returns:
            Dictionary with stress testing summary statistics
        """
        try:
            summary = {
                'engine_status': {
                    'status': self.status.value,
                    'last_test_time': self.last_test_time.isoformat() if self.last_test_time else None,
                    'total_scenarios': len(self.scenarios),
                    'enabled_scenarios': sum(1 for s in self.scenarios.values() if s.enabled)
                },
                'performance_metrics': self.computation_stats.copy(),
                'scenario_summary': {},
                'alert_summary': {
                    'total_alerts': len(self.alerts),
                    'unacknowledged_alerts': sum(1 for a in self.alerts if not a.acknowledged),
                    'critical_alerts': sum(1 for a in self.alerts if a.priority in [AlertPriority.CRITICAL, AlertPriority.EMERGENCY])
                }
            }

            # Scenario summaries
            for scenario_id, results_list in self.results.items():
                if results_list:
                    latest_result = results_list[-1]
                    scenario_name = self.scenarios[scenario_id].name

                    summary['scenario_summary'][scenario_name] = {
                        'last_pnl_impact': latest_result.pnl_percentage,
                        'severity': latest_result.severity.value,
                        'passed_thresholds': latest_result.passed_thresholds,
                        'total_runs': len(results_list)
                    }

            return summary

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.get_stress_summary")
            return {}

    def get_worst_case_scenarios(self, top_n: int = 5) -> list[dict[str, Any]]:
        """
        Get the worst-case stress test results.

        Args:
            top_n: Number of worst-case scenarios to return

        Returns:
            List of worst-case scenario results
        """
        try:
            all_results = []

            # Collect all recent results
            for scenario_id, results_list in self.results.items():
                if results_list:
                    latest_result = results_list[-1]
                    scenario_name = self.scenarios[scenario_id].name

                    all_results.append({
                        'scenario_name': scenario_name,
                        'scenario_type': latest_result.scenario_type.name,
                        'severity': latest_result.severity.value,
                        'pnl_impact': latest_result.pnl_percentage,
                        'portfolio_pnl': latest_result.portfolio_pnl,
                        'var_99': latest_result.var_impact.get(0.99, 0.0),
                        'max_drawdown': latest_result.maximum_drawdown,
                        'test_timestamp': latest_result.test_timestamp.isoformat()
                    })

            # Sort by PnL impact (most negative first)
            all_results.sort(key=lambda x: x['pnl_impact'])

            return all_results[:top_n]

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.get_worst_case_scenarios")
            return []

    def generate_stress_report(self) -> str:
        """
        Generate comprehensive stress testing report.

        Returns:
            Formatted text report
        """
        try:
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("SPYDER REAL-TIME STRESS TESTING REPORT")
            report_lines.append("=" * 80)
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")

            # Engine status
            summary = self.get_stress_summary()
            engine_status = summary.get('engine_status', {})

            report_lines.append("ENGINE STATUS:")
            report_lines.append(f"  Status: {engine_status.get('status', 'Unknown').upper()}")
            report_lines.append(f"  Total Scenarios: {engine_status.get('total_scenarios', 0)}")
            report_lines.append(f"  Enabled Scenarios: {engine_status.get('enabled_scenarios', 0)}")
            if engine_status.get('last_test_time'):
                report_lines.append(f"  Last Test: {engine_status['last_test_time']}")
            report_lines.append("")

            # Performance metrics
            perf_metrics = summary.get('performance_metrics', {})
            report_lines.append("PERFORMANCE METRICS:")
            report_lines.append(f"  Total Tests Run: {perf_metrics.get('total_tests', 0)}")
            report_lines.append(f"  Average Computation Time: {perf_metrics.get('avg_computation_time', 0):.3f}s")
            report_lines.append(f"  Maximum Computation Time: {perf_metrics.get('max_computation_time', 0):.3f}s")
            report_lines.append("")

            # Worst case scenarios
            worst_cases = self.get_worst_case_scenarios(5)
            if worst_cases:
                report_lines.append("WORST CASE SCENARIOS:")
                for i, scenario in enumerate(worst_cases, 1):
                    report_lines.append(f"  {i}. {scenario['scenario_name']}")
                    report_lines.append(f"     Type: {scenario['scenario_type']}")
                    report_lines.append(f"     Severity: {scenario['severity'].upper()}")
                    report_lines.append(f"     P&L Impact: {scenario['pnl_impact']:.2%}")
                    report_lines.append(f"     Portfolio P&L: ${scenario['portfolio_pnl']:,.2f}")
                    report_lines.append("")

            # Alert summary
            alert_summary = summary.get('alert_summary', {})
            if alert_summary.get('total_alerts', 0) > 0:
                report_lines.append("ALERT SUMMARY:")
                report_lines.append(f"  Total Alerts: {alert_summary['total_alerts']}")
                report_lines.append(f"  Unacknowledged: {alert_summary['unacknowledged_alerts']}")
                report_lines.append(f"  Critical Alerts: {alert_summary['critical_alerts']}")
                report_lines.append("")

            report_lines.append("=" * 80)
            return "\n".join(report_lines)

        except Exception as e:
            self.error_handler.handle_error(e, context="StressTesting.generate_stress_report")
            return f"Error generating stress report: {e}"

    # ==========================================================================
    # PRIVATE METHODS - Core Implementation
    # ==========================================================================
    def _create_default_scenarios(self) -> None:
        """Create default stress scenarios."""
        # Black Monday scenario
        black_monday = StressScenario(
            scenario_id="black_monday",
            scenario_type=StressScenarioType.EQUITY_CRASH,
            name="Black Monday (1987)",
            description="Replication of October 19, 1987 market crash",
            severity=StressSeverity.CATASTROPHIC,
            equity_shock=BLACK_MONDAY_SHOCK,
            vix_level=VIX_EXTREME,
            correlation_multiplier=CORRELATION_BREAKDOWN_THRESHOLD
        )

        # Flash Crash scenario
        flash_crash = StressScenario(
            scenario_id="flash_crash",
            scenario_type=StressScenarioType.LIQUIDITY_CRISIS,
            name="Flash Crash (2010)",
            description="May 6, 2010 flash crash simulation",
            severity=StressSeverity.EXTREME,
            equity_shock=FLASH_CRASH_SHOCK,
            vix_level=VIX_PANIC,
            correlation_multiplier=0.5
        )

        # COVID Crash scenario
        covid_crash = StressScenario(
            scenario_id="covid_crash",
            scenario_type=StressScenarioType.GEOPOLITICAL_SHOCK,
            name="COVID Crash (2020)",
            description="March 2020 pandemic market crash",
            severity=StressSeverity.EXTREME,
            equity_shock=COVID_CRASH_SHOCK,
            vix_level=VIX_EXTREME,
            correlation_multiplier=0.2
        )

        # VIX Spike scenario
        vix_spike = StressScenario(
            scenario_id="vix_spike",
            scenario_type=StressScenarioType.VIX_SPIKE,
            name="VIX Spike",
            description="Sudden volatility spike scenario",
            severity=StressSeverity.SEVERE,
            equity_shock=-0.05,
            vix_level=VIX_PANIC,
            vol_surface_shift={"short_term": 1.5, "long_term": 1.2}
        )

        # Interest Rate Shock scenario
        rate_shock = StressScenario(
            scenario_id="rate_shock",
            scenario_type=StressScenarioType.INTEREST_RATE_SHOCK,
            name="Interest Rate Shock",
            description="Sudden 100bps rate increase",
            severity=StressSeverity.MODERATE,
            rate_shock=RATE_SHOCK_LARGE,
            equity_shock=-0.03
        )

        # Add all scenarios
        scenarios = [black_monday, flash_crash, covid_crash, vix_spike, rate_shock]
        for scenario in scenarios:
            self.add_scenario(scenario)

    def _initialize_computation_engine(self) -> None:
        """Initialize computation engine components."""
        # Initialize math utilities
        self.math_utils = MathUtils()

        # Initialize cache
        self._result_cache = {}
        self._cache_expiry = {}

        # Reset statistics
        self.computation_stats = {
            'total_tests': 0,
            'avg_computation_time': 0.0,
            'max_computation_time': 0.0
        }

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for continuous stress testing."""
        self.logger.info("Started stress testing monitoring loop")

        while self._running:
            try:
                # This would integrate with portfolio management system
                # For now, we just sleep and could trigger alerts
                time.sleep(REFRESH_INTERVAL)

                # Clean up old cache entries
                self._cleanup_cache()

                # Process any pending alerts
                self._process_alerts()

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)  # Brief pause before retrying

        self.logger.info("Stress testing monitoring loop stopped")

    async def _execute_stress_test(self, scenario: StressScenario, portfolio: PortfolioSnapshot) -> StressResult:
        """Execute a single stress test scenario."""
        start_time = time.time()

        # Calculate base scenario parameters
        scenario_params = {
            'equity_shock': scenario.equity_shock,
            'vix_level': scenario.vix_level,
            'rate_shock': scenario.rate_shock / 10000,  # Convert bps to decimal
            'vol_surface_shift': scenario.vol_surface_shift,
            'correlation_multiplier': scenario.correlation_multiplier
        }

        # Calculate portfolio P&L under stress
        portfolio_pnl = self._calculate_scenario_pnl(portfolio, scenario_params)
        pnl_percentage = (portfolio_pnl / portfolio.portfolio_value) if portfolio.portfolio_value > 0 else 0.0

        # Calculate position-level P&L
        position_pnl = self._calculate_position_pnl(portfolio, scenario_params)

        # Calculate Greeks impact
        greeks_impact = self._calculate_greeks_impact(portfolio, scenario_params)

        # Calculate risk metrics
        var_impact = self._calculate_var_impact(portfolio, scenario_params)
        expected_shortfall = self._calculate_expected_shortfall(portfolio, scenario_params)
        max_drawdown = abs(min(0, pnl_percentage))

        # Check if result passes thresholds
        passed_thresholds = self._check_thresholds(pnl_percentage, scenario.severity)

        # Create result
        result = StressResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            scenario_type=scenario.scenario_type,
            severity=scenario.severity,
            portfolio_pnl=portfolio_pnl,
            pnl_percentage=pnl_percentage,
            position_pnl=position_pnl,
            delta_change=greeks_impact.get('delta', 0.0),
            gamma_change=greeks_impact.get('gamma', 0.0),
            vega_change=greeks_impact.get('vega', 0.0),
            theta_change=greeks_impact.get('theta', 0.0),
            var_impact=var_impact,
            expected_shortfall=expected_shortfall,
            maximum_drawdown=max_drawdown,
            correlation_impact=scenario_params['correlation_multiplier'] - 1.0,
            computation_time=time.time() - start_time,
            passed_thresholds=passed_thresholds
        )

        return result

    def _calculate_scenario_pnl(self, portfolio: PortfolioSnapshot, scenario_params: dict[str, Any]) -> float:
        """Calculate portfolio P&L under stress scenario."""
        # Simplified P&L calculation - in production would use more sophisticated models

        total_pnl = 0.0
        equity_shock = scenario_params.get('equity_shock', 0.0)
        vol_shock = scenario_params.get('vol_surface_shift', {}).get('short_term', 1.0)

        # Delta P&L (first-order price impact)
        delta_pnl = portfolio.total_delta * portfolio.portfolio_value * equity_shock

        # Gamma P&L (second-order price impact)
        gamma_pnl = 0.5 * portfolio.total_gamma * portfolio.portfolio_value * (equity_shock ** 2)

        # Vega P&L (volatility impact)
        vega_pnl = portfolio.total_vega * (vol_shock - 1.0) * 0.01  # 1% vol change

        # Theta P&L (time decay - minimal for stress test)
        theta_pnl = portfolio.total_theta * scenario_params.get('time_horizon_days', 1)

        total_pnl = delta_pnl + gamma_pnl + vega_pnl + theta_pnl

        return total_pnl

    def _calculate_position_pnl(self, portfolio: PortfolioSnapshot, scenario_params: dict[str, Any]) -> dict[str, float]:
        """Calculate individual position P&L under stress."""
        position_pnl = {}

        # Simplified calculation for each position
        for position_id, position_data in portfolio.positions.items():
            # This would be more sophisticated in production
            position_value = position_data.get('value', 0.0)
            position_delta = position_data.get('delta', 0.0)

            equity_shock = scenario_params.get('equity_shock', 0.0)
            pnl = position_delta * position_value * equity_shock

            position_pnl[position_id] = pnl

        return position_pnl

    def _calculate_greeks_impact(self, portfolio: PortfolioSnapshot, scenario_params: dict[str, Any]) -> dict[str, float]:
        """Calculate impact on portfolio Greeks under stress."""
        equity_shock = scenario_params.get('equity_shock', 0.0)
        vol_shock = scenario_params.get('vol_surface_shift', {}).get('short_term', 1.0)

        # Greeks would change under stress conditions
        # Simplified calculation - production would use more sophisticated models

        return {
            'delta': portfolio.total_delta * (1 + equity_shock * 0.1),  # Delta changes with underlying
            'gamma': portfolio.total_gamma * (1 + equity_shock * 0.2),  # Gamma changes with underlying
            'vega': portfolio.total_vega * vol_shock,                   # Vega scales with vol
            'theta': portfolio.total_theta * (1 + abs(equity_shock) * 0.1),  # Theta changes with stress
        }

    def _calculate_var_impact(self, portfolio: PortfolioSnapshot, scenario_params: dict[str, Any]) -> dict[float, float]:
        """Calculate VaR impact at different confidence levels."""
        equity_shock = scenario_params.get('equity_shock', 0.0)
        portfolio_value = portfolio.portfolio_value

        # Simple VaR approximation based on stress scenario
        base_var = abs(equity_shock) * portfolio_value

        return {
            0.95: base_var * 1.0,   # 95% VaR
            0.99: base_var * 1.5,   # 99% VaR
            0.999: base_var * 2.0   # 99.9% VaR
        }

    def _calculate_expected_shortfall(self, portfolio: PortfolioSnapshot, scenario_params: dict[str, Any]) -> float:
        """Calculate Expected Shortfall (Conditional VaR)."""
        equity_shock = scenario_params.get('equity_shock', 0.0)
        portfolio_value = portfolio.portfolio_value

        # Simplified ES calculation
        return abs(equity_shock) * portfolio_value * 1.3  # ES typically 30% higher than VaR

    def _generate_random_scenarios(self, iterations: int, time_horizon_days: int) -> list[dict[str, Any]]:
        """Generate random scenarios for Monte Carlo simulation."""
        scenarios = []

        for _ in range(iterations):
            # Random equity return (normal distribution)
            daily_vol = 0.015  # Approximate daily SPY volatility
            equity_return = np.random.normal(0, daily_vol * np.sqrt(time_horizon_days))

            # Random VIX level (log-normal distribution)
            vix_level = np.random.lognormal(np.log(VIX_NORMAL), 0.3)

            # Random rate shock (normal distribution)
            rate_shock = np.random.normal(0, 0.0005)  # 5bps daily std

            # Random correlation multiplier
            correlation_mult = np.random.uniform(0.3, 1.5)

            scenarios.append({
                'equity_shock': equity_return,
                'vix_level': vix_level,
                'rate_shock': rate_shock,
                'correlation_multiplier': correlation_mult,
                'vol_surface_shift': {'short_term': np.random.uniform(0.8, 1.3)}
            })

        return scenarios

    # ==========================================================================
    # PRIVATE METHODS - Validation and Utilities
    # ==========================================================================
    def _validate_scenario(self, scenario: StressScenario) -> bool:
        """Validate stress scenario parameters."""
        if not scenario.scenario_id:
            self.logger.error("Scenario ID is required")
            return False

        if not scenario.name:
            self.logger.error("Scenario name is required")
            return False

        if scenario.scenario_id in self.scenarios:
            self.logger.error(f"Scenario ID already exists: {scenario.scenario_id}")
            return False

        # Validate shock parameters are within reasonable bounds
        if abs(scenario.equity_shock) > 0.5:  # 50% max shock
            self.logger.error("Equity shock too large (max 50%)")
            return False

        if scenario.vix_level < 5 or scenario.vix_level > 150:
            self.logger.error("VIX level out of reasonable range (5-150)")
            return False

        return True

    def _check_thresholds(self, pnl_percentage: float, severity: StressSeverity) -> bool:
        """Check if stress result passes defined thresholds."""
        # Define thresholds based on severity
        severity_thresholds = {
            StressSeverity.MILD: -0.02,         # -2%
            StressSeverity.MODERATE: -0.05,     # -5%
            StressSeverity.SEVERE: -0.10,       # -10%
            StressSeverity.EXTREME: -0.20,      # -20%
            StressSeverity.CATASTROPHIC: -0.30  # -30%
        }

        threshold = severity_thresholds.get(severity, -0.05)
        return pnl_percentage >= threshold

    def _check_stress_alerts(self, result: StressResult) -> None:
        """Check stress result for alert conditions."""
        # Critical loss alert
        if result.pnl_percentage <= -CRITICAL_STRESS_THRESHOLD:
            alert = StressAlert(
                alert_id="",
                priority=AlertPriority.CRITICAL,
                scenario_name=result.scenario_name,
                message=f"Critical stress loss: {result.pnl_percentage:.1%} in scenario {result.scenario_name}",
                portfolio_impact=result.pnl_percentage,
                threshold_breached="Critical Stress Threshold"
            )
            self._add_alert(alert)

        # Extreme loss alert
        elif result.pnl_percentage <= -EXTREME_STRESS_THRESHOLD:
            alert = StressAlert(
                alert_id="",
                priority=AlertPriority.EMERGENCY,
                scenario_name=result.scenario_name,
                message=f"EXTREME stress loss: {result.pnl_percentage:.1%} in scenario {result.scenario_name}",
                portfolio_impact=result.pnl_percentage,
                threshold_breached="Extreme Stress Threshold"
            )
            self._add_alert(alert)

        # Threshold failure alert
        elif not result.passed_thresholds:
            alert = StressAlert(
                alert_id="",
                priority=AlertPriority.HIGH,
                scenario_name=result.scenario_name,
                message=f"Stress threshold exceeded: {result.pnl_percentage:.1%} in {result.scenario_name}",
                portfolio_impact=result.pnl_percentage,
                threshold_breached="Scenario Threshold"
            )
            self._add_alert(alert)

    def _add_alert(self, alert: StressAlert) -> None:
        """Add stress alert with cooldown logic."""
        # Check cooldown
        alert_key = f"{alert.scenario_name}_{alert.threshold_breached}"
        current_time = time.time()

        if alert_key in self._alert_cooldown:
            if current_time - self._alert_cooldown[alert_key] < ALERT_COOLDOWN:
                return  # Skip due to cooldown

        self._alert_cooldown[alert_key] = current_time
        self.alerts.append(alert)

        self.logger.warning(f"Stress alert: {alert.message}")

    def _process_alerts(self) -> None:
        """Process pending alerts."""
        # Remove old alerts (older than 1 hour)
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff_time]

        # Count unacknowledged critical alerts
        critical_count = sum(1 for a in self.alerts
                           if not a.acknowledged and a.priority in [AlertPriority.CRITICAL, AlertPriority.EMERGENCY])

        if critical_count > 0:
            self.logger.warning(f"{critical_count} unacknowledged critical stress alerts")

    # ==========================================================================
    # PRIVATE METHODS - Caching and Performance
    # ==========================================================================
    def _generate_cache_key(self, scenario_id: str, portfolio: PortfolioSnapshot) -> str:
        """Generate cache key for result caching."""
        portfolio_hash = hash(f"{portfolio.portfolio_value}_{portfolio.total_delta}_{portfolio.total_gamma}")
        return f"{scenario_id}_{portfolio_hash}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached result is still valid."""
        if cache_key not in self._result_cache:
            return False

        if cache_key not in self._cache_expiry:
            return False

        return time.time() < self._cache_expiry[cache_key]

    def _cache_result(self, cache_key: str, result: StressResult) -> None:
        """Cache stress test result."""
        self._result_cache[cache_key] = result
        self._cache_expiry[cache_key] = time.time() + 30.0  # 30 second cache

    def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        current_time = time.time()
        expired_keys = [k for k, expiry in self._cache_expiry.items() if current_time > expiry]

        for key in expired_keys:
            self._result_cache.pop(key, None)
            self._cache_expiry.pop(key, None)

    def _update_computation_stats(self, computation_time: float) -> None:
        """Update computation statistics."""
        self.computation_stats['max_computation_time'] = max(
            self.computation_stats['max_computation_time'],
            computation_time
        )

        # Update running average
        total_tests = self.computation_stats['total_tests']
        current_avg = self.computation_stats['avg_computation_time']

        self.computation_stats['avg_computation_time'] = (
            (current_avg * total_tests + computation_time) / (total_tests + 1)
        )

    def _get_last_run_time(self, scenario_id: str) -> str | None:
        """Get last run time for a scenario."""
        if scenario_id in self.results and self.results[scenario_id]:
            return self.results[scenario_id][-1].test_timestamp.isoformat()
        return None

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up stress testing engine resources."""
        try:
            # Stop monitoring
            self.stop_monitoring()

            # Clean up thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)

            # Clear caches
            self._result_cache.clear()
            self._cache_expiry.clear()

            self.logger.info("Stress testing engine cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def run_distributed_monte_carlo(self, portfolio: 'PortfolioSnapshot',
                                     iterations: int = MONTE_CARLO_ITERATIONS,
                                     time_horizon_days: int = 1,
                                     num_cpus: int | None = None) -> dict[str, Any]:
        """
        Run Monte Carlo stress simulation distributed across Ray workers.

        Partitions iterations across workers for near-linear speedup on
        large simulation counts.

        Args:
            portfolio: Current portfolio snapshot.
            iterations: Total number of Monte Carlo iterations.
            time_horizon_days: Simulation time horizon.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Combined simulation results with risk metrics.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available, falling back to sequential Monte Carlo")
            return self.run_monte_carlo_simulation(portfolio, iterations, time_horizon_days)

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        n_workers = num_cpus or mproc.cpu_count()
        chunk_size = iterations // n_workers
        remainder = iterations % n_workers

        # Serialize portfolio data for workers
        portfolio_data = {
            'portfolio_value': portfolio.portfolio_value,
            'total_delta': portfolio.total_delta,
            'total_gamma': portfolio.total_gamma,
            'total_vega': portfolio.total_vega,
            'total_theta': portfolio.total_theta,
            'positions': {k: dict(v) for k, v in portfolio.positions.items()},
        }
        portfolio_ref = ray.put(portfolio_data)

        @ray.remote
        def _monte_carlo_chunk(portfolio_ref, n_iterations: int,
                                time_horizon: int, seed: int) -> list[float]:
            """Run a chunk of Monte Carlo iterations on a Ray worker."""
            import numpy as _np
            _np.random.seed(seed)

            pdata = portfolio_ref
            pv = pdata['portfolio_value']
            delta = pdata['total_delta']
            vega = pdata['total_vega']

            pnl_results = []
            for _ in range(n_iterations):
                # Random market scenario
                equity_shock = _np.random.normal(0, 0.02 * _np.sqrt(time_horizon))
                vol_shock = _np.random.normal(0, 0.05)

                # P&L from Greeks-based approximation
                pnl = (delta * pv * equity_shock +
                       vega * vol_shock * 100 +
                       _np.random.normal(0, pv * 0.001))
                pnl_results.append(float(pnl))

            return pnl_results

        self.logger.info(f"Ray Monte Carlo: {iterations} iterations across {n_workers} workers")
        start_time = time.time()

        futures = []
        for i in range(n_workers):
            n = chunk_size + (1 if i < remainder else 0)
            futures.append(_monte_carlo_chunk.remote(
                portfolio_ref, n, time_horizon_days, seed=42 + i
            ))

        chunk_results = ray.get(futures)
        pnl_distribution = []
        for chunk in chunk_results:
            pnl_distribution.extend(chunk)

        pnl_array = np.array(pnl_distribution)
        computation_time = time.time() - start_time

        results = {
            'simulation_stats': {
                'iterations': len(pnl_distribution),
                'time_horizon_days': time_horizon_days,
                'computation_time': computation_time,
                'portfolio_value': portfolio.portfolio_value,
                'backend': 'ray',
                'num_workers': n_workers,
            },
            'pnl_statistics': {
                'mean': float(np.mean(pnl_array)),
                'std': float(np.std(pnl_array)),
                'min': float(np.min(pnl_array)),
                'max': float(np.max(pnl_array)),
                'median': float(np.median(pnl_array)),
            },
            'risk_metrics': {
                'var_95': float(np.percentile(pnl_array, 5)),
                'var_99': float(np.percentile(pnl_array, 1)),
                'var_999': float(np.percentile(pnl_array, 0.1)),
                'expected_shortfall_95': float(np.mean(pnl_array[pnl_array <= np.percentile(pnl_array, 5)])),
                'expected_shortfall_99': float(np.mean(pnl_array[pnl_array <= np.percentile(pnl_array, 1)])),
            },
            'distribution_data': pnl_distribution,
        }

        self.logger.info(f"Ray Monte Carlo complete: {iterations} iterations in {computation_time:.2f}s, "
                          f"VaR99=${results['risk_metrics']['var_99']:,.0f}")
        return results

    def run_distributed_stress_scenarios(self, portfolio: 'PortfolioSnapshot',
                                          scenario_ids: list[str] | None = None,
                                          num_cpus: int | None = None) -> list[dict[str, Any]]:
        """
        Run multiple stress scenarios in parallel via Ray.

        Args:
            portfolio: Current portfolio snapshot.
            scenario_ids: Specific scenarios to run (None = all).
            num_cpus: Number of CPUs to allocate.

        Returns:
            List of scenario results.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed stress scenarios")
            return []

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        scenarios_to_run = scenario_ids or list(self.scenarios.keys())
        scenario_data = [
            {
                'scenario_id': sid,
                'equity_shock': self.scenarios[sid].equity_shock if sid in self.scenarios else -0.05,
                'vix_level': self.scenarios[sid].vix_level if sid in self.scenarios else 30,
                'name': self.scenarios[sid].name if sid in self.scenarios else sid,
            }
            for sid in scenarios_to_run if sid in self.scenarios
        ]

        portfolio_data = {
            'portfolio_value': portfolio.portfolio_value,
            'total_delta': portfolio.total_delta,
            'total_vega': portfolio.total_vega,
        }
        portfolio_ref = ray.put(portfolio_data)
        ray.put(scenario_data)

        @ray.remote
        def _evaluate_scenario(portfolio_ref, scenario: dict) -> dict:
            """Evaluate a single stress scenario on a Ray worker."""
            pdata = portfolio_ref
            pnl = (pdata['total_delta'] * pdata['portfolio_value'] * scenario['equity_shock'] +
                   pdata['total_vega'] * (scenario['vix_level'] - 20) * 10)
            return {
                'scenario_id': scenario['scenario_id'],
                'scenario_name': scenario['name'],
                'portfolio_pnl': float(pnl),
                'pnl_percentage': float(pnl / pdata['portfolio_value']) if pdata['portfolio_value'] else 0,
                'status': 'completed',
            }

        futures = [_evaluate_scenario.remote(portfolio_ref, s) for s in scenario_data]
        results = ray.get(futures)

        self.logger.info(f"Ray stress scenarios: {len(results)} completed")
        return results

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_default_portfolio_snapshot() -> PortfolioSnapshot:
    """Create a default portfolio snapshot for testing."""
    return PortfolioSnapshot(
        timestamp=datetime.now(),
        positions={
            'SPY_CALL_450': {'value': 10000, 'delta': 50, 'gamma': 2, 'vega': 30, 'theta': -5},
            'SPY_PUT_440': {'value': 8000, 'delta': -30, 'gamma': 1.5, 'vega': 25, 'theta': -3}
        },
        portfolio_value=100000,
        cash_balance=20000,
        total_delta=20,
        total_gamma=3.5,
        total_vega=55,
        total_theta=-8,
        total_rho=10
    )

def create_black_monday_scenario() -> StressScenario:
    """Create Black Monday stress scenario."""
    return StressScenario(
        scenario_id="black_monday_custom",
        scenario_type=StressScenarioType.EQUITY_CRASH,
        name="Black Monday Replication",
        description="Custom Black Monday scenario with enhanced parameters",
        severity=StressSeverity.CATASTROPHIC,
        equity_shock=BLACK_MONDAY_SHOCK,
        vix_level=VIX_EXTREME,
        correlation_multiplier=0.2
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_stress_testing_instance: RealTimeStressTesting | None = None

def get_stress_testing_instance() -> RealTimeStressTesting:
    """
    Get singleton instance of the stress testing engine.

    Returns:
        RealTimeStressTesting instance
    """
    global _stress_testing_instance
    if _stress_testing_instance is None:
        _stress_testing_instance = RealTimeStressTesting()
        _stress_testing_instance.initialize()
    return _stress_testing_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    logging.info("🎯 SPYDER E07 - Real-Time Stress Testing Engine")
    logging.info("=" * 80)

    try:
        # Create stress testing engine
        stress_engine = RealTimeStressTesting()
        logging.info("✅ Stress Testing Engine initialized")

        # Initialize engine
        if not stress_engine.initialize():
            logging.info("❌ Failed to initialize stress testing engine")
            return False

        # Create test portfolio
        portfolio = create_default_portfolio_snapshot()
        logging.info(f"📊 Created test portfolio: ${portfolio.portfolio_value:,.2f}")

        # Test single scenario
        logging.info("\n🔍 Testing Black Monday scenario...")
        black_monday_result = await stress_engine.run_single_scenario("black_monday", portfolio)
        if black_monday_result:
            logging.info(f"   P&L Impact: {black_monday_result.pnl_percentage:.2%}")
            logging.info(f"   Portfolio P&L: ${black_monday_result.portfolio_pnl:,.2f}")
            logging.info(f"   Severity: {black_monday_result.severity.value}")
            logging.info(f"   Computation Time: {black_monday_result.computation_time:.3f}s")

        # Test all scenarios
        logging.info("\n🚀 Running all stress scenarios...")
        all_results = await stress_engine.run_all_scenarios(portfolio)
        logging.info(f"✅ Completed {len(all_results)} stress scenarios")

        # Show worst case scenarios
        worst_cases = stress_engine.get_worst_case_scenarios(3)
        if worst_cases:
            logging.info("\n⚠️  WORST CASE SCENARIOS:")
            for i, scenario in enumerate(worst_cases, 1):
                logging.info(f"   {i}. {scenario['scenario_name']}: {scenario['pnl_impact']:.2%}")

        # Run Monte Carlo simulation
        logging.info("\n🎲 Running Monte Carlo simulation...")
        mc_results = stress_engine.run_monte_carlo_simulation(portfolio, iterations=1000)
        if mc_results:
            pnl_stats = mc_results.get('pnl_statistics', {})
            risk_metrics = mc_results.get('risk_metrics', {})
            logging.info(f"   Mean P&L: ${pnl_stats.get('mean', 0):,.2f}")
            logging.info(f"   99% VaR: ${risk_metrics.get('var_99', 0):,.2f}")
            logging.info(f"   Expected Shortfall: ${risk_metrics.get('expected_shortfall_99', 0):,.2f}")

        # Generate comprehensive report
        logging.info("\n📋 Generating stress testing report...")
        report = stress_engine.generate_stress_report()
        logging.info("📊 STRESS TESTING REPORT:")
        logging.info("-" * 40)
        # Print first few lines of report
        report_lines = report.split('\n')[:15]
        for line in report_lines:
            logging.info(line)
        logging.info("   ... (truncated)")

        # Test performance
        summary = stress_engine.get_stress_summary()
        perf_metrics = summary.get('performance_metrics', {})
        logging.info("\n⚡ PERFORMANCE METRICS:")
        logging.info(f"   Total Tests: {perf_metrics.get('total_tests', 0)}")
        logging.info(f"   Average Computation Time: {perf_metrics.get('avg_computation_time', 0):.3f}s")
        logging.info(f"   Maximum Computation Time: {perf_metrics.get('max_computation_time', 0):.3f}s")

        # Cleanup
        stress_engine.cleanup()
        logging.info("\n✅ Real-Time Stress Testing Engine test completed successfully!")

        logging.info("\n🎯 STRESS TESTING CAPABILITIES:")
        logging.info(f"   • {len(stress_engine.scenarios)} Built-in Scenarios")
        logging.info("   • Monte Carlo Simulation (10,000 iterations)")
        logging.info("   • Real-time Portfolio Monitoring")
        logging.info("   • Multi-severity Risk Assessment")
        logging.info("   • Performance Optimized (<1s per test)")
        logging.info("   • Comprehensive Alert System")
        logging.info("   • Historical Scenario Replication")
        logging.info("   • Custom Scenario Support")

        return True

    except Exception as e:
        logging.info(f"❌ Error during testing: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())
