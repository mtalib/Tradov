#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMPORARY UTILITY: Comprehensive IB_INSYNC Scanner for Spyder Project

Purpose: Scan entire Spyder codebase at /home/adam/Projects/Spyder to find 
         all remaining occurrences of ib_insync that need to be replaced 
         with ib_async for IB Gateway 10.37 compatibility

Author: Mohamed Talib  
Date: 2025-01-21
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter
import json
from datetime import datetime

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Spyder project path (will auto-detect current directory)
SPYDER_ROOT = Path.cwd()

# File extensions to scan
PYTHON_EXTENSIONS = ['.py', '.pyx', '.pyi']

# Comprehensive patterns to search for
IB_INSYNC_PATTERNS = [
    # Import statements
    (r'from\s+ib_insync\s+import\s+([^#\n]+)', 'IMPORT_FROM'),
    (r'import\s+ib_insync(?:\s+as\s+\w+)?', 'IMPORT_DIRECT'),
    
    # Variable and constant references
    (r'HAS_IB_INSYNC', 'VARIABLE'),
    (r'ib_insync_AVAILABLE', 'VARIABLE'), 
    (r'IB_INSYNC_AVAILABLE', 'VARIABLE'),
    
    # Direct usage
    (r'ib_insync\.(\w+)', 'USAGE'),
    
    # Comments and documentation
    (r'#.*ib_insync.*', 'COMMENT'),
    (r'"""[^"]*ib_insync[^"]*"""', 'DOCSTRING'),
    (r"'''[^']*ib_insync[^']*'''", 'DOCSTRING'),
    
    # String literals
    (r'"[^"]*ib_insync[^"]*"', 'STRING'),
    (r"'[^']*ib_insync[^']*'", 'STRING'),
    
    # Exception handling
    (r'except\s+.*ib_insync.*:', 'EXCEPTION'),
    
    # Conditional checks
    (r'if\s+.*ib_insync.*:', 'CONDITIONAL'),
    
    # Print/log statements
    (r'(?:print|log|logger)\s*\([^)]*ib_insync[^)]*\)', 'OUTPUT'),
]

# Directories to exclude from scanning
EXCLUDE_DIRS = [
    '__pycache__',
    '.git', 
    '.pytest_cache',
    'venv',
    'env',
    '.vscode',
    '.idea',
    'temp',
    'logs',
    'backup',
    '.backup',
    'node_modules'
]

# Files to exclude
EXCLUDE_FILES = [
    '*.pyc',
    '*.pyo', 
    '*.pyd',
    '*.so',
    '*.egg-info',
    '.DS_Store',
    'Thumbs.db'
]

# ==============================================================================
# SCANNER CLASS
# ==============================================================================

class SpyderIBInsyncScanner:
    """Comprehensive scanner for ib_insync occurrences in Spyder codebase"""
    
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.results = defaultdict(list)
        self.file_count = 0
        self.total_occurrences = 0
        self.pattern_stats = Counter()
        self.affected_modules = set()
        self.critical_modules = set()
        
        # Track what needs to be replaced
        self.replacement_map = {
            'from ib_insync import': 'from ib_async import',
            'import ib_insync': 'import ib_async',
            'ib_insync.': 'ib_async.',
            'HAS_IB_INSYNC': 'HAS_IB_ASYNC',
            'ib_insync_AVAILABLE': 'ib_async_AVAILABLE',
            'IB_INSYNC_AVAILABLE': 'IB_ASYNC_AVAILABLE',
            '"ib_insync': '"ib_async',
            "'ib_insync": "'ib_async",
            'ib_insync not available': 'ib_async not available',
            'install ib_insync': 'install ib_async',
            'pip install ib_insync': 'pip install ib_async',
        }
        
    def scan_file(self, file_path: Path) -> List[Tuple[int, str, str, str]]:
        """
        Scan a single file for ib_insync patterns
        
        Returns:
            List of (line_number, line_content, pattern_matched, pattern_type)
        """
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_stripped = line.strip()
                    
                    for pattern, pattern_type in IB_INSYNC_PATTERNS:
                        matches_found = re.finditer(pattern, line, re.IGNORECASE)
                        for match in matches_found:
                            matches.append((line_num, line_stripped, match.group(0), pattern_type))
                            self.pattern_stats[pattern_type] += 1
                            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
        return matches
    
    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped"""
        # Skip excluded directories
        if any(exclude in str(path) for exclude in EXCLUDE_DIRS):
            return True
            
        # Skip excluded files
        if any(path.match(pattern) for pattern in EXCLUDE_FILES):
            return True
            
        return False
    
    def categorize_module(self, file_path: Path) -> str:
        """Categorize module by its path"""
        path_str = str(file_path)
        
        if 'SpyderB_Broker' in path_str:
            return 'BROKER'
        elif 'SpyderA_Core' in path_str:
            return 'CORE'
        elif 'SpyderT_Testing' in path_str:
            return 'TESTING'
        elif 'SpyderI_Integration' in path_str:
            return 'INTEGRATION'
        elif 'SpyderU_Utilities' in path_str:
            return 'UTILITIES'
        elif 'SpyderV_QuantModels' in path_str:
            return 'QUANT'
        elif 'SpyderR_Runtime' in path_str:
            return 'RUNTIME'
        elif 'SpyderD_Strategies' in path_str:
            return 'STRATEGIES'
        else:
            return 'OTHER'
    
    def is_critical_module(self, file_path: Path) -> bool:
        """Check if module is critical for trading operations"""
        critical_patterns = [
            'SpyderB01_SpyderClient',
            'SpyderB05_ConnectionManager', 
            'SpyderB08_MultiClientDataManager',
            'SpyderB11_AsyncIOBridge',
            'SpyderA01_Main',
            'SpyderA02_TradingEngine',
        ]
        
        return any(pattern in str(file_path) for pattern in critical_patterns)
    
    def scan_directory(self) -> Dict[str, List[Tuple[int, str, str, str]]]:
        """
        Scan entire directory tree for ib_insync occurrences
        
        Returns:
            Dictionary mapping file paths to list of matches
        """
        print(f"🔍 Scanning Spyder codebase at: {self.root_path}")
        print(f"📁 Looking for ib_insync patterns in {PYTHON_EXTENSIONS} files")
        print("=" * 80)
        
        if not self.root_path.exists():
            print(f"❌ Directory does not exist: {self.root_path}")
            return {}
        
        for root, dirs, files in os.walk(self.root_path):
            root_path = Path(root)
            
            # Skip excluded directories
            if self.should_skip_path(root_path):
                continue
                
            # Remove excluded dirs from dirs list to prevent traversal
            dirs[:] = [d for d in dirs if not self.should_skip_path(root_path / d)]
            
            for file in files:
                file_path = root_path / file
                
                # Only scan Python files
                if file_path.suffix not in PYTHON_EXTENSIONS:
                    continue
                    
                # Skip excluded files
                if self.should_skip_path(file_path):
                    continue
                    
                self.file_count += 1
                matches = self.scan_file(file_path)
                
                if matches:
                    relative_path = file_path.relative_to(self.root_path)
                    self.results[str(relative_path)] = matches
                    self.total_occurrences += len(matches)
                    self.affected_modules.add(self.categorize_module(file_path))
                    
                    if self.is_critical_module(file_path):
                        self.critical_modules.add(str(relative_path))
                    
        return dict(self.results)
    
    def print_results(self):
        """Print comprehensive scan results"""
        print(f"\n📊 COMPREHENSIVE SCAN RESULTS")
        print("=" * 80)
        print(f"📁 Root Directory: {self.root_path}")
        print(f"📄 Files scanned: {self.file_count}")
        print(f"🔍 Files with ib_insync: {len(self.results)}")
        print(f"📊 Total occurrences: {self.total_occurrences}")
        print(f"🏗️  Affected module types: {', '.join(sorted(self.affected_modules))}")
        
        if not self.results:
            print("\n✅ 🎉 NO IB_INSYNC OCCURRENCES FOUND!")
            print("Your Spyder codebase is already using ib_async! 🚀")
            return
            
        # Pattern type statistics
        print(f"\n📈 PATTERN TYPE BREAKDOWN:")
        print("-" * 50)
        for pattern_type, count in self.pattern_stats.most_common():
            print(f"   {pattern_type:15}: {count:3d} occurrences")
        
        # Critical modules first
        if self.critical_modules:
            print(f"\n🚨 CRITICAL MODULES NEEDING ATTENTION ({len(self.critical_modules)}):")
            print("-" * 50)
            for module in sorted(self.critical_modules):
                matches = self.results[module]
                print(f"   📄 {module} - {len(matches)} occurrences")
        
        # All affected files
        print(f"\n📋 ALL AFFECTED FILES ({len(self.results)}):")
        print("-" * 50)
        
        # Sort by module type and then by occurrence count
        sorted_files = sorted(
            self.results.items(), 
            key=lambda x: (self.categorize_module(Path(x[0])), -len(x[1]))
        )
        
        current_category = None
        for file_path, matches in sorted_files:
            category = self.categorize_module(Path(file_path))
            
            if category != current_category:
                print(f"\n   🏷️  {category} MODULES:")
                current_category = category
                
            critical_marker = " [CRITICAL]" if file_path in self.critical_modules else ""
            print(f"      📄 {file_path} ({len(matches)} occurrences){critical_marker}")
    
    def print_detailed_occurrences(self, max_files: int = 5):
        """Print detailed occurrences for top files"""
        if not self.results:
            return
            
        print(f"\n🔍 DETAILED OCCURRENCES (Top {max_files} files):")
        print("=" * 80)
        
        # Sort by occurrence count
        sorted_files = sorted(
            self.results.items(), 
            key=lambda x: len(x[1]), 
            reverse=True
        )
        
        for file_path, matches in sorted_files[:max_files]:
            print(f"\n📄 {file_path}")
            print("-" * 60)
            
            for line_num, line_content, pattern, pattern_type in matches:
                # Highlight the matched pattern
                highlighted = self.highlight_pattern(line_content, pattern)
                print(f"  {line_num:3d} [{pattern_type:8}]: {highlighted}")
    
    def highlight_pattern(self, line: str, pattern: str) -> str:
        """Add highlighting to matched patterns"""
        # Simple highlighting with brackets
        if pattern in line:
            return line.replace(pattern, f"[{pattern}]")
        return line
    
    def generate_replacement_script(self, output_file: str = "temp_fix_ib_insync.py"):
        """Generate a script to help with ib_insync to ib_async conversion"""
        if not self.results:
            return
            
        script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO-GENERATED: IB_INSYNC to IB_ASYNC Conversion Script

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Root Path: {self.root_path}
Files Found: {len(self.results)}
Total Occurrences: {self.total_occurrences}

USAGE:
    python {output_file} --preview    # Show what would be changed
    python {output_file} --apply      # Apply the changes
    python {output_file} --backup     # Create backups first
"""

import re
import shutil
from pathlib import Path

# Root directory
ROOT_PATH = Path("{self.root_path}")

# Files to process
AFFECTED_FILES = {repr(list(self.results.keys()))}

# Replacement patterns
REPLACEMENTS = {repr(self.replacement_map)}

def preview_changes():
    """Preview what would be changed"""
    print("🔍 PREVIEW: Changes that would be made:")
    print("=" * 60)
    
    for file_path in AFFECTED_FILES:
        full_path = ROOT_PATH / file_path
        print(f"\\n📄 {{file_path}}")
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            changes = 0
            for old, new in REPLACEMENTS.items():
                if old in content:
                    count = content.count(old)
                    changes += count
                    print(f"   • '{{old}}' → '{{new}}' ({{count}} times)")
                    
            if changes == 0:
                print("   ✅ No changes needed")
                
        except Exception as e:
            print(f"   ❌ Error reading file: {{e}}")

def apply_changes(create_backup=True):
    """Apply the changes to files"""
    print("🔧 APPLYING: Changes to files...")
    print("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for file_path in AFFECTED_FILES:
        full_path = ROOT_PATH / file_path
        
        try:
            # Create backup if requested
            if create_backup:
                backup_path = full_path.with_suffix(full_path.suffix + '.backup')
                shutil.copy2(full_path, backup_path)
                print(f"💾 Backup created: {{backup_path}}")
            
            # Read file
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply replacements
            original_content = content
            for old, new in REPLACEMENTS.items():
                content = content.replace(old, new)
            
            # Write back if changed
            if content != original_content:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Updated: {{file_path}}")
                success_count += 1
            else:
                print(f"📋 No changes: {{file_path}}")
                
        except Exception as e:
            print(f"❌ Error processing {{file_path}}: {{e}}")
            error_count += 1
    
    print(f"\\n📊 SUMMARY:")
    print(f"   ✅ Successfully updated: {{success_count}} files")
    print(f"   ❌ Errors: {{error_count}} files")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python {output_file} [--preview|--apply|--backup]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "--preview":
        preview_changes()
    elif action == "--apply":
        apply_changes(create_backup=False)
    elif action == "--backup":
        apply_changes(create_backup=True)
    else:
        print("Invalid action. Use --preview, --apply, or --backup")
        sys.exit(1)
'''
        
        output_path = self.root_path / output_file
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
            
        # Make executable
        os.chmod(output_path, 0o755)
        
        print(f"\n🔧 CONVERSION SCRIPT GENERATED:")
        print(f"   📄 {output_path}")
        print(f"   🔍 Preview: python {output_file} --preview")
        print(f"   💾 Backup: python {output_file} --backup")
        print(f"   ⚡ Apply: python {output_file} --apply")
    
    def save_detailed_report(self, output_file: str = "ib_insync_scan_report.json"):
        """Save detailed report to JSON file"""
        report_data = {
            'scan_info': {
                'timestamp': datetime.now().isoformat(),
                'root_path': str(self.root_path),
                'files_scanned': self.file_count,
                'files_with_ib_insync': len(self.results),
                'total_occurrences': self.total_occurrences,
            },
            'statistics': {
                'pattern_types': dict(self.pattern_stats),
                'affected_modules': list(self.affected_modules),
                'critical_modules': list(self.critical_modules),
            },
            'detailed_results': {
                file_path: [
                    {
                        'line': line_num,
                        'content': line_content,
                        'pattern': pattern,
                        'type': pattern_type
                    }
                    for line_num, line_content, pattern, pattern_type in matches
                ]
                for file_path, matches in self.results.items()
            },
            'recommendations': self.get_recommendations()
        }
        
        output_path = self.root_path / output_file
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 DETAILED REPORT SAVED:")
        print(f"   📄 {output_path}")
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations based on scan results"""
        recommendations = []
        
        if not self.results:
            recommendations.append("🎉 No ib_insync found! Your codebase is ready for ib_async.")
            return recommendations
        
        recommendations.append(f"📊 Found {self.total_occurrences} ib_insync occurrences in {len(self.results)} files")
        
        if self.critical_modules:
            recommendations.append(f"🚨 {len(self.critical_modules)} critical modules need immediate attention")
            
        if 'BROKER' in self.affected_modules:
            recommendations.append("🔗 Broker modules affected - connection stability at risk")
            
        if 'TESTING' in self.affected_modules:
            recommendations.append("🧪 Testing modules affected - update test dependencies")
            
        recommendations.extend([
            "🔧 Run the generated conversion script to fix automatically",
            "💾 Create backups before applying changes",
            "🧪 Test thoroughly after conversion",
            "📦 Install ib_async: pip install ib_async",
            "🗑️  Remove old library: pip uninstall ib_insync",
        ])
        
        return recommendations

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function"""
    
    print("🕷️  SPYDER IB_INSYNC COMPREHENSIVE SCANNER")
    print("=" * 80)
    print(f"🎯 Target: {SPYDER_ROOT}")
    print(f"📅 Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Validate path
    if not SPYDER_ROOT.exists():
        print(f"❌ Spyder directory does not exist: {SPYDER_ROOT}")
        print("Please check the path and try again.")
        return
        
    # Run scan
    scanner = SpyderIBInsyncScanner(SPYDER_ROOT)
    results = scanner.scan_directory()
    
    # Print results
    scanner.print_results()
    
    # Show detailed occurrences for top files
    if results:
        scanner.print_detailed_occurrences(max_files=3)
    
    # Generate reports and tools
    scanner.save_detailed_report()
    
    if results:
        scanner.generate_replacement_script()
        
        # Print recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        print("-" * 50)
        for rec in scanner.get_recommendations():
            print(f"   {rec}")
    
    # Final summary
    if scanner.total_occurrences > 0:
        print(f"\n🚨 ACTION REQUIRED:")
        print(f"   Found {scanner.total_occurrences} ib_insync occurrences in {len(results)} files")
        print(f"   These need to be replaced with ib_async for IB Gateway 10.37 compatibility!")
        print(f"   Use the generated conversion script to fix automatically.")
    else:
        print(f"\n✅ 🎉 CONGRATULATIONS!")
        print(f"   Your Spyder codebase is already using ib_async!")
        print(f"   No legacy ib_insync references found.")

if __name__ == "__main__":
    main()
