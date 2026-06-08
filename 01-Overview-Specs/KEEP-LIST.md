# 01-Overview-Specs Keep List (Canonical)

Last Updated: 2026-05-10
Purpose: Define the canonical documents to keep in this folder and reduce drift and duplication.

## Naming Convention

Use two document classes:

1. Evergreen core docs (no date prefix)
- Use for continuously maintained references.
- Examples: architecture, glossary, roadmap, operator manuals.

2. Dated snapshots (`YYYY-MM-DD-` prefix)
- Use for point-in-time reports, launch checklists, runbooks, and milestone specs.

## Canonical Keep Set

### Evergreen Core

- `Architecture.md`
- `Glossary.md`
- `Roadmap.md`
- `Tradov-Developer-Manual.md`
- `Trading-Decision-One-Page.md`
- `Tradov-Architecture.json`

### Active Dated Specs and Reports

- `2026-05-10-TRADING_DECISION_WORKFLOW-FULL-v19.md`
- `2026-05-08-Anthropic-Repo-Adoption-Implementation-Plan.md`
- `2026-05-05-Market-Data.md`
- `2026-05-04-Telegram-Incident-Response-Runbook.md`
- `2026-05-02-Autonomous-Decision-Contract-Overview.md`
- `2026-05-01-Strategy-Reference-Chart.md`
- `2026-04-30-TradingAgents-Ideas.md`
- `2026-04-29-Real-Time-Simulation-Report.md`
- `2026-04-25-Live-Launch-Checklist.md`

### Historical but Retained (Context)

- `2026-05-10-TRADING_DECISION_WORKFLOW-FULL-v18.md`
- `2026-05-09-TRADING_DECISION_WORKFLOW-FULL-v17.md`
- `2026-05-05-24x5-Autonomous-Operations-Board-Memo.md`
- `2026-05-05-24x5-Autonomous-Operations-End-to-End-Completion-Report.md`
- `2026-05-05-24x5-Autonomous-Operations-Executive-Completion-Brief.md`

### Archived by Allowlist

- `2026-05-05-24x5-Autonomous-Operations-Board-Memo-Slide-Format.md` moved to `12-Archive/Overview-Specs-Pruned-2026-05-09/`

## Archive Policy

When content is superseded, move it to `12-Archive/` using a dated batch folder. Avoid hard-deleting historical decision records unless they are duplicated elsewhere and validated.

## Notes

- The full trading decision workflow source of truth in this folder is `2026-05-10-TRADING_DECISION_WORKFLOW-FULL-v19.md`.
- Keep one full workflow source of truth in this folder at a time; older full versions should be treated as historical context and moved to `12-Archive/` during the next pruning pass.