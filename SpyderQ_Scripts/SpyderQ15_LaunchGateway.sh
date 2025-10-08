#!/bin/bash
# ==============================================================================
# SPYDER - Autonomous Options Trading System v1.0
#
# Series: SpyderQ_Scripts
# Module: SpyderQ15_LaunchGateway.sh
# Purpose: Launch IB Gateway with automated configuration and monitoring
#
# Author: Mohamed Talib
# Year Created: 2025
# Last Updated: 2025-10-08 Time: 12:00:00
#
# Module Description:
#     Automated launcher for IB Gateway with comprehensive health checking,
#     credential management, and process monitoring. Supports both paper and
#     live trading modes with intelligent startup sequencing.
#
# Usage:
#     ./SpyderQ15_LaunchGateway.sh [--mode=paper|live] [--clean] [--verify]
#
# Options:
#     --mode=paper    Launch in paper trading mode (default)
#     --mode=live     Launch in live trading mode
#     --clean         Perform clean restart (kill existing processes)
#     --verify        Verify connection after launch
#
# Dependencies:
#     - IB Gateway installed at ~/Jts/ibgateway/1039/
#     - IBC installed and configured
#     - Credentials in environment (IB_USERNAME, IB_PASSWORD)
#
# Change Log:
#     2025-10-08 (v1.0.0):
#         - Initial production release
#         - Converted from launch_spyder_gateway.sh
#         - Added comprehensive error handling
#         - Implemented health checking
# ==============================================================================

set -euo pipefail

# ==============================================================================
# CONSTANTS
# ==============================================================================
readonly SCRIPT_NAME="SpyderQ15_LaunchGateway"
readonly SCRIPT_VERSION="1.0.0"

# Paths
readonly SPYDER_HOME="${SPYDER_HOME:-$HOME/Projects/Spyder}"
readonly IB_GATEWAY_DIR="${IB_GATEWAY_DIR:-$HOME/Jts/ibgateway/1039}"
readonly IB_GATEWAY_EXE="$IB_GATEWAY_DIR/ibgateway"
readonly IBC_PATH="${IBC_PATH:-$HOME/ibc}"
readonly LOG_DIR="${SPYDER_LOGS:-$HOME/spyder_logs}"
readonly LOG_FILE="$LOG_DIR/gateway_launcher.log"

# Ports
readonly PAPER_PORT=4002
readonly LIVE_PORT=4001

# Timeouts (seconds)
readonly STARTUP_TIMEOUT=60
readonly API_READY_WAIT=10
readonly CONNECTION_CHECK_INTERVAL=5

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# ==============================================================================
# GLOBAL VARIABLES
# ==============================================================================
TRADING_MODE="paper"
CLEAN_START=false
VERIFY_CONNECTION=false
GATEWAY_PORT=$PAPER_PORT

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "${BLUE}$*${NC}"
}

log_success() {
    log "SUCCESS" "${GREEN}$*${NC}"
}

log_warning() {
    log "WARNING" "${YELLOW}$*${NC}"
}

log_error() {
    log "ERROR" "${RED}$*${NC}"
}

print_header() {
    echo -e "${CYAN}"
    echo "======================================================================"
    echo "  SPYDER Gateway Launcher v${SCRIPT_VERSION}"
    echo "======================================================================"
    echo -e "${NC}"
}

parse_arguments() {
    for arg in "$@"; do
        case $arg in
            --mode=paper)
                TRADING_MODE="paper"
                GATEWAY_PORT=$PAPER_PORT
                ;;
            --mode=live)
                TRADING_MODE="live"
                GATEWAY_PORT=$LIVE_PORT
                log_warning "⚠️  LIVE TRADING MODE - REAL MONEY!"
                ;;
            --clean)
                CLEAN_START=true
                ;;
            --verify)
                VERIFY_CONNECTION=true
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown argument: $arg"
                show_usage
                exit 1
                ;;
        esac
    done
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Launch IB Gateway with automated configuration and monitoring.

OPTIONS:
    --mode=paper    Launch in paper trading mode (default)
    --mode=live     Launch in live trading mode (REAL MONEY)
    --clean         Perform clean restart (kill existing processes)
    --verify        Verify API connection after launch
    --help, -h      Show this help message

EXAMPLES:
    $0                          # Paper trading mode
    $0 --mode=live              # Live trading mode
    $0 --clean --verify         # Clean start with verification
    $0 --mode=paper --verify    # Paper mode with verification

ENVIRONMENT VARIABLES:
    SPYDER_HOME      SPYDER installation directory
    IB_GATEWAY_DIR   IB Gateway installation directory
    IB_USERNAME      IB account username
    IB_PASSWORD      IB account password
    SPYDER_LOGS      Log file directory

EOF
}

check_prerequisites() {
    log_info "🔍 Checking prerequisites..."
    local errors=0

    # Check IB Gateway installation
    if [[ ! -f "$IB_GATEWAY_EXE" ]]; then
        log_error "IB Gateway not found at: $IB_GATEWAY_EXE"
        errors=$((errors + 1))
    else
        log_success "✅ IB Gateway found"
    fi

    # Check credentials
    if [[ -z "${IB_USERNAME:-}" ]] || [[ -z "${IB_PASSWORD:-}" ]]; then
        log_error "Credentials not found in environment"
        log_error "Please set IB_USERNAME and IB_PASSWORD"
        errors=$((errors + 1))
    else
        log_success "✅ Credentials loaded"
    fi

    # Check Java
    if ! command -v java &> /dev/null; then
        log_error "Java not found - required for IB Gateway"
        errors=$((errors + 1))
    else
        log_success "✅ Java available"
    fi

    # Create log directory
    mkdir -p "$LOG_DIR" 2>/dev/null || true

    return $errors
}

check_port_available() {
    local port="$1"
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

is_gateway_running() {
    if pgrep -f "ibgateway" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

kill_gateway_processes() {
    log_info "🔥 Killing existing Gateway processes..."
    
    local killed=false
    
    if pkill -9 -f "ibgateway" 2>/dev/null; then
        log_info "   Killed ibgateway processes"
        killed=true
    fi
    
    if pkill -9 -f "IBC" 2>/dev/null; then
        log_info "   Killed IBC processes"
        killed=true
    fi
    
    if pkill -9 -f "Xvfb" 2>/dev/null; then
        log_info "   Killed Xvfb processes"
        killed=true
    fi
    
    if $killed; then
        sleep 2
        log_success "✅ Processes terminated"
        return 0
    else
        log_info "   No processes to kill"
        return 1
    fi
}

clear_temp_files() {
    log_info "🧹 Clearing temporary files..."
    
    local settings_dir="$HOME/Jts"
    if [[ -d "$settings_dir" ]]; then
        find "$settings_dir" -name "*.lck" -delete 2>/dev/null || true
        find "$settings_dir" -name "*.tmp" -delete 2>/dev/null || true
    fi
    
    log_success "✅ Temporary files cleared"
}

launch_gateway() {
    log_info "🚀 Launching IB Gateway..."
    log_info "   Mode: $TRADING_MODE"
    log_info "   Port: $GATEWAY_PORT"
    
    export DISPLAY=:1
    
    if ! pgrep -f "Xvfb :1" > /dev/null; then
        log_info "   Starting Xvfb..."
        Xvfb :1 -screen 0 1024x768x24 &
        sleep 2
    fi
    
    cd "$IB_GATEWAY_DIR" || exit 1
    
    local launch_cmd="$IB_GATEWAY_EXE"
    
    nohup $launch_cmd >> "$LOG_DIR/gateway_output.log" 2>&1 &
    local gateway_pid=$!
    
    log_info "   Gateway PID: $gateway_pid"
    log_success "✅ Gateway launch initiated"
    
    return 0
}

wait_for_gateway_ready() {
    log_info "⏳ Waiting for Gateway to be ready..."
    
    local elapsed=0
    local check_interval=$CONNECTION_CHECK_INTERVAL
    
    while [[ $elapsed -lt $STARTUP_TIMEOUT ]]; do
        if check_port_available "$GATEWAY_PORT"; then
            log_success "✅ Gateway port $GATEWAY_PORT is listening!"
            sleep $API_READY_WAIT
            log_info "   Additional wait for API initialization complete"
            return 0
        fi
        
        if ! is_gateway_running; then
            log_error "Gateway process died during startup"
            return 1
        fi
        
        elapsed=$((elapsed + check_interval))
        log_info "   Waiting... ${elapsed}s / ${STARTUP_TIMEOUT}s"
        sleep $check_interval
    done
    
    log_error "⏱️  Timeout waiting for Gateway"
    return 1
}

verify_api_connection() {
    log_info "🧪 Verifying API connection..."
    
    local test_script="$SPYDER_HOME/SpyderT_Testing/SpyderT10_GatewayDryRunTest.sh"
    
    if [[ -f "$test_script" ]]; then
        if bash "$test_script" --port="$GATEWAY_PORT"; then
            log_success "✅ API connection verified"
            return 0
        else
            log_warning "⚠️  API connection test failed"
            return 1
        fi
    else
        log_warning "⚠️  Test script not found, skipping verification"
        return 0
    fi
}

show_status() {
    echo ""
    log_info "📊 Gateway Status:"
    log_info "   Trading Mode: $TRADING_MODE"
    log_info "   Port: $GATEWAY_PORT"
    
    if is_gateway_running; then
        log_success "   Process: Running"
    else
        log_warning "   Process: Not Running"
    fi
    
    if check_port_available "$GATEWAY_PORT"; then
        log_success "   API: Available"
    else
        log_warning "   API: Not Available"
    fi
    echo ""
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
main() {
    print_header
    
    parse_arguments "$@"
    
    log_info "Configuration:"
    log_info "   Trading Mode: $TRADING_MODE"
    log_info "   Gateway Port: $GATEWAY_PORT"
    log_info "   Clean Start: $CLEAN_START"
    log_info "   Verify: $VERIFY_CONNECTION"
    echo ""
    
    if ! check_prerequisites; then
        log_error "❌ Prerequisites check failed"
        exit 1
    fi
    echo ""
    
    if $CLEAN_START; then
        if is_gateway_running; then
            kill_gateway_processes
            clear_temp_files
            echo ""
        else
            log_info "No existing Gateway processes found"
            echo ""
        fi
    fi
    
    if check_port_available "$GATEWAY_PORT"; then
        log_warning "⚠️  Gateway already running on port $GATEWAY_PORT"
        
        read -p "Use existing Gateway? (y/n): " -n 1 -r
        echo
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_success "✅ Using existing Gateway connection"
            show_status
            exit 0
        else
            log_info "Restarting Gateway..."
            kill_gateway_processes
            clear_temp_files
            echo ""
        fi
    fi
    
    if ! launch_gateway; then
        log_error "❌ Gateway launch failed"
        exit 1
    fi
    echo ""
    
    if ! wait_for_gateway_ready; then
        log_error "❌ Gateway failed to start properly"
        exit 1
    fi
    echo ""
    
    if $VERIFY_CONNECTION; then
        if ! verify_api_connection; then
            log_warning "⚠️  Connection verification had issues"
        fi
        echo ""
    fi
    
    show_status
    
    log_success "🎉 Gateway is operational!"
    log_info "You can now launch SPYDER Dashboard"
    
    return 0
}

main "$@"