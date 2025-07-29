# DASHBOARD INTEGRATION PATCH
# Apply these changes to SpyderG_GUI/SpyderG05_TradingDashboard.py

# ==============================================================================
# 1. UPDATE IMPORTS SECTION (around line 80-120)
# ==============================================================================

# FIND this section in SpyderG05_TradingDashboard.py:
# ==============================================================================
# LOCAL IMPORTS - MULTI-CLIENT BACKEND INTEGRATION (INVISIBLE TO USER)
# ==============================================================================

# REPLACE the imports with:

# Production SpyderB08 Multi-Client Integration
try:
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager,
        get_manager_instance,
        reset_manager_instance,
        OrderRequest,
        ClientPurpose
    )
    MULTI_CLIENT_AVAILABLE = True
    print("✅ Production Multi-Client Data Manager available")
except ImportError as e:
    MULTI_CLIENT_AVAILABLE = False
    print(f"⚠️ Production Multi-Client Data Manager not available: {e}")

# SpyderClient integration (fallback)
try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    SPYDER_CLIENT_AVAILABLE = True
    print("✅ SpyderClient available for fallback")
except ImportError as e:
    SPYDER_CLIENT_AVAILABLE = False
    print(f"⚠️ SpyderClient not available: {e}")

# ==============================================================================
# 2. REPLACE RealMarketDataWorker CLASS (around line 500-800)
# ==============================================================================

# FIND the class RealMarketDataWorker(QThread): and REPLACE entirely with:

class ProfessionalMarketDataWorker(QThread):
    """
    Professional Market Data Worker using Production SpyderB08
    
    Integrates the production MultiClientDataManager with Order Execution Priority
    into the dashboard seamlessly. Maintains exact same interface for UI compatibility.
    """
    
    # Signals for dashboard communication (SAME as before)
    data_updated = pyqtSignal(dict)
    connection_status_changed = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        
        # Professional multi-client manager
        self.manager = None
        self.running = False
        self.market_data = {}
        self.connection_status = False
        
        # Dashboard symbols (from existing structure)
        self.dashboard_symbols = [
            # S&P Core (Client 2 - Critical)
            'SPY', 'SPX', '/ES',
            # Volatility (Client 4 - High)
            'VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY',
            # Market Internals (Client 5 - High)
            '$TICK', '$TRIN', '$ADD', 'CPC', 'PCALL', 'SKEW',
            # Major Indices (Client 6 - High)
            'DIA', 'QQQ', 'IWM',
            # Bonds & Credit (Client 7 - Medium)
            'TLT', 'LQD',
            # Correlations (Client 7 - Medium)
            'DXY', 'GLD',
            # Custom Metrics (simulated)
            'GEX', 'DEX', 'OGL', 'DIX', 'SWAN'
        ]
        
        print("🏗️ Professional Market Data Worker initialized")
        print(f"   📊 Using production SpyderB08 with Order Execution Priority")
        print(f"   🎯 Will manage {len(self.dashboard_symbols)} symbols across multiple clients")

    def run(self):
        """Main execution thread using production multi-client manager"""
        print("🚀 Starting Professional Market Data Worker...")
        self.running = True
        
        # Initialize production multi-client manager
        if self.initialize_multi_client_system():
            print("✅ Production multi-client system initialized")
            
            # Subscribe to dashboard symbols
            self.subscribe_to_dashboard_symbols()
            
            # Main monitoring loop
            self.start_monitoring_loop()
        else:
            print("❌ Multi-client system failed - falling back to simulation")
            self.start_simulation_mode()

    def initialize_multi_client_system(self) -> bool:
        """Initialize the production multi-client manager"""
        try:
            if MULTI_CLIENT_AVAILABLE:
                # Get production manager instance
                self.manager = get_manager_instance()
                
                # Start the manager
                if self.manager.start():
                    self.connection_status = True
                    self.connection_status_changed.emit(True, "PROFESSIONAL MODE - Multi-Client Active")
                    
                    # Register data callback
                    self.register_data_callbacks()
                    
                    return True
                else:
                    print("❌ Failed to start multi-client manager")
                    return False
            else:
                print("⚠️ Multi-client manager not available")
                return False
                
        except Exception as e:
            print(f"❌ Error initializing multi-client system: {e}")
            return False

    def register_data_callbacks(self):
        """Register callbacks for market data updates"""
        try:
            for symbol in self.dashboard_symbols:
                # Skip custom metrics (these are simulated)
                if symbol in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
                    continue
                
                # Register callback for each symbol
                def create_callback(sym):
                    def callback(tick_data):
                        # Convert tick data to dashboard format
                        self.handle_tick_update(sym, tick_data)
                    return callback
                
                self.manager.subscribe_to_data(symbol, create_callback(symbol))
                
            print(f"✅ Registered callbacks for {len(self.dashboard_symbols)} symbols")
            
        except Exception as e:
            print(f"❌ Error registering callbacks: {e}")

    def handle_tick_update(self, symbol: str, tick_data):
        """Handle tick data updates from multi-client manager"""
        try:
            # Convert tick data to dashboard format
            if hasattr(tick_data, 'price'):
                # MarketDataTick object
                price = tick_data.price
                timestamp = tick_data.timestamp
            elif isinstance(tick_data, dict):
                # Dict format
                price = tick_data.get('price', 0.0)
                timestamp = tick_data.get('timestamp', datetime.now())
            else:
                # Raw tick data
                price = float(tick_data)
                timestamp = datetime.now()
            
            # Update market data
            if symbol not in self.market_data:
                self.market_data[symbol] = {
                    'symbol': symbol,
                    'last': 0.0,
                    'change': 0.0,
                    'change_pct': 0.0,
                    'timestamp': timestamp
                }
            
            # Calculate change
            old_price = self.market_data[symbol]['last']
            change = price - old_price if old_price > 0 else 0
            change_pct = (change / old_price) * 100 if old_price > 0 else 0
            
            # Update data
            self.market_data[symbol].update({
                'last': price,
                'change': change,
                'change_pct': change_pct,
                'timestamp': timestamp
            })
            
            # Show critical updates
            if symbol == 'SPY':
                print(f"💰 PROFESSIONAL UPDATE: {symbol} = ${price:.2f} (Multi-Client)")
            
        except Exception as e:
            print(f"❌ Error handling tick update for {symbol}: {e}")

    def subscribe_to_dashboard_symbols(self):
        """Subscribe to all dashboard symbols using production manager"""
        try:
            print("📡 Subscribing to dashboard symbols via production multi-client manager...")
            
            subscribed_count = 0
            for symbol in self.dashboard_symbols:
                # Skip custom metrics (simulate these)
                if symbol in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
                    continue
                
                try:
                    # Subscribe via production manager
                    # (callback registration handled in register_data_callbacks)
                    subscribed_count += 1
                    
                except Exception as e:
                    print(f"⚠️ Error subscribing to {symbol}: {e}")
            
            print(f"✅ Subscribed to {subscribed_count} symbols via production manager")
            
        except Exception as e:
            print(f"❌ Error subscribing to symbols: {e}")

    def start_monitoring_loop(self):
        """Start the main monitoring and data distribution loop"""
        print("🔄 Starting professional monitoring loop...")
        
        while self.running:
            try:
                # Get status from production manager
                if self.manager:
                    status = self.manager.get_status_summary()
                    
                    if status.get('is_running'):
                        # Update connection status
                        active_clients = status.get('active_clients', [])
                        total_clients = status.get('total_clients', 0)
                        order_execution_priority = status.get('order_execution_priority', False)
                        
                        if order_execution_priority:
                            status_msg = f"PROFESSIONAL MODE - Order Exec Priority + {len(active_clients)}/{total_clients} Clients"
                        else:
                            status_msg = f"PROFESSIONAL MODE - {len(active_clients)}/{total_clients} Clients"
                        
                        self.connection_status_changed.emit(True, status_msg)
                
                # Add custom metrics (simulated)
                self.update_custom_metrics()
                
                # Emit market data update
                if self.market_data:
                    self.data_updated.emit(self.market_data.copy())
                
                # Sleep based on fastest frequency (1s for critical data)
                self.msleep(1000)
                
            except Exception as e:
                print(f"❌ Error in professional monitoring loop: {e}")
                self.error_occurred.emit(str(e))
                self.msleep(5000)

    def update_custom_metrics(self):
        """Update custom metrics (GEX, DEX, OGL, DIX, SWAN) with simulation"""
        try:
            import random
            
            # Custom metrics data (simulated)
            custom_data = {
                'GEX': -2500000000 + random.uniform(-500000000, 500000000),  # -2.5B ± 500M
                'DEX': 850000000 + random.uniform(-100000000, 100000000),    # 850M ± 100M
                'OGL': 637.50 + random.uniform(-2.0, 2.0),                   # OGL ± $2
                'DIX': 42.5 + random.uniform(-5.0, 5.0),                     # DIX ± 5%
                'SWAN': 1.85 + random.uniform(-0.2, 0.2)                     # SWAN ± 0.2
            }
            
            for symbol, value in custom_data.items():
                if symbol not in self.market_data:
                    self.market_data[symbol] = {
                        'symbol': symbol,
                        'last': value,
                        'change': 0.0,
                        'change_pct': 0.0,
                        'timestamp': datetime.now()
                    }
                else:
                    old_value = self.market_data[symbol]['last']
                    change = value - old_value
                    change_pct = (change / old_value) * 100 if old_value != 0 else 0
                    
                    self.market_data[symbol].update({
                        'last': value,
                        'change': change,
                        'change_pct': change_pct,
                        'timestamp': datetime.now()
                    })
            
        except Exception as e:
            print(f"❌ Error updating custom metrics: {e}")

    def start_simulation_mode(self):
        """Fallback simulation mode"""
        print("🔄 Starting simulation mode...")
        self.connection_status_changed.emit(False, "SIMULATION MODE - Multi-Client Unavailable")
        
        while self.running:
            self.update_simulation_data()
            self.msleep(2000)

    def update_simulation_data(self):
        """Enhanced simulation data"""
        base_prices = {
            # S&P Core
            'SPY': 637.00, 'SPX': 6370.0, '/ES': 6372.0,
            # Volatility
            'VIX': 15.32, 'VIX9D': 14.8, 'VXV': 16.2, 'VXMT': 17.5,
            'VVIX': 82.45, 'UVXY': 22.18,
            # Major Indices
            'DIA': 449.87, 'QQQ': 568.55, 'IWM': 224.12,
            # Bonds & Credit
            'TLT': 85.88, 'LQD': 109.42,
            # Correlations
            'DXY': 103.25, 'GLD': 305.30,
            # Custom Metrics
            'GEX': -2500000000, 'DEX': 850000000, 'OGL': 637.50,
            'DIX': 42.5, 'SWAN': 1.85
        }
        
        import random
        for symbol, base_price in base_prices.items():
            change = random.uniform(-0.2, 0.2)
            change_pct = (change / base_price) * 100 if base_price != 0 else 0
            
            self.market_data[symbol] = {
                'symbol': symbol,
                'last': base_price + change,
                'change': change,
                'change_pct': change_pct,
                'timestamp': datetime.now()
            }
        
        self.data_updated.emit(self.market_data.copy())

    def submit_order(self, symbol: str, action: str, quantity: int, order_type: str = "MKT") -> int:
        """Submit order via production manager (Order Execution Client 1)"""
        try:
            if self.manager and MULTI_CLIENT_AVAILABLE:
                order = OrderRequest(
                    symbol=symbol,
                    action=action,
                    quantity=quantity,
                    order_type=order_type
                )
                
                def order_callback(status):
                    print(f"📋 Order callback: {status}")
                
                order_id = self.manager.submit_order(order, order_callback)
                print(f"⚡ Order {order_id} submitted via Client 1 (Order Execution Priority)")
                return order_id
            else:
                print("⚠️ Order submission not available - multi-client manager not active")
                return -1
                
        except Exception as e:
            print(f"❌ Error submitting order: {e}")
            return -1

    def stop(self):
        """Stop the professional market data worker"""
        print("🛑 Stopping Professional Market Data Worker...")
        self.running = False
        
        if self.manager:
            try:
                self.manager.stop()
                print("✅ Production multi-client manager stopped")
            except:
                pass

# ==============================================================================
# 3. UPDATE DASHBOARD CLASS __init__ METHOD (around line 1000-1100)
# ==============================================================================

# FIND the line in SpyderTradingDashboard.__init__ that initializes market_worker:
# self.market_worker = None

# REPLACE the entire setup_bridge_system method with:

    def setup_bridge_system(self):
        """Initialize the production multi-client bridge system (backend only)"""
        try:
            if MULTI_CLIENT_AVAILABLE:
                # Production multi-client system is handled by ProfessionalMarketDataWorker
                self.add_system_log("✅ Production multi-client bridge system available")
                self.connection_info.bridge_connected = True
            else:
                self.add_system_log("⚠️ Production multi-client system not available - using fallback mode")
                
        except Exception as e:
            self.logger.error(f"Error setting up bridge system: {e}")
            self.add_system_log(f"❌ Bridge setup error: {e}")

# ==============================================================================
# 4. UPDATE start_system METHOD (around line 1200-1300)
# ==============================================================================

# FIND the start_system method and REPLACE the market worker initialization with:

    def start_system(self):
        """Handle start system button click (Enhanced with production multi-client backend)"""
        # SpyderT09 original functionality
        self.ib_connected = True
        self.update_connection_status()
        self.add_system_log("System started - Connected to IB Gateway")
        self.add_automation_log("System started - Autonomous AI Engine initializing")
        
        # Production multi-client backend integration
        if not self.market_worker or not self.market_worker.isRunning():
            # Use ProfessionalMarketDataWorker with production SpyderB08
            self.market_worker = ProfessionalMarketDataWorker()
            self.market_worker.data_updated.connect(self.on_market_data_updated)
            self.market_worker.connection_status_changed.connect(self.on_connection_status_changed)
            self.market_worker.error_occurred.connect(self.on_market_error)
            self.market_worker.start()
            
            self.add_system_log("📊 Production Multi-Client System started")
            self.add_system_log("🏆 Order Execution Priority (Client 1) activated")
        
        print("✅ Starting IB Gateway connection with production multi-client backend...")

# ==============================================================================
# 5. ADD ORDER EXECUTION METHOD (add this new method to SpyderTradingDashboard class)
# ==============================================================================

    def submit_order(self, symbol: str, action: str, quantity: int, order_type: str = "MKT") -> int:
        """Submit order via production multi-client system (Client 1 priority)"""
        try:
            if self.market_worker and hasattr(self.market_worker, 'submit_order'):
                order_id = self.market_worker.submit_order(symbol, action, quantity, order_type)
                
                if order_id > 0:
                    self.add_system_log(f"⚡ Order {order_id} submitted: {action} {quantity} {symbol}")
                    self.add_automation_log(f"Order execution via Client 1 (highest priority)")
                    return order_id
                else:
                    self.add_system_log(f"❌ Order submission failed: {action} {quantity} {symbol}")
                    return -1
            else:
                self.add_system_log("⚠️ Order execution not available - system not ready")
                return -1
                
        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            self.add_system_log(f"❌ Order submission error: {e}")
            return -1