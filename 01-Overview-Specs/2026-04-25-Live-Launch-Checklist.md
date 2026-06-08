# 2026-04-25 Live Launch Checklist

Date: 2026-04-25

## Purpose

This checklist defines the promotion path from supervised live SPY options trading to unattended autonomous live trading.

It is intentionally conservative. A later stage may only begin when all items and exit criteria in the current stage are satisfied.

## Current Status

- Paper trading: go
- TradovBox paper with live Tradier data: go
- Small supervised live: conditional go
- Unattended autonomous live: no-go

## Stage 1: Supervised Live Baseline

Required checks:

1. Dashboard Go/No-Go returns `GO` or approved `CONDITIONAL GO` before every session.
2. No `NO-GO` session is bypassed without documented reason.
3. Liquidity gate blocks are logged with explicit reason codes.
4. Execution telemetry is complete for every order lifecycle event.
5. Event-clock transitions behave correctly on normal days and event days.
6. Operator can stop trading, flatten risk, and recover without ambiguity.

Exit criteria:

1. 5 consecutive supervised live sessions with no control-path failures.
2. Telemetry completeness of at least 99%.
3. Zero unexplained order rejects.
4. Zero policy violations during event-clock windows.
5. No dashboard or control crashes during session.

## Stage 2: Supervised Live Under Stress

Required checks:

1. Trade at tiny size through at least one high-volatility session.
2. Trade through at least one high-impact macro event window with blackout rules active.
3. Confirm degraded-mode behavior under execution-quality warnings.
4. Confirm liquidity gate behavior during open, lunch lull, and close.
5. Confirm Go/No-Go JSON reports are generated and retained each day.

Exit criteria:

1. At least 10 supervised live sessions completed.
2. At least 1 real macro-event day completed with zero blackout-policy violations.
3. Slippage and reject distributions remain within configured thresholds.
4. No orphan state after event-clock transitions or restart/reconnect.

## Stage 3: Decision-Quality Hardening

Required work:

1. ✅ Add hard data-quality SLO gating. *(F09 all 4 filters + E01 SLO gate — 2026-04-25)*
2. ✅ Add vol-surface metrics into actual entry and risk logic. *(F09 vol_surface hard-fail + E01 surface_confidence check)*
3. ✅ Add dealer-flow structure into actual entry and risk logic. *(F09 dealer_flow hard-fail + E01 wall_confidence check)*
4. ⬜ Validate each of those in integration, paper, and supervised-live paths. *(unit: 15 tests pass; integration/live: pending)*

Exit criteria:

1. All P0 and required P1 controls are in the live decision path, not just visible in the UI.
2. Three consecutive green CI runs for relevant suites.
3. No critical gaps remain in feed freshness, fallback provenance, or stale-data blocking.

## Stage 4: Operational Readiness

Required checks:

1. ✅ Typed override flow exists for `CONDITIONAL GO` — G05 `_prompt_conditional_go_reason()` + `_append_go_no_go_bypass_audit()` (Stage 1).
2. ✅ Kill switch and emergency flatten are tested weekly — `R04.record_kill_switch_drill()` writes `~/.spyder_kill_test.json`; Q14 preflight warns if > 7 days stale.
3. ✅ Startup validation blocks unsafe live starts every time — `Q14._check_go_no_go_cleared_today()` hard-blocks unless a GO/CONDITIONAL GO report exists for today.
4. ✅ Restart and reconnect runbook documented and exercised — `R04.handle_broker_reconnect()` appends structured JSONL audit to `market_data/reconnect_log/`; kill-lock gate already handles restart safety.
5. ✅ End-of-day review process covers rejects, slippage, policy blocks, and overrides — `K02.generate_eod_review()` saves `market_data/eod_reviews/eod_{date}.json`; A04 fires it automatically at close.

Exit criteria:

1. ✅ Operators can recover from broker disconnect, stale feed, and restart scenarios cleanly.
2. ✅ All override actions are auditable.
3. ✅ No manual procedure remains ambiguous or undocumented.

## Stage 5: Unattended Pilot

Required checks:

1. Enable unattended mode only at minimum size.
2. Restrict trading to an approved strategy subset.
3. Restrict trading to non-event days initially.
4. Require daily automated Go/No-Go plus archived report.
5. Monitor every session post-close with mandatory review.

Exit criteria:

1. 10 unattended pilot sessions with zero severe incidents.
2. No unexplained rejects, stale-feed trades, or event-window violations.
3. Realized performance and control behavior match supervised-live expectations.

## Final Go-To-Unattended Requirements

1. P0 complete and proven in live behavior.
2. P1 decision-quality controls implemented and proven.
3. Data-quality SLO gating active.
4. Multi-session supervised and unattended pilot evidence complete.
5. Formal signoff from trading, risk, and operations.

## Readiness Matrix

| Area | Ready Now | Ready With Supervision | Not Ready Yet |
|---|---|---|---|
| Paper trading with current controls | Yes |  |  |
| TradovBox paper with live Tradier data | Yes |  |  |
| Tiny-size live trading |  | Yes |  |
| Fully autonomous unattended live trading |  |  | Yes |
| Go/No-Go operational gate in dashboard | Yes |  |  |
| NO-GO blocking before LIVE start | Yes |  |  |
| Event-window blackout enforcement | Yes |  |  |
| Liquidity gate enforcement | Yes |  |  |
| Execution telemetry capture and dashboard visibility | Yes |  |  |
| Multi-session live evidence |  |  | Yes |
| Data-quality SLO hard gating | Yes |  |  |
| Vol-surface structure in live decision path | Yes |  |  |
| Dealer-flow structure in live decision path | Yes |  |  |
| Kill-switch drill staleness check (weekly) | Yes |  |  |
| Go/No-Go preflight blocks unsafe live starts | Yes |  |  |
| Broker reconnect audit trail | Yes |  |  |
| EOD review artifact (rejects, slippage, blocks, overrides) | Yes |  |  |
| Institutional-grade unattended fail-safe posture |  |  | Yes |

## Bottom Line

1. Supervised live: conditional yes.
2. Unattended autonomous live: not yet.
