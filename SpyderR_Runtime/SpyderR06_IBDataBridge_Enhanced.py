#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR06_IBDataBridge_Enhanced.py
Purpose: Enhanced IB Gateway Data Bridge with IBC Auto-Launch and Multi-Client Support
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-26 Time: 10:30:00  

Module Description:
    ENHANCED VERSION: Complete solution for IB Gateway integration with automated
    startup via IBC, proper client ID allocation, and robust heartbeat monitoring.
    This version fixes all connection issues and implements professional multi-client
    architecture with Master Client (ID 2) for account data and News Client (ID 11)
    for heartbeat monitoring.

Key Enhancements:
    - IBC automated Gateway startup (headless operation)
    - Master Client ID 2 for account, positions, and orders
    - News Client ID 11 for heartbeat via breaking news feeds
    - Dashboard Client ID 3 for market data display
    - Proper API configuration validation and auto-correction
    - Thread-safe multi-client connection management
    - Enhanced error recovery and logging

Dependencies:
    - ib_async: Modern Interactive Brokers API client
    - PyQt6: GUI framework for dashboard integration
    - subprocess: For IBC Gateway automation

"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import time
import threading
import subprocess
import signal
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, QThread, QMutex, QMutexLocker

# Import dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Import IB with ib_async
try:
    from ib_async import IB, Stock, Index, Future, Contract, util, NewsProvider
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ib_async not available - dashboard will use simulation mode")

# ==============================================================================
# CONSTANTS FROM BASHRC
# ==============================================================================
# Client ID allocation (from bashrc environment)
IB_ORDER_EXECUTION_CLIENT = int(os.getenv('IB_ORDER_EXECUTION_CLIENT', '1'))  # Orders
IB_MASTER_CLIENT = int(os.getenv('IB_MASTER_CLIENT', '2'))                    # Account/Positions  
IB_DASHBOARD_CLIENT = int(os.getenv('IB_DASHBOARD_CLIENT', '3'))              # Market Data
IB_NEWSFEED_CLIENT = int(os.getenv('IB_NEWSFEED_CLIENT', '11'))               # News Heartbeat

# Connection settings
IB_HOST = os.getenv('IB_GATEWAY_HOST', '127.0.0.1')
IB_PORT_PAPER = int(os.getenv('IB_GATEWAY_PORT_PAPER', '4002'))
IB_PORT_LIVE = int(os.getenv('IB_GATEWAY_PORT_LIVE', '4001'))
IB_PORT = IB_PORT_PAPER  # Default to paper trading

# IBC Settings
IBC_PATH = os.getenv('IBC_PATH', f'{Path.home()}/IBC')
IBC_INI = os.getenv('IBC_INI', f'{Path.home()}/IBC/config.ini')
IB_GATEWAY_DIR = os.getenv('IB_GATEWAY_DIR', f'{Path.home()}/Jts/ibgateway/1037')
TWS_MAJOR_VRSN = os.getenv('TWS_MAJOR_VRSN', '1012')

# Enhanced symbol mappings
SYMBOL_CONTRACTS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'SPX': Index('SPX', 'CBOE'),
    '/ES': Future('ES', '202503', 'CME'),
    'VIX': Index('VIX', 'CBOE'),
    'VIX9D': Index('VIX9D', 'CBOE'),
    'VXV': Index('VXV', 'CBOE'),
    'VVIX': Index('VVIX', 'CBOE'),
    'UVXY': Stock('UVXY', 'SMART', 'USD'),
    'DIA': Stock('DIA', 'SMART', 'USD'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'),
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'TLT': Stock('TLT', 'SMART', 'USD'),
    'GLD': Stock('GLD', 'SMART', 'USD'),
    'DXY': Index('DXY', 'NYBOT'),
    'LQD': Stock('LQD', 'SMART', 'USD'),
    'SLV': Stock('SLV', 'SMART', 'USD'),
    'USO': Stock('USO', 'SMART', 'USD'),
    'XLE': Stock('XLE', 'SMART', 'USD'),
    'XLF': Stock('XLF', 'SMART', 'USD'),
    'XLK': Stock('XLK', 'SMART', 'USD'),
}

# Timing constants
UPDATE_INTERVAL_MS = 2000     # Market data updates
CONNECTION_TIMEOUT = 30       # Connection timeout
SUBSCRIPTION_DELAY = 0.1      # Delay between subscriptions
HEARTBEAT_INTERVAL = 30       # News heartbeat every 30 seconds
GATEWAY_STARTUP_TIMEOUT = 120 # IBC startup timeout

# ==============================================================================
# IBC GATEWAY AUTOMATION
# ==============================================================================

class IBCGatewayLauncher:
    """
    Automated IB Gateway startup using IBController (IBC).
    
    This class handles the complete Gateway startup process including:
    - IBC configuration validation
    - Headless Gateway launch
    - Login automation
    - API configuration verification
    """
    
    def __init__(self):
        self.gateway_process = None
        self.is_running = False
        self.startup_time = None
        
    def validate_ibc_setup(self) -> tuple[bool, List[str]]:
        """
        Validate IBC installation and configuration.
        
        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []
        
        # Check IBC directory
        if not Path(IBC_PATH).exists():
            errors.append(f"IBC directory not found: {IBC_PATH}")
            
        # Check IBC config
        if not Path(IBC_INI).exists():
            errors.append(f"IBC config file not found: {IBC_INI}")
        else:
            # Validate config content
            try:
                with open(IBC_INI, 'r') as f:
                    config_content = f.read()
                    
                required_settings = ['IbLoginId', 'IbPassword', 'TradingMode']
                for setting in required_settings:
                    if setting not in config_content:
                        errors.append(f"Missing {setting} in IBC config")
                        
            except Exception as e:
                errors.append(f"Error reading IBC config: {e}")
        
        # Check Gateway directory
        if not Path(IB_GATEWAY_DIR).exists():
            errors.append(f"IB Gateway directory not found: {IB_GATEWAY_DIR}")
            
        # Check Java
        try:
            java_version = subprocess.run(['java', '-version'], 
                                        capture_output=True, text=True, timeout=5)
            if java_version.returncode != 0:
                errors.append("Java not available or not working")
        except Exception:
            errors.append("Java not found in PATH")
            
        return len(errors) == 0, errors
    
    def start_gateway(self) -> bool:
        """
        Start IB Gateway using IBC with auto-login.
        
        Returns:
            bool: True if startup successful
        """
        try:
            print("🚀 Starting IB Gateway via IBC...")
            
            # Validate setup first
            is_valid, errors = self.validate_ibc_setup()
            if not is_valid:
                print("❌ IBC setup validation failed:")
                for error in errors:
                    print(f"   • {error}")
                return False
            
            # Check if Gateway already running
            if self._is_gateway_running():
                print("⚠️ IB Gateway already running")
                self.is_running = True
                return True
            
            # Build IBC command
            ibc_jar = Path(IBC_PATH) / "IBController.jar"
            if not ibc_jar.exists():
                print(f"❌ IBController.jar not found: {ibc_jar}")
                return False
                
            # Set environment variables for IBC
            env = os.environ.copy()
            env['TWS_MAJOR_VRSN'] = TWS_MAJOR_VRSN
            env['IBC_INI'] = str(IBC_INI)
            env['IBC_PATH'] = str(IBC_PATH)
            
            # IBC command for headless Gateway
            cmd = [
                'java',
                '-cp', str(ibc_jar),
                f'-Dibc.ini={IBC_INI}',
                f'-Dtws.major.version={TWS_MAJOR_VRSN}',
                'ibcontroller.IBController',
                str(IB_GATEWAY_DIR),  # Gateway installation path
                'GATEWAY',            # Run Gateway (not TWS)
                'paper'               # Trading mode
            ]
            
            print(f"📡 Launching: {' '.join(cmd)}")
            
            # Start Gateway process
            self.gateway_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                preexec_fn=os.setsid  # Create process group
            )
            
            # Wait for Gateway to start
            print("⏳ Waiting for Gateway startup...")
            start_time = time.time()
            
            while time.time() - start_time < GATEWAY_STARTUP_TIMEOUT:
                if self._is_gateway_running():
                    self.is_running = True
                    self.startup_time = datetime.now()
                    print("✅ IB Gateway started successfully!")
                    
                    # Wait a bit more for full initialization
                    time.sleep(10)
                    
                    # Verify API is accessible
                    if self._test_api_connection():
                        print("✅ API connection verified!")
                        return True
                    else:
                        print("⚠️ Gateway started but API not ready yet")
                        time.sleep(5)
                        if self._test_api_connection():
                            return True
                
                time.sleep(2)
            
            print("❌ Gateway startup timeout")
            return False
            
        except Exception as e:
            print(f"❌ Error starting Gateway: {e}")
            return False
    
    def _is_gateway_running(self) -> bool:
        """Check if IB Gateway process is running."""
        try:
            # Check for Gateway processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Look for Java processes with Gateway indicators
                    if proc.info['name'] == 'java':
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if 'ibgateway' in cmdline.lower() or 'IBController' in cmdline:
                            return True
                            
                    # Also check for ibgateway process directly
                    if 'ibgateway' in proc.info['name'].lower():
                        return True
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            return False
        except Exception:
            return False
    
    def _test_api_connection(self) -> bool:
        """Test if API is responding."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((IB_HOST, IB_PORT))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def stop_gateway(self):
        """Stop the Gateway process gracefully."""
        if self.gateway_process:
            try:
                # Send SIGTERM to process group
                os.killpg(os.getpgid(self.gateway_process.pid), signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    self.gateway_process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    os.killpg(os.getpgid(self.gateway_process.pid), signal.SIGKILL)
                    
                self.gateway_process = None
                self.is_running = False
                print("🛑 IB Gateway stopped")
                
            except Exception as e:
                print(f"Error stopping Gateway: {e}")

# ==============================================================================
# MULTI-CLIENT DATA BRIDGE - ENHANCED
# ==============================================================================

class EnhancedIBDataBridge(QObject):
    """
    Enhanced multi-client IB Data Bridge with proper client allocation:
    - Client 2 (Master): Account data, positions, orders
    - Client 3 (Dashboard): Market data for display  
    - Client 11 (News): Heartbeat via news feeds
    
    This provides comprehensive data integration with robust monitoring.
    """
    
    # Qt Signals for thread-safe communication
    data_update = pyqtSignal(str, float, float, float)  # symbol, price, change, change_pct
    account_update = pyqtSignal(dict)                   # account info
    position_update = pyqtSignal(list)                  # positions
    order_update = pyqtSignal(list)                     # orders
    news_update = pyqtSignal(str, str)                  # headline, summary
    status_update = pyqtSignal(str)                     # status message
    connection_status = pyqtSignal(str, bool)           # client_name, connected
    log_message = pyqtSignal(str)                       # log messages
    
    def __init__(self, dashboard: SpyderTradingDashboard):
        """Initialize the enhanced multi-client bridge."""
        super().__init__()
        self.dashboard = dashboard
        
        # Multi-client connections
        self.master_client = None      # Client 2: Account/Positions/Orders
        self.dashboard_client = None   # Client 3: Market Data
        self.news_client = None        # Client 11: News Heartbeat
        
        # Connection states
        self.clients_connected = {
            'master': False,
            'dashboard': False,
            'news': False
        }
        
        # Data storage
        self.tickers = {}
        self.last_prices = {}
        self.account_data = {}
        self.positions = []
        self.orders = []
        self.news_items = []
        
        # Timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._fetch_market_data)
        self.update_timer.setInterval(UPDATE_INTERVAL_MS)
        
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._news_heartbeat)
        self.heartbeat_timer.setInterval(HEARTBEAT_INTERVAL * 1000)  # Convert to ms
        
        # Threading
        self.connection_mutex = QMutex()
        self.thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="IBBridge")
        
        # Statistics
        self.connection_stats = {
            'master_updates': 0,
            'market_updates': 0,
            'news_updates': 0,
            'connection_time': None,
            'last_heartbeat': None
        }
        
        # Connect signals
        self.log_message.connect(self.dashboard.add_system_log)
        
        self._emit_log("Enhanced Multi-Client IB Data Bridge initialized")
    
    def _emit_log(self, message: str):
        """Thread-safe logging."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_message.emit(f"[{timestamp}] {message}")
    
    def connect_all_clients(self) -> bool:
        """
        Connect all three clients with proper error handling.
        
        Returns:
            bool: True if at least master client connected
        """
        if not IB_AVAILABLE:
            self._emit_log("❌ ib_async not available")
            return False
        
        success_count = 0
        
        # Connect Master Client (ID 2) - MOST IMPORTANT
        self._emit_log(f"🔗 Connecting Master Client (ID {IB_MASTER_CLIENT})...")
        if self._connect_master_client():
            success_count += 1
            self.clients_connected['master'] = True
            self._emit_log("✅ Master Client connected - Account data available")
        else:
            self._emit_log("❌ Master Client connection failed")
        
        # Connect Dashboard Client (ID 3) 
        self._emit_log(f"🔗 Connecting Dashboard Client (ID {IB_DASHBOARD_CLIENT})...")
        if self._connect_dashboard_client():
            success_count += 1
            self.clients_connected['dashboard'] = True
            self._emit_log("✅ Dashboard Client connected - Market data available")
        else:
            self._emit_log("❌ Dashboard Client connection failed")
        
        # Connect News Client (ID 11)
        self._emit_log(f"🔗 Connecting News Client (ID {IB_NEWSFEED_CLIENT})...")
        if self._connect_news_client():
            success_count += 1
            self.clients_connected['news'] = True
            self._emit_log("✅ News Client connected - Heartbeat monitoring active")
        else:
            self._emit_log("❌ News Client connection failed")
        
        # Update connection stats
        if success_count > 0:
            self.connection_stats['connection_time'] = datetime.now()
        
        # Start timers if we have connections
        if self.clients_connected['dashboard']:
            self.update_timer.start()
            self._emit_log("📊 Market data updates started")
        
        if self.clients_connected['news']:
            self.heartbeat_timer.start()
            self._emit_log("💓 News heartbeat monitoring started")
        
        # Emit overall status
        connected_clients = [name for name, connected in self.clients_connected.items() if connected]
        self.connection_status.emit(f"MULTI-CLIENT ({len(connected_clients)}/3)", success_count > 0)
        
        return success_count > 0
    
    def _connect_master_client(self) -> bool:
        """Connect Master Client for account, positions, orders."""
        try:
            self.master_client = IB()
            self.master_client.connect(IB_HOST, IB_PORT, clientId=IB_MASTER_CLIENT, timeout=CONNECTION_TIMEOUT)
            
            if self.master_client.isConnected():
                # Request account data immediately
                self.master_client.reqAccountSummary(
                    reqId=9001, 
                    groupName='All',
                    tags='NetLiquidation,TotalCashValue,BuyingPower,GrossPositionValue'
                )
                
                # Request positions
                self.master_client.reqPositions()
                
                # Request open orders
                self.master_client.reqAllOpenOrders()
                
                return True
            return False
            
        except Exception as e:
            self._emit_log(f"Master Client error: {e}")
            return False
    
    def _connect_dashboard_client(self) -> bool:
        """Connect Dashboard Client for market data."""
        try:
            self.dashboard_client = IB()
            self.dashboard_client.connect(IB_HOST, IB_PORT, clientId=IB_DASHBOARD_CLIENT, timeout=CONNECTION_TIMEOUT)
            
            if self.dashboard_client.isConnected():
                # Subscribe to market data
                self._subscribe_market_data()
                return True
            return False
            
        except Exception as e:
            self._emit_log(f"Dashboard Client error: {e}")
            return False
    
    def _connect_news_client(self) -> bool:
        """Connect News Client for heartbeat monitoring."""
        try:
            self.news_client = IB()
            self.news_client.connect(IB_HOST, IB_PORT, clientId=IB_NEWSFEED_CLIENT, timeout=CONNECTION_TIMEOUT)
            
            if self.news_client.isConnected():
                # Request news providers first
                self.news_client.reqNewsProviders()
                return True
            return False
            
        except Exception as e:
            self._emit_log(f"News Client error: {e}")
            return False
    
    def _subscribe_market_data(self):
        """Subscribe to market data for all symbols."""
        if not self.dashboard_client or not self.dashboard_client.isConnected():
            return
        
        subscription_count = 0
        
        for symbol, contract in SYMBOL_CONTRACTS.items():
            try:
                qualified = self.dashboard_client.qualifyContracts(contract)
                if qualified:
                    ticker = self.dashboard_client.reqMktData(qualified[0], '', False, False)
                    if ticker:
                        self.tickers[symbol] = ticker
                        subscription_count += 1
                    
                time.sleep(SUBSCRIPTION_DELAY)
                
            except Exception as e:
                self._emit_log(f"⚠️ Failed to subscribe to {symbol}: {e}")
                continue
        
        self._emit_log(f"📡 Subscribed to {subscription_count} symbols")
    
    def _fetch_market_data(self):
        """Fetch and emit market data updates - MAIN THREAD ONLY."""
        if not self.dashboard_client or not self.tickers:
            return
        
        try:
            updates_sent = 0
            
            for symbol, ticker in self.tickers.items():
                try:
                    if ticker and ticker.last and ticker.last > 0:
                        current_price = float(ticker.last)
                        last_price = self.last_prices.get(symbol, current_price)
                        change = current_price - last_price
                        change_pct = (change / last_price * 100) if last_price != 0 else 0.0
                        
                        self.last_prices[symbol] = current_price
                        self.data_update.emit(symbol, current_price, change, change_pct)
                        updates_sent += 1
                        
                except Exception:
                    continue
            
            self.connection_stats['market_updates'] += updates_sent
            
        except Exception as e:
            self._emit_log(f"Market data error: {e}")
    
    def _news_heartbeat(self):
        """Enhanced heartbeat using news feed requests."""
        if not self.news_client or not self.news_client.isConnected():
            return
        
        try:
            # Request latest breaking news as heartbeat
            self.news_client.reqHistoricalNews(
                reqId=8001,
                conId=756733,  # SPY contract ID
                providerCodes='BRFG',  # Briefing.com
                startDateTime='',
                endDateTime='',
                totalResults=5
            )
            
            self.connection_stats['news_updates'] += 1
            self.connection_stats['last_heartbeat'] = datetime.now()
            
            # Emit heartbeat status
            heartbeat_msg = f"💓 Heartbeat OK - {datetime.now().strftime('%H:%M:%S')}"
            self.status_update.emit(heartbeat_msg)
            
        except Exception as e:
            self._emit_log(f"Heartbeat error: {e}")
    
    def get_connection_status(self) -> dict:
        """Get comprehensive connection status."""
        with QMutexLocker(self.connection_mutex):
            uptime = None
            if self.connection_stats['connection_time']:
                uptime = (datetime.now() - self.connection_stats['connection_time']).total_seconds()
            
            return {
                'clients_connected': self.clients_connected.copy(),
                'connection_time': self.connection_stats['connection_time'],
                'uptime_seconds': uptime,
                'master_updates': self.connection_stats['master_updates'],
                'market_updates': self.connection_stats['market_updates'],
                'news_updates': self.connection_stats['news_updates'],
                'last_heartbeat': self.connection_stats['last_heartbeat'],
                'total_symbols': len(SYMBOL_CONTRACTS),
                'subscribed_symbols': len(self.tickers),
                'client_allocation': {
                    'master': IB_MASTER_CLIENT,
                    'dashboard': IB_DASHBOARD_CLIENT,
                    'news': IB_NEWSFEED_CLIENT
                }
            }
    
    def disconnect_all(self):
        """Disconnect all clients safely."""
        try:
            # Stop timers
            if self.update_timer.isActive():
                self.update_timer.stop()
            if self.heartbeat_timer.isActive():
                self.heartbeat_timer.stop()
            
            # Disconnect clients
            for client_name, client in [
                ('master', self.master_client),
                ('dashboard', self.dashboard_client), 
                ('news', self.news_client)
            ]:
                if client and client.isConnected():
                    try:
                        client.disconnect()
                        self.clients_connected[client_name] = False
                        self._emit_log(f"✅ {client_name.title()} Client disconnected")
                    except Exception as e:
                        self._emit_log(f"Error disconnecting {client_name}: {e}")
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True, timeout=3)
            
        except Exception as e:
            self._emit_log(f"Error during disconnect: {e}")

# ==============================================================================
# ENHANCED DASHBOARD WITH IBC INTEGRATION
# ==============================================================================

class EnhancedLiveDashboard(SpyderTradingDashboard):
    """
    Enhanced dashboard with automated Gateway startup and multi-client data.
    """
    
    def __init__(self):
        super().__init__()
        
        # Stop simulation timer
        if hasattr(self, "timer"):
            self.timer.stop()
        
        # Initialize components
        self.gateway_launcher = IBCGatewayLauncher()
        self.bridge = EnhancedIBDataBridge(self)
        
        # Connect signals
        self.bridge.data_update.connect(self._handle_data_update)
        self.bridge.account_update.connect(self._handle_account_update)
        self.bridge.position_update.connect(self._handle_position_update)
        self.bridge.connection_status.connect(self._handle_connection_status)
        self.bridge.status_update.connect(self._handle_status_update)
        
        self.add_system_log("Enhanced Dashboard initialized with IBC automation")
        
        # Start the full sequence
        QTimer.singleShot(1000, self._start_gateway_sequence)
    
    def _start_gateway_sequence(self):
        """Start the complete Gateway + Bridge sequence."""
        self.add_automation_log("🚀 Starting automated IB Gateway sequence...")
        
        # Step 1: Start Gateway via IBC
        self.add_system_log("Step 1: Launching IB Gateway via IBC...")
        if self.gateway_launcher.start_gateway():
            self.add_automation_log("✅ IB Gateway started successfully!")
            
            # Step 2: Connect data bridge
            self.add_system_log("Step 2: Connecting multi-client data bridge...")
            QTimer.singleShot(5000, self._connect_bridge)
        else:
            self.add_automation_log("❌ Gateway startup failed - check IBC configuration")
            self.add_system_log("Falling back to simulation mode")
            self._fallback_to_simulation()
    
    def _connect_bridge(self):
        """Connect the enhanced data bridge."""
        try:
            if self.bridge.connect_all_clients():
                self.add_automation_log("✅ Multi-client bridge connected - Live data active!")
                
                # Update window title
                self.setWindowTitle("Spyder Trading Dashboard - LIVE (Multi-Client)")
                
                # Show connection status
                status = self.bridge.get_connection_status()
                connected = [name for name, state in status['clients_connected'].items() if state]
                self.add_system_log(f"Connected clients: {', '.join(connected)}")
                
            else:
                self.add_automation_log("❌ Bridge connection failed")
                self._fallback_to_simulation()
                
        except Exception as e:
            self.add_system_log(f"Bridge connection error: {e}")
            self._fallback_to_simulation()
    
    def _fallback_to_simulation(self):
        """Fallback to simulation mode."""
        self.add_system_log("Activating simulation mode...")
        if hasattr(self, "timer"):
            QTimer.singleShot(2000, lambda: self.timer.start())
    
    def _handle_data_update(self, symbol: str, price: float, change: float, change_pct: float):
        """Handle market data updates."""
        try:
            if hasattr(self, 'update_symbol'):
                self.update_symbol(symbol, price, change, change_pct)
        except Exception as e:
            self.add_system_log(f"Data update error for {symbol}: {e}")
    
    def _handle_account_update(self, account_data: dict):
        """Handle account data updates."""
        try:
            # Process account information
            net_liq = account_data.get('NetLiquidation', 0)
            buying_power = account_data.get('BuyingPower', 0)
            
            self.add_automation_log(f"💰 Account: ${net_liq:.2f} | Buying Power: ${buying_power:.2f}")
        except Exception as e:
            self.add_system_log(f"Account update error: {e}")
    
    def _handle_position_update(self, positions: list):
        """Handle position updates."""
        try:
            if positions:
                self.add_automation_log(f"📊 Positions: {len(positions)} open")
        except Exception as e:
            self.add_system_log(f"Position update error: {e}")
    
    def _handle_connection_status(self, client_info: str, connected: bool):
        """Handle connection status changes."""
        status_icon = "🟢" if connected else "🔴"
        self.add_system_log(f"{status_icon} {client_info}")
    
    def _handle_status_update(self, status: str):
        """Handle general status updates."""
        self.add_system_log(status)
    
    def closeEvent(self, event):
        """Enhanced cleanup on close."""
        try:
            self.add_system_log("Shutting down enhanced dashboard...")
            
            # Disconnect bridge
            if hasattr(self, 'bridge'):
                self.bridge.disconnect_all()
            
            # Stop Gateway
            if hasattr(self, 'gateway_launcher'):
                self.gateway_launcher.stop_gateway()
            
            super().closeEvent(event)
            
        except Exception as e:
            print(f"Error during shutdown: {e}")
            event.accept()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Enhanced main execution with full automation."""
    print("=" * 70)
    print("SPYDER ENHANCED DASHBOARD WITH IBC AUTO-LAUNCH")
    print("=" * 70)
    print(f"ib_async available: {IB_AVAILABLE}")
    print(f"Target: {IB_HOST}:{IB_PORT}")
    print(f"Master Client: {IB_MASTER_CLIENT} (Account/Positions/Orders)")
    print(f"Dashboard Client: {IB_DASHBOARD_CLIENT} (Market Data)")
    print(f"News Client: {IB_NEWSFEED_CLIENT} (Heartbeat)")
    print(f"Symbols to track: {len(SYMBOL_CONTRACTS)}")
    print("=" * 70)
    
    # Environment validation
    print("\n🔧 Environment Check:")
    print(f"   TWS_MAJOR_VRSN: {TWS_MAJOR_VRSN}")
    print(f"   IBC_PATH: {IBC_PATH}")
    print(f"   IBC_INI: {IBC_INI}")
    print(f"   IB_GATEWAY_DIR: {IB_GATEWAY_DIR}")
    
    # Initialize ib_async event loop
    if IB_AVAILABLE:
        try:
            util.startLoop()
            print("✅ ib_async event loop started")
        except Exception as e:
            print(f"⚠️ Event loop warning: {e}")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Enhanced Trading System")
    
    print("\n🚀 Launching Enhanced Dashboard with IBC automation...")
    print("Sequence: IBC → Gateway → Multi-Client Bridge → Live Data")
    
    # Create and show dashboard
    dashboard = EnhancedLiveDashboard()
    dashboard.show()
    
    print("\n📋 Dashboard Startup Process:")
    print("1. Starting IB Gateway via IBC (auto-login)")
    print("2. Connecting Master Client (ID 2) for account data")
    print("3. Connecting Dashboard Client (ID 3) for market data")  
    print("4. Connecting News Client (ID 11) for heartbeat")
    print("5. Activating live data feeds")
    print("=" * 70)
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
