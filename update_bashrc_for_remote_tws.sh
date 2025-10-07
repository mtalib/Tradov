#!/bin/bash
# ==============================================================================
# Update .bashrc for Remote TWS Configuration
# ==============================================================================
# This script updates the Interactive Brokers configuration in .bashrc to
# support remote TWS running on a Windows computer instead of local IB Gateway.
# ==============================================================================

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASHRC_FILE="$HOME/.bashrc"
BACKUP_FILE="$HOME/.bashrc.backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗"
echo -e "║                    UPDATE .bashrc FOR REMOTE TWS                            ║"
echo -e "║              Spyder Trading System Configuration Update                      ║"
echo -e "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ==============================================================================
# FUNCTIONS
# ==============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to get Windows IP from configuration
get_windows_ip() {
    local config_file="$HOME/Projects/Spyder/config/config_remote_tws.py"

    if [ -f "$config_file" ]; then
        # Extract IP address from config file
        local windows_ip=$(grep 'ip_address.*:' "$config_file" | sed 's/.*: *"\([^"]*\)".*/\1/')
        if [ -n "$windows_ip" ]; then
            echo "$windows_ip"
            return 0
        fi
    fi

    # Fallback - ask user
    echo ""
    read -p "Enter Windows computer IP address: " windows_ip
    echo "$windows_ip"
}

# Function to backup .bashrc
backup_bashrc() {
    log_info "Creating backup of .bashrc..."

    if [ -f "$BASHRC_FILE" ]; then
        cp "$BASHRC_FILE" "$BACKUP_FILE"
        log_success "Backup created: $BACKUP_FILE"
        return 0
    else
        log_error ".bashrc file not found!"
        return 1
    fi
}

# Function to update IB configuration in .bashrc
update_ib_configuration() {
    local windows_ip="$1"

    log_info "Updating Interactive Brokers configuration..."

    # Create temporary file with updated configuration
    local temp_file=$(mktemp)

    # Flag to track if we're in the IB configuration section
    local in_ib_section=false
    local ib_section_updated=false

    while IFS= read -r line; do
        # Check if we're entering the IB configuration section
        if [[ "$line" =~ "INTERACTIVE BROKERS CONFIGURATION" ]]; then
            in_ib_section=true
            echo "$line" >> "$temp_file"
            continue
        fi

        # Check if we're leaving the IB configuration section
        if [ "$in_ib_section" = true ] && [[ "$line" =~ "SPYDER TRADING SYSTEM CONFIGURATION" ]]; then
            # Insert our updated IB configuration before the next section
            if [ "$ib_section_updated" = false ]; then
                cat << EOF >> "$temp_file"
# ===============================================================================
# INTERACTIVE BROKERS CONFIGURATION - REMOTE TWS SETUP
# ===============================================================================
# IB Gateway Version Configuration
export TWS_MAJOR_VRSN="1039"
export IB_GATEWAY_VERSION="10.39"

# Remote TWS Configuration (Updated for Windows Computer)
export IB_REMOTE_TWS_HOST="$windows_ip"
export IB_TWS_PORT_PAPER="7497"        # TWS Paper Trading Port
export IB_TWS_PORT_LIVE="7496"         # TWS Live Trading Port

# Legacy Gateway Ports (for backward compatibility)
export IB_GATEWAY_HOST="$windows_ip"   # Updated to remote TWS
export IB_GATEWAY_PORT_PAPER="7497"    # Updated to TWS paper port
export IB_GATEWAY_PORT_LIVE="7496"     # Updated to TWS live port

# Default to paper trading (safety first!)
export IB_DEFAULT_PORT="\$IB_TWS_PORT_PAPER"
export IB_TRADING_MODE="paper"

# IB Client ID Allocation (as per Spyder architecture)
export IB_ORDER_EXECUTION_CLIENT="1"    # For order execution
export IB_MASTER_CLIENT="2"             # For account/positions monitoring
export IB_DASHBOARD_CLIENT="3"          # For market data dashboard
export IB_HISTORICAL_CLIENT="4"         # For historical data
export IB_SCANNER_CLIENT="5"            # For market scanners
export IB_RISK_CLIENT="6"               # For risk management
export IB_BACKUP_CLIENT="7"             # Backup connection
export IB_TEST_CLIENT="8"               # For testing
export IB_MONITOR_CLIENT="9"            # For system monitoring
export IB_ADMIN_CLIENT="10"             # Administrative tasks
export IB_NEWSFEED_CLIENT="11"          # News feed heartbeat

# Remote TWS Connection Settings
export IB_CONNECTION_TYPE="remote_tws"
export IB_WINDOWS_COMPUTER="$windows_ip"
export IB_CONNECTION_TIMEOUT="30"
export IB_RECONNECTION_ATTEMPTS="5"

# IB Gateway Installation Paths (Local - for reference only)
export IB_GATEWAY_DIR="\$HOME/Jts/ibgateway/1039"
export IB_TWS_DIR="\$HOME/Jts/tws"
export IBC_PATH="\$HOME/IBC"
export IBC_INI="\$HOME/IBC/config.ini"

# IB Data Subscription Settings
export IB_MARKET_DATA_TYPE="3"  # 3=delayed, 1=live (requires subscription)

# IB Server Selection (Note: This is handled by remote TWS)
export IB_PREFERRED_SERVER="zdc1.ibllc.com"  # Zurich server
export IB_FORCE_ZURICH="true"

EOF
                ib_section_updated=true
            fi
            in_ib_section=false
            echo "$line" >> "$temp_file"
            continue
        fi

        # Skip old IB configuration lines if we're in the section
        if [ "$in_ib_section" = true ]; then
            # Skip lines that start with export IB_ or export TWS_
            if [[ "$line" =~ ^export\ (IB_|TWS_) ]] || [[ "$line" =~ ^export\ IBC_ ]]; then
                continue
            fi
            # Skip Docker configuration (not needed for remote TWS)
            if [[ "$line" =~ IB_DOCKER ]]; then
                continue
            fi
        fi

        echo "$line" >> "$temp_file"

    done < "$BASHRC_FILE"

    # Replace original file with updated content
    mv "$temp_file" "$BASHRC_FILE"

    log_success "IB configuration updated for remote TWS at $windows_ip"
}

# Function to update IB aliases and functions
update_ib_aliases() {
    local windows_ip="$1"

    log_info "Updating IB aliases and functions..."

    # Create temporary file
    local temp_file=$(mktemp)

    # Flag to track sections
    local in_docker_aliases=false
    local in_ib_check_function=false

    while IFS= read -r line; do
        # Skip Docker aliases section (not needed for remote TWS)
        if [[ "$line" =~ "IB GATEWAY DOCKER ALIASES" ]]; then
            in_docker_aliases=true
            # Add comment explaining why Docker aliases are removed
            cat << EOF >> "$temp_file"
# ===============================================================================
# IB GATEWAY DOCKER ALIASES - DISABLED FOR REMOTE TWS
# ===============================================================================
# Docker aliases disabled because we're using remote TWS on Windows computer.
# The TWS application runs on $windows_ip, not in a local Docker container.

EOF
            continue
        fi

        # Check if we're leaving Docker aliases section
        if [ "$in_docker_aliases" = true ] && [[ "$line" =~ "IB Connection testing aliases" ]]; then
            in_docker_aliases=false
            # Add updated connection testing aliases
            cat << EOF >> "$temp_file"
# ===============================================================================
# IB REMOTE TWS CONNECTION TESTING ALIASES
# ===============================================================================
# Updated aliases for testing remote TWS connection
alias ib-test='python \$SPYDER_HOME/simple_ib_test.py --ip $windows_ip --port 7497'
alias ib-test-comprehensive='python \$SPYDER_HOME/simple_ib_test.py --ip $windows_ip --port 7497 --comprehensive'
alias ib-diagnose='python \$SPYDER_HOME/diagnose_tws_handshake.py --windows-ip $windows_ip --port 7497'
alias ib-ports='python \$SPYDER_HOME/debug_tws_connection.py --ip $windows_ip --port 7497'
alias ib-status='python \$SPYDER_HOME/SpyderQ_Scripts/SpyderQ22_CheckIBStatus.py'

EOF
            continue
        fi

        # Skip lines in Docker aliases section
        if [ "$in_docker_aliases" = true ]; then
            continue
        fi

        # Update ib-check function
        if [[ "$line" =~ "Function to check IB Gateway connectivity" ]] || [[ "$line" =~ "ib-check()" ]]; then
            in_ib_check_function=true
            # Add updated ib-check function
            cat << EOF >> "$temp_file"
# Function to check Remote TWS connectivity
ib-check() {
    echo "🔍 Checking Remote TWS connectivity..."
    echo "----------------------------------------"
    echo "🌐 Remote TWS: $windows_ip:7497"
    echo ""

    # Check network connectivity
    if ping -c 1 -W 3 $windows_ip &>/dev/null; then
        echo "✅ Network connectivity to $windows_ip: OK"
    else
        echo "❌ Network connectivity to $windows_ip: FAILED"
        echo "   Check if Windows computer is reachable"
        return 1
    fi

    # Check TWS port
    if nc -zv $windows_ip 7497 2>/dev/null; then
        echo "✅ TWS port 7497 is accessible"
    else
        echo "❌ TWS port 7497 is not accessible"
        echo "   Check if TWS is running on Windows computer"
    fi

    # Check live port too
    if nc -zv $windows_ip 7496 2>/dev/null; then
        echo "✅ TWS port 7496 is accessible"
    else
        echo "❌ TWS port 7496 is not accessible"
    fi

    echo ""
    echo "🔧 Environment:"
    echo "   IB_REMOTE_TWS_HOST=\$IB_REMOTE_TWS_HOST"
    echo "   IB_TWS_PORT_PAPER=\$IB_TWS_PORT_PAPER"
    echo "   IB_TRADING_MODE=\$IB_TRADING_MODE"
    echo ""
    echo "🧪 Quick Tests:"
    echo "   Run: ib-test"
    echo "   Run: ib-diagnose"
    echo "   Run: ib-status"
}

EOF
            continue
        fi

        # Skip lines in old ib-check function
        if [ "$in_ib_check_function" = true ]; then
            if [[ "$line" =~ ^} ]]; then
                in_ib_check_function=false
            fi
            continue
        fi

        # Keep other lines
        echo "$line" >> "$temp_file"

    done < "$BASHRC_FILE"

    # Replace original file
    mv "$temp_file" "$BASHRC_FILE"

    log_success "IB aliases and functions updated"
}

# Function to add remote TWS information to login message
update_login_message() {
    local windows_ip="$1"

    log_info "Updating login message..."

    # Update the commented login message
    sed -i "s|# echo \"   IB Gateway: \$IB_GATEWAY_HOST:\$IB_GATEWAY_PORT_PAPER (Paper)\"|# echo \"   Remote TWS: $windows_ip:7497 (Paper)\"|g" "$BASHRC_FILE"
    sed -i "s|# echo \"   Run 'ib-check' to verify IB Gateway status\"|# echo \"   Run 'ib-check' to verify Remote TWS status\"|g" "$BASHRC_FILE"

    log_success "Login message updated"
}

# Function to validate the updated configuration
validate_configuration() {
    log_info "Validating updated configuration..."

    # Check if the configuration looks correct
    if grep -q "IB_REMOTE_TWS_HOST" "$BASHRC_FILE" && grep -q "remote_tws" "$BASHRC_FILE"; then
        log_success "Configuration validation passed"
        return 0
    else
        log_error "Configuration validation failed!"
        return 1
    fi
}

# Function to show summary
show_summary() {
    local windows_ip="$1"

    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════════════╗"
    echo -e "║                            UPDATE COMPLETE                                  ║"
    echo -e "╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}✅ .bashrc has been updated for Remote TWS configuration${NC}"
    echo ""
    echo -e "${YELLOW}Key Changes Made:${NC}"
    echo "• IB_GATEWAY_HOST updated to: $windows_ip"
    echo "• IB_TWS_PORT_PAPER set to: 7497"
    echo "• IB_TWS_PORT_LIVE set to: 7496"
    echo "• Added IB_REMOTE_TWS_HOST: $windows_ip"
    echo "• Updated ib-check() function for remote testing"
    echo "• Updated connection testing aliases"
    echo "• Disabled Docker aliases (not needed for remote TWS)"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Reload your shell: ${BLUE}source ~/.bashrc${NC}"
    echo "2. Test connection: ${BLUE}ib-check${NC}"
    echo "3. Run diagnostics: ${BLUE}ib-diagnose${NC}"
    echo "4. Test IB connection: ${BLUE}ib-test${NC}"
    echo ""
    echo -e "${GREEN}Backup created at: ${BACKUP_FILE}${NC}"
    echo ""
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    # Check if we're in the right directory
    if [ ! -d "$HOME/Projects/Spyder" ]; then
        log_error "Spyder project directory not found!"
        log_error "Please run this script from the correct environment"
        exit 1
    fi

    # Get Windows IP
    log_info "Detecting Windows TWS computer IP..."
    WINDOWS_IP=$(get_windows_ip)

    if [ -z "$WINDOWS_IP" ]; then
        log_error "Could not determine Windows computer IP address"
        exit 1
    fi

    log_success "Windows TWS IP: $WINDOWS_IP"

    # Confirm with user
    echo ""
    read -p "Update .bashrc for Remote TWS at $WINDOWS_IP? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled by user"
        exit 0
    fi

    # Create backup
    if ! backup_bashrc; then
        log_error "Failed to create backup"
        exit 1
    fi

    # Update configuration
    log_info "Updating .bashrc configuration..."

    if ! update_ib_configuration "$WINDOWS_IP"; then
        log_error "Failed to update IB configuration"
        exit 1
    fi

    if ! update_ib_aliases "$WINDOWS_IP"; then
        log_error "Failed to update IB aliases"
        exit 1
    fi

    update_login_message "$WINDOWS_IP"

    # Validate
    if ! validate_configuration; then
        log_error "Configuration validation failed"
        log_warning "Restoring backup..."
        cp "$BACKUP_FILE" "$BASHRC_FILE"
        exit 1
    fi

    # Show summary
    show_summary "$WINDOWS_IP"

    echo -e "${GREEN}🎉 .bashrc update completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Remember to run: ${BLUE}source ~/.bashrc${NC} ${YELLOW}to apply changes${NC}"
}

# ==============================================================================
# SCRIPT ENTRY POINT
# ==============================================================================

# Check if running with --help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Update .bashrc for Remote TWS Configuration"
    echo ""
    echo "This script updates your .bashrc file to configure environment variables"
    echo "and aliases for connecting to a remote TWS instance running on Windows."
    echo ""
    echo "Usage: $0"
    echo ""
    echo "The script will:"
    echo "• Create a backup of your current .bashrc"
    echo "• Update IB Gateway configuration for remote TWS"
    echo "• Update aliases and functions for remote testing"
    echo "• Validate the new configuration"
    echo ""
    exit 0
fi

# Run main function
main "$@"
