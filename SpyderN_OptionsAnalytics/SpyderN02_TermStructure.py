#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN02_TermStructure.py
Group: N (Options Analytics)
Purpose: Options term structure analysis

Description:
    This module analyzes the term structure of implied volatility across different
    expiration dates. It identifies calendar spread opportunities, monitors volatility
    term dynamics, and detects anomalies in the term structure that may indicate
    trading opportunities or regime changes.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: IMPLEMENTED
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from collections import defaultdict
import warnings
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import interpolate, optimize
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC01_OptionsDataFeed import OptionsDataFeed
from SpyderC_MarketData.SpyderC03_HistoricalDataManager import HistoricalDataManager
from SpyderA_Core.SpyderA03_EventManager import EventManager, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
MIN_DTE = 1  # Minimum days to expiration
MAX_DTE = 365  # Maximum days to expiration
MIN_VOLUME = 50  # Minimum volume for valid quotes
TERM_STRUCTURE_WINDOW = 20  # Days for historical comparison
CALENDAR_SPREAD_MIN_VOL_DIFF = 0.02  # 2% minimum vol difference
CONTANGO_THRESHOLD = 0.01  # 1% slope for contango/backwardation

# Standard expiration buckets (days)
EXPIRATION_BUCKETS = [7, 14, 30, 45, 60, 90, 120, 180, 365]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TermStructurePoint:
    """Single point on the volatility term structure."""
    expiration: date
    dte: int  # Days to expiration
    atm_iv: float  # At-the-money implied volatility
    avg_iv: float  # Average IV across strikes
    volume: int
    open_interest: int
    bid_ask_spread: float
    confidence: float  # Data quality confidence (0-1)
    
@dataclass
class TermStructureAnalysis:
    """Complete term structure analysis results."""
    timestamp: datetime
    points: List[TermStructurePoint]
    slope: float  # Overall slope of term structure
    curvature: float  # Second derivative measure
    contango: bool  # True if upward sloping
    backwardation: bool  # True if downward sloping
    kinks: List[int]  # DTEs where structure has kinks
    smooth_curve: Optional[Any] = None  # Interpolated curve
    r_squared: float = 0.0  # Fit quality
    
@dataclass
class CalendarSpreadOpportunity:
    """Calendar spread trading opportunity."""
    near_expiry: date
    far_expiry: date
    near_dte: int
    far_dte: int
    strike: float
    vol_difference: float
    forward_vol: float
    expected_profit: float
    confidence: float
    entry_conditions: Dict[str, Any]
    
@dataclass
class TermStructureAnomaly:
    """Anomaly in term structure."""
    anomaly_type: str  # 'KINK', 'INVERSION', 'SPIKE', 'EVENT'
    dte_range: Tuple[int, int]
    magnitude: float
    historical_percentile: float
    likely_cause: str
    trading_implications: str

@dataclass
class ForwardVolatility:
    """Forward volatility between two dates."""
    start_date: date
    end_date: date
    start_dte: int
    end_dte: int
    forward_vol: float
    spot_near: float
    spot_far: float
    confidence: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TermStructureAnalyzer:
    """
    Analyzes options term structure for trading opportunities.
    
    This class provides comprehensive term structure analysis including
    curve fitting, anomaly detection, and calendar spread identification.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the term structure analyzer.
        
        Args:
            symbol: Underlying symbol to analyze
        """
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.symbol = symbol
        
        # Data management
        self.data_feed = OptionsDataFeed(symbol)
        self.historical_manager = HistoricalDataManager()
        self.event_manager = EventManager()
        
        # Cache
        self.term_structure_cache: Dict[date, TermStructureAnalysis] = {}
        self.historical_structures: List[TermStructureAnalysis] = []
        
        # Analysis parameters
        self.interpolation_method = 'cubic'  # or 'linear', 'polynomial'
        self.min_points_for_analysis = 4
        
        self.logger.info(f"TermStructureAnalyzer initialized for {symbol}")
        
    # ==========================================================================
    # TERM STRUCTURE ANALYSIS
    # ==========================================================================
    def analyze_term_structure(self, 
                             option_chains: Optional[Dict[date, pd.DataFrame]] = None,
                             use_otm: bool = False) -> TermStructureAnalysis:
        """
        Analyze volatility term structure across expirations.
        
        Args:
            option_chains: Pre-loaded option chains by expiration
            use_otm: Whether to use OTM options for IV calculation
            
        Returns:
            Complete term structure analysis
        """
        try:
            # Get option chains if not provided
            if option_chains is None:
                option_chains = self._load_all_option_chains()
                
            if len(option_chains) < self.min_points_for_analysis:
                self.logger.warning(f"Insufficient expirations: {len(option_chains)}")
                return self._create_empty_analysis()
                
            # Calculate term structure points
            points = []
            spot_price = self._get_spot_price()
            
            for expiry, chain in sorted(option_chains.items()):
                point = self._calculate_term_point(expiry, chain, spot_price, use_otm)
                if point and point.confidence > 0.5:
                    points.append(point)
                    
            if len(points) < self.min_points_for_analysis:
                self.logger.warning("Insufficient valid points after filtering")
                return self._create_empty_analysis()
                
            # Sort by DTE
            points.sort(key=lambda x: x.dte)
            
            # Fit term structure curve
            smooth_curve, r_squared = self._fit_term_curve(points)
            
            # Calculate structure characteristics
            slope = self._calculate_slope(points)
            curvature = self._calculate_curvature(points)
            kinks = self._detect_kinks(points)
            
            # Determine market regime
            contango = slope > CONTANGO_THRESHOLD
            backwardation = slope < -CONTANGO_THRESHOLD
            
            analysis = TermStructureAnalysis(
                timestamp=datetime.now(),
                points=points,
                slope=slope,
                curvature=curvature,
                contango=contango,
                backwardation=backwardation,
                kinks=kinks,
                smooth_curve=smooth_curve,
                r_squared=r_squared
            )
            
            # Cache result
            self.term_structure_cache[date.today()] = analysis
            self.historical_structures.append(analysis)
            
            # Emit event
            self._emit_term_structure_event(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing term structure: {e}")
            return self._create_empty_analysis()
            
    def _calculate_term_point(self, 
                            expiry: date,
                            chain: pd.DataFrame,
                            spot_price: float,
                            use_otm: bool) -> Optional[TermStructurePoint]:
        """
        Calculate single term structure point.
        
        Args:
            expiry: Expiration date
            chain: Option chain DataFrame
            spot_price: Current spot price
            use_otm: Whether to use OTM options
            
        Returns:
            Term structure point or None
        """
        try:
            # Calculate DTE
            dte = (expiry - date.today()).days
            if dte < MIN_DTE or dte > MAX_DTE:
                return None
                
            # Filter for liquid options
            liquid_chain = chain[chain['volume'] >= MIN_VOLUME].copy()
            if liquid_chain.empty:
                return None
                
            # Calculate ATM IV
            atm_strike = self._find_atm_strike(liquid_chain, spot_price)
            atm_iv = self._calculate_atm_iv(liquid_chain, atm_strike)
            
            # Calculate average IV
            if use_otm:
                avg_iv = self._calculate_otm_weighted_iv(liquid_chain, spot_price)
            else:
                avg_iv = self._calculate_weighted_avg_iv(liquid_chain)
                
            # Calculate metrics
            total_volume = liquid_chain['volume'].sum()
            total_oi = liquid_chain['open_interest'].sum()
            avg_spread = liquid_chain['ask'].mean() - liquid_chain['bid'].mean()
            
            # Calculate confidence based on liquidity and spread
            confidence = self._calculate_point_confidence(
                total_volume, total_oi, avg_spread, len(liquid_chain)
            )
            
            return TermStructurePoint(
                expiration=expiry,
                dte=dte,
                atm_iv=atm_iv,
                avg_iv=avg_iv,
                volume=int(total_volume),
                open_interest=int(total_oi),
                bid_ask_spread=avg_spread,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating term point for {expiry}: {e}")
            return None
            
    def _fit_term_curve(self, 
                       points: List[TermStructurePoint]) -> Tuple[Any, float]:
        """
        Fit smooth curve to term structure points.
        
        Args:
            points: List of term structure points
            
        Returns:
            Tuple of (interpolation function, R-squared)
        """
        try:
            # Extract data
            x = np.array([p.dte for p in points])
            y = np.array([p.atm_iv for p in points])
            weights = np.array([p.confidence for p in points])
            
            # Fit based on method
            if self.interpolation_method == 'cubic':
                # Cubic spline with smoothing
                smooth_curve = interpolate.UnivariateSpline(
                    x, y, w=weights, s=0.0001, k=min(3, len(points) - 1)
                )
            elif self.interpolation_method == 'polynomial':
                # Polynomial fit
                degree = min(4, len(points) - 1)
                coeffs = np.polyfit(x, y, degree, w=weights)
                smooth_curve = np.poly1d(coeffs)
            else:
                # Linear interpolation
                smooth_curve = interpolate.interp1d(
                    x, y, kind='linear', fill_value='extrapolate'
                )
                
            # Calculate R-squared
            y_pred = smooth_curve(x)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            return smooth_curve, r_squared
            
        except Exception as e:
            self.logger.error(f"Error fitting term curve: {e}")
            return None, 0.0
            
    # ==========================================================================
    # CALENDAR SPREAD ANALYSIS
    # ==========================================================================
    def find_calendar_spreads(self, 
                            term_structure: Optional[TermStructureAnalysis] = None,
                            min_vol_diff: float = CALENDAR_SPREAD_MIN_VOL_DIFF,
                            min_dte_spread: int = 7) -> List[CalendarSpreadOpportunity]:
        """
        Find calendar spread opportunities.
        
        Args:
            term_structure: Current term structure (uses latest if None)
            min_vol_diff: Minimum volatility difference
            min_dte_spread: Minimum days between expirations
            
        Returns:
            List of calendar spread opportunities
        """
        try:
            # Get term structure
            if term_structure is None:
                term_structure = self.analyze_term_structure()
                
            if len(term_structure.points) < 2:
                return []
                
            opportunities = []
            spot_price = self._get_spot_price()
            
            # Check all expiration pairs
            for i, near_point in enumerate(term_structure.points[:-1]):
                for far_point in term_structure.points[i+1:]:
                    # Check minimum DTE spread
                    if far_point.dte - near_point.dte < min_dte_spread:
                        continue
                        
                    # Calculate volatility difference
                    vol_diff = far_point.atm_iv - near_point.atm_iv
                    
                    # Check for opportunity
                    if abs(vol_diff) >= min_vol_diff:
                        # Calculate forward volatility
                        forward_vol = self.calculate_forward_volatility(
                            near_point.dte, far_point.dte,
                            near_point.atm_iv, far_point.atm_iv
                        )
                        
                        # Estimate profit potential
                        expected_profit = self._estimate_calendar_profit(
                            spot_price, vol_diff, near_point.dte, far_point.dte
                        )
                        
                        # Calculate confidence
                        confidence = (near_point.confidence + far_point.confidence) / 2
                        
                        # Create opportunity
                        opp = CalendarSpreadOpportunity(
                            near_expiry=near_point.expiration,
                            far_expiry=far_point.expiration,
                            near_dte=near_point.dte,
                            far_dte=far_point.dte,
                            strike=spot_price,  # ATM calendar
                            vol_difference=vol_diff,
                            forward_vol=forward_vol,
                            expected_profit=expected_profit,
                            confidence=confidence,
                            entry_conditions={
                                'near_iv': near_point.atm_iv,
                                'far_iv': far_point.atm_iv,
                                'vol_ratio': far_point.atm_iv / near_point.atm_iv,
                                'structure_type': 'CONTANGO' if vol_diff > 0 else 'BACKWARDATION'
                            }
                        )
                        opportunities.append(opp)
                        
            # Sort by expected profit
            opportunities.sort(key=lambda x: x.expected_profit, reverse=True)
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error finding calendar spreads: {e}")
            return []
            
    def calculate_forward_volatility(self, 
                                   near_dte: int, 
                                   far_dte: int,
                                   near_iv: float,
                                   far_iv: float) -> float:
        """
        Calculate forward implied volatility.
        
        Args:
            near_dte: Near term days to expiration
            far_dte: Far term days to expiration
            near_iv: Near term implied volatility
            far_iv: Far term implied volatility
            
        Returns:
            Forward implied volatility
        """
        try:
            # Convert to time fractions
            t1 = near_dte / 365.0
            t2 = far_dte / 365.0
            
            # Calculate variance
            var1 = (near_iv ** 2) * t1
            var2 = (far_iv ** 2) * t2
            
            # Forward variance
            forward_var = (var2 - var1) / (t2 - t1)
            
            # Convert back to volatility
            forward_vol = np.sqrt(max(0, forward_var))
            
            return forward_vol
            
        except Exception as e:
            self.logger.error(f"Error calculating forward volatility: {e}")
            return 0.0
            
    # ==========================================================================
    # ANOMALY DETECTION
    # ==========================================================================
    def detect_term_anomalies(self, 
                            current: Optional[TermStructureAnalysis] = None,
                            lookback_days: int = TERM_STRUCTURE_WINDOW) -> List[TermStructureAnomaly]:
        """
        Detect anomalies in term structure.
        
        Args:
            current: Current term structure
            lookback_days: Days of history to compare
            
        Returns:
            List of detected anomalies
        """
        try:
            # Get current structure
            if current is None:
                current = self.analyze_term_structure()
                
            if len(current.points) < 3:
                return []
                
            anomalies = []
            
            # Get historical structures
            historical = self._get_historical_structures(lookback_days)
            
            # Check for inversions
            inversions = self._detect_inversions(current)
            anomalies.extend(inversions)
            
            # Check for kinks
            kink_anomalies = self._detect_kink_anomalies(current, historical)
            anomalies.extend(kink_anomalies)
            
            # Check for spikes
            spike_anomalies = self._detect_spike_anomalies(current, historical)
            anomalies.extend(spike_anomalies)
            
            # Check for event-driven anomalies
            event_anomalies = self._detect_event_anomalies(current)
            anomalies.extend(event_anomalies)
            
            return anomalies
            
        except Exception as e:
            self.logger.error(f"Error detecting anomalies: {e}")
            return []
            
    def _detect_inversions(self, 
                          structure: TermStructureAnalysis) -> List[TermStructureAnomaly]:
        """Detect term structure inversions."""
        anomalies = []
        
        for i in range(len(structure.points) - 1):
            near = structure.points[i]
            far = structure.points[i + 1]
            
            # Check for inversion (near > far)
            if near.atm_iv > far.atm_iv + 0.01:  # 1% threshold
                magnitude = near.atm_iv - far.atm_iv
                
                anomaly = TermStructureAnomaly(
                    anomaly_type='INVERSION',
                    dte_range=(near.dte, far.dte),
                    magnitude=magnitude,
                    historical_percentile=95.0,  # Would calculate from history
                    likely_cause='Near-term event or supply/demand imbalance',
                    trading_implications='Consider selling near-term, buying far-term'
                )
                anomalies.append(anomaly)
                
        return anomalies
        
    def _detect_kink_anomalies(self,
                              current: TermStructureAnalysis,
                              historical: List[TermStructureAnalysis]) -> List[TermStructureAnomaly]:
        """Detect anomalous kinks in term structure."""
        anomalies = []
        
        if not current.kinks:
            return anomalies
            
        # Compare current kinks to historical norms
        for kink_dte in current.kinks:
            # Find magnitude of kink
            kink_magnitude = self._calculate_kink_magnitude(current, kink_dte)
            
            # Compare to historical
            historical_magnitudes = [
                self._calculate_kink_magnitude(h, kink_dte)
                for h in historical
                if any(abs(p.dte - kink_dte) < 5 for p in h.points)
            ]
            
            if historical_magnitudes:
                percentile = self._calculate_percentile(kink_magnitude, historical_magnitudes)
                
                if percentile > 90:  # Anomalous kink
                    anomaly = TermStructureAnomaly(
                        anomaly_type='KINK',
                        dte_range=(kink_dte - 5, kink_dte + 5),
                        magnitude=kink_magnitude,
                        historical_percentile=percentile,
                        likely_cause='Option flow concentration or event expectation',
                        trading_implications='Potential calendar spread opportunity'
                    )
                    anomalies.append(anomaly)
                    
        return anomalies
        
    def _detect_spike_anomalies(self,
                               current: TermStructureAnalysis,
                               historical: List[TermStructureAnalysis]) -> List[TermStructureAnomaly]:
        """Detect volatility spikes in term structure."""
        anomalies = []
        
        for point in current.points:
            # Get historical IVs for similar DTEs
            historical_ivs = []
            for hist in historical:
                for hp in hist.points:
                    if abs(hp.dte - point.dte) < 5:
                        historical_ivs.append(hp.atm_iv)
                        
            if len(historical_ivs) >= 5:
                mean_iv = np.mean(historical_ivs)
                std_iv = np.std(historical_ivs)
                z_score = (point.atm_iv - mean_iv) / std_iv if std_iv > 0 else 0
                
                if abs(z_score) > 2:  # 2 standard deviations
                    percentile = norm.cdf(z_score) * 100
                    
                    anomaly = TermStructureAnomaly(
                        anomaly_type='SPIKE',
                        dte_range=(point.dte - 2, point.dte + 2),
                        magnitude=z_score,
                        historical_percentile=percentile,
                        likely_cause='Unusual option activity or market stress',
                        trading_implications='Mean reversion opportunity if temporary'
                    )
                    anomalies.append(anomaly)
                    
        return anomalies
        
    def _detect_event_anomalies(self,
                               structure: TermStructureAnalysis) -> List[TermStructureAnomaly]:
        """Detect event-driven anomalies (earnings, FOMC, etc.)."""
        anomalies = []
        
        # Look for local peaks that might indicate events
        for i in range(1, len(structure.points) - 1):
            prev = structure.points[i - 1]
            curr = structure.points[i]
            next = structure.points[i + 1]
            
            # Check for local peak
            if curr.atm_iv > prev.atm_iv + 0.02 and curr.atm_iv > next.atm_iv + 0.02:
                # Likely event-driven
                anomaly = TermStructureAnomaly(
                    anomaly_type='EVENT',
                    dte_range=(curr.dte - 2, curr.dte + 2),
                    magnitude=curr.atm_iv - (prev.atm_iv + next.atm_iv) / 2,
                    historical_percentile=90.0,  # Estimate
                    likely_cause='Earnings, FOMC, or other binary event',
                    trading_implications='Event volatility play or avoidance'
                )
                anomalies.append(anomaly)
                
        return anomalies
        
    # ==========================================================================
    # TRADING SIGNALS
    # ==========================================================================
    def generate_term_signals(self,
                            min_confidence: float = 0.7) -> List[Dict[str, Any]]:
        """
        Generate trading signals from term structure analysis.
        
        Args:
            min_confidence: Minimum confidence for signals
            
        Returns:
            List of trading signals
        """
        try:
            signals = []
            
            # Analyze current structure
            current = self.analyze_term_structure()
            
            # Calendar spread signals
            calendar_opps = self.find_calendar_spreads(current)
            for opp in calendar_opps:
                if opp.confidence >= min_confidence:
                    signal = {
                        'type': 'CALENDAR_SPREAD',
                        'action': 'BUY' if opp.vol_difference > 0 else 'SELL',
                        'near_expiry': opp.near_expiry,
                        'far_expiry': opp.far_expiry,
                        'strike': opp.strike,
                        'expected_profit': opp.expected_profit,
                        'confidence': opp.confidence,
                        'entry_conditions': opp.entry_conditions,
                        'reason': f"Vol difference: {opp.vol_difference:.2%}"
                    }
                    signals.append(signal)
                    
            # Anomaly-based signals
            anomalies = self.detect_term_anomalies(current)
            for anomaly in anomalies:
                if anomaly.historical_percentile > 90:
                    signal = {
                        'type': f'ANOMALY_{anomaly.anomaly_type}',
                        'action': 'MONITOR',
                        'dte_range': anomaly.dte_range,
                        'magnitude': anomaly.magnitude,
                        'confidence': anomaly.historical_percentile / 100,
                        'implications': anomaly.trading_implications,
                        'reason': anomaly.likely_cause
                    }
                    signals.append(signal)
                    
            # Regime-based signals
            if current.contango and current.slope > 0.03:
                signal = {
                    'type': 'REGIME_CONTANGO',
                    'action': 'FAVOR_CALENDAR_LONGS',
                    'slope': current.slope,
                    'confidence': current.r_squared,
                    'reason': 'Strong contango favors selling near-term volatility'
                }
                signals.append(signal)
                
            elif current.backwardation and current.slope < -0.03:
                signal = {
                    'type': 'REGIME_BACKWARDATION',
                    'action': 'FAVOR_NEAR_TERM',
                    'slope': current.slope,
                    'confidence': current.r_squared,
                    'reason': 'Backwardation suggests near-term stress'
                }
                signals.append(signal)
                
            return signals
            
        except Exception as e:
            self.logger.error(f"Error generating term signals: {e}")
            return []
            
    # ==========================================================================
    # VISUALIZATION AND METRICS
    # ==========================================================================
    def get_term_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive term structure metrics.
        
        Returns:
            Dictionary of metrics
        """
        try:
            current = self.analyze_term_structure()
            
            metrics = {
                'timestamp': current.timestamp,
                'num_expirations': len(current.points),
                'slope': current.slope,
                'curvature': current.curvature,
                'regime': 'CONTANGO' if current.contango else 'BACKWARDATION' if current.backwardation else 'FLAT',
                'r_squared': current.r_squared,
                'avg_iv': np.mean([p.atm_iv for p in current.points]),
                'iv_range': (
                    min(p.atm_iv for p in current.points),
                    max(p.atm_iv for p in current.points)
                ),
                'kink_count': len(current.kinks),
                'total_volume': sum(p.volume for p in current.points),
                'avg_confidence': np.mean([p.confidence for p in current.points])
            }
            
            # Add forward volatilities
            if len(current.points) >= 2:
                forwards = []
                for i in range(len(current.points) - 1):
                    fwd = self.calculate_forward_volatility(
                        current.points[i].dte,
                        current.points[i + 1].dte,
                        current.points[i].atm_iv,
                        current.points[i + 1].atm_iv
                    )
                    forwards.append(fwd)
                metrics['forward_vols'] = forwards
                
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting term metrics: {e}")
            return {}
            
    def plot_term_structure(self,
                           save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create term structure visualization data.
        
        Args:
            save_path: Optional path to save plot data
            
        Returns:
            Plot data dictionary
        """
        try:
            current = self.analyze_term_structure()
            
            # Prepare plot data
            plot_data = {
                'dte': [p.dte for p in current.points],
                'atm_iv': [p.atm_iv for p in current.points],
                'avg_iv': [p.avg_iv for p in current.points],
                'confidence': [p.confidence for p in current.points],
                'volume': [p.volume for p in current.points]
            }
            
            # Add smooth curve if available
            if current.smooth_curve:
                smooth_dte = np.linspace(
                    min(plot_data['dte']),
                    max(plot_data['dte']),
                    100
                )
                smooth_iv = current.smooth_curve(smooth_dte)
                plot_data['smooth_dte'] = smooth_dte.tolist()
                plot_data['smooth_iv'] = smooth_iv.tolist()
                
            # Add annotations for anomalies
            anomalies = self.detect_term_anomalies(current)
            plot_data['anomalies'] = [
                {
                    'type': a.anomaly_type,
                    'dte_range': a.dte_range,
                    'magnitude': a.magnitude
                }
                for a in anomalies
            ]
            
            # Save if requested
            if save_path:
                with open(save_path, 'w') as f:
                    json.dump(plot_data, f, indent=2)
                    
            return plot_data
            
        except Exception as e:
            self.logger.error(f"Error creating plot data: {e}")
            return {}
            
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _load_all_option_chains(self) -> Dict[date, pd.DataFrame]:
        """Load option chains for all available expirations."""
        try:
            chains = {}
            expirations = self.data_feed.get_expiration_dates(self.symbol)
            
            for expiry in expirations:
                chain = self.data_feed.get_options_chain(self.symbol, expiry)
                if chain is not None and not chain.empty:
                    chains[expiry] = chain
                    
            return chains
            
        except Exception as e:
            self.logger.error(f"Error loading option chains: {e}")
            return {}
            
    def _get_spot_price(self) -> float:
        """Get current spot price."""
        try:
            return self.data_feed.get_spot_price(self.symbol)
        except:
            return 440.0  # Default SPY price
            
    def _find_atm_strike(self, chain: pd.DataFrame, spot_price: float) -> float:
        """Find at-the-money strike."""
        strikes = chain['strike'].unique()
        return min(strikes, key=lambda x: abs(x - spot_price))
        
    def _calculate_atm_iv(self, chain: pd.DataFrame, atm_strike: float) -> float:
        """Calculate ATM implied volatility."""
        atm_options = chain[chain['strike'] == atm_strike]
        
        if atm_options.empty:
            return 0.0
            
        # Average call and put IV
        call_iv = atm_options[atm_options['type'] == 'CALL']['implied_volatility'].mean()
        put_iv = atm_options[atm_options['type'] == 'PUT']['implied_volatility'].mean()
        
        return (call_iv + put_iv) / 2 if not np.isnan(call_iv) and not np.isnan(put_iv) else 0.0
        
    def _calculate_weighted_avg_iv(self, chain: pd.DataFrame) -> float:
        """Calculate volume-weighted average IV."""
        chain = chain[chain['volume'] > 0].copy()
        
        if chain.empty:
            return 0.0
            
        total_volume = chain['volume'].sum()
        if total_volume == 0:
            return chain['implied_volatility'].mean()
            
        weighted_iv = (chain['implied_volatility'] * chain['volume']).sum() / total_volume
        return weighted_iv
        
    def _calculate_otm_weighted_iv(self, chain: pd.DataFrame, spot_price: float) -> float:
        """Calculate OTM-weighted IV (for VIX-like calculation)."""
        # Use OTM puts below spot and OTM calls above spot
        otm_puts = chain[(chain['type'] == 'PUT') & (chain['strike'] < spot_price)]
        otm_calls = chain[(chain['type'] == 'CALL') & (chain['strike'] > spot_price)]
        
        otm_options = pd.concat([otm_puts, otm_calls])
        
        if otm_options.empty:
            return self._calculate_weighted_avg_iv(chain)
            
        # Weight by 1/K^2 (VIX methodology simplified)
        otm_options['weight'] = 1 / (otm_options['strike'] ** 2)
        total_weight = otm_options['weight'].sum()
        
        if total_weight == 0:
            return otm_options['implied_volatility'].mean()
            
        weighted_iv = (otm_options['implied_volatility'] * otm_options['weight']).sum() / total_weight
        return weighted_iv
        
    def _calculate_point_confidence(self,
                                  volume: int,
                                  open_interest: int,
                                  spread: float,
                                  num_strikes: int) -> float:
        """Calculate confidence score for a term structure point."""
        # Volume component (0-0.4)
        vol_score = min(0.4, volume / 10000 * 0.4)
        
        # OI component (0-0.3)
        oi_score = min(0.3, open_interest / 50000 * 0.3)
        
        # Spread component (0-0.2)
        spread_score = max(0, 0.2 - spread * 2)
        
        # Strike coverage component (0-0.1)
        strike_score = min(0.1, num_strikes / 50 * 0.1)
        
        return vol_score + oi_score + spread_score + strike_score
        
    def _calculate_slope(self, points: List[TermStructurePoint]) -> float:
        """Calculate overall slope of term structure."""
        if len(points) < 2:
            return 0.0
            
        # Use linear regression
        x = np.array([p.dte for p in points])
        y = np.array([p.atm_iv for p in points])
        
        # Normalize by DTE range
        coeffs = np.polyfit(x, y, 1)
        return coeffs[0] * 30  # Slope per 30 days
        
    def _calculate_curvature(self, points: List[TermStructurePoint]) -> float:
        """Calculate curvature (second derivative) of term structure."""
        if len(points) < 3:
            return 0.0
            
        # Fit quadratic and get second derivative
        x = np.array([p.dte for p in points])
        y = np.array([p.atm_iv for p in points])
        
        coeffs = np.polyfit(x, y, 2)
        return coeffs[0] * 2  # Second derivative
        
    def _detect_kinks(self, points: List[TermStructurePoint]) -> List[int]:
        """Detect kinks (sharp changes) in term structure."""
        if len(points) < 3:
            return []
            
        kinks = []
        
        for i in range(1, len(points) - 1):
            # Calculate local slopes
            slope1 = (points[i].atm_iv - points[i-1].atm_iv) / (points[i].dte - points[i-1].dte)
            slope2 = (points[i+1].atm_iv - points[i].atm_iv) / (points[i+1].dte - points[i].dte)
            
            # Check for significant slope change
            slope_change = abs(slope2 - slope1)
            if slope_change > 0.001:  # 0.1% per day threshold
                kinks.append(points[i].dte)
                
        return kinks
        
    def _calculate_kink_magnitude(self,
                                 structure: TermStructureAnalysis,
                                 kink_dte: int) -> float:
        """Calculate magnitude of a kink."""
        # Find points around kink
        points_before = [p for p in structure.points if p.dte < kink_dte]
        points_after = [p for p in structure.points if p.dte > kink_dte]
        
        if not points_before or not points_after:
            return 0.0
            
        # Get closest points
        before = max(points_before, key=lambda p: p.dte)
        after = min(points_after, key=lambda p: p.dte)
        kink_point = next((p for p in structure.points if abs(p.dte - kink_dte) < 3), None)
        
        if not kink_point:
            return 0.0
            
        # Calculate expected IV at kink (linear interpolation)
        expected_iv = before.atm_iv + (after.atm_iv - before.atm_iv) * \
                     (kink_point.dte - before.dte) / (after.dte - before.dte)
                     
        return abs(kink_point.atm_iv - expected_iv)
        
    def _calculate_percentile(self, value: float, historical: List[float]) -> float:
        """Calculate percentile of value in historical distribution."""
        if not historical:
            return 50.0
            
        return (sum(1 for h in historical if h <= value) / len(historical)) * 100
        
    def _estimate_calendar_profit(self,
                                 spot: float,
                                 vol_diff: float,
                                 near_dte: int,
                                 far_dte: int) -> float:
        """Estimate profit potential for calendar spread."""
        # Simplified estimation based on vol difference and time
        time_factor = np.sqrt(far_dte / near_dte)
        vol_factor = abs(vol_diff) * 100  # Convert to percentage points
        
        # Rough estimate: $50 per vol point per contract
        base_profit = vol_factor * 50
        
        # Adjust for time decay benefit
        if vol_diff > 0:  # Selling expensive near-term
            base_profit *= (1 + (time_factor - 1) * 0.5)
        else:  # Selling expensive far-term
            base_profit *= (1 + (1 / time_factor - 1) * 0.3)
            
        return base_profit
        
    def _get_historical_structures(self, days: int) -> List[TermStructureAnalysis]:
        """Get historical term structures."""
        cutoff = datetime.now() - timedelta(days=days)
        return [s for s in self.historical_structures if s.timestamp > cutoff]
        
    def _emit_term_structure_event(self, analysis: TermStructureAnalysis) -> None:
        """Emit term structure analysis event."""
        event = Event(
            'term_structure.analyzed',
            {
                'symbol': self.symbol,
                'timestamp': analysis.timestamp,
                'slope': analysis.slope,
                'regime': 'CONTANGO' if analysis.contango else 'BACKWARDATION' if analysis.backwardation else 'FLAT',
                'num_points': len(analysis.points),
                'r_squared': analysis.r_squared
            }
        )
        self.event_manager.emit(event)
        
    def _create_empty_analysis(self) -> TermStructureAnalysis:
        """Create empty term structure analysis."""
        return TermStructureAnalysis(
            timestamp=datetime.now(),
            points=[],
            slope=0.0,
            curvature=0.0,
            contango=False,
            backwardation=False,
            kinks=[],
            smooth_curve=None,
            r_squared=0.0
        )

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'TermStructureAnalyzer',
    'TermStructurePoint',
    'TermStructureAnalysis',
    'CalendarSpreadOpportunity',
    'TermStructureAnomaly',
    'ForwardVolatility'
]

# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = TermStructureAnalyzer("SPY")
    
    print("=== SPYDER Term Structure Analyzer ===\n")
    
    # Analyze current term structure
    structure = analyzer.analyze_term_structure()
    
    print(f"📊 Term Structure Analysis:")
    print(f"Points: {len(structure.points)}")
    print(f"Slope: {structure.slope:.4f} (per 30 days)")
    print(f"Regime: {'CONTANGO' if structure.contango else 'BACKWARDATION' if structure.backwardation else 'FLAT'}")
    print(f"R-squared: {structure.r_squared:.3f}")
    
    # Show term structure points
    print(f"\n📈 Volatility Term Structure:")
    for point in structure.points[:5]:  # First 5 points
        print(f"  {point.dte}d: {point.atm_iv:.1%} "
              f"(Vol: {point.volume:,}, Conf: {point.confidence:.2f})")
        
    # Find calendar spreads
    calendars = analyzer.find_calendar_spreads(structure)
    if calendars:
        print(f"\n📅 Calendar Spread Opportunities:")
        for cal in calendars[:3]:  # Top 3
            print(f"  {cal.near_dte}d/{cal.far_dte}d: "
                  f"Vol diff: {cal.vol_difference:.2%}, "
                  f"Expected profit: ${cal.expected_profit:.0f}")
            
    # Detect anomalies
    anomalies = analyzer.detect_term_anomalies(structure)
    if anomalies:
        print(f"\n⚠️ Term Structure Anomalies:")
        for anomaly in anomalies:
            print(f"  {anomaly.anomaly_type} at {anomaly.dte_range[0]}-{anomaly.dte_range[1]}d")
            print(f"    Magnitude: {anomaly.magnitude:.3f}")
            print(f"    {anomaly.trading_implications}")
            
    # Generate signals
    signals = analyzer.generate_term_signals()
    if signals:
        print(f"\n📡 Trading Signals:")
        for signal in signals[:3]:  # Top 3
            print(f"  {signal['type']}: {signal['action']}")
            print(f"    Reason: {signal['reason']}")
            print(f"    Confidence: {signal['confidence']:.1%}")
            
    # Get metrics
    metrics = analyzer.get_term_metrics()
    print(f"\n📊 Summary Metrics:")
    print(f"  Average IV: {metrics['avg_iv']:.1%}")
    print(f"  IV Range: {metrics['iv_range'][0]:.1%} - {metrics['iv_range'][1]:.1%}")
    print(f"  Total Volume: {metrics['total_volume']:,}")
    
    print("\n✅ Term structure analysis complete!")
            