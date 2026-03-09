#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD33_RenaissanceMeanReversion.py
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
import uuid
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy,
    TradingSignal,
    StrategyPosition,
    EventManager,
    RiskProfile,
    SignalType,
    SignalStrength,
    PositionType,
    SIGNAL_EXPIRY_SECONDS
)
from Spyder.SpyderF_Analysis.SpyderF21_RenaissanceIndicators import (
    RenaissanceStyleSignalGenerator,
    MeanReversionIndicators,
    VolatilityIndicators,
    VolatilityRegime,
    RenaissanceSignal,
    ZSCORE_OVERBOUGHT,
    ZSCORE_OVERSOLD
)
from Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer import (
    RenaissancePositionSizer,
    PositionSizeMethod
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
DEFAULT_MIN_CONFIDENCE = 0.55           # Minimum confidence to trade (55%)
DEFAULT_MIN_IV_PERCENTILE = 25          # Minimum IV for buying options
DEFAULT_MAX_IV_PERCENTILE = 75          # Maximum IV for buying options
DEFAULT_MIN_DTE = 7                     # Minimum days to expiration
DEFAULT_MAX_DTE = 60                    # Maximum days to expiration
DEFAULT_MONEYNESS_MIN = 0.01            # 1% OTM minimum
DEFAULT_MONEYNESS_MAX = 0.05            # 5% OTM maximum

# Stop loss and take profit defaults
DEFAULT_STOP_LOSS_PCT = 0.30            # 30% stop loss
DEFAULT_TAKE_PROFIT_PCT = 0.50          # 50% take profit
THETA_STOP_LOSS_PCT = 0.50              # 50% stop loss for premium selling
THETA_TAKE_PROFIT_PCT = 0.50            # 50% profit target for premium selling


# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class OptionType(Enum):
    """Option type enumeration"""
    CALL = "call"
    PUT = "put"


class TradeAction(Enum):
    """Trade action type"""
    BUY = "buy"
    SELL = "sell"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionContract:
    """Represents an option contract"""
    symbol: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: OptionType
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    implied_vol: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float = 0.0

    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2

    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiration"""
        return (self.expiry - datetime.now()).days


@dataclass
class RenaissanceTradingSignal:
    """Extended trading signal for Renaissance strategy"""
    base_signal: TradingSignal
    contract: OptionContract | None
    trade_action: TradeAction
    strategy_type: str  # 'mean_reversion' or 'theta_decay'
    zscore: float
    iv_percentile: float
    volatility_regime: VolatilityRegime


# ==============================================================================
# RENAISSANCE MEAN REVERSION STRATEGY
# ==============================================================================
class RenaissanceMeanReversionStrategy(BaseStrategy):
    """
    Renaissance-inspired mean reversion strategy for SPY options.

    This strategy implements two core approaches:
    1. Mean Reversion: Trade options based on Z-score extremes
    2. Theta Decay: Sell premium when volatility is elevated

    The key innovation is confidence-scaled position sizing, where
    higher conviction signals receive larger allocations.
    """

    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any]
    ):
        """
        Initialize the Renaissance mean reversion strategy.

        Args:
            name: Strategy name
            event_manager: Event management system
            risk_profile: Risk management profile
            config: Strategy-specific configuration
        """
        super().__init__(name, event_manager, risk_profile, config)

        # Strategy-specific configuration
        self.min_confidence = config.get('min_confidence', DEFAULT_MIN_CONFIDENCE)
        self.min_iv_percentile = config.get('min_iv_percentile', DEFAULT_MIN_IV_PERCENTILE)
        self.max_iv_percentile = config.get('max_iv_percentile', DEFAULT_MAX_IV_PERCENTILE)
        self.min_dte = config.get('min_dte', DEFAULT_MIN_DTE)
        self.max_dte = config.get('max_dte', DEFAULT_MAX_DTE)
        self.moneyness_min = config.get('moneyness_min', DEFAULT_MONEYNESS_MIN)
        self.moneyness_max = config.get('moneyness_max', DEFAULT_MONEYNESS_MAX)

        # Initialize components
        self.signal_generator = RenaissanceStyleSignalGenerator(
            confidence_threshold=self.min_confidence
        )
        self.mean_rev_indicators = MeanReversionIndicators()
        self.vol_indicators = VolatilityIndicators()

        # Position sizer
        self.position_sizer = RenaissancePositionSizer(
            initial_capital=risk_profile.account_size,
            max_position_size=risk_profile.max_position_size,
            max_portfolio_risk=risk_profile.max_portfolio_risk,
            min_confidence=self.min_confidence
        )

        # Strategy state
        self.current_zscore: float = 0.0
        self.current_iv_percentile: float = 50.0
        self.current_volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL

        # Option chain reference
        self.option_chain: list[OptionContract] = []

        self.logger.info(
            f"RenaissanceMeanReversionStrategy initialized: "
            f"min_confidence={self.min_confidence:.2%}, "
            f"IV range=[{self.min_iv_percentile}%, {self.max_iv_percentile}%]"
        )

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """
        Generate trading signals based on Renaissance-style analysis.

        This method:
        1. Calculates Z-score for mean reversion detection
        2. Analyzes IV percentile for volatility regime
        3. Evaluates option contracts for trading opportunities
        4. Generates signals with confidence scores

        Args:
            market_data: DataFrame with 'close' and optionally 'implied_vol'

        Returns:
            List of trading signals
        """
        signals = []

        try:
            # Update market indicators
            self._update_market_indicators(market_data)

            # Generate Renaissance-style signal
            ren_signal = self.signal_generator.get_current_signal(market_data)

            if ren_signal is None or ren_signal.confidence < self.min_confidence:
                return signals

            # Update state
            self.current_zscore = ren_signal.zscore
            self.current_iv_percentile = ren_signal.iv_percentile
            self.current_volatility_regime = ren_signal.volatility_regime

            # Get current SPY price
            spy_price = market_data['close'].iloc[-1]

            # Evaluate each contract in the option chain
            for contract in self.option_chain:
                signal = self._evaluate_contract(
                    contract=contract,
                    spy_price=spy_price,
                    ren_signal=ren_signal
                )

                if signal is not None and signal.confidence >= self.min_confidence:
                    signals.append(signal)

            # Sort by confidence (highest first)
            signals.sort(key=lambda x: x.confidence, reverse=True)

            # Limit to top N signals
            max_signals = self.config.get('max_signals_per_cycle', 3)
            signals = signals[:max_signals]

            self.logger.info(
                f"Generated {len(signals)} signals | "
                f"Z-score: {self.current_zscore:.2f} | "
                f"IV Pct: {self.current_iv_percentile:.1f}%"
            )

        except Exception as e:
            self.error_handler.handle_error(
                e, {'method': 'generate_signals', 'strategy': self.name}
            )

        return signals

    def _update_market_indicators(self, market_data: pd.DataFrame) -> None:
        """Update all market indicators."""
        if 'close' in market_data.columns:
            zscore_series = self.mean_rev_indicators.calculate_zscore(
                market_data['close'], window=20
            )
            if len(zscore_series) > 0 and not pd.isna(zscore_series.iloc[-1]):
                self.current_zscore = zscore_series.iloc[-1]

        if 'implied_vol' in market_data.columns:
            iv_pct_series = self.vol_indicators.iv_percentile(
                market_data['implied_vol'], window=252
            )
            if len(iv_pct_series) > 0 and not pd.isna(iv_pct_series.iloc[-1]):
                self.current_iv_percentile = iv_pct_series.iloc[-1]

        self.current_volatility_regime = self.vol_indicators.classify_volatility_regime(
            self.current_iv_percentile
        )

    def _evaluate_contract(
        self,
        contract: OptionContract,
        spy_price: float,
        ren_signal: RenaissanceSignal
    ) -> TradingSignal | None:
        """
        Evaluate a single option contract for trading opportunity.

        Implements two strategies:
        1. Mean Reversion: Buy options when price is at extremes
        2. Theta Decay: Sell options when IV is elevated

        Args:
            contract: Option contract to evaluate
            spy_price: Current SPY price
            ren_signal: Renaissance-style signal

        Returns:
            TradingSignal if opportunity found, None otherwise
        """
        try:
            # Check days to expiration
            dte = contract.days_to_expiry
            if dte < self.min_dte or dte > self.max_dte:
                return None

            # Calculate moneyness
            if contract.option_type == OptionType.CALL:
                moneyness = (contract.strike - spy_price) / spy_price
            else:
                moneyness = (spy_price - contract.strike) / spy_price

            # Focus on slightly OTM options
            if abs(moneyness) < self.moneyness_min or abs(moneyness) > self.moneyness_max:
                return None

            # Initialize signal components
            signal_type = None
            confidence = 0.0
            reasoning = ""
            stop_loss_pct = DEFAULT_STOP_LOSS_PCT
            take_profit_pct = DEFAULT_TAKE_PROFIT_PCT

            # Strategy 1: Mean Reversion
            zscore = ren_signal.zscore
            iv_pct = ren_signal.iv_percentile

            if zscore > ZSCORE_OVERBOUGHT:
                # Overbought - buy puts (expect reversion down)
                if contract.option_type == OptionType.PUT and iv_pct < self.max_iv_percentile:
                    signal_type = SignalType.BUY
                    confidence = min(0.5 + (zscore - ZSCORE_OVERBOUGHT) * 0.1, 0.95)
                    reasoning = f"Mean reversion: Z={zscore:.2f} overbought, buying puts"

            elif zscore < ZSCORE_OVERSOLD:
                # Oversold - buy calls (expect reversion up)
                if contract.option_type == OptionType.CALL and iv_pct < self.max_iv_percentile:
                    signal_type = SignalType.BUY
                    confidence = min(0.5 + (abs(zscore) - abs(ZSCORE_OVERSOLD)) * 0.1, 0.95)
                    reasoning = f"Mean reversion: Z={zscore:.2f} oversold, buying calls"

            # Strategy 2: Theta Decay (sell premium when IV is high)
            if signal_type is None:
                if iv_pct > self.max_iv_percentile and dte <= 30:
                    if abs(moneyness) > 0.02:  # Further OTM for selling
                        signal_type = SignalType.SELL
                        confidence = 0.55 + (iv_pct - self.max_iv_percentile) * 0.005
                        confidence = min(confidence, 0.85)
                        reasoning = f"Theta decay: IV pct={iv_pct:.1f}%, selling premium"
                        stop_loss_pct = THETA_STOP_LOSS_PCT
                        take_profit_pct = THETA_TAKE_PROFIT_PCT

            if signal_type is None:
                return None

            # Calculate entry, stop, and target prices
            if signal_type == SignalType.BUY:
                entry_price = contract.ask  # Buy at ask
                stop_loss = entry_price * (1 - stop_loss_pct)
                take_profit = entry_price * (1 + take_profit_pct)
            else:  # SELL
                entry_price = contract.bid  # Sell at bid
                stop_loss = entry_price * (1 + stop_loss_pct)
                take_profit = entry_price * (1 - take_profit_pct)

            # Calculate position size
            size_result = self.position_sizer.calculate_position_size(
                entry_price=entry_price,
                stop_loss=stop_loss,
                confidence=confidence,
                method=PositionSizeMethod.CONFIDENCE_SCALED
            )

            if size_result.num_contracts == 0:
                return None

            # Create trading signal
            trading_signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=signal_type,
                symbol=contract.symbol,
                strength=self._confidence_to_strength(confidence),
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=size_result.num_contracts,
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=SIGNAL_EXPIRY_SECONDS),
                metadata={
                    'contract': contract.symbol,
                    'strike': contract.strike,
                    'expiry': contract.expiry.isoformat(),
                    'option_type': contract.option_type.value,
                    'zscore': zscore,
                    'iv_percentile': iv_pct,
                    'volatility_regime': ren_signal.volatility_regime.value,
                    'reasoning': reasoning,
                    'strategy': 'renaissance_mean_reversion'
                }
            )

            return trading_signal

        except Exception as e:
            self.error_handler.handle_error(
                e, {'method': '_evaluate_contract', 'contract': contract.symbol}
            )
            return None

    def _confidence_to_strength(self, confidence: float) -> SignalStrength:
        """Convert confidence score to signal strength."""
        if confidence >= 0.85:
            return SignalStrength.VERY_STRONG
        elif confidence >= 0.70:
            return SignalStrength.STRONG
        elif confidence >= 0.55:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def validate_signal(self, signal: TradingSignal) -> bool:
        """
        Validate a trading signal before execution.

        Checks:
        1. Confidence threshold
        2. Position limits
        3. Daily trade limits
        4. Signal freshness

        Args:
            signal: Trading signal to validate

        Returns:
            True if signal is valid
        """
        try:
            # Check confidence
            if signal.confidence < self.min_confidence:
                self.logger.debug(f"Signal rejected: confidence {signal.confidence:.2%} below minimum")
                return False

            # Check signal freshness
            if not signal.is_valid():
                self.logger.debug("Signal rejected: expired")
                return False

            # Check position limits
            if len(self.positions) >= self.max_positions:
                self.logger.debug("Signal rejected: max positions reached")
                return False

            # Check for duplicate position
            for pos in self.positions.values():
                if pos.symbol == signal.symbol:
                    self.logger.debug(f"Signal rejected: position already exists for {signal.symbol}")
                    return False

            # Check entry price validity
            if signal.entry_price <= 0:
                self.logger.debug("Signal rejected: invalid entry price")
                return False

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'validate_signal'})
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """
        Calculate position size using Renaissance-style confidence scaling.

        Position size is proportional to signal confidence.

        Args:
            signal: Trading signal

        Returns:
            Position size in contracts
        """
        try:
            result = self.position_sizer.calculate_position_size(
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                confidence=signal.confidence,
                method=PositionSizeMethod.CONFIDENCE_SCALED
            )

            return result.num_contracts

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'calculate_position_size'})
            return 0

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        """
        Determine if position should be exited.

        Exit conditions:
        1. Stop loss hit
        2. Take profit hit
        3. Time-based exit (approaching expiration)
        4. Mean reversion completed (Z-score normalized)

        Args:
            position: Current position
            market_data: Current market data

        Returns:
            Tuple of (should_exit, reason)
        """
        try:
            current_price = position.current_price

            # Check stop loss
            if position.position_type == PositionType.LONG:
                if current_price <= position.stop_loss:
                    return True, "Stop loss hit"
                if current_price >= position.take_profit:
                    return True, "Take profit hit"
            else:  # SHORT (sold options)
                if current_price >= position.stop_loss:
                    return True, "Stop loss hit"
                if current_price <= position.take_profit:
                    return True, "Take profit hit"

            # Check for mean reversion completion
            if abs(self.current_zscore) < 0.5:  # Z-score normalized
                # Exit with profit if P&L is positive
                if position.unrealized_pnl > 0:
                    return True, "Mean reversion completed, Z-score normalized"

            # Time-based exit: close before expiration
            metadata = position.metadata
            if 'expiry' in metadata:
                expiry = datetime.fromisoformat(metadata['expiry'])
                days_remaining = (expiry - datetime.now()).days
                if days_remaining <= 3:  # Close 3 days before expiration
                    return True, "Approaching expiration"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'should_exit_position'})
            return False, ""

    def update_option_chain(self, option_chain: list[OptionContract]) -> None:
        """
        Update the available option chain.

        Args:
            option_chain: List of available option contracts
        """
        self.option_chain = option_chain
        self.logger.debug(f"Option chain updated: {len(option_chain)} contracts")

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get strategy-specific statistics."""
        base_stats = self.get_state()

        metrics = self.position_sizer.get_metrics()

        return {
            **base_stats,
            'current_zscore': self.current_zscore,
            'current_iv_percentile': self.current_iv_percentile,
            'volatility_regime': self.current_volatility_regime.value,
            'position_sizer_metrics': metrics,
            'strategy_type': 'renaissance_mean_reversion',
            'min_confidence': self.min_confidence,
            'iv_range': f"[{self.min_iv_percentile}%, {self.max_iv_percentile}%]",
            'dte_range': f"[{self.min_dte}, {self.max_dte}]"
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_renaissance_strategy(
    event_manager: EventManager,
    risk_profile: RiskProfile,
    config: dict[str, Any] | None = None
) -> RenaissanceMeanReversionStrategy:
    """
    Factory function to create a Renaissance mean reversion strategy.

    Args:
        event_manager: Event management system
        risk_profile: Risk management profile
        config: Strategy configuration (optional)

    Returns:
        Configured RenaissanceMeanReversionStrategy instance
    """
    default_config = {
        'min_confidence': 0.55,
        'min_iv_percentile': 25,
        'max_iv_percentile': 75,
        'min_dte': 7,
        'max_dte': 60,
        'moneyness_min': 0.01,
        'moneyness_max': 0.05,
        'max_positions': 5,
        'max_signals_per_cycle': 3,
        'auto_execute': False
    }

    if config:
        default_config.update(config)

    return RenaissanceMeanReversionStrategy(
        name="RenaissanceMeanReversion",
        event_manager=event_manager,
        risk_profile=risk_profile,
        config=default_config
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.05,
        max_portfolio_risk=0.02,
        max_loss_per_trade=0.01
    )

    config = {
        'min_confidence': 0.55,
        'max_positions': 5,
        'auto_execute': False
    }

    # Create strategy
    strategy = create_renaissance_strategy(event_manager, risk_profile, config)


    # Generate sample market data
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')

    # Simulate SPY price with mean reversion
    price = 450
    prices = [price]
    for _ in range(99):
        change = np.random.randn() * 2 + (450 - price) * 0.05
        price += change
        prices.append(price)

    market_data = pd.DataFrame({
        'close': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'volume': np.random.randint(50000000, 100000000, 100),
        'implied_vol': np.random.uniform(0.15, 0.35, 100)
    }, index=dates)


    # Create sample option chain
    current_price = prices[-1]
    sample_options = []
    for i in range(-5, 6):
        strike = round(current_price + i * 2, 0)
        for opt_type in [OptionType.CALL, OptionType.PUT]:
            sample_options.append(OptionContract(
                symbol=f"SPY250117{opt_type.value[0].upper()}{int(strike)}",
                underlying="SPY",
                strike=strike,
                expiry=datetime.now() + timedelta(days=30),
                option_type=opt_type,
                bid=max(0.5, 5 - abs(i) * 0.5),
                ask=max(0.6, 5.2 - abs(i) * 0.5),
                last=max(0.55, 5.1 - abs(i) * 0.5),
                volume=1000,
                open_interest=5000,
                implied_vol=0.25,
                delta=0.5 - i * 0.05 if opt_type == OptionType.CALL else -0.5 + i * 0.05,
                gamma=0.02,
                theta=-0.05,
                vega=0.15
            ))

    strategy.update_option_chain(sample_options)


    # Start strategy

    if strategy.start():
        pass

    # Process market data
    strategy.process_market_data(market_data)

    # Get signals
    signals = strategy.get_signals()

    for _signal in signals:
        pass

    # Get strategy stats

    stats = strategy.get_strategy_stats()

    # Stop strategy
    if strategy.stop():
        pass

