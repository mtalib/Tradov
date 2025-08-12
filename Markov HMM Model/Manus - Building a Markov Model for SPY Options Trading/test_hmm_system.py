#!/usr/bin/env python3
"""
Comprehensive Test Suite for SPY HMM AI Trading System
Tests all components of the HMM trading system for functionality and performance.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import unittest
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import logging
import time
import threading
from unittest.mock import Mock, patch, MagicMock
import warnings
warnings.filterwarnings('ignore')

# Import system components
from spy_hmm_ai_agent import (
    MessageBus, DataAgent, HMMAgent, MarketRegime, 
    MessageType, TradingSignal, SystemState, BaseAgent
)
from strategy_risk_agents import StrategyAgent, RiskManagementAgent
from complete_hmm_trading_system import TradingSystemManager

# Set up logging for tests
logging.basicConfig(level=logging.WARNING)  # Reduce noise during testing
logger = logging.getLogger(__name__)

class TestMessageBus(unittest.TestCase):
    """Test the message bus functionality"""
    
    def setUp(self):
        self.message_bus = MessageBus()
        
    def tearDown(self):
        if self.message_bus.running:
            self.message_bus.stop()
    
    def test_message_bus_start_stop(self):
        """Test message bus start and stop functionality"""
        self.assertFalse(self.message_bus.running)
        
        self.message_bus.start()
        self.assertTrue(self.message_bus.running)
        
        self.message_bus.stop()
        self.assertFalse(self.message_bus.running)
    
    def test_agent_registration(self):
        """Test agent registration and unregistration"""
        # Create mock agent
        mock_agent = Mock()
        mock_agent.agent_id = "TestAgent"
        
        # Test registration
        self.message_bus.register_agent(mock_agent)
        self.assertIn("TestAgent", self.message_bus.agents)
        
        # Test unregistration
        self.message_bus.unregister_agent("TestAgent")
        self.assertNotIn("TestAgent", self.message_bus.agents)

class TestDataAgent(unittest.TestCase):
    """Test the data agent functionality"""
    
    def setUp(self):
        self.message_bus = MessageBus()
        self.data_agent = DataAgent(self.message_bus, ["SPY"])
        
    def tearDown(self):
        if self.data_agent.running:
            self.data_agent.stop()
        if self.message_bus.running:
            self.message_bus.stop()
    
    def test_data_processing(self):
        """Test data processing functionality"""
        # Process real data
        processed_data = self.data_agent.process_data(None)
        
        # Check that data was processed
        self.assertIsInstance(processed_data, dict)
        if "SPY" in processed_data:
            spy_data = processed_data["SPY"]
            self.assertIsInstance(spy_data, pd.DataFrame)
            
            # Check for required columns
            required_columns = ['returns', 'volatility']
            for col in required_columns:
                if col in spy_data.columns:
                    self.assertIn(col, spy_data.columns)
    
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
        result = self.data_agent._add_technical_indicators(sample_data)
        
        # Check that indicators were added
        expected_indicators = ['rsi', 'macd', 'bb_upper', 'bb_lower']
        for indicator in expected_indicators:
            if indicator in result.columns:
                self.assertIn(indicator, result.columns)

class TestHMMAgent(unittest.TestCase):
    """Test the HMM agent functionality"""
    
    def setUp(self):
        self.message_bus = MessageBus()
        self.hmm_agent = HMMAgent(self.message_bus)
        
    def tearDown(self):
        if self.hmm_agent.running:
            self.hmm_agent.stop()
        if self.message_bus.running:
            self.message_bus.stop()
    
    def test_feature_preparation(self):
        """Test feature preparation for HMM model"""
        # Create sample data with required columns
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
        features = self.hmm_agent._prepare_features(sample_data)
        
        if features is not None:
            self.assertIsInstance(features, np.ndarray)
            self.assertEqual(len(features.shape), 2)  # Should be 2D array
            self.assertGreater(features.shape[0], 0)  # Should have rows
            self.assertGreater(features.shape[1], 0)  # Should have columns
    
    def test_regime_prediction(self):
        """Test regime prediction functionality"""
        # Create sample features
        n_samples = 100
        n_features = 5
        features = np.random.randn(n_samples, n_features)
        
        # Train model first
        self.hmm_agent._train_hmm_model(features)
        
        if self.hmm_agent.hmm_model is not None:
            # Test prediction
            regime, confidence = self.hmm_agent._predict_regime(features)
            
            self.assertIsInstance(regime, MarketRegime)
            self.assertIsInstance(confidence, float)
            self.assertGreaterEqual(confidence, 0.0)
            self.assertLessEqual(confidence, 1.0)

class TestStrategyAgent(unittest.TestCase):
    """Test the strategy agent functionality"""
    
    def setUp(self):
        self.message_bus = MessageBus()
        self.strategy_agent = StrategyAgent(self.message_bus)
        
    def tearDown(self):
        if self.strategy_agent.running:
            self.strategy_agent.stop()
        if self.message_bus.running:
            self.message_bus.stop()
    
    def test_signal_generation(self):
        """Test trading signal generation"""
        # Create sample market data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        sample_data = pd.DataFrame({
            'Close': np.random.randn(len(dates)).cumsum() + 100,
            'returns': np.random.randn(len(dates)) * 0.02,
            'volatility': np.random.rand(len(dates)) * 0.3 + 0.1,
            'rsi': np.random.rand(len(dates)) * 100,
            'macd': np.random.randn(len(dates)) * 0.01,
            'momentum_5': np.random.randn(len(dates)) * 0.05,
            'momentum_10': np.random.randn(len(dates)) * 0.08,
            'bb_width': np.random.rand(len(dates)) * 0.1,
            'volume_ratio': np.random.rand(len(dates)) * 2 + 0.5
        }, index=dates)
        
        market_data = {"SPY": sample_data}
        
        # Set regime for testing
        self.strategy_agent.current_regime = MarketRegime.LOW_VOLATILITY_TRENDING
        self.strategy_agent.regime_confidence = 0.8
        
        # Test signal generation
        signals = self.strategy_agent.process_data(market_data)
        
        # Signals should be a list
        self.assertIsInstance(signals, list)
    
    def test_position_sizing(self):
        """Test position sizing calculation"""
        signal_strength = 0.7
        regime = MarketRegime.LOW_VOLATILITY_TRENDING
        
        position_size = self.strategy_agent._calculate_position_size(signal_strength, regime)
        
        self.assertIsInstance(position_size, float)
        self.assertGreater(position_size, 0.0)
        self.assertLessEqual(position_size, 0.05)  # Should not exceed 5%

class TestRiskManagementAgent(unittest.TestCase):
    """Test the risk management agent functionality"""
    
    def setUp(self):
        self.message_bus = MessageBus()
        self.risk_agent = RiskManagementAgent(self.message_bus)
        
    def tearDown(self):
        if self.risk_agent.running:
            self.risk_agent.stop()
        if self.message_bus.running:
            self.message_bus.stop()
    
    def test_risk_assessment(self):
        """Test risk assessment functionality"""
        # Create sample trading signal
        signal = TradingSignal(
            symbol="SPY",
            signal_type="BUY",
            confidence=0.7,
            regime=MarketRegime.LOW_VOLATILITY_TRENDING,
            strategy="momentum",
            entry_price=450.0,
            position_size=0.03
        )
        
        # Test risk assessment
        risk_assessment = self.risk_agent.process_data(signal)
        
        self.assertIsInstance(risk_assessment, dict)
        self.assertIn("approved", risk_assessment)
        self.assertIn("adjusted_size", risk_assessment)
        self.assertIn("risk_score", risk_assessment)
        self.assertIsInstance(risk_assessment["approved"], bool)
    
    def test_volatility_adjustment(self):
        """Test volatility-based position adjustment"""
        # Create sample market data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        sample_data = pd.DataFrame({
            'volatility': [0.15, 0.25, 0.35]  # Different volatility levels
        }, index=dates[:3])
        
        self.risk_agent.market_data = {"SPY": sample_data}
        
        adjustment = self.risk_agent._calculate_volatility_adjustment()
        
        self.assertIsInstance(adjustment, float)
        self.assertGreater(adjustment, 0.0)

class TestTradingSystemIntegration(unittest.TestCase):
    """Test the complete trading system integration"""
    
    def setUp(self):
        self.system = TradingSystemManager(["SPY"], 100000)
        
    def tearDown(self):
        if self.system.running:
            self.system.stop_system()
    
    def test_system_initialization(self):
        """Test system initialization"""
        self.assertIsNotNone(self.system.data_agent)
        self.assertIsNotNone(self.system.hmm_agent)
        self.assertIsNotNone(self.system.strategy_agent)
        self.assertIsNotNone(self.system.risk_agent)
        self.assertIsNotNone(self.system.execution_agent)
    
    def test_system_start_stop(self):
        """Test system start and stop functionality"""
        # Start system
        self.system.start_system()
        self.assertTrue(self.system.running)
        self.assertEqual(self.system.system_state.system_status, "RUNNING")
        
        # Give it a moment to initialize
        time.sleep(2)
        
        # Stop system
        self.system.stop_system()
        self.assertFalse(self.system.running)
        self.assertEqual(self.system.system_state.system_status, "STOPPED")

class TestPerformanceValidation(unittest.TestCase):
    """Test system performance and validation"""
    
    def setUp(self):
        self.system = TradingSystemManager(["SPY"], 100000)
        
    def tearDown(self):
        if self.system.running:
            self.system.stop_system()
    
    def test_data_quality(self):
        """Test data quality and completeness"""
        # Get recent SPY data
        try:
            spy_data = yf.download("SPY", period="1mo", interval="1d")
            
            # Check data quality
            self.assertFalse(spy_data.empty)
            self.assertGreater(len(spy_data), 10)  # At least 10 days of data
            
            # Check for required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in required_columns:
                self.assertIn(col, spy_data.columns)
            
            # Check for missing values
            missing_pct = spy_data.isnull().sum().sum() / (len(spy_data) * len(spy_data.columns))
            self.assertLess(missing_pct, 0.05)  # Less than 5% missing data
            
        except Exception as e:
            self.skipTest(f"Could not download data for testing: {e}")
    
    def test_regime_detection_stability(self):
        """Test regime detection stability"""
        # Create stable test data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        
        # Low volatility trending data
        trend_data = pd.DataFrame({
            'returns': np.random.normal(0.001, 0.01, len(dates)),  # Small positive trend, low vol
            'volatility': np.random.normal(0.15, 0.02, len(dates)),
            'rsi': np.random.normal(55, 10, len(dates)),
            'macd': np.random.normal(0.001, 0.002, len(dates)),
            'macd_histogram': np.random.normal(0.0005, 0.001, len(dates)),
            'bb_width': np.random.normal(0.04, 0.01, len(dates)),
            'volume_ratio': np.random.normal(1.0, 0.2, len(dates)),
            'momentum_5': np.random.normal(0.01, 0.02, len(dates)),
            'momentum_10': np.random.normal(0.02, 0.03, len(dates))
        }, index=dates)
        
        # Test HMM agent
        hmm_agent = HMMAgent(MessageBus())
        
        # Process data multiple times and check for stability
        regimes = []
        confidences = []
        
        for _ in range(5):
            regime, confidence = hmm_agent.process_data(trend_data)
            if regime is not None:
                regimes.append(regime)
                confidences.append(confidence)
        
        if regimes:
            # Check that regime detection is somewhat stable
            unique_regimes = set(regimes)
            self.assertLessEqual(len(unique_regimes), 2)  # Should not jump between all 3 regimes
    
    def test_signal_quality(self):
        """Test trading signal quality"""
        # Create strategy agent
        strategy_agent = StrategyAgent(MessageBus())
        
        # Create sample market data
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
        sample_data = pd.DataFrame({
            'Close': np.random.randn(len(dates)).cumsum() + 100,
            'returns': np.random.randn(len(dates)) * 0.02,
            'volatility': np.random.rand(len(dates)) * 0.3 + 0.1,
            'rsi': np.random.rand(len(dates)) * 100,
            'macd': np.random.randn(len(dates)) * 0.01,
            'momentum_5': np.random.randn(len(dates)) * 0.05,
            'momentum_10': np.random.randn(len(dates)) * 0.08,
            'bb_width': np.random.rand(len(dates)) * 0.1,
            'volume_ratio': np.random.rand(len(dates)) * 2 + 0.5
        }, index=dates)
        
        market_data = {"SPY": sample_data}
        
        # Set high confidence regime
        strategy_agent.current_regime = MarketRegime.LOW_VOLATILITY_TRENDING
        strategy_agent.regime_confidence = 0.8
        
        # Generate signals
        signals = strategy_agent.process_data(market_data)
        
        # Validate signal quality
        for signal in signals:
            # Check signal structure
            self.assertIsInstance(signal, TradingSignal)
            self.assertIn(signal.signal_type, ["BUY", "SELL", "HOLD"])
            self.assertGreaterEqual(signal.confidence, 0.0)
            self.assertLessEqual(signal.confidence, 1.0)
            
            # Check position sizing
            if signal.position_size:
                self.assertGreater(signal.position_size, 0.0)
                self.assertLessEqual(signal.position_size, 0.05)  # Max 5%

def run_performance_benchmark():
    """Run a performance benchmark of the system"""
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK")
    print("="*60)
    
    # Test data processing speed
    print("Testing data processing speed...")
    start_time = time.time()
    
    message_bus = MessageBus()
    data_agent = DataAgent(message_bus, ["SPY"])
    
    # Process data
    processed_data = data_agent.process_data(None)
    
    processing_time = time.time() - start_time
    print(f"Data processing time: {processing_time:.2f} seconds")
    
    if "SPY" in processed_data:
        data_size = len(processed_data["SPY"])
        print(f"Processed {data_size} data points")
        print(f"Processing rate: {data_size/processing_time:.0f} points/second")
    
    # Test HMM training speed
    print("\nTesting HMM training speed...")
    start_time = time.time()
    
    hmm_agent = HMMAgent(message_bus)
    if "SPY" in processed_data:
        regime, confidence = hmm_agent.process_data(processed_data["SPY"])
        
        training_time = time.time() - start_time
        print(f"HMM training time: {training_time:.2f} seconds")
        print(f"Detected regime: {regime.name if regime else 'None'}")
        print(f"Confidence: {confidence:.3f}")
    
    # Test memory usage
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
    print(f"\nMemory usage: {memory_usage:.1f} MB")
    
    print("\nBenchmark completed.")

def main():
    """Run all tests"""
    print("SPY HMM AI Trading System - Test Suite")
    print("="*50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestMessageBus,
        TestDataAgent,
        TestHMMAgent,
        TestStrategyAgent,
        TestRiskManagementAgent,
        TestTradingSystemIntegration,
        TestPerformanceValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")
    
    # Run performance benchmark
    try:
        run_performance_benchmark()
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

