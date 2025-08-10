#!/bin/bash
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Spyder Version: 1.0
# Module: SpyderQ41_Backup.sh
# Group: Q (Scripts)
# Purpose: Backup configuration, data, and critical system files
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 18:45:00
#
# Description:
#     Comprehensive backup utility that creates timestamped backups of
#     configuration files, trading data, logs, and system state. Supports
#     full and incremental backups, encryption, remote storage, and automatic
#     rotation of old backups to manage disk space efficiently.
# ===============================================================================

set -e

# Configuration
SPYDER_HOME="${SPYDER_HOME:-/home/adam/Projects/Spyder}"
BACKUP_DIR="$SPYDER_HOME/backup"
REMOTE_BACKUP="${REMOTE_BACKUP:-}"  # Set to remote path if needed
MAX_BACKUPS=10
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup categories
CONFIG_FILES=(
    ".env"
    "config/*.yaml"
    "config/*.json"
    "SpyderQ_Scripts/*.sh"
    "SpyderQ_Scripts/*.py"
)

DATA_DIRS=(
    "data/reports"
    "data/metrics"
    "data/positions"
)

CRITICAL_FILES=(
    "*.db"
    "*.sqlite"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
TOTAL_FILES=0
BACKUP_SIZE=0

# ===============================================================================
# HELPER FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        SPYDER BACKUP UTILITY              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
}

print_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# ===============================================================================
# BACKUP FUNCTIONS
# ===============================================================================

create_backup_structure() {
    local backup_path="$1"
    mkdir -p "$backup_path"/{config,data,logs,scripts,state}
}

backup_configuration() {
    local backup_path="$1"
    print_info "Backing up configuration files..."
    
    for pattern in "${CONFIG_FILES[@]}"; do
        # Use find to handle wildcards properly
        find "$SPYDER_HOME" -maxdepth 2 -path "$SPYDER_HOME/$pattern" -type f 2>/dev/null | while read file; do
            if [ -f "$file" ]; then
                local rel_path="${file#$SPYDER_HOME/}"
                local dest_dir="$backup_path/config/$(dirname "$rel_path")"
                mkdir -p "$dest_dir"
                cp -p "$file" "$dest_dir/"
                ((TOTAL_FILES++))
                echo "  ✓ $(basename "$file")"
            fi
        done
    done
    
    print_success "Configuration backed up"
}

backup_data() {
    local backup_path="$1"
    print_info "Backing up data directories..."
    
    for dir in "${DATA_DIRS[@]}"; do
        if [ -d "$SPYDER_HOME/$dir" ]; then
            mkdir -p "$backup_path/data"
            cp -rp "$SPYDER_HOME/$dir" "$backup_path/data/"
            local count=$(find "$SPYDER_HOME/$dir" -type f | wc -l)
            TOTAL_FILES=$((TOTAL_FILES + count))
            echo "  ✓ $dir ($count files)"
        fi
    done
    
    print_success "Data directories backed up"
}

backup_databases() {
    local backup_path="$1"
    print_info "Backing up database files..."
    
    mkdir -p "$backup_path/state"
    
    # Find all database files
    find "$SPYDER_HOME" -maxdepth 3 \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) -type f 2>/dev/null | while read db; do
        if [ -f "$db" ]; then
            # For SQLite databases, create a proper backup
            if command -v sqlite3 &> /dev/null; then
                local db_name=$(basename "$db")
                sqlite3 "$db" ".backup '$backup_path/state/$db_name'" 2>/dev/null && \
                    echo "  ✓ $db_name (SQLite backup)"
            else
                cp -p "$db" "$backup_path/state/"
                echo "  ✓ $(basename "$db") (file copy)"
            fi
            ((TOTAL_FILES++))
        fi
    done
    
    print_success "Databases backed up"
}

backup_logs() {
    local backup_path="$1"
    local log_days="${2:-1}"  # Default to last 24 hours of logs
    
    print_info "Backing up recent logs (last $log_days day(s))..."
    
    if [ -d "$SPYDER_HOME/logs" ]; then
        mkdir -p "$backup_path/logs"
        
        # Find recent log files
        find "$SPYDER_HOME/logs" -type f -name "*.log" -mtime -$log_days -exec cp -p {} "$backup_path/logs/" \; 2>/dev/null
        
        local log_count=$(find "$backup_path/logs" -type f | wc -l)
        TOTAL_FILES=$((TOTAL_FILES + log_count))
        print_success "Logs backed up ($log_count files)"
    else
        print_warning "No logs directory found"
    fi
}

backup_scripts() {
    local backup_path="$1"
    print_info "Backing up Q-Series scripts..."
    
    if [ -d "$SPYDER_HOME/SpyderQ_Scripts" ]; then
        cp -rp "$SPYDER_HOME/SpyderQ_Scripts" "$backup_path/scripts/"
        local script_count=$(find "$SPYDER_HOME/SpyderQ_Scripts" -type f | wc -l)
        TOTAL_FILES=$((TOTAL_FILES + script_count))
        print_success "Scripts backed up ($script_count files)"
    fi
}

create_manifest() {
    local backup_path="$1"
    local backup_type="$2"
    
    cat > "$backup_path/MANIFEST.txt" << EOF
SPYDER BACKUP MANIFEST
======================
Date: $(date)
Type: $backup_type
Hostname: $(hostname)
User: $USER
Spyder Home: $SPYDER_HOME
Total Files: $TOTAL_FILES
Backup Size: $(du -sh "$backup_path" | cut -f1)

Contents:
---------
$(find "$backup_path" -type d -maxdepth 2 | sed "s|$backup_path|.|g" | sort)

Checksums:
----------
EOF
    
    # Generate checksums for critical files
    find "$backup_path" -type f \( -name "*.env" -o -name "*.db" -o -name "*.sqlite" \) -exec sha256sum {} \; >> "$backup_path/MANIFEST.txt" 2>/dev/null
    
    print_success "Manifest created"
}

compress_backup() {
    local backup_path="$1"
    local archive_name="$2"
    
    print_info "Compressing backup..."
    
    cd "$BACKUP_DIR"
    tar -czf "$archive_name" "$(basename "$backup_path")" 2>/dev/null
    
    if [ -f "$archive_name" ]; then
        BACKUP_SIZE=$(du -h "$archive_name" | cut -f1)
        rm -rf "$backup_path"
        print_success "Backup compressed: $archive_name ($BACKUP_SIZE)"
        return 0
    else
        print_error "Compression failed"
        return 1
    fi
}

encrypt_backup() {
    local archive_name="$1"
    
    if command -v gpg &> /dev/null; then
        print_info "Encrypting backup..."
        
        # Use symmetric encryption with passphrase
        gpg --cipher-algo AES256 --symmetric --batch --passphrase "$BACKUP_PASSWORD" "$archive_name" 2>/dev/null
        
        if [ -f "$archive_name.gpg" ]; then
            rm "$archive_name"
            print_success "Backup encrypted: $archive_name.gpg"
            return 0
        fi
    fi
    
    print_warning "Encryption skipped (gpg not available or no password set)"
    return 1
}

rotate_backups() {
    print_info "Rotating old backups..."
    
    # Count existing backups
    local backup_count=$(find "$BACKUP_DIR" -maxdepth 1 -name "spyder_backup_*.tar.gz*" | wc -l)
    
    if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
        local remove_count=$((backup_count - MAX_BACKUPS))
        print_info "Removing $remove_count old backup(s)..."
        
        # Remove oldest backups
        find "$BACKUP_DIR" -maxdepth 1 -name "spyder_backup_*.tar.gz*" -printf '%T+ %p\n' | \
            sort | head -n "$remove_count" | cut -d' ' -f2 | while read old_backup; do
            rm "$old_backup"
            echo "  Removed: $(basename "$old_backup")"
        done
    fi
    
    print_success "Backup rotation complete"
}

upload_to_remote() {
    local archive_name="$1"
    
    if [ -n "$REMOTE_BACKUP" ]; then
        print_info "Uploading to remote storage..."
        
        # Support various remote protocols
        if [[ "$REMOTE_BACKUP" == s3://* ]]; then
            # AWS S3
            if command -v aws &> /dev/null; then
                aws s3 cp "$BACKUP_DIR/$archive_name" "$REMOTE_BACKUP/" && \
                    print_success "Uploaded to S3"
            else
                print_warning "AWS CLI not installed"
            fi
        elif [[ "$REMOTE_BACKUP" == *:* ]]; then
            # SCP/SSH
            scp "$BACKUP_DIR/$archive_name" "$REMOTE_BACKUP/" && \
                print_success "Uploaded via SCP"
        else
            # Local network path
            cp "$BACKUP_DIR/$archive_name" "$REMOTE_BACKUP/" && \
                print_success "Copied to network location"
        fi
    fi
}

# ===============================================================================
# RESTORE FUNCTION
# ===============================================================================

restore_backup() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        print_error "Backup file not found: $backup_file"
        return 1
    fi
    
    print_warning "This will restore from backup: $(basename "$backup_file")"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Restore cancelled"
        return 1
    fi
    
    # Create restore directory
    local restore_dir="$BACKUP_DIR/restore_$TIMESTAMP"
    mkdir -p "$restore_dir"
    
    # Extract backup
    print_info "Extracting backup..."
    tar -xzf "$backup_file" -C "$restore_dir"
    
    # Find the extracted backup directory
    local extracted_dir=$(find "$restore_dir" -maxdepth 1 -type d -name "spyder_backup_*" | head -1)
    
    if [ -z "$extracted_dir" ]; then
        print_error "Failed to extract backup"
        return 1
    fi
    
    # Restore files
    print_info "Restoring files..."
    
    # Backup current state before restore
    print_info "Creating safety backup of current state..."
    "$0" --quick
    
    # Restore configuration
    if [ -d "$extracted_dir/config" ]; then
        cp -rp "$extracted_dir/config/"* "$SPYDER_HOME/" 2>/dev/null || true
        print_success "Configuration restored"
    fi
    
    # Restore data
    if [ -d "$extracted_dir/data" ]; then
        cp -rp "$extracted_dir/data/"* "$SPYDER_HOME/data/" 2>/dev/null || true
        print_success "Data restored"
    fi
    
    # Restore databases
    if [ -d "$extracted_dir/state" ]; then
        cp -p "$extracted_dir/state/"*.db "$SPYDER_HOME/" 2>/dev/null || true
        cp -p "$extracted_dir/state/"*.sqlite "$SPYDER_HOME/" 2>/dev/null || true
        print_success "Databases restored"
    fi
    
    # Restore scripts
    if [ -d "$extracted_dir/scripts/SpyderQ_Scripts" ]; then
        cp -rp "$extracted_dir/scripts/SpyderQ_Scripts/"* "$SPYDER_HOME/SpyderQ_Scripts/" 2>/dev/null || true
        print_success "Scripts restored"
    fi
    
    # Clean up
    rm -rf "$restore_dir"
    
    print_success "Restore complete!"
    print_warning "Please restart Spyder services for changes to take effect"
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    # Parse arguments
    case "$1" in
        --full|-f)
            BACKUP_TYPE="FULL"
            ;;
        --quick|-q)
            BACKUP_TYPE="QUICK"
            ;;
        --restore|-r)
            if [ -z "$2" ]; then
                print_error "Please specify backup file to restore"
                echo "Usage: $0 --restore <backup_file>"
                exit 1
            fi
            restore_backup "$2"
            exit $?
            ;;
        --list|-l)
            print_header
            echo ""
            print_info "Available backups:"
            ls -lh "$BACKUP_DIR"/spyder_backup_*.tar.gz* 2>/dev/null || echo "No backups found"
            exit 0
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --full, -f      Create full backup"
            echo "  --quick, -q     Create quick backup (config only)"
            echo "  --restore FILE  Restore from backup file"
            echo "  --list, -l      List available backups"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_PASSWORD    Password for encryption"
            echo "  REMOTE_BACKUP      Remote backup location"
            echo "  MAX_BACKUPS        Maximum backups to keep (default: 10)"
            exit 0
            ;;
        *)
            BACKUP_TYPE="STANDARD"
            ;;
    esac
    
    print_header
    echo ""
    print_info "Starting $BACKUP_TYPE backup..."
    echo ""
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Create timestamped backup path
    local backup_path="$BACKUP_DIR/spyder_backup_$TIMESTAMP"
    local archive_name="spyder_backup_${TIMESTAMP}_${BACKUP_TYPE}.tar.gz"
    
    # Create backup structure
    create_backup_structure "$backup_path"
    
    # Perform backup based on type
    case "$BACKUP_TYPE" in
        FULL)
            backup_configuration "$backup_path"
            backup_data "$backup_path"
            backup_databases "$backup_path"
            backup_logs "$backup_path" 7  # Last 7 days
            backup_scripts "$backup_path"
            ;;
        QUICK)
            backup_configuration "$backup_path"
            backup_databases "$backup_path"
            ;;
        STANDARD)
            backup_configuration "$backup_path"
            backup_data "$backup_path"
            backup_databases "$backup_path"
            backup_logs "$backup_path" 1  # Last 24 hours
            backup_scripts "$backup_path"
            ;;
    esac
    
    # Create manifest
    create_manifest "$backup_path" "$BACKUP_TYPE"
    
    # Compress backup
    compress_backup "$backup_path" "$archive_name"
    
    # Encrypt if password is set
    if [ -n "$BACKUP_PASSWORD" ]; then
        encrypt_backup "$archive_name"
        archive_name="$archive_name.gpg"
    fi
    
    # Rotate old backups
    rotate_backups
    
    # Upload to remote if configured
    upload_to_remote "$archive_name"
    
    # Summary
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          BACKUP COMPLETE!                 ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Backup Type: $BACKUP_TYPE"
    echo "Files Backed Up: $TOTAL_FILES"
    echo "Backup Size: $BACKUP_SIZE"
    echo "Location: $BACKUP_DIR/$archive_name"
    
    if [ -n "$REMOTE_BACKUP" ]; then
        echo "Remote: $REMOTE_BACKUP"
    fi
    
    echo ""
    echo "To restore from this backup:"
    echo "  $0 --restore $BACKUP_DIR/$archive_name"
}

# Run main
main "$@"
