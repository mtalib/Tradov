#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX08_PerformanceAnalyticsAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Performance Analytics and Reporting

Description:
    This agent provides deep performance insights using AI to analyze trading
    results, identify patterns in wins/losses, and generate natural language
    reports. It goes beyond traditional metrics to provide actionable insights
    for strategy improvement, risk adjustment, and portfolio optimization.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-17
Last Updated: 2025-01-28 Time: 18:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU11_FeatureFlags import is_spyderx_enabled, SPYDERX_FEATURE_FLAGS
from SpyderM_Monitoring.SpyderM04_TradingMetrics import TradingMetrics
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model configuration
DEFAULT_MODEL = "llama3" if OLLAMA_AVAILABLE else None
DEFAULT_TEMPERATURE = 0.3  # Low temperature for accurate analysis

# Performance thresholds
MIN_SHARPE_RATIO = 1.0
MIN_WIN_RATE = 0.45
MAX_DRAWDOWN_ACCEPTABLE = 0.15
MIN_PROFIT_FACTOR = 1.2

# Analysis periods
ANALYSIS_WINDOWS = [5, 20, 60, 252]  # Days: Week, Month, Quarter, Year
ROLLING_WINDOW = 20  # Default rolling window

# Report configuration
MAX_REPORT_LENGTH = 5000  # Characters
INSIGHT_CONFIDENCE_THRESHOLD = 0.7

# ==============================================================================
# ENUMS
# ==============================================================================
class PerformanceMetric(Enum):
    """Performance metric types"""
    RETURN = "return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    CALMAR_RATIO = "calmar_ratio"
    INFORMATION_RATIO = "information_ratio"

class AnalysisType(Enum):
    """Types of performance analysis"""
    ATTRIBUTION = "attribution"
    REGIME = "regime"
    FACTOR = "factor"
    BEHAVIORAL = "behavioral"
    RISK_ADJUSTED = "risk_adjusted"

class ReportFormat(Enum):
    """Report format types"""
    EXECUTIVE_SUMMARY = "executive_summary"
    DETAILED_ANALYSIS = "detailed_analysis"
    TECHNICAL_REPORT = "technical_report"
    VISUAL_DASHBOARD = "visual_dashboard"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PerformanceData:
    """Container for performance data"""
    returns: pd.Series
    trades: List[Dict[str, Any]]
    positions: pd.DataFrame
    equity_curve: pd.Series
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceAnalysis:
    """Comprehensive performance analysis result"""
    metrics: Dict[str, float]
    attribution: Dict[str, Any]
    regime_analysis: Dict[str, Any]
    factor_analysis: Dict[str, Any]
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    recommendations: List[Dict[str, Any]]
    natural_language_summary: str
    confidence_scores: Dict[str, float]

@dataclass
class AttributionResult:
    """Performance attribution analysis"""
    strategy_attribution: Dict[str, float]
    timeframe_attribution: Dict[str, float]
    asset_attribution: Dict[str, float]
    factor_attribution: Dict[str, float]
    residual: float

@dataclass
class RegimePerformance:
    """Performance by market regime"""
    regime_name: str
    period_count: int
    total_return: float
    avg_return: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float

@dataclass
class AIInsight:
    """AI-generated performance insight"""
    category: str
    finding: str
    impact: str
    recommendation: str
    confidence: float
    supporting_data: Dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX08_PerformanceAnalyticsAgent:
    """
    AI-Enhanced Performance Analytics Agent.
    
    This agent provides deep performance analysis using AI to identify patterns,
    generate insights, and create actionable recommendations. It combines
    traditional performance metrics with advanced AI analysis for comprehensive
    portfolio evaluation.
    
    Attributes:
        model_name: Ollama model for AI analysis
        temperature: Temperature setting for AI responses
        metrics_calculator: Traditional metrics calculator
        analysis_cache: Cache for analysis results
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the Performance Analytics Agent"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.model_name = model_name
        self.temperature = temperature
        
        # Initialize components
        self.metrics_calculator = PerformanceMetrics()
        self.trading_metrics = TradingMetrics()
        
        # Analysis cache
        self.analysis_cache = {}
        self.cache_timestamps = {}
        
        # Historical analyses for trend detection
        self.analysis_history = deque(maxlen=100)
        
        # Performance tracking
        self.agent_metrics = {
            'analyses_performed': 0,
            'reports_generated': 0,
            'ai_queries': 0,
            'insights_generated': 0,
            'avg_confidence': 0.0
        }
        
        self.logger.info(f"Performance Analytics Agent initialized with model: {model_name}")
    
    # ==========================================================================
    # PUBLIC METHODS - MAIN FUNCTIONALITY
    # ==========================================================================
    async def analyze_performance(
        self,
        performance_data: PerformanceData,
        benchmark_data: Optional[pd.Series] = None,
        analysis_types: Optional[List[AnalysisType]] = None
    ) -> PerformanceAnalysis:
        """
        Perform comprehensive AI-enhanced performance analysis.
        
        Args:
            performance_data: Trading performance data
            benchmark_data: Benchmark returns for comparison
            analysis_types: Specific analyses to perform
            
        Returns:
            PerformanceAnalysis with AI insights
        """
        try:
            # Default to all analysis types
            if analysis_types is None:
                analysis_types = list(AnalysisType)
            
            # Calculate base metrics
            metrics = self._calculate_comprehensive_metrics(
                performance_data, benchmark_data
            )
            
            # Perform attribution analysis
            attribution = None
            if AnalysisType.ATTRIBUTION in analysis_types:
                attribution = await self._perform_attribution_analysis(
                    performance_data
                )
            
            # Perform regime analysis
            regime_analysis = None
            if AnalysisType.REGIME in analysis_types:
                regime_analysis = await self._perform_regime_analysis(
                    performance_data
                )
            
            # Perform factor analysis
            factor_analysis = None
            if AnalysisType.FACTOR in analysis_types:
                factor_analysis = await self._perform_factor_analysis(
                    performance_data
                )
            
            # Get AI-enhanced insights
            if is_spyderx_enabled("USE_AI_ANALYTICS") and OLLAMA_AVAILABLE:
                analysis = await self._enhance_with_ai_analysis(
                    metrics, attribution, regime_analysis, 
                    factor_analysis, performance_data
                )
            else:
                # Fallback to rule-based analysis
                analysis = self._create_rule_based_analysis(
                    metrics, attribution, regime_analysis, factor_analysis
                )
            
            # Store in history
            self.analysis_history.append({
                'timestamp': datetime.now(),
                'metrics': metrics,
                'analysis': analysis
            })
            
            # Update agent metrics
            self._update_agent_metrics(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Performance analysis failed: {e}")
            return self._create_error_analysis(str(e))
    
    async def generate_performance_report(
        self,
        analysis: PerformanceAnalysis,
        report_format: ReportFormat = ReportFormat.EXECUTIVE_SUMMARY,
        custom_sections: Optional[List[str]] = None
    ) -> str:
        """
        Generate natural language performance report.
        
        Args:
            analysis: Completed performance analysis
            report_format: Type of report to generate
            custom_sections: Additional sections to include
            
        Returns:
            Formatted performance report
        """
        try:
            # Base report sections
            report_sections = []
            
            # Executive summary
            if report_format == ReportFormat.EXECUTIVE_SUMMARY:
                summary = await self._generate_executive_summary(analysis)
                report_sections.append(summary)
            
            # Detailed sections
            elif report_format == ReportFormat.DETAILED_ANALYSIS:
                report_sections.extend([
                    await self._generate_metrics_section(analysis),
                    await self._generate_attribution_section(analysis),
                    await self._generate_regime_section(analysis),
                    await self._generate_recommendations_section(analysis)
                ])
            
            # Technical report
            elif report_format == ReportFormat.TECHNICAL_REPORT:
                report_sections.extend([
                    await self._generate_technical_summary(analysis),
                    await self._generate_statistical_analysis(analysis),
                    await self._generate_risk_analysis(analysis)
                ])
            
            # Add custom sections
            if custom_sections:
                for section in custom_sections:
                    custom_content = await self._generate_custom_section(
                        section, analysis
                    )
                    report_sections.append(custom_content)
            
            # Combine sections
            report = "\n\n".join(report_sections)
            
            # Ensure report length
            if len(report) > MAX_REPORT_LENGTH:
                report = await self._summarize_report(report)
            
            self.agent_metrics['reports_generated'] += 1
            
            return report
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            return f"Error generating report: {str(e)}"
    
    async def identify_performance_patterns(
        self,
        performance_history: List[PerformanceData],
        pattern_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify patterns in historical performance using AI.
        
        Args:
            performance_history: Historical performance data
            pattern_types: Specific patterns to look for
            
        Returns:
            List of identified patterns with insights
        """
        try:
            patterns = []
            
            # Time-based patterns
            time_patterns = self._identify_time_patterns(performance_history)
            patterns.extend(time_patterns)
            
            # Strategy patterns
            strategy_patterns = self._identify_strategy_patterns(performance_history)
            patterns.extend(strategy_patterns)
            
            # Market condition patterns
            market_patterns = await self._identify_market_patterns(performance_history)
            patterns.extend(market_patterns)
            
            # AI pattern enhancement
            if is_spyderx_enabled("USE_AI_ANALYTICS") and OLLAMA_AVAILABLE:
                ai_patterns = await self._ai_pattern_discovery(
                    performance_history, patterns
                )
                patterns.extend(ai_patterns)
            
            # Filter by requested types
            if pattern_types:
                patterns = [p for p in patterns if p['type'] in pattern_types]
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Pattern identification failed: {e}")
            return []
    
    async def generate_improvement_recommendations(
        self,
        current_performance: PerformanceAnalysis,
        historical_analyses: Optional[List[PerformanceAnalysis]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate AI-powered improvement recommendations.
        
        Args:
            current_performance: Current performance analysis
            historical_analyses: Historical analyses for trend detection
            
        Returns:
            List of actionable recommendations
        """
        try:
            recommendations = []
            
            # Analyze weaknesses
            for weakness in current_performance.weaknesses:
                rec = await self._generate_weakness_recommendation(
                    weakness, current_performance
                )
                if rec:
                    recommendations.append(rec)
            
            # Identify optimization opportunities
            opportunities = await self._identify_optimization_opportunities(
                current_performance, historical_analyses
            )
            recommendations.extend(opportunities)
            
            # AI-enhanced recommendations
            if is_spyderx_enabled("USE_AI_ANALYTICS") and OLLAMA_AVAILABLE:
                ai_recommendations = await self._generate_ai_recommendations(
                    current_performance, historical_analyses
                )
                recommendations.extend(ai_recommendations)
            
            # Prioritize recommendations
            prioritized = self._prioritize_recommendations(
                recommendations, current_performance
            )
            
            return prioritized[:10]  # Top 10 recommendations
            
        except Exception as e:
            self.logger.error(f"Recommendation generation failed: {e}")
            return []
    
    # ==========================================================================
    # PRIVATE METHODS - METRICS CALCULATION
    # ==========================================================================
    def _calculate_comprehensive_metrics(
        self,
        performance_data: PerformanceData,
        benchmark_data: Optional[pd.Series] = None
    ) -> Dict[str, float]:
        """Calculate all performance metrics"""
        returns = performance_data.returns
        
        metrics = {
            # Basic metrics
            'total_return': self.metrics_calculator.total_return(returns),
            'annual_return': self.metrics_calculator.annual_return(returns),
            'volatility': self.metrics_calculator.volatility(returns),
            
            # Risk-adjusted metrics
            'sharpe_ratio': self.metrics_calculator.sharpe_ratio(returns),
            'sortino_ratio': self.metrics_calculator.sortino_ratio(returns),
            'calmar_ratio': self.metrics_calculator.calmar_ratio(returns),
            
            # Drawdown metrics
            'max_drawdown': self.metrics_calculator.max_drawdown(returns),
            'avg_drawdown': self._calculate_average_drawdown(returns),
            'drawdown_duration': self._calculate_max_drawdown_duration(returns),
            
            # Trade metrics
            'win_rate': self._calculate_win_rate(performance_data.trades),
            'profit_factor': self._calculate_profit_factor(performance_data.trades),
            'avg_win_loss_ratio': self._calculate_win_loss_ratio(performance_data.trades),
            
            # Risk metrics
            'var_95': self._calculate_var(returns, 0.95),
            'cvar_95': self._calculate_cvar(returns, 0.95),
            'downside_deviation': self._calculate_downside_deviation(returns),
            
            # Consistency metrics
            'positive_months': self._calculate_positive_periods(returns, 'M'),
            'longest_winning_streak': self._calculate_longest_streak(performance_data.trades, True),
            'longest_losing_streak': self._calculate_longest_streak(performance_data.trades, False)
        }
        
        # Benchmark relative metrics
        if benchmark_data is not None:
            metrics.update({
                'alpha': self._calculate_alpha(returns, benchmark_data),
                'beta': self._calculate_beta(returns, benchmark_data),
                'information_ratio': self._calculate_information_ratio(returns, benchmark_data),
                'tracking_error': self._calculate_tracking_error(returns, benchmark_data)
            })
        
        return metrics
    
    # ==========================================================================
    # PRIVATE METHODS - ATTRIBUTION ANALYSIS
    # ==========================================================================
    async def _perform_attribution_analysis(
        self,
        performance_data: PerformanceData
    ) -> AttributionResult:
        """Perform performance attribution analysis"""
        trades = performance_data.trades
        
        # Strategy attribution
        strategy_attribution = defaultdict(float)
        for trade in trades:
            strategy = trade.get('strategy', 'unknown')
            pnl = trade.get('pnl', 0)
            strategy_attribution[strategy] += pnl
        
        # Normalize to percentages
        total_pnl = sum(strategy_attribution.values())
        if total_pnl != 0:
            strategy_attribution = {
                k: v/total_pnl for k, v in strategy_attribution.items()
            }
        
        # Time-based attribution
        timeframe_attribution = self._calculate_timeframe_attribution(trades)
        
        # Asset attribution (for multi-asset portfolios)
        asset_attribution = self._calculate_asset_attribution(trades)
        
        # Factor attribution (if factor data available)
        factor_attribution = await self._calculate_factor_attribution(
            performance_data
        )
        
        # Calculate residual
        residual = 1.0 - sum([
            sum(strategy_attribution.values()),
            sum(timeframe_attribution.values()),
            sum(asset_attribution.values()),
            sum(factor_attribution.values())
        ]) / 4  # Average of attributions
        
        return AttributionResult(
            strategy_attribution=dict(strategy_attribution),
            timeframe_attribution=timeframe_attribution,
            asset_attribution=asset_attribution,
            factor_attribution=factor_attribution,
            residual=residual
        )
    
    # ==========================================================================
    # PRIVATE METHODS - AI ENHANCEMENT
    # ==========================================================================
    async def _enhance_with_ai_analysis(
        self,
        metrics: Dict[str, float],
        attribution: Optional[AttributionResult],
        regime_analysis: Optional[Dict[str, Any]],
        factor_analysis: Optional[Dict[str, Any]],
        performance_data: PerformanceData
    ) -> PerformanceAnalysis:
        """Enhance analysis with AI insights"""
        try:
            # Prepare context for AI
            context = {
                'metrics': metrics,
                'attribution': attribution.__dict__ if attribution else {},
                'regime_analysis': regime_analysis or {},
                'factor_analysis': factor_analysis or {},
                'trade_count': len(performance_data.trades),
                'period': f"{performance_data.returns.index[0]} to {performance_data.returns.index[-1]}"
            }
            
            # Query AI for insights
            prompt = self._construct_analysis_prompt(context)
            response = await self._query_ai_model(prompt)
            
            # Parse AI response
            ai_insights = self._parse_ai_analysis(response)
            
            # Extract key findings
            strengths = ai_insights.get('strengths', [])
            weaknesses = ai_insights.get('weaknesses', [])
            opportunities = ai_insights.get('opportunities', [])
            
            # Generate recommendations
            recommendations = await self._generate_ai_recommendations_from_insights(
                ai_insights, metrics, performance_data
            )
            
            # Build confidence scores
            confidence_scores = self._calculate_confidence_scores(
                ai_insights, metrics
            )
            
            analysis = PerformanceAnalysis(
                metrics=metrics,
                attribution=attribution.__dict__ if attribution else {},
                regime_analysis=regime_analysis or {},
                factor_analysis=factor_analysis or {},
                strengths=strengths[:5],  # Top 5
                weaknesses=weaknesses[:5],
                opportunities=opportunities[:5],
                recommendations=recommendations,
                natural_language_summary=ai_insights.get('summary', ''),
                confidence_scores=confidence_scores
            )
            
            self.agent_metrics['ai_queries'] += 1
            self.agent_metrics['insights_generated'] += len(strengths) + len(weaknesses)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"AI analysis enhancement failed: {e}")
            # Fallback to rule-based
            return self._create_rule_based_analysis(
                metrics, attribution, regime_analysis, factor_analysis
            )
    
    async def _query_ai_model(self, prompt: str) -> str:
        """Query the AI model for analysis"""
        if not OLLAMA_AVAILABLE:
            return ""
            
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert quantitative analyst and portfolio manager.
                        Analyze performance data to provide actionable insights.
                        Focus on identifying patterns, strengths, weaknesses, and specific improvements.
                        Be precise with numbers and provide concrete recommendations."""
                    },
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": self.temperature}
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"AI model query failed: {e}")
            return ""
    
    def _construct_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Construct prompt for AI performance analysis"""
        metrics = context['metrics']
        
        return f"""Analyze the following trading performance data:

Key Metrics:
- Total Return: {metrics.get('total_return', 0):.2%}
- Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}
- Max Drawdown: {metrics.get('max_drawdown', 0):.2%}
- Win Rate: {metrics.get('win_rate', 0):.2%}
- Profit Factor: {metrics.get('profit_factor', 0):.2f}

Attribution Analysis:
{json.dumps(context.get('attribution', {}), indent=2)}

Trading Period: {context.get('period', 'Unknown')}
Total Trades: {context.get('trade_count', 0)}

Provide:
1. Top 5 performance strengths
2. Top 5 weaknesses or areas of concern
3. Top 5 opportunities for improvement
4. Specific actionable recommendations
5. Overall assessment summary (100-150 words)
6. Confidence level in each finding (0-1)

Format response as JSON with keys: strengths, weaknesses, opportunities, 
recommendations, summary, confidence_scores"""
    
    # ==========================================================================
    # PRIVATE METHODS - REPORT GENERATION
    # ==========================================================================
    async def _generate_executive_summary(
        self,
        analysis: PerformanceAnalysis
    ) -> str:
        """Generate executive summary report"""
        metrics = analysis.metrics
        
        summary = f"""# PERFORMANCE EXECUTIVE SUMMARY

## Overview
{analysis.natural_language_summary}

## Key Performance Indicators
- **Total Return**: {metrics.get('total_return', 0):.2%}
- **Sharpe Ratio**: {metrics.get('sharpe_ratio', 0):.2f}
- **Maximum Drawdown**: {metrics.get('max_drawdown', 0):.2%}
- **Win Rate**: {metrics.get('win_rate', 0):.2%}

## Strengths
{self._format_list(analysis.strengths)}

## Areas for Improvement
{self._format_list(analysis.weaknesses)}

## Recommendations
{self._format_recommendations(analysis.recommendations[:3])}

## Risk Assessment
- Value at Risk (95%): {metrics.get('var_95', 0):.2%}
- Downside Deviation: {metrics.get('downside_deviation', 0):.2%}
- Longest Losing Streak: {metrics.get('longest_losing_streak', 0)} trades

*Generated by AI Performance Analytics on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
        return summary
    
    def _format_list(self, items: List[str]) -> str:
        """Format list items for report"""
        if not items:
            return "- No items identified"
        return "\n".join([f"- {item}" for item in items])
    
    def _format_recommendations(self, recommendations: List[Dict[str, Any]]) -> str:
        """Format recommendations for report"""
        if not recommendations:
            return "No recommendations at this time."
        
        formatted = []
        for i, rec in enumerate(recommendations, 1):
            formatted.append(
                f"{i}. **{rec.get('title', 'Recommendation')}**\n"
                f"   {rec.get('description', '')}\n"
                f"   *Expected Impact*: {rec.get('impact', 'Moderate')}\n"
            )
        
        return "\n".join(formatted)
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _calculate_win_rate(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate win rate from trades"""
        if not trades:
            return 0.0
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return wins / len(trades)
    
    def _calculate_profit_factor(self, trades: List[Dict[str, Any]]) -> float:
        """Calculate profit factor"""
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def _calculate_confidence_scores(
        self,
        ai_insights: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate confidence scores for various aspects"""
        confidence_scores = ai_insights.get('confidence_scores', {})
        
        # Add metric-based confidence
        if metrics.get('trade_count', 0) < 30:
            confidence_scores['statistical_significance'] = 0.5
        else:
            confidence_scores['statistical_significance'] = min(
                0.95, 0.5 + metrics.get('trade_count', 0) / 200
            )
        
        # Data quality confidence
        confidence_scores['data_quality'] = 0.9  # Assume good quality
        
        # Overall confidence
        if confidence_scores:
            confidence_scores['overall'] = np.mean(list(confidence_scores.values()))
        else:
            confidence_scores['overall'] = 0.7
        
        return confidence_scores
    
    def _update_agent_metrics(self, analysis: PerformanceAnalysis) -> None:
        """Update agent performance metrics"""
        self.agent_metrics['analyses_performed'] += 1
        
        # Update average confidence
        avg_conf = self.agent_metrics['avg_confidence']
        new_conf = analysis.confidence_scores.get('overall', 0.7)
        n = self.agent_metrics['analyses_performed']
        
        self.agent_metrics['avg_confidence'] = (
            (avg_conf * (n - 1) + new_conf) / n
        )
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return self.agent_metrics.copy()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_performance_analytics_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE
) -> SpyderX08_PerformanceAnalyticsAgent:
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