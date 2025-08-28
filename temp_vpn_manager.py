#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Temporary VPN Manager - Standalone Version
No dependencies on GatewayConfig or credentials
"""

import subprocess
import socket
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# European VPN endpoints optimized for IBKR Zurich connectivity
OPTIMAL_VPN_ENDPOINTS = {
    # Switzerland - Closest to Zurich
    'zurich': {
        'country': 'Switzerland',
        'city': 'Zurich', 
        'priority': 1,
        'expected_latency': '5-15ms',
        'providers': ['ProtonVPN', 'Surfshark', 'NordVPN']
    },
    'geneva': {
        'country': 'Switzerland',
        'city': 'Geneva',
        'priority': 2, 
        'expected_latency': '10-20ms',
        'providers': ['ExpressVPN', 'CyberGhost', 'Surfshark']
    },
    
    # Germany - Frankfurt is major financial hub
    'frankfurt': {
        'country': 'Germany', 
        'city': 'Frankfurt',
        'priority': 3,
        'expected_latency': '15-25ms',
        'providers': ['NordVPN', 'ExpressVPN', 'ProtonVPN']
    },
    'munich': {
        'country': 'Germany',
        'city': 'Munich', 
        'priority': 4,
        'expected_latency': '20-30ms',
        'providers': ['Surfshark', 'CyberGhost']
    },
    
    # Netherlands - Amsterdam excellent connectivity
    'amsterdam': {
        'country': 'Netherlands',
        'city': 'Amsterdam',
        'priority': 5, 
        'expected_latency': '25-35ms',
        'providers': ['NordVPN', 'ExpressVPN', 'ProtonVPN', 'Surfshark']
    },
    
    # Austria - Close to Zurich
    'vienna': {
        'country': 'Austria',
        'city': 'Vienna',
        'priority': 6,
        'expected_latency': '20-30ms', 
        'providers': ['CyberGhost', 'Surfshark']
    }
}

# VPN Provider Configuration
VPN_PROVIDERS = {
    'nordvpn': {
        'name': 'NordVPN',
        'binary': 'nordvpn',
        'connect_cmd': 'nordvpn connect {server}',
        'disconnect_cmd': 'nordvpn disconnect',
        'status_cmd': 'nordvpn status',
        'install_cmd': 'wget -qnc https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb && sudo dpkg -i nordvpn-release_1.0.0_all.deb && sudo apt update && sudo apt install nordvpn -y'
    },
    'expressvpn': {
        'name': 'ExpressVPN',
        'binary': 'expressvpn',
        'connect_cmd': 'expressvpn connect {server}',
        'disconnect_cmd': 'expressvpn disconnect',
        'status_cmd': 'expressvpn status',
        'install_cmd': 'Download from https://www.expressvpn.com/setup#manual'
    },
    'protonvpn': {
        'name': 'ProtonVPN',
        'binary': 'protonvpn-cli',
        'connect_cmd': 'protonvpn-cli connect {server}',
        'disconnect_cmd': 'protonvpn-cli disconnect', 
        'status_cmd': 'protonvpn-cli status',
        'install_cmd': 'pip install protonvpn-cli'
    }
}

def detect_vpn_providers():
    """Detect which VPN providers are installed"""
    print("🔍 Detecting VPN Providers:")
    print("-" * 30)
    
    available_providers = []
    
    for provider_key, provider_config in VPN_PROVIDERS.items():
        binary = provider_config['binary']
        
        try:
            # Check if binary exists
            result = subprocess.run(['which', binary], capture_output=True)
            
            if result.returncode == 0:
                print(f"✅ {provider_config['name']}: INSTALLED")
                available_providers.append(provider_key)
                
                # Try to get status
                try:
                    status_result = subprocess.run(
                        provider_config['status_cmd'].split(),
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if status_result.returncode == 0:
                        # Parse basic status
                        output = status_result.stdout.lower()
                        if "connected" in output:
                            print(f"   📡 Status: CONNECTED")
                        elif "disconnected" in output:
                            print(f"   📡 Status: DISCONNECTED")
                        else:
                            print(f"   📡 Status: UNKNOWN")
                    
                except subprocess.TimeoutExpired:
                    print(f"   📡 Status: TIMEOUT")
                except:
                    print(f"   📡 Status: ERROR")
                    
            else:
                print(f"❌ {provider_config['name']}: NOT INSTALLED")
                print(f"   💡 Install: {provider_config['install_cmd']}")
                
        except Exception as e:
            print(f"❌ {provider_config['name']}: ERROR - {e}")
            
    return available_providers

def get_current_ip_location():
    """Get current public IP and geographic location"""
    print("\n🌐 Current Public IP & Location:")
    print("-" * 35)
    
    try:
        # Try multiple IP detection services
        services = [
            'https://ipapi.co/json/',
            'https://ip-api.com/json/', 
            'https://ipinfo.io/json'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract info (format varies by service)
                    ip = data.get('ip') or data.get('query')
                    country = data.get('country_name') or data.get('country')
                    city = data.get('city')
                    region = data.get('region') or data.get('regionName')
                    
                    if ip:
                        print(f"📍 IP Address: {ip}")
                        print(f"🏳️  Country: {country}")
                        if city:
                            print(f"🏙️  City: {city}")
                        if region:
                            print(f"🗺️  Region: {region}")
                            
                        # Check if European location (good for IBKR)
                        european_countries = [
                            'Switzerland', 'Germany', 'Netherlands', 'Austria', 
                            'France', 'United Kingdom', 'Belgium', 'Luxembourg'
                        ]
                        
                        is_european = any(eu in str(country) for eu in european_countries)
                        
                        if is_european:
                            print("✅ European IP detected - EXCELLENT for IBKR Zurich!")
                        else:
                            print("⚠️  Non-European IP - may be blocked by IBKR Zurich servers")
                            
                        return ip, country, city
                        
            except requests.RequestException:
                continue
                
        print("❌ Unable to detect public IP")
        return None, None, None
        
    except Exception as e:
        print(f"❌ IP detection error: {e}")
        return None, None, None

def test_ibkr_connectivity():
    """Test connectivity to IBKR Zurich servers"""
    print("\n🎯 Testing IBKR Zurich Connectivity:")
    print("-" * 40)
    
    zurich_servers = {
        'primary': 'zdc1.ibllc.com',
        'backup1': 'zdc1-hb1.ibllc.com',
        'backup2': 'zdc1-hb2.ibllc.com'
    }
    
    ports = [4000, 4001]  # Market data and trading ports
    reachable_servers = 0
    
    for server_name, server in zurich_servers.items():
        print(f"\n🖥️  {server} ({server_name}):")
        server_reachable = False
        
        for port in ports:
            try:
                start_time = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                
                result = sock.connect_ex((server, port))
                latency = (time.time() - start_time) * 1000
                
                sock.close()
                
                if result == 0:
                    print(f"  ✅ Port {port}: REACHABLE ({latency:.1f}ms)")
                    server_reachable = True
                else:
                    print(f"  ❌ Port {port}: BLOCKED")
                    
            except socket.timeout:
                print(f"  ⏱️  Port {port}: TIMEOUT")
            except Exception as e:
                print(f"  ❌ Port {port}: ERROR - {e}")
                
        if server_reachable:
            reachable_servers += 1
            
    return reachable_servers

def show_optimal_endpoints():
    """Show optimal VPN endpoints for IBKR trading"""
    print("\n🎯 Optimal VPN Endpoints for IBKR Zurich:")
    print("-" * 50)
    
    print("Priority | Location | Expected Latency | Providers")
    print("-" * 60)
    
    for endpoint_key, config in OPTIMAL_VPN_ENDPOINTS.items():
        providers_str = ", ".join(config['providers'][:3])  # Show first 3
        print(f"   {config['priority']}     | {config['city']:<8} | {config['expected_latency']:<15} | {providers_str}")
        
    print(f"\n💡 Recommendation:")
    print(f"   1. Install a VPN provider (NordVPN, ExpressVPN, etc.)")
    print(f"   2. Connect to Swiss or German servers")  
    print(f"   3. Test IBKR connectivity")
    print(f"   4. If successful, restart IB Gateway")

def show_installation_guides():
    """Show VPN installation guides"""
    print("\n🛠️  VPN Provider Installation Guides:")
    print("=" * 45)
    
    guides = {
        'NordVPN (Recommended)': [
            "# Download and install NordVPN",
            "wget -qnc https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/nordvpn-release_1.0.0_all.deb",
            "sudo dpkg -i nordvpn-release_1.0.0_all.deb", 
            "sudo apt update",
            "sudo apt install nordvpn -y",
            "",
            "# Login and connect",
            "nordvpn login",
            "nordvpn connect switzerland  # or germany, netherlands"
        ],
        'ProtonVPN (Free tier available)': [
            "# Install via pip", 
            "pip install protonvpn-cli",
            "",
            "# Initialize and login",
            "protonvpn-cli init",
            "protonvpn-cli login",
            "protonvpn-cli connect --country ch  # Switzerland"
        ],
        'ExpressVPN': [
            "# Download from official site:",
            "# https://www.expressvpn.com/setup#manual",
            "# Select Ubuntu package",
            "",
            "sudo dpkg -i expressvpn_*_amd64.deb",
            "expressvpn activate",
            "expressvpn connect switzerland"
        ]
    }
    
    for provider, commands in guides.items():
        print(f"\n--- {provider} ---")
        for cmd in commands:
            if cmd.startswith("#"):
                print(f"\033[92m{cmd}\033[0m")  # Green for comments
            else:
                print(f"  {cmd}")

def test_vpn_solution():
    """Test if VPN actually solves the IBKR connectivity issue"""
    print("\n🧪 VPN Solution Test:")
    print("=" * 25)
    
    print("📊 BEFORE VPN:")
    pre_ip, pre_country, pre_city = get_current_ip_location()
    pre_reachable = test_ibkr_connectivity()
    
    print(f"\n📈 Summary:")
    print(f"  Current Location: {pre_city}, {pre_country}")
    print(f"  IBKR Servers Reachable: {pre_reachable}/3")
    
    if pre_reachable == 0:
        print("❌ All IBKR servers blocked - VPN connection required")
    elif pre_reachable < 3:
        print("⚠️  Some IBKR servers blocked - VPN may improve connectivity")
    else:
        print("✅ All IBKR servers reachable - VPN not needed!")
        
    print(f"\n💡 Next Steps:")
    if pre_reachable == 0:
        print("  1. Install and connect to European VPN server")
        print("  2. Re-run this test to verify connectivity")
        print("  3. Restart IB Gateway once connectivity confirmed")
    else:
        print("  🎉 Your connection already works! No VPN needed.")

def main():
    """Main VPN manager diagnostic"""
    print("🌐 SPYDER VPN Manager - IBKR Zurich Bypass")
    print("=" * 50)
    
    # Detect installed VPN providers
    available_providers = detect_vpn_providers()
    
    # Show current IP and location
    get_current_ip_location()
    
    # Test IBKR connectivity
    reachable_servers = test_ibkr_connectivity()
    
    # Show optimal endpoints
    show_optimal_endpoints()
    
    # Overall assessment
    print(f"\n📊 OVERALL ASSESSMENT:")
    print("=" * 25)
    
    if len(available_providers) > 0:
        print(f"✅ VPN Providers Available: {len(available_providers)}")
        for provider in available_providers:
            print(f"   • {VPN_PROVIDERS[provider]['name']}")
    else:
        print(f"❌ No VPN Providers Installed")
        
    if reachable_servers == 0:
        print(f"❌ IBKR Connectivity: ALL BLOCKED")
        print(f"   🚨 VPN CONNECTION REQUIRED")
    elif reachable_servers < 3:
        print(f"⚠️  IBKR Connectivity: PARTIAL ({reachable_servers}/3)")
        print(f"   💡 VPN recommended for full access")
    else:
        print(f"✅ IBKR Connectivity: EXCELLENT ({reachable_servers}/3)")
        print(f"   🎉 No VPN needed!")
        
    # Show next steps
    print(f"\n🎯 RECOMMENDED ACTIONS:")
    print("-" * 25)
    
    if len(available_providers) == 0 and reachable_servers == 0:
        print("  1. Install VPN provider (see installation guides below)")
        print("  2. Connect to Swiss/German server")
        print("  3. Test IBKR connectivity") 
        print("  4. Restart IB Gateway")
        show_installation_guides()
        
    elif len(available_providers) > 0 and reachable_servers == 0:
        print("  1. Connect VPN to European server:")
        for provider in available_providers:
            provider_config = VPN_PROVIDERS[provider]
            print(f"     {provider_config['connect_cmd'].replace('{server}', 'switzerland')}")
        print("  2. Re-run: python temp_vpn_manager.py")
        print("  3. If successful, restart IB Gateway")
        
    elif reachable_servers > 0:
        print("  ✅ IBKR connectivity working!")
        print("  🎯 Your IB Gateway should connect directly to Zurich")
        
    print(f"\n⏰ Test completed at {datetime.now()}")

if __name__ == "__main__":
    main()
