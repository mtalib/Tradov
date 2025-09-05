#!/bin/bash
# ==============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ41_Backup.sh
# Group: Q (Scripts)
# Purpose: Wrapper script for backup operations (calls Python module)
# Author: Mohamed Talib
# Date Created: 2025-09-05
# Last Updated: 2025-09-05 Time: 15:45:00
#
# Description:
#     Backward compatibility wrapper that calls SpyderQ90_SystemUtilities.py
#     for backup operations. Supports full, incremental, config-only, and
#     data-only backups with automatic rotation of old backups.
# ==============================================================================

# Set environment
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
PYTHON_MODULE="$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py"
BACKUP_DIR="$SPYDER_HOME/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo ""
    echo "=========================================="
    echo "SPYDER BACKUP UTILITY"
    echo "=========================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --type TYPE     Backup type: full|config|data|incremental (default: full)
    --restore ID    Restore from backup with given ID
    --list          List available backups
    --verify ID     Verify backup integrity
    --cleanup       Remove old backups (keep last 90 days)
    --dry-run       Show what would be done without doing it
    --help          Show this help message

Backup Types:
    full        Complete system backup (default)
    config      Configuration files only
    data        Database files only
    incremental Not yet implemented

Examples:
    $0                          # Create full backup
    $0 --type config            # Backup configs only
    $0 --type data              # Backup databases only
    $0 --list                   # Show available backups
    $0 --restore backup_id      # Restore specific backup
    $0 --cleanup                # Remove old backups

EOF
}

list_backups() {
    echo -e "${BLUE}Available Backups:${NC}"
    echo "----------------------------------------"
    
    if [ -d "$BACKUP_DIR" ]; then
        # Find and list backups with details
        for backup in "$BACKUP_DIR"/spyder_backup_*.tar.gz; do
            if [ -f "$backup" ]; then
                filename=$(basename "$backup")
                size=$(du -h "$backup" | cut -f1)
                modified=$(stat -c "%y" "$backup" | cut -d' ' -f1,2 | cut -d'.' -f1)
                
                # Extract type from filename
                backup_type=$(echo "$filename" | sed -n 's/spyder_backup_\([^_]*\)_.*/\1/p')
                
                echo "  $filename"
                echo "    Type: $backup_type | Size: $size | Date: $modified"
                echo ""
            fi
        done
        
        # Summary
        total_count=$(ls -1 "$BACKUP_DIR"/spyder_backup_*.tar.gz 2>/dev/null | wc -l)
        total_size=$(du -ch "$BACKUP_DIR"/spyder_backup_*.tar.gz 2>/dev/null | tail -1 | cut -f1)
        
        echo "----------------------------------------"
        echo "Total: $total_count backups, $total_size"
    else
        echo "No backup directory found"
    fi
}

verify_backup() {
    local backup_id="$1"
    local backup_file="$BACKUP_DIR/${backup_id}.tar.gz"
    
    if [ ! -f "$backup_file" ]; then
        # Try with full name if not found
        backup_file="$BACKUP_DIR/${backup_id}"
        if [ ! -f "$backup_file" ]; then
            echo -e "${RED}Error: Backup not found: $backup_id${NC}"
            return 1
        fi
    fi
    
    echo "Verifying backup: $(basename "$backup_file")"
    
    # Test archive integrity
    if tar -tzf "$backup_file" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Archive integrity: OK${NC}"
        
        # Show contents summary
        echo ""
        echo "Backup contents:"
        tar -tzf "$backup_file" | head -20
        
        file_count=$(tar -tzf "$backup_file" | wc -l)
        echo ""
        echo "Total files: $file_count"
        
        # Check for manifest
        if tar -tzf "$backup_file" | grep -q "manifest.json"; then
            echo -e "${GREEN}✓ Manifest found${NC}"
            
            # Extract and show manifest
            echo ""
            echo "Manifest content:"
            tar -xzOf "$backup_file" manifest.json 2>/dev/null | python3 -m json.tool | head -20
        else
            echo -e "${YELLOW}⚠ No manifest found${NC}"
        fi
        
        return 0
    else
        echo -e "${RED}✗ Archive is corrupted${NC}"
        return 1
    fi
}

# ==============================================================================
# ARGUMENT PARSING
# ==============================================================================

ACTION="backup"
BACKUP_TYPE="full"
RESTORE_ID=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --type)
            BACKUP_TYPE="$2"
            shift 2
            ;;
        --restore)
            ACTION="restore"
            RESTORE_ID="$2"
            shift 2
            ;;
        --list)
            ACTION="list"
            shift
            ;;
        --verify)
            ACTION="verify"
            RESTORE_ID="$2"
            shift 2
            ;;
        --cleanup)
            ACTION="cleanup"
            shift
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

print_header

# Check if Python module exists
if [ ! -f "$PYTHON_MODULE" ]; then
    echo -e "${RED}Error: Python module not found: $PYTHON_MODULE${NC}"
    echo "Please ensure SpyderQ90_SystemUtilities.py is installed"
    exit 1
fi

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Execute requested action
case $ACTION in
    backup)
        echo "Creating $BACKUP_TYPE backup..."
        echo ""
        
        # Check disk space first
        available_space=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
        echo "Available disk space: $(numfmt --to=iec --from-unit=1K $available_space)"
        echo ""
        
        # Create backup
        python3 "$PYTHON_MODULE" backup --backup-type "$BACKUP_TYPE" $DRY_RUN
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Backup completed successfully${NC}"
            
            # Show latest backup
            latest_backup=$(ls -t "$BACKUP_DIR"/spyder_backup_*.tar.gz 2>/dev/null | head -1)
            if [ -f "$latest_backup" ]; then
                size=$(du -h "$latest_backup" | cut -f1)
                echo "Latest backup: $(basename "$latest_backup") ($size)"
            fi
        else
            echo -e "${RED}✗ Backup failed${NC}"
        fi
        ;;
        
    restore)
        if [ -z "$RESTORE_ID" ]; then
            echo -e "${RED}Error: No backup ID specified${NC}"
            echo "Use --list to see available backups"
            exit 1
        fi
        
        echo "Restoring from backup: $RESTORE_ID"
        echo -e "${YELLOW}Warning: This will overwrite existing files${NC}"
        read -p "Continue? (y/N): " -n 1 -r
        echo ""
        
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 "$PYTHON_MODULE" restore --backup-id "$RESTORE_ID"
            EXIT_CODE=$?
            
            if [ $EXIT_CODE -eq 0 ]; then
                echo -e "${GREEN}✓ Restore completed successfully${NC}"
            else
                echo -e "${RED}✗ Restore failed${NC}"
            fi
        else
            echo "Restore cancelled"
            EXIT_CODE=0
        fi
        ;;
        
    list)
        list_backups
        EXIT_CODE=0
        ;;
        
    verify)
        if [ -z "$RESTORE_ID" ]; then
            echo -e "${RED}Error: No backup ID specified${NC}"
            exit 1
        fi
        verify_backup "$RESTORE_ID"
        EXIT_CODE=$?
        ;;
        
    cleanup)
        echo "Cleaning old backups (keeping last 90 days)..."
        python3 "$PYTHON_MODULE" cleanup --retention-days 90 $DRY_RUN
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo -e "${GREEN}✓ Cleanup completed${NC}"
        else
            echo -e "${RED}✗ Cleanup failed${NC}"
        fi
        ;;
esac

echo ""
echo "=========================================="

exit $EXIT_CODE