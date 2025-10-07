
# TWS Configuration Guide - Based on Research Reports
# Generated: 2025-10-06 23:08:49

## CRITICAL TWS SETTINGS (Must be configured on Windows TWS computer: 192.168.1.4)

### 1. API Settings (File → Global Configuration → API → Settings)
✅ Enable ActiveX and Socket Clients: CHECKED
✅ Socket Port (Paper Trading): 7497
✅ Socket Port (Live Trading): 7496
✅ Trusted IPs: 192.168.1.9
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
✅ Allow inbound connections from 192.168.1.9

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
2. Verify 192.168.1.9 appears in TWS "API connections" dialog
3. Try connecting from Windows computer first (localhost test)
4. Consider TWS version - avoid 10.23+ if possible (has reqExecutions bug)
5. Test with Python 3.11/3.12 instead of 3.13+

## PRODUCTION DEPLOYMENT
- Use connection pooling with different client IDs
- Implement health checks every 5 minutes
- Setup automatic reconnection with backoff
- Monitor TWS log files for API errors
- Consider IB Gateway as fallback option
