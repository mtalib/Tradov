#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD23_BrokenWingButterfly.py
Purpose: Broken Wing Butterfly strategy - bullish-neutral put broken wing butterfly with defined risk

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-05-25 Time: 00:00:00

Module Description:
    Dedicated Broken Wing Butterfly strategy. Builds a bullish-to-neutral
    put broken wing butterfly using a narrower upper wing and wider lower wing
    to collect credit while capping downside risk.

        Runtime note:
        - Defaults to same-day expiry via ``target_dte=0`` unless overridden.
        - Implements the put-side credit-oriented variant used by the lean
            recovery / bullish-pivot path, not a generic debit or call-side BWB.

    Entry intent:
    - Confirm a stable bullish-to-neutral tape before selling premium.
    - Prefer supportive implied volatility and downside skew conditions.
    - Align strikes and expiration to the listed chain when live data is available.
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from math import erf, sqrt
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    SignalStrength,
    SignalType,
    TradingSignal,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Safe imports with fallbacks
try:
    from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
        MultiLegStrategyType,
        MultiLegStructure,
        OptionLeg as CoordinatorOptionLeg,
        get_multileg_coordinator,
    )

    MULTILEG_COORDINATOR_AVAILABLE = True
except ImportError:
    try:
        from SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
            MultiLegStrategyType,
            MultiLegStructure,
            OptionLeg as CoordinatorOptionLeg,
            get_multileg_coordinator,
        )

        MULTILEG_COORDINATOR_AVAILABLE = True
    except ImportError:
        MULTILEG_COORDINATOR_AVAILABLE = False

try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager  # noqa: F401
except ImportError:
    EventManager = Any  # type: ignore[misc,assignment]


# ==============================================================================
# CONSTANTS
# ==============================================================================
BWB_MIN_IV_RANK = 25.0
BWB_OPTIMAL_IV_RANK = 45.0
BWB_MAX_IV_RANK = 80.0

BWB_DEFAULT_UPPER_WIDTH = 1.0
BWB_DEFAULT_LOWER_WIDTH = 3.0
BWB_DEFAULT_BODY_OFFSET = 1.0
BWB_DEFAULT_TARGET_DTE = 0

BWB_MIN_CREDIT = 0.15
BWB_MIN_PROBABILITY = 0.55
BWB_PROFIT_TARGET = 0.40
BWB_STOP_LOSS_PCT = 0.75
BWB_MAX_PULLBACK = 0.02
BWB_SIGNAL_EXPIRY_MINUTES = 15


# ==============================================================================
# ENUMS
# ==============================================================================
class BrokenWingButterflyState(Enum):
    """Lifecycle state for a broken wing butterfly strategy instance."""

    ANALYZING = auto()
    READY_TO_ENTER = auto()
    ENTERING = auto()
    ACTIVE = auto()
    MONITORING = auto()
    PROFIT_TARGET_HIT = auto()
    STOP_LOSS_HIT = auto()
    THESIS_BROKEN = auto()
    CLOSING = auto()
    CLOSED = auto()
    ERROR = auto()


class BrokenWingButterflyAdjustmentType(Enum):
    """Adjustment actions for a put broken wing butterfly."""

    ROLL_BODY_DOWN = "roll_body_down"
    ADD_DOWNSTREAM_HEDGE = "add_downstream_hedge"
    CLOSE_EARLY = "close_early"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class BrokenWingButterflySetup:
    """Concrete put broken wing butterfly setup recommendation."""

    underlying_price: float
    upper_wing_strike: float
    body_strike: float
    lower_wing_strike: float
    expiration_date: datetime
    days_to_expiry: int
    upper_width: float
    lower_width: float
    expected_credit: float
    max_profit: float
    max_loss: float
    downside_breakeven: float
    upside_profit_floor: float
    probability_of_profit: float
    directional_bias: str
    setup_quality_score: float


@dataclass
class BrokenWingButterflyAnalysis:
    """Market analysis for a put broken wing butterfly entry."""

    market_suitable: bool
    bullish_outlook_confirmed: bool
    iv_analysis: dict[str, Any]
    skew_analysis: dict[str, Any]
    expected_move_analysis: dict[str, Any]
    body_strike_recommendation: float | None
    upper_width_recommendation: float | None
    lower_width_recommendation: float | None
    setup_recommendation: str
    confidence_score: float
    risk_warnings: list[str]


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BrokenWingButterflyStrategy(BaseStrategy):
    """Bullish-to-neutral put broken wing butterfly strategy.

    The strategy expresses a modest upside or range-bound thesis with limited
    downside risk by buying one put above the short body, selling two body puts,
    and buying one farther-out protective put below the body.
    """

    def __init__(
        self,
        event_manager: EventManager = None,
        risk_profile: RiskProfile = None,
        config: dict[str, Any] = None,
    ):
        """Initialize the strategy with D32 execution integration."""
        super().__init__(
            name="Broken Wing Butterfly Strategy",
            strategy_type="broken_wing_butterfly",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {},
        )

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.symbol = str(self.config.get("symbol", "SPY")).upper()

        self.multileg_coordinator = None
        if MULTILEG_COORDINATOR_AVAILABLE:
            try:
                self.multileg_coordinator = get_multileg_coordinator({"symbol": self.symbol})
                self.logger.info("Connected Broken Wing Butterfly strategy to D32")
            except Exception as exc:
                self.logger.error("Failed to connect BWB strategy to D32: %s", exc)
        else:
            self.logger.warning("MultiLegStrategyCoordinator not available for BWB")

        self.upper_width = float(self.config.get("upper_width", BWB_DEFAULT_UPPER_WIDTH))
        self.lower_width = float(self.config.get("lower_width", BWB_DEFAULT_LOWER_WIDTH))
        self.body_strike_offset = float(
            self.config.get("body_strike_offset", BWB_DEFAULT_BODY_OFFSET)
        )
        self.target_dte = int(self.config.get("target_dte", BWB_DEFAULT_TARGET_DTE))
        self.remaining_session_fraction = float(
            self.config.get("remaining_session_fraction", 0.15)
        )
        self.prefer_live_chain = bool(self.config.get("prefer_live_chain", True))
        self.min_credit = float(self.config.get("min_credit", BWB_MIN_CREDIT))
        self.min_probability = float(self.config.get("min_probability", BWB_MIN_PROBABILITY))
        self.profit_target = float(self.config.get("profit_target", BWB_PROFIT_TARGET))
        self.stop_loss_pct = float(self.config.get("stop_loss_pct", BWB_STOP_LOSS_PCT))
        self.default_contracts = max(1, int(self.config.get("contracts", 1) or 1))
        self._live_quote_client: Any | None = None
        self._live_quote_client_unavailable = False

        self.current_analysis: BrokenWingButterflyAnalysis | None = None
        self.active_setups: list[BrokenWingButterflySetup] = []
        self.strategy_state = BrokenWingButterflyState.ANALYZING
        self.performance_metrics = {
            "total_bwb_trades": 0,
            "winning_bwb_trades": 0,
            "total_bwb_profit": 0.0,
            "avg_bwb_hold_days": 0.0,
            "bwb_win_rate": 0.0,
            "avg_credit_captured": 0.0,
        }

    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """Generate one BWB entry signal when the setup is suitable."""
        if market_data is None or market_data.empty:
            return []

        try:
            setup = self.build_broken_wing_butterfly_setup(market_data)
            if setup is None or setup.setup_quality_score <= 0.0:
                return []

            score = setup.setup_quality_score
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
                symbol=self.symbol,
                strength=strength,
                confidence=score,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit=0.0,
                position_size=self.default_contracts,
                timestamp=now,
                expires_at=now + timedelta(minutes=BWB_SIGNAL_EXPIRY_MINUTES),
                metadata={
                    "strategy_tag": "broken_wing_butterfly",
                    "strategy_type": "broken_wing_butterfly",
                    "direction": setup.directional_bias,
                    "upper_wing_strike": setup.upper_wing_strike,
                    "body_strike": setup.body_strike,
                    "lower_wing_strike": setup.lower_wing_strike,
                    "expected_credit": setup.expected_credit,
                    "max_profit": setup.max_profit,
                    "max_loss": setup.max_loss,
                    "downside_breakeven": setup.downside_breakeven,
                    "target_dte": setup.days_to_expiry,
                },
            )
            return [signal]
        except Exception as exc:
            self.logger.error("BWB signal generation failed: %s", exc, exc_info=True)
            return []

    def validate_signal(self, signal: Any) -> bool:
        """Apply a lightweight validity check to external signals."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: Any) -> int:
        """Use the requested contract size when available."""
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else self.default_contracts

    def should_exit_position(
        self,
        position: Any,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Bridge the base strategy exit contract for strategy positions."""
        if market_data is None or market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        stop_loss = getattr(position, "stop_loss", None)
        take_profit = getattr(position, "take_profit", None)

        if stop_loss is not None and current_price <= float(stop_loss):
            return True, "stop_loss"
        if take_profit is not None and current_price >= float(take_profit):
            return True, "take_profit"
        return False, ""

    def analyze_broken_wing_butterfly_opportunity(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame = None,
    ) -> BrokenWingButterflyAnalysis:
        """Analyze whether a put BWB fits the current market context."""
        try:
            current_price = float(market_data["close"].iloc[-1])
            bullish_outlook_confirmed = self._confirm_bullish_or_neutral_outlook(market_data)
            iv_analysis = self._analyze_iv_for_bwb(market_data)
            skew_analysis = self._analyze_skew_for_bwb(option_chain, current_price)
            expected_move_analysis = self._analyze_expected_move_for_bwb(market_data, current_price)

            market_suitable = self._assess_market_suitability_for_bwb(
                bullish_outlook_confirmed,
                iv_analysis,
                skew_analysis,
                expected_move_analysis,
            )

            body_strike = None
            upper_width = None
            lower_width = None
            recommendation = ""
            confidence_score = 0.0
            risk_warnings: list[str] = []

            if market_suitable:
                body_strike = self._find_recommended_body_strike(current_price, option_chain)
                upper_width, lower_width = self._recommend_wing_widths(
                    expected_move_analysis,
                    option_chain,
                )
                recommendation, confidence_score = self._generate_bwb_recommendation(
                    iv_analysis,
                    skew_analysis,
                    expected_move_analysis,
                )
                risk_warnings = self._identify_bwb_risk_warnings(
                    bullish_outlook_confirmed,
                    iv_analysis,
                    expected_move_analysis,
                )

            analysis = BrokenWingButterflyAnalysis(
                market_suitable=market_suitable,
                bullish_outlook_confirmed=bullish_outlook_confirmed,
                iv_analysis=iv_analysis,
                skew_analysis=skew_analysis,
                expected_move_analysis=expected_move_analysis,
                body_strike_recommendation=body_strike,
                upper_width_recommendation=upper_width,
                lower_width_recommendation=lower_width,
                setup_recommendation=recommendation,
                confidence_score=confidence_score,
                risk_warnings=risk_warnings,
            )
            self.current_analysis = analysis
            return analysis
        except Exception as exc:
            self.logger.error("BWB opportunity analysis failed: %s", exc)
            self.error_handler.handle_error(
                exc,
                {"method": "analyze_broken_wing_butterfly_opportunity"},
            )
            return BrokenWingButterflyAnalysis(
                market_suitable=False,
                bullish_outlook_confirmed=False,
                iv_analysis={},
                skew_analysis={},
                expected_move_analysis={},
                body_strike_recommendation=None,
                upper_width_recommendation=None,
                lower_width_recommendation=None,
                setup_recommendation="Analysis failed",
                confidence_score=0.0,
                risk_warnings=["Analysis error occurred"],
            )

    def build_broken_wing_butterfly_setup(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame = None,
    ) -> BrokenWingButterflySetup | None:
        """Build a concrete put BWB setup from the current market snapshot."""
        expiration_date = self._resolve_target_expiration()
        chain_frame = option_chain
        if chain_frame is None and self.prefer_live_chain:
            chain_frame = self._get_live_option_chain_dataframe(expiration_date)

        analysis = self.analyze_broken_wing_butterfly_opportunity(market_data, chain_frame)
        if not analysis.market_suitable:
            return None
        if analysis.body_strike_recommendation is None:
            return None
        if analysis.upper_width_recommendation is None or analysis.lower_width_recommendation is None:
            return None

        current_price = float(market_data["close"].iloc[-1])
        body_strike = float(analysis.body_strike_recommendation)
        upper_width = float(analysis.upper_width_recommendation)
        lower_width = float(analysis.lower_width_recommendation)

        upper_wing_strike = round(body_strike + upper_width, 2)
        lower_wing_strike = round(body_strike - lower_width, 2)
        if chain_frame is not None and not chain_frame.empty:
            upper_wing_strike, body_strike, lower_wing_strike = self._align_setup_to_chain(
                body_strike,
                upper_width,
                lower_width,
                chain_frame,
            )
            upper_width = round(upper_wing_strike - body_strike, 2)
            lower_width = round(body_strike - lower_wing_strike, 2)

        expected_credit = self._estimate_entry_credit(
            chain_frame,
            upper_wing_strike,
            body_strike,
            lower_wing_strike,
        )
        max_profit = round(upper_width + expected_credit, 2)
        max_loss = round(max(0.0, lower_width - upper_width - expected_credit), 2)
        downside_breakeven = round(body_strike - upper_width - expected_credit, 2)
        upside_profit_floor = round(expected_credit, 2)
        probability = self._estimate_probability_of_profit(
            current_price,
            downside_breakeven,
            analysis.expected_move_analysis.get("expected_move_dollars", 0.0),
        )

        return BrokenWingButterflySetup(
            underlying_price=current_price,
            upper_wing_strike=upper_wing_strike,
            body_strike=body_strike,
            lower_wing_strike=lower_wing_strike,
            expiration_date=expiration_date,
            days_to_expiry=max(0, self.target_dte),
            upper_width=upper_width,
            lower_width=lower_width,
            expected_credit=expected_credit,
            max_profit=max_profit,
            max_loss=max_loss,
            downside_breakeven=downside_breakeven,
            upside_profit_floor=upside_profit_floor,
            probability_of_profit=probability,
            directional_bias="bullish_neutral",
            setup_quality_score=analysis.confidence_score,
        )

    def _resolve_target_expiration(self) -> datetime:
        """Resolve the nearest listed expiration for the configured DTE when available."""
        target_expiration = datetime.now(UTC) + timedelta(days=max(self.target_dte, 0))
        if not self.prefer_live_chain:
            return target_expiration

        client = self._get_live_quote_client()
        if client is None:
            return target_expiration

        try:
            expirations_payload = client.get_option_expirations(self.symbol)
            expiration_values = self._extract_expiration_values(expirations_payload)
            listed_dates = [
                datetime.fromisoformat(value).date()
                for value in expiration_values
                if isinstance(value, str) and value
            ]
            if not listed_dates:
                return target_expiration

            target_date = target_expiration.date()
            selected_date = min(
                listed_dates,
                key=lambda value: (abs((value - target_date).days), value < target_date, value),
            )
            return datetime(
                selected_date.year,
                selected_date.month,
                selected_date.day,
                tzinfo=UTC,
            )
        except Exception as exc:
            self.logger.debug("BWB live expiration lookup failed: %s", exc)
            return target_expiration

    def _get_live_quote_client(self) -> Any | None:
        """Create and cache the live Tradier quote client lazily."""
        if self._live_quote_client_unavailable:
            return None
        if self._live_quote_client is not None:
            return self._live_quote_client

        try:
            try:
                from Spyder.SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env
            except ImportError:
                from SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env

            self._live_quote_client = create_tradier_client_from_env()
            return self._live_quote_client
        except Exception as exc:
            self._live_quote_client_unavailable = True
            self.logger.debug("BWB live quote client unavailable: %s", exc)
            return None

    def _get_live_option_chain_dataframe(self, expiration_date: datetime) -> pd.DataFrame | None:
        """Fetch a live option chain with Greeks and normalize it into a DataFrame."""
        client = self._get_live_quote_client()
        if client is None:
            return None

        try:
            contracts = client.get_option_chain_with_greeks(
                self.symbol,
                expiration_date.date().isoformat(),
            )
        except Exception as exc:
            self.logger.debug("BWB live option chain lookup failed: %s", exc)
            return None

        rows: list[dict[str, Any]] = []
        for contract in contracts or []:
            bid = float(getattr(contract, "bid", 0.0) or 0.0)
            ask = float(getattr(contract, "ask", 0.0) or 0.0)
            mid = float(getattr(contract, "mid", 0.0) or 0.0)
            last = float(getattr(contract, "last", 0.0) or 0.0)
            if mid <= 0.0 and bid > 0.0 and ask > 0.0:
                mid = (bid + ask) / 2.0
            rows.append(
                {
                    "symbol": getattr(contract, "symbol", ""),
                    "strike": float(getattr(contract, "strike", 0.0) or 0.0),
                    "option_type": str(getattr(contract, "option_type", "") or "").lower(),
                    "expiration": str(
                        getattr(contract, "expiration", "") or expiration_date.date().isoformat()
                    ),
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "mid": max(mid, last, 0.0),
                    "delta": float(getattr(contract, "delta", 0.0) or 0.0),
                    "iv": float(getattr(contract, "iv", np.nan) or np.nan),
                }
            )

        if not rows:
            return None
        return pd.DataFrame(rows)

    @staticmethod
    def _extract_expiration_values(payload: Any) -> list[str]:
        """Extract ISO expiration strings from the broker payload shape."""
        if isinstance(payload, dict):
            expirations = payload.get("expirations", payload.get("expiration", payload))
            if isinstance(expirations, dict):
                values = expirations.get("date", expirations.get("dates", []))
            elif isinstance(expirations, list):
                values = expirations
            else:
                values = []
        elif isinstance(payload, list):
            values = payload
        else:
            values = []
        return [str(value) for value in values if value]

    async def create_broken_wing_butterfly_position(
        self,
        setup: BrokenWingButterflySetup,
    ) -> str | None:
        """Submit the BWB through the D32 execution coordinator."""
        try:
            if self.multileg_coordinator is None:
                self.logger.error("MultiLegStrategyCoordinator not available for BWB execution")
                return None

            structure = self._build_multileg_structure_from_setup(setup)
            position_id = await self.multileg_coordinator.execute_multileg_strategy(structure)
            if position_id:
                self.active_setups.append(setup)
                self.strategy_state = BrokenWingButterflyState.ACTIVE
                self.logger.info("Broken Wing Butterfly position created: %s", position_id)
            return position_id
        except Exception as exc:
            self.logger.error("BWB position creation failed: %s", exc)
            return None

    def should_close_broken_wing_butterfly(self, position_data: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate simple exit conditions for an open BWB."""
        try:
            current_pnl_pct = float(position_data.get("pnl_percent", 0.0) or 0.0)
            dte = int(position_data.get("days_to_expiry", self.target_dte) or self.target_dte)
            body_strike = float(position_data.get("body_strike", 0.0) or 0.0)
            underlying_price = float(position_data.get("underlying_price", 0.0) or 0.0)

            if current_pnl_pct >= self.profit_target:
                return True, "profit_target"
            if current_pnl_pct <= -self.stop_loss_pct:
                return True, "stop_loss"
            if dte <= 0 and body_strike > 0.0 and underlying_price < body_strike:
                return True, "0dte_downside_test"
            return False, "hold"
        except Exception as exc:
            self.logger.error("BWB exit analysis failed: %s", exc)
            return True, "analysis_error"

    def get_strategy_performance(self) -> dict[str, Any]:
        """Return a compact BWB performance summary."""
        return {
            "strategy_name": "Broken Wing Butterfly",
            "performance_metrics": self.performance_metrics.copy(),
            "current_state": self.strategy_state.name,
            "active_setups": len(self.active_setups),
            "multileg_coordinator_connected": self.multileg_coordinator is not None,
            "last_analysis": {
                "timestamp": datetime.now(UTC).isoformat(),
                "market_suitable": self.current_analysis.market_suitable if self.current_analysis else False,
                "bullish_outlook": (
                    self.current_analysis.bullish_outlook_confirmed if self.current_analysis else False
                ),
                "confidence_score": self.current_analysis.confidence_score if self.current_analysis else 0.0,
            },
        }

    def _confirm_bullish_or_neutral_outlook(self, market_data: pd.DataFrame) -> bool:
        """Confirm that the market is stable enough for a put-side BWB."""
        try:
            closes = market_data["close"]
            if len(closes) < 11:
                return False

            short_term_change = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6]
            medium_term_change = (closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11]
            near_term_ma = closes.tail(5).mean()
            pullback_ok = (
                short_term_change >= -BWB_MAX_PULLBACK
                and medium_term_change >= -(BWB_MAX_PULLBACK * 1.5)
            )
            price_holding = closes.iloc[-1] >= near_term_ma * 0.995
            return bool(pullback_ok and price_holding)
        except Exception as exc:
            self.logger.error("BWB outlook analysis failed: %s", exc)
            return False

    def _analyze_iv_for_bwb(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze implied volatility suitability for a premium-selling BWB."""
        no_iv = {
            "current_iv": float("nan"),
            "iv_rank": float("nan"),
            "iv_suitable_for_bwb": False,
            "iv_quality_score": 0.0,
            "iv_data_available": False,
        }
        try:
            iv_col = market_data.get("iv") if isinstance(market_data, pd.DataFrame) else None
            if iv_col is None or iv_col.dropna().empty:
                return no_iv

            current_iv = float(iv_col.iloc[-1])
            if np.isnan(current_iv):
                return no_iv

            iv_history = iv_col.dropna().tail(min(len(iv_col.dropna()), 252))
            if iv_history.empty:
                return no_iv

            iv_rank = float((current_iv > iv_history).sum() / len(iv_history) * 100.0)
            if iv_rank < BWB_MIN_IV_RANK:
                iv_quality_score = 0.0
            elif iv_rank > BWB_MAX_IV_RANK:
                iv_quality_score = 0.4
            else:
                iv_quality_score = max(
                    0.0,
                    1.0 - abs(iv_rank - BWB_OPTIMAL_IV_RANK) / BWB_OPTIMAL_IV_RANK,
                )

            return {
                "current_iv": current_iv,
                "iv_rank": iv_rank,
                "iv_suitable_for_bwb": BWB_MIN_IV_RANK <= iv_rank <= BWB_MAX_IV_RANK,
                "iv_quality_score": iv_quality_score,
                "iv_data_available": True,
            }
        except Exception as exc:
            self.logger.error("BWB IV analysis failed: %s", exc)
            return no_iv

    def _analyze_skew_for_bwb(
        self,
        option_chain: pd.DataFrame | None,
        current_price: float,
    ) -> dict[str, Any]:
        """Measure downside skew support for a put-side BWB."""
        default_result = {
            "put_call_skew": 0.0,
            "skew_favorable_for_bwb": True,
            "skew_quality_score": 0.5,
            "skew_data_available": False,
        }
        if option_chain is None or option_chain.empty:
            return default_result

        try:
            if "strike" not in option_chain.columns or "option_type" not in option_chain.columns:
                return default_result

            iv_column = None
            for candidate in ("implied_volatility", "iv", "smv_vol"):
                if candidate in option_chain.columns:
                    iv_column = candidate
                    break
            if iv_column is None:
                return default_result

            chain = option_chain.copy()
            chain["distance"] = (chain["strike"] - current_price).abs()
            near_atm = chain.nsmallest(12, "distance")
            puts = near_atm[near_atm["option_type"].astype(str).str.lower() == "put"][iv_column].dropna()
            calls = near_atm[near_atm["option_type"].astype(str).str.lower() == "call"][iv_column].dropna()
            if puts.empty or calls.empty:
                return default_result

            skew = float(puts.mean() - calls.mean())
            quality = max(0.0, min(1.0, 0.5 + (skew * 10.0)))
            return {
                "put_call_skew": skew,
                "skew_favorable_for_bwb": skew >= -0.01,
                "skew_quality_score": quality,
                "skew_data_available": True,
            }
        except Exception as exc:
            self.logger.error("BWB skew analysis failed: %s", exc)
            return default_result

    def _analyze_expected_move_for_bwb(
        self,
        market_data: pd.DataFrame,
        current_price: float,
    ) -> dict[str, Any]:
        """Estimate short-dated expected move and compare it to wing asymmetry."""
        try:
            iv_analysis = self._analyze_iv_for_bwb(market_data)
            current_iv = float(iv_analysis.get("current_iv", 0.20) or 0.20)
            if np.isnan(current_iv):
                current_iv = 0.20

            if self.target_dte <= 0:
                lookahead_days = max(0.05, self.remaining_session_fraction)
            else:
                lookahead_days = float(max(1, self.target_dte))

            expected_move = current_price * current_iv * sqrt(lookahead_days / 252.0)
            credit_buffer = max(0.5, self.lower_width - self.upper_width)
            move_ratio = expected_move / credit_buffer
            return {
                "expected_move_dollars": expected_move,
                "expected_move_percent": expected_move / current_price if current_price > 0 else 0.0,
                "expected_move_vs_credit_buffer": move_ratio,
                "expected_move_suitable_for_bwb": expected_move <= max(self.lower_width * 1.2, 3.0),
                "move_quality_score": max(0.0, min(1.0, 1.0 - max(0.0, move_ratio - 1.0))),
            }
        except Exception as exc:
            self.logger.error("BWB expected move analysis failed: %s", exc)
            return {
                "expected_move_dollars": 0.0,
                "expected_move_percent": 0.0,
                "expected_move_vs_credit_buffer": 0.0,
                "expected_move_suitable_for_bwb": False,
                "move_quality_score": 0.0,
            }

    def _assess_market_suitability_for_bwb(
        self,
        bullish_outlook: bool,
        iv_analysis: dict[str, Any],
        skew_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> bool:
        """Determine whether the market context supports a put BWB."""
        try:
            return bool(
                bullish_outlook
                and iv_analysis.get("iv_data_available", False)
                and iv_analysis.get("iv_suitable_for_bwb", False)
                and skew_analysis.get("skew_favorable_for_bwb", True)
                and expected_move_analysis.get("expected_move_suitable_for_bwb", False)
            )
        except Exception as exc:
            self.logger.warning("BWB suitability check failed: %s", exc)
            return False

    def _find_recommended_body_strike(
        self,
        current_price: float,
        option_chain: pd.DataFrame | None,
    ) -> float:
        """Choose a slightly OTM short body strike using the live strike grid when available."""
        strike_increment = self._infer_strike_increment(option_chain)
        body_target = current_price - self.body_strike_offset
        if option_chain is not None and not option_chain.empty and "strike" in option_chain.columns:
            strikes = sorted(
                float(strike)
                for strike in option_chain[
                    option_chain.get("option_type", pd.Series(["put"] * len(option_chain))).astype(str).str.lower() == "put"
                ]["strike"].dropna().unique()
            )
            if strikes:
                candidates = [strike for strike in strikes if strike <= body_target]
                if candidates:
                    return float(candidates[-1])
                return float(min(strikes, key=lambda strike: abs(strike - body_target)))

        return round(float(np.floor(body_target / strike_increment) * strike_increment), 2)

    def _recommend_wing_widths(
        self,
        expected_move_analysis: dict[str, Any],
        option_chain: pd.DataFrame | None,
    ) -> tuple[float, float]:
        """Align configured wing widths to the available strike increment."""
        strike_increment = self._infer_strike_increment(option_chain)
        upper_width = max(strike_increment, self._round_to_increment(self.upper_width, strike_increment))
        lower_floor = max(
            upper_width + strike_increment,
            expected_move_analysis.get("expected_move_dollars", 0.0) * 0.75,
            self.lower_width,
        )
        lower_width = max(
            upper_width + strike_increment,
            self._round_to_increment(lower_floor, strike_increment),
        )
        return round(upper_width, 2), round(lower_width, 2)

    def _estimate_entry_credit(
        self,
        option_chain: pd.DataFrame | None,
        upper_wing_strike: float,
        body_strike: float,
        lower_wing_strike: float,
    ) -> float:
        """Estimate the entry credit using live mids when possible."""
        if option_chain is not None and not option_chain.empty:
            upper_mid = self._extract_put_mid(option_chain, upper_wing_strike)
            body_mid = self._extract_put_mid(option_chain, body_strike)
            lower_mid = self._extract_put_mid(option_chain, lower_wing_strike)
            if upper_mid is not None and body_mid is not None and lower_mid is not None:
                return round(max(0.01, (body_mid * 2.0) - upper_mid - lower_mid), 2)

        estimate = (0.15 * self.upper_width) + (0.05 * max(0.0, self.lower_width - self.upper_width))
        return round(max(self.min_credit, estimate), 2)

    def _align_setup_to_chain(
        self,
        body_target: float,
        upper_width: float,
        lower_width: float,
        option_chain: pd.DataFrame,
    ) -> tuple[float, float, float]:
        """Align the BWB body and wings to listed put strikes using live mids when possible."""
        if option_chain.empty or "strike" not in option_chain.columns:
            return (
                round(body_target + upper_width, 2),
                round(body_target, 2),
                round(body_target - lower_width, 2),
            )

        option_types = option_chain.get("option_type")
        if option_types is None:
            puts = option_chain
        else:
            puts = option_chain[option_types.astype(str).str.lower() == "put"]
        strikes = sorted(float(value) for value in puts["strike"].dropna().unique())
        if len(strikes) < 3:
            return (
                round(body_target + upper_width, 2),
                round(body_target, 2),
                round(body_target - lower_width, 2),
            )

        body_candidates = sorted(
            strikes,
            key=lambda strike: (0 if strike <= body_target else 1, abs(strike - body_target)),
        )
        best_candidate: tuple[float, float, float] | None = None
        best_score = float("-inf")

        for body_strike in body_candidates[:8]:
            upper_candidates = [strike for strike in strikes if strike > body_strike]
            lower_candidates = [strike for strike in strikes if strike < body_strike]
            if not upper_candidates or not lower_candidates:
                continue

            upper_wing = min(
                upper_candidates,
                key=lambda strike: abs((strike - body_strike) - upper_width),
            )
            lower_wing = min(
                lower_candidates,
                key=lambda strike: abs((body_strike - strike) - lower_width),
            )

            actual_upper_width = upper_wing - body_strike
            actual_lower_width = body_strike - lower_wing
            if actual_lower_width <= actual_upper_width:
                continue

            credit = self._estimate_entry_credit(option_chain, upper_wing, body_strike, lower_wing)
            max_loss = max(0.01, (body_strike - lower_wing) - (upper_wing - body_strike) - credit)
            distance_penalty = abs(body_strike - body_target) * 0.05
            width_penalty = (
                abs(actual_upper_width - upper_width) + abs(actual_lower_width - lower_width)
            ) * 0.25
            credit_penalty = 0.0 if credit >= self.min_credit else 1.0
            score = (credit / max_loss) - distance_penalty - width_penalty - credit_penalty
            if score > best_score:
                best_score = score
                best_candidate = (upper_wing, body_strike, lower_wing)

        if best_candidate is not None:
            return tuple(round(value, 2) for value in best_candidate)

        return (
            round(body_target + upper_width, 2),
            round(body_target, 2),
            round(body_target - lower_width, 2),
        )

    def _estimate_probability_of_profit(
        self,
        current_price: float,
        downside_breakeven: float,
        expected_move: float,
    ) -> float:
        """Approximate the probability that price stays above the downside breakeven."""
        if expected_move <= 0:
            return 0.65
        z_score = (current_price - downside_breakeven) / max(0.01, expected_move)
        probability = 0.5 * (1.0 + erf(z_score / sqrt(2.0)))
        return max(0.35, min(0.95, probability))

    def _generate_bwb_recommendation(
        self,
        iv_analysis: dict[str, Any],
        skew_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> tuple[str, float]:
        """Generate a recommendation string and confidence score."""
        iv_score = float(iv_analysis.get("iv_quality_score", 0.0) or 0.0)
        skew_score = float(skew_analysis.get("skew_quality_score", 0.0) or 0.0)
        move_score = float(expected_move_analysis.get("move_quality_score", 0.0) or 0.0)
        overall = (iv_score * 0.35) + (skew_score * 0.25) + (move_score * 0.40)

        if overall >= 0.8:
            recommendation = "Excellent put BWB opportunity - premium rich with contained downside"
        elif overall >= 0.6:
            recommendation = "Good put BWB opportunity - bullish-neutral conditions are supportive"
        elif overall >= 0.4:
            recommendation = "Marginal put BWB opportunity - size carefully"
        else:
            recommendation = "Poor put BWB opportunity - wait for better skew or IV"
        return recommendation, overall

    def _identify_bwb_risk_warnings(
        self,
        bullish_outlook: bool,
        iv_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> list[str]:
        """List the main trade-selection risks for the current snapshot."""
        warnings: list[str] = []
        if not bullish_outlook:
            warnings.append("Market is losing support - downside tail risk is rising")
        iv_rank = float(iv_analysis.get("iv_rank", 0.0) or 0.0)
        if iv_rank < BWB_MIN_IV_RANK:
            warnings.append("IV rank is too low for efficient premium collection")
        if expected_move_analysis.get("expected_move_vs_credit_buffer", 0.0) > 1.0:
            warnings.append("Expected move is large relative to the broken-wing buffer")
        return warnings

    def _infer_strike_increment(self, option_chain: pd.DataFrame | None) -> float:
        """Infer the live strike increment or fall back to a one-dollar grid."""
        if option_chain is not None and not option_chain.empty and "strike" in option_chain.columns:
            strikes = sorted(float(value) for value in option_chain["strike"].dropna().unique())
            if len(strikes) >= 2:
                increments = [
                    round(strikes[index + 1] - strikes[index], 4)
                    for index in range(len(strikes) - 1)
                    if strikes[index + 1] > strikes[index]
                ]
                positive = [increment for increment in increments if increment > 0]
                if positive:
                    return max(0.5, min(positive))
        return 1.0

    @staticmethod
    def _round_to_increment(value: float, increment: float) -> float:
        """Round a value up to the nearest allowed strike increment."""
        if increment <= 0:
            return value
        return float(np.ceil(value / increment) * increment)

    @staticmethod
    def _extract_put_mid(option_chain: pd.DataFrame, strike: float) -> float | None:
        """Extract a put midpoint for the requested strike from a chain DataFrame."""
        try:
            rows = option_chain[
                (option_chain["strike"].astype(float) == float(strike))
                & (option_chain["option_type"].astype(str).str.lower() == "put")
            ]
            if rows.empty:
                return None
            row = rows.iloc[0]
            mid = row.get("mid")
            if mid is not None and float(mid) > 0:
                return float(mid)
            bid = row.get("bid")
            ask = row.get("ask")
            if bid is not None and ask is not None and float(bid) > 0 and float(ask) > 0:
                return (float(bid) + float(ask)) / 2.0
            last = row.get("last")
            if last is not None:
                return float(last)
            return None
        except Exception:
            return None

    def _build_multileg_structure_from_setup(
        self,
        setup: BrokenWingButterflySetup,
    ) -> MultiLegStructure:
        """Convert a BWB setup into the D32 structure used for execution."""
        if not MULTILEG_COORDINATOR_AVAILABLE:
            raise RuntimeError("D32 coordinator types are unavailable")

        legs = [
            CoordinatorOptionLeg("put", setup.upper_wing_strike, 1, setup.expiration_date),
            CoordinatorOptionLeg("put", setup.body_strike, -2, setup.expiration_date),
            CoordinatorOptionLeg("put", setup.lower_wing_strike, 1, setup.expiration_date),
        ]
        structure = MultiLegStructure(
            strategy_type=MultiLegStrategyType.BROKEN_WING_BUTTERFLY,
            legs=legs,
            net_credit=setup.expected_credit,
            max_profit=setup.max_profit,
            max_loss=setup.max_loss,
            breakeven_points=[setup.downside_breakeven],
            probability_profit=setup.probability_of_profit,
            net_delta=0.05,
            net_gamma=-0.01,
            net_theta=0.03,
            net_vega=-0.02,
            wing_width=setup.lower_width,
            body_width=setup.upper_width,
            risk_reward_ratio=(setup.max_loss / setup.max_profit) if setup.max_profit > 0 else 0.0,
        )
        structure.underlying_symbol = self.symbol
        structure.expiration_date = setup.expiration_date.date().isoformat()
        structure.contracts = self.default_contracts
        return structure


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_broken_wing_butterfly_strategy(
    event_manager: EventManager = None,
    risk_profile: RiskProfile = None,
    config: dict[str, Any] = None,
) -> BrokenWingButterflyStrategy:
    """Factory for the native Broken Wing Butterfly strategy."""
    return BrokenWingButterflyStrategy(event_manager, risk_profile, config)
