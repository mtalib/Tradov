#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF07_GapAnalyzer.py
Group: F (Technical Analysis)
Purpose: Gap analysis with news event correlation

Description:
    This module analyzes price gaps including overnight gaps, intraday gaps,
    and gap fills. It correlates gaps with news events to identify news-driven
    moves versus technical gaps.

Author: Claude AI (Enhanced by Maestro)
Date: 2024-01-07
Version: 2.0 - Added news event correlation and enhanced statistics
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from datetime import datetime, timedelta, time
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import FeatureFlags
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor

# ==============================================================================
# ENUMS
# ==============================================================================
class GapType(Enum):
    """Types of gaps."""
    COMMON = "common"           # Small, likely to fill
    BREAKAWAY = "breakaway"     # Start of new trend
    RUNAWAY = "runaway"         # Continuation gap
    EXHAUSTION = "exhaustion"   # End of trend
    OVERNIGHT = "overnight"     # Opening gap
    INTRADAY = "intraday"      # During trading hours
    WEEKEND = "weekend"        # Weekend gap

class GapDirection(Enum):
    """Gap direction."""
    UP = "up"
    DOWN = "down"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class NewsEvent:
    """News event data structure."""
    timestamp: datetime
    headline: str
    importance: str  # 'high', 'medium', 'low'
    category: str    # 'earnings', 'economic', 'fed', etc.
    sentiment: float = 0.0  # -1 to 1
    
@dataclass
class Gap:
    """Individual gap data."""
    gap_time: datetime
    gap_type: GapType
    direction: GapDirection
    size: float  # Absolute size
    size_percent: float  # Percentage size
    pre_gap_price: float
    post_gap_price: float
    volume_at_gap: float = 0
    filled: bool = False
    fill_time: Optional[datetime] = None
    fill_price: Optional[float] = None
    correlated_news: List[NewsEvent] = field(default_factory=list)
    
    @property
    def is_significant(self) -> bool:
        """Check if gap is significant (> 0.5%)."""
        return abs(self.size_percent) > 0.005
    
    @property
    def fill_percentage(self) -> float:
        """Calculate how much of gap was filled."""
        if not self.filled or not self.fill_price:
            return 0.0
        
        if self.direction == GapDirection.UP:
            fill_amount = self.post_gap_price - self.fill_price
        else:
            fill_amount = self.fill_price - self.post_gap_price
        
        return fill_amount / abs(self.size)
    
    @property
    def is_news_driven(self) -> bool:
        """Check if gap is likely news-driven."""
        return len(self.correlated_news) > 0

@dataclass
class GapStatistics:
    """Gap statistics for analysis."""
    total_gaps: int = 0
    up_gaps: int = 0
    down_gaps: int = 0
    filled_gaps: int = 0
    news_driven_gaps: int = 0
    avg_gap_size: float = 0.0
    avg_fill_time_minutes: float = 0.0
    fill_rate: float = 0.0
    news_correlation_rate: float = 0.0
    
@dataclass
class GapAnalysis:
    """Complete gap analysis results."""
    gaps: List[Gap]
    statistics: GapStatistics
    current_gap: Optional[Gap] = None
    gap_zones: List[Tuple[float, float]] = field(default_factory=list)  # Unfilled gap zones
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    
    def is_acceptable_for_entry(self) -> bool:
        """Check if current gap conditions are acceptable for entry."""
        if not self.current_gap:
            return True
        
        # Avoid trading large unfilled gaps
        if self.current_gap.is_significant and not self.current_gap.filled:
            return False
        
        # Avoid exhaustion gaps
        if self.current_gap.gap_type == GapType.EXHAUSTION:
            return False
        
        return True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/transmission."""
        return {
            'total_gaps': len(self.gaps),
            'statistics': {
                'fill_rate': self.statistics.fill_rate,
                'avg_gap_size': self.statistics.avg_gap_size,
                'news_correlation_rate': self.statistics.news_correlation_rate
            },
            'current_gap': {
                'exists': self.current_gap is not None,
                'size': self.current_gap.size_percent if self.current_gap else 0,
                'filled': self.current_gap.filled if self.current_gap else True,
                'news_driven': self.current_gap.is_news_driven if self.current_gap else False
            },
            'unfilled_zones': len(self.gap_zones)
        }

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class GapAnalyzer:
    """
    Gap analyzer with news correlation capability.
    
    Features:
    - Overnight and intraday gap detection
    - Gap classification and statistics
    - News event correlation
    - Gap fill tracking
    - Trading suitability assessment
    """
    
    def __init__(self, 
                 config_manager: Optional[ConfigManager] = None,
                 news_manager: Optional[Any] = None):
        """Initialize with optional news manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager or ConfigManager()
        self.news_manager = news_manager  # Optional news integration
        self.feature_flags = FeatureFlags()
        self.monitor = SystemMonitor()
        
        # Load configuration
        self._load_config()
        
        # Gap storage
        self.detected_gaps: List[Gap] = []
        self.gap_zones: List[Tuple[float, float]] = []
        
        self.logger.info("GapAnalyzer initialized with news correlation")
    
    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config('gap_analyzer', {})
        
        # Gap detection parameters
        self.min_gap_size = config.get('min_gap_size', 0.001)  # 0.1%
        self.significant_gap_size = config.get('significant_gap_size', 0.005)  # 0.5%
        self.lookback_days = config.get('lookback_days', 30)
        
        # Trading hours
        self.market_open = time(9, 30)
        self.market_close = time(16, 0)
        self.pre_market_start = time(4, 0)
        self.after_hours_end = time(20, 0)
        
        # News correlation
        self.news_window_minutes = config.get('news_window_minutes', 60)
        self.min_news_importance = config.get('min_news_importance', 'medium')
        
        # Feature flags
        self.enable_news_correlation = self.config_manager.is_feature_enabled('gap_news_correlation')
        self.enable_volume_analysis = config.get('enable_volume_analysis', True)
        self.track_gap_fills = config.get('track_gap_fills', True)
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    
    def analyze(self, data: pd.DataFrame, 
               current_price: Optional[float] = None) -> GapAnalysis:
        """
        Perform complete gap analysis.
        
        Args:
            data: OHLCV DataFrame with datetime index
            current_price: Current market price
            
        Returns:
            Complete gap analysis
        """
        start_time = datetime.now()
        
        try:
            # Detect all gaps
            gaps = self._detect_gaps(data)
            
            # Track gap fills if enabled
            if self.track_gap_fills:
                self._track_gap_fills(gaps, data)
            
            # Correlate with news if enabled
            if self.enable_news_correlation and self.news_manager:
                self._correlate_with_news(gaps)
            
            # Calculate statistics
            statistics = self._calculate_statistics(gaps)
            
            # Identify current gap
            current_gap = self._identify_current_gap(gaps, current_price or data['close'].iloc[-1])
            
            # Find unfilled gap zones
            gap_zones = self._find_unfilled_zones(gaps)
            
            # Create analysis result
            analysis = GapAnalysis(
                gaps=gaps,
                statistics=statistics,
                current_gap=current_gap,
                gap_zones=gap_zones
            )
            
            # Record metrics
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.monitor.record_metric('gap_analysis.execution_ms', elapsed_ms)
            self.monitor.record_metric('gap_analysis.gaps_found', len(gaps))
            
            # Store for reference
            self.detected_gaps = gaps
            self.gap_zones = gap_zones
            
            return analysis
            
        except Exception as e:
            self.error_handler.handle_error(e, "Gap analysis failed")
            return GapAnalysis([], GapStatistics())
    
    def calculate_overnight_gap(self, 
                              yesterday_close: float,
                              today_open: float) -> Optional[Gap]:
        """
        Calculate overnight gap between sessions.
        
        Args:
            yesterday_close: Previous session close
            today_open: Current session open
            
        Returns:
            Gap object if gap exists
        """
        gap_size = today_open - yesterday_close
        gap_percent = gap_size / yesterday_close
        
        if abs(gap_percent) < self.min_gap_size:
            return None
        
        return Gap(
            gap_time=datetime.now().replace(hour=9, minute=30),
            gap_type=GapType.OVERNIGHT,
            direction=GapDirection.UP if gap_size > 0 else GapDirection.DOWN,
            size=abs(gap_size),
            size_percent=abs(gap_percent),
            pre_gap_price=yesterday_close,
            post_gap_price=today_open
        )
    
    def is_gap_filled(self, gap: Gap, current_price: float) -> bool:
        """
        Check if a gap has been filled.
        
        Args:
            gap: Gap to check
            current_price: Current market price
            
        Returns:
            True if gap is filled
        """
        if gap.direction == GapDirection.UP:
            # Up gap is filled when price drops to pre-gap level
            return current_price <= gap.pre_gap_price
        else:
            # Down gap is filled when price rises to pre-gap level
            return current_price >= gap.pre_gap_price
    
    def get_gap_fill_probability(self, gap: Gap) -> float:
        """
        Estimate probability of gap fill based on historical data.
        
        Args:
            gap: Gap to analyze
            
        Returns:
            Fill probability (0-1)
        """
        if not self.detected_gaps:
            return 0.5  # Default
        
        # Find similar gaps
        similar_gaps = [g for g in self.detected_gaps 
                       if g.gap_type == gap.gap_type and
                       g.direction == gap.direction and
                       abs(g.size_percent - gap.size_percent) < 0.002]
        
        if not similar_gaps:
            # Use overall statistics
            filled = sum(1 for g in self.detected_gaps if g.filled)
            return filled / len(self.detected_gaps) if self.detected_gaps else 0.5
        
        # Calculate fill rate for similar gaps
        filled = sum(1 for g in similar_gaps if g.filled)
        return filled / len(similar_gaps)
    
    # ==========================================================================
    # GAP DETECTION
    # ==========================================================================
    
    def _detect_gaps(self, data: pd.DataFrame) -> List[Gap]:
        """Detect all gaps in the data."""
        gaps = []
        
        # Ensure datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            self.logger.warning("Data index is not datetime, gap detection may be inaccurate")
            return gaps
        
        # Sort by time
        data = data.sort_index()
        
        for i in range(1, len(data)):
            current = data.iloc[i]
            previous = data.iloc[i-1]
            
            # Check for time gap (new session)
            time_diff = data.index[i] - data.index[i-1]
            
            if time_diff > timedelta(hours=12):
                # Overnight gap
                gap = self._create_gap(
                    previous['close'],
                    current['open'],
                    data.index[i],
                    GapType.OVERNIGHT,
                    current.get('volume', 0)
                )
            elif time_diff > timedelta(days=2):
                # Weekend gap
                gap = self._create_gap(
                    previous['close'],
                    current['open'],
                    data.index[i],
                    GapType.WEEKEND,
                    current.get('volume', 0)
                )
            else:
                # Intraday gap (between candles)
                gap = self._create_gap(
                    previous['close'],
                    current['open'],
                    data.index[i],
                    GapType.INTRADAY,
                    current.get('volume', 0)
                )
            
            if gap:
                # Classify gap type
                gap.gap_type = self._classify_gap_type(gap, data, i)
                gaps.append(gap)
        
        return gaps
    
    def _create_gap(self, pre_price: float, post_price: float,
                   gap_time: datetime, gap_type: GapType,
                   volume: float = 0) -> Optional[Gap]:
        """Create gap object if gap is significant."""
        gap_size = post_price - pre_price
        gap_percent = gap_size / pre_price
        
        if abs(gap_percent) < self.min_gap_size:
            return None
        
        return Gap(
            gap_time=gap_time,
            gap_type=gap_type,
            direction=GapDirection.UP if gap_size > 0 else GapDirection.DOWN,
            size=abs(gap_size),
            size_percent=abs(gap_percent),
            pre_gap_price=pre_price,
            post_gap_price=post_price,
            volume_at_gap=volume
        )
    
    def _classify_gap_type(self, gap: Gap, data: pd.DataFrame, 
                         gap_index: int) -> GapType:
        """Classify gap as common, breakaway, runaway, or exhaustion."""
        if gap.gap_type != GapType.OVERNIGHT:
            return gap.gap_type
        
        # Look at context
        lookback = 10
        if gap_index < lookback:
            return GapType.COMMON
        
        # Previous trend
        prev_data = data.iloc[gap_index-lookback:gap_index]
        prev_returns = prev_data['close'].pct_change().mean()
        
        # Volume analysis
        if self.enable_volume_analysis and 'volume' in data.columns:
            avg_volume = prev_data['volume'].mean()
            gap_volume = gap.volume_at_gap
            volume_surge = gap_volume > avg_volume * 1.5
        else:
            volume_surge = False
        
        # Classification logic
        if abs(gap.size_percent) < self.significant_gap_size:
            return GapType.COMMON
        
        # Same direction as trend with volume = runaway
        if ((gap.direction == GapDirection.UP and prev_returns > 0) or
            (gap.direction == GapDirection.DOWN and prev_returns < 0)):
            if volume_surge:
                return GapType.RUNAWAY
            else:
                # Check if trend is exhausted
                if gap_index + 5 < len(data):
                    post_data = data.iloc[gap_index:gap_index+5]
                    post_returns = post_data['close'].pct_change().mean()
                    if ((gap.direction == GapDirection.UP and post_returns < 0) or
                        (gap.direction == GapDirection.DOWN and post_returns > 0)):
                        return GapType.EXHAUSTION
        
        # Opposite direction with volume = breakaway
        if volume_surge:
            return GapType.BREAKAWAY
        
        return GapType.COMMON
    
    # ==========================================================================
    # GAP FILL TRACKING
    # ==========================================================================
    
    def _track_gap_fills(self, gaps: List[Gap], data: pd.DataFrame):
        """Track which gaps have been filled."""
        for gap in gaps:
            if gap.filled:
                continue
            
            # Get data after gap
            post_gap_data = data[data.index > gap.gap_time]
            
            if post_gap_data.empty:
                continue
            
            # Check each candle for fill
            for idx, candle in post_gap_data.iterrows():
                if gap.direction == GapDirection.UP:
                    # Check if low touched pre-gap price
                    if candle['low'] <= gap.pre_gap_price:
                        gap.filled = True
                        gap.fill_time = idx
                        gap.fill_price = gap.pre_gap_price
                        break
                else:
                    # Check if high touched pre-gap price
                    if candle['high'] >= gap.pre_gap_price:
                        gap.filled = True
                        gap.fill_time = idx
                        gap.fill_price = gap.pre_gap_price
                        break
    
    # ==========================================================================
    # NEWS CORRELATION
    # ==========================================================================
    
    def _correlate_with_news(self, gaps: List[Gap]):
        """Correlate gaps with news events."""
        if not self.news_manager:
            return
        
        for gap in gaps:
            try:
                # Get news events around gap time
                start_time = gap.gap_time - timedelta(minutes=self.news_window_minutes)
                end_time = gap.gap_time + timedelta(minutes=15)
                
                news_events = self.news_manager.get_events(
                    start_time=start_time,
                    end_time=end_time,
                    min_importance=self.min_news_importance
                )
                
                # Filter relevant news
                relevant_news = []
                for event in news_events:
                    # Check if news could have caused gap
                    if event.timestamp < gap.gap_time:
                        # Check sentiment alignment
                        if ((gap.direction == GapDirection.UP and event.sentiment > 0) or
                            (gap.direction == GapDirection.DOWN and event.sentiment < 0) or
                            event.importance == 'high'):
                            relevant_news.append(event)
                
                gap.correlated_news = relevant_news
                
            except Exception as e:
                self.logger.warning(f"News correlation failed for gap: {e}")
    
    def _is_news_driven_gap(self, gap: Gap, news_events: List[NewsEvent]) -> bool:
        """Determine if gap is likely news-driven."""
        if not news_events:
            return False
        
        # Check for high-importance news
        high_importance = any(e.importance == 'high' for e in news_events)
        if high_importance:
            return True
        
        # Check for sentiment alignment
        avg_sentiment = np.mean([e.sentiment for e in news_events])
        sentiment_aligned = (
            (gap.direction == GapDirection.UP and avg_sentiment > 0.3) or
            (gap.direction == GapDirection.DOWN and avg_sentiment < -0.3)
        )
        
        return sentiment_aligned and len(news_events) >= 2
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def _calculate_statistics(self, gaps: List[Gap]) -> GapStatistics:
        """Calculate gap statistics."""
        if not gaps:
            return GapStatistics()
        
        stats = GapStatistics()
        stats.total_gaps = len(gaps)
        stats.up_gaps = sum(1 for g in gaps if g.direction == GapDirection.UP)
        stats.down_gaps = sum(1 for g in gaps if g.direction == GapDirection.DOWN)
        stats.filled_gaps = sum(1 for g in gaps if g.filled)
        stats.news_driven_gaps = sum(1 for g in gaps if g.is_news_driven)
        
        stats.avg_gap_size = np.mean([g.size_percent for g in gaps])
        stats.fill_rate = stats.filled_gaps / stats.total_gaps if stats.total_gaps > 0 else 0
        stats.news_correlation_rate = stats.news_driven_gaps / stats.total_gaps if stats.total_gaps > 0 else 0
        
        # Average fill time
        fill_times = []
        for gap in gaps:
            if gap.filled and gap.fill_time:
                fill_duration = (gap.fill_time - gap.gap_time).total_seconds() / 60
                fill_times.append(fill_duration)
        
        if fill_times:
            stats.avg_fill_time_minutes = np.mean(fill_times)
        
        return stats
    
    def _identify_current_gap(self, gaps: List[Gap], 
                            current_price: float) -> Optional[Gap]:
        """Identify if we're currently in a gap."""
        if not gaps:
            return None
        
        # Get today's gaps
        today = datetime.now().date()
        todays_gaps = [g for g in gaps if g.gap_time.date() == today]
        
        if not todays_gaps:
            return None
        
        # Get most recent gap
        latest_gap = max(todays_gaps, key=lambda g: g.gap_time)
        
        # Check if still in gap
        if not latest_gap.filled:
            return latest_gap
        
        return None
    
    def _find_unfilled_zones(self, gaps: List[Gap]) -> List[Tuple[float, float]]:
        """Find price zones with unfilled gaps."""
        zones = []
        
        for gap in gaps:
            if not gap.filled and gap.is_significant:
                if gap.direction == GapDirection.UP:
                    # Unfilled zone below current price
                    zones.append((gap.pre_gap_price, gap.post_gap_price))
                else:
                    # Unfilled zone above current price
                    zones.append((gap.post_gap_price, gap.pre_gap_price))
        
        # Merge overlapping zones
        if zones:
            zones = self._merge_overlapping_zones(zones)
        
        return zones
    
    def _merge_overlapping_zones(self, zones: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Merge overlapping gap zones."""
        if not zones:
            return []
        
        # Sort by lower bound
        sorted_zones = sorted(zones, key=lambda z: min(z))
        merged = [sorted_zones[0]]
        
        for zone in sorted_zones[1:]:
            last_zone = merged[-1]
            
            # Check for overlap
            if (min(zone) <= max(last_zone) and max(zone) >= min(last_zone)):
                # Merge zones
                merged[-1] = (min(min(zone), min(last_zone)), 
                            max(max(zone), max(last_zone)))
            else:
                merged.append(zone)
        
        return merged


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data with gaps
    dates = []
    prices = []
    volumes = []
    
    # Generate data with some gaps
    current_date = datetime(2024, 1, 1, 9, 30)
    price = 585.0
    
    for day in range(20):
        # Morning gap
        if day > 0:
            # Create overnight gap
            gap_size = np.random.normal(0, 2)
            if abs(gap_size) > 1:  # Significant gap
                price += gap_size
        
        # Intraday data
        for hour in range(7):  # 9:30 AM to 4:00 PM
            for minute in range(0, 60, 5):
                dates.append(current_date + timedelta(days=day, hours=hour, minutes=minute))
                
                # Normal price movement
                price += np.random.normal(0, 0.1)
                prices.append(price)
                volumes.append(np.random.randint(1000, 5000))
    
    # Create DataFrame
    data = pd.DataFrame({
        'open': prices,
        'high': [p + abs(np.random.normal(0, 0.1)) for p in prices],
        'low': [p - abs(np.random.normal(0, 0.1)) for p in prices],
        'close': [p + np.random.normal(0, 0.05) for p in prices],
        'volume': volumes
    }, index=dates)
    
    # Mock news manager
    class MockNewsManager:
        def get_events(self, start_time, end_time, min_importance='medium'):
            # Generate some fake news
            events = []
            if np.random.random() > 0.5:
                events.append(NewsEvent(
                    timestamp=start_time + timedelta(minutes=30),
                    headline="Fed Minutes Released",
                    importance='high',
                    category='fed',
                    sentiment=np.random.uniform(-1, 1)
                ))
            return events
    
    # Initialize analyzer
    config_manager = ConfigManager()
    news_manager = MockNewsManager()
    analyzer = GapAnalyzer(config_manager, news_manager)
    
    # Analyze gaps
    print("=== Gap Analysis ===")
    analysis = analyzer.analyze(data)
    
    print(f"Total gaps found: {analysis.statistics.total_gaps}")
    print(f"Up gaps: {analysis.statistics.up_gaps}")
    print(f"Down gaps: {analysis.statistics.down_gaps}")
    print(f"Fill rate: {analysis.statistics.fill_rate:.1%}")
    print(f"Average gap size: {analysis.statistics.avg_gap_size:.3%}")
    print(f"News correlation rate: {analysis.statistics.news_correlation_rate:.1%}")
    
    # Show significant gaps
    print("\n=== Significant Gaps ===")
    significant_gaps = [g for g in analysis.gaps if g.is_significant]
    
    for gap in significant_gaps[:5]:
        print(f"\nTime: {gap.gap_time}")
        print(f"Type: {gap.gap_type.value}")
        print(f"Direction: {gap.direction.value}")
        print(f"Size: {gap.size_percent:.2%}")
        print(f"Filled: {gap.filled}")
        if gap.filled and gap.fill_time:
            fill_minutes = (gap.fill_time - gap.gap_time).total_seconds() / 60
            print(f"Fill time: {fill_minutes:.0f} minutes")
        print(f"News driven: {gap.is_news_driven}")
        if gap.correlated_news:
            print(f"News events: {len(gap.correlated_news)}")
    
    # Check current gap
    print("\n=== Current Gap Status ===")
    if analysis.current_gap:
        print(f"Currently in gap: {analysis.current_gap.direction.value}")
        print(f"Gap size: {analysis.current_gap.size_percent:.2%}")
        print(f"Acceptable for entry: {analysis.is_acceptable_for_entry()}")
        
        # Fill probability
        fill_prob = analyzer.get_gap_fill_probability(analysis.current_gap)
        print(f"Fill probability: {fill_prob:.1%}")
    else:
        print("No current gap")
    
    # Unfilled zones
    print(f"\n=== Unfilled Gap Zones ===")
    print(f"Number of zones: {len(analysis.gap_zones)}")
    for i, (low, high) in enumerate(analysis.gap_zones[:3]):
        print(f"Zone {i+1}: ${low:.2f} - ${high:.2f}")
    
    # Test overnight gap calculation
    print("\n=== Overnight Gap Test ===")
    overnight_gap = analyzer.calculate_overnight_gap(584.50, 586.25)
    if overnight_gap:
        print(f"Overnight gap: {overnight_gap.direction.value} {overnight_gap.size_percent:.2%}")