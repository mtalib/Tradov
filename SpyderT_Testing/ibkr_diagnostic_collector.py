#!/usr/bin/env python3
"""
IBKR Support Diagnostic Information Generator
Run this script to collect current system state for IBKR support
"""

import subprocess
import socket
import sys
import time
from datetime import datetime
import platform


def run_command(cmd, description):
    """Run a command and return formatted output"""
    print(f"\n{'='*50}")
    print(f"📋 {description}")
    print(f"Command: {cmd}")
    print(f"{'='*50}")

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error (exit code {result.returncode}):")
            print(result.stderr)
    except subprocess.TimeoutExpired:
        print("Command timed out")
    except Exception as e:
        print(f"Error running command: {e}")


def test_socket_connection():
    """Test basic socket connection"""
    print(f"\n{'='*50}")
    print(f"🔌 Socket Connection Test")
    print(f"{'='*50}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        start_time = time.time()
        result = sock.connect_ex(("127.0.0.1", 4002))
        connect_time = time.time() - start_time

        if result == 0:
            print(f"✅ TCP connection successful in {connect_time:.3f}s")

            # Try to send test data
            try:
                sock.send(b"TEST\n")
                sock.settimeout(2)
                response = sock.recv(100)
                print(f"Response to test data: {repr(response)}")
            except socket.timeout:
                print("⚠️  No response to test data (expected for API port)")
            except Exception as e:
                print(f"Error during data test: {e}")
        else:
            print(f"❌ TCP connection failed with error code: {result}")

        sock.close()
    except Exception as e:
        print(f"❌ Socket test error: {e}")


def main():
    """Generate comprehensive diagnostic report"""
    print("🔍 IBKR Support - System Diagnostic Report Generator")
    print(f"Generated: {datetime.now()}")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python: {sys.version}")

    # System Information
    run_command("uname -a", "System Information")

    # Python Environment
    run_command("python3 --version", "Python Version")
    run_command("pip show ibapi", "IBAPI Package Information")

    # Network Configuration
    run_command("netstat -tlnp | grep :4002", "Port 4002 Status (netstat)")
    run_command("ss -tlnp | grep :4002", "Port 4002 Status (ss)")

    # Process Information
    run_command("ps aux | grep -i gateway | grep -v grep", "IB Gateway Process")
    run_command(
        "ps aux | grep java | grep -i gateway | grep -v grep",
        "Java Gateway Process Details",
    )

    # IB Gateway Installation
    run_command(
        "find /home/adam/Jts -name '*.log' -o -name 'ibgateway.vmoptions' | head -5",
        "IB Gateway Files",
    )
    run_command(
        "ls -la /home/adam/Jts/ibgateway/1040/ | head -10",
        "IB Gateway Installation Directory",
    )

    # Network Connectivity
    test_socket_connection()
    run_command("telnet 127.0.0.1 4002", "Telnet Test (will timeout)")

    # System Resources
    run_command("free -h", "Memory Usage")
    run_command("df -h /home/adam", "Disk Space")

    # Firewall Status
    run_command("sudo ufw status", "UFW Firewall Status")
    run_command("sudo iptables -L | head -10", "IPTables Status")

    print(f"\n{'='*50}")
    print("📊 DIAGNOSTIC SUMMARY")
    print(f"{'='*50}")
    print("This diagnostic information has been collected for IBKR support.")
    print("Key points to include in your support ticket:")
    print("1. Issue: API connection hangs during handshake")
    print("2. Platform: Linux with Python 3.13")
    print("3. IBAPI Version: 9.81.1.post1")
    print("4. IB Gateway: v10.40.1 (latest)")
    print("5. All configuration verified as correct")
    print("6. Issue persists across fresh installations")

    print(f"\n🎯 Next Steps:")
    print("1. Save this output and include with your IBKR support ticket")
    print("2. Reference the main report: IBKR_Support_Report.md")
    print("3. Mention that standard troubleshooting has been exhausted")


if __name__ == "__main__":
    main()
