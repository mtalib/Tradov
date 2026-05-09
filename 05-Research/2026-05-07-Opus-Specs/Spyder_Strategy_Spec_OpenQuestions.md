# Spyder Strategy Remediation — Open Questions

**Date:** 2026-05-07
**Relates to:** `Spyder_Strategy_Audit_Master_Plan.md` and three accompanying specs

---

## Q1 — Decision 2: Async/sync bridge — where is the event loop? (D02 + D10)

**Spec reference:** `Spyder_D02_D10_MultiLeg_Spec.md` §2.2 STEP 2, Master Plan Decision 2 Option A

The spec proposes making `generate_signals()` a thin sync wrapper that calls
`asyncio.run_coroutine_threadsafe()` against a running loop. D31 drives
`generate_signals()` from inside its `_on_market_data_event` fan-out thread,
which is not an async context.

**Two sub-questions:**

1. Is there a system-level asyncio event loop running at steady state (e.g. inside
   A02 or R02/R04)? If yes, where is the loop handle stored so D02/D10 can
   reach it at call time?

2. If no shared loop exists, `asyncio.run()` is the only alternative — but it
   blocks D31's fan-out for every other strategy while Iron Condor/Butterfly
   analysis runs. Is that acceptable, or should `analyze_iron_condor_opportunity`
   / `analyze_iron_butterfly_opportunity` be given a hard wall-clock timeout
   (e.g. 200 ms) and return `market_suitable=False` if the timeout is hit?

---

## Q2 — PMR-04: Should the F20 import block be split? (D34)

**Spec reference:** `Spyder_D34_PivotMR_Spec.md` §2.4 STEP 4

`SpyderF20_Indicators` exports `RSI` and `ATR` but **not** `VWAP` or
`VWAPSlope`. The spec imports all four symbols in a single try/except block,
so when `VWAP` is missing the entire import fails and
`_F20_INDICATORS_AVAILABLE = False` — meaning `RSI` and `ATR` never route
through F20 either.

The practical output of Step 4 in its current form would be only the
deprecation comments; no indicator would actually migrate.

**Question:** Should the import block be split into two independent try/except
guards so that `RSI` and `ATR` migrate to F20 now (Phase 1), while `VWAP` and
`VWAPSlope` remain as local implementations until F20 is extended in a
separate spec?

---

## Q3 — IC-01: Division by zero when only one strike candidate exists (D02)

**Spec reference:** `Spyder_D02_D10_MultiLeg_Spec.md` §2.4 STEP 4

The replacement scoring formula uses min-max normalisation:

```python
bid_n  = (candidates['bid']  - candidates['bid'].min())  / (candidates['bid'].max()  - candidates['bid'].min())
vol_n  = (candidates['volume'] - ...) / (...)
oi_n   = (candidates['open_interest'] - ...) / (...)
candidates['score'] = bid_n * 0.4 + vol_n * 0.3 + oi_n * 0.3
```

When only one candidate row survives the delta filter, `max - min = 0` and all
three normalised columns become `NaN` (divide-by-zero), making `score` NaN and
`idxmax()` undefined.

**Question:** What is the preferred fallback for the single-candidate case?

- **Option A:** Return the sole candidate immediately without scoring (it wins
  trivially).
- **Option B:** Fall back to the raw un-normalised formula
  (`bid * 0.4 + volume * 0.0001 * 0.3 + oi * 0.0001 * 0.3`) — same behaviour
  as the current broken implementation but only for the degenerate case.

---

## Q4 — PMR-05: Is the 90-minute reaper horizon too loose? (D34)

**Spec reference:** `Spyder_D34_PivotMR_Spec.md` §2.5 STEP 5

The proposed constant is:

```python
TRADE_STATE_REAP_HORIZON_MIN = 90   # evict OpenTradeState older than 90 min
```

The strategy's own time stop closes positions after **12 minutes** of
unprofitable holding. Under normal operation a trade state should therefore
never survive beyond ~15 minutes. A 90-minute reaper horizon means a leaked
state can persist through most of a trading session before it is evicted.

**Question:** Is there a specific reason to prefer 90 minutes over a tighter
value such as 30–40 minutes? A value of `max(TIME_STOP_MINUTES * 3, 40)` (i.e.
40 minutes with the current constants) would catch leaks much earlier while
still providing a generous buffer above the 12-minute stop.
