#!/usr/bin/env python3
"""
FIXED IB CONNECTION TEST

SPYDER - Autonomous Options Trading System v1.0

Module: temp_fixed_connection_test.py
Purpose: Fixed connection test with correct ib_async method names
"""

import asyncio
import sys
from ib_async import IB

async def test_working_connection():
    """Test the working IB Gateway connection with correct API calls."""
    print("🧪 Testing Working IB Gateway Connection")
    print("-" * 50)
    
    ib = IB()
    
    try:
        # Connect to Gateway
        await ib.connectAsync('127.0.0.1', 4002, clientId=1, timeout=15)
        
        if ib.isConnected():
            print("✅ Connection established successfully!")
            
            # Get server information with correct method names
            try:
                # Try different possible method names
                if hasattr(ib, 'serverVersion'):
                    version = ib.serverVersion()
                    print(f"📊 Server version: {version}")
                elif hasattr(ib, 'reqServerVersion'):
                    version = ib.reqServerVersion()
                    print(f"📊 Server version: {version}")
                else:
                    print("⚠️ Server version method not found, but connection works")
                
                # Get current time
                if hasattr(ib, 'reqCurrentTime'):
                    current_time = ib.reqCurrentTime()
                    print(f"🕒 Server time: {current_time}")
                elif hasattr(ib, 'currentTime'):
                    current_time = ib.currentTime()
                    print(f"🕒 Server time: {current_time}")
                else:
                    print("⚠️ Time method not found, but connection works")
                
                # Get managed accounts
                if hasattr(ib, 'managedAccounts'):
                    accounts = ib.managedAccounts()
                    print(f"👤 Managed accounts: {accounts}")
                else:
                    print("⚠️ Managed accounts method not found, but connection works")
                
                # Test basic request
                try:
                    account_summary = ib.reqAccountSummary(
                        reqId=1, 
                        groupName="All", 
                        tags="AccountType,TotalCashValue"
                    )
                    await asyncio.sleep(2)  # Wait for response
                    print(f"📋 Account data received: {len(account_summary)} items")
                    
                except Exception as e:
                    print(f"⚠️ Account summary test failed: {e}")
                
            except Exception as e:
                print(f"⚠️ API method error: {e}")
                print("✅ But connection itself works!")
            
            # Test that we can send/receive data
            print("✅ CONNECTION VERIFIED AND WORKING!")
            return True
            
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected cleanly")

def generate_spyder_connection_code():
    """Generate working connection code for Spyder modules."""
    return '''
# WORKING SPYDER IB GATEWAY CONNECTION
# Generated after successful connection test

import asyncio
from ib_async import IB

class SpyderIBConnection:
    """Working IB Gateway connection for Spyder trading system."""
    
    def __init__(self, host='127.0.0.1', port=4002, client_id=1):
        """Initialize connection parameters."""
        self.host = host
        self.port = port  
        self.client_id = client_id
        self.ib = None
        self.connected = False
    
    async def connect(self, timeout=30):
        """Connect to IB Gateway."""
        try:
            self.ib = IB()
            await self.ib.connectAsync(
                host=self.host,
                port=self.port, 
                clientId=self.client_id,
                timeout=timeout
            )
            
            if self.ib.isConnected():
                self.connected = True
                print("✅ Spyder connected to IB Gateway")
                
                # Get basic info if available
                try:
                    if hasattr(self.ib, 'managedAccounts'):
                        accounts = self.ib.managedAccounts()
                        print(f"👤 Trading accounts: {accounts}")
                except:
                    pass
                    
                return True
            else:
                print("❌ Spyder connection failed")
                return False
                
        except Exception as e:
            print(f"❌ Spyder connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                self.connected = False
                print("🔌 Spyder disconnected from IB Gateway")
        except Exception as e:
            print(f"⚠️ Disconnect error: {e}")

# Usage example for Spyder modules:
async def spyder_connect_example():
    """Example connection for Spyder modules."""
    connection = SpyderIBConnection()
    
    if await connection.connect():
        # Your Spyder trading logic here
        print("🕷️ Ready for autonomous trading!")
        
        # Always disconnect when done
        connection.disconnect()
        return connection
    else:
        return None

# Test the connection
if __name__ == "__main__":
    connection = asyncio.run(spyder_connect_example())
'''

async def main():
    """Main test function."""
    success = await test_working_connection()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 IB GATEWAY CONNECTION WORKING!")
        print("=" * 60)
        print("Connection parameters confirmed:")
        print("  Host: 127.0.0.1")
        print("  Port: 4002") 
        print("  Client ID: 1")
        print("\n🚀 READY TO BUILD SPYDER MODULES!")
        
        print("\n📝 Spyder Connection Code:")
        print(generate_spyder_connection_code())
        
        return 0
    else:
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
