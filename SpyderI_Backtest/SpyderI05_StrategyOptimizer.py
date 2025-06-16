#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI03_StrategyOptimizer.py
Group: I (Backtesting)
Purpose: Parameter optimization for LOGIC BOUNDARIES ONLY

═══════════════════════════════════════════════════════════════════════
⚠️ ⚠️ ⚠️  CRITICAL WARNING - READ BEFORE USING  ⚠️ ⚠️ ⚠️
═══════════════════════════════════════════════════════════════════════

This optimizer uses UNREALISTIC backtesting data!
It CANNOT find optimal parameters for real trading!

WHY OPTIMIZATION ON FAKE DATA FAILS:
❌ Optimizes for fake bid-ask spreads (real spreads kill profits)
❌ Assumes perfect fills (real fills have slippage)
❌ Ignores liquidity constraints (can't exit when you want)
❌ No assignment risk modeling (early assignment ruins strategies)
❌ Perfect hindsight bias (curve-fitting to noise)
❌ Greeks behavior is simplified (real Greeks are complex)

USE THIS ONLY TO:
✅ Find rough parameter boundaries (e.g., position size 1-5%)
✅ Test optimization code functionality
✅ Understand parameter relationships
✅ Debug the optimization process

FOR REAL OPTIMIZATION:
Use SpyderL07_PaperTradeLearner.py after 4+ weeks of paper trading!
It optimizes based on ACTUAL market behavior and real fills.

═══════════════════════════════════════════════════════════════════════

Author: Mohamed Talib
Date: 2025-05-30
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
import json
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy.optimize import differential_evolution, minimize
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderI_Backtest.SpyderI01_BacktestEngine import BacktestEngine, BacktestConfig
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy

# ==============================================================================
# CONSTANTS
# ==============================================================================
OPTIMIZER_WARNING = """
╔════════════════════════════════════════════════════════════════════════╗
║                  ⚠️  PARAMETER OPTIMIZER WARNING ⚠️                      ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║ This optimizer uses FAKE BACKTESTING DATA and CANNOT find             ║
║ optimal parameters for real options trading!                           ║
║                                                                        ║
║ Real options trading has:                                              ║
║ • Bid-ask spreads that eat 20-50% of theoretical profit               ║
║ • Liquidity issues preventing exits at desired prices                 ║
║ • Assignment risk that disrupts multi-leg strategies                  ║
║ • Market makers who adjust spreads against you                        ║
║ • Greeks that behave differently in fast markets                      ║
║                                                                        ║
║ Parameters "optimized" here will likely LOSE MONEY in real trading!   ║
║                                                                        ║
║ For REAL optimization:                                                 ║
║ 1. Paper trade for 4-8 weeks                                          ║
║ 2. Use SpyderL07_PaperTradeLearner.py                                ║
║ 3. Optimize based on ACTUAL fills and market behavior                 ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
"""

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class ParameterDefinition:
    """Parameter to optimize - but results are UNREALISTIC"""
    name: str
    min_value: float
    max_value: float
    step: Optional[float] = None
    parameter_type: type = float
    
    # Warning about parameter
    is_realistic: bool = False
    warning: str = "Optimized on fake data - not valid for real trading!"

class OptimizationResult:
    """Optimization results - FOR BOUNDARY TESTING ONLY"""
    # Big warning
    warning: str = field(default=OPTIMIZER_WARNING)
    is_valid_for_trading: bool = field(default=False)
    
    # Parameters found (unrealistic)
    best_params: Dict[str, Any] = field(default_factory=dict)
    fake_performance: float = 0.0  # Emphasize it's fake
    
    # Boundary information (somewhat useful)
    param_boundaries: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    sensitivity_analysis: Dict[str, float] = field(default_factory=dict)
    
    # Debug info
    iterations: int = 0
    convergence: bool = False
    optimization_time: float = 0.0
    
    # All trials (for analysis)
    all_trials: List[Dict[str, Any]] = field(default_factory=list)
    
    def print_warning(self):
        """Print prominent warning"""
        print("\n" + "="*80)
        print(self.warning)
        print("="*80)
        print("\nThese parameters are based on FAKE DATA!")
        print("Do NOT use them for real trading!")
        print("Use paper trading results for real optimization!")
        print("="*80 + "\n")

# ==============================================================================
# STRATEGY OPTIMIZER CLASS
# ==============================================================================
class StrategyOptimizer:
    """
    Parameter optimizer for FINDING ROUGH BOUNDARIES ONLY.
    
    ⚠️ WARNING: This does NOT find optimal trading parameters!
    
    The "optimal" parameters found here will likely lose money because:
    - Based on unrealistic backtesting
    - Ignores real market microstructure
    - Overfits to fake data patterns
    - Doesn't account for execution realities
    
    Use this ONLY to:
    - Find reasonable parameter ranges
    - Test optimization code
    - Understand parameter relationships
    
    For REAL optimization, use paper trading data!
    """
    
    def __init__(self, backtest_config: BacktestConfig):
        """
        Initialize optimizer for LOGIC TESTING.
        
        Args:
            backtest_config: Backtesting configuration
        """
        self.config = backtest_config
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Print warning
        print(OPTIMIZER_WARNING)
        warnings.warn(
            "StrategyOptimizer uses FAKE data - results not valid for trading!",
            UserWarning,
            stacklevel=2
        )
        
        self.logger.warning("StrategyOptimizer initialized - FOR BOUNDARY TESTING ONLY!")
        self.logger.warning("Do NOT use results for real trading decisions!")
        
        # Track optimization progress
        self.trial_count = 0
        self.best_fake_score = float('-inf')
        self.all_trials = []
    
    # ==========================================================================
    # OPTIMIZATION METHODS (FOR BOUNDARIES ONLY)
    # ==========================================================================
    def find_parameter_boundaries(
        self,
        strategy: BaseStrategy,
        parameters: List[ParameterDefinition],
        n_trials: int = 100,
        optimization_metric: str = 'fake_sharpe'  # Emphasize it's fake
    ) -> OptimizationResult:
        """
        Find rough parameter boundaries using FAKE DATA.
        
        ⚠️ Results are NOT valid for real trading!
        
        Args:
            strategy: Strategy to test
            parameters: Parameters to explore
            n_trials: Number of trials
            optimization_metric: Metric to optimize (all fake)
            
        Returns:
            OptimizationResult with boundaries and warnings
        """
        self.logger.warning(f"Starting BOUNDARY SEARCH for {strategy.__class__.__name__}")
        self.logger.warning("Results based on FAKE DATA - not valid for trading!")
        
        result = OptimizationResult()
        result.print_warning()  # Show warning immediately
        
        # Store boundaries
        for param in parameters:
            result.param_boundaries[param.name] = (param.min_value, param.max_value)
        
        # Run optimization (results are meaningless for real trading)
        start_time = datetime.datetime.now()
        
        try:
            # Use Optuna for boundary exploration
            study = optuna.create_study(
                direction='maximize',
                study_name='FAKE_BOUNDARY_TEST'
            )
            
            # Objective function
            def fake_objective(trial):
                # Sample parameters
                params = {}
                for param_def in parameters:
                    if param_def.parameter_type == float:
                        params[param_def.name] = trial.suggest_float(
                            param_def.name,
                            param_def.min_value,
                            param_def.max_value,
                            step=param_def.step
                        )
                    elif param_def.parameter_type == int:
                        params[param_def.name] = trial.suggest_int(
                            param_def.name,
                            int(param_def.min_value),
                            int(param_def.max_value),
                            step=int(param_def.step) if param_def.step else 1
                        )
                
                # Run fake backtest
                fake_score = self._run_fake_backtest(strategy, params, optimization_metric)
                
                # Store trial
                self.all_trials.append({
                    'params': params.copy(),
                    'fake_score': fake_score,
                    'warning': 'Based on fake data!'
                })
                
                return fake_score
            
            # Optimize
            study.optimize(fake_objective, n_trials=n_trials, n_jobs=1)
            
            # Get results (but they're fake!)
            result.best_params = study.best_params
            result.fake_performance = study.best_value
            result.iterations = len(study.trials)
            result.all_trials = self.all_trials
            
            # Sensitivity analysis (on fake data)
            result.sensitivity_analysis = self._analyze_fake_sensitivity(parameters)
            
        except Exception as e:
            self.logger.error(f"Error in boundary search: {e}")
            self.error_handler.handle_error(e)
        
        # Calculate time
        result.optimization_time = (datetime.datetime.now() - start_time).total_seconds()
        
        # Print summary
        self._print_boundary_summary(result)
        
        return result
    
    def test_parameter_grid(
        self,
        strategy: BaseStrategy,
        param_grid: Dict[str, List[float]]
    ) -> pd.DataFrame:
        """
        Test parameter grid for LOGIC VALIDATION ONLY.
        
        Args:
            strategy: Strategy to test
            param_grid: Grid of parameters to test
            
        Returns:
            DataFrame of results (all based on fake data)
        """
        self.logger.warning("Testing parameter grid on FAKE DATA")
        
        results = []
        
        # Generate all combinations
        import itertools
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        for combination in itertools.product(*values):
            params = dict(zip(keys, combination))
            
            # Run fake test
            fake_score = self._run_fake_backtest(strategy, params, 'fake_return')
            
            results.append({
                **params,
                'fake_score': fake_score,
                'is_realistic': False,
                'warning': 'Based on fake data - not valid for trading!'
            })
        
        df = pd.DataFrame(results)
        
        # Add warning to DataFrame
        df.attrs['warning'] = "ALL RESULTS BASED ON FAKE DATA - DO NOT USE FOR TRADING!"
        
        return df
    
    # ==========================================================================
    # FAKE BACKTEST RUNNER
    # ==========================================================================
    def _run_fake_backtest(
        self,
        strategy: BaseStrategy,
        params: Dict[str, Any],
        metric: str
    ) -> float:
        """
        Run fake backtest for parameter testing.
        
        Returns fake performance metric.
        """
        # Apply parameters to strategy
        for param_name, param_value in params.items():
            if hasattr(strategy, param_name):
                setattr(strategy, param_name, param_value)
        
        # Create fake backtest
        test_config = BacktestConfig(
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            initial_capital=self.config.initial_capital,
            strategies=[strategy],
            logic_testing_only=True  # Emphasize it's for testing
        )
        
        # Run fake backtest
        engine = BacktestEngine(test_config)
        fake_results = engine.run()
        
        # Return fake metric
        if metric == 'fake_sharpe':
            # Fake Sharpe ratio
            returns = fake_results.equity_curve.pct_change().dropna()
            if len(returns) > 0:
                return returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
            return 0.0
        elif metric == 'fake_return':
            # Fake return
            return fake_results.total_return
        else:
            return 0.0
    
    # ==========================================================================
    # ANALYSIS METHODS (ON FAKE DATA)
    # ==========================================================================
    def _analyze_fake_sensitivity(
        self,
        parameters: List[ParameterDefinition]
    ) -> Dict[str, float]:
        """
        Analyze parameter sensitivity using FAKE DATA.
        
        Results show which parameters affect fake performance most.
        NOT indicative of real trading behavior!
        """
        if not self.all_trials:
            return {}
        
        sensitivity = {}
        
        for param in parameters:
            param_values = [t['params'].get(param.name, 0) for t in self.all_trials]
            fake_scores = [t['fake_score'] for t in self.all_trials]
            
            if len(set(param_values)) > 1:
                # Calculate fake correlation
                correlation = np.corrcoef(param_values, fake_scores)[0, 1]
                sensitivity[param.name] = abs(correlation)
            else:
                sensitivity[param.name] = 0.0
        
        return sensitivity
    
    # ==========================================================================
    # REPORTING
    # ==========================================================================
    def _print_boundary_summary(self, result: OptimizationResult) -> None:
        """Print summary of boundary exploration"""
        print("\n" + "="*80)
        print("PARAMETER BOUNDARY EXPLORATION RESULTS")
        print("⚠️  BASED ON FAKE DATA - NOT VALID FOR TRADING! ⚠️")
        print("="*80)
        
        print("\nParameter Boundaries Tested:")
        for param, (min_val, max_val) in result.param_boundaries.items():
            print(f"  {param}: {min_val:.4f} to {max_val:.4f}")
        
        print("\nFake 'Optimal' Parameters (DO NOT USE FOR TRADING):")
        for param, value in result.best_params.items():
            print(f"  {param}: {value:.4f} ⚠️")
        
        print(f"\nFake Performance Score: {result.fake_performance:.4f}")
        print("(This score is meaningless for real trading!)")
        
        if result.sensitivity_analysis:
            print("\nParameter Sensitivity (on fake data):")
            sorted_sensitivity = sorted(
                result.sensitivity_analysis.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for param, sensitivity in sorted_sensitivity:
                print(f"  {param}: {sensitivity:.3f}")
        
        print("\n" + "="*80)
        print("NEXT STEPS:")
        print("1. Use these boundaries as rough starting points only")
        print("2. Start paper trading with conservative parameters")
        print("3. Use SpyderL07_PaperTradeLearner.py for REAL optimization")
        print("4. Only trust parameters validated by actual trading!")
        print("="*80 + "\n")
    
    def export_fake_results(self, result: OptimizationResult, filename: str) -> None:
        """Export fake results with prominent warnings"""
        data = {
            'WARNING': OPTIMIZER_WARNING,
            'is_valid_for_trading': False,
            'based_on': 'FAKE_BACKTESTING_DATA',
            'boundaries_tested': result.param_boundaries,
            'fake_best_params': result.best_params,
            'fake_performance': result.fake_performance,
            'sensitivity_on_fake_data': result.sensitivity_analysis,
            'all_fake_trials': result.all_trials,
            'REMINDER': 'USE PAPER TRADING FOR REAL OPTIMIZATION!'
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\nFake results exported to {filename}")
        print("Remember: These are NOT valid for real trading!")

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================
def test_optimization_logic(strategy: BaseStrategy) -> None:
    """
    Test optimization logic only.
    
    This validates that the optimization code works,
    but results are NOT valid for trading!
    """
    print("\n" + "="*80)
    print("TESTING OPTIMIZATION LOGIC ONLY")
    print("Results are based on FAKE DATA and NOT valid for trading!")
    print("="*80 + "\n")
    
    # Define test parameters
    test_params = [
        ParameterDefinition('position_size', 0.01, 0.05, 0.01),
        ParameterDefinition('stop_loss', 0.05, 0.20, 0.05),
        ParameterDefinition('take_profit', 0.10, 0.50, 0.10)
    ]
    
    # Create test config
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=30)
    
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        strategies=[strategy],
        logic_testing_only=True
    )
    
    # Run boundary test
    optimizer = StrategyOptimizer(config)
    result = optimizer.find_parameter_boundaries(
        strategy,
        test_params,
        n_trials=20  # Few trials for logic testing
    )
    
    print("\nLogic test complete!")
    print("For REAL optimization, use paper trading data!")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print(OPTIMIZER_WARNING)
    print("\nThis module is for PARAMETER BOUNDARY TESTING ONLY!")
    print("Real optimization requires paper trading data.")
    print("See SpyderL07_PaperTradeLearner.py for actual optimization.\n")
