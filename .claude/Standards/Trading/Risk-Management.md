12. Standards/Trading/Risk-Management.md

```markdown
# Risk Management Standards for Spyder Trading System

## Overview

Risk management is the cornerstone of the Spyder trading system. This document defines comprehensive risk management standards covering position limits, drawdown controls, correlation monitoring, and emergency procedures to protect capital in all market conditions.

## Core Risk Principles

### Capital Preservation First
- **Primary Objective**: Preserve capital over profit maximization
- **Risk-Adjusted Returns**: Focus on risk-adjusted performance metrics
- **Defensive Positioning**: Always assume markets can move against positions
- **Systematic Approach**: Rules-based risk management, not discretionary

### Multi-Layer Risk Framework

```
┌─────────────────────────────────────────────────────────────┐
│                   Portfolio Level Risk                      │
│     • Overall exposure limits                              │
│     • Correlation controls                                 │
│     • Sector concentration limits                          │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   Strategy Level Risk                       │
│     • Strategy-specific position limits                    │
│     • Risk/reward ratio requirements                       │
│     • Drawdown controls                                    │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   Position Level Risk                       │
│     • Individual position size limits                      │
│     • Greeks exposure limits                              │
│     • Time decay monitoring                               │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                   Pre-Trade Risk                            │
│     • Order validation                                     │
│     • Available capital checks                            │
│     • Regulatory compliance                               │
└─────────────────────────────────────────────────────────────┘
```

## Position Size Limits

### Maximum Position Sizing Rules

```python
class PositionLimits:
    """Position sizing limits for risk management."""
    
    # Portfolio-level limits
    MAX_PORTFOLIO_RISK = 0.02  # 2% of capital per trade
    MAX_DAILY_RISK = 0.05      # 5% of capital per day
    MAX_STRATEGY_ALLOCATION = 0.20  # 20% per strategy max
    
    # Individual position limits
    MAX_SINGLE_POSITION_VALUE = 10000  # $10,000 max per position
    MAX_OPTIONS_POSITIONS = 50         # Max 50 option contracts
    MAX_UNDERLYING_SHARES = 1000       # Max 1000 shares
    
    # Greeks exposure limits
    MAX_DELTA_EXPOSURE = 1000    # Max $1000 delta exposure
    MAX_GAMMA_EXPOSURE = 100     # Max 100 gamma exposure
    MAX_VEGA_EXPOSURE = 500      # Max $500 vega exposure
    MAX_THETA_EXPOSURE = -200    # Max $200 theta decay per day

def calculate_position_size(
    available_capital: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss_price: float
) -> int:
    """
    Calculate maximum position size based on risk parameters.
    
    Args:
        available_capital: Total available trading capital
        risk_per_trade: Percentage of capital to risk (0.02 = 2%)
        entry_price: Planned entry price
        stop_loss_price: Stop loss price level
        
    Returns:
        Maximum position size in shares/contracts
    """
    # Calculate risk per share/contract
    risk_per_unit = abs(entry_price - stop_loss_price)
    
    # Calculate maximum risk amount
    max_risk_amount = available_capital * risk_per_trade
    
    # Calculate position size
    position_size = int(max_risk_amount / risk_per_unit)
    
    # Apply hard position limits
    max_allowed = min(
        PositionLimits.MAX_SINGLE_POSITION_VALUE / entry_price,
        PositionLimits.MAX_OPTIONS_POSITIONS if is_option(entry_price) else PositionLimits.MAX_UNDERLYING_SHARES
    )
    
    return min(position_size, int(max_allowed))
```

### Dynamic Position Sizing

```python
class DynamicPositionSizer:
    """Dynamic position sizing based on market conditions."""
    
    def __init__(self):
        self.volatility_multiplier = {
            'low': 1.5,     # Increase size in low vol
            'normal': 1.0,  # Normal sizing
            'high': 0.5,    # Reduce size in high vol
            'extreme': 0.25 # Minimal size in extreme vol
        }
    
    def calculate_size_with_volatility(
        self,
        base_size: int,
        current_iv: float,
        historical_iv: float
    ) -> int:
        """Adjust position size based on volatility regime."""
        
        iv_ratio = current_iv / historical_iv
        
        if iv_ratio > 2.0:
            regime = 'extreme'
        elif iv_ratio > 1.5:
            regime = 'high'
        elif iv_ratio < 0.7:
            regime = 'low'
        else:
            regime = 'normal'
        
        adjusted_size = int(base_size * self.volatility_multiplier[regime])
        return max(1, adjusted_size)  # Minimum size of 1
```

## Drawdown Controls

### Maximum Drawdown Limits

```python
class DrawdownManager:
    """Manages drawdown monitoring and controls."""
    
    def __init__(self, max_drawdown: float = 0.10):
        self.max_drawdown = max_drawdown  # 10% max drawdown
        self.peak_capital = 0.0
        self.current_capital = 0.0
        self.daily_drawdown_limit = 0.03  # 3% daily limit
        self.strategy_drawdown_limit = 0.05  # 5% per strategy
        
    def update_capital(self, new_capital: float) -> None:
        """Update capital and check drawdown limits."""
        self.current_capital = new_capital
        self.peak_capital = max(self.peak_capital, new_capital)
        
        current_drawdown = self.get_current_drawdown()
        
        if current_drawdown > self.max_drawdown:
            self.trigger_emergency_stop("Maximum drawdown exceeded")
        elif current_drawdown > self.max_drawdown * 0.8:  # 80% of max
            self.trigger_warning("Approaching maximum drawdown")
    
    def get_current_drawdown(self) -> float:
        """Calculate current drawdown percentage."""
        if self.peak_capital == 0:
            return 0.0
        return (self.peak_capital - self.current_capital) / self.peak_capital
    
    def check_daily_drawdown(self, start_of_day_capital: float) -> bool:
        """Check if daily drawdown limit is exceeded."""
        daily_loss = (start_of_day_capital - self.current_capital) / start_of_day_capital
        return daily_loss <= self.daily_drawdown_limit
    
    def trigger_emergency_stop(self, reason: str) -> None:
        """Emergency stop all trading activities."""
        print(f"EMERGENCY STOP: {reason}")
        # Implementation would halt all trading
        
    def trigger_warning(self, message: str) -> None:
        """Trigger risk warning notification."""
        print(f"RISK WARNING: {message}")
        # Implementation would send alerts
```

### Strategy-Level Drawdown Monitoring

```python
class StrategyRiskMonitor:
    """Monitor risk metrics for individual strategies."""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.peak_value = 0.0
        self.current_value = 0.0
        self.max_consecutive_losses = 5
        self.consecutive_losses = 0
        self.max_strategy_drawdown = 0.08  # 8% max per strategy
        
    def update_performance(self, trade_pnl: float) -> None:
        """Update strategy performance and check limits."""
        self.current_value += trade_pnl
        
        if trade_pnl > 0:
            self.consecutive_losses = 0
            self.peak_value = max(self.peak_value, self.current_value)
        else:
            self.consecutive_losses += 1
        
        # Check drawdown
        if self.peak_value > 0:
            drawdown = (self.peak_value - self.current_value) / self.peak_value
            if drawdown > self.max_strategy_drawdown:
                self.disable_strategy("Excessive drawdown")
        
        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.disable_strategy("Too many consecutive losses")
    
    def disable_strategy(self, reason: str) -> None:
        """Disable strategy due to risk concerns."""
        print(f"DISABLING {self.strategy_name}: {reason}")
        # Implementation would disable strategy
```

## Greeks Risk Management

### Greeks Exposure Monitoring

```python
class GreeksRiskManager:
    """Monitor and manage Greeks exposure across portfolio."""
    
    def __init__(self):
        self.max_delta = 1000      # Maximum delta exposure
        self.max_gamma = 100       # Maximum gamma exposure
        self.max_vega = 500        # Maximum vega exposure
        self.max_theta = -200      # Maximum theta decay (negative)
        
        self.current_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'vega': 0.0,
            'theta': 0.0,
            'rho': 0.0
        }
    
    def validate_new_position(
        self,
        position_greeks: Dict[str, float],
        quantity: int
    ) -> bool:
        """Validate new position doesn't exceed Greeks limits."""
        
        # Calculate new portfolio Greeks
        projected_greeks = {}
        for greek, current_value in self.current_greeks.items():
            projected_value = current_value + (position_greeks.get(greek, 0) * quantity)
            projected_greeks[greek] = projected_value
        
        # Check limits
        if abs(projected_greeks['delta']) > self.max_delta:
            print(f"Delta limit exceeded: {projected_greeks['delta']}")
            return False
            
        if abs(projected_greeks['gamma']) > self.max_gamma:
            print(f"Gamma limit exceeded: {projected_greeks['gamma']}")
            return False
            
        if abs(projected_greeks['vega']) > self.max_vega:
            print(f"Vega limit exceeded: {projected_greeks['vega']}")
            return False
            
        if projected_greeks['theta'] < self.max_theta:  # More negative than limit
            print(f"Theta limit exceeded: {projected_greeks['theta']}")
            return False
        
        return True
    
    def update_portfolio_greeks(self, position_greeks: Dict[str, float], quantity: int) -> None:
        """Update portfolio Greeks after position change."""
        for greek in self.current_greeks:
            self.current_greeks[greek] += position_greeks.get(greek, 0) * quantity
    
    def get_hedge_recommendations(self) -> List[Dict[str, Any]]:
        """Generate hedge recommendations based on current Greeks."""
        recommendations = []
        
        # Delta hedging
        if abs(self.current_greeks['delta']) > self.max_delta * 0.8:
            hedge_shares = -int(self.current_greeks['delta'] / 100)  # SPY delta ~= 100
            recommendations.append({
                'type': 'delta_hedge',
                'action': 'BUY' if hedge_shares > 0 else 'SELL',
                'quantity': abs(hedge_shares),
                'symbol': 'SPY',
                'reason': f"Hedge delta exposure of {self.current_greeks['delta']}"
            })
        
        # Vega hedging
        if abs(self.current_greeks['vega']) > self.max_vega * 0.8:
            recommendations.append({
                'type': 'vega_hedge',
                'reason': f"High vega exposure: {self.current_greeks['vega']}"
            })
        
        return recommendations
```

## Correlation Risk Management

### Correlation Monitoring

```python
class CorrelationRiskManager:
    """Monitor correlation risk across positions."""
    
    def __init__(self):
        self.max_sector_concentration = 0.30  # 30% max in one sector
        self.max_correlation_exposure = 0.50   # 50% max in correlated positions
        self.position_correlations = {}
        
    def analyze_portfolio_correlation(self, positions: Dict[str, float]) -> Dict[str, float]:
        """Analyze correlation risk in current portfolio."""
        
        # Group by sector
        sector_exposure = {}
        for symbol, exposure in positions.items():
            sector = self.get_sector(symbol)
            sector_exposure[sector] = sector_exposure.get(sector, 0) + abs(exposure)
        
        total_exposure = sum(abs(exp) for exp in positions.values())
        
        # Calculate sector concentrations
        sector_concentrations = {
            sector: exposure / total_exposure
            for sector, exposure in sector_exposure.items()
        }
        
        # Identify violations
        violations = {
            sector: concentration
            for sector, concentration in sector_concentrations.items()
            if concentration > self.max_sector_concentration
        }
        
        return violations
    
    def get_sector(self, symbol: str) -> str:
        """Get sector for symbol (simplified)."""
        sector_map = {
            'SPY': 'broad_market',
            'QQQ': 'technology',
            'IWM': 'small_cap',
            'XLF': 'financial',
            'XLE': 'energy'
        }
        return sector_map.get(symbol, 'unknown')
    
    def validate_new_position_correlation(
        self,
        new_symbol: str,
        new_exposure: float,
        existing_positions: Dict[str, float]
    ) -> bool:
        """Validate new position doesn't create excessive correlation."""
        
        # Add new position to existing
        updated_positions = existing_positions.copy()
        updated_positions[new_symbol] = updated_positions.get(new_symbol, 0) + new_exposure
        
        # Check for correlation violations
        violations = self.analyze_portfolio_correlation(updated_positions)
        
        if violations:
            print(f"Correlation violations: {violations}")
            return False
        
        return True
```

## Emergency Procedures

### Circuit Breaker Implementation

```python
class CircuitBreaker:
    """Implement circuit breaker for emergency situations."""
    
    def __init__(self):
        self.triggers = {
            'volatility_spike': 0.50,      # 50% volatility increase
            'rapid_loss': 0.05,            # 5% loss in 15 minutes
            'system_error': True,          # Any system error
            'market_halt': True,           # Exchange trading halt
            'connection_loss': True        # Loss of market connection
        }
        
        self.is_triggered = False
        self.trigger_reason = None
        self.trigger_time = None
    
    def check_triggers(self, market_data: Dict[str, Any], system_health: Dict[str, Any]) -> bool:
        """Check if any circuit breaker triggers are activated."""
        
        # Volatility spike check
        current_vol = market_data.get('implied_volatility', 0.2)
        baseline_vol = market_data.get('baseline_volatility', 0.2)
        if current_vol > baseline_vol * (1 + self.triggers['volatility_spike']):
            self.trigger_circuit_breaker("Volatility spike detected")
            return True
        
        # Rapid loss check
        recent_pnl = market_data.get('recent_pnl_15min', 0)
        total_capital = market_data.get('total_capital', 100000)
        if recent_pnl / total_capital < -self.triggers['rapid_loss']:
            self.trigger_circuit_breaker("Rapid loss detected")
            return True
        
        # System health checks
        if not system_health.get('broker_connected', True):
            self.trigger_circuit_breaker("Broker connection lost")
            return True
        
        if system_health.get('system_error', False):
            self.trigger_circuit_breaker("System error detected")
            return True
        
        return False
    
    def trigger_circuit_breaker(self, reason: str) -> None:
        """Trigger emergency circuit breaker."""
        from datetime import datetime
        
        self.is_triggered = True
        self.trigger_reason = reason
        self.trigger_time = datetime.now()
        
        print(f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}")
        
        # Emergency actions
        self.close_all_positions()
        self.cancel_all_orders()
        self.disable_new_trading()
        self.send_emergency_alerts()
    
    def close_all_positions(self) -> None:
        """Close all open positions immediately."""
        print("Closing all positions...")
        # Implementation would close all positions
    
    def cancel_all_orders(self) -> None:
        """Cancel all pending orders."""
        print("Cancelling all orders...")
        # Implementation would cancel orders
    
    def disable_new_trading(self) -> None:
        """Disable all new trading activities."""
        print("Disabling new trading...")
        # Implementation would disable trading
    
    def send_emergency_alerts(self) -> None:
        """Send emergency notifications."""
        print("Sending emergency alerts...")
        # Implementation would send notifications
    
    def reset_circuit_breaker(self, authorization_code: str) -> bool:
        """Reset circuit breaker with proper authorization."""
        if authorization_code != "EMERGENCY_RESET_2025":
            return False
        
        self.is_triggered = False
        self.trigger_reason = None
        self.trigger_time = None
        
        print("Circuit breaker reset - trading may resume")
        return True
```

### Risk Validation Pipeline

```python
class RiskValidationPipeline:
    """Comprehensive risk validation for all trading decisions."""
    
    def __init__(self):
        self.validators = [
            self.validate_position_size,
            self.validate_portfolio_risk,
            self.validate_correlation,
            self.validate_greeks_exposure,
            self.validate_market_conditions,
            self.validate_strategy_limits
        ]
    
    def validate_trade(self, trade_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Run comprehensive risk validation on proposed trade."""
        
        errors = []
        
        for validator in self.validators:
            try:
                is_valid, error_message = validator(trade_data)
                if not is_valid:
                    errors.append(error_message)
            except Exception as e:
                errors.append(f"Validation error: {str(e)}")
        
        return len(errors) == 0, errors
    
    def validate_position_size(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate position size is within limits."""
        position_value = trade_data.get('quantity', 0) * trade_data.get('price', 0)
        
        if position_value > PositionLimits.MAX_SINGLE_POSITION_VALUE:
            return False, f"Position value ${position_value} exceeds limit"
        
        return True, ""
    
    def validate_portfolio_risk(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate trade doesn't exceed portfolio risk limits."""
        # Implementation would check portfolio-level risk
        return True, ""
    
    def validate_correlation(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate trade doesn't create excessive correlation."""
        # Implementation would check correlation limits
        return True, ""
    
    def validate_greeks_exposure(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate Greeks exposure is within limits."""
        # Implementation would check Greeks limits
        return True, ""
    
    def validate_market_conditions(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate market conditions are suitable for trading."""
        # Check if market is open
        if not self.is_market_open():
            return False, "Market is closed"
        
        # Check for extreme volatility
        if self.is_extreme_volatility():
            return False, "Extreme market volatility detected"
        
        return True, ""
    
    def validate_strategy_limits(self, trade_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate strategy-specific limits."""
        # Implementation would check strategy limits
        return True, ""
    
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        # Implementation would check market hours
        return True
    
    def is_extreme_volatility(self) -> bool:
        """Check for extreme market volatility."""
        # Implementation would check volatility metrics
        return False
```

## Risk Reporting and Monitoring

### Real-Time Risk Dashboard

```python
class RiskDashboard:
    """Real-time risk monitoring dashboard."""
    
    def __init__(self):
        self.risk_metrics = {}
        self.alerts = []
    
    def update_risk_metrics(self, portfolio_data: Dict[str, Any]) -> None:
        """Update all risk metrics for dashboard display."""
        
        self.risk_metrics = {
            'current_drawdown': self.calculate_drawdown(portfolio_data),
            'var_95': self.calculate_var(portfolio_data, 0.95),
            'expected_shortfall': self.calculate_expected_shortfall(portfolio_data),
            'portfolio_beta': self.calculate_beta(portfolio_data),
            'correlation_risk': self.calculate_correlation_risk(portfolio_data),
            'greeks_exposure': self.calculate_greeks_exposure(portfolio_data),
            'concentration_risk': self.calculate_concentration_risk(portfolio_data)
        }
        
        # Check for risk alerts
        self.check_risk_alerts()
    
    def generate_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        
        return {
            'timestamp': datetime.now(),
            'risk_metrics': self.risk_metrics,
            'active_alerts': self.alerts,
            'risk_score': self.calculate_overall_risk_score(),
            'recommendations': self.generate_risk_recommendations()
        }
    
    def calculate_overall_risk_score(self) -> float:
        """Calculate overall portfolio risk score (0-100)."""
        # Implementation would combine multiple risk factors
        return 25.0  # Example: Low risk
    
    def generate_risk_recommendations(self) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        if self.risk_metrics.get('current_drawdown', 0) > 0.05:
            recommendations.append("Consider reducing position sizes due to drawdown")
        
        if self.risk_metrics.get('concentration_risk', 0) > 0.3:
            recommendations.append("Diversify positions to reduce concentration risk")
        
        return recommendations
```

---

These risk management standards ensure the Spyder trading system maintains strict capital preservation protocols while enabling profitable trading operations. Regular review and updating of these standards is essential as market conditions and system capabilities evolve.

  return current_count < limit_config['limit']
    
    def record_request(self, request_type: str) -> None:
        """Record that a request was made."""
        
        if request_type in self.request_history:
            self.request_history[request_type].append(datetime.now())
        else:
            self.logger.warning(f"Recording request for unknown type: {request_type}")
    
    def wait_if_needed(self, request_type: str) -> float:
        """Wait if necessary to respect rate limits, return wait time."""
        
        if self.can_make_request(request_type):
            return 0.0
        
        # Calculate wait time
        if request_type not in self.limits:
            return 0.0
        
        limit_config = self.limits[request_type]
        oldest_request = min(self.request_history[request_type])
        wait_until = oldest_request + timedelta(seconds=limit_config['window'])
        wait_time = (wait_until - datetime.now()).total_seconds()
        
        if wait_time > 0:
            self.logger.info(f"Rate limit reached for {request_type}, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        
        return max(0.0, wait_time)
    
    def get_rate_limit_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current rate limit status for all request types."""
        
        status = {}
        now = datetime.now()
        
        for request_type, limit_config in self.limits.items():
            window_start = now - timedelta(seconds=limit_config['window'])
            
            # Count recent requests
            recent_requests = [
                req_time for req_time in self.request_history[request_type]
                if req_time > window_start
            ]
            
            status[request_type] = {
                'current_count': len(recent_requests),
                'limit': limit_config['limit'],
                'window_seconds': limit_config['window'],
                'utilization_percent': (len(recent_requests) / limit_config['limit']) * 100,
                'can_make_request': len(recent_requests) < limit_config['limit']
            }
        
        return status



