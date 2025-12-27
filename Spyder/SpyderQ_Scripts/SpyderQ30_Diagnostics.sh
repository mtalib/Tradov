#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ30_Diagnostics.sh
# Group: Q (Scripts)
# Purpose: System diagnostics and troubleshooting utility
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 16:15:00
#
# Description:
#     Comprehensive diagnostic tool that checks system dependencies, network
#     connectivity, IB Gateway configuration, Python environment, and identifies
#     common issues. Generates detailed diagnostic reports for troubleshooting.
# ===============================================================================

set -e

# ===============================================================================
# CONFIGURATION
# ===============================================================================
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
VENV_PATH="$SPYDER_HOME/spyder_venv"
LOG_DIR="$SPYDER_HOME/logs"
REPORT_DIR="$SPYDER_HOME/diagnostics"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/diagnostic_report_$TIMESTAMP.txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNINGS=0

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║           SPYDER SYSTEM DIAGNOSTICS TOOL                  ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    echo -e "\n${CYAN}═══ $1 ═══${NC}"
    echo -e "\n${CYAN}═══ $1 ═══${NC}" >> "$REPORT_FILE"
}

test_pass() {
    local test_name=$1
    local details=$2
    echo -e "${GREEN}[✓]${NC} $test_name: PASS $details"
    echo "[✓] $test_name: PASS $details" >> "$REPORT_FILE"
    ((TOTAL_TESTS++))
    ((PASSED_TESTS++))
}

test_fail() {
    local test_name=$1
    local details=$2
    echo -e "${RED}[✗]${NC} $test_name: FAIL - $details"
    echo "[✗] $test_name: FAIL - $details" >> "$REPORT_FILE"
    ((TOTAL_TESTS++))
    ((FAILED_TESTS++))
}

test_warn() {
    local test_name=$1
    local details=$2
    echo -e "${YELLOW}[!]${NC} $test_name: WARNING - $details"
    echo "[!] $test_name: WARNING - $details" >> "$REPORT_FILE"
    ((WARNINGS++))
}

# ===============================================================================
# DIAGNOSTIC TESTS
# ===============================================================================

check_system_requirements() {
    print_section "System Requirements"
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        local os_info=$(lsb_release -d 2>/dev/null | cut -f2 || echo "Unknown Linux")
        test_pass "Operating System" "- $os_info"
    else
        test_fail "Operating System" "Not Linux ($OSTYPE)"
    fi
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 --version 2>&1 | awk '{print $2}')
        local major=$(echo $python_version | cut -d. -f1)
        local minor=$(echo $python_version | cut -d. -f2)
        
        if [ "$major" -eq 3 ] && [ "$minor" -ge 8 ]; then
            test_pass "Python Version" "- $python_version"
        else
            test_fail "Python Version" "$python_version (requires 3.8+)"
        fi
    else
        test_fail "Python" "Not installed"
    fi
    
    # Check memory
    local total_mem=$(free -m | awk 'NR==2{print $2}')
    local available_mem=$(free -m | awk 'NR==2{print $7}')
    
    if [ "$total_mem" -ge 4096 ]; then
        test_pass "System Memory" "- ${total_mem}MB total, ${available_mem}MB available"
    else
        test_warn "System Memory" "${total_mem}MB (recommend 4GB+)"
    fi
    
    # Check disk space
    local disk_free=$(df -h "$SPYDER_HOME" | awk 'NR==2{print $4}')
    local disk_free_mb=$(df -m "$SPYDER_HOME" | awk 'NR==2{print $4}')
    
    if [ "$disk_free_mb" -ge 1024 ]; then
        test_pass "Disk Space" "- $disk_free available"
    else
        test_warn "Disk Space" "$disk_free (recommend 1GB+)"
    fi
}

check_spyder_installation() {
    print_section "Spyder Installation"
    
    # Check directory structure
    if [ -d "$SPYDER_HOME" ]; then
        test_pass "Spyder Directory" "- $SPYDER_HOME"
    else
        test_fail "Spyder Directory" "Not found at $SPYDER_HOME"
        return
    fi
    
    # Check virtual environment
    if [ -d "$VENV_PATH" ]; then
        test_pass "Virtual Environment" "- $VENV_PATH"
        
        # Check activation
        if [ -f "$VENV_PATH/bin/activate" ]; then
            test_pass "Venv Activation Script" ""
        else
            test_fail "Venv Activation Script" "Not found"
        fi
    else
        test_fail "Virtual Environment" "Not found at $VENV_PATH"
    fi
    
    # Check core modules
    local modules=(
        "SpyderA_Core"
        "SpyderB_Broker"
        "SpyderC_MarketData"
        "SpyderG_GUI"
        "SpyderQ_Scripts"
    )
    
    for module in "${modules[@]}"; do
        if [ -d "$SPYDER_HOME/$module" ]; then
            local count=$(find "$SPYDER_HOME/$module" -name "*.py" | wc -l)
            test_pass "$module" "- $count Python files"
        else
            test_fail "$module" "Directory not found"
        fi
    done
}

check_python_dependencies() {
    print_section "Python Dependencies"
    
    # Activate virtual environment
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        
        # Check critical packages
        local packages=(
            "ibapi"
            "ib_async"
            "PyQt6"
            "pandas"
            "numpy"
            "matplotlib"
            "prometheus_client"
        )
        
        for package in "${packages[@]}"; do
            if python3 -c "import $package" 2>/dev/null; then
                local version=$(python3 -c "import $package; print(getattr($package, '__version__', 'installed'))" 2>/dev/null || echo "installed")
                test_pass "$package" "- $version"
            else
                test_fail "$package" "Not installed"
            fi
        done
        
        deactivate
    else
        test_fail "Dependency Check" "Cannot activate virtual environment"
    fi
}

check_network_connectivity() {
    print_section "Network Connectivity"
    
    # Check localhost
    if ping -c 1 127.0.0.1 &> /dev/null; then
        test_pass "Localhost" ""
    else
        test_fail "Localhost" "Cannot ping 127.0.0.1"
    fi
    
    # Check IB ports
    local ports=("4001:Live Trading" "4002:Paper Trading" "9090:Prometheus")
    
    for port_info in "${ports[@]}"; do
        IFS=':' read -r port description <<< "$port_info"
        
        if nc -z localhost $port 2>/dev/null; then
            test_pass "Port $port" "- $description (OPEN)"
        else
            test_warn "Port $port" "$description (CLOSED)"
        fi
    done
    
    # Check internet connectivity
    if ping -c 1 google.com &> /dev/null; then
        test_pass "Internet Connection" ""
    else
        test_warn "Internet Connection" "Cannot reach google.com"
    fi
}

check_ib_gateway() {
    print_section "IB Gateway Configuration"
    
    # Check IB Gateway installation
    local ib_paths=(
        "$HOME/Jts"
        "$HOME/IBController"
        "/opt/ibgateway"
    )
    
    local found_gateway=false
    for path in "${ib_paths[@]}"; do
        if [ -d "$path" ]; then
            test_pass "IB Gateway Directory" "- Found at $path"
            found_gateway=true
            break
        fi
    done
    
    if [ "$found_gateway" = false ]; then
        test_fail "IB Gateway" "Not found in standard locations"
    fi
    
    # Check if IB Gateway is running
    if pgrep -f "ibgateway" > /dev/null 2>&1; then
        local pid=$(pgrep -f "ibgateway" | head -1)
        test_pass "IB Gateway Process" "- Running (PID: $pid)"
    else
        test_warn "IB Gateway Process" "Not running"
    fi
    
    # Check configuration file
    if [ -f "$SPYDER_HOME/.env" ]; then
        test_pass "Configuration File" "- .env found"
        
        # Check for required settings
        if grep -q "IB_GATEWAY_HOST" "$SPYDER_HOME/.env"; then
            test_pass "IB Gateway Host Config" ""
        else
            test_warn "IB Gateway Host" "Not configured in .env"
        fi
    else
        test_fail "Configuration File" ".env not found"
    fi
}

check_log_files() {
    print_section "Log Files Analysis"
    
    if [ -d "$LOG_DIR" ]; then
        # Check log directory size
        local log_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
        test_pass "Log Directory" "- Size: $log_size"
        
        # Check for recent errors
        local error_count=0
        if [ -f "$LOG_DIR/system/main.log" ]; then
            error_count=$(grep -c "ERROR\|CRITICAL" "$LOG_DIR/system/main.log" 2>/dev/null || echo "0")
            
            if [ "$error_count" -eq 0 ]; then
                test_pass "System Log Errors" "- No errors found"
            else
                test_warn "System Log Errors" "$error_count errors found"
            fi
        fi
        
        # Check log rotation
        local old_logs=$(find "$LOG_DIR" -name "*.log" -mtime +7 | wc -l)
        if [ "$old_logs" -gt 0 ]; then
            test_warn "Old Log Files" "$old_logs files older than 7 days"
        else
            test_pass "Log Rotation" "- No old logs"
        fi
    else
        test_fail "Log Directory" "Not found at $LOG_DIR"
    fi
}

check_permissions() {
    print_section "File Permissions"
    
    # Check script permissions
    local scripts=(
        "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
        "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ11_StopAll.sh"
        "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ20_Status.sh"
    )
    
    for script in "${scripts[@]}"; do
        if [ -f "$script" ]; then
            if [ -x "$script" ]; then
                test_pass "$(basename $script)" "- Executable"
            else
                test_fail "$(basename $script)" "Not executable"
            fi
        else
            test_warn "$(basename $script)" "Not found"
        fi
    done
    
    # Check directory permissions
    if [ -w "$LOG_DIR" ]; then
        test_pass "Log Directory" "- Writable"
    else
        test_fail "Log Directory" "Not writable"
    fi
}

generate_recommendations() {
    print_section "Recommendations"
    
    echo -e "\n${CYAN}Based on diagnostics:${NC}"
    echo -e "\nBased on diagnostics:" >> "$REPORT_FILE"
    
    if [ "$FAILED_TESTS" -gt 0 ]; then
        echo -e "${RED}Critical Issues to Fix:${NC}"
        echo "Critical Issues to Fix:" >> "$REPORT_FILE"
        
        # Provide specific recommendations based on failures
        if ! command -v python3 &> /dev/null; then
            echo "  • Install Python 3.8 or higher"
            echo "  • Install Python 3.8 or higher" >> "$REPORT_FILE"
        fi
        
        if [ ! -d "$VENV_PATH" ]; then
            echo "  • Create virtual environment: python3 -m venv $VENV_PATH"
            echo "  • Create virtual environment: python3 -m venv $VENV_PATH" >> "$REPORT_FILE"
        fi
        
        if ! pgrep -f "ibgateway" > /dev/null 2>&1; then
            echo "  • Start IB Gateway before running Spyder"
            echo "  • Start IB Gateway before running Spyder" >> "$REPORT_FILE"
        fi
    fi
    
    if [ "$WARNINGS" -gt 0 ]; then
        echo -e "\n${YELLOW}Warnings to Address:${NC}"
        echo -e "\nWarnings to Address:" >> "$REPORT_FILE"
        echo "  • Review warning items above for optimal performance"
        echo "  • Review warning items above for optimal performance" >> "$REPORT_FILE"
    fi
    
    if [ "$FAILED_TESTS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
        echo -e "${GREEN}System is ready for trading!${NC}"
        echo "System is ready for trading!" >> "$REPORT_FILE"
    fi
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Create report directory
    mkdir -p "$REPORT_DIR"
    
    # Initialize report file
    echo "SPYDER DIAGNOSTIC REPORT" > "$REPORT_FILE"
    echo "Generated: $(date)" >> "$REPORT_FILE"
    echo "========================================" >> "$REPORT_FILE"
    
    # Display header
    clear
    print_header
    echo ""
    
    # Run all diagnostic checks
    check_system_requirements
    check_spyder_installation
    check_python_dependencies
    check_network_connectivity
    check_ib_gateway
    check_log_files
    check_permissions
    
    # Generate summary
    echo ""
    echo -e "${CYAN}═══ DIAGNOSTIC SUMMARY ═══${NC}"
    echo ""
    echo -e "Total Tests: $TOTAL_TESTS"
    echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
    echo -e "${RED}Failed: $FAILED_TESTS${NC}"
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    
    # Calculate health score
    if [ "$TOTAL_TESTS" -gt 0 ]; then
        local health_score=$((PASSED_TESTS * 100 / TOTAL_TESTS))
        echo ""
        
        if [ "$health_score" -ge 90 ]; then
            echo -e "System Health: ${GREEN}${health_score}% - EXCELLENT${NC}"
        elif [ "$health_score" -ge 70 ]; then
            echo -e "System Health: ${YELLOW}${health_score}% - GOOD${NC}"
        else
            echo -e "System Health: ${RED}${health_score}% - NEEDS ATTENTION${NC}"
        fi
    fi
    
    # Generate recommendations
    generate_recommendations
    
    # Save report location
    echo ""
    echo -e "${CYAN}Full report saved to: $REPORT_FILE${NC}"
    echo ""
}

# Run diagnostics
main "$@"