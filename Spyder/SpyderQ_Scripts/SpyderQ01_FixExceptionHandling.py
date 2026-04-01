#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Script: fix_exception_handling.py
Purpose: Helper script to identify and suggest fixes for broad exception handlers

This script scans the codebase for problematic exception handling patterns
and provides recommendations for improvement.

Usage:
    python Spyder/SpyderQ_Scripts/fix_exception_handling.py --check
    python Spyder/SpyderQ_Scripts/fix_exception_handling.py --fix --module SpyderR04_LiveEngine.py
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import ast
import re
from pathlib import Path
from typing import List, Tuple

# ==============================================================================
# CONFIGURATION
# ==============================================================================
SPYDER_ROOT = Path(__file__).parent.parent
EXCEPTION_PATTERNS = {
    'broad_exception': re.compile(r'except\s+Exception\s+as\s+\w+:'),
    'bare_except': re.compile(r'except\s*:'),
    'pass_after_exception': re.compile(r'except.*:\s*pass'),
}

# Recommended specific exceptions for common scenarios
EXCEPTION_RECOMMENDATIONS = {
    'network': ['ConnectionError', 'TimeoutError', 'URLError'],
    'file': ['FileNotFoundError', 'PermissionError', 'IOError'],
    'parsing': ['ValueError', 'KeyError', 'json.JSONDecodeError'],
    'broker': ['ConnectionError', 'TimeoutError', 'BrokerAPIError'] ,
    'calculation': ['ValueError', 'ZeroDivisionError', 'OverflowError'],
}


# ==============================================================================
# HELPER FUNCTIONS  
# ==============================================================================
def find_exception_issues(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Find exception handling issues in a Python file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of (line_number, issue_type, code_snippet) tuples
    """
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, start=1):
            # Check for broad exception
            if EXCEPTION_PATTERNS['broad_exception'].search(line):
                # Look ahead to see if it's properly handled
                context = ''.join(lines[max(0, line_num-1):min(len(lines), line_num+5)])
                
                # Check if it has proper logging and re-raises
                has_logging = 'logger.' in context or 'logging.' in context
                has_reraise = 'raise' in context
                has_exc_info = 'exc_info=True' in context
                
                if not (has_logging and has_exc_info):
                    issues.append((
                        line_num,
                        'broad_exception_no_exc_info',
                        line.strip()
                    ))
            
            # Check for bare except
            if EXCEPTION_PATTERNS['bare_except'].search(line):
                issues.append((
                    line_num,
                    'bare_except',
                    line.strip()
                ))
            
            # Check for except-pass
            if EXCEPTION_PATTERNS['pass_after_exception'].search(line):
                issues.append((
                    line_num,
                    'exception_pass',
                    line.strip()
                ))
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    
    return issues


def suggest_fix(issue_type: str, code_snippet: str, context: str) -> str:
    """
    Suggest a fix for an exception handling issue.
    
    Args:
        issue_type: Type of issue found
        code_snippet: Original code
        context: Surrounding context to determine appropriate exceptions
        
    Returns:
        Suggested fix as string
    """
    suggestions = {
        'broad_exception_no_exc_info': """
# ❌ Current (problematic):
except Exception as e:
    logger.error(f"Error: {e}")

# ✅ Better:
except (ConnectionError, TimeoutError) as e:
    logger.error(f"Network error: {e}")
    # Handle recoverable errors
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    return default_value
except Exception as e:
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise  # Re-raise unexpected errors
""",
        'bare_except': """
# ❌ Current (problematic):
except:
    pass

# ✅ Better:
except (SpecificError1, SpecificError2) as e:
    logger.warning(f"Expected error: {e}")
    # Handle gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
""",
        'exception_pass': """
# ❌ Current (problematic):
except Exception:
    pass  # Silent failure

# ✅ Better:
except ExpectedError as e:
    logger.debug(f"Expected condition: {e}")
    # Handle explicitly
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return default_or_raise
"""
    }
    
    return suggestions.get(issue_type, "No suggestion available")


def scan_codebase(root_dir: Path) -> dict:
    """
    Scan entire codebase for exception handling issues.
    
    Args:
        root_dir: Root directory to scan
        
    Returns:
        Dictionary of {file_path: [issues]}
    """
    results = {}
    
    # Scan all Python files
    for py_file in root_dir.rglob("*.py"):
        # Skip test files and archive
        if any(part in py_file.parts for part in ['SpyderT_Testing', '13-Archive', '__pycache__', '.venv']):
            continue
        
        issues = find_exception_issues(py_file)
        if issues:
            results[py_file] = issues
    
    return results


def generate_report(results: dict) -> str:
    """Generate a report of exception handling issues."""
    report = []
    report.append("=" * 80)
    report.append("EXCEPTION HANDLING ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")
    
    total_issues = sum(len(issues) for issues in results.values())
    report.append(f"Total files with issues: {len(results)}")
    report.append(f"Total issues found: {total_issues}")
    report.append("")
    
    # Group by issue type
    issue_counts = {}
    for file_path, issues in results.items():
        for line_num, issue_type, code in issues:
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    
    report.append("Issues by type:")
    for issue_type, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
        report.append(f"  {issue_type}: {count}")
    report.append("")
    
    # Detail by file
    report.append("=" * 80)
    report.append("DETAILS BY FILE")
    report.append("=" * 80)
    report.append("")
    
    for file_path, issues in sorted(results.items(), key=lambda x: len(x[1]), reverse=True):
        report.append(f"\n{file_path.relative_to(SPYDER_ROOT)}")
        report.append(f"  {len(issues)} issue(s)")
        
        for line_num, issue_type, code in issues:
            report.append(f"    Line {line_num}: {issue_type}")
            report.append(f"      {code}")
        
        report.append("")
    
    # Add recommendations
    report.append("=" * 80)
    report.append("RECOMMENDATIONS")
    report.append("=" * 80)
    report.append("")
    report.append("1. Replace broad `except Exception` with specific exceptions")
    report.append("2. Always include exc_info=True for unexpected errors")
    report.append("3. Never use bare `except:` without qualification")
    report.append("4. Never silently pass on exceptions")
    report.append("5. Re-raise unexpected exceptions after logging")
    report.append("")
    report.append("See generated examples above for each issue type.")
    report.append("")
    
    return "\n".join(report)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze and fix exception handling issues"
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='Scan codebase and report issues'
    )
    parser.add_argument(
        '--report',
        type=str,
        help='Output report to file'
    )
    parser.add_argument(
        '--module',
        type=str,
        help='Specific module to analyze'
    )
    
    args = parser.parse_args()
    
    if args.check:
        print("Scanning codebase for exception handling issues...")
        
        if args.module:
            # Scan specific module
            module_path = SPYDER_ROOT / args.module
            if module_path.exists():
                results = {module_path: find_exception_issues(module_path)}
            else:
                print(f"Module not found: {module_path}")
                return
        else:
            # Scan entire codebase
            results = scan_codebase(SPYDER_ROOT)
        
        # Generate report
        report = generate_report(results)
        print(report)
        
        # Save to file if requested
        if args.report:
            report_path = Path(args.report)
            report_path.write_text(report)
            print(f"\nReport saved to: {report_path}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
