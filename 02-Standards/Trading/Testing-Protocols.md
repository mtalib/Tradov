15. Standards/Trading/Testing-Protocols.md

```markdown
# Trading Testing Protocols for Spyder Trading System

## Overview

This document establishes comprehensive testing protocols for all trading-related functionality in the Spyder system. Given the financial nature of the system, rigorous testing is essential to prevent monetary losses and ensure reliable operation in live markets.

## Testing Hierarchy

### 1. Unit Testing Protocol

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any, List

class TestTradingStrategy:
    """Unit test suite for trading strategy components."""
    
    @pytest.fixture
    def mock_market_data(self):
        """Provide realistic mock market data."""
        return {
            'symbol': 'SPY',
            'underlying_price': 450.25,
            'timestamp': datetime.now(),
            'implied_volatility': 0.22,
            'historical_volatility': 0.18,
            'option_chain': self._create_mock_option_chain(),
            'volume': 1000000,
            'bid': 450.20,
            'ask': 450.30
        }
    
    @pytest.fixture
    def strategy_config(self):
        """Standard strategy configuration for testing."""
        return {
            'max_position_size': 10,
            'risk_per_trade': 0.02,
            'profit_target': 0.25,
            'stop_loss': 2.0,
            'max_dte': 45,
            'min_dte': 7
        }
    
    def test_signal_generation_valid_conditions(self, mock_market_data, strategy_config):
        """Test signal generation under valid market conditions."""
        # Arrange
        strategy = IronCondorStrategy("test_ic", strategy_config)
        
        # Act
        signals = strategy.generate_signals(mock_market_data)
        
        # Assert
        assert isinstance(signals, list)
        if signals:  # If signals generated
            signal = signals[0]
            assert hasattr(signal, 'strategy_name')
            assert hasattr(signal, 'confidence')
            assert hasattr(signal, 'strength')
            assert 0 <= signal.confidence <= 1
            assert 0 <= signal.strength <= 1
    
    def test_position_sizing_risk_compliance(self, strategy_config):
        """Test position sizing respects risk management rules."""
        # Arrange
        strategy = IronCondorStrategy("test_ic", strategy_config)
        mock_signal = self._create_mock_signal()
        
        # Act
        position_size = strategy.calculate_position_size(mock_signal)
        
        # Assert
        assert position_size > 0
        assert position_size <= strategy_config['max_position_size']
        
        # Calculate risk and verify it's within limits
        max_risk = mock_signal.metadata.get('max_risk', 0)
        total_risk = max_risk * position_size * 100  # Options multiplier
        max_allowed_risk = 100000 * strategy_config['risk_per_trade']  # Assuming $100k capital
        
        assert total_risk <= max_allowed_risk
    
    def test_signal_validation_rejects_invalid_signals(self):
        """Test signal validation properly rejects invalid signals."""
        # Arrange
        strategy = IronCondorStrategy("test_ic", {})
        invalid_signal = TradingSignal(
            strategy_name="test",
            symbol="SPY",
            action="INVALID_ACTION",
            signal_type="IRON_CONDOR",
            strength=1.5,  # Invalid: > 1.0
            confidence=-0.1,  # Invalid: < 0.0
            target_price=None,
            stop_loss=None,
            position_size=0,  # Invalid: must be > 0
            expiry=None,
            metadata={}  # Missing required fields
        )
        
        # Act & Assert
        assert not strategy.validate_signal(invalid_signal)
    
    def test_risk_calculations_accuracy(self):
        """Test risk calculation accuracy with known values."""
        # Test with known option pricing values
        strike_width = Decimal('5.0')
        credit_received = Decimal('1.25')
        expected_max_risk = strike_width - credit_received
        
        calculated_risk = self._calculate_iron_condor_risk(strike_width, credit_received)
        
        assert abs(calculated_risk - expected_max_risk) < Decimal('0.01')
    
    def test_greeks_calculations_theoretical_values(self):
        """Test Greeks calculations against theoretical values."""
        # Test with Black-Scholes theoretical values
        test_params = {
            'spot': 100.0,
            'strike': 100.0,  # ATM
            'time_to_expiry': 0.25,  # 3 months
            'volatility': 0.20,
            'risk_free_rate': 0.02
        }
        
        greeks = calculate_option_greeks(**test_params)
        
        # ATM call delta should be around 0.5
        assert 0.45 < greeks['delta'] < 0.55
        
        # Gamma should be positive and significant for ATM
        assert greeks['gamma'] > 0.01
        
        # Theta should be negative (time decay)
        assert greeks['theta'] < 0
        
        # Vega should be positive and significant for ATM
        assert greeks['vega'] > 5.0
    
    @pytest.mark.parametrize("market_condition,expected_result", [
        ("high_volatility", True),
        ("low_volatility", False),
        ("trending_market", False),
        ("sideways_market", True)
    ])
    def test_market_condition_responses(self, market_condition, expected_result):
        """Test strategy responds appropriately to different market conditions."""
        # Arrange
        strategy = IronCondorStrategy("test_ic", {})
        market_data = self._create_market_data_for_condition(market_condition)
        
        # Act
        should_trade = strategy._are_conditions_favorable(market_data)
        
        # Assert
        assert should_trade == expected_result
    
    def _create_mock_option_chain(self) -> Dict[str, Any]:
        """Create realistic mock option chain data."""
        return {
            'underlying': 'SPY',
            'underlying_price': 450.25,
            'expiry': '20250221',
            'calls': {
                445.0: {'bid': 8.1, 'ask': 8.3, 'iv': 0.18, 'delta': 0.65},
                450.0: {'bid': 5.2, 'ask': 5.4, 'iv': 0.19, 'delta': 0.52},
                455.0: {'bid': 3.1, 'ask': 3.3, 'iv': 0.20, 'delta': 0.38},
                460.0: {'bid': 1.8, 'ask': 2.0, 'iv': 0.21, 'delta': 0.25}
            },
            'puts': {
                440.0: {'bid': 1.5, 'ask': 1.7, 'iv': 0.19, 'delta': -0.22},
                445.0: {'bid': 2.8, 'ask': 3.0, 'iv': 0.18, 'delta': -0.35},
                450.0: {'bid': 4.9, 'ask': 5.1, 'iv': 0.19, 'delta': -0.48},
                455.0: {'bid': 7.8, 'ask': 8.0, 'iv': 0.20, 'delta': -0.62}
            }
        }
```

### 2. Integration Testing Protocol

```python
class TestBrokerIntegration:
    """Integration tests for broker connectivity and operations."""
    
    @pytest.mark.integration
    @pytest.mark.requires_paper_account
    def test_connection_establishment(self):
        """Test successful connection to IBKR paper trading."""
        # Arrange
        config = IBKRConnectionConfig(
            host='127.0.0.1',
            port=4002,  # Paper trading port
            client_id=999,  # Test client ID
            timeout=30
        )
        connection_manager = IBKRConnectionManager(config)
        
        # Act
        connection_result = connection_manager.connect()
        
        # Assert
        assert connection_result is True
        assert connection_manager.is_connected()
        
        # Verify we can get account info
        status = connection_manager.get_connection_status()
        assert status['connected'] is True
        assert status['client_id'] == 999
        
        # Cleanup
        connection_manager.disconnect()
    
    @pytest.mark.integration
    def test_market_data_subscription_flow(self):
        """Test complete market data subscription workflow."""
        # Arrange
        connection_manager = self._get_test_connection()
        data_manager = IBKRMarketDataManager(connection_manager)
        received_data = []
        
        def data_callback(data):
            received_data.append(data)
        
        # Act
        subscription_success = data_manager.subscribe_ticker('SPY', data_callback)
        
        # Assert initial subscription
        assert subscription_success is True
        
        # Wait for data (up to 10 seconds)
        timeout = time.time() + 10
        while len(received_data) == 0 and time.time() < timeout:
            time.sleep(0.1)
        
        # Verify data received
        assert len(received_data) > 0
        
        latest_data = received_data[-1]
        assert latest_data['symbol'] == 'SPY'
        assert 'bid' in latest_data
        assert 'ask' in latest_data
        assert latest_data['bid'] > 0
        assert latest_data['ask'] > latest_data['bid']
        
        # Test unsubscription
        unsubscribe_success = data_manager.unsubscribe('SPY')
        assert unsubscribe_success is True
    
    @pytest.mark.integration
    @pytest.mark.paper_only
    def test_order_submission_lifecycle(self):
        """Test complete order lifecycle in paper trading."""
        # Arrange
        connection_manager = self._get_test_connection()
        order_manager = IBKROrderManager(connection_manager)
        
        test_order = IBKROrder(
            symbol='SPY',
            action='BUY',
            quantity=1,
            order_type='LMT',
            limit_price=Decimal('400.00'),  # Well below market for testing
            time_in_force='DAY'
        )
        
        # Act - Submit Order
        order_id = order_manager.submit_order(test_order)
        
        # Assert order submission
        assert order_id is not None
        assert order_id in order_manager.pending_orders
        
        # Wait for order acknowledgment
        time.sleep(2)
        
        # Test order modification
        modifications = {'limit_price': Decimal('401.00')}
        modify_success = order_manager.modify_order(order_id, modifications)
        assert modify_success is True
        
        # Test order cancellation
        cancel_success = order_manager.cancel_order(order_id)
        assert cancel_success is True
        
        # Verify order history recorded
        history = order_manager.order_history
        order_events = [event for event in history if event['order_id'] == order_id]
        
        assert len(order_events) >= 3  # Submit, modify, cancel
        event_types = [event['event_type'] for event in order_events]
        assert 'SUBMITTED' in event_types
        assert 'MODIFIED' in event_types
        assert 'CANCEL_REQUESTED' in event_types
    
    @pytest.mark.integration
    def test_options_data_accuracy(self):
        """Test options data accuracy and completeness."""
        # Arrange
        connection_manager = self._get_test_connection()
        data_manager = IBKRMarketDataManager(connection_manager)
        option_data = []
        
        def option_callback(data):
            option_data.append(data)
        
        # Get next monthly expiry
        next_expiry = self._get_next_monthly_expiry()
        
        # Act
        subscription_success = data_manager.subscribe_option_chain(
            'SPY', 
            next_expiry, 
            option_callback
        )
        
        # Assert subscription success
        assert subscription_success is True
        
        # Wait for option data
        timeout = time.time() + 30  # Options data can take longer
        while len(option_data) < 10 and time.time() < timeout:
            time.sleep(0.5)
        
        # Verify option data quality
        assert len(option_data) >= 10  # Should receive multiple option quotes
        
        for data_point in option_data[:5]:  # Check first 5 data points
            assert data_point['symbol'] == 'SPY'
            assert data_point['expiry'] == next_expiry
            assert data_point['right'] in ['C', 'P']
            assert data_point['strike'] > 0
            
            # Verify Greeks are present (may be None initially)
            assert 'delta' in data_point
            assert 'gamma' in data_point
            assert 'theta' in data_point
            assert 'vega' in data_point
    
    def _get_test_connection(self) -> IBKRConnectionManager:
        """Get test connection manager."""
        config = IBKRConnectionConfig(
            host=os.getenv('IBKR_HOST', '127.0.0.1'),
            port=int(os.getenv('IBKR_PAPER_PORT', '4002')),
            client_id=999,
            timeout=30
        )
        
        connection_manager = IBKRConnectionManager(config)
        if not connection_manager.connect():
            pytest.skip("Cannot establish IBKR connection for integration test")
        
        return connection_manager
```

### 3. Paper Trading Validation Protocol

```python
class PaperTradingValidator:
    """Comprehensive paper trading validation framework."""
    
    def __init__(self):
        self.validation_config = {
            'min_validation_period_days': 7,
            'min_trades_required': 5,
            'max_acceptable_drawdown': 0.05,
            'min_win_rate': 0.40,
            'max_consecutive_losses': 5,
            'required_market_conditions': ['normal', 'volatile', 'trending']
        }
        
        self.logger = SpyderLogger.get_logger("PaperValidator")
    
    @pytest.mark.paper_trading
    @pytest.mark.slow
    def test_strategy_paper_trading_validation(self, strategy_name: str):
        """Run comprehensive paper trading validation for strategy."""
        
        # Ensure we're in paper trading mode
        original_mode = os.environ.get('TRADING_MODE', 'PAPER')
        os.environ['TRADING_MODE'] = 'PAPER'
        
        try:
            # Initialize strategy for paper trading
            strategy = self._initialize_strategy_for_paper_trading(strategy_name)
            
            # Run validation
            validation_results = self._run_paper_trading_cycle(strategy)
            
            # Validate results
            self._assert_paper_trading_results(validation_results)
            
        finally:
            # Restore original trading mode
            os.environ['TRADING_MODE'] = original_mode
    
    def _run_paper_trading_cycle(self, strategy) -> Dict[str, Any]:
        """Run complete paper trading validation cycle."""
        
        start_time = datetime.now()
        end_time = start_time + timedelta(days=self.validation_config['min_validation_period_days'])
        
        results = {
            'start_time': start_time,
            'end_time': end_time,
            'trades': [],
            'daily_pnl': [],
            'max_drawdown': 0.0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'consecutive_losses': 0,
            'max_consecutive_losses': 0,
            'risk_violations': [],
            'market_conditions_tested': set()
        }
        
        # Start strategy
        if not strategy.start():
            raise RuntimeError("Failed to start strategy for paper trading")
        
        try:
            # Run strategy for validation period
            current_time = start_time
            daily_capital = 100000.0  # Starting capital
            peak_capital = daily_capital
            consecutive_losses = 0
            
            while current_time < end_time:
                # Simulate daily trading
                daily_result = self._simulate_daily_trading(strategy, current_time)
                
                if daily_result:
                    results['trades'].extend(daily_result['trades'])
                    
                    # Update daily P&L
                    daily_pnl = sum(trade['pnl'] for trade in daily_result['trades'])
                    daily_capital += daily_pnl
                    results['daily_pnl'].append({
                        'date': current_time.date(),
                        'pnl': daily_pnl,
                        'capital': daily_capital
                    })
                    
                    # Update drawdown
                    if daily_capital > peak_capital:
                        peak_capital = daily_capital
                        consecutive_losses = 0
                    else:
                        if daily_pnl < 0:
                            consecutive_losses += 1
                    
                    current_drawdown = (peak_capital - daily_capital) / peak_capital
                    results['max_drawdown'] = max(results['max_drawdown'], current_drawdown)
                    results['max_consecutive_losses'] = max(results['max_consecutive_losses'], consecutive_losses)
                    
                    # Record market conditions tested
                    market_condition = self._classify_market_condition(current_time)
                    results['market_conditions_tested'].add(market_condition)
                    
                    # Check for risk violations
                    violations = self._check_risk_violations(daily_result['trades'])
                    results['risk_violations'].extend(violations)
                
                current_time += timedelta(days=1)
                
                # Skip weekends
                if current_time.weekday() >= 5:
                    current_time += timedelta(days=2)
        
        finally:
            strategy.stop()
        
        # Calculate final metrics
        results['total_pnl'] = daily_capital - 100000.0
        results['win_rate'] = self._calculate_win_rate(results['trades'])
        
        return results
    
    def _assert_paper_trading_results(self, results: Dict[str, Any]) -> None:
        """Assert paper trading results meet validation criteria."""
        
        config = self.validation_config
        
        # Check minimum trades requirement
        assert len(results['trades']) >= config['min_trades_required'], \
            f"Insufficient trades: {len(results['trades'])} < {config['min_trades_required']}"
        
        # Check drawdown limit
        assert results['max_drawdown'] <= config['max_acceptable_drawdown'], \
            f"Excessive drawdown: {results['max_drawdown']:.1%} > {config['max_acceptable_drawdown']:.1%}"
        
        # Check win rate
        assert results['win_rate'] >= config['min_win_rate'], \
            f"Low win rate: {results['win_rate']:.1%} < {config['min_win_rate']:.1%}"
        
        # Check consecutive losses
        assert results['max_consecutive_losses'] <= config['max_consecutive_losses'], \
            f"Too many consecutive losses: {results['max_consecutive_losses']}"
        
        # Check risk violations
        assert len(results['risk_violations']) == 0, \
            f"Risk violations detected: {results['risk_violations']}"
        
        # Check market conditions coverage
        tested_conditions = results['market_conditions_tested']
        required_conditions = set(config['required_market_conditions'])
        missing_conditions = required_conditions - tested_conditions
        
        assert len(missing_conditions) == 0, \
            f"Missing market conditions: {missing_conditions}"
        
        # Check overall profitability (allow small losses for learning)
        min_acceptable_pnl = -1000  # Allow $1000 loss maximum
        assert results['total_pnl'] >= min_acceptable_pnl, \
            f"Excessive losses: ${results['total_pnl']:.2f}"
    
    def _simulate_daily_trading(self, strategy, date: datetime) -> Optional[Dict[str, Any]]:
        """Simulate one day of trading for the strategy."""
        
        try:
            # Generate mock market data for the day
            market_data = self._generate_daily_market_data(date)
            
            # Generate signals
            signals = strategy.generate_signals(market_data)
            
            # Simulate trade execution
            trades = []
            for signal in signals:
                if strategy.validate_signal(signal):
                    trade_result = self._simulate_trade_execution(signal, market_data)
                    if trade_result:
                        trades.append(trade_result)
            
            return {'trades': trades, 'market_data': market_data}
            
        except Exception as e:
            self.logger.error(f"Daily simulation error for {date}: {e}")
            return None
    
    def _simulate_trade_execution(self, signal: TradingSignal, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Simulate execution of a single trade."""
        
        try:
            # Simulate entry
            entry_price = self._simulate_fill_price(signal.target_price, market_data)
            entry_time = market_data['timestamp']
            
            # Simulate holding period (simplified)
            holding_days = random.randint(1, 30)
            exit_time = entry_time + timedelta(days=holding_days)
            
            # Simulate exit price based on strategy logic
            exit_price = self._simulate_exit_price(signal, entry_price, holding_days)
            
            # Calculate P&L
            if signal.action == 'BUY':
                pnl = (exit_price - entry_price) * signal.position_size * 100
            else:  # SELL
                pnl = (entry_price - exit_price) * signal.position_size * 100
            
            # Subtract commission
            commission = self._calculate_commission(signal.position_size)
            net_pnl = pnl - commission
            
            return {
                'signal': signal,
                'entry_time': entry_time,
                'entry_price': entry_price,
                'exit_time': exit_time,
                'exit_price': exit_price,
                'gross_pnl': pnl,
                'commission': commission,
                'pnl': net_pnl,
                'holding_days': holding_days
            }
            
        except Exception as e:
            self.logger.error(f"Trade simulation error: {e}")
            return None
```

### 4. Live Trading Validation Protocol

```python
class LiveTradingValidator:
    """Validation protocol for live trading deployment."""
    
    VALIDATION_STAGES = [
        'pre_deployment_checks',
        'limited_capital_test',
        'single_strategy_validation', 
        'multi_strategy_coordination',
        'full_deployment_approval'
    ]
    
    def __init__(self):
        self.current_stage = None
        self.validation_results = {}
        self.logger = SpyderLogger.get_logger("LiveValidator")
    
    def validate_for_live_deployment(self, strategy_name: str) -> Dict[str, Any]:
        """Complete validation process for live trading deployment."""
        
        validation_report = {
            'strategy_name': strategy_name,
            'validation_date': datetime.now(),
            'stages_completed': [],
            'stages_passed': [],
            'stages_failed': [],
            'overall_result': 'PENDING',
            'recommendations': [],
            'deployment_approved': False
        }
        
        try:
            for stage in self.VALIDATION_STAGES:
                self.current_stage = stage
                self.logger.info(f"Running validation stage: {stage}")
                
                stage_result = self._run_validation_stage(stage, strategy_name)
                validation_report['stages_completed'].append(stage)
                
                if stage_result['passed']:
                    validation_report['stages_passed'].append(stage)
                    self.logger.info(f"Stage {stage} PASSED")
                else:
                    validation_report['stages_failed'].append(stage)
                    self.logger.error(f"Stage {stage} FAILED: {stage_result['reason']}")
                    validation_report['recommendations'].extend(stage_result.get('recommendations', []))
                    break  # Stop on first failure
            
            # Determine overall result
            all_stages_passed = len(validation_report['stages_passed']) == len(self.VALIDATION_STAGES)
            validation_report['deployment_approved'] = all_stages_passed
            validation_report['overall_result'] = 'APPROVED' if all_stages_passed else 'REJECTED'
            
        except Exception as e:
            validation_report['overall_result'] = 'ERROR'
            validation_report['error'] = str(e)
            self.logger.error(f"Validation error: {e}")
        
        return validation_report
    
    def _run_validation_stage(self, stage: str, strategy_name: str) -> Dict[str, Any]:
        """Run specific validation stage."""
        
        stage_methods = {
            'pre_deployment_checks': self._pre_deployment_checks,
            'limited_capital_test': self._limited_capital_test,
            'single_strategy_validation': self._single_strategy_validation,
            'multi_strategy_coordination': self._multi_strategy_coordination,
            'full_deployment_approval': self._full_deployment_approval
        }
        
        if stage not in stage_methods:
            return {'passed': False, 'reason': f'Unknown validation stage: {stage}'}
        
        return stage_methods[stage](strategy_name)
    
    def _pre_deployment_checks(self, strategy_name: str) -> Dict[str, Any]:
        """Pre-deployment system and strategy checks."""
        
        checks = {
            'code_review_completed': self._check_code_review_status(strategy_name),
            'unit_tests_passing': self._check_unit_test_results(strategy_name),
            'paper_trading_validated': self._check_paper_trading_results(strategy_name),
            'risk_limits_configured': self._check_risk_configuration(strategy_name),
            'monitoring_setup': self._check_monitoring_setup(strategy_name),
            'backup_procedures': self._check_backup_procedures(),
            'emergency_stops': self._check_emergency_procedures()
        }
        
        failed_checks = [check for check, passed in checks.items() if not passed]
        
        if failed_checks:
            return {
                'passed': False,
                'reason': f'Failed pre-deployment checks: {failed_checks}',
                'recommendations': [f'Complete {check}' for check in failed_checks]
            }
        
        return {'passed': True, 'reason': 'All pre-deployment checks passed'}
    
    def _limited_capital_test(self, strategy_name: str) -> Dict[str, Any]:
        """Test with limited capital allocation."""
        
        try:
            # Set strict capital limits for testing
            test_capital = 5000  # $5,000 maximum for testing
            original_limits = self._set_temporary_limits(strategy_name, test_capital)
            
            # Run strategy for limited time with small positions
            test_duration = timedelta(hours=4)  # 4 hours of live testing
            test_results = self._run_limited_live_test(strategy_name, test_duration)
            
            # Restore original limits
            self._restore_limits(strategy_name, original_limits)
            
            # Evaluate test results
            if test_results['max_loss'] > test_capital * 0.1:  # Max 10% loss
                return {
                    'passed': False,
                    'reason': f'Excessive loss in limited test: ${test_results["max_loss"]}'
                }
            
            if test_results['risk_violations'] > 0:
                return {
                    'passed': False,
                    'reason': f'Risk violations in limited test: {test_results["risk_violations"]}'
                }
            
            return {
                'passed': True,
                'reason': 'Limited capital test completed successfully',
                'test_results': test_results
            }
            
        except Exception as e:
            return {
                'passed': False,
                'reason': f'Limited capital test failed: {str(e)}'
            }
    
    def _check_code_review_status(self, strategy_name: str) -> bool:
        """Check if strategy has completed code review."""
        # Implementation would check code review system
        return True  # Placeholder
    
    def _check_unit_test_results(self, strategy_name: str) -> bool:
        """Check unit test results for strategy."""
        try:
            # Run unit tests for specific strategy
            result = pytest.main([
                f'SpyderT_Testing/test_{strategy_name}.py',
                '--tb=short',
                '-v'
            ])
            return result == 0  # 0 = all tests passed
        except Exception:
            return False
    
    def _check_paper_trading_results(self, strategy_name: str
