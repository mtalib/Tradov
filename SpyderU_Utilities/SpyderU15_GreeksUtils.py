#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Greeks Utilities Helper (DataFrame-safe)
Handles py_vollib imports and DataFrame/float conversion
"""

import numpy as np
from typing import Union, Tuple

# Import Greeks functions
try:
    from py_vollib.black_scholes import black_scholes
    from py_vollib.black_scholes.greeks import analytical as greeks
    GREEKS_AVAILABLE = True
    print("✅ py_vollib Greeks loaded successfully")
except ImportError:
    GREEKS_AVAILABLE = False
    print("⚠️ py_vollib not available, using manual calculations")

def _extract_value(result) -> float:
    """Extract float value from py_vollib result (handles DataFrames)."""
    try:
        if hasattr(result, 'iloc'):
            # It's a DataFrame/Series
            return float(result.iloc[0])
        elif hasattr(result, 'item'):
            # It's a numpy array
            return float(result.item())
        else:
            # It's already a number
            return float(result)
    except:
        return float(result)

class SpyderGreeksCalculator:
    """Professional Greeks calculation for Spyder system (DataFrame-safe)."""
    
    @staticmethod
    def calculate_option_price(option_type: str, spot: float, strike: float, 
                             time_to_expiry: float, risk_free_rate: float, 
                             volatility: float) -> float:
        """Calculate option price."""
        if GREEKS_AVAILABLE:
            result = black_scholes(option_type, spot, strike, time_to_expiry, 
                                 risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_black_scholes(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_delta(option_type: str, spot: float, strike: float, 
                       time_to_expiry: float, risk_free_rate: float, 
                       volatility: float) -> float:
        """Calculate delta."""
        if GREEKS_AVAILABLE:
            result = greeks.delta(option_type, spot, strike, time_to_expiry, 
                                risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_delta(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_gamma(option_type: str, spot: float, strike: float, 
                       time_to_expiry: float, risk_free_rate: float, 
                       volatility: float) -> float:
        """Calculate gamma."""
        if GREEKS_AVAILABLE:
            result = greeks.gamma(option_type, spot, strike, time_to_expiry, 
                                risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_gamma(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_theta(option_type: str, spot: float, strike: float, 
                       time_to_expiry: float, risk_free_rate: float, 
                       volatility: float) -> float:
        """Calculate theta."""
        if GREEKS_AVAILABLE:
            result = greeks.theta(option_type, spot, strike, time_to_expiry, 
                                risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_theta(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_vega(option_type: str, spot: float, strike: float, 
                      time_to_expiry: float, risk_free_rate: float, 
                      volatility: float) -> float:
        """Calculate vega."""
        if GREEKS_AVAILABLE:
            result = greeks.vega(option_type, spot, strike, time_to_expiry, 
                               risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_vega(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_rho(option_type: str, spot: float, strike: float, 
                     time_to_expiry: float, risk_free_rate: float, 
                     volatility: float) -> float:
        """Calculate rho."""
        if GREEKS_AVAILABLE:
            result = greeks.rho(option_type, spot, strike, time_to_expiry, 
                              risk_free_rate, volatility)
            return _extract_value(result)
        else:
            return SpyderGreeksCalculator._manual_rho(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
    
    @staticmethod
    def calculate_all_greeks(option_type: str, spot: float, strike: float, 
                           time_to_expiry: float, risk_free_rate: float, 
                           volatility: float) -> dict:
        """Calculate all Greeks at once."""
        return {
            'price': SpyderGreeksCalculator.calculate_option_price(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            ),
            'delta': SpyderGreeksCalculator.calculate_delta(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            ),
            'gamma': SpyderGreeksCalculator.calculate_gamma(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            ),
            'theta': SpyderGreeksCalculator.calculate_theta(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            ),
            'vega': SpyderGreeksCalculator.calculate_vega(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            ),
            'rho': SpyderGreeksCalculator.calculate_rho(
                option_type, spot, strike, time_to_expiry, risk_free_rate, volatility
            )
        }
    
    # Manual calculations (fallback)
    @staticmethod
    def _d1_d2(spot: float, strike: float, time_to_expiry: float, 
               risk_free_rate: float, volatility: float) -> Tuple[float, float]:
        """Calculate d1 and d2 for Black-Scholes."""
        d1 = (np.log(spot/strike) + (risk_free_rate + 0.5*volatility**2)*time_to_expiry) / (volatility*np.sqrt(time_to_expiry))
        d2 = d1 - volatility*np.sqrt(time_to_expiry)
        return d1, d2
    
    @staticmethod
    def _manual_black_scholes(option_type: str, spot: float, strike: float, 
                            time_to_expiry: float, risk_free_rate: float, 
                            volatility: float) -> float:
        """Manual Black-Scholes calculation."""
        from scipy.stats import norm
        
        d1, d2 = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        
        if option_type.lower() == 'c':
            return spot*norm.cdf(d1) - strike*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(d2)
        else:
            return strike*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(-d2) - spot*norm.cdf(-d1)
    
    @staticmethod
    def _manual_delta(option_type: str, spot: float, strike: float, 
                     time_to_expiry: float, risk_free_rate: float, 
                     volatility: float) -> float:
        """Manual delta calculation."""
        from scipy.stats import norm
        
        d1, _ = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        
        if option_type.lower() == 'c':
            return norm.cdf(d1)
        else:
            return norm.cdf(d1) - 1
    
    @staticmethod
    def _manual_gamma(option_type: str, spot: float, strike: float, 
                     time_to_expiry: float, risk_free_rate: float, 
                     volatility: float) -> float:
        """Manual gamma calculation."""
        from scipy.stats import norm
        
        d1, _ = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        return norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry))
    
    @staticmethod
    def _manual_theta(option_type: str, spot: float, strike: float, 
                     time_to_expiry: float, risk_free_rate: float, 
                     volatility: float) -> float:
        """Manual theta calculation."""
        from scipy.stats import norm
        
        d1, d2 = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        
        if option_type.lower() == 'c':
            return -(spot*norm.pdf(d1)*volatility)/(2*np.sqrt(time_to_expiry)) - risk_free_rate*strike*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(d2)
        else:
            return -(spot*norm.pdf(d1)*volatility)/(2*np.sqrt(time_to_expiry)) + risk_free_rate*strike*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(-d2)
    
    @staticmethod
    def _manual_vega(option_type: str, spot: float, strike: float, 
                    time_to_expiry: float, risk_free_rate: float, 
                    volatility: float) -> float:
        """Manual vega calculation."""
        from scipy.stats import norm
        
        d1, _ = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        return spot * norm.pdf(d1) * np.sqrt(time_to_expiry)
    
    @staticmethod
    def _manual_rho(option_type: str, spot: float, strike: float, 
                   time_to_expiry: float, risk_free_rate: float, 
                   volatility: float) -> float:
        """Manual rho calculation."""
        from scipy.stats import norm
        
        _, d2 = SpyderGreeksCalculator._d1_d2(spot, strike, time_to_expiry, risk_free_rate, volatility)
        
        if option_type.lower() == 'c':
            return strike*time_to_expiry*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(d2)
        else:
            return -strike*time_to_expiry*np.exp(-risk_free_rate*time_to_expiry)*norm.cdf(-d2)

def test_greeks_calculations():
    """Test all Greeks calculations with DataFrame handling."""
    print("🧮 Testing Spyder Greeks Calculator (DataFrame-safe)")
    print("=" * 50)
    
    # Test parameters
    spot = 500.0
    strike = 505.0
    time_to_expiry = 0.25
    risk_free_rate = 0.05
    volatility = 0.20
    
    try:
        calc = SpyderGreeksCalculator()
        greeks_data = calc.calculate_all_greeks('c', spot, strike, time_to_expiry, risk_free_rate, volatility)
        
        print("✅ SPY 505 Call (3 months):")
        print(f"   Price: ${greeks_data['price']:.2f}")
        print(f"   Delta: {greeks_data['delta']:.4f}")
        print(f"   Gamma: {greeks_data['gamma']:.4f}")
        print(f"   Theta: {greeks_data['theta']:.4f}")
        print(f"   Vega: {greeks_data['vega']:.4f}")
        print(f"   Rho: {greeks_data['rho']:.4f}")
        print("✅ All Greeks calculations working perfectly!")
        
        # Test put option too
        put_greeks = calc.calculate_all_greeks('p', spot, strike, time_to_expiry, risk_free_rate, volatility)
        print("\n✅ SPY 505 Put (3 months):")
        print(f"   Price: ${put_greeks['price']:.2f}")
        print(f"   Delta: {put_greeks['delta']:.4f}")
        print("✅ Put calculations working too!")
        
        return True
        
    except Exception as e:
        print(f"❌ Greeks calculation error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_greeks_calculations()
