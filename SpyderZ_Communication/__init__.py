#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderZ02_MessageProtocol.py
Group: Z (Communication Infrastructure)
Purpose: Standardized message protocol with schema validation and efficient serialization

Description:
    This module provides:
    - Standardized message schemas for all SPYDER components
    - Message validation and type checking
    - Efficient serialization using MessagePack (optional)
    - Backward compatibility with JSON
    - Message versioning support

Author: SPYDER Team
Date: 2025-06-28
Version: 1.0
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import json
import logging
import time
import uuid
import zlib
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, Union

# Optional MessagePack for efficient serialization
try:
    import msgpack

    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    print("Warning: msgpack not installed. Using JSON serialization.")
    print("Install with: pip install msgpack")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Protocol version
PROTOCOL_VERSION = "1.0"

# Serialization formats


class SerializationFormat(Enum):
    JSON = "json"
    MSGPACK = "msgpack"
    COMPRESSED_JSON = "compressed_json"
    COMPRESSED_MSGPACK = "compressed_msgpack"


# Default format
DEFAULT_FORMAT = SerializationFormat.MSGPACK if MSGPACK_AVAILABLE else SerializationFormat.JSON

# ==============================================================================
# MESSAGE TYPES
# ==============================================================================


class MessageCategory(Enum):
    """High-level message categories."""

    MARKET = "MARKET"
    TRADE = "TRADE"
    RISK = "RISK"
    SYSTEM = "SYSTEM"
    STRATEGY = "STRATEGY"
    ACCOUNT = "ACCOUNT"
    ALERT = "ALERT"


class MarketDataType(Enum):
    """Market data message subtypes."""

    QUOTE = "QUOTE"
    TRADE_TICK = "TRADE_TICK"
    OPTION_CHAIN = "OPTION_CHAIN"
    GREEKS = "GREEKS"
    DEPTH = "DEPTH"
    STATISTICS = "STATISTICS"


class TradeMessageType(Enum):
    """Trade-related message subtypes."""

    ORDER_NEW = "ORDER_NEW"
    ORDER_MODIFY = "ORDER_MODIFY"
    ORDER_CANCEL = "ORDER_CANCEL"
    ORDER_STATUS = "ORDER_STATUS"
    FILL = "FILL"
    PARTIAL_FILL = "PARTIAL_FILL"
    REJECTION = "REJECTION"


class RiskMessageType(Enum):
    """Risk-related message subtypes."""

    PORTFOLIO_GREEKS = "PORTFOLIO_GREEKS"
    POSITION_RISK = "POSITION_RISK"
    MARGIN_UPDATE = "MARGIN_UPDATE"
    RISK_LIMIT = "RISK_LIMIT"
    STRESS_TEST = "STRESS_TEST"


# ==============================================================================
# BASE MESSAGE SCHEMAS
# ==============================================================================


@dataclass
class MessageHeader:
    """Standard message header for all SPYDER messages."""

    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    version: str = PROTOCOL_VERSION
    source: str = ""
    destination: str = ""
    correlation_id: Optional[str] = None
    sequence_num: Optional[int] = None

    def to_datetime(self) -> datetime:
        """Convert timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp)


@dataclass
class SpyderBaseMessage:
    """Base class for all SPYDER messages."""

    header: MessageHeader
    category: MessageCategory
    msg_type: str
    data: Dict[str, Any]

    def validate(self) -> bool:
        """Validate message structure."""
        return True  # Override in subclasses


# ==============================================================================
# MARKET DATA MESSAGES
# ==============================================================================


@dataclass
class QuoteMessage:
    """Stock or option quote message."""

    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    volume: int
    timestamp: float
    exchange: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "QuoteMessage":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class OptionQuoteMessage(QuoteMessage):
    """Option-specific quote message."""

    underlying: str
    strike: float
    expiry: str  # YYYYMMDD format
    option_type: str  # "CALL" or "PUT"
    open_interest: int = 0
    implied_volatility: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None


@dataclass
class OptionChainMessage:
    """Complete option chain for a symbol."""

    underlying: str
    underlying_price: float
    timestamp: float
    expirations: List[str]
    chain: List[OptionQuoteMessage]

    def filter_by_expiry(self, expiry: str) -> List[OptionQuoteMessage]:
        """Filter chain by expiration date."""
        return [opt for opt in self.chain if opt.expiry == expiry]

    def filter_by_strike_range(
        self, min_strike: float, max_strike: float
    ) -> List[OptionQuoteMessage]:
        """Filter chain by strike range."""
        return [opt for opt in self.chain if min_strike <= opt.strike <= max_strike]


@dataclass
class MarketDepthMessage:
    """Level 2 market depth."""

    symbol: str
    timestamp: float
    bids: List[Dict[str, float]]  # [{'price': x, 'size': y}, ...]
    asks: List[Dict[str, float]]

    def get_best_bid(self) -> Optional[Dict[str, float]]:
        """Get best bid."""
        return self.bids[0] if self.bids else None

    def get_best_ask(self) -> Optional[Dict[str, float]]:
        """Get best ask."""
        return self.asks[0] if self.asks else None


# ==============================================================================
# TRADE MESSAGES
# ==============================================================================


@dataclass
class OrderMessage:
    """Order request/status message."""

    order_id: str
    symbol: str
    quantity: int
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", "STOP", etc.
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"  # "DAY", "GTC", "IOC", "FOK"
    status: str = "PENDING"
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    commission: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.filled_quantity >= self.quantity

    def is_partially_filled(self) -> bool:
        """Check if order is partially filled."""
        return 0 < self.filled_quantity < self.quantity


@dataclass
class OptionOrderMessage(OrderMessage):
    """Option-specific order message."""

    underlying: str
    strike: float
    expiry: str
    option_type: str  # "CALL" or "PUT"


@dataclass
class SpreadOrderMessage:
    """Multi-leg spread order."""

    spread_id: str
    strategy_type: str  # "IRON_CONDOR", "BULL_PUT_SPREAD", etc.
    legs: List[OptionOrderMessage]
    net_debit_credit: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class FillMessage:
    """Trade execution fill message."""

    fill_id: str
    order_id: str
    symbol: str
    quantity: int
    price: float
    side: str
    commission: float
    exchange: str
    timestamp: float
    is_partial: bool = False


# ==============================================================================
# RISK MESSAGES
# ==============================================================================


@dataclass
class PortfolioGreeksMessage:
    """Portfolio-level Greeks."""

    timestamp: float
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    delta_dollars: float  # Delta in dollar terms
    gamma_dollars: float
    theta_dollars: float
    vega_dollars: float

    def get_risk_summary(self) -> Dict[str, float]:
        """Get risk summary dictionary."""
        return {
            "delta": self.total_delta,
            "gamma": self.total_gamma,
            "theta": self.total_theta,
            "vega": self.total_vega,
            "delta_$": self.delta_dollars,
            "theta_$": self.theta_dollars,
        }


@dataclass
class PositionRiskMessage:
    """Individual position risk metrics."""

    position_id: str
    symbol: str
    quantity: int
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    delta: float
    gamma: float
    theta: float
    vega: float
    days_to_expiry: Optional[int] = None
    implied_volatility: Optional[float] = None


@dataclass
class RiskLimitMessage:
    """Risk limit alert/breach message."""

    limit_type: str  # "MAX_DELTA", "MAX_LOSS", etc.
    current_value: float
    limit_value: float
    severity: str  # "WARNING", "CRITICAL", "BREACH"
    action_required: str
    timestamp: float = field(default_factory=time.time)

    def is_breached(self) -> bool:
        """Check if limit is breached."""
        return abs(self.current_value) > abs(self.limit_value)


# ==============================================================================
# SYSTEM MESSAGES
# ==============================================================================


@dataclass
class SystemStatusMessage:
    """System component status."""

    component: str
    status: str  # "HEALTHY", "DEGRADED", "ERROR", "OFFLINE"
    latency_ms: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class HeartbeatMessage:
    """System heartbeat."""

    source: str
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0
    metrics: Optional[Dict[str, Any]] = None


# ==============================================================================
# MESSAGE FACTORY
# ==============================================================================


class MessageFactory:
    """Factory for creating standardized messages."""

    @staticmethod
    def create_quote(
        symbol: str, bid: float, ask: float, last: float, volume: int, **kwargs
    ) -> SpyderBaseMessage:
        """Create a quote message."""
        quote = QuoteMessage(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=kwargs.get("bid_size", 0),
            ask_size=kwargs.get("ask_size", 0),
            last=last,
            volume=volume,
            timestamp=time.time(),
            exchange=kwargs.get("exchange"),
        )

        return SpyderBaseMessage(
            header=MessageHeader(source=kwargs.get("source", "MARKET_DATA")),
            category=MessageCategory.MARKET,
            msg_type=MarketDataType.QUOTE.value,
            data=asdict(quote),
        )

    @staticmethod
    def create_option_quote(
        symbol: str, underlying: str, strike: float, expiry: str, option_type: str, **kwargs
    ) -> SpyderBaseMessage:
        """Create an option quote message."""
        opt_quote = OptionQuoteMessage(
            symbol=symbol,
            underlying=underlying,
            strike=strike,
            expiry=expiry,
            option_type=option_type,
            bid=kwargs.get("bid", 0),
            ask=kwargs.get("ask", 0),
            bid_size=kwargs.get("bid_size", 0),
            ask_size=kwargs.get("ask_size", 0),
            last=kwargs.get("last", 0),
            volume=kwargs.get("volume", 0),
            timestamp=time.time(),
            open_interest=kwargs.get("open_interest", 0),
            implied_volatility=kwargs.get("implied_volatility"),
            delta=kwargs.get("delta"),
            gamma=kwargs.get("gamma"),
            theta=kwargs.get("theta"),
            vega=kwargs.get("vega"),
        )

        return SpyderBaseMessage(
            header=MessageHeader(source=kwargs.get("source", "OPTIONS_DATA")),
            category=MessageCategory.MARKET,
            msg_type=MarketDataType.GREEKS.value,
            data=asdict(opt_quote),
        )

    @staticmethod
    def create_order(order: OrderMessage, source: str = "TRADING_ENGINE") -> SpyderBaseMessage:
        """Create an order message."""
        return SpyderBaseMessage(
            header=MessageHeader(source=source),
            category=MessageCategory.TRADE,
            msg_type=TradeMessageType.ORDER_NEW.value,
            data=asdict(order),
        )

    @staticmethod
    def create_fill(fill: FillMessage, source: str = "BROKER") -> SpyderBaseMessage:
        """Create a fill message."""
        return SpyderBaseMessage(
            header=MessageHeader(source=source),
            category=MessageCategory.TRADE,
            msg_type=TradeMessageType.FILL.value,
            data=asdict(fill),
        )

    @staticmethod
    def create_portfolio_greeks(
        greeks: PortfolioGreeksMessage, source: str = "RISK_ENGINE"
    ) -> SpyderBaseMessage:
        """Create a portfolio Greeks message."""
        return SpyderBaseMessage(
            header=MessageHeader(source=source),
            category=MessageCategory.RISK,
            msg_type=RiskMessageType.PORTFOLIO_GREEKS.value,
            data=asdict(greeks),
        )


# ==============================================================================
# SERIALIZATION
# ==============================================================================


class MessageSerializer:
    """Handle message serialization/deserialization."""

    def __init__(self, format: SerializationFormat = DEFAULT_FORMAT):
        """Initialize serializer."""
        self.format = format
        self.logger = logging.getLogger(__name__)

    def serialize(self, message: Union[SpyderBaseMessage, Dict]) -> bytes:
        """Serialize message to bytes."""
        # Convert to dict if needed
        if isinstance(message, SpyderBaseMessage):
            data = self._message_to_dict(message)
        else:
            data = message

        # Serialize based on format
        if self.format == SerializationFormat.JSON:
            return json.dumps(data, default=str).encode("utf-8")

        elif self.format == SerializationFormat.MSGPACK:
            if MSGPACK_AVAILABLE:
                return msgpack.packb(data, use_bin_type=True)
            else:
                # Fallback to JSON
                return json.dumps(data, default=str).encode("utf-8")

        elif self.format == SerializationFormat.COMPRESSED_JSON:
            json_bytes = json.dumps(data, default=str).encode("utf-8")
            return zlib.compress(json_bytes)

        elif self.format == SerializationFormat.COMPRESSED_MSGPACK:
            if MSGPACK_AVAILABLE:
                msgpack_bytes = msgpack.packb(data, use_bin_type=True)
                return zlib.compress(msgpack_bytes)
            else:
                # Fallback to compressed JSON
                json_bytes = json.dumps(data, default=str).encode("utf-8")
                return zlib.compress(json_bytes)

    def deserialize(self, data: bytes) -> Dict:
        """Deserialize bytes to dictionary."""
        try:
            if self.format == SerializationFormat.JSON:
                return json.loads(data.decode("utf-8"))

            elif self.format == SerializationFormat.MSGPACK:
                if MSGPACK_AVAILABLE:
                    return msgpack.unpackb(data, raw=False)
                else:
                    return json.loads(data.decode("utf-8"))

            elif self.format == SerializationFormat.COMPRESSED_JSON:
                decompressed = zlib.decompress(data)
                return json.loads(decompressed.decode("utf-8"))

            elif self.format == SerializationFormat.COMPRESSED_MSGPACK:
                decompressed = zlib.decompress(data)
                if MSGPACK_AVAILABLE:
                    return msgpack.unpackb(decompressed, raw=False)
                else:
                    return json.loads(decompressed.decode("utf-8"))

        except Exception as e:
            self.logger.error(f"Deserialization error: {e}")
            raise

    def _message_to_dict(self, message: SpyderBaseMessage) -> Dict:
        """Convert message object to dictionary."""
        return {
            "header": asdict(message.header),
            "category": message.category.value,
            "msg_type": message.msg_type,
            "data": message.data,
        }

    def _dict_to_message(self, data: Dict) -> SpyderBaseMessage:
        """Convert dictionary to message object."""
        header_data = data["header"]
        header = MessageHeader(**header_data)

        return SpyderBaseMessage(
            header=header,
            category=MessageCategory(data["category"]),
            msg_type=data["msg_type"],
            data=data["data"],
        )


# ==============================================================================
# MESSAGE VALIDATION
# ==============================================================================


class MessageValidator:
    """Validate messages against schemas."""

    # Required fields for each message type
    SCHEMAS = {
        MarketDataType.QUOTE.value: ["symbol", "bid", "ask", "last", "volume"],
        MarketDataType.OPTION_CHAIN.value: ["underlying", "underlying_price", "chain"],
        TradeMessageType.ORDER_NEW.value: ["order_id", "symbol", "quantity", "side"],
        TradeMessageType.FILL.value: ["fill_id", "order_id", "symbol", "quantity", "price"],
        RiskMessageType.PORTFOLIO_GREEKS.value: [
            "total_delta",
            "total_gamma",
            "total_theta",
            "total_vega",
        ],
    }

    @classmethod
    def validate(cls, message: SpyderBaseMessage) -> bool:
        """Validate message against schema."""
        msg_type = message.msg_type

        if msg_type not in cls.SCHEMAS:
            return True  # No schema defined, assume valid

        required_fields = cls.SCHEMAS[msg_type]
        message_fields = message.data.keys()

        # Check all required fields are present
        for field in required_fields:
            if field not in message_fields:
                logging.error(f"Missing required field '{field}' in {msg_type} message")
                return False

        return True


# ==============================================================================
# PROTOCOL MANAGER
# ==============================================================================


class ProtocolManager:
    """Central protocol management."""

    def __init__(self, serialization_format: SerializationFormat = DEFAULT_FORMAT):
        """Initialize protocol manager."""
        self.serializer = MessageSerializer(serialization_format)
        self.factory = MessageFactory()
        self.validator = MessageValidator()
        self.logger = logging.getLogger(__name__)

    def create_message(
        self, category: MessageCategory, msg_type: str, data: Dict, source: str = ""
    ) -> SpyderBaseMessage:
        """Create a validated message."""
        message = SpyderBaseMessage(
            header=MessageHeader(source=source), category=category, msg_type=msg_type, data=data
        )

        if not self.validator.validate(message):
            raise ValueError(f"Invalid message format for {msg_type}")

        return message

    def serialize_message(self, message: SpyderBaseMessage) -> bytes:
        """Serialize a message."""
        return self.serializer.serialize(message)

    def deserialize_message(self, data: bytes) -> SpyderBaseMessage:
        """Deserialize and validate a message."""
        msg_dict = self.serializer.deserialize(data)
        message = self.serializer._dict_to_message(msg_dict)

        if not self.validator.validate(message):
            raise ValueError("Received invalid message")

        return message

    def get_serialization_stats(self, message: SpyderBaseMessage) -> Dict[str, int]:
        """Get size statistics for different serialization formats."""
        stats = {}

        # JSON
        json_bytes = json.dumps(asdict(message), default=str).encode("utf-8")
        stats["json"] = len(json_bytes)

        # Compressed JSON
        stats["compressed_json"] = len(zlib.compress(json_bytes))

        # MessagePack
        if MSGPACK_AVAILABLE:
            msgpack_bytes = msgpack.packb(asdict(message), use_bin_type=True)
            stats["msgpack"] = len(msgpack_bytes)
            stats["compressed_msgpack"] = len(zlib.compress(msgpack_bytes))

        return stats


# ==============================================================================
# USAGE EXAMPLES
# ==============================================================================


def example_usage():
    """Demonstrate protocol usage."""
    # Create protocol manager
    protocol = ProtocolManager(SerializationFormat.MSGPACK)

    # Example 1: Create and serialize a quote message
    print("Example 1: Quote Message")
    print("-" * 50)

    quote_msg = protocol.factory.create_quote(
        symbol="SPY",
        bid=450.25,
        ask=450.30,
        last=450.28,
        volume=1234567,
        bid_size=100,
        ask_size=150,
        source="IB_GATEWAY",
    )

    # Serialize
    serialized = protocol.serialize_message(quote_msg)
    print(f"Serialized size: {len(serialized)} bytes")

    # Get size comparison
    stats = protocol.get_serialization_stats(quote_msg)
    print(f"Size comparison: {stats}")

    # Deserialize
    deserialized = protocol.deserialize_message(serialized)
    print(f"Deserialized: {deserialized.data['symbol']} @ {deserialized.data['last']}")

    # Example 2: Option order message
    print("\nExample 2: Option Order Message")
    print("-" * 50)

    option_order = OptionOrderMessage(
        order_id="ORD123456",
        symbol="SPY230630C00450000",
        underlying="SPY",
        strike=450.0,
        expiry="20230630",
        option_type="CALL",
        quantity=10,
        side="BUY",
        order_type="LIMIT",
        price=2.50,
    )

    order_msg = protocol.factory.create_order(option_order, source="STRATEGY_ENGINE")
    print(
        f"Order: {
            order_msg.data['symbol']} {
            order_msg.data['side']} {
                order_msg.data['quantity']}"
    )

    # Example 3: Portfolio Greeks
    print("\nExample 3: Portfolio Greeks Message")
    print("-" * 50)

    greeks = PortfolioGreeksMessage(
        timestamp=time.time(),
        total_delta=245.5,
        total_gamma=-12.3,
        total_theta=-156.8,
        total_vega=-523.1,
        total_rho=45.2,
        delta_dollars=24550.0,
        gamma_dollars=-1230.0,
        theta_dollars=-156.8,
        vega_dollars=-523.1,
    )

    greeks_msg = protocol.factory.create_portfolio_greeks(greeks)
    print(f"Portfolio Greeks: {greeks.get_risk_summary()}")

    # Example 4: Risk limit breach
    print("\nExample 4: Risk Limit Message")
    print("-" * 50)

    risk_limit = RiskLimitMessage(
        limit_type="MAX_DELTA",
        current_value=550.0,
        limit_value=500.0,
        severity="BREACH",
        action_required="Reduce delta exposure immediately",
    )

    risk_msg = protocol.create_message(
        MessageCategory.RISK,
        RiskMessageType.RISK_LIMIT.value,
        asdict(risk_limit),
        source="RISK_MONITOR",
    )

    print(
        f"Risk Limit Breach: {risk_limit.limit_type} = {risk_limit.current_value} "
        f"(limit: {risk_limit.limit_value})"
    )
    print(f"Action: {risk_limit.action_required}")


if __name__ == "__main__":
    example_usage()
