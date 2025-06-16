#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF03_SupportResistance.py
Group: F (Technical Analysis)
Purpose: Dynamic support/resistance levels

Description:
    This module identifies and tracks dynamic support and resistance levels
    using multiple methods including pivot points, volume profile, historical
    price levels, and psychological levels. It provides real-time level
    updates and strength ratings for better trade entry and exit decisions.

Author: Your Name
Date: 2025-06-15
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import Counter
from enum import Enum, auto
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Level detection parameters
MIN_TOUCHES = 3
TOUCH_TOLERANCE = 0.002  # 0.2% tolerance for level touches
CLUSTER_EPSILON = 0.005  # 0.5% for clustering levels
HIGH_VOLUME_PERCENTILE = 80

# Pivot lookback periods
PIVOT_LOOKBACK_DAILY = 20
PIVOT_LOOKBACK_WEEKLY = 5

# Volume profile settings
VOLUME_BINS = 50

# Level strength
ROUND_NUMBER_STRENGTH = 0.5
HALF_POINT_STRENGTH = 0.4
QUARTER_POINT_STRENGTH = 0.3

# ==============================================================================
# ENUMS
# ==============================================================================
class LevelType(Enum):
    """Types of support/resistance levels"""
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"
    PIVOT = "PIVOT"
    HISTORICAL = "HISTORICAL"
    VOLUME = "VOLUME"
    PSYCHOLOGICAL = "PSYCHOLOGICAL"
    DYNAMIC = "DYNAMIC"
    FIBONACCI = "FIBONACCI"
    PREVIOUS_HIGH = "PREVIOUS_HIGH"
    PREVIOUS_LOW = "PREVIOUS_LOW"

class LevelStrength(Enum):
    """Strength categories for levels"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    MAJOR = "major"

class PivotType(Enum):
    """Types of pivot points"""
    STANDARD = "standard"
    FIBONACCI = "fibonacci"
    WOODIE = "woodie"
    CAMARILLA = "camarilla"
    DEMARK = "demark"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Level:
    """Support/Resistance level"""
    price: float
    level_type: LevelType
    strength: float
    touches: int
    first_seen: datetime
    last_tested: datetime
    volume_at_level: float = 0
    held_duration: timedelta = timedelta(0)
    breach_count: int = 0
    notes: str = ""
    
    @property
    def age(self) -> timedelta:
        """Get age of the level"""
        return datetime.now() - self.first_seen
    
    @property
    def strength_category(self) -> LevelStrength:
        """Get strength category"""
        if self.strength >= 0.8:
            return LevelStrength.MAJOR
        elif self.strength >= 0.6:
            return LevelStrength.STRONG
        elif self.strength >= 0.4:
            return LevelStrength.MODERATE
        else:
            return LevelStrength.WEAK

@dataclass
class PivotPoints:
    """Pivot point levels"""
    pivot: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float
    timeframe: str
    calculated_at: datetime = field(default_factory=datetime.now)

@dataclass
class VolumeNode:
    """Volume profile node"""
    price_level: float
    volume: float
    buy_volume: float
    sell_volume: float
    
    @property
    def delta(self) -> float:
        """Get volume delta"""
        return self.buy_volume - self.sell_volume
    
    @property
    def buy_percentage(self) -> float:
        """Get buy volume percentage"""
        return self.buy_volume / self.volume if self.volume > 0 else 0.5

# ==============================================================================
# SUPPORT RESISTANCE ANALYZER CLASS
# ==============================================================================
class SupportResistanceAnalyzer:
    """
    Identifies and tracks dynamic support and resistance levels.
    
    Features:
    - Multiple level detection methods
    - Dynamic strength calculation
    - Level clustering and merging
    - Real-time level updates
    - Historical level tracking
    """
    
    def __init__(self):
        """Initialize support/resistance analyzer"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Level storage
        self.levels: Dict[float, Level] = {}
        self.historical_levels: List[Level] = []
        
        # Volume profile
        self.volume_profile: List[VolumeNode] = []
        
        # Cache
        self._pivot_cache: Dict[str, PivotPoints] = {}
        self._last_update: Optional[datetime] = None
        
        self.logger.info("SupportResistanceAnalyzer initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - LEVEL DETECTION
    # ==========================================================================
    def analyze(self, data: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Comprehensive support/resistance analysis.
        
        Args:
            data: OHLCV DataFrame
            current_price: Current market price
            
        Returns:
            Analysis results dictionary
        """
        try:
            if len(data) < 10:
                return self._empty_analysis()
            
            # Clear old levels
            self._clean_old_levels()
            
            # Detect levels using multiple methods
            pivot_levels = self._calculate_pivot_levels(data)
            historical_levels = self._find_historical_levels(data)
            volume_levels = self._find_volume_levels(data)
            psychological_levels = self._find_psychological_levels(current_price)
            
            # Combine and cluster levels
            all_levels = (pivot_levels + historical_levels + 
                         volume_levels + psychological_levels)
            clustered_levels = self._cluster_levels(all_levels)
            
            # Update level database
            self._update_levels(clustered_levels, data)
            
            # Get nearby levels
            nearby_support = self._get_nearby_levels(current_price, 'support')
            nearby_resistance = self._get_nearby_levels(current_price, 'resistance')
            
            # Calculate key metrics
            nearest_support = nearby_support[0] if nearby_support else None
            nearest_resistance = nearby_resistance[0] if nearby_resistance else None
            
            return {
                'current_price': current_price,
                'support_levels': nearby_support[:5],
                'resistance_levels': nearby_resistance[:5],
                'nearest_support': nearest_support,
                'nearest_resistance': nearest_resistance,
                'support_distance': (current_price - nearest_support.price) / current_price if nearest_support else None,
                'resistance_distance': (nearest_resistance.price - current_price) / current_price if nearest_resistance else None,
                'total_levels': len(self.levels),
                'pivot_points': self._get_current_pivots(),
                'volume_profile': self._get_volume_profile_summary(),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, "Error in support/resistance analysis")
            return self._empty_analysis()
    
    def get_level_at_price(self, price: float, tolerance: float = TOUCH_TOLERANCE) -> Optional[Level]:
        """
        Get level at or near a specific price.
        
        Args:
            price: Target price
            tolerance: Price tolerance
            
        Returns:
            Level object or None
        """
        for level_price, level in self.levels.items():
            if abs(level_price - price) / price <= tolerance:
                return level
        return None
    
    def test_level(self, price: float, high: float, low: float) -> Optional[str]:
        """
        Test if price action interacted with any level.
        
        Args:
            price: Current price
            high: Period high
            low: Period low
            
        Returns:
            'support_held', 'support_broken', 'resistance_held', 'resistance_broken', or None
        """
        # Check support levels
        for level_price, level in self.levels.items():
            if level_price < price:  # Support level
                if low <= level_price <= high:
                    # Level was tested
                    level.touches += 1
                    level.last_tested = datetime.now()
                    
                    if low < level_price:
                        level.breach_count += 1
                        return 'support_broken'
                    else:
                        return 'support_held'
        
        # Check resistance levels
        for level_price, level in self.levels.items():
            if level_price > price:  # Resistance level
                if low <= level_price <= high:
                    # Level was tested
                    level.touches += 1
                    level.last_tested = datetime.now()
                    
                    if high > level_price:
                        level.breach_count += 1
                        return 'resistance_broken'
                    else:
                        return 'resistance_held'
        
        return None
    
    # ==========================================================================
    # PRIVATE METHODS - PIVOT CALCULATIONS
    # ==========================================================================
    def _calculate_pivot_levels(self, data: pd.DataFrame) -> List[Level]:
        """Calculate pivot point levels"""
        levels = []
        
        try:
            # Daily pivots
            daily_pivots = self._calculate_pivots(data, 'D', PivotType.STANDARD)
            if daily_pivots:
                levels.extend(self._pivots_to_levels(daily_pivots, LevelType.PIVOT))
            
            # Weekly pivots (if enough data)
            if len(data) >= PIVOT_LOOKBACK_WEEKLY * 5:  # 5 days per week
                weekly_pivots = self._calculate_pivots(data, 'W', PivotType.STANDARD)
                if weekly_pivots:
                    levels.extend(self._pivots_to_levels(weekly_pivots, LevelType.PIVOT))
            
            # Fibonacci pivots for key levels
            fib_pivots = self._calculate_pivots(data, 'D', PivotType.FIBONACCI)
            if fib_pivots:
                levels.extend(self._pivots_to_levels(fib_pivots, LevelType.PIVOT))
                
        except Exception as e:
            self.logger.error(f"Error calculating pivot levels: {str(e)}")
        
        return levels
    
    def _calculate_pivots(self, data: pd.DataFrame, timeframe: str, 
                         pivot_type: PivotType) -> Optional[PivotPoints]:
        """Calculate specific pivot points"""
        try:
            # Get previous period's HLC
            if timeframe == 'D' and len(data) >= 1:
                period_data = data.iloc[-min(len(data), 390):]  # Last day (390 minutes)
            elif timeframe == 'W' and len(data) >= 5 * 390:
                period_data = data.iloc[-min(len(data), 5 * 390):]  # Last week
            else:
                return None
            
            if len(period_data) == 0:
                return None
            
            high = period_data['high'].max()
            low = period_data['low'].min()
            close = period_data['close'].iloc[-1]
            
            if pivot_type == PivotType.STANDARD:
                pivot = (high + low + close) / 3
                r1 = 2 * pivot - low
                s1 = 2 * pivot - high
                r2 = pivot + (high - low)
                s2 = pivot - (high - low)
                r3 = high + 2 * (pivot - low)
                s3 = low - 2 * (high - pivot)
                
            elif pivot_type == PivotType.FIBONACCI:
                pivot = (high + low + close) / 3
                range_hl = high - low
                r1 = pivot + 0.382 * range_hl
                s1 = pivot - 0.382 * range_hl
                r2 = pivot + 0.618 * range_hl
                s2 = pivot - 0.618 * range_hl
                r3 = pivot + 1.000 * range_hl
                s3 = pivot - 1.000 * range_hl
                
            elif pivot_type == PivotType.WOODIE:
                pivot = (high + low + 2 * close) / 4
                r1 = 2 * pivot - low
                s1 = 2 * pivot - high
                r2 = pivot + (high - low)
                s2 = pivot - (high - low)
                r3 = r1 + (high - low)
                s3 = s1 - (high - low)
                
            else:
                return None
            
            pivots = PivotPoints(
                pivot=pivot,
                r1=r1, r2=r2, r3=r3,
                s1=s1, s2=s2, s3=s3,
                timeframe=timeframe
            )
            
            # Cache the pivots
            self._pivot_cache[f"{timeframe}_{pivot_type.value}"] = pivots
            
            return pivots
            
        except Exception as e:
            self.logger.error(f"Pivot calculation error: {str(e)}")
            return None
    
    def _pivots_to_levels(self, pivots: PivotPoints, level_type: LevelType) -> List[Level]:
        """Convert pivot points to Level objects"""
        levels = []
        now = datetime.now()
        
        # Map pivot levels to strength
        level_map = {
            'pivot': (pivots.pivot, 0.8),
            'r1': (pivots.r1, 0.7),
            's1': (pivots.s1, 0.7),
            'r2': (pivots.r2, 0.6),
            's2': (pivots.s2, 0.6),
            'r3': (pivots.r3, 0.5),
            's3': (pivots.s3, 0.5)
        }
        
        for name, (price, strength) in level_map.items():
            level = Level(
                price=price,
                level_type=level_type,
                strength=strength,
                touches=0,
                first_seen=now,
                last_tested=now,
                notes=f"{pivots.timeframe} {name}"
            )
            levels.append(level)
        
        return levels
    
    # ==========================================================================
    # PRIVATE METHODS - HISTORICAL LEVELS
    # ==========================================================================
    def _find_historical_levels(self, data: pd.DataFrame) -> List[Level]:
        """Find historical support/resistance levels"""
        levels = []
        
        try:
            # Find local highs and lows
            highs = data['high'].values
            lows = data['low'].values
            
            # Detect peaks (potential resistance)
            if len(highs) > 10:
                peak_indices, _ = find_peaks(highs, distance=5, prominence=data['high'].std() * 0.5)
                
                # Create levels from peaks
                for idx in peak_indices:
                    level = Level(
                        price=highs[idx],
                        level_type=LevelType.HISTORICAL,
                        strength=0.6,
                        touches=1,
                        first_seen=data.index[idx],
                        last_tested=data.index[idx],
                        notes="Historical high"
                    )
                    levels.append(level)
            
            # Detect troughs (potential support)
            if len(lows) > 10:
                trough_indices, _ = find_peaks(-lows, distance=5, prominence=data['low'].std() * 0.5)
                
                # Create levels from troughs
                for idx in trough_indices:
                    level = Level(
                        price=lows[idx],
                        level_type=LevelType.HISTORICAL,
                        strength=0.6,
                        touches=1,
                        first_seen=data.index[idx],
                        last_tested=data.index[idx],
                        notes="Historical low"
                    )
                    levels.append(level)
            
            # Find price levels with multiple touches
            all_prices = np.concatenate([highs, lows])
            price_counts = self._count_price_touches(all_prices)
            
            for price, count in price_counts.items():
                if count >= MIN_TOUCHES:
                    level = Level(
                        price=price,
                        level_type=LevelType.HISTORICAL,
                        strength=min(0.5 + count * 0.1, 0.9),
                        touches=count,
                        first_seen=data.index[0],
                        last_tested=data.index[-1],
                        notes=f"Tested {count} times"
                    )
                    levels.append(level)
                    
        except Exception as e:
            self.logger.error(f"Error finding historical levels: {str(e)}")
        
        return levels
    
    def _count_price_touches(self, prices: np.ndarray) -> Dict[float, int]:
        """Count touches at price levels"""
        # Round prices to reduce noise
        rounded_prices = np.round(prices, 2)
        
        # Count occurrences
        price_counts = Counter(rounded_prices)
        
        # Filter by minimum touches
        return {price: count for price, count in price_counts.items() 
                if count >= MIN_TOUCHES}
    
    # ==========================================================================
    # PRIVATE METHODS - VOLUME LEVELS
    # ==========================================================================
    def _find_volume_levels(self, data: pd.DataFrame) -> List[Level]:
        """Find high volume price levels"""
        levels = []
        
        if 'volume' not in data.columns or len(data) < 10:
            return levels
        
        try:
            # Create volume profile
            volume_profile = self._create_volume_profile(data)
            
            if not volume_profile:
                return levels
            
            # Find high volume nodes
            volumes = [node.volume for node in volume_profile]
            if volumes:
                high_volume_threshold = np.percentile(volumes, HIGH_VOLUME_PERCENTILE)
                max_volume = max(volumes)
                
                for node in volume_profile:
                    if node.volume >= high_volume_threshold:
                        # Determine strength based on volume
                        strength = 0.7 + (node.volume / max_volume) * 0.3
                        
                        level = Level(
                            price=node.price_level,
                            level_type=LevelType.VOLUME,
                            strength=min(strength, 1.0),
                            touches=0,
                            first_seen=data.index[0],
                            last_tested=data.index[-1],
                            volume_at_level=node.volume,
                            notes=f"High volume node (delta: {node.delta:,.0f})"
                        )
                        levels.append(level)
                        
        except Exception as e:
            self.logger.error(f"Error finding volume levels: {str(e)}")
        
        return levels
    
    def _create_volume_profile(self, data: pd.DataFrame) -> List[VolumeNode]:
        """Create volume profile from price and volume data"""
        try:
            # Get price range
            price_min = data['low'].min()
            price_max = data['high'].max()
            
            if price_min >= price_max:
                return []
            
            # Create price bins
            bins = np.linspace(price_min, price_max, VOLUME_BINS + 1)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            
            # Initialize volume nodes
            nodes = []
            for center in bin_centers:
                nodes.append(VolumeNode(
                    price_level=center,
                    volume=0,
                    buy_volume=0,
                    sell_volume=0
                ))
            
            # Distribute volume to bins
            for idx, row in data.iterrows():
                # Find which bins this candle touches
                low_bin = np.searchsorted(bins, row['low'], side='left')
                high_bin = np.searchsorted(bins, row['high'], side='right')
                
                # Distribute volume evenly across touched bins
                if high_bin > low_bin:
                    volume_per_bin = row['volume'] / (high_bin - low_bin)
                    
                    for i in range(max(0, low_bin-1), min(len(nodes), high_bin)):
                        nodes[i].volume += volume_per_bin
                        
                        # Estimate buy/sell volume
                        if row['close'] > row['open']:
                            nodes[i].buy_volume += volume_per_bin * 0.6
                            nodes[i].sell_volume += volume_per_bin * 0.4
                        else:
                            nodes[i].buy_volume += volume_per_bin * 0.4
                            nodes[i].sell_volume += volume_per_bin * 0.6
            
            # Store and return profile
            self.volume_profile = nodes
            return nodes
            
        except Exception as e:
            self.logger.error(f"Error creating volume profile: {str(e)}")
            return []
    
    # ==========================================================================
    # PRIVATE METHODS - PSYCHOLOGICAL LEVELS
    # ==========================================================================
    def _find_psychological_levels(self, current_price: float, range_multiplier: float = 0.1) -> List[Level]:
        """Find psychological price levels"""
        levels = []
        
        try:
            # Determine price range to check
            price_range = current_price * range_multiplier
            min_price = current_price - price_range
            max_price = current_price + price_range
            
            # Round numbers (multiples of 10)
            round_base = 10
            start = int(min_price / round_base) * round_base
            
            price = start
            while price <= max_price:
                if min_price <= price <= max_price:
                    level = Level(
                        price=price,
                        level_type=LevelType.PSYCHOLOGICAL,
                        strength=ROUND_NUMBER_STRENGTH,
                        touches=0,
                        first_seen=datetime.now(),
                        last_tested=datetime.now(),
                        notes=f"Round number {price}"
                    )
                    levels.append(level)
                
                # Add half points
                half_price = price + round_base / 2
                if min_price <= half_price <= max_price:
                    level = Level(
                        price=half_price,
                        level_type=LevelType.PSYCHOLOGICAL,
                        strength=HALF_POINT_STRENGTH,
                        touches=0,
                        first_seen=datetime.now(),
                        last_tested=datetime.now(),
                        notes=f"Half point {half_price}"
                    )
                    levels.append(level)
                
                price += round_base
            
            # For SPY, also add quarter points (x.25, x.75)
            quarter_base = 0.25
            start = int(min_price / quarter_base) * quarter_base
            
            price = start
            while price <= max_price:
                if min_price <= price <= max_price and price % 0.25 == 0 and price % 0.5 != 0:
                    level = Level(
                        price=price,
                        level_type=LevelType.PSYCHOLOGICAL,
                        strength=QUARTER_POINT_STRENGTH,
                        touches=0,
                        first_seen=datetime.now(),
                        last_tested=datetime.now(),
                        notes=f"Quarter point {price}"
                    )
                    levels.append(level)
                
                price += quarter_base
                
        except Exception as e:
            self.logger.error(f"Error finding psychological levels: {str(e)}")
        
        return levels
    
    # ==========================================================================
    # PRIVATE METHODS - LEVEL CLUSTERING
    # ==========================================================================
    def _cluster_levels(self, levels: List[Level]) -> List[Level]:
        """Cluster nearby levels together"""
        if not levels:
            return []
        
        # Sort levels by price
        sorted_levels = sorted(levels, key=lambda x: x.price)
        
        # Group nearby levels
        clustered = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            # Check if level is close to cluster
            cluster_center = np.mean([l.price for l in current_cluster])
            
            if abs(level.price - cluster_center) / cluster_center <= CLUSTER_EPSILON:
                current_cluster.append(level)
            else:
                # Process current cluster
                if current_cluster:
                    merged_level = self._merge_levels(current_cluster)
                    clustered.append(merged_level)
                
                # Start new cluster
                current_cluster = [level]
        
        # Process final cluster
        if current_cluster:
            merged_level = self._merge_levels(current_cluster)
            clustered.append(merged_level)
        
        return clustered
    
    def _merge_levels(self, levels: List[Level]) -> Level:
        """Merge multiple levels into one"""
        # Use weighted average for price
        total_weight = sum(l.strength for l in levels)
        if total_weight > 0:
            price = sum(l.price * l.strength for l in levels) / total_weight
        else:
            price = np.mean([l.price for l in levels])
        
        # Combine attributes
        merged = Level(
            price=price,
            level_type=levels[0].level_type,  # Use primary type
            strength=min(1.0, np.mean([l.strength for l in levels]) * 1.1),  # Boost for confluence
            touches=sum(l.touches for l in levels),
            first_seen=min(l.first_seen for l in levels),
            last_tested=max(l.last_tested for l in levels),
            volume_at_level=sum(l.volume_at_level for l in levels),
            notes=f"Merged from {len(levels)} levels"
        )
        
        return merged
    
    # ==========================================================================
    # PRIVATE METHODS - LEVEL MANAGEMENT
    # ==========================================================================
    def _update_levels(self, new_levels: List[Level], data: pd.DataFrame) -> None:
        """Update level database with new levels"""
        for level in new_levels:
            # Check if level already exists
            existing = self.get_level_at_price(level.price)
            
            if existing:
                # Update existing level
                existing.touches += level.touches
                existing.last_tested = max(existing.last_tested, level.last_tested)
                existing.strength = min(1.0, existing.strength * 1.05)  # Slight strength boost
                existing.volume_at_level += level.volume_at_level
            else:
                # Add new level
                self.levels[level.price] = level
        
        # Update level strengths based on recent price action
        self._update_level_strengths(data)
    
    def _update_level_strengths(self, data: pd.DataFrame) -> None:
        """Update strength of all levels based on recent price action"""
        if len(data) == 0:
            return
            
        current_price = data['close'].iloc[-1]
        current_time = datetime.now()
        
        for level in self.levels.values():
            # Decay strength over time
            age_hours = (current_time - level.last_tested).total_seconds() / 3600
            time_decay = 0.995 ** (age_hours / 24)  # 0.5% decay per day
            
            # Boost strength for nearby levels
            distance = abs(level.price - current_price) / current_price
            proximity_boost = 1.0 + max(0, 0.1 - distance) * 2  # Up to 20% boost
            
            # Update strength
            level.strength = min(1.0, level.strength * time_decay * proximity_boost)
    
    def _clean_old_levels(self, max_age_days: int = 90) -> None:
        """Remove old or weak levels"""
        current_time = datetime.now()
        levels_to_remove = []
        
        for price, level in self.levels.items():
            # Remove old untested levels
            if (current_time - level.last_tested).days > max_age_days:
                levels_to_remove.append(price)
            # Remove very weak levels
            elif level.strength < 0.1:
                levels_to_remove.append(price)
        
        for price in levels_to_remove:
            # Archive before removing
            self.historical_levels.append(self.levels[price])
            del self.levels[price]
    
    # ==========================================================================
    # PRIVATE METHODS - LEVEL QUERIES
    # ==========================================================================
    def _get_nearby_levels(self, price: float, direction: str, max_levels: int = 10) -> List[Level]:
        """Get nearby support or resistance levels"""
        if direction == 'support':
            # Get levels below current price
            nearby = [(p, l) for p, l in self.levels.items() if p < price]
            nearby.sort(key=lambda x: x[0], reverse=True)  # Closest first
        else:
            # Get levels above current price
            nearby = [(p, l) for p, l in self.levels.items() if p > price]
            nearby.sort(key=lambda x: x[0])  # Closest first
        
        return [level for _, level in nearby[:max_levels]]
    
    def _get_current_pivots(self) -> Dict[str, PivotPoints]:
        """Get current pivot points"""
        return {
            timeframe: pivots 
            for timeframe, pivots in self._pivot_cache.items()
            if (datetime.now() - pivots.calculated_at).total_seconds() < 86400  # 24 hours
        }
    
    def _get_volume_profile_summary(self) -> Dict[str, Any]:
        """Get volume profile summary"""
        if not self.volume_profile:
            return {}
        
        total_volume = sum(node.volume for node in self.volume_profile)
        
        if total_volume == 0:
            return {}
            
        poc_node = max(self.volume_profile, key=lambda x: x.volume)
        
        return {
            'poc': poc_node.price_level,  # Point of Control
            'total_volume': total_volume,
            'buy_volume': sum(node.buy_volume for node in self.volume_profile),
            'sell_volume': sum(node.sell_volume for node in self.volume_profile),
            'nodes': len(self.volume_profile)
        }
    
    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis result"""
        return {
            'current_price': 0,
            'support_levels': [],
            'resistance_levels': [],
            'nearest_support': None,
            'nearest_resistance': None,
            'support_distance': None,
            'resistance_distance': None,
            'total_levels': 0,
            'pivot_points': {},
            'volume_profile': {},
            'timestamp': datetime.now()
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def calculate_fibonacci_levels(high: float, low: float, trend: str = 'up') -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels.
    
    Args:
        high: Swing high
        low: Swing low
        trend: 'up' or 'down'
        
    Returns:
        Dictionary of Fibonacci levels
    """
    range_size = high - low
    
    if trend == 'up':
        # Retracement levels from high
        levels = {
            '0.0%': high,
            '23.6%': high - range_size * 0.236,
            '38.2%': high - range_size * 0.382,
            '50.0%': high - range_size * 0.500,
            '61.8%': high - range_size * 0.618,
            '78.6%': high - range_size * 0.786,
            '100.0%': low,
            '127.2%': low - range_size * 0.272,  # Extension
            '161.8%': low - range_size * 0.618   # Extension
        }
    else:
        # Retracement levels from low
        levels = {
            '0.0%': low,
            '23.6%': low + range_size * 0.236,
            '38.2%': low + range_size * 0.382,
            '50.0%': low + range_size * 0.500,
            '61.8%': low + range_size * 0.618,
            '78.6%': low + range_size * 0.786,
            '100.0%': high,
            '127.2%': high + range_size * 0.272,  # Extension
            '161.8%': high + range_size * 0.618   # Extension
        }
    
    return levels

def find_order_blocks(data: pd.DataFrame, lookback: int = 50) -> List[Dict[str, Any]]:
    """
    Find order blocks (institutional supply/demand zones).
    
    Args:
        data: OHLCV DataFrame
        lookback: Lookback period
        
    Returns:
        List of order block dictionaries
    """
    order_blocks = []
    
    if len(data) < lookback:
        return order_blocks
    
    recent_data = data.tail(lookback)
    
    for i in range(2, len(recent_data) - 2):
        # Bullish order block: Strong move up after consolidation
        if (recent_data.iloc[i]['close'] > recent_data.iloc[i]['open'] and  # Bullish candle
            recent_data.iloc[i]['volume'] > recent_data.iloc[i-1]['volume'] * 1.5 and  # Volume spike
            recent_data.iloc[i+1]['close'] > recent_data.iloc[i]['high']):  # Continuation
            
            order_blocks.append({
                'type': 'demand',
                'top': recent_data.iloc[i]['high'],
                'bottom': recent_data.iloc[i]['low'],
                'timestamp': recent_data.index[i],
                'strength': recent_data.iloc[i]['volume'] / recent_data['volume'].mean()
            })
        
        # Bearish order block: Strong move down after consolidation
        elif (recent_data.iloc[i]['close'] < recent_data.iloc[i]['open'] and  # Bearish candle
              recent_data.iloc[i]['volume'] > recent_data.iloc[i-1]['volume'] * 1.5 and  # Volume spike
              recent_data.iloc[i+1]['close'] < recent_data.iloc[i]['low']):  # Continuation
            
            order_blocks.append({
                'type': 'supply',
                'top': recent_data.iloc[i]['high'],
                'bottom': recent_data.iloc[i]['low'],
                'timestamp': recent_data.index[i],
                'strength': recent_data.iloc[i]['volume'] / recent_data['volume'].mean()
            })
    
    return order_blocks

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'SupportResistanceAnalyzer',
    'Level',
    'LevelType',
    'LevelStrength',
    'PivotType',
    'PivotPoints',
    'VolumeNode',
    'calculate_fibonacci_levels',
    'find_order_blocks'
]

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test support/resistance analyzer
    analyzer = SupportResistanceAnalyzer()
    
    # Create sample data
    dates = pd.date_range(start='2025-01-01', periods=100, freq='5min')
    np.random.seed(42)
    
    # Generate data with clear levels
    base_price = 450
    prices = []
    
    for i in range(100):
        # Create price that bounces between levels
        if i % 20 < 10:
            price = base_price + np.random.normal(0, 0.2)
        else:
            price = base_price + 2 + np.random.normal(0, 0.2)
        
        prices.append(price)
    
    data = pd.DataFrame({
        'open': prices[:-1] + [prices[-1]],
        'high': [p + abs(np.random.normal(0, 0.1)) for p in prices],
        'low': [p - abs(np.random.normal(0, 0.1)) for p in prices],
        'close': prices,
        'volume': np.random.randint(1000000, 2000000, 100)
    }, index=dates)
    
    # Analyze
    current_price = prices[-1]
    analysis = analyzer.analyze(data, current_price)
    
    print("Support/Resistance Analysis")
    print("=" * 50)
    print(f"Current Price: {current_price:.2f}")
    print(f"Total Levels: {analysis['total_levels']}")
    
    print("\nNearby Support Levels:")
    for level in analysis['support_levels'][:3]:
        print(f"  {level.price:.2f} - {level.strength_category.value} "
              f"(touches: {level.touches}, strength: {level.strength:.2%})")
    
    print("\nNearby Resistance Levels:")
    for level in analysis['resistance_levels'][:3]:
        print(f"  {level.price:.2f} - {level.strength_category.value} "
              f"(touches: {level.touches}, strength: {level.strength:.2%})")
    
    if analysis['nearest_support']:
        print(f"\nNearest Support: {analysis['nearest_support'].price:.2f} "
              f"({analysis['support_distance']:.2%} away)")
    
    if analysis['nearest_resistance']:
        print(f"Nearest Resistance: {analysis['nearest_resistance'].price:.2f} "
              f"({analysis['resistance_distance']:.2%} away)")
    
    # Test Fibonacci levels
    fib_levels = calculate_fibonacci_levels(high=455, low=445, trend='up')
    print("\nFibonacci Levels:")
    for label, price in fib_levels.items():
        print(f"  {label}: {price:.2f}")
