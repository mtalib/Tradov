#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS08_ShortSqueezeDetector.py
Purpose: Detect rapid market spikes driven by short covering or short squeeze dynamics

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-27 Time: 00:00:00

Module Description:
    Multi-signal composite detector for short covering and short squeeze events
    in SPY. Combines five independent evidence streams into a single composite
    score (0–10) and classifies the spike type.

    Detection signals:
        1. Price Velocity       – Rapid intraday acceleration vs. rolling std dev
        2. Volume Surge         – Volume spike above rolling average
        3. Put/Call Collapse    – Sharp drop in put/call ratio or call sweep surge
        4. GEX Regime Shift     – Gamma flip cross or extreme-negative GEX
        5. Call Sweep Cluster   – Cluster of large aggressive call sweeps in a
                                  short window

    Output:
        SqueezeSignal with:
            • composite_score (0–10)
            • squeeze_type: SHORT_COVER | GAMMA_SQUEEZE | FEAR_RALLY | COMPOUND | NONE
            • strength:  NONE | WATCH | MODERATE | STRONG | EXTREME
            • component scores and   reasoning text
            • action_bias: trading posture suggestion

    Integration:
        # Standalone mode (auto-fetch via yfinance)
        detector = ShortSqueezeDetector(auto_fetch=True)
        signal = detector.detect()

        # Integrated mode (data driven by the pipeline)
        detector = ShortSqueezeDetector()
        detector.update_price_data(ohlcv_df)          # from SpyderC01/C08
        detector.update_options_flow(recent_flows)    # from SpyderC30
        detector.update_gex(gex_value, flip_level)    # from SpyderN09
        signal = detector.detect()

        # Module singleton
        from SpyderS_Signals.SpyderS08_ShortSqueezeDetector import get_squeeze_detector
        detector = get_squeeze_detector()
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore[assignment]
    _YFINANCE_AVAILABLE = False

try:
    from Spyder.SpyderC_MarketData.SpyderC29_DataProviderRouter import get_data_provider as _get_c29_provider
    _C29_AVAILABLE = True
except ImportError:
    _get_c29_provider = None  # type: ignore[assignment]
    _C29_AVAILABLE = False

try:
    import pandas as pd
    _PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PANDAS_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# Optional — OptionsFlow / TradeType types from SpyderC30.
# The detector degrades gracefully when flow data is absent.
try:
    from Spyder.SpyderC_MarketData.SpyderC30_OrderFlowAnalyzer import (
        OptionsFlow,
        TradeType,
    )
    _FLOW_TYPES_AVAILABLE = True
except ImportError:
    OptionsFlow = None  # type: ignore[assignment,misc]
    TradeType = None  # type: ignore[assignment,misc]
    _FLOW_TYPES_AVAILABLE = False

# ==============================================================================
# CONSTANTS — thresholds are tunable via the config dict
# ==============================================================================

# --- Price velocity ---
VELOCITY_WINDOW_BARS: int = 6       # Number of 5-min bars for velocity window
VELOCITY_ZSCORE_WATCH: float = 1.5  # z-score that starts the watch
VELOCITY_ZSCORE_MODERATE: float = 2.5
VELOCITY_ZSCORE_STRONG: float = 4.0

# --- Volume surge ---
VOLUME_LOOKBACK_BARS: int = 20      # Rolling average lookback (bars)
VOLUME_RATIO_WATCH: float = 2.0     # 2× average = watch
VOLUME_RATIO_MODERATE: float = 3.5
VOLUME_RATIO_STRONG: float = 6.0

# --- Put/call ratio collapse ---
PCR_LOOKBACK: int = 20              # Prior PCR readings used for baseline
PCR_DROP_WATCH: float = 0.20        # 20% relative drop = watch
PCR_DROP_MODERATE: float = 0.35
PCR_DROP_STRONG: float = 0.50

# --- GEX regime ---
GEX_EXTREME_NEGATIVE: float = -1_000_000_000   # -$1 B
GEX_NEGATIVE: float = -500_000_000             # -$500 M
GEX_FLIP_PROXIMITY_PCT: float = 0.005          # 0.5% of current price

# --- Call sweep cluster ---
SWEEP_WINDOW_MINUTES: int = 10      # Time window for sweep clustering
SWEEP_COUNT_WATCH: int = 3
SWEEP_COUNT_MODERATE: int = 5
SWEEP_COUNT_STRONG: int = 8
SWEEP_MIN_PREMIUM: float = 50_000   # Minimum $50 K per sweep

# --- Composite score thresholds ---
SCORE_WATCH: float = 2.5
SCORE_MODERATE: float = 4.5
SCORE_STRONG: float = 6.5
SCORE_EXTREME: float = 8.0

# --- Fear rally ---
FEAR_RALLY_VIX_MIN: float = 20.0    # VIX above this with price up = fear rally
FEAR_RALLY_PRICE_CHANGE_MIN: float = 0.003   # 0.3% minimum price rise

# ==============================================================================
# ENUMS
# ==============================================================================

class SqueezeType(Enum):
    """Classification of the dominant squeeze mechanism."""
    NONE = "none"
    SHORT_COVER = "short_cover"        # Shorts closing positions into a rally
    GAMMA_SQUEEZE = "gamma_squeeze"    # Dealer delta-hedging amplifying the move
    FEAR_RALLY = "fear_rally"          # Price up + VIX up — forced/panic covering
    COMPOUND = "compound"              # Two or more mechanisms simultaneously


class SqueezeStrength(Enum):
    """Categorical strength of the detected squeeze signal."""
    NONE = "none"
    WATCH = "watch"          # Score 2.5 – 4.5  — worth monitoring
    MODERATE = "moderate"    # Score 4.5 – 6.5  — probable short covering
    STRONG = "strong"        # Score 6.5 – 8.0  — strong squeeze in progress
    EXTREME = "extreme"      # Score 8.0 – 10.0 — extreme squeeze


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ComponentScore:
    """Score and reasoning for a single detection component."""
    name: str
    score: float        # 0.0 – 2.0
    weight: float       # Signal weight (all weights sum to 1.0)
    reading: float      # Raw numeric reading (z-score, ratio, count …)
    threshold: str      # Triggered threshold: "none" | "watch" | "moderate" | "strong"
    description: str    # Human-readable explanation

    @property
    def weighted_score(self) -> float:
        """Component contribution to the composite 0–1 score."""
        return self.score * self.weight


@dataclass
class SqueezeSignal:
    """
    Full output snapshot from ShortSqueezeDetector.

    Attributes:
        composite_score:  Weighted score, 0.0 – 10.0.
        squeeze_type:     Dominant mechanism detected.
        strength:         Categorical strength classification.
        components:       Per-signal breakdown list.
        reasoning:        Human-readable explanation string.
        timestamp:        UTC time signal was generated.
        price:            SPY price at detection time.
        price_change_pct: Fractional price change over the velocity window.
        vix_level:        VIX at detection time (0 if unavailable).
        action_bias:      Suggested trading posture for SPY options.
        confidence:       Fraction of components that had real data (0–1).
    """
    composite_score: float
    squeeze_type: SqueezeType
    strength: SqueezeStrength
    components: list[ComponentScore]
    reasoning: str
    timestamp: datetime
    price: float = 0.0
    price_change_pct: float = 0.0
    vix_level: float = 0.0
    action_bias: str = "neutral"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON / dashboard display."""
        return {
            "composite_score": round(self.composite_score, 2),
            "squeeze_type": self.squeeze_type.value,
            "strength": self.strength.value,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "price_change_pct": round(self.price_change_pct * 100, 3),
            "vix_level": self.vix_level,
            "action_bias": self.action_bias,
            "confidence": round(self.confidence, 2),
            "components": [
                {
                    "name": c.name,
                    "score": round(c.score, 2),
                    "weight": c.weight,
                    "weighted": round(c.weighted_score, 2),
                    "reading": round(c.reading, 4),
                    "threshold": c.threshold,
                    "description": c.description,
                }
                for c in self.components
            ],
        }

    def __str__(self) -> str:
        return (
            f"SqueezeSignal [{self.strength.value.upper()}] "
            f"type={self.squeeze_type.value} "
            f"score={self.composite_score:.1f}/10 "
            f"price={self.price:.2f} "
            f"Δ={self.price_change_pct * 100:+.2f}% "
            f"| {self.reasoning}"
        )


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class ShortSqueezeDetector:
    """
    Multi-signal short squeeze and short covering detector for SPY.

    Combines six independent evidence streams into a composite 0–10 score
    and classifies the spike type (GAMMA_SQUEEZE, SHORT_COVER, FEAR_RALLY,
    COMPOUND, or NONE).

    The detector operates in two modes:

    *Standalone* — set ``auto_fetch=True``.  On each ``detect()`` call the
    module fetches the latest SPY 5-min OHLCV bars, VIX readings, and the
    options-chain put/call ratio from yfinance.  No other modules needed.

    *Integrated* — push data from the live pipeline using the ``update_*``
    methods, then call ``detect()``.  Each component degrades gracefully when
    its data source is absent, so partial integration is fully supported.

    Args:
        symbol:     Instrument to monitor (default "SPY").
        auto_fetch: Populate price / VIX data from yfinance on every detect().
        config:     Optional override dict for any threshold constant.

    Example (standalone)::

        detector = ShortSqueezeDetector(auto_fetch=True)
        signal = detector.detect()
        if signal.strength != SqueezeStrength.NONE:
            print(signal)

    Example (integrated)::

        detector = ShortSqueezeDetector()
        detector.update_price_data(ohlcv_df)       # from SpyderC01_DataFeed
        detector.update_options_flow(flows)        # from SpyderC30_OrderFlowAnalyzer
        detector.update_gex(gex_val, flip_level)   # from SpyderN09_GammaExposure
        detector.update_breadth(tick, add, trin)   # from SpyderC04_MarketInternals
        signal = detector.detect()
    """

    def __init__(
        self,
        symbol: str = "SPY",
        auto_fetch: bool = False,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.symbol = symbol
        self.auto_fetch = auto_fetch
        self._cfg = config or {}
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self._lock = threading.RLock()

        # Price/volume rolling buffers (stores 5-min bar dicts)
        self._price_bars: deque[dict[str, float]] = deque(maxlen=60)  # ~5 hours
        self._vix_readings: deque[float] = deque(maxlen=20)

        # Options flow buffer (OptionsFlow objects, up to 1 hour old)
        self._flow_buffer: deque[Any] = deque(maxlen=2000)

        # Put/call ratio history (directly fed or computed from flow_buffer)
        self._pcr_history: deque[float] = deque(maxlen=PCR_LOOKBACK + 1)

        # GEX state from SpyderN09 / SpyderC30
        self._current_gex: float | None = None
        self._prev_gex: float | None = None
        self._gex_flip_level: float | None = None

        # Market breadth / internals from SpyderC04_MarketInternals
        self._breadth_tick: float | None = None   # NYSE TICK  ($TICK)
        self._breadth_add: float | None = None    # Advance-Decline difference ($ADD)
        self._breadth_trin: float | None = None   # Arms Index ($TRIN)

        # Latest computed signal
        self._latest_signal: SqueezeSignal | None = None

        self.logger.info(
            f"ShortSqueezeDetector initialised for {symbol} "
            f"(auto_fetch={auto_fetch})"
        )

    # ==========================================================================
    # PUBLIC — DATA FEED METHODS
    # ==========================================================================

    def update_price_data(self, bars: Any) -> None:
        """
        Ingest OHLCV bar data in bulk (e.g. from SpyderC01_DataFeed).

        Args:
            bars: pandas DataFrame with columns open/high/low/close/volume
                  (case-insensitive). Rows should be in chronological order.
                  The last 20 rows are ingested.
        """
        with self._lock:
            if bars is None or len(bars) == 0:
                return
            for _, row in bars.tail(20).iterrows():
                self._price_bars.append({
                    "open":   float(row.get("open",   row.get("Open",   0))),
                    "high":   float(row.get("high",   row.get("High",   0))),
                    "low":    float(row.get("low",    row.get("Low",    0))),
                    "close":  float(row.get("close",  row.get("Close",  0))),
                    "volume": float(row.get("volume", row.get("Volume", 0))),
                })

    def update_price_bar(
        self,
        close: float,
        volume: float,
        open_: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
    ) -> None:
        """
        Feed a single completed bar directly (real-time pipeline callers).

        Args:
            close:  Bar close price.
            volume: Bar volume.
            open_:  Bar open price  (defaults to close if omitted).
            high:   Bar high price  (defaults to close if omitted).
            low:    Bar low price   (defaults to close if omitted).
        """
        with self._lock:
            self._price_bars.append({
                "open":   open_ or close,
                "high":   high  or close,
                "low":    low   or close,
                "close":  close,
                "volume": volume,
            })

    def update_vix(self, vix_level: float) -> None:
        """Feed the latest VIX reading."""
        with self._lock:
            self._vix_readings.append(float(vix_level))

    def update_options_flow(self, flows: list) -> None:
        """
        Feed recent OptionsFlow records from SpyderC30_OrderFlowAnalyzer.

        Old flows (> 1 hour) are evicted automatically.

        Args:
            flows: List of OptionsFlow objects from the last N minutes.
        """
        with self._lock:
            cutoff = datetime.utcnow() - timedelta(hours=1)
            # Evict stale entries
            while self._flow_buffer and self._flow_buffer[0].timestamp < cutoff:
                self._flow_buffer.popleft()
            for flow in flows:
                self._flow_buffer.append(flow)

    def update_put_call_ratio(self, pcr: float) -> None:
        """
        Directly feed a pre-calculated put/call ratio reading.

        Useful when SpyderS07_CustomMetricsOrchestrator already has the value.

        Args:
            pcr: Current volume-based put/call ratio.
        """
        with self._lock:
            self._pcr_history.append(float(pcr))

    def update_gex(
        self,
        current_gex: float,
        flip_level: float | None = None,
    ) -> None:
        """
        Update gamma exposure state from SpyderN09_GammaExposure or
        SpyderC30_OrderFlowAnalyzer.

        Args:
            current_gex: Net dealer GEX in dollars.
                         Negative = dealers are short gamma (amplifies moves).
            flip_level:  Price level where GEX changes sign (None if unknown).
        """
        with self._lock:
            self._prev_gex = self._current_gex
            self._current_gex = float(current_gex)
            if flip_level is not None:
                self._gex_flip_level = float(flip_level)

    def update_breadth(
        self,
        tick: float | None = None,
        add: float | None = None,
        trin: float | None = None,
    ) -> None:
        """
        Feed NYSE market breadth data from SpyderC04_MarketInternals.

        Any subset of the three values may be provided; omitted arguments
        leave the stored value unchanged.  Called after each internals
        refresh in the live pipeline.

        Args:
            tick: NYSE TICK index ($TICK).  Positive = more upticks than
                  downticks across all NYSE issues.
            add:  NYSE Advance-Decline difference ($ADD).  Positive =
                  more advancing issues than declining.
            trin: TRIN / Arms Index ($TRIN).  < 1.0 = bullish volume
                  (advancing stocks dominating volume); > 1.0 = bearish.

        Example::

            mi = get_market_internals_analyzer()         # from SpyderC04
            detector.update_breadth(
                tick=mi.get_internal_value("TICK"),
                add=mi.get_internal_value("ADD"),
                trin=mi.get_internal_value("TRIN"),
            )
        """
        with self._lock:
            if tick is not None:
                self._breadth_tick = float(tick)
            if add is not None:
                self._breadth_add = float(add)
            if trin is not None:
                self._breadth_trin = float(trin)

    # ==========================================================================
    # PUBLIC — DETECTION
    # ==========================================================================

    def detect(self) -> SqueezeSignal:
        """
        Run the full six-component squeeze detection pipeline.

        If ``auto_fetch=True`` and yfinance is available, price/VIX data is
        refreshed from yfinance before detection runs.

        Returns:
            SqueezeSignal containing the composite score, type classification,
            component breakdown, and action bias.
        """
        with self._lock:
            if self.auto_fetch and _YFINANCE_AVAILABLE:
                self._auto_fetch_data()

            components: list[ComponentScore] = []
            data_count = 0  # Components with real (non-stub) data

            # ------------------------------------------------------------------
            c1, has_c1 = self._score_price_velocity()
            components.append(c1)
            data_count += int(has_c1)

            c2, has_c2 = self._score_volume_surge()
            components.append(c2)
            data_count += int(has_c2)

            c3, has_c3 = self._score_pcr_collapse()
            components.append(c3)
            data_count += int(has_c3)

            c4, has_c4 = self._score_gex_regime()
            components.append(c4)
            data_count += int(has_c4)

            c5, has_c5 = self._score_call_sweep_cluster()
            components.append(c5)
            data_count += int(has_c5)

            c6, has_c6 = self._score_breadth_narrowness()
            components.append(c6)
            data_count += int(has_c6)
            # ------------------------------------------------------------------

            # Weights sum to 1.0, so sum of weighted_score is 0–1.
            # Multiply by 10 → 0–10 composite.
            raw = sum(c.weighted_score for c in components)
            composite = min(10.0, raw * 10.0)

            strength = self._classify_strength(composite)
            squeeze_type = self._classify_type(components, has_c4)

            current_price = self._get_latest_price()
            price_change = self._get_recent_price_change()
            vix = self._vix_readings[-1] if self._vix_readings else 0.0
            action_bias = self._determine_action_bias(strength, squeeze_type, price_change)
            reasoning = self._build_reasoning(components, strength, squeeze_type, price_change)

            signal = SqueezeSignal(
                composite_score=round(composite, 2),
                squeeze_type=squeeze_type,
                strength=strength,
                components=components,
                reasoning=reasoning,
                timestamp=datetime.utcnow(),
                price=current_price,
                price_change_pct=price_change,
                vix_level=vix,
                action_bias=action_bias,
                confidence=round(data_count / 6.0, 2),
            )

            self._latest_signal = signal

            if strength not in (SqueezeStrength.NONE, SqueezeStrength.WATCH):
                self.logger.warning("Short squeeze detected: %s", signal)
            else:
                self.logger.debug(
                    f"No squeeze (score={composite:.2f}, data={data_count}/6)"
                )

            return signal

    def get_latest(self) -> SqueezeSignal | None:
        """Return the most recently computed signal, or None if never run."""
        return self._latest_signal

    def get_status_dict(self) -> dict[str, Any]:
        """
        Return a lightweight status dict suitable for dashboard display.

        Returns:
            Dict with keys: active, strength, score, type, price,
            price_change_pct, action_bias, confidence, reasoning,
            last_checked.
        """
        sig = self._latest_signal
        if sig is None:
            return {
                "active": False,
                "strength": SqueezeStrength.NONE.value,
                "score": 0.0,
                "type": SqueezeType.NONE.value,
                "price": 0.0,
                "price_change_pct": 0.0,
                "action_bias": "neutral",
                "confidence": 0.0,
                "reasoning": "Detector not yet run.",
                "last_checked": None,
            }
        return {
            "active": sig.strength != SqueezeStrength.NONE,
            "strength": sig.strength.value,
            "score": sig.composite_score,
            "type": sig.squeeze_type.value,
            "price": sig.price,
            "price_change_pct": round(sig.price_change_pct * 100, 3),
            "action_bias": sig.action_bias,
            "confidence": sig.confidence,
            "reasoning": sig.reasoning,
            "last_checked": sig.timestamp.isoformat(),
        }

    # ==========================================================================
    # PRIVATE — AUTO-FETCH (yfinance)
    # ==========================================================================

    def _auto_fetch_data(self) -> None:
        """Populate price bars, VIX, and PCR via C29 (preferred) or yfinance."""
        # SPY 5-min OHLCV — try C29 first
        _spy_fetched = False
        if _C29_AVAILABLE:
            try:
                from datetime import datetime as _dt, timedelta as _td
                client = _get_c29_provider()
                _end = _dt.now().strftime("%Y-%m-%d")
                _start = (_dt.now() - _td(days=2)).strftime("%Y-%m-%d")
                spy_df = client.get_historical_bars(
                    self.symbol, start=_start, end=_end, timespan="minute", multiplier=5
                )
                if spy_df is not None and not spy_df.empty:
                    self._price_bars.clear()
                    for _, row in spy_df.tail(40).iterrows():
                        self._price_bars.append({
                            "open":   float(row.get("open", 0.0)),
                            "high":   float(row.get("high", 0.0)),
                            "low":    float(row.get("low", 0.0)),
                            "close":  float(row.get("close", 0.0)),
                            "volume": float(row.get("volume", 0.0)),
                        })
                    _spy_fetched = True
            except Exception as exc:
                self.logger.debug("C29 SPY fetch failed: %s", exc)

        if not _spy_fetched and _YFINANCE_AVAILABLE:
            try:
                self.logger.debug("C29 unavailable for SPY bars — using yfinance fallback")
                spy = yf.download(
                    self.symbol,
                    period="2d",
                    interval="5m",
                    progress=False,
                    auto_adjust=True,
                )
                if spy is not None and len(spy) > 0:
                    self._price_bars.clear()
                    for _, row in spy.tail(40).iterrows():
                        self._price_bars.append({
                            "open":   float(row["Open"]),
                            "high":   float(row["High"]),
                            "low":    float(row["Low"]),
                            "close":  float(row["Close"]),
                            "volume": float(row["Volume"]),
                        })
            except Exception as exc:
                self.logger.debug("yfinance SPY fetch failed: %s", exc)

        # VIX — not available from MassiveClient; yfinance-only
        if _YFINANCE_AVAILABLE:
            try:
                self.logger.debug("Fetching ^VIX via yfinance (not available from MassiveClient)")
                vix = yf.download(
                    "^VIX",
                    period="1d",
                    interval="5m",
                    progress=False,
                    auto_adjust=True,
                )
                if vix is not None and len(vix) > 0:
                    self._vix_readings.clear()
                    for _, row in vix.tail(10).iterrows():
                        self._vix_readings.append(float(row["Close"]))
            except Exception as exc:
                self.logger.debug("yfinance VIX fetch failed: %s", exc)

        # Options chain put/call ratio — try C29 first
        if len(self._pcr_history) < 3:
            _pcr_fetched = False
            if _C29_AVAILABLE:
                try:
                    client = _get_c29_provider()
                    expirations = client.get_option_expirations(self.symbol)
                    if expirations:
                        contracts = client.get_option_chain(self.symbol, expiration=expirations[0])
                        call_vol = sum(c.get("volume", 0) or 0 for c in contracts if c.get("option_type") == "call")
                        put_vol = sum(c.get("volume", 0) or 0 for c in contracts if c.get("option_type") == "put")
                        if call_vol > 0:
                            self._pcr_history.append(put_vol / call_vol)
                            _pcr_fetched = True
                except Exception as exc:
                    self.logger.debug("C29 options chain fetch failed: %s", exc)

            if not _pcr_fetched and _YFINANCE_AVAILABLE:
                try:
                    self.logger.debug("C29 unavailable for options PCR — using yfinance fallback")
                    ticker = yf.Ticker(self.symbol)
                    exp = ticker.options
                    if exp:
                        chain = ticker.option_chain(exp[0])
                        call_vol = chain.calls["volume"].fillna(0).sum()
                        put_vol = chain.puts["volume"].fillna(0).sum()
                        if call_vol > 0:
                            self._pcr_history.append(put_vol / call_vol)
                except Exception as exc:
                    self.logger.debug("yfinance options chain fetch failed: %s", exc)

    # ==========================================================================
    # PRIVATE — COMPONENT SCORERS
    # Each returns (ComponentScore, bool) where bool = data was available.
    # ==========================================================================

    def _score_price_velocity(self) -> tuple[ComponentScore, bool]:
        """
        Score upside price acceleration against the rolling standard deviation.

        A short squeeze typically shows up as a price move that is several
        standard deviations larger than the trailing intraday noise, even
        before volume or flow signals confirm it.

        Returns:
            (ComponentScore, has_data)
        """
        bars = list(self._price_bars)
        min_bars = VELOCITY_WINDOW_BARS + 5
        if len(bars) < min_bars:
            return ComponentScore(
                name="price_velocity",
                score=0.0, weight=0.22, reading=0.0,
                threshold="none",
                description=f"Need ≥{min_bars} bars (have {len(bars)})",
            ), False

        closes = np.array([b["close"] for b in bars], dtype=float)
        returns = np.diff(closes) / closes[:-1]

        # N-bar return for the latest window
        recent_return = (
            (closes[-1] - closes[-VELOCITY_WINDOW_BARS]) / closes[-VELOCITY_WINDOW_BARS]
        )

        # Rolling std dev from the historical portion (exclude the recent window)
        hist_returns = returns[: -VELOCITY_WINDOW_BARS]
        hist_std = float(np.std(hist_returns)) if len(hist_returns) > 2 else 0.001
        if hist_std == 0:
            hist_std = 0.001

        # Scale std to match VELOCITY_WINDOW_BARS length
        scaled_std = hist_std * np.sqrt(VELOCITY_WINDOW_BARS)
        z_score = recent_return / scaled_std

        # Only score upside moves — short squeezes are rallies
        if z_score <= 0:
            score, threshold = 0.0, "none"
        elif z_score < VELOCITY_ZSCORE_WATCH:
            score, threshold = 0.3, "none"
        elif z_score < VELOCITY_ZSCORE_MODERATE:
            score, threshold = 1.0, "watch"
        elif z_score < VELOCITY_ZSCORE_STRONG:
            score, threshold = 1.6, "moderate"
        else:
            score, threshold = 2.0, "strong"

        return ComponentScore(
            name="price_velocity",
            score=score,
            weight=0.22,
            reading=round(z_score, 2),
            threshold=threshold,
            description=(
                f"{VELOCITY_WINDOW_BARS}-bar move {recent_return * 100:+.2f}% "
                f"= {z_score:.1f}σ above rolling baseline"
            ),
        ), True

    def _score_volume_surge(self) -> tuple[ComponentScore, bool]:
        """
        Score current bar volume relative to the rolling average.

        Short covering almost always produces an anomalous surge in volume
        as shorts race to cover and longs add momentum-driven positions.

        Returns:
            (ComponentScore, has_data)
        """
        bars = list(self._price_bars)
        min_bars = VOLUME_LOOKBACK_BARS + 1
        if len(bars) < min_bars:
            return ComponentScore(
                name="volume_surge",
                score=0.0, weight=0.18, reading=0.0,
                threshold="none",
                description=f"Need ≥{min_bars} bars (have {len(bars)})",
            ), False

        volumes = np.array([b["volume"] for b in bars], dtype=float)
        rolling_avg = float(np.mean(volumes[-VOLUME_LOOKBACK_BARS - 1: -1]))
        if rolling_avg <= 0:
            return ComponentScore(
                name="volume_surge",
                score=0.0, weight=0.18, reading=0.0,
                threshold="none",
                description="Average volume is zero",
            ), False

        ratio = volumes[-1] / rolling_avg

        if ratio < VOLUME_RATIO_WATCH:
            score, threshold = 0.0, "none"
        elif ratio < VOLUME_RATIO_MODERATE:
            score, threshold = 0.8, "watch"
        elif ratio < VOLUME_RATIO_STRONG:
            score, threshold = 1.5, "moderate"
        else:
            score, threshold = 2.0, "strong"

        return ComponentScore(
            name="volume_surge",
            score=score,
            weight=0.18,
            reading=round(ratio, 2),
            threshold=threshold,
            description=(
                f"Volume {ratio:.1f}× rolling {VOLUME_LOOKBACK_BARS}-bar average"
            ),
        ), True

    def _score_pcr_collapse(self) -> tuple[ComponentScore, bool]:
        """
        Score the collapse in the options put/call ratio.

        A rapidly falling PCR means puts are being closed and/or calls are
        being aggressively bought — a classic early-warning signal that
        shorts are covering.  The detector can compute PCR from the live
        flow buffer or from directly fed readings via update_put_call_ratio().

        Returns:
            (ComponentScore, has_data)
        """
        # If live flow data is available, compute the current PCR from it
        if _FLOW_TYPES_AVAILABLE and len(self._flow_buffer) >= 20:
            window_sec = 900  # last 15 minutes
            cutoff = datetime.utcnow() - timedelta(seconds=window_sec)
            recent_flows = [f for f in self._flow_buffer if f.timestamp >= cutoff]
            if recent_flows:
                call_vol = sum(
                    f.size for f in recent_flows if f.option_type == "call"
                )
                put_vol = sum(
                    f.size for f in recent_flows if f.option_type == "put"
                )
                if call_vol > 0:
                    self._pcr_history.append(put_vol / call_vol)

        if len(self._pcr_history) < 3:
            return ComponentScore(
                name="pcr_collapse",
                score=0.0, weight=0.18, reading=0.0,
                threshold="none",
                description="Need ≥3 PCR readings",
            ), False

        history = list(self._pcr_history)
        baseline = float(np.mean(history[:-1]))
        current = float(history[-1])

        if baseline <= 0:
            relative_drop = 0.0
        else:
            relative_drop = (baseline - current) / baseline  # positive = PCR fell

        if relative_drop <= 0:
            score, threshold = 0.0, "none"
        elif relative_drop < PCR_DROP_WATCH:
            score, threshold = 0.3, "none"
        elif relative_drop < PCR_DROP_MODERATE:
            score, threshold = 1.0, "watch"
        elif relative_drop < PCR_DROP_STRONG:
            score, threshold = 1.6, "moderate"
        else:
            score, threshold = 2.0, "strong"

        return ComponentScore(
            name="pcr_collapse",
            score=score,
            weight=0.18,
            reading=round(relative_drop, 4),
            threshold=threshold,
            description=(
                f"PCR {current:.2f} vs baseline {baseline:.2f} "
                f"({relative_drop * 100:+.1f}% drop)"
            ),
        ), True

    def _score_gex_regime(self) -> tuple[ComponentScore, bool]:
        """
        Score the GEX regime and proximity to the gamma flip level.

        When GEX is deeply negative, market makers are short gamma and
        *must* buy into rallies to stay delta-neutral — mechanically
        amplifying any short-driven spike.  A recent flip from negative
        to positive GEX is the single most powerful gamma-squeeze indicator.

        Returns:
            (ComponentScore, has_data)
        """
        if self._current_gex is None:
            return ComponentScore(
                name="gex_regime",
                score=0.0, weight=0.13, reading=0.0,
                threshold="none",
                description="No GEX data available",
            ), False

        gex = self._current_gex
        price = self._get_latest_price()
        score = 0.0
        threshold = "none"
        detail_parts: list[str] = []

        # --- Negative GEX score ---
        if gex < GEX_EXTREME_NEGATIVE:
            score += 1.5
            threshold = "strong"
            detail_parts.append(f"GEX extremely negative (${gex / 1e9:.1f}B)")
        elif gex < GEX_NEGATIVE:
            score += 0.8
            threshold = "watch"
            detail_parts.append(f"GEX negative (${gex / 1e9:.1f}B)")
        elif gex < 0:
            score += 0.3
            detail_parts.append(f"GEX slightly negative (${gex / 1e6:.0f}M)")
        else:
            detail_parts.append("GEX positive — limited dealer amplification")

        # --- GEX just flipped positive (strongest gamma-squeeze trigger) ---
        if self._prev_gex is not None and self._prev_gex < 0 and gex >= 0:
            score = min(2.0, score + 0.8)
            threshold = "strong"
            detail_parts.append("GEX just flipped positive — dealer buying triggered")
        elif self._gex_flip_level is not None and price > 0:
            dist_pct = abs(price - self._gex_flip_level) / self._gex_flip_level
            if dist_pct < GEX_FLIP_PROXIMITY_PCT:
                score = min(2.0, score + 0.5)
                threshold = threshold if threshold != "none" else "watch"
                detail_parts.append(
                    f"Price within {GEX_FLIP_PROXIMITY_PCT * 100:.1f}% of "
                    f"GEX flip level ({self._gex_flip_level:.2f})"
                )

        score = min(2.0, score)
        return ComponentScore(
            name="gex_regime",
            score=score,
            weight=0.13,
            reading=round(gex / 1e9, 3),
            threshold=threshold,
            description=" | ".join(detail_parts),
        ), True

    def _score_call_sweep_cluster(self) -> tuple[ComponentScore, bool]:
        """
        Score a cluster of large, aggressive call sweeps in a short window.

        Institutional short covering often precedes or accompanies rapid
        accumulation of near-the-money calls executed as exchange sweeps
        at the ask.  A burst of such sweeps in a 10-minute window is a
        high-conviction short-covering signal.

        Returns:
            (ComponentScore, has_data)
        """
        if not _FLOW_TYPES_AVAILABLE or len(self._flow_buffer) < 5:
            return ComponentScore(
                name="call_sweep_cluster",
                score=0.0, weight=0.17, reading=0.0,
                threshold="none",
                description="No options flow data",
            ), False

        cutoff = datetime.utcnow() - timedelta(minutes=SWEEP_WINDOW_MINUTES)
        recent = [f for f in self._flow_buffer if f.timestamp >= cutoff]

        # Aggressive call buys: side=ask/buy + minimum premium
        call_sweeps = [
            f for f in recent
            if f.option_type == "call"
            and getattr(f, "side", "mid") in ("ask", "buy")
            and getattr(f, "premium", 0) >= SWEEP_MIN_PREMIUM
        ]

        # Further filter to significant lot sizes (≥100 contracts)
        large_sweeps = [f for f in call_sweeps if f.size >= 100]
        count = len(large_sweeps)
        total_premium = sum(f.premium for f in call_sweeps)

        if count < SWEEP_COUNT_WATCH:
            score, threshold = 0.0, "none"
        elif count < SWEEP_COUNT_MODERATE:
            score, threshold = 0.8, "watch"
        elif count < SWEEP_COUNT_STRONG:
            score, threshold = 1.5, "moderate"
        else:
            score, threshold = 2.0, "strong"

        return ComponentScore(
            name="call_sweep_cluster",
            score=score,
            weight=0.17,
            reading=float(count),
            threshold=threshold,
            description=(
                f"{count} large call sweeps in last {SWEEP_WINDOW_MINUTES} min "
                f"(${total_premium / 1_000:.0f}K total premium)"
            ),
        ), True

    # ==========================================================================
    # PRIVATE — CLASSIFIERS AND HELPERS
    # ==========================================================================

    def _score_breadth_narrowness(self) -> tuple[ComponentScore, bool]:
        """
        Score how narrow the current advance is as evidence of a squeeze.

        A short squeeze lifts the index via forced covering concentrated in
        a handful of heavily-shorted names — the average stock does NOT
        participate:

        * $ADD stays low or negative despite an index gain.
        * $TRIN stays ≥ 1.0: advancing stocks lack volume support (forced,
          not genuine buying).
        * $TICK can spike briefly to extreme levels but rarely sustains.

        A genuine bullish reversal shows the opposite: large positive $ADD,
        $TRIN < 0.8, and sustained moderate-to-positive $TICK.

        Score semantics:  HIGH score (→ 2.0) = narrow advance = squeeze.
                          LOW  score (→ 0.0) = broad advance  = reversal.

        Feed data via ``update_breadth(tick, add, trin)`` before calling
        ``detect()``.  The component degrades gracefully to a zero-weight
        stub when no breadth data has been supplied.

        Returns:
            (ComponentScore, has_data)
        """
        tick = self._breadth_tick
        add  = self._breadth_add
        trin = self._breadth_trin

        if tick is None and add is None and trin is None:
            return ComponentScore(
                name="breadth_narrowness",
                score=0.0, weight=0.12, reading=0.0,
                threshold="none",
                description="No breadth data — call update_breadth()",
            ), False

        sub_scores: list[float] = []
        details: list[str] = []

        # --- $ADD sub-score (0 = broad reversal, 1 = narrow squeeze) ---
        if add is not None:
            if add < 0.0:
                add_sub = 1.0    # More declining than advancing → pure squeeze
            elif add < 200.0:
                add_sub = 0.85
            elif add < 500.0:
                add_sub = 0.60
            elif add < 1_000.0:
                add_sub = 0.35
            elif add < 1_500.0:
                add_sub = 0.12
            else:
                add_sub = 0.0    # Very broad advance → genuine reversal
            sub_scores.append(add_sub)
            details.append(f"ADD={add:+.0f}")

        # --- $TRIN sub-score (0 = bullish volume, 1 = volume not confirming) ---
        if trin is not None:
            if trin >= 1.4:
                trin_sub = 1.0   # Volume clearly NOT behind the advancing stocks
            elif trin >= 1.1:
                trin_sub = 0.70
            elif trin >= 0.9:
                trin_sub = 0.40  # Neutral territory
            elif trin >= 0.70:
                trin_sub = 0.12
            else:
                trin_sub = 0.0   # Strong bullish volume confirms the advance
            sub_scores.append(trin_sub)
            details.append(f"TRIN={trin:.2f}")

        # --- $TICK sub-score (extreme = panic/forced; moderate = orderly) ---
        if tick is not None:
            abs_tick = abs(tick)
            if abs_tick >= 900:
                # Extreme reading in either direction → panic / forced action
                tick_sub = 0.70
            elif abs_tick >= 600:
                tick_sub = 0.35
            elif abs_tick >= 300:
                tick_sub = 0.15
            else:
                tick_sub = 0.0
            sub_scores.append(tick_sub)
            details.append(f"TICK={tick:+.0f}")

        if not sub_scores:
            return ComponentScore(
                name="breadth_narrowness",
                score=0.0, weight=0.12, reading=0.0,
                threshold="none",
                description="All breadth values are None",
            ), False

        avg_sub = sum(sub_scores) / len(sub_scores)
        # Scale to 0–2 (same range ceiling as every other component)
        score = avg_sub * 2.0

        if score >= 1.5:
            threshold = "strong"
            label = "Very narrow breadth — squeeze signature"
        elif score >= 1.0:
            threshold = "moderate"
            label = "Narrow breadth"
        elif score >= 0.5:
            threshold = "watch"
            label = "Mixed breadth"
        else:
            threshold = "broad"
            label = "Broad advance — reversal signature"

        # Primary scalar reading for the dashboard: prefer ADD
        primary_reading = (
            add if add is not None else (trin if trin is not None else tick or 0.0)
        )
        return ComponentScore(
            name="breadth_narrowness",
            score=score,
            weight=0.12,
            reading=float(primary_reading),
            threshold=threshold,
            description=f"{label}: {', '.join(details)}",
        ), True

    # ==========================================================================
    # PRIVATE — CLASSIFIERS AND HELPERS
    # ==========================================================================

    def _classify_strength(self, score: float) -> SqueezeStrength:
        if score >= SCORE_EXTREME:
            return SqueezeStrength.EXTREME
        if score >= SCORE_STRONG:
            return SqueezeStrength.STRONG
        if score >= SCORE_MODERATE:
            return SqueezeStrength.MODERATE
        if score >= SCORE_WATCH:
            return SqueezeStrength.WATCH
        return SqueezeStrength.NONE

    def _classify_type(
        self, components: list[ComponentScore], has_gex: bool
    ) -> SqueezeType:
        """Determine the dominant squeeze mechanism from component scores."""
        by_name = {c.name: c.score for c in components}

        is_gamma = has_gex and by_name.get("gex_regime", 0.0) >= 1.0
        is_flow = (
            by_name.get("call_sweep_cluster", 0.0) >= 1.0
            or by_name.get("pcr_collapse", 0.0) >= 1.0
        )
        is_price_vol = (
            by_name.get("price_velocity", 0.0) >= 1.0
            and by_name.get("volume_surge", 0.0) >= 1.0
        )

        price_change = self._get_recent_price_change()
        vix = self._vix_readings[-1] if self._vix_readings else 0.0
        is_fear_rally = (
            price_change >= FEAR_RALLY_PRICE_CHANGE_MIN and vix >= FEAR_RALLY_VIX_MIN
        )

        # Breadth discrimination: a broad advance (many stocks participating)
        # refutes pure short-cover and points to a genuine bullish reversal.
        # breadth_narrowness score < 0.5 with real data → broad = NOT a squeeze.
        breadth_score = by_name.get("breadth_narrowness", -1.0)
        has_broad_breadth = (0.0 <= breadth_score < 0.5)

        active = sum([is_gamma, is_flow, is_price_vol, is_fear_rally])
        if active >= 2:
            return SqueezeType.COMPOUND
        if is_gamma:
            return SqueezeType.GAMMA_SQUEEZE
        if is_fear_rally:
            return SqueezeType.FEAR_RALLY
        if is_flow or is_price_vol:
            if has_broad_breadth:
                # Broad participation overrides the flow/price signal —
                # this looks like a genuine rally, not forced short covering.
                return SqueezeType.NONE
            return SqueezeType.SHORT_COVER
        return SqueezeType.NONE

    def _determine_action_bias(
        self,
        strength: SqueezeStrength,
        squeeze_type: SqueezeType,
        price_change: float,
    ) -> str:
        """
        Map strength + type to a suggested SPY options posture.

        Returns one of:
            "neutral"        — no evidence of squeeze
            "avoid_shorts"   — early warning; close / reduce short exposure
            "ride_calls"     — strong short cover / flow signal; calls directional
            "ride_gamma"     — gamma squeeze; short-dated calls, ladder strikes
            "hedge_or_flat"  — fear rally; uncertain reversal risk, flatten delta
        """
        if strength == SqueezeStrength.NONE:
            return "neutral"
        if strength == SqueezeStrength.WATCH:
            return "avoid_shorts"
        if squeeze_type == SqueezeType.GAMMA_SQUEEZE:
            return "ride_gamma"
        if squeeze_type == SqueezeType.FEAR_RALLY:
            return "hedge_or_flat"
        if strength in (SqueezeStrength.STRONG, SqueezeStrength.EXTREME):
            return "ride_calls"
        return "avoid_shorts"

    def _build_reasoning(
        self,
        components: list[ComponentScore],
        strength: SqueezeStrength,
        squeeze_type: SqueezeType,
        price_change: float,
    ) -> str:
        if strength == SqueezeStrength.NONE:
            return "No squeeze conditions detected."

        triggered = [c for c in components if c.threshold != "none"]
        if not triggered:
            return "Weak multi-signal convergence — no individual threshold breached."

        parts = [
            f"{c.name.replace('_', ' ').title()} ({c.description})"
            for c in triggered
        ]
        type_label = squeeze_type.value.replace("_", " ").title()
        return (
            f"{type_label} [{strength.value.upper()}]: "
            + "; ".join(parts)
            + f".  Price change: {price_change * 100:+.2f}%."
        )

    def _get_latest_price(self) -> float:
        bars = list(self._price_bars)
        return bars[-1]["close"] if bars else 0.0

    def _get_recent_price_change(self) -> float:
        bars = list(self._price_bars)
        if len(bars) < VELOCITY_WINDOW_BARS:
            return 0.0
        old = bars[-VELOCITY_WINDOW_BARS]["close"]
        new = bars[-1]["close"]
        return (new - old) / old if old else 0.0


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_detector_instance: ShortSqueezeDetector | None = None
_instance_lock = threading.Lock()


def get_squeeze_detector(
    symbol: str = "SPY",
    auto_fetch: bool = False,
) -> ShortSqueezeDetector:
    """
    Return the module-level singleton ShortSqueezeDetector.

    Thread-safe.  Creates the instance on first call; subsequent calls
    return the same object regardless of the arguments passed.

    Args:
        symbol:     Instrument (default "SPY").
        auto_fetch: Enable yfinance auto-population on first creation.

    Returns:
        The global ShortSqueezeDetector instance.
    """
    global _detector_instance
    with _instance_lock:
        if _detector_instance is None:
            _detector_instance = ShortSqueezeDetector(
                symbol=symbol, auto_fetch=auto_fetch
            )
        return _detector_instance


# ==============================================================================
# STANDALONE QUICK-TEST
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)  # noqa: T201
    print("ShortSqueezeDetector — standalone test (yfinance)")  # noqa: T201
    print("=" * 60)  # noqa: T201

    detector = ShortSqueezeDetector(symbol="SPY", auto_fetch=True)
    signal = detector.detect()
    print(signal)  # noqa: T201
    print()  # noqa: T201
    print("Full signal dict:")  # noqa: T201
    print(json.dumps(signal.to_dict(), indent=2))  # noqa: T201
