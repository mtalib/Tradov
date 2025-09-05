#!/bin/bash
# ==============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ40_Cleanup.sh
# Group: Q (Scripts)
# Purpose: Wrapper script for cleanup operations (calls Python module)
# Author: Mohamed Talib
# Date Created: 2025-09-05
# Last Updated: 2025-09-05 Time: 15:45:00
#
# Description:
#     Backward compatibility wrapper that calls SpyderQ90_SystemUtilities.py
#     for cleanup operations. This maintains compatibility with existing scripts
#     and cron jobs during the transition to Python-based utilities.
# ==============================================================================

# Set environment
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
PYTHON_MODULE="$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo ""
    echo "=========================================="
    echo "SPYDER CLEANUP UTILITY"
    echo "=========================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --all           Perform complete cleanup (default)
    --logs          Clean only log files
    --temp          Clean only temp files
    --backups       Clean only old backups
    --retention N   Keep files from last N days (default: 30)
    --dry-run       Show what would be deleted without deleting
    --help          Show this help message

Examples:
    $0                     # Full cleanup with 30-day retention
    $0 --retention 7       # Full cleanup keeping last 7 days
    $0 --logs --dry-run    # Show what logs would be deleted
    $0 --temp              # Clean only temp files

EOF
}

# ==============================================================================
# ARGUMENT PARSING
# ==============================================================================

ACTION="cleanup"
RETENTION_DAYS=30
DRY_RUN=""
SPECIFIC_TARGET=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            ACTION="cleanup"
            shift
            ;;
        --logs)
            SPECIFIC_TARGET="logs"
            shift
            ;;
        --temp)
            SPECIFIC_TARGET="temp"
            shift
            ;;
        --backups)
            SPECIFIC_TARGET="backups"
            shift
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
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

# Check Python availability
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Determine what to clean
if [ -n "$SPECIFIC_TARGET" ]; then
    echo -e "${YELLOW}Note: Specific cleanup targets not yet implemented in wrapper${NC}"
    echo "Performing full cleanup instead..."
fi

# Execute cleanup
echo "Starting cleanup operations..."
echo "Retention period: $RETENTION_DAYS days"

if [ -n "$DRY_RUN" ]; then
    echo -e "${YELLOW}DRY RUN MODE - No files will be deleted${NC}"
fi

echo ""

# Call Python module
python3 "$PYTHON_MODULE" cleanup \
    --retention-days "$RETENTION_DAYS" \
    $DRY_RUN

EXIT_CODE=$?

# Report results
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Cleanup completed successfully${NC}"
    
    # Show disk space
    echo ""
    echo "Current disk usage:"
    df -h "$SPYDER_HOME" | grep -v "Filesystem"
else
    echo -e "${RED}✗ Cleanup failed with exit code: $EXIT_CODE${NC}"
fi

echo ""
echo "=========================================="

exit $EXIT_CODE