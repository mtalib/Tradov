#!/usr/bin/env python3
"""Compatibility shim for legacy import path.

Canonical module: Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_canonical_symbols() -> dict[str, object]:
	"""Load canonical symbols, with a direct-file fallback for test stubs."""
	try:
		from Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils import __dict__ as mod_dict
		module_file = mod_dict.get("__file__")
		if module_file and Path(str(module_file)).resolve() != Path(__file__).resolve():
			return mod_dict
	except Exception:
		pass

	canonical_path = (
		Path(__file__).resolve().parents[1]
		/ "Spyder"
		/ "SpyderU_Utilities"
		/ "SpyderU05_NetworkUtils.py"
	)
	spec = importlib.util.spec_from_file_location(
		"Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils",
		str(canonical_path),
	)
	if spec is None or spec.loader is None:
		raise ImportError("Unable to load canonical SpyderU05_NetworkUtils module")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	parent_key = "Spyder.SpyderU_Utilities"
	parent_mod = sys.modules.get(parent_key)
	if parent_mod is None:
		parent_mod = types.ModuleType(parent_key)
		sys.modules[parent_key] = parent_mod
	if not hasattr(parent_mod, "__path__"):
		parent_mod.__path__ = []  # type: ignore[attr-defined]
	sys.modules["Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils"] = module
	return module.__dict__


_symbols = _load_canonical_symbols()
for _name, _value in list(_symbols.items()):
	if not _name.startswith("_"):
		globals()[_name] = _value
