#!/usr/bin/env python3
"""Compatibility package for legacy top-level imports.

This shim allows modules/tests that import
`SpyderU_Utilities.*` to continue working after the package moved under
`Spyder.SpyderU_Utilities.*`.
"""

from pathlib import Path

# Include the canonical utilities directory in package search path so imports
# work consistently whether the alias hook resolves through short or long names.
_shim_dir = Path(__file__).resolve().parent
_canonical_dir = _shim_dir.parent / "Spyder" / "SpyderU_Utilities"

__path__ = [str(_shim_dir)]
if _canonical_dir.is_dir():
	__path__.append(str(_canonical_dir))

