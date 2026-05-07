#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderY10_AgentScheduler.py
Group: Y (AutoAgents)
Purpose: Central scheduler that manages lifecycle of all Y-series agents

Author: Mohamed Talib
Date Created: 2026-02-25
Last Updated: 2026-02-25 Time: 12:00:00

Description:
    Manages starting, stopping, pausing, and monitoring all Y-series
    autonomous agents. Provides a unified control plane, health dashboard
    data, and graceful shutdown orchestration.

Boundary with Y08 (MetaOrchestratorAgent)
------------------------------------------
    Y10 owns **when agents run and whether they are alive**:
      - Starting, stopping, and pausing individual agents on demand
      - Enforcing market-hours gating (agents only active during session)
      - Detecting and restarting crashed or unresponsive agents
      - Exposing the lifecycle state consumed by G32 AgentHealthDashboard
      - Coordinating graceful shutdown across all daemons at EOD

    Y08 owns **what the agents decide and whether they agree**:
      - Conflict resolution when agents emit contradictory signals
      - Cross-agent decision synthesis and confidence weighting
      - Adjusting agent confidence thresholds based on market conditions
      - Escalating irreconcilable conflicts to human operators

    Rule of thumb: if the question is "are the agents running?", that is
    Y10.  If the question is "do their outputs agree?", that is Y08.

License: All dependencies are MIT/BSD/Apache — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from .SpyderY00_BaseAutoAgent import (
    BaseAutoAgent,
    AgentState,
    OllamaConfig,
)

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger("SpyderY_Scheduler")
except ImportError:
    logger = logging.getLogger("SpyderY_Scheduler")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        )
        logger.addHandler(handler)


# ==============================================================================
# SCHEDULER
# ==============================================================================
class AgentScheduler:
    """Central control plane for all SpyderY autonomous agents.

    Responsibilities:
      - Register and manage agent instances
      - Start/stop agents individually or as a group
      - Monitor agent health via heartbeats
      - Provide aggregated status for the GUI dashboard
      - Handle graceful shutdown on SIGINT/SIGTERM
      - Restart failed agents with backoff

    Usage:
        scheduler = AgentScheduler()
        scheduler.register(MarketSenseAgent)
        scheduler.register(RiskSentinelAgent)
        scheduler.start_all()
        # ... runs until interrupted ...
        scheduler.stop_all()
    """

    MAX_RESTART_ATTEMPTS = 3
    RESTART_BACKOFF_SECONDS = 30
    HEALTH_CHECK_INTERVAL = 60  # seconds

    def __init__(
        self,
        ollama_config: OllamaConfig | None = None,
        message_bus: Any | None = None,
        state_dir: Path | None = None,
        telegram_bot: Any | None = None,
    ):
        self.ollama_config = ollama_config or OllamaConfig.from_env()
        self.message_bus = message_bus
        self.state_dir = state_dir or Path("data/agent_state")
        self.telegram_bot = telegram_bot

        self._agents: dict[str, BaseAutoAgent] = {}
        self._agent_classes: dict[str, type[BaseAutoAgent]] = {}
        self._restart_counts: dict[str, int] = {}
        self._stop_event = threading.Event()
        self._health_thread: threading.Thread | None = None
        self._started = False

        logger.info("AgentScheduler initialized")

    # ==========================================================================
    # REGISTRATION
    # ==========================================================================
    def register(
        self,
        agent_class: type[BaseAutoAgent],
        **kwargs: Any,
    ) -> BaseAutoAgent:
        """Register and instantiate an agent.

        Args:
            agent_class: The BaseAutoAgent subclass to instantiate.
            **kwargs: Additional keyword arguments passed to the agent constructor.

        Returns:
            The instantiated agent.
        """
        agent = agent_class(
            ollama_config=self.ollama_config,
            message_bus=self.message_bus,
            state_dir=self.state_dir,
            **kwargs,
        )
        self._agents[agent.AGENT_ID] = agent
        self._agent_classes[agent.AGENT_ID] = agent_class
        self._restart_counts[agent.AGENT_ID] = 0
        logger.info(
            "Registered agent: %s (id=%s)", agent.AGENT_NAME, agent.AGENT_ID
        )
        return agent

    def unregister(self, agent_id: str) -> None:
        """Stop and remove an agent."""
        agent = self._agents.get(agent_id)
        if agent:
            agent.stop()
            del self._agents[agent_id]
            del self._agent_classes[agent_id]
            del self._restart_counts[agent_id]
            logger.info("Unregistered agent: %s", agent_id)

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================
    def start_all(self) -> None:
        """Start all registered agents and the health monitor."""
        logger.info("Starting %s agents...", len(self._agents))
        self._stop_event.clear()
        self._started = True

        # Install signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        for _agent_id, agent in self._agents.items():
            try:
                agent.start()
                logger.info("  ✓ %s started", agent.AGENT_NAME)
            except Exception as e:
                logger.error("  ✗ %s failed to start: %s", agent.AGENT_NAME, e, exc_info=True)

        # Start health monitoring
        self._health_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="SpyderY-HealthMonitor",
            daemon=True,
        )
        self._health_thread.start()

        logger.info("All agents started. Health monitor active.")

    def stop_all(self) -> None:
        """Gracefully stop all agents."""
        if not self._started:
            return

        logger.info("Stopping all agents...")
        self._stop_event.set()
        self._started = False

        # Stop in reverse registration order
        for agent_id in reversed(list(self._agents.keys())):
            agent = self._agents[agent_id]
            try:
                agent.stop()
                logger.info("  ✓ %s stopped", agent.AGENT_NAME)
            except Exception as e:
                logger.error("  ✗ %s failed to stop: %s", agent.AGENT_NAME, e, exc_info=True)

        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)

        logger.info("All agents stopped.")

    def start_agent(self, agent_id: str) -> bool:
        """Start a specific agent by ID."""
        agent = self._agents.get(agent_id)
        if not agent:
            logger.warning("Agent not found: %s", agent_id)
            return False
        try:
            agent.start()
            return True
        except Exception as e:
            logger.error("Failed to start %s: %s", agent_id, e, exc_info=True)
            return False

    def stop_agent(self, agent_id: str) -> bool:
        """Stop a specific agent by ID."""
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        try:
            agent.stop()
            return True
        except Exception as e:
            logger.error("Failed to stop %s: %s", agent_id, e, exc_info=True)
            return False

    def pause_agent(self, agent_id: str) -> bool:
        """Pause a specific agent."""
        agent = self._agents.get(agent_id)
        if agent:
            agent.pause()
            return True
        return False

    def resume_agent(self, agent_id: str) -> bool:
        """Resume a specific agent."""
        agent = self._agents.get(agent_id)
        if agent:
            agent.resume()
            return True
        return False

    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    def _health_monitor_loop(self) -> None:
        """Periodically check agent health and restart failed agents."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.HEALTH_CHECK_INTERVAL)
            if self._stop_event.is_set():
                break

            for agent_id, agent in list(self._agents.items()):
                if agent.state == AgentState.ERROR:
                    self._handle_agent_failure(agent_id)
                elif agent.state == AgentState.STOPPED and self._started:
                    # Agent stopped unexpectedly
                    self._handle_agent_failure(agent_id)

    def _handle_agent_failure(self, agent_id: str) -> None:
        """Attempt to restart a failed agent with backoff."""
        restarts = self._restart_counts.get(agent_id, 0)
        if restarts >= self.MAX_RESTART_ATTEMPTS:
            logger.error(
                f"Agent {agent_id} has failed {restarts} times — not restarting. "
                f"Manual intervention required."
            )
            if self.telegram_bot is not None:
                try:
                    self.telegram_bot.send_alert(
                        title="Agent Failure — Manual Intervention Required",
                        message=(
                            f"Agent <b>{agent_id}</b> has failed {restarts} times "
                            f"and will not be restarted automatically. "
                            f"Manual intervention is required."
                        ),
                        severity="critical",
                    )
                except Exception as _alert_err:
                    logger.warning("Failed to send Telegram alert: %s", _alert_err)
            return

        self._restart_counts[agent_id] = restarts + 1
        backoff = self.RESTART_BACKOFF_SECONDS * (restarts + 1)
        logger.warning(
            f"Agent {agent_id} failed (attempt {restarts + 1}/{self.MAX_RESTART_ATTEMPTS}). "
            f"Restarting in {backoff}s..."
        )

        # Wait then restart
        self._stop_event.wait(timeout=backoff)
        if self._stop_event.is_set():
            return

        agent_class = self._agent_classes.get(agent_id)
        if agent_class:
            # Re-create and start the agent
            old_agent = self._agents[agent_id]
            old_agent.stop()  # Ensure cleanup

            new_agent = agent_class(
                ollama_config=self.ollama_config,
                message_bus=self.message_bus,
                state_dir=self.state_dir,
            )
            self._agents[agent_id] = new_agent
            try:
                new_agent.start()
                logger.info("Agent %s restarted successfully", agent_id)
            except Exception as e:
                logger.error("Agent %s restart failed: %s", agent_id, e, exc_info=True)

    # ==========================================================================
    # STATUS & DASHBOARD
    # ==========================================================================
    def get_all_status(self) -> dict[str, Any]:
        """Return aggregated status of all agents for the dashboard."""
        session = BaseAutoAgent.get_current_session()
        agents_status = {}
        total_llm_calls = 0
        total_messages = 0
        total_errors = 0

        for agent_id, agent in self._agents.items():
            status = agent.get_status()
            agents_status[agent_id] = status
            total_llm_calls += status.get("llm_calls", 0)
            total_messages += status.get("messages_sent", 0)
            total_errors += status.get("errors", 0)

        running = sum(
            1 for s in agents_status.values() if s["state"] == "RUNNING"
        )
        sleeping = sum(
            1 for s in agents_status.values() if s["state"] == "SLEEPING"
        )

        return {
            "scheduler": {
                "started": self._started,
                "current_session": session.value,
                "total_agents": len(self._agents),
                "running": running,
                "sleeping": sleeping,
                "total_llm_calls": total_llm_calls,
                "total_messages": total_messages,
                "total_errors": total_errors,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "agents": agents_status,
        }

    def get_agent(self, agent_id: str) -> BaseAutoAgent | None:
        """Get an agent instance by ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[dict[str, str]]:
        """List all registered agents with basic info."""
        return [
            {
                "id": agent.AGENT_ID,
                "name": agent.AGENT_NAME,
                "state": agent.state.name,
                "version": agent.AGENT_VERSION,
            }
            for agent in self._agents.values()
        ]

    # ==========================================================================
    # SIGNAL HANDLING
    # ==========================================================================
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGINT/SIGTERM for graceful shutdown."""
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — initiating graceful shutdown...", sig_name)
        self.stop_all()

    # ==========================================================================
    # CONTEXT MANAGER
    # ==========================================================================
    def __enter__(self) -> "AgentScheduler":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop_all()

    # ==========================================================================
    # BLOCKING RUN
    # ==========================================================================
    def run_forever(self) -> None:
        """Start all agents and block until interrupted.

        Useful for running the agent constellation as a standalone service:
            scheduler = AgentScheduler()
            scheduler.register(MarketSenseAgent)
            scheduler.register(RiskSentinelAgent)
            scheduler.run_forever()
        """
        self.start_all()
        try:
            while self._started:
                self._stop_event.wait(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()

    def __repr__(self) -> str:
        running = sum(1 for a in self._agents.values() if a.state == AgentState.RUNNING)
        return (
            f"<AgentScheduler agents={len(self._agents)} running={running} "
            f"session={BaseAutoAgent.get_current_session().value}>"
        )
