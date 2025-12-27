#!/bin/bash
# ==============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ50_ExportData.sh
# Group: Q (Scripts)
# Purpose: Wrapper script for data export operations (calls Python module)
# Author: Mohamed Talib
# Date Created: 2025-09-05
# Last Updated: 2025-09-05 Time: 15:45:00
#
# Description:
#     Backward compatibility wrapper that calls SpyderQ90_SystemUtilities.py
#     for data export operations. Supports multiple export formats including
#     CSV, JSON, Excel, and Parquet with date range filtering.
# ==============================================================================

# Set environment
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
PYTHON_MODULE="$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py"
EXPORT_DIR="$SPYDER_HOME/exports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo ""
    echo "=========================================="
    echo "SPYDER DATA EXPORT UTILITY"
    echo "=========================================="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --format FORMAT   Export format: csv|json|excel|parquet (default: csv)
    --start DATE      Start date (YYYY-MM-DD)
    --end DATE        End date (YYYY-MM-DD)
    --type TYPE       Data type: trades|positions|performance|all (default: all)
    --output FILE     Output filename (optional)
    --list            List recent exports
    --report          Generate performance report
    --help            Show this help message

Export Formats:
    csv       Comma-separated values (default)
    json      JavaScript Object Notation
    excel     Microsoft Excel format
    parquet   Apache Parquet (efficient columnar storage)

Data Types:
    trades       Trading history
    positions    Current and historical positions
    performance  Performance metrics and statistics
    all          Export all available data (default)

Examples:
    $0                                    # Export all data as CSV
    $0 --format json                      # Export all data as JSON
    $0 --format excel --type trades       # Export trades to Excel
    $0 --start 2025-01-01 --end 2025-01-31  # Export January data
    $0 --report                           # Generate performance report

EOF
}

list_exports() {
    echo -e "${BLUE}Recent Exports:${NC}"
    echo "----------------------------------------"
    
    if [ -d "$EXPORT_DIR" ]; then
        # List recent exports with details
        for export_file in $(ls -t "$EXPORT_DIR"/spyder_export_* 2>/dev/null | head -20); do
            if [ -f "$export_file" ]; then
                filename=$(basename "$export_file")
                size=$(du -h "$export_file" | cut -f1)
                modified=$(stat -c "%y" "$export_file" | cut -d' ' -f1,2 | cut -d'.' -f1)
                
                # Determine format from extension
                extension="${filename##*.}"
                
                echo "  $filename"
                echo "    Format: $extension | Size: $size | Date: $modified"
                echo ""
            fi
        done
        
        # Summary
        total_count=$(ls -1 "$EXPORT_DIR"/spyder_export_* 2>/dev/null | wc -l)
        
        if [ $total_count -gt 0 ]; then
            total_size=$(du -ch "$EXPORT_DIR"/spyder_export_* 2>/dev/null | tail -1 | cut -f1)
            echo "----------------------------------------"
            echo "Total: $total_count exports, $total_size"
        else
            echo "No exports found"
        fi
    else
        echo "Export directory not found"
    fi
}

generate_performance_report() {
    echo -e "${CYAN}Generating Performance Report...${NC}"
    echo ""
    
    # Call Python module to generate report
    python3 "$PYTHON_MODULE" report
    
    echo ""
    echo -e "${GREEN}Report generated${NC}"
    
    # Also export the data
    echo ""
    echo "Exporting performance data..."
    python3 "$PYTHON_MODULE" export --export-format csv
}

validate_date() {
    local date_str="$1"
    if [[ ! "$date_str" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        echo -e "${RED}Error: Invalid date format: $date_str${NC}"
        echo "Expected format: YYYY-MM-DD"
        return 1
    fi
    return 0
}

# ==============================================================================
# ARGUMENT PARSING
# ==============================================================================

ACTION="export"
EXPORT_FORMAT="csv"
START_DATE=""
END_DATE=""
DATA_TYPE="all"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --format)
            EXPORT_FORMAT="$2"
            shift 2
            ;;
        --start)
            START_DATE="$2"
            if ! validate_date "$START_DATE"; then
                exit 1
            fi
            shift 2
            ;;
        --end)
            END_DATE="$2"
            if ! validate_date "$END_DATE"; then
                exit 1
            fi
            shift 2
            ;;
        --type)
            DATA_TYPE="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --list)
            ACTION="list"
            shift
            ;;
        --report)
            ACTION="report"
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

# Create export directory if needed
mkdir -p "$EXPORT_DIR"

# Execute requested action
case $ACTION in
    export)
        # Validate export format
        if [[ ! "$EXPORT_FORMAT" =~ ^(csv|json|excel|parquet)$ ]]; then
            echo -e "${RED}Error: Invalid export format: $EXPORT_FORMAT${NC}"
            echo "Valid formats: csv, json, excel, parquet"
            exit 1
        fi
        
        echo "Export Configuration:"
        echo "  Format: $EXPORT_FORMAT"
        echo "  Data Type: $DATA_TYPE"
        
        if [ -n "$START_DATE" ]; then
            echo "  Start Date: $START_DATE"
        fi
        
        if [ -n "$END_DATE" ]; then
            echo "  End Date: $END_DATE"
        fi
        
        echo ""
        echo "Exporting data..."
        
        # Build Python command
        CMD="python3 $PYTHON_MODULE export --export-format $EXPORT_FORMAT"
        
        # Note: The current Python module doesn't support date parameters yet
        # This would need to be implemented in the Python module
        if [ -n "$START_DATE" ] || [ -n "$END_DATE" ]; then
            echo -e "${YELLOW}Note: Date filtering not yet implemented in Python module${NC}"
            echo "Exporting all available data..."
        fi
        
        # Execute export
        $CMD
        EXIT_CODE=$?
        
        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ Export completed successfully${NC}"
            
            # Show latest export
            latest_export=$(ls -t "$EXPORT_DIR"/spyder_export_* 2>/dev/null | head -1)
            if [ -f "$latest_export" ]; then
                size=$(du -h "$latest_export" | cut -f1)
                echo "Export file: $(basename "$latest_export") ($size)"
                echo "Location: $latest_export"
                
                # If output file specified, copy to that location
                if [ -n "$OUTPUT_FILE" ]; then
                    cp "$latest_export" "$OUTPUT_FILE"
                    echo "Copied to: $OUTPUT_FILE"
                fi
            fi
        else
            echo -e "${RED}✗ Export failed${NC}"
        fi
        ;;
        
    list)
        list_exports
        EXIT_CODE=0
        ;;
        
    report)
        generate_performance_report
        EXIT_CODE=$?
        ;;
esac

echo ""
echo "=========================================="

exit $EXIT_CODE