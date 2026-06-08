# 2026-05-03 Hands-Free 24x5 Autonomous Operations Proposal

## Objective
Enable Tradov to run hands-free, set-and-forget, 24 hours/day during weekdays, with an enforced active trading window of 09:30 to 16:15 ET for SPY options, automated risk-aware shutdown, ongoing Telegram profit/loss updates during market hours, end-of-day and end-of-week P/L summaries, complete logging artifacts for weekend review, and urgent Telegram escalation.

## Executive Decision
Yes, this is feasible with the current codebase, but only with a controlled rollout and explicit operational guardrails.

Current repo evidence shows the required building blocks already exist:
- Timed/session-aware scheduling via A04 scheduler and market calendar.
- Process lifecycle launch/stop scripts and service unit scaffolding.
- Headless mode capability in launcher.
- Telegram bot integration and startup wiring from environment.
- Existing live launch readiness checklist that already classifies unattended live as a staged promotion.

## What "24x5 hands-free" means here
- Platform uptime: services remain running continuously Monday-Friday.
- Trading activity: enabled only from 09:30 to 16:15 ET for SPY options.
- Outside that window: no new entries, controlled stop/flatten policy, artifact generation, health monitoring continues.
- Weekend: no trading; logs and EOD artifacts available for review.

## Baseline Findings From Current Tradov

### Scheduling and market-time awareness
- A04 already supports trading day/session logic, holiday/weekend awareness, and ET-aware market checks.
- This is a strong foundation for enforcing weekday windows and avoiding weekend/holiday starts.

### Launch and shutdown control
- Q14 launcher supports mode and headless operation.
- Q10/Q11 scripts provide bulk start/stop process control.
- Existing systemd service unit demonstrates environment, working directory, and restart patterns.

### Alerting and Telegram
- Telegram integration already exists and can be bootstrapped from TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
- Bot startup is optional/fail-safe when not configured, which is good for controlled rollout.

### Operational readiness posture
- Live launch checklist explicitly requires staged promotion from supervised to unattended pilot.
- This aligns with a safe path for autonomous operation and should remain the governing policy.

## Proposed Operating Model

### Daily weekday timeline (ET)
1. 08:55: Preflight (no trading)
- Validate config/env and broker connectivity.
- Validate data feed freshness and calendar status.
- Validate kill-switch lock state and stale-drill checks.
- Send Telegram preflight summary (GO / CONDITIONAL GO / NO-GO).

2. 09:30: Start autonomous trading session
- Start core service in headless mode if not already active.
- Enable trading gate only if preflight is GO (or approved CONDITIONAL GO path).
- Publish Telegram "session started" message with mode, account, and strategy set.

3. 09:30-16:15: Intraday autonomous run
- Execute strategies and risk checks under existing risk controls.
- Keep monitoring/metrics/logging active.
- Send Telegram actionable urgency alerts and recurring P/L heartbeat summaries.

4. 15:30-16:00: Expiration-day safety gates (0DTE)
- Enforce configurable no-new-risk window for same-day-expiring contracts.
- Enforce broker at-risk cutoff minus safety buffer for forced flatten of short at-risk positions.
- Escalate HIGH alert if broker cutoff data is missing for live mode (fail closed).

5. 16:15: Controlled session stop
- Disable new entries immediately.
- Apply defined close behavior (flatten-all OR managed carry policy; recommend flatten-all for unattended phase).
- Run EOD artifact generation.
- Send Telegram end-of-day P/L summary.

6. 16:15-17:30: Post-close assignment risk window
- Keep non-trading health monitors active.
- Track assignment/pin-risk exposure until exercise decision window ends.
- Send urgent Telegram alert if any short near-the-money exposure remains during this window.

7. 17:30 onward: Post-session monitoring only
- Keep non-trading health monitors active.
- No order-entry capability until next trading window.

### Weekend mode
- Trading disabled by policy.
- Keep services either:
  - Option A: running in monitor-only mode, or
  - Option B: fully stopped after Friday close and auto-start Monday pre-open.
- Recommended for simplicity and lower risk: Option B in early unattended rollout.
- Send Telegram end-of-week P/L summary (Friday 16:20 ET or Saturday 08:00 ET fallback).

## Target Architecture (Minimal Change)

### Layer 1: Host/process orchestration
Use systemd as the source of truth for process lifecycle and recovery.

- Primary service:
  - tradov-main.service (headless, auto-restart on failure)
- Window timers:
  - tradov-session-start.timer -> 09:30 ET weekdays
  - tradov-session-stop.timer -> 16:15 ET weekdays
  - tradov-0dte-risk-cutoff.timer -> configurable window before broker cutoff (recommended: 15:45 ET baseline)
- Optional:
  - tradov-preflight.timer -> 08:55 ET weekdays
  - tradov-weekend-stop.timer -> Friday 16:20 ET
  - tradov-monday-start.timer -> Monday 08:55 ET

### Layer 2: In-app trading gates
Keep the app-level safety gate as mandatory, even if systemd starts a process.

- Required gates before any order flow:
  - Trading day/session valid
  - Entry trust gate and Go/No-Go status valid
  - Data freshness and risk sync valid
  - Broker client available and healthy

This dual-layer model prevents accidental orders from scheduler bugs or host restarts.

### Expiration-day and broker-cutoff policy
- Exchange close for SPY options is 16:15 ET; this is the hard market-trading boundary.
- Broker liquidation/exercise safety cutoffs can be earlier and must be configured per broker profile.
- In live mode, if broker cutoff configuration is unavailable or stale, entries are blocked (fail closed).
- Exercise-decision monitoring window runs through 17:30 ET to manage pin-risk visibility.

## Telegram Escalation Design

### Channel setup
- Use one primary operator channel/chat ID.
- Optionally add backup chat ID for critical alerts only.

### Severity policy
- Critical (immediate): broker disconnect, kill-switch trigger, risk circuit-breaker, stop-loss rejection patterns, repeated order rejects, stale feed lockout during active session.
- High (near-real-time): session start/stop anomalies, preflight NO-GO, unexpected strategy halt.
- Informational: compressed periodic P/L heartbeat, EOD P/L summary, and EOW P/L summary.

## Telegram P/L Reporting Plan

### Ongoing intraday P/L updates
- Cadence: every 30 minutes during active window (09:30-16:15 ET).
- Optional higher cadence mode: every 15 minutes when account drawdown exceeds warning threshold.
- Fields per update:
  - timestamp ET
  - realized P/L day
  - unrealized P/L current
  - net P/L day
  - open positions count
  - largest winner and loser position (symbol and value)
  - risk state (normal, warning, critical)

### End-of-day P/L Telegram summary
- Dispatch time: 16:16-16:20 ET after close workflow completes.
- Required fields:
  - total realized P/L day
  - total unrealized P/L carry (should be zero in flatten-all mode)
  - gross and net return percentages
  - trade count, win rate, average winner, average loser
  - max intraday drawdown
  - major rejects/risk blocks count
  - one-line operational status (clean close or incident flag)

### End-of-week P/L Telegram summary
- Dispatch time: Friday 16:20-17:00 ET.
- Fallback dispatch: Saturday 08:00 ET if Friday job fails.
- Required fields:
  - weekly realized P/L
  - weekly net return percentage
  - best day and worst day P/L
  - total trades and weekly win rate
  - weekly max drawdown
  - count of critical incidents and unresolved items
  - readiness note for next Monday (go, conditional go, no-go)

### Delivery rules and reliability
- P/L messages are informational and must not suppress critical alerts.
- If Telegram delivery fails, retry with backoff and persist to a local pending queue for replay.
- Escalate a HIGH alert if EOD or EOW summary cannot be delivered after retry budget.

### Telegram message templates (examples)

#### Intraday P/L heartbeat template
Use every 30 minutes during active trading window.

```text
[INFO][P/L HEARTBEAT] TRADOV
Time (ET): 2026-05-04 11:30
Mode/Acct: LIVE / XXXXX1234
Realized P/L (Day): +$325.40
Unrealized P/L: -$74.10
Net P/L (Day): +$251.30 (+0.21%)
Open Positions: 3
Top Winner: SPY 0DTE 530C +$142.00
Top Loser: SPY 0DTE 525P -$88.00
Risk State: NORMAL
```

#### End-of-day P/L summary template
Use once after controlled stop completes.

```text
[EOD SUMMARY] TRADOV
Date (ET): 2026-05-04
Mode/Acct: LIVE / XXXXX1234
Realized P/L (Day): +$612.75
Unrealized Carry: $0.00
Net Return (Day): +0.51%
Trades: 12 | Win Rate: 66.7%
Avg Winner: +$96.40 | Avg Loser: -$58.20
Max Intraday Drawdown: -0.34%
Rejects/Risk Blocks: 1 / 2
Session Close Status: CLEAN CLOSE
Artifact: market_data/eod_reviews/eod_2026-05-04.json
```

#### End-of-week P/L summary template
Use Friday primary dispatch, Saturday fallback dispatch.

```text
[EOW SUMMARY] TRADOV
Week: 2026-W19
Mode/Acct: LIVE / XXXXX1234
Weekly Realized P/L: +$2,184.90
Weekly Net Return: +1.82%
Best Day: Tue +$845.20
Worst Day: Thu -$312.40
Trades: 57 | Weekly Win Rate: 63.2%
Weekly Max Drawdown: -0.91%
Critical Incidents: 0
Unresolved Items: 1 (non-blocking)
Monday Readiness: GO
Artifact: market_data/weekly/weekly_pnl_summary_2026-W19.json
```

#### JSON payload schema (transport-safe)
When sending via bot API wrapper, keep a machine-parsable payload alongside display text.

```json
{
  "message_type": "pl_heartbeat",
  "timestamp_et": "2026-05-04T11:30:00-04:00",
  "mode": "live",
  "account": "XXXXX1234",
  "realized_pl_day": 325.4,
  "unrealized_pl": -74.1,
  "net_pl_day": 251.3,
  "net_return_pct_day": 0.21,
  "open_positions": 3,
  "risk_state": "normal",
  "correlation_id": "sess-20260504-01"
}
```

### Threshold-triggered unscheduled P/L alerts
Send immediate Telegram messages when P/L crosses configured guardrails; these are event-driven and independent of the periodic heartbeat schedule.

#### Default trigger set (recommended)
- Daily loss breach: net day P/L <= -$500 (HIGH) and <= -$1,000 (CRITICAL).
- Daily profit milestone: net day P/L >= +$500 and each additional +$500 step (INFO).
- Drawdown acceleration: intraday drawdown worsens by >= 0.40% within 15 minutes (HIGH).
- Recovery milestone: drawdown recovers by >= 0.30% from worst point (INFO).
- Realized loss streak: 3 consecutive losing closes on executed trades within 30 minutes (HIGH).

#### Suggested trigger values by account size
Use these as starting values, then tighten or loosen after 2-3 weeks of real alert telemetry.

| Account equity (USD) | High daily loss alert | Critical daily loss alert | Profit milestone step | Drawdown acceleration alert |
|---|---:|---:|---:|---:|
| 10,000 | -100 (1.0%) | -200 (2.0%) | +100 (1.0%) | 0.40% in 15 min |
| 25,000 | -250 (1.0%) | -500 (2.0%) | +250 (1.0%) | 0.40% in 15 min |
| 50,000 | -500 (1.0%) | -1,000 (2.0%) | +500 (1.0%) | 0.35% in 15 min |
| 100,000 | -1,000 (1.0%) | -2,000 (2.0%) | +1,000 (1.0%) | 0.30% in 15 min |
| 250,000 | -2,500 (1.0%) | -5,000 (2.0%) | +2,500 (1.0%) | 0.25% in 15 min |

#### Percentage-based tuning formula
To normalize behavior across account sizes, derive trigger values from net liquidation value (NLV):

- high_loss_usd = -0.010 x NLV
- critical_loss_usd = -0.020 x NLV
- profit_step_usd = +0.010 x NLV
- recovery_milestone_pct = 0.30% (0.25%-0.40% range)
- drawdown_acceleration_pct = 0.30%-0.40% over 15 minutes (smaller accounts use higher end to reduce noise)

Round USD thresholds to nearest 25 for cleaner operator readability in Telegram.

#### Anti-noise controls
- Cooldown: do not resend the same trigger type within 15 minutes unless severity escalates.
- Hysteresis: require a 10% buffer move away from threshold before a re-arm of the same trigger.
- Session cap: max 30 informational trigger alerts per day; no cap on CRITICAL alerts.

#### Unscheduled alert template: loss breach
```text
[HIGH][P/L THRESHOLD BREACH] TRADOV
Time (ET): 2026-05-04 13:42
Mode/Acct: LIVE / XXXXX1234
Trigger: Daily loss threshold exceeded
Threshold: -$500.00
Current Net P/L (Day): -$563.20 (-0.47%)
Open Positions: 2
Risk State: WARNING
Action: Monitor closely; auto-risk controls active.
Correlation: sess-20260504-01
```

#### Unscheduled alert template: critical loss breach
```text
[CRITICAL][P/L CIRCUIT ALERT] TRADOV
Time (ET): 2026-05-04 14:07
Mode/Acct: LIVE / XXXXX1234
Trigger: Critical daily loss threshold exceeded
Threshold: -$1,000.00
Current Net P/L (Day): -$1,042.70 (-0.86%)
Risk State: CRITICAL
Action: New entries blocked; emergency policy engaged.
Correlation: sess-20260504-01
```

#### Unscheduled alert template: profit milestone
```text
[INFO][P/L MILESTONE] TRADOV
Time (ET): 2026-05-04 12:18
Mode/Acct: LIVE / XXXXX1234
Trigger: Profit milestone reached
Milestone: +$1,000
Current Net P/L (Day): +$1,036.10 (+0.86%)
Open Positions: 1
Risk State: NORMAL
Correlation: sess-20260504-01
```

#### Trigger payload schema
```json
{
  "message_type": "pl_threshold_alert",
  "timestamp_et": "2026-05-04T13:42:00-04:00",
  "mode": "live",
  "account": "XXXXX1234",
  "trigger_code": "DAILY_LOSS_HIGH",
  "severity": "high",
  "threshold_value": -500.0,
  "current_net_pl_day": -563.2,
  "drawdown_pct": -0.47,
  "risk_state": "warning",
  "cooldown_active": false,
  "correlation_id": "sess-20260504-01"
}
```

### Message contracts
Each urgent Telegram message should include:
- timestamp ET
- severity
- subsystem
- account/mode
- short action guidance
- correlation id or event id

## Telegram Remote Halt Control (Operator Commands)

Yes, Tradov should support command-based remote halt from Telegram for unattended operations.

### Proposed command set (v1)
- `/status`
  - Returns trading state, mode, open positions count, current net day P/L, and last critical alert.
- `/halt`
  - Immediately blocks new entries and triggers kill-switch persistence (lock file), with optional emergency flatten based on policy.
- `/flatten`
  - Closes open positions and cancels open orders, then confirms final position state.
- `/resume`
  - Clears kill-lock and resumes only if preflight gates pass (calendar, data freshness, risk sync, broker health).
- `/help`
  - Returns available commands and required confirmation format.

### Safety and authorization model
- Whitelist-only operators:
  - Accept commands only from configured Telegram user IDs (not username string matching alone).
- Two-step confirmation for dangerous actions:
  - `/halt` -> bot replies with short token challenge -> operator must respond `/confirm HALT <token>` within 60 seconds.
  - `/resume` uses similar confirmation challenge.
- Optional dual-approval mode (future):
  - Require confirmation from two approved operators for `/resume` in live mode.

### Command execution behavior
- `/halt` behavior:
  - Set in-memory kill-switch.
  - Persist kill-lock file so restart cannot silently resume.
  - Emit critical alert and write audit entry.
- `/flatten` behavior:
  - Cancel all working orders.
  - Close all open positions.
  - Report per-symbol results and residual risk if any legs fail.
- `/resume` behavior:
  - Clear kill-lock only after all preflight checks pass.
  - If checks fail, remain halted and return explicit failed gates.

### Audit and compliance requirements
- Every operator command must write an immutable audit event containing:
  - timestamp ET
  - telegram user id
  - command
  - correlation id
  - pre-state
  - action result
  - post-state
- Store daily command audit at:
  - `market_data/operator_commands/operator_commands_YYYY-MM-DD.jsonl`

### Telegram command response templates

#### HALT accepted
```text
[CRITICAL][OPERATOR HALT EXECUTED] TRADOV
Time (ET): 2026-05-04 14:18
Requested By: user_id=123456789
Action: HALT
Result: SUCCESS
Trading State: HALTED
Kill Lock: ACTIVE
Positions: 2 open (flatten policy: pending)
Correlation: op-20260504-1418
```

#### RESUME blocked by failed preflight
```text
[HIGH][RESUME BLOCKED] TRADOV
Time (ET): 2026-05-04 15:02
Requested By: user_id=123456789
Action: RESUME
Result: DENIED
Failed Gates: data_freshness, broker_health
Trading State: HALTED
Kill Lock: ACTIVE
Correlation: op-20260504-1502
```

### Implementation notes for current codebase
- Reuse existing Telegram polling path currently used for approval callbacks.
- Add a command parser for text messages and callback commands.
- Wire command actions to existing halt/stop and kill-lock primitives in runtime and launcher.
- Ensure command actions are no-op in unauthorized contexts.

## Logging and Weekend Review Package

Generate and retain a daily operations bundle under market_data and logs:
- session_summary_YYYY-MM-DD.json
- execution_rejects_YYYY-MM-DD.jsonl
- risk_events_YYYY-MM-DD.jsonl
- go_no_go_YYYY-MM-DD.json
- reconnect_log_YYYY-MM-DD.jsonl
- pnl_and_drawdown_YYYY-MM-DD.json

Weekly (Friday close or Saturday 08:00 ET), generate:
- weekly_ops_report_YYYY-WW.md
- includes incidents, rejects, policy blocks, downtime, and action items.
- weekly_pnl_summary_YYYY-WW.json

Retention recommendation:
- hot: 30 days local
- warm archive: 6-12 months compressed

## Safety Defaults For Unattended Phase
- Default mode for first unattended wave: paper or minimum live size.
- Default close policy at 16:15 ET: flatten all open intraday positions.
- Default 0DTE policy: no new 0DTE entries after configurable cutoff (recommended 15:45 ET baseline).
- NO-GO must hard-block entry; no silent bypass.
- If broker/data health is uncertain, fail closed (no new orders).
- Any uncertainty in position state triggers safe mode and Telegram critical alert.

## Implementation Plan

### Phase 0 (1-2 days): Pre-production hardening
- Finalize service and timer units.
- Add/confirm preflight command path and machine-readable output.
- Verify Telegram credentials and test alert routing.
- Configure Telegram P/L heartbeat interval and EOD/EOW summary jobs.
- Validate timezone handling on host (system clock + ET conversion tests).

### Phase 1 (3-5 trading days): Paper unattended pilot
- Full autonomous schedule at 09:30-16:15 ET.
- Mandatory daily EOD and weekly review artifacts.
- Validate intraday, EOD, and EOW Telegram P/L message accuracy against saved artifacts.
- Track incident count and alert quality.

### Phase 2 (5-10 trading days): Tiny live supervised fallback
- Enable tiny-size live with human-on-call only for critical alerts.
- Keep flatten-at-close mandatory.
- No strategy expansion until incident rate is stable.

### Phase 3: Set-and-forget live 24x5
- Promote only after measurable stability criteria are met.
- Keep strict fail-closed and Telegram escalation policy.

## Acceptance Criteria
- 10+ consecutive scheduled weekday sessions start and stop exactly on policy window.
- Zero trades outside 09:30-16:15 ET.
- Zero SPY options order attempts after 16:15 ET.
- Zero unresolved at-risk short positions beyond configured broker cutoff unless explicitly approved incident mode is active.
- Zero unresolved critical alerts.
- EOD artifact completeness >= 99%.
- Telegram critical alerts delivered within 60 seconds.
- Telegram intraday P/L heartbeat delivery success >= 99% during active sessions.
- Telegram end-of-day and end-of-week P/L summaries delivered for 100% of completed sessions/weeks (or flagged with explicit delivery-failure alert).
- No phantom/orphan order state at session boundaries.

## Open Risks and Mitigations
1. Risk: time boundary and holiday edge cases.
- Mitigation: A04 market calendar as source of truth; test early close days explicitly.

2. Risk: process alive but trading gate stale.
- Mitigation: dual-layer gating (systemd plus in-app checks), periodic gate health metric.

3. Risk: alert fatigue.
- Mitigation: strict severity routing; periodic summaries only for non-actionable events.

4. Risk: weekend confidence gap.
- Mitigation: mandatory weekly report and unresolved-incident checklist before Monday start.

5. Risk: after-hours gap and pin risk (16:15-17:30 ET).
- Mitigation: enforce 0DTE no-new-risk cutoff, flatten short near-the-money exposure before broker cutoff, and run post-close assignment-risk monitoring through 17:30 ET with CRITICAL escalation for unresolved at-risk shorts.

## Proposed Task Backlog (Execution-Ready)
1. Create/validate systemd units and timers for preflight, start, and stop windows.
2. Wire preflight command to output GO/CONDITIONAL GO/NO-GO JSON and Telegram summary.
3. Enforce 09:30-16:15 ET SPY options gate in one authoritative runtime path.
4. Enforce broker-cutoff-aware 0DTE no-new-risk gate and flatten-or-managed-close policy by 16:15 ET with auditable result.
5. Implement Telegram intraday P/L heartbeat publisher with configurable cadence.
6. Implement Telegram EOD and EOW P/L summary publishers with retry and fallback scheduling.
7. Add daily artifact bundling and weekly report generation jobs.
8. Add on-host operational dashboard command for quick status and last incident.
9. Run paper unattended pilot and record metrics against acceptance criteria.

## Compact Implementation Checklist (Module-Mapped)

### Step 1: Session windows and host timers
- Target files:
  - Tradov/TradovQ_Scripts/TradovQ74_TradovMain.service
  - Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py
  - Tradov/TradovQ_Scripts/TradovQ10_StartAll.sh
  - Tradov/TradovQ_Scripts/TradovQ11_StopAll.sh
- Actions:
  - Set weekday timer boundaries to 09:30 start and 16:15 stop.
  - Add explicit 0DTE risk-cutoff timer hook (recommended baseline 15:45 ET).
  - Ensure Friday EOW timing aligns with 16:20 ET primary dispatch window.
- Done when:
  - Service/timer dry run shows exactly one start and one stop event per weekday.

### Step 2: In-app trading gate authority
- Target files:
  - Tradov/TradovA_Core/TradovA04_Scheduler.py
  - Tradov/TradovA_Core/TradovA06_MasterController.py
- Actions:
  - Make 09:30-16:15 ET the authoritative SPY options entry gate.
  - Block new entries after configured 0DTE no-new-risk cutoff.
  - Enforce fail-closed behavior if broker cutoff profile is missing in live mode.
- Done when:
  - No SPY options entry attempts occur outside 09:30-16:15 ET in pilot logs.

### Step 3: Controlled stop and pin-risk window
- Target files:
  - Tradov/TradovA_Core/TradovA06_MasterController.py
  - Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py
- Actions:
  - Execute close policy at 16:15 ET (flatten-all in unattended v1 default).
  - Define at-risk short option policy using configurable distance-to-ATM threshold and broker cutoff buffer.
  - Add post-close assignment-risk state tracking through 17:30 ET.
  - Emit escalation when short near-the-money exposure remains in post-close window.
- Done when:
  - EOD close runs complete and post-close risk status is auditable for each session.

### Pin Risk Control Policy (Mandatory in unattended mode)
- Policy defaults:
  - No new 0DTE short risk after cutoff (recommended baseline 15:45 ET; broker-profile configurable).
  - Force flatten all at-risk short options before broker cutoff minus safety buffer.
  - At-risk default: short leg within configurable proximity to underlying price or delta threshold (profile-driven).
  - If broker cutoff metadata is unavailable in live mode, trading remains blocked (fail closed).
- Monitoring window:
  - From 16:15 ET to 17:30 ET, continue assignment-risk monitoring and Telegram escalation.
  - Critical alert if unresolved short at-risk exposure persists past configured cutoff.
- Audit requirements:
  - Persist pin-risk decisions and actions to daily artifacts with correlation IDs.
  - Record pre-cutoff position snapshot, flatten attempts, and residual-risk status.

## Day-by-Day Runbook

### Phase 0 Runbook (1-2 days, pre-production hardening)

#### Day 1: Timing, gates, and preflight
- Configure host timers for 08:55 preflight, 09:30 session start, 16:15 session stop, and 0DTE risk cutoff.
- Validate scheduler timezone handling and holiday/early-close behavior.
- Implement preflight JSON contract (GO/CONDITIONAL GO/NO-GO) and Telegram preflight summary.
- Verify fail-closed behavior when broker cutoff profile is missing.
- Exit criteria:
  - Dry run shows deterministic timer events and correct gate state transitions.

#### Day 2: Pin risk controls, messaging, and artifact checks
- Wire pin-risk policy controls (no-new-risk cutoff, forced flatten, post-close monitoring).
- Validate Telegram routing for heartbeat, EOD, EOW, and CRITICAL escalation flows.
- Validate daily artifact bundle generation and operator command audit logging.
- Run a full end-to-end simulated day from preflight through post-close window.
- Exit criteria:
  - All required artifacts generated and Telegram scenarios verified, including failure/retry behavior.

### Phase 1 Runbook (3-5 trading days, paper unattended pilot)

#### Day 1: Controlled pilot start
- Run unattended paper session with full schedule.
- Observe entry/exit gate behavior and confirm no orders outside policy window.
- Validate heartbeat timing and EOD summary completeness.
- Daily pass/fail gates:
  - Window compliance pass.
  - Alert latency pass.
  - Artifact completeness pass.

#### Day 2: Expiration-day simulation emphasis
- Focus on 0DTE behavior and cutoff logic under elevated activity.
- Validate forced flatten path and post-close assignment-risk monitoring.
- Trigger synthetic near-the-money short exposure to verify escalation path.
- Daily pass/fail gates:
  - Pin-risk policy pass.
  - Broker-cutoff fail-closed path pass.

#### Day 3: Reliability and recovery drills
- Induce temporary Telegram send failure to validate retry and queue replay.
- Induce data staleness condition to validate NO-GO and entry block.
- Verify operator audit log entries for all control actions.
- Daily pass/fail gates:
  - Delivery reliability pass.
  - Safety interlock pass.

#### Day 4: Stability confirmation (optional if 3-day pilot is clean)
- Repeat unattended run with no manual interventions.
- Compare operational metrics against Day 1-3 baseline.
- Daily pass/fail gates:
  - Alert volume manageable.
  - No unresolved critical incidents.

#### Day 5: Promotion readiness review (optional for 5-day pilot)
- Compile pilot evidence against acceptance criteria.
- Produce go/no-go recommendation for tiny-live supervised fallback.
- Document open defects, owner, and remediation ETA.
- Exit criteria:
  - Promotion decision is evidence-based and signed off by operational owner.

### Step 4: Telegram P/L and escalation delivery
- Target files:
  - Tradov/TradovJ_Alerts/TradovJ05_TelegramBot.py
- Actions:
  - Heartbeat window: 09:30-16:15 ET with configured cadence.
  - EOD summary window: 16:16-16:20 ET.
  - EOW summary window: Friday 16:20-17:00 ET with Saturday 08:00 fallback.
  - Add retry/backoff plus local pending queue replay for failed sends.
- Done when:
  - Delivery SLOs match spec targets and failed sends produce explicit HIGH alerts.

### Step 5: Artifacts, audits, and acceptance evidence
- Target files:
  - Tradov/TradovA_Core/TradovA04_Scheduler.py
  - Tradov/TradovA_Core/TradovA06_MasterController.py
  - Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py
- Actions:
  - Emit daily operational artifacts and weekly summary outputs defined in this proposal.
  - Persist operator command audit log and correlation IDs for every control action.
  - Capture pilot evidence for all acceptance criteria.
- Done when:
  - 10+ consecutive sessions satisfy policy window, alerting, and artifact completeness metrics.

## Recommendation
Proceed now with a staged unattended rollout (paper -> tiny live -> set-and-forget live) using the architecture above. The platform is close enough to support this, but production autonomy should remain gate-driven and fail-closed, with Telegram reserved for urgent actionable incidents.

## Recommended Starter Profile (v1.0)

Use this profile as the initial production baseline for unattended operation, then tune after 10 trading sessions of telemetry.

### Profile intent
- Keep behavior conservative and readable.
- Prioritize loss-protection signals over profit-celebration noise.
- Provide enough P/L visibility without excessive Telegram spam.

### v1.0 settings
- Intraday P/L heartbeat cadence: every 30 minutes.
- Elevated heartbeat cadence: every 15 minutes when drawdown >= 0.75%.
- High daily loss alert: -1.0% of NLV.
- Critical daily loss alert: -2.0% of NLV.
- Profit milestone step: +1.0% of NLV.
- Drawdown acceleration trigger: 0.35% worsening in 15 minutes.
- Recovery milestone trigger: 0.30% rebound from worst intraday drawdown.
- Loss streak trigger: 3 consecutive losing closes in 30 minutes.
- Cooldown for repeated same trigger: 15 minutes.
- Re-arm hysteresis: 10% beyond threshold.
- Informational trigger cap: 30 per session.
- 0DTE no-new-risk cutoff: configurable by broker profile (recommended baseline: 15:45 ET).
- EOD summary dispatch: 16:16-16:20 ET.
- EOW summary dispatch: Friday 16:20-17:00 ET; Saturday 08:00 ET fallback.

### Example instantiated values (for NLV = 50,000)
- High daily loss alert: -500
- Critical daily loss alert: -1,000
- Profit milestone step: +500 increments
- Elevated heartbeat mode activates at: -375 net day P/L equivalent drawdown state

### Promotion rule for v1.1 tuning
Change thresholds only after at least 10 sessions and all conditions below are met:
- Critical alert false-positive rate <= 5%
- Intraday P/L heartbeat delivery success >= 99%
- Operator feedback indicates manageable alert volume
- No missed EOD/EOW summary deliveries without explicit failure alert

## Source Files Used For This Proposal
- Tradov/TradovA_Core/TradovA04_Scheduler.py
- Tradov/TradovA_Core/TradovA06_MasterController.py
- Tradov/TradovQ_Scripts/TradovQ14_MainLauncher.py
- Tradov/TradovQ_Scripts/TradovQ10_StartAll.sh
- Tradov/TradovQ_Scripts/TradovQ11_StopAll.sh
- Tradov/TradovQ_Scripts/TradovQ74_TradovMain.service
- Tradov/TradovQ_Scripts/TradovQ93_RunPaper.py
- Tradov/TradovJ_Alerts/TradovJ05_TelegramBot.py
- 01-Overview-Specs/2026-04-25-Live-Launch-Checklist.md
