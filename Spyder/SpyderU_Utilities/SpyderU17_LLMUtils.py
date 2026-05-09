#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU17_LLMUtils.py
Purpose: Shared utilities for LLM/Ollama integration across X-series and Y-series agents

Author: Spyder
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re

# ==============================================================================
# CONSTANTS — default model fallbacks (overridden by .env)
# ==============================================================================
_DEFAULT_PRIMARY = "gemma4:26b"
_DEFAULT_FAST    = "gemma4:e4b"
_DEFAULT_CODE    = "gemma4:26b"
_DEFAULT_FINANCE = "gemma4:e4b"


# ==============================================================================
# ENV-BASED MODEL RESOLUTION
# ==============================================================================

def get_primary_model() -> str:
    """Return the configured PRIMARY model from env, or the default."""
    return os.getenv("OLLAMA_PRIMARY_MODEL", _DEFAULT_PRIMARY)


def get_fast_model() -> str:
    """Return the configured FAST model from env, or the default."""
    return os.getenv("OLLAMA_FAST_MODEL", _DEFAULT_FAST)


def get_code_model() -> str:
    """Return the configured CODE model from env, or the default."""
    return os.getenv("OLLAMA_CODE_MODEL", _DEFAULT_CODE)


def get_finance_model() -> str:
    """Return the configured FINANCE model from env, or the default."""
    return os.getenv("OLLAMA_FINANCE_MODEL", _DEFAULT_FINANCE)


# ==============================================================================
# THINKING-BLOCK HANDLING
# ==============================================================================

# Gemma 4 wraps chain-of-thought in <|channel>thought\n...<channel|>
# This regex strips those blocks before returning content to callers.
_THINK_PATTERN = re.compile(
    r"<\|channel>thought\n.*?<channel\|>",
    re.DOTALL,
)


def strip_thinking_block(content: str) -> str:
    """Strip Gemma 4 thinking tokens from an LLM response.

    Gemma 4 (and some other models with built-in reasoning) may wrap
    chain-of-thought in ``<|channel>thought\\n...<channel|>`` blocks.
    This function removes those blocks and returns clean response text
    suitable for downstream JSON parsing, logging, or display.

    Args:
        content: Raw LLM response string, potentially containing think blocks.

    Returns:
        Response string with all thinking blocks removed and leading/trailing
        whitespace stripped.
    """
    if not content:
        return content
    return _THINK_PATTERN.sub("", content).strip()


__all__ = [
    "get_primary_model",
    "get_fast_model",
    "get_code_model",
    "get_finance_model",
    "strip_thinking_block",
]
