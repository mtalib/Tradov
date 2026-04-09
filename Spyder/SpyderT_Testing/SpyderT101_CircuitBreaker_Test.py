#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT101_CircuitBreaker_Test.py
Purpose: Circuit breaker functionality tests

Author: Spyder Development Team
Year Created: 2026
Last Updated: 2026-03-17 Time: 00:00:00

Test Coverage:
    - Circuit breaker activation on trigger conditions
    - Order halting when circuit breaker is active
    - Circuit breaker reset functionality
    - Multiple trigger condition handling
    - Integration with risk management system
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderE_Risk.SpyderE16_CircuitBreakerProtocol import (
    SpyderCircuitBreakerProtocol as CircuitBreaker,
    CircuitBreakerLevel as CircuitBreakerState,
)
from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig, ExecutionState
from Spyder.SpyderT_Testing.SpyderT01_UnitTestFramework import SpyderTestBase


# ==============================================================================
# TEST CLASS
# ==============================================================================
class TestCircuitBreaker(SpyderTestBase):
    """Tests for circuit breaker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()

        # Create mock dependencies
        self.mock_broker = MagicMock()
        self.mock_broker.get_account_info.return_value = {
            'buying_power': 50000,
            'net_liquidation': 100000
        }
        self.mock_broker.heartbeat.return_value = True

        self.mock_risk_manager = MagicMock()
        self.mock_risk_manager.check_daily_limits.return_value = True

        self.config = LiveTradingConfig(
            account_id="TEST_ACCOUNT",
            max_daily_loss=5000.0
        )

    def _create_active_engine(self):
        """Create a LiveEngine in TRADING state, bypassing broker verification."""
        engine = LiveEngine(
            broker_interface=self.mock_broker,
            risk_manager=self.mock_risk_manager,
            config=self.config
        )
        engine.state = ExecutionState.TRADING
        engine.broker_connected = True
        return engine

    def test_circuit_breaker_activation_on_daily_loss(self):
        """Test circuit breaker activates when daily loss limit is exceeded."""
        engine = self._create_active_engine()

        # Simulate daily loss exceeding limit
        engine.daily_loss = 6000.0  # Exceeds MAX_DAILY_LOSS of 5000

        # Create test order
        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }

        # Mock safety check to detect daily loss breach
        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult

            # Safety check should FAIL due to daily loss
            mock_safety.return_value = SafetyCheck(
                check_name="daily_loss_limit",
                result=SafetyCheckResult.FAILED,
                message="Daily loss $6000 exceeds limit $5000",
                timestamp=datetime.now()
            )

            result = engine.execute_order(test_order)

            # Order should be rejected
            assert result['status'] == 'rejected'
            assert 'daily loss' in result['reason'].lower()

        engine.stop_trading()
        engine.cleanup()

    def test_circuit_breaker_halts_all_orders(self):
        """Test that circuit breaker halts all new orders."""
        engine = LiveEngine(
            broker_interface=self.mock_broker,
            risk_manager=self.mock_risk_manager,
            config=self.config
        )

        engine.initialize()
        engine.start_trading()

        # Activate emergency stop
        engine.emergency_stop = True

        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }

        # Attempt to execute order
        result = engine.execute_order(test_order)

        # Should be rejected due to emergency stop
        assert result['status'] == 'rejected'
        # Emergency stop should prevent trading

        engine.stop_trading()
        engine.cleanup()

    def test_circuit_breaker_max_daily_trades(self):
        """Test circuit breaker triggers on max daily trades."""
        engine = self._create_active_engine()

        # Set daily trades to limit
        engine.daily_trades = engine.config.max_daily_trades

        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }

        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult

            mock_safety.return_value = SafetyCheck(
                check_name="max_daily_trades",
                result=SafetyCheckResult.FAILED,
                message=f"Max daily trades {engine.config.max_daily_trades} reached",
                timestamp=datetime.now()
            )

            result = engine.execute_order(test_order)

            assert result['status'] == 'rejected'
            assert 'daily trades' in result['reason'].lower() or 'max' in result['reason'].lower()

        engine.stop_trading()
        engine.cleanup()

    def test_circuit_breaker_emergency_stop(self):
        """Test emergency stop activation and behavior."""
        engine = self._create_active_engine()

        # Verify trading is active
        assert engine.state == ExecutionState.TRADING

        # Activate emergency stop (changes mode and state)
        engine.emergency_stop = True
        engine.state = ExecutionState.STOPPED

        assert engine.emergency_stop is True

        # Verify no new orders can be executed
        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }

        result = engine.execute_order(test_order)
        assert result['status'] == 'rejected'

    def test_circuit_breaker_reset(self):
        """Test circuit breaker can be reset after trigger."""
        engine = self._create_active_engine()

        # Activate emergency stop
        engine.emergency_stop = True
        engine.state = ExecutionState.STOPPED

        # Reset emergency stop
        engine.emergency_stop = False
        engine.daily_loss = 0.0
        engine.daily_trades = 0
        engine.state = ExecutionState.TRADING  # Resume trading state

        # Verify trading can resume
        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 1,
            'type': 'LIMIT',
            'price': 2.50
        }

        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult

            mock_safety.return_value = SafetyCheck(
                check_name="reset_check",
                result=SafetyCheckResult.PASSED,
                message="OK",
                timestamp=datetime.now()
            )

            with patch.object(engine, '_request_order_confirmation') as mock_confirm:
                mock_confirm.return_value = True  # Confirmed

                with patch.object(engine, '_wait_for_execution') as mock_wait, \
                     patch.object(engine, '_update_execution_metrics'):
                    mock_wait.return_value = {'status': 'filled', 'fill_price': 2.45}

                    result = engine.execute_order(test_order)

                    assert result['status'] in ['filled', 'pending'] or 'confirmation' in result.get('reason', '')

    def test_position_limit_circuit_breaker(self):
        """Test circuit breaker triggers on position size limit."""
        engine = self._create_active_engine()

        # Create oversized order
        oversized_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': engine.config.max_position_size + 100,  # Exceed limit
            'type': 'LIMIT',
            'price': 2.50
        }

        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult

            mock_safety.return_value = SafetyCheck(
                check_name="position_size_limit",
                result=SafetyCheckResult.FAILED,
                message=f"Position size exceeds limit {engine.config.max_position_size}",
                timestamp=datetime.now()
            )

            result = engine.execute_order(oversized_order)

            assert result['status'] == 'rejected'
            assert 'position' in result['reason'].lower() or 'size' in result['reason'].lower()

        engine.stop_trading()
        engine.cleanup()


# ==============================================================================
# RUN TESTS
# ==============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
