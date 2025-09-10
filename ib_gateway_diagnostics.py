#!/usr/bin/env python3
"""
IB Gateway Diagnostics for Ubuntu/Wayland
Comprehensive troubleshooting for Interactive Brokers Gateway connectivity
"""

import os
import socket
import subprocess
import sys
import time
import psutil
from pathlib import Path

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

def check_processes():
    """Check for IB Gateway related processes"""
    print_header("Process Check")
    
    gateway_processes = []
    java_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            if 'ibgateway' in cmdline.lower() or 'interactive brokers' in cmdline.lower():
                gateway_processes.append(proc)
                print_success(f"IB Gateway Process Found: PID {proc.info['pid']}")
                print_info(f"Command: {cmdline[:100]}...")
                
            elif 'java' in proc.info['name'].lower() and ('tws' in cmdline.lower() or 'gateway' in cmdline.lower()):
                java_processes.append(proc)
                print_success(f"Java TWS/Gateway Process: PID {proc.info['pid']}")
                print_info(f"Command: {cmdline[:100]}...")
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if not gateway_processes and not java_processes:
        print_error("No IB Gateway processes found!")
        print_info("IB Gateway might not be running")
    
    return len(gateway_processes) > 0 or len(java_processes) > 0

def check_ports():
    """Check if IB Gateway ports are listening"""
    print_header("Port Check")
    
    ports_to_check = [4001, 4002, 7496, 7497]  # Common IB ports
    listening_ports = []
    
    for port in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        try:
            result = sock.connect_ex(('127.0.0.1', port))
            if result == 0:
                print_success(f"Port {port} is open and accepting connections")
                listening_ports.append(port)
            else:
                print_error(f"Port {port} is not accessible (error code: {result})")
        except Exception as e:
            print_error(f"Port {port} check failed: {e}")
        finally:
            sock.close()
    
    # Check what's actually listening on these ports
    print_info("Checking what's listening on these ports...")
    try:
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            for port in ports_to_check:
                if f':{port}' in line and 'LISTEN' in line:
                    print_success(f"Port {port} listener: {line.strip()}")
    except Exception as e:
        print_warning(f"Could not run netstat: {e}")
        
        # Try ss as alternative
        try:
            result = subprocess.run(['ss', '-tlnp'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                for port in ports_to_check:
                    if f':{port}' in line and 'LISTEN' in line:
                        print_success(f"Port {port} listener: {line.strip()}")
        except Exception as e2:
            print_warning(f"Could not run ss either: {e2}")
    
    return listening_ports

def check_firewall():
    """Check firewall status"""
    print_header("Firewall Check")
    
    try:
        # Check UFW status
        result = subprocess.run(['sudo', 'ufw', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            print_info("UFW Status:")
            print(result.stdout)
            
            if 'Status: active' in result.stdout:
                print_warning("UFW is active - check if IB ports are allowed")
            else:
                print_success("UFW is inactive - no firewall blocking")
        else:
            print_info("UFW not available or accessible")
            
    except Exception as e:
        print_warning(f"Could not check UFW: {e}")

def check_ib_gateway_config():
    """Check for IB Gateway configuration files"""
    print_header("IB Gateway Configuration Check")
    
    # Common IB Gateway installation paths
    possible_paths = [
        Path.home() / "IBJts",
        Path.home() / ".wine" / "drive_c" / "IBJts",
        Path("/opt/IBJts"),
        Path("/usr/local/IBJts"),
        Path.home() / "Jts"
    ]
    
    found_installations = []
    
    for path in possible_paths:
        if path.exists():
            found_installations.append(path)
            print_success(f"IB Installation found: {path}")
            
            # Look for gateway executable
            gateway_exe = path / "ibgateway" / "latest" / "ibgateway"
            if gateway_exe.exists():
                print_success(f"Gateway executable: {gateway_exe}")
            
            # Look for config files
            config_files = list(path.rglob("*.xml")) + list(path.rglob("*.properties"))
            if config_files:
                print_info(f"Config files found: {len(config_files)}")
                for config in config_files[:5]:  # Show first 5
                    print_info(f"  - {config}")
    
    if not found_installations:
        print_error("No IB Gateway installations found in common locations")
        print_info("IB Gateway might be installed in a custom location")

def test_basic_socket_connection():
    """Test basic socket connectivity"""
    print_header("Socket Connection Test")
    
    ports = [4001, 4002]
    
    for port in ports:
        print_info(f"Testing socket connection to 127.0.0.1:{port}")
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        try:
            start_time = time.time()
            sock.connect(('127.0.0.1', port))
            connect_time = time.time() - start_time
            print_success(f"Socket connected to port {port} in {connect_time:.3f}s")
            
            # Try to send a simple message (this might fail, but connection works)
            try:
                sock.send(b'test')
                print_success(f"Data sent to port {port}")
            except Exception as e:
                print_info(f"Could not send data (normal): {e}")
                
        except socket.timeout:
            print_error(f"Connection to port {port} timed out after 10 seconds")
        except ConnectionRefusedError:
            print_error(f"Connection to port {port} refused - nothing listening")
        except Exception as e:
            print_error(f"Connection to port {port} failed: {e}")
        finally:
            sock.close()

def check_system_info():
    """Check system information relevant to IB Gateway"""
    print_header("System Information")
    
    print_info(f"Python version: {sys.version}")
    print_info(f"Operating System: {os.uname()}")
    
    # Check for Wayland
    if os.environ.get('WAYLAND_DISPLAY'):
        print_info("Running on Wayland")
        print_info(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY')}")
    else:
        print_info("Not running on Wayland (or WAYLAND_DISPLAY not set)")
    
    if os.environ.get('DISPLAY'):
        print_info(f"X11 DISPLAY: {os.environ.get('DISPLAY')}")
    
    # Check Java
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print_success("Java is installed")
            print_info(f"Java version info: {result.stderr.split(chr(10))[0]}")
        else:
            print_error("Java is not installed or not accessible")
    except Exception as e:
        print_error(f"Could not check Java: {e}")

def check_ib_async_version():
    """Check ib_async installation"""
    print_header("ib_async Library Check")
    
    try:
        import ib_async
        print_success(f"ib_async is installed: {ib_async.__version__}")
        
        # Test import of key components
        from ib_async import IB, Stock
        print_success("Key ib_async components imported successfully")
        
    except ImportError as e:
        print_error(f"ib_async import failed: {e}")
    except Exception as e:
        print_error(f"ib_async check failed: {e}")

def main():
    print_header("IB Gateway Diagnostics Tool")
    print_info("Diagnosing Interactive Brokers Gateway connectivity issues...")
    
    # Run all diagnostic checks
    processes_found = check_processes()
    listening_ports = check_ports()
    check_firewall()
    check_ib_gateway_config()
    test_basic_socket_connection()
    check_system_info()
    check_ib_async_version()
    
    # Summary
    print_header("Diagnostic Summary")
    
    if processes_found:
        print_success("IB Gateway processes are running")
    else:
        print_error("IB Gateway processes NOT found")
        print_info("Solution: Start IB Gateway application first")
    
    if listening_ports:
        print_success(f"Found {len(listening_ports)} listening ports: {listening_ports}")
    else:
        print_error("No IB Gateway ports are listening")
        print_info("Solution: Check IB Gateway API configuration")
    
    if not processes_found:
        print_header("Recommended Actions")
        print_info("1. Start IB Gateway application")
        print_info("2. Login to your IB account")
        print_info("3. Enable API in Gateway settings:")
        print_info("   - Configure -> Settings -> API -> Enable ActiveX and Socket Clients")
        print_info("   - Set Socket port to 4002 (paper) or 4001 (live)")
        print_info("   - Ensure 'Read-Only API' is unchecked if you need trading")
        print_info("4. Click 'Apply' and restart Gateway if needed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Diagnostics interrupted by user{Colors.END}")
    except Exception as e:
        print_error(f"Diagnostics failed: {e}")
        import traceback
        traceback.print_exc()