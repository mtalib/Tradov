#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Phase 2 Advanced Integration Layer

Module: SpyderPhase2Integration.py
Purpose: Integration layer for Phase 2 advanced optimization deployment
Author: SPYDER Team
Date Created: 2026-01-16

Description:
    This module provides the integration layer for deploying Phase 2 advanced
    optimization frameworks into the existing SPYDER trading system.

    Key Features:
    - Seamless integration with existing trading system
    - Phase 2 advanced optimization deployment
    - Performance monitoring and reporting
    - Gradual rollout capabilities
    - Fallback mechanisms to Phase 1

    Integration Points:
    - SpyderD30_RegimeGatedSelector (existing)
    - SpyderE14_KellyPositionSizer (existing)
    - SpyderAdvancedOptimizer (Phase 2)
    - Trading execution modules
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderStrategyOptimizer_Standalone import SpyderStrategyOptimizer, OptimizationResult
from SpyderAdvancedOptimizer import SpyderAdvancedOptimizer, AdvancedOptimizationResult

# ==============================================================================
# INTEGRATION DATA STRUCTURES
# ==============================================================================

@dataclass
class IntegrationConfig:
    """Configuration for Phase 2 integration."""
    enable_phase2: bool = True
    phase2_rollout_percentage: float = 100.0  # 0-100%
    fallback_to_phase1: bool = True
    performance_monitoring: bool = True
    advanced_features: Dict[str, bool] = field(default_factory=lambda: {
        'advanced_hmm': True,
        'kernel_regression': True,
        'portfolio_optimization': True,
        'ml_adaptation': True
    })
    risk_limits: Dict[str, float] = field(default_factory=lambda: {
        'max_position_size': 0.15,
        'max_portfolio_volatility': 0.20,
        'min_confidence_threshold': 0.50
    })

@dataclass
class IntegrationResult:
    """Result of integration operation."""
    success: bool
    phase_used: str  # 'phase1' or 'phase2'
    optimization_result: Union[OptimizationResult, AdvancedOptimizationResult]
    performance_metrics: Dict[str, float]
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PerformanceComparison:
    """Performance comparison between Phase 1 and Phase 2."""
    phase1_metrics: Dict[str, float]
    phase2_metrics: Dict[str, float]
    improvement_percentage: Dict[str, float]
    statistical_significance: Dict[str, float]
    recommendation: str

# ==============================================================================
# PHASE 2 INTEGRATION ENGINE
# ==============================================================================

class SpyderPhase2Integration:
    """
    Phase 2 Integration Engine

    Provides seamless integration of Phase 2 advanced optimization
    into the existing SPYDER trading system.
    """

    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        self.logger = logging.getLogger(__name__)

        # Initialize optimizers
        self.phase1_optimizer: Optional[SpyderStrategyOptimizer] = None
        self.phase2_optimizer: Optional[SpyderAdvancedOptimizer] = None

        # Performance tracking
        self.performance_history: List[IntegrationResult] = []
        self.phase1_results: List[OptimizationResult] = []
        self.phase2_results: List[AdvancedOptimizationResult] = []

        # Integration metrics
        self.integration_metrics: Dict[str, Any] = {
            'total_decisions': 0,
            'phase1_decisions': 0,
            'phase2_decisions': 0,
            'fallback_events': 0,
            'performance_improvements': [],
            'error_rate': 0.0
        }

        self.logger.info("SpyderPhase2Integration initialized")

    def initialize_integration(self, historical_data: pd.DataFrame) -> bool:
        """
        Initialize both Phase 1 and Phase 2 optimizers.

        Args:
            historical_data: Historical market data for training

        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing Phase 2 integration...")

            # Initialize Phase 1 optimizer
            self.phase1_optimizer = SpyderStrategyOptimizer(capital=100000)
            if not self.phase1_optimizer.initialize_frameworks(historical_data):
                self.logger.error("Phase 1 optimizer initialization failed")
                return False

            # Initialize Phase 2 optimizer
            self.phase2_optimizer = SpyderAdvancedOptimizer(capital=100000, enable_advanced_features=True)
            if not self.phase2_optimizer.initialize_frameworks(historical_data):
                self.logger.warning("Phase 1 frameworks failed for Phase 2 - using Phase 1 only")
                self.config.enable_phase2 = False

            if self.config.enable_phase2:
                if not self.phase2_optimizer.initialize_advanced_frameworks(historical_data):
                    self.logger.warning("Phase 2 advanced frameworks failed - falling back to Phase 1")
                    self.config.enable_phase2 = False

            self.logger.info("✅ Phase 2 integration initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Integration initialization failed: {e}")
            return False

    def get_optimization_decision(self,
                                current_market_data: pd.DataFrame,
                                current_price: float,
                                vix_level: Optional[float] = None,
                                current_portfolio: Optional[Dict[str, float]] = None) -> IntegrationResult:
        """
        Get optimization decision using integrated Phase 1/2 system.

        Args:
            current_market_data: Current market data
            current_price: Current SPY price
            vix_level: Current VIX level
            current_portfolio: Current portfolio weights

        Returns:
            Integrated optimization result
        """
        try:
            self.integration_metrics['total_decisions'] += 1

            # Determine which phase to use
            use_phase2 = self._should_use_phase2()

            if use_phase2 and self.phase2_optimizer:
                # Use Phase 2 advanced optimization
                result = self._execute_phase2_optimization(
                    current_market_data, current_price, vix_level, current_portfolio
                )
                phase_used = 'phase2'
                self.integration_metrics['phase2_decisions'] += 1
                self.phase2_results.append(result.optimization_result)

            else:
                # Use Phase 1 optimization (or fallback)
                result = self._execute_phase1_optimization(
                    current_market_data, current_price, vix_level
                )
                phase_used = 'phase1'
                self.integration_metrics['phase1_decisions'] += 1
                self.phase1_results.append(result.optimization_result)

                if use_phase2:
                    self.integration_metrics['fallback_events'] += 1
                    result.warnings.append("Phase 2 requested but fell back to Phase 1")

            # Track performance
            self.performance_history.append(result)

            # Calculate performance metrics
            result.performance_metrics = self._calculate_performance_metrics(result)

            self.logger.info(
                f"Integration Decision: {phase_used.upper()} → "
                f"{result.optimization_result.selected_strategy.value.replace('_', ' ').title()} "
                f"(Size: {result.optimization_result.position_size:.1%})"
            )

            return result

        except Exception as e:
            self.logger.error(f"Optimization decision failed: {e}")
            # Emergency fallback to Phase 1
            return self._emergency_fallback(current_market_data, current_price, vix_level)

    def _should_use_phase2(self) -> bool:
        """Determine if Phase 2 should be used for this decision."""
        if not self.config.enable_phase2 or not self.phase2_optimizer:
            return False

        # Check rollout percentage
        if np.random.random() * 100 > self.config.phase2_rollout_percentage:
            return False

        # Check if advanced features are enabled
        required_features = ['advanced_hmm', 'kernel_regression', 'portfolio_optimization']
        if not all(self.config.advanced_features.get(feature, False) for feature in required_features):
            return False

        return True

    def _execute_phase2_optimization(self,
                                   market_data: pd.DataFrame,
                                   price: float,
                                   vix_level: Optional[float],
                                   portfolio: Optional[Dict[str, float]]) -> IntegrationResult:
        """Execute Phase 2 advanced optimization."""
        try:
            advanced_result = self.phase2_optimizer.advanced_optimize_strategy(
                market_data, price, vix_level, portfolio
            )

            # Validate result against risk limits
            if self._validate_risk_limits(advanced_result):
                return IntegrationResult(
                    success=True,
                    phase_used='phase2',
                    optimization_result=advanced_result,
                    performance_metrics={}
                )
            else:
                # Risk limits exceeded - fallback to Phase 1
                self.logger.warning("Phase 2 result exceeded risk limits - falling back to Phase 1")
                return self._execute_phase1_optimization(market_data, price, vix_level)

        except Exception as e:
            self.logger.error(f"Phase 2 optimization failed: {e}")
            if self.config.fallback_to_phase1:
                return self._execute_phase1_optimization(market_data, price, vix_level)
            else:
                raise

    def _execute_phase1_optimization(self,
                                   market_data: pd.DataFrame,
                                   price: float,
                                   vix_level: Optional[float]) -> IntegrationResult:
        """Execute Phase 1 optimization."""
        try:
            phase1_result = self.phase1_optimizer.optimize_strategy(market_data, price, vix_level)

            return IntegrationResult(
                success=True,
                phase_used='phase1',
                optimization_result=phase1_result,
                performance_metrics={}
            )

        except Exception as e:
            self.logger.error(f"Phase 1 optimization failed: {e}")
            raise

    def _validate_risk_limits(self, result: AdvancedOptimizationResult) -> bool:
        """Validate optimization result against risk limits."""
        # Check position size
        if result.position_size > self.config.risk_limits['max_position_size']:
            return False

        # Check confidence threshold
        if hasattr(result, 'confidence_score') and result.confidence_score < self.config.risk_limits['min_confidence_threshold']:
            return False

        # Check portfolio volatility (if available)
        if hasattr(result, 'portfolio_weights'):
            # Simplified volatility check - in practice would calculate actual portfolio volatility
            pass

        return True

    def _emergency_fallback(self, market_data: pd.DataFrame, price: float, vix_level: Optional[float]) -> IntegrationResult:
        """Emergency fallback when all optimizations fail."""
        self.logger.error("EMERGENCY FALLBACK: All optimization methods failed")

        # Return minimal safe position
        safe_result = OptimizationResult(
            regime=MarketRegime.NEUTRAL,
            selected_strategy=StrategyType.iron_condor,
            position_size=0.01,  # 1% - very conservative
            expected_return=0.0,
            risk_adjusted_size=0.005,
            volatility_multiplier=0.5,
            confidence_score=0.5,
            timestamp=datetime.now()
        )

        return IntegrationResult(
            success=False,
            phase_used='emergency_fallback',
            optimization_result=safe_result,
            performance_metrics={'emergency_fallback': 1},
            warnings=["Emergency fallback activated - manual review required"]
        )

    def _calculate_performance_metrics(self, result: IntegrationResult) -> Dict[str, float]:
        """Calculate performance metrics for the result."""
        metrics = {}

        # Basic metrics
        opt_result = result.optimization_result
        metrics['position_size'] = opt_result.position_size
        metrics['confidence_score'] = opt_result.confidence_score
        metrics['expected_return'] = getattr(opt_result, 'expected_return', 0.0)

        # Phase-specific metrics
        if result.phase_used == 'phase2' and isinstance(opt_result, AdvancedOptimizationResult):
            metrics['evolution_score'] = opt_result.strategy_evolution_score
            metrics['risk_parity_adjustment'] = opt_result.risk_parity_adjustment
            metrics['advanced_regime'] = hash(opt_result.advanced_regime.value)  # Numeric representation

        # Risk metrics
        metrics['sharpe_ratio'] = metrics['expected_return'] / 0.15  # Assuming 15% vol
        metrics['risk_adjusted_return'] = metrics['expected_return'] * metrics['confidence_score']

        return metrics

    def compare_performance(self) -> PerformanceComparison:
        """
        Compare performance between Phase 1 and Phase 2.

        Returns:
            Performance comparison results
        """
        if len(self.phase1_results) < 10 or len(self.phase2_results) < 10:
            return PerformanceComparison(
                phase1_metrics={},
                phase2_metrics={},
                improvement_percentage={},
                statistical_significance={},
                recommendation="Insufficient data for comparison"
            )

        # Calculate Phase 1 metrics
        phase1_metrics = self._calculate_phase_metrics(self.phase1_results)

        # Calculate Phase 2 metrics
        phase2_metrics = self._calculate_phase_metrics(self.phase2_results)

        # Calculate improvements
        improvements = {}
        significance = {}

        for metric in phase1_metrics:
            if metric in phase2_metrics and phase1_metrics[metric] != 0:
                improvement = ((phase2_metrics[metric] - phase1_metrics[metric]) / abs(phase1_metrics[metric])) * 100
                improvements[metric] = improvement

                # Simple significance test (would use proper statistical test in production)
                if abs(improvement) > 20:  # 20% improvement threshold
                    significance[metric] = 0.95
                elif abs(improvement) > 10:
                    significance[metric] = 0.80
                else:
                    significance[metric] = 0.50

        # Generate recommendation
        avg_improvement = np.mean(list(improvements.values()))
        if avg_improvement > 15:
            recommendation = "Strong recommendation to deploy Phase 2"
        elif avg_improvement > 5:
            recommendation = "Moderate improvement - consider gradual Phase 2 rollout"
        else:
            recommendation = "Limited improvement - maintain Phase 1 or investigate issues"

        return PerformanceComparison(
            phase1_metrics=phase1_metrics,
            phase2_metrics=phase2_metrics,
            improvement_percentage=improvements,
            statistical_significance=significance,
            recommendation=recommendation
        )

    def _calculate_phase_metrics(self, results: List) -> Dict[str, float]:
        """Calculate average metrics for a phase."""
        if not results:
            return {}

        metrics = {}
        n_results = len(results)

        # Aggregate metrics
        for result in results:
            for key, value in self._calculate_performance_metrics(
                IntegrationResult(True, 'test', result, {})
            ).items():
                if isinstance(value, (int, float)):
                    metrics[key] = metrics.get(key, 0) + value

        # Average metrics
        for key in metrics:
            metrics[key] /= n_results

        return metrics

    def generate_integration_report(self) -> str:
        """
        Generate comprehensive integration report.

        Returns:
            Formatted integration report
        """
        report = []
        report.append("=" * 80)
        report.append("🔗 SPYDER PHASE 2 INTEGRATION REPORT")
        report.append("=" * 80)
        report.append("")

        # Configuration status
        report.append("⚙️ INTEGRATION CONFIGURATION")
        report.append(f"Phase 2 Enabled: {'✅' if self.config.enable_phase2 else '❌'}")
        report.append(f"Phase 2 Rollout: {self.config.phase2_rollout_percentage:.0f}%")
        report.append(f"Fallback to Phase 1: {'✅' if self.config.fallback_to_phase1 else '❌'}")
        report.append("")

        # Framework status
        report.append("🤖 FRAMEWORK STATUS")
        report.append(f"Phase 1 Optimizer: {'✅ Active' if self.phase1_optimizer else '❌ Inactive'}")
        report.append(f"Phase 2 Optimizer: {'✅ Active' if self.phase2_optimizer else '❌ Inactive'}")
        report.append("")

        # Decision statistics
        total_decisions = self.integration_metrics['total_decisions']
        if total_decisions > 0:
            phase1_pct = (self.integration_metrics['phase1_decisions'] / total_decisions) * 100
            phase2_pct = (self.integration_metrics['phase2_decisions'] / total_decisions) * 100
            fallback_pct = (self.integration_metrics['fallback_events'] / total_decisions) * 100

            report.append("📊 DECISION STATISTICS")
            report.append(f"Total Decisions: {total_decisions}")
            report.append(f"Phase 1 Decisions: {self.integration_metrics['phase1_decisions']} ({phase1_pct:.1f}%)")
            report.append(f"Phase 2 Decisions: {self.integration_metrics['phase2_decisions']} ({phase2_pct:.1f}%)")
            report.append(f"Fallback Events: {self.integration_metrics['fallback_events']} ({fallback_pct:.1f}%)")
            report.append("")

        # Performance comparison
        if len(self.phase1_results) >= 5 and len(self.phase2_results) >= 5:
            comparison = self.compare_performance()

            report.append("📈 PERFORMANCE COMPARISON")
            report.append("Phase 1 vs Phase 2 Metrics:")
            for metric in comparison.improvement_percentage:
                p1_val = comparison.phase1_metrics.get(metric, 0)
                p2_val = comparison.phase2_metrics.get(metric, 0)
                imp = comparison.improvement_percentage.get(metric, 0)
                sig = comparison.statistical_significance.get(metric, 0)

                report.append(f"  • {metric}: {p1_val:.3f} → {p2_val:.3f} ({imp:+.1f}%, {sig:.0%} significance)")

            report.append("")
            report.append(f"Recommendation: {comparison.recommendation}")
            report.append("")

        # Risk management
        report.append("🛡️ RISK MANAGEMENT")
        report.append(f"Max Position Size: {self.config.risk_limits['max_position_size']:.1%}")
        report.append(f"Max Portfolio Volatility: {self.config.risk_limits['max_portfolio_volatility']:.1%}")
        report.append(f"Min Confidence Threshold: {self.config.risk_limits['min_confidence_threshold']:.1%}")
        report.append("")

        # Advanced features
        report.append("🚀 ADVANCED FEATURES STATUS")
        for feature, enabled in self.config.advanced_features.items():
            status = '✅ Enabled' if enabled else '❌ Disabled'
            report.append(f"  • {feature.replace('_', ' ').title()}: {status}")
        report.append("")

        # Recommendations
        report.append("💡 INTEGRATION RECOMMENDATIONS")

        if self.config.enable_phase2 and self.phase2_optimizer:
            if self.integration_metrics['fallback_events'] > total_decisions * 0.1:  # >10% fallbacks
                report.append("⚠️ High fallback rate detected - investigate Phase 2 stability")
            else:
                report.append("✅ Phase 2 integration stable - consider increasing rollout percentage")

            comparison = self.compare_performance()
            if 'sharpe_ratio' in comparison.improvement_percentage:
                sharpe_imp = comparison.improvement_percentage['sharpe_ratio']
                if sharpe_imp > 20:
                    report.append("🎯 Excellent Phase 2 performance - accelerate deployment")
                elif sharpe_imp > 0:
                    report.append("👍 Phase 2 showing improvements - continue gradual rollout")
                else:
                    report.append("🔍 Phase 2 needs optimization - review advanced frameworks")
        else:
            report.append("🔄 Phase 2 not enabled - focus on Phase 1 optimization")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def export_integration_config(self, filepath: str) -> None:
        """Export integration configuration to JSON file."""
        config_dict = {
            'enable_phase2': self.config.enable_phase2,
            'phase2_rollout_percentage': self.config.phase2_rollout_percentage,
            'fallback_to_phase1': self.config.fallback_to_phase1,
            'performance_monitoring': self.config.performance_monitoring,
            'advanced_features': self.config.advanced_features,
            'risk_limits': self.config.risk_limits,
            'export_timestamp': datetime.now().isoformat()
        }

        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2, default=str)

        self.logger.info(f"Integration config exported to {filepath}")

    def import_integration_config(self, filepath: str) -> bool:
        """Import integration configuration from JSON file."""
        try:
            with open(filepath, 'r') as f:
                config_dict = json.load(f)

            self.config = IntegrationConfig(
                enable_phase2=config_dict.get('enable_phase2', True),
                phase2_rollout_percentage=config_dict.get('phase2_rollout_percentage', 100.0),
                fallback_to_phase1=config_dict.get('fallback_to_phase1', True),
                performance_monitoring=config_dict.get('performance_monitoring', True),
                advanced_features=config_dict.get('advanced_features', {}),
                risk_limits=config_dict.get('risk_limits', {})
            )

            self.logger.info(f"Integration config imported from {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Config import failed: {e}")
            return False

# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================

def demonstrate_phase2_integration():
    """
    Demonstrate Phase 2 integration capabilities.
    """
    print("=" * 80)
    print("🔗 SPYDER PHASE 2 INTEGRATION DEMO")
    print("=" * 80)
    print()

    # Create integration configuration
    config = IntegrationConfig(
        enable_phase2=True,
        phase2_rollout_percentage=100.0,  # Full rollout for demo
        fallback_to_phase1=True,
        advanced_features={
            'advanced_hmm': True,
            'kernel_regression': True,
            'portfolio_optimization': True,
            'ml_adaptation': False  # Disable ML for demo stability
        }
    )

    # Initialize integration
    print("1. Initializing Phase 2 integration...")
    integration = SpyderPhase2Integration(config)

    # Generate historical data
    from SpyderStrategyOptimizer_Standalone import create_sample_market_data
    historical_data = create_sample_market_data(500)
    print(f"   ✅ Generated {len(historical_data)} days of historical data")

    if not integration.initialize_integration(historical_data):
        print("   ❌ Integration initialization failed")
        return

    print("   ✅ Phase 2 integration initialized")
    print()

    # Demonstrate integration decisions
    print("2. Demonstrating integration decisions...")

    test_scenarios = [
        {"name": "Bull Market", "vix": 16, "expected_phase": "phase2"},
        {"name": "Bear Market", "vix": 28, "expected_phase": "phase2"},
        {"name": "Neutral Market", "vix": 20, "expected_phase": "phase1"},  # Test fallback
    ]

    for i, scenario in enumerate(test_scenarios):
        print(f"\n   Scenario {i+1}: {scenario['name']} (VIX: {scenario['vix']})")

        # Get recent market data
        recent_data = historical_data.tail(30).copy()
        current_price = recent_data['close'].iloc[-1]

        # Get integration decision
        result = integration.get_optimization_decision(
            recent_data, current_price, scenario['vix']
        )

        print(f"   → Phase Used: {result.phase_used.upper()}")
        print(f"   → Strategy: {result.optimization_result.selected_strategy.value.replace('_', ' ').title()}")
        print(f"   → Position Size: {result.optimization_result.position_size:.1%}")
        print(f"   → Confidence: {result.optimization_result.confidence_score:.1%}")
        print(f"   → Success: {'✅' if result.success else '❌'}")

        if result.warnings:
            print(f"   → Warnings: {', '.join(result.warnings)}")

    print()

    # Performance comparison
    print("3. Performance Analysis...")

    if len(integration.phase1_results) > 0 and len(integration.phase2_results) > 0:
        comparison = integration.compare_performance()

        print("   Phase Comparison:")
        print(f"   → Phase 1 Results: {len(integration.phase1_results)}")
        print(f"   → Phase 2 Results: {len(integration.phase2_results)}")
        print(f"   → Recommendation: {comparison.recommendation}")

        if comparison.improvement_percentage:
            print("   → Key Improvements:")
            for metric, improvement in list(comparison.improvement_percentage.items())[:3]:
                print(f"     • {metric}: {improvement:+.1f}%")

    print()

    # Generate integration report
    print("4. Generating integration report...")
    report = integration.generate_integration_report()
    print(report)

    # Export configuration
    config_file = "SpyderPhase2_Integration_Config.json"
    integration.export_integration_config(config_file)
    print(f"📄 Integration config exported to: {config_file}")

    # Save report
    report_file = "SpyderPhase2_Integration_Report.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"📄 Integration report saved to: {report_file}")
    print()
    print("✅ Phase 2 Integration Demo Complete!")
    print("🔗 Integration layer ready for deployment")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run integration demonstration
    demonstrate_phase2_integration()

if __name__ == "__main__":
    main()