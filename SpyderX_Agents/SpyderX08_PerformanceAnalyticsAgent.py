#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX08_PerformanceAnalyticsAgent.py
Purpose: AI-Enhanced Performance Analytics and Trading Insights
Group: X (AI Agents)

This module implements an intelligent performance analytics agent that tracks,
analyzes, and provides AI-driven insights on trading performance, identifying
patterns and suggesting optimizations using Ollama AI integration.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-16
Last Updated: 2025-06-19 Time: 13:50
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import statistics
import numpy as np
from collections import defaultdict, deque

# Third-party imports
import pandas as pd

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Performance metrics
PERFORMANCE_METRICS = [
    'total_return',
    'sharpe_ratio',
    'sortino_ratio',
    'max_drawdown',
    'win_rate',
    'profit_factor',
    'average_win',
    'average_loss',
    'expectancy',
    'kelly_criterion'
]

# Time periods for analysis
class TimePeriod(Enum):
    """Time period enumeration."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    ALL_TIME = "ALL_TIME"

# Performance categories
class PerformanceCategory(Enum):
    """Performance category enumeration."""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    BELOW_AVERAGE = "BELOW_AVERAGE"
    POOR = "POOR"

# Risk metrics thresholds
RISK_THRESHOLDS = {
    'max_drawdown_warning': 0.10,  # 10%
    'max_drawdown_critical': 0.20,  # 20%
    'sharpe_ratio_good': 1.5,
    'sharpe_ratio_excellent': 2.0,
    'win_rate_minimum': 0.45,
    'profit_factor_minimum': 1.2
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.4

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class Trade:
    """Trade data structure."""
    id: str
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: str  # 'LONG' or 'SHORT'
    pnl: Optional[float]
    strategy: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure."""
    period: TimePeriod
    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    expectancy: float
    kelly_criterion: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceReport:
    """Performance report data structure."""
    metrics: PerformanceMetrics
    category: PerformanceCategory
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    ai_insights: Dict[str, Any]
    risk_assessment: Dict[str, Any]

@dataclass
class OptimizationSuggestion:
    """Optimization suggestion data structure."""
    category: str
    priority: str  # 'HIGH', 'MEDIUM', 'LOW'
    suggestion: str
    expected_impact: str
    implementation_steps: List[str]
    confidence: float

# ==============================================================================
# PERFORMANCE ANALYTICS AGENT CLASS
# ==============================================================================

class SpyderX08_PerformanceAnalyticsAgent:
    """
    AI-Enhanced Performance Analytics Agent.
    
    This agent analyzes trading performance using AI to identify patterns,
    provide insights, and suggest optimizations for the SPY options trading system.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Performance Analytics Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Data storage
        self.trades = []
        self.daily_equity = {}
        self.performance_cache = {}
        
        # Analysis state
        self.last_analysis_time = None
        self.pattern_memory = deque(maxlen=100)
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # MAIN ANALYSIS METHODS
    # ==========================================================================
    
    async def analyze_performance(self, trades: List[Trade],
                                period: TimePeriod = TimePeriod.ALL_TIME,
                                end_date: Optional[datetime] = None) -> PerformanceReport:
        """
        Analyze trading performance with AI insights.
        
        Args:
            trades: List of trades to analyze
            period: Time period for analysis
            end_date: End date for analysis (default: now)
            
        Returns:
            PerformanceReport object
        """
        self.logger.info(f"Analyzing performance for {period.value} period")
        
        try:
            # Filter trades by period
            filtered_trades = self._filter_trades_by_period(trades, period, end_date)
            
            if not filtered_trades:
                return self._create_empty_report(period)
            
            # Calculate metrics
            metrics = self._calculate_performance_metrics(filtered_trades, period)
            
            # Get AI insights
            ai_insights = await self._get_ai_performance_insights(metrics, filtered_trades)
            
            # Categorize performance
            category = self._categorize_performance(metrics)
            
            # Identify strengths and weaknesses
            strengths, weaknesses = self._identify_strengths_weaknesses(metrics)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(metrics, ai_insights)
            
            # Risk assessment
            risk_assessment = self._assess_risk(metrics, filtered_trades)
            
            # Cache results
            cache_key = f"{period.value}_{end_date or 'latest'}"
            self.performance_cache[cache_key] = metrics
            
            return PerformanceReport(
                metrics=metrics,
                category=category,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                ai_insights=ai_insights,
                risk_assessment=risk_assessment
            )
            
        except Exception as e:
            self.logger.error(f"Performance analysis failed: {e}")
            return self._create_empty_report(period)
    
    async def get_optimization_suggestions(self, 
                                         recent_performance: PerformanceMetrics,
                                         historical_trades: List[Trade]) -> List[OptimizationSuggestion]:
        """
        Get AI-powered optimization suggestions.
        
        Args:
            recent_performance: Recent performance metrics
            historical_trades: Historical trade data
            
        Returns:
            List of optimization suggestions
        """
        self.logger.info("Generating optimization suggestions")
        
        # Get AI suggestions
        ai_suggestions = await self._get_ai_optimization_suggestions(
            recent_performance, historical_trades
        )
        
        # Combine with rule-based suggestions
        rule_suggestions = self._get_rule_based_suggestions(recent_performance)
        
        # Merge and prioritize
        all_suggestions = self._merge_and_prioritize_suggestions(
            ai_suggestions, rule_suggestions
        )
        
        return all_suggestions
    
    # ==========================================================================
    # METRICS CALCULATION METHODS
    # ==========================================================================
    
    def _calculate_performance_metrics(self, trades: List[Trade],
                                     period: TimePeriod) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        if not trades:
            return self._create_empty_metrics(period)
        
        # Basic statistics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
        # Returns
        returns = [t.pnl for t in trades if t.pnl is not None]
        total_return = sum(returns) if returns else 0
        
        # Win/Loss statistics
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = (sum(t.pnl for t in winning_trades) / len(winning_trades) 
                  if winning_trades else 0)
        avg_loss = (sum(abs(t.pnl) for t in losing_trades) / len(losing_trades)
                   if losing_trades else 0)
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = sum(abs(t.pnl) for t in losing_trades)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Expectancy
        expectancy = (win_rate * avg_win - (1 - win_rate) * avg_loss) if total_trades > 0 else 0
        
        # Risk-adjusted returns
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        max_drawdown = self._calculate_max_drawdown(trades)
        
        # Kelly Criterion
        kelly_criterion = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)
        
        # Date range
        start_date = min(t.entry_time for t in trades)
        end_date = max(t.exit_time or t.entry_time for t in trades)
        
        return PerformanceMetrics(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            average_win=avg_win,
            average_loss=avg_loss,
            expectancy=expectancy,
            kelly_criterion=kelly_criterion
        )
    
    def _calculate_sharpe_ratio(self, returns: List[float],
                              risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        
        avg_return = statistics.mean(returns)
        std_dev = statistics.stdev(returns)
        
        if std_dev == 0:
            return 0.0
        
        # Annualized Sharpe ratio (assuming daily returns)
        return (avg_return - risk_free_rate/252) / std_dev * np.sqrt(252)
    
    def _calculate_sortino_ratio(self, returns: List[float],
                               risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio."""
        if not returns:
            return 0.0
        
        avg_return = statistics.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        
        if not downside_returns:
            return float('inf') if avg_return > risk_free_rate else 0.0
        
        downside_std = statistics.stdev(downside_returns) if len(downside_returns) > 1 else 0
        
        if downside_std == 0:
            return 0.0
        
        # Annualized Sortino ratio
        return (avg_return - risk_free_rate/252) / downside_std * np.sqrt(252)
    
    def _calculate_max_drawdown(self, trades: List[Trade]) -> float:
        """Calculate maximum drawdown."""
        if not trades:
            return 0.0
        
        # Build equity curve
        equity = 0
        peak = 0
        max_dd = 0
        
        sorted_trades = sorted(trades, key=lambda t: t.exit_time or t.entry_time)
        
        for trade in sorted_trades:
            if trade.pnl is not None:
                equity += trade.pnl
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0
                max_dd = max(max_dd, drawdown)
        
        return max_dd
    
    def _calculate_kelly_criterion(self, win_rate: float,
                                 avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly Criterion for position sizing."""
        if avg_loss == 0 or win_rate == 0:
            return 0.0
        
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Cap at 25% for safety
        return min(0.25, max(0, kelly))
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _get_ai_performance_insights(self, metrics: PerformanceMetrics,
                                         trades: List[Trade]) -> Dict[str, Any]:
        """Get AI insights on performance."""
        if not self.ollama_client:
            return self._get_fallback_insights(metrics)
        
        # Prepare trade summary
        strategy_performance = self._summarize_strategy_performance(trades)
        
        prompt = f"""Analyze this trading performance and provide insights:

Performance Metrics:
- Total Trades: {metrics.total_trades}
- Win Rate: {metrics.win_rate:.1%}
- Profit Factor: {metrics.profit_factor:.2f}
- Sharpe Ratio: {metrics.sharpe_ratio:.2f}
- Max Drawdown: {metrics.max_drawdown:.1%}
- Total Return: ${metrics.total_return:.2f}
- Expectancy: ${metrics.expectancy:.2f}

Strategy Performance:
{json.dumps(strategy_performance, indent=2)}

Provide a JSON response with:
{{
    "performance_summary": "overall assessment",
    "key_patterns": ["pattern1", "pattern2", ...],
    "risk_concerns": ["concern1", "concern2", ...],
    "improvement_areas": ["area1", "area2", ...],
    "market_adaptation": "how well strategies adapt to market",
    "psychological_factors": "trading discipline assessment",
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return self._get_fallback_insights(metrics)
                
        except Exception as e:
            self.logger.error(f"AI performance insights failed: {e}")
            return self._get_fallback_insights(metrics)
    
    async def _get_ai_optimization_suggestions(self,
                                             performance: PerformanceMetrics,
                                             trades: List[Trade]) -> List[OptimizationSuggestion]:
        """Get AI-powered optimization suggestions."""
        if not self.ollama_client:
            return []
        
        prompt = f"""Based on this trading performance, suggest optimizations:

Current Performance:
- Win Rate: {performance.win_rate:.1%}
- Sharpe Ratio: {performance.sharpe_ratio:.2f}
- Max Drawdown: {performance.max_drawdown:.1%}
- Profit Factor: {performance.profit_factor:.2f}

Weaknesses Identified:
{self._identify_weaknesses_for_prompt(performance)}

Provide a JSON response with optimization suggestions:
{{
    "suggestions": [
        {{
            "category": "risk_management/entry_timing/exit_strategy/position_sizing",
            "priority": "HIGH/MEDIUM/LOW",
            "suggestion": "specific suggestion",
            "expected_impact": "expected improvement",
            "implementation_steps": ["step1", "step2", ...],
            "confidence": 0.0-1.0
        }}
    ]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                suggestions = []
                
                for item in data.get('suggestions', []):
                    suggestions.append(OptimizationSuggestion(
                        category=item.get('category', 'general'),
                        priority=item.get('priority', 'MEDIUM'),
                        suggestion=item.get('suggestion', ''),
                        expected_impact=item.get('expected_impact', ''),
                        implementation_steps=item.get('implementation_steps', []),
                        confidence=item.get('confidence', 0.5)
                    ))
                
                return suggestions
            else:
                return []
                
        except Exception as e:
            self.logger.error(f"AI optimization suggestions failed: {e}")
            return []
    
    def _get_fallback_insights(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """Fallback insights when AI is unavailable."""
        patterns = []
        concerns = []
        improvements = []
        
        # Identify patterns
        if metrics.win_rate > 0.6:
            patterns.append("High win rate strategy")
        if metrics.profit_factor > 2:
            patterns.append("Strong profit factor")
        
        # Risk concerns
        if metrics.max_drawdown > 0.15:
            concerns.append("High maximum drawdown")
        if metrics.sharpe_ratio < 1:
            concerns.append("Low risk-adjusted returns")
        
        # Improvements
        if metrics.win_rate < 0.5:
            improvements.append("Improve trade selection")
        if metrics.expectancy < 0:
            improvements.append("Review risk-reward ratios")
        
        return {
            'performance_summary': 'Rule-based analysis',
            'key_patterns': patterns,
            'risk_concerns': concerns,
            'improvement_areas': improvements,
            'market_adaptation': 'Requires AI analysis',
            'psychological_factors': 'Requires AI analysis',
            'confidence': 0.5
        }
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def _categorize_performance(self, metrics: PerformanceMetrics) -> PerformanceCategory:
        """Categorize overall performance."""
        score = 0
        
        # Score based on key metrics
        if metrics.sharpe_ratio >= RISK_THRESHOLDS['sharpe_ratio_excellent']:
            score += 3
        elif metrics.sharpe_ratio >= RISK_THRESHOLDS['sharpe_ratio_good']:
            score += 2
        elif metrics.sharpe_ratio >= 1:
            score += 1
        
        if metrics.win_rate >= 0.6:
            score += 2
        elif metrics.win_rate >= RISK_THRESHOLDS['win_rate_minimum']:
            score += 1
        
        if metrics.profit_factor >= 2:
            score += 2
        elif metrics.profit_factor >= RISK_THRESHOLDS['profit_factor_minimum']:
            score += 1
        
        if metrics.max_drawdown <= RISK_THRESHOLDS['max_drawdown_warning']:
            score += 2
        elif metrics.max_drawdown <= RISK_THRESHOLDS['max_drawdown_critical']:
            score += 1
        
        # Categorize based on score
        if score >= 8:
            return PerformanceCategory.EXCELLENT
        elif score >= 6:
            return PerformanceCategory.GOOD
        elif score >= 4:
            return PerformanceCategory.AVERAGE
        elif score >= 2:
            return PerformanceCategory.BELOW_AVERAGE
        else:
            return PerformanceCategory.POOR
    
    def _identify_strengths_weaknesses(self, 
                                     metrics: PerformanceMetrics) -> Tuple[List[str], List[str]]:
        """Identify performance strengths and weaknesses."""
        strengths = []
        weaknesses = []
        
        # Strengths
        if metrics.sharpe_ratio >= RISK_THRESHOLDS['sharpe_ratio_excellent']:
            strengths.append("Excellent risk-adjusted returns")
        elif metrics.sharpe_ratio >= RISK_THRESHOLDS['sharpe_ratio_good']:
            strengths.append("Good risk-adjusted returns")
        
        if metrics.win_rate >= 0.6:
            strengths.append(f"High win rate ({metrics.win_rate:.1%})")
        
        if metrics.profit_factor >= 2:
            strengths.append(f"Strong profit factor ({metrics.profit_factor:.1f})")
        
        if metrics.max_drawdown <= RISK_THRESHOLDS['max_drawdown_warning']:
            strengths.append(f"Low drawdown risk ({metrics.max_drawdown:.1%})")
        
        if metrics.expectancy > 0:
            strengths.append(f"Positive expectancy (${metrics.expectancy:.2f})")
        
        # Weaknesses
        if metrics.sharpe_ratio < 1:
            weaknesses.append("Low risk-adjusted returns")
        
        if metrics.win_rate < RISK_THRESHOLDS['win_rate_minimum']:
            weaknesses.append(f"Low win rate ({metrics.win_rate:.1%})")
        
        if metrics.profit_factor < RISK_THRESHOLDS['profit_factor_minimum']:
            weaknesses.append(f"Weak profit factor ({metrics.profit_factor:.1f})")
        
        if metrics.max_drawdown > RISK_THRESHOLDS['max_drawdown_critical']:
            weaknesses.append(f"High drawdown risk ({metrics.max_drawdown:.1%})")
        
        if metrics.expectancy <= 0:
            weaknesses.append("Negative or zero expectancy")
        
        return strengths, weaknesses
    
    def _generate_recommendations(self, metrics: PerformanceMetrics,
                                ai_insights: Dict[str, Any]) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Risk management recommendations
        if metrics.max_drawdown > RISK_THRESHOLDS['max_drawdown_critical']:
            recommendations.append("Implement stricter position sizing to reduce drawdown risk")
        
        if metrics.sharpe_ratio < 1:
            recommendations.append("Focus on improving risk-reward ratios")
        
        # Win rate recommendations
        if metrics.win_rate < RISK_THRESHOLDS['win_rate_minimum']:
            recommendations.append("Improve trade entry criteria for better win rate")
        
        # Profit optimization
        if metrics.average_win < metrics.average_loss * 2:
            recommendations.append("Target higher profit targets relative to stop losses")
        
        # Add AI recommendations if available
        ai_improvements = ai_insights.get('improvement_areas', [])
        recommendations.extend(ai_improvements[:3])  # Top 3 AI suggestions
        
        return recommendations
    
    def _assess_risk(self, metrics: PerformanceMetrics,
                    trades: List[Trade]) -> Dict[str, Any]:
        """Assess trading risk profile."""
        risk_score = 0
        risk_factors = []
        
        # Drawdown risk
        if metrics.max_drawdown > RISK_THRESHOLDS['max_drawdown_critical']:
            risk_score += 3
            risk_factors.append("Critical drawdown levels")
        elif metrics.max_drawdown > RISK_THRESHOLDS['max_drawdown_warning']:
            risk_score += 2
            risk_factors.append("Elevated drawdown risk")
        
        # Consistency risk
        if metrics.win_rate < RISK_THRESHOLDS['win_rate_minimum']:
            risk_score += 2
            risk_factors.append("Low win rate")
        
        # Profit factor risk
        if metrics.profit_factor < RISK_THRESHOLDS['profit_factor_minimum']:
            risk_score += 2
            risk_factors.append("Weak profit factor")
        
        # Risk level
        if risk_score >= 5:
            risk_level = "HIGH"
        elif risk_score >= 3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'var_95': self._calculate_var(trades, 0.95),
            'recommended_position_size': min(0.25, metrics.kelly_criterion)
        }
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _filter_trades_by_period(self, trades: List[Trade],
                               period: TimePeriod,
                               end_date: Optional[datetime]) -> List[Trade]:
        """Filter trades by time period."""
        if period == TimePeriod.ALL_TIME:
            return trades
        
        end = end_date or datetime.now()
        
        period_days = {
            TimePeriod.DAILY: 1,
            TimePeriod.WEEKLY: 7,
            TimePeriod.MONTHLY: 30,
            TimePeriod.QUARTERLY: 90,
            TimePeriod.YEARLY: 365
        }
        
        start = end - timedelta(days=period_days.get(period, 30))
        
        return [t for t in trades if start <= (t.exit_time or t.entry_time) <= end]
    
    def _summarize_strategy_performance(self, trades: List[Trade]) -> Dict[str, Any]:
        """Summarize performance by strategy."""
        strategy_stats = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'pnl': 0, 'avg_pnl': 0
        })
        
        for trade in trades:
            strategy = trade.strategy
            strategy_stats[strategy]['trades'] += 1
            if trade.pnl:
                strategy_stats[strategy]['pnl'] += trade.pnl
                if trade.pnl > 0:
                    strategy_stats[strategy]['wins'] += 1
        
        # Calculate averages and win rates
        for strategy, stats in strategy_stats.items():
            if stats['trades'] > 0:
                stats['avg_pnl'] = stats['pnl'] / stats['trades']
                stats['win_rate'] = stats['wins'] / stats['trades']
        
        return dict(strategy_stats)
    
    def _identify_weaknesses_for_prompt(self, metrics: PerformanceMetrics) -> str:
        """Format weaknesses for AI prompt."""
        _, weaknesses = self._identify_strengths_weaknesses(metrics)
        return '\n'.join(f"- {w}" for w in weaknesses) if weaknesses else "None identified"
    
    def _get_rule_based_suggestions(self, 
                                  metrics: PerformanceMetrics) -> List[OptimizationSuggestion]:
        """Generate rule-based optimization suggestions."""
        suggestions = []
        
        # Position sizing suggestion
        if metrics.kelly_criterion < 0.05:
            suggestions.append(OptimizationSuggestion(
                category="position_sizing",
                priority="HIGH",
                suggestion="Increase position sizes based on Kelly Criterion",
                expected_impact="Higher returns with controlled risk",
                implementation_steps=[
                    "Calculate Kelly percentage for each trade",
                    "Start with 50% of Kelly for safety",
                    "Gradually increase as confidence grows"
                ],
                confidence=0.7
            ))
        
        # Risk management suggestion
        if metrics.max_drawdown > RISK_THRESHOLDS['max_drawdown_critical']:
            suggestions.append(OptimizationSuggestion(
                category="risk_management",
                priority="HIGH",
                suggestion="Implement dynamic position sizing based on drawdown",
                expected_impact="Reduced maximum drawdown by 30-40%",
                implementation_steps=[
                    "Reduce position size by 50% after 10% drawdown",
                    "Further reduce by 25% after 15% drawdown",
                    "Return to normal sizing after recovery"
                ],
                confidence=0.8
            ))
        
        return suggestions
    
    def _merge_and_prioritize_suggestions(self,
                                        ai_suggestions: List[OptimizationSuggestion],
                                        rule_suggestions: List[OptimizationSuggestion]) -> List[OptimizationSuggestion]:
        """Merge and prioritize all suggestions."""
        all_suggestions = ai_suggestions + rule_suggestions
        
        # Sort by priority and confidence
        priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
        all_suggestions.sort(
            key=lambda s: (priority_order.get(s.priority, 3), -s.confidence)
        )
        
        # Remove duplicates (keep highest confidence)
        seen = set()
        unique_suggestions = []
        for suggestion in all_suggestions:
            key = (suggestion.category, suggestion.suggestion[:50])
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions[:10]  # Top 10 suggestions
    
    def _calculate_var(self, trades: List[Trade], confidence: float = 0.95) -> float:
        """Calculate Value at Risk."""
        returns = [t.pnl for t in trades if t.pnl is not None]
        if not returns:
            return 0.0
        
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return sorted_returns[index] if index < len(sorted_returns) else sorted_returns[0]
    
    def _create_empty_metrics(self, period: TimePeriod) -> PerformanceMetrics:
        """Create empty metrics object."""
        return PerformanceMetrics(
            period=period,
            start_date=datetime.now(),
            end_date=datetime.now(),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_return=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            max_drawdown=0,
            win_rate=0,
            profit_factor=0,
            average_win=0,
            average_loss=0,
            expectancy=0,
            kelly_criterion=0
        )
    
    def _create_empty_report(self, period: TimePeriod) -> PerformanceReport:
        """Create empty performance report."""
        return PerformanceReport(
            metrics=self._create_empty_metrics(period),
            category=PerformanceCategory.POOR,
            strengths=[],
            weaknesses=["No trades to analyze"],
            recommendations=["Start trading to generate performance data"],
            ai_insights={},
            risk_assessment={'risk_level': 'UNKNOWN', 'risk_score': 0}
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_performance_analytics_agent(model_name: str = DEFAULT_MODEL,
                                     temperature: float = DEFAULT_TEMPERATURE) -> SpyderX08_PerformanceAnalyticsAgent:
    """
    Factory function to create Performance Analytics Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX08_PerformanceAnalyticsAgent instance
    """
    return SpyderX08_PerformanceAnalyticsAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX08_PerformanceAnalyticsAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_performance_analytics_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_performance_agent():
    """Test the Performance Analytics Agent functionality."""
    print("="*80)
    print("Testing SpyderX08_PerformanceAnalyticsAgent")
    print("="*80)
    
    agent = create_performance_analytics_agent()
    
    # Create sample trades
    sample_trades = [
        Trade(
            id="T001",
            symbol="SPY",
            entry_time=datetime.now() - timedelta(days=30),
            exit_time=datetime.now() - timedelta(days=29),
            entry_price=450.00,
            exit_price=452.50,
            quantity=10,
            side="LONG",
            pnl=250.00,
            strategy="Momentum"
        ),
        Trade(
            id="T002",
            symbol="SPY",
            entry_time=datetime.now() - timedelta(days=25),
            exit_time=datetime.now() - timedelta(days=24),
            entry_price=451.00,
            exit_price=449.50,
            quantity=10,
            side="LONG",
            pnl=-150.00,
            strategy="Momentum"
        ),
        Trade(
            id="T003",
            symbol="SPY",
            entry_time=datetime.now() - timedelta(days=20),
            exit_time=datetime.now() - timedelta(days=19),
            entry_price=448.00,
            exit_price=451.00,
            quantity=15,
            side="LONG",
            pnl=450.00,
            strategy="MeanReversion"
        ),
        Trade(
            id="T004",
            symbol="SPY",
            entry_time=datetime.now() - timedelta(days=15),
            exit_time=datetime.now() - timedelta(days=14),
            entry_price=452.00,
            exit_price=451.00,
            quantity=10,
            side="SHORT",
            pnl=100.00,
            strategy="MeanReversion"
        ),
        Trade(
            id="T005",
            symbol="SPY",
            entry_time=datetime.now() - timedelta(days=10),
            exit_time=datetime.now() - timedelta(days=9),
            entry_price=450.00,
            exit_price=448.00,
            quantity=20,
            side="LONG",
            pnl=-400.00,
            strategy="Breakout"
        )
    ]
    
    # Test performance analysis
    print("\nTest 1: Overall Performance Analysis")
    print("-"*40)
    
    report = await agent.analyze_performance(sample_trades, TimePeriod.ALL_TIME)
    
    print(f"Performance Category: {report.category.value}")
    print(f"\nMetrics:")
    print(f"  Total Trades: {report.metrics.total_trades}")
    print(f"  Win Rate: {report.metrics.win_rate:.1%}")
    print(f"  Total Return: ${report.metrics.total_return:.2f}")
    print(f"  Sharpe Ratio: {report.metrics.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {report.metrics.max_drawdown:.1%}")
    print(f"  Profit Factor: {report.metrics.profit_factor:.2f}")
    
    print(f"\nStrengths:")
    for strength in report.strengths:
        print(f"  - {strength}")
    
    print(f"\nWeaknesses:")
    for weakness in report.weaknesses:
        print(f"  - {weakness}")
    
    print(f"\nRecommendations:")
    for rec in report.recommendations[:3]:
        print(f"  - {rec}")
    
    # Test optimization suggestions
    print("\n\nTest 2: Optimization Suggestions")
    print("-"*40)
    
    suggestions = await agent.get_optimization_suggestions(
        report.metrics, sample_trades
    )
    
    for i, suggestion in enumerate(suggestions[:3], 1):
        print(f"\nSuggestion {i}:")
        print(f"  Category: {suggestion.category}")
        print(f"  Priority: {suggestion.priority}")
        print(f"  Suggestion: {suggestion.suggestion}")
        print(f"  Expected Impact: {suggestion.expected_impact}")
        print(f"  Confidence: {suggestion.confidence:.1%}")
    
    # Test risk assessment
    print("\n\nTest 3: Risk Assessment")
    print("-"*40)
    
    risk = report.risk_assessment
    print(f"Risk Level: {risk['risk_level']}")
    print(f"Risk Score: {risk['risk_score']}")
    print(f"Risk Factors:")
    for factor in risk.get('risk_factors', []):
        print(f"  - {factor}")
    print(f"Recommended Position Size: {risk.get('recommended_position_size', 0):.1%}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_performance_agent())
    
    print("\n" + "="*80)
    print("SpyderX08_PerformanceAnalyticsAgent module loaded successfully!")
    print("="*80)