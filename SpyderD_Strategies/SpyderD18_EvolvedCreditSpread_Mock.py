#!/usr/bin/env python3
"""
Mock Evolved Credit Spread Strategy for Testing
Simulates the real evolved strategy behavior for integration testing
"""

from dataclasses import dataclass
from typing import Dict, List, Any
import random

@dataclass
class MockEvolvedParams:
    fitness_score: float = 0.823
    generation: int = 20
    strategy_type: str = "credit_spread"
    evolution_time: str = "45.2 seconds"
    total_mutations: int = 156

class EvolvedCreditSpreadStrategy:
    """Mock evolved strategy for comprehensive testing."""
    
    def __init__(self):
        self.strategy_name = "EvolvedCreditSpreadStrategy_Mock"
        self.evolved_params = MockEvolvedParams()
        self.version = "1.0_TEST"
        print("   🎯 Mock Evolved Strategy initialized")
        print(f"   📈 Simulated fitness: {self.evolved_params.fitness_score:.3f}")
    
    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """Mock market analysis with realistic values."""
        
        # Simulate analysis based on market data
        price = market_data.get('current_price', 400.0)
        vix = market_data.get('vix', 18.5)
        
        # Generate realistic analysis values
        signal_strength = 0.75 + (random.random() * 0.2)  # 0.75-0.95
        ai_confidence = 0.85 + (random.random() * 0.1)    # 0.85-0.95
        risk_score = 0.15 + (random.random() * 0.15)      # 0.15-0.30
        
        # Adjust based on VIX (higher VIX = more caution)
        if vix > 25:
            signal_strength *= 0.9
            risk_score *= 1.2
        elif vix < 15:
            signal_strength *= 1.1
            risk_score *= 0.8
        
        analysis = {
            'signal_strength': min(0.95, signal_strength),
            'ai_confidence': min(0.95, ai_confidence),
            'risk_score': min(0.50, risk_score),
            'market_regime': 'normal',
            'volatility_forecast': vix * 0.95,
            'trend_strength': 0.65
        }
        
        print(f"   🔍 Market analysis complete:")
        print(f"     Signal Strength: {analysis['signal_strength']:.3f}")
        print(f"     AI Confidence: {analysis['ai_confidence']:.3f}")
        print(f"     Risk Score: {analysis['risk_score']:.3f}")
        
        return analysis
    
    def generate_signals(self, analysis: Dict[str, float]) -> List[Dict[str, Any]]:
        """Mock signal generation with realistic trading signals."""
        
        signals = []
        
        # Only generate signals if confidence is high enough
        if analysis['ai_confidence'] > 0.7 and analysis['signal_strength'] > 0.6:
            
            # Generate 1-3 signals based on confidence
            num_signals = 1 if analysis['ai_confidence'] < 0.85 else 2
            if analysis['ai_confidence'] > 0.92:
                num_signals = 3
            
            for i in range(num_signals):
                signal = {
                    'action': 'OPEN_CREDIT_SPREAD',
                    'short_strike': 395.0 - (i * 2.5),  # Varying strikes
                    'long_strike': 390.0 - (i * 2.5),
                    'confidence': analysis['ai_confidence'] - (i * 0.05),
                    'expected_profit': 1.2 + (i * 0.1),
                    'max_risk': 3.8 - (i * 0.2),
                    'days_to_expiry': 15 + (i * 5),
                    'delta_neutral': True,
                    'signal_id': f"ECS_{i+1}_{int(analysis['signal_strength']*1000)}"
                }
                signals.append(signal)
        
        print(f"   📡 Generated {len(signals)} trading signals")
        for i, signal in enumerate(signals):
            print(f"     Signal {i+1}: {signal['action']} at ${signal['short_strike']:.1f}")
        
        return signals
    
    def get_strategy_metrics(self) -> Dict[str, Any]:
        """Get strategy performance metrics."""
        return {
            'fitness_score': self.evolved_params.fitness_score,
            'win_rate': 0.73,
            'avg_profit': 145.67,
            'max_drawdown': -5.2,
            'sharpe_ratio': 1.89,
            'total_trades': 234,
            'profitable_trades': 171
        }
