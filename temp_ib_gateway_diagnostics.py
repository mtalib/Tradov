#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_ib_gateway_diagnostics.py
Purpose: Comprehensive IB Gateway diagnostics for Ubuntu/Wayland environment
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 12:15:00

Module Description:
    Advanced diagnostic tool for troubleshooting Interactive Brokers Gateway 
    connectivity issues in the Spyder trading system. Provides comprehensive
    system analysis including process monitoring, port scanning, firewall
    checking, configuration validation, and connectivity testing. Specifically
    optimized for Ubuntu 25.04 with Wayland and IB Gateway v10.39.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import socket
import subprocess
import sys
import time
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️  psutil not installed. Some features will be limited.")
    print("   Install: pip install psutil")

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2  # Master Client ID for Spyder system
PAPER_TRADING_PORT = 4002
LIVE_TRADING_PORT = 4001
DEFAULT_PORTS = [LIVE_TRADING_PORT, PAPER_TRADING_PORT, 7496, 7497]
IB_GATEWAY_VERSION = "10.39"
TWS_MAJOR_VRSN = "1039"
DOCKER_IMAGE = "gnzsnz/ib-gateway-docker:latest"
DOCKER_CONTAINER = "ib_gateway"

# ==============================================================================
# DIAGNOSTIC RESULT ENUMS
# ==============================================================================
class DiagnosticStatus(Enum):
    """Status codes for diagnostic checks"""
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    WARNING = "⚠️  WARNING"
    INFO = "ℹ️  INFO"
    SKIPPED = "⏭️  SKIPPED"

# ==============================================================================
# COLOR CODES FOR TERMINAL OUTPUT
# ==============================================================================
class Colors:
    """Terminal color codes for enhanced output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# ==============================================================================
# OUTPUT FORMATTING FUNCTIONS
# ==============================================================================
def print_header(text: str) -> None:
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text: str) -> None:
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text: str) -> None:
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text: str) -> None:
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text: str) -> None:
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

# ==============================================================================
# DIAGNOSTIC FUNCTIONS
# ==============================================================================
def check_processes() -> bool:
    """
    Check for IB Gateway related processes.
    
    Returns:
        True if Gateway processes found, False otherwise
    """
    print_header("Process Check")
    
    if not PSUTIL_AVAILABLE:
        print_warning("psutil not available, using fallback method")
        return check_processes_fallback()
    
    gateway_processes = []
    java_processes = []
    docker_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            # Check for Docker containers
            if 'docker' in proc.info['name'].lower():
                if DOCKER_CONTAINER in cmdline or 'ib-gateway' in cmdline:
                    docker_processes.append(proc)
                    print_success(f"Docker IB Gateway Container: PID {proc.info['pid']}")
            
            # Check for IB Gateway processes
            if 'ibgateway' in cmdline.lower() or 'interactive brokers' in cmdline.lower():
                gateway_processes.append(proc)
                print_success(f"IB Gateway Process Found: PID {proc.info['pid']}")
                print_info(f"Command: {cmdline[:100]}...")
                
            # Check for Java TWS/Gateway processes
            elif 'java' in proc.info['name'].lower():
                if any(term in cmdline.lower() for term in ['tws', 'gateway', TWS_MAJOR_VRSN]):
                    java_processes.append(proc)
                    print_success(f"Java TWS/Gateway Process: PID {proc.info['pid']}")
                    
                    # Check memory usage
                    try:
                        mem_info = proc.memory_info()
                        mem_mb = mem_info.rss / (1024 * 1024)
                        print_info(f"Memory usage: {mem_mb:.1f} MB")
                    except:
                        pass
                    
                    print_info(f"Command: {cmdline[:100]}...")
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Summary
    total_processes = len(gateway_processes) + len(java_processes) + len(docker_processes)
    
    if total_processes > 0:
        print(f"\n{Colors.GREEN}Summary:{Colors.END}")
        print(f"  Gateway processes: {len(gateway_processes)}")
        print(f"  Java processes: {len(java_processes)}")
        print(f"  Docker containers: {len(docker_processes)}")
        return True
    else:
        print_error("No IB Gateway processes found!")
        print_info("IB Gateway might not be running")
        return False

def check_processes_fallback() -> bool:
    """
    Fallback process checking without psutil.
    
    Returns:
        True if processes found, False otherwise
    """
    try:
        # Check using ps command
        result = subprocess.run(
            ['ps', 'aux'], 
            capture_output=True, 
            text=True
        )
        
        found_processes = False
        for line in result.stdout.split('\n'):
            if 'java' in line and any(term in line.lower() for term in ['gateway', 'tws', TWS_MAJOR_VRSN]):
                print_success(f"Found process: {line[:120]}...")
                found_processes = True
        
        # Check Docker
        try:
            docker_result = subprocess.run(
                ['docker', 'ps'], 
                capture_output=True, 
                text=True
            )
            if DOCKER_CONTAINER in docker_result.stdout or 'ib-gateway' in docker_result.stdout:
                print_success(f"Docker container '{DOCKER_CONTAINER}' is running")
                found_processes = True
        except:
            pass
        
        return found_processes
        
    except Exception as e:
        print_error(f"Process check failed: {e}")
        return False

def check_ports() -> Tuple[List[int], Dict[int, str]]:
    """
    Check if IB Gateway ports are listening.
    
    Returns:
        Tuple of (listening_ports, port_details)
    """
    print_header("Port Check")
    
    listening_ports = []
    port_details = {}
    
    for port in DEFAULT_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                port_type = get_port_type(port)
                print_success(f"Port {port} is open and accepting connections ({port_type})")
                listening_ports.append(port)
                port_details[port] = port_type
            else:
                print_error(f"Port {port} is not accessible (error code: {result})")
        except socket.timeout:
            print_error(f"Port {port} connection timed out")
        except Exception as e:
            print_error(f"Port {port} check failed: {e}")
        finally:
            sock.close()
    
    # Check what's actually listening on these ports
    print_info("\nChecking what's listening on these ports...")
    try:
        # Try netstat first
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        if result.returncode == 0:
            analyze_netstat_output(result.stdout, DEFAULT_PORTS)
    except FileNotFoundError:
        # Try ss as alternative
        try:
            result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
            if result.returncode == 0:
                analyze_netstat_output(result.stdout, DEFAULT_PORTS)
        except FileNotFoundError:
            print_warning("Neither netstat nor ss available for detailed port analysis")
    
    if listening_ports:
        print_info(f"\n{Colors.GREEN}Active ports: {listening_ports}{Colors.END}")
        print_info(f"Master Client ID configured: {MASTER_CLIENT_ID}")
    
    return listening_ports, port_details

def get_port_type(port: int) -> str:
    """Get description for a port number"""
    port_types = {
        LIVE_TRADING_PORT: "Live Trading",
        PAPER_TRADING_PORT: "Paper Trading",
        7496: "TWS Live",
        7497: "TWS Paper"
    }
    return port_types.get(port, "Unknown")

def analyze_netstat_output(output: str, ports: List[int]) -> None:
    """Analyze netstat/ss output for port information"""
    lines = output.split('\n')
    for line in lines:
        for port in ports:
            if f':{port}' in line and 'LISTEN' in line:
                print_info(f"Port {port} listener: {line.strip()[:100]}")

def check_firewall() -> None:
    """Check firewall status and rules"""
    print_header("Firewall Check")
    
    try:
        # Check UFW status
        result = subprocess.run(
            ['sudo', '-n', 'ufw', 'status', 'verbose'], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print_info("UFW Firewall Status:")
            
            if 'Status: active' in result.stdout:
                print_warning("UFW is active - checking for IB Gateway rules...")
                
                # Check for specific port rules
                for port in DEFAULT_PORTS:
                    if str(port) in result.stdout:
                        print_success(f"Port {port} appears to be allowed in firewall")
                    else:
                        print_warning(f"Port {port} might be blocked - add rule: sudo ufw allow {port}/tcp")
            else:
                print_success("UFW is inactive - no firewall blocking")
                
            # Show relevant rules
            for line in result.stdout.split('\n'):
                if any(str(port) in line for port in DEFAULT_PORTS):
                    print_info(f"  {line.strip()}")
        else:
            if 'sudo: a password is required' in result.stderr:
                print_info("Cannot check UFW without sudo password")
                print_info("Run manually: sudo ufw status verbose")
            else:
                print_info("UFW not available or accessible")
            
    except subprocess.TimeoutExpired:
        print_warning("Firewall check timed out")
    except Exception as e:
        print_warning(f"Could not check UFW: {e}")
    
    # Check iptables (basic check)
    try:
        result = subprocess.run(
            ['sudo', '-n', 'iptables', '-L', '-n'], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        
        if result.returncode == 0 and 'ACCEPT' in result.stdout:
            print_info("iptables rules detected - manual review recommended")
    except:
        pass

def check_ib_gateway_config() -> None:
    """Check for IB Gateway configuration files and settings"""
    print_header("IB Gateway Configuration Check")
    
    # Common IB Gateway installation paths
    possible_paths = [
        Path.home() / "IBJts",
        Path.home() / ".wine" / "drive_c" / "IBJts",
        Path("/opt/IBJts"),
        Path("/usr/local/IBJts"),
        Path.home() / "Jts",
        Path.home() / "IB"
    ]
    
    found_installations = []
    
    for base_path in possible_paths:
        if base_path.exists():
            found_installations.append(base_path)
            print_success(f"IB Installation found: {base_path}")
            
            # Look for version 10.39
            version_paths = [
                base_path / "ibgateway" / TWS_MAJOR_VRSN,
                base_path / "ibgateway" / "latest",
                base_path / TWS_MAJOR_VRSN
            ]
            
            for version_path in version_paths:
                if version_path.exists():
                    print_success(f"  Gateway version found: {version_path}")
                    
                    # Check for JAR files
                    jar_files = list(version_path.glob("*.jar"))
                    if jar_files:
                        print_info(f"  JAR files: {len(jar_files)} found")
            
            # Look for config files
            config_patterns = ["*.xml", "*.properties", "*.ini", "*.conf"]
            config_files = []
            
            for pattern in config_patterns:
                config_files.extend(list(base_path.rglob(pattern)))
            
            if config_files:
                print_info(f"  Config files found: {len(config_files)}")
                
                # Show important config files
                important_configs = ['jts.ini', 'tws.xml', 'settings.xml', 'api-settings.xml']
                for config in config_files[:10]:  # Show first 10
                    if any(imp in config.name.lower() for imp in important_configs):
                        print_info(f"    ⭐ {config.name}: {config}")
                    else:
                        print_info(f"    - {config.name}")
    
    if not found_installations:
        print_error("No IB Gateway installations found in common locations")
        print_info("IB Gateway might be:")
        print_info("  1. Installed in a custom location")
        print_info("  2. Running in a Docker container")
        print_info(f"  3. Not installed - download from IBKR website")
    
    # Check Docker installation
    check_docker_installation()

def check_docker_installation() -> None:
    """Check for Docker-based IB Gateway installation"""
    print_info("\nChecking Docker installation...")
    
    try:
        # Check if Docker is installed
        docker_version = subprocess.run(
            ['docker', '--version'],
            capture_output=True,
            text=True
        )
        
        if docker_version.returncode == 0:
            print_success(f"Docker installed: {docker_version.stdout.strip()}")
            
            # Check for IB Gateway container
            result = subprocess.run(
                ['docker', 'ps', '-a', '--format', 'table {{.Names}}\t{{.Image}}\t{{.Status}}'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'ib-gateway' in line.lower() or DOCKER_CONTAINER in line:
                        print_success(f"Docker container found: {line}")
                        
                        # Check container details
                        container_name = line.split()[0] if line else DOCKER_CONTAINER
                        check_docker_container_details(container_name)
    except FileNotFoundError:
        print_info("Docker not installed")
    except Exception as e:
        print_warning(f"Docker check failed: {e}")

def check_docker_container_details(container_name: str) -> None:
    """Get detailed information about Docker container"""
    try:
        # Get container environment variables
        result = subprocess.run(
            ['docker', 'inspect', container_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            import json
            config = json.loads(result.stdout)
            if config:
                env_vars = config[0].get('Config', {}).get('Env', [])
                print_info("  Container environment:")
                for env in env_vars:
                    if any(key in env for key in ['TWS_', 'IB_', 'TRADING_MODE']):
                        print_info(f"    {env}")
    except:
        pass

def test_basic_socket_connection() -> None:
    """Test basic socket connectivity to IB Gateway"""
    print_header("Socket Connection Test")
    
    ports_to_test = [PAPER_TRADING_PORT, LIVE_TRADING_PORT]
    
    for port in ports_to_test:
        print_info(f"\nTesting socket connection to 127.0.0.1:{port}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        try:
            start_time = time.time()
            sock.connect(('127.0.0.1', port))
            connect_time = time.time() - start_time
            print_success(f"Socket connected to port {port} in {connect_time:.3f}s")
            
            # Try to send API version handshake (might fail but connection works)
            try:
                # IB API initial handshake
                sock.send(b'API\0')
                sock.settimeout(2)
                response = sock.recv(1024)
                if response:
                    print_success(f"Received response from port {port}: {len(response)} bytes")
            except socket.timeout:
                print_info(f"No immediate response from port {port} (normal for IB Gateway)")
            except Exception as e:
                print_info(f"Could not complete handshake (normal): {e}")
                
        except socket.timeout:
            print_error(f"Connection to port {port} timed out after 10 seconds")
        except ConnectionRefusedError:
            print_error(f"Connection to port {port} refused - nothing listening")
        except Exception as e:
            print_error(f"Connection to port {port} failed: {e}")
        finally:
            sock.close()

def check_system_info() -> None:
    """Check system information relevant to IB Gateway"""
    print_header("System Information")
    
    # Python version
    print_info(f"Python version: {sys.version}")
    
    # Operating System
    print_info(f"Operating System: {os.uname()}")
    
    # Display environment
    session_type = os.environ.get('XDG_SESSION_TYPE', 'unknown')
    print_info(f"Session type: {session_type}")
    
    if session_type == 'wayland':
        print_success("Running on Wayland (as expected for Ubuntu 25.04)")
        if os.environ.get('WAYLAND_DISPLAY'):
            print_info(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY')}")
    
    if os.environ.get('DISPLAY'):
        print_info(f"X11 DISPLAY: {os.environ.get('DISPLAY')}")
    
    # Check Java
    try:
        result = subprocess.run(
            ['java', '-version'], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            java_output = result.stderr if result.stderr else result.stdout
            version_line = java_output.split('\n')[0]
            print_success(f"Java installed: {version_line}")
            
            # Check Java memory settings
            try:
                max_heap = subprocess.run(
                    ['java', '-XX:+PrintFlagsFinal', '-version'],
                    capture_output=True,
                    text=True
                )
                for line in max_heap.stderr.split('\n'):
                    if 'MaxHeapSize' in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            heap_mb = int(parts[3]) / (1024 * 1024)
                            print_info(f"Java Max Heap: {heap_mb:.0f} MB")
                            break
            except:
                pass
        else:
            print_error("Java is not installed or not accessible")
    except FileNotFoundError:
        print_error("Java command not found in PATH")
    except Exception as e:
        print_error(f"Could not check Java: {e}")
    
    # Environment variables
    print_info("\nRelevant environment variables:")
    relevant_vars = ['TWS_MAJOR_VRSN', 'IB_GATEWAY_PORT', 'IB_GATEWAY_HOST', 'PATH']
    for var in relevant_vars:
        value = os.environ.get(var)
        if value:
            print_info(f"  {var}: {value[:100]}")  # Truncate long values

def check_ib_async_version() -> None:
    """Check ib_async installation and compatibility"""
    print_header("ib_async Library Check")
    
    try:
        import ib_async
        print_success(f"ib_async is installed: version {ib_async.__version__}")
        
        # Test import of key components
        from ib_async import IB, Stock, Option, Contract
        print_success("Key ib_async components imported successfully")
        
        # Check for connection capability
        print_info(f"Ready to connect with Master Client ID: {MASTER_CLIENT_ID}")
        
        # Test basic functionality
        test_contract = Stock('SPY', 'SMART', 'USD')
        print_success(f"Test contract created: {test_contract}")
        
    except ImportError as e:
        print_error(f"ib_async not installed or import failed: {e}")
        print_info("Install with: pip install ib_async")
    except Exception as e:
        print_error(f"ib_async check failed: {e}")

def generate_diagnostic_report() -> Dict[str, Any]:
    """Generate a comprehensive diagnostic report"""
    report = {
        'timestamp': datetime.now().isoformat(),
        'master_client_id': MASTER_CLIENT_ID,
        'gateway_version': IB_GATEWAY_VERSION,
        'tws_major_vrsn': TWS_MAJOR_VRSN,
        'checks_performed': [],
        'issues_found': [],
        'recommendations': []
    }
    
    return report

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main diagnostic execution"""
    print_header("SPYDER IB Gateway Diagnostics Tool")
    print_info(f"Diagnostic run started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Master Client ID: {MASTER_CLIENT_ID}")
    print_info(f"Target Gateway Version: {IB_GATEWAY_VERSION}")
    print_info(f"Docker Image: {DOCKER_IMAGE}")
    
    # Run all diagnostic checks
    processes_found = check_processes()
    listening_ports, port_details = check_ports()
    check_firewall()
    check_ib_gateway_config()
    test_basic_socket_connection()
    check_system_info()
    check_ib_async_version()
    
    # Generate summary
    print_header("Diagnostic Summary")
    
    all_good = True
    
    if processes_found:
        print_success("IB Gateway processes are running")
    else:
        print_error("IB Gateway processes NOT found")
        print_info("Solution: Start IB Gateway application or Docker container")
        all_good = False
    
    if listening_ports:
        print_success(f"Found {len(listening_ports)} listening ports: {listening_ports}")
        for port, details in port_details.items():
            print_info(f"  Port {port}: {details}")
    else:
        print_error("No IB Gateway ports are listening")
        print_info("Solution: Check IB Gateway API configuration")
        all_good = False
    
    if not processes_found or not listening_ports:
        print_header("Recommended Actions")
        
        if not processes_found:
            print_info("1. Start IB Gateway:")
            print_info("   Option A: Start IB Gateway application manually")
            print_info("   Option B: Start Docker container:")
            print_info(f"     docker run -d --name {DOCKER_CONTAINER} \\")
            print_info(f"       -p {PAPER_TRADING_PORT}:{PAPER_TRADING_PORT} \\")
            print_info(f"       -e TWS_MAJOR_VRSN={TWS_MAJOR_VRSN} \\")
            print_info(f"       -e TRADING_MODE=paper \\")
            print_info(f"       {DOCKER_IMAGE}")
            
        print_info("\n2. Configure API Settings in IB Gateway:")
        print_info("   - Configure -> Settings -> API -> Settings")
        print_info("   - Enable ActiveX and Socket Clients: ✓")
        print_info(f"   - Socket port: {PAPER_TRADING_PORT} (paper) or {LIVE_TRADING_PORT} (live)")
        print_info(f"   - Master Client ID: {MASTER_CLIENT_ID}")
        print_info("   - Read-Only API: ☐ (unchecked for trading)")
        print_info("   - Trusted IP Addresses: 127.0.0.1")
        
        print_info("\n3. Apply settings and restart Gateway if needed")
        
        print_info("\n4. Test connection with:")
        print_info("   python temp_ib_gateway_startup_check.py")
    
    if all_good:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 System appears ready for Spyder trading!{Colors.END}")
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some issues need attention - see recommendations above{Colors.END}")
    
    # Save diagnostic report
    report = generate_diagnostic_report()
    report_file = Path(f"ib_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    try:
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print_info(f"\nDiagnostic report saved to: {report_file}")
    except Exception as e:
        print_warning(f"Could not save report: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Diagnostics interrupted by user{Colors.END}")
    except Exception as e:
        print_error(f"Diagnostics failed: {e}")
        import traceback
        traceback.print_exc()