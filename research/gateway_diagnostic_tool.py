#!/usr/bin/env python3
"""
COMPREHENSIVE IB GATEWAY API DIAGNOSTIC TOOL
Diagnoses EXACTLY why the API handshake is failing
"""

import os
import sys
import socket
import subprocess
import configparser
from pathlib import Path
from datetime import datetime

class GatewayDiagnostic:
    def __init__(self):
        self.jts_path = Path.home() / "Jts"
        self.jts_ini = self.jts_path / "jts.ini"
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def print_header(self, text):
        print("\n" + "=" * 70)
        print(f"  {text}")
        print("=" * 70)
    
    def check_gateway_process(self):
        """Check if Gateway is running"""
        self.print_header("1️⃣  GATEWAY PROCESS CHECK")
        
        try:
            result = subprocess.run(['pgrep', '-f', 'ibgateway'], 
                                  capture_output=True, text=True)
            pids = result.stdout.strip().split('\n')
            
            if result.stdout.strip():
                self.successes.append(f"Gateway is running (PIDs: {', '.join(pids)})")
                print(f"✅ Gateway is running")
                print(f"   PIDs: {', '.join(pids)}")
                
                # Get detailed process info
                for pid in pids:
                    if pid:
                        ps_result = subprocess.run(['ps', '-p', pid, '-o', 'cmd='],
                                                 capture_output=True, text=True)
                        print(f"   Process: {ps_result.stdout.strip()[:80]}")
                return True
            else:
                self.issues.append("Gateway is NOT running")
                print("❌ Gateway is NOT running")
                print("   Action: Start IB Gateway first")
                return False
                
        except Exception as e:
            self.issues.append(f"Cannot check Gateway process: {e}")
            print(f"❌ Error checking process: {e}")
            return False
    
    def check_port_listening(self):
        """Check if port 4002 is listening"""
        self.print_header("2️⃣  PORT LISTENING CHECK")
        
        try:
            # Check using netstat
            result = subprocess.run(['netstat', '-tlpn'], 
                                  capture_output=True, text=True)
            
            port_4002_found = False
            for line in result.stdout.split('\n'):
                if ':4002' in line:
                    port_4002_found = True
                    print(f"✅ Port 4002 is listening:")
                    print(f"   {line.strip()}")
                    self.successes.append("Port 4002 is listening")
                    break
            
            if not port_4002_found:
                self.issues.append("Port 4002 is NOT listening")
                print("❌ Port 4002 is NOT listening")
                print("   This means Gateway hasn't opened the API port")
                print("   Possible causes:")
                print("   - API not enabled in jts.ini")
                print("   - Gateway still starting up")
                print("   - Gateway in error state")
                return False
                
            return True
            
        except Exception as e:
            self.warnings.append(f"Cannot check ports: {e}")
            print(f"⚠️  Cannot check ports: {e}")
            return False
    
    def check_socket_connection(self):
        """Test raw socket connection to port"""
        self.print_header("3️⃣  SOCKET CONNECTION TEST")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('127.0.0.1', 4002))
            sock.close()
            
            if result == 0:
                print("✅ Socket connection to port 4002 successful")
                self.successes.append("Socket connection works")
                return True
            else:
                print(f"❌ Socket connection failed (error code: {result})")
                self.issues.append(f"Socket connection failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Socket connection error: {e}")
            self.issues.append(f"Socket error: {e}")
            return False
    
    def check_jts_ini(self):
        """Analyze jts.ini configuration"""
        self.print_header("4️⃣  JTS.INI CONFIGURATION ANALYSIS")
        
        if not self.jts_ini.exists():
            print(f"❌ jts.ini NOT FOUND at: {self.jts_ini}")
            self.issues.append("jts.ini file missing")
            return False
        
        print(f"✅ jts.ini found at: {self.jts_ini}")
        
        # Read and parse jts.ini
        config = configparser.ConfigParser()
        try:
            config.read(self.jts_ini)
        except Exception as e:
            print(f"❌ Error reading jts.ini: {e}")
            self.issues.append(f"Cannot parse jts.ini: {e}")
            return False
        
        # Check critical settings
        critical_checks = {
            'TradingMode': 'paper',
            'LocalServerPort': '4002',
            'TrustedIPs': '127.0.0.1',
        }
        
        print("\n📋 Critical Settings Check:")
        all_good = True
        
        if 'IBGateway' in config:
            for key, expected in critical_checks.items():
                value = config['IBGateway'].get(key, 'NOT SET')
                
                if key == 'TrustedIPs':
                    # Check if 127.0.0.1 is in the list
                    if '127.0.0.1' in value or 'localhost' in value.lower():
                        print(f"   ✅ {key}: {value}")
                    else:
                        print(f"   ❌ {key}: {value}")
                        print(f"      Missing 127.0.0.1!")
                        self.issues.append(f"{key} doesn't include 127.0.0.1")
                        all_good = False
                elif value == expected or value.lower() == expected.lower():
                    print(f"   ✅ {key}: {value}")
                else:
                    print(f"   ❌ {key}: {value} (expected: {expected})")
                    self.issues.append(f"{key} is '{value}' but should be '{expected}'")
                    all_good = False
            
            # Check potentially problematic settings
            print("\n📋 Other Important Settings:")
            
            # API logging (should be disabled)
            log_api = config['IBGateway'].get('logApi', 'not set')
            if log_api.lower() in ['false', '0', 'no']:
                print(f"   ✅ logApi: {log_api} (disabled - good)")
            else:
                print(f"   ⚠️  logApi: {log_api}")
                self.warnings.append("API logging is enabled - may cause delays")
            
            # Show all IBGateway settings
            print("\n📄 All [IBGateway] Settings:")
            for key, value in config['IBGateway'].items():
                print(f"   {key} = {value}")
        else:
            print("❌ [IBGateway] section not found in jts.ini!")
            self.issues.append("[IBGateway] section missing")
            all_good = False
        
        return all_good
    
    def check_firewall(self):
        """Check firewall rules"""
        self.print_header("5️⃣  FIREWALL CHECK")
        
        try:
            # Check UFW status
            result = subprocess.run(['sudo', 'ufw', 'status'], 
                                  capture_output=True, text=True, 
                                  timeout=5)
            
            if 'inactive' in result.stdout.lower():
                print("✅ UFW firewall is inactive (no blocking)")
                self.successes.append("Firewall not blocking")
                return True
            elif 'active' in result.stdout.lower():
                print("⚠️  UFW firewall is active")
                print("   Checking localhost rules...")
                
                # Localhost should always be allowed
                print("   💡 Localhost (127.0.0.1) traffic is typically not filtered")
                print("      But if you have strict rules, this could be an issue")
                self.warnings.append("Firewall active - verify localhost allowed")
                return True
                
        except subprocess.TimeoutExpired:
            print("⚠️  Cannot check firewall (sudo timeout)")
        except Exception as e:
            print(f"⚠️  Cannot check firewall: {e}")
        
        return True
    
    def test_ib_insync_connection(self):
        """Test actual ib_insync connection"""
        self.print_header("6️⃣  IB-INSYNC CONNECTION TEST")
        
        try:
            from ib_insync import IB
            
            print("📡 Attempting ib-insync connection...")
            print("   Host: 127.0.0.1")
            print("   Port: 4002")
            print("   Client ID: 999")
            print("   Timeout: 10 seconds")
            print()
            
            ib = IB()
            
            # Try to connect with timeout
            import asyncio
            
            async def try_connect():
                try:
                    await asyncio.wait_for(
                        ib.connectAsync('127.0.0.1', 4002, clientId=999),
                        timeout=10.0
                    )
                    return True
                except asyncio.TimeoutError:
                    return False
                except Exception as e:
                    return str(e)
            
            # Run async connection
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(try_connect())
            
            if result is True:
                print("✅ CONNECTION SUCCESSFUL!")
                print(f"   Managed accounts: {ib.managedAccounts()}")
                self.successes.append("ib-insync connection works!")
                ib.disconnect()
                return True
            elif result is False:
                print("❌ CONNECTION TIMEOUT")
                print("   The connection attempt timed out during handshake")
                print()
                print("   🔍 THIS IS THE PROBLEM:")
                print("   Gateway is listening, socket connects, but API handshake fails")
                print()
                print("   Possible causes:")
                print("   1. API not enabled in Gateway GUI (most likely)")
                print("   2. Incompatible API version")
                print("   3. Gateway in error state")
                print("   4. Corrupted Gateway installation")
                self.issues.append("API handshake timeout - check Gateway GUI API settings")
                return False
            else:
                print(f"❌ CONNECTION ERROR: {result}")
                self.issues.append(f"Connection error: {result}")
                return False
                
        except ImportError:
            print("❌ ib-insync library not available")
            print("   Install with: pip install ib-insync")
            self.warnings.append("Cannot test connection - ib-insync not installed")
            return False
        except Exception as e:
            print(f"❌ Connection test error: {e}")
            self.issues.append(f"Connection test failed: {e}")
            return False
    
    def generate_report(self):
        """Generate final diagnostic report"""
        self.print_header("📊 DIAGNOSTIC REPORT")
        
        print(f"\n✅ Successes: {len(self.successes)}")
        for success in self.successes:
            print(f"   • {success}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.issues:
            print(f"\n❌ Issues Found: {len(self.issues)}")
            for issue in self.issues:
                print(f"   • {issue}")
        
        print("\n" + "=" * 70)
        
        if not self.issues:
            print("🎉 ALL CHECKS PASSED!")
            print("   Your Gateway should be able to accept API connections")
        else:
            print("🔧 ISSUES DETECTED - See above for details")
            print("\n💡 RECOMMENDED ACTIONS:")
            
            if "Gateway is NOT running" in str(self.issues):
                print("   1. Start IB Gateway")
            
            if "Port 4002 is NOT listening" in str(self.issues):
                print("   1. Wait for Gateway to fully start")
                print("   2. Check Gateway error messages")
                print("   3. Restart Gateway")
            
            if "API handshake timeout" in str(self.issues):
                print("   1. Open IB Gateway GUI")
                print("   2. Go to: Configure > Settings > API > Settings")
                print("   3. Enable 'Enable ActiveX and Socket Clients'")
                print("   4. Verify Socket port: 4002")
                print("   5. Add 127.0.0.1 to Trusted IP Addresses")
                print("   6. Click Apply/OK")
                print("   7. May need to restart Gateway after changes")
        
        print("=" * 70)
    
    def run_full_diagnostic(self):
        """Run complete diagnostic sequence"""
        print("🔍 IB GATEWAY API COMPREHENSIVE DIAGNOSTIC")
        print(f"Timestamp: {datetime.now()}")
        print(f"System: {os.uname().sysname} {os.uname().release}")
        
        # Run all checks
        gateway_running = self.check_gateway_process()
        
        if gateway_running:
            port_listening = self.check_port_listening()
            socket_works = self.check_socket_connection()
        else:
            port_listening = False
            socket_works = False
        
        config_ok = self.check_jts_ini()
        firewall_ok = self.check_firewall()
        
        # Only test connection if everything else looks good
        if gateway_running and port_listening and socket_works:
            connection_ok = self.test_ib_insync_connection()
        else:
            print("\n⚠️  Skipping connection test - prerequisites not met")
            connection_ok = False
        
        # Generate report
        self.generate_report()
        
        return len(self.issues) == 0

if __name__ == "__main__":
    diagnostic = GatewayDiagnostic()
    success = diagnostic.run_full_diagnostic()
    sys.exit(0 if success else 1)
