#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF06_GreeksCalculator.py
Group: F (Technical Analysis)
Purpose: Options Greeks calculations using QuantLib

Description:
    This module provides professional-grade options pricing and Greeks calculations
    using QuantLib. It supports American options (SPY), various pricing models,
    and advanced Greeks including second-order sensitivities. The module integrates
    seamlessly with the Spyder trading system for real-time risk management.

Author: Mohamed Talib
Date: 2025-06-12
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import numpy as np
from typing import Dict, Optional, Tuple, Union
from enum import Enum
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import QuantLib as ql
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model parameters
BINOMIAL_STEPS = 100  # Steps for binomial tree
MC_PATHS = 10000      # Paths for Monte Carlo
MC_STEPS = 100        # Time steps for Monte Carlo
CALENDAR_DAYS_PER_YEAR = 365
TRADING_DAYS_PER_YEAR = 252

# Risk-free rate source
DEFAULT_RISK_FREE_RATE = 0.05  # 5% default if not provided

# ==============================================================================
# ENUMS
# ==============================================================================
class PricingModel(Enum):
    """Available pricing models"""
    BINOMIAL_CRR = "crr"          # Cox-Ross-Rubinstein
    BINOMIAL_JR = "jarrowrudd"    # Jarrow-Rudd
    BINOMIAL_LR = "lr"            # Leisen-Reimer
    BINOMIAL_TIAN = "tian"        # Tian
    MONTE_CARLO = "mc"            # Monte Carlo
    FINITE_DIFFERENCES = "fd"      # Finite Differences

# ==============================================================================
# GREEKS CALCULATOR CLASS
# ==============================================================================
class GreeksCalculator:
    """
    Professional options pricing and Greeks calculator using QuantLib.
    
    This class provides accurate pricing for American options and calculates
    all standard Greeks plus advanced sensitivities. It supports multiple
    pricing models and handles edge cases gracefully.
    """
    
    def __init__(self, logger: Optional[SpyderLogger] = None,
                 error_handler: Optional[SpyderErrorHandler] = None):
        """Initialize Greeks calculator"""
        self.logger = logger or SpyderLogger()
        self.error_handler = error_handler or SpyderErrorHandler()
        
        # Set QuantLib evaluation date
        self.evaluation_date = ql.Date.todaysDate()
        ql.Settings.instance().evaluationDate = self.evaluation_date
        
        # Default model
        self.default_model = PricingModel.BINOMIAL_CRR
        
        # Calendar for business days
        self.calendar = ql.UnitedStates(ql.UnitedStates.NYSE)
        
        self.logger.info("QuantLib Greeks Calculator initialized")
    
    # ==========================================================================
    # MAIN PRICING METHODS
    # ==========================================================================
    def calculate_option_price(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool = True,
        dividend_yield: float = 0.0,
        model: PricingModel = None
    ) -> float:
        """
        Calculate option price using QuantLib
        
        Args:
            spot_price: Current price of underlying
            strike_price: Strike price of option
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            option_type: CALL or PUT
            is_american: True for American, False for European
            dividend_yield: Dividend yield of underlying
            model: Pricing model to use
            
        Returns:
            Option price
        """
        try:
            # Create QuantLib option
            option = self._create_option(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility, option_type,
                is_american, dividend_yield
            )
            
            # Set pricing engine
            model = model or self.default_model
            engine = self._create_pricing_engine(
                spot_price, risk_free_rate, volatility,
                dividend_yield, model
            )
            option.setPricingEngine(engine)
            
            # Calculate price
            price = option.NPV()
            
            return max(0.0, price)
            
        except Exception as e:
            self.logger.error(f"Error calculating option price: {e}")
            self.error_handler.handle_error(e)
            # Fallback to Black-Scholes for European
            if not is_american:
                return self._black_scholes_price(
                    spot_price, strike_price, time_to_expiry,
                    risk_free_rate, volatility, option_type
                )
            return 0.0
    
    def calculate_all_greeks(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool = True,
        dividend_yield: float = 0.0,
        model: PricingModel = None
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option
        
        Returns dictionary with:
            - price: Option price
            - delta: Rate of change of price with spot
            - gamma: Rate of change of delta with spot
            - theta: Rate of change of price with time
            - vega: Rate of change of price with volatility
            - rho: Rate of change of price with interest rate
            - lambda: Option elasticity
            - vanna: Rate of change of delta with volatility
            - charm: Rate of change of delta with time
            - vomma: Rate of change of vega with volatility
            - veta: Rate of change of vega with time
        """
        try:
            # Create option and pricing engine
            option = self._create_option(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility, option_type,
                is_american, dividend_yield
            )
            
            model = model or self.default_model
            engine = self._create_pricing_engine(
                spot_price, risk_free_rate, volatility,
                dividend_yield, model
            )
            option.setPricingEngine(engine)
            
            # Calculate all Greeks
            greeks = {
                'price': option.NPV(),
                'delta': option.delta(),
                'gamma': option.gamma(),
                'theta': option.theta() / CALENDAR_DAYS_PER_YEAR,  # Convert to per day
                'vega': option.vega() / 100,  # Convert to per 1% vol change
                'rho': option.rho() / 100,    # Convert to per 1% rate change
            }
            
            # Calculate lambda (elasticity)
            if greeks['price'] > 0:
                greeks['lambda'] = greeks['delta'] * spot_price / greeks['price']
            else:
                greeks['lambda'] = 0.0
            
            # Calculate second-order Greeks using finite differences
            second_order = self._calculate_second_order_greeks(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility, option_type,
                is_american, dividend_yield, model
            )
            greeks.update(second_order)
            
            return greeks
            
        except Exception as e:
            self.logger.error(f"Error calculating Greeks: {e}")
            self.error_handler.handle_error(e)
            return self._empty_greeks()
    
    # ==========================================================================
    # INDIVIDUAL GREEKS
    # ==========================================================================
    def delta(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool = True
    ) -> float:
        """Calculate option delta"""
        greeks = self.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, option_type,
            is_american
        )
        return greeks['delta']
    
    def gamma(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType = None,
        is_american: bool = True
    ) -> float:
        """Calculate option gamma (same for calls and puts)"""
        greeks = self.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL,
            is_american
        )
        return greeks['gamma']
    
    def theta(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool = True
    ) -> float:
        """Calculate option theta (time decay per day)"""
        greeks = self.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, option_type,
            is_american
        )
        return greeks['theta']
    
    def vega(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType = None,
        is_american: bool = True
    ) -> float:
        """Calculate option vega (same for calls and puts)"""
        greeks = self.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, OptionType.CALL,
            is_american
        )
        return greeks['vega']
    
    def rho(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool = True
    ) -> float:
        """Calculate option rho"""
        greeks = self.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, option_type,
            is_american
        )
        return greeks['rho']
    
    # ==========================================================================
    # IMPLIED VOLATILITY
    # ==========================================================================
    def calculate_implied_volatility(
        self,
        option_price: float,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        option_type: OptionType,
        is_american: bool = True,
        dividend_yield: float = 0.0,
        initial_guess: float = 0.25
    ) -> Optional[float]:
        """
        Calculate implied volatility from option price
        
        Args:
            option_price: Market price of option
            spot_price: Current price of underlying
            strike_price: Strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free rate
            option_type: CALL or PUT
            is_american: True for American options
            dividend_yield: Dividend yield
            initial_guess: Initial volatility guess
            
        Returns:
            Implied volatility or None if cannot be calculated
        """
        try:
            # Create option
            option = self._create_option(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, initial_guess, option_type,
                is_american, dividend_yield
            )
            
            # Create process with initial volatility
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot_price))
            flat_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(self.evaluation_date, risk_free_rate, ql.Actual365Fixed())
            )
            dividend_yield_ts = ql.YieldTermStructureHandle(
                ql.FlatForward(self.evaluation_date, dividend_yield, ql.Actual365Fixed())
            )
            
            # Use binomial engine for American options
            if is_american:
                process = ql.BlackScholesMertonProcess(
                    spot_handle, dividend_yield_ts, flat_ts,
                    ql.BlackVolTermStructureHandle(
                        ql.BlackConstantVol(
                            self.evaluation_date, self.calendar,
                            initial_guess, ql.Actual365Fixed()
                        )
                    )
                )
                engine = ql.BinomialVanillaEngine(process, "crr", BINOMIAL_STEPS)
            else:
                engine = ql.AnalyticEuropeanEngine(
                    ql.BlackScholesMertonProcess(
                        spot_handle, dividend_yield_ts, flat_ts,
                        ql.BlackVolTermStructureHandle(
                            ql.BlackConstantVol(
                                self.evaluation_date, self.calendar,
                                initial_guess, ql.Actual365Fixed()
                            )
                        )
                    )
                )
            
            option.setPricingEngine(engine)
            
            # Calculate implied volatility
            try:
                iv = option.impliedVolatility(
                    option_price,
                    process,
                    1e-4,  # accuracy
                    100,   # max iterations
                    0.001, # min vol
                    4.0    # max vol
                )
                return iv
            except:
                # Try alternative method with different bounds
                return self._implied_vol_bisection(
                    option_price, spot_price, strike_price,
                    time_to_expiry, risk_free_rate, option_type,
                    is_american, dividend_yield
                )
                
        except Exception as e:
            self.logger.warning(f"Could not calculate implied volatility: {e}")
            return None
    
    # ==========================================================================
    # PROBABILITY CALCULATIONS
    # ==========================================================================
    def calculate_probability_itm(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        dividend_yield: float = 0.0
    ) -> float:
        """Calculate probability of option finishing in-the-money"""
        try:
            # For risk-neutral probability, use N(d2)
            d1, d2 = self._calculate_d1_d2(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility, dividend_yield
            )
            
            normal = ql.CumulativeNormalDistribution()
            
            if option_type == OptionType.CALL:
                return normal(d2)
            else:
                return normal(-d2)
                
        except Exception as e:
            self.logger.error(f"Error calculating ITM probability: {e}")
            return 0.5
    
    def calculate_probability_touch(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        volatility: float
    ) -> float:
        """
        Calculate probability of touching strike price before expiration
        Using approximation: P(touch) ≈ 2 * P(ITM)
        """
        # Simplified calculation
        if spot_price == strike_price:
            return 1.0
            
        # Standard deviation of price movement
        std_dev = volatility * np.sqrt(time_to_expiry)
        
        # Distance to strike in standard deviations
        distance = abs(np.log(strike_price / spot_price)) / std_dev
        
        # Approximate probability of touch
        prob_touch = 2 * (1 - ql.CumulativeNormalDistribution()(distance))
        
        return min(1.0, prob_touch)
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _create_option(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool,
        dividend_yield: float
    ) -> ql.VanillaOption:
        """Create QuantLib option object"""
        # Convert time to expiry to QuantLib date
        expiry_date = self.evaluation_date + int(time_to_expiry * 365)
        
        # Create payoff
        if option_type == OptionType.CALL:
            payoff = ql.PlainVanillaPayoff(ql.Option.Call, strike_price)
        else:
            payoff = ql.PlainVanillaPayoff(ql.Option.Put, strike_price)
        
        # Create exercise
        if is_american:
            exercise = ql.AmericanExercise(self.evaluation_date, expiry_date)
        else:
            exercise = ql.EuropeanExercise(expiry_date)
        
        # Create option
        option = ql.VanillaOption(payoff, exercise)
        
        return option
    
    def _create_pricing_engine(
        self,
        spot_price: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        model: PricingModel
    ) -> ql.PricingEngine:
        """Create appropriate pricing engine"""
        # Create market data handles
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot_price))
        
        # Flat term structures
        flat_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(self.evaluation_date, risk_free_rate, ql.Actual365Fixed())
        )
        dividend_yield_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(self.evaluation_date, dividend_yield, ql.Actual365Fixed())
        )
        flat_vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(
                self.evaluation_date, self.calendar,
                volatility, ql.Actual365Fixed()
            )
        )
        
        # Create process
        process = ql.BlackScholesMertonProcess(
            spot_handle, dividend_yield_ts, flat_ts, flat_vol_ts
        )
        
        # Create engine based on model
        if model == PricingModel.BINOMIAL_CRR:
            return ql.BinomialVanillaEngine(process, "crr", BINOMIAL_STEPS)
        elif model == PricingModel.BINOMIAL_JR:
            return ql.BinomialVanillaEngine(process, "jarrowrudd", BINOMIAL_STEPS)
        elif model == PricingModel.BINOMIAL_LR:
            return ql.BinomialVanillaEngine(process, "lr", BINOMIAL_STEPS)
        elif model == PricingModel.BINOMIAL_TIAN:
            return ql.BinomialVanillaEngine(process, "tian", BINOMIAL_STEPS)
        elif model == PricingModel.MONTE_CARLO:
            return ql.MCAmericanEngine(
                process, "pseudorandom", 
                timeSteps=MC_STEPS,
                requiredSamples=MC_PATHS
            )
        elif model == PricingModel.FINITE_DIFFERENCES:
            return ql.FdBlackScholesVanillaEngine(process)
        else:
            # Default to CRR binomial
            return ql.BinomialVanillaEngine(process, "crr", BINOMIAL_STEPS)
    
    def _calculate_second_order_greeks(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType,
        is_american: bool,
        dividend_yield: float,
        model: PricingModel
    ) -> Dict[str, float]:
        """Calculate second-order Greeks using finite differences"""
        second_order = {}
        
        # Small perturbations
        spot_shift = spot_price * 0.001
        vol_shift = volatility * 0.01
        time_shift = 1 / 365  # One day
        
        try:
            # Base Greeks
            base_greeks = self.calculate_all_greeks(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility, option_type,
                is_american, dividend_yield, model
            )
            
            # Vanna: d(Delta)/d(Vol)
            greeks_vol_up = self.calculate_all_greeks(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, volatility + vol_shift, option_type,
                is_american, dividend_yield, model
            )
            second_order['vanna'] = (greeks_vol_up['delta'] - base_greeks['delta']) / vol_shift
            
            # Charm: d(Delta)/d(Time)
            if time_to_expiry > time_shift:
                greeks_time_down = self.calculate_all_greeks(
                    spot_price, strike_price, time_to_expiry - time_shift,
                    risk_free_rate, volatility, option_type,
                    is_american, dividend_yield, model
                )
                second_order['charm'] = -(greeks_time_down['delta'] - base_greeks['delta']) / time_shift
            else:
                second_order['charm'] = 0.0
            
            # Vomma: d(Vega)/d(Vol)
            second_order['vomma'] = (greeks_vol_up['vega'] - base_greeks['vega']) / vol_shift
            
            # Veta: d(Vega)/d(Time)
            if time_to_expiry > time_shift:
                second_order['veta'] = -(greeks_time_down['vega'] - base_greeks['vega']) / time_shift
            else:
                second_order['veta'] = 0.0
                
        except Exception as e:
            self.logger.warning(f"Error calculating second-order Greeks: {e}")
            second_order = {
                'vanna': 0.0,
                'charm': 0.0,
                'vomma': 0.0,
                'veta': 0.0
            }
        
        return second_order
    
    def _calculate_d1_d2(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float
    ) -> Tuple[float, float]:
        """Calculate d1 and d2 for Black-Scholes formula"""
        if time_to_expiry <= 0 or volatility <= 0:
            return 0.0, 0.0
            
        d1 = (np.log(spot_price / strike_price) + 
              (risk_free_rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        return d1, d2
    
    def _black_scholes_price(
        self,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        option_type: OptionType
    ) -> float:
        """Black-Scholes price for European options (fallback)"""
        if time_to_expiry <= 0:
            # Intrinsic value at expiry
            if option_type == OptionType.CALL:
                return max(0, spot_price - strike_price)
            else:
                return max(0, strike_price - spot_price)
        
        d1, d2 = self._calculate_d1_d2(
            spot_price, strike_price, time_to_expiry,
            risk_free_rate, volatility, 0.0
        )
        
        normal = ql.CumulativeNormalDistribution()
        
        if option_type == OptionType.CALL:
            price = (spot_price * normal(d1) - 
                    strike_price * np.exp(-risk_free_rate * time_to_expiry) * normal(d2))
        else:
            price = (strike_price * np.exp(-risk_free_rate * time_to_expiry) * normal(-d2) - 
                    spot_price * normal(-d1))
        
        return max(0, price)
    
    def _implied_vol_bisection(
        self,
        option_price: float,
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        option_type: OptionType,
        is_american: bool,
        dividend_yield: float
    ) -> Optional[float]:
        """Calculate implied volatility using bisection method"""
        # Bounds for volatility
        vol_min = 0.001
        vol_max = 4.0
        tolerance = 1e-5
        max_iterations = 100
        
        for i in range(max_iterations):
            vol_mid = (vol_min + vol_max) / 2
            
            # Calculate price with mid volatility
            price_mid = self.calculate_option_price(
                spot_price, strike_price, time_to_expiry,
                risk_free_rate, vol_mid, option_type,
                is_american, dividend_yield
            )
            
            # Check convergence
            if abs(price_mid - option_price) < tolerance:
                return vol_mid
            
            # Update bounds
            if price_mid > option_price:
                vol_max = vol_mid
            else:
                vol_min = vol_mid
            
            # Check if bounds are too close
            if vol_max - vol_min < tolerance:
                return vol_mid
        
        return None
    
    def _empty_greeks(self) -> Dict[str, float]:
        """Return empty Greeks dictionary"""
        return {
            'price': 0.0,
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'lambda': 0.0,
            'vanna': 0.0,
            'charm': 0.0,
            'vomma': 0.0,
            'veta': 0.0
        }


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test the Greeks calculator
    calculator = GreeksCalculator()
    
    # Test parameters
    spot = 450.0
    strike = 450.0
    tte = 30 / 365  # 30 days
    rate = 0.05
    vol = 0.20
    
    print("Testing QuantLib Greeks Calculator")
    print("=" * 50)
    print(f"Spot: ${spot}")
    print(f"Strike: ${strike}")
    print(f"Time to Expiry: {tte * 365:.0f} days")
    print(f"Risk-Free Rate: {rate * 100:.1f}%")
    print(f"Volatility: {vol * 100:.1f}%")
    print()
    
    # Calculate for both call and put
    for opt_type in [OptionType.CALL, OptionType.PUT]:
        print(f"\n{opt_type.name} Option:")
        print("-" * 30)
        
        # American option Greeks
        greeks = calculator.calculate_all_greeks(
            spot, strike, tte, rate, vol, opt_type, is_american=True
        )
        
        print(f"Price: ${greeks['price']:.2f}")
        print(f"Delta: {greeks['delta']:.4f}")
        print(f"Gamma: {greeks['gamma']:.4f}")
        print(f"Theta: ${greeks['theta']:.2f}/day")
        print(f"Vega: ${greeks['vega']:.2f}/1% vol")
        print(f"Rho: ${greeks['rho']:.2f}/1% rate")
        
        # Probability calculations
        prob_itm = calculator.calculate_probability_itm(
            spot, strike, tte, rate, vol, opt_type
        )
        prob_touch = calculator.calculate_probability_touch(
            spot, strike, tte, vol
        )
        
        print(f"\nProbability ITM: {prob_itm * 100:.1f}%")
        print(f"Probability Touch: {prob_touch * 100:.1f}%")
    
    # Test implied volatility
    print("\n\nImplied Volatility Test:")
    print("-" * 30)
    call_price = 5.50
    iv = calculator.calculate_implied_volatility(
        call_price, spot, strike, tte, rate, OptionType.CALL
    )
    if iv:
        print(f"Market Price: ${call_price:.2f}")
        print(f"Implied Volatility: {iv * 100:.1f}%")
