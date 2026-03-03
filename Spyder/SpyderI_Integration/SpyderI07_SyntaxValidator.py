#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI07_SyntaxValidator.py
Group: I (Integration)
Purpose: Automated syntax validation and fixing for all Spyder modules
Author: Mohamed Talib
Date Created: 2025-08-14
Last Updated: 2025-08-14 Time: 12:00:00

Description:
    This module provides comprehensive syntax validation and automatic fixing
    capabilities for the entire Spyder codebase. It identifies syntax errors,
    provides detailed diagnostics, and can automatically fix common issues like
    indentation problems, missing colons, unclosed brackets, and more. This tool
    ensures code quality and helps maintain production readiness.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import ast
import json
import os
import re
import subprocess
import sys
import tokenize
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import autopep8

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import black

    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False
    print("Warning: Black formatter not available. Install with: pip install black")

try:
    import isort

    ISORT_AVAILABLE = True
except ImportError:
    ISORT_AVAILABLE = False
    print("Warning: isort not available. Install with: pip install isort")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Spyder module patterns
SPYDER_MODULE_PATTERN = r"Spyder[A-Z]\d+_.*\.py$"
SPYDER_GROUPS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
]

# Common syntax error patterns
SYNTAX_PATTERNS = {
    "missing_colon": r"^\s*(if|elif|else|for|while|def|class|try|except|finally|with)\s+[^:]+$",
    "unclosed_bracket": r"[\(\[\{][^\)\]\}]*$",
    "unclosed_string": r'["\'](?:[^"\'\n\\]|\\.)*$',
    "invalid_indentation": r"^( {1,3}|\t| {5,7}| {9,11})",
    "trailing_whitespace": r"\s+$",
    "mixed_indentation": r"^(\t+ +| +\t+)",
}

# Auto-fixable issues
FIXABLE_ISSUES = {
    "indentation": True,
    "missing_colon": True,
    "trailing_whitespace": True,
    "mixed_indentation": True,
    "import_order": True,
    "line_length": True,
    "missing_newline": True,
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


class ErrorType(Enum):
    """Types of syntax errors"""

    SYNTAX_ERROR = "syntax_error"
    INDENTATION_ERROR = "indentation_error"
    IMPORT_ERROR = "import_error"
    NAME_ERROR = "name_error"
    ATTRIBUTE_ERROR = "attribute_error"
    TYPE_ERROR = "type_error"
    UNCLOSED_BRACKET = "unclosed_bracket"
    UNCLOSED_STRING = "unclosed_string"
    MISSING_COLON = "missing_colon"
    INVALID_SYNTAX = "invalid_syntax"


class FixStatus(Enum):
    """Status of fix attempts"""

    FIXED = "fixed"
    PARTIALLY_FIXED = "partially_fixed"
    UNFIXABLE = "unfixable"
    SKIPPED = "skipped"


@dataclass
class SyntaxIssue:
    """Represents a syntax issue in a file"""

    file_path: Path
    line_number: int
    column: int
    error_type: ErrorType
    message: str
    code_line: str
    suggestion: Optional[str] = None
    fixable: bool = False
    fixed: bool = False


@dataclass
class ValidationResult:
    """Result of file validation"""

    file_path: Path
    valid: bool
    issues: List[SyntaxIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fix_status: Optional[FixStatus] = None
    original_content: Optional[str] = None
    fixed_content: Optional[str] = None


@dataclass
class ValidationReport:
    """Complete validation report"""

    timestamp: datetime
    total_files: int
    valid_files: int
    files_with_errors: int
    total_issues: int
    fixed_issues: int
    unfixable_issues: int
    results_by_file: Dict[str, ValidationResult] = field(default_factory=dict)
    summary_by_group: Dict[str, Dict[str, int]] = field(default_factory=dict)


# ==============================================================================
# SYNTAX VALIDATOR CLASS
# ==============================================================================


class SyntaxValidator:
    """
    Comprehensive syntax validator and fixer for Spyder modules.

    This class provides automated syntax checking, error detection, and
    fixing capabilities for the entire Spyder codebase.
    """

    def __init__(self, project_root: str = ".", auto_fix: bool = False):
        """
        Initialize the syntax validator.

        Args:
            project_root: Root directory of the Spyder project
            auto_fix: Whether to automatically fix issues
        """
        self.project_root = Path(project_root)
        self.auto_fix = auto_fix

        # Validation state
        self.results: Dict[str, ValidationResult] = {}
        self.current_report: Optional[ValidationReport] = None

        # Statistics
        self.stats = {
            "files_checked": 0,
            "files_valid": 0,
            "files_fixed": 0,
            "total_issues": 0,
            "issues_fixed": 0,
        }

    # ==========================================================================
    # MAIN VALIDATION METHODS
    # ==========================================================================

    def validate_all(self) -> ValidationReport:
        """
        Validate all Spyder modules in the project.

        Returns:
            Complete validation report
        """
        print("🔍 Starting comprehensive syntax validation...")
        print("=" * 80)

        report = ValidationReport(
            timestamp=datetime.now(),
            total_files=0,
            valid_files=0,
            files_with_errors=0,
            total_issues=0,
            fixed_issues=0,
            unfixable_issues=0,
        )

        # Find all Python files
        python_files = self._find_python_files()
        report.total_files = len(python_files)

        # Validate each file
        for file_path in python_files:
            result = self.validate_file(file_path)

            # Update report
            report.results_by_file[str(file_path)] = result
            if result.valid:
                report.valid_files += 1
            else:
                report.files_with_errors += 1
                report.total_issues += len(result.issues)

            # Group statistics
            group = self._get_module_group(file_path)
            if group not in report.summary_by_group:
                report.summary_by_group[group] = {"total": 0, "valid": 0, "errors": 0, "fixed": 0}

            report.summary_by_group[group]["total"] += 1
            if result.valid:
                report.summary_by_group[group]["valid"] += 1
            else:
                report.summary_by_group[group]["errors"] += 1

            if result.fix_status == FixStatus.FIXED:
                report.summary_by_group[group]["fixed"] += 1
                report.fixed_issues += len([i for i in result.issues if i.fixed])

        # Calculate unfixable issues
        report.unfixable_issues = report.total_issues - report.fixed_issues

        self.current_report = report
        return report

    def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate a single Python file.

        Args:
            file_path: Path to the file

        Returns:
            Validation result
        """
        result = ValidationResult(file_path=file_path, valid=True)

        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                result.original_content = content

            # Check for basic syntax errors
            syntax_issues = self._check_syntax(file_path, content)
            result.issues.extend(syntax_issues)

            # Check for indentation issues
            indentation_issues = self._check_indentation(content)
            result.issues.extend(indentation_issues)

            # Check for import issues
            import_issues = self._check_imports(content)
            result.issues.extend(import_issues)

            # Check for common patterns
            pattern_issues = self._check_patterns(content)
            result.issues.extend(pattern_issues)

            # Update validity
            result.valid = len(result.issues) == 0

            # Attempt fixes if enabled
            if self.auto_fix and result.issues:
                result = self._attempt_fixes(result)

            # Update statistics
            self.stats["files_checked"] += 1
            if result.valid:
                self.stats["files_valid"] += 1

        except Exception as e:
            result.valid = False
            result.issues.append(
                SyntaxIssue(
                    file_path=file_path,
                    line_number=0,
                    column=0,
                    error_type=ErrorType.SYNTAX_ERROR,
                    message=f"Failed to validate file: {str(e)}",
                    code_line="",
                    fixable=False,
                )
            )

        return result

    # ==========================================================================
    # SYNTAX CHECKING METHODS
    # ==========================================================================

    def _check_syntax(self, file_path: Path, content: str) -> List[SyntaxIssue]:
        """Check for Python syntax errors using AST."""
        issues = []

        try:
            ast.parse(content)
        except SyntaxError as e:
            lines = content.split("\n")
            code_line = lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else ""

            issue = SyntaxIssue(
                file_path=file_path,
                line_number=e.lineno or 0,
                column=e.offset or 0,
                error_type=self._classify_syntax_error(e),
                message=e.msg,
                code_line=code_line,
                fixable=self._is_fixable_syntax_error(e),
                suggestion=self._suggest_fix(e, code_line),
            )
            issues.append(issue)

        return issues

    def _check_indentation(self, content: str) -> List[SyntaxIssue]:
        """Check for indentation issues."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for mixed indentation
            if re.match(SYNTAX_PATTERNS["mixed_indentation"], line):
                issues.append(
                    SyntaxIssue(
                        file_path=Path(""),
                        line_number=i,
                        column=0,
                        error_type=ErrorType.INDENTATION_ERROR,
                        message="Mixed tabs and spaces in indentation",
                        code_line=line,
                        fixable=True,
                        suggestion="Use consistent 4-space indentation",
                    )
                )

            # Check for invalid indentation levels
            if re.match(SYNTAX_PATTERNS["invalid_indentation"], line):
                issues.append(
                    SyntaxIssue(
                        file_path=Path(""),
                        line_number=i,
                        column=0,
                        error_type=ErrorType.INDENTATION_ERROR,
                        message="Invalid indentation (not a multiple of 4)",
                        code_line=line,
                        fixable=True,
                        suggestion="Use 4-space indentation",
                    )
                )

        return issues

    def _check_imports(self, content: str) -> List[SyntaxIssue]:
        """Check for import-related issues."""
        issues = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "SpyderU16_TechnicalAnalysis" in node.module:
                        for alias in node.names:
                            if alias.name == "VolumeSMAIndicator":
                                issues.append(
                                    SyntaxIssue(
                                        file_path=Path(""),
                                        line_number=node.lineno,
                                        column=node.col_offset,
                                        error_type=ErrorType.IMPORT_ERROR,
                                        message="VolumeSMAIndicator doesn't exist in ta.volume",
                                        code_line="",
                                        fixable=True,
                                        suggestion="Use VolumeWeightedAveragePrice instead",
                                    )
                                )
        except BaseException:
            pass  # If we can't parse, syntax check will catch it

        return issues

    def _check_patterns(self, content: str) -> List[SyntaxIssue]:
        """Check for common syntax pattern issues."""
        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for missing colons
            if re.match(SYNTAX_PATTERNS["missing_colon"], line.strip()):
                issues.append(
                    SyntaxIssue(
                        file_path=Path(""),
                        line_number=i,
                        column=len(line),
                        error_type=ErrorType.MISSING_COLON,
                        message="Missing colon after control statement",
                        code_line=line,
                        fixable=True,
                        suggestion=f"{line.rstrip()}:",
                    )
                )

            # Check for trailing whitespace
            if re.search(SYNTAX_PATTERNS["trailing_whitespace"], line):
                issues.append(
                    SyntaxIssue(
                        file_path=Path(""),
                        line_number=i,
                        column=len(line.rstrip()),
                        error_type=ErrorType.INVALID_SYNTAX,
                        message="Trailing whitespace",
                        code_line=line,
                        fixable=True,
                        suggestion=line.rstrip(),
                    )
                )

        # Check for unclosed brackets
        bracket_stack = []
        bracket_pairs = {"(": ")", "[": "]", "{": "}"}

        for i, line in enumerate(lines, 1):
            for char in line:
                if char in bracket_pairs:
                    bracket_stack.append((char, i))
                elif char in bracket_pairs.values():
                    if bracket_stack and bracket_pairs[bracket_stack[-1][0]] == char:
                        bracket_stack.pop()

        for bracket, line_num in bracket_stack:
            issues.append(
                SyntaxIssue(
                    file_path=Path(""),
                    line_number=line_num,
                    column=0,
                    error_type=ErrorType.UNCLOSED_BRACKET,
                    message=f"Unclosed {bracket} bracket",
                    code_line=lines[line_num - 1] if line_num <= len(lines) else "",
                    fixable=False,
                )
            )

        return issues

    # ==========================================================================
    # FIXING METHODS
    # ==========================================================================

    def _attempt_fixes(self, result: ValidationResult) -> ValidationResult:
        """
        Attempt to fix issues in a file.

        Args:
            result: Validation result with issues

        Returns:
            Updated result with fixes applied
        """
        if not result.original_content:
            return result

        fixed_content = result.original_content
        fixes_applied = 0

        # Apply autopep8 for basic fixes
        try:
            fixed_content = autopep8.fix_code(
                fixed_content, options={"aggressive": 2, "max_line_length": 100}
            )
            fixes_applied += 1
        except BaseException:
            pass

        # Apply black formatting if available
        if BLACK_AVAILABLE:
            try:
                fixed_content = black.format_str(fixed_content, mode=black.Mode(line_length=100))
                fixes_applied += 1
            except BaseException:
                pass

        # Apply isort for import sorting if available
        if ISORT_AVAILABLE:
            try:
                fixed_content = isort.code(fixed_content)
                fixes_applied += 1
            except BaseException:
                pass

        # Custom fixes for specific issues
        for issue in result.issues:
            if issue.fixable and issue.suggestion:
                fixed_content = self._apply_custom_fix(fixed_content, issue)

        # Validate the fixed content
        try:
            ast.parse(fixed_content)
            result.fixed_content = fixed_content
            result.fix_status = FixStatus.FIXED

            # Save fixed file if enabled
            if self.auto_fix:
                backup_path = result.file_path.with_suffix(".py.bak")
                with open(backup_path, "w") as f:
                    f.write(result.original_content)

                with open(result.file_path, "w") as f:
                    f.write(fixed_content)

                print(f"✅ Fixed: {result.file_path}")
                self.stats["files_fixed"] += 1

        except SyntaxError:
            result.fix_status = FixStatus.PARTIALLY_FIXED

        return result

    def _apply_custom_fix(self, content: str, issue: SyntaxIssue) -> str:
        """Apply a custom fix for a specific issue."""
        lines = content.split("\n")

        if issue.line_number > 0 and issue.line_number <= len(lines):
            if issue.error_type == ErrorType.MISSING_COLON:
                lines[issue.line_number - 1] = issue.suggestion or lines[issue.line_number - 1]
            elif issue.error_type == ErrorType.INDENTATION_ERROR:
                # Fix indentation to 4-space multiples
                line = lines[issue.line_number - 1]
                stripped = line.lstrip()
                indent_level = (len(line) - len(stripped)) // 4
                lines[issue.line_number - 1] = "    " * indent_level + stripped

        return "\n".join(lines)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project."""
        python_files = []

        for group in SPYDER_GROUPS:
            group_dir = self.project_root / f"Spyder{group}_*"
            for dir_path in self.project_root.glob(f"Spyder{group}_*"):
                if dir_path.is_dir():
                    python_files.extend(dir_path.glob("*.py"))

        return sorted(python_files)

    def _get_module_group(self, file_path: Path) -> str:
        """Get the module group from file path."""
        match = re.match(r"Spyder([A-Z])", file_path.parent.name)
        return match.group(1) if match else "Other"

    def _classify_syntax_error(self, error: SyntaxError) -> ErrorType:
        """Classify a syntax error."""
        msg = error.msg.lower()

        if "indent" in msg:
            return ErrorType.INDENTATION_ERROR
        elif "import" in msg:
            return ErrorType.IMPORT_ERROR
        elif "name" in msg:
            return ErrorType.NAME_ERROR
        elif "bracket" in msg or "parenthes" in msg:
            return ErrorType.UNCLOSED_BRACKET
        elif "string" in msg or "quote" in msg:
            return ErrorType.UNCLOSED_STRING
        elif "colon" in msg:
            return ErrorType.MISSING_COLON
        else:
            return ErrorType.SYNTAX_ERROR

    def _is_fixable_syntax_error(self, error: SyntaxError) -> bool:
        """Determine if a syntax error is automatically fixable."""
        fixable_messages = [
            "invalid syntax",
            "unexpected indent",
            "expected an indented block",
            "trailing comma",
            "missing colon",
        ]

        return any(msg in error.msg.lower() for msg in fixable_messages)

    def _suggest_fix(self, error: SyntaxError, code_line: str) -> Optional[str]:
        """Suggest a fix for a syntax error."""
        msg = error.msg.lower()

        if "colon" in msg:
            return f"{code_line.rstrip()}:"
        elif "indent" in msg:
            return "    " + code_line.lstrip()

        return None

    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================

    def generate_report(self, output_file: Optional[Path] = None) -> str:
        """
        Generate a detailed validation report.

        Args:
            output_file: Optional file to save report to

        Returns:
            Report as string
        """
        if not self.current_report:
            return "No validation report available. Run validate_all() first."

        report = self.current_report

        # Build report string
        lines = [
            "=" * 80,
            "SPYDER SYNTAX VALIDATION REPORT",
            "=" * 80,
            f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "SUMMARY",
            "-" * 40,
            f"Total Files Scanned: {report.total_files}",
            f"Valid Files: {report.valid_files} ({report.valid_files/max(report.total_files, 1)*100:.1f}%)",
            f"Files with Errors: {report.files_with_errors}",
            f"Total Issues Found: {report.total_issues}",
            f"Issues Fixed: {report.fixed_issues}",
            f"Unfixable Issues: {report.unfixable_issues}",
            "",
            "BY MODULE GROUP",
            "-" * 40,
        ]

        for group in sorted(report.summary_by_group.keys()):
            stats = report.summary_by_group[group]
            lines.append(
                f"Group {group}: {stats['valid']}/{stats['total']} valid, "
                f"{stats['errors']} errors, {stats['fixed']} fixed"
            )

        # List files with errors
        if report.files_with_errors > 0:
            lines.extend(["", "FILES WITH ERRORS", "-" * 40])

            for file_path, result in report.results_by_file.items():
                if not result.valid:
                    lines.append(f"\n{file_path}:")
                    for issue in result.issues[:3]:  # Show first 3 issues
                        lines.append(
                            f"  Line {issue.line_number}: {issue.error_type.value} - {issue.message}"
                        )
                    if len(result.issues) > 3:
                        lines.append(f"  ... and {len(result.issues) - 3} more issues")

        # Success files (brief list)
        if report.valid_files > 0:
            lines.extend(["", f"✅ {report.valid_files} FILES VALIDATED SUCCESSFULLY", ""])

        report_text = "\n".join(lines)

        # Save to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)
            print(f"📄 Report saved to: {output_file}")

        return report_text

    def generate_fix_script(self) -> str:
        """
        Generate a shell script to fix all issues.

        Returns:
            Shell script as string
        """
        if not self.current_report:
            return "# No validation report available"

        script = [
            "#!/bin/bash",
            "# Spyder Syntax Fix Script",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "echo 'Starting Spyder syntax fixes...'",
            "",
        ]

        for file_path, result in self.current_report.results_by_file.items():
            if not result.valid and result.fix_status != FixStatus.UNFIXABLE:
                script.append(f"echo 'Fixing {file_path}...'")
                script.append(f"autopep8 --in-place --aggressive --aggressive {file_path}")

                if BLACK_AVAILABLE:
                    script.append(f"black {file_path} --line-length 100")

                if ISORT_AVAILABLE:
                    script.append(f"isort {file_path}")

                script.append("")

        script.append("echo 'Syntax fixes complete!'")

        return "\n".join(script)


# ==============================================================================
# COMMAND-LINE INTERFACE
# ==============================================================================


def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Spyder Syntax Validator - Automated syntax checking and fixing"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to Spyder project root (default: current directory)",
    )
    parser.add_argument(
        "--fix", action="store_true", help="Automatically fix issues where possible"
    )
    parser.add_argument("--report", help="Save report to specified file")
    parser.add_argument("--script", help="Generate fix script and save to file")

    args = parser.parse_args()

    # Create validator
    validator = SyntaxValidator(args.path, auto_fix=args.fix)

    # Run validation
    report = validator.validate_all()

    # Generate and display report
    report_text = validator.generate_report(Path(args.report) if args.report else None)
    print(report_text)

    # Generate fix script if requested
    if args.script:
        script = validator.generate_fix_script()
        with open(args.script, "w") as f:
            f.write(script)
        os.chmod(args.script, 0o755)
        print(f"\n📝 Fix script saved to: {args.script}")

    # Exit with appropriate code
    sys.exit(0 if report.files_with_errors == 0 else 1)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================


if __name__ == "__main__":
    main()
else:
    print("✅ Syntax Validator Module Loaded - Ready for validation")
