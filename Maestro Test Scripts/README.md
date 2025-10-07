# Maestro Test Scripts

This folder contains valuable test, diagnostic, and utility tools created during the Spyder project development.

**Total Scripts:** 39 (spanning January → October 2025)

**Cleanup Status:** ✅ October 2, 2025 - Deleted 48 temporary/experimental scripts (see `CLEANUP_RECOMMENDATIONS.md`)

---

## 📅 Organization

All scripts are prefixed with date: `YYYYMMDD_script_name.py`

- **January 29, 2025** (1 script): Visualization migration tool
- **August 16-27, 2025** (6 scripts): Setup utilities, Docker configuration, trading control
- **September 22-23, 2025** (2 scripts): Development tools (Zed, Spyder integration)
- **September 29, 2025** (3 scripts): Module audit and migration utilities
- **September 30, 2025** (3 scripts): Gateway health monitoring and threading integration
- **October 1, 2025** (22 scripts): Connection testing, market data tests, diagnostics
- **October 2, 2025** (2 scripts): Historical Data Farm diagnostics

---

## 📂 Script Categories

### 🎨 Visualization Migration (January 2025)

Automated visualization framework migration tool.

| Script | Purpose |
|--------|---------|
| `20250129_migrate_to_plotly.py` | Automated Matplotlib → Plotly migration tool |

### ⚙️ Setup & Configuration (August 2025)

One-time setup and configuration utilities.

| Script | Purpose |
|--------|---------|
| `20250816_setup_ibautomater.sh` | IBAutomater setup and configuration |
| `20250816_trading_control.sh` | Trading control and management utility |
| `20250822_launch_terminal.sh` | Terminal launcher utility |
| `20250823_spyder_paper_wrapper.sh` | Paper trading wrapper script |
| `20250827_setup_docker_ib_gateway.sh` | Docker-based IB Gateway setup (319 lines) |
| `20250922_open_in_spyder.sh` | Open files in Spyder IDE |

### 🛠️ Development Utilities (September 2025)

Personal development and integration tools.

| Script | Purpose |
|--------|---------|
| `20250923_export_zed_conversations.py` | Export Zed editor conversations |

### 🔧 Migration & Audit Utilities (September 2025)

Automated tools for code quality and framework migration.

| Script | Purpose |
|--------|---------|
| `20250929_migrate_to_pyside6.py` | Automated PyQt6 → PySide6 migration tool |
| `20250929_audit_init_files.py` | Audit all __init__.py files for compliance |
| `20250929_test_package_imports.py` | Verify all Spyder packages import correctly |

### 🏥 Gateway Monitoring & Diagnostics (September 30, 2025)

Tools for monitoring Gateway health and diagnosing connection issues.

| Script | Purpose |
|--------|---------|
| `20250930_gateway_health_monitor.py` | Monitor Gateway health and auto-restart (264 lines) |
| `20250930_dashboard_threading_integration.py` | Dashboard threading integration tests (12K) |
| `20250930_threading_fix_connection_manager.py` | Connection manager threading fixes (11K) |

### 🔍 Comprehensive Diagnostics (October 1 & 2, 2025)

In-depth diagnostic tools for Gateway and connection analysis.

| Script | Purpose |
|--------|---------|
| `20251001_diagnose_gateway.py` | Comprehensive Gateway diagnostics |
| `20251001_comprehensive_gateway_test.py` | Full Gateway functionality test |
| `20251002_diagnose_historical_data_farm.py` | Diagnose Historical Data Farm issues |
| `20251001_debug_plotly_chart.py` | Debug Plotly chart rendering |

### 🧪 Connection Test Suite (October 1 & 2, 2025)

Testing Gateway connections, handshakes, and client behavior.

| Script | Purpose |
|--------|---------|
| `20251001_test_api_client.py` | Test API client connections |
| `20251002_test_ib_connection.py` | Simple IB connection verification |
| `20251001_test_connectAsync_60s.py` | Test 60-second connection timeout |
| `20251001_test_handshake_timeout.py` | Test connection handshake timeout |
| `20251001_test_simple_handshake.py` | Simple handshake test |
| `20251001_test_quick_connectivity.py` | Quick connectivity check |
| `20251001_test_socket_diagnostic.py` | Socket-level diagnostics |
| `20251001_test_gateway_10_37.py` | Test IB Gateway 10.37 specific features |
| `20251001_test_gateway_stability.py` | Test Gateway stability over time |
| `20251001_test_client_id_conflicts.py` | Test for client ID conflicts |

### 📊 Market Data Test Suite (October 1, 2025)

Testing market data subscriptions and data flow.

| Script | Purpose |
|--------|---------|
| `20251001_test_market_data_flow.py` | Test market data flow from Gateway |
| `20251001_test_market_data_working.py` | Verify market data is working |
| `20251001_test_simple_market_data.py` | Simple market data subscription test |
| `20251001_test_optimized_market_data.py` | Test optimized market data handling |
| `20251001_test_timeout_market_data.py` | Test market data timeout scenarios |

### 🎨 Dashboard & UI Test Suite (October 1, 2025)

Testing dashboard components and UI elements.

| Script | Purpose |
|--------|---------|
| `20251001_test_dashboard_launch.py` | Test dashboard launch sequence |
| `20251001_test_minimal_dashboard.py` | Minimal dashboard for testing |
| `20251001_test_chart_display.py` | Test chart display functionality |
| `20251001_test_chart_generation.py` | Test chart generation |
| `20251001_test_webengine_basic.py` | Test WebEngine basic functionality |
| `20251001_test_widget_display.py` | Test widget display |

---

## 🎯 Key Testing Milestones

### January 29, 2025 - Visualization Migration
- ✅ Created automated Matplotlib → Plotly migration tool
- ✅ Prepared for project-wide chart library standardization

### September 29, 2025 - Code Quality & Framework Migration
- ✅ Audited all 24 Spyder modules for code health
- ✅ Standardized all `__init__.py` files (24/24 modules)
- ✅ Created PyQt6 → PySide6 migration tool
- ✅ Verified all package imports working correctly

### October 1, 2025 - Gateway Stabilization
- ✅ Tested and fixed API flood protection (50 msg/sec limit)
- ✅ Tested Gateway connection stability (exponential backoff)
- ✅ Tested client ID conflicts and resolution
- ✅ Tested market data subscriptions (100 max)
- ✅ Tested dashboard launch with various configurations
- ✅ Eliminated Client 999 phantom connection
- ✅ Fixed IBDataConnector singleton lifecycle (Qt C++ race)

### October 2, 2025 - Historical Data Farm & Cleanup
- ✅ Diagnosed Historical Data Farm disconnection (rate limit violations)
- ✅ Tested connection with Client 2 (verified in Gateway)
- ✅ Decided to disable historical data (not needed for live trading)
- ✅ Cleaned up 48 temporary/experimental scripts (67% reduction)

---

## 🗂️ Cleanup Summary (October 2, 2025)

**Deleted:** 48 scripts (67% of collection)
**Retained:** 39 scripts (54% of original 72)

### Categories Deleted
1. ❌ **Flood Protection Experiments** (15 scripts) - Superseded by production flood protection
2. ❌ **Experimental Dashboard Launchers** (12 scripts) - Superseded by `launch_dashboard_production.py`
3. ❌ **Simple Connection Tests** (14 scripts) - Basic tests, information now documented
4. ❌ **Simple UI/Chart Tests** (4 scripts) - Basic display tests, replaced by comprehensive tests
5. ❌ **Temporary Utilities** (3 scripts) - One-time use scripts, no longer needed

### Why Keep These 39 Scripts?
✅ **Reusable Tools**: Setup scripts, migration utilities still valuable
✅ **Comprehensive Tests**: Complex integration tests with valuable patterns
✅ **Diagnostics**: In-depth diagnostic tools for troubleshooting
✅ **Reference Examples**: Good code examples for future development
✅ **Health Monitoring**: Active monitoring and health check tools

For detailed analysis, see: `CLEANUP_RECOMMENDATIONS.md`

---

## 📚 Related Documentation

For comprehensive documentation of the fixes and improvements, see:

### Maestro Reports Folder
- `20250928_Module_Audit_Report.md` - Complete module audit (September)
- `20250929_Init_Files_Audit_Report.md` - Init files standardization (September)
- `20251001_COMPLETE_FIX_SUMMARY.md` - All October 1st fixes
- `20251001_API_FLOOD_PROTECTION_COMPLETE.md` - Flood protection implementation
- `20251001_CLIENT_999_ELIMINATED.md` - Client 999 fix
- `20251001_IBDATACONNECTOR_SINGLETON_FIX.md` - Singleton lifecycle fix
- `20251002_IB_GATEWAY_STABILITY_REPORT_FOR_IBKR.md` - Complete IBKR report
- `20251002_HISTORICAL_DATA_FARM_STABILITY_SUCCESS.md` - Historical data solution
- `CLEANUP_RECOMMENDATIONS.md` - Detailed cleanup analysis

---

## ⚠️ Important Notes

### Production Usage
These scripts are **FOR TESTING AND DIAGNOSTICS ONLY**. The production system uses:
- `launch_dashboard_production.py` - Production dashboard launcher
- `launch_balanced_gateway.sh` - Production Gateway launcher
- `optimize_gateway_jvm.sh` - Gateway JVM optimization
- Stable modules in `SpyderA_Core/`, `SpyderB_Broker/`, etc.
- Tested configurations documented in Maestro Reports

### Script Status
- ✅ **Valuable Tools**: 39 high-value scripts retained
- 🗑️ **Archived**: 48 temporary scripts deleted after serving their purpose
- 📚 **Documented**: All solutions documented in Maestro Reports

### Re-running Tests
⚠️ **Before running any test scripts:**
1. Ensure IB Gateway is running and stable
2. Check that production dashboard is not running (avoid port conflicts)
3. Be aware of API rate limits (50 msg/sec, 100 subscriptions max)
4. Monitor Gateway console for any issues

---

## 🎓 Lessons Learned

### What Worked
1. ✅ Socket-based connection testing (no client ID needed)
2. ✅ Token bucket algorithm for rate limiting
3. ✅ Exponential backoff for reconnection
4. ✅ 2-second delays between client connections
5. ✅ Singleton pattern with proper Qt lifecycle management

### What Didn't Work
1. ❌ Full IB connection for testing (created Client 999 phantom)
2. ❌ Aggressive rate limiting without request queuing
3. ❌ Calling `deleteLater()` on singleton objects
4. ❌ Setting parent-child Qt relationships on singletons

### Critical Discoveries
1. 🔍 Historical Data limit: 60 requests per 10 minutes (extremely strict)
2. 🔍 Qt C++ objects can be deleted while Python references exist
3. 🔍 IBKR disconnects immediately on rate violations (no warnings)
4. 🔍 Market Data Farm != Historical Data Farm (different limits)

---

**Archive Created:** October 2, 2025
**Total Scripts:** 39 (cleaned from 72)
**Status:** Successfully stabilized IB Gateway 10.37 🎉
