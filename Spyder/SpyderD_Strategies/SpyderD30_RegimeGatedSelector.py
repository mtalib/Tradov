#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Series: SpyderD_Strategies
Module: SpyderD30_RegimeGatedSelector.py
Purpose: Regime-Gated Strategy Selection
Author: SPYDER Team
Date Created: 2025-01-04
Last Updated: 2025-01-04

Description:
    Implements Regime-Gated Strategy Selection based on HMM Regime Detection,
    inspired by Renaissance Technologies' quantitative framework.

    Regime-Gated Selection provides:
    - Automatic strategy switching based on market regime
    - Avoidance of "strategy mismatch" errors
    - Optimal strategy selection for each regime (Bull/Chop/Crisis)
    - Confidence-based strategy activation
    - Smooth transitions between strategies
    - Integration with existing Spyder strategies

    Based on Renaissance research, regime-gated selection is critical
    for avoiding deploying inappropriate strategies during wrong
    market conditions, which is a major source of losses.

Key Features:
    - HMM-based regime detection integration
    - Strategy matrix (regime × optimal strategy)
    - Confidence thresholds for strategy switching
    - Smooth transition management
    - Strategy performance tracking by regime
    - Automatic strategy activation/deactivation
    - Integration with existing Spyder strategies

Dependencies:
    - SpyderL09_UnifiedRegimeEngine for consensus regime detection (preferred)
    - SpyderE21_HMMRegimeDetector for regime detection (fallback)
    - SpyderD_Strategies for available strategies
    - SpyderE20_FrustrationAnalyzer for market state assessment

References:
    - Renaissance Technologies research on regime-gated trading
    - Quantitative finance literature on regime switching
    - Machine learning applications to trading
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# Reinforcement Learning (optional)
try:
    import gym
    from gym import spaces
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv  # noqa: F401
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback logging if custom modules not available
    import logging
    SpyderLogger = logging.getLogger
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.error("[%s] %s", context, e)
    })

# Import L09 Unified Regime Engine (preferred source)
try:
    from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
        UnifiedRegimeEngine,
        MarketRegime as L09MarketRegime,
        RegimeConsensus,
    )
    L09_AVAILABLE = True
except ImportError:
    try:
        from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
            UnifiedRegimeEngine,
            MarketRegime as L09MarketRegime,
            RegimeConsensus,
        )
        L09_AVAILABLE = True
    except ImportError:
        L09_AVAILABLE = False

# Import HMM Regime Detector (fallback)
try:
    from Spyder.SpyderE_Risk.SpyderE21_HMMRegimeDetector import (
        HMMRegimeDetector,
        MarketRegime,
        RegimePrediction
    )
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn(
        "HMMRegimeDetector not available. Regime-gated selection disabled. "
        "Install with: pip install hmmlearn", stacklevel=2
    )

    # Fallback MarketRegime enum
    class MarketRegime(Enum):
        BULL = "bull"
        CHOP = "chop"
        CRISIS = "crisis"
        UNKNOWN = "unknown"

# L09 8-state → D30 4-state regime mapping (lazily built to avoid circular imports)
_L09_TO_D30_REGIME_MAP: dict | None = None


def _get_l09_to_d30_regime_map() -> dict:
    """Return the L09 → D30 regime mapping, building it on first access."""
    global _L09_TO_D30_REGIME_MAP
    if _L09_TO_D30_REGIME_MAP is None:
        if L09_AVAILABLE:
            _L09_TO_D30_REGIME_MAP = {
                L09MarketRegime.BULL_TRENDING: MarketRegime.BULL,
                L09MarketRegime.BEAR_TRENDING: MarketRegime.CRISIS,
                L09MarketRegime.SIDEWAYS_RANGE: MarketRegime.CHOP,
                L09MarketRegime.HIGH_VOLATILITY: MarketRegime.CHOP,
                L09MarketRegime.LOW_VOLATILITY: MarketRegime.BULL,
                L09MarketRegime.CRISIS_MODE: MarketRegime.CRISIS,
                L09MarketRegime.RECOVERY_MODE: MarketRegime.BULL,
                L09MarketRegime.UNKNOWN: MarketRegime.UNKNOWN,
            }
        else:
            _L09_TO_D30_REGIME_MAP = {}
    return _L09_TO_D30_REGIME_MAP

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Strategy Types
class StrategyType(Enum):
    """Available strategy types."""
    CALENDAR_SPREADS = "calendar_spreads"  # Optimal for Bull regime
    IRON_CONDORS = "iron_condors"  # Optimal for Chop regime
    LONG_STRADDLES = "long_straddles"  # Optimal for Crisis regime
    CREDIT_SPREADS = "credit_spreads"  # Good for Bull/Chop
    DEBIT_SPREADS = "debit_spreads"  # Good for Chop/Crisis
    IRON_BUTTERFLIES = "iron_butterflies"  # Good for Chop
    VERTICAL_SPREADS = "vertical_spreads"  # Good for Bull/Chop
    RATIO_SPREADS = "ratio_spreads"  # Good for volatility
    NEUTRAL = "neutral"  # No active strategy

# Transition States
class TransitionState(Enum):
    """Transition states for strategy switching."""
    STABLE = "stable"  # No transition needed
    PREPARING = "preparing"  # Preparing to switch
    SWITCHING = "switching"  # In transition
    COMPLETED = "completed"  # Transition complete

# Default Configuration
DEFAULT_CONFIDENCE_THRESHOLD = 0.70  # 70% confidence required to switch
DEFAULT_MIN_REGIME_DURATION = 5  # Minimum days in regime before switching
DEFAULT_TRANSITION_PERIOD = 3  # Days to transition between strategies

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class StrategyProfile:
    """Profile of a trading strategy."""
    strategy_type: StrategyType
    optimal_regimes: list[MarketRegime]  # Regimes where this strategy is optimal
    avoid_regimes: list[MarketRegime]  # Regimes to avoid
    greek_profile: str  # "positive_delta", "neutral_delta", "negative_delta"
    volatility_preference: str  # "low", "medium", "high"
    expected_sharpe: float  # Expected Sharpe ratio
    max_drawdown: float  # Maximum expected drawdown
    description: str = ""

@dataclass
class RegimeStrategyMapping:
    """Mapping of regimes to optimal strategies."""
    regime: MarketRegime
    primary_strategy: StrategyType  # Best strategy for this regime
    secondary_strategies: list[StrategyType]  # Alternative strategies
    avoid_strategies: list[StrategyType]  # Strategies to avoid
    confidence_threshold: float  # Minimum confidence to use primary strategy

@dataclass
class StrategySelection:
    """Result of strategy selection."""
    timestamp: datetime
    current_regime: MarketRegime
    selected_strategy: StrategyType
    previous_strategy: StrategyType | None
    confidence: float  # Confidence in regime detection
    transition_state: TransitionState
    transition_progress: float  # 0-1, progress of transition
    reason: str  # Explanation for selection
    expected_performance: dict[str, float] | None = None  # Expected metrics

@dataclass
class StrategyPerformance:
    """Performance tracking by regime."""
    strategy_type: StrategyType
    regime: MarketRegime
    total_trades: int
    win_rate: float
    avg_return: float
    sharpe_ratio: float
    max_drawdown: float
    last_updated: datetime

# ==============================================================================
# STRATEGY PROFILES
# ==============================================================================

# Strategy profiles for each strategy type
STRATEGY_PROFILES = {
    StrategyType.CALENDAR_SPREADS: StrategyProfile(
        strategy_type=StrategyType.CALENDAR_SPREADS,
        optimal_regimes=[MarketRegime.BULL],
        avoid_regimes=[MarketRegime.CRISIS],
        greek_profile="positive_delta",
        volatility_preference="low",
        expected_sharpe=2.0,
        max_drawdown=0.10,
        description="Calendar spreads profit from time decay in low-volatility bull markets"
    ),
    StrategyType.IRON_CONDORS: StrategyProfile(
        strategy_type=StrategyType.IRON_CONDORS,
        optimal_regimes=[MarketRegime.CHOP],
        avoid_regimes=[MarketRegime.BULL, MarketRegime.CRISIS],
        greek_profile="neutral_delta",
        volatility_preference="medium",
        expected_sharpe=1.8,
        max_drawdown=0.15,
        description="Iron condors profit from range-bound markets"
    ),
    StrategyType.LONG_STRADDLES: StrategyProfile(
        strategy_type=StrategyType.LONG_STRADDLES,
        optimal_regimes=[MarketRegime.CRISIS],
        avoid_regimes=[MarketRegime.BULL, MarketRegime.CHOP],
        greek_profile="neutral_delta",
        volatility_preference="high",
        expected_sharpe=1.5,
        max_drawdown=0.20,
        description="Long straddles profit from large moves in crisis conditions"
    ),
    StrategyType.CREDIT_SPREADS: StrategyProfile(
        strategy_type=StrategyType.CREDIT_SPREADS,
        optimal_regimes=[MarketRegime.BULL, MarketRegime.CHOP],
        avoid_regimes=[MarketRegime.CRISIS],
        greek_profile="positive_delta",
        volatility_preference="low",
        expected_sharpe=1.7,
        max_drawdown=0.12,
        description="Credit spreads profit from time decay in stable markets"
    ),
    StrategyType.DEBIT_SPREADS: StrategyProfile(
        strategy_type=StrategyType.DEBIT_SPREADS,
        optimal_regimes=[MarketRegime.CHOP, MarketRegime.CRISIS],
        avoid_regimes=[MarketRegime.BULL],
        greek_profile="neutral_delta",
        volatility_preference="high",
        expected_sharpe=1.6,
        max_drawdown=0.18,
        description="Debit spreads profit from directional moves"
    ),
    StrategyType.IRON_BUTTERFLIES: StrategyProfile(
        strategy_type=StrategyType.IRON_BUTTERFLIES,
        optimal_regimes=[MarketRegime.CHOP],
        avoid_regimes=[MarketRegime.BULL, MarketRegime.CRISIS],
        greek_profile="neutral_delta",
        volatility_preference="medium",
        expected_sharpe=1.9,
        max_drawdown=0.14,
        description="Iron butterflies profit from low volatility"
    ),
    StrategyType.VERTICAL_SPREADS: StrategyProfile(
        strategy_type=StrategyType.VERTICAL_SPREADS,
        optimal_regimes=[MarketRegime.BULL, MarketRegime.CHOP],
        avoid_regimes=[MarketRegime.CRISIS],
        greek_profile="positive_delta",
        volatility_preference="low",
        expected_sharpe=1.8,
        max_drawdown=0.13,
        description="Vertical spreads profit from directional bias"
    ),
    StrategyType.RATIO_SPREADS: StrategyProfile(
        strategy_type=StrategyType.RATIO_SPREADS,
        optimal_regimes=[MarketRegime.CHOP, MarketRegime.CRISIS],
        avoid_regimes=[MarketRegime.BULL],
        greek_profile="neutral_delta",
        volatility_preference="high",
        expected_sharpe=1.5,
        max_drawdown=0.16,
        description="Ratio spreads profit from volatility skew"
    ),
    StrategyType.NEUTRAL: StrategyProfile(
        strategy_type=StrategyType.NEUTRAL,
        optimal_regimes=[MarketRegime.UNKNOWN],
        avoid_regimes=[],
        greek_profile="neutral_delta",
        volatility_preference="any",
        expected_sharpe=0.0,
        max_drawdown=0.00,
        description="No active strategy - wait for clear signal"
    )
}

# Regime-strategy mapping
REGIME_STRATEGY_MAPPINGS = {
    MarketRegime.BULL: RegimeStrategyMapping(
        regime=MarketRegime.BULL,
        primary_strategy=StrategyType.CALENDAR_SPREADS,
        secondary_strategies=[
            StrategyType.CREDIT_SPREADS,
            StrategyType.VERTICAL_SPREADS
        ],
        avoid_strategies=[
            StrategyType.LONG_STRADDLES,
            StrategyType.DEBIT_SPREADS
        ],
        confidence_threshold=0.70
    ),
    MarketRegime.CHOP: RegimeStrategyMapping(
        regime=MarketRegime.CHOP,
        primary_strategy=StrategyType.IRON_CONDORS,
        secondary_strategies=[
            StrategyType.IRON_BUTTERFLIES,
            StrategyType.CREDIT_SPREADS,
            StrategyType.VERTICAL_SPREADS
        ],
        avoid_strategies=[
            StrategyType.CALENDAR_SPREADS,
            StrategyType.LONG_STRADDLES
        ],
        confidence_threshold=0.70
    ),
    MarketRegime.CRISIS: RegimeStrategyMapping(
        regime=MarketRegime.CRISIS,
        primary_strategy=StrategyType.LONG_STRADDLES,
        secondary_strategies=[
            StrategyType.DEBIT_SPREADS,
            StrategyType.RATIO_SPREADS
        ],
        avoid_strategies=[
            StrategyType.CALENDAR_SPREADS,
            StrategyType.CREDIT_SPREADS,
            StrategyType.IRON_CONDORS,
            StrategyType.IRON_BUTTERFLIES,
            StrategyType.VERTICAL_SPREADS
        ],
        confidence_threshold=0.70
    ),
    MarketRegime.UNKNOWN: RegimeStrategyMapping(
        regime=MarketRegime.UNKNOWN,
        primary_strategy=StrategyType.NEUTRAL,
        secondary_strategies=[],
        avoid_strategies=[],
        confidence_threshold=0.90
    )
}

# ==============================================================================
# RL ENVIRONMENT — STRATEGY SELECTION
# ==============================================================================
if HAS_SB3:
    class StrategySelectionEnvironment(gym.Env):
        """
        RL environment for dynamic strategy selection across market regimes.

        The agent learns to select optimal strategies by observing regime
        probabilities, market indicators, and per-strategy recent P&L,
        rather than relying on a static regime→strategy mapping.

        Observation (15-dim):
            [regime_probs(4), regime_confidence, days_in_regime,
             vix_percentile, spy_return_5d, spy_return_20d, put_call_ratio,
             market_breadth, per_strategy_recent_pnl(5 top strategies)]

        Actions (9 discrete — one per non-neutral StrategyType):
            0=calendar_spreads, 1=iron_condors, 2=long_straddles,
            3=credit_spreads, 4=debit_spreads, 5=iron_butterflies,
            6=vertical_spreads, 7=ratio_spreads, 8=neutral

        Reward:
            risk-adjusted return of selected strategy over next period.
        """

        STRATEGY_LIST = [
            'calendar_spreads', 'iron_condors', 'long_straddles',
            'credit_spreads', 'debit_spreads', 'iron_butterflies',
            'vertical_spreads', 'ratio_spreads', 'neutral',
        ]
        N_STRATEGIES = len(STRATEGY_LIST)

        def __init__(
            self,
            episode_length: int = 60,
            historical_returns: dict[str, np.ndarray] | None = None,
        ):
            super().__init__()
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(15,), dtype=np.float32
            )
            self.action_space = spaces.Discrete(self.N_STRATEGIES)
            self.episode_length = episode_length

            # Strategy return histories (synthetic if not provided)
            if historical_returns is not None:
                self.strategy_returns = historical_returns
            else:
                self.strategy_returns = self._generate_synthetic_returns()

            self.current_step = 0
            self.cumulative_reward = 0.0
            self.current_regime_idx = 0

        def reset(self) -> np.ndarray:
            self.current_step = 0
            self.cumulative_reward = 0.0
            self.current_regime_idx = np.random.randint(0, 4)
            return self._get_obs()

        def step(self, action: int):
            strategy_name = self.STRATEGY_LIST[action]

            # Simulate strategy return for this period
            ret_series = self.strategy_returns.get(strategy_name, np.zeros(500))
            idx = (self.current_step * 7 + np.random.randint(0, len(ret_series))) % len(ret_series)
            strategy_return = float(ret_series[idx])

            # Regime alignment bonus/penalty
            regime_names = ['bull', 'chop', 'crisis', 'unknown']
            regime = regime_names[self.current_regime_idx]
            alignment_bonus = 0.0
            regime_strategy_map = {
                'bull': ['calendar_spreads', 'credit_spreads', 'vertical_spreads'],
                'chop': ['iron_condors', 'iron_butterflies', 'credit_spreads'],
                'crisis': ['long_straddles', 'debit_spreads', 'ratio_spreads'],
                'unknown': ['neutral'],
            }
            if strategy_name in regime_strategy_map.get(regime, []):
                alignment_bonus = 0.002
            elif strategy_name == 'neutral':
                alignment_bonus = -0.001  # Small penalty for doing nothing

            reward = strategy_return + alignment_bonus
            self.cumulative_reward += reward
            self.current_step += 1

            # Regime transitions
            if np.random.random() < 0.05:  # 5% chance of regime change
                self.current_regime_idx = np.random.randint(0, 4)

            done = self.current_step >= self.episode_length
            return self._get_obs(), float(reward), done, {
                'strategy': strategy_name,
                'regime': regime_names[self.current_regime_idx],
                'cumulative_reward': self.cumulative_reward,
            }

        def _get_obs(self) -> np.ndarray:
            regime_probs = np.zeros(4)
            regime_probs[self.current_regime_idx] = 0.7
            other_prob = 0.3 / 3
            for i in range(4):
                if i != self.current_regime_idx:
                    regime_probs[i] = other_prob

            # Market indicators (synthetic)
            vix_pct = np.random.uniform(0, 1)
            spy_5d = np.random.normal(0, 0.02)
            spy_20d = np.random.normal(0, 0.04)
            pcr = np.random.uniform(0.5, 1.5)
            breadth = np.random.uniform(-1, 1)

            # Per-strategy recent P&L (top 5)
            strat_pnls = []
            for s in self.STRATEGY_LIST[:5]:
                r = self.strategy_returns.get(s, np.zeros(10))
                strat_pnls.append(float(np.mean(r[-10:])))

            obs = np.concatenate([
                regime_probs,           # 4
                [0.7],                  # regime_confidence  # 1
                [self.current_step],    # days_in_regime proxy  # 1
                [vix_pct, spy_5d, spy_20d, pcr, breadth],  # 5
                strat_pnls[:4],         # 4 (truncate to fit 15)
            ])
            return obs.astype(np.float32)

        @staticmethod
        def _generate_synthetic_returns() -> dict[str, np.ndarray]:
            np.random.seed(42)
            returns = {}
            for s in StrategySelectionEnvironment.STRATEGY_LIST:
                mu = np.random.uniform(-0.001, 0.003)
                sigma = np.random.uniform(0.005, 0.02)
                returns[s] = np.random.normal(mu, sigma, 500)
            return returns


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class RegimeGatedSelector:
    """
    Regime-Gated Strategy Selector for Automatic Strategy Switching.

    Inspired by Renaissance Technologies' quantitative framework, this module
    implements automatic strategy selection based on HMM regime detection,
    avoiding "strategy mismatch" errors where wrong strategies are deployed
    during inappropriate market conditions.

    Key Concepts:
        - Regime Detection: HMM identifies current market state
        - Strategy Matrix: Maps regimes to optimal strategies
        - Confidence Thresholds: Only switch when confident
        - Smooth Transitions: Gradual strategy switching
        - Performance Tracking: Learn from past performance

    Example:
        >>> selector = RegimeGatedSelector()
        >>> selector.initialize(hmm_detector)
        >>> selection = selector.select_strategy(regime_prediction)
        >>> print(f"Strategy: {selection.selected_strategy.value}")
    """

    def __init__(self,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 min_regime_duration: int = DEFAULT_MIN_REGIME_DURATION,
                 transition_period: int = DEFAULT_TRANSITION_PERIOD):
        """
        Initialize Regime-Gated Strategy Selector.

        Args:
            confidence_threshold: Minimum confidence to switch strategies
            min_regime_duration: Minimum days in regime before switching
            transition_period: Days to transition between strategies
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.confidence_threshold = confidence_threshold
        self.min_regime_duration = min_regime_duration
        self.transition_period = transition_period

        # HMM Regime Detector (E21 — fallback)
        self.hmm_detector: HMMRegimeDetector | None = None

        # L09 Unified Regime Engine (preferred)
        self.unified_engine: UnifiedRegimeEngine | None = None if not L09_AVAILABLE else None

        # State tracking
        self.current_strategy: StrategyType = StrategyType.NEUTRAL
        self.previous_strategy: StrategyType | None = None
        self.current_regime: MarketRegime = MarketRegime.UNKNOWN
        self.days_in_regime: int = 0
        self.days_in_transition: int = 0
        self.transition_state: TransitionState = TransitionState.STABLE

        # Historical tracking
        self.selection_history: list[StrategySelection] = []
        self.performance_history: dict[StrategyType, list[StrategyPerformance]] = {}

        # Performance tracking
        for strategy_type in StrategyType:
            self.performance_history[strategy_type] = []

        self.logger.info(
            f"RegimeGatedSelector initialized: "
            f"confidence_threshold={confidence_threshold:.2%}, "
            f"min_duration={min_regime_duration} days"
        )

        if not HMM_AVAILABLE:
            self.logger.warning("HMM not available - regime detection disabled")

        if L09_AVAILABLE:
            self.logger.info("L09 UnifiedRegimeEngine available as preferred regime source")

        # RL strategy selection agent (optional)
        self._rl_selector_model = None
        self._rl_enabled = HAS_SB3
        self._load_rl_selector_model()

    def _load_rl_selector_model(self, model_path: str | None = None) -> None:
        """Load pre-trained RL strategy selection model if available."""
        if not HAS_SB3:
            self._rl_enabled = False
            return
        try:
            if model_path:
                self._rl_selector_model = PPO.load(model_path)
                self.logger.info("RL strategy selector loaded from %s", model_path)
            else:
                import os
                default_path = "models/rl/strategy_selection/strategy_selection_PPO_final"
                if os.path.exists(default_path + ".zip"):
                    self._rl_selector_model = PPO.load(default_path)
                    self.logger.info("RL strategy selector loaded from default path")
                else:
                    self._rl_enabled = False
                    self.logger.debug("No RL strategy selector model found — using rule-based selection")  # noqa: E501
        except Exception as e:
            self._rl_enabled = False
            self.logger.warning("Failed to load RL strategy selector: %s", e)

    def _get_rl_strategy_observation(self, regime_prediction) -> np.ndarray:
        """Build observation vector for RL strategy selection agent."""
        regime_map = {
            MarketRegime.BULL: 0, MarketRegime.CHOP: 1,
            MarketRegime.CRISIS: 2, MarketRegime.UNKNOWN: 3,
        }
        regime_idx = regime_map.get(regime_prediction.current_regime, 3)
        regime_probs = np.zeros(4)
        regime_probs[regime_idx] = regime_prediction.confidence
        remaining = (1.0 - regime_prediction.confidence) / 3
        for i in range(4):
            if i != regime_idx:
                regime_probs[i] = remaining

        # Per-strategy recent Sharpe (from performance_history)
        strat_pnls = []
        strategy_order = [
            StrategyType.CALENDAR_SPREADS, StrategyType.IRON_CONDORS,
            StrategyType.LONG_STRADDLES, StrategyType.CREDIT_SPREADS,
            StrategyType.DEBIT_SPREADS,
        ]
        for st in strategy_order[:4]:
            perfs = self.performance_history.get(st, [])
            if perfs:
                strat_pnls.append(perfs[-1].sharpe_ratio)
            else:
                strat_pnls.append(0.0)

        obs = np.concatenate([
            regime_probs,                    # 4
            [regime_prediction.confidence],  # 1
            [float(self.days_in_regime)],    # 1
            [0.5, 0.0, 0.0, 1.0, 0.0],     # placeholders: vix_pct, spy_5d, spy_20d, pcr, breadth
            strat_pnls,                      # 4
        ])
        return obs.astype(np.float32)

    def _rl_select_strategy(self, regime_prediction) -> StrategyType | None:
        """Use RL model to select strategy (returns None if RL not available)."""
        if not self._rl_enabled or self._rl_selector_model is None:
            return None
        try:
            obs = self._get_rl_strategy_observation(regime_prediction)
            action, _ = self._rl_selector_model.predict(obs, deterministic=True)
            action = int(action)
            strategy_map = {
                0: StrategyType.CALENDAR_SPREADS,
                1: StrategyType.IRON_CONDORS,
                2: StrategyType.LONG_STRADDLES,
                3: StrategyType.CREDIT_SPREADS,
                4: StrategyType.DEBIT_SPREADS,
                5: StrategyType.IRON_BUTTERFLIES,
                6: StrategyType.VERTICAL_SPREADS,
                7: StrategyType.RATIO_SPREADS,
                8: StrategyType.NEUTRAL,
            }
            return strategy_map.get(action)
        except Exception as e:
            self.logger.warning("RL strategy selection failed: %s", e)
            return None

    def initialize(self, hmm_detector: HMMRegimeDetector) -> bool:
        """
        Initialize with HMM Regime Detector (fallback path).

        Args:
            hmm_detector: HMM Regime Detector instance

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not HMM_AVAILABLE:
                self.logger.error("HMM not available - cannot initialize")
                return False

            self.hmm_detector = hmm_detector

            self.logger.info("RegimeGatedSelector initialized with HMM detector")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "RegimeGatedSelector.initialize")
            return False

    def initialize_with_unified_engine(self, engine: 'UnifiedRegimeEngine') -> bool:
        """
        Initialize with L09 Unified Regime Engine (preferred path).

        The unified engine provides consensus-based regime detection from
        multiple sources (ML, signals, HMM, quantitative, attribution),
        giving more robust regime classification than E21 alone.

        Args:
            engine: UnifiedRegimeEngine instance

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if not L09_AVAILABLE:
                self.logger.error("L09 UnifiedRegimeEngine not available")
                return False

            self.unified_engine = engine
            self.logger.info(
                "RegimeGatedSelector initialized with L09 UnifiedRegimeEngine"
            )
            return True

        except Exception as e:
            self.error_handler.handle_error(
                e, "RegimeGatedSelector.initialize_with_unified_engine"
            )
            return False

    def select_strategy_from_consensus(
        self,
        consensus: 'RegimeConsensus',
        force_switch: bool = False,
    ) -> StrategySelection:
        """
        Select optimal strategy from L09 regime consensus.

        Maps the L09 8-state regime taxonomy to D30's 4-state strategy
        categories (BULL/CHOP/CRISIS/UNKNOWN) and delegates to the
        existing strategy selection logic.

        Args:
            consensus: L09 RegimeConsensus result
            force_switch: Force strategy switch regardless of confidence

        Returns:
            StrategySelection with selected strategy
        """
        # Map L09 regime → D30 regime
        regime_map = _get_l09_to_d30_regime_map()
        mapped_regime = regime_map.get(
            consensus.regime, MarketRegime.UNKNOWN
        )

        # Build a RegimePrediction-compatible object for internal reuse
        prediction = RegimePrediction(
            timestamp=consensus.timestamp,
            current_regime=mapped_regime,
            regime_probabilities={mapped_regime: consensus.confidence},
            confidence=consensus.confidence,
            transition_probability=0.0,
            expected_duration=consensus.regime_duration.total_seconds() / 86400,
            reason=f"L09 consensus: {consensus.regime.value} "
                   f"(mapped to {mapped_regime.value})",
        )

        return self.select_strategy(prediction, force_switch=force_switch)

    def select_strategy(self,
                       regime_prediction: RegimePrediction,
                       force_switch: bool = False) -> StrategySelection:
        """
        Select optimal strategy based on regime prediction.

        Args:
            regime_prediction: HMM regime prediction
            force_switch: Force strategy switch regardless of confidence

        Returns:
            StrategySelection with selected strategy
        """
        try:
            self.logger.debug("Selecting strategy based on regime...")

            # Get regime
            regime = regime_prediction.current_regime
            confidence = regime_prediction.confidence

            # Update regime tracking
            if regime != self.current_regime:
                self.current_regime = regime
                self.days_in_regime = 0
            else:
                self.days_in_regime += 1

            # Get regime-strategy mapping
            mapping = REGIME_STRATEGY_MAPPINGS.get(regime)

            if mapping is None:
                # Unknown regime - use neutral
                return self._create_neutral_selection(
                    regime,
                    confidence,
                    "Unknown regime - neutral strategy"
                )

            # Check if confidence meets threshold
            if confidence < self.confidence_threshold and not force_switch:
                # Not confident enough - maintain current strategy
                return self._create_stable_selection(
                    regime,
                    confidence,
                    f"Low confidence ({confidence:.2%}) - maintain current strategy"
                )

            # Check if minimum regime duration met
            if self.days_in_regime < self.min_regime_duration and not force_switch:
                # Haven't been in regime long enough
                return self._create_stable_selection(
                    regime,
                    confidence,
                    f"Regime duration ({self.days_in_regime}d) < minimum ({self.min_regime_duration}d)"  # noqa: E501
                )

            # Get optimal strategy — RL-enhanced or rule-based
            rl_choice = self._rl_select_strategy(regime_prediction)
            if rl_choice is not None:
                optimal_strategy = rl_choice
                # Still respect avoid list from mapping
                if optimal_strategy in mapping.avoid_strategies:
                    self.logger.debug(
                        f"RL chose {optimal_strategy.value} but it's in avoid list — "
                        f"falling back to mapping primary"
                    )
                    optimal_strategy = mapping.primary_strategy
            else:
                optimal_strategy = mapping.primary_strategy

            # Check if strategy change needed
            if optimal_strategy == self.current_strategy:
                # No change needed
                return self._create_stable_selection(
                    regime,
                    confidence,
                    f"Current strategy {self.current_strategy.value} is optimal for {regime.value} regime"  # noqa: E501
                )

            # Strategy change needed - initiate transition
            return self._initiate_transition(
                regime,
                optimal_strategy,
                confidence,
                mapping
            )

        except Exception as e:
            self.error_handler.handle_error(e, "RegimeGatedSelector.select_strategy")
            return self._create_neutral_selection(
                regime_prediction.current_regime,
                0.0,
                f"Error: {str(e)}"
            )

    def _create_stable_selection(self,
                                 regime: MarketRegime,
                                 confidence: float,
                                 reason: str) -> StrategySelection:
        """Create selection for stable state (no change needed)."""
        return StrategySelection(
            timestamp=datetime.now(),
            current_regime=regime,
            selected_strategy=self.current_strategy,
            previous_strategy=self.previous_strategy,
            confidence=confidence,
            transition_state=TransitionState.STABLE,
            transition_progress=1.0,
            reason=reason,
            expected_performance=self._get_expected_performance(self.current_strategy, regime)
        )

    def _create_neutral_selection(self,
                                  regime: MarketRegime,
                                  confidence: float,
                                  reason: str) -> StrategySelection:
        """Create selection for neutral strategy."""
        return StrategySelection(
            timestamp=datetime.now(),
            current_regime=regime,
            selected_strategy=StrategyType.NEUTRAL,
            previous_strategy=self.current_strategy,
            confidence=confidence,
            transition_state=TransitionState.STABLE,
            transition_progress=1.0,
            reason=reason,
            expected_performance=None
        )

    def _initiate_transition(self,
                             regime: MarketRegime,
                             new_strategy: StrategyType,
                             confidence: float,
                             mapping: RegimeStrategyMapping) -> StrategySelection:
        """Initiate transition to new strategy."""
        # Store previous strategy
        self.previous_strategy = self.current_strategy

        # Start transition
        self.transition_state = TransitionState.PREPARING
        self.days_in_transition = 0

        # Get expected performance
        profile = STRATEGY_PROFILES.get(new_strategy)
        expected_performance = {}
        if profile:
            expected_performance = {
                'expected_sharpe': profile.expected_sharpe,
                'max_drawdown': profile.max_drawdown,
                'greek_profile': profile.greek_profile,
                'volatility_preference': profile.volatility_preference
            }

        # Create selection
        selection = StrategySelection(
            timestamp=datetime.now(),
            current_regime=regime,
            selected_strategy=new_strategy,
            previous_strategy=self.previous_strategy,
            confidence=confidence,
            transition_state=self.transition_state,
            transition_progress=0.0,
            reason=f"Switching to {new_strategy.value} for {regime.value} regime",
            expected_performance=expected_performance
        )

        # Store selection
        self.selection_history.append(selection)

        self.logger.info(
            "Initiating transition: %s -> %s", self.current_strategy.value, new_strategy.value
        )

        return selection

    def update_transition(self) -> StrategySelection | None:
        """
        Update transition progress.

        Returns:
            StrategySelection if transition complete, None otherwise
        """
        if self.transition_state == TransitionState.STABLE:
            return None

        # Update transition progress
        self.days_in_transition += 1
        progress = min(1.0, self.days_in_transition / self.transition_period)

        # Check if transition complete
        if progress >= 1.0:
            # Complete transition
            self.current_strategy = self.selection_history[-1].selected_strategy
            self.transition_state = TransitionState.COMPLETED
            self.days_in_transition = 0

            selection = StrategySelection(
                timestamp=datetime.now(),
                current_regime=self.current_regime,
                selected_strategy=self.current_strategy,
                previous_strategy=self.previous_strategy,
                confidence=1.0,
                transition_state=TransitionState.COMPLETED,
                transition_progress=1.0,
                reason=f"Transition complete - now using {self.current_strategy.value}",
                expected_performance=self._get_expected_performance(
                    self.current_strategy,
                    self.current_regime
                )
            )

            self.selection_history.append(selection)

            self.logger.info(
                "Transition complete: %s active", self.current_strategy.value
            )

            return selection
        else:
            # Transition in progress
            return None

    def record_performance(self,
                           strategy_type: StrategyType,
                           regime: MarketRegime,
                           total_trades: int,
                           win_rate: float,
                           avg_return: float,
                           sharpe_ratio: float,
                           max_drawdown: float) -> None:
        """
        Record strategy performance by regime.

        Args:
            strategy_type: Strategy type
            regime: Market regime
            total_trades: Total number of trades
            win_rate: Win rate (0-1)
            avg_return: Average return
            sharpe_ratio: Sharpe ratio
            max_drawdown: Maximum drawdown
        """
        performance = StrategyPerformance(
            strategy_type=strategy_type,
            regime=regime,
            total_trades=total_trades,
            win_rate=win_rate,
            avg_return=avg_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            last_updated=datetime.now()
        )

        self.performance_history[strategy_type].append(performance)

        self.logger.debug(
            "Performance recorded: %s in %s regime", strategy_type.value, regime.value
        )

    def get_strategy_performance(self,
                                 strategy_type: StrategyType,
                                 regime: MarketRegime) -> StrategyPerformance | None:
        """
        Get performance of strategy in specific regime.

        Args:
            strategy_type: Strategy type
            regime: Market regime

        Returns:
            StrategyPerformance if available, None otherwise
        """
        performances = self.performance_history.get(strategy_type, [])

        for perf in performances:
            if perf.regime == regime:
                return perf

        return None

    def _get_expected_performance(self,
                                 strategy_type: StrategyType,
                                 regime: MarketRegime) -> dict[str, float] | None:
        """
        Get expected performance metrics for a strategy in a regime.

        Args:
            strategy_type: Strategy type
            regime: Market regime

        Returns:
            Dictionary with expected performance metrics
        """
        # Get strategy profile
        profile = STRATEGY_PROFILES.get(strategy_type)

        if profile is None:
            return None

        # Check if strategy is optimal for regime
        if regime not in profile.optimal_regimes:
            # Not optimal - reduce expected performance
            expected_sharpe = profile.expected_sharpe * 0.7
        else:
            # Optimal - use full expected performance
            expected_sharpe = profile.expected_sharpe

        return {
            'expected_sharpe': expected_sharpe,
            'max_drawdown': profile.max_drawdown,
            'greek_profile': profile.greek_profile,
            'volatility_preference': profile.volatility_preference
        }

    def get_optimal_strategy(self, regime: MarketRegime) -> StrategyType:
        """
        Get optimal strategy for given regime based on historical performance.

        Args:
            regime: Market regime

        Returns:
            Optimal strategy type
        """
        # Get regime-strategy mapping
        mapping = REGIME_STRATEGY_MAPPINGS.get(regime)

        if mapping is None:
            return StrategyType.NEUTRAL

        # Check historical performance
        candidate_strategies = [mapping.primary_strategy] + mapping.secondary_strategies

        best_strategy = mapping.primary_strategy
        best_sharpe = 0.0

        for strategy in candidate_strategies:
            performance = self.get_strategy_performance(strategy, regime)
            if performance and performance.sharpe_ratio > best_sharpe:
                best_sharpe = performance.sharpe_ratio
                best_strategy = strategy

        return best_strategy

    def get_selection_history(self, periods: int = 30) -> pd.DataFrame:
        """
        Get historical strategy selections.

        Args:
            periods: Number of periods to retrieve

        Returns:
            DataFrame with selection history
        """
        if not self.selection_history:
            return pd.DataFrame()

        history = self.selection_history[-periods:]

        return pd.DataFrame([
            {
                'timestamp': sel.timestamp,
                'regime': sel.current_regime.value,
                'strategy': sel.selected_strategy.value,
                'previous_strategy': sel.previous_strategy.value if sel.previous_strategy else None,
                'confidence': sel.confidence,
                'transition_state': sel.transition_state.value,
                'transition_progress': sel.transition_progress,
                'reason': sel.reason
            }
            for sel in history
        ])

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics on strategy selection.

        Returns:
            Dictionary with statistics
        """
        if not self.selection_history:
            return {}

        # Count strategy usage
        strategy_counts = {}
        for sel in self.selection_history:
            strategy = sel.selected_strategy.value
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        # Count regime occurrences
        regime_counts = {}
        for sel in self.selection_history:
            regime = sel.current_regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        # Calculate transition frequency
        transitions = 0
        for i in range(1, len(self.selection_history)):
            if (self.selection_history[i].selected_strategy !=
                self.selection_history[i-1].selected_strategy):
                transitions += 1

        transition_frequency = transitions / len(self.selection_history) if self.selection_history else 0.0  # noqa: E501

        return {
            'total_selections': len(self.selection_history),
            'current_strategy': self.current_strategy.value,
            'current_regime': self.current_regime.value,
            'days_in_regime': self.days_in_regime,
            'transition_state': self.transition_state.value,
            'strategy_distribution': strategy_counts,
            'regime_distribution': regime_counts,
            'transition_frequency': transition_frequency,
            'hmm_available': HMM_AVAILABLE,
            'l09_available': L09_AVAILABLE,
            'unified_engine_initialized': self.unified_engine is not None,
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sample_regime_predictions(n_predictions: int = 30) -> list[RegimePrediction]:
    """
    Create sample regime predictions for testing.

    Args:
        n_predictions: Number of predictions to generate

    Returns:
        List of RegimePrediction objects
    """
    predictions = []

    # Simulate regime changes
    regimes = [MarketRegime.BULL, MarketRegime.CHOP, MarketRegime.CRISIS]
    current_regime = MarketRegime.BULL

    for i in range(n_predictions):
        # Random regime transition (stickiness)
        if np.random.random() < 0.10:  # 10% chance of regime change
            current_regime = np.random.choice(regimes)

        # Create prediction
        prediction = RegimePrediction(
            timestamp=datetime.now() - timedelta(days=n_predictions - i),
            current_regime=current_regime,
            regime_probabilities={
                MarketRegime.BULL: 0.30 if current_regime != MarketRegime.BULL else 0.70,
                MarketRegime.CHOP: 0.30 if current_regime != MarketRegime.CHOP else 0.60,
                MarketRegime.CRISIS: 0.30 if current_regime != MarketRegime.CRISIS else 0.50,
                MarketRegime.UNKNOWN: 0.01
            },
            confidence=0.70 if current_regime != MarketRegime.UNKNOWN else 0.50,
            transition_probability=0.05,
            expected_duration=5.0,
            recommended_strategy="calendar_spreads" if current_regime == MarketRegime.BULL else "iron_condors",  # noqa: E501
            reason=f"Regime {current_regime.value} detected"
        )

        predictions.append(prediction)

    return predictions


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":

    # Create selector
    selector = RegimeGatedSelector(
        confidence_threshold=0.70,
        min_regime_duration=5,
        transition_period=3
    )

    # Display strategy profiles
    for strategy_type, _profile in STRATEGY_PROFILES.items():
        if strategy_type != StrategyType.NEUTRAL:
            pass

    # Test strategy selection with sample predictions
    predictions = create_sample_regime_predictions(n_predictions=30)

    for _i, prediction in enumerate(predictions[-10:]):
        selection = selector.select_strategy(prediction)


    # Test performance recording
    selector.record_performance(
        strategy_type=StrategyType.CALENDAR_SPREADS,
        regime=MarketRegime.BULL,
        total_trades=50,
        win_rate=0.60,
        avg_return=0.02,
        sharpe_ratio=2.1,
        max_drawdown=0.08
    )

    performance = selector.get_strategy_performance(
        StrategyType.CALENDAR_SPREADS,
        MarketRegime.BULL
    )

    if performance:
        pass

    # Get statistics
    stats = selector.get_statistics()
    for key, _value in stats.items():
        if key not in ['strategy_distribution', 'regime_distribution']:
            pass

