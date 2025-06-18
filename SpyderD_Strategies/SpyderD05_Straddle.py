#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD05_Straddle.py
Group: D (Trading Strategies)
Purpose: Long straddle/strangle strategies

Description:
    This module implements long straddle and strangle strategies designed to
    profit from significant price movements in either direction. These strategies
    are particularly effective before major events or when expecting increased
    volatility.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import math
import uuid
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    OptionType, OrderAction, SignalType, OptionRight
)
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy, TradingSignal, SignalStrength, StrategyPosition
)
from SpyderB_Broker.SpyderB06_ContractBuilder import OptionContract
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderA_Core.SpyderA05_EventManager import EventManager
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MIN_IMPLIED_VOL_RANK = 20  # Minimum IV rank for entry
MAX_IMPLIED_VOL_RANK = 50  # Maximum IV rank (avoid when too expensive)
MIN_EXPECTED_MOVE = 0.015  # Minimum expected move (1.5%)
MAX_DAYS_TO_EXPIRY = 45
MIN_DAYS_TO_EXPIRY = 7

# Straddle/Strangle parameters
STRANGLE_DELTA = 0.30  # Delta for strangle strikes
STRADDLE_ATM_THRESHOLD = 0.50  # Strike within 0.5% of spot for straddle
MIN_PROFIT_TARGET = 0.25  # 25% profit target
MAX_LOSS_PERCENT = 0.50  # 50% max loss

# Event-based parameters
EARNINGS_WINDOW_DAYS = 3  # Days before/after earnings
FOMC_WINDOW_DAYS = 2  # Days before/after FOMC
HIGH_VOL_EVENTS = ['earnings', 'fomc', 'cpi', 'jobs_report', 'opex']

# Greeks thresholds
MIN_VEGA = 0.10  # Minimum vega exposure
MAX_THETA_DECAY = -0.05  # Maximum theta decay per day
MIN_GAMMA = 0.01  # Minimum gamma

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyType(Enum):
    """Straddle/Strangle strategy types"""
    LONG_STRADDLE = auto()
    LONG_STRANGLE = auto()
    
class VolatilityRegime(Enum):
    """Volatility regime classification"""
    LOW = auto()
    NORMAL = auto()
    ELEVATED = auto()
    HIGH = auto()
    
class EventType(Enum):
    """Market event types"""
    NONE = auto()
    EARNINGS = auto()
    FOMC = auto()
    ECONOMIC_DATA = auto()
    OPEX = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class VolatilitySetup:
    """Volatility trade setup"""
    strategy_type: StrategyType
    call_strike: float
    put_strike: float
    expiration: datetime
    total_premium: float
    breakeven_up: float
    breakeven_down: float
    max_profit: float  # Theoretical unlimited
    max_loss: float
    implied_vol: float
    historical_vol: float
    vol_rank: float
    expected_move: float
    vega: float
    gamma: float
    theta: float
    
class MarketEvent:
    """Upcoming market event"""
    event_type: EventType
    event_date: datetime
    expected_impact: str  # 'low', 'medium', 'high'
    description: str

class VolatilityAnalysis:
    """Volatility analysis results"""
    current_iv: float
    iv_rank: float
    iv_percentile: float
    hv_20: float  # 20-day historical volatility
    hv_30: float  # 30-day historical volatility
    iv_hv_ratio: float
    volatility_regime: VolatilityRegime
    term_structure: Dict[int, float]  # DTE -> IV
    volatility_smile: Dict[float, float]  # Strike -> IV
    upcoming_events: List[MarketEvent]

# ==============================================================================
# STRADDLE/STRANGLE STRATEGY CLASS
# ==============================================================================
class StraddleStrategy(BaseStrategy):
    """
    Long straddle and strangle strategy implementation.
    
    Profits from large price movements in either direction by:
    - Identifying low volatility environments
    - Detecting upcoming catalysts
    - Managing positions based on realized vs implied volatility
    """
    
    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: Dict[str, Any]
    ):
        """
        Initialize straddle/strangle strategy.
        
        Args:
            event_manager: Event manager instance
            risk_profile: Risk profile
            config: Strategy configuration
        """
        super().__init__(
            name="Straddle",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config
        )
        
        # Strategy specific configuration
        self.use_straddles = config.get('use_straddles', True)
        self.use_strangles = config.get('use_strangles', True)
        self.trade_events = config.get('trade_events', True)
        self.max_positions = config.get('max_positions', 2)
        self.target_dte = config.get('target_dte', 30)
        
        # Components
        self.volatility_analyzer = VolatilityAnalyzer()
        self.greeks_calculator = GreeksCalculator()
        self.trading_calendar = TradingCalendar()
        
        # State tracking
        self.volatility_analysis: Optional[VolatilityAnalysis] = None
        self.active_setups: List[VolatilitySetup] = []
        
        self.logger.info("StraddleStrategy initialized")
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """
        Generate straddle/strangle signals.
        
        Args:
            market_data: Market data DataFrame
            
        Returns:
            List of trading signals
        """
        signals = []
        
        if len(market_data) < 30:
            return signals
        
        try:
            # Analyze volatility conditions
            self.volatility_analysis = self._analyze_volatility(market_data)
            
            if self.volatility_analysis is None:
                return signals
            
            # Check for entry opportunities
            if self._should_enter_volatility_trade():
                # Determine best strategy type
                setups = self._find_volatility_setups(market_data)
                
                # Create signals from best setups
                for setup in setups[:1]:  # Limit to 1 new position
                    signal = self._create_signal_from_setup(setup, market_data)
                    if signal:
                        signals.append(signal)
            
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            self.error_handler.handle_error(e, self.name)
        
        return signals
    
    def _analyze_volatility(self, market_data: pd.DataFrame) -> Optional[VolatilityAnalysis]:
        """Analyze volatility conditions"""
        current_price = market_data['close'].iloc[-1]
        
        # Calculate implied volatility metrics
        # In real implementation, would get from option chain
        current_iv = self._estimate_implied_volatility(market_data)
        iv_rank = self._calculate_iv_rank(current_iv)
        iv_percentile = self._calculate_iv_percentile(current_iv)
        
        # Calculate historical volatility
        returns = market_data['close'].pct_change()
        hv_20 = returns.rolling(20).std().iloc[-1] * math.sqrt(252)
        hv_30 = returns.rolling(30).std().iloc[-1] * math.sqrt(252)
        
        # IV/HV ratio
        iv_hv_ratio = current_iv / hv_20 if hv_20 > 0 else 1.0
        
        # Determine volatility regime
        if iv_rank < 25:
            vol_regime = VolatilityRegime.LOW
        elif iv_rank < 50:
            vol_regime = VolatilityRegime.NORMAL
        elif iv_rank < 75:
            vol_regime = VolatilityRegime.ELEVATED
        else:
            vol_regime = VolatilityRegime.HIGH
        
        # Get term structure (simplified)
        term_structure = self._get_term_structure()
        
        # Get volatility smile (simplified)
        volatility_smile = self._get_volatility_smile(current_price)
        
        # Check for upcoming events
        upcoming_events = self._get_upcoming_events()
        
        return VolatilityAnalysis(
            current_iv=current_iv,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            hv_20=hv_20,
            hv_30=hv_30,
            iv_hv_ratio=iv_hv_ratio,
            volatility_regime=vol_regime,
            term_structure=term_structure,
            volatility_smile=volatility_smile,
            upcoming_events=upcoming_events
        )
    
    def _should_enter_volatility_trade(self) -> bool:
        """Check if should enter volatility trade"""
        if not self.volatility_analysis:
            return False
        
        # Check position limits
        current_positions = len([p for p in self.positions.values() 
                               if p.metadata.get('strategy_type') in ['straddle', 'strangle']])
        if current_positions >= self.max_positions:
            return False
        
        # Check IV rank
        if (self.volatility_analysis.iv_rank < MIN_IMPLIED_VOL_RANK or
            self.volatility_analysis.iv_rank > MAX_IMPLIED_VOL_RANK):
            return False
        
        # Check for upcoming catalysts
        high_impact_events = [e for e in self.volatility_analysis.upcoming_events 
                            if e.expected_impact == 'high']
        
        # Look for volatility expansion setups
        if self.volatility_analysis.volatility_regime == VolatilityRegime.LOW:
            # Low volatility with potential catalyst
            if high_impact_events or self.volatility_analysis.iv_hv_ratio < 0.8:
                return True
        
        # Event-based trades
        if self.trade_events and high_impact_events:
            days_to_event = (high_impact_events[0].event_date - datetime.now()).days
            if 1 <= days_to_event <= 5:
                return True
        
        # Term structure opportunities
        if self._check_term_structure_opportunity():
            return True
        
        return False
    
    def _find_volatility_setups(self, market_data: pd.DataFrame) -> List[VolatilitySetup]:
        """Find potential volatility setups"""
        setups = []
        current_price = market_data['close'].iloc[-1]
        
        # Find optimal expiration
        target_expiration = self._find_optimal_expiration()
        
        if not target_expiration:
            return setups
        
        # Check straddle setup
        if self.use_straddles:
            straddle_setup = self._create_straddle_setup(
                current_price,
                target_expiration
            )
            if straddle_setup and self._validate_setup(straddle_setup):
                setups.append(straddle_setup)
        
        # Check strangle setup
        if self.use_strangles:
            strangle_setup = self._create_strangle_setup(
                current_price,
                target_expiration
            )
            if strangle_setup and self._validate_setup(strangle_setup):
                setups.append(strangle_setup)
        
        # Sort by expected value
        setups.sort(key=lambda x: self._calculate_setup_score(x), reverse=True)
        
        return setups
    
    def _create_straddle_setup(
        self,
        current_price: float,
        expiration: datetime
    ) -> Optional[VolatilitySetup]:
        """Create straddle setup"""
        # Find ATM strike
        atm_strike = round(current_price)
        
        # Calculate option prices (simplified)
        time_to_expiry = (expiration - datetime.now()).days / 365.0
        volatility = self.volatility_analysis.current_iv if self.volatility_analysis else 0.15
        risk_free_rate = 0.05
        
        # Calculate call and put prices
        call_price = self.greeks_calculator.black_scholes_price(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL
        )
        put_price = self.greeks_calculator.black_scholes_price(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.PUT
        )
        
        total_premium = call_price + put_price
        
        # Calculate breakevens
        breakeven_up = atm_strike + total_premium
        breakeven_down = atm_strike - total_premium
        
        # Expected move
        expected_move = volatility * math.sqrt(time_to_expiry) * current_price
        
        # Calculate Greeks
        call_delta = self.greeks_calculator.delta(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL
        )
        put_delta = self.greeks_calculator.delta(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.PUT
        )
        
        # Combined Greeks
        vega = self.greeks_calculator.vega(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility
        ) * 2  # Both legs
        
        gamma = self.greeks_calculator.gamma(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility
        ) * 2  # Both legs
        
        theta = self.greeks_calculator.theta(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL
        ) + self.greeks_calculator.theta(
            current_price, atm_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.PUT
        )
        
        return VolatilitySetup(
            strategy_type=StrategyType.LONG_STRADDLE,
            call_strike=atm_strike,
            put_strike=atm_strike,
            expiration=expiration,
            total_premium=total_premium,
            breakeven_up=breakeven_up,
            breakeven_down=breakeven_down,
            max_profit=float('inf'),  # Theoretical unlimited
            max_loss=total_premium * 100,  # Premium paid
            implied_vol=volatility,
            historical_vol=self.volatility_analysis.hv_20 if self.volatility_analysis else 0.15,
            vol_rank=self.volatility_analysis.iv_rank if self.volatility_analysis else 50,
            expected_move=expected_move,
            vega=vega,
            gamma=gamma,
            theta=theta
        )
    
    def _create_strangle_setup(
        self,
        current_price: float,
        expiration: datetime
    ) -> Optional[VolatilitySetup]:
        """Create strangle setup"""
        # Find OTM strikes based on delta
        time_to_expiry = (expiration - datetime.now()).days / 365.0
        volatility = self.volatility_analysis.current_iv if self.volatility_analysis else 0.15
        
        # Find strikes with target delta
        call_strike = self._find_strike_by_delta(
            current_price, STRANGLE_DELTA, OptionType.CALL,
            time_to_expiry, volatility
        )
        put_strike = self._find_strike_by_delta(
            current_price, -STRANGLE_DELTA, OptionType.PUT,
            time_to_expiry, volatility
        )
        
        # Calculate option prices
        risk_free_rate = 0.05
        
        call_price = self.greeks_calculator.black_scholes_price(
            current_price, call_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL
        )
        put_price = self.greeks_calculator.black_scholes_price(
            current_price, put_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.PUT
        )
        
        total_premium = call_price + put_price
        
        # Calculate breakevens
        breakeven_up = call_strike + total_premium
        breakeven_down = put_strike - total_premium
        
        # Expected move
        expected_move = volatility * math.sqrt(time_to_expiry) * current_price
        
        # Calculate Greeks
        vega = (self.greeks_calculator.vega(
            current_price, call_strike, time_to_expiry,
            risk_free_rate, volatility
        ) + self.greeks_calculator.vega(
            current_price, put_strike, time_to_expiry,
            risk_free_rate, volatility
        ))
        
        gamma = (self.greeks_calculator.gamma(
            current_price, call_strike, time_to_expiry,
            risk_free_rate, volatility
        ) + self.greeks_calculator.gamma(
            current_price, put_strike, time_to_expiry,
            risk_free_rate, volatility
        ))
        
        theta = (self.greeks_calculator.theta(
            current_price, call_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL
        ) + self.greeks_calculator.theta(
            current_price, put_strike, time_to_expiry,
            risk_free_rate, volatility, OptionType.PUT
        ))
        
        return VolatilitySetup(
            strategy_type=StrategyType.LONG_STRANGLE,
            call_strike=call_strike,
            put_strike=put_strike,
            expiration=expiration,
            total_premium=total_premium,
            breakeven_up=breakeven_up,
            breakeven_down=breakeven_down,
            max_profit=float('inf'),  # Theoretical unlimited
            max_loss=total_premium * 100,  # Premium paid
            implied_vol=volatility,
            historical_vol=self.volatility_analysis.hv_20 if self.volatility_analysis else 0.15,
            vol_rank=self.volatility_analysis.iv_rank if self.volatility_analysis else 50,
            expected_move=expected_move,
            vega=vega,
            gamma=gamma,
            theta=theta
        )
    
    def _create_signal_from_setup(
        self,
        setup: VolatilitySetup,
        market_data: pd.DataFrame
    ) -> Optional[TradingSignal]:
        """Create trading signal from volatility setup"""
        # Create option contracts
        call_contract = OptionContract(
            symbol="SPY",
            strike=setup.call_strike,
            expiration=setup.expiration,
            right=OptionRight.CALL,
            multiplier=100
        )
        
        put_contract = OptionContract(
            symbol="SPY",
            strike=setup.put_strike,
            expiration=setup.expiration,
            right=OptionRight.PUT,
            multiplier=100
        )
        
        # Determine signal strength
        score = self._calculate_setup_score(setup)
        if score > 0.8:
            strength = SignalStrength.VERY_STRONG
        elif score > 0.6:
            strength = SignalStrength.STRONG
        elif score > 0.4:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        
        # Create signal
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            strategy_name=self.name,
            signal_type=SignalType.VOLATILITY,
            strength=strength,
            contracts=[call_contract, put_contract],
            entry_price=market_data['close'].iloc[-1],
            stop_loss=None,  # Managed by position logic
            take_profit=None,  # Managed by position logic
            confidence=score,
            metadata={
                'strategy_type': setup.strategy_type.name.lower(),
                'total_premium': setup.total_premium,
                'breakeven_up': setup.breakeven_up,
                'breakeven_down': setup.breakeven_down,
                'max_loss': setup.max_loss,
                'implied_vol': setup.implied_vol,
                'vol_rank': setup.vol_rank,
                'expected_move': setup.expected_move,
                'vega': setup.vega,
                'gamma': setup.gamma,
                'theta': setup.theta,
                'days_to_expiry': (setup.expiration - datetime.now()).days
            }
        )
        
        return signal
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def should_enter_position(self, signal: TradingSignal) -> bool:
        """Check if position should be entered"""
        # Verify volatility conditions haven't changed dramatically
        if self.volatility_analysis:
            current_iv_rank = self.volatility_analysis.iv_rank
            signal_iv_rank = signal.metadata.get('vol_rank', 0)
            
            # Don't enter if IV rank has increased significantly
            if current_iv_rank > signal_iv_rank + 20:
                self.logger.info(f"IV rank increased too much: {current_iv_rank} vs {signal_iv_rank}")
                return False
        
        # Check Greeks
        if signal.metadata.get('vega', 0) < MIN_VEGA:
            return False
        
        if signal.metadata.get('theta', 0) < MAX_THETA_DECAY:
            return False
        
        return True
    
    def should_exit_position(self, position: StrategyPosition) -> bool:
        """Check if position should be exited"""
        # Calculate position P&L percentage
        entry_cost = position.metadata.get('total_premium', 1) * 100 * position.position_size
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        # Profit target
        if pnl_percent >= MIN_PROFIT_TARGET:
            self.logger.info(f"Position {position.position_id} hit profit target: {pnl_percent:.2%}")
            return True
        
        # Stop loss
        if pnl_percent <= -MAX_LOSS_PERCENT:
            self.logger.info(f"Position {position.position_id} hit stop loss: {pnl_percent:.2%}")
            return True
        
        # Time-based exit
        days_to_expiry = position.metadata.get('days_to_expiry', 30)
        days_held = (datetime.now() - position.entry_time).days
        current_dte = days_to_expiry - days_held
        
        if current_dte <= 3:  # Exit 3 days before expiry
            self.logger.info(f"Position {position.position_id} approaching expiry")
            return True
        
        # Volatility collapse
        if self.volatility_analysis:
            entry_iv = position.metadata.get('implied_vol', 0.15)
            current_iv = self.volatility_analysis.current_iv
            
            if current_iv < entry_iv * 0.7:  # 30% IV drop
                self.logger.info(f"Volatility collapsed for position {position.position_id}")
                return True
        
        # Check if expected move has been realized
        entry_price = position.entry_price
        expected_move = position.metadata.get('expected_move', 0)
        actual_move = abs(self.current_price - entry_price)
        
        if actual_move > expected_move * 0.8:  # 80% of expected move realized
            if pnl_percent > 0.10:  # Take profits if positive
                self.logger.info(f"Expected move realized for position {position.position_id}")
                return True
        
        return False
    
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for volatility trade"""
        # Risk-based sizing
        max_loss = signal.metadata.get('max_loss', 0)
        
        if max_loss <= 0:
            return 0
        
        # Risk 2% of account per trade
        risk_amount = self.risk_profile.account_size * 0.02
        position_size = int(risk_amount / max_loss)
        
        # Apply limits
        return max(1, min(position_size, 10))
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _estimate_implied_volatility(self, market_data: pd.DataFrame) -> float:
        """Estimate implied volatility from market data"""
        # In real implementation, would get from option chain
        # For now, use historical volatility with adjustment
        returns = market_data['close'].pct_change()
        hv = returns.rolling(20).std().iloc[-1] * math.sqrt(252)
        
        # Add premium for implied over historical
        iv_premium = 1.1  # 10% premium
        
        return hv * iv_premium
    
    def _calculate_iv_rank(self, current_iv: float) -> float:
        """Calculate IV rank (simplified)"""
        # Would use historical IV data
        # For now, use normalized value
        mean_iv = 0.15
        std_iv = 0.05
        
        z_score = (current_iv - mean_iv) / std_iv
        # Convert to 0-100 scale
        iv_rank = 50 + z_score * 20
        
        return max(0, min(100, iv_rank))
    
    def _calculate_iv_percentile(self, current_iv: float) -> float:
        """Calculate IV percentile (simplified)"""
        # Would use historical IV data
        return self._calculate_iv_rank(current_iv)  # Same as rank for now
    
    def _get_term_structure(self) -> Dict[int, float]:
        """Get volatility term structure"""
        # Simplified term structure
        base_vol = self.volatility_analysis.current_iv if self.volatility_analysis else 0.15
        
        term_structure = {
            7: base_vol * 1.1,    # Short-term premium
            14: base_vol * 1.05,
            30: base_vol,
            45: base_vol * 0.98,
            60: base_vol * 0.95
        }
        
        return term_structure
    
    def _get_volatility_smile(self, current_price: float) -> Dict[float, float]:
        """Get volatility smile"""
        # Simplified smile
        atm_vol = self.volatility_analysis.current_iv if self.volatility_analysis else 0.15
        
        smile = {}
        for pct in [-10, -5, -2, 0, 2, 5, 10]:
            strike = current_price * (1 + pct / 100)
            # Higher vol for OTM options
            skew = abs(pct) * 0.002
            smile[strike] = atm_vol + skew
        
        return smile
    
    def _get_upcoming_events(self) -> List[MarketEvent]:
        """Get upcoming market events"""
        events = []
        
        # Check earnings (would use actual earnings calendar)
        next_earnings = datetime.now() + timedelta(days=30)
        events.append(MarketEvent(
            event_type=EventType.EARNINGS,
            event_date=next_earnings,
            expected_impact='high',
            description='SPY component earnings'
        ))
        
        # Check FOMC (would use actual calendar)
        next_fomc = self.trading_calendar.get_next_fomc_date()
        if next_fomc and (next_fomc - datetime.now()).days <= 45:
            events.append(MarketEvent(
                event_type=EventType.FOMC,
                event_date=next_fomc,
                expected_impact='high',
                description='FOMC meeting'
            ))
        
        # Check economic data
        # CPI typically released around 12th of month
        next_month = datetime.now().replace(day=12) + timedelta(days=30)
        events.append(MarketEvent(
            event_type=EventType.ECONOMIC_DATA,
            event_date=next_month,
            expected_impact='medium',
            description='CPI release'
        ))
        
        return sorted(events, key=lambda x: x.event_date)
    
    def _check_term_structure_opportunity(self) -> bool:
        """Check for term structure trading opportunity"""
        if not self.volatility_analysis:
            return False
        
        term_structure = self.volatility_analysis.term_structure
        
        # Look for inverted term structure
        if term_structure.get(7, 0) > term_structure.get(30, 0) * 1.2:
            return True
        
        # Look for steep term structure
        if term_structure.get(45, 0) < term_structure.get(7, 0) * 0.8:
            return True
        
        return False
    
    def _find_optimal_expiration(self) -> Optional[datetime]:
        """Find optimal expiration date"""
        if not self.volatility_analysis:
            return None
        
        # Check for upcoming events
        high_impact_events = [e for e in self.volatility_analysis.upcoming_events 
                            if e.expected_impact == 'high']
        
        if high_impact_events and self.trade_events:
            # Trade the event
            event_date = high_impact_events[0].event_date
            # Find expiration just after event
            days_after_event = 2
            target_date = event_date + timedelta(days=days_after_event)
        else:
            # Use target DTE
            target_date = datetime.now() + timedelta(days=self.target_dte)
        
        # Find nearest expiration
        return self.trading_calendar.get_next_expiration_after(target_date)
    
    def _find_strike_by_delta(
        self,
        spot: float,
        target_delta: float,
        option_type: OptionType,
        time: float,
        volatility: float
    ) -> float:
        """Find strike for target delta"""
        risk_free_rate = 0.05
        
        # Binary search for strike
        if option_type == OptionType.CALL:
            low_strike = spot * 0.9
            high_strike = spot * 1.1
        else:
            low_strike = spot * 0.9
            high_strike = spot * 1.1
        
        for _ in range(20):  # Max iterations
            mid_strike = (low_strike + high_strike) / 2
            
            delta = self.greeks_calculator.delta(
                spot, mid_strike, time,
                risk_free_rate, volatility, option_type
            )
            
            if abs(delta - target_delta) < 0.01:
                return round(mid_strike)
            
            if option_type == OptionType.CALL:
                if delta > target_delta:
                    low_strike = mid_strike
                else:
                    high_strike = mid_strike
            else:
                if delta < target_delta:
                    high_strike = mid_strike
                else:
                    low_strike = mid_strike
        
        return round(mid_strike)
    
    def _validate_setup(self, setup: VolatilitySetup) -> bool:
        """Validate volatility setup"""
        # Check minimum expected move
        if setup.expected_move < MIN_EXPECTED_MOVE * setup.call_strike:
            return False
        
        # Check Greeks
        if setup.vega < MIN_VEGA:
            return False
        
        if setup.theta < MAX_THETA_DECAY:
            return False
        
        if setup.gamma < MIN_GAMMA:
            return False
        
        # Check breakevens are reasonable
        breakeven_width = (setup.breakeven_up - setup.breakeven_down) / setup.call_strike
        if breakeven_width > 0.10:  # More than 10% move needed
            return False
        
        return True
    
    def _calculate_setup_score(self, setup: VolatilitySetup) -> float:
        """Calculate setup quality score"""
        score = 0.0
        
        # IV rank component (0-0.3)
        if 20 <= setup.vol_rank <= 35:
            score += 0.3
        elif 35 < setup.vol_rank <= 50:
            score += 0.2
        else:
            score += 0.1
        
        # Expected move vs breakeven (0-0.3)
        move_ratio = setup.expected_move / ((setup.breakeven_up - setup.breakeven_down) / 2)
        if move_ratio > 1.5:
            score += 0.3
        elif move_ratio > 1.2:
            score += 0.2
        else:
            score += 0.1
        
        # Greeks component (0-0.2)
        if setup.vega > 0.20 and setup.gamma > 0.02:
            score += 0.2
        elif setup.vega > 0.15 and setup.gamma > 0.015:
            score += 0.15
        else:
            score += 0.1
        
        # IV/HV ratio (0-0.2)
        if self.volatility_analysis:
            if self.volatility_analysis.iv_hv_ratio < 0.9:
                score += 0.2
            elif self.volatility_analysis.iv_hv_ratio < 1.1:
                score += 0.15
            else:
                score += 0.1
        
        return min(score, 1.0)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test straddle/strangle strategy
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    # Initialize components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.02
    )
    
    # Create strategy
    strategy = StraddleStrategy(
        event_manager=event_manager,
        risk_profile=risk_profile,
        config={
            'use_straddles': True,
            'use_strangles': True,
            'trade_events': True,
            'max_positions': 2,
            'target_dte': 30
        }
    )
    
    # Start strategy
    strategy.start()
    
    # Create sample market data with low volatility setup
    dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
    base_price = 450
    
    # Low volatility period
    returns = np.random.randn(100) * 0.005  # 0.5% daily vol
    prices = base_price * np.exp(np.cumsum(returns))
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.randn(100) * 0.001),
        'high': prices * (1 + abs(np.random.randn(100) * 0.002)),
        'low': prices * (1 - abs(np.random.randn(100) * 0.002)),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Process market data
    signals = strategy.generate_signals(market_data)
    
    # Print results
    print(f"Strategy: {strategy.name}")
    
    if strategy.volatility_analysis:
        print(f"\nVolatility Analysis:")
        print(f"Current IV: {strategy.volatility_analysis.current_iv:.2%}")
        print(f"IV Rank: {strategy.volatility_analysis.iv_rank:.0f}")
        print(f"HV20: {strategy.volatility_analysis.hv_20:.2%}")
        print(f"IV/HV Ratio: {strategy.volatility_analysis.iv_hv_ratio:.2f}")
        print(f"Volatility Regime: {strategy.volatility_analysis.volatility_regime.name}")
        print(f"Upcoming Events: {len(strategy.volatility_analysis.upcoming_events)}")
    
    print(f"\nSignals Generated: {len(signals)}")
    
    for signal in signals:
        print(f"\nSignal Type: {signal.metadata.get('strategy_type')}")
        print(f"Call Strike: ${signal.contracts[0].strike}")
        print(f"Put Strike: ${signal.contracts[1].strike}")
        print(f"Total Premium: ${signal.metadata.get('total_premium', 0):.2f}")
        print(f"Breakeven Up: ${signal.metadata.get('breakeven_up', 0):.2f}")
        print(f"Breakeven Down: ${signal.metadata.get('breakeven_down', 0):.2f}")
        print(f"Expected Move: ${signal.metadata.get('expected_move', 0):.2f}")
        print(f"Vega: {signal.metadata.get('vega', 0):.3f}")
        print(f"Gamma: {signal.metadata.get('gamma', 0):.3f}")
        print(f"Theta: ${signal.metadata.get('theta', 0):.2f}")
        print(f"Signal Strength: {signal.strength.name}")
    
    # Stop strategy
    strategy.stop()
            