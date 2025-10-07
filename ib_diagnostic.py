#!/usr/bin/env python3
"""
IB Gateway 10.39 Connection Diagnostic Tool
Tests connectivity and provides troubleshooting guidance
"""

import socket
import subprocess
import time
import sys
from typing import Tuple, Optional

# Configuration
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORTS = {
    "paper": 4002,
    "live": 4001
}
DEFAULT_CLIENT_ID = 999

def print_header(text: str):
    """Print formatted header"""
    print(f"\n{'=' * 60}")
    print(f"{text}")
    print(f"{'=' * 60}\n")

def print_status(success: bool, message: str):
    """Print colored status message"""
    symbol = "✅" if success else "❌"
    print(f"{symbol} {message}")

def check_gateway_process() -> Tuple[bool, str]:
    """Check if IB Gateway process is running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return True, f"Gateway process running (PIDs: {', '.join(pids)})"
        else:
            return False, "Gateway process not found"
    except Exception as e:
        return False, f"Error checking process: {e}"

def check_port_listening(port: int) -> Tuple[bool, str]:
    """Check if Gateway port is listening"""
    try:
        result = subprocess.run(
            ["ss", "-tln"],
            capture_output=True,
            text=True
        )
        
        if f":{port}" in result.stdout:
            return True, f"Port {port} is listening"
        else:
            return False, f"Port {port} is NOT listening"
    except Exception as e:
        return False, f"Error checking port: {e}"

def test_port_connection(host: str, port: int, timeout: int = 5) -> Tuple[bool, str]:
    """Test TCP connection to Gateway port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return True, f"TCP connection to {host}:{port} successful"
        else:
            return False, f"TCP connection to {host}:{port} failed (error {result})"
    except Exception as e:
        return False, f"Connection test error: {e}"

def test_ib_api_connection(host: str, port: int, client_id: int) -> Tuple[bool, str, Optional[dict]]:
    """Test actual IB API connection"""
    try:
        from ib_async import IB
        
        ib = IB()
        print(f"   Attempting API connection to {host}:{port}...")
        
        # Try to connect
        ib.connect(host, port, clientId=client_id, timeout=10)
        
        if ib.isConnected():
            # Get connection details
            info = {
                "server_version": ib.client.serverVersion(),
                "connection_time": str(ib.client.connectionTime()),
                "managed_accounts": ib.managedAccounts()
            }
            
            ib.disconnect()
            
            return True, "IB API connection successful", info
        else:
            return False, "IB API connection failed - not connected", None
            
    except ImportError:
        return False, "ib_async library not installed (pip install ib_async)", None
    except Exception as e:
        return False, f"IB API connection error: {e}", None

def suggest_fixes(diagnostics: dict):
    """Provide troubleshooting suggestions based on diagnostics"""
    print_header("TROUBLESHOOTING SUGGESTIONS")
    
    if not diagnostics['process_running']:
        print("🔧 Gateway is not running:")
        print("   1. Start Gateway: cd ~/Jts/ibgateway/1039 && ./ibgateway")
        print("   2. Or use: bash ~/Projects/Spyder/launch_balanced_gateway.sh")
        print()
    
    if diagnostics['process_running'] and not diagnostics['port_listening']:
        print("🔧 Gateway running but port not listening:")
        print("   1. Gateway may still be starting up - wait 30-60 seconds")
        print("   2. Check Gateway logs: tail -f ~/Jts/ibgateway/1039/logs/*.log")
        print("   3. Restart Gateway with proper settings")
        print()
    
    if diagnostics['port_listening'] and not diagnostics['tcp_connection']:
        print("🔧 Port listening but TCP connection fails:")
        print("   1. Check firewall: sudo ufw status")
        print("   2. Check if port is bound to localhost only")
        print("   3. Verify no other process is using the port")
        print()
    
    if diagnostics['tcp_connection'] and not diagnostics['api_connection']:
        print("🔧 TCP works but IB API connection fails:")
        print("   1. Check Gateway API settings:")
        print("      - Open Gateway GUI")
        print("      - Go to Configuration -> API -> Settings")
        print("      - Ensure 'Enable ActiveX and Socket Clients' is checked")
        print("      - Ensure 'Socket port' matches (4002 for paper, 4001 for live)")
        print("      - Ensure 'Read-Only API' is unchecked (if you need to trade)")
        print("   2. Check for client ID conflicts")
        print("   3. Review Gateway logs for authentication errors")
        print()
    
    if all([diagnostics['process_running'], 
            diagnostics['port_listening'],
            diagnostics['tcp_connection'],
            diagnostics['api_connection']]):
        print("✅ All checks passed! Your connection should work.")
        print()
        print("If still having issues:")
        print("   1. Try different client IDs (avoid 0, try 1-999)")
        print("   2. Check your credentials in Gateway")
        print("   3. Ensure you have an active IB account with API access")
        print("   4. Check IB account management for API permissions")
        print()

def main():
    """Run comprehensive diagnostics"""
    print_header("IB GATEWAY 10.39 CONNECTION DIAGNOSTICS")
    
    # Determine trading mode
    mode = input("Trading mode (paper/live)? [paper]: ").strip().lower() or "paper"
    port = GATEWAY_PORTS.get(mode, 4002)
    
    print(f"\nTesting connection to {mode.upper()} trading (port {port})...\n")
    
    # Store diagnostic results
    diagnostics = {
        'process_running': False,
        'port_listening': False,
        'tcp_connection': False,
        'api_connection': False
    }
    
    # Test 1: Check Gateway process
    print("Test 1: Gateway Process")
    success, message = check_gateway_process()
    print_status(success, message)
    diagnostics['process_running'] = success
    
    if not success:
        suggest_fixes(diagnostics)
        return 1
    
    # Test 2: Check port listening
    print("\nTest 2: Port Listening")
    success, message = check_port_listening(port)
    print_status(success, message)
    diagnostics['port_listening'] = success
    
    if not success:
        print("\n⏳ Gateway may still be initializing. Waiting 10 seconds...")
        time.sleep(10)
        success, message = check_port_listening(port)
        print_status(success, message)
        diagnostics['port_listening'] = success
    
    # Test 3: TCP connection
    print("\nTest 3: TCP Connection")
    success, message = test_port_connection(GATEWAY_HOST, port)
    print_status(success, message)
    diagnostics['tcp_connection'] = success
    
    # Test 4: IB API connection
    print("\nTest 4: IB API Connection")
    success, message, info = test_ib_api_connection(GATEWAY_HOST, port, DEFAULT_CLIENT_ID)
    print_status(success, message)
    diagnostics['api_connection'] = success
    
    if success and info:
        print(f"\n   Connection Details:")
        print(f"   - Server Version: {info['server_version']}")
        print(f"   - Connection Time: {info['connection_time']}")
        print(f"   - Managed Accounts: {info['managed_accounts']}")
    
    # Provide suggestions
    suggest_fixes(diagnostics)
    
    # Summary
    print_header("SUMMARY")
    total = len(diagnostics)
    passed = sum(diagnostics.values())
    print(f"Tests Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All diagnostics passed! Gateway is fully operational.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review suggestions above.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
        sys.exit(1)