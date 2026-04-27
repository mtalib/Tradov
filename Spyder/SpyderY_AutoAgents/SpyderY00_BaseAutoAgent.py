#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY00_BaseAutoAgent.py
Group: Y (AutoAgents)
Purpose: Base class for all autonomous 24/7 LLM-powered agents

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Abstract base class that all SpyderY autonomous agents inherit from.
    Provides the core lifecycle (start/stop/pause/resume), LLM integration
    via Ollama, message bus publishing/subscribing, scheduling, persistent
    state management, health monitoring, and graceful shutdown.

    SpyderY agents differ from SpyderX agents:
      - SpyderX agents are on-demand utilities (stateless, called when needed)
      - SpyderY agents are autonomous daemons (persistent state, scheduled,
        continuously running 24/7 with market-aware scheduling)

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import threading
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from .SpyderY_InferenceBackends import (
    InferenceBackend,
    OllamaBackend,
    OpenVINOBackend,
    OpenVINOConfig,
)

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger("SpyderY_AutoAgents")
except ImportError:
    logger = logging.getLogger("SpyderY_AutoAgents")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        logger.addHandler(handler)

try:
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = None

try:
    from Spyder.SpyderI_Integration.SpyderI06_AgentMessageBus import (
        Message,
        MessagePriority,
        MessageType,
    )
    MESSAGE_BUS_AVAILABLE = True
except ImportError:
    MESSAGE_BUS_AVAILABLE = False


# ==============================================================================
# LLM CONFIGURATION
# ==============================================================================
@dataclass
class OllamaConfig:
    """Unified Ollama LLM configuration for all Y-series agents.

    All models listed here are AGPL-free:
      - Llama 3.1/3.2: Meta Community License (permissive commercial use)
      - Mistral 7B: Apache 2.0
      - Qwen 2.5 Coder: Apache 2.0
      - Phi-3.5 Mini: MIT
    """

    base_url: str = "http://localhost:11434"
    primary_model: str = "llama3.1:8b-instruct-q5_K_M"
    fast_model: str = "llama3.2:3b-instruct-q4_K_M"
    code_model: str = "qwen2.5-coder:7b-instruct-q5_K_M"
    finance_model: str = "mistral:7b-instruct-v0.3-q5_K_M"
    timeout: int = 60
    max_retries: int = 3
    temperature_default: float = 0.3
    temperature_creative: float = 0.7
    max_context_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        """Load config from environment variables, falling back to defaults."""
        return cls(
            base_url=os.getenv("OLLAMA_BASE_URL", cls.base_url),
            primary_model=os.getenv("OLLAMA_PRIMARY_MODEL", cls.primary_model),
            fast_model=os.getenv("OLLAMA_FAST_MODEL", cls.fast_model),
            code_model=os.getenv("OLLAMA_CODE_MODEL", cls.code_model),
            finance_model=os.getenv("OLLAMA_FINANCE_MODEL", cls.finance_model),
            timeout=int(os.getenv("OLLAMA_TIMEOUT", str(cls.timeout))),
            max_retries=int(os.getenv("OLLAMA_MAX_RETRIES", str(cls.max_retries))),
            temperature_default=float(
                os.getenv("OLLAMA_TEMPERATURE_DEFAULT", str(cls.temperature_default))
            ),
            temperature_creative=float(
                os.getenv("OLLAMA_TEMPERATURE_CREATIVE", str(cls.temperature_creative))
            ),
        )


def _build_inference_backend(ollama_config: "OllamaConfig") -> InferenceBackend:
    """Construct an InferenceBackend from SPYDER_LLM_BACKEND env var.

    SPYDER_LLM_BACKEND=ollama    → OllamaBackend  (default)
    SPYDER_LLM_BACKEND=openvino  → OpenVINOBackend (Intel CPU/GPU/NPU)

    The role→model-id mapping for OllamaBackend is derived from the
    supplied OllamaConfig so that env-var overrides are still honoured.
    """
    backend_name = os.getenv("SPYDER_LLM_BACKEND", "ollama").lower().strip()
    if backend_name == "openvino":
        return OpenVINOBackend(OpenVINOConfig.from_env())
    return OllamaBackend({
        "primary": ollama_config.primary_model,
        "fast":    ollama_config.fast_model,
        "code":    ollama_config.code_model,
        "finance": ollama_config.finance_model,
    })


# ==============================================================================
# AGENT ENUMS & DATA STRUCTURES
# ==============================================================================
class AgentState(Enum):
    """Lifecycle states for autonomous agents."""
    INITIALIZING = auto()
    RUNNING = auto()
    PAUSED = auto()
    SLEEPING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class MarketSession(Enum):
    """Market session periods (all times US Eastern)."""
    OVERNIGHT = "overnight"       # 8:00 PM - 4:00 AM ET
    PRE_MARKET = "pre_market"     # 4:00 AM - 9:30 AM ET
    MARKET_OPEN = "market_open"   # 9:30 AM - 9:45 AM ET  (first 15 min)
    MARKET_HOURS = "market_hours" # 9:45 AM - 3:45 PM ET
    POWER_HOUR = "power_hour"     # 3:45 PM - 4:00 PM ET
    POST_MARKET = "post_market"   # 4:00 PM - 8:00 PM ET


class LLMRole(Enum):
    """Which Ollama model slot to use for a given task."""
    PRIMARY = "primary"     # General reasoning (Llama 3.1 8B)
    FAST = "fast"           # Quick summaries (Llama 3.2 3B)
    CODE = "code"           # Code analysis (Qwen 2.5 Coder)
    FINANCE = "finance"     # Financial reasoning (Mistral 7B)


@dataclass
class AgentHeartbeat:
    """Periodic health signal from an agent."""
    agent_id: str
    state: AgentState
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime_seconds: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    llm_calls: int = 0
    llm_avg_latency_ms: float = 0.0
    errors: int = 0
    last_error: str | None = None
    current_task: str = "idle"
    memory_mb: float = 0.0


@dataclass
class AgentOutput:
    """Standardized output from any Y-series agent."""
    agent_id: str
    output_type: str          # "analysis", "signal", "alert", "decision", "report"
    topic: str                # Message bus topic
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0   # 0.0 - 1.0
    reasoning: str = ""       # LLM-generated explanation
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 300    # 5-minute default TTL
    priority: str = "NORMAL"  # Maps to MessagePriority


# ==============================================================================
# BASE AUTO AGENT
# ==============================================================================
class BaseAutoAgent(ABC):
    """Abstract base class for all SpyderY autonomous agents.

    Provides:
      - Lifecycle management (start, stop, pause, resume)
      - Ollama LLM integration with model selection by role
      - AgentMessageBus publishing and subscribing
      - Market-session-aware scheduling
      - Persistent state save/load to JSON
      - Health monitoring via heartbeats
      - Graceful shutdown with state persistence
    """

    # Subclasses must define these
    AGENT_ID: str = "base"
    AGENT_NAME: str = "BaseAutoAgent"
    AGENT_VERSION: str = "1.0.0"
    DESCRIPTION: str = ""

    # Which market sessions this agent is active during
    ACTIVE_SESSIONS: set[MarketSession] = {
        MarketSession.OVERNIGHT,
        MarketSession.PRE_MARKET,
        MarketSession.MARKET_OPEN,
        MarketSession.MARKET_HOURS,
        MarketSession.POWER_HOUR,
        MarketSession.POST_MARKET,
    }

    # Default tick interval in seconds (how often the main loop runs)
    TICK_INTERVAL: float = 60.0

    def __init__(
        self,
        ollama_config: OllamaConfig | None = None,
        message_bus: Any | None = None,
        state_dir: Path | None = None,
        inference_backend: InferenceBackend | None = None,
    ):
        # Configuration
        self.ollama_config = ollama_config or OllamaConfig.from_env()
        self.message_bus = message_bus

        # Inference backend (Ollama or OpenVINO)
        self._backend: InferenceBackend = (
            inference_backend or _build_inference_backend(self.ollama_config)
        )

        # State
        self.state = AgentState.INITIALIZING
        self._start_time: datetime | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused initially
        self._thread: threading.Thread | None = None

        # Metrics
        self._messages_sent: int = 0
        self._messages_received: int = 0
        self._llm_calls: int = 0
        self._llm_total_latency_ms: float = 0.0
        self._errors: int = 0
        self._last_error: str | None = None

        # Persistence
        self._state_dir = state_dir or Path("data/agent_state")
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / f"{self.AGENT_ID}_state.json"

        # Subscriptions tracking
        self._subscriptions: list[str] = []

        logger.info(
            "[%s] %s v%s initialized", self.AGENT_ID, self.AGENT_NAME, self.AGENT_VERSION
        )

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def start(self) -> None:
        """Start the agent in a background thread."""
        if self.state == AgentState.RUNNING:
            logger.warning("[%s] Already running", self.AGENT_ID)
            return

        self._stop_event.clear()
        self._pause_event.set()
        self._start_time = datetime.now(timezone.utc)
        self.state = AgentState.RUNNING

        # Load any persisted state
        self._load_state()

        # Allow subclass initialization
        self.on_start()

        # Start the main loop in a daemon thread
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"SpyderY-{self.AGENT_ID}",
            daemon=True,
        )
        self._thread.start()
        logger.info("[%s] Started", self.AGENT_ID)

    def stop(self) -> None:
        """Gracefully stop the agent, persisting state."""
        if self.state in (AgentState.STOPPED, AgentState.STOPPING):
            return

        logger.info("[%s] Stopping...", self.AGENT_ID)
        self.state = AgentState.STOPPING
        self._stop_event.set()
        self._pause_event.set()  # Unpause if paused, so loop can exit

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        # Allow subclass cleanup
        self.on_stop()

        # Persist state
        self._save_state()

        self.state = AgentState.STOPPED
        logger.info("[%s] Stopped", self.AGENT_ID)

    def pause(self) -> None:
        """Pause the agent (it stays alive but stops ticking)."""
        if self.state == AgentState.RUNNING:
            self._pause_event.clear()
            self.state = AgentState.PAUSED
            logger.info("[%s] Paused", self.AGENT_ID)

    def resume(self) -> None:
        """Resume a paused agent."""
        if self.state == AgentState.PAUSED:
            self._pause_event.set()
            self.state = AgentState.RUNNING
            logger.info("[%s] Resumed", self.AGENT_ID)

    # ==========================================================================
    # MAIN LOOP
    # ==========================================================================
    def _run_loop(self) -> None:
        """Main agent loop — ticks at TICK_INTERVAL, respects scheduling."""
        while not self._stop_event.is_set():
            try:
                # Wait if paused
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break

                # Check market session
                session = self.get_current_session()
                if session not in self.ACTIVE_SESSIONS:
                    self.state = AgentState.SLEEPING
                    self._stop_event.wait(timeout=60)  # Check every minute
                    continue

                if self.state == AgentState.SLEEPING:
                    self.state = AgentState.RUNNING
                    self.on_wake(session)

                # Execute the agent's main work
                self.tick(session)

                # Emit heartbeat
                self._emit_heartbeat()

            except Exception as e:
                self._errors += 1
                self._last_error = str(e)
                logger.error(
                    "[%s] Error in tick: %s\n%s", self.AGENT_ID, e, traceback.format_exc()
                )
                # Back off on error
                self._stop_event.wait(timeout=min(self.TICK_INTERVAL * 2, 300))
                continue

            # Wait for next tick
            self._stop_event.wait(timeout=self.TICK_INTERVAL)

    # ==========================================================================
    # ABSTRACT METHODS — Subclasses MUST implement these
    # ==========================================================================
    @abstractmethod
    def tick(self, session: MarketSession) -> None:
        """Called every TICK_INTERVAL seconds during active sessions.

        This is the main work method. The agent should:
          1. Gather data (market, signals, messages)
          2. Analyze using quantitative methods + LLM reasoning
          3. Publish outputs to the message bus
          4. Update internal state

        Args:
            session: Current market session for context-aware behavior.
        """
        ...

    @abstractmethod
    def get_state_snapshot(self) -> dict[str, Any]:
        """Return agent-specific state for persistence.

        Called during stop() and periodically for checkpointing.
        Must return a JSON-serializable dict.
        """
        ...

    @abstractmethod
    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore agent-specific state from a previously saved snapshot.

        Called during start() if a state file exists.
        """
        ...

    # ==========================================================================
    # OPTIONAL HOOKS — Subclasses CAN override these
    # ==========================================================================
    def on_start(self) -> None:  # noqa: B027
        """Called once when the agent starts, before the main loop."""
        pass

    def on_stop(self) -> None:  # noqa: B027
        """Called once when the agent stops, after the main loop exits."""
        pass

    def on_wake(self, session: MarketSession) -> None:
        """Called when the agent wakes up after sleeping through an inactive session."""
        logger.info("[%s] Waking up for %s", self.AGENT_ID, session.value)

    def on_message(self, topic: str, message: Any) -> None:
        """Called when a subscribed message bus topic receives a message."""
        self._messages_received += 1

    # ==========================================================================
    # LLM INTERFACE
    # ==========================================================================
    def llm_query(
        self,
        prompt: str,
        role: LLMRole = LLMRole.PRIMARY,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int = 2048,
    ) -> str | None:
        """Send a prompt to the local Ollama LLM and return the response.

        Args:
            prompt: The user prompt to send.
            role: Which model to use (PRIMARY, FAST, CODE, FINANCE).
            system_prompt: Optional system prompt for context.
            temperature: Override default temperature.
            max_tokens: Maximum response tokens.

        Returns:
            The LLM response text, or None if unavailable/failed.
        """
        if not self._backend.is_available():
            logger.debug(
                f"[{self.AGENT_ID}] Backend '{self._backend.name}' not available, "
                "skipping LLM query"
            )
            return None

        model = self._backend.model_id_for_role(role.value)
        temp = temperature or self.ollama_config.temperature_default

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.ollama_config.max_retries):
            try:
                start_ms = time.time() * 1000
                content = self._backend.chat(model, messages, temp, max_tokens)
                elapsed_ms = (time.time() * 1000) - start_ms

                if content is None:
                    raise RuntimeError("Backend returned None")

                self._llm_calls += 1
                self._llm_total_latency_ms += elapsed_ms
                logger.debug(
                    f"[{self.AGENT_ID}] LLM ({model}) responded in {elapsed_ms:.0f}ms"
                )
                return content

            except Exception as e:
                logger.warning(
                    "[%s] LLM query attempt %s failed: %s", self.AGENT_ID, attempt + 1, e
                )
                if attempt < self.ollama_config.max_retries - 1:
                    time.sleep(2 ** attempt)  # thread-safe: time.sleep() intentional

        logger.error("[%s] LLM query failed after all retries", self.AGENT_ID)
        return None

    def llm_query_json(
        self,
        prompt: str,
        role: LLMRole = LLMRole.PRIMARY,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any] | None:
        """Send a prompt to the LLM and parse the response as JSON.

        Adds instructions to return valid JSON. Attempts to extract JSON
        from the response even if surrounded by markdown fences or text.

        Returns:
            Parsed dict, or None on failure.
        """
        json_system = (system_prompt or "") + (
            "\n\nYou MUST respond with valid JSON only. "
            "Do not include markdown fences, explanations, or any text outside the JSON object."
        )
        raw = self.llm_query(
            prompt=prompt,
            role=role,
            system_prompt=json_system.strip(),
            temperature=temperature or 0.2,  # Lower temp for structured output
        )
        if not raw:
            return None

        # Try direct parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown fences
        import re
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block
        brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("[%s] Failed to parse LLM response as JSON", self.AGENT_ID)
        return None

    # ==========================================================================
    # MESSAGE BUS
    # ==========================================================================
    def publish(self, output: AgentOutput) -> bool:
        """Publish an AgentOutput to the message bus.

        If the message bus is not available, logs the output instead.
        """
        self._messages_sent += 1

        if self.message_bus and MESSAGE_BUS_AVAILABLE:
            try:
                priority_map = {
                    "CRITICAL": MessagePriority.CRITICAL,
                    "HIGH": MessagePriority.HIGH,
                    "NORMAL": MessagePriority.NORMAL,
                    "LOW": MessagePriority.LOW,
                    "BULK": MessagePriority.BULK,
                }
                msg = Message(
                    topic=output.topic,
                    sender=self.AGENT_ID,
                    message_type=MessageType.PUBLISH,
                    priority=priority_map.get(output.priority, MessagePriority.NORMAL),
                    payload={
                        "agent_id": output.agent_id,
                        "output_type": output.output_type,
                        "data": output.payload,
                        "confidence": output.confidence,
                        "reasoning": output.reasoning,
                    },
                    ttl=output.ttl_seconds,
                )
                self.message_bus.publish(msg)
                return True
            except Exception as e:
                logger.error("[%s] Failed to publish: %s", self.AGENT_ID, e)
                return False
        else:
            # Log output when bus is unavailable (development/testing)
            logger.info(
                f"[{self.AGENT_ID}] OUTPUT [{output.output_type}] "
                f"topic={output.topic} confidence={output.confidence:.2f} "
                f"| {output.reasoning[:120]}"
            )
            return True

    def subscribe(self, topic: str) -> None:
        """Subscribe to a message bus topic."""
        self._subscriptions.append(topic)
        if self.message_bus and MESSAGE_BUS_AVAILABLE:
            try:
                self.message_bus.subscribe(
                    subscriber_id=self.AGENT_ID,
                    name=self.AGENT_NAME,
                    topics=[topic],
                    callback=lambda msg: self.on_message(topic, msg),
                )
            except Exception as e:
                logger.warning(
                    "[%s] Failed to subscribe to %s: %s", self.AGENT_ID, topic, e
                )

    # ==========================================================================
    # MARKET SESSION
    # ==========================================================================
    @staticmethod
    def get_current_session() -> MarketSession:
        """Determine the current market session based on US Eastern time.

        Returns the MarketSession enum for the current time.
        """
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo

        et_now = datetime.now(ZoneInfo("America/New_York"))
        hour, minute = et_now.hour, et_now.minute
        time_val = hour * 60 + minute  # Minutes since midnight

        if time_val < 240:                          # Before 4:00 AM
            return MarketSession.OVERNIGHT
        elif time_val < 570:                        # 4:00 AM - 9:30 AM
            return MarketSession.PRE_MARKET
        elif time_val < 585:                        # 9:30 AM - 9:45 AM
            return MarketSession.MARKET_OPEN
        elif time_val < 945:                        # 9:45 AM - 3:45 PM
            return MarketSession.MARKET_HOURS
        elif time_val < 960:                        # 3:45 PM - 4:00 PM
            return MarketSession.POWER_HOUR
        elif time_val < 1200:                       # 4:00 PM - 8:00 PM
            return MarketSession.POST_MARKET
        else:                                       # 8:00 PM - midnight
            return MarketSession.OVERNIGHT

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def _save_state(self) -> None:
        """Persist agent state to disk."""
        try:
            state = {
                "agent_id": self.AGENT_ID,
                "agent_version": self.AGENT_VERSION,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "metrics": {
                    "messages_sent": self._messages_sent,
                    "messages_received": self._messages_received,
                    "llm_calls": self._llm_calls,
                    "errors": self._errors,
                },
                "agent_state": self.get_state_snapshot(),
            }
            with open(self._state_file, "w") as f:
                json.dump(state, f, indent=2, default=str)
            logger.debug("[%s] State saved to %s", self.AGENT_ID, self._state_file)
        except Exception as e:
            logger.error("[%s] Failed to save state: %s", self.AGENT_ID, e)

    def _load_state(self) -> None:
        """Restore agent state from disk."""
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file) as f:
                state = json.load(f)

            # Restore metrics
            metrics = state.get("metrics", {})
            self._messages_sent = metrics.get("messages_sent", 0)
            self._messages_received = metrics.get("messages_received", 0)
            self._llm_calls = metrics.get("llm_calls", 0)
            self._errors = metrics.get("errors", 0)

            # Restore agent-specific state
            agent_state = state.get("agent_state", {})
            if agent_state:
                self.restore_state(agent_state)

            logger.info(
                "[%s] State restored from %s", self.AGENT_ID, self._state_file
            )
        except Exception as e:
            logger.warning("[%s] Failed to load state: %s", self.AGENT_ID, e)

    # ==========================================================================
    # HEALTH
    # ==========================================================================
    def _emit_heartbeat(self) -> None:
        """Publish a heartbeat to the meta.health topic."""
        try:
            import resource
            mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except Exception:
            mem_mb = 0.0

        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        avg_latency = 0.0
        if self._llm_calls > 0:
            avg_latency = self._llm_total_latency_ms / self._llm_calls

        heartbeat = AgentHeartbeat(
            agent_id=self.AGENT_ID,
            state=self.state,
            uptime_seconds=uptime,
            messages_sent=self._messages_sent,
            messages_received=self._messages_received,
            llm_calls=self._llm_calls,
            llm_avg_latency_ms=avg_latency,
            errors=self._errors,
            last_error=self._last_error,
            memory_mb=mem_mb,
        )
        self.publish(AgentOutput(
            agent_id=self.AGENT_ID,
            output_type="heartbeat",
            topic="meta.health",
            payload=asdict(heartbeat),
            priority="BULK",
            ttl_seconds=120,
        ))

    def get_status(self) -> dict[str, Any]:
        """Return current agent status for the dashboard/monitoring."""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        avg_latency = 0.0
        if self._llm_calls > 0:
            avg_latency = self._llm_total_latency_ms / self._llm_calls

        return {
            "agent_id": self.AGENT_ID,
            "agent_name": self.AGENT_NAME,
            "version": self.AGENT_VERSION,
            "state": self.state.name,
            "uptime_seconds": uptime,
            "session": self.get_current_session().value,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "llm_calls": self._llm_calls,
            "llm_avg_latency_ms": round(avg_latency, 1),
            "errors": self._errors,
            "last_error": self._last_error,
            "subscriptions": self._subscriptions,
            "backend": self._backend.name,
            "backend_available": self._backend.is_available(),
        }

    # ==========================================================================
    # REPR
    # ==========================================================================
    def __repr__(self) -> str:
        return (
            f"<{self.AGENT_NAME} id={self.AGENT_ID} state={self.state.name} "
            f"llm_calls={self._llm_calls} msgs={self._messages_sent}>"
        )
