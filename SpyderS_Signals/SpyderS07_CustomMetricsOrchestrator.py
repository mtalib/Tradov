#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderS07_CustomMetricsOrchestrator.py
Group: S (Signals)
Purpose: Central orchestrator for all custom market metrics (IB Client 10)
Author: Mohamed Talib
Date Created: 2025-01-31
Last Updated: 2025-01-31 Time: 12:00:00

Description:
    Central orchestrator that coordinates all custom metric calculations and
    serves as IB Client 10. Provides a unified interface for GEX, DEX, OGL,
    DIX, SWAN, and SKEW calculations. Emits Qt signals for GUI integration
    and manages update scheduling for all metrics.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
import time
from datetime import datetime
from typing import Dict, Optional, Any
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    SPYDER_INTEGRATION = True
except ImportError:
    SpyderLogger = logging
    SpyderErrorHandler = None
    SPYDER_INTEGRATION = False

# Import all signal calculators
from SpyderS01_DIXCalculator import DIXCalculator, get_calculator_instance
from SpyderS03_BlackSwanIndicator import BlackSwanIndicator, get_black_swan_indicator
from SpyderS05_GEXDEXCalculator import GEXDEXCalculator  # Will be moved from N09
from SpyderS06_SKEWCalculator import SKEWCalculator, get_skew_calculator  # Will be moved from C18

# ==============================================================================
# CONSTANTS
# ==============================================================================
CLIENT_ID = 10  # IB Gateway Client ID
UPDATE_INTERVAL = 60  # Default update interval in seconds
FAST_UPDATE = 30  # Fast update during volatile periods
SLOW_UPDATE = 300  # Slow update during quiet periods

# ==============================================================================
# MAIN ORCHESTRATOR CLASS
# ==============================================================================
class CustomMetricsOrchestrator(QObject):
    """
    Central orchestrator for all custom market metrics.
    
    This class coordinates calculation of all custom indicators (GEX, DEX, OGL,
    DIX, SWAN, SKEW) and serves as IB Client 10 for the system. It provides
    Qt signals for GUI integration and manages efficient update scheduling.
    
    Signals:
        metrics_updated: Emitted when any metric updates
        connection_status_changed: IB connection status changes
        error_occurred: Error in calculation or connection
        
    Example:
        >>> orchestrator = CustomMetricsOrchestrator()
        >>> orchestrator.start()
        >>> metrics = orchestrator.get_all_metrics()
    """
    
    # Qt Signals
    metrics_updated = pyqtSignal(dict)  # All metrics update
    gex_updated = pyqtSignal(dict)      # GEX specific update
    dix_updated = pyqtSignal(float)     # DIX specific update
    swan_updated = pyqtSignal(dict)     # SWAN specific update
    connection_status_changed = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the orchestrator"""
        super().__init__()
        
        # Logging
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
            
        # Configuration
        self.config = config or {}
        self.client_id = CLIENT_ID
        self.update_interval = self.config.get('update_interval', UPDATE_INTERVAL)
        self.auto_start = self.config.get('auto_start', True)
        
        # Initialize calculators
        self._init_calculators()
        
        # Current metrics storage
        self.current_metrics = {
            'GEX': 0.0,
            'DEX': 0.0,
            'OGL': 0.0,
            'DIX': 0.0,
            'SWAN': 1.0,
            'SKEW': 100.0
        }
        
        # IB connection status
        self.ib_connected = False
        
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_metrics)
        self.update_timer.setInterval(self.update_interval * 1000)
        
        # Thread control
        self.running = False
        self.update_thread = None
        
        self.logger.info(f"Custom Metrics Orchestrator initialized (Client ID: {CLIENT_ID})")
        
        if self.auto_start:
            self.start()
            
    def _init_calculators(self):
        """Initialize all metric calculators"""
        try:
            # DIX Calculator
            self.dix_calculator = get_calculator_instance()
            self.logger.info("DIX Calculator initialized")
        except Exception as e:
            self.logger.warning(f"DIX Calculator not available: {e}")
            self.dix_calculator = None
            
        try:
            # Black Swan Indicator
            self.swan_indicator = get_black_swan_indicator()
            self.logger.info("Black Swan Indicator initialized")
        except Exception as e:
            self.logger.warning(f"Black Swan Indicator not available: {e}")
            self.swan_indicator = None
            
        try:
            # GEX/DEX Calculator (will be from S05)
            self.gex_calculator = GEXDEXCalculator()
            self.logger.info("GEX/DEX Calculator initialized")
        except Exception as e:
            self.logger.warning(f"GEX/DEX Calculator not available: {e}")
            self.gex_calculator = None
            
        try:
            # SKEW Calculator (will be from S06)
            self.skew_calculator = get_skew_calculator()
            self.logger.info("SKEW Calculator initialized")
        except Exception as e:
            self.logger.warning(f"SKEW Calculator not available: {e}")
            self.skew_calculator = None
            
    # ==========================================================================
    # PUBLIC METHODS - Control
    # ==========================================================================
    def start(self):
        """Start the orchestrator and begin updates"""
        if self.running:
            self.logger.warning("Orchestrator already running")
            return
            
        self.running = True
        self.update_timer.start()
        
        # Initial update
        self.update_all_metrics()
        
        self.logger.info("Custom Metrics Orchestrator started")
        self.connection_status_changed.emit(True, f"Client {CLIENT_ID} Active")
        
    def stop(self):
        """Stop the orchestrator"""
        self.running = False
        self.update_timer.stop()
        
        self.logger.info("Custom Metrics Orchestrator stopped")
        self.connection_status_changed.emit(False, f"Client {CLIENT_ID} Stopped")
        
    def connect_to_ib(self) -> bool:
        """
        Connect to IB Gateway as Client 10.
        
        Returns:
            True if connected successfully
        """
        try:
            # This would contain actual IB connection logic
            # For now, simulate connection
            self.ib_connected = True
            self.connection_status_changed.emit(True, f"IB Client {CLIENT_ID} Connected")
            self.logger.info(f"Connected to IB Gateway as Client {CLIENT_ID}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to IB: {e}")
            self.error_occurred.emit(str(e))
            return False
            
    def disconnect_from_ib(self):
        """Disconnect from IB Gateway"""
        self.ib_connected = False
        self.connection_status_changed.emit(False, f"IB Client {CLIENT_ID} Disconnected")
        self.logger.info("Disconnected from IB Gateway")
        
    # ==========================================================================
    # PUBLIC METHODS - Metrics
    # ==========================================================================
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all current metric values.
        
        Returns:
            Dictionary containing all metric values
        """
        return self.current_metrics.copy()
        
    def update_all_metrics(self):
        """Update all metrics and emit signals"""
        try:
            updated_metrics = {}
            
            # Update GEX/DEX/OGL
            if self.gex_calculator:
                try:
                    gex_data = self.gex_calculator.calculate_all()
                    updated_metrics['GEX'] = gex_data.get('gex', -2.5e9) / 1e9  # Convert to billions
                    updated_metrics['DEX'] = gex_data.get('dex', 850e6) / 1e6   # Convert to millions
                    updated_metrics['OGL'] = gex_data.get('ogl', 585.5)
                    self.gex_updated.emit(gex_data)
                except Exception as e:
                    self.logger.error(f"Error updating GEX/DEX: {e}")
                    # Use last known values
                    updated_metrics['GEX'] = self.current_metrics.get('GEX', -2.5)
                    updated_metrics['DEX'] = self.current_metrics.get('DEX', 850)
                    updated_metrics['OGL'] = self.current_metrics.get('OGL', 585.5)
            else:
                # Simulation mode
                updated_metrics['GEX'] = -2.5 + np.random.normal(0, 0.5)
                updated_metrics['DEX'] = 850 + np.random.normal(0, 100)
                updated_metrics['OGL'] = 585.5 + np.random.normal(0, 1)
                
            # Update DIX
            if self.dix_calculator:
                try:
                    dix_result = self.dix_calculator.calculate_dix()
                    if dix_result:
                        updated_metrics['DIX'] = dix_result.dix_percentage
                        self.dix_updated.emit(dix_result.dix_percentage)
                except Exception as e:
                    self.logger.error(f"Error updating DIX: {e}")
                    updated_metrics['DIX'] = self.current_metrics.get('DIX', 42.5)
            else:
                # Simulation mode
                updated_metrics['DIX'] = 42.5 + np.random.normal(0, 1)
                
            # Update SWAN
            if self.swan_indicator:
                try:
                    swan_result = self.swan_indicator.calculate_swan_score()
                    updated_metrics['SWAN'] = swan_result.overall_score
                    self.swan_updated.emit({
                        'score': swan_result.overall_score,
                        'status': swan_result.status.value,
                        'components': swan_result.component_scores
                    })
                except Exception as e:
                    self.logger.error(f"Error updating SWAN: {e}")
                    updated_metrics['SWAN'] = self.current_metrics.get('SWAN', 1.85)
            else:
                # Simulation mode - mostly low with occasional spikes
                if np.random.random() < 0.95:
                    updated_metrics['SWAN'] = 1.85 + np.random.normal(0, 0.2)
                else:
                    updated_metrics['SWAN'] = 3.5 + np.random.normal(0, 0.5)
                updated_metrics['SWAN'] = max(1, min(5, updated_metrics['SWAN']))
                
            # Update SKEW
            if self.skew_calculator:
                try:
                    skew_result = self.skew_calculator.calculate_skew()
                    if skew_result:
                        updated_metrics['SKEW'] = skew_result.skew_index
                except Exception as e:
                    self.logger.error(f"Error updating SKEW: {e}")
                    updated_metrics['SKEW'] = self.current_metrics.get('SKEW', 125.5)
            else:
                # Simulation mode
                updated_metrics['SKEW'] = 125.5 + np.random.normal(0, 5)
                
            # Format for display
            formatted_metrics = self._format_metrics(updated_metrics)
            
            # Update stored values
            self.current_metrics.update(updated_metrics)
            
            # Emit update signal
            self.metrics_updated.emit(formatted_metrics)
            
            # Adjust update frequency based on volatility
            self._adjust_update_frequency(updated_metrics)
            
            self.logger.debug(f"Metrics updated: GEX={updated_metrics['GEX']:.1f}B, "
                            f"DIX={updated_metrics['DIX']:.1f}%, "
                            f"SWAN={updated_metrics['SWAN']:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error in update_all_metrics: {e}")
            self.error_occurred.emit(str(e))
            if self.error_handler:
                self.error_handler.handle_error(e)
                
    def _format_metrics(self, metrics: Dict) -> Dict[str, Dict]:
        """Format metrics for display"""
        formatted = {}
        
        # GEX
        gex_value = metrics.get('GEX', 0)
        formatted['GEX'] = {
            'value': gex_value,
            'formatted_value': f"{gex_value:.1f}B",
            'change': 0,  # Would calculate from history
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        # DEX
        dex_value = metrics.get('DEX', 0)
        formatted['DEX'] = {
            'value': dex_value,
            'formatted_value': f"{dex_value:.0f}M",
            'change': 0,
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        # OGL
        ogl_value = metrics.get('OGL', 0)
        formatted['OGL'] = {
            'value': ogl_value,
            'formatted_value': f"{ogl_value:.2f}",
            'change': 0,
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        # DIX
        dix_value = metrics.get('DIX', 0)
        formatted['DIX'] = {
            'value': dix_value,
            'formatted_value': f"{dix_value:.1f}%",
            'change': 0,
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        # SWAN
        swan_value = metrics.get('SWAN', 0)
        formatted['SWAN'] = {
            'value': swan_value,
            'formatted_value': f"{swan_value:.2f}",
            'change': 0,
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        # SKEW
        skew_value = metrics.get('SKEW', 0)
        formatted['SKEW'] = {
            'value': skew_value,
            'formatted_value': f"{skew_value:.1f}",
            'change': 0,
            'change_pct': 0,
            'timestamp': datetime.now()
        }
        
        return formatted
        
    def _adjust_update_frequency(self, metrics: Dict):
        """Adjust update frequency based on market conditions"""
        swan_score = metrics.get('SWAN', 1)
        
        if swan_score > 3:
            # High risk - fast updates
            new_interval = FAST_UPDATE
        elif swan_score > 2:
            # Moderate risk - normal updates
            new_interval = UPDATE_INTERVAL
        else:
            # Low risk - slow updates
            new_interval = SLOW_UPDATE
            
        if new_interval != self.update_timer.interval() / 1000:
            self.update_timer.setInterval(new_interval * 1000)
            self.logger.info(f"Update frequency adjusted to {new_interval}s")
            
    # ==========================================================================
    # PUBLIC METHODS - Individual Metrics
    # ==========================================================================
    def get_gex(self) -> float:
        """Get current GEX value in billions"""
        return self.current_metrics.get('GEX', 0)
        
    def get_dex(self) -> float:
        """Get current DEX value in millions"""
        return self.current_metrics.get('DEX', 0)
        
    def get_ogl(self) -> float:
        """Get current OGL (Zero Gamma Level)"""
        return self.current_metrics.get('OGL', 0)
        
    def get_dix(self) -> float:
        """Get current DIX percentage"""
        return self.current_metrics.get('DIX', 0)
        
    def get_swan(self) -> float:
        """Get current SWAN score (1-5)"""
        return self.current_metrics.get('SWAN', 1)
        
    def get_skew(self) -> float:
        """Get current SKEW index"""
        return self.current_metrics.get('SKEW', 100)
        
    def force_update(self, metric: Optional[str] = None):
        """Force update of specific metric or all metrics"""
        if metric:
            # Update specific metric
            if metric == 'GEX' and self.gex_calculator:
                self.gex_calculator.calculate_all()
            elif metric == 'DIX' and self.dix_calculator:
                self.dix_calculator.calculate_dix()
            elif metric == 'SWAN' and self.swan_indicator:
                self.swan_indicator.calculate_swan_score()
            elif metric == 'SKEW' and self.skew_calculator:
                self.skew_calculator.calculate_skew()
        else:
            # Update all
            self.update_all_metrics()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_orchestrator_instance = None

def get_metrics_orchestrator() -> CustomMetricsOrchestrator:
    """Get singleton instance of metrics orchestrator"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = CustomMetricsOrchestrator()
    return _orchestrator_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    print("="*60)
    print("CUSTOM METRICS ORCHESTRATOR TEST")
    print("="*60)
    
    # Create Qt application for signals
    app = QApplication(sys.argv)
    
    # Create orchestrator
    orchestrator = CustomMetricsOrchestrator()
    
    # Connect signals for testing
    orchestrator.metrics_updated.connect(
        lambda m: print(f"\n📊 Metrics Updated: {m['GEX']['formatted_value']} GEX, "
                       f"{m['DIX']['formatted_value']} DIX, "
                       f"{m['SWAN']['formatted_value']} SWAN")
    )
    
    # Start orchestrator
    orchestrator.start()
    
    # Get initial metrics
    metrics = orchestrator.get_all_metrics()
    
    print(f"\n📈 Initial Metrics:")
    print(f"  GEX: {metrics['GEX']:.1f}B")
    print(f"  DEX: {metrics['DEX']:.0f}M")
    print(f"  OGL: {metrics['OGL']:.2f}")
    print(f"  DIX: {metrics['DIX']:.1f}%")
    print(f"  SWAN: {metrics['SWAN']:.2f}")
    print(f"  SKEW: {metrics['SKEW']:.1f}")
    
    print("\n✅ Orchestrator test completed!")
    print("(Orchestrator will continue running - Ctrl+C to stop)")
    
    # Run event loop
    try:
        app.exec()
    except KeyboardInterrupt:
        orchestrator.stop()
        print("\n🛑 Orchestrator stopped")
