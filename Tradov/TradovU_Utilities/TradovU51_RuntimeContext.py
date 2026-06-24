#!/usr/bin/env python3
"""Immutable runtime context shared across trading components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TradingMode = Literal["paper", "live"]


@dataclass(frozen=True)
class RuntimeContext:
    """Stable per-session runtime metadata.

    Environment variables remain startup inputs, but runtime components should
    prefer this context over mutable process-global env reads.
    """

    mode: TradingMode
    session_id: str
    broker_environment: str = "live"
    market_data_environment: str = "live"
    strict_autonomous: bool = False

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    @property
    def is_paper(self) -> bool:
        return self.mode == "paper"

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "session_id": self.session_id,
            "broker_environment": self.broker_environment,
            "market_data_environment": self.market_data_environment,
            "strict_autonomous": self.strict_autonomous,
        }


def coerce_runtime_context(value: object) -> RuntimeContext | None:
    """Return *value* when it is already a RuntimeContext."""
    return value if isinstance(value, RuntimeContext) else None


def resolve_effective_trading_mode(
    *,
    runtime_context: RuntimeContext | None = None,
    env_mode: object | None = None,
    fallback: str = "paper",
) -> str:
    """Resolve the effective trading mode with context taking precedence."""
    if runtime_context is not None:
        return runtime_context.mode

    raw_mode = env_mode if env_mode is not None else fallback
    mode = str(raw_mode).strip().lower()
    if mode in {"live", "production", "prod"}:
        return "live"
    return "paper"

__all__ = [
    "RuntimeContext",
    "TradingMode",
    "coerce_runtime_context",
    "resolve_effective_trading_mode",
]
