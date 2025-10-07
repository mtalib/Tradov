#!/bin/bash
# SPYDER - Comprehensive Connection Testing Script
# Tests both IB Gateway and TWS API connections with detailed diagnostics

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Log file
LOG_FILE="logs/connection_test_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo -e "${CYAN}🕷️  SPYDER - Connection Testing Suite${NC}"
echo -e "${CYAN}====================================${NC}"
echo -e "${BLUE}Log file: ${LOG_FILE}${NC}"
echo

# Function to log with timestamp
log() {
    local message="$1"
    local timestamp="[$(date '+%Y-%m-%d %H:%M:%S')]"
    echo -e "${timestamp} $message" | tee -a "$LOG_FILE"
}

# Function to log without timestamp (for formatting)
log_plain() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

# Test results tracking
GATEWAY_AVAILABLE=false
TWS_AVAILABLE=false
GATEWAY_PORT_4001=false
GATEWAY_PORT_4002=false
TWS_PORT_7496=false
TWS_PORT_7497=false
GATEWAY_PROCESS_RUNNING=false
TWS_COMPUTER_REACHABLE=false

# Function to test network connectivity
test_network_basic() {
    log "${BLUE}🌐 Testing basic network connectivity...${NC}"

    # Test internet connectivity
    if ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
        log "${GREEN}✅ Internet connectivity: OK${NC}"
    else
        log "${RED}❌ Internet connectivity: FAILED${NC}"
    fi

    # Test local loopback
    if ping -c 1 -W 1 127.0.0.1 > /dev/null 2>&1; then
        log "${GREEN}✅ Local loopback: OK${NC}"
    else
        log "${RED}❌ Local loopback: FAILED${NC}"
    fi

    # Get local IP
    local_ip=$(hostname -I | awk '{print $1}')
    log "${BLUE}   Local IP: ${local_ip}${NC}"

    echo
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

# Function to test IB Gateway
test_gateway_connection() {
    log "${BLUE}🏪 Testing IB Gateway Connection...${NC}"
    log_plain "${BLUE}================================${NC}"

    # Check if Gateway process is running
    if pgrep -f "ibgateway" > /dev/null; then
        GATEWAY_PROCESS_RUNNING=true
        log "${GREEN}✅ IB Gateway process: RUNNING${NC}"

        # Get Gateway process info
        local gateway_pid=$(pgrep -f "ibgateway" | head -1)
        local gateway_cmd=$(ps -p $gateway_pid -o cmd= 2>/dev/null || echo "Unknown")
        log "${BLUE}   PID: ${gateway_pid}${NC}"
        log "${BLUE}   Command: ${gateway_cmd:0:80}...${NC}"
    else
        GATEWAY_PROCESS_RUNNING=false
        log "${RED}❌ IB Gateway process: NOT RUNNING${NC}"
    fi

    # Test port 4001 (Live)
    log "${BLUE}🔍 Testing Gateway Live port (4001)...${NC}"
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/4001" 2>/dev/null; then
        GATEWAY_PORT_4001=true
        log "${GREEN}✅ Port 4001 (Live): ACCESSIBLE${NC}"
    else
        GATEWAY_PORT_4001=false
        log "${RED}❌ Port 4001 (Live): NOT ACCESSIBLE${NC}"
    fi

    # Test port 4002 (Paper)
    log "${BLUE}🔍 Testing Gateway Paper port (4002)...${NC}"
    if timeout 3 bash -c "</dev/tcp/127.0.0.1/4002" 2>/dev/null; then
        GATEWAY_PORT_4002=true
        log "${GREEN}✅ Port 4002 (Paper): ACCESSIBLE${NC}"
    else
        GATEWAY_PORT_4002=false
        log "${RED}❌ Port 4002 (Paper): NOT ACCESSIBLE${NC}"
    fi

    # Overall Gateway status
    if [[ "$GATEWAY_PORT_4001" == true ]] || [[ "$GATEWAY_PORT_4002" == true ]]; then
        GATEWAY_AVAILABLE=true
        log "${GREEN}✅ IB Gateway: AVAILABLE${NC}"
    else
        GATEWAY_AVAILABLE=false
        log "${RED}❌ IB Gateway: NOT AVAILABLE${NC}"

        if [[ "$GATEWAY_PROCESS_RUNNING" == false ]]; then
            log "${YELLOW}💡 Suggestion: Start Gateway with './launch_spyder_with_gateway.sh'${NC}"
        else
            log "${YELLOW}💡 Suggestion: Gateway running but ports not accessible - restart Gateway${NC}"
        fi
    fi

    echo
}

# Function to test TWS connection
test_tws_connection() {
    local tws_ip=$(get_tws_ip)

    log "${BLUE}🌐 Testing Remote TWS Connection...${NC}"
    log_plain "${BLUE}==================================${NC}"
    log "${BLUE}   TWS Computer IP: ${tws_ip}${NC}"

    # Test if TWS computer is reachable
    log "${BLUE}🏓 Pinging TWS computer...${NC}"
    if ping -c 3 -W 3 "$tws_ip" > /dev/null 2>&1; then
        TWS_COMPUTER_REACHABLE=true
        log "${GREEN}✅ TWS Computer: REACHABLE${NC}"

        # Get ping statistics
        local ping_stats=$(ping -c 3 -W 3 "$tws_ip" 2>/dev/null | tail -1)
        log "${BLUE}   ${ping_stats}${NC}"
    else
        TWS_COMPUTER_REACHABLE=false
        log "${RED}❌ TWS Computer: NOT REACHABLE${NC}"
        log "${YELLOW}💡 Check: Network connection, Windows computer power, IP address${NC}"
    fi

    # Test port 7496 (Live) - only if computer is reachable
    if [[ "$TWS_COMPUTER_REACHABLE" == true ]]; then
        log "${BLUE}🔍 Testing TWS Live port (7496)...${NC}"
        if timeout 5 bash -c "</dev/tcp/$tws_ip/7496" 2>/dev/null; then
            TWS_PORT_7496=true
            log "${GREEN}✅ Port 7496 (Live): ACCESSIBLE${NC}"
        else
            TWS_PORT_7496=false
            log "${RED}❌ Port 7496 (Live): NOT ACCESSIBLE${NC}"
        fi

        # Test port 7497 (Paper)
        log "${BLUE}🔍 Testing TWS Paper port (7497)...${NC}"
        if timeout 5 bash -c "</dev/tcp/$tws_ip/7497" 2>/dev/null; then
            TWS_PORT_7497=true
            log "${GREEN}✅ Port 7497 (Paper): ACCESSIBLE${NC}"
        else
            TWS_PORT_7497=false
            log "${RED}❌ Port 7497 (Paper): NOT ACCESSIBLE${NC}"
        fi
    else
        TWS_PORT_7496=false
        TWS_PORT_7497=false
        log "${YELLOW}⚠️  Skipping port tests (computer not reachable)${NC}"
    fi

    # Overall TWS status
    if [[ "$TWS_PORT_7496" == true ]] || [[ "$TWS_PORT_7497" == true ]]; then
        TWS_AVAILABLE=true
        log "${GREEN}✅ Remote TWS: AVAILABLE${NC}"
    else
        TWS_AVAILABLE=false
        log "${RED}❌ Remote TWS: NOT AVAILABLE${NC}"

        if [[ "$TWS_COMPUTER_REACHABLE" == false ]]; then
            log "${YELLOW}💡 Suggestion: Check network connection and Windows computer${NC}"
        else
            log "${YELLOW}💡 Suggestion: Start TWS on Windows, enable API, add Ubuntu IP to trusted IPs${NC}"
        fi
    fi

    echo
}

# Function to test current configuration
test_current_config() {
    log "${BLUE}⚙️  Testing Current Configuration...${NC}"
    log_plain "${BLUE}=================================${NC}"

    if [[ -f "config/config.py" ]]; then
        local config_content=$(cat config/config.py)

        if echo "$config_content" | grep -q "remote_tws"; then
            local tws_ip=$(get_tws_ip)
            log "${CYAN}📋 Current: Remote TWS Configuration${NC}"
            log "${BLUE}   TWS Computer: ${tws_ip}${NC}"
            log "${BLUE}   Paper Port: 7497, Live Port: 7496${NC}"

            if [[ "$TWS_AVAILABLE" == true ]]; then
                log "${GREEN}✅ Current configuration: WORKING${NC}"
            else
                log "${RED}❌ Current configuration: NOT WORKING${NC}"
            fi

        elif echo "$config_content" | grep -q "local_gateway\|127.0.0.1.*4002"; then
            log "${CYAN}📋 Current: IB Gateway Configuration${NC}"
            log "${BLUE}   Gateway Host: 127.0.0.1${NC}"
            log "${BLUE}   Paper Port: 4002, Live Port: 4001${NC}"

            if [[ "$GATEWAY_AVAILABLE" == true ]]; then
                log "${GREEN}✅ Current configuration: WORKING${NC}"
            else
                log "${RED}❌ Current configuration: NOT WORKING${NC}"
            fi
        else
            log "${YELLOW}⚠️  Current: Unknown/Mixed Configuration${NC}"
        fi
    else
        log "${RED}❌ No configuration file found: config/config.py${NC}"
    fi

    echo
}

# Function to run API connection tests
test_api_connections() {
    log "${BLUE}🔌 Testing API Connections...${NC}"
    log_plain "${BLUE}===========================${NC}"

    # Test Gateway API if available
    if [[ "$GATEWAY_AVAILABLE" == true ]]; then
        log "${BLUE}🏪 Testing Gateway API connection...${NC}"

        if [[ -f "simple_ib_test.py" ]]; then
            log "${BLUE}   Running simple_ib_test.py...${NC}"
            if timeout 30 python3 simple_ib_test.py 2>&1 | tee -a "$LOG_FILE" | grep -q "Connected successfully"; then
                log "${GREEN}✅ Gateway API test: PASSED${NC}"
            else
                log "${RED}❌ Gateway API test: FAILED${NC}"
            fi
        else
            log "${YELLOW}⚠️  No API test script available (simple_ib_test.py)${NC}"
        fi
    fi

    # Test TWS API if available
    if [[ "$TWS_AVAILABLE" == true ]]; then
        log "${BLUE}🌐 Testing TWS API connection...${NC}"

        if [[ -f "test_remote_tws_connection.py" ]]; then
            local tws_ip=$(get_tws_ip)
            log "${BLUE}   Running test_remote_tws_connection.py...${NC}"
            if timeout 30 python3 test_remote_tws_connection.py --windows-ip "$tws_ip" --quick-test 2>&1 | tee -a "$LOG_FILE" | grep -q "success"; then
                log "${GREEN}✅ TWS API test: PASSED${NC}"
            else
                log "${RED}❌ TWS API test: FAILED${NC}"
            fi
        else
            log "${YELLOW}⚠️  No TWS test script available (test_remote_tws_connection.py)${NC}"
        fi
    fi

    echo
}

# Function to show recommendations
show_recommendations() {
    log "${PURPLE}🎯 Recommendations${NC}"
    log_plain "${PURPLE}===============${NC}"

    if [[ "$GATEWAY_AVAILABLE" == true ]] && [[ "$TWS_AVAILABLE" == true ]]; then
        log "${GREEN}🎉 Both connection methods are available!${NC}"
        log "${BLUE}   You can choose either:${NC}"
        log "${BLUE}   • IB Gateway: Stable, local, no network dependency${NC}"
        log "${BLUE}   • Remote TWS: Professional, no handshake issues${NC}"

    elif [[ "$GATEWAY_AVAILABLE" == true ]]; then
        log "${GREEN}✅ IB Gateway is available${NC}"
        log "${BLUE}   • Use: ./launch_spyder_gateway.sh${NC}"
        log "${BLUE}   • Pros: Local, no network issues${NC}"
        log "${BLUE}   • Cons: Known handshake timeouts${NC}"

        if [[ "$TWS_COMPUTER_REACHABLE" == false ]]; then
            log "${YELLOW}💡 To enable TWS: Check Windows computer connection${NC}"
        else
            log "${YELLOW}💡 To enable TWS: Start TWS on Windows, enable API${NC}"
        fi

    elif [[ "$TWS_AVAILABLE" == true ]]; then
        log "${GREEN}✅ Remote TWS is available${NC}"
        log "${BLUE}   • Use: ./launch_spyder_tws.sh${NC}"
        log "${BLUE}   • Pros: No handshake issues, professional setup${NC}"
        log "${BLUE}   • Cons: Network dependency${NC}"

        if [[ "$GATEWAY_PROCESS_RUNNING" == false ]]; then
            log "${YELLOW}💡 To enable Gateway: Run ./launch_spyder_with_gateway.sh${NC}"
        else
            log "${YELLOW}💡 To enable Gateway: Restart Gateway (ports not accessible)${NC}"
        fi

    else
        log "${RED}❌ Neither connection method is currently available${NC}"
        log "${YELLOW}🔧 Troubleshooting needed:${NC}"

        if [[ "$GATEWAY_PROCESS_RUNNING" == false ]]; then
            log "${YELLOW}   Gateway: Start with ./launch_spyder_with_gateway.sh${NC}"
        else
            log "${YELLOW}   Gateway: Restart (process running but ports not accessible)${NC}"
        fi

        if [[ "$TWS_COMPUTER_REACHABLE" == false ]]; then
            log "${YELLOW}   TWS: Check Windows computer network connection${NC}"
        else
            log "${YELLOW}   TWS: Start TWS, enable API, configure trusted IPs${NC}"
        fi
    fi

    echo
}

# Function to generate JSON report
generate_json_report() {
    local json_file="logs/connection_test_$(date +%Y%m%d_%H%M%S).json"

    cat > "$json_file" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "test_duration": "$(date +%s)",
    "local_ip": "$(hostname -I | awk '{print $1}')",
    "tws_ip": "$(get_tws_ip)",
    "results": {
        "gateway": {
            "available": $GATEWAY_AVAILABLE,
            "process_running": $GATEWAY_PROCESS_RUNNING,
            "port_4001_accessible": $GATEWAY_PORT_4001,
            "port_4002_accessible": $GATEWAY_PORT_4002
        },
        "remote_tws": {
            "available": $TWS_AVAILABLE,
            "computer_reachable": $TWS_COMPUTER_REACHABLE,
            "port_7496_accessible": $TWS_PORT_7496,
            "port_7497_accessible": $TWS_PORT_7497
        },
        "summary": {
            "methods_available": $(( (GATEWAY_AVAILABLE ? 1 : 0) + (TWS_AVAILABLE ? 1 : 0) )),
            "recommended_method": "$(if [[ "$TWS_AVAILABLE" == true ]]; then echo "remote_tws"; elif [[ "$GATEWAY_AVAILABLE" == true ]]; then echo "gateway"; else echo "none"; fi)"
        }
    }
}
EOF

    log "${BLUE}📄 JSON report saved: ${json_file}${NC}"
}

# Function to show summary
show_summary() {
    log_plain "${CYAN}📊 CONNECTION TEST SUMMARY${NC}"
    log_plain "${CYAN}==========================${NC}"

    # Gateway Summary
    if [[ "$GATEWAY_AVAILABLE" == true ]]; then
        log_plain "${GREEN}🏪 IB Gateway: ✅ AVAILABLE${NC}"
    else
        log_plain "${RED}🏪 IB Gateway: ❌ NOT AVAILABLE${NC}"
    fi

    # TWS Summary
    if [[ "$TWS_AVAILABLE" == true ]]; then
        log_plain "${GREEN}🌐 Remote TWS: ✅ AVAILABLE${NC}"
    else
        log_plain "${RED}🌐 Remote TWS: ❌ NOT AVAILABLE${NC}"
    fi

    # Overall Status
    local available_methods=$(( (GATEWAY_AVAILABLE ? 1 : 0) + (TWS_AVAILABLE ? 1 : 0) ))

    case $available_methods in
        2)
            log_plain "${GREEN}🎉 Status: Both methods available - Maximum flexibility!${NC}"
            ;;
        1)
            log_plain "${YELLOW}⚠️  Status: One method available - Working but limited options${NC}"
            ;;
        0)
            log_plain "${RED}❌ Status: No methods available - Troubleshooting required${NC}"
            ;;
    esac

    echo
    log_plain "${BLUE}🚀 Launch Commands:${NC}"

    if [[ "$GATEWAY_AVAILABLE" == true ]]; then
        log_plain "${GREEN}   IB Gateway: ./launch_spyder_gateway.sh${NC}"
    fi

    if [[ "$TWS_AVAILABLE" == true ]]; then
        log_plain "${GREEN}   Remote TWS: ./launch_spyder_tws.sh${NC}"
    fi

    log_plain "${BLUE}   Connection Selector: ./launch_connection_selector.py${NC}"

    echo
}

# Main execution
main() {
    log "${CYAN}🚀 Starting comprehensive connection test...${NC}"
    log "${BLUE}Test started at: $(date)${NC}"
    echo

    # Run all tests
    test_network_basic
    test_gateway_connection
    test_tws_connection
    test_current_config

    # Optional API tests (if --full flag is provided)
    if [[ "$1" == "--full" ]]; then
        test_api_connections
    fi

    # Generate recommendations
    show_recommendations

    # Generate reports
    generate_json_report

    # Show summary
    show_summary

    log "${CYAN}✨ Connection test completed at: $(date)${NC}"
    log "${BLUE}Full log available at: ${LOG_FILE}${NC}"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "SPYDER Connection Testing Suite"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --full         Run full tests including API connection tests"
        echo "  --help, -h     Show this help message"
        echo ""
        echo "This script tests:"
        echo "• Network connectivity"
        echo "• IB Gateway availability and ports"
        echo "• Remote TWS accessibility and ports"
        echo "• Current configuration status"
        echo "• API connections (with --full flag)"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
