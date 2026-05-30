# 2026-05-28 Root Cleanup

Archived from the repository root during a cleanup pass on 2026-05-28.

This folder contains generated or intermediate artifacts that were cluttering the
root of the repo:

- `bandit-report.txt`
- `bandit_results.txt`
- `diff_part_aa` through `diff_part_aj`
- `files.txt`
- `run_log.txt`
- `test_output.txt`
- `test_results.txt`
- `updated_files.txt`

Deleted instead of archived because they are safe to regenerate:

- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `htmlcov/`
- `coverage.xml`

Moved out of the root as part of the same cleanup:

- `analyze_logs.py` -> `Spyder/SpyderQ_Scripts/analyze_logs.py`
- `check_quotes.py` -> `Spyder/SpyderQ_Scripts/check_quotes.py`
- `restore_script.py` -> `Spyder/SpyderQ_Scripts/restore_script.py`

Left in place intentionally:

- runtime state and databases (`logs/`, `pids/`, `*.db`)