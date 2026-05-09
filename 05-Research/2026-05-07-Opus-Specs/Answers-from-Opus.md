A1 — Drop the bridge entirely; make analysis methods sync
I over-engineered this. Looking back at analyze_iron_condor_opportunity and analyze_iron_butterfly_opportunity, neither method awaits anything. Every helper they call (_analyze_iv_for_iron_condor, _calculate_volatility_skew, _analyze_trend_for_iron_condor, etc.) is sync. The async keyword on those analysis methods is decorative — there's no actual concurrency happening.
The clean fix is therefore: drop async from the analysis methods, not bridge to them. Reserve async for the methods that genuinely await (create_iron_condor_position, create_iron_butterfly_position, which await coordinator calls — those stay async because they're driven by the orchestrator on a separate path, not by generate_signals).
Revised STEP 2 for D02:
Change analyze_iron_condor_opportunity from async def to def. Then generate_signals becomes:
pythondef generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
    """Sync entry point for the BaseStrategy contract."""
    try:
        if market_data is None or market_data.empty:
            return []

        analysis = self.analyze_iron_condor_opportunity(market_data, option_chain=None)
        if analysis is None or not analysis.market_suitable:
            return []

        signal = self._build_signal_from_analysis(analysis, market_data)
        return [signal] if signal is not None else []

    except Exception as e:
        self.logger.error("IronCondor.generate_signals failed: %s", e, exc_info=True)
        return []
_run_analysis_sync is no longer needed — delete it from the spec. _build_signal_from_analysis stays as written.
D10 gets the same treatment: analyze_iron_butterfly_opportunity becomes def, no bridge, no timeout.
Side benefits:

D31's fan-out thread is never blocked on an event loop it doesn't own.
No timeout dance, no asyncio.run cost (~5–10 ms per call), no thread-safety questions about the loop handle.
The remaining async methods (create_iron_*_position) keep their orchestrator-driven contract intact.

One thing to verify before making the change: confirm no other call site in the codebase awaits analyze_iron_condor_opportunity or analyze_iron_butterfly_opportunity. If something does (e.g. a test, or D31/D32 reaching in), that call site needs to drop the await. Quick check: grep -rn "await.*analyze_iron_\(condor\|butterfly\)_opportunity" across the repo. If nothing matches, the change is safe.

A2 — Yes, split the import block
You're right — the spec as written produces no actual migration when VWAP is missing from F20. Split it.
Revised STEP 4 for D34, replace the F20 import additions with:
pythonfrom Spyder.SpyderF_Analysis.SpyderF20_Indicators import ADX as _f20_adx

# Prefer F20 for shared indicators when available. Each indicator is
# guarded independently so a missing symbol doesn't disable the others.
try:
    from Spyder.SpyderF_Analysis.SpyderF20_Indicators import RSI as _f20_rsi  # noqa: F401
    _F20_RSI_AVAILABLE = True
except ImportError:
    _F20_RSI_AVAILABLE = False

try:
    from Spyder.SpyderF_Analysis.SpyderF20_Indicators import ATR as _f20_atr  # noqa: F401
    _F20_ATR_AVAILABLE = True
except ImportError:
    _F20_ATR_AVAILABLE = False

# VWAP / VWAPSlope are not yet exposed by F20; tracked under a separate
# F20-extension spec. The local implementations remain primary for now.
_F20_VWAP_AVAILABLE = False
Drop the combined _F20_INDICATORS_AVAILABLE flag from any acceptance criteria — replace with the three independent flags.
For RSI specifically, since the rolling cache in _refresh_bar_buffer is the hot path (called every bar), you can route it through F20 conditionally:
pythonif self._bar_buffer:
    closes_arr = np.array([b.close for b in self._bar_buffer], dtype=float)
    if _F20_RSI_AVAILABLE:
        # F20 RSI is expected to return a full series aligned 1:1 with input.
        # Verify shape parity in a one-off test before relying on this path.
        self._rsi_series = np.asarray(_f20_rsi(closes_arr, timeperiod=14), dtype=float)
    else:
        self._rsi_series = _rolling_rsi(closes_arr, period=14)
else:
    self._rsi_series = np.array([], dtype=float)
ATR is currently only computed once per bar in generate_signals, so the F20 routing for ATR can be a straightforward conditional substitution at that call site. Verify F20's RSI returns Wilder smoothing (matching _compute_rsi's scalar implementation) before flipping the switch — if F20 uses simple-MA RSI, the values will diverge ~5–10 points during regime changes and you'll want _rolling_rsi to remain primary.

A3 — Option A; and noting my spec used divide-by-max, not min-max
A clarification first: my spec used divide-by-max (values / vmax with a vmax <= 0.0 guard), not min-max. With divide-by-max and a single candidate, the result is 1.0 / 1.0 = 1.0 for that row — no NaN. So the original spec didn't have the bug you're describing.
That said: min-max normalisation is the better choice because it gives full discrimination across the candidate range (a candidate with bid = 0.30 and one with bid = 0.31 should produce noticeably different scores; divide-by-max squashes them to 0.97 and 1.00). If you've upgraded to min-max, keep it — and Option A is the right answer for the single-candidate case.
Revised _norm for both single-candidate and uniform-value edge cases:
pythondef _norm(col: str) -> pd.Series:
    if col not in candidates.columns:
        return pd.Series(0.0, index=candidates.index)
    values = candidates[col].astype(float).fillna(0.0)
    vmin = float(values.min())
    vmax = float(values.max())
    if vmax - vmin <= 0.0:
        # All candidates tied on this dimension — neutral contribution.
        return pd.Series(0.5, index=candidates.index)
    return (values - vmin) / (vmax - vmin)
And add a single-candidate short-circuit at the top of _select_best_short_strike:
pythonif candidates.empty:
    return None
if len(candidates) == 1:
    return float(candidates.iloc[0]['strike'])

candidates = candidates.copy()
# ... normalisation block follows ...
Returning 0.5 for tied dimensions (rather than 0.0) preserves a meaningful score — otherwise a candidate that's tied on every dimension would score 0 across the board and be indistinguishable from a candidate that's worst on every dimension.

A4 — Tighten to 40 minutes; the agent's reasoning is correct
The 90-minute number was conservative without justification. Your suggested formula is better.
Revised constant:
python# A leaked OpenTradeState should be evicted well after the time-stop
# expires but before it can persist into the next session segment.
# With TIME_STOP_MINUTES = 12, this gives 36-minute-floor 40-minute reap,
# i.e. ~3× the worst-case unprofitable hold.
TRADE_STATE_REAP_HORIZON_MIN = max(TIME_STOP_MINUTES * 3, 40)
One caveat the agent should know about before tightening: a profitable position can legitimately hold longer than the 12-minute stop, because the time stop only fires when the position is unprofitable. A profitable PMR position waits for a VWAP cross, which on a slow drift day could take 30+ minutes. With TIME_STOP_MINUTES * 3 = 36, that's tight but still fine — a profitable position lingering past 36 minutes is itself a signal something has gone wrong with the exit-monitor pipeline, and a warning log is appropriate.
If you want a wider safety margin to cover legitimate slow-VWAP-cross scenarios, bump the multiplier to 4× (= 48 minutes) or set the floor to 60. Either is defensible. I'd lean toward 40 because (a) PMR is explicitly designed for fast reversion in the 10:15–14:00 window, and (b) every reaper eviction generates a warning log, which is the point — operators want to know about exit-callback failures sooner rather than later.

Recap of spec changes from these answers
The agent should treat these as binding amendments to the original specs:

D02 + D10 spec, §2.2: Drop the _run_analysis_sync helper; make analyze_iron_*_opportunity sync methods (remove async); generate_signals calls them directly. Verify no await analyze_iron_*_opportunity exists elsewhere first.
D02 + D10 spec, §2.4: Add single-candidate short-circuit; if using min-max normalisation, return 0.5 (not 0.0) when vmax - vmin == 0.
D34 spec, §2.4: Split the F20 import into per-symbol guards with _F20_RSI_AVAILABLE / _F20_ATR_AVAILABLE / _F20_VWAP_AVAILABLE flags.
D34 spec, §2.5: Change reaper horizon to max(TIME_STOP_MINUTES * 3, 40).
