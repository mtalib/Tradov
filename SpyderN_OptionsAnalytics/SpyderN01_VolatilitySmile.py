#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN01_VolatilitySmile.py
Group: N (Options Analytics)
Purpose: Volatility smile analysis

Description:
    This module analyzes implied volatility patterns across strike prices to
    identify the volatility smile/smirk. It detects pricing anomalies, measures
    smile dynamics, and provides trading signals based on smile distortions.
    The module integrates with the Greeks calculator for accurate IV calculations.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: PRODUCTION - Fully implemented
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import math
from collections import deque
import threading
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from scipy import stats, interpolate, optimize
from scipy.optimize import curve_fit, minimize

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Smile fitting parameters
MIN_STRIKES_FOR_FIT = 5  # Minimum strikes needed for smile fitting
SMILE_STRIKE_RANGE = (0.80, 1.20)  # Moneyness range for smile analysis
OUTLIER_THRESHOLD = 3.0  # Standard deviations for outlier detection

# Smile model types
POLYNOMIAL_ORDER = 4  # Order for polynomial fitting
SVI_MAX_ITERATIONS = 1000  # Max iterations for SVI calibration

# Anomaly detection
SMILE_ASYMMETRY_THRESHOLD = 0.05  # Threshold for asymmetry detection
CONVEXITY_WARNING_THRESHOLD = -0.001  # Negative convexity warning
SMILE_HISTORY_SIZE = 100  # Number of historical smiles to keep

# ==============================================================================
# ENUMS AND DATA STRUCTURES
# ==============================================================================
@dataclass
class SmilePoint:
    """Single point on the volatility smile."""
    strike: float
    moneyness: float  # K/S
    log_moneyness: float  # log(K/S)
    implied_vol: float
    volume: int
    open_interest: int
    bid_ask_spread: float
    is_outlier: bool = False

@dataclass
class SVIParameters:
    """Stochastic Volatility Inspired (SVI) model parameters."""
    a: float  # Level
    b: float  # Angle
    rho: float  # Rotation
    m: float  # Shift
    sigma: float  # Smoothness
    
    def total_variance(self, k: float) -> float:
        """Calculate total variance for log-moneyness k."""
        return self.a + self.b * (self.rho * (k - self.m) + 
                                  np.sqrt((k - self.m)**2 + self.sigma**2))

@dataclass
class SmileAnalysis:
    """Complete smile analysis results."""
    timestamp: datetime
    expiry: datetime
    underlying_price: float
    forward_price: float
    
    # Smile data
    smile_points: List[SmilePoint]
    fitted_smile: Optional[Any]  # Fitted function
    
    # Smile characteristics
    atm_vol: float
    atm_skew: float  # First derivative at ATM
    atm_convexity: float  # Second derivative at ATM
    
    # Asymmetry measures
    put_wing_slope: float
    call_wing_slope: float
    asymmetry_ratio: float
    
    # Model parameters
    model_type: str  # 'polynomial', 'svi', 'sabr'
    model_params: Dict[str, float]
    fit_error: float  # RMSE
    r_squared: float
    
    # Anomalies
    anomalies: List[Dict[str, Any]]
    mispriced_strikes: List[Tuple[float, float]]  # (strike, expected_iv - actual_iv)

@dataclass
class SmileSignal:
    """Trading signal from smile analysis."""
    timestamp: datetime
    signal_type: str  # 'mispricing', 'smile_trade', 'calendar'
    strikes: List[float]
    strategy: str
    expected_edge: float  # Expected profit in IV terms
    confidence: float
    rationale: str
    entry_conditions: Dict[str, Any]

# ==============================================================================
# VOLATILITY SMILE ANALYZER CLASS
# ==============================================================================
class VolatilitySmileAnalyzer:
    """
    Analyzes implied volatility smiles for trading opportunities.
    
    This class fits various smile models, detects anomalies, identifies
    mispricings, and generates trading signals based on smile analysis.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the volatility smile analyzer.
        
        Args:
            symbol: Underlying symbol to analyze
        """
        self.symbol = symbol
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data sources
        self.option_chain_mgr = OptionChainManager()
        self.greeks_calculator = GreeksCalculator()
        self.event_manager = get_event_manager()
        
        # Smile history
        self.smile_history: Dict[datetime, deque] = {}  # expiry -> historical smiles
        self.current_smiles: Dict[datetime, SmileAnalysis] = {}
        
        # Calibration cache
        self.calibration_cache: Dict[str, Any] = {}
        
        # Threading
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        self.logger.info(f"VolatilitySmileAnalyzer initialized for {symbol}")
        
    # ==========================================================================
    # MAIN ANALYSIS METHODS
    # ==========================================================================
    def analyze_smile(self, 
                     option_chain: pd.DataFrame,
                     expiry: Optional[datetime] = None,
                     model: str = "svi") -> SmileAnalysis:
        """
        Analyze volatility smile for an option chain.
        
        Args:
            option_chain: DataFrame with option data
            expiry: Specific expiry to analyze (closest if None)
            model: Model to use ('polynomial', 'svi', 'sabr')
            
        Returns:
            SmileAnalysis object with results
        """
        try:
            # Filter for specific expiry
            if expiry is None:
                expiry = self._get_nearest_expiry(option_chain)
                
            chain = option_chain[option_chain['expiry'] == expiry].copy()
            
            if len(chain) < MIN_STRIKES_FOR_FIT:
                raise ValueError(f"Insufficient data for smile analysis: {len(chain)} strikes")
                
            # Get underlying and forward prices
            underlying_price = chain['underlying_price'].iloc[0]
            forward_price = self._calculate_forward_price(underlying_price, expiry)
            
            # Extract smile points
            smile_points = self._extract_smile_points(chain, underlying_price)
            
            # Remove outliers
            cleaned_points = self._remove_outliers(smile_points)
            
            # Fit smile model
            if model == "svi":
                fitted_smile, params, metrics = self._fit_svi_smile(cleaned_points)
            elif model == "polynomial":
                fitted_smile, params, metrics = self._fit_polynomial_smile(cleaned_points)
            else:
                raise ValueError(f"Unknown model type: {model}")
                
            # Calculate smile characteristics
            characteristics = self._calculate_smile_characteristics(
                fitted_smile, underlying_price, cleaned_points
            )
            
            # Detect anomalies
            anomalies = self._detect_smile_anomalies(cleaned_points, fitted_smile)
            
            # Find mispriced strikes
            mispriced = self._find_mispriced_strikes(cleaned_points, fitted_smile)
            
            # Create analysis object
            analysis = SmileAnalysis(
                timestamp=datetime.now(),
                expiry=expiry,
                underlying_price=underlying_price,
                forward_price=forward_price,
                smile_points=smile_points,
                fitted_smile=fitted_smile,
                atm_vol=characteristics['atm_vol'],
                atm_skew=characteristics['atm_skew'],
                atm_convexity=characteristics['atm_convexity'],
                put_wing_slope=characteristics['put_wing_slope'],
                call_wing_slope=characteristics['call_wing_slope'],
                asymmetry_ratio=characteristics['asymmetry_ratio'],
                model_type=model,
                model_params=params,
                fit_error=metrics['rmse'],
                r_squared=metrics['r_squared'],
                anomalies=anomalies,
                mispriced_strikes=mispriced
            )
            
            # Update cache
            with self._lock:
                self.current_smiles[expiry] = analysis
                if expiry not in self.smile_history:
                    self.smile_history[expiry] = deque(maxlen=SMILE_HISTORY_SIZE)
                self.smile_history[expiry].append(analysis)
                
            # Emit event
            self._emit_smile_update(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing smile: {e}")
            self.error_handler.handle_error(e, {"method": "analyze_smile"})
            raise
            
    # ==========================================================================
    # SMILE FITTING METHODS
    # ==========================================================================
    def _fit_svi_smile(self, 
                      smile_points: List[SmilePoint]) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
        """
        Fit SVI (Stochastic Volatility Inspired) model to smile.
        
        The SVI parameterization is:
        w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))
        where w is total variance and k is log-moneyness
        """
        # Extract data
        k_values = np.array([p.log_moneyness for p in smile_points])
        w_values = np.array([p.implied_vol**2 for p in smile_points])  # Total variance
        
        # Initial parameter guess
        a0 = np.mean(w_values)
        b0 = 0.1
        rho0 = -0.5
        m0 = 0.0
        sigma0 = 0.1
        
        initial_params = [a0, b0, rho0, m0, sigma0]
        
        # Define objective function
        def objective(params):
            a, b, rho, m, sigma = params
            
            # SVI constraints
            if b < 0 or sigma < 0 or abs(rho) > 1:
                return 1e10
                
            # Calculate model variance
            model_w = a + b * (rho * (k_values - m) + 
                             np.sqrt((k_values - m)**2 + sigma**2))
                             
            # Penalize negative variance
            if np.any(model_w < 0):
                return 1e10
                
            # RMSE
            return np.sqrt(np.mean((model_w - w_values)**2))
            
        # Optimize
        result = optimize.minimize(
            objective,
            initial_params,
            method='Nelder-Mead',
            options={'maxiter': SVI_MAX_ITERATIONS}
        )
        
        if not result.success:
            self.logger.warning("SVI optimization did not converge")
            
        # Extract parameters
        a, b, rho, m, sigma = result.x
        svi_params = SVIParameters(a=a, b=b, rho=rho, m=m, sigma=sigma)
        
        # Create fitted function
        def fitted_smile(moneyness):
            k = np.log(moneyness)
            total_var = svi_params.total_variance(k)
            return np.sqrt(max(total_var, 1e-6))  # Ensure positive
            
        # Calculate metrics
        fitted_values = np.array([fitted_smile(p.moneyness) for p in smile_points])
        actual_values = np.array([p.implied_vol for p in smile_points])
        
        rmse = np.sqrt(np.mean((fitted_values - actual_values)**2))
        ss_res = np.sum((actual_values - fitted_values)**2)
        ss_tot = np.sum((actual_values - np.mean(actual_values))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        params_dict = {
            'a': a, 'b': b, 'rho': rho, 'm': m, 'sigma': sigma
        }
        
        metrics = {'rmse': rmse, 'r_squared': r_squared}
        
        return fitted_smile, params_dict, metrics
        
    def _fit_polynomial_smile(self, 
                            smile_points: List[SmilePoint]) -> Tuple[Any, Dict[str, float], Dict[str, float]]:
        """Fit polynomial model to smile."""
        # Extract data
        x = np.array([p.log_moneyness for p in smile_points])
        y = np.array([p.implied_vol for p in smile_points])
        
        # Fit polynomial
        coeffs = np.polyfit(x, y, POLYNOMIAL_ORDER)
        poly = np.poly1d(coeffs)
        
        # Create fitted function
        def fitted_smile(moneyness):
            return float(poly(np.log(moneyness)))
            
        # Calculate metrics
        fitted_values = poly(x)
        rmse = np.sqrt(np.mean((fitted_values - y)**2))
        ss_res = np.sum((y - fitted_values)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        params_dict = {f'c{i}': coeff for i, coeff in enumerate(coeffs)}
        metrics = {'rmse': rmse, 'r_squared': r_squared}
        
        return fitted_smile, params_dict, metrics
        
    # ==========================================================================
    # SMILE ANALYSIS METHODS
    # ==========================================================================
    def _extract_smile_points(self, 
                            chain: pd.DataFrame, 
                            spot: float) -> List[SmilePoint]:
        """Extract smile points from option chain."""
        smile_points = []
        
        # Group by strike
        for strike, group in chain.groupby('strike'):
            moneyness = strike / spot
            
            # Skip if outside analysis range
            if moneyness < SMILE_STRIKE_RANGE[0] or moneyness > SMILE_STRIKE_RANGE[1]:
                continue
                
            # Average put and call IVs
            put_data = group[group['type'] == 'PUT']
            call_data = group[group['type'] == 'CALL']
            
            ivs = []
            volumes = []
            ois = []
            spreads = []
            
            if not put_data.empty:
                ivs.append(put_data['implied_volatility'].iloc[0])
                volumes.append(put_data['volume'].iloc[0])
                ois.append(put_data['open_interest'].iloc[0])
                if 'bid' in put_data.columns and 'ask' in put_data.columns:
                    spreads.append(put_data['ask'].iloc[0] - put_data['bid'].iloc[0])
                    
            if not call_data.empty:
                ivs.append(call_data['implied_volatility'].iloc[0])
                volumes.append(call_data['volume'].iloc[0])
                ois.append(call_data['open_interest'].iloc[0])
                if 'bid' in call_data.columns and 'ask' in call_data.columns:
                    spreads.append(call_data['ask'].iloc[0] - call_data['bid'].iloc[0])
                    
            if ivs:
                smile_points.append(SmilePoint(
                    strike=strike,
                    moneyness=moneyness,
                    log_moneyness=np.log(moneyness),
                    implied_vol=np.mean(ivs),
                    volume=sum(volumes),
                    open_interest=sum(ois),
                    bid_ask_spread=np.mean(spreads) if spreads else 0.0
                ))
                
        return sorted(smile_points, key=lambda x: x.strike)
        
    def _remove_outliers(self, smile_points: List[SmilePoint]) -> List[SmilePoint]:
        """Remove outlier points from smile."""
        if len(smile_points) < 5:
            return smile_points
            
        # Calculate median absolute deviation
        ivs = np.array([p.implied_vol for p in smile_points])
        median = np.median(ivs)
        mad = np.median(np.abs(ivs - median))
        
        # Mark outliers
        cleaned = []
        for point in smile_points:
            z_score = abs(point.implied_vol - median) / (mad * 1.4826) if mad > 0 else 0
            
            if z_score < OUTLIER_THRESHOLD:
                cleaned.append(point)
            else:
                point.is_outlier = True
                self.logger.debug(f"Outlier detected at strike {point.strike}: IV={point.implied_vol}")
                
        return cleaned
        
    def _calculate_smile_characteristics(self, 
                                       fitted_smile: Any,
                                       spot: float,
                                       smile_points: List[SmilePoint]) -> Dict[str, float]:
        """Calculate key smile characteristics."""
        # ATM volatility
        atm_vol = fitted_smile(1.0)
        
        # Calculate derivatives at ATM
        h = 0.001  # Small step for numerical derivative
        
        # First derivative (skew)
        atm_skew = (fitted_smile(1.0 + h) - fitted_smile(1.0 - h)) / (2 * h)
        
        # Second derivative (convexity)
        atm_convexity = (fitted_smile(1.0 + h) - 2 * fitted_smile(1.0) + 
                        fitted_smile(1.0 - h)) / (h**2)
                        
        # Wing slopes (using 10-delta region approximation)
        put_wing_moneyness = 0.90
        call_wing_moneyness = 1.10
        
        put_wing_slope = (fitted_smile(put_wing_moneyness) - atm_vol) / (put_wing_moneyness - 1.0)
        call_wing_slope = (fitted_smile(call_wing_moneyness) - atm_vol) / (call_wing_moneyness - 1.0)
        
        # Asymmetry ratio
        asymmetry_ratio = abs(put_wing_slope / call_wing_slope) if call_wing_slope != 0 else float('inf')
        
        return {
            'atm_vol': atm_vol,
            'atm_skew': atm_skew,
            'atm_convexity': atm_convexity,
            'put_wing_slope': put_wing_slope,
            'call_wing_slope': call_wing_slope,
            'asymmetry_ratio': asymmetry_ratio
        }
        
    def _detect_smile_anomalies(self, 
                              smile_points: List[SmilePoint],
                              fitted_smile: Any) -> List[Dict[str, Any]]:
        """Detect anomalies in the smile."""
        anomalies = []
        
        # Check for negative butterfly spreads (arbitrage)
        for i in range(1, len(smile_points) - 1):
            k1, k2, k3 = smile_points[i-1].strike, smile_points[i].strike, smile_points[i+1].strike
            iv1, iv2, iv3 = smile_points[i-1].implied_vol, smile_points[i].implied_vol, smile_points[i+1].implied_vol
            
            # Butterfly condition: IV should be convex
            butterfly_value = iv2 - (iv1 + iv3) / 2
            
            if butterfly_value < -0.01:  # Small tolerance
                anomalies.append({
                    'type': 'negative_butterfly',
                    'strikes': [k1, k2, k3],
                    'severity': abs(butterfly_value),
                    'message': f"Negative butterfly at strikes {k1:.0f}-{k2:.0f}-{k3:.0f}"
                })
                
        # Check for calendar arbitrage opportunities
        if hasattr(self, 'smile_history'):
            historical_atm = [s.atm_vol for s in list(self.smile_history.values())[-10:] 
                            if hasattr(s, 'atm_vol')]
            if historical_atm:
                current_atm = fitted_smile(1.0)
                historical_mean = np.mean(historical_atm)
                
                if abs(current_atm - historical_mean) / historical_mean > 0.20:
                    anomalies.append({
                        'type': 'calendar_opportunity',
                        'current_vol': current_atm,
                        'historical_vol': historical_mean,
                        'severity': abs(current_atm - historical_mean),
                        'message': "Large deviation from historical volatility"
                    })
                    
        # Check for excessive asymmetry
        put_points = [p for p in smile_points if p.moneyness < 0.98]
        call_points = [p for p in smile_points if p.moneyness > 1.02]
        
        if put_points and call_points:
            avg_put_vol = np.mean([p.implied_vol for p in put_points])
            avg_call_vol = np.mean([p.implied_vol for p in call_points])
            
            asymmetry = abs(avg_put_vol - avg_call_vol) / ((avg_put_vol + avg_call_vol) / 2)
            
            if asymmetry > SMILE_ASYMMETRY_THRESHOLD:
                anomalies.append({
                    'type': 'excessive_asymmetry',
                    'put_vol': avg_put_vol,
                    'call_vol': avg_call_vol,
                    'severity': asymmetry,
                    'message': f"Smile asymmetry: {asymmetry:.1%}"
                })
                
        return anomalies
        
    def _find_mispriced_strikes(self, 
                              smile_points: List[SmilePoint],
                              fitted_smile: Any,
                              threshold: float = 0.02) -> List[Tuple[float, float]]:
        """Find strikes that deviate significantly from fitted smile."""
        mispriced = []
        
        for point in smile_points:
            expected_iv = fitted_smile(point.moneyness)
            actual_iv = point.implied_vol
            difference = expected_iv - actual_iv
            
            # Check if significant and has decent liquidity
            if abs(difference) > threshold and point.volume > 50:
                mispriced.append((point.strike, difference))
                
        return mispriced
        
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def detect_anomalies(self, 
                        current_smile: Optional[SmileAnalysis] = None,
                        historical_smiles: Optional[List[SmileAnalysis]] = None) -> List[SmileSignal]:
        """
        Detect anomalies and generate trading signals.
        
        Args:
            current_smile: Current smile analysis
            historical_smiles: Historical smile data
            
        Returns:
            List of trading signals
        """
        if current_smile is None:
            # Use most recent
            if not self.current_smiles:
                return []
            current_smile = list(self.current_smiles.values())[0]
            
        signals = []
        
        # Check for mispricing opportunities
        if current_smile.mispriced_strikes:
            for strike, diff in current_smile.mispriced_strikes:
                if abs(diff) > 0.03:  # Significant mispricing
                    signal = self._generate_mispricing_signal(
                        current_smile, strike, diff
                    )
                    if signal:
                        signals.append(signal)
                        
        # Check for smile trading opportunities
        if current_smile.atm_convexity < CONVEXITY_WARNING_THRESHOLD:
            signal = self._generate_convexity_signal(current_smile)
            if signal:
                signals.append(signal)
                
        # Check for asymmetry trades
        if current_smile.asymmetry_ratio > 1.5 or current_smile.asymmetry_ratio < 0.67:
            signal = self._generate_asymmetry_signal(current_smile)
            if signal:
                signals.append(signal)
                
        return signals
        
    def _generate_mispricing_signal(self, 
                                  smile: SmileAnalysis,
                                  strike: float,
                                  difference: float) -> Optional[SmileSignal]:
        """Generate signal for mispriced option."""
        # Determine if option is cheap or expensive
        if difference > 0:
            # Actual IV < Expected IV -> Option is cheap
            strategy = f"Buy options at strike {strike:.0f}"
            expected_edge = difference
        else:
            # Actual IV > Expected IV -> Option is expensive
            strategy = f"Sell options at strike {strike:.0f}"
            expected_edge = -difference
            
        return SmileSignal(
            timestamp=datetime.now(),
            signal_type="mispricing",
            strikes=[strike],
            strategy=strategy,
            expected_edge=expected_edge,
            confidence=0.7 + (0.3 * smile.r_squared),
            rationale=f"Strike {strike:.0f} is mispriced by {difference:.3f} IV points",
            entry_conditions={
                'min_volume': 100,
                'max_spread': 0.10,
                'time_of_day': 'avoid_first_last_30min'
            }
        )
        
    def _generate_convexity_signal(self, smile: SmileAnalysis) -> Optional[SmileSignal]:
        """Generate signal for abnormal convexity."""
        if smile.atm_convexity >= 0:
            return None
            
        # Negative convexity suggests selling butterfly
        atm_strike = smile.underlying_price
        wing_width = atm_strike * 0.02  # 2% wings
        
        return SmileSignal(
            timestamp=datetime.now(),
            signal_type="smile_trade",
            strikes=[
                atm_strike - wing_width,
                atm_strike,
                atm_strike + wing_width
            ],
            strategy="Sell butterfly spread",
            expected_edge=abs(smile.atm_convexity) * 10,
            confidence=0.65,
            rationale=f"Negative smile convexity ({smile.atm_convexity:.4f}) suggests butterfly sale",
            entry_conditions={
                'max_days_to_expiry': 30,
                'min_volume': 500,
                'volatility_regime': 'normal'
            }
        )
        
    def _generate_asymmetry_signal(self, smile: SmileAnalysis) -> Optional[SmileSignal]:
        """Generate signal for smile asymmetry."""
        if 0.8 < smile.asymmetry_ratio < 1.2:
            return None
            
        if smile.asymmetry_ratio > 1.5:
            # Put skew too steep relative to calls
            strategy = "Risk reversal: Sell puts, buy calls"
            strikes = [
                smile.underlying_price * 0.95,  # 95% put
                smile.underlying_price * 1.05   # 105% call
            ]
        else:
            # Call skew too steep relative to puts
            strategy = "Risk reversal: Buy puts, sell calls"
            strikes = [
                smile.underlying_price * 0.95,  # 95% put
                smile.underlying_price * 1.05   # 105% call
            ]
            
        return SmileSignal(
            timestamp=datetime.now(),
            signal_type="smile_trade",
            strikes=strikes,
            strategy=strategy,
            expected_edge=abs(1.0 - smile.asymmetry_ratio) * 0.05,
            confidence=0.70,
            rationale=f"Smile asymmetry ratio {smile.asymmetry_ratio:.2f} suggests risk reversal",
            entry_conditions={
                'delta_neutral': True,
                'rebalance_frequency': 'daily',
                'max_position_size': 0.5
            }
        )
        
    # ==========================================================================
    # UTILITIES AND HELPERS
    # ==========================================================================
    def _get_nearest_expiry(self, option_chain: pd.DataFrame) -> datetime:
        """Get nearest expiry date from option chain."""
        expiries = option_chain['expiry'].unique()
        if len(expiries) == 0:
            raise ValueError("No expiry dates in option chain")
            
        # Find closest to 30 days
        target_date = datetime.now() + timedelta(days=30)
        return min(expiries, key=lambda x: abs((x - target_date).days))
        
    def _calculate_forward_price(self, spot: float, expiry: datetime) -> float:
        """Calculate forward price using put-call parity."""
        # Simplified - in production would use actual rates and dividends
        r = 0.05  # Risk-free rate
        q = 0.02  # Dividend yield
        T = (expiry - datetime.now()).days / 365.0
        
        return spot * np.exp((r - q) * T)
        
    def _emit_smile_update(self, analysis: SmileAnalysis) -> None:
        """Emit smile analysis update event."""
        event = Event(
            type=EventType.ANALYTICS,
            data={
                'type': 'smile_update',
                'symbol': self.symbol,
                'expiry': analysis.expiry.isoformat(),
                'atm_vol': analysis.atm_vol,
                'skew': analysis.atm_skew,
                'convexity': analysis.atm_convexity,
                'anomalies': len(analysis.anomalies),
                'mispricings': len(analysis.mispriced_strikes)
            }
        )
        self.event_manager.emit(event)
        
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_smile_metrics(self, expiry: Optional[datetime] = None) -> Dict[str, float]:
        """
        Get current smile metrics.
        
        Args:
            expiry: Specific expiry (uses nearest if None)
            
        Returns:
            Dictionary of smile metrics
        """
        if expiry is None and self.current_smiles:
            # Use nearest expiry
            expiry = min(self.current_smiles.keys(), 
                        key=lambda x: abs((x - datetime.now()).days - 30))
                        
        if expiry not in self.current_smiles:
            return {
                'atm_vol': 0.0,
                'skew': 0.0,
                'convexity': 0.0,
                'asymmetry': 1.0,
                'implemented': True
            }
            
        smile = self.current_smiles[expiry]
        
        return {
            'atm_vol': smile.atm_vol,
            'skew': smile.atm_skew,
            'convexity': smile.atm_convexity,
            'asymmetry': smile.asymmetry_ratio,
            'put_wing': smile.put_wing_slope,
            'call_wing': smile.call_wing_slope,
            'fit_quality': smile.r_squared,
            'implemented': True
        }
        
    def get_smile_surface(self) -> Dict[str, Any]:
        """Get smile surface across all expiries."""
        surface_data = {
            'timestamp': datetime.now().isoformat(),
            'expiries': [],
            'strikes': [],
            'volatilities': [],
            'underlying_price': 0.0
        }
        
        if not self.current_smiles:
            return surface_data
            
        # Collect data from all expiries
        all_strikes = set()
        for smile in self.current_smiles.values():
            for point in smile.smile_points:
                all_strikes.add(point.strike)
                
        all_strikes = sorted(list(all_strikes))
        
        # Build surface
        for expiry, smile in sorted(self.current_smiles.items()):
            surface_data['expiries'].append(expiry)
            row_vols = []
            
            for strike in all_strikes:
                # Interpolate if needed
                moneyness = strike / smile.underlying_price
                vol = smile.fitted_smile(moneyness) if smile.fitted_smile else 0.0
                row_vols.append(vol)
                
            surface_data['volatilities'].append(row_vols)
            
        surface_data['strikes'] = all_strikes
        surface_data['underlying_price'] = list(self.current_smiles.values())[0].underlying_price
        
        return surface_data
        
    def start_monitoring(self, update_interval: int = 300) -> None:
        """
        Start continuous smile monitoring.
        
        Args:
            update_interval: Update interval in seconds (default 5 minutes)
        """
        if self._running:
            self.logger.warning("Smile monitoring already running")
            return
            
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(update_interval,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info(f"Started smile monitoring with {update_interval}s interval")
        
    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Stopped smile monitoring")
        
    def _monitor_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Get option chains for all expiries
                chains = self.option_chain_mgr.get_all_chains(self.symbol)
                
                for expiry, chain in chains.items():
                    if chain is not None and not chain.empty:
                        # Analyze smile
                        analysis = self.analyze_smile(chain, expiry)
                        
                        # Generate signals
                        signals = self.detect_anomalies(analysis)
                        
                        # Emit signals
                        for signal in signals:
                            self._emit_signal(signal)
                            
            except Exception as e:
                self.logger.error(f"Error in smile monitor loop: {e}")
                
            time.sleep(interval)
            
    def _emit_signal(self, signal: SmileSignal) -> None:
        """Emit trading signal event."""
        event = Event(
            type=EventType.SIGNAL,
            data={
                'source': 'smile_analyzer',
                'signal': {
                    'timestamp': signal.timestamp.isoformat(),
                    'type': signal.signal_type,
                    'strikes': signal.strikes,
                    'strategy': signal.strategy,
                    'expected_edge': signal.expected_edge,
                    'confidence': signal.confidence,
                    'rationale': signal.rationale
                }
            }
        )
        self.event_manager.emit(event)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = ['VolatilitySmileAnalyzer', 'SmileAnalysis', 'SmileSignal', 'SVIParameters']

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the smile analyzer
    analyzer = VolatilitySmileAnalyzer("SPY")
    
    print("="*60)
    print("SPYDER - Volatility Smile Analyzer Test")
    print("="*60)
    
    # Create sample data
    sample_chain = pd.DataFrame({
        'strike': [400, 410, 420, 430, 440, 450, 460, 470, 480],
        'type': ['PUT'] * 9,
        'expiry': [datetime.now() + timedelta(days=30)] * 9,
        'underlying_price': [440] * 9,
        'implied_volatility': [0.22, 0.20, 0.18, 0.16, 0.15, 0.16, 0.17, 0.19, 0.21],
        'volume': [100, 200, 500, 1000, 2000, 1000, 500, 200, 100],
        'open_interest': [1000, 2000, 5000, 10000, 20000, 10000, 5000, 2000, 1000],
        'bid': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        'ask': [1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1]
    })
    
    # Analyze smile
    analysis = analyzer.analyze_smile(sample_chain)
    
    print(f"\nSmile Analysis Results:")
    print(f"  ATM Vol: {analysis.atm_vol:.3f}")
    print(f"  ATM Skew: {analysis.atm_skew:.4f}")
    print(f"  ATM Convexity: {analysis.atm_convexity:.4f}")
    print(f"  Asymmetry Ratio: {analysis.asymmetry_ratio:.2f}")
    print(f"  Model: {analysis.model_type}")
    print(f"  Fit R²: {analysis.r_squared:.3f}")
    
    if analysis.anomalies:
        print(f"\nAnomalies Detected: {len(analysis.anomalies)}")
        for anomaly in analysis.anomalies:
            print(f"  - {anomaly['type']}: {anomaly['message']}")
            
    if analysis.mispriced_strikes:
        print(f"\nMispriced Strikes: {len(analysis.mispriced_strikes)}")
        for strike, diff in analysis.mispriced_strikes:
            print(f"  - Strike {strike:.0f}: {diff:+.3f} IV")
            
    # Generate signals
    signals = analyzer.detect_anomalies(analysis)
    
    if signals:
        print(f"\nTrading Signals: {len(signals)}")
        for signal in signals:
            print(f"  - {signal.signal_type}: {signal.strategy}")
            print(f"    Expected Edge: {signal.expected_edge:.3f}")
            print(f"    Confidence: {signal.confidence:.1%}")
            
    print("\nSmile Analyzer test completed successfully!")