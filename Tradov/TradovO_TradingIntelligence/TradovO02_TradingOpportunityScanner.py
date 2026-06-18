#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovO_TradingIntelligence
Module: TradovO02_TradingOpportunityScanner.py
Purpose: Multi-strategy trading opportunity scanner and ranking engine
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 17:00:00

Module Description:
    Advanced trading opportunity scanner that synthesizes data from existing analytics
    modules (TradovN, TradovF, TradovS) to identify, rank, and recommend optimal trading
    opportunities across multiple strategies. Acts as a meta-decision engine that
    coordinates regime detection, options analytics, volatility analysis, and strategy
    optimization to provide actionable trading recommendations with confidence scoring
    and risk assessment.

Key Features:
    • Cross-strategy opportunity ranking and comparison
    • Real-time market regime integration for context-aware recommendations
    • Options-specific opportunity identification (skew, gamma, theta opportunities)
    • Multi-timeframe opportunity analysis (intraday, weekly, monthly)
    • Risk-adjusted opportunity scoring with position sizing recommendations
    • Strategy arbitrage detection across different approaches to same market view
    • Integration with existing Spyder analytics ecosystem
    • Actionable trade recommendations with entry/exit criteria
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import uuid

# alphalens-reloaded: factor Information Coefficient (IC) for signal quality
try:
    import alphalens  # noqa: F401
    from alphalens import performance as al_perf  # noqa: F401
    _ALPHALENS_AVAILABLE = True
except ImportError:
    _ALPHALENS_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
# TradovU07_Constants not used directly in this module

try:
    from Tradov.TradovF_Analysis.TradovF06_GreeksCalculator import GreeksCalculator  # noqa: F401
    from Tradov.TradovF_Analysis.TradovF11_GreeksAggregator import GreeksAggregator  # noqa: F401
    from Tradov.TradovF_Analysis.TradovF04_VolatilityAnalysis import VolatilityAnalyzer  # noqa: F401
    from Tradov.TradovF_Analysis.TradovF08_VolatilityRegime import VolatilityRegimeDetector  # noqa: F401
    ANALYSIS_MODULES_AVAILABLE = True
except ImportError:
    ANALYSIS_MODULES_AVAILABLE = False

try:
    from Tradov.TradovS_Signals.TradovS05_GEXDEXCalculator import GEXDEXCalculator
    from Tradov.TradovS_Signals.TradovS06_SKEWCalculator import SKEWCalculator
    SIGNALS_AVAILABLE = True
except ImportError:
    SIGNALS_AVAILABLE = False

try:
    from Tradov.TradovL_ML.TradovL09_UnifiedRegimeEngine import get_unified_regime_engine
    REGIME_ENGINE_AVAILABLE = True
except ImportError:
    REGIME_ENGINE_AVAILABLE = False

try:
    from Tradov.TradovE_Risk.TradovE19_UnifiedRiskCoordinator import get_unified_risk_coordinator
    RISK_COORDINATOR_AVAILABLE = True
except ImportError:
    RISK_COORDINATOR_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Opportunity scoring weights
OPPORTUNITY_WEIGHTS = {
    'edge_strength': 0.25,           # How strong is the statistical edge
    'risk_reward_ratio': 0.20,       # Risk/reward attractiveness
    'probability_of_profit': 0.15,   # Likelihood of success
    'liquidity_score': 0.15,         # How tradeable is the opportunity
    'regime_alignment': 0.10,        # Alignment with market regime
    'volatility_advantage': 0.10,    # Volatility mispricing edge
    'time_decay_advantage': 0.05     # Theta capture opportunity
}

# Confidence thresholds
MIN_OPPORTUNITY_CONFIDENCE = 0.60
HIGH_CONFIDENCE_THRESHOLD = 0.80
VERY_HIGH_CONFIDENCE_THRESHOLD = 0.90

# Risk limits
MAX_SINGLE_OPPORTUNITY_RISK = 0.05    # 5% of portfolio
MAX_STRATEGY_ALLOCATION = 0.30        # 30% to any single strategy type
MAX_CORRELATION_EXPOSURE = 0.50       # 50% in correlated positions

# Market condition filters
MIN_VOLATILITY_RANK = 10              # Minimum IV rank for vol selling
MAX_VOLATILITY_RANK = 90              # Maximum IV rank for vol buying
MIN_VOLUME_THRESHOLD = 1000           # Minimum daily volume
MIN_OPEN_INTEREST = 100               # Minimum open interest

# Timing parameters
MAX_DTE_FOR_THETA_PLAYS = 45          # Maximum DTE for theta strategies
MIN_DTE_FOR_DELTA_PLAYS = 7           # Minimum DTE for directional plays
EARNINGS_BUFFER_DAYS = 7              # Days to avoid before earnings

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class OpportunityType(Enum):
    """Types of trading opportunities"""
    CREDIT_SPREAD = "credit_spread"
    IRON_CONDOR = "iron_condor"
    LONG_STRADDLE = "long_straddle"
    SHORT_STRADDLE = "short_straddle"
    BREAKOUT_PLAY = "breakout_play"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY_ARBITRAGE = "volatility_arbitrage"
    GAMMA_SCALPING = "gamma_scalping"
    THETA_HARVESTING = "theta_harvesting"
    SKEW_ARBITRAGE = "skew_arbitrage"

class OpportunityPriority(Enum):
    """Opportunity priority levels"""
    CRITICAL = "critical"        # Must execute immediately
    HIGH = "high"               # Execute within 1 hour
    MEDIUM = "medium"           # Execute within 4 hours
    LOW = "low"                 # Execute within 24 hours
    MONITOR = "monitor"         # Track but don't execute yet

class MarketBias(Enum):
    """Market bias for opportunity filtering"""
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"

class VolatilityEnvironment(Enum):
    """Volatility environment classification"""
    VERY_LOW_VOL = "very_low_vol"
    LOW_VOL = "low_vol"
    MODERATE_VOL = "moderate_vol"
    HIGH_VOL = "high_vol"
    VERY_HIGH_VOL = "very_high_vol"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TradingOpportunity:
    """Complete trading opportunity with all metadata"""
    opportunity_id: str
    opportunity_type: OpportunityType
    priority: OpportunityPriority
    timestamp: datetime

    # Core metrics
    confidence_score: float
    risk_reward_ratio: float
    probability_of_profit: float
    expected_profit: float
    maximum_loss: float

    # Market context
    current_price: float
    market_bias: MarketBias
    volatility_environment: VolatilityEnvironment
    regime_context: str | None

    # Strategy details
    strategy_name: str
    entry_criteria: dict[str, Any]
    exit_criteria: dict[str, Any]
    position_size_recommendation: int

    # Options-specific data
    strikes: list[float] = field(default_factory=list)
    expiration_date: datetime | None = None
    implied_volatilities: list[float] = field(default_factory=list)
    greeks: dict[str, float] = field(default_factory=dict)

    # Risk metrics
    delta_exposure: float = 0.0
    gamma_risk: float = 0.0
    theta_capture: float = 0.0
    vega_exposure: float = 0.0

    # Liquidity assessment
    liquidity_score: float = 0.0
    estimated_slippage: float = 0.0
    market_impact: float = 0.0

    # Supporting analysis
    supporting_indicators: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    alternative_strategies: list[str] = field(default_factory=list)

    # Execution metadata
    time_sensitivity: int = 0  # Minutes until opportunity expires
    minimum_execution_size: int = 1
    maximum_execution_size: int = 10

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'opportunity_id': self.opportunity_id,
            'type': self.opportunity_type.value,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'confidence': self.confidence_score,
            'risk_reward': self.risk_reward_ratio,
            'pop': self.probability_of_profit,
            'expected_profit': self.expected_profit,
            'max_loss': self.maximum_loss,
            'current_price': self.current_price,
            'market_bias': self.market_bias.value,
            'vol_environment': self.volatility_environment.value,
            'strategy': self.strategy_name,
            'entry_criteria': self.entry_criteria,
            'exit_criteria': self.exit_criteria,
            'position_size': self.position_size_recommendation,
            'strikes': self.strikes,
            'expiration': self.expiration_date.isoformat() if self.expiration_date else None,
            'greeks': self.greeks,
            'liquidity_score': self.liquidity_score,
            'time_sensitivity': self.time_sensitivity,
            'supporting_indicators': self.supporting_indicators,
            'risk_factors': self.risk_factors
        }

@dataclass
class OpportunityContext:
    """Market context for opportunity scanning"""
    timestamp: datetime
    spy_price: float
    vix_level: float

    # Market regime
    primary_regime: str
    regime_confidence: float
    regime_transition_probability: float

    # Volatility environment
    iv_rank: float
    iv_percentile: float
    term_structure_slope: float
    skew_level: float

    # Greeks environment
    total_gamma_exposure: float
    dealer_positioning: str

    # Flow analysis
    put_call_ratio: float
    options_volume_ratio: float
    institutional_flow_bias: str

    # Technical context
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    trend_strength: float = 0.0
    momentum_score: float = 0.0

@dataclass
class StrategyComparison:
    """Comparison between multiple strategies for same market view"""
    market_view: str
    strategies: list[dict[str, Any]]
    recommended_strategy: str
    reasoning: str
    efficiency_score: float

# ==============================================================================
# MAIN OPPORTUNITY SCANNER CLASS
# ==============================================================================
class TradingOpportunityScanner:
    """
    Advanced trading opportunity scanner and ranking engine.

    Synthesizes data from existing Spyder analytics modules to identify,
    rank, and recommend optimal trading opportunities across multiple
    strategies with comprehensive risk assessment and context awareness.
    """

    def __init__(self, config: dict[str, Any] = None):
        """Initialize trading opportunity scanner"""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config or {}

        # Integration with existing modules
        self.regime_engine = None
        self.risk_coordinator = None
        self.analytics_modules = {}

        # Initialize analytics connections
        self._initialize_analytics_connections()

        # Opportunity tracking
        self.active_opportunities: dict[str, TradingOpportunity] = {}
        self.opportunity_history: deque = deque(maxlen=1000)
        self.opportunity_performance: dict[str, dict[str, float]] = defaultdict(dict)

        # Scanner state
        self.last_scan_time: datetime | None = None
        self.scan_frequency_seconds = self.config.get('scan_frequency', 300)  # 5 minutes
        self.is_scanning = False

        # Performance tracking
        self.scanner_metrics = {
            'total_opportunities_identified': 0,
            'high_confidence_opportunities': 0,
            'opportunities_executed': 0,
            'average_confidence_score': 0.0,
            'profitable_recommendations': 0,
            'total_recommendations': 0
        }

        # Threading
        self._lock = threading.RLock()
        self._stop_event = threading.Event()

        self.logger.info("TradingOpportunityScanner initialized successfully")

    def _initialize_analytics_connections(self) -> None:
        """Initialize connections to existing analytics modules"""
        try:
            # Connect to regime engine
            if REGIME_ENGINE_AVAILABLE:
                self.regime_engine = get_unified_regime_engine()
                self.logger.info("Connected to unified regime engine")

            # Connect to risk coordinator
            if RISK_COORDINATOR_AVAILABLE:
                self.risk_coordinator = get_unified_risk_coordinator()
                self.logger.info("Connected to unified risk coordinator")

            # Initialize analytics modules
            if SIGNALS_AVAILABLE:
                self.analytics_modules['gex_calculator'] = GEXDEXCalculator()
                self.analytics_modules['skew_calculator'] = SKEWCalculator()
                self.logger.info("Connected to signals modules")

        except Exception as e:
            self.logger.error("Failed to initialize analytics connections: %s", e)

    # ==========================================================================
    # PUBLIC METHODS - MAIN INTERFACE
    # ==========================================================================

    async def scan_opportunities(self, market_data: pd.DataFrame) -> list[TradingOpportunity]:
        """
        Comprehensive opportunity scan across all strategies.

        Args:
            market_data: Current market data

        Returns:
            List of ranked trading opportunities
        """
        try:
            self.is_scanning = True
            self.last_scan_time = datetime.now(UTC)

            # Get market context
            context = await self._build_opportunity_context(market_data)

            # Scan different opportunity types
            opportunities = []

            # Volatility-based opportunities
            vol_opportunities = await self._scan_volatility_opportunities(context, market_data)
            opportunities.extend(vol_opportunities)

            # Directional opportunities
            directional_opportunities = await self._scan_directional_opportunities(context, market_data)  # noqa: E501
            opportunities.extend(directional_opportunities)

            # Greeks-based opportunities
            greeks_opportunities = await self._scan_greeks_opportunities(context, market_data)
            opportunities.extend(greeks_opportunities)

            # Arbitrage opportunities
            arbitrage_opportunities = await self._scan_arbitrage_opportunities(context, market_data)
            opportunities.extend(arbitrage_opportunities)

            # Filter and rank opportunities
            filtered_opportunities = self._filter_opportunities(opportunities, context)
            ranked_opportunities = self._rank_opportunities(filtered_opportunities, context)

            # Update tracking
            with self._lock:
                for opp in ranked_opportunities:
                    self.active_opportunities[opp.opportunity_id] = opp

                # Update metrics
                self.scanner_metrics['total_opportunities_identified'] += len(ranked_opportunities)
                high_conf_count = sum(1 for opp in ranked_opportunities
                                    if opp.confidence_score >= HIGH_CONFIDENCE_THRESHOLD)
                self.scanner_metrics['high_confidence_opportunities'] += high_conf_count

                if ranked_opportunities:
                    avg_confidence = sum(opp.confidence_score for opp in ranked_opportunities) / len(ranked_opportunities)  # noqa: E501
                    self.scanner_metrics['average_confidence_score'] = avg_confidence

            self.logger.info("Opportunity scan completed: %s opportunities found", len(ranked_opportunities))  # noqa: E501
            return ranked_opportunities

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'scan_opportunities',
                'market_data_shape': market_data.shape if market_data is not None else None
            })
            return []
        finally:
            self.is_scanning = False

    async def get_best_opportunities(self, count: int = 5,
                                   opportunity_types: list[OpportunityType] | None = None,
                                   min_confidence: float = MIN_OPPORTUNITY_CONFIDENCE) -> list[TradingOpportunity]:  # noqa: E501
        """Get top opportunities matching criteria"""
        try:
            with self._lock:
                filtered_opportunities = []

                for opp in self.active_opportunities.values():
                    # Filter by confidence
                    if opp.confidence_score < min_confidence:
                        continue

                    # Filter by type if specified
                    if opportunity_types and opp.opportunity_type not in opportunity_types:
                        continue

                    filtered_opportunities.append(opp)

                # Sort by priority and confidence
                filtered_opportunities.sort(
                    key=lambda x: (x.priority.value, -x.confidence_score, -x.risk_reward_ratio)
                )

                return filtered_opportunities[:count]

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'get_best_opportunities'})
            return []

    async def compare_strategies_for_view(self, market_view: str,
                                        current_price: float) -> StrategyComparison:
        """Compare different strategies for expressing same market view"""
        try:
            strategies = []

            if market_view.lower() in ['bullish', 'moderately_bullish']:
                strategies.extend([
                    self._analyze_bull_call_spread(current_price),
                    self._analyze_bull_put_spread(current_price),
                    self._analyze_long_call_option(current_price),
                    self._analyze_cash_secured_put(current_price)
                ])

            elif market_view.lower() in ['bearish', 'moderately_bearish']:
                strategies.extend([
                    self._analyze_bear_call_spread(current_price),
                    self._analyze_bear_put_spread(current_price),
                    self._analyze_long_put_option(current_price),
                    self._analyze_covered_call(current_price)
                ])

            elif market_view.lower() == 'neutral':
                strategies.extend([
                    self._analyze_iron_condor(current_price),
                    self._analyze_short_straddle(current_price),
                    self._analyze_butterfly_spread(current_price),
                    self._analyze_calendar_spread(current_price)
                ])

            # Find best strategy
            best_strategy = max(strategies, key=lambda x: x.get('efficiency_score', 0))

            return StrategyComparison(
                market_view=market_view,
                strategies=strategies,
                recommended_strategy=best_strategy['name'],
                reasoning=best_strategy.get('reasoning', 'Highest efficiency score'),
                efficiency_score=best_strategy.get('efficiency_score', 0)
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'compare_strategies_for_view'})
            return StrategyComparison(
                market_view=market_view,
                strategies=[],
                recommended_strategy='none',
                reasoning='Analysis failed',
                efficiency_score=0.0
            )

    # ==========================================================================
    # OPPORTUNITY SCANNING METHODS
    # ==========================================================================

    async def _build_opportunity_context(self, market_data: pd.DataFrame) -> OpportunityContext:
        """Build comprehensive market context for opportunity scanning"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Get regime information
            regime_info = await self._get_regime_context()

            # Get volatility context
            vix_level = market_data.get('vix', pd.Series([20.0])).iloc[-1] if 'vix' in market_data else 20.0  # noqa: E501

            # Estimate IV metrics (would use real data in production)
            iv_rank = self._estimate_iv_rank(market_data)
            iv_percentile = self._estimate_iv_percentile(market_data)

            # Get flow context (placeholder - would use real options flow data)
            flow_context = self._get_flow_context(market_data)

            # Technical analysis
            support_levels, resistance_levels = self._find_key_levels(market_data)
            trend_strength = self._calculate_trend_strength(market_data)

            return OpportunityContext(
                timestamp=datetime.now(UTC),
                spy_price=current_price,
                vix_level=vix_level,
                primary_regime=regime_info.get('regime', 'unknown'),
                regime_confidence=regime_info.get('confidence', 0.5),
                regime_transition_probability=regime_info.get('transition_prob', 0.1),
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                term_structure_slope=0.0,  # Placeholder
                skew_level=self._estimate_skew_level(market_data),
                total_gamma_exposure=0.0,  # Would integrate with GEX calculator
                dealer_positioning='neutral',
                put_call_ratio=flow_context.get('put_call_ratio', 1.0),
                options_volume_ratio=flow_context.get('volume_ratio', 1.0),
                institutional_flow_bias=flow_context.get('flow_bias', 'neutral'),
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                trend_strength=trend_strength,
                momentum_score=self._calculate_momentum_score(market_data)
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_build_opportunity_context'})
            # Return default context
            return OpportunityContext(
                timestamp=datetime.now(UTC),
                spy_price=market_data['close'].iloc[-1],
                vix_level=20.0,
                primary_regime='unknown',
                regime_confidence=0.5,
                regime_transition_probability=0.1,
                iv_rank=50.0,
                iv_percentile=50.0,
                term_structure_slope=0.0,
                skew_level=0.0,
                total_gamma_exposure=0.0,
                dealer_positioning='neutral',
                put_call_ratio=1.0,
                options_volume_ratio=1.0,
                institutional_flow_bias='neutral'
            )

    async def _scan_volatility_opportunities(self, context: OpportunityContext,
                                           market_data: pd.DataFrame) -> list[TradingOpportunity]:
        """Scan for volatility-based trading opportunities"""
        opportunities = []

        try:
            # High IV opportunities (volatility selling)
            if context.iv_rank > 70:
                # Iron Condor opportunity
                if context.trend_strength < 0.3:  # Low trend = range-bound
                    ic_opportunity = self._create_iron_condor_opportunity(context, market_data)
                    if ic_opportunity:
                        opportunities.append(ic_opportunity)

                # Credit spreads
                if context.trend_strength > 0.4:  # Trending market
                    credit_opportunity = self._create_credit_spread_opportunity(context, market_data)  # noqa: E501
                    if credit_opportunity:
                        opportunities.append(credit_opportunity)

            # Low IV opportunities (volatility buying)
            elif context.iv_rank < 30:
                # Long straddle before volatility expansion
                if context.regime_transition_probability > 0.3:
                    straddle_opportunity = self._create_long_straddle_opportunity(context, market_data)  # noqa: E501
                    if straddle_opportunity:
                        opportunities.append(straddle_opportunity)

            # Volatility arbitrage opportunities
            if abs(context.iv_rank - context.iv_percentile) > 20:
                arb_opportunity = self._create_volatility_arbitrage_opportunity(context, market_data)  # noqa: E501
                if arb_opportunity:
                    opportunities.append(arb_opportunity)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_scan_volatility_opportunities'})

        return opportunities

    async def _scan_directional_opportunities(self, context: OpportunityContext,
                                            market_data: pd.DataFrame) -> list[TradingOpportunity]:
        """Scan for directional trading opportunities"""
        opportunities = []

        try:
            # Strong trend continuation
            if abs(context.trend_strength) > 0.7:
                breakout_opportunity = self._create_breakout_opportunity(context, market_data)
                if breakout_opportunity:
                    opportunities.append(breakout_opportunity)

            # Mean reversion near support/resistance
            current_price = context.spy_price

            # Near support levels
            for support in context.support_levels:
                if abs(current_price - support) / current_price < 0.01:  # Within 1%
                    mr_opportunity = self._create_mean_reversion_opportunity(
                        context, market_data, 'bullish', support
                    )
                    if mr_opportunity:
                        opportunities.append(mr_opportunity)

            # Near resistance levels
            for resistance in context.resistance_levels:
                if abs(current_price - resistance) / current_price < 0.01:  # Within 1%
                    mr_opportunity = self._create_mean_reversion_opportunity(
                        context, market_data, 'bearish', resistance
                    )
                    if mr_opportunity:
                        opportunities.append(mr_opportunity)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_scan_directional_opportunities'})

        return opportunities

    async def _scan_greeks_opportunities(self, context: OpportunityContext,
                                       market_data: pd.DataFrame) -> list[TradingOpportunity]:
        """Scan for Greeks-based trading opportunities"""
        opportunities = []

        try:
            # Gamma scalping opportunities
            if context.vix_level > 25 and abs(context.total_gamma_exposure) > 1000000:
                gamma_opportunity = self._create_gamma_scalping_opportunity(context, market_data)
                if gamma_opportunity:
                    opportunities.append(gamma_opportunity)

            # Theta harvesting opportunities
            if context.iv_rank > 50 and context.trend_strength < 0.4:
                theta_opportunity = self._create_theta_harvesting_opportunity(context, market_data)
                if theta_opportunity:
                    opportunities.append(theta_opportunity)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_scan_greeks_opportunities'})

        return opportunities

    async def _scan_arbitrage_opportunities(self, context: OpportunityContext,
                                          market_data: pd.DataFrame) -> list[TradingOpportunity]:
        """Scan for arbitrage opportunities"""
        opportunities = []

        try:
            # Skew arbitrage
            if abs(context.skew_level) > 0.05:  # Significant skew
                skew_opportunity = self._create_skew_arbitrage_opportunity(context, market_data)
                if skew_opportunity:
                    opportunities.append(skew_opportunity)

            # Calendar spread arbitrage
            if context.term_structure_slope > 0.02:  # Steep term structure
                calendar_opportunity = self._create_calendar_spread_opportunity(context, market_data)  # noqa: E501
                if calendar_opportunity:
                    opportunities.append(calendar_opportunity)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_scan_arbitrage_opportunities'})

        return opportunities

    # ==========================================================================
    # OPPORTUNITY CREATION METHODS
    # ==========================================================================

    def _create_iron_condor_opportunity(self, context: OpportunityContext,
                                      market_data: pd.DataFrame) -> TradingOpportunity | None:
        """Create iron condor opportunity"""
        try:
            current_price = context.spy_price

            # Calculate strikes (example logic)
            put_strike_short = current_price - 10
            put_strike_long = current_price - 15
            call_strike_short = current_price + 10
            call_strike_long = current_price + 15

            # Estimate metrics (would use real options pricing)
            estimated_credit = 2.50
            max_loss = 2.50  # Width - Credit
            put_strike_short - estimated_credit
            call_strike_short + estimated_credit

            # Calculate probability of profit (simplified)
            pop = 0.70  # Placeholder

            # Risk/reward
            risk_reward = estimated_credit / max_loss

            # Calculate confidence
            confidence = self._calculate_iron_condor_confidence(context, market_data)

            if confidence < MIN_OPPORTUNITY_CONFIDENCE:
                return None

            return TradingOpportunity(
                opportunity_id=str(uuid.uuid4()),
                opportunity_type=OpportunityType.IRON_CONDOR,
                priority=OpportunityPriority.MEDIUM,
                timestamp=datetime.now(UTC),
                confidence_score=confidence,
                risk_reward_ratio=risk_reward,
                probability_of_profit=pop,
                expected_profit=estimated_credit * pop,
                maximum_loss=max_loss,
                current_price=current_price,
                market_bias=MarketBias.NEUTRAL,
                volatility_environment=VolatilityEnvironment.HIGH_VOL,
                regime_context=context.primary_regime,
                strategy_name='Iron Condor',
                entry_criteria={
                    'iv_rank_min': 60,
                    'trend_strength_max': 0.3,
                    'dte_range': [21, 45]
                },
                exit_criteria={
                    'profit_target': 0.25,
                    'stop_loss': 2.0,
                    'dte_min': 7
                },
                position_size_recommendation=1,
                strikes=[put_strike_long, put_strike_short, call_strike_short, call_strike_long],
                expiration_date=datetime.now(UTC) + timedelta(days=30),
                greeks={'delta': 0.0, 'gamma': -0.05, 'theta': 0.10, 'vega': -0.30},
                liquidity_score=0.8,
                supporting_indicators=['High IV Rank', 'Range-bound market', 'Low trend strength'],
                risk_factors=['Pin risk at strikes', 'Volatility expansion risk']
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_iron_condor_opportunity'})
            return None

    def _create_credit_spread_opportunity(self, context: OpportunityContext,
                                        market_data: pd.DataFrame) -> TradingOpportunity | None:
        """Create credit spread opportunity based on trend direction"""
        try:
            current_price = context.spy_price

            # Determine spread type based on trend
            if context.trend_strength > 0:
                # Bull put spread
                opportunity_type = OpportunityType.CREDIT_SPREAD
                short_strike = current_price - 5
                long_strike = current_price - 10
                market_bias = MarketBias.BULLISH
                strategy_name = 'Bull Put Spread'
            else:
                # Bear call spread
                opportunity_type = OpportunityType.CREDIT_SPREAD
                short_strike = current_price + 5
                long_strike = current_price + 10
                market_bias = MarketBias.BEARISH
                strategy_name = 'Bear Call Spread'

            # Estimate metrics
            estimated_credit = 1.75
            max_loss = 3.25  # Width - Credit
            pop = 0.65
            risk_reward = estimated_credit / max_loss

            # Calculate confidence
            confidence = self._calculate_credit_spread_confidence(context, market_data)

            if confidence < MIN_OPPORTUNITY_CONFIDENCE:
                return None

            return TradingOpportunity(
                opportunity_id=str(uuid.uuid4()),
                opportunity_type=opportunity_type,
                priority=OpportunityPriority.HIGH,
                timestamp=datetime.now(UTC),
                confidence_score=confidence,
                risk_reward_ratio=risk_reward,
                probability_of_profit=pop,
                expected_profit=estimated_credit * pop,
                maximum_loss=max_loss,
                current_price=current_price,
                market_bias=market_bias,
                volatility_environment=VolatilityEnvironment.HIGH_VOL,
                regime_context=context.primary_regime,
                strategy_name=strategy_name,
                entry_criteria={
                    'iv_rank_min': 50,
                    'trend_strength_min': 0.4,
                    'dte_range': [14, 45]
                },
                exit_criteria={
                    'profit_target': 0.25,
                    'stop_loss': 2.0,
                    'trend_reversal': True
                },
                position_size_recommendation=2,
                strikes=[long_strike, short_strike],
                expiration_date=datetime.now(UTC) + timedelta(days=21),
                greeks={'delta': 0.15 if context.trend_strength > 0 else -0.15,
                       'theta': 0.08, 'vega': -0.20},
                liquidity_score=0.9,
                supporting_indicators=['High IV', 'Strong trend', 'Volume confirmation'],
                risk_factors=['Trend reversal risk', 'Volatility expansion']
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_credit_spread_opportunity'})
            return None

    # ==========================================================================
    # OPPORTUNITY FILTERING AND RANKING
    # ==========================================================================

    def _filter_opportunities(self, opportunities: list[TradingOpportunity],
                             context: OpportunityContext) -> list[TradingOpportunity]:
        """Filter opportunities based on risk and market conditions"""
        filtered = []

        try:
            for opp in opportunities:
                # Confidence filter
                if opp.confidence_score < MIN_OPPORTUNITY_CONFIDENCE:
                    continue

                # Risk filter
                if opp.maximum_loss > MAX_SINGLE_OPPORTUNITY_RISK * 100000:  # Assuming $100k portfolio  # noqa: E501
                    continue

                # Market conditions filter
                if not self._is_market_condition_suitable(opp, context):
                    continue

                # Liquidity filter
                if opp.liquidity_score < 0.5:
                    continue

                filtered.append(opp)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_filter_opportunities'})

        return filtered

    def _rank_opportunities(self, opportunities: list[TradingOpportunity],
                           context: OpportunityContext) -> list[TradingOpportunity]:
        """Rank opportunities by composite score"""
        try:
            for opp in opportunities:
                # Calculate composite score
                score = (
                    opp.confidence_score * OPPORTUNITY_WEIGHTS['edge_strength'] +
                    min(opp.risk_reward_ratio / 2, 1.0) * OPPORTUNITY_WEIGHTS['risk_reward_ratio'] +
                    opp.probability_of_profit * OPPORTUNITY_WEIGHTS['probability_of_profit'] +
                    opp.liquidity_score * OPPORTUNITY_WEIGHTS['liquidity_score'] +
                    self._calculate_regime_alignment_score(opp, context) * OPPORTUNITY_WEIGHTS['regime_alignment'] +  # noqa: E501
                    self._calculate_volatility_advantage_score(opp, context) * OPPORTUNITY_WEIGHTS['volatility_advantage'] +  # noqa: E501
                    self._calculate_theta_advantage_score(opp, context) * OPPORTUNITY_WEIGHTS['time_decay_advantage']  # noqa: E501
                )

                # Store score for sorting
                opp.composite_score = score

                # Assign priority based on score
                if score >= 0.85:
                    opp.priority = OpportunityPriority.CRITICAL
                elif score >= 0.75:
                    opp.priority = OpportunityPriority.HIGH
                elif score >= 0.65:
                    opp.priority = OpportunityPriority.MEDIUM
                else:
                    opp.priority = OpportunityPriority.LOW

            # Sort by composite score
            opportunities.sort(key=lambda x: getattr(x, 'composite_score', 0), reverse=True)

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_rank_opportunities'})

        return opportunities

    def compute_factor_ic(
        self,
        factor_scores: pd.Series,
        forward_returns: pd.Series,
        periods: int = 5,
    ) -> dict[str, float]:
        """
        Compute Information Coefficient (IC) and related alpha-factor statistics
        using alphalens (alphalens-reloaded).

        IC measures the rank correlation between a factor signal and its forward
        returns — the primary quality metric for any quantitative signal.

        Args:
            factor_scores: Series of float scores (index = datetime).
            forward_returns: Series of forward returns with the same index.
            periods: Number of periods ahead the forward returns are computed.

        Returns:
            Dict with 'ic_mean', 'ic_std', 'ir' (Information Ratio), and
            'ic_skew'.  All values are 0.0 when alphalens is unavailable or
            inputs are insufficient.
        """
        _empty: dict[str, float] = {'ic_mean': 0.0, 'ic_std': 0.0, 'ir': 0.0, 'ic_skew': 0.0}
        if not _ALPHALENS_AVAILABLE:
            self.logger.debug("alphalens not available — skipping IC computation")
            return _empty

        try:
            from scipy.stats import spearmanr
            # Align indices and drop NaNs
            aligned = pd.concat([factor_scores.rename('factor'), forward_returns.rename('fwd')], axis=1).dropna()  # noqa: E501
            if len(aligned) < 20:
                return _empty

            # Rolling IC (Spearman rank correlation, window=20)
            ic_series = []
            window = min(20, len(aligned) // 2)
            for i in range(window, len(aligned)):
                sub = aligned.iloc[i - window:i]
                rho, _ = spearmanr(sub['factor'], sub['fwd'])
                ic_series.append(float(rho))

            ic_arr = np.array(ic_series)
            ic_mean = float(np.mean(ic_arr))
            ic_std = float(np.std(ic_arr) + 1e-9)
            return {
                'ic_mean': ic_mean,
                'ic_std': ic_std,
                'ir': ic_mean / ic_std,
                'ic_skew': float(pd.Series(ic_arr).skew()),
            }
        except Exception as exc:
            self.error_handler.handle_error(exc, {'method': 'compute_factor_ic'})
            return _empty

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _calculate_iron_condor_confidence(self, context: OpportunityContext,
                                         market_data: pd.DataFrame) -> float:
        """Calculate confidence for iron condor opportunity"""
        confidence = 0.5  # Base confidence

        # IV rank bonus
        if context.iv_rank > 70:
            confidence += 0.2
        elif context.iv_rank > 50:
            confidence += 0.1

        # Range-bound market bonus
        if context.trend_strength < 0.2:
            confidence += 0.15
        elif context.trend_strength < 0.4:
            confidence += 0.05

        # Volatility environment bonus
        if context.vix_level > 25:
            confidence += 0.10

        # Regime stability bonus
        if context.regime_confidence > 0.7:
            confidence += 0.05

        return min(1.0, confidence)

    def _calculate_credit_spread_confidence(self, context: OpportunityContext,
                                          market_data: pd.DataFrame) -> float:
        """Calculate confidence for credit spread opportunity"""
        confidence = 0.5  # Base confidence

        # Trend strength bonus
        if abs(context.trend_strength) > 0.7:
            confidence += 0.2
        elif abs(context.trend_strength) > 0.5:
            confidence += 0.1

        # IV rank bonus
        if context.iv_rank > 60:
            confidence += 0.15

        # Volume confirmation
        if context.options_volume_ratio > 1.2:
            confidence += 0.05

        return min(1.0, confidence)

    async def _get_regime_context(self) -> dict[str, Any]:
        """Get current market regime context"""
        if self.regime_engine:
            try:
                # Would integrate with actual regime engine
                return {
                    'regime': 'bull_trending',
                    'confidence': 0.75,
                    'transition_prob': 0.15
                }
            except Exception as e:
                self.logger.error("Failed to get regime context: %s", e)

        return {'regime': 'unknown', 'confidence': 0.5, 'transition_prob': 0.2}

    def _estimate_iv_rank(self, market_data: pd.DataFrame) -> float:
        """Estimate IV rank from price volatility"""
        try:
            returns = market_data['close'].pct_change().dropna()
            if len(returns) < 20:
                return 50.0

            current_vol = returns.rolling(10).std().iloc[-1] * np.sqrt(252)
            historical_vols = returns.rolling(10).std() * np.sqrt(252)

            rank = (historical_vols <= current_vol).mean() * 100
            return min(95, max(5, rank))

        except Exception:
            return 50.0

    def _estimate_iv_percentile(self, market_data: pd.DataFrame) -> float:
        """Estimate IV percentile"""
        # Simplified - would use actual IV data
        return self._estimate_iv_rank(market_data)

    def _estimate_skew_level(self, market_data: pd.DataFrame) -> float:
        """Estimate volatility skew level"""
        # Placeholder - would use actual options data
        return 0.0

    def _get_flow_context(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Get options flow context"""
        # Placeholder - would integrate with flow tracker
        return {
            'put_call_ratio': 1.0,
            'volume_ratio': 1.0,
            'flow_bias': 'neutral'
        }

    def _find_key_levels(self, market_data: pd.DataFrame) -> tuple[list[float], list[float]]:
        """Find key support and resistance levels"""
        try:
            high = market_data['high'].values
            low = market_data['low'].values
            close = market_data['close'].values

            # Simple pivot detection
            support_levels = []
            resistance_levels = []

            window = 10
            for i in range(window, len(close) - window):
                # Local low (support)
                if all(low[i] <= low[j] for j in range(i-window, i+window+1) if j != i):
                    support_levels.append(low[i])

                # Local high (resistance)
                if all(high[i] >= high[j] for j in range(i-window, i+window+1) if j != i):
                    resistance_levels.append(high[i])

            # Keep recent levels
            current_price = close[-1]
            support_levels = [s for s in support_levels[-5:] if s < current_price]
            resistance_levels = [r for r in resistance_levels[-5:] if r > current_price]

            return support_levels, resistance_levels

        except Exception:
            return [], []

    def _calculate_trend_strength(self, market_data: pd.DataFrame) -> float:
        """Calculate trend strength (-1 to +1)"""
        try:
            prices = market_data['close']

            # Simple trend calculation
            if len(prices) < 20:
                return 0.0

            sma_short = prices.rolling(10).mean().iloc[-1]
            sma_long = prices.rolling(20).mean().iloc[-1]

            trend = (sma_short - sma_long) / sma_long
            return max(-1.0, min(1.0, trend * 10))  # Scale factor

        except Exception:
            return 0.0

    def _calculate_momentum_score(self, market_data: pd.DataFrame) -> float:
        """Calculate momentum score"""
        try:
            prices = market_data['close']

            if len(prices) < 10:
                return 0.0

            momentum = (prices.iloc[-1] - prices.iloc[-5]) / prices.iloc[-5]
            return max(-1.0, min(1.0, momentum * 20))

        except Exception:
            return 0.0

    # Additional placeholder methods for opportunity creation
    def _create_long_straddle_opportunity(self, context, market_data): return None
    def _create_volatility_arbitrage_opportunity(self, context, market_data): return None
    def _create_breakout_opportunity(self, context, market_data): return None
    def _create_mean_reversion_opportunity(self, context, market_data, direction, level): return None  # noqa: E501
    def _create_gamma_scalping_opportunity(self, context, market_data): return None
    def _create_theta_harvesting_opportunity(self, context, market_data): return None
    def _create_skew_arbitrage_opportunity(self, context, market_data): return None
    def _create_calendar_spread_opportunity(self, context, market_data): return None

    # Strategy analysis placeholder methods
    def _analyze_bull_call_spread(self, price): return {'name': 'Bull Call Spread', 'efficiency_score': 0.7}  # noqa: E501
    def _analyze_bull_put_spread(self, price): return {'name': 'Bull Put Spread', 'efficiency_score': 0.8}  # noqa: E501
    def _analyze_long_call_option(self, price): return {'name': 'Long Call', 'efficiency_score': 0.6}  # noqa: E501
    def _analyze_cash_secured_put(self, price): return {'name': 'Cash Secured Put', 'efficiency_score': 0.7}  # noqa: E501
    def _analyze_bear_call_spread(self, price): return {'name': 'Bear Call Spread', 'efficiency_score': 0.8}  # noqa: E501
    def _analyze_bear_put_spread(self, price): return {'name': 'Bear Put Spread', 'efficiency_score': 0.7}  # noqa: E501
    def _analyze_long_put_option(self, price): return {'name': 'Long Put', 'efficiency_score': 0.6}
    def _analyze_covered_call(self, price): return {'name': 'Covered Call', 'efficiency_score': 0.5}
    def _analyze_iron_condor(self, price): return {'name': 'Iron Condor', 'efficiency_score': 0.9}
    def _analyze_short_straddle(self, price): return {'name': 'Short Straddle', 'efficiency_score': 0.7}  # noqa: E501
    def _analyze_butterfly_spread(self, price): return {'name': 'Butterfly', 'efficiency_score': 0.6}  # noqa: E501
    def _analyze_calendar_spread(self, price): return {'name': 'Calendar Spread', 'efficiency_score': 0.8}  # noqa: E501

    def _is_market_condition_suitable(self, opp, context): return True
    def _calculate_regime_alignment_score(self, opp, context): return 0.8
    def _calculate_volatility_advantage_score(self, opp, context): return 0.7
    def _calculate_theta_advantage_score(self, opp, context): return 0.6

    # ==========================================================================
    # STATUS AND REPORTING METHODS
    # ==========================================================================

    def get_scanner_status(self) -> dict[str, Any]:
        """Get comprehensive scanner status"""
        with self._lock:
            return {
                'scanner_name': 'TradingOpportunityScanner',
                'is_scanning': self.is_scanning,
                'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
                'scan_frequency_seconds': self.scan_frequency_seconds,
                'active_opportunities': len(self.active_opportunities),
                'analytics_connections': {
                    'regime_engine': self.regime_engine is not None,
                    'risk_coordinator': self.risk_coordinator is not None,
                    'signals': SIGNALS_AVAILABLE
                },
                'performance_metrics': self.scanner_metrics.copy()
            }

    def get_opportunity_summary(self) -> dict[str, Any]:
        """Get summary of current opportunities"""
        with self._lock:
            if not self.active_opportunities:
                return {'total_opportunities': 0}

            opportunities = list(self.active_opportunities.values())

            # Group by type
            type_breakdown = defaultdict(int)
            priority_breakdown = defaultdict(int)

            total_expected_profit = 0
            total_max_loss = 0
            confidence_scores = []

            for opp in opportunities:
                type_breakdown[opp.opportunity_type.value] += 1
                priority_breakdown[opp.priority.value] += 1
                total_expected_profit += opp.expected_profit
                total_max_loss += opp.maximum_loss
                confidence_scores.append(opp.confidence_score)

            return {
                'total_opportunities': len(opportunities),
                'type_breakdown': dict(type_breakdown),
                'priority_breakdown': dict(priority_breakdown),
                'total_expected_profit': total_expected_profit,
                'total_max_loss': total_max_loss,
                'average_confidence': np.mean(confidence_scores) if confidence_scores else 0,
                'high_confidence_count': sum(1 for score in confidence_scores if score >= HIGH_CONFIDENCE_THRESHOLD)  # noqa: E501
            }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_opportunity_scanner(config: dict[str, Any] = None) -> TradingOpportunityScanner:
    """Create trading opportunity scanner instance"""
    return TradingOpportunityScanner(config)

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create opportunity scanner
    config = {
        'scan_frequency': 300,  # 5 minutes
        'min_confidence': 0.65,
        'max_opportunities': 10
    }

    scanner = create_opportunity_scanner(config)

    status = scanner.get_scanner_status()
    for _connection, available in status['analytics_connections'].items():
        status_symbol = '✅' if available else '❌'

    # Create sample market data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # SPY-like trending market data
    base_price = 450
    trend = np.linspace(0, 25, 100)  # $25 uptrend
    noise = np.random.randn(100) * 3
    prices = base_price + trend + noise

    # Add volatility spike
    vix_data = 20 + 10 * np.sin(np.linspace(0, 4*np.pi, 100)) + np.random.randn(100) * 2
    vix_data = np.clip(vix_data, 10, 45)

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 0.5,
        'high': prices + np.abs(np.random.randn(100) * 2),
        'low': prices - np.abs(np.random.randn(100) * 2),
        'close': prices,
        'volume': np.random.randint(50000000, 200000000, 100),
        'vix': vix_data
    })


    # Test opportunity scanning

    async def run_opportunity_scan():
        opportunities = await scanner.scan_opportunities(market_data)
        return opportunities

    # Run the async scan
    import asyncio
    opportunities = asyncio.run(run_opportunity_scan())


    if opportunities:
        for _i, opp in enumerate(opportunities[:5], 1):  # Show top 5

            if opp.strikes:
                pass


            if opp.risk_factors:
                pass
    else:
        pass

    # Test strategy comparison

    async def run_strategy_comparison():
        comparison = await scanner.compare_strategies_for_view("bullish", prices[-1])
        return comparison

    comparison = asyncio.run(run_strategy_comparison())


    for _strategy in comparison.strategies:
        pass

    # Get scanner summary
    summary = scanner.get_opportunity_summary()

    if summary.get('total_opportunities', 0) > 0:

        if summary.get('type_breakdown'):
            for _opp_type, _count in summary['type_breakdown'].items():
                pass
