#!/bin/bash
# SPYDER - TWS API Launcher Wrapper
# Automatically switches to Remote TWS configuration and launches SPYDER

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

echo -e "${CYAN}🕷️  SPYDER - TWS API Launcher${NC}"
echo -e "${CYAN}==============================${NC}"
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

# Function to extract TWS IP from config
get_tws_ip() {
    if [[ -f "config/config_remote_tws.py" ]]; then
        grep -o '"ip_address":\s*"[^"]*"' config/config_remote_tws.py | sed 's/"ip_address":\s*"\([^"]*\)"/\1/' | head -1
    else
        echo "192.168.1.244"  # Default fallback
    fi
}

# Function to check if TWS is accessible
check_tws_connection() {
    local tws_ip="${1:-192.168.1.244}"
    local tws_port="${2:-7497}"

    log "${BLUE}🔍 Testing connection to TWS at ${tws_ip}:${tws_port}...${NC}"

    if timeout 5 bash -c "</dev/tcp/$tws_ip/$tws_port" 2>/dev/null; then
        return 0  # TWS is accessible
    else
        return 1  # TWS is not accessible
    fi
}

# Function to ping TWS computer
ping_tws_computer() {
    local tws_ip="${1:-192.168.1.244}"

    log "${BLUE}🏓 Pinging TWS computer at ${tws_ip}...${NC}"

    if ping -c 3 -W 3 "$tws_ip" > /dev/null 2>&1; then
        log "${GREEN}✅ TWS computer is reachable${NC}"
        return 0
    else
        log "${RED}❌ TWS computer is not reachable${NC}"
        return 1
    fi
}

# Function to check both TWS ports
check_all_tws_ports() {
    local tws_ip="${1:-192.168.1.244}"
    local paper_port=7497
    local live_port=7496
    local success=0

    log "${BLUE}🔍 Checking TWS API ports on ${tws_ip}...${NC}"

    # Check paper trading port
    if check_tws_connection "$tws_ip" "$paper_port"; then
        log "${GREEN}✅ Paper trading port ($paper_port) accessible${NC}"
        success=1
    else
        log "${RED}❌ Paper trading port ($paper_port) not accessible${NC}"
    fi

    # Check live trading port
    if check_tws_connection "$tws_ip" "$live_port"; then
        log "${GREEN}✅ Live trading port ($live_port) accessible${NC}"
        success=1
    else
        log "${RED}❌ Live trading port ($live_port) not accessible${NC}"
    fi

    return $((success == 0))
}

# Function to switch to TWS configuration
switch_to_tws_config() {
    local trading_mode="${1:-paper}"
    log "${BLUE}🔄 Switching to Remote TWS configuration (${trading_mode} mode)...${NC}"

    # Backup current config
    if [[ -f "config/config.py" ]]; then
        local backup_name="config_backup_$(date +%Y%m%d_%H%M%S).py"
        mkdir -p config/backups
        cp config/config.py "config/backups/$backup_name"
        log "${GREEN}✅ Current config backed up as: $backup_name${NC}"
    fi

    # Check if TWS config exists
    if [[ -f "config/config_remote_tws.py" ]]; then
        cp config/config_remote_tws.py config/config.py
        log "${GREEN}✅ Switched to Remote TWS configuration${NC}"

        # Verify the switch
        if grep -q "remote_tws" config/config.py; then
            log "${GREEN}✅ Configuration verified: remote_tws mode active${NC}"

            # Extract and display TWS IP
            local tws_ip=$(get_tws_ip)
            log "${GREEN}   TWS Computer: ${tws_ip}${NC}"
            log "${GREEN}   Trading Mode: ${trading_mode}${NC}"
        else
            log "${YELLOW}⚠️  Configuration switch may not have completed properly${NC}"
        fi

        # Set trading mode environment variable for this session
        export TRADING_MODE="$trading_mode"
        log "${GREEN}✅ Trading mode set to: ${trading_mode}${NC}"
    else
        log "${RED}❌ TWS configuration file not found: config/config_remote_tws.py${NC}"
        log "${RED}   Run setup_remote_tws.sh first to create TWS configuration${NC}"
        exit 1
    fi
}

# Function to validate TWS setup
validate_tws_setup() {
    local tws_ip=$(get_tws_ip)

    log "${BLUE}🔍 Validating TWS setup...${NC}"
    log "${BLUE}   TWS Computer: ${tws_ip}${NC}"

    # Step 1: Ping test
    if ! ping_tws_computer "$tws_ip"; then
        log "${RED}❌ TWS computer not reachable${NC}"
        log "${RED}   Please check:${NC}"
        log "${RED}   • Network connection${NC}"
        log "${RED}   • Windows computer is on and connected${NC}"
        log "${RED}   • IP address is correct: ${tws_ip}${NC}"
        return 1
    fi

    # Step 2: Port accessibility test
    if ! check_all_tws_ports "$tws_ip"; then
        log "${RED}❌ TWS API ports not accessible${NC}"
        log "${RED}   Please check:${NC}"
        log "${RED}   • TWS is running on Windows computer${NC}"
        log "${RED}   • TWS API is enabled (File → Global Configuration → API → Settings)${NC}"
        log "${RED}   • Ubuntu IP ($(hostname -I | awk '{print $1}')) is in TWS trusted IPs${NC}"
        log "${RED}   • Windows Firewall allows ports 7496/7497${NC}"
        return 1
    fi

    log "${GREEN}✅ TWS setup validation passed${NC}"
    return 0
}

# Function to launch SPYDER dashboard
launch_spyder_dashboard() {
    log "${BLUE}🚀 Launching SPYDER Dashboard...${NC}"

    # Check if virtual environment exists
    if [[ -d ".venv" ]]; then
        log "${BLUE}   Activating virtual environment...${NC}"
        source .venv/bin/activate
    elif [[ -d ".venv_consolidated" ]]; then
        log "${BLUE}   Activating consolidated virtual environment...${NC}"
        source .venv_consolidated/bin/activate
    fi

    # Launch dashboard
    if [[ -f "launch_dashboard_production.py" ]]; then
        log "${GREEN}✅ Starting SPYDER Production Dashboard${NC}"
        python3 launch_dashboard_production.py
    else
        log "${RED}❌ Dashboard launcher not found: launch_dashboard_production.py${NC}"
        exit 1
    fi
}

# Function to perform connection test
test_tws_connection() {
    log "${BLUE}🔍 Testing TWS connection...${NC}"

    if [[ -f "test_remote_tws_connection.py" ]]; then
        local tws_ip=$(get_tws_ip)
        python3 test_remote_tws_connection.py --windows-ip "$tws_ip" --full-test
    else
        log "${YELLOW}⚠️  No TWS connection test script available${NC}"

        # Simple validation
        if validate_tws_setup; then
            log "${GREEN}✅ Basic TWS validation passed${NC}"
        else
            log "${RED}❌ Basic TWS validation failed${NC}"
            return 1
        fi
    fi
}

# Function to show TWS troubleshooting help
show_tws_troubleshooting() {
    local tws_ip=$(get_tws_ip)

    echo
    log "${YELLOW}🔧 TWS Connection Troubleshooting:${NC}"
    echo
    echo -e "${BLUE}On Windows Computer (${tws_ip}):${NC}"
    echo "1. Ensure TWS is running and logged in"
    echo "2. Go to File → Global Configuration → API → Settings"
    echo "3. Check 'Enable ActiveX and Socket Clients'"
    echo "4. Add Ubuntu IP to 'Trusted IPs': $(hostname -I | awk '{print $1}')"
    echo "5. Ensure Windows Firewall allows TWS"
    echo
    echo -e "${BLUE}Network Check:${NC}"
    echo "• Ping test: ping $tws_ip"
    echo "• Port test: telnet $tws_ip 7497"
    echo
    echo -e "${BLUE}For detailed setup:${NC}"
    echo "• See: REMOTE_TWS_MIGRATION_GUIDE.md"
    echo "• Run: ./setup_remote_tws.sh --interactive"
    echo
}

# Main execution
main() {
    local tws_ip
    local trading_mode=$(get_trading_mode "$@")

    log "${CYAN}Starting SPYDER with Remote TWS API (${trading_mode} mode)...${NC}"

    # Step 1: Switch configuration
    switch_to_tws_config "$trading_mode"
    tws_ip=$(get_tws_ip)

    # Step 2: Validate TWS setup
    log "${BLUE}🔍 Validating TWS connection...${NC}"
    if ! validate_tws_setup; then
        log "${RED}❌ TWS validation failed${NC}"
        show_tws_troubleshooting
        exit 1
    fi

    # Step 3: Test connection
    log "${BLUE}🔍 Testing connection...${NC}"
    if test_tws_connection; then
        log "${GREEN}✅ TWS connection test passed${NC}"
    else
        log "${YELLOW}⚠️  Connection test had issues, but TWS is reachable...${NC}"
        log "${YELLOW}   Proceeding with launch (connection issues may resolve during startup)${NC}"
    fi

    # Step 4: Launch dashboard
    log "${BLUE}🎯 Ready to launch SPYDER Dashboard${NC}"
    echo
    echo -e "${GREEN}=================================${NC}"
    echo -e "${GREEN}🕷️  SPYDER - Remote TWS Mode${NC}"
    echo -e "${GREEN}   TWS Computer: ${tws_ip}${NC}"
    local port=$([ "$trading_mode" = "live" ] && echo "7496" || echo "7497")
    echo -e "${GREEN}   Active Port: ${port}${NC}"
    echo -e "${GREEN}   Trading Mode: ${trading_mode^^}${NC}"
    echo -e "${GREEN}   Connection: Remote${NC}"
    echo -e "${GREEN}   Status: Ready${NC}"
    echo -e "${GREEN}=================================${NC}"
    echo

    launch_spyder_dashboard
}

# Handle command line arguments
case "${1:-}" in
    --test-only|--test-only=*)
        local trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔍 Running connection test only (${trading_mode} mode)...${NC}"
        switch_to_tws_config "$trading_mode"
        validate_tws_setup
        test_tws_connection
        exit $?
        ;;
    --config-only|--config-only=*)
        local trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔄 Switching configuration only (${trading_mode} mode)...${NC}"
        switch_to_tws_config "$trading_mode"
        exit 0
        ;;
    --validate-only|--validate-only=*)
        local trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔍 Running validation only (${trading_mode} mode)...${NC}"
        switch_to_tws_config "$trading_mode"
        validate_tws_setup
        exit $?
        ;;
    --troubleshoot)
        local trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔧 Showing troubleshooting information...${NC}"
        switch_to_tws_config "$trading_mode"
        show_tws_troubleshooting
        exit 0
        ;;
    --help|-h)
        echo "SPYDER Remote TWS API Launcher"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --test-only           Test TWS connection only"
        echo "  --config-only         Switch to TWS config only"
        echo "  --validate-only       Validate TWS setup only"
        echo "  --troubleshoot        Show troubleshooting help"
        echo "  --mode=paper|live     Set trading mode (default: paper)"
        echo "  --paper               Use paper trading mode"
        echo "  --live                Use live trading mode"
        echo "  --help, -h            Show this help message"
        echo ""
        echo "This script will:"
        echo "1. Switch to Remote TWS configuration"
        echo "2. Validate TWS computer accessibility"
        echo "3. Test TWS API ports"
        echo "4. Launch SPYDER Dashboard"
        echo ""
        echo "Examples:"
        echo "  $0                     # Launch with paper trading (default)"
        echo "  $0 --mode=live         # Launch with live trading"
        echo "  $0 --live --test-only  # Test live trading connection"
        echo ""
        echo "Requirements:"
        echo "• Windows computer running TWS"
        echo "• TWS API enabled and configured"
        echo "• Network connectivity between computers"
        exit 0
        ;;
    --mode=*|--paper|--live)
        # Mode arguments - continue to main execution
        main "$@"
        ;;
    "")
        # Default: full launch
        main "$@"
        ;;
    *)
        log "${RED}❌ Unknown option: $1${NC}"
        log "${BLUE}Use --help for usage information${NC}"
        exit 1
        ;;
esac
