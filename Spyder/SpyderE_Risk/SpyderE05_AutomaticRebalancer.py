#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE05_AutomaticRebalancer.py
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
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RebalanceType(Enum):
    """Types of rebalancing actions."""

    DELTA_HEDGE = "DELTA_HEDGE"
    GAMMA_SCALP = "GAMMA_SCALP"
    VEGA_HEDGE = "VEGA_HEDGE"
    THETA_ROLL = "THETA_ROLL"
    EMERGENCY = "EMERGENCY"
    SCHEDULED = "SCHEDULED"


class HedgeInstrument(Enum):
    """Available hedging instruments."""

    SPY_SHARES = "SPY_SHARES"
    ES_FUTURES = "ES_FUTURES"
    SPY_OPTIONS = "SPY_OPTIONS"
    VIX_OPTIONS = "VIX_OPTIONS"
    MICRO_ES = "MICRO_ES"  # Micro E-mini futures


@dataclass
class RebalanceAction:
    """Specific rebalancing action to execute."""

    action_type: RebalanceType
    greek: str  # delta, gamma, vega, theta
    current_value: float
    target_value: float
    hedge_instrument: HedgeInstrument
    hedge_quantity: float
    hedge_side: str  # BUY or SELL
    urgency: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    estimated_cost: float
    reason: str


@dataclass
class PortfolioGreeks:
    """Current portfolio-level Greeks."""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    charm: float  # Delta decay
    vanna: float  # Delta/vega sensitivity
    portfolio_value: float
    notional_value: float


class SpyderAutomaticRebalancer:
    """
    Implements automated Greek rebalancing for professional portfolio management.
    Features:
    - Real-time Greek monitoring and rebalancing
    - Multiple hedging instrument selection
    - Cost-optimized execution
    - Portfolio-level Greek aggregation
    - Automatic threshold-based triggers
    """

    def __init__(self, greek_manager=None, order_manager=None, market_data=None):
        """Initialize automatic rebalancer."""
        self.greek_manager = greek_manager
        self.order_manager = order_manager
        self.market_data = market_data
        # Rebalancing thresholds per $1M notional
        self.THRESHOLDS = {
            "delta": {
                "warning": 0.08,  # ±80 delta per $1M
                "action": 0.10,  # ±100 delta per $1M
                "critical": 0.15,  # ±150 delta per $1M
            },
            "gamma": {
                "warning": 40,  # 40 gamma per $1M
                "action": 50,  # 50 gamma per $1M
                "critical": 75,  # 75 gamma per $1M
            },
            "vega": {
                "warning": 150,  # 150 vega per $1M
                "action": 200,  # 200 vega per $1M
                "critical": 300,  # 300 vega per $1M
            },
            "theta": {
                "warning": -75,  # -$75 per day per $100k
                "action": -100,  # -$100 per day per $100k
                "critical": -150,  # -$150 per day per $100k
            },
        }
        # Hedge instrument characteristics
        self.HEDGE_CHARACTERISTICS = {
            HedgeInstrument.SPY_SHARES: {
                "delta": 1.0,
                "gamma": 0.0,
                "min_size": 1,
                "cost_basis": 0.01,  # $0.01 per share cost
                "speed": "FAST",
            },
            HedgeInstrument.ES_FUTURES: {
                "delta": 50.0,  # 50 SPY shares per contract
                "gamma": 0.0,
                "min_size": 1,
                "cost_basis": 2.50,  # $2.50 per contract
                "speed": "FAST",
            },
            HedgeInstrument.MICRO_ES: {
                "delta": 5.0,  # 5 SPY shares per contract
                "gamma": 0.0,
                "min_size": 1,
                "cost_basis": 0.50,  # $0.50 per contract
                "speed": "FAST",
            },
            HedgeInstrument.SPY_OPTIONS: {
                "delta": "VARIABLE",
                "gamma": "VARIABLE",
                "min_size": 1,
                "cost_basis": "SPREAD",
                "speed": "MEDIUM",
            },
            HedgeInstrument.VIX_OPTIONS: {
                "delta": "VARIABLE",
                "gamma": 0.0,
                "min_size": 1,
                "cost_basis": "SPREAD",
                "speed": "SLOW",
            },
        }
        # Monitoring settings
        self.MONITORING_INTERVAL = 15  # seconds (aggressive for demo, normally 60-300)
        self.REBALANCE_COOLDOWN = 300  # 5 minutes between non-urgent rebalances
        # State tracking
        self.last_rebalance = defaultdict(lambda: datetime.min)
        self.rebalance_history = []
        self.monitoring_active = False
        self.emergency_mode = False
        # Cost tracking
        self.daily_rebalance_cost = 0
        self.daily_rebalance_count = 0
        self.cost_limits = {
            "daily_max": 10000,  # $10k daily rebalancing cost limit
            "per_action_max": 1000,  # $1k per rebalancing action
        }

    async def start_monitoring(self):
        """Start automatic Greek monitoring and rebalancing."""
        self.monitoring_active = True
        logger.info("Starting automatic Greek rebalancing monitor")
        while self.monitoring_active:
            try:
                # Get current portfolio Greeks
                greeks = await self._calculate_portfolio_greeks()
                # Check for required rebalancing
                actions = self._check_rebalance_requirements(greeks)
                # Execute rebalancing actions
                if actions:
                    await self._execute_rebalancing(actions, greeks)
                # Log current status
                self._log_greek_status(greeks)
                # Wait for next monitoring cycle
                await asyncio.sleep(self.MONITORING_INTERVAL)
            except Exception as e:
                logger.error(f"Error in Greek monitoring: {str(e)}")
                await asyncio.sleep(self.MONITORING_INTERVAL)

    async def _calculate_portfolio_greeks(self) -> PortfolioGreeks:
        """Calculate aggregate portfolio Greeks."""
        if not self.greek_manager:
            # Return dummy data for demo
            return PortfolioGreeks(
                delta=125.5,
                gamma=55.2,
                vega=225.8,
                theta=-112.5,
                rho=15.2,
                charm=-2.1,
                vanna=1.8,
                portfolio_value=1_000_000,
                notional_value=5_000_000,
            )
        # Get all positions
        positions = await self.greek_manager.get_all_positions()
        # Aggregate Greeks
        total_greeks = PortfolioGreeks(
            delta=0,
            gamma=0,
            vega=0,
            theta=0,
            rho=0,
            charm=0,
            vanna=0,
            portfolio_value=0,
            notional_value=0,
        )
        for position in positions:
            greeks = position.get("greeks", {})
            total_greeks.delta += greeks.get("delta", 0) * position["quantity"]
            total_greeks.gamma += greeks.get("gamma", 0) * position["quantity"]
            total_greeks.vega += greeks.get("vega", 0) * position["quantity"]
            total_greeks.theta += greeks.get("theta", 0) * position["quantity"]
            total_greeks.rho += greeks.get("rho", 0) * position["quantity"]
            total_greeks.portfolio_value += position["market_value"]
            total_greeks.notional_value += position["notional_value"]
        return total_greeks

    def _check_rebalance_requirements(self, greeks: PortfolioGreeks) -> List[RebalanceAction]:
        """Check if rebalancing is required based on thresholds."""
        actions = []
        # Normalize Greeks per $1M notional
        scale_factor = 1_000_000 / max(greeks.notional_value, 1)
        # Check delta
        normalized_delta = abs(greeks.delta) * scale_factor
        delta_threshold = self.THRESHOLDS["delta"]
        if normalized_delta > delta_threshold["critical"]:
            actions.append(self._create_delta_hedge(greeks, "IMMEDIATE"))
        elif normalized_delta > delta_threshold["action"]:
            if self._can_rebalance("delta"):
                actions.append(self._create_delta_hedge(greeks, "HIGH"))
        # Check gamma
        normalized_gamma = abs(greeks.gamma) * scale_factor
        gamma_threshold = self.THRESHOLDS["gamma"]
        if normalized_gamma > gamma_threshold["critical"]:
            actions.append(self._create_gamma_hedge(greeks, "IMMEDIATE"))
        elif normalized_gamma > gamma_threshold["action"]:
            if self._can_rebalance("gamma"):
                actions.append(self._create_gamma_hedge(greeks, "MEDIUM"))
        # Check vega
        normalized_vega = abs(greeks.vega) * scale_factor
        vega_threshold = self.THRESHOLDS["vega"]
        if normalized_vega > vega_threshold["critical"]:
            actions.append(self._create_vega_hedge(greeks, "HIGH"))
        elif normalized_vega > vega_threshold["action"]:
            if self._can_rebalance("vega"):
                actions.append(self._create_vega_hedge(greeks, "MEDIUM"))
        # Check theta (different normalization - per $100k)
        normalized_theta = greeks.theta * (100_000 / max(greeks.portfolio_value, 1))
        theta_threshold = self.THRESHOLDS["theta"]
        if normalized_theta < theta_threshold["critical"]:
            actions.append(self._create_theta_adjustment(greeks, "HIGH"))
        elif normalized_theta < theta_threshold["action"]:
            if self._can_rebalance("theta"):
                actions.append(self._create_theta_adjustment(greeks, "LOW"))
        return [action for action in actions if action is not None]

    def _create_delta_hedge(
        self, greeks: PortfolioGreeks, urgency: str
    ) -> Optional[RebalanceAction]:
        """Create delta hedging action."""
        # Determine optimal hedging instrument
        hedge_instrument = self._select_hedge_instrument(
            greek="delta", size=abs(greeks.delta), urgency=urgency
        )
        # Calculate hedge quantity
        instrument_chars = self.HEDGE_CHARACTERISTICS[hedge_instrument]
        if hedge_instrument in [HedgeInstrument.SPY_SHARES]:
            hedge_quantity = round(abs(greeks.delta))
        elif hedge_instrument == HedgeInstrument.ES_FUTURES:
            hedge_quantity = round(abs(greeks.delta) / 50)  # 50 delta per contract
        elif hedge_instrument == HedgeInstrument.MICRO_ES:
            hedge_quantity = round(abs(greeks.delta) / 5)  # 5 delta per contract
        else:
            return None  # Complex option hedge not implemented here
        if hedge_quantity == 0:
            return None
        # Determine side
        hedge_side = "SELL" if greeks.delta > 0 else "BUY"
        # Estimate cost
        estimated_cost = self._estimate_hedge_cost(hedge_instrument, hedge_quantity, hedge_side)
        return RebalanceAction(
            action_type=RebalanceType.DELTA_HEDGE,
            greek="delta",
            current_value=greeks.delta,
            target_value=0,
            hedge_instrument=hedge_instrument,
            hedge_quantity=hedge_quantity,
            hedge_side=hedge_side,
            urgency=urgency,
            estimated_cost=estimated_cost,
            reason=f"Delta outside threshold: {greeks.delta:.1f}",
        )

    def _create_gamma_hedge(
        self, greeks: PortfolioGreeks, urgency: str
    ) -> Optional[RebalanceAction]:
        """Create gamma hedging action."""
        # Gamma hedging requires options
        hedge_instrument = HedgeInstrument.SPY_OPTIONS
        # Calculate required gamma adjustment
        target_gamma = 0  # Neutral target
        gamma_needed = target_gamma - greeks.gamma
        # Estimate ATM option gamma (simplified)
        atm_option_gamma = 0.5  # Typical ATM gamma
        hedge_quantity = round(abs(gamma_needed) / atm_option_gamma)
        if hedge_quantity == 0:
            return None
        hedge_side = "BUY" if gamma_needed > 0 else "SELL"
        # Estimate cost (more complex for options)
        estimated_cost = hedge_quantity * 250  # Rough estimate
        return RebalanceAction(
            action_type=RebalanceType.GAMMA_SCALP,
            greek="gamma",
            current_value=greeks.gamma,
            target_value=target_gamma,
            hedge_instrument=hedge_instrument,
            hedge_quantity=hedge_quantity,
            hedge_side=hedge_side,
            urgency=urgency,
            estimated_cost=estimated_cost,
            reason=f"Gamma exposure high: {greeks.gamma:.1f}",
        )

    def _create_vega_hedge(
        self, greeks: PortfolioGreeks, urgency: str
    ) -> Optional[RebalanceAction]:
        """Create vega hedging action."""
        # Vega hedging typically uses VIX options or SPY options
        hedge_instrument = HedgeInstrument.VIX_OPTIONS
        # Calculate required vega adjustment
        target_vega = 0  # Neutral target
        vega_needed = target_vega - greeks.vega
        # VIX option typically has 100 vega per contract
        vix_option_vega = 100
        hedge_quantity = round(abs(vega_needed) / vix_option_vega)
        if hedge_quantity == 0:
            return None
        hedge_side = "BUY" if vega_needed > 0 else "SELL"
        estimated_cost = hedge_quantity * 150  # Rough estimate
        return RebalanceAction(
            action_type=RebalanceType.VEGA_HEDGE,
            greek="vega",
            current_value=greeks.vega,
            target_value=target_vega,
            hedge_instrument=hedge_instrument,
            hedge_quantity=hedge_quantity,
            hedge_side=hedge_side,
            urgency=urgency,
            estimated_cost=estimated_cost,
            reason=f"Vega exposure high: {greeks.vega:.1f}",
        )

    def _create_theta_adjustment(
        self, greeks: PortfolioGreeks, urgency: str
    ) -> Optional[RebalanceAction]:
        """Create theta adjustment action (typically rolling positions)."""
        # Theta adjustment usually involves rolling to longer-dated options
        return RebalanceAction(
            action_type=RebalanceType.THETA_ROLL,
            greek="theta",
            current_value=greeks.theta,
            target_value=greeks.theta * 0.5,  # Reduce by 50%
            hedge_instrument=HedgeInstrument.SPY_OPTIONS,
            hedge_quantity=0,  # Determined during execution
            hedge_side="ROLL",
            urgency=urgency,
            estimated_cost=500,  # Roll transaction costs
            reason=f"Theta decay excessive: ${greeks.theta:.0f}/day",
        )

    def _select_hedge_instrument(self, greek: str, size: float, urgency: str) -> HedgeInstrument:
        """Select optimal hedging instrument based on requirements."""
        if greek == "delta":
            # For delta hedging, choose based on size and urgency
            if urgency == "IMMEDIATE":
                # Use fastest instrument
                if size < 100:
                    return HedgeInstrument.SPY_SHARES
                elif size < 500:
                    return HedgeInstrument.MICRO_ES
                else:
                    return HedgeInstrument.ES_FUTURES
            else:
                # Optimize for cost
                if size < 50:
                    return HedgeInstrument.SPY_SHARES
                elif size < 250:
                    return HedgeInstrument.MICRO_ES
                else:
                    return HedgeInstrument.ES_FUTURES
        elif greek == "vega":
            return HedgeInstrument.VIX_OPTIONS
        else:
            return HedgeInstrument.SPY_OPTIONS

    def _estimate_hedge_cost(
        self, instrument: HedgeInstrument, quantity: float, side: str
    ) -> float:
        """Estimate cost of hedging action."""
        chars = self.HEDGE_CHARACTERISTICS[instrument]
        base_cost = chars["cost_basis"]
        if isinstance(base_cost, (int, float)):
            # Simple cost calculation
            transaction_cost = base_cost * quantity
        else:
            # Complex cost (options with spread)
            transaction_cost = quantity * 10  # Rough estimate
        # Add market impact for large orders
        if quantity > 100:
            transaction_cost *= 1.2
        return transaction_cost

    def _can_rebalance(self, greek: str) -> bool:
        """Check if rebalancing is allowed based on cooldown and cost limits."""
        # Check cooldown
        last_rebalance = self.last_rebalance[greek]
        cooldown_elapsed = (datetime.now() - last_rebalance).seconds
        if cooldown_elapsed < self.REBALANCE_COOLDOWN:
            return False
        # Check daily cost limit
        if self.daily_rebalance_cost >= self.cost_limits["daily_max"]:
            logger.warning(
                f"Daily rebalancing cost limit reached: " f"${self.daily_rebalance_cost:.0f}"
            )
            return False
        return True

    async def _execute_rebalancing(self, actions: List[RebalanceAction], greeks: PortfolioGreeks):
        """Execute rebalancing actions."""
        logger.info(f"Executing {len(actions)} rebalancing actions")
        # Sort by urgency
        urgency_order = {"IMMEDIATE": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        actions.sort(key=lambda x: urgency_order.get(x.urgency, 4))
        for action in actions:
            try:
                # Check cost limit
                if action.estimated_cost > self.cost_limits["per_action_max"]:
                    logger.warning(
                        f"Rebalancing action exceeds cost limit: " f"${action.estimated_cost:.0f}"
                    )
                    continue
                # Execute based on action type
                if action.action_type == RebalanceType.DELTA_HEDGE:
                    await self._execute_delta_hedge(action)
                elif action.action_type == RebalanceType.GAMMA_SCALP:
                    await self._execute_gamma_hedge(action)
                elif action.action_type == RebalanceType.VEGA_HEDGE:
                    await self._execute_vega_hedge(action)
                elif action.action_type == RebalanceType.THETA_ROLL:
                    await self._execute_theta_roll(action)
                # Update tracking
                self.last_rebalance[action.greek] = datetime.now()
                self.daily_rebalance_cost += action.estimated_cost
                self.daily_rebalance_count += 1
                # Record history
                self._record_rebalance(action, greeks)
                # Brief pause between actions
                if action.urgency != "IMMEDIATE":
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to execute rebalancing action: {str(e)}")

    async def _execute_delta_hedge(self, action: RebalanceAction):
        """Execute delta hedging trade."""
        logger.info(
            f"Executing delta hedge: {action.hedge_side} "
            f"{action.hedge_quantity} {action.hedge_instrument.value}"
        )
        if not self.order_manager:
            logger.warning("No order manager available for delta hedge")
            return
        # Create order based on instrument
        if action.hedge_instrument == HedgeInstrument.SPY_SHARES:
            order = {
                "symbol": "SPY",
                "quantity": action.hedge_quantity,
                "side": action.hedge_side,
                "order_type": "LIMIT",
                "time_in_force": "IOC",  # Immediate or cancel
                "limit_price": "MIDPOINT",  # Use midpoint pricing
                "reason": f"Delta hedge: {action.current_value:.1f} -> 0",
            }
        elif action.hedge_instrument in [HedgeInstrument.ES_FUTURES, HedgeInstrument.MICRO_ES]:
            symbol = "ES" if action.hedge_instrument == HedgeInstrument.ES_FUTURES else "MES"
            order = {
                "symbol": symbol,
                "quantity": action.hedge_quantity,
                "side": action.hedge_side,
                "order_type": "LIMIT",
                "time_in_force": "IOC",
                "limit_price": "MIDPOINT",
                "reason": f"Delta hedge via futures",
            }
        await self.order_manager.submit_order(order)

    async def _execute_gamma_hedge(self, action: RebalanceAction):
        """Execute gamma hedging trade."""
        logger.info(
            f"Executing gamma hedge: {action.hedge_side} " f"{action.hedge_quantity} ATM options"
        )
        # Gamma hedging logic would go here
        # Typically involves buying/selling ATM options
        pass

    async def _execute_vega_hedge(self, action: RebalanceAction):
        """Execute vega hedging trade."""
        logger.info(
            f"Executing vega hedge: {action.hedge_side} " f"{action.hedge_quantity} VIX options"
        )
        # Vega hedging logic would go here
        # Typically involves VIX options or variance swaps
        pass

    async def _execute_theta_roll(self, action: RebalanceAction):
        """Execute theta roll to reduce time decay."""
        logger.info(
            f"Executing theta roll to reduce decay from " f"${action.current_value:.0f}/day"
        )
        # Theta roll logic would go here
        # Involves closing near-term options and opening longer-term
        pass

    def _log_greek_status(self, greeks: PortfolioGreeks):
        """Log current Greek status."""
        # Normalize per $1M notional
        scale = 1_000_000 / max(greeks.notional_value, 1)
        status = (
            f"Greeks per $1M: Δ={greeks.delta*scale:.1f}, "
            f"Γ={greeks.gamma*scale:.1f}, "
            f"V={greeks.vega*scale:.1f}, "
            f"Θ=${greeks.theta*(100_000/max(greeks.portfolio_value, 1)):.0f}/day"
        )
        # Determine if any are in warning/action zones
        if any(self._check_rebalance_requirements(greeks)):
            logger.warning(f"Greeks outside thresholds: {status}")
        else:
            logger.debug(f"Greeks within limits: {status}")

    def _record_rebalance(self, action: RebalanceAction, greeks: PortfolioGreeks):
        """Record rebalancing action in history."""
        record = {
            "timestamp": datetime.now(),
            "action_type": action.action_type.value,
            "greek": action.greek,
            "pre_value": action.current_value,
            "post_value": action.target_value,
            "instrument": action.hedge_instrument.value,
            "quantity": action.hedge_quantity,
            "side": action.hedge_side,
            "cost": action.estimated_cost,
            "portfolio_value": greeks.portfolio_value,
            "notional_value": greeks.notional_value,
        }
        self.rebalance_history.append(record)

    def get_rebalancing_stats(self, period_days: int = 30) -> Dict[str, Any]:
        """Get rebalancing statistics for period."""
        if not self.rebalance_history:
            return {"no_data": True}
        df = pd.DataFrame(self.rebalance_history)
        cutoff = datetime.now() - timedelta(days=period_days)
        df = df[df["timestamp"] >= cutoff]
        if df.empty:
            return {"no_data": True}
        stats = {
            "total_rebalances": len(df),
            "daily_average": len(df) / period_days,
            "total_cost": df["cost"].sum(),
            "avg_cost_per_action": df["cost"].mean(),
            "by_greek": df.groupby("greek")["cost"].agg(["count", "sum"]).to_dict(),
            "by_instrument": df.groupby("instrument")["cost"].agg(["count", "sum"]).to_dict(),
            "urgency_breakdown": df.groupby("action_type")["cost"].count().to_dict(),
        }
        return stats

    async def emergency_flatten(self, reason: str = "Manual emergency"):
        """Emergency flattening of all Greeks."""
        logger.critical(f"EMERGENCY GREEK FLATTENING: {reason}")
        self.emergency_mode = True
        # Get current Greeks
        greeks = await self._calculate_portfolio_greeks()
        # Create immediate hedging actions for all Greeks
        actions = []
        # Delta hedge
        if abs(greeks.delta) > 1:
            actions.append(self._create_delta_hedge(greeks, "IMMEDIATE"))
        # Gamma hedge
        if abs(greeks.gamma) > 1:
            actions.append(self._create_gamma_hedge(greeks, "IMMEDIATE"))
        # Vega hedge
        if abs(greeks.vega) > 10:
            actions.append(self._create_vega_hedge(greeks, "IMMEDIATE"))
        # Execute all hedges immediately
        await self._execute_rebalancing([a for a in actions if a is not None], greeks)
        self.emergency_mode = False
        logger.info("Emergency flattening complete")

    def stop_monitoring(self):
        """Stop automatic monitoring."""
        self.monitoring_active = False
        logger.info("Stopping automatic Greek rebalancing monitor")

    # --------------------------------------------------------------------------
    # STABLE-BASELINES3: RL COST-AWARE REBALANCING
    # --------------------------------------------------------------------------

    def create_rebalancing_rl_env(self):
        """
        Create an RL environment for cost-aware rebalancing scheduling.

        The agent learns WHEN to rebalance by weighing tracking error
        against transaction costs and market impact.

        Returns:
            gym.Env instance for training with SB3 PPO/SAC.
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            try:
                import gym
                from gym import spaces
            except ImportError:
                logger.warning("gym/gymnasium not installed — RL env unavailable")
                return None

        class RebalancingEnvironment(gym.Env):
            """
            RL environment for rebalancing schedule optimization.

            Observation: [tracking_error, portfolio_drift, days_since_rebal,
                         market_vol, spread_cost, time_of_day_norm]
            Action: 0=hold, 1=partial_rebalance, 2=full_rebalance
            Reward: -tracking_error - transaction_cost + risk_reduction
            """
            metadata = {'render_modes': []}

            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-5.0, high=5.0, shape=(6,), dtype=np.float32)
                self.action_space = spaces.Discrete(3)
                self.step_count = 0
                self.max_steps = 252
                self._state = np.zeros(6, dtype=np.float32)

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.step_count = 0
                self._state = np.array([
                    np.random.uniform(0, 0.05),   # tracking_error
                    np.random.uniform(0, 0.1),    # portfolio_drift
                    0.0,                           # days_since_rebal
                    np.random.uniform(0.1, 0.4),  # market_vol
                    np.random.uniform(0.001, 0.01), # spread_cost
                    np.random.uniform(0, 1),       # time_of_day
                ], dtype=np.float32)
                return self._state, {}

            def step(self, action):
                self.step_count += 1
                tracking_error = self._state[0]
                drift = self._state[1]
                spread = self._state[4]

                if action == 0:  # hold
                    cost = 0
                    self._state[0] += np.random.uniform(0, 0.005)
                    self._state[1] += np.random.uniform(0, 0.01)
                    self._state[2] += 1
                elif action == 1:  # partial rebalance
                    cost = spread * 0.5
                    self._state[0] *= 0.5
                    self._state[1] *= 0.5
                    self._state[2] = 0
                else:  # full rebalance
                    cost = spread * 1.0
                    self._state[0] = np.random.uniform(0, 0.005)
                    self._state[1] = np.random.uniform(0, 0.01)
                    self._state[2] = 0

                reward = -tracking_error * 10 - cost * 100 - drift * 5
                self._state[3] = np.clip(
                    self._state[3] + np.random.normal(0, 0.02), 0.05, 0.8)
                done = self.step_count >= self.max_steps
                return self._state.copy(), float(reward), done, False, {}

        return RebalancingEnvironment()

    def train_rebalancing_policy(self, total_timesteps: int = 50000) -> Optional[Any]:
        """
        Train a PPO policy for cost-aware rebalancing.

        Args:
            total_timesteps: Training steps.

        Returns:
            Trained SB3 model or None if unavailable.
        """
        env = self.create_rebalancing_rl_env()
        if env is None:
            return None

        try:
            from stable_baselines3 import PPO
            model = PPO('MlpPolicy', env, verbose=0,
                       learning_rate=3e-4, n_steps=2048)
            model.learn(total_timesteps=total_timesteps)
            logger.info(f"Rebalancing RL policy trained: {total_timesteps} steps")
            return model
        except ImportError:
            logger.warning("stable-baselines3 not installed")
            return None


async def main():
    """Example usage of automatic rebalancer."""
    rebalancer = SpyderAutomaticRebalancer()
    # Start monitoring in background
    monitor_task = asyncio.create_task(rebalancer.start_monitoring())
    # Simulate for 30 seconds
    await asyncio.sleep(30)
    # Get stats
    stats = rebalancer.get_rebalancing_stats(period_days=1)
    print("\nRebalancing Statistics:")
    print(json.dumps(stats, indent=2, default=str))
    # Stop monitoring
    rebalancer.stop_monitoring()
    await monitor_task


if __name__ == "__main__":
    asyncio.run(main())
# Alias for compatibility
AutomaticRebalancer = SpyderAutomaticRebalancer
