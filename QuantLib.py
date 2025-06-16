"""
Enhanced Mock QuantLib module for Spyder Trading System.

This module provides a more complete mock of QuantLib functionality to allow
the system to run without the full QuantLib installation. For production use,
please install the full QuantLib-Python package.

To install full QuantLib:
    pip install QuantLib-Python
"""

import warnings
import numpy as np
from datetime import datetime
from typing import Optional, Union
from enum import Enum

warnings.warn(
    "Using mock QuantLib module. Install QuantLib-Python for full functionality.",
    UserWarning,
    stacklevel=2
)

# Enums and Constants
class Option:
    """Option type enum."""
    Call = "Call"
    Put = "Put"

class Frequency:
    """Frequency enum."""
    Annual = 1
    Semiannual = 2
    Quarterly = 4
    Monthly = 12
    Daily = 365

class DayCounter:
    """Day counter base class."""
    pass

class Actual365Fixed(DayCounter):
    """Actual/365 Fixed day counter."""
    pass

class Actual360(DayCounter):
    """Actual/360 day counter."""
    pass

class ActualActual(DayCounter):
    """Actual/Actual day counter."""
    pass

class Thirty360(DayCounter):
    """30/360 day counter."""
    pass

# Date classes
class Date:
    """Mock QuantLib Date."""
    def __init__(self, day=None, month=None, year=None):
        if day is None:
            self.date = datetime.now()
        else:
            self.date = datetime(year, month, day)
    
    def __str__(self):
        return self.date.strftime("%Y-%m-%d")
    
    @staticmethod
    def todaysDate():
        """Get today's date."""
        return Date()

class Period:
    """Mock QuantLib Period."""
    def __init__(self, length, units):
        self.length = length
        self.units = units

class Settings:
    """Mock QuantLib Settings."""
    instance = None
    
    def __new__(cls):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance
    
    def __init__(self):
        self.evaluationDate = Date(15, 6, 2025)

# Calendar classes
class Calendar:
    """Mock calendar class."""
    def __init__(self, name="TARGET"):
        self.name = name
    
    def isBusinessDay(self, date):
        """Check if business day."""
        return date.date.weekday() < 5  # Monday-Friday
    
    def businessDaysBetween(self, date1, date2):
        """Approximate business days between dates."""
        delta = date2.date - date1.date
        weeks = delta.days // 7
        remaining_days = delta.days % 7
        return weeks * 5 + min(remaining_days, 5)
    
    def advance(self, date, period):
        """Advance date by period."""
        return date  # Simplified

class UnitedStates(Calendar):
    """Mock US calendar."""
    def __init__(self, market=None):
        super().__init__("UnitedStates")
        self.market = market

class TARGET(Calendar):
    """Mock TARGET calendar."""
    def __init__(self):
        super().__init__("TARGET")

# Quotes and handles
class SimpleQuote:
    """Mock simple quote."""
    def __init__(self, value):
        self.value = float(value)
    
    def setValue(self, value):
        self.value = float(value)

class QuoteHandle:
    """Mock quote handle."""
    def __init__(self, quote):
        self.quote = quote
    
    def value(self):
        if hasattr(self.quote, 'value'):
            return self.quote.value
        return float(self.quote)

# Interest rate structures
class YieldTermStructure:
    """Mock yield term structure."""
    def __init__(self):
        self.referenceDate = Date.todaysDate()
    
    def discount(self, date):
        """Mock discount factor."""
        return 0.95

class FlatForward(YieldTermStructure):
    """Mock flat forward rate."""
    def __init__(self, reference_date, rate, day_counter):
        super().__init__()
        self.referenceDate = reference_date
        self.rate = rate
        self.dayCounter = day_counter

class YieldTermStructureHandle:
    """Mock yield term structure handle."""
    def __init__(self, term_structure):
        self.termStructure = term_structure

# Volatility structures
class BlackVolTermStructure:
    """Mock Black volatility term structure."""
    def __init__(self):
        self.referenceDate = Date.todaysDate()

class BlackConstantVol(BlackVolTermStructure):
    """Mock constant volatility."""
    def __init__(self, reference_date, calendar, volatility, day_counter):
        super().__init__()
        self.referenceDate = reference_date
        self.calendar = calendar
        self.volatility = volatility
        self.dayCounter = day_counter

class BlackVolTermStructureHandle:
    """Mock volatility term structure handle."""
    def __init__(self, vol_structure):
        self.volStructure = vol_structure

# Processes
class StochasticProcess:
    """Mock stochastic process base."""
    pass

class BlackScholesMertonProcess(StochasticProcess):
    """Mock Black-Scholes-Merton process."""
    def __init__(self, spot, dividend_yield, risk_free_rate, volatility):
        self.spot = spot
        self.dividendYield = dividend_yield
        self.riskFreeRate = risk_free_rate
        self.volatility = volatility

class BlackScholesProcess(BlackScholesMertonProcess):
    """Mock Black-Scholes process (no dividends)."""
    def __init__(self, spot, risk_free_rate, volatility):
        super().__init__(spot, YieldTermStructureHandle(FlatForward(Date(), 0.0, Actual365Fixed())), 
                        risk_free_rate, volatility)

# Option instruments
class Exercise:
    """Mock exercise base class."""
    pass

class EuropeanExercise(Exercise):
    """Mock European exercise."""
    def __init__(self, expiry_date):
        self.expiryDate = expiry_date

class AmericanExercise(Exercise):
    """Mock American exercise."""
    def __init__(self, earliest_date, latest_date):
        self.earliestDate = earliest_date
        self.latestDate = latest_date

class BermudanExercise(Exercise):
    """Mock Bermudan exercise."""
    def __init__(self, dates):
        self.dates = dates

class Payoff:
    """Mock payoff base class."""
    pass

class PlainVanillaPayoff(Payoff):
    """Mock plain vanilla payoff."""
    def __init__(self, option_type, strike):
        self.optionType = option_type
        self.strike = strike

class StrikedTypePayoff(PlainVanillaPayoff):
    """Mock striked type payoff."""
    pass

# Options
class VanillaOption:
    """Mock vanilla option."""
    def __init__(self, payoff, exercise):
        self.payoff = payoff
        self.exercise = exercise
        self.engine = None
        self._npv = 10.0  # Default NPV
        self._delta = 0.5
        self._gamma = 0.01
        self._vega = 0.2
        self._theta = -0.05
        self._rho = 0.1
    
    def setPricingEngine(self, engine):
        """Set pricing engine."""
        self.engine = engine
    
    def NPV(self):
        """Net present value."""
        return self._npv
    
    def delta(self):
        """Delta."""
        return self._delta
    
    def gamma(self):
        """Gamma."""
        return self._gamma
    
    def vega(self):
        """Vega."""
        return self._vega
    
    def theta(self):
        """Theta."""
        return self._theta
    
    def rho(self):
        """Rho."""
        return self._rho

class EuropeanOption(VanillaOption):
    """Mock European option."""
    pass

class AmericanOption(VanillaOption):
    """Mock American option."""
    pass

# Pricing engines
class PricingEngine:
    """Mock pricing engine base."""
    pass

class AnalyticEuropeanEngine(PricingEngine):
    """Mock analytic European engine."""
    def __init__(self, process):
        self.process = process

class BinomialEngine(PricingEngine):
    """Mock binomial engine base."""
    def __init__(self, process, steps):
        self.process = process
        self.steps = steps

class BinomialVanillaEngine(BinomialEngine):
    """Mock binomial vanilla engine."""
    pass

class FDEuropeanEngine(PricingEngine):
    """Mock finite differences European engine."""
    def __init__(self, process, time_steps, grid_points):
        self.process = process
        self.timeSteps = time_steps
        self.gridPoints = grid_points

class FDAmericanEngine(PricingEngine):
    """Mock finite differences American engine."""
    def __init__(self, process, time_steps, grid_points):
        self.process = process
        self.timeSteps = time_steps
        self.gridPoints = grid_points

class MCEuropeanEngine(PricingEngine):
    """Mock Monte Carlo European engine."""
    def __init__(self, process, traits, time_steps, required_samples=None, 
                 required_tolerance=None, max_samples=None, seed=None):
        self.process = process
        self.timeSteps = time_steps

# Tree types for binomial models
class CoxRossRubinstein:
    """Cox-Ross-Rubinstein tree."""
    pass

class JarrowRudd:
    """Jarrow-Rudd tree."""
    pass

class AdditiveEQPBinomialTree:
    """Additive EQP binomial tree."""
    pass

class Trigeorgis:
    """Trigeorgis tree."""
    pass

class Tian:
    """Tian tree."""
    pass

class LeisenReimer:
    """Leisen-Reimer tree."""
    pass

class Joshi4:
    """Joshi4 tree."""
    pass

# Additional utilities
class NullCalendar(Calendar):
    """Null calendar - all days are business days."""
    def __init__(self):
        super().__init__("Null")
    
    def isBusinessDay(self, date):
        return True

# Version info
__version__ = "1.31.0-mock"

# Export main classes and functions
__all__ = [
    # Core classes
    'Date', 'Period', 'Settings', 'Calendar', 'UnitedStates', 'TARGET', 'NullCalendar',
    
    # Day counters
    'DayCounter', 'Actual365Fixed', 'Actual360', 'ActualActual', 'Thirty360',
    
    # Options
    'Option', 'VanillaOption', 'EuropeanOption', 'AmericanOption',
    
    # Payoffs and exercises
    'Payoff', 'PlainVanillaPayoff', 'StrikedTypePayoff',
    'Exercise', 'EuropeanExercise', 'AmericanExercise', 'BermudanExercise',
    
    # Market data
    'SimpleQuote', 'QuoteHandle',
    
    # Term structures
    'YieldTermStructure', 'FlatForward', 'YieldTermStructureHandle',
    'BlackVolTermStructure', 'BlackConstantVol', 'BlackVolTermStructureHandle',
    
    # Processes
    'StochasticProcess', 'BlackScholesMertonProcess', 'BlackScholesProcess',
    
    # Pricing engines
    'PricingEngine', 'AnalyticEuropeanEngine', 'BinomialEngine', 'BinomialVanillaEngine',
    'FDEuropeanEngine', 'FDAmericanEngine', 'MCEuropeanEngine',
    
    # Tree types
    'CoxRossRubinstein', 'JarrowRudd', 'AdditiveEQPBinomialTree', 
    'Trigeorgis', 'Tian', 'LeisenReimer', 'Joshi4',
    
    # Enums
    'Frequency'
]
