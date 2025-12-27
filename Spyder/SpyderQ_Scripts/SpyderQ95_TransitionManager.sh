#!/bin/bash
# ==============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ95_TransitionManager.sh
# Group: Q (Scripts)
# Purpose: Manage transition from shell scripts to Python utilities
# Author: Mohamed Talib
# Date Created: 2025-09-05
# Last Updated: 2025-09-05 Time: 16:00:00
#
# Description:
#     This script manages the transition from individual shell scripts to the
#     consolidated Python utility module. It creates backups, installs wrapper
#     scripts, updates references, and provides rollback capabilities.
# ==============================================================================

# Set environment
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
ARCHIVE_DIR="$SCRIPTS_DIR/archived"
BACKUP_DIR="$SCRIPTS_DIR/transition_backup_$(date +%Y%m%d_%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Track operations
OPERATIONS_LOG="$SCRIPTS_DIR/transition_log_$(date +%Y%m%d_%H%M%S).txt"

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    cat << EOF

==========================================
SPYDER Q-SERIES TRANSITION MANAGER
==========================================
Version: 1.0
Date: $(date '+%Y-%m-%d %H:%M:%S')

This tool will help transition from individual
shell scripts to the consolidated Python module.

EOF
}

log_operation() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$OPERATIONS_LOG"
    echo "$message"
}

check_prerequisites() {
    local errors=0
    
    echo -e "${CYAN}Checking prerequisites...${NC}"
    echo ""
    
    # Check Python 3
    if command -v python3 &> /dev/null; then
        python_version=$(python3 --version 2>&1 | awk '{print $2}')
        echo -e "${GREEN}✓${NC} Python 3 installed: $python_version"
    else
        echo -e "${RED}✗${NC} Python 3 not found"
        ((errors++))
    fi
    
    # Check if new Python module exists
    if [ -f "$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py" ]; then
        echo -e "${GREEN}✓${NC} SpyderQ90_SystemUtilities.py found"
    else
        echo -e "${RED}✗${NC} SpyderQ90_SystemUtilities.py not found"
        ((errors++))
    fi
    
    # Check for required Python packages
    for package in pandas sqlite3; do
        if python3 -c "import $package" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} Python package '$package' available"
        else
            echo -e "${YELLOW}⚠${NC} Python package '$package' not found (may need installation)"
        fi
    done
    
    # Check disk space
    available_space=$(df "$SCRIPTS_DIR" | awk 'NR==2 {print $4}')
    available_mb=$((available_space / 1024))
    if [ $available_mb -gt 100 ]; then
        echo -e "${GREEN}✓${NC} Sufficient disk space: ${available_mb}MB available"
    else
        echo -e "${YELLOW}⚠${NC} Low disk space: ${available_mb}MB available"
    fi
    
    echo ""
    
    if [ $errors -gt 0 ]; then
        echo -e "${RED}Prerequisites check failed with $errors error(s)${NC}"
        return 1
    else
        echo -e "${GREEN}All prerequisites met${NC}"
        return 0
    fi
}

create_backup() {
    echo -e "${CYAN}Creating backup of existing scripts...${NC}"
    
    mkdir -p "$BACKUP_DIR"
    log_operation "Created backup directory: $BACKUP_DIR"
    
    # List of scripts to backup
    local scripts_to_backup=(
        "SpyderQ40_Cleanup.sh"
        "SpyderQ41_Backup.sh"
        "SpyderQ50_ExportData.sh"
        "SpyderQ30_Diagnostics.sh"
        "SpyderQ20_Status.sh"
        "SpyderQ21_Monitor.sh"
        "SpyderQ22_CheckIBStatus.py"
    )
    
    local backed_up=0
    for script in "${scripts_to_backup[@]}"; do
        if [ -f "$SCRIPTS_DIR/$script" ]; then
            cp "$SCRIPTS_DIR/$script" "$BACKUP_DIR/"
            echo "  Backed up: $script"
            log_operation "Backed up: $script"
            ((backed_up++))
        fi
    done
    
    echo -e "${GREEN}✓ Backed up $backed_up scripts${NC}"
    echo ""
}

install_wrapper_scripts() {
    echo -e "${CYAN}Installing wrapper scripts...${NC}"
    echo ""
    
    local installed=0
    
    # Check if wrapper scripts exist (they should be created already)
    for wrapper in SpyderQ40_Cleanup.sh SpyderQ41_Backup.sh SpyderQ50_ExportData.sh; do
        if [ -f "$SCRIPTS_DIR/${wrapper}.new" ]; then
            # Move old script if it exists
            if [ -f "$SCRIPTS_DIR/$wrapper" ]; then
                mv "$SCRIPTS_DIR/$wrapper" "$SCRIPTS_DIR/${wrapper}.old"
                log_operation "Renamed old $wrapper to ${wrapper}.old"
            fi
            
            # Install new wrapper
            mv "$SCRIPTS_DIR/${wrapper}.new" "$SCRIPTS_DIR/$wrapper"
            chmod +x "$SCRIPTS_DIR/$wrapper"
            echo -e "  ${GREEN}✓${NC} Installed: $wrapper"
            log_operation "Installed wrapper: $wrapper"
            ((installed++))
        else
            echo -e "  ${YELLOW}⚠${NC} Wrapper not found: ${wrapper}.new"
            echo "      Please ensure wrapper scripts are created first"
        fi
    done
    
    echo ""
    echo "Installed $installed wrapper scripts"
    echo ""
}

archive_old_scripts() {
    echo -e "${CYAN}Archiving deprecated scripts...${NC}"
    echo ""
    
    mkdir -p "$ARCHIVE_DIR"
    
    # Scripts to archive (one-time setup scripts)
    local scripts_to_archive=(
        "SpyderQ01_Setup.sh"
        "SpyderQ02_Dependencies.sh"
        "SpyderQ03_InstallGateway.sh"
        "SpyderQ05_InstallCommands.sh"
        "SpyderQ06_MigrateToQSeries.sh"
        "SpyderQ35_VerifySystem.sh"
        "SpyderQ80_VerifyDashboardIntegration.py"
    )
    
    local archived=0
    for script in "${scripts_to_archive[@]}"; do
        if [ -f "$SCRIPTS_DIR/$script" ]; then
            mv "$SCRIPTS_DIR/$script" "$ARCHIVE_DIR/"
            echo "  Archived: $script"
            log_operation "Archived: $script to $ARCHIVE_DIR"
            ((archived++))
        fi
    done
    
    echo -e "${GREEN}✓ Archived $archived scripts${NC}"
    echo ""
}

update_cron_jobs() {
    echo -e "${CYAN}Checking for cron jobs to update...${NC}"
    echo ""
    
    # Check if user has cron jobs
    if crontab -l 2>/dev/null | grep -q "SpyderQ"; then
        echo "Found Spyder-related cron jobs:"
        echo ""
        crontab -l | grep "SpyderQ"
        echo ""
        echo -e "${YELLOW}Please update your cron jobs to use the new Python module:${NC}"
        echo ""
        echo "Old format:"
        echo "  0 2 * * * $SCRIPTS_DIR/SpyderQ40_Cleanup.sh"
        echo ""
        echo "New format:"
        echo "  0 2 * * * /usr/bin/python3 $SCRIPTS_DIR/SpyderQ90_SystemUtilities.py daily"
        echo ""
        echo "Would you like to edit your crontab now? (y/N): "
        read -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            crontab -e
        fi
    else
        echo "No Spyder-related cron jobs found"
    fi
    echo ""
}

test_new_system() {
    echo -e "${CYAN}Testing new system...${NC}"
    echo ""
    
    local tests_passed=0
    local tests_failed=0
    
    # Test 1: Python module import
    echo -n "Testing Python module import... "
    if python3 -c "import sys; sys.path.insert(0, '$SPYDER_HOME'); from SpyderQ_Scripts.SpyderQ90_SystemUtilities import SystemUtilities" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((tests_passed++))
    else
        echo -e "${RED}✗${NC}"
        ((tests_failed++))
    fi
    
    # Test 2: Generate report
    echo -n "Testing report generation... "
    if python3 "$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py" report > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((tests_passed++))
    else
        echo -e "${RED}✗${NC}"
        ((tests_failed++))
    fi
    
    # Test 3: Dry run cleanup
    echo -n "Testing cleanup (dry run)... "
    if python3 "$SCRIPTS_DIR/SpyderQ90_SystemUtilities.py" cleanup --dry-run > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((tests_passed++))
    else
        echo -e "${RED}✗${NC}"
        ((tests_failed++))
    fi
    
    echo ""
    echo "Test Results: $tests_passed passed, $tests_failed failed"
    echo ""
    
    if [ $tests_failed -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${YELLOW}Some tests failed. Please check the configuration.${NC}"
        return 1
    fi
}

create_rollback_script() {
    echo -e "${CYAN}Creating rollback script...${NC}"
    
    cat > "$BACKUP_DIR/rollback.sh" << 'EOF'
#!/bin/bash
# Rollback script for Q-Series transition

BACKUP_DIR="$(dirname "$0")"
SCRIPTS_DIR="$(dirname "$BACKUP_DIR")"

echo "Rolling back Q-Series transition..."

# Restore backed up scripts
for script in "$BACKUP_DIR"/*.sh "$BACKUP_DIR"/*.py; do
    if [ -f "$script" ]; then
        filename=$(basename "$script")
        cp "$script" "$SCRIPTS_DIR/$filename"
        echo "Restored: $filename"
    fi
done

# Remove wrapper scripts
rm -f "$SCRIPTS_DIR/SpyderQ40_Cleanup.sh"
rm -f "$SCRIPTS_DIR/SpyderQ41_Backup.sh"
rm -f "$SCRIPTS_DIR/SpyderQ50_ExportData.sh"

# Restore old versions if they exist
for old_script in "$SCRIPTS_DIR"/*.sh.old; do
    if [ -f "$old_script" ]; then
        original="${old_script%.old}"
        mv "$old_script" "$original"
        echo "Restored: $(basename "$original")"
    fi
done

echo "Rollback complete!"
EOF
    
    chmod +x "$BACKUP_DIR/rollback.sh"
    echo -e "${GREEN}✓ Created rollback script: $BACKUP_DIR/rollback.sh${NC}"
    echo ""
}

print_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}TRANSITION COMPLETE${NC}"
    echo "=========================================="
    echo ""
    echo "Summary:"
    echo "  • Backup location: $BACKUP_DIR"
    echo "  • Operations log: $OPERATIONS_LOG"
    echo "  • Rollback script: $BACKUP_DIR/rollback.sh"
    echo ""
    echo "Next Steps:"
    echo "  1. Test the new wrapper scripts:"
    echo "     $SCRIPTS_DIR/SpyderQ40_Cleanup.sh --help"
    echo "     $SCRIPTS_DIR/SpyderQ41_Backup.sh --help"
    echo "     $SCRIPTS_DIR/SpyderQ50_ExportData.sh --help"
    echo ""
    echo "  2. Update any custom scripts that reference old scripts"
    echo ""
    echo "  3. Update cron jobs if necessary"
    echo ""
    echo "  4. If issues arise, rollback with:"
    echo "     $BACKUP_DIR/rollback.sh"
    echo ""
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    print_header
    
    # Initialize log
    echo "Transition started at $(date)" > "$OPERATIONS_LOG"
    
    # Step 1: Check prerequisites
    if ! check_prerequisites; then
        echo -e "${RED}Please fix prerequisites before continuing${NC}"
        exit 1
    fi
    
    # Confirmation
    echo ""
    echo -e "${YELLOW}This will transition your Q-Series scripts to use the new Python module.${NC}"
    echo "A complete backup will be created first."
    echo ""
    read -p "Continue with transition? (y/N): " -n 1 -r
    echo ""
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_operation "Transition cancelled by user"
        echo "Transition cancelled"
        exit 0
    fi
    
    # Step 2: Create backup
    create_backup
    
    # Step 3: Create rollback script
    create_rollback_script
    
    # Step 4: Install wrapper scripts
    echo -e "${YELLOW}Note: Wrapper scripts need to be created first${NC}"
    echo "Please save the wrapper scripts from the previous artifacts as:"
    echo "  • SpyderQ40_Cleanup.sh"
    echo "  • SpyderQ41_Backup.sh"
    echo "  • SpyderQ50_ExportData.sh"
    echo ""
    read -p "Have you saved the wrapper scripts? (y/N): " -n 1 -r
    echo ""
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Make wrapper scripts executable
        chmod +x "$SCRIPTS_DIR/SpyderQ40_Cleanup.sh" 2>/dev/null
        chmod +x "$SCRIPTS_DIR/SpyderQ41_Backup.sh" 2>/dev/null
        chmod +x "$SCRIPTS_DIR/SpyderQ50_ExportData.sh" 2>/dev/null
        echo -e "${GREEN}✓ Wrapper scripts ready${NC}"
    fi
    
    # Step 5: Archive old scripts (optional)
    echo ""
    read -p "Archive one-time setup scripts? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        archive_old_scripts
    fi
    
    # Step 6: Update cron jobs
    update_cron_jobs
    
    # Step 7: Test new system
    test_new_system
    
    # Step 8: Print summary
    print_summary
    
    log_operation "Transition completed successfully"
}

# Handle arguments
case "${1:-}" in
    --rollback)
        if [ -d "$SCRIPTS_DIR/transition_backup_"* ]; then
            latest_backup=$(ls -dt "$SCRIPTS_DIR/transition_backup_"* | head -1)
            if [ -f "$latest_backup/rollback.sh" ]; then
                echo "Executing rollback from: $latest_backup"
                exec "$latest_backup/rollback.sh"
            else
                echo -e "${RED}Rollback script not found${NC}"
                exit 1
            fi
        else
            echo -e "${RED}No backup found for rollback${NC}"
            exit 1
        fi
        ;;
    --help|-h)
        echo "Usage: $0 [--rollback|--help]"
        echo ""
        echo "Options:"
        echo "  --rollback  Rollback to previous configuration"
        echo "  --help      Show this help message"
        exit 0
        ;;
    *)
        main
        ;;
esac