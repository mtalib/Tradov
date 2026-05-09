#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI06_AgentMessageBus.py
Group: I (Integration)
Purpose: Message bus for inter-agent communication
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 15:00:00

Description:
    This module provides a high-performance message bus for communication between
    all AI agents (X01-X15) and other system components. It implements pub/sub
    messaging, priority queuing, topic-based routing, and ensures reliable
    message delivery across the distributed agent ecosystem.

Key Features:
    - Publish/Subscribe messaging pattern
    - Topic-based message routing
    - Priority message queuing
    - Request/Reply patterns
    - Message persistence and replay
    - Dead letter queue for failed messages
    - Performance monitoring and metrics
    - Circuit breaker for fault tolerance
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import copy
import json
import os
import uuid
import pickle
import threading
import queue
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

try:
    from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
        extract_agent_handoff_envelope,
        validate_agent_handoff_envelope,
    )
    AGENT_HANDOFF_SCHEMA_AVAILABLE = True
except Exception:
    AGENT_HANDOFF_SCHEMA_AVAILABLE = False

    def extract_agent_handoff_envelope(payload):
        return None, None

    def validate_agent_handoff_envelope(envelope, schema_name=None):
        return True, None

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_QUEUE_SIZE = 10000
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
DEFAULT_TTL = 60  # 60 seconds
MAX_RETRIES = 3
DEAD_LETTER_THRESHOLD = 5
CIRCUIT_BREAKER_THRESHOLD = 10
CIRCUIT_BREAKER_TIMEOUT = 30  # seconds
DEFAULT_SHADOW_VALIDATION_REQUIRED_TOPICS = {
    "meta.decisions",
    "meta.orchestration",
    "signals.validated",
}
DEFAULT_SHADOW_VALIDATION_TOPIC_PREFIXES = (
    "meta.",
    "signals.",
    "market.",
    "risk.",
)
DEFAULT_AGENT_POLICY_ENFORCE_SENDER_PATTERNS = (
    "Y[0-9][0-9]_*",
    "X[0-9][0-9]_*",
)
DEFAULT_AGENT_POLICY_ENFORCE_TOPIC_PREFIXES = (
    "meta.",
    "signals.",
    "execution.",
    "strategy.",
)
DEFAULT_AGENT_POLICY_ENFORCE_TOPICS = {
    "meta.decisions",
    "meta.orchestration",
    "signals.validated",
}
DEFAULT_AGENT_HANDOFF_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "agent_handoff_policy.json"
DEFAULT_AGENT_HANDOFF_POLICY = {
    "version": "1.0",
    "enforcement": {
        "paper_mode": True,
        "live_mode": False,
        "default_action_paper": "deny",
        "default_action_live": "allow",
        "enforce_sender_patterns": list(DEFAULT_AGENT_POLICY_ENFORCE_SENDER_PATTERNS),
        "enforce_topic_prefixes": list(DEFAULT_AGENT_POLICY_ENFORCE_TOPIC_PREFIXES),
        "enforce_topics": list(DEFAULT_AGENT_POLICY_ENFORCE_TOPICS),
    },
    "role_bindings": {
        "Y00_*": "observe",
        "Y01_*": "advisory",
        "Y02_*": "execution_advisory",
        "Y03_*": "advisory",
        "Y04_*": "advisory",
        "Y05_*": "execution_advisory",
        "Y06_*": "advisory",
        "Y07_*": "observe",
        "Y08_*": "execution_advisory",
        "Y09_*": "observe",
        "Y10_*": "observe",
        "X14_*": "execution_advisory",
        "X*": "advisory",
    },
    "role_permissions": {
        "observe": {
            "allow_topics": ["system.*", "meta.health", "meta.heartbeat", "market.regime"],
            "allow_actions": ["observe", "status", "heartbeat", "regime_update"],
            "deny_topics": ["signals.validated", "execution.*"],
            "deny_actions": ["execution_advice", "execution_order", "execute"],
        },
        "advisory": {
            "allow_topics": ["meta.*", "market.*", "risk.*", "strategy.recommendation"],
            "allow_actions": ["observe", "status", "regime_update", "decision", "escalation", "signal"],
            "deny_topics": ["execution.*"],
            "deny_actions": ["execution_advice", "execution_order", "execute"],
        },
        "execution_advisory": {
            "allow_topics": [
                "meta.*",
                "market.*",
                "risk.*",
                "signals.validated",
                "strategy.*",
                "execution.intent",
            ],
            "allow_actions": [
                "observe",
                "status",
                "regime_update",
                "decision",
                "escalation",
                "signal",
                "execution_advice",
            ],
            "deny_topics": ["execution.orders", "execution.submit", "execution.route"],
            "deny_actions": ["execution_order", "execute"],
        },
        "execution_authorized": {
            "allow_topics": ["meta.*", "market.*", "risk.*", "signals.*", "strategy.*", "execution.*"],
            "allow_actions": [
                "observe",
                "status",
                "regime_update",
                "decision",
                "escalation",
                "signal",
                "execution_advice",
                "execution_order",
                "execute",
            ],
            "deny_topics": [],
            "deny_actions": [],
        },
    },
}

# Topic definitions
TOPICS = {
    'market': 'market.*',
    'signals': 'signals.*',
    'risk': 'risk.*',
    'execution': 'execution.*',
    'performance': 'performance.*',
    'system': 'system.*',
    'alerts': 'alerts.*',
    'strategy': 'strategy.*',
    'research': 'research.*'
}

# ==============================================================================
# ENUMS
# ==============================================================================
class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BULK = 4  # Lowest priority

class MessageType(Enum):
    """Types of messages"""
    PUBLISH = "publish"
    REQUEST = "request"
    REPLY = "reply"
    BROADCAST = "broadcast"
    COMMAND = "command"
    EVENT = "event"
    HEARTBEAT = "heartbeat"

class DeliveryMode(Enum):
    """Message delivery modes"""
    AT_MOST_ONCE = "at_most_once"  # Fire and forget
    AT_LEAST_ONCE = "at_least_once"  # Retry until ack
    EXACTLY_ONCE = "exactly_once"  # Guaranteed single delivery

class SubscriberState(Enum):
    """Subscriber connection states"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISCONNECTED = "disconnected"
    CIRCUIT_OPEN = "circuit_open"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Message:
    """Message structure for the bus"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    sender: str = ""
    message_type: MessageType = MessageType.PUBLISH
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Any = None
    headers: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = DEFAULT_TTL
    correlation_id: str | None = None
    reply_to: str | None = None
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE
    retry_count: int = 0

    def __lt__(self, other):
        """For priority queue comparison"""
        return self.priority.value < other.priority.value

    def is_expired(self) -> bool:
        """Check if message has expired"""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds() > self.ttl

    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(asdict(self), default=str)

@dataclass
class Subscriber:
    """Subscriber information"""
    id: str
    name: str
    topics: list[str]
    callback: Callable
    filter_func: Callable | None = None
    state: SubscriberState = SubscriberState.ACTIVE
    message_count: int = 0
    error_count: int = 0
    last_message: datetime | None = None
    circuit_breaker_opens: int = 0

@dataclass
class TopicStats:
    """Statistics for a topic"""
    topic: str
    message_count: int = 0
    subscriber_count: int = 0
    avg_processing_time: float = 0.0
    error_rate: float = 0.0
    last_message: datetime | None = None

@dataclass
class BusMetrics:
    """Message bus metrics"""
    total_messages: int = 0
    delivered_messages: int = 0
    failed_messages: int = 0
    active_subscribers: int = 0
    topics_count: int = 0
    queue_size: int = 0
    dead_letter_count: int = 0
    avg_latency: float = 0.0
    throughput: float = 0.0


class PublishReceipt(str):
    """Awaitable publish receipt for sync/async compatibility.

    ``publish()`` now executes synchronously (so legacy sync call-sites work),
    but this receipt can still be awaited by existing async call-sites that do
    ``await bus.publish(...)``.
    """

    def __new__(cls, message_id: str):
        return super().__new__(cls, message_id)

    def __await__(self):
        async def _return_value() -> str:
            return str(self)

        return _return_value().__await__()

# ==============================================================================
# MAIN MESSAGE BUS CLASS
# ==============================================================================
class AgentMessageBus:
    """
    High-performance message bus for agent communication.

    Provides reliable pub/sub messaging with priority queuing,
    topic-based routing, and fault tolerance.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the message bus"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        self._worker_thread = None

        # Message queues
        self.priority_queue = queue.PriorityQueue(maxsize=MAX_QUEUE_SIZE)
        self.dead_letter_queue = deque(maxlen=1000)
        self.pending_replies = {}  # correlation_id -> future

        # Subscriptions
        self.subscribers = {}  # subscriber_id -> Subscriber
        self.topic_subscribers = defaultdict(set)  # topic -> set of subscriber_ids

        # Topic management
        self.topic_stats = {}  # topic -> TopicStats
        self.topic_patterns = {}  # pattern -> compiled regex

        # Message history
        self.message_history = deque(maxlen=10000)
        self.reply_timeout = self.config.get('reply_timeout', 30)

        # Metrics
        self.metrics = BusMetrics()
        self.latency_history = deque(maxlen=1000)

        # Persistence
        self.persist_messages = self.config.get('persist', False)
        self.persistence_path = Path(self.config.get('persistence_path', 'data/messages'))

        # Phase 1: shadow-mode contract validation (advisory only)
        self.shadow_validation_enabled = bool(
            self.config.get("shadow_validation_agent_handoffs", True)
        )
        self.shadow_validation_required_topics = set(
            self.config.get(
                "shadow_validation_required_topics",
                list(DEFAULT_SHADOW_VALIDATION_REQUIRED_TOPICS),
            )
        )
        self.shadow_validation_topic_prefixes = tuple(
            self.config.get(
                "shadow_validation_topic_prefixes",
                list(DEFAULT_SHADOW_VALIDATION_TOPIC_PREFIXES),
            )
        )
        self.shadow_validation_stats: dict[str, int] = {
            "valid": 0,
            "invalid": 0,
            "missing": 0,
            "unavailable": 0,
        }

        # Phase 2: paper-mode sender-role/topic/action policy enforcement.
        self.agent_handoff_policy = self._load_agent_handoff_policy()
        self.trading_mode = self._resolve_trading_mode()
        self.policy_enforcement_stats: dict[str, int] = {
            "allowed": 0,
            "blocked": 0,
            "skipped": 0,
        }

        # Start worker
        self._start_worker()

        self.logger.info("Agent Message Bus initialized mode=%s", self.trading_mode)

    def _resolve_trading_mode(self) -> str:
        """Resolve operating mode to "paper" or "live"."""
        paper_mode = self.config.get("paper_mode")
        if isinstance(paper_mode, bool):
            return "paper" if paper_mode else "live"

        raw_mode_candidates = (
            self.config.get("trading_mode"),
            self.config.get("run_mode"),
            self.config.get("mode"),
            os.getenv("SPYDER_TRADING_MODE"),
            os.getenv("TRADING_MODE"),
        )

        for candidate in raw_mode_candidates:
            if not candidate:
                continue

            mode = str(candidate).strip().lower()
            if mode in {"live", "production", "prod"}:
                return "live"
            if mode in {"paper", "sandbox", "sim", "simulation", "development", "dev", "test", "testing"}:
                return "paper"

        return "paper"

    def _load_agent_handoff_policy(self) -> dict[str, Any]:
        """Load policy from config, ConfigManager, or repo file fallback."""
        config_policy = self.config.get("agent_handoff_policy")
        if isinstance(config_policy, dict) and config_policy:
            return copy.deepcopy(config_policy)

        # Prefer the global ConfigManager policy if available.
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg_mgr = get_config_manager()
            cfg_policy = cfg_mgr.get("autonomous_readiness.agent_handoff_policy")
            if isinstance(cfg_policy, dict) and cfg_policy:
                return copy.deepcopy(cfg_policy)
        except Exception:
            pass

        configured_path = self.config.get("agent_handoff_policy_path")
        if isinstance(configured_path, str) and configured_path.strip():
            policy_path = Path(configured_path).expanduser()
        else:
            policy_path = DEFAULT_AGENT_HANDOFF_POLICY_PATH

        try:
            if policy_path.exists() and policy_path.is_file():
                with open(policy_path, encoding="utf-8") as fp:
                    policy = json.load(fp)
                if isinstance(policy, dict) and policy:
                    return policy
        except Exception as e:
            self.logger.warning("I06 policy load failed from %s: %s", policy_path, e)

        return copy.deepcopy(DEFAULT_AGENT_HANDOFF_POLICY)

    def _is_policy_enforcement_enabled(self) -> bool:
        """Return True when policy enforcement is active for current mode."""
        enforcement = self.agent_handoff_policy.get("enforcement", {})
        if self.trading_mode == "live":
            return bool(enforcement.get("live_mode", False))
        return bool(enforcement.get("paper_mode", True))

    def _policy_default_action(self) -> str:
        """Return policy fallback action for the current operating mode."""
        enforcement = self.agent_handoff_policy.get("enforcement", {})
        if self.trading_mode == "live":
            default_action = enforcement.get("default_action_live", "allow")
        else:
            default_action = enforcement.get("default_action_paper", "deny")
        return str(default_action).strip().lower()

    def _match_any_pattern(self, value: str, patterns: list[Any]) -> bool:
        """Return True when a value matches any wildcard pattern."""
        if not value or not isinstance(patterns, list):
            return False

        for pattern in patterns:
            if isinstance(pattern, str) and pattern and fnmatchcase(value, pattern):
                return True
        return False

    def _is_sender_in_policy_scope(self, sender: str) -> bool:
        """Limit enforcement to configured sender ID patterns."""
        enforcement = self.agent_handoff_policy.get("enforcement", {})
        sender_patterns = enforcement.get("enforce_sender_patterns")
        if not isinstance(sender_patterns, list) or not sender_patterns:
            sender_patterns = list(DEFAULT_AGENT_POLICY_ENFORCE_SENDER_PATTERNS)
        return self._match_any_pattern(sender, sender_patterns)

    def _is_topic_in_policy_scope(self, topic: str) -> bool:
        """Return True when a topic is in policy enforcement scope."""
        enforcement = self.agent_handoff_policy.get("enforcement", {})
        required_topics = enforcement.get("enforce_topics")
        if not isinstance(required_topics, list):
            required_topics = list(DEFAULT_AGENT_POLICY_ENFORCE_TOPICS)
        if topic in required_topics:
            return True

        prefixes = enforcement.get("enforce_topic_prefixes")
        if not isinstance(prefixes, list) or not prefixes:
            prefixes = list(DEFAULT_AGENT_POLICY_ENFORCE_TOPIC_PREFIXES)
        return any(isinstance(prefix, str) and topic.startswith(prefix) for prefix in prefixes)

    def _resolve_sender_role(self, sender: str) -> str | None:
        """Resolve sender role from policy role bindings (exact first, then pattern)."""
        bindings = self.agent_handoff_policy.get("role_bindings", {})
        if not isinstance(bindings, dict) or not sender:
            return None

        exact = bindings.get(sender)
        if isinstance(exact, str) and exact:
            return exact

        for pattern, role in bindings.items():
            if not isinstance(pattern, str) or not isinstance(role, str):
                continue
            if pattern == sender:
                return role
            if fnmatchcase(sender, pattern):
                return role

        return None

    def _extract_policy_action(self, payload: Any) -> str | None:
        """Extract normalized handoff action from payload metadata."""
        if not isinstance(payload, dict):
            return None

        envelope, _ = extract_agent_handoff_envelope(payload)
        if isinstance(envelope, dict):
            handoff_type = envelope.get("handoff_type")
            if isinstance(handoff_type, str) and handoff_type:
                return handoff_type.strip().lower()

        for key in ("output_type", "action", "intent"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value.strip().lower()

        return None

    def _policy_decision(self, reason_code: str) -> tuple[bool, str]:
        """Apply mode-specific default action for unresolved policy checks."""
        default_action = self._policy_default_action()
        if default_action == "allow":
            return True, f"{reason_code}_allowed_by_default"
        return False, reason_code

    def _evaluate_agent_handoff_policy(self, message: Message) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate sender-role/topic/action policy for a message publish operation."""
        context: dict[str, Any] = {
            "mode": self.trading_mode,
            "sender": message.sender,
            "topic": message.topic,
            "role": None,
            "action": None,
        }

        if not self._is_policy_enforcement_enabled():
            self.policy_enforcement_stats["skipped"] += 1
            return True, "policy_disabled", context

        if not self._is_sender_in_policy_scope(message.sender):
            self.policy_enforcement_stats["skipped"] += 1
            return True, "sender_out_of_scope", context

        if not self._is_topic_in_policy_scope(message.topic):
            self.policy_enforcement_stats["skipped"] += 1
            return True, "topic_out_of_scope", context

        role = self._resolve_sender_role(message.sender)
        context["role"] = role
        if not role:
            return (*self._policy_decision("sender_role_unbound"), context)

        role_permissions = self.agent_handoff_policy.get("role_permissions", {})
        if not isinstance(role_permissions, dict):
            return (*self._policy_decision("policy_permissions_unavailable"), context)

        permission = role_permissions.get(role)
        if not isinstance(permission, dict):
            return (*self._policy_decision("role_not_configured"), context)

        deny_topics = permission.get("deny_topics", [])
        if self._match_any_pattern(message.topic, deny_topics):
            return False, "topic_explicitly_denied", context

        allow_topics = permission.get("allow_topics", [])
        if isinstance(allow_topics, list) and allow_topics and not self._match_any_pattern(message.topic, allow_topics):
            return (*self._policy_decision("topic_not_allowed"), context)

        action = self._extract_policy_action(message.payload)
        context["action"] = action

        deny_actions = permission.get("deny_actions", [])
        if isinstance(action, str) and action and self._match_any_pattern(action, deny_actions):
            return False, "action_explicitly_denied", context

        allow_actions = permission.get("allow_actions", [])
        if isinstance(allow_actions, list) and allow_actions:
            if not action:
                return (*self._policy_decision("action_missing"), context)
            if not self._match_any_pattern(action, allow_actions):
                return (*self._policy_decision("action_not_allowed"), context)

        return True, "allowed", context

    def _start_worker(self):
        """Start the message processing worker"""
        self._worker_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._worker_thread.start()
        self.logger.debug("Message processing worker started")

    def _process_messages(self):
        """Main message processing loop"""
        while not self._shutdown.is_set():
            try:
                # Get message with timeout
                try:
                    priority, message = self.priority_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Process message
                self._deliver_message(message)

                # Update metrics
                self.metrics.queue_size = self.priority_queue.qsize()

            except Exception as e:
                self.logger.error("Error processing message: %s", e)

    def subscribe(
        self,
        subscriber_id: str,
        topics: list[str],
        callback: Callable,
        filter_func: Callable | None = None,
        name: str = None
    ) -> bool:
        """
        Subscribe to topics.

        Args:
            subscriber_id: Unique subscriber identifier
            topics: List of topics or patterns to subscribe to
            callback: Function to call with messages
            filter_func: Optional filter function
            name: Human-readable name

        Returns:
            Success status
        """
        with self._lock:
            try:
                # Create subscriber
                subscriber = Subscriber(
                    id=subscriber_id,
                    name=name or subscriber_id,
                    topics=topics,
                    callback=callback,
                    filter_func=filter_func
                )

                # Register subscriber
                self.subscribers[subscriber_id] = subscriber

                # Update topic mappings
                for topic in topics:
                    self.topic_subscribers[topic].add(subscriber_id)

                    # Initialize topic stats
                    if topic not in self.topic_stats:
                        self.topic_stats[topic] = TopicStats(topic=topic)
                    self.topic_stats[topic].subscriber_count += 1

                self.metrics.active_subscribers = len(self.subscribers)
                self.metrics.topics_count = len(self.topic_stats)

                self.logger.info("Subscriber %s registered for topics: %s", name, topics)
                return True

            except Exception as e:
                self.logger.error("Subscription failed: %s", e)
                return False

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from all topics"""
        with self._lock:
            try:
                if subscriber_id not in self.subscribers:
                    return False

                subscriber = self.subscribers[subscriber_id]

                # Remove from topic mappings
                for topic in subscriber.topics:
                    self.topic_subscribers[topic].discard(subscriber_id)
                    if topic in self.topic_stats:
                        self.topic_stats[topic].subscriber_count -= 1

                # Remove subscriber
                del self.subscribers[subscriber_id]

                self.metrics.active_subscribers = len(self.subscribers)

                self.logger.info("Subscriber %s unsubscribed", subscriber.name)
                return True

            except Exception as e:
                self.logger.error("Unsubscribe failed: %s", e)
                return False

    def publish(
        self,
        topic: str | Message,
        payload: Any = None,
        sender: str | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: dict[str, Any] | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> PublishReceipt:
        """Publish a message (sync + await-compatible).

        Supported call shapes:
        1) ``publish(Message(...))`` (legacy sync object-style)
        2) ``publish("topic", payload, sender, ...)`` (current topic/payload style)

        The returned ``PublishReceipt`` is awaitable, so existing async call-sites
        using ``await bus.publish(...)`` continue to work.
        """
        if isinstance(topic, Message):
            message = topic
            self.logger.debug(
                "I06 publish adapter used: Message-object path topic=%s sender=%s",
                message.topic,
                message.sender,
            )
        else:
            message = Message(
                topic=topic,
                sender=sender or "unknown",
                message_type=MessageType.PUBLISH,
                priority=priority,
                payload=payload,
                headers=headers or {},
                ttl=ttl,
            )

        # Defensive sender normalization for legacy object-style publishers
        if not message.sender:
            message.sender = sender or "unknown"

        # Phase 1 shadow validation: advisory-only, no blocking.
        self._shadow_validate_message_contract(message=message, stage="publish")

        if not isinstance(message.headers, dict):
            message.headers = {}

        # Phase 2 sender-role/topic/action policy gate.
        allowed, reason_code, context = self._evaluate_agent_handoff_policy(message)
        message.headers.setdefault("policy_enforcement", {})["publish"] = {
            "checked": True,
            "allowed": bool(allowed),
            "reason_code": reason_code,
            "mode": context.get("mode"),
            "role": context.get("role"),
            "action": context.get("action"),
        }
        if not allowed:
            self.policy_enforcement_stats["blocked"] += 1
            self.logger.warning(
                "I06 policy blocked publish topic=%s sender=%s role=%s action=%s reason=%s",
                message.topic,
                message.sender,
                context.get("role"),
                context.get("action"),
                reason_code,
            )
            self._add_to_dead_letter(message, f"policy_denied:{reason_code}")
            return PublishReceipt(message.id)
        self.policy_enforcement_stats["allowed"] += 1

        # Add to queue
        self._enqueue_message(message)

        # Update metrics
        self.metrics.total_messages += 1
        if message.topic not in self.topic_stats:
            self.topic_stats[message.topic] = TopicStats(topic=message.topic)
            self.metrics.topics_count = len(self.topic_stats)
        self.topic_stats[message.topic].message_count += 1
        self.topic_stats[message.topic].last_message = datetime.now(timezone.utc)

        return PublishReceipt(message.id)

    def publish_message(self, message: Message) -> PublishReceipt:
        """Compatibility adapter for explicit Message-object publishing."""
        return self.publish(message)

    def publish_sync(
        self,
        topic: str,
        payload: Any,
        sender: str | None = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: dict[str, Any] | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> PublishReceipt:
        """Compatibility adapter for sync topic/payload style publishing."""
        self.logger.debug("I06 publish adapter used: publish_sync topic=%s sender=%s", topic, sender)
        return self.publish(
            topic=topic,
            payload=payload,
            sender=sender,
            priority=priority,
            headers=headers,
            ttl=ttl,
        )

    async def publish_async(
        self,
        topic: str,
        payload: Any,
        sender: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: dict[str, Any] | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> str:
        """Async compatibility wrapper for explicit coroutine call-sites."""
        return str(
            self.publish(
                topic=topic,
                payload=payload,
                sender=sender,
                priority=priority,
                headers=headers,
                ttl=ttl,
            )
        )

    async def request(
        self,
        topic: str,
        payload: Any,
        sender: str,
        timeout: float | None = None
    ) -> Any:
        """
        Send request and wait for reply.

        Args:
            topic: Topic to send request to
            payload: Request payload
            sender: Sender identifier
            timeout: Reply timeout in seconds

        Returns:
            Reply payload
        """
        # Create request message
        correlation_id = str(uuid.uuid4())
        message = Message(
            topic=topic,
            sender=sender,
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=f"{sender}.reply"
        )

        # Create future for reply
        future = asyncio.Future()
        self.pending_replies[correlation_id] = future

        # Send request
        self._enqueue_message(message)

        # Wait for reply
        try:
            reply = await asyncio.wait_for(
                future,
                timeout=timeout or self.reply_timeout
            )
            return reply

        except TimeoutError:
            self.logger.warning("Request timeout for %s", topic)
            del self.pending_replies[correlation_id]
            return None

        except Exception as e:
            self.logger.error("Request failed: %s", e)
            if correlation_id in self.pending_replies:
                del self.pending_replies[correlation_id]
            return None

    def reply(
        self,
        original_message: Message,
        payload: Any,
        sender: str
    ):
        """Send reply to a request"""
        if not original_message.correlation_id:
            self.logger.warning("Cannot reply to message without correlation_id")
            return

        # Create reply message
        reply_message = Message(
            topic=original_message.reply_to or f"{original_message.sender}.reply",
            sender=sender,
            message_type=MessageType.REPLY,
            priority=MessagePriority.HIGH,
            payload=payload,
            correlation_id=original_message.correlation_id
        )

        # Send reply
        self._enqueue_message(reply_message)

    def broadcast(
        self,
        payload: Any,
        sender: str,
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """Broadcast message to all subscribers"""
        message = Message(
            topic="*",  # Special broadcast topic
            sender=sender,
            message_type=MessageType.BROADCAST,
            priority=priority,
            payload=payload
        )

        self._enqueue_message(message)

    def _enqueue_message(self, message: Message):
        """Add message to priority queue"""
        try:
            # Check message size
            # NOTE: pickle.dumps used here solely to measure serialized byte size
            # before enqueue — not for persistence.  The resulting bytes are
            # immediately discarded; only len() is used.
            message_size = len(pickle.dumps(message))  # noqa: S301 — byte-size measurement only, not deserialized
            if message_size > MAX_MESSAGE_SIZE:
                self.logger.error("Message too large: %s bytes", message_size)
                return

            # Add to queue with priority
            self.priority_queue.put((message.priority.value, message))

            # Persist if enabled
            if self.persist_messages:
                self._persist_message(message)

            # Record in history
            self.message_history.append(message)

        except queue.Full:
            self.logger.error("Message queue full, message dropped")
            self.metrics.failed_messages += 1
            self._add_to_dead_letter(message, "Queue full")

        except Exception as e:
            self.logger.error("Failed to enqueue message: %s", e)
            self.metrics.failed_messages += 1

    def _deliver_message(self, message: Message):
        """Deliver message to subscribers"""
        delivered = False
        start_time = datetime.now(timezone.utc)

        try:
            # Check if message expired
            if message.is_expired():
                self.logger.debug("Message %s expired", message.id)
                self._add_to_dead_letter(message, "Expired")
                return

            # Handle reply messages
            if message.message_type == MessageType.REPLY:
                self._handle_reply(message)
                return

            # Phase 1 shadow validation on consume path (advisory-only).
            self._shadow_validate_message_contract(message=message, stage="consume")

            # Find matching subscribers
            subscribers = self._find_subscribers(message.topic)

            # Deliver to each subscriber
            for subscriber_id in subscribers:
                subscriber = self.subscribers.get(subscriber_id)
                if not subscriber:
                    continue

                # Check subscriber state
                if subscriber.state != SubscriberState.ACTIVE:
                    continue

                # Apply filter if exists
                if subscriber.filter_func:
                    try:
                        if not subscriber.filter_func(message):
                            continue
                    except Exception as e:
                        self.logger.error("Filter function error: %s", e)
                        continue

                # Deliver message
                try:
                    subscriber.callback(message)
                    subscriber.message_count += 1
                    subscriber.last_message = datetime.now(timezone.utc)
                    delivered = True

                except Exception as e:
                    self.logger.error("Delivery to %s failed: %s", subscriber.name, e)
                    self._handle_delivery_failure(subscriber, message, e)

            # Update metrics
            if delivered:
                self.metrics.delivered_messages += 1
                latency = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.latency_history.append(latency)
                self.metrics.avg_latency = np.mean(list(self.latency_history))
            else:
                # No subscribers or all failed
                if message.delivery_mode == DeliveryMode.AT_LEAST_ONCE:
                    self._retry_message(message)

        except Exception as e:
            self.logger.error("Message delivery error: %s", e)
            self.metrics.failed_messages += 1
            self._add_to_dead_letter(message, str(e))

    def _find_subscribers(self, topic: str) -> set[str]:
        """Find subscribers for a topic"""
        subscribers = set()

        # Direct topic match
        if topic in self.topic_subscribers:
            subscribers.update(self.topic_subscribers[topic])

        # Wildcard matching
        if topic == "*":
            # Broadcast to all
            subscribers.update(self.subscribers.keys())
        else:
            # Pattern matching for wildcards
            for pattern, subs in self.topic_subscribers.items():
                if self._match_topic(topic, pattern):
                    subscribers.update(subs)

        return subscribers

    def _match_topic(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern"""
        if pattern == "*":
            return True

        if "*" in pattern:
            # Simple wildcard matching
            pattern_parts = pattern.split(".")
            topic_parts = topic.split(".")

            if len(pattern_parts) != len(topic_parts):
                return False

            return all(not (p != "*" and p != t) for p, t in zip(pattern_parts, topic_parts, strict=False))  # noqa: E501

        return topic == pattern

    def _should_shadow_validate_topic(self, topic: str) -> bool:
        """Return True when a topic is in shadow-validation scope."""
        if topic in self.shadow_validation_required_topics:
            return True
        return any(topic.startswith(prefix) for prefix in self.shadow_validation_topic_prefixes)

    def _shadow_validate_message_contract(self, message: Message, stage: str) -> None:
        """Advisory-only agent handoff validation for Phase 1 shadow mode."""
        if not self.shadow_validation_enabled:
            return

        if not self._should_shadow_validate_topic(message.topic):
            return

        if not isinstance(message.headers, dict):
            message.headers = {}

        shadow_result: dict[str, Any] = {
            "checked": False,
            "valid": True,
            "schema": None,
            "error": None,
        }

        if not AGENT_HANDOFF_SCHEMA_AVAILABLE:
            self.shadow_validation_stats["unavailable"] += 1
            shadow_result["error"] = "schema_validator_unavailable"
            message.headers.setdefault("shadow_validation", {})[stage] = shadow_result
            return

        payload = message.payload if isinstance(message.payload, dict) else None
        envelope, schema_name = extract_agent_handoff_envelope(payload)
        shadow_result["checked"] = True
        shadow_result["schema"] = schema_name

        if envelope is None:
            if message.topic in self.shadow_validation_required_topics:
                self.shadow_validation_stats["missing"] += 1
                shadow_result["valid"] = False
                shadow_result["error"] = "missing_agent_handoff_envelope"
                self.logger.warning(
                    "I06 shadow contract advisory: missing envelope "
                    "topic=%s sender=%s stage=%s",
                    message.topic,
                    message.sender,
                    stage,
                )

            message.headers.setdefault("shadow_validation", {})[stage] = shadow_result
            return

        valid, error = validate_agent_handoff_envelope(envelope, schema_name)
        shadow_result["valid"] = bool(valid)
        shadow_result["error"] = error
        if isinstance(envelope, dict) and isinstance(envelope.get("schema"), str):
            shadow_result["schema"] = envelope.get("schema")

        if valid:
            self.shadow_validation_stats["valid"] += 1
        else:
            self.shadow_validation_stats["invalid"] += 1
            self.logger.warning(
                "I06 shadow contract advisory: invalid envelope "
                "topic=%s sender=%s stage=%s schema=%s error=%s",
                message.topic,
                message.sender,
                stage,
                shadow_result.get("schema"),
                error,
            )

        message.headers.setdefault("shadow_validation", {})[stage] = shadow_result

    def _handle_reply(self, message: Message):
        """Handle reply message"""
        correlation_id = message.correlation_id

        if correlation_id in self.pending_replies:
            future = self.pending_replies[correlation_id]
            if not future.done():
                future.set_result(message.payload)
            del self.pending_replies[correlation_id]

    def _handle_delivery_failure(self, subscriber: Subscriber, message: Message, error: Exception):
        """Handle failed delivery to subscriber"""
        subscriber.error_count += 1

        # Check for circuit breaker
        if subscriber.error_count >= CIRCUIT_BREAKER_THRESHOLD:
            self.logger.warning("Circuit breaker opened for %s", subscriber.name)
            subscriber.state = SubscriberState.CIRCUIT_OPEN
            subscriber.circuit_breaker_opens += 1

            # Schedule circuit breaker reset
            threading.Timer(
                CIRCUIT_BREAKER_TIMEOUT,
                self._reset_circuit_breaker,
                args=[subscriber.id]
            ).start()

        # Retry if needed
        if message.delivery_mode == DeliveryMode.AT_LEAST_ONCE:
            self._retry_message(message)

    def _reset_circuit_breaker(self, subscriber_id: str):
        """Reset circuit breaker for subscriber"""
        with self._lock:
            if subscriber_id in self.subscribers:
                subscriber = self.subscribers[subscriber_id]
                subscriber.state = SubscriberState.ACTIVE
                subscriber.error_count = 0
                self.logger.info("Circuit breaker reset for %s", subscriber.name)

    def _retry_message(self, message: Message):
        """Retry failed message"""
        message.retry_count += 1

        if message.retry_count <= MAX_RETRIES:
            # Re-enqueue with lower priority
            message.priority = MessagePriority.LOW
            self._enqueue_message(message)
        else:
            # Max retries exceeded
            self._add_to_dead_letter(message, "Max retries exceeded")

    def _add_to_dead_letter(self, message: Message, reason: str):
        """Add message to dead letter queue"""
        self.dead_letter_queue.append({
            'message': message,
            'reason': reason,
            'timestamp': datetime.now(timezone.utc)
        })

        self.metrics.dead_letter_count = len(self.dead_letter_queue)
        self.metrics.failed_messages += 1

        self.logger.warning("Message %s sent to dead letter: %s", message.id, reason)

    def _persist_message(self, message: Message):
        """Persist message to disk"""
        try:
            self.persistence_path.mkdir(parents=True, exist_ok=True)

            # Persist message using JSON via the canonical Message.to_json() schema.
            # Payload fields that are not JSON-serialisable (e.g. numpy arrays,
            # custom objects) are coerced to strings by the `default=str` fallback
            # inside Message.to_json() / asdict().  If the JSON path fails for any
            # reason we fall back to pickle to guarantee delivery persistence.
            json_filename = self.persistence_path / f"{message.id}.json"
            try:
                with open(json_filename, 'w', encoding='utf-8') as f:
                    f.write(message.to_json())
            except (TypeError, ValueError) as json_exc:
                self.logger.debug(
                    f"JSON serialisation failed for message {message.id} "
                    f"({json_exc}); falling back to pickle."
                )
                pkl_filename = self.persistence_path / f"{message.id}.pkl"
                import joblib as _joblib
                _joblib.dump(message, pkl_filename)

        except Exception as e:
            self.logger.error("Failed to persist message: %s", e)

    def get_metrics(self) -> BusMetrics:
        """Get current metrics"""
        with self._lock:
            # Calculate throughput
            if self.latency_history:
                time_window = 60  # 1 minute
                recent_messages = [
                    m for m in self.message_history
                    if (datetime.now(timezone.utc) - m.timestamp).total_seconds() <= time_window
                ]
                self.metrics.throughput = len(recent_messages) / time_window

            return self.metrics

    def get_topic_stats(self, topic: str = None) -> dict[str, TopicStats]:
        """Get statistics for topics"""
        with self._lock:
            if topic:
                return {topic: self.topic_stats.get(topic)}
            return dict(self.topic_stats)

    def get_dead_letters(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent dead letter messages"""
        return list(self.dead_letter_queue)[-limit:]

    def clear_dead_letters(self):
        """Clear dead letter queue"""
        with self._lock:
            self.dead_letter_queue.clear()
            self.metrics.dead_letter_count = 0
            self.logger.info("Dead letter queue cleared")

    def shutdown(self):
        """Shutdown message bus"""
        self.logger.info("Shutting down message bus...")

        # Signal shutdown
        self._shutdown.set()

        # Wait for worker to finish
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

        # Process remaining messages
        while not self.priority_queue.empty():
            try:
                _, message = self.priority_queue.get_nowait()
                self.logger.debug("Dropping message %s during shutdown", message.id)
            except Exception:
                break

        self.logger.info("Message bus shutdown complete")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_message_bus(config: dict[str, Any] | None = None) -> AgentMessageBus:
    """Create and initialize message bus instance"""
    return AgentMessageBus(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    import asyncio

    async def test_message_bus():
        # Create message bus
        bus = create_message_bus()


        # Test subscriber
        def test_callback(message: Message):
            pass

        # Subscribe to topics
        bus.subscribe(
            "test_agent",
            ["market.*", "signals.*"],
            test_callback,
            name="Test Agent"
        )

        # Publish messages

        await bus.publish(
            "market.update",
            {"SPY": 450.0, "VIX": 18.5},
            "market_agent",
            priority=MessagePriority.HIGH
        )

        await bus.publish(
            "signals.entry",
            {"action": "BUY", "strategy": "IronCondor"},
            "strategy_agent",
            priority=MessagePriority.NORMAL
        )

        # Test request/reply

        async def reply_handler(message: Message):
            if message.message_type == MessageType.REQUEST:
                bus.reply(message, {"status": "OK"}, "responder")

        bus.subscribe("responder", ["test.request"], reply_handler)

        await bus.request(
            "test.request",
            {"query": "status"},
            "requester"
        )

        # Wait for processing
        await asyncio.sleep(1)

        # Get metrics
        bus.get_metrics()

        # Shutdown
        bus.shutdown()

    # Run test
    asyncio.run(test_message_bus())
