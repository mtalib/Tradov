#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderD22_AdaptiveVolatility.py
Group: D (Strategies)
Purpose: Adaptive volatility trading strategy leveraging N-modules
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 16:30:00

Description:
    This module implements an adaptive volatility trading strategy that leverages
    the N-group numerical modules for sophisticated volatility analysis. It trades
    the volatility risk premium, IV/HV divergences, term structure anomalies, and
    volatility regime changes. The strategy dynamically adjusts positions based on
    volatility forecasts, skew analysis, and market microstructure.

Key Features:
    - IV vs HV arbitrage trading
    - Volatility risk premium harvesting
    - Term structure trading (contango/backwardation)
    - Volatility regime detection and adaptation
    - Skew trading opportunities
    - Integration with N04_OptionsGreeks and N05_VolatilityModeling
    - Dynamic position sizing based on volatility forecast
    - Multiple timeframe volatility analysis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy
)

# Optional analytics imports
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator  # noqa: E501
    HAS_GREEKS_CALC = True
except ImportError:
    OptionsGreeksCalculator = None
    HAS_GREEKS_CALC = False

try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder import VolatilitySurfaceBuilder as VolatilityModeling  # noqa: E501
    HAS_VOL_MODELING = True
except ImportError:
    VolatilityModeling = None
    HAS_VOL_MODELING = False



class StatisticalAnalysis:
    """Stub statistical analysis helper — extend as needed."""
    pass


@dataclass
class Signal:
    """Lightweight signal wrapper for adaptive volatility decisions."""
    action: str = "HOLD"
    strength: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyState(Enum):
    """Strategy operational state."""
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


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
# CONSTANTS
# ==============================================================================
# Volatility thresholds
IV_HV_DIVERGENCE_THRESHOLD = 0.20  # 20% divergence triggers signal
VOLATILITY_RISK_PREMIUM_TARGET = 0.15  # Target 15% premium
SKEW_EXTREME_THRESHOLD = 2.0  # 2 standard deviations
TERM_STRUCTURE_SLOPE_THRESHOLD = 0.10  # 10% slope difference

# Position limits
MAX_VEGA_EXPOSURE = 1000  # Maximum vega per position
MAX_VOLATILITY_POSITIONS = 5
MIN_DAYS_TO_EXPIRY = 15
MAX_DAYS_TO_EXPIRY = 60

# Regime thresholds
REGIME_CHANGE_CONFIDENCE = 0.70  # 70% confidence for regime change
VOLATILITY_SPIKE_THRESHOLD = 1.5  # 50% increase = spike
VOLATILITY_CRUSH_THRESHOLD = 0.7  # 30% decrease = crush

# Risk parameters
MAX_POSITION_SIZE = 0.05  # 5% of portfolio per position
STOP_LOSS_MULTIPLIER = 2.0  # Stop at 2x expected move
TARGET_PROFIT_MULTIPLIER = 1.5  # Target 1.5x risk

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    LOW_STABLE = "low_stable"
    LOW_RISING = "low_rising"
    NORMAL = "normal"
    HIGH_STABLE = "high_stable"
    HIGH_FALLING = "high_falling"
    SPIKE = "spike"
    CRUSH = "crush"
    TRANSITIONING = "transitioning"

class VolatilityTrade(Enum):
    """Types of volatility trades"""
    LONG_VOLATILITY = "long_volatility"
    SHORT_VOLATILITY = "short_volatility"
    VOLATILITY_ARBITRAGE = "volatility_arbitrage"
    TERM_STRUCTURE = "term_structure"
    SKEW_TRADE = "skew_trade"
    DISPERSION = "dispersion"
    CORRELATION = "correlation"

class SignalStrength(Enum):
    """Signal strength levels"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics"""
    spot_price: float
    implied_volatility: float
    historical_volatility: float
    iv_rank: float
    iv_percentile: float
    volatility_risk_premium: float
    realized_volatility: float
    garch_forecast: float
    ewma_volatility: float
    parkinson_volatility: float
    term_structure: dict[int, float]
    volatility_smile: dict[float, float]
    skew: float
    kurtosis: float
    regime: VolatilityRegime
    regime_confidence: float

@dataclass
class VolatilitySignal:
    """Volatility trading signal"""
    trade_type: VolatilityTrade
    direction: str  # LONG, SHORT, NEUTRAL
    strength: SignalStrength
    entry_iv: float
    target_iv: float
    stop_iv: float
    expected_edge: float
    confidence: float
    time_horizon: int  # Days
    recommended_structure: str
    size_recommendation: float

@dataclass
class VolatilityPosition:
    """Active volatility position"""
    position_id: str
    trade_type: VolatilityTrade
    entry_date: datetime
    expiration: datetime
    structure: str  # straddle, strangle, etc.
    entry_iv: float
    current_iv: float
    target_iv: float
    stop_iv: float
    vega: float
    theta: float
    gamma: float
    pnl: float
    days_held: int

# ==============================================================================
# RL ENVIRONMENT — VOLATILITY POSITION SIZING & OPPORTUNITY SCORING
# ==============================================================================
if HAS_SB3:
    class VolSizingEnvironment(gym.Env):
        """
        RL environment for adaptive volatility position sizing and
        opportunity selection.

        The agent observes volatility metrics (IV, HV, VRP, term structure,
        skew, regime) and decides position size and which opportunity to
        prioritise. This replaces the hardcoded scoring weights in
        ``_select_best_opportunity()`` and the trivial
        ``_calculate_position_size()`` with a learned policy.

        Observation (10-dim):
            [iv_rank, iv_percentile, vrp, iv_hv_ratio, skew_z,
             term_slope, regime_enc, regime_confidence,
             signal_strength_norm, expected_edge]

        Actions (5 discrete):
            0=skip, 1=tiny (0.2x), 2=small (0.5x), 3=full (1.0x),
            4=aggressive (1.5x)

        Reward:
            Simulated trade P&L weighted by chosen size.
        """

        SIZE_MULTIPLIERS = [0.0, 0.2, 0.5, 1.0, 1.5]

        REGIME_ENCODING = {
            'low_stable': 0.0,
            'low_rising': 0.15,
            'normal': 0.30,
            'high_stable': 0.50,
            'high_falling': 0.65,
            'spike': 0.80,
            'crush': 0.90,
            'transitioning': 1.0,
        }

        def __init__(self, episode_length: int = 60):
            super().__init__()
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(10,), dtype=np.float32
            )
            self.action_space = spaces.Discrete(5)
            self.episode_length = episode_length
            self.current_step = 0
            self.cumulative_pnl = 0.0
            self._data = self._generate_synthetic_data()

        def reset(self) -> np.ndarray:
            max_start = max(0, len(self._data) - self.episode_length - 1)
            self._start = np.random.randint(0, max(1, max_start))
            self.current_step = 0
            self.cumulative_pnl = 0.0
            return self._get_obs()

        def step(self, action: int):
            idx = self._start + self.current_step
            row = self._data.iloc[idx]
            size = self.SIZE_MULTIPLIERS[action]

            if action == 0:  # Skip
                reward = -0.001  # tiny patience cost
            else:
                trade_return = row.get('future_pnl', 0.0)
                reward = float(trade_return * size)
                self.cumulative_pnl += reward

            self.current_step += 1
            done = self.current_step >= self.episode_length
            info = {'pnl': self.cumulative_pnl, 'size': size}
            return self._get_obs(), float(reward), done, info

        def _get_obs(self) -> np.ndarray:
            idx = min(self._start + self.current_step, len(self._data) - 1)
            r = self._data.iloc[idx]
            return np.array([
                r['iv_rank'],
                r['iv_percentile'],
                r['vrp'],
                r['iv_hv_ratio'],
                r['skew_z'],
                r['term_slope'],
                r['regime_enc'],
                r['regime_confidence'],
                r['signal_strength'],
                r['expected_edge'],
            ], dtype=np.float32)

        @staticmethod
        def _generate_synthetic_data(n: int = 2000) -> pd.DataFrame:
            iv_rank = np.random.uniform(0, 1, n)
            iv_pct = np.random.uniform(0, 1, n)
            vrp = np.random.normal(0.05, 0.10, n)
            iv_hv = np.random.uniform(0.6, 1.6, n)
            skew = np.random.normal(0, 1, n)
            term = np.random.normal(0, 0.05, n)
            regime = np.random.uniform(0, 1, n)
            conf = np.random.uniform(0.4, 1.0, n)
            strength = np.random.uniform(0, 1, n)
            edge = np.random.normal(0.02, 0.05, n)
            future_pnl = edge + np.random.normal(0, 0.03, n)
            return pd.DataFrame({
                'iv_rank': iv_rank, 'iv_percentile': iv_pct, 'vrp': vrp,
                'iv_hv_ratio': iv_hv, 'skew_z': skew, 'term_slope': term,
                'regime_enc': regime, 'regime_confidence': conf,
                'signal_strength': strength, 'expected_edge': edge,
                'future_pnl': future_pnl,
            })


# ==============================================================================
# MAIN STRATEGY CLASS
# ==============================================================================
class AdaptiveVolatilityStrategy(BaseStrategy):
    """
    Adaptive volatility trading strategy.

    Leverages numerical modules to identify and trade volatility opportunities
    across multiple timeframes and structures.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Adaptive Volatility Strategy"""
        super().__init__(config)

        self.strategy_name = "AdaptiveVolatility"
        self.version = "1.0.0"

        # Initialize numerical components
        if OptionsGreeksCalculator is None:
            raise ImportError(
                "OptionsGreeksCalculator unavailable — check SpyderN04_OptionsGreeksCalculator imports"  # noqa: E501
            )
        if VolatilityModeling is None:
            raise ImportError(
                "VolatilityModeling unavailable — check SpyderN06_VolatilitySurfaceBuilder imports"
            )
        self.greeks_calculator = OptionsGreeksCalculator()
        self.volatility_model = VolatilityModeling()
        self.statistical_analyzer = StatisticalAnalysis()

        # Strategy parameters
        self.iv_hv_threshold = config.get('iv_hv_threshold', IV_HV_DIVERGENCE_THRESHOLD)
        self.vrp_target = config.get('vrp_target', VOLATILITY_RISK_PREMIUM_TARGET)
        self.max_vega = config.get('max_vega', MAX_VEGA_EXPOSURE)

        # Position tracking
        self.active_positions: dict[str, VolatilityPosition] = {}
        self.position_history: list[VolatilityPosition] = []

        # Volatility tracking
        self.current_metrics: VolatilityMetrics | None = None
        self.volatility_history = []
        self.regime_history = []

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.sharpe_ratio = 0.0

        # Calibration data
        self.iv_history = pd.DataFrame()
        self.hv_history = pd.DataFrame()
        self.regime_model = None

        self.logger.info("%s initialized", self.strategy_name)

        # RL volatility sizing model (optional)
        self._rl_vol_model = None
        self._rl_vol_enabled = HAS_SB3
        self._load_rl_vol_model()

    def _load_rl_vol_model(self, model_path: str | None = None) -> None:
        """Load pre-trained RL volatility sizing model if available."""
        if not HAS_SB3:
            self._rl_vol_enabled = False
            return
        try:
            import os
            if model_path:
                self._rl_vol_model = PPO.load(model_path)
                self.logger.info("RL vol sizing model loaded from %s", model_path)
            else:
                default_path = "models/rl/vol_sizing/vol_sizing_PPO_final"
                if os.path.exists(default_path + ".zip"):
                    self._rl_vol_model = PPO.load(default_path)
                    self.logger.info("RL vol sizing model loaded from default path")
                else:
                    self._rl_vol_enabled = False
        except Exception as e:
            self._rl_vol_enabled = False
            self.logger.warning("Failed to load RL vol model: %s", e)

    def _get_rl_position_size(
        self,
        metrics: 'VolatilityMetrics',
        signal_strength: float,
        expected_edge: float = 0.0,
    ) -> float | None:
        """
        Query RL model for position size recommendation.

        Args:
            metrics: Current volatility metrics.
            signal_strength: Normalised signal strength (0–1).
            expected_edge: Expected edge of the opportunity.

        Returns:
            Position size multiplier, or None if RL is unavailable.
        """
        if not self._rl_vol_enabled or self._rl_vol_model is None:
            return None

        try:
            regime_enc = {
                VolatilityRegime.LOW_STABLE: 0.0,
                VolatilityRegime.LOW_RISING: 0.15,
                VolatilityRegime.NORMAL: 0.30,
                VolatilityRegime.HIGH_STABLE: 0.50,
                VolatilityRegime.HIGH_FALLING: 0.65,
                VolatilityRegime.SPIKE: 0.80,
                VolatilityRegime.CRUSH: 0.90,
                VolatilityRegime.TRANSITIONING: 1.0,
            }.get(metrics.regime, 0.3)

            iv_hv_ratio = (
                metrics.implied_volatility / max(0.001, metrics.historical_volatility)
            )

            obs = np.array([
                metrics.iv_rank,
                metrics.iv_percentile,
                metrics.volatility_risk_premium,
                iv_hv_ratio,
                metrics.skew,
                next(iter(metrics.term_structure.values()), 0.0)
                    if metrics.term_structure else 0.0,
                regime_enc,
                metrics.regime_confidence,
                signal_strength,
                expected_edge,
            ], dtype=np.float32)

            action, _ = self._rl_vol_model.predict(obs, deterministic=True)
            action = int(action)
            size_mults = [0.0, 0.2, 0.5, 1.0, 1.5]
            return size_mults[action]

        except Exception as e:
            self.logger.warning("RL vol sizing failed: %s", e)
            return None

    def analyze_market_conditions(self, market_data: dict[str, Any]) -> Signal:
        """
        Analyze volatility conditions and generate trading signals.

        Args:
            market_data: Current market data including options

        Returns:
            Trading signal with volatility positions
        """
        try:
            # Calculate comprehensive volatility metrics
            metrics = self._calculate_volatility_metrics(market_data)
            self.current_metrics = metrics

            # Detect regime and transitions
            self._detect_regime_change(metrics)

            # Analyze trading opportunities
            opportunities = []

            # Check IV/HV divergence
            iv_hv_signal = self._analyze_iv_hv_divergence(metrics)
            if iv_hv_signal:
                opportunities.append(iv_hv_signal)

            # Check volatility risk premium
            vrp_signal = self._analyze_vrp(metrics)
            if vrp_signal:
                opportunities.append(vrp_signal)

            # Check term structure
            term_signal = self._analyze_term_structure(metrics)
            if term_signal:
                opportunities.append(term_signal)

            # Check skew opportunities
            skew_signal = self._analyze_skew(metrics)
            if skew_signal:
                opportunities.append(skew_signal)

            # Combine signals and select best opportunity
            if opportunities:
                best_signal = self._select_best_opportunity(opportunities, metrics)
                return self._create_trade_signal(best_signal, metrics, market_data)

            # Check existing positions for management
            management_signal = self._manage_positions(metrics, market_data)
            if management_signal:
                return management_signal

            return Signal(action="HOLD")

        except Exception as e:
            self.logger.error("Error analyzing volatility: %s", e)
            self.error_handler.handle_error(e, {"method": "analyze_market_conditions"})
            return Signal(action="HOLD")

    def _calculate_volatility_metrics(self, market_data: dict[str, Any]) -> VolatilityMetrics:
        """Calculate comprehensive volatility metrics"""
        try:
            spot = market_data['SPY']['last']

            # Get IV from options data
            options_data = market_data.get('options_data', {})
            current_iv = options_data.get('implied_volatility', 0.20)

            # Calculate historical volatilities using N-modules
            price_history = market_data.get('price_history', [])

            # Use VolatilityModeling module for sophisticated calculations
            hv_20 = self.volatility_model.calculate_historical_volatility(price_history, 20)
            realized_vol = self.volatility_model.calculate_realized_volatility(price_history)
            garch_forecast = self.volatility_model.garch_forecast(price_history)
            ewma_vol = self.volatility_model.calculate_ewma_volatility(price_history)
            parkinson_vol = self.volatility_model.calculate_parkinson_volatility(
                market_data.get('high_low_data', [])
            )

            # Calculate IV rank and percentile
            iv_rank = self._calculate_iv_rank(current_iv)
            iv_percentile = self._calculate_iv_percentile(current_iv)

            # Calculate volatility risk premium
            vrp = current_iv - realized_vol

            # Get term structure
            term_structure = self._extract_term_structure(options_data)

            # Get volatility smile/skew
            smile = self._extract_volatility_smile(options_data)

            # Calculate skew and kurtosis
            skew = self.statistical_analyzer.calculate_skew(price_history)
            kurtosis = self.statistical_analyzer.calculate_kurtosis(price_history)

            # Determine regime
            regime, confidence = self._determine_volatility_regime(
                current_iv, hv_20, iv_rank, vrp
            )

            return VolatilityMetrics(
                spot_price=spot,
                implied_volatility=current_iv,
                historical_volatility=hv_20,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                volatility_risk_premium=vrp,
                realized_volatility=realized_vol,
                garch_forecast=garch_forecast,
                ewma_volatility=ewma_vol,
                parkinson_volatility=parkinson_vol,
                term_structure=term_structure,
                volatility_smile=smile,
                skew=skew,
                kurtosis=kurtosis,
                regime=regime,
                regime_confidence=confidence
            )

        except Exception as e:
            self.logger.error("Error calculating volatility metrics: %s", e)
            # Return default metrics
            return VolatilityMetrics(
                spot_price=market_data.get('SPY', {}).get('last', 450),
                implied_volatility=0.20,
                historical_volatility=0.18,
                iv_rank=50,
                iv_percentile=50,
                volatility_risk_premium=0.02,
                realized_volatility=0.18,
                garch_forecast=0.19,
                ewma_volatility=0.19,
                parkinson_volatility=0.17,
                term_structure={},
                volatility_smile={},
                skew=0,
                kurtosis=3,
                regime=VolatilityRegime.NORMAL,
                regime_confidence=0.5
            )

    def _calculate_iv_rank(self, current_iv: float) -> float:
        """Calculate IV rank over past year"""
        if len(self.iv_history) < 20:
            return 50.0  # Default to middle

        yearly_ivs = self.iv_history.tail(252)['iv'].values
        min_iv = yearly_ivs.min()
        max_iv = yearly_ivs.max()

        if max_iv == min_iv:
            return 50.0

        return ((current_iv - min_iv) / (max_iv - min_iv)) * 100

    def _calculate_iv_percentile(self, current_iv: float) -> float:
        """Calculate IV percentile over past year"""
        if len(self.iv_history) < 20:
            return 50.0

        yearly_ivs = self.iv_history.tail(252)['iv'].values
        return stats.percentileofscore(yearly_ivs, current_iv)

    def _extract_term_structure(self, options_data: dict) -> dict[int, float]:
        """Extract volatility term structure"""
        term_structure = {}

        expirations = options_data.get('expirations', {})
        for days, data in expirations.items():
            if isinstance(days, int) and 'implied_volatility' in data:
                term_structure[days] = data['implied_volatility']

        return term_structure

    def _extract_volatility_smile(self, options_data: dict) -> dict[float, float]:
        """Extract volatility smile/skew"""
        smile = {}

        chain = options_data.get('chain', {})
        for strike, data in chain.items():
            if isinstance(data, dict) and 'implied_volatility' in data:
                smile[strike] = data['implied_volatility']

        return smile

    def _determine_volatility_regime(
        self,
        iv: float,
        hv: float,
        iv_rank: float,
        vrp: float
    ) -> tuple[VolatilityRegime, float]:
        """Determine current volatility regime"""

        # Low volatility regimes
        if iv < 0.12:  # IV below 12%
            if iv > hv * 1.1:  # IV rising relative to HV
                return VolatilityRegime.LOW_RISING, 0.7
            else:
                return VolatilityRegime.LOW_STABLE, 0.8

        # High volatility regimes
        elif iv > 0.25:  # IV above 25%
            if iv < hv * 0.9:  # IV falling relative to HV
                return VolatilityRegime.HIGH_FALLING, 0.7
            else:
                return VolatilityRegime.HIGH_STABLE, 0.8

        # Spike detection
        if len(self.iv_history) > 5:
            recent_avg = self.iv_history.tail(5)['iv'].mean()
            if iv > recent_avg * VOLATILITY_SPIKE_THRESHOLD:
                return VolatilityRegime.SPIKE, 0.9
            elif iv < recent_avg * VOLATILITY_CRUSH_THRESHOLD:
                return VolatilityRegime.CRUSH, 0.9

        # Check for regime transition
        if abs(vrp) > 0.05 and iv_rank > 70:
            return VolatilityRegime.TRANSITIONING, 0.6

        return VolatilityRegime.NORMAL, 0.5

    def _detect_regime_change(self, metrics: VolatilityMetrics) -> VolatilitySignal | None:
        """Detect volatility regime changes"""
        if not self.regime_history:
            self.regime_history.append(metrics.regime)
            return None

        previous_regime = self.regime_history[-1]
        current_regime = metrics.regime

        # Check for significant regime change
        if previous_regime != current_regime and metrics.regime_confidence > REGIME_CHANGE_CONFIDENCE:  # noqa: E501
            self.regime_history.append(current_regime)

            # Generate signal based on regime transition
            if current_regime == VolatilityRegime.SPIKE:
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SHORT_VOLATILITY,
                    direction="SHORT",
                    strength=SignalStrength.STRONG,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 0.8,
                    stop_iv=metrics.implied_volatility * 1.2,
                    expected_edge=0.10,
                    confidence=metrics.regime_confidence,
                    time_horizon=10,
                    recommended_structure="short_straddle",
                    size_recommendation=0.5
                )

            elif current_regime == VolatilityRegime.CRUSH:
                return VolatilitySignal(
                    trade_type=VolatilityTrade.LONG_VOLATILITY,
                    direction="LONG",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 1.3,
                    stop_iv=metrics.implied_volatility * 0.7,
                    expected_edge=0.08,
                    confidence=metrics.regime_confidence,
                    time_horizon=15,
                    recommended_structure="long_strangle",
                    size_recommendation=0.7
                )

        self.regime_history.append(current_regime)
        return None

    def _analyze_iv_hv_divergence(self, metrics: VolatilityMetrics) -> VolatilitySignal | None:
        """Analyze IV/HV divergence for trading opportunities"""
        divergence = metrics.implied_volatility - metrics.historical_volatility
        divergence_ratio = divergence / metrics.historical_volatility

        if abs(divergence_ratio) > self.iv_hv_threshold:
            if divergence_ratio > self.iv_hv_threshold:
                # IV too high relative to HV - sell volatility
                return VolatilitySignal(
                    trade_type=VolatilityTrade.VOLATILITY_ARBITRAGE,
                    direction="SHORT",
                    strength=self._calculate_signal_strength(abs(divergence_ratio)),
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.historical_volatility * 1.1,
                    stop_iv=metrics.implied_volatility * 1.15,
                    expected_edge=divergence * 0.5,
                    confidence=min(0.8, abs(divergence_ratio)),
                    time_horizon=20,
                    recommended_structure="iron_condor",
                    size_recommendation=self._calculate_position_size(divergence_ratio)
                )
            else:
                # IV too low relative to HV - buy volatility
                return VolatilitySignal(
                    trade_type=VolatilityTrade.VOLATILITY_ARBITRAGE,
                    direction="LONG",
                    strength=self._calculate_signal_strength(abs(divergence_ratio)),
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.historical_volatility * 0.9,
                    stop_iv=metrics.implied_volatility * 0.85,
                    expected_edge=abs(divergence) * 0.5,
                    confidence=min(0.8, abs(divergence_ratio)),
                    time_horizon=20,
                    recommended_structure="calendar_spread",
                    size_recommendation=self._calculate_position_size(abs(divergence_ratio))
                )

        return None

    def _analyze_vrp(self, metrics: VolatilityMetrics) -> VolatilitySignal | None:
        """Analyze volatility risk premium"""
        if metrics.volatility_risk_premium > self.vrp_target:
            # Significant VRP - sell volatility
            return VolatilitySignal(
                trade_type=VolatilityTrade.SHORT_VOLATILITY,
                direction="SHORT",
                strength=SignalStrength.MODERATE,
                entry_iv=metrics.implied_volatility,
                target_iv=metrics.realized_volatility,
                stop_iv=metrics.implied_volatility * 1.20,
                expected_edge=metrics.volatility_risk_premium * 0.7,
                confidence=0.65,
                time_horizon=30,
                recommended_structure="put_spread",
                size_recommendation=0.8
            )

        elif metrics.volatility_risk_premium < -self.vrp_target * 0.5:
            # Negative VRP - potential volatility expansion
            return VolatilitySignal(
                trade_type=VolatilityTrade.LONG_VOLATILITY,
                direction="LONG",
                strength=SignalStrength.WEAK,
                entry_iv=metrics.implied_volatility,
                target_iv=metrics.implied_volatility * 1.25,
                stop_iv=metrics.implied_volatility * 0.80,
                expected_edge=abs(metrics.volatility_risk_premium) * 0.5,
                confidence=0.55,
                time_horizon=20,
                recommended_structure="long_butterfly",
                size_recommendation=0.5
            )

        return None

    def _analyze_term_structure(self, metrics: VolatilityMetrics) -> VolatilitySignal | None:
        """Analyze volatility term structure"""
        if len(metrics.term_structure) < 2:
            return None

        # Calculate term structure slope
        terms = sorted(metrics.term_structure.keys())
        if len(terms) >= 2:
            front_month = metrics.term_structure[terms[0]]
            back_month = metrics.term_structure[terms[-1]]
            slope = (back_month - front_month) / front_month

            if abs(slope) > TERM_STRUCTURE_SLOPE_THRESHOLD:
                if slope > TERM_STRUCTURE_SLOPE_THRESHOLD:
                    # Contango - sell front, buy back
                    return VolatilitySignal(
                        trade_type=VolatilityTrade.TERM_STRUCTURE,
                        direction="NEUTRAL",
                        strength=SignalStrength.MODERATE,
                        entry_iv=front_month,
                        target_iv=(front_month + back_month) / 2,
                        stop_iv=front_month * 1.3,
                        expected_edge=abs(slope) * 0.3,
                        confidence=0.60,
                        time_horizon=terms[0],
                        recommended_structure="calendar_spread",
                        size_recommendation=0.6
                    )
                else:
                    # Backwardation - buy front, sell back
                    return VolatilitySignal(
                        trade_type=VolatilityTrade.TERM_STRUCTURE,
                        direction="NEUTRAL",
                        strength=SignalStrength.MODERATE,
                        entry_iv=front_month,
                        target_iv=(front_month + back_month) / 2,
                        stop_iv=front_month * 0.7,
                        expected_edge=abs(slope) * 0.3,
                        confidence=0.60,
                        time_horizon=terms[0],
                        recommended_structure="reverse_calendar",
                        size_recommendation=0.6
                    )

        return None

    def _analyze_skew(self, metrics: VolatilityMetrics) -> VolatilitySignal | None:
        """Analyze volatility skew for opportunities"""
        if abs(metrics.skew) > SKEW_EXTREME_THRESHOLD:
            if metrics.skew > SKEW_EXTREME_THRESHOLD:
                # Extreme positive skew - potential mean reversion
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SKEW_TRADE,
                    direction="SHORT",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 0.9,
                    stop_iv=metrics.implied_volatility * 1.15,
                    expected_edge=0.06,
                    confidence=0.55,
                    time_horizon=15,
                    recommended_structure="put_ratio_spread",
                    size_recommendation=0.5
                )
            else:
                # Extreme negative skew - potential volatility expansion
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SKEW_TRADE,
                    direction="LONG",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 1.1,
                    stop_iv=metrics.implied_volatility * 0.85,
                    expected_edge=0.06,
                    confidence=0.55,
                    time_horizon=15,
                    recommended_structure="call_ratio_spread",
                    size_recommendation=0.5
                )

        return None

    def _calculate_signal_strength(self, divergence: float) -> SignalStrength:
        """Calculate signal strength based on divergence magnitude"""
        abs_div = abs(divergence)
        if abs_div < 0.3:
            return SignalStrength.WEAK
        elif abs_div < 0.5:
            return SignalStrength.MODERATE
        elif abs_div < 0.7:
            return SignalStrength.STRONG
        elif abs_div < 1.0:
            return SignalStrength.VERY_STRONG
        else:
            return SignalStrength.EXTREME

    def _calculate_position_size(self, signal_strength: float) -> float:
        """Calculate position size based on signal strength (RL-enhanced)."""
        # Try RL model first
        if self._rl_vol_enabled and self.current_metrics is not None:
            rl_size = self._get_rl_position_size(
                self.current_metrics, signal_strength
            )
            if rl_size is not None:
                self.logger.debug(f"RL position size: {rl_size:.2f} (signal={signal_strength:.2f})")
                return rl_size
        # Fallback to rule-based
        return min(1.0, max(0.2, signal_strength))

    def _select_best_opportunity(
        self,
        opportunities: list[VolatilitySignal],
        metrics: VolatilityMetrics
    ) -> VolatilitySignal:
        """Select best trading opportunity from multiple signals (RL-enhanced scoring)."""
        # Score each opportunity
        scored_opportunities = []

        for opp in opportunities:
            # Query RL for size/skip recommendation
            rl_size = None
            if self._rl_vol_enabled and metrics is not None:
                rl_size = self._get_rl_position_size(
                    metrics,
                    opp.strength.value / 5.0,
                    opp.expected_edge,
                )

            if rl_size is not None and rl_size == 0.0:
                # RL says skip this opportunity
                continue

            score = 0.0

            # Weight by signal strength
            score += opp.strength.value * 20

            # Weight by confidence
            score += opp.confidence * 100

            # Weight by expected edge
            score += opp.expected_edge * 200

            # Adjust for regime alignment
            if self._is_regime_aligned(opp, metrics.regime):
                score *= 1.2

            # Adjust for IV rank
            if metrics.iv_rank > 70 and opp.direction == "SHORT" or metrics.iv_rank < 30 and opp.direction == "LONG":  # noqa: E501
                score *= 1.1

            # RL size boost: larger recommended size = higher score
            if rl_size is not None:
                score *= (0.5 + rl_size)  # range [0.7 .. 2.0]

            scored_opportunities.append((opp, score))

        if not scored_opportunities:
            # All filtered out by RL — return first opportunity as fallback
            return opportunities[0]

        # Return highest scoring opportunity
        return max(scored_opportunities, key=lambda x: x[1])[0]

    def _is_regime_aligned(self, signal: VolatilitySignal, regime: VolatilityRegime) -> bool:
        """Check if signal aligns with current regime"""
        alignments = {
            VolatilityRegime.HIGH_FALLING: ["SHORT"],
            VolatilityRegime.LOW_RISING: ["LONG"],
            VolatilityRegime.SPIKE: ["SHORT"],
            VolatilityRegime.CRUSH: ["LONG"]
        }

        return signal.direction in alignments.get(regime, [])

    def _create_trade_signal(
        self,
        vol_signal: VolatilitySignal,
        metrics: VolatilityMetrics,
        market_data: dict
    ) -> Signal:
        """Create trading signal from volatility signal"""
        # Map structure to specific strategy
        structure_map = {
            "iron_condor": "IRON_CONDOR",
            "short_straddle": "SHORT_STRADDLE",
            "long_strangle": "LONG_STRANGLE",
            "calendar_spread": "CALENDAR",
            "put_spread": "PUT_SPREAD",
            "long_butterfly": "BUTTERFLY",
            "put_ratio_spread": "RATIO_SPREAD",
            "call_ratio_spread": "RATIO_SPREAD"
        }

        strategy = structure_map.get(vol_signal.recommended_structure, "CUSTOM")

        # Calculate contracts based on vega limit
        target_vega = self.max_vega * vol_signal.size_recommendation
        contracts = self._calculate_contracts_for_vega(target_vega, market_data)

        return Signal(
            action="ENTER",
            strategy=strategy,
            direction=vol_signal.direction,
            contracts=contracts,
            confidence=vol_signal.confidence,
            metadata={
                'trade_type': vol_signal.trade_type.value,
                'entry_iv': vol_signal.entry_iv,
                'target_iv': vol_signal.target_iv,
                'stop_iv': vol_signal.stop_iv,
                'expected_edge': vol_signal.expected_edge,
                'time_horizon': vol_signal.time_horizon,
                'structure': vol_signal.recommended_structure,
                'current_regime': metrics.regime.value,
                'iv_rank': metrics.iv_rank,
                'vrp': metrics.volatility_risk_premium
            }
        )

    def _calculate_contracts_for_vega(self, target_vega: float, market_data: dict) -> int:
        """Calculate number of contracts for target vega exposure"""
        # Get ATM vega from options chain
        chain = market_data.get('options_chain', {})
        atm_strike = market_data['SPY']['last']

        # Find closest ATM option
        atm_vega = 0.50  # Default estimate

        for strike, data in chain.get('calls', {}).items():
            if abs(strike - atm_strike) < 1.0:
                atm_vega = data.get('vega', 0.50)
                break

        # Calculate contracts
        contracts = int(target_vega / (atm_vega * 100))
        return max(1, min(contracts, 20))  # Limit between 1 and 20

    def _manage_positions(
        self,
        metrics: VolatilityMetrics,
        market_data: dict
    ) -> Signal | None:
        """Manage existing volatility positions"""
        for pos_id, position in self.active_positions.items():
            # Update position metrics
            position.current_iv = metrics.implied_volatility
            position.days_held = (datetime.now(timezone.utc) - position.entry_date).days

            # Check exit conditions
            if position.current_iv <= position.target_iv:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Target reached",
                    metadata={'final_iv': position.current_iv}
                )

            elif position.current_iv >= position.stop_iv:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Stop loss",
                    metadata={'final_iv': position.current_iv}
                )

            elif position.days_held >= position.trade_type.time_horizon:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Time exit",
                    metadata={'final_iv': position.current_iv}
                )

        return None

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get strategy performance statistics"""
        return {
            'strategy': self.strategy_name,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / max(1, self.total_trades),
            'total_pnl': self.total_pnl,
            'sharpe_ratio': self.sharpe_ratio,
            'active_positions': len(self.active_positions),
            'current_regime': self.current_metrics.regime.value if self.current_metrics else "UNKNOWN",  # noqa: E501
            'current_iv': self.current_metrics.implied_volatility if self.current_metrics else 0,
            'iv_rank': self.current_metrics.iv_rank if self.current_metrics else 50
        }

    # ------------------------------------------------------------------
    # BaseStrategy abstract contract
    # ------------------------------------------------------------------
    def generate_signals(self, market_data) -> list:
        """Bridge BaseStrategy.generate_signals to analyze_market_conditions."""
        import pandas as pd
        if isinstance(market_data, pd.DataFrame):
            data_dict = market_data.to_dict('list') if not market_data.empty else {}
        else:
            data_dict = market_data if isinstance(market_data, dict) else {}
        signal = self.analyze_market_conditions(data_dict)
        if signal and getattr(signal, 'action', 'HOLD') != 'HOLD':
            from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import TradingSignal
            from uuid import uuid4
            ts = TradingSignal(
                signal_id=str(uuid4()),
                symbol=self.config.get('symbol', 'SPY'),
                action=signal.action,
                quantity=1,
                entry_price=0.0,
                strategy_id='AdaptiveVolatility',
            )
            return [ts]
        return []

    def validate_signal(self, signal, account_value: float = 0) -> bool:
        """Validate a generated signal meets minimum requirements."""
        return bool(signal and getattr(signal, 'symbol', None) and getattr(signal, 'quantity', 0) > 0)  # noqa: E501

    def calculate_position_size(self, signal, account_value: float) -> int:
        """Return contract count scaled by account value and per-trade risk budget."""
        risk_budget = account_value * self.config.get('max_risk_per_trade', 0.02)
        premium_per_contract = getattr(signal, 'entry_price', 1.0) * 100 or 100
        return max(1, int(risk_budget / premium_per_contract))

    def should_exit_position(self, position: dict, current_data: dict) -> bool:
        """Return True when the position should be closed based on P&L thresholds."""
        pnl_pct = current_data.get('pnl_pct', 0.0)
        stop_loss = self.config.get('stop_loss_pct', -1.0)
        profit_target = self.config.get('profit_target_pct', 0.50)
        return pnl_pct <= stop_loss or pnl_pct >= profit_target


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_adaptive_volatility_strategy(config: dict[str, Any] | None = None) -> AdaptiveVolatilityStrategy:  # noqa: E501
    """Factory function to create AdaptiveVolatilityStrategy instance"""
    return AdaptiveVolatilityStrategy(config)
