#!/usr/bin/env python3
"""
Test Suite for HMM Signal Provider
Comprehensive tests for the streamlined signal provider system.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import unittest
import time
import threading
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import warnings
warnings.filterwarnings('ignore')

# Import components to test
from hmm_signal_provider import (
    HMMSignalProvider, TradingSignal, RegimeUpdate, MarketData,
    MarketRegime, create_signal_provider
)
from signal_provider_api import SignalProviderAPI, create_api, quick_start_api
from pyqt6_integration_example import SignalProviderIntegration, SimpleIntegrationExample

class TestHMMSignalProvider(unittest.TestCase):
    """Test the core HMM Signal Provider"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.provider = HMMSignalProvider(symbols=["SPY"])
        
    def tearDown(self):
        """Clean up after tests"""
        if self.provider.running:
            self.provider.stop()
    
    def test_initialization(self):
        """Test provider initialization"""
        self.assertIsNotNone(self.provider)
        self.assertEqual(self.provider.symbols, ["SPY"])
        self.assertIsNotNone(self.provider.config)
        self.assertFalse(self.provider.running)
    
    def test_configuration(self):
        """Test configuration handling"""
        config = self.provider.config
        
        # Check required configuration sections
        self.assertIn("hmm", config)
        self.assertIn("data", config)
        self.assertIn("strategy", config)
        self.assertIn("risk", config)
        
        # Check HMM configuration
        hmm_config = config["hmm"]
        self.assertEqual(hmm_config["n_components"], 3)
        self.assertIn("covariance_type", hmm_config)
        
        # Check strategy configuration
        strategy_config = config["strategy"]
        self.assertIn("regime_strategies", strategy_config)
        self.assertEqual(len(strategy_config["regime_strategies"]), 3)
    
    def test_start_stop(self):
        """Test start and stop functionality"""
        # Test start
        self.provider.start()
        self.assertTrue(self.provider.running)
        self.assertIsNotNone(self.provider.update_thread)
        
        # Give it a moment to start
        time.sleep(1)
        
        # Test stop
        self.provider.stop()
        self.assertFalse(self.provider.running)
    
    def test_technical_indicators(self):
        """Test technical indicator calculation"""
        # Create sample data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        sample_data = pd.DataFrame({
            'Open': np.random.randn(len(dates)).cumsum() + 100,
            'High': np.random.randn(len(dates)).cumsum() + 102,
            'Low': np.random.randn(len(dates)).cumsum() + 98,
            'Close': np.random.randn(len(dates)).cumsum() + 100,
            'Volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
        
        # Add technical indicators
        result = self.provider._add_technical_indicators(sample_data)
        
        # Check that indicators were added
        expected_indicators = ['returns', 'volatility', 'rsi', 'macd']
        for indicator in expected_indicators:
            if indicator in result.columns:
                self.assertIn(indicator, result.columns)
                # Check that values are not all NaN
                self.assertFalse(result[indicator].isna().all())
    
    def test_hmm_feature_preparation(self):
        """Test HMM feature preparation"""
        # Create sample data with technical indicators
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        sample_data = pd.DataFrame({
            'returns': np.random.randn(len(dates)) * 0.02,
            'volatility': np.random.rand(len(dates)) * 0.3 + 0.1,
            'rsi': np.random.rand(len(dates)) * 100,
            'macd': np.random.randn(len(dates)) * 0.01,
            'macd_histogram': np.random.randn(len(dates)) * 0.005,
            'bb_width': np.random.rand(len(dates)) * 0.1,
            'volume_ratio': np.random.rand(len(dates)) * 2 + 0.5,
            'momentum_5': np.random.randn(len(dates)) * 0.05,
            'momentum_10': np.random.randn(len(dates)) * 0.08
        }, index=dates)
        
        # Test feature preparation
        features = self.provider._prepare_hmm_features(sample_data)
        
        if features is not None:
            self.assertIsInstance(features, np.ndarray)
            self.assertEqual(len(features.shape), 2)
            self.assertGreater(features.shape[0], 0)
            self.assertGreater(features.shape[1], 0)
    
    def test_regime_mapping(self):
        """Test regime mapping functionality"""
        # Create sample features
        features = np.random.randn(100, 9)  # 100 samples, 9 features
        
        # Test regime mapping
        for state in [0, 1, 2]:
            regime = self.provider._map_state_to_regime(state, features)
            self.assertIsInstance(regime, MarketRegime)
    
    def test_position_sizing(self):
        """Test position sizing calculation"""
        signal_strengths = [0.5, 0.7, 0.9]
        
        for strength in signal_strengths:
            position_size = self.provider._calculate_position_size(strength)
            
            self.assertIsInstance(position_size, float)
            self.assertGreater(position_size, 0.0)
            self.assertLessEqual(position_size, self.provider.config["risk"]["max_position_size"])
    
    def test_api_methods(self):
        """Test public API methods"""
        # Test get_current_regime
        regime_info = self.provider.get_current_regime()
        self.assertIsNone(regime_info)  # Should be None initially
        
        # Test get_latest_signals
        signals = self.provider.get_latest_signals()
        self.assertIsInstance(signals, list)
        self.assertEqual(len(signals), 0)  # Should be empty initially
        
        # Test get_status
        status = self.provider.get_status()
        self.assertIsInstance(status, dict)
        self.assertIn("running", status)
        self.assertIn("symbols_tracked", status)

class TestSignalProviderAPI(unittest.TestCase):
    """Test the Signal Provider API"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = SignalProviderAPI(symbols=["SPY"])
        
    def tearDown(self):
        """Clean up after tests"""
        if self.api.is_running:
            self.api.stop()
    
    def test_api_initialization(self):
        """Test API initialization"""
        result = self.api.initialize()
        
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertTrue(result["success"])
        self.assertIsNotNone(self.api.provider)
    
    def test_api_start_stop(self):
        """Test API start and stop"""
        # Initialize first
        self.api.initialize()
        
        # Test start
        start_result = self.api.start()
        self.assertTrue(start_result["success"])
        self.assertTrue(self.api.is_running)
        
        # Test stop
        stop_result = self.api.stop()
        self.assertTrue(stop_result["success"])
        self.assertFalse(self.api.is_running)
    
    def test_api_status(self):
        """Test API status methods"""
        # Test before initialization
        status = self.api.get_status()
        self.assertFalse(status["initialized"])
        
        # Test after initialization
        self.api.initialize()
        status = self.api.get_status()
        self.assertTrue(status["initialized"])
        self.assertIn("symbols", status)
    
    def test_api_regime_methods(self):
        """Test regime-related API methods"""
        # Test get_current_regime
        regime = self.api.get_current_regime()
        self.assertIsInstance(regime, dict)
        self.assertIn("regime", regime)
        self.assertIn("confidence", regime)
        
        # Test get_regime_history (requires initialization)
        self.api.initialize()
        history = self.api.get_regime_history()
        self.assertIsInstance(history, dict)
        self.assertIn("success", history)
    
    def test_api_signal_methods(self):
        """Test signal-related API methods"""
        # Test get_signals
        signals = self.api.get_signals()
        self.assertIsInstance(signals, dict)
        self.assertIn("signals", signals)
        self.assertIn("count", signals)
        self.assertEqual(signals["count"], 0)  # Should be empty initially
    
    def test_api_data_methods(self):
        """Test data-related API methods"""
        # Test get_market_data (requires initialization)
        self.api.initialize()
        data = self.api.get_market_data()
        self.assertIsInstance(data, dict)
        self.assertIn("success", data)
    
    def test_api_subscription(self):
        """Test event subscription functionality"""
        callback_called = False
        
        def test_callback(data):
            nonlocal callback_called
            callback_called = True
        
        # Test subscription
        result = self.api.subscribe_to_events("regime", test_callback)
        self.assertTrue(result["success"])
        
        # Test unsubscription
        result = self.api.unsubscribe_from_events("regime", test_callback)
        self.assertTrue(result["success"])
    
    def test_api_configuration(self):
        """Test configuration methods"""
        # Test get_configuration
        config = self.api.get_configuration()
        self.assertIsInstance(config, dict)
        self.assertIn("symbols", config)
        
        # Test update_configuration
        new_config = {"test": "value"}
        result = self.api.update_configuration(new_config)
        self.assertTrue(result["success"])
        self.assertTrue(result["restart_required"])

class TestIntegrationExamples(unittest.TestCase):
    """Test integration examples"""
    
    def test_signal_provider_integration(self):
        """Test SignalProviderIntegration class"""
        integration = SignalProviderIntegration()
        
        # Test initialization
        provider = integration.initialize_provider(symbols=["SPY"])
        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, HMMSignalProvider)
        
        # Test callback registration
        callback_called = False
        
        def test_callback(data):
            nonlocal callback_called
            callback_called = True
        
        integration.register_callback("regime_changed", test_callback)
        
        # Test API methods
        regime_info = integration.get_current_regime()
        self.assertIsInstance(regime_info, dict)
        
        signals = integration.get_recent_signals()
        self.assertIsInstance(signals, list)
        
        status = integration.get_system_status()
        self.assertIsInstance(status, dict)
    
    def test_simple_integration_example(self):
        """Test SimpleIntegrationExample class"""
        example = SimpleIntegrationExample()
        
        self.assertIsNotNone(example.integration)
        self.assertIsInstance(example.integration, SignalProviderIntegration)

class TestDataStructures(unittest.TestCase):
    """Test data structures and types"""
    
    def test_trading_signal(self):
        """Test TradingSignal data structure"""
        signal = TradingSignal(
            symbol="SPY",
            signal_type="BUY",
            confidence=0.75,
            regime=MarketRegime.LOW_VOLATILITY_TRENDING,
            strategy="momentum",
            entry_price=450.0
        )
        
        self.assertEqual(signal.symbol, "SPY")
        self.assertEqual(signal.signal_type, "BUY")
        self.assertEqual(signal.confidence, 0.75)
        self.assertEqual(signal.regime, MarketRegime.LOW_VOLATILITY_TRENDING)
        self.assertIsInstance(signal.timestamp, datetime)
    
    def test_regime_update(self):
        """Test RegimeUpdate data structure"""
        regime_update = RegimeUpdate(
            regime=MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING,
            confidence=0.85
        )
        
        self.assertEqual(regime_update.regime, MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING)
        self.assertEqual(regime_update.confidence, 0.85)
        self.assertIsInstance(regime_update.timestamp, datetime)
    
    def test_market_data(self):
        """Test MarketData data structure"""
        sample_df = pd.DataFrame({
            'Close': [100, 101, 102],
            'Volume': [1000, 1100, 1200]
        })
        
        market_data = MarketData(
            symbol="SPY",
            data=sample_df
        )
        
        self.assertEqual(market_data.symbol, "SPY")
        self.assertIsInstance(market_data.data, pd.DataFrame)
        self.assertIsInstance(market_data.timestamp, datetime)

class TestPerformanceAndStability(unittest.TestCase):
    """Test performance and stability"""
    
    def test_memory_usage(self):
        """Test memory usage doesn't grow excessively"""
        provider = HMMSignalProvider(symbols=["SPY"])
        
        # Simulate adding many signals
        for i in range(1000):
            signal = TradingSignal(
                symbol="SPY",
                signal_type="BUY" if i % 2 == 0 else "SELL",
                confidence=0.5 + (i % 50) / 100,
                regime=MarketRegime.LOW_VOLATILITY_TRENDING,
                strategy="test",
                entry_price=100.0 + i
            )
            provider.signal_history.append(signal)
        
        # Check that history is limited
        self.assertLessEqual(len(provider.signal_history), 1000)
        
        provider.stop()
    
    def test_thread_safety(self):
        """Test thread safety of data access"""
        provider = HMMSignalProvider(symbols=["SPY"])
        provider.start()
        
        # Give it time to start
        time.sleep(2)
        
        # Access data from multiple threads
        def access_data():
            for _ in range(10):
                status = provider.get_status()
                regime = provider.get_current_regime()
                signals = provider.get_latest_signals()
                time.sleep(0.1)
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=access_data)
            threads.append(thread)
            thread.start()
        
        # Wait for threads to complete
        for thread in threads:
            thread.join(timeout=10)
        
        provider.stop()
    
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        provider = HMMSignalProvider(symbols=["INVALID_SYMBOL"])
        
        # Test with invalid symbol (should handle gracefully)
        provider.start()
        time.sleep(5)  # Let it try to get data
        
        # Should still be running despite data errors
        self.assertTrue(provider.running)
        
        provider.stop()

class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions"""
    
    def test_create_signal_provider(self):
        """Test create_signal_provider function"""
        provider = create_signal_provider(symbols=["SPY"])
        
        self.assertIsInstance(provider, HMMSignalProvider)
        self.assertEqual(provider.symbols, ["SPY"])
    
    def test_create_api(self):
        """Test create_api function"""
        api = create_api(symbols=["SPY"])
        
        self.assertIsInstance(api, SignalProviderAPI)
        self.assertEqual(api.symbols, ["SPY"])
    
    def test_quick_start_api(self):
        """Test quick_start_api function"""
        api = quick_start_api(symbols=["SPY"])
        
        self.assertIsInstance(api, SignalProviderAPI)
        self.assertTrue(api.is_running)
        
        # Clean up
        api.stop()

def run_performance_test():
    """Run performance benchmarks"""
    print("\n" + "="*50)
    print("PERFORMANCE TESTS")
    print("="*50)
    
    # Test signal provider startup time
    print("Testing signal provider startup time...")
    start_time = time.time()
    
    provider = create_signal_provider(symbols=["SPY"])
    provider.start()
    
    startup_time = time.time() - start_time
    print(f"Startup time: {startup_time:.2f} seconds")
    
    # Test API response time
    print("Testing API response times...")
    api = SignalProviderAPI(symbols=["SPY"])
    api.initialize()
    
    # Test various API calls
    api_tests = [
        ("get_status", lambda: api.get_status()),
        ("get_current_regime", lambda: api.get_current_regime()),
        ("get_signals", lambda: api.get_signals()),
        ("get_configuration", lambda: api.get_configuration())
    ]
    
    for test_name, test_func in api_tests:
        start_time = time.time()
        result = test_func()
        response_time = time.time() - start_time
        print(f"{test_name}: {response_time*1000:.1f}ms")
    
    # Clean up
    provider.stop()
    
    print("Performance tests completed.")

def main():
    """Run all tests"""
    print("HMM Signal Provider - Test Suite")
    print("="*40)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestHMMSignalProvider,
        TestSignalProviderAPI,
        TestIntegrationExamples,
        TestDataStructures,
        TestPerformanceAndStability,
        TestConvenienceFunctions
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "="*40)
    print("TEST SUMMARY")
    print("="*40)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success rate: {success_rate:.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}")
    
    # Run performance tests
    try:
        run_performance_test()
    except Exception as e:
        print(f"\nPerformance test failed: {e}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

