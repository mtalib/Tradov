import socket
import time

# First check if port is open
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', 4002))
sock.close()

if result == 0:
    print("✅ Port 4002 is open")
    
    # Now try IB connection
    from ib_async import IB
    
    for attempt in range(3):
        ib = IB()
        try:
            # Increase timeout
            ib.connect('127.0.0.1', 4002, clientId=999, timeout=20)
            print(f"✅ CONNECTED! Attempt {attempt+1}")
            print(f"Server: {ib.client.serverVersion()}")
            
            # Get account
            print(f"Account: {ib.managedAccounts()}")
            
            ib.disconnect()
            break
            
        except Exception as e:
            print(f"❌ Attempt {attempt+1} failed: {e}")
            time.sleep(2)
else:
    print("❌ Port 4002 is not accessible")
