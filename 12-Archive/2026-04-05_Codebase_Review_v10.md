# Spyder Codebase Review — v10

> **Date:** 2026-04-05
> **Reviewer:** Claude Sonnet 4.6
> **Scope:** Fresh audit of 460 Python files. All ruff violations enumerated; runtime bugs identified via
> AST analysis; dead-code and style findings catalogued.
> **Prior reviews:** v1–v9 (earlier cycles), v9 (2026-04-05)
> **Status:** 3 high-severity runtime bugs, 5 medium-severity issues, 12 notice-level items, 3 new opportunities

---

## Executive Summary

A fresh pass over the 460-file codebase via `ruff`, AST analysis, and manual inspection found **464 ruff
violations** (312 auto-fixable), **3 genuine runtime bugs** that will raise `NameError` if their code
paths execute, and **5 medium-severity issues** spanning legacy remnants and code quality. All v9
open items remain unaffected.

| Category | Count | Auto-fixable |
|----------|------:|-------------:|
| High — runtime `NameError` bugs | 3 | No |
| Medium — runtime risks / legacy stubs | 5 | Partial |
| Notice — style / dead code | 12 | Most |
| Opportunities (new) | 3 | Yes/No |
| Carried-over opportunities (v9) | 3 | Yes/No |

---

## Part 1 — High-Severity: Runtime Bugs

### H-1 · `self` referenced in module-level functions — P01, P02

**Files:**
- `SpyderP_PortfolioMgmt/SpyderP01_PortfolioManager.py` L1911, L1978
- `SpyderP_PortfolioMgmt/SpyderP02_AllocationOptimizer.py` L1964, L2021, L2099

**Problem:**  
Five module-level functions (not methods) reference `self.logger.debug(...)` inside their `except`
clauses. `self` is undefined at module scope — these raise `NameError` if the `except` branch executes,
silently preventing the fallback return value and crashing the calculation.

Affected functions:

| File | Line | Function |
|------|------|---------|
| P01 | 1893 / 1911 | `calculate_portfolio_correlation()` |
| P01 | 1916 / 1978 | `optimize_portfolio_allocation()` |
| P02 | ~1960 / 1964 | `calculate_efficient_frontier()` |
| P02 | ~2015 / 2021 | `optimize_black_litterman_views()` |
| P02 | ~2095 / 2099 | test-allocation block inside `__main__`-style function |

**Fix:** Replace `self.logger.debug(...)` with `logging.getLogger(__name__).debug(...)` in all five
locations. Each file already imports `logging`.

```python
# Before
except Exception as e:
    self.logger.debug(f"calculate_portfolio_correlation calculation error: {e}")

# After
except Exception as e:
    logging.getLogger(__name__).debug("calculate_portfolio_correlation error: %s", e)
```

---

### H-2 · `symbol` undefined in `R04_LiveEngine._calculate_order_value`

**File:** `SpyderR_Runtime/SpyderR04_LiveEngine.py` L1004, L1010, L1012

**Problem:**  
`_calculate_order_value(self, order: dict[str, Any])` fetches live price for market orders using the
variable `symbol`, which is never extracted from the `order` dict. On the market-order path (where
`price == 0`), the code reaches L1004 and raises `NameError: name 'symbol' is not defined`. This
would fire during live trading whenever a market order lacks an explicit price.

**Fix:** Extract `symbol` from `order` before the inner `try` block:

```python
# Add before the inner try (around L1002):
symbol = order.get('symbol', '')

# Existing code then works:
quotes = self.broker.get_quotes([symbol]) if symbol else {}
```

---

### H-3 · `__all__.extend()` before `__all__` is defined — SpyderI/__init__.py

**File:** `SpyderI_Integration/__init__.py` L97 vs L212

**Problem:**  
L97 calls `__all__.extend(["AnalysisManager"])` inside the `try` block that imports
`SpyderI05_DiagnosticsEngine_Analyzers`. The `__all__ = [...]` list is not defined until L212. If
`SpyderI05` is importable (which it is on a complete install), importing
`Spyder.SpyderI_Integration` raises:

```
NameError: name '__all__' is not defined
```

This silently breaks all callers of the integration package.

**Fix:** Move `__all__: list[str] = []` to the top of the module (before the first `try:` block):

```python
# After version constants, before any try: import blocks
__all__: list[str] = []
```

The existing `__all__ = [...]` at L212 then simply re-assigns (harmless) or can be removed and folded
into the top-level list.

---

## Part 2 — Medium-Severity Issues

### M-1 · `builtins` and `logging` undefined in X16 MetaCoordinator

**File:** `SpyderX_Agents/SpyderX16_MetaCoordinator.py`

Two separate undefined-name bugs:

| Line | Problem | Fix |
|------|---------|-----|
| L85 | `logging.getLogger(__name__).warning(...)` — `logging` not imported | Add `import logging` to module imports |
| L523 | `except builtins.TimeoutError:` — `builtins` not imported | Change to `except (TimeoutError, asyncio.TimeoutError):` |

The L523 fix is preferred over `import builtins` because `asyncio.wait_for` raises `asyncio.TimeoutError`
(aliased to `TimeoutError` in Python 3.11+), so catching both covers all Python 3.10/3.11 targets.

---

### M-2 · `logging` undefined in Q04 LaunchDashboard

**File:** `SpyderQ_Scripts/SpyderQ04_LaunchDashboard.py` L473

**Problem:** A method inside a GUI class calls `logging.getLogger(__name__).debug(...)`. Q04's
module-level imports (`sys`, `os`, `datetime`, `Path`) do not include `logging`.

**Fix:** Add `import logging` to the standard-library imports section of Q04.

---

### M-3 · Legacy `IB()` stub in Q06 — NameError on execution

**File:** `SpyderQ_Scripts/SpyderQ06_LaunchDashboardDirect.py` L140

**Problem:** The IBKR migration left a dead connection loop that calls `IB()` (the `ib_insync`
class). `IB` is never imported. The loop comment says *"legacy — uses Tradier now"* but the dead
code is still present and will raise `NameError: name 'IB' is not defined` if the connection path
is reached.

**Fix:** Remove the entire IBKR connection loop (the `for client_id, config in self.client_configs`
block that calls `IB()`) and replace with a `self.logger.warning("IBKR connections removed — use
Tradier")` stub, or delete the method outright if it has no callers.

---

### M-4 · Legacy `Contract`, `Ticker`, `Order` type annotations in R02

**File:** `SpyderR_Runtime/SpyderR02_PaperEngine.py` L131, L205, L281

**Problem:** Three IBKR types remain as type annotations after the Tradier migration:

| Line | Annotation | Status |
|------|-----------|--------|
| L131 | `contract: Contract \| None = None` | `Contract` never imported |
| L205 | `self.market_data: dict[str, Ticker] = {}` | `Ticker` never imported |
| L281 | `def place_order(self, contract: Contract, order: Order)` | Both never imported |

Additionally, R02 has `import logging` on both L32 and L50 (F811 duplicate import).

**Fix:**
- Replace `Contract`, `Ticker`, `Order` with `Any` (already imported) or define local stubs.
- Remove the duplicate `import logging` at L50.

---

### M-5 · 86 unused imports (F401) across 50+ production files

**Scope:** 86 F401 violations outside test files. Notable non-trivial cases:

| File | Unused import | Note |
|------|--------------|------|
| `SpyderA01_Main.py` | `ConfigurationError` | Imported inside try-block but never used |
| `SpyderB00_OrderTypes.py` | `Union` | Replaced by `X \| Y` syntax throughout |
| `SpyderB40_TradierClient.py` | `CircuitBreakerError` | Imported alongside `tradier_breaker` but not caught |
| `SpyderC00_MarketDataProtocol.py` | `MassiveClient` | Conditional import that's never referenced |

The bulk (80+) are auto-fixable:

```bash
ruff check --select F401 --fix Spyder/
```

Verify after: a small number of `F401` items in optional-import `try:` blocks may need manual review
(those marked `consider using importlib.util.find_spec`).

---

## Part 3 — Notice: Style and Dead Code

### N-1 · F811 duplicate imports (2 files)

| File | Duplicate |
|------|-----------|
| `SpyderR_Runtime/SpyderR02_PaperEngine.py` L32, L50 | `import logging` twice |
| `SpyderC_MarketData/SpyderC19_AfterHoursDataManager.py` L23, L25 | `import os` twice |

Auto-fixable: `ruff check --select F811 --fix Spyder/SpyderR_Runtime/SpyderR02_PaperEngine.py Spyder/SpyderC_MarketData/SpyderC19_AfterHoursDataManager.py`

---

### N-2 · UP017 — `timezone.utc` → `datetime.UTC` (6 production files)

18 violations total; 6 outside tests:

| File |
|------|
| `SpyderG_GUI/SpyderG32_AgentHealthDashboard.py` |
| `SpyderJ_Alerts/SpyderJ03_WebhookNotifier.py` |
| `SpyderM_Monitoring/SpyderM08_HealthEndpoint.py` |
| `SpyderU_Utilities/SpyderU12_AgentIntegration.py` |
| `SpyderU_Utilities/SpyderU42_StrategyCircuitBreaker.py` |
| `SpyderU_Utilities/SpyderU43_CorrelationLogger.py` |

Auto-fixable: `ruff check --select UP017 --fix Spyder/`

---

### N-3 · UP009 — Redundant UTF-8 encoding declarations (6 files)

`# -*- coding: utf-8 -*-` is the default in Python 3 and can be removed:

```
SpyderD_Strategies/SpyderD06_BullPutSpread.py
SpyderD_Strategies/SpyderD07_BearCallSpread.py
SpyderI_Integration/SpyderI12_ModuleRegistry.py
SpyderM_Monitoring/SpyderM08_HealthEndpoint.py
SpyderX_Agents/SpyderX06_BacktestingAgent.py
SpyderY_AutoAgents/SpyderY_InferenceBackends.py
```

Auto-fixable: `ruff check --select UP009 --fix Spyder/`

---

### N-4 · UP042 — `(str, Enum)` → `StrEnum` (2 production files)

| File | Class |
|------|-------|
| `SpyderC_MarketData/SpyderC29_DataProviderRouter.py` | `DataProvider` |
| `SpyderJ_Alerts/SpyderJ03_WebhookNotifier.py` | `Severity` |

`StrEnum` requires Python ≥ 3.11. Confirm the minimum target version before applying.

Auto-fixable with: `ruff check --select UP042 --fix Spyder/`

---

### N-5 · One-off fixable violations (UP037, UP043, F541, B007, E701)

| Rule | Count | File(s) | Fix |
|------|------:|--------|-----|
| UP037 quoted annotation | 1 | `SpyderX02_FlowAgent.py:265` | `ruff --fix` |
| UP043 default type args | 1 | `SpyderU43_CorrelationLogger.py:166` | `ruff --fix` |
| F541 f-string no placeholder | 2 | `SpyderC28_MassiveHistoricalDownloader.py:434`, `SpyderH08_TradeJournal.py:582` | `ruff --fix` |
| B007 unused loop var | 3 | `SpyderQ01_FixExceptionHandling.py:203-204` | Rename to `_file_path`, `_line_num`, `_code` |
| E701 multi-statement line | 5 | `SpyderU12_AgentIntegration.py:274-277` | Expand to separate lines |

Batch fix: `ruff check --select UP037,UP043,F541 --fix Spyder/`

---

### N-6 · 229 trailing-whitespace violations (W293/W291)

G05 carries 14 (already tracked as Opp-4). The remaining 215 are spread across ~50 files.

Auto-fixable: `ruff check --select W293,W291 --fix Spyder/`

---

### N-7 · Dead `__init__.py` imports pointing to non-existent modules (3 files)

| File | Missing module | Consequence |
|------|---------------|-------------|
| `SpyderI_Integration/__init__.py:105` | `SpyderI05_DiagnosticsEngine_Analyzers` | `ImportError` silently swallowed every startup — `AnalysisManager` never available |
| `SpyderF_Analysis/__init__.py:105` | `SpyderF12_AdvancedBacktestingEngine` | Same; `AdvancedBacktestingEngine` always absent |
| `SpyderT_Testing/__init__.py:66,90` | `SpyderT02_BrokerTestSuite`, `SpyderT05_LiveIBConnectionTest` | IBKR-era test files, never existed post-migration |

**Recommended action:** Remove the `try:` blocks for the missing modules entirely. The dead
`except ImportError` branches produce misleading warning logs on every import of these packages.

---

### N-8 · 73 `print()` calls (T201) in production packages

Files with `print()` outside test blocks:

```
SpyderC27_MassiveClient.py      SpyderS04_BlackSwanScheduler.py
SpyderS08_ShortSqueezeDetector  SpyderH08_TradeJournal.py
SpyderS03_BlackSwanIndicator    SpyderU04_Encryption.py
SpyderU42_StrategyCircuitBreaker SpyderU43_CorrelationLogger.py
SpyderX06_BacktestingAgent      SpyderX08_PerformanceAnalyticsAgent.py
```

Most are inside `if __name__ == "__main__"` demo blocks, which is acceptable. The non-`__main__`
occurrences should be converted to `logger.info(...)` calls. A targeted scan:

```bash
ruff check --select T201 Spyder/ 2>&1 | grep -v "__main__"
```

---

### N-9 · `logging.basicConfig()` called inside a production method (not `__main__`)

**File:** `SpyderA_Core/SpyderA01_Main.py` L551, L563

Both calls are inside `_setup_logging()` (the fallback branch when `SpyderLogger` is unavailable).
`logging.basicConfig()` is idempotent — it is a no-op if handlers are already attached — so this
is unlikely to cause runtime damage. However it is an anti-pattern: a library/component should not
configure the root logger. If `SpyderLogger` ever fails to load during production startup, the root
logger would be reconfigured at an unexpected point.

**Recommended action:** Replace the `basicConfig` fallback with a `StreamHandler` added only to
the package logger (`logging.getLogger('Spyder')`), not the root logger.

---

### N-10 · `SpyderQ06` dead IBKR connection loop

**File:** `SpyderQ_Scripts/SpyderQ06_LaunchDashboardDirect.py`

Beyond the `IB()` NameError (M-3 above), the entire multi-client connection loop (~30 lines) is
unreachable code following the Tradier migration. The loop iterates `self.client_configs`, which
appears to have no Tradier-compatible entries. The whole method should either be replaced with a
Tradier health-check or removed.

---

### N-11 · `SpyderR02_PaperEngine` — duplicate `import logging` on L50

Already covered in M-4 but worth noting explicitly: L50 (`import logging`) comes after the
SpyderLogger/SpyderErrorHandler imports on L48–49, shadowing the first `import logging` at L32.
The F811 auto-fix handles this.

---

### N-12 · `Spyder/__init__.py` top-level package missing `__all__`

**File:** `Spyder/__init__.py`

The top-level package `__init__.py` is the only `__init__` file in the production tree without an
`__all__` declaration. While not a runtime bug, its absence means `from Spyder import *` exports
everything, which is unintentional. A minimal `__all__ = []` (or an explicit export list) would
bring it in line with all sub-packages.

---

## Part 4 — Opportunities (New)

### Opp-5 · f-string logging — 2,569 sites (performance anti-pattern)

**Status:** 🔵 Open — large scope, safe to defer

Every `logger.debug(f"msg {val}")` call evaluates the f-string unconditionally, even when the
`DEBUG` level is suppressed. The correct pattern is lazy `%`-format:

```python
# Before (eager evaluation)
self.logger.debug(f"Order {order_id} placed for {symbol}")

# After (lazy — format string only evaluated if DEBUG is active)
self.logger.debug("Order %s placed for %s", order_id, symbol)
```

Count: `2,569` logger calls use f-strings in production files. This is a mechanical transformation
but touches nearly every file. Suggest applying incrementally — start with hot paths in A-series
(core) and B-series (broker), run `pytest -x` after each package.

A `ruff` rule for this is `G004` (requires enabling the `G` flake8-logging-format plugin):

```bash
ruff check --select G004 Spyder/
```

---

### Opp-6 · Batch auto-fix — 312 ruff violations in one pass

**Status:** 🔵 Open — zero risk, ~5 minutes

312 of the 464 violations are flagged `[*]` (safe auto-fix). Running:

```bash
ruff check --fix Spyder/
```

will resolve in one pass: W293/W291 trailing whitespace (229), F401 unused imports (86 — review
output), F811 duplicate imports, F541 f-string placeholders, UP017, UP009, UP037, UP043.

Run `pytest -x` afterward to confirm no regressions.

---

### Opp-7 · UP007 `Optional[X]` → `X | None` (carried from v9, Opp-2)

**Status:** 🔵 Open

Confirmed 0 violations as of current scan (`ruff --select UP007` returns clean). Opp-2 is now
**closed** — no action needed.

---

## Part 5 — Carried-Over Open Items (v9)

| ID | Description | Status |
|----|-------------|--------|
| **Opp-3** | Upgrade `PRIMARY`/`CODE` Ollama roles to `gemma4:26b` | 🔵 Open (RAM-gated) |
| **Opp-4** | G05 18 pre-existing ruff violations | 🔵 Open |
| **OpenVINO** | `optimum-intel` upstream incompatibility with `transformers 5.x` | ⛔ Blocked |

---

## Appendix A — Open Item Summary

| ID | Severity | File(s) | Description | Status |
|----|----------|---------|-------------|--------|
| **H-1** | 🔴 High | P01:1911,1978 / P02:1964,2021,2099 | `self` undefined in module-level functions | 🔴 Open |
| **H-2** | 🔴 High | R04:1004–1012 | `symbol` undefined in `_calculate_order_value` | 🔴 Open |
| **H-3** | 🔴 High | I/__init__:97 | `__all__.extend` before `__all__` is defined | 🔴 Open |
| **M-1** | 🟡 Medium | X16:85,523 | `logging` and `builtins` undefined | 🟡 Open |
| **M-2** | 🟡 Medium | Q04:473 | `logging` undefined | 🟡 Open |
| **M-3** | 🟡 Medium | Q06:140 | Legacy `IB()` NameError on execution | 🟡 Open |
| **M-4** | 🟡 Medium | R02:131,205,281,50 | Legacy IBKR types + duplicate import | 🟡 Open |
| **M-5** | 🟡 Medium | ~50 files | 86 unused imports (F401) | 🟡 Open |
| **N-1** | 🔵 Notice | R02, C19 | Duplicate imports (F811) | 🔵 Open |
| **N-2** | 🔵 Notice | 6 files | UP017 `timezone.utc` → `datetime.UTC` | 🔵 Open |
| **N-3** | 🔵 Notice | 6 files | UP009 redundant UTF-8 encoding comments | 🔵 Open |
| **N-4** | 🔵 Notice | C29, J03 | UP042 `(str,Enum)` → `StrEnum` | 🔵 Open |
| **N-5** | 🔵 Notice | Various | UP037, UP043, F541, B007, E701 (1–3 each) | 🔵 Open |
| **N-6** | 🔵 Notice | ~50 files | 229 trailing-whitespace violations | 🔵 Open |
| **N-7** | 🔵 Notice | I, F, T `__init__` | Dead imports to non-existent modules | 🔵 Open |
| **N-8** | 🔵 Notice | 10 files | `print()` calls outside `__main__` | 🔵 Open |
| **N-9** | 🔵 Notice | A01:551,563 | `logging.basicConfig` in production method | 🔵 Open |
| **N-10** | 🔵 Notice | Q06 | Dead IBKR connection loop (beyond M-3) | 🔵 Open |
| **N-11** | 🔵 Notice | R02:50 | Duplicate `import logging` (subset of M-4) | 🔵 Open |
| **N-12** | 🔵 Notice | `Spyder/__init__.py` | Missing `__all__` in top-level package | 🔵 Open |
| **Opp-5** | — | ~460 files | 2,569 f-string logger calls (perf) | 🔵 Open |
| **Opp-6** | — | ~50 files | 312 auto-fixable ruff violations (batch) | 🔵 Open |
| **Opp-3** | — | `.env` | Upgrade Ollama roles to `gemma4:26b` | 🔵 RAM-gated |
| **Opp-4** | — | G05 | 18 pre-existing ruff violations | 🔵 Open |
| **OpenVINO** | Blocker | — | `optimum-intel` upstream incompatibility | ⛔ Blocked |

---

## Appendix B — Recommended Fix Order

```
Priority 1 (runtime bugs — fix before next live session):
  H-1: P01/P02 — replace self.logger with logging.getLogger(__name__)
  H-2: R04     — extract symbol from order dict
  H-3: I/init  — move __all__ = [] before first try: block

Priority 2 (medium — fix before next staging deploy):
  M-1: X16     — add import logging; fix builtins.TimeoutError
  M-2: Q04     — add import logging
  M-3: Q06     — remove or stub dead IB() connection loop
  M-4: R02     — replace Contract/Ticker/Order with Any; remove duplicate import
  M-5: all     — ruff check --select F401 --fix Spyder/

Priority 3 (batch auto-fix — one PR):
  Opp-6: ruff check --fix Spyder/  (covers N-1,2,3,5,6,11)
  N-7:   remove dead __init__ try-blocks for missing modules manually

Priority 4 (deferred):
  N-4:  StrEnum upgrade (confirm Python ≥ 3.11)
  N-8:  convert non-__main__ print() to logger calls
  N-9:  replace basicConfig fallback in A01
  N-10: remove dead Q06 IBKR loop
  Opp-5: f-string → %s logging (incremental, hot-paths first)
  Opp-3: gemma4:26b (RAM-gated)
  Opp-4: G05 cleanup
```
