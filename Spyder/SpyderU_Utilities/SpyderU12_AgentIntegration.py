#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU12_AgentIntegration.py
Purpose: SPYDER - Autonomous Options Trading System v1.0

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Autonomous Options Trading System v1.0

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from enum import Enum

class AgentStatus(Enum):
    """Agent status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"

from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class AgentMetrics:
    """Agent metrics data class"""
    agent_id: str = "unknown"
    status: AgentStatus = AgentStatus.UNKNOWN
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime_seconds: int = 0
    requests_processed: int = 0
    errors_count: int = 0
    last_activity: datetime | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "uptime_seconds": self.uptime_seconds,
            "requests_processed": self.requests_processed,
            "errors_count": self.errors_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "metadata": self.metadata
        }
