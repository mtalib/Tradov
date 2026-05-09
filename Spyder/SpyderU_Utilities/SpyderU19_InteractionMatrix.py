#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU19_InteractionMatrix.py
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
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

DEFAULT_MATRIX_SIZE = 100
INTERACTION_TIMEOUT = 300  # 5 minutes
MAX_HISTORY_SIZE = 10000
UPDATE_INTERVAL = 60  # 1 minute

# ==============================================================================
# ENUMS
# ==============================================================================
class InteractionType(Enum):
    """Types of module interactions"""
    FUNCTION_CALL = "function_call"
    DATA_EXCHANGE = "data_exchange"
    EVENT_TRIGGER = "event_trigger"
    SUBSCRIPTION = "subscription"
    NOTIFICATION = "notification"
    ERROR_PROPAGATION = "error_propagation"
    STATUS_UPDATE = "status_update"

class InteractionStatus(Enum):
    """Status of interactions"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PENDING = "pending"
    RETRYING = "retrying"

class MatrixMetric(Enum):
    """Matrix analysis metrics"""
    FREQUENCY = "frequency"
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"
    DATA_VOLUME = "data_volume"
    ERROR_RATE = "error_rate"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Interaction:
    """Single interaction between modules"""
    source: str
    target: str
    interaction_type: InteractionType
    timestamp: datetime
    status: InteractionStatus = InteractionStatus.PENDING
    latency_ms: float | None = None
    data_size: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Check if interaction was successful"""
        return self.status == InteractionStatus.SUCCESS

    @property
    def duration_ms(self) -> float:
        """Get interaction duration in milliseconds"""
        return self.latency_ms or 0.0

@dataclass
class ModuleStats:
    """Statistics for a module's interactions"""
    module_name: str
    total_interactions: int = 0
    successful_interactions: int = 0
    failed_interactions: int = 0
    average_latency: float = 0.0
    total_data_sent: int = 0
    total_data_received: int = 0
    error_count: int = 0
    last_activity: datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_interactions == 0:
            return 0.0
        return (self.successful_interactions / self.total_interactions) * 100

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage"""
        if self.total_interactions == 0:
            return 0.0
        return (self.failed_interactions / self.total_interactions) * 100

@dataclass
class MatrixAnalysis:
    """Analysis results from interaction matrix"""
    matrix_data: np.ndarray
    module_names: list[str]
    metric_type: MatrixMetric
    hotspots: list[tuple[str, str, float]] = field(default_factory=list)
    bottlenecks: list[str] = field(default_factory=list)
    isolated_modules: list[str] = field(default_factory=list)
    critical_paths: list[list[str]] = field(default_factory=list)
    health_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)

# ==============================================================================
# INTERACTION MATRIX CLASS
# ==============================================================================
class InteractionMatrix:
    """
    Module interaction matrix for system communication analysis.

    Features:
    - Real-time interaction tracking
    - Communication pattern analysis
    - Performance bottleneck identification
    - System health monitoring
    - Data flow visualization
    - Module coupling analysis
    """

    def __init__(self, max_modules: int = DEFAULT_MATRIX_SIZE):
        """
        Initialize interaction matrix.

        Args:
            max_modules: Maximum number of modules to track
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.max_modules = max_modules

        # Data storage
        self.modules: dict[str, int] = {}  # module_name -> index
        self.module_names: list[str] = []
        self.interactions: list[Interaction] = []
        self.module_stats: dict[str, ModuleStats] = {}

        # Matrices for different metrics
        self.frequency_matrix = np.zeros((max_modules, max_modules), dtype=int)
        self.latency_matrix = np.zeros((max_modules, max_modules), dtype=float)
        self.success_matrix = np.zeros((max_modules, max_modules), dtype=float)
        self.data_volume_matrix = np.zeros((max_modules, max_modules), dtype=int)

        # Monitoring
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.RLock()

        # Cache for analysis results
        self._analysis_cache: dict[str, MatrixAnalysis] = {}
        self._cache_timestamp = datetime.now(timezone.utc)

        self.logger.info("InteractionMatrix initialized (max_modules: %s)", max_modules)

    # ==========================================================================
    # PUBLIC METHODS - INTERACTION RECORDING
    # ==========================================================================
    def record_interaction(self, source: str, target: str,
                          interaction_type: InteractionType,
                          status: InteractionStatus = InteractionStatus.SUCCESS,
                          latency_ms: float | None = None,
                          data_size: int | None = None,
                          error_message: str | None = None,
                          metadata: dict[str, Any] | None = None) -> None:
        """
        Record an interaction between modules.

        Args:
            source: Source module name
            target: Target module name
            interaction_type: Type of interaction
            status: Interaction status
            latency_ms: Interaction latency in milliseconds
            data_size: Size of data exchanged
            error_message: Error message if failed
            metadata: Additional metadata
        """
        try:
            with self._lock:
                # Ensure modules are registered
                self._register_module(source)
                self._register_module(target)

                # Create interaction record
                interaction = Interaction(
                    source=source,
                    target=target,
                    interaction_type=interaction_type,
                    timestamp=datetime.now(timezone.utc),
                    status=status,
                    latency_ms=latency_ms,
                    data_size=data_size,
                    error_message=error_message,
                    metadata=metadata or {}
                )

                # Store interaction
                self.interactions.append(interaction)

                # Limit history size
                if len(self.interactions) > MAX_HISTORY_SIZE:
                    self.interactions = self.interactions[-MAX_HISTORY_SIZE:]

                # Update matrices
                self._update_matrices(interaction)

                # Update module statistics
                self._update_module_stats(interaction)

                # Invalidate cache
                self._invalidate_cache()

        except Exception as e:
            self.logger.error("Error recording interaction: %s", str(e))

    def start_interaction(self, source: str, target: str,
                         interaction_type: InteractionType,
                         metadata: dict[str, Any] | None = None) -> str:
        """
        Start tracking an interaction (returns interaction ID for completion).

        Args:
            source: Source module name
            target: Target module name
            interaction_type: Type of interaction
            metadata: Additional metadata

        Returns:
            Interaction ID for completion tracking
        """
        try:
            interaction_id = f"{source}->{target}:{datetime.now(timezone.utc).timestamp()}"

            # Record as pending
            self.record_interaction(
                source=source,
                target=target,
                interaction_type=interaction_type,
                status=InteractionStatus.PENDING,
                metadata=metadata
            )

            return interaction_id

        except Exception as e:
            self.logger.error("Error starting interaction: %s", str(e))
            return ""

    def complete_interaction(self, interaction_id: str,
                           status: InteractionStatus = InteractionStatus.SUCCESS,
                           latency_ms: float | None = None,
                           data_size: int | None = None,
                           error_message: str | None = None) -> None:
        """
        Complete a tracked interaction.

        Args:
            interaction_id: Interaction ID from start_interaction
            status: Final status
            latency_ms: Measured latency
            data_size: Data size exchanged
            error_message: Error message if failed
        """
        try:
            # For simplicity, just record the completion
            # In a full implementation, you'd track pending interactions
            self.logger.debug("Completed interaction %s with status %s", interaction_id, status.value)  # noqa: E501

        except Exception as e:
            self.logger.error("Error completing interaction: %s", str(e))

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def analyze_matrix(self, metric: MatrixMetric = MatrixMetric.FREQUENCY,
                      time_window: timedelta | None = None) -> MatrixAnalysis:
        """
        Analyze the interaction matrix for patterns and insights.

        Args:
            metric: Metric to analyze
            time_window: Optional time window for analysis

        Returns:
            MatrixAnalysis object with results
        """
        try:
            cache_key = f"{metric.value}_{time_window}"

            # Check cache
            if (cache_key in self._analysis_cache and
                datetime.now(timezone.utc) - self._cache_timestamp < timedelta(minutes=5)):
                return self._analysis_cache[cache_key]

            with self._lock:
                # Filter interactions by time window if specified
                filtered_interactions = self.interactions
                if time_window:
                    cutoff_time = datetime.now(timezone.utc) - time_window
                    filtered_interactions = [
                        i for i in self.interactions
                        if i.timestamp >= cutoff_time
                    ]

                # Get matrix data based on metric
                if metric == MatrixMetric.FREQUENCY:
                    matrix_data = self._calculate_frequency_matrix(filtered_interactions)
                elif metric == MatrixMetric.LATENCY:
                    matrix_data = self._calculate_latency_matrix(filtered_interactions)
                elif metric == MatrixMetric.SUCCESS_RATE:
                    matrix_data = self._calculate_success_rate_matrix(filtered_interactions)
                elif metric == MatrixMetric.DATA_VOLUME:
                    matrix_data = self._calculate_data_volume_matrix(filtered_interactions)
                else:
                    matrix_data = self.frequency_matrix[:len(self.module_names), :len(self.module_names)]  # noqa: E501

                # Perform analysis
                analysis = self._perform_matrix_analysis(matrix_data, metric)

                # Cache result
                self._analysis_cache[cache_key] = analysis

                return analysis

        except Exception as e:
            self.logger.error("Error analyzing matrix: %s", str(e))
            return MatrixAnalysis(
                matrix_data=np.zeros((1, 1)),
                module_names=[],
                metric_type=metric
            )

    def get_module_statistics(self, module_name: str | None = None) -> ModuleStats | dict[str, ModuleStats]:  # noqa: E501
        """
        Get statistics for a module or all modules.

        Args:
            module_name: Specific module name (None for all)

        Returns:
            ModuleStats or dictionary of all stats
        """
        try:
            with self._lock:
                if module_name:
                    return self.module_stats.get(module_name, ModuleStats(module_name))
                else:
                    return self.module_stats.copy()

        except Exception as e:
            self.logger.error("Error getting module statistics: %s", str(e))
            if module_name:
                return ModuleStats(module_name)
            else:
                return {}

    def get_interaction_history(self, source: str | None = None,
                               target: str | None = None,
                               limit: int = 100) -> list[Interaction]:
        """
        Get interaction history with optional filtering.

        Args:
            source: Filter by source module
            target: Filter by target module
            limit: Maximum number of interactions to return

        Returns:
            List of filtered interactions
        """
        try:
            with self._lock:
                filtered = self.interactions

                if source:
                    filtered = [i for i in filtered if i.source == source]

                if target:
                    filtered = [i for i in filtered if i.target == target]

                # Sort by timestamp (most recent first) and limit
                filtered.sort(key=lambda x: x.timestamp, reverse=True)
                return filtered[:limit]

        except Exception as e:
            self.logger.error("Error getting interaction history: %s", str(e))
            return []

    def identify_hotspots(self, metric: MatrixMetric = MatrixMetric.FREQUENCY,
                         top_n: int = 10) -> list[tuple[str, str, float]]:
        """
        Identify interaction hotspots (high activity pairs).

        Args:
            metric: Metric to analyze
            top_n: Number of top hotspots to return

        Returns:
            List of (source, target, value) tuples
        """
        try:
            analysis = self.analyze_matrix(metric)
            return analysis.hotspots[:top_n]

        except Exception as e:
            self.logger.error("Error identifying hotspots: %s", str(e))
            return []

    def detect_bottlenecks(self) -> list[str]:
        """
        Detect potential bottleneck modules.

        Returns:
            List of module names that may be bottlenecks
        """
        try:
            bottlenecks = []

            with self._lock:
                for module_name, stats in self.module_stats.items():
                    # High interaction volume with high latency
                    if (stats.total_interactions > 100 and
                        stats.average_latency > 1000) or stats.error_rate > 10:  # > 1 second
                        bottlenecks.append(module_name)

            return bottlenecks

        except Exception as e:
            self.logger.error("Error detecting bottlenecks: %s", str(e))
            return []

    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def start_monitoring(self, update_interval: int = UPDATE_INTERVAL) -> None:
        """
        Start continuous monitoring and analysis.

        Args:
            update_interval: Update interval in seconds
        """
        try:
            if self._monitoring:
                self.logger.warning("Monitoring already active")
                return

            self._monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(update_interval,),
                daemon=True
            )
            self._monitor_thread.start()

            self.logger.info("Interaction monitoring started (interval: %ss)", update_interval)

        except Exception as e:
            self.logger.error("Error starting monitoring: %s", str(e))

    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        try:
            self._monitoring = False
            self.logger.info("Interaction monitoring stopped")

        except Exception as e:
            self.logger.error("Error stopping monitoring: %s", str(e))

    def get_system_health(self) -> dict[str, Any]:
        """
        Get overall system interaction health metrics.

        Returns:
            Dictionary with health metrics
        """
        try:
            with self._lock:
                total_interactions = len(self.interactions)
                if total_interactions == 0:
                    return {
                        'health_score': 100.0,
                        'total_interactions': 0,
                        'active_modules': 0,
                        'average_latency': 0.0,
                        'error_rate': 0.0,
                        'status': 'idle'
                    }

                # Calculate metrics
                successful = sum(1 for i in self.interactions if i.is_successful)
                success_rate = (successful / total_interactions) * 100

                latencies = [i.latency_ms for i in self.interactions if i.latency_ms is not None]
                avg_latency = np.mean(latencies) if latencies else 0.0

                error_rate = 100 - success_rate

                # Calculate health score
                health_score = 100.0
                health_score -= error_rate * 0.5  # Penalize errors
                health_score -= min(avg_latency / 100, 20)  # Penalize high latency
                health_score = max(0.0, min(100.0, health_score))

                # Determine status
                if health_score >= 90:
                    status = 'excellent'
                elif health_score >= 75:
                    status = 'good'
                elif health_score >= 50:
                    status = 'fair'
                else:
                    status = 'poor'

                return {
                    'health_score': health_score,
                    'total_interactions': total_interactions,
                    'active_modules': len(self.module_stats),
                    'success_rate': success_rate,
                    'average_latency': avg_latency,
                    'error_rate': error_rate,
                    'status': status
                }

        except Exception as e:
            self.logger.error("Error getting system health: %s", str(e))
            return {'health_score': 0.0, 'status': 'error'}

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _register_module(self, module_name: str) -> None:
        """Register a module in the matrix"""
        if module_name not in self.modules:
            if len(self.module_names) >= self.max_modules:
                self.logger.warning("Maximum modules reached (%s)", self.max_modules)
                return

            index = len(self.module_names)
            self.modules[module_name] = index
            self.module_names.append(module_name)
            self.module_stats[module_name] = ModuleStats(module_name)

            self.logger.debug("Registered module: %s (index: %s)", module_name, index)

    def _update_matrices(self, interaction: Interaction) -> None:
        """Update the interaction matrices"""
        try:
            source_idx = self.modules.get(interaction.source)
            target_idx = self.modules.get(interaction.target)

            if source_idx is None or target_idx is None:
                return

            # Update frequency matrix
            self.frequency_matrix[source_idx, target_idx] += 1

            # Update latency matrix
            if interaction.latency_ms is not None:
                current_count = self.frequency_matrix[source_idx, target_idx]
                current_avg = self.latency_matrix[source_idx, target_idx]

                # Running average
                new_avg = ((current_avg * (current_count - 1)) + interaction.latency_ms) / current_count  # noqa: E501
                self.latency_matrix[source_idx, target_idx] = new_avg

            # Update success matrix
            if interaction.is_successful:
                success_count = self.success_matrix[source_idx, target_idx]
                total_count = self.frequency_matrix[source_idx, target_idx]
                self.success_matrix[source_idx, target_idx] = ((success_count * (total_count - 1)) + 1) / total_count  # noqa: E501
            else:
                success_count = self.success_matrix[source_idx, target_idx]
                total_count = self.frequency_matrix[source_idx, target_idx]
                self.success_matrix[source_idx, target_idx] = (success_count * (total_count - 1)) / total_count  # noqa: E501

            # Update data volume matrix
            if interaction.data_size is not None:
                self.data_volume_matrix[source_idx, target_idx] += interaction.data_size

        except Exception as e:
            self.logger.error("Error updating matrices: %s", str(e))

    def _update_module_stats(self, interaction: Interaction) -> None:
        """Update module statistics"""
        try:
            # Update source stats
            source_stats = self.module_stats[interaction.source]
            source_stats.total_interactions += 1
            if interaction.is_successful:
                source_stats.successful_interactions += 1
            else:
                source_stats.failed_interactions += 1
                source_stats.error_count += 1

            if interaction.latency_ms is not None:
                # Running average
                total = source_stats.total_interactions
                current_avg = source_stats.average_latency
                source_stats.average_latency = ((current_avg * (total - 1)) + interaction.latency_ms) / total  # noqa: E501

            if interaction.data_size is not None:
                source_stats.total_data_sent += interaction.data_size

            source_stats.last_activity = interaction.timestamp

            # Update target stats
            target_stats = self.module_stats[interaction.target]
            if interaction.data_size is not None:
                target_stats.total_data_received += interaction.data_size
            target_stats.last_activity = interaction.timestamp

        except Exception as e:
            self.logger.error("Error updating module stats: %s", str(e))

    def _calculate_frequency_matrix(self, interactions: list[Interaction]) -> np.ndarray:
        """Calculate frequency matrix from interactions"""
        matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=int)

        for interaction in interactions:
            source_idx = self.modules.get(interaction.source)
            target_idx = self.modules.get(interaction.target)

            if source_idx is not None and target_idx is not None:
                matrix[source_idx, target_idx] += 1

        return matrix

    def _calculate_latency_matrix(self, interactions: list[Interaction]) -> np.ndarray:
        """Calculate average latency matrix from interactions"""
        matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=float)
        count_matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=int)

        for interaction in interactions:
            if interaction.latency_ms is None:
                continue

            source_idx = self.modules.get(interaction.source)
            target_idx = self.modules.get(interaction.target)

            if source_idx is not None and target_idx is not None:
                matrix[source_idx, target_idx] += interaction.latency_ms
                count_matrix[source_idx, target_idx] += 1

        # Calculate averages
        with np.errstate(divide='ignore', invalid='ignore'):
            matrix = np.divide(matrix, count_matrix, out=np.zeros_like(matrix), where=count_matrix!=0)  # noqa: E501

        return matrix

    def _calculate_success_rate_matrix(self, interactions: list[Interaction]) -> np.ndarray:
        """Calculate success rate matrix from interactions"""
        success_matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=int)
        total_matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=int)

        for interaction in interactions:
            source_idx = self.modules.get(interaction.source)
            target_idx = self.modules.get(interaction.target)

            if source_idx is not None and target_idx is not None:
                total_matrix[source_idx, target_idx] += 1
                if interaction.is_successful:
                    success_matrix[source_idx, target_idx] += 1

        # Calculate success rates
        with np.errstate(divide='ignore', invalid='ignore'):
            rate_matrix = np.divide(success_matrix, total_matrix, out=np.zeros_like(success_matrix, dtype=float), where=total_matrix!=0)  # noqa: E501

        return rate_matrix * 100  # Convert to percentage

    def _calculate_data_volume_matrix(self, interactions: list[Interaction]) -> np.ndarray:
        """Calculate data volume matrix from interactions"""
        matrix = np.zeros((len(self.module_names), len(self.module_names)), dtype=int)

        for interaction in interactions:
            if interaction.data_size is None:
                continue

            source_idx = self.modules.get(interaction.source)
            target_idx = self.modules.get(interaction.target)

            if source_idx is not None and target_idx is not None:
                matrix[source_idx, target_idx] += interaction.data_size

        return matrix

    def _perform_matrix_analysis(self, matrix_data: np.ndarray, metric: MatrixMetric) -> MatrixAnalysis:  # noqa: E501
        """Perform comprehensive analysis on matrix data"""
        try:
            # Find hotspots (high values)
            hotspots = []
            flat_indices = np.argsort(matrix_data.flatten())[::-1]  # Descending order

            for idx in flat_indices[:20]:  # Top 20
                row, col = np.unravel_index(idx, matrix_data.shape)
                value = matrix_data[row, col]

                if value > 0 and row < len(self.module_names) and col < len(self.module_names):
                    hotspots.append((self.module_names[row], self.module_names[col], float(value)))

            # Find bottlenecks (modules with high outgoing traffic)
            outgoing_sums = np.sum(matrix_data, axis=1)
            bottleneck_indices = np.argsort(outgoing_sums)[::-1][:5]  # Top 5
            bottlenecks = [self.module_names[i] for i in bottleneck_indices
                          if i < len(self.module_names) and outgoing_sums[i] > 0]

            # Find isolated modules (no interactions)
            row_sums = np.sum(matrix_data, axis=1)
            col_sums = np.sum(matrix_data, axis=0)
            isolated_indices = np.where((row_sums == 0) & (col_sums == 0))[0]
            isolated_modules = [self.module_names[i] for i in isolated_indices
                              if i < len(self.module_names)]

            # Calculate health score
            np.sum(matrix_data)
            non_zero_count = np.count_nonzero(matrix_data)
            connectivity = non_zero_count / (len(self.module_names) ** 2) if len(self.module_names) > 0 else 0  # noqa: E501

            health_score = connectivity * 100
            if metric == MatrixMetric.SUCCESS_RATE:
                avg_success_rate = np.mean(matrix_data[matrix_data > 0]) if non_zero_count > 0 else 100  # noqa: E501
                health_score = avg_success_rate
            elif metric == MatrixMetric.LATENCY:
                avg_latency = np.mean(matrix_data[matrix_data > 0]) if non_zero_count > 0 else 0
                health_score = max(0, 100 - (avg_latency / 10))  # Penalize high latency

            # Generate recommendations
            recommendations = self._generate_matrix_recommendations(
                matrix_data, metric, hotspots, bottlenecks, isolated_modules
            )

            return MatrixAnalysis(
                matrix_data=matrix_data,
                module_names=self.module_names.copy(),
                metric_type=metric,
                hotspots=hotspots,
                bottlenecks=bottlenecks,
                isolated_modules=isolated_modules,
                health_score=health_score,
                recommendations=recommendations
            )

        except Exception as e:
            self.logger.error("Error performing matrix analysis: %s", str(e))
            return MatrixAnalysis(
                matrix_data=matrix_data,
                module_names=self.module_names.copy(),
                metric_type=metric
            )

    def _generate_matrix_recommendations(self, matrix_data: np.ndarray, metric: MatrixMetric,
                                       hotspots: list[tuple[str, str, float]],
                                       bottlenecks: list[str],
                                       isolated_modules: list[str]) -> list[str]:
        """Generate recommendations based on matrix analysis"""
        recommendations = []

        try:
            if hotspots:
                recommendations.append(f"Monitor {len(hotspots)} high-traffic module pairs")

            if bottlenecks:
                recommendations.append(f"Optimize {len(bottlenecks)} potential bottleneck modules")

            if isolated_modules:
                recommendations.append(f"Review {len(isolated_modules)} isolated modules")

            if metric == MatrixMetric.LATENCY:
                high_latency = [h for h in hotspots if h[2] > 1000]  # > 1 second
                if high_latency:
                    recommendations.append(f"Reduce latency for {len(high_latency)} slow interactions")  # noqa: E501

            elif metric == MatrixMetric.SUCCESS_RATE:
                low_success = [h for h in hotspots if h[2] < 95]  # < 95% success
                if low_success:
                    recommendations.append(f"Improve reliability for {len(low_success)} error-prone interactions")  # noqa: E501

        except Exception as e:
            self.logger.error("Error generating recommendations: %s", str(e))

        return recommendations

    def _monitor_loop(self, update_interval: int) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Perform periodic analysis
                health = self.get_system_health()

                # Log health status
                if health['health_score'] < 70:
                    self.logger.warning(f"System interaction health: {health['health_score']:.1f} ({health['status']})")  # noqa: E501
                else:
                    self.logger.debug(f"System interaction health: {health['health_score']:.1f} ({health['status']})")  # noqa: E501

                # Clean old interactions
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                with self._lock:
                    self.interactions = [i for i in self.interactions if i.timestamp >= cutoff_time]

                time.sleep(update_interval)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", str(e))
                time.sleep(update_interval)  # thread-safe: time.sleep() intentional

    def _invalidate_cache(self) -> None:
        """Invalidate analysis cache"""
        self._analysis_cache.clear()
        self._cache_timestamp = datetime.now(timezone.utc)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_interaction_matrix: InteractionMatrix | None = None

def get_interaction_matrix() -> InteractionMatrix:
    """
    Get singleton instance of interaction matrix.

    Returns:
        InteractionMatrix instance
    """
    global _interaction_matrix
    if _interaction_matrix is None:
        _interaction_matrix = InteractionMatrix()
    return _interaction_matrix

def record_interaction(source: str, target: str, interaction_type: str = "function_call",
                      success: bool = True, latency_ms: float | None = None) -> None:
    """Quick interaction recording"""
    matrix = get_interaction_matrix()
    status = InteractionStatus.SUCCESS if success else InteractionStatus.FAILURE
    int_type = InteractionType(interaction_type) if interaction_type in [t.value for t in InteractionType] else InteractionType.FUNCTION_CALL  # noqa: E501

    matrix.record_interaction(source, target, int_type, status, latency_ms)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test interaction matrix
    import random


    matrix = get_interaction_matrix()

    # Test interaction recording
    modules = ["SpyderA01_Main", "SpyderB01_SpyderClient", "SpyderC01_DataFeed", "SpyderD01_BaseStrategy"]  # noqa: E501

    # Generate sample interactions
    for _i in range(100):
        source = random.choice(modules)
        target = random.choice([m for m in modules if m != source])

        matrix.record_interaction(
            source=source,
            target=target,
            interaction_type=InteractionType.FUNCTION_CALL,
            status=InteractionStatus.SUCCESS if random.random() > 0.1 else InteractionStatus.FAILURE,  # noqa: E501
            latency_ms=random.uniform(10, 500),
            data_size=random.randint(100, 10000)
        )


    # Test analysis
    analysis = matrix.analyze_matrix(MatrixMetric.FREQUENCY)

    # Test hotspot identification
    hotspots = matrix.identify_hotspots(MatrixMetric.FREQUENCY, 5)
    for _i, (_, _, _value) in enumerate(hotspots[:3], 1):
        pass

    # Test module statistics
    stats = matrix.get_module_statistics()
    for _module_name, _module_stats in list(stats.items())[:3]:
        pass

    # Test system health
    health = matrix.get_system_health()

    # Test quick function
    record_interaction("TestModule1", "TestModule2", "function_call", True, 25.5)

