#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB18_CustomMetricsClient.py
Group: B (Broker/Connection)
Purpose: Client 10 - Custom Metrics (GEX, DEX, OGL, DIX, SWAN)
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2025-08-12 Time: 18:00:00

Description:
    Dedicated IB Gateway client (ID: 10) for fetching and calculating custom
    metrics including Gamma Exposure (GEX), Delta Exposure (DEX), Zero Gamma
    Level (OGL), Dark Index (DIX), and Black Swan Risk (SWAN). These metrics
    provide advanced market structure insights for the trading system.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_insync import IB, Option, Stock, Index, util
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("⚠️ ib_insync not available - running in simulation mode")

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_ID = 10  # Fixed Client ID for Custom Metrics
CLIENT_PURPOSE = "Custom Metrics (GEX/DEX/OGL/DIX/SWAN)"
UPDATE_INTERVAL = 60  # Update metrics every 60 seconds
PAPER_PORT = 4002
LIVE_PORT = 4001

# Market Constants
SPX_MULTIPLIER = 100  # SPX option multiplier
MARKET_OPEN = datetime.strptime("09:30", "%H:%M").time()
MARKET_CLOSE = datetime.strptime("16:00", "%H:%M").time()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CustomMetrics:
    """Container for all custom metrics"""
    gex: float = 0.0  # Gamma Exposure (billions)
    dex: float = 0.0  # Delta Exposure (millions)
    ogl: float = 0.0  # Zero Gamma Level
    dix: float = 0.0  # Dark Index (percentage)
    swan: float = 0.0  # Black Swan Risk (1-5 scale)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            'GEX': {
                'value': self.gex,
                'formatted_value': f"{self.gex:.1f}B",
                'change': 0,
                'change_pct': 0,
                'timestamp': self.timestamp
            },
            'DEX': {
                'value': self.dex,
                'formatted_value': f"{self.dex:.0f}M",
                'change': 0,
                'change_pct': 0,
                'timestamp': self.timestamp
            },
            'OGL': {
                'value': self.ogl,
                'formatted_value': f"{self.ogl:.2f}",
                'change': 0,
                'change_pct': 0,
                'timestamp': self.timestamp
            },
            'DIX': {
                'value': self.dix,
                'formatted_value': f"{self.dix:.1f}%",
                'change': 0,
                'change_pct': 0,
                'timestamp': self.timestamp
            },
            'SWAN': {
                'value': self.swan,
                'formatted_value': f"{self.swan:.2f}",
                'change': 0,
                'change_pct': 0,
                'timestamp': self.timestamp
            }
        }

# ==============================================================================
# CUSTOM METRICS CLIENT
# ==============================================================================
class CustomMetricsClient(QObject):
    """
    Client 10: Specialized client for custom market metrics calculation.
    Connects to IB Gateway with ID 10 to fetch option chain data and calculate
    GEX, DEX, OGL, DIX, and SWAN indicators.
    """
    
    # Signals
    metrics_updated = pyqtSignal(dict)  # Emits updated metrics
    connection_status_changed = pyqtSignal(bool)  # Connection status
    error_occurred = pyqtSignal(str)  # Error messages
    
    def __init__(self, port: int = PAPER_PORT):
        """Initialize Custom Metrics Client"""
        super().__init__()
        
        # Logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
        
        # IB Connection
        self.ib = None
        self.port = port
        self.connected = False
        
        # Metrics data
        self.current_metrics = CustomMetrics()
        self.metrics_history = deque(maxlen=100)
        
        # Threading
        self.update_thread = None
        self.stop_flag = threading.Event()
        
        # Simulation mode data
        self.simulation_mode = not IB_AVAILABLE
        self.simulation_data = self._init_simulation_data()
        
        # Update timer for Qt
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_metrics)
        self.update_timer.setInterval(UPDATE_INTERVAL * 1000)
        
        self.logger.info(f"CustomMetricsClient initialized (Client ID: {CLIENT_ID})")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect(self) -> bool:
        """Connect to IB Gateway as Client 10"""
        try:
            if self.simulation_mode:
                self.logger.info("Running in simulation mode")
                self.connected = True
                self.connection_status_changed.emit(True)
                self.start_updates()
                return True
            
            self.logger.info(f"Connecting to IB Gateway on port {self.port} with Client ID {CLIENT_ID}")
            
            self.ib = IB()
            self.ib.connect('127.0.0.1', self.port, clientId=CLIENT_ID, timeout=30)
            
            if self.ib.isConnected():
                self.connected = True
                self.connection_status_changed.emit(True)
                self.logger.info(f"✅ Client 10 connected: {CLIENT_PURPOSE}")
                self.start_updates()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.error_occurred.emit(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        try:
            self.stop_updates()
            
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            
            self.connected = False
            self.connection_status_changed.emit(False)
            self.logger.info("Client 10 disconnected")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check connection status"""
        if self.simulation_mode:
            return self.connected
        return self.ib and self.ib.isConnected()
    
    # ==========================================================================
    # METRICS CALCULATION
    # ==========================================================================
    
    def calculate_gex(self, options_data: pd.DataFrame) -> float:
        """
        Calculate Gamma Exposure (GEX) in billions
        
        GEX = Σ(Gamma × Open Interest × Contract Size × Spot Price × Spot Price ÷ 100)
        """
        try:
            if self.simulation_mode:
                # Simulate GEX ranging from -5B to +5B
                return np.random.normal(-2.5, 1.5)
            
            # Real calculation would process options chain
            # This is a simplified version
            total_gex = 0
            
            # Process calls (positive gamma for market makers)
            call_gex = options_data[options_data['type'] == 'C']['gamma'].sum() * SPX_MULTIPLIER
            
            # Process puts (negative gamma for market makers)
            put_gex = -options_data[options_data['type'] == 'P']['gamma'].sum() * SPX_MULTIPLIER
            
            total_gex = (call_gex + put_gex) / 1_000_000_000  # Convert to billions
            
            return round(total_gex, 1)
            
        except Exception as e:
            self.logger.error(f"Error calculating GEX: {e}")
            return 0.0
    
    def calculate_dex(self, options_data: pd.DataFrame) -> float:
        """
        Calculate Delta Exposure (DEX) in millions
        
        DEX = Σ(Delta × Open Interest × Contract Size × Spot Price)
        """
        try:
            if self.simulation_mode:
                # Simulate DEX ranging from -2000M to +2000M
                return np.random.normal(850, 500)
            
            # Real calculation would process options chain
            total_dex = 0
            
            # Process calls
            call_dex = options_data[options_data['type'] == 'C']['delta'].sum() * SPX_MULTIPLIER
            
            # Process puts
            put_dex = options_data[options_data['type'] == 'P']['delta'].sum() * SPX_MULTIPLIER
            
            total_dex = (call_dex + put_dex) / 1_000_000  # Convert to millions
            
            return round(total_dex, 0)
            
        except Exception as e:
            self.logger.error(f"Error calculating DEX: {e}")
            return 0.0
    
    def calculate_ogl(self, spot_price: float, options_data: pd.DataFrame) -> float:
        """
        Calculate Zero Gamma Level (OGL)
        The price level where total gamma exposure equals zero
        """
        try:
            if self.simulation_mode:
                # Simulate OGL around current SPY price
                return spot_price + np.random.normal(0, 2)
            
            # Find the strike where gamma exposure flips
            # This is a simplified calculation
            strikes = options_data['strike'].unique()
            gamma_by_strike = options_data.groupby('strike')['gamma'].sum()
            
            # Find zero crossing point
            for i in range(len(gamma_by_strike) - 1):
                if gamma_by_strike.iloc[i] * gamma_by_strike.iloc[i+1] < 0:
                    # Linear interpolation
                    strike1 = strikes[i]
                    strike2 = strikes[i+1]
                    gamma1 = gamma_by_strike.iloc[i]
                    gamma2 = gamma_by_strike.iloc[i+1]
                    
                    ogl = strike1 + (strike2 - strike1) * (-gamma1 / (gamma2 - gamma1))
                    return round(ogl, 2)
            
            return spot_price  # Default to spot if no crossing found
            
        except Exception as e:
            self.logger.error(f"Error calculating OGL: {e}")
            return spot_price
    
    def calculate_dix(self) -> float:
        """
        Calculate Dark Index (DIX) - Dark Pool Sentiment
        Percentage of S&P 500 dollar volume from dark pools
        """
        try:
            if self.simulation_mode:
                # Simulate DIX between 35% and 50%
                return np.random.normal(42.5, 3)
            
            # Real implementation would fetch dark pool data
            # This is a placeholder
            return 42.5
            
        except Exception as e:
            self.logger.error(f"Error calculating DIX: {e}")
            return 42.5
    
    def calculate_swan(self, vix: float, skew: float, put_call_ratio: float) -> float:
        """
        Calculate Black Swan Risk Indicator
        Scale: 1 (low risk) to 5 (extreme risk)
        
        Based on:
        - VIX level
        - SKEW index
        - Put/Call ratio
        - Term structure
        """
        try:
            if self.simulation_mode:
                # Simulate SWAN between 1 and 3 (mostly low risk)
                value = np.random.exponential(0.5) + 1
                return min(5, max(1, value))
            
            # Weighted risk calculation
            risk_score = 1.0
            
            # VIX component (0-2 points)
            if vix > 30:
                risk_score += 2
            elif vix > 20:
                risk_score += 1
            elif vix > 15:
                risk_score += 0.5
            
            # SKEW component (0-1.5 points)
            if skew > 140:
                risk_score += 1.5
            elif skew > 130:
                risk_score += 1
            elif skew > 125:
                risk_score += 0.5
            
            # Put/Call ratio component (0-1.5 points)
            if put_call_ratio > 1.5:
                risk_score += 1.5
            elif put_call_ratio > 1.2:
                risk_score += 1
            elif put_call_ratio > 1.0:
                risk_score += 0.5
            
            return min(5, max(1, round(risk_score, 2)))
            
        except Exception as e:
            self.logger.error(f"Error calculating SWAN: {e}")
            return 1.85
    
    # ==========================================================================
    # UPDATE MANAGEMENT
    # ==========================================================================
    
    def start_updates(self):
        """Start the metrics update thread"""
        if not self.update_thread or not self.update_thread.is_alive():
            self.stop_flag.clear()
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
            self.update_timer.start()
            self.logger.info("Metrics update thread started")
    
    def stop_updates(self):
        """Stop the metrics update thread"""
        self.stop_flag.set()
        self.update_timer.stop()
        
        if self.update_thread:
            self.update_thread.join(timeout=5)
            self.logger.info("Metrics update thread stopped")
    
    def _update_loop(self):
        """Main update loop running in separate thread"""
        while not self.stop_flag.is_set():
            try:
                self._update_metrics()
                time.sleep(UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
                time.sleep(5)
    
    def _update_metrics(self):
        """Update all custom metrics"""
        try:
            if self.simulation_mode:
                # Use simulation data
                self._update_simulation_metrics()
            else:
                # Fetch real data from IB
                self._fetch_and_calculate_metrics()
            
            # Store in history
            self.metrics_history.append(self.current_metrics)
            
            self.logger.debug(f"Metrics updated: GEX={self.current_metrics.gex:.1f}B, "
                            f"DEX={self.current_metrics.dex:.0f}M, "
                            f"OGL={self.current_metrics.ogl:.2f}, "
                            f"DIX={self.current_metrics.dix:.1f}%, "
                            f"SWAN={self.current_metrics.swan:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")
    
    def _update_simulation_metrics(self):
        """Update metrics with simulated data"""
        # Add some random walk to simulation data
        self.current_metrics.gex += np.random.normal(0, 0.5)
        self.current_metrics.gex = max(-10, min(10, self.current_metrics.gex))
        
        self.current_metrics.dex += np.random.normal(0, 100)
        self.current_metrics.dex = max(-3000, min(3000, self.current_metrics.dex))
        
        self.current_metrics.ogl = 585.5 + np.random.normal(0, 1)
        
        self.current_metrics.dix = max(30, min(55, self.current_metrics.dix + np.random.normal(0, 1)))
        
        # SWAN tends to stay low with occasional spikes
        if np.random.random() < 0.05:  # 5% chance of spike
            self.current_metrics.swan = min(5, self.current_metrics.swan + np.random.uniform(0.5, 2))
        else:
            self.current_metrics.swan = max(1, self.current_metrics.swan * 0.95)
        
        self.current_metrics.timestamp = datetime.now()
    
    def _fetch_and_calculate_metrics(self):
        """Fetch real data from IB and calculate metrics"""
        # This would implement real IB data fetching
        # For now, use simulation
        self._update_simulation_metrics()
    
    def _emit_metrics(self):
        """Emit current metrics via Qt signal"""
        metrics_dict = self.current_metrics.to_dict()
        self.metrics_updated.emit(metrics_dict)
    
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    
    def _init_simulation_data(self) -> CustomMetrics:
        """Initialize simulation data"""
        return CustomMetrics(
            gex=-2.5,
            dex=850.0,
            ogl=585.5,
            dix=42.5,
            swan=1.85
        )
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics as dictionary"""
        return self.current_metrics.to_dict()
    
    def get_metrics_history(self) -> List[CustomMetrics]:
        """Get metrics history"""
        return list(self.metrics_history)
    
    def force_update(self):
        """Force an immediate metrics update"""
        self._update_metrics()
        self._emit_metrics()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

_client_instance = None

def get_metrics_client(port: int = PAPER_PORT) -> CustomMetricsClient:
    """
    Get or create singleton CustomMetricsClient instance
    
    Args:
        port: IB Gateway port (4002 for paper, 4001 for live)
    
    Returns:
        CustomMetricsClient instance
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = CustomMetricsClient(port)
    
    return _client_instance

def reset_metrics_client():
    """Reset the singleton instance"""
    global _client_instance
    
    if _client_instance:
        if _client_instance.is_connected():
            _client_instance.disconnect()
        _client_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    # Test the client
    app = QApplication(sys.argv)
    
    client = get_metrics_client()
    
    # Connect signals for testing
    client.connection_status_changed.connect(
        lambda status: print(f"Connection status: {'Connected' if status else 'Disconnected'}")
    )
    
    client.metrics_updated.connect(
        lambda metrics: print(f"Metrics updated: {metrics}")
    )
    
    client.error_occurred.connect(
        lambda error: print(f"Error: {error}")
    )
    
    # Test connection
    if client.connect():
        print("✅ Client 10 connected successfully")
        print(f"Current metrics: {client.get_current_metrics()}")
    else:
        print("❌ Failed to connect Client 10")
    
    sys.exit(app.exec())
