# Spyder Codebase Review — v14

> **Date:** 2026-04-08
> **Reviewer:** GitHub Copilot / Claude Sonnet 4.6
> **Scope:** Fresh full-spectrum audit — security (OWASP / ruff S-rules), ghost modules,
> dashboard completeness, logging discipline, stale artefacts, and complexity analysis.
> **Prior review:** v13 (2026-04-07) — closed at 0 ruff violations. All v13 items resolved.
> **Status:** New findings identified across five categories.

---

## Executive Summary

v14 is a new-findings pass. The codebase remains at **0 base ruff violations**. The audit
this cycle used the full ruff rule-set (`S`, `PLR`, `F`, `RUF`) plus manual inspection of
security-sensitive call-sites, module registry consistency, and GUI completeness.

| Category | Count | Notes |
|----------|------:|-------|
| High — exploitable vectors | 2 | H02 SQL, C35 XML |
| Medium — design / data gaps | 4 | stale noqa, ghost module, pickle, P&L stub |
| Notice — cosmetic / minor | 7 | MD5, credentials, logging, unused import, complexity, dead branch, yfinance |
| Carry-forward from v13 | 3 | RAM-gated upgrade, CI typing, 2 TODO comments |
| Fixable with `ruff --fix` | 2 | F401 G05, RUF100 batch |
| New improvement opportunities | 7 | A–G below |

---

## Part 1 — New Findings

---

### H-1 · SQL column injection in `update_position()` — H02:551

**File:** `SpyderH_Storage/SpyderH02_DatabaseManager.py:537–555`  
**Severity:** 🟠 High  
**Rule:** S608

```python
# Current — column names from caller dict land directly in the SQL string
set_clause = ", ".join([f"{k} = ?" for k in updates])
cursor.execute(f"""
    UPDATE positions
    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
    WHERE position_id = ?
""", values)
```

**Risk:** `updates` keys are embedded in the query string without sanitisation. Because
SQLite does not support binding identifiers (only values), any caller who supplies an
unexpected key produces at minimum a malformed query; a caller accepting keys from
serialised or network input could achieve arbitrary column manipulation.

**Fix:** Whitelist column names against a frozen set of valid `positions` columns:

```python
_ALLOWED_POSITION_COLUMNS = frozenset({
    "quantity", "avg_price", "current_price", "unrealized_pnl",
    "realized_pnl", "status", "market_value", "strategy",
})

def update_position(self, position_id: int, updates: dict[str, Any]):
    invalid = set(updates) - _ALLOWED_POSITION_COLUMNS
    if invalid:
        raise ValueError(f"Column(s) not allowed in update_position: {invalid}")
    ...
```

The two other S608 hits — H01:922 and H02:780 — use `table_name` drawn from a
hardcoded `frozenset` / `TABLES.values()` with explicit allowlist checks; they
are **not actionable** (effectively already safe).

---

### H-2 · Unsafe XML parsing of external RSS feed — C35:676

**File:** `SpyderC_MarketData/SpyderC35_SentimentAnalyzer.py:676`  
**Severity:** 🟠 High  
**Rule:** S314

```python
root = ET.fromstring(response.text)   # stdlib xml — vulnerable to XXE
```

`response.text` is the raw body of a Yahoo Finance RSS HTTP response — external,
attacker-influenced content. The stdlib `xml.etree.ElementTree` parser does not
protect against XML External Entity (XXE) injection or billion-laughs DoS attacks.

**Fix:** Replace with `defusedxml`:

```python
import defusedxml.ElementTree as ET   # drop-in replacement
root = ET.fromstring(response.text)   # now XXE-safe
```

`defusedxml` is already present in `requirements-analysis.txt`. One import line
change, no other code modifications needed.

---

### M-1 · 1,206 stale `# noqa` directives (RUF100)

**Scope:** Production code across A, B, C, D, E, F, G, H, L, N, P, R, S, X, Y, Z series  
**Severity:** 🟡 Medium

```
$ ruff check Spyder/ --select RUF100 | grep -v SpyderT_Testing | wc -l
1,206
```

Stale suppressions accumulated during the v8–v11 cleanup sweeps when rule-sets changed.
They mask the true violation count and create a false sense of security — an actual new
violation could be silently suppressed by a stale `# noqa` that happens to match its code.

**Fix (mechanical):**
```bash
ruff check Spyder/ --select RUF100 --fix
```
Ruff auto-removes all stale directives. This does not change behaviour — it only removes
comments whose rule codes are no longer raised at the annotated line.

---

### M-2 · Ghost module `C26` in I12 ModuleRegistry

**File:** `SpyderI_Integration/SpyderI12_ModuleRegistry.py:151`  
**Severity:** 🟡 Medium

```python
"C26": ModuleRecord("C26", "SpyderC_MarketData",
                    "SpyderC26_DatabentooClient", "DatabentooClient", ...)
```

The file `SpyderC26_DatabentooClient.py` **does not exist** in the repository.
The C-series directory contains `SpyderC27_MassiveClient.py` and
`SpyderC29_DataProviderRouter.py` as the current Databento integration points.
Any code path that resolves the registry entry for "C26" will receive `None` or
raise `ModuleNotFoundError` at runtime.

**Fix:** Update the registry to map `C26` → `C27`/`C29`, or remove the stale entry
entirely and consolidate Databento routing through `SpyderC29_DataProviderRouter`.
Also note the filename had a typo (`Databentoo` ← extra `o`) which should be corrected
in all registry strings.

---

### M-3 · P&L Performance table not wired to live data

**File:** `SpyderG_GUI/SpyderG05_TradingDashboard.py`  
**Severity:** 🟡 Medium

`self.pnl_table = None` is set at line 1662. The table widget is created in
`create_pnl_table()` with hardcoded `QTableWidgetItem` placeholder values. No method
in the class calls `pnl_table.setItem()` after initialisation — the 4-row × 8-column
grid never updates from real trading data.

The dashboard also contains 28 calls to `random.uniform()` / `random.randint()` /
`random.gauss()` in display-facing code paths — simulated data visible to the operator
even in paper and live mode.

**Recommended path:**
1. Add a `_refresh_pnl_table(self, stats: dict)` method that maps H-series performance
   metrics (Sharpe, Calmar, win-rate, etc.) from `SpyderH07_PerformanceAnalytics` into
   the 4-period (TODAY / WEEK / MONTH / YEAR) rows.
2. Call `_refresh_pnl_table()` from the existing `_on_data_updated()` slot.
3. Audit and remove the `random.*` calls, replacing each with a `0.0` / `"—"` default
   until the real data path is wired.

---

### M-4 · 16 `pickle.load()` calls on internal model files

**Files:** A02, C02 ×2, E11, E12, F08, L08, L15, L16, M06, N02, N12, P03, P05, P06, X14  
**Severity:** 🟡 Medium  
**Rule:** S301

All 16 calls read files written by the same system (ML model checkpoints, state caches,
IV history). The immediate threat is low — these are not deserialising untrusted network
data. However, if a checkpoint file were replaced by a malicious actor with filesystem
access, arbitrary code could execute on load.

**Mitigation options (in order of preference):**
1. **Short-term**: Verify the checkpoint path is inside a controlled directory before
   loading (a `Path.resolve()` check against `models/` or `data/`).
2. **Medium-term**: Migrate ML model serialisation to `joblib.dump/load` (scikit-learn
   convention, equally fast, same threat model but widely adopted and auditable).
3. **Long-term**: Add file-integrity hashing (SHA-256, not MD5) on save; verify before
   load.

---

### N-1 · 17 MD5 hash calls without `usedforsecurity=False` (S324)

**Files:** C09, C17, C18, C24, E19 ×4, F11 ×2, S06, U11, X03, X04, X05, X13, Z05  
**Severity:** 🔵 Notice

All confirmed to be **non-cryptographic** — cache-key generation, experiment IDs,
config checksums. None compute security-related digests. The ruff `S324` flag fires
because `hashlib.md5()` defaults to cryptographic mode.

**Fix (one second per file):**
```python
# Before
hashlib.md5(key_str.encode()).hexdigest()

# After
hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()
```
Python 3.9+ added the `usedforsecurity` parameter specifically for this pattern.
Adding it at all 17 sites silences S324 without changing behaviour.

---

### N-2 · Hardcoded placeholder credentials in example blocks (S105)

**Files:**
- `SpyderJ_Alerts/SpyderJ02_EmailNotifier.py:786` — `password='encrypted_password'`
- `SpyderJ_Alerts/SpyderJ05_TelegramBot.py:958` — `BOT_TOKEN = "YOUR_BOT_TOKEN"`
- `SpyderQ_Scripts/SpyderQ03_ValidateConfiguration.py:343` — validator test value
- `SpyderF_Analysis/SpyderF09_EntryFilters.py:47` — feature-flag default (false positive)  
**Severity:** 🔵 Notice

All occurrences are inside `if __name__ == "__main__"` demo blocks or validator
test fixtures. None appear in live-path code. Risk is **informational only**.

**Fix:** Add a `# noqa: S105` annotation on each line (3 genuine hits + 1 false positive),
or restructure the example blocks to read from `os.environ` to model best practice for
any human reader working from these examples.

---

### N-3 · ~12 production files use raw `logging.getLogger()` instead of `SpyderLogger`

**Files (selection):** M05, M06, M08, P01, P02, P04, Y05  
**Severity:** 🔵 Notice

The project standard (`SpyderU01_Logger.py`) requires `SpyderLogger.get_logger(__name__)`.
These files use the stdlib `logging.getLogger(__name__)` directly, bypassing the
structured formatter, rotating-file handler, and the GUI log console integration.

Q-scripts are an accepted exception (standalone CLI tools). M/P/Y-series production
modules are not.

**Fix:** Replace bare `logging.getLogger(...)` with:
```python
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
self.logger = SpyderLogger.get_logger(__name__)
```

---

### N-4 · Unused import `QComboBox` in G05 (F401)

**File:** `SpyderG_GUI/SpyderG05_TradingDashboard.py:92`  
**Severity:** 🔵 Notice

```python
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,   # ← imported but never referenced
    ...
)
```

**Fix:** Remove `QComboBox` from the import list —
`ruff check --fix --select F401` will do this automatically.

---

### N-5 · 149 functions exceed complexity thresholds (PLR0912/PLR0915/PLR0911)

**Scope:** All series — predominantly D, E, A, B, C  
**Severity:** 🔵 Notice

```
PLR0912 (too many branches)  →  ~85 functions
PLR0915 (too many statements) → ~45 functions
PLR0911 (too many returns)    → 85 functions
```

These are not bugs but they indicate functions that are hard to test and maintain.
The worst offenders are the strategy `generate_signal` / `calculate_entry_price`
methods in the D-series and the `_handle_event` dispatch functions in A02/A06.

**Recommended approach:** Extract sub-handlers and early-return guards rather than
large if/elif trees. Prioritise when adding new unit tests to a function.

---

### N-6 · N10 dead-branch import of deleted `SpyderC07_OPRAFeed`

**File:** `SpyderN_OptionsAnalytics/SpyderN10_OptionsFlowAnalyzer.py:43–47`  
**Severity:** 🔵 Notice

```python
try:
    from Spyder.SpyderC_MarketData.SpyderC07_OPRAFeed import OPRAFeedHandler
    _OPRA_AVAILABLE = True
except ImportError:
    OPRAFeedHandler = None
    _OPRA_AVAILABLE = False
```

`SpyderC07_OPRAFeed.py` was removed from the repository. The try/except branch
means this never raises at runtime — `_OPRA_AVAILABLE` is always `False`. The
dead `True` branch, and all code paths gated on `_OPRA_AVAILABLE`, are unreachable.

**Fix:** Remove the try/except block, set `_OPRA_AVAILABLE = False` unconditionally,
and audit N10 for any dead `if _OPRA_AVAILABLE:` branches that can be deleted.

---

### N-7 · yfinance used in 6 production modules — not migrated to Databento

**Files:** `S01_DIXCalculator`, `S03_BlackSwanIndicator`, `S06_SKEWCalculator`,
           `S08_ShortSqueezeDetector`, `C10_VIXAnalyzer`, `C22_FactorDataProvider`  
**Severity:** 🔵 Notice

The system is mid-migration from Polygon.io/yfinance → Databento. Six S-series and
C-series modules still use `yfinance` as a primary or fallback data source. This
creates an undeclared dependency on a third-party library outside the approved
provider set, and risks unexpected data when `yfinance`'s unofficial API changes.

**Recommended path:**
- Route VIX, factor, and options-chain data through `SpyderC29_DataProviderRouter`
  which already abstracts provider selection.
- `yfinance` can remain as a last-resort fallback with explicit logging when used.

---

## Part 2 — Carry-Forward from v13

### Opp-3 (v13) · Upgrade Ollama roles to `gemma4:26b`

**Status:** 🔵 Deferred — RAM-gated. Apply when hardware supports the larger context model.

---

### Opp-C (v13) · Enforce static typing in CI

**Status:** 🔵 Deferred. Add `pyright --project .` or `mypy --strict` to the CI pipeline.
Annotations are already high quality; a `pyrightconfig.json` would have caught the
C-1 wrong-object assignment from v12 automatically.

---

### N-2 (v13) · Two surviving TODO comments

**Status:** 🔵 Notice — no broken behaviour. Still open.

| File | Line | Comment |
|------|-----:|---------|
| `SpyderF_Analysis/SpyderF09_EntryFilters.py` | 913 | `TODO: Integrate portfolio-level Greek correlation when position data available.` |
| `SpyderB_Broker/SpyderB30_SPYOptionsChainManager.py` | 879 | `# TODO: Reinitialize with new expiration` |

---

## Part 3 — New Improvement Opportunities

### Opp-A · One-liner MD5 suppression — 17 files (< 2 min)

Add `usedforsecurity=False` at all 17 `hashlib.md5(...)` call-sites to clear S324
across the board. Each change is a single keyword argument — no logic change.

---

### Opp-B · `defusedxml` in C35 — 2 lines (< 5 min) — **addresses H-2**

```python
# SpyderC35_SentimentAnalyzer.py
- import xml.etree.ElementTree as ET
+ import defusedxml.ElementTree as ET
```
`defusedxml` is already in `requirements-analysis.txt`. No other changes required.

---

### Opp-C · Column-name allowlist in H02 `update_position()` — **addresses H-1**

Add a `_ALLOWED_POSITION_COLUMNS` frozenset and a validation block at the top of
`update_position()`. Prevents unexpected column names from entering the SQL string.
Estimated effort: ~10 lines.

---

### Opp-D · Batch-clear 1,206 stale `# noqa` directives — **addresses M-1**

```bash
ruff check Spyder/ --select RUF100 --fix
```
Fully automated. Commit the result. Zero behavioural change.

---

### Opp-E · Wire P&L Performance table to real data — **addresses M-3**

Add `_refresh_pnl_table(stats: dict)` reading from `SpyderH07_PerformanceAnalytics`
and call it from `_on_data_updated()`. Medium effort — requires defining the 4-period
aggregation logic (TODAY/WEEK/MONTH/YEAR stats windows) against the trade history table.

---

### Opp-F · Fix I12 ghost `C26` registry entry — **addresses M-2**

Update `SpyderI12_ModuleRegistry.py` line 151 to reference `SpyderC29_DataProviderRouter`
(or `SpyderC27_MassiveClient`) and fix the `Databentoo` typo in the class name string.

---

### Opp-G · Clean N10 dead OPRA branch — **addresses N-6**

Remove the try/except import block in N10 and audit for any `if _OPRA_AVAILABLE:`
branches inside the file that can be deleted, simplifying the flow analyser.

---

## Appendix A — Complete Finding Register

| ID | Sev | Description | Status |
|----|-----|-------------|--------|
| **H-1** | 🟠 | `update_position()` in H02 builds SQL SET clause from raw dict keys | 🆕 Open |
| **H-2** | 🟠 | `ET.fromstring(response.text)` parses external Yahoo RSS — XXE risk (C35) | 🆕 Open |
| **M-1** | 🟡 | 1,206 stale `# noqa: RUF100` directives in production code | 🆕 Open |
| **M-2** | 🟡 | Ghost `C26` registry entry (file deleted; `Databentoo` typo) | 🆕 Open |
| **M-3** | 🟡 | P&L Performance table — hardcoded placeholder data, never refreshed | 🆕 Open |
| **M-4** | 🟡 | 16 `pickle.load()` calls on model/state files | 🆕 Open |
| **N-1** | 🔵 | 17 `hashlib.md5()` without `usedforsecurity=False` | 🆕 Open |
| **N-2** | 🔵 | Placeholder credentials in 3 `if __name__` example blocks | 🆕 Open |
| **N-3** | 🔵 | ~12 production files using `logging.getLogger()` instead of `SpyderLogger` | 🆕 Open |
| **N-4** | 🔵 | Unused `QComboBox` import in G05:92 | 🆕 Open |
| **N-5** | 🔵 | 149 functions over PLR complexity thresholds | 🆕 Open |
| **N-6** | 🔵 | N10 imports deleted C07_OPRAFeed (graceful fail) — dead branch | 🆕 Open |
| **N-7** | 🔵 | yfinance used in 6 production modules (not yet Databento-migrated) | 🆕 Open |
| **Opp-3** (v13) | ⬜ | Upgrade Ollama roles to `gemma4:26b` | 🔵 RAM-gated |
| **Opp-C** (v13) | ⬜ | Add `pyright`/`mypy --strict` to CI pipeline | 🔵 Deferred |
| **N-2** (v13) | 🔵 | 2 surviving TODO comments (F09:913, B30:879) | 🔵 Notice |

---

## Appendix B — Priority Order

```
Immediate (security, low effort):
  H-2:   import defusedxml in C35 — 2 lines
  H-1:   add column allowlist to H02 update_position() — ~10 lines
  N-4:   remove unused QComboBox import in G05 — ruff --fix

Short-term (quality, automated):
  Opp-D: ruff check --select RUF100 --fix  →  clears M-1 (1,206 stale directives)
  N-1:   add usedforsecurity=False to 17 MD5 calls  →  clears N-1

Medium-term (data / integration):
  M-2:   fix I12 ghost C26 registry entry
  N-6:   clean dead OPRA branch in N10
  N-3:   migrate ~12 files to SpyderLogger.get_logger()
  N-2:   add # noqa: S105 to 3 example credential lines

Longer-term (feature / architecture):
  M-3:   wire P&L Performance table to real H07 analytics data
  M-4:   migrate ML checkpoints from pickle to joblib
  N-7:   route yfinance modules through C29 DataProviderRouter
  N-5:   refactor highest-complexity strategy functions

Deferred (carry-forward):
  Opp-3: gemma4:26b when RAM available
  Opp-C: add pyright/mypy to CI
  N-2 v13: implement F09 Greek-correlation TODO, B30 expiration reinit TODO
```
