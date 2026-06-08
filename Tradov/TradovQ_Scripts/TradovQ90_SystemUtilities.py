#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovQ_Scripts
Module: TradovQ90_SystemUtilities.py
Purpose: Consolidated system utilities for cleanup, backup, and data export
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-05 Time: 15:30:00

Module Description:
    This module consolidates system utility functions previously implemented
    as separate shell scripts. It provides cleanup operations for logs and
    temporary files, backup functionality for critical system data, and
    export capabilities for trading data and reports. Integrates with the
    main Tradov system for maintenance and data management operations.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import sqlite3
import tarfile
import json
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add Tradov home to path if not already present
_DEFAULT_TRADOV_HOME = str(Path(__file__).resolve().parents[2])
TRADOV_HOME = os.environ.get("TRADOV_HOME", _DEFAULT_TRADOV_HOME)
if TRADOV_HOME not in sys.path:
    sys.path.insert(0, TRADOV_HOME)

try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
except ImportError as e:
    print(f"Warning: Could not import utilities: {e}")
    # Fallback to basic logging
    import logging
    TradovLogger = logging
    TradovErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Directory paths
LOGS_DIR = Path(TRADOV_HOME) / "logs"
BACKUP_DIR = Path(TRADOV_HOME) / "backups"
EXPORT_DIR = Path(TRADOV_HOME) / "exports"
TEMP_DIR = Path(TRADOV_HOME) / "temp"
DATA_DIR = Path(TRADOV_HOME) / "data"
CONFIG_DIR = Path(TRADOV_HOME) / "config"

# Cleanup settings
DEFAULT_LOG_RETENTION_DAYS = 30
DEFAULT_BACKUP_RETENTION_DAYS = 90
MAX_BACKUP_SIZE_GB = 50
LOG_PATTERNS = ["*.log", "*.log.*", "*.out", "*.err"]
TEMP_PATTERNS = ["*.tmp", "*.temp", "*.cache", "*.pid"]

# Export formats
EXPORT_FORMATS = ["csv", "json", "excel", "parquet"]

# ==============================================================================
# ENUMS
# ==============================================================================
class OperationStatus(Enum):
    """Status of utility operations"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"

class BackupType(Enum):
    """Types of backups"""
    FULL = "full"
    INCREMENTAL = "incremental"
    CONFIG_ONLY = "config"
    DATA_ONLY = "data"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CleanupReport:
    """Report of cleanup operations"""
    files_deleted: int
    space_freed_mb: float
    errors: list[str]
    status: OperationStatus
    timestamp: datetime

@dataclass
class BackupInfo:
    """Information about a backup"""
    backup_id: str
    backup_type: BackupType
    timestamp: datetime
    size_mb: float
    files_count: int
    location: Path
    manifest: dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SystemUtilities:
    """
    Consolidated system utilities for Tradov maintenance operations.

    This class provides centralized functionality for system maintenance
    including cleanup of logs and temporary files, backup operations,
    data export, and system health checks. Replaces multiple shell
    scripts with Python implementations for better integration.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        dry_run: If True, shows what would be done without doing it

    Example:
        >>> utils = SystemUtilities()
        >>> utils.cleanup_logs(retention_days=30)
        >>> utils.create_backup(backup_type=BackupType.FULL)
        >>> utils.export_trading_data(format="csv")
    """

    def __init__(self, dry_run: bool = False):
        """Initialize system utilities."""
        self.logger = TradovLogger.get_logger(__name__) if TradovLogger else logging.getLogger(__name__)
        self.error_handler = TradovErrorHandler() if TradovErrorHandler else None
        self.dry_run = dry_run

        # Create necessary directories
        for directory in [BACKUP_DIR, EXPORT_DIR, TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

        self.logger.info("SystemUtilities initialized (dry_run=%s)", dry_run)

    # ==========================================================================
    # CLEANUP METHODS
    # ==========================================================================
    def cleanup_all(self, retention_days: int = DEFAULT_LOG_RETENTION_DAYS) -> CleanupReport:
        """
        Perform complete system cleanup.

        Args:
            retention_days: Number of days to retain logs

        Returns:
            CleanupReport with operation results
        """
        self.logger.info("Starting complete system cleanup")

        total_deleted = 0
        total_freed = 0.0
        all_errors = []

        # Clean logs
        log_report = self.cleanup_logs(retention_days)
        total_deleted += log_report.files_deleted
        total_freed += log_report.space_freed_mb
        all_errors.extend(log_report.errors)

        # Clean temp files
        temp_report = self.cleanup_temp_files()
        total_deleted += temp_report.files_deleted
        total_freed += temp_report.space_freed_mb
        all_errors.extend(temp_report.errors)

        # Clean old backups
        backup_report = self.cleanup_old_backups(DEFAULT_BACKUP_RETENTION_DAYS)
        total_deleted += backup_report.files_deleted
        total_freed += backup_report.space_freed_mb
        all_errors.extend(backup_report.errors)

        # Optimize databases
        self.optimize_databases()

        status = OperationStatus.SUCCESS if not all_errors else OperationStatus.PARTIAL

        report = CleanupReport(
            files_deleted=total_deleted,
            space_freed_mb=total_freed,
            errors=all_errors,
            status=status,
            timestamp=datetime.now(UTC)
        )

        self.logger.info(f"Cleanup complete: {total_deleted} files deleted, {total_freed:.2f} MB freed")
        return report

    def cleanup_logs(self, retention_days: int = DEFAULT_LOG_RETENTION_DAYS) -> CleanupReport:
        """
        Clean up old log files.

        Args:
            retention_days: Number of days to retain logs

        Returns:
            CleanupReport with operation results
        """
        self.logger.info("Cleaning logs older than %s days", retention_days)

        files_deleted = 0
        space_freed = 0.0
        errors = []
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

        try:
            if LOGS_DIR.exists():
                for pattern in LOG_PATTERNS:
                    for log_file in LOGS_DIR.glob(pattern):
                        try:
                            if log_file.stat().st_mtime < cutoff_date.timestamp():
                                size_mb = log_file.stat().st_size / (1024 * 1024)

                                if self.dry_run:
                                    self.logger.info(f"[DRY RUN] Would delete: {log_file} ({size_mb:.2f} MB)")
                                else:
                                    log_file.unlink()
                                    self.logger.debug("Deleted: %s", log_file)

                                files_deleted += 1
                                space_freed += size_mb

                        except Exception as e:
                            error_msg = f"Error deleting {log_file}: {e}"
                            errors.append(error_msg)
                            self.logger.error(error_msg)

        except Exception as e:
            error_msg = f"Error accessing logs directory: {e}"
            errors.append(error_msg)
            self.logger.error(error_msg)

        status = OperationStatus.SUCCESS if not errors else OperationStatus.PARTIAL

        return CleanupReport(
            files_deleted=files_deleted,
            space_freed_mb=space_freed,
            errors=errors,
            status=status,
            timestamp=datetime.now(UTC)
        )

    def cleanup_temp_files(self) -> CleanupReport:
        """
        Clean up temporary files.

        Returns:
            CleanupReport with operation results
        """
        self.logger.info("Cleaning temporary files")

        files_deleted = 0
        space_freed = 0.0
        errors = []

        # Clean system temp directory
        for temp_location in [TEMP_DIR, Path("/tmp")]:
            if temp_location.exists():
                for pattern in TEMP_PATTERNS:
                    for temp_file in temp_location.glob(f"tradov_{pattern}"):
                        try:
                            size_mb = temp_file.stat().st_size / (1024 * 1024)

                            if self.dry_run:
                                self.logger.info("[DRY RUN] Would delete: %s", temp_file)
                            else:
                                temp_file.unlink()

                            files_deleted += 1
                            space_freed += size_mb

                        except Exception as e:
                            errors.append(f"Error deleting {temp_file}: {e}")

        status = OperationStatus.SUCCESS if not errors else OperationStatus.PARTIAL

        return CleanupReport(
            files_deleted=files_deleted,
            space_freed_mb=space_freed,
            errors=errors,
            status=status,
            timestamp=datetime.now(UTC)
        )

    def cleanup_old_backups(self, retention_days: int = DEFAULT_BACKUP_RETENTION_DAYS) -> CleanupReport:
        """
        Clean up old backup files.

        Args:
            retention_days: Number of days to retain backups

        Returns:
            CleanupReport with operation results
        """
        self.logger.info("Cleaning backups older than %s days", retention_days)

        files_deleted = 0
        space_freed = 0.0
        errors = []
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)

        if BACKUP_DIR.exists():
            for backup_file in BACKUP_DIR.glob("tradov_backup_*.tar.gz"):
                try:
                    if backup_file.stat().st_mtime < cutoff_date.timestamp():
                        size_mb = backup_file.stat().st_size / (1024 * 1024)

                        if self.dry_run:
                            self.logger.info("[DRY RUN] Would delete backup: %s", backup_file)
                        else:
                            backup_file.unlink()

                        files_deleted += 1
                        space_freed += size_mb

                except Exception as e:
                    errors.append(f"Error deleting backup {backup_file}: {e}")

        status = OperationStatus.SUCCESS if not errors else OperationStatus.PARTIAL

        return CleanupReport(
            files_deleted=files_deleted,
            space_freed_mb=space_freed,
            errors=errors,
            status=status,
            timestamp=datetime.now(UTC)
        )

    # ==========================================================================
    # BACKUP METHODS
    # ==========================================================================
    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        description: str = ""
    ) -> BackupInfo | None:
        """
        Create a system backup.

        Args:
            backup_type: Type of backup to create
            description: Optional description for the backup

        Returns:
            BackupInfo if successful, None otherwise
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup_id = f"tradov_backup_{backup_type.value}_{timestamp}"
        backup_file = BACKUP_DIR / f"{backup_id}.tar.gz"

        self.logger.info("Creating %s backup: %s", backup_type.value, backup_id)

        try:
            files_count = 0
            manifest = {
                "backup_id": backup_id,
                "type": backup_type.value,
                "timestamp": timestamp,
                "description": description,
                "modules": [],
                "configs": [],
                "data": []
            }

            with tarfile.open(backup_file, "w:gz") as tar:
                # Backup based on type
                if backup_type in [BackupType.FULL, BackupType.CONFIG_ONLY]:
                    # Backup configuration files
                    if CONFIG_DIR.exists():
                        tar.add(CONFIG_DIR, arcname="config")
                        manifest["configs"] = [str(f.relative_to(CONFIG_DIR))
                                               for f in CONFIG_DIR.rglob("*") if f.is_file()]
                        files_count += len(manifest["configs"])

                    # Backup .env files
                    for env_file in Path(TRADOV_HOME).glob("*.env"):
                        tar.add(env_file, arcname=f"env/{env_file.name}")
                        files_count += 1

                if backup_type in [BackupType.FULL, BackupType.DATA_ONLY]:
                    # Backup databases
                    if DATA_DIR.exists():
                        for db_file in DATA_DIR.glob("*.db"):
                            # Create consistent backup for SQLite
                            self._backup_sqlite_database(db_file, tar)
                            manifest["data"].append(db_file.name)
                            files_count += 1

                if backup_type == BackupType.FULL:
                    # Backup Python modules (exclude __pycache__)
                    for module_dir in Path(TRADOV_HOME).glob("Tradov*"):
                        if module_dir.is_dir() and not module_dir.name.endswith("__pycache__"):
                            tar.add(module_dir, arcname=module_dir.name,
                                   filter=lambda x: None if "__pycache__" in x.name else x)
                            manifest["modules"].append(module_dir.name)

                # Add manifest to backup
                manifest_file = TEMP_DIR / f"{backup_id}_manifest.json"
                with open(manifest_file, "w") as f:
                    json.dump(manifest, f, indent=2)
                tar.add(manifest_file, arcname="manifest.json")
                manifest_file.unlink()

            # Get backup size
            size_mb = backup_file.stat().st_size / (1024 * 1024)

            backup_info = BackupInfo(
                backup_id=backup_id,
                backup_type=backup_type,
                timestamp=datetime.now(UTC),
                size_mb=size_mb,
                files_count=files_count,
                location=backup_file,
                manifest=manifest
            )

            self.logger.info(f"Backup created successfully: {backup_file} ({size_mb:.2f} MB, {files_count} files)")
            return backup_info

        except Exception as e:
            self.logger.error("Backup failed: %s", e)
            if backup_file.exists():
                backup_file.unlink()
            return None

    def _backup_sqlite_database(self, db_path: Path, tar: tarfile.TarFile) -> None:
        """
        Create consistent SQLite database backup.

        Args:
            db_path: Path to database file
            tar: Tar archive to add backup to
        """
        try:
            # Use SQLite backup API for consistency
            backup_path = TEMP_DIR / f"{db_path.stem}_backup{db_path.suffix}"

            with sqlite3.connect(db_path) as source, sqlite3.connect(backup_path) as backup:
                source.backup(backup)

            tar.add(backup_path, arcname=f"data/{db_path.name}")
            backup_path.unlink()

        except Exception as e:
            self.logger.warning("SQLite backup failed, using file copy: %s", e)
            tar.add(db_path, arcname=f"data/{db_path.name}")

    def restore_backup(self, backup_id: str, target_dir: Path | None = None) -> bool:
        """
        Restore from a backup.

        Args:
            backup_id: ID of the backup to restore
            target_dir: Target directory (defaults to TRADOV_HOME)

        Returns:
            True if successful, False otherwise
        """
        backup_file = BACKUP_DIR / f"{backup_id}.tar.gz"

        if not backup_file.exists():
            self.logger.error("Backup not found: %s", backup_file)
            return False

        target = target_dir or Path(TRADOV_HOME)

        try:
            self.logger.info("Restoring backup: %s", backup_id)

            with tarfile.open(backup_file, "r:gz") as tar:
                # Check manifest first
                try:
                    manifest_member = tar.getmember("manifest.json")
                    manifest_file = tar.extractfile(manifest_member)
                    manifest = json.load(manifest_file)
                    self.logger.info("Restoring %s backup from %s", manifest['type'], manifest['timestamp'])
                except KeyError:
                    self.logger.warning("No manifest found in backup")

                # Extract all files
                tar.extractall(target)

            self.logger.info("Backup restored successfully")
            return True

        except Exception as e:
            self.logger.error("Restore failed: %s", e)
            return False

    # ==========================================================================
    # EXPORT METHODS
    # ==========================================================================
    def export_trading_data(
        self,
        format: str = "csv",
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> Path | None:
        """
        Export trading data in specified format.

        Args:
            format: Export format (csv, json, excel, parquet)
            start_date: Start date for data export
            end_date: End date for data export

        Returns:
            Path to exported file if successful
        """
        if format not in EXPORT_FORMATS:
            self.logger.error("Invalid export format: %s", format)
            return None

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        export_file = EXPORT_DIR / f"tradov_export_{timestamp}.{format}"

        try:
            # Collect data from databases
            data = self._collect_trading_data(start_date, end_date)

            if not data:
                self.logger.warning("No data to export")
                return None

            # Export based on format
            if format == "csv":
                data.to_csv(export_file, index=False)
            elif format == "json":
                data.to_json(export_file, orient="records", indent=2)
            elif format == "excel":
                with pd.ExcelWriter(export_file, engine='openpyxl') as writer:
                    data.to_excel(writer, sheet_name='Trading Data', index=False)
            elif format == "parquet":
                data.to_parquet(export_file, index=False)

            self.logger.info("Data exported successfully: %s", export_file)
            return export_file

        except Exception as e:
            self.logger.error("Export failed: %s", e)
            return None

    def _collect_trading_data(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> pd.DataFrame | None:
        """
        Collect trading data from databases.

        Args:
            start_date: Start date for data collection
            end_date: End date for data collection

        Returns:
            DataFrame with trading data
        """
        db_file = DATA_DIR / "tradov_trades.db"

        if not db_file.exists():
            self.logger.warning("No trading database found")
            return None

        try:
            conn = sqlite3.connect(db_file)

            query = "SELECT * FROM trades WHERE 1=1"
            params = []

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY timestamp"

            df = pd.read_sql_query(query, conn, params=params)
            conn.close()

            return df

        except Exception as e:
            self.logger.error("Failed to collect trading data: %s", e)
            return None

    # ==========================================================================
    # DATABASE METHODS
    # ==========================================================================
    def optimize_databases(self) -> bool:
        """
        Optimize all SQLite databases.

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Optimizing databases")

        if not DATA_DIR.exists():
            return True

        success = True

        for db_file in DATA_DIR.glob("*.db"):
            try:
                conn = sqlite3.connect(db_file)

                # VACUUM to reclaim space
                conn.execute("VACUUM")

                # ANALYZE to update statistics
                conn.execute("ANALYZE")

                conn.close()
                self.logger.debug("Optimized: %s", db_file.name)

            except Exception as e:
                self.logger.error("Failed to optimize %s: %s", db_file.name, e)
                success = False

        return success

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def check_disk_space(self) -> dict[str, float]:
        """
        Check available disk space.

        Returns:
            Dictionary with disk space information in GB
        """
        try:
            stat = os.statvfs(TRADOV_HOME)

            total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
            available_gb = (stat.f_available * stat.f_frsize) / (1024**3)
            used_gb = total_gb - available_gb
            percent_used = (used_gb / total_gb) * 100

            return {
                "total_gb": total_gb,
                "available_gb": available_gb,
                "used_gb": used_gb,
                "percent_used": percent_used
            }

        except Exception as e:
            self.logger.error("Failed to check disk space: %s", e)
            return {}

    def generate_maintenance_report(self) -> str:
        """
        Generate a maintenance report.

        Returns:
            Formatted maintenance report string
        """
        report = []
        report.append("=" * 60)
        report.append("TRADOV SYSTEM MAINTENANCE REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Disk space
        disk_info = self.check_disk_space()
        if disk_info:
            report.append("DISK SPACE:")
            report.append(f"  Total: {disk_info['total_gb']:.2f} GB")
            report.append(f"  Used: {disk_info['used_gb']:.2f} GB ({disk_info['percent_used']:.1f}%)")
            report.append(f"  Available: {disk_info['available_gb']:.2f} GB")
            report.append("")

        # Log files
        if LOGS_DIR.exists():
            log_files = list(LOGS_DIR.glob("*.log"))
            total_size = sum(f.stat().st_size for f in log_files) / (1024**2)
            report.append("LOG FILES:")
            report.append(f"  Count: {len(log_files)}")
            report.append(f"  Total Size: {total_size:.2f} MB")
            report.append("")

        # Backups
        if BACKUP_DIR.exists():
            backup_files = list(BACKUP_DIR.glob("tradov_backup_*.tar.gz"))
            if backup_files:
                total_size = sum(f.stat().st_size for f in backup_files) / (1024**2)
                latest = max(backup_files, key=lambda f: f.stat().st_mtime)
                report.append("BACKUPS:")
                report.append(f"  Count: {len(backup_files)}")
                report.append(f"  Total Size: {total_size:.2f} MB")
                report.append(f"  Latest: {latest.name}")
                report.append("")

        # Databases
        if DATA_DIR.exists():
            db_files = list(DATA_DIR.glob("*.db"))
            if db_files:
                report.append("DATABASES:")
                for db in db_files:
                    size_mb = db.stat().st_size / (1024**2)
                    report.append(f"  {db.name}: {size_mb:.2f} MB")
                report.append("")

        report.append("=" * 60)

        return "\n".join(report)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def perform_daily_maintenance() -> bool:
    """
    Perform daily maintenance tasks.

    Returns:
        True if successful
    """
    utils = SystemUtilities()

    # Cleanup old logs (keep 30 days)
    utils.cleanup_logs(retention_days=30)

    # Cleanup temp files
    utils.cleanup_temp_files()

    # Optimize databases
    utils.optimize_databases()

    # Create daily backup (config only)
    utils.create_backup(backup_type=BackupType.CONFIG_ONLY, description="Daily backup")

    return True

def perform_weekly_maintenance() -> bool:
    """
    Perform weekly maintenance tasks.

    Returns:
        True if successful
    """
    utils = SystemUtilities()

    # Full cleanup
    utils.cleanup_all(retention_days=30)

    # Create weekly full backup
    utils.create_backup(backup_type=BackupType.FULL, description="Weekly full backup")

    # Generate and save report
    report = utils.generate_maintenance_report()
    report_file = LOGS_DIR / f"maintenance_report_{datetime.now(UTC).strftime('%Y%m%d')}.txt"
    with open(report_file, "w") as f:
        f.write(report)

    return True

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
def main():
    """Main entry point for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Tradov System Utilities - Maintenance and Management Tools"
    )

    parser.add_argument(
        "action",
        choices=["cleanup", "backup", "restore", "export", "report", "daily", "weekly"],
        help="Action to perform"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it"
    )

    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Days to retain files (for cleanup)"
    )

    parser.add_argument(
        "--backup-type",
        choices=["full", "incremental", "config", "data"],
        default="full",
        help="Type of backup to create"
    )

    parser.add_argument(
        "--backup-id",
        help="Backup ID for restore operation"
    )

    parser.add_argument(
        "--export-format",
        choices=["csv", "json", "excel", "parquet"],
        default="csv",
        help="Export format for data"
    )

    args = parser.parse_args()

    # Initialize utilities
    utils = SystemUtilities(dry_run=args.dry_run)

    # Perform requested action
    if args.action == "cleanup":
        report = utils.cleanup_all(retention_days=args.retention_days)
        print(f"Cleanup complete: {report.files_deleted} files deleted, "
              f"{report.space_freed_mb:.2f} MB freed")

    elif args.action == "backup":
        backup_type = BackupType[args.backup_type.upper()]
        info = utils.create_backup(backup_type=backup_type)
        if info:
            print(f"Backup created: {info.backup_id} ({info.size_mb:.2f} MB)")
        else:
            print("Backup failed")
            sys.exit(1)

    elif args.action == "restore":
        if not args.backup_id:
            print("Error: --backup-id required for restore")
            sys.exit(1)
        success = utils.restore_backup(args.backup_id)
        if success:
            print("Restore completed successfully")
        else:
            print("Restore failed")
            sys.exit(1)

    elif args.action == "export":
        export_file = utils.export_trading_data(format=args.export_format)
        if export_file:
            print(f"Data exported to: {export_file}")
        else:
            print("Export failed")
            sys.exit(1)

    elif args.action == "report":
        report = utils.generate_maintenance_report()
        print(report)

    elif args.action == "daily":
        success = perform_daily_maintenance()
        print("Daily maintenance completed" if success else "Daily maintenance failed")

    elif args.action == "weekly":
        success = perform_weekly_maintenance()
        print("Weekly maintenance completed" if success else "Weekly maintenance failed")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    main()
