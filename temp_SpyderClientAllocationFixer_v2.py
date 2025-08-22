#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities 
Module: temp_SpyderClientAllocationFixer_v2.py 
Purpose: IMPROVED System-wide Client ID Allocation Scanner with Reduced False Positives
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-23 Time: 10:30:00  

Module Description:
    Version 2 of the client allocation scanner with improved accuracy and reduced 
    false positives. Features context-aware scanning, better pattern matching, 
    and more compact reporting. Identifies ONLY real client allocation issues 
    while ignoring legitimate client references and already-fixed code.
"""

import os
import re
import sys
import ast
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from collections import defaultdict

# ==============================================================================
# CONSTANTS - CORRECT ALLOCATION
# ==============================================================================
CORRECT_CLIENT_ALLOCATION = {
    1: "Orders",       # ORDER EXECUTION (HIGHEST PRIORITY)
    2: "Admin",        # ADMINISTRATIVE 
    3: "Core",         # CORE DATA
    4: "Options",      # SPY OPTIONS
    5: "Volatility",   # VOLATILITY DATA
    6: "Internals",    # MARKET INTERNALS
    7: "Major ETFs",   # MAJOR INDICES
    8: "Extended",     # EXTENDED ASSETS
    9: "Sector ETFs",  # SECTOR ETFS
    10: "International" # INTERNATIONAL
}

# Files to exclude from scanning
EXCLUDE_FILES = [
    '__pycache__',
    '.git',
    '.pyc',
    'temp_SpyderClientAllocationFixer',  # Don't scan ourselves
    '_FIXED.py',  # Skip already fixed files
    '.backup',
    'test_',
    'node_modules',
    '.vscode',
    'venv',
    'env'
]

# Files we know are already fixed
FIXED_FILES = [
    'SpyderB13_GatewayConfig_FIXED.py',
    'SpyderG07_PrometheusMetricsDisplay_FIXED.py',
    'SpyderG06_ClientMonitorPanel_FIXED.py',
    'SpyderG05_TradingDashboard.py'  # Manually fixed line 2201
]

# ==============================================================================
# IMPROVED SEARCH PATTERNS
# ==============================================================================
class PatternMatcher:
    """Context-aware pattern matching to reduce false positives"""
    
    def __init__(self):
        # Define specific problematic patterns with context
        self.wrong_patterns = {
            'WRONG_ORDER': {
                'pattern': r'["\']Admin["\'],\s*["\']Orders["\']',
                'description': 'Admin before Orders in array',
                'severity': 'HIGH'
            },
            'CLIENT_0_DEFINITION': {
                'pattern': r'CLIENT[\s_]0["\s:]+["\']?\w+',
                'description': 'Client 0 definition (should start at 1)',
                'severity': 'HIGH'
            },
            'RANGE_0_8': {
                'pattern': r'range\s*\(\s*0\s*,\s*[89]\s*\)',
                'description': 'Range starting at 0 or ending at 8',
                'severity': 'HIGH'
            },
            'RANGE_1_9': {
                'pattern': r'range\s*\(\s*1\s*,\s*9\s*\)',
                'description': 'Range 1-9 (should be 1-11 for 1-10 inclusive)',
                'severity': 'MEDIUM'
            },
            'MAX_CLIENT_9': {
                'pattern': r'max_client[_id]*\s*[=<]\s*9(?!\d)',
                'description': 'Max client set to 9 (should be 10)',
                'severity': 'MEDIUM'
            },
            'CLIENT_DICT_0_8': {
                'pattern': r'CLIENT_DEFINITIONS\s*=\s*\{[^}]*"CLIENT\s*0"',
                'description': 'CLIENT_DEFINITIONS starting with Client 0',
                'severity': 'HIGH'
            }
        }
        
        # Patterns that indicate CORRECT implementation (to skip)
        self.correct_patterns = [
            r'range\s*\(\s*1\s*,\s*11\s*\)',  # Correct range(1, 11)
            r'["\']Orders["\'],\s*["\']Admin["\']',  # Correct order
            r'client_id\s*==\s*1.*Orders',  # Client 1 = Orders
            r'client_id\s*==\s*2.*Admin',   # Client 2 = Admin
            r'DEFAULT_MAX_CLIENT_ID\s*=\s*10',  # Correct max
        ]
    
    def should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped"""
        line_stripped = line.strip()
        
        # Skip comments
        if line_stripped.startswith('#'):
            return True
            
        # Skip docstrings
        if '"""' in line_stripped or "'''" in line_stripped:
            return True
            
        # Skip logging statements
        if 'logger.' in line_stripped or 'print(' in line_stripped:
            return True
            
        # Skip test assertions
        if 'assert' in line_stripped or 'test_' in line_stripped:
            return True
            
        return False
    
    def check_for_issues(self, line: str, line_num: int, file_path: Path) -> Optional[Dict]:
        """Check a line for client allocation issues"""
        
        if self.should_skip_line(line):
            return None
        
        # Check if line contains correct pattern (skip if it does)
        for correct_pattern in self.correct_patterns:
            if re.search(correct_pattern, line, re.IGNORECASE):
                return None
        
        # Check for problematic patterns
        for issue_type, issue_info in self.wrong_patterns.items():
            if re.search(issue_info['pattern'], line, re.IGNORECASE):
                return {
                    'file': file_path,
                    'line_number': line_num,
                    'line_content': line.strip(),
                    'issue_type': issue_type,
                    'description': issue_info['description'],
                    'severity': issue_info['severity']
                }
        
        return None

# ==============================================================================
# SCANNER CLASS
# ==============================================================================
class ImprovedClientScanner:
    """Improved scanner with reduced false positives"""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.pattern_matcher = PatternMatcher()
        self.issues_found = []
        self.files_scanned = 0
        self.files_skipped = 0
        self.critical_files = {}
        
        # Track specific modules we care about
        self.target_modules = {
            'SpyderB13_GatewayConfig.py': 'Broker Configuration',
            'SpyderB14_MultiClientWatchdog.py': 'Multi-Client Watchdog',
            'SpyderG05_TradingDashboard.py': 'Trading Dashboard',
            'SpyderG06_ClientMonitorPanel.py': 'Client Monitor Panel',
            'SpyderG07_PrometheusMetricsDisplay.py': 'Prometheus Metrics'
        }
    
    def should_skip_file(self, file_path: Path) -> bool:
        """Determine if file should be skipped"""
        file_name = file_path.name
        
        # Skip if in exclude list
        for exclude in EXCLUDE_FILES:
            if exclude in str(file_path):
                return True
        
        # Skip if already fixed
        if file_name in FIXED_FILES:
            self.files_skipped += 1
            return True
        
        # Skip non-Python files
        if not file_name.endswith('.py'):
            return True
        
        # Skip test files
        if 'test' in file_name.lower():
            return True
            
        return False
    
    def scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for issues"""
        if self.should_skip_file(file_path):
            return []
        
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            self.files_scanned += 1
            
            # Track if this is a critical file
            if file_path.name in self.target_modules:
                self.critical_files[file_path.name] = []
            
            # Check each line
            for line_num, line in enumerate(lines, 1):
                issue = self.pattern_matcher.check_for_issues(line, line_num, file_path)
                if issue:
                    issues.append(issue)
                    
                    # Track critical file issues
                    if file_path.name in self.target_modules:
                        self.critical_files[file_path.name].append(issue)
        
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
        
        return issues
    
    def scan_project(self) -> None:
        """Scan entire project"""
        print(f"\n🔍 IMPROVED SCANNER V2 - Starting scan")
        print(f"📂 Project root: {self.project_root}")
        print("=" * 60)
        
        # Walk through all directories
        for root, dirs, files in os.walk(self.project_root):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(ex in d for ex in EXCLUDE_FILES)]
            
            current_dir = Path(root)
            
            # Only process Spyder directories and subdirectories
            if not any(part.startswith('Spyder') for part in current_dir.parts):
                if current_dir != self.project_root:
                    continue
            
            for file_name in files:
                file_path = current_dir / file_name
                issues = self.scan_file(file_path)
                if issues:
                    self.issues_found.extend(issues)
    
    def generate_compact_report(self) -> None:
        """Generate a compact, focused report"""
        print("\n" + "=" * 80)
        print("📊 SCAN RESULTS SUMMARY")
        print("=" * 80)
        
        print(f"✅ Files scanned: {self.files_scanned}")
        print(f"⏭️  Files skipped: {self.files_skipped}")
        print(f"🚨 Total issues found: {len(self.issues_found)}")
        
        if not self.issues_found:
            print("\n✨ No client allocation issues detected!")
            return
        
        # Group issues by severity
        by_severity = defaultdict(list)
        for issue in self.issues_found:
            by_severity[issue['severity']].append(issue)
        
        # Report critical files first
        if self.critical_files:
            print("\n" + "=" * 80)
            print("🎯 CRITICAL MODULE ISSUES")
            print("=" * 80)
            
            for module_name, module_issues in self.critical_files.items():
                if module_issues:
                    print(f"\n📁 {module_name} ({self.target_modules[module_name]})")
                    print("-" * 40)
                    for issue in module_issues:
                        print(f"  Line {issue['line_number']:4d}: {issue['description']}")
                        print(f"  {'':10} {issue['line_content'][:60]}...")
        
        # Summary by severity
        print("\n" + "=" * 80)
        print("⚠️  ISSUES BY SEVERITY")
        print("=" * 80)
        
        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            if severity in by_severity:
                issues = by_severity[severity]
                print(f"\n{severity} Priority: {len(issues)} issues")
                
                # Group by file for compact display
                by_file = defaultdict(list)
                for issue in issues:
                    rel_path = issue['file'].relative_to(self.project_root)
                    by_file[str(rel_path)].append(issue)
                
                # Show up to 3 files per severity
                for idx, (file_path, file_issues) in enumerate(list(by_file.items())[:3]):
                    print(f"  • {file_path}")
                    for issue in file_issues[:2]:  # Show max 2 issues per file
                        print(f"    Line {issue['line_number']}: {issue['description']}")
                
                if len(by_file) > 3:
                    print(f"  ... and {len(by_file) - 3} more files")
        
        # Quick fix suggestions
        print("\n" + "=" * 80)
        print("💡 QUICK FIX GUIDE")
        print("=" * 80)
        
        fix_guide = {
            'WRONG_ORDER': 'Change ["Admin", "Orders"] to ["Orders", "Admin"]',
            'CLIENT_0_DEFINITION': 'Start client definitions at 1, not 0',
            'RANGE_0_8': 'Change range(0, 9) to range(1, 11)',
            'RANGE_1_9': 'Change range(1, 9) to range(1, 11)',
            'MAX_CLIENT_9': 'Change max_client = 9 to max_client = 10',
            'CLIENT_DICT_0_8': 'Update CLIENT_DEFINITIONS to use 1-10 range'
        }
        
        found_types = set(issue['issue_type'] for issue in self.issues_found)
        for issue_type in found_types:
            if issue_type in fix_guide:
                print(f"  • {issue_type}: {fix_guide[issue_type]}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution"""
    print("=" * 80)
    print("🔍 SPYDER CLIENT ALLOCATION SCANNER V2")
    print("   Improved accuracy with reduced false positives")
    print("=" * 80)
    
    # Parse arguments
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    # Initialize scanner
    scanner = ImprovedClientScanner()
    
    # Run scan
    scanner.scan_project()
    
    # Generate report
    scanner.generate_compact_report()
    
    # Show next steps
    print("\n" + "=" * 80)
    print("📝 NEXT STEPS")
    print("=" * 80)
    print("1. Review HIGH severity issues first")
    print("2. Check critical modules (SpyderB13, SpyderB14, etc.)")
    print("3. Apply fixes manually and test each module")
    print("4. Re-run scanner to verify: python temp_SpyderClientAllocationFixer_v2.py")
    
    # If verbose, show all issues
    if verbose and scanner.issues_found:
        print("\n" + "=" * 80)
        print("📋 VERBOSE: All Issues")
        print("=" * 80)
        for issue in scanner.issues_found:
            rel_path = issue['file'].relative_to(scanner.project_root)
            print(f"{rel_path}:{issue['line_number']}")
            print(f"  {issue['description']}")
            print(f"  {issue['line_content']}")
            print()

if __name__ == "__main__":
    main()
