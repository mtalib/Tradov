#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX14_OrchestratorAgent.py
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
import asyncio
from datetime import datetime, timezone
from typing import Any, TypedDict
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
try:
    import gymnasium as gym
except ImportError:
    import gym
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

# LangGraph — stateful multi-agent orchestration (TradingAgents-inspired)
try:
    from langgraph.graph import StateGraph, END, START  # type: ignore[import]
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

try:
    from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
        build_agent_handoff_envelope,
    )
except Exception:
    def build_agent_handoff_envelope(**kwargs):
        return {
            "schema": kwargs.get("schema", "AGENT_HANDOFF_V1"),
            "schema_version": "1.0",
            "handoff_type": kwargs.get("handoff_type", "handoff"),
            "topic": kwargs.get("topic", ""),
            "producer": {"agent_id": kwargs.get("producer_agent_id", "unknown")},
            "timestamp": kwargs.get("timestamp", datetime.now(timezone.utc).timestamp()),
            "payload": kwargs.get("payload", {}),
            "confidence": kwargs.get("confidence"),
            "reasoning": kwargs.get("reasoning", ""),
        }

# Lazy agent-module registry — each X-series agent is loaded on first use so
# a single failed agent import cannot break the entire orchestrator.
import importlib as _importlib

_AGENT_MODULE_PATHS: dict[str, str] = {
    "greeks":       "Spyder.SpyderX_Agents.SpyderX01_GreeksAgent",
    "flow":         "Spyder.SpyderX_Agents.SpyderX02_FlowAgent",
    "strategy":     "Spyder.SpyderX_Agents.SpyderX03_StrategyDirectorAgent",
    "risk":         "Spyder.SpyderX_Agents.SpyderX04_RiskGuardianAgent",
    "ml_research":  "Spyder.SpyderX_Agents.SpyderX05_MLResearchAgent",
    "execution":    "Spyder.SpyderX_Agents.SpyderX07_ExecutionStrategyAgent",
    "performance":  "Spyder.SpyderX_Agents.SpyderX08_PerformanceAnalyticsAgent",
    "alerts":       "Spyder.SpyderX_Agents.SpyderX09_AlertManagerAgent",
    "quant":        "Spyder.SpyderX_Agents.SpyderX10_QuantModelsAgent",
    "sentiment":    "Spyder.SpyderX_Agents.SpyderX11_SentimentAnalysisAgent",
    "health":       "Spyder.SpyderX_Agents.SpyderX12_SystemHealthAgent",
    "market":       "Spyder.SpyderX_Agents.SpyderX13_MarketAnalysisAgent",
}
_AGENT_MODULE_CACHE: dict[str, Any] = {}

def _load_agent_module(key: str) -> Any:
    """Import and cache an X-series agent module; return None on failure."""
    if key not in _AGENT_MODULE_CACHE:
        path = _AGENT_MODULE_PATHS.get(key)
        if not path:
            _AGENT_MODULE_CACHE[key] = None
            return None
        try:
            _AGENT_MODULE_CACHE[key] = _importlib.import_module(path)
        except Exception as _exc:
            logging.getLogger(__name__).warning(
                "X-agent module %r unavailable: %s", path, _exc
            )
            _AGENT_MODULE_CACHE[key] = None
    return _AGENT_MODULE_CACHE[key]
import logging  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
META_MODEL_PATH = "models/orchestrator/meta_learner.pth"
AGENT_WEIGHTS_PATH = "models/orchestrator/agent_weights.json"
MIN_AGENT_CONFIDENCE = 0.3
MAX_AGENT_TIMEOUT = 5.0  # seconds
COOPERATION_REWARD = 1.0
COMPETITION_PENALTY = -0.5


# ==============================================================================
# LANGGRAPH STATE (TradingAgents-inspired stateful pipeline)
# ==============================================================================
class OrchestrationState(TypedDict):
    """Typed state passed between LangGraph orchestration nodes.

    Nodes:
        analyst    → collects raw agent outputs in parallel
        debate     → classifies outputs into bull/bear/hold camps
        strategist → weights + consensus from meta-learning
        risk       → conflict detection + final decision creation
    """

    market_state: dict       # raw market conditions dict
    query: str               # decision query, e.g. "should_enter_iron_condor"
    timeout: float           # per-agent timeout in seconds
    agent_outputs: list      # list[AgentOutput] populated by analyst node
    debate: dict             # bull/bear camp summary from debate node
    weights: dict            # agent weight map from strategist node
    consensus: dict          # consensus dict from _build_consensus
    decision: Any            # OrchestratorDecision | None set by risk node


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AgentState(Enum):
    """Agent operational states"""

    ACTIVE = auto()
    DEGRADED = auto()
    FAILED = auto()
    SUSPENDED = auto()


@dataclass
class AgentOutput:
    """Standardized output from any agent"""

    agent_id: str
    prediction: Any
    confidence: float
    reasoning: str
    processing_time: float
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorDecision:
    """Final decision from orchestrator"""

    action: str
    confidence: float
    contributing_agents: list[str]
    agent_weights: dict[str, float]
    consensus_score: float
    dissenting_opinions: list[dict[str, Any]]
    reasoning: str
    execution_params: dict[str, Any]


@dataclass
class AgentPerformance:
    """Track individual agent performance"""

    agent_id: str
    accuracy_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    latency_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    reliability_score: float = 1.0
    specialization_areas: set[str] = field(default_factory=set)
    failure_count: int = 0
    success_count: int = 0


# ==============================================================================
# META-LEARNING NETWORK
# ==============================================================================
class MetaLearningNetwork(nn.Module):
    """
    Neural network for meta-learning agent coordination.
    Uses attention mechanism to dynamically weight agent outputs.
    """

    def __init__(self, n_agents: int, state_dim: int, hidden_dim: int = 256):
        super().__init__()

        # Agent embedding
        self.agent_embeddings = nn.Embedding(n_agents, hidden_dim)

        # State encoder
        self.state_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Attention mechanism for agent importance
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim, num_heads=8, dropout=0.1
        )

        # Weight predictor
        self.weight_predictor = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, n_agents),
            nn.Softmax(dim=-1),
        )

        # Value head for RL
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, 128), nn.ReLU(), nn.Linear(128, 1)
        )

    def forward(
        self, state: torch.Tensor, agent_outputs: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass to predict agent weights.

        Args:
            state: Market state tensor
            agent_outputs: Tensor of agent outputs

        Returns:
            weights: Agent weight distribution
            value: State value estimate
        """
        # Encode state
        state_encoded = self.state_encoder(state)

        # Get agent embeddings
        agent_indices = torch.arange(agent_outputs.shape[0])
        agent_embeds = self.agent_embeddings(agent_indices)

        # Apply attention
        attended, _ = self.attention(
            agent_embeds.unsqueeze(0),
            agent_embeds.unsqueeze(0),
            agent_outputs.unsqueeze(0),
        )
        attended = attended.squeeze(0)

        # Combine state and attention
        combined = torch.cat(
            [state_encoded.repeat(attended.shape[0], 1), attended], dim=-1
        )

        # Predict weights
        weights = self.weight_predictor(combined.mean(dim=0, keepdim=True))

        # Estimate value
        value = self.value_head(state_encoded)

        return weights, value


# ==============================================================================
# ORCHESTRATOR ENVIRONMENT
# ==============================================================================
class OrchestratorEnv(gym.Env):
    """
    Custom Gym environment for training the orchestrator.
    Simulates multi-agent coordination scenarios.
    """

    def __init__(self, n_agents: int = 13):
        super().__init__()

        self.n_agents = n_agents
        self.action_space = gym.spaces.Box(
            low=0, high=1, shape=(n_agents,), dtype=np.float32
        )
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(100,), dtype=np.float32
        )

        self.state = None
        self.step_count = 0
        self.episode_rewards = []

    def reset(self):
        """Reset environment to initial state."""
        self.state = np.random.randn(100).astype(np.float32)
        self.step_count = 0
        self.episode_rewards = []
        return self.state

    def step(self, action):
        """Execute action (agent weights) and return results."""
        # Simulate agent coordination results
        # Higher weight variance = less consensus = lower reward
        weight_variance = np.var(action)
        consensus_reward = 1.0 / (1.0 + weight_variance)

        # Simulate performance based on weights
        performance = np.random.normal(0.5, 0.1) + 0.2 * consensus_reward

        # Calculate reward
        reward = performance * consensus_reward
        self.episode_rewards.append(reward)

        # Update state
        self.state = np.random.randn(100).astype(np.float32)
        self.step_count += 1

        # Episode ends after 100 steps
        done = self.step_count >= 100

        info = {
            "consensus": consensus_reward,
            "performance": performance,
            "weights": action,
        }

        return self.state, reward, done, info


# ==============================================================================
# ORCHESTRATOR AGENT CLASS
# ==============================================================================
class SpyderX14_OrchestratorAgent:
    """
    Master orchestrator agent that coordinates all other AI agents.

    This agent uses meta-learning to dynamically adjust how it combines
    predictions from all other agents based on their recent performance
    and the current market regime.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the orchestrator agent.

        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Agent registry
        self.agents = self._initialize_agents()
        self._registered_agent_count = len(self.agents)
        self._effective_agent_count = max(1, self._registered_agent_count)
        if self._registered_agent_count == 0:
            self.logger.warning(
                "No X-agents registered; starting in fallback mode "
                "with safe single-worker defaults."
            )
        self.agent_states = {agent_id: AgentState.ACTIVE for agent_id in self.agents}
        self.agent_performance = {
            agent_id: AgentPerformance(agent_id=agent_id) for agent_id in self.agents
        }

        # Meta-learning components
        self.meta_network = MetaLearningNetwork(
            n_agents=self._effective_agent_count, state_dim=100
        ).to(self.device)
        self.meta_optimizer = optim.Adam(self.meta_network.parameters(), lr=3e-4)

        # RL components
        self.rl_env = None
        self.rl_model = None
        self._initialize_rl()

        # Performance tracking
        self.decision_history = deque(maxlen=10000)
        self.weight_history = defaultdict(lambda: deque(maxlen=1000))

        # Threading for parallel agent execution
        self.executor = ThreadPoolExecutor(max_workers=self._effective_agent_count)

        # LangGraph orchestration pipeline (TradingAgents-inspired)
        self._graph = self._build_orchestration_graph() if LANGGRAPH_AVAILABLE else None

        # Load saved weights if available
        self._load_saved_state()

        self.logger.info("✅ Orchestrator initialized with %s agents", len(self.agents))

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================

    def _initialize_agents(self) -> dict[str, Any]:
        """Initialize all available agents via the lazy module registry."""
        agents: dict[str, Any] = {}
        for key in _AGENT_MODULE_PATHS:
            mod = _load_agent_module(key)
            if mod is None:
                continue
            get_fn = getattr(mod, "get_instance", None)
            if callable(get_fn):
                instance = get_fn()
                if instance is not None:
                    agents[key] = instance
            else:
                self.logger.warning("Agent module %r has no get_instance()", key)
        return agents

    def _initialize_rl(self) -> None:
        """Initialize reinforcement learning components."""
        try:
            # Create environment
            self.rl_env = DummyVecEnv([lambda: OrchestratorEnv(self._effective_agent_count)])

            # Create PPO model
            self.rl_model = PPO(
                "MlpPolicy",
                self.rl_env,
                verbose=0,
                n_steps=2048,
                batch_size=64,
                n_epochs=10,
                learning_rate=3e-4,
                clip_range=0.2,
            )

        except Exception as e:
            self.logger.warning("RL initialization failed: %s", e)
            self.rl_model = None

    def _load_saved_state(self) -> None:
        """Load saved model and weights."""
        try:
            # Load meta-learning model
            model_path = Path(META_MODEL_PATH)
            if model_path.exists():
                self.meta_network.load_state_dict(torch.load(model_path))
                self.logger.info("Loaded saved meta-learning model")

            # Load agent weights
            weights_path = Path(AGENT_WEIGHTS_PATH)
            # Backward-compat: migrate from legacy .pkl if .json not present
            if not weights_path.exists():
                legacy = weights_path.with_suffix('.pkl')
                if legacy.exists():
                    import joblib as _joblib
                    with open(legacy, 'rb') as _f:
                        _wd = _joblib.load(_f)
                    weights_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(weights_path, 'w', encoding='utf-8') as _f:
                        json.dump(dict(_wd), _f, indent=2)
            if weights_path.exists():
                with open(weights_path, encoding='utf-8') as f:
                    saved_weights = json.load(f)
                    for agent_id, weights in saved_weights.items():
                        self.weight_history[agent_id].extend(weights)
                self.logger.info("Loaded saved agent weights")

        except Exception as e:
            self.logger.warning("Failed to load saved state: %s", e)

    # ==========================================================================
    # AGENT COORDINATION METHODS
    # ==========================================================================

    async def coordinate_agents(
        self,
        market_state: dict[str, Any],
        query: str,
        timeout: float = MAX_AGENT_TIMEOUT,
    ) -> OrchestratorDecision:
        """
        Coordinate all agents to make a collective decision.

        Args:
            market_state: Current market conditions
            query: Decision query (e.g., "should_enter_trade")
            timeout: Maximum time to wait for agent responses

        Returns:
            OrchestratorDecision with collective intelligence
        """
        try:
            start_time = datetime.now(timezone.utc)

            # --- LangGraph path (TradingAgents-inspired stateful pipeline) ---
            if self._graph is not None:
                initial_state: OrchestrationState = {
                    "market_state": market_state,
                    "query": query,
                    "timeout": timeout,
                    "agent_outputs": [],
                    "debate": {},
                    "weights": {},
                    "consensus": {},
                    "decision": None,
                }
                result = await self._graph.ainvoke(initial_state)
                decision = result.get("decision")
                if decision is not None:
                    processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                    self.logger.info(
                        "LangGraph orchestrated decision in %.2fs — "
                        "%d agents, confidence: %.0f%%",
                        processing_time,
                        len(result.get("agent_outputs", [])),
                        decision.confidence * 100,
                    )
                    return decision

            # --- Fallback: existing meta-learning path ---
            # Collect agent outputs in parallel
            agent_outputs = await self._collect_agent_outputs(
                market_state, query, timeout
            )

            # Filter out failed agents
            valid_outputs = [
                output
                for output in agent_outputs
                if output is not None and output.confidence >= MIN_AGENT_CONFIDENCE
            ]

            if not valid_outputs:
                return self._create_fallback_decision("No valid agent outputs")

            # Calculate dynamic weights
            weights = await self._calculate_dynamic_weights(market_state, valid_outputs)

            # Build consensus
            consensus = self._build_consensus(valid_outputs, weights)

            # Detect conflicts
            conflicts = self._detect_conflicts(valid_outputs, consensus)

            # Create final decision
            decision = self._create_orchestrated_decision(
                consensus, conflicts, valid_outputs, weights
            )

            # Update performance tracking
            self._update_performance_tracking(decision, valid_outputs)

            # Log decision
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info(
                f"Orchestrated decision in {processing_time:.2f}s with "
                f"{len(valid_outputs)} agents, confidence: {decision.confidence:.2%}"
            )

            return decision

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "coordinate_agents", "query": query}
            )
            return self._create_fallback_decision(str(e))

    async def _collect_agent_outputs(
        self, market_state: dict[str, Any], query: str, timeout: float
    ) -> list[AgentOutput]:
        """Collect outputs from all active agents in parallel."""
        agent_futures = {}

        # Submit tasks to thread pool
        for agent_id, agent in self.agents.items():
            if self.agent_states[agent_id] == AgentState.ACTIVE:
                future = self.executor.submit(
                    self._get_agent_output, agent_id, agent, market_state, query
                )
                agent_futures[future] = agent_id

        # Collect results with timeout
        outputs = []
        for future in as_completed(agent_futures, timeout=timeout):
            try:
                output = future.result()
                if output:
                    outputs.append(output)
            except Exception as e:
                agent_id = agent_futures[future]
                self.logger.warning("Agent %s failed: %s", agent_id, e)
                self._handle_agent_failure(agent_id)

        return outputs

    def _get_agent_output(
        self, agent_id: str, agent: Any, market_state: dict[str, Any], query: str
    ) -> AgentOutput | None:
        """Get output from a single agent."""
        try:
            start_time = datetime.now(timezone.utc)

            # Call agent's analyze method
            if hasattr(agent, "analyze"):
                result = agent.analyze(market_state, query)
            else:
                result = agent.predict(market_state)

            # Extract prediction and confidence
            if isinstance(result, dict):
                prediction = result.get("prediction", result.get("action", None))
                confidence = result.get("confidence", 0.5)
                reasoning = result.get("reasoning", "")
                metadata = result.get("metadata", {})
            else:
                prediction = result
                confidence = 0.5
                reasoning = ""
                metadata = {}

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

            return AgentOutput(
                agent_id=agent_id,
                prediction=prediction,
                confidence=confidence,
                reasoning=reasoning,
                processing_time=processing_time,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata,
            )

        except Exception as e:
            self.logger.error("Agent %s error: %s", agent_id, e)
            return None

    # ==========================================================================
    # META-LEARNING METHODS
    # ==========================================================================

    async def _calculate_dynamic_weights(
        self, market_state: dict[str, Any], agent_outputs: list[AgentOutput]
    ) -> dict[str, float]:
        """Calculate dynamic weights using meta-learning."""
        try:
            # Prepare state tensor
            state_features = self._extract_state_features(market_state)
            state_tensor = torch.tensor(state_features, dtype=torch.float32).to(
                self.device
            )

            # Prepare agent output tensor
            output_features = self._extract_output_features(agent_outputs)
            output_tensor = torch.tensor(output_features, dtype=torch.float32).to(
                self.device
            )

            # Get weights from meta-network
            with torch.no_grad():
                weights, _ = self.meta_network(state_tensor, output_tensor)
                weights = weights.squeeze().cpu().numpy()

            # Map weights to agent IDs
            agent_weights = {}
            for i, output in enumerate(agent_outputs):
                if i < len(weights):
                    agent_weights[output.agent_id] = float(weights[i])

            # Adjust based on recent performance
            agent_weights = self._adjust_weights_by_performance(agent_weights)

            # Normalize
            total = sum(agent_weights.values())
            if total > 0:
                agent_weights = {k: v / total for k, v in agent_weights.items()}

            return agent_weights

        except Exception as e:
            self.logger.error("Weight calculation error: %s", e)
            # Fallback to equal weights
            return {
                output.agent_id: 1.0 / len(agent_outputs) for output in agent_outputs
            }

    def _adjust_weights_by_performance(
        self, weights: dict[str, float]
    ) -> dict[str, float]:
        """Adjust weights based on recent agent performance."""
        adjusted = {}

        for agent_id, weight in weights.items():
            performance = self.agent_performance.get(agent_id)
            if performance:
                # Calculate performance multiplier
                reliability = performance.reliability_score
                recent_accuracy = (
                    np.mean(list(performance.accuracy_history)[-100:])
                    if performance.accuracy_history
                    else 0.5
                )

                multiplier = 0.5 + 0.5 * reliability * recent_accuracy
                adjusted[agent_id] = weight * multiplier
            else:
                adjusted[agent_id] = weight

        return adjusted

    # ==========================================================================
    # CONSENSUS BUILDING
    # ==========================================================================

    def _build_consensus(
        self, agent_outputs: list[AgentOutput], weights: dict[str, float]
    ) -> dict[str, Any]:
        """Build consensus from weighted agent outputs."""
        consensus = {
            "action": None,
            "confidence": 0.0,
            "reasoning": [],
            "vote_distribution": defaultdict(float),
        }

        # Aggregate predictions
        action_votes = defaultdict(float)
        total_confidence = 0.0

        for output in agent_outputs:
            weight = weights.get(output.agent_id, 0.0)
            action = str(output.prediction)

            action_votes[action] += weight * output.confidence
            total_confidence += weight * output.confidence

            if output.reasoning:
                consensus["reasoning"].append(
                    {
                        "agent": output.agent_id,
                        "reasoning": output.reasoning,
                        "weight": weight,
                    }
                )

        # Determine consensus action
        if action_votes:
            consensus["action"] = max(action_votes, key=action_votes.get)
            consensus["confidence"] = action_votes[consensus["action"]] / max(
                total_confidence, 1.0
            )
            consensus["vote_distribution"] = dict(action_votes)

        return consensus

    def _detect_conflicts(
        self, agent_outputs: list[AgentOutput], consensus: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Detect conflicting opinions among agents."""
        conflicts = []
        consensus_action = consensus["action"]

        for output in agent_outputs:
            if str(output.prediction) != consensus_action and output.confidence > 0.7:
                conflicts.append(
                    {
                        "agent": output.agent_id,
                        "prediction": output.prediction,
                        "confidence": output.confidence,
                        "reasoning": output.reasoning,
                    }
                )

        return conflicts

    # ==========================================================================
    # COMPETITIVE/COOPERATIVE DYNAMICS
    # ==========================================================================

    def implement_competitive_dynamics(self, task: str) -> dict[str, Any]:
        """
        Implement competitive dynamics between agents.
        Agents compete for resource allocation based on performance.
        """
        competition_results = {
            "winners": [],
            "resource_allocation": {},
            "performance_boost": {},
        }

        # Rank agents by recent performance
        agent_scores = {}
        for agent_id, performance in self.agent_performance.items():
            score = (
                performance.reliability_score
                * (performance.success_count + 1)
                / (performance.failure_count + 1)
            )
            agent_scores[agent_id] = score

        # Top performers get resource boost
        sorted_agents = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)

        for i, (agent_id, _) in enumerate(sorted_agents):
            if i < 3:  # Top 3 agents
                competition_results["winners"].append(agent_id)
                competition_results["resource_allocation"][
                    agent_id
                ] = 1.5  # 50% more resources
                competition_results["performance_boost"][agent_id] = 0.1
            else:
                competition_results["resource_allocation"][agent_id] = 1.0
                competition_results["performance_boost"][agent_id] = 0.0

        return competition_results

    def implement_cooperative_dynamics(self, agent_outputs: list[AgentOutput]) -> float:
        """
        Calculate cooperation score based on agent alignment.
        Higher score means better cooperation.
        """
        if len(agent_outputs) < 2:
            return 1.0

        # Calculate pairwise agreement
        agreements = []
        for i in range(len(agent_outputs)):
            for j in range(i + 1, len(agent_outputs)):
                if agent_outputs[i].prediction == agent_outputs[j].prediction:
                    agreements.append(1.0)
                else:
                    agreements.append(0.0)

        cooperation_score = np.mean(agreements) if agreements else 0.5

        # Reward cooperation in agent performance
        for output in agent_outputs:
            performance = self.agent_performance[output.agent_id]
            performance.reliability_score = min(
                1.0, performance.reliability_score + cooperation_score * 0.01
            )

        return cooperation_score

    # ==========================================================================
    # DECISION CREATION
    # ==========================================================================

    def _create_orchestrated_decision(
        self,
        consensus: dict[str, Any],
        conflicts: list[dict[str, Any]],
        agent_outputs: list[AgentOutput],
        weights: dict[str, float],
    ) -> OrchestratorDecision:
        """Create final orchestrated decision."""
        # Calculate consensus score
        consensus_score = self.implement_cooperative_dynamics(agent_outputs)

        # Build reasoning
        reasoning_parts = ["Orchestrator Analysis:"]
        reasoning_parts.append(
            f"- Consensus: {consensus['action']} ({consensus['confidence']:.2%} confidence)"
        )
        reasoning_parts.append(f"- Agent alignment: {consensus_score:.2%}")
        reasoning_parts.append(f"- Contributing agents: {len(agent_outputs)}")

        if conflicts:
            reasoning_parts.append(f"- Dissenting opinions: {len(conflicts)}")

        # Add top agent reasonings
        top_reasonings = sorted(
            consensus["reasoning"], key=lambda x: x["weight"], reverse=True
        )[:3]

        for r in top_reasonings:
            reasoning_parts.append(f"- {r['agent']}: {r['reasoning'][:100]}...")

        reasoning_text = "\n".join(reasoning_parts)
        legacy_decision_payload = {
            "action": consensus["action"],
            "confidence": consensus["confidence"],
            "consensus_score": consensus_score,
            "contributing_agents": [output.agent_id for output in agent_outputs],
            "dissenting_count": len(conflicts),
        }
        handoff_envelope = build_agent_handoff_envelope(
            topic="meta.decisions",
            producer_agent_id="X14_orchestrator",
            producer_class=self.__class__.__name__,
            schema="AGENT_DECISION_V1",
            handoff_type="decision",
            payload=legacy_decision_payload,
            confidence=float(consensus["confidence"]),
            reasoning=reasoning_text,
            decision={
                "action": str(consensus["action"]),
                "confidence": float(consensus["confidence"]),
                "reasoning": reasoning_text,
            },
            legacy_payload=legacy_decision_payload,
        )

        # Prepare execution parameters
        execution_params = {
            "priority": "high" if consensus["confidence"] > 0.8 else "normal",
            "risk_check_required": len(conflicts) > 2,
            "consensus_strength": consensus_score,
            "market_conditions": "volatile" if conflicts else "stable",
            "agent_handoff": handoff_envelope,
        }

        return OrchestratorDecision(
            action=consensus["action"],
            confidence=consensus["confidence"],
            contributing_agents=[output.agent_id for output in agent_outputs],
            agent_weights=weights,
            consensus_score=consensus_score,
            dissenting_opinions=conflicts,
            reasoning=reasoning_text,
            execution_params=execution_params,
        )

    def _create_fallback_decision(self, reason: str) -> OrchestratorDecision:
        """Create fallback decision when orchestration fails."""
        fallback_payload = {
            "action": "hold",
            "confidence": 0.0,
            "consensus_score": 0.0,
            "contributing_agents": [],
            "dissenting_count": 0,
            "fallback": True,
        }
        fallback_reasoning = f"Fallback decision: {reason}"
        fallback_handoff = build_agent_handoff_envelope(
            topic="meta.decisions",
            producer_agent_id="X14_orchestrator",
            producer_class=self.__class__.__name__,
            schema="AGENT_DECISION_V1",
            handoff_type="decision",
            payload=fallback_payload,
            confidence=0.0,
            reasoning=fallback_reasoning,
            decision={
                "action": "hold",
                "confidence": 0.0,
                "reasoning": fallback_reasoning,
            },
            legacy_payload=fallback_payload,
        )

        return OrchestratorDecision(
            action="hold",
            confidence=0.0,
            contributing_agents=[],
            agent_weights={},
            consensus_score=0.0,
            dissenting_opinions=[],
            reasoning=fallback_reasoning,
            execution_params={
                "priority": "low",
                "fallback": True,
                "agent_handoff": fallback_handoff,
            },
        )

    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================

    def _update_performance_tracking(
        self, decision: OrchestratorDecision, agent_outputs: list[AgentOutput]
    ) -> None:
        """Update performance metrics for all agents."""
        # Store decision
        self.decision_history.append(
            {
                "timestamp": datetime.now(timezone.utc),
                "decision": decision,
                "outputs": agent_outputs,
            }
        )

        # Update individual agent metrics
        for output in agent_outputs:
            performance = self.agent_performance[output.agent_id]

            # Update latency
            performance.latency_history.append(output.processing_time)

            # Confidence as proxy for accuracy (will be updated with actual results)
            performance.accuracy_history.append(output.confidence)

            # Update weight history
            weight = decision.agent_weights.get(output.agent_id, 0.0)
            self.weight_history[output.agent_id].append(weight)

    def update_with_results(
        self, decision_id: str, actual_outcome: dict[str, Any]
    ) -> None:
        """
        Update agent performance based on actual trading results.

        Args:
            decision_id: ID of the decision to update
            actual_outcome: Actual trading results
        """
        # Find decision in history
        # Update accuracy scores based on outcome
        # Retrain meta-learning model if needed
        pass  # Implementation depends on outcome tracking system

    # ==========================================================================
    # TRAINING METHODS
    # ==========================================================================

    def train_meta_learner(self, episodes: int = 1000) -> None:
        """Train the meta-learning network using PPO."""
        if self.rl_model is None:
            self.logger.warning("RL model not initialized, skipping training")
            return

        try:
            self.logger.info("Training meta-learner for %s episodes...", episodes)
            self.rl_model.learn(total_timesteps=episodes * 100)

            # Save trained model
            model_path = Path(META_MODEL_PATH)
            model_path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(self.meta_network.state_dict(), model_path)

            self.logger.info("✅ Meta-learner training complete")

        except Exception as e:
            self.logger.error("Training failed: %s", e)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _extract_state_features(self, market_state: dict[str, Any]) -> np.ndarray:
        """Extract features from market state."""
        features = []

        # Price features
        if "price" in market_state:
            features.extend(
                [
                    market_state["price"],
                    market_state.get("price_change", 0),
                    market_state.get("price_volatility", 0),
                ]
            )

        # Volume features
        if "volume" in market_state:
            features.extend(
                [market_state["volume"], market_state.get("volume_ratio", 1)]
            )

        # Technical indicators
        for indicator in ["rsi", "macd", "bb_position"]:
            features.append(market_state.get(indicator, 0))

        # Pad to fixed size
        while len(features) < 100:
            features.append(0.0)

        return np.array(features[:100], dtype=np.float32)

    def _extract_output_features(self, agent_outputs: list[AgentOutput]) -> np.ndarray:
        """Extract features from agent outputs."""
        features = []

        for output in agent_outputs:
            features.extend(
                [
                    output.confidence,
                    output.processing_time,
                    (
                        1.0
                        if output.prediction == "buy"
                        else -1.0 if output.prediction == "sell" else 0.0
                    ),
                ]
            )

        # Pad to fixed size
        max_features = len(self.agents) * 3
        while len(features) < max_features:
            features.append(0.0)

        return np.array(features[:max_features], dtype=np.float32)

    def _handle_agent_failure(self, agent_id: str) -> None:
        """Handle agent failure."""
        performance = self.agent_performance[agent_id]
        performance.failure_count += 1

        # Degrade agent if too many failures
        if performance.failure_count > 5:
            self.agent_states[agent_id] = AgentState.DEGRADED
            self.logger.warning("Agent %s degraded due to failures", agent_id)

    def get_agent_status(self) -> dict[str, Any]:
        """Get current status of all agents."""
        status = {}

        for agent_id in self.agents:
            performance = self.agent_performance[agent_id]
            recent_weights = list(self.weight_history[agent_id])[-10:]

            status[agent_id] = {
                "state": self.agent_states[agent_id].name,
                "reliability": performance.reliability_score,
                "avg_latency": (
                    np.mean(list(performance.latency_history)[-100:])
                    if performance.latency_history
                    else 0
                ),
                "recent_weight": np.mean(recent_weights) if recent_weights else 0,
                "success_rate": performance.success_count
                / (performance.success_count + performance.failure_count + 1),
            }

        return status

    def save_state(self) -> None:
        """Save current orchestrator state."""
        try:
            # Save weights
            weights_path = Path(AGENT_WEIGHTS_PATH)
            weights_path.parent.mkdir(parents=True, exist_ok=True)

            with open(weights_path, 'w', encoding='utf-8') as f:
                json.dump(dict(self.weight_history), f, indent=2)

            self.logger.info("Saved orchestrator state")

        except Exception as e:
            self.logger.error("Failed to save state: %s", e)

    # ==========================================================================
    # LANGGRAPH PIPELINE (TradingAgents-inspired stateful orchestration)
    # ==========================================================================

    def _build_orchestration_graph(self) -> Any:
        """Build and compile the LangGraph orchestration pipeline.

        Pipeline: analyst → debate → strategist → risk → END

        Returns:
            Compiled ``CompiledGraph`` ready for ``ainvoke``, or ``None`` if
            LangGraph is not available.
        """
        if not LANGGRAPH_AVAILABLE:
            return None
        try:
            builder = StateGraph(OrchestrationState)
            builder.add_node("analyst", self._analyst_node)
            builder.add_node("debate", self._debate_node)
            builder.add_node("strategist", self._strategist_node)
            builder.add_node("risk", self._risk_node)
            builder.add_edge(START, "analyst")
            builder.add_edge("analyst", "debate")
            builder.add_edge("debate", "strategist")
            builder.add_edge("strategist", "risk")
            builder.add_edge("risk", END)
            return builder.compile()
        except Exception as exc:
            self.logger.warning("Failed to compile LangGraph pipeline: %s", exc)
            return None

    async def _analyst_node(self, state: OrchestrationState) -> dict:
        """LangGraph node — collect raw outputs from all active X-agents.

        Mirrors the TradingAgents Analyst Team stage: each specialist agent
        produces an independent assessment that feeds into the debate stage.
        """
        outputs = await self._collect_agent_outputs(
            state["market_state"], state["query"], state.get("timeout", MAX_AGENT_TIMEOUT)
        )
        valid = [
            o for o in outputs
            if o is not None and o.confidence >= MIN_AGENT_CONFIDENCE
        ]
        return {"agent_outputs": valid}

    def _debate_node(self, state: OrchestrationState) -> dict:
        """LangGraph node — classify agent signals into bull/bear/hold camps.

        Mirrors the TradingAgents Bull/Bear Researcher debate stage without an
        additional LLM call: the agent signals themselves constitute the
        adversarial evidence. The resulting ``debate`` dict is injected into the
        strategist's reasoning context.
        """
        outputs: list = state.get("agent_outputs", [])
        _bullish = {"buy", "long", "bullish", "enter", "call", "iron_condor"}
        _bearish = {"sell", "short", "bearish", "exit", "put", "hedge"}

        bull_agents, bear_agents, hold_agents = [], [], []
        for o in outputs:
            pred = str(o.prediction).lower()
            if any(b in pred for b in _bullish):
                bull_agents.append(o)
            elif any(b in pred for b in _bearish):
                bear_agents.append(o)
            else:
                hold_agents.append(o)

        debate = {
            "bull_count": len(bull_agents),
            "bear_count": len(bear_agents),
            "hold_count": len(hold_agents),
            "bull_avg_confidence": (
                sum(o.confidence for o in bull_agents) / len(bull_agents)
                if bull_agents else 0.0
            ),
            "bear_avg_confidence": (
                sum(o.confidence for o in bear_agents) / len(bear_agents)
                if bear_agents else 0.0
            ),
            "bull_agents": [o.agent_id for o in bull_agents],
            "bear_agents": [o.agent_id for o in bear_agents],
            "hold_agents": [o.agent_id for o in hold_agents],
        }
        return {"debate": debate}

    async def _strategist_node(self, state: OrchestrationState) -> dict:
        """LangGraph node — compute dynamic weights + build consensus.

        Mirrors the TradingAgents Trader stage: synthesises the analyst and
        debate evidence into a weighted consensus action.
        """
        outputs: list = state.get("agent_outputs", [])
        if not outputs:
            return {
                "weights": {},
                "consensus": {"action": "hold", "confidence": 0.0, "reasoning": [], "vote_distribution": {}},
            }
        weights = await self._calculate_dynamic_weights(state["market_state"], outputs)
        consensus = self._build_consensus(outputs, weights)

        # Annotate consensus with debate context
        debate = state.get("debate", {})
        if debate:
            consensus["debate_context"] = debate

        return {"weights": weights, "consensus": consensus}

    def _risk_node(self, state: OrchestrationState) -> dict:
        """LangGraph node — conflict detection and final decision creation.

        Mirrors the TradingAgents Risk/Portfolio Manager stage: validates the
        proposed action and produces the authoritative ``OrchestratorDecision``.
        """
        outputs: list = state.get("agent_outputs", [])
        consensus: dict = state.get("consensus", {"action": "hold", "confidence": 0.0})
        weights: dict = state.get("weights", {})

        if not outputs:
            return {"decision": self._create_fallback_decision("No valid agent outputs")}

        conflicts = self._detect_conflicts(outputs, consensus)
        decision = self._create_orchestrated_decision(consensus, conflicts, outputs, weights)
        self._update_performance_tracking(decision, outputs)
        return {"decision": decision}


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: SpyderX14_OrchestratorAgent | None = None


def create_orchestrator_agent(
    config: dict[str, Any] | None = None,
) -> SpyderX14_OrchestratorAgent:
    """Factory function to create orchestrator agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX14_OrchestratorAgent(config)
    return _module_instance


def get_orchestrator_agent() -> SpyderX14_OrchestratorAgent | None:
    """Get existing orchestrator instance."""
    return _module_instance


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test orchestrator functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Orchestrator Agent Testing")
    parser.add_argument("--train", action="store_true", help="Train meta-learner")
    parser.add_argument("--test", action="store_true", help="Test coordination")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    args = parser.parse_args()

    orchestrator = create_orchestrator_agent()

    if args.train:
        logging.info("Training meta-learner...")
        orchestrator.train_meta_learner(episodes=100)

    if args.test:
        logging.info("\n=== Testing Agent Coordination ===")

        # Test market state
        market_state = {
            "price": 450.25,
            "price_change": 0.5,
            "volume": 1000000,
            "rsi": 65,
            "macd": 0.5,
            "vix": 18.5,
        }

        # Run coordination
        decision = await orchestrator.coordinate_agents(
            market_state, "should_enter_iron_condor"
        )

        logging.info("\nDecision: %s", decision.action)
        logging.info(f"Confidence: {decision.confidence:.2%}")
        logging.info(f"Consensus Score: {decision.consensus_score:.2%}")
        logging.info("Contributing Agents: %s", len(decision.contributing_agents))
        logging.info("\nReasoning:\n%s", decision.reasoning)

        if decision.dissenting_opinions:
            logging.info("\nDissenting Opinions: %s", len(decision.dissenting_opinions))
            for dissent in decision.dissenting_opinions[:3]:
                logging.info(
                    f"- {dissent['agent']}: {dissent['prediction']} ({dissent['confidence']:.2%})"
                )

    if args.status:
        logging.info("\n=== Agent Status ===")
        status = orchestrator.get_agent_status()

        for agent_id, info in status.items():
            logging.info("\n%s:", agent_id)
            logging.info("  State: %s", info['state'])
            logging.info(f"  Reliability: {info['reliability']:.2%}")
            logging.info(f"  Avg Latency: {info['avg_latency']:.3f}s")
            logging.info(f"  Recent Weight: {info['recent_weight']:.2%}")
            logging.info(f"  Success Rate: {info['success_rate']:.2%}")


if __name__ == "__main__":
    asyncio.run(main())
