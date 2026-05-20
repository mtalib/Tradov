---
name: focused-regression
description: 'Run a narrow regression or validation loop for Spyder. Use for targeted pytest, --no-cov single-regression checks, touched-path ruff, failing test reruns, or validating one module series without widening scope.'
argument-hint: 'Module path, test path, failing test name, or changed files to validate'
---

# Focused Regression

Use this skill when the goal is to validate a specific Spyder change quickly without jumping to the full suite.

## When to Use

- A single test or module is failing and you want the narrowest rerun.
- You changed one or two files and want a targeted `pytest` plus `ruff` loop.
- Coverage gating would obscure a local regression check.
- You need to validate a broker, GUI, runtime, or test-helper change before widening scope.

## Procedure

1. Identify the smallest executable target.
   - Prefer a direct failing test path or test name.
   - If only a production file changed, map it to the nearest existing test file under `Spyder/SpyderT_Testing`.
   - If no narrow pytest target exists yet, start with `ruff check` on the touched files.

2. Activate the project environment before running Python tooling.
   - `source .venv/bin/activate`

3. Choose the first validation pass.
   - Quick local regression: `pytest <target> --no-cov`
   - CI-style targeted run when needed: `pytest <target>`
   - Lint touched files: `ruff check <paths>`

4. Keep the loop narrow.
   - After the first code edit, run one focused validation before more patching.
   - If the result is a local defect, fix that slice and rerun the same command.
   - Only widen to additional tests when the focused target passes or clearly cannot explain the failure.

5. Account for repo-specific gotchas.
   - Test bootstrap stubs can pollute `sys.modules`; prefer narrow stubs and restore them in cleanup.
   - For GUI regressions, avoid broad PySide6 stubs unless the test truly needs them.
   - For trading-path changes, prefer paper-safe validation and avoid live-only execution flows.

## Output

Return:

- The command or commands selected.
- Why each command is the narrowest useful check.
- The failing tests or lint findings, if any.
- The next smallest rerun to try after a fix.

## References

- [pytest.ini](../../../pytest.ini)
- [ruff.toml](../../../ruff.toml)
- [Test Coverage Guide](../../../02-Standards-Instructions/TEST_COVERAGE_GUIDE.md)
- [testing.instructions.md](../../instructions/testing.instructions.md)
- [trading-safety.instructions.md](../../instructions/trading-safety.instructions.md)