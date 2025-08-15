"""
Tests for the events module
"""

import pytest
import time

from ibautomater.events import IBEvent, EventData, StartResult, EventEmitter


class TestEventData:
    """Test cases for EventData"""
    
    def test_event_data_creation(self):
        """Test creating event data"""
        event_data = EventData(IBEvent.OUTPUT_DATA_RECEIVED, "test data")
        
        assert event_data.event_type == IBEvent.OUTPUT_DATA_RECEIVED
        assert event_data.data == "test data"
        assert isinstance(event_data.timestamp, float)
        assert event_data.timestamp > 0
    
    def test_event_data_with_timestamp(self):
        """Test creating event data with custom timestamp"""
        custom_timestamp = time.time()
        event_data = EventData(IBEvent.LOGIN_COMPLETED, None, custom_timestamp)
        
        assert event_data.timestamp == custom_timestamp


class TestStartResult:
    """Test cases for StartResult"""
    
    def test_successful_result(self):
        """Test successful start result"""
        result = StartResult(True, process_id=12345)
        
        assert result.success == True
        assert result.has_error == False
        assert result.process_id == 12345
        assert result.error_code is None
        assert result.error_message is None
    
    def test_failed_result(self):
        """Test failed start result"""
        result = StartResult(False, "START_FAILED", "Gateway not found")
        
        assert result.success == False
        assert result.has_error == True
        assert result.error_code == "START_FAILED"
        assert result.error_message == "Gateway not found"
        assert result.process_id is None


class TestEventEmitter:
    """Test cases for EventEmitter"""
    
    def setup_method(self):
        """Setup test environment"""
        self.emitter = EventEmitter()
        self.received_events = []
    
    def event_handler(self, event_data):
        """Test event handler"""
        self.received_events.append(event_data)
    
    def test_register_handler(self):
        """Test registering event handlers"""
        self.emitter.on(IBEvent.OUTPUT_DATA_RECEIVED, self.event_handler)
        
        # Emit an event
        self.emitter.emit(IBEvent.OUTPUT_DATA_RECEIVED, "test data")
        
        # Check that handler was called
        assert len(self.received_events) == 1
        assert self.received_events[0].event_type == IBEvent.OUTPUT_DATA_RECEIVED
        assert self.received_events[0].data == "test data"
    
    def test_multiple_handlers(self):
        """Test multiple handlers for same event"""
        received_events_2 = []
        
        def handler2(event_data):
            received_events_2.append(event_data)
        
        # Register two handlers
        self.emitter.on(IBEvent.LOGIN_COMPLETED, self.event_handler)
        self.emitter.on(IBEvent.LOGIN_COMPLETED, handler2)
        
        # Emit event
        self.emitter.emit(IBEvent.LOGIN_COMPLETED, "login success")
        
        # Both handlers should be called
        assert len(self.received_events) == 1
        assert len(received_events_2) == 1
    
    def test_unregister_handler(self):
        """Test unregistering event handlers"""
        self.emitter.on(IBEvent.ERROR_DATA_RECEIVED, self.event_handler)
        
        # Emit event - should be received
        self.emitter.emit(IBEvent.ERROR_DATA_RECEIVED, "error")
        assert len(self.received_events) == 1
        
        # Unregister handler
        self.emitter.off(IBEvent.ERROR_DATA_RECEIVED, self.event_handler)
        
        # Emit event again - should not be received
        self.emitter.emit(IBEvent.ERROR_DATA_RECEIVED, "error2")
        assert len(self.received_events) == 1  # Still only 1
    
    def test_emit_without_handlers(self):
        """Test emitting events without registered handlers"""
        # Should not raise an exception
        self.emitter.emit(IBEvent.EXITED, "exit code")
        
        # No events should be received
        assert len(self.received_events) == 0
    
    def test_handler_exception(self):
        """Test that handler exceptions don't break other handlers"""
        def failing_handler(event_data):
            raise Exception("Handler failed")
        
        # Register both a failing and working handler
        self.emitter.on(IBEvent.RESTARTED, failing_handler)
        self.emitter.on(IBEvent.RESTARTED, self.event_handler)
        
        # Emit event - working handler should still be called
        self.emitter.emit(IBEvent.RESTARTED, "restart data")
        
        # Working handler should have received the event
        assert len(self.received_events) == 1
    
    def test_clear_handlers(self):
        """Test clearing event handlers"""
        self.emitter.on(IBEvent.OUTPUT_DATA_RECEIVED, self.event_handler)
        self.emitter.on(IBEvent.ERROR_DATA_RECEIVED, self.event_handler)
        
        # Clear specific event handlers
        self.emitter.clear(IBEvent.OUTPUT_DATA_RECEIVED)
        
        # Emit events
        self.emitter.emit(IBEvent.OUTPUT_DATA_RECEIVED, "output")
        self.emitter.emit(IBEvent.ERROR_DATA_RECEIVED, "error")
        
        # Only error event should be received
        assert len(self.received_events) == 1
        assert self.received_events[0].event_type == IBEvent.ERROR_DATA_RECEIVED
    
    def test_clear_all_handlers(self):
        """Test clearing all event handlers"""
        self.emitter.on(IBEvent.OUTPUT_DATA_RECEIVED, self.event_handler)
        self.emitter.on(IBEvent.ERROR_DATA_RECEIVED, self.event_handler)
        
        # Clear all handlers
        self.emitter.clear()
        
        # Emit events - none should be received
        self.emitter.emit(IBEvent.OUTPUT_DATA_RECEIVED, "output")
        self.emitter.emit(IBEvent.ERROR_DATA_RECEIVED, "error")
        
        assert len(self.received_events) == 0

