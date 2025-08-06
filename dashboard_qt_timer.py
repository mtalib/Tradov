#!/usr/bin/env python3
"""Dashboard using QTimer instead of threads - avoids hanging"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import QTimer, pyqtSlot
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

class IBClient(EWrapper, EClient):
    def __init__(self, dashboard):
        EClient.__init__(self, self)
        self.dashboard = dashboard
        
    def nextValidId(self, orderId):
        print(f"✅ Connected! Order ID: {orderId}")
        self.dashboard.on_connected()
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        if errorCode == 2104:
            print("✅ Market data farm connected")
        else:
            print(f"IB {errorCode}: {errorString}")
            
    def tickPrice(self, reqId, tickType, price, attrib):
        self.dashboard.on_price(reqId, price)

class TimerDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ib = None
        self.connected = False
        self.setup_ui()
        self.setup_ib()
        
    def setup_ui(self):
        self.setWindowTitle("SPYDER - Timer Based Dashboard")
        self.setGeometry(100, 100, 600, 400)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("font-size: 20px; padding: 20px;")
        layout.addWidget(self.status_label)
        
        self.spy_label = QLabel("SPY: ---")
        self.spy_label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.spy_label)
        
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        layout.addWidget(quit_btn)
        
        layout.addStretch()
        central.setLayout(layout)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel { color: white; }
            QPushButton { 
                background-color: #333; 
                color: white; 
                border: 1px solid #555; 
                padding: 10px;
            }
        """)
        
    def setup_ib(self):
        """Setup IB connection using QTimer instead of threads"""
        self.ib = IBClient(self)
        
        # Connect to IB
        print("Connecting to IB Gateway...")
        self.ib.connect("127.0.0.1", 4002, 11)  # Client ID 11
        
        # Use QTimer to process IB messages
        self.ib_timer = QTimer()
        self.ib_timer.timeout.connect(self.process_ib_messages)
        self.ib_timer.start(50)  # Process every 50ms
        
        self.status_label.setText("Connecting...")
        
    @pyqtSlot()
    def process_ib_messages(self):
        """Process IB messages in the main thread"""
        if self.ib and self.ib.isConnected():
            self.ib.run()  # This processes one message
            
    def on_connected(self):
        """Called when IB connects"""
        self.connected = True
        self.status_label.setText("✅ Connected to IB Gateway")
        self.status_label.setStyleSheet("color: #00ff00; font-size: 20px; padding: 20px;")
        
        # Subscribe to SPY
        QTimer.singleShot(1000, self.subscribe_spy)
        
    def subscribe_spy(self):
        """Subscribe to SPY data"""
        if self.connected:
            contract = Contract()
            contract.symbol = "SPY"
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            print("Subscribing to SPY...")
            self.ib.reqMktData(1, contract, "", False, False, [])
            
    def on_price(self, reqId, price):
        """Update price display"""
        if reqId == 1:  # SPY
            self.spy_label.setText(f"SPY: ${price:.2f}")
            
    def closeEvent(self, event):
        """Clean shutdown"""
        if self.ib_timer:
            self.ib_timer.stop()
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    print("="*50)
    print("TIMER-BASED DASHBOARD")
    print("="*50)
    print("This version uses QTimer instead of threads")
    print("Should not hang or freeze")
    print("="*50)
    
    dashboard = TimerDashboard()
    dashboard.show()
    
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())