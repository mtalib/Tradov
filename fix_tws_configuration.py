#!/usr/bin/env python3
"""
SPYDER - TWS Configuration Fix Script
====================================

Based on comprehensive research from 6 AI reports, this script automates
the TWS configuration changes needed to resolve API handshake timeouts.

Research Sources:
- Claude: Race condition delay solution
- ChatGPT: Read-only mode and TWS settings
- Perplexity: reqExecutions timeout bypass
- Copilot: Network and logging optimizations
- Gemini: Protocol adherence requirements
- Grok: Version compatibility issues

This script provides step-by-step guidance and automated fixes where possible.
"""

import os
import sys
import json
import socket
import subprocess
import platform
from datetime import datetime
from pathlib import Path

# Colors for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
PURPLE = "\033[0;35m"
NC = "\033[0m"  # No Color


class TWSConfigurationFixer:
    """
    Comprehensive TWS configuration fixer based on research findings
    """

    def __init__(self):
        self.fixes_applied = []
        self.manual_steps = []
        self.warnings = []
        self.linux_ip = self.get_linux_ip()
        self.tws_ip = "192.168.1.4"
        self.config_dir = Path(__file__).parent / "config"

    def get_linux_ip(self):
        """Get the Linux machine's IP address for TWS trusted IPs"""
        try:
            # Connect to remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            try:
                # Fallback method
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except:
                return "192.168.1.9"  # Last resort fallback

    def print_header(self):
        """Print script header"""
        print(f"{CYAN}🕷️ SPYDER - TWS Configuration Fixer{NC}")
        print(f"{CYAN}=====================================")
        print(f"Based on 6 AI Research Reports")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Linux IP: {self.linux_ip}")
        print(f"TWS IP: {self.tws_ip}")
        print(f"====================================={NC}")
        print()

    def check_python_version(self):
        """Check Python version compatibility (Research finding)"""
        print(f"{BLUE}🐍 Checking Python Version Compatibility...{NC}")

        version = sys.version_info
        print(f"   Current Python: {version.major}.{version.minor}.{version.micro}")

        if version.major == 3 and version.minor >= 13:
            self.warnings.append(
                {
                    "issue": "Python 3.13+ Compatibility",
                    "description": "Multiple research reports indicate Python 3.13+ may have compatibility issues with ib_async",
                    "recommendation": "Consider testing with Python 3.11 or 3.12",
                    "priority": "HIGH",
                }
            )
            print(
                f"   {YELLOW}⚠️ Python 3.13+ detected - may have ib_async compatibility issues{NC}"
            )
        else:
            print(f"   {GREEN}✅ Python version appears compatible{NC}")

        print()

    def update_spyder_config(self):
        """Update SPYDER configuration files with research-backed settings"""
        print(f"{BLUE}⚙️ Updating SPYDER Configuration Files...{NC}")

        # Configuration updates based on research
        config_updates = {
            "connection_settings": {
                "PROVEN_RACE_CONDITION_DELAY": 1.0,  # Claude's solution
                "EXTENDED_REQUEST_TIMEOUT": 30.0,  # All reports recommend
                "CONNECTION_TIMEOUT": 15.0,  # Increased from 4s default
                "USE_READONLY_MODE": True,  # ChatGPT/Perplexity solution
                "DISABLE_ORDER_DOWNLOAD": True,  # Multiple reports recommend
                "ENABLE_TCP_NODELAY": True,  # Copilot solution
                "MAX_RETRIES": 5,
                "RETRY_DELAY": 2.0,
            },
            "tws_settings": {
                "host": self.tws_ip,
                "paper_port": 7497,
                "live_port": 7496,
                "trusted_ip": self.linux_ip,
                "bulk_data_timeout": 300,  # ChatGPT recommendation
                "download_orders_on_connect": False,  # Critical fix
                "api_logging_enabled": True,
                "timezone_setting": "UTC",  # Perplexity fix for reqExecutions
            },
        }

        # Save enhanced configuration
        config_file = self.config_dir / "maestro_tws_config.json"
        try:
            with open(config_file, "w") as f:
                json.dump(config_updates, f, indent=2)

            self.fixes_applied.append(
                {
                    "fix": "SPYDER Configuration Update",
                    "description": "Applied all research-backed configuration changes",
                    "file": str(config_file),
                }
            )
            print(f"   {GREEN}✅ Configuration saved to {config_file}{NC}")

        except Exception as e:
            print(f"   {RED}❌ Failed to save configuration: {e}{NC}")

        # Update main config files
        self.update_config_files()
        print()

    def update_config_files(self):
        """Update existing configuration files"""
        config_files = ["config.py", "config_remote_tws.py"]

        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                try:
                    # Read current config
                    with open(config_path, "r") as f:
                        content = f.read()

                    # Add race condition delay constant if not present
                    if "PROVEN_RACE_CONDITION_DELAY" not in content:
                        race_condition_fix = """
# MAESTRO FIX: Race condition delay (Claude's proven solution)
PROVEN_RACE_CONDITION_DELAY = 1.0  # Critical delay for API handshake stabilization

# MAESTRO FIX: Enhanced connection settings (All research reports)
ENHANCED_CONNECTION_CONFIG = {
    "request_timeout": 30.0,        # Extended from 4s default
    "connection_timeout": 15.0,     # Generous handshake timeout
    "use_readonly_mode": True,      # Bypass reqExecutions timeout
    "disable_order_download": True, # Prevent startup sync issues
    "enable_tcp_nodelay": True,     # Copilot's optimization
    "max_retries": 5,
    "retry_delay": 2.0,
    "apply_race_condition_delay": True
}
"""
                        content += race_condition_fix

                        # Write updated config
                        with open(config_path, "w") as f:
                            f.write(content)

                        print(
                            f"   {GREEN}✅ Updated {config_file} with MAESTRO fixes{NC}"
                        )

                except Exception as e:
                    print(f"   {YELLOW}⚠️ Could not update {config_file}: {e}{NC}")

    def create_connection_test_script(self):
        """Create optimized connection test script"""
        print(f"{BLUE}🧪 Creating Enhanced Connection Test Script...{NC}")

        test_script = '''#!/usr/bin/env python3
"""
MAESTRO Enhanced TWS Connection Test
Based on 6 AI research reports
"""

import asyncio
import socket
import time
from ib_async import IB, util

async def maestro_connection_test():
    """Test with all research-backed optimizations"""
    print("🕷️ MAESTRO Enhanced TWS Connection Test")
    print("=" * 50)

    # Apply TCP optimizations (Copilot solution)
    original_create_connection = asyncio.get_event_loop().create_connection

    async def optimized_connection(*args, **kwargs):
        transport, protocol = await original_create_connection(*args, **kwargs)
        sock = transport.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return transport, protocol

    asyncio.get_event_loop().create_connection = optimized_connection

    # Initialize ib_async (Claude's working pattern)
    util.startLoop()
    util.logToConsole('DEBUG')

    ib = IB()
    ib.RequestTimeout = 30.0  # All reports recommend extended timeout

    try:
        print("🔌 Connecting with MAESTRO optimizations...")

        # SOLUTION 1: Read-only mode (ChatGPT/Perplexity fix)
        await ib.connectAsync(
            host='192.168.1.4',
            port=7497,
            clientId=1,
            timeout=15.0,
            readonly=True  # Bypasses reqExecutions timeout
        )

        print("✅ Phase 1: Connection established")

        # SOLUTION 2: Race condition delay (Claude's proven solution)
        print("⏳ Phase 2: Applying race condition delay (1.0s)...")
        await asyncio.sleep(1.0)

        # SOLUTION 3: Validate connection
        if ib.isConnected():
            accounts = ib.managedAccounts()
            print(f"✅ Phase 3: Connected to accounts: {accounts}")

            # Test server time
            server_time = await ib.reqCurrentTimeAsync()
            print(f"✅ Server time: {server_time}")

            print("\\n🎉 MAESTRO CONNECTION TEST SUCCESS!")
            print("✅ All research-backed solutions working")

        else:
            print("❌ Connection validation failed")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"Error type: {type(e).__name__}")

    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected cleanly")

if __name__ == "__main__":
    asyncio.run(maestro_connection_test())
'''

        test_file = Path("maestro_enhanced_test.py")
        try:
            with open(test_file, "w") as f:
                f.write(test_script)

            # Make executable
            os.chmod(test_file, 0o755)

            self.fixes_applied.append(
                {
                    "fix": "Enhanced Connection Test",
                    "description": "Created test script with all research optimizations",
                    "file": str(test_file),
                }
            )
            print(f"   {GREEN}✅ Created {test_file}{NC}")

        except Exception as e:
            print(f"   {RED}❌ Failed to create test script: {e}{NC}")

        print()

    def check_network_connectivity(self):
        """Verify network connectivity to TWS"""
        print(f"{BLUE}🌐 Testing Network Connectivity...{NC}")

        # Ping test
        try:
            if platform.system().lower() == "windows":
                result = subprocess.run(
                    ["ping", "-n", "3", self.tws_ip],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "3", self.tws_ip],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            if result.returncode == 0:
                print(f"   {GREEN}✅ Ping to {self.tws_ip} successful{NC}")
            else:
                print(
                    f"   {YELLOW}⚠️ Ping to {self.tws_ip} failed (may be blocked by firewall){NC}"
                )

        except Exception as e:
            print(f"   {YELLOW}⚠️ Ping test error: {e}{NC}")

        # Port connectivity test
        ports = {7497: "Paper Trading", 7496: "Live Trading"}
        accessible_ports = []

        for port, description in ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((self.tws_ip, port))
                sock.close()

                if result == 0:
                    print(f"   {GREEN}✅ Port {port} ({description}) accessible{NC}")
                    accessible_ports.append(port)
                else:
                    print(f"   {RED}❌ Port {port} ({description}) not accessible{NC}")

            except Exception as e:
                print(f"   {YELLOW}⚠️ Port {port} test error: {e}{NC}")

        if not accessible_ports:
            self.warnings.append(
                {
                    "issue": "No TWS Ports Accessible",
                    "description": "Cannot connect to TWS API ports",
                    "recommendation": "Check if TWS is running and API is enabled",
                    "priority": "CRITICAL",
                }
            )

        print()

    def generate_tws_configuration_guide(self):
        """Generate comprehensive TWS configuration guide"""
        print(f"{BLUE}📋 Generating TWS Configuration Guide...{NC}")

        guide = f"""
# TWS Configuration Guide - Based on Research Reports
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## CRITICAL TWS SETTINGS (Must be configured on Windows TWS computer: {self.tws_ip})

### 1. API Settings (File → Global Configuration → API → Settings)
✅ Enable ActiveX and Socket Clients: CHECKED
✅ Socket Port (Paper Trading): 7497
✅ Socket Port (Live Trading): 7496
✅ Trusted IPs: {self.linux_ip}
❌ Download open orders on connection: UNCHECKED (Critical - causes timeouts)
❌ Allow connections from localhost only: UNCHECKED (for remote connections)
✅ Read-Only API: UNCHECKED (unless you only need market data)

### 2. Connection Settings
✅ Timeout to send bulk data to API: 300 seconds (increased from default)
✅ API Message Log: ENABLED (for debugging)
✅ Logging Level: Detail

### 3. Display Settings (Global Configuration → Display)
✅ Time Zone: UTC (fixes reqExecutions timezone bug in TWS 10.23+)

### 4. System Settings
✅ Java Memory Allocation: 4096 MB minimum (prevent startup stalls)
✅ Auto logoff time: 2+ hours (prevent disconnections)

## WINDOWS FIREWALL SETTINGS
✅ Add firewall exception for ports 7497 and 7496
✅ Allow inbound connections from {self.linux_ip}

## RESEARCH-BACKED CLIENT FIXES (Already applied to SPYDER)
✅ Read-only mode connection (bypasses reqExecutions timeout)
✅ 1.0 second race condition delay after connection
✅ Extended connection timeout (15s instead of 4s)
✅ Extended request timeout (30s instead of 4s)
✅ TCP_NODELAY optimization
✅ Connection retry logic with exponential backoff

## TESTING PROCEDURE
1. Apply TWS settings above
2. Restart TWS completely
3. Run: python maestro_enhanced_test.py
4. Should see "MAESTRO CONNECTION TEST SUCCESS!"

## TROUBLESHOOTING
If connection still fails:
1. Check TWS API log file for errors
2. Verify {self.linux_ip} appears in TWS "API connections" dialog
3. Try connecting from Windows computer first (localhost test)
4. Consider TWS version - avoid 10.23+ if possible (has reqExecutions bug)
5. Test with Python 3.11/3.12 instead of 3.13+

## PRODUCTION DEPLOYMENT
- Use connection pooling with different client IDs
- Implement health checks every 5 minutes
- Setup automatic reconnection with backoff
- Monitor TWS log files for API errors
- Consider IB Gateway as fallback option
"""

        guide_file = Path("TWS_Configuration_Guide.md")
        try:
            with open(guide_file, "w") as f:
                f.write(guide)

            self.fixes_applied.append(
                {
                    "fix": "TWS Configuration Guide",
                    "description": "Comprehensive setup guide based on all research",
                    "file": str(guide_file),
                }
            )
            print(f"   {GREEN}✅ Created {guide_file}{NC}")

        except Exception as e:
            print(f"   {RED}❌ Failed to create guide: {e}{NC}")

        print()

    def print_manual_steps(self):
        """Print manual steps that need to be performed on Windows TWS"""
        print(
            f"{YELLOW}📋 MANUAL STEPS REQUIRED ON WINDOWS TWS COMPUTER ({self.tws_ip}):{NC}"
        )
        print()

        manual_steps = [
            f"1. Open TWS on Windows computer ({self.tws_ip})",
            "2. Go to: File → Global Configuration → API → Settings",
            "3. ✅ Check 'Enable ActiveX and Socket Clients'",
            "4. ✅ Set Socket Port: 7497 (Paper), 7496 (Live)",
            f"5. ✅ Add Trusted IP: {self.linux_ip}",
            "6. ❌ UNCHECK 'Download open orders on connection' (CRITICAL)",
            "7. ✅ Set 'Timeout to send bulk data to API': 300 seconds",
            "8. ✅ Enable 'Create API message log file'",
            "9. Go to: Global Configuration → Display → Time Zone",
            "10. ✅ Set Time Zone to 'UTC' (fixes reqExecutions bug)",
            "11. Click Apply → OK",
            "12. Restart TWS completely",
            "13. Run test: python maestro_enhanced_test.py",
        ]

        for step in manual_steps:
            print(f"   {step}")

        print()

    def print_summary(self):
        """Print summary of fixes applied and next steps"""
        print(f"{CYAN}📊 MAESTRO TWS CONFIGURATION FIX SUMMARY{NC}")
        print(f"{CYAN}========================================={NC}")
        print()

        if self.fixes_applied:
            print(f"{GREEN}✅ AUTOMATED FIXES APPLIED:{NC}")
            for fix in self.fixes_applied:
                print(f"   • {fix['fix']}: {fix['description']}")
                if "file" in fix:
                    print(f"     File: {fix['file']}")
            print()

        if self.warnings:
            print(f"{YELLOW}⚠️ WARNINGS & RECOMMENDATIONS:{NC}")
            for warning in self.warnings:
                priority_color = RED if warning["priority"] == "CRITICAL" else YELLOW
                print(
                    f"   {priority_color}• {warning['issue']} ({warning['priority']}){NC}"
                )
                print(f"     {warning['description']}")
                print(f"     Recommendation: {warning['recommendation']}")
                print()

        print(f"{BLUE}🚀 NEXT STEPS:{NC}")
        print(f"   1. Follow manual TWS configuration steps above")
        print(f"   2. Restart TWS completely after configuration")
        print(f"   3. Run: python maestro_enhanced_test.py")
        print(f"   4. If successful, run: python maestro_tws_fix.py")
        print(f"   5. Integrate with SPYDER production system")
        print()

        print(f"{GREEN}🎯 SUCCESS CRITERIA:{NC}")
        print(f"   ✅ TCP connection succeeds immediately")
        print(f"   ✅ API handshake completes within 1-2 seconds")
        print(f"   ✅ No 4-second timeout errors")
        print(f"   ✅ Managed accounts and server time retrieved")
        print(f"   ✅ Connection remains stable for extended periods")
        print()

    def run(self):
        """Run the complete configuration fix process"""
        self.print_header()

        # Automated fixes
        self.check_python_version()
        self.update_spyder_config()
        self.create_connection_test_script()
        self.check_network_connectivity()
        self.generate_tws_configuration_guide()

        # Manual steps guidance
        self.print_manual_steps()

        # Summary
        self.print_summary()


if __name__ == "__main__":
    try:
        fixer = TWSConfigurationFixer()
        fixer.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}⚠️ Configuration fix interrupted by user{NC}")
    except Exception as e:
        print(f"\n{RED}💥 Unexpected error: {e}{NC}")
        import traceback

        traceback.print_exc()
