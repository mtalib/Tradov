#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ40_Cleanup.sh
# Group: Q (Scripts)
# Purpose: Clean logs, temporary files, and manage disk space
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 18:30:00
#
# Description:
#     Comprehensive cleanup utility that removes old logs, temporary files,
#     cache data, and manages disk space. Includes options for selective
#     cleaning, archiving important data before deletion, and safe cleanup
#     of trading artifacts while preserving critical system files.
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
LOG_DIR="$SPYDER_HOME/logs"
DATA_DIR="$SPYDER_HOME/data"
CACHE_DIR="$SPYDER_HOME/.cache"
BACKUP_DIR="$SPYDER_HOME/backup"
ARCHIVE_DIR="$SPYDER_HOME/archive"

# Cleanup settings
LOG_RETENTION_DAYS=7
DATA_RETENTION_DAYS=30
REPORT_RETENTION_DAYS=90
MIN_FREE_SPACE_GB=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
FILES_DELETED=0
SPACE_FREED=0
FILES_ARCHIVED=0

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      SPYDER SYSTEM CLEANUP UTILITY        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
}

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

get_size() {
    du -sh "$1" 2>/dev/null | cut -f1
}

get_free_space_gb() {
    df "$SPYDER_HOME" | awk 'NR==2 {print int($4/1048576)}'
}

# ===============================================================================
# CLEANUP FUNCTIONS
# ===============================================================================

clean_logs() {
    print_info "Cleaning log files older than $LOG_RETENTION_DAYS days..."
    
    if [ ! -d "$LOG_DIR" ]; then
        print_warning "Log directory not found"
        return
    fi
    
    local initial_size=$(get_size "$LOG_DIR")
    
    # Clean old log files
    find "$LOG_DIR" -type f -name "*.log" -mtime +$LOG_RETENTION_DAYS -print -delete 2>/dev/null | while read file; do
        ((FILES_DELETED++))
        echo "  Deleted: $(basename "$file")"
    done
    
    # Clean empty log files
    find "$LOG_DIR" -type f -name "*.log" -empty -delete 2>/dev/null
    
    # Compress large current logs
    find "$LOG_DIR" -type f -name "*.log" -size +100M -exec gzip {} \; 2>/dev/null
    
    local final_size=$(get_size "$LOG_DIR")
    print_success "Log cleanup complete ($initial_size → $final_size)"
}

clean_python_cache() {
    print_info "Cleaning Python cache files..."
    
    local count=0
    
    # Remove __pycache__ directories
    find "$SPYDER_HOME" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove .pyc files
    find "$SPYDER_HOME" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove .pyo files
    find "$SPYDER_HOME" -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # Remove .pyd files
    find "$SPYDER_HOME" -type f -name "*.pyd" -delete 2>/dev/null || true
    
    print_success "Python cache cleaned"
}

clean_temp_files() {
    print_info "Cleaning temporary files..."
    
    # Clean tmp files
    find "$SPYDER_HOME" -type f -name "*.tmp" -delete 2>/dev/null || true
    find "$SPYDER_HOME" -type f -name "*.temp" -delete 2>/dev/null || true
    find "$SPYDER_HOME" -type f -name "*~" -delete 2>/dev/null || true
    find "$SPYDER_HOME" -type f -name ".~*" -delete 2>/dev/null || true
    
    # Clean vim swap files
    find "$SPYDER_HOME" -type f -name "*.swp" -delete 2>/dev/null || true
    find "$SPYDER_HOME" -type f -name "*.swo" -delete 2>/dev/null || true
    
    # Clean backup files
    find "$SPYDER_HOME" -type f -name "*.bak" -delete 2>/dev/null || true
    find "$SPYDER_HOME" -type f -name "*.backup" -delete 2>/dev/null || true
    
    print_success "Temporary files cleaned"
}

clean_old_data() {
    print_info "Cleaning old data files..."
    
    if [ ! -d "$DATA_DIR" ]; then
        print_warning "Data directory not found"
        return
    fi
    
    # Archive old reports before deletion
    mkdir -p "$ARCHIVE_DIR/reports"
    find "$DATA_DIR/reports" -type f -name "*.csv" -mtime +$REPORT_RETENTION_DAYS \
        -exec mv {} "$ARCHIVE_DIR/reports/" \; 2>/dev/null || true
    
    # Clean old metrics data
    find "$DATA_DIR/metrics" -type f -mtime +$DATA_RETENTION_DAYS -delete 2>/dev/null || true
    
    # Clean old health check data
    find "$DATA_DIR/health" -type f -mtime +7 -delete 2>/dev/null || true
    
    print_success "Old data files cleaned"
}

clean_docker_artifacts() {
    print_info "Checking for Docker artifacts..."
    
    if command -v docker &> /dev/null; then
        # Clean dangling images
        docker image prune -f 2>/dev/null || true
        
        # Clean stopped containers
        docker container prune -f 2>/dev/null || true
        
        # Clean unused volumes
        docker volume prune -f 2>/dev/null || true
        
        print_success "Docker artifacts cleaned"
    else
        print_info "Docker not installed, skipping"
    fi
}

clean_ib_gateway_logs() {
    print_info "Cleaning IB Gateway logs..."
    
    local ib_dir="$HOME/Jts"
    if [ -d "$ib_dir" ]; then
        # Clean IB logs older than 7 days
        find "$ib_dir" -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
        find "$ib_dir" -type f -name "*.txt" -mtime +7 -delete 2>/dev/null || true
        print_success "IB Gateway logs cleaned"
    else
        print_info "IB Gateway directory not found, skipping"
    fi
}

optimize_databases() {
    print_info "Optimizing database files..."
    
    # Find and optimize SQLite databases
    find "$SPYDER_HOME" -type f -name "*.db" -o -name "*.sqlite" | while read db; do
        if command -v sqlite3 &> /dev/null; then
            sqlite3 "$db" "VACUUM;" 2>/dev/null && \
                echo "  Optimized: $(basename "$db")"
        fi
    done
    
    print_success "Database optimization complete"
}

# ===============================================================================
# REPORT GENERATION
# ===============================================================================

generate_report() {
    local report_file="$LOG_DIR/cleanup_$(date +%Y%m%d_%H%M%S).log"
    
    {
        echo "SPYDER CLEANUP REPORT"
        echo "===================="
        echo "Date: $(date)"
        echo "Files Deleted: $FILES_DELETED"
        echo "Space Freed: $(numfmt --to=iec $SPACE_FREED 2>/dev/null || echo "${SPACE_FREED} bytes")"
        echo "Files Archived: $FILES_ARCHIVED"
        echo ""
        echo "Disk Usage After Cleanup:"
        df -h "$SPYDER_HOME"
        echo ""
        echo "Directory Sizes:"
        du -sh "$SPYDER_HOME"/* 2>/dev/null | sort -h
    } | tee "$report_file"
    
    print_success "Report saved to: $report_file"
}

# ===============================================================================
# INTERACTIVE MODE
# ===============================================================================

interactive_mode() {
    print_header
    echo ""
    echo "Select cleanup options:"
    echo "  1) Quick cleanup (logs and temp files)"
    echo "  2) Standard cleanup (logs, temp, cache)"
    echo "  3) Deep cleanup (everything including old data)"
    echo "  4) Custom selection"
    echo "  5) Exit"
    echo ""
    read -p "Choice [1-5]: " choice
    
    case $choice in
        1)
            clean_logs
            clean_temp_files
            ;;
        2)
            clean_logs
            clean_temp_files
            clean_python_cache
            ;;
        3)
            clean_logs
            clean_temp_files
            clean_python_cache
            clean_old_data
            clean_docker_artifacts
            clean_ib_gateway_logs
            optimize_databases
            ;;
        4)
            custom_selection
            ;;
        5)
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

custom_selection() {
    echo ""
    echo "Select items to clean (space-separated numbers):"
    echo "  1) Log files"
    echo "  2) Temporary files"
    echo "  3) Python cache"
    echo "  4) Old data files"
    echo "  5) Docker artifacts"
    echo "  6) IB Gateway logs"
    echo "  7) Optimize databases"
    echo ""
    read -p "Selections: " -a selections
    
    for sel in "${selections[@]}"; do
        case $sel in
            1) clean_logs ;;
            2) clean_temp_files ;;
            3) clean_python_cache ;;
            4) clean_old_data ;;
            5) clean_docker_artifacts ;;
            6) clean_ib_gateway_logs ;;
            7) optimize_databases ;;
            *) print_warning "Invalid selection: $sel" ;;
        esac
    done
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Check free space
    FREE_SPACE_GB=$(get_free_space_gb)
    if [ "$FREE_SPACE_GB" -lt "$MIN_FREE_SPACE_GB" ]; then
        print_warning "Low disk space: ${FREE_SPACE_GB}GB free"
        echo "Proceeding with aggressive cleanup..."
        LOG_RETENTION_DAYS=3
        DATA_RETENTION_DAYS=7
    fi
    
    # Parse arguments
    if [ "$1" == "--auto" ] || [ "$1" == "-a" ]; then
        print_header
        echo ""
        print_info "Running automatic cleanup..."
        clean_logs
        clean_temp_files
        clean_python_cache
        generate_report
    elif [ "$1" == "--deep" ] || [ "$1" == "-d" ]; then
        print_header
        echo ""
        print_info "Running deep cleanup..."
        clean_logs
        clean_temp_files
        clean_python_cache
        clean_old_data
        clean_docker_artifacts
        clean_ib_gateway_logs
        optimize_databases
        generate_report
    elif [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --auto, -a     Run automatic standard cleanup"
        echo "  --deep, -d     Run deep cleanup (all items)"
        echo "  --help, -h     Show this help message"
        echo ""
        echo "Without options, runs in interactive mode"
    else
        interactive_mode
        generate_report
    fi
    
    # Final disk space check
    echo ""
    print_info "Final disk usage:"
    df -h "$SPYDER_HOME" | grep -v Filesystem
    
    FREE_SPACE_AFTER=$(get_free_space_gb)
    SPACE_GAINED=$((FREE_SPACE_AFTER - FREE_SPACE_GB))
    if [ "$SPACE_GAINED" -gt 0 ]; then
        print_success "Freed ${SPACE_GAINED}GB of disk space!"
    fi
}

# Run main
main "$@"
