#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF21_RenaissanceIndicators.py
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
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats

# pykalman: Kalman filter / smoother with EM parameter estimation
try:
    from pykalman import KalmanFilter
    _PYKALMAN_AVAILABLE = True
except ImportError:
    _PYKALMAN_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

ZSCORE_OVERBOUGHT = 2.0
ZSCORE_OVERSOLD = -2.0
ZSCORE_EXTREME_OVERBOUGHT = 3.0
ZSCORE_EXTREME_OVERSOLD = -3.0

# Volatility percentile thresholds
IV_HIGH_PERCENTILE = 75
IV_LOW_PERCENTILE = 25
IV_EXTREME_HIGH = 90
IV_EXTREME_LOW = 10

# Signal confidence thresholds
MIN_CONFIDENCE_THRESHOLD = 0.50
HIGH_CONFIDENCE_THRESHOLD = 0.75

# Default lookback periods
DEFAULT_ZSCORE_WINDOW = 20
DEFAULT_IV_WINDOW = 252  # Trading days in a year
DEFAULT_VOLATILITY_WINDOW = 60


# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class MeanReversionSignal(Enum):
    """Mean reversion signal types"""
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    NEUTRAL = "neutral"
    BUY = "buy"
    STRONG_BUY = "strong_buy"


class VolatilityRegime(Enum):
    """Volatility regime classification"""
    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RenaissanceSignal:
    """Renaissance-style trading signal with full context"""
    timestamp: datetime
    signal_type: MeanReversionSignal
    confidence: float  # 0.0 to 1.0
    zscore: float
    iv_percentile: float
    bb_percent_b: float
    volatility_regime: VolatilityRegime
    reasoning: str

    # Component signals
    mean_rev_component: float = 0.0
    vol_component: float = 0.0
    bb_component: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'zscore': self.zscore,
            'iv_percentile': self.iv_percentile,
            'bb_percent_b': self.bb_percent_b,
            'volatility_regime': self.volatility_regime.value,
            'reasoning': self.reasoning,
            'components': {
                'mean_reversion': self.mean_rev_component,
                'volatility': self.vol_component,
                'bollinger': self.bb_component
            }
        }


@dataclass
class SpreadAnalysis:
    """Bid-ask spread analysis results"""
    spread: float
    spread_pct: float
    avg_spread: float
    spread_volatility: float
    liquidity_score: float  # 0-1, higher is better


# ==============================================================================
# MEAN REVERSION INDICATORS
# ==============================================================================
class MeanReversionIndicators:
    """
    Statistical mean reversion indicators based on Renaissance Technologies' approach.

    Renaissance's core insight: prices exhibit temporary deviations from equilibrium
    that can be exploited through statistical analysis.
    """

    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

    def calculate_zscore(self, prices: pd.Series, window: int = DEFAULT_ZSCORE_WINDOW) -> pd.Series:
        """
        Calculate Z-score for mean reversion detection.

        Z-score measures how many standard deviations the current price is from
        the rolling mean. Renaissance uses this to identify statistical anomalies.

        Interpretation:
            - Z > 2.0: Overbought, expect reversion down
            - Z < -2.0: Oversold, expect reversion up
            - |Z| > 3.0: Extreme condition, high-probability reversion

        Args:
            prices: Series of prices
            window: Lookback window for calculating mean and std

        Returns:
            Series of Z-scores
        """
        try:
            rolling_mean = prices.rolling(window=window).mean()
            rolling_std = prices.rolling(window=window).std()

            # Avoid division by zero
            zscore = (prices - rolling_mean) / (rolling_std + 1e-10)

            return zscore

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'calculate_zscore'})
            return pd.Series(index=prices.index, dtype=float)

    def bollinger_bands(self, prices: pd.Series, window: int = 20,
                       num_std: float = 2.0) -> dict[str, pd.Series]:
        """
        Calculate Bollinger Bands for statistical deviation detection.

        Renaissance uses statistical deviation bands to identify when prices
        move beyond normal ranges (typically 2-3 standard deviations).

        Args:
            prices: Series of prices
            window: Lookback window
            num_std: Number of standard deviations for bands

        Returns:
            Dictionary with upper, middle, lower bands, bandwidth, and %B
        """
        try:
            middle_band = prices.rolling(window=window).mean()
            std = prices.rolling(window=window).std()
            upper_band = middle_band + (std * num_std)
            lower_band = middle_band - (std * num_std)

            # Bandwidth measures volatility - useful for squeeze conditions
            bandwidth = (upper_band - lower_band) / (middle_band + 1e-10)

            # %B indicates where price is relative to bands
            # %B > 1: Above upper band (overbought)
            # %B < 0: Below lower band (oversold)
            percent_b = (prices - lower_band) / (upper_band - lower_band + 1e-10)

            return {
                'upper': upper_band,
                'middle': middle_band,
                'lower': lower_band,
                'bandwidth': bandwidth,
                'percent_b': percent_b
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'bollinger_bands'})
            return {}

    def statistical_arbitrage_signal(self, price1: pd.Series, price2: pd.Series,
                                     window: int = 60, entry_threshold: float = 2.0,
                                     exit_threshold: float = 0.5) -> pd.DataFrame:
        """
        Generate statistical arbitrage signals between two correlated instruments.

        This is the core of Renaissance's pairs trading strategy.
        Identifies when the price ratio deviates from its historical mean.

        Args:
            price1: Price series of first instrument
            price2: Price series of second instrument
            window: Lookback window for calculating statistics
            entry_threshold: Z-score threshold for entering trade (e.g., 2.0 = 2 std devs)
            exit_threshold: Z-score threshold for exiting trade

        Returns:
            DataFrame with signals and statistics
        """
        try:
            # Calculate price ratio
            ratio = price1 / (price2 + 1e-10)

            # Calculate rolling statistics
            ratio_mean = ratio.rolling(window=window).mean()
            ratio_std = ratio.rolling(window=window).std()

            # Calculate Z-score of ratio
            zscore = (ratio - ratio_mean) / (ratio_std + 1e-10)

            # Generate signals
            signals = pd.DataFrame(index=price1.index)
            signals['ratio'] = ratio
            signals['zscore'] = zscore
            signals['signal'] = 0

            # Entry signals
            signals.loc[zscore > entry_threshold, 'signal'] = -1  # Short the spread
            signals.loc[zscore < -entry_threshold, 'signal'] = 1  # Long the spread

            # Generate signals
            signals = pd.DataFrame(index=price1.index)
            signals['ratio'] = ratio
            signals['zscore'] = zscore
            signals['signal'] = 0

            # Entry signals
            signals.loc[zscore > entry_threshold, 'signal'] = -1  # Short the spread
            signals.loc[zscore < -entry_threshold, 'signal'] = 1  # Long the spread

            # Exit signals (mean reversion occurred)
            signals.loc[abs(zscore) < exit_threshold, 'signal'] = 0

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'statistical_arbitrage_signal'})
            return pd.DataFrame()

    def kalman_smooth_price(
        self,
        prices: pd.Series,
        n_iter: int = 10,
    ) -> pd.Series:
        """
        Apply a Kalman smoother (pykalman) to a price series to separate signal
        from noise.  Parameters are estimated via the EM algorithm.

        Falls back to a simple rolling-mean when pykalman is not available.

        Args:
            prices: Raw price series (indexed by datetime or int).
            n_iter:  Number of EM iterations for parameter estimation.

        Returns:
            Smoothed price series with the same index as ``prices``.
        """
        if prices is None or len(prices) < 5:
            return prices

        if not _PYKALMAN_AVAILABLE:
            # Graceful fallback: rolling mean with a small window
            return prices.rolling(window=5, min_periods=1).mean()

        try:
            obs = prices.values.reshape(-1, 1).astype(float)
            kf = KalmanFilter(
                transition_matrices=[1],
                observation_matrices=[1],
                initial_state_mean=obs[0],
                initial_state_covariance=1,
                observation_covariance=1,
                transition_covariance=0.05,
            )
            kf = kf.em(obs, n_iter=n_iter)
            state_means, _ = kf.smooth(obs)
            return pd.Series(state_means.flatten(), index=prices.index, name=f"{prices.name}_kalman")  # noqa: E501
        except Exception as exc:
            self.error_handler.handle_error(exc, {'method': 'kalman_smooth_price'})
            return prices.rolling(window=5, min_periods=1).mean()


# ==============================================================================
# VOLATILITY INDICATORS
# ==============================================================================
class VolatilityIndicators:
    """
    Volatility-based indicators for options trading.

    Renaissance recognizes that volatility itself is mean-reverting,
    making it a powerful predictor for options strategies.
    """

    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

    def historical_volatility(self, prices: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate historical volatility (annualized).

        Args:
            prices: Series of prices
            window: Lookback window

        Returns:
            Series of annualized volatility
        """
        try:
            log_returns = np.log(prices / prices.shift(1))
            volatility = log_returns.rolling(window=window).std() * np.sqrt(252)
            return volatility

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'historical_volatility'})
            return pd.Series(index=prices.index, dtype=float)

    def iv_percentile(self, implied_vol: pd.Series, window: int = DEFAULT_IV_WINDOW) -> pd.Series:
        """
        Calculate implied volatility percentile for mean reversion.

        High IV percentile suggests volatility may revert lower (sell premium).
        Low IV percentile suggests volatility may expand (buy premium).

        Args:
            implied_vol: Series of implied volatility values
            window: Lookback window (252 = 1 year of trading days)

        Returns:
            Series of IV percentile (0-100)
        """
        try:
            def percentile_rank(series):
                if len(series) < 2:
                    return np.nan
                return stats.percentileofscore(series[:-1], series.iloc[-1])

            iv_pct = implied_vol.rolling(window=window, min_periods=2).apply(
                percentile_rank, raw=False
            )
            return iv_pct

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'iv_percentile'})
            return pd.Series(index=implied_vol.index, dtype=float)

    def volatility_zscore(self, implied_vol: pd.Series,
                          window: int = DEFAULT_VOLATILITY_WINDOW) -> pd.Series:
        """
        Calculate Z-score of implied volatility for mean reversion trading.

        Args:
            implied_vol: Series of implied volatility
            window: Lookback window

        Returns:
            Series of volatility Z-scores
        """
        try:
            iv_mean = implied_vol.rolling(window=window).mean()
            iv_std = implied_vol.rolling(window=window).std()
            iv_zscore = (implied_vol - iv_mean) / (iv_std + 1e-10)
            return iv_zscore

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'volatility_zscore'})
            return pd.Series(index=implied_vol.index, dtype=float)

    def classify_volatility_regime(self, iv_percentile: float) -> VolatilityRegime:
        """
        Classify current volatility regime based on IV percentile.

        Args:
            iv_percentile: Current IV percentile (0-100)

        Returns:
            VolatilityRegime enum value
        """
        if iv_percentile < IV_EXTREME_LOW:
            return VolatilityRegime.VERY_LOW
        elif iv_percentile < IV_LOW_PERCENTILE:
            return VolatilityRegime.LOW
        elif iv_percentile <= IV_HIGH_PERCENTILE:
            return VolatilityRegime.NORMAL
        elif iv_percentile <= IV_EXTREME_HIGH:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.VERY_HIGH


# ==============================================================================
# MARKET MICROSTRUCTURE INDICATORS
# ==============================================================================
class MarketMicrostructureIndicators:
    """
    Market microstructure indicators for high-frequency trading patterns.

    Renaissance analyzes order flow and market microstructure to
    optimize execution and identify short-term alpha.
    """

    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

    def bid_ask_spread_analysis(self, bid: pd.Series, ask: pd.Series,
                                 mid_price: pd.Series, window: int = 20) -> SpreadAnalysis:
        """
        Analyze bid-ask spread for liquidity and execution quality.

        Renaissance optimizes transaction costs by analyzing spread patterns.

        Args:
            bid: Series of bid prices
            ask: Series of ask prices
            mid_price: Series of mid prices
            window: Rolling window for analysis

        Returns:
            SpreadAnalysis with spread metrics
        """
        try:
            spread = ask - bid
            spread_pct = spread / (mid_price + 1e-10)

            # Rolling average spread (lower = better liquidity)
            avg_spread = spread_pct.rolling(window=window).mean()

            # Spread volatility (higher = less stable liquidity)
            spread_vol = spread_pct.rolling(window=window).std()

            # Calculate liquidity score (0-1, higher is better)
            current_spread_pct = spread_pct.iloc[-1] if len(spread_pct) > 0 else 0
            liquidity_score = max(0, 1 - (current_spread_pct * 100))  # Normalize

            return SpreadAnalysis(
                spread=spread.iloc[-1] if len(spread) > 0 else 0,
                spread_pct=current_spread_pct,
                avg_spread=avg_spread.iloc[-1] if len(avg_spread) > 0 else 0,
                spread_volatility=spread_vol.iloc[-1] if len(spread_vol) > 0 else 0,
                liquidity_score=min(1, max(0, liquidity_score))
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'bid_ask_spread_analysis'})
            return SpreadAnalysis(0, 0, 0, 0, 0)

    def order_flow_imbalance(self, buy_volume: pd.Series, sell_volume: pd.Series,
                              window: int = 20) -> pd.Series:
        """
        Calculate order flow imbalance.

        Persistent imbalances can predict short-term price movements.

        Args:
            buy_volume: Series of buy-side volume
            sell_volume: Series of sell-side volume
            window: Smoothing window

        Returns:
            Series of order flow imbalance (-1 to 1)
        """
        try:
            total_volume = buy_volume + sell_volume + 1e-10
            imbalance = (buy_volume - sell_volume) / total_volume

            # Smooth the imbalance
            smoothed_imbalance = imbalance.rolling(window=window).mean()

            return smoothed_imbalance

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'order_flow_imbalance'})
            return pd.Series(index=buy_volume.index, dtype=float)


# ==============================================================================
# OPTIONS GREEKS INDICATORS
# ==============================================================================
class OptionsGreeksIndicators:
    """
    Options Greeks-based indicators for systematic trading.

    Gamma exposure and theta decay patterns provide actionable signals.
    """

    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

    def gamma_exposure_imbalance(self, strikes: np.ndarray, gamma_profile: np.ndarray,
                                  open_interest: np.ndarray, current_price: float) -> float:
        """
        Calculate market-wide gamma exposure imbalance.

        Large gamma imbalances can predict price movements as dealers hedge.

        Args:
            strikes: Array of strike prices
            gamma_profile: Array of gamma values at each strike
            open_interest: Array of open interest at each strike
            current_price: Current underlying price

        Returns:
            Net gamma exposure (positive = dealers long gamma)
        """
        try:
            # Weight gamma by open interest
            weighted_gamma = gamma_profile * open_interest
            net_gamma = np.sum(weighted_gamma)

            return net_gamma

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'gamma_exposure_imbalance'})
            return 0.0

    def theta_decay_score(self, days_to_expiry: int, theta: float) -> float:
        """
        Generate score based on theta decay acceleration.

        Theta decay accelerates in the final weeks before expiration.

        Args:
            days_to_expiry: Days until option expiration
            theta: Current theta value

        Returns:
            Theta decay score (higher = more attractive for premium selling)
        """
        try:
            # Theta decay accelerates significantly in last 30 days
            if days_to_expiry <= 7:
                decay_multiplier = 3.0
            elif days_to_expiry <= 14:
                decay_multiplier = 2.0
            elif days_to_expiry <= 30:
                decay_multiplier = 1.5
            else:
                decay_multiplier = 1.0

            theta_score = abs(theta) * decay_multiplier
            return theta_score

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'theta_decay_score'})
            return 0.0


# ==============================================================================
# RENAISSANCE-STYLE SIGNAL GENERATOR
# ==============================================================================
class RenaissanceStyleSignalGenerator:
    """
    Combines multiple indicators to generate Renaissance-style trading signals.

    The key insight: combine multiple weakly predictive signals into a robust
    trading model. Each signal contributes with appropriate weights based on
    its historical predictive power.
    """

    def __init__(self, confidence_threshold: float = MIN_CONFIDENCE_THRESHOLD):
        """
        Args:
            confidence_threshold: Minimum confidence score to generate signal (0-1)
        """
        self.confidence_threshold = confidence_threshold
        self.mean_rev = MeanReversionIndicators()
        self.vol_ind = VolatilityIndicators()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Signal weights (can be tuned based on backtesting)
        self.mean_rev_weight = 0.4
        self.vol_weight = 0.3
        self.bb_weight = 0.3

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate composite trading signals from multiple indicators.

        Args:
            data: DataFrame with columns: 'close', optionally 'implied_vol'

        Returns:
            DataFrame with signals and confidence scores
        """
        try:
            signals = pd.DataFrame(index=data.index)

            # Calculate Z-score for mean reversion
            zscore = self.mean_rev.calculate_zscore(data['close'], window=20)

            # Calculate Bollinger Bands
            bb = self.mean_rev.bollinger_bands(data['close'], window=20, num_std=2.0)

            # Calculate IV percentile if available
            if 'implied_vol' in data.columns:
                iv_pct = self.vol_ind.iv_percentile(data['implied_vol'], window=252)
                iv_zscore = self.vol_ind.volatility_zscore(data['implied_vol'], window=60)
            else:
                iv_pct = pd.Series(50, index=data.index)  # Neutral if no IV data
                iv_zscore = pd.Series(0, index=data.index)

            # Generate component signals
            # Mean reversion signal: extreme Z-scores suggest reversal
            mean_rev_signal = np.where(zscore > ZSCORE_OVERBOUGHT, -1,
                                       np.where(zscore < ZSCORE_OVERSOLD, 1, 0))

            # Volatility signal: high IV suggests selling premium, low IV suggests buying
            vol_signal = np.where(iv_pct > IV_HIGH_PERCENTILE, -1,
                                 np.where(iv_pct < IV_LOW_PERCENTILE, 1, 0))

            # Bollinger Band signal
            if 'percent_b' in bb:
                bb_signal = np.where(bb['percent_b'] > 1, -1,
                                    np.where(bb['percent_b'] < 0, 1, 0))
            else:
                bb_signal = np.zeros(len(data))

            # Combine signals with weights
            composite_signal = (mean_rev_signal * self.mean_rev_weight +
                               vol_signal * self.vol_weight +
                               bb_signal * self.bb_weight)

            # Calculate confidence based on signal strength
            confidence = np.abs(composite_signal)

            # Final signal (only when confidence exceeds threshold)
            final_signal = np.where(confidence >= self.confidence_threshold,
                                   np.sign(composite_signal), 0)

            # Build output DataFrame
            signals['zscore'] = zscore
            signals['iv_percentile'] = iv_pct
            signals['iv_zscore'] = iv_zscore
            signals['bb_percent_b'] = bb.get('percent_b', pd.Series(0.5, index=data.index))
            signals['mean_rev_signal'] = mean_rev_signal
            signals['vol_signal'] = vol_signal
            signals['bb_signal'] = bb_signal
            signals['composite_signal'] = composite_signal
            signals['confidence'] = confidence
            signals['final_signal'] = final_signal

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'generate_signals'})
            return pd.DataFrame()

    def get_current_signal(self, data: pd.DataFrame) -> RenaissanceSignal | None:
        """
        Get the current trading signal with full context.

        Args:
            data: DataFrame with market data

        Returns:
            RenaissanceSignal if conditions are met, None otherwise
        """
        try:
            signals = self.generate_signals(data)

            if signals.empty or len(signals) == 0:
                return None

            # Get latest values
            latest = signals.iloc[-1]

            # Determine signal type
            final_sig = latest['final_signal']
            if final_sig > 0:
                if latest['confidence'] > HIGH_CONFIDENCE_THRESHOLD:
                    signal_type = MeanReversionSignal.STRONG_BUY
                else:
                    signal_type = MeanReversionSignal.BUY
            elif final_sig < 0:
                if latest['confidence'] > HIGH_CONFIDENCE_THRESHOLD:
                    signal_type = MeanReversionSignal.STRONG_SELL
                else:
                    signal_type = MeanReversionSignal.SELL
            else:
                signal_type = MeanReversionSignal.NEUTRAL

            # Classify volatility regime
            iv_pct = latest['iv_percentile']
            vol_regime = self.vol_ind.classify_volatility_regime(iv_pct)

            # Build reasoning
            reasoning = self._build_reasoning(latest)

            return RenaissanceSignal(
                timestamp=datetime.now(timezone.utc),
                signal_type=signal_type,
                confidence=float(latest['confidence']),
                zscore=float(latest['zscore']),
                iv_percentile=float(iv_pct),
                bb_percent_b=float(latest['bb_percent_b']),
                volatility_regime=vol_regime,
                reasoning=reasoning,
                mean_rev_component=float(latest['mean_rev_signal']),
                vol_component=float(latest['vol_signal']),
                bb_component=float(latest['bb_signal'])
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'get_current_signal'})
            return None

    def _build_reasoning(self, latest: pd.Series) -> str:
        """Build human-readable reasoning for the signal."""
        reasons = []

        zscore = latest['zscore']
        if zscore > ZSCORE_OVERBOUGHT:
            reasons.append(f"Z-score {zscore:.2f} indicates overbought condition")
        elif zscore < ZSCORE_OVERSOLD:
            reasons.append(f"Z-score {zscore:.2f} indicates oversold condition")

        iv_pct = latest['iv_percentile']
        if iv_pct > IV_HIGH_PERCENTILE:
            reasons.append(f"IV percentile {iv_pct:.1f}% is elevated (favor selling premium)")
        elif iv_pct < IV_LOW_PERCENTILE:
            reasons.append(f"IV percentile {iv_pct:.1f}% is low (favor buying premium)")

        bb_pct = latest['bb_percent_b']
        if bb_pct > 1:
            reasons.append(f"Price above upper Bollinger Band (%B={bb_pct:.2f})")
        elif bb_pct < 0:
            reasons.append(f"Price below lower Bollinger Band (%B={bb_pct:.2f})")

        return "; ".join(reasons) if reasons else "No strong signals detected"


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_renaissance_signal_generator(confidence_threshold: float = 0.5) -> RenaissanceStyleSignalGenerator:  # noqa: E501
    """
    Factory function to create a Renaissance-style signal generator.

    Args:
        confidence_threshold: Minimum confidence for generating signals

    Returns:
        Configured RenaissanceStyleSignalGenerator instance
    """
    return RenaissanceStyleSignalGenerator(confidence_threshold=confidence_threshold)


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Generate sample data
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=252, freq='D')

    # Simulate SPY price data with mean-reverting behavior
    price = 450
    prices = [price]
    for _ in range(251):
        # Mean-reverting random walk
        change = np.random.randn() * 2 + (450 - price) * 0.05
        price += change
        prices.append(price)

    data = pd.DataFrame({
        'close': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'volume': np.random.randint(50000000, 100000000, 252),
        'implied_vol': np.random.uniform(0.15, 0.35, 252)
    }, index=dates)


    # Test indicators

    mean_rev = MeanReversionIndicators()
    vol_ind = VolatilityIndicators()

    # Z-score
    zscore = mean_rev.calculate_zscore(data['close'])

    # Bollinger Bands
    bb = mean_rev.bollinger_bands(data['close'])

    # IV Percentile
    iv_pct = vol_ind.iv_percentile(data['implied_vol'])

    # Historical Volatility
    hist_vol = vol_ind.historical_volatility(data['close'])

    # Generate signals

    signal_gen = create_renaissance_signal_generator(confidence_threshold=0.5)
    signals = signal_gen.generate_signals(data)


    # Count signals
    buy_signals = (signals['final_signal'] == 1).sum()
    sell_signals = (signals['final_signal'] == -1).sum()
    neutral = (signals['final_signal'] == 0).sum()


    # Get current signal
    current_signal = signal_gen.get_current_signal(data)
    if current_signal:
        pass

