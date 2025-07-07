#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB10_IBDataTypes.py
Group: B (Broker Integration)
Purpose: Enhanced IB data type definitions and conversions

Description:
    This module provides comprehensive data type definitions for IB integration.
    It includes all IB-specific types for contracts, orders, executions, market data,
    and account information. The module provides validation, serialization, and
    conversion utilities to ensure type safety and data integrity throughout the
    broker integration layer.

Author: Mohamed Talib
Date: 2025-01-04
Version: 2.0 (Enhanced with complete IB types)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Dict, Any, List, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, date, time
import json
import pickle
from decimal import Decimal

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default values for IB contracts
DEFAULT_EXCHANGE = "SMART"
DEFAULT_CURRENCY = "USD"
DEFAULT_MULTIPLIER = "100"

# Contract ID ranges
COMBO_CONTRACT_ID = 28812380  # IB's special ID for combos

# ==============================================================================
# ENUMS - COMPREHENSIVE IB TYPES
# ==============================================================================

class SecurityType(Enum):
    """Security types for IB contracts"""
    STOCK = "STK"
    OPTION = "OPT"
    FUTURE = "FUT"
    FOREX = "CASH"
    INDEX = "IND"
    COMMODITY = "CMDTY"
    BOND = "BOND"
    FUND = "FUND"
    CFD = "CFD"
    CRYPTO = "CRYPTO"
    COMBO = "BAG"
    WARRANT = "WAR"
    STRUCTURED = "IOPT"

class OrderAction(Enum):
    """Order actions"""
    BUY = "BUY"
    SELL = "SELL"

class OrderType(Enum):
    """Comprehensive order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    TRAILING_STOP = "TRAIL"
    MARKET_IF_TOUCHED = "MIT"
    LIMIT_IF_TOUCHED = "LIT"
    PEGGED_TO_MARKET = "PEG MKT"
    PEGGED_TO_MIDPOINT = "PEG MID"
    PEGGED_TO_BENCHMARK = "PEG BENCH"
    SNAP_TO_MARKET = "SNAP MKT"
    SNAP_TO_MIDPOINT = "SNAP MID"
    VWAP = "VWAP"
    RELATIVE = "REL"
    BOX_TOP = "BOX TOP"
    LIMIT_ON_CLOSE = "LOC"
    MARKET_ON_CLOSE = "MOC"
    MARKET_ON_OPEN = "MOO"
    PEGGED_TO_PRIMARY = "PEG PRIM"
    VOLATILITY = "VOL"
    
class OrderStatus(Enum):
    """Order status values"""
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    API_PENDING = "ApiPending"
    API_CANCELLED = "ApiCancelled"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartiallyFilled"
    INACTIVE = "Inactive"
    UNKNOWN = "Unknown"

class TimeInForce(Enum):
    """Time in force options"""
    DAY = "DAY"
    GTC = "GTC"  # Good till cancelled
    IOC = "IOC"  # Immediate or cancel
    FOK = "FOK"  # Fill or kill
    GTD = "GTD"  # Good till date
    OPG = "OPG"  # Opening
    DTC = "DTC"  # Day till cancelled
    
class OrderConditionType(Enum):
    """Order condition types"""
    PRICE = 1
    TIME = 3
    MARGIN = 4
    EXECUTION = 5
    VOLUME = 6
    PERCENT_CHANGE = 7

class TriggerMethod(Enum):
    """Trigger methods for stop orders"""
    DEFAULT = 0
    DOUBLE_BID_ASK = 1
    LAST = 2
    DOUBLE_LAST = 3
    BID_ASK = 4
    LAST_OR_BID_ASK = 7
    MID_POINT = 8

class AlgoStrategy(Enum):
    """IB algorithmic trading strategies"""
    VWAP = "Vwap"
    TWAP = "Twap"
    PERCENT_OF_VOLUME = "PctVol"
    TARGET_CLOSE = "TargetClose"
    ARRIVAL_PRICE = "ArrivalPx"
    DARK_ICE = "DarkIce"
    ICEBERG = "IceBerg"
    ADAPTIVE = "Adaptive"
    
class BarSize(Enum):
    """Bar sizes for historical data"""
    SEC_1 = "1 secs"
    SEC_5 = "5 secs"
    SEC_10 = "10 secs"
    SEC_15 = "15 secs"
    SEC_30 = "30 secs"
    MIN_1 = "1 min"
    MIN_2 = "2 mins"
    MIN_3 = "3 mins"
    MIN_5 = "5 mins"
    MIN_10 = "10 mins"
    MIN_15 = "15 mins"
    MIN_20 = "20 mins"
    MIN_30 = "30 mins"
    HOUR_1 = "1 hour"
    HOUR_2 = "2 hours"
    HOUR_3 = "3 hours"
    HOUR_4 = "4 hours"
    HOUR_8 = "8 hours"
    DAY_1 = "1 day"
    WEEK_1 = "1 week"
    MONTH_1 = "1 month"

class WhatToShow(Enum):
    """What to show for historical data"""
    TRADES = "TRADES"
    MIDPOINT = "MIDPOINT"
    BID = "BID"
    ASK = "ASK"
    BID_ASK = "BID_ASK"
    HISTORICAL_VOLATILITY = "HISTORICAL_VOLATILITY"
    IMPLIED_VOLATILITY = "OPTION_IMPLIED_VOLATILITY"
    YIELD_BID = "YIELD_BID"
    YIELD_ASK = "YIELD_ASK"
    YIELD_BID_ASK = "YIELD_BID_ASK"
    YIELD_LAST = "YIELD_LAST"

class TickType(Enum):
    """Tick types for market data"""
    BID_SIZE = 0
    BID = 1
    ASK = 2
    ASK_SIZE = 3
    LAST = 4
    LAST_SIZE = 5
    HIGH = 6
    LOW = 7
    VOLUME = 8
    CLOSE = 9
    BID_OPTION_COMPUTATION = 10
    ASK_OPTION_COMPUTATION = 11
    LAST_OPTION_COMPUTATION = 12
    MODEL_OPTION = 13
    OPEN = 14
    LOW_13_WEEK = 15
    HIGH_13_WEEK = 16
    LOW_26_WEEK = 17
    HIGH_26_WEEK = 18
    LOW_52_WEEK = 19
    HIGH_52_WEEK = 20
    AVG_VOLUME = 21
    OPEN_INTEREST = 22
    OPTION_HISTORICAL_VOL = 23
    OPTION_IMPLIED_VOL = 24
    OPTION_BID_EXCH = 25
    OPTION_ASK_EXCH = 26
    OPTION_CALL_OPEN_INTEREST = 27
    OPTION_PUT_OPEN_INTEREST = 28
    OPTION_CALL_VOLUME = 29
    OPTION_PUT_VOLUME = 30
    INDEX_FUTURE_PREMIUM = 31
    BID_EXCH = 32
    ASK_EXCH = 33
    AUCTION_VOLUME = 34
    AUCTION_PRICE = 35
    AUCTION_IMBALANCE = 36
    MARK_PRICE = 37
    BID_EFP_COMPUTATION = 38
    ASK_EFP_COMPUTATION = 39
    LAST_EFP_COMPUTATION = 40
    OPEN_EFP_COMPUTATION = 41
    HIGH_EFP_COMPUTATION = 42
    LOW_EFP_COMPUTATION = 43
    CLOSE_EFP_COMPUTATION = 44
    LAST_TIMESTAMP = 45
    SHORTABLE = 46
    RT_VOLUME = 48
    HALTED = 49
    BID_YIELD = 50
    ASK_YIELD = 51
    LAST_YIELD = 52
    CUST_OPTION_COMPUTATION = 53
    TRADE_COUNT = 54
    TRADE_RATE = 55
    VOLUME_RATE = 56
    LAST_RTH_TRADE = 57
    RT_HISTORICAL_VOL = 58
    IB_DIVIDENDS = 59
    BOND_FACTOR_MULTIPLIER = 60
    REGULATORY_IMBALANCE = 61
    NEWS_TICK = 62
    SHORT_TERM_VOLUME_3_MIN = 63
    SHORT_TERM_VOLUME_5_MIN = 64
    SHORT_TERM_VOLUME_10_MIN = 65
    DELAYED_BID = 66
    DELAYED_ASK = 67
    DELAYED_LAST = 68
    DELAYED_BID_SIZE = 69
    DELAYED_ASK_SIZE = 70
    DELAYED_LAST_SIZE = 71
    DELAYED_HIGH = 72
    DELAYED_LOW = 73
    DELAYED_VOLUME = 74
    DELAYED_CLOSE = 75
    DELAYED_OPEN = 76
    RT_TRD_VOLUME = 77
    CREDITMAN_MARK_PRICE = 78
    CREDITMAN_SLOW_MARK_PRICE = 79
    DELAYED_BID_OPTION = 80
    DELAYED_ASK_OPTION = 81
    DELAYED_LAST_OPTION = 82
    DELAYED_MODEL_OPTION = 83
    LAST_EXCH = 84
    LAST_REG_TIME = 85
    FUTURES_OPEN_INTEREST = 86
    AVG_OPT_VOLUME = 87
    DELAYED_LAST_TIMESTAMP = 88
    SHORTABLE_SHARES = 89

# ==============================================================================
# DATA STRUCTURES - ENHANCED
# ==============================================================================

@dataclass
class IBContract:
    """
    Enhanced IB Contract representation.
    
    Represents any tradeable instrument in the IB system with all possible fields.
    """
    symbol: str
    sec_type: SecurityType
    exchange: str = DEFAULT_EXCHANGE
    currency: str = DEFAULT_CURRENCY
    local_symbol: str = ""
    primary_exchange: str = ""
    
    # Identifiers
    con_id: Optional[int] = None
    sec_id: Optional[str] = None
    sec_id_type: Optional[str] = None  # ISIN, CUSIP, etc.
    
    # Option-specific fields
    last_trade_date_or_contract_month: Optional[str] = None
    strike: Optional[float] = None
    right: Optional[str] = None  # "C" for Call, "P" for Put
    multiplier: Optional[str] = None
    
    # Combo fields
    combo_legs: Optional[List['ComboLeg']] = None
    combo_legs_description: Optional[str] = None
    
    # Additional fields
    include_expired: bool = False
    trading_class: Optional[str] = None
    min_tick: Optional[float] = None
    md_size_multiplier: Optional[int] = None
    aggr_group: Optional[int] = None
    under_symbol: Optional[str] = None
    under_sec_type: Optional[str] = None
    market_rule_ids: Optional[str] = None
    real_expiration_date: Optional[str] = None
    stock_type: Optional[str] = None
    
    # Bond-specific
    cusip: Optional[str] = None
    ratings: Optional[str] = None
    desc_append: Optional[str] = None
    bond_type: Optional[str] = None
    coupon_type: Optional[str] = None
    callable: Optional[bool] = None
    putable: Optional[bool] = None
    coupon: Optional[float] = None
    convertible: Optional[bool] = None
    maturity: Optional[str] = None
    issue_date: Optional[str] = None
    
    def to_ib_contract(self):
        """Convert to ib_insync Contract object."""
        from ib_insync import Contract, ComboLeg as IBComboLeg
        
        contract = Contract()
        contract.symbol = self.symbol
        contract.secType = self.sec_type.value
        contract.exchange = self.exchange
        contract.currency = self.currency
        
        if self.con_id:
            contract.conId = self.con_id
        if self.local_symbol:
            contract.localSymbol = self.local_symbol
        if self.primary_exchange:
            contract.primaryExchange = self.primary_exchange
        
        # Option fields
        if self.last_trade_date_or_contract_month:
            contract.lastTradeDateOrContractMonth = self.last_trade_date_or_contract_month
        if self.strike:
            contract.strike = self.strike
        if self.right:
            contract.right = self.right
        if self.multiplier:
            contract.multiplier = self.multiplier
            
        # Combo legs
        if self.combo_legs:
            contract.comboLegs = []
            for leg in self.combo_legs:
                ib_leg = IBComboLeg()
                ib_leg.conId = leg.con_id
                ib_leg.ratio = leg.ratio
                ib_leg.action = leg.action
                ib_leg.exchange = leg.exchange
                contract.comboLegs.append(ib_leg)
        
        return contract

@dataclass
class ComboLeg:
    """Combo leg definition for multi-leg orders."""
    con_id: int
    ratio: int = 1
    action: str = "BUY"  # BUY or SELL
    exchange: str = DEFAULT_EXCHANGE
    open_close: int = 0  # 0=Same, 1=Open, 2=Close
    short_sale_slot: int = 0
    designated_location: str = ""
    exempt_code: int = -1

@dataclass
class IBOrder:
    """
    Enhanced IB Order representation with all order types and attributes.
    """
    action: OrderAction
    total_quantity: float
    order_type: OrderType
    
    # Price fields
    lmt_price: Optional[float] = None
    aux_price: Optional[float] = None  # Stop price
    
    # Time in force
    tif: TimeInForce = TimeInForce.DAY
    
    # Order identification
    order_id: Optional[int] = None
    client_id: Optional[int] = None
    perm_id: Optional[int] = None
    parent_id: Optional[int] = None
    
    # Status
    status: Optional[OrderStatus] = None
    filled: float = 0.0
    remaining: float = 0.0
    avg_fill_price: float = 0.0
    
    # Account
    account: Optional[str] = None
    
    # Advanced order attributes
    oca_group: Optional[str] = None
    oca_type: Optional[int] = None  # 1=Cancel all, 2=Reduce qty, 3=Reduce qty with block
    order_ref: Optional[str] = None
    transmit: bool = True
    
    # Execution options
    display_size: Optional[int] = None
    trigger_method: Optional[TriggerMethod] = None
    outside_rth: bool = False
    hidden: bool = False
    
    # Discretionary orders
    discretionary_amt: float = 0.0
    
    # Good after time
    good_after_time: Optional[str] = None
    good_till_date: Optional[str] = None
    
    # Financial advisors
    fa_group: Optional[str] = None
    fa_method: Optional[str] = None
    fa_percentage: Optional[str] = None
    fa_profile: Optional[str] = None
    
    # Institutional orders
    designated_location: Optional[str] = None
    open_close: Optional[str] = None  # "O"=Open, "C"=Close
    origin: int = 0  # 0=Customer, 1=Firm
    short_sale_slot: int = 0  # 1=Broker, 2=Third party
    exempt_code: int = -1
    
    # SMART routing
    smart_routing_params: Optional[List['TagValue']] = None
    
    # Clearing
    clearing_account: Optional[str] = None
    clearing_intent: Optional[str] = None  # IB, Away, PTA
    
    # Algo orders
    algo_strategy: Optional[AlgoStrategy] = None
    algo_params: Optional[List['TagValue']] = None
    algo_id: Optional[str] = None
    
    # Conditional orders
    conditions: Optional[List['OrderCondition']] = None
    conditions_cancel_order: bool = False
    
    # Adjusted orders
    adjusted_order_type: Optional[str] = None
    trigger_price: Optional[float] = None
    trail_stop_price: Optional[float] = None
    lmt_price_offset: Optional[float] = None
    adjusted_stop_price: Optional[float] = None
    adjusted_stop_limit_price: Optional[float] = None
    adjusted_trailing_amount: Optional[float] = None
    adjustable_trailing_unit: Optional[int] = None
    
    # Scale orders
    scale_init_level_size: Optional[int] = None
    scale_subs_level_size: Optional[int] = None
    scale_price_increment: Optional[float] = None
    scale_price_adjust_value: Optional[float] = None
    scale_price_adjust_interval: Optional[int] = None
    scale_profit_offset: Optional[float] = None
    scale_auto_reset: bool = False
    scale_init_position: Optional[int] = None
    scale_init_fill_qty: Optional[int] = None
    scale_random_percent: bool = False
    
    # Hedge orders
    hedge_type: Optional[str] = None  # "D"=Delta, "B"=Beta, "F"=FX, "P"=Pair
    hedge_param: Optional[str] = None
    
    # Volatility orders
    volatility: Optional[float] = None
    volatility_type: Optional[int] = None  # 1=Daily, 2=Annual
    continuous_update: bool = False
    reference_price_type: Optional[int] = None  # 1=Bid/Ask midpoint, 2=BidOrAsk
    delta_neutral_order_type: Optional[str] = None
    delta_neutral_aux_price: Optional[float] = None
    delta_neutral_con_id: Optional[int] = None
    delta_neutral_open_close: Optional[str] = None
    delta_neutral_short_sale: bool = False
    delta_neutral_short_sale_slot: int = 0
    delta_neutral_designated_location: Optional[str] = None
    
    # Pegged orders
    basis_points: Optional[float] = None
    basis_points_type: Optional[int] = None
    
    # Soft dollar tiers
    soft_dollar_tier: Optional['SoftDollarTier'] = None
    
    # Order combo legs
    order_combo_legs: Optional[List['OrderComboLeg']] = None
    
    # Don't use auto price for hedge
    dont_use_auto_price_for_hedge: bool = False
    
    # Cancellation
    cancel_after: Optional[int] = None  # Cancel after n seconds
    
    # Ext operator
    ext_operator: Optional[str] = None
    
    # Native cash quantity
    cash_qty: Optional[float] = None
    
    # Mifid execution
    mifid_execution_algo: Optional[str] = None
    mifid_execution_decision: Optional[str] = None
    
    # Customer account
    customer_account: Optional[str] = None
    
    # Professional customer
    professional_customer: bool = False
    
    # Notify on fill
    notify_on_fill: bool = False
    
    # Shareholder
    shareholder: Optional[str] = None
    
    # Imbalance only
    imbalance_only: bool = False
    
    # Route marketable to exchange
    route_marketable_to_exchange: bool = False
    
    # Snapshot market order
    snapshot_mkt_order: bool = False
    
    def to_ib_order(self):
        """Convert to ib_insync Order object."""
        from ib_insync import Order, OrderCondition, TagValue
        
        order = Order()
        order.action = self.action.value
        order.totalQuantity = self.total_quantity
        order.orderType = self.order_type.value
        
        if self.lmt_price is not None:
            order.lmtPrice = self.lmt_price
        if self.aux_price is not None:
            order.auxPrice = self.aux_price
            
        order.tif = self.tif.value
        
        if self.order_id:
            order.orderId = self.order_id
        if self.client_id:
            order.clientId = self.client_id
        if self.perm_id:
            order.permId = self.perm_id
        if self.parent_id:
            order.parentId = self.parent_id
            
        if self.account:
            order.account = self.account
            
        # Copy all other attributes
        for attr in ['ocaGroup', 'ocaType', 'orderRef', 'transmit', 'displaySize',
                    'outsideRth', 'hidden', 'discretionaryAmt', 'goodAfterTime',
                    'goodTillDate', 'faGroup', 'faMethod', 'faPercentage', 'faProfile']:
            value = getattr(self, self._to_snake_case(attr), None)
            if value is not None:
                setattr(order, attr, value)
        
        return order
    
    @staticmethod
    def _to_snake_case(camel_case: str) -> str:
        """Convert camelCase to snake_case."""
        result = []
        for i, char in enumerate(camel_case):
            if char.isupper() and i > 0:
                result.append('_')
            result.append(char.lower())
        return ''.join(result)

@dataclass
class TagValue:
    """Tag-value pair for algo orders and smart routing."""
    tag: str
    value: str

@dataclass
class OrderCondition:
    """Base order condition."""
    condition_type: OrderConditionType

@dataclass
class PriceCondition(OrderCondition):
    """Price-based order condition."""
    condition_type: OrderConditionType = OrderConditionType.PRICE
    con_id: int = 0
    exchange: str = ""
    is_more: bool = True
    trigger_price: float = 0.0

@dataclass
class TimeCondition(OrderCondition):
    """Time-based order condition."""
    condition_type: OrderConditionType = OrderConditionType.TIME
    is_more: bool = True
    time: str = ""  # YYYYMMDD HH:MM:SS

@dataclass
class MarginCondition(OrderCondition):
    """Margin-based order condition."""
    condition_type: OrderConditionType = OrderConditionType.MARGIN
    is_more: bool = True
    percent: float = 0.0

@dataclass
class ExecutionCondition(OrderCondition):
    """Execution-based order condition."""
    condition_type: OrderConditionType = OrderConditionType.EXECUTION
    exchange: str = ""
    sec_type: str = ""
    symbol: str = ""

@dataclass
class VolumeCondition(OrderCondition):
    """Volume-based order condition."""
    condition_type: OrderConditionType = OrderConditionType.VOLUME
    con_id: int = 0
    exchange: str = ""
    is_more: bool = True
    volume: int = 0

@dataclass
class PercentChangeCondition(OrderCondition):
    """Percent change order condition."""
    condition_type: OrderConditionType = OrderConditionType.PERCENT_CHANGE
    con_id: int = 0
    exchange: str = ""
    is_more: bool = True
    percent_change: float = 0.0

@dataclass
class SoftDollarTier:
    """Soft dollar tier for commission."""
    name: str
    value: str
    display_name: Optional[str] = None

@dataclass
class OrderComboLeg:
    """Order combo leg for complex orders."""
    price: Optional[float] = None

@dataclass
class IBPosition:
    """
    Enhanced IB Position representation with all fields.
    """
    contract: IBContract
    position: float
    market_price: float
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    account: str
    
    # Additional fields
    last_update: Optional[datetime] = None

@dataclass
class IBExecution:
    """
    IB Execution representation with complete fill details.
    """
    exec_id: str
    time: str
    account: str
    exchange: str
    side: str
    shares: float
    price: float
    perm_id: int
    client_id: int
    order_id: int
    liquidation: int
    cum_qty: float
    avg_price: float
    order_ref: Optional[str] = None
    ev_rule: Optional[str] = None
    ev_multiplier: Optional[float] = None
    model_code: Optional[str] = None
    last_liquidity: Optional[int] = None
    
    # Additional execution details
    exec_cost: Optional[float] = None
    exec_commission: Optional[float] = None
    yield_redemption_date: Optional[int] = None  # YYYYMMDD
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class IBCommissionReport:
    """IB Commission report with all fee details."""
    exec_id: str
    commission: float
    currency: str
    realized_pnl: float
    yield_val: float
    yield_redemption_date: int  # YYYYMMDD
    
    # Additional fee breakdown
    broker_commission: Optional[float] = None
    exchange_fee: Optional[float] = None
    regulatory_fee: Optional[float] = None
    clearing_fee: Optional[float] = None
    other_fees: Optional[float] = None
    
    # Tax-related
    tax_amount: Optional[float] = None
    tax_basis: Optional[float] = None

@dataclass
class IBTrade:
    """
    Enhanced IB Trade representation.
    
    Represents a complete trade including order, contract, and execution details.
    """
    contract: IBContract
    order: IBOrder
    order_status: 'OrderState'
    fills: List[IBExecution] = field(default_factory=list)
    commission_reports: List[IBCommissionReport] = field(default_factory=list)
    log: List['TradeLogEntry'] = field(default_factory=list)
    
    # Computed fields
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.order_status.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.order_status.status in [
            OrderStatus.PENDING_SUBMIT,
            OrderStatus.PRE_SUBMITTED,
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED
        ]
    
    @property
    def filled_quantity(self) -> float:
        """Get total filled quantity."""
        return sum(fill.shares for fill in self.fills)
    
    @property
    def avg_fill_price(self) -> float:
        """Calculate average fill price."""
        if not self.fills:
            return 0.0
        total_value = sum(fill.shares * fill.price for fill in self.fills)
        total_shares = sum(fill.shares for fill in self.fills)
        return total_value / total_shares if total_shares > 0 else 0.0
    
    @property
    def total_commission(self) -> float:
        """Get total commission."""
        return sum(report.commission for report in self.commission_reports)

@dataclass
class OrderState:
    """Order state with complete status information."""
    status: OrderStatus
    filled: float = 0.0
    remaining: float = 0.0
    avg_fill_price: float = 0.0
    perm_id: Optional[int] = None
    parent_id: Optional[int] = None
    last_fill_price: float = 0.0
    client_id: Optional[int] = None
    why_held: Optional[str] = None
    mkt_cap_price: Optional[float] = None
    
    # Completed status
    completed_time: Optional[str] = None
    completed_status: Optional[str] = None
    
    # Commission
    commission: Optional[float] = None
    min_commission: Optional[float] = None
    max_commission: Optional[float] = None
    commission_currency: Optional[str] = None
    
    # Warning text
    warning_text: Optional[str] = None
    
    # Initial margin
    init_margin_before: Optional[str] = None
    init_margin_change: Optional[str] = None
    init_margin_after: Optional[str] = None
    
    # Maintenance margin
    maint_margin_before: Optional[str] = None
    maint_margin_change: Optional[str] = None
    maint_margin_after: Optional[str] = None
    
    # Equity with loan
    equity_with_loan_before: Optional[str] = None
    equity_with_loan_change: Optional[str] = None
    equity_with_loan_after: Optional[str] = None

@dataclass
class TradeLogEntry:
    """Trade log entry for audit trail."""
    time: datetime
    status: OrderStatus
    message: str
    error_code: Optional[int] = None

@dataclass
class IBMarketData:
    """
    Enhanced IB Market data representation.
    
    Contains all possible market data fields including Greeks for options.
    """
    contract: IBContract
    
    # Price fields
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    
    # Size fields
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    last_size: Optional[int] = None
    
    # Volume and counts
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    trade_count: Optional[int] = None
    trade_rate: Optional[float] = None
    volume_rate: Optional[float] = None
    
    # Option specific
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    
    # Option volume/OI
    option_call_open_interest: Optional[int] = None
    option_put_open_interest: Optional[int] = None
    option_call_volume: Optional[int] = None
    option_put_volume: Optional[int] = None
    
    # Historical volatility
    historical_volatility: Optional[float] = None
    historical_volatility_close: Optional[float] = None
    
    # Price statistics
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    week_13_high: Optional[float] = None
    week_13_low: Optional[float] = None
    week_26_high: Optional[float] = None
    week_26_low: Optional[float] = None
    
    # Market internals
    put_call_ratio: Optional[float] = None
    put_call_interest_ratio: Optional[float] = None
    
    # Dividends
    dividends: Optional[float] = None
    
    # Bond specific
    bond_factor_multiplier: Optional[float] = None
    
    # Regulatory
    regulatory_imbalance: Optional[float] = None
    
    # Mark price
    mark_price: Optional[float] = None
    
    # Auction
    auction_volume: Optional[int] = None
    auction_price: Optional[float] = None
    auction_imbalance: Optional[int] = None
    
    # Real-time volume
    rt_volume: Optional[str] = None
    rt_historical_vol: Optional[float] = None
    rt_trade_volume: Optional[int] = None
    
    # Shortable
    shortable: Optional[float] = None
    shortable_shares: Optional[int] = None
    
    # Halted
    halted: Optional[int] = None
    
    # Index future premium
    index_future_premium: Optional[float] = None
    
    # EFP values
    bid_efp: Optional[float] = None
    ask_efp: Optional[float] = None
    last_efp: Optional[float] = None
    open_efp: Optional[float] = None
    high_efp: Optional[float] = None
    low_efp: Optional[float] = None
    close_efp: Optional[float] = None
    
    # Yield
    bid_yield: Optional[float] = None
    ask_yield: Optional[float] = None
    last_yield: Optional[float] = None
    
    # Timestamps
    last_timestamp: Optional[datetime] = None
    
    # News
    news_tick: Optional[str] = None
    
    # Short-term volume
    short_term_volume_3: Optional[int] = None
    short_term_volume_5: Optional[int] = None
    short_term_volume_10: Optional[int] = None
    
    # Delayed data (when real-time not subscribed)
    delayed_bid: Optional[float] = None
    delayed_ask: Optional[float] = None
    delayed_last: Optional[float] = None
    delayed_bid_size: Optional[int] = None
    delayed_ask_size: Optional[int] = None
    delayed_last_size: Optional[int] = None
    delayed_high: Optional[float] = None
    delayed_low: Optional[float] = None
    delayed_volume: Optional[int] = None
    delayed_close: Optional[float] = None
    delayed_open: Optional[float] = None
    
    # Exchange info
    last_exchange: Optional[str] = None
    bid_exchange: Optional[str] = None
    ask_exchange: Optional[str] = None
    
    # Creditman marks
    creditman_mark_price: Optional[float] = None
    creditman_slow_mark_price: Optional[float] = None
    
    # Average option volume
    avg_opt_volume: Optional[int] = None
    
    # Futures open interest
    futures_open_interest: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}

@dataclass
class IBBar:
    """Historical bar data."""
    date: Union[date, datetime]
    open: float
    high: float
    low: float
    close: float
    volume: int
    average: float
    bar_count: int
    
    # Additional fields for some bar types
    wap: Optional[float] = None  # Weighted average price
    has_gaps: Optional[bool] = None

@dataclass
class IBTickData:
    """Real-time tick data."""
    time: datetime
    tick_type: TickType
    value: Union[float, int, str]
    
    # Additional tick attributes
    tick_attrib: Optional['TickAttrib'] = None
    
    # For bid/ask ticks
    can_auto_execute: Optional[bool] = None
    past_limit: Optional[bool] = None
    pre_open: Optional[bool] = None

@dataclass
class TickAttrib:
    """Tick attributes."""
    can_auto_execute: bool = False
    past_limit: bool = False
    pre_open: bool = False

@dataclass
class IBAccountValue:
    """Account value entry."""
    account: str
    tag: str
    value: str
    currency: str
    model_code: Optional[str] = None

@dataclass
class IBPortfolioItem:
    """Portfolio item with position and P&L."""
    contract: IBContract
    position: float
    market_price: float
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    account: str

@dataclass
class IBOrderBook:
    """Level 2 order book data."""
    symbol: str
    time: datetime
    bids: List[Tuple[float, int, str]] = field(default_factory=list)  # price, size, exchange
    asks: List[Tuple[float, int, str]] = field(default_factory=list)  # price, size, exchange
    
    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price."""
        return self.bids[0][0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price."""
        return self.asks[0][0] if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

# ==============================================================================
# TYPE ALIASES
# ==============================================================================
ContractId = int
OrderId = int
TickerId = int
ExecutionId = str
RequestId = int

# ==============================================================================
# CONVERSION AND VALIDATION CLASS
# ==============================================================================

class IBDataTypeManager:
    """
    Enhanced manager class for IB data types with validation and conversion.
    
    Provides comprehensive validation, conversion, and serialization utilities
    for all IB data types, ensuring data integrity throughout the system.
    """
    
    def __init__(self):
        """Initialize the IB data type manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Validation rules
        self._setup_validation_rules()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    def _setup_validation_rules(self):
        """Setup validation rules for different data types."""
        self.validation_rules = {
            'symbol': lambda x: isinstance(x, str) and 1 <= len(x) <= 12,
            'strike': lambda x: isinstance(x, (int, float)) and x > 0,
            'quantity': lambda x: isinstance(x, (int, float)) and x > 0,
            'price': lambda x: isinstance(x, (int, float)) and x >= 0,
            'expiry': lambda x: isinstance(x, str) and len(x) == 8 and x.isdigit(),
            'right': lambda x: x in ['C', 'P', 'CALL', 'PUT']
        }
    
    # ==========================================================================
    # CONTRACT CREATION AND VALIDATION
    # ==========================================================================
    
    def create_stock_contract(self, symbol: str, exchange: str = DEFAULT_EXCHANGE,
                            currency: str = DEFAULT_CURRENCY,
                            primary_exchange: str = "") -> IBContract:
        """Create and validate a stock contract."""
        if not self.validation_rules['symbol'](symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        
        return IBContract(
            symbol=symbol.upper(),
            sec_type=SecurityType.STOCK,
            exchange=exchange,
            currency=currency,
            primary_exchange=primary_exchange
        )
    
    def create_option_contract(self, symbol: str, last_trade_date: str,
                             strike: float, right: str,
                             exchange: str = DEFAULT_EXCHANGE,
                             currency: str = DEFAULT_CURRENCY,
                             multiplier: str = DEFAULT_MULTIPLIER) -> IBContract:
        """Create and validate an option contract."""
        # Validate inputs
        if not self.validation_rules['symbol'](symbol):
            raise ValueError(f"Invalid symbol: {symbol}")
        if not self.validation_rules['expiry'](last_trade_date):
            raise ValueError(f"Invalid expiry date: {last_trade_date}")
        if not self.validation_rules['strike'](strike):
            raise ValueError(f"Invalid strike price: {strike}")
        if not self.validation_rules['right'](right):
            raise ValueError(f"Invalid right: {right}")
        
        # Normalize right
        right = 'C' if right in ['C', 'CALL'] else 'P'
        
        return IBContract(
            symbol=symbol.upper(),
            sec_type=SecurityType.OPTION,
            exchange=exchange,
            currency=currency,
            last_trade_date_or_contract_month=last_trade_date,
            strike=strike,
            right=right,
            multiplier=multiplier
        )
    
    def create_combo_contract(self, symbol: str, legs: List[ComboLeg],
                            exchange: str = DEFAULT_EXCHANGE,
                            currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create a combo/spread contract."""
        if not legs or len(legs) < 2:
            raise ValueError("Combo contract requires at least 2 legs")
        
        return IBContract(
            symbol=symbol.upper(),
            sec_type=SecurityType.COMBO,
            exchange=exchange,
            currency=currency,
            combo_legs=legs
        )
    
    # ==========================================================================
    # ORDER CREATION AND VALIDATION
    # ==========================================================================
    
    def create_market_order(self, action: OrderAction, quantity: float,
                          **kwargs) -> IBOrder:
        """Create and validate a market order."""
        if not self.validation_rules['quantity'](quantity):
            raise ValueError(f"Invalid quantity: {quantity}")
        
        order = IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.MARKET
        )
        
        # Apply additional attributes
        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)
        
        return order
    
    def create_limit_order(self, action: OrderAction, quantity: float,
                         limit_price: float, **kwargs) -> IBOrder:
        """Create and validate a limit order."""
        if not self.validation_rules['quantity'](quantity):
            raise ValueError(f"Invalid quantity: {quantity}")
        if not self.validation_rules['price'](limit_price):
            raise ValueError(f"Invalid limit price: {limit_price}")
        
        order = IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.LIMIT,
            lmt_price=limit_price
        )
        
        # Apply additional attributes
        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)
        
        return order
    
    def create_stop_order(self, action: OrderAction, quantity: float,
                        stop_price: float, **kwargs) -> IBOrder:
        """Create and validate a stop order."""
        if not self.validation_rules['quantity'](quantity):
            raise ValueError(f"Invalid quantity: {quantity}")
        if not self.validation_rules['price'](stop_price):
            raise ValueError(f"Invalid stop price: {stop_price}")
        
        order = IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.STOP,
            aux_price=stop_price
        )
        
        # Apply additional attributes
        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)
        
        return order
    
    def create_bracket_order(self, parent_order: IBOrder, take_profit: float,
                           stop_loss: float) -> Tuple[IBOrder, IBOrder, IBOrder]:
        """Create a bracket order (parent + take profit + stop loss)."""
        # Validate parent order
        if parent_order.order_type != OrderType.LIMIT:
            raise ValueError("Parent order must be a limit order")
        
        # Create take profit order
        tp_action = OrderAction.SELL if parent_order.action == OrderAction.BUY else OrderAction.BUY
        take_profit_order = self.create_limit_order(
            action=tp_action,
            quantity=parent_order.total_quantity,
            limit_price=take_profit,
            parent_id=parent_order.order_id,
            transmit=False
        )
        
        # Create stop loss order
        stop_loss_order = self.create_stop_order(
            action=tp_action,
            quantity=parent_order.total_quantity,
            stop_price=stop_loss,
            parent_id=parent_order.order_id,
            transmit=True  # Transmit all orders
        )
        
        # Set parent order to not transmit
        parent_order.transmit = False
        
        return parent_order, take_profit_order, stop_loss_order
    
    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    
    def validate_contract(self, contract: IBContract) -> bool:
        """Validate contract completeness and correctness."""
        try:
            # Basic validation
            if not contract.symbol:
                return False
            
            if contract.sec_type == SecurityType.OPTION:
                # Option-specific validation
                if not all([contract.last_trade_date_or_contract_month,
                          contract.strike, contract.right]):
                    return False
                
                if contract.right not in ['C', 'P']:
                    return False
                
                if contract.strike <= 0:
                    return False
            
            elif contract.sec_type == SecurityType.COMBO:
                # Combo validation
                if not contract.combo_legs or len(contract.combo_legs) < 2:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Contract validation error: {e}")
            return False
    
    def validate_order(self, order: IBOrder) -> bool:
        """Validate order completeness and correctness."""
        try:
            # Basic validation
            if order.total_quantity <= 0:
                return False
            
            # Order type specific validation
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if not order.lmt_price or order.lmt_price <= 0:
                    return False
            
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if not order.aux_price or order.aux_price <= 0:
                    return False
            
            # Scale order validation
            if order.scale_init_level_size:
                if not all([order.scale_subs_level_size, order.scale_price_increment]):
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Order validation error: {e}")
            return False
    
    # ==========================================================================
    # SERIALIZATION METHODS
    # ==========================================================================
    
    def contract_to_json(self, contract: IBContract) -> str:
        """Serialize contract to JSON."""
        data = asdict(contract)
        # Convert enums to values
        data['sec_type'] = contract.sec_type.value
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data)
    
    def contract_from_json(self, json_str: str) -> IBContract:
        """Deserialize contract from JSON."""
        data = json.loads(json_str)
        # Convert sec_type back to enum
        data['sec_type'] = SecurityType(data['sec_type'])
        return IBContract(**data)
    
    def order_to_json(self, order: IBOrder) -> str:
        """Serialize order to JSON."""
        data = asdict(order)
        # Convert enums to values
        data['action'] = order.action.value
        data['order_type'] = order.order_type.value
        data['tif'] = order.tif.value
        if order.status:
            data['status'] = order.status.value
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data)
    
    def order_from_json(self, json_str: str) -> IBOrder:
        """Deserialize order from JSON."""
        data = json.loads(json_str)
        # Convert enums back
        data['action'] = OrderAction(data['action'])
        data['order_type'] = OrderType(data['order_type'])
        data['tif'] = TimeInForce(data['tif'])
        if 'status' in data:
            data['status'] = OrderStatus(data['status'])
        return IBOrder(**data)
    
    # ==========================================================================
    # CONVERSION METHODS
    # ==========================================================================
    
    def convert_to_ib_contract(self, spyder_contract: IBContract):
        """Convert SPYDER contract to ib_insync contract."""
        return spyder_contract.to_ib_contract()
    
    def convert_to_ib_order(self, spyder_order: IBOrder):
        """Convert SPYDER order to ib_insync order."""
        return spyder_order.to_ib_order()
    
    def convert_from_ib_position(self, ib_position) -> IBPosition:
        """Convert ib_insync position to SPYDER position."""
        # Extract contract details
        contract = IBContract(
            symbol=ib_position.contract.symbol,
            sec_type=SecurityType(ib_position.contract.secType),
            exchange=ib_position.contract.exchange,
            currency=ib_position.contract.currency
        )
        
        return IBPosition(
            contract=contract,
            position=ib_position.position,
            market_price=ib_position.marketPrice,
            market_value=ib_position.marketValue,
            average_cost=ib_position.avgCost,
            unrealized_pnl=ib_position.unrealizedPNL,
            realized_pnl=ib_position.realizedPNL,
            account=ib_position.account
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

# Singleton instance
_data_type_manager: Optional[IBDataTypeManager] = None

def get_data_type_manager() -> IBDataTypeManager:
    """
    Get singleton IBDataTypeManager instance.
    
    Returns:
        IBDataTypeManager instance
    """
    global _data_type_manager
    if _data_type_manager is None:
        _data_type_manager = IBDataTypeManager()
    return _data_type_manager

# Convenience functions for contract creation
def create_stock_contract(symbol: str, exchange: str = DEFAULT_EXCHANGE,
                        currency: str = DEFAULT_CURRENCY) -> IBContract:
    """Create a stock contract."""
    return get_data_type_manager().create_stock_contract(symbol, exchange, currency)

def create_option_contract(symbol: str, last_trade_date: str, strike: float,
                         right: str, exchange: str = DEFAULT_EXCHANGE,
                         currency: str = DEFAULT_CURRENCY) -> IBContract:
    """Create an option contract."""
    return get_data_type_manager().create_option_contract(
        symbol, last_trade_date, strike, right, exchange, currency
    )

def create_combo_contract(symbol: str, legs: List[ComboLeg],
                        exchange: str = DEFAULT_EXCHANGE,
                        currency: str = DEFAULT_CURRENCY) -> IBContract:
    """Create a combo contract."""
    return get_data_type_manager().create_combo_contract(symbol, legs, exchange, currency)

# Convenience functions for order creation
def create_market_order(action: OrderAction, quantity: float, **kwargs) -> IBOrder:
    """Create a market order."""
    return get_data_type_manager().create_market_order(action, quantity, **kwargs)

def create_limit_order(action: OrderAction, quantity: float,
                     limit_price: float, **kwargs) -> IBOrder:
    """Create a limit order."""
    return get_data_type_manager().create_limit_order(action, quantity, limit_price, **kwargs)

def create_stop_order(action: OrderAction, quantity: float,
                    stop_price: float, **kwargs) -> IBOrder:
    """Create a stop order."""
    return get_data_type_manager().create_stop_order(action, quantity, stop_price, **kwargs)

def create_bracket_order(parent_order: IBOrder, take_profit: float,
                       stop_loss: float) -> Tuple[IBOrder, IBOrder, IBOrder]:
    """Create a bracket order."""
    return get_data_type_manager().create_bracket_order(parent_order, take_profit, stop_loss)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    # Enums
    "SecurityType",
    "OrderAction", 
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "OrderConditionType",
    "TriggerMethod",
    "AlgoStrategy",
    "BarSize",
    "WhatToShow",
    "TickType",
    
    # Data structures
    "IBContract",
    "ComboLeg",
    "IBOrder",
    "TagValue",
    "OrderCondition",
    "PriceCondition",
    "TimeCondition",
    "MarginCondition",
    "ExecutionCondition",
    "VolumeCondition",
    "PercentChangeCondition",
    "SoftDollarTier",
    "OrderComboLeg",
    "IBPosition", 
    "IBExecution",
    "IBCommissionReport",
    "IBTrade",
    "OrderState",
    "TradeLogEntry",
    "IBMarketData",
    "IBBar",
    "IBTickData",
    "TickAttrib",
    "IBAccountValue",
    "IBPortfolioItem",
    "IBOrderBook",
    
    # Type aliases
    "ContractId",
    "OrderId",
    "TickerId",
    "ExecutionId",
    "RequestId",
    
    # Manager class
    "IBDataTypeManager",
    
    # Module functions
    "create_stock_contract",
    "create_option_contract",
    "create_combo_contract",
    "create_market_order",
    "create_limit_order",
    "create_stop_order",
    "create_bracket_order",
    "get_data_type_manager"
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Enhanced IB Data Types Module")
    print("=" * 50)
    
    manager = IBDataTypeManager()
    
    # Test stock contract
    spy = manager.create_stock_contract("SPY")
    print(f"✅ Stock contract: {spy.symbol} ({spy.sec_type.value})")
    
    # Test option contract
    spy_call = manager.create_option_contract("SPY", "20250620", 450.0, "C")
    print(f"✅ Option contract: {spy_call.symbol} {spy_call.last_trade_date_or_contract_month} "
          f"{spy_call.right}{spy_call.strike}")
    
    # Test combo contract
    leg1 = ComboLeg(con_id=1234, ratio=1, action="BUY")
    leg2 = ComboLeg(con_id=5678, ratio=1, action="SELL")
    spread = manager.create_combo_contract("SPY", [leg1, leg2])
    print(f"✅ Combo contract: {spread.symbol} with {len(spread.combo_legs)} legs")
    
    # Test orders
    market_order = manager.create_market_order(OrderAction.BUY, 100)
    print(f"✅ Market order: {market_order.action.value} {market_order.total_quantity}")
    
    limit_order = manager.create_limit_order(OrderAction.SELL, 50, 451.50)
    print(f"✅ Limit order: {limit_order.action.value} {limit_order.total_quantity} @ "
          f"${limit_order.lmt_price}")
    
    # Test bracket order
    parent = manager.create_limit_order(OrderAction.BUY, 100, 450.00)
    parent.order_id = 1
    bracket = manager.create_bracket_order(parent, 455.00, 445.00)
    print(f"✅ Bracket order created with {len(bracket)} orders")
    
    # Test serialization
    json_contract = manager.contract_to_json(spy)
    print(f"\n✅ Contract serialized to JSON ({len(json_contract)} chars)")
    
    # Test deserialization
    restored_contract = manager.contract_from_json(json_contract)
    print(f"✅ Contract restored: {restored_contract.symbol}")
    
    print("\n✅ All enhanced data types tested successfully!")