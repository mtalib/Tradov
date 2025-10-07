#!/bin/bash
#
# Restart IB Gateway with Trusted IPs Configuration
# =================================================
#
# This script gracefully restarts IB Gateway after updating the trusted IPs
# configuration to ensure the new settings take effect.
#
# Usage:
#   ./restart_ib_gateway_with_trusted_ips.sh
#   ./restart_ib_gateway_with_trusted_ips.sh --force
#   ./restart_ib_gateway_with_trusted_ips.sh --check-only
#

set -e

# Configuration
SCRIPT_NAME="🔄 IB Gateway Restart (Trusted IPs Update)"
LOG_PREFIX="[$(date '+%H:%M:%S')]"
GATEWAY_PROCESS_NAME="ibgateway"
JTS_INI_PATH="$HOME/Jts/jts.ini"
MAX_WAIT_TIME=30
FORCE_RESTART=false
CHECK_ONLY=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${LOG_PREFIX} ${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${LOG_PREFIX} ${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${LOG_PREFIX} ${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${LOG_PREFIX} ${RED}❌ $1${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_RESTART=true
            shift
            ;;
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --help|-h)
            echo "$SCRIPT_NAME"
            echo "Usage: $0 [--force] [--check-only] [--help]"
            echo ""
            echo "Options:"
            echo "  --force      Force restart even if configuration hasn't changed"
            echo "  --check-only Only check configuration, don't restart"
            echo "  --help       Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to get current IB Gateway process ID
get_gateway_pid() {
    pgrep -f "ibgateway.*GWClient" 2>/dev/null | head -n1
}

# Function to check if IB Gateway is running
is_gateway_running() {
    local pid=$(get_gateway_pid)
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# Function to check port 4002 status
check_port_status() {
    if netstat -tlnp 2>/dev/null | grep -q ":4002.*LISTEN"; then
        return 0
    else
        return 1
    fi
}

# Function to verify trusted IPs configuration
check_trusted_ips_config() {
    if [[ ! -f "$JTS_INI_PATH" ]]; then
        log_error "jts.ini file not found: $JTS_INI_PATH"
        return 1
    fi

    local current_ips
    current_ips=$(grep -i "^TrustedIPs" "$JTS_INI_PATH" 2>/dev/null | cut -d'=' -f2 | tr -d ' ')

    if [[ -z "$current_ips" ]]; then
        log_warning "No TrustedIPs setting found in jts.ini"
        return 1
    fi

    local system_ip
    system_ip=$(hostname -I | awk '{print $1}')

    log_info "Current TrustedIPs: $current_ips"
    log_info "System IP: $system_ip"

    if [[ "$current_ips" == *"$system_ip"* ]]; then
        log_success "System IP ($system_ip) is in TrustedIPs configuration"
        return 0
    else
        log_error "System IP ($system_ip) NOT found in TrustedIPs configuration"
        log_error "Current TrustedIPs: $current_ips"
        return 1
    fi
}

# Function to gracefully stop IB Gateway
stop_gateway() {
    local pid=$(get_gateway_pid)

    if [[ -z "$pid" ]]; then
        log_info "IB Gateway is not running"
        return 0
    fi

    log_info "Stopping IB Gateway (PID: $pid)..."

    # Try graceful shutdown first
    if kill -TERM "$pid" 2>/dev/null; then
        log_info "Sent SIGTERM to IB Gateway, waiting for graceful shutdown..."

        # Wait for graceful shutdown
        local count=0
        while [[ $count -lt $MAX_WAIT_TIME ]]; do
            if ! kill -0 "$pid" 2>/dev/null; then
                log_success "IB Gateway stopped gracefully"
                return 0
            fi
            sleep 1
            ((count++))
        done

        # If still running after graceful timeout, force kill
        log_warning "Graceful shutdown timeout, forcing termination..."
        if kill -KILL "$pid" 2>/dev/null; then
            sleep 2
            if ! kill -0 "$pid" 2>/dev/null; then
                log_success "IB Gateway force-stopped"
                return 0
            fi
        fi
    fi

    log_error "Failed to stop IB Gateway"
    return 1
}

# Function to start IB Gateway
start_gateway() {
    log_info "Starting IB Gateway..."

    # Check if gateway startup scripts exist
    local gateway_script=""

    # Look for common IB Gateway startup methods
    if [[ -f "./launch_spyder_with_gateway.sh" ]]; then
        gateway_script="./launch_spyder_with_gateway.sh"
    elif [[ -f "./launch_balanced_gateway.sh" ]]; then
        gateway_script="./launch_balanced_gateway.sh"
    elif [[ -x "$HOME/Jts/ibgateway/*/ibgateway" ]]; then
        gateway_script=$(find "$HOME/Jts/ibgateway" -name "ibgateway" -executable | head -n1)
    else
        log_warning "No standard IB Gateway startup script found"
        log_info "Please start IB Gateway manually"
        return 1
    fi

    log_info "Using startup script: $gateway_script"

    # Start IB Gateway in background
    if [[ "$gateway_script" == *"launch_spyder"* ]]; then
        log_info "Starting IB Gateway through Spyder launcher..."
        nohup "$gateway_script" > /dev/null 2>&1 &
    else
        log_info "Starting IB Gateway directly..."
        nohup "$gateway_script" > /dev/null 2>&1 &
    fi

    # Wait for startup
    log_info "Waiting for IB Gateway to start..."
    local count=0
    while [[ $count -lt $MAX_WAIT_TIME ]]; do
        if check_port_status; then
            log_success "IB Gateway is listening on port 4002"
            break
        fi
        sleep 1
        ((count++))
    done

    if check_port_status; then
        log_success "IB Gateway started successfully"
        return 0
    else
        log_error "IB Gateway startup timeout or failed"
        return 1
    fi
}

# Function to test connection after restart
test_connection() {
    log_info "Testing connection to IB Gateway..."

    # Test with telnet-style connection
    if command -v timeout >/dev/null 2>&1; then
        local test_result
        test_result=$(timeout 3 bash -c 'echo | telnet localhost 4002' 2>&1)

        if [[ "$test_result" == *"Connected"* ]]; then
            if [[ "$test_result" == *"Connection closed by foreign host"* ]]; then
                log_warning "Connection established but immediately closed (authentication needed)"
                log_info "This suggests IB Gateway is running but needs proper API client connection"
            else
                log_success "Connection test successful"
            fi
        else
            log_error "Connection test failed"
            log_error "Result: $test_result"
        fi
    else
        log_info "Telnet not available for connection test"
    fi

    # Show current listening status
    local listening_info
    listening_info=$(netstat -tlnp 2>/dev/null | grep ":4002" || echo "No process listening on port 4002")
    log_info "Port status: $listening_info"
}

# Main execution
main() {
    echo "$SCRIPT_NAME"
    echo "=================================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Mode: $(if [[ "$CHECK_ONLY" == "true" ]]; then echo "CHECK ONLY"; elif [[ "$FORCE_RESTART" == "true" ]]; then echo "FORCE RESTART"; else echo "NORMAL RESTART"; fi)"
    echo "=================================================="

    # Step 1: Check trusted IPs configuration
    log_info "Checking trusted IPs configuration..."
    if ! check_trusted_ips_config; then
        log_error "Trusted IPs configuration check failed"
        log_error "Please run: python fix_ib_gateway_trusted_ips.py"
        exit 1
    fi

    if [[ "$CHECK_ONLY" == "true" ]]; then
        log_success "Configuration check completed - trusted IPs are correctly configured"
        exit 0
    fi

    # Step 2: Check if restart is needed
    if [[ "$FORCE_RESTART" != "true" ]]; then
        if is_gateway_running && check_port_status; then
            log_info "IB Gateway is already running and configuration looks correct"
            log_info "Use --force to restart anyway"

            # Test connection with current setup
            test_connection
            exit 0
        fi
    fi

    # Step 3: Stop IB Gateway if running
    if is_gateway_running; then
        if ! stop_gateway; then
            log_error "Failed to stop IB Gateway"
            exit 1
        fi
    fi

    # Step 4: Wait a moment for cleanup
    log_info "Waiting for system cleanup..."
    sleep 3

    # Step 5: Start IB Gateway
    if ! start_gateway; then
        log_error "Failed to start IB Gateway"
        exit 1
    fi

    # Step 6: Test the connection
    sleep 2
    test_connection

    # Success message
    echo ""
    echo "=================================================="
    echo "✅ IB GATEWAY RESTART COMPLETED SUCCESSFULLY"
    echo "=================================================="
    echo "📊 Status: IB Gateway is running with updated trusted IPs"
    echo "🌐 Trusted IPs: $(grep -i '^TrustedIPs' "$JTS_INI_PATH" | cut -d'=' -f2)"
    echo "🔌 Port 4002: $(if check_port_status; then echo "LISTENING"; else echo "NOT LISTENING"; fi)"
    echo ""
    echo "🔄 NEXT STEPS:"
    echo "   1. Test API connection from your trading applications"
    echo "   2. Monitor IB Gateway logs for successful connections"
    echo "   3. Verify that API clients can now connect without immediate disconnection"
    echo ""
    echo "🛠️  TROUBLESHOOTING:"
    echo "   • If connections still fail, check IB Gateway API settings in the GUI"
    echo "   • Verify 'Enable ActiveX and Socket Clients' is checked"
    echo "   • Ensure correct trading mode (paper/live) is selected"
    echo "   • Check client ID conflicts in your applications"
}

# Error handling
trap 'log_error "Script interrupted"; exit 1' INT TERM

# Run main function
main "$@"
