#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX03_StrategyDirectorAgent.py
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
import json
import asyncio
import logging
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from enum import Enum
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import numpy as np

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    logging.info("Warning: ollama package not installed. Install with: pip install ollama")
    OLLAMA_AVAILABLE = False

# Pydantic v2 — structured output validation (TradingAgents-inspired)
try:
    from pydantic import BaseModel as _PydanticBase, Field as _PField, field_validator as _fv, ValidationError as _PydanticValidationError  # type: ignore[import]
    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Note: In standalone mode, we're not importing from other Spyder modules
# In production, these would be imported from the Spyder ecosystem
try:
    from Spyder.SpyderU_Utilities.SpyderU17_LLMUtils import get_primary_model, strip_thinking_block
except ImportError:
    import os
    def get_primary_model() -> str:  # type: ignore[misc]
        return os.getenv("OLLAMA_PRIMARY_MODEL", "gemma4:26b")
    def strip_thinking_block(content: str) -> str:  # type: ignore[misc]
        import re
        return re.sub(r"<\|channel>thought\n.*?<channel\|>", "", content, flags=re.DOTALL).strip()

# ==============================================================================
# CONSTANTS
# ==============================================================================
# LLM Configuration
DEFAULT_LLM_MODEL = get_primary_model()
DEFAULT_TEMPERATURE = 0.3
MAX_TOKENS = 2000

# Strategy Configuration
MAX_CONCURRENT_STRATEGIES = 5
MIN_CONFIDENCE_THRESHOLD = 0.6
STRATEGY_CACHE_TTL = 300  # 5 minutes

# Bull/Bear Debate (TradingAgents-inspired adversarial research pattern)
DEBATE_ROUNDS = 1        # Rounds of bull-vs-bear debate before final synthesis
DEBATE_MAX_TOKENS = 512  # Tokens per debate response (concise arguments)

# Risk Thresholds
MAX_PORTFOLIO_RISK = 0.02
MAX_POSITION_SIZE = 5000
MIN_WIN_RATE = 0.5

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyType(Enum):
    """Available trading strategies"""
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    SHORT_PUT = "short_put"
    SHORT_CALL = "short_call"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    RATIO_SPREAD = "ratio_spread"
    JADE_LIZARD = "jade_lizard"
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly"
    ZERO_DTE = "zero_dte"
    VOLATILITY_ARBITRAGE = "volatility_arbitrage"
    SYNTHETIC_LONG = "synthetic_long"

class MarketRegime(Enum):
    """Market condition classifications"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION = "transition"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """Market data structure"""
    timestamp: datetime
    underlying_price: float
    volatility: float
    volume: int
    trend_strength: float  # -1 to 1
    vix_level: float
    market_breadth: float  # 0 to 1

@dataclass
class Portfolio:
    """Portfolio state structure"""
    cash: float
    positions: list[dict[str, Any]]
    total_value: float
    current_risk: float
    buying_power: float

@dataclass
class StrategyParameters:
    """Parameters for strategy execution"""
    strategy_type: StrategyType
    strikes: list[float]
    expirations: list[datetime]
    quantities: list[int]
    max_loss: float
    target_profit: float
    entry_conditions: dict[str, Any]
    exit_conditions: dict[str, Any]
    adjustment_rules: dict[str, Any]
    confidence_score: float = 0.0

@dataclass
class MarketContext:
    """Current market analysis context"""
    regime: MarketRegime
    trend_strength: float  # -1 to 1
    volatility_percentile: float  # 0 to 100
    support_levels: list[float]
    resistance_levels: list[float]
    volume_profile: dict[str, float]
    sentiment_score: float  # -1 to 1
    economic_events: list[dict[str, Any]]

@dataclass
class StrategyRecommendation:
    """AI-generated strategy recommendation"""
    timestamp: datetime
    strategy_params: StrategyParameters
    market_context: MarketContext
    reasoning: str
    expected_return: float
    risk_metrics: dict[str, float]
    ai_insights: dict[str, Any]
    alternative_strategies: list[StrategyParameters]

@dataclass
class DebateRound:
    """One round of adversarial bull/bear researcher debate."""
    round_num: int
    bull_case: str   # Bull researcher argument
    bear_case: str   # Bear researcher argument


# ------------------------------------------------------------------------------
# Pydantic structured output model (TradingAgents-inspired validated response)
# ------------------------------------------------------------------------------
if _PYDANTIC_AVAILABLE:
    class StrategyAIResponse(_PydanticBase):  # type: ignore[misc]
        """Pydantic model that validates and coerces the LLM's JSON output.

        All fields mirror what ``_create_strategy_parameters`` expects so that
        callers receive a type-safe, default-filled dict via ``.model_dump()``.
        """

        strategy_type: str = _PField(default="iron_condor")
        reasoning: str = _PField(default="")
        strikes: list[float] = _PField(default_factory=list)
        expiration_days: int = _PField(default=45, ge=1, le=180)
        position_size: int = _PField(default=1, ge=1, le=100)
        confidence: float = _PField(default=0.5, ge=0.0, le=1.0)
        expected_return: float = _PField(default=0.5)
        risk_metrics: dict = _PField(default_factory=dict)
        entry_conditions: dict = _PField(default_factory=dict)
        exit_conditions: dict = _PField(default_factory=lambda: {"target": 0.5, "stop": -0.5})
        adjustment_rules: dict = _PField(default_factory=dict)

        @_fv("confidence", mode="before")
        @classmethod
        def clamp_confidence(cls, v: float) -> float:  # type: ignore[misc]
            # Run before field constraints so out-of-range values are clamped
            # rather than rejected (Pydantic v2 validators default to mode='after').
            return max(0.0, min(1.0, float(v)))
else:
    StrategyAIResponse = None  # type: ignore[assignment,misc]

_STRATEGY_RESPONSE_DEFAULTS: dict[str, Any] = {
    "strategy_type": "iron_condor",
    "reasoning": "Fallback strategy due to parsing error",
    "strikes": [],
    "expiration_days": 45,
    "position_size": 1,
    "confidence": 0.5,
    "expected_return": 0.5,
    "risk_metrics": {},
    "entry_conditions": {},
    "exit_conditions": {"target": 0.5, "stop": -0.5},
    "adjustment_rules": {},
}


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX03_StrategyDirectorAgent:
    """
    AI-Enhanced Strategy Director Agent.

    This agent intelligently selects and manages trading strategies based on
    market conditions, portfolio state, and risk parameters. It uses Ollama
    for advanced pattern recognition and strategy optimization.

    Attributes:
        logger: Module logger instance
        config: Agent configuration
        ollama_client: Ollama LLM client
        active_strategies: Currently active trading strategies
        strategy_history: Historical strategy performance

    Example:
        >>> agent = SpyderX03_StrategyDirectorAgent()
        >>> recommendation = await agent.select_strategy(market_data, portfolio)
        >>> print(recommendation.strategy_params.strategy_type)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the Strategy Director Agent.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger

        # LLM configuration
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        self.max_concurrent = self.config.get('max_concurrent_strategies', MAX_CONCURRENT_STRATEGIES)  # noqa: E501
        self.min_confidence = self.config.get('min_confidence_threshold', MIN_CONFIDENCE_THRESHOLD)

        # Initialize Ollama client
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                # Test if Ollama is running
                ollama.list()
                self.ollama_client = ollama
                self.logger.info("Ollama initialized with model: %s", self.model_name)
            except Exception as e:
                self.logger.error("Failed to connect to Ollama: %s", e)
                self.logger.info("Agent will work with reduced AI capabilities")

        # Strategy management
        self.active_strategies: dict[str, StrategyParameters] = {}
        self.strategy_performance: dict[StrategyType, list[float]] = defaultdict(list)
        self.strategy_history: list[StrategyRecommendation] = []

        # Market analysis
        self.current_market_context: MarketContext | None = None
        self.market_regime_history: deque = deque(maxlen=100)

        # Caching for performance
        self.strategy_cache: dict[str, tuple[StrategyRecommendation, datetime]] = {}
        self.cache_ttl = timedelta(seconds=STRATEGY_CACHE_TTL)

        self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    async def select_strategy(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        risk_constraints: dict[str, Any] | None = None
    ) -> StrategyRecommendation | None:
        """
        Select optimal trading strategy based on current conditions.

        Args:
            market_data: Current market data
            portfolio: Current portfolio state
            risk_constraints: Optional risk constraints

        Returns:
            Strategy recommendation or None if no suitable strategy
        """
        start_time = datetime.now(UTC)

        try:
            # Check cache first
            cache_key = self._generate_cache_key(market_data, portfolio)
            cached_strategy = self._get_cached_strategy(cache_key)
            if cached_strategy:
                return cached_strategy

            # Analyze market context
            market_context = await self._analyze_market_context(market_data)
            self.current_market_context = market_context

            # Check if we can add more strategies
            if not self._can_add_strategy(portfolio, risk_constraints):
                self.logger.info("Cannot add more strategies due to constraints")
                return None

            # Get AI strategy recommendation
            if self.ollama_client:
                strategy_recommendation = await self._get_ai_strategy_recommendation(
                    market_data,
                    portfolio,
                    market_context,
                    risk_constraints
                )
            else:
                strategy_recommendation = self._get_rule_based_strategy(
                    market_data,
                    portfolio,
                    market_context,
                    risk_constraints
                )

            if strategy_recommendation and strategy_recommendation.strategy_params.confidence_score >= self.min_confidence:  # noqa: E501
                # Cache the recommendation
                self._cache_strategy(cache_key, strategy_recommendation)

                # Store in history
                self.strategy_history.append(strategy_recommendation)

                # Log performance
                elapsed = (datetime.now(UTC) - start_time).total_seconds()
                self.logger.info(
                    f"Strategy selected: {strategy_recommendation.strategy_params.strategy_type.value} "  # noqa: E501
                    f"with confidence {strategy_recommendation.strategy_params.confidence_score:.2%} "  # noqa: E501
                    f"in {elapsed:.2f} seconds"
                )

                return strategy_recommendation

            return None

        except Exception as e:
            self.logger.error("Error in strategy selection: %s", str(e))
            return None

    async def manage_active_strategies(
        self,
        market_data: MarketData,
        portfolio: Portfolio
    ) -> list[dict[str, Any]]:
        """
        Manage currently active strategies and recommend adjustments.

        Args:
            market_data: Current market data
            portfolio: Current portfolio state

        Returns:
            List of recommended actions for active strategies
        """
        actions = []

        for strategy_id, strategy_params in self.active_strategies.items():
            # Check exit conditions
            should_exit = await self._check_exit_conditions(
                strategy_params,
                market_data,
                portfolio
            )

            if should_exit:
                actions.append({
                    'strategy_id': strategy_id,
                    'action': 'exit',
                    'reason': should_exit
                })
            else:
                # Check for adjustments
                adjustment = await self._check_adjustments(
                    strategy_params,
                    market_data,
                    portfolio
                )

                if adjustment:
                    actions.append({
                        'strategy_id': strategy_id,
                        'action': 'adjust',
                        'adjustment': adjustment
                    })

        return actions

    def get_strategy_performance(
        self,
        strategy_type: StrategyType | None = None
    ) -> dict[str, Any]:
        """
        Get performance metrics for strategies.

        Args:
            strategy_type: Optional specific strategy type

        Returns:
            Performance metrics dictionary
        """
        if strategy_type:
            returns = self.strategy_performance.get(strategy_type, [])
            if not returns:
                return {"message": f"No performance data for {strategy_type.value}"}

            return {
                'strategy_type': strategy_type.value,
                'total_trades': len(returns),
                'average_return': np.mean(returns),
                'win_rate': sum(1 for r in returns if r > 0) / len(returns),
                'sharpe_ratio': self._calculate_sharpe_ratio(returns)
            }

        # Return overall performance
        all_returns = []
        for returns in self.strategy_performance.values():
            all_returns.extend(returns)

        if not all_returns:
            return {"message": "No performance data available"}

        return {
            'total_strategies': len(self.strategy_performance),
            'total_trades': len(all_returns),
            'average_return': np.mean(all_returns),
            'win_rate': sum(1 for r in all_returns if r > 0) / len(all_returns),
            'best_strategy': self._get_best_strategy()
        }

    # ==========================================================================
    # PRIVATE METHODS - MARKET ANALYSIS
    # ==========================================================================
    async def _analyze_market_context(self, market_data: MarketData) -> MarketContext:
        """
        Analyze current market conditions.

        Args:
            market_data: Current market data

        Returns:
            Market context analysis
        """
        # Determine market regime
        regime = self._determine_market_regime(market_data)

        # Calculate support/resistance (simplified)
        support_levels = [market_data.underlying_price * 0.98, market_data.underlying_price * 0.95]
        resistance_levels = [market_data.underlying_price * 1.02, market_data.underlying_price * 1.05]  # noqa: E501

        # Volume profile (simplified)
        volume_profile = {
            'current': market_data.volume,
            'average': 1000000,  # Placeholder
            'relative': market_data.volume / 1000000
        }

        # Create context
        context = MarketContext(
            regime=regime,
            trend_strength=market_data.trend_strength,
            volatility_percentile=self._calculate_volatility_percentile(market_data.volatility),
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            volume_profile=volume_profile,
            sentiment_score=0.0,  # Placeholder
            economic_events=[]  # Placeholder
        )

        # Store in history
        self.market_regime_history.append(regime)

        return context

    def _determine_market_regime(self, market_data: MarketData) -> MarketRegime:
        """Determine current market regime."""
        # Simplified regime detection
        if market_data.volatility > 25:
            return MarketRegime.HIGH_VOLATILITY
        elif market_data.volatility < 12:
            return MarketRegime.LOW_VOLATILITY
        elif market_data.trend_strength > 0.5:
            return MarketRegime.TRENDING_UP
        elif market_data.trend_strength < -0.5:
            return MarketRegime.TRENDING_DOWN
        else:
            return MarketRegime.RANGE_BOUND

    def _calculate_volatility_percentile(self, current_vol: float) -> float:
        """Calculate volatility percentile."""
        # Simplified calculation
        # In production, this would use historical volatility data
        if current_vol < 10:
            return 10.0
        elif current_vol < 15:
            return 30.0
        elif current_vol < 20:
            return 50.0
        elif current_vol < 30:
            return 70.0
        else:
            return 90.0

    # ==========================================================================
    # PRIVATE METHODS - AI INTEGRATION
    # ==========================================================================
    async def _get_ai_strategy_recommendation(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        market_context: MarketContext,
        risk_constraints: dict[str, Any] | None = None
    ) -> StrategyRecommendation | None:
        """
        Get AI-powered strategy recommendation using Ollama.

        Args:
            market_data: Current market data
            portfolio: Portfolio state
            market_context: Market analysis context
            risk_constraints: Risk constraints

        Returns:
            Strategy recommendation or None
        """
        try:
            # Run adversarial bull/bear debate before final synthesis
            debate_rounds = await self._run_bull_bear_debate(
                market_data, market_context, risk_constraints
            )

            # Build prompt
            prompt = self._build_strategy_prompt(
                market_data,
                portfolio,
                market_context,
                risk_constraints
            )

            # Enrich the synthesis prompt with debate findings
            if debate_rounds:
                last = debate_rounds[-1]
                prompt += (
                    "\n\n## Analyst Debate\n"
                    f"**Bull Researcher**: {last.bull_case}\n\n"
                    f"**Bear Researcher**: {last.bear_case}\n\n"
                    "Weigh both arguments above in your final JSON recommendation."
                )

            # Query Ollama — use chat() for consistent system-role support
            response = await asyncio.to_thread(
                self.ollama_client.chat,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert options trading strategist for SPY. "
                            "Select the optimal strategy based on market conditions and risk constraints. "  # noqa: E501
                            "Respond in JSON."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS,
                    'think': False
                }
            )

            raw = response['message']['content']
            # Parse AI response
            ai_recommendation = self._parse_ai_strategy_response(strip_thinking_block(raw))

            # Create strategy parameters
            strategy_params = self._create_strategy_parameters(
                ai_recommendation,
                market_data,
                portfolio
            )

            # Create recommendation
            recommendation = StrategyRecommendation(
                timestamp=datetime.now(UTC),
                strategy_params=strategy_params,
                market_context=market_context,
                reasoning=ai_recommendation.get('reasoning', ''),
                expected_return=ai_recommendation.get('expected_return', 0.0),
                risk_metrics=ai_recommendation.get('risk_metrics', {}),
                ai_insights=ai_recommendation,
                alternative_strategies=[]
            )

            return recommendation

        except Exception as e:
            self.logger.error("Error getting AI strategy recommendation: %s", e)
            return None

    async def _run_bull_bear_debate(
        self,
        market_data: MarketData,
        market_context: MarketContext,
        risk_constraints: dict[str, Any] | None = None,
    ) -> list[DebateRound]:
        """Run N rounds of adversarial bull/bear debate before final synthesis.

        Inspired by TradingAgents' Researcher Team pattern: a Bull Researcher
        argues for upside/income strategies and a Bear Researcher argues for
        protective/downside strategies. Both views are injected into the final
        synthesis prompt so the Strategist LLM must weigh them.

        Args:
            market_data: Current market snapshot.
            market_context: Derived regime and volatility context.
            risk_constraints: Optional risk constraints.

        Returns:
            List of DebateRound records, one per round.
        """
        if not self.ollama_client:
            return []

        rounds: list[DebateRound] = []
        prior_bull: str = ""
        prior_bear: str = ""

        for n in range(DEBATE_ROUNDS):
            bull_case = await self._run_debate_side(
                "bull", market_data, market_context, risk_constraints, prior_bear
            )
            bear_case = await self._run_debate_side(
                "bear", market_data, market_context, risk_constraints, prior_bull
            )
            rounds.append(DebateRound(round_num=n + 1, bull_case=bull_case, bear_case=bear_case))
            prior_bull = bull_case
            prior_bear = bear_case

        return rounds

    async def _run_debate_side(
        self,
        stance: str,
        market_data: MarketData,
        market_context: MarketContext,
        risk_constraints: dict[str, Any] | None,
        opposing_view: str,
    ) -> str:
        """Run one side of the bull/bear debate.

        Args:
            stance: ``"bull"`` or ``"bear"``.
            market_data: Current market snapshot.
            market_context: Derived regime context.
            risk_constraints: Optional risk constraints.
            opposing_view: Prior-round opposing argument (empty string on round 1).

        Returns:
            The researcher's argument as a string; empty string on failure.
        """
        if stance == "bull":
            system_msg = (
                "You are a Bull Researcher for SPY options. Argue FOR bullish or "
                "income-generating strategies (e.g. Short Put, Iron Condor, Bull "
                "Call Spread). Highlight why upside or range-bound plays make sense "
                "right now. Be concise and specific — 3 to 4 sentences."
            )
            user_prefix = "Argue for a BULLISH or NEUTRAL-INCOME options strategy"
        else:
            system_msg = (
                "You are a Bear Researcher for SPY options. Argue FOR bearish or "
                "protective strategies (e.g. Bear Put Spread, Long Put, protective "
                "collar). Highlight tail risks, downside scenarios, and why hedging "
                "makes sense right now. Be concise and specific — 3 to 4 sentences."
            )
            user_prefix = "Argue for a BEARISH or PROTECTIVE options strategy"

        content = (
            f"{user_prefix} given:\n"
            f"- SPY: ${market_data.underlying_price:.2f}\n"
            f"- IV: {market_data.volatility:.1f}%  VIX: {market_data.vix_level:.1f}\n"
            f"- Trend: {market_data.trend_strength:+.2f}  "
            f"Regime: {market_context.regime.value}\n"
        )
        if opposing_view:
            content += f"\nOpposing view to rebut:\n{opposing_view}\n"
        if risk_constraints:
            content += f"\nRisk constraints: {risk_constraints}\n"

        try:
            response = await asyncio.to_thread(
                self.ollama_client.chat,
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": content},
                ],
                options={
                    "temperature": self.temperature,
                    "num_predict": DEBATE_MAX_TOKENS,
                    "think": False,
                },
            )
            return strip_thinking_block(response["message"]["content"])
        except Exception as exc:
            self.logger.warning("Debate side '%s' failed: %s", stance, exc)
            return ""

    def _build_strategy_prompt(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        market_context: MarketContext,
        risk_constraints: dict[str, Any] | None = None
    ) -> str:
        """Build prompt for Ollama strategy selection."""
        constraints_str = ""
        if risk_constraints:
            constraints_str = "\nRisk Constraints:\n"
            for key, value in risk_constraints.items():
                constraints_str += f"- {key}: {value}\n"

        # Get recent performance
        recent_performance = self.get_strategy_performance()
        perf_str = f"Win Rate: {recent_performance.get('win_rate', 0):.1%}" if recent_performance.get('total_trades', 0) > 0 else "No history"  # noqa: E501

        prompt = f"""You are an expert options trading strategist. Select the optimal options strategy based on current market conditions.

Market Data:
- SPY Price: ${market_data.underlying_price:.2f}
- Implied Volatility: {market_data.volatility:.1f}%
- VIX Level: {market_data.vix_level:.1f}
- Trend Strength: {market_data.trend_strength:.2f} (-1 bearish to +1 bullish)
- Market Regime: {market_context.regime.value}
- Volatility Percentile: {market_context.volatility_percentile:.0f}%

Portfolio:
- Available Cash: ${portfolio.cash:,.2f}
- Current Risk: {portfolio.current_risk:.1%}
- Buying Power: ${portfolio.buying_power:,.2f}
- Active Positions: {len(portfolio.positions)}
{constraints_str}

Recent Performance: {perf_str}

Available Strategies:
1. Bull Call Spread - Bullish, limited risk
2. Bear Put Spread - Bearish, limited risk
3. Iron Condor - Range-bound, high probability
4. Iron Butterfly - Range-bound, higher profit potential
5. Calendar Spread - Volatility play
6. Straddle/Strangle - Volatility expansion
7. Short Put - Bullish income
8. Zero DTE - Day trading

Provide your recommendation as JSON with the following structure:
{{
    "strategy_type": "strategy_name",
    "reasoning": "detailed explanation",
    "strikes": [list of strikes],
    "expiration_days": number,
    "position_size": number of contracts,
    "entry_conditions": {{"condition": "value"}},
    "exit_conditions": {{"target": percent, "stop": percent}},
    "expected_return": percent,
    "confidence": 0-1,
    "risk_metrics": {{"max_loss": amount, "probability_profit": percent}}
}}"""  # noqa: E501

        return prompt

    def _parse_ai_strategy_response(self, response: str) -> dict[str, Any]:
        """Parse Ollama response for strategy recommendation.

        Uses Pydantic v2 (TradingAgents-inspired structured output pattern) to
        validate and coerce the LLM JSON. Falls back to raw dict or hardcoded
        defaults on parse or validation failure.
        """
        data: dict[str, Any] | None = None

        # Step 1: extract the first JSON object from the response
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                data = json.loads(response[start:end])
        except Exception as exc:
            self.logger.error("Failed to parse AI response JSON: %s", exc)

        if data is None:
            return dict(_STRATEGY_RESPONSE_DEFAULTS)

        # Step 2: validate with Pydantic if available
        if _PYDANTIC_AVAILABLE and StrategyAIResponse is not None:
            try:
                return StrategyAIResponse.model_validate(data).model_dump()
            except _PydanticValidationError as exc:
                self.logger.warning(
                    "Pydantic validation failed, falling back to raw dict: %s", exc
                )

        # Step 3: return raw dict (may have unvalidated/unexpected types)
        return data

    def _create_strategy_parameters(
        self,
        ai_recommendation: dict[str, Any],
        market_data: MarketData,
        portfolio: Portfolio
    ) -> StrategyParameters:
        """Create strategy parameters from AI recommendation."""
        # Map strategy name to enum
        strategy_type_str = ai_recommendation.get('strategy_type', 'iron_condor').lower().replace(' ', '_')  # noqa: E501
        strategy_type = StrategyType.IRON_CONDOR  # Default

        for st in StrategyType:
            if st.value == strategy_type_str:
                strategy_type = st
                break

        # Calculate expiration
        days = ai_recommendation.get('expiration_days', 45)
        expiration = datetime.now(UTC) + timedelta(days=days)

        # Get strikes or calculate them
        strikes = ai_recommendation.get('strikes', [])
        if not strikes:
            strikes = self._calculate_default_strikes(strategy_type, market_data.underlying_price)

        # Create parameters
        return StrategyParameters(
            strategy_type=strategy_type,
            strikes=strikes,
            expirations=[expiration],
            quantities=[ai_recommendation.get('position_size', 1)],
            max_loss=ai_recommendation.get('risk_metrics', {}).get('max_loss', 1000),
            target_profit=ai_recommendation.get('expected_return', 0.5) * 1000,
            entry_conditions=ai_recommendation.get('entry_conditions', {}),
            exit_conditions=ai_recommendation.get('exit_conditions', {'target': 0.5, 'stop': -0.5}),
            adjustment_rules=ai_recommendation.get('adjustment_rules', {}),
            confidence_score=ai_recommendation.get('confidence', 0.7)
        )

    # ==========================================================================
    # PRIVATE METHODS - RULE-BASED FALLBACK
    # ==========================================================================
    def _get_rule_based_strategy(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        market_context: MarketContext,
        risk_constraints: dict[str, Any] | None = None
    ) -> StrategyRecommendation | None:
        """
        Get rule-based strategy recommendation (fallback when AI unavailable).

        Args:
            market_data: Current market data
            portfolio: Portfolio state
            market_context: Market analysis
            risk_constraints: Risk constraints

        Returns:
            Strategy recommendation or None
        """
        # Simple rule-based logic
        strategy_type = None
        reasoning = ""

        if market_context.regime == MarketRegime.HIGH_VOLATILITY:
            if market_data.volatility > 30:
                strategy_type = StrategyType.IRON_CONDOR
                reasoning = "High volatility favors premium selling strategies"
            else:
                strategy_type = StrategyType.STRADDLE
                reasoning = "Elevated volatility with potential for expansion"

        elif market_context.regime == MarketRegime.TRENDING_UP:
            strategy_type = StrategyType.BULL_CALL_SPREAD
            reasoning = "Uptrend favors bullish strategies with defined risk"

        elif market_context.regime == MarketRegime.TRENDING_DOWN:
            strategy_type = StrategyType.BEAR_PUT_SPREAD
            reasoning = "Downtrend favors bearish strategies with defined risk"

        else:  # RANGE_BOUND
            strategy_type = StrategyType.IRON_BUTTERFLY
            reasoning = "Range-bound market favors neutral strategies"

        if not strategy_type:
            return None

        # Create basic parameters
        strikes = self._calculate_default_strikes(strategy_type, market_data.underlying_price)

        strategy_params = StrategyParameters(
            strategy_type=strategy_type,
            strikes=strikes,
            expirations=[datetime.now(UTC) + timedelta(days=45)],
            quantities=[1],
            max_loss=1000,
            target_profit=500,
            entry_conditions={'volatility': market_data.volatility},
            exit_conditions={'target': 0.5, 'stop': -0.5},
            adjustment_rules={},
            confidence_score=0.6
        )

        return StrategyRecommendation(
            timestamp=datetime.now(UTC),
            strategy_params=strategy_params,
            market_context=market_context,
            reasoning=reasoning,
            expected_return=0.15,
            risk_metrics={'max_loss': 1000, 'probability_profit': 0.65},
            ai_insights={},
            alternative_strategies=[]
        )

    def _calculate_default_strikes(
        self,
        strategy_type: StrategyType,
        underlying_price: float
    ) -> list[float]:
        """Calculate default strikes for a strategy."""
        strikes = []

        if strategy_type == StrategyType.IRON_CONDOR:
            # Example: 5% OTM for shorts, 10% OTM for longs
            strikes = [
                round(underlying_price * 0.90),  # Long put
                round(underlying_price * 0.95),  # Short put
                round(underlying_price * 1.05),  # Short call
                round(underlying_price * 1.10)   # Long call
            ]
        elif strategy_type == StrategyType.BULL_CALL_SPREAD:
            strikes = [
                round(underlying_price),         # Long call ATM
                round(underlying_price * 1.03)   # Short call 3% OTM
            ]
        elif strategy_type == StrategyType.BEAR_PUT_SPREAD:
            strikes = [
                round(underlying_price * 0.97),  # Short put 3% OTM
                round(underlying_price)          # Long put ATM
            ]
        elif strategy_type == StrategyType.STRADDLE:
            strikes = [round(underlying_price)]  # ATM
        else:
            # Default: ATM strike
            strikes = [round(underlying_price)]

        return strikes

    # ==========================================================================
    # PRIVATE METHODS - STRATEGY MANAGEMENT
    # ==========================================================================
    def _can_add_strategy(
        self,
        portfolio: Portfolio,
        risk_constraints: dict[str, Any] | None = None
    ) -> bool:
        """Check if we can add another strategy."""
        # Check concurrent strategy limit
        if len(self.active_strategies) >= self.max_concurrent:
            return False

        # Check portfolio constraints
        if risk_constraints:
            max_risk = risk_constraints.get('max_portfolio_risk', MAX_PORTFOLIO_RISK)
            if portfolio.current_risk >= max_risk:
                return False

            min_cash = risk_constraints.get('min_cash_reserve', 1000)
            if portfolio.cash < min_cash:
                return False

        return True

    async def _check_exit_conditions(
        self,
        strategy: StrategyParameters,
        market_data: MarketData,
        portfolio: Portfolio
    ) -> str | None:
        """Check if strategy should be exited."""
        # This would check actual P&L in production
        # For now, return None (no exit)
        return None

    async def _check_adjustments(
        self,
        strategy: StrategyParameters,
        market_data: MarketData,
        portfolio: Portfolio
    ) -> dict[str, Any] | None:
        """Check if strategy needs adjustment."""
        # This would check for rolling, delta adjustment, etc.
        # For now, return None (no adjustment)
        return None

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _generate_cache_key(
        self,
        market_data: MarketData,
        portfolio: Portfolio
    ) -> str:
        """Generate cache key for strategy recommendation."""
        key_parts = [
            f"{market_data.underlying_price:.0f}",
            f"{market_data.volatility:.0f}",
            f"{portfolio.cash:.0f}",
            f"{len(portfolio.positions)}"
        ]

        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    def _get_cached_strategy(self, cache_key: str) -> StrategyRecommendation | None:
        """Get cached strategy if still valid."""
        if cache_key in self.strategy_cache:
            recommendation, timestamp = self.strategy_cache[cache_key]
            if datetime.now(UTC) - timestamp < self.cache_ttl:
                self.logger.info("Using cached strategy recommendation")
                return recommendation

        return None

    def _cache_strategy(self, cache_key: str, recommendation: StrategyRecommendation):
        """Cache strategy recommendation."""
        self.strategy_cache[cache_key] = (recommendation, datetime.now(UTC))

    def _calculate_sharpe_ratio(self, returns: list[float]) -> float:
        """Calculate Sharpe ratio from returns."""
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        if returns_array.std() == 0:
            return 0.0

        # Assuming daily returns and 252 trading days
        return (returns_array.mean() / returns_array.std()) * np.sqrt(252)

    def _get_best_strategy(self) -> str | None:
        """Get best performing strategy type."""
        best_sharpe = -np.inf
        best_strategy = None

        for strategy_type, returns in self.strategy_performance.items():
            if len(returns) >= 10:  # Minimum trades for evaluation
                sharpe = self._calculate_sharpe_ratio(returns)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_strategy = strategy_type.value

        return best_strategy

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def clear_cache(self):
        """Clear strategy cache."""
        self.strategy_cache.clear()
        self.logger.info("Strategy cache cleared")

    def reset_performance(self):
        """Reset performance tracking."""
        self.strategy_performance.clear()
        self.strategy_history.clear()
        self.logger.info("Performance history reset")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_strategy_director_agent(config: dict[str, Any] | None = None) -> SpyderX03_StrategyDirectorAgent:  # noqa: E501
    """
    Factory function to create Strategy Director Agent.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured SpyderX03_StrategyDirectorAgent instance
    """
    return SpyderX03_StrategyDirectorAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: SpyderX03_StrategyDirectorAgent | None = None

def get_module_instance(config: dict[str, Any] | None = None) -> SpyderX03_StrategyDirectorAgent:
    """
    Get singleton instance of the module.

    Args:
        config: Configuration if creating new instance

    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX03_StrategyDirectorAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    async def test_agent():
        """Test the Strategy Director Agent."""
        # Create agent
        config = {
            'llm_model': 'llama3.2:3b-instruct-q4_K_M',
            'temperature': 0.3,
            'max_concurrent_strategies': 5,
            'min_confidence_threshold': 0.6
        }

        agent = create_strategy_director_agent(config)

        # Create sample market data
        market_data = MarketData(
            timestamp=datetime.now(UTC),
            underlying_price=550.00,
            volatility=18.5,
            volume=85000000,
            trend_strength=0.3,
            vix_level=16.2,
            market_breadth=0.6
        )

        # Create sample portfolio
        portfolio = Portfolio(
            cash=25000.0,
            positions=[],
            total_value=25000.0,
            current_risk=0.0,
            buying_power=25000.0
        )

        # Risk constraints
        risk_constraints = {
            'max_position_size': 5000,
            'max_portfolio_risk': 0.02,
            'min_win_rate': 0.5,
            'min_cash_reserve': 5000
        }

        # Test strategy selection

        recommendation = await agent.select_strategy(
            market_data,
            portfolio,
            risk_constraints
        )

        if recommendation:

            if recommendation.risk_metrics:
                for _key, _value in recommendation.risk_metrics.items():
                    pass

            if recommendation.ai_insights:
                pass
        else:
            pass

        # Show performance
        perf = agent.get_strategy_performance()
        for _key, _value in perf.items():
            pass

    # Run test
    asyncio.run(test_agent())
