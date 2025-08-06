#!/usr/bin/env python3
"""Check IB Gateway status quickly"""

import socket
import subprocess
import time

def check_port():
    """Check if IB Gateway port is open"""
    print("1. Checking if port 4002 is open...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 4002))
        sock.close()
        
        if result == 0:
            print("✅ Port 4002 is OPEN")
            return True
        else:
            print("❌ Port 4002 is CLOSED - IB Gateway not responding")
            return False
    except Exception as e:
        print(f"❌ Error checking port: {e}")
        return False

def check_process():
    """Check if IB Gateway process is running"""
    print("\n2. Checking for IB Gateway process...")
    try:
        result = subprocess.run(['pgrep', '-f', 'ibgateway'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"✅ IB Gateway is running (PID: {', '.join(pids)})")
            
            # Check memory usage
            for pid in pids:
                try:
                    mem_result = subprocess.run(['ps', '-p', pid, '-o', '%mem,rss'], capture_output=True, text=True)
                    print(f"   Memory usage for PID {pid}:")
                    print(f"   {mem_result.stdout}")
                except:
                    pass
            return True
        else:
            print("❌ IB Gateway process NOT found")
            return False
    except Exception as e:
        print(f"❌ Error checking process: {e}")
        return False

def test_socket_response():
    """Test if socket responds to API handshake"""
    print("\n3. Testing API response...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(('127.0.0.1', 4002))
        
        # Send API handshake
        sock.send(b"API\0")
        
        # Try to receive response
        sock.settimeout(1)
        try:
            data = sock.recv(100)
            if data:
                print(f"✅ Got API response: {len(data)} bytes")
            else:
                print("❌ No API response")
        except socket.timeout:
            print("❌ API not responding (timeout)")
            
        sock.close()
    except Exception as e:
        print(f"❌ Socket test failed: {e}")

def main():
    print("="*50)
    print("IB GATEWAY STATUS CHECK")
    print("="*50)
    
    port_ok = check_port()
    process_ok = check_process()
    
    if not port_ok and process_ok:
        print("\n⚠️  IB Gateway is running but port is not open!")
        print("   Try restarting IB Gateway")
    elif not process_ok:
        print("\n⚠️  IB Gateway is not running!")
        print("   Please start IB Gateway and login")
    else:
        test_socket_response()
    
    print("\n" + "="*50)
    print("RECOMMENDATIONS:")
    print("="*50)
    
    if port_ok and process_ok:
        print("1. IB Gateway seems to be in a bad state")
        print("2. Try: pkill -f ibgateway")
        print("3. Start IB Gateway fresh")
        print("4. Check the log for 'API server is listening on port 4002'")
    else:
        print("1. Start IB Gateway")
        print("2. Login and wait for 'Logged in' status")
        print("3. Verify API is enabled in settings")

if __name__ == "__main__":
    main()