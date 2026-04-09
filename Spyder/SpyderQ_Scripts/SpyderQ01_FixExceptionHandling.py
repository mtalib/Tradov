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
def find_exception_issues(file_path: Path) -> list[tuple[int, str, str]]:
    """
    Find exception handling issues in a Python file.

    Args:
        file_path: Path to Python file

    Returns:
        List of (line_number, issue_type, code_snippet) tuples
    """
    issues = []

    try:
        with open(file_path, encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, start=1):
            # Check for broad exception
            if EXCEPTION_PATTERNS['broad_exception'].search(line):
                # Look ahead to see if it's properly handled
                context = ''.join(lines[max(0, line_num-1):min(len(lines), line_num+5)])

                # Check if it has proper logging and re-raises
                has_logging = 'logger.' in context or 'logging.' in context
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
    for _file_path, issues in results.items():
        for _line_num, issue_type, _code in issues:
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
def find_silent_swallowers_ast(file_path: Path) -> list[tuple[int, str]]:
    """
    Use AST analysis to find exception handlers that silently swallow errors.

    A handler is classified as a silent swallower when its body contains
    *no* call to a logging function (``logger.*``, ``logging.*``,
    ``self.logger.*``) **and** does not re-raise the exception.

    This is strictly more accurate than the regex-based approach in
    ``find_exception_issues()`` because it operates on the actual parse
    tree rather than raw text, eliminating false positives caused by
    commented-out code or log calls on the next-but-one line.

    Args:
        file_path: Path to a Python source file.

    Returns:
        List of ``(line_number, handler_summary)`` tuples for each
        silently-swallowing handler found.
    """
    results: list[tuple[int, str]] = []

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return results
    except OSError:
        return results

    # ── AST visitor ──────────────────────────────────────────────────────────

    class _SilentSwallowerVisitor(ast.NodeVisitor):
        """Walk every ExceptHandler and test for logging / re-raise."""

        _LOG_ATTRS = frozenset(
            ["debug", "info", "warning", "warn", "error", "critical",
             "exception", "fatal"]
        )

        def _has_log_call(self, nodes: list[ast.stmt]) -> bool:
            """Return True if any node in *nodes* (recursively) is a log call."""
            for node in ast.walk(ast.Module(body=nodes, type_ignores=[])):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                # logger.error(...) / self.logger.error(...)
                if isinstance(func, ast.Attribute):
                    if func.attr in self._LOG_ATTRS:
                        return True
                # logging.error(...)
                if isinstance(func, ast.Attribute):
                    if isinstance(func.value, ast.Name) and func.value.id == "logging":
                        return True
            return False

        def _has_raise(self, nodes: list[ast.stmt]) -> bool:
            """Return True if any top-level statement in *nodes* is a raise."""
            for node in nodes:
                if isinstance(node, ast.Raise):
                    return True
                # raise inside an if-block at the top of the handler
                if isinstance(node, ast.If):
                    if self._has_raise(node.body) or self._has_raise(node.orelse):
                        return True
            return False

        def _body_is_only_pass(self, nodes: list[ast.stmt]) -> bool:
            return len(nodes) == 1 and isinstance(nodes[0], ast.Pass)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            body = node.body

            is_silent = (
                self._body_is_only_pass(body)
                or (not self._has_log_call(body) and not self._has_raise(body))
            )

            if is_silent:
                # Build a human-readable summary of what type is caught.
                if node.type is None:
                    caught = "bare except"
                elif isinstance(node.type, ast.Tuple):
                    caught = "except (" + ", ".join(
                        (e.id if isinstance(e, ast.Name) else ast.unparse(e))
                        for e in node.type.elts
                    ) + ")"
                elif isinstance(node.type, ast.Name):
                    caught = f"except {node.type.id}"
                else:
                    caught = f"except {ast.unparse(node.type)}"

                if node.name:
                    caught += f" as {node.name}"

                results.append((node.lineno, caught))

            self.generic_visit(node)

    _SilentSwallowerVisitor().visit(tree)
    return results


def scan_silent_swallowers(root_dir: Path) -> dict[Path, list[tuple[int, str]]]:
    """
    Scan all production Python files for silently-swallowing exception handlers.

    Excludes test files, archive, venv, and build artefacts.

    Args:
        root_dir: Repository root to scan.

    Returns:
        Mapping of file path → list of ``(line_number, handler_summary)``.
    """
    results: dict[Path, list[tuple[int, str]]] = {}

    _SKIP_PARTS = frozenset(["SpyderT_Testing", "13-Archive", "__pycache__", ".venv",
                              "htmlcov", "dist", "build"])

    for py_file in sorted(root_dir.rglob("*.py")):
        if any(part in _SKIP_PARTS for part in py_file.parts):
            continue
        hits = find_silent_swallowers_ast(py_file)
        if hits:
            results[py_file] = hits

    return results


def generate_silent_swallower_report(results: dict[Path, list[tuple[int, str]]]) -> str:
    """Format the silent-swallower scan results as a human-readable report."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("SILENT EXCEPTION SWALLOWER REPORT (AST-based)")
    lines.append("=" * 80)
    lines.append("")

    total = sum(len(v) for v in results.values())
    lines.append(f"Files with silent swallowers : {len(results)}")
    lines.append(f"Total silent handlers        : {total}")
    lines.append("")

    # Top offenders
    top = sorted(results.items(), key=lambda x: len(x[1]), reverse=True)
    lines.append("Top files by handler count:")
    for path, hits in top[:15]:
        rel = path.relative_to(SPYDER_ROOT) if SPYDER_ROOT in path.parents else path
        lines.append(f"  {len(hits):3d}  {rel}")
    lines.append("")

    lines.append("=" * 80)
    lines.append("DETAILS")
    lines.append("=" * 80)
    for path, hits in top:
        rel = path.relative_to(SPYDER_ROOT) if SPYDER_ROOT in path.parents else path
        lines.append(f"\n{rel}  ({len(hits)} handlers)")
        for lineno, summary in hits:
            lines.append(f"    Line {lineno:4d}: {summary}")

    lines.append("")
    lines.append("Recommended action: add logger.error(..., exc_info=True) or raise")
    lines.append("Priority files for manual review: P01 (PortfolioManager), P02, H01")
    return "\n".join(lines)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main() -> None:
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
    parser.add_argument(
        '--silent-swallowers',
        action='store_true',
        help='Run AST-based scan for silently-swallowing exception handlers'
    )

    args = parser.parse_args()

    if args.silent_swallowers:
        print("Scanning for silently-swallowing exception handlers (AST)...")
        swallower_results = scan_silent_swallowers(SPYDER_ROOT)
        swallower_report = generate_silent_swallower_report(swallower_results)
        print(swallower_report)
        if args.report:
            report_path = Path(args.report)
            report_path.write_text(swallower_report)
            print(f"\nReport saved to: {report_path}")
        return

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
