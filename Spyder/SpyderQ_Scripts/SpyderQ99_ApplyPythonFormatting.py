#!/usr/bin/env python3
"""
Script to apply standard Python formatting to all Spyder modules
"""

import re
from datetime import datetime, timezone
from pathlib import Path

# Get today's date and time
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
NOW_TIME = datetime.now(timezone.utc).strftime("%H:%M:%S")

def extract_module_info(filepath: str) -> tuple[str, str, str]:
    """
    Extract Series, Module name, and Purpose from filename and path.

    Returns:
        Tuple of (series, module_name, purpose_guess)
    """
    path = Path(filepath)
    filename = path.stem

    # Extract series from directory name (e.g., SpyderA_Core -> SpyderA_Core)
    parent_dir = path.parent.name

    if parent_dir.startswith('Spyder') and '_' in parent_dir:
        series = parent_dir
    else:
        series = "SpyderX_Unknown"

    # Module name is the filename
    module_name = filename + ".py"

    # Try to guess purpose from module name
    purpose = f"Module for {filename.replace('Spyder', '').replace('_', ' ').strip()}"

    return series, module_name, purpose


def has_standard_header(content: str) -> bool:
    """Check if file already has the standard header format."""
    # Check for key markers of standard format
    markers = [
        "#!/usr/bin/env python3",
        "# -*- coding: utf-8 -*-",
        "SPYDER - Autonomous Options Trading System",
        "Author: Mohamed Talib"
    ]

    return all(marker in content for marker in markers[:3])


def extract_docstring(content: str) -> str | None:
    """Extract existing module docstring if present."""
    # Match triple-quoted docstring at start of file
    match = re.search(r'^\s*"""(.+?)"""', content, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()

    match = re.search(r"^\s*'''(.+?)'''", content, re.DOTALL | re.MULTILINE)
    if match:
        return match.group(1).strip()

    return None


def extract_imports(content: str) -> tuple[list[str], list[str], list[str]]:
    """
    Extract and categorize imports.

    Returns:
        Tuple of (standard_imports, third_party_imports, local_imports)
    """
    lines = content.split('\n')

    standard_imports = []
    third_party_imports = []
    local_imports = []

    # Standard library modules (common ones)
    stdlib_modules = {
        'os', 'sys', 'time', 'datetime', 'json', 'csv', 'random', 're',
        'threading', 'asyncio', 'logging', 'collections', 'dataclasses',
        'typing', 'enum', 'pathlib', 'uuid', 'warnings', 'copy', 'queue',
        'concurrent', 'functools', 'itertools', 'abc', 'contextlib'
    }

    import_started = False
    for line in lines:
        stripped = line.strip()

        # Skip shebang, encoding, and docstrings
        if stripped.startswith('#!') or stripped.startswith('# -*-') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        if stripped.startswith('import ') or stripped.startswith('from '):
            import_started = True

            # Determine module category
            if stripped.startswith('from '):
                match = re.match(r'from\s+(\S+)', stripped)
                if match:
                    module = match.group(1).split('.')[0]
                else:
                    module = ""
            else:
                match = re.match(r'import\s+(\S+)', stripped)
                if match:
                    module = match.group(1).split('.')[0]
                else:
                    module = ""

            # Categorize
            if module in stdlib_modules:
                standard_imports.append(stripped)
            elif 'Spyder' in stripped or module.startswith('.'):
                local_imports.append(stripped)
            elif module and not module.startswith('_'):
                third_party_imports.append(stripped)
        elif import_started and stripped and not stripped.startswith('#'):
            # Stop at first non-import, non-comment line
            break

    return standard_imports, third_party_imports, local_imports


def extract_code_body(content: str) -> str:
    """Extract the main code body after imports."""
    lines = content.split('\n')

    # Skip shebang, encoding, docstring, and imports
    in_docstring = False
    imports_done = False
    code_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip shebang and encoding
        if stripped.startswith('#!') or stripped.startswith('# -*-'):
            continue

        # Track docstring
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue

        if in_docstring:
            continue

        # Track imports
        if stripped.startswith('import ') or stripped.startswith('from '):
            imports_done = True
            continue

        # Found first non-import line after imports
        if imports_done and stripped and not stripped.startswith('#'):
            code_start = i
            break

    return '\n'.join(lines[code_start:])


def create_standard_header(filepath: str, existing_content: str) -> str:
    """
    Create standard header for a module.
    """
    series, module_name, purpose = extract_module_info(filepath)

    # Try to extract existing docstring for better purpose description
    existing_docstring = extract_docstring(existing_content)
    if existing_docstring:
        # Try to extract purpose from existing docstring
        for line in existing_docstring.split('\n'):
            if line.strip() and len(line.strip()) > 20:
                purpose = line.strip()
                break

    header = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: {series}
Module: {module_name}
Purpose: {purpose}

Author: Mohamed Talib
Year Created: 2025
Last Updated: {TODAY} Time: {NOW_TIME}

Module Description:
    {purpose}

Change Log:
    {TODAY}:
        - Applied standard Python formatting
        - Updated module header and structure
"""

'''

    return header


def format_module(filepath: str) -> bool:
    """
    Apply standard formatting to a Python module.

    Returns:
        True if file was modified, False otherwise
    """
    try:
        # Read existing content
        with open(filepath, encoding='utf-8') as f:
            content = f.read()

        # Skip if already has standard header (to preserve hand-crafted headers)
        if has_standard_header(content):
            print(f"  ⏭️  Skipping {filepath} (already has standard header)")
            return False

        # Skip empty files
        if not content.strip():
            print(f"  ⏭️  Skipping {filepath} (empty file)")
            return False

        # Skip __init__.py files (keep them minimal)
        if filepath.endswith('__init__.py'):
            print(f"  ⏭️  Skipping {filepath} (__init__.py)")
            return False

        # Create new formatted content
        header = create_standard_header(filepath, content)

        # Extract imports
        std_imports, third_party_imports, local_imports = extract_imports(content)

        # Build imports sections
        imports_section = ""

        if std_imports:
            imports_section += "# " + "="*78 + "\n"
            imports_section += "# STANDARD IMPORTS\n"
            imports_section += "# " + "="*78 + "\n"
            imports_section += '\n'.join(std_imports) + "\n\n"

        if third_party_imports:
            imports_section += "# " + "="*78 + "\n"
            imports_section += "# THIRD-PARTY IMPORTS\n"
            imports_section += "# " + "="*78 + "\n"
            imports_section += '\n'.join(third_party_imports) + "\n\n"

        if local_imports:
            imports_section += "# " + "="*78 + "\n"
            imports_section += "# LOCAL IMPORTS\n"
            imports_section += "# " + "="*78 + "\n"
            imports_section += '\n'.join(local_imports) + "\n\n"

        # Extract code body (everything after imports)
        code_body = extract_code_body(content)

        # Combine all sections
        new_content = header + imports_section + code_body

        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  ✅ Formatted {filepath}")
        return True

    except Exception as e:
        print(f"  ❌ Error formatting {filepath}: {e}")
        return False


def main():
    """Main execution function."""
    print("="*80)
    print("SPYDER Python Formatting Script")
    print("="*80)
    print(f"Date: {TODAY}")
    print(f"Time: {NOW_TIME}")
    print("="*80)

    # Get list of all Python files
    base_dir = Path("/home/user/Spyder")

    # Find all Python files in Spyder modules
    python_files = []
    for pattern in ["Spyder/Spyder*/**/*.py", "config/*.py"]:
        python_files.extend(base_dir.glob(pattern))

    # Filter out __pycache__ and .venv
    python_files = [
        f for f in python_files
        if '__pycache__' not in str(f)
        and '.venv' not in str(f)
        and 'Python_Format_Example.py' not in str(f)
    ]

    print(f"\nFound {len(python_files)} Python files to process\n")

    # Process each file
    modified_count = 0
    skipped_count = 0

    for filepath in sorted(python_files):
        if format_module(str(filepath)):
            modified_count += 1
        else:
            skipped_count += 1

    print("\n" + "="*80)
    print("FORMATTING COMPLETE")
    print("="*80)
    print(f"Modified: {modified_count} files")
    print(f"Skipped:  {skipped_count} files")
    print(f"Total:    {len(python_files)} files")
    print("="*80)


if __name__ == "__main__":
    main()
