#!/usr/bin/env python3
"""
HMM Signal Provider API
A simple API wrapper for easy integration with any application.
Provides REST-like interface and WebSocket support for real-time updates.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict
import logging

# Import our signal provider
from hmm_signal_provider import (
    HMMSignalProvider, TradingSignal, RegimeUpdate, MarketData,
    MarketRegime, create_signal_provider
)

logger = logging.getLogger(__name__)

class SignalProviderAPI:
    """
    API wrapper for the HMM Signal Provider
    Provides simple methods for integration with any application
    """
    
    def __init__(self, symbols: List[str] = None, config: Dict[str, Any] = None):
        """
        Initialize the API
        
        Args:
            symbols: List of symbols to track
            config: Configuration dictionary
        """
        self.symbols = symbols or ["SPY"]
        self.config = config
        self.provider = None
        self.is_running = False
        
        # Event storage for API access
        self.latest_regime = None
        self.signal_buffer = []
        self.data_buffer = {}
        self.event_log = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Event subscribers (for WebSocket-like functionality)
        self.subscribers = {
            "regime": [],
            "signal": [],
            "data": [],
            "status": []
        }
    
    def initialize(self) -> Dict[str, Any]:
        """
        Initialize the signal provider
        
        Returns:
            Status dictionary
        """
        try:
            self.provider = create_signal_provider(
                symbols=self.symbols,
                config=self.config,
                callbacks={
                    "data": self._on_data_callback,
                    "regime": self._on_regime_callback,
                    "signal": self._on_signal_callback
                }
            )
            
            return {
                "success": True,
                "message": "Signal provider initialized successfully",
                "symbols": self.symbols
            }
            
        except Exception as e:
            logger.error(f"Error initializing provider: {e}")
            return {
                "success": False,
                "message": f"Initialization failed: {e}"
            }
    
    def start(self) -> Dict[str, Any]:
        """
        Start the signal provider
        
        Returns:
            Status dictionary
        """
        try:
            if not self.provider:
                return {
                    "success": False,
                    "message": "Provider not initialized. Call initialize() first."
                }
            
            self.provider.start()
            self.is_running = True
            
            self._notify_subscribers("status", {
                "event": "started",
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "success": True,
                "message": "Signal provider started successfully"
            }
            
        except Exception as e:
            logger.error(f"Error starting provider: {e}")
            return {
                "success": False,
                "message": f"Start failed: {e}"
            }
    
    def stop(self) -> Dict[str, Any]:
        """
        Stop the signal provider
        
        Returns:
            Status dictionary
        """
        try:
            if self.provider:
                self.provider.stop()
            
            self.is_running = False
            
            self._notify_subscribers("status", {
                "event": "stopped",
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                "success": True,
                "message": "Signal provider stopped successfully"
            }
            
        except Exception as e:
            logger.error(f"Error stopping provider: {e}")
            return {
                "success": False,
                "message": f"Stop failed: {e}"
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current system status
        
        Returns:
            Status dictionary
        """
        if not self.provider:
            return {
                "initialized": False,
                "running": False,
                "message": "Provider not initialized"
            }
        
        status = self.provider.get_status()
        
        return {
            "initialized": True,
            "running": status["running"],
            "last_update": status["last_update"].isoformat() if status["last_update"] else None,
            "symbols": status["symbols_tracked"],
            "signals_generated": status["signals_generated"],
            "regime_changes": status["regime_changes"],
            "models_trained": status["models_trained"],
            "current_regime": status["current_regime"]
        }
    
    def get_current_regime(self) -> Dict[str, Any]:
        """
        Get current market regime
        
        Returns:
            Regime information dictionary
        """
        with self.lock:
            if not self.latest_regime:
                return {
                    "regime": None,
                    "confidence": 0.0,
                    "timestamp": None,
                    "message": "No regime detected yet"
                }
            
            return {
                "regime": self.latest_regime.regime.name,
                "confidence": self.latest_regime.confidence,
                "timestamp": self.latest_regime.timestamp.isoformat(),
                "regime_probabilities": self.latest_regime.regime_probabilities.tolist() if self.latest_regime.regime_probabilities is not None else None
            }
    
    def get_signals(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get recent trading signals
        
        Args:
            limit: Maximum number of signals to return
        
        Returns:
            Signals dictionary
        """
        with self.lock:
            signals = self.signal_buffer[-limit:] if self.signal_buffer else []
            
            formatted_signals = []
            for signal in signals:
                formatted_signals.append({
                    "symbol": signal.symbol,
                    "signal_type": signal.signal_type,
                    "confidence": signal.confidence,
                    "regime": signal.regime.name,
                    "strategy": signal.strategy,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "position_size": signal.position_size,
                    "timestamp": signal.timestamp.isoformat(),
                    "metadata": signal.metadata
                })
            
            return {
                "signals": formatted_signals,
                "count": len(formatted_signals),
                "total_generated": len(self.signal_buffer)
            }
    
    def get_market_data(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get current market data
        
        Args:
            symbol: Specific symbol (optional)
        
        Returns:
            Market data dictionary
        """
        if not self.provider:
            return {
                "success": False,
                "message": "Provider not initialized"
            }
        
        try:
            data = self.provider.get_market_data(symbol)
            
            # Convert DataFrame to JSON-serializable format
            formatted_data = {}
            for sym, df in data.items():
                if df is not None and not df.empty:
                    # Get last few rows for API response
                    recent_data = df.tail(10)
                    formatted_data[sym] = {
                        "latest_price": float(recent_data['Close'].iloc[-1]),
                        "latest_volume": int(recent_data['Volume'].iloc[-1]),
                        "price_change": float(recent_data['Close'].pct_change().iloc[-1]),
                        "volatility": float(recent_data['volatility'].iloc[-1]) if 'volatility' in recent_data.columns else None,
                        "rsi": float(recent_data['rsi'].iloc[-1]) if 'rsi' in recent_data.columns else None,
                        "timestamp": recent_data.index[-1].isoformat(),
                        "data_points": len(df)
                    }
            
            return {
                "success": True,
                "data": formatted_data,
                "symbols": list(formatted_data.keys())
            }
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {
                "success": False,
                "message": f"Error retrieving market data: {e}"
            }
    
    def force_update(self) -> Dict[str, Any]:
        """
        Force an immediate update
        
        Returns:
            Status dictionary
        """
        try:
            if not self.provider:
                return {
                    "success": False,
                    "message": "Provider not initialized"
                }
            
            self.provider.force_update()
            
            return {
                "success": True,
                "message": "Force update completed",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in force update: {e}")
            return {
                "success": False,
                "message": f"Force update failed: {e}"
            }
    
    def get_regime_history(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get regime change history
        
        Args:
            limit: Maximum number of regime changes to return
        
        Returns:
            Regime history dictionary
        """
        if not self.provider:
            return {
                "success": False,
                "message": "Provider not initialized"
            }
        
        try:
            history = self.provider.get_regime_history(limit)
            
            formatted_history = []
            for regime_update in history:
                formatted_history.append({
                    "regime": regime_update.regime.name,
                    "confidence": regime_update.confidence,
                    "timestamp": regime_update.timestamp.isoformat(),
                    "regime_probabilities": regime_update.regime_probabilities.tolist() if regime_update.regime_probabilities is not None else None
                })
            
            return {
                "success": True,
                "history": formatted_history,
                "count": len(formatted_history)
            }
            
        except Exception as e:
            logger.error(f"Error getting regime history: {e}")
            return {
                "success": False,
                "message": f"Error retrieving regime history: {e}"
            }
    
    def subscribe_to_events(self, event_type: str, callback_func) -> Dict[str, Any]:
        """
        Subscribe to real-time events
        
        Args:
            event_type: Type of event ("regime", "signal", "data", "status")
            callback_func: Function to call when event occurs
        
        Returns:
            Subscription status
        """
        if event_type not in self.subscribers:
            return {
                "success": False,
                "message": f"Invalid event type: {event_type}"
            }
        
        self.subscribers[event_type].append(callback_func)
        
        return {
            "success": True,
            "message": f"Subscribed to {event_type} events",
            "subscriber_count": len(self.subscribers[event_type])
        }
    
    def unsubscribe_from_events(self, event_type: str, callback_func) -> Dict[str, Any]:
        """
        Unsubscribe from events
        
        Args:
            event_type: Type of event
            callback_func: Function to remove
        
        Returns:
            Unsubscription status
        """
        if event_type not in self.subscribers:
            return {
                "success": False,
                "message": f"Invalid event type: {event_type}"
            }
        
        try:
            self.subscribers[event_type].remove(callback_func)
            return {
                "success": True,
                "message": f"Unsubscribed from {event_type} events"
            }
        except ValueError:
            return {
                "success": False,
                "message": "Callback function not found in subscribers"
            }
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get current configuration
        
        Returns:
            Configuration dictionary
        """
        return {
            "symbols": self.symbols,
            "config": self.config,
            "provider_config": self.provider.config if self.provider else None
        }
    
    def update_configuration(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration (requires restart)
        
        Args:
            new_config: New configuration dictionary
        
        Returns:
            Update status
        """
        try:
            self.config = new_config
            
            return {
                "success": True,
                "message": "Configuration updated. Restart required to apply changes.",
                "restart_required": True
            }
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {
                "success": False,
                "message": f"Configuration update failed: {e}"
            }
    
    # Internal callback methods
    
    def _on_data_callback(self, market_data: MarketData):
        """Handle data updates from provider"""
        with self.lock:
            self.data_buffer[market_data.symbol] = market_data
            
        self._notify_subscribers("data", {
            "symbol": market_data.symbol,
            "timestamp": market_data.timestamp.isoformat(),
            "data_points": len(market_data.data)
        })
    
    def _on_regime_callback(self, regime_update: RegimeUpdate):
        """Handle regime updates from provider"""
        with self.lock:
            self.latest_regime = regime_update
        
        self._notify_subscribers("regime", {
            "regime": regime_update.regime.name,
            "confidence": regime_update.confidence,
            "timestamp": regime_update.timestamp.isoformat()
        })
    
    def _on_signal_callback(self, signal: TradingSignal):
        """Handle signal updates from provider"""
        with self.lock:
            self.signal_buffer.append(signal)
            # Keep only last 1000 signals
            if len(self.signal_buffer) > 1000:
                self.signal_buffer = self.signal_buffer[-1000:]
        
        self._notify_subscribers("signal", {
            "symbol": signal.symbol,
            "signal_type": signal.signal_type,
            "confidence": signal.confidence,
            "regime": signal.regime.name,
            "entry_price": signal.entry_price,
            "timestamp": signal.timestamp.isoformat()
        })
    
    def _notify_subscribers(self, event_type: str, data: Dict[str, Any]):
        """Notify all subscribers of an event"""
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")

# Convenience functions for quick setup

def create_api(symbols: List[str] = None, config: Dict[str, Any] = None) -> SignalProviderAPI:
    """
    Create a signal provider API instance
    
    Args:
        symbols: List of symbols to track
        config: Configuration dictionary
    
    Returns:
        SignalProviderAPI instance
    """
    return SignalProviderAPI(symbols, config)

def quick_start_api(symbols: List[str] = None) -> SignalProviderAPI:
    """
    Quick start API with default configuration
    
    Args:
        symbols: List of symbols to track
    
    Returns:
        Started SignalProviderAPI instance
    """
    api = create_api(symbols)
    api.initialize()
    api.start()
    return api

# Example usage and testing
if __name__ == "__main__":
    import time
    
    def on_regime_change(data):
        print(f"Regime Event: {data['regime']} (Confidence: {data['confidence']:.1%})")
    
    def on_signal_generated(data):
        print(f"Signal Event: {data['signal_type']} {data['symbol']} @ ${data['entry_price']:.2f}")
    
    def on_status_change(data):
        print(f"Status Event: {data['event']} at {data['timestamp']}")
    
    # Create and configure API
    print("Creating HMM Signal Provider API...")
    api = create_api(symbols=["SPY"])
    
    # Subscribe to events
    api.subscribe_to_events("regime", on_regime_change)
    api.subscribe_to_events("signal", on_signal_generated)
    api.subscribe_to_events("status", on_status_change)
    
    # Initialize and start
    print("Initializing...")
    init_result = api.initialize()
    print(f"Initialization: {init_result}")
    
    print("Starting...")
    start_result = api.start()
    print(f"Start: {start_result}")
    
    try:
        print("API running... Press Ctrl+C to stop")
        while True:
            time.sleep(30)
            
            # Print status
            status = api.get_status()
            print(f"Status: Running={status['running']}, Signals={status['signals_generated']}")
            
            # Print current regime
            regime = api.get_current_regime()
            if regime['regime']:
                print(f"Current Regime: {regime['regime']} (Confidence: {regime['confidence']:.1%})")
            
    except KeyboardInterrupt:
        print("\nStopping API...")
        stop_result = api.stop()
        print(f"Stop: {stop_result}")
        print("API stopped.")

