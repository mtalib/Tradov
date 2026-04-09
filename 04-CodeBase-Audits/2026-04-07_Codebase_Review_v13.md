# Spyder Codebase Review — v13

> **Date:** 2026-04-07
> **Reviewer:** Claude Sonnet 4.6
> **Scope:** Full implementation pass — all v12 findings resolved, plus pre-existing ruff
> violations in 5 working-directory files cleared.
> **Prior reviews:** v12 (2026-04-07) identified 9 new findings.
> **Status:** `ruff check Spyder/` → **0 violations** (471 files). All actionable v12 items
> closed. Three items remain open by design (deferred/hardware-gated).

---

## Executive Summary

v13 is a pure remediation pass — no new anomalies were found. Every correctable finding from
v12 was fixed in a single session. The codebase is now clean on all axes covered by v11–v13:
lint, runtime-correctness, thread-safety, logging discipline, and provider-routing
consistency.

| Category | v12 Count | v13 Count | Delta |
|----------|----------:|----------:|------:|
| Critical — runtime wrong-object | 1 | **0** | −1 fixed |
| High — code bugs / logging | 3 | **0** | −3 fixed |
| Medium — design gaps | 3 | **0** | −3 fixed |
| Notice — stale artefacts | 2 | **0** | −2 fixed |
| Pre-existing ruff violations (5 files) | 37 | **0** | −37 fixed |
| Opportunities — deferred | 3 | 3 | unchanged |
| Opp-3 (prior — RAM-gated) | 1 | 1 | unchanged |

---

## Part 1 — Fixed in This Session

### C-1 · Wrong object assigned to `suite["iv_engine"]`

**File:** `SpyderV_QuantModels/__init__.py:317`

Replaced `SpyderAIModels` (the AI-models class) with the correct IV-engine instances:

```python
# Before:
suite["iv_engine"] = SpyderAIModels  # IV engine is a module, not a singleton class

# After:
suite["iv_engine"] = BlackScholesCalculator()
suite["greeks_calculator"] = GreeksCalculator()
suite["volatility_analyzer"] = VolatilityAnalyzer()
```

---

### H-1 · Indentation bug — dashboard log-level never set on normal startup path

**File:** `SpyderA_Core/SpyderA01_Main.py:518–520`

Dedented the `logging.getLogger("SpyderG_GUI.SpyderG05_TradingDashboard").setLevel(logging.INFO)`
call by one level so it executes unconditionally, outside the `else:` fallback branch.

---

### H-2 · `logging.basicConfig()` in `_setup_logging()` instance method

**File:** `SpyderA_Core/SpyderA01_Main.py:512,524`

Replaced both `logging.basicConfig()` calls with a package-scoped `StreamHandler` attached
only to `logging.getLogger("Spyder")`, leaving the root logger untouched:

```python
# Fallback path — was: logging.basicConfig(...)
_spyder_root = logging.getLogger("Spyder")
if not _spyder_root.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    _spyder_root.addHandler(_handler)
_spyder_root.setLevel(self.config.log_level)

# Exception handler — was: logging.basicConfig(level=logging.WARNING)
_spyder_root = logging.getLogger("Spyder")
if not _spyder_root.handlers:
    _spyder_root.addHandler(logging.StreamHandler())
```

---

### H-3 · `logging.basicConfig()` at module level in test file

**File:** `SpyderT_Testing/SpyderT14_RiskSuiteIntegrationTest.py:61–64`

Removed the four-line `logging.basicConfig(...)` block entirely; left only
`logger = logging.getLogger(__name__)`.

---

### M-1 + Opp-B + N-1 · Stale Polygon and Databento references (10 files)

Removed all references to the two retired data providers across:

| File | Change |
|------|--------|
| `SpyderC29_DataProviderRouter.py` | Removed `POLYGON` from `DataProvider` enum; updated docstring and `from_env()` |
| `SpyderQ02_ValidateEnv.py` | Updated header to "Tradier + Massive"; fixed validation to `"massive"` only; updated changelog |
| `.env.example` | Removed entire `DATABENTO CONFIGURATION` block (8 env-vars); set `DATA_PROVIDER=massive`; updated setup checklist |
| `SpyderC_MarketData/__init__.py` | Header and `__description__` updated to "Massive" |
| `SpyderC00_MarketDataProtocol.py` | "formerly Polygon.io" removed |
| `SpyderC01_DataFeed.py` | "Polygon.io) WebSocket" → "Massive WebSocket" |
| `SpyderE13_DayProfitTarget.py` | "Massive/Polygon.io" → "Massive" |
| `SpyderG05_TradingDashboard.py` | Three "Polygon.io" references removed (lines 13, 39, 124) |
| `SpyderT_Testing/conftest.py` | "Set Massive (Polygon.io) environment variables" → "Set Massive environment variables" |
| `SpyderC29_DataProviderRouter.py` | Module docstring `polygon` line removed |

---

### M-2 + Opp-A · 14 thread-unsafe singleton factories

Added double-checked locking to all 14 module-level singletons that lacked it. Pattern
applied uniformly:

```python
_instance = None
_instance_lock = threading.Lock()   # added

def get_instance():
    global _instance
    if _instance is None:
        with _instance_lock:           # added
            if _instance is None:      # added (double-checked)
                _instance = HeavyObject()
    return _instance
```

`import threading` added where not already present (11 of the 14 files).

**Files fixed (14 total):**

| Package | File |
|---------|------|
| SpyderF_Analysis | `SpyderF16_RealTimeAnalytics.py` |
| SpyderS_Signals | `SpyderS01_DIXCalculator.py` |
| SpyderS_Signals | `SpyderS03_BlackSwanIndicator.py` |
| SpyderU_Utilities | `SpyderU20_InstitutionalLibraries.py` |
| SpyderL_ML | `SpyderL17_FederatedLearning.py` |
| SpyderX_Agents | `SpyderX02_FlowAgent.py` |
| SpyderX_Agents | `SpyderX04_RiskGuardianAgent.py` |
| SpyderX_Agents | `SpyderX07_ExecutionStrategyAgent.py` |
| SpyderX_Agents | `SpyderX09_AlertManagerAgent.py` |
| SpyderX_Agents | `SpyderX10_QuantModelsAgent.py` |
| SpyderX_Agents | `SpyderX12_SystemHealthAgent.py` |
| SpyderX_Agents | `SpyderX13_MarketAnalysisAgent.py` |
| SpyderC_MarketData | `SpyderC15_MicrostructureAnalyzer.py` |
| SpyderC_MarketData | `SpyderC24_ModelDataPipeline.py` |

---

### M-3 · `except BaseException: pass` in `SpyderU_Utilities/__init__.py`

**File:** `SpyderU_Utilities/__init__.py:283`

`except BaseException:` → `except Exception:`. The body (a pure dict-lookup) cannot raise
`SystemExit` or `KeyboardInterrupt`; the broad catch was unnecessary.

---

### Bonus · Pre-existing syntax error in `SpyderE13_DayProfitTarget.py`

**File:** `SpyderE_Risk/SpyderE13_DayProfitTarget.py:2094`

An unclosed parenthesis in `setStyleSheet("color: green; font-weight: normal;"` (missing
closing `)`) had been introduced by prior uncommitted work. Fixed as part of this session.

---

### Pre-existing ruff violations in 5 working-directory files (37 → 0)

These violations pre-dated this session. Fixed in a separate sub-pass:

| File | Violations | Fix |
|------|----------:|-----|
| `SpyderQ96_CollectFinetuneData.py` | 4 | Auto-fix: removed UTF-8 comment, unused `os`, `datetime`, `TradeType` imports |
| `SpyderQ98_FinetuneGemma4Spyder.py` | 2 | Auto-fix: removed UTF-8 comment; manual: removed unused `TrainingArguments` from deferred import |
| `SpyderQ99_ApplyPythonFormatting.py` | 8 | Auto-fix: removed UTF-8 comment, `os` import; modernised `Optional`/`Tuple`/`List` type annotations |
| `SpyderT44_DatabentoClient_Test.py` | 11 | Manual: removed 3 dead Databento-era test classes (`TestParseOpraTicker`, `TestOptionContract`, `TestDownloadState`) referencing symbols from the removed `SpyderC26_DatabentoClient` |
| `test_sharpe_comparison.py` | 12 | Auto-fix: removed 9 empty `f`-string prefixes; removed UTF-8 comment, `os` import, deprecated `List` annotation |

---

## Part 2 — Deferred (Unchanged from v12)

### Opp-3 · Upgrade Ollama roles to `gemma4:26b`

**Status:** 🔵 Deferred — RAM-gated. Apply when hardware supports the larger model.

---

### Opp-C · Enforce static typing in CI

**Status:** 🔵 Deferred. Add `pyright --project .` or `mypy --strict` to the CI pipeline.
The existing annotations are high quality; a `pyrightconfig.json` would catch wrong-object
assignments (like the former C-1) automatically.

---

### N-2 · Two surviving TODO comments

**Status:** 🔵 Notice — no broken behaviour.

| File | Line | Comment |
|------|-----:|---------|
| `SpyderF_Analysis/SpyderF09_EntryFilters.py` | 913 | `TODO: Integrate portfolio-level Greek correlation when position data available.` |
| `SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py` | 879 | `# TODO: Reinitialize with new expiration` |

---

## Appendix A — Full Resolution Record

| ID | Sev | Description | Status |
|----|-----|-------------|--------|
| **C-1** | 🔴 | Wrong object (`SpyderAIModels`) assigned to `suite["iv_engine"]` in V/__init__ | ✅ Fixed |
| **H-1** | 🟠 | `setLevel` indented inside `else:` — never ran on normal startup path | ✅ Fixed |
| **H-2** | 🟠 | `logging.basicConfig()` in `_setup_logging()` instance method (A01) | ✅ Fixed |
| **H-3** | 🟠 | `logging.basicConfig()` at module level in T14 test file | ✅ Fixed |
| **M-1** | 🟡 | Stale `POLYGON` enum member + Databento config in C29, Q02, and `.env.example` | ✅ Fixed |
| **M-2** | 🟡 | 14 thread-unsafe singleton factories missing double-checked locking | ✅ Fixed |
| **M-3** | 🟡 | `except BaseException: pass` in `U/__init__.py` — overly broad catch | ✅ Fixed |
| **N-1** | 🔵 | Q02 changelog/header references removed Databento provider | ✅ Fixed (covered by M-1) |
| **N-2** | 🔵 | 2 surviving TODO comments (F09, B30) | 🔵 Notice — left open |
| **Bonus** | 🟠 | Pre-existing unclosed `)` syntax error in E13:2094 | ✅ Fixed |
| **Pre-existing** | 🟡 | 37 ruff violations in Q96, Q98, Q99, T44, test_sharpe | ✅ Fixed |
| **Opp-3** | ⬜ | Upgrade Ollama roles to `gemma4:26b` | 🔵 RAM-gated |
| **Opp-C** | ⬜ | Add `pyright`/`mypy --strict` to CI pipeline | 🔵 Deferred |

---

## Appendix B — Next Actions

```
When ready (no urgency):
  Opp-3:  Bump Ollama model config once RAM is available
  Opp-C:  Add pyright to CI (one-time setup; catches type bugs automatically)
  N-2:    Resolve the two TODO comments when the related features are implemented
```
