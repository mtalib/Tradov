"""
Renaissance-Style Indicators for SPY Options Trading
Implements statistical arbitrage and mean reversion indicators inspired by Renaissance Technologies
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, Dict, Optional
import warnings
warnings.filterwarnings('ignore')


class MeanReversionIndicators:
    """
    Statistical mean reversion indicators based on Renaissance Technologies' approach
    """
    
    @staticmethod
    def calculate_zscore(prices: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate Z-score for mean reversion detection
        
        Z-score measures how many standard deviations the current price is from the mean.
        Renaissance uses this to identify statistical anomalies.
        
        Args:
            prices: Series of prices
            window: Lookback window for calculating mean and std
            
        Returns:
            Series of Z-scores
        """
        rolling_mean = prices.rolling(window=window).mean()
        rolling_std = prices.rolling(window=window).std()
        zscore = (prices - rolling_mean) / rolling_std
        return zscore
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, window: int = 20, num_std: float = 2.0) -> Dict[str, pd.Series]:
        """
        Calculate Bollinger Bands for statistical deviation detection
        
        Renaissance uses statistical deviation bands to identify when prices
        move beyond normal ranges (typically 2-3 standard deviations).
        
        Args:
            prices: Series of prices
            window: Lookback window
            num_std: Number of standard deviations for bands
            
        Returns:
            Dictionary with upper, middle, lower bands and bandwidth
        """
        middle_band = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        upper_band = middle_band + (std * num_std)
        lower_band = middle_band - (std * num_std)
        
        # Bandwidth measures volatility - useful for identifying squeeze conditions
        bandwidth = (upper_band - lower_band) / middle_band
        
        # %B indicates where price is relative to bands
        percent_b = (prices - lower_band) / (upper_band - lower_band)
        
        return {
            'upper': upper_band,
            'middle': middle_band,
            'lower': lower_band,
            'bandwidth': bandwidth,
            'percent_b': percent_b
        }
    
    @staticmethod
    def statistical_arbitrage_signal(price1: pd.Series, price2: pd.Series, 
                                     window: int = 60, entry_threshold: float = 2.0,
                                     exit_threshold: float = 0.5) -> pd.DataFrame:
        """
        Generate statistical arbitrage signals between two correlated instruments
        
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
        # Calculate price ratio
        ratio = price1 / price2
        
        # Calculate rolling statistics
        ratio_mean = ratio.rolling(window=window).mean()
        ratio_std = ratio.rolling(window=window).std()
        
        # Calculate Z-score of ratio
        zscore = (ratio - ratio_mean) / ratio_std
        
        # Generate signals
        # Positive Z-score: price1 is relatively expensive, short price1/long price2
        # Negative Z-score: price1 is relatively cheap, long price1/short price2
        signals = pd.DataFrame(index=price1.index)
        signals['ratio'] = ratio
        signals['zscore'] = zscore
        signals['signal'] = 0
        
        # Entry signals
        signals.loc[zscore > entry_threshold, 'signal'] = -1  # Short the spread
        signals.loc[zscore < -entry_threshold, 'signal'] = 1   # Long the spread
        
        # Exit signals (mean reversion occurred)
        signals.loc[abs(zscore) < exit_threshold, 'signal'] = 0
        
        return signals


class VolatilityIndicators:
    """
    Volatility-based indicators for options trading
    """
    
    @staticmethod
    def historical_volatility(prices: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate historical volatility (annualized)
        
        Args:
            prices: Series of prices
            window: Lookback window
            
        Returns:
            Series of annualized volatility
        """
        log_returns = np.log(prices / prices.shift(1))
        volatility = log_returns.rolling(window=window).std() * np.sqrt(252)
        return volatility
    
    @staticmethod
    def iv_percentile(implied_vol: pd.Series, window: int = 252) -> pd.Series:
        """
        Calculate implied volatility percentile for mean reversion
        
        High IV percentile suggests volatility may revert lower (sell premium)
        Low IV percentile suggests volatility may expand (buy premium)
        
        Args:
            implied_vol: Series of implied volatility values
            window: Lookback window (252 = 1 year of trading days)
            
        Returns:
            Series of IV percentile (0-100)
        """
        def percentile_rank(series):
            if len(series) < 2:
                return np.nan
            return stats.percentileofscore(series[:-1], series.iloc[-1])
        
        iv_pct = implied_vol.rolling(window=window).apply(percentile_rank, raw=False)
        return iv_pct
    
    @staticmethod
    def volatility_zscore(implied_vol: pd.Series, window: int = 60) -> pd.Series:
        """
        Calculate Z-score of implied volatility for mean reversion trading
        
        Args:
            implied_vol: Series of implied volatility
            window: Lookback window
            
        Returns:
            Series of volatility Z-scores
        """
        iv_mean = implied_vol.rolling(window=window).mean()
        iv_std = implied_vol.rolling(window=window).std()
        iv_zscore = (implied_vol - iv_mean) / iv_std
        return iv_zscore


class OptionsGreeksIndicators:
    """
    Options Greeks-based indicators for systematic trading
    """
    
    @staticmethod
    def gamma_exposure_imbalance(strikes: np.ndarray, gamma_profile: np.ndarray,
                                  open_interest: np.ndarray, current_price: float) -> float:
        """
        Calculate market-wide gamma exposure imbalance
        
        Large gamma imbalances can predict price movements as dealers hedge.
        
        Args:
            strikes: Array of strike prices
            gamma_profile: Array of gamma values at each strike
            open_interest: Array of open interest at each strike
            current_price: Current underlying price
            
        Returns:
            Net gamma exposure (positive = dealers long gamma, negative = dealers short gamma)
        """
        # Weight gamma by open interest and distance from current price
        weighted_gamma = gamma_profile * open_interest
        
        # Separate calls and puts (typically puts have negative gamma for dealers)
        net_gamma = np.sum(weighted_gamma)
        
        return net_gamma
    
    @staticmethod
    def theta_decay_signal(days_to_expiry: int, theta: float) -> float:
        """
        Generate signal based on theta decay acceleration
        
        Theta decay accelerates in the final weeks before expiration.
        
        Args:
            days_to_expiry: Days until option expiration
            theta: Current theta value
            
        Returns:
            Theta decay score (higher = more attractive for premium selling)
        """
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


class MarketMicrostructureIndicators:
    """
    Market microstructure indicators for high-frequency trading
    """
    
    @staticmethod
    def bid_ask_spread_analysis(bid: pd.Series, ask: pd.Series, 
                                 mid_price: pd.Series) -> Dict[str, pd.Series]:
        """
        Analyze bid-ask spread for liquidity and execution quality
        
        Renaissance optimizes transaction costs by analyzing spread patterns.
        
        Args:
            bid: Series of bid prices
            ask: Series of ask prices
            mid_price: Series of mid prices
            
        Returns:
            Dictionary with spread metrics
        """
        spread = ask - bid
        spread_pct = spread / mid_price
        
        # Rolling average spread (lower = better liquidity)
        avg_spread = spread_pct.rolling(window=20).mean()
        
        # Spread volatility (higher = less stable liquidity)
        spread_vol = spread_pct.rolling(window=20).std()
        
        return {
            'spread': spread,
            'spread_pct': spread_pct,
            'avg_spread': avg_spread,
            'spread_volatility': spread_vol
        }
    
    @staticmethod
    def order_flow_imbalance(buy_volume: pd.Series, sell_volume: pd.Series,
                             window: int = 20) -> pd.Series:
        """
        Calculate order flow imbalance
        
        Persistent imbalances can predict short-term price movements.
        
        Args:
            buy_volume: Series of buy-side volume
            sell_volume: Series of sell-side volume
            window: Smoothing window
            
        Returns:
            Series of order flow imbalance (-1 to 1)
        """
        total_volume = buy_volume + sell_volume
        imbalance = (buy_volume - sell_volume) / total_volume
        
        # Smooth the imbalance
        smoothed_imbalance = imbalance.rolling(window=window).mean()
        
        return smoothed_imbalance


class RenaissanceStyleSignalGenerator:
    """
    Combines multiple indicators to generate Renaissance-style trading signals
    """
    
    def __init__(self, confidence_threshold: float = 0.6):
        """
        Args:
            confidence_threshold: Minimum confidence score to generate signal (0-1)
        """
        self.confidence_threshold = confidence_threshold
        self.mean_rev = MeanReversionIndicators()
        self.vol_ind = VolatilityIndicators()
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate composite trading signals from multiple indicators
        
        Args:
            data: DataFrame with columns: 'close', 'high', 'low', 'volume', 'implied_vol'
            
        Returns:
            DataFrame with signals and confidence scores
        """
        signals = pd.DataFrame(index=data.index)
        
        # Calculate Z-score for mean reversion
        zscore = self.mean_rev.calculate_zscore(data['close'], window=20)
        
        # Calculate Bollinger Bands
        bb = self.mean_rev.bollinger_bands(data['close'], window=20, num_std=2.0)
        
        # Calculate IV percentile
        if 'implied_vol' in data.columns:
            iv_pct = self.vol_ind.iv_percentile(data['implied_vol'], window=252)
            iv_zscore = self.vol_ind.volatility_zscore(data['implied_vol'], window=60)
        else:
            iv_pct = pd.Series(50, index=data.index)  # Neutral if no IV data
            iv_zscore = pd.Series(0, index=data.index)
        
        # Generate composite signal
        # Mean reversion signal: extreme Z-scores suggest reversal
        mean_rev_signal = np.where(zscore > 2, -1,  # Overbought, expect reversion down
                                   np.where(zscore < -2, 1, 0))  # Oversold, expect reversion up
        
        # Volatility signal: high IV suggests selling premium, low IV suggests buying
        vol_signal = np.where(iv_pct > 75, -1,  # High IV, sell premium
                             np.where(iv_pct < 25, 1, 0))  # Low IV, buy premium
        
        # Bollinger Band signal
        bb_signal = np.where(bb['percent_b'] > 1, -1,  # Above upper band
                            np.where(bb['percent_b'] < 0, 1, 0))  # Below lower band
        
        # Combine signals with weights
        composite_signal = (mean_rev_signal * 0.4 + 
                           vol_signal * 0.3 + 
                           bb_signal * 0.3)
        
        # Calculate confidence based on signal strength
        confidence = abs(composite_signal)
        
        # Final signal (only when confidence exceeds threshold)
        final_signal = np.where(confidence >= self.confidence_threshold,
                               np.sign(composite_signal), 0)
        
        signals['zscore'] = zscore
        signals['iv_percentile'] = iv_pct
        signals['iv_zscore'] = iv_zscore
        signals['bb_percent_b'] = bb['percent_b']
        signals['mean_rev_signal'] = mean_rev_signal
        signals['vol_signal'] = vol_signal
        signals['bb_signal'] = bb_signal
        signals['composite_signal'] = composite_signal
        signals['confidence'] = confidence
        signals['final_signal'] = final_signal
        
        return signals


# Example usage
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
    
    # Generate signals
    signal_gen = RenaissanceStyleSignalGenerator(confidence_threshold=0.6)
    signals = signal_gen.generate_signals(data)
    
    # Display results
    print("Renaissance-Style Trading Signals for SPY Options")
    print("=" * 60)
    print(f"\nLast 10 days:")
    print(signals[['zscore', 'iv_percentile', 'confidence', 'final_signal']].tail(10))
    
    # Count signals
    buy_signals = (signals['final_signal'] == 1).sum()
    sell_signals = (signals['final_signal'] == -1).sum()
    neutral = (signals['final_signal'] == 0).sum()
    
    print(f"\nSignal Distribution:")
    print(f"Buy Signals: {buy_signals}")
    print(f"Sell Signals: {sell_signals}")
    print(f"Neutral: {neutral}")
    print(f"Win Rate Target: ~50.75% (Renaissance style)")
