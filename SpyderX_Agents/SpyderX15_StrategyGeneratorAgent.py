#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX15_StrategyGeneratorAgent.py
Group: X (AI Agents)
Purpose: Autonomous AI Strategy Generation and Evolution

Description:
    This module implements an agentic AI system that autonomously generates,
    tests, and evolves trading strategies. Inspired by Man Group's AlphaGPT,
    it uses genetic algorithms, code generation, and reinforcement learning
    to continuously discover new profitable strategies for SPY options trading.

Key Features:
    - Autonomous strategy ideation and hypothesis generation
    - Code generation using templates and LLM-based synthesis
    - Genetic algorithm optimization for strategy evolution
    - Automated backtesting and performance evaluation
    - Learning from successful pattern recognition
    - Strategy mutation and crossover operations
    - Risk-aware fitness functions
    
Architecture:
    - Strategy DNA encoding for genetic operations
    - Template-based code generation engine
    - Integration with SpyderX06_BacktestingAgent
    - Performance database for pattern learning
    - Multi-objective optimization (return, risk, drawdown)

Author: SPYDER Strategy Evolution Team
Date: 2025-07-11
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import json
import pickle
import ast
import random
import copy
from pathlib import Path
import hashlib
import inspect
import textwrap

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from deap import base, creator, tools, algorithms
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModelForCausalLM
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    BACKTEST_YEARS,
    MIN_TRADES_FOR_VALIDATION,
    MAX_DRAWDOWN_THRESHOLD
)
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from SpyderX_Agents.SpyderX06_BacktestingAgent import SpyderX06_BacktestingAgent
from SpyderL_ML.SpyderL05_PatternRecognition import PatternRecognizer

# ==============================================================================
# CONSTANTS
# ==============================================================================
POPULATION_SIZE = 100
GENERATION_COUNT = 50
MUTATION_RATE = 0.2
CROSSOVER_RATE = 0.7
ELITE_SIZE = 10
STRATEGY_DB_PATH = "data/strategies/generated_strategies.db"
TEMPLATE_PATH = "templates/strategy_templates/"
MAX_STRATEGY_COMPLEXITY = 20
MIN_FITNESS_THRESHOLD = 0.5

# Strategy Components
ENTRY_CONDITIONS = [
    'rsi_oversold', 'rsi_overbought', 'macd_cross', 'bollinger_squeeze',
    'volume_spike', 'price_breakout', 'support_bounce', 'resistance_test',
    'ma_cross', 'momentum_shift', 'vix_spike', 'put_call_ratio',
    'dark_pool_flow', 'option_sweep', 'gamma_squeeze', 'delta_neutral'
]

EXIT_CONDITIONS = [
    'profit_target', 'stop_loss', 'time_decay', 'volatility_exit',
    'technical_reversal', 'trailing_stop', 'delta_threshold', 'gamma_risk',
    'theta_decay', 'vega_exposure', 'adverse_movement', 'regime_change'
]

STRATEGY_TYPES = [
    'iron_condor', 'credit_spread', 'debit_spread', 'straddle', 'strangle',
    'butterfly', 'calendar', 'diagonal', 'ratio_spread', 'jade_lizard',
    'broken_wing', 'double_calendar', 'zebra', 'backratio'
]

RISK_PARAMS = [
    'max_position_size', 'max_portfolio_risk', 'kelly_criterion',
    'volatility_sizing', 'correlation_limit', 'concentration_limit'
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyGene:
    """Genetic encoding of a trading strategy"""
    strategy_type: str
    entry_conditions: List[str]
    entry_weights: List[float]
    exit_conditions: List[str]
    exit_weights: List[float]
    risk_params: Dict[str, float]
    time_constraints: Dict[str, Any]
    Greeks_thresholds: Dict[str, float]
    
    def to_dna(self) -> List[float]:
        """Convert strategy to genetic sequence"""
        dna = []
        
        # Encode strategy type
        dna.append(STRATEGY_TYPES.index(self.strategy_type))
        
        # Encode entry conditions
        for condition in ENTRY_CONDITIONS:
            if condition in self.entry_conditions:
                idx = self.entry_conditions.index(condition)
                dna.extend([1.0, self.entry_weights[idx]])
            else:
                dna.extend([0.0, 0.0])
        
        # Encode exit conditions
        for condition in EXIT_CONDITIONS:
            if condition in self.exit_conditions:
                idx = self.exit_conditions.index(condition)
                dna.extend([1.0, self.exit_weights[idx]])
            else:
                dna.extend([0.0, 0.0])
        
        # Encode risk parameters
        for param in RISK_PARAMS:
            dna.append(self.risk_params.get(param, 0.5))
        
        return dna
    
    @classmethod
    def from_dna(cls, dna: List[float]) -> 'StrategyGene':
        """Reconstruct strategy from genetic sequence"""
        idx = 0
        
        # Decode strategy type
        strategy_type = STRATEGY_TYPES[int(dna[idx]) % len(STRATEGY_TYPES)]
        idx += 1
        
        # Decode entry conditions
        entry_conditions = []
        entry_weights = []
        for condition in ENTRY_CONDITIONS:
            if dna[idx] > 0.5:
                entry_conditions.append(condition)
                entry_weights.append(dna[idx + 1])
            idx += 2
        
        # Decode exit conditions
        exit_conditions = []
        exit_weights = []
        for condition in EXIT_CONDITIONS:
            if dna[idx] > 0.5:
                exit_conditions.append(condition)
                exit_weights.append(dna[idx + 1])
            idx += 2
        
        # Decode risk parameters
        risk_params = {}
        for param in RISK_PARAMS:
            if idx < len(dna):
                risk_params[param] = dna[idx]
                idx += 1
        
        return cls(
            strategy_type=strategy_type,
            entry_conditions=entry_conditions,
            entry_weights=entry_weights,
            exit_conditions=exit_conditions,
            exit_weights=exit_weights,
            risk_params=risk_params,
            time_constraints={},
            Greeks_thresholds={}
        )

@dataclass
class GeneratedStrategy:
    """A complete generated trading strategy"""
    id: str
    name: str
    gene: StrategyGene
    code: str
    backtest_results: Optional[Dict[str, Any]] = None
    fitness_score: float = 0.0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    creation_date: datetime = field(default_factory=datetime.now)
    
    def get_hash(self) -> str:
        """Generate unique hash for strategy"""
        return hashlib.md5(self.code.encode()).hexdigest()[:8]

@dataclass
class EvolutionMetrics:
    """Track evolution progress"""
    generation: int
    best_fitness: float
    avg_fitness: float
    diversity_score: float
    novel_strategies: int
    convergence_rate: float

# ==============================================================================
# STRATEGY CODE GENERATOR
# ==============================================================================
class StrategyCodeGenerator:
    """Generate Python code for trading strategies"""
    
    def __init__(self):
        self.logger = SpyderLogger().get_logger(self.__class__.__name__)
        self.template_cache = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """Load strategy templates"""
        self.base_template = '''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Generated Strategy: {name}
Generated: {timestamp}
Fitness Score: {fitness:.3f}
"""

from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
import numpy as np
import pandas as pd

class {class_name}(BaseStrategy):
    """
    Autonomously generated strategy using genetic algorithms.
    
    Strategy Type: {strategy_type}
    Entry Conditions: {entry_conditions}
    Exit Conditions: {exit_conditions}
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.name = "{name}"
        self.strategy_type = "{strategy_type}"
        
        # Risk parameters
        {risk_params_init}
        
        # Entry/Exit weights
        self.entry_weights = {entry_weights}
        self.exit_weights = {exit_weights}
        
        # Greeks thresholds
        self.greeks_thresholds = {greeks_thresholds}
    
    def check_entry_conditions(self, market_data):
        """Check if entry conditions are met"""
        signals = []
        
        {entry_logic}
        
        # Weighted combination
        if signals:
            weights = self.entry_weights[:len(signals)]
            weighted_score = np.average(signals, weights=weights)
            return weighted_score > 0.6
        return False
    
    def check_exit_conditions(self, position, market_data):
        """Check if exit conditions are met"""
        signals = []
        
        {exit_logic}
        
        # Weighted combination
        if signals:
            weights = self.exit_weights[:len(signals)]
            weighted_score = np.average(signals, weights=weights)
            return weighted_score > 0.5
        return False
    
    def calculate_position_size(self, market_data):
        """Calculate position size based on risk parameters"""
        account_value = self.get_account_value()
        
        {sizing_logic}
        
        return position_size
    
    def execute_trade(self, signal, market_data):
        """Execute the {strategy_type} strategy"""
        {execution_logic}
        
        return orders
'''
    
    def generate_strategy_code(self, gene: StrategyGene, name: str) -> str:
        """Generate complete strategy code from gene"""
        
        # Generate class name
        class_name = f"Generated{name.replace(' ', '')}Strategy"
        
        # Generate risk parameters initialization
        risk_params_init = self._generate_risk_params_init(gene.risk_params)
        
        # Generate entry logic
        entry_logic = self._generate_entry_logic(gene.entry_conditions)
        
        # Generate exit logic
        exit_logic = self._generate_exit_logic(gene.exit_conditions)
        
        # Generate sizing logic
        sizing_logic = self._generate_sizing_logic(gene.risk_params)
        
        # Generate execution logic
        execution_logic = self._generate_execution_logic(gene.strategy_type)
        
        # Fill template
        code = self.base_template.format(
            name=name,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            fitness=0.0,  # Will be updated after backtesting
            class_name=class_name,
            strategy_type=gene.strategy_type,
            entry_conditions=", ".join(gene.entry_conditions),
            exit_conditions=", ".join(gene.exit_conditions),
            risk_params_init=risk_params_init,
            entry_weights=gene.entry_weights,
            exit_weights=gene.exit_weights,
            greeks_thresholds=gene.Greeks_thresholds,
            entry_logic=entry_logic,
            exit_logic=exit_logic,
            sizing_logic=sizing_logic,
            execution_logic=execution_logic
        )
        
        return code
    
    def _generate_risk_params_init(self, risk_params: Dict[str, float]) -> str:
        """Generate risk parameter initialization code"""
        lines = []
        for param, value in risk_params.items():
            lines.append(f"self.{param} = {value:.4f}")
        return "\n        ".join(lines)
    
    def _generate_entry_logic(self, conditions: List[str]) -> str:
        """Generate entry condition checking logic"""
        logic_map = {
            'rsi_oversold': '''
        # RSI Oversold
        rsi = market_data.get('rsi', 50)
        if rsi < 30:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'macd_cross': '''
        # MACD Cross
        macd = market_data.get('macd', 0)
        macd_signal = market_data.get('macd_signal', 0)
        if macd > macd_signal and market_data.get('prev_macd', 0) <= market_data.get('prev_macd_signal', 0):
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'volume_spike': '''
        # Volume Spike
        volume_ratio = market_data.get('volume_ratio', 1.0)
        if volume_ratio > 2.0:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'vix_spike': '''
        # VIX Spike
        vix = market_data.get('vix', 20)
        vix_ma = market_data.get('vix_ma20', 20)
        if vix > vix_ma * 1.2:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'option_sweep': '''
        # Option Sweep Detection
        sweep_detected = market_data.get('option_sweep', False)
        if sweep_detected:
            signals.append(1.0)
        else:
            signals.append(0.0)'''
        }
        
        logic_parts = []
        for condition in conditions:
            if condition in logic_map:
                logic_parts.append(logic_map[condition])
        
        return "\n".join(logic_parts) if logic_parts else "        # No entry conditions"
    
    def _generate_exit_logic(self, conditions: List[str]) -> str:
        """Generate exit condition checking logic"""
        logic_map = {
            'profit_target': '''
        # Profit Target
        pnl_percent = position.get('pnl_percent', 0)
        if pnl_percent >= self.profit_target:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'stop_loss': '''
        # Stop Loss
        pnl_percent = position.get('pnl_percent', 0)
        if pnl_percent <= -self.stop_loss:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'time_decay': '''
        # Time Decay (Theta)
        days_held = position.get('days_held', 0)
        dte = position.get('dte', 30)
        if days_held > 5 and dte < 5:
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'delta_threshold': '''
        # Delta Threshold
        position_delta = position.get('delta', 0)
        if abs(position_delta) > self.greeks_thresholds.get('delta', 0.5):
            signals.append(1.0)
        else:
            signals.append(0.0)''',
            
            'volatility_exit': '''
        # Volatility Exit
        current_iv = market_data.get('iv', 0.2)
        entry_iv = position.get('entry_iv', 0.2)
        if current_iv < entry_iv * 0.8:
            signals.append(1.0)
        else:
            signals.append(0.0)'''
        }
        
        logic_parts = []
        for condition in conditions:
            if condition in logic_map:
                logic_parts.append(logic_map[condition])
        
        return "\n".join(logic_parts) if logic_parts else "        # No exit conditions"
    
    def _generate_sizing_logic(self, risk_params: Dict[str, float]) -> str:
        """Generate position sizing logic"""
        return '''
        # Kelly Criterion with safety factor
        kelly_fraction = self.kelly_criterion * 0.25  # Conservative Kelly
        
        # Volatility-based sizing
        vix = market_data.get('vix', 20)
        vol_adjustment = 20 / vix  # Inverse volatility sizing
        
        # Maximum position size constraint
        max_size = account_value * self.max_position_size
        
        # Calculate final position size
        position_size = min(
            account_value * kelly_fraction * vol_adjustment,
            max_size
        )
        
        # Round to nearest contract
        position_size = max(1, int(position_size / 100))'''
    
    def _generate_execution_logic(self, strategy_type: str) -> str:
        """Generate strategy-specific execution logic"""
        execution_map = {
            'iron_condor': '''
        # Iron Condor execution
        strikes = self.calculate_iron_condor_strikes(market_data)
        
        orders = [
            self.create_order('SELL', 'PUT', strikes['short_put'], 1),
            self.create_order('BUY', 'PUT', strikes['long_put'], 1),
            self.create_order('SELL', 'CALL', strikes['short_call'], 1),
            self.create_order('BUY', 'CALL', strikes['long_call'], 1)
        ]''',
            
            'credit_spread': '''
        # Credit Spread execution
        spread_type = 'PUT' if signal == 'BULLISH' else 'CALL'
        strikes = self.calculate_credit_spread_strikes(market_data, spread_type)
        
        orders = [
            self.create_order('SELL', spread_type, strikes['short'], 1),
            self.create_order('BUY', spread_type, strikes['long'], 1)
        ]''',
            
            'straddle': '''
        # Straddle execution
        atm_strike = self.get_atm_strike(market_data['price'])
        
        orders = [
            self.create_order('BUY', 'PUT', atm_strike, 1),
            self.create_order('BUY', 'CALL', atm_strike, 1)
        ]'''
        }
        
        return execution_map.get(strategy_type, "# Strategy execution logic")

# ==============================================================================
# STRATEGY GENERATOR AGENT
# ==============================================================================
class SpyderX15_StrategyGeneratorAgent:
    """
    Autonomous AI agent for generating and evolving trading strategies.
    
    This agent uses genetic algorithms and machine learning to continuously
    create, test, and improve trading strategies without human intervention.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the strategy generator agent"""
        self.logger = SpyderLogger().get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.population_size = self.config.get('population_size', POPULATION_SIZE)
        self.generation_count = self.config.get('generations', GENERATION_COUNT)
        
        # Components
        self.code_generator = StrategyCodeGenerator()
        self.backtesting_agent = SpyderX06_BacktestingAgent.get_instance()
        self.pattern_recognizer = PatternRecognizer()
        
        # Genetic algorithm setup
        self._setup_genetic_algorithm()
        
        # Strategy database
        self.strategy_db = {}
        self.successful_patterns = defaultdict(list)
        self.generation_history = []
        
        # Performance tracking
        self.best_strategy = None
        self.fitness_history = []
        
        # Load existing strategies
        self._load_strategy_database()
        
        self.logger.info("✅ Strategy Generator Agent initialized")
    
    # ==========================================================================
    # GENETIC ALGORITHM SETUP
    # ==========================================================================
    
    def _setup_genetic_algorithm(self) -> None:
        """Setup DEAP genetic algorithm framework"""
        # Create fitness class (maximize)
        if not hasattr(creator, "FitnessMax"):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        
        # Create individual class
        if not hasattr(creator, "Individual"):
            creator.create("Individual", list, fitness=creator.FitnessMax)
        
        # Create toolbox
        self.toolbox = base.Toolbox()
        
        # Gene attributes
        self.toolbox.register("attr_float", random.uniform, 0, 1)
        
        # Individual and population
        gene_size = self._calculate_gene_size()
        self.toolbox.register(
            "individual",
            tools.initRepeat,
            creator.Individual,
            self.toolbox.attr_float,
            n=gene_size
        )
        self.toolbox.register(
            "population",
            tools.initRepeat,
            list,
            self.toolbox.individual
        )
        
        # Genetic operators
        self.toolbox.register("evaluate", self._evaluate_strategy)
        self.toolbox.register("mate", tools.cxTwoPoint)
        self.toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.2, indpb=MUTATION_RATE)
        self.toolbox.register("select", tools.selTournament, tournsize=3)
    
    def _calculate_gene_size(self) -> int:
        """Calculate the size of strategy gene"""
        size = 1  # Strategy type
        size += len(ENTRY_CONDITIONS) * 2  # Condition + weight
        size += len(EXIT_CONDITIONS) * 2   # Condition + weight
        size += len(RISK_PARAMS)           # Risk parameters
        return size
    
    # ==========================================================================
    # STRATEGY GENERATION
    # ==========================================================================
    
    async def generate_new_strategies(self, 
                                      count: int = 10,
                                      strategy_type: Optional[str] = None) -> List[GeneratedStrategy]:
        """
        Generate new trading strategies.
        
        Args:
            count: Number of strategies to generate
            strategy_type: Specific type to generate (optional)
            
        Returns:
            List of generated strategies
        """
        try:
            self.logger.info(f"Generating {count} new strategies...")
            strategies = []
            
            for i in range(count):
                # Create random gene or use guided generation
                if random.random() < 0.3 and self.successful_patterns:
                    # Learn from successful patterns
                    gene = self._generate_from_patterns(strategy_type)
                else:
                    # Random generation
                    gene = self._generate_random_gene(strategy_type)
                
                # Generate strategy
                strategy = await self._create_strategy_from_gene(gene)
                strategies.append(strategy)
                
                self.logger.info(f"Generated strategy: {strategy.name}")
            
            return strategies
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_new_strategies',
                'count': count
            })
            return []
    
    def _generate_random_gene(self, strategy_type: Optional[str] = None) -> StrategyGene:
        """Generate a random strategy gene"""
        # Select strategy type
        if strategy_type and strategy_type in STRATEGY_TYPES:
            selected_type = strategy_type
        else:
            selected_type = random.choice(STRATEGY_TYPES)
        
        # Select entry conditions (2-5 conditions)
        num_entry = random.randint(2, 5)
        entry_conditions = random.sample(ENTRY_CONDITIONS, num_entry)
        entry_weights = [random.random() for _ in range(num_entry)]
        
        # Normalize weights
        total = sum(entry_weights)
        entry_weights = [w/total for w in entry_weights]
        
        # Select exit conditions (2-4 conditions)
        num_exit = random.randint(2, 4)
        exit_conditions = random.sample(EXIT_CONDITIONS, num_exit)
        exit_weights = [random.random() for _ in range(num_exit)]
        
        # Normalize weights
        total = sum(exit_weights)
        exit_weights = [w/total for w in exit_weights]
        
        # Generate risk parameters
        risk_params = {
            'max_position_size': random.uniform(0.05, 0.2),
            'max_portfolio_risk': random.uniform(0.1, 0.3),
            'kelly_criterion': random.uniform(0.1, 0.5),
            'volatility_sizing': random.uniform(0.5, 2.0),
            'correlation_limit': random.uniform(0.5, 0.8),
            'concentration_limit': random.uniform(0.2, 0.4)
        }
        
        # Generate Greeks thresholds
        greeks_thresholds = {
            'delta': random.uniform(0.2, 0.8),
            'gamma': random.uniform(0.01, 0.1),
            'theta': random.uniform(-0.5, -0.1),
            'vega': random.uniform(0.1, 0.5)
        }
        
        return StrategyGene(
            strategy_type=selected_type,
            entry_conditions=entry_conditions,
            entry_weights=entry_weights,
            exit_conditions=exit_conditions,
            exit_weights=exit_weights,
            risk_params=risk_params,
            time_constraints={},
            Greeks_thresholds=greeks_thresholds
        )
    
    def _generate_from_patterns(self, strategy_type: Optional[str] = None) -> StrategyGene:
        """Generate strategy based on successful patterns"""
        # Find successful strategies of similar type
        if strategy_type:
            patterns = [p for p in self.successful_patterns[strategy_type]]
        else:
            patterns = [p for patterns in self.successful_patterns.values() for p in patterns]
        
        if not patterns:
            return self._generate_random_gene(strategy_type)
        
        # Select a successful pattern
        base_pattern = random.choice(patterns)
        
        # Create variation
        gene = copy.deepcopy(base_pattern)
        
        # Mutate slightly
        if random.random() < 0.5:
            # Add or remove a condition
            if random.random() < 0.5 and len(gene.entry_conditions) < 5:
                new_condition = random.choice([c for c in ENTRY_CONDITIONS if c not in gene.entry_conditions])
                gene.entry_conditions.append(new_condition)
                gene.entry_weights.append(random.random())
            elif len(gene.entry_conditions) > 2:
                idx = random.randint(0, len(gene.entry_conditions) - 1)
                gene.entry_conditions.pop(idx)
                gene.entry_weights.pop(idx)
        
        # Adjust weights
        for i in range(len(gene.entry_weights)):
            gene.entry_weights[i] += random.gauss(0, 0.1)
            gene.entry_weights[i] = max(0, min(1, gene.entry_weights[i]))
        
        # Normalize
        total = sum(gene.entry_weights)
        gene.entry_weights = [w/total for w in gene.entry_weights]
        
        return gene
    
    async def _create_strategy_from_gene(self, gene: StrategyGene) -> GeneratedStrategy:
        """Create a complete strategy from gene"""
        # Generate unique name
        strategy_id = f"GEN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(1000, 9999)}"
        name = f"{gene.strategy_type.replace('_', ' ').title()} {strategy_id[-4:]}"
        
        # Generate code
        code = self.code_generator.generate_strategy_code(gene, name)
        
        # Create strategy object
        strategy = GeneratedStrategy(
            id=strategy_id,
            name=name,
            gene=gene,
            code=code
        )
        
        return strategy
    
    # ==========================================================================
    # GENETIC EVOLUTION
    # ==========================================================================
    
    async def evolve_strategies(self, 
                                initial_population: Optional[List[GeneratedStrategy]] = None,
                                generations: Optional[int] = None) -> List[GeneratedStrategy]:
        """
        Evolve strategies using genetic algorithm.
        
        Args:
            initial_population: Starting strategies (optional)
            generations: Number of generations to evolve
            
        Returns:
            Evolved population of strategies
        """
        try:
            generations = generations or self.generation_count
            
            # Create initial population
            if initial_population:
                population = [
                    creator.Individual(strategy.gene.to_dna())
                    for strategy in initial_population
                ]
            else:
                population = self.toolbox.population(n=self.population_size)
            
            # Statistics
            stats = tools.Statistics(lambda ind: ind.fitness.values)
            stats.register("avg", np.mean)
            stats.register("std", np.std)
            stats.register("min", np.min)
            stats.register("max", np.max)
            
            # Hall of fame
            hof = tools.HallOfFame(ELITE_SIZE)
            
            self.logger.info(f"Starting evolution for {generations} generations...")
            
            # Evolution loop
            for gen in range(generations):
                self.logger.info(f"Generation {gen + 1}/{generations}")
                
                # Evaluate population
                fitnesses = await self._evaluate_population(population)
                for ind, fit in zip(population, fitnesses):
                    ind.fitness.values = (fit,)
                
                # Update hall of fame
                hof.update(population)
                
                # Record statistics
                record = stats.compile(population)
                self.generation_history.append(EvolutionMetrics(
                    generation=gen,
                    best_fitness=record['max'],
                    avg_fitness=record['avg'],
                    diversity_score=self._calculate_diversity(population),
                    novel_strategies=self._count_novel_strategies(population),
                    convergence_rate=record['std']
                ))
                
                self.logger.info(
                    f"Gen {gen}: Avg={record['avg']:.3f}, "
                    f"Max={record['max']:.3f}, Std={record['std']:.3f}"
                )
                
                # Selection
                offspring = self.toolbox.select(population, len(population))
                offspring = list(map(self.toolbox.clone, offspring))
                
                # Crossover
                for child1, child2 in zip(offspring[::2], offspring[1::2]):
                    if random.random() < CROSSOVER_RATE:
                        self.toolbox.mate(child1, child2)
                        del child1.fitness.values
                        del child2.fitness.values
                
                # Mutation
                for mutant in offspring:
                    if random.random() < MUTATION_RATE:
                        self.toolbox.mutate(mutant)
                        del mutant.fitness.values
                
                # Replace population
                population[:] = offspring
                
                # Add elite back
                for elite in hof:
                    population[random.randint(0, len(population)-1)] = self.toolbox.clone(elite)
            
            # Convert best individuals back to strategies
            evolved_strategies = []
            for individual in hof:
                gene = StrategyGene.from_dna(individual)
                strategy = await self._create_strategy_from_gene(gene)
                strategy.fitness_score = individual.fitness.values[0]
                strategy.generation = generations
                evolved_strategies.append(strategy)
            
            # Save best strategy
            if evolved_strategies:
                self.best_strategy = evolved_strategies[0]
                self._save_successful_pattern(self.best_strategy)
            
            return evolved_strategies
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'evolve_strategies',
                'generations': generations
            })
            return []
    
    async def _evaluate_population(self, population: List) -> List[float]:
        """Evaluate fitness of entire population"""
        fitnesses = []
        
        for individual in population:
            fitness = await self._evaluate_strategy(individual)
            fitnesses.append(fitness)
        
        return fitnesses
    
    async def _evaluate_strategy(self, individual: List[float]) -> float:
        """
        Evaluate fitness of a strategy.
        
        Multi-objective fitness function considering:
        - Total return
        - Sharpe ratio
        - Maximum drawdown
        - Win rate
        - Number of trades
        """
        try:
            # Convert DNA to strategy
            gene = StrategyGene.from_dna(individual)
            strategy = await self._create_strategy_from_gene(gene)
            
            # Backtest strategy
            backtest_results = await self.backtesting_agent.backtest_strategy(
                strategy_code=strategy.code,
                start_date=datetime.now() - timedelta(days=365 * BACKTEST_YEARS),
                end_date=datetime.now()
            )
            
            if not backtest_results or 'error' in backtest_results:
                return 0.0
            
            # Extract metrics
            total_return = backtest_results.get('total_return', 0)
            sharpe_ratio = backtest_results.get('sharpe_ratio', 0)
            max_drawdown = abs(backtest_results.get('max_drawdown', -1))
            win_rate = backtest_results.get('win_rate', 0)
            num_trades = backtest_results.get('num_trades', 0)
            
            # Check minimum requirements
            if num_trades < MIN_TRADES_FOR_VALIDATION:
                return 0.0
            
            if max_drawdown > MAX_DRAWDOWN_THRESHOLD:
                return 0.0
            
            # Multi-objective fitness
            fitness = (
                0.3 * min(total_return / 0.5, 1.0) +  # Normalize to 50% return
                0.3 * min(sharpe_ratio / 2.0, 1.0) +  # Normalize to 2.0 Sharpe
                0.2 * (1 - max_drawdown) +             # Penalize drawdown
                0.2 * win_rate                         # Reward consistency
            )
            
            # Store results
            strategy.backtest_results = backtest_results
            strategy.fitness_score = fitness
            
            return fitness
            
        except Exception as e:
            self.logger.error(f"Strategy evaluation error: {e}")
            return 0.0
    
    def _calculate_diversity(self, population: List) -> float:
        """Calculate genetic diversity of population"""
        if len(population) < 2:
            return 0.0
        
        # Convert to numpy array
        dna_matrix = np.array([ind[:] for ind in population])
        
        # Calculate pairwise distances
        distances = []
        for i in range(len(population)):
            for j in range(i + 1, len(population)):
                dist = np.linalg.norm(dna_matrix[i] - dna_matrix[j])
                distances.append(dist)
        
        # Diversity is average distance
        return np.mean(distances) if distances else 0.0
    
    def _count_novel_strategies(self, population: List) -> int:
        """Count strategies that haven't been seen before"""
        novel_count = 0
        
        for individual in population:
            gene = StrategyGene.from_dna(individual)
            strategy_hash = hashlib.md5(str(gene).encode()).hexdigest()
            
            if strategy_hash not in self.strategy_db:
                novel_count += 1
        
        return novel_count
    
    # ==========================================================================
    # PATTERN LEARNING
    # ==========================================================================
    
    def _save_successful_pattern(self, strategy: GeneratedStrategy) -> None:
        """Save successful strategy pattern for future learning"""
        if strategy.fitness_score > 0.7:  # High fitness threshold
            self.successful_patterns[strategy.gene.strategy_type].append(strategy.gene)
            
            # Keep only best patterns
            if len(self.successful_patterns[strategy.gene.strategy_type]) > 20:
                # Sort by fitness and keep top 20
                patterns = self.successful_patterns[strategy.gene.strategy_type]
                patterns.sort(key=lambda g: getattr(g, 'fitness', 0), reverse=True)
                self.successful_patterns[strategy.gene.strategy_type] = patterns[:20]
    
    async def analyze_successful_strategies(self) -> Dict[str, Any]:
        """Analyze patterns in successful strategies"""
        analysis = {
            'common_entry_conditions': defaultdict(int),
            'common_exit_conditions': defaultdict(int),
            'optimal_risk_params': defaultdict(list),
            'strategy_type_performance': defaultdict(list),
            'condition_correlations': {}
        }
        
        # Analyze all successful patterns
        for strategy_type, patterns in self.successful_patterns.items():
            for pattern in patterns:
                # Count condition frequency
                for condition in pattern.entry_conditions:
                    analysis['common_entry_conditions'][condition] += 1
                
                for condition in pattern.exit_conditions:
                    analysis['common_exit_conditions'][condition] += 1
                
                # Collect risk parameters
                for param, value in pattern.risk_params.items():
                    analysis['optimal_risk_params'][param].append(value)
        
        # Calculate averages and insights
        insights = {
            'top_entry_conditions': sorted(
                analysis['common_entry_conditions'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'top_exit_conditions': sorted(
                analysis['common_exit_conditions'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'optimal_risk_ranges': {
                param: {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values)
                }
                for param, values in analysis['optimal_risk_params'].items()
                if values
            }
        }
        
        return insights
    
    # ==========================================================================
    # STRATEGY DEPLOYMENT
    # ==========================================================================
    
    async def deploy_strategy(self, strategy: GeneratedStrategy) -> bool:
        """
        Deploy a generated strategy to production.
        
        Args:
            strategy: Strategy to deploy
            
        Returns:
            Success status
        """
        try:
            # Final validation
            if strategy.fitness_score < MIN_FITNESS_THRESHOLD:
                self.logger.warning(f"Strategy {strategy.name} fitness too low for deployment")
                return False
            
            # Save strategy code
            strategy_file = Path(f"SpyderD_Strategies/Generated/{strategy.id}.py")
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(strategy_file, 'w') as f:
                f.write(strategy.code)
            
            # Update strategy database
            self.strategy_db[strategy.id] = strategy
            self._save_strategy_database()
            
            # Log deployment
            self.logger.info(
                f"✅ Deployed strategy {strategy.name} "
                f"(fitness: {strategy.fitness_score:.3f})"
            )
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'deploy_strategy',
                'strategy': strategy.name
            })
            return False
    
    # ==========================================================================
    # PERSISTENCE
    # ==========================================================================
    
    def _save_strategy_database(self) -> None:
        """Save strategy database to disk"""
        try:
            db_path = Path(STRATEGY_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare data for serialization
            db_data = {
                'strategies': {
                    sid: {
                        'id': s.id,
                        'name': s.name,
                        'gene': s.gene.__dict__,
                        'fitness_score': s.fitness_score,
                        'generation': s.generation,
                        'creation_date': s.creation_date.isoformat()
                    }
                    for sid, s in self.strategy_db.items()
                },
                'successful_patterns': {
                    stype: [g.__dict__ for g in patterns]
                    for stype, patterns in self.successful_patterns.items()
                },
                'generation_history': [
                    {
                        'generation': m.generation,
                        'best_fitness': m.best_fitness,
                        'avg_fitness': m.avg_fitness,
                        'diversity_score': m.diversity_score
                    }
                    for m in self.generation_history[-100:]  # Keep last 100
                ]
            }
            
            with open(db_path, 'w') as f:
                json.dump(db_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save strategy database: {e}")
    
    def _load_strategy_database(self) -> None:
        """Load strategy database from disk"""
        try:
            db_path = Path(STRATEGY_DB_PATH)
            if not db_path.exists():
                return
            
            with open(db_path, 'r') as f:
                db_data = json.load(f)
            
            # Reconstruct strategies
            for sid, sdata in db_data.get('strategies', {}).items():
                gene_data = sdata['gene']
                gene = StrategyGene(**gene_data)
                
                strategy = GeneratedStrategy(
                    id=sdata['id'],
                    name=sdata['name'],
                    gene=gene,
                    code="",  # Code not stored in JSON
                    fitness_score=sdata['fitness_score'],
                    generation=sdata['generation'],
                    creation_date=datetime.fromisoformat(sdata['creation_date'])
                )
                
                self.strategy_db[sid] = strategy
            
            # Reconstruct patterns
            for stype, patterns in db_data.get('successful_patterns', {}).items():
                self.successful_patterns[stype] = [
                    StrategyGene(**p) for p in patterns
                ]
            
            self.logger.info(f"Loaded {len(self.strategy_db)} strategies from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load strategy database: {e}")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def get_best_strategies(self, count: int = 10) -> List[GeneratedStrategy]:
        """Get top performing strategies"""
        sorted_strategies = sorted(
            self.strategy_db.values(),
            key=lambda s: s.fitness_score,
            reverse=True
        )
        return sorted_strategies[:count]
    
    def get_evolution_report(self) -> Dict[str, Any]:
        """Get comprehensive evolution report"""
        if not self.generation_history:
            return {}
        
        latest = self.generation_history[-1]
        
        return {
            'total_strategies_generated': len(self.strategy_db),
            'generations_completed': len(self.generation_history),
            'current_best_fitness': latest.best_fitness,
            'current_avg_fitness': latest.avg_fitness,
            'population_diversity': latest.diversity_score,
            'novel_strategies_last_gen': latest.novel_strategies,
            'top_strategies': [
                {
                    'name': s.name,
                    'type': s.gene.strategy_type,
                    'fitness': s.fitness_score,
                    'generation': s.generation
                }
                for s in self.get_best_strategies(5)
            ],
            'pattern_insights': asyncio.run(self.analyze_successful_strategies())
        }

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: Optional[SpyderX15_StrategyGeneratorAgent] = None

def create_strategy_generator_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX15_StrategyGeneratorAgent:
    """Factory function to create strategy generator agent"""
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX15_StrategyGeneratorAgent(config)
    return _module_instance

def get_strategy_generator_agent() -> Optional[SpyderX15_StrategyGeneratorAgent]:
    """Get existing strategy generator instance"""
    return _module_instance

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test strategy generation functionality"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Strategy Generator Agent')
    parser.add_argument('--generate', type=int, help='Generate N new strategies')
    parser.add_argument('--evolve', type=int, help='Evolve for N generations')
    parser.add_argument('--report', action='store_true', help='Show evolution report')
    parser.add_argument('--deploy-best', action='store_true', help='Deploy best strategy')
    args = parser.parse_args()
    
    generator = create_strategy_generator_agent()
    
    if args.generate:
        print(f"\n=== Generating {args.generate} New Strategies ===")
        strategies = await generator.generate_new_strategies(args.generate)
        
        for strategy in strategies:
            print(f"\nStrategy: {strategy.name}")
            print(f"Type: {strategy.gene.strategy_type}")
            print(f"Entry Conditions: {', '.join(strategy.gene.entry_conditions)}")
            print(f"Exit Conditions: {', '.join(strategy.gene.exit_conditions)}")
    
    if args.evolve:
        print(f"\n=== Evolving Strategies for {args.evolve} Generations ===")
        evolved = await generator.evolve_strategies(generations=args.evolve)
        
        print(f"\nEvolved {len(evolved)} elite strategies")
        for strategy in evolved[:5]:
            print(f"\n{strategy.name}:")
            print(f"  Fitness: {strategy.fitness_score:.3f}")
            print(f"  Type: {strategy.gene.strategy_type}")
    
    if args.report:
        print("\n=== Evolution Report ===")
        report = generator.get_evolution_report()
        
        print(f"Total Strategies: {report.get('total_strategies_generated', 0)}")
        print(f"Generations: {report.get('generations_completed', 0)}")
        print(f"Best Fitness: {report.get('current_best_fitness', 0):.3f}")
        print(f"Avg Fitness: {report.get('current_avg_fitness', 0):.3f}")
        print(f"Diversity: {report.get('population_diversity', 0):.3f}")
        
        if 'top_strategies' in report:
            print("\nTop Strategies:")
            for s in report['top_strategies']:
                print(f"  {s['name']} ({s['type']}): {s['fitness']:.3f}")
        
        if 'pattern_insights' in report:
            insights = report['pattern_insights']
            print("\nTop Entry Conditions:")
            for condition, count in insights.get('top_entry_conditions', []):
                print(f"  {condition}: {count}")
    
    if args.deploy_best:
        best = generator.get_best_strategies(1)
        if best:
            print(f"\n=== Deploying Best Strategy ===")
            success = await generator.deploy_strategy(best[0])
            if success:
                print(f"✅ Successfully deployed {best[0].name}")
            else:
                print(f"❌ Failed to deploy {best[0].name}")

if __name__ == "__main__":
    asyncio.run(main())
