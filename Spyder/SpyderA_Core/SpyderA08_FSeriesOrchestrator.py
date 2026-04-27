#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA08_FSeriesOrchestrator.py
Purpose: Central F-Series Analytics Coordination and Orchestration Engine
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-30 Time: 23:45:00

Module Description:
    Institutional-grade central orchestration system for F12-F16 analytics modules.
    Provides intelligent coordination, resource allocation, priority management,
    and real-time performance optimization for the complete F-series institutional
    analytics suite. Ensures optimal performance, prevents resource conflicts,
    and maintains system stability for autonomous SPY options trading operations.

Key Features:
    • Central coordination of F12-F16 analytics modules
    • Intelligent resource allocation and priority management
    • Real-time performance monitoring and optimization
    • Adaptive workload balancing and queue management
    • Cross-module dependency resolution and scheduling
    • Dynamic priority adjustment based on market conditions
    • Resource conflict prevention and resolution
    • Performance bottleneck detection and mitigation
    • Health monitoring and automatic recovery
    • Integration with A06_MasterController

F-Series Module Coordination:
    • F12_AdvancedBacktestingEngine - Strategic backtesting coordination
    • F13_ModelValidation - AI/ML model validation orchestration
    • F14_MarketMicrostructure - Real-time microstructure analysis
    • F15_PerformanceAttribution - Performance analysis coordination
    • F16_RealTimeAnalytics - Real-time streaming orchestration
    • C21-C24 Data Pipeline - Data flow optimization

Dependencies:
    asyncio>=3.4.0, threading, queue, psutil>=5.9.0, numpy>=1.24.0
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import time
import asyncio
import threading
import queue
import logging
import traceback
import psutil
from pathlib import Path
from datetime import datetime
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import json

# Third-party imports
from collections import deque

# Add Spyder modules to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================

class ModulePriority(Enum):
    """Module execution priority levels"""
    CRITICAL = 1      # F16 Real-time analytics
    HIGH = 2          # F14 Market microstructure
    MEDIUM = 3        # F15 Performance attribution
    LOW = 4           # F13 Model validation
    BATCH = 5         # F12 Backtesting

class ResourceType(Enum):
    """System resource types"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    NETWORK = "network"
    GPU = "gpu"

class ModuleStatus(Enum):
    """F-Series module operational status"""
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"
    THROTTLED = "throttled"

class ExecutionMode(Enum):
    """Module execution modes"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
    ADAPTIVE = "adaptive"

@dataclass
class ResourceAllocation:
    """Resource allocation specification"""
    cpu_cores: int = 1
    memory_mb: int = 512
    io_priority: int = 3  # 1-5 scale
    network_bandwidth_mbps: int = 100
    gpu_memory_mb: int = 0
    max_execution_time_s: int = 300

@dataclass
class ModuleTask:
    """F-Series module execution task"""
    task_id: str
    module_name: str
    priority: ModulePriority
    function_name: str
    parameters: dict[str, Any]
    dependencies: list[str] = field(default_factory=list)
    resource_requirements: ResourceAllocation = field(default_factory=ResourceAllocation)
    created_time: datetime = field(default_factory=datetime.now)
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    completed_time: datetime | None = None
    status: ModuleStatus = ModuleStatus.QUEUED
    result: Any | None = None
    error: str | None = None
    execution_time_s: float = 0.0
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ModuleMetrics:
    """Module performance and health metrics"""
    module_name: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time_s: float = 0.0
    average_execution_time_s: float = 0.0
    current_cpu_usage: float = 0.0
    current_memory_usage_mb: float = 0.0
    peak_memory_usage_mb: float = 0.0
    error_rate: float = 0.0
    last_activity: datetime = field(default_factory=datetime.now)
    health_score: float = 100.0

@dataclass
class SystemResources:
    """System resource monitoring"""
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    available_memory_mb: float = 0.0
    disk_io_read_mbps: float = 0.0
    disk_io_write_mbps: float = 0.0
    network_io_mbps: float = 0.0
    active_connections: int = 0
    load_average: tuple[float, float, float] = (0.0, 0.0, 0.0)

@dataclass
class OrchestrationConfig:
    """Orchestration engine configuration"""
    max_concurrent_tasks: int = 8
    resource_allocation_strategy: str = "adaptive"
    priority_queue_size: int = 1000
    health_check_interval_s: int = 30
    performance_monitoring_interval_s: int = 10
    auto_scaling_enabled: bool = True
    failover_enabled: bool = True
    max_retry_attempts: int = 3
    task_timeout_s: int = 300

# ==============================================================================
# F-SERIES ORCHESTRATOR ENGINE
# ==============================================================================

class FSeriesOrchestrator:
    """
    Central F-Series Analytics Coordination and Orchestration Engine

    This class provides institutional-grade coordination and orchestration
    of F12-F16 analytics modules with intelligent resource management,
    priority scheduling, and performance optimization for SPY options trading.
    """

    def __init__(self, config: OrchestrationConfig | None = None):
        """Initialize the F-Series Orchestrator"""
        self.config = config or OrchestrationConfig()
        self.logger = self._setup_logging()

        # Core orchestration components
        self.task_queues: dict[ModulePriority, queue.PriorityQueue] = {}
        self.running_tasks: dict[str, ModuleTask] = {}
        self.completed_tasks: dict[str, ModuleTask] = {}
        self.module_metrics: dict[str, ModuleMetrics] = {}

        # Resource management
        self.system_resources = SystemResources()
        self.resource_allocations: dict[str, ResourceAllocation] = {}
        self.resource_locks = {}

        # Module registry and interfaces
        self.f_series_modules = {}
        self.c_series_modules = {}
        self.module_interfaces = {}

        # Orchestration control
        self.orchestration_active = False
        self.orchestration_thread = None
        self.monitoring_thread = None
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_tasks)

        # Performance optimization
        self.performance_history = deque(maxlen=1000)
        self.adaptive_parameters = {
            "cpu_threshold": 80.0,
            "memory_threshold": 85.0,
            "io_threshold": 75.0,
            "auto_scale_factor": 1.2
        }

        # Initialize priority queues
        for priority in ModulePriority:
            self.task_queues[priority] = queue.PriorityQueue(maxsize=self.config.priority_queue_size)  # noqa: E501

        # Initialize module metrics
        f_series_modules = ["F12", "F13", "F14", "F15", "F16"]
        c_series_modules = ["C21", "C22", "C23", "C24"]

        for module in f_series_modules + c_series_modules:
            self.module_metrics[module] = ModuleMetrics(module_name=module)
            self.resource_locks[module] = threading.RLock()

        self.logger.info("F-Series Orchestrator initialized successfully")
        self._log_configuration()

    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging configuration"""
        logger = logging.getLogger("FSeriesOrchestrator")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s | ORCHESTRATOR | %(levelname)s | %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            # File handler
            log_file = Path("logs") / f"f_series_orchestrator_{datetime.now().strftime('%Y%m%d')}.log"  # noqa: E501
            log_file.parent.mkdir(exist_ok=True)

            file_handler = logging.FileHandler(log_file)
            file_formatter = logging.Formatter(
                '%(asctime)s | ORCHESTRATOR | %(levelname)s | %(funcName)s | %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        return logger

    def _log_configuration(self) -> None:
        """Log orchestrator configuration details"""
        self.logger.info("F-Series Orchestrator Configuration:")
        self.logger.info("  Max Concurrent Tasks: %s", self.config.max_concurrent_tasks)
        self.logger.info("  Resource Strategy: %s", self.config.resource_allocation_strategy)
        self.logger.info("  Auto Scaling: %s", self.config.auto_scaling_enabled)
        self.logger.info("  Failover: %s", self.config.failover_enabled)
        self.logger.info("  Task Timeout: %ss", self.config.task_timeout_s)

    # ==========================================================================
    # MODULE REGISTRATION AND INTERFACES
    # ==========================================================================

    def register_f_series_module(self, module_name: str, module_instance: Any) -> bool:
        """Register F-series module with orchestrator"""
        try:
            if module_name not in ["F12", "F13", "F14", "F15", "F16"]:
                raise ValueError(f"Invalid F-series module name: {module_name}")

            self.f_series_modules[module_name] = module_instance
            self.module_interfaces[module_name] = self._create_module_interface(module_name, module_instance)  # noqa: E501

            self.logger.info("F-series module registered: %s", module_name)
            return True

        except Exception as e:
            self.logger.error("Failed to register F-series module %s: %s", module_name, e)
            return False

    def register_c_series_module(self, module_name: str, module_instance: Any) -> bool:
        """Register C-series data pipeline module with orchestrator"""
        try:
            if module_name not in ["C21", "C22", "C23", "C24"]:
                raise ValueError(f"Invalid C-series module name: {module_name}")

            self.c_series_modules[module_name] = module_instance
            self.module_interfaces[module_name] = self._create_module_interface(module_name, module_instance)  # noqa: E501

            self.logger.info("C-series module registered: %s", module_name)
            return True

        except Exception as e:
            self.logger.error("Failed to register C-series module %s: %s", module_name, e)
            return False

    def _create_module_interface(self, module_name: str, module_instance: Any) -> dict[str, Callable]:  # noqa: E501
        """Create standardized interface for module interaction"""
        interface = {}

        # Standard module methods
        standard_methods = [
            "initialize", "execute", "get_status", "get_metrics",
            "pause", "resume", "stop", "health_check"
        ]

        for method_name in standard_methods:
            if hasattr(module_instance, method_name):
                interface[method_name] = getattr(module_instance, method_name)

        # Module-specific methods based on F-series functionality
        module_specific_methods = {
            "F12": ["run_backtest", "get_backtest_results", "optimize_strategy"],
            "F13": ["validate_model", "check_drift", "get_validation_metrics"],
            "F14": ["analyze_microstructure", "get_order_flow", "calculate_impact"],
            "F15": ["calculate_attribution", "analyze_performance", "generate_report"],
            "F16": ["start_streaming", "get_real_time_metrics", "configure_alerts"],
            "C21": ["process_data_pipeline", "get_pipeline_status", "optimize_flow"],
            "C22": ["get_factor_data", "validate_factors", "update_factors"],
            "C23": ["optimize_latency", "configure_priority", "get_performance"],
            "C24": ["process_model_data", "extract_features", "validate_pipeline"]
        }

        if module_name in module_specific_methods:
            for method_name in module_specific_methods[module_name]:
                if hasattr(module_instance, method_name):
                    interface[method_name] = getattr(module_instance, method_name)

        return interface

    # ==========================================================================
    # TASK SCHEDULING AND EXECUTION
    # ==========================================================================

    def submit_task(self,
                   module_name: str,
                   function_name: str,
                   parameters: dict[str, Any],
                   priority: ModulePriority | None = None,
                   dependencies: list[str] | None = None,
                   resource_requirements: ResourceAllocation | None = None) -> str:
        """Submit task for orchestrated execution"""

        try:
            # Generate unique task ID
            task_id = f"{module_name}_{function_name}_{int(time.time() * 1000000)}"

            # Determine priority based on module type
            if priority is None:
                priority_map = {
                    "F16": ModulePriority.CRITICAL,  # Real-time analytics
                    "F14": ModulePriority.HIGH,      # Microstructure
                    "F15": ModulePriority.MEDIUM,    # Attribution
                    "F13": ModulePriority.LOW,       # Model validation
                    "F12": ModulePriority.BATCH,     # Backtesting
                    "C23": ModulePriority.CRITICAL,  # Ultra-low latency optimizer
                    "C21": ModulePriority.HIGH,      # Integration hub
                    "C22": ModulePriority.MEDIUM,    # Factor data
                    "C24": ModulePriority.LOW        # Model data pipeline
                }
                priority = priority_map.get(module_name, ModulePriority.MEDIUM)

            # Set default resource requirements
            if resource_requirements is None:
                resource_requirements = self._get_default_resources(module_name)

            # Create task
            task = ModuleTask(
                task_id=task_id,
                module_name=module_name,
                priority=priority,
                function_name=function_name,
                parameters=parameters,
                dependencies=dependencies or [],
                resource_requirements=resource_requirements
            )

            # Add to appropriate priority queue
            queue_item = (priority.value, time.time(), task)
            self.task_queues[priority].put(queue_item)

            self.logger.debug("Task submitted: %s [%s.%s]", task_id, module_name, function_name)
            return task_id

        except Exception as e:
            self.logger.error("Failed to submit task: %s", e)
            raise

    def _get_default_resources(self, module_name: str) -> ResourceAllocation:
        """Get default resource allocation for module"""
        resource_profiles = {
            "F12": ResourceAllocation(cpu_cores=2, memory_mb=2048, io_priority=2),
            "F13": ResourceAllocation(cpu_cores=2, memory_mb=1536, io_priority=3),
            "F14": ResourceAllocation(cpu_cores=4, memory_mb=1024, io_priority=1),
            "F15": ResourceAllocation(cpu_cores=2, memory_mb=1024, io_priority=3),
            "F16": ResourceAllocation(cpu_cores=4, memory_mb=512, io_priority=1),
            "C21": ResourceAllocation(cpu_cores=2, memory_mb=1024, io_priority=2),
            "C22": ResourceAllocation(cpu_cores=1, memory_mb=512, io_priority=4),
            "C23": ResourceAllocation(cpu_cores=4, memory_mb=256, io_priority=1),
            "C24": ResourceAllocation(cpu_cores=2, memory_mb=1536, io_priority=3)
        }

        return resource_profiles.get(module_name, ResourceAllocation())

    async def execute_task(self, task: ModuleTask) -> bool:
        """Execute individual module task with monitoring"""
        try:
            task.status = ModuleStatus.RUNNING
            task.started_time = datetime.now()

            # Update running tasks registry
            self.running_tasks[task.task_id] = task

            # Check dependencies
            if not self._check_task_dependencies(task):
                task.status = ModuleStatus.ERROR
                task.error = "Dependencies not satisfied"
                return False

            # Allocate resources
            if not self._allocate_resources(task):
                task.status = ModuleStatus.ERROR
                task.error = "Resource allocation failed"
                return False

            # Get module interface
            if task.module_name not in self.module_interfaces:
                raise ValueError(f"Module {task.module_name} not registered")

            interface = self.module_interfaces[task.module_name]

            if task.function_name not in interface:
                raise ValueError(f"Function {task.function_name} not available in {task.module_name}")  # noqa: E501

            # Execute task function
            start_time = time.perf_counter()

            if asyncio.iscoroutinefunction(interface[task.function_name]):
                task.result = await interface[task.function_name](**task.parameters)
            else:
                # Run synchronous function in executor
                task.result = await asyncio.get_running_loop().run_in_executor(
                    self.executor,
                    interface[task.function_name],
                    **task.parameters
                )

            end_time = time.perf_counter()
            task.execution_time_s = end_time - start_time

            # Update task status
            task.status = ModuleStatus.COMPLETED
            task.completed_time = datetime.now()

            # Update module metrics
            self._update_module_metrics(task)

            # Release resources
            self._release_resources(task)

            # Move to completed tasks
            self.completed_tasks[task.task_id] = task
            del self.running_tasks[task.task_id]

            self.logger.debug(f"Task completed: {task.task_id} in {task.execution_time_s:.3f}s")
            return True

        except Exception as e:
            task.status = ModuleStatus.ERROR
            task.error = str(e)
            task.completed_time = datetime.now()

            # Update metrics for failed task
            self._update_module_metrics(task)

            # Release resources
            self._release_resources(task)

            # Handle retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = ModuleStatus.QUEUED

                # Requeue with delay
                await asyncio.sleep(2 ** task.retry_count)  # Exponential backoff
                queue_item = (task.priority.value, time.time(), task)
                self.task_queues[task.priority].put(queue_item)

                self.logger.warning("Task %s failed, retrying (%s/%s)", task.task_id, task.retry_count, task.max_retries)  # noqa: E501
            else:
                self.completed_tasks[task.task_id] = task
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                self.logger.error("Task %s failed permanently: %s", task.task_id, e)

            return False

    def _check_task_dependencies(self, task: ModuleTask) -> bool:
        """Check if task dependencies are satisfied"""
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False

            dep_task = self.completed_tasks[dep_id]
            if dep_task.status != ModuleStatus.COMPLETED:
                return False

        return True

    def _allocate_resources(self, task: ModuleTask) -> bool:
        """Allocate system resources for task execution"""
        try:
            # Check resource availability
            if not self._check_resource_availability(task.resource_requirements):
                return False

            # Reserve resources
            self.resource_allocations[task.task_id] = task.resource_requirements

            return True

        except Exception as e:
            self.logger.error("Resource allocation failed for task %s: %s", task.task_id, e)
            return False

    def _release_resources(self, task: ModuleTask) -> None:
        """Release allocated resources after task completion"""
        try:
            if task.task_id in self.resource_allocations:
                del self.resource_allocations[task.task_id]
        except Exception as e:
            self.logger.error("Resource release failed for task %s: %s", task.task_id, e)

    def _check_resource_availability(self, requirements: ResourceAllocation) -> bool:
        """Check if required resources are available"""
        # Get current system resources
        self._update_system_resources()

        # Check CPU availability
        if self.system_resources.cpu_usage_percent > self.adaptive_parameters["cpu_threshold"]:
            return False

        # Check memory availability
        required_memory = requirements.memory_mb
        if self.system_resources.available_memory_mb < required_memory:
            return False

        # Check if too many tasks are already using resources
        total_allocated_memory = sum(alloc.memory_mb for alloc in self.resource_allocations.values())  # noqa: E501
        return not total_allocated_memory + required_memory > self.system_resources.available_memory_mb * 0.8  # noqa: E501

    def _update_module_metrics(self, task: ModuleTask) -> None:
        """Update performance metrics for module"""
        try:
            metrics = self.module_metrics[task.module_name]

            if task.status == ModuleStatus.COMPLETED:
                metrics.tasks_completed += 1
                metrics.total_execution_time_s += task.execution_time_s
                metrics.average_execution_time_s = (
                    metrics.total_execution_time_s / metrics.tasks_completed
                )
            elif task.status == ModuleStatus.ERROR:
                metrics.tasks_failed += 1

            # Calculate error rate
            total_tasks = metrics.tasks_completed + metrics.tasks_failed
            if total_tasks > 0:
                metrics.error_rate = metrics.tasks_failed / total_tasks

            # Update health score (100 - error_rate * 100)
            metrics.health_score = max(0, 100 - (metrics.error_rate * 100))

            metrics.last_activity = datetime.now()

        except Exception as e:
            self.logger.error("Failed to update metrics for %s: %s", task.module_name, e)

    # ==========================================================================
    # ORCHESTRATION ENGINE
    # ==========================================================================

    async def start_orchestration(self) -> None:
        """Start the orchestration engine"""
        if self.orchestration_active:
            self.logger.warning("Orchestration already active")
            return

        self.orchestration_active = True
        self.logger.info("Starting F-Series Orchestration Engine")

        # Start orchestration loop
        self.orchestration_task = asyncio.create_task(self._orchestration_loop())

        # Start monitoring
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        self.logger.info("F-Series Orchestration Engine started successfully")

    async def stop_orchestration(self) -> None:
        """Stop the orchestration engine gracefully"""
        self.logger.info("Stopping F-Series Orchestration Engine")

        self.orchestration_active = False

        # Cancel orchestration and monitoring tasks
        if hasattr(self, 'orchestration_task'):
            self.orchestration_task.cancel()

        if hasattr(self, 'monitoring_task'):
            self.monitoring_task.cancel()

        # Wait for running tasks to complete or timeout
        timeout = 30  # 30 seconds
        start_time = time.time()

        while self.running_tasks and (time.time() - start_time) < timeout:
            await asyncio.sleep(1)
            self.logger.info("Waiting for %s tasks to complete...", len(self.running_tasks))

        # Force stop remaining tasks if timeout exceeded
        if self.running_tasks:
            self.logger.warning("Force stopping %s remaining tasks", len(self.running_tasks))

        self.logger.info("F-Series Orchestration Engine stopped")

    async def _orchestration_loop(self) -> None:
        """Main orchestration loop for task processing"""
        self.logger.info("Orchestration loop started")

        while self.orchestration_active:
            try:
                # Process tasks from priority queues
                await self._process_priority_queues()

                # Optimize resource allocation
                self._optimize_resource_allocation()

                # Check for bottlenecks
                self._detect_performance_bottlenecks()

                # Short sleep to prevent CPU saturation
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error("Orchestration loop error: %s", e)
                await asyncio.sleep(1)  # Longer sleep on error

    async def _process_priority_queues(self) -> None:
        """Process tasks from priority queues"""
        # Check if we can start new tasks
        max_concurrent = self.config.max_concurrent_tasks
        current_running = len(self.running_tasks)

        if current_running >= max_concurrent:
            return

        # Process queues in priority order
        for priority in ModulePriority:
            if current_running >= max_concurrent:
                break

            try:
                # Get task from queue (non-blocking)
                queue_item = self.task_queues[priority].get_nowait()
                _, _, task = queue_item

                # Check if resources are available
                if not self._check_resource_availability(task.resource_requirements):
                    # Put task back in queue
                    self.task_queues[priority].put(queue_item)
                    continue

                # Start task execution
                asyncio.create_task(self.execute_task(task))
                current_running += 1

                self.logger.debug("Started task: %s [Priority: %s]", task.task_id, priority.name)

            except queue.Empty:
                # No tasks in this priority queue
                continue
            except Exception as e:
                self.logger.error("Error processing priority queue %s: %s", priority.name, e)

    async def _monitoring_loop(self) -> None:
        """System monitoring and health checks"""
        self.logger.info("Monitoring loop started")

        while self.orchestration_active:
            try:
                # Update system resources
                self._update_system_resources()

                # Check module health
                self._check_module_health()

                # Update performance history
                self._update_performance_history()

                # Adaptive parameter adjustment
                self._adjust_adaptive_parameters()

                # Sleep until next monitoring cycle
                await asyncio.sleep(self.config.performance_monitoring_interval_s)

            except Exception as e:
                self.logger.error("Monitoring loop error: %s", e)
                await asyncio.sleep(10)  # Longer sleep on error

    def _update_system_resources(self) -> None:
        """Update current system resource usage"""
        try:
            # CPU usage
            self.system_resources.cpu_usage_percent = psutil.cpu_percent()

            # Memory usage
            memory = psutil.virtual_memory()
            self.system_resources.memory_usage_percent = memory.percent
            self.system_resources.available_memory_mb = memory.available / (1024 * 1024)

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self.system_resources.disk_io_read_mbps = disk_io.read_bytes / (1024 * 1024)
                self.system_resources.disk_io_write_mbps = disk_io.write_bytes / (1024 * 1024)

            # Network I/O
            net_io = psutil.net_io_counters()
            if net_io:
                self.system_resources.network_io_mbps = (
                    (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
                )

            # Load average (Unix systems)
            if hasattr(os, 'getloadavg'):
                self.system_resources.load_average = os.getloadavg()

        except Exception as e:
            self.logger.error("Failed to update system resources: %s", e)

    def _check_module_health(self) -> None:
        """Check health status of all registered modules"""
        for module_name, metrics in self.module_metrics.items():
            try:
                # Check if module has been inactive for too long
                inactive_time = datetime.now() - metrics.last_activity
                if inactive_time.total_seconds() > 300:  # 5 minutes
                    metrics.health_score = max(0, metrics.health_score - 10)

                # Check error rates
                if metrics.error_rate > 0.1:  # 10% error rate threshold
                    metrics.health_score = max(0, metrics.health_score - 20)

                # Log health warnings
                if metrics.health_score < 70:
                    self.logger.warning(f"Module {module_name} health degraded: {metrics.health_score:.1f}")  # noqa: E501

            except Exception as e:
                self.logger.error("Health check failed for %s: %s", module_name, e)

    def _optimize_resource_allocation(self) -> None:
        """Optimize resource allocation based on current system state"""
        try:
            # Adjust CPU threshold based on current load
            cpu_usage = self.system_resources.cpu_usage_percent
            if cpu_usage > 90:
                self.adaptive_parameters["cpu_threshold"] = max(70, cpu_usage - 10)
            elif cpu_usage < 50:
                self.adaptive_parameters["cpu_threshold"] = min(85, cpu_usage + 20)

            # Adjust memory threshold
            memory_usage = self.system_resources.memory_usage_percent
            if memory_usage > 90:
                self.adaptive_parameters["memory_threshold"] = max(75, memory_usage - 10)
            elif memory_usage < 60:
                self.adaptive_parameters["memory_threshold"] = min(90, memory_usage + 15)

        except Exception as e:
            self.logger.error("Resource optimization failed: %s", e)

    def _detect_performance_bottlenecks(self) -> None:
        """Detect and log performance bottlenecks"""
        try:
            # Check for CPU bottlenecks
            if self.system_resources.cpu_usage_percent > 95:
                self.logger.warning("CPU bottleneck detected - high CPU usage")

            # Check for memory bottlenecks
            if self.system_resources.memory_usage_percent > 95:
                self.logger.warning("Memory bottleneck detected - high memory usage")

            # Check for I/O bottlenecks
            if (self.system_resources.disk_io_read_mbps + self.system_resources.disk_io_write_mbps) > 100:  # noqa: E501
                self.logger.warning("I/O bottleneck detected - high disk activity")

            # Check task queue lengths
            for priority, task_queue in self.task_queues.items():
                if task_queue.qsize() > 50:
                    self.logger.warning("Task queue bottleneck: %s queue has %s tasks", priority.name, task_queue.qsize())  # noqa: E501

        except Exception as e:
            self.logger.error("Bottleneck detection failed: %s", e)

    def _update_performance_history(self) -> None:
        """Update performance history for trend analysis"""
        try:
            performance_snapshot = {
                "timestamp": datetime.now(),
                "cpu_usage": self.system_resources.cpu_usage_percent,
                "memory_usage": self.system_resources.memory_usage_percent,
                "running_tasks": len(self.running_tasks),
                "completed_tasks": len(self.completed_tasks),
                "total_queue_size": sum(q.qsize() for q in self.task_queues.values())
            }

            self.performance_history.append(performance_snapshot)

        except Exception as e:
            self.logger.error("Performance history update failed: %s", e)

    def _adjust_adaptive_parameters(self) -> None:
        """Adjust adaptive parameters based on performance trends"""
        try:
            if len(self.performance_history) < 10:
                return

            # Get recent performance data
            recent_data = list(self.performance_history)[-10:]

            # Calculate average CPU usage over recent period
            avg_cpu = sum(d["cpu_usage"] for d in recent_data) / len(recent_data)

            # Adjust auto-scale factor based on trends
            if avg_cpu > 80:
                self.adaptive_parameters["auto_scale_factor"] = min(2.0,
                    self.adaptive_parameters["auto_scale_factor"] * 1.1)
            elif avg_cpu < 50:
                self.adaptive_parameters["auto_scale_factor"] = max(0.8,
                    self.adaptive_parameters["auto_scale_factor"] * 0.9)

        except Exception as e:
            self.logger.error("Adaptive parameter adjustment failed: %s", e)

    # ==========================================================================
    # TASK MANAGEMENT AND QUERIES
    # ==========================================================================

    def get_task_status(self, task_id: str) -> ModuleTask | None:
        """Get current status of a task"""
        # Check running tasks
        if task_id in self.running_tasks:
            return self.running_tasks[task_id]

        # Check completed tasks
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]

        # Check queued tasks
        for priority_queue in self.task_queues.values():
            # Note: This is not efficient for large queues, but provides completeness
            temp_items = []
            found_task = None

            try:
                while not priority_queue.empty():
                    item = priority_queue.get_nowait()
                    temp_items.append(item)

                    _, _, task = item
                    if task.task_id == task_id:
                        found_task = task
                        break
            except queue.Empty:
                pass
            finally:
                # Put items back in queue
                for item in temp_items:
                    priority_queue.put(item)

            if found_task:
                return found_task

        return None

    def get_module_metrics(self, module_name: str | None = None) -> dict[str, ModuleMetrics]:
        """Get performance metrics for modules"""
        if module_name:
            return {module_name: self.module_metrics.get(module_name)}
        else:
            return dict(self.module_metrics)

    def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "orchestration_active": self.orchestration_active,
            "running_tasks": len(self.running_tasks),
            "queued_tasks": sum(q.qsize() for q in self.task_queues.values()),
            "completed_tasks": len(self.completed_tasks),
            "system_resources": {
                "cpu_usage_percent": self.system_resources.cpu_usage_percent,
                "memory_usage_percent": self.system_resources.memory_usage_percent,
                "available_memory_mb": self.system_resources.available_memory_mb,
                "load_average": self.system_resources.load_average
            },
            "module_health": {
                name: metrics.health_score
                for name, metrics in self.module_metrics.items()
            },
            "adaptive_parameters": dict(self.adaptive_parameters)
        }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or running task"""
        try:
            # Check if task is running
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                task.status = ModuleStatus.ERROR
                task.error = "Task cancelled by user"

                # Move to completed tasks
                self.completed_tasks[task_id] = task
                del self.running_tasks[task_id]

                self.logger.info("Running task cancelled: %s", task_id)
                return True

            # Check queued tasks and remove
            for priority_queue in self.task_queues.values():
                temp_items = []
                task_cancelled = False

                try:
                    while not priority_queue.empty():
                        item = priority_queue.get_nowait()
                        _, _, task = item

                        if task.task_id == task_id:
                            task.status = ModuleStatus.ERROR
                            task.error = "Task cancelled by user"
                            self.completed_tasks[task_id] = task
                            task_cancelled = True
                            self.logger.info("Queued task cancelled: %s", task_id)
                        else:
                            temp_items.append(item)
                except queue.Empty:
                    pass
                finally:
                    # Put remaining items back in queue
                    for item in temp_items:
                        priority_queue.put(item)

                if task_cancelled:
                    return True

            return False

        except Exception as e:
            self.logger.error("Failed to cancel task %s: %s", task_id, e)
            return False

    # ==========================================================================
    # REPORTING AND EXPORT
    # ==========================================================================

    def generate_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report"""
        try:
            # Calculate aggregate metrics
            total_completed = sum(m.tasks_completed for m in self.module_metrics.values())
            total_failed = sum(m.tasks_failed for m in self.module_metrics.values())
            total_execution_time = sum(m.total_execution_time_s for m in self.module_metrics.values())  # noqa: E501

            overall_success_rate = (
                total_completed / (total_completed + total_failed) * 100
                if (total_completed + total_failed) > 0 else 100
            )

            # Get performance history statistics
            if self.performance_history:
                recent_cpu = [h["cpu_usage"] for h in self.performance_history[-20:]]
                recent_memory = [h["memory_usage"] for h in self.performance_history[-20:]]

                avg_cpu = sum(recent_cpu) / len(recent_cpu) if recent_cpu else 0
                avg_memory = sum(recent_memory) / len(recent_memory) if recent_memory else 0
            else:
                avg_cpu = avg_memory = 0

            report = {
                "report_timestamp": datetime.now().isoformat(),
                "orchestration_status": "Active" if self.orchestration_active else "Inactive",

                "aggregate_metrics": {
                    "total_tasks_completed": total_completed,
                    "total_tasks_failed": total_failed,
                    "overall_success_rate": overall_success_rate,
                    "total_execution_time_hours": total_execution_time / 3600,
                    "average_task_duration_seconds": (
                        total_execution_time / total_completed
                        if total_completed > 0 else 0
                    )
                },

                "current_status": {
                    "running_tasks": len(self.running_tasks),
                    "queued_tasks": sum(q.qsize() for q in self.task_queues.values()),
                    "completed_tasks": len(self.completed_tasks)
                },

                "system_performance": {
                    "average_cpu_usage_percent": avg_cpu,
                    "average_memory_usage_percent": avg_memory,
                    "current_cpu_usage_percent": self.system_resources.cpu_usage_percent,
                    "current_memory_usage_percent": self.system_resources.memory_usage_percent,
                    "available_memory_mb": self.system_resources.available_memory_mb
                },

                "module_performance": {
                    name: {
                        "tasks_completed": metrics.tasks_completed,
                        "tasks_failed": metrics.tasks_failed,
                        "error_rate": metrics.error_rate,
                        "health_score": metrics.health_score,
                        "average_execution_time_s": metrics.average_execution_time_s,
                        "total_execution_time_s": metrics.total_execution_time_s
                    }
                    for name, metrics in self.module_metrics.items()
                },

                "adaptive_parameters": dict(self.adaptive_parameters),

                "configuration": {
                    "max_concurrent_tasks": self.config.max_concurrent_tasks,
                    "resource_allocation_strategy": self.config.resource_allocation_strategy,
                    "auto_scaling_enabled": self.config.auto_scaling_enabled,
                    "failover_enabled": self.config.failover_enabled
                }
            }

            return report

        except Exception as e:
            self.logger.error("Performance report generation failed: %s", e)
            return {"error": str(e)}

    def export_performance_data(self, output_file: str | None = None) -> str:
        """Export performance data to JSON file"""
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"f_series_orchestrator_performance_{timestamp}.json"

            report = self.generate_performance_report()

            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            self.logger.info("Performance data exported to: %s", output_file)
            return output_file

        except Exception as e:
            self.logger.error("Performance data export failed: %s", e)
            raise

# ==============================================================================
# INTEGRATION WITH A06 MASTER CONTROLLER
# ==============================================================================

class MasterControllerIntegration:
    """Integration interface with SpyderA06_MasterController"""

    def __init__(self, orchestrator: FSeriesOrchestrator):
        self.orchestrator = orchestrator
        self.logger = orchestrator.logger

    def register_with_master_controller(self, master_controller) -> bool:
        """Register F-Series Orchestrator with Master Controller"""
        try:
            # Register orchestrator as a critical system component
            master_controller.register_component(
                component_id="F_SERIES_ORCHESTRATOR",
                component_instance=self.orchestrator,
                component_type="ORCHESTRATOR",
                priority=1,  # High priority
                dependencies=["DATA_MANAGER", "RISK_MANAGER"]
            )

            self.logger.info("Successfully registered with Master Controller")
            return True

        except Exception as e:
            self.logger.error("Failed to register with Master Controller: %s", e)
            return False

    def handle_master_controller_commands(self, command: str, parameters: dict[str, Any]) -> Any:
        """Handle commands from Master Controller"""
        try:
            if command == "START":
                return asyncio.create_task(self.orchestrator.start_orchestration())

            elif command == "STOP":
                return asyncio.create_task(self.orchestrator.stop_orchestration())

            elif command == "STATUS":
                return self.orchestrator.get_system_status()

            elif command == "HEALTH_CHECK":
                return self.orchestrator.get_module_metrics()

            elif command == "SUBMIT_TASK":
                return self.orchestrator.submit_task(**parameters)

            elif command == "CANCEL_TASK":
                return self.orchestrator.cancel_task(parameters["task_id"])

            elif command == "PERFORMANCE_REPORT":
                return self.orchestrator.generate_performance_report()

            else:
                raise ValueError(f"Unknown command: {command}")

        except Exception as e:
            self.logger.error("Command handling failed: %s - %s", command, e)
            raise

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

async def main():
    """Main execution function for testing and demonstration"""
    logging.info("🚀 F-Series Orchestrator Starting...")

    # Create orchestrator with custom configuration
    config = OrchestrationConfig(
        max_concurrent_tasks=6,
        resource_allocation_strategy="adaptive",
        auto_scaling_enabled=True,
        failover_enabled=True
    )

    orchestrator = FSeriesOrchestrator(config)

    try:
        # Start orchestration
        await orchestrator.start_orchestration()

        # Simulate task submissions
        logging.info("📝 Submitting test tasks...")

        # Submit various F-series tasks
        task_ids = []

        # F16 Real-time analytics task (Critical priority)
        task_id = orchestrator.submit_task(
            module_name="F16",
            function_name="start_streaming",
            parameters={"symbols": ["SPY"], "update_interval": 0.1}
        )
        task_ids.append(task_id)

        # F14 Microstructure analysis (High priority)
        task_id = orchestrator.submit_task(
            module_name="F14",
            function_name="analyze_microstructure",
            parameters={"symbol": "SPY", "depth": 5}
        )
        task_ids.append(task_id)

        # F15 Performance attribution (Medium priority)
        task_id = orchestrator.submit_task(
            module_name="F15",
            function_name="calculate_attribution",
            parameters={"portfolio": "test_portfolio", "benchmark": "SPY"}
        )
        task_ids.append(task_id)

        logging.info("✅ Submitted %s test tasks", len(task_ids))

        # Monitor execution for 30 seconds
        logging.info("📊 Monitoring execution for 30 seconds...")

        for _i in range(30):
            status = orchestrator.get_system_status()
            logging.info(f"Running: {status['running_tasks']}, "
                  f"Queued: {status['queued_tasks']}, "
                  f"Completed: {status['completed_tasks']}, "
                  f"CPU: {status['system_resources']['cpu_usage_percent']:.1f}%")

            await asyncio.sleep(1)

        # Generate and print performance report
        logging.info("\n📈 Generating Performance Report...")
        report = orchestrator.generate_performance_report()

        logging.info(f"Overall Success Rate: {report['aggregate_metrics']['overall_success_rate']:.1f}%")  # noqa: E501
        logging.info("Tasks Completed: %s", report['aggregate_metrics']['total_tasks_completed'])
        logging.info(f"Average CPU Usage: {report['system_performance']['average_cpu_usage_percent']:.1f}%")  # noqa: E501

        # Export performance data
        export_file = orchestrator.export_performance_data()
        logging.info("Performance data exported to: %s", export_file)

    except Exception as e:
        logging.info("❌ Orchestrator test failed: %s", e)
        traceback.print_exc()

    finally:
        # Stop orchestration
        await orchestrator.stop_orchestration()
        logging.info("🎯 F-Series Orchestrator Test Complete!")

if __name__ == "__main__":
    # Run the orchestrator test
    asyncio.run(main())
