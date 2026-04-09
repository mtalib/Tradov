#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX15_StrategyGeneratorAgent.py
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
from typing import Any
from dataclasses import dataclass
from collections import defaultdict
import random
import copy

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import logging

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    SPYDER_LOGGER_AVAILABLE = True
except ImportError:
    SPYDER_LOGGER_AVAILABLE = False
    import logging
# ==============================================================================
# CONSTANTS
# ==============================================================================
POPULATION_SIZE = 20  # Smaller for demo
GENERATION_COUNT = 10
MUTATION_RATE = 0.3
CROSSOVER_RATE = 0.7

# Strategy Components
ENTRY_CONDITIONS = [
    'rsi_oversold', 'rsi_overbought', 'macd_cross', 'bollinger_squeeze',
    'volume_spike', 'price_breakout', 'support_bounce', 'ma_cross',
    'vix_spike', 'put_call_ratio', 'momentum_shift'
]

EXIT_CONDITIONS = [
    'profit_target', 'stop_loss', 'time_decay', 'volatility_exit',
    'technical_reversal', 'trailing_stop', 'delta_threshold'
]

STRATEGY_TYPES = [
    'iron_condor', 'credit_spread', 'straddle', 'strangle',
    'butterfly', 'calendar'
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SimpleStrategyGene:
    """Simplified genetic encoding of a trading strategy"""
    strategy_type: str
    entry_conditions: list[str]
    entry_weights: list[float]
    exit_conditions: list[str]
    exit_weights: list[float]
    risk_factor: float  # Single risk parameter

    def mutate(self, mutation_rate: float = 0.1):
        """Simple mutation operation"""
        # Mutate entry conditions
        if random.random() < mutation_rate:
            if len(self.entry_conditions) > 1:
                # Remove a condition
                idx = random.randint(0, len(self.entry_conditions) - 1)
                self.entry_conditions.pop(idx)
                self.entry_weights.pop(idx)
            else:
                # Add a condition
                available = [c for c in ENTRY_CONDITIONS if c not in self.entry_conditions]
                if available:
                    self.entry_conditions.append(random.choice(available))
                    self.entry_weights.append(random.random())

        # Mutate weights
        for i in range(len(self.entry_weights)):
            if random.random() < mutation_rate:
                self.entry_weights[i] += random.gauss(0, 0.1)
                self.entry_weights[i] = max(0.1, min(1.0, self.entry_weights[i]))

        # Normalize weights
        if self.entry_weights:
            total = sum(self.entry_weights)
            self.entry_weights = [w/total for w in self.entry_weights]

        # Mutate risk factor
        if random.random() < mutation_rate:
            self.risk_factor += random.gauss(0, 0.05)
            self.risk_factor = max(0.1, min(0.5, self.risk_factor))

    def crossover(self, other: 'SimpleStrategyGene') -> 'SimpleStrategyGene':
        """Simple crossover operation"""
        # Mix entry conditions
        all_conditions = list(set(self.entry_conditions + other.entry_conditions))
        child_conditions = random.sample(
            all_conditions,
            min(len(all_conditions), random.randint(2, 4))
        )

        # Create weights
        child_weights = [random.random() for _ in child_conditions]
        total = sum(child_weights)
        child_weights = [w/total for w in child_weights]

        # Mix exit conditions
        child_exit = random.choice([self.exit_conditions, other.exit_conditions])
        child_exit_weights = random.choice([self.exit_weights, other.exit_weights])

        # Mix other properties
        child_type = random.choice([self.strategy_type, other.strategy_type])
        child_risk = (self.risk_factor + other.risk_factor) / 2

        return SimpleStrategyGene(
            strategy_type=child_type,
            entry_conditions=child_conditions,
            entry_weights=child_weights,
            exit_conditions=child_exit,
            exit_weights=child_exit_weights,
            risk_factor=child_risk
        )

@dataclass
class SimpleStrategy:
    """A simple generated strategy"""
    id: str
    name: str
    gene: SimpleStrategyGene
    fitness: float = 0.0
    generation: int = 0

# ==============================================================================
# SIMPLIFIED STRATEGY GENERATOR
# ==============================================================================
class SimplifiedStrategyGenerator:
    """Simplified strategy generator for testing"""

    def __init__(self):
        if SPYDER_LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        self.population = []
        self.generation = 0
        self.best_strategy = None
        self.fitness_history = []

        self.logger.info("✅ Simplified Strategy Generator initialized")

    def create_random_gene(self) -> SimpleStrategyGene:
        """Create a random strategy gene"""
        # Random strategy type
        strategy_type = random.choice(STRATEGY_TYPES)

        # Random entry conditions (2-4)
        num_entry = random.randint(2, 4)
        entry_conditions = random.sample(ENTRY_CONDITIONS, num_entry)
        entry_weights = [random.random() for _ in range(num_entry)]

        # Normalize weights
        total = sum(entry_weights)
        entry_weights = [w/total for w in entry_weights]

        # Random exit conditions (2-3)
        num_exit = random.randint(2, 3)
        exit_conditions = random.sample(EXIT_CONDITIONS, num_exit)
        exit_weights = [random.random() for _ in range(num_exit)]

        # Normalize weights
        total = sum(exit_weights)
        exit_weights = [w/total for w in exit_weights]

        # Random risk factor
        risk_factor = random.uniform(0.1, 0.3)

        return SimpleStrategyGene(
            strategy_type=strategy_type,
            entry_conditions=entry_conditions,
            entry_weights=entry_weights,
            exit_conditions=exit_conditions,
            exit_weights=exit_weights,
            risk_factor=risk_factor
        )

    def evaluate_strategy(self, gene: SimpleStrategyGene) -> float:
        """Simple fitness evaluation (mock)"""
        fitness = 0.0

        # Reward certain combinations
        if 'rsi_oversold' in gene.entry_conditions and 'profit_target' in gene.exit_conditions:
            fitness += 0.2

        if 'volume_spike' in gene.entry_conditions:
            fitness += 0.15

        if gene.strategy_type in ['iron_condor', 'credit_spread']:
            fitness += 0.1

        # Reward balanced entry conditions
        if 2 <= len(gene.entry_conditions) <= 3:
            fitness += 0.1

        # Reward moderate risk
        if 0.15 <= gene.risk_factor <= 0.25:
            fitness += 0.1

        # Add some randomness to simulate real performance
        fitness += random.uniform(0.0, 0.3)

        # Ensure 0-1 range
        return min(1.0, max(0.0, fitness))

    def initialize_population(self, size: int = POPULATION_SIZE) -> None:
        """Initialize random population"""
        self.population = []

        for i in range(size):
            gene = self.create_random_gene()
            strategy = SimpleStrategy(
                id=f"STRAT_{i:03d}",
                name=f"{gene.strategy_type.title()} Strategy {i}",
                gene=gene,
                generation=0
            )
            strategy.fitness = self.evaluate_strategy(gene)
            self.population.append(strategy)

        # Sort by fitness
        self.population.sort(key=lambda s: s.fitness, reverse=True)
        self.best_strategy = self.population[0]

        self.logger.info("Initialized population of %s strategies", size)
        self.logger.info(f"Best initial fitness: {self.best_strategy.fitness:.3f}")

    def evolve_generation(self) -> None:
        """Evolve one generation"""
        self.generation += 1
        new_population = []

        # Keep top 20% (elitism)
        elite_count = max(1, len(self.population) // 5)
        elites = self.population[:elite_count]
        new_population.extend(elites)

        # Generate offspring
        while len(new_population) < len(self.population):
            # Tournament selection
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()

            # Crossover
            if random.random() < CROSSOVER_RATE:
                child_gene = parent1.gene.crossover(parent2.gene)
            else:
                child_gene = copy.deepcopy(random.choice([parent1.gene, parent2.gene]))

            # Mutation
            if random.random() < MUTATION_RATE:
                child_gene.mutate()

            # Create child strategy
            child = SimpleStrategy(
                id=f"STRAT_G{self.generation}_{len(new_population):03d}",
                name=f"{child_gene.strategy_type.title()} Strategy Gen{self.generation}",
                gene=child_gene,
                generation=self.generation
            )
            child.fitness = self.evaluate_strategy(child_gene)
            new_population.append(child)

        # Update population
        self.population = new_population
        self.population.sort(key=lambda s: s.fitness, reverse=True)

        # Update best strategy
        if self.population[0].fitness > self.best_strategy.fitness:
            self.best_strategy = self.population[0]

        # Record fitness
        avg_fitness = np.mean([s.fitness for s in self.population])
        self.fitness_history.append({
            'generation': self.generation,
            'best_fitness': self.population[0].fitness,
            'avg_fitness': avg_fitness
        })

        self.logger.info(
            f"Generation {self.generation}: "
            f"Best={self.population[0].fitness:.3f}, "
            f"Avg={avg_fitness:.3f}"
        )

    def tournament_selection(self, tournament_size: int = 3) -> SimpleStrategy:
        """Tournament selection"""
        tournament = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(tournament, key=lambda s: s.fitness)

    def evolve(self, generations: int = GENERATION_COUNT) -> None:
        """Run complete evolution"""
        self.logger.info("Starting evolution for %s generations...", generations)

        for _gen in range(generations):
            self.evolve_generation()

        self.logger.info(f"Evolution complete! Best fitness: {self.best_strategy.fitness:.3f}")

    def get_report(self) -> dict[str, Any]:
        """Generate evolution report"""
        if not self.population:
            return {"error": "No population exists"}

        # Top strategies
        top_5 = self.population[:5]

        # Strategy type distribution
        type_counts = defaultdict(int)
        for strategy in self.population:
            type_counts[strategy.gene.strategy_type] += 1

        # Common entry conditions
        condition_counts = defaultdict(int)
        for strategy in top_5:
            for condition in strategy.gene.entry_conditions:
                condition_counts[condition] += 1

        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'best_fitness': self.best_strategy.fitness if self.best_strategy else 0,
            'avg_fitness': np.mean([s.fitness for s in self.population]),
            'best_strategy': {
                'name': self.best_strategy.name,
                'type': self.best_strategy.gene.strategy_type,
                'fitness': self.best_strategy.fitness,
                'entry_conditions': self.best_strategy.gene.entry_conditions,
                'exit_conditions': self.best_strategy.gene.exit_conditions,
                'risk_factor': self.best_strategy.gene.risk_factor
            } if self.best_strategy else None,
            'top_strategies': [
                {
                    'name': s.name,
                    'type': s.gene.strategy_type,
                    'fitness': s.fitness
                }
                for s in top_5
            ],
            'strategy_type_distribution': dict(type_counts),
            'common_entry_conditions': sorted(
                condition_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'fitness_history': self.fitness_history
        }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Test the simplified strategy generator"""
    logging.info("🧬 SPYDER SIMPLIFIED STRATEGY GENERATOR TEST")
    logging.info("=" * 60)

    # Create generator
    generator = SimplifiedStrategyGenerator()

    # Initialize population
    logging.info("\n1️⃣ Initializing random population...")
    generator.initialize_population(20)

    # Show initial report
    report = generator.get_report()
    logging.info("   Population: %s strategies", report['population_size'])
    logging.info(f"   Best fitness: {report['best_fitness']:.3f}")
    logging.info(f"   Average fitness: {report['avg_fitness']:.3f}")

    if report['best_strategy']:
        best = report['best_strategy']
        logging.info("   Best strategy: %s (%s)", best['name'], best['type'])
        logging.info("   Entry conditions: %s", ', '.join(best['entry_conditions']))

    # Evolve for a few generations
    logging.info("\n2️⃣ Running evolution...")
    generator.evolve(5)

    # Final report
    final_report = generator.get_report()
    logging.info("\n3️⃣ Evolution Results:")
    logging.info("   Generations completed: %s", final_report['generation'])
    logging.info(f"   Final best fitness: {final_report['best_fitness']:.3f}")
    logging.info(f"   Final avg fitness: {final_report['avg_fitness']:.3f}")

    logging.info("\n🏆 Best Strategy:")
    if final_report['best_strategy']:
        best = final_report['best_strategy']
        logging.info("   Name: %s", best['name'])
        logging.info("   Type: %s", best['type'])
        logging.info(f"   Fitness: {best['fitness']:.3f}")
        logging.info("   Entry: %s", ', '.join(best['entry_conditions']))
        logging.info("   Exit: %s", ', '.join(best['exit_conditions']))
        logging.info(f"   Risk Factor: {best['risk_factor']:.3f}")

    logging.info("\n📊 Top 5 Strategies:")
    for i, strategy in enumerate(final_report['top_strategies'], 1):
        logging.info(f"   {i}. {strategy['name']} ({strategy['type']}) - {strategy['fitness']:.3f}")

    logging.info("\n📈 Strategy Type Distribution:")
    for stype, count in final_report['strategy_type_distribution'].items():
        logging.info("   %s: %s", stype, count)

    logging.info("\n🎯 Common Entry Conditions:")
    for condition, count in final_report['common_entry_conditions']:
        logging.info("   %s: %s", condition, count)

    logging.info("\n✅ Simplified Strategy Generator test completed!")
    logging.info("🚀 Ready for full institutional strategy evolution!")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--report":
            # Quick report mode
            generator = SimplifiedStrategyGenerator()
            generator.initialize_population(10)
            report = generator.get_report()


        elif sys.argv[1] == "--generate":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            generator = SimplifiedStrategyGenerator()
            generator.initialize_population(count)

            for _strategy in generator.population:
                pass

        elif sys.argv[1] == "--evolve":
            generations = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            generator = SimplifiedStrategyGenerator()
            generator.initialize_population(10)
            generator.evolve(generations)

    else:
        # Run full demo
        asyncio.run(main())
