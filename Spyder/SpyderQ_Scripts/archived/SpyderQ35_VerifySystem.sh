#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ35_VerifySystem.sh
# Group: Q (Scripts/Testing)
# Purpose: Comprehensive system verification after installation or migration
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:30:00
#
# Description:
#     Performs thorough verification of the Spyder system including dependencies,
#     module imports, configurations, network connectivity, and integration tests.
#     Essential for validating new installations or post-migration systems.
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
VENV_PATH="$SPYDER_HOME/spyder_venv"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
LOG_DIR="$SPYDER_HOME/logs"
TEST_LOG="$LOG_DIR/verification_$(date +%Y%m%d_%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# Test categories
declare -A TEST_RESULTS

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  SPYDER SYSTEM VERIFICATION${NC}"
    echo -e "${BLUE}  $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

test_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    echo "[PASS] $1" >> "$TEST_LOG"
    ((PASSED_TESTS++))
    ((TOTAL_TESTS++))
}

test_fail() {
    echo -e "  ${RED}✗${NC} $1"
    echo "[FAIL] $1: $2" >> "$TEST_LOG"
    ((FAILED_TESTS++))
    ((TOTAL_TESTS++))
}

test_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    echo "[WARN] $1" >> "$TEST_LOG"
    ((WARNINGS++))
}

test_info() {
    echo -e "  ${CYAN}ℹ${NC} $1"
    echo "[INFO] $1" >> "$TEST_LOG"
}

# ===============================================================================
# ENVIRONMENT TESTS
# ===============================================================================

test_environment() {
    print_section "1. ENVIRONMENT VERIFICATION"
    
    # Check Spyder home
    if [ -d "$SPYDER_HOME" ]; then
        test_pass "Spyder home exists: $SPYDER_HOME"
    else
        test_fail "Spyder home not found" "$SPYDER_HOME"
        return 1
    fi
    
    # Check Python version
    if command -v python3.10 &> /dev/null; then
        PY_VERSION=$(python3.10 --version 2>&1)
        test_pass "Python 3.10 found: $PY_VERSION"
    else
        test_fail "Python 3.10 not found" "Required for Spyder"
    fi
    
    # Check virtual environment
    if [ -d "$VENV_PATH" ]; then
        test_pass "Virtual environment exists"
        if [ -f "$VENV_PATH/bin/activate" ]; then
            test_pass "Virtual environment is valid"
        else
            test_fail "Virtual environment corrupted" "Missing activate script"
        fi
    else
        test_fail "Virtual environment not found" "$VENV_PATH"
    fi
    
    # Check configuration file
    if [ -f "$SPYDER_HOME/.env" ]; then
        test_pass "Configuration file exists"
        # Check for required variables
        source "$SPYDER_HOME/.env" 2>/dev/null || true
        
        if [ -n "$IB_USERNAME" ]; then
            test_pass "IB credentials configured"
        else
            test_warn "IB credentials not configured"
        fi
    else
        test_fail "Configuration file missing" ".env file required"
    fi
    
    # Check directory structure
    for dir in logs data scripts config services; do
        if [ -d "$SPYDER_HOME/$dir" ]; then
            test_pass "Directory exists: $dir/"
        else
            test_warn "Directory missing: $dir/ (creating...)"
            mkdir -p "$SPYDER_HOME/$dir"
        fi
    done
}

# ===============================================================================
# DEPENDENCY TESTS
# ===============================================================================

test_dependencies() {
    print_section "2. DEPENDENCY VERIFICATION"
    
    # Activate virtual environment
    source "$VENV_PATH/bin/activate" 2>/dev/null || {
        test_fail "Cannot activate virtual environment" ""
        return 1
    }
    
    # Test critical Python packages
    local packages=(
        "ib_insync:IB API wrapper"
        "pandas:Data analysis"
        "numpy:Numerical computing"
        "PyQt6:GUI framework"
        "prometheus_client:Metrics"
        "psutil:System monitoring"
        "sqlalchemy:Database"
        "pytz:Timezone support"
        "requests:HTTP client"
        "aiohttp:Async HTTP"
    )
    
    for pkg_info in "${packages[@]}"; do
        IFS=':' read -r pkg desc <<< "$pkg_info"
        if python -c "import $pkg" 2>/dev/null; then
            version=$(python -c "import $pkg; print(getattr($pkg, '__version__', 'unknown'))" 2>/dev/null || echo "N/A")
            test_pass "$desc ($pkg v$version)"
        else
            test_fail "$desc" "Package $pkg not installed"
        fi
    done
}

# ===============================================================================
# MODULE IMPORT TESTS
# ===============================================================================

test_module_imports() {
    print_section "3. MODULE IMPORT VERIFICATION"
    
    source "$VENV_PATH/bin/activate" 2>/dev/null
    cd "$SPYDER_HOME"
    
    # Test core modules
    local modules=(
        "SpyderA_Core.SpyderA06_MasterController:Master Controller"
        "SpyderB_Broker.SpyderB14_MultiClientWatchdog:Watchdog"
        "SpyderB_Broker.SpyderB15_PrometheusMetrics:Metrics"
        "SpyderB_Broker.SpyderB16_GatewayIntegration:Integration"
        "SpyderE_Risk.SpyderE11_MaxLossProtection:Risk Manager"
        "SpyderE_Risk.SpyderE12_PortfolioVaR:Portfolio VaR"
        "SpyderX_Agents.SpyderX16_MetaCoordinator:Meta Coordinator"
        "SpyderG_GUI.SpyderG05_TradingDashboard:Dashboard"
        "SpyderP_PortfolioMgmt.SpyderP05_MultiStrategyAllocator:Allocator"
        "SpyderP_PortfolioMgmt.SpyderP06_StrategyRotation:Strategy Rotation"
    )
    
    for mod_info in "${modules[@]}"; do
        IFS=':' read -r module desc <<< "$mod_info"
        if python -c "from $module import *" 2>/dev/null; then
            test_pass "$desc imports successfully"
        else
            test_fail "$desc import failed" "$module"
        fi
    done
}

# ===============================================================================
# NETWORK CONNECTIVITY TESTS
# ===============================================================================

test_network() {
    print_section "4. NETWORK CONNECTIVITY"
    
    # Check localhost
    if ping -c 1 localhost &> /dev/null; then
        test_pass "Localhost reachable"
    else
        test_fail "Localhost not reachable" "Network issue"
    fi
    
    # Check IB Gateway ports
    if nc -z localhost 4002 2>/dev/null; then
        test_pass "IB Gateway (Paper) port 4002 open"
    else
        test_warn "IB Gateway (Paper) port 4002 closed"
    fi
    
    if nc -z localhost 4001 2>/dev/null; then
        test_pass "IB Gateway (Live) port 4001 open"
    else
        test_info "IB Gateway (Live) port 4001 closed (normal for paper trading)"
    fi
    
    # Check Prometheus metrics port
    if nc -z localhost 8000 2>/dev/null; then
        test_pass "Metrics port 8000 open"
    else
        test_info "Metrics port 8000 closed (service not running)"
    fi
    
    # Check internet connectivity
    if ping -c 1 8.8.8.8 &> /dev/null; then
        test_pass "Internet connectivity OK"
    else
        test_warn "No internet connectivity"
    fi
    
    # Check IB servers (if possible)
    if nslookup "api.ibkr.com" &> /dev/null; then
        test_pass "IB servers reachable (DNS)"
    else
        test_warn "Cannot resolve IB servers"
    fi
}

# ===============================================================================
# SCRIPT VERIFICATION
# ===============================================================================

test_scripts() {
    print_section "5. Q-SERIES SCRIPT VERIFICATION"
    
    # Check critical scripts exist
    local critical_scripts=(
        "SpyderQ01_Setup.sh:Setup script"
        "SpyderQ10_StartAll.sh:Start script"
        "SpyderQ11_StopAll.sh:Stop script"
        "SpyderQ16_SpyderControl.sh:Control script"
        "SpyderQ20_Status.sh:Status script"
        "SpyderQ25_SystemMonitor.py:Monitor script"
    )
    
    for script_info in "${critical_scripts[@]}"; do
        IFS=':' read -r script desc <<< "$script_info"
        if [ -f "$SCRIPTS_DIR/$script" ]; then
            if [ -x "$SCRIPTS_DIR/$script" ]; then
                test_pass "$desc exists and is executable"
            else
                test_warn "$desc exists but not executable"
                chmod +x "$SCRIPTS_DIR/$script"
            fi
        else
            test_fail "$desc missing" "$script"
        fi
    done
    
    # Check service files
    local service_files=(
        "SpyderQ70_Watchdog.service"
        "SpyderQ71_Metrics.service"
        "SpyderQ74_SpyderMain.service"
    )
    
    for service in "${service_files[@]}"; do
        if [ -f "$SPYDER_HOME/services/$service" ]; then
            test_pass "Service file exists: $service"
        else
            test_warn "Service file missing: $service"
        fi
    done
}

# ===============================================================================
# DATABASE TESTS
# ===============================================================================

test_database() {
    print_section "6. DATABASE VERIFICATION"
    
    source "$VENV_PATH/bin/activate" 2>/dev/null
    
    # Test SQLite availability
    if python -c "import sqlite3; print(sqlite3.version)" &> /dev/null; then
        test_pass "SQLite available"
    else
        test_fail "SQLite not available" "Required for data storage"
    fi
    
    # Check database files
    if [ -f "$SPYDER_HOME/data/spyder.db" ]; then
        test_pass "Main database exists"
        size=$(du -h "$SPYDER_HOME/data/spyder.db" | cut -f1)
        test_info "Database size: $size"
    else
        test_info "Main database not created yet"
    fi
    
    # Test database connectivity
    python << EOF 2>/dev/null && test_pass "Database connectivity OK" || test_fail "Database connectivity failed" ""
import sqlite3
conn = sqlite3.connect('$SPYDER_HOME/data/test.db')
conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)')
conn.close()
EOF
}

# ===============================================================================
# INTEGRATION TESTS
# ===============================================================================

test_integration() {
    print_section "7. INTEGRATION TESTS"
    
    source "$VENV_PATH/bin/activate" 2>/dev/null
    cd "$SPYDER_HOME"
    
    # Test basic imports work together
    python << 'EOF' 2>/dev/null && test_pass "Module integration OK" || test_fail "Module integration failed" "Import conflicts"
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig
    from SpyderB_Broker.SpyderB14_MultiClientWatchdog import MultiClientWatchdog
    from SpyderU_Utilities.SpyderU01_Logger import Logger
    print("Integration test passed")
    exit(0)
except Exception as e:
    print(f"Integration failed: {e}")
    exit(1)
EOF
    
    # Test configuration loading
    if [ -f "$SPYDER_HOME/.env" ]; then
        python << 'EOF' 2>/dev/null && test_pass "Configuration loading OK" || test_warn "Configuration loading issues"
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / "Spyder" / ".env")
if os.getenv("SPYDER_HOME"):
    exit(0)
else:
    exit(1)
EOF
    fi
}

# ===============================================================================
# PERFORMANCE TESTS
# ===============================================================================

test_performance() {
    print_section "8. PERFORMANCE CHECKS"
    
    # Check system resources
    MEM_AVAILABLE=$(free -g | awk 'NR==2 {print $7}')
    if [ "$MEM_AVAILABLE" -ge 2 ]; then
        test_pass "Sufficient memory available: ${MEM_AVAILABLE}GB"
    else
        test_warn "Low memory available: ${MEM_AVAILABLE}GB (minimum 2GB recommended)"
    fi
    
    # Check CPU
    CPU_CORES=$(nproc)
    if [ "$CPU_CORES" -ge 2 ]; then
        test_pass "Sufficient CPU cores: $CPU_CORES"
    else
        test_warn "Limited CPU cores: $CPU_CORES (2+ recommended)"
    fi
    
    # Check disk space
    DISK_AVAILABLE=$(df -BG "$SPYDER_HOME" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$DISK_AVAILABLE" -ge 5 ]; then
        test_pass "Sufficient disk space: ${DISK_AVAILABLE}GB"
    else
        test_warn "Low disk space: ${DISK_AVAILABLE}GB (5GB+ recommended)"
    fi
    
    # Check Python startup time
    START_TIME=$(date +%s%N)
    python -c "import sys" 2>/dev/null
    END_TIME=$(date +%s%N)
    STARTUP_MS=$(( (END_TIME - START_TIME) / 1000000 ))
    
    if [ "$STARTUP_MS" -lt 500 ]; then
        test_pass "Python startup time OK: ${STARTUP_MS}ms"
    else
        test_warn "Slow Python startup: ${STARTUP_MS}ms"
    fi
}

# ===============================================================================
# SECURITY TESTS
# ===============================================================================

test_security() {
    print_section "9. SECURITY VERIFICATION"
    
    # Check file permissions
    if [ -f "$SPYDER_HOME/.env" ]; then
        PERM=$(stat -c %a "$SPYDER_HOME/.env")
        if [ "$PERM" = "600" ] || [ "$PERM" = "640" ]; then
            test_pass "Config file permissions secure: $PERM"
        else
            test_warn "Config file permissions too open: $PERM (fixing...)"
            chmod 600 "$SPYDER_HOME/.env"
        fi
    fi
    
    # Check for sensitive data in logs
    if [ -d "$LOG_DIR" ]; then
        if grep -r "password\|PASSWORD" "$LOG_DIR" 2>/dev/null | grep -v "Binary file" > /dev/null; then
            test_warn "Potential passwords found in logs"
        else
            test_pass "No passwords found in logs"
        fi
    fi
    
    # Check ownership
    OWNER=$(stat -c %U "$SPYDER_HOME")
    if [ "$OWNER" = "$USER" ]; then
        test_pass "Correct ownership: $USER"
    else
        test_warn "Incorrect ownership: $OWNER (should be $USER)"
    fi
}

# ===============================================================================
# QUICK FUNCTIONALITY TEST
# ===============================================================================

test_functionality() {
    print_section "10. QUICK FUNCTIONALITY TEST"
    
    # Test status script
    if [ -x "$SCRIPTS_DIR/SpyderQ20_Status.sh" ]; then
        if "$SCRIPTS_DIR/SpyderQ20_Status.sh" &> /dev/null; then
            test_pass "Status script works"
        else
            test_warn "Status script has issues"
        fi
    fi
    
    # Test monitor script
    if [ -f "$SCRIPTS_DIR/SpyderQ25_SystemMonitor.py" ]; then
        if python "$SCRIPTS_DIR/SpyderQ25_SystemMonitor.py" --once --json &> /dev/null; then
            test_pass "Monitor script works"
        else
            test_warn "Monitor script has issues"
        fi
    fi
    
    # Test control script
    if [ -x "$SCRIPTS_DIR/SpyderQ16_SpyderControl.sh" ]; then
        if "$SCRIPTS_DIR/SpyderQ16_SpyderControl.sh" help &> /dev/null; then
            test_pass "Control script works"
        else
            test_warn "Control script has issues"
        fi
    fi
}

# ===============================================================================
# REPORT GENERATION
# ===============================================================================

generate_report() {
    local grade=""
    local percentage=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    
    if [ $percentage -ge 90 ]; then
        grade="A"
        grade_color=$GREEN
    elif [ $percentage -ge 80 ]; then
        grade="B"
        grade_color=$GREEN
    elif [ $percentage -ge 70 ]; then
        grade="C"
        grade_color=$YELLOW
    elif [ $percentage -ge 60 ]; then
        grade="D"
        grade_color=$YELLOW
    else
        grade="F"
        grade_color=$RED
    fi
    
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  VERIFICATION REPORT${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    echo -e "Total Tests:     $TOTAL_TESTS"
    echo -e "${GREEN}Passed:          $PASSED_TESTS${NC}"
    echo -e "${RED}Failed:          $FAILED_TESTS${NC}"
    echo -e "${YELLOW}Warnings:        $WARNINGS${NC}"
    echo ""
    echo -e "Success Rate:    ${percentage}%"
    echo -e "System Grade:    ${grade_color}${grade}${NC}"
    echo ""
    
    if [ $FAILED_TESTS -gt 0 ]; then
        echo -e "${RED}⚠ CRITICAL ISSUES FOUND${NC}"
        echo "Review the log for details: $TEST_LOG"
        echo ""
        echo "Common fixes:"
        echo "  • Missing dependencies: pip install -r requirements.txt"
        echo "  • Permission issues: chmod +x scripts/SpyderQ*.sh"
        echo "  • Missing config: cp .env.example .env && edit .env"
    elif [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠ MINOR ISSUES FOUND${NC}"
        echo "System is functional but review warnings"
    else
        echo -e "${GREEN}✅ SYSTEM FULLY VERIFIED${NC}"
        echo "Ready for production use!"
    fi
    
    echo ""
    echo "Full report saved to: $TEST_LOG"
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Create log directory
    mkdir -p "$LOG_DIR"
    
    # Start logging
    echo "SPYDER SYSTEM VERIFICATION" > "$TEST_LOG"
    echo "==========================" >> "$TEST_LOG"
    echo "Date: $(date)" >> "$TEST_LOG"
    echo "" >> "$TEST_LOG"
    
    # Print header
    print_header
    
    # Run all tests
    test_environment
    test_dependencies
    test_module_imports
    test_network
    test_scripts
    test_database
    test_integration
    test_performance
    test_security
    test_functionality
    
    # Generate report
    generate_report
    
    # Return appropriate exit code
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main
main "$@"