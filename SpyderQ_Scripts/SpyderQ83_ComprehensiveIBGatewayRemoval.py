#!/usr/bin/env python3
"""
SPYDER Q83 - Comprehensive IB Gateway Removal Utility
=====================================================

Series: SpyderQ_Scripts
Module: SpyderQ83_ComprehensiveIBGatewayRemoval.py
Purpose: Safely remove all IB Gateway related files, scripts, and modules
Author: SPYDER Development Team
Version: 1.0
Date: 2025-10-20

This script provides a comprehensive solution for removing all IB Gateway related
files from the SPYDER project while maintaining system integrity and providing
detailed logging of all removal operations.
"""

import os
import sys
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import argparse


@dataclass
class RemovalResult:
    """Result of a file removal operation"""
    file_path: str
    removed: bool
    reason: str = ""
    backup_path: str = ""
    file_size: int = 0


@dataclass
class RemovalStats:
    """Statistics for the removal operation"""
    total_files: int = 0
    removed_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    total_size_freed: int = 0
    backup_size: int = 0


class ComprehensiveIBGatewayRemover:
    """
    Comprehensive IB Gateway file remover with backup and logging capabilities.

    This class handles the safe removal of all IB Gateway related files while
    maintaining proper backups and detailed operation logs.
    """

    def __init__(self, project_root: Optional[Path] = None, backup_dir: Optional[Path] = None):
        """
        Initialize the IB Gateway remover.

        Args:
            project_root: Root directory of the SPYDER project
            backup_dir: Directory to store backups of removed files
        """
        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self.backup_dir = backup_dir or self.project_root / "backup_ib_gateway_removal"

        # Setup logging
        self._setup_logging()

        # Initialize statistics
        self.stats = RemovalStats()
        self.removal_results: List[RemovalResult] = []

        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)

        self.logger.info(f"Comprehensive IB Gateway Remover initialized")
        self.logger.info(f"Project root: {self.project_root}")
        self.logger.info(f"Backup directory: {self.backup_dir}")

    def _setup_logging(self):
        """Setup comprehensive logging for the removal process"""
        log_file = self.backup_dir / f"ib_gateway_removal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Create logger
        self.logger = logging.getLogger("ComprehensiveIBGatewayRemover")
        self.logger.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_files_to_remove(self) -> Dict[str, List[str]]:
        """
        Get the comprehensive list of files to remove.

        Returns:
            Dictionary with categories as keys and file lists as values
        """
        files_to_remove = {
            "diagnostic_fix_scripts": [
                "ib_gateway_1039_handshake_fix.py",
                "test_ib_gateway_1039_fix.py",
                "diagnose_ib_gateway_api_config.py",
                "fix_ib_gateway_trusted_ips.py",
                "fix_ib_gateway_port_config.py",
                "fix_gateway_complete.py",
                "fix_ib_gateway.py",
                "gateway_diagnostic_tool.py",
                "layer4_ib_gateway_diagnostic.py",
                "nuclear_jts_fixer.py",
                "nuclear_jts_fixer_auto.py",
                "create_minimal_jts_ini.py",
                "fix_complete_jts_ini_config.py",
                "force_enable_gateway_api.py",
                "auto_fix_gateway_api.py",
                "fix_and_restart_gateway.py",
            ],
            "shell_scripts": [
                "check_gateway_ready.sh",
                "fix_gateway_connection.sh",
                "restart_ib_gateway_with_trusted_ips.sh",
                "launch_spyder_with_gateway.sh",
                "launch_spyder_with_gateway.sh.backup",
                "launch_spyder_gateway.sh",
                "launch_spyder_with_1039_fixes.sh",
                "launch_spyder_direct.sh",
            ],
            "test_files": [
                "test_simple_gateway_connection.py",
                "test_existing_gateway.py",
                "test_minimal_gateway.py",
                "test_ipv6_gateway.py",
                "test_existing_connection_manager.py",
                "trigger_connections_simple.py",
                "quick_tws_api_test.py",
                "diagnose_tws_handshake.py",
                "ib_diagnostic.py",
                "simple_ib_test.py",
            ],
            "documentation": [
                "IB_GATEWAY_1039_HANDSHAKE_SOLUTION.md",
                "IB_GATEWAY_API_CONFIGURATION_SUMMARY.md",
                "IB_GATEWAY_REMOVAL_LIST.md",
                "IBKR_GATEWAY_API_COMPREHENSIVE_DIAGNOSTIC_REPORT.md",
                "IBKR_GATEWAY_API_SUPPORT_REPORT.md",
                "ENABLE_IB_GATEWAY_API_GUIDE.md",
                "SOLUTION_ENABLE_GATEWAY_API.md",
                "UPDATE_GATEWAY_SOLUTION.md",
                "GATEWAY_SOCKET_FIX.md",
                "LAYER4_NETWORK_DIAGNOSIS_REPORT.md",
                "COMPREHENSIVE_IB_GATEWAY_REMOVAL_LIST.md",
            ],
            "configuration": [
                "ib_gateway_config_template.json",
                "SimpleGatewayTest.java",
            ],
            "spyder_modules": [
                "SpyderB_Broker/SpyderB31_Specialized1039ConnectionManager.py",
                "SpyderG_GUI/SpyderG14_GatewayControlPanel.py",
                "SpyderG_GUI/SpyderG14_GatewayControlPanel.bak.py",
                "SpyderG_GUI/SpyderG05_TradingDashboard_Original_Backup.py",
                "SpyderG_GUI/SpyderG05_TradingDashboard.py.backup",
                "SpyderU_Utilities/SpyderU20_IBGatewayWatchdog.py",
                "SpyderU_Utilities/SpyderU21_IBGatewayJVMConfig.py",
                "SpyderI_Integration/SpyderI13_IBAutomaterUI.py",
            ],
            "spyder_scripts": [
                "SpyderQ_Scripts/SpyderQ81_RemoveIBGateway.py",
                "SpyderQ_Scripts/SpyderQ82_RemoveIBGatewayFiles.py",
                "SpyderQ_Scripts/archived/SpyderQ01_Setup.sh",
                "SpyderQ_Scripts/archived/SpyderQ03_InstallGateway.sh",
            ],
            "research_files": [
                "research/gateway_diagnostic_tool.py",
                "research/gateway_nuclear_restart.py",
                "research/nuclear_jts_fixer.py",
                "research/auto_fix_gateway_api.py",
                "research/spyder_auto_launcher.py",
                "research/bashrc_old.md",
            ],
            "maestro_scripts": [
                "Maestro Test Scripts/20250827_setup_docker_ib_gateway.sh",
                "Maestro Test Scripts/20250930_gateway_health_monitor.py",
            ],
            "config_files": [
                "config/config_gateway.py",
            ],
            "miscellaneous": [
                "new_container.md",
            ]
        }

        return files_to_remove

    def get_directories_to_remove(self) -> List[str]:
        """
        Get the list of directories to remove.

        Returns:
            List of directory paths to remove
        """
        directories = [
            "ib_gateway_tests",
            "ib_gateway_backup",
            "ib_gateway_logs",
            "ib_gateway_config",
            "ib_gateway_scripts",
            "backup",
        ]

        return directories

    def backup_file(self, file_path: Path) -> Optional[Path]:
        """
        Create a backup of a file before removal.

        Args:
            file_path: Path to the file to backup

        Returns:
            Path to the backup file, or None if backup failed
        """
        try:
            if not file_path.exists():
                return None

            # Create backup path maintaining directory structure
            relative_path = file_path.relative_to(self.project_root)
            backup_path = self.backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file to backup location
            shutil.copy2(file_path, backup_path)

            self.logger.debug(f"Backed up: {file_path} -> {backup_path}")
            return backup_path

        except Exception as e:
            self.logger.error(f"Failed to backup {file_path}: {e}")
            return None

    def remove_file(self, file_path: Path, create_backup: bool = True) -> RemovalResult:
        """
        Remove a single file with optional backup.

        Args:
            file_path: Path to the file to remove
            create_backup: Whether to create a backup before removal

        Returns:
            RemovalResult object with operation details
        """
        result = RemovalResult(file_path=str(file_path), removed=False)

        try:
            # Check if file exists
            if not file_path.exists():
                result.reason = "File does not exist"
                self.stats.skipped_files += 1
                return result

            # Get file size
            result.file_size = file_path.stat().st_size

            # Create backup if requested
            if create_backup:
                backup_path = self.backup_file(file_path)
                if backup_path:
                    result.backup_path = str(backup_path)
                    self.stats.backup_size += backup_path.stat().st_size

            # Remove the file
            file_path.unlink()
            result.removed = True
            self.stats.removed_files += 1
            self.stats.total_size_freed += result.file_size

            self.logger.info(f"Removed: {file_path} ({result.file_size} bytes)")

        except Exception as e:
            result.reason = str(e)
            self.stats.failed_files += 1
            self.logger.error(f"Failed to remove {file_path}: {e}")

        self.stats.total_files += 1
        return result

    def remove_directory(self, dir_path: Path, create_backup: bool = True) -> bool:
        """
        Remove a directory and all its contents.

        Args:
            dir_path: Path to the directory to remove
            create_backup: Whether to create a backup before removal

        Returns:
            True if removal was successful, False otherwise
        """
        try:
            if not dir_path.exists():
                self.logger.debug(f"Directory does not exist: {dir_path}")
                return True

            # Create backup if requested
            if create_backup:
                backup_path = self.backup_dir / dir_path.relative_to(self.project_root)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(dir_path, backup_path, dirs_exist_ok=True)
                self.logger.info(f"Backed up directory: {dir_path} -> {backup_path}")

            # Remove directory
            shutil.rmtree(dir_path)
            self.logger.info(f"Removed directory: {dir_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to remove directory {dir_path}: {e}")
            return False

    def remove_all_files(self, dry_run: bool = False, create_backup: bool = True) -> Dict[str, List[RemovalResult]]:
        """
        Remove all IB Gateway related files.

        Args:
            dry_run: If True, only simulate removal without actually removing files
            create_backup: Whether to create backups of removed files

        Returns:
            Dictionary with categories as keys and removal results as values
        """
        files_to_remove = self.get_files_to_remove()
        all_results = {}

        self.logger.info(f"Starting comprehensive IB Gateway file removal (dry_run={dry_run})")

        for category, file_list in files_to_remove.items():
            self.logger.info(f"Processing category: {category}")
            category_results = []

            for file_name in file_list:
                file_path = self.project_root / file_name

                if dry_run:
                    # Simulate removal
                    result = RemovalResult(file_path=str(file_path), removed=False)
                    if file_path.exists():
                        result.reason = "Dry run - file would be removed"
                        result.file_size = file_path.stat().st_size
                        self.stats.total_files += 1
                        self.stats.total_size_freed += result.file_size
                    else:
                        result.reason = "File does not exist"
                        self.stats.skipped_files += 1
                    category_results.append(result)
                else:
                    # Actual removal
                    result = self.remove_file(file_path, create_backup)
                    category_results.append(result)

            all_results[category] = category_results
            self.logger.info(f"Completed category: {category}")

        self.removal_results.extend([result for results in all_results.values() for result in results])
        return all_results

    def remove_all_directories(self, dry_run: bool = False, create_backup: bool = True) -> List[bool]:
        """
        Remove all IB Gateway related directories.

        Args:
            dry_run: If True, only simulate removal without actually removing directories
            create_backup: Whether to create backups of removed directories

        Returns:
            List of boolean values indicating success for each directory
        """
        directories = self.get_directories_to_remove()
        results = []

        self.logger.info(f"Starting directory removal (dry_run={dry_run})")

        for dir_name in directories:
            dir_path = self.project_root / dir_name

            if dry_run:
                if dir_path.exists():
                    self.logger.info(f"Dry run - directory would be removed: {dir_path}")
                    results.append(True)
                else:
                    self.logger.debug(f"Directory does not exist: {dir_path}")
                    results.append(True)
            else:
                result = self.remove_directory(dir_path, create_backup)
                results.append(result)

        return results

    def generate_removal_report(self) -> str:
        """
        Generate a comprehensive removal report.

        Returns:
            Path to the generated report file
        """
        report_path = self.backup_dir / f"removal_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_data = {
            "timestamp": datetime.now().isoformat(),
            "project_root": str(self.project_root),
            "backup_directory": str(self.backup_dir),
            "statistics": {
                "total_files": self.stats.total_files,
                "removed_files": self.stats.removed_files,
                "failed_files": self.stats.failed_files,
                "skipped_files": self.stats.skipped_files,
                "total_size_freed_mb": round(self.stats.total_size_freed / (1024 * 1024), 2),
                "backup_size_mb": round(self.stats.backup_size / (1024 * 1024), 2),
            },
            "removal_results": [
                {
                    "file_path": result.file_path,
                    "removed": result.removed,
                    "reason": result.reason,
                    "backup_path": result.backup_path,
                    "file_size": result.file_size,
                }
                for result in self.removal_results
            ]
        }

        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        self.logger.info(f"Removal report generated: {report_path}")
        return str(report_path)

    def print_summary(self):
        """Print a summary of the removal operation"""
        print("\n" + "="*60)
        print("IB GATEWAY REMOVAL SUMMARY")
        print("="*60)
        print(f"Total files processed: {self.stats.total_files}")
        print(f"Files successfully removed: {self.stats.removed_files}")
        print(f"Files failed to remove: {self.stats.failed_files}")
        print(f"Files skipped (not found): {self.stats.skipped_files}")
        print(f"Total size freed: {self.stats.total_size_freed / (1024 * 1024):.2f} MB")
        print(f"Backup size: {self.stats.backup_size / (1024 * 1024):.2f} MB")
        print(f"Backup location: {self.backup_dir}")
        print("="*60)


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description="Comprehensive IB Gateway File Removal Utility"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate removal without actually removing files"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backups of removed files"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Root directory of the SPYDER project"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Directory to store backups of removed files"
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Only remove files, not directories"
    )
    parser.add_argument(
        "--dirs-only",
        action="store_true",
        help="Only remove directories, not files"
    )

    args = parser.parse_args()

    # Create remover instance
    remover = ComprehensiveIBGatewayRemover(
        project_root=args.project_root,
        backup_dir=args.backup_dir
    )

    try:
        # Remove files
        if not args.dirs_only:
            file_results = remover.remove_all_files(
                dry_run=args.dry_run,
                create_backup=not args.no_backup
            )

        # Remove directories
        if not args.files_only:
            dir_results = remover.remove_all_directories(
                dry_run=args.dry_run,
                create_backup=not args.no_backup
            )

        # Generate report
        report_path = remover.generate_removal_report()

        # Print summary
        remover.print_summary()

        if not args.dry_run:
            print(f"\nDetailed report saved to: {report_path}")
            print(f"Check the log file in the backup directory for detailed information.")
        else:
            print("\nDRY RUN COMPLETED - No files were actually removed")
            print("Run without --dry-run to perform the actual removal.")

        return 0

    except KeyboardInterrupt:
        print("\n\nRemoval process interrupted by user")
        return 1
    except Exception as e:
        print(f"\nError during removal process: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())