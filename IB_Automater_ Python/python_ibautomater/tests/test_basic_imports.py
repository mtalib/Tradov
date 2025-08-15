"""
Basic import tests that don't require display environment
"""

import pytest


def test_config_import():
    """Test importing configuration module"""
    from ibautomater.config import IBConfig, TradingMode, Region
    
    # Test enum values
    assert TradingMode.PAPER.value == "paper"
    assert TradingMode.LIVE.value == "live"
    assert Region.US.value == "us"


def test_events_import():
    """Test importing events module"""
    from ibautomater.events import IBEvent, EventData, StartResult, EventEmitter
    
    # Test enum values
    assert IBEvent.OUTPUT_DATA_RECEIVED.value == "output_data_received"
    assert IBEvent.LOGIN_COMPLETED.value == "login_completed"


def test_exceptions_import():
    """Test importing exceptions module"""
    from ibautomater.exceptions import (
        IBAutomaterError,
        ProcessError,
        AuthenticationError,
        UIError,
        ConfigurationError,
        TimeoutError,
        TwoFactorError
    )
    
    # Test exception hierarchy
    assert issubclass(ProcessError, IBAutomaterError)
    assert issubclass(AuthenticationError, IBAutomaterError)
    assert issubclass(TwoFactorError, AuthenticationError)


def test_basic_config_creation():
    """Test basic configuration creation without validation"""
    import tempfile
    from ibautomater.config import IBConfig, TradingMode
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config = IBConfig(
            ib_directory=temp_dir,
            ib_version="10.19",
            username="testuser",
            password="testpass",
            trading_mode=TradingMode.PAPER,
            port=7497
        )
        
        assert config.username == "testuser"
        assert config.trading_mode == TradingMode.PAPER
        assert config.port == 7497


def test_start_result():
    """Test StartResult functionality"""
    from ibautomater.events import StartResult
    
    # Test successful result
    success_result = StartResult(True, process_id=12345)
    assert success_result.success == True
    assert success_result.has_error == False
    assert success_result.process_id == 12345
    
    # Test failed result
    fail_result = StartResult(False, "ERROR_CODE", "Error message")
    assert fail_result.success == False
    assert fail_result.has_error == True
    assert fail_result.error_code == "ERROR_CODE"
    assert fail_result.error_message == "Error message"


def test_event_emitter():
    """Test basic event emitter functionality"""
    from ibautomater.events import EventEmitter, IBEvent
    
    emitter = EventEmitter()
    received_events = []
    
    def handler(event_data):
        received_events.append(event_data)
    
    # Register handler and emit event
    emitter.on(IBEvent.OUTPUT_DATA_RECEIVED, handler)
    emitter.emit(IBEvent.OUTPUT_DATA_RECEIVED, "test data")
    
    # Verify event was received
    assert len(received_events) == 1
    assert received_events[0].event_type == IBEvent.OUTPUT_DATA_RECEIVED
    assert received_events[0].data == "test data"

