# DEPRECATED - IBKR Legacy Code

**Status:** DEPRECATED as of 2025-11-25
**Reason:** Spyder migrated from Interactive Brokers (IBKR) to Tradier + Polygon.io

## What's in this directory?

This directory contains legacy code and utilities that were used when Spyder integrated with Interactive Brokers TWS/Gateway using the ib_insync library.

### Files Deprecated (11 files total)

1. **Bashrc Configuration Scripts (3 files)**
   - `apply_enhanced_bashrc.py` - Set up IB environment variables
   - `apply_dual_mode_bashrc.py` - Dual-mode IB configuration
   - `setup_dual_mode_bashrc.py` - IB mode switcher setup
   - These configured bash aliases and environment variables for IB Gateway/TWS

2. **IB-Specific Utilities (3 files)**
   - `client_consolidation_analysis.py` - Analyzed IB client connections
   - `install_spyder_desktop_launcher.py` - Desktop launcher with IB references
   - `SpyderQ80_ConnectAPIDeploy.py.DEPRECATED` - ConnectAPI deployment (IBKR-specific)

3. **IB Monitoring & Diagnostics (5 files)**
   - `SpyderQ22_CheckIBStatus.py.DEPRECATED` - Check IB Gateway connection status
   - `SpyderQ24_ProductionWatchdog.py.DEPRECATED` - IB production watchdog
   - `SpyderQ25_SystemMonitor.py.DEPRECATED` - IB system monitor
   - `SpyderQ45_Diagnostics.py.DEPRECATED` - IB diagnostics tool
   - `SpyderQ91_MonitoringUtilities.py.DEPRECATED` - IB monitoring utilities

4. **Archived Test Files (in archived_ibkr/ subdirectory)**
   - `archived_ibkr/comprehensive_library_test.py.DEPRECATED` - ib_insync library tests
   - `archived_ibkr/README.md` - Original archived IBKR documentation

## Why These Were Deprecated

Spyder underwent a major architecture migration:

### Old Architecture (DEPRECATED)
- **Broker:** Interactive Brokers (via ib_insync library)
- **Market Data:** Interactive Brokers TWS/Gateway
- **Connection:** Local or remote TWS instances
- **Authentication:** Username/password, multiple client IDs

### New Architecture (CURRENT)
- **Broker:** Tradier API (SpyderB40_TradierClient)
- **Market Data:** Polygon.io WebSocket + REST API
- **Connection:** Direct API calls (no local software required)
- **Authentication:** API keys in .env file

## Migration Status

✅ **Complete:**
- Core trading system migrated to Tradier
- Market data migrated to Polygon.io
- Configuration updated (config/config.py)
- Main modules updated

✅ **Deprecated:**
- All ib_insync imports removed from active code
- IB-specific utilities moved to this directory
- Legacy bashrc scripts archived

## Do Not Use

These files are kept for historical reference only and **should not be used** in current Spyder installations.

### For New Users

If you're setting up Spyder for the first time:
1. **Do NOT** use files in this directory
2. **Do NOT** install ib_insync
3. **Do NOT** configure IB Gateway/TWS

Instead:
1. Follow the main README.md setup instructions
2. Get Tradier API credentials
3. Get Polygon.io API credentials
4. Configure .env file (see .env.example)

## Historical Reference

These files represent Spyder's evolution from an IB-focused system to a modern multi-broker platform. They may be useful for:
- Understanding migration history
- Reference for similar migrations
- Historical code archaeology

---

**Migration Date:** 2025-11-25
**Last IBKR Version:** Pre-Tradier migration
**Current System:** Tradier + Polygon.io
