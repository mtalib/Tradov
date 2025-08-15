"""
Event system for IBAutomater
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class IBEvent(Enum):
    """Event types for IBAutomater"""
    OUTPUT_DATA_RECEIVED = "output_data_received"
    ERROR_DATA_RECEIVED = "error_data_received"
    EXITED = "exited"
    RESTARTED = "restarted"
    LOGIN_COMPLETED = "login_completed"
    TWO_FACTOR_REQUIRED = "two_factor_required"
    PROCESS_STARTED = "process_started"
    PROCESS_STOPPED = "process_stopped"
    UI_DIALOG_DETECTED = "ui_dialog_detected"


@dataclass
class EventData:
    """Event data container"""
    event_type: IBEvent
    data: Any
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class StartResult:
    """Result of a start operation"""
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    process_id: Optional[int] = None
    
    @property
    def has_error(self) -> bool:
        """Check if the result contains an error"""
        return not self.success


@dataclass
class ExitedEventArgs:
    """Arguments for the Exited event"""
    exit_code: int
    reason: str
    unexpected: bool = False


class EventEmitter:
    """Event emitter for IBAutomater events"""
    
    def __init__(self):
        self._handlers: Dict[IBEvent, List[Callable]] = {}
    
    def on(self, event_type: IBEvent, handler: Callable):
        """Register an event handler"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def off(self, event_type: IBEvent, handler: Callable):
        """Unregister an event handler"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def emit(self, event_type: IBEvent, data: Any = None):
        """Emit an event to all registered handlers"""
        if event_type in self._handlers:
            event_data = EventData(event_type, data)
            for handler in self._handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    # Log the error but don't let it stop other handlers
                    print(f"Error in event handler for {event_type}: {e}")
    
    def clear(self, event_type: Optional[IBEvent] = None):
        """Clear event handlers"""
        if event_type is None:
            self._handlers.clear()
        elif event_type in self._handlers:
            self._handlers[event_type].clear()

