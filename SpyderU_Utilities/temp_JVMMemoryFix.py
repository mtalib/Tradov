#!/usr/bin/env python3
"""
Temporary JVM Memory Fix for IB Gateway API Timeout Issues
Run this script to immediately fix JVM memory configuration
"""

import os
import sys
import subprocess
import psutil
import time
from pathlib import Path

def check_system_memory():
    """Check if system has enough memory for 4GB allocation"""
    memory = psutil.virtual_memory()
    available_gb = memory.available / (1024**3)
    
    print(f"💾 System Memory Analysis:")
    print(f"   Total: {memory.total / (1024**3):.1f} GB")
    print(f"   Available: {available_gb:.1f} GB")
    print(f"   Used: {memory.percent:.1f}%")
    
    can_allocate_4gb = available_gb >= 5.0  # Need 1GB headroom
    
    if can_allocate_4gb:
        print(f"   ✅ Can allocate 4GB heap (recommended)")
        return 4
    elif available_gb >= 3.0:
        print(f"   ⚠️  Can allocate 2GB heap (minimum)")
        return 2
    else:
        print(f"   ❌ Insufficient memory for optimal allocation")
        return 1

def find_ib_gateway():
    """Find IB Gateway installation"""
    base_dir = Path.home() / "Jts"
    
    if not base_dir.exists():
        print(f"❌ IB Gateway directory not found: {base_dir}")
        return None, None
    
    # Look for ibgateway subdirectory
    gateway_dir = base_dir / "ibgateway"
    if not gateway_dir.exists():
        print(f"❌ IB Gateway subdirectory not found: {gateway_dir}")
        return None, None
    
    # Find version directory (1037, 1039, latest)
    for version in ["1037", "1039", "latest"]:
        version_dir = gateway_dir / version
        if version_dir.exists():
            jar_file = version_dir / "ibgateway.jar"
            if jar_file.exists():
                print(f"✅ Found IB Gateway {version}: {version_dir}")
                return version_dir, jar_file
    
    print(f"❌ IB Gateway JAR file not found in {gateway_dir}")
    return None, None

def create_optimized_startup_script(gateway_dir, jar_file, heap_gb):
    """Create startup script with optimized JVM settings"""
    
    script_path = Path.home() / "start_ib_gateway_4gb.sh"
    
    # Create heap dump directory
    heap_dump_dir = Path.home() / "ib_heap_dumps"
    heap_dump_dir.mkdir(exist_ok=True)
    
    # JVM arguments for stability and performance
    jvm_args = [
        f"-Xms{heap_gb}g",                     # Initial heap size
        f"-Xmx{heap_gb}g",                     # Maximum heap size (same for stability)
        "-XX:+UseG1GC",                        # G1 garbage collector for low latency
        "-XX:MaxGCPauseMillis=250",            # Limit GC pauses to 250ms
        "-XX:+HeapDumpOnOutOfMemoryError",     # Create heap dump on OOM
        f"-XX:HeapDumpPath={heap_dump_dir}/",  # Heap dump location
        "-XX:+ExitOnOutOfMemoryError",         # Clean restart on OOM
        "-XX:+PrintGC",                        # Enable GC logging
        "-XX:+PrintGCTimeStamps",              # Timestamp GC events
        f"-Xloggc:{Path.home()}/ib_gc.log",    # GC log file
        "-Djava.net.preferIPv4Stack=true",     # Prefer IPv4 networking
        "-Dsun.net.useExclusiveBind=false"     # Allow port sharing
    ]
    
    script_content = f'''#!/bin/bash
# Optimized IB Gateway Startup Script - 4GB Memory Fix
# Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}

echo "================================================"
echo "  IB Gateway - Optimized 4GB Memory Configuration"
echo "  Heap Size: {heap_gb}GB"
echo "  Location: {gateway_dir}"
echo "================================================"

# Kill any existing IB Gateway processes
echo "Stopping existing IB Gateway processes..."
pkill -f "ibgateway" 2>/dev/null || true
sleep 2

# Display current memory
echo ""
echo "System Memory Before Start:"
free -h | grep Mem:

echo ""
echo "Starting IB Gateway with {heap_gb}GB heap..."
echo "JVM Args: {' '.join(jvm_args)}"

# Change to gateway directory
cd "{gateway_dir}"

# Start IB Gateway with optimized JVM settings
java {' '.join(jvm_args)} \\
    -cp "{jar_file}" \\
    ibgateway.GWClient \\
    "$@"

echo "IB Gateway stopped"
'''
    
    # Write script
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make executable
    script_path.chmod(0o755)
    
    print(f"✅ Optimized startup script created: {script_path}")
    return script_path

def test_api_connection():
    """Test current API connection"""
    import socket
    
    print("🔍 Testing IB Gateway API on port 4002...")
    
    try:
        # Test port connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        result = sock.connect_ex(("127.0.0.1", 4002))
        if result != 0:
            print("❌ Port 4002 is closed - IB Gateway not running")
            return False
        
        print("✅ Port 4002 is open")
        
        # Test API handshake
        sock.settimeout(10)  # Give more time for handshake
        sock.send(b'API\\0')
        time.sleep(0.5)
        sock.send(b'v100..176')
        
        # Wait for response
        response = sock.recv(1024)
        
        if response:
            print(f"✅ API handshake successful! ({len(response)} bytes received)")
            print("🎉 IB Gateway API is working properly!")
            return True
        else:
            print("❌ API handshake failed - no response")
            return False
            
    except socket.timeout:
        print("❌ API handshake timed out - likely JVM memory issue")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False
    finally:
        sock.close()

def main():
    """Main fix routine"""
    print("🔧 IB Gateway JVM Memory Fix")
    print("=" * 50)
    
    # Step 1: Check system memory
    heap_gb = check_system_memory()
    print()
    
    # Step 2: Find IB Gateway
    print("📁 Locating IB Gateway...")
    gateway_dir, jar_file = find_ib_gateway()
    if not gateway_dir:
        print("❌ Cannot proceed without IB Gateway installation")
        return False
    print()
    
    # Step 3: Create optimized startup script
    print("⚙️  Creating optimized startup script...")
    script_path = create_optimized_startup_script(gateway_dir, jar_file, heap_gb)
    print()
    
    # Step 4: Test current API (if running)
    print("🧪 Testing current API connection...")
    api_working = test_api_connection()
    print()
    
    # Step 5: Provide instructions
    print("📋 NEXT STEPS:")
    print("=" * 30)
    
    if not api_working:
        print("1. Stop current IB Gateway:")
        print("   pkill -f ibgateway")
        print()
        print("2. Start with optimized memory settings:")
        print(f"   bash {script_path}")
        print()
        print("3. Login and wait for 'API server listening on port 4002'")
        print()
        print("4. Test the API:")
        print("   python3 ~/quick_api_test.py")
    else:
        print("✅ IB Gateway API is already working!")
        print("   Use the optimized script for future startups:")
        print(f"   bash {script_path}")
    
    print()
    print("💡 The 4GB heap allocation should resolve API timeout issues")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\n❌ Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
