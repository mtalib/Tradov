#!/usr/bin/env python3
"""Compatibility shim for legacy import path.

Canonical module: Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_canonical_symbols() -> dict[str, object]:
	"""Load canonical symbols, with a direct-file fallback for test stubs."""
	try:
		from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import __dict__ as mod_dict
		module_file = mod_dict.get("__file__")
		if module_file and Path(str(module_file)).resolve() != Path(__file__).resolve():
			return mod_dict
	except Exception:
		pass

	# Some test suites inject a non-package module at
	# `Spyder.SpyderU_Utilities`, which breaks normal package imports.
	canonical_path = (
		Path(__file__).resolve().parents[1]
		/ "Spyder"
		/ "SpyderU_Utilities"
		/ "SpyderU02_ErrorHandler.py"
	)
	spec = importlib.util.spec_from_file_location(
		"Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
		str(canonical_path),
	)
	if spec is None or spec.loader is None:
		raise ImportError("Unable to load canonical SpyderU02_ErrorHandler module")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	# Register canonical import key for callers importing through
	# `Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler`.
	parent_key = "Spyder.SpyderU_Utilities"
	parent_mod = sys.modules.get(parent_key)
	if parent_mod is None:
		parent_mod = types.ModuleType(parent_key)
		sys.modules[parent_key] = parent_mod
	if not hasattr(parent_mod, "__path__"):
		parent_mod.__path__ = []  # type: ignore[attr-defined]
	sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = module
	return module.__dict__


_symbols = _load_canonical_symbols()
for _name, _value in list(_symbols.items()):
	if not _name.startswith("_"):
		globals()[_name] = _value
