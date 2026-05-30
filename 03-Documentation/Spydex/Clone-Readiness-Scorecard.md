# Spydex Clone Readiness Scorecard

This document defines the stability gate Spyder must clear before it is cloned into Spydex. The goal is to avoid carrying recent instability into a second codebase and to keep the fork clean, isolated, and safe.

## Purpose

Spydex should not be created until Spyder has been stable long enough to serve as a reliable baseline. The fork should be a controlled copy of a known-good release, then customized for SPX on a separate machine with a separate Tradier account.

## Hard Gates

All of the following must be true before the fork is approved:

1. Zero open P0 issues.
2. Zero open P1 issues in startup, data freshness, risk gate, execution, or shutdown.
3. No live-safety policy violations.
4. All safety-critical tests pass.
5. The hard gates hold for 3 consecutive trading weeks.

If any hard gate fails, the answer is No-Go.

## Weekly Scorecard

Score each category from 0 to 2:

1. 2 = meets target.
2. 1 = warning or partial pass.
3. 0 = miss or breach.

Maximum score is 20. Clone-ready threshold is 18 or higher, with all hard gates passing.

| Dimension | Metric | Target | Automatic No-Go |
|---|---|---|---|
| Incident Stability | P0/P1 count in week | P0 = 0, P1 <= 1 non-safety | Any P0, or repeated P1 in same subsystem |
| Execution Safety | Wrong-route / duplicate-order / bypass events | 0 | Any confirmed unsafe execution path |
| Risk Gate Integrity | Rejected vs admitted correctness | 99%+ correct | Any confirmed bypass or misroute |
| Startup Reliability | Clean startup success rate | 99%+ | Any startup deadlock or hang in trading hours |
| Shutdown Reliability | Clean shutdown success rate | 99%+ | Forced kill needed for a normal stop |
| Market Data Freshness | Freshness SLO compliance | 99%+ on time | Stale data causes incorrect decisions |
| Strategy Determinism | Replay consistency on fixed inputs | 99%+ deterministic | Material unexplained drift |
| Test Health | Safety-critical suites | 100% pass | Any failure in a safety-critical suite |
| Code Health | Lint/type/static checks on touched paths | 100% pass | New high-severity issue in a critical path |
| Ops Readiness | Runbooks, alerts, rollback drills | Complete and tested | Missing rollback or untested failover |

## Safety-Critical Test Buckets

These must stay green before the fork:

1. Startup and SessionSupervisor lifecycle.
2. Data provider routing and freshness monitoring.
3. Strategy admission and risk validation boundaries.
4. Order dispatch path and paper/live guards.
5. GUI worker threading and shutdown behavior.
6. Recovery, orphan cleanup, and fail-closed behavior.

## Clone Approval Decision

Use the following decision logic:

1. Any hard gate fails: No-Go.
2. Score below 18: No-Go.
3. Score 18 or higher, but fewer than 3 consecutive green weeks: Hold.
4. Score 18 or higher with 3 consecutive green weeks and no hard-gate breaches: Go.

## Fork Preconditions

When the scorecard reaches Go, confirm the following before cloning:

1. Tag a golden Spyder commit.
2. Freeze risky feature work around the fork window.
3. Prepare the second machine.
4. Provision the second Tradier account.
5. Separate env files, logs, caches, state, and service names.
6. Rotate any credentials used by the new machine or app.

## Weekly Review Template

Use this section every week during the stability gate:

1. Week ending date:
2. Hard gates passed? Yes / No
3. Total score out of 20:
4. New incidents:
5. Regressions fixed this week:
6. Regressions introduced this week:
7. Highest residual risk:
8. Decision: Go / Hold / No-Go

## Notes

This scorecard is intentionally conservative. The fork should happen only after Spyder looks boring, not merely functional. That keeps Spydex from inheriting avoidable instability.