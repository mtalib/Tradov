#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix remaining Spyder references in Python files, especially in imports
"""

import os
import re
from pathlib import Path
from typing import List, Tuple, Set

def fix_imports_in_file(file_path: Path, dry_run: bool = True) -> Tuple[bool, List[str]]:
    """
    Fix all remaining Spyder references in a Python file.
    
    Args:
        file_path: Path to the file
        dry_run: If True, only show what would change
        
    Returns:
        Tuple of (was_modified, list_of_changes)
    """
    changes = []
    
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Make a copy for modifications
        modified_content = original_content
        
        # Comprehensive replacement patterns
        replacements = [
            # Fix module imports - more specific patterns first
            (r'\.Spyder([A-Z])(\d+)_', r'.Spyder\1\2_'),  # e.g., .SpyderA01_Main
            (r'import Spyder([A-Z])(\d+)_', r'import Spyder\1\2_'),  # import SpyderA01_Main
            (r'from SpyderA_Core\.Spyder', 'from SpyderA_Core.Spyder'),
            (r'from SpyderB_Broker\.Spyder', 'from SpyderB_Broker.Spyder'),
            (r'from SpyderC_MarketData\.Spyder', 'from SpyderC_MarketData.Spyder'),
            (r'from SpyderD_Strategies\.Spyder', 'from SpyderD_Strategies.Spyder'),
            (r'from SpyderE_Risk\.Spyder', 'from SpyderE_Risk.Spyder'),
            (r'from SpyderF_Analysis\.Spyder', 'from SpyderF_Analysis.Spyder'),
            (r'from SpyderG_GUI\.Spyder', 'from SpyderG_GUI.Spyder'),
            (r'from SpyderH_Storage\.Spyder', 'from SpyderH_Storage.Spyder'),
            (r'from SpyderI_Backtest\.Spyder', 'from SpyderI_Backtest.Spyder'),
            (r'from SpyderJ_Alerts\.Spyder', 'from SpyderJ_Alerts.Spyder'),
            (r'from SpyderK_Reports\.Spyder', 'from SpyderK_Reports.Spyder'),
            (r'from SpyderL_ML\.Spyder', 'from SpyderL_ML.Spyder'),
            (r'from SpyderM_MarketMicrostructure\.Spyder', 'from SpyderM_MarketMicrostructure.Spyder'),
            (r'from SpyderN_OptionsAnalytics\.Spyder', 'from SpyderN_OptionsAnalytics.Spyder'),
            (r'from SpyderO_RiskControl\.Spyder', 'from SpyderO_RiskControl.Spyder'),
            (r'from SpyderP_PaperTrading\.Spyder', 'from SpyderP_PaperTrading.Spyder'),
            (r'from SpyderQ_QuantitativeModels\.Spyder', 'from SpyderQ_QuantitativeModels.Spyder'),
            (r'from SpyderU_Utilities\.Spyder', 'from SpyderU_Utilities.Spyder'),
            
            # Fix class names that were missed
            (r'\bSpyderLogger\b', 'SpyderLogger'),
            (r'\bSpyderErrorHandler\b', 'SpyderErrorHandler'),
            (r'\bSpyderConfig\b', 'SpyderConfig'),
            (r'\bSpyderDatabase\b', 'SpyderDatabase'),
            (r'\bSpyderApplication\b', 'SpyderApplication'),
            (r'\bTempSpyderLogger\b', 'TempSpyderLogger'),
            
            # Fix any remaining standalone "Spyder" references
            (r'\bSpyder\b(?![-_])', 'Spyder'),  # Standalone "Spyder" not followed by - or _
            (r'\bspyder\b(?![-_])', 'spyder'),  # Lowercase version
            (r'\bSPYDER\b(?![-_])', 'SPYDER'),  # Uppercase version
            
            # Fix string references
            (r'"Spyder ', '"Spyder '),
            (r"'Spyder ", "'Spyder "),
            (r' Spyder"', ' Spyder"'),
            (r" Spyder'", " Spyder'"),
            
            # Fix comments
            (r'# Spyder', '# Spyder'),
            (r'# spyder', '# spyder'),
            
            # Fix docstrings
            (r'"""Spyder', '"""Spyder'),
            (r"'''Spyder", "'''Spyder"),
        ]
        
        # Apply replacements and track changes
        for pattern, replacement in replacements:
            # Find all matches before replacement
            matches = re.findall(pattern, modified_content)
            if matches:
                # Count unique occurrences
                if isinstance(matches[0], tuple):
                    # For patterns with groups
                    count = len(matches)
                else:
                    # For simple patterns
                    count = len(set(matches))
                
                if count > 0:
                    changes.append(f"{pattern} → {replacement} ({count} occurrences)")
                    modified_content = re.sub(pattern, replacement, modified_content)
        
        # Check if file was modified
        was_modified = original_content != modified_content
        
        # Write changes if not dry run
        if was_modified and not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
        
        return was_modified, changes
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False, []

def find_remaining_spyder_references(project_root: Path) -> Set[str]:
    """Find any remaining Spyder references in the project."""
    remaining = set()
    
    for file_path in project_root.rglob("*.py"):
        # Skip virtual environments
        if '.venv' in file_path.parts or 'venv' in file_path.parts:
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Search for various Spyder patterns
            patterns = [
                r'Spyder[A-Z]\d+_\w+',  # SpyderA01_Main
                r'\.Spyder\w+',         # .SpyderLogger
                r'\bSpyder\b',          # Standalone Spyder
                r'spyder',              # Lowercase
                r'SPYDER',              # Uppercase
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                if matches:
                    rel_path = file_path.relative_to(project_root)
                    remaining.add(f"{rel_path}: {', '.join(set(matches)[:3])}")
                    
        except Exception:
            pass
            
    return remaining

def main():
    """Main function to fix remaining Spyder references."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix remaining Spyder references in Python files')
    parser.add_argument(
        'project_root',
        help='Path to the Spyder project root'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the updates (default is dry run)'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check for remaining Spyder references'
    )
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root)
    if not project_root.exists():
        print(f"Error: Project root does not exist: {project_root}")
        return 1
    
    # If check-only mode
    if args.check_only:
        print("Checking for remaining Spyder references...")
        remaining = find_remaining_spyder_references(project_root)
        
        if remaining:
            print(f"\nFound {len(remaining)} files with Spyder references:")
            for ref in sorted(remaining)[:20]:  # Show first 20
                print(f"  - {ref}")
            if len(remaining) > 20:
                print(f"  ... and {len(remaining) - 20} more")
        else:
            print("✅ No Spyder references found!")
        return 0
    
    dry_run = not args.execute
    
    print("="*60)
    print(f"{'DRY RUN: ' if dry_run else ''}Fixing remaining Spyder references")
    print(f"Project root: {project_root}")
    print("="*60)
    
    # Find all Python files
    python_files = list(project_root.rglob("*.py"))
    total_files = len(python_files)
    modified_files = 0
    total_changes = 0
    
    print(f"\nProcessing {total_files} Python files...")
    
    # Process each file
    for i, file_path in enumerate(python_files, 1):
        # Skip virtual environments
        if '.venv' in file_path.parts or 'venv' in file_path.parts:
            continue
            
        was_modified, changes = fix_imports_in_file(file_path, dry_run)
        
        if was_modified:
            modified_files += 1
            total_changes += len(changes)
            
            rel_path = file_path.relative_to(project_root)
            print(f"\n[{i}/{total_files}] {rel_path}")
            
            for change in changes[:5]:  # Show first 5 changes
                print(f"  - {change}")
            if len(changes) > 5:
                print(f"  ... and {len(changes) - 5} more changes")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Files scanned: {total_files}")
    print(f"Files modified: {modified_files}")
    print(f"Total replacements: {total_changes}")
    
    if dry_run:
        print("\nThis was a DRY RUN - no files were actually modified")
        print("To apply changes, run with --execute flag")
        
        # Also show remaining references
        print("\nChecking for patterns that would remain after fix...")
        remaining = find_remaining_spyder_references(project_root)
        if remaining:
            print(f"Note: {len(remaining)} files may still need manual review")
    else:
        print("\n✅ All files have been updated!")
        
        # Final check
        print("\nFinal check for remaining references...")
        remaining = find_remaining_spyder_references(project_root)
        if remaining:
            print(f"⚠️  {len(remaining)} files still contain Spyder references")
            print("These may need manual review.")
        else:
            print("✅ No Spyder references remaining!")
    
    return 0

if __name__ == "__main__":
    exit(main())
