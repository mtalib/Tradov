#!/usr/bin/env python3
"""
Quick audit script for __init__.py files
"""

import os
import re
from pathlib import Path


def analyze_init_file(filepath):
    """Analyze an __init__.py file and return issues"""
    issues = []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Check file size
    size = len(content)
    if size < 100:
        issues.append(f"Very small file ({size} bytes)")

    # Check for basic elements
    if "__version__" not in content:
        issues.append("Missing __version__")

    if "__all__" not in content:
        issues.append("Missing __all__")

    if "import" not in content and size > 50:
        issues.append("No imports found")

    # Check for documentation
    if '"""' not in content:
        issues.append("Missing docstring")

    # Check for package description
    if "Package:" not in content and "Module:" not in content:
        issues.append("Missing package/module description")

    return issues


def main():
    spyder_root = "/home/adam/Projects/Spyder"
    modules = []

    # Find all Spyder module directories
    for item in os.listdir(spyder_root):
        if item.startswith("Spyder") and os.path.isdir(os.path.join(spyder_root, item)):
            init_file = os.path.join(spyder_root, item, "__init__.py")
            if os.path.exists(init_file):
                modules.append((item, init_file))

    modules.sort()

    print("=== SPYDER __init__.py AUDIT ===\n")

    problem_modules = []

    for module_name, init_path in modules:
        issues = analyze_init_file(init_path)
        if issues:
            problem_modules.append((module_name, issues))
            print(f"🔴 {module_name}:")
            for issue in issues:
                print(f"   • {issue}")
            print()
        else:
            print(f"✅ {module_name}: OK")

    print(f"\n=== SUMMARY ===")
    print(f"Total modules: {len(modules)}")
    print(f"Modules with issues: {len(problem_modules)}")
    print(f"Modules OK: {len(modules) - len(problem_modules)}")

    if problem_modules:
        print(f"\nModules needing attention:")
        for module_name, _ in problem_modules:
            print(f"  - {module_name}")


if __name__ == "__main__":
    main()
