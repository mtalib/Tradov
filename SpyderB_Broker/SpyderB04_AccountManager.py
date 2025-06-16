#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: SpyderB04_AccountManager.py
Group: B (Broker Integration)
Purpose: Account data and portfolio management

Description:
    This module manages account information and portfolio data for the Spyder trading system.
    It tracks account balances, buying power, margin requirements, and portfolio statistics.
    The module ensures accurate account monitoring, risk calculations based on available
    capital, and compliance with margin requirements.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import threading
from typing import Dict, List, Optional, Any, Tuple, Set, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import json
import pandas as pd

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from ibapi.contract import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import *
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType, EventPriority
from SpyderB_Broker.SpyderB01_IBClient import IBClient

# ==============================================================================
# ENUMS
# ==============================================================================
class AccountType(Enum):
    """Account types"""
    CASH = "cash"
    MARGIN = "margin"
    PORTFOLIO_MARGIN = "portfolio_margin"

class CurrencyType(Enum):
    """Currency types"""
    BASE = "BASE"
    USD = "USD"

class MarginMode(Enum):
    """Margin calculation modes"""
    REGULAR = "regular"
    PATTERN_DAY_TRADER = "pdt"
    PORTFOLIO_MARGIN = "pm"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class AccountBalance:
    """Account balance information"""
    net_liquidation: float = 0.0
    total_cash: float = 0.0
    settled_cash: float = 0.0
    buying_power: float = 0.0
    equity_with_loan: float = 0.0
    
    # Margin values
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    available_funds: float = 0.0
    excess_liquidity: float = 0.0
    cushion: float = 0.0  # Margin cushion percentage
    
    # Risk metrics
    margin_usage: float = 0.0  # Percentage
    leverage: float = 0.0
    day_trades_remaining: int = 3
    
    # P&L
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Timestamp
    last_update: datetime.datetime = field(default_factory=datetime.datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'net_liquidation': self.net_liquidation,
            'total_cash': self.total_cash,
            'settled_cash': self.settled_cash,
            'buying_power': self.buying_power,
            'initial_margin': self.initial_margin,
            'maintenance_margin': self.maintenance_margin,
            'margin_usage': self.margin_usage,
            'leverage': self.leverage,
            'daily_pnl': self.daily_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'last_update': self.last_update.isoformat()
        }

class PortfolioItem:
    """Portfolio item (position summary)"""
    symbol: str
    position: int
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'symbol': self.symbol,
            'position': self.position,
            'market_value': self.market_value,
            'average_cost': self.average_cost,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl
        }

class MarginRequirement:
    """Margin requirement for a position"""
    symbol: str
    initial_margin: float
    maintenance_margin: float
    current_margin: float
    margin_change: float
    margin_type: str  # 'equity', 'option', 'future'

class AccountAlert:
    """Account-related alert"""
    alert_type: str
    severity: str  # 'info', 'warning', 'critical'
    message: str
    value: float
    threshold: float
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)

# ==============================================================================
# ACCOUNT MANAGER CLASS
# ==============================================================================
class AccountManager:
    """
    Manages account data and portfolio information.
    
    Features:
    - Real-time account balance tracking
    - Buying power monitoring
    - Margin requirement calculations
    - Portfolio composition analysis
    - Risk metrics monitoring
    - Account alerts and notifications
    """
    
    def __init__(self, ib_client: IBClient, event_manager: EventManager):
        """
        Initialize account manager.
        
        Args:
            ib_client: IB client instance
            event_manager: Event manager instance
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Account data
        self.account_id: Optional[str] = None
        self.account_type = AccountType.MARGIN
        self.margin_mode = MarginMode.REGULAR
        self.currency = CurrencyType.USD
        
        # Current values
        self.balance = AccountBalance()
        self.portfolio: Dict[str, PortfolioItem] = {}
        self.margin_requirements: Dict[str, MarginRequirement] = {}
        
        # Historical data
        self.balance_history: deque = deque(maxlen=288)  # 24 hours at 5-min intervals
        self.pnl_history: deque = deque(maxlen=1000)
        
        # Alerts
        self.active_alerts: List[AccountAlert] = []
        self.alert_history: deque = deque(maxlen=100)
        
        # Raw account values from IB
        self._account_values: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._account_lock = threading.RLock()
        
        # IB callbacks
        self._register_ib_callbacks()
        
        # Risk parameters
        self.risk_parameters = {
            'max_leverage': 2.0,
            'max_margin_usage': 0.80,
            'min_excess_liquidity': 10000,
            'min_buying_power': 5000,
            'position_size_limit': 0.20  # Max 20% per position
        }
        
        self.logger.info("AccountManager initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start account monitoring"""
        if self._running:
            return
        
        self._running = True
        
        # Request initial account data
        self._request_account_updates()
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_account,
            daemon=True,
            name="AccountMonitor"
        )
        self._monitor_thread.start()
        
        self.logger.info("Account monitoring started")
    
    def stop(self) -> None:
        """Stop account monitoring"""
        self._running = False
        
        # Cancel account updates
        if self.account_id:
            self.ib_client.reqAccountUpdates(False, self.account_id)
        
        # Wait for thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        self.logger.info("Account monitoring stopped")
    
    # ==========================================================================
    # ACCOUNT DATA MANAGEMENT
    # ==========================================================================
    def _request_account_updates(self) -> None:
        """Request account updates from broker"""
        # Request managed accounts first
        self.ib_client.reqManagedAccts()
        
        # Note: Account updates will be requested after receiving managed accounts
    
    def _update_balance(self) -> None:
        """Update account balance from raw values"""
        with self._account_lock:
            # Get BASE currency values (account total)
            base_values = self._account_values.get('BASE', {})
            
            # Update balance object
            self.balance.net_liquidation = base_values.get('NetLiquidation', 0.0)
            self.balance.total_cash = base_values.get('TotalCashValue', 0.0)
            self.balance.settled_cash = base_values.get('SettledCash', 0.0)
            self.balance.buying_power = base_values.get('BuyingPower', 0.0)
            self.balance.equity_with_loan = base_values.get('EquityWithLoanValue', 0.0)
            
            # Margin values
            self.balance.initial_margin = base_values.get('InitMarginReq', 0.0)
            self.balance.maintenance_margin = base_values.get('MaintMarginReq', 0.0)
            self.balance.available_funds = base_values.get('AvailableFunds', 0.0)
            self.balance.excess_liquidity = base_values.get('ExcessLiquidity', 0.0)
            self.balance.cushion = base_values.get('Cushion', 0.0) * 100  # Convert to percentage
            
            # Risk metrics
            if self.balance.net_liquidation > 0:
                self.balance.margin_usage = (
                    self.balance.maintenance_margin / self.balance.net_liquidation * 100
                )
            
            self.balance.leverage = base_values.get('Leverage', 0.0)
            self.balance.day_trades_remaining = int(base_values.get('DayTradesRemaining', 3))
            
            # P&L
            self.balance.daily_pnl = base_values.get('DailyPnL', 0.0)
            self.balance.unrealized_pnl = base_values.get('UnrealizedPnL', 0.0)
            self.balance.realized_pnl = base_values.get('RealizedPnL', 0.0)
            
            self.balance.last_update = datetime.datetime.now()
            
            # Add to history
            self.balance_history.append({
                'timestamp': self.balance.last_update,
                'net_liquidation': self.balance.net_liquidation,
                'buying_power': self.balance.buying_power,
                'margin_usage': self.balance.margin_usage,
                'daily_pnl': self.balance.daily_pnl
            })
    
    def _check_account_alerts(self) -> None:
        """Check for account alerts"""
        alerts = []
        
        # Buying power check
        if self.balance.buying_power < self.risk_parameters['min_buying_power']:
            alerts.append(AccountAlert(
                alert_type='low_buying_power',
                severity='critical',
                message=f"Low buying power: ${self.balance.buying_power:.2f}",
                value=self.balance.buying_power,
                threshold=self.risk_parameters['min_buying_power']
            ))
        elif self.balance.buying_power < self.balance.net_liquidation * BUYING_POWER_WARNING_THRESHOLD:
            alerts.append(AccountAlert(
                alert_type='buying_power_warning',
                severity='warning',
                message=f"Buying power below {BUYING_POWER_WARNING_THRESHOLD*100}% of NAV",
                value=self.balance.buying_power,
                threshold=self.balance.net_liquidation * BUYING_POWER_WARNING_THRESHOLD
            ))
        
        # Margin usage check
        if self.balance.margin_usage > self.risk_parameters['max_margin_usage'] * 100:
            alerts.append(AccountAlert(
                alert_type='high_margin_usage',
                severity='critical',
                message=f"High margin usage: {self.balance.margin_usage:.1f}%",
                value=self.balance.margin_usage,
                threshold=self.risk_parameters['max_margin_usage'] * 100
            ))
        elif self.balance.margin_usage > MARGIN_WARNING_THRESHOLD * 100:
            alerts.append(AccountAlert(
                alert_type='margin_usage_warning',
                severity='warning',
                message=f"Margin usage above {MARGIN_WARNING_THRESHOLD*100}%",
                value=self.balance.margin_usage,
                threshold=MARGIN_WARNING_THRESHOLD * 100
            ))
        
        # Excess liquidity check
        if self.balance.excess_liquidity < self.risk_parameters['min_excess_liquidity']:
            alerts.append(AccountAlert(
                alert_type='low_excess_liquidity',
                severity='warning',
                message=f"Low excess liquidity: ${self.balance.excess_liquidity:.2f}",
                value=self.balance.excess_liquidity,
                threshold=self.risk_parameters['min_excess_liquidity']
            ))
        
        # Pattern day trader check
        if self.margin_mode == MarginMode.PATTERN_DAY_TRADER and self.balance.day_trades_remaining <= 0:
            alerts.append(AccountAlert(
                alert_type='pdt_restriction',
                severity='critical',
                message="No day trades remaining - PDT restriction active",
                value=0,
                threshold=1
            ))
        
        # Process alerts
        for alert in alerts:
            self._process_alert(alert)
    
    def _process_alert(self, alert: AccountAlert) -> None:
        """Process an account alert"""
        # Check if alert is already active
        existing = next((a for a in self.active_alerts 
                        if a.alert_type == alert.alert_type), None)
        
        if not existing:
            # New alert
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Emit event
            priority = EventPriority.CRITICAL if alert.severity == 'critical' else EventPriority.HIGH
            
            self.event_manager.emit(Event(
                EventType.RISK if alert.severity == 'critical' else EventType.WARNING,
                {
                    'type': 'account_alert',
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'value': alert.value,
                    'threshold': alert.threshold
                },
                priority=priority
            ))
            
            self.logger.warning(f"Account alert: {alert.message}")
    
    def _clear_resolved_alerts(self) -> None:
        """Clear alerts that are no longer valid"""
        with self._account_lock:
            # Re-check all active alerts
            resolved_alerts = []
            
            for alert in self.active_alerts:
                # Check if condition still exists
                if alert.alert_type == 'low_buying_power':
                    if self.balance.buying_power >= alert.threshold:
                        resolved_alerts.append(alert)
                elif alert.alert_type == 'high_margin_usage':
                    if self.balance.margin_usage <= alert.threshold:
                        resolved_alerts.append(alert)
                # Add other alert type checks as needed
            
            # Remove resolved alerts
            for alert in resolved_alerts:
                self.active_alerts.remove(alert)
                self.logger.info(f"Alert resolved: {alert.alert_type}")
    
    # ==========================================================================
    # MONITORING
    # ==========================================================================
    def _monitor_account(self) -> None:
        """Monitor account status"""
        while self._running:
            try:
                # Update calculations
                self._update_balance()
                
                # Check alerts
                self._check_account_alerts()
                self._clear_resolved_alerts()
                
                # Calculate portfolio metrics
                self._calculate_portfolio_metrics()
                
                # Emit account update event
                self.event_manager.emit(Event(
                    EventType.PERFORMANCE,
                    {
                        'type': 'account_update',
                        'net_liquidation': self.balance.net_liquidation,
                        'buying_power': self.balance.buying_power,
                        'margin_usage': self.balance.margin_usage,
                        'daily_pnl': self.balance.daily_pnl,
                        'unrealized_pnl': self.balance.unrealized_pnl,
                        'realized_pnl': self.balance.realized_pnl
                    },
                    priority=EventPriority.LOW
                ))
                
                time.sleep(ACCOUNT_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in account monitor: {e}")
    
    def _calculate_portfolio_metrics(self) -> None:
        """Calculate portfolio-level metrics"""
        with self._account_lock:
            if not self.portfolio:
                return
            
            # Portfolio composition
            total_value = sum(item.market_value for item in self.portfolio.values())
            
            # Concentration risk
            if total_value > 0:
                for symbol, item in self.portfolio.items():
                    concentration = abs(item.market_value) / total_value
                    
                    if concentration > self.risk_parameters['position_size_limit']:
                        self._process_alert(AccountAlert(
                            alert_type='position_concentration',
                            severity='warning',
                            message=f"{symbol} exceeds {self.risk_parameters['position_size_limit']*100}% of portfolio",
                            value=concentration * 100,
                            threshold=self.risk_parameters['position_size_limit'] * 100
                        ))
    
    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _register_ib_callbacks(self) -> None:
        """Register IB API callbacks"""
        self.ib_client.register_callback('managedAccounts', self._on_managed_accounts)
        self.ib_client.register_callback('updateAccountValue', self._on_account_value)
        self.ib_client.register_callback('updatePortfolio', self._on_portfolio_update)
        self.ib_client.register_callback('updateAccountTime', self._on_account_time)
        self.ib_client.register_callback('accountSummary', self._on_account_summary)
        self.ib_client.register_callback('accountSummaryEnd', self._on_account_summary_end)
    
    def _on_managed_accounts(self, accountsList: str) -> None:
        """Handle managed accounts list from IB"""
        accounts = accountsList.split(',')
        if accounts:
            self.account_id = accounts[0]  # Use first account
            self.logger.info(f"Using account: {self.account_id}")
            
            # Request account updates
            self.ib_client.reqAccountUpdates(True, self.account_id)
            
            # Request account summary
            self.ib_client.reqAccountSummary(
                1,  # Request ID
                "All",  # Group
                ",".join(ACCOUNT_KEYS)  # Tags
            )
    
    def _on_account_value(self, key: str, val: str, currency: str, accountName: str) -> None:
        """Handle account value update from IB"""
        with self._account_lock:
            try:
                # Convert value to float
                value = float(val)
                
                # Store by currency
                self._account_values[currency][key] = value
                
                # Log important values
                if key in ['NetLiquidation', 'BuyingPower', 'DailyPnL']:
                    self.logger.debug(f"{key}: {value} {currency}")
                    
            except ValueError:
                # Some values might be strings (e.g., account type)
                self._account_values[currency][key] = val
    
    def _on_portfolio_update(self, contract, position: float, marketPrice: float,
                            marketValue: float, averageCost: float, unrealizedPNL: float,
                            realizedPNL: float, accountName: str) -> None:
        """Handle portfolio update from IB"""
        with self._account_lock:
            if position != 0:
                # Create or update portfolio item
                item = PortfolioItem(
                    symbol=contract.symbol,
                    position=int(position),
                    market_value=marketValue,
                    average_cost=averageCost,
                    unrealized_pnl=unrealizedPNL,
                    realized_pnl=realizedPNL
                )
                
                self.portfolio[contract.symbol] = item
            else:
                # Remove if position is closed
                self.portfolio.pop(contract.symbol, None)
    
    def _on_account_time(self, timeStamp: str) -> None:
        """Handle account time update from IB"""
        self.logger.debug(f"Account update time: {timeStamp}")
    
    def _on_account_summary(self, reqId: int, account: str, tag: str, value: str,
                           currency: str) -> None:
        """Handle account summary update from IB"""
        # Similar to account value updates
        self._on_account_value(tag, value, currency, account)
    
    def _on_account_summary_end(self, reqId: int) -> None:
        """Handle end of account summary from IB"""
        self.logger.info("Account summary update complete")
    
    # ==========================================================================
    # POSITION SIZING
    # ==========================================================================
    def calculate_position_size(
        self,
        strategy_type: str,
        risk_per_trade: float = 0.02,
        stop_loss_percent: Optional[float] = None
    ) -> int:
        """
        Calculate appropriate position size based on account.
        
        Args:
            strategy_type: Type of strategy
            risk_per_trade: Risk per trade as percentage of account
            stop_loss_percent: Stop loss percentage for the trade
            
        Returns:
            Position size (number of contracts/shares)
        """
        with self._account_lock:
            # Base calculation on net liquidation
            risk_amount = self.balance.net_liquidation * risk_per_trade
            
            # Ensure we have enough buying power
            max_position_value = min(
                self.balance.buying_power * 0.9,  # Use 90% of buying power
                self.balance.net_liquidation * self.risk_parameters['position_size_limit']
            )
            
            # Calculate position size based on strategy
            if strategy_type == 'option':
                # For options, consider premium and potential loss
                if stop_loss_percent:
                    # Size based on stop loss
                    position_size = int(risk_amount / (stop_loss_percent * 100))
                else:
                    # Size based on premium (assume average $5 per contract)
                    position_size = int(max_position_value / 500)
            else:
                # For stocks
                if stop_loss_percent:
                    # Assume $450 SPY price for calculation
                    position_size = int(risk_amount / (450 * stop_loss_percent))
                else:
                    position_size = int(max_position_value / 450)
            
            # Apply limits
            position_size = max(1, min(position_size, 50))  # Between 1 and 50
            
            return position_size
    
    def has_sufficient_buying_power(self, required_amount: float) -> bool:
        """
        Check if account has sufficient buying power.
        
        Args:
            required_amount: Amount of buying power required
            
        Returns:
            True if sufficient
        """
        with self._account_lock:
            # Maintain cash reserve
            available = self.balance.buying_power - CASH_RESERVE_MINIMUM
            return available >= required_amount
    
    # ==========================================================================
    # QUERIES
    # ==========================================================================
    def get_account_balance(self) -> AccountBalance:
        """Get current account balance"""
        with self._account_lock:
            return self.balance
    
    def get_portfolio(self) -> Dict[str, PortfolioItem]:
        """Get current portfolio"""
        with self._account_lock:
            return self.portfolio.copy()
    
    def get_buying_power(self) -> float:
        """Get current buying power"""
        with self._account_lock:
            return self.balance.buying_power
    
    def get_margin_usage(self) -> float:
        """Get current margin usage percentage"""
        with self._account_lock:
            return self.balance.margin_usage
    
    def get_daily_pnl(self) -> float:
        """Get daily P&L"""
        with self._account_lock:
            return self.balance.daily_pnl
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get comprehensive account summary"""
        with self._account_lock:
            return {
                'account_id': self.account_id,
                'account_type': self.account_type.value,
                'balance': self.balance.to_dict(),
                'portfolio_count': len(self.portfolio),
                'portfolio_value': sum(item.market_value for item in self.portfolio.values()),
                'active_alerts': len(self.active_alerts),
                'alerts': [
                    {
                        'type': alert.alert_type,
                        'severity': alert.severity,
                        'message': alert.message
                    }
                    for alert in self.active_alerts
                ]
            }
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get risk-related metrics"""
        with self._account_lock:
            return {
                'margin_usage': self.balance.margin_usage,
                'leverage': self.balance.leverage,
                'buying_power_ratio': (
                    self.balance.buying_power / self.balance.net_liquidation 
                    if self.balance.net_liquidation > 0 else 0
                ),
                'excess_liquidity': self.balance.excess_liquidity,
                'cushion': self.balance.cushion,
                'day_trades_remaining': self.balance.day_trades_remaining
            }
    
    def export_balance_history(self) -> pd.DataFrame:
        """Export balance history to DataFrame"""
        if self.balance_history:
            return pd.DataFrame(list(self.balance_history))
        else:
            return pd.DataFrame()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test account manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Mock IB client
    class MockIBClient:
        def __init__(self):
            self.callbacks = defaultdict(list)
        
        def register_callback(self, event, callback):
            self.callbacks[event].append(callback)
        
        def reqManagedAccts(self):
            print("Requesting managed accounts...")
            # Simulate response
            for callback in self.callbacks['managedAccounts']:
                callback("DU1234567")
        
        def reqAccountUpdates(self, subscribe, account):
            print(f"{'Subscribing to' if subscribe else 'Unsubscribing from'} account {account}")
            
            if subscribe:
                # Simulate account value updates
                for callback in self.callbacks['updateAccountValue']:
                    callback('NetLiquidation', '100000', 'BASE', account)
                    callback('BuyingPower', '50000', 'BASE', account)
                    callback('DailyPnL', '1250', 'BASE', account)
                    callback('InitMarginReq', '15000', 'BASE', account)
                    callback('MaintMarginReq', '12000', 'BASE', account)
        
        def reqAccountSummary(self, reqId, groupName, tags):
            print(f"Requesting account summary: {tags}")
    
    # Initialize
    event_manager = EventManager()
    ib_client = MockIBClient()
    account_manager = AccountManager(ib_client, event_manager)
    
    # Start monitoring
    account_manager.start()
    
    # Wait for data
    time.sleep(2)
    
    # Get account summary
    summary = account_manager.get_account_summary()
    print("Account Summary:")
    print(json.dumps(summary, indent=2))
    
    # Calculate position size
    position_size = account_manager.calculate_position_size(
        strategy_type='option',
        risk_per_trade=0.02,
        stop_loss_percent=0.20
    )
    print(f"\nRecommended position size: {position_size} contracts")
    
    # Check buying power
    required = 10000
    sufficient = account_manager.has_sufficient_buying_power(required)
    print(f"\nSufficient buying power for ${required}: {sufficient}")
    
    # Get risk metrics
    risk_metrics = account_manager.get_risk_metrics()
    print("\nRisk Metrics:")
    print(json.dumps(risk_metrics, indent=2))
    
    # Stop
    account_manager.stop()