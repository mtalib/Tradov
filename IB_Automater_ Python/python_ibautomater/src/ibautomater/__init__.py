"""
Python IBAutomater - Interactive Brokers Gateway Automation Tool

A Python implementation of IBAutomater that provides comprehensive automation
for Interactive Brokers Gateway including startup, login, restart handling,
and 2FA support.
"""

# Import core components that don't require display
from .config import IBConfig, TradingMode
from .events import IBEvent, EventData, StartResult
from .exceptions import IBAutomaterError, ProcessError, AuthenticationError, UIError

__version__ = "1.0.0"
__author__ = "Python IBAutomater Team"

# IBAutomater is imported only when needed to avoid display dependency
# from .ibautomater import IBAutomater

__all__ = [
    "IBAutomater",
    "IBConfig", 
    "TradingMode",
    "IBEvent",
    "EventData",
    "StartResult",
    "IBAutomaterError",
    "ProcessError",
    "AuthenticationError", 
    "UIError",
]

