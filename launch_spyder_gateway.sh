#!/bin/bash
# SPYDER - IB Gateway Launcher Wrapper
# Automatically switches to Gateway configuration and launches SPYDER

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

echo -e "${CYAN}🕷️  SPYDER - IB Gateway Launcher${NC}"
echo -e "${CYAN}=================================${NC}"
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

# Function to check if Gateway is running
check_gateway_running() {
    if pgrep -f "ibgateway" > /dev/null; then
        return 0  # Gateway is running
    else
        return 1  # Gateway is not running
    fi
}

# Function to check if Gateway port is accessible
check_gateway_port() {
    local port=${1:-4002}
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/$port" 2>/dev/null; then
        return 0  # Port is accessible
    else
        return 1  # Port is not accessible
    fi
}

# Function to start Gateway if needed
start_gateway_if_needed() {
    log "${BLUE}🔍 Checking IB Gateway status...${NC}"

    if check_gateway_running; then
        log "${GREEN}✅ IB Gateway process is running${NC}"

        if check_gateway_port 4002; then
            log "${GREEN}✅ Gateway paper port (4002) is accessible${NC}"
            return 0
        else
            log "${YELLOW}⚠️  Gateway running but port not accessible - restarting...${NC}"
            pkill -f "ibgateway" 2>/dev/null || true
            sleep 3
        fi
    else
        log "${YELLOW}⚠️  IB Gateway not running${NC}"
    fi

    log "${BLUE}🚀 Starting IB Gateway...${NC}"

    # Prefer credential-enabled wrapper if present
    if [[ -x "$SCRIPT_DIR/launch_gateway_with_credentials.sh" ]]; then
        log "${BLUE}   Using launch_gateway_with_credentials.sh (credential-aware)${NC}"
        bash "$SCRIPT_DIR/launch_gateway_with_credentials.sh" "$trading_mode" &
        GATEWAY_PID=$!
    elif [[ -f "./launch_spyder_with_gateway.sh" ]]; then
        log "${BLUE}   Using launch_spyder_with_gateway.sh${NC}"
        bash ./launch_spyder_with_gateway.sh &
        GATEWAY_PID=$!
    elif [[ -f "./launch_balanced_gateway.sh" ]]; then
        log "${BLUE}   Using launch_balanced_gateway.sh${NC}"
        bash ./launch_balanced_gateway.sh &
        GATEWAY_PID=$!
    else
        log "${RED} No Gateway launcher script found${NC}"
        log "${RED}   Please ensure launch_spyder_with_gateway.sh or launch_gateway_with_credentials.sh exists${NC}"
        exit 1
    fi

    # Wait for Gateway to start
    log "${BLUE}⏳ Waiting for Gateway to initialize...${NC}"
    local wait_count=0
    local max_wait=30

    while [[ $wait_count -lt $max_wait ]]; do
        if check_gateway_port 4002; then
            log "${GREEN}✅ Gateway is ready (port 4002 accessible)${NC}"
            return 0
        fi

        sleep 2
        wait_count=$((wait_count + 1))
        echo -n "."
    done

    echo
    log "${RED}❌ Gateway failed to start within ${max_wait} seconds${NC}"
    return 1
}

# Function to switch to Gateway configuration
switch_to_gateway_config() {
    local trading_mode="${1:-paper}"
    log "${BLUE}🔄 Switching to IB Gateway configuration (${trading_mode} mode)...${NC}"

    # Backup current config
    if [[ -f "config/config.py" ]]; then
        local backup_name="config_backup_$(date +%Y%m%d_%H%M%S).py"
        mkdir -p config/backups
        cp config/config.py "config/backups/$backup_name"
        log "${GREEN}✅ Current config backed up as: $backup_name${NC}"
    fi

    # Check if Gateway config exists
    if [[ -f "config/config_gateway.py" ]]; then
        cp config/config_gateway.py config/config.py
        log "${GREEN}✅ Switched to IB Gateway configuration${NC}"

        # Verify the switch
        if grep -q "local_gateway" config/config.py; then
            log "${GREEN}✅ Configuration verified: local_gateway mode active${NC}"
        else
            log "${YELLOW}⚠️  Configuration switch may not have completed properly${NC}"
        fi
    else
        log "${RED}❌ Gateway configuration file not found: config/config_gateway.py${NC}"
        log "${RED}   Creating default Gateway configuration...${NC}"

        # Create basic Gateway config
        cat > config/config.py << 'EOF'
# SPYDER - IB Gateway Configuration (Auto-generated)
IB_CONFIG = {
    "use_gateway": True,
    "connection_type": "local_gateway",
    "gateway": {
        "paper": {
            "host": "127.0.0.1",
            "port": 4002,
            "clientId": 1,
        },
        "live": {
            "host": "127.0.0.1",
            "port": 4001,
            "clientId": 2,
        },
    },
}

def get_active_config():
    import os
    mode = os.environ.get("TRADING_MODE", "$trading_mode")
    config = IB_CONFIG["gateway"][mode]
    return {
        "host": config["host"],
        "port": config["port"],
        "clientId": config["clientId"],
        "mode": mode,
        "connection_type": "local_gateway"
    }
EOF
        log "${GREEN}✅ Created basic Gateway configuration${NC}"
    fi

    # Set trading mode environment variable for this session
    export TRADING_MODE="$trading_mode"
    log "${GREEN}✅ Trading mode set to: ${trading_mode}${NC}"
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
test_gateway_connection() {
    log "${BLUE}🔍 Testing Gateway connection...${NC}"

    if [[ -f "test_gateway_connection.py" ]]; then
        python3 test_gateway_connection.py
    elif [[ -f "simple_ib_test.py" ]]; then
        python3 simple_ib_test.py
    else
        log "${YELLOW}⚠️  No connection test script available${NC}"

        # Simple port test
        if check_gateway_port 4002; then
            log "${GREEN}✅ Basic port test passed (4002 accessible)${NC}"
        else
            log "${RED}❌ Basic port test failed (4002 not accessible)${NC}"
            return 1
        fi
    fi
}

# Main execution
main() {
    local trading_mode=$(get_trading_mode "$@")
    log "${CYAN}Starting SPYDER with IB Gateway (${trading_mode} mode)...${NC}"

    # Step 1: Switch configuration
    switch_to_gateway_config "$trading_mode"

    # Step 2: Ensure Gateway is running
    if ! start_gateway_if_needed; then
        log "${RED}❌ Failed to start IB Gateway${NC}"
        log "${RED}   Please check Gateway installation and credentials${NC}"
        exit 1
    fi

    # Step 3: Test connection
    log "${BLUE}🔍 Testing connection...${NC}"
    if test_gateway_connection; then
        log "${GREEN}✅ Gateway connection test passed${NC}"
    else
        log "${YELLOW}⚠️  Connection test had issues, but proceeding...${NC}"
    fi

    # Step 4: Launch dashboard
    log "${BLUE}🎯 Ready to launch SPYDER Dashboard${NC}"
    echo
    echo -e "${GREEN}=================================${NC}"
    echo -e "${GREEN}🕷️  SPYDER - IB Gateway Mode${NC}"
    echo -e "${GREEN}   Local Gateway: 127.0.0.1:$([ "$trading_mode" = "live" ] && echo "4001" || echo "4002")${NC}"
    echo -e "${GREEN}   Trading Mode: ${trading_mode^^}${NC}"
    echo -e "${GREEN}   Connection: Local${NC}"
    echo -e "${GREEN}   Status: Ready${NC}"
    echo -e "${GREEN}=================================${NC}"
    echo

    launch_spyder_dashboard
}

# Handle command line arguments
case "${1:-}" in
    --test-only|--test-only=*)
        trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔍 Running connection test only (${trading_mode} mode)...${NC}"
        switch_to_gateway_config "$trading_mode"
        start_gateway_if_needed
        test_gateway_connection
        exit $?
        ;;
    --config-only|--config-only=*)
        trading_mode=$(get_trading_mode "$@")
        log "${BLUE}🔄 Switching configuration only (${trading_mode} mode)...${NC}"
        switch_to_gateway_config "$trading_mode"
        exit 0
        ;;
    --help|-h)
        echo "SPYDER IB Gateway Launcher"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --test-only           Test Gateway connection only"
        echo "  --config-only         Switch to Gateway config only"
        echo "  --mode=paper|live     Set trading mode (default: paper)"
        echo "  --paper               Use paper trading mode"
        echo "  --live                Use live trading mode"
        echo "  --help, -h            Show this help message"
        echo ""
        echo "This script will:"
        echo "1. Switch to IB Gateway configuration"
        echo "2. Start IB Gateway if not running"
        echo "3. Test the connection"
        echo "4. Launch SPYDER Dashboard"
        echo ""
        echo "Examples:"
        echo "  $0                     # Launch with paper trading (default)"
        echo "  $0 --mode=live         # Launch with live trading"
        echo "  $0 --paper --test-only # Test paper trading connection"
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
