#!/usr/bin/env python3
"""
SPYDER Dashboard with Integrated Heartbeat
Prevents IB Gateway disconnections
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QTextEdit, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen
from ib_async import IB, Stock
from datetime import datetime

CLIENT_ID = 123  # Your working client ID

class IBWorkerWithHeartbeat(QObject):
    """IB worker with heartbeat to prevent disconnections"""
    
    connected = pyqtSignal(bool)
    status_update = pyqtSignal(str)
    price_update = pyqtSignal(str, float, float, float)
    heartbeat_sent = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.ib = None
        self.tickers = {}
        self.update_timer = None
        self.heartbeat_timer = None
        
    def connect_to_ib(self):
        """Connect to IB Gateway"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 4002, clientId=CLIENT_ID, timeout=10)
            
            if self.ib.isConnected():
                self.status_update.emit(f"✅ Connected! Account: {self.ib.managedAccounts()}")
                self.connected.emit(True)
                
                # Subscribe to symbols
                symbols = ['SPY', 'QQQ', 'IWM']
                for symbol in symbols:
                    self.subscribe_symbol(symbol)
                
                # Start update timer
                self.update_timer = QTimer()
                self.update_timer.timeout.connect(self.update_prices)
                self.update_timer.start(500)
                
                # Start heartbeat timer - every 2 minutes
                self.heartbeat_timer = QTimer()
                self.heartbeat_timer.timeout.connect(self.send_heartbeat)
                self.heartbeat_timer.start(120000)  # 120 seconds
                
                # Send initial heartbeat
                self.send_heartbeat()
                
                return True
        except Exception as e:
            self.status_update.emit(f"❌ Error: {e}")
            self.connected.emit(False)
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to keep connection alive"""
        if self.ib and self.ib.isConnected():
            try:
                # Request current time as heartbeat
                server_time = self.ib.reqCurrentTime()
                time_str = datetime.fromtimestamp(server_time).strftime('%H:%M:%S')
                self.heartbeat_sent.emit(f"💓 Heartbeat sent - Server time: {time_str}")
                self.status_update.emit(f"💓 Heartbeat at {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                self.status_update.emit(f"⚠️ Heartbeat failed: {e}")
    
    def subscribe_symbol(self, symbol):
        """Subscribe to a symbol"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.tickers[symbol] = ticker
            self.status_update.emit(f"📊 Subscribed to {symbol}")
            self.ib.sleep(0.1)
        except Exception as e:
            self.status_update.emit(f"❌ Error subscribing to {symbol}: {e}")
    
    def update_prices(self):
        """Emit price updates"""
        for symbol, ticker in self.tickers.items():
            last = ticker.last if ticker.last and ticker.last > 0 else 0
            bid = ticker.bid if ticker.bid and ticker.bid > 0 else 0
            ask = ticker.ask if ticker.ask and ticker.ask > 0 else 0
            
            if last > 0 or bid > 0 or ask > 0:
                if last == 0 and bid > 0 and ask > 0:
                    last = (bid + ask) / 2
                elif last == 0 and bid > 0:
                    last = bid
                elif last == 0 and ask > 0:
                    last = ask
                    
                self.price_update.emit(symbol, last, bid, ask)
    
    def disconnect(self):
        """Disconnect from IB"""
        if self.update_timer:
            self.update_timer.stop()
            self.update_timer = None
            
        if self.heartbeat_timer:
            self.heartbeat_timer.stop()
            self.heartbeat_timer = None
            
        if self.ib and self.ib.isConnected():
            for ticker in self.tickers.values():
                try:
                    self.ib.cancelMktData(ticker)
                except:
                    pass
            self.ib.disconnect()
            self.ib = None
            self.tickers.clear()
            self.connected.emit(False)

class DashboardWithHeartbeat(QMainWindow):
    """Dashboard with integrated heartbeat"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.worker_thread = None
        self.heartbeat_count = 0
        self.setup_ui()
        self.auto_connect()
        
    def setup_ui(self):
        """Create UI"""
        self.setWindowTitle("SPYDER - Dashboard with Heartbeat")
        self.setGeometry(100, 100, 900, 700)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel { color: white; }
            QPushButton {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #555;
                padding: 8px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
            QTextEdit {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #555;
                font-family: monospace;
                font-size: 12px;
            }
            QGroupBox {
                color: white;
                border: 1px solid #555;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTableWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #555;
                gridline-color: #444;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
        """)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Title
        title = QLabel("SPYDER TRADING DASHBOARD")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Status section
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: Connecting...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 16))
        status_layout.addWidget(self.status_label)
        
        # Heartbeat indicator
        self.heartbeat_label = QLabel("💓 Heartbeats: 0")
        self.heartbeat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heartbeat_label.setFont(QFont("Arial", 14))
        self.heartbeat_label.setStyleSheet("color: #00ff41;")
        status_layout.addWidget(self.heartbeat_label)
        
        layout.addLayout(status_layout)
        
        # Market data table
        market_group = QGroupBox("Market Data")
        market_layout = QVBoxLayout()
        
        self.market_table = QTableWidget(3, 5)
        self.market_table.setHorizontalHeaderLabels(["Symbol", "Last", "Bid", "Ask", "Time"])
        
        # Set column widths
        self.market_table.setColumnWidth(0, 100)
        self.market_table.setColumnWidth(1, 120)
        self.market_table.setColumnWidth(2, 120)
        self.market_table.setColumnWidth(3, 120)
        self.market_table.setColumnWidth(4, 150)
        
        # Add symbol rows
        symbols = ['SPY', 'QQQ', 'IWM']
        for i, symbol in enumerate(symbols):
            self.market_table.setItem(i, 0, QTableWidgetItem(symbol))
            for j in range(1, 5):
                item = QTableWidgetItem("---")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.market_table.setItem(i, j, item)
        
        market_layout.addWidget(self.market_table)
        market_group.setLayout(market_layout)
        layout.addWidget(market_group)
        
        # Log
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        log_layout.addWidget(self.log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Disconnect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.connect_btn.setMinimumHeight(40)
        button_layout.addWidget(self.connect_btn)
        
        self.heartbeat_btn = QPushButton("Send Heartbeat Now")
        self.heartbeat_btn.clicked.connect(self.force_heartbeat)
        self.heartbeat_btn.setMinimumHeight(40)
        button_layout.addWidget(self.heartbeat_btn)
        
        layout.addLayout(button_layout)
        
        # Info label
        info_label = QLabel("💡 Heartbeat sent every 2 minutes to prevent disconnection")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(info_label)
    
    def auto_connect(self):
        """Auto connect on startup"""
        self.log_message("Starting IB connection with heartbeat...")
        self.start_worker()
    
    def start_worker(self):
        """Start worker thread"""
        self.worker_thread = QThread()
        self.worker = IBWorkerWithHeartbeat()
        self.worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker.connected.connect(self.on_connected)
        self.worker.status_update.connect(self.log_message)
        self.worker.price_update.connect(self.on_price_update)
        self.worker.heartbeat_sent.connect(self.on_heartbeat_sent)
        
        # Start
        self.worker_thread.started.connect(self.worker.connect_to_ib)
        self.worker_thread.start()
    
    @pyqtSlot(bool)
    def on_connected(self, connected):
        """Handle connection status"""
        if connected:
            self.status_label.setText("Status: Connected ✅")
            self.status_label.setStyleSheet("color: #00ff41;")
            self.connect_btn.setText("Disconnect")
        else:
            self.status_label.setText("Status: Disconnected ❌")
            self.status_label.setStyleSheet("color: #ff1744;")
            self.connect_btn.setText("Connect")
    
    @pyqtSlot(str, float, float, float)
    def on_price_update(self, symbol, last, bid, ask):
        """Update price display"""
        for row in range(self.market_table.rowCount()):
            if self.market_table.item(row, 0).text() == symbol:
                if last > 0:
                    self.market_table.item(row, 1).setText(f"${last:.2f}")
                    self.market_table.item(row, 1).setForeground(Qt.GlobalColor.green)
                
                if bid > 0:
                    self.market_table.item(row, 2).setText(f"${bid:.2f}")
                    self.market_table.item(row, 2).setForeground(Qt.GlobalColor.cyan)
                
                if ask > 0:
                    self.market_table.item(row, 3).setText(f"${ask:.2f}")
                    self.market_table.item(row, 3).setForeground(Qt.GlobalColor.yellow)
                
                self.market_table.item(row, 4).setText(
                    datetime.now().strftime("%H:%M:%S")
                )
                break
    
    @pyqtSlot(str)
    def on_heartbeat_sent(self, message):
        """Handle heartbeat sent"""
        self.heartbeat_count += 1
        self.heartbeat_label.setText(f"💓 Heartbeats: {self.heartbeat_count}")
        # Flash effect
        self.heartbeat_label.setStyleSheet("color: #ffff00;")
        QTimer.singleShot(500, lambda: self.heartbeat_label.setStyleSheet("color: #00ff41;"))
    
    def log_message(self, message):
        """Add to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"{timestamp} - {message}")
    
    def toggle_connection(self):
        """Connect or disconnect"""
        if self.worker:
            self.log_message("Disconnecting...")
            self.worker.disconnect()
            self.stop_worker()
        else:
            self.log_message("Reconnecting...")
            self.start_worker()
    
    def force_heartbeat(self):
        """Force send heartbeat"""
        if self.worker:
            self.log_message("Forcing heartbeat...")
            self.worker.send_heartbeat()
    
    def stop_worker(self):
        """Stop worker thread"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            if not self.worker_thread.wait(5000):
                self.worker_thread.terminate()
        self.worker = None
        self.worker_thread = None
        self.connect_btn.setText("Connect")
    
    def closeEvent(self, event):
        """Clean shutdown"""
        if self.worker:
            self.worker.disconnect()
        self.stop_worker()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    print("\n" + "="*60)
    print("SPYDER - Dashboard with Heartbeat")
    print("="*60)
    print("✅ Automatic heartbeat every 2 minutes")
    print("✅ Prevents IB Gateway disconnections")
    print("✅ Shows heartbeat counter")
    print("="*60 + "\n")
    
    dashboard = DashboardWithHeartbeat()
    dashboard.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
