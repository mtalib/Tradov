#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF07_GapAnalyzer.py
Group: F (Analysis)
Purpose: Overnight gap analysis for entry filters

Description:
    This module analyzes overnight gaps in SPY price to support entry filtering
    based on research findings. Large overnight gaps (>0.3%) are associated with
    lower success rates and should be avoided for options strategies.

Author: Mohamed Talib
Date: 2025-06-06
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import numpy as np
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC02_HistoricalData import HistoricalDataManager
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Gap thresholds (from research)
MAX_ACCEPTABLE_GAP = 0.003      # 0.3% max overnight gap for entry
LARGE_GAP_THRESHOLD = 0.005     # 0.5% considered large gap
EXTREME_GAP_THRESHOLD = 0.01    # 1.0% extreme gap

# Time definitions
MARKET_CLOSE_TIME = datetime.time(16, 0)    # 4:00 PM ET
MARKET_OPEN_TIME = datetime.time(9, 30)     # 9:30 AM ET
PRE_MARKET_START = datetime.time(4, 0)      # 4:00 AM ET

# Historical analysis
GAP_HISTORY_DAYS = 30          # Days of gap history to maintain
GAP_FADE_WINDOW = 60           # Minutes to check for gap fade

# ==============================================================================
# ENUMS
# ==============================================================================
class GapType(Enum):
    """Gap classification types"""
    TINY = "tiny"               # < 0.1%
    SMALL = "small"             # 0.1% - 0.3%
    MEDIUM = "medium"           # 0.3% - 0.5%
    LARGE = "large"             # 0.5% - 1.0%
    EXTREME = "extreme"         # > 1.0%

class GapDirection(Enum):
    """Gap direction"""
    UP = "up"
    DOWN = "down"
    FLAT = "flat"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GapData:
    """Overnight gap data"""
    date: datetime.date
    previous_close: float
    open_price: float
    gap_size: float             # Absolute gap
    gap_percentage: float       # Percentage gap
    gap_type: GapType
    gap_direction: GapDirection
    pre_market_high: float
    pre_market_low: float
    gap_filled: bool = False
    fill_time: Optional[datetime.time] = None
    intraday_high: float = 0.0
    intraday_low: float = 0.0
    
    def is_acceptable_for_entry(self) -> bool:
        """Check if gap is acceptable for strategy entry"""
        return abs(self.gap_percentage) <= MAX_ACCEPTABLE_GAP

@dataclass
class GapStatistics:
    """Gap statistics over time"""
    avg_gap_size: float
    avg_positive_gap: float
    avg_negative_gap: float
    gap_fill_rate: float
    avg_fill_time_minutes: float
    large_gap_frequency: float
    extreme_gap_days: List[datetime.date]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/display"""
        return {
            'avg_gap_size': f"{self.avg_gap_size:.2%}",
            'avg_positive_gap': f"{self.avg_positive_gap:.2%}",
            'avg_negative_gap': f"{self.avg_negative_gap:.2%}",
            'gap_fill_rate': f"{self.gap_fill_rate:.1%}",
            'avg_fill_time_minutes': self.avg_fill_time_minutes,
            'large_gap_frequency': f"{self.large_gap_frequency:.1%}",
            'extreme_gap_count': len(self.extreme_gap_days)
        }

# ==============================================================================
# GAP ANALYZER CLASS
# ==============================================================================
class GapAnalyzer:
    """
    Analyzes overnight gaps and their impact on trading.
    
    Based on research showing that overnight gaps > 0.3% should be
    avoided for options strategies due to lower success rates.
    """
    
    def __init__(self, historical_data_manager: Optional[HistoricalDataManager] = None):
        """Initialize gap analyzer"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.historical_data = historical_data_manager
        self.calendar = TradingCalendar()
        
        # Gap history
        self.gap_history: deque = deque(maxlen=GAP_HISTORY_DAYS)
        self.today_gap: Optional[GapData] = None
        
        # Real-time tracking
        self.previous_close = None
        self.today_open = None
        self.pre_market_prices = []
        
        # Statistics cache
        self._stats_cache: Optional[GapStatistics] = None
        self._stats_cache_date: Optional[datetime.date] = None
        
        # Load historical gaps if data manager available
        if self.historical_data:
            self._load_historical_gaps()
        
        self.logger.info("GapAnalyzer initialized")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def calculate_overnight_gap(self, symbol: str = "SPY") -> float:
        """
        Calculate current overnight gap percentage.
        
        Args:
            symbol: Symbol to analyze (default SPY)
            
        Returns:
            Gap percentage (positive for gap up, negative for gap down)
        """
        if self.today_gap and self.today_gap.date == datetime.date.today():
            return self.today_gap.gap_percentage
        
        # Get previous close and today's open
        prev_close = self._get_previous_close(symbol)
        today_open = self._get_today_open(symbol)
        
        if prev_close and today_open:
            gap_pct = (today_open - prev_close) / prev_close
            
            # Create gap data
            self.today_gap = self._create_gap_data(prev_close, today_open)
            
            # Add to history
            self.gap_history.append(self.today_gap)
            
            self.logger.info(f"Overnight gap: {gap_pct:.2%} ({self.today_gap.gap_type.value})")
            
            return gap_pct
        
        return 0.0
    
    def is_gap_acceptable(self, symbol: str = "SPY") -> bool:
        """
        Check if current gap is acceptable for trading.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if gap is within acceptable range
        """
        gap = self.calculate_overnight_gap(symbol)
        acceptable = abs(gap) <= MAX_ACCEPTABLE_GAP
        
        if not acceptable:
            self.logger.warning(f"Gap {gap:.2%} exceeds acceptable threshold {MAX_ACCEPTABLE_GAP:.1%}")
        
        return acceptable
    
    def get_gap_statistics(self, days: int = GAP_HISTORY_DAYS) -> GapStatistics:
        """
        Get gap statistics over specified period.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            GapStatistics object
        """
        # Check cache
        if (self._stats_cache and 
            self._stats_cache_date == datetime.date.today()):
            return self._stats_cache
        
        # Calculate statistics
        if not self.gap_history:
            return self._empty_statistics()
        
        # Filter to requested days
        cutoff_date = datetime.date.today() - datetime.timedelta(days=days)
        recent_gaps = [g for g in self.gap_history if g.date >= cutoff_date]
        
        if not recent_gaps:
            return self._empty_statistics()
        
        # Calculate metrics
        gap_sizes = [g.gap_percentage for g in recent_gaps]
        positive_gaps = [g.gap_percentage for g in recent_gaps if g.gap_direction == GapDirection.UP]
        negative_gaps = [g.gap_percentage for g in recent_gaps if g.gap_direction == GapDirection.DOWN]
        
        # Gap fill analysis
        filled_gaps = [g for g in recent_gaps if g.gap_filled]
        fill_times = []
        for gap in filled_gaps:
            if gap.fill_time:
                # Calculate minutes from open to fill
                open_time = datetime.datetime.combine(gap.date, MARKET_OPEN_TIME)
                fill_datetime = datetime.datetime.combine(gap.date, gap.fill_time)
                minutes = (fill_datetime - open_time).seconds / 60
                fill_times.append(minutes)
        
        # Large gap frequency
        large_gaps = [g for g in recent_gaps if g.gap_type in [GapType.LARGE, GapType.EXTREME]]
        extreme_gaps = [g for g in recent_gaps if g.gap_type == GapType.EXTREME]
        
        stats = GapStatistics(
            avg_gap_size=np.mean(np.abs(gap_sizes)) if gap_sizes else 0,
            avg_positive_gap=np.mean(positive_gaps) if positive_gaps else 0,
            avg_negative_gap=np.mean(negative_gaps) if negative_gaps else 0,
            gap_fill_rate=len(filled_gaps) / len(recent_gaps) if recent_gaps else 0,
            avg_fill_time_minutes=np.mean(fill_times) if fill_times else 0,
            large_gap_frequency=len(large_gaps) / len(recent_gaps) if recent_gaps else 0,
            extreme_gap_days=[g.date for g in extreme_gaps]
        )
        
        # Cache results
        self._stats_cache = stats
        self._stats_cache_date = datetime.date.today()
        
        return stats
    
    def check_gap_fade(self, current_price: float) -> bool:
        """
        Check if current gap is fading (filling).
        
        Args:
            current_price: Current market price
            
        Returns:
            True if gap is fading
        """
        if not self.today_gap:
            return False
        
        if self.today_gap.gap_direction == GapDirection.UP:
            # Gap up is fading if price moves down toward previous close
            return current_price < self.today_gap.open_price
        elif self.today_gap.gap_direction == GapDirection.DOWN:
            # Gap down is fading if price moves up toward previous close
            return current_price > self.today_gap.open_price
        
        return False
    
    def update_intraday_data(self, high: float, low: float, last: float):
        """
        Update intraday price data for gap analysis.
        
        Args:
            high: Intraday high
            low: Intraday low
            last: Last price
        """
        if not self.today_gap:
            return
        
        # Update intraday extremes
        self.today_gap.intraday_high = max(self.today_gap.intraday_high, high)
        self.today_gap.intraday_low = min(self.today_gap.intraday_low, low)
        
        # Check if gap filled
        if not self.today_gap.gap_filled:
            if self.today_gap.gap_direction == GapDirection.UP:
                # Gap up fills if low reaches previous close
                if low <= self.today_gap.previous_close:
                    self.today_gap.gap_filled = True
                    self.today_gap.fill_time = datetime.datetime.now().time()
                    self.logger.info("Gap up filled")
            
            elif self.today_gap.gap_direction == GapDirection.DOWN:
                # Gap down fills if high reaches previous close
                if high >= self.today_gap.previous_close:
                    self.today_gap.gap_filled = True
                    self.today_gap.fill_time = datetime.datetime.now().time()
                    self.logger.info("Gap down filled")
    
    def get_pre_market_gap(self, symbol: str = "SPY") -> float:
        """
        Get pre-market gap indication.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            Pre-market gap percentage
        """
        # This would connect to pre-market data feed
        # For now, return 0 as placeholder
        return 0.0
    
    def get_gap_trading_bias(self) -> str:
        """
        Get trading bias based on gap analysis.
        
        Returns:
            'bullish', 'bearish', or 'neutral'
        """
        if not self.today_gap:
            return 'neutral'
        
        # Large gaps often fade
        if self.today_gap.gap_type in [GapType.LARGE, GapType.EXTREME]:
            if self.today_gap.gap_direction == GapDirection.UP:
                return 'bearish'  # Expect fade
            elif self.today_gap.gap_direction == GapDirection.DOWN:
                return 'bullish'  # Expect bounce
        
        # Small gaps often continue
        elif self.today_gap.gap_type in [GapType.TINY, GapType.SMALL]:
            if self.today_gap.gap_direction == GapDirection.UP:
                return 'bullish'
            elif self.today_gap.gap_direction == GapDirection.DOWN:
                return 'bearish'
        
        return 'neutral'
    
    # ==========================================================================
    # HISTORICAL ANALYSIS
    # ==========================================================================
    def analyze_gap_patterns(self, lookback_days: int = 90) -> Dict[str, Any]:
        """
        Analyze historical gap patterns.
        
        Args:
            lookback_days: Days to analyze
            
        Returns:
            Dictionary with pattern analysis
        """
        patterns = {
            'gap_and_go': 0,      # Gap continues in same direction
            'gap_and_fade': 0,    # Gap reverses
            'inside_days': 0,     # Stay within gap range
            'trend_days': 0,      # Break beyond gap
        }
        
        # Analyze each gap
        for gap in self.gap_history:
            if gap.intraday_high == 0 or gap.intraday_low == 0:
                continue
            
            # Determine pattern
            if gap.gap_direction == GapDirection.UP:
                if gap.intraday_high > gap.open_price * 1.002:  # Continued up
                    patterns['gap_and_go'] += 1
                elif gap.gap_filled:
                    patterns['gap_and_fade'] += 1
                else:
                    patterns['inside_days'] += 1
            
            elif gap.gap_direction == GapDirection.DOWN:
                if gap.intraday_low < gap.open_price * 0.998:  # Continued down
                    patterns['gap_and_go'] += 1
                elif gap.gap_filled:
                    patterns['gap_and_fade'] += 1
                else:
                    patterns['inside_days'] += 1
        
        # Add percentages
        total = sum(patterns.values())
        if total > 0:
            pattern_percentages = {
                f"{k}_pct": v / total for k, v in patterns.items()
            }
            patterns.update(pattern_percentages)
        
        return patterns
    
    def get_gap_seasonality(self) -> Dict[str, float]:
        """
        Analyze gap patterns by day of week.
        
        Returns:
            Average gap by day of week
        """
        day_gaps = {i: [] for i in range(5)}  # Monday = 0
        
        for gap in self.gap_history:
            weekday = gap.date.weekday()
            if weekday < 5:  # Weekday only
                day_gaps[weekday].append(abs(gap.gap_percentage))
        
        # Calculate averages
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        seasonality = {}
        
        for day, gaps in day_gaps.items():
            if gaps:
                seasonality[day_names[day]] = np.mean(gaps)
            else:
                seasonality[day_names[day]] = 0.0
        
        return seasonality
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _get_previous_close(self, symbol: str) -> Optional[float]:
        """Get previous trading day's close"""
        if self.previous_close:
            return self.previous_close
        
        # Get from historical data if available
        if self.historical_data:
            prev_date = self.calendar.get_previous_trading_day()
            # Implementation would fetch actual close
            return 450.0  # Placeholder
        
        return None
    
    def _get_today_open(self, symbol: str) -> Optional[float]:
        """Get today's opening price"""
        if self.today_open:
            return self.today_open
        
        # Get from market data
        # Implementation would fetch actual open
        return 450.5  # Placeholder
    
    def _create_gap_data(self, prev_close: float, open_price: float) -> GapData:
        """Create GapData object from prices"""
        gap_size = open_price - prev_close
        gap_pct = gap_size / prev_close
        
        # Classify gap
        abs_gap = abs(gap_pct)
        if abs_gap < 0.001:
            gap_type = GapType.TINY
        elif abs_gap < MAX_ACCEPTABLE_GAP:
            gap_type = GapType.SMALL
        elif abs_gap < LARGE_GAP_THRESHOLD:
            gap_type = GapType.MEDIUM
        elif abs_gap < EXTREME_GAP_THRESHOLD:
            gap_type = GapType.LARGE
        else:
            gap_type = GapType.EXTREME
        
        # Direction
        if gap_size > 0.0001:
            direction = GapDirection.UP
        elif gap_size < -0.0001:
            direction = GapDirection.DOWN
        else:
            direction = GapDirection.FLAT
        
        return GapData(
            date=datetime.date.today(),
            previous_close=prev_close,
            open_price=open_price,
            gap_size=gap_size,
            gap_percentage=gap_pct,
            gap_type=gap_type,
            gap_direction=direction,
            pre_market_high=open_price,
            pre_market_low=open_price
        )
    
    def _load_historical_gaps(self):
        """Load historical gap data"""
        # Would load from database or calculate from historical data
        # For now, generate some sample data
        for i in range(GAP_HISTORY_DAYS):
            date = datetime.date.today() - datetime.timedelta(days=i+1)
            if self.calendar.is_trading_day(date):
                # Generate random gap data for testing
                prev_close = 450 + np.random.randn() * 2
                gap_pct = np.random.randn() * 0.003  # Average 0.3% std dev
                open_price = prev_close * (1 + gap_pct)
                
                gap_data = self._create_gap_data(prev_close, open_price)
                gap_data.date = date
                
                # Simulate some gap fills
                if abs(gap_pct) < 0.003 and np.random.random() > 0.3:
                    gap_data.gap_filled = True
                    gap_data.fill_time = datetime.time(10, 30)
                
                self.gap_history.appendleft(gap_data)
    
    def _empty_statistics(self) -> GapStatistics:
        """Return empty statistics object"""
        return GapStatistics(
            avg_gap_size=0.0,
            avg_positive_gap=0.0,
            avg_negative_gap=0.0,
            gap_fill_rate=0.0,
            avg_fill_time_minutes=0.0,
            large_gap_frequency=0.0,
            extreme_gap_days=[]
        )
    
    # ==========================================================================
    # REPORTING
    # ==========================================================================
    def generate_gap_report(self) -> str:
        """Generate gap analysis report"""
        stats = self.get_gap_statistics()
        patterns = self.analyze_gap_patterns()
        seasonality = self.get_gap_seasonality()
        
        report = f"""
Gap Analysis Report
==================

Current Session:
- Date: {datetime.date.today()}
- Gap: {self.calculate_overnight_gap():.2%}
- Type: {self.today_gap.gap_type.value if self.today_gap else 'N/A'}
- Acceptable for Entry: {'Yes' if self.is_gap_acceptable() else 'No'}

{GAP_HISTORY_DAYS}-Day Statistics:
- Average Gap Size: {stats.avg_gap_size:.2%}
- Average Positive Gap: {stats.avg_positive_gap:.2%}
- Average Negative Gap: {stats.avg_negative_gap:.2%}
- Gap Fill Rate: {stats.gap_fill_rate:.1%}
- Average Fill Time: {stats.avg_fill_time_minutes:.0f} minutes
- Large Gap Frequency: {stats.large_gap_frequency:.1%}

Gap Patterns:
- Gap and Go: {patterns.get('gap_and_go_pct', 0):.1%}
- Gap and Fade: {patterns.get('gap_and_fade_pct', 0):.1%}
- Inside Days: {patterns.get('inside_days_pct', 0):.1%}

Day of Week Analysis:
"""
        for day, avg_gap in seasonality.items():
            report += f"- {day}: {avg_gap:.2%}\n"
        
        return report

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test gap analyzer
    analyzer = GapAnalyzer()
    
    # Calculate current gap
    gap = analyzer.calculate_overnight_gap()
    print(f"Current overnight gap: {gap:.2%}")
    print(f"Acceptable for entry: {analyzer.is_gap_acceptable()}")
    
    # Get statistics
    stats = analyzer.get_gap_statistics()
    print(f"\nGap Statistics:")
    for key, value in stats.to_dict().items():
        print(f"  {key}: {value}")
    
    # Analyze patterns
    patterns = analyzer.analyze_gap_patterns()
    print(f"\nGap Patterns:")
    for pattern, value in patterns.items():
        if '_pct' in pattern:
            print(f"  {pattern}: {value:.1%}")
    
    # Day of week analysis
    seasonality = analyzer.get_gap_seasonality()
    print(f"\nGap by Day of Week:")
    for day, avg in seasonality.items():
        print(f"  {day}: {avg:.2%}")
    
    # Generate report
    print("\n" + analyzer.generate_gap_report())
