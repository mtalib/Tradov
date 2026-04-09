#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ08_ValidatePackageExports.py
Purpose: Validate that every symbol declared in a package's __all__ is actually
         importable and present in the package namespace at runtime.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-02

Module Description:
    Iterates every Spyder series package (A–Z), imports the package, and checks
    that each name in ``__all__`` resolves to a real object in ``dir(package)``.

    A symbol fails validation when:
        • It appears in ``__all__`` but has no matching ``import`` statement in
          ``__init__.py`` (phantom export — e.g. the v3 U-series TechnicalAnalysis
          finding).
        • The import statement references a non-existent module (wrong module
          number — e.g. the v3 E-series E03/E04 finding).
        • The target class / function was removed or renamed (stale export).

    Exit codes:
        0 — all packages clean
        1 — one or more symbols failed validation

Usage::

    # From the project root:
    python Spyder/SpyderQ_Scripts/SpyderQ08_ValidatePackageExports.py

    # Validate a single package:
    python Spyder/SpyderQ_Scripts/SpyderQ08_ValidatePackageExports.py --package SpyderE_Risk

    # Machine-readable JSON output:
    python Spyder/SpyderQ_Scripts/SpyderQ08_ValidatePackageExports.py --json

    # Suppress passing packages (failures only):
    python Spyder/SpyderQ_Scripts/SpyderQ08_ValidatePackageExports.py --failures-only

Dependencies:
    Python standard library only (importlib, argparse, json, sys, pathlib).
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import importlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path setup — allow running from any working directory
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# All 25 Spyder series packages in alphabetical order
# ---------------------------------------------------------------------------
_ALL_PACKAGES: list[str] = [
    "Spyder.SpyderA_Core",
    "Spyder.SpyderB_Broker",
    "Spyder.SpyderC_MarketData",
    "Spyder.SpyderD_Strategies",
    "Spyder.SpyderE_Risk",
    "Spyder.SpyderF_Analysis",
    "Spyder.SpyderG_GUI",
    "Spyder.SpyderH_Storage",
    "Spyder.SpyderI_Integration",
    "Spyder.SpyderJ_Alerts",
    "Spyder.SpyderK_Reports",
    "Spyder.SpyderL_ML",
    "Spyder.SpyderM_Monitoring",
    "Spyder.SpyderN_OptionsAnalytics",
    "Spyder.SpyderO_TradingIntelligence",
    "Spyder.SpyderP_PortfolioMgmt",
    "Spyder.SpyderQ_Scripts",
    "Spyder.SpyderR_Runtime",
    "Spyder.SpyderS_Signals",
    "Spyder.SpyderT_Testing",
    "Spyder.SpyderU_Utilities",
    "Spyder.SpyderV_QuantModels",
    "Spyder.SpyderX_Agents",
    "Spyder.SpyderY_AutoAgents",
    "Spyder.SpyderZ_Communication",
]


# ==============================================================================
# COLOUR HELPERS
# ==============================================================================

class _C:
    """ANSI colour codes (disabled when stdout is not a tty)."""
    _tty = sys.stdout.isatty()
    GREEN  = "\033[92m"  if _tty else ""
    YELLOW = "\033[93m"  if _tty else ""
    RED    = "\033[91m"  if _tty else ""
    BLUE   = "\033[94m"  if _tty else ""
    BOLD   = "\033[1m"   if _tty else ""
    DIM    = "\033[2m"   if _tty else ""
    END    = "\033[0m"   if _tty else ""


def _ok(msg: str) -> str:
    return f"{_C.GREEN}✅ {msg}{_C.END}"

def _warn(msg: str) -> str:
    return f"{_C.YELLOW}⚠️  {msg}{_C.END}"

def _err(msg: str) -> str:
    return f"{_C.RED}❌ {msg}{_C.END}"

def _hdr(msg: str) -> str:
    return f"{_C.BOLD}{_C.BLUE}{msg}{_C.END}"


# ==============================================================================
# VALIDATION LOGIC
# ==============================================================================

def _short_name(pkg: str) -> str:
    """Return the bare series name, e.g. 'SpyderE_Risk'."""
    return pkg.split(".")[-1]


import logging as _logging


class _SilentImport:
    """Context manager: mute logging noise during package import.

    Only suppresses the Python logging system; does not redirect stdout/stderr
    so that import-time side effects (file I/O, sys.modules mutations) are
    not disrupted.
    """

    def __enter__(self) -> _SilentImport:
        self._old_level = _logging.root.manager.disable
        _logging.disable(_logging.CRITICAL)
        return self

    def __exit__(self, *_: object) -> None:
        _logging.disable(self._old_level)


def validate_package(pkg_dotted: str) -> dict[str, Any]:
    """
    Import *pkg_dotted* and check every symbol in its ``__all__``.

    Returns a dict::

        {
            "package":  "Spyder.SpyderE_Risk",
            "status":   "ok" | "import_error" | "failures",
            "error":    "<traceback string>" | None,
            "all_count": int,
            "passed":   ["SymA", "SymB", ...],
            "failed":   [
                {"symbol": "SymC", "reason": "not in dir(package)"},
                ...
            ],
        }
    """
    result: dict[str, Any] = {
        "package":   pkg_dotted,
        "status":    "ok",
        "error":     None,
        "all_count": 0,
        "passed":    [],
        "failed":    [],
    }

    # 1. Import the package (silencing all logging / print output)
    try:
        with _SilentImport():
            pkg = importlib.import_module(pkg_dotted)
    except Exception:
        result["status"] = "import_error"
        result["error"]  = traceback.format_exc()
        return result

    # 2. Read __all__; skip packages that don't define it
    all_names: list[str] = getattr(pkg, "__all__", None)  # type: ignore[assignment]
    if all_names is None:
        result["status"] = "no_all"
        return result

    result["all_count"] = len(all_names)
    pkg_dir = set(dir(pkg))

    # 3. Check each symbol
    for name in all_names:
        if name in pkg_dir:
            # Extra check: make sure it's not just a string constant in dir()
            try:
                obj = getattr(pkg, name, _SENTINEL)
                if obj is _SENTINEL:
                    result["failed"].append({
                        "symbol": name,
                        "reason": "listed in __all__ but getattr() returns sentinel",
                    })
                else:
                    result["passed"].append(name)
            except Exception as exc:
                result["failed"].append({
                    "symbol": name,
                    "reason": f"getattr raised: {exc}",
                })
        else:
            result["failed"].append({
                "symbol": name,
                "reason": "listed in __all__ but absent from dir(package)",
            })

    if result["failed"]:
        result["status"] = "failures"

    return result


_SENTINEL = object()


def _resolve_packages(args: argparse.Namespace) -> list[str]:
    if args.package:
        pkg = args.package
        # Accept short form like "SpyderE_Risk" or full "Spyder.SpyderE_Risk"
        if not pkg.startswith("Spyder."):
            pkg = f"Spyder.{pkg}"
        return [pkg]
    return _ALL_PACKAGES


# ==============================================================================
# REPORTING
# ==============================================================================

def _print_human(results: list[dict[str, Any]], failures_only: bool) -> None:
    width = 70
    print(_hdr("=" * width))
    print(_hdr(f"{'SPYDER — Package Export Validator':^{width}}"))
    print(_hdr("=" * width))

    total_packages = len(results)
    total_symbols  = sum(r["all_count"] for r in results)
    total_passed   = sum(len(r["passed"]) for r in results)
    total_failed   = sum(len(r["failed"]) for r in results)
    import_errors  = sum(1 for r in results if r["status"] == "import_error")
    pkg_failures   = sum(1 for r in results if r["status"] == "failures")

    for r in results:
        short = _short_name(r["package"])
        status = r["status"]

        if status == "import_error":
            print(_err(f"{short:<35} IMPORT ERROR"))
            # Print the first line of the traceback for quick diagnosis
            first_line = r["error"].strip().splitlines()[-1] if r["error"] else ""
            print(f"  {_C.DIM}{first_line}{_C.END}")
            continue

        if status == "no_all":
            if not failures_only:
                print(f"  {_C.DIM}{short:<35} (no __all__ defined — skipped){_C.END}")
            continue

        n_pass = len(r["passed"])
        n_fail = len(r["failed"])

        if n_fail == 0:
            if not failures_only:
                print(_ok(f"{short:<35} {n_pass}/{r['all_count']} symbols OK"))
        else:
            print(_err(f"{short:<35} {n_fail} FAILURE(S) / {r['all_count']} symbols"))
            for f in r["failed"]:
                print(f"    {_C.RED}• {f['symbol']}{_C.END}")
                print(f"      {_C.DIM}{f['reason']}{_C.END}")

    # Summary
    print(_hdr("=" * width))
    print(f"  Packages checked : {total_packages}")
    print(f"  Symbols checked  : {total_symbols}")
    print(f"  Passed           : {_C.GREEN}{total_passed}{_C.END}")
    if import_errors:
        print(f"  Import errors    : {_C.RED}{import_errors}{_C.END}")
    if total_failed:
        print(f"  Failed symbols   : {_C.RED}{total_failed}{_C.END}")
        print(f"  Packages failing : {_C.RED}{pkg_failures}{_C.END}")
    else:
        print(f"  Failed symbols   : {_C.GREEN}0{_C.END}")
    print(_hdr("=" * width))

    if total_failed == 0 and import_errors == 0:
        print(_ok("All package exports validated successfully."))
    else:
        print(_err(f"{total_failed} symbol(s) failed validation across {pkg_failures} package(s)."))


def _print_json(results: list[dict[str, Any]]) -> None:
    # Strip traceback noise from JSON output for readability
    clean = []
    for r in results:
        entry = dict(r)
        if entry.get("error"):
            # Keep only the last line (the actual exception message)
            entry["error"] = entry["error"].strip().splitlines()[-1]
        clean.append(entry)
    print(json.dumps(clean, indent=2))


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate that every __all__ symbol is importable in each Spyder series package.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python SpyderQ08_ValidatePackageExports.py
  python SpyderQ08_ValidatePackageExports.py --package SpyderE_Risk
  python SpyderQ08_ValidatePackageExports.py --failures-only
  python SpyderQ08_ValidatePackageExports.py --json
        """,
    )
    p.add_argument(
        "--package", "-p",
        metavar="SERIES",
        help="Validate a single package (e.g. SpyderE_Risk). Default: all 25 series.",
    )
    p.add_argument(
        "--failures-only", "-f",
        action="store_true",
        help="Suppress passing packages; show only failures and errors.",
    )
    p.add_argument(
        "--json", "-j",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON (suppresses human output).",
    )
    p.add_argument(
        "--no-exit-code",
        action="store_true",
        help="Always exit 0 (useful in CI pipelines where you want the report but not a build failure).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args   = parser.parse_args(argv)

    packages = _resolve_packages(args)
    results  = [validate_package(pkg) for pkg in packages]

    if args.json_output:
        _print_json(results)
    else:
        _print_human(results, failures_only=args.failures_only)

    any_failure = any(
        r["status"] in ("import_error", "failures") for r in results
    )

    if args.no_exit_code:
        return 0
    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
