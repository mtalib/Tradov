#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: SpyderQ06_MigrateToQSeries.sh
# Group: Q (Scripts/Setup)
# Purpose: Automatically migrate existing scripts to Q-series structure
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:30:00
#
# Description:
#     Intelligently migrates existing Spyder scripts to the new Q-series naming
#     convention. Creates backups, updates references, and verifies the migration.
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
SCRIPTS_DIR="$SPYDER_HOME/SpyderQ_Scripts"
BACKUP_DIR="$SPYDER_HOME/backup/pre-migration-$(date +%Y%m%d_%H%M%S)"
MIGRATION_LOG="$SPYDER_HOME/logs/migration.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Migration mapping
declare -A MIGRATION_MAP=(
    # Installation scripts
    ["install.sh"]="SpyderQ02_Dependencies.sh"
    ["install_fresh_gateway.sh"]="SpyderQ03_InstallGateway.sh"
    ["setup_watchdog_service.sh"]="SpyderQ04_SetupWatchdog.sh"
    
    # Start/Stop scripts
    ["start_multi_client.py"]="SpyderQ12_StartMultiClient.py"
    ["start_real_gateway.py"]="SpyderQ13_StartRealGateway.py"
    ["spyder_launcher.py"]="SpyderQ14_MainLauncher.py"
    ["spyder.sh"]="SpyderQ15_SpyderLegacy.sh"
    
    # Monitoring scripts
    ["check_ib_status.py"]="SpyderQ22_CheckIBStatus.py"
    ["dashboard_qt_timer.py"]="SpyderQ23_DashboardTimer.py"
    ["ib_production_watchdog.py"]="SpyderQ24_ProductionWatchdog.py"
    
    # Testing scripts
    ["spyder_integration_test_suite.py"]="SpyderQ31_IntegrationTestSuite.py"
    ["simple_ib_test.py"]="SpyderQ32_SimpleIBTest.py"
    
    # Maintenance scripts
    ["fix_b07.py"]="SpyderQ40_FixB07.py"
    ["fix_time_sync.sh"]="SpyderQ41_TimeSync.sh"
    ["integration-fixes.sh"]="SpyderQ42_IntegrationFixes.sh"
    
    # Service files
    ["ib-watchdog.service"]="SpyderQ72_IBWatchdog.service"
    ["ib_watchdog_service.txt"]="SpyderQ73_IBWatchdogTemplate.service"
)

# Track migration results
declare -a MIGRATED=()
declare -a SKIPPED=()
declare -a FAILED=()
declare -a NEW_SCRIPTS=()

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  SPYDER Q-SERIES MIGRATION TOOL${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1" >> "$MIGRATION_LOG"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >> "$MIGRATION_LOG"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1" >> "$MIGRATION_LOG"
}

print_info() {
    echo -e "${CYAN}[i]${NC} $1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1" >> "$MIGRATION_LOG"
}

# ===============================================================================
# BACKUP FUNCTIONS
# ===============================================================================

create_backup() {
    print_info "Creating backup of current scripts..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup scripts directory
    if [ -d "$SCRIPTS_DIR" ]; then
        cp -r "$SCRIPTS_DIR" "$BACKUP_DIR/scripts_backup"
        print_success "Scripts backed up to $BACKUP_DIR"
    fi
    
    # Backup service files
    if [ -d "$SPYDER_HOME/services" ]; then
        cp -r "$SPYDER_HOME/services" "$BACKUP_DIR/services_backup"
        print_success "Services backed up"
    fi
    
    # Create restore script
    cat > "$BACKUP_DIR/restore.sh" << 'EOF'
#!/bin/bash
# Restore script for pre-migration state
echo "Restoring from backup..."
BACKUP_DIR="$(dirname "$0")"
SPYDER_HOME="$(dirname "$(dirname "$BACKUP_DIR")")"

if [ -d "$BACKUP_DIR/scripts_backup" ]; then
    rm -rf "$SPYDER_HOME/scripts"
    cp -r "$BACKUP_DIR/scripts_backup" "$SPYDER_HOME/scripts"
    echo "Scripts restored"
fi

if [ -d "$BACKUP_DIR/services_backup" ]; then
    rm -rf "$SPYDER_HOME/services"
    cp -r "$BACKUP_DIR/services_backup" "$SPYDER_HOME/services"
    echo "Services restored"
fi

echo "Restore complete!"
EOF
    chmod +x "$BACKUP_DIR/restore.sh"
    print_success "Restore script created at $BACKUP_DIR/restore.sh"
}

# ===============================================================================
# MIGRATION FUNCTIONS
# ===============================================================================

migrate_file() {
    local old_name="$1"
    local new_name="$2"
    local source_path=""
    local dest_path=""
    
    # Find source file
    if [ -f "$SCRIPTS_DIR/$old_name" ]; then
        source_path="$SCRIPTS_DIR/$old_name"
        dest_path="$SCRIPTS_DIR/$new_name"
    elif [ -f "$SPYDER_HOME/$old_name" ]; then
        source_path="$SPYDER_HOME/$old_name"
        dest_path="$SCRIPTS_DIR/$new_name"
    elif [ -f "$SPYDER_HOME/services/$old_name" ]; then
        source_path="$SPYDER_HOME/services/$old_name"
        dest_path="$SPYDER_HOME/services/$new_name"
    else
        SKIPPED+=("$old_name (not found)")
        return 1
    fi
    
    # Check if destination already exists
    if [ -f "$dest_path" ]; then
        if [ "$source_path" != "$dest_path" ]; then
            print_warning "$new_name already exists, keeping both"
            # Rename old file with .old extension
            mv "$source_path" "${source_path}.old"
            MIGRATED+=("$old_name → ${old_name}.old (preserved)")
        else
            SKIPPED+=("$old_name (already migrated)")
        fi
        return 0
    fi
    
    # Perform migration
    if mv "$source_path" "$dest_path"; then
        MIGRATED+=("$old_name → $new_name")
        print_success "Migrated: $old_name → $new_name"
        
        # Update shebang if needed
        update_file_header "$dest_path" "$new_name"
        
        # Make executable if it's a script
        if [[ "$new_name" == *.sh ]] || [[ "$new_name" == *.py ]]; then
            chmod +x "$dest_path"
        fi
        
        return 0
    else
        FAILED+=("$old_name → $new_name")
        print_error "Failed to migrate: $old_name"
        return 1
    fi
}

update_file_header() {
    local file_path="$1"
    local script_name="$2"
    
    # Skip if file doesn't exist
    [ -f "$file_path" ] || return 0
    
    # Get file extension
    local ext="${file_path##*.}"
    
    # Create temporary file with updated header
    local temp_file=$(mktemp)
    local date_created=$(date +%Y-%m-%d)
    local time_updated=$(date "+%H:%M:%S")
    
    if [[ "$ext" == "py" ]]; then
        cat > "$temp_file" << EOF
#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Module: $script_name
# Group: Q (Scripts)
# Purpose: Migrated from legacy script
# Author: Mohamed Talib
# Date Created: $date_created
# Last Updated: $date_created Time: $time_updated
#
# Description:
#     Migrated to Q-series naming convention for better organization.
#     Original functionality preserved.
# ===============================================================================

EOF
    elif [[ "$ext" == "sh" ]]; then
        cat > "$temp_file" << EOF
#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Script: $script_name
# Group: Q (Scripts)
# Purpose: Migrated from legacy script
# Author: Mohamed Talib
# Date Created: $date_created
# Last Updated: $date_created Time: $time_updated
#
# Description:
#     Migrated to Q-series naming convention for better organization.
#     Original functionality preserved.
# ===============================================================================

EOF
    fi
    
    # Append original content (skip old shebang if present)
    if [[ "$ext" == "py" ]] || [[ "$ext" == "sh" ]]; then
        tail -n +2 "$file_path" >> "$temp_file" 2>/dev/null || cat "$file_path" >> "$temp_file"
        mv "$temp_file" "$file_path"
    else
        rm "$temp_file"
    fi
}

update_references() {
    print_info "Updating script references..."
    
    # Files to check for references
    local files_to_check=(
        "$SPYDER_HOME"/*.py
        "$SPYDER_HOME"/*.sh
        "$SCRIPTS_DIR"/*.py
        "$SCRIPTS_DIR"/*.sh
        "$SPYDER_HOME"/.env
        "$SPYDER_HOME"/README.md
    )
    
    for old_name in "${!MIGRATION_MAP[@]}"; do
        local new_name="${MIGRATION_MAP[$old_name]}"
        
        for file in "${files_to_check[@]}"; do
            if [ -f "$file" ]; then
                # Use sed to replace references
                sed -i.bak "s|$old_name|$new_name|g" "$file" 2>/dev/null || true
            fi
        done
    done
    
    # Clean up backup files
    find "$SPYDER_HOME" -name "*.bak" -delete
    
    print_success "References updated"
}

create_index() {
    print_info "Creating Q-Series index..."
    
    cat > "$SCRIPTS_DIR/Q_SERIES_INDEX.md" << 'EOF'
# SPYDER Q-Series Script Index

## Organization Structure

### Q00-Q09: Setup & Installation
- **Q01**: Main setup script
- **Q02**: Dependencies installation
- **Q03**: IB Gateway installation
- **Q04**: Watchdog setup
- **Q05**: Command installation
- **Q06**: Migration tool

### Q10-Q19: Start/Stop/Control
- **Q10**: Start all components
- **Q11**: Stop all components
- **Q12**: Start multi-client
- **Q13**: Start real gateway
- **Q14**: Main launcher
- **Q15**: Legacy spyder command
- **Q16**: Master control script

### Q20-Q29: Monitoring & Status
- **Q20**: System status
- **Q21**: Live monitor
- **Q22**: IB status check
- **Q23**: Dashboard timer
- **Q24**: Production watchdog
- **Q25**: Advanced system monitor

### Q30-Q39: Testing & Development
- **Q30**: Development test suite
- **Q31**: Integration tests
- **Q32**: Simple IB test
- **Q35**: System verification

### Q40-Q49: Maintenance & Cleanup
- **Q40**: Fix B07 module
- **Q41**: Time synchronization
- **Q42**: Integration fixes
- **Q45**: System diagnostics

### Q50-Q59: Data & Reports
- **Q50**: Export trading data
- **Q51**: Import trading data
- **Q52**: Archive reports

### Q60-Q69: Helper Scripts
- **Q60**: Metrics exporter
- **Q61**: Health reporter
- **Q62**: Client analyzer

### Q70-Q79: Service Files
- **Q70**: Watchdog service
- **Q71**: Metrics service
- **Q72**: IB Watchdog service
- **Q74**: Main Spyder service

### Q80-Q89: Configuration
- **Q80**: Environment config
- **Q81**: Prometheus config
- **Q82**: Alert rules

## Quick Reference

```bash
# Most common commands after migration:
spyder start              # Start trading system
spyder stop              # Stop trading system
spyder status            # Check status
spyder monitor           # Live monitoring
spyder help              # Show all commands
```

## Migration Date
Generated: $(date '+%Y-%m-%d %H:%M:%S')
EOF
    
    print_success "Index created at $SCRIPTS_DIR/Q_SERIES_INDEX.md"
}

# ===============================================================================
# VERIFICATION FUNCTIONS
# ===============================================================================

verify_migration() {
    print_info "Verifying migration..."
    
    local issues=0
    
    # Check if critical scripts exist
    local critical_scripts=(
        "SpyderQ01_Setup.sh"
        "SpyderQ10_StartAll.sh"
        "SpyderQ11_StopAll.sh"
        "SpyderQ16_SpyderControl.sh"
        "SpyderQ20_Status.sh"
    )
    
    for script in "${critical_scripts[@]}"; do
        if [ -f "$SCRIPTS_DIR/$script" ]; then
            print_success "$script found"
        else
            print_error "$script missing"
            ((issues++))
        fi
    done
    
    # Check permissions
    for script in "$SCRIPTS_DIR"/SpyderQ*.sh; do
        if [ -f "$script" ]; then
            if [ -x "$script" ]; then
                print_success "$(basename "$script") is executable"
            else
                print_warning "$(basename "$script") not executable, fixing..."
                chmod +x "$script"
            fi
        fi
    done
    
    # Check Python scripts
    for script in "$SCRIPTS_DIR"/SpyderQ*.py; do
        if [ -f "$script" ]; then
            if python3 -m py_compile "$script" 2>/dev/null; then
                print_success "$(basename "$script") syntax OK"
            else
                print_error "$(basename "$script") has syntax errors"
                ((issues++))
            fi
        fi
    done
    
    if [ $issues -eq 0 ]; then
        print_success "Migration verification passed!"
        return 0
    else
        print_error "Migration verification found $issues issue(s)"
        return 1
    fi
}

# ===============================================================================
# REPORTING
# ===============================================================================

generate_report() {
    local report_file="$SPYDER_HOME/logs/migration_report_$(date +%Y%m%d_%H%M%S).txt"
    
    {
        echo "SPYDER Q-SERIES MIGRATION REPORT"
        echo "================================="
        echo "Date: $(date)"
        echo "Backup Location: $BACKUP_DIR"
        echo ""
        
        echo "SUCCESSFULLY MIGRATED (${#MIGRATED[@]}):"
        echo "------------------------"
        for item in "${MIGRATED[@]}"; do
            echo "  ✓ $item"
        done
        echo ""
        
        echo "SKIPPED (${#SKIPPED[@]}):"
        echo "------------------------"
        for item in "${SKIPPED[@]}"; do
            echo "  - $item"
        done
        echo ""
        
        echo "FAILED (${#FAILED[@]}):"
        echo "------------------------"
        for item in "${FAILED[@]}"; do
            echo "  ✗ $item"
        done
        echo ""
        
        echo "NEW Q-SERIES SCRIPTS:"
        echo "------------------------"
        for script in "$SCRIPTS_DIR"/SpyderQ*.{sh,py} "$SPYDER_HOME/services"/SpyderQ*.service; do
            if [ -f "$script" ]; then
                echo "  • $(basename "$script")"
            fi
        done
        echo ""
        
        echo "NEXT STEPS:"
        echo "-----------"
        echo "1. Review the migration results above"
        echo "2. Test critical scripts:"
        echo "   ./SpyderQ35_VerifySystem.sh"
        echo "3. Install system commands:"
        echo "   ./SpyderQ05_InstallCommands.sh"
        echo "4. If issues found, restore from backup:"
        echo "   $BACKUP_DIR/restore.sh"
        
    } | tee "$report_file"
    
    print_info "Report saved to: $report_file"
}

# ===============================================================================
# MAIN MIGRATION PROCESS
# ===============================================================================

main() {
    print_header
    echo ""
    
    # Check prerequisites
    if [ ! -d "$SPYDER_HOME" ]; then
        print_error "Spyder not found at $SPYDER_HOME"
        exit 1
    fi
    
    # Create necessary directories
    mkdir -p "$SCRIPTS_DIR"
    mkdir -p "$SPYDER_HOME/services"
    mkdir -p "$SPYDER_HOME/logs"
    
    # Initialize log
    echo "===== MIGRATION STARTED: $(date) =====" > "$MIGRATION_LOG"
    
    # Confirmation
    echo "This will migrate your Spyder scripts to Q-series naming."
    echo "A full backup will be created first."
    echo ""
    read -p "Continue with migration? (y/N): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Migration cancelled"
        exit 0
    fi
    
    # Step 1: Backup
    echo ""
    print_info "Step 1: Creating backup..."
    create_backup
    
    # Step 2: Migrate files
    echo ""
    print_info "Step 2: Migrating files..."
    for old_name in "${!MIGRATION_MAP[@]}"; do
        new_name="${MIGRATION_MAP[$old_name]}"
        migrate_file "$old_name" "$new_name"
    done
    
    # Step 3: Update references
    echo ""
    print_info "Step 3: Updating references..."
    update_references
    
    # Step 4: Create index
    echo ""
    print_info "Step 4: Creating index..."
    create_index
    
    # Step 5: Verify
    echo ""
    print_info "Step 5: Verifying migration..."
    verify_migration
    
    # Step 6: Generate report
    echo ""
    print_info "Step 6: Generating report..."
    generate_report
    
    echo ""
    print_success "Migration complete!"
    echo ""
    echo "To complete setup, run:"
    echo "  1. cd $SCRIPTS_DIR"
    echo "  2. ./SpyderQ35_VerifySystem.sh"
    echo "  3. ./SpyderQ05_InstallCommands.sh"
}

# Run main
main "$@"
