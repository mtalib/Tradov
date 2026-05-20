#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ16_SpyderControl.sh
# Group: Q (Scripts/Control)
# Purpose: Master control script for complete Spyder system management
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:00:00
#
# Description:
#     Comprehensive control script that manages all Spyder components including
#     broker API, AI agents, risk systems, and monitoring. Provides commands for
#     starting, stopping, status checking, and system diagnostics.
# ===============================================================================

# ===============================================================================
# CONFIGURATION
# ===============================================================================

SPYDER_HOME="/home/adam/Projects/Spyder"
LEGACY_VENV_PATH="$SPYDER_HOME/spyder_venv"
MODERN_VENV_PATH="$SPYDER_HOME/.venv"
if [ -d "$MODERN_VENV_PATH" ]; then
    VENV_PATH="$MODERN_VENV_PATH"
else
    VENV_PATH="$LEGACY_VENV_PATH"
fi
LOG_DIR="$SPYDER_HOME/logs"
DATA_DIR="$SPYDER_HOME/data"
CONFIG_FILE="$SPYDER_HOME/.env"
PACKAGE_SCRIPTS_DIR="$SPYDER_HOME/Spyder/SpyderQ_Scripts"
LEGACY_SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
if [ -d "$PACKAGE_SCRIPTS_DIR" ]; then
    SCRIPTS_DIR="$PACKAGE_SCRIPTS_DIR"
else
    SCRIPTS_DIR="$LEGACY_SCRIPTS_DIR"
fi
MAIN_LAUNCHER_PATH="$SCRIPTS_DIR/SpyderQ14_MainLauncher.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Component definitions
declare -A COMPONENTS=(
    ["broker"]="Broker API"
    ["master"]="Master Controller"
    ["watchdog"]="Multi-Client Watchdog"
    ["metrics"]="Prometheus Metrics"
    ["coordinator"]="Meta Coordinator"
    ["risk"]="Risk Manager"
    ["dashboard"]="Trading Dashboard"
    ["agents"]="AI Agents"
)

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  SPYDER CONTROL SYSTEM${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
}

check_environment() {
    # Check if virtual environment exists
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found at $VENV_PATH"
        print_info "Run SpyderQ01_Setup.sh first"
        return 1
    fi
    
    # Check if config exists
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Configuration file not found at $CONFIG_FILE"
        print_info "Create .env file with your settings"
        return 1
    fi
    
    # Check Python version
    if ! command -v python3.10 &> /dev/null; then
        print_error "Python 3.10 is required but not found"
        return 1
    fi
    
    return 0
}

# ===============================================================================
# COMPONENT MANAGEMENT
# ===============================================================================

check_broker_api() {
    print_info "Checking Broker API configuration..."
    
    if [ -f "$CONFIG_FILE" ] && grep -q "TRADIER_API_KEY" "$CONFIG_FILE"; then
        print_success "Tradier API key configured"
        return 0
    fi
    
    print_warning "TRADIER_API_KEY not found in $CONFIG_FILE"
    echo "Set TRADIER_API_KEY in .env for live/paper trading"
    return 1
}

start_master_controller() {
    print_info "Starting Master Controller..."
    
    source "$VENV_PATH/bin/activate"
    cd "$SPYDER_HOME"
    
    python -m SpyderA_Core.SpyderA06_MasterController \
        > "$LOG_DIR/system/master.log" 2>&1 &
    
    local PID=$!
    echo $PID > "$LOG_DIR/master.pid"
    sleep 3
    
    if ps -p $PID > /dev/null; then
        print_success "Master Controller started (PID: $PID)"
        return 0
    else
        print_error "Failed to start Master Controller"
        return 1
    fi
}

start_monitoring() {
    print_info "Starting monitoring components..."
    
    # Start Watchdog
    "$SCRIPTS_DIR/SpyderQ13_StartWatchdog.sh" &
    
    # Start Metrics
    "$SCRIPTS_DIR/SpyderQ14_StartMetrics.sh" &
    
    sleep 2
    print_success "Monitoring components started"
}

start_ai_agents() {
    print_info "Starting AI Agents..."
    
    source "$VENV_PATH/bin/activate"
    cd "$SPYDER_HOME"
    
    # Start Meta Coordinator (manages all other agents)
    python -m SpyderX_Agents.SpyderX16_MetaCoordinator \
        > "$LOG_DIR/system/coordinator.log" 2>&1 &
    
    local PID=$!
    echo $PID > "$LOG_DIR/coordinator.pid"
    sleep 2
    
    if ps -p $PID > /dev/null; then
        print_success "AI Agents started via Meta Coordinator (PID: $PID)"
        return 0
    else
        print_error "Failed to start AI Agents"
        return 1
    fi
}

start_dashboard() {
    print_info "Starting Trading Dashboard..."
    
    source "$VENV_PATH/bin/activate"
    cd "$SPYDER_HOME"
    
    python -m SpyderG_GUI.SpyderG05_TradingDashboard \
        > "$LOG_DIR/system/dashboard.log" 2>&1 &
    
    local PID=$!
    echo $PID > "$LOG_DIR/dashboard.pid"
    sleep 3
    
    if ps -p $PID > /dev/null; then
        print_success "Trading Dashboard started (PID: $PID)"
        print_info "Dashboard should open in a new window"
        return 0
    else
        print_error "Failed to start Trading Dashboard"
        return 1
    fi
}

stop_component() {
    local pidfile="$1"
    local name="$2"
    
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if ps -p $PID > /dev/null 2>&1; then
            print_info "Stopping $name (PID: $PID)..."
            kill -TERM $PID 2>/dev/null
            sleep 2
            
            if ps -p $PID > /dev/null 2>&1; then
                print_warning "Force stopping $name"
                kill -KILL $PID 2>/dev/null
            fi
            
            print_success "$name stopped"
            rm -f "$pidfile"
        else
            print_warning "$name not running (stale PID file)"
            rm -f "$pidfile"
        fi
    else
        print_info "$name not running"
    fi
}

# ===============================================================================
# MAIN COMMANDS
# ===============================================================================

cmd_start() {
    print_header "Starting Spyder System"
    echo ""
    
    if ! check_environment; then
        return 1
    fi
    
    # Start components in order
    check_broker_api || print_warning "Continue without broker API"
    echo ""
    
    start_monitoring
    echo ""
    
    start_master_controller
    echo ""
    
    start_ai_agents
    echo ""
    
    if [ "$1" == "--with-dashboard" ]; then
        start_dashboard
        echo ""
    fi
    
    print_success "Spyder system started successfully"
    echo ""
    echo "Use 'spyder status' to check component status"
    echo "Use 'spyder monitor' for live monitoring"
}

cmd_stop() {
    print_header "Stopping Spyder System"
    echo ""
    
    # Stop components in reverse order
    stop_component "$LOG_DIR/dashboard.pid" "Trading Dashboard"
    stop_component "$LOG_DIR/coordinator.pid" "AI Agents"
    stop_component "$LOG_DIR/master.pid" "Master Controller"
    stop_component "$LOG_DIR/integration.pid" "Integration Manager"
    stop_component "$LOG_DIR/watchdog.pid" "Watchdog"
    stop_component "$LOG_DIR/metrics.pid" "Metrics"
    
    echo ""
    print_success "Spyder system stopped"
}

cmd_restart() {
    print_header "Restarting Spyder System"
    echo ""
    
    cmd_stop
    echo ""
    sleep 3
    cmd_start "$@"
}

cmd_status() {
    print_header "System Status"
    echo ""
    
    # Use the new monitoring script
    python "$SCRIPTS_DIR/SpyderQ25_SystemMonitor.py" --once
}

cmd_monitor() {
    print_header "Live System Monitor"
    echo ""
    
    # Use the new monitoring script in continuous mode
    python "$SCRIPTS_DIR/SpyderQ25_SystemMonitor.py" --interval 5
}

cmd_logs() {
    local component="${1:-system}"
    
    print_header "Viewing Logs: $component"
    echo ""
    
    case $component in
        master)
            tail -f "$LOG_DIR/system/master.log"
            ;;
        watchdog)
            tail -f "$LOG_DIR/system/watchdog.log"
            ;;
        metrics)
            tail -f "$LOG_DIR/system/metrics.log"
            ;;
        dashboard)
            tail -f "$LOG_DIR/system/dashboard.log"
            ;;
        agents)
            tail -f "$LOG_DIR/system/coordinator.log"
            ;;
        all)
            tail -f "$LOG_DIR/system/"*.log
            ;;
        *)
            tail -f "$LOG_DIR/system/"*.log
            ;;
    esac
}

cmd_check() {
    print_header "System Health Check"
    echo ""
    
    local issues=0
    
    # Check environment
    print_info "Checking environment..."
    if check_environment; then
        print_success "Environment OK"
    else
        print_error "Environment issues found"
        ((issues++))
    fi
    echo ""
    
    # Check Broker API
    print_info "Checking Broker API..."
    if [ -f "$CONFIG_FILE" ] && grep -q "TRADIER_API_KEY" "$CONFIG_FILE"; then
        print_success "Broker API configured"
    else
        print_error "Broker API not configured"
        ((issues++))
    fi
    echo ""
    
    # Check metrics endpoint
    print_info "Checking metrics endpoint..."
    if curl -s localhost:8000/metrics > /dev/null 2>&1; then
        print_success "Metrics endpoint responding"
    else
        print_warning "Metrics endpoint not responding"
    fi
    echo ""
    
    # Check disk space
    print_info "Checking disk space..."
    DISK_USAGE=$(df "$SPYDER_HOME" | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -lt 90 ]; then
        print_success "Disk usage: ${DISK_USAGE}%"
    else
        print_error "Low disk space: ${DISK_USAGE}%"
        ((issues++))
    fi
    echo ""
    
    # Check log files
    print_info "Checking log directory..."
    if [ -d "$LOG_DIR" ]; then
        LOG_SIZE=$(du -sh "$LOG_DIR" | cut -f1)
        print_success "Log directory: $LOG_SIZE"
    else
        print_error "Log directory not found"
        ((issues++))
    fi
    echo ""
    
    # Summary
    if [ "$issues" -eq 0 ]; then
        print_success "System health check passed"
    else
        print_error "System health check found $issues issue(s)"
    fi
}

cmd_backup() {
    print_header "Creating System Backup"
    echo ""
    
    BACKUP_DIR="$SPYDER_HOME/backup"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/spyder_backup_$TIMESTAMP.tar.gz"
    
    mkdir -p "$BACKUP_DIR"
    
    print_info "Creating backup..."
    tar -czf "$BACKUP_FILE" \
        --exclude="$SPYDER_HOME/spyder_venv" \
        --exclude="$SPYDER_HOME/logs" \
        --exclude="$SPYDER_HOME/backup" \
        -C "$SPYDER_HOME" . 2>/dev/null
    
    if [ -f "$BACKUP_FILE" ]; then
        SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_success "Backup created: $BACKUP_FILE ($SIZE)"
    else
        print_error "Backup failed"
    fi
}

cmd_clean() {
    print_header "Cleaning System"
    echo ""
    
    print_info "Cleaning old logs..."
    find "$LOG_DIR" -type f -name "*.log" -mtime +7 -delete
    print_success "Old logs removed"
    
    print_info "Cleaning temporary files..."
    find "$SPYDER_HOME" -type f -name "*.pyc" -delete
    find "$SPYDER_HOME" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    print_success "Temporary files cleaned"
    
    print_info "Cleaning old data files..."
    find "$DATA_DIR" -type f -name "*.tmp" -delete
    print_success "Old data files cleaned"
}

cmd_reset_paper_state() {
    print_header "Reset Paper State"
    echo ""

    if [ ! -x "$VENV_PATH/bin/python" ]; then
        print_error "Python interpreter not found at $VENV_PATH/bin/python"
        return 1
    fi

    if [ ! -f "$MAIN_LAUNCHER_PATH" ]; then
        print_error "Main launcher not found at $MAIN_LAUNCHER_PATH"
        return 1
    fi

    print_warning "This will back up and clear local paper ledger/tracker state via H05"
    print_info "Running guarded paper reset through Q14..."

    cd "$SPYDER_HOME" || return 1
    "$VENV_PATH/bin/python" "$MAIN_LAUNCHER_PATH" --mode paper --headless --reset-paper-state
    local reset_status=$?

    if [ "$reset_status" -eq 0 ]; then
        print_success "Paper state reset completed"
    else
        print_error "Paper state reset failed"
    fi

    return "$reset_status"
}

cmd_help() {
    echo -e "${CYAN}SPYDER Control System${NC}"
    echo ""
    echo "Usage: spyder [command] [options]"
    echo ""
    echo "Commands:"
    echo "  start [--with-dashboard]  Start all Spyder components"
    echo "  stop                      Stop all Spyder components"
    echo "  restart                   Restart all components"
    echo "  status                    Show system status"
    echo "  monitor                   Live system monitoring"
    echo "  logs [component]          View component logs"
    echo "  check                     Run health check"
    echo "  backup                    Create system backup"
    echo "  clean                     Clean temporary files"
    echo "  reset-paper-state         Back up and clear local paper state"
    echo "  help                      Show this help message"
    echo ""
    echo "Components:"
    echo "  master     Master Controller"
    echo "  watchdog   Multi-Client Watchdog"
    echo "  metrics    Prometheus Metrics"
    echo "  dashboard  Trading Dashboard"
    echo "  agents     AI Agents"
    echo "  all        All components"
    echo ""
    echo "Examples:"
    echo "  spyder start               Start system without dashboard"
    echo "  spyder start --with-dashboard  Start with dashboard"
    echo "  spyder logs master         View master controller logs"
    echo "  spyder monitor             Start live monitoring"
    echo "  spyder reset-paper-state   Back up and clear paper ledger/state"
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_error "Do not run as root"
        exit 1
    fi
    
    # Parse command
    COMMAND="${1:-help}"
    shift
    
    case "$COMMAND" in
        start)
            cmd_start "$@"
            ;;
        stop)
            cmd_stop
            ;;
        restart)
            cmd_restart "$@"
            ;;
        status)
            cmd_status
            ;;
        monitor)
            cmd_monitor
            ;;
        logs)
            cmd_logs "$@"
            ;;
        check)
            cmd_check
            ;;
        backup)
            cmd_backup
            ;;
        clean)
            cmd_clean
            ;;
        reset-paper-state)
            cmd_reset_paper_state
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            echo "Use 'spyder help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"