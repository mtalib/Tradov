Standards/Python/Testing-Standards.md

```markdown
# Python Testing Standards for Tradov Trading System

## Overview

Testing is critical in the Tradov trading system because bugs can result in financial losses. This document defines comprehensive testing standards covering unit tests, integration tests, paper trading validation, and live system testing protocols.

## Testing Framework Structure

### Core Testing Architecture

```python
# TradovT_Testing/TradovT01_UnitTestFramework.py
"""
Core testing framework for the Tradov trading system.

Provides base classes, fixtures, and utilities for all testing
throughout the system.
"""

import pytest
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, List, Any, Optional

class TradovTestBase:
    """
    Base class for all Tradov tests.
    
    Provides common setup, teardown, and utility methods that
    all test classes should inherit from.
    """
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup run before each test method."""
        self.start_time = datetime.now()
        # Setup test environment
        
    @pytest.fixture(autouse=True)  
    def teardown_method(self):
        """Cleanup run after each test method."""
        # Cleanup test environment
        elapsed = datetime.now() - self.start_time
        print(f"Test completed in {elapsed.total_seconds():.2f}s")

class MockDataProvider:
    """Mock data provider for testing without live market data."""
    
    @staticmethod
    def generate_option_chain(symbol: str, expiry: datetime) -> Dict[str, Any]:
        """Generate realistic mock option chain data."""
        # Implementation for generating test data
        
    @staticmethod
    def generate_market_data(symbol: str, bars: int = 100) -> pd.DataFrame:
        """Generate realistic market data for testing."""
        # Implementation for generating OHLCV data
```

## Unit Testing Standards

### Test Organization

```python
# Test file naming: test_TradovX##_ModuleName.py
# Example: TradovT_Testing/test_TradovD02_IronCondor.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from TradovD_Strategies.TradovD02_IronCondor import IronCondorStrategy
from TradovT_Testing.TradovT01_UnitTestFramework import TradovTestBase

class TestIronCondorStrategy(TradovTestBase):
    """
    Unit tests for Iron Condor strategy implementation.
    
    Tests cover:
    - Strategy initialization and configuration
    - Signal generation logic
    - Position sizing calculations
    - Risk management integration
    - Error handling and edge cases
    """
    
    def setup_method(self):
        """Setup test fixtures before each test."""
        super().setup_method()
        
        # Create strategy instance with test configuration
        self.config = {
            'target_delta': 0.15,
            'max_dte': 45,
            'min_dte': 7,
            'profit_target': 0.25,
            'stop_loss': 2.0
        }
        
        self.strategy = IronCondorStrategy("test_iron_condor", self.config)
        
        # Mock external dependencies
        self.mock_broker = Mock()
        self.mock_data_provider = Mock()
        self.mock_risk_manager = Mock()
        
    def test_strategy_initialization(self):
        """Test strategy initializes correctly with valid configuration."""
        # Arrange - setup done in setup_method
        
        # Act
        result = self.strategy.initialize()
        
        # Assert
        assert result is True
        assert self.strategy.name == "test_iron_condor"
        assert self.strategy.config['target_delta'] == 0.15
        assert self.strategy.state == StrategyState.READY
        
    def test_strategy_initialization_invalid_config(self):
        """Test strategy handles invalid configuration gracefully."""
        # Arrange
        invalid_config = {'target_delta': -0.5}  # Invalid negative delta
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid target_delta"):
            strategy = IronCondorStrategy("test", invalid_config)
            strategy.initialize()
            
    @patch('TradovC_MarketData.TradovC03_OptionChain.get_option_chain')
    def test_signal_generation_with_valid_data(self, mock_option_chain):
        """Test signal generation with valid option chain data."""
        # Arrange
        mock_option_chain.return_value = self._create_mock_option_chain()
        market_data = self._create_mock_market_data()
        
        # Act
        signals = self.strategy.generate_signals(market_data)
        
        # Assert
        assert len(signals) > 0
        signal = signals[0]
        assert signal['strategy'] == 'iron_condor'
        assert 'call_spread' in signal
        assert 'put_spread' in signal
        assert signal['risk_reward_ratio'] > 0
        
    def test_position_sizing_calculation(self):
        """Test position sizing respects risk management rules."""
        # Arrange
        signal = {
            'max_risk': 500.0,
            'max_reward': 125.0,
            'probability_of_profit': 0.75
        }
        
        # Act
        position_size = self.strategy.calculate_position_size(signal)
        
        # Assert
        assert position_size > 0
        assert position_size <= self.strategy.max_position_size
        
    def _create_mock_option_chain(self) -> Dict[str, Any]:
        """Helper method to create realistic mock option chain."""
        return {
            'symbol': 'SPY',
            'expiry': datetime(2025, 2, 21),
            'calls': {
                440.0: {'bid': 2.1, 'ask': 2.3, 'delta': 0.15, 'iv': 0.18},
                445.0: {'bid': 1.2, 'ask': 1.4, 'delta': 0.10, 'iv': 0.19}
            },
            'puts': {
                435.0: {'bid': 1.8, 'ask': 2.0, 'delta': -0.12, 'iv': 0.17},
                430.0: {'bid': 1.0, 'ask': 1.2, 'delta': -0.08, 'iv': 0.18}
            }
        }
```

### Test Categories and Requirements

#### 1. Functionality Tests
```python
def test_option_pricing_accuracy(self):
    """Test Black-Scholes option pricing matches expected values."""
    # Test known values with high precision
    price = calculate_option_price(
        spot=100.0, strike=105.0, time=0.25, vol=0.20, rate=0.02
    )
    expected = 3.4567  # Known theoretical value
    assert abs(price - expected) < 0.0001
    
def test_greeks_calculation_accuracy(self):
    """Test Greeks calculations match theoretical values."""
    greeks = calculate_greeks(100.0, 105.0, 0.25, 0.20, 0.02)
    
    # Test delta
    assert 0.40 < greeks['delta'] < 0.50  # Expected range for ATM call
    
    # Test gamma (should be highest for ATM options)
    assert greeks['gamma'] > 0.01
    
    # Test theta (should be negative for long options)
    assert greeks['theta'] < 0
```

#### 2. Error Handling Tests
```python
def test_invalid_input_handling(self):
    """Test function handles invalid inputs gracefully."""
    with pytest.raises(ValueError):
        calculate_option_price(
            spot=-100.0,  # Invalid negative price
            strike=105.0, 
            time=0.25, 
            vol=0.20, 
            rate=0.02
        )
        
    with pytest.raises(ZeroDivisionError):
        calculate_option_price(
            spot=100.0, 
            strike=105.0, 
            time=0.0,  # Invalid zero time
            vol=0.20, 
            rate=0.02
        )

def test_network_error_handling(self):
    """Test system handles network failures gracefully."""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = ConnectionError("Network unavailable")
        
        result = fetch_market_data("SPY")
        
        assert result is None  # Should return None, not crash
        # Verify error was logged
        assert "Network unavailable" in captured_logs
```

#### 3. Edge Case Tests
```python
def test_market_close_behavior(self):
    """Test behavior when market is closed."""
    with patch('TradovU_Utilities.TradovU10_TradingCalendar.is_market_open') as mock_open:
        mock_open.return_value = False
        
        result = submit_order({'symbol': 'SPY', 'quantity': 100})
        
        assert result['success'] is False
        assert 'market closed' in result['error_message'].lower()

def test_extreme_volatility_handling(self):
    """Test system behavior during extreme volatility events."""
    # Test with very high volatility (>100%)
    high_vol_data = create_market_data_with_volatility(2.5)
    
    signals = strategy.generate_signals(high_vol_data)
    
    # Strategy should reduce position sizes or avoid trading
    if signals:
        for signal in signals:
            assert signal['position_size'] < strategy.normal_position_size
```

#### 4. Performance Tests
```python
@pytest.mark.performance
def test_signal_generation_performance(self):
    """Test signal generation completes within acceptable time."""
    large_dataset = generate_market_data(rows=10000)
    
    start_time = time.time()
    signals = strategy.generate_signals(large_dataset)
    elapsed = time.time() - start_time
    
    # Should process 10k rows in under 1 second
    assert elapsed < 1.0
    
@pytest.mark.performance  
def test_concurrent_strategy_execution(self):
    """Test multiple strategies can run concurrently without conflicts."""
    strategies = [create_test_strategy(f"test_{i}") for i in range(5)]
    
    ## Run strategies concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(strategy.run_test_cycle) for strategy in strategies]
        results = [future.result() for future in futures]
    
    # All strategies should complete successfully
    assert all(result['success'] for result in results)
    
    # No resource conflicts or data corruption
    assert len(set(result['strategy_id'] for result in results)) == 5
```

## Integration Testing Standards

### Broker Integration Tests
```python
class TestBrokerIntegration(TradovTestBase):
    """
    Integration tests for broker connectivity and order execution.
    
    These tests require a connection to IBKR paper trading account.
    They validate end-to-end functionality without risking real money.
    """
    
    @pytest.mark.integration
    @pytest.mark.requires_broker_connection
    def test_connection_establishment(self):
        """Test successful connection to IBKR paper trading."""
        # Arrange
        broker_client = IBKRClient(
            host='127.0.0.1',
            port=4002,  # Paper trading port
            client_id=1
        )
        
        # Act
        connection_result = broker_client.connect(timeout=30)
        
        # Assert
        assert connection_result is True
        assert broker_client.is_connected()
        assert broker_client.account_id is not None
        
        # Cleanup
        broker_client.disconnect()
        
    @pytest.mark.integration
    def test_market_data_subscription(self):
        """Test real-time market data subscription."""
        # Arrange
        data_manager = MarketDataManager()
        received_data = []
        
        def data_callback(ticker_data):
            received_data.append(ticker_data)
        
        # Act
        data_manager.subscribe_ticker('SPY', data_callback)
        time.sleep(5)  # Wait for data
        
        # Assert
        assert len(received_data) > 0
        latest_data = received_data[-1]
        assert 'bid' in latest_data
        assert 'ask' in latest_data
        assert latest_data['bid'] > 0
        assert latest_data['ask'] > latest_data['bid']
        
        # Cleanup
        data_manager.unsubscribe_ticker('SPY')
        
    @pytest.mark.integration
    @pytest.mark.paper_trading_only
    def test_option_order_lifecycle(self):
        """Test complete option order lifecycle in paper trading."""
        # Arrange
        order_manager = OrderManager()
        option_order = {
            'symbol': 'SPY',
            'strike': 450.0,
            'expiry': get_next_monthly_expiry(),
            'option_type': 'CALL',
            'action': 'BUY',
            'quantity': 1,
            'order_type': 'LMT',
            'limit_price': 2.50
        }
        
        # Act - Submit Order
        order_id = order_manager.submit_order(option_order)
        assert order_id is not None
        
        # Wait for order to be acknowledged
        time.sleep(2)
        order_status = order_manager.get_order_status(order_id)
        assert order_status in ['SUBMITTED', 'FILLED', 'PENDING']
        
        # Cancel if not filled (to avoid leaving open orders)
        if order_status != 'FILLED':
            cancel_result = order_manager.cancel_order(order_id)
            assert cancel_result is True
```

### Database Integration Tests
```python
class TestDatabaseIntegration(TradovTestBase):
    """Integration tests for database operations."""
    
    @pytest.fixture
    def test_database(self):
        """Create isolated test database."""
        test_db_path = "test_tradov.db"
        db_manager = DatabaseManager(test_db_path)
        db_manager.initialize_schema()
        yield db_manager
        # Cleanup
        os.remove(test_db_path)
        
    def test_trade_storage_and_retrieval(self, test_database):
        """Test storing and retrieving trade data."""
        # Arrange
        test_trade = {
            'trade_id': 'TEST_001',
            'strategy': 'iron_condor',
            'symbol': 'SPY',
            'entry_time': datetime.now(),
            'quantity': 10,
            'entry_price': 1.25,
            'commission': 5.00
        }
        
        # Act - Store trade
        result = test_database.store_trade(test_trade)
        assert result is True
        
        # Act - Retrieve trade
        retrieved_trade = test_database.get_trade('TEST_001')
        
        # Assert
        assert retrieved_trade is not None
        assert retrieved_trade['trade_id'] == 'TEST_001'
        assert retrieved_trade['strategy'] == 'iron_condor'
        assert abs(retrieved_trade['entry_price'] - 1.25) < 0.01
        
    def test_performance_data_aggregation(self, test_database):
        """Test performance metrics calculation from stored trades."""
        # Arrange - Store multiple trades
        trades = [
            create_test_trade('T001', pnl=100.0),
            create_test_trade('T002', pnl=-50.0),
            create_test_trade('T003', pnl=75.0),
            create_test_trade('T004', pnl=25.0)
        ]
        
        for trade in trades:
            test_database.store_trade(trade)
            
        # Act
        performance = test_database.calculate_performance_metrics(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now()
        )
        
        # Assert
        assert performance['total_pnl'] == 150.0
        assert performance['win_rate'] == 0.75  # 3 out of 4 trades profitable
        assert performance['average_win'] == (100 + 75 + 25) / 3
```

## Paper Trading Validation

### Paper Trading Test Framework
```python
class PaperTradingValidator(TradovTestBase):
    """
    Comprehensive paper trading validation framework.
    
    Validates strategies in simulated environment before live deployment.
    """
    
    def test_strategy_paper_trading_cycle(self):
        """Test complete strategy execution in paper trading mode."""
        # Arrange
        strategy = IronCondorStrategy("paper_test", self.get_test_config())
        paper_engine = PaperTradingEngine()
        
        # Configure paper trading environment
        paper_engine.set_initial_capital(100000)
        paper_engine.set_commission_structure(stock=1.0, option=0.65)
        
        # Act - Run strategy for paper trading period
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        results = paper_engine.run_strategy(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date
        )
        
        # Assert - Validate results
        assert results['trades_executed'] > 0
        assert 'total_pnl' in results
        assert 'max_drawdown' in results
        assert 'sharpe_ratio' in results
        
        # Risk checks
        assert results['max_drawdown'] < 0.10  # Max 10% drawdown
        assert results['max_single_loss'] < 1000  # Max $1000 single loss
        
    def test_strategy_risk_compliance(self):
        """Test strategy complies with all risk management rules."""
        # Test position sizing limits
        # Test correlation limits
        # Test maximum exposure limits
        # Test stop-loss functionality
        pass
        
    def test_strategy_market_condition_adaptation(self):
        """Test strategy adapts to different market conditions."""
        # Test behavior in high volatility
        # Test behavior in low volatility
        # Test behavior during market stress
        pass
```

### Automated Paper Trading Validation
```python
@pytest.mark.paper_trading
@pytest.mark.overnight
def test_automated_paper_trading_validation():
    """
    Automated overnight paper trading validation.
    
    This test runs continuously during market hours to validate
    real-time strategy performance in paper trading mode.
    """
    validation_config = {
        'max_runtime_hours': 8,  # Full trading day
        'max_drawdown_threshold': 0.05,  # 5%
        'min_trades_required': 5,
        'max_single_trade_risk': 500.0
    }
    
    validator = AutomatedPaperValidator(validation_config)
    
    # Run validation
    results = validator.run_full_day_validation()
    
    # Generate validation report
    report = validator.generate_validation_report(results)
    
    # Assert validation passed
    assert results['validation_passed'] is True
    assert results['risk_violations'] == 0
    
    # Save report for review
    with open(f"validation_report_{datetime.now().strftime('%Y%m%d')}.json", 'w') as f:
        json.dump(report, f, indent=2)
```

## Test Data Management

### Mock Data Generation
```python
class TestDataFactory:
    """Factory for generating realistic test data."""
    
    @staticmethod
    def create_realistic_market_data(
        symbol: str = 'SPY',
        days: int = 30,
        volatility: float = 0.20,
        trend: float = 0.0
    ) -> pd.DataFrame:
        """
        Generate realistic market data for testing.
        
        Args:
            symbol: Stock symbol
            days: Number of days of data
            volatility: Annual volatility (as decimal)
            trend: Annual return trend (as decimal)
            
        Returns:
            DataFrame with OHLCV data
        """
        np.random.seed(42)  # Reproducible results
        
        # Generate price series using geometric Brownian motion
        dt = 1/252  # Daily time step
        price_series = []
        current_price = 450.0  # Starting price for SPY
        
        for i in range(days * 24):  # Hourly data
            random_return = np.random.normal(
                trend * dt, 
                volatility * np.sqrt(dt)
            )
            current_price *= (1 + random_return)
            price_series.append(current_price)
            
        # Create OHLCV structure
        data = []
        for i in range(0, len(price_series), 24):  # Daily bars from hourly data
            day_prices = price_series[i:i+24]
            data.append({
                'timestamp': datetime.now() - timedelta(days=days-i//24),
                'open': day_prices[0],
                'high': max(day_prices),
                'low': min(day_prices),
                'close': day_prices[-1],
                'volume': np.random.randint(50_000_000, 150_000_000)
            })
            
        return pd.DataFrame(data)
        
    @staticmethod
    def create_option_chain_data(
        underlying_price: float,
        expiry: datetime,
        volatility: float = 0.20
    ) -> Dict[str, Any]:
        """Generate realistic option chain data."""
        
        strikes = np.arange(
            underlying_price * 0.8,  # 20% OTM puts
            underlying_price * 1.2,  # 20% OTM calls
            2.5  # Strike intervals
        )
        
        calls = {}
        puts = {}
        
        for strike in strikes:
            # Calculate theoretical prices and Greeks
            call_price = black_scholes_call(underlying_price, strike, 
                                          get_time_to_expiry(expiry), 
                                          volatility, 0.02)
            put_price = black_scholes_put(underlying_price, strike,
                                        get_time_to_expiry(expiry),
                                        volatility, 0.02)
            
            # Add bid-ask spread
            spread_pct = 0.05  # 5% spread
            
            calls[strike] = {
                'bid': call_price * (1 - spread_pct/2),
                'ask': call_price * (1 + spread_pct/2),
                'last': call_price,
                'volume': np.random.randint(0, 1000),
                'open_interest': np.random.randint(100, 5000),
                'iv': volatility + np.random.normal(0, 0.02)  # IV varies slightly
            }
            
            puts[strike] = {
                'bid': put_price * (1 - spread_pct/2),
                'ask': put_price * (1 + spread_pct/2),
                'last': put_price,
                'volume': np.random.randint(0, 1000), 
                'open_interest': np.random.randint(100, 5000),
                'iv': volatility + np.random.normal(0, 0.02)
            }
            
        return {
            'symbol': 'SPY',
            'underlying_price': underlying_price,
            'expiry': expiry,
            'calls': calls,
            'puts': puts,
            'timestamp': datetime.now()
        }
```

### Test Database Management
```python
class TestDatabaseManager:
    """Manages test databases with proper isolation."""
    
    def __init__(self):
        self.test_databases = {}
        
    def create_test_database(self, test_name: str) -> str:
        """Create isolated test database."""
        db_path = f"test_{test_name}_{uuid.uuid4().hex[:8]}.db"
        self.test_databases[test_name] = db_path
        
        # Initialize with test schema
        db_manager = DatabaseManager(db_path)
        db_manager.initialize_schema()
        
        return db_path
        
    def cleanup_test_databases(self):
        """Clean up all test databases."""
        for db_path in self.test_databases.values():
            if os.path.exists(db_path):
                os.remove(db_path)
        self.test_databases.clear()
        
    @contextmanager
    def temporary_database(self, test_name: str):
        """Context manager for temporary test database."""
        db_path = self.create_test_database(test_name)
        try:
            yield db_path
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
```

## Testing Configuration and Environment

### Test Configuration
```python
# conftest.py - pytest configuration
import pytest
import os
from typing import Generator

@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture."""
    return {
        'broker': {
            'host': '127.0.0.1',
            'port': 4002,  # Paper trading
            'client_id_base': 1000  # Use high client IDs for testing
        },
        'database': {
            'test_db_prefix': 'test_tradov_',
            'cleanup_on_exit': True
        },
        'timeouts': {
            'connection': 30,
            'data_fetch': 10,
            'order_execution': 15
        }
    }

@pytest.fixture
def mock_market_data():
    """Provide mock market data for tests."""
    return TestDataFactory.create_realistic_market_data()

@pytest.fixture
def paper_trading_environment():
    """Setup paper trading environment for integration tests."""
    # Verify paper trading mode
    assert os.getenv('TRADING_MODE', 'PAPER') == 'PAPER'
    
    # Setup paper trading client
    client = create_paper_trading_client()
    yield client
    
    # Cleanup
    client.disconnect()

# Test markers for different test categories
pytest.mark.unit = pytest.mark.mark("unit", "Unit tests")
pytest.mark.integration = pytest.mark.mark("integration", "Integration tests")
pytest.mark.paper_trading = pytest.mark.mark("paper_trading", "Paper trading tests")
pytest.mark.performance = pytest.mark.mark("performance", "Performance tests")
pytest.mark.slow = pytest.mark.mark("slow", "Slow running tests")
```

### Environment Setup
```python
# test_environment.py
class TestEnvironment:
    """Manages test environment setup and teardown."""
    
    @classmethod
    def setup_test_environment(cls):
        """Setup complete test environment."""
        # Set environment variables for testing
        os.environ['TRADING_MODE'] = 'PAPER'
        os.environ['LOG_LEVEL'] = 'DEBUG'
        os.environ['DATABASE_PATH'] = 'test_tradov.db'
        
        # Initialize test database
        cls._initialize_test_database()
        
        # Setup mock services
        cls._setup_mock_services()
        
    @classmethod
    def teardown_test_environment(cls):
        """Clean up test environment."""
        # Clean up test databases
        test_db_files = glob.glob('test_*.db')
        for db_file in test_db_files:
            os.remove(db_file)
            
        # Reset environment variables
        test_env_vars = ['TRADING_MODE', 'LOG_LEVEL', 'DATABASE_PATH']
        for var in test_env_vars:
            if var in os.environ:
                del os.environ[var]
```

## Test Execution and Reporting

### Test Suite Organization
```bash
# Run different test categories
pytest TradovT_Testing/ -m unit                    # Unit tests only
pytest TradovT_Testing/ -m integration             # Integration tests
pytest TradovT_Testing/ -m paper_trading           # Paper trading tests
pytest TradovT_Testing/ -m "not slow"              # Fast tests only

# Generate coverage report
pytest TradovT_Testing/ --cov=Tradov --cov-report=html

# Run performance tests
pytest TradovT_Testing/ -m performance --benchmark-only

# Parallel test execution
pytest TradovT_Testing/ -n auto                    # Auto-detect CPU cores
```

### Automated Test Reports
```python
class TestReportGenerator:
    """Generate comprehensive test reports."""
    
    def generate_test_report(self, test_results: Dict[str, Any]) -> str:
        """
        Generate comprehensive test report.
        
        Includes:
        - Test coverage analysis
        - Performance benchmarks
        - Risk compliance validation
        - Paper trading results
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'test_summary': {
                'total_tests': test_results['total'],
                'passed': test_results['passed'],
                'failed': test_results['failed'],
                'skipped': test_results['skipped'],
                'coverage_percentage': test_results.get('coverage', 0)
            },
            'risk_validation': {
                'max_drawdown_compliant': test_results.get('max_drawdown_ok', True),
                'position_limits_respected': test_results.get('position_limits_ok', True),
                'stop_loss_functional': test_results.get('stop_loss_ok', True)
            },
            'performance_benchmarks': test_results.get('benchmarks', {}),
            'paper_trading_results': test_results.get('paper_trading', {})
        }
        
        # Generate HTML report
        html_report = self._generate_html_report(report)
        
        # Save report
        report_path = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(report_path, 'w') as f:
            f.write(html_report)
            
        return report_path
```

## Continuous Testing Integration

### Pre-Commit Testing
```python
# .pre-commit-config.yaml equivalent in Python
class PreCommitValidator:
    """Validate code before commits."""
    
    def run_pre_commit_tests(self) -> bool:
        """Run essential tests before allowing commits."""
        
        # 1. Run fast unit tests
        unit_result = subprocess.run([
            'pytest', 'TradovT_Testing/', '-m', 'unit', '--maxfail=1'
        ], capture_output=True)
        
        if unit_result.returncode != 0:
            print("❌ Unit tests failed")
            return False
            
        # 2. Check code coverage
        coverage_result = subprocess.run([
            'pytest', '--cov=Tradov', '--cov-fail-under=80'
        ], capture_output=True)
        
        if coverage_result.returncode != 0:
            print("❌ Code coverage below 80%")
            return False
            
        # 3. Run linting
        lint_result = subprocess.run(['flake8', 'Tradov/'], capture_output=True)
        if lint_result.returncode != 0:
            print("❌ Linting errors found")
            return False
            
        print("✅ All pre-commit tests passed")
        return True
```

### Automated Testing Pipeline
```python
class TestPipeline:
    """Automated testing pipeline for continuous integration."""
    
    def run_full_test_suite(self) -> Dict[str, Any]:
        """Run complete test suite with reporting."""
        
        results = {
            'start_time': datetime.now(),
            'stages': {}
        }
        
        # Stage 1: Unit Tests
        results['stages']['unit_tests'] = self._run_unit_tests()
        
        # Stage 2: Integration Tests (if unit tests pass)
        if results['stages']['unit_tests']['success']:
            results['stages']['integration_tests'] = self._run_integration_tests()
        
        # Stage 3: Paper Trading Validation
        if all(stage['success'] for stage in results['stages'].values()):
            results['stages']['paper_trading'] = self._run_paper_trading_tests()
            
        results['end_time'] = datetime.now()
        results['total_duration'] = (results['end_time'] - results['start_time']).total_seconds()
        
        # Generate comprehensive report
        report_path = TestReportGenerator().generate_test_report(results)
        results['report_path'] = report_path
        
        return results
```

## Testing Best Practices Summary

### Critical Testing Rules
1. **Never test with live trading accounts** - Always use paper trading
2. **Test financial calculations with known values** - Use theoretical option prices
3. **Mock external dependencies** - Don't rely on market data availability
4. **Test error conditions extensively** - Financial systems must be robust
5. **Validate risk management** - Ensure stop-losses and limits work
6. **Test with realistic data** - Use proper market data patterns
7. **Performance test critical paths** - Ensure low latency for trading operations

### Test Coverage Requirements
- **Unit Tests**: Minimum 85% code coverage
- **Integration Tests**: All external API interactions
- **Paper Trading**: All strategies before live deployment
- **Error Handling**: All exception paths
- **Performance**: All time-critical operations
- **Risk Management**: All risk control mechanisms

### Testing Frequency
- **Unit Tests**: Every commit
- **Integration Tests**: Daily
- **Paper Trading Validation**: Before any live deployment
- **Full System Tests**: Weekly
- **Performance Benchmarking**: Monthly
- **Stress Testing**: Quarterly

---

Following these testing standards ensures the Tradov trading system maintains the highest levels of reliability and safety, protecting against financial losses due to software defects while enabling confident deployment of new features and strategies.
```

## 10. Standards/Python/Type-Hints.md

```markdown
# Type Hints Standards for Tradov Trading System

## Overview

Type hints are mandatory throughout the Tradov trading system to ensure code reliability, enable better IDE support, and catch potential errors before they can cause financial losses. This document defines comprehensive type annotation standards for all Python code.

## Basic Type Annotations

### Primitive Types
```python
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from decimal import Decimal
from datetime import datetime, date, timedelta

# Basic types
account_balance: float = 100000.0
position_count: int = 5
is_market_open: bool = True
symbol: str = "SPY"

# Use Decimal for precise financial calculations
precise_price: Decimal = Decimal('450.25')
commission_rate: Decimal = Decimal('0.65')

# Date and time types
trade_timestamp: datetime = datetime.now()
expiry_date: date = date(2025, 2, 21)
hold_period: timedelta = timedelta(days=30)
```

### Collection Types
```python
from typing import Dict, List, Tuple, Set, Optional

# Lists with specific element types
stock_symbols: List[str] = ["SPY", "QQQ", "IWM"]
price_history: List[float] = [450.0, 451.25, 449.75]
trade_quantities: List[int] = [100, 200, 150]

# Dictionaries with specific key/value types
position_sizes: Dict[str, int] = {"SPY": 100, "QQQ": 50}
option_greeks: Dict[str, float] = {
    "delta": 0.45,
    "gamma": 0.012,
    "theta": -0.08
}

# Complex nested structures
portfolio_positions: Dict[str, List[Dict[str, Any]]] = {
    "SPY": [
        {"strike": 450.0, "expiry": "2025-02-21", "quantity": 10},
        {"strike": 455.0, "expiry": "2025-02-21", "quantity": -5}
    ]
}

# Tuples for fixed-length sequences
price_range: Tuple[float, float] = (445.0, 455.0)
option_specification: Tuple[str, float, datetime, str] = (
    "SPY", 450.0, datetime(2025, 2, 21), "CALL"
)

# Sets for unique collections
active_symbols: Set[str] = {"SPY", "QQQ", "IWM"}
```

## Function Type Annotations

### Basic Function Annotations
```python
def calculate_option_delta(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = 0.02
) -> float:
    """Calculate option delta using Black-Scholes model."""
    # Implementation here
    return calculated_delta

def validate_trade_parameters(
    symbol: str,
    quantity: int,
    order_type: str,
    limit_price: Optional[float] = None
) -> bool:
    """Validate trade parameters before order submission."""
    # Implementation here
    return is_valid
```

### Functions with Complex Return Types
```python
def analyze_option_chain(
    symbol: str,
    expiry_date: datetime
) -> Dict[str, Dict[float, Dict[str, float]]]:
    """
    Analyze option chain and return structured data.
    
    Returns:
        Dictionary with structure:
        {
            'calls': {strike: {'bid': float, 'ask': float, 'iv': float}},
            'puts': {strike: {'bid': float, 'ask': float, 'iv': float}}
        }
    """
    return {
        'calls': {450.0: {'bid': 2.5, 'ask': 2.7, 'iv': 0.18}},
        'puts': {450.0: {'bid': 3.1, 'ask': 3.3, 'iv': 0.19}}
    }

def get_portfolio_performance(
    start_date: datetime,
    end_date: datetime
) -> Tuple[float, float, Dict[str, float]]:
    """
    Calculate portfolio performance metrics.
    
    Returns:
        Tuple of (total_return, sharpe_ratio, detailed_metrics)
    """
    total_return = 0.15
    sharpe_ratio = 1.45
    detailed_metrics = {
        'max_drawdown': 0.08,
        'win_rate': 0.72,
        'profit_factor': 1.85
    }
    return total_return, sharpe_ratio, detailed_metrics
```

### Functions with Union Types
```python
from typing import Union

def process_order_response(
    response: Union[str, Dict[str, Any], None]
) -> Optional[str]:
    """
    Process different types of order responses.
    
    Args:
        response: Can be error string, success dict, or None for timeout
        
    Returns:
        Order ID if successful, None otherwise
    """
    if isinstance(response, dict):
        return response.get('order_id')
    elif isinstance(response, str):
        # Handle error message
        return None
    else:
        # Handle None/timeout case
        return None

def parse_market_data(
    data: Union[bytes, str, Dict[str, Any]]
) -> Optional[Dict[str, float]]:
    """Parse market data from various input formats."""
    if isinstance(data, bytes):
        # Parse binary data
        pass
    elif isinstance(data, str):
        # Parse JSON string
        pass
    elif isinstance(data, dict):
        # Already parsed
        pass
    return parsed_data
```

## Class Type Annotations

### Class Attributes and Methods
```python
from typing import ClassVar, Optional, Dict, List
from dataclasses import dataclass
from decimal import Decimal

class TradingStrategy:
    """Base class for all trading strategies."""
    
    # Class variables
    DEFAULT_MAX_POSITIONS: ClassVar[int] = 10
    DEFAULT_RISK_PER_TRADE: ClassVar[float] = 0.02
    
    def __init__(self, name: str, initial_capital: Decimal) -> None:
        """Initialize trading strategy."""
        # Instance attributes with type annotations
        self.name: str = name
        self.initial_capital: Decimal = initial_capital
        self.current_positions: Dict[str, int] = {}
        self.trade_history: List[Dict[str, Any]] = []
        self.is_active: bool = False
        self.performance_metrics: Optional[Dict[str, float]] = None
        
    def add_position(
        self, 
        symbol: str, 
        quantity: int, 
        entry_price: Decimal
    ) -> bool:
        """Add new position to strategy."""
        # Implementation here
        return True
        
    def calculate_portfolio_value(self) -> Decimal:
        """Calculate current portfolio value."""
        # Implementation here
        return Decimal('0')
        
    def get_performance_metrics(self) -> Dict[str, float]:
        """Calculate and return performance metrics."""
        if self.performance_metrics is None:
            self.performance_metrics = self._calculate_metrics()
        return self.performance_metrics
        
    def _calculate_metrics(self) -> Dict[str, float]:
        """Private method to calculate performance metrics."""
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
```

### Generic Classes
```python
from typing import TypeVar, Generic, List, Optional

T = TypeVar('T')

class DataBuffer(Generic[T]):
    """Generic buffer for storing typed data."""
    
    def __init__(self, max_size: int) -> None:
        self.max_size: int = max_size
        self.buffer: List[T] = []
        
    def add(self, item: T) -> None:
        """Add item to buffer."""
        if len(self.buffer) >= self.max_size:
            self.buffer.pop(0)  # Remove oldest
        self.buffer.append(item)
        
    def get_latest(self) -> Optional[T]:
        """Get most recent item."""
        return self.buffer[-1] if self.buffer else None
        
    def get_all(self) -> List[T]:
        """Get all items in buffer."""
        return self.buffer.copy()

# Usage with specific types
price_buffer: DataBuffer
