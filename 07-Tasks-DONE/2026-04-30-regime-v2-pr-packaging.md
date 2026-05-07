# Regime-v2 Scope Isolation and PR Packaging

Date: 2026-04-30
Branch: fix/audit-v14-all
Target PR: #14

## Functional Validation Status

Authoritative full-suite run:
- Command: /home/adam/Projects/Spyder/.venv/bin/python -m pytest Spyder/SpyderT_Testing -q
- Result: 10040 passed, 18 skipped, 2 xfailed, 48 warnings
- Functional failures: 0
- Coverage gate: failed at 34.04% (required 60%)

Isolated deterministic contract run:
- Command: /home/adam/Projects/Spyder/.venv/bin/python -m pytest Spyder/SpyderT_Testing/SpyderT184_RegimeV2DeterministicContract.py -q -o addopts=''
- Result: 8 passed

## Scope Isolation Facts

Current branch is broad (75 changed files). For regime-v2 packaging from this session:
- Trackable code file in scope:
   - Spyder/SpyderT_Testing/SpyderT184_RegimeV2DeterministicContract.py (new)
- Non-trackable evidence file (gitignored):
  - 11-TestLogs/2026-04-30-regime-v2-finalization.md

Gitignore proof:
- 11-TestLogs/.gitignore contains wildcard rule that ignores files under 11-TestLogs.

## Clean Commit Recipe (Single-File Scope)

1. Stage only scope file:
   git add Spyder/SpyderT_Testing/SpyderT184_RegimeV2DeterministicContract.py

2. Verify staged scope:
   git diff --staged --name-only

3. Commit:
   git commit -m "test(regime-v2): stabilize deterministic L09->D30 contract mapping"

4. Push branch:
   git push origin fix/audit-v14-all

## Optional: Attach Finalization Evidence To PR Description

Because 11-TestLogs is ignored, copy these facts into PR text/comment instead of committing that file:
- full-suite functional status (10040 passed, 0 failed)
- isolated deterministic file status (8 passed)
- coverage-policy blocker (34.04% vs 60%)

## Coverage Track (What Remains)

The only remaining gate blocker is repository-global coverage threshold, not functionality. To close this, follow-up work must add tests in high-LOC/low-coverage modules (for example A03, B02, C16, R04, E01).