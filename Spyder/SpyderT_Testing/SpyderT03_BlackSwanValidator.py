#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderT03_BlackSwanValidator.py
Group: T (Testing)
Purpose: Comprehensive validation and testing for Black Swan Indicator system
Author: Mohamed Talib
Date Created: 2025-01-15 
Last Updated: 2025-01-15 Time: 13:00:00  

Description:
    This module provides comprehensive testing and validation capabilities for
    the Black Swan Indicator system. It includes unit tests, integration tests,
    performance benchmarks, stress tests, and validation against historical
    events. Ensures all components work correctly and meet performance requirements.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import time
import unittest
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderT_Testing.SpyderT01_UnitTestFramework import SpyderTestFramework
    SPYDER_INTEGRATION = True
except ImportError:
    # Fallback for standalone operation
    import logging
    SpyderLogger = logging
    SpyderErrorHandler = None
    SpyderTestFramework = unittest.TestCase
    SPYDER_INTEGRATION = False

# Import Black Swan modules
from SpyderS06_BlackSwanDataCollector import (
    BlackSwanDataCollector, MarketDataSet, DataQuality, DataSource
)
from SpyderS07_BlackSwanCalculator import (
    BlackSwanCalculator, BlackSwanIndicatorResult, RiskStatus, AlertLevel
)
from SpyderS08_BlackSwanGUI import BlackSwanWidget
from SpyderS09_BlackSwanCLI import BlackSwanCLI
from SpyderS10_BlackSwanOptimizer import BlackSwanOptimizer
from SpyderS11_BlackSwanScheduler import BlackSwanScheduler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Test parameters
TEST_DATA_SIZE = 100
PERFORMANCE_THRESHOLD_MS = 5000  # 5 seconds max for data collection
CALCULATION_THRESHOLD_MS = 100   # 100ms max for calculation

# Validation thresholds
MIN_ACCURACY = 0.80
MIN_PRECISION = 0.60
MIN_RECALL = 0.70

# Test scenarios
TEST_SCENARIOS = [
    {'name': 'Normal Market', 'vix': 15, 'sp500_change': 0.5, 'expected': RiskStatus.GREEN},
    {'name': 'Elevated Volatility', 'vix': 25, 'sp500_change': -1.0, 'expected': RiskStatus.YELLOW},
    {'name': 'Market Stress', 'vix': 35, 'sp500_change': -3.0, 'expected': RiskStatus.RED},
    {'name': 'Extreme Conditions', 'vix': 60, 'sp500_change': -7.0, 'expected': RiskStatus.RED},
    {'name': 'Recovery Phase', 'vix': 22, 'sp500_change': 2.0, 'expected': RiskStatus.GREEN}
]

# ==============================================================================
# ENUMS
# ==============================================================================
class TestType(Enum):
    """Types of tests"""
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    STRESS = "stress"
    VALIDATION = "validation"

class TestResult(Enum):
    """Test result status"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TestCase:
    """Individual test case"""
    test_id: str
    test_type: TestType
    description: str
    result: TestResult
    execution_time: float
    details: Dict[str, Any]
    error_message: Optional[str] = None

@dataclass
class ValidationReport:
    """Complete validation report"""
    timestamp: datetime
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    test_cases: List[TestCase]
    performance_metrics: Dict[str, float]
    recommendations: List[str]

# ==============================================================================
# TEST CLASSES
# ==============================================================================
class BlackSwanDataCollectorTests(SpyderTestFramework):
    """Unit tests for BlackSwanDataCollector"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = BlackSwanDataCollector()
        
    def test_initialization(self):
        """Test collector initialization"""
        self.assertIsNotNone(self.collector)
        self.assertIsNotNone(self.collector.symbols)
        self.assertEqual(len(self.collector.symbols), 9)
        
    def test_data_collection(self):
        """Test data collection functionality"""
        start_time = time.time()
        data = self.collector.collect_all_data()
        execution_time = time.time() - start_time
        
        # Check data structure
        self.assertIsInstance(data, MarketDataSet)
        self.assertIsNotNone(data.volatility)
        self.assertIsNotNone(data.market_performance)
        self.assertIsNotNone(data.credit)
        self.assertIsNotNone(data.liquidity)
        self.assertIsNotNone(data.options)
        
        # Check performance
        self.assertLess(execution_time * 1000, PERFORMANCE_THRESHOLD_MS,
                       f"Data collection too slow: {execution_time * 1000:.0f}ms")
                       
    def test_single_indicator_fetch(self):
        """Test fetching single indicators"""
        vix = self.collector.get_single_indicator('vix')
        self.assertIsInstance(vix, (int, float, type(None)))
        
        if vix is not None:
            self.assertGreaterEqual(vix, 0)
            self.assertLessEqual(vix, 100)
            
    def test_data_source_fallback(self):
        """Test data source fallback mechanism"""
        sources = self.collector.test_data_sources()
        
        # At least one source should be available
        available_sources = [s for s, available in sources.items() if available]
        self.assertGreater(len(available_sources), 0,
                          "No data sources available")
                          
    def test_cache_functionality(self):
        """Test data caching"""
        # First call - should fetch fresh data
        data1 = self.collector.collect_all_data()
        
        # Second call immediately - should return cached
        start_time = time.time()
        data2 = self.collector.collect_all_data()
        cache_time = time.time() - start_time
        
        # Cache should be much faster
        self.assertLess(cache_time, 0.1, "Cache not working properly")
        
        # Data should be identical
        self.assertEqual(data1.timestamp, data2.timestamp)
        
    def test_error_handling(self):
        """Test error handling in data collection"""
        # Test with invalid symbol
        invalid_data = self.collector._get_symbol_data("INVALID_SYMBOL")
        self.assertIsNone(invalid_data)
        
        # Collector should continue working
        data = self.collector.collect_all_data()
        self.assertIsNotNone(data)

class BlackSwanCalculatorTests(SpyderTestFramework):
    """Unit tests for BlackSwanCalculator"""
    
    def setUp(self):
        """Setup test environment"""
        self.calculator = BlackSwanCalculator()
        self.collector = BlackSwanDataCollector()
        
    def test_initialization(self):
        """Test calculator initialization"""
        self.assertIsNotNone(self.calculator)
        self.assertIsNotNone(self.calculator.weights)
        self.assertIsNotNone(self.calculator.thresholds)
        
        # Check weights sum to 1
        total_weight = sum(self.calculator.weights.values())
        self.assertAlmostEqual(total_weight, 1.0, places=2)
        
    def test_calculation_accuracy(self):
        """Test calculation accuracy with known inputs"""
        # Create test data
        test_data = self._create_test_market_data(vix=30, sp500_change=-2.5)
        
        # Calculate
        start_time = time.time()
        result = self.calculator.calculate_indicator(test_data)
        execution_time = time.time() - start_time
        
        # Check result
        self.assertIsInstance(result, BlackSwanIndicatorResult)
        self.assertIn(result.status, [RiskStatus.YELLOW, RiskStatus.RED])
        
        # Check performance
        self.assertLess(execution_time * 1000, CALCULATION_THRESHOLD_MS,
                       f"Calculation too slow: {execution_time * 1000:.0f}ms")
                       
    def test_component_calculations(self):
        """Test individual component calculations"""
        test_data = self._create_test_market_data()
        result = self.calculator.calculate_indicator(test_data)
        
        # Check all components present
        expected_components = ['volatility', 'market_performance', 'credit_stress',
                             'liquidity_stress', 'options_activity']
        
        for component in expected_components:
            self.assertIn(component, result.component_scores)
            score = result.component_scores[component]
            self.assertGreaterEqual(score.raw_score, 0)
            self.assertLessEqual(score.raw_score, 5)
            
    def test_threshold_logic(self):
        """Test threshold classification logic"""
        test_cases = [
            (0.5, RiskStatus.GREEN),
            (1.5, RiskStatus.GREEN),
            (1.95, RiskStatus.YELLOW),
            (2.5, RiskStatus.RED),
            (4.5, RiskStatus.RED)
        ]
        
        for score, expected_status in test_cases:
            # Create data that produces specific score
            test_data = self._create_test_market_data()
            
            # Manually set score for testing
            self.calculator.score_history = [(datetime.now(), score)]
            status, _, _ = self.calculator._determine_status(score)
            
            self.assertEqual(status, expected_status,
                           f"Score {score} should be {expected_status}")
                           
    def test_momentum_adjustments(self):
        """Test momentum adjustment calculations"""
        # Add historical scores
        base_time = datetime.now()
        for i in range(10):
            score = 2.5 if i > 5 else 1.0
            self.calculator.score_history.append(
                (base_time - timedelta(minutes=10-i), score)
            )
            
        # Calculate adjustments
        adjustments = self.calculator._calculate_momentum_adjustments(2.5)
        
        # Should detect sustained stress
        self.assertGreater(adjustments.sustained_stress, 0)
        
    def test_weight_validation(self):
        """Test weight validation"""
        # Valid weights
        valid_weights = {
            'volatility': 0.3,
            'market_performance': 0.25,
            'credit_stress': 0.2,
            'liquidity_stress': 0.15,
            'options_activity': 0.1
        }
        self.assertTrue(self.calculator.set_component_weights(valid_weights))
        
        # Invalid weights (don't sum to 1)
        invalid_weights = valid_weights.copy()
        invalid_weights['volatility'] = 0.5
        self.assertFalse(self.calculator.set_component_weights(invalid_weights))
        
    def test_threshold_validation(self):
        """Test threshold validation"""
        # Valid thresholds
        valid_thresholds = {
            'green_max': 1.8,
            'yellow_max': 2.2,
            'red_max': 5.0
        }
        self.assertTrue(self.calculator.set_thresholds(valid_thresholds))
        
        # Invalid thresholds (wrong order)
        invalid_thresholds = {
            'green_max': 2.5,
            'yellow_max': 2.0,
            'red_max': 5.0
        }
        self.assertFalse(self.calculator.set_thresholds(invalid_thresholds))
        
    def _create_test_market_data(self, vix=20, sp500_change=0):
        """Helper to create test market data"""
        return MarketDataSet(
            volatility={'vix_current': vix, 'timestamp': datetime.now().isoformat()},
            market_performance={
                'sp500_current': 4500,
                'sp500_daily_change': sp500_change,
                'sp500_5day_change': sp500_change * 3,
                'timestamp': datetime.now().isoformat()
            },
            credit={
                'credit_spread_proxy': 300,
                'banking_performance': 0,
                'timestamp': datetime.now().isoformat()
            },
            liquidity={
                'usd_volatility': 5,
                'liquidity_stress': 1.0,
                'timestamp': datetime.now().isoformat()
            },
            options={
                'put_call_ratio': 1.0,
                'options_volume_surge': 1.0,
                'timestamp': datetime.now().isoformat()
            },
            timestamp=datetime.now(),
            overall_quality=DataQuality.DEFAULT
        )

class BlackSwanIntegrationTests(SpyderTestFramework):
    """Integration tests for Black Swan system"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = BlackSwanDataCollector()
        self.calculator = BlackSwanCalculator()
        self.optimizer = BlackSwanOptimizer()
        self.scheduler = BlackSwanScheduler()
        
    def test_end_to_end_flow(self):
        """Test complete data flow from collection to calculation"""
        # Collect data
        market_data = self.collector.collect_all_data()
        self.assertIsNotNone(market_data)
        
        # Calculate indicator
        result = self.calculator.calculate_indicator(market_data)
        self.assertIsNotNone(result)
        
        # Verify result integrity
        self.assertIn(result.status, [RiskStatus.GREEN, RiskStatus.YELLOW, RiskStatus.RED])
        self.assertGreaterEqual(result.overall_score, 0)
        self.assertLessEqual(result.overall_score, 5)
        
    def test_optimizer_integration(self):
        """Test optimizer integration with calculator"""
        # Run quick optimization
        result = self.optimizer.optimize_thresholds(
            method='grid_search',
            target_metric='f1_score'
        )
        
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.optimal_thresholds)
        
        # Apply optimized thresholds
        self.assertTrue(
            self.calculator.set_thresholds(result.optimal_thresholds)
        )
        
    def test_scheduler_integration(self):
        """Test scheduler integration"""
        # Add test task
        task_id = self.scheduler.add_daily_check("10:00")
        self.assertIsNotNone(task_id)
        
        # Run task manually
        success = self.scheduler.run_now(task_id)
        self.assertTrue(success)
        
        # Check results stored
        status = self.scheduler.get_status()
        self.assertGreater(status['daily_checks'], 0)
        
    def test_gui_widget_creation(self):
        """Test GUI widget creation (if display available)"""
        try:
            widget = BlackSwanWidget()
            self.assertIsNotNone(widget)
            
            # Test data update
            test_data = self.collector.collect_all_data()
            result = self.calculator.calculate_indicator(test_data)
            widget.update_display(result)
            
        except Exception as e:
            # Skip if no display
            if "no display" in str(e).lower():
                self.skipTest("No display available for GUI test")
            else:
                raise
                
    def test_cli_functionality(self):
        """Test CLI basic functionality"""
        cli = BlackSwanCLI()
        
        # Test single check
        result = cli.run_single_check()
        self.assertIsNotNone(result)
        
        # Test export
        success = cli.export_data('json', 'test_export.json')
        self.assertTrue(success)
        
        # Cleanup
        if os.path.exists('test_export.json'):
            os.remove('test_export.json')

# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================
class BlackSwanPerformanceTests(SpyderTestFramework):
    """Performance tests for Black Swan system"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = BlackSwanDataCollector()
        self.calculator = BlackSwanCalculator()
        
    def test_data_collection_performance(self):
        """Test data collection performance"""
        times = []
        
        for _ in range(10):
            start_time = time.time()
            self.collector.collect_all_data(force_refresh=True)
            times.append(time.time() - start_time)
            
        avg_time = np.mean(times)
        self.assertLess(avg_time * 1000, PERFORMANCE_THRESHOLD_MS,
                       f"Average collection time too high: {avg_time * 1000:.0f}ms")
                       
    def test_calculation_performance(self):
        """Test calculation performance"""
        # Prepare test data
        test_data = self.collector.collect_all_data()
        times = []
        
        for _ in range(100):
            start_time = time.time()
            self.calculator.calculate_indicator(test_data)
            times.append(time.time() - start_time)
            
        avg_time = np.mean(times)
        self.assertLess(avg_time * 1000, CALCULATION_THRESHOLD_MS,
                       f"Average calculation time too high: {avg_time * 1000:.0f}ms")
                       
    def test_memory_usage(self):
        """Test memory usage under load"""
        import gc
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Generate load
        results = []
        for _ in range(1000):
            data = self.collector.collect_all_data()
            result = self.calculator.calculate_indicator(data)
            results.append(result)
            
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Clean up
        results.clear()
        gc.collect()
        
        # Should not leak excessive memory
        self.assertLess(memory_increase, 100,  # 100 MB max increase
                       f"Memory usage increased by {memory_increase:.0f} MB")
                       
    def test_concurrent_access(self):
        """Test concurrent access to components"""
        import threading
        
        errors = []
        results = []
        
        def worker():
            try:
                data = self.collector.collect_all_data()
                result = self.calculator.calculate_indicator(data)
                results.append(result)
            except Exception as e:
                errors.append(e)
                
        # Launch multiple threads
        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
            
        # Wait for completion
        for t in threads:
            t.join()
            
        # Check results
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
        self.assertEqual(len(results), 10)

# ==============================================================================
# STRESS TESTS
# ==============================================================================
class BlackSwanStressTests(SpyderTestFramework):
    """Stress tests for Black Swan system"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = BlackSwanDataCollector()
        self.calculator = BlackSwanCalculator()
        
    def test_extreme_market_conditions(self):
        """Test with extreme market values"""
        extreme_scenarios = [
            {'vix': 90, 'sp500_change': -20},
            {'vix': 5, 'sp500_change': 10},
            {'vix': 150, 'sp500_change': -50},
            {'vix': 0, 'sp500_change': 0}
        ]
        
        for scenario in extreme_scenarios:
            test_data = self._create_extreme_data(
                scenario['vix'], 
                scenario['sp500_change']
            )
            
            # Should not crash
            result = self.calculator.calculate_indicator(test_data)
            self.assertIsNotNone(result)
            self.assertGreaterEqual(result.overall_score, 0)
            self.assertLessEqual(result.overall_score, 5)
            
    def test_missing_data_handling(self):
        """Test handling of missing data"""
        # Create data with missing values
        incomplete_data = MarketDataSet(
            volatility={'vix_current': None},
            market_performance={'sp500_daily_change': None},
            credit={},
            liquidity={},
            options={},
            timestamp=datetime.now(),
            overall_quality=DataQuality.DEFAULT
        )
        
        # Should handle gracefully
        result = self.calculator.calculate_indicator(incomplete_data)
        self.assertIsNotNone(result)
        
    def test_rapid_successive_calls(self):
        """Test rapid successive calls"""
        results = []
        
        # Rapid fire calls
        for _ in range(100):
            data = self.collector.collect_all_data()
            result = self.calculator.calculate_indicator(data)
            results.append(result)
            
        # All should succeed
        self.assertEqual(len(results), 100)
        
    def test_long_running_operation(self):
        """Test long running operation"""
        # Simulate 24 hours of operation
        start_time = time.time()
        results = []
        
        # Run for simulated 24 hours (accelerated)
        for hour in range(24):
            for _ in range(12):  # Every 5 minutes
                data = self.collector.collect_all_data()
                result = self.calculator.calculate_indicator(data)
                results.append(result)
                
        execution_time = time.time() - start_time
        
        # Should complete without issues
        self.assertEqual(len(results), 24 * 12)
        self.assertLess(execution_time, 60, "Long run test taking too long")
        
    def _create_extreme_data(self, vix, sp500_change):
        """Create extreme test data"""
        return MarketDataSet(
            volatility={'vix_current': vix, 'timestamp': datetime.now().isoformat()},
            market_performance={
                'sp500_current': 4500,
                'sp500_daily_change': sp500_change,
                'sp500_5day_change': sp500_change * 5,
                'timestamp': datetime.now().isoformat()
            },
            credit={
                'credit_spread_proxy': 1000 if vix > 50 else 100,
                'banking_performance': sp500_change * 1.5,
                'timestamp': datetime.now().isoformat()
            },
            liquidity={
                'usd_volatility': vix * 0.8,
                'liquidity_stress': min(5.0, vix / 20),
                'timestamp': datetime.now().isoformat()
            },
            options={
                'put_call_ratio': min(5.0, vix / 15),
                'options_volume_surge': min(5.0, vix / 20),
                'timestamp': datetime.now().isoformat()
            },
            timestamp=datetime.now(),
            overall_quality=DataQuality.DEFAULT
        )

# ==============================================================================
# VALIDATION TESTS
# ==============================================================================
class BlackSwanValidationTests(SpyderTestFramework):
    """Validation tests against known scenarios"""
    
    def setUp(self):
        """Setup test environment"""
        self.collector = BlackSwanDataCollector()
        self.calculator = BlackSwanCalculator()
        self.optimizer = BlackSwanOptimizer()
        
    def test_known_scenarios(self):
        """Test against known market scenarios"""
        results = []
        
        for scenario in TEST_SCENARIOS:
            # Create test data
            test_data = self._create_scenario_data(scenario)
            
            # Calculate
            result = self.calculator.calculate_indicator(test_data)
            
            # Check expectation
            passed = result.status == scenario['expected']
            results.append({
                'scenario': scenario['name'],
                'expected': scenario['expected'],
                'actual': result.status,
                'passed': passed
            })
            
        # Calculate accuracy
        passed_count = sum(1 for r in results if r['passed'])
        accuracy = passed_count / len(results)
        
        self.assertGreaterEqual(accuracy, MIN_ACCURACY,
                              f"Scenario accuracy too low: {accuracy:.1%}")
                              
        # Print results
        for result in results:
            if not result['passed']:
                print(f"Failed scenario: {result['scenario']} - "
                      f"Expected: {result['expected'].value}, "
                      f"Got: {result['actual'].value}")
                      
    def test_historical_event_detection(self):
        """Test detection of historical events"""
        validation_results = self.optimizer.validate_against_historical_events()
        
        detection_rate = validation_results['detection_rate']
        self.assertGreaterEqual(detection_rate, 0.6,
                              f"Historical detection rate too low: {detection_rate:.1%}")
                              
    def test_backtest_performance(self):
        """Test backtest performance metrics"""
        # Get current thresholds
        thresholds = self.calculator.get_thresholds()
        
        # Run backtest
        backtest_result = self.optimizer.backtest(thresholds)
        
        # Check performance metrics
        self.assertGreaterEqual(backtest_result.precision, MIN_PRECISION,
                              f"Precision too low: {backtest_result.precision:.3f}")
        self.assertGreaterEqual(backtest_result.recall, MIN_RECALL,
                              f"Recall too low: {backtest_result.recall:.3f}")
                              
    def test_component_importance(self):
        """Test component importance through sensitivity analysis"""
        components = ['volatility', 'market_performance', 'credit_stress',
                     'liquidity_stress', 'options_activity']
                     
        sensitivities = {}
        
        for component in components:
            result = self.optimizer.sensitivity_analysis(component, steps=10)
            sensitivities[component] = result.elasticity
            
        # Volatility should be most important
        max_sensitivity = max(sensitivities.items(), key=lambda x: x[1])
        self.assertEqual(max_sensitivity[0], 'volatility',
                        f"Expected volatility to be most sensitive, got {max_sensitivity[0]}")
                        
    def _create_scenario_data(self, scenario):
        """Create data for specific scenario"""
        vix = scenario['vix']
        sp500_change = scenario['sp500_change']
        
        # Derive other values from scenario
        credit_spread = 300 + (vix - 20) * 10
        banking_perf = sp500_change * 1.2
        usd_vol = vix * 0.5
        put_call = 1.0 + (vix - 20) * 0.02
        
        return MarketDataSet(
            volatility={'vix_current': vix, 'timestamp': datetime.now().isoformat()},
            market_performance={
                'sp500_current': 4500,
                'sp500_daily_change': sp500_change,
                'sp500_5day_change': sp500_change * 3,
                'timestamp': datetime.now().isoformat()
            },
            credit={
                'credit_spread_proxy': credit_spread,
                'banking_performance': banking_perf,
                'timestamp': datetime.now().isoformat()
            },
            liquidity={
                'usd_volatility': usd_vol,
                'liquidity_stress': 1.0 + (vix - 20) / 20,
                'timestamp': datetime.now().isoformat()
            },
            options={
                'put_call_ratio': put_call,
                'options_volume_surge': 1.0 + (vix - 20) / 30,
                'timestamp': datetime.now().isoformat()
            },
            timestamp=datetime.now(),
            overall_quality=DataQuality.DEFAULT
        )

# ==============================================================================
# MAIN VALIDATOR CLASS
# ==============================================================================
class BlackSwanValidator:
    """
    Comprehensive validator for Black Swan Indicator system.
    
    This class orchestrates all validation tests and generates comprehensive
    reports on system functionality, performance, and accuracy.
    
    Attributes:
        logger: Module logger instance
        test_results: List of all test results
        
    Example:
        >>> validator = BlackSwanValidator()
        >>> report = validator.run_full_validation()
        >>> validator.save_report(report, "validation_report.json")
    """
    
    def __init__(self):
        """Initialize the validator"""
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            
        self.test_results: List[TestCase] = []
        
    def run_full_validation(self, test_types: Optional[List[TestType]] = None) -> ValidationReport:
        """
        Run comprehensive validation suite.
        
        Args:
            test_types: Optional list of test types to run
            
        Returns:
            Validation report
        """
        if test_types is None:
            test_types = list(TestType)
            
        self.logger.info("Starting Black Swan system validation")
        start_time = time.time()
        
        # Run each test type
        if TestType.UNIT in test_types:
            self._run_unit_tests()
            
        if TestType.INTEGRATION in test_types:
            self._run_integration_tests()
            
        if TestType.PERFORMANCE in test_types:
            self._run_performance_tests()
            
        if TestType.STRESS in test_types:
            self._run_stress_tests()
            
        if TestType.VALIDATION in test_types:
            self._run_validation_tests()
            
        # Generate report
        report = self._generate_report()
        
        total_time = time.time() - start_time
        self.logger.info(f"Validation completed in {total_time:.2f} seconds")
        
        return report
        
    def _run_unit_tests(self):
        """Run unit tests"""
        self.logger.info("Running unit tests...")
        
        test_classes = [
            BlackSwanDataCollectorTests,
            BlackSwanCalculatorTests
        ]
        
        for test_class in test_classes:
            self._run_test_suite(test_class, TestType.UNIT)
            
    def _run_integration_tests(self):
        """Run integration tests"""
        self.logger.info("Running integration tests...")
        self._run_test_suite(BlackSwanIntegrationTests, TestType.INTEGRATION)
        
    def _run_performance_tests(self):
        """Run performance tests"""
        self.logger.info("Running performance tests...")
        self._run_test_suite(BlackSwanPerformanceTests, TestType.PERFORMANCE)
        
    def _run_stress_tests(self):
        """Run stress tests"""
        self.logger.info("Running stress tests...")
        self._run_test_suite(BlackSwanStressTests, TestType.STRESS)
        
    def _run_validation_tests(self):
        """Run validation tests"""
        self.logger.info("Running validation tests...")
        self._run_test_suite(BlackSwanValidationTests, TestType.VALIDATION)
        
    def _run_test_suite(self, test_class, test_type: TestType):
        """Run a test suite and record results"""
        suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        
        for test in suite:
            test_id = f"{test_class.__name__}.{test._testMethodName}"
            description = test._testMethodDoc or test._testMethodName
            
            start_time = time.time()
            
            try:
                # Run test
                result = runner.run(test)
                
                if result.wasSuccessful():
                    test_result = TestResult.PASS
                    error_message = None
                elif result.skipped:
                    test_result = TestResult.SKIP
                    error_message = "Test skipped"
                else:
                    test_result = TestResult.FAIL
                    error_message = str(result.failures[0][1]) if result.failures else None
                    
            except Exception as e:
                test_result = TestResult.ERROR
                error_message = str(e)
                
            execution_time = time.time() - start_time
            
            # Record result
            test_case = TestCase(
                test_id=test_id,
                test_type=test_type,
                description=description,
                result=test_result,
                execution_time=execution_time,
                details={},
                error_message=error_message
            )
            
            self.test_results.append(test_case)
            
    def _generate_report(self) -> ValidationReport:
        """Generate validation report"""
        # Count results
        total_tests = len(self.test_results)
        passed = sum(1 for t in self.test_results if t.result == TestResult.PASS)
        failed = sum(1 for t in self.test_results if t.result == TestResult.FAIL)
        skipped = sum(1 for t in self.test_results if t.result == TestResult.SKIP)
        errors = sum(1 for t in self.test_results if t.result == TestResult.ERROR)
        
        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics()
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        
        return ValidationReport(
            timestamp=datetime.now(),
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            test_cases=self.test_results,
            performance_metrics=performance_metrics,
            recommendations=recommendations
        )
        
    def _calculate_performance_metrics(self) -> Dict[str, float]:
        """Calculate performance metrics from test results"""
        metrics = {}
        
        # Average execution times by test type
        for test_type in TestType:
            type_tests = [t for t in self.test_results if t.test_type == test_type]
            if type_tests:
                avg_time = np.mean([t.execution_time for t in type_tests])
                metrics[f'{test_type.value}_avg_time'] = avg_time
                
        # Overall statistics
        all_times = [t.execution_time for t in self.test_results]
        if all_times:
            metrics['total_execution_time'] = sum(all_times)
            metrics['avg_test_time'] = np.mean(all_times)
            metrics['max_test_time'] = max(all_times)
            
        # Success rate
        if self.test_results:
            success_rate = sum(1 for t in self.test_results 
                             if t.result == TestResult.PASS) / len(self.test_results)
            metrics['success_rate'] = success_rate
            
        return metrics
        
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check for failed tests
        failed_tests = [t for t in self.test_results if t.result == TestResult.FAIL]
        if failed_tests:
            recommendations.append(
                f"⚠️ {len(failed_tests)} tests failed. Review and fix issues."
            )
            
            # Group by test type
            failed_by_type = {}
            for test in failed_tests:
                test_type = test.test_type.value
                if test_type not in failed_by_type:
                    failed_by_type[test_type] = 0
                failed_by_type[test_type] += 1
                
            for test_type, count in failed_by_type.items():
                recommendations.append(
                    f"  - {count} {test_type} tests failed"
                )
                
        # Check performance
        perf_tests = [t for t in self.test_results 
                     if t.test_type == TestType.PERFORMANCE]
        if perf_tests:
            slow_tests = [t for t in perf_tests if t.execution_time > 5.0]
            if slow_tests:
                recommendations.append(
                    f"⚠️ {len(slow_tests)} performance tests exceeded 5 seconds"
                )
                
        # Check stress test results
        stress_tests = [t for t in self.test_results 
                       if t.test_type == TestType.STRESS]
        if stress_tests:
            stress_failures = [t for t in stress_tests 
                             if t.result != TestResult.PASS]
            if stress_failures:
                recommendations.append(
                    f"⚠️ System may not handle extreme conditions well"
                )
                
        # Overall assessment
        success_rate = self._calculate_performance_metrics().get('success_rate', 0)
        if success_rate >= 0.95:
            recommendations.append("✅ System validation passed with excellent results")
        elif success_rate >= 0.80:
            recommendations.append("✅ System validation passed with good results")
        else:
            recommendations.append("❌ System validation failed - significant issues found")
            
        return recommendations
        
    def save_report(self, report: ValidationReport, filename: str):
        """
        Save validation report to file.
        
        Args:
            report: Validation report
            filename: Output filename
        """
        # Convert to dictionary
        report_dict = {
            'timestamp': report.timestamp.isoformat(),
            'summary': {
                'total_tests': report.total_tests,
                'passed': report.passed,
                'failed': report.failed,
                'skipped': report.skipped,
                'errors': report.errors
            },
            'performance_metrics': report.performance_metrics,
            'recommendations': report.recommendations,
            'test_results': [
                {
                    'test_id': t.test_id,
                    'test_type': t.test_type.value,
                    'description': t.description,
                    'result': t.result.value,
                    'execution_time': t.execution_time,
                    'error_message': t.error_message
                }
                for t in report.test_cases
            ]
        }
        
        # Save based on extension
        if filename.endswith('.json'):
            with open(filename, 'w') as f:
                json.dump(report_dict, f, indent=2)
        elif filename.endswith('.txt'):
            self._save_text_report(report, filename)
        else:
            # Default to JSON
            with open(filename + '.json', 'w') as f:
                json.dump(report_dict, f, indent=2)
                
        self.logger.info(f"Validation report saved to {filename}")
        
    def _save_text_report(self, report: ValidationReport, filename: str):
        """Save report in text format"""
        with open(filename, 'w') as f:
            f.write("BLACK SWAN SYSTEM VALIDATION REPORT\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("SUMMARY\n")
            f.write("-"*30 + "\n")
            f.write(f"Total Tests: {report.total_tests}\n")
            f.write(f"Passed: {report.passed}\n")
            f.write(f"Failed: {report.failed}\n")
            f.write(f"Skipped: {report.skipped}\n")
            f.write(f"Errors: {report.errors}\n")
            f.write(f"Success Rate: {report.passed/report.total_tests:.1%}\n\n")
            
            f.write("PERFORMANCE METRICS\n")
            f.write("-"*30 + "\n")
            for metric, value in report.performance_metrics.items():
                f.write(f"{metric}: {value:.3f}\n")
                
            f.write("\nRECOMMENDATIONS\n")
            f.write("-"*30 + "\n")
            for rec in report.recommendations:
                f.write(f"{rec}\n")
                
            f.write("\nDETAILED TEST RESULTS\n")
            f.write("-"*30 + "\n")
            
            # Group by test type
            for test_type in TestType:
                type_tests = [t for t in report.test_cases if t.test_type == test_type]
                if type_tests:
                    f.write(f"\n{test_type.value.upper()} TESTS\n")
                    for test in type_tests:
                        status = "✓" if test.result == TestResult.PASS else "✗"
                        f.write(f"{status} {test.test_id} ({test.execution_time:.3f}s)\n")
                        if test.error_message:
                            f.write(f"  Error: {test.error_message}\n")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def run_quick_validation() -> bool:
    """
    Run quick validation check.
    
    Returns:
        True if all critical tests pass
    """
    validator = BlackSwanValidator()
    
    # Run only unit and integration tests
    report = validator.run_full_validation([TestType.UNIT, TestType.INTEGRATION])
    
    return report.failed == 0 and report.errors == 0

def generate_validation_report(output_file: str = "black_swan_validation.json"):
    """
    Generate comprehensive validation report.
    
    Args:
        output_file: Output filename for report
    """
    validator = BlackSwanValidator()
    report = validator.run_full_validation()
    validator.save_report(report, output_file)
    
    return report

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    print("="*60)
    print("BLACK SWAN VALIDATOR - COMPREHENSIVE TESTING")
    print("="*60)
    
    # Run full validation
    validator = BlackSwanValidator()
    report = validator.run_full_validation()
    
    # Print summary
    print(f"\nValidation Summary:")
    print(f"  Total Tests: {report.total_tests}")
    print(f"  Passed: {report.passed}")
    print(f"  Failed: {report.failed}")
    print(f"  Skipped: {report.skipped}")
    print(f"  Errors: {report.errors}")
    print(f"  Success Rate: {report.passed/report.total_tests:.1%}")
    
    print(f"\nPerformance Metrics:")
    for metric, value in report.performance_metrics.items():
        print(f"  {metric}: {value:.3f}")
        
    print(f"\nRecommendations:")
    for rec in report.recommendations:
        print(f"  {rec}")
        
    # Save report
    validator.save_report(report, "black_swan_validation_report.json")
    validator.save_report(report, "black_swan_validation_report.txt")
    
    print(f"\nReports saved to:")
    print(f"  - black_swan_validation_report.json")
    print(f"  - black_swan_validation_report.txt")
    
    # Exit with appropriate code
    if report.failed > 0 or report.errors > 0:
        print("\n❌ Validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ Validation PASSED")
        sys.exit(0)
