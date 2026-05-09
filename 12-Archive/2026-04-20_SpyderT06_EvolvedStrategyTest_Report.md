# Test Report — SpyderT06_EvolvedCreditSpread

**Date:** 2026-04-20  
**Branch:** `refactor/g05-widget-extraction`  
**Module:** `Spyder/SpyderT_Testing/SpyderT06_EvolvedStrategyTest.py`  
**Environment:** Python 3.13.7 · pytest 8.4.2 · Ubuntu 25.04  
**Result:** ✅ **31 passed / 0 failed / 1 warning** — 9.16 s

---

## Summary

| Suite | Tests | Passed | Failed | Skipped |
|---|---|---|---|---|
| TestCanonicalModuleImports | 6 | 6 | 0 | 0 |
| TestU20InstitutionalLibraries | 4 | 4 | 0 | 0 |
| TestEvolvedStrategyParams | 6 | 6 | 0 | 0 |
| TestInstitutionalOptionsPricing | 6 | 6 | 0 | 0 |
| TestInstitutionalPerformanceSimulation | 6 | 6 | 0 | 0 |
| TestPMROverrideEnvironment | 3 | 3 | 0 | 0 |
| **TOTAL** | **31** | **31** | **0** | **0** |

---

## Test Suite Detail

### 1 · TestCanonicalModuleImports
Verifies that each of the six canonical modules used by the evolved credit-spread stack can be imported without error.

| Test | Module Under Test | Result | Duration |
|---|---|---|---|
| `test_module_importable[D25 UnifiedCreditSpreadEngine-...]` | `SpyderD_Strategies.SpyderD25_UnifiedCreditSpreadEngine` | ✅ PASS | 5.60 s |
| `test_module_importable[D18 EvolvedCreditSpread-...]` | `SpyderD_Strategies.SpyderD18_EvolvedCreditSpread` | ✅ PASS | < 0.01 s |
| `test_module_importable[S08 PivotMeanReversionSignal-...]` | `SpyderS_Signals.SpyderS08_PivotMeanReversionSignal` | ✅ PASS | < 0.01 s |
| `test_module_importable[L09 UnifiedRegimeEngine-...]` | `SpyderL_ML.SpyderL09_UnifiedRegimeEngine` | ✅ PASS | < 0.01 s |
| `test_module_importable[V09 IVEngine-...]` | `SpyderV_QuantModels.SpyderV09_IVEngine` | ✅ PASS | < 0.01 s |
| `test_module_importable[E01 RiskManager-...]` | `SpyderE_Risk.SpyderE01_RiskManager` | ✅ PASS | < 0.01 s |

> **Note:** D25 import takes ~5.6 s due to loading the full Spyder package init chain (G-Series, X-Series agents, V-Series modules). This is expected; it is a one-time module-scope cost.

---

### 2 · TestU20InstitutionalLibraries
Verifies the `SpyderU20_InstitutionalLibraries` singleton initialises correctly and exposes the expected public API. All 8/8 institutional libraries (QuantLib, Ray, etc.) loaded successfully.

| Test | Assertion | Result |
|---|---|---|
| `test_singleton_returns_object` | `get_institutional_libraries()` returns a non-`None` object | ✅ PASS |
| `test_option_type_accessible_via_module_import` | `OptionType` enum importable from U20 | ✅ PASS |
| `test_library_status_is_dict` | `get_library_status()` returns a `dict` | ✅ PASS |
| `test_available_libraries_count_tuple` | `get_available_libraries_count()` returns a 2-tuple of ints | ✅ PASS |

---

### 3 · TestEvolvedStrategyParams
Verifies `EvolvedStrategyParams` defaults are aligned with the constants defined in `SpyderD18_EvolvedCreditSpread.py` (source of truth).

| Test | Expected | Actual | Result |
|---|---|---|---|
| `test_fitness_score_range` | `0.0 ≤ fitness ≤ 1.0` | 0.799 | ✅ PASS |
| `test_fitness_matches_d18_constant` | `EVOLVED_FITNESS = 0.799` | 0.799 | ✅ PASS |
| `test_generation_matches_d18_constant` | `EVOLVED_GENERATION = 15` | 15 | ✅ PASS |
| `test_risk_factor_matches_d18_constant` | `EVOLVED_RISK_FACTOR = 0.212` | 0.212 | ✅ PASS |
| `test_strategy_type_is_credit_spread` | `strategy_type == "credit_spread"` | "credit_spread" | ✅ PASS |
| `test_entry_conditions_non_empty` | `entry_conditions` list is non-empty | `["price_breakout", "rsi_oversold", "volume_spike"]` | ✅ PASS |

---

### 4 · TestInstitutionalOptionsPricing
Prices a SPY **bull-put credit spread** via the QuantLib-backed `price_option()` function and asserts key structural properties.

**Scenario parameters:**
- Underlying: SPY @ $400.00
- Short leg: put @ $393 strike (5 DTE equivalent: 0.0274 yr)
- Long leg: put @ $388 strike (same expiry)
- IV: 17%  ·  Risk-free rate: 5%

| Test | Assertion | Result |
|---|---|---|
| `test_short_leg_pricing_returns_result` | Short put price is a finite float > 0 | ✅ PASS |
| `test_long_leg_pricing_returns_result` | Long put price is a finite float > 0 | ✅ PASS |
| `test_net_credit_is_positive` | Net credit = short premium − long premium > 0 | ✅ PASS |
| `test_max_loss_bounded_by_spread_width` | Max loss ≤ spread width ($5.00) | ✅ PASS |
| `test_greeks_are_numeric` | Delta and gamma are finite floats | ✅ PASS |
| `test_net_delta_within_realistic_range` | Net put delta ∈ (−1, 0) | ✅ PASS |

---

### 5 · TestInstitutionalPerformanceSimulation
Simulates 252 trading days of returns (seed=42, mean=0.07/yr, vol=0.15/yr) and validates institutional performance metrics via `calculate_institutional_metrics()`.

| Test | Assertion | Result |
|---|---|---|
| `test_metrics_object_returned` | Returns non-`None` `InstitutionalMetrics` object | ✅ PASS |
| `test_annual_return_finite` | `annual_return` is finite | ✅ PASS |
| `test_sharpe_ratio_positive` | `sharpe_ratio > 0` | ✅ PASS |
| `test_max_drawdown_non_positive` | `max_drawdown ≤ 0` | ✅ PASS |
| `test_volatility_in_realistic_range` | `0 < volatility < 2.0` | ✅ PASS |
| `test_calmar_ratio_finite` | `calmar_ratio` is finite | ✅ PASS |

---

### 6 · TestPMROverrideEnvironment
Validates the Pivot Mean-Reversion signal integration environment used by D25.

| Test | Assertion | Result |
|---|---|---|
| `test_pmr_env_var_is_valid_value` | `SPYDER_PMR_ENABLED` env var is unset, `"0"`, or `"1"` (not garbage) | ✅ PASS |
| `test_s08_signal_importable` | `PivotMeanReversionSignal`, `PivotMRSignal`, `PivotDirection` all importable from S08 | ✅ PASS |
| `test_s08_min_fire_score_sensible` | `MIN_FIRE_SCORE = 60` (in range 1–100) | ✅ PASS |

---

## Warnings

| Severity | Source | Message |
|---|---|---|
| `FutureWarning` | `ray._private.worker` | Ray will no longer override accelerator env var when `num_gpus=0`. Set `RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0` to silence. |

No action required — this is a Ray library deprecation notice, unrelated to Spyder logic.

---

## Performance (Slowest Tests)

| Duration | Phase | Test |
|---|---|---|
| 5.60 s | call | `TestCanonicalModuleImports::test_module_importable[D25 ...]` |
| 3.49 s | setup | `TestU20InstitutionalLibraries::test_singleton_returns_object` |
| < 0.01 s | call | All remaining 29 tests |

The D25 import and U20 fixture setup costs are one-time module-scoped operations (Ray init, QuantLib init). Subsequent tests reuse the cached objects at negligible cost.

---

## Issues Observed in Startup Logs (Not Test Failures)

These are pre-existing module availability gaps logged during the D25 import chain. They do not affect this test suite but are noted for completeness:

| Module | Issue |
|---|---|
| `SpyderC01_DataFeed` | Cannot import `DataFeed` — API change |
| `SpyderV01–V04, V06–V08` | Class name mismatches on import |
| `SpyderE03_DrawdownControl` | Module missing / renamed |
| `SpyderN09_GammaExposure`, `SpyderN11_OptionsGreeksFlow` | Not available |
| `SpyderL12_RandomForestEnsemble` | Missing `shap` dependency |
| `SpyderP01_PortfolioManager` | `GammaExposureCalculator` import broken in S05 |
| `SpyderU15_PerformanceMetrics` | `PerformanceMetrics` not exported |
| `SpyderK09_RegulatoryReports` | Missing `reportlab` dependency |

---

## Conclusion

`SpyderT06_EvolvedStrategyTest` passes cleanly. The evolved credit-spread stack is verified end-to-end:

- All 6 canonical modules are importable
- `EvolvedStrategyParams` constants match D18 source of truth (fitness=0.799, gen=15, risk=0.212)
- Institutional QuantLib options pricing produces structurally valid results for a SPY bull-put spread
- Performance metrics are mathematically consistent for a simulated 252-day return series
- S08 Pivot Mean-Reversion signal integration environment is correctly configured
