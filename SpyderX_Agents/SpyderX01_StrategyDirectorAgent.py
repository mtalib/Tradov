#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX01_StrategyDirectorAgent.py
Purpose: AI-Enhanced Strategy Selection and Management
Group: X (AI Agents)

Description:
    Replaces the entire SpyderD strategy group (18 modules) with an intelligent
    AI agent that dynamically selects and manages trading strategies based on
    market conditions, portfolio state, and risk parameters.

    Replaced Modules:
    - SpyderD01_BullCallSpread through SpyderD18_VolatilityArbitrage
    - All strategy selection logic
    - Strategy parameter optimization
    - Multi-strategy portfolio management

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - asyncio
    - Existing Spyder infrastructure
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib

# Import Spyder core components
from SpyderU01_DataStructures import (
    OptionContract, Portfolio, TradeSignal, MarketData,
    Greeks, PositionType
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Strategy Types
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

# Market Regime
class MarketRegime(Enum):
    """Market conditions"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITION = "transition"

@dataclass
class StrategyParameters:
    """Parameters for strategy execution"""
    strategy_type: StrategyType
    strikes: List[float]
    expirations: List[datetime]
    quantities: List[int]
    max_loss: float
    target_profit: float
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    adjustment_rules: Dict[str, Any]
    confidence_score: float = 0.0

@dataclass
class StrategyPerformance:
    """Track strategy performance"""
    strategy_type: StrategyType
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_holding_period: timedelta = timedelta(0)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class MarketContext:
    """Current market analysis"""
    regime: MarketRegime
    trend_strength: float  # -1 to 1
    volatility_percentile: float  # 0 to 100
    support_levels: List[float]
    resistance_levels: List[float]
    volume_profile: Dict[str, float]
    sentiment_score: float  # -1 to 1
    economic_events: List[Dict[str, Any]]

class StrategyDirectorAgent(SpyderBaseAgent):
    """
    AI-Enhanced Strategy Director Agent
    
    Replaces traditional rule-based strategy selection with intelligent
    decision making based on market conditions and portfolio state.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Strategy Director Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('strategy_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.max_concurrent_strategies = config.get('max_concurrent_strategies', 5)
        self.min_confidence_threshold = config.get('min_strategy_confidence', 0.6)
        
        # Strategy management
        self.active_strategies: Dict[str, StrategyParameters] = {}
        self.strategy_performance: Dict[StrategyType, StrategyPerformance] = {}
        self.strategy_correlation_matrix: pd.DataFrame = pd.DataFrame()
        
        # Market analysis
        self.current_market_context: Optional[MarketContext] = None
        self.market_regime_history: deque = deque(maxlen=100)
        
        # Caching for performance
        self.strategy_cache: Dict[str, Tuple[StrategyParameters, datetime]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        # Risk integration
        self.risk_agent = None  # Will be set during initialization
        self.greeks_agent = None  # Will be set during initialization
        
        # Performance tracking
        self.decision_history: List[Dict[str, Any]] = []
        self.adaptation_metrics: Dict[str, float] = {}
        
        self.logger.info("Strategy Director Agent initialized")

    async def initialize(self, event_manager=None, risk_agent=None, greeks_agent=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.risk_agent = risk_agent
        self.greeks_agent = greeks_agent
        
        # Initialize strategy performance history
        for strategy_type in StrategyType:
            self.strategy_performance[strategy_type] = StrategyPerformance(strategy_type)
        
        # Subscribe to relevant events
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_update)
            self.event_manager.subscribe(EventType.PORTFOLIO_UPDATE, self._handle_portfolio_update)
            self.event_manager.subscribe(EventType.RISK_ALERT, self._handle_risk_alert)
        
        self.state = AgentState.RUNNING
        self.logger.info("Strategy Director Agent initialized with dependencies")

    async def select_strategy(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        risk_constraints: Dict[str, Any]
    ) -> Optional[StrategyParameters]:
        """
        Main strategy selection method
        
        Args:
            market_data: Current market data
            portfolio: Current portfolio state
            risk_constraints: Risk parameters from Risk Guardian
            
        Returns:
            Selected strategy parameters or None
        """
        try:
            # Update market context
            self.current_market_context = await self._analyze_market_context(market_data)
            
            # Check cache first
            cache_key = self._generate_cache_key(market_data, portfolio, risk_constraints)
            cached_strategy = self._get_cached_strategy(cache_key)
            if cached_strategy:
                self.logger.debug(f"Using cached strategy: {cached_strategy.strategy_type}")
                return cached_strategy
            
            # Get AI recommendation
            strategy_recommendation = await self._get_ai_strategy_recommendation(
                self.current_market_context,
                portfolio,
                risk_constraints
            )
            
            if strategy_recommendation and strategy_recommendation.confidence_score >= self.min_confidence_threshold:
                # Validate with risk agent
                if self.risk_agent:
                    risk_approved = await self._validate_with_risk_agent(
                        strategy_recommendation,
                        portfolio
                    )
                    if not risk_approved:
                        self.logger.warning("Strategy rejected by risk agent")
                        return None
                
                # Cache the decision
                self._cache_strategy(cache_key, strategy_recommendation)
                
                # Record decision
                self._record_decision(strategy_recommendation, self.current_market_context)
                
                return strategy_recommendation
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in strategy selection: {str(e)}")
            return None

    async def _analyze_market_context(self, market_data: MarketData) -> MarketContext:
        """Analyze current market conditions"""
        # Calculate technical indicators
        trend_strength = self._calculate_trend_strength(market_data)
        volatility_percentile = self._calculate_volatility_percentile(market_data)
        
        # Determine market regime
        regime = self._determine_market_regime(trend_strength, volatility_percentile)
        
        # Calculate support/resistance
        support_levels, resistance_levels = self._calculate_support_resistance(market_data)
        
        # Volume profile
        volume_profile = self._analyze_volume_profile(market_data)
        
        # Sentiment (placeholder - would integrate with sentiment agent)
        sentiment_score = 0.0
        
        # Economic events (placeholder - would integrate with calendar)
        economic_events = []
        
        context = MarketContext(
            regime=regime,
            trend_strength=trend_strength,
            volatility_percentile=volatility_percentile,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            volume_profile=volume_profile,
            sentiment_score=sentiment_score,
            economic_events=economic_events
        )
        
        # Update regime history
        self.market_regime_history.append((datetime.now(), regime))
        
        return context

    async def _get_ai_strategy_recommendation(
        self,
        market_context: MarketContext,
        portfolio: Portfolio,
        risk_constraints: Dict[str, Any]
    ) -> Optional[StrategyParameters]:
        """Get AI recommendation for strategy selection"""
        
        # Prepare context for LLM
        context = self._prepare_llm_context(market_context, portfolio, risk_constraints)
        
        # Query LLM
        prompt = f"""
        As an expert options trading strategist, analyze the following market conditions and portfolio state to recommend the best strategy:

        Market Context:
        - Regime: {market_context.regime.value}
        - Trend Strength: {market_context.trend_strength:.2f} (-1 to 1)
        - Volatility Percentile: {market_context.volatility_percentile:.1f}%
        - Current SPY Price: ${context['current_price']:.2f}
        - Support Levels: {market_context.support_levels[:3]}
        - Resistance Levels: {market_context.resistance_levels[:3]}

        Portfolio State:
        - Available Capital: ${portfolio.cash:.2f}
        - Current Positions: {len(portfolio.positions)}
        - Open P&L: ${context['open_pnl']:.2f}
        - Current Leverage: {context['leverage']:.2f}x

        Risk Constraints:
        - Max Position Size: ${risk_constraints.get('max_position_size', 10000):.2f}
        - Max Portfolio Risk: {risk_constraints.get('max_portfolio_risk', 0.02)*100:.1f}%
        - Required Win Rate: {risk_constraints.get('min_win_rate', 0.5)*100:.0f}%

        Strategy Performance History:
        {self._format_strategy_performance()}

        Based on this analysis, recommend:
        1. The most appropriate strategy type
        2. Specific strike prices and expirations
        3. Position sizing
        4. Entry and exit conditions
        5. Confidence level (0-1)

        Respond in JSON format with the structure:
        {{
            "strategy_type": "strategy_name",
            "reasoning": "brief explanation",
            "strikes": [strike1, strike2],
            "expiration_days": days_to_expiration,
            "position_size": number_of_contracts,
            "entry_conditions": {{}},
            "exit_conditions": {{}},
            "confidence": 0.0-1.0
        }}
        """
        
        try:
            # Call LLM (with timeout)
            response = await asyncio.wait_for(
                self._query_llm(prompt),
                timeout=5.0
            )
            
            # Parse response
            strategy_data = json.loads(response)
            
            # Convert to StrategyParameters
            return self._parse_strategy_recommendation(strategy_data, context['current_price'])
            
        except asyncio.TimeoutError:
            self.logger.warning("LLM query timeout, using fallback strategy")
            return self._get_fallback_strategy(market_context, portfolio)
        except Exception as e:
            self.logger.error(f"Error in AI recommendation: {str(e)}")
            return self._get_fallback_strategy(market_context, portfolio)

    def _calculate_trend_strength(self, market_data: MarketData) -> float:
        """Calculate trend strength from -1 (strong down) to 1 (strong up)"""
        if not market_data.price_history or len(market_data.price_history) < 20:
            return 0.0
        
        prices = [p.close for p in market_data.price_history[-20:]]
        
        # Simple trend strength based on slope and consistency
        returns = np.diff(prices) / prices[:-1]
        trend = np.mean(returns) * 100  # Scale up
        consistency = 1 - np.std(returns)  # Higher consistency = stronger trend
        
        return np.clip(trend * consistency, -1, 1)

    def _calculate_volatility_percentile(self, market_data: MarketData) -> float:
        """Calculate current volatility percentile (0-100)"""
        if hasattr(market_data, 'implied_volatility'):
            # Use IV percentile if available
            return market_data.iv_percentile
        
        # Calculate historical volatility percentile
        if not market_data.price_history or len(market_data.price_history) < 252:
            return 50.0  # Default to median
        
        prices = [p.close for p in market_data.price_history]
        returns = np.diff(prices) / prices[:-1]
        
        # 20-day rolling volatility
        vol_window = 20
        volatilities = []
        for i in range(vol_window, len(returns)):
            vol = np.std(returns[i-vol_window:i]) * np.sqrt(252)
            volatilities.append(vol)
        
        current_vol = volatilities[-1]
        percentile = (np.sum(np.array(volatilities) <= current_vol) / len(volatilities)) * 100
        
        return percentile

    def _determine_market_regime(self, trend_strength: float, volatility_percentile: float) -> MarketRegime:
        """Determine current market regime"""
        if volatility_percentile > 80:
            return MarketRegime.HIGH_VOLATILITY
        elif volatility_percentile < 20:
            return MarketRegime.LOW_VOLATILITY
        elif trend_strength > 0.5:
            return MarketRegime.TRENDING_UP
        elif trend_strength < -0.5:
            return MarketRegime.TRENDING_DOWN
        elif abs(trend_strength) < 0.2:
            return MarketRegime.RANGE_BOUND
        else:
            return MarketRegime.TRANSITION

    def _calculate_support_resistance(self, market_data: MarketData) -> Tuple[List[float], List[float]]:
        """Calculate support and resistance levels"""
        if not market_data.price_history or len(market_data.price_history) < 20:
            current_price = market_data.current_price
            return [current_price * 0.98, current_price * 0.96], [current_price * 1.02, current_price * 1.04]
        
        prices = [p.high for p in market_data.price_history[-50:]]
        lows = [p.low for p in market_data.price_history[-50:]]
        
        # Simple pivot points
        highs_sorted = sorted(set(prices), reverse=True)
        lows_sorted = sorted(set(lows))
        
        resistance_levels = highs_sorted[:3] if len(highs_sorted) >= 3 else highs_sorted
        support_levels = lows_sorted[:3] if len(lows_sorted) >= 3 else lows_sorted
        
        return support_levels, resistance_levels

    def _analyze_volume_profile(self, market_data: MarketData) -> Dict[str, float]:
        """Analyze volume profile"""
        profile = {
            'average_volume': 0,
            'current_volume_ratio': 1.0,
            'volume_trend': 0.0
        }
        
        if hasattr(market_data, 'volume_history') and market_data.volume_history:
            volumes = market_data.volume_history[-20:]
            profile['average_volume'] = np.mean(volumes)
            if len(volumes) > 1:
                profile['current_volume_ratio'] = volumes[-1] / profile['average_volume']
                profile['volume_trend'] = (volumes[-1] - volumes[-5]) / volumes[-5] if volumes[-5] > 0 else 0
        
        return profile

    def _prepare_llm_context(
        self,
        market_context: MarketContext,
        portfolio: Portfolio,
        risk_constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare context data for LLM"""
        # Calculate portfolio metrics
        open_pnl = sum(pos.unrealized_pnl for pos in portfolio.positions.values())
        leverage = sum(abs(pos.quantity * pos.entry_price) for pos in portfolio.positions.values()) / portfolio.cash if portfolio.cash > 0 else 0
        
        return {
            'current_price': market_context.support_levels[0] if market_context.support_levels else 0,
            'open_pnl': open_pnl,
            'leverage': leverage,
            'active_strategies': list(self.active_strategies.keys())
        }

    def _format_strategy_performance(self) -> str:
        """Format strategy performance for LLM context"""
        perf_summary = []
        for strategy_type, perf in self.strategy_performance.items():
            if perf.total_trades > 0:
                win_rate = (perf.winning_trades / perf.total_trades) * 100
                avg_pnl = perf.total_pnl / perf.total_trades
                perf_summary.append(
                    f"- {strategy_type.value}: {win_rate:.0f}% win rate, "
                    f"${avg_pnl:.2f} avg P&L, {perf.total_trades} trades"
                )
        
        return '\n'.join(perf_summary[:5]) if perf_summary else "No historical performance data"

    def _parse_strategy_recommendation(
        self,
        strategy_data: Dict[str, Any],
        current_price: float
    ) -> StrategyParameters:
        """Parse LLM recommendation into StrategyParameters"""
        # Map strategy name to enum
        strategy_type = StrategyType(strategy_data['strategy_type'])
        
        # Calculate expiration date
        expiration_days = strategy_data.get('expiration_days', 30)
        expiration = datetime.now() + timedelta(days=expiration_days)
        
        # Build parameters
        params = StrategyParameters(
            strategy_type=strategy_type,
            strikes=strategy_data.get('strikes', [current_price]),
            expirations=[expiration],
            quantities=[strategy_data.get('position_size', 1)],
            max_loss=strategy_data.get('max_loss', 1000),
            target_profit=strategy_data.get('target_profit', 500),
            entry_conditions=strategy_data.get('entry_conditions', {}),
            exit_conditions=strategy_data.get('exit_conditions', {}),
            adjustment_rules=strategy_data.get('adjustment_rules', {}),
            confidence_score=strategy_data.get('confidence', 0.5)
        )
        
        return params

    def _get_fallback_strategy(
        self,
        market_context: MarketContext,
        portfolio: Portfolio
    ) -> StrategyParameters:
        """Get fallback strategy when AI fails"""
        # Simple rule-based fallback
        current_price = market_context.support_levels[0] if market_context.support_levels else 400
        
        if market_context.regime == MarketRegime.TRENDING_UP:
            # Bull call spread
            return StrategyParameters(
                strategy_type=StrategyType.BULL_CALL_SPREAD,
                strikes=[current_price, current_price * 1.02],
                expirations=[datetime.now() + timedelta(days=30)],
                quantities=[1, -1],
                max_loss=200,
                target_profit=300,
                entry_conditions={'min_iv_rank': 30},
                exit_conditions={'profit_target': 0.5, 'stop_loss': 0.5},
                adjustment_rules={},
                confidence_score=0.6
            )
        else:
            # Iron condor for range-bound or uncertain markets
            return StrategyParameters(
                strategy_type=StrategyType.IRON_CONDOR,
                strikes=[
                    current_price * 0.95,
                    current_price * 0.97,
                    current_price * 1.03,
                    current_price * 1.05
                ],
                expirations=[datetime.now() + timedelta(days=45)],
                quantities=[1, -1, -1, 1],
                max_loss=200,
                target_profit=100,
                entry_conditions={'min_iv_rank': 50},
                exit_conditions={'profit_target': 0.5, 'stop_loss': 0.75},
                adjustment_rules={'roll_at_dte': 21},
                confidence_score=0.5
            )

    async def _validate_with_risk_agent(
        self,
        strategy: StrategyParameters,
        portfolio: Portfolio
    ) -> bool:
        """Validate strategy with risk agent"""
        if not self.risk_agent:
            return True  # Pass if no risk agent
        
        # Create mock trade for validation
        mock_trade = {
            'strategy': strategy.strategy_type.value,
            'max_loss': strategy.max_loss,
            'strikes': strategy.strikes,
            'quantities': strategy.quantities
        }
        
        risk_assessment = await self.risk_agent.evaluate_trade(mock_trade, portfolio)
        return risk_assessment.get('approved', False)

    def _generate_cache_key(
        self,
        market_data: MarketData,
        portfolio: Portfolio,
        risk_constraints: Dict[str, Any]
    ) -> str:
        """Generate cache key for strategy decisions"""
        key_data = {
            'price': round(market_data.current_price, 1),
            'regime': self.current_market_context.regime.value if self.current_market_context else 'unknown',
            'positions': len(portfolio.positions),
            'cash': round(portfolio.cash, -2),  # Round to nearest 100
            'risk': str(risk_constraints)
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_strategy(self, cache_key: str) -> Optional[StrategyParameters]:
        """Get cached strategy if valid"""
        if cache_key in self.strategy_cache:
            strategy, timestamp = self.strategy_cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return strategy
            else:
                del self.strategy_cache[cache_key]
        return None

    def _cache_strategy(self, cache_key: str, strategy: StrategyParameters):
        """Cache strategy decision"""
        self.strategy_cache[cache_key] = (strategy, datetime.now())
        
        # Clean old cache entries
        if len(self.strategy_cache) > 1000:
            # Remove oldest entries
            sorted_cache = sorted(self.strategy_cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_cache[:100]:
                del self.strategy_cache[key]

    def _record_decision(self, strategy: StrategyParameters, market_context: MarketContext):
        """Record strategy decision for analysis"""
        decision = {
            'timestamp': datetime.now(),
            'strategy': strategy.strategy_type.value,
            'confidence': strategy.confidence_score,
            'market_regime': market_context.regime.value,
            'trend_strength': market_context.trend_strength,
            'volatility_percentile': market_context.volatility_percentile
        }
        
        self.decision_history.append(decision)
        
        # Keep only recent history
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]

    async def update_strategy_performance(
        self,
        strategy_type: StrategyType,
        trade_result: Dict[str, Any]
    ):
        """Update strategy performance metrics"""
        perf = self.strategy_performance[strategy_type]
        
        perf.total_trades += 1
        if trade_result['pnl'] > 0:
            perf.winning_trades += 1
        
        perf.total_pnl += trade_result['pnl']
        perf.last_updated = datetime.now()
        
        # Update Sharpe ratio and other metrics
        # (simplified - would need more sophisticated calculation)
        if perf.total_trades > 10:
            win_rate = perf.winning_trades / perf.total_trades
            avg_pnl = perf.total_pnl / perf.total_trades
            perf.sharpe_ratio = (win_rate - 0.5) * 2  # Simplified
        
        self.logger.info(
            f"Updated {strategy_type.value} performance: "
            f"{perf.winning_trades}/{perf.total_trades} wins, "
            f"${perf.total_pnl:.2f} total P&L"
        )

    async def get_active_strategies(self) -> Dict[str, StrategyParameters]:
        """Get currently active strategies"""
        return self.active_strategies.copy()

    async def close_strategy(self, strategy_id: str) -> bool:
        """Close an active strategy"""
        if strategy_id in self.active_strategies:
            del self.active_strategies[strategy_id]
            self.logger.info(f"Closed strategy: {strategy_id}")
            return True
        return False

    async def _handle_market_update(self, event: Event):
        """Handle market data updates"""
        # Update market context periodically
        if hasattr(event, 'data') and 'market_data' in event.data:
            asyncio.create_task(self._analyze_market_context(event.data['market_data']))

    async def _handle_portfolio_update(self, event: Event):
        """Handle portfolio updates"""
        # Re-evaluate strategies if portfolio changes significantly
        pass

    async def _handle_risk_alert(self, event: Event):
        """Handle risk alerts"""
        if hasattr(event, 'data') and event.data.get('severity') == 'high':
            # Consider closing or adjusting strategies
            self.logger.warning(f"Risk alert received: {event.data}")

    async def _query_llm(self, prompt: str) -> str:
        """Query the LLM (placeholder for actual implementation)"""
        # In production, this would call ollama or another LLM service
        # For now, return a mock response
        return json.dumps({
            "strategy_type": "iron_condor",
            "reasoning": "High IV environment favors premium selling",
            "strikes": [390, 395, 405, 410],
            "expiration_days": 45,
            "position_size": 1,
            "entry_conditions": {"iv_rank": 50},
            "exit_conditions": {"profit_target": 0.5},
            "confidence": 0.75
        })

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Save performance metrics
        self._save_performance_history()
        
        self.logger.info("Strategy Director Agent shutdown complete")

    def _save_performance_history(self):
        """Save performance history for future analysis"""
        # Would save to database or file
        pass

# Factory function
def create_strategy_director_agent(config: Dict[str, Any]) -> StrategyDirectorAgent:
    """Create and return a Strategy Director Agent instance"""
    return StrategyDirectorAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'strategy_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'max_concurrent_strategies': 5,
        'min_strategy_confidence': 0.6
    }
    
    # Create agent
    strategy_agent = create_strategy_director_agent(test_config)
    
    # Example usage (would be in async context)
    async def example_usage():
        # Initialize agent
        await strategy_agent.initialize()
        
        # Mock market data and portfolio
        market_data = MarketData(current_price=400.0)
        portfolio = Portfolio(cash=10000.0)
        risk_constraints = {
            'max_position_size': 5000,
            'max_portfolio_risk': 0.02,
            'min_win_rate': 0.5
        }
        
        # Get strategy recommendation
        strategy = await strategy_agent.select_strategy(
            market_data,
            portfolio,
            risk_constraints
        )
        
        if strategy:
            print(f"Recommended: {strategy.strategy_type.value}")
            print(f"Confidence: {strategy.confidence_score:.2f}")
            print(f"Strikes: {strategy.strikes}")
    
    # Run example
    # asyncio.run(example_usage())
