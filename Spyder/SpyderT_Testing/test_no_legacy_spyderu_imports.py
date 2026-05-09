#!/usr/bin/env python3
"""Guardrail test to prevent legacy SpyderU import paths in active code."""

from __future__ import annotations

import ast
from pathlib import Path


LEGACY_PREFIX = "SpyderU_Utilities"
CANONICAL_PREFIX = "Spyder.SpyderU_Utilities"


def _find_legacy_imports(package_root: Path) -> list[str]:
    """Return import locations that still use the legacy short package path."""
    violations: list[str] = []

    for py_file in package_root.rglob("*.py"):
        rel_path = py_file.relative_to(package_root.parent)
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (OSError, SyntaxError) as exc:
            violations.append(f"{rel_path}: unable to parse ({exc})")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name == LEGACY_PREFIX or name.startswith(f"{LEGACY_PREFIX}."):
                        violations.append(
                            f"{rel_path}:{node.lineno}: import {name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if module_name == LEGACY_PREFIX or module_name.startswith(f"{LEGACY_PREFIX}."):
                    violations.append(
                        f"{rel_path}:{node.lineno}: from {module_name} import ..."
                    )

    return violations


def test_no_legacy_spyderu_short_path_imports() -> None:
    """Legacy imports must use Spyder.SpyderU_Utilities canonical path."""
    repo_root = Path(__file__).resolve().parents[2]
    package_root = repo_root / "Spyder"
    violations = _find_legacy_imports(package_root)

    assert not violations, "\n".join(
        [
            f"Found legacy short-path imports. Use {CANONICAL_PREFIX} instead:",
            *sorted(violations),
        ]
    )
