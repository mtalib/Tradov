#!/usr/bin/env python3
"""
Spyder Matplotlib to Plotly Migration Script

Purpose: Automatically migrate matplotlib usage to Plotly across the Spyder codebase
         to align with project preferences for Plotly as the primary visualization library.

Author: Spyder Development Team
Created: 2025-01-29

Usage:
    python scripts/migrate_to_plotly.py [--dry-run] [--backup] [--verbose]

    --dry-run: Show what would be changed without making changes
    --backup: Create backup files before modification (recommended)
    --verbose: Show detailed progress information
"""

import os
import re
import sys
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Migration patterns for common matplotlib -> Plotly conversions
MIGRATION_PATTERNS = [
    # Import replacements
    {
        "pattern": r"import matplotlib\.pyplot as plt",
        "replacement": "import plotly.graph_objects as go\nimport plotly.express as px",
        "description": "Replace matplotlib pyplot import with Plotly",
    },
    {
        "pattern": r"from matplotlib\.figure import Figure",
        "replacement": "import plotly.graph_objects as go",
        "description": "Replace matplotlib Figure import",
    },
    {
        "pattern": r"from matplotlib\.backends\.backend_qtagg import FigureCanvasQTAgg as FigureCanvas",
        "replacement": "# Plotly integration - no direct canvas equivalent needed",
        "description": "Remove matplotlib Qt backend import",
    },
    {
        "pattern": r"import matplotlib\.patches as patches",
        "replacement": "# Plotly shapes used instead of matplotlib patches",
        "description": "Remove matplotlib patches import",
    },
    {
        "pattern": r'matplotlib\.use\(["\']QtAgg["\']\)',
        "replacement": "# Plotly does not require backend configuration",
        "description": "Remove matplotlib backend configuration",
    },
    # Unused imports (just remove)
    {
        "pattern": r"import matplotlib\.pyplot as plt\n(?!.*plt\.)",
        "replacement": "",
        "description": "Remove unused matplotlib pyplot import",
        "flags": re.MULTILINE | re.DOTALL,
    },
    # Figure creation patterns
    {
        "pattern": r"self\.figure = Figure\(figsize=\((\d+),\s*(\d+)\),\s*dpi=\d+\)",
        "replacement": r"# Plotly figure created as needed - no persistent figure object",
        "description": "Replace matplotlib Figure creation",
    },
    # Canvas patterns
    {
        "pattern": r"self\.canvas = FigureCanvas\(self\.figure\)",
        "replacement": "# Plotly widgets handle their own display",
        "description": "Replace matplotlib canvas creation",
    },
    # Common plotting patterns
    {
        "pattern": r"ax\.plot\(",
        "replacement": "go.Scatter(",
        "description": "Convert matplotlib plot to Plotly scatter",
    },
    # Rectangle patches (for candlesticks)
    {
        "pattern": r"patches\.Rectangle\(",
        "replacement": "go.Scatter(  # Convert to Plotly candlestick or bar",
        "description": "Convert matplotlib Rectangle to Plotly equivalent",
    },
]

# Files to exclude from migration
EXCLUDE_PATTERNS = [
    r"__pycache__",
    r"\.pyc$",
    r"\.git",
    r"\.pytest_cache",
    r"backup_",
    r"_backup\.py$",
    r"test_.*\.py$",  # Skip test files for now
    r"scripts/migrate_to_plotly\.py$",  # Don't migrate this script itself
]

# Priority order for file processing (process these first)
PRIORITY_FILES = [
    "SpyderG_GUI/SpyderG05_TradingDashboard.py",
    "SpyderF_Analysis/SpyderF12_AdvancedBacktestingEngine.py",
    "SpyderF_Analysis/SpyderF13_ModelValidation.py",
    "SpyderF_Analysis/SpyderF14_MarketMicrostructure.py",
]


class PlotlyMigrator:
    def __init__(self, dry_run=False, create_backup=True, verbose=False):
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.verbose = verbose
        self.changes_made = []
        self.files_processed = []
        self.errors = []

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        if self.verbose or level == "ERROR":
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")

    def should_exclude_file(self, file_path: str) -> bool:
        """Check if file should be excluded from migration"""
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, file_path):
                return True
        return False

    def create_backup_file(self, file_path: str) -> str:
        """Create backup of file before modification"""
        if not self.create_backup:
            return ""

        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(file_path, backup_path)
        self.log(f"Created backup: {backup_path}")
        return backup_path

    def migrate_file(self, file_path: str) -> bool:
        """Migrate a single file from matplotlib to Plotly"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            changes_in_file = []

            # Apply migration patterns
            for pattern_info in MIGRATION_PATTERNS:
                pattern = pattern_info["pattern"]
                replacement = pattern_info["replacement"]
                description = pattern_info["description"]
                flags = pattern_info.get("flags", 0)

                if flags:
                    new_content = re.sub(pattern, replacement, content, flags=flags)
                else:
                    new_content = re.sub(pattern, replacement, content)

                if new_content != content:
                    changes_in_file.append(description)
                    content = new_content
                    self.log(f"Applied: {description}")

            # Only write if changes were made
            if content != original_content:
                if not self.dry_run:
                    # Create backup first
                    backup_path = self.create_backup_file(file_path)

                    # Write updated content
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

                self.changes_made.append(
                    {
                        "file": file_path,
                        "changes": changes_in_file,
                        "backup": backup_path if not self.dry_run else "dry-run",
                    }
                )

                return True

        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            self.log(error_msg, "ERROR")
            self.errors.append(error_msg)
            return False

        return False

    def find_python_files(self, root_dir: str) -> List[str]:
        """Find all Python files that need migration"""
        python_files = []

        for root, dirs, files in os.walk(root_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, root_dir)

                    if not self.should_exclude_file(relative_path):
                        python_files.append(file_path)

        return python_files

    def sort_files_by_priority(self, files: List[str]) -> List[str]:
        """Sort files by priority (important files first)"""
        priority_files = []
        regular_files = []

        for file_path in files:
            relative_path = os.path.relpath(file_path, os.getcwd())

            is_priority = any(
                priority_file in relative_path for priority_file in PRIORITY_FILES
            )

            if is_priority:
                priority_files.append(file_path)
            else:
                regular_files.append(file_path)

        return priority_files + regular_files

    def run_migration(self, root_dir: str = "."):
        """Run the complete migration process"""
        self.log("Starting Matplotlib to Plotly migration...")
        self.log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")
        self.log(f"Backup: {'ENABLED' if self.create_backup else 'DISABLED'}")

        # Find all Python files
        python_files = self.find_python_files(root_dir)
        self.log(f"Found {len(python_files)} Python files to check")

        # Sort by priority
        sorted_files = self.sort_files_by_priority(python_files)

        # Process each file
        files_changed = 0
        for file_path in sorted_files:
            relative_path = os.path.relpath(file_path, root_dir)
            self.log(f"Processing: {relative_path}")

            if self.migrate_file(file_path):
                files_changed += 1
                self.log(f"✅ Updated: {relative_path}")
            else:
                self.log(f"⏭️  No changes: {relative_path}")

            self.files_processed.append(relative_path)

        # Print summary
        self.print_summary(files_changed)

    def print_summary(self, files_changed: int):
        """Print migration summary"""
        print("\n" + "=" * 60)
        print("MATPLOTLIB TO PLOTLY MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Files processed: {len(self.files_processed)}")
        print(f"Files changed: {files_changed}")
        print(f"Errors: {len(self.errors)}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")

        if self.changes_made:
            print(f"\nChanged files:")
            for change in self.changes_made:
                print(f"  📁 {change['file']}")
                for desc in change["changes"]:
                    print(f"     • {desc}")
                if change["backup"] != "dry-run":
                    print(f"     💾 Backup: {change['backup']}")

        if self.errors:
            print(f"\nErrors encountered:")
            for error in self.errors:
                print(f"  ❌ {error}")

        print("\n" + "=" * 60)

        if not self.dry_run and files_changed > 0:
            print("✅ Migration completed successfully!")
            print("🔍 Please review the changes and test your application.")
            print("📋 Consider updating your requirements.txt to prioritize Plotly.")
        elif self.dry_run:
            print("ℹ️  This was a dry run. Use --live to apply changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Spyder codebase from matplotlib to Plotly"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--live", action="store_true", help="Apply changes (opposite of --dry-run)"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Skip creating backup files"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress information",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to process (default: current directory)",
    )

    args = parser.parse_args()

    # Default to dry-run unless --live is specified
    dry_run = not args.live
    create_backup = not args.no_backup

    if dry_run:
        print("🔍 Running in DRY RUN mode (use --live to apply changes)")
    else:
        print("⚡ Running in LIVE mode - changes will be applied!")
        response = input("Continue? (y/N): ")
        if response.lower() != "y":
            print("Migration cancelled.")
            return

    migrator = PlotlyMigrator(
        dry_run=dry_run, create_backup=create_backup, verbose=args.verbose
    )

    migrator.run_migration(args.root)


if __name__ == "__main__":
    main()
