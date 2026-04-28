#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC04_MarketInternals.py
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
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventBus, EventType
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

INTERNAL_SYMBOLS = {
    "TICK": "$TICK",      # NYSE Tick Index (Tradier)
    "TICKI": "$TICKQ",   # Nasdaq Tick Index (Tradier)
    "ADD": "$ADD",        # NYSE Advance/Decline (Tradier)
    "VOLD": "NYSE:VOLD",  # NYSE Up/Down Volume (Tradier: none; Massive: I:VOLD)
    "TRIN": "$TRIN",      # NYSE Arms Index (Tradier)
    "TRINQ": "$TRINQ",    # Nasdaq Arms Index (Tradier)
    "VIX": "VIX",         # Volatility Index (Tradier)
    "VIX9D": "INDEX:VIX9D",  # 9-day VIX (event-bus only)
    "PCALL": "INDEX:PCALL",  # Put/Call Ratio All (event-bus only)
    "PCSP": "INDEX:PCSP",    # Put/Call Ratio SPX (event-bus only)
    "CPCE": "INDEX:CPCE",    # CBOE Equity Put/Call (event-bus only)
    "SKEW": "INDEX:SKEW",    # CBOE Skew Index (event-bus only)
    "SPXHILO": "NYSE:SPXHILO",  # S&P 500 New Highs/Lows (event-bus only)
    "NYHL": "NYSE:NYHL",        # NYSE New Highs/Lows (event-bus only)
    "NQHL": "NASDAQ:NQHL",      # Nasdaq New Highs/Lows (event-bus only)
    # 0-DTE mean-reversion abort gates (added 2026-04)
    "XLK": "XLK",      # Technology SPDR (Tradier equity quote)
    "XLF": "XLF",      # Financials SPDR (Tradier equity quote)
    "TNX": "$TNX",     # 10-Year Treasury Yield (Tradier index quote)
    # RVOL is computed locally from SPY volume — no fetch symbol
}

# Tradier-native symbols that can be fetched directly via get_quotes().
# Maps Tradier symbol string -> INTERNAL_SYMBOLS key.
# Source: Tradier official docs (April 2026 screenshot).
# $TICK and $ADD are confirmed Real-time; $VIX is confirmed Real-time.
# $TRIN, $TRINQ, $TICKQ are NOT listed in Tradier's official index symbol table
# and have been removed until confirmed working on a production account.
# XLK/XLF are standard equity ETFs; $TNX is Tradier's 10Y yield index symbol.
TRADIER_FETCHABLE_SYMBOLS = {
    "$TICK":  "TICK",
    "$ADD":   "ADD",
    "$VIX":   "VIX",
    "XLK":    "XLK",
    "XLF":    "XLF",
    "$TNX":   "TNX",
}

# SPY is fetched alongside internals solely to compute RVOL (Relative Volume).
# Its last/volume fields are NOT stored in internals_data — handled separately.
_SPY_RVOL_SYMBOL = "SPY"

# TNX intraday spike threshold (% move from session open that triggers warning)
TNX_SPIKE_PCT = 0.005  # 0.5% = meaningful intraday yield move

# RVOL thresholds
RVOL_HIGH = 2.0    # > 2× expected volume at this time of day — institutional activity
RVOL_LOW  = 0.4   # < 0.4× expected — suspiciously thin; fades may gap

# ET market session length constant
_SESSION_MINUTES: float = 390.0  # 9:30–16:00 ET

# How often (seconds) to poll Tradier for market internals
TRADIER_FETCH_INTERVAL = 5

# How often (seconds) to poll Massive (Polygon) for VOLD

# Thresholds
TICK_EXTREME_HIGH = 1000
TICK_EXTREME_LOW = -1000
TICK_OVERBOUGHT = 600
TICK_OVERSOLD = -600

TRIN_BULLISH = 0.7
TRIN_BEARISH = 1.3

VIX_LOW = 12
VIX_NORMAL = 20
VIX_HIGH = 25
VIX_EXTREME = 30

# Update intervals (seconds)
UPDATE_INTERVAL = 1
ANALYSIS_INTERVAL = 5

# ==============================================================================
# ENUMS
# ==============================================================================


class MarketCondition(Enum):
    """Market condition based on internals"""

    EXTREMELY_BULLISH = "extremely_bullish"
    BULLISH = "bullish"
    MODERATELY_BULLISH = "moderately_bullish"
    NEUTRAL = "neutral"
    MODERATELY_BEARISH = "moderately_bearish"
    BEARISH = "bearish"
    EXTREMELY_BEARISH = "extremely_bearish"


class BreadthCondition(Enum):
    """Market breadth condition"""

    EXTREMELY_STRONG = "extremely_strong"
    STRONG = "strong"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    WEAK = "weak"
    EXTREMELY_WEAK = "extremely_weak"


class MarketPhase(Enum):
    """Market phase detection"""

    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class InternalData:
    """Data structure for market internal"""

    symbol: str
    value: float
    timestamp: datetime
    change: float = 0.0
    percent_change: float = 0.0


@dataclass
class MarketInternalsSnapshot:
    """Snapshot of all market internals"""

    timestamp: datetime
    tick: float
    ticki: float
    add: float
    vold: float
    trin: float
    vix: float
    vix9d: float
    pcall: float
    pcsp: float
    cpce: float
    skew: float
    spx_hilo: float
    ny_hilo: float
    nq_hilo: float
    # 0-DTE abort-gate additions (2026-04)
    xlk: float = 0.0    # Technology SPDR last price
    xlf: float = 0.0    # Financials SPDR last price
    tnx: float = 0.0    # 10-Year Treasury Yield (%)
    rvol: float = 1.0   # SPY Relative Volume ratio (1.0 = normal)


@dataclass
class InternalsAnalysis:
    """Analysis of market internals"""

    timestamp: datetime
    market_condition: MarketCondition
    breadth_condition: BreadthCondition
    market_phase: MarketPhase
    tick_extreme: bool
    breadth_divergence: bool
    volume_confirmation: bool
    signal_strength: float  # -1 to 1
    confidence: float  # 0 to 1
    indicators: dict[str, float]
    warnings: list[str]


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class MarketInternalsAnalyzer:
    """
    Market internals analyzer for comprehensive market breadth analysis.

    This class monitors all major market internals including TICK, ADD, VOLD,
    TRIN, and various other breadth indicators to assess market sentiment
    and generate trading signals.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_bus: Event management system
        internals_data: Current internal values
        history: Historical data for analysis

    Example:
        >>> analyzer = MarketInternalsAnalyzer()
        >>> analyzer.initialize()
        >>> analysis = analyzer.get_current_analysis()
    """

    def __init__(self, tradier_client: Any = None):
        """Initialize the market internals analyzer.

        Args:
            tradier_client: Optional SpyderB40_TradierClient instance. When
                provided, market internals (TICK, TRIN, ADD, etc.) are fetched
                directly from Tradier every TRADIER_FETCH_INTERVAL seconds
                instead of relying solely on event-bus broadcasts.
"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_bus = EventBus()
        self.tradier_client = tradier_client

        # Data storage
        self.internals_data: dict[str, InternalData] = {}
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.snapshots: deque = deque(maxlen=500)

        # Analysis state
        self.current_analysis: InternalsAnalysis | None = None
        self.market_phase_history: deque = deque(maxlen=100)
        self.divergence_history: deque = deque(maxlen=50)

        # Control flags
        self.is_running = False
        self.update_thread: threading.Thread | None = None
        self.analysis_thread: threading.Thread | None = None
        self.lock = threading.Lock()

        # Callbacks
        self.analysis_callbacks: list[callable] = []

        # Tradier fetch tracking
        self._last_tradier_fetch: float = 0.0
        # Massive fetch tracking

        # RVOL computation state
        # SPY average_volume from Tradier quote (20-day trailing average)
        self._spy_avg_volume: float = 0.0
        # SPY cumulative volume at the start of today's session (pre-market clip)
        self._spy_session_start_volume: float = 0.0
        # Flag: session start volume has been captured
        self._spy_session_start_captured: bool = False
        # TNX at session open — for intraday spike calculation
        self._tnx_session_open: float = 0.0

        sources: list[str] = []
        if tradier_client:
            sources.append("Tradier")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize market internals monitoring.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing market internals monitoring")

            # Initialize data structures
            for symbol_key, symbol in INTERNAL_SYMBOLS.items():
                self.internals_data[symbol_key] = InternalData(
                    symbol=symbol, value=0.0, timestamp=datetime.now(timezone.utc)
                )
            # RVOL is computed locally — register a synthetic entry
            self.internals_data["RVOL"] = InternalData(
                symbol="RVOL", value=1.0, timestamp=datetime.now(timezone.utc)
            )

            # Subscribe to market data events
            self.event_bus.subscribe(EventType.MARKET_DATA, self._handle_market_data)

            # Start monitoring
            self.start()

            self.logger.info("Market internals monitoring initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            return False

    def start(self) -> None:
        """Start internals monitoring."""
        if not self.is_running:
            self.is_running = True

            # Start update thread
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()

            # Start analysis thread
            self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
            self.analysis_thread.start()

            self.logger.info("Market internals monitoring started")

    def stop(self) -> None:
        """Stop internals monitoring."""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        if self.analysis_thread:
            self.analysis_thread.join(timeout=5)
        self.logger.info("Market internals monitoring stopped")

    def update_internal(self, symbol: str, value: float) -> None:
        """
        Update internal value.

        Args:
            symbol: Internal symbol (e.g., 'TICK')
            value: Current value
        """
        with self.lock:
            if symbol in self.internals_data:
                old_value = self.internals_data[symbol].value
                self.internals_data[symbol].value = value
                self.internals_data[symbol].timestamp = datetime.now(timezone.utc)
                self.internals_data[symbol].change = value - old_value
                if old_value != 0:
                    self.internals_data[symbol].percent_change = (
                        (value - old_value) / abs(old_value) * 100
                    )

                # Add to history
                self.history[symbol].append({"timestamp": datetime.now(timezone.utc), "value": value})

    def get_current_analysis(self) -> InternalsAnalysis | None:
        """
        Get current market internals analysis.

        Returns:
            Current analysis or None
        """
        return self.current_analysis

    def get_internal_value(self, symbol: str) -> float | None:
        """
        Get current value for internal.

        Args:
            symbol: Internal symbol

        Returns:
            Current value or None
        """
        if symbol in self.internals_data:
            return self.internals_data[symbol].value
        return None

    def get_market_condition(self) -> MarketCondition:
        """
        Get current market condition.

        Returns:
            Current market condition
        """
        if self.current_analysis:
            return self.current_analysis.market_condition
        return MarketCondition.NEUTRAL

    def get_breadth_condition(self) -> BreadthCondition:
        """
        Get current breadth condition.

        Returns:
            Current breadth condition
        """
        if self.current_analysis:
            return self.current_analysis.breadth_condition
        return BreadthCondition.NEUTRAL

    def register_analysis_callback(self, callback: callable) -> None:
        """
        Register callback for analysis updates.

        Args:
            callback: Function to call with analysis
        """
        self.analysis_callbacks.append(callback)

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def analyze_tick(self) -> tuple[float, bool]:
        """
        Analyze NYSE TICK.

        Returns:
            Tuple of (signal_strength, is_extreme)
        """
        tick = self.get_internal_value("TICK") or 0

        # Calculate signal strength
        if tick >= TICK_EXTREME_HIGH:
            signal = 1.0
            extreme = True
        elif tick >= TICK_OVERBOUGHT:
            signal = 0.5 + 0.5 * (tick - TICK_OVERBOUGHT) / (TICK_EXTREME_HIGH - TICK_OVERBOUGHT)
            extreme = False
        elif tick <= TICK_EXTREME_LOW:
            signal = -1.0
            extreme = True
        elif tick <= TICK_OVERSOLD:
            signal = -0.5 - 0.5 * (tick - TICK_OVERSOLD) / (TICK_EXTREME_LOW - TICK_OVERSOLD)
            extreme = False
        else:
            signal = tick / TICK_OVERBOUGHT * 0.5
            extreme = False

        return signal, extreme

    def analyze_breadth(self) -> tuple[BreadthCondition, float]:
        """
        Analyze market breadth.

        Returns:
            Tuple of (breadth_condition, breadth_score)
        """
        add = self.get_internal_value("ADD") or 0
        vold = self.get_internal_value("VOLD") or 0

        # Calculate breadth score
        add_score = np.clip(add / 1000, -1, 1)
        vold_score = np.clip(vold / 1e9, -1, 1)
        breadth_score = (add_score + vold_score) / 2

        # Determine condition
        if breadth_score >= 0.8:
            condition = BreadthCondition.EXTREMELY_STRONG
        elif breadth_score >= 0.6:
            condition = BreadthCondition.STRONG
        elif breadth_score >= 0.2:
            condition = BreadthCondition.POSITIVE
        elif breadth_score >= -0.2:
            condition = BreadthCondition.NEUTRAL
        elif breadth_score >= -0.6:
            condition = BreadthCondition.NEGATIVE
        elif breadth_score >= -0.8:
            condition = BreadthCondition.WEAK
        else:
            condition = BreadthCondition.EXTREMELY_WEAK

        return condition, breadth_score

    def analyze_trin(self) -> float:
        """
        Analyze TRIN (Arms Index).

        Returns:
            TRIN signal (-1 to 1)
        """
        trin = self.get_internal_value("TRIN") or 1.0

        if trin <= TRIN_BULLISH:
            # Bullish
            signal = 1.0 - (trin / TRIN_BULLISH)
        elif trin >= TRIN_BEARISH:
            # Bearish
            signal = -1.0 * min((trin - TRIN_BEARISH) / TRIN_BEARISH, 1.0)
        else:
            # Neutral
            signal = (TRIN_BULLISH - trin) / (TRIN_BEARISH - TRIN_BULLISH)

        return signal

    def detect_divergence(self) -> tuple[bool, float]:
        """
        Detect price/breadth divergence.

        Returns:
            Tuple of (has_divergence, divergence_strength)
        """
        # Get recent history
        if len(self.snapshots) < 20:
            return False, 0.0

        recent_snapshots = list(self.snapshots)[-20:]

        # Calculate trends
        tick_values = [s.tick for s in recent_snapshots]
        add_values = [s.add for s in recent_snapshots]
        timestamps = list(range(len(recent_snapshots)))

        # Linear regression for trends
        tick_slope, _, tick_r, _, _ = stats.linregress(timestamps, tick_values)
        add_slope, _, add_r, _, _ = stats.linregress(timestamps, add_values)

        # Check for divergence
        divergence = False
        strength = 0.0

        if abs(tick_r) > 0.7 and abs(add_r) > 0.7:
            # Strong trends detected
            if (tick_slope > 0 and add_slope < 0) or (tick_slope < 0 and add_slope > 0):
                divergence = True
                strength = abs(tick_slope - add_slope) / max(abs(tick_slope), abs(add_slope))

        return divergence, strength

    def detect_market_phase(self) -> MarketPhase:
        """
        Detect current market phase.

        Returns:
            Current market phase
        """
        if len(self.snapshots) < 50:
            return MarketPhase.ACCUMULATION

        recent_snapshots = list(self.snapshots)[-50:]

        # Calculate indicators
        tick_avg = statistics.mean([s.tick for s in recent_snapshots])
        add_avg = statistics.mean([s.add for s in recent_snapshots])
        vold_avg = statistics.mean([s.vold for s in recent_snapshots])
        trin_avg = statistics.mean([s.trin for s in recent_snapshots])

        # Determine phase
        if tick_avg > 200 and add_avg > 500 and trin_avg < 1.0:
            phase = MarketPhase.MARKUP
        elif tick_avg < -200 and add_avg < -500 and trin_avg > 1.0:
            phase = MarketPhase.MARKDOWN
        elif abs(tick_avg) < 200 and trin_avg > 0.9 and trin_avg < 1.1:
            if vold_avg > 0:
                phase = MarketPhase.DISTRIBUTION
            else:
                phase = MarketPhase.ACCUMULATION
        else:
            phase = MarketPhase.ACCUMULATION

        return phase

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _update_loop(self) -> None:
        """Update loop for fetching internal data."""
        while self.is_running:
            try:
                now = time.monotonic()
                # Poll Tradier for live market internals (TICK, TRIN, ADD, VIX, etc.)
                if (
                    self.tradier_client is not None
                    and now - self._last_tradier_fetch >= TRADIER_FETCH_INTERVAL
                ):
                    self._fetch_from_tradier()
                    self._last_tradier_fetch = now

                # Create snapshot
                snapshot = self._create_snapshot()
                if snapshot:
                    with self.lock:
                        self.snapshots.append(snapshot)

                time.sleep(UPDATE_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Update loop error: %s", e)
                time.sleep(UPDATE_INTERVAL)  # thread-safe: time.sleep() intentional

    def _fetch_from_tradier(self) -> None:
        """Fetch market internals directly from Tradier API.

        Calls get_quotes() with all Tradier-supported internal symbols
        ($TICK, $ADD, $VIX, XLK, XLF, $TNX) plus SPY (for RVOL) and
        pushes the values into the internals_data store via update_internal().
        """
        try:
            # Include SPY alongside internals for RVOL computation
            symbols = list(TRADIER_FETCHABLE_SYMBOLS.keys()) + [_SPY_RVOL_SYMBOL]
            response = self.tradier_client.get_quotes(symbols)

            quotes_wrapper = (response or {}).get("quotes", {})
            if not quotes_wrapper:
                return

            raw = quotes_wrapper.get("quote", [])
            # Tradier returns a dict for one symbol, list for multiple
            if isinstance(raw, dict):
                raw = [raw]

            for quote in raw:
                tradier_symbol = quote.get("symbol", "")

                # --- SPY: extract volume fields for RVOL, do NOT store as internal ---
                if tradier_symbol == _SPY_RVOL_SYMBOL:
                    self._update_spy_rvol_state(quote)
                    continue

                internal_key = TRADIER_FETCHABLE_SYMBOLS.get(tradier_symbol)
                if not internal_key:
                    continue

                # Prefer last trade price; fall back to previous close
                value = quote.get("last") or quote.get("prevclose") or 0.0
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue

                if value != 0.0:
                    self.update_internal(internal_key, value)

                    # Track TNX session open for spike detection
                    if internal_key == "TNX" and self._tnx_session_open == 0.0:
                        self._tnx_session_open = value

        except Exception as e:
            self.logger.warning("Tradier internals fetch failed: %s", e)

    def _update_spy_rvol_state(self, quote: dict) -> None:
        """Extract SPY volume fields from a Tradier quote dict and update RVOL state.

        Uses Tradier's ``average_volume`` (20-day ADV) and ``volume`` (session
        cumulative) to compute ``rvol = current_vol / expected_vol_at_this_time``
        where ``expected = average_volume * elapsed_fraction_of_session``.

        RVOL > 1.0 means above-average activity; RVOL >= 2.0 is the abort gate.
        """
        try:
            avg_vol = float(quote.get("average_volume") or 0.0)
            cur_vol = float(quote.get("volume") or 0.0)
            if avg_vol > 0:
                self._spy_avg_volume = avg_vol
            if self._spy_avg_volume > 0 and cur_vol > 0:
                self.update_internal("RVOL", self._compute_rvol(cur_vol))
        except (TypeError, ValueError):
            pass

    def _compute_rvol(self, current_volume: float) -> float:
        """Compute SPY Relative Volume ratio.

        RVOL = current_cumulative_volume / expected_cumulative_volume_at_now

        Expected = ADV (20-day) × fraction of regular session elapsed.
        Session = 9:30–16:00 ET (390 minutes).
        Floor elapsed at 1 minute to avoid division-by-zero at the open.

        Returns:
            float: RVOL ratio (1.0 = perfectly normal; > 2.0 = institutional surge).
        """
        if self._spy_avg_volume <= 0:
            return 1.0
        # Compute ET time without importing pytz — use UTC offset heuristic
        now_utc = datetime.now(timezone.utc)
        # ET = UTC-4 (EDT summer) or UTC-5 (EST winter); use market-hours offset
        et_offset = timedelta(hours=-4)  # EDT (Mar–Nov); acceptable approximation
        now_et = now_utc + et_offset
        open_et = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        elapsed = (now_et - open_et).total_seconds() / 60.0
        elapsed = max(1.0, min(elapsed, _SESSION_MINUTES))
        fraction = elapsed / _SESSION_MINUTES
        expected = self._spy_avg_volume * fraction
        return round(current_volume / expected, 2) if expected > 0 else 1.0

    def _analysis_loop(self) -> None:
        """Analysis loop for processing internals."""
        while self.is_running:
            try:
                # Perform analysis
                analysis = self._perform_analysis()
                if analysis:
                    self.current_analysis = analysis

                    # Notify callbacks
                    for callback in self.analysis_callbacks:
                        try:
                            callback(analysis)
                        except Exception as e:
                            self.logger.error("Callback error: %s", e)

                    # Publish event
                    event = Event(
                        type=EventType.MARKET_INTERNALS,
                        data={"analysis": analysis, "timestamp": datetime.now(timezone.utc)},
                    )
                    self.event_bus.publish(event)

                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Analysis loop error: %s", e)
                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

    def _create_snapshot(self) -> MarketInternalsSnapshot | None:
        """Create snapshot of current internals."""
        try:
            with self.lock:
                snapshot = MarketInternalsSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    tick=self.get_internal_value("TICK") or 0,
                    ticki=self.get_internal_value("TICKI") or 0,
                    add=self.get_internal_value("ADD") or 0,
                    vold=self.get_internal_value("VOLD") or 0,
                    trin=self.get_internal_value("TRIN") or 1.0,
                    vix=self.get_internal_value("VIX") or 20,
                    vix9d=self.get_internal_value("VIX9D") or 20,
                    pcall=self.get_internal_value("PCALL") or 1.0,
                    pcsp=self.get_internal_value("PCSP") or 1.0,
                    cpce=self.get_internal_value("CPCE") or 1.0,
                    skew=self.get_internal_value("SKEW") or 125,
                    spx_hilo=self.get_internal_value("SPXHILO") or 0,
                    ny_hilo=self.get_internal_value("NYHL") or 0,
                    nq_hilo=self.get_internal_value("NQHL") or 0,
                    xlk=self.get_internal_value("XLK") or 0.0,
                    xlf=self.get_internal_value("XLF") or 0.0,
                    tnx=self.get_internal_value("TNX") or 0.0,
                    rvol=self.get_internal_value("RVOL") or 1.0,
                )
                return snapshot

        except Exception as e:
            self.logger.error("Error creating snapshot: %s", e)
            return None

    def _perform_analysis(self) -> InternalsAnalysis | None:
        """Perform comprehensive internals analysis."""
        try:
            # Get component analyses
            tick_signal, tick_extreme = self.analyze_tick()
            breadth_condition, breadth_score = self.analyze_breadth()
            trin_signal = self.analyze_trin()
            has_divergence, divergence_strength = self.detect_divergence()
            market_phase = self.detect_market_phase()

            # Calculate overall signal
            overall_signal = tick_signal * 0.4 + breadth_score * 0.3 + trin_signal * 0.3

            # Determine market condition
            if overall_signal >= 0.8:
                condition = MarketCondition.EXTREMELY_BULLISH
            elif overall_signal >= 0.5:
                condition = MarketCondition.BULLISH
            elif overall_signal >= 0.2:
                condition = MarketCondition.MODERATELY_BULLISH
            elif overall_signal >= -0.2:
                condition = MarketCondition.NEUTRAL
            elif overall_signal >= -0.5:
                condition = MarketCondition.MODERATELY_BEARISH
            elif overall_signal >= -0.8:
                condition = MarketCondition.BEARISH
            else:
                condition = MarketCondition.EXTREMELY_BEARISH

            # Check volume confirmation
            vold = self.get_internal_value("VOLD") or 0
            volume_confirmation = (overall_signal > 0 and vold > 0) or (
                overall_signal < 0 and vold < 0
            )

            # Calculate confidence
            confidence = min(
                abs(overall_signal), 1.0 - divergence_strength, 0.8 if volume_confirmation else 0.6
            )

            # Generate warnings
            warnings = []
            if tick_extreme:
                warnings.append("TICK at extreme levels")
            if has_divergence:
                warnings.append("Price/breadth divergence detected")
            if not volume_confirmation:
                warnings.append("Volume not confirming price action")

            # TNX spike abort gate
            tnx_now = self.get_internal_value("TNX") or 0.0
            if self._tnx_session_open > 0.0 and tnx_now > 0.0:
                tnx_chg = abs(tnx_now - self._tnx_session_open) / self._tnx_session_open
                if tnx_chg >= TNX_SPIKE_PCT:
                    direction = "up" if tnx_now > self._tnx_session_open else "down"
                    warnings.append(
                        f"TNX spike {direction} {tnx_chg * 100:.2f}% intraday — cancel pending pivots"  # noqa: E501
                    )

            # RVOL abort / confirmation gate
            rvol = self.get_internal_value("RVOL") or 1.0
            if rvol >= RVOL_HIGH:
                warnings.append(
                    f"RVOL={rvol:.1f}x — institutional surge; mean-reversion entries at risk"
                )
            elif rvol <= RVOL_LOW:
                warnings.append(
                    f"RVOL={rvol:.1f}x — thin volume; fills may gap on mean-reversion entries"
                )

            # Create analysis
            analysis = InternalsAnalysis(
                timestamp=datetime.now(timezone.utc),
                market_condition=condition,
                breadth_condition=breadth_condition,
                market_phase=market_phase,
                tick_extreme=tick_extreme,
                breadth_divergence=has_divergence,
                volume_confirmation=volume_confirmation,
                signal_strength=overall_signal,
                confidence=confidence,
                indicators={
                    "tick_signal": tick_signal,
                    "breadth_score": breadth_score,
                    "trin_signal": trin_signal,
                    "divergence_strength": divergence_strength,
                },
                warnings=warnings,
            )

            return analysis

        except Exception as e:
            self.logger.error("Error performing analysis: %s", e)
            return None

    def _handle_market_data(self, event: Event) -> None:
        """Handle market data events."""
        try:
            data = event.data
            symbol = data.get("symbol", "")

            # Check if it's an internal symbol
            for key, internal_symbol in INTERNAL_SYMBOLS.items():
                if symbol == internal_symbol:
                    value = data.get("last", 0)
                    self.update_internal(key, value)
                    break

        except Exception as e:
            self.logger.error("Error handling market data: %s", e)

    # ==========================================================================
    # ADVANCED ANALYSIS
    # ==========================================================================
    def get_sector_rotation_signals(self) -> dict[str, float]:
        """
        Get sector rotation signals based on internals.

        Returns:
            Dict of sector to signal strength
        """
        signals = {}

        # Analyze different internal combinations
        risk_on_score = 0.0
        defensive_score = 0.0

        # Risk-on indicators
        if self.get_internal_value("VIX") < VIX_LOW:
            risk_on_score += 0.3
        if self.get_internal_value("CPCE") < 0.7:
            risk_on_score += 0.3
        if self.get_internal_value("ADD") > 1000:
            risk_on_score += 0.4

        # Defensive indicators
        if self.get_internal_value("VIX") > VIX_HIGH:
            defensive_score += 0.3
        if self.get_internal_value("CPCE") > 1.2:
            defensive_score += 0.3
        if self.get_internal_value("ADD") < -1000:
            defensive_score += 0.4

        # Map to sectors
        if risk_on_score > defensive_score:
            signals["XLK"] = risk_on_score  # Technology
            signals["XLF"] = risk_on_score * 0.8  # Financials
            signals["XLY"] = risk_on_score * 0.7  # Consumer Discretionary
            signals["XLU"] = -risk_on_score * 0.5  # Utilities (inverse)
            signals["XLP"] = -risk_on_score * 0.5  # Consumer Staples (inverse)
        else:
            signals["XLU"] = defensive_score  # Utilities
            signals["XLP"] = defensive_score  # Consumer Staples
            signals["XLV"] = defensive_score * 0.8  # Healthcare
            signals["XLK"] = -defensive_score * 0.5  # Technology (inverse)
            signals["XLF"] = -defensive_score * 0.5  # Financials (inverse)

        return signals

    def get_trading_signals(self) -> dict[str, Any]:
        """
        Generate trading signals based on internals.

        Returns:
            Dict of trading signals and recommendations
        """
        if not self.current_analysis:
            return {}

        signals = {
            "timestamp": datetime.now(timezone.utc),
            "market_condition": self.current_analysis.market_condition.value,
            "signal_strength": self.current_analysis.signal_strength,
            "confidence": self.current_analysis.confidence,
            "recommendations": [],
        }

        # Generate recommendations based on conditions
        if self.current_analysis.tick_extreme:
            if self.current_analysis.signal_strength > 0.8:
                signals["recommendations"].append(
                    {
                        "action": "FADE",
                        "reason": "Extreme overbought TICK",
                        "strategy": "Bear Call Spread",
                    }
                )
            elif self.current_analysis.signal_strength < -0.8:
                signals["recommendations"].append(
                    {
                        "action": "FADE",
                        "reason": "Extreme oversold TICK",
                        "strategy": "Bull Put Spread",
                    }
                )

        if self.current_analysis.breadth_divergence:
            signals["recommendations"].append(
                {
                    "action": "CAUTION",
                    "reason": "Price/breadth divergence",
                    "strategy": "Reduce position size",
                }
            )

        # Market phase specific recommendations
        if self.current_analysis.market_phase == MarketPhase.MARKUP:
            signals["recommendations"].append(
                {
                    "action": "TREND_FOLLOW",
                    "reason": "Strong markup phase",
                    "strategy": "Bull Put Spreads",
                }
            )
        elif self.current_analysis.market_phase == MarketPhase.MARKDOWN:
            signals["recommendations"].append(
                {
                    "action": "TREND_FOLLOW",
                    "reason": "Strong markdown phase",
                    "strategy": "Bear Call Spreads",
                }
            )

        return signals


# ==============================================================================
# TEST SECTION
# ==============================================================================
if __name__ == "__main__":
    # Test the market internals analyzer
    analyzer = MarketInternalsAnalyzer()

    if analyzer.initialize():

        # Simulate some data updates
        test_data = {"TICK": 450, "ADD": 1200, "VOLD": 1.5e9, "TRIN": 0.85, "VIX": 18.5}

        for symbol, value in test_data.items():
            analyzer.update_internal(symbol, value)

        # Wait for analysis
        time.sleep(6)  # thread-safe: time.sleep() intentional

        # Get analysis
        analysis = analyzer.get_current_analysis()
        if analysis:

            if analysis.warnings:
                for _warning in analysis.warnings:
                    pass

        # Get trading signals
        signals = analyzer.get_trading_signals()
        if signals.get("recommendations"):
            for _rec in signals["recommendations"]:
                pass

        # Stop analyzer
        analyzer.stop()

class MarketInternals:
    """Main market internals coordinator class"""

    def __init__(self):
        self.current_data: InternalData | None = None
        self.current_snapshot: MarketInternalsSnapshot | None = None
        self.current_analysis: InternalsAnalysis | None = None

    def update_data(self, data: InternalData) -> None:
        """Update internal data"""
        self.current_data = data

    def update_snapshot(self, snapshot: MarketInternalsSnapshot) -> None:
        """Update market internals snapshot"""
        self.current_snapshot = snapshot

    def update_analysis(self, analysis: InternalsAnalysis) -> None:
        """Update internals analysis"""
        self.current_analysis = analysis

    def get_current_condition(self) -> MarketCondition:
        """Get current market condition"""
        if self.current_analysis:
            return self.current_analysis.market_condition
        return MarketCondition.NEUTRAL

    def get_breadth_condition(self) -> BreadthCondition:
        """Get current breadth condition"""
        if self.current_analysis:
            return self.current_analysis.breadth_condition
        return BreadthCondition.NEUTRAL

    def get_market_phase(self) -> MarketPhase:
        """Get current market phase"""
        if self.current_analysis:
            return self.current_analysis.market_phase
        return MarketPhase.ACCUMULATION

def get_market_internals() -> MarketInternals:
    """Factory function to get MarketInternals instance"""
    return MarketInternals()
