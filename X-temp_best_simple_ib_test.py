#!/usr/bin/env python3
"""Simple IB Connection Test - Based on user's code"""

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

class TestWrapper(EWrapper, EClient):
    def __init__(self):  # Fixed the typo
        EClient.__init__(self, self)
        self.connected = False
        
    def nextValidId(self, orderId: int):
        print("✅ Connected. Next valid order ID:", orderId)
        self.connected = True
        # Don't disconnect immediately - let's see what happens
        
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"IB Message ({errorCode}): {errorString}")
        
    def connectAck(self):
        print("✅ Connection acknowledged")

print("Starting simple IB test...")
print("-" * 40)

app = TestWrapper()

def run():
    print("Starting message processing thread...")
    app.run()
    print("Message thread ended")

print("Connecting to IB Gateway on port 4002...")
app.connect("127.0.0.1", 4002, clientId=123)

if app.isConnected():
    print("✅ Socket connected successfully")
    
    # Start the message processing thread
    thread = threading.Thread(target=run)
    thread.start()
    
    # Wait a bit to see if we get connected
    print("Waiting for API handshake...")
    for i in range(10):
        if app.connected:
            break
        time.sleep(0.5)
        print(".", end="", flush=True)
    
    print()
    
    if app.connected:
        print("✅ SUCCESS! API is working!")
        app.disconnect()
    else:
        print("❌ No API response after 5 seconds")
        app.disconnect()
        
    thread.join(timeout=2)
else:
    print("❌ Failed to establish socket connection")

print("-" * 40)
print("Test complete")