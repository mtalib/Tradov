#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC15_MicrostructureAnalyzer.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
from queue import Queue, Empty

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

SWEEP_VOLUME_MULTIPLIER = 3.0  # Volume must be 3x average to be considered sweep
SWEEP_TIME_WINDOW = 1.0  # seconds - time window for sweep detection
IMBALANCE_THRESHOLD = 0.65  # 65% imbalance triggers signal
QUOTE_STUFFING_THRESHOLD = 100  # quotes per second threshold
HIDDEN_LIQUIDITY_RATIO = 0.3  # Hidden liquidity detection threshold

# Analysis windows
MICROSTRUCTURE_WINDOW = 300  # 5 minutes of data
ORDER_FLOW_WINDOW = 60  # 1 minute for order flow analysis
QUOTE_HISTORY_SIZE = 10000  # Number of quotes to keep in memory

# Market impact thresholds
LARGE_ORDER_SIZE = 100  # contracts
PRICE_IMPACT_THRESHOLD = 0.05  # 5 cents price impact


# ==============================================================================
# ENUMS
# ==============================================================================
class MicrostructureSignal(Enum):
    """Types of microstructure signals"""

    SWEEP_DETECTED = "sweep_detected"
    IMBALANCE_BUY = "imbalance_buy"
    IMBALANCE_SELL = "imbalance_sell"
    HIDDEN_LIQUIDITY = "hidden_liquidity"
    QUOTE_STUFFING = "quote_stuffing"
    LARGE_ORDER = "large_order"
    PRICE_IMPROVEMENT = "price_improvement"
    TOXIC_FLOW = "toxic_flow"


class OrderType(Enum):
    """Order type classification"""

    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    ALGORITHMIC = "algorithmic"
    HIGH_FREQUENCY = "high_frequency"
    SWEEP = "sweep"


class LiquidityType(Enum):
    """Liquidity type classification"""

    VISIBLE = "visible"
    HIDDEN = "hidden"
    DARK_POOL = "dark_pool"
    ICEBERG = "iceberg"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OrderBookLevel:
    """Single level in the order book"""

    price: float
    size: int
    orders: int
    timestamp: float
    exchange: str = ""


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot"""

    symbol: str
    timestamp: float
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]
    mid_price: float
    spread: float
    total_bid_size: int
    total_ask_size: int
    imbalance: float


@dataclass
class OrderFlowMetrics:
    """Order flow analysis metrics"""

    buy_volume: int
    sell_volume: int
    buy_trades: int
    sell_trades: int
    avg_buy_size: float
    avg_sell_size: float
    volume_imbalance: float
    trade_imbalance: float
    large_buy_orders: int
    large_sell_orders: int


@dataclass
class SweepOrder:
    """Detected sweep order"""

    symbol: str
    timestamp: float
    side: str  # 'BUY' or 'SELL'
    total_size: int
    avg_price: float
    exchanges_hit: list[str]
    time_span: float  # seconds
    price_impact: float


@dataclass
class MicrostructureEvent:
    """Microstructure event detection"""

    event_type: MicrostructureSignal
    symbol: str
    timestamp: float
    details: dict[str, Any]
    confidence: float  # 0.0 to 1.0
    impact_estimate: float  # Estimated price impact


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MicrostructureAnalyzer:
    """
    Advanced market microstructure analyzer for SPY options.

    This class provides real-time analysis of market microstructure including
    order book dynamics, sweep detection, hidden liquidity identification,
    and detection of manipulative trading patterns.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event management system
        order_books: Current order book snapshots by symbol
        flow_metrics: Order flow metrics by symbol
        sweep_detector: Sweep order detection system

    Example:
        >>> analyzer = MicrostructureAnalyzer()
        >>> analyzer.start()
        >>> events = analyzer.analyze_symbol("SPY")
    """

    def __init__(self):
        """Initialize the microstructure analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler(__name__)
        self.event_manager = get_event_manager()

        # Order book tracking
        self.order_books: dict[str, OrderBookSnapshot] = {}
        self.book_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MICROSTRUCTURE_WINDOW)
        )

        # Order flow tracking
        self.flow_metrics: dict[str, OrderFlowMetrics] = {}
        self.trade_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=ORDER_FLOW_WINDOW * 100)
        )

        # Quote tracking for manipulation detection
        self.quote_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=QUOTE_HISTORY_SIZE)
        )
        self.quote_rates: dict[str, list[float]] = defaultdict(list)

        # Sweep detection
        self.sweep_candidates: dict[str, list[dict]] = defaultdict(list)
        self.detected_sweeps: deque = deque(maxlen=1000)

        # Hidden liquidity tracking
        self.hidden_liquidity_estimates: dict[str, float] = {}
        self.execution_quality: dict[str, list[float]] = defaultdict(list)

        # Processing flags
        self.is_running = False
        self.analysis_thread = None
        self.update_queue = Queue()

        # Performance metrics
        self.detection_stats = {
            "sweeps_detected": 0,
            "imbalances_detected": 0,
            "hidden_liquidity_found": 0,
            "quote_stuffing_detected": 0,
        }

        self.logger.info("MicrostructureAnalyzer initialized successfully")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    def start(self):
        """Start the microstructure analyzer."""
        try:
            if self.is_running:
                self.logger.warning("MicrostructureAnalyzer already running")
                return

            self.is_running = True

            # Start analysis thread
            self.analysis_thread = threading.Thread(
                target=self._analysis_loop, daemon=True
            )
            self.analysis_thread.start()

            # Subscribe to market data events
            self._subscribe_to_events()

            self.logger.info("MicrostructureAnalyzer started successfully")

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "start"})

    def stop(self):
        """Stop the microstructure analyzer."""
        try:
            self.is_running = False

            if self.analysis_thread:
                self.analysis_thread.join(timeout=5.0)

            self._unsubscribe_from_events()

            self.logger.info("MicrostructureAnalyzer stopped")

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "stop"})

    # ==========================================================================
    # ORDER BOOK ANALYSIS
    # ==========================================================================
    def update_order_book(
        self, symbol: str, bids: list[tuple[float, int]], asks: list[tuple[float, int]]
    ) -> OrderBookSnapshot:
        """
        Update order book and calculate metrics.

        Args:
            symbol: Option symbol
            bids: List of (price, size) tuples
            asks: List of (price, size) tuples

        Returns:
            Updated order book snapshot
        """
        try:
            timestamp = time.time()

            # Convert to OrderBookLevel objects
            bid_levels = [
                OrderBookLevel(price=p, size=s, orders=1, timestamp=timestamp)
                for p, s in bids
            ]
            ask_levels = [
                OrderBookLevel(price=p, size=s, orders=1, timestamp=timestamp)
                for p, s in asks
            ]

            # Calculate metrics
            total_bid_size = sum(level.size for level in bid_levels)
            total_ask_size = sum(level.size for level in ask_levels)

            if bid_levels and ask_levels:
                mid_price = (bid_levels[0].price + ask_levels[0].price) / 2
                spread = ask_levels[0].price - bid_levels[0].price
            else:
                mid_price = 0
                spread = 0

            # Calculate imbalance
            if total_bid_size + total_ask_size > 0:
                imbalance = total_bid_size / (total_bid_size + total_ask_size)
            else:
                imbalance = 0.5

            # Create snapshot
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                timestamp=timestamp,
                bids=bid_levels,
                asks=ask_levels,
                mid_price=mid_price,
                spread=spread,
                total_bid_size=total_bid_size,
                total_ask_size=total_ask_size,
                imbalance=imbalance,
            )

            # Store snapshot
            self.order_books[symbol] = snapshot
            self.book_history[symbol].append(snapshot)

            # Queue for analysis
            self.update_queue.put(("book", symbol, snapshot))

            return snapshot

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "update_order_book", "symbol": symbol}
            )
            return None

    def detect_order_book_imbalance(self, symbol: str) -> MicrostructureEvent | None:
        """
        Detect significant order book imbalances.

        Args:
            symbol: Option symbol to analyze

        Returns:
            MicrostructureEvent if imbalance detected, None otherwise
        """
        try:
            if symbol not in self.order_books:
                return None

            book = self.order_books[symbol]

            # Check for significant imbalance
            if book.imbalance > IMBALANCE_THRESHOLD:
                # Buy-side imbalance
                return MicrostructureEvent(
                    event_type=MicrostructureSignal.IMBALANCE_BUY,
                    symbol=symbol,
                    timestamp=book.timestamp,
                    details={
                        "imbalance": book.imbalance,
                        "bid_size": book.total_bid_size,
                        "ask_size": book.total_ask_size,
                        "spread": book.spread,
                    },
                    confidence=min(book.imbalance, 0.95),
                    impact_estimate=book.spread * 0.5,
                )

            elif book.imbalance < (1 - IMBALANCE_THRESHOLD):
                # Sell-side imbalance
                return MicrostructureEvent(
                    event_type=MicrostructureSignal.IMBALANCE_SELL,
                    symbol=symbol,
                    timestamp=book.timestamp,
                    details={
                        "imbalance": book.imbalance,
                        "bid_size": book.total_bid_size,
                        "ask_size": book.total_ask_size,
                        "spread": book.spread,
                    },
                    confidence=min(1 - book.imbalance, 0.95),
                    impact_estimate=book.spread * 0.5,
                )

            return None

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "detect_order_book_imbalance", "symbol": symbol}
            )
            return None

    # ==========================================================================
    # SWEEP ORDER DETECTION
    # ==========================================================================
    def process_trade(
        self, symbol: str, price: float, size: int, side: str, exchange: str = ""
    ) -> SweepOrder | None:
        """
        Process trade and detect potential sweep orders.

        Args:
            symbol: Option symbol
            price: Trade price
            size: Trade size
            side: 'BUY' or 'SELL'
            exchange: Exchange identifier

        Returns:
            SweepOrder if sweep detected, None otherwise
        """
        try:
            timestamp = time.time()

            # Store trade
            trade = {
                "timestamp": timestamp,
                "price": price,
                "size": size,
                "side": side,
                "exchange": exchange,
            }
            self.trade_history[symbol].append(trade)

            # Check for sweep pattern
            if size >= LARGE_ORDER_SIZE:
                # Look for related trades in time window
                recent_trades = [
                    t
                    for t in self.sweep_candidates[symbol]
                    if timestamp - t["timestamp"] <= SWEEP_TIME_WINDOW
                ]

                # Add current trade
                recent_trades.append(trade)

                # Check if this constitutes a sweep
                if self._is_sweep_pattern(symbol, recent_trades):
                    sweep = self._create_sweep_order(symbol, recent_trades)
                    if sweep:
                        self.detected_sweeps.append(sweep)
                        self.detection_stats["sweeps_detected"] += 1

                        # Emit event
                        self.event_manager.emit(
                            Event(
                                EventType.MARKET_SIGNAL,
                                {
                                    "signal_type": "sweep_detected",
                                    "sweep": sweep,
                                    "symbol": symbol,
                                },
                            )
                        )

                        return sweep

                # Store as potential sweep candidate
                self.sweep_candidates[symbol].append(trade)

                # Clean old candidates
                self.sweep_candidates[symbol] = [
                    t
                    for t in self.sweep_candidates[symbol]
                    if timestamp - t["timestamp"] <= SWEEP_TIME_WINDOW * 2
                ]

            # Update flow metrics
            self._update_flow_metrics(symbol, trade)

            return None

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "process_trade", "symbol": symbol, "size": size}
            )
            return None

    def _is_sweep_pattern(self, symbol: str, trades: list[dict]) -> bool:
        """Determine if trades constitute a sweep pattern."""
        try:
            if len(trades) < 2:
                return False

            # Calculate total volume
            total_volume = sum(t["size"] for t in trades)

            # Get average volume for comparison
            flow = self.flow_metrics.get(symbol)
            if not flow:
                return False

            avg_trade_size = (flow.avg_buy_size + flow.avg_sell_size) / 2
            if avg_trade_size == 0:
                return False

            # Check volume criteria
            if total_volume < avg_trade_size * SWEEP_VOLUME_MULTIPLIER:
                return False

            # Check time span
            time_span = max(t["timestamp"] for t in trades) - min(
                t["timestamp"] for t in trades
            )
            if time_span > SWEEP_TIME_WINDOW:
                return False

            # Check price consistency (should be aggressive)
            prices = [t["price"] for t in trades]
            price_range = max(prices) - min(prices)

            if trades[0]["side"] == "BUY":
                # Buy sweep should show increasing prices
                return price_range > 0 and prices[-1] >= prices[0]
            else:
                # Sell sweep should show decreasing prices
                return price_range > 0 and prices[-1] <= prices[0]

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_is_sweep_pattern", "symbol": symbol}
            )
            return False

    def _create_sweep_order(
        self, symbol: str, trades: list[dict]
    ) -> SweepOrder | None:
        """Create SweepOrder object from trades."""
        try:
            if not trades:
                return None

            total_size = sum(t["size"] for t in trades)
            total_value = sum(t["price"] * t["size"] for t in trades)
            avg_price = total_value / total_size

            exchanges = list(
                {t.get("exchange", "") for t in trades if t.get("exchange")}
            )
            time_span = max(t["timestamp"] for t in trades) - min(
                t["timestamp"] for t in trades
            )

            # Estimate price impact
            first_price = trades[0]["price"]
            last_price = trades[-1]["price"]
            price_impact = abs(last_price - first_price)

            return SweepOrder(
                symbol=symbol,
                timestamp=trades[-1]["timestamp"],
                side=trades[0]["side"],
                total_size=total_size,
                avg_price=avg_price,
                exchanges_hit=exchanges,
                time_span=time_span,
                price_impact=price_impact,
            )

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_create_sweep_order", "symbol": symbol}
            )
            return None

    # ==========================================================================
    # HIDDEN LIQUIDITY DETECTION
    # ==========================================================================
    def detect_hidden_liquidity(self, symbol: str) -> MicrostructureEvent | None:
        """
        Detect presence of hidden liquidity.

        Args:
            symbol: Option symbol to analyze

        Returns:
            MicrostructureEvent if hidden liquidity detected
        """
        try:
            # Get recent trades
            trades = list(self.trade_history.get(symbol, []))
            if len(trades) < 10:
                return None

            # Get order book
            book = self.order_books.get(symbol)
            if not book:
                return None

            # Analyze trades that executed inside the spread
            hidden_trades = []
            for trade in trades[-50:]:  # Last 50 trades
                if book.bids and book.asks:
                    best_bid = book.bids[0].price
                    best_ask = book.asks[0].price

                    # Trade inside spread suggests hidden liquidity
                    if best_bid < trade["price"] < best_ask:
                        hidden_trades.append(trade)

            # Calculate hidden liquidity ratio
            if trades:
                hidden_ratio = len(hidden_trades) / min(len(trades), 50)

                if hidden_ratio > HIDDEN_LIQUIDITY_RATIO:
                    # Estimate hidden liquidity size
                    hidden_volume = sum(t["size"] for t in hidden_trades)
                    visible_volume = book.total_bid_size + book.total_ask_size

                    self.hidden_liquidity_estimates[symbol] = hidden_volume
                    self.detection_stats["hidden_liquidity_found"] += 1

                    return MicrostructureEvent(
                        event_type=MicrostructureSignal.HIDDEN_LIQUIDITY,
                        symbol=symbol,
                        timestamp=time.time(),
                        details={
                            "hidden_ratio": hidden_ratio,
                            "hidden_volume": hidden_volume,
                            "visible_volume": visible_volume,
                            "trade_count": len(hidden_trades),
                        },
                        confidence=min(hidden_ratio * 2, 0.9),
                        impact_estimate=book.spread * 0.25,
                    )

            return None

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "detect_hidden_liquidity", "symbol": symbol}
            )
            return None

    # ==========================================================================
    # QUOTE STUFFING DETECTION
    # ==========================================================================
    def process_quote(
        self, symbol: str, bid: float, ask: float, bid_size: int, ask_size: int
    ) -> MicrostructureEvent | None:
        """
        Process quote update and detect quote stuffing.

        Args:
            symbol: Option symbol
            bid: Bid price
            ask: Ask price
            bid_size: Bid size
            ask_size: Ask size

        Returns:
            MicrostructureEvent if quote stuffing detected
        """
        try:
            timestamp = time.time()

            # Store quote
            quote = {
                "timestamp": timestamp,
                "bid": bid,
                "ask": ask,
                "bid_size": bid_size,
                "ask_size": ask_size,
            }
            self.quote_history[symbol].append(quote)

            # Calculate quote rate
            recent_quotes = [
                q
                for q in self.quote_history[symbol]
                if timestamp - q["timestamp"] <= 1.0  # Last second
            ]

            quote_rate = len(recent_quotes)
            self.quote_rates[symbol].append(quote_rate)

            # Detect quote stuffing
            if quote_rate > QUOTE_STUFFING_THRESHOLD:
                # Analyze quote patterns
                price_changes = 0
                size_changes = 0

                for i in range(1, len(recent_quotes)):
                    if (
                        recent_quotes[i]["bid"] != recent_quotes[i - 1]["bid"]
                        or recent_quotes[i]["ask"] != recent_quotes[i - 1]["ask"]
                    ):
                        price_changes += 1
                    if (
                        recent_quotes[i]["bid_size"] != recent_quotes[i - 1]["bid_size"]
                        or recent_quotes[i]["ask_size"]
                        != recent_quotes[i - 1]["ask_size"]
                    ):
                        size_changes += 1

                # High quote rate with minimal price changes indicates stuffing
                if price_changes < quote_rate * 0.1:  # Less than 10% price changes
                    self.detection_stats["quote_stuffing_detected"] += 1

                    return MicrostructureEvent(
                        event_type=MicrostructureSignal.QUOTE_STUFFING,
                        symbol=symbol,
                        timestamp=timestamp,
                        details={
                            "quote_rate": quote_rate,
                            "price_changes": price_changes,
                            "size_changes": size_changes,
                            "duration": 1.0,
                        },
                        confidence=min(quote_rate / QUOTE_STUFFING_THRESHOLD, 1.0),
                        impact_estimate=0.0,  # Quote stuffing doesn't directly impact price
                    )

            return None

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "process_quote", "symbol": symbol}
            )
            return None

    # ==========================================================================
    # ORDER FLOW ANALYSIS
    # ==========================================================================
    def _update_flow_metrics(self, symbol: str, trade: dict):
        """Update order flow metrics with new trade."""
        try:
            # Initialize metrics if needed
            if symbol not in self.flow_metrics:
                self.flow_metrics[symbol] = OrderFlowMetrics(
                    buy_volume=0,
                    sell_volume=0,
                    buy_trades=0,
                    sell_trades=0,
                    avg_buy_size=0,
                    avg_sell_size=0,
                    volume_imbalance=0,
                    trade_imbalance=0,
                    large_buy_orders=0,
                    large_sell_orders=0,
                )

            metrics = self.flow_metrics[symbol]

            # Update based on trade side
            if trade["side"] == "BUY":
                metrics.buy_volume += trade["size"]
                metrics.buy_trades += 1
                if trade["size"] >= LARGE_ORDER_SIZE:
                    metrics.large_buy_orders += 1
            else:
                metrics.sell_volume += trade["size"]
                metrics.sell_trades += 1
                if trade["size"] >= LARGE_ORDER_SIZE:
                    metrics.large_sell_orders += 1

            # Recalculate averages
            if metrics.buy_trades > 0:
                metrics.avg_buy_size = metrics.buy_volume / metrics.buy_trades
            if metrics.sell_trades > 0:
                metrics.avg_sell_size = metrics.sell_volume / metrics.sell_trades

            # Calculate imbalances
            total_volume = metrics.buy_volume + metrics.sell_volume
            if total_volume > 0:
                metrics.volume_imbalance = (
                    metrics.buy_volume - metrics.sell_volume
                ) / total_volume

            total_trades = metrics.buy_trades + metrics.sell_trades
            if total_trades > 0:
                metrics.trade_imbalance = (
                    metrics.buy_trades - metrics.sell_trades
                ) / total_trades

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_update_flow_metrics", "symbol": symbol}
            )

    def analyze_order_flow(self, symbol: str) -> dict[str, Any]:
        """
        Analyze order flow patterns for a symbol.

        Args:
            symbol: Option symbol to analyze

        Returns:
            Dictionary of order flow analysis results
        """
        try:
            if symbol not in self.flow_metrics:
                return {}

            metrics = self.flow_metrics[symbol]
            trades = list(self.trade_history.get(symbol, []))

            if not trades:
                return {}

            # Calculate additional metrics
            recent_trades = trades[-100:]  # Last 100 trades

            # Identify trade clustering
            trade_times = [t["timestamp"] for t in recent_trades]
            if len(trade_times) > 1:
                inter_trade_times = [
                    trade_times[i + 1] - trade_times[i]
                    for i in range(len(trade_times) - 1)
                ]
                avg_inter_trade_time = statistics.mean(inter_trade_times)
                trade_clustering = (
                    statistics.stdev(inter_trade_times)
                    if len(inter_trade_times) > 1
                    else 0
                )
            else:
                avg_inter_trade_time = 0
                trade_clustering = 0

            # Identify institutional vs retail flow
            large_trades = [t for t in recent_trades if t["size"] >= LARGE_ORDER_SIZE]
            institutional_ratio = (
                len(large_trades) / len(recent_trades) if recent_trades else 0
            )

            # Calculate order flow toxicity (adverse selection indicator)
            toxicity = self._calculate_flow_toxicity(symbol, recent_trades)

            return {
                "metrics": metrics,
                "institutional_ratio": institutional_ratio,
                "avg_inter_trade_time": avg_inter_trade_time,
                "trade_clustering": trade_clustering,
                "toxicity": toxicity,
                "recent_trade_count": len(recent_trades),
                "large_trade_count": len(large_trades),
            }

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "analyze_order_flow", "symbol": symbol}
            )
            return {}

    def _calculate_flow_toxicity(self, symbol: str, trades: list[dict]) -> float:
        """Calculate order flow toxicity (probability of adverse selection)."""
        try:
            if len(trades) < 10:
                return 0.0

            # Look at price movement after large trades
            toxic_trades = 0
            total_large_trades = 0

            for i, trade in enumerate(trades[:-5]):  # Leave room to check future prices
                if trade["size"] >= LARGE_ORDER_SIZE:
                    total_large_trades += 1

                    # Check if price moved against the trade
                    future_trades = trades[i + 1 : i + 6]  # Next 5 trades
                    if future_trades:
                        initial_price = trade["price"]
                        final_price = future_trades[-1]["price"]

                        if trade["side"] == "BUY" and final_price < initial_price or trade["side"] == "SELL" and final_price > initial_price:  # noqa: E501
                            toxic_trades += 1

            if total_large_trades > 0:
                return toxic_trades / total_large_trades

            return 0.0

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_calculate_flow_toxicity", "symbol": symbol}
            )
            return 0.0

    # ==========================================================================
    # COMPREHENSIVE ANALYSIS
    # ==========================================================================
    def analyze_symbol(self, symbol: str) -> list[MicrostructureEvent]:
        """
        Perform comprehensive microstructure analysis for a symbol.

        Args:
            symbol: Option symbol to analyze

        Returns:
            List of detected microstructure events
        """
        try:
            events = []

            # Check order book imbalance
            imbalance_event = self.detect_order_book_imbalance(symbol)
            if imbalance_event:
                events.append(imbalance_event)

            # Check for hidden liquidity
            hidden_event = self.detect_hidden_liquidity(symbol)
            if hidden_event:
                events.append(hidden_event)

            # Analyze order flow
            flow_analysis = self.analyze_order_flow(symbol)
            if flow_analysis:
                metrics = flow_analysis.get("metrics")
                if metrics:
                    # Check for significant flow imbalance
                    if abs(metrics.volume_imbalance) > 0.7:
                        signal_type = (
                            MicrostructureSignal.IMBALANCE_BUY
                            if metrics.volume_imbalance > 0
                            else MicrostructureSignal.IMBALANCE_SELL
                        )

                        events.append(
                            MicrostructureEvent(
                                event_type=signal_type,
                                symbol=symbol,
                                timestamp=time.time(),
                                details={
                                    "volume_imbalance": metrics.volume_imbalance,
                                    "trade_imbalance": metrics.trade_imbalance,
                                    "flow_analysis": flow_analysis,
                                },
                                confidence=abs(metrics.volume_imbalance),
                                impact_estimate=0.02,  # 2 cents estimated impact
                            )
                        )

                    # Check for toxic flow
                    if flow_analysis.get("toxicity", 0) > 0.6:
                        events.append(
                            MicrostructureEvent(
                                event_type=MicrostructureSignal.TOXIC_FLOW,
                                symbol=symbol,
                                timestamp=time.time(),
                                details={
                                    "toxicity": flow_analysis["toxicity"],
                                    "institutional_ratio": flow_analysis.get(
                                        "institutional_ratio", 0
                                    ),
                                },
                                confidence=flow_analysis["toxicity"],
                                impact_estimate=0.05,  # Higher impact for toxic flow
                            )
                        )

            return events

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "analyze_symbol", "symbol": symbol}
            )
            return []

    # ==========================================================================
    # ANALYSIS LOOP
    # ==========================================================================
    def _analysis_loop(self):
        """Main analysis loop running in separate thread."""
        while self.is_running:
            try:
                # Process updates from queue
                try:
                    update_type, symbol, data = self.update_queue.get(timeout=0.1)

                    if update_type == "book":
                        # Analyze order book update
                        events = self.analyze_symbol(symbol)
                        for event in events:
                            self._emit_event(event)

                except Empty:
                    pass

                # Periodic analysis of all tracked symbols
                if time.time() % 5 < 0.1:  # Every 5 seconds
                    self._periodic_analysis()

            except Exception as e:
                self.error_handler.handle_error(e, {"method": "_analysis_loop"})
                time.sleep(1)  # thread-safe: time.sleep() intentional

    def _periodic_analysis(self):
        """Perform periodic analysis of all symbols."""
        try:
            for symbol in list(self.order_books.keys()):
                # Full analysis
                events = self.analyze_symbol(symbol)
                for event in events:
                    self._emit_event(event)

                # Clean old data
                self._clean_old_data(symbol)

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_periodic_analysis"})

    def _clean_old_data(self, symbol: str):
        """Clean old data for a symbol."""
        try:
            current_time = time.time()

            # Clean old trades
            if symbol in self.trade_history:
                self.trade_history[symbol] = deque(
                    [
                        t
                        for t in self.trade_history[symbol]
                        if current_time - t["timestamp"] <= ORDER_FLOW_WINDOW
                    ],
                    maxlen=ORDER_FLOW_WINDOW * 100,
                )

            # Clean old sweep candidates
            if symbol in self.sweep_candidates:
                self.sweep_candidates[symbol] = [
                    t
                    for t in self.sweep_candidates[symbol]
                    if current_time - t["timestamp"] <= SWEEP_TIME_WINDOW * 2
                ]

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_clean_old_data", "symbol": symbol}
            )

    # ==========================================================================
    # EVENT HANDLING
    # ==========================================================================
    def _subscribe_to_events(self):
        """Subscribe to relevant market data events."""
        try:
            # Subscribe to order book updates
            self.event_manager.subscribe(
                EventType.ORDER_BOOK_UPDATE, self._handle_order_book_update
            )

            # Subscribe to trade updates
            self.event_manager.subscribe(
                EventType.TRADE_UPDATE, self._handle_trade_update
            )

            # Subscribe to quote updates
            self.event_manager.subscribe(
                EventType.QUOTE_UPDATE, self._handle_quote_update
            )

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_subscribe_to_events"})

    def _unsubscribe_from_events(self):
        """Unsubscribe from market data events."""
        try:
            self.event_manager.unsubscribe(
                EventType.ORDER_BOOK_UPDATE, self._handle_order_book_update
            )
            self.event_manager.unsubscribe(
                EventType.TRADE_UPDATE, self._handle_trade_update
            )
            self.event_manager.unsubscribe(
                EventType.QUOTE_UPDATE, self._handle_quote_update
            )

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "_unsubscribe_from_events"})

    def _handle_order_book_update(self, event: Event):
        """Handle order book update event."""
        try:
            data = event.data
            symbol = data.get("symbol")
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            if symbol:
                self.update_order_book(symbol, bids, asks)

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_handle_order_book_update", "event": event}
            )

    def _handle_trade_update(self, event: Event):
        """Handle trade update event."""
        try:
            data = event.data
            symbol = data.get("symbol")
            price = data.get("price")
            size = data.get("size")
            side = data.get("side")
            exchange = data.get("exchange", "")

            if all([symbol, price is not None, size, side]):
                self.process_trade(symbol, price, size, side, exchange)

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_handle_trade_update", "event": event}
            )

    def _handle_quote_update(self, event: Event):
        """Handle quote update event."""
        try:
            data = event.data
            symbol = data.get("symbol")
            bid = data.get("bid")
            ask = data.get("ask")
            bid_size = data.get("bid_size")
            ask_size = data.get("ask_size")

            if all(
                [
                    symbol,
                    bid is not None,
                    ask is not None,
                    bid_size is not None,
                    ask_size is not None,
                ]
            ):
                self.process_quote(symbol, bid, ask, bid_size, ask_size)

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "_handle_quote_update", "event": event}
            )

    def _emit_event(self, microstructure_event: MicrostructureEvent):
        """Emit microstructure event."""
        try:
            self.event_manager.emit(
                Event(
                    EventType.MICROSTRUCTURE_SIGNAL,
                    {
                        "event": microstructure_event,
                        "symbol": microstructure_event.symbol,
                        "type": microstructure_event.event_type.value,
                        "confidence": microstructure_event.confidence,
                    },
                )
            )

            self.logger.info(
                f"Microstructure event detected: {microstructure_event.event_type.value} "
                f"for {microstructure_event.symbol} (confidence: {microstructure_event.confidence:.2f})"  # noqa: E501
            )

        except Exception as e:
            self.error_handler.handle_error(
                e,
                {
                    "method": "_emit_event",
                    "event_type": microstructure_event.event_type,
                },
            )

    # ==========================================================================
    # REPORTING AND STATISTICS
    # ==========================================================================
    def get_statistics(self) -> dict[str, Any]:
        """Get analyzer statistics and performance metrics."""
        try:
            stats = {
                "detection_stats": self.detection_stats.copy(),
                "tracked_symbols": len(self.order_books),
                "recent_sweeps": len(self.detected_sweeps),
                "symbols_with_hidden_liquidity": len(
                    [s for s, v in self.hidden_liquidity_estimates.items() if v > 0]
                ),
                "total_events_processed": sum(
                    len(h) for h in self.quote_history.values()
                ),
                "active_flow_metrics": len(self.flow_metrics),
            }

            # Add per-symbol statistics
            symbol_stats = {}
            for symbol in self.order_books:
                flow = self.flow_metrics.get(symbol)
                if flow:
                    symbol_stats[symbol] = {
                        "volume_imbalance": flow.volume_imbalance,
                        "trade_imbalance": flow.trade_imbalance,
                        "large_orders": flow.large_buy_orders + flow.large_sell_orders,
                        "avg_trade_size": (flow.avg_buy_size + flow.avg_sell_size) / 2,
                    }

            stats["symbol_statistics"] = symbol_stats

            return stats

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "get_statistics"})
            return {}

    def generate_report(self) -> str:
        """Generate comprehensive microstructure analysis report."""
        try:
            report = ["=" * 60]
            report.append("MICROSTRUCTURE ANALYSIS REPORT")
            report.append("=" * 60)
            report.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")

            # Detection statistics
            report.append("DETECTION STATISTICS:")
            report.append("-" * 30)
            for key, value in self.detection_stats.items():
                report.append(f"{key}: {value}")
            report.append("")

            # Recent sweeps
            report.append("RECENT SWEEP ORDERS:")
            report.append("-" * 30)
            recent_sweeps = list(self.detected_sweeps)[-5:]  # Last 5
            for sweep in recent_sweeps:
                report.append(
                    f"{sweep.symbol}: {sweep.side} {sweep.total_size} @ "
                    f"${sweep.avg_price:.2f} (impact: ${sweep.price_impact:.3f})"
                )
            report.append("")

            # Order flow summary
            report.append("ORDER FLOW SUMMARY:")
            report.append("-" * 30)
            for symbol, metrics in list(self.flow_metrics.items())[:10]:  # Top 10
                report.append(
                    f"{symbol}: Vol Imbalance: {metrics.volume_imbalance:+.2f}, "
                    f"Buy: {metrics.buy_volume}, Sell: {metrics.sell_volume}"
                )
            report.append("")

            # Hidden liquidity
            report.append("HIDDEN LIQUIDITY ESTIMATES:")
            report.append("-" * 30)
            for symbol, estimate in list(self.hidden_liquidity_estimates.items())[:5]:
                if estimate > 0:
                    report.append(f"{symbol}: {estimate:.0f} contracts")

            report.append("=" * 60)

            return "\n".join(report)

        except Exception as e:
            self.error_handler.handle_error(e, {"method": "generate_report"})
            return "Error generating report"


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance
_analyzer_instance = None
_analyzer_instance_lock = threading.Lock()


def get_microstructure_analyzer() -> MicrostructureAnalyzer:
    """Get or create the global MicrostructureAnalyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        with _analyzer_instance_lock:
            if _analyzer_instance is None:
                _analyzer_instance = MicrostructureAnalyzer()
    return _analyzer_instance
