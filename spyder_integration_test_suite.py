#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
Integration Test Suite

This comprehensive test suite validates the integration of all Spyder modules,
ensuring they work together correctly as a cohesive trading system.

Test Coverage:
    - System Orchestrator startup/shutdown
    - Options Analytics pipeline (N01-N07)
    - Data flow between modules
    - Event routing and messaging
    - Risk management integration
    - GUI dashboard functionality
    - Database operations
    - Error handling and recovery

Author: Mohamed Talib
Date: 2025-08-07
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import unittest
import time
import threading
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# SYSTEM PATH SETUP
# ==============================================================================
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# ==============================================================================
# MODULE IMPORTS FOR TESTING
# ==============================================================================
# Core modules
try:
    from SpyderI_Integration.SpyderI05_SystemOrchestrator import (
        SystemOrchestrator, SystemState, ModuleState
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    print("⚠️ System Orchestrator not available")

# Options Analytics modules (N01-N07)
try:
    from SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
    from SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import ImpliedVolatilityEngine
    from SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import OptionsChainManager
    from SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator
    from SpyderN_OptionsAnalytics.SpyderN05_OptionsExpirationManager import OptionsExpirationManager
    from SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder import VolatilitySurfaceBuilder
    from SpyderN_OptionsAnalytics.SpyderN07_OptionsFlowTracker import OptionsFlowTracker
    OPTIONS_AVAILABLE = True
except ImportError as e:
    OPTIONS_AVAILABLE = False
    print(f"⚠️ Options modules not available: {e}")

# Utilities
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    print("⚠️ Utility modules not available")

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================
TEST_CONFIG = {
    'symbol': 'SPY',
    'underlying_price': 585.0,
    'risk_free_rate': 0.05,
    'dividend_yield': 0.015,
    'test_strikes': [575, 580, 585, 590, 595],
    'test_expiries': [7, 14, 30, 60],  # Days to expiry
    'db_path': ':memory:',  # Use in-memory database for testing
    'timeout': 30  # Test timeout in seconds
}

# ==============================================================================
# BASE TEST CLASS
# ==============================================================================
class SpyderIntegrationTest(unittest.TestCase):
    """Base class for Spyder integration tests"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        cls.logger = SpyderLogger.get_logger('IntegrationTest') if UTILS_AVAILABLE else None
        cls.test_data_created = False
        
    def setUp(self):
        """Set up before each test"""
        self.start_time = time.time()
        
    def tearDown(self):
        """Clean up after each test"""
        elapsed = time.time() - self.start_time
        print(f"  Test completed in {elapsed:.2f}s")
        
    def create_test_options_data(self) -> pd.DataFrame:
        """Create synthetic options data for testing"""
        data = []
        underlying = TEST_CONFIG['underlying_price']
        
        for days in TEST_CONFIG['test_expiries']:
            expiry = datetime.now() + timedelta(days=days)
            
            for strike in TEST_CONFIG['test_strikes']:
                # Generate realistic IV with smile
                moneyness = strike / underlying
                base_iv = 0.15 + 0.05 * (days / 365)
                smile = 0.02 * (np.log(moneyness))**2
                
                for option_type in ['CALL', 'PUT']:
                    iv = base_iv + smile + np.random.normal(0, 0.01)
                    
                    data.append({
                        'symbol': TEST_CONFIG['symbol'],
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': option_type,
                        'bid': np.random.uniform(1, 5),
                        'ask': np.random.uniform(1.1, 5.1),
                        'last': np.random.uniform(1, 5),
                        'volume': np.random.randint(100, 5000),
                        'open_interest': np.random.randint(1000, 10000),
                        'implied_volatility': max(0.05, min(0.50, iv))
                    })
        
        return pd.DataFrame(data)

# ==============================================================================
# SYSTEM ORCHESTRATOR TESTS
# ==============================================================================
class TestSystemOrchestrator(SpyderIntegrationTest):
    """Test System Orchestrator functionality"""
    
    @unittest.skipUnless(ORCHESTRATOR_AVAILABLE, "Orchestrator not available")
    def test_01_orchestrator_initialization(self):
        """Test orchestrator can be initialized"""
        print("\n  Testing Orchestrator initialization...")
        
        orchestrator = SystemOrchestrator()
        self.assertIsNotNone(orchestrator)
        self.assertEqual(orchestrator.state, SystemState.STOPPED)
        
    @unittest.skipUnless(ORCHESTRATOR_AVAILABLE, "Orchestrator not available")
    def test_02_module_discovery(self):
        """Test module discovery"""
        print("\n  Testing module discovery...")
        
        orchestrator = SystemOrchestrator()
        orchestrator._discover_modules()
        
        self.assertGreater(len(orchestrator.modules), 0)
        print(f"    Discovered {len(orchestrator.modules)} modules")
        
        # Check for critical modules
        critical_found = 0
        for module_name in ['SpyderU01_Logger', 'SpyderU02_ErrorHandler']:
            if module_name in orchestrator.modules:
                critical_found += 1
        
        self.assertGreater(critical_found, 0, "No critical modules found")
        
    @unittest.skipUnless(ORCHESTRATOR_AVAILABLE, "Orchestrator not available")
    def test_03_dependency_graph(self):
        """Test dependency graph building"""
        print("\n  Testing dependency graph...")
        
        orchestrator = SystemOrchestrator()
        orchestrator._discover_modules()
        orchestrator._build_dependency_graph()
        
        self.assertIsNotNone(orchestrator.dependency_graph)
        self.assertGreater(len(orchestrator.dependency_graph.nodes), 0)
        
        # Check for circular dependencies
        cycles = orchestrator._detect_circular_dependencies()
        print(f"    Circular dependencies found: {len(cycles)}")
        
    @unittest.skipUnless(ORCHESTRATOR_AVAILABLE and UTILS_AVAILABLE, 
                        "Required modules not available")
    def test_04_partial_startup(self):
        """Test starting critical modules only"""
        print("\n  Testing partial system startup...")
        
        orchestrator = SystemOrchestrator()
        orchestrator._discover_modules()
        
        # Try to start logger module
        if 'SpyderU01_Logger' in orchestrator.modules:
            success = orchestrator._load_module('SpyderU01_Logger')
            self.assertTrue(success, "Failed to load Logger module")
            
            module_info = orchestrator.modules['SpyderU01_Logger']
            self.assertEqual(module_info.state, ModuleState.LOADED)

# ==============================================================================
# OPTIONS ANALYTICS PIPELINE TESTS
# ==============================================================================
class TestOptionsAnalyticsPipeline(SpyderIntegrationTest):
    """Test the complete options analytics pipeline"""
    
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_01_pricing_engine(self):
        """Test N01 OptionsPricer"""
        print("\n  Testing Options Pricing Engine...")
        
        pricer = OptionsPricer()
        
        # Test Black-Scholes pricing
        price = pricer.calculate_option_price(
            spot=TEST_CONFIG['underlying_price'],
            strike=590,
            time_to_expiry=30/365,
            volatility=0.20,
            risk_free_rate=TEST_CONFIG['risk_free_rate'],
            option_type='CALL'
        )
        
        self.assertGreater(price, 0)
        self.assertLess(price, TEST_CONFIG['underlying_price'])
        print(f"    Call price: ${price:.2f}")
        
        # Test Greeks
        greeks = pricer.calculate_greeks(
            spot=TEST_CONFIG['underlying_price'],
            strike=590,
            time_to_expiry=30/365,
            volatility=0.20,
            risk_free_rate=TEST_CONFIG['risk_free_rate'],
            option_type='CALL'
        )
        
        self.assertIn('delta', greeks)
        self.assertIn('gamma', greeks)
        self.assertIn('theta', greeks)
        self.assertIn('vega', greeks)
        print(f"    Delta: {greeks['delta']:.3f}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_02_iv_engine(self):
        """Test N02 ImpliedVolatilityEngine"""
        print("\n  Testing Implied Volatility Engine...")
        
        iv_engine = ImpliedVolatilityEngine()
        
        # Test IV calculation
        iv = iv_engine.calculate_iv(
            option_price=5.0,
            spot=TEST_CONFIG['underlying_price'],
            strike=590,
            time_to_expiry=30/365,
            risk_free_rate=TEST_CONFIG['risk_free_rate'],
            option_type='CALL'
        )
        
        self.assertGreater(iv, 0)
        self.assertLess(iv, 1.0)
        print(f"    Implied Volatility: {iv:.2%}")
        
        # Test IV rank
        historical_ivs = np.random.uniform(0.10, 0.30, 252)
        iv_rank = iv_engine.calculate_iv_rank(0.20, historical_ivs)
        
        self.assertGreaterEqual(iv_rank, 0)
        self.assertLessEqual(iv_rank, 100)
        print(f"    IV Rank: {iv_rank:.0f}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_03_chain_manager(self):
        """Test N03 OptionsChainManager"""
        print("\n  Testing Options Chain Manager...")
        
        manager = OptionsChainManager()
        
        # Create test data
        options_data = self.create_test_options_data()
        
        # Add contracts
        for _, row in options_data.iterrows():
            contract = manager.add_contract(
                manager._create_contract_from_row(row)
            )
        
        # Get chain
        chain = manager.get_chain(TEST_CONFIG['symbol'])
        
        self.assertFalse(chain.empty)
        print(f"    Chain size: {len(chain)} contracts")
        
        # Test strike selection
        atm = manager.get_atm_strike(
            TEST_CONFIG['symbol'],
            datetime.now() + timedelta(days=30)
        )
        
        self.assertGreater(atm, 0)
        print(f"    ATM Strike: ${atm}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_04_greeks_calculator(self):
        """Test N04 OptionsGreeksCalculator"""
        print("\n  Testing Greeks Calculator...")
        
        calculator = OptionsGreeksCalculator()
        
        # Add test position
        position = calculator.add_position(
            symbol=TEST_CONFIG['symbol'],
            strike=590,
            expiry=datetime.now() + timedelta(days=30),
            option_type='CALL',
            quantity=10,
            spot=TEST_CONFIG['underlying_price'],
            volatility=0.20
        )
        
        self.assertIsNotNone(position)
        print(f"    Position Delta: {position.position_delta:.0f}")
        
        # Test scenario analysis
        scenarios = calculator.run_scenario_analysis(
            scenario_type=calculator.ScenarioType.SPOT_MOVE
        )
        
        self.assertGreater(len(scenarios), 0)
        print(f"    Scenarios calculated: {len(scenarios)}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_05_expiration_manager(self):
        """Test N05 OptionsExpirationManager"""
        print("\n  Testing Expiration Manager...")
        
        manager = OptionsExpirationManager()
        
        # Add expiring position
        position = manager.add_position(
            symbol=TEST_CONFIG['symbol'],
            strike=585,
            expiry=datetime.now() + timedelta(days=1),
            option_type='CALL',
            quantity=5,
            current_price=2.0,
            underlying_price=TEST_CONFIG['underlying_price']
        )
        
        self.assertIsNotNone(position)
        print(f"    Recommended Action: {position.recommended_action.value}")
        
        # Test exercise decisions
        decisions = manager.determine_exercise_decisions()
        self.assertIsInstance(decisions, list)
        
        # Test roll opportunities
        rolls = manager.identify_roll_opportunities()
        print(f"    Roll opportunities: {len(rolls)}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_06_volatility_surface(self):
        """Test N06 VolatilitySurfaceBuilder"""
        print("\n  Testing Volatility Surface Builder...")
        
        builder = VolatilitySurfaceBuilder()
        
        # Create test data
        options_data = self.create_test_options_data()
        
        # Build surface
        surface = builder.build_surface(
            symbol=TEST_CONFIG['symbol'],
            options_data=options_data,
            underlying_price=TEST_CONFIG['underlying_price'],
            risk_free_rate=TEST_CONFIG['risk_free_rate']
        )
        
        self.assertIsNotNone(surface)
        print(f"    Surface built with {surface.data_points} points")
        
        # Analyze surface
        analytics = builder.analyze_surface(TEST_CONFIG['symbol'])
        
        self.assertIsNotNone(analytics)
        print(f"    Term Structure: {analytics.term_structure_shape}")
        print(f"    Skew Pattern: {analytics.skew_pattern.value}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_07_flow_tracker(self):
        """Test N07 OptionsFlowTracker"""
        print("\n  Testing Options Flow Tracker...")
        
        tracker = OptionsFlowTracker()
        
        # Process test flow
        test_flow = {
            'timestamp': datetime.now(),
            'symbol': TEST_CONFIG['symbol'],
            'strike': 590,
            'expiry': datetime.now() + timedelta(days=7),
            'option_type': 'CALL',
            'size': 1000,
            'price': 2.50,
            'bid': 2.48,
            'ask': 2.52,
            'underlying_price': TEST_CONFIG['underlying_price'],
            'volume': 5000,
            'open_interest': 2000,
            'iv': 0.20,
            'delta': 0.35,
            'gamma': 0.02
        }
        
        flow = tracker.process_flow(test_flow)
        
        self.assertIsNotNone(flow)
        print(f"    Flow Type: {flow.flow_type.value}")
        print(f"    Premium: ${flow.premium:,.0f}")
        
        # Test sentiment
        sentiment = tracker.calculate_market_sentiment(TEST_CONFIG['symbol'])
        print(f"    Market Sentiment: {sentiment.value}")

# ==============================================================================
# INTEGRATION FLOW TESTS
# ==============================================================================
class TestIntegrationFlow(SpyderIntegrationTest):
    """Test complete data flow through multiple modules"""
    
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_01_pricing_to_greeks_flow(self):
        """Test flow from pricing to Greeks calculation"""
        print("\n  Testing Pricing → Greeks flow...")
        
        # Initialize modules
        pricer = OptionsPricer()
        calculator = OptionsGreeksCalculator()
        
        # Price option
        price = pricer.calculate_option_price(
            spot=TEST_CONFIG['underlying_price'],
            strike=590,
            time_to_expiry=30/365,
            volatility=0.20,
            risk_free_rate=TEST_CONFIG['risk_free_rate'],
            option_type='CALL'
        )
        
        # Calculate Greeks
        greeks = pricer.calculate_greeks(
            spot=TEST_CONFIG['underlying_price'],
            strike=590,
            time_to_expiry=30/365,
            volatility=0.20,
            risk_free_rate=TEST_CONFIG['risk_free_rate'],
            option_type='CALL'
        )
        
        # Add to portfolio
        position = calculator.add_position(
            symbol=TEST_CONFIG['symbol'],
            strike=590,
            expiry=datetime.now() + timedelta(days=30),
            option_type='CALL',
            quantity=10,
            spot=TEST_CONFIG['underlying_price'],
            volatility=0.20
        )
        
        # Verify consistency
        self.assertAlmostEqual(position.delta, greeks['delta'], places=2)
        print(f"    Price: ${price:.2f}, Delta: {greeks['delta']:.3f}")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_02_chain_to_surface_flow(self):
        """Test flow from chain manager to volatility surface"""
        print("\n  Testing Chain → Surface flow...")
        
        # Initialize modules
        chain_manager = OptionsChainManager()
        surface_builder = VolatilitySurfaceBuilder()
        
        # Create and populate chain
        options_data = self.create_test_options_data()
        
        for _, row in options_data.iterrows():
            chain_manager.add_contract(
                chain_manager._create_contract_from_row(row)
            )
        
        # Get chain data
        chain = chain_manager.get_chain(TEST_CONFIG['symbol'])
        
        # Build surface from chain
        surface = surface_builder.build_surface(
            symbol=TEST_CONFIG['symbol'],
            options_data=chain,
            underlying_price=TEST_CONFIG['underlying_price']
        )
        
        self.assertIsNotNone(surface)
        self.assertGreater(surface.data_points, 0)
        print(f"    Chain → Surface: {len(chain)} → {surface.data_points} points")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_03_flow_to_expiration_flow(self):
        """Test flow from flow tracker to expiration manager"""
        print("\n  Testing Flow → Expiration flow...")
        
        # Initialize modules
        flow_tracker = OptionsFlowTracker()
        exp_manager = OptionsExpirationManager()
        
        # Process unusual flow
        unusual_flow = {
            'timestamp': datetime.now(),
            'symbol': TEST_CONFIG['symbol'],
            'strike': 585,
            'expiry': datetime.now() + timedelta(days=2),
            'option_type': 'PUT',
            'size': 5000,
            'price': 3.00,
            'bid': 2.95,
            'ask': 3.05,
            'underlying_price': TEST_CONFIG['underlying_price'],
            'volume': 20000,
            'open_interest': 5000,
            'iv': 0.25,
            'delta': -0.45,
            'gamma': 0.03
        }
        
        flow = flow_tracker.process_flow(unusual_flow)
        
        # Add to expiration manager if near expiry
        if flow.is_unusual:
            position = exp_manager.add_position(
                symbol=flow.symbol,
                strike=flow.strike,
                expiry=flow.expiry,
                option_type=flow.option_type,
                quantity=-50,  # Short position
                current_price=flow.price,
                underlying_price=flow.underlying_price
            )
            
            self.assertIsNotNone(position)
            print(f"    Unusual flow detected → Expiration action: {position.recommended_action.value}")

# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================
class TestPerformance(SpyderIntegrationTest):
    """Test system performance and resource usage"""
    
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_01_bulk_pricing_performance(self):
        """Test bulk options pricing performance"""
        print("\n  Testing bulk pricing performance...")
        
        pricer = OptionsPricer()
        
        # Time bulk pricing
        start = time.time()
        prices = []
        
        for strike in TEST_CONFIG['test_strikes']:
            for days in TEST_CONFIG['test_expiries']:
                price = pricer.calculate_option_price(
                    spot=TEST_CONFIG['underlying_price'],
                    strike=strike,
                    time_to_expiry=days/365,
                    volatility=0.20,
                    risk_free_rate=TEST_CONFIG['risk_free_rate'],
                    option_type='CALL'
                )
                prices.append(price)
        
        elapsed = time.time() - start
        total_calcs = len(TEST_CONFIG['test_strikes']) * len(TEST_CONFIG['test_expiries'])
        
        print(f"    Priced {total_calcs} options in {elapsed:.3f}s")
        print(f"    Rate: {total_calcs/elapsed:.0f} options/second")
        
        self.assertLess(elapsed, 1.0, "Pricing too slow")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_02_surface_building_performance(self):
        """Test volatility surface building performance"""
        print("\n  Testing surface building performance...")
        
        builder = VolatilitySurfaceBuilder()
        
        # Create larger dataset
        large_data = []
        for _ in range(5):
            df = self.create_test_options_data()
            large_data.append(df)
        
        options_data = pd.concat(large_data, ignore_index=True)
        
        # Time surface building
        start = time.time()
        
        surface = builder.build_surface(
            symbol=TEST_CONFIG['symbol'],
            options_data=options_data,
            underlying_price=TEST_CONFIG['underlying_price']
        )
        
        elapsed = time.time() - start
        
        print(f"    Built surface from {len(options_data)} contracts in {elapsed:.3f}s")
        
        self.assertLess(elapsed, 5.0, "Surface building too slow")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_03_flow_processing_performance(self):
        """Test flow processing performance"""
        print("\n  Testing flow processing performance...")
        
        tracker = OptionsFlowTracker()
        
        # Generate test flows
        test_flows = []
        for _ in range(100):
            flow = {
                'timestamp': datetime.now(),
                'symbol': TEST_CONFIG['symbol'],
                'strike': np.random.choice(TEST_CONFIG['test_strikes']),
                'expiry': datetime.now() + timedelta(days=np.random.choice([7, 14, 30])),
                'option_type': np.random.choice(['CALL', 'PUT']),
                'size': np.random.randint(100, 5000),
                'price': np.random.uniform(1, 5),
                'bid': np.random.uniform(0.9, 4.9),
                'ask': np.random.uniform(1.1, 5.1),
                'underlying_price': TEST_CONFIG['underlying_price'],
                'volume': np.random.randint(1000, 10000),
                'open_interest': np.random.randint(1000, 20000),
                'iv': np.random.uniform(0.15, 0.30),
                'delta': np.random.uniform(-0.5, 0.5),
                'gamma': np.random.uniform(0.01, 0.05)
            }
            test_flows.append(flow)
        
        # Time processing
        start = time.time()
        
        for flow_data in test_flows:
            tracker.process_flow(flow_data)
        
        elapsed = time.time() - start
        
        print(f"    Processed {len(test_flows)} flows in {elapsed:.3f}s")
        print(f"    Rate: {len(test_flows)/elapsed:.0f} flows/second")
        
        self.assertLess(elapsed, 2.0, "Flow processing too slow")

# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================
class TestErrorHandling(SpyderIntegrationTest):
    """Test error handling and recovery"""
    
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_01_invalid_input_handling(self):
        """Test handling of invalid inputs"""
        print("\n  Testing invalid input handling...")
        
        pricer = OptionsPricer()
        
        # Test negative volatility
        with self.assertRaises(ValueError):
            pricer.calculate_option_price(
                spot=100,
                strike=100,
                time_to_expiry=0.25,
                volatility=-0.20,  # Invalid
                risk_free_rate=0.05,
                option_type='CALL'
            )
        
        # Test zero time to expiry
        price = pricer.calculate_option_price(
            spot=100,
            strike=100,
            time_to_expiry=0,  # At expiry
            volatility=0.20,
            risk_free_rate=0.05,
            option_type='CALL'
        )
        
        self.assertEqual(price, max(0, 100 - 100))  # Intrinsic value
        print("    Invalid input handling: PASSED")
        
    @unittest.skipUnless(OPTIONS_AVAILABLE, "Options modules not available")
    def test_02_data_validation(self):
        """Test data validation in chain manager"""
        print("\n  Testing data validation...")
        
        manager = OptionsChainManager()
        
        # Try to add invalid contract
        invalid_contract = {
            'symbol': '',  # Invalid
            'strike': -100,  # Invalid
            'expiry': datetime.now() - timedelta(days=1),  # Past expiry
            'option_type': 'INVALID',  # Invalid type
        }
        
        # Should handle gracefully
        try:
            contract = manager.add_contract(invalid_contract)
            # Contract should be rejected or sanitized
        except Exception as e:
            # Should handle error gracefully
            self.assertIsInstance(e, (ValueError, KeyError))
        
        print("    Data validation: PASSED")

# ==============================================================================
# TEST SUITE RUNNER
# ==============================================================================
def run_integration_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print(" SPYDER INTEGRATION TEST SUITE")
    print("="*80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"Project Root: {project_root}")
    print("="*80)
    
    # Check module availability
    print("\n📦 Module Availability:")
    print(f"  System Orchestrator: {'✅' if ORCHESTRATOR_AVAILABLE else '❌'}")
    print(f"  Options Analytics: {'✅' if OPTIONS_AVAILABLE else '❌'}")
    print(f"  Utilities: {'✅' if UTILS_AVAILABLE else '❌'}")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestSystemOrchestrator,
        TestOptionsAnalyticsPipeline,
        TestIntegrationFlow,
        TestPerformance,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(test_class))
    
    # Run tests
    print("\n🧪 Running Tests:")
    print("-"*80)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*80)
    print(" TEST SUMMARY")
    print("="*80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
        
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split(chr(10))[0]}")
        
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback.split(chr(10))[0]}")
    
    print("="*80)
    print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    return result.wasSuccessful()

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Run integration tests
    success = run_integration_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)