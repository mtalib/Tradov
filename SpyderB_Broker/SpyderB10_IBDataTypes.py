#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB10_IBDataTypes.py
Purpose: Enhanced IB data type definitions and conversions with modern ib_async integration
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-21 Time: 20:45:00  

Module Description:
    This module provides comprehensive data type definitions for IB integration
    using the modern ib_async library. It includes all IB-specific types for contracts,
    orders, executions, market data, and account information. The module provides
    validation, serialization, and conversion utilities to ensure type safety and
    data integrity throughout the broker integration layer with enhanced IB Gateway
    10.37 compatibility.

Key Features:
    • Modern ib_async integration for enhanced stability
    • Comprehensive data type definitions for all IB entities
    • Type-safe conversion utilities between SPYDER and IB formats
    • Enhanced validation and error handling
    • Serialization support for persistence and messaging

Dependencies:
    • ib_async (modern IB API wrapper)
    • Standard Python typing and dataclasses

Installation Note:
    pip install ib_async
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
    """Order types"""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    RELATIVE = "REL"
    TRAIL = "TRAIL"
    TRAIL_LIMIT = "TRAIL LIMIT"
    MIDPRICE = "MIDPRICE"
    VWAP = "VWAP"
    TWAP = "TWAP"
    ARRIVAL_PRICE = "ARRIVAL PRICE"
    BALANCE_IMPACT_RISK = "BALANCE IMPACT RISK"
    MARKET_ON_CLOSE = "MOC"
    LIMIT_ON_CLOSE = "LOC"
    PEGGED_TO_PRIMARY = "PEGPRIM"
    PEGGED_TO_MARKET = "PEGMKT"
    PEGGED_TO_STOCK = "PEGSTK"
    PEGGED_TO_MIDPOINT = "PEGMID"
    BRACKET = "BRACKET"
    ICEBERG = "ICEBERG"

class TimeInForce(Enum):
    """Time in force values"""
    DAY = "DAY"
    GOOD_TILL_CANCEL = "GTC"
    IMMEDIATE_OR_CANCEL = "IOC"
    GOOD_TILL_DATE = "GTD"
    FILL_OR_KILL = "FOK"
    AT_THE_OPENING = "OPG"
    AT_THE_CLOSE = "CLS"

class OrderStatus(Enum):
    """Order status values"""
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    API_CANCELLED = "ApiCancelled"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"

class TickType(Enum):
    """Market data tick types"""
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

class PositionSide(Enum):
    """Position side enumeration"""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

# ==============================================================================
# DATACLASS DEFINITIONS
# ==============================================================================

@dataclass
class ComboLeg:
    """
    Represents a leg in a combination order.
    """
    con_id: int = 0
    ratio: int = 1
    action: str = "BUY"  # BUY or SELL
    exchange: str = DEFAULT_EXCHANGE
    open_close: int = 0  # 0=Same, 1=Open, 2=Close
    short_sale_slot: int = 0  # 0=NA, 1=clearing broker, 2=third party
    designated_location: str = ""
    exempt_code: int = -1

@dataclass
class DeltaNeutralContract:
    """
    Represents a delta neutral contract for options.
    """
    con_id: int = 0
    delta: float = 0.0
    price: float = 0.0

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
    combo_legs: Optional[List[ComboLeg]] = None
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
        """Convert to ib_async Contract object."""
        from ib_async import Contract, ComboLeg as IBComboLeg
        
        contract = Contract()
        contract.symbol = self.symbol
        contract.secType = self.sec_type.value
        contract.exchange = self.exchange
        contract.currency = self.currency
        contract.localSymbol = self.local_symbol
        contract.primaryExchange = self.primary_exchange
        
        # Set optional fields if present
        if self.con_id is not None:
            contract.conId = self.con_id
        if self.sec_id:
            contract.secId = self.sec_id
        if self.sec_id_type:
            contract.secIdType = self.sec_id_type
        if self.last_trade_date_or_contract_month:
            contract.lastTradeDateOrContractMonth = self.last_trade_date_or_contract_month
        if self.strike is not None:
            contract.strike = self.strike
        if self.right:
            contract.right = self.right
        if self.multiplier:
            contract.multiplier = self.multiplier
        if self.trading_class:
            contract.tradingClass = self.trading_class
        if self.include_expired:
            contract.includeExpired = self.include_expired
        
        # Handle combo legs
        if self.combo_legs:
            contract.comboLegs = []
            for leg in self.combo_legs:
                ib_leg = IBComboLeg()
                ib_leg.conId = leg.con_id
                ib_leg.ratio = leg.ratio
                ib_leg.action = leg.action
                ib_leg.exchange = leg.exchange
                ib_leg.openClose = leg.open_close
                ib_leg.shortSaleSlot = leg.short_sale_slot
                ib_leg.designatedLocation = leg.designated_location
                ib_leg.exemptCode = leg.exempt_code
                contract.comboLegs.append(ib_leg)
        
        return contract
    
    @classmethod
    def from_ib_contract(cls, ib_contract) -> 'IBContract':
        """Create IBContract from ib_async Contract object."""
        combo_legs = None
        if hasattr(ib_contract, 'comboLegs') and ib_contract.comboLegs:
            combo_legs = []
            for leg in ib_contract.comboLegs:
                combo_legs.append(ComboLeg(
                    con_id=leg.conId,
                    ratio=leg.ratio,
                    action=leg.action,
                    exchange=leg.exchange,
                    open_close=leg.openClose,
                    short_sale_slot=leg.shortSaleSlot,
                    designated_location=leg.designatedLocation,
                    exempt_code=leg.exemptCode
                ))
        
        return cls(
            symbol=ib_contract.symbol,
            sec_type=SecurityType(ib_contract.secType),
            exchange=ib_contract.exchange,
            currency=ib_contract.currency,
            local_symbol=getattr(ib_contract, 'localSymbol', ''),
            primary_exchange=getattr(ib_contract, 'primaryExchange', ''),
            con_id=getattr(ib_contract, 'conId', None),
            sec_id=getattr(ib_contract, 'secId', None),
            sec_id_type=getattr(ib_contract, 'secIdType', None),
            last_trade_date_or_contract_month=getattr(ib_contract, 'lastTradeDateOrContractMonth', None),
            strike=getattr(ib_contract, 'strike', None),
            right=getattr(ib_contract, 'right', None),
            multiplier=getattr(ib_contract, 'multiplier', None),
            combo_legs=combo_legs,
            trading_class=getattr(ib_contract, 'tradingClass', None)
        )

@dataclass
class IBOrder:
    """
    Enhanced IB Order representation with all order fields.
    """
    action: OrderAction
    total_quantity: float
    order_type: OrderType = OrderType.MARKET
    
    # Price fields
    limit_price: Optional[float] = None
    aux_price: Optional[float] = None  # Stop price for stop orders
    
    # Order management
    order_id: Optional[int] = None
    client_id: Optional[int] = None
    perm_id: Optional[int] = None
    parent_id: Optional[int] = None
    oca_group: Optional[str] = None
    oca_type: int = 0  # 0=None, 1=Cancel with Block, 2=Reduce with Block, 3=Reduce Non-Block
    
    # Time and validity
    tif: TimeInForce = TimeInForce.DAY
    good_after_time: Optional[str] = None
    good_till_date: Optional[str] = None
    
    # Execution settings
    all_or_none: bool = False
    min_qty: Optional[int] = None
    percent_offset: Optional[float] = None
    override_percentage_constraints: bool = False
    trail_stop_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    
    # Advanced order fields
    fa_group: Optional[str] = None
    fa_profile: Optional[str] = None
    fa_method: Optional[str] = None
    fa_percentage: Optional[str] = None
    
    # Institutional
    open_close: str = "O"  # O=Open, C=Close
    origin: int = 0  # 0=Customer, 1=Firm
    short_sale_slot: int = 0  # 0=NA, 1=clearing broker, 2=third party
    designated_location: Optional[str] = None
    exempt_code: int = -1
    
    # Execution and display
    discretionary_amt: float = 0
    e_trade_only: bool = True
    firm_quote_only: bool = True
    nbbo_price_cap: Optional[float] = None
    opt_out_smart_routing: bool = False
    
    # Order status and timing
    status: Optional[OrderStatus] = None
    initial_margin: Optional[str] = None
    maintenance_margin: Optional[str] = None
    equity_with_loan: Optional[str] = None
    commission: Optional[float] = None
    min_commission: Optional[float] = None
    max_commission: Optional[float] = None
    commission_currency: Optional[str] = None
    warning_text: Optional[str] = None
    
    # Timestamps
    created_time: Optional[datetime] = None
    filled_time: Optional[datetime] = None
    
    def to_ib_order(self):
        """Convert to ib_async Order object."""
        from ib_async import Order, OrderCondition, TagValue
        
        order = Order()
        order.action = self.action.value
        order.totalQuantity = self.total_quantity
        order.orderType = self.order_type.value
        order.tif = self.tif.value
        
        # Price fields
        if self.limit_price is not None:
            order.lmtPrice = self.limit_price
        if self.aux_price is not None:
            order.auxPrice = self.aux_price
        
        # Order management
        if self.order_id is not None:
            order.orderId = self.order_id
        if self.client_id is not None:
            order.clientId = self.client_id
        if self.perm_id is not None:
            order.permId = self.perm_id
        if self.parent_id is not None:
            order.parentId = self.parent_id
        if self.oca_group:
            order.ocaGroup = self.oca_group
        order.ocaType = self.oca_type
        
        # Time and validity
        if self.good_after_time:
            order.goodAfterTime = self.good_after_time
        if self.good_till_date:
            order.goodTillDate = self.good_till_date
        
        # Execution settings
        order.allOrNone = self.all_or_none
        if self.min_qty is not None:
            order.minQty = self.min_qty
        if self.percent_offset is not None:
            order.percentOffset = self.percent_offset
        order.overridePercentageConstraints = self.override_percentage_constraints
        if self.trail_stop_price is not None:
            order.trailStopPrice = self.trail_stop_price
        if self.trailing_percent is not None:
            order.trailingPercent = self.trailing_percent
        
        # Advanced fields
        if self.fa_group:
            order.faGroup = self.fa_group
        if self.fa_profile:
            order.faProfile = self.fa_profile
        if self.fa_method:
            order.faMethod = self.fa_method
        if self.fa_percentage:
            order.faPercentage = self.fa_percentage
        
        # Institutional
        order.openClose = self.open_close
        order.origin = self.origin
        order.shortSaleSlot = self.short_sale_slot
        if self.designated_location:
            order.designatedLocation = self.designated_location
        order.exemptCode = self.exempt_code
        
        # Execution and display
        order.discretionaryAmt = self.discretionary_amt
        order.eTradeOnly = self.e_trade_only
        order.firmQuoteOnly = self.firm_quote_only
        if self.nbbo_price_cap is not None:
            order.nbboPriceCap = self.nbbo_price_cap
        order.optOutSmartRouting = self.opt_out_smart_routing
        
        return order
    
    @classmethod
    def from_ib_order(cls, ib_order) -> 'IBOrder':
        """Create IBOrder from ib_async Order object."""
        return cls(
            action=OrderAction(ib_order.action),
            total_quantity=ib_order.totalQuantity,
            order_type=OrderType(ib_order.orderType),
            limit_price=getattr(ib_order, 'lmtPrice', None),
            aux_price=getattr(ib_order, 'auxPrice', None),
            order_id=getattr(ib_order, 'orderId', None),
            client_id=getattr(ib_order, 'clientId', None),
            perm_id=getattr(ib_order, 'permId', None),
            parent_id=getattr(ib_order, 'parentId', None),
            oca_group=getattr(ib_order, 'ocaGroup', None),
            oca_type=getattr(ib_order, 'ocaType', 0),
            tif=TimeInForce(getattr(ib_order, 'tif', 'DAY')),
            good_after_time=getattr(ib_order, 'goodAfterTime', None),
            good_till_date=getattr(ib_order, 'goodTillDate', None),
            all_or_none=getattr(ib_order, 'allOrNone', False),
            min_qty=getattr(ib_order, 'minQty', None),
            percent_offset=getattr(ib_order, 'percentOffset', None)
        )

@dataclass
class IBExecution:
    """
    Represents an order execution/fill.
    """
    exec_id: str
    time: str
    acct_number: str
    exchange: str
    side: str  # BOT or SLD
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

@dataclass
class IBCommissionReport:
    """
    Represents commission information for an execution.
    """
    exec_id: str
    commission: float
    currency: str
    realized_pnl: Optional[float] = None
    yield_: Optional[float] = None
    yield_redemption_date: Optional[int] = None

@dataclass
class IBPosition:
    """
    Represents a position in an account.
    """
    contract: IBContract
    position: float
    market_price: float
    market_value: float
    average_cost: float
    unrealized_pnl: float
    realized_pnl: float
    account: str

@dataclass
class IBAccountValue:
    """
    Represents an account value/summary item.
    """
    key: str
    value: str
    currency: str
    account_name: str

@dataclass
class IBTicker:
    """
    Represents market data for a contract.
    """
    contract: IBContract
    time: Optional[datetime] = None
    bid: Optional[float] = None
    bid_size: Optional[int] = None
    ask: Optional[float] = None
    ask_size: Optional[int] = None
    last: Optional[float] = None
    last_size: Optional[int] = None
    volume: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    open_: Optional[float] = None
    halted: Optional[bool] = None

# ==============================================================================
# DATA TYPE MANAGER CLASS
# ==============================================================================

class IBDataTypeManager:
    """
    Manager class for IB data types with conversion utilities.
    
    This class provides centralized management of IB data types with
    methods for creation, validation, conversion, and serialization
    of contracts, orders, and other IB entities.
    """
    
    def __init__(self):
        """Initialize the data type manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Cache for validated contracts
        self._contract_cache: Dict[str, IBContract] = {}
        
        self.logger.debug("IBDataTypeManager initialized with ib_async support")
    
    # ==========================================================================
    # CONTRACT CREATION METHODS
    # ==========================================================================
    
    def create_stock_contract(self, symbol: str, exchange: str = DEFAULT_EXCHANGE,
                            currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create a stock contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.STOCK,
            exchange=exchange,
            currency=currency
        )
    
    def create_option_contract(self, symbol: str, last_trade_date: str, strike: float,
                             right: str, exchange: str = DEFAULT_EXCHANGE,
                             currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create an option contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.OPTION,
            exchange=exchange,
            currency=currency,
            last_trade_date_or_contract_month=last_trade_date,
            strike=strike,
            right=right.upper(),
            multiplier=DEFAULT_MULTIPLIER
        )
    
    def create_future_contract(self, symbol: str, last_trade_date: str,
                             exchange: str, currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create a futures contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.FUTURE,
            exchange=exchange,
            currency=currency,
            last_trade_date_or_contract_month=last_trade_date
        )
    
    def create_forex_contract(self, symbol: str, currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create a forex contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.FOREX,
            exchange="IDEALPRO",
            currency=currency
        )
    
    def create_index_contract(self, symbol: str, exchange: str,
                            currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create an index contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.INDEX,
            exchange=exchange,
            currency=currency
        )
    
    def create_combo_contract(self, symbol: str, legs: List[ComboLeg],
                            exchange: str = DEFAULT_EXCHANGE,
                            currency: str = DEFAULT_CURRENCY) -> IBContract:
        """Create a combination contract."""
        return IBContract(
            symbol=symbol,
            sec_type=SecurityType.COMBO,
            exchange=exchange,
            currency=currency,
            combo_legs=legs
        )
    
    # ==========================================================================
    # ORDER CREATION METHODS
    # ==========================================================================
    
    def create_market_order(self, action: OrderAction, quantity: float, **kwargs) -> IBOrder:
        """Create a market order."""
        return IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.MARKET,
            **kwargs
        )
    
    def create_limit_order(self, action: OrderAction, quantity: float, 
                         limit_price: float, **kwargs) -> IBOrder:
        """Create a limit order."""
        return IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
            **kwargs
        )
    
    def create_stop_order(self, action: OrderAction, quantity: float,
                        stop_price: float, **kwargs) -> IBOrder:
        """Create a stop order."""
        return IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.STOP,
            aux_price=stop_price,
            **kwargs
        )
    
    def create_stop_limit_order(self, action: OrderAction, quantity: float,
                              limit_price: float, stop_price: float, **kwargs) -> IBOrder:
        """Create a stop limit order."""
        return IBOrder(
            action=action,
            total_quantity=quantity,
            order_type=OrderType.STOP_LIMIT,
            limit_price=limit_price,
            aux_price=stop_price,
            **kwargs
        )
    
    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    
    def validate_contract(self, contract: IBContract) -> bool:
        """Validate a contract."""
        try:
            # Basic validation
            if not contract.symbol:
                raise ValueError("Contract symbol is required")
            
            if not contract.sec_type:
                raise ValueError("Contract security type is required")
            
            # Option-specific validation
            if contract.sec_type == SecurityType.OPTION:
                if not contract.last_trade_date_or_contract_month:
                    raise ValueError("Option contract requires expiration date")
                if contract.strike is None:
                    raise ValueError("Option contract requires strike price")
                if not contract.right:
                    raise ValueError("Option contract requires right (C/P)")
                if contract.right not in ['C', 'P']:
                    raise ValueError("Option right must be 'C' or 'P'")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Contract validation failed: {e}")
            self.error_handler.handle_error(e)
            return False
    
    def validate_order(self, order: IBOrder) -> bool:
        """Validate an order."""
        try:
            # Basic validation
            if order.total_quantity <= 0:
                raise ValueError("Order quantity must be positive")
            
            # Limit order validation
            if order.order_type == OrderType.LIMIT:
                if order.limit_price is None or order.limit_price <= 0:
                    raise ValueError("Limit orders require valid limit price")
            
            # Stop order validation
            if order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
                if order.aux_price is None or order.aux_price <= 0:
                    raise ValueError("Stop orders require valid stop price")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Order validation failed: {e}")
            self.error_handler.handle_error(e)
            return False
    
    # ==========================================================================
    # SERIALIZATION METHODS
    # ==========================================================================
    
    def contract_to_json(self, contract: IBContract) -> str:
        """Serialize contract to JSON."""
        data = asdict(contract)
        # Convert enum to value
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
        """Convert SPYDER contract to ib_async contract."""
        return spyder_contract.to_ib_contract()
    
    def convert_to_ib_order(self, spyder_order: IBOrder):
        """Convert SPYDER order to ib_async order."""
        return spyder_order.to_ib_order()
    
    def convert_from_ib_position(self, ib_position) -> IBPosition:
        """Convert ib_async position to SPYDER position."""
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

def create_limit_order(action: OrderAction, quantity: float, limit_price: float, **kwargs) -> IBOrder:
    """Create a limit order."""
    return get_data_type_manager().create_limit_order(action, quantity, limit_price, **kwargs)

def create_stop_order(action: OrderAction, quantity: float, stop_price: float, **kwargs) -> IBOrder:
    """Create a stop order."""
    return get_data_type_manager().create_stop_order(action, quantity, stop_price, **kwargs)

def create_stop_limit_order(action: OrderAction, quantity: float, limit_price: float,
                          stop_price: float, **kwargs) -> IBOrder:
    """Create a stop limit order."""
    return get_data_type_manager().create_stop_limit_order(
        action, quantity, limit_price, stop_price, **kwargs
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    # Enums
    'SecurityType', 'OrderAction', 'OrderType', 'TimeInForce', 'OrderStatus',
    'TickType', 'PositionSide',
    
    # Data classes
    'ComboLeg', 'DeltaNeutralContract', 'IBContract', 'IBOrder', 'IBExecution',
    'IBCommissionReport', 'IBPosition', 'IBAccountValue', 'IBTicker',
    
    # Manager class
    'IBDataTypeManager', 'get_data_type_manager',
    
    # Convenience functions
    'create_stock_contract', 'create_option_contract', 'create_combo_contract',
    'create_market_order', 'create_limit_order', 'create_stop_order',
    'create_stop_limit_order'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("IBDataTypes - Enhanced with ib_async")
    logger.info("=" * 50)
    
    try:
        # Create data type manager
        manager = get_data_type_manager()
        
        # Test contract creation
        spy_stock = manager.create_stock_contract('SPY')
        logger.info(f"📄 Created stock contract: {spy_stock.symbol}")
        
        # Test option contract
        spy_call = manager.create_option_contract('SPY', '20250620', 450.0, 'C')
        logger.info(f"📄 Created option contract: {spy_call.symbol} {spy_call.strike} {spy_call.right}")
        
        # Test order creation
        market_order = manager.create_market_order(OrderAction.BUY, 100)
        logger.info(f"📝 Created market order: {market_order.action.value} {market_order.total_quantity}")
        
        # Test validation
        is_valid_contract = manager.validate_contract(spy_stock)
        is_valid_order = manager.validate_order(market_order)
        logger.info(f"✅ Contract valid: {is_valid_contract}, Order valid: {is_valid_order}")
        
        # Test conversion to ib_async objects
        ib_contract = manager.convert_to_ib_contract(spy_stock)
        ib_order = manager.convert_to_ib_order(market_order)
        logger.info(f"🔄 Converted to ib_async objects successfully")
        
        # Test serialization
        contract_json = manager.contract_to_json(spy_stock)
        order_json = manager.order_to_json(market_order)
        logger.info(f"💾 Serialized contract and order to JSON")
        
        # Test deserialization
        contract_from_json = manager.contract_from_json(contract_json)
        order_from_json = manager.order_from_json(order_json)
        logger.info(f"📥 Deserialized contract and order from JSON")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        
    logger.info(f"\n🎉 IBDataTypes ready with ib_async!")
    logger.info(f"Comprehensive data type support for IB integration")
