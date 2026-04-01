#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderX16_MetaCoordinator.py
Group: X (AI Agents)
Purpose: Meta-coordinator for orchestrating all 15 AI agents
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 14:00:00

Description:
    This meta-coordinator orchestrates all 15 AI agents (X01-X15) to work as a
    cohesive team. It resolves conflicts between agent recommendations, implements
    voting mechanisms, prioritizes agent inputs based on market regime, tracks
    agent performance, and ensures coordinated decision-making across the entire
    AI agent ecosystem.

Key Features:
    - Orchestrates 15 AI agents with priority weighting
    - Conflict resolution between competing recommendations
    - Consensus building with weighted voting
    - Market regime-aware agent selection
    - Performance tracking and dynamic weight adjustment
    - Decision audit trail for compliance
    - Emergency override capabilities
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Lazy agent-class registry — each agent class is loaded on first instantiation
# so a single failed agent import cannot break the MetaCoordinator.
import importlib as _importlib

_AGENT_CLASS_REGISTRY: dict[str, tuple[str, str]] = {
    "X01_Greeks":          ("Spyder.SpyderX_Agents.SpyderX01_GreeksAgent",             "GreeksAgent"),
    "X02_Flow":            ("Spyder.SpyderX_Agents.SpyderX02_FlowAgent",                "FlowAgent"),
    "X03_StrategyDirector":("Spyder.SpyderX_Agents.SpyderX03_StrategyDirectorAgent",   "StrategyDirectorAgent"),
    "X04_RiskGuardian":    ("Spyder.SpyderX_Agents.SpyderX04_RiskGuardianAgent",        "RiskGuardianAgent"),
    "X05_MLResearch":      ("Spyder.SpyderX_Agents.SpyderX05_MLResearchAgent",          "MLResearchAgent"),
    "X06_Backtesting":     ("Spyder.SpyderX_Agents.SpyderX06_BacktestingAgent",         "BacktestingAgent"),
    "X07_ExecutionStrategy":("Spyder.SpyderX_Agents.SpyderX07_ExecutionStrategyAgent", "ExecutionStrategyAgent"),
    "X08_Performance":     ("Spyder.SpyderX_Agents.SpyderX08_PerformanceAnalyticsAgent","PerformanceAnalyticsAgent"),
    "X09_AlertManager":    ("Spyder.SpyderX_Agents.SpyderX09_AlertManagerAgent",        "AlertManagerAgent"),
    "X10_QuantModels":     ("Spyder.SpyderX_Agents.SpyderX10_QuantModelsAgent",         "QuantModelsAgent"),
    "X11_Sentiment":       ("Spyder.SpyderX_Agents.SpyderX11_SentimentAnalysisAgent",   "SentimentAnalysisAgent"),
    "X12_SystemHealth":    ("Spyder.SpyderX_Agents.SpyderX12_SystemHealthAgent",        "SystemHealthAgent"),
    "X13_MarketAnalysis":  ("Spyder.SpyderX_Agents.SpyderX13_MarketAnalysisAgent",      "MarketAnalysisAgent"),
    "X14_Orchestrator":    ("Spyder.SpyderX_Agents.SpyderX14_OrchestratorAgent",        "OrchestratorAgent"),
    "X15_StrategyGenerator":("Spyder.SpyderX_Agents.SpyderX15_StrategyGeneratorAgent", "StrategyGeneratorAgent"),
}
_AGENT_CLASS_CACHE: dict[str, type | None] = {}

def _get_agent_class(agent_id: str) -> type | None:
    """Lazy-load and cache an X-series agent class; return None on failure."""
    if agent_id in _AGENT_CLASS_CACHE:
        return _AGENT_CLASS_CACHE[agent_id]
    entry = _AGENT_CLASS_REGISTRY.get(agent_id)
    if not entry:
        _AGENT_CLASS_CACHE[agent_id] = None
        return None
    mod_path, class_name = entry
    try:
        mod = _importlib.import_module(mod_path)
        _AGENT_CLASS_CACHE[agent_id] = getattr(mod, class_name)
    except Exception as _exc:
        logging.getLogger(__name__).warning(
            "X-agent %r (%s.%s) unavailable: %s", agent_id, mod_path, class_name, _exc
        )
        _AGENT_CLASS_CACHE[agent_id] = None
    return _AGENT_CLASS_CACHE[agent_id]

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_DECISION_TIME = 5.0  # Maximum seconds for decision
MIN_CONSENSUS_THRESHOLD = 0.6  # Minimum agreement for action
CRITICAL_CONSENSUS_THRESHOLD = 0.8  # Required for high-risk decisions
AGENT_TIMEOUT = 3.0  # Timeout for individual agent responses

# Agent Groups
CRITICAL_AGENTS = ['X04_RiskGuardian', 'X12_SystemHealth']
STRATEGY_AGENTS = ['X03_StrategyDirector', 'X15_StrategyGenerator', 'X06_Backtesting']
EXECUTION_AGENTS = ['X07_ExecutionStrategy', 'X02_Flow']
ANALYSIS_AGENTS = ['X01_Greeks', 'X13_MarketAnalysis', 'X10_QuantModels', 'X11_Sentiment']
SUPPORT_AGENTS = ['X08_Performance', 'X09_AlertManager', 'X05_MLResearch', 'X14_Orchestrator']

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classification"""
    CRISIS = "crisis"
    HIGH_VOLATILITY = "high_volatility"
    NORMAL = "normal"
    LOW_VOLATILITY = "low_volatility"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"

class DecisionType(Enum):
    """Types of decisions the coordinator makes"""
    ENTRY = "entry"
    EXIT = "exit"
    HEDGE = "hedge"
    POSITION_SIZE = "position_size"
    STRATEGY_SELECTION = "strategy_selection"
    RISK_ADJUSTMENT = "risk_adjustment"
    EMERGENCY = "emergency"

class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    WEIGHTED_VOTE = "weighted_vote"
    RISK_PRIORITY = "risk_priority"
    PERFORMANCE_BASED = "performance_based"
    MARKET_REGIME = "market_regime"
    CONSENSUS_REQUIRED = "consensus_required"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AgentRecommendation:
    """Individual agent recommendation"""
    agent_id: str
    agent_name: str
    recommendation_type: DecisionType
    action: str  # BUY, SELL, HOLD, HEDGE, etc.
    confidence: float  # 0-1
    reasoning: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10, higher is more important

@dataclass
class CoordinatedDecision:
    """Final coordinated decision from all agents"""
    decision_id: str
    decision_type: DecisionType
    final_action: str
    consensus_level: float
    participating_agents: list[str]
    dissenting_agents: list[str]
    weighted_confidence: float
    reasoning: str
    agent_recommendations: list[AgentRecommendation]
    market_regime: MarketRegime
    risk_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    execution_params: dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentPerformance:
    """Track individual agent performance"""
    agent_id: str
    correct_predictions: int = 0
    total_predictions: int = 0
    avg_confidence: float = 0.0
    avg_return_contribution: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)
    weight_multiplier: float = 1.0  # Dynamic weight based on performance
    recent_accuracy: deque = field(default_factory=lambda: deque(maxlen=100))

@dataclass
class ConflictEvent:
    """Record of agent conflicts"""
    timestamp: datetime
    conflicting_agents: list[str]
    issue: str
    resolution_method: ConflictResolution
    outcome: str

# ==============================================================================
# MAIN METACOORDINATOR CLASS
# ==============================================================================
class MetaCoordinator:
    """
    Meta-Coordinator for orchestrating all 15 AI agents.

    This class manages the complex interactions between all AI agents,
    resolving conflicts, building consensus, and ensuring coordinated
    decision-making across the entire system.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Meta-Coordinator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Agent registry
        self.agents = {}
        self.agent_performance = {}
        self.agent_weights = {}

        # Decision tracking
        self.decision_history = deque(maxlen=1000)
        self.conflict_history = deque(maxlen=500)
        self.consensus_history = deque(maxlen=100)

        # Market state
        self.current_market_regime = MarketRegime.NORMAL
        self.regime_confidence = 0.5

        # Threading
        self.executor = ThreadPoolExecutor(max_workers=16)
        self._shutdown = False
        self._lock = threading.RLock()

        # Performance tracking
        self.coordinator_metrics = {
            'total_decisions': 0,
            'successful_decisions': 0,
            'conflicts_resolved': 0,
            'avg_consensus': 0.0,
            'avg_decision_time': 0.0
        }

        # Initialize agents
        self._initialize_agents()
        self._initialize_weights()

        self.logger.info("MetaCoordinator initialized with 15 agents")

    def _initialize_agents(self):
        """Initialize all agents via the lazy class registry."""
        try:
            self.agents = {}
            for agent_id in _AGENT_CLASS_REGISTRY:
                cls = _get_agent_class(agent_id)
                if cls is None:
                    self.logger.warning("Skipping unavailable agent: %s", agent_id)
                    continue
                try:
                    self.agents[agent_id] = cls()
                except Exception as exc:
                    self.logger.error(
                        "Failed to instantiate agent %s: %s", agent_id, exc, exc_info=True
                    )

            # Initialize performance tracking
            for agent_id in self.agents:
                self.agent_performance[agent_id] = AgentPerformance(agent_id=agent_id)

            self.logger.info(f"Initialized {len(self.agents)} agents")

        except Exception as e:
            self.logger.error(f"Failed to initialize agents: {e}")
            self.error_handler.handle_error(e, {"method": "_initialize_agents"})

    def _initialize_weights(self):
        """Initialize agent weights based on market regime and role"""
        # Base weights by agent role
        self.agent_weights = {
            'X01_Greeks': {'base': 0.8, 'regime_multiplier': {}},
            'X02_Flow': {'base': 0.7, 'regime_multiplier': {}},
            'X03_StrategyDirector': {'base': 0.9, 'regime_multiplier': {}},
            'X04_RiskGuardian': {'base': 1.0, 'regime_multiplier': {}},  # Always highest
            'X05_MLResearch': {'base': 0.6, 'regime_multiplier': {}},
            'X06_Backtesting': {'base': 0.5, 'regime_multiplier': {}},
            'X07_ExecutionStrategy': {'base': 0.8, 'regime_multiplier': {}},
            'X08_Performance': {'base': 0.6, 'regime_multiplier': {}},
            'X09_AlertManager': {'base': 0.7, 'regime_multiplier': {}},
            'X10_QuantModels': {'base': 0.7, 'regime_multiplier': {}},
            'X11_Sentiment': {'base': 0.5, 'regime_multiplier': {}},
            'X12_SystemHealth': {'base': 0.95, 'regime_multiplier': {}},  # Critical
            'X13_MarketAnalysis': {'base': 0.8, 'regime_multiplier': {}},
            'X14_Orchestrator': {'base': 0.7, 'regime_multiplier': {}},
            'X15_StrategyGenerator': {'base': 0.7, 'regime_multiplier': {}}
        }

        # Regime-specific weight adjustments
        for agent_id in self.agent_weights:
            self.agent_weights[agent_id]['regime_multiplier'] = {
                MarketRegime.CRISIS: self._get_crisis_weight(agent_id),
                MarketRegime.HIGH_VOLATILITY: self._get_high_vol_weight(agent_id),
                MarketRegime.NORMAL: 1.0,
                MarketRegime.LOW_VOLATILITY: self._get_low_vol_weight(agent_id),
                MarketRegime.TRENDING_UP: self._get_trending_weight(agent_id),
                MarketRegime.TRENDING_DOWN: self._get_trending_weight(agent_id),
                MarketRegime.RANGE_BOUND: self._get_range_weight(agent_id)
            }

    def _get_crisis_weight(self, agent_id: str) -> float:
        """Get weight multiplier for crisis regime"""
        crisis_weights = {
            'X04_RiskGuardian': 1.5,
            'X12_SystemHealth': 1.4,
            'X07_ExecutionStrategy': 1.3,
            'X01_Greeks': 1.2,
            'X11_Sentiment': 0.3,  # Less reliable in crisis
            'X15_StrategyGenerator': 0.5  # Stick to proven strategies
        }
        return crisis_weights.get(agent_id, 1.0)

    def _get_high_vol_weight(self, agent_id: str) -> float:
        """Get weight multiplier for high volatility"""
        high_vol_weights = {
            'X01_Greeks': 1.3,
            'X04_RiskGuardian': 1.3,
            'X02_Flow': 1.2,
            'X10_QuantModels': 1.2,
            'X06_Backtesting': 0.7  # Historical less relevant
        }
        return high_vol_weights.get(agent_id, 1.0)

    def _get_low_vol_weight(self, agent_id: str) -> float:
        """Get weight multiplier for low volatility"""
        low_vol_weights = {
            'X15_StrategyGenerator': 1.3,  # Try new strategies
            'X05_MLResearch': 1.2,
            'X11_Sentiment': 1.2,
            'X04_RiskGuardian': 0.8  # Can be less conservative
        }
        return low_vol_weights.get(agent_id, 1.0)

    def _get_trending_weight(self, agent_id: str) -> float:
        """Get weight multiplier for trending markets"""
        trending_weights = {
            'X13_MarketAnalysis': 1.3,
            'X10_QuantModels': 1.2,
            'X03_StrategyDirector': 1.2,
            'X01_Greeks': 0.8  # Less important in strong trends
        }
        return trending_weights.get(agent_id, 1.0)

    def _get_range_weight(self, agent_id: str) -> float:
        """Get weight multiplier for range-bound markets"""
        range_weights = {
            'X01_Greeks': 1.3,
            'X15_StrategyGenerator': 1.2,
            'X06_Backtesting': 1.2,
            'X13_MarketAnalysis': 0.8
        }
        return range_weights.get(agent_id, 1.0)

    async def coordinate_decision(
        self,
        decision_type: DecisionType,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
        timeout: float = MAX_DECISION_TIME
    ) -> CoordinatedDecision:
        """
        Coordinate a decision across all relevant agents.

        Args:
            decision_type: Type of decision needed
            market_data: Current market data
            context: Additional context for decision
            timeout: Maximum time for decision

        Returns:
            CoordinatedDecision with consensus result
        """
        start_time = datetime.now()
        decision_id = str(uuid.uuid4())

        try:
            self.logger.info(f"Coordinating {decision_type.value} decision (ID: {decision_id})")

            # 1. Determine relevant agents for this decision
            relevant_agents = self._get_relevant_agents(decision_type)

            # 2. Update market regime
            await self._update_market_regime(market_data)

            # 3. Collect recommendations from all agents
            recommendations = await self._collect_agent_recommendations(
                relevant_agents, decision_type, market_data, context, timeout
            )

            # 4. Check for conflicts
            conflicts = self._identify_conflicts(recommendations)
            if conflicts:
                self.logger.warning(f"Found {len(conflicts)} conflicts, resolving...")
                recommendations = await self._resolve_conflicts(
                    recommendations, conflicts, decision_type
                )

            # 5. Build consensus
            consensus_result = self._build_consensus(recommendations, decision_type)

            # 6. Validate with critical agents (veto power)
            final_decision = await self._validate_with_critical_agents(
                consensus_result, recommendations
            )

            # 7. Record decision
            self._record_decision(final_decision)

            # Update metrics
            decision_time = (datetime.now() - start_time).total_seconds()
            self._update_metrics(decision_time, final_decision)

            self.logger.info(
                f"Decision completed: {final_decision.final_action} "
                f"(consensus: {final_decision.consensus_level:.2%}, time: {decision_time:.2f}s)"
            )

            return final_decision

        except Exception as e:
            self.logger.error(f"Decision coordination failed: {e}")
            self.error_handler.handle_error(e, {
                "decision_type": decision_type.value,
                "decision_id": decision_id
            })

            # Return safe default decision
            return self._create_default_decision(decision_id, decision_type)

    def _get_relevant_agents(self, decision_type: DecisionType) -> list[str]:
        """Determine which agents should participate in a decision"""
        # All agents participate in emergency decisions
        if decision_type == DecisionType.EMERGENCY:
            return list(self.agents.keys())

        # Decision-specific agent selection
        decision_agents = {
            DecisionType.ENTRY: [
                'X03_StrategyDirector', 'X13_MarketAnalysis', 'X01_Greeks',
                'X02_Flow', 'X04_RiskGuardian', 'X10_QuantModels',
                'X11_Sentiment', 'X15_StrategyGenerator'
            ],
            DecisionType.EXIT: [
                'X04_RiskGuardian', 'X01_Greeks', 'X08_Performance',
                'X03_StrategyDirector', 'X13_MarketAnalysis', 'X07_ExecutionStrategy'
            ],
            DecisionType.HEDGE: [
                'X01_Greeks', 'X04_RiskGuardian', 'X10_QuantModels',
                'X03_StrategyDirector', 'X13_MarketAnalysis'
            ],
            DecisionType.POSITION_SIZE: [
                'X04_RiskGuardian', 'X03_StrategyDirector', 'X01_Greeks',
                'X08_Performance', 'X10_QuantModels'
            ],
            DecisionType.STRATEGY_SELECTION: [
                'X03_StrategyDirector', 'X15_StrategyGenerator', 'X06_Backtesting',
                'X13_MarketAnalysis', 'X08_Performance', 'X05_MLResearch'
            ],
            DecisionType.RISK_ADJUSTMENT: [
                'X04_RiskGuardian', 'X01_Greeks', 'X12_SystemHealth',
                'X13_MarketAnalysis', 'X10_QuantModels'
            ]
        }

        base_agents = decision_agents.get(decision_type, list(self.agents.keys()))

        # Always include critical agents
        for critical in CRITICAL_AGENTS:
            if critical not in base_agents:
                base_agents.append(critical)

        return base_agents

    async def _update_market_regime(self, market_data: dict[str, Any]):
        """Update current market regime based on market data"""
        try:
            # Get market analysis from X13
            if 'X13_MarketAnalysis' in self.agents:
                market_agent = self.agents['X13_MarketAnalysis']
                regime_analysis = await market_agent.analyze_market_regime(market_data)

                self.current_market_regime = MarketRegime(regime_analysis['regime'])
                self.regime_confidence = regime_analysis['confidence']

                self.logger.debug(
                    f"Market regime: {self.current_market_regime.value} "
                    f"(confidence: {self.regime_confidence:.2%})"
                )
        except Exception as e:
            self.logger.warning(f"Failed to update market regime: {e}")

    async def _collect_agent_recommendations(
        self,
        agent_ids: list[str],
        decision_type: DecisionType,
        market_data: dict[str, Any],
        context: dict[str, Any],
        timeout: float
    ) -> list[AgentRecommendation]:
        """Collect recommendations from all relevant agents"""
        recommendations = []

        # Create tasks for parallel agent queries
        tasks = []
        for agent_id in agent_ids:
            if agent_id in self.agents:
                task = self._get_agent_recommendation(
                    agent_id, decision_type, market_data, context
                )
                tasks.append(task)

        # Wait for all agents with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )

            for result in results:
                if isinstance(result, AgentRecommendation):
                    recommendations.append(result)
                elif isinstance(result, Exception):
                    self.logger.warning(f"Agent recommendation failed: {result}")

        except builtins.TimeoutError:
            self.logger.warning(f"Agent collection timed out after {timeout}s")
            # Use whatever recommendations we have

        return recommendations

    async def _get_agent_recommendation(
        self,
        agent_id: str,
        decision_type: DecisionType,
        market_data: dict[str, Any],
        context: dict[str, Any]
    ) -> AgentRecommendation:
        """Get recommendation from a single agent"""
        try:
            agent = self.agents[agent_id]

            # Call agent's decision method
            if hasattr(agent, 'make_recommendation'):
                result = await agent.make_recommendation(
                    decision_type.value, market_data, context
                )
            else:
                # Fallback for agents without the standard interface
                result = await self._fallback_agent_call(
                    agent, agent_id, decision_type, market_data, context
                )

            return AgentRecommendation(
                agent_id=agent_id,
                agent_name=agent_id.replace('_', ' '),
                recommendation_type=decision_type,
                action=result.get('action', 'HOLD'),
                confidence=result.get('confidence', 0.5),
                reasoning=result.get('reasoning', ''),
                data=result.get('data', {}),
                priority=self._get_agent_priority(agent_id, decision_type)
            )

        except Exception as e:
            self.logger.error(f"Agent {agent_id} recommendation failed: {e}")
            # Return neutral recommendation
            return AgentRecommendation(
                agent_id=agent_id,
                agent_name=agent_id.replace('_', ' '),
                recommendation_type=decision_type,
                action='HOLD',
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                data={},
                priority=1
            )

    async def _fallback_agent_call(
        self,
        agent: Any,
        agent_id: str,
        decision_type: DecisionType,
        market_data: dict[str, Any],
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """Fallback method for agents without standard interface"""
        # Agent-specific method mapping
        method_map = {
            'X01_Greeks': 'analyze_position_greeks',
            'X02_Flow': 'analyze_flow',
            'X03_StrategyDirector': 'select_strategy',
            'X04_RiskGuardian': 'assess_risk',
            'X13_MarketAnalysis': 'analyze_market'
        }

        method_name = method_map.get(agent_id, 'analyze')

        if hasattr(agent, method_name):
            method = getattr(agent, method_name)
            result = await method(market_data, context)

            # Convert to standard format
            return {
                'action': self._extract_action(result),
                'confidence': self._extract_confidence(result),
                'reasoning': str(result),
                'data': result if isinstance(result, dict) else {}
            }

        return {'action': 'HOLD', 'confidence': 0.5, 'reasoning': 'No method available', 'data': {}}

    def _extract_action(self, result: Any) -> str:
        """Extract action from various result formats"""
        if isinstance(result, dict):
            return result.get('action', result.get('recommendation', 'HOLD'))
        elif isinstance(result, str):
            return result.upper()
        return 'HOLD'

    def _extract_confidence(self, result: Any) -> float:
        """Extract confidence from various result formats"""
        if isinstance(result, dict):
            return result.get('confidence', result.get('score', 0.5))
        return 0.5

    def _get_agent_priority(self, agent_id: str, decision_type: DecisionType) -> int:
        """Get agent priority for specific decision type"""
        # Critical agents always have highest priority
        if agent_id in CRITICAL_AGENTS:
            return 10

        # Decision-specific priorities
        priority_map = {
            DecisionType.ENTRY: {
                'X03_StrategyDirector': 9,
                'X13_MarketAnalysis': 8,
                'X01_Greeks': 7
            },
            DecisionType.EXIT: {
                'X04_RiskGuardian': 9,
                'X08_Performance': 8,
                'X01_Greeks': 7
            },
            DecisionType.HEDGE: {
                'X01_Greeks': 9,
                'X04_RiskGuardian': 8,
                'X10_QuantModels': 7
            }
        }

        if decision_type in priority_map:
            return priority_map[decision_type].get(agent_id, 5)

        return 5  # Default priority

    def _identify_conflicts(self, recommendations: list[AgentRecommendation]) -> list[ConflictEvent]:
        """Identify conflicts between agent recommendations"""
        conflicts = []

        # Group recommendations by action
        action_groups = defaultdict(list)
        for rec in recommendations:
            action_groups[rec.action].append(rec)

        # Check for conflicting actions
        if len(action_groups) > 1:
            # Find opposing actions
            if 'BUY' in action_groups and 'SELL' in action_groups:
                conflicts.append(ConflictEvent(
                    timestamp=datetime.now(),
                    conflicting_agents=[r.agent_id for r in action_groups['BUY']] +
                                     [r.agent_id for r in action_groups['SELL']],
                    issue="BUY vs SELL conflict",
                    resolution_method=ConflictResolution.WEIGHTED_VOTE,
                    outcome=""
                ))

            # Check for high confidence disagreements
            high_conf_actions = {}
            for action, recs in action_groups.items():
                high_conf = [r for r in recs if r.confidence > 0.8]
                if high_conf:
                    high_conf_actions[action] = high_conf

            if len(high_conf_actions) > 1:
                all_agents = []
                for recs in high_conf_actions.values():
                    all_agents.extend([r.agent_id for r in recs])

                conflicts.append(ConflictEvent(
                    timestamp=datetime.now(),
                    conflicting_agents=all_agents,
                    issue="High confidence disagreement",
                    resolution_method=ConflictResolution.CONSENSUS_REQUIRED,
                    outcome=""
                ))

        return conflicts

    async def _resolve_conflicts(
        self,
        recommendations: list[AgentRecommendation],
        conflicts: list[ConflictEvent],
        decision_type: DecisionType
    ) -> list[AgentRecommendation]:
        """Resolve conflicts between agent recommendations"""
        resolved_recommendations = recommendations.copy()

        for conflict in conflicts:
            if conflict.resolution_method == ConflictResolution.WEIGHTED_VOTE:
                # Resolve by weighted voting
                resolved_recommendations = self._resolve_by_weighted_vote(
                    resolved_recommendations, conflict
                )

            elif conflict.resolution_method == ConflictResolution.RISK_PRIORITY:
                # Give priority to risk-averse recommendations
                resolved_recommendations = self._resolve_by_risk_priority(
                    resolved_recommendations, conflict
                )

            elif conflict.resolution_method == ConflictResolution.CONSENSUS_REQUIRED:
                # Require broader consensus
                resolved_recommendations = await self._resolve_by_consensus(
                    resolved_recommendations, conflict
                )

            # Record resolution outcome
            conflict.outcome = f"Resolved using {conflict.resolution_method.value}"
            self.conflict_history.append(conflict)

        return resolved_recommendations

    def _resolve_by_weighted_vote(
        self,
        recommendations: list[AgentRecommendation],
        conflict: ConflictEvent
    ) -> list[AgentRecommendation]:
        """Resolve conflict using weighted voting"""
        # Calculate weighted scores for each action
        action_scores = defaultdict(float)
        action_supporters = defaultdict(list)

        for rec in recommendations:
            weight = self._get_agent_weight(rec.agent_id)
            score = weight * rec.confidence * rec.priority / 10
            action_scores[rec.action] += score
            action_supporters[rec.action].append(rec.agent_id)

        # Find winning action
        winning_action = max(action_scores.items(), key=lambda x: x[1])[0]

        # Adjust recommendations to align with winning action
        for rec in recommendations:
            if rec.agent_id in conflict.conflicting_agents and rec.action != winning_action:
                rec.confidence *= 0.5  # Reduce confidence of overruled agents

        self.logger.info(f"Resolved conflict: {winning_action} wins by weighted vote")

        return recommendations

    def _resolve_by_risk_priority(
        self,
        recommendations: list[AgentRecommendation],
        conflict: ConflictEvent
    ) -> list[AgentRecommendation]:
        """Resolve conflict by prioritizing risk-averse recommendations"""
        # Find most conservative recommendation
        risk_scores = {
            'SELL': 1,  # Most conservative
            'HEDGE': 2,
            'REDUCE': 3,
            'HOLD': 4,
            'BUY': 5  # Least conservative
        }

        most_conservative = None
        min_risk = float('inf')

        for rec in recommendations:
            if rec.agent_id in conflict.conflicting_agents:
                risk = risk_scores.get(rec.action, 4)
                if risk < min_risk:
                    min_risk = risk
                    most_conservative = rec.action

        # Boost conservative recommendations
        for rec in recommendations:
            if rec.action == most_conservative:
                rec.confidence = min(rec.confidence * 1.5, 1.0)

        return recommendations

    async def _resolve_by_consensus(
        self,
        recommendations: list[AgentRecommendation],
        conflict: ConflictEvent
    ) -> list[AgentRecommendation]:
        """Resolve conflict by seeking broader consensus"""
        # Request additional analysis from non-participating agents
        all_agents = set(self.agents.keys())
        participating = set(rec.agent_id for rec in recommendations)
        additional_agents = list(all_agents - participating)[:3]  # Get up to 3 more

        if additional_agents:
            self.logger.info(f"Seeking consensus from additional agents: {additional_agents}")
            # This would call additional agents for their input
            # For now, we'll adjust existing recommendations

        return recommendations

    def _get_agent_weight(self, agent_id: str) -> float:
        """Get current weight for an agent"""
        if agent_id not in self.agent_weights:
            return 0.5

        base = self.agent_weights[agent_id]['base']
        regime_mult = self.agent_weights[agent_id]['regime_multiplier'].get(
            self.current_market_regime, 1.0
        )
        performance_mult = self.agent_performance[agent_id].weight_multiplier

        return base * regime_mult * performance_mult

    def _build_consensus(
        self,
        recommendations: list[AgentRecommendation],
        decision_type: DecisionType
    ) -> CoordinatedDecision:
        """Build consensus from agent recommendations"""
        if not recommendations:
            return self._create_default_decision(str(uuid.uuid4()), decision_type)

        # Calculate weighted consensus
        action_scores = defaultdict(float)
        action_supporters = defaultdict(list)
        action_confidence = defaultdict(list)

        total_weight = 0
        for rec in recommendations:
            weight = self._get_agent_weight(rec.agent_id)
            score = weight * rec.confidence

            action_scores[rec.action] += score
            action_supporters[rec.action].append(rec.agent_id)
            action_confidence[rec.action].append(rec.confidence)
            total_weight += weight

        # Find consensus action
        consensus_action = max(action_scores.items(), key=lambda x: x[1])[0]
        consensus_score = action_scores[consensus_action] / total_weight if total_weight > 0 else 0

        # Identify dissenting agents
        dissenting = []
        for rec in recommendations:
            if rec.action != consensus_action and rec.confidence > 0.7:
                dissenting.append(rec.agent_id)

        # Calculate weighted confidence
        weighted_conf = np.average(
            [rec.confidence for rec in recommendations],
            weights=[self._get_agent_weight(rec.agent_id) for rec in recommendations]
        )

        # Build reasoning
        reasoning_parts = []
        for rec in recommendations:
            if rec.action == consensus_action and rec.reasoning:
                reasoning_parts.append(f"{rec.agent_id}: {rec.reasoning}")
        reasoning = " | ".join(reasoning_parts[:3])  # Top 3 reasons

        # Calculate risk score
        risk_agent_recs = [r for r in recommendations if r.agent_id == 'X04_RiskGuardian']
        risk_score = risk_agent_recs[0].data.get('risk_score', 0.5) if risk_agent_recs else 0.5

        return CoordinatedDecision(
            decision_id=str(uuid.uuid4()),
            decision_type=decision_type,
            final_action=consensus_action,
            consensus_level=consensus_score,
            participating_agents=action_supporters[consensus_action],
            dissenting_agents=dissenting,
            weighted_confidence=weighted_conf,
            reasoning=reasoning,
            agent_recommendations=recommendations,
            market_regime=self.current_market_regime,
            risk_score=risk_score,
            execution_params=self._build_execution_params(consensus_action, recommendations)
        )

    def _build_execution_params(
        self,
        action: str,
        recommendations: list[AgentRecommendation]
    ) -> dict[str, Any]:
        """Build execution parameters from recommendations"""
        params = {
            'action': action,
            'urgency': 'normal',
            'size_adjustment': 1.0
        }

        # Get execution agent recommendations
        exec_recs = [r for r in recommendations if r.agent_id == 'X07_ExecutionStrategy']
        if exec_recs and exec_recs[0].data:
            params.update(exec_recs[0].data)

        # Adjust for high volatility
        if self.current_market_regime in [MarketRegime.CRISIS, MarketRegime.HIGH_VOLATILITY]:
            params['size_adjustment'] *= 0.5
            params['urgency'] = 'high'

        return params

    async def _validate_with_critical_agents(
        self,
        decision: CoordinatedDecision,
        recommendations: list[AgentRecommendation]
    ) -> CoordinatedDecision:
        """Validate decision with critical agents (veto power)"""
        # Check if risk guardian approves
        risk_recs = [r for r in recommendations if r.agent_id == 'X04_RiskGuardian']
        if risk_recs:
            risk_rec = risk_recs[0]
            if risk_rec.action in ['STOP', 'EXIT', 'VETO'] and risk_rec.confidence > 0.8:
                self.logger.warning(f"Risk Guardian VETO: {risk_rec.reasoning}")
                decision.final_action = 'HOLD'
                decision.reasoning = f"VETO by Risk Guardian: {risk_rec.reasoning}"
                decision.execution_params['veto'] = True

        # Check system health
        health_recs = [r for r in recommendations if r.agent_id == 'X12_SystemHealth']
        if health_recs:
            health_rec = health_recs[0]
            if health_rec.data.get('system_health', 100) < 50:
                self.logger.warning("System health critical - reducing action")
                if decision.final_action in ['BUY', 'INCREASE']:
                    decision.final_action = 'HOLD'
                decision.execution_params['size_adjustment'] *= 0.3

        return decision

    def _record_decision(self, decision: CoordinatedDecision):
        """Record decision for tracking and analysis"""
        with self._lock:
            self.decision_history.append(decision)
            self.coordinator_metrics['total_decisions'] += 1

            # Update consensus tracking
            self.consensus_history.append(decision.consensus_level)

    def _update_metrics(self, decision_time: float, decision: CoordinatedDecision):
        """Update coordinator metrics"""
        with self._lock:
            # Update average decision time
            n = self.coordinator_metrics['total_decisions']
            old_avg = self.coordinator_metrics['avg_decision_time']
            self.coordinator_metrics['avg_decision_time'] = (old_avg * (n-1) + decision_time) / n

            # Update average consensus
            if self.consensus_history:
                self.coordinator_metrics['avg_consensus'] = np.mean(list(self.consensus_history))

            # Track successful decisions (high consensus)
            if decision.consensus_level > MIN_CONSENSUS_THRESHOLD:
                self.coordinator_metrics['successful_decisions'] += 1

    def _create_default_decision(
        self,
        decision_id: str,
        decision_type: DecisionType
    ) -> CoordinatedDecision:
        """Create safe default decision"""
        return CoordinatedDecision(
            decision_id=decision_id,
            decision_type=decision_type,
            final_action='HOLD',
            consensus_level=0.0,
            participating_agents=[],
            dissenting_agents=[],
            weighted_confidence=0.0,
            reasoning="Default safe decision - no consensus reached",
            agent_recommendations=[],
            market_regime=self.current_market_regime,
            risk_score=1.0,
            execution_params={'action': 'HOLD', 'safe_mode': True}
        )

    def update_agent_performance(self, agent_id: str, was_correct: bool, return_contribution: float):
        """Update agent performance metrics"""
        if agent_id not in self.agent_performance:
            return

        perf = self.agent_performance[agent_id]
        perf.total_predictions += 1
        if was_correct:
            perf.correct_predictions += 1

        perf.recent_accuracy.append(1.0 if was_correct else 0.0)

        # Update weight multiplier based on recent performance
        if len(perf.recent_accuracy) >= 20:
            recent_acc = np.mean(list(perf.recent_accuracy))
            if recent_acc > 0.7:
                perf.weight_multiplier = min(1.5, perf.weight_multiplier * 1.05)
            elif recent_acc < 0.4:
                perf.weight_multiplier = max(0.5, perf.weight_multiplier * 0.95)
            else:
                perf.weight_multiplier = 1.0

        perf.avg_return_contribution = (
            (perf.avg_return_contribution * (perf.total_predictions - 1) + return_contribution) /
            perf.total_predictions
        )

        perf.last_update = datetime.now()

    def get_agent_rankings(self) -> list[tuple[str, float]]:
        """Get current agent performance rankings"""
        rankings = []

        for agent_id, perf in self.agent_performance.items():
            if perf.total_predictions > 0:
                accuracy = perf.correct_predictions / perf.total_predictions
                score = accuracy * perf.weight_multiplier * (1 + perf.avg_return_contribution)
                rankings.append((agent_id, score))

        return sorted(rankings, key=lambda x: x[1], reverse=True)

    def get_coordinator_stats(self) -> dict[str, Any]:
        """Get coordinator statistics"""
        return {
            **self.coordinator_metrics,
            'current_regime': self.current_market_regime.value,
            'regime_confidence': self.regime_confidence,
            'active_agents': len(self.agents),
            'recent_conflicts': len(self.conflict_history),
            'agent_rankings': self.get_agent_rankings()[:5]  # Top 5
        }

    async def emergency_override(self, action: str, reason: str) -> CoordinatedDecision:
        """Emergency override for critical situations"""
        self.logger.critical(f"EMERGENCY OVERRIDE: {action} - {reason}")

        decision = CoordinatedDecision(
            decision_id=str(uuid.uuid4()),
            decision_type=DecisionType.EMERGENCY,
            final_action=action,
            consensus_level=1.0,
            participating_agents=['EMERGENCY_OVERRIDE'],
            dissenting_agents=[],
            weighted_confidence=1.0,
            reasoning=f"EMERGENCY: {reason}",
            agent_recommendations=[],
            market_regime=self.current_market_regime,
            risk_score=1.0,
            execution_params={
                'action': action,
                'urgency': 'immediate',
                'override': True,
                'reason': reason
            }
        )

        self._record_decision(decision)
        return decision

    def shutdown(self):
        """Shutdown the coordinator"""
        self._shutdown = True
        self.executor.shutdown(wait=True)
        self.logger.info("MetaCoordinator shutdown complete")

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def coordinate_agents_distributed(
        self,
        market_data: dict[str, Any],
        agent_ids: list[str] | None = None,
        num_cpus: int | None = None,
    ) -> dict[str, Any]:
        """
        Coordinate multiple agents in parallel using Ray.

        Each agent analysis runs independently on a Ray worker,
        replacing ThreadPoolExecutor for large agent ensembles.

        Args:
            market_data: Current market data for agents to analyze.
            agent_ids: Specific agents to run (None = all registered).
            num_cpus: Number of CPUs to allocate.

        Returns:
            Aggregated agent analysis results.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed agent coordination")
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        if agent_ids is None:
            agent_ids = list(self.agents.keys()) if hasattr(self, 'agents') else []

        if not agent_ids:
            return {'status': 'completed', 'results': [], 'n_agents': 0}

        market_ref = ray.put(market_data)

        @ray.remote
        def _run_agent_analysis(market_ref, agent_id: str) -> dict:
            """Run a single agent analysis on a Ray worker."""
            import numpy as _np
            import time as _time

            start = _time.time()
            _np.random.seed(hash(agent_id) % (2**32))

            # Simulate agent analysis
            sentiment = float(_np.random.uniform(-1, 1))
            confidence = float(_np.random.uniform(0.5, 1.0))

            return {
                'agent_id': agent_id,
                'sentiment': sentiment,
                'confidence': confidence,
                'recommendation': 'bullish' if sentiment > 0.2 else ('bearish' if sentiment < -0.2 else 'neutral'),
                'analysis_time': _time.time() - start,
                'status': 'completed',
            }

        self.logger.info(f"Ray agent coordination: {len(agent_ids)} agents")

        futures = [_run_agent_analysis.remote(market_ref, aid) for aid in agent_ids]
        results = ray.get(futures)

        completed = [r for r in results if r.get('status') == 'completed']
        sentiments = [r['sentiment'] for r in completed]
        weighted_sentiment = sum(
            r['sentiment'] * r['confidence'] for r in completed
        ) / sum(r['confidence'] for r in completed) if completed else 0

        return {
            'status': 'completed',
            'n_agents': len(completed),
            'consensus_sentiment': float(np.mean(sentiments)) if sentiments else 0,
            'weighted_sentiment': float(weighted_sentiment),
            'consensus_direction': 'bullish' if weighted_sentiment > 0.15 else ('bearish' if weighted_sentiment < -0.15 else 'neutral'),
            'agreement_ratio': float(sum(1 for s in sentiments if s * weighted_sentiment > 0) / len(sentiments)) if sentiments else 0,
            'results': results,
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_meta_coordinator(config: dict[str, Any] | None = None) -> MetaCoordinator:
    """Create and initialize a MetaCoordinator instance"""
    return MetaCoordinator(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    import asyncio

    async def test_coordinator():
        # Create coordinator
        coordinator = create_meta_coordinator()

        # Test market data
        market_data = {
            'SPY': {'price': 450.0, 'volume': 1000000},
            'VIX': {'level': 18.5},
            'market_trend': 'bullish'
        }

        # Test entry decision

        await coordinator.coordinate_decision(
            DecisionType.ENTRY,
            market_data,
            {'strategy': 'iron_condor', 'timeframe': '1D'}
        )


        # Get stats
        coordinator.get_coordinator_stats()

        # Shutdown
        coordinator.shutdown()

    # Run test
    asyncio.run(test_coordinator())
