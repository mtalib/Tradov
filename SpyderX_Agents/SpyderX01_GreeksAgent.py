#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderX01_GreeksAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Greeks Calculation and Analysis Agent

Description:
    This agent augments the traditional Greeks calculation modules with AI-powered
    analysis and interpretation. It provides intelligent risk assessment, position
    recommendations, and real-time Greeks monitoring with natural language explanations.
    The agent integrates with existing SpyderF06_GreeksCalculator and SpyderE06_GreeksManager
    modules to enhance their functionality with AI capabilities.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-27 
Last Updated: 2025-01-27 Time: 16:30  
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from functools import lru_cache

# AI/ML imports (placeholder for actual implementations)
# These would be replaced with actual AI framework imports
# import ollama  # For LLM integration
# import langchain  # For agent orchestration

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities import SpyderLogger, get_logger

# ==============================================================================
# CONSTANTS
# ==============================================================================
# AI Model Configuration
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.7
MAX_TOKENS = 2048

# Greeks Thresholds
DELTA_THRESHOLD = 0.5
GAMMA_THRESHOLD = 0.1
THETA_THRESHOLD = -50
VEGA_THRESHOLD = 100

# Risk Levels
RISK_LEVELS = {
    'LOW': 0,
    'MEDIUM': 1,
    'HIGH': 2,
    'CRITICAL': 3
}

# ==============================================================================
# ENUMS
# ==============================================================================
class AnalysisMode(Enum):
    """Analysis modes for the Greeks agent"""
    QUICK = "quick"
    DETAILED = "detailed"
    PORTFOLIO = "portfolio"
    REAL_TIME = "real_time"

class RecommendationType(Enum):
    """Types of recommendations the agent can make"""
    HEDGE = "hedge"
    ADJUST = "adjust"
    CLOSE = "close"
    HOLD = "hold"
    MONITOR = "monitor"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GreeksData:
    """Greeks data structure"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float
    underlying_price: float
    option_price: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class GreeksAnalysis:
    """AI-enhanced Greeks analysis result"""
    greeks_data: GreeksData
    risk_score: int
    risk_assessment: str
    recommendations: List[str]
    natural_language_summary: str
    hedge_suggestions: Optional[List[Dict[str, Any]]] = None
    confidence_score: float = 0.0
    analysis_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioGreeksAnalysis:
    """Portfolio-level Greeks analysis"""
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    portfolio_risk_score: int
    position_correlations: Dict[str, float]
    recommendations: List[str]
    natural_language_summary: str
    rebalancing_suggestions: Optional[List[Dict[str, Any]]] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX01_GreeksAgent:
    """
    AI-Enhanced Greeks Analysis Agent.
    
    This agent provides intelligent analysis of option Greeks using AI/ML
    capabilities to augment traditional calculations with actionable insights.
    
    Attributes:
        logger: Module logger instance
        config: Agent configuration
        analysis_history: History of analyses performed
        
    Example:
        >>> agent = SpyderX01_GreeksAgent()
        >>> analysis = await agent.analyze_greeks(greeks_data)
        >>> print(analysis.natural_language_summary)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Greeks Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = get_logger(__name__)
        self.config = config or self._get_default_config()
        
        # Initialize components
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        
        # Analysis tracking
        self.analysis_history: List[GreeksAnalysis] = []
        self.performance_metrics = {
            'total_analyses': 0,
            'avg_response_time': 0,
            'accuracy_score': 0
        }
        
        # Cache for repeated analyses
        self._analysis_cache = {}
        
        self.logger.info(f"{self.__class__.__name__} initialized with model: {self.model_name}")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    
    async def analyze_greeks(
        self, 
        greeks_data: GreeksData,
        mode: AnalysisMode = AnalysisMode.DETAILED,
        market_context: Optional[Dict[str, Any]] = None
    ) -> GreeksAnalysis:
        """
        Analyze option Greeks with AI enhancement.
        
        Args:
            greeks_data: Greeks data to analyze
            mode: Analysis mode
            market_context: Optional market context
            
        Returns:
            AI-enhanced Greeks analysis
        """
        start_time = time.time()
        
        try:
            # Check cache
            cache_key = self._generate_cache_key(greeks_data, mode)
            if cache_key in self._analysis_cache:
                self.logger.debug(f"Returning cached analysis for {greeks_data.symbol}")
                return self._analysis_cache[cache_key]
            
            # Perform risk assessment
            risk_score = self._calculate_risk_score(greeks_data)
            
            # Generate AI analysis
            risk_assessment = await self._generate_risk_assessment(
                greeks_data, risk_score, market_context
            )
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                greeks_data, risk_score, mode
            )
            
            # Generate natural language summary
            summary = await self._generate_summary(
                greeks_data, risk_assessment, recommendations
            )
            
            # Generate hedge suggestions if needed
            hedge_suggestions = None
            if risk_score >= RISK_LEVELS['HIGH']:
                hedge_suggestions = await self._generate_hedge_suggestions(greeks_data)
            
            # Create analysis result
            analysis = GreeksAnalysis(
                greeks_data=greeks_data,
                risk_score=risk_score,
                risk_assessment=risk_assessment,
                recommendations=recommendations,
                natural_language_summary=summary,
                hedge_suggestions=hedge_suggestions,
                confidence_score=self._calculate_confidence_score(greeks_data)
            )
            
            # Update cache and history
            self._analysis_cache[cache_key] = analysis
            self.analysis_history.append(analysis)
            
            # Update metrics
            self._update_metrics(time.time() - start_time)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing Greeks: {str(e)}")
            raise
    
    async def analyze_portfolio_greeks(
        self,
        positions: List[GreeksData],
        market_context: Optional[Dict[str, Any]] = None
    ) -> PortfolioGreeksAnalysis:
        """
        Analyze portfolio-level Greeks.
        
        Args:
            positions: List of position Greeks
            market_context: Optional market context
            
        Returns:
            Portfolio-level Greeks analysis
        """
        try:
            # Calculate aggregate Greeks
            total_delta = sum(pos.delta for pos in positions)
            total_gamma = sum(pos.gamma for pos in positions)
            total_theta = sum(pos.theta for pos in positions)
            total_vega = sum(pos.vega for pos in positions)
            
            # Calculate portfolio risk score
            portfolio_risk_score = self._calculate_portfolio_risk_score(
                total_delta, total_gamma, total_theta, total_vega
            )
            
            # Calculate position correlations
            correlations = self._calculate_position_correlations(positions)
            
            # Generate recommendations
            recommendations = await self._generate_portfolio_recommendations(
                positions, portfolio_risk_score, market_context
            )
            
            # Generate summary
            summary = await self._generate_portfolio_summary(
                total_delta, total_gamma, total_theta, total_vega,
                portfolio_risk_score, len(positions)
            )
            
            # Generate rebalancing suggestions if needed
            rebalancing = None
            if portfolio_risk_score >= RISK_LEVELS['MEDIUM']:
                rebalancing = await self._generate_rebalancing_suggestions(positions)
            
            return PortfolioGreeksAnalysis(
                total_delta=total_delta,
                total_gamma=total_gamma,
                total_theta=total_theta,
                total_vega=total_vega,
                portfolio_risk_score=portfolio_risk_score,
                position_correlations=correlations,
                recommendations=recommendations,
                natural_language_summary=summary,
                rebalancing_suggestions=rebalancing
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing portfolio Greeks: {str(e)}")
            raise
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Returns:
            Performance metrics dictionary
        """
        return self.performance_metrics.copy()
    
    # ==========================================================================
    # PRIVATE METHODS - RISK CALCULATIONS
    # ==========================================================================
    
    def _calculate_risk_score(self, greeks_data: GreeksData) -> int:
        """Calculate risk score based on Greeks values."""
        risk_score = 0
        
        # Delta risk
        if abs(greeks_data.delta) > DELTA_THRESHOLD:
            risk_score += 1
        
        # Gamma risk
        if abs(greeks_data.gamma) > GAMMA_THRESHOLD:
            risk_score += 2
        
        # Theta risk (decay)
        if greeks_data.theta < THETA_THRESHOLD:
            risk_score += 1
        
        # Vega risk
        if abs(greeks_data.vega) > VEGA_THRESHOLD:
            risk_score += 1
        
        # Time to expiry risk
        days_to_expiry = (greeks_data.expiry - datetime.now()).days
        if days_to_expiry < 7:
            risk_score += 2
        elif days_to_expiry < 14:
            risk_score += 1
        
        return min(risk_score, RISK_LEVELS['CRITICAL'])
    
    def _calculate_portfolio_risk_score(
        self, 
        total_delta: float,
        total_gamma: float,
        total_theta: float,
        total_vega: float
    ) -> int:
        """Calculate portfolio-level risk score."""
        risk_score = 0
        
        # Portfolio Greeks thresholds (scaled up)
        if abs(total_delta) > DELTA_THRESHOLD * 10:
            risk_score += 2
        if abs(total_gamma) > GAMMA_THRESHOLD * 10:
            risk_score += 2
        if total_theta < THETA_THRESHOLD * 10:
            risk_score += 1
        if abs(total_vega) > VEGA_THRESHOLD * 10:
            risk_score += 1
        
        return min(risk_score, RISK_LEVELS['CRITICAL'])
    
    def _calculate_confidence_score(self, greeks_data: GreeksData) -> float:
        """Calculate confidence score for the analysis."""
        # Simplified confidence calculation
        confidence = 0.95
        
        # Reduce confidence for extreme values
        if abs(greeks_data.delta) > 0.9:
            confidence -= 0.1
        if abs(greeks_data.gamma) > 0.5:
            confidence -= 0.1
        if greeks_data.implied_volatility > 1.0:
            confidence -= 0.15
        
        return max(0.5, confidence)
    
    def _calculate_position_correlations(self, positions: List[GreeksData]) -> Dict[str, float]:
        """Calculate correlations between positions."""
        # Simplified correlation calculation
        correlations = {}
        
        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions[i+1:], i+1):
                key = f"{pos1.symbol}_{pos2.symbol}"
                # Simplified correlation based on strike distance and type
                if pos1.option_type == pos2.option_type:
                    correlation = 0.8
                else:
                    correlation = -0.3
                
                correlations[key] = correlation
        
        return correlations
    
    # ==========================================================================
    # PRIVATE METHODS - AI GENERATION (MOCK IMPLEMENTATIONS)
    # ==========================================================================
    
    async def _generate_risk_assessment(
        self,
        greeks_data: GreeksData,
        risk_score: int,
        market_context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate AI risk assessment using Ollama."""
        try:
            import ollama
            
            risk_levels = {0: "Low", 1: "Medium", 2: "High", 3: "Critical"}
            risk_level = risk_levels.get(risk_score, "Unknown")
            
            prompt = f"""You are an expert options trader analyzing position risk.

Position Details:
- Symbol: {greeks_data.symbol}
- Strike: ${greeks_data.strike}
- Type: {greeks_data.option_type}
- Days to expiry: {(greeks_data.expiry - datetime.now()).days}

Greeks:
- Delta: {greeks_data.delta:.3f} (directional exposure)
- Gamma: {greeks_data.gamma:.3f} (delta change rate)
- Theta: {greeks_data.theta:.2f} (daily time decay)
- Vega: {greeks_data.vega:.2f} (volatility sensitivity)
- IV: {greeks_data.implied_volatility:.1%}

Risk Score: {risk_score}/3 ({risk_level})
{f"Market Context: {market_context}" if market_context else ""}

Provide a concise risk assessment in 3-4 bullet points. Focus on the most critical risks."""

            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.7,
                    'num_predict': 200,
                    'num_thread': 16
                }
            )
            
            return response['response']
            
        except Exception as e:
            self.logger.warning(f"Ollama not available, using mock: {e}")
            # Fallback to mock implementation
            risk_levels = {0: "Low", 1: "Medium", 2: "High", 3: "Critical"}
            risk_level = risk_levels.get(risk_score, "Unknown")
            
            assessment = f"Risk Level: {risk_level}\n"
            
            if abs(greeks_data.delta) > DELTA_THRESHOLD:
                assessment += f"- High directional exposure (Delta: {greeks_data.delta:.3f})\n"
            
            if abs(greeks_data.gamma) > GAMMA_THRESHOLD:
                assessment += f"- Significant gamma risk (Gamma: {greeks_data.gamma:.3f})\n"
            
            if greeks_data.theta < THETA_THRESHOLD:
                assessment += f"- High time decay (Theta: {greeks_data.theta:.2f})\n"
            
            if abs(greeks_data.vega) > VEGA_THRESHOLD:
                assessment += f"- High volatility exposure (Vega: {greeks_data.vega:.2f})\n"
            
            return assessment

    async def _generate_recommendations(
        self,
        greeks_data: GreeksData,
        risk_score: int,
        mode: AnalysisMode
    ) -> List[str]:
        """Generate trading recommendations."""
        recommendations = []
        
        # Delta hedging recommendation
        if abs(greeks_data.delta) > DELTA_THRESHOLD:
            if greeks_data.delta > 0:
                recommendations.append("Consider delta hedging by selling underlying or buying puts")
            else:
                recommendations.append("Consider delta hedging by buying underlying or buying calls")
        
        # Gamma risk recommendation
        if abs(greeks_data.gamma) > GAMMA_THRESHOLD:
            recommendations.append("High gamma exposure - consider gamma hedging with opposite options")
        
        # Time decay recommendation
        days_to_expiry = (greeks_data.expiry - datetime.now()).days
        if greeks_data.theta < THETA_THRESHOLD and days_to_expiry < 14:
            recommendations.append("Significant time decay approaching - consider rolling or closing position")
        
        # Volatility recommendation
        if abs(greeks_data.vega) > VEGA_THRESHOLD:
            recommendations.append("High vega exposure - monitor implied volatility closely")
        
        # General recommendation based on risk score
        if risk_score >= RISK_LEVELS['HIGH']:
            recommendations.append("Overall risk is high - immediate action recommended")
        elif risk_score == RISK_LEVELS['MEDIUM']:
            recommendations.append("Monitor position closely for changes")
        else:
            recommendations.append("Position within acceptable risk parameters")
        
        return recommendations
    
    async def _generate_summary(
        self,
        greeks_data: GreeksData,
        risk_assessment: str,
        recommendations: List[str]
    ) -> str:
        """Generate natural language summary."""
        # Mock implementation
        days_to_expiry = (greeks_data.expiry - datetime.now()).days
        
        summary = f"Analysis for {greeks_data.symbol} {greeks_data.option_type} option:\n\n"
        summary += f"Strike: ${greeks_data.strike}, Expiry: {days_to_expiry} days\n"
        summary += f"Current Price: ${greeks_data.option_price:.2f}, Underlying: ${greeks_data.underlying_price:.2f}\n\n"
        summary += risk_assessment + "\n"
        summary += "Key Recommendations:\n"
        for i, rec in enumerate(recommendations[:3], 1):
            summary += f"{i}. {rec}\n"
        
        return summary
    
    async def _generate_hedge_suggestions(self, greeks_data: GreeksData) -> List[Dict[str, Any]]:
        """Generate hedge suggestions."""
        suggestions = []
        
        # Delta hedge
        if abs(greeks_data.delta) > DELTA_THRESHOLD:
            suggestions.append({
                'type': 'delta_hedge',
                'action': 'sell' if greeks_data.delta > 0 else 'buy',
                'instrument': 'underlying',
                'quantity': abs(greeks_data.delta * 100),  # Per contract
                'rationale': 'Neutralize directional risk'
            })
        
        # Gamma hedge
        if abs(greeks_data.gamma) > GAMMA_THRESHOLD:
            opposite_type = 'put' if greeks_data.option_type == 'call' else 'call'
            suggestions.append({
                'type': 'gamma_hedge',
                'action': 'buy',
                'instrument': f'{opposite_type} option',
                'strike': greeks_data.strike,
                'rationale': 'Reduce gamma exposure'
            })
        
        return suggestions
    
    async def _generate_portfolio_recommendations(
        self,
        positions: List[GreeksData],
        risk_score: int,
        market_context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate portfolio-level recommendations."""
        recommendations = []
        
        if risk_score >= RISK_LEVELS['HIGH']:
            recommendations.append("Portfolio risk is elevated - consider reducing position sizes")
        
        # Check for concentrated risk
        strikes = [pos.strike for pos in positions]
        if len(set(strikes)) < len(strikes) / 2:
            recommendations.append("Risk concentrated around few strikes - consider diversifying")
        
        # Check expiration clustering
        expiries = [pos.expiry for pos in positions]
        if len(set(expiries)) < 3:
            recommendations.append("Expirations clustered - consider spreading across time")
        
        return recommendations
    
    async def _generate_portfolio_summary(
        self,
        total_delta: float,
        total_gamma: float,
        total_theta: float,
        total_vega: float,
        risk_score: int,
        position_count: int
    ) -> str:
        """Generate portfolio summary."""
        risk_levels = {0: "Low", 1: "Medium", 2: "High", 3: "Critical"}
        risk_level = risk_levels.get(risk_score, "Unknown")
        
        summary = f"Portfolio Analysis Summary:\n\n"
        summary += f"Total Positions: {position_count}\n"
        summary += f"Overall Risk Level: {risk_level}\n\n"
        summary += f"Aggregate Greeks:\n"
        summary += f"- Delta: {total_delta:+.2f}\n"
        summary += f"- Gamma: {total_gamma:+.3f}\n"
        summary += f"- Theta: {total_theta:+.2f}\n"
        summary += f"- Vega: {total_vega:+.2f}\n\n"
        
        # Add interpretation
        if abs(total_delta) > DELTA_THRESHOLD * 5:
            direction = "bullish" if total_delta > 0 else "bearish"
            summary += f"Portfolio has significant {direction} bias.\n"
        
        if total_theta < THETA_THRESHOLD * 5:
            summary += f"High time decay of ${abs(total_theta):.2f} per day.\n"
        
        return summary
    
    async def _generate_rebalancing_suggestions(
        self,
        positions: List[GreeksData]
    ) -> List[Dict[str, Any]]:
        """Generate rebalancing suggestions."""
        suggestions = []
        
        # Calculate target Greeks (simplified)
        total_delta = sum(pos.delta for pos in positions)
        
        if abs(total_delta) > DELTA_THRESHOLD * 5:
            # Suggest delta-neutral rebalancing
            suggestions.append({
                'action': 'rebalance',
                'target': 'delta_neutral',
                'current_delta': total_delta,
                'adjustment_needed': -total_delta,
                'priority': 'high'
            })
        
        return suggestions
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _generate_cache_key(self, greeks_data: GreeksData, mode: AnalysisMode) -> str:
        """Generate cache key for analysis."""
        return f"{greeks_data.symbol}_{greeks_data.strike}_{greeks_data.expiry.date()}_{mode.value}"
    
    def _update_metrics(self, response_time: float) -> None:
        """Update performance metrics."""
        self.performance_metrics['total_analyses'] += 1
        
        # Update average response time
        total = self.performance_metrics['total_analyses']
        current_avg = self.performance_metrics['avg_response_time']
        new_avg = ((current_avg * (total - 1)) + response_time) / total
        self.performance_metrics['avg_response_time'] = new_avg
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'llm_model': DEFAULT_LLM_MODEL,
            'temperature': DEFAULT_TEMPERATURE,
            'max_tokens': MAX_TOKENS,
            'cache_ttl': 3600,  # 1 hour
            'risk_thresholds': {
                'delta': DELTA_THRESHOLD,
                'gamma': GAMMA_THRESHOLD,
                'theta': THETA_THRESHOLD,
                'vega': VEGA_THRESHOLD
            }
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_greeks_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX01_GreeksAgent:
    """
    Factory function to create Greeks Agent.
    
    Args:
        config: Agent configuration
        
    Returns:
        Configured SpyderX01_GreeksAgent instance
    """
    return SpyderX01_GreeksAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization code
_module_instance: Optional[SpyderX01_GreeksAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX01_GreeksAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX01_GreeksAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    import asyncio
    
    async def test_agent():
        """Test the Greeks Agent functionality."""
        print("Testing SpyderX01_GreeksAgent...")
        print("=" * 60)
        
        # Create agent
        agent = create_greeks_agent()
        
        # Create test Greeks data
        test_greeks = GreeksData(
            symbol="SPY_240201C550",
            strike=550.0,
            expiry=datetime.now() + timedelta(days=10),
            option_type='call',
            delta=0.65,
            gamma=0.15,
            theta=-45.5,
            vega=125.3,
            rho=0.05,
            implied_volatility=0.25,
            underlying_price=548.50,
            option_price=5.25
        )
        
        # Test single position analysis
        print("\n1. Testing single position analysis...")
        analysis = await agent.analyze_greeks(test_greeks)
        print(f"\nRisk Score: {analysis.risk_score}")
        print(f"Risk Assessment:\n{analysis.risk_assessment}")
        print(f"\nRecommendations:")
        for rec in analysis.recommendations:
            print(f"  - {rec}")
        print(f"\nSummary:\n{analysis.natural_language_summary}")
        
        # Test portfolio analysis
        print("\n2. Testing portfolio analysis...")
        positions = [
            test_greeks,
            GreeksData(
                symbol="SPY_240201P540",
                strike=540.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='put',
                delta=-0.35,
                gamma=0.12,
                theta=-38.2,
                vega=98.5,
                rho=-0.03,
                implied_volatility=0.22,
                underlying_price=548.50,
                option_price=3.75
            )
        ]
        
        portfolio_analysis = await agent.analyze_portfolio_greeks(positions)
        print(f"\nPortfolio Summary:\n{portfolio_analysis.natural_language_summary}")
        
        # Show performance metrics
        print("\n3. Performance Metrics:")
        metrics = agent.get_performance_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
    
    # Run the test
    asyncio.run(test_agent())
