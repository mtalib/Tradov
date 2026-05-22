#!/usr/bin/env python3
from __future__ import annotations
import uuid
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD02_IronCondor.py
Purpose: Iron Condor strategy with consolidated multi-leg infrastructure (Updated)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 16:30:00

Module Description:
    Iron Condor strategy implementation focused on strategy-specific entry/exit logic
    and market analysis. Generic multi-leg construction, order management, and Greeks
    calculations have been moved to SpyderD32_MultiLegStrategyCoordinator for
    consolidation and code reuse across all multi-leg strategies.

CONSOLIDATION UPDATE:
    Generic multi-leg infrastructure REMOVED and consolidated into D32_MultiLegStrategyCoordinator.
    This module now focuses exclusively on Iron Condor specific trading logic:
    - Iron Condor entry criteria and market condition analysis
    - Strike selection methodology specific to Iron Condor
    - Profit targets and stop loss rules for Iron Condor
    - Adjustment techniques specific to Iron Condor strategy
    - Exit criteria and position management for Iron Condor

Key Features:
    • Iron Condor specific entry conditions (high IV, range-bound market)
    • Strike selection at 16-20 delta puts/calls for optimal risk/reward
    • Dynamic profit targets (25-50% of credit received)
    • Stop loss at 2x credit received or delta breach
    • Time decay management (close at 21-45 DTE)
    • Iron Condor specific adjustment techniques
    • Integration with D32 for multi-leg execution

Removed Infrastructure:
    • Generic multi-leg order management - Now in D32
    • Combined Greeks calculations - Now in D32
    • Multi-leg position sizing - Now in D32
    • Generic P&L calculations - Now in D32
    • Position group validation - Now in D32
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import UTC, date, datetime, timedelta  # noqa: E402
import re  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402
from typing import Any  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from enum import Enum, auto  # noqa: E402

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

try:
    ET_TZ = ZoneInfo('America/New_York')
except Exception:  # pragma: no cover - defensive tzdata fallback
    ET_TZ = UTC

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy  # noqa: E402
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile  # noqa: E402
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (  # noqa: E402
    SignalStrength, SignalType, TradingSignal,
)

# Integration with consolidated multi-leg coordinator
try:
    from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
        MultiLegStrategyCoordinator, MultiLegStrategyType, get_multileg_coordinator  # noqa: F401
    )
    MULTILEG_COORDINATOR_AVAILABLE = True
except ImportError:
    try:
        # Compatibility path for legacy PYTHONPATH/module layouts.
        from SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
            MultiLegStrategyCoordinator, MultiLegStrategyType, get_multileg_coordinator  # noqa: F401,E501
        )
        MULTILEG_COORDINATOR_AVAILABLE = True
    except ImportError:
        MULTILEG_COORDINATOR_AVAILABLE = False

# Integration with event management
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType  # noqa: F401
    EVENT_MANAGER_AVAILABLE = True
except ImportError:
    EVENT_MANAGER_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Iron Condor specific parameters
IC_MIN_IV_RANK = 40                    # Minimum IV rank for IC entry
IC_OPTIMAL_IV_RANK = 60                # Optimal IV rank for IC
IC_MAX_IV_RANK = 80                    # Maximum IV rank (too high)

IC_DELTA_TARGET_PUT = -0.16            # Target delta for short put (16 delta)
IC_DELTA_TARGET_CALL = 0.16            # Target delta for short call (16 delta)
IC_DELTA_TOLERANCE = 0.04              # Tolerance for delta selection

IC_MIN_DTE = 21                        # Minimum days to expiration
IC_MAX_DTE = 45                        # Maximum days to expiration
IC_OPTIMAL_DTE = 30                    # Optimal days to expiration

IC_PROFIT_TARGET_MIN = 0.25            # 25% profit target
IC_PROFIT_TARGET_MAX = 0.50            # 50% profit target
IC_STOP_LOSS_MULTIPLIER = 2.0          # 2x credit received

IC_MIN_CREDIT = 0.30                   # Minimum credit per contract
IC_MAX_WIDTH = 10.0                    # Maximum spread width
MAX_ACTIVE_SETUPS = 20                 # Trim active_setups beyond this count

# Market condition thresholds
IC_MIN_EXPECTED_MOVE_RATIO = 0.8       # Minimum expected move vs spread width
IC_MAX_EXPECTED_MOVE_RATIO = 1.2       # Maximum expected move vs spread width
IC_VOLATILITY_SKEW_MAX = 0.05          # Maximum acceptable volatility skew

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class IronCondorState(Enum):
    """Iron Condor position states"""
    ANALYZING = auto()
    READY_TO_ENTER = auto()
    ENTERING = auto()
    ACTIVE = auto()
    MONITORING = auto()
    PROFIT_TARGET_HIT = auto()
    STOP_LOSS_HIT = auto()
    ADJUSTING = auto()
    CLOSING = auto()
    CLOSED = auto()
    ERROR = auto()

class IronCondorAdjustmentType(Enum):
    """Types of Iron Condor adjustments"""
    ROLL_PUT_SIDE = "roll_put_side"
    ROLL_CALL_SIDE = "roll_call_side"
    CONVERT_TO_BUTTERFLY = "convert_to_butterfly"
    CLOSE_UNTESTED_SIDE = "close_untested_side"
    ROLL_ENTIRE_STRUCTURE = "roll_entire_structure"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class IronCondorSetup:
    """Iron Condor strategy setup parameters"""
    underlying_price: float
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    expiration_date: datetime
    days_to_expiry: int
    expected_credit: float
    max_profit: float
    max_loss: float
    probability_of_profit: float
    iv_rank: float
    expected_move: float
    setup_quality_score: float

@dataclass
class IronCondorAnalysis:
    """Iron Condor market analysis results"""
    market_suitable: bool
    iv_analysis: dict[str, float]
    volatility_skew: float
    expected_move_analysis: dict[str, float]
    trend_analysis: dict[str, Any]
    optimal_strikes: dict[str, float] | None
    setup_recommendation: str
    confidence_score: float
    risk_warnings: list[str]

# ==============================================================================
# MAIN IRON CONDOR STRATEGY CLASS
# ==============================================================================
class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy with consolidated multi-leg infrastructure.

    Focuses exclusively on Iron Condor specific trading logic while leveraging
    the consolidated multi-leg coordinator (D26) for infrastructure operations.

    This implementation handles:
    - Iron Condor specific entry criteria
    - Strike selection methodology
    - Profit targets and risk management
    - Strategy-specific adjustments
    - Exit criteria and timing
    """

    def __init__(self, event_manager: EventManager = None,
                 risk_profile: RiskProfile = None, config: dict[str, Any] = None):
        """Initialize Iron Condor strategy"""

        # Initialize base strategy
        super().__init__(
            name="Iron Condor Strategy",
            strategy_type="iron_condor",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {}
        )

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize multi-leg coordinator integration
        self.multileg_coordinator = None
        if MULTILEG_COORDINATOR_AVAILABLE:
            try:
                self.multileg_coordinator = get_multileg_coordinator()
                self.logger.debug("✅ Connected to MultiLegStrategyCoordinator")
            except Exception as e:
                self.logger.error("Failed to connect to coordinator: %s", e)
        else:
            self.logger.warning("❌ MultiLegStrategyCoordinator not available")

        # Iron Condor specific configuration
        self.min_iv_rank = self.config.get('min_iv_rank', IC_MIN_IV_RANK)
        self.profit_target = self.config.get('profit_target', IC_PROFIT_TARGET_MIN)
        self.stop_loss_multiplier = self.config.get('stop_loss_multiplier', IC_STOP_LOSS_MULTIPLIER)
        self.min_dte = self.config.get('min_dte', IC_MIN_DTE)
        self.max_dte = self.config.get('max_dte', IC_MAX_DTE)
        self.min_credit = self.config.get('min_credit', IC_MIN_CREDIT)

        # Strategy state
        self.current_analysis: IronCondorAnalysis | None = None
        self.active_setups: list[IronCondorSetup] = []
        self.strategy_state = IronCondorState.ANALYZING
        self._last_no_signal_reason_key = ""

        # Performance tracking
        self.performance_metrics = {
            'total_ic_trades': 0,
            'winning_ic_trades': 0,
            'total_ic_profit': 0.0,
            'avg_ic_hold_days': 0.0,
            'ic_win_rate': 0.0,
            'avg_credit_captured': 0.0,
            'max_consecutive_losses': 0,
            'best_ic_trade': 0.0,
            'worst_ic_trade': 0.0
        }

        self.logger.debug("🎯 IronCondorStrategy initialized with D32 integration")

    @staticmethod
    def _format_diagnostic_float(value: Any) -> str:
        """Format optional numeric diagnostics for structured no-entry logs."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "n/a"
        if np.isnan(numeric):
            return "n/a"
        return f"{numeric:.4f}"

    def _build_no_signal_blockers(self, analysis: IronCondorAnalysis) -> list[str]:
        """Summarize why the current market state did not yield an Iron Condor entry."""
        blockers = list(analysis.risk_warnings or [])

        def _add(token: str) -> None:
            if token and token not in blockers:
                blockers.append(token)

        iv_analysis = analysis.iv_analysis or {}
        expected_move_analysis = analysis.expected_move_analysis or {}
        trend_analysis = analysis.trend_analysis or {}

        if not iv_analysis.get("iv_data_available", False):
            _add("iv_data_unavailable")
        elif not iv_analysis.get("iv_suitable_for_ic", False):
            _add("iv_rank_out_of_range")

        if not expected_move_analysis.get("expected_move_suitable_for_ic", False):
            _add("expected_move_out_of_range")

        if not trend_analysis.get("trend_suitable_for_ic", False):
            _add("trend_not_range_bound")

        if float(analysis.confidence_score or 0.0) <= 0.0:
            _add("confidence_zero")

        return blockers

    def _log_no_signal_blockers(self, analysis: IronCondorAnalysis, blockers: list[str]) -> None:
        """Emit a deduplicated summary when Iron Condor declines to enter."""
        reason_key = "|".join(blockers)
        if reason_key == self._last_no_signal_reason_key:
            return

        self._last_no_signal_reason_key = reason_key
        iv_analysis = analysis.iv_analysis or {}
        expected_move_analysis = analysis.expected_move_analysis or {}
        trend_analysis = analysis.trend_analysis or {}

        self.logger.info(
            "IronCondor no entry: blockers=%s iv_available=%s iv_rank=%s expected_move_pct=%s range_bound=%s confidence=%.2f",
            ",".join(blockers),
            bool(iv_analysis.get("iv_data_available", False)),
            self._format_diagnostic_float(iv_analysis.get("iv_rank")),
            self._format_diagnostic_float(expected_move_analysis.get("expected_move_percent")),
            bool(trend_analysis.get("is_range_bound", False)),
            float(analysis.confidence_score or 0.0),
        )

    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """Generate Iron Condor entry signals from current market data.

        Calls the synchronous analysis pipeline and emits one TradingSignal when
        the Iron Condor conditions are met.  Returns an empty list otherwise.
        """
        if market_data is None or market_data.empty:
            return []
        try:
            analysis = self.analyze_iron_condor_opportunity(market_data)
            if not analysis.market_suitable or analysis.confidence_score <= 0.0:
                blockers = self._build_no_signal_blockers(analysis)
                analysis.risk_warnings = blockers
                self.current_analysis = analysis
                if blockers:
                    self._log_no_signal_blockers(analysis, blockers)
                return []

            score = analysis.confidence_score
            if score >= 0.8:
                strength = SignalStrength.VERY_STRONG
            elif score >= 0.6:
                strength = SignalStrength.STRONG
            elif score >= 0.4:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            current_price = float(market_data["close"].iloc[-1])
            now = datetime.now(UTC)
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.SELL,
                symbol="SPY",
                strength=strength,
                confidence=score,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit=0.0,
                position_size=1,
                timestamp=now,
                expires_at=now + timedelta(minutes=30),
                metadata={
                    "strategy_tag":        "iron_condor",
                    "strategy_type":       "iron_condor",
                    "optimal_strikes":     analysis.optimal_strikes,
                    "iv_rank":             analysis.iv_analysis.get("iv_rank"),
                    "confidence_score":    score,
                    "setup_recommendation": analysis.setup_recommendation,
                    "risk_warnings":       analysis.risk_warnings,
                },
            )
            self._last_no_signal_reason_key = ""
            return [signal]
        except Exception as exc:
            self.logger.error("generate_signals failed: %s", exc, exc_info=True)
            return []

    def validate_signal(self, signal: Any) -> bool:
        """Basic safety gate for external signals."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: Any) -> int:
        """Use provided size when available, otherwise default to one contract."""
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else 1

    def should_exit_position(self, position: Any,
                             market_data: pd.DataFrame) -> tuple[bool, str]:
        """Generic stop/take-profit exit adapter for BaseStrategy contract."""
        if market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        stop_loss = getattr(position, "stop_loss", None)
        take_profit = getattr(position, "take_profit", None)
        position_type = str(getattr(getattr(position, "position_type", ""), "value", "")).lower()

        if stop_loss is not None:
            if position_type == "short":
                if current_price >= stop_loss:
                    return True, "stop_loss"
            elif current_price <= stop_loss:
                return True, "stop_loss"

        if take_profit is not None:
            if position_type == "short":
                if current_price <= take_profit:
                    return True, "take_profit"
            elif current_price >= take_profit:
                return True, "take_profit"

        return False, ""

    # ==========================================================================
    # IRON CONDOR SPECIFIC MARKET ANALYSIS
    # ==========================================================================

    def analyze_iron_condor_opportunity(self, market_data: pd.DataFrame,
                                        option_chain: pd.DataFrame = None) -> IronCondorAnalysis:
        """
        Analyze market conditions for Iron Condor entry.

        This is Iron Condor specific analysis - generic analysis is in D32.
        """
        try:
            current_price = market_data['close'].iloc[-1]

            # IV Analysis (Iron Condor specific)
            iv_analysis = self._analyze_iv_for_iron_condor(market_data)

            # Volatility skew analysis
            volatility_skew = self._calculate_volatility_skew(option_chain) if option_chain is not None else 0.0  # noqa: E501

            # Expected move analysis
            expected_move_analysis = self._analyze_expected_move_for_ic(market_data, current_price)

            # Trend analysis (Iron Condor prefers range-bound)
            trend_analysis = self._analyze_trend_for_iron_condor(market_data)

            # Overall suitability
            market_suitable = self._assess_market_suitability_for_ic(
                iv_analysis, expected_move_analysis, trend_analysis
            )

            # Find optimal strikes if suitable
            optimal_strikes = None
            setup_recommendation = ""
            confidence_score = 0.0
            risk_warnings = []

            if market_suitable:
                # Confidence score and recommendation do not require an option chain.
                setup_recommendation, confidence_score = self._generate_ic_recommendation(
                    iv_analysis, expected_move_analysis, trend_analysis
                )
                if option_chain is not None:
                    optimal_strikes = self._find_optimal_iron_condor_strikes(
                        current_price, option_chain, iv_analysis
                    )
                    risk_warnings = self._identify_ic_risk_warnings(
                        iv_analysis, expected_move_analysis, volatility_skew
                    )

            analysis = IronCondorAnalysis(
                market_suitable=market_suitable,
                iv_analysis=iv_analysis,
                volatility_skew=volatility_skew,
                expected_move_analysis=expected_move_analysis,
                trend_analysis=trend_analysis,
                optimal_strikes=optimal_strikes,
                setup_recommendation=setup_recommendation,
                confidence_score=confidence_score,
                risk_warnings=risk_warnings
            )

            self.current_analysis = analysis
            return analysis

        except Exception as e:
            self.logger.error("Iron Condor analysis failed: %s", e)
            self.error_handler.handle_error(e, {"method": "analyze_iron_condor_opportunity"})

            return IronCondorAnalysis(
                market_suitable=False,
                iv_analysis={},
                volatility_skew=0.0,
                expected_move_analysis={},
                trend_analysis={},
                optimal_strikes=None,
                setup_recommendation="Analysis failed",
                confidence_score=0.0,
                risk_warnings=["Analysis error occurred"]
            )

    def _analyze_iv_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze implied volatility specifically for Iron Condor strategy.

        Returns iv_data_available=False (no synthetic fallback) when IV is absent
        so that _assess_market_suitability_for_ic can gate on real data.
        """
        _no_iv = {
            'current_iv': float('nan'),
            'iv_rank': float('nan'),
            'iv_suitable_for_ic': False,
            'iv_quality_score': 0.0,
            'iv_trend': 'unknown',
            'iv_data_available': False,
        }
        try:
            iv_col = market_data.get('iv') if isinstance(market_data, pd.DataFrame) else None
            if iv_col is None or iv_col.dropna().empty:
                return _no_iv

            current_iv = float(iv_col.iloc[-1])
            if np.isnan(current_iv):
                return _no_iv

            iv_history = iv_col.tail(252)
            iv_rank_col = market_data.get('iv_rank') if isinstance(market_data, pd.DataFrame) else None
            iv_rank_hint = None
            if iv_rank_col is not None and hasattr(iv_rank_col, 'dropna'):
                iv_rank_series = iv_rank_col.dropna()
                if not iv_rank_series.empty:
                    try:
                        iv_rank_hint = float(iv_rank_series.iloc[-1])
                    except (TypeError, ValueError):
                        iv_rank_hint = None

            if iv_rank_hint is not None and not np.isnan(iv_rank_hint):
                if 0.0 <= iv_rank_hint <= 1.0:
                    iv_rank_hint *= 100.0
                iv_rank = iv_rank_hint
            else:
                iv_history_non_null = iv_history.dropna()
                if iv_history_non_null.empty:
                    iv_rank = 50.0
                elif iv_history_non_null.nunique() <= 1:
                    # D31 may inject one live ATM-IV snapshot across every row in the
                    # rolling market frame. That flat series is not real IV history;
                    # treating it as history collapses rank to 0. Use a neutral rank
                    # until S07 provides a true IVR hint.
                    iv_rank = 50.0
                else:
                    iv_rank = float((current_iv > iv_history_non_null).sum() / len(iv_history_non_null) * 100)

            return {
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_suitable_for_ic': IC_MIN_IV_RANK <= iv_rank <= IC_MAX_IV_RANK,
                'iv_quality_score': self._calculate_iv_quality_score(current_iv, iv_rank),
                'iv_trend': 'rising' if current_iv > float(iv_history.mean()) else 'falling',
                'iv_data_available': True,
            }

        except Exception as e:
            self.logger.error("IV analysis failed: %s", e)
            return _no_iv

    def _calculate_iv_quality_score(self, current_iv: float, iv_rank: float) -> float:
        """Calculate IV quality score for Iron Condor (0.0 to 1.0)"""
        try:
            # Optimal IV rank for Iron Condor is around 60
            iv_rank_score = 1.0 - abs(iv_rank - IC_OPTIMAL_IV_RANK) / IC_OPTIMAL_IV_RANK

            # Prefer moderate to high IV for premium selling
            iv_level_score = min(1.0, current_iv / 0.25) if current_iv > 0.15 else 0.0

            # Combined score
            return (iv_rank_score * 0.6 + iv_level_score * 0.4)

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IV analysis failed: %s", e)
            return 0.0

    def _analyze_expected_move_for_ic(self, market_data: pd.DataFrame,
                                    current_price: float) -> dict[str, float]:
        """Analyze expected move for Iron Condor positioning"""
        try:
            # Calculate volatility-based expected move
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]
            days_to_expiry = 30  # Default assumption

            # Expected move calculation
            expected_move = current_price * current_iv * np.sqrt(days_to_expiry / 365)
            expected_move_pct = expected_move / current_price

            # Iron Condor specific analysis
            analysis = {
                'expected_move_dollars': expected_move,
                'expected_move_percent': expected_move_pct,
                'expected_move_suitable_for_ic': 0.02 <= expected_move_pct <= 0.06,  # 2-6%
                'move_quality_score': self._calculate_move_quality_score(expected_move_pct)
            }

            return analysis

        except Exception as e:
            self.logger.error("Expected move analysis failed: %s", e)
            return {
                'expected_move_dollars': 10.0,
                'expected_move_percent': 0.03,
                'expected_move_suitable_for_ic': True,
                'move_quality_score': 0.5
            }

    def _calculate_move_quality_score(self, expected_move_pct: float) -> float:
        """Calculate expected move quality for Iron Condor"""
        try:
            # Optimal expected move for IC is 3-4%
            optimal_move = 0.035

            if 0.02 <= expected_move_pct <= 0.06:
                # Within acceptable range
                deviation = abs(expected_move_pct - optimal_move)
                return max(0.0, 1.0 - deviation / 0.02)
            else:
                # Outside acceptable range
                return 0.0

        except (ValueError, ZeroDivisionError, TypeError) as e:
            self.logger.warning("Move quality calculation failed: %s", e)
            return 0.0

    def _analyze_trend_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze trend conditions for Iron Condor (prefers range-bound)"""
        try:
            # Calculate trend indicators
            closes = market_data['close'].tail(20)
            sma_20 = closes.mean()
            current_price = closes.iloc[-1]

            # Price vs moving average
            price_vs_sma = (current_price - sma_20) / sma_20

            # Volatility of recent returns
            returns = closes.pct_change().dropna()
            return_volatility = returns.std()

            # Range-bound detection
            high_20 = market_data['high'].tail(20).max()
            low_20 = market_data['low'].tail(20).min()
            range_size = (high_20 - low_20) / current_price

            # Range-bound is ideal for Iron Condor
            is_range_bound = range_size < 0.08 and abs(price_vs_sma) < 0.02

            return {
                'trend_strength': abs(price_vs_sma),
                'is_range_bound': is_range_bound,
                'range_size_percent': range_size,
                'return_volatility': return_volatility,
                'trend_suitable_for_ic': is_range_bound,
                'trend_quality_score': 1.0 if is_range_bound else 0.5
            }

        except Exception as e:
            self.logger.error("Trend analysis failed: %s", e)
            return {
                'trend_strength': 0.01,
                'is_range_bound': True,
                'range_size_percent': 0.05,
                'return_volatility': 0.01,
                'trend_suitable_for_ic': True,
                'trend_quality_score': 0.8
            }

    def _assess_market_suitability_for_ic(self, iv_analysis: dict,
                                        expected_move_analysis: dict,
                                        trend_analysis: dict) -> bool:
        """Assess overall market suitability for Iron Condor.

        Requires real IV data — returns False immediately if IV is unavailable
        to prevent entries based on synthetic fallback values.
        """
        try:
            if not iv_analysis.get('iv_data_available', False):
                return False
            iv_suitable = iv_analysis.get('iv_suitable_for_ic', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ic', False)
            trend_suitable = trend_analysis.get('trend_suitable_for_ic', False)
            return iv_suitable and move_suitable and trend_suitable

        except (KeyError, TypeError, AttributeError) as e:
            self.logger.warning("Market condition check failed: %s", e)
            return False

    # ==========================================================================
    # IRON CONDOR SPECIFIC STRIKE SELECTION
    # ==========================================================================

    def _find_optimal_iron_condor_strikes(self, current_price: float,
                                        option_chain: pd.DataFrame,
                                        iv_analysis: dict) -> dict[str, float] | None:
        """Find optimal strike selection for Iron Condor"""
        try:
            if option_chain is None or option_chain.empty:
                return None

            # Target deltas for Iron Condor
            target_put_delta = IC_DELTA_TARGET_PUT
            target_call_delta = IC_DELTA_TARGET_CALL

            # Find strikes closest to target deltas
            puts = option_chain[option_chain['option_type'] == 'put'].copy()
            calls = option_chain[option_chain['option_type'] == 'call'].copy()

            # Short put strike (around 16 delta)
            short_put_candidates = puts[
                (puts['delta'] >= target_put_delta - IC_DELTA_TOLERANCE) &
                (puts['delta'] <= target_put_delta + IC_DELTA_TOLERANCE)
            ]

            # Short call strike (around 16 delta)
            short_call_candidates = calls[
                (calls['delta'] >= target_call_delta - IC_DELTA_TOLERANCE) &
                (calls['delta'] <= target_call_delta + IC_DELTA_TOLERANCE)
            ]

            if short_put_candidates.empty or short_call_candidates.empty:
                return None

            # Select best strikes based on premium and liquidity
            short_put_strike = self._select_best_short_strike(short_put_candidates, 'put')
            short_call_strike = self._select_best_short_strike(short_call_candidates, 'call')

            # Find long strikes (protection)
            long_put_strike = self._find_long_protection_strike(
                puts, short_put_strike, 'put', current_price
            )
            long_call_strike = self._find_long_protection_strike(
                calls, short_call_strike, 'call', current_price
            )

            if not all([short_put_strike, long_put_strike, short_call_strike, long_call_strike]):
                return None

            # Validate strike selection
            if not self._validate_iron_condor_strikes(
                long_put_strike, short_put_strike, short_call_strike, long_call_strike
            ):
                return None

            return {
                'long_put_strike': long_put_strike,
                'short_put_strike': short_put_strike,
                'short_call_strike': short_call_strike,
                'long_call_strike': long_call_strike
            }

        except Exception as e:
            self.logger.error("Strike selection failed: %s", e)
            return None

    def _select_best_short_strike(self, candidates: pd.DataFrame, option_type: str) -> float | None:
        """Select best short strike from candidates using min-max normalised scoring.

        Single-candidate short-circuit avoids spurious normalisation artefacts.
        Tied dimensions return 0.5 so that no column can dominate by coincidence.
        """
        try:
            if candidates.empty:
                return None

            # Short-circuit when only one candidate
            if len(candidates) == 1:
                return float(candidates.iloc[0]['strike'])

            candidates = candidates.copy()

            def _norm(series: pd.Series) -> pd.Series:
                """Min-max normalise; return 0.5 for all-equal columns."""
                vmin, vmax = series.min(), series.max()
                if vmax - vmin <= 0:
                    return pd.Series(0.5, index=series.index)
                return (series - vmin) / (vmax - vmin)

            _zero = pd.Series(0.0, index=candidates.index)
            bid_col = candidates['bid'] if 'bid' in candidates.columns else _zero
            vol_col = candidates['volume'] if 'volume' in candidates.columns else _zero
            oi_col  = candidates['open_interest'] if 'open_interest' in candidates.columns else _zero

            candidates['score'] = (
                _norm(bid_col) * 0.4
                + _norm(vol_col) * 0.3
                + _norm(oi_col)  * 0.3
            )

            best_candidate = candidates.loc[candidates['score'].idxmax()]
            return float(best_candidate['strike'])

        except Exception as e:
            self.logger.error("Best strike selection failed: %s", e)
            return None

    def _find_long_protection_strike(self, options: pd.DataFrame, short_strike: float,
                                   option_type: str, current_price: float) -> float | None:
        """Find appropriate long protection strike"""
        try:
            if option_type == 'put':
                # Long put should be below short put
                candidates = options[options['strike'] < short_strike]
                target_width = min(IC_MAX_WIDTH, short_strike * 0.05)  # 5% of strike or max width
                target_strike = short_strike - target_width

                if candidates.empty:
                    return None

                # Find closest to target
                candidates['distance'] = abs(candidates['strike'] - target_strike)
                best_candidate = candidates.loc[candidates['distance'].idxmin()]

            else:  # call
                # Long call should be above short call
                candidates = options[options['strike'] > short_strike]
                target_width = min(IC_MAX_WIDTH, short_strike * 0.05)
                target_strike = short_strike + target_width

                if candidates.empty:
                    return None

                candidates['distance'] = abs(candidates['strike'] - target_strike)
                best_candidate = candidates.loc[candidates['distance'].idxmin()]

            return best_candidate['strike']

        except Exception as e:
            self.logger.error("Long protection strike selection failed: %s", e)
            return None

    def _validate_iron_condor_strikes(self, long_put: float, short_put: float,
                                    short_call: float, long_call: float) -> bool:
        """Validate Iron Condor strike selection"""
        try:
            # Basic structure validation
            if not (long_put < short_put < short_call < long_call):
                return False

            # Check spread widths
            put_width = short_put - long_put
            call_width = long_call - short_call

            if put_width <= 0 or call_width <= 0:
                return False

            if max(put_width, call_width) > IC_MAX_WIDTH:
                return False

            # Check spread width balance (shouldn't be too imbalanced)
            width_ratio = max(put_width, call_width) / min(put_width, call_width)
            return width_ratio <= 2.0  # Maximum 2:1 ratio


        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("Strike validation failed: %s", e)
            return False

    # ==========================================================================
    # IRON CONDOR SPECIFIC EXECUTION INTERFACE
    # ==========================================================================

    async def create_iron_condor_position(self, setup: IronCondorSetup) -> str | None:
        """Create Iron Condor position using D26 coordinator"""
        try:
            if not self.multileg_coordinator:
                self.logger.error("MultiLegStrategyCoordinator not available")
                return None

            # Create the Iron Condor structure using D26
            structure = await self.multileg_coordinator.analyze_multileg_opportunity(
                market_data=None,  # Would need market data
                strategy_type=MultiLegStrategyType.IRON_CONDOR
            )

            if not structure:
                self.logger.warning("Could not create Iron Condor structure")
                return None

            # Execute the position through D26
            position_id = await self.multileg_coordinator.execute_multileg_strategy(structure)

            if position_id:
                self.active_setups.append(setup)
                # Trim to prevent unbounded growth
                if len(self.active_setups) > MAX_ACTIVE_SETUPS:
                    self.active_setups = self.active_setups[-MAX_ACTIVE_SETUPS:]
                self.strategy_state = IronCondorState.ACTIVE
                self.logger.info("✅ Iron Condor position created: %s", position_id)

            return position_id

        except Exception as e:
            self.logger.error("Iron Condor position creation failed: %s", e)
            return None

    # ==========================================================================
    # IRON CONDOR SPECIFIC MANAGEMENT
    # ==========================================================================

    def should_close_iron_condor(self, position_data: dict) -> tuple[bool, str]:
        """Iron Condor specific exit criteria"""
        try:
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            days_held = position_data.get('days_held', 0)
            dte = position_data.get('days_to_expiry', 30)

            # Profit target hit
            if current_pnl_pct >= self.profit_target:
                return True, "Profit target achieved"

            # Stop loss hit
            if current_pnl_pct <= -self.stop_loss_multiplier:
                return True, "Stop loss triggered"

            # Time-based exit (close with 7-10 DTE)
            if dte <= 7:
                return True, "Time decay exit - approaching expiration"

            # Early profit taking if very profitable
            if current_pnl_pct >= 0.75 and days_held >= 7:
                return True, "Early profit taking - 75% profit achieved"

            return False, "Hold position"

        except Exception as e:
            self.logger.error("Exit criteria analysis failed: %s", e)
            return True, "Exit due to analysis error"

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        """Best-effort datetime coercion for mixed runtime payloads."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value

        text = str(value).strip()
        if not text:
            return None

        normalized = text.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(normalized, fmt)
                except ValueError:
                    continue
        return None

    @classmethod
    def _coerce_date(cls, value: Any) -> date | None:
        """Best-effort date coercion for expiration fields."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        parsed = cls._coerce_datetime(value)
        if parsed is not None:
            return parsed.date()
        return None

    @staticmethod
    def _extract_occ_expiration(symbol: str) -> date | None:
        """Parse OCC option expirations from contract symbols when needed."""
        match = re.search(r'(\d{6})[CP]\d{8}$', str(symbol or '').upper())
        if match is None:
            return None

        try:
            return datetime.strptime(match.group(1), '%y%m%d').date()
        except ValueError:
            return None

    @classmethod
    def _days_held(cls, opened_at: Any) -> int:
        """Calculate holding duration without forcing timezone awareness."""
        opened = cls._coerce_datetime(opened_at)
        if opened is None:
            return 0

        if opened.tzinfo is not None:
            now = cls._now_et().astimezone(opened.tzinfo)
        else:
            now = cls._now_et().replace(tzinfo=None)
        return max(0, (now - opened).days)

    @staticmethod
    def _now_et() -> datetime:
        """Return the current ET timestamp for DTE and holding-period math."""
        return datetime.now(ET_TZ)

    @classmethod
    def _days_to_expiry(cls, expiration: Any, symbol: str) -> int:
        """Calculate DTE from explicit payload fields or the option symbol."""
        expiry = cls._coerce_date(expiration)
        if expiry is None:
            expiry = cls._extract_occ_expiration(symbol)
        if expiry is None:
            return IC_MAX_DTE

        return max(0, (expiry - cls._now_et().date()).days)

    @staticmethod
    def _build_exit_position_data(position: Any) -> dict[str, Any]:
        """Normalize ExitMonitor position views into Iron Condor exit inputs."""
        raw = position.raw if isinstance(getattr(position, 'raw', None), dict) else {}
        quantity = float(getattr(position, 'quantity', 0.0) or raw.get('quantity', 0.0) or 0.0)
        entry_price = float(
            getattr(position, 'cost_basis', 0.0)
            or raw.get('cost_basis', 0.0)
            or raw.get('entry_price', 0.0)
            or 0.0
        )
        multiplier = float(raw.get('multiplier', 100.0) or 100.0)
        unrealized_pnl = float(
            getattr(position, 'unrealized_pnl', 0.0)
            or raw.get('unrealized_pnl', 0.0)
            or 0.0
        )
        entry_notional = abs(entry_price * quantity * multiplier)
        pnl_percent = (unrealized_pnl / entry_notional) if entry_notional > 0.0 else 0.0

        return {
            'symbol': str(getattr(position, 'symbol', '') or raw.get('symbol', '') or ''),
            'quantity': quantity,
            'entry_price': entry_price,
            'current_price': float(
                getattr(position, 'current_price', 0.0)
                or raw.get('current_price', 0.0)
                or 0.0
            ),
            'unrealized_pnl': unrealized_pnl,
            'pnl_percent': pnl_percent,
            'days_held': 0,
            'days_to_expiry': IC_MAX_DTE,
        }

    def check_exit(self, position: Any) -> str | None:
        """Adapt authoritative runtime leg positions to Iron Condor exit rules."""
        position_data = self._build_exit_position_data(position)
        raw = position.raw if isinstance(getattr(position, 'raw', None), dict) else {}

        position_data['days_held'] = self._days_held(raw.get('opened_at'))
        position_data['days_to_expiry'] = self._days_to_expiry(
            raw.get('expiration') or raw.get('expiration_date'),
            position_data['symbol'],
        )

        if position_data['days_to_expiry'] <= 7:
            return 'close'

        # Keep PnL-based exits on short premium legs only; closing a long wing
        # independently while the short leg is still open would remove protection.
        if position_data['quantity'] >= 0:
            return None

        should_close, _reason = self.should_close_iron_condor(position_data)
        return 'close' if should_close else None

    def suggest_iron_condor_adjustment(self, position_data: dict) -> IronCondorAdjustmentType | None:  # noqa: E501
        """Suggest Iron Condor specific adjustments"""
        try:
            underlying_price = position_data.get('underlying_price', 0)
            short_put_strike = position_data.get('short_put_strike', 0)
            short_call_strike = position_data.get('short_call_strike', 0)
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            dte = position_data.get('days_to_expiry', 30)

            # Only consider adjustments if losing money and have time
            if current_pnl_pct >= -0.25 or dte <= 14:
                return None

            # Determine which side is being challenged
            put_side_challenged = underlying_price < short_put_strike * 1.02
            call_side_challenged = underlying_price > short_call_strike * 0.98

            if put_side_challenged:
                return IronCondorAdjustmentType.ROLL_PUT_SIDE
            elif call_side_challenged:
                return IronCondorAdjustmentType.ROLL_CALL_SIDE
            else:
                # Both sides safe - maybe convert to butterfly for more credit
                return IronCondorAdjustmentType.CONVERT_TO_BUTTERFLY

        except Exception as e:
            self.logger.error("Adjustment analysis failed: %s", e)
            return None

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _calculate_volatility_skew(self, option_chain: pd.DataFrame) -> float:
        """Calculate volatility skew for Iron Condor analysis"""
        try:
            if option_chain is None or option_chain.empty:
                return 0.0

            puts = option_chain[option_chain['option_type'] == 'put']
            calls = option_chain[option_chain['option_type'] == 'call']

            if puts.empty or calls.empty:
                return 0.0

            # Compare IV between puts and calls at similar deltas
            put_iv = puts[abs(puts['delta'] + 0.16) < 0.02]['iv'].mean()
            call_iv = calls[abs(calls['delta'] - 0.16) < 0.02]['iv'].mean()

            if pd.isna(put_iv) or pd.isna(call_iv):
                return 0.0

            return abs(put_iv - call_iv)

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IV skew calculation failed: %s", e)
            return 0.0

    def _generate_ic_recommendation(self, iv_analysis: dict, expected_move_analysis: dict,
                                  trend_analysis: dict) -> tuple[str, float]:
        """Generate Iron Condor setup recommendation"""
        try:
            iv_score = iv_analysis.get('iv_quality_score', 0.0)
            move_score = expected_move_analysis.get('move_quality_score', 0.0)
            trend_score = trend_analysis.get('trend_quality_score', 0.0)

            overall_score = (iv_score * 0.4 + move_score * 0.3 + trend_score * 0.3)

            if overall_score >= 0.8:
                recommendation = "Excellent Iron Condor opportunity - high probability setup"
            elif overall_score >= 0.6:
                recommendation = "Good Iron Condor opportunity - favorable conditions"
            elif overall_score >= 0.4:
                recommendation = "Marginal Iron Condor opportunity - proceed with caution"
            else:
                recommendation = "Poor Iron Condor opportunity - consider other strategies"

            return recommendation, overall_score

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IC recommendation generation failed: %s", e)
            return "Analysis incomplete", 0.0

    def _identify_ic_risk_warnings(self, iv_analysis: dict, expected_move_analysis: dict,
                                 volatility_skew: float) -> list[str]:
        """Identify risk warnings for Iron Condor"""
        warnings = []

        try:
            # IV warnings
            iv_rank = iv_analysis.get('iv_rank', 50)
            if iv_rank < 30:
                warnings.append("Low IV rank - limited premium available")
            elif iv_rank > 80:
                warnings.append("Very high IV rank - potential volatility contraction")

            # Expected move warnings
            expected_move_pct = expected_move_analysis.get('expected_move_percent', 0.03)
            if expected_move_pct > 0.06:
                warnings.append("Large expected move - increased risk of strikes being breached")

            # Volatility skew warnings
            if volatility_skew > IC_VOLATILITY_SKEW_MAX:
                warnings.append("High volatility skew - uneven risk between puts and calls")

            return warnings

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IC risk warning identification failed: %s", e)
            return ["Risk analysis incomplete"]

    def get_strategy_performance(self) -> dict[str, Any]:
        """Get Iron Condor strategy performance metrics"""
        return {
            'strategy_name': 'Iron Condor',
            'consolidation_status': 'Infrastructure moved to D32',
            'performance_metrics': self.performance_metrics.copy(),
            'current_state': self.strategy_state.name,
            'active_setups': len(self.active_setups),
            'multileg_coordinator_connected': self.multileg_coordinator is not None,
            'last_analysis': {
                'timestamp': datetime.now(UTC).isoformat(),
                'market_suitable': self.current_analysis.market_suitable if self.current_analysis else False,  # noqa: E501
                'confidence_score': self.current_analysis.confidence_score if self.current_analysis else 0.0  # noqa: E501
            }
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_iron_condor_strategy(event_manager: EventManager = None,
                               risk_profile: RiskProfile = None,
                               config: dict[str, Any] = None) -> IronCondorStrategy:
    """Factory function to create Iron Condor strategy"""
    return IronCondorStrategy(event_manager, risk_profile, config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Test configuration
    test_config = {
        'min_iv_rank': 40,
        'profit_target': 0.25,
        'stop_loss_multiplier': 2.0,
        'min_dte': 21,
        'max_dte': 45
    }

    # Create strategy
    strategy = create_iron_condor_strategy(config=test_config)



    # Show strategy configuration


    # Show performance metrics
    performance = strategy.get_strategy_performance()


