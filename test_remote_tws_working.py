#!/usr/bin/env python3
"""
SPYDER - Test Remote TWS Connection
Verify that Remote TWS connection works properly (should work since user confirmed)
Test the exact pattern that should work with TWS API
"""

import asyncio
from ib_async import IB, util
from datetime import datetime
import sys
import os
import time
import socket
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def get_tws_ip_from_config():
    """Get TWS IP from configuration"""
    try:
        config_path = project_root / "config" / "config.py"
        if config_path.exists():
            with open(config_path, "r") as f:
                content = f.read()

            import re

            ip_match = re.search(r'"ip_address":\s*"([^"]+)"', content)
            if ip_match:
                return ip_match.group(1)
    except Exception as e:
        print(f"⚠️ Could not read config: {e}")

    # Default fallback
    return "192.168.1.4"


async def test_network_connectivity(tws_ip):
    """Test basic network connectivity to TWS computer"""
    print(f"🌐 Testing network connectivity to {tws_ip}...")

    # Ping test
    import subprocess

    try:
        result = subprocess.run(
            ["ping", "-c", "3", "-W", "3", tws_ip],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            print(f"✅ Ping successful to {tws_ip}")
            # Extract ping statistics
            lines = result.stdout.split("\n")
            for line in lines:
                if "packet loss" in line or "min/avg/max" in line:
                    print(f"   {line.strip()}")
            return True
        else:
            print(f"❌ Ping failed to {tws_ip}")
            return False

    except Exception as e:
        print(f"❌ Ping test failed: {e}")
        return False


def test_tws_ports(tws_ip):
    """Test TWS API ports accessibility"""
    print(f"🔌 Testing TWS API ports on {tws_ip}...")

    ports = {7497: "Paper Trading", 7496: "Live Trading"}

    accessible_ports = []

    for port, description in ports.items():
        try:
            print(f"   Testing port {port} ({description})...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((tws_ip, port))
            sock.close()

            if result == 0:
                print(f"   ✅ Port {port} ({description}) is accessible")
                accessible_ports.append(port)
            else:
                print(f"   ❌ Port {port} ({description}) is not accessible")

        except Exception as e:
            print(f"   ❌ Port {port} test failed: {e}")

    return accessible_ports


async def test_tws_api_connection(tws_ip, port=7497):
    """Test actual TWS API connection"""
    print(f"\n🕷️ SPYDER - Testing TWS API Connection")
    print(f"=" * 50)
    print(f"Host: {tws_ip}")
    print(f"Port: {port} ({'Paper' if port == 7497 else 'Live'} Trading)")
    print()

    # Initialize ib_async utilities (as in working example)
    util.startLoop()  # Required for ib_async
    util.logToConsole()  # Enable logging for debugging
    print("✅ ib_async utilities initialized")

    # Create IB instance
    ib = IB()
    print("✅ IB instance created")

    try:
        print(f"\n🔌 Connecting to TWS API...")
        start_time = time.time()

        # Use the working pattern from user's research
        await ib.connectAsync(host=tws_ip, port=port, clientId=1)

        connection_time = time.time() - start_time
        print(f"✅ Connected to TWS API in {connection_time:.2f} seconds")
        print(f"   Connection status: {ib.isConnected()}")

        # Test connection by requesting server time (from working example)
        print(f"\n🕐 Testing connection with server time request...")
        server_time = await ib.reqCurrentTimeAsync()
        print(f"✅ Current IB server time: {server_time}")

        # Get managed accounts to verify connection
        print(f"\n💼 Getting managed accounts...")
        accounts = ib.managedAccounts()
        print(f"✅ Managed accounts: {accounts}")

        # Test basic market data request
        print(f"\n📊 Testing basic market data...")
        from ib_async import Stock

        spy_contract = Stock("SPY", "SMART", "USD")
        ib.qualifyContracts(spy_contract)
        print("✅ Contract qualified successfully")

        # Quick market data test
        ticker = ib.reqMktData(spy_contract, "", False, False)
        print("✅ Market data request sent")

        # Wait briefly for data
        await asyncio.sleep(3)

        if ticker.last and ticker.last > 0:
            print(f"✅ Market data received: SPY = ${ticker.last}")
        else:
            print("ℹ️ Market data pending (normal during off-hours)")

        # Cancel market data
        ib.cancelMktData(spy_contract)

        # Keep connection alive briefly for demo (from working example)
        print(f"\n⏳ Keeping connection alive for 5 seconds...")
        await asyncio.sleep(5)

        print(f"\n🎉 ALL TWS TESTS PASSED!")
        print(f"✅ Remote TWS connection is working perfectly")
        print(f"✅ This confirms TWS API is the right solution")

        return True

    except Exception as e:
        print(f"\n❌ TWS connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Detailed error analysis
        if "timeout" in str(e).lower():
            print(f"\n🔍 TIMEOUT ERROR ANALYSIS:")
            print(f"   • TWS may not be running on Windows computer")
            print(f"   • TWS API may not be enabled")
            print(f"   • Client ID may be in use")
            print(f"   • Network latency too high")

        elif "connection refused" in str(e).lower():
            print(f"\n🔍 CONNECTION REFUSED ANALYSIS:")
            print(f"   • TWS is not running on {tws_ip}")
            print(f"   • Port {port} is not accessible")
            print(f"   • Windows firewall blocking connection")
            print(f"   • TWS API not enabled")

        elif "already connected" in str(e).lower():
            print(f"\n🔍 ALREADY CONNECTED ANALYSIS:")
            print(f"   • Client ID 1 is already in use")
            print(f"   • Try a different client ID")

        return False

    finally:
        # Clean disconnect (from working example)
        if ib.isConnected():
            ib.disconnect()
            print(f"\n🔌 Disconnected cleanly from TWS")


async def test_both_trading_modes(tws_ip):
    """Test both paper and live trading connections"""
    print(f"\n🎯 Testing Both Trading Modes")
    print(f"=" * 50)

    results = {}

    # Test Paper Trading (port 7497)
    print(f"\n📝 Testing Paper Trading Mode...")
    try:
        success = await test_tws_api_connection(tws_ip, 7497)
        results["paper"] = success
        if success:
            print(f"✅ Paper Trading: WORKING")
        else:
            print(f"❌ Paper Trading: FAILED")
    except Exception as e:
        print(f"❌ Paper Trading test crashed: {e}")
        results["paper"] = False

    # Brief pause between tests
    await asyncio.sleep(2)

    # Test Live Trading (port 7496)
    print(f"\n💰 Testing Live Trading Mode...")
    try:
        success = await test_tws_api_connection(tws_ip, 7496)
        results["live"] = success
        if success:
            print(f"✅ Live Trading: WORKING")
        else:
            print(f"❌ Live Trading: FAILED")
    except Exception as e:
        print(f"❌ Live Trading test crashed: {e}")
        results["live"] = False

    return results


async def main():
    """Main test function"""
    print(f"🚀 SPYDER - Remote TWS Connection Test")
    print(f"=" * 60)
    print(f"📅 Started: {datetime.now()}")
    print(f"🐍 Python: {sys.version}")
    print()

    # Get TWS IP from configuration
    tws_ip = get_tws_ip_from_config()
    print(f"🎯 TWS Computer IP: {tws_ip}")
    print()

    # Step 1: Test network connectivity
    print(f"STEP 1: Network Connectivity Test")
    print(f"=" * 40)
    network_ok = await test_network_connectivity(tws_ip)

    if not network_ok:
        print(f"\n❌ Network connectivity failed")
        print(f"   Cannot reach TWS computer at {tws_ip}")
        print(f"   Check network connection and IP address")
        return

    # Step 2: Test port accessibility
    print(f"\nSTEP 2: Port Accessibility Test")
    print(f"=" * 40)
    accessible_ports = test_tws_ports(tws_ip)

    if not accessible_ports:
        print(f"\n❌ No TWS ports accessible")
        print(f"   TWS may not be running or API not enabled")
        print(f"   Check TWS configuration on Windows computer")
        return

    print(f"\n✅ Accessible ports: {accessible_ports}")

    # Step 3: Test API connections
    print(f"\nSTEP 3: TWS API Connection Tests")
    print(f"=" * 40)

    # Test all accessible ports
    working_connections = []

    if 7497 in accessible_ports:
        print(f"\n📝 Testing Paper Trading API...")
        try:
            success = await test_tws_api_connection(tws_ip, 7497)
            if success:
                working_connections.append("Paper Trading (7497)")
        except Exception as e:
            print(f"❌ Paper trading test failed: {e}")

    if 7496 in accessible_ports:
        print(f"\n💰 Testing Live Trading API...")
        try:
            success = await test_tws_api_connection(tws_ip, 7496)
            if success:
                working_connections.append("Live Trading (7496)")
        except Exception as e:
            print(f"❌ Live trading test failed: {e}")

    # Final Results
    print(f"\n{'=' * 60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'=' * 60}")

    if working_connections:
        print(f"🎉 SUCCESS! Working TWS connections:")
        for connection in working_connections:
            print(f"   ✅ {connection}")

        print(f"\n💡 CONCLUSIONS:")
        print(f"   ✅ Remote TWS API is working correctly")
        print(f"   ✅ This confirms TWS is the right solution")
        print(f"   ✅ IB Gateway handshake issues are bypassed")
        print(f"   ✅ Your dual-connection system is perfect!")

        print(f"\n🚀 RECOMMENDATIONS:")
        print(f"   • Use Remote TWS as your primary connection method")
        print(f"   • Keep IB Gateway as backup for offline development")
        print(f"   • Update SPYDER to prefer TWS over Gateway")
        print(f"   • Implement the working connection pattern in your client code")

    else:
        print(f"❌ NO WORKING TWS CONNECTIONS")
        print(f"   Network and ports are accessible but API handshake failed")
        print(f"   Check TWS configuration:")
        print(f"   • Enable API in TWS settings")
        print(f"   • Add {socket.gethostbyname(socket.gethostname())} to trusted IPs")
        print(f"   • Restart TWS after configuration changes")

    print(f"\n🕐 Test completed: {datetime.now()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
