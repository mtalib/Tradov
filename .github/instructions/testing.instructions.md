---
description: "Use when editing pytest tests, conftest bootstrap logic, or test helpers in Spyder. Covers repo markers, focused validation, bootstrap pollution, and narrow stubbing practices."
applyTo:
  - "Spyder/SpyderT_Testing/**/*.py"
  - "conftest.py"
---
# Testing Guidelines

- Follow the repo markers in [pytest.ini](../../pytest.ini): `unit`, `integration`, `paper`, `live`, `gui`, `manual`, and the other declared markers. Use the smallest appropriate scope.
- Prefer targeted `pytest` runs for the touched slice. For a one-off regression check during local iteration, `--no-cov` is acceptable to avoid unrelated coverage-gate failures masking the result.
- Be careful with bootstrap stubs: do not force-replace `Spyder.*` modules in `sys.modules` unless the real import truly fails, and always restore polluted entries in teardown or cleanup.
- When stubbing inside loops, capture loop variables in default arguments to avoid late-binding bugs.
- Avoid broad PySide6 stubs when a test only needs one widget or item class. Patch the narrowest Qt surface possible.
- Defensive cleanup matters: tests that instantiate via `__new__` or partial initialization should not rely on destructors touching missing attributes.
- References: [conftest.py](../../conftest.py), [pytest.ini](../../pytest.ini), and [Test Coverage Guide](../../02-Standards-Instructions/TEST_COVERAGE_GUIDE.md).