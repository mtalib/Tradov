#!/usr/bin/env python3
"""
Detailed IBAPI connection test with verbose logging
"""

import sys
import time
import threading
from datetime import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import OrderId, TickerId
from ibapi.account_summary_tags import AccountSummaryTags

class DetailedIBKRTest(EClient, EWrapper):
    """Detailed IBAPI test with verbose logging"""
    
    def __init__(self, port=4002):
        EClient.__init__(self, self)
        self.port = port
        self.connected = False
        self.next_valid_id_received = False
        self.account_data = {}
        self.errors = []
        
    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        print(f"[{timestamp}] {message}")
        
    def nextValidId(self, orderId: OrderId):
        """Connection established successfully"""
        self.log(f"SUCCESS: nextValidId received: {orderId}")
        self.next_valid_id_received = True
        
        # Request account summary
        self.log("Requesting account summary...")
        self.reqAccountSummary(1, "All", AccountSummaryTags.AllTags)
        
    def connectAck(self):
        """Connection acknowledged"""
        self.log("Connection acknowledged by server")
        self.connected = True
        
    def connectionClosed(self):
        """Connection closed"""
        self.log("Connection closed by server")
        self.connected = False
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Account data received"""
        self.log(f"Account data: {account} | {tag}: {value} {currency}")
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account][tag] = {'value': value, 'currency': currency}
        
    def accountSummaryEnd(self, reqId: int):
        """Account summary complete"""
        self.log("Account summary completed successfully")
        self.disconnect()
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle errors with detailed logging"""
        error_msg = f"Error {errorCode}: {errorString}"
        if reqId != -1:
            error_msg = f"ReqID {reqId} - {error_msg}"
        if advancedOrderRejectJson:
            error_msg += f" | Advanced: {advancedOrderRejectJson}"
            
        self.log(f"ERROR: {error_msg}")
        self.errors.append((errorCode, errorString))
        
        # Critical errors that should stop the test
        if errorCode in [504, 502, 1100, 2104, 2106, 2110]:
            self.log(f"Critical error {errorCode} - stopping test")
            self.disconnect()
    
    def managedAccounts(self, accountsList: str):
        """Managed accounts received"""
        self.log(f"Managed accounts: {accountsList}")
    
    def run_detailed_test(self):
        """Run detailed connection test"""
        self.log(f"Starting detailed IBAPI test on port {self.port}")
        self.log("=" * 50)
        
        try:
            self.log(f"Attempting connection to 127.0.0.1:{self.port}")
            self.connect("127.0.0.1", self.port, clientId=1)
            
            # Start message loop
            self.log("Starting message processing thread...")
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()
            
            # Wait and monitor connection status
            for i in range(30):  # 30 second timeout
                time.sleep(1)
                
                if self.next_valid_id_received:
                    self.log("Connection fully established - waiting for data...")
                    # Wait for account data
                    time.sleep(10)
                    break
                elif self.errors:
                    self.log("Errors detected - stopping test")
                    break
                elif i % 5 == 0:
                    self.log(f"Still waiting for connection... ({i}s)")
            
            # Results
            self.log("=" * 50)
            self.log("TEST RESULTS:")
            
            if self.next_valid_id_received:
                self.log("STATUS: SUCCESS - Full connection established")
                self.log(f"Account data points: {sum(len(data) for data in self.account_data.values())}")
                for account, data in self.account_data.items():
                    self.log(f"  Account {account}: {len(data)} items")
                return True
            elif self.errors:
                self.log("STATUS: FAILED - Errors occurred")
                for code, msg in self.errors:
                    self.log(f"  Error {code}: {msg}")
                return False
            else:
                self.log("STATUS: TIMEOUT - No response from server")
                return False
                
        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            return False
        finally:
            try:
                self.disconnect()
            except:
                pass

def main():
    """Test both available ports with detailed logging"""
    print("Detailed IBKR IBAPI Connection Test")
    print("=" * 40)
    
    ports_to_test = [4002, 4001]
    success_count = 0
    
    for port in ports_to_test:
        print(f"\nTesting port {port}:")
        print("-" * 30)
        
        tester = DetailedIBKRTest(port)
        if tester.run_detailed_test():
            success_count += 1
        
        print()
    
    print("SUMMARY:")
    print(f"Successful connections: {success_count}/{len(ports_to_test)}")
    return success_count > 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)