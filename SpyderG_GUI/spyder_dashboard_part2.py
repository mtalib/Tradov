# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def is_market_hours():
    """Check if current time is within market hours (4:00 AM - 4:30 PM ET)"""
    eastern = pytz.timezone("US/Eastern")
    now_et = datetime.now(eastern).time()
    return MARKET_OPEN_TIME <= now_et <= MARKET_CLOSE_TIME


def check_ib_gateway_connection():
    """Check if IB Gateway is running - ENHANCED WITH DEBUG"""
    try:
        # Check paper trading port first (4002)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Increased timeout
        paper_result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()

        if paper_result == 0:
            print("✅ IB Gateway detected on port 4002 (PAPER)")
            return True, "PAPER (Port 4002)"

        # Check live trading port (4001)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Increased timeout
        live_result = sock.connect_ex(("127.0.0.1", 4001))
        sock.close()

        if live_result == 0:
            print("✅ IB Gateway detected on port 4001 (LIVE)")
            return True, "LIVE (Port 4001)"

        print("⌐ No IB Gateway detected on ports 4001 or 4002")
        return False, "No IB Gateway detected"

    except Exception as e:
        print(f"⌐ IB Gateway connection check failed: {e}")
        return False, f"Check failed: {e}"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    symbol: str
    last: float
    change: float
    change_pct: float
    timestamp: datetime


@dataclass
class GreekRisk:
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class ConnectionInfo:
    ib_connected: bool = False
    bridge_connected: bool = False
    connection_mode: str = "DISCONNECTED"
    market_data_status: str = "NONE"
    trading_active: bool = False
    last_update: Optional[datetime] = None
    last_successful_data: Optional[datetime] = None
    data_was_live: bool = False
    simulation_mode: bool = False


# ==============================================================================
# ENHANCED LOGGING CLASSES - REVERSE CHRONOLOGICAL ORDER
# ==============================================================================
class ReverseOrderLogger:
    """Logger that maintains entries in reverse chronological order (newest first)"""
    
    def __init__(self, max_entries: int = 150, update_callback=None):
        self.entries = []
        self.max_entries = max_entries
        self.update_callback = update_callback
    
    def add_entry(self, message: str):
        """Add new entry at the beginning (newest first)"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # Insert at beginning for reverse chronological order
        self.entries.insert(0, formatted_message)
        
        # Limit entries
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[:self.max_entries]
        
        # Notify UI to update
        if self.update_callback:
            self.update_callback()
    
    def get_recent_entries(self, count: int = 20) -> List[str]:
        """Get most recent entries (already in newest-first order)"""
        return self.entries[:count]

# ==============================================================================
# AUTO-RECONNECTION MANAGER
# ==============================================================================
class AutoReconnectionManager(QObject):
    """Manages auto-reconnection with exponential backoff"""
    
    reconnection_status_changed = Signal(str)
    connection_restored = Signal()
    
    def __init__(self):
        super().__init__()
        self.retry_count = 0
        self.max_retries = 10
        self.base_delay = 5
        self.max_delay = 60
        self.retry_timer = QTimer()
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self.attempt_reconnection)
        self.reconnection_active = False
        self.worker_ref = None
    
    def start_reconnection(self, worker):
        """Start reconnection attempts with exponential backoff"""
        if not is_market_hours():
            return
            
        self.worker_ref = worker
        self.reconnection_active = True
        self.retry_count = 0
        self._schedule_next_attempt()
    
    def stop_reconnection(self):
        """Stop reconnection attempts"""
        self.reconnection_active = False
        self.retry_timer.stop()
        self.retry_count = 0
    
    def _schedule_next_attempt(self):
        """Schedule next reconnection attempt with exponential backoff"""
        if not self.reconnection_active or not is_market_hours():
            return
            
        self.retry_count += 1
        
        if self.retry_count > self.max_retries:
            self.reconnection_status_changed.emit("❌ Auto-reconnection failed - maximum attempts reached")
            self.stop_reconnection()
            return
        
        delay = min(self.base_delay * (2 ** (self.retry_count - 1)), self.max_delay)
        
        self.reconnection_status_changed.emit(f"🔄 Reconnection attempt #{self.retry_count} in {delay}s...")
        self.retry_timer.start(delay * 1000)
    
    def attempt_reconnection(self):
        """Attempt to reconnect"""
        if not self.reconnection_active or not self.worker_ref:
            return
            
        self.reconnection_status_changed.emit(f"🔌 Attempting reconnection #{self.retry_count}...")
        
        connected, mode = check_ib_gateway_connection()
        
        if connected:
            self.reconnection_status_changed.emit(f"✅ Reconnection successful! ({mode})")
            self.connection_restored.emit()
            self.stop_reconnection()
            
            if self.worker_ref:
                self.worker_ref.ib_connected = True
                self.worker_ref.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
        else:
            self.reconnection_status_changed.emit(f"⚠️ Reconnection attempt #{self.retry_count} failed")
            self._schedule_next_attempt()


# ==============================================================================
# THREAD-SAFE MARKET DATA WORKER - FIXED CONNECTION DETECTION
# ==============================================================================
class ThreadSafeMarketDataWorker(QObject):
    """Thread-safe market data worker with real IB connection detection and heartbeat monitoring"""

    data_updated = Signal(dict)
    connection_status_changed = Signal(bool, str)
    market_data_status_changed = Signal(str)
    error_occurred = Signal(str)
    heartbeat_received = Signal(str)
    heartbeat_status_changed = Signal(str)  # New signal for heartbeat status
    log_message = Signal(str)  # New signal for log messages

    def __init__(self):
        super().__init__()
        self.logger = SpyderLogger.get_logger(__name__)

        # FIXED: Start with actual connection check instead of assuming connected
        self.ib_connected = False
        self._check_initial_connection()

        self.market_data = {}
        self.data_mutex = QMutex()
        self.client_id = CLIENT_ID
        self.market_hours = is_market_hours()

        # Initialize enhanced logging
        self.reverse_logger = ReverseOrderLogger(max_entries=200)
        
        # Initialize auto-reconnection manager
        self.auto_reconnector = AutoReconnectionManager()
        self.auto_reconnector.reconnection_status_changed.connect(self.log_message.emit)
        self.auto_reconnector.connection_restored.connect(self._on_connection_restored)

        # Data update timer (simulation)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_data)
        self.update_timer.start(2000)

        # Market hours check timer
        self.market_hours_timer = QTimer()
        self.market_hours_timer.timeout.connect(self._check_market_hours)
        self.market_hours_timer.start(60000)

        # HEARTBEAT MONITORING SYSTEM
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self._heartbeat_check)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)  # 30 seconds

        # Heartbeat warning timer (blue heart indicator)
        self.heartbeat_warning_timer = QTimer()
        self.heartbeat_warning_timer.timeout.connect(self._heartbeat_warning)

        self.last_data_update = {}
        self._init_simulation_data()

        print(f"🔧 Market Data Worker initialized with enhanced logging and auto-reconnection")
        print(
            f"📡 Initial IB Connection: {'CONNECTED' if self.ib_connected else 'DISCONNECTED'}"
        )
        print(f"📊 Market: {'OPEN' if self.market_hours else 'CLOSED'}")

    def _check_initial_connection(self):
        """Check actual IB Gateway connection on startup - ENHANCED WITH DEBUG"""
        try:
            print("🔍 Checking initial IB Gateway connection...")
            connected, mode = check_ib_gateway_connection()
            self.ib_connected = connected

            if connected:
                print(f"✅ IB Gateway detected: {mode}")
                # Emit log message instead of error
                self.log_message.emit(f"✅ IB Gateway detected at startup: {mode}")
            else:
                print(f"⌐ No IB Gateway connection detected")
                # Emit log message instead of error
                self.log_message.emit("⌐ No IB Gateway connection detected at startup")

        except Exception as e:
            print(f"⚠️ Connection check error: {e}")
            # Emit log message instead of error
            self.log_message.emit(f"⚠️ Initial connection check error: {e}")
            self.ib_connected = False

    def _on_connection_restored(self):
        """Handle connection restoration"""
        self.log_message.emit("🎉 Connection successfully restored via auto-reconnection")

    def _heartbeat_check(self):
        """30-second heartbeat check for IB Gateway connection"""
        try:
            # Check actual connection
            connected, mode = check_ib_gateway_connection()
            previous_status = self.ib_connected
            self.ib_connected = connected

            # Log to enhanced logger
            if connected:
                self.reverse_logger.add_entry(f"💚 Heartbeat: IB Gateway healthy ({mode})")
            else:
                self.reverse_logger.add_entry("💔 Heartbeat: IB Gateway connection lost")

            # Emit heartbeat status based on connection
            if connected:
                self.heartbeat_status_changed.emit("connected")  # Green heart
                if not previous_status:
                    # Connection restored
                    self.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: IB Gateway connection restored ({mode})"
                    )
                else:
                    self.heartbeat_received.emit(
                        f"💚 Heartbeat: IB Gateway healthy ({mode})"
                    )
                
                # Stop auto-reconnection if it was running
                if self.auto_reconnector.reconnection_active:
                    self.auto_reconnector.stop_reconnection()
                    
            else:
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                if previous_status:
                    # Connection lost - start auto-reconnection
                    self.connection_status_changed.emit(False, "IB DISCONNECTED")
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: IB Gateway connection lost"
                    )
                    
                    # Start auto-reconnection if during market hours
                    if is_market_hours():
                        self.auto_reconnector.start_reconnection(self)
                        
                else:
                    self.heartbeat_received.emit(
                        "💔 Heartbeat: IB Gateway still disconnected"
                    )

            # Start warning timer for blue heart (10 seconds before next check)
            self.heartbeat_warning_timer.start(HEARTBEAT_WARNING_TIME)

        except Exception as e:
            self.heartbeat_status_changed.emit("error")  # Red heart
            self.heartbeat_received.emit(f"💔 Heartbeat error: {e}")
            self.reverse_logger.add_entry(f"❌ Heartbeat error: {e}")

    def _heartbeat_warning(self):
        """Show blue heart 20 seconds before next heartbeat check"""
        self.heartbeat_status_changed.emit("warning")  # Blue heart
        self.heartbeat_warning_timer.stop()

    def _init_simulation_data(self):
        """Initialize simulation data with all symbols"""
        base_prices = {
            "SPY": 585.25,
            "SPX": 5850.75,
            "/ES": 5852.50,
            "VIX": 15.32,
            "VIX9D": 14.8,
            "VXV": 16.2,
            "VXMT": 17.5,
            "VVIX": 82.45,
            "UVXY": 22.18,
            "$TICK": 234,
            "$TRIN": 0.85,
            "$ADD": 1245,
            "CPC": 0.95,
            "PCALL": 0.88,
            "SKEW": 125.5,
            "DIA": 425.33,
            "QQQ": 485.92,
            "IWM": 225.18,
            "TLT": 92.45,
            "LQD": 105.32,
            "DXY": 103.25,
            "GLD": 195.67,
            "GEX": -2500000000,
            "DEX": 850000000,
            "OGL": 585.50,
            "DIX": 42.5,
            "SWAN": 1.85,
        }

        with QMutexLocker(self.data_mutex):
            for symbol, price in base_prices.items():
                self.market_data[symbol] = {
                    "symbol": symbol,
                    "last": price,
                    "change": 0,
                    "change_pct": 0,
                    "timestamp": datetime.now(),
                }
                self.last_data_update[symbol] = datetime.now()

    def _check_market_hours(self):
        """Check if market hours status has changed"""
        current_market_hours = is_market_hours()

        if current_market_hours != self.market_hours:
            self.market_hours = current_market_hours
            print(
                f"📊 Market hours changed: {'OPEN' if self.market_hours else 'CLOSED'}"
            )

            if not self.market_hours:
                # Market closed - stop auto-reconnection
                self.auto_reconnector.stop_reconnection()
                if self.ib_connected:
                    self.market_data_status_changed.emit("NONE")

    @Slot()
    def start(self):
        """Start the worker - FIXED TO EMIT PROPER INITIAL STATUS"""
        print("🚀 Starting Thread-Safe Market Data Worker with enhanced features...")

        # FIXED: Re-check connection at start and emit proper status
        try:
            connected, mode = check_ib_gateway_connection()
            self.ib_connected = connected

            if connected:
                self.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
                self.market_data_status_changed.emit("LIVE")
                self.heartbeat_status_changed.emit("connected")  # Green heart
                print(f"✅ IB Gateway connected at startup: {mode}")
                self.reverse_logger.add_entry(f"✅ Worker started - IB Gateway connected ({mode})")
            else:
                self.connection_status_changed.emit(False, "IB DISCONNECTED")
                self.market_data_status_changed.emit("NONE")
                self.heartbeat_status_changed.emit("disconnected")  # Red heart
                print("⌐ IB Gateway disconnected at startup")
                self.reverse_logger.add_entry("⌐ Worker started - IB Gateway disconnected")

        except Exception as e:
            print(f"⚠️ Startup connection check error: {e}")
            self.ib_connected = False
            self.connection_status_changed.emit(False, "IB DISCONNECTED")
            self.market_data_status_changed.emit("NONE")
            self.heartbeat_status_changed.emit("error")  # Red heart
            self.reverse_logger.add_entry(f"❌ Worker startup error: {e}")

    def _emit_data(self):
        """Emit current market data"""
        with QMutexLocker(self.data_mutex):
            data_copy = self.market_data.copy()

        self._update_simulation_data(data_copy)
        self.data_updated.emit(data_copy)

    def _update_simulation_data(self, data: dict):
        """Update simulation data with realistic market movements"""
        if not is_market_hours():
            return

        current_time = datetime.now()

        for symbol, market_info in data.items():
            if symbol not in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
                old_price = market_info["last"]
                change = random.uniform(-0.5, 0.5)
                new_price = old_price + change
                change_pct = (change / old_price * 100) if old_price != 0 else 0

                market_info.update(
                    {
                        "last": new_price,
                        "change": change,
                        "change_pct": change_pct,
                        "timestamp": current_time,
                    }
                )

            with QMutexLocker(self.data_mutex):
                self.last_data_update[symbol] = current_time

    def force_connect(self):
        """Manual connect - now checks actual connection"""
        print("🔥 Manual connect requested")
        if not is_market_hours():
            print("📊 Cannot connect - market is closed")
            return False

        # Check actual connection
        connected, mode = check_ib_gateway_connection()
        self.ib_connected = connected

        if connected:
            self.connection_status_changed.emit(True, f"IB CONNECTED ({mode})")
            self.market_data_status_changed.emit("LIVE")
            self.reverse_logger.add_entry(f"🔥 Manual connection successful ({mode})")
            # Stop auto-reconnection if running
            self.auto_reconnector.stop_reconnection()
            return True
        else:
            self.connection_status_changed.emit(False, "IB DISCONNECTED")
            self.market_data_status_changed.emit("NONE")
            self.reverse_logger.add_entry("❌ Manual connection failed")
            return False

    def force_disconnect(self):
        """Manual disconnect"""
        print("🔥 Manual disconnect requested")
        self.ib_connected = False
        self.connection_status_changed.emit(False, "IB DISCONNECTED")
        self.market_data_status_changed.emit("NONE")
        self.reverse_logger.add_entry("🔥 Manual disconnection")
        # Stop auto-reconnection
        self.auto_reconnector.stop_reconnection()

    def stop(self):
        """Stop worker and all timers"""
        print("🛑 Stopping worker with enhanced logging and auto-reconnection...")
        self.update_timer.stop()
        self.market_hours_timer.stop()
        self.heartbeat_timer.stop()
        self.heartbeat_warning_timer.stop()
        self.auto_reconnector.stop_reconnection()
        self.reverse_logger.add_entry("🛑 Market Data Worker stopped")