#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC11_FuturesBasis.py
Group: C (Market Data)
Purpose: ES/SPY basis analysis and arbitrage opportunities

Description:
    This module analyzes the basis between ES futures and SPY ETF to identify
    arbitrage opportunities, fair value calculations, and market inefficiencies.
    It provides real-time basis monitoring, dividend tracking, interest rate
    adjustments, and automated alerts for profitable trading opportunities.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last Updated: 2025-07-01 Time: 15:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
import bisect
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set, Deque
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import warnings
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
from scipy import stats, optimize
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderB_Broker.SpyderB01_SpyderClient import IBClient
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeed
from SpyderC_MarketData.SpyderC02_HistoricalData import HistoricalDataManager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# ES Futures specifications
ES_MULTIPLIER = 50  # ES futures multiplier
ES_TICK_SIZE = 0.25  # Minimum tick size
ES_TICK_VALUE = 12.50  # Value per tick

# SPY specifications
SPY_MULTIPLIER = 1  # SPY ETF multiplier
SPY_TICK_SIZE = 0.01  # Minimum tick size

# Contract specifications
ES_CONTRACT_MONTHS = ['H', 'M', 'U', 'Z']  # Mar, Jun, Sep, Dec
ES_EXPIRATION_OFFSET = 3  # Business days before 3rd Friday

# Basis calculation parameters
RISK_FREE_RATE_DEFAULT = 0.05  # Default risk-free rate (5%)
DIVIDEND_YIELD_DEFAULT = 0.015  # Default SPY dividend yield (1.5%)
COST_OF_CARRY_ADJUSTMENT = 0.0001  # Adjustment for trading costs

# Arbitrage thresholds
MIN_BASIS_POINTS = 2.0  # Minimum 2 basis points for arbitrage
MAX_BASIS_POINTS = 50.0  # Maximum expected basis
TRANSACTION_COSTS = 0.05  # Total transaction costs per side
MIN_PROFIT_THRESHOLD = 0.10  # Minimum profit threshold

# Update frequencies
BASIS_UPDATE_FREQUENCY = 1  # seconds
FAIR_VALUE_UPDATE_FREQUENCY = 5  # seconds
DIVIDEND_UPDATE_FREQUENCY = 3600  # 1 hour
INTEREST_RATE_UPDATE_FREQUENCY = 300  # 5 minutes

# Historical data
HISTORICAL_BASIS_DAYS = 252  # 1 year of basis history
VOLATILITY_WINDOW = 20  # 20-day volatility window

# ==============================================================================
# ENUMS
# ==============================================================================
class BasisDirection(Enum):
    """Basis direction relative to fair value"""
    POSITIVE = "positive"           # ES > Fair Value
    NEGATIVE = "negative"           # ES < Fair Value
    FAIR = "fair"                  # ES ≈ Fair Value

class ArbitrageOpportunity(Enum):
    """Types of arbitrage opportunities"""
    BUY_ES_SELL_SPY = "buy_es_sell_spy"      # ES undervalued
    SELL_ES_BUY_SPY = "sell_es_buy_spy"      # ES overvalued
    NO_OPPORTUNITY = "no_opportunity"         # No profitable arbitrage
    INSUFFICIENT_EDGE = "insufficient_edge"   # Edge too small

class BasisRegime(Enum):
    """Basis trading regimes"""
    CONVERGENCE = "convergence"       # Normal convergence to expiration
    DIVERGENCE = "divergence"         # Unusual divergence from fair value
    VOLATILE = "volatile"             # High basis volatility
    STABLE = "stable"                 # Low basis volatility
    ANOMALY = "anomaly"              # Statistical anomaly

class MarketSession(Enum):
    """Trading session types"""
    PRE_MARKET = "pre_market"         # 4:00-9:30 ET
    REGULAR = "regular"               # 9:30-16:00 ET
    AFTER_HOURS = "after_hours"       # 16:00-20:00 ET
    OVERNIGHT = "overnight"           # 20:00-4:00 ET

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ESFuturesData:
    """ES futures data point"""
    timestamp: datetime
    contract_month: str
    expiration_date: date
    price: float
    bid: float
    ask: float
    volume: int
    open_interest: int
    settlement: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None

@dataclass
class SPYData:
    """SPY ETF data point"""
    timestamp: datetime
    price: float
    bid: float
    ask: float
    volume: int
    nav: Optional[float] = None  # Net Asset Value
    premium_discount: Optional[float] = None
    dividend_yield: Optional[float] = None

@dataclass
class BasisData:
    """Basis calculation data"""
    timestamp: datetime
    es_price: float
    spy_price: float
    raw_basis: float
    fair_value_basis: float
    basis_points: float
    direction: BasisDirection
    days_to_expiry: int
    interest_rate: float
    dividend_yield: float
    cost_of_carry: float

@dataclass
class FairValueCalculation:
    """Fair value calculation components"""
    timestamp: datetime
    spy_price: float
    interest_rate: float
    dividend_yield: float
    days_to_expiry: int
    time_to_expiry: float
    interest_adjustment: float
    dividend_adjustment: float
    fair_value: float
    theoretical_es_price: float

@dataclass
class ArbitrageSignal:
    """Arbitrage opportunity signal"""
    timestamp: datetime
    opportunity_type: ArbitrageOpportunity
    expected_profit: float
    profit_bps: float
    confidence_score: float
    risk_score: float
    entry_price_es: float
    entry_price_spy: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    max_holding_period: Optional[int] = None  # minutes

@dataclass
class BasisStatistics:
    """Basis statistical analysis"""
    timestamp: datetime
    mean_basis: float
    std_basis: float
    percentile_5: float
    percentile_95: float
    current_percentile: float
    zscore: float
    volatility: float
    autocorrelation: float
    mean_reversion_half_life: float

@dataclass
class DividendSchedule:
    """SPY dividend schedule"""
    ex_date: date
    payment_date: date
    amount: float
    yield_impact: float
    days_to_ex_date: int
    adjustment_factor: float

@dataclass
class BasisMonitoringAlert:
    """Basis monitoring alert"""
    timestamp: datetime
    alert_type: str
    severity: str  # INFO, WARNING, CRITICAL
    message: str
    current_basis: float
    threshold_breached: float
    recommended_action: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class FuturesBasisAnalyzer:
    """
    ES/SPY basis analysis system for arbitrage opportunity detection,
    fair value calculations, and real-time monitoring.
    """
    
    def __init__(self, ib_client: Optional[IBClient] = None, config: Optional[Dict] = None):
        """
        Initialize futures basis analyzer.
        
        Args:
            ib_client: Interactive Brokers client for live data
            config: Configuration dictionary
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.datetime_utils = DateTimeUtils()
        self.trading_calendar = TradingCalendar()
        
        # Configuration
        self.config = config or {}
        self.ib_client = ib_client
        
        # Data storage
        self.current_es_data: Optional[ESFuturesData] = None
        self.current_spy_data: Optional[SPYData] = None
        self.current_basis: Optional[BasisData] = None
        self.basis_history: deque = deque(maxlen=HISTORICAL_BASIS_DAYS * 1440)  # Minute data
        
        # Market data components
        self.data_feed = DataFeed(ib_client) if ib_client else None
        self.historical_manager = HistoricalDataManager(ib_client) if ib_client else None
        
        # Analysis components
        self.fair_value_calculator = FairValueCalculator()
        self.arbitrage_detector = ArbitrageDetector()
        self.basis_statistics = BasisStatisticsCalculator()
        self.dividend_tracker = DividendTracker()
        
        # State tracking
        self.is_running = False
        self.last_update = None
        self.update_thread = None
        self.current_session = MarketSession.REGULAR
        
        # Market parameters
        self.risk_free_rate = RISK_FREE_RATE_DEFAULT
        self.dividend_yield = DIVIDEND_YIELD_DEFAULT
        self.next_dividend = None
        
        # Performance tracking
        self.arbitrage_signals: deque = deque(maxlen=1000)
        self.alert_history: deque = deque(maxlen=500)
        
        # Initialize
        self._initialize_market_parameters()
        self._load_historical_basis_data()
        
        self.logger.info("Futures Basis Analyzer initialized successfully")

    # ==========================================================================
    # PUBLIC METHODS - DATA UPDATES
    # ==========================================================================
    
    def start_real_time_monitoring(self) -> None:
        """Start real-time basis monitoring"""
        if self.is_running:
            self.logger.warning("Basis monitoring already running")
            return
            
        self.is_running = True
        self.update_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.update_thread.start()
        
        self.logger.info("Started real-time basis monitoring")

    def stop_real_time_monitoring(self) -> None:
        """Stop real-time basis monitoring"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5.0)
        
        self.logger.info("Stopped real-time basis monitoring")

    def update_market_data(self) -> Tuple[ESFuturesData, SPYData]:
        """
        Update ES and SPY market data.
        
        Returns:
            Tuple of (ES data, SPY data)
        """
        try:
            # Update ES futures data
            if self.ib_client:
                es_data = self._fetch_live_es_data()
                spy_data = self._fetch_live_spy_data()
            else:
                es_data = self._fetch_simulated_es_data()
                spy_data = self._fetch_simulated_spy_data()
            
            self.current_es_data = es_data
            self.current_spy_data = spy_data
            self.last_update = datetime.now()
            
            # Calculate basis
            self._calculate_current_basis()
            
            # Emit update event
            self.event_manager.emit_event(Event(
                type=EventType.DATA_UPDATE,
                source=self.__class__.__name__,
                data={
                    'es_data': es_data,
                    'spy_data': spy_data,
                    'basis': self.current_basis
                }
            ))
            
            return es_data, spy_data
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_market_data")
            raise

    def calculate_fair_value(self) -> FairValueCalculation:
        """
        Calculate theoretical fair value for ES futures.
        
        Returns:
            Fair value calculation
        """
        if not self.current_spy_data:
            raise ValueError("No SPY data available for fair value calculation")
        
        try:
            fair_value = self.fair_value_calculator.calculate(
                spy_price=self.current_spy_data.price,
                interest_rate=self.risk_free_rate,
                dividend_yield=self.dividend_yield,
                days_to_expiry=self._get_days_to_expiry(),
                next_dividend=self.next_dividend
            )
            
            return fair_value
            
        except Exception as e:
            self.error_handler.handle_error(e, "calculate_fair_value")
            raise

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    
    def detect_arbitrage_opportunities(self) -> List[ArbitrageSignal]:
        """
        Detect arbitrage opportunities.
        
        Returns:
            List of arbitrage signals
        """
        if not all([self.current_es_data, self.current_spy_data, self.current_basis]):
            return []
        
        try:
            opportunities = self.arbitrage_detector.detect(
                es_data=self.current_es_data,
                spy_data=self.current_spy_data,
                basis_data=self.current_basis,
                fair_value=self.calculate_fair_value(),
                historical_basis=list(self.basis_history)
            )
            
            # Store signals
            self.arbitrage_signals.extend(opportunities)
            
            # Emit signals
            for signal in opportunities:
                if signal.opportunity_type != ArbitrageOpportunity.NO_OPPORTUNITY:
                    self._emit_arbitrage_signal(signal)
            
            return opportunities
            
        except Exception as e:
            self.error_handler.handle_error(e, "detect_arbitrage_opportunities")
            return []

    def analyze_basis_regime(self) -> BasisRegime:
        """
        Analyze current basis trading regime.
        
        Returns:
            Current basis regime
        """
        if len(self.basis_history) < 100:
            return BasisRegime.STABLE
        
        try:
            # Calculate regime metrics
            recent_basis = [b.basis_points for b in list(self.basis_history)[-60:]]  # Last hour
            recent_volatility = np.std(recent_basis)
            
            # Get statistical analysis
            stats = self.basis_statistics.calculate(list(self.basis_history))
            
            # Determine regime
            if abs(stats.zscore) > 3.0:
                return BasisRegime.ANOMALY
            elif recent_volatility > stats.std_basis * 2:
                return BasisRegime.VOLATILE
            elif abs(stats.current_percentile - 50) > 40:
                return BasisRegime.DIVERGENCE
            elif recent_volatility < stats.std_basis * 0.5:
                return BasisRegime.STABLE
            else:
                return BasisRegime.CONVERGENCE
                
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_basis_regime")
            return BasisRegime.STABLE

    def get_basis_statistics(self) -> BasisStatistics:
        """
        Get comprehensive basis statistics.
        
        Returns:
            Basis statistics
        """
        if len(self.basis_history) < 20:
            raise ValueError("Insufficient basis history for statistics")
        
        try:
            return self.basis_statistics.calculate(list(self.basis_history))
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_basis_statistics")
            raise

    def check_dividend_impact(self) -> Dict[str, Any]:
        """
        Check upcoming dividend impact on basis.
        
        Returns:
            Dividend impact analysis
        """
        try:
            dividend_info = self.dividend_tracker.get_next_dividend_info()
            
            if not dividend_info:
                return {'has_upcoming_dividend': False}
            
            # Calculate impact
            days_to_ex = dividend_info.days_to_ex_date
            impact_on_basis = dividend_info.amount * dividend_info.adjustment_factor
            
            return {
                'has_upcoming_dividend': True,
                'ex_date': dividend_info.ex_date,
                'days_to_ex_date': days_to_ex,
                'dividend_amount': dividend_info.amount,
                'estimated_basis_impact': impact_on_basis,
                'yield_impact': dividend_info.yield_impact,
                'recommended_action': self._get_dividend_trading_recommendation(dividend_info)
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "check_dividend_impact")
            return {'has_upcoming_dividend': False, 'error': str(e)}

    # ==========================================================================
    # PUBLIC METHODS - UTILITY
    # ==========================================================================
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive monitoring summary.
        
        Returns:
            Dictionary containing monitoring summary
        """
        if not all([self.current_es_data, self.current_spy_data, self.current_basis]):
            return {'status': 'insufficient_data'}
        
        try:
            fair_value = self.calculate_fair_value()
            regime = self.analyze_basis_regime()
            opportunities = self.detect_arbitrage_opportunities()
            dividend_info = self.check_dividend_impact()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'es_price': f"{self.current_es_data.price:.2f}",
                'spy_price': f"{self.current_spy_data.price:.2f}",
                'raw_basis': f"{self.current_basis.raw_basis:.2f}",
                'fair_value_basis': f"{self.current_basis.fair_value_basis:.2f}",
                'basis_points': f"{self.current_basis.basis_points:.1f}",
                'basis_direction': self.current_basis.direction.value,
                'days_to_expiry': self.current_basis.days_to_expiry,
                'fair_value': f"{fair_value.fair_value:.2f}",
                'theoretical_es': f"{fair_value.theoretical_es_price:.2f}",
                'regime': regime.value,
                'arbitrage_opportunities': len([o for o in opportunities 
                                               if o.opportunity_type != ArbitrageOpportunity.NO_OPPORTUNITY]),
                'best_opportunity': opportunities[0].opportunity_type.value if opportunities else 'none',
                'expected_profit_bps': f"{opportunities[0].profit_bps:.1f}" if opportunities else "0.0",
                'dividend_impact': dividend_info,
                'session': self.current_session.value,
                'last_update': self.last_update.isoformat() if self.last_update else None
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_monitoring_summary")
            return {'status': 'error', 'message': str(e)}

    def get_historical_performance(self, days: int = 30) -> Dict[str, Any]:
        """
        Get historical arbitrage performance.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Historical performance metrics
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            recent_signals = [s for s in self.arbitrage_signals 
                            if s.timestamp >= cutoff_time]
            
            if not recent_signals:
                return {'period_days': days, 'total_signals': 0}
            
            # Calculate performance metrics
            total_signals = len(recent_signals)
            profitable_signals = len([s for s in recent_signals if s.expected_profit > 0])
            avg_profit_bps = np.mean([s.profit_bps for s in recent_signals])
            max_profit_bps = max([s.profit_bps for s in recent_signals])
            
            # Signal distribution
            signal_types = {}
            for signal in recent_signals:
                signal_type = signal.opportunity_type.value
                signal_types[signal_type] = signal_types.get(signal_type, 0) + 1
            
            return {
                'period_days': days,
                'total_signals': total_signals,
                'profitable_signals': profitable_signals,
                'success_rate': f"{(profitable_signals/total_signals)*100:.1f}%" if total_signals > 0 else "0%",
                'avg_profit_bps': f"{avg_profit_bps:.2f}",
                'max_profit_bps': f"{max_profit_bps:.2f}",
                'signal_distribution': signal_types,
                'daily_avg_signals': f"{total_signals/days:.1f}"
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "get_historical_performance")
            return {'error': str(e)}

    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    
    def _fetch_live_es_data(self) -> ESFuturesData:
        """Fetch live ES futures data from IB"""
        # Implementation for live ES data fetching
        # This would use the IB client to get real ES futures data
        pass

    def _fetch_live_spy_data(self) -> SPYData:
        """Fetch live SPY data from IB"""
        # Implementation for live SPY data fetching
        pass

    def _fetch_simulated_es_data(self) -> ESFuturesData:
        """Generate simulated ES futures data for testing"""
        base_price = 4500.0
        if self.current_es_data:
            base_price = self.current_es_data.price
        
        # Simple random walk
        change = np.random.normal(0, 2.5)
        new_price = base_price + change
        
        return ESFuturesData(
            timestamp=datetime.now(),
            contract_month='M',  # June contract
            expiration_date=date(2025, 6, 20),
            price=new_price,
            bid=new_price - 0.25,
            ask=new_price + 0.25,
            volume=np.random.randint(10000, 50000),
            open_interest=np.random.randint(500000, 1000000),
            change=change,
            change_pct=(change / base_price) * 100
        )

    def _fetch_simulated_spy_data(self) -> SPYData:
        """Generate simulated SPY data for testing"""
        # SPY price should be approximately ES/50
        if self.current_es_data:
            base_spy = self.current_es_data.price / ES_MULTIPLIER
        else:
            base_spy = 450.0
        
        # Add small random variation
        change = np.random.normal(0, 0.05)
        new_price = base_spy + change
        
        return SPYData(
            timestamp=datetime.now(),
            price=new_price,
            bid=new_price - 0.01,
            ask=new_price + 0.01,
            volume=np.random.randint(1000000, 5000000),
            nav=new_price * 1.0001,  # Slight premium to NAV
            premium_discount=0.0001,
            dividend_yield=self.dividend_yield
        )

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    
    def _calculate_current_basis(self) -> None:
        """Calculate current basis between ES and SPY"""
        if not all([self.current_es_data, self.current_spy_data]):
            return
        
        try:
            # Calculate raw basis (ES - SPY*50)
            spy_equivalent = self.current_spy_data.price * ES_MULTIPLIER
            raw_basis = self.current_es_data.price - spy_equivalent
            
            # Calculate fair value basis
            fair_value = self.calculate_fair_value()
            fair_value_basis = self.current_es_data.price - fair_value.theoretical_es_price
            
            # Convert to basis points
            basis_points = (fair_value_basis / spy_equivalent) * 10000
            
            # Determine direction
            if abs(basis_points) < 1.0:
                direction = BasisDirection.FAIR
            elif basis_points > 0:
                direction = BasisDirection.POSITIVE
            else:
                direction = BasisDirection.NEGATIVE
            
            # Create basis data
            self.current_basis = BasisData(
                timestamp=datetime.now(),
                es_price=self.current_es_data.price,
                spy_price=self.current_spy_data.price,
                raw_basis=raw_basis,
                fair_value_basis=fair_value_basis,
                basis_points=basis_points,
                direction=direction,
                days_to_expiry=self._get_days_to_expiry(),
                interest_rate=self.risk_free_rate,
                dividend_yield=self.dividend_yield,
                cost_of_carry=self._calculate_cost_of_carry()
            )
            
            # Add to history
            self.basis_history.append(self.current_basis)
            
        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_current_basis")

    def _get_days_to_expiry(self) -> int:
        """Get days to ES futures expiry"""
        if not self.current_es_data:
            return 30  # Default
        
        today = date.today()
        return (self.current_es_data.expiration_date - today).days

    def _calculate_cost_of_carry(self) -> float:
        """Calculate cost of carry"""
        return self.risk_free_rate - self.dividend_yield + COST_OF_CARRY_ADJUSTMENT

    def _get_dividend_trading_recommendation(self, dividend_info: DividendSchedule) -> str:
        """Get trading recommendation based on dividend timing"""
        days_to_ex = dividend_info.days_to_ex_date
        
        if days_to_ex <= 1:
            return "AVOID_NEW_POSITIONS"
        elif days_to_ex <= 3:
            return "CLOSE_LONG_SPY_POSITIONS"
        elif days_to_ex <= 7:
            return "MONITOR_BASIS_CLOSELY"
        else:
            return "NORMAL_TRADING"

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    
    def _initialize_market_parameters(self) -> None:
        """Initialize market parameters"""
        try:
            # Update interest rates
            self._update_interest_rates()
            
            # Update dividend information
            self.dividend_tracker.update_dividend_schedule()
            self.next_dividend = self.dividend_tracker.get_next_dividend_info()
            
            # Determine current session
            self.current_session = self._determine_market_session()
            
        except Exception as e:
            self.error_handler.handle_error(e, "_initialize_market_parameters")

    def _load_historical_basis_data(self) -> None:
        """Load historical basis data"""
        try:
            if self.historical_manager:
                # Load from database in real implementation
                pass
            else:
                # Generate sample historical data for testing
                for i in range(1000):
                    # Simulate historical basis
                    timestamp = datetime.now() - timedelta(minutes=i)
                    basis_points = np.random.normal(0, 5)  # Historical mean ~0, std ~5 bps
                    
                    basis_data = BasisData(
                        timestamp=timestamp,
                        es_price=4500 + np.random.normal(0, 20),
                        spy_price=450 + np.random.normal(0, 2),
                        raw_basis=np.random.normal(0, 1),
                        fair_value_basis=np.random.normal(0, 0.5),
                        basis_points=basis_points,
                        direction=BasisDirection.FAIR,
                        days_to_expiry=30,
                        interest_rate=self.risk_free_rate,
                        dividend_yield=self.dividend_yield,
                        cost_of_carry=self._calculate_cost_of_carry()
                    )
                    
                    self.basis_history.appendleft(basis_data)
                    
        except Exception as e:
            self.error_handler.handle_error(e, "_load_historical_basis_data")

    def _update_interest_rates(self) -> None:
        """Update current interest rates"""
        # In real implementation, would fetch from Fed/market data
        # For now, use default
        self.risk_free_rate = RISK_FREE_RATE_DEFAULT

    def _determine_market_session(self) -> MarketSession:
        """Determine current market session"""
        now = datetime.now().time()
        
        if datetime.time(4, 0) <= now < datetime.time(9, 30):
            return MarketSession.PRE_MARKET
        elif datetime.time(9, 30) <= now < datetime.time(16, 0):
            return MarketSession.REGULAR
        elif datetime.time(16, 0) <= now < datetime.time(20, 0):
            return MarketSession.AFTER_HOURS
        else:
            return MarketSession.OVERNIGHT

    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.is_running:
            try:
                # Update market data
                self.update_market_data()
                
                # Check for arbitrage opportunities
                opportunities = self.detect_arbitrage_opportunities()
                
                # Check for alerts
                self._check_monitoring_alerts()
                
                # Update market parameters periodically
                if (not self.last_update or 
                    (datetime.now() - self.last_update).seconds >= INTEREST_RATE_UPDATE_FREQUENCY):
                    self._update_interest_rates()
                
                time.sleep(BASIS_UPDATE_FREQUENCY)
                
            except Exception as e:
                self.error_handler.handle_error(e, "_monitoring_loop")
                time.sleep(10)  # Wait longer on error

    def _check_monitoring_alerts(self) -> None:
        """Check for monitoring alerts"""
        if not self.current_basis:
            return
        
        try:
            alerts = []
            
            # Extreme basis alert
            if abs(self.current_basis.basis_points) > 20:
                alerts.append(BasisMonitoringAlert(
                    timestamp=datetime.now(),
                    alert_type="EXTREME_BASIS",
                    severity="WARNING",
                    message=f"Extreme basis detected: {self.current_basis.basis_points:.1f} bps",
                    current_basis=self.current_basis.basis_points,
                    threshold_breached=20.0,
                    recommended_action="INVESTIGATE_ARBITRAGE"
                ))
            
            # Arbitrage opportunity alert
            opportunities = self.detect_arbitrage_opportunities()
            profitable_ops = [o for o in opportunities 
                            if o.opportunity_type != ArbitrageOpportunity.NO_OPPORTUNITY 
                            and o.profit_bps > MIN_PROFIT_THRESHOLD]
            
            if profitable_ops:
                best_op = max(profitable_ops, key=lambda x: x.profit_bps)
                alerts.append(BasisMonitoringAlert(
                    timestamp=datetime.now(),
                    alert_type="ARBITRAGE_OPPORTUNITY",
                    severity="INFO",
                    message=f"Arbitrage opportunity: {best_op.opportunity_type.value} ({best_op.profit_bps:.1f} bps)",
                    current_basis=self.current_basis.basis_points,
                    threshold_breached=MIN_PROFIT_THRESHOLD,
                    recommended_action=best_op.opportunity_type.value.upper()
                ))
            
            # Store and emit alerts
            for alert in alerts:
                self.alert_history.append(alert)
                self._emit_monitoring_alert(alert)
                
        except Exception as e:
            self.error_handler.handle_error(e, "_check_monitoring_alerts")

    def _emit_arbitrage_signal(self, signal: ArbitrageSignal) -> None:
        """Emit arbitrage signal event"""
        event_data = {
            'opportunity_type': signal.opportunity_type.value,
            'expected_profit': signal.expected_profit,
            'profit_bps': signal.profit_bps,
            'confidence_score': signal.confidence_score,
            'entry_price_es': signal.entry_price_es,
            'entry_price_spy': signal.entry_price_spy
        }
        
        self.event_manager.emit_event(Event(
            type=EventType.SIGNAL_GENERATED,
            source=self.__class__.__name__,
            data=event_data
        ))

    def _emit_monitoring_alert(self, alert: BasisMonitoringAlert) -> None:
        """Emit monitoring alert event"""
        event_data = {
            'alert_type': alert.alert_type,
            'severity': alert.severity,
            'message': alert.message,
            'recommended_action': alert.recommended_action
        }
        
        self.event_manager.emit_event(Event(
            type=EventType.ALERT_GENERATED,
            source=self.__class__.__name__,
            data=event_data
        ))

# ==============================================================================
# HELPER CLASSES
# ==============================================================================
class FairValueCalculator:
    """Fair value calculation for ES futures"""
    
    def calculate(self, spy_price: float, interest_rate: float, 
                 dividend_yield: float, days_to_expiry: int,
                 next_dividend: Optional[DividendSchedule] = None) -> FairValueCalculation:
        """Calculate theoretical fair value"""
        
        # Time to expiry in years
        time_to_expiry = days_to_expiry / 365.0
        
        # Interest adjustment (compound interest)
        interest_adjustment = spy_price * (math.exp(interest_rate * time_to_expiry) - 1)
        
        # Dividend adjustment
        dividend_adjustment = 0.0
        if next_dividend and next_dividend.days_to_ex_date <= days_to_expiry:
            # Present value of known dividend
            days_to_dividend = next_dividend.days_to_ex_date
            time_to_dividend = days_to_dividend / 365.0
            dividend_pv = next_dividend.amount * math.exp(-interest_rate * time_to_dividend)
            dividend_adjustment = dividend_pv
        else:
            # Estimated dividend yield
            dividend_adjustment = spy_price * dividend_yield * time_to_expiry
        
        # Fair value calculation
        fair_value = spy_price + interest_adjustment - dividend_adjustment
        theoretical_es_price = fair_value * ES_MULTIPLIER
        
        return FairValueCalculation(
            timestamp=datetime.now(),
            spy_price=spy_price,
            interest_rate=interest_rate,
            dividend_yield=dividend_yield,
            days_to_expiry=days_to_expiry,
            time_to_expiry=time_to_expiry,
            interest_adjustment=interest_adjustment,
            dividend_adjustment=dividend_adjustment,
            fair_value=fair_value,
            theoretical_es_price=theoretical_es_price
        )


class ArbitrageDetector:
    """Arbitrage opportunity detection"""
    
    def detect(self, es_data: ESFuturesData, spy_data: SPYData,
              basis_data: BasisData, fair_value: FairValueCalculation,
              historical_basis: List[BasisData]) -> List[ArbitrageSignal]:
        """Detect arbitrage opportunities"""
        
        signals = []
        
        # Calculate mispricing
        theoretical_es = fair_value.theoretical_es_price
        actual_es = es_data.price
        mispricing = actual_es - theoretical_es
        mispricing_bps = (mispricing / (spy_data.price * ES_MULTIPLIER)) * 10000
        
        # Check if mispricing exceeds threshold
        if abs(mispricing_bps) < MIN_BASIS_POINTS:
            signals.append(ArbitrageSignal(
                timestamp=datetime.now(),
                opportunity_type=ArbitrageOpportunity.NO_OPPORTUNITY,
                expected_profit=0.0,
                profit_bps=0.0,
                confidence_score=0.0,
                risk_score=0.0,
                entry_price_es=es_data.price,
                entry_price_spy=spy_data.price
            ))
            return signals
        
        # Determine opportunity type
        if mispricing > 0:  # ES overvalued
            opportunity_type = ArbitrageOpportunity.SELL_ES_BUY_SPY
        else:  # ES undervalued
            opportunity_type = ArbitrageOpportunity.BUY_ES_SELL_SPY
        
        # Calculate expected profit
        expected_profit = abs(mispricing) - TRANSACTION_COSTS
        profit_bps = abs(mispricing_bps) - (TRANSACTION_COSTS / (spy_data.price * ES_MULTIPLIER) * 10000)
        
        # Calculate confidence and risk scores
        confidence_score = self._calculate_confidence_score(mispricing_bps, historical_basis)
        risk_score = self._calculate_risk_score(es_data, spy_data, basis_data)
        
        # Check if profitable after costs
        if profit_bps > MIN_PROFIT_THRESHOLD:
            signals.append(ArbitrageSignal(
                timestamp=datetime.now(),
                opportunity_type=opportunity_type,
                expected_profit=expected_profit,
                profit_bps=profit_bps,
                confidence_score=confidence_score,
                risk_score=risk_score,
                entry_price_es=es_data.price,
                entry_price_spy=spy_data.price,
                take_profit=theoretical_es,
                max_holding_period=min(240, basis_data.days_to_expiry * 24 * 60)  # Max 4 hours or expiry
            ))
        else:
            signals.append(ArbitrageSignal(
                timestamp=datetime.now(),
                opportunity_type=ArbitrageOpportunity.INSUFFICIENT_EDGE,
                expected_profit=expected_profit,
                profit_bps=profit_bps,
                confidence_score=confidence_score,
                risk_score=risk_score,
                entry_price_es=es_data.price,
                entry_price_spy=spy_data.price
            ))
        
        return signals
    
    def _calculate_confidence_score(self, mispricing_bps: float, 
                                  historical_basis: List[BasisData]) -> float:
        """Calculate confidence score for arbitrage signal"""
        if len(historical_basis) < 50:
            return 0.5  # Medium confidence with limited data
        
        # Calculate historical statistics
        historical_bps = [b.basis_points for b in historical_basis[-252:]]  # Last year
        mean_basis = np.mean(historical_bps)
        std_basis = np.std(historical_bps)
        
        # Z-score of current mispricing
        if std_basis > 0:
            z_score = abs((mispricing_bps - mean_basis) / std_basis)
            # Higher z-score = higher confidence (more unusual = more likely to revert)
            confidence = min(0.95, z_score / 3.0)
        else:
            confidence = 0.5
        
        return confidence
    
    def _calculate_risk_score(self, es_data: ESFuturesData, spy_data: SPYData,
                            basis_data: BasisData) -> float:
        """Calculate risk score for arbitrage signal"""
        risk_factors = []
        
        # Volume risk (low volume = higher risk)
        if es_data.volume < 1000:
            risk_factors.append(0.3)
        elif es_data.volume < 5000:
            risk_factors.append(0.1)
        
        # Spread risk (wide spreads = higher risk)
        es_spread_bps = ((es_data.ask - es_data.bid) / es_data.price) * 10000
        spy_spread_bps = ((spy_data.ask - spy_data.bid) / spy_data.price) * 10000
        
        if es_spread_bps > 10 or spy_spread_bps > 5:
            risk_factors.append(0.2)
        
        # Time to expiry risk (close to expiry = higher risk)
        if basis_data.days_to_expiry < 5:
            risk_factors.append(0.4)
        elif basis_data.days_to_expiry < 15:
            risk_factors.append(0.2)
        
        # Calculate overall risk score
        base_risk = 0.1  # Base risk level
        additional_risk = sum(risk_factors)
        
        return min(0.9, base_risk + additional_risk)


class BasisStatisticsCalculator:
    """Basis statistics calculation"""
    
    def calculate(self, basis_history: List[BasisData]) -> BasisStatistics:
        """Calculate comprehensive basis statistics"""
        
        if len(basis_history) < 20:
            raise ValueError("Insufficient data for statistics calculation")
        
        # Extract basis points
        basis_points = [b.basis_points for b in basis_history]
        current_basis = basis_points[-1]
        
        # Basic statistics
        mean_basis = np.mean(basis_points)
        std_basis = np.std(basis_points)
        percentile_5 = np.percentile(basis_points, 5)
        percentile_95 = np.percentile(basis_points, 95)
        current_percentile = stats.percentileofscore(basis_points, current_basis)
        zscore = (current_basis - mean_basis) / std_basis if std_basis > 0 else 0
        
        # Volatility (rolling standard deviation)
        if len(basis_points) >= 20:
            recent_volatility = np.std(basis_points[-20:])
        else:
            recent_volatility = std_basis
        
        # Autocorrelation
        if len(basis_points) >= 50:
            autocorr = np.corrcoef(basis_points[:-1], basis_points[1:])[0, 1]
        else:
            autocorr = 0.0
        
        # Mean reversion half-life estimation
        half_life = self._calculate_mean_reversion_half_life(basis_points)
        
        return BasisStatistics(
            timestamp=datetime.now(),
            mean_basis=mean_basis,
            std_basis=std_basis,
            percentile_5=percentile_5,
            percentile_95=percentile_95,
            current_percentile=current_percentile,
            zscore=zscore,
            volatility=recent_volatility,
            autocorrelation=autocorr,
            mean_reversion_half_life=half_life
        )
    
    def _calculate_mean_reversion_half_life(self, basis_points: List[float]) -> float:
        """Calculate mean reversion half-life in minutes"""
        if len(basis_points) < 100:
            return 60.0  # Default 1 hour
        
        try:
            # Simple AR(1) estimation
            y = np.array(basis_points[1:])
            x = np.array(basis_points[:-1])
            
            # Add constant term
            X = np.column_stack([np.ones(len(x)), x])
            
            # OLS regression
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            phi = beta[1]  # AR coefficient
            
            # Half-life calculation
            if 0 < phi < 1:
                half_life = -np.log(2) / np.log(phi)
            else:
                half_life = 60.0  # Default if no mean reversion detected
            
            return min(max(half_life, 5.0), 1440.0)  # Bound between 5 minutes and 1 day
            
        except:
            return 60.0  # Default on error


class DividendTracker:
    """SPY dividend tracking and impact analysis"""
    
    def __init__(self):
        self.dividend_schedule: List[DividendSchedule] = []
        self.last_update = None
    
    def update_dividend_schedule(self) -> None:
        """Update SPY dividend schedule"""
        # In real implementation, would fetch from market data provider
        # For now, create sample dividend schedule
        today = date.today()
        
        # SPY typically pays quarterly dividends
        sample_dividends = [
            DividendSchedule(
                ex_date=date(2025, 3, 21),
                payment_date=date(2025, 3, 28),
                amount=1.45,
                yield_impact=0.0032,
                days_to_ex_date=(date(2025, 3, 21) - today).days,
                adjustment_factor=0.95
            ),
            DividendSchedule(
                ex_date=date(2025, 6, 20),
                payment_date=date(2025, 6, 27),
                amount=1.52,
                yield_impact=0.0034,
                days_to_ex_date=(date(2025, 6, 20) - today).days,
                adjustment_factor=0.95
            ),
            DividendSchedule(
                ex_date=date(2025, 9, 19),
                payment_date=date(2025, 9, 26),
                amount=1.48,
                yield_impact=0.0033,
                days_to_ex_date=(date(2025, 9, 19) - today).days,
                adjustment_factor=0.95
            ),
            DividendSchedule(
                ex_date=date(2025, 12, 19),
                payment_date=date(2025, 12, 26),
                amount=1.55,
                yield_impact=0.0035,
                days_to_ex_date=(date(2025, 12, 19) - today).days,
                adjustment_factor=0.95
            )
        ]
        
        # Filter for future dividends
        self.dividend_schedule = [d for d in sample_dividends if d.days_to_ex_date >= 0]
        self.last_update = datetime.now()
    
    def get_next_dividend_info(self) -> Optional[DividendSchedule]:
        """Get information about the next upcoming dividend"""
        if not self.dividend_schedule:
            return None
        
        # Find the next dividend (minimum days to ex-date)
        upcoming_dividends = [d for d in self.dividend_schedule if d.days_to_ex_date >= 0]
        if not upcoming_dividends:
            return None
        
        return min(upcoming_dividends, key=lambda x: x.days_to_ex_date)
    
    def get_dividend_impact_factor(self, days_to_expiry: int) -> float:
        """Calculate dividend impact factor for basis calculation"""
        next_div = self.get_next_dividend_info()
        if not next_div or next_div.days_to_ex_date > days_to_expiry:
            return 0.0
        
        # Impact decreases as we get closer to ex-date
        time_factor = max(0.1, next_div.days_to_ex_date / days_to_expiry)
        return next_div.amount * next_div.adjustment_factor * time_factor

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_futures_basis_analyzer(ib_client: Optional[IBClient] = None, 
                                 config: Optional[Dict] = None) -> FuturesBasisAnalyzer:
    """
    Factory function to create futures basis analyzer.
    
    Args:
        ib_client: IB client instance
        config: Configuration dictionary
        
    Returns:
        Configured FuturesBasisAnalyzer instance
    """
    return FuturesBasisAnalyzer(ib_client, config)

def calculate_theoretical_basis(spy_price: float, interest_rate: float, 
                              dividend_yield: float, days_to_expiry: int) -> float:
    """
    Calculate theoretical basis between ES and SPY.
    
    Args:
        spy_price: Current SPY price
        interest_rate: Risk-free interest rate
        dividend_yield: SPY dividend yield
        days_to_expiry: Days to ES futures expiry
        
    Returns:
        Theoretical basis in points
    """
    calculator = FairValueCalculator()
    fair_value = calculator.calculate(spy_price, interest_rate, dividend_yield, days_to_expiry)
    return fair_value.theoretical_es_price - (spy_price * ES_MULTIPLIER)

def get_basis_percentile(current_basis: float, historical_basis: List[float]) -> float:
    """
    Get percentile ranking of current basis.
    
    Args:
        current_basis: Current basis value
        historical_basis: List of historical basis values
        
    Returns:
        Percentile ranking (0-100)
    """
    if not historical_basis:
        return 50.0
    
    return stats.percentileofscore(historical_basis, current_basis)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization code
_global_analyzer: Optional[FuturesBasisAnalyzer] = None

def get_global_analyzer() -> Optional[FuturesBasisAnalyzer]:
    """Get global analyzer instance"""
    return _global_analyzer

def set_global_analyzer(analyzer: FuturesBasisAnalyzer) -> None:
    """Set global analyzer instance"""
    global _global_analyzer
    _global_analyzer = analyzer

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER C11 - Futures Basis Analyzer Test")
    print("=" * 80)
    
    # Create analyzer
    basis_analyzer = FuturesBasisAnalyzer()
    
    # Update market data
    print("\n1. Updating Market Data...")
    es_data, spy_data = basis_analyzer.update_market_data()
    print(f"ES Price: {es_data.price:.2f}")
    print(f"SPY Price: {spy_data.price:.2f}")
    print(f"ES Volume: {es_data.volume:,}")
    print(f"SPY Volume: {spy_data.volume:,}")
    
    # Calculate fair value
    print("\n2. Calculating Fair Value...")
    fair_value = basis_analyzer.calculate_fair_value()
    print(f"SPY Price: ${fair_value.spy_price:.2f}")
    print(f"Fair Value: ${fair_value.fair_value:.2f}")
    print(f"Theoretical ES: {fair_value.theoretical_es_price:.2f}")
    print(f"Interest Adjustment: ${fair_value.interest_adjustment:.4f}")
    print(f"Dividend Adjustment: ${fair_value.dividend_adjustment:.4f}")
    
    # Analyze current basis
    print("\n3. Analyzing Current Basis...")
    if basis_analyzer.current_basis:
        basis = basis_analyzer.current_basis
        print(f"Raw Basis: {basis.raw_basis:.2f} points")
        print(f"Fair Value Basis: {basis.fair_value_basis:.2f} points")
        print(f"Basis Points: {basis.basis_points:.1f} bps")
        print(f"Direction: {basis.direction.value}")
        print(f"Days to Expiry: {basis.days_to_expiry}")
    
    # Detect arbitrage opportunities
    print("\n4. Detecting Arbitrage Opportunities...")
    opportunities = basis_analyzer.detect_arbitrage_opportunities()
    if opportunities:
        for i, opp in enumerate(opportunities):
            print(f"  Opportunity {i+1}:")
            print(f"    Type: {opp.opportunity_type.value}")
            print(f"    Expected Profit: ${opp.expected_profit:.4f}")
            print(f"    Profit (bps): {opp.profit_bps:.2f}")
            print(f"    Confidence: {opp.confidence_score:.1%}")
            print(f"    Risk Score: {opp.risk_score:.1%}")
    
    # Get basis statistics
    print("\n5. Basis Statistics...")
    try:
        stats = basis_analyzer.get_basis_statistics()
        print(f"Mean Basis: {stats.mean_basis:.2f} bps")
        print(f"Std Dev: {stats.std_basis:.2f} bps")
        print(f"Current Percentile: {stats.current_percentile:.0f}%")
        print(f"Z-Score: {stats.zscore:.2f}")
        print(f"Volatility: {stats.volatility:.2f} bps")
        print(f"Mean Reversion Half-Life: {stats.mean_reversion_half_life:.0f} minutes")
    except ValueError as e:
        print(f"Statistics not available: {e}")
    
    # Check dividend impact
    print("\n6. Dividend Impact Analysis...")
    dividend_info = basis_analyzer.check_dividend_impact()
    if dividend_info['has_upcoming_dividend']:
        print(f"Next Ex-Date: {dividend_info['ex_date']}")
        print(f"Days to Ex-Date: {dividend_info['days_to_ex_date']}")
        print(f"Dividend Amount: ${dividend_info['dividend_amount']:.2f}")
        print(f"Estimated Basis Impact: {dividend_info['estimated_basis_impact']:.2f} points")
        print(f"Recommended Action: {dividend_info['recommended_action']}")
    else:
        print("No upcoming dividend impact")
    
    # Get monitoring summary
    print("\n7. Monitoring Summary...")
    summary = basis_analyzer.get_monitoring_summary()
    if summary.get('status') != 'insufficient_data':
        print(f"ES Price: {summary['es_price']}")
        print(f"SPY Price: {summary['spy_price']}")
        print(f"Basis Points: {summary['basis_points']}")
        print(f"Fair Value: {summary['fair_value']}")
        print(f"Regime: {summary['regime']}")
        print(f"Arbitrage Opportunities: {summary['arbitrage_opportunities']}")
        print(f"Best Opportunity: {summary['best_opportunity']}")
        print(f"Expected Profit: {summary['expected_profit_bps']} bps")
    
    # Test real-time monitoring for a few seconds
    print("\n8. Testing Real-Time Monitoring (5 seconds)...")
    basis_analyzer.start_real_time_monitoring()
    time.sleep(5)
    basis_analyzer.stop_real_time_monitoring()
    
    # Get historical performance
    print("\n9. Historical Performance (Last 7 days)...")
    performance = basis_analyzer.get_historical_performance(days=7)
    if 'error' not in performance:
        print(f"Total Signals: {performance['total_signals']}")
        print(f"Success Rate: {performance['success_rate']}")
        print(f"Avg Profit: {performance['avg_profit_bps']} bps")
        print(f"Max Profit: {performance['max_profit_bps']} bps")
        print(f"Daily Avg Signals: {performance['daily_avg_signals']}")
    
    print("\n✅ Futures Basis Analyzer test completed successfully")
    
    # Demonstrate utility functions
    print("\n" + "=" * 80)
    print("UTILITY FUNCTIONS TEST")
    print("=" * 80)
    
    # Test theoretical basis calculation
    print("\n1. Theoretical Basis Calculation...")
    theoretical_basis = calculate_theoretical_basis(
        spy_price=450.0,
        interest_rate=0.05,
        dividend_yield=0.015,
        days_to_expiry=30
    )
    print(f"Theoretical Basis: {theoretical_basis:.2f} points")
    
    # Test basis percentile calculation
    print("\n2. Basis Percentile Calculation...")
    historical_data = [np.random.normal(0, 5) for _ in range(100)]  # Sample data
    current_basis_val = 8.5
    percentile = get_basis_percentile(current_basis_val, historical_data)
    print(f"Current Basis: {current_basis_val:.1f} bps")
    print(f"Historical Percentile: {percentile:.0f}%")
    
    print("\n✅ All tests completed successfully")
