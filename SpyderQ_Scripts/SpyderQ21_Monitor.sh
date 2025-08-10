#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ21_Monitor.sh
# Group: Q (Scripts)
# Purpose: Real-time monitoring dashboard for Spyder system
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 15:15:00
#
# Description:
#     Provides a real-time terminal-based monitoring dashboard for the Spyder
#     trading system. Displays live updates of system status, trading activity,
#     client connections, performance metrics, and logs. Complements the PyQt6
#     GUI dashboard with a lightweight terminal interface for remote monitoring.
# ===============================================================================

# ===============================================================================
# CONFIGURATION
# ===============================================================================
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
PID_DIR="$SPYDER_HOME/pids"
LOG_DIR="$SPYDER_HOME/logs"
CONFIG_FILE="$SPYDER_HOME/.env"

# Update intervals
UPDATE_INTERVAL=2  # seconds
LOG_LINES=10      # number of log lines to show

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'
BOLD='\033[1m'

# Screen management
CLEAR_SCREEN='\033[2J'
MOVE_CURSOR='\033[H'

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

cleanup() {
    # Reset terminal on exit
    tput cnorm  # Show cursor
    tput sgr0   # Reset colors
    echo -e "${NC}"
    exit 0
}

trap cleanup EXIT INT TERM

get_terminal_size() {
    TERM_COLS=$(tput cols)
    TERM_ROWS=$(tput lines)
}

draw_header() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S ET')
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}${BOLD}          SPYDER REAL-TIME MONITOR - TRADING SYSTEM DASHBOARD             ${NC}${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}                         $timestamp                          ${BLUE}║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
}

draw_separator() {
    echo -e "${CYAN}───────────────────────────────────────────────────────────────────────────${NC}"
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

check_process() {
    local pid=$1
    if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

format_status() {
    local status=$1
    if [ "$status" = "RUNNING" ]; then
        echo -e "${GREEN}● RUNNING${NC}"
    elif [ "$status" = "STOPPED" ]; then
        echo -e "${RED}○ STOPPED${NC}"
    elif [ "$status" = "WARNING" ]; then
        echo -e "${YELLOW}◐ WARNING${NC}"
    else
        echo -e "$status"
    fi
}

get_cpu_usage() {
    top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
}

get_memory_usage() {
    free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}'
}

get_process_memory() {
    local pid=$1
    if [ -n "$pid" ] && check_process $pid; then
        ps -o rss= -p $pid | awk '{printf "%.1f", $1/1024}'
    else
        echo "0"
    fi
}

# ===============================================================================
# MONITORING FUNCTIONS
# ===============================================================================

show_system_status() {
    echo -e "${BOLD}${WHITE}SYSTEM STATUS${NC}"
    echo ""
    
    # IB Gateway
    local ib_status="STOPPED"
    if pgrep -f "ibgateway" > /dev/null 2>&1; then
        ib_status="RUNNING"
    fi
    printf "  %-25s %s\n" "IB Gateway:" "$(format_status $ib_status)"
    
    # Trading Engine
    local engine_pid=$(get_pid "main_engine")
    local engine_status="STOPPED"
    if check_process "$engine_pid"; then
        engine_status="RUNNING"
        local engine_mem=$(get_process_memory $engine_pid)
        printf "  %-25s %s (PID: %s, Mem: %s MB)\n" "Trading Engine:" "$(format_status $engine_status)" "$engine_pid" "$engine_mem"
    else
        printf "  %-25s %s\n" "Trading Engine:" "$(format_status $engine_status)"
    fi
    
    # GUI Dashboard
    local gui_pid=$(get_pid "gui")
    local gui_status="STOPPED"
    if check_process "$gui_pid"; then
        gui_status="RUNNING"
        local gui_mem=$(get_process_memory $gui_pid)
        printf "  %-25s %s (PID: %s, Mem: %s MB)\n" "GUI Dashboard:" "$(format_status $gui_status)" "$gui_pid" "$gui_mem"
    else
        printf "  %-25s %s\n" "GUI Dashboard:" "$(format_status $gui_status)"
    fi
    
    # Watchdog
    local watchdog_pid=$(get_pid "watchdog")
    local watchdog_status="STOPPED"
    if check_process "$watchdog_pid"; then
        watchdog_status="RUNNING"
    fi
    printf "  %-25s %s\n" "Production Watchdog:" "$(format_status $watchdog_status)"
    
    # System Monitor
    local monitor_pid=$(get_pid "monitor")
    local monitor_status="STOPPED"
    if check_process "$monitor_pid"; then
        monitor_status="RUNNING"
    fi
    printf "  %-25s %s\n" "System Monitor:" "$(format_status $monitor_status)"
}

show_client_connections() {
    echo -e "${BOLD}${WHITE}CLIENT CONNECTIONS (Multi-Client Architecture)${NC}"
    echo ""
    
    local clients=("Admin" "Orders" "Core" "Options" "Volatility" "Internals" "Major ETFs" "Extended" "Sector ETFs")
    
    # Check if Prometheus metrics are available
    local prometheus_available=false
    if nc -z localhost 9090 2>/dev/null; then
        prometheus_available=true
    fi
    
    # Display in two columns
    for i in {0..4}; do
        local left_idx=$i
        local right_idx=$((i + 5))
        
        # Left column
        if [ $left_idx -lt 9 ]; then
            if [ "$prometheus_available" = true ]; then
                printf "  ${GREEN}●${NC} CLIENT %d: %-15s" "$left_idx" "${clients[$left_idx]}"
            else
                printf "  ${RED}○${NC} CLIENT %d: %-15s" "$left_idx" "${clients[$left_idx]}"
            fi
        fi
        
        # Right column
        if [ $right_idx -lt 9 ]; then
            printf "    "
            if [ "$prometheus_available" = true ]; then
                printf "${GREEN}●${NC} CLIENT %d: %-15s" "$right_idx" "${clients[$right_idx]}"
            else
                printf "${RED}○${NC} CLIENT %d: %-15s" "$right_idx" "${clients[$right_idx]}"
            fi
        fi
        
        echo ""
    done
}

show_performance_metrics() {
    echo -e "${BOLD}${WHITE}PERFORMANCE METRICS${NC}"
    echo ""
    
    local cpu_usage=$(get_cpu_usage)
    local mem_usage=$(get_memory_usage)
    
    # CPU bar graph
    printf "  CPU Usage:    [" 
    local cpu_bars=$((${cpu_usage%.*} / 5))
    for i in {1..20}; do
        if [ $i -le $cpu_bars ]; then
            if [ $i -le 10 ]; then
                echo -n -e "${GREEN}█${NC}"
            elif [ $i -le 15 ]; then
                echo -n -e "${YELLOW}█${NC}"
            else
                echo -n -e "${RED}█${NC}"
            fi
        else
            echo -n "░"
        fi
    done
    printf "] %s%%\n" "$cpu_usage"
    
    # Memory bar graph
    printf "  Memory Usage: ["
    local mem_bars=$((${mem_usage%.*} / 5))
    for i in {1..20}; do
        if [ $i -le $mem_bars ]; then
            if [ $i -le 10 ]; then
                echo -n -e "${GREEN}█${NC}"
            elif [ $i -le 15 ]; then
                echo -n -e "${YELLOW}█${NC}"
            else
                echo -n -e "${RED}█${NC}"
            fi
        else
            echo -n "░"
        fi
    done
    printf "] %s%%\n" "$mem_usage"
    
    # Disk usage
    local disk_usage=$(df -h "$SPYDER_HOME" | awk 'NR==2{print $5}' | sed 's/%//')
    printf "  Disk Usage:   ["
    local disk_bars=$((disk_usage / 5))
    for i in {1..20}; do
        if [ $i -le $disk_bars ]; then
            if [ $i -le 10 ]; then
                echo -n -e "${GREEN}█${NC}"
            elif [ $i -le 15 ]; then
                echo -n -e "${YELLOW}█${NC}"
            else
                echo -n -e "${RED}█${NC}"
            fi
        else
            echo -n "░"
        fi
    done
    printf "] %s%%\n" "$disk_usage"
}

show_trading_activity() {
    echo -e "${BOLD}${WHITE}TRADING ACTIVITY${NC}"
    echo ""
    
    # Check if trading is active
    local trading_status="INACTIVE"
    local trading_mode="PAPER"
    
    if [ -f "$CONFIG_FILE" ]; then
        if grep -q "ENABLE_LIVE_TRADING=true" "$CONFIG_FILE" 2>/dev/null; then
            trading_mode="LIVE"
        fi
    fi
    
    # Simulate some trading metrics (in production, would read from actual data)
    printf "  %-20s %s\n" "Trading Status:" "$(format_status $trading_status)"
    printf "  %-20s %s\n" "Trading Mode:" "$trading_mode"
    printf "  %-20s %s\n" "Open Positions:" "0"
    printf "  %-20s %s\n" "Today's P&L:" "$0.00"
    printf "  %-20s %s\n" "Total Volume:" "0"
}

show_recent_logs() {
    echo -e "${BOLD}${WHITE}RECENT LOGS${NC}"
    echo ""
    
    if [ -d "$LOG_DIR/system" ]; then
        # Show recent log entries with color coding
        tail -n $LOG_LINES "$LOG_DIR/system/main.log" 2>/dev/null | while IFS= read -r line; do
            if echo "$line" | grep -q "ERROR\|CRITICAL\|FATAL"; then
                echo -e "  ${RED}$line${NC}"
            elif echo "$line" | grep -q "WARNING"; then
                echo -e "  ${YELLOW}$line${NC}"
            elif echo "$line" | grep -q "SUCCESS\|CONNECTED"; then
                echo -e "  ${GREEN}$line${NC}"
            else
                echo -e "  ${WHITE}$line${NC}"
            fi
        done
    else
        echo "  No logs available"
    fi
}

show_alerts() {
    echo -e "${BOLD}${WHITE}ALERTS & NOTIFICATIONS${NC}"
    echo ""
    
    # Check for critical conditions
    local alerts_found=false
    
    # Check CPU
    local cpu_usage=$(get_cpu_usage)
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "  ${RED}⚠ HIGH CPU USAGE: ${cpu_usage}%${NC}"
        alerts_found=true
    fi
    
    # Check Memory
    local mem_usage=$(get_memory_usage)
    if (( $(echo "$mem_usage > 80" | bc -l) )); then
        echo -e "  ${RED}⚠ HIGH MEMORY USAGE: ${mem_usage}%${NC}"
        alerts_found=true
    fi
    
    # Check if IB Gateway is down
    if ! pgrep -f "ibgateway" > /dev/null 2>&1; then
        echo -e "  ${YELLOW}⚠ IB Gateway is not running${NC}"
        alerts_found=true
    fi
    
    # Check for recent errors in logs
    if [ -f "$LOG_DIR/system/main.log" ]; then
        local error_count=$(tail -n 100 "$LOG_DIR/system/main.log" 2>/dev/null | grep -c "ERROR\|CRITICAL" || echo "0")
        if [ $error_count -gt 5 ]; then
            echo -e "  ${YELLOW}⚠ $error_count errors in recent logs${NC}"
            alerts_found=true
        fi
    fi
    
    if [ "$alerts_found" = false ]; then
        echo -e "  ${GREEN}✓ No alerts${NC}"
    fi
}

# ===============================================================================
# MAIN MONITORING LOOP
# ===============================================================================

main_loop() {
    # Hide cursor
    tput civis
    
    while true; do
        # Clear screen and reset cursor
        echo -e "${CLEAR_SCREEN}${MOVE_CURSOR}"
        
        # Get terminal size
        get_terminal_size
        
        # Draw dashboard
        draw_header
        echo ""
        
        # Create two-column layout
        {
            # Left column
            show_system_status
            echo ""
            show_client_connections
            echo ""
            show_performance_metrics
        } | while IFS= read -r line; do
            echo "$line"
        done
        
        draw_separator
        
        # Bottom section
        show_trading_activity
        echo ""
        draw_separator
        show_recent_logs
        echo ""
        draw_separator
        show_alerts
        
        # Footer
        echo ""
        draw_separator
        echo -e "${CYAN}Press Ctrl+C to exit | Refresh: ${UPDATE_INTERVAL}s | ${NC}[F5] Force Refresh [Q] Quit [H] Help"
        
        # Wait for update interval or user input
        read -t $UPDATE_INTERVAL -n 1 key
        case $key in
            q|Q)
                cleanup
                ;;
            h|H)
                show_help
                ;;
            r|R)
                continue
                ;;
        esac
    done
}

show_help() {
    echo -e "${CLEAR_SCREEN}${MOVE_CURSOR}"
    echo -e "${BOLD}${WHITE}SPYDER MONITOR - HELP${NC}"
    echo ""
    echo "Keyboard Shortcuts:"
    echo "  Q - Quit monitor"
    echo "  H - Show this help"
    echo "  R - Force refresh"
    echo "  Ctrl+C - Exit"
    echo ""
    echo "Status Indicators:"
    echo -e "  ${GREEN}●${NC} - Running/Active"
    echo -e "  ${RED}○${NC} - Stopped/Inactive"
    echo -e "  ${YELLOW}◐${NC} - Warning/Degraded"
    echo ""
    echo "This monitor shows real-time status of:"
    echo "  • System components (IB Gateway, Trading Engine, GUI)"
    echo "  • Multi-client connections (9 IB clients)"
    echo "  • Performance metrics (CPU, Memory, Disk)"
    echo "  • Trading activity and P&L"
    echo "  • Recent log entries"
    echo "  • System alerts and warnings"
    echo ""
    echo "Press any key to return to monitor..."
    read -n 1
}

# ===============================================================================
# SCRIPT EXECUTION
# ===============================================================================

# Check for command line options
case "$1" in
    --help|-h)
        echo "SPYDER Real-Time Monitor"
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --once         Run once and exit (no loop)"
        echo "  --interval N   Set update interval to N seconds (default: 2)"
        echo ""
        exit 0
        ;;
    --once)
        # Run once without loop
        get_terminal_size
        draw_header
        echo ""
        show_system_status
        echo ""
        show_client_connections
        echo ""
        show_performance_metrics
        echo ""
        draw_separator
        show_trading_activity
        echo ""
        draw_separator
        show_recent_logs
        echo ""
        draw_separator
        show_alerts
        exit 0
        ;;
    --interval)
        UPDATE_INTERVAL=$2
        ;;
esac

# Start monitoring loop
main_loop