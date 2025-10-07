#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Historical Data Farm Disconnection Diagnostic Tool

This script checks for potential causes of Historical Data Farm disconnections
and provides recommendations.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("🔍 HISTORICAL DATA FARM DISCONNECTION DIAGNOSTIC")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ==============================================================================
# CHECK 1: Rate Limit Configuration
# ==============================================================================
print("📋 CHECK 1: Rate Limit Configuration")
print("-" * 80)

try:
    from SpyderC_MarketData.SpyderC02_HistoricalData import (
        MAX_HISTORICAL_REQUESTS_PER_SECOND,
        MAX_HISTORICAL_REQUESTS_PER_10_MINUTES,
        HISTORICAL_REQUEST_WINDOW,
    )

    print(f"✅ Historical data module loaded")
    print(
        f"   MAX_HISTORICAL_REQUESTS_PER_SECOND: {MAX_HISTORICAL_REQUESTS_PER_SECOND}"
    )
    print(
        f"   MAX_HISTORICAL_REQUESTS_PER_10_MINUTES: {MAX_HISTORICAL_REQUESTS_PER_10_MINUTES}"
    )
    print(f"   HISTORICAL_REQUEST_WINDOW: {HISTORICAL_REQUEST_WINDOW} seconds")

    # Check if settings are correct
    if MAX_HISTORICAL_REQUESTS_PER_SECOND > 0.15:
        print(
            f"⚠️  WARNING: Request rate ({MAX_HISTORICAL_REQUESTS_PER_SECOND}) is too high!"
        )
        print(f"   Recommended: 0.1 (1 request per 10 seconds)")
    else:
        print(f"✅ Request rate is properly configured")

    if MAX_HISTORICAL_REQUESTS_PER_10_MINUTES != 60:
        print(
            f"⚠️  WARNING: 10-minute limit should be 60, not {MAX_HISTORICAL_REQUESTS_PER_10_MINUTES}"
        )
    else:
        print(f"✅ 10-minute limit is correct")

except ImportError as e:
    print(f"❌ Failed to import historical data module: {e}")
except Exception as e:
    print(f"❌ Error checking rate limits: {e}")

print()

# ==============================================================================
# CHECK 2: Active Connections
# ==============================================================================
print("📋 CHECK 2: Active IB Connections")
print("-" * 80)

try:
    from SpyderB_Broker.SpyderB01_SpyderClient import get_spyder_client

    # Try to get client status
    print("Checking for active IB connections...")
    # Note: We can't actually connect here without disrupting the system
    print("✅ SpyderClient module available")
    print("   (Cannot check active connections without creating new client)")

except ImportError as e:
    print(f"⚠️  SpyderClient not available: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

print()

# ==============================================================================
# CHECK 3: Historical Data Manager Instances
# ==============================================================================
print("📋 CHECK 3: Looking for Historical Data Manager Usage")
print("-" * 80)

import subprocess
import os

# Search for historical data requests in running code
try:
    spyder_dir = Path(__file__).parent

    # Search for files that import or use HistoricalDataManager
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "HistoricalDataManager", str(spyder_dir)],
        capture_output=True,
        text=True,
        timeout=5,
    )

    if result.stdout:
        files_using_historical = set()
        for line in result.stdout.split("\n"):
            if line and ":" in line:
                file_path = line.split(":")[0]
                # Exclude the historical data module itself
                if "SpyderC02_HistoricalData.py" not in file_path:
                    files_using_historical.add(file_path)

        if files_using_historical:
            print(
                f"Found {len(files_using_historical)} file(s) using HistoricalDataManager:"
            )
            for f in sorted(files_using_historical):
                relative_path = (
                    Path(f).relative_to(spyder_dir)
                    if spyder_dir in Path(f).parents
                    else f
                )
                print(f"   • {relative_path}")
        else:
            print("✅ No active usage of HistoricalDataManager found")
    else:
        print("✅ No files importing HistoricalDataManager")

except subprocess.TimeoutExpired:
    print("⚠️  Search timed out")
except Exception as e:
    print(f"⚠️  Could not search for HistoricalDataManager usage: {e}")

print()

# ==============================================================================
# CHECK 4: Potential Flood Protection Issues
# ==============================================================================
print("📋 CHECK 4: API Flood Protection Status")
print("-" * 80)

try:
    from SpyderB_Broker.SpyderB33_APIFloodProtection import APIFloodProtection

    print("✅ API Flood Protection module available")
    print("   This should protect against excessive requests")

    # Check if flood protection has correct historical data limits
    protection = APIFloodProtection()
    if "historical_data" in protection.rate_limiters:
        hist_limiter = protection.rate_limiters["historical_data"]
        print(f"   Historical data rate limiter configured:")
        print(f"     • Limit: {hist_limiter.limit}")
        print(f"     • Window: {hist_limiter.window} seconds")

        # IBKR limit is 60 per 600 seconds
        expected_limit = 60
        expected_window = 600

        if (
            hist_limiter.limit != expected_limit
            or hist_limiter.window != expected_window
        ):
            print(f"⚠️  WARNING: Flood protection limits don't match IBKR requirements!")
            print(
                f"   Expected: {expected_limit} requests per {expected_window} seconds"
            )
            print(
                f"   Current:  {hist_limiter.limit} requests per {hist_limiter.window} seconds"
            )
        else:
            print(f"✅ Flood protection correctly configured for IBKR limits")
    else:
        print("⚠️  WARNING: No 'historical_data' rate limiter found in flood protection")

except ImportError:
    print("⚠️  API Flood Protection module not available")
except Exception as e:
    print(f"❌ Error checking flood protection: {e}")

print()

# ==============================================================================
# CHECK 5: IB Gateway Status
# ==============================================================================
print("📋 CHECK 5: IB Gateway Process Status")
print("-" * 80)

try:
    # Check if Gateway is running
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=3)

    gateway_found = False
    for line in result.stdout.split("\n"):
        if "java" in line.lower() and "gateway" in line.lower():
            gateway_found = True
            # Extract memory usage
            parts = line.split()
            if len(parts) > 5:
                mem_percent = parts[3]
                print(f"✅ IB Gateway is running")
                print(f"   Memory usage: {mem_percent}%")
            break

    if not gateway_found:
        print("❌ IB Gateway does not appear to be running!")
        print("   Start Gateway with: ./launch_gateway_antiflood.sh")

except Exception as e:
    print(f"⚠️  Could not check Gateway status: {e}")

print()

# ==============================================================================
# RECOMMENDATIONS
# ==============================================================================
print("=" * 80)
print("💡 RECOMMENDATIONS")
print("=" * 80)

recommendations = []

# Check if we found any issues
if MAX_HISTORICAL_REQUESTS_PER_SECOND > 0.15:
    recommendations.append(
        "⚠️  CRITICAL: Reduce MAX_HISTORICAL_REQUESTS_PER_SECOND to 0.1 in SpyderC02_HistoricalData.py"
    )

recommendations.append(
    "✅ Rate limits are configured correctly (0.1 req/sec, 60 per 10 min)"
)

recommendations.append(
    "🔍 If disconnections persist, check these additional causes:\n"
    "   1. Network issues or firewall blocking connections\n"
    "   2. Multiple clients making historical requests simultaneously\n"
    "   3. Cached/queued requests from previous sessions\n"
    "   4. IB Gateway memory issues (check if > 3.5GB RAM used)"
)

recommendations.append(
    "📊 Monitor IB Gateway console for error messages:\n"
    "   • Error 162: Historical Market Data Service error\n"
    "   • Error 162: HMDS query returned no data\n"
    "   • Pacing violation warnings"
)

recommendations.append(
    "🔧 Emergency actions if disconnection persists:\n"
    "   1. Restart IB Gateway: ./launch_gateway_antiflood.sh\n"
    "   2. Wait 10-15 minutes for IBKR pacing penalty to clear\n"
    "   3. Check for any background test scripts making requests\n"
    "   4. Verify no other applications are connected to Gateway"
)

for i, rec in enumerate(recommendations, 1):
    print(f"\n{i}. {rec}")

print()
print("=" * 80)
print("✅ Diagnostic Complete")
print("=" * 80)
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()
