#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6 to PySide6 Migration Script for Spyder Project

This script automatically migrates Python    args = parser.parse_args()

    migrator = PySide6ToPySide6Migrator()

    if args.all or args.target is None:s from PySide6 to PySide6.
It handles import statements, signal names, and common PySide6-specific syntax.

Usage:
    python migrate_to_pyside6.py <file_path>
    python migrate_to_pyside6.py --all  # Migrate all found PySide6 files

Author: GitHub Copilot
Date: 2025-09-28
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


class PySide6ToPySide6Migrator:
    """Handles migration from PySide6 to PySide6"""

    def __init__(self):
        self.replacements = {
            # Import replacements
            r"from PySide6": "from PySide6",
            r"import PySide6": "import PySide6",
            r"PySide6\.": "PySide6.",
            # Signal replacements
            r"Signal": "Signal",
            r"Slot": "Slot",
            # Other PySide6 specific replacements
            r"QApplication\.processEvents\(\)": "QApplication.processEvents()",
            r"QCoreApplication\.processEvents\(\)": "QCoreApplication.processEvents()",
        }

        self.comment_replacements = {
            r"PySide6": "PySide6",
            r"PySide6": "PySide6",
            r"PYSIDE6": "PYSIDE6",
        }

    def migrate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Migrate a single file from PySide6 to PySide6

        Returns:
            Tuple of (success, list_of_changes)
        """
        changes = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Apply main replacements
            for pattern, replacement in self.replacements.items():
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    matches = re.findall(pattern, content)
                    changes.append(
                        f"Replaced {len(matches)} occurrences of '{pattern}' with '{replacement}'"
                    )
                    content = new_content

            # Apply comment replacements
            for pattern, replacement in self.comment_replacements.items():
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    matches = re.findall(pattern, content)
                    changes.append(
                        f"Updated {len(matches)} comments/strings containing '{pattern}'"
                    )
                    content = new_content

            # Only write if changes were made
            if content != original_content:
                # Create backup
                backup_path = f"{file_path}.pre_pyside6_migration"
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(original_content)

                # Write migrated content
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                changes.append(f"Created backup: {backup_path}")
                return True, changes
            else:
                return False, ["No PySide6 imports found"]

        except Exception as e:
            return False, [f"Error migrating file: {str(e)}"]

    def find_PySide6_files(self, root_dir: str) -> List[str]:
        """Find all Python files that import PySide6"""
        PySide6_files = []

        for root, dirs, files in os.walk(root_dir):
            # Skip virtual environments and cache directories
            dirs[:] = [
                d for d in dirs if not d.startswith(".venv") and d != "__pycache__"
            ]

            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            if re.search(r"from PySide6|import PySide6", content):
                                PySide6_files.append(file_path)
                    except Exception:
                        continue

        return PySide6_files


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Python files from PySide6 to PySide6"
    )
    parser.add_argument("target", nargs="?", help="File path to migrate")
    parser.add_argument(
        "--all", action="store_true", help="Migrate all PySide6 files found"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Root directory to search (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )

    args = parser.parse_args()

    migrator = PySide6ToPySide6Migrator()

    if args.target == "--all" or args.target is None:
        # Find all PySide6 files
        PySide6_files = migrator.find_PySide6_files(args.root)

        if not PySide6_files:
            print("No PySide6 files found!")
            return

        print(f"Found {len(PySide6_files)} files with PySide6 imports:")
        for file_path in PySide6_files:
            print(f"  - {file_path}")

        if args.dry_run:
            print("\n[DRY RUN] Would migrate these files.")
            return

        print(f"\nMigrating {len(PySide6_files)} files...")

        for file_path in PySide6_files:
            success, changes = migrator.migrate_file(file_path)

            print(f"\n📁 {file_path}")
            if success:
                print("✅ Successfully migrated")
                for change in changes:
                    print(f"   • {change}")
            else:
                print("⚠️  No changes needed or error occurred")
                for change in changes:
                    print(f"   • {change}")

    else:
        # Migrate single file
        if not os.path.exists(args.target):
            print(f"Error: File {args.target} not found!")
            return

        if args.dry_run:
            print(f"[DRY RUN] Would migrate: {args.target}")
            return

        success, changes = migrator.migrate_file(args.target)

        print(f"📁 {args.target}")
        if success:
            print("✅ Successfully migrated")
            for change in changes:
                print(f"   • {change}")
        else:
            print("⚠️  No changes needed or error occurred")
            for change in changes:
                print(f"   • {change}")


if __name__ == "__main__":
    main()
