# Telegram Message Templates

> **Source file:** `Tradov/TradovJ_Alerts/TradovJ05_TelegramBot.py` (2,755 lines)
> **Last audited:** 2026-06-06

---

## Table of Contents

1. [Trade Lifecycle Messages](#1-trade-lifecycle-messages)
2. [Stop Loss Alert](#2-stop-loss-alert)
3. [Daily Summary](#3-daily-summary)
4. [General Alert](#4-general-alert)
5. [P/L Threshold Alerts](#5-pl-threshold-alerts)
6. [End-of-Week Summary](#6-end-of-week-summary)
7. [Inbound Command Responses](#7-inbound-command-responses)
8. [Generic Template Map](#8-generic-template-map)

---

## 1. Trade Lifecycle Messages

### 1.1 Trade Opened (`send_trade_opened`, line 444)

Emitted when a new position is opened. Emoji selects **bull** for CALL positions, **bear** otherwise.

```
{🐂/🐻} TRADE OPENED

📊 Strategy: {strategy}
📌 Symbol: {symbol}
🔄 Type: {position_type}
💵 Quantity: {quantity}
💵 Entry Price: ${entry_price:.2f}
🎯 Target: ${target_price:.2f}            ← optional
🛑 Stop Loss: ${stop_price:.2f}           ← optional
⚠️ Max Risk: ${max_risk:.2f}              ← optional

🕐 {HH:MM AM/PM} ET
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `symbol` | str | yes | e.g. "SPY 450C" |
| `strategy` | str | yes | Strategy display name |
| `position_type` | str | yes | Drives bull/bear emoji |
| `quantity` | int | yes | Contracts/shares |
| `entry_price` | float | yes | |
| `target_price` | float | no | |
| `stop_price` | float | no | |
| `max_risk` | float | no | |

**Priority:** HIGH · **Message type:** TRADE_OPEN

---

### 1.2 Trade Closed (`send_trade_closed`, line 485)

Emitted when a position is closed. Status and emojis depend on P/L sign.

```
{💰/📉} TRADE CLOSED - {PROFIT|LOSS}

📊 Strategy: {strategy}
📌 Symbol: {symbol}
🔄 Type: {position_type}
💵 Entry: ${entry_price:.2f}
💵 Exit: ${exit_price:.2f}
💵 Quantity: {quantity}

{✅/❌} P&L: ${pnl:+.2f} ({pnl_percent:+.1f}%)
ℹ️ Reason: {reason}

🕐 {HH:MM AM/PM} ET
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `symbol` | str | yes | |
| `strategy` | str | yes | |
| `position_type` | str | yes | |
| `entry_price` | float | yes | |
| `exit_price` | float | yes | |
| `quantity` | int | yes | |
| `pnl` | float | yes | Dollar P/L |
| `pnl_percent` | float | yes | Percentage P/L |
| `reason` | str | no | Default: "Target reached" |

**Priority:** HIGH · **Message type:** TRADE_CLOSE

---

### 1.3 Compact Trade Opened (`send_compact_trade_message`, line 529, event_type="opened")

Single-line notification used by live event handlers (`_handle_trade_event`, `_handle_position_closed_event`).

```
🎯 {strategy} executed · {symbol}  {time} ET
```

**Priority:** HIGH · **Message type:** TRADE_OPEN

---

### 1.4 Compact Trade Closed (`send_compact_trade_message`, line 529, event_type="closed")

```
{💰/📉} {strategy} closed · P&L: {pnl_str} ({pct}%)  {time} ET
```

Where `pnl_str` is `+$X.XX` or `-$X.XX`.

**Priority:** HIGH · **Message type:** TRADE_CLOSE

---

## 2. Stop Loss Alert

### 2.1 Stop Loss Triggered (`send_stop_loss_alert`, line 549)

```
🛑 STOP LOSS TRIGGERED 🛑

📌 Symbol: {symbol}
💵 Entry: ${entry_price:.2f}
💵 Stop: ${stop_price:.2f}
❌ Loss: ${loss_amount:.2f}

Position closed to limit losses

🕐 {HH:MM AM/PM} ET
```

| Field | Type | Required |
|---|---|---|
| `symbol` | str | yes |
| `entry_price` | float | yes |
| `stop_price` | float | yes |
| `loss_amount` | float | yes |

**Priority:** CRITICAL · **Message type:** STOP_LOSS

---

## 3. Daily Summary

### 3.1 Daily Trading Summary (`send_daily_summary`, line 576)

```
📅 DAILY SUMMARY {💰/📉}

Date: {Month DD, YYYY}

📊 Trading Activity:
• Total Trades: {total_trades}
• Winners: {winning_trades} ✅
• Losers: {losing_trades} ❌
• Win Rate: {win_rate:.1f}%

💰 P&L Breakdown:
• Gross P&L: ${gross_pnl:+.2f}
• Commissions: -${commissions:.2f}
• Net P&L: ${net_pnl:+.2f} {✅/❌}

🏆 Best Trade:
{symbol} +${pnl:.2f}                         ← optional

😞 Worst Trade:
{symbol} -${abs(pnl):.2f}                    ← optional

💼 Account Balance: ${balance:,.2f}           ← optional

🤖 Tradov - Autonomous Trading
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `date` | datetime | yes | |
| `total_trades` | int | yes | |
| `winning_trades` | int | yes | |
| `losing_trades` | int | yes | |
| `gross_pnl` | float | yes | |
| `commissions` | float | yes | |
| `net_pnl` | float | yes | Drives header emoji |
| `win_rate` | float | yes | |
| `best_trade` | dict | no | `{symbol, pnl}` |
| `worst_trade` | dict | no | `{symbol, pnl}` |
| `account_balance` | float | no | |

**Priority:** NORMAL · **Message type:** SUMMARY

---

## 4. General Alert

### 4.1 Generic Alert (`send_alert`, line 632)

```
{emoji} {TITLE}

{message}

🕐 {HH:MM AM/PM} ET
```

Severity-to-emoji mapping:

| Severity | Emoji |
|---|---|
| `info` | ℹ️ |
| `warning` | ⚠️ |
| `error` | ❌ |
| `critical` | 🔥 |
| *(default)* | 🔔 |

| Field | Type | Required |
|---|---|---|
| `title` | str | yes |
| `message` | str | yes |
| `severity` | str | no (default `"info"`) |

**Priority:** mapped from severity · **Message type:** ALERT

---

## 5. P/L Threshold Alerts

### `_format_pl_threshold_alert` (line 1499)

All four threshold alerts share the same body format; only the header icon and title differ.

```
{icon} {TITLE}
Time (ET): {YYYY-MM-DD HH:MM}
Mode/Acct: {mode} / {account_id}
Net P/L (Day): ${net_pl:+.2f}
Realized: ${realized:+.2f}  |  Unrealized: ${unrealized:+.2f}
Threshold: ${threshold:+.2f}
Open Positions: {n}
Risk State: {state}
Correlation: {correlation_id}
```

### 5.1 Critical Daily Loss

| | |
|---|---|
| **Icon** | 🚨 |
| **Title** | CRITICAL: DAILY LOSS LIMIT BREACH |
| **Priority** | CRITICAL |
| **Cooldown** | 15 min |
| **Trigger** | `net_pl ≤ -2% NLV` |

### 5.2 High Daily Loss

| | |
|---|---|
| **Icon** | ⚠️ |
| **Title** | WARNING: HIGH DAILY LOSS |
| **Priority** | HIGH |
| **Cooldown** | 15 min |
| **Trigger** | `net_pl ≤ -1% NLV` |
| **Cap** | Counts toward INFO daily cap |

### 5.3 Drawdown Acceleration

| | |
|---|---|
| **Icon** | 📉 |
| **Title** | ALERT: DRAWDOWN ACCELERATION |
| **Priority** | HIGH |
| **Cooldown** | 15 min |
| **Trigger** | ≥ 0.35% NLV drop within cooldown window |
| **Cap** | Counts toward INFO daily cap |

### 5.4 Profit Milestone

| | |
|---|---|
| **Icon** | 🎯 |
| **Title** | INFO: PROFIT MILESTONE REACHED |
| **Priority** | NORMAL |
| **Trigger** | Every 1% NLV step above session start |
| **Cap** | Counts toward INFO daily cap |

---

## 6. End-of-Week Summary

### 6.1 EOW P/L Summary (`send_eow_summary`, line 1536)

Aggregated from up to 5 daily EOD review artifacts.

```
📆 END-OF-WEEK P/L SUMMARY
Week: {week_key}  |  Mode: {mode}
Weekly Net P/L: ${weekly_pl:+.2f} ({net_return_pct:+.2f}% NLV)
Days Traded: {days_traded}
Trades: {count}  |  Win Rate: {rate:.1f}%
Max Weekly Drawdown: ${max_drawdown:.2f}
Best Day:  {date} ${pl:+.2f}
Worst Day: {date} ${pl:+.2f}
Generated: {YYYY-MM-DD HH:MM} ET
```

Saved atomically to `market_data/weekly/weekly_pnl_summary_{week_key}.json`.

**Priority:** HIGH · **Message type:** SUMMARY

---

## 7. Inbound Command Responses

### 7.1 `/help`

```
Available commands: /status, /halt, /flatten, /resume, /confirm, /help
```

### 7.2 Unknown Command

```
Unknown command: {command}. Use /help.
```

### 7.3 Unauthorized User

```
⛔ Unauthorized. Your user_id ({uid}) is not in the allowed list.
```

### 7.4 `/status`

```
📟 TRADOV STATUS

Bot Running: {YES|NO}
Session Running: {YES|NO}
Queue Size: {n}
Messages Sent: {n}
Kill Lock: {ACTIVE|INACTIVE}
Resume Dual Approval: {ON|OFF}
Resume Failed Gates: {comma-separated | "none"}
Checked At (ET): {YYYY-MM-DD HH:MM:SS}
Correlation: {id}
```

### 7.5 `/halt` — Success

```
🛑 HALT command accepted. KILL_SWITCH emitted.
Correlation: {id}
```

**Priority:** CRITICAL

### 7.6 `/halt` — Failure

```
❌ HALT command failed: could not emit KILL_SWITCH.
Correlation: {id}
```

**Priority:** CRITICAL

### 7.7 Confirmation Request (halt / flatten / resume)

```
⚠️ Confirm {ACTION} within 60s:
/confirm {action} {TOKEN}
{Dual approval required: 2 operators}   ← resume + dual-approval only
Correlation: {id}
```

### 7.8 `/confirm` — Bad Usage

```
Usage: /confirm <halt|flatten|resume> <TOKEN>
```

### 7.9 `/confirm` — Token Expired (resume-specific)

```
Resume confirmation token expired. Reissue /resume.
```

### 7.10 `/confirm` — Token Expired (general)

```
Confirmation token expired. Reissue command.
```

### 7.11 `/confirm` — Wrong Token (resume-specific)

```
Invalid resume confirmation token.
```

### 7.12 `/confirm` — Wrong Token/Action (general)

```
Invalid confirmation token/action.
```

### 7.13 `/confirm` — Duplicate Approval

```
Your resume approval was already recorded.
```

### 7.14 `/confirm` — First of Two Approvals (dual-approval resume)

```
⏳ Resume approval recorded. Waiting for second operator.
Approvals: 1/2
Correlation: {id}
```

### 7.15 `/resume` — Denied

```
⛔ RESUME DENIED
Failed gates: {comma-separated gate names}
Correlation: {id}
```

**Priority:** HIGH

### 7.16 `/resume` — Success

```
▶️ RESUME COMMAND PROCESSED
Kill Lock Cleared: {YES|NO/NA}
Engine Resume Called: {YES|NO}
Approved By: {[user_id, user_id]}
Correlation: {id}
```

**Priority:** HIGH

### 7.17 `/flatten` — Success

```
🧯 FLATTEN COMMAND RESULT
Success: YES
Detail: Supervisor stop(flatten=True) executed
Correlation: {id}
```

**Priority:** CRITICAL

### 7.18 `/flatten` — Failure

```
🧯 FLATTEN COMMAND RESULT
Success: NO
Detail: {reason}
Correlation: {id}
```

**Priority:** HIGH

### 7.19 No Pending Confirmation

```
No pending confirmation found.
```

### 7.20 Unsupported Confirmation Action

```
Unsupported confirmation action: {action}
```

---

## 8. Generic Template Map

`_load_templates()` (line 2403) returns a dictionary of reusable templates for programmatic use:

| Key | Format |
|---|---|
| `trade_open` | `{emoji} TRADE OPENED\n\n{details}` |
| `trade_close` | `{emoji} TRADE CLOSED\n\n{details}` |
| `alert` | `{emoji} {title}\n\n{message}` |
| `error` | `{emoji} ERROR\n\n{error_message}` |
| `summary` | `{emoji} {title}\n\n{content}` |

---

## Appendix: Emoji Dictionary

The bot initializes a standard emoji map (constructor):

| Key | Emoji | Usage |
|---|---|---|
| `bull` | 🐂 | CALL trade opened |
| `bear` | 🐻 | PUT trade opened |
| `chart` | 📊 | Strategy label |
| `pin` | 📌 | Symbol label |
| `trade` | 🔄 | Type label |
| `money` | 💵 | Price/quantity labels |
| `target` | 🎯 | Target price |
| `stop` | 🛑 | Stop loss |
| `warning` | ⚠️ | Warning / max risk |
| `profit` | 💰 | Profitable close header |
| `loss` | 📉 | Losing close header |
| `success` | ✅ | Winner / positive P/L |
| `error` | ❌ | Loser / error / negative |
| `info` | ℹ️ | Info / reason |
| `time` | 🕐 | Timestamps |
| `calendar` | 📅 | Daily summary |
| `robot` | 🤖 | System signature |
| `fire` | 🔥 | Critical severity |
| `alert` | 🔔 | Default alert fallback |

---

## Appendix: Message Routing & Priority

| Priority | Tier | Typical Use |
|---|---|---|
| `CRITICAL` | 1 | Kill switch, stop loss, critical loss, flatten success |
| `HIGH` | 2 | Trade open/close, high loss, drawdown, commands |
| `NORMAL` | 3 | Status, summaries, milestones, help |
| `LOW` | 4 | (reserved, not currently used) |

All messages pass through `_split_message()` (line 1670) which splits at Telegram's 4,096-character limit on newline boundaries.
