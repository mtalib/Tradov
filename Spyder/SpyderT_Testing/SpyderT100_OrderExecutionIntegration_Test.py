#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT100_OrderExecutionIntegration_Test.py
Purpose: End-to-end integration test for order-to-execution flow

Author: Spyder Development Team
Year Created: 2026
Last Updated: 2026-03-17 Time: 00:00:00

Test Coverage:
    - Order submission → Risk check → Broker → Fill → Position update
    - Live trading confirmation workflow
    - Safety check integration
    - Position tracking synchronization
    - Trade journal integration
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import tempfile
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager
from Spyder.SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager
from Spyder.SpyderH_Storage.SpyderH08_TradeJournal import TradeJournal, TradeJournalEntry, TradeOutcome, SignalQuality
from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig, TradingMode, ExecutionState
from Spyder.SpyderT_Testing.SpyderT01_UnitTestFramework import SpyderTestBase


# ==============================================================================
# TEST CLASS
# ==============================================================================
class TestOrderExecutionIntegration(SpyderTestBase):
    """Integration tests for complete order execution flow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        
        # Create mock broker interface
        self.mock_broker = MagicMock()
        self.mock_broker.get_account_info.return_value = {
            'buying_power': 50000,
            'net_liquidation': 100000
        }
        self.mock_broker.get_positions.return_value = {}
        self.mock_broker.heartbeat.return_value = True
        
        # Create mock risk manager
        self.mock_risk_manager = MagicMock()
        self.mock_risk_manager.check_daily_limits.return_value = True
        
        # Create configuration
        self.config = LiveTradingConfig(
            account_id="TEST_ACCOUNT",
            max_daily_trades=100,
            max_position_size=1000,
            max_daily_loss=5000.0,
            require_confirmation=True
        )
        
        # Create trade journal with temp file (each sqlite3.connect(':memory:') creates a separate DB)
        self._journal_fd, self._journal_path = tempfile.mkstemp(suffix='.db')
        os.close(self._journal_fd)
        self.journal = TradeJournal(db_path=self._journal_path)
        
    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, '_journal_path') and os.path.exists(self._journal_path):
            os.unlink(self._journal_path)
        super().teardown_method()
    
    def _create_active_engine(self):
        """Create a LiveEngine with mocked initialization in TRADING state."""
        engine = LiveEngine(
            broker_interface=self.mock_broker,
            risk_manager=self.mock_risk_manager,
            config=self.config
        )
        # Bypass broker verification and set engine to trading state
        engine.state = ExecutionState.TRADING
        engine.broker_connected = True
        return engine
    
    def test_complete_order_flow_with_confirmation(self):
        """Test complete order flow with live trading confirmation."""
        engine = self._create_active_engine()
        
        # Create test order
        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }
        
        # Mock safety checks to pass
        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult
            
            mock_safety.return_value = SafetyCheck(
                check_name="test_check",
                result=SafetyCheckResult.PASSED,
                message="All checks passed",
                timestamp=datetime.now()
            )
            
            # Test without confirmation (should be rejected)
            with patch.object(engine, '_request_order_confirmation') as mock_confirm:
                mock_confirm.return_value = False  # Production code checks: if not confirmed
                
                result = engine.execute_order(test_order)
                
                assert result['status'] == 'rejected'
                assert 'confirmation' in result['reason'].lower()
                assert result.get('confirmation_declined') is True
            
            # Test with confirmation (should proceed)
            with patch.object(engine, '_request_order_confirmation') as mock_confirm:
                mock_confirm.return_value = True  # Confirmed
                
                # Mock order execution and metrics update
                with patch.object(engine, '_wait_for_execution') as mock_wait, \
                     patch.object(engine, '_update_execution_metrics'):
                    mock_wait.return_value = {
                        'status': 'filled',
                        'fill_price': 2.45,
                        'fill_quantity': 10
                    }
                    
                    result = engine.execute_order(test_order)
                    
                    # Should be filled
                    assert result['status'] == 'filled'
                    assert result['fill_price'] == 2.45
        
        # Clean up
        engine.stop_trading()
        engine.cleanup()
    
    def test_order_rejection_by_risk_manager(self):
        """Test that risk manager can reject orders."""
        engine = self._create_active_engine()
        
        test_order = {
            'symbol': 'SPY 420C 2026-03-21',
            'side': 'BUY',
            'quantity': 10,
            'type': 'LIMIT',
            'price': 2.50
        }
        
        # Mock safety check failure
        with patch.object(engine, '_perform_order_safety_checks') as mock_safety:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import SafetyCheck, SafetyCheckResult
            
            mock_safety.return_value = SafetyCheck(
                check_name="daily_loss_limit",
                result=SafetyCheckResult.FAILED,
                message="Daily loss limit exceeded",
                timestamp=datetime.now()
            )
            
            result = engine.execute_order(test_order)
            
            assert result['status'] == 'rejected'
            assert 'daily loss limit' in result['reason'].lower()
        
        engine.stop_trading()
        engine.cleanup()
    
    def test_position_tracker_integration(self):
        """Test that position tracker initializes and tracks positions."""
        # Create position tracker with mock spyder_client
        tracker = PositionTracker(spyder_client=MagicMock(), update_interval=0.1)
        
        # Verify construction
        assert tracker.update_interval == 0.1
        assert tracker._running is False
        assert tracker._position_lock is not None
        
        # Verify callback registration works
        callback = MagicMock()
        tracker.add_position_callback(callback)
        assert callback in tracker._position_callbacks
        
        # Verify callback removal works
        tracker.remove_position_callback(callback)
        assert callback not in tracker._position_callbacks
    
    def test_trade_journal_integration(self):
        """Test that trades are properly journaled."""
        # Create journal entry
        entry = TradeJournalEntry(
            entry_id="TEST_001",
            order_id="ORD_001",
            timestamp=datetime.now(),
            symbol="SPY 420C 2026-03-21",
            strategy_name="TestStrategy",
            signal_source="TEST_SIGNAL",
            signal_strength=0.85,
            signal_quality=SignalQuality.STRONG,
            entry_reason="Test trade",
            market_regime="NEUTRAL",
            volatility_regime="NORMAL",
            risk_check_result="PASSED",
            position_size=10,
            intended_size=10,
            entry_price=2.50,
            confidence_level=0.85
        )
        
        # Add to journal
        assert self.journal.add_entry(entry) is True
        
        # Retrieve entry
        retrieved = self.journal.get_entry("TEST_001")
        assert retrieved is not None
        assert retrieved.order_id == "ORD_001"
        assert retrieved.symbol == "SPY 420C 2026-03-21"
        
        # Update outcome
        assert self.journal.update_outcome(
            entry_id="TEST_001",
            outcome=TradeOutcome.WIN,
            exit_price=1.25,
            realized_pnl=1250.0,
            exit_reason="Test outcome"
        ) is True
        
        # Verify statistics
        stats = self.journal.get_statistics()
        assert stats['total_trades'] == 1
        assert stats['wins'] == 1
        assert stats['win_rate'] == 100.0
    
    def test_paper_mode_no_confirmation_required(self):
        """Test that paper trading mode doesn't require confirmation."""
        # Create paper trading config
        paper_config = LiveTradingConfig(
            account_id="PAPER_ACCOUNT",
            require_confirmation=False  # No confirmation in paper mode
        )
        
        engine = LiveEngine(
            broker_interface=self.mock_broker,
            risk_manager=self.mock_risk_manager,
            config=paper_config
        )
        
        engine.mode = TradingMode.PAPER
        engine.initialize()
        engine.start_trading()
        
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
                check_name="test",
                result=SafetyCheckResult.PASSED,
                message="OK",
                timestamp=datetime.now()
            )
            
            with patch.object(engine, '_wait_for_execution') as mock_wait:
                mock_wait.return_value = {'status': 'filled', 'fill_price': 2.45}
                
                # Should execute without confirmation prompt
                result = engine.execute_order(test_order)
                
                # Confirmation should not be called in paper mode
                assert 'confirmation_declined' not in result
        
        engine.stop_trading()
        engine.cleanup()


# ==============================================================================
# RUN TESTS
# ==============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
