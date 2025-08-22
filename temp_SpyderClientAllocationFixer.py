#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities [Application Name] [Series Letter] [Series Name] 
Module: temp_SpyderClientAllocationFixer.py [Application Name][Series Letter] [Module Number]_[Purpose].py 
Purpose: System-wide Client ID Allocation Consistency Scanner
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-22 Time: 14:45:00  

Module Description:
    Comprehensive system-wide scanner to identify client ID allocation 
    inconsistencies across the Spyder codebase. Searches for modules using 
    outdated client ranges (0-8, 1-9) and incorrect client purposes, then 
    provides detailed reports and suggestions based on the authoritative 
    SpyderB08 specification. SCAN ONLY - all fixes must be applied manually 
    after careful review to ensure trading system stability.
    
    CORRECT CLIENT ALLOCATION (1-10):
    - Client 1: ORDER EXECUTION (HIGHEST PRIORITY)
    - Client 2: ADMINISTRATIVE OPERATIONS  
    - Client 3: CORE DATA (SPY, SPX, /ES, VIX, TICK-NYSE)
    - Client 4: SPY OPTIONS CHAINS (0DTE, 1DTE)
    - Client 5: VOLATILITY INDICATORS (VIX9D, VXV, VXMT, VVIV, UVXY)
    - Client 6: MARKET INTERNALS (TRIN, ADD, CPC, PCALL, SKEW, VUD)
    - Client 7: MAJOR INDICES (DIA, QQQ, IWM, 1DTE OPTIONS)
    - Client 8: EXTENDED ASSETS (TLT, LQD, DXY, GLD, WEEKLY OPTIONS)
    - Client 9: SECTOR ETFS (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLC, XLB)
    - Client 10: INTERNATIONAL MARKETS (FTLC, AUD.JPY, DAX, HSI, EWJ, etc.)
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import shutil

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Correct client allocation according to SpyderB08_MultiClientDataManager.py
CORRECT_CLIENT_ALLOCATION = {
    1: "Orders",      # ORDER_EXECUTION (HIGHEST PRIORITY)
    2: "Admin",       # ADMINISTRATIVE 
    3: "Core",        # CORE_DATA
    4: "Options",     # OPTIONS_DATA
    5: "Volatility",  # VOLATILITY_DATA
    6: "Internals",   # MARKET_INTERNALS
    7: "Major ETFs",  # MAJOR_INDICES
    8: "Extended",    # EXTENDED_ASSETS
    9: "Sector ETFs", # SECTOR_ETFS
    10: "International" # INTERNATIONAL
}

# Short names for compact display
CORRECT_CLIENT_ALLOCATION_SHORT = {
    1: "Orders",
    2: "Admin", 
    3: "Core",
    4: "Options",
    5: "Volatility"
}

# Files/directories to exclude from search
EXCLUDE_FILES = [
    '__pycache__',
    '.git',
    '.pyc',
    'temp_SpyderClientAllocationFixer.py',  # Don't modify ourselves
    'node_modules',
    '.vscode',
    'venv',
    'env',
    '.pytest_cache',
    'build',
    'dist',
    '.egg-info'
]

# Enhanced search patterns for better detection
SEARCH_PATTERNS = [
    # Old range patterns
    r'client.*[0-8](?![0-9])',  # Client 0-8 but not 10
    r'CLIENT.*[0-8](?![0-9])',
    r'range.*0.*8(?![0-9])',
    r'range.*0.*9(?![0-9])',
    r'0-8(?!\d)',
    r'0-9(?!\d)',
    r'1-9(?!\d)',
    
    # Wrong allocation patterns - more specific
    r'client_1_5_types.*=.*\[.*"Admin".*"Orders"',
    r'CLIENT_DEFINITIONS.*=.*\[.*\(0.*"Admin"',
    r'"Admin".*,.*"Orders".*,.*"Core"',
    r'["\']\s*Admin\s*["\']\s*,\s*["\']\s*Orders\s*["\']',
    
    # Specific wrong assignments
    r'[Cc]lient\s*0\s*[:\-]?\s*[Aa]dmin',
    r'[Cc]lient\s*1\s*[:\-]?\s*[Oo]rders',
    r'[Cc]lient\s*2\s*[:\-]?\s*[Aa]dmin',
    r'administrative.*client.*0',
    r'order.*execution.*client.*[02]',
    
    # Range specifications
    r'max_client_id.*[<>=].*9(?!\d)',
    r'client.*range.*9(?!\d)',
    r'get_client_id_range.*9(?!\d)',
    
    # Function calls with old ranges
    r'range\s*\(\s*0\s*,\s*[89]\s*\)',
    r'range\s*\(\s*1\s*,\s*9\s*\)'
]

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def print_banner():
    """Print startup banner"""
    print("=" * 80)
    print("🔍 SPYDER CLIENT ALLOCATION CONSISTENCY SCANNER")
    print("=" * 80)
    print("🎯 SCAN ONLY - No automatic fixes applied to trading system")
    print("📋 Correct allocation (SpyderB08 authoritative):")
    for client_id, purpose in CORRECT_CLIENT_ALLOCATION.items():
        print(f"   Client {client_id:2d}: {purpose}")
    print("⚠️  All fixes must be applied manually after careful review")
    print("=" * 80)

def is_excluded_file(file_path: Path) -> bool:
    """Check if file should be excluded from search"""
    # Only scan Python and markdown files
    if file_path.suffix not in ['.py', '.md']:
        return True
        
    # Check if file or any parent directory is in exclude list
    for exclude in EXCLUDE_FILES:
        if exclude in str(file_path):
            return True
            
    # Never exclude files in Spyder directories
    if any(part.startswith('Spyder') for part in file_path.parts):
        return False
        
    return False

def test_scanner_setup(project_root: Path) -> None:
    """Test that the scanner can find expected files"""
    print("\n🧪 TESTING SCANNER SETUP")
    print("=" * 50)
    
    expected_files = [
        'SpyderB13_GatewayConfig.py',
        'SpyderB14_MultiClientWatchdog.py', 
        'SpyderG05_TradingDashboard.py',
        'SpyderG06_ClientMonitorPanel.py',
        'SpyderG07_PrometheusMetricsDisplay.py'
    ]
    
    found_files = []
    for root, dirs, files in os.walk(project_root):
        for file_name in files:
            if file_name in expected_files:
                file_path = Path(root) / file_name
                rel_path = file_path.relative_to(project_root)
                found_files.append((file_name, rel_path))
                print(f"✅ Found: {rel_path}")
    
    missing_files = [f for f in expected_files if f not in [found[0] for found in found_files]]
    if missing_files:
        print(f"\n❌ Missing files:")
        for missing in missing_files:
            print(f"   • {missing}")
        print(f"\n💡 If files exist but not found:")
        print(f"   • Check file names are exactly as expected")
        print(f"   • Verify you're in the correct directory")
        print(f"   • Use --debug flag for detailed scanning output")
    else:
        print(f"\n✅ All expected files found! Scanner should work correctly.")
    
    print(f"\n📊 Summary: {len(found_files)}/{len(expected_files)} target files found")

def backup_file(file_path: Path) -> Path:
    """Create backup of file before modification"""
    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
    shutil.copy2(file_path, backup_path)
    return backup_path

# ==============================================================================
# MAIN SCANNER CLASS
# ==============================================================================
class SpyderClientAllocationFixer:
    """Main class for finding and fixing client allocation issues"""
    
    def __init__(self, project_root: Optional[Path] = None, debug_mode: bool = False):
        """Initialize the fixer"""
        self.project_root = project_root or Path.cwd()
        self.debug_mode = debug_mode
        self.issues_found = []
        self.files_scanned = 0
        self.files_with_issues = 0
        self.fixes_applied = 0
        
    def scan_file(self, file_path: Path) -> List[Dict]:
        """Scan a single file for client allocation issues"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            if self.debug_mode:
                rel_path = file_path.relative_to(self.project_root)
                print(f"   🔍 Scanning: {rel_path}")
                
            # Check each line for patterns
            for line_num, line in enumerate(lines, 1):
                for pattern in SEARCH_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        issue_type = self._classify_issue(pattern, line)
                        issues.append({
                            'file': file_path,
                            'line_number': line_num,
                            'line_content': line.strip(),
                            'pattern': pattern,
                            'type': issue_type
                        })
                        
                        if self.debug_mode:
                            print(f"      🚨 Line {line_num}: {issue_type}")
                            print(f"         {line.strip()[:80]}...")
                        
        except Exception as e:
            if self.debug_mode:
                print(f"⚠️ Error scanning {file_path}: {e}")
            
        return issues
    
    def _classify_issue(self, pattern: str, line: str) -> str:
        """Classify the type of issue found"""
        line_lower = line.lower()
        
        if 'admin' in line_lower and 'orders' in line_lower:
            if line_lower.find('admin') < line_lower.find('orders'):
                return "WRONG_ORDER_ADMIN_FIRST"
            
        if '0-8' in line or '0-9' in line:
            return "OLD_RANGE"
            
        if 'client 0' in line_lower or 'client_id.*0' in line_lower:
            return "CLIENT_0_USAGE"
            
        if 'client.*1.*order' in line_lower:
            return "WRONG_ORDER_CLIENT"
            
        if 'client.*2.*admin' in line_lower:
            return "WRONG_ADMIN_CLIENT"
            
        return "GENERAL_INCONSISTENCY"
    
    def scan_project(self) -> None:
        """Scan entire project for client allocation issues"""
        print(f"🔍 Scanning project at: {self.project_root}")
        print("=" * 60)
        
        # First, identify key Spyder directories
        spyder_dirs = self._find_spyder_directories()
        print(f"📁 Found Spyder directories: {len(spyder_dirs)}")
        for dir_path in spyder_dirs:
            rel_path = dir_path.relative_to(self.project_root)
            print(f"   📂 {rel_path}")
        print()
        
        # Scan all directories recursively
        directories_scanned = []
        for root, dirs, files in os.walk(self.project_root):
            current_dir = Path(root)
            
            # Remove excluded directories but keep Spyder directories
            dirs[:] = [d for d in dirs if not self._should_exclude_directory(d)]
            
            # Track directories being scanned
            if any(part.startswith('Spyder') for part in current_dir.parts) or current_dir == self.project_root:
                rel_path = current_dir.relative_to(self.project_root) if current_dir != self.project_root else Path('.')
                directories_scanned.append(rel_path)
                if len(files) > 0:  # Only show directories with files
                    py_files = [f for f in files if f.endswith('.py')]
                    if py_files:
                        print(f"📁 Scanning {rel_path} ({len(py_files)} .py files)")
            
            for file_name in files:
                file_path = Path(root) / file_name
                
                if is_excluded_file(file_path):
                    continue
                    
                self.files_scanned += 1
                issues = self.scan_file(file_path)
                
                if issues:
                    self.files_with_issues += 1
                    self.issues_found.extend(issues)
                    
        print(f"\n📊 Scan complete:")
        print(f"   • {len(directories_scanned)} directories scanned")
        print(f"   • {self.files_scanned} files scanned")
        print(f"   • {self.files_with_issues} files with issues found")
        
        # Verify we found the target modules
        self._verify_target_modules()
        
    def report_issues(self) -> None:
        """Generate detailed report of issues found"""
        if not self.issues_found:
            print("✅ No client allocation issues found!")
            return
            
        print("\n" + "=" * 80)
        print("📋 CLIENT ALLOCATION ISSUES REPORT")
        print("=" * 80)
        
        # Group issues by file
        issues_by_file = {}
        for issue in self.issues_found:
            file_path = issue['file']
            if file_path not in issues_by_file:
                issues_by_file[file_path] = []
            issues_by_file[file_path].append(issue)
            
        # Print issues by file
        for file_path, file_issues in issues_by_file.items():
            rel_path = file_path.relative_to(self.project_root)
            print(f"\n📁 {rel_path}")
            print("-" * 60)
            
            for issue in file_issues:
                print(f"   Line {issue['line_number']:4d}: {issue['type']}")
                print(f"   {'':10} {issue['line_content'][:70]}...")
                print()
                
        # Summary by issue type
        print("\n" + "=" * 80)
        print("📈 ISSUE SUMMARY")
        print("=" * 80)
        
        issue_types = {}
        for issue in self.issues_found:
            issue_type = issue['type']
            if issue_type not in issue_types:
                issue_types[issue_type] = 0
            issue_types[issue_type] += 1
            
        for issue_type, count in sorted(issue_types.items()):
            print(f"   {issue_type:25s}: {count:3d} occurrences")
            
    def generate_fixes(self) -> List[Dict]:
        """Generate specific fixes for identified issues"""
        fixes = []
        
        for issue in self.issues_found:
            fix = self._generate_fix_for_issue(issue)
            if fix:
                fixes.append(fix)
                
        return fixes
    
    def _generate_fix_for_issue(self, issue: Dict) -> Optional[Dict]:
        """Generate a specific fix for an issue"""
        issue_type = issue['type']
        line_content = issue['line_content']
        
        if issue_type == "WRONG_ORDER_ADMIN_FIRST":
            # Fix: ["Admin", "Orders", ...] -> ["Orders", "Admin", ...]
            if '"Admin", "Orders"' in line_content:
                new_line = line_content.replace('"Admin", "Orders"', '"Orders", "Admin"')
                return {
                    'file': issue['file'],
                    'line_number': issue['line_number'],
                    'old_line': line_content,
                    'new_line': new_line,
                    'description': 'Swap Admin/Orders to correct order'
                }
                
        elif issue_type == "OLD_RANGE":
            # Fix range specifications
            if '0-8' in line_content:
                new_line = line_content.replace('0-8', '1-10')
                return {
                    'file': issue['file'],
                    'line_number': issue['line_number'], 
                    'old_line': line_content,
                    'new_line': new_line,
                    'description': 'Update range from 0-8 to 1-10'
                }
            elif '0-9' in line_content:
                new_line = line_content.replace('0-9', '1-10') 
                return {
                    'file': issue['file'],
                    'line_number': issue['line_number'],
                    'old_line': line_content,
                    'new_line': new_line,
                    'description': 'Update range from 0-9 to 1-10'
                }
                
        elif issue_type == "CLIENT_0_USAGE":
            # Fix Client 0 references
            if 'client 0' in line_content.lower():
                new_line = re.sub(r'[Cc]lient 0', 'Client 2', line_content)  # Admin is now Client 2
                return {
                    'file': issue['file'],
                    'line_number': issue['line_number'],
                    'old_line': line_content,
                    'new_line': new_line,
                    'description': 'Replace Client 0 with Client 2 (Admin)'
                }
                
        return None
    
    def _find_spyder_directories(self) -> List[Path]:
        """Find all Spyder module directories"""
        spyder_dirs = []
        
        for item in self.project_root.iterdir():
            if item.is_dir() and item.name.startswith('Spyder'):
                spyder_dirs.append(item)
                
        return sorted(spyder_dirs)
    
    def _should_exclude_directory(self, dir_name: str) -> bool:
        """Check if directory should be excluded (but preserve Spyder dirs)"""
        # Never exclude Spyder directories
        if dir_name.startswith('Spyder'):
            return False
            
        # Exclude standard non-code directories
        exclude_patterns = ['__pycache__', '.git', 'node_modules', '.vscode', 'venv', 'env', '.pytest_cache']
        return any(exclude in dir_name for exclude in exclude_patterns)
    
    def _verify_target_modules(self) -> None:
        """Verify we found the specific target modules mentioned by user"""
        target_modules = [
            'SpyderB13_GatewayConfig.py',
            'SpyderB14_MultiClientWatchdog.py', 
            'SpyderG07_PrometheusMetricsDisplay.py',
            'SpyderG06_ClientMonitorPanel.py',
            'SpyderG05_TradingDashboard.py'
        ]
        
        print(f"\n🎯 Verifying target modules:")
        found_modules = []
        
        for issue in self.issues_found:
            file_name = issue['file'].name
            if file_name in target_modules and file_name not in found_modules:
                found_modules.append(file_name)
                
        for module in target_modules:
            if module in found_modules:
                print(f"   ✅ {module} - issues found")
            else:
                # Check if file exists but no issues found
                file_found = False
                for root, dirs, files in os.walk(self.project_root):
                    if module in files:
                        file_found = True
                        break
                        
                if file_found:
                    print(f"   ✅ {module} - scanned, no issues detected")
                else:
                    print(f"   ❌ {module} - not found in project")
                    
        if len(found_modules) == 0:
            print(f"   ⚠️  No issues found in target modules - this might indicate:")
            print(f"      • Files are already correct (good!)")
            print(f"      • Search patterns need adjustment")
            print(f"      • Files are in unexpected locations")
    
    def show_fix_suggestions(self, fixes: List[Dict]) -> None:
        """Show suggested fixes for manual review - NO AUTOMATIC APPLICATION"""
        if not fixes:
            print("✅ No automatic fix suggestions generated!")
            return
            
        print(f"\n💡 SUGGESTED FIXES FOR MANUAL REVIEW: {len(fixes)}")
        print("=" * 60)
        print("⚠️  IMPORTANT: These are suggestions only - review each carefully!")
        print("=" * 60)
        
        files_to_fix = {}
        for fix in fixes:
            file_path = fix['file']
            if file_path not in files_to_fix:
                files_to_fix[file_path] = []
            files_to_fix[file_path].append(fix)
            
        for file_path, file_fixes in files_to_fix.items():
            rel_path = file_path.relative_to(self.project_root)
            print(f"\n📁 {rel_path}")
            print("-" * 40)
            
            # Sort by line number 
            file_fixes.sort(key=lambda x: x['line_number'])
            
            for fix in file_fixes:
                print(f"   Line {fix['line_number']:4d}: {fix['description']}")
                print(f"   {'':10} CURRENT: {fix['old_line'][:60]}...")
                print(f"   {'':10} SUGGEST: {fix['new_line'][:60]}...")
                print(f"   {'':10} ⚠️  REVIEW MANUALLY BEFORE APPLYING")
                print()
                
        print(f"\n💡 RECOMMENDATION:")
        print(f"   • Review each suggestion in context")
        print(f"   • Make changes manually after understanding impact") 
        print(f"   • Test each module after changes")
        print(f"   • Consider backup before modifying files")

# ==============================================================================
# MANUAL FIX SUGGESTIONS
# ==============================================================================
def generate_manual_fix_report():
    """Generate manual fix suggestions for complex issues"""
    print("\n" + "=" * 80)
    print("🔧 MANUAL FIX SUGGESTIONS")
    print("=" * 80)
    
    manual_fixes = [
        {
            'file': 'SpyderG05_TradingDashboard.py',
            'line': '~2201',
            'issue': 'client_1_5_types = ["Admin", "Orders", "Core", "Options", "Volatility"]',
            'fix': 'client_1_5_types = ["Orders", "Admin", "Core", "Options", "Volatility"]',
            'priority': 'HIGH'
        },
        {
            'file': 'SpyderB13_GatewayConfig.py', 
            'line': 'Multiple',
            'issue': 'Inconsistent client range (1-9 vs 1-10) and allocation',
            'fix': 'Update all references to use 1-10 range with Client 1=Orders, Client 2=Admin',
            'priority': 'HIGH'
        },
        {
            'file': 'SpyderG07_PrometheusMetricsDisplay.py',
            'line': '~180-200',
            'issue': 'Uses old 0-8 client range in _get_client_type()',
            'fix': 'Update to 1-10 range with correct client types',
            'priority': 'MEDIUM'
        },
        {
            'file': 'SpyderG06_ClientMonitorPanel.py',
            'line': '~150-170', 
            'issue': 'CLIENT_DEFINITIONS uses 0-8 range',
            'fix': 'Update to 1-10 range with correct allocation',
            'priority': 'MEDIUM'
        },
        {
            'file': 'SpyderB14_MultiClientWatchdog.py',
            'line': 'Multiple',
            'issue': 'Mixed references to old and new client allocation',
            'fix': 'Ensure all references use Client 1=Orders, Client 2=Admin',
            'priority': 'HIGH'
        }
    ]
    
    for fix in manual_fixes:
        print(f"\n📁 {fix['file']}")
        print(f"   🔸 Priority: {fix['priority']}")
        print(f"   🔸 Line(s): {fix['line']}")
        print(f"   🔸 Issue: {fix['issue']}")
        print(f"   🔸 Fix: {fix['fix']}")
        
    print(f"\n💡 After applying fixes, search for remaining patterns:")
    print("   grep -r 'client.*0' --include='*.py' .")
    print("   grep -r '0-8\\|0-9' --include='*.py' .")
    print("   grep -r 'Admin.*Orders' --include='*.py' .")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution function - SCAN AND REPORT ONLY"""
    import sys
    
    # Check for debug mode flag
    debug_mode = '--debug' in sys.argv or '-d' in sys.argv
    verbose_mode = '--verbose' in sys.argv or '-v' in sys.argv
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    print_banner()
    
    # Initialize fixer
    project_root = Path.cwd()
    print(f"🏠 Working directory: {project_root}")
    
    # Test mode - just verify scanner setup
    if test_mode:
        test_scanner_setup(project_root)
        return
    
    # Verify we're in the right place
    if not any(item.name.startswith('Spyder') for item in project_root.iterdir() if item.is_dir()):
        print("\n⚠️  WARNING: No Spyder directories found in current directory!")
        print("   Make sure you're running this from the Spyder project root.")
        print("   Expected directories: SpyderB_Broker, SpyderG_GUI, etc.")
        
        # Look for Spyder directories one level up or down
        parent_spyder = list((project_root.parent).glob('Spyder*'))
        child_spyder = list(project_root.glob('*/Spyder*'))
        
        if parent_spyder:
            print(f"   💡 Found Spyder directories in parent: {[d.name for d in parent_spyder]}")
            print(f"      Try: cd .. && python {Path(__file__).name}")
        elif child_spyder:
            print(f"   💡 Found Spyder directories in subdirs: {[d.name for d in child_spyder]}")
        
        response = input("\n❓ Continue anyway? (y/n): ").lower().strip()
        if response != 'y':
            print("Exiting...")
            return
    
    fixer = SpyderClientAllocationFixer(project_root, debug_mode=debug_mode or verbose_mode)
    
    # Scan project
    fixer.scan_project()
    
    # Report issues
    fixer.report_issues()
    
    # Generate fix suggestions (but don't apply them)
    fixes = fixer.generate_fixes()
    if fixes:
        print(f"\n💡 Generated {len(fixes)} fix suggestions for manual review")
        fixer.show_fix_suggestions(fixes)
    
    # Generate manual fix suggestions for complex cases
    generate_manual_fix_report()
    
    print("\n" + "=" * 80)
    print("✅ CLIENT ALLOCATION SCAN COMPLETE")
    print("=" * 80)
    print("📋 Recommended workflow:")
    print("   1. Review all identified issues above")
    print("   2. Manually fix SpyderG05 line 2201 (simple array change)")
    print("   3. Address each other module individually")
    print("   4. Test each module after making changes")
    print("   5. Re-run this scanner to verify fixes")
    print("   6. Never apply automatic fixes to trading system code")
    print("\n💡 Focus on high-priority issues first (SpyderB13, SpyderB14)")
    print("🔒 Always backup files before making changes")
    print("\n🔧 Command line options:")
    print("   --test or -t   : Test scanner setup (find target files)")
    print("   --debug or -d  : Enable debug output")
    print("   --verbose or -v: Enable verbose output")
    
if __name__ == "__main__":
    main()
