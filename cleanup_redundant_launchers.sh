#!/bin/bash
# ==============================================================================
# SPYDER - Cleanup Redundant Launcher Scripts
#
# Script: cleanup_redundant_launchers.sh
# Purpose: Safely delete redundant launcher files that have been archived
# Author: Mohamed Talib
# Date Created: 2025-09-05
# 
# Description:
#     This script removes redundant launcher files from the Spyder directory
#     after confirming they have been archived. Includes safety checks and
#     dry-run option.
# ==============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set the Spyder home directory
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
ARCHIVE_DIR="$SPYDER_HOME/archived"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# List of files to delete
FILES_TO_DELETE=(
    "fast_launcher.py"
    "bulletproof-launcher.py"
    "simple-dock-launcher.py"
    "spyder_simple_launcher.py"
    "start_spyder.py"
    "launch_terminal.py"
    "launch_spyder.sh"
    "launch_spyder_gui.sh"
    "launch_spyder_wayland.sh"
    "launch_dashboard.sh"
    "launch_dashboard_with_real_data.sh"
    "launch_trading_dashboard.sh"
    "spyder-dashboard-launcher.sh"
    "spyder_debug_launcher.sh"
    "advanced-wayland-launcher.py"
    "dock-launcher.sh"
)

# Additional temporary files to clean
TEMP_FILES_TO_DELETE=(
    "temp_detailed_ibapi_test.py"
    "temp_ibapi_only_test.py"
    "temp_ib_process_diagnostic.py"
    "spyder_ib_test.log"
    "spyder_master.log"
    "events.db"
    "dashboard_integration_report.json"
    "ib_insync_scan_report.json"
)

# Platform-specific files to clean
PLATFORM_FILES_TO_DELETE=(
    "claude-flow"
    "claude-flow.bat"
    "claude-flow.ps1"
    "claude-flow.config.json"
    "fix_wayland_display.sh"
)

# Wrapper files to clean
WRAPPER_FILES_TO_DELETE=(
    "spyder_dashboard_wrapper.sh"
    "spyder_live_wrapper.sh"
    "spyder_paper_wrapper.sh"
    "spyder_status_wrapper.sh"
)

# Desktop/Icon files to clean
DESKTOP_FILES_TO_DELETE=(
    "spyder_desktop_launcher.txt"
    "spyder_desktop_cleanup.sh"
    "spyder-trading.desktop.backup"
    "install-spy_icon.txt"
    "update_icon_for_dashboard.sh"
)

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo ""
    echo "=============================================="
    echo "SPYDER REDUNDANT FILES CLEANUP"
    echo "=============================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Directory: $SPYDER_HOME"
    echo ""
}

check_archive_exists() {
    if [ ! -d "$ARCHIVE_DIR" ]; then
        echo -e "${RED}Warning: Archive directory not found at $ARCHIVE_DIR${NC}"
        echo "Please ensure files are archived before deletion."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✓ Archive directory found${NC}"
    fi
}

count_files() {
    local count=0
    local found_files=()
    
    # Check all file arrays
    for file in "${FILES_TO_DELETE[@]}" "${TEMP_FILES_TO_DELETE[@]}" "${PLATFORM_FILES_TO_DELETE[@]}" "${WRAPPER_FILES_TO_DELETE[@]}" "${DESKTOP_FILES_TO_DELETE[@]}"; do
        if [ -f "$SPYDER_HOME/$file" ]; then
            ((count++))
            found_files+=("$file")
        fi
    done
    
    echo "$count"
    if [ $count -gt 0 ]; then
        echo -e "${YELLOW}Found $count files to delete:${NC}"
        for file in "${found_files[@]}"; do
            size=$(du -h "$SPYDER_HOME/$file" 2>/dev/null | cut -f1)
            echo "  • $file ($size)"
        done
    else
        echo -e "${GREEN}No redundant files found to delete${NC}"
    fi
}

create_final_backup() {
    echo -e "${BLUE}Creating final backup before deletion...${NC}"
    
    local backup_dir="$SPYDER_HOME/archived/final_backup_$TIMESTAMP"
    mkdir -p "$backup_dir"
    
    local backed_up=0
    for file in "${FILES_TO_DELETE[@]}" "${TEMP_FILES_TO_DELETE[@]}" "${PLATFORM_FILES_TO_DELETE[@]}" "${WRAPPER_FILES_TO_DELETE[@]}" "${DESKTOP_FILES_TO_DELETE[@]}"; do
        if [ -f "$SPYDER_HOME/$file" ]; then
            cp "$SPYDER_HOME/$file" "$backup_dir/" 2>/dev/null && ((backed_up++))
        fi
    done
    
    if [ $backed_up -gt 0 ]; then
        echo -e "${GREEN}✓ Backed up $backed_up files to $backup_dir${NC}"
    fi
}

delete_files() {
    local dry_run=$1
    local deleted=0
    local failed=0
    
    echo ""
    echo "Starting deletion process..."
    echo "------------------------------"
    
    # Function to delete a single file
    delete_file() {
        local file=$1
        local category=$2
        
        if [ -f "$SPYDER_HOME/$file" ]; then
            if [ "$dry_run" = true ]; then
                echo -e "${YELLOW}[DRY RUN]${NC} Would delete: $file ${BLUE}[$category]${NC}"
                ((deleted++))
            else
                if rm "$SPYDER_HOME/$file" 2>/dev/null; then
                    echo -e "${GREEN}✓${NC} Deleted: $file ${BLUE}[$category]${NC}"
                    ((deleted++))
                else
                    echo -e "${RED}✗${NC} Failed to delete: $file"
                    ((failed++))
                fi
            fi
        fi
    }
    
    # Delete launcher files
    echo -e "\n${BLUE}Cleaning launcher files...${NC}"
    for file in "${FILES_TO_DELETE[@]}"; do
        delete_file "$file" "launcher"
    done
    
    # Delete temporary files
    echo -e "\n${BLUE}Cleaning temporary files...${NC}"
    for file in "${TEMP_FILES_TO_DELETE[@]}"; do
        delete_file "$file" "temp"
    done
    
    # Delete platform-specific files
    echo -e "\n${BLUE}Cleaning platform-specific files...${NC}"
    for file in "${PLATFORM_FILES_TO_DELETE[@]}"; do
        delete_file "$file" "platform"
    done
    
    # Delete wrapper files
    echo -e "\n${BLUE}Cleaning wrapper files...${NC}"
    for file in "${WRAPPER_FILES_TO_DELETE[@]}"; do
        delete_file "$file" "wrapper"
    done
    
    # Delete desktop/icon files
    echo -e "\n${BLUE}Cleaning desktop/icon files...${NC}"
    for file in "${DESKTOP_FILES_TO_DELETE[@]}"; do
        delete_file "$file" "desktop"
    done
    
    echo ""
    echo "------------------------------"
    if [ "$dry_run" = true ]; then
        echo -e "${YELLOW}DRY RUN COMPLETE: Would delete $deleted files${NC}"
    else
        echo -e "${GREEN}CLEANUP COMPLETE: Deleted $deleted files${NC}"
        if [ $failed -gt 0 ]; then
            echo -e "${RED}Failed to delete $failed files${NC}"
        fi
    fi
}

show_disk_space() {
    echo ""
    echo "Disk space information:"
    echo "----------------------"
    df -h "$SPYDER_HOME" | grep -v Filesystem
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    print_header
    
    # Parse arguments
    DRY_RUN=false
    SKIP_BACKUP=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                echo -e "${YELLOW}DRY RUN MODE - No files will be deleted${NC}"
                shift
                ;;
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --dry-run      Show what would be deleted without deleting"
                echo "  --skip-backup  Skip creating final backup"
                echo "  --help         Show this help message"
                echo ""
                echo "This script deletes redundant launcher and temporary files"
                echo "from the Spyder directory after confirming they are archived."
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                exit 1
                ;;
        esac
    done
    
    # Change to Spyder directory
    cd "$SPYDER_HOME" || {
        echo -e "${RED}Error: Cannot access $SPYDER_HOME${NC}"
        exit 1
    }
    
    # Check if archive exists
    check_archive_exists
    
    # Count files to be deleted
    echo ""
    file_count=$(count_files | head -1)
    
    if [ "$file_count" -eq 0 ]; then
        echo -e "${GREEN}✓ No redundant files to delete. Directory is clean!${NC}"
        show_disk_space
        exit 0
    fi
    
    # Show what will be deleted
    count_files | tail -n +2
    
    # Confirm deletion
    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo -e "${YELLOW}⚠ WARNING: This will permanently delete $file_count files${NC}"
        echo "Make sure you have verified that:"
        echo "  1. Files are properly archived"
        echo "  2. Your system works without these files"
        echo "  3. No active processes are using these files"
        echo ""
        read -p "Are you sure you want to delete these files? (yes/N): " -r
        
        if [[ ! "$REPLY" == "yes" ]]; then
            echo -e "${YELLOW}Deletion cancelled${NC}"
            exit 0
        fi
        
        # Create final backup unless skipped
        if [ "$SKIP_BACKUP" = false ]; then
            create_final_backup
        fi
    fi
    
    # Delete files
    delete_files $DRY_RUN
    
    # Show disk space
    show_disk_space
    
    echo ""
    echo "=============================================="
    echo -e "${GREEN}Cleanup script completed${NC}"
    echo "=============================================="
}

# Run main function
main "$@"
