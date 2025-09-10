#!/usr/bin/env python3
"""
Temporary IB Gateway/TWS Process Diagnostic Tool
Checks if IB Gateway or TWS is running and what ports they're using
"""

import subprocess
import socket
import psutil
from datetime import datetime

def check_ib_processes():
    """Check for running IB Gateway/TWS processes"""
    print("🔍 CHECKING FOR IB PROCESSES")
    print("=" * 50)
    
    ib_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name'].lower()
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            # Look for IB-related processes
            if any(keyword in name for keyword in ['gateway', 'tws', 'ibgateway', 'java']) or \
               any(keyword in cmdline.lower() for keyword in ['ibgateway', 'tws', 'interactivebrokers']):
                ib_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline
                })
                print(f"✓ Found: PID {proc.info['pid']} - {proc.info['name']}")
                if cmdline:
                    print(f"  Command: {cmdline[:100]}...")
                print()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not ib_processes:
        print("❌ No IB Gateway or TWS processes found running")
    
    return ib_processes

def check_listening_ports():
    """Check what ports are listening on localhost"""
    print("\n🔍 CHECKING LISTENING PORTS")
    print("=" * 50)
    
    listening_ports = []
    
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'LISTEN' and conn.laddr.ip == '127.0.0.1':
            listening_ports.append(conn.laddr.port)
    
    # Check specific IB ports
    ib_ports = [4001, 4002, 7496, 7497, 7498, 7499]
    
    print("IB-Related Ports:")
    for port in ib_ports:
        status = "✓ LISTENING" if port in listening_ports else "❌ NOT LISTENING"
        print(f"  Port {port}: {status}")
    
    print(f"\nAll Listening Ports on 127.0.0.1:")
    for port in sorted(listening_ports):
        print(f"  {port}")
    
    return listening_ports

def check_docker_containers():
    """Check for IB Gateway Docker containers"""
    print("\n🔍 CHECKING DOCKER CONTAINERS")
    print("=" * 50)
    
    try:
        result = subprocess.run(['docker', 'ps', '-a'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            ib_containers = []
            
            for line in lines[1:]:  # Skip header
                if any(keyword in line.lower() for keyword in ['ib-gateway', 'ibgateway', 'tws']):
                    ib_containers.append(line)
                    print(f"Found: {line}")
            
            if not ib_containers:
                print("❌ No IB Gateway Docker containers found")
                
            return ib_containers
            
        else:
            print("❌ Docker not available or error running docker ps")
            return []
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ Docker not available")
        return []

def test_basic_connectivity():
    """Test basic network connectivity"""
    print("\n🔍 TESTING BASIC CONNECTIVITY") 
    print("=" * 50)
    
    # Test localhost connectivity
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 22))  # SSH port as test
        sock.close()
        print("✓ Localhost connectivity working")
    except Exception as e:
        print(f"❌ Localhost connectivity issue: {e}")
    
    # Test internet connectivity 
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('google.com', 80))
        sock.close()
        if result == 0:
            print("✓ Internet connectivity working")
        else:
            print("❌ Internet connectivity issues")
    except Exception as e:
        print(f"❌ Internet connectivity error: {e}")

def check_ib_installation():
    """Check for IB Gateway installation"""
    print("\n🔍 CHECKING IB INSTALLATION")
    print("=" * 50)
    
    common_paths = [
        "/opt/IBJts",
        "/home/adam/IBJts", 
        "/home/adam/Jts",
        "/usr/local/IBJts",
        "~/IBJts",
        "~/Jts"
    ]
    
    found_installations = []
    
    for path in common_paths:
        expanded_path = path.replace("~", "/home/adam")
        try:
            import os
            if os.path.exists(expanded_path):
                found_installations.append(expanded_path)
                print(f"✓ Found IB installation: {expanded_path}")
                
                # List contents
                contents = os.listdir(expanded_path)
                print(f"  Contents: {', '.join(contents[:10])}")
                if len(contents) > 10:
                    print(f"  ... and {len(contents) - 10} more items")
        except Exception as e:
            continue
    
    if not found_installations:
        print("❌ No IB installations found in common locations")
    
    return found_installations

def main():
    """Main diagnostic function"""
    print(f"🔧 IB GATEWAY/TWS DIAGNOSTIC TOOL")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Run all diagnostics
    processes = check_ib_processes()
    ports = check_listening_ports()
    containers = check_docker_containers()
    test_basic_connectivity()
    installations = check_ib_installation()
    
    # Summary and recommendations
    print("\n💡 SUMMARY & RECOMMENDATIONS")
    print("=" * 60)
    
    if not processes and not containers:
        print("❌ MAIN ISSUE: No IB Gateway or TWS is currently running")
        print("\n🔧 NEXT STEPS:")
        print("1. Start IB Gateway manually:")
        print("   - Open IB Gateway application")
        print("   - Or use Docker: docker run -p 4002:4002 ib-gateway")
        print("   - Or use your existing Spyder gateway automation")
        
    if not any(port in [4001, 4002, 7496, 7497] for port in ports):
        print("2. If Gateway is running, check port configuration")
        print("3. Verify firewall settings aren't blocking IB ports")
        
    if installations:
        print(f"✓ IB installations found at: {installations}")
    else:
        print("4. Consider reinstalling IB Gateway if not found")
    
    print("\n🎯 Once IB Gateway is running, re-run the connection tester:")
    print("   python SpyderB_Broker/SpyderB23_IBKRConnectionTester.py")

if __name__ == "__main__":
    main()