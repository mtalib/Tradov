#!/usr/bin/env python3
"""
Mock Strategy Generator for Testing
Simple version without heavy dependencies
"""

from dataclasses import dataclass
from typing import List

@dataclass
class MockGene:
    strategy_type: str = "credit_spread"
    entry_conditions: List[str] = None
    risk_factor: float = 0.15
    
    def __post_init__(self):
        if self.entry_conditions is None:
            self.entry_conditions = ["rsi_oversold", "volume_spike", "momentum_shift"]

@dataclass  
class MockStrategy:
    fitness: float = 0.823
    gene: MockGene = None
    
    def __post_init__(self):
        if self.gene is None:
            self.gene = MockGene()

class SimplifiedStrategyGenerator:
    """Mock strategy generator for testing purposes."""
    
    def __init__(self):
        self.best_strategy = MockStrategy()
        self.population = []
        print("   🧬 Mock Strategy Generator initialized")
    
    def initialize_population(self, size: int):
        """Initialize population."""
        self.population = [MockStrategy(fitness=0.75 + i*0.02) for i in range(size)]
        print(f"   📊 Mock population initialized: {size} strategies")
        return True
    
    def evolve(self, generations: int):
        """Mock evolution process."""
        print(f"   🚀 Mock evolution running: {generations} generations")
        
        # Simulate realistic improvement over generations
        for gen in range(generations):
            improvement = 0.02 + (gen * 0.01)
            self.best_strategy.fitness = min(0.95, self.best_strategy.fitness + improvement)
        
        print(f"   🏆 Best fitness achieved: {self.best_strategy.fitness:.3f}")
        print(f"   🎯 Strategy type: {self.best_strategy.gene.strategy_type}")
        print(f"   ⚡ Risk factor: {self.best_strategy.gene.risk_factor:.3f}")
        return True
