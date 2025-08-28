#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Temporary Zurich Connectivity Diagnostic - Standalone Version
No dependencies on GatewayConfig or credentials
"""

import socket
import subprocess
import time
from datetime import datetime

# IBKR Zurich Server Configuration
ZURICH_SERVERS = {
    'primary': 'zdc1.ibllc.com',
    'backup1': 'zdc1-hb1.ibllc.com', 
    'backup2': 'zdc1-hb2.ibllc.com'
}

# Required ports for IBKR connectivity
REQUIRED_PORTS = {
    'trading': 4001,  # Authentication and trading operations
    'market_data': 4000  # Market data distribution
}

# DNS override IPs for Zurich servers
ZURICH_IPS = {
    'zdc1.ibllc.com': '185.179.200.100',
    'zdc1-hb1.ibllc.com': '185.179.200.101', 
    'zdc1-hb2.ibllc.com': '185.179.200.102'
}

def test_dns_resolution():
    """Test DNS resolution for all Zurich servers"""
    print("🔍 Testing DNS Resolution:")
    print("-" * 30)
    
    dns_ok = True
    for name, server in ZURICH_SERVERS.items():
        try:
            start_time = time.time()
            resolved_ip = socket.gethostbyname(server)
            latency = (time.time() - start_time) * 1000
            
            # Check if resolved to correct IP
            expected_ip = ZURICH_IPS.get(server, "unknown")
            correct_ip = resolved_ip == expected_ip
            
            status = "✅" if correct_ip else "⚠️"
            print(f"{status} {server} -> {resolved_ip} ({latency:.1f}ms)")
            
            if not correct_ip:
                print(f"   Expected: {expected_ip}")
                dns_ok = False
                
        except socket.gaierror as e:
            print(f"❌ {server} -> DNS FAILED: {e}")
            dns_ok = False
            
    return dns_ok

def test_port_connectivity():
    """Test port connectivity to all servers and ports"""
    print("\n📡 Testing Port Connectivity:")
    print("-" * 35)
    
    reachable_servers = 0
    zurich_reachable = False
    
    for server_name, server in ZURICH_SERVERS.items():
        server_reachable = False
        print(f"\n🖥️  {server} ({server_name}):")
        
        for port_name, port in REQUIRED_PORTS.items():
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                
                result = sock.connect_ex((server, port))
                latency = (time.time() - start_time) * 1000
                
                sock.close()
                
                if result == 0:
                    print(f"  ✅ Port {port} ({port_name}): OK ({latency:.1f}ms)")
                    server_reachable = True
                else:
                    print(f"  ❌ Port {port} ({port_name}): BLOCKED")
                    
            except socket.timeout:
                print(f"  ⏱️  Port {port} ({port_name}): TIMEOUT")
            except Exception as e:
                print(f"  ❌ Port {port} ({port_name}): ERROR - {e}")
                
        if server_reachable:
            reachable_servers += 1
            if server_name == 'primary':
                zurich_reachable = True
                
    return zurich_reachable, reachable_servers

def test_network_routing():
    """Test network routing to primary Zurich server"""
    print("\n🗺️  Network Routing Analysis:")
    print("-" * 35)
    
    server = ZURICH_SERVERS['primary']
    routing_issues = []
    
    try:
        result = subprocess.run(
            ['traceroute', '-n', '-w', '3', server],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            print(f"Route to {server}:")
            
            for i, line in enumerate(lines):
                if i == 0:  # Skip header
                    continue
                    
                print(f"  {i}: {line}")
                
                # Check for US routing (should go direct to EU)
                if any(pattern in line for pattern in ['64.190.', '104.160.', '199.16.']):
                    routing_issues.append(f"Traffic routing through US servers (hop {i})")
                    
                # Check for timeouts
                if '* * *' in line:
                    routing_issues.append(f"Network timeout at hop {i}")
                    
        else:
            routing_issues.append(f"Traceroute failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        routing_issues.append("Traceroute timeout - possible network blocking")
    except FileNotFoundError:
        routing_issues.append("Traceroute utility not available (install with: sudo apt install traceroute)")
    except Exception as e:
        routing_issues.append(f"Routing analysis error: {e}")
        
    return routing_issues

def generate_recommendations(dns_ok, zurich_reachable, backup_count, routing_issues):
    """Generate recommendations based on test results"""
    print("\n💡 Recommendations:")
    print("-" * 20)
    
    if not dns_ok:
        print("  🌐 DNS resolution issue detected")
        print("     → Add DNS overrides to /etc/hosts")
        print("     → Run: sudo nano /etc/hosts")
        print("     → Add these lines:")
        for server, ip in ZURICH_IPS.items():
            print(f"       {ip} {server}")
            
    if not zurich_reachable:
        print("  🔧 Zurich primary server unreachable")
        if backup_count > 0:
            print(f"     → {backup_count} backup servers available")
            print("     → Gateway may use backup automatically")
        else:
            print("     → No backup servers reachable")
            print("     → Check firewall/ISP blocking")
            
    if routing_issues:
        print("  🗺️  Network routing problems:")
        for issue in routing_issues:
            print(f"     → {issue}")
            
    print("\n🛠️  Quick Fix Commands:")
    print("     # Add DNS overrides")
    print("     sudo cp /etc/hosts /etc/hosts.backup")
    print("     echo '' | sudo tee -a /etc/hosts")
    print("     echo '# IBKR Zurich DNS Override' | sudo tee -a /etc/hosts")
    for server, ip in ZURICH_IPS.items():
        print(f"     echo '{ip} {server}' | sudo tee -a /etc/hosts")

def main():
    """Main diagnostic function"""
    print("🇨🇭 SPYDER Zurich Connectivity Diagnostic")
    print("=" * 50)
    
    # Test DNS resolution
    dns_ok = test_dns_resolution()
    
    # Test port connectivity
    zurich_reachable, backup_count = test_port_connectivity()
    
    # Test network routing
    routing_issues = test_network_routing()
    
    # Overall status
    print(f"\n📊 OVERALL STATUS:")
    print("=" * 20)
    
    if zurich_reachable and dns_ok:
        print("✅ EXCELLENT: Direct Zurich connectivity working")
    elif backup_count > 0:
        print("⚠️  FAIR: Backup servers available, primary may be blocked")
    elif dns_ok:
        print("❌ POOR: DNS OK but all servers unreachable")
    else:
        print("❌ CRITICAL: DNS and connectivity issues")
        
    print(f"🌐 DNS Resolution: {'✅ OK' if dns_ok else '❌ FAILED'}")
    print(f"🎯 Zurich Primary: {'✅ REACHABLE' if zurich_reachable else '❌ BLOCKED'}")
    print(f"🔄 Backup Servers: {backup_count}/2 reachable")
    print(f"🗺️  Routing Issues: {len(routing_issues)} detected")
    
    # Generate recommendations
    generate_recommendations(dns_ok, zurich_reachable, backup_count, routing_issues)
    
    print(f"\n⏰ Diagnostic completed at {datetime.now()}")

if __name__ == "__main__":
    main()
