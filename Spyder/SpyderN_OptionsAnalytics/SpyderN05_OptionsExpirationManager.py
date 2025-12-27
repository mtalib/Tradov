#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN05_OptionsExpirationManager.py
Group: N (Options Analytics)
Purpose: Options expiration management, pin risk analysis, and roll automation
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 21:00:00

Description:
    This module provides comprehensive options expiration management including
    expiration tracking, pin risk analysis, auto-exercise decisions, roll
    management, assignment risk assessment, and expiration-day strategies.
    It ensures smooth handling of expiring positions and automates critical
    expiration-related decisions to minimize risk and optimize outcomes.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import json
import threading
import sqlite3
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import calendar
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
import holidays

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import pricing modules if available
try:
    from SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
    from SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False
    print("⚠️ Options analytics modules not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Time constants
MARKET_OPEN = time(9, 30)  # 9:30 AM ET
MARKET_CLOSE = time(16, 0)  # 4:00 PM ET
OPTIONS_CUTOFF = time(16, 15)  # 4:15 PM ET for after-hours exercise
ROLL_DAYS_BEFORE = 5  # Days before expiry to consider rolling
PIN_RISK_THRESHOLD = 0.02  # 2% from strike for pin risk

# Expiration parameters
WEEKLY_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'DIA', 'AAPL', 'TSLA', 'NVDA']
MONTHLY_SYMBOLS = ['VIX', 'GLD', 'TLT', 'SLV', 'USO']
AM_SETTLEMENT = ['SPX', 'VIX', 'RUT', 'NDX']  # AM settlement indices

# Risk thresholds
MAX_PIN_RISK_EXPOSURE = 100000  # Maximum dollar exposure to pin risk
AUTO_EXERCISE_THRESHOLD = 0.01  # Exercise if ITM by more than 1 cent
ASSIGNMENT_PROBABILITY_THRESHOLD = 0.80  # 80% probability threshold

# Roll parameters
MIN_PREMIUM_FOR_ROLL = 0.10  # Minimum premium to collect for roll
MAX_ROLL_COST = 0.50  # Maximum cost to pay for defensive roll
TARGET_ROLL_DTE = 30  # Target days to expiry for rolls

# ==============================================================================
# ENUMS
# ==============================================================================
class ExpirationType(Enum):
    """Expiration type enumeration"""
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    LEAP = "LEAP"
    SPECIAL = "SPECIAL"

class SettlementType(Enum):
    """Settlement type enumeration"""
    PM = "PM"  # Regular PM settlement
    AM = "AM"  # AM settlement (indices)
    CASH = "CASH"  # Cash settled
    PHYSICAL = "PHYSICAL"  # Physical delivery

class ExpirationAction(Enum):
    """Action to take on expiration"""
    EXERCISE = "EXERCISE"
    ABANDON = "ABANDON"
    ROLL = "ROLL"
    CLOSE = "CLOSE"
    HEDGE = "HEDGE"
    MONITOR = "MONITOR"

class PinRiskLevel(Enum):
    """Pin risk severity levels"""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RollType(Enum):
    """Roll strategy types"""
    CALENDAR = "CALENDAR"  # Same strike, different expiry
    DIAGONAL = "DIAGONAL"  # Different strike and expiry
    VERTICAL = "VERTICAL"  # Different strike, same expiry
    DEFENSIVE = "DEFENSIVE"  # Roll to avoid assignment
    OFFENSIVE = "OFFENSIVE"  # Roll for credit

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class ExpiringPosition:
    """Expiring options position"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'CALL' or 'PUT'
    quantity: int  # Negative for short
    current_price: float
    underlying_price: float
    days_to_expiry: int
    hours_to_expiry: float
    moneyness: float  # Distance from strike as percentage
    intrinsic_value: float
    extrinsic_value: float
    assignment_probability: float
    pin_risk_level: PinRiskLevel
    recommended_action: ExpirationAction
    action_reason: str
    
@dataclass
class PinRiskAnalysis:
    """Pin risk analysis for expiring positions"""
    strike: float
    underlying_price: float
    distance_from_strike: float
    distance_percentage: float
    risk_level: PinRiskLevel
    gamma_exposure: float
    max_loss: float
    max_gain: float
    probability_of_pin: float
    hedge_recommendation: Optional[Dict[str, Any]] = None
    
@dataclass
class RollOpportunity:
    """Options roll opportunity"""
    current_position: ExpiringPosition
    roll_type: RollType
    target_expiry: datetime
    target_strike: float
    net_credit: float  # Positive for credit, negative for debit
    new_delta: float
    new_theta: float
    risk_reduction: float  # Percentage risk reduction
    execution_priority: int  # 1 = highest priority
    notes: str
    
@dataclass
class ExpirationSchedule:
    """Expiration schedule and key dates"""
    expiry_date: date
    expiry_type: ExpirationType
    settlement_type: SettlementType
    symbols: List[str]
    total_positions: int
    total_exposure: float
    actions_required: int
    last_trading_day: date
    exercise_cutoff: datetime
    
@dataclass
class AssignmentRisk:
    """Early assignment risk assessment"""
    position: ExpiringPosition
    dividend_date: Optional[date]
    dividend_amount: float
    interest_cost: float
    probability_of_assignment: float
    economic_benefit: float  # Benefit to counterparty for early exercise
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    mitigation_action: Optional[str] = None

# ==============================================================================
# OPTIONS EXPIRATION MANAGER CLASS
# ==============================================================================
class OptionsExpirationManager:
    """
    Comprehensive options expiration management system.
    
    Features:
        - Expiration tracking and scheduling
        - Pin risk analysis and mitigation
        - Auto-exercise decision logic
        - Roll opportunity identification
        - Assignment risk assessment
        - Expiration day strategy execution
        - Historical expiration analysis
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Options Expiration Manager
        
        Args:
            config: Configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.auto_exercise_enabled = self.config.get('auto_exercise', True)
        self.auto_roll_enabled = self.config.get('auto_roll', False)
        self.pin_risk_hedging = self.config.get('pin_risk_hedging', True)
        
        # Positions tracking
        self.positions: List[ExpiringPosition] = []
        self.expiration_schedule: Dict[date, ExpirationSchedule] = {}
        self.roll_opportunities: List[RollOpportunity] = []
        
        # Analytics engines
        self.pricer = OptionsPricer() if ANALYTICS_AVAILABLE else None
        self.greeks_calculator = OptionsGreeksCalculator() if ANALYTICS_AVAILABLE else None
        
        # Market data
        self.underlying_prices: Dict[str, float] = {}
        self.dividend_schedule: Dict[str, List[Tuple[date, float]]] = {}
        self.interest_rate = 0.05
        
        # US market holidays
        self.us_holidays = holidays.US(years=range(2020, 2030))
        
        # Threading
        self.lock = threading.Lock()
        self.monitoring_thread = None
        self.monitoring_active = False
        
        # Database for historical tracking
        self.db_path = self.config.get('db_path', 'expiration_history.db')
        self._initialize_database()
        
        self.logger.info("OptionsExpirationManager initialized")
    
    # ==========================================================================
    # EXPIRATION TRACKING
    # ==========================================================================
    
    def add_position(self, symbol: str, strike: float, expiry: datetime,
                    option_type: str, quantity: int,
                    current_price: float,
                    underlying_price: Optional[float] = None) -> ExpiringPosition:
        """
        Add position to expiration tracking
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiry: Expiration datetime
            option_type: 'CALL' or 'PUT'
            quantity: Position quantity (negative for short)
            current_price: Current option price
            underlying_price: Current underlying price
            
        Returns:
            ExpiringPosition object
        """
        with self.lock:
            # Get underlying price
            if underlying_price is None:
                underlying_price = self.underlying_prices.get(symbol, strike)
            else:
                self.underlying_prices[symbol] = underlying_price
            
            # Calculate time to expiry
            now = datetime.now()
            days_to_expiry = (expiry.date() - now.date()).days
            hours_to_expiry = (expiry - now).total_seconds() / 3600
            
            # Calculate moneyness
            if option_type == 'CALL':
                moneyness = (underlying_price - strike) / strike
                intrinsic = max(0, underlying_price - strike)
            else:  # PUT
                moneyness = (strike - underlying_price) / strike
                intrinsic = max(0, strike - underlying_price)
            
            extrinsic = current_price - intrinsic
            
            # Calculate assignment probability
            assignment_prob = self._calculate_assignment_probability(
                symbol, strike, expiry, option_type, underlying_price
            )
            
            # Analyze pin risk
            pin_risk = self._analyze_pin_risk(
                strike, underlying_price, quantity, option_type
            )
            
            # Determine recommended action
            action, reason = self._determine_expiration_action(
                symbol, strike, expiry, option_type, quantity,
                underlying_price, days_to_expiry, intrinsic
            )
            
            # Create position
            position = ExpiringPosition(
                symbol=symbol,
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                quantity=quantity,
                current_price=current_price,
                underlying_price=underlying_price,
                days_to_expiry=days_to_expiry,
                hours_to_expiry=hours_to_expiry,
                moneyness=moneyness,
                intrinsic_value=intrinsic,
                extrinsic_value=extrinsic,
                assignment_probability=assignment_prob,
                pin_risk_level=pin_risk.risk_level,
                recommended_action=action,
                action_reason=reason
            )
            
            self.positions.append(position)
            
            # Update expiration schedule
            self._update_expiration_schedule(position)
            
            return position
    
    def get_expiring_positions(self, days_ahead: int = 7) -> List[ExpiringPosition]:
        """
        Get positions expiring within specified days
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring positions
        """
        cutoff_date = datetime.now() + timedelta(days=days_ahead)
        
        expiring = [
            pos for pos in self.positions
            if pos.expiry <= cutoff_date
        ]
        
        # Sort by expiry and moneyness
        expiring.sort(key=lambda x: (x.expiry, abs(x.moneyness)))
        
        return expiring
    
    def get_expiration_calendar(self, months_ahead: int = 3) -> pd.DataFrame:
        """
        Get expiration calendar
        
        Args:
            months_ahead: Number of months to look ahead
            
        Returns:
            DataFrame with expiration dates and details
        """
        expirations = []
        
        # Generate expiration dates
        start_date = date.today()
        end_date = start_date + timedelta(days=months_ahead * 30)
        
        current_date = start_date
        while current_date <= end_date:
            # Check for monthly expiration (3rd Friday)
            if self._is_monthly_expiration(current_date):
                exp_type = ExpirationType.MONTHLY
                
                # Check if quarterly
                if current_date.month in [3, 6, 9, 12]:
                    exp_type = ExpirationType.QUARTERLY
                
                expirations.append({
                    'date': current_date,
                    'type': exp_type.value,
                    'day_of_week': current_date.strftime('%A'),
                    'symbols': self._get_symbols_for_expiry(current_date, exp_type)
                })
            
            # Check for weekly expiration (Friday)
            elif current_date.weekday() == 4:  # Friday
                # Check if this is a weekly (not monthly)
                if not self._is_monthly_expiration(current_date):
                    expirations.append({
                        'date': current_date,
                        'type': ExpirationType.WEEKLY.value,
                        'day_of_week': 'Friday',
                        'symbols': WEEKLY_SYMBOLS
                    })
            
            current_date += timedelta(days=1)
        
        if expirations:
            df = pd.DataFrame(expirations)
            df['date'] = pd.to_datetime(df['date'])
            return df
        
        return pd.DataFrame()
    
    # ==========================================================================
    # PIN RISK ANALYSIS
    # ==========================================================================
    
    def _analyze_pin_risk(self, strike: float, underlying: float,
                         quantity: int, option_type: str) -> PinRiskAnalysis:
        """
        Analyze pin risk for position
        
        Args:
            strike: Strike price
            underlying: Underlying price
            quantity: Position quantity
            option_type: 'CALL' or 'PUT'
            
        Returns:
            PinRiskAnalysis object
        """
        distance = underlying - strike
        distance_pct = abs(distance) / strike
        
        # Determine risk level based on distance
        if distance_pct > 0.05:  # More than 5% away
            risk_level = PinRiskLevel.NONE
        elif distance_pct > 0.03:  # 3-5% away
            risk_level = PinRiskLevel.LOW
        elif distance_pct > 0.02:  # 2-3% away
            risk_level = PinRiskLevel.MEDIUM
        elif distance_pct > 0.01:  # 1-2% away
            risk_level = PinRiskLevel.HIGH
        else:  # Less than 1% away
            risk_level = PinRiskLevel.CRITICAL
        
        # Calculate gamma exposure (simplified)
        if self.greeks_calculator and abs(quantity) > 0:
            greeks = self.greeks_calculator.calculate_greeks(
                underlying, strike, 1/365, 0.20, self.interest_rate, option_type
            )
            gamma_exposure = greeks['gamma'] * quantity * 100 * underlying**2 / 100
        else:
            gamma_exposure = 0.0
        
        # Calculate max loss/gain
        if quantity > 0:  # Long position
            max_loss = quantity * 100 * current_price
            max_gain = float('inf') if option_type == 'CALL' else quantity * 100 * strike
        else:  # Short position
            max_gain = abs(quantity) * 100 * current_price
            max_loss = float('inf') if option_type == 'CALL' else abs(quantity) * 100 * strike
        
        # Calculate probability of pin
        # Use normal distribution around strike
        volatility = 0.20  # Assumed
        time_to_expiry = 1/365  # 1 day
        std_dev = underlying * volatility * np.sqrt(time_to_expiry)
        prob_of_pin = 2 * stats.norm.cdf(strike + strike * PIN_RISK_THRESHOLD, underlying, std_dev) - \
                     2 * stats.norm.cdf(strike - strike * PIN_RISK_THRESHOLD, underlying, std_dev)
        
        # Hedge recommendation for high risk
        hedge_rec = None
        if risk_level in [PinRiskLevel.HIGH, PinRiskLevel.CRITICAL]:
            hedge_rec = self._get_pin_risk_hedge(strike, underlying, quantity, option_type)
        
        return PinRiskAnalysis(
            strike=strike,
            underlying_price=underlying,
            distance_from_strike=distance,
            distance_percentage=distance_pct,
            risk_level=risk_level,
            gamma_exposure=gamma_exposure,
            max_loss=max_loss,
            max_gain=max_gain,
            probability_of_pin=prob_of_pin,
            hedge_recommendation=hedge_rec
        )
    
    def _get_pin_risk_hedge(self, strike: float, underlying: float,
                           quantity: int, option_type: str) -> Dict[str, Any]:
        """Get hedge recommendation for pin risk"""
        hedge = {
            'action': 'HEDGE_PIN_RISK',
            'trades': []
        }
        
        if quantity < 0:  # Short position with pin risk
            # Buy protective option
            hedge['trades'].append({
                'action': 'BUY',
                'option_type': option_type,
                'strike': strike,
                'quantity': abs(quantity),
                'reason': 'Pin risk protection'
            })
        else:  # Long position
            # Consider closing or rolling
            hedge['trades'].append({
                'action': 'CLOSE',
                'option_type': option_type,
                'strike': strike,
                'quantity': quantity,
                'reason': 'Avoid pin risk'
            })
        
        return hedge
    
    # ==========================================================================
    # AUTO-EXERCISE DECISIONS
    # ==========================================================================
    
    def determine_exercise_decisions(self) -> List[Dict[str, Any]]:
        """
        Determine auto-exercise decisions for expiring positions
        
        Returns:
            List of exercise decisions
        """
        decisions = []
        
        # Get positions expiring today
        today_expiring = self.get_expiring_positions(days_ahead=0)
        
        for position in today_expiring:
            if position.quantity > 0:  # Long position only
                decision = self._make_exercise_decision(position)
                decisions.append(decision)
        
        return decisions
    
    def _make_exercise_decision(self, position: ExpiringPosition) -> Dict[str, Any]:
        """Make exercise decision for position"""
        decision = {
            'symbol': position.symbol,
            'strike': position.strike,
            'option_type': position.option_type,
            'quantity': position.quantity,
            'action': 'ABANDON',
            'reason': '',
            'economic_value': 0.0
        }
        
        # Check if ITM
        if position.intrinsic_value > AUTO_EXERCISE_THRESHOLD:
            # Calculate economic benefit
            exercise_value = position.intrinsic_value * position.quantity * 100
            commission_cost = 0.65 * abs(position.quantity)  # Estimated commission
            
            if exercise_value > commission_cost:
                decision['action'] = 'EXERCISE'
                decision['reason'] = f'ITM by ${position.intrinsic_value:.2f}'
                decision['economic_value'] = exercise_value - commission_cost
            else:
                decision['reason'] = 'Commission exceeds intrinsic value'
        else:
            decision['reason'] = f'OTM or ATM (intrinsic: ${position.intrinsic_value:.2f})'
        
        # Check for dividend capture (calls only)
        if position.option_type == 'CALL' and position.symbol in self.dividend_schedule:
            div_decision = self._check_dividend_exercise(position)
            if div_decision['exercise']:
                decision['action'] = 'EXERCISE'
                decision['reason'] = div_decision['reason']
                decision['economic_value'] = div_decision['value']
        
        return decision
    
    def _check_dividend_exercise(self, position: ExpiringPosition) -> Dict[str, Any]:
        """Check if early exercise is beneficial for dividend capture"""
        result = {'exercise': False, 'reason': '', 'value': 0.0}
        
        if position.symbol not in self.dividend_schedule:
            return result
        
        # Check for upcoming dividend
        for div_date, div_amount in self.dividend_schedule[position.symbol]:
            if position.expiry.date() >= div_date > date.today():
                # Calculate if early exercise is beneficial
                interest_cost = position.strike * self.interest_rate * \
                               (position.expiry.date() - date.today()).days / 365
                
                if div_amount > position.extrinsic_value + interest_cost:
                    result['exercise'] = True
                    result['reason'] = f'Dividend capture: ${div_amount:.2f}'
                    result['value'] = div_amount - position.extrinsic_value - interest_cost
                    break
        
        return result
    
    # ==========================================================================
    # ROLL MANAGEMENT
    # ==========================================================================
    
    def identify_roll_opportunities(self) -> List[RollOpportunity]:
        """
        Identify options roll opportunities
        
        Returns:
            List of roll opportunities
        """
        opportunities = []
        
        # Get positions eligible for rolling
        roll_candidates = [
            pos for pos in self.positions
            if pos.days_to_expiry <= ROLL_DAYS_BEFORE and pos.quantity != 0
        ]
        
        for position in roll_candidates:
            # Analyze different roll strategies
            roll_ops = []
            
            # Calendar roll (same strike, next expiry)
            calendar = self._analyze_calendar_roll(position)
            if calendar:
                roll_ops.append(calendar)
            
            # Diagonal roll (different strike and expiry)
            diagonal = self._analyze_diagonal_roll(position)
            if diagonal:
                roll_ops.append(diagonal)
            
            # Defensive roll (if at risk)
            if position.quantity < 0 and position.intrinsic_value > 0:
                defensive = self._analyze_defensive_roll(position)
                if defensive:
                    roll_ops.append(defensive)
            
            opportunities.extend(roll_ops)
        
        # Sort by priority
        opportunities.sort(key=lambda x: x.execution_priority)
        
        self.roll_opportunities = opportunities
        return opportunities
    
    def _analyze_calendar_roll(self, position: ExpiringPosition) -> Optional[RollOpportunity]:
        """Analyze calendar roll opportunity"""
        # Find next expiration
        next_expiry = self._get_next_expiry(position.symbol, position.expiry)
        
        if not next_expiry:
            return None
        
        # Estimate prices (would use actual market data)
        current_price = position.current_price
        time_value_decay = current_price * 0.3  # 30% time decay estimate
        new_price = current_price + time_value_decay
        
        # Calculate net credit/debit
        if position.quantity < 0:  # Short position
            net_credit = new_price - current_price
        else:  # Long position
            net_credit = -(new_price - current_price)
        
        # Only proceed if favorable
        if net_credit < MIN_PREMIUM_FOR_ROLL and position.quantity < 0:
            return None
        
        return RollOpportunity(
            current_position=position,
            roll_type=RollType.CALENDAR,
            target_expiry=next_expiry,
            target_strike=position.strike,
            net_credit=net_credit,
            new_delta=position.moneyness * 0.5,  # Estimated
            new_theta=-0.05,  # Estimated
            risk_reduction=20.0,  # 20% risk reduction
            execution_priority=2,
            notes="Calendar roll to next expiry"
        )
    
    def _analyze_diagonal_roll(self, position: ExpiringPosition) -> Optional[RollOpportunity]:
        """Analyze diagonal roll opportunity"""
        next_expiry = self._get_next_expiry(position.symbol, position.expiry)
        
        if not next_expiry:
            return None
        
        # Determine new strike based on market move
        if position.option_type == 'CALL':
            if position.underlying_price > position.strike:
                # Roll up and out
                new_strike = position.strike + 5.0
            else:
                # Roll down and out
                new_strike = position.strike - 5.0
        else:  # PUT
            if position.underlying_price < position.strike:
                # Roll down and out
                new_strike = position.strike - 5.0
            else:
                # Roll up and out
                new_strike = position.strike + 5.0
        
        # Estimate net credit (simplified)
        strike_adjustment = abs(new_strike - position.strike) * 0.01
        net_credit = strike_adjustment if position.quantity < 0 else -strike_adjustment
        
        return RollOpportunity(
            current_position=position,
            roll_type=RollType.DIAGONAL,
            target_expiry=next_expiry,
            target_strike=new_strike,
            net_credit=net_credit,
            new_delta=(position.underlying_price - new_strike) / new_strike * 0.5,
            new_theta=-0.04,
            risk_reduction=30.0,
            execution_priority=3,
            notes=f"Diagonal roll to {new_strike}"
        )
    
    def _analyze_defensive_roll(self, position: ExpiringPosition) -> Optional[RollOpportunity]:
        """Analyze defensive roll for challenged position"""
        if position.quantity >= 0:  # Only for short positions
            return None
        
        next_expiry = self._get_next_expiry(position.symbol, position.expiry)
        
        if not next_expiry:
            return None
        
        # Roll to OTM strike
        if position.option_type == 'CALL':
            new_strike = position.underlying_price * 1.05  # 5% OTM
        else:  # PUT
            new_strike = position.underlying_price * 0.95  # 5% OTM
        
        # Round to nearest strike interval
        new_strike = round(new_strike / 5) * 5
        
        # This will likely cost money (defensive)
        roll_cost = -position.intrinsic_value - MAX_ROLL_COST
        
        return RollOpportunity(
            current_position=position,
            roll_type=RollType.DEFENSIVE,
            target_expiry=next_expiry,
            target_strike=new_strike,
            net_credit=roll_cost,
            new_delta=0.30,  # Target 30 delta
            new_theta=-0.03,
            risk_reduction=50.0,  # Significant risk reduction
            execution_priority=1,  # High priority
            notes="Defensive roll to avoid assignment"
        )
    
    # ==========================================================================
    # ASSIGNMENT RISK
    # ==========================================================================
    
    def assess_assignment_risk(self) -> List[AssignmentRisk]:
        """
        Assess early assignment risk for short positions
        
        Returns:
            List of assignment risk assessments
        """
        risks = []
        
        # Only check short positions
        short_positions = [pos for pos in self.positions if pos.quantity < 0]
        
        for position in short_positions:
            risk = self._calculate_assignment_risk(position)
            risks.append(risk)
        
        # Sort by risk level
        risks.sort(key=lambda x: x.probability_of_assignment, reverse=True)
        
        return risks
    
    def _calculate_assignment_risk(self, position: ExpiringPosition) -> AssignmentRisk:
        """Calculate assignment risk for position"""
        # Check for dividend risk (calls)
        div_date = None
        div_amount = 0.0
        
        if position.option_type == 'CALL' and position.symbol in self.dividend_schedule:
            for date, amount in self.dividend_schedule[position.symbol]:
                if date <= position.expiry.date():
                    div_date = date
                    div_amount = amount
                    break
        
        # Calculate interest cost
        interest_cost = position.strike * self.interest_rate * position.days_to_expiry / 365
        
        # Calculate economic benefit to counterparty
        economic_benefit = 0.0
        if position.option_type == 'CALL':
            economic_benefit = max(0, position.intrinsic_value + div_amount - position.extrinsic_value - interest_cost)
        else:  # PUT
            economic_benefit = max(0, position.intrinsic_value - position.extrinsic_value + interest_cost)
        
        # Calculate probability
        if economic_benefit > 0:
            # Higher benefit = higher probability
            prob = min(0.95, economic_benefit / (position.strike * 0.01))
        else:
            # Base probability on moneyness
            if position.intrinsic_value > position.strike * 0.05:  # Deep ITM
                prob = 0.80
            elif position.intrinsic_value > 0:  # ITM
                prob = 0.50
            else:  # OTM
                prob = 0.05
        
        # Determine risk level
        if prob > 0.80:
            risk_level = 'HIGH'
            mitigation = 'Close or roll immediately'
        elif prob > 0.50:
            risk_level = 'MEDIUM'
            mitigation = 'Monitor closely, prepare to roll'
        else:
            risk_level = 'LOW'
            mitigation = 'Monitor'
        
        return AssignmentRisk(
            position=position,
            dividend_date=div_date,
            dividend_amount=div_amount,
            interest_cost=interest_cost,
            probability_of_assignment=prob,
            economic_benefit=economic_benefit,
            risk_level=risk_level,
            mitigation_action=mitigation
        )
    
    def _calculate_assignment_probability(self, symbol: str, strike: float,
                                         expiry: datetime, option_type: str,
                                         underlying: float) -> float:
        """Calculate probability of assignment"""
        # Simplified calculation
        moneyness = (underlying - strike) / strike if option_type == 'CALL' else (strike - underlying) / strike
        
        if moneyness > 0.05:  # Deep ITM
            return 0.95
        elif moneyness > 0.02:  # ITM
            return 0.70
        elif moneyness > 0:  # Slightly ITM
            return 0.50
        elif moneyness > -0.02:  # ATM
            return 0.20
        else:  # OTM
            return 0.05
    
    # ==========================================================================
    # EXPIRATION ACTIONS
    # ==========================================================================
    
    def _determine_expiration_action(self, symbol: str, strike: float,
                                    expiry: datetime, option_type: str,
                                    quantity: int, underlying: float,
                                    days_to_expiry: int,
                                    intrinsic: float) -> Tuple[ExpirationAction, str]:
        """
        Determine recommended action for expiring position
        
        Returns:
            Tuple of (action, reason)
        """
        # Expiration day
        if days_to_expiry == 0:
            if quantity > 0:  # Long position
                if intrinsic > AUTO_EXERCISE_THRESHOLD:
                    return ExpirationAction.EXERCISE, "ITM - auto-exercise"
                else:
                    return ExpirationAction.ABANDON, "OTM - let expire"
            else:  # Short position
                if intrinsic > 0:
                    return ExpirationAction.CLOSE, "ITM short - close to avoid assignment"
                else:
                    return ExpirationAction.MONITOR, "OTM short - monitor until close"
        
        # Pre-expiration
        elif days_to_expiry <= ROLL_DAYS_BEFORE:
            if quantity < 0 and intrinsic > 0:  # Short and ITM
                return ExpirationAction.ROLL, "ITM short - consider rolling"
            elif abs((underlying - strike) / strike) < PIN_RISK_THRESHOLD:
                return ExpirationAction.HEDGE, "Near strike - pin risk"
            else:
                return ExpirationAction.MONITOR, "Monitor position"
        
        else:
            return ExpirationAction.MONITOR, "Time remaining"
    
    # ==========================================================================
    # SCHEDULING AND UTILITIES
    # ==========================================================================
    
    def _update_expiration_schedule(self, position: ExpiringPosition) -> None:
        """Update expiration schedule with position"""
        exp_date = position.expiry.date()
        
        if exp_date not in self.expiration_schedule:
            # Determine expiration type
            if self._is_monthly_expiration(exp_date):
                exp_type = ExpirationType.MONTHLY
                if exp_date.month in [3, 6, 9, 12]:
                    exp_type = ExpirationType.QUARTERLY
            elif exp_date.weekday() == 4:  # Friday
                exp_type = ExpirationType.WEEKLY
            else:
                exp_type = ExpirationType.SPECIAL
            
            # Determine settlement type
            if position.symbol in AM_SETTLEMENT:
                settlement = SettlementType.AM
            else:
                settlement = SettlementType.PM
            
            schedule = ExpirationSchedule(
                expiry_date=exp_date,
                expiry_type=exp_type,
                settlement_type=settlement,
                symbols=[position.symbol],
                total_positions=1,
                total_exposure=abs(position.quantity * 100 * position.current_price),
                actions_required=1 if position.recommended_action != ExpirationAction.MONITOR else 0,
                last_trading_day=self._get_last_trading_day(exp_date),
                exercise_cutoff=datetime.combine(exp_date, OPTIONS_CUTOFF)
            )
            
            self.expiration_schedule[exp_date] = schedule
        else:
            # Update existing schedule
            schedule = self.expiration_schedule[exp_date]
            if position.symbol not in schedule.symbols:
                schedule.symbols.append(position.symbol)
            schedule.total_positions += 1
            schedule.total_exposure += abs(position.quantity * 100 * position.current_price)
            if position.recommended_action != ExpirationAction.MONITOR:
                schedule.actions_required += 1
    
    def _is_monthly_expiration(self, check_date: date) -> bool:
        """Check if date is monthly options expiration (3rd Friday)"""
        if check_date.weekday() != 4:  # Not Friday
            return False
        
        # Check if it's the 3rd Friday
        first_day = check_date.replace(day=1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        
        return check_date == third_friday
    
    def _get_last_trading_day(self, expiry_date: date) -> date:
        """Get last trading day before expiration"""
        # For most options, last trading day is expiration day
        # For AM settlement, it's the day before
        last_day = expiry_date
        
        # Check if market is open
        while last_day in self.us_holidays or last_day.weekday() >= 5:
            last_day -= timedelta(days=1)
        
        return last_day
    
    def _get_next_expiry(self, symbol: str, current_expiry: datetime) -> Optional[datetime]:
        """Get next available expiry date"""
        # Determine if weekly or monthly
        if symbol in WEEKLY_SYMBOLS:
            # Next Friday
            next_friday = current_expiry + timedelta(days=7)
            while next_friday.weekday() != 4:
                next_friday += timedelta(days=1)
            return next_friday
        else:
            # Next monthly expiration
            next_month = current_expiry.replace(day=1) + timedelta(days=32)
            next_month = next_month.replace(day=1)
            
            # Find 3rd Friday
            first_friday = next_month + timedelta(days=(4 - next_month.weekday()) % 7)
            third_friday = first_friday + timedelta(weeks=2)
            
            return datetime.combine(third_friday, current_expiry.time())
    
    def _get_symbols_for_expiry(self, expiry_date: date,
                               exp_type: ExpirationType) -> List[str]:
        """Get symbols that have options expiring on date"""
        if exp_type == ExpirationType.WEEKLY:
            return WEEKLY_SYMBOLS
        elif exp_type in [ExpirationType.MONTHLY, ExpirationType.QUARTERLY]:
            return WEEKLY_SYMBOLS + MONTHLY_SYMBOLS
        else:
            return []
    
    # ==========================================================================
    # DATABASE OPERATIONS
    # ==========================================================================
    
    def _initialize_database(self) -> None:
        """Initialize database for historical tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expiration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    strike REAL,
                    expiry DATE,
                    option_type TEXT,
                    quantity INTEGER,
                    action_taken TEXT,
                    pnl REAL,
                    notes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS roll_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_strike REAL,
                    original_expiry DATE,
                    new_strike REAL,
                    new_expiry DATE,
                    roll_type TEXT,
                    net_credit REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
    
    def save_expiration_action(self, position: ExpiringPosition,
                              action: str, pnl: float, notes: str = "") -> None:
        """Save expiration action to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO expiration_history 
                (symbol, strike, expiry, option_type, quantity, action_taken, pnl, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (position.symbol, position.strike, position.expiry,
                 position.option_type, position.quantity, action, pnl, notes))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to save expiration action: {e}")

# ==============================================================================
# TEST/DEMO CODE
# ==============================================================================
if __name__ == "__main__":
    print("="*80)
    print(" SPYDER OPTIONS EXPIRATION MANAGER TEST")
    print("="*80)
    
    # Create manager
    manager = OptionsExpirationManager()
    
    # Test 1: Add expiring positions
    print("\n1. Adding Expiring Positions...")
    
    # Positions with different expiration scenarios
    positions_data = [
        # Expiring today - ITM call
        ('SPY', 580, datetime.now(), 'CALL', 2, 6.50, 585.0),
        # Expiring today - OTM put
        ('SPY', 575, datetime.now(), 'PUT', -5, 0.10, 585.0),
        # Expiring in 3 days - near strike (pin risk)
        ('SPY', 585, datetime.now() + timedelta(days=3), 'CALL', -10, 2.00, 585.50),
        # Expiring in 5 days - ITM short put
        ('SPY', 590, datetime.now() + timedelta(days=5), 'PUT', -3, 6.00, 585.0),
        # Expiring in 7 days - OTM call
        ('SPY', 595, datetime.now() + timedelta(days=7), 'CALL', 5, 0.50, 585.0),
    ]
    
    for data in positions_data:
        position = manager.add_position(*data)
        print(f"  {position.symbol} {position.strike} {position.option_type}: "
              f"Action={position.recommended_action.value}, "
              f"Pin Risk={position.pin_risk_level.value}")
    
    # Test 2: Get expiration calendar
    print("\n2. Expiration Calendar...")
    calendar = manager.get_expiration_calendar(months_ahead=2)
    if not calendar.empty:
        print(f"  Next 5 expirations:")
        for _, row in calendar.head().iterrows():
            print(f"    {row['date'].strftime('%Y-%m-%d')} ({row['type']})")
    
    # Test 3: Exercise decisions
    print("\n3. Auto-Exercise Decisions...")
    decisions = manager.determine_exercise_decisions()
    for decision in decisions:
        print(f"  {decision['symbol']} {decision['strike']} {decision['option_type']}: "
              f"{decision['action']} - {decision['reason']}")
    
    # Test 4: Roll opportunities
    print("\n4. Roll Opportunities...")
    rolls = manager.identify_roll_opportunities()
    for roll in rolls[:3]:  # Show top 3
        print(f"  {roll.current_position.symbol} {roll.current_position.strike}: "
              f"{roll.roll_type.value} to {roll.target_strike} @ {roll.target_expiry.date()}")
        print(f"    Net Credit: ${roll.net_credit:.2f}, "
              f"Risk Reduction: {roll.risk_reduction:.0f}%")
    
    # Test 5: Assignment risk
    print("\n5. Assignment Risk Assessment...")
    risks = manager.assess_assignment_risk()
    for risk in risks:
        if risk.probability_of_assignment > 0.20:
            print(f"  {risk.position.symbol} {risk.position.strike} {risk.position.option_type}: "
                  f"P(Assignment)={risk.probability_of_assignment:.0%}, "
                  f"Risk={risk.risk_level}")
            print(f"    Mitigation: {risk.mitigation_action}")
    
    # Test 6: Pin risk analysis
    print("\n6. Pin Risk Analysis...")
    for position in manager.positions:
        if position.pin_risk_level not in [PinRiskLevel.NONE, PinRiskLevel.LOW]:
            print(f"  {position.symbol} {position.strike}: "
                  f"Pin Risk={position.pin_risk_level.value}, "
                  f"Distance={abs(position.underlying_price - position.strike):.2f}")
    
    # Test 7: Expiration schedule
    print("\n7. Expiration Schedule Summary...")
    for exp_date, schedule in sorted(manager.expiration_schedule.items()):
        print(f"  {exp_date}: {schedule.total_positions} positions, "
              f"${schedule.total_exposure:,.0f} exposure, "
              f"{schedule.actions_required} actions required")
    
    print("\n" + "="*80)
    print(" ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*80)