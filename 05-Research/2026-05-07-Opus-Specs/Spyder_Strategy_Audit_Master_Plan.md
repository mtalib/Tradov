# Tradov Strategy Modules — Master Plan

**Scope:** Audit and remediation of five strategy modules in the `TradovD_Strategies` series.
**Date:** 2026-05-07
**Owner:** Adam (Tradov)
**Implementation agent:** Claude Opus 4.6 in VS Code

---

## Modules in scope

| Module | Strategy | Audit grade | Severity |
|---|---|---|---|
| `TradovD02_IronCondor.py` | Iron Condor | C | High (architectural + correctness) |
| `TradovD10_IronButterfly.py` | Iron Butterfly | C | High (architectural + correctness) |
| `TradovD06_BullPutSpread.py` | Bull Put Spread | B− | Medium (small bugs, doc drift) |
| `TradovD07_BearCallSpread.py` | Bear Call Spread | B− | Medium (small bugs, doc drift) |
| `TradovD34_PivotMeanReversion.py` | Intraday Pivot MR | B+ | Low–Medium (perf + edge cases) |

---

## Spec deliverables

Three implementation specs accompany this master plan:

1. **`Tradov_D02_D10_MultiLeg_Spec.md`** — Iron Condor + Iron Butterfly (paired; they share the same architectural defects).
2. **`Tradov_D06_D07_VerticalSpread_Spec.md`** — Bull Put + Bear Call (paired; they are mirror images).
3. **`Tradov_D34_PivotMR_Spec.md`** — Pivot Mean Reversion (standalone).

Each spec is self-contained: it lists every change, gives exact find/replace patterns or new code blocks, and ends with an acceptance checklist.

---

## Execution order (recommended)

Execute in this order to minimise rework risk:

1. **D02 + D10 together** (highest impact, shared architecture).
   These two have a contract violation (`generate_signals → []` unconditionally) and a documentation drift (`D26` vs `D32`) that should be resolved with the same decision. Doing them together avoids reverting one to match the other.

2. **D34** (isolated correctness fixes).
   No cross-module impact. Performance fix (RSI O(n²) → O(1)), VWAP NaN guard, indicator consolidation onto F20.

3. **D06 + D07 together** (small, mirror changes).
   Lowest risk; do last to confirm the credit-spread parent (`TradovD03_CreditSpread`) is stable after any D02/D10 touch.

---

## Cross-cutting decisions required *before* execution

The implementation agent must confirm these answers with the user **before** starting D02/D10. They affect every module to varying degrees.

### Decision 1 — Coordinator module name

The header docstrings of D02 and D10 say `D26_MultiLegStrategyCoordinator`, but the `import` statements reference `TradovD32_MultiLegStrategyCoordinator`. Pick one:

- **Option A (assumed correct):** The actual file is `TradovD32_MultiLegStrategyCoordinator.py`. Update docstrings everywhere to say `D32`.
- **Option B:** The intended file is `TradovD26_MultiLegStrategyCoordinator.py` and the imports are wrong.

The specs default to **Option A** and assume `D32` is the canonical name. If Option B is correct, swap `D32 → D26` in all references.

### Decision 2 — How does the engine call multi-leg strategies?

Currently `D02.generate_signals()` and `D10.generate_signals()` return `[]` unconditionally because entry runs through async `analyze_iron_condor_opportunity()` / `analyze_iron_butterfly_opportunity()`. Pick one:

- **Option A (recommended):** Make `generate_signals()` a thin sync wrapper that runs the async analysis via `asyncio.run_coroutine_threadsafe()` against the running loop, builds a `TradingSignal` from the analysis result, and returns it. This restores the `BaseStrategy` contract.
- **Option B:** Document explicitly that `generate_signals()` is intentionally a no-op for multi-leg strategies, and that the orchestrator (`D31`/`D32`) drives them via the async API directly. Add a class-level marker (e.g., `IS_MULTILEG_ASYNC = True`) so the engine skips the sync hook.

The specs default to **Option A** because it preserves uniform engine behaviour. Option B is acceptable if the orchestrator is already structured that way.

### Decision 3 — Synthetic-IV fallback policy

Both D02 and D10 currently fall back to `pd.Series([0.20])` and `pd.Series([0.20] * 100)` when the `iv` column is missing. This is a P0 silent-data-fabrication bug. The fix is non-controversial but the user must confirm the policy:

- **Recommended policy:** When `iv` is missing or NaN, the analysis methods return an `IronCondorAnalysis`/`IronButterflyAnalysis` with `market_suitable=False` and `risk_warnings=["IV data unavailable — analysis skipped"]`. No defaults, no synthesis.

The specs assume this policy.

---

## Verification protocol (applies to every module)

After each module is implemented:

1. `python -m py_compile <module>.py` must pass.
2. `ruff check <module>.py` must report no new errors.
3. `mypy <module>.py --ignore-missing-imports` must pass for the changed surface.
4. The module's `if __name__ == "__main__":` block must execute without exception.
5. Any unit tests under `Tradov/TradovT_Testing/` that target the module must pass.

---

## Out of scope

These items are surfaced by the audit but deferred:

- Full type-unification work (`MarketRegime` etc.) — handled by separate plan.
- Exception handler audit (~3000 bare `except`) — handled by separate plan.
- `TradovD03_CreditSpread` modifications — D06/D07 spec only touches the children. If parent changes are needed for delta-tightening, that becomes a separate D03 spec.
- `TradovS08_PivotMeanReversionSignal` modifications — D34 spec assumes S08 is correct as-is.
- New strategy backtesting — orthogonal to remediation.
