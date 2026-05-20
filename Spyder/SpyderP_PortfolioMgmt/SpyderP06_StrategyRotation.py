#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderP06_StrategyRotation.py
Group: P (Portfolio Management)
Purpose: Intelligent strategy rotation based on market regime detection
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 17:00:00

Description:
    This module provides sophisticated market regime detection and automatic
    strategy rotation capabilities. It analyzes market conditions to identify
    regimes (trending, range-bound, volatile, crisis), maps optimal strategies
    to each regime, manages smooth transitions between strategies, and tracks
    performance attribution by market regime to optimize strategy selection.

Key Features:
    - Multi-factor market regime detection
    - Strategy-regime performance mapping
    - Smooth transition management
    - Whipsaw prevention with regime persistence
    - Position scaling during transitions
    - Performance attribution by regime
    - Adaptive learning from regime history
    - Integration with allocation and risk systems
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import numpy as np
import pandas as pd
from datetime import datetime, UTC
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import threading
from pathlib import Path
from types import SimpleNamespace
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats  # noqa: E402
from sklearn.mixture import GaussianMixture  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from Spyder.SpyderF_Analysis import SpyderF20_Indicators as talib  # noqa: E402

# Institutional Analytics
try:
    import empyrical
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

try:
    import riskfolio as rp  # noqa: F401
    HAS_RISKFOLIO = True
except ImportError:
    HAS_RISKFOLIO = False

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402
from Spyder.SpyderI_Integration.SpyderI06_AgentMessageBus import MessagePriority  # noqa: E402

try:
    from Spyder.SpyderX_Agents.SpyderX16_MetaCoordinator import MetaCoordinator
except ImportError:
    MetaCoordinator = None  # type: ignore

# ==============================================================================
# HELPERS
# ==============================================================================

def _json_default(obj):
    """JSON serialization helper: converts datetime/Enum/dataclass for json.dump."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    return str(obj)


def _ns(d):
    """Recursively convert dicts to SimpleNamespace for attribute-compatible access."""
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in d.items()})
    if isinstance(d, list):
        return [_ns(i) for i in d]
    return d


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market regimes
REGIME_FEATURES = [
    'returns', 'volatility', 'volume', 'vix', 'term_structure',
    'momentum', 'mean_reversion', 'correlation', 'skew', 'kurtosis'
]

# Regime persistence requirements
MIN_REGIME_DAYS = 3  # Minimum days in regime before switching
CONFIRMATION_PERIODS = 2  # Periods to confirm regime change
REGIME_CONFIDENCE_THRESHOLD = 0.65  # Minimum confidence for regime change

# Strategy mapping to regimes (D01-D26)
REGIME_STRATEGY_MAP = {
    'TRENDING_UP': [
        'D13_MACrossover', 'D06_BullPutSpread', 'D20_VerticalSpreadOptimizer',
        'D08_OpeningRangeBreakout', 'D03_CreditSpread'
    ],
    'TRENDING_DOWN': [
        'D07_BearCallSpread', 'D13_MACrossover', 'D03_CreditSpread',
        'D20_VerticalSpreadOptimizer', 'D16_RatioSpreads'
    ],
    'RANGE_BOUND': [
        'D02_IronCondor', 'D10_IronButterfly', 'D14_CalendarSpread',
        'D21_DoubleCalendar', 'D12_RSIMeanReversion'
    ],
    'HIGH_VOLATILITY': [
        'D05_Straddle', 'D15_StraddleStrangle', 'D22_AdaptiveVolatility',
        'D04_ZeroDTE', 'D11_SpecializedZeroDTE', 'D26_GammaScalper'
    ],
    'LOW_VOLATILITY': [
        'D02_IronCondor', 'D18_EvolvedCreditSpread', 'D19_JadeLizard',
        'D14_CalendarSpread', 'D03_CreditSpread'
    ],
    'CRISIS': [
        'D09_GreeksBased', 'D01_BaseStrategy', 'D07_BearCallSpread',
        'D16_RatioSpreads', 'D22_AdaptiveVolatility'
    ],
    'RECOVERY': [
        'D06_BullPutSpread', 'D03_CreditSpread', 'D17_DiagonalSpread',
        'D20_VerticalSpreadOptimizer', 'D05_Straddle'
    ]
}

# Transition rules
TRANSITION_SPEED = {
    'IMMEDIATE': 1.0,  # 100% immediate transition
    'FAST': 0.5,  # 50% per period
    'MODERATE': 0.25,  # 25% per period
    'SLOW': 0.1  # 10% per period
}

# Performance tracking
REGIME_LOOKBACK = 252  # Days for regime analysis
PERFORMANCE_WINDOW = 60  # Days for performance attribution

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classifications"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    CRISIS = "crisis"
    RECOVERY = "recovery"
    TRANSITIONAL = "transitional"

class RegimeIndicator(Enum):
    """Indicators for regime detection"""
    TREND = "trend"
    VOLATILITY = "volatility"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLUME = "volume"
    CORRELATION = "correlation"
    SENTIMENT = "sentiment"

class TransitionType(Enum):
    """Types of strategy transitions"""
    IMMEDIATE = "immediate"  # Crisis or risk event
    GRADUAL = "gradual"  # Normal regime change
    SCALED = "scaled"  # Position scaling
    HEDGED = "hedged"  # With hedging

class RotationReason(Enum):
    """Reasons for strategy rotation"""
    REGIME_CHANGE = "regime_change"
    PERFORMANCE = "performance"
    RISK_LIMIT = "risk_limit"
    CORRELATION = "correlation"
    MANUAL = "manual"
    REBALANCE = "rebalance"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RegimeState:
    """Current market regime state"""
    regime: MarketRegime
    confidence: float
    indicators: dict[RegimeIndicator, float]
    start_time: datetime
    duration_days: int
    strength: float  # 0-1 regime strength
    volatility: float
    trend: float
    features: dict[str, float]

@dataclass
class RegimeTransition:
    """Regime transition event"""
    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_time: datetime
    confidence: float
    transition_type: TransitionType
    expected_duration: int  # Days
    indicators_changed: list[RegimeIndicator]

@dataclass
class StrategyPerformance:
    """Strategy performance in a regime"""
    strategy_id: str
    regime: MarketRegime
    total_return: float
    avg_daily_return: float
    volatility: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    trade_count: int
    days_active: int
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))

@dataclass
class RotationPlan:
    """Plan for strategy rotation"""
    timestamp: datetime
    reason: RotationReason
    current_strategies: list[str]
    target_strategies: list[str]
    transition_type: TransitionType
    transition_speed: float
    position_adjustments: dict[str, float]  # strategy -> scale factor
    expected_impact: float
    risk_score: float
    approved: bool = False

@dataclass
class RotationEvent:
    """Record of completed rotation"""
    plan: RotationPlan
    execution_time: datetime
    strategies_added: list[str]
    strategies_removed: list[str]
    strategies_scaled: dict[str, float]
    actual_impact: float
    success: bool
    errors: list[str] = field(default_factory=list)

# ==============================================================================
# MAIN STRATEGY ROTATION CLASS
# ==============================================================================
class StrategyRotation:
    """
    Intelligent strategy rotation based on market regime detection.

    Analyzes market conditions to identify regimes and automatically
    rotates strategies to optimize performance in each regime.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Strategy Rotation system"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Market data
        self.market_data = deque(maxlen=REGIME_LOOKBACK)
        self.price_data = deque(maxlen=REGIME_LOOKBACK)
        self.volume_data = deque(maxlen=REGIME_LOOKBACK)
        self.vix_data = deque(maxlen=REGIME_LOOKBACK)

        # Regime detection
        self.current_regime = MarketRegime.RANGE_BOUND
        self.regime_confidence = 0.5
        self.regime_history = deque(maxlen=1000)
        self.regime_start = datetime.now(UTC)
        self.regime_features = {}

        # Strategy performance tracking
        self.strategy_performance = defaultdict(lambda: defaultdict(list))
        self.regime_performance = defaultdict(list)
        self.active_strategies = []

        # Rotation management
        self.rotation_history = deque(maxlen=100)
        self.pending_rotations = []
        self.in_transition = False
        self.transition_progress = {}

        # Machine learning models
        self.regime_classifier = None
        self.performance_predictor = None
        self.scaler = StandardScaler()

        # Integration
        self.allocator = None
        self.coordinator = None
        self.message_bus = None

        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()

        # Initialize components
        self._initialize_models()
        self._load_historical_data()

        self.logger.info("Strategy Rotation system initialized")

    def _initialize_models(self):
        """Initialize machine learning models"""
        try:
            # Regime classifier
            self.regime_classifier = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

            # GMM for volatility regimes
            self.volatility_model = GaussianMixture(
                n_components=3,  # Low, Normal, High volatility
                covariance_type='full',
                random_state=42
            )

            self.logger.info("ML models initialized")

        except Exception as e:
            self.logger.error("Failed to initialize models: %s", e)

    def _load_historical_data(self):
        """Load historical regime and performance data"""
        try:
            history_file = Path("data/portfolio/regime_history.json")
            # Backward-compat: migrate from legacy .pkl if .json not present
            if not history_file.exists():
                legacy = history_file.with_suffix('.pkl')
                if legacy.exists():
                    import joblib as _joblib
                    with open(legacy, 'rb') as _f:
                        _data = _joblib.load(_f)
                    history_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(history_file, 'w', encoding='utf-8') as _f:
                        json.dump(_data, _f, default=_json_default, indent=2)
            if history_file.exists():
                with open(history_file, encoding='utf-8') as f:
                    data = json.load(f)
                    self.regime_history = deque(
                        (_ns(item) for item in data['regimes']), maxlen=1000
                    )
                    self.rotation_history = deque(
                        (_ns(item) for item in data['rotations']), maxlen=100
                    )

                    # Load performance data
                    if 'performance' in data:
                        self.strategy_performance = data['performance']

                    self.logger.info("Loaded %s historical regimes", len(self.regime_history))
        except Exception as e:
            self.logger.warning("Could not load historical data: %s", e)

    def update_market_data(
        self,
        price: float,
        volume: float,
        vix: float,
        additional_data: dict[str, float] | None = None
    ):
        """
        Update market data for regime detection.

        Args:
            price: Current SPY price
            volume: Trading volume
            vix: VIX level
            additional_data: Other market indicators
        """
        with self._lock:
            timestamp = datetime.now(UTC)

            # Store raw data
            self.price_data.append(price)
            self.volume_data.append(volume)
            self.vix_data.append(vix)

            # Store complete market data
            market_point = {
                'timestamp': timestamp,
                'price': price,
                'volume': volume,
                'vix': vix
            }

            if additional_data:
                market_point.update(additional_data)

            self.market_data.append(market_point)

            # Check for regime change if enough data
            if len(self.price_data) >= 20:
                self._detect_regime_change()

    def _detect_regime_change(self):
        """Detect if market regime has changed"""
        try:
            # Calculate regime features
            features = self._calculate_regime_features()

            # Get regime prediction
            regime, confidence = self._predict_regime(features)

            # Check if regime changed
            if regime != self.current_regime:
                # Check persistence requirement
                if self._check_regime_persistence(regime, confidence):
                    self._initiate_regime_change(regime, confidence)
            else:
                # Update confidence in current regime
                self.regime_confidence = confidence

        except Exception as e:
            self.logger.error("Regime detection failed: %s", e)

    def _calculate_regime_features(self) -> dict[str, float]:
        """Calculate features for regime detection"""
        features = {}

        try:
            prices = np.array(self.price_data)
            volumes = np.array(self.volume_data)
            vix = np.array(self.vix_data)

            # Returns
            returns = np.diff(prices) / prices[:-1]
            features['return_mean'] = np.mean(returns)
            features['return_std'] = np.std(returns)

            # Trend
            if len(prices) >= 20:
                sma_20 = np.mean(prices[-20:])
                sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
                features['trend'] = (prices[-1] - sma_20) / sma_20
                features['trend_strength'] = (sma_20 - sma_50) / sma_50 if sma_50 > 0 else 0

            # Volatility
            features['volatility'] = np.std(returns) * np.sqrt(252)
            features['vix_level'] = vix[-1] if len(vix) > 0 else 20
            features['vix_change'] = (vix[-1] - np.mean(vix[-5:])) / np.mean(vix[-5:]) if len(vix) >= 5 else 0  # noqa: E501

            # Volume
            features['volume_ratio'] = volumes[-1] / np.mean(volumes) if len(volumes) > 0 else 1
            features['volume_trend'] = np.polyfit(range(len(volumes)), volumes, 1)[0] if len(volumes) > 1 else 0  # noqa: E501

            # Momentum
            if len(prices) >= 14:
                rsi = talib.RSI(prices, timeperiod=14)
                features['rsi'] = rsi[-1] if not np.isnan(rsi[-1]) else 50

                macd, signal, _ = talib.MACD(prices)
                features['macd_signal'] = (macd[-1] - signal[-1]) if len(macd) > 0 and not np.isnan(macd[-1]) else 0  # noqa: E501

            # Mean reversion
            if len(prices) >= 20:
                bb_upper, bb_middle, bb_lower = talib.BBANDS(prices, timeperiod=20)
                features['bb_position'] = (prices[-1] - bb_middle[-1]) / (bb_upper[-1] - bb_lower[-1]) if not np.isnan(bb_middle[-1]) else 0  # noqa: E501

            # Distribution
            if len(returns) > 0:
                features['skew'] = stats.skew(returns)
                features['kurtosis'] = stats.kurtosis(returns)

            # Regime strength indicators
            features['trend_consistency'] = self._calculate_trend_consistency(prices)
            features['volatility_regime'] = self._classify_volatility_regime(returns)

            self.regime_features = features
            return features

        except Exception as e:
            self.logger.error("Feature calculation failed: %s", e)
            return {}

    def _calculate_trend_consistency(self, prices: np.ndarray) -> float:
        """Calculate trend consistency metric"""
        if len(prices) < 10:
            return 0.5

        # Count consecutive up/down days
        returns = np.diff(prices)
        positive = returns > 0

        # Find runs of same sign
        runs = []
        current_run = 1
        for i in range(1, len(positive)):
            if positive[i] == positive[i-1]:
                current_run += 1
            else:
                runs.append(current_run)
                current_run = 1
        runs.append(current_run)

        # Longer runs indicate stronger trend
        avg_run = np.mean(runs)
        consistency = min(avg_run / 5, 1.0)  # Normalize to 0-1

        return consistency

    def _classify_volatility_regime(self, returns: np.ndarray) -> float:
        """Classify volatility regime using GMM"""
        if len(returns) < 30:
            return 0.5

        try:
            # Fit GMM if not fitted
            vol_data = np.abs(returns).reshape(-1, 1)
            if not hasattr(self.volatility_model, 'converged_'):
                self.volatility_model.fit(vol_data)

            # Predict current volatility regime
            current_vol = np.std(returns[-10:]).reshape(1, -1)
            probs = self.volatility_model.predict_proba(current_vol)[0]

            # Return weighted score (0=low, 0.5=normal, 1=high)
            regime_score = probs[0] * 0 + probs[1] * 0.5 + probs[2] * 1.0
            return regime_score

        except Exception:
            return 0.5

    def _predict_regime(self, features: dict[str, float]) -> tuple[MarketRegime, float]:
        """Predict market regime from features"""
        # Rule-based regime detection (can be replaced with ML model)

        trend = features.get('trend', 0)
        volatility = features.get('volatility', 0.15)
        vix = features.get('vix_level', 20)
        rsi = features.get('rsi', 50)
        trend_consistency = features.get('trend_consistency', 0.5)

        confidence = 0.5

        # Crisis detection
        if vix > 35 or volatility > 0.35:
            regime = MarketRegime.CRISIS
            confidence = min(vix / 40, 1.0)

        # High volatility
        elif vix > 25 or volatility > 0.25:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = 0.7

        # Low volatility
        elif vix < 15 and volatility < 0.12:
            regime = MarketRegime.LOW_VOLATILITY
            confidence = 0.7

        # Trending up
        elif trend > 0.02 and trend_consistency > 0.6 and rsi > 50:
            regime = MarketRegime.TRENDING_UP
            confidence = min(trend_consistency, 0.85)

        # Trending down
        elif trend < -0.02 and trend_consistency > 0.6 and rsi < 50:
            regime = MarketRegime.TRENDING_DOWN
            confidence = min(trend_consistency, 0.85)

        # Recovery
        elif self.current_regime == MarketRegime.CRISIS and vix < 25:
            regime = MarketRegime.RECOVERY
            confidence = 0.6

        # Range bound (default)
        else:
            regime = MarketRegime.RANGE_BOUND
            confidence = 0.6

        return regime, confidence

    def _check_regime_persistence(self, new_regime: MarketRegime, confidence: float) -> bool:
        """Check if regime change meets persistence requirements"""
        # Need minimum confidence
        if confidence < REGIME_CONFIDENCE_THRESHOLD:
            return False

        # Check if we've been in current regime long enough
        days_in_regime = (datetime.now(UTC) - self.regime_start).days
        # Look for confirmation over multiple periods
        # This is simplified - would check recent predictions
        return days_in_regime >= MIN_REGIME_DAYS

    def _initiate_regime_change(self, new_regime: MarketRegime, confidence: float):
        """Initiate regime change and strategy rotation"""
        self.logger.info(
            f"Regime change detected: {self.current_regime.value} -> {new_regime.value} "
            f"(confidence: {confidence:.2%})"
        )

        # Record transition
        transition = RegimeTransition(
            from_regime=self.current_regime,
            to_regime=new_regime,
            transition_time=datetime.now(UTC),
            confidence=confidence,
            transition_type=self._determine_transition_type(new_regime),
            expected_duration=self._estimate_regime_duration(new_regime),
            indicators_changed=self._get_changed_indicators()
        )

        # Update regime
        old_regime = self.current_regime
        self.current_regime = new_regime
        self.regime_confidence = confidence
        self.regime_start = datetime.now(UTC)

        # Record in history
        regime_state = RegimeState(
            regime=new_regime,
            confidence=confidence,
            indicators={},  # Would populate with actual indicators
            start_time=datetime.now(UTC),
            duration_days=0,
            strength=confidence,
            volatility=self.regime_features.get('volatility', 0),
            trend=self.regime_features.get('trend', 0),
            features=self.regime_features.copy()
        )
        self.regime_history.append(regime_state)

        # Plan strategy rotation
        rotation_plan = self._create_rotation_plan(old_regime, new_regime, transition)

        # Execute rotation
        self._execute_rotation(rotation_plan)

        # Send notification
        self._broadcast_regime_change(new_regime, confidence)

    def _determine_transition_type(self, new_regime: MarketRegime) -> TransitionType:
        """Determine type of transition based on regime"""
        if new_regime == MarketRegime.CRISIS:
            return TransitionType.IMMEDIATE
        elif new_regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.RECOVERY]:
            return TransitionType.HEDGED
        else:
            return TransitionType.GRADUAL

    def _estimate_regime_duration(self, regime: MarketRegime) -> int:
        """Estimate expected duration of regime in days"""
        # Based on historical averages
        historical_durations = {
            MarketRegime.TRENDING_UP: 60,
            MarketRegime.TRENDING_DOWN: 45,
            MarketRegime.RANGE_BOUND: 30,
            MarketRegime.HIGH_VOLATILITY: 20,
            MarketRegime.LOW_VOLATILITY: 40,
            MarketRegime.CRISIS: 15,
            MarketRegime.RECOVERY: 35
        }
        return historical_durations.get(regime, 30)

    def _get_changed_indicators(self) -> list[RegimeIndicator]:
        """Get indicators that triggered regime change"""
        # Simplified - would analyze which indicators changed most
        return [RegimeIndicator.TREND, RegimeIndicator.VOLATILITY]

    def _create_rotation_plan(
        self,
        from_regime: MarketRegime,
        to_regime: MarketRegime,
        transition: RegimeTransition
    ) -> RotationPlan:
        """Create strategy rotation plan"""
        # Get optimal strategies for new regime
        target_strategies = self._get_optimal_strategies(to_regime)

        # Determine position adjustments
        adjustments = self._calculate_position_adjustments(
            self.active_strategies,
            target_strategies,
            transition.transition_type
        )

        # Calculate transition speed
        speed_map = {
            TransitionType.IMMEDIATE: TRANSITION_SPEED['IMMEDIATE'],
            TransitionType.GRADUAL: TRANSITION_SPEED['MODERATE'],
            TransitionType.SCALED: TRANSITION_SPEED['SLOW'],
            TransitionType.HEDGED: TRANSITION_SPEED['FAST']
        }
        speed = speed_map.get(transition.transition_type, TRANSITION_SPEED['MODERATE'])

        # Estimate impact
        impact = self._estimate_rotation_impact(adjustments)

        # Calculate risk score
        risk_score = self._calculate_rotation_risk(from_regime, to_regime, adjustments)

        plan = RotationPlan(
            timestamp=datetime.now(UTC),
            reason=RotationReason.REGIME_CHANGE,
            current_strategies=self.active_strategies.copy(),
            target_strategies=target_strategies,
            transition_type=transition.transition_type,
            transition_speed=speed,
            position_adjustments=adjustments,
            expected_impact=impact,
            risk_score=risk_score,
            approved=risk_score < 0.7  # Auto-approve if risk acceptable
        )

        return plan

    def _get_optimal_strategies(self, regime: MarketRegime) -> list[str]:
        """Get optimal strategies for a regime"""
        # Get base strategies for regime
        regime_key = regime.value.upper()
        base_strategies = REGIME_STRATEGY_MAP.get(regime_key, [])

        # Rank by historical performance in this regime
        if regime in self.regime_performance:
            performance_data = self.regime_performance[regime]

            # Sort by Sharpe ratio in regime
            ranked = sorted(
                performance_data,
                key=lambda x: x.sharpe_ratio,
                reverse=True
            )

            # Take top performers
            optimal = [p.strategy_id for p in ranked[:7]]

            # Add base strategies if not enough
            for strategy in base_strategies:
                if strategy not in optimal and len(optimal) < 10:
                    optimal.append(strategy)

            return optimal[:10]  # Max 10 strategies

        # Default to mapped strategies
        return base_strategies[:7]

    def _calculate_position_adjustments(
        self,
        current: list[str],
        target: list[str],
        transition_type: TransitionType
    ) -> dict[str, float]:
        """Calculate position adjustments for rotation"""
        adjustments = {}

        # Strategies to remove
        for strategy in current:
            if strategy not in target:
                if transition_type == TransitionType.IMMEDIATE:
                    adjustments[strategy] = 0.0  # Close immediately
                else:
                    adjustments[strategy] = 0.5  # Scale down 50%

        # Strategies to add
        for strategy in target:
            if strategy not in current:
                if transition_type == TransitionType.IMMEDIATE:
                    adjustments[strategy] = 1.0  # Full position
                else:
                    adjustments[strategy] = 0.5  # Start with 50%

        # Strategies to maintain
        for strategy in set(current) & set(target):
            adjustments[strategy] = 1.0  # Keep full position

        return adjustments

    def _estimate_rotation_impact(self, adjustments: dict[str, float]) -> float:
        """Estimate market impact of rotation"""
        # Simplified impact model
        changes = sum(abs(1.0 - adj) for adj in adjustments.values())
        impact = changes * 0.001  # 10 bps per full position change
        return min(impact, 0.01)  # Cap at 1%

    def _calculate_rotation_risk(
        self,
        from_regime: MarketRegime,
        to_regime: MarketRegime,
        adjustments: dict[str, float]
    ) -> float:
        """Calculate risk score for rotation"""
        risk = 0.0

        # Risk from regime uncertainty
        risk += (1 - self.regime_confidence) * 0.3

        # Risk from transition magnitude
        transition_size = len([a for a in adjustments.values() if a < 1.0])
        risk += (transition_size / 10) * 0.3

        # Risk from market conditions
        if self.regime_features.get('volatility', 0) > 0.25:
            risk += 0.2

        # Risk from regime type
        if to_regime in [MarketRegime.CRISIS, MarketRegime.HIGH_VOLATILITY]:
            risk += 0.2

        return min(risk, 1.0)

    def _execute_rotation(self, plan: RotationPlan):
        """Execute strategy rotation plan"""
        if not plan.approved:
            self.logger.warning(f"Rotation plan not approved (risk: {plan.risk_score:.2f})")
            return

        try:
            self.logger.info(
                f"Executing rotation: {len(plan.current_strategies)} -> "
                f"{len(plan.target_strategies)} strategies"
            )

            # Mark as in transition
            self.in_transition = True

            # Initialize transition progress
            for strategy in plan.position_adjustments:
                self.transition_progress[strategy] = 0.0

            # Create rotation event
            event = RotationEvent(
                plan=plan,
                execution_time=datetime.now(UTC),
                strategies_added=[],
                strategies_removed=[],
                strategies_scaled={},
                actual_impact=0.0,
                success=False
            )

            # Execute adjustments
            for strategy, adjustment in plan.position_adjustments.items():
                if adjustment == 0.0:
                    # Remove strategy
                    if strategy in self.active_strategies:
                        self.active_strategies.remove(strategy)
                        event.strategies_removed.append(strategy)

                elif adjustment == 1.0 and strategy not in self.active_strategies:
                    # Add strategy
                    self.active_strategies.append(strategy)
                    event.strategies_added.append(strategy)

                else:
                    # Scale strategy
                    event.strategies_scaled[strategy] = adjustment
                    self.transition_progress[strategy] = adjustment

            # Update allocator if available
            if self.allocator:
                self._update_allocator(plan.target_strategies)

            # Mark success
            event.success = True
            event.actual_impact = plan.expected_impact  # Would measure actual

            # Record event
            self.rotation_history.append(event)

            # Clear transition state
            self.in_transition = False
            self.transition_progress.clear()

            self.logger.info(
                f"Rotation completed: Added {len(event.strategies_added)}, "
                f"Removed {len(event.strategies_removed)}, "
                f"Scaled {len(event.strategies_scaled)}"
            )

        except Exception as e:
            self.logger.error("Rotation execution failed: %s", e)
            self.error_handler.handle_error(e, {"plan": asdict(plan)})
            self.in_transition = False

    def _update_allocator(self, strategies: list[str]):
        """Update allocator with new strategy list"""
        try:
            # This would interface with P05_MultiStrategyAllocator
            # to update eligible strategies and trigger rebalancing
            pass
        except Exception as e:
            self.logger.error("Allocator update failed: %s", e)

    def _broadcast_regime_change(self, regime: MarketRegime, confidence: float):
        """Broadcast regime change via message bus"""
        if self.message_bus:
            self.message_bus.publish(
                topic="regime.change",
                sender="StrategyRotation",
                priority=MessagePriority.HIGH,
                payload={
                    'regime': regime.value,
                    'confidence': confidence,
                    'timestamp': datetime.now(UTC).isoformat(),
                    'active_strategies': self.active_strategies,
                    'features': self.regime_features
                },
            )

    def update_strategy_performance(
        self,
        strategy_id: str,
        regime: MarketRegime,
        daily_return: float,
        trades: int = 0
    ):
        """
        Update strategy performance in regime.

        Args:
            strategy_id: Strategy identifier
            regime: Current regime
            daily_return: Today's return
            trades: Number of trades
        """
        with self._lock:
            # Store raw performance
            self.strategy_performance[strategy_id][regime].append({
                'date': datetime.now(UTC).date(),
                'return': daily_return,
                'trades': trades
            })

            # Update aggregated performance
            self._update_regime_performance(strategy_id, regime)

    def _update_regime_performance(self, strategy_id: str, regime: MarketRegime):
        """Update aggregated performance metrics"""
        perf_data = self.strategy_performance[strategy_id][regime]

        if len(perf_data) < 5:
            return  # Need minimum data

        # Calculate metrics
        returns = [p['return'] for p in perf_data]

        perf = StrategyPerformance(
            strategy_id=strategy_id,
            regime=regime,
            total_return=np.prod([1 + r for r in returns]) - 1,
            avg_daily_return=np.mean(returns),
            volatility=np.std(returns) * np.sqrt(252),
            sharpe_ratio=0,  # Would calculate properly
            win_rate=len([r for r in returns if r > 0]) / len(returns),
            max_drawdown=self._calculate_max_drawdown(returns),
            trade_count=sum(p['trades'] for p in perf_data),
            days_active=len(perf_data)
        )

        # Calculate Sharpe
        if perf.volatility > 0:
            perf.sharpe_ratio = (perf.avg_daily_return * 252) / perf.volatility

        # Store or update
        regime_perfs = self.regime_performance[regime]

        # Find and update or append
        updated = False
        for i, existing in enumerate(regime_perfs):
            if existing.strategy_id == strategy_id:
                regime_perfs[i] = perf
                updated = True
                break

        if not updated:
            regime_perfs.append(perf)

    def _calculate_max_drawdown(self, returns: list[float]) -> float:
        """Calculate maximum drawdown from returns"""
        cumulative = np.cumprod([1 + r for r in returns])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(np.min(drawdown))

    def get_regime_analysis(self) -> dict[str, Any]:
        """Get comprehensive regime analysis"""
        # Calculate regime statistics
        regime_stats = {}
        for regime_state in self.regime_history:
            regime = regime_state.regime
            if regime not in regime_stats:
                regime_stats[regime] = {
                    'count': 0,
                    'total_days': 0,
                    'avg_confidence': 0,
                    'transitions_to': defaultdict(int)
                }

            regime_stats[regime]['count'] += 1
            regime_stats[regime]['total_days'] += regime_state.duration_days

        # Get performance by regime
        performance_summary = {}
        for regime, perfs in self.regime_performance.items():
            if perfs:
                performance_summary[regime.value] = {
                    'top_strategies': [
                        {
                            'strategy': p.strategy_id,
                            'sharpe': p.sharpe_ratio,
                            'return': p.avg_daily_return * 252
                        }
                        for p in sorted(perfs, key=lambda x: x.sharpe_ratio, reverse=True)[:5]
                    ],
                    'avg_sharpe': np.mean([p.sharpe_ratio for p in perfs]),
                    'avg_return': np.mean([p.avg_daily_return * 252 for p in perfs])
                }

        return {
            'current_regime': self.current_regime.value,
            'confidence': self.regime_confidence,
            'regime_start': self.regime_start.isoformat(),
            'days_in_regime': (datetime.now(UTC) - self.regime_start).days,
            'active_strategies': self.active_strategies,
            'in_transition': self.in_transition,
            'regime_features': self.regime_features,
            'regime_statistics': {
                k.value: v for k, v in regime_stats.items()
            },
            'performance_by_regime': performance_summary,
            'recent_rotations': len(self.rotation_history),
            'transition_progress': self.transition_progress
        }

    def get_strategy_recommendations(
        self,
        regime: MarketRegime | None = None
    ) -> list[dict[str, Any]]:
        """
        Get strategy recommendations for regime.

        Args:
            regime: Specific regime or use current

        Returns:
            List of recommended strategies with scores
        """
        if regime is None:
            regime = self.current_regime

        recommendations = []

        # Get strategies for regime
        strategies = self._get_optimal_strategies(regime)

        for i, strategy_id in enumerate(strategies):
            # Get performance in regime
            perf_in_regime = None
            if regime in self.regime_performance:
                for perf in self.regime_performance[regime]:
                    if perf.strategy_id == strategy_id:
                        perf_in_regime = perf
                        break

            recommendation = {
                'rank': i + 1,
                'strategy': strategy_id,
                'regime_fit': 1.0 - (i / 10),  # Decreasing fit score
                'historical_sharpe': perf_in_regime.sharpe_ratio if perf_in_regime else 0,
                'historical_return': perf_in_regime.avg_daily_return * 252 if perf_in_regime else 0,
                'confidence': self.regime_confidence * (1.0 - i/20),
                'recommended_allocation': 1.0 / len(strategies)  # Equal weight default
            }

            recommendations.append(recommendation)

        return recommendations

    def force_rotation(
        self,
        target_strategies: list[str],
        reason: RotationReason = RotationReason.MANUAL
    ) -> RotationEvent:
        """
        Force strategy rotation (manual override).

        Args:
            target_strategies: Target strategy list
            reason: Reason for rotation

        Returns:
            RotationEvent with results
        """
        self.logger.info("Manual rotation initiated: %s", reason.value)

        # Create rotation plan
        plan = RotationPlan(
            timestamp=datetime.now(UTC),
            reason=reason,
            current_strategies=self.active_strategies.copy(),
            target_strategies=target_strategies,
            transition_type=TransitionType.GRADUAL,
            transition_speed=TRANSITION_SPEED['FAST'],
            position_adjustments=self._calculate_position_adjustments(
                self.active_strategies,
                target_strategies,
                TransitionType.GRADUAL
            ),
            expected_impact=0.005,
            risk_score=0.3,
            approved=True  # Manual override approved
        )

        # Execute
        self._execute_rotation(plan)

        # Return last event
        return self.rotation_history[-1] if self.rotation_history else None

    def backtest_regime_strategy(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, Any]:
        """
        Backtest regime-based strategy selection.

        Uses empyrical for validated performance metrics when available.

        Args:
            start_date: Backtest start
            end_date: Backtest end

        Returns:
            Backtest results with validated metrics.
        """
        # Filter regime/rotation history to date range
        regime_changes = [r for r in self.regime_history
                         if r.start_time >= start_date and r.start_time <= end_date]
        rotations = [r for r in self.rotation_history
                    if r.execution_time >= start_date and r.execution_time <= end_date]

        results = {
            'period': f"{start_date.date()} to {end_date.date()}",
            'total_regimes': len(self.regime_history),
            'regime_changes': len(regime_changes),
            'rotations': len(rotations),
        }

        # Calculate real metrics from strategy performance history
        all_returns = []
        for perf_data in self.strategy_performance.values():
            if isinstance(perf_data, dict) and 'returns' in perf_data:
                all_returns.extend(perf_data['returns'])
            elif hasattr(perf_data, 'returns_history'):
                all_returns.extend(list(perf_data.returns_history))

        if all_returns and len(all_returns) >= 10:
            ret_series = pd.Series(all_returns)

            if HAS_EMPYRICAL:
                # Institutional-grade metrics via empyrical
                results['sharpe_ratio'] = float(empyrical.sharpe_ratio(ret_series, period='daily'))
                results['max_drawdown'] = float(empyrical.max_drawdown(ret_series))
                results['total_return'] = float(empyrical.cum_returns_final(ret_series))
                results['annual_return'] = float(empyrical.annual_return(ret_series, period='daily'))  # noqa: E501
                results['annual_volatility'] = float(empyrical.annual_volatility(ret_series, period='daily'))  # noqa: E501
                results['sortino_ratio'] = float(empyrical.sortino_ratio(ret_series, period='daily'))  # noqa: E501
                results['calmar_ratio'] = float(empyrical.calmar_ratio(ret_series, period='daily'))
                results['var_5'] = float(empyrical.value_at_risk(ret_series, cutoff=0.05))
                results['cvar_5'] = float(empyrical.conditional_value_at_risk(ret_series, cutoff=0.05))  # noqa: E501
                results['stability'] = float(empyrical.stability_of_timeseries(ret_series))
            else:
                # Basic calculations without empyrical
                total_return = float(np.prod(1 + ret_series) - 1)
                annual_vol = float(ret_series.std() * np.sqrt(252))
                annual_return = float(ret_series.mean() * 252)
                sharpe = annual_return / annual_vol if annual_vol > 0 else 0

                # Max drawdown
                cumulative = (1 + ret_series).cumprod()
                running_max = cumulative.cummax()
                drawdown = (cumulative - running_max) / running_max
                max_dd = float(drawdown.min())

                results['sharpe_ratio'] = sharpe
                results['max_drawdown'] = max_dd
                results['total_return'] = total_return
                results['annual_return'] = annual_return
                results['annual_volatility'] = annual_vol

            # Win rate from actual trades
            winning = sum(1 for r in all_returns if r > 0)
            results['win_rate'] = winning / len(all_returns)
            results['total_trades'] = len(all_returns)
            results['metrics_source'] = 'empyrical' if HAS_EMPYRICAL else 'local'
        else:
            # Insufficient data — calculate from regime history metadata
            results['win_rate'] = 0.0
            results['sharpe_ratio'] = 0.0
            results['max_drawdown'] = 0.0
            results['total_return'] = 0.0
            results['metrics_source'] = 'insufficient_data'

        return results

    def shutdown(self):
        """Shutdown rotation system and save state"""
        self._shutdown.set()

        # Save history
        try:
            history_file = Path("data/portfolio/regime_history.json")
            history_file.parent.mkdir(parents=True, exist_ok=True)

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'regimes': list(self.regime_history),
                    'rotations': list(self.rotation_history),
                    'performance': dict(self.strategy_performance),
                    'timestamp': datetime.now(UTC)
                }, f, default=_json_default, indent=2)

            self.logger.info("Regime history saved")
        except Exception as e:
            self.logger.error("Failed to save history: %s", e)

        self.logger.info("Strategy Rotation shutdown complete")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_strategy_rotation(config: dict[str, Any] | None = None) -> StrategyRotation:
    """Create and initialize StrategyRotation instance"""
    return StrategyRotation(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Create rotation system
    rotation = create_strategy_rotation()


    # Simulate market data updates

    # Normal market
    for _ in range(20):
        rotation.update_market_data(
            price=450 + np.random.normal(0, 2),
            volume=100000000 + np.random.normal(0, 10000000),
            vix=18 + np.random.normal(0, 1)
        )

    # Trending up
    for i in range(20):
        rotation.update_market_data(
            price=450 + i * 0.5 + np.random.normal(0, 1),
            volume=120000000,
            vix=15 + np.random.normal(0, 0.5)
        )

    # High volatility
    for _ in range(20):
        rotation.update_market_data(
            price=460 + np.random.normal(0, 5),
            volume=150000000,
            vix=28 + np.random.normal(0, 2)
        )

    # Get regime analysis
    analysis = rotation.get_regime_analysis()


    # Get recommendations
    recommendations = rotation.get_strategy_recommendations()

    for _rec in recommendations[:5]:
        pass

    # Test forced rotation

    new_strategies = ['D02_IronCondor', 'D05_Straddle', 'D14_CalendarSpread']
    event = rotation.force_rotation(new_strategies, RotationReason.MANUAL)

    if event:
        pass

    # Shutdown
    rotation.shutdown()
