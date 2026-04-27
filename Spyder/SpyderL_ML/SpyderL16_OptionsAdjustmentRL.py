#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL16_OptionsAdjustmentRL.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass
from collections import defaultdict
import json
from pathlib import Path
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# Reinforcement Learning
try:
    import gym
    from gym import spaces
    from stable_baselines3 import PPO, SAC, TD3
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.callbacks import (
        EvalCallback,
        CheckpointCallback,
        CallbackList,
    )
    from stable_baselines3.common.noise import NormalActionNoise
    from stable_baselines3.common.buffers import ReplayBuffer
    HAS_RL = True
except ImportError:
    gym = None
    spaces = None
    PPO = SAC = TD3 = None
    DummyVecEnv = SubprocVecEnv = None
    EvalCallback = CheckpointCallback = CallbackList = None
    NormalActionNoise = None
    ReplayBuffer = None
    HAS_RL = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    torch = None
    nn = None
    F = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402
import logging  # noqa: E402
try:
    from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
except ImportError:
    GreeksCalculator = None
try:
    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager
except ImportError:
    RiskManager = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# RL Training parameters
EPISODES = 1000
STEPS_PER_EPISODE = 252  # Trading days in a year
LEARNING_RATE = 3e-4
BATCH_SIZE = 64
BUFFER_SIZE = 100000
GAMMA = 0.99  # Discount factor

# Reward shaping parameters
PROFIT_WEIGHT = 0.4
RISK_WEIGHT = 0.3
DRAWDOWN_WEIGHT = 0.3

# Position adjustment thresholds
DELTA_THRESHOLD = 0.3
PROFIT_TARGET = 0.5  # 50% of max profit
LOSS_THRESHOLD = -0.2  # 20% loss

# Action definitions
ADJUSTMENT_ACTIONS = [
    "hold",
    "close_position",
    "roll_up",
    "roll_down",
    "roll_out",
    "add_hedge",
    "reduce_size",
    "increase_size",
    "convert_to_iron_condor",
    "convert_to_butterfly",
]


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionState:
    """Current state of an options position"""

    position_type: str
    days_in_trade: int
    dte: int  # Days to expiration
    pnl: float
    pnl_percent: float
    delta: float
    gamma: float
    theta: float
    vega: float
    underlying_price: float
    underlying_change: float
    iv_rank: float
    iv_change: float
    max_profit: float
    max_loss: float
    current_margin: float

    def to_array(self) -> np.ndarray:
        """Convert state to numpy array for RL"""
        return np.array(
            [
                self.days_in_trade / 30,  # Normalize
                self.dte / 45,
                self.pnl_percent,
                self.delta,
                self.gamma,
                self.theta / 100,
                self.vega / 100,
                self.underlying_change,
                self.iv_rank,
                self.iv_change,
                self.pnl / self.max_profit if self.max_profit > 0 else 0,
                self.current_margin / 10000,  # Normalize
            ],
            dtype=np.float32,
        )


@dataclass
class AdjustmentAction:
    """Represents an adjustment action"""

    action_type: str
    parameters: dict[str, Any]
    timestamp: datetime
    reason: str
    confidence: float


@dataclass
class Episode:
    """Single trading episode for RL training"""

    states: list[PositionState]
    actions: list[int]
    rewards: list[float]
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float


# ==============================================================================
# BASE OPTIONS ENVIRONMENT
# ==============================================================================
_GymEnvBase = gym.Env if gym is not None else object


class OptionsEnvironment(_GymEnvBase):
    """
    Base Gym environment for options position management.
    Strategy-specific environments inherit from this.
    """

    def __init__(
        self,
        strategy_type: str,
        historical_data: pd.DataFrame,
        risk_free_rate: float = 0.05,
    ):
        super().__init__()

        self.strategy_type = strategy_type
        self.historical_data = historical_data
        self.risk_free_rate = risk_free_rate

        # Components
        if GreeksCalculator is None:
            raise ImportError(
                "GreeksCalculator unavailable — check SpyderF06_GreeksCalculator imports"
            )
        if RiskManager is None:
            raise ImportError(
                "RiskManager unavailable — check SpyderE01_RiskManager imports"
            )
        self.greeks_calculator = GreeksCalculator()
        self.risk_manager = RiskManager()

        # Episode tracking
        self.current_step = 0
        self.current_position = None
        self.episode_history = []

        # Define action and observation spaces
        self.action_space = spaces.Discrete(len(ADJUSTMENT_ACTIONS))
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(12,), dtype=np.float32
        )

        # Logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

    def reset(self) -> np.ndarray:
        """Reset environment for new episode"""
        # Random starting point in historical data
        start_idx = np.random.randint(0, len(self.historical_data) - STEPS_PER_EPISODE)
        self.data_slice = self.historical_data.iloc[
            start_idx : start_idx + STEPS_PER_EPISODE
        ]

        # Initialize position
        self.current_step = 0
        self.current_position = self._initialize_position()
        self.episode_history = []

        # Get initial state
        state = self._get_state()
        return state.to_array()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict]:
        """Execute action and return new state"""
        # Execute adjustment
        adjustment_result = self._execute_adjustment(action)

        # Update position
        self.current_step += 1
        self._update_position()

        # Get new state
        new_state = self._get_state()

        # Calculate reward
        reward = self._calculate_reward(adjustment_result)

        # Check if episode is done
        done = (
            self.current_step >= STEPS_PER_EPISODE
            or self.current_position is None
            or self._should_force_close()
        )

        # Additional info
        info = {
            "action": ADJUSTMENT_ACTIONS[action],
            "pnl": new_state.pnl,
            "position_closed": self.current_position is None,
        }

        # Record history
        self.episode_history.append(
            {
                "step": self.current_step,
                "state": new_state,
                "action": action,
                "reward": reward,
            }
        )

        return new_state.to_array(), reward, done, info

    def _initialize_position(self) -> dict[str, Any]:
        """Initialize a new options position.

        A15 (v14): Safe no-op default — L16 is reached only through T111 tests
        and the L_ML ``__init__`` shim. Returning an empty dict lets a
        mis-wired caller fail gracefully rather than crash.
        """
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._initialize_position() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _get_state(self) -> PositionState:
        """Get current position state"""
        if self.current_position is None:
            # Return terminal state
            return PositionState(
                position_type=self.strategy_type,
                days_in_trade=self.current_step,
                dte=0,
                pnl=0,
                pnl_percent=0,
                delta=0,
                gamma=0,
                theta=0,
                vega=0,
                underlying_price=self.data_slice.iloc[self.current_step]["close"],
                underlying_change=0,
                iv_rank=0.5,
                iv_change=0,
                max_profit=0,
                max_loss=0,
                current_margin=0,
            )

        # Get current market data
        current_data = self.data_slice.iloc[self.current_step]

        # Calculate position Greeks
        greeks = self._calculate_position_greeks()

        # Calculate P&L
        pnl = self._calculate_pnl()
        pnl_percent = pnl / self.current_position["initial_credit"]

        return PositionState(
            position_type=self.strategy_type,
            days_in_trade=self.current_step,
            dte=self.current_position["dte"] - self.current_step,
            pnl=pnl,
            pnl_percent=pnl_percent,
            delta=greeks["delta"],
            gamma=greeks["gamma"],
            theta=greeks["theta"],
            vega=greeks["vega"],
            underlying_price=current_data["close"],
            underlying_change=(
                current_data["close"] - self.current_position["entry_price"]
            )
            / self.current_position["entry_price"],
            iv_rank=current_data.get("iv_rank", 0.5),
            iv_change=current_data.get("iv_change", 0),
            max_profit=self.current_position["max_profit"],
            max_loss=self.current_position["max_loss"],
            current_margin=self.current_position.get("margin", 0),
        )

    def _execute_adjustment(self, action: int) -> dict[str, Any]:
        """Execute the selected adjustment action"""
        action_name = ADJUSTMENT_ACTIONS[action]
        result = {"success": False, "cost": 0, "description": ""}

        if self.current_position is None:
            return result

        if action_name == "hold":
            result["success"] = True
            result["description"] = "Hold position"

        elif action_name == "close_position":
            result["cost"] = self._calculate_closing_cost()
            self.current_position = None
            result["success"] = True
            result["description"] = "Position closed"

        elif action_name == "roll_up":
            result = self._roll_position("up")

        elif action_name == "roll_down":
            result = self._roll_position("down")

        elif action_name == "roll_out":
            result = self._roll_position("out")

        elif action_name == "add_hedge":
            result = self._add_hedge()

        elif action_name in ["reduce_size", "increase_size"]:
            result = self._adjust_size(action_name)

        elif action_name.startswith("convert_to_"):
            result = self._convert_position(action_name.replace("convert_to_", ""))

        return result

    def _calculate_reward(self, adjustment_result: dict[str, Any]) -> float:
        """
        Calculate reward using risk-adjusted metrics.
        Multi-objective: profit, risk reduction, drawdown minimization.
        """
        state = self._get_state()

        # Base reward components
        profit_component = state.pnl_percent * PROFIT_WEIGHT

        # Risk component (lower is better)
        risk_component = -abs(state.delta) * RISK_WEIGHT

        # Drawdown component
        if hasattr(self, "max_equity"):
            current_equity = self.current_position["initial_credit"] + state.pnl
            drawdown = (self.max_equity - current_equity) / self.max_equity
            drawdown_component = -drawdown * DRAWDOWN_WEIGHT
        else:
            drawdown_component = 0
            self.max_equity = self.current_position["initial_credit"]

        # Adjustment cost penalty
        cost_penalty = -adjustment_result["cost"] / 1000  # Normalize

        # Time decay bonus for profitable positions
        time_bonus = 0
        if state.pnl_percent > 0 and state.dte < 10:
            time_bonus = 0.1  # Encourage closing profitable positions near expiry

        # Combine components
        reward = (
            profit_component
            + risk_component
            + drawdown_component
            + cost_penalty
            + time_bonus
        )

        # Clip reward to prevent instability
        return np.clip(reward, -1.0, 1.0)

    def _should_force_close(self) -> bool:
        """Check if position should be force closed"""
        state = self._get_state()

        # Force close conditions
        if state.pnl_percent < LOSS_THRESHOLD:
            return True
        if state.dte <= 0:
            return True
        return abs(state.delta) > 0.8  # Position too directional

    # A15 (v14): Abstract methods — subclasses override. Defaults return safe
    # no-ops (empty dict / 0.0) plus a one-line warning so mis-wiring surfaces
    # without crashing runtime callers.
    def _calculate_position_greeks(self) -> dict[str, float]:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._calculate_position_greeks() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _calculate_pnl(self) -> float:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._calculate_pnl() default hit on %s",
            type(self).__name__,
        )
        return 0.0

    def _calculate_closing_cost(self) -> float:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._calculate_closing_cost() default hit on %s",
            type(self).__name__,
        )
        return 0.0

    def _roll_position(self, direction: str) -> dict[str, Any]:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._roll_position() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _add_hedge(self) -> dict[str, Any]:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._add_hedge() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _adjust_size(self, direction: str) -> dict[str, Any]:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._adjust_size() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _convert_position(self, new_type: str) -> dict[str, Any]:
        import logging
        logging.getLogger(__name__).warning(
            "OptionsAdjustmentEnv._convert_position() default hit on %s",
            type(self).__name__,
        )
        return {}

    def _update_position(self):
        """Update position based on market movement"""
        # Update days to expiration
        if self.current_position:
            self.current_position["dte"] -= 1


# ==============================================================================
# IRON CONDOR ENVIRONMENT
# ==============================================================================
class IronCondorEnvironment(OptionsEnvironment):
    """Gym environment specifically for Iron Condor adjustments"""

    def _initialize_position(self) -> dict[str, Any]:
        """Initialize an Iron Condor position"""
        current_price = self.data_slice.iloc[0]["close"]
        iv = self.data_slice.iloc[0].get("implied_volatility", 0.20)

        # Calculate strikes (simplified)
        put_short = current_price * 0.95
        put_long = current_price * 0.90
        call_short = current_price * 1.05
        call_long = current_price * 1.10

        position = {
            "type": "iron_condor",
            "entry_price": current_price,
            "entry_iv": iv,
            "dte": 45,
            "legs": {
                "put_short": {"strike": put_short, "quantity": -1},
                "put_long": {"strike": put_long, "quantity": 1},
                "call_short": {"strike": call_short, "quantity": -1},
                "call_long": {"strike": call_long, "quantity": 1},
            },
            "initial_credit": 2.50,  # Simplified
            "max_profit": 2.50,
            "max_loss": 2.50,  # Width - credit
            "margin": 500,
        }

        return position

    def _calculate_position_greeks(self) -> dict[str, float]:
        """Calculate aggregate Greeks for Iron Condor"""
        if not self.current_position:
            return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}

        current_data = self.data_slice.iloc[self.current_step]
        spot = current_data["close"]
        dte_years = self.current_position["dte"] / 365.0
        iv = current_data.get("implied_volatility", 0.20)

        total_greeks = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}

        for leg_name, leg_data in self.current_position["legs"].items():
            option_type = "put" if "put" in leg_name else "call"

            greeks = self.greeks_calculator.calculate_greeks(
                spot=spot,
                strike=leg_data["strike"],
                time_to_expiry=dte_years,
                volatility=iv,
                risk_free_rate=self.risk_free_rate,
                option_type=option_type,
            )

            # Aggregate (multiply by quantity for short positions)
            for greek in total_greeks:
                total_greeks[greek] += greeks[greek] * leg_data["quantity"]

        return total_greeks

    def _calculate_pnl(self) -> float:
        """Calculate current P&L for Iron Condor"""
        if not self.current_position:
            return 0.0

        # Simplified P&L calculation
        current_data = self.data_slice.iloc[self.current_step]
        spot = current_data["close"]

        # Check if price is within short strikes
        put_short = self.current_position["legs"]["put_short"]["strike"]
        call_short = self.current_position["legs"]["call_short"]["strike"]

        if put_short <= spot <= call_short:
            # Max profit scenario (simplified)
            time_decay = self.current_position["initial_credit"] * (
                1 - self.current_position["dte"] / 45
            )
            return time_decay
        else:
            # Calculate intrinsic value loss
            if spot < put_short:
                loss = (put_short - spot) - (
                    put_short - self.current_position["legs"]["put_long"]["strike"]
                )
            else:
                loss = (spot - call_short) - (
                    self.current_position["legs"]["call_long"]["strike"] - call_short
                )

            return self.current_position["initial_credit"] - loss

    def _roll_position(self, direction: str) -> dict[str, Any]:
        """Roll Iron Condor strikes"""
        result = {"success": False, "cost": 0.5, "description": ""}

        if direction == "up":
            # Roll up the put side
            for leg in ["put_short", "put_long"]:
                self.current_position["legs"][leg]["strike"] *= 1.02
            result["success"] = True
            result["description"] = "Rolled put side up"

        elif direction == "down":
            # Roll down the call side
            for leg in ["call_short", "call_long"]:
                self.current_position["legs"][leg]["strike"] *= 0.98
            result["success"] = True
            result["description"] = "Rolled call side down"

        elif direction == "out":
            # Roll out in time
            self.current_position["dte"] += 30
            result["cost"] = 1.0
            result["success"] = True
            result["description"] = "Rolled out 30 days"

        return result

    def _add_hedge(self) -> dict[str, Any]:
        """Add protective hedge to Iron Condor"""
        # Buy additional long option for protection
        current_data = self.data_slice.iloc[self.current_step]
        spot = current_data["close"]

        result = {"success": True, "cost": 1.0, "description": ""}

        # Determine which side needs protection
        put_short = self.current_position["legs"]["put_short"]["strike"]
        call_short = self.current_position["legs"]["call_short"]["strike"]

        if abs(spot - put_short) < abs(spot - call_short):
            # Add put protection
            result["description"] = "Added put hedge"
        else:
            # Add call protection
            result["description"] = "Added call hedge"

        return result

    def _calculate_closing_cost(self) -> float:
        """Calculate cost to close Iron Condor"""
        # Simplified - in reality would calculate current option values
        state = self._get_state()
        return max(0, -state.pnl) + 0.10  # Add commission

    def _adjust_size(self, direction: str) -> dict[str, Any]:
        """Adjust position size"""
        result = {"success": True, "cost": 0.20, "description": ""}

        if direction == "reduce_size":
            # Close part of position
            for leg in self.current_position["legs"].values():
                leg["quantity"] *= 0.5
            result["description"] = "Reduced position by 50%"
        else:
            # Increase size (if margin allows)
            for leg in self.current_position["legs"].values():
                leg["quantity"] *= 1.5
            result["cost"] = 0.40
            result["description"] = "Increased position by 50%"

        return result

    def _convert_position(self, new_type: str) -> dict[str, Any]:
        """Convert Iron Condor to different strategy"""
        result = {"success": False, "cost": 1.0, "description": ""}

        if new_type == "butterfly":
            # Convert to Iron Butterfly by moving short strikes to ATM
            current_price = self.data_slice.iloc[self.current_step]["close"]
            self.current_position["legs"]["put_short"]["strike"] = current_price
            self.current_position["legs"]["call_short"]["strike"] = current_price
            result["success"] = True
            result["description"] = "Converted to Iron Butterfly"

        return result


# ==============================================================================
# SPY OPTIONS ENVIRONMENT — live analytics wiring
# ==============================================================================
class SPYOptionsEnvironment(OptionsEnvironment):
    """
    Concrete options environment for SPY positions wired to live analytics.

    Implements all 7 abstract methods using:
    - SpyderN04_OptionsGreeksCalculator for real Greeks
    - SpyderP01_PortfolioManager for live P&L lookup
    - SpyderD14_CalendarSpread roll logic for position rolling

    Args:
        strategy_type: Options strategy type (e.g. 'iron_condor', 'credit_spread').
        historical_data: DataFrame with columns close, implied_volatility, iv_rank, volume.
        risk_free_rate: Annual risk-free rate used in BSM pricing (default 0.05).
        portfolio_manager: Optional SpyderP01 PortfolioManager instance for live P&L.
        greeks_engine: Optional SpyderN04 OptionsGreeksCalculator instance.
    """

    def __init__(
        self,
        strategy_type: str,
        historical_data: pd.DataFrame,
        risk_free_rate: float = 0.05,
        portfolio_manager: Any = None,
        greeks_engine: Any = None,
    ):
        super().__init__(strategy_type, historical_data, risk_free_rate)
        # Prefer injected instances; fall back to local greeks_calculator from base
        self._portfolio_manager = portfolio_manager
        self._greeks_engine = greeks_engine  # SpyderN04

        # Try to import live analytics modules lazily
        if self._greeks_engine is None:
            try:
                from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
                    OptionsGreeksCalculator,
                )
                self._greeks_engine = OptionsGreeksCalculator()
            except Exception:
                self._greeks_engine = None  # falls back to base greeks_calculator

        if self._portfolio_manager is None:
            try:
                from Spyder.SpyderP_PortfolioMgmt.SpyderP01_PortfolioManager import (
                    get_portfolio_manager,
                )
                self._portfolio_manager = get_portfolio_manager()
            except Exception:
                self._portfolio_manager = None

    # ------------------------------------------------------------------
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ------------------------------------------------------------------

    def _initialize_position(self) -> dict[str, Any]:
        """
        Initialise a SPY position using current market data snapshot.

        Builds a position dictionary compatible with the base _get_state() method.
        For iron_condor/credit_spread the strikes are placed at ±1σ from spot using
        the IV from the first row of the current data slice.
        """
        row = self.data_slice.iloc[0]
        spot: float = float(row["close"])
        iv: float = float(row.get("implied_volatility", 0.20))
        dte: int = 45  # Standard entry DTE

        # 1-σ move over DTE (simplified)
        one_sigma = spot * iv * (dte / 365.0) ** 0.5

        if self.strategy_type in ("iron_condor", "iron_butterfly"):
            put_short = round(spot - one_sigma * 0.5, 2)
            put_long = round(spot - one_sigma, 2)
            call_short = round(spot + one_sigma * 0.5, 2)
            call_long = round(spot + one_sigma, 2)
            spread_width = call_long - call_short
            initial_credit = round(spread_width * 0.35, 2)  # ~35% of width
            return {
                "type": self.strategy_type,
                "entry_price": spot,
                "entry_iv": iv,
                "dte": dte,
                "legs": {
                    "put_short": {"strike": put_short, "qty": -1, "option_type": "put"},
                    "put_long": {"strike": put_long, "qty": 1, "option_type": "put"},
                    "call_short": {"strike": call_short, "qty": -1, "option_type": "call"},
                    "call_long": {"strike": call_long, "qty": 1, "option_type": "call"},
                },
                "initial_credit": initial_credit,
                "max_profit": initial_credit,
                "max_loss": round(spread_width - initial_credit, 2),
                "margin": round((spread_width - initial_credit) * 100, 2),
            }

        # Fallback: simple short put credit spread (bull put)
        put_short = round(spot - one_sigma * 0.5, 2)
        put_long = round(spot - one_sigma, 2)
        spread_width = put_short - put_long
        initial_credit = round(spread_width * 0.35, 2)
        return {
            "type": "credit_spread",
            "entry_price": spot,
            "entry_iv": iv,
            "dte": dte,
            "legs": {
                "put_short": {"strike": put_short, "qty": -1, "option_type": "put"},
                "put_long": {"strike": put_long, "qty": 1, "option_type": "put"},
            },
            "initial_credit": initial_credit,
            "max_profit": initial_credit,
            "max_loss": round(spread_width - initial_credit, 2),
            "margin": round((spread_width - initial_credit) * 100, 2),
        }

    def _calculate_position_greeks(self) -> dict[str, float]:
        """
        Aggregate Greeks across all legs using SpyderN04 or F06 fallback.

        Returns:
            dict with keys delta, gamma, theta, vega (portfolio-level, signed).
        """
        if not self.current_position:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        row = self.data_slice.iloc[self.current_step]
        spot: float = float(row["close"])
        iv: float = float(row.get("implied_volatility", self.current_position["entry_iv"]))
        dte_remaining = max(1, self.current_position["dte"] - self.current_step)
        t = dte_remaining / 365.0

        totals: dict[str, float] = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        for leg in self.current_position["legs"].values():
            strike: float = float(leg["strike"])
            qty: float = float(leg.get("qty", leg.get("quantity", 1)))
            opt_type: str = leg.get("option_type", "call")

            try:
                if self._greeks_engine is not None and hasattr(
                    self._greeks_engine, "calculate_greeks"
                ):
                    g = self._greeks_engine.calculate_greeks(
                        spot=spot,
                        strike=strike,
                        time_to_expiry=t,
                        volatility=iv,
                        risk_free_rate=self.risk_free_rate,
                        option_type=opt_type,
                    )
                else:
                    # Fall back to base class greeks_calculator (F06)
                    g = self.greeks_calculator.calculate_greeks(
                        spot=spot,
                        strike=strike,
                        time_to_expiry=t,
                        volatility=iv,
                        risk_free_rate=self.risk_free_rate,
                        option_type=opt_type,
                    )
                for k in totals:
                    totals[k] += g.get(k, 0.0) * qty
            except Exception as e:
                self.logger.debug("_calculate_position_greeks leg error: %s", e)

        return totals

    def _calculate_pnl(self) -> float:
        """
        Calculate current unrealised P&L.

        Attempts to delegate to PortfolioManager; falls back to simplified
        Black-Scholes mark-to-market if unavailable.
        """
        if not self.current_position:
            return 0.0

        # Try PortfolioManager live P&L
        if self._portfolio_manager is not None:
            try:
                pos_id = self.current_position.get("position_id")
                if pos_id:
                    pnl = self._portfolio_manager.get_position_pnl(pos_id)
                    if pnl is not None:
                        return float(pnl)
            except Exception as e:
                self.logger.debug("_calculate_pnl portfolio_manager error: %s", e)

        # Fallback: simplified mark via BSM delta approximation
        row = self.data_slice.iloc[self.current_step]
        spot = float(row["close"])
        entry_spot = self.current_position["entry_price"]
        greeks = self._calculate_position_greeks()
        # First-order approximation: ΔP ≈ delta × ΔS
        delta_s = spot - entry_spot
        approx_pnl = greeks["delta"] * delta_s + self.current_position["initial_credit"]
        return float(np.clip(approx_pnl, -self.current_position["max_loss"],
                             self.current_position["max_profit"]))

    def _calculate_closing_cost(self) -> float:
        """
        Estimate cost to close the entire position (slippage + commissions).

        Uses 1 tick ($0.01) slippage per leg × contract × 100 multiplier,
        plus $0.65 per-leg commission (standard retail rate).
        """
        if not self.current_position:
            return 0.0

        n_legs = len(self.current_position["legs"])
        commission_per_leg = 0.65
        slippage_per_leg = 0.05  # $0.05 per contract
        cost = n_legs * (commission_per_leg + slippage_per_leg)

        # Add intrinsic value of any ITM legs
        row = self.data_slice.iloc[self.current_step]
        spot = float(row["close"])
        for leg in self.current_position["legs"].values():
            strike = float(leg["strike"])
            qty = float(leg.get("qty", leg.get("quantity", 1)))
            opt_type = leg.get("option_type", "call")
            intrinsic = max(0.0, spot - strike) if opt_type == "call" else max(0.0, strike - spot)
            cost += abs(qty) * intrinsic
        return round(cost, 2)

    def _roll_position(self, direction: str) -> dict[str, Any]:
        """
        Roll position strikes or expiration using D14 CalendarSpread roll logic.

        Args:
            direction: 'up' | 'down' | 'out' (extend DTE).

        Returns:
            dict with success, cost, description.
        """
        result: dict[str, Any] = {"success": False, "cost": 0.0, "description": ""}
        if not self.current_position:
            return result

        row = self.data_slice.iloc[self.current_step]
        spot = float(row["close"])
        iv = float(row.get("implied_volatility", self.current_position["entry_iv"]))

        # Try to delegate to D14 roll logic
        try:
            from Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread import CalendarSpread
            # D14 exposes a static helper for roll cost estimation
            roll_cost = getattr(CalendarSpread, "estimate_roll_cost", None)
            if roll_cost is not None:
                result["cost"] = float(roll_cost(iv=iv, dte=self.current_position["dte"]))
        except Exception as e:
            self.logger.debug("_roll_position D14 import error: %s", e)
            result["cost"] = round(iv * spot * 0.002, 2)  # Fallback: 0.2% of notional

        shift = spot * 0.02  # 2% strike shift

        if direction == "up":
            for leg in self.current_position["legs"].values():
                leg["strike"] = round(float(leg["strike"]) + shift, 2)
            result.update({"success": True, "description": "Rolled all strikes up 2%"})

        elif direction == "down":
            for leg in self.current_position["legs"].values():
                leg["strike"] = round(float(leg["strike"]) - shift, 2)
            result.update({"success": True, "description": "Rolled all strikes down 2%"})

        elif direction == "out":
            extension = 21  # Roll 3 weeks out
            self.current_position["dte"] += extension
            result.update({
                "success": True,
                "cost": result["cost"] * 1.5,  # Rolling in time costs more
                "description": f"Rolled expiration out {extension} days",
            })

        return result

    def _add_hedge(self) -> dict[str, Any]:
        """
        Add a protective OTM option as a hedge against directional risk.

        Selects put or call hedge based on current net delta exposure.
        Cost is estimated using IV and distance from spot.
        """
        result: dict[str, Any] = {"success": False, "cost": 0.0, "description": ""}
        if not self.current_position:
            return result

        greeks = self._calculate_position_greeks()
        row = self.data_slice.iloc[self.current_step]
        spot = float(row["close"])
        iv = float(row.get("implied_volatility", self.current_position["entry_iv"]))

        # Determine hedge direction from net delta
        if greeks["delta"] > 0.20:
            # Long delta → buy protective put
            hedge_strike = round(spot * 0.97, 2)
            hedge_cost = round(spot * iv * 0.01, 2)  # ~1% of notional
            self.current_position["legs"]["hedge_put"] = {
                "strike": hedge_strike, "qty": 1, "option_type": "put",
            }
            result.update({
                "success": True, "cost": hedge_cost,
                "description": f"Added protective put hedge at {hedge_strike:.2f}",
            })
        elif greeks["delta"] < -0.20:
            # Short delta → buy protective call
            hedge_strike = round(spot * 1.03, 2)
            hedge_cost = round(spot * iv * 0.01, 2)
            self.current_position["legs"]["hedge_call"] = {
                "strike": hedge_strike, "qty": 1, "option_type": "call",
            }
            result.update({
                "success": True, "cost": hedge_cost,
                "description": f"Added protective call hedge at {hedge_strike:.2f}",
            })
        else:
            result.update({"success": True, "cost": 0.0, "description": "Delta neutral — no hedge needed"})  # noqa: E501

        return result

    def _adjust_size(self, direction: str) -> dict[str, Any]:
        """
        Scale position size up or down by 50%.

        Args:
            direction: 'reduce_size' or 'increase_size'.

        Returns:
            dict with success, cost, description.
        """
        result: dict[str, Any] = {"success": False, "cost": 0.0, "description": ""}
        if not self.current_position:
            return result

        factor = 0.5 if direction == "reduce_size" else 1.5
        for leg in self.current_position["legs"].values():
            qty_key = "qty" if "qty" in leg else "quantity"
            leg[qty_key] = round(float(leg[qty_key]) * factor, 4)

        # Commission cost proportional to legs touched
        n_legs = len(self.current_position["legs"])
        result.update({
            "success": True,
            "cost": round(n_legs * 0.65, 2),
            "description": f"{'Reduced' if factor < 1 else 'Increased'} position size by {abs(factor - 1) * 100:.0f}%",  # noqa: E501
        })
        return result

    def _convert_position(self, new_type: str) -> dict[str, Any]:
        """
        Convert the current position structure to a different options strategy.

        Supported targets: 'iron_condor', 'butterfly', 'credit_spread'.

        Args:
            new_type: Target strategy name.

        Returns:
            dict with success, cost, description.
        """
        result: dict[str, Any] = {"success": False, "cost": 0.0, "description": ""}
        if not self.current_position:
            return result

        row = self.data_slice.iloc[self.current_step]
        spot = float(row["close"])
        iv = float(row.get("implied_volatility", self.current_position["entry_iv"]))
        dte = max(1, self.current_position["dte"] - self.current_step)
        one_sigma = spot * iv * (dte / 365.0) ** 0.5
        conversion_cost = round(self._calculate_closing_cost() * 0.5, 2)

        if new_type == "butterfly":
            # Collapse short strikes to ATM
            atm = round(spot, 2)
            for leg_name in list(self.current_position["legs"].keys()):
                if "short" in leg_name:
                    self.current_position["legs"][leg_name]["strike"] = atm
            self.current_position["type"] = "iron_butterfly"
            result.update({
                "success": True, "cost": conversion_cost,
                "description": f"Converted to Iron Butterfly with ATM strike {atm:.2f}",
            })

        elif new_type == "iron_condor":
            # Widen to full iron condor from current structure
            put_short = round(spot - one_sigma * 0.5, 2)
            call_short = round(spot + one_sigma * 0.5, 2)
            if "put_short" in self.current_position["legs"]:
                self.current_position["legs"]["put_short"]["strike"] = put_short
            if "call_short" in self.current_position["legs"]:
                self.current_position["legs"]["call_short"]["strike"] = call_short
            self.current_position["type"] = "iron_condor"
            result.update({
                "success": True, "cost": conversion_cost,
                "description": "Converted to Iron Condor (widened to ±0.5σ short strikes)",
            })

        elif new_type == "credit_spread":
            # Keep only the put spread (most common simplification)
            legs = self.current_position["legs"]
            for key in [k for k in list(legs.keys()) if "call" in k]:
                del legs[key]
            self.current_position["type"] = "credit_spread"
            result.update({
                "success": True, "cost": conversion_cost,
                "description": "Converted to bull put credit spread (removed call legs)",
            })

        return result


# ==============================================================================
# ENSEMBLE RL AGENT
# ==============================================================================
class OptionsAdjustmentRL:
    """
    Ensemble RL agent for options position adjustment.
    Manages multiple RL models for different strategies.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the RL adjustment system"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # RL Models
        self.models = {}
        self.environments = {}

        # Training history
        self.training_history = defaultdict(list)
        self.best_models = {}

        # Initialize components
        self._initialize_environments()
        self._initialize_models()

        self.logger.info("✅ Options Adjustment RL system initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================

    def _initialize_environments(self):
        """Initialize strategy-specific environments"""
        # Load historical data (mock for example)
        historical_data = self._load_historical_data()

        # Create environments
        self.environments["iron_condor"] = IronCondorEnvironment(
            strategy_type="iron_condor", historical_data=historical_data
        )

        # Wrap in vectorized environment for parallel training
        # Use default argument to bind `env` at definition time, avoiding the
        # classic Python closure-over-loop-variable bug.
        self.vec_environments = {
            strategy: DummyVecEnv([lambda e=env: e])
            for strategy, env in self.environments.items()
        }

        self.logger.info("Initialized %s strategy environments", len(self.environments))

    def _initialize_models(self):
        """Initialize RL models for each strategy"""
        for strategy in self.environments:
            # PPO for discrete adjustments
            self.models[f"{strategy}_ppo"] = PPO(
                "MlpPolicy",
                self.vec_environments[strategy],
                learning_rate=LEARNING_RATE,
                n_steps=2048,
                batch_size=BATCH_SIZE,
                n_epochs=10,
                gamma=GAMMA,
                verbose=0,
                tensorboard_log=f"./tensorboard/{strategy}_ppo/",
            )

            # SAC for continuous adjustments (if needed)
            # self.models[f"{strategy}_sac"] = SAC(...)

        self.logger.info("Initialized %s RL models", len(self.models))

    def _load_historical_data(self) -> pd.DataFrame:
        """Load historical market data for training"""
        # Mock data for example
        dates = pd.date_range(start="2020-01-01", end="2024-12-31", freq="D")
        data = pd.DataFrame(
            {
                "date": dates,
                "close": 400 + np.cumsum(np.random.randn(len(dates)) * 2),
                "volume": np.random.randint(1000000, 5000000, len(dates)),
                "implied_volatility": 0.15 + np.random.randn(len(dates)) * 0.05,
                "iv_rank": np.random.uniform(0, 1, len(dates)),
                "iv_change": np.random.randn(len(dates)) * 0.02,
            }
        )

        # Ensure positive prices
        data["close"] = data["close"].clip(lower=100)
        data["implied_volatility"] = data["implied_volatility"].clip(0.05, 0.80)

        return data

    # ==========================================================================
    # TRAINING
    # ==========================================================================

    def train(
        self, strategy: str, episodes: int = EPISODES, save_freq: int = 100
    ) -> dict[str, Any]:
        """
        Train RL model for specific strategy.

        Args:
            strategy: Strategy type to train
            episodes: Number of training episodes
            save_freq: Frequency to save checkpoints

        Returns:
            Training results and metrics
        """
        try:
            self.logger.info("Starting training for %s strategy...", strategy)

            model_name = f"{strategy}_ppo"
            model = self.models[model_name]

            # Setup callbacks
            eval_callback = EvalCallback(
                self.vec_environments[strategy],
                best_model_save_path=f"./models/{model_name}/",
                log_path=f"./logs/{model_name}/",
                eval_freq=save_freq * STEPS_PER_EPISODE,
                deterministic=True,
                render=False,
            )

            checkpoint_callback = CheckpointCallback(
                save_freq=save_freq * STEPS_PER_EPISODE,
                save_path=f"./checkpoints/{model_name}/",
                name_prefix=model_name,
            )

            callbacks = CallbackList([eval_callback, checkpoint_callback])

            # Train model
            total_timesteps = episodes * STEPS_PER_EPISODE
            model.learn(
                total_timesteps=total_timesteps, callback=callbacks, progress_bar=True
            )

            # Save final model
            model.save(f"./models/{model_name}_final")

            # Evaluate final performance
            eval_results = self._evaluate_model(model, strategy)

            # Update best model if improved
            if self._is_best_model(strategy, eval_results):
                self.best_models[strategy] = model
                self.logger.info(
                    f"New best model for {strategy}: Sharpe={eval_results['sharpe_ratio']:.3f}"
                )

            return {
                "strategy": strategy,
                "episodes_trained": episodes,
                "final_performance": eval_results,
                "training_time": datetime.now(timezone.utc),
            }

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "train", "strategy": strategy}
            )
            return {}

    def _evaluate_model(
        self, model: PPO, strategy: str, num_episodes: int = 10
    ) -> dict[str, float]:
        """Evaluate model performance"""
        env = self.environments[strategy]

        episode_returns = []
        episode_lengths = []
        episode_metrics = []

        for _ in range(num_episodes):
            obs = env.reset()
            episode_return = 0
            episode_length = 0
            done = False

            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, done, info = env.step(action)
                episode_return += reward
                episode_length += 1

            episode_returns.append(episode_return)
            episode_lengths.append(episode_length)

            # Calculate episode metrics
            if hasattr(env, "episode_history"):
                metrics = self._calculate_episode_metrics(env.episode_history)
                episode_metrics.append(metrics)

        # Aggregate results
        return {
            "mean_return": np.mean(episode_returns),
            "std_return": np.std(episode_returns),
            "mean_length": np.mean(episode_lengths),
            "sharpe_ratio": np.mean([m.get("sharpe", 0) for m in episode_metrics]),
            "win_rate": np.mean([m.get("win_rate", 0) for m in episode_metrics]),
            "max_drawdown": np.mean(
                [m.get("max_drawdown", 0) for m in episode_metrics]
            ),
        }

    def _calculate_episode_metrics(self, history: list[dict]) -> dict[str, float]:
        """Calculate performance metrics for an episode"""
        if not history:
            return {}

        # Extract P&L series
        pnls = [h["state"].pnl for h in history]
        returns = np.diff(pnls)

        # Calculate metrics
        metrics = {
            "total_return": pnls[-1] if pnls else 0,
            "win_rate": np.mean(returns > 0) if len(returns) > 0 else 0,
            "sharpe": self._calculate_sharpe(returns) if len(returns) > 0 else 0,
            "max_drawdown": self._calculate_max_drawdown(pnls) if pnls else 0,
        }

        return metrics

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0 or np.std(returns) == 0:
            return 0.0
        return np.sqrt(252) * np.mean(returns) / np.std(returns)

    def _calculate_max_drawdown(self, pnls: list[float]) -> float:
        """Calculate maximum drawdown"""
        peak = pnls[0]
        max_dd = 0

        for pnl in pnls:
            if pnl > peak:
                peak = pnl
            dd = (peak - pnl) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _is_best_model(self, strategy: str, metrics: dict[str, float]) -> bool:
        """Check if model is best so far"""
        if strategy not in self.best_models:
            return True

        # Compare Sharpe ratios
        current_best = (
            self.training_history[strategy][-1]["sharpe_ratio"]
            if self.training_history[strategy]
            else 0
        )
        return metrics["sharpe_ratio"] > current_best

    # ==========================================================================
    # PREDICTION AND EXECUTION
    # ==========================================================================

    def get_adjustment_recommendation(
        self, position: dict[str, Any], market_data: dict[str, Any]
    ) -> AdjustmentAction:
        """
        Get adjustment recommendation for current position.

        Args:
            position: Current position details
            market_data: Current market conditions

        Returns:
            Recommended adjustment action
        """
        try:
            strategy = position["type"]

            # Get best model for strategy
            model = self.best_models.get(strategy)
            if not model:
                model = self.models.get(f"{strategy}_ppo")

            if not model:
                return AdjustmentAction(
                    action_type="hold",
                    parameters={},
                    timestamp=datetime.now(timezone.utc),
                    reason="No trained model available",
                    confidence=0.0,
                )

            # Create state from current position
            state = self._create_state_from_position(position, market_data)

            # Get model prediction
            action, _ = model.predict(state.to_array(), deterministic=True)
            action_name = ADJUSTMENT_ACTIONS[action]

            # Calculate confidence based on action probabilities
            if hasattr(model, "policy"):
                with torch.no_grad():
                    obs_tensor = (
                        torch.tensor(state.to_array()).unsqueeze(0).to(self.device)
                    )
                    dist = model.policy.get_distribution(obs_tensor)
                    probs = dist.distribution.probs[0].cpu().numpy()
                    confidence = float(probs[action])
            else:
                confidence = 0.7  # Default confidence

            # Generate reason based on state
            reason = self._generate_adjustment_reason(state, action_name)

            # Create adjustment parameters
            parameters = self._create_adjustment_parameters(position, action_name)

            return AdjustmentAction(
                action_type=action_name,
                parameters=parameters,
                timestamp=datetime.now(timezone.utc),
                reason=reason,
                confidence=confidence,
            )

        except Exception as e:
            self.error_handler.handle_error(
                e,
                {
                    "method": "get_adjustment_recommendation",
                    "position_type": position.get("type", "unknown"),
                },
            )

            return AdjustmentAction(
                action_type="hold",
                parameters={},
                timestamp=datetime.now(timezone.utc),
                reason="Error in recommendation system",
                confidence=0.0,
            )

    def _create_state_from_position(
        self, position: dict[str, Any], market_data: dict[str, Any]
    ) -> PositionState:
        """Create PositionState from current position"""
        # Calculate Greeks
        greeks = self._calculate_live_greeks(position, market_data)

        # Calculate P&L
        pnl = position.get("unrealized_pnl", 0)
        pnl_percent = pnl / position.get("initial_credit", 1)

        return PositionState(
            position_type=position["type"],
            days_in_trade=position.get("days_held", 0),
            dte=position.get("dte", 30),
            pnl=pnl,
            pnl_percent=pnl_percent,
            delta=greeks["delta"],
            gamma=greeks["gamma"],
            theta=greeks["theta"],
            vega=greeks["vega"],
            underlying_price=market_data["price"],
            underlying_change=(market_data["price"] - position["entry_price"])
            / position["entry_price"],
            iv_rank=market_data.get("iv_rank", 0.5),
            iv_change=market_data.get("iv_change", 0),
            max_profit=position.get("max_profit", 0),
            max_loss=position.get("max_loss", 0),
            current_margin=position.get("margin_requirement", 0),
        )

    def _calculate_live_greeks(
        self, position: dict[str, Any], market_data: dict[str, Any]
    ) -> dict[str, float]:
        """Calculate live Greeks for position"""
        if GreeksCalculator is None:
            return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
        calculator = GreeksCalculator()
        total_greeks = {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}

        # Sum Greeks across all legs
        for leg in position.get("legs", []):
            greeks = calculator.calculate_greeks(
                spot=market_data["price"],
                strike=leg["strike"],
                time_to_expiry=position["dte"] / 365.0,
                volatility=market_data.get("iv", 0.20),
                risk_free_rate=0.05,
                option_type=leg["option_type"],
            )

            # Multiply by position (negative for short)
            multiplier = leg["quantity"]
            for greek in total_greeks:
                total_greeks[greek] += greeks[greek] * multiplier

        return total_greeks

    def _generate_adjustment_reason(self, state: PositionState, action: str) -> str:
        """Generate human-readable reason for adjustment"""
        reasons = []

        # Check various conditions
        if state.pnl_percent > PROFIT_TARGET:
            reasons.append(f"Profit target reached ({state.pnl_percent:.1%})")

        if state.pnl_percent < LOSS_THRESHOLD:
            reasons.append(f"Loss threshold breached ({state.pnl_percent:.1%})")

        if abs(state.delta) > DELTA_THRESHOLD:
            reasons.append(f"Delta risk high ({state.delta:.2f})")

        if state.dte < 10:
            reasons.append(f"Approaching expiration ({state.dte} days)")

        if state.iv_change > 0.2:
            reasons.append("Significant IV expansion")
        elif state.iv_change < -0.2:
            reasons.append("Significant IV contraction")

        # Action-specific reasons
        if action == "roll_out" and state.dte < 21:
            reasons.append("Rolling to maintain time premium")

        if action == "add_hedge" and abs(state.delta) > 0.2:
            reasons.append("Adding protection against directional risk")

        return "; ".join(reasons) if reasons else f"RL model recommends {action}"

    def _create_adjustment_parameters(
        self, position: dict[str, Any], action: str
    ) -> dict[str, Any]:
        """Create specific parameters for adjustment"""
        params = {}

        if action == "roll_out":
            params["target_dte"] = 45
            params["same_strikes"] = True

        elif action == "roll_up":
            params["strikes_to_adjust"] = ["put_short", "put_long"]
            params["adjustment_percent"] = 0.02  # 2% higher

        elif action == "roll_down":
            params["strikes_to_adjust"] = ["call_short", "call_long"]
            params["adjustment_percent"] = -0.02  # 2% lower

        elif action == "reduce_size":
            params["reduction_percent"] = 0.5  # Close 50%

        elif action == "add_hedge":
            # Determine which side needs hedging
            if position.get("delta", 0) > 0:
                params["hedge_type"] = "put"
            else:
                params["hedge_type"] = "call"
            params["hedge_delta"] = 0.25

        return params

    # ==========================================================================
    # ENSEMBLE METHODS
    # ==========================================================================

    def create_ensemble_recommendation(
        self,
        position: dict[str, Any],
        market_data: dict[str, Any],
        models: list[str] | None = None,
    ) -> AdjustmentAction:
        """
        Get ensemble recommendation from multiple models.

        Args:
            position: Current position
            market_data: Market data
            models: List of models to use (default: all available)

        Returns:
            Consensus adjustment recommendation
        """
        if models is None:
            models = [m for m in self.models if position["type"] in m]

        recommendations = []

        for model_name in models:
            if model_name in self.models:
                rec = self.get_adjustment_recommendation(position, market_data)
                recommendations.append(rec)

        if not recommendations:
            return AdjustmentAction(
                action_type="hold",
                parameters={},
                timestamp=datetime.now(timezone.utc),
                reason="No recommendations available",
                confidence=0.0,
            )

        # Vote on action
        action_votes = defaultdict(float)
        for rec in recommendations:
            action_votes[rec.action_type] += rec.confidence

        # Select action with highest weighted votes
        best_action = max(action_votes, key=action_votes.get)
        ensemble_confidence = action_votes[best_action] / len(recommendations)

        # Combine reasons
        all_reasons = [
            rec.reason for rec in recommendations if rec.action_type == best_action
        ]
        combined_reason = f"Ensemble consensus: {'; '.join(set(all_reasons))}"

        # Use parameters from highest confidence recommendation
        best_rec = max(
            [r for r in recommendations if r.action_type == best_action],
            key=lambda x: x.confidence,
        )

        return AdjustmentAction(
            action_type=best_action,
            parameters=best_rec.parameters,
            timestamp=datetime.now(timezone.utc),
            reason=combined_reason,
            confidence=ensemble_confidence,
        )

    # ==========================================================================
    # PERSISTENCE
    # ==========================================================================

    def save_models(self, path: str = "./saved_models/"):
        """Save all trained models"""
        Path(path).mkdir(parents=True, exist_ok=True)

        for name, model in self.models.items():
            model_path = Path(path) / f"{name}.zip"
            model.save(model_path)
            self.logger.info("Saved model: %s", name)

        # Save training history
        history_path = Path(path) / "training_history.json"
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(dict(self.training_history), f, indent=2)

    def load_models(self, path: str = "./saved_models/"):
        """Load previously trained models"""
        model_files = Path(path).glob("*.zip")

        for model_file in model_files:
            model_name = model_file.stem

            # Determine model type and environment
            if "_ppo" in model_name:
                strategy = model_name.replace("_ppo", "")
                if strategy in self.vec_environments:
                    self.models[model_name] = PPO.load(
                        model_file, env=self.vec_environments[strategy]
                    )
                    self.logger.info("Loaded model: %s", model_name)

        # Load training history
        history_path = Path(path) / "training_history.json"
        # Backward-compat: migrate from legacy .pkl
        if not history_path.exists():
            legacy = history_path.with_suffix('.pkl')
            if legacy.exists():
                import joblib as _joblib
                with open(legacy, 'rb') as _f:
                    _hist = _joblib.load(_f)
                with open(history_path, 'w', encoding='utf-8') as _f:
                    json.dump(dict(_hist), _f, indent=2)
        if history_path.exists():
            with open(history_path, encoding='utf-8') as f:
                self.training_history = defaultdict(list, json.load(f))

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def train_with_rllib(self, strategy: str = 'iron_condor',
                          num_workers: int = 4,
                          training_iterations: int = 100,
                          checkpoint_freq: int = 10) -> dict[str, Any]:
        """
        Train RL model using Ray RLlib for distributed multi-worker training.

        RLlib distributes rollout collection across multiple workers while
        centralizing policy updates, enabling much faster training.

        Args:
            strategy: Strategy type to train.
            num_workers: Number of parallel rollout workers.
            training_iterations: Number of training iterations.
            checkpoint_freq: How often to save checkpoints.

        Returns:
            Training results with performance metrics.
        """
        try:
            from ray.rllib.algorithms.ppo import PPOConfig
            import ray
        except ImportError:
            self.logger.warning("Ray RLlib not available, falling back to SB3 training")
            return self.train(strategy=strategy, episodes=training_iterations * 20)

        if not ray.is_initialized():
            ray.init(num_cpus=num_workers + 1, ignore_reinit_error=True)

        self.logger.info(f"RLlib training: strategy={strategy}, workers={num_workers}, "
                          f"iterations={training_iterations}")

        # Build RLlib PPO config
        config = (
            PPOConfig()
            .environment(
                env='CartPole-v1',  # Placeholder — replace with custom env registration
                env_config={
                    'strategy': strategy,
                    'historical_data': self.historical_data.to_dict() if self.historical_data is not None else {},  # noqa: E501
                }
            )
            .rollouts(
                num_rollout_workers=num_workers,
                rollout_fragment_length=200,
            )
            .training(
                lr=LEARNING_RATE,
                gamma=GAMMA,
                train_batch_size=2048,
                sgd_minibatch_size=BATCH_SIZE,
                num_sgd_iter=10,
            )
            .framework('torch')
            .resources(num_gpus=0)
        )

        algo = config.build()
        results_history = []
        best_reward = float('-inf')

        try:
            for i in range(training_iterations):
                result = algo.train()
                episode_reward = result.get('episode_reward_mean', 0)
                results_history.append({
                    'iteration': i,
                    'reward_mean': episode_reward,
                    'reward_min': result.get('episode_reward_min', 0),
                    'reward_max': result.get('episode_reward_max', 0),
                    'episodes_total': result.get('episodes_total', 0),
                    'timesteps_total': result.get('timesteps_total', 0),
                })

                if episode_reward > best_reward:
                    best_reward = episode_reward

                if (i + 1) % checkpoint_freq == 0:
                    checkpoint_dir = algo.save()
                    self.logger.info(f"RLlib iter {i+1}/{training_iterations}: "
                                      f"reward={episode_reward:.2f}, best={best_reward:.2f}, "
                                      f"checkpoint={checkpoint_dir}")

            final_result = {
                'strategy': strategy,
                'backend': 'rllib',
                'num_workers': num_workers,
                'total_iterations': training_iterations,
                'best_reward': best_reward,
                'final_reward': results_history[-1]['reward_mean'] if results_history else 0,
                'total_timesteps': results_history[-1].get('timesteps_total', 0) if results_history else 0,  # noqa: E501
                'history': results_history,
            }

            self.logger.info(f"RLlib training complete: best_reward={best_reward:.2f}")
            return final_result

        finally:
            algo.stop()

    def distributed_hyperparameter_search(self, strategy: str = 'iron_condor',
                                            param_space: dict | None = None,
                                            num_samples: int = 20,
                                            num_cpus: int | None = None) -> dict[str, Any]:
        """
        Distributed hyperparameter search for RL training using Ray.

        Args:
            strategy: Strategy type.
            param_space: Hyperparameter search space.
            num_samples: Number of configurations to try.
            num_cpus: CPU allocation.

        Returns:
            Best hyperparameters and search results.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed HP search")
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        if param_space is None:
            param_space = {
                'learning_rate': [1e-4, 3e-4, 1e-3, 3e-3],
                'gamma': [0.95, 0.97, 0.99],
                'batch_size': [32, 64, 128],
                'n_epochs': [5, 10, 20],
            }

        from itertools import product as iterproduct
        combos = list(iterproduct(*param_space.values()))
        param_names = list(param_space.keys())

        @ray.remote
        def _train_with_params(params: dict, strategy: str) -> dict:
            """Train one configuration on a Ray worker."""
            import numpy as _np
            _np.random.seed(hash(str(params)) % (2**32))
            # Simulated training — replace with actual SB3/RLlib training
            noise = _np.random.randn(100) * params.get('learning_rate', 1e-3)
            reward = float(_np.mean(noise) * 1000 + _np.random.randn() * 10)
            return {
                'params': params,
                'reward': reward,
                'strategy': strategy,
                'status': 'completed',
            }

        self.logger.info(f"Distributed HP search: {len(combos)} configurations, "
                          f"strategy={strategy}")

        futures = [
            _train_with_params.remote(dict(zip(param_names, combo, strict=False)), strategy)
            for combo in combos[:num_samples]
        ]
        search_results = ray.get(futures)

        completed = [r for r in search_results if r.get('status') == 'completed']
        if not completed:
            return {'status': 'failed', 'reason': 'no completed trials'}

        best = max(completed, key=lambda x: x['reward'])
        return {
            'status': 'completed',
            'best_params': best['params'],
            'best_reward': best['reward'],
            'total_trials': len(completed),
            'all_results': search_results,
        }


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: OptionsAdjustmentRL | None = None


def create_options_adjustment_rl(
    config: dict[str, Any] | None = None,
) -> OptionsAdjustmentRL:
    """Factory function to create options adjustment RL system"""
    global _module_instance
    if _module_instance is None:
        _module_instance = OptionsAdjustmentRL(config)
    return _module_instance


def get_options_adjustment_rl() -> OptionsAdjustmentRL | None:
    """Get existing instance"""
    return _module_instance


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test options adjustment RL functionality"""
    import argparse

    parser = argparse.ArgumentParser(description="Options Adjustment RL Testing")
    parser.add_argument("--train", type=str, help="Train model for strategy")
    parser.add_argument("--episodes", type=int, default=100, help="Training episodes")
    parser.add_argument("--test", type=str, help="Test model for strategy")
    parser.add_argument("--demo", action="store_true", help="Run demo adjustment")
    args = parser.parse_args()

    # Create RL system
    rl_system = create_options_adjustment_rl()

    if args.train:
        logging.info("\n=== Training %s Strategy ===", args.train)
        results = rl_system.train(strategy=args.train, episodes=args.episodes)

        logging.info("\nTraining Results:")
        logging.info(f"Mean Return: {results['final_performance']['mean_return']:.3f}")
        logging.info(f"Sharpe Ratio: {results['final_performance']['sharpe_ratio']:.3f}")
        logging.info(f"Win Rate: {results['final_performance']['win_rate']:.2%}")
        logging.info(f"Max Drawdown: {results['final_performance']['max_drawdown']:.2%}")

        # Save models
        rl_system.save_models()

    if args.test:
        logging.info("\n=== Testing %s Strategy ===", args.test)

        # Load models if needed
        rl_system.load_models()

        # Create test position
        test_position = {
            "type": args.test,
            "entry_price": 450,
            "initial_credit": 2.50,
            "days_held": 10,
            "dte": 35,
            "unrealized_pnl": 0.75,
            "legs": [
                {"strike": 440, "option_type": "put", "quantity": -1},
                {"strike": 430, "option_type": "put", "quantity": 1},
                {"strike": 460, "option_type": "call", "quantity": -1},
                {"strike": 470, "option_type": "call", "quantity": 1},
            ],
        }

        test_market = {"price": 452, "iv": 0.18, "iv_rank": 0.45, "iv_change": 0.02}

        # Get recommendation
        recommendation = rl_system.get_adjustment_recommendation(
            test_position, test_market
        )

        logging.info("\nRecommendation: %s", recommendation.action_type)
        logging.info(f"Confidence: {recommendation.confidence:.2%}")
        logging.info("Reason: %s", recommendation.reason)
        logging.info("Parameters: %s", recommendation.parameters)

    if args.demo:
        logging.info("\n=== Adjustment Demo ===")

        # Simulate position lifecycle
        position = {
            "type": "iron_condor",
            "entry_price": 450,
            "initial_credit": 2.50,
            "days_held": 0,
            "dte": 45,
            "unrealized_pnl": 0,
            "legs": [
                {"strike": 427.5, "option_type": "put", "quantity": -1},
                {"strike": 405, "option_type": "put", "quantity": 1},
                {"strike": 472.5, "option_type": "call", "quantity": -1},
                {"strike": 495, "option_type": "call", "quantity": 1},
            ],
        }

        # Simulate 30 days
        for day in range(30):
            # Simulate market movement
            price_change = np.random.randn() * 2
            iv_change = np.random.randn() * 0.01

            market = {
                "price": position["entry_price"] + price_change * (day + 1),
                "iv": 0.20 + iv_change,
                "iv_rank": 0.5 + np.random.randn() * 0.1,
                "iv_change": iv_change,
            }

            # Update position
            position["days_held"] = day
            position["dte"] = 45 - day
            position["unrealized_pnl"] = np.random.randn() * 0.5 + (day * 0.02)

            # Get recommendation
            rec = rl_system.get_adjustment_recommendation(position, market)

            if rec.action_type != "hold":
                logging.info(f"\nDay {day}: Price=${market['price']:.2f}")
                logging.info("Action: %s", rec.action_type)
                logging.info("Reason: %s", rec.reason)
                logging.info(f"P&L: ${position['unrealized_pnl']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
