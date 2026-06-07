# 2026-06-02 Mark ZeroHFT Strategy

This note compares Mark's 0DTE SPX options approach with Spyder's ZeroHFT implementation. The goal is not to copy the interview literally, but to preserve the useful structure: short premium, defined risk, repeated small entries, and strict risk filtering.

## Core Thesis

Mark's stated edge is not market prediction. It is repeated execution of small defined-risk SPX credit structures with tight risk management, high liquidity, and deliberate handling of adverse moves. The useful model is:

1. Trade SPX/SPXW because it is liquid, cash-settled, and operationally efficient.
2. Use defined-risk credit spreads instead of naked short premium.
3. Focus on small short deltas rather than trying to be perfectly directional.
4. Treat risk controls as first-class logic, not as post-entry cleanup.
5. Repeat many small, bounded decisions instead of waiting for a single perfect setup.

## What Mark's Note Implies for ZeroHFT

Mark's note suggests a strategy that is more active than the current ZeroHFT defaults, but still disciplined.

1. Timing should begin shortly after the open and continue intraday, not just in a narrow window.
2. Short strikes should live in a modest delta band, roughly 7 to 20 delta.
3. Structures should stay defined-risk and liquid.
4. Tail protection should exist as a real hedge allocation or portfolio overlay, not only as a readiness check.
5. Position sizing should remain small enough that repeated losses do not break the book.

## Current ZeroHFT Behavior

ZeroHFT already implements most of the strategy-specific safety architecture that Mark's note would require. The shared regime, stress, stance, and dispatch controls sit one layer up in D31 and apply across strategies.

1. It is SPX-focused and routes through a defined-risk micro-tranche executor.
2. It enforces delta-band selection, VIX gating, IV-rank gating, probability-of-profit gating, calendar gating, and gamma gating.
3. It is paper-only by default.
4. It refuses unstructured fallback if the defined-risk planner is unavailable.
5. It serializes multileg paper orders through D31 rather than letting the strategy drift into ad hoc single-leg behavior.

The broader regime, stress, stance, and dispatch controls are not ZeroHFT-only. They are shared D31-level controls that apply across strategies, while ZeroHFT adds its own entry gates on top of that system-wide framework.

The current code path is concentrated in:

- [SpyderD41_ZeroHFT.py](/home/adam/Projects/Spyder/Spyder/SpyderD_Strategies/SpyderD41_ZeroHFT.py)
- [SpyderD40_MicroTrancheExecutor.py](/home/adam/Projects/Spyder/Spyder/SpyderD_Strategies/SpyderD40_MicroTrancheExecutor.py)
- [SpyderD31_StrategyOrchestrator.py](/home/adam/Projects/Spyder/Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py)

## Notable Gaps Versus the Interview

1. The strategy is more conservative than Mark's described pace. ZeroHFT now runs on a 60-second cadence and has a higher daily cap than the earlier version, but it still does not try to reproduce the full 100-200 trades/day style from the interview.
2. The current wing width is narrower than the historical ZeroHFT default and is now aligned to a tighter micro-tranche assumption.
3. Tail hedging is only partially modeled. The code now supports an optional allocator hook, but the tail hedge is still not a fully separate live hedge book managed inside ZeroHFT itself.
4. The strategy remains intentionally paper-safe by default.

## Practical Interpretation

If the goal is to track Mark more closely, ZeroHFT should be thought of as a constrained proxy rather than a literal clone.

- Keep the defined-risk spread structure.
- Keep the volatility and profit-quality gates.
- Keep the paper-safe default.
- Use the micro-tranche executor as the bounded entry mechanism.
- Decide separately whether tail protection should become a real allocated hedge path.

## Working Conclusion

ZeroHFT is directionally consistent with Mark's framework: sell small defined-risk premium in liquid SPX markets, repeat the process, and let risk rules dominate the workflow. The implementation is safer and more bounded than the interview suggests, which is appropriate for an automated system.

The open design question is whether the system should remain a conservative proxy for the strategy, or whether future work should widen cadence, cadence count, and hedge allocation to get closer to the operational style described by Mark.
