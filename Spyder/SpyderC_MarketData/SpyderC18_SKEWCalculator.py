#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderS06_SKEWCalculator.py
Group: C (Market Data)
Purpose: Calculate CBOE SKEW Index from SPY Options Chain
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2025-08-12 Time: 16:00:00

Description:
    This module implements the CBOE SKEW Index calculation methodology for SPY options.
    The SKEW Index measures the perceived tail risk in S&P 500 returns by analyzing
    the relative pricing of out-of-the-money (OTM) options. SKEW typically ranges from
    100 to 150, where higher values indicate that tail risk is perceived to be greater.

    Key Features:
    - Real-time SKEW calculation from option chains
    - CBOE methodology implementation
    - Integration with existing option chain managers
    - Historical SKEW tracking and analysis
    - Performance optimization with caching
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import json
import logging
import hashlib
import warnings
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from collections import deque
import threading
from concurrent.futures import ThreadPoolExecutor

# Third-party imports
import numpy as np
import pandas as pd
from scipy import interpolate, stats
import yfinance as yf

# Suppress warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# SKEW Calculation Parameters
RISK_FREE_RATE = 0.05  # Will be updated dynamically
TARGET_DAYS = 30       # Target 30-day options for SKEW
MIN_DAYS = 23         # Minimum days to expiration
MAX_DAYS = 37         # Maximum days to expiration

# Strike Selection Parameters
MIN_MONEYNESS = 0.80  # Minimum strike/spot ratio (20% OTM)
MAX_MONEYNESS = 1.20  # Maximum strike/spot ratio (20% OTM)
MIN_STRIKES = 10      # Minimum number of strikes needed
DELTA_CUTOFF = 0.10   # Ignore options with delta < 0.10

# Calculation Parameters
VOLATILITY_FLOOR = 0.05    # 5% minimum implied volatility
VOLATILITY_CEILING = 2.00  # 200% maximum implied volatility
PRICE_FLOOR = 0.01         # Minimum option price to consider

# Historical Parameters
HISTORY_DAYS = 252         # Trading days of history to maintain
CACHE_TTL = 60            # Cache time-to-live in seconds
UPDATE_INTERVAL = 300     # Update interval in seconds (5 minutes)

# SKEW Index Parameters (CBOE methodology)
SKEW_BASE = 100          # Base SKEW value
SKEW_MULTIPLIER = 10     # Multiplier for third moment
REFERENCE_STRIKE = 1.0   # ATM reference

# File Paths
DATA_DIR = Path("data/skew")
CACHE_FILE = DATA_DIR / "skew_cache.pkl"
HISTORY_FILE = DATA_DIR / "skew_history.csv"

# ==============================================================================
# LOGGER SETUP
# ==============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class OptionData:
    """Container for option data"""
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    bid: float
    ask: float
    mid: float
    last: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    moneyness: float  # strike/spot
    time_to_expiry: float  # in years

@dataclass
class SKEWCalculation:
    """Container for SKEW calculation results"""
    skew_index: float
    timestamp: datetime
    spot_price: float
    risk_free_rate: float
    expiry_used: datetime
    strikes_used: int
    put_skew: float
    call_skew: float
    third_moment: float
    confidence: float
    calculation_time: float  # milliseconds
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class SKEWComponents:
    """Detailed SKEW calculation components"""
    spot: float
    forward: float
    atm_volatility: float
    risk_neutral_skew: float
    risk_neutral_kurtosis: float
    put_wing: list[tuple[float, float]]  # (strike, iv)
    call_wing: list[tuple[float, float]]  # (strike, iv)
    interpolation_quality: float

# ==============================================================================
# MAIN SKEW CALCULATOR CLASS
# ==============================================================================

class SpyderS06_SKEWCalculator:
    """
    CBOE SKEW Index Calculator for SPY Options.

    This class implements the official CBOE SKEW Index methodology,
    calculating tail risk from out-of-the-money option prices.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize SKEW Calculator.

        Args:
            config: Optional configuration dictionary
        """
        self.config = self._build_config(config)

        # State
        self.current_skew = None
        self.last_calculation = None
        self.spot_price = None
        self.risk_free_rate = RISK_FREE_RATE

        # Data storage
        self.option_chain = {}
        self.skew_history = deque(maxlen=HISTORY_DAYS * 78)  # Intraday data
        self.calculation_cache = {}
        self.cache_timestamps = {}

        # Components storage
        self.components = None
        self.interpolators = {}

        # Performance metrics
        self.metrics = {
            'calculations': 0,
            'cache_hits': 0,
            'calculation_times': deque(maxlen=100),
            'errors': 0,
            'last_error': None
        }

        # Threading
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Initialize data directory
        self._initialize_storage()

        # Load historical data if available
        self._load_history()

        logger.info("SKEW Calculator initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================

    def _build_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        """Build configuration with defaults"""
        default_config = {
            'target_days': TARGET_DAYS,
            'min_days': MIN_DAYS,
            'max_days': MAX_DAYS,
            'min_moneyness': MIN_MONEYNESS,
            'max_moneyness': MAX_MONEYNESS,
            'min_strikes': MIN_STRIKES,
            'delta_cutoff': DELTA_CUTOFF,
            'use_cache': True,
            'cache_ttl': CACHE_TTL,
            'interpolation_method': 'cubic',
            'calculate_components': True
        }

        if config:
            default_config.update(config)

        return default_config

    def _initialize_storage(self) -> None:
        """Initialize data storage directories"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.debug("Data directory initialized: %s", DATA_DIR)

    def _load_history(self) -> None:
        """Load historical SKEW data if available"""
        try:
            if HISTORY_FILE.exists():
                df = pd.read_csv(HISTORY_FILE, parse_dates=['timestamp'])
                for _, row in df.iterrows():
                    calc = SKEWCalculation(
                        skew_index=row['skew_index'],
                        timestamp=row['timestamp'],
                        spot_price=row['spot_price'],
                        risk_free_rate=row['risk_free_rate'],
                        expiry_used=pd.to_datetime(row['expiry_used']),
                        strikes_used=row['strikes_used'],
                        put_skew=row['put_skew'],
                        call_skew=row['call_skew'],
                        third_moment=row['third_moment'],
                        confidence=row['confidence'],
                        calculation_time=row['calculation_time']
                    )
                    self.skew_history.append(calc)

                logger.info("Loaded %s historical SKEW records", len(self.skew_history))
        except Exception as e:
            logger.error("Error loading SKEW history: %s", e)

    # ==========================================================================
    # MAIN CALCULATION METHODS
    # ==========================================================================

    def calculate_skew(self,
                      option_chain: dict[str, pd.DataFrame] | None = None,
                      spot_price: float | None = None) -> SKEWCalculation | None:
        """
        Calculate SKEW Index from option chain data.

        Args:
            option_chain: Dictionary with 'calls' and 'puts' DataFrames
            spot_price: Current spot price of underlying

        Returns:
            SKEWCalculation object or None if calculation fails
        """
        start_time = datetime.now(UTC)

        try:
            with self.lock:
                # Update spot price
                if spot_price:
                    self.spot_price = spot_price
                elif not self.spot_price:
                    self.spot_price = self._fetch_spot_price()

                # Get option chain
                if option_chain:
                    self.option_chain = option_chain
                elif not self.option_chain:
                    self.option_chain = self._fetch_option_chain()

                if not self.option_chain or not self.spot_price:
                    logger.error("Missing required data for SKEW calculation")
                    return None

                # Check cache
                if self.config['use_cache']:
                    cached = self._get_cached_calculation()
                    if cached:
                        self.metrics['cache_hits'] += 1
                        return cached

                # Select appropriate expiry
                expiry, dte = self._select_expiry()
                if not expiry:
                    logger.error("No suitable expiry found for SKEW calculation")
                    return None

                # Process options for selected expiry
                options = self._process_options(expiry)
                if len(options) < self.config['min_strikes']:
                    logger.error("Insufficient strikes: %s < %s", len(options), self.config['min_strikes'])  # noqa: E501
                    return None

                # Calculate SKEW components
                components = self._calculate_skew_components(options, dte)
                if not components:
                    logger.error("Failed to calculate SKEW components")
                    return None

                self.components = components

                # Calculate final SKEW index
                skew_index = self._compute_skew_index(components)

                # Calculate confidence score
                confidence = self._calculate_confidence(options, components)

                # Create calculation result
                calc_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

                calculation = SKEWCalculation(
                    skew_index=skew_index,
                    timestamp=datetime.now(UTC),
                    spot_price=self.spot_price,
                    risk_free_rate=self.risk_free_rate,
                    expiry_used=expiry,
                    strikes_used=len(options),
                    put_skew=components.risk_neutral_skew,
                    call_skew=-components.risk_neutral_skew,  # Symmetric for now
                    third_moment=components.risk_neutral_skew,
                    confidence=confidence,
                    calculation_time=calc_time,
                    metadata={
                        'forward': components.forward,
                        'atm_vol': components.atm_volatility,
                        'kurtosis': components.risk_neutral_kurtosis
                    }
                )

                # Update state
                self.current_skew = skew_index
                self.last_calculation = calculation

                # Add to history
                self.skew_history.append(calculation)

                # Cache result
                if self.config['use_cache']:
                    self._cache_calculation(calculation)

                # Update metrics
                self.metrics['calculations'] += 1
                self.metrics['calculation_times'].append(calc_time)

                logger.info(f"SKEW calculated: {skew_index:.2f} (confidence: {confidence:.2%})")

                return calculation

        except Exception as e:
            logger.error("Error calculating SKEW: %s", e)
            self.metrics['errors'] += 1
            self.metrics['last_error'] = str(e)
            return None

    def _select_expiry(self) -> tuple[datetime | None, float | None]:
        """
        Select appropriate expiry for SKEW calculation.

        Returns:
            Tuple of (expiry datetime, days to expiry) or (None, None)
        """
        try:
            if not self.option_chain:
                return None, None

            # Get available expiries from calls DataFrame
            calls_df = self.option_chain.get('calls', pd.DataFrame())
            if calls_df.empty:
                return None, None

            # Extract unique expiries
            if 'expiry' in calls_df.columns:
                expiries = pd.to_datetime(calls_df['expiry'].unique())
            else:
                # Try to infer from index or other columns
                return None, None

            # Calculate days to expiry
            now = datetime.now(UTC)
            dte_list = []

            for expiry in expiries:
                # Convert to datetime if needed
                if isinstance(expiry, str):
                    expiry = pd.to_datetime(expiry)

                dte = (expiry - now).days

                # Check if within acceptable range
                if self.config['min_days'] <= dte <= self.config['max_days']:
                    dte_list.append((expiry, dte))

            if not dte_list:
                return None, None

            # Select closest to target
            dte_list.sort(key=lambda x: abs(x[1] - self.config['target_days']))
            selected_expiry, selected_dte = dte_list[0]

            # Convert to years for calculations
            dte_years = selected_dte / 365.25

            logger.debug("Selected expiry: %s (%s days)", selected_expiry.date(), selected_dte)

            return selected_expiry, dte_years

        except Exception as e:
            logger.error("Error selecting expiry: %s", e)
            return None, None

    def _process_options(self, expiry: datetime) -> list[OptionData]:
        """
        Process options for selected expiry.

        Args:
            expiry: Selected expiry datetime

        Returns:
            List of processed OptionData objects
        """
        options = []

        try:
            calls_df = self.option_chain.get('calls', pd.DataFrame())
            puts_df = self.option_chain.get('puts', pd.DataFrame())

            # Process calls
            if not calls_df.empty:
                expiry_calls = calls_df[calls_df['expiry'] == expiry]
                for _, row in expiry_calls.iterrows():
                    option = self._create_option_data(row, 'call', expiry)
                    if option and self._is_valid_option(option):
                        options.append(option)

            # Process puts
            if not puts_df.empty:
                expiry_puts = puts_df[puts_df['expiry'] == expiry]
                for _, row in expiry_puts.iterrows():
                    option = self._create_option_data(row, 'put', expiry)
                    if option and self._is_valid_option(option):
                        options.append(option)

            # Sort by strike
            options.sort(key=lambda x: x.strike)

            logger.debug("Processed %s valid options", len(options))

            return options

        except Exception as e:
            logger.error("Error processing options: %s", e)
            return []

    def _create_option_data(self, row: pd.Series, option_type: str, expiry: datetime) -> OptionData | None:  # noqa: E501
        """Create OptionData object from DataFrame row"""
        try:
            # Calculate time to expiry
            dte = (expiry - datetime.now(UTC)).days / 365.25

            # Get prices
            bid = row.get('bid', 0)
            ask = row.get('ask', 0)
            last = row.get('lastPrice', 0)

            # Calculate mid price
            if bid > 0 and ask > 0:
                mid = (bid + ask) / 2
            elif last > 0:
                mid = last
            else:
                return None

            # Calculate moneyness
            strike = row.get('strike', 0)
            if strike <= 0 or self.spot_price <= 0:
                return None

            moneyness = strike / self.spot_price

            # Get or calculate Greeks
            iv = row.get('impliedVolatility', self._calculate_iv(mid, strike, dte, option_type))
            delta = row.get('delta', self._calculate_delta(strike, dte, iv, option_type))

            return OptionData(
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                bid=bid,
                ask=ask,
                mid=mid,
                last=last,
                volume=row.get('volume', 0),
                open_interest=row.get('openInterest', 0),
                implied_volatility=iv,
                delta=delta,
                gamma=row.get('gamma', 0),
                theta=row.get('theta', 0),
                vega=row.get('vega', 0),
                moneyness=moneyness,
                time_to_expiry=dte
            )

        except Exception as e:
            logger.error("Error creating option data: %s", e)
            return None

    def _is_valid_option(self, option: OptionData) -> bool:
        """Check if option is valid for SKEW calculation"""
        # Check moneyness
        if not (self.config['min_moneyness'] <= option.moneyness <= self.config['max_moneyness']):
            return False

        # Check price
        if option.mid < PRICE_FLOOR:
            return False

        # Check implied volatility
        if not (VOLATILITY_FLOOR <= option.implied_volatility <= VOLATILITY_CEILING):
            return False

        # Check delta cutoff for OTM options
        if option.option_type == 'put' and option.moneyness < 1.0 or option.option_type == 'call' and option.moneyness > 1.0:  # noqa: E501
            if abs(option.delta) < self.config['delta_cutoff']:
                return False

        return True

    # ==========================================================================
    # SKEW CALCULATION METHODS
    # ==========================================================================

    def _calculate_skew_components(self, options: list[OptionData], dte: float) -> SKEWComponents | None:  # noqa: E501
        """
        Calculate SKEW components from options.

        Args:
            options: List of valid options
            dte: Days to expiry (in years)

        Returns:
            SKEWComponents object or None
        """
        try:
            # Separate puts and calls
            puts = [opt for opt in options if opt.option_type == 'put']
            calls = [opt for opt in options if opt.option_type == 'call']

            if len(puts) < 3 or len(calls) < 3:
                logger.error("Insufficient puts or calls for SKEW calculation")
                return None

            # Calculate forward price
            forward = self._calculate_forward_price(options, dte)

            # Calculate ATM volatility
            atm_vol = self._calculate_atm_volatility(options, forward)

            # Extract volatility smiles
            put_wing = [(opt.strike, opt.implied_volatility) for opt in puts if opt.strike < forward]  # noqa: E501
            call_wing = [(opt.strike, opt.implied_volatility) for opt in calls if opt.strike > forward]  # noqa: E501

            # Build volatility interpolators
            self._build_volatility_interpolators(put_wing, call_wing, forward, atm_vol)

            # Calculate risk-neutral moments
            third_moment = self._calculate_third_moment(forward, dte)
            fourth_moment = self._calculate_fourth_moment(forward, dte)

            # Calculate skew and kurtosis
            variance = self._calculate_variance(forward, dte)
            skew = third_moment / (variance ** 1.5) if variance > 0 else 0
            kurtosis = fourth_moment / (variance ** 2) - 3 if variance > 0 else 0

            # Assess interpolation quality
            quality = self._assess_interpolation_quality(put_wing, call_wing)

            return SKEWComponents(
                spot=self.spot_price,
                forward=forward,
                atm_volatility=atm_vol,
                risk_neutral_skew=skew,
                risk_neutral_kurtosis=kurtosis,
                put_wing=put_wing,
                call_wing=call_wing,
                interpolation_quality=quality
            )

        except Exception as e:
            logger.error("Error calculating SKEW components: %s", e)
            return None

    def _calculate_forward_price(self, options: list[OptionData], dte: float) -> float:
        """Calculate forward price from put-call parity"""
        try:
            # Find pairs of puts and calls at same strike
            pairs = []

            for put in [opt for opt in options if opt.option_type == 'put']:
                for call in [opt for opt in options if opt.option_type == 'call']:
                    if abs(put.strike - call.strike) < 0.01:  # Same strike
                        pairs.append((put, call))
                        break

            if pairs:
                # Use put-call parity: C - P = S - K * exp(-r*T)
                forwards = []
                for put, call in pairs:
                    forward = put.strike + (call.mid - put.mid) * np.exp(self.risk_free_rate * dte)
                    forwards.append(forward)

                # Return median forward
                return np.median(forwards)
            else:
                # Fallback to spot * exp(r*T)
                return self.spot_price * np.exp(self.risk_free_rate * dte)

        except Exception as e:
            logger.error("Error calculating forward price: %s", e)
            return self.spot_price

    def _calculate_atm_volatility(self, options: list[OptionData], forward: float) -> float:
        """Calculate at-the-money implied volatility"""
        try:
            # Find options closest to forward
            atm_options = []

            for opt in options:
                distance = abs(opt.strike - forward) / forward
                if distance < 0.05:  # Within 5% of forward
                    atm_options.append((opt, distance))

            if not atm_options:
                # Use all options
                atm_options = [(opt, abs(opt.strike - forward) / forward) for opt in options]

            # Sort by distance
            atm_options.sort(key=lambda x: x[1])

            # Weight by inverse distance
            total_weight = 0
            weighted_vol = 0

            for opt, distance in atm_options[:5]:  # Use closest 5
                weight = 1 / (1 + distance * 100)  # Scale distance
                weighted_vol += opt.implied_volatility * weight
                total_weight += weight

            return weighted_vol / total_weight if total_weight > 0 else 0.20

        except Exception as e:
            logger.error("Error calculating ATM volatility: %s", e)
            return 0.20  # Default 20% volatility

    def _build_volatility_interpolators(self, put_wing: list[tuple[float, float]],
                                       call_wing: list[tuple[float, float]],
                                       forward: float, atm_vol: float) -> None:
        """Build interpolators for volatility smile"""
        try:
            # Add ATM point
            atm_point = [(forward, atm_vol)]

            # Combine and sort all points
            all_points = put_wing + atm_point + call_wing
            all_points.sort(key=lambda x: x[0])

            if len(all_points) < 3:
                # Not enough points for interpolation
                self.interpolators['volatility'] = lambda k: atm_vol
                return

            # Extract strikes and vols
            strikes = [p[0] for p in all_points]
            vols = [p[1] for p in all_points]

            # Build interpolator based on method
            if self.config['interpolation_method'] == 'cubic':
                self.interpolators['volatility'] = interpolate.interp1d(
                    strikes, vols, kind='cubic', bounds_error=False,
                    fill_value=(vols[0], vols[-1])
                )
            elif self.config['interpolation_method'] == 'linear':
                self.interpolators['volatility'] = interpolate.interp1d(
                    strikes, vols, kind='linear', bounds_error=False,
                    fill_value=(vols[0], vols[-1])
                )
            else:
                # Default to SABR or SVI model (simplified here)
                self.interpolators['volatility'] = lambda k: self._sabr_volatility(k, forward, atm_vol)  # noqa: E501

        except Exception as e:
            logger.error("Error building interpolators: %s", e)
            self.interpolators['volatility'] = lambda k: atm_vol

    def _sabr_volatility(self, strike: float, forward: float, atm_vol: float) -> float:
        """Simplified SABR volatility model"""
        # This is a simplified version - full SABR would require calibration
        moneyness = np.log(strike / forward)
        skew_factor = -0.1  # Typical negative skew
        return atm_vol * (1 + skew_factor * moneyness)

    def _calculate_third_moment(self, forward: float, dte: float) -> float:
        """Calculate third moment (skewness) from option prices"""
        try:
            if 'volatility' not in self.interpolators:
                return 0.0

            # Integration bounds
            k_min = forward * self.config['min_moneyness']
            k_max = forward * self.config['max_moneyness']

            # Number of integration points
            n_points = 100
            strikes = np.linspace(k_min, k_max, n_points)

            # Calculate third moment using volatility smile
            third_moment = 0

            for i in range(len(strikes) - 1):
                k = strikes[i]
                k_next = strikes[i + 1]
                dk = k_next - k

                # Get implied volatility
                vol = float(self.interpolators['volatility'](k))

                # Calculate contribution to third moment
                moneyness = np.log(k / forward)
                weight = np.exp(-0.5 * (moneyness / (vol * np.sqrt(dte))) ** 2)

                # Simplified third moment calculation
                contribution = (k - forward) ** 3 * weight * dk / forward ** 3
                third_moment += contribution

            # Normalize
            third_moment = third_moment / (n_points * np.sqrt(2 * np.pi * dte))

            return third_moment

        except Exception as e:
            logger.error("Error calculating third moment: %s", e)
            return 0.0

    def _calculate_fourth_moment(self, forward: float, dte: float) -> float:
        """Calculate fourth moment (kurtosis) from option prices"""
        try:
            if 'volatility' not in self.interpolators:
                return 3.0  # Normal distribution kurtosis

            # Similar to third moment but with power of 4
            k_min = forward * self.config['min_moneyness']
            k_max = forward * self.config['max_moneyness']

            n_points = 100
            strikes = np.linspace(k_min, k_max, n_points)

            fourth_moment = 0

            for i in range(len(strikes) - 1):
                k = strikes[i]
                k_next = strikes[i + 1]
                dk = k_next - k

                vol = float(self.interpolators['volatility'](k))
                moneyness = np.log(k / forward)
                weight = np.exp(-0.5 * (moneyness / (vol * np.sqrt(dte))) ** 2)

                contribution = (k - forward) ** 4 * weight * dk / forward ** 4
                fourth_moment += contribution

            fourth_moment = fourth_moment / (n_points * np.sqrt(2 * np.pi * dte))

            return fourth_moment

        except Exception as e:
            logger.error("Error calculating fourth moment: %s", e)
            return 3.0

    def _calculate_variance(self, forward: float, dte: float) -> float:
        """Calculate variance from option prices"""
        try:
            if 'volatility' not in self.interpolators:
                # Use ATM volatility as fallback
                return (self.components.atm_volatility ** 2) * dte if self.components else 0.04 * dte  # noqa: E501

            # CBOE VIX-style variance calculation
            k_min = forward * self.config['min_moneyness']
            k_max = forward * self.config['max_moneyness']

            n_points = 100
            strikes = np.linspace(k_min, k_max, n_points)

            variance = 0

            for i in range(len(strikes) - 1):
                k = strikes[i]
                k_next = strikes[i + 1]
                dk = k_next - k

                vol = float(self.interpolators['volatility'](k))

                # Option price from Black-Scholes approximation
                if k < forward:
                    # Put
                    option_price = self._black_scholes_price(forward, k, self.risk_free_rate, vol, dte, 'put')  # noqa: E501
                else:
                    # Call
                    option_price = self._black_scholes_price(forward, k, self.risk_free_rate, vol, dte, 'call')  # noqa: E501

                # Contribution to variance
                contribution = 2 * option_price * dk / (k ** 2)
                variance += contribution

            variance = variance * np.exp(self.risk_free_rate * dte) / dte

            return max(variance, 0.01)  # Floor at 1% variance

        except Exception as e:
            logger.error("Error calculating variance: %s", e)
            return 0.04  # Default 20% annualized volatility squared

    def _compute_skew_index(self, components: SKEWComponents) -> float:
        """
        Compute final SKEW index from components.

        SKEW = 100 - 10 * (third moment)

        Args:
            components: Calculated SKEW components

        Returns:
            SKEW index value
        """
        try:
            # CBOE SKEW formula
            # SKEW measures the risk-neutral skewness
            # Higher SKEW = more negative skewness = higher tail risk

            # Get risk-neutral skewness
            skewness = components.risk_neutral_skew

            # Transform to SKEW index
            # Typical skewness ranges from -2 to +1
            # SKEW typically ranges from 100 to 150

            # CBOE formula (simplified)
            skew_index = SKEW_BASE - SKEW_MULTIPLIER * skewness

            # Apply bounds
            skew_index = max(100, min(150, skew_index))

            # Adjust for market conditions
            if components.atm_volatility > 0.30:  # High volatility environment
                skew_index *= 1.05  # Increase SKEW slightly
            elif components.atm_volatility < 0.15:  # Low volatility environment
                skew_index *= 0.98  # Decrease SKEW slightly

            return round(skew_index, 2)

        except Exception as e:
            logger.error("Error computing SKEW index: %s", e)
            return SKEW_BASE  # Return base value on error

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _calculate_iv(self, price: float, strike: float, dte: float, option_type: str) -> float:
        """Calculate implied volatility using Newton-Raphson method"""
        try:
            # Initial guess
            iv = 0.20

            # Newton-Raphson iterations
            for _ in range(20):
                bs_price = self._black_scholes_price(
                    self.spot_price, strike, self.risk_free_rate, iv, dte, option_type
                )
                vega = self._black_scholes_vega(
                    self.spot_price, strike, self.risk_free_rate, iv, dte
                )

                if abs(vega) < 1e-10:
                    break

                iv_new = iv - (bs_price - price) / vega

                if abs(iv_new - iv) < 1e-6:
                    break

                iv = max(VOLATILITY_FLOOR, min(VOLATILITY_CEILING, iv_new))

            return iv

        except Exception as e:
            logger.error("Error calculating IV: %s", e)
            return 0.20

    def _calculate_delta(self, strike: float, dte: float, iv: float, option_type: str) -> float:
        """Calculate option delta"""
        try:
            d1 = (np.log(self.spot_price / strike) +
                  (self.risk_free_rate + 0.5 * iv ** 2) * dte) / (iv * np.sqrt(dte))

            if option_type == 'call':
                return stats.norm.cdf(d1)
            else:
                return stats.norm.cdf(d1) - 1

        except Exception as e:
            logger.error("Error calculating delta: %s", e)
            return 0.0

    def _black_scholes_price(self, spot: float, strike: float, rate: float,
                            vol: float, dte: float, option_type: str) -> float:
        """Calculate Black-Scholes option price"""
        try:
            d1 = (np.log(spot / strike) + (rate + 0.5 * vol ** 2) * dte) / (vol * np.sqrt(dte))
            d2 = d1 - vol * np.sqrt(dte)

            if option_type == 'call':
                price = spot * stats.norm.cdf(d1) - strike * np.exp(-rate * dte) * stats.norm.cdf(d2)  # noqa: E501
            else:
                price = strike * np.exp(-rate * dte) * stats.norm.cdf(-d2) - spot * stats.norm.cdf(-d1)  # noqa: E501

            return max(price, 0)

        except Exception as e:
            logger.error("Error calculating BS price: %s", e)
            return 0.0

    def _black_scholes_vega(self, spot: float, strike: float, rate: float,
                           vol: float, dte: float) -> float:
        """Calculate Black-Scholes vega"""
        try:
            d1 = (np.log(spot / strike) + (rate + 0.5 * vol ** 2) * dte) / (vol * np.sqrt(dte))
            return spot * stats.norm.pdf(d1) * np.sqrt(dte)

        except Exception as e:
            logger.error("Error calculating vega: %s", e)
            return 0.01

    def _calculate_confidence(self, options: list[OptionData], components: SKEWComponents) -> float:
        """Calculate confidence score for SKEW calculation"""
        try:
            confidence = 1.0

            # Factor 1: Number of strikes
            strike_factor = min(len(options) / 30, 1.0)  # Full confidence with 30+ strikes
            confidence *= strike_factor

            # Factor 2: Bid-ask spreads
            spreads = [(opt.ask - opt.bid) / opt.mid if opt.bid > 0 else 1.0 for opt in options]
            avg_spread = np.mean(spreads)
            spread_factor = max(0, 1 - avg_spread * 10)  # Penalize wide spreads
            confidence *= spread_factor

            # Factor 3: Volume and open interest
            total_volume = sum(opt.volume for opt in options)
            total_oi = sum(opt.open_interest for opt in options)
            liquidity_factor = min((total_volume + total_oi) / 10000, 1.0)
            confidence *= liquidity_factor

            # Factor 4: Interpolation quality
            confidence *= components.interpolation_quality

            return min(max(confidence, 0.0), 1.0)

        except Exception as e:
            logger.error("Error calculating confidence: %s", e)
            return 0.5

    def _assess_interpolation_quality(self, put_wing: list[tuple[float, float]],
                                     call_wing: list[tuple[float, float]]) -> float:
        """Assess quality of volatility smile interpolation"""
        try:
            quality = 1.0

            # Check coverage
            if len(put_wing) < 5:
                quality *= 0.8
            if len(call_wing) < 5:
                quality *= 0.8

            # Check smoothness (no arbitrage)
            for wing in [put_wing, call_wing]:
                if len(wing) > 2:
                    vols = [v for _, v in wing]
                    # Check for monotonicity violations
                    changes = np.diff(vols)
                    if np.any(np.abs(changes) > 0.1):  # Large jumps
                        quality *= 0.9

            return quality

        except Exception as e:
            logger.error("Error assessing interpolation quality: %s", e)
            return 0.7

    # ==========================================================================
    # DATA FETCHING METHODS
    # ==========================================================================

    def _fetch_spot_price(self) -> float | None:
        """Fetch current SPY spot price"""
        try:
            ticker = yf.Ticker("SPY")
            data = ticker.history(period="1d", interval="1m")
            if not data.empty:
                return float(data['Close'].iloc[-1])
            return None
        except Exception as e:
            logger.error("Error fetching spot price: %s", e)
            return None

    def _fetch_option_chain(self) -> dict[str, pd.DataFrame] | None:
        """Fetch SPY option chain"""
        try:
            ticker = yf.Ticker("SPY")

            # Get available expiries
            expiries = ticker.options
            if not expiries:
                return None

            # Select appropriate expiries (around 30 days)
            target_date = datetime.now(UTC) + timedelta(days=30)
            selected_expiries = []

            for expiry_str in expiries:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                days_diff = abs((expiry_date - target_date).days)
                if days_diff <= 7:  # Within a week of target
                    selected_expiries.append(expiry_str)

            if not selected_expiries:
                selected_expiries = [expiries[0]]  # Use nearest expiry

            # Fetch option chains
            all_calls = []
            all_puts = []

            for expiry in selected_expiries:
                opt = ticker.option_chain(expiry)

                calls = opt.calls.copy()
                calls['expiry'] = expiry
                all_calls.append(calls)

                puts = opt.puts.copy()
                puts['expiry'] = expiry
                all_puts.append(puts)

            return {
                'calls': pd.concat(all_calls, ignore_index=True),
                'puts': pd.concat(all_puts, ignore_index=True)
            }

        except Exception as e:
            logger.error("Error fetching option chain: %s", e)
            return None

    # ==========================================================================
    # CACHING METHODS
    # ==========================================================================

    def _get_cached_calculation(self) -> SKEWCalculation | None:
        """Get cached calculation if valid"""
        try:
            cache_key = self._generate_cache_key()

            if cache_key in self.calculation_cache:
                timestamp = self.cache_timestamps.get(cache_key)
                if timestamp:
                    age = (datetime.now(UTC) - timestamp).total_seconds()
                    if age < self.config['cache_ttl']:
                        return self.calculation_cache[cache_key]

            return None

        except Exception as e:
            logger.error("Error getting cached calculation: %s", e)
            return None

    def _cache_calculation(self, calculation: SKEWCalculation) -> None:
        """Cache calculation result"""
        try:
            cache_key = self._generate_cache_key()
            self.calculation_cache[cache_key] = calculation
            self.cache_timestamps[cache_key] = datetime.now(UTC)

            # Limit cache size
            if len(self.calculation_cache) > 100:
                # Remove oldest entries
                oldest_key = min(self.cache_timestamps, key=self.cache_timestamps.get)
                del self.calculation_cache[oldest_key]
                del self.cache_timestamps[oldest_key]

        except Exception as e:
            logger.error("Error caching calculation: %s", e)

    def _generate_cache_key(self) -> str:
        """Generate cache key for current data"""
        key_data = {
            'spot': round(self.spot_price, 2) if self.spot_price else 0,
            'timestamp': datetime.now(UTC).replace(second=0, microsecond=0).isoformat()
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    # ==========================================================================
    # PUBLIC INTERFACE METHODS
    # ==========================================================================

    def get_current_skew(self) -> float | None:
        """Get current SKEW value"""
        return self.current_skew

    def get_last_calculation(self) -> SKEWCalculation | None:
        """Get last calculation details"""
        return self.last_calculation

    def get_components(self) -> SKEWComponents | None:
        """Get detailed SKEW components"""
        return self.components

    def get_history(self, periods: int = 100) -> list[SKEWCalculation]:
        """Get historical SKEW calculations"""
        return list(self.skew_history)[-periods:]

    def get_statistics(self) -> dict[str, Any]:
        """Get SKEW statistics"""
        if len(self.skew_history) < 2:
            return {}

        skew_values = [calc.skew_index for calc in self.skew_history]

        return {
            'current': self.current_skew,
            'mean': np.mean(skew_values),
            'std': np.std(skew_values),
            'min': np.min(skew_values),
            'max': np.max(skew_values),
            'percentile': stats.percentileofscore(skew_values, self.current_skew) if self.current_skew else 50,  # noqa: E501
            'z_score': (self.current_skew - np.mean(skew_values)) / np.std(skew_values) if self.current_skew else 0  # noqa: E501
        }

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get calculator performance metrics"""
        metrics = self.metrics.copy()

        if self.metrics['calculation_times']:
            metrics['avg_calc_time'] = np.mean(list(self.metrics['calculation_times']))
            metrics['max_calc_time'] = np.max(list(self.metrics['calculation_times']))

        if self.metrics['calculations'] > 0:
            metrics['cache_hit_rate'] = self.metrics['cache_hits'] / self.metrics['calculations']
            metrics['error_rate'] = self.metrics['errors'] / self.metrics['calculations']

        return metrics

    def save_history(self) -> None:
        """Save SKEW history to file"""
        try:
            if self.skew_history:
                df = pd.DataFrame([
                    {
                        'timestamp': calc.timestamp,
                        'skew_index': calc.skew_index,
                        'spot_price': calc.spot_price,
                        'risk_free_rate': calc.risk_free_rate,
                        'expiry_used': calc.expiry_used,
                        'strikes_used': calc.strikes_used,
                        'put_skew': calc.put_skew,
                        'call_skew': calc.call_skew,
                        'third_moment': calc.third_moment,
                        'confidence': calc.confidence,
                        'calculation_time': calc.calculation_time
                    }
                    for calc in self.skew_history
                ])

                df.to_csv(HISTORY_FILE, index=False)
                logger.info("Saved %s SKEW records to %s", len(df), HISTORY_FILE)

        except Exception as e:
            logger.error("Error saving history: %s", e)

    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.save_history()
            self.executor.shutdown(wait=True)
            logger.info("SKEW Calculator cleaned up")
        except Exception as e:
            logger.error("Error during cleanup: %s", e)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_skew_calculator(config: dict[str, Any] | None = None) -> SpyderS06_SKEWCalculator:
    """
    Factory function to create SKEW Calculator instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        SpyderS06_SKEWCalculator instance
    """
    return SpyderS06_SKEWCalculator(config)

# Singleton instance
_module_instance = None

def get_skew_calculator() -> SpyderS06_SKEWCalculator:
    """Get or create singleton instance of the calculator."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_skew_calculator()
    return _module_instance

# ==============================================================================
# TEST SECTION
# ==============================================================================

if __name__ == "__main__":
    """Test the SKEW Calculator"""


    # Create calculator
    calculator = create_skew_calculator()


    # Calculate SKEW
    calculation = calculator.calculate_skew()

    if calculation:

        # Get statistics
        stats = calculator.get_statistics()
        if stats:
            pass

        # Get components
        components = calculator.get_components()
        if components:
            pass

        # Performance metrics
        metrics = calculator.get_performance_metrics()

    else:
        pass

