Technical Specifications: Integrating Spyder with Tradier API  and Databento 
System Overview
Build a local trading application on Ubuntu/Wayland using Python 3.10+ and PySide6 that integrates:

Tradier API: Brokerage operations (account info, orders, positions)

Databento API: Real-time and historical market data (focus on SPY options)

Architecture Requirements
Project Structure
text
trading_system/
├── main.py                 # PySide6 application entry point
├── config/
│   ├── __init__.py
│   ├── settings.py         # API keys, endpoints, environment vars
│   └── constants.py        # Symbol mappings, exchange codes
├── core/
│   ├── __init__.py
│   ├── data_manager.py     # Central data hub coordinating both APIs
│   ├── event_bus.py        # Internal pub/sub for system events
│   └── logger.py           # Structured logging
├── api_connectors/
│   ├── __init__.py
│   ├── tradier_client.py   # Tradier REST + Streaming implementation
│   └── databento_client.py # Databento historical + live implementation
├── models/
│   ├── __init__.py
│   ├── market_data.py      # Pydantic models for quotes, trades, options chains
│   └── account.py          # Account, positions, orders models
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # PySide6 main window
│   ├── widgets/
│   │   ├── chart_widget.py # Real-time price chart
│   │   ├── options_chain.py # Options chain display
│   │   ├── order_entry.py   # Order placement interface
│   │   └── account_view.py  # Account summary
│   └── styles/
│       └── dark_theme.qss   # Consistent UI styling
├── strategies/
│   ├── __init__.py
│   └── spy_options_strat.py # Your automated trading logic
└── utils/
    ├── __init__.py
    ├── time_utils.py        # Timestamp conversion (nanosecond precision)
    └── calculations.py      # Greeks, IV calculations if needed
API Integration Specifications
1. Databento Client (api_connectors/databento_client.py)
Requirements
Install Databento Python package: pip install databento

Handle nanosecond timestamps (Databento's native format)

Support both live streaming and historical data

Convert Databento schemas to internal models

Implementation Spec
python
from databento import Historical, Live, Schema, Dataset
import asyncio
from typing import Callable, Dict, List, Optional
from datetime import datetime, timedelta

class DatabentoClient:
    """Manages all Databento data connections"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.historical = Historical(api_key)
        self.live_clients: Dict[str, Live] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        
    async def connect_live(self, symbols: List[str], schema: Schema = Schema.OHLCV_1S):
        """
        Connect to live data stream
        For SPY options: need to handle dynamic option symbols
        """
        # Implementation details:
        # 1. Initialize Live client with dataset (GLBX.MDP3 for futures, but need OPRA for options)
        # 2. Subscribe to symbols with specific schema
        # 3. Start async loop to receive messages
        # 4. Dispatch to subscribers based on symbol/type
        pass
    
    async def get_historical_options_chain(
        self, 
        symbol: str = "SPY", 
        date: datetime,
        minutes_before: int = 390,  # Full trading day
        minutes_after: int = 0
    ):
        """
        Fetch historical options chain for backtesting
        Returns all strikes/expirations with quotes/trades
        """
        # Use historical.timeseries.get_range()
        # Schema: Schema.OPTION_TRADES, Schema.OPTION_QUOTES, Schema.DEFINITION
        pass
    
    def subscribe_quotes(self, symbols: List[str], callback: Callable):
        """Subscribe to real-time option quotes"""
        pass
    
    def subscribe_trades(self, symbols: List[str], callback: Callable):
        """Subscribe to real-time option trades"""
        pass
2. Tradier Client (api_connectors/tradier_client.py)
Requirements
Install requests, websocket-client: pip install requests websocket-client

Support both REST API and streaming API

Handle authentication and rate limiting

Provide synchronous (for UI) and asynchronous (for background) interfaces

Implementation Spec
python
import requests
import websocket
import threading
from typing import Dict, Any, Optional, Callable, List

class TradierClient:
    """Manages Tradier brokerage operations"""
    
    def __init__(self, access_token: str, account_id: str, is_paper: bool = True):
        self.access_token = access_token
        self.account_id = account_id
        self.base_url = "https://api.tradier.com/v1"
        self.stream_url = "wss://stream.tradier.com/v1/markets/events"
        self.session = self._create_session()
        self.ws: Optional[websocket.WebSocketApp] = None
        
    def _create_session(self):
        """Create requests session with auth headers"""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json'
        })
        return session
    
    # ===== REST API Methods =====
    def get_account_balance(self) -> Dict[str, Any]:
        """Get account balance and details"""
        response = self.session.get(f"{self.base_url}/accounts/{self.account_id}/balances")
        return response.json()
    
    def get_positions(self) -> List[Dict]:
        """Get current positions (especially option positions)"""
        response = self.session.get(f"{self.base_url}/accounts/{self.account_id}/positions")
        return response.json().get('positions', {}).get('position', [])
    
    def place_order(self, order_params: Dict) -> Dict:
        """
        Place option order
        Example order_params:
        {
            'symbol': 'SPY',
            'option_symbol': 'SPY250218C00550000',
            'side': 'buy_to_open',
            'quantity': 1,
            'type': 'limit',
            'price': 2.35,
            'duration': 'day'
        }
        """
        response = self.session.post(
            f"{self.base_url}/accounts/{self.account_id}/orders",
            data=order_params
        )
        return response.json()
    
    def get_option_chains(self, symbol: str = "SPY", expiration: str = None) -> List[Dict]:
        """Get current options chain"""
        params = {'symbol': symbol, 'expiration': expiration} if expiration else {'symbol': symbol}
        response = self.session.get(f"{self.base_url}/markets/options/chains", params=params)
        return response.json().get('options', {}).get('option', [])
    
    # ===== Streaming API Methods =====
    def start_streaming(self, symbols: List[str], callbacks: Dict[str, Callable]):
        """
        Start WebSocket connection for real-time data
        Note: Tradier streaming is primarily for equities, limited options data
        """
        def on_message(ws, message):
            # Parse message and route to appropriate callback
            data = json.loads(message)
            if 'type' in data and data['type'] in callbacks:
                callbacks[data['type']](data)
        
        # WebSocket implementation
        self.ws = websocket.WebSocketApp(
            self.stream_url,
            header={'Authorization': f'Bearer {self.access_token}'},
            on_message=on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # Start in separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Subscribe after connection
        self._stream_subscribe(symbols)
3. Data Manager (core/data_manager.py)
Purpose
Central coordinator that merges data from both sources and provides a unified interface for the UI and trading strategies.

python
from typing import Dict, Any, Optional, Callable
from PySide6.QtCore import QObject, Signal, QThread
import pandas as pd

class DataManager(QObject):
    """Central data hub - emits Qt signals for UI updates"""
    
    # Qt signals for UI updates
    option_quote_updated = Signal(dict)  # Emit when new option quote arrives
    account_updated = Signal(dict)        # Emit when account changes
    order_filled = Signal(dict)           # Emit on order fills
    chart_data_updated = Signal(pd.DataFrame)  # For real-time chart updates
    
    def __init__(self, tradier_client, databento_client):
        super().__init__()
        self.tradier = tradier_client
        self.databento = databento_client
        self.current_positions = {}
        self.option_quotes = {}  # Symbol -> latest quote
        self.option_greeks = {}  # Option -> greeks (if calculating)
        
    def start(self, symbols_to_watch: List[str]):
        """Start all data feeds"""
        # Start Tradier account monitoring (polling or streaming)
        self._start_account_monitor()
        
        # Start Databento data feeds
        self._start_option_feeds(symbols_to_watch)
        
    def _start_option_feeds(self, symbols: List[str]):
        """Subscribe to option quotes/trades via Databento"""
        # Convert option symbols to Databento-compatible format
        # Subscribe to quotes and trades
        # Connect callbacks that emit Qt signals
        pass
        
    def get_current_option_chain(self, underlying: str = "SPY") -> pd.DataFrame:
        """
        Get current options chain with real-time quotes merged in
        Combines Tradier's chain definition with Databento's real-time prices
        """
        # 1. Get chain definition from Tradier
        tradier_chain = self.tradier.get_option_chains(underlying)
        
        # 2. Convert to DataFrame
        df = pd.DataFrame(tradier_chain)
        
        # 3. Merge real-time quotes from Databento
        for idx, row in df.iterrows():
            symbol = row['symbol']
            if symbol in self.option_quotes:
                df.loc[idx, 'bid'] = self.option_quotes[symbol]['bid']
                df.loc[idx, 'ask'] = self.option_quotes[symbol]['ask']
                df.loc[idx, 'last'] = self.option_quotes[symbol]['last']
                
        return df
4. Strategy Implementation (strategies/spy_options_strat.py)
python
from PySide6.QtCore import QObject, QTimer
import pandas as pd
import numpy as np

class SPYOptionsStrategy(QObject):
    """Your automated trading logic"""
    
    def __init__(self, data_manager, tradier_client):
        super().__init__()
        self.data = data_manager
        self.tradier = tradier_client
        self.position_sizing = {}  # Track position sizes
        self.signals = pd.DataFrame()  # Store generated signals
        
        # Connect to data signals
        self.data.option_quote_updated.connect(self.on_quote_update)
        
    def on_quote_update(self, quote: dict):
        """Process each new quote - main strategy logic"""
        # 1. Extract option details (strike, expiration, type)
        # 2. Calculate Greeks if needed
        # 3. Check strategy conditions
        # 4. Generate signals
        # 5. Execute orders via Tradier
        pass
        
    def calculate_greeks(self, option_data: dict) -> dict:
        """Calculate option Greeks (can use py_vollib or similar)"""
        # Implementation using py_vollib or custom calculations
        pass
        
    def execute_signal(self, signal: dict):
        """Place order based on signal"""
        order_params = {
            'symbol': 'SPY',
            'option_symbol': signal['option_symbol'],
            'side': signal['side'],  # 'buy_to_open', 'sell_to_close', etc.
            'quantity': signal['quantity'],
            'type': 'limit',
            'price': signal['limit_price'],
            'duration': 'day'
        }
        
        result = self.tradier.place_order(order_params)
        if result.get('order', {}).get('id'):
            self.logger.info(f"Order placed: {result}")
        else:
            self.logger.error(f"Order failed: {result}")
UI Components Specifications
Main Window (ui/main_window.py)
python
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self, data_manager, tradier_client):
        super().__init__()
        self.data = data_manager
        self.tradier = tradier_client
        
        self.setWindowTitle("SPY Options Trading System")
        self.setGeometry(100, 100, 1600, 900)
        
        # Central widget with layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        # Left panel - Account info and positions
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.account_view = AccountView()
        left_layout.addWidget(self.account_view)
        
        # Center panel - Chart and options chain
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        self.chart = RealTimeChart()
        self.options_chain = OptionsChainWidget()
        center_layout.addWidget(self.chart)
        center_layout.addWidget(self.options_chain)
        
        # Right panel - Order entry
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.order_entry = OrderEntryWidget()
        right_layout.addWidget(self.order_entry)
        
        # Add panels to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(center_panel, 3)
        layout.addWidget(right_panel, 1)
        
        # Connect data signals to UI updates
        self.data.account_updated.connect(self.account_view.update_account)
        self.data.option_quote_updated.connect(self.options_chain.update_quote)
        self.data.chart_data_updated.connect(self.chart.update_data)
Real-time Chart Widget (ui/widgets/chart_widget.py)
python
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout
import pandas as pd
import numpy as np

class RealTimeChart(QWidget):
    """Real-time price chart using pyqtgraph for performance"""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Price')
        self.plot_widget.setLabel('bottom', 'Time')
        self.plot_widget.showGrid(x=True, y=True)
        
        # Create curves
        self.price_curve = self.plot_widget.plot(pen='y')
        self.bid_curve = self.plot_widget.plot(pen='g')
        self.ask_curve = self.plot_widget.plot(pen='r')
        
        layout.addWidget(self.plot_widget)
        
        self.data_buffer = pd.DataFrame(columns=['timestamp', 'price', 'bid', 'ask'])
        self.max_points = 1000
        
    def update_data(self, new_data: pd.DataFrame):
        """Update chart with new data points"""
        # Append new data to buffer
        self.data_buffer = pd.concat([self.data_buffer, new_data]).tail(self.max_points)
        
        # Update curves
        if not self.data_buffer.empty:
            x = range(len(self.data_buffer))
            self.price_curve.setData(x, self.data_buffer['price'].values)
            self.bid_curve.setData(x, self.data_buffer['bid'].values)
            self.ask_curve.setData(x, self.data_buffer['ask'].values)
Options Chain Widget (ui/widgets/options_chain.py)
python
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
import pandas as pd

class OptionsChainWidget(QTableWidget):
    """Interactive options chain display"""
    
    def __init__(self):
        super().__init__()
        self.setColumnCount(12)
        self.setHorizontalHeaderLabels([
            'Expiration', 'Strike', 'Type',
            'Bid', 'Ask', 'Last',
            'Delta', 'Gamma', 'Theta', 'Vega',
            'Volume', 'OI'
        ])
        
        # Stretch columns
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        # Enable sorting
        self.setSortingEnabled(True)
        
    def update_chain(self, chain_df: pd.DataFrame):
        """Update the options chain display"""
        self.setRowCount(len(chain_df))
        
        for row, (idx, option) in enumerate(chain_df.iterrows()):
            # Fill data
            self.setItem(row, 0, QTableWidgetItem(str(option.get('expiration', ''))))
            self.setItem(row, 1, QTableWidgetItem(str(option.get('strike', ''))))
            self.setItem(row, 2, QTableWidgetItem(option.get('option_type', '')))
            
            # Color code bid/ask
            bid_item = QTableWidgetItem(f"{option.get('bid', 0):.2f}")
            if option.get('bid', 0) > 0:
                bid_item.setForeground(Qt.green)
            self.setItem(row, 3, bid_item)
            
            ask_item = QTableWidgetItem(f"{option.get('ask', 0):.2f}")
            if option.get('ask', 0) > 0:
                ask_item.setForeground(Qt.red)
            self.setItem(row, 4, ask_item)
            
            self.setItem(row, 5, QTableWidgetItem(f"{option.get('last', 0):.2f}"))
            self.setItem(row, 6, QTableWidgetItem(f"{option.get('delta', 0):.3f}"))
            self.setItem(row, 7, QTableWidgetItem(f"{option.get('gamma', 0):.4f}"))
            self.setItem(row, 8, QTableWidgetItem(f"{option.get('theta', 0):.3f}"))
            self.setItem(row, 9, QTableWidgetItem(f"{option.get('vega', 0):.3f}"))
            self.setItem(row, 10, QTableWidgetItem(str(option.get('volume', 0))))
            self.setItem(row, 11, QTableWidgetItem(str(option.get('open_interest', 0))))
    
    def update_quote(self, quote: dict):
        """Update a single quote in real-time"""
        # Find the row for this option symbol and update bid/ask
        pass
Ubuntu/Wayland Specifics
Wayland Compatibility
python
import os
from PySide6.QtGui import QGuiApplication

# Ensure Wayland platform plugin is available
os.environ['QT_QPA_PLATFORM'] = 'wayland'

# Or use xcb as fallback
if 'wayland' not in os.environ.get('XDG_SESSION_TYPE', ''):
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
Dependencies (requirements.txt)
txt
# Core
pyside6==6.6.0
python-dotenv==1.0.0

# Data
databento>=0.30.0
pandas>=2.0.0
numpy>=1.24.0
pyarrow>=12.0.0  # For efficient data transfer

# Broker API
requests>=2.31.0
websocket-client>=1.6.0

# Calculations
py_vollib>=1.0.1  # Options pricing and Greeks
scipy>=1.11.0     # Numerical methods

# Visualization
pyqtgraph>=0.13.0
matplotlib>=3.7.0  # For static charts if needed

# Utilities
pydantic>=2.0.0   # Data validation
loguru>=0.7.0     # Logging
aiofiles>=23.1.0  # Async file I/O
Testing Strategy
Unit Tests
python
# tests/test_databento_client.py
# tests/test_tradier_client.py
# tests/test_data_manager.py
# tests/test_strategy.py
Integration Tests
python
# tests/integration/test_live_data_flow.py
# Test that data flows from Databento -> DataManager -> UI
Mock Testing
Create mock clients for testing without live connections:

python
# tests/mocks/mock_databento.py
# tests/mocks/mock_tradier.py
Configuration (config/settings.py)
python
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Tradier
    TRADIER_TOKEN = os.getenv('TRADIER_TOKEN')
    TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID')
    TRADIER_PAPER = os.getenv('TRADIER_PAPER', 'True').lower() == 'true'
    
    # Databento
    DATABENTO_API_KEY = os.getenv('DATABENTO_API_KEY')
    DATABENTO_DATASET = os.getenv('DATABENTO_DATASET', 'OPRA')  # Options feed
    
    # Trading
    SPY_SYMBOL = 'SPY'
    MAX_POSITION_SIZE = int(os.getenv('MAX_POSITION_SIZE', '10'))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% of account
    
    # Paths
    DATA_DIR = os.getenv('DATA_DIR', './data')
    LOG_DIR = os.getenv('LOG_DIR', './logs')
    
    # Performance
    UPDATE_INTERVAL_MS = int(os.getenv('UPDATE_INTERVAL_MS', '100'))  # UI updates
Deployment Instructions for Coding Agent
Setup Environment

bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Configure API Keys

Create .env file with your credentials

Test connections with provided test scripts

Run Application

bash
python main.py
Monitoring

Logs written to logs/ directory

Use loguru for structured logging with rotation

This specification provides a complete foundation for your coding agent to build a robust, real-time options trading system integrating Tradier and Databento with a professional PySide6 interface on Ubuntu/Wayland.


