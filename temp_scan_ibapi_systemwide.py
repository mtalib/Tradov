#!/usr/bin/env python3
"""
System-Wide IBAPI Scanner for Spyder Project

This script scans all Python files in the Spyder project directory tree
to find instances of "IBAPI" usage, categorizes them, and provides
recommendations for modernization to ib_async.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# File extensions to scan
SCAN_EXTENSIONS = {'.py', '.md', '.txt', '.rst', '.cfg', '.ini', '.sh'}

# Directories to skip
SKIP_DIRECTORIES = {
    '__pycache__', '.git', '.venv', 'venv', '.pytest_cache', 
    '.mypy_cache', '.tox', 'build', 'dist', '.idea', '.vscode'
}

# IBAPI patterns to search for
IBAPI_PATTERNS = [
    r'\bibapi\b',           # ibapi (word boundary)
    r'\bIBAPI\b',           # IBAPI (word boundary)  
    r'\bib_api\b',          # ib_api (alternative naming)
    r'from.*ibapi',         # import statements
    r'import.*ibapi',       # import statements
    r'ibapi\.',             # ibapi.something
    r'IBAPI\.',             # IBAPI.something
]

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

class IssueType(Enum):
    IMPORT_STATEMENT = "import_statement"
    CLASS_USAGE = "class_usage"
    METHOD_CALL = "method_call"
    COMMENT = "comment"
    VARIABLE_NAME = "variable_name"
    STRING_LITERAL = "string_literal"
    DOCUMENTATION = "documentation"

@dataclass
class IbapiMatch:
    file_path: str
    line_number: int
    line_content: str
    match_text: str
    issue_type: IssueType
    context_lines: List[str] = field(default_factory=list)
    suggested_fix: str = ""

@dataclass
class ScanResults:
    total_files_scanned: int = 0
    total_matches: int = 0
    files_with_issues: Set[str] = field(default_factory=set)
    matches_by_type: Dict[IssueType, List[IbapiMatch]] = field(default_factory=dict)
    matches_by_file: Dict[str, List[IbapiMatch]] = field(default_factory=dict)

# ==============================================================================
# SCANNER CLASS
# ==============================================================================

class IbapiScanner:
    """System-wide scanner for IBAPI usage in Spyder project"""
    
    def __init__(self, root_directory: str = "."):
        """
        Initialize the scanner.
        
        Args:
            root_directory: Root directory to start scanning from
        """
        self.root_dir = Path(root_directory).resolve()
        self.results = ScanResults()
        
        # Compile regex patterns
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in IBAPI_PATTERNS]
        
        print(f"🔍 IBAPI Scanner initialized")
        print(f"📁 Root directory: {self.root_dir}")
        print(f"🎯 Scanning for patterns: {len(IBAPI_PATTERNS)} patterns")
        
    def scan_directory(self) -> ScanResults:
        """
        Scan the directory tree for IBAPI usage.
        
        Returns:
            ScanResults: Complete scan results
        """
        print(f"\n🚀 Starting system-wide IBAPI scan...")
        print("=" * 60)
        
        for file_path in self._get_files_to_scan():
            self._scan_file(file_path)
            
        self._categorize_results()
        self._generate_suggestions()
        
        print(f"\n✅ Scan completed!")
        print(f"📊 Files scanned: {self.results.total_files_scanned}")
        print(f"🎯 Total matches: {self.results.total_matches}")
        print(f"📁 Files with issues: {len(self.results.files_with_issues)}")
        
        return self.results
    
    def _get_files_to_scan(self) -> List[Path]:
        """Get list of files to scan"""
        files_to_scan = []
        
        for root, dirs, files in os.walk(self.root_dir):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix in SCAN_EXTENSIONS:
                    files_to_scan.append(file_path)
        
        print(f"📁 Found {len(files_to_scan)} files to scan")
        return files_to_scan
    
    def _scan_file(self, file_path: Path):
        """Scan a single file for IBAPI usage"""
        try:
            self.results.total_files_scanned += 1
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Track if this file has any matches
            file_has_matches = False
            
            for line_num, line in enumerate(lines, 1):
                for pattern in self.patterns:
                    matches = pattern.finditer(line)
                    
                    for match in matches:
                        file_has_matches = True
                        self.results.total_matches += 1
                        
                        # Determine issue type
                        issue_type = self._classify_match(line, match.group())
                        
                        # Get context lines
                        context_lines = self._get_context_lines(lines, line_num - 1)
                        
                        # Create match object
                        ibapi_match = IbapiMatch(
                            file_path=str(file_path.relative_to(self.root_dir)),
                            line_number=line_num,
                            line_content=line.strip(),
                            match_text=match.group(),
                            issue_type=issue_type,
                            context_lines=context_lines
                        )
                        
                        # Store match
                        if issue_type not in self.results.matches_by_type:
                            self.results.matches_by_type[issue_type] = []
                        self.results.matches_by_type[issue_type].append(ibapi_match)
                        
                        if ibapi_match.file_path not in self.results.matches_by_file:
                            self.results.matches_by_file[ibapi_match.file_path] = []
                        self.results.matches_by_file[ibapi_match.file_path].append(ibapi_match)
            
            if file_has_matches:
                self.results.files_with_issues.add(str(file_path.relative_to(self.root_dir)))
                
        except Exception as e:
            print(f"⚠️ Error scanning {file_path}: {e}")
    
    def _classify_match(self, line: str, match_text: str) -> IssueType:
        """Classify the type of IBAPI usage"""
        line_lower = line.lower().strip()
        
        if line_lower.startswith('#') or '"""' in line or "'''" in line:
            return IssueType.COMMENT
        elif 'from' in line_lower and 'import' in line_lower:
            return IssueType.IMPORT_STATEMENT
        elif 'import' in line_lower:
            return IssueType.IMPORT_STATEMENT  
        elif 'class' in line_lower and 'ibapi' in line_lower:
            return IssueType.CLASS_USAGE
        elif '(' in line and ')' in line:
            return IssueType.METHOD_CALL
        elif '"' in line or "'" in line:
            return IssueType.STRING_LITERAL
        elif '=' in line:
            return IssueType.VARIABLE_NAME
        else:
            return IssueType.DOCUMENTATION
    
    def _get_context_lines(self, lines: List[str], center_line: int, context: int = 2) -> List[str]:
        """Get context lines around the match"""
        start = max(0, center_line - context)
        end = min(len(lines), center_line + context + 1)
        return [lines[i].rstrip() for i in range(start, end)]
    
    def _categorize_results(self):
        """Categorize and organize results"""
        pass  # Results are already categorized during scanning
    
    def _generate_suggestions(self):
        """Generate fix suggestions for each match"""
        for issue_type, matches in self.results.matches_by_type.items():
            for match in matches:
                match.suggested_fix = self._get_suggestion(match)
    
    def _get_suggestion(self, match: IbapiMatch) -> str:
        """Get suggested fix for a specific match"""
        if match.issue_type == IssueType.IMPORT_STATEMENT:
            if 'from ibapi' in match.line_content.lower():
                return "Replace with: from ib_async import ..."
            elif 'import ibapi' in match.line_content.lower():
                return "Replace with: from ib_async import ..."
        elif match.issue_type == IssueType.CLASS_USAGE:
            return "Update to use ib_async equivalent classes"
        elif match.issue_type == IssueType.METHOD_CALL:
            return "Update to use ib_async methods"
        elif match.issue_type == IssueType.COMMENT:
            return "Update comment to reference ib_async"
        elif match.issue_type == IssueType.DOCUMENTATION:
            return "Update documentation to reference ib_async"
        
        return "Review and update to use ib_async"

# ==============================================================================
# REPORT GENERATOR
# ==============================================================================

class IbapiReportGenerator:
    """Generate detailed reports from scan results"""
    
    def __init__(self, results: ScanResults):
        self.results = results
    
    def generate_summary_report(self):
        """Generate a summary report"""
        print("\n" + "=" * 80)
        print("📋 IBAPI USAGE SUMMARY REPORT")
        print("=" * 80)
        
        print(f"\n📊 SCAN STATISTICS:")
        print(f"   • Files scanned: {self.results.total_files_scanned}")
        print(f"   • Total IBAPI references: {self.results.total_matches}")
        print(f"   • Files with IBAPI usage: {len(self.results.files_with_issues)}")
        
        if self.results.total_matches == 0:
            print(f"\n🎉 EXCELLENT! No IBAPI usage found!")
            print(f"✅ Your system appears to be using modern ib_async")
            return
            
        print(f"\n📈 MATCHES BY TYPE:")
        for issue_type, matches in self.results.matches_by_type.items():
            print(f"   • {issue_type.value.replace('_', ' ').title()}: {len(matches)}")
        
        print(f"\n📁 FILES WITH ISSUES:")
        for file_path in sorted(self.results.files_with_issues):
            match_count = len(self.results.matches_by_file[file_path])
            print(f"   • {file_path} ({match_count} matches)")
    
    def generate_detailed_report(self):
        """Generate detailed findings report"""
        if self.results.total_matches == 0:
            return
            
        print(f"\n" + "=" * 80)
        print("🔍 DETAILED FINDINGS")
        print("=" * 80)
        
        for file_path in sorted(self.results.files_with_issues):
            matches = self.results.matches_by_file[file_path]
            print(f"\n📄 FILE: {file_path}")
            print("-" * 60)
            
            for i, match in enumerate(matches, 1):
                print(f"\n{i}. Line {match.line_number} ({match.issue_type.value}):")
                print(f"   Match: '{match.match_text}'")
                print(f"   Line:  {match.line_content}")
                if match.suggested_fix:
                    print(f"   💡 Suggestion: {match.suggested_fix}")
    
    def generate_action_plan(self):
        """Generate action plan for fixes"""
        if self.results.total_matches == 0:
            return
            
        print(f"\n" + "=" * 80)
        print("🎯 ACTION PLAN")
        print("=" * 80)
        
        # Priority 1: Import statements
        import_matches = self.results.matches_by_type.get(IssueType.IMPORT_STATEMENT, [])
        if import_matches:
            print(f"\n🚨 PRIORITY 1: Import Statements ({len(import_matches)} matches)")
            print("   These need immediate attention to use ib_async:")
            for match in import_matches:
                print(f"   • {match.file_path}:{match.line_number}")
        
        # Priority 2: Class and method usage
        class_matches = self.results.matches_by_type.get(IssueType.CLASS_USAGE, [])
        method_matches = self.results.matches_by_type.get(IssueType.METHOD_CALL, [])
        if class_matches or method_matches:
            total_code = len(class_matches) + len(method_matches)
            print(f"\n⚠️ PRIORITY 2: Code Usage ({total_code} matches)")
            print("   These require code updates:")
            for match in class_matches + method_matches:
                print(f"   • {match.file_path}:{match.line_number}")
        
        # Priority 3: Comments and documentation
        comment_matches = self.results.matches_by_type.get(IssueType.COMMENT, [])
        doc_matches = self.results.matches_by_type.get(IssueType.DOCUMENTATION, [])
        if comment_matches or doc_matches:
            total_docs = len(comment_matches) + len(doc_matches)
            print(f"\n📝 PRIORITY 3: Documentation ({total_docs} matches)")
            print("   These should be updated for consistency:")
            files = set([m.file_path for m in comment_matches + doc_matches])
            for file_path in sorted(files):
                print(f"   • {file_path}")
    
    def generate_file_summary(self):
        """Generate clean summary list of files with IBAPI occurrences"""
        if self.results.total_matches == 0:
            return
            
        print(f"\n" + "=" * 80)
        print("📁 FILES WITH IBAPI OCCURRENCES")
        print("=" * 80)
        print(f"📊 Total: {len(self.results.files_with_issues)} files with {self.results.total_matches} total occurrences")
        print("-" * 80)
        
        # Sort files by number of occurrences (highest first)
        file_counts = []
        for file_path in self.results.files_with_issues:
            count = len(self.results.matches_by_file[file_path])
            file_counts.append((file_path, count))
        
        # Sort by count (descending), then by filename
        file_counts.sort(key=lambda x: (-x[1], x[0]))
        
        print(f"{'FILE NAME':<60} {'OCCURRENCES':>12}")
        print("-" * 72)
        
        for file_path, count in file_counts:
            # Truncate long file paths for better display
            display_path = file_path
            if len(display_path) > 55:
                display_path = "..." + display_path[-52:]
            
            print(f"{display_path:<60} {count:>12}")
        
        print("-" * 72)
        print(f"{'TOTAL':<60} {self.results.total_matches:>12}")
        
        # Show top offenders
        if len(file_counts) > 0:
            print(f"\n🔥 TOP 5 FILES WITH MOST IBAPI USAGE:")
            for i, (file_path, count) in enumerate(file_counts[:5], 1):
                print(f"   {i}. {file_path} ({count} occurrences)")
                
        print(f"\n💡 RECOMMENDATION:")
        print(f"   Start with files having the most occurrences for maximum impact")
        print(f"   Focus on import statements first (Priority 1 items)")
        print(f"   Consider creating a migration checklist from this list")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function"""
    print("🚀 SPYDER IBAPI SYSTEM-WIDE SCANNER")
    print("=" * 60)
    print("🎯 Purpose: Find legacy IBAPI usage for ib_async migration")
    print("📁 Scanning all Python and config files in project")
    print("⚡ Looking for imports, usage, and references")
    
    try:
        # Initialize scanner
        scanner = IbapiScanner()
        
        # Perform scan
        results = scanner.scan_directory()
        
        # Generate reports
        report_generator = IbapiReportGenerator(results)
        
        report_generator.generate_summary_report()
        report_generator.generate_detailed_report()
        report_generator.generate_action_plan()
        report_generator.generate_file_summary()  # NEW: Clean file summary
        
        print(f"\n" + "=" * 80)
        print("🏁 SCAN COMPLETE")
        print("=" * 80)
        
        if results.total_matches > 0:
            print("🔧 ACTION REQUIRED: Legacy IBAPI usage found")
            print("💡 Consider updating to ib_async for better compatibility")
            print("📋 Use the action plan above to prioritize updates")
        else:
            print("🎉 SUCCESS: No legacy IBAPI usage detected!")
            print("✅ Your system is clean and modern")
        
    except Exception as e:
        print(f"❌ Scanner error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
