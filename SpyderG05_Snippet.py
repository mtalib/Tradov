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
