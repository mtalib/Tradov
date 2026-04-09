#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ09_ValidateMissingExports.py
Purpose: Find production modules that exist on disk but are not exported
         (or even imported) in their package __init__.py.

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-04-04

Module Description:
    Complements SpyderQ08_ValidatePackageExports (which verifies declared exports
    actually resolve) by scanning in the opposite direction: for every .py module
    that exists on disk, it checks whether the package __init__.py references the
    module at all.  Modules with zero references are "invisible" — consumers that
    call ``from SpyderX_Package import SomeClass`` will never find them.

    A module is flagged as MISSING when:
    • It is a .py file inside a Spyder series package directory
    • It is not ``__init__.py`` and not a private/dunder file
    • Its filename does not appear ANYWHERE as a string or dotted import in the
      package ``__init__.py``

    This catches the H-1 finding from the v5 codebase audit (129+ invisible modules
    across 16 packages) and can be run as a pre-commit hook to prevent regressions.

Exit codes:
    0 — all modules have at least one reference in their package __init__.py
    1 — one or more modules are completely invisible

Usage::

    # From the project root:
    python Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py

    # Suppress packages with no issues:
    python Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py --failures-only

    # Machine-readable JSON (suitable for CI pipelines):
    python Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py --json

    # Scan a single package:
    python Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py --package SpyderN_OptionsAnalytics

    # Show counts only (summary):
    python Spyder/SpyderQ_Scripts/SpyderQ09_ValidateMissingExports.py --summary

Dependencies:
    Python standard library only (ast, argparse, json, pathlib, sys).
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import ast
import json
import sys
from pathlib import Path
from typing import NamedTuple


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class PackageResult(NamedTuple):
    """Validation result for a single package."""
    package_name: str
    total_modules: int
    missing_modules: list[str]
    referenced_modules: list[str]

    @property
    def missing_count(self) -> int:
        return len(self.missing_modules)

    @property
    def is_clean(self) -> bool:
        return self.missing_count == 0


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Packages to skip (not production series packages)
_SKIP_PACKAGES = frozenset({
    "SpyderT_Testing",  # Test suite — not exported via package __init__
    "SpyderQ_Scripts",  # Launcher scripts — not exported
})

# Module filename prefixes to skip within packages
_SKIP_PREFIXES = frozenset({"__", "test_", "conftest"})


# ==============================================================================
# CORE LOGIC
# ==============================================================================

def _find_spyder_packages(root: Path) -> list[Path]:
    """Return all Spyder series package directories under *root*."""
    return sorted(
        p for p in root.iterdir()
        if p.is_dir()
        and p.name.startswith("Spyder")
        and (p / "__init__.py").exists()
        and p.name not in _SKIP_PACKAGES
    )


def _find_module_files(package_dir: Path) -> list[str]:
    """
    Return bare module names (no .py suffix) that should be exported.

    Excludes __init__.py, private files, and test files.
    """
    modules: list[str] = []
    for py_file in sorted(package_dir.glob("*.py")):
        name = py_file.stem
        if name == "__init__":
            continue
        if any(name.startswith(prefix) for prefix in _SKIP_PREFIXES):
            continue
        modules.append(name)
    return modules


def _init_references(init_path: Path) -> set[str]:
    """
    Return all identifiers referenced in an __init__.py that look like module names.

    Strategy:
    1. Parse the AST to find all ``from .SpyderXNN_Name import ...`` and
       ``import .SpyderXNN_Name`` statements.
    2. Also do a raw string scan for any substring that matches the module stem
       (catches dynamic imports like ``importlib.import_module(".SpyderX01_Foo", ...)``).
    """
    source = init_path.read_text(encoding="utf-8")
    referenced: set[str] = set()

    # --- AST scan ---
    try:
        tree = ast.parse(source, filename=str(init_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # from .SpyderXNN_Name import ...
                mod = node.module or ""
                # Strip leading dots and package prefix
                stem = mod.lstrip(".").split(".")[-1]
                if stem:
                    referenced.add(stem)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    stem = alias.name.split(".")[-1]
                    referenced.add(stem)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Catch string literals that may be module names
                val = node.value.strip(".")
                if val.startswith("Spyder"):
                    referenced.add(val.split(".")[-1])
    except SyntaxError:
        pass  # Fall through to raw string scan

    # --- Raw string scan (catches f-strings, dynamic imports, comments) ---
    lines = source.splitlines()
    for line in lines:
        if "#" in line:
            line = line[:line.index("#")]
        for token in line.replace("'", '"').split('"'):
            token = token.strip().lstrip(".")
            if token.startswith("Spyder") and token.replace("_", "").isalnum():
                referenced.add(token.split(".")[-1])

    return referenced


def validate_package(package_dir: Path) -> PackageResult:
    """
    Validate a single package, returning all missing module names.

    Args:
        package_dir: Path to the package directory containing __init__.py.

    Returns:
        PackageResult with counts and lists of missing/referenced modules.
    """
    init_path = package_dir / "__init__.py"
    all_modules = _find_module_files(package_dir)
    referenced = _init_references(init_path)

    missing: list[str] = []
    found: list[str] = []

    for module_name in all_modules:
        if module_name in referenced:
            found.append(module_name)
        else:
            missing.append(module_name)

    return PackageResult(
        package_name=package_dir.name,
        total_modules=len(all_modules),
        missing_modules=missing,
        referenced_modules=found,
    )


def run_validation(
    root: Path,
    single_package: str | None = None,
    failures_only: bool = False,
    as_json: bool = False,
    summary_only: bool = False,
) -> int:
    """
    Run the missing-exports validation across all (or one) packages.

    Returns:
        int: Exit code — 0 (all clean) or 1 (failures found).
    """
    packages = _find_spyder_packages(root)

    if single_package:
        packages = [p for p in packages if p.name == single_package]
        if not packages:
            msg = f"Package '{single_package}' not found under {root}"
            if as_json:
                print(json.dumps({"error": msg}))
            else:
                print(f"ERROR: {msg}", file=sys.stderr)
            return 1

    results = [validate_package(p) for p in packages]
    total_missing = sum(r.missing_count for r in results)

    # ----------------------------------------------------------------
    # JSON output
    # ----------------------------------------------------------------
    if as_json:
        payload = {
            "total_packages": len(results),
            "packages_with_missing": sum(1 for r in results if not r.is_clean),
            "total_missing_modules": total_missing,
            "packages": [
                {
                    "package": r.package_name,
                    "total_modules": r.total_modules,
                    "missing_count": r.missing_count,
                    "missing": r.missing_modules,
                    "referenced": r.referenced_modules,
                    "status": "CLEAN" if r.is_clean else "MISSING_EXPORTS",
                }
                for r in results
                if not (failures_only and r.is_clean)
            ],
        }
        print(json.dumps(payload, indent=2))
        return 0 if total_missing == 0 else 1

    # ----------------------------------------------------------------
    # Human-readable output
    # ----------------------------------------------------------------
    WIDTH = 72
    print("=" * WIDTH)
    print("  Spyder Missing-Exports Validator (Q09)")
    print("=" * WIDTH)

    for r in results:
        if failures_only and r.is_clean:
            continue

        status = "✓ CLEAN" if r.is_clean else f"✗ {r.missing_count} MISSING"
        print(f"\n[{status}] {r.package_name}  ({r.total_modules} modules on disk)")

        if not r.is_clean and not summary_only:
            for mod in r.missing_modules:
                print(f"    ↳ NOT REFERENCED: {mod}.py")

    print("\n" + "-" * WIDTH)
    packages_clean = sum(1 for r in results if r.is_clean)
    packages_dirty = len(results) - packages_clean
    print(f"  Packages scanned : {len(results)}")
    print(f"  Packages clean   : {packages_clean}")
    print(f"  Packages missing : {packages_dirty}")
    print(f"  Total invisible  : {total_missing} modules")

    if total_missing == 0:
        print("\n  ✓ All modules are referenced in their package __init__.py")
    else:
        print(
            f"\n  ✗ {total_missing} module(s) have NO reference in their package __init__.py"
        )
        print("    Add import statements or remove unused files to silence this.")
    print("=" * WIDTH)

    return 0 if total_missing == 0 else 1


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="SpyderQ09_ValidateMissingExports",
        description=(
            "Find Spyder modules that exist on disk but are not referenced "
            "anywhere in their package __init__.py (invisible modules)."
        ),
    )
    parser.add_argument(
        "--package",
        metavar="PACKAGE_NAME",
        help="Validate a single package (e.g. SpyderN_OptionsAnalytics).",
    )
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Only print packages that have missing exports.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output results as a JSON object.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        dest="summary_only",
        help="Print counts only, not individual missing module names.",
    )
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=None,
        help=(
            "Root directory containing the Spyder series packages. "
            "Defaults to the 'Spyder/' sub-directory relative to this script."
        ),
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Resolve root
    if args.root:
        root = Path(args.root).resolve()
    else:
        # Script lives in Spyder/SpyderQ_Scripts/ — go up one level
        script_dir = Path(__file__).resolve().parent
        root = script_dir.parent  # Spyder/

    if not root.exists():
        print(f"ERROR: root directory not found: {root}", file=sys.stderr)
        return 2

    return run_validation(
        root=root,
        single_package=args.package,
        failures_only=args.failures_only,
        as_json=args.as_json,
        summary_only=args.summary_only,
    )


if __name__ == "__main__":
    sys.exit(main())
