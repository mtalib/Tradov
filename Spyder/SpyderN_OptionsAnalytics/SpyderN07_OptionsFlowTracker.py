#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN07_OptionsFlowTracker.py
Group: N (Options Analytics)
Purpose: Real-time options flow analysis, unusual activity detection, and sentiment tracking
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 22:00:00

Description:
    This module tracks real-time options flow to identify smart money movements,
    unusual options activity (UOA), large trades, sweep orders, and market maker
    positioning. It provides sentiment analysis, flow toxicity metrics, and
    actionable trading signals based on options order flow patterns.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
import queue
from datetime import datetime, timedelta, time, UTC
from typing import Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np  # noqa: E402

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path  # noqa: E402
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Flow thresholds
MIN_PREMIUM = 25000  # Minimum premium for tracking
MIN_SIZE = 100  # Minimum contract size
BLOCK_SIZE = 500  # Block trade threshold
SWEEP_TIME_WINDOW = 3  # Seconds for sweep detection
UNUSUAL_VOLUME_RATIO = 2.0  # Volume/OI ratio for unusual activity

# Time windows
FLOW_WINDOW = 300  # 5 minutes for flow aggregation
SENTIMENT_WINDOW = 900  # 15 minutes for sentiment
TOXICITY_WINDOW = 60  # 1 minute for toxicity

# Market hours
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

# Sentiment thresholds
BULLISH_RATIO = 1.5  # Call/Put ratio for bullish
BEARISH_RATIO = 0.67  # Call/Put ratio for bearish

# ==============================================================================
# ENUMS
# ==============================================================================
class OrderType(Enum):
    """Options order type"""
    BUY_TO_OPEN = "BTO"
    SELL_TO_OPEN = "STO"
    BUY_TO_CLOSE = "BTC"
    SELL_TO_CLOSE = "STC"
    UNKNOWN = "UNK"

# Module-level aliases for backwards-compatible bare-name usage
BUY_TO_OPEN = OrderType.BUY_TO_OPEN
SELL_TO_OPEN = OrderType.SELL_TO_OPEN
BUY_TO_CLOSE = OrderType.BUY_TO_CLOSE
SELL_TO_CLOSE = OrderType.SELL_TO_CLOSE
UNKNOWN = OrderType.UNKNOWN


class FlowType(Enum):
    """Options flow classification"""
    SWEEP = "SWEEP"
    BLOCK = "BLOCK"
    SPLIT = "SPLIT"
    REGULAR = "REGULAR"
    UNUSUAL = "UNUSUAL"
    REPEAT = "REPEAT"

class Sentiment(Enum):
    """Market sentiment"""
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"

class AggressorSide(Enum):
    """Trade aggressor side"""
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"

class InstitutionalIndicator(Enum):
    """Institutional activity indicators"""
    SMART_MONEY = "SMART_MONEY"
    HEDGE = "HEDGE"
    RETAIL = "RETAIL"
    MARKET_MAKER = "MARKET_MAKER"
    UNKNOWN = "UNKNOWN"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionsFlow:
    """Individual options flow/trade"""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'CALL' or 'PUT'
    size: int
    price: float
    premium: float
    underlying_price: float
    implied_volatility: float
    delta: float
    gamma: float

    # Flow characteristics
    order_type: OrderType
    flow_type: FlowType
    aggressor: AggressorSide
    at_ask: bool
    at_bid: bool
    between_market: bool

    # Context
    volume_today: int
    open_interest: int
    volume_oi_ratio: float

    # Unusual indicators
    is_unusual: bool
    is_sweep: bool
    is_block: bool
    is_repeat: bool

    # Sentiment
    sentiment_score: float  # -1 to 1
    toxicity_score: float  # 0 to 1

@dataclass
class AggregatedFlow:
    """Aggregated flow over time window"""
    symbol: str
    time_window: timedelta
    start_time: datetime
    end_time: datetime

    # Volume metrics
    total_call_volume: int
    total_put_volume: int
    total_call_premium: float
    total_put_premium: float

    # Directional flow
    buy_call_volume: int
    sell_call_volume: int
    buy_put_volume: int
    sell_put_volume: int

    # Premium flow
    buy_call_premium: float
    sell_call_premium: float
    buy_put_premium: float
    sell_put_premium: float

    # Ratios
    call_put_ratio: float
    put_call_ratio: float
    buy_sell_ratio: float

    # Greeks flow
    net_delta_flow: float
    net_gamma_flow: float
    net_vega_flow: float

    # Sentiment
    sentiment: Sentiment
    sentiment_strength: float

    # Unusual activity
    unusual_trades: list[OptionsFlow]
    sweep_count: int
    block_count: int

@dataclass
class FlowAlert:
    """Alert for significant flow"""
    timestamp: datetime
    alert_type: str
    symbol: str
    message: str
    flow: OptionsFlow
    significance: float  # 0 to 1
    action_required: bool

@dataclass
class MarketMakerActivity:
    """Market maker positioning"""
    symbol: str
    timestamp: datetime
    net_position_delta: float
    hedging_flow: float
    pin_risk_management: bool
    likely_direction: str  # 'LONG', 'SHORT', 'NEUTRAL'

@dataclass
class FlowToxicity:
    """Flow toxicity metrics"""
    timestamp: datetime
    symbol: str
    toxicity_score: float  # 0 to 1
    adverse_selection: float
    informed_trading_probability: float
    order_imbalance: float

# ==============================================================================
# OPTIONS FLOW TRACKER CLASS
# ==============================================================================
class OptionsFlowTracker:
    """
    Real-time options flow tracking and analysis.

    Features:
        - Real-time flow processing
        - Unusual activity detection
        - Sweep order identification
        - Block trade tracking
        - Sentiment analysis
        - Market maker positioning
        - Flow toxicity metrics
        - Smart money detection
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the Options Flow Tracker

        Args:
            config: Configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.min_premium = self.config.get('min_premium', MIN_PREMIUM)
        self.min_size = self.config.get('min_size', MIN_SIZE)

        # Flow storage
        self.flows: deque = deque(maxlen=10000)  # Recent flows
        self.aggregated_flows: dict[str, AggregatedFlow] = {}
        self.unusual_activity: list[OptionsFlow] = []
        self.alerts: list[FlowAlert] = []

        # Tracking
        self.symbol_flows: dict[str, list[OptionsFlow]] = defaultdict(list)
        self.sweep_tracker: dict[str, list[OptionsFlow]] = defaultdict(list)
        self.repeat_tracker: dict[tuple, list[datetime]] = defaultdict(list)

        # Market maker tracking
        self.mm_activity: dict[str, MarketMakerActivity] = {}

        # Sentiment tracking
        self.sentiment_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.current_sentiment: dict[str, Sentiment] = {}

        # Statistics
        self.daily_stats: dict[str, dict] = {}
        self.historical_averages: dict[str, dict] = {}

        # Threading
        self.lock = threading.Lock()
        self.flow_queue = queue.Queue()
        self.processing_thread = None
        self.monitoring = False

        self.logger.info("OptionsFlowTracker initialized")

    # ==========================================================================
    # FLOW PROCESSING
    # ==========================================================================

    def process_flow(self, trade_data: dict[str, Any]) -> OptionsFlow:
        """
        Process incoming options trade

        Args:
            trade_data: Trade data dictionary

        Returns:
            OptionsFlow object
        """
        with self.lock:
            # Create flow object
            flow = self._create_flow_object(trade_data)

            # Classify flow
            flow = self._classify_flow(flow)

            # Check for unusual activity
            flow = self._check_unusual_activity(flow)

            # Calculate sentiment
            flow.sentiment_score = self._calculate_flow_sentiment(flow)

            # Calculate toxicity
            flow.toxicity_score = self._calculate_toxicity(flow)

            # Store flow
            self.flows.append(flow)
            self.symbol_flows[flow.symbol].append(flow)

            # Check for patterns
            self._check_sweep(flow)
            self._check_repeat(flow)
            self._check_block(flow)

            # Update aggregated flow
            self._update_aggregated_flow(flow)

            # Generate alerts if needed
            self._generate_alerts(flow)

            return flow

    def _create_flow_object(self, trade_data: dict) -> OptionsFlow:
        """Create OptionsFlow object from trade data"""
        # Calculate premium
        size = trade_data.get('size', 0)
        price = trade_data.get('price', 0)
        premium = size * price * 100

        # Determine order type
        order_type = self._determine_order_type(trade_data)

        # Determine aggressor
        aggressor = self._determine_aggressor(trade_data)

        # Price location
        bid = trade_data.get('bid', 0)
        ask = trade_data.get('ask', 0)
        at_ask = abs(price - ask) < 0.01 if ask > 0 else False
        at_bid = abs(price - bid) < 0.01 if bid > 0 else False
        between_market = not at_ask and not at_bid

        # Volume/OI ratio
        volume = trade_data.get('volume', 0)
        oi = trade_data.get('open_interest', 1)
        vol_oi_ratio = volume / oi if oi > 0 else 0

        flow = OptionsFlow(
            timestamp=trade_data.get('timestamp', datetime.now(UTC)),
            symbol=trade_data['symbol'],
            strike=trade_data['strike'],
            expiry=trade_data['expiry'],
            option_type=trade_data['option_type'],
            size=size,
            price=price,
            premium=premium,
            underlying_price=trade_data.get('underlying_price', 0),
            implied_volatility=trade_data.get('iv', 0.20),
            delta=trade_data.get('delta', 0),
            gamma=trade_data.get('gamma', 0),
            order_type=order_type,
            flow_type=FlowType.REGULAR,
            aggressor=aggressor,
            at_ask=at_ask,
            at_bid=at_bid,
            between_market=between_market,
            volume_today=volume,
            open_interest=oi,
            volume_oi_ratio=vol_oi_ratio,
            is_unusual=False,
            is_sweep=False,
            is_block=False,
            is_repeat=False,
            sentiment_score=0.0,
            toxicity_score=0.0
        )

        return flow

    def _determine_order_type(self, trade_data: dict) -> OrderType:
        """Determine if trade is opening or closing"""
        # Simplified logic - would use more sophisticated methods
        oi_change = trade_data.get('oi_change', 0)

        if oi_change > 0:
            # Opening position
            if trade_data.get('aggressor') == 'BUY':
                return BUY_TO_OPEN
            else:
                return SELL_TO_OPEN
        elif oi_change < 0:
            # Closing position
            if trade_data.get('aggressor') == 'BUY':
                return BUY_TO_CLOSE
            else:
                return SELL_TO_CLOSE
        else:
            return UNKNOWN

    def _determine_aggressor(self, trade_data: dict) -> AggressorSide:
        """Determine trade aggressor"""
        price = trade_data.get('price', 0)
        bid = trade_data.get('bid', 0)
        ask = trade_data.get('ask', 0)

        if ask > 0 and abs(price - ask) < 0.01:
            return AggressorSide.BUY
        elif bid > 0 and abs(price - bid) < 0.01:
            return AggressorSide.SELL
        else:
            # Use tick direction
            tick = trade_data.get('tick_direction', 0)
            if tick > 0:
                return AggressorSide.BUY
            elif tick < 0:
                return AggressorSide.SELL
            else:
                return AggressorSide.NEUTRAL

    def _classify_flow(self, flow: OptionsFlow) -> OptionsFlow:
        """Classify flow type"""
        # Check for block trade
        if flow.size >= BLOCK_SIZE:
            flow.flow_type = FlowType.BLOCK
            flow.is_block = True

        # Check for split trade (multiple exchanges)
        # This would need exchange data

        # Check for unusual volume
        if flow.volume_oi_ratio >= UNUSUAL_VOLUME_RATIO:
            flow.flow_type = FlowType.UNUSUAL
            flow.is_unusual = True

        return flow

    # ==========================================================================
    # UNUSUAL ACTIVITY DETECTION
    # ==========================================================================

    def _check_unusual_activity(self, flow: OptionsFlow) -> OptionsFlow:
        """Check for unusual options activity"""
        unusual_indicators = 0

        # High volume relative to OI
        if flow.volume_oi_ratio >= UNUSUAL_VOLUME_RATIO:
            unusual_indicators += 1

        # Large premium
        if flow.premium >= self.min_premium * 5:
            unusual_indicators += 1

        # Far OTM with high volume
        moneyness = flow.strike / flow.underlying_price
        if (flow.option_type == 'CALL' and moneyness > 1.10) or \
           (flow.option_type == 'PUT' and moneyness < 0.90):
            if flow.volume_today > 1000:
                unusual_indicators += 1

        # Near expiry with high activity
        days_to_expiry = (flow.expiry - datetime.now(UTC)).days
        if days_to_expiry <= 7 and flow.size >= 500:
            unusual_indicators += 1

        # Mark as unusual if multiple indicators
        if unusual_indicators >= 2:
            flow.is_unusual = True
            flow.flow_type = FlowType.UNUSUAL
            self.unusual_activity.append(flow)

        return flow

    def _check_sweep(self, flow: OptionsFlow) -> None:
        """Check for sweep orders"""
        key = (flow.symbol, flow.strike, flow.expiry, flow.option_type)

        # Add to sweep tracker
        self.sweep_tracker[key].append(flow)

        # Remove old flows outside window
        cutoff = datetime.now(UTC) - timedelta(seconds=SWEEP_TIME_WINDOW)
        self.sweep_tracker[key] = [
            f for f in self.sweep_tracker[key]
            if f.timestamp > cutoff
        ]

        # Check if this is a sweep
        if len(self.sweep_tracker[key]) >= 3:
            # Multiple trades at different prices in quick succession
            prices = [f.price for f in self.sweep_tracker[key]]
            if len(set(prices)) >= 2:
                flow.is_sweep = True
                flow.flow_type = FlowType.SWEEP

                # Mark all related flows as sweep
                for f in self.sweep_tracker[key]:
                    f.is_sweep = True
                    f.flow_type = FlowType.SWEEP

    def _check_repeat(self, flow: OptionsFlow) -> None:
        """Check for repeat buying"""
        key = (flow.symbol, flow.strike, flow.expiry, flow.option_type)

        # Track repeat activity
        self.repeat_tracker[key].append(flow.timestamp)

        # Remove old timestamps
        cutoff = datetime.now(UTC) - timedelta(hours=1)
        self.repeat_tracker[key] = [
            t for t in self.repeat_tracker[key]
            if t > cutoff
        ]

        # Check for repeat pattern
        if len(self.repeat_tracker[key]) >= 3:
            flow.is_repeat = True
            flow.flow_type = FlowType.REPEAT

    def _check_block(self, flow: OptionsFlow) -> None:
        """Check for block trades"""
        if flow.size >= BLOCK_SIZE:
            flow.is_block = True
            flow.flow_type = FlowType.BLOCK

    # ==========================================================================
    # SENTIMENT ANALYSIS
    # ==========================================================================

    def _calculate_flow_sentiment(self, flow: OptionsFlow) -> float:
        """Calculate sentiment score for individual flow"""
        sentiment = 0.0

        # Base sentiment from option type and order type
        if flow.option_type == 'CALL':
            if flow.order_type == BUY_TO_OPEN:
                sentiment = 0.8  # Bullish
            elif flow.order_type == SELL_TO_OPEN:
                sentiment = -0.3  # Slightly bearish (could be covered call)
        else:  # PUT
            if flow.order_type == BUY_TO_OPEN:
                sentiment = -0.8  # Bearish
            elif flow.order_type == SELL_TO_OPEN:
                sentiment = 0.3  # Slightly bullish (could be cash-secured put)

        # Adjust for aggressiveness
        if flow.at_ask:
            sentiment *= 1.2  # More aggressive
        elif flow.at_bid:
            sentiment *= 0.8  # Less aggressive

        # Adjust for size
        if flow.is_block:
            sentiment *= 1.5  # Institutional likely

        # Adjust for unusual activity
        if flow.is_unusual:
            sentiment *= 1.3

        # Clamp to [-1, 1]
        sentiment = max(-1.0, min(1.0, sentiment))

        return sentiment

    def calculate_market_sentiment(self, symbol: str,
                                  window: int = SENTIMENT_WINDOW) -> Sentiment:
        """
        Calculate overall market sentiment for symbol

        Args:
            symbol: Symbol to analyze
            window: Time window in seconds

        Returns:
            Sentiment enum
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=window)
        recent_flows = [
            f for f in self.symbol_flows[symbol]
            if f.timestamp > cutoff
        ]

        if not recent_flows:
            return Sentiment.NEUTRAL

        # Calculate call/put ratios
        call_volume = sum(f.size for f in recent_flows if f.option_type == 'CALL')
        put_volume = sum(f.size for f in recent_flows if f.option_type == 'PUT')

        call_premium = sum(f.premium for f in recent_flows if f.option_type == 'CALL')
        put_premium = sum(f.premium for f in recent_flows if f.option_type == 'PUT')

        # Volume-based sentiment
        if put_volume > 0:
            vol_ratio = call_volume / put_volume
        else:
            vol_ratio = float('inf') if call_volume > 0 else 1.0

        # Premium-based sentiment (more accurate)
        if put_premium > 0:
            prem_ratio = call_premium / put_premium
        else:
            prem_ratio = float('inf') if call_premium > 0 else 1.0

        # Average sentiment scores
        avg_sentiment = np.mean([f.sentiment_score for f in recent_flows])

        # Determine sentiment
        if prem_ratio > 2.0 or (vol_ratio > 2.5 and avg_sentiment > 0.5):
            sentiment = Sentiment.VERY_BULLISH
        elif prem_ratio > BULLISH_RATIO or (vol_ratio > 1.5 and avg_sentiment > 0.2):
            sentiment = Sentiment.BULLISH
        elif prem_ratio < 0.5 or (vol_ratio < 0.4 and avg_sentiment < -0.5):
            sentiment = Sentiment.VERY_BEARISH
        elif prem_ratio < BEARISH_RATIO or (vol_ratio < 0.67 and avg_sentiment < -0.2):
            sentiment = Sentiment.BEARISH
        else:
            sentiment = Sentiment.NEUTRAL

        # Store sentiment
        self.current_sentiment[symbol] = sentiment
        self.sentiment_history[symbol].append((datetime.now(UTC), sentiment))

        return sentiment

    # ==========================================================================
    # TOXICITY METRICS
    # ==========================================================================

    def _calculate_toxicity(self, flow: OptionsFlow) -> float:
        """Calculate flow toxicity (adverse selection)"""
        toxicity = 0.0

        # Quick price reversal after trade indicates toxicity
        # This would need tick data to implement properly

        # Proxy metrics for toxicity
        factors = []

        # Large size at market
        if flow.at_ask and flow.size >= BLOCK_SIZE:
            factors.append(0.3)

        # Sweep orders can be toxic
        if flow.is_sweep:
            factors.append(0.4)

        # Far OTM with urgency
        moneyness = flow.strike / flow.underlying_price
        if abs(1.0 - moneyness) > 0.15 and flow.at_ask:
            factors.append(0.2)

        # High IV trades
        if flow.implied_volatility > 0.50:
            factors.append(0.2)

        # Calculate weighted toxicity
        if factors:
            toxicity = min(1.0, sum(factors))

        return toxicity

    def calculate_flow_toxicity(self, symbol: str,
                               window: int = TOXICITY_WINDOW) -> FlowToxicity:
        """
        Calculate overall flow toxicity metrics

        Args:
            symbol: Symbol to analyze
            window: Time window in seconds

        Returns:
            FlowToxicity object
        """
        cutoff = datetime.now(UTC) - timedelta(seconds=window)
        recent_flows = [
            f for f in self.symbol_flows[symbol]
            if f.timestamp > cutoff
        ]

        if not recent_flows:
            return FlowToxicity(
                timestamp=datetime.now(UTC),
                symbol=symbol,
                toxicity_score=0.0,
                adverse_selection=0.0,
                informed_trading_probability=0.0,
                order_imbalance=0.0
            )

        # Average toxicity
        avg_toxicity = np.mean([f.toxicity_score for f in recent_flows])

        # Order imbalance
        buy_volume = sum(f.size for f in recent_flows if f.aggressor == AggressorSide.BUY)
        sell_volume = sum(f.size for f in recent_flows if f.aggressor == AggressorSide.SELL)
        total_volume = buy_volume + sell_volume

        if total_volume > 0:
            order_imbalance = abs(buy_volume - sell_volume) / total_volume
        else:
            order_imbalance = 0.0

        # Informed trading probability (PIN)
        # Simplified version
        unusual_count = sum(1 for f in recent_flows if f.is_unusual)
        if len(recent_flows) > 0:
            informed_prob = unusual_count / len(recent_flows)
        else:
            informed_prob = 0.0

        # Adverse selection (price impact)
        # This would need post-trade price data
        adverse_selection = avg_toxicity * 0.5  # Proxy

        return FlowToxicity(
            timestamp=datetime.now(UTC),
            symbol=symbol,
            toxicity_score=avg_toxicity,
            adverse_selection=adverse_selection,
            informed_trading_probability=informed_prob,
            order_imbalance=order_imbalance
        )

    # ==========================================================================
    # AGGREGATION AND ANALYSIS
    # ==========================================================================

    def _update_aggregated_flow(self, flow: OptionsFlow) -> None:
        """Update aggregated flow statistics"""
        symbol = flow.symbol

        if symbol not in self.aggregated_flows:
            self.aggregated_flows[symbol] = self._create_aggregated_flow(symbol)

        agg = self.aggregated_flows[symbol]

        # Update volumes
        if flow.option_type == 'CALL':
            agg.total_call_volume += flow.size
            agg.total_call_premium += flow.premium

            if flow.aggressor == AggressorSide.BUY:
                agg.buy_call_volume += flow.size
                agg.buy_call_premium += flow.premium
            else:
                agg.sell_call_volume += flow.size
                agg.sell_call_premium += flow.premium
        else:  # PUT
            agg.total_put_volume += flow.size
            agg.total_put_premium += flow.premium

            if flow.aggressor == AggressorSide.BUY:
                agg.buy_put_volume += flow.size
                agg.buy_put_premium += flow.premium
            else:
                agg.sell_put_volume += flow.size
                agg.sell_put_premium += flow.premium

        # Update Greeks flow
        agg.net_delta_flow += flow.delta * flow.size * 100
        agg.net_gamma_flow += flow.gamma * flow.size * 100

        # Update ratios
        if agg.total_put_volume > 0:
            agg.call_put_ratio = agg.total_call_volume / agg.total_put_volume

        if agg.total_call_volume > 0:
            agg.put_call_ratio = agg.total_put_volume / agg.total_call_volume

        total_buy = agg.buy_call_volume + agg.buy_put_volume
        total_sell = agg.sell_call_volume + agg.sell_put_volume
        if total_sell > 0:
            agg.buy_sell_ratio = total_buy / total_sell

        # Track unusual
        if flow.is_unusual:
            agg.unusual_trades.append(flow)

        if flow.is_sweep:
            agg.sweep_count += 1

        if flow.is_block:
            agg.block_count += 1

    def _create_aggregated_flow(self, symbol: str) -> AggregatedFlow:
        """Create new aggregated flow object"""
        return AggregatedFlow(
            symbol=symbol,
            time_window=timedelta(seconds=FLOW_WINDOW),
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC) + timedelta(seconds=FLOW_WINDOW),
            total_call_volume=0,
            total_put_volume=0,
            total_call_premium=0.0,
            total_put_premium=0.0,
            buy_call_volume=0,
            sell_call_volume=0,
            buy_put_volume=0,
            sell_put_volume=0,
            buy_call_premium=0.0,
            sell_call_premium=0.0,
            buy_put_premium=0.0,
            sell_put_premium=0.0,
            call_put_ratio=1.0,
            put_call_ratio=1.0,
            buy_sell_ratio=1.0,
            net_delta_flow=0.0,
            net_gamma_flow=0.0,
            net_vega_flow=0.0,
            sentiment=Sentiment.NEUTRAL,
            sentiment_strength=0.0,
            unusual_trades=[],
            sweep_count=0,
            block_count=0
        )

    # ==========================================================================
    # ALERTS AND SIGNALS
    # ==========================================================================

    def _generate_alerts(self, flow: OptionsFlow) -> None:
        """Generate alerts for significant flow"""
        alerts_generated = []

        # Unusual activity alert
        if flow.is_unusual:
            alert = FlowAlert(
                timestamp=datetime.now(UTC),
                alert_type="UNUSUAL_ACTIVITY",
                symbol=flow.symbol,
                message=f"Unusual options activity: {flow.symbol} {flow.strike} {flow.option_type}",
                flow=flow,
                significance=0.8,
                action_required=True
            )
            alerts_generated.append(alert)

        # Sweep alert
        if flow.is_sweep:
            alert = FlowAlert(
                timestamp=datetime.now(UTC),
                alert_type="SWEEP_DETECTED",
                symbol=flow.symbol,
                message=f"Sweep order detected: {flow.symbol} {flow.strike} {flow.option_type}",
                flow=flow,
                significance=0.9,
                action_required=True
            )
            alerts_generated.append(alert)

        # Large block alert
        if flow.is_block and flow.premium >= self.min_premium * 10:
            alert = FlowAlert(
                timestamp=datetime.now(UTC),
                alert_type="LARGE_BLOCK",
                symbol=flow.symbol,
                message=f"Large block trade: ${flow.premium:,.0f} in {flow.symbol}",
                flow=flow,
                significance=0.85,
                action_required=False
            )
            alerts_generated.append(alert)

        # Repeat buying alert
        if flow.is_repeat:
            alert = FlowAlert(
                timestamp=datetime.now(UTC),
                alert_type="REPEAT_BUYING",
                symbol=flow.symbol,
                message=f"Repeat buying detected: {flow.symbol} {flow.strike} {flow.option_type}",
                flow=flow,
                significance=0.7,
                action_required=False
            )
            alerts_generated.append(alert)

        # Store alerts
        self.alerts.extend(alerts_generated)

        # Log critical alerts
        for alert in alerts_generated:
            if alert.significance >= 0.8:
                self.logger.info("ALERT: %s", alert.message)

    def get_trading_signals(self, symbol: str) -> list[dict[str, Any]]:
        """
        Get trading signals based on flow analysis

        Args:
            symbol: Symbol to analyze

        Returns:
            List of trading signals
        """
        signals = []

        # Get recent sentiment
        sentiment = self.calculate_market_sentiment(symbol)

        # Get aggregated flow
        if symbol in self.aggregated_flows:
            agg = self.aggregated_flows[symbol]

            # Strong bullish signal
            if (sentiment == Sentiment.VERY_BULLISH and
                agg.call_put_ratio > 2.0 and
                agg.sweep_count > 3):
                signals.append({
                    'type': 'BULLISH',
                    'strength': 'STRONG',
                    'action': 'BUY_CALLS',
                    'reason': 'Strong bullish flow with sweeps',
                    'confidence': 0.8
                })

            # Strong bearish signal
            elif (sentiment == Sentiment.VERY_BEARISH and
                  agg.put_call_ratio > 2.0 and
                  agg.sweep_count > 3):
                signals.append({
                    'type': 'BEARISH',
                    'strength': 'STRONG',
                    'action': 'BUY_PUTS',
                    'reason': 'Strong bearish flow with sweeps',
                    'confidence': 0.8
                })

            # Unusual activity signal
            if len(agg.unusual_trades) >= 5:
                signals.append({
                    'type': 'UNUSUAL',
                    'strength': 'MODERATE',
                    'action': 'MONITOR',
                    'reason': f'{len(agg.unusual_trades)} unusual trades detected',
                    'confidence': 0.6
                })

            # High toxicity warning
            toxicity = self.calculate_flow_toxicity(symbol)
            if toxicity.toxicity_score > 0.7:
                signals.append({
                    'type': 'WARNING',
                    'strength': 'HIGH',
                    'action': 'AVOID',
                    'reason': 'High flow toxicity detected',
                    'confidence': 0.9
                })

        return signals

    # ==========================================================================
    # MARKET MAKER DETECTION
    # ==========================================================================

    def detect_market_maker_activity(self, symbol: str) -> MarketMakerActivity:
        """
        Detect market maker positioning

        Args:
            symbol: Symbol to analyze

        Returns:
            MarketMakerActivity object
        """
        recent_flows = self.symbol_flows[symbol][-100:]  # Last 100 trades

        if not recent_flows:
            return MarketMakerActivity(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                net_position_delta=0.0,
                hedging_flow=0.0,
                pin_risk_management=False,
                likely_direction='NEUTRAL'
            )

        # Calculate net delta position
        net_delta = sum(f.delta * f.size * 100 for f in recent_flows)

        # Detect hedging patterns
        delta_neutral_trades = 0
        for i in range(1, len(recent_flows)):
            if abs(recent_flows[i].delta + recent_flows[i-1].delta) < 0.1:
                delta_neutral_trades += 1

        hedging_ratio = delta_neutral_trades / len(recent_flows) if recent_flows else 0

        # Check for pin risk management (near expiry, ATM activity)
        pin_risk = False
        for flow in recent_flows:
            days_to_expiry = (flow.expiry - datetime.now(UTC)).days
            moneyness = flow.strike / flow.underlying_price

            if days_to_expiry <= 1 and 0.98 <= moneyness <= 1.02:
                pin_risk = True
                break

        # Determine likely direction
        if net_delta > 1000:
            direction = 'LONG'
        elif net_delta < -1000:
            direction = 'SHORT'
        else:
            direction = 'NEUTRAL'

        mm_activity = MarketMakerActivity(
            symbol=symbol,
            timestamp=datetime.now(UTC),
            net_position_delta=net_delta,
            hedging_flow=hedging_ratio,
            pin_risk_management=pin_risk,
            likely_direction=direction
        )

        self.mm_activity[symbol] = mm_activity

        return mm_activity

    # ==========================================================================
    # REPORTING
    # ==========================================================================

    def get_flow_summary(self, symbol: str) -> dict[str, Any]:
        """
        Get comprehensive flow summary for symbol

        Args:
            symbol: Symbol to summarize

        Returns:
            Summary dictionary
        """
        if symbol not in self.aggregated_flows:
            return {}

        agg = self.aggregated_flows[symbol]
        sentiment = self.current_sentiment.get(symbol, Sentiment.NEUTRAL)
        toxicity = self.calculate_flow_toxicity(symbol)
        mm_activity = self.mm_activity.get(symbol)

        summary = {
            'symbol': symbol,
            'timestamp': datetime.now(UTC),
            'volumes': {
                'total_call_volume': agg.total_call_volume,
                'total_put_volume': agg.total_put_volume,
                'total_premium': agg.total_call_premium + agg.total_put_premium
            },
            'ratios': {
                'call_put_ratio': agg.call_put_ratio,
                'put_call_ratio': agg.put_call_ratio,
                'buy_sell_ratio': agg.buy_sell_ratio
            },
            'sentiment': {
                'current': sentiment.value,
                'strength': agg.sentiment_strength
            },
            'unusual_activity': {
                'count': len(agg.unusual_trades),
                'sweep_count': agg.sweep_count,
                'block_count': agg.block_count
            },
            'toxicity': {
                'score': toxicity.toxicity_score,
                'informed_probability': toxicity.informed_trading_probability,
                'order_imbalance': toxicity.order_imbalance
            },
            'market_maker': {
                'net_delta': mm_activity.net_position_delta if mm_activity else 0,
                'direction': mm_activity.likely_direction if mm_activity else 'UNKNOWN'
            },
            'signals': self.get_trading_signals(symbol)
        }

        return summary

    def get_top_flows(self, n: int = 10) -> list[OptionsFlow]:
        """Get top flows by premium"""
        sorted_flows = sorted(self.flows, key=lambda x: x.premium, reverse=True)
        return sorted_flows[:n]

    def get_unusual_flows(self, symbol: str | None = None) -> list[OptionsFlow]:
        """Get unusual flows"""
        if symbol:
            return [f for f in self.unusual_activity if f.symbol == symbol]
        return self.unusual_activity

# ==============================================================================
# TEST/DEMO CODE
# ==============================================================================
if __name__ == "__main__":

    # Create tracker
    tracker = OptionsFlowTracker()

    # Generate synthetic flow data

    test_flows = [
        # Unusual large call sweep
        {
            'timestamp': datetime.now(UTC),
            'symbol': 'SPY',
            'strike': 590,
            'expiry': datetime.now(UTC) + timedelta(days=7),
            'option_type': 'CALL',
            'size': 5000,
            'price': 2.50,
            'bid': 2.48,
            'ask': 2.52,
            'underlying_price': 585,
            'volume': 15000,
            'open_interest': 5000,
            'iv': 0.18,
            'delta': 0.35,
            'gamma': 0.02
        },
        # Block put trade
        {
            'timestamp': datetime.now(UTC) - timedelta(seconds=30),
            'symbol': 'SPY',
            'strike': 580,
            'expiry': datetime.now(UTC) + timedelta(days=14),
            'option_type': 'PUT',
            'size': 1000,
            'price': 3.20,
            'bid': 3.15,
            'ask': 3.25,
            'underlying_price': 585,
            'volume': 8000,
            'open_interest': 12000,
            'iv': 0.20,
            'delta': -0.30,
            'gamma': 0.015
        },
        # Repeat call buying
        {
            'timestamp': datetime.now(UTC) - timedelta(seconds=60),
            'symbol': 'SPY',
            'strike': 588,
            'expiry': datetime.now(UTC) + timedelta(days=3),
            'option_type': 'CALL',
            'size': 300,
            'price': 1.85,
            'bid': 1.83,
            'ask': 1.87,
            'underlying_price': 585,
            'volume': 5000,
            'open_interest': 3000,
            'iv': 0.22,
            'delta': 0.45,
            'gamma': 0.03
        }
    ]

    # Process flows
    processed_flows = []
    for flow_data in test_flows:
        flow = tracker.process_flow(flow_data)
        processed_flows.append(flow)

    # Analyze sentiment
    sentiment = tracker.calculate_market_sentiment('SPY')

    # Get aggregated flow
    if 'SPY' in tracker.aggregated_flows:
        agg = tracker.aggregated_flows['SPY']

    # Check toxicity
    toxicity = tracker.calculate_flow_toxicity('SPY')

    # Detect market maker activity
    mm_activity = tracker.detect_market_maker_activity('SPY')

    # Get trading signals
    signals = tracker.get_trading_signals('SPY')
    for _signal in signals:
        pass

    # Check alerts
    for _alert in tracker.alerts:
        pass

    # Get top flows
    top_flows = tracker.get_top_flows(3)
    for _i, _ in enumerate(top_flows, 1):
        pass

    # Get comprehensive summary
    summary = tracker.get_flow_summary('SPY')
    if summary:
        pass

