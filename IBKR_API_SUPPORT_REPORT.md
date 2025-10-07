# IBKR TWS API Connection Issue - Technical Support Report

**Report Date:** October 6, 2025  
**Report ID:** SPYDER-TWS-API-001  
**Severity:** High - Blocking production trading system deployment  
**Issue Type:** TWS API Handshake Timeout  

---

## Executive Summary

We are experiencing consistent TWS API handshake timeouts when connecting from our Linux-based trading system to TWS running on a Windows computer. While TCP socket connections succeed immediately, the API handshake consistently fails after exactly 4 seconds across all client IDs and connection patterns tested.

This issue mirrors a previously documented IB Gateway handshake timeout bug (which affected our system earlier), but is now occurring with TWS Paper Trading API as well.

---

## Environment Details

### Client System (Linux)
- **Operating System:** Ubuntu 22.04.3 LTS
- **Display Server:** Wayland
- **Python Version:** 3.13.3
- **Architecture:** x86_64
- **Network Interface:** Ethernet (192.168.1.9)

### Python Environment
- **ib_async Version:** Latest (via pip)
- **GUI Framework:** PySide6 (Qt6)
- **Async Framework:** asyncio
- **Additional Libraries:** pandas, numpy, matplotlib

### TWS Host System (Windows)
- **TWS Version:** Paper Trading Mode
- **Operating System:** Windows (version not specified)
- **Network Interface:** Ethernet (192.168.1.4)
- **TWS API Port:** 7497 (Paper Trading)

### Application Architecture
- **System Name:** SPYDER (Custom Trading Dashboard)
- **Connection Type:** Remote TWS API over LAN
- **Client Architecture:** Multi-threaded with async API client
- **GUI Framework:** Custom PySide6 dashboard with real-time data display
- **Connection Pool:** Custom implementation for multiple data streams

---

## Problem Description

### Primary Issue
TWS API connections consistently timeout during the handshake phase after exactly 4 seconds, despite successful TCP socket connections.

### Symptoms
1. **TCP Connection:** ✅ Succeeds immediately (<1ms)
2. **API Handshake:** ❌ Times out after 4.0 seconds consistently
3. **Error Pattern:** `TimeoutError()` in ib_async client
4. **Reproducibility:** 100% failure rate across all tested scenarios

### Error Sequence
```
2025-10-06 22:15:14,568 ib_async.client INFO Connecting to 192.168.1.4:7497 with clientId 1...
2025-10-06 22:15:14,574 ib_async.client INFO Connected
2025-10-06 22:15:18,578 ib_async.client INFO Disconnecting
2025-10-06 22:15:18,578 ib_async.client ERROR API connection failed: TimeoutError()
```

---

## Network Configuration

### Network Topology
```
Linux Client (192.168.1.9) ←→ [LAN] ←→ Windows TWS (192.168.1.4)
```

### Network Tests Performed
1. **Ping Test:** ✅ Success (1-4ms latency, 0% packet loss)
2. **Port Accessibility:** ✅ Port 7497 accessible, Port 7496 closed
3. **Raw Socket Test:** ✅ TCP connection succeeds immediately
4. **Network Route:** ✅ Direct LAN routing confirmed

### Firewall Status
- **Linux Client:** Standard Ubuntu firewall (outbound connections allowed)
- **Windows Host:** Windows Firewall (TWS ports accessible as confirmed by successful TCP connections)

---

## TWS Configuration

### API Settings (Confirmed Correct)
- ✅ **Enable ActiveX and Socket Clients:** Enabled
- ✅ **Socket Port:** 7497 (Paper Trading)
- ✅ **Trusted IPs:** 192.168.1.9 (Linux client IP)
- ✅ **Read-Only API:** Disabled (full API access)
- ✅ **Download open orders on connection:** Enabled

### TWS Status
- **TWS Application:** Running and responsive
- **Trading Mode:** Paper Trading
- **API Status:** Active (confirmed by port accessibility)
- **Connection History:** No existing API connections

---

## Testing Methodology & Results

### Test 1: Network Connectivity
```bash
# Command: ping -c 3 192.168.1.4
# Result: ✅ SUCCESS
# Latency: 1.358/2.281/3.937/1.173 ms (min/avg/max/mdev)
# Packet Loss: 0%
```

### Test 2: Port Accessibility
```python
# Raw socket connection test
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
result = sock.connect_ex(('192.168.1.4', 7497))
# Result: ✅ SUCCESS (result == 0)
# Connection Time: <0.01 seconds
```

### Test 3: Multiple Client IDs
Tested client IDs: 1, 2, 3, 10, 100
- **Result:** ❌ All failed with identical 4-second timeout
- **Pattern:** Same timeout duration regardless of client ID

### Test 4: Connection Patterns
Tested multiple ib_async connection patterns:
1. **Basic connectAsync():** ❌ 4-second timeout
2. **Async with custom timeout:** ❌ 4-second timeout (ignores custom timeout)
3. **Synchronous connection:** ❌ 4-second timeout
4. **Connection retry logic:** ❌ All retries fail identically

### Test 5: ib_async Configuration
```python
# Tested initialization patterns:
util.startLoop()      # ✅ Initializes correctly
util.logToConsole()   # ✅ Logging active
ib = IB()            # ✅ Instance creates successfully

# Connection attempt:
await ib.connectAsync(host='192.168.1.4', port=7497, clientId=1)
# Result: ❌ TimeoutError after 4.000 seconds
```

---

## Code Examples

### Minimal Reproduction Case
```python
#!/usr/bin/env python3
import asyncio
from ib_async import IB, util

async def test_connection():
    util.startLoop()
    util.logToConsole()
    
    ib = IB()
    
    try:
        # This consistently fails after 4 seconds
        await ib.connectAsync(host='192.168.1.4', port=7497, clientId=1)
        print("✅ Connected successfully")
        
        # Test basic functionality
        server_time = await ib.reqCurrentTimeAsync()
        print(f"Server time: {server_time}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        if ib.isConnected():
            ib.disconnect()

if __name__ == "__main__":
    asyncio.run(test_connection())
```

### Expected vs Actual Behavior
**Expected:** API handshake completes within 1-2 seconds, followed by successful server time request  
**Actual:** TCP connection succeeds, but API handshake times out after exactly 4 seconds

---

## Historical Context

### Previous IB Gateway Issue
Our system previously experienced identical handshake timeout issues with IB Gateway:
- **Symptom:** 4-second handshake timeout
- **Diagnosis:** Known IB Gateway bug in version 10.37
- **Resolution:** Migrated to Remote TWS as recommended solution

### Current TWS Issue
The same 4-second timeout pattern is now occurring with TWS Paper Trading API, suggesting a similar underlying issue in the API handshake protocol.

---

## System Architecture Impact

### SPYDER Trading System
Our custom trading dashboard requires reliable TWS API connectivity for:
- **Real-time market data** (SPY options chains)
- **Order management** (credit spreads, iron condors)
- **Portfolio monitoring** (P&L, positions, risk metrics)
- **Strategy execution** (0DTE scalping, automated signals)

### Production Readiness Blocker
This issue prevents deployment of our production trading system, as reliable API connectivity is critical for:
- Automated strategy execution
- Real-time risk management
- Position monitoring and alerts
- Market data feed integrity

---

## Technical Analysis

### Timeout Pattern Analysis
- **Consistency:** Exactly 4.000 seconds across all tests
- **Independence:** Timeout duration unaffected by:
  - Client ID selection
  - Network latency
  - Connection retry attempts
  - Custom timeout settings

### Potential Root Causes
1. **API Protocol Issue:** Handshake sequence not completing properly
2. **Authentication Timing:** Trusted IP validation taking too long
3. **Resource Contention:** TWS internal resource allocation delays
4. **Protocol Version:** Incompatibility between ib_async and TWS API version
5. **Threading/Async Issue:** Event loop or async handling problem in ib_async

---

## Diagnostic Data

### ib_async Library Versions
```bash
# pip list | grep ib
ib-async            0.9.86
```

### Python Environment
```bash
# python --version
Python 3.13.3

# python -c "import asyncio; print(asyncio.__file__)"
/usr/lib/python3.13/asyncio/__init__.py
```

### Network Interface Details
```bash
# ip addr show | grep 192.168.1.9
inet 192.168.1.9/24 brd 192.168.1.255 scope global dynamic noprefixroute enp3s0
```

---

## Troubleshooting Attempts

### Configuration Verification
1. ✅ TWS API settings confirmed correct multiple times
2. ✅ Trusted IP (192.168.1.9) verified in TWS configuration
3. ✅ Port 7497 confirmed accessible via telnet and socket tests
4. ✅ TWS restarted multiple times after configuration changes

### Code Pattern Testing
1. ✅ Multiple ib_async connection patterns tested
2. ✅ Different client IDs tested (1, 2, 3, 10, 100)
3. ✅ Various timeout values tested (no effect on 4-second timeout)
4. ✅ Synchronous and asynchronous patterns both tested

### Environment Testing
1. ✅ Network connectivity thoroughly verified
2. ✅ Firewall rules confirmed not blocking connections
3. ✅ No antivirus software interfering with connections
4. ✅ Python environment and dependencies verified

---

## Request for Support

### Specific Questions
1. **Is this a known issue** with TWS Paper Trading API handshake timeouts?
2. **Are there specific TWS settings** required for Linux/ib_async compatibility?
3. **Is there a protocol-level debugging mode** to see handshake sequence details?
4. **Are there known issues** with ib_async library and recent TWS versions?
5. **What diagnostic information** can we collect to help resolve this issue?

### Required Assistance
1. **Root Cause Analysis:** Help identify why API handshake is timing out
2. **Configuration Guidance:** Verify all TWS settings are optimal for our setup
3. **Protocol Debugging:** Access to lower-level handshake diagnostics
4. **Alternative Solutions:** If TWS API has limitations, recommend alternative approaches

### Urgency
This issue is blocking our production trading system deployment. We have a working infrastructure but cannot proceed without reliable TWS API connectivity.

---

## Contact Information

**Development Team:** SPYDER Trading System  
**Primary Contact:** [User Contact Information]  
**Environment:** Ubuntu 22.04 / Python 3.13.3 / PySide6  
**System:** Remote TWS API integration for automated trading  

---

## Appendix: Log Files

### Full Connection Attempt Log
```
2025-10-06 22:15:14,568 ib_async.client INFO Connecting to 192.168.1.4:7497 with clientId 1...
2025-10-06 22:15:14,574 ib_async.client INFO Connected
2025-10-06 22:15:18,578 ib_async.client INFO Disconnecting
2025-10-06 22:15:18,578 ib_async.client ERROR API connection failed: TimeoutError()
2025-10-06 22:15:18,582 ib_async.client INFO Disconnected.
```

### Network Diagnostic Output
```
PING 192.168.1.4 (192.168.1.4) 56(84) bytes of data.
64 bytes from 192.168.1.4: icmp_seq=1 ttl=128 time=1.36 ms
64 bytes from 192.168.1.4: icmp_seq=2 ttl=128 time=2.28 ms
64 bytes from 192.168.1.4: icmp_seq=3 ttl=128 time=3.94 ms

--- 192.168.1.4 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 1.358/2.281/3.937/1.173 ms
```

---

**End of Report**