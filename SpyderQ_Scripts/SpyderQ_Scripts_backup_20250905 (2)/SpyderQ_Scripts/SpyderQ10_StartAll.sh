#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ10_StartAll.sh
# Group: Q (Scripts)
# Purpose: Master startup script for complete Spyder system with GUI support
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 14:30:00
#
# Description:
#     Comprehensive startup script that initializes the entire Spyder trading
#     system including IB Gateway connection, trading engine, monitoring services,
#     and PyQt6 GUI dashboard. Designed to be launched from desktop icon or
#     terminal with proper error handling and status feedback.
# ===============================================================================

set -e  # Exit on error

# ===============================================================================
# CONFIGURATION
# ===============================================================================
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
VENV_PATH="$SPYDER_HOME/spyder_venv"
LOG_DIR="$SPYDER_HOME/logs"
PID_DIR="$SPYDER_HOME/pids"
CONFIG_FILE="$SPYDER_HOME/.env"

# Process names
GATEWAY_PROCESS="ibgateway"
MAIN_PROCESS="SpyderA01_Main"
DASHBOARD_PROCESS="SpyderG01_MainWindow"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# GUI Mode Detection
GUI_MODE=false
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    GUI_MODE=true
fi

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}    SPYDER TRADING SYSTEM STARTUP${NC}"
    echo -e "${BLUE}    Version 1.0 - SPY Options Trading${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    log_message "SUCCESS" "$1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    log_message "ERROR" "$1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
    log_message "WARNING" "$1"
}

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
    log_message "INFO" "$1"
}

log_message() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_DIR/startup.log"
}

# ===============================================================================
# STARTUP CHECKS
# ===============================================================================

check_environment() {
    print_info "Checking environment..."
    
    # Check if Spyder directory exists
    if [ ! -d "$SPYDER_HOME" ]; then
        print_error "Spyder directory not found: $SPYDER_HOME"
        exit 1
    fi
    
    # Check Python virtual environment
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found: $VENV_PATH"
        print_info "Run SpyderQ01_Setup.sh first"
        exit 1
    fi
    
    # Check configuration file
    if [ ! -f "$CONFIG_FILE" ]; then
        print_warning "Configuration file not found, creating default..."
        create_default_config
    fi
    
    # Create necessary directories
    mkdir -p "$LOG_DIR"/{system,trading,clients}
    mkdir -p "$PID_DIR"
    
    print_success "Environment check passed"
}

create_default_config() {
    cat > "$CONFIG_FILE" << 'EOF'
# SPYDER Configuration
SPYDER_ENV=production
SPYDER_HOME=/home/adam/Projects/Spyder

# IB Gateway Configuration
IB_GATEWAY_HOST=127.0.0.1
IB_GATEWAY_PORT=7497
IB_CLIENT_ID=1
IB_ACCOUNT=

# Trading Configuration
ENABLE_LIVE_TRADING=false
ENABLE_PAPER_TRADING=true
MAX_DAILY_TRADES=50
MAX_POSITION_SIZE=10000

# Risk Management
MAX_DAILY_LOSS=1000
MAX_POSITION_RISK=0.02
STOP_LOSS_PERCENTAGE=0.02

# GUI Configuration
ENABLE_GUI=true
GUI_THEME=dark
GUI_UPDATE_INTERVAL=1000

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
ENABLE_ALERTS=true
EOF
    print_success "Created default configuration"
}

# ===============================================================================
# PROCESS MANAGEMENT
# ===============================================================================

is_process_running() {
    local process_name=$1
    pgrep -f "$process_name" > /dev/null 2>&1
}

save_pid() {
    local process_name=$1
    local pid=$2
    echo "$pid" > "$PID_DIR/$process_name.pid"
}

get_pid() {
    local process_name=$1
    local pid_file="$PID_DIR/$process_name.pid"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    else
        echo ""
    fi
}

# ===============================================================================
# IB GATEWAY STARTUP
# ===============================================================================

start_ib_gateway() {
    print_info "Checking IB Gateway..."
    
    if is_process_running "$GATEWAY_PROCESS"; then
        print_success "IB Gateway already running"
    else
        print_warning "IB Gateway not running"
        print_info "Please start IB Gateway manually"
        print_info "Gateway path: ~/Jts/ibgateway/1039/ibgateway"
        
        if [ "$GUI_MODE" = true ]; then
            # Show GUI notification
            notify-send "Spyder Trading System" "Please start IB Gateway before continuing" -i dialog-warning
        fi
        
        read -p "Press Enter when IB Gateway is running..."
        
        if is_process_running "$GATEWAY_PROCESS"; then
            print_success "IB Gateway detected"
        else
            print_error "IB Gateway still not running. Cannot continue."
            exit 1
        fi
    fi
}

# ===============================================================================
# TRADING ENGINE STARTUP
# ===============================================================================

start_trading_engine() {
    print_info "Starting Trading Engine..."
    
    # Activate virtual environment
    source "$VENV_PATH/bin/activate"
    
    # Set Python path
    export PYTHONPATH="$SPYDER_HOME:$PYTHONPATH"
    
    # Source configuration
    source "$CONFIG_FILE"
    
    # Start main trading engine
    cd "$SPYDER_HOME"
    
    if [ -f "SpyderA_Core/SpyderA01_Main.py" ]; then
        nohup python3 SpyderA_Core/SpyderA01_Main.py \
            > "$LOG_DIR/system/main.log" 2>&1 &
        
        local pid=$!
        save_pid "main_engine" $pid
        
        # Wait for engine to initialize
        sleep 3
        
        if kill -0 $pid 2>/dev/null; then
            print_success "Trading Engine started (PID: $pid)"
        else
            print_error "Trading Engine failed to start"
            return 1
        fi
    else
        print_error "Main trading module not found"
        return 1
    fi
}

# ===============================================================================
# MONITORING SERVICES
# ===============================================================================

start_monitoring_services() {
    print_info "Starting Monitoring Services..."
    
    # Start Production Watchdog
    if [ -f "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py" ]; then
        nohup python3 "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py" \
            > "$LOG_DIR/system/watchdog.log" 2>&1 &
        
        local watchdog_pid=$!
        save_pid "watchdog" $watchdog_pid
        print_success "Watchdog started (PID: $watchdog_pid)"
    fi
    
    # Start System Monitor
    if [ -f "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ25_SystemMonitor.py" ]; then
        nohup python3 "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ25_SystemMonitor.py" \
            > "$LOG_DIR/system/monitor.log" 2>&1 &
        
        local monitor_pid=$!
        save_pid "monitor" $monitor_pid
        print_success "System Monitor started (PID: $monitor_pid)"
    fi
}

# ===============================================================================
# GUI DASHBOARD
# ===============================================================================

start_gui_dashboard() {
    if [ "$GUI_MODE" = false ]; then
        print_warning "No display detected, skipping GUI"
        return
    fi
    
    print_info "Starting GUI Dashboard..."
    
    # Check if GUI is enabled in config
    if grep -q "ENABLE_GUI=false" "$CONFIG_FILE" 2>/dev/null; then
        print_info "GUI disabled in configuration"
        return
    fi
    
    # Start PyQt6 Dashboard
    if [ -f "$SPYDER_HOME/SpyderG_GUI/SpyderG01_MainWindow.py" ]; then
        cd "$SPYDER_HOME"
        python3 SpyderG_GUI/SpyderG01_MainWindow.py \
            > "$LOG_DIR/system/gui.log" 2>&1 &
        
        local gui_pid=$!
        save_pid "gui" $gui_pid
        
        sleep 2
        
        if kill -0 $gui_pid 2>/dev/null; then
            print_success "GUI Dashboard started (PID: $gui_pid)"
        else
            print_error "GUI Dashboard failed to start"
            print_info "Check logs at: $LOG_DIR/system/gui.log"
        fi
    else
        print_warning "GUI module not found"
    fi
}

# ===============================================================================
# STATUS CHECK
# ===============================================================================

check_system_status() {
    print_info "System Status Check..."
    
    local all_good=true
    
    # Check IB Gateway
    if is_process_running "$GATEWAY_PROCESS"; then
        print_success "IB Gateway: Running"
    else
        print_error "IB Gateway: Not Running"
        all_good=false
    fi
    
    # Check Trading Engine
    local main_pid=$(get_pid "main_engine")
    if [ -n "$main_pid" ] && kill -0 $main_pid 2>/dev/null; then
        print_success "Trading Engine: Running (PID: $main_pid)"
    else
        print_error "Trading Engine: Not Running"
        all_good=false
    fi
    
    # Check Watchdog
    local watchdog_pid=$(get_pid "watchdog")
    if [ -n "$watchdog_pid" ] && kill -0 $watchdog_pid 2>/dev/null; then
        print_success "Watchdog: Running (PID: $watchdog_pid)"
    else
        print_warning "Watchdog: Not Running"
    fi
    
    # Check GUI
    local gui_pid=$(get_pid "gui")
    if [ -n "$gui_pid" ] && kill -0 $gui_pid 2>/dev/null; then
        print_success "GUI Dashboard: Running (PID: $gui_pid)"
    else
        print_info "GUI Dashboard: Not Running"
    fi
    
    if [ "$all_good" = true ]; then
        print_success "All critical systems operational"
        return 0
    else
        print_error "Some systems failed to start"
        return 1
    fi
}

# ===============================================================================
# CLEANUP ON EXIT
# ===============================================================================

cleanup_on_exit() {
    if [ $? -ne 0 ]; then
        print_error "Startup failed. Check logs in: $LOG_DIR"
        
        if [ "$GUI_MODE" = true ]; then
            notify-send "Spyder Startup Failed" "Check logs in $LOG_DIR" -i dialog-error
        fi
    fi
}

trap cleanup_on_exit EXIT

# ===============================================================================
# MAIN STARTUP SEQUENCE
# ===============================================================================

main() {
    # Clear terminal if running interactively
    if [ -t 1 ]; then
        clear
    fi
    
    # Initialize log
    echo "===== SPYDER STARTUP: $(date) =====" >> "$LOG_DIR/startup.log"
    
    # Display header
    print_header
    echo ""
    
    # Run startup sequence
    check_environment
    echo ""
    
    start_ib_gateway
    echo ""
    
    start_trading_engine
    echo ""
    
    start_monitoring_services
    echo ""
    
    start_gui_dashboard
    echo ""
    
    # Final status check
    check_system_status
    echo ""
    
    # Success message
    if [ $? -eq 0 ]; then
        print_success "🚀 Spyder Trading System is now running!"
        echo ""
        echo "Monitor logs: tail -f $LOG_DIR/system/*.log"
        echo "Stop system: $SPYDER_HOME/SpyderQ_Scripts/SpyderQ11_StopAll.sh"
        echo ""
        
        if [ "$GUI_MODE" = true ]; then
            notify-send "Spyder Trading System" "System successfully started" -i dialog-information
        fi
    else
        print_error "System startup incomplete. Please check the errors above."
        exit 1
    fi
}

# ===============================================================================
# SCRIPT EXECUTION
# ===============================================================================

# Run main function
main "$@"