#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD24_Butterfly.py
Purpose: Butterfly strategy - long call butterfly with defined debit risk and pin-risk targeting

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-05-25 Time: 00:00:00

Module Description:
    Dedicated Butterfly strategy. Builds a long call butterfly to express a
    neutral-to-slightly-bullish thesis with capped debit risk and a defined
    profit tent around the body strike.

    Entry intent:
    - Confirm stable, range-bound tape before opening a pin-focused structure.
    - Keep debit contained relative to wing width and expected move.
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
BFLY_DEFAULT_WING_WIDTH = 1.0
BFLY_DEFAULT_TARGET_DTE = 0
BFLY_DEFAULT_MAX_DEBIT = 0.65
BFLY_PROFIT_TARGET_PCT = 0.80
BFLY_STOP_LOSS_RETAINED_VALUE_FRACTION = 0.45
BFLY_STOP_LOSS_PNL_FALLBACK_PCT = -0.55
BFLY_SIGNAL_EXPIRY_MINUTES = 15


# ==============================================================================
# ENUMS
# ==============================================================================
class ButterflyState(Enum):
    """Lifecycle state for a long call butterfly strategy."""

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


class ButterflyAdjustmentType(Enum):
    """Adjustment actions for a long call butterfly."""

    ROLL_CENTER = "roll_center"
    WIDEN_WINGS = "widen_wings"
    CLOSE_EARLY = "close_early"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ButterflySetup:
    """Concrete long call butterfly recommendation."""

    underlying_price: float
    lower_strike: float
    body_strike: float
    upper_strike: float
    expiration_date: datetime
    days_to_expiry: int
    wing_width: float
    expected_debit: float
    max_profit: float
    max_loss: float
    lower_breakeven: float
    upper_breakeven: float
    probability_of_profit: float
    directional_bias: str
    setup_quality_score: float


@dataclass
class ButterflyAnalysis:
    """Market analysis for a long call butterfly entry."""

    market_suitable: bool
    neutral_outlook_confirmed: bool
    iv_analysis: dict[str, Any]
    expected_move_analysis: dict[str, Any]
    body_strike_recommendation: float | None
    wing_width_recommendation: float | None
    setup_recommendation: str
    confidence_score: float
    risk_warnings: list[str]


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ButterflyStrategy(BaseStrategy):
    """Native long call butterfly debit strategy.

    Args:
        event_manager: Shared event bus used by the D-series runtime.
        risk_profile: Strategy risk profile used for sizing limits.
        config: Strategy configuration overrides.
        name: Optional runtime strategy instance name.
    """

    def __init__(
        self,
        event_manager: EventManager = None,
        risk_profile: RiskProfile = None,
        config: dict[str, Any] = None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            name=name or "Butterfly Strategy",
            strategy_type="butterfly",
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
                self.logger.info("Connected Butterfly strategy to D32")
            except Exception as exc:
                self.logger.error("Failed to connect Butterfly strategy to D32: %s", exc)
        else:
            self.logger.warning("MultiLegStrategyCoordinator not available for Butterfly")

        self.wing_width = float(self.config.get("wing_width", BFLY_DEFAULT_WING_WIDTH))
        self.target_dte = int(self.config.get("target_dte", BFLY_DEFAULT_TARGET_DTE))
        self.max_debit = float(self.config.get("max_debit", BFLY_DEFAULT_MAX_DEBIT))
        self.remaining_session_fraction = float(
            self.config.get("remaining_session_fraction", 0.15)
        )
        self.prefer_live_chain = bool(self.config.get("prefer_live_chain", True))
        self.default_contracts = max(1, int(self.config.get("contracts", 1) or 1))
        self.max_contracts = max(1, int(self.config.get("max_contracts", 10) or 10))
        self._live_quote_client: Any | None = None
        self._live_quote_client_unavailable = False

        self.current_analysis: ButterflyAnalysis | None = None
        self.active_setups: list[ButterflySetup] = []
        self.strategy_state = ButterflyState.ANALYZING
        self.performance_metrics = {
            "total_butterfly_trades": 0,
            "winning_butterfly_trades": 0,
            "total_butterfly_profit": 0.0,
            "avg_butterfly_hold_days": 0.0,
            "butterfly_win_rate": 0.0,
            "avg_debit_paid": 0.0,
        }

    @staticmethod
    def _resolve_stop_loss_mark(entry_debit: float) -> float:
        """Return the per-spread stop-loss mark for a long debit butterfly."""
        return max(0.01, round(entry_debit * BFLY_STOP_LOSS_RETAINED_VALUE_FRACTION, 2))

    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """Generate one long butterfly entry signal when the setup fits.

        Args:
            market_data: Recent market data for the configured symbol.

        Returns:
            A single buy signal when the setup quality is positive, otherwise an empty list.
        """
        if market_data is None or market_data.empty:
            return []

        try:
            setup = self.build_butterfly_setup(market_data)
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

            now = datetime.now(UTC)
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                strength=strength,
                confidence=score,
                entry_price=setup.expected_debit,
                stop_loss=self._resolve_stop_loss_mark(setup.expected_debit),
                take_profit=max(setup.expected_debit + 0.01, round(setup.expected_debit * 1.8, 2)),
                position_size=self.default_contracts,
                timestamp=now,
                expires_at=now + timedelta(minutes=BFLY_SIGNAL_EXPIRY_MINUTES),
                metadata={
                    "strategy_tag": "butterfly",
                    "strategy_type": "butterfly",
                    "structure": "long_call_butterfly",
                    "direction": setup.directional_bias,
                    "expiration_date": setup.expiration_date.date().isoformat(),
                    "lower_strike": setup.lower_strike,
                    "body_strike": setup.body_strike,
                    "upper_strike": setup.upper_strike,
                    "expected_debit": setup.expected_debit,
                    "max_profit": setup.max_profit,
                    "max_loss": setup.max_loss,
                    "lower_breakeven": setup.lower_breakeven,
                    "upper_breakeven": setup.upper_breakeven,
                    "target_dte": setup.days_to_expiry,
                },
            )
            return [signal]
        except Exception as exc:
            self.logger.error("Butterfly signal generation failed: %s", exc, exc_info=True)
            return []

    def validate_signal(self, signal: Any) -> bool:
        """Apply a lightweight sanity check to external signals."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        if getattr(signal, "signal_type", None) != SignalType.BUY:
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: Any) -> int:
        """Use the configured risk budget for debit butterfly sizing."""
        debit = float(getattr(signal, "entry_price", 0.0) or 0.0)
        if debit <= 0.0:
            return self.default_contracts
        risk_budget = self.risk_profile.account_size * self.risk_profile.max_loss_per_trade
        contracts = int(risk_budget // max(debit * 100.0, 1.0))
        return max(1, min(self.max_contracts, contracts or self.default_contracts))

    def should_exit_position(
        self,
        position: Any,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Exit when spot breaks the defined butterfly body or wings."""
        if market_data is None or market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        metadata = getattr(position, "metadata", {}) or {}
        lower_strike = float(metadata.get("lower_strike", 0.0) or 0.0)
        upper_strike = float(metadata.get("upper_strike", 0.0) or 0.0)
        if lower_strike > 0.0 and current_price <= lower_strike:
            return True, "lower_wing_breached"
        if upper_strike > 0.0 and current_price >= upper_strike:
            return True, "upper_wing_breached"
        return False, ""

    def should_close_butterfly(self, position_data: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate grouped long-butterfly exits for ExitMonitor integration."""
        try:
            current_pnl_pct = float(position_data.get("pnl_percent", 0.0) or 0.0)
            unrealized_pnl = float(position_data.get("unrealized_pnl", 0.0) or 0.0)
            entry_notional = float(position_data.get("entry_notional", 0.0) or 0.0)
            quantity = max(int(position_data.get("quantity", 0) or 0), 0)
            dte = int(position_data.get("days_to_expiry", self.target_dte) or self.target_dte)
            is_hydrated_carryover = bool(position_data.get("is_hydrated_carryover"))
            profit_target_pct = float(
                self.config.get("profit_target_pct", BFLY_PROFIT_TARGET_PCT)
            )

            if current_pnl_pct >= profit_target_pct:
                return True, "profit_target"
            if entry_notional > 0.0 and quantity > 0:
                entry_debit = entry_notional / max(quantity * 100.0, 1.0)
                stop_loss_mark = self._resolve_stop_loss_mark(entry_debit) * quantity * 100.0
                current_mark_value = max(entry_notional + unrealized_pnl, 0.0)
                if current_mark_value <= stop_loss_mark + 1e-9:
                    return True, "stop_loss_mark"
            elif current_pnl_pct <= float(
                self.config.get("stop_loss_pnl_pct", BFLY_STOP_LOSS_PNL_FALLBACK_PCT)
            ):
                return True, "stop_loss_mark"
            if is_hydrated_carryover and dte <= 0 and unrealized_pnl > 0.0:
                return True, "pre_carryover_profit_take"
            return False, "hold"
        except Exception as exc:
            self.logger.error("Butterfly exit analysis failed: %s", exc)
            return True, "analysis_error"

    def analyze_butterfly_opportunity(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame = None,
    ) -> ButterflyAnalysis:
        """Analyze whether a long call butterfly fits the current market snapshot.

        Args:
            market_data: Recent underlying market data.
            option_chain: Optional normalized option chain.

        Returns:
            A scored butterfly analysis payload.
        """
        try:
            current_price = float(market_data["close"].iloc[-1])
            neutral_outlook_confirmed = self._confirm_neutral_to_slightly_bullish_outlook(market_data)
            iv_analysis = self._analyze_iv_for_butterfly(market_data)
            expected_move_analysis = self._analyze_expected_move_for_butterfly(
                market_data,
                current_price,
            )
            increment = self._infer_strike_increment(option_chain)
            body_strike = self._find_recommended_body_strike(current_price, increment)
            recommended_width = self._recommend_wing_width(expected_move_analysis, increment)
            market_suitable = self._assess_market_suitability_for_butterfly(
                neutral_outlook_confirmed,
                iv_analysis,
                expected_move_analysis,
            )

            recommendation, confidence_score = self._generate_butterfly_recommendation(
                neutral_outlook_confirmed,
                iv_analysis,
                expected_move_analysis,
            )
            risk_warnings = self._identify_butterfly_risk_warnings(
                neutral_outlook_confirmed,
                iv_analysis,
                expected_move_analysis,
            )

            analysis = ButterflyAnalysis(
                market_suitable=market_suitable,
                neutral_outlook_confirmed=neutral_outlook_confirmed,
                iv_analysis=iv_analysis,
                expected_move_analysis=expected_move_analysis,
                body_strike_recommendation=body_strike if market_suitable else None,
                wing_width_recommendation=recommended_width if market_suitable else None,
                setup_recommendation=recommendation,
                confidence_score=confidence_score if market_suitable else 0.0,
                risk_warnings=risk_warnings,
            )
            self.current_analysis = analysis
            return analysis
        except Exception as exc:
            self.logger.error("Butterfly opportunity analysis failed: %s", exc)
            self.error_handler.handle_error(
                exc,
                {"method": "analyze_butterfly_opportunity"},
            )
            return ButterflyAnalysis(
                market_suitable=False,
                neutral_outlook_confirmed=False,
                iv_analysis={},
                expected_move_analysis={},
                body_strike_recommendation=None,
                wing_width_recommendation=None,
                setup_recommendation="Analysis failed",
                confidence_score=0.0,
                risk_warnings=["Analysis error occurred"],
            )

    def build_butterfly_setup(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame = None,
    ) -> ButterflySetup | None:
        """Build a concrete long call butterfly setup.

        Args:
            market_data: Recent underlying market data.
            option_chain: Optional normalized option chain.

        Returns:
            A normalized butterfly setup or ``None`` when conditions do not fit.
        """
        expiration_date = self._resolve_target_expiration()
        chain_frame = option_chain
        if chain_frame is None and self.prefer_live_chain:
            chain_frame = self._get_live_option_chain_dataframe(expiration_date)

        analysis = self.analyze_butterfly_opportunity(market_data, chain_frame)
        if not analysis.market_suitable:
            return None
        if analysis.body_strike_recommendation is None or analysis.wing_width_recommendation is None:
            return None

        current_price = float(market_data["close"].iloc[-1])
        body_strike = float(analysis.body_strike_recommendation)
        wing_width = float(analysis.wing_width_recommendation)
        lower_strike = round(body_strike - wing_width, 2)
        upper_strike = round(body_strike + wing_width, 2)

        if chain_frame is not None and not chain_frame.empty:
            lower_strike, body_strike, upper_strike = self._align_setup_to_chain(
                body_strike,
                wing_width,
                chain_frame,
            )
            wing_width = round(min(body_strike - lower_strike, upper_strike - body_strike), 2)

        expected_debit = self._estimate_entry_debit(
            chain_frame,
            lower_strike,
            body_strike,
            upper_strike,
        )
        if expected_debit <= 0.0 or expected_debit >= wing_width or expected_debit > self.max_debit:
            return None

        max_profit = round(max(0.01, wing_width - expected_debit), 2)
        max_loss = round(expected_debit, 2)
        lower_breakeven = round(lower_strike + expected_debit, 2)
        upper_breakeven = round(upper_strike - expected_debit, 2)
        probability = self._estimate_probability_of_profit(
            current_price,
            lower_breakeven,
            upper_breakeven,
            analysis.expected_move_analysis.get("expected_move_dollars", 0.0),
        )

        return ButterflySetup(
            underlying_price=current_price,
            lower_strike=lower_strike,
            body_strike=body_strike,
            upper_strike=upper_strike,
            expiration_date=expiration_date,
            days_to_expiry=max(0, self.target_dte),
            wing_width=wing_width,
            expected_debit=expected_debit,
            max_profit=max_profit,
            max_loss=max_loss,
            lower_breakeven=lower_breakeven,
            upper_breakeven=upper_breakeven,
            probability_of_profit=probability,
            directional_bias="neutral_slightly_bullish",
            setup_quality_score=analysis.confidence_score,
        )

    async def create_butterfly_position(
        self,
        market_data: pd.DataFrame,
        option_chain: pd.DataFrame = None,
    ) -> str | None:
        """Create and route a long call butterfly position through D32.

        Args:
            market_data: Recent underlying market data.
            option_chain: Optional normalized option chain.

        Returns:
            The created position identifier or ``None`` when routing fails.
        """
        if self.multileg_coordinator is None:
            self.logger.warning("Butterfly position routing unavailable without D32")
            return None

        setup = self.build_butterfly_setup(market_data, option_chain)
        if setup is None:
            return None

        try:
            self.strategy_state = ButterflyState.ENTERING
            structure = self._build_multileg_structure_from_setup(setup)
            position_id = await self.multileg_coordinator.execute_multileg_strategy(structure)
            if position_id:
                self.active_setups.append(setup)
                self.strategy_state = ButterflyState.ACTIVE
            return position_id
        except Exception as exc:
            self.strategy_state = ButterflyState.ERROR
            self.logger.error("Butterfly position creation failed: %s", exc, exc_info=True)
            return None

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
            self.logger.debug("Butterfly live expiration lookup failed: %s", exc)
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
            self.logger.debug("Butterfly live quote client unavailable: %s", exc)
            return None

    def _get_live_option_chain_dataframe(self, expiration_date: datetime) -> pd.DataFrame | None:
        """Fetch a live call chain and normalize it into a DataFrame."""
        client = self._get_live_quote_client()
        if client is None:
            return None

        try:
            contracts = client.get_option_chain_with_greeks(
                self.symbol,
                expiration_date.date().isoformat(),
            )
        except Exception as exc:
            self.logger.debug("Butterfly live option chain lookup failed: %s", exc)
            return None

        rows: list[dict[str, Any]] = []
        for contract in contracts or []:
            option_type = str(getattr(contract, "option_type", "") or "").lower()
            if option_type != "call":
                continue
            bid = float(getattr(contract, "bid", 0.0) or 0.0)
            ask = float(getattr(contract, "ask", 0.0) or 0.0)
            last = float(getattr(contract, "last", 0.0) or 0.0)
            mid = float(getattr(contract, "mid", 0.0) or 0.0)
            if mid <= 0.0 and bid > 0.0 and ask > 0.0:
                mid = (bid + ask) / 2.0
            rows.append(
                {
                    "symbol": getattr(contract, "symbol", self.symbol),
                    "strike": float(getattr(contract, "strike", 0.0) or 0.0),
                    "option_type": option_type,
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "mid": mid,
                    "iv": float(getattr(contract, "iv", 0.0) or 0.0),
                    "expiration": getattr(contract, "expiration", expiration_date.date().isoformat()),
                }
            )
        if not rows:
            return None
        return pd.DataFrame(rows)

    @staticmethod
    def _extract_expiration_values(payload: Any) -> list[Any]:
        """Extract expiration values from the common Tradier payload shapes."""
        if payload is None:
            return []
        if isinstance(payload, dict):
            expirations = payload.get("expirations")
            if isinstance(expirations, dict):
                dates = expirations.get("date")
                if isinstance(dates, list):
                    return dates
                if dates is not None:
                    return [dates]
            if isinstance(expirations, list):
                return expirations
            dates = payload.get("date")
            if isinstance(dates, list):
                return dates
            if dates is not None:
                return [dates]
        if isinstance(payload, list):
            return payload
        return []

    def _confirm_neutral_to_slightly_bullish_outlook(self, market_data: pd.DataFrame) -> bool:
        """Confirm that spot is stable enough for a pin-risk style trade."""
        closes = market_data["close"].dropna()
        if len(closes) < 3:
            return False
        recent = closes.tail(min(len(closes), 5))
        start_price = float(recent.iloc[0])
        end_price = float(recent.iloc[-1])
        if start_price <= 0.0:
            return False
        net_move = (end_price - start_price) / start_price
        realized_noise = recent.pct_change().dropna().abs().mean()
        return net_move >= -0.004 and net_move <= 0.008 and realized_noise <= 0.004

    def _analyze_iv_for_butterfly(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Score IV suitability for a debit butterfly."""
        if "iv" not in market_data.columns:
            return {
                "current_iv": None,
                "iv_rank": 30.0,
                "iv_quality_score": 0.6,
            }

        iv_values = market_data["iv"].dropna().astype(float)
        if iv_values.empty:
            return {
                "current_iv": None,
                "iv_rank": 30.0,
                "iv_quality_score": 0.6,
            }

        current_iv = float(iv_values.iloc[-1])
        iv_low = float(iv_values.min())
        iv_high = float(iv_values.max())
        iv_rank = 30.0
        if (iv_high - iv_low) < 0.05:
            iv_rank = 35.0
        elif iv_high > iv_low:
            iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100.0
        iv_quality_score = max(0.0, 1.0 - min(abs(iv_rank - 30.0) / 70.0, 1.0))
        return {
            "current_iv": current_iv,
            "iv_rank": round(iv_rank, 2),
            "iv_quality_score": round(iv_quality_score, 2),
        }

    def _analyze_expected_move_for_butterfly(
        self,
        market_data: pd.DataFrame,
        current_price: float,
    ) -> dict[str, Any]:
        """Estimate the near-term move budget relative to the body and wings."""
        closes = market_data["close"].dropna().astype(float)
        returns = closes.pct_change().dropna()
        realized_vol = float(returns.std(ddof=0)) if not returns.empty else 0.0
        intraday_component = 0.0
        if {"high", "low", "close"}.issubset(market_data.columns):
            sample = market_data[["high", "low", "close"]].dropna().tail(5)
            if not sample.empty:
                intraday_component = float(((sample["high"] - sample["low"]) / sample["close"]).mean())

        horizon_factor = max(self.remaining_session_fraction, 0.05)
        if self.target_dte > 0:
            horizon_factor = sqrt(max(self.target_dte, 1) / 252.0)

        minimum_move_floor = 0.0005 if self.target_dte == 0 else 0.0025
        expected_move_pct = max(
            realized_vol * max(sqrt(max(len(returns), 1)), 1.0) * horizon_factor,
            intraday_component * horizon_factor * 0.5,
            minimum_move_floor,
        )
        expected_move = round(current_price * expected_move_pct, 2)
        move_quality_score = max(0.0, min(1.0, 1.0 - (expected_move / max(self.wing_width, 0.5))))
        return {
            "expected_move_dollars": expected_move,
            "expected_move_pct": round(expected_move_pct, 4),
            "move_quality_score": round(move_quality_score, 2),
        }

    def _find_recommended_body_strike(self, current_price: float, increment: float) -> float:
        """Round spot to the nearest listed strike increment for the body."""
        if increment <= 0.0:
            return round(current_price, 2)
        rounded = round(current_price / increment) * increment
        return round(float(rounded), 2)

    def _recommend_wing_width(
        self,
        expected_move_analysis: dict[str, Any],
        increment: float,
    ) -> float:
        """Choose a symmetric wing width consistent with the expected move."""
        base_width = max(self.wing_width, float(expected_move_analysis.get("expected_move_dollars", 0.0) or 0.0))
        base_width = max(base_width, increment if increment > 0.0 else 1.0)
        if increment > 0.0:
            steps = max(1, round(base_width / increment))
            return round(steps * increment, 2)
        return round(base_width, 2)

    def _assess_market_suitability_for_butterfly(
        self,
        neutral_outlook_confirmed: bool,
        iv_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> bool:
        """Gate the trade to stable, reasonably priced butterfly conditions."""
        return (
            neutral_outlook_confirmed
            and float(iv_analysis.get("iv_quality_score", 0.0) or 0.0) >= 0.25
            and float(expected_move_analysis.get("move_quality_score", 0.0) or 0.0) >= 0.30
        )

    def _generate_butterfly_recommendation(
        self,
        neutral_outlook_confirmed: bool,
        iv_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> tuple[str, float]:
        """Generate the trade recommendation string and confidence score."""
        stability_score = 1.0 if neutral_outlook_confirmed else 0.0
        iv_score = float(iv_analysis.get("iv_quality_score", 0.0) or 0.0)
        move_score = float(expected_move_analysis.get("move_quality_score", 0.0) or 0.0)
        overall = round((stability_score * 0.45) + (iv_score * 0.20) + (move_score * 0.35), 2)

        if overall >= 0.8:
            recommendation = "Excellent long butterfly opportunity - stable tape with contained move risk"
        elif overall >= 0.6:
            recommendation = "Good long butterfly opportunity - range-bound conditions are supportive"
        elif overall >= 0.4:
            recommendation = "Marginal long butterfly opportunity - keep size small"
        else:
            recommendation = "Poor long butterfly opportunity - expected move is too large"
        return recommendation, overall

    def _identify_butterfly_risk_warnings(
        self,
        neutral_outlook_confirmed: bool,
        iv_analysis: dict[str, Any],
        expected_move_analysis: dict[str, Any],
    ) -> list[str]:
        """List trade-selection warnings for the current snapshot."""
        warnings: list[str] = []
        if not neutral_outlook_confirmed:
            warnings.append("Underlying is moving too aggressively for a pin-focused butterfly")
        iv_rank = float(iv_analysis.get("iv_rank", 0.0) or 0.0)
        if iv_rank > 70.0:
            warnings.append("IV is elevated, which can make the debit too expensive")
        expected_move = float(expected_move_analysis.get("expected_move_dollars", 0.0) or 0.0)
        if expected_move > self.wing_width:
            warnings.append("Expected move is larger than the configured wing width")
        return warnings

    def _align_setup_to_chain(
        self,
        body_target: float,
        wing_width: float,
        option_chain: pd.DataFrame,
    ) -> tuple[float, float, float]:
        """Align the setup to the nearest listed call strikes."""
        if option_chain.empty or "strike" not in option_chain.columns:
            return (
                round(body_target - wing_width, 2),
                round(body_target, 2),
                round(body_target + wing_width, 2),
            )

        option_types = option_chain.get("option_type")
        if option_types is None:
            calls = option_chain
        else:
            calls = option_chain[option_types.astype(str).str.lower() == "call"]
        strikes = sorted(float(value) for value in calls["strike"].dropna().unique())
        if len(strikes) < 3:
            return (
                round(body_target - wing_width, 2),
                round(body_target, 2),
                round(body_target + wing_width, 2),
            )

        body_candidates = sorted(strikes, key=lambda strike: abs(strike - body_target))
        best_candidate: tuple[float, float, float] | None = None
        best_score = float("-inf")

        for body_strike in body_candidates[:8]:
            lower_candidates = [strike for strike in strikes if strike < body_strike]
            upper_candidates = [strike for strike in strikes if strike > body_strike]
            if not lower_candidates or not upper_candidates:
                continue

            lower_strike = min(
                lower_candidates,
                key=lambda strike: abs((body_strike - strike) - wing_width),
            )
            upper_strike = min(
                upper_candidates,
                key=lambda strike: abs((strike - body_strike) - wing_width),
            )
            lower_width = body_strike - lower_strike
            upper_width = upper_strike - body_strike
            width_penalty = abs(lower_width - wing_width) + abs(upper_width - wing_width)
            symmetry_penalty = abs(lower_width - upper_width)
            distance_penalty = abs(body_strike - body_target) * 0.05
            score = -(width_penalty + symmetry_penalty + distance_penalty)
            if score > best_score:
                best_score = score
                best_candidate = (lower_strike, body_strike, upper_strike)

        if best_candidate is not None:
            return tuple(round(value, 2) for value in best_candidate)

        return (
            round(body_target - wing_width, 2),
            round(body_target, 2),
            round(body_target + wing_width, 2),
        )

    def _estimate_entry_debit(
        self,
        option_chain: pd.DataFrame | None,
        lower_strike: float,
        body_strike: float,
        upper_strike: float,
    ) -> float:
        """Estimate the net debit for the long call butterfly."""
        if option_chain is not None and not option_chain.empty:
            lower_mid = self._extract_call_mid(option_chain, lower_strike)
            body_mid = self._extract_call_mid(option_chain, body_strike)
            upper_mid = self._extract_call_mid(option_chain, upper_strike)
            if lower_mid is not None and body_mid is not None and upper_mid is not None:
                return round(max(0.01, lower_mid + upper_mid - (body_mid * 2.0)), 2)

        wing_width = min(body_strike - lower_strike, upper_strike - body_strike)
        fallback_debit = max(0.20, wing_width * 0.35)
        return round(fallback_debit, 2)

    def _estimate_probability_of_profit(
        self,
        current_price: float,
        lower_breakeven: float,
        upper_breakeven: float,
        expected_move: float,
    ) -> float:
        """Approximate the probability that price stays within the profit tent."""
        if expected_move <= 0.0:
            return 0.55
        lower_z = (lower_breakeven - current_price) / max(0.01, expected_move)
        upper_z = (upper_breakeven - current_price) / max(0.01, expected_move)
        lower_cdf = 0.5 * (1.0 + erf(lower_z / sqrt(2.0)))
        upper_cdf = 0.5 * (1.0 + erf(upper_z / sqrt(2.0)))
        probability = upper_cdf - lower_cdf
        return max(0.15, min(0.95, probability))

    def _infer_strike_increment(self, option_chain: pd.DataFrame | None) -> float:
        """Infer the listed strike increment or fall back to a one-dollar grid."""
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
    def _extract_call_mid(option_chain: pd.DataFrame, strike: float) -> float | None:
        """Extract a call midpoint for the requested strike from a chain DataFrame."""
        try:
            rows = option_chain[
                (option_chain["strike"].astype(float) == float(strike))
                & (option_chain["option_type"].astype(str).str.lower() == "call")
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
        setup: ButterflySetup,
    ) -> MultiLegStructure:
        """Convert a butterfly setup into the D32 execution structure."""
        if not MULTILEG_COORDINATOR_AVAILABLE:
            raise RuntimeError("D32 coordinator types are unavailable")

        legs = [
            CoordinatorOptionLeg("call", setup.lower_strike, 1, setup.expiration_date),
            CoordinatorOptionLeg("call", setup.body_strike, -2, setup.expiration_date),
            CoordinatorOptionLeg("call", setup.upper_strike, 1, setup.expiration_date),
        ]
        structure = MultiLegStructure(
            strategy_type=MultiLegStrategyType.BUTTERFLY,
            legs=legs,
            net_credit=-setup.expected_debit,
            max_profit=setup.max_profit,
            max_loss=setup.max_loss,
            breakeven_points=[setup.lower_breakeven, setup.upper_breakeven],
            probability_profit=setup.probability_of_profit,
            net_delta=0.02,
            net_gamma=0.03,
            net_theta=-0.02,
            net_vega=0.01,
            wing_width=setup.wing_width,
            body_width=0.0,
            risk_reward_ratio=(setup.max_loss / setup.max_profit) if setup.max_profit > 0 else 0.0,
        )
        structure.underlying_symbol = self.symbol
        structure.expiration_date = setup.expiration_date.date().isoformat()
        structure.contracts = self.default_contracts
        return structure


    # ==============================================================================
    # MODULE FUNCTIONS
    # ==============================================================================
def create_butterfly_strategy(
    event_manager: EventManager = None,
    risk_profile: RiskProfile = None,
    config: dict[str, Any] = None,
) -> ButterflyStrategy:
    """Create a native Butterfly strategy instance.

    Args:
        event_manager: Shared event bus used by the D-series runtime.
        risk_profile: Strategy risk profile used for sizing limits.
        config: Strategy configuration overrides.

    Returns:
        A configured ``ButterflyStrategy`` instance.
    """
    return ButterflyStrategy(event_manager, risk_profile, config)
