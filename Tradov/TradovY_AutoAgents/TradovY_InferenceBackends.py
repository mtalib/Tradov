#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovY_AutoAgents
Module: TradovY_InferenceBackends.py
Purpose: Pluggable inference backends for TradovY autonomous agents

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Description:
    Defines an abstract InferenceBackend protocol and two concrete
    implementations so that Y-series agents can transparently switch
    between Ollama (default) and Intel OpenVINO GenAI without any
    changes to agent code.

    Backend selection is controlled by a single env var:

        TRADOV_LLM_BACKEND=ollama      → OllamaBackend   (default)
        TRADOV_LLM_BACKEND=openvino    → OpenVINOBackend

    OllamaBackend
    -------------
    Wraps the `ollama` Python SDK.  Model names (e.g. "gemma4:e4b") come
    from OllamaConfig in TradovY00_BaseAutoAgent and are passed in at
    construction time as a plain role→name dict.

    OpenVINOBackend
    ---------------
    Runs INT4-quantised OpenVINO IR models via `openvino-genai`.
    Pipelines are lazy-loaded per model directory and cached.
    Device selection uses the OpenVINO AUTO plugin which probes for
    Intel iGPU → NPU → CPU in priority order.

    Model directories are expected to contain OpenVINO IR exports
    produced by optimum-cli:

        optimum-cli export openvino \\
            --model google/gemma-3-4b-it \\
            --weight-format int4 \\
            models/openvino/gemma4-e4b

    Install the required package with:

        pip install openvino-genai optimum[openvino]

License: All dependencies are Apache 2.0 / MIT / BSD — AGPL-free.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger("TradovY_AutoAgents")


# ==============================================================================
# ABSTRACT BASE
# ==============================================================================
class InferenceBackend(ABC):
    """Contract that all TradovY inference backends must satisfy.

    Backend instances are created once per agent and reused across
    every ``llm_query()`` call.  Thread safety is the responsibility
    of the concrete implementation (Ollama's SDK is thread-safe;
    OpenVINO pipelines are not — each agent owns its own instance).
    """

    @abstractmethod
    def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        """Send a chat-formatted prompt and return the text response.

        Args:
            model_id:    Backend-specific identifier — a model tag for
                         Ollama (``"gemma4:e4b"``) or a directory path
                         for OpenVINO (``"models/openvino/gemma4-e4b"``).
            messages:    OpenAI-style list of ``{"role": ..., "content": ...}``
                         dicts (system / user / assistant).
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.

        Returns:
            The generated text, or ``None`` if the backend is unavailable
            or generation fails (callers handle retries).
        """
        ...

    @abstractmethod
    def model_id_for_role(self, role: str) -> str:
        """Return the backend-specific model identifier for a role name.

        Args:
            role: One of ``"primary"``, ``"fast"``, ``"code"``,
                  ``"finance"``.

        Returns:
            A model tag (Ollama) or directory path (OpenVINO).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend is reachable / initialised."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name for status reporting and logging."""
        ...


# ==============================================================================
# OLLAMA BACKEND
# ==============================================================================
class OllamaBackend(InferenceBackend):
    """Calls the local Ollama server via the ``ollama`` Python SDK.

    Args:
        role_model_map: Mapping of role name to Ollama model tag, e.g.
            ``{"primary": "gemma4:e4b", "fast": "gemma4:e2b", ...}``.
    """

    def __init__(self, role_model_map: dict[str, str]) -> None:
        self._role_model_map = role_model_map
        try:
            import ollama as _ollama
            self._ollama = _ollama
            self._available = True
        except ImportError:
            self._ollama = None
            self._available = False
            logger.warning(
                "[OllamaBackend] 'ollama' package not installed. "
                "LLM queries will be disabled."
            )

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        return self._available

    def model_id_for_role(self, role: str) -> str:
        return self._role_model_map.get(
            role, self._role_model_map.get("primary", "")
        )

    def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        if not self._available:
            return None
        response = self._ollama.chat(
            model=model_id,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )
        return response.get("message", {}).get("content", "") or None


# ==============================================================================
# OPENVINO CONFIG
# ==============================================================================
@dataclass
class OpenVINOConfig:
    """Paths to INT4-quantised OpenVINO IR model directories, one per role.

    All paths default to env-var overrides, falling back to paths under
    ``models/openvino/``.  The ``device`` field is passed directly to the
    OpenVINO AUTO / explicit device plugin:

    - ``"AUTO"``  — OpenVINO picks the best available device automatically
                    (iGPU → NPU → CPU on Intel hardware).
    - ``"GPU"``   — force Intel Arc / Iris Xe iGPU.
    - ``"NPU"``   — force Intel AI Boost NPU (requires NPU driver).
    - ``"CPU"``   — force CPU fallback.

    Convert a Hugging Face model to OpenVINO INT4 format with::

        optimum-cli export openvino \\
            --model google/gemma-3-4b-it \\
            --weight-format int4 \\
            models/openvino/gemma4-e4b
    """

    primary_model_dir: str = field(
        default_factory=lambda: os.getenv(
            "OPENVINO_PRIMARY_MODEL_DIR", "models/openvino/gemma4-e4b"
        )
    )
    fast_model_dir: str = field(
        default_factory=lambda: os.getenv(
            "OPENVINO_FAST_MODEL_DIR", "models/openvino/gemma4-e2b"
        )
    )
    code_model_dir: str = field(
        default_factory=lambda: os.getenv(
            "OPENVINO_CODE_MODEL_DIR", "models/openvino/gemma4-e4b"
        )
    )
    finance_model_dir: str = field(
        default_factory=lambda: os.getenv(
            "OPENVINO_FINANCE_MODEL_DIR", "models/openvino/gemma4-e4b"
        )
    )
    device: str = field(
        default_factory=lambda: os.getenv("OPENVINO_DEVICE", "AUTO")
    )

    @classmethod
    def from_env(cls) -> "OpenVINOConfig":
        """Construct config from environment variables."""
        return cls()


# ==============================================================================
# OPENVINO BACKEND
# ==============================================================================
class OpenVINOBackend(InferenceBackend):
    """Runs INT4 models via Intel OpenVINO GenAI.

    Pipelines are lazy-loaded on first use for each model directory and
    then cached for the lifetime of the agent.  This means the first
    query for a given role incurs a one-time load cost; subsequent
    queries reuse the cached pipeline.

    Device ``"AUTO"`` lets the OpenVINO runtime probe for the best
    available device on the host, which on a Core Ultra NUC means:
    Intel Arc iGPU → Intel AI Boost NPU → CPU fallback.

    The NPU path requires the Intel NPU driver to be installed::

        # Ubuntu — Intel NPU driver (kernel 6.6+)
        sudo apt install intel-npu-driver

    Args:
        config: OpenVINO configuration; defaults to ``OpenVINOConfig.from_env()``.
    """

    # Gemma 4 conversation turn delimiters (same tokens as Gemma 3)
    _BOT: str = "<start_of_turn>"
    _EOT: str = "<end_of_turn>\n"
    # Gemma 4 has native system-role support; OpenAI "assistant" maps to Gemma "model"
    _ROLE_MAP: dict[str, str] = {"assistant": "model", "system": "system", "user": "user"}

    def __init__(self, config: OpenVINOConfig | None = None) -> None:
        self._config = config or OpenVINOConfig.from_env()
        self._pipelines: dict[str, Any] = {}

        try:
            import openvino_genai as _ov_genai
            self._ov_genai = _ov_genai
            self._available = True
            logger.info(
                "[OpenVINOBackend] Initialised — device=%s", self._config.device
            )
        except ImportError:
            self._ov_genai = None
            self._available = False
            logger.warning(
                "[OpenVINOBackend] 'openvino-genai' not installed. "
                "Run: pip install openvino-genai optimum[openvino]"
            )

    @property
    def name(self) -> str:
        return f"openvino({self._config.device})"

    def is_available(self) -> bool:
        return self._available

    def model_id_for_role(self, role: str) -> str:
        return {
            "primary": self._config.primary_model_dir,
            "fast":    self._config.fast_model_dir,
            "code":    self._config.code_model_dir,
            "finance": self._config.finance_model_dir,
        }.get(role, self._config.primary_model_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_pipeline(self, model_dir: str) -> Any | None:
        """Lazy-load and cache an LLMPipeline for *model_dir*."""
        if not self._available:
            return None

        if model_dir not in self._pipelines:
            resolved = Path(model_dir)
            if not resolved.exists():
                logger.error(
                    f"[OpenVINOBackend] Model directory not found: {model_dir}. "
                    "Export a model first — see module docstring for the command."
                )
                return None
            try:
                logger.info(
                    f"[OpenVINOBackend] Loading pipeline: {model_dir} "
                    f"on device={self._config.device}"
                )
                self._pipelines[model_dir] = self._ov_genai.LLMPipeline(
                    model_dir, self._config.device
                )
                logger.info("[OpenVINOBackend] Pipeline ready: %s", model_dir)
            except Exception as exc:
                logger.error(
                    "[OpenVINOBackend] Failed to load %s: %s", model_dir, exc
                )
                return None

        return self._pipelines[model_dir]

    def _format_chat_prompt(self, messages: list[dict[str, str]]) -> str:
        """Convert an OpenAI-style messages list to Gemma 4 turn format.

        Gemma 4 chat template (native system-role support)::

            <start_of_turn>system
            {system_content}<end_of_turn>
            <start_of_turn>user
            {user_content}<end_of_turn>
            <start_of_turn>model
            {response}<end_of_turn>
            <start_of_turn>model

        Unlike Gemma 3, Gemma 4 has a dedicated ``system`` role so system
        messages are emitted as their own turn rather than being merged
        into the first user turn.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.

        Returns:
            A single string ready for ``LLMPipeline.generate()``.
        """
        parts: list[str] = []
        for msg in messages:
            role = self._ROLE_MAP.get(msg.get("role", "user"), "user")
            content = msg.get("content", "")
            parts.append(f"{self._BOT}{role}\n{content}{self._EOT}")

        # Open the model's response turn
        parts.append(f"{self._BOT}model\n")
        return "".join(parts)

    # ------------------------------------------------------------------
    # InferenceBackend implementation
    # ------------------------------------------------------------------
    def chat(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        """Generate a response using an OpenVINO LLMPipeline.

        Args:
            model_id:    Path to the OpenVINO IR model directory.
            messages:    OpenAI-style messages list.
            temperature: Sampling temperature.
            max_tokens:  Maximum tokens to generate.

        Returns:
            Generated text string, or ``None`` on failure.
        """
        pipeline = self._get_pipeline(model_id)
        if pipeline is None:
            return None

        # Prefer the model's own chat template (most accurate for any Gemma version);
        # fall back to manual formatting if apply_chat_template is unavailable.
        try:
            tokenizer = pipeline.get_tokenizer()
            prompt = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True
            )
        except Exception:
            prompt = self._format_chat_prompt(messages)

        gen_config = self._ov_genai.GenerationConfig()
        gen_config.max_new_tokens = max_tokens
        gen_config.temperature = temperature
        gen_config.do_sample = temperature > 0.0

        try:
            result = pipeline.generate(prompt, gen_config)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:
            logger.error(
                "[OpenVINOBackend] Generation failed for %s: %s", model_id, exc
            )
            return None
