#!/usr/bin/env python3
"""
SPYDER - Quick TWS Port Test
Test TWS API ports directly without relying on ping
Windows often blocks ping but allows TWS API connections
"""

import socket
import sys
from datetime import datetime
import subprocess
import platform


def test_port_connectivity(host, port, timeout=5):
    """Test if a specific port is accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"   ⚠️ Port {port} test error: {e}")
        return False


def test_network_route(host):
    """Test network route to host"""
    try:
        if platform.system().lower() == "windows":
            cmd = ["tracert", "-h", "5", "-w", "1000", host]
        else:
            cmd = ["traceroute", "-m", "5", "-w", "1", host]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return "timeout" not in result.stdout.lower()
    except:
        return False


def scan_network_for_tws():
    """Scan local network for TWS instances"""
    print("🔍 Scanning local network for TWS instances...")

    # Get local network range
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        network_base = ".".join(local_ip.split(".")[:-1]) + "."
        print(f"   Local IP: {local_ip}")
        print(f"   Scanning: {network_base}1-254")
    except:
        print("   ⚠️ Could not determine local network")
        return []

    tws_instances = []

    # Quick scan common IPs first
    priority_ips = [
        "192.168.1.4",  # Configured IP
        "192.168.1.100",
        "192.168.1.101",
        "192.168.1.200",
        "192.168.1.201",
        "192.168.0.100",
        "192.168.0.101",
    ]

    print("   Testing priority IPs...")
    for ip in priority_ips:
        for port in [7497, 7496]:  # Paper, Live
            if test_port_connectivity(ip, port, timeout=2):
                mode = "Paper" if port == 7497 else "Live"
                tws_instances.append((ip, port, mode))
                print(f"   ✅ Found TWS: {ip}:{port} ({mode})")

    return tws_instances


def main():
    print("🕷️ SPYDER - Quick TWS Port Test")
    print("=" * 50)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Configured TWS IP
    tws_ip = "192.168.1.4"
    tws_ports = {7497: "Paper Trading", 7496: "Live Trading"}

    print(f"🎯 Testing configured TWS: {tws_ip}")
    print("-" * 30)

    accessible_ports = []

    # Test each port
    for port, description in tws_ports.items():
        print(f"Testing {port} ({description})...", end=" ")

        if test_port_connectivity(tws_ip, port):
            print("✅ ACCESSIBLE")
            accessible_ports.append((port, description))
        else:
            print("❌ Not accessible")

    print()

    if accessible_ports:
        print("🎉 SUCCESS! TWS API ports found:")
        for port, desc in accessible_ports:
            print(f"   ✅ {tws_ip}:{port} - {desc}")

        print(f"\n💡 NEXT STEPS:")
        print(f"   • Run full API test: python test_remote_tws_working.py")
        print(f"   • Launch SPYDER with TWS: ./launch_spyder_tws.sh")
        print(f"   • Use connection selector: python launch_connection_selector.py")

    else:
        print("❌ No TWS API ports accessible on configured IP")
        print(f"\n🔍 Troubleshooting:")
        print(f"   • Is TWS running on Windows computer?")
        print(f"   • Is TWS API enabled in settings?")
        print(f"   • Is Windows firewall blocking ports?")
        print(f"   • Has the IP address changed?")

        print(f"\n🌐 Testing network route...")
        if test_network_route(tws_ip):
            print(f"   ✅ Network route exists to {tws_ip}")
            print(f"   → TWS is probably not running or API disabled")
        else:
            print(f"   ❌ No network route to {tws_ip}")
            print(f"   → Computer may be off or IP changed")

        # Scan network for TWS instances
        found_instances = scan_network_for_tws()

        if found_instances:
            print(f"\n🎯 Alternative TWS instances found:")
            for ip, port, mode in found_instances:
                print(f"   • {ip}:{port} - {mode} Trading")
            print(f"\n   Update config/config_remote_tws.py with correct IP")
        else:
            print(f"\n🔍 No TWS instances found on local network")
            print(f"   • Check if TWS is running")
            print(f"   • Verify network connectivity")
            print(f"   • Try manual IP scan")

    print(f"\n" + "=" * 50)
    print(f"Test completed: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback

        traceback.print_exc()
