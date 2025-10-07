#!/bin/bash
# SPYDER - Quick Launch Script
# Automatically chooses the best available connection method and launches SPYDER

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}🕷️  SPYDER - Quick Launch${NC}"
echo -e "${CYAN}==========================${NC}"
echo

# Function to log with timestamp
log() {
    echo -e "[$(date '+%H:%M:%S')] $1"
}

# Function to get trading mode from arguments or environment
get_trading_mode() {
    local mode=""

    # Check command line arguments
    for arg in "$@"; do
        case "$arg" in
            --mode=*)
                mode="${arg#*=}"
                ;;
            --paper)
                mode="paper"
                ;;
            --live)
                mode="live"
                ;;
        esac
    done

    # Fallback to environment variable or default
    if [[ -z "$mode" ]]; then
        mode="${TRADING_MODE:-paper}"
    fi

    echo "$mode"
}

# Function to get TWS IP from config
get_tws_ip() {
    if [[ -f "config/config_remote_tws.py" ]]; then
        grep -o '"ip_address":\s*"[^"]*"' config/config_remote_tws.py | sed 's/"ip_address":\s*"\([^"]*\)"/\1/' | head -1
    elif [[ -f "config/config.py" ]] && grep -q "remote_tws" config/config.py; then
        grep -o '"ip_address":\s*"[^"]*"' config/config.py | sed 's/"ip_address":\s*"\([^"]*\)"/\1/' | head -1
    else
        echo "192.168.1.244"  # Default fallback
    fi
}

# Function to test Gateway availability
test_gateway_availability() {
    local gateway_available=false
    local gateway_running=false
    local port_accessible=false

    # Check if Gateway process is running
    if pgrep -f "ibgateway" > /dev/null 2>&1; then
        gateway_running=true
    fi

    # Test port accessibility (paper trading port)
    if timeout 2 bash -c "</dev/tcp/127.0.0.1/4002" 2>/dev/null; then
        port_accessible=true
    fi

    if [[ "$gateway_running" == true ]] && [[ "$port_accessible" == true ]]; then
        gateway_available=true
    fi

    echo "$gateway_available"
}

# Function to test TWS availability
test_tws_availability() {
    local tws_available=false
    local tws_ip=$(get_tws_ip)

    # Quick ping test (1 second timeout)
    if ping -c 1 -W 1 "$tws_ip" > /dev/null 2>&1; then
        # Test port accessibility (paper trading port)
        if timeout 3 bash -c "</dev/tcp/$tws_ip/7497" 2>/dev/null; then
            tws_available=true
        fi
    fi

    echo "$tws_available"
}

# Function to determine best connection method
determine_best_connection() {
    local trading_mode="$1"

    log "${BLUE}🔍 Scanning available connection methods...${NC}"

    # Test Gateway
    local gateway_available=$(test_gateway_availability)
    if [[ "$gateway_available" == "true" ]]; then
        log "${GREEN}✅ IB Gateway: Available${NC}"
    else
        log "${RED}❌ IB Gateway: Not available${NC}"
    fi

    # Test TWS
    local tws_available=$(test_tws_availability)
    if [[ "$tws_available" == "true" ]]; then
        local tws_ip=$(get_tws_ip)
        log "${GREEN}✅ Remote TWS: Available (${tws_ip})${NC}"
    else
        log "${RED}❌ Remote TWS: Not available${NC}"
    fi

    # Decision logic
    if [[ "$tws_available" == "true" ]]; then
        # Prefer TWS if available (better stability, no handshake issues)
        log "${CYAN}🎯 Best choice: Remote TWS (preferred for stability)${NC}"
        echo "tws"
    elif [[ "$gateway_available" == "true" ]]; then
        # Use Gateway as fallback
        log "${CYAN}🎯 Best choice: IB Gateway (fallback option)${NC}"
        echo "gateway"
    else
        # No connection available
        log "${RED}❌ No connection methods available${NC}"
        echo "none"
    fi
}

# Function to show connection method summary
show_connection_summary() {
    local method="$1"
    local trading_mode="$2"

    case "$method" in
        "tws")
            local tws_ip=$(get_tws_ip)
            local port=$([ "$trading_mode" = "live" ] && echo "7496" || echo "7497")
            echo
            echo -e "${GREEN}=================================${NC}"
            echo -e "${GREEN}🌐 SPYDER - Remote TWS Mode${NC}"
            echo -e "${GREEN}   TWS Computer: ${tws_ip}${NC}"
            echo -e "${GREEN}   Port: ${port}${NC}"
            echo -e "${GREEN}   Trading Mode: ${trading_mode^^}${NC}"
            echo -e "${GREEN}   Status: Quick Launch${NC}"
            echo -e "${GREEN}=================================${NC}"
            ;;
        "gateway")
            local port=$([ "$trading_mode" = "live" ] && echo "4001" || echo "4002")
            echo
            echo -e "${GREEN}=================================${NC}"
            echo -e "${GREEN}🏪 SPYDER - IB Gateway Mode${NC}"
            echo -e "${GREEN}   Gateway: 127.0.0.1:${port}${NC}"
            echo -e "${GREEN}   Trading Mode: ${trading_mode^^}${NC}"
            echo -e "${GREEN}   Status: Quick Launch${NC}"
            echo -e "${GREEN}=================================${NC}"
            ;;
    esac
}

# Function to launch with selected method
launch_with_method() {
    local method="$1"
    local trading_mode="$2"

    case "$method" in
        "tws")
            if [[ -f "./launch_spyder_tws.sh" ]]; then
                log "${GREEN}🚀 Launching with Remote TWS...${NC}"
                exec ./launch_spyder_tws.sh --mode="$trading_mode"
            else
                log "${RED}❌ TWS launcher not found${NC}"
                exit 1
            fi
            ;;
        "gateway")
            if [[ -f "./launch_spyder_gateway.sh" ]]; then
                log "${GREEN}🚀 Launching with IB Gateway...${NC}"
                exec ./launch_spyder_gateway.sh --mode="$trading_mode"
            else
                log "${RED}❌ Gateway launcher not found${NC}"
                exit 1
            fi
            ;;
        "none")
            log "${RED}❌ No connection methods available${NC}"
            echo
            log "${YELLOW}🔧 Troubleshooting suggestions:${NC}"
            log "${YELLOW}   • Start IB Gateway: ./launch_spyder_with_gateway.sh${NC}"
            log "${YELLOW}   • Check TWS computer connection${NC}"
            log "${YELLOW}   • Run full diagnostics: ./test_all_connections.sh --full${NC}"
            log "${YELLOW}   • Use connection selector: ./launch_connection_selector.py${NC}"
            exit 1
            ;;
    esac
}

# Function to show help
show_help() {
    echo "SPYDER Quick Launch - Automatic Best Connection Selection"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --mode=paper|live     Set trading mode (default: paper)"
    echo "  --paper               Use paper trading mode"
    echo "  --live                Use live trading mode"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "This script automatically:"
    echo "1. Tests available connection methods (Gateway and TWS)"
    echo "2. Chooses the best available option"
    echo "3. Launches SPYDER with optimal settings"
    echo ""
    echo "Connection Priority:"
    echo "1. Remote TWS (preferred - better stability)"
    echo "2. IB Gateway (fallback - local connection)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Quick launch with paper trading"
    echo "  $0 --mode=live        # Quick launch with live trading"
    echo "  $0 --paper            # Explicit paper trading mode"
}

# Main execution
main() {
    local trading_mode=$(get_trading_mode "$@")

    log "${CYAN}🚀 Quick Launch - Finding best connection for ${trading_mode} trading...${NC}"
    echo

    # Determine best connection method
    local best_method=$(determine_best_connection "$trading_mode")

    # Show summary
    show_connection_summary "$best_method" "$trading_mode"

    # Launch with selected method
    launch_with_method "$best_method" "$trading_mode"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --mode=*|--paper|--live)
        # Mode arguments - continue to main execution
        main "$@"
        ;;
    "")
        # Default: quick launch
        main "$@"
        ;;
    *)
        log "${RED}❌ Unknown option: $1${NC}"
        log "${BLUE}Use --help for usage information${NC}"
        exit 1
        ;;
esac
