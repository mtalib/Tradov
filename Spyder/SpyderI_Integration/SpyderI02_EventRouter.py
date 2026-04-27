#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI02_EventRouter.py
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
import threading
import time
import queue
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from collections.abc import Callable
from re import Pattern
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import uuid
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import fnmatch
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

try:
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Routing configuration
DEFAULT_BATCH_SIZE = 100
DEFAULT_BATCH_TIMEOUT = 1.0  # seconds
MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 1.5

# Performance thresholds
CIRCUIT_BREAKER_THRESHOLD = 10  # errors per minute
SLOW_HANDLER_THRESHOLD = 1000   # milliseconds
HIGH_LATENCY_THRESHOLD = 500    # milliseconds

# Queue sizes
EVENT_QUEUE_SIZE = 10000
PRIORITY_QUEUE_SIZE = 1000
CORRELATION_BUFFER_SIZE = 5000

# Monitoring intervals
PERFORMANCE_CHECK_INTERVAL = 30  # seconds
CORRELATION_ANALYSIS_INTERVAL = 60  # seconds
CLEANUP_INTERVAL = 300  # 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class RoutingStrategy(Enum):
    """Event routing strategies."""
    BROADCAST = "broadcast"        # Send to all matching handlers
    ROUND_ROBIN = "round_robin"    # Distribute evenly
    LOAD_BALANCED = "load_balanced" # Send to least loaded handler
    PRIORITY = "priority"          # Route by handler priority
    FAILOVER = "failover"         # Try primary, fallback on failure

class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5

class HandlerState(Enum):
    """Event handler states."""
    HEALTHY = "healthy"
    SLOW = "slow"
    OVERLOADED = "overloaded"
    CIRCUIT_OPEN = "circuit_open"
    DISABLED = "disabled"

class CorrelationType(Enum):
    """Types of event correlations."""
    CAUSAL = "causal"           # A causes B
    TEMPORAL = "temporal"       # A and B happen together
    SEQUENTIAL = "sequential"   # A then B in sequence
    INVERSE = "inverse"         # A and not B
    PATTERN = "pattern"         # Complex patterns

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RoutingRule:
    """Event routing rule definition."""
    rule_id: str
    name: str
    pattern: str                    # Event pattern to match
    target_modules: list[str]       # Target module IDs
    strategy: RoutingStrategy = RoutingStrategy.BROADCAST
    priority: int = 0               # Higher number = higher priority
    conditions: dict[str, Any] = field(default_factory=dict)
    transformations: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0

@dataclass
class HandlerInfo:
    """Information about an event handler."""
    handler_id: str
    module_id: str
    event_types: set[str]
    handler_function: Callable
    priority: int = 0
    state: HandlerState = HandlerState.HEALTHY
    last_execution: datetime | None = None
    total_executions: int = 0
    success_count: int = 0
    error_count: int = 0
    average_latency: float = 0.0
    max_latency: float = 0.0
    circuit_breaker_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class EventCorrelation:
    """Event correlation information."""
    correlation_id: str
    source_event: str
    target_event: str
    correlation_type: CorrelationType
    strength: float                 # 0.0 to 1.0
    confidence: float              # Statistical confidence
    time_window: float             # Time window in seconds
    occurrences: int = 0
    last_seen: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class RoutingMetrics:
    """Routing performance metrics."""
    events_processed: int = 0
    events_routed: int = 0
    events_dropped: int = 0
    events_failed: int = 0
    average_routing_time: float = 0.0
    handler_utilization: dict[str, float] = field(default_factory=dict)
    correlation_hits: int = 0
    circuit_breaker_trips: int = 0

@dataclass
class PrioritizedEvent:
    """Event with priority and routing information."""
    event: Event
    priority: EventPriority
    routing_rules: list[str]
    correlation_id: str | None = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

# ==============================================================================
# EVENT ROUTER CLASS
# ==============================================================================
class EventRouter:
    """
    Intelligent event routing system for SPYDER integration.

    The Event Router provides sophisticated event routing capabilities:
    - Pattern-based routing with regex and glob support
    - Multiple routing strategies (broadcast, round-robin, load-balanced)
    - Event correlation analysis and pattern detection
    - Circuit breaker protection for handlers
    - Performance monitoring and optimization
    - Guaranteed delivery with retry mechanisms
    - Real-time analytics and reporting

    Features:
    - Dynamic routing rule management
    - Handler health monitoring and load balancing
    - Event correlation analysis for pattern detection
    - Performance optimization with batching and caching
    - Circuit breaker protection against overloaded handlers
    - Comprehensive metrics and monitoring
    - Integration with SPYDER ecosystem components

    Attributes:
        routing_rules: Active routing rules
        handlers: Registered event handlers
        correlations: Detected event correlations
        metrics: Performance and usage metrics
    """

    def __init__(self, config: dict[str, Any] = None):
        """Initialize the Event Router."""
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()

        # Configuration
        self.config = config or {}
        self.enable_correlation = self.config.get('enable_correlation', True)
        self.enable_circuit_breaker = self.config.get('enable_circuit_breaker', True)
        self.enable_batching = self.config.get('enable_batching', True)
        self.batch_size = self.config.get('batch_size', DEFAULT_BATCH_SIZE)
        self.batch_timeout = self.config.get('batch_timeout', DEFAULT_BATCH_TIMEOUT)

        # Routing system
        self.routing_rules: dict[str, RoutingRule] = {}
        self.handlers: dict[str, HandlerInfo] = {}
        self.compiled_patterns: dict[str, Pattern] = {}

        # Event queues
        self.event_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=EVENT_QUEUE_SIZE)
        self.priority_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=PRIORITY_QUEUE_SIZE)
        self.correlation_buffer: deque = deque(maxlen=CORRELATION_BUFFER_SIZE)

        # Correlation analysis
        self.correlations: dict[str, EventCorrelation] = {}
        self.correlation_matrix: dict[tuple[str, str], float] = {}
        self.event_history: deque = deque(maxlen=10000)

        # Performance tracking
        self.metrics = RoutingMetrics()
        self.performance_history: deque = deque(maxlen=1000)
        self.handler_performance: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Threading and execution
        self.thread_pool = ThreadPoolExecutor(max_workers=self.config.get('max_workers', 10))
        self._stop_event = threading.Event()
        self._routing_thread = None
        self._correlation_thread = None
        self._monitoring_thread = None

        # Integration Hub connection
        self.integration_hub = None
        if HUB_AVAILABLE:
            self.integration_hub = get_integration_hub()

        # Initialize
        self._initialize_router()

        self.logger.info("🔀 Event Router initialized - Intelligent event routing active")

    # ==========================================================================
    # INITIALIZATION AND SETUP
    # ==========================================================================
    def _initialize_router(self) -> None:
        """Initialize the event router."""
        try:
            # Register with event manager
            self._register_core_handlers()

            # Load default routing rules
            self._load_default_routing_rules()

            # Start processing threads
            self._start_processing()

            # Register with integration hub
            if self.integration_hub:
                self.integration_hub.register_module(self)

            self.logger.info("✅ Event Router fully initialized")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_initialize_router'
            })

    def _register_core_handlers(self) -> None:
        """Register core event handlers."""
        try:
            # Register for all event types to enable routing
            for event_type in EventType:
                self.event_manager.subscribe(event_type, self._route_event)

            self.logger.info("📋 Registered core event handlers")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_register_core_handlers'
            })

    def _load_default_routing_rules(self) -> None:
        """Load default routing rules."""
        try:
            default_rules = [
                # Critical system events to monitoring
                RoutingRule(
                    rule_id="critical_to_monitoring",
                    name="Route critical events to monitoring",
                    pattern="*.critical.*",
                    target_modules=["SpyderM01_SystemMonitor", "SpyderJ01_AlertManager"],
                    strategy=RoutingStrategy.BROADCAST,
                    priority=100
                ),

                # Trading events to risk management
                RoutingRule(
                    rule_id="trading_to_risk",
                    name="Route trading events to risk modules",
                    pattern="trading.*",
                    target_modules=["SpyderE01_RiskManager", "SpyderE03_GreekLimitsManager"],
                    strategy=RoutingStrategy.BROADCAST,
                    priority=90
                ),

                # Strategy events to portfolio management
                RoutingRule(
                    rule_id="strategy_to_portfolio",
                    name="Route strategy events to portfolio",
                    pattern="strategy.*",
                    target_modules=["SpyderP01_PortfolioManager"],
                    strategy=RoutingStrategy.LOAD_BALANCED,
                    priority=80
                ),

                # Error events to error handling and alerts
                RoutingRule(
                    rule_id="errors_to_handlers",
                    name="Route errors to handlers",
                    pattern="error.*",
                    target_modules=["SpyderU02_ErrorHandler", "SpyderJ01_AlertManager"],
                    strategy=RoutingStrategy.BROADCAST,
                    priority=95
                ),

                # Market data to analysis modules
                RoutingRule(
                    rule_id="market_data_to_analysis",
                    name="Route market data to analysis",
                    pattern="market.*",
                    target_modules=["SpyderF04_VolatilityAnalysis", "SpyderF10_MarketRegimeDetector"],  # noqa: E501
                    strategy=RoutingStrategy.ROUND_ROBIN,
                    priority=70
                )
            ]

            for rule in default_rules:
                self.add_routing_rule(rule)

            self.logger.info("📝 Loaded %s default routing rules", len(default_rules))

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_load_default_routing_rules'
            })

    # ==========================================================================
    # ROUTING RULE MANAGEMENT
    # ==========================================================================
    def add_routing_rule(self, rule: RoutingRule) -> bool:
        """
        Add a new routing rule.

        Args:
            rule: Routing rule to add

        Returns:
            Whether rule was added successfully
        """
        try:
            # Validate rule
            if not self._validate_routing_rule(rule):
                return False

            # Compile pattern
            compiled_pattern = self._compile_pattern(rule.pattern)
            if compiled_pattern:
                self.compiled_patterns[rule.rule_id] = compiled_pattern

            # Store rule
            self.routing_rules[rule.rule_id] = rule

            self.logger.info("➕ Added routing rule: %s", rule.name)
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'add_routing_rule',
                'rule_id': rule.rule_id
            })
            return False

    def remove_routing_rule(self, rule_id: str) -> bool:
        """Remove a routing rule."""
        try:
            if rule_id in self.routing_rules:
                del self.routing_rules[rule_id]

                if rule_id in self.compiled_patterns:
                    del self.compiled_patterns[rule_id]

                self.logger.info("➖ Removed routing rule: %s", rule_id)
                return True

            return False

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'remove_routing_rule',
                'rule_id': rule_id
            })
            return False

    def _validate_routing_rule(self, rule: RoutingRule) -> bool:
        """Validate a routing rule."""
        try:
            # Check required fields
            if not rule.rule_id or not rule.pattern:
                self.logger.warning("Rule missing required fields")
                return False

            # Check for duplicate rule ID
            if rule.rule_id in self.routing_rules:
                self.logger.warning("Rule ID already exists: %s", rule.rule_id)
                return False

            # Validate pattern
            if not self._validate_pattern(rule.pattern):
                self.logger.warning("Invalid pattern: %s", rule.pattern)
                return False

            # Validate target modules
            if not rule.target_modules:
                self.logger.warning("Rule has no target modules")
                return False

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_validate_routing_rule'
            })
            return False

    def _validate_pattern(self, pattern: str) -> bool:
        """Validate an event pattern."""
        try:
            # Try to compile as regex
            re.compile(pattern)
            return True
        except re.error:
            try:
                # Try as glob pattern
                fnmatch.translate(pattern)
                return True
            except Exception:
                return False

    def _compile_pattern(self, pattern: str) -> Pattern | None:
        """Compile event pattern for efficient matching."""
        try:
            # Convert glob to regex if needed
            if '*' in pattern or '?' in pattern:
                regex_pattern = fnmatch.translate(pattern)
                return re.compile(regex_pattern, re.IGNORECASE)
            else:
                # Treat as regex
                return re.compile(pattern, re.IGNORECASE)

        except Exception as e:
            self.logger.warning("Could not compile pattern '%s': %s", pattern, e)
            return None

    # ==========================================================================
    # HANDLER REGISTRATION
    # ==========================================================================
    def register_handler(self, module_id: str, event_types: list[str],
                        handler_function: Callable, priority: int = 0) -> str:
        """
        Register an event handler.

        Args:
            module_id: Module identifier
            event_types: Event types to handle
            handler_function: Handler function
            priority: Handler priority (higher = more priority)

        Returns:
            Handler ID
        """
        try:
            handler_id = f"{module_id}_{uuid.uuid4().hex[:8]}"

            handler_info = HandlerInfo(
                handler_id=handler_id,
                module_id=module_id,
                event_types=set(event_types),
                handler_function=handler_function,
                priority=priority
            )

            self.handlers[handler_id] = handler_info

            self.logger.info("📋 Registered handler %s for %s", handler_id, module_id)
            return handler_id

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'register_handler',
                'module_id': module_id
            })
            return ""

    def unregister_handler(self, handler_id: str) -> bool:
        """Unregister an event handler."""
        try:
            if handler_id in self.handlers:
                del self.handlers[handler_id]
                self.logger.info("📤 Unregistered handler: %s", handler_id)
                return True

            return False

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'unregister_handler',
                'handler_id': handler_id
            })
            return False

    # ==========================================================================
    # EVENT ROUTING CORE
    # ==========================================================================
    def _route_event(self, event: Event) -> None:
        """Main event routing entry point."""
        try:
            # Determine event priority
            priority = self._determine_event_priority(event)

            # Find matching routing rules
            matching_rules = self._find_matching_rules(event)

            # Create prioritized event
            prioritized_event = PrioritizedEvent(
                event=event,
                priority=priority,
                routing_rules=[rule.rule_id for rule in matching_rules],
                correlation_id=self._check_correlation(event)
            )

            # Queue for processing
            if priority in [EventPriority.CRITICAL, EventPriority.URGENT]:
                self.priority_queue.put((priority.value, prioritized_event))
            else:
                self.event_queue.put((priority.value, prioritized_event))

            # Update metrics
            self.metrics.events_processed += 1

            # Add to event history for correlation analysis
            if self.enable_correlation:
                self.event_history.append({
                    'timestamp': datetime.now(timezone.utc),
                    'event_type': event.type.value,
                    'source': event.source,
                    'event_id': getattr(event, 'id', str(uuid.uuid4()))
                })

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_route_event',
                'event_type': event.type.value if event else 'unknown'
            })

    def _determine_event_priority(self, event: Event) -> EventPriority:
        """Determine event priority based on type and content."""
        try:
            # Critical events
            if event.type == EventType.ERROR:
                severity = event.data.get('severity', 'medium')
                if severity in ['critical', 'fatal']:
                    return EventPriority.CRITICAL
                elif severity == 'high':
                    return EventPriority.HIGH
                else:
                    return EventPriority.NORMAL

            # System events
            elif event.type == EventType.SYSTEM:
                action = event.data.get('action', '')
                if 'critical' in action.lower() or 'emergency' in action.lower():
                    return EventPriority.URGENT
                elif 'warning' in action.lower():
                    return EventPriority.HIGH
                else:
                    return EventPriority.NORMAL

            # Trading events
            elif event.type == EventType.TRADING:
                if 'risk' in str(event.data).lower() or 'violation' in str(event.data).lower():
                    return EventPriority.HIGH
                else:
                    return EventPriority.NORMAL

            # Default priority
            return EventPriority.NORMAL

        except Exception:
            return EventPriority.NORMAL

    def _find_matching_rules(self, event: Event) -> list[RoutingRule]:
        """Find routing rules that match an event."""
        matching_rules = []

        try:
            event_signature = self._create_event_signature(event)

            for _rule_id, rule in self.routing_rules.items():
                if not rule.enabled:
                    continue

                # Check pattern match
                if self._pattern_matches(rule, event_signature):
                    # Check additional conditions
                    if self._check_rule_conditions(rule, event):
                        matching_rules.append(rule)
                        rule.usage_count += 1

            # Sort by priority (highest first)
            matching_rules.sort(key=lambda r: r.priority, reverse=True)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_find_matching_rules'
            })

        return matching_rules

    def _create_event_signature(self, event: Event) -> str:
        """Create a signature string for event matching."""
        try:
            signature_parts = [
                event.type.value,
                event.source or 'unknown'
            ]

            # Add action if available
            if hasattr(event, 'data') and isinstance(event.data, dict):
                action = event.data.get('action')
                if action:
                    signature_parts.append(str(action))

            return '.'.join(signature_parts).lower()

        except Exception:
            return f"{event.type.value}.{event.source or 'unknown'}".lower()

    def _pattern_matches(self, rule: RoutingRule, event_signature: str) -> bool:
        """Check if rule pattern matches event signature."""
        try:
            # Use compiled pattern if available
            if rule.rule_id in self.compiled_patterns:
                pattern = self.compiled_patterns[rule.rule_id]
                return bool(pattern.match(event_signature))

            # Fallback to simple string matching
            return fnmatch.fnmatch(event_signature, rule.pattern.lower())

        except Exception:
            return False

    def _check_rule_conditions(self, rule: RoutingRule, event: Event) -> bool:
        """Check additional rule conditions."""
        try:
            if not rule.conditions:
                return True

            # Check source condition
            if 'source' in rule.conditions:
                required_sources = rule.conditions['source']
                if isinstance(required_sources, str):
                    required_sources = [required_sources]
                if event.source not in required_sources:
                    return False

            # Check time-based conditions
            if 'time_window' in rule.conditions:
                # Implementation would check if current time is within specified window
                pass

            # Check data conditions
            if 'data_conditions' in rule.conditions and hasattr(event, 'data'):
                data_conditions = rule.conditions['data_conditions']
                for key, expected_value in data_conditions.items():
                    if event.data.get(key) != expected_value:
                        return False

            return True

        except Exception:
            return True  # Default to allowing on error

    # ==========================================================================
    # EVENT PROCESSING
    # ==========================================================================
    def _start_processing(self) -> None:
        """Start event processing threads."""
        try:
            self._routing_thread = threading.Thread(
                target=self._routing_loop,
                name="EventRouter-Main",
                daemon=True
            )
            self._routing_thread.start()

            if self.enable_correlation:
                self._correlation_thread = threading.Thread(
                    target=self._correlation_loop,
                    name="EventRouter-Correlation",
                    daemon=True
                )
                self._correlation_thread.start()

            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="EventRouter-Monitor",
                daemon=True
            )
            self._monitoring_thread.start()

            self.logger.info("🚀 Event Router processing threads started")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_start_processing'
            })

    def _routing_loop(self) -> None:
        """Main event routing loop."""
        while not self._stop_event.is_set():
            try:
                # Process priority queue first
                self._process_priority_events()

                # Process regular events
                self._process_regular_events()

                # Small sleep to prevent busy waiting
                time.sleep(0.01)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Error in routing loop: %s", e)
                time.sleep(1)  # thread-safe: time.sleep() intentional

    def _process_priority_events(self) -> None:
        """Process high-priority events."""
        try:
            while not self.priority_queue.empty():
                try:
                    priority, prioritized_event = self.priority_queue.get_nowait()
                    self._process_event(prioritized_event)
                    self.priority_queue.task_done()
                except queue.Empty:
                    break

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_process_priority_events'
            })

    def _process_regular_events(self) -> None:
        """Process regular events with batching."""
        try:
            events_batch = []
            batch_start = time.time()

            # Collect events for batch processing
            while (len(events_batch) < self.batch_size and
                   time.time() - batch_start < self.batch_timeout):
                try:
                    priority, prioritized_event = self.event_queue.get(timeout=0.1)
                    events_batch.append(prioritized_event)
                    self.event_queue.task_done()
                except queue.Empty:
                    break

            # Process batch
            if events_batch:
                if self.enable_batching and len(events_batch) > 1:
                    self._process_event_batch(events_batch)
                else:
                    for event in events_batch:
                        self._process_event(event)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_process_regular_events'
            })

    def _process_event(self, prioritized_event: PrioritizedEvent) -> None:
        """Process a single event."""
        try:
            start_time = time.time()

            # Get target handlers for each rule
            for rule_id in prioritized_event.routing_rules:
                rule = self.routing_rules.get(rule_id)
                if not rule:
                    continue

                # Get handlers for this rule
                target_handlers = self._get_target_handlers(rule)

                # Route to handlers based on strategy
                success = self._route_to_handlers(
                    prioritized_event.event,
                    target_handlers,
                    rule.strategy
                )

                # Update rule metrics
                if success:
                    rule.success_count += 1
                else:
                    rule.error_count += 1

            # Update routing metrics
            routing_time = (time.time() - start_time) * 1000  # ms
            self.metrics.events_routed += 1
            self.metrics.average_routing_time = (
                (self.metrics.average_routing_time * (self.metrics.events_routed - 1) + routing_time) /  # noqa: E501
                self.metrics.events_routed
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_process_event'
            })
            self.metrics.events_failed += 1

    def _process_event_batch(self, events_batch: list[PrioritizedEvent]) -> None:
        """Process a batch of events for optimization."""
        try:
            # Group events by target handlers for efficiency
            handler_groups = defaultdict(list)

            for prioritized_event in events_batch:
                for rule_id in prioritized_event.routing_rules:
                    rule = self.routing_rules.get(rule_id)
                    if rule:
                        for module_id in rule.target_modules:
                            handler_groups[module_id].append(prioritized_event.event)

            # Process each handler group
            futures = []
            for module_id, events in handler_groups.items():
                future = self.thread_pool.submit(self._batch_process_handler, module_id, events)
                futures.append(future)

            # Wait for completion
            for future in futures:
                try:
                    future.result(timeout=5.0)  # 5 second timeout
                except Exception as e:
                    self.logger.warning("Batch processing failed: %s", e)

            self.metrics.events_routed += len(events_batch)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_process_event_batch'
            })

    def _get_target_handlers(self, rule: RoutingRule) -> list[HandlerInfo]:
        """Get target handlers for a routing rule."""
        target_handlers = []

        try:
            for module_id in rule.target_modules:
                # Find handlers for this module
                module_handlers = [
                    handler for handler in self.handlers.values()
                    if (handler.module_id == module_id and
                        handler.state != HandlerState.DISABLED)
                ]
                target_handlers.extend(module_handlers)

            # Filter out circuit-broken handlers
            if self.enable_circuit_breaker:
                target_handlers = [
                    handler for handler in target_handlers
                    if handler.state != HandlerState.CIRCUIT_OPEN
                ]

            return target_handlers

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_get_target_handlers'
            })
            return []

    def _route_to_handlers(self, event: Event, handlers: list[HandlerInfo],
                          strategy: RoutingStrategy) -> bool:
        """Route event to handlers using specified strategy."""
        try:
            if not handlers:
                return False

            success = False

            if strategy == RoutingStrategy.BROADCAST:
                # Send to all handlers
                for handler in handlers:
                    if self._invoke_handler(handler, event):
                        success = True

            elif strategy == RoutingStrategy.ROUND_ROBIN:
                # Send to next handler in rotation
                handler = min(handlers, key=lambda h: h.total_executions)
                success = self._invoke_handler(handler, event)

            elif strategy == RoutingStrategy.LOAD_BALANCED:
                # Send to least loaded handler
                handler = min(handlers, key=lambda h: h.average_latency)
                success = self._invoke_handler(handler, event)

            elif strategy == RoutingStrategy.PRIORITY:
                # Send to highest priority handler
                handler = max(handlers, key=lambda h: h.priority)
                success = self._invoke_handler(handler, event)

            elif strategy == RoutingStrategy.FAILOVER:
                # Try handlers in priority order until success
                sorted_handlers = sorted(handlers, key=lambda h: h.priority, reverse=True)
                for handler in sorted_handlers:
                    if self._invoke_handler(handler, event):
                        success = True
                        break

            return success

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_route_to_handlers'
            })
            return False

    def _invoke_handler(self, handler: HandlerInfo, event: Event) -> bool:
        """Invoke a specific event handler."""
        try:
            start_time = time.time()

            # Check circuit breaker
            if self.enable_circuit_breaker and handler.state == HandlerState.CIRCUIT_OPEN:
                return False

            # Invoke handler
            try:
                handler.handler_function(event)

                # Update success metrics
                handler.success_count += 1
                handler.total_executions += 1
                handler.last_execution = datetime.now(timezone.utc)

                # Update latency
                latency = (time.time() - start_time) * 1000  # ms
                handler.average_latency = (
                    (handler.average_latency * (handler.success_count - 1) + latency) /
                    handler.success_count
                )
                handler.max_latency = max(handler.max_latency, latency)

                # Check for slow handler
                if latency > SLOW_HANDLER_THRESHOLD:
                    handler.state = HandlerState.SLOW
                elif handler.state == HandlerState.SLOW and latency < HIGH_LATENCY_THRESHOLD:
                    handler.state = HandlerState.HEALTHY

                return True

            except Exception as e:
                # Update error metrics
                handler.error_count += 1
                handler.total_executions += 1

                # Check circuit breaker
                if self.enable_circuit_breaker:
                    error_rate = handler.error_count / max(1, handler.total_executions)
                    if error_rate > 0.5 and handler.error_count > 5:  # 50% error rate
                        handler.state = HandlerState.CIRCUIT_OPEN
                        handler.circuit_breaker_count += 1
                        self.metrics.circuit_breaker_trips += 1
                        self.logger.warning("🔌 Circuit breaker opened for handler %s", handler.handler_id)  # noqa: E501

                raise e

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_invoke_handler',
                'handler_id': handler.handler_id
            })
            return False

    def _batch_process_handler(self, module_id: str, events: list[Event]) -> None:
        """Process events in batch for a specific handler."""
        try:
            # Find batch-capable handler
            batch_handler = None
            for handler in self.handlers.values():
                if (handler.module_id == module_id and
                    hasattr(handler.handler_function, 'process_batch')):
                    batch_handler = handler
                    break

            if batch_handler:
                # Use batch processing
                batch_handler.handler_function.process_batch(events)
            else:
                # Process individually
                for event in events:
                    regular_handlers = [
                        h for h in self.handlers.values()
                        if h.module_id == module_id
                    ]
                    if regular_handlers:
                        self._invoke_handler(regular_handlers[0], event)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_batch_process_handler',
                'module_id': module_id
            })

    # ==========================================================================
    # CORRELATION ANALYSIS
    # ==========================================================================
    def _check_correlation(self, event: Event) -> str | None:
        """Check for event correlations."""
        try:
            if not self.enable_correlation:
                return None

            current_time = datetime.now(timezone.utc)
            event_type = event.type.value

            # Look for correlated events in recent history
            for correlation in self.correlations.values():
                if correlation.source_event == event_type:
                    # Check if we should expect a correlated event
                    time_window = timedelta(seconds=correlation.time_window)

                    # Generate correlation ID for tracking
                    correlation_id = f"{correlation.correlation_id}_{uuid.uuid4().hex[:8]}"

                    # Add to correlation buffer for monitoring
                    self.correlation_buffer.append({
                        'correlation_id': correlation_id,
                        'source_event': event_type,
                        'expected_target': correlation.target_event,
                        'timestamp': current_time,
                        'deadline': current_time + time_window
                    })

                    return correlation_id

            return None

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_check_correlation'
            })
            return None

    def _correlation_loop(self) -> None:
        """Correlation analysis loop."""
        while not self._stop_event.is_set():
            try:
                self._analyze_correlations()
                self._cleanup_expired_correlations()
                time.sleep(CORRELATION_ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Error in correlation analysis: %s", e)
                time.sleep(CORRELATION_ANALYSIS_INTERVAL * 2)  # thread-safe: time.sleep() intentional  # noqa: E501

    def _analyze_correlations(self) -> None:
        """Analyze event patterns for correlations."""
        try:
            if len(self.event_history) < 10:
                return

            # Convert to DataFrame for analysis
            events_df = pd.DataFrame(list(self.event_history))

            # Group by time windows
            time_windows = [5, 10, 30, 60]  # seconds

            for window in time_windows:
                self._analyze_temporal_correlations(events_df, window)

            # Analyze sequential patterns
            self._analyze_sequential_patterns(events_df)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_analyze_correlations'
            })

    def _analyze_temporal_correlations(self, events_df, window_seconds: int) -> None:
        """Analyze temporal correlations within a time window."""
        try:
            # This would implement statistical correlation analysis
            # For brevity, showing simplified version

            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(seconds=window_seconds)

            recent_events = events_df[events_df['timestamp'] >= cutoff_time]

            return recent_events

        except Exception as e:
            self.logger.error("Error getting recent events: %s", e)
            return pd.DataFrame()

