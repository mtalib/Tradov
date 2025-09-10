#!/usr/bin/env python3
"""
Temporary IBAPI-only test script
Exactly what IBKR support requested - raw IBAPI test
"""

import sys
import time
import threading
from datetime import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import OrderId, TickerId
from ibapi.account_summary_tags import AccountSummaryTags

# Test ports (IBKR typically uses these)
TEST_PORTS = [7496, 4002, 4001, 7497]

class IBKRTest(EClient, EWrapper):
    """IBKR Support Test - Raw IBAPI as requested"""
    
    def __init__(self, port=7496):
        EClient.__init__(self, self)
        self.port = port
        self.account_data = {}
        self.connection_established = False
        self.test_complete = False
        self.error_occurred = False
        self.error_details = ""
        self.start_time = None
        
    def nextValidId(self, orderId: OrderId):
        """Called when connection is established"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection established. Next valid order ID: {orderId}")
        self.connection_established = True
        
        # Request account summary as per IBKR test script
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Requesting account summary...")
        self.reqAccountSummary(
            reqId=1,
            groupName="All",
            tags=AccountSummaryTags.AllTags
        )
    
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Handle account summary data"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Account: {account}, Tag: {tag}, Value: {value}, Currency: {currency}")
        
        # Store account data
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account][tag] = {'value': value, 'currency': currency}
    
    def accountSummaryEnd(self, reqId: int):
        """Called when account summary is complete"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Account summary complete for request {reqId}")
        self.test_complete = True
        
        # Disconnect gracefully
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Disconnecting...")
        self.disconnect()
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle connection errors"""
        error_msg = f"Error - ReqID: {reqId}, Code: {errorCode}, Message: {errorString}"
        if advancedOrderRejectJson:
            error_msg += f", Advanced: {advancedOrderRejectJson}"
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
        
        self.error_occurred = True
        self.error_details = f"Code {errorCode}: {errorString}"
        
        # For critical connection errors, mark test as complete
        if errorCode in [504, 502, 1100, 2104]:
            self.test_complete = True
    
    def run_test(self, timeout=30):
        """Run the IBAPI test"""
        print(f"Starting IBAPI test on port {self.port}")
        print(f"Connecting to 127.0.0.1:{self.port}...")
        
        self.start_time = time.time()
        
        try:
            # Connect to IB Gateway
            self.connect("127.0.0.1", self.port, 0)
            
            # Start the message processing loop in a separate thread
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()
            
            # Wait for test completion or timeout
            elapsed = 0
            while elapsed < timeout and not self.test_complete:
                time.sleep(0.1)
                elapsed = time.time() - self.start_time
            
            # Results
            duration = time.time() - self.start_time
            
            if self.test_complete and not self.error_occurred:
                print(f"\nSUCCESS: Test completed in {duration:.2f}s")
                print(f"Account data retrieved: {len(self.account_data)} accounts")
                for account, data in self.account_data.items():
                    print(f"  Account {account}: {len(data)} data points")
                return True
                
            elif self.error_occurred:
                print(f"\nFAILED: {self.error_details}")
                print(f"Test duration: {duration:.2f}s")
                return False
                
            else:
                print(f"\nTIMEOUT: Test timed out after {timeout} seconds")
                return False
            
        except Exception as e:
            print(f"\nEXCEPTION: {str(e)}")
            return False
        
        finally:
            try:
                self.disconnect()
            except:
                pass

def test_port_connectivity(port):
    """Test if port is reachable"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", port))
            return result == 0
    except:
        return False

def main():
    """Run IBAPI tests on available ports"""
    print("IBKR Support Test - Raw IBAPI")
    print("=" * 40)
    print(f"Test time: {datetime.now()}")
    print()
    
    # Check which ports are available
    available_ports = []
    for port in TEST_PORTS:
        if test_port_connectivity(port):
            available_ports.append(port)
            print(f"Port {port}: AVAILABLE")
        else:
            print(f"Port {port}: NOT AVAILABLE")
    
    if not available_ports:
        print("\nNo IB Gateway ports are available!")
        print("Please start IB Gateway/TWS and try again.")
        return False
    
    print(f"\nTesting available ports: {available_ports}")
    print("-" * 40)
    
    # Test each available port
    success_count = 0
    for port in available_ports:
        print(f"\nTesting port {port}:")
        print("-" * 20)
        
        tester = IBKRTest(port)
        if tester.run_test():
            success_count += 1
        
        print()
    
    print("=" * 40)
    print("FINAL RESULTS:")
    print(f"Ports tested: {len(available_ports)}")
    print(f"Successful connections: {success_count}")
    
    if success_count > 0:
        print("SUCCESS: IBAPI connection working!")
        print("This confirms your IB Gateway is accessible via raw IBAPI.")
    else:
        print("FAILED: No successful IBAPI connections.")
        print("Send these results to IBKR support.")
    
    return success_count > 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)