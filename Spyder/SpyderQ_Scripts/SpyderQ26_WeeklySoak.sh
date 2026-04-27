#!/usr/bin/env bash
# ===================================================================
# SPYDER - Autonomous Options Trading System v1.0
#
# Series: SpyderQ_Scripts
# Module: SpyderQ26_WeeklySoak.sh
# Purpose: 48-hour paper-soak harness for pre-live gate (v14 O8)
#
# Usage (cron operator wires one of the following; leave commented here):
#   # Friday 23:00 ET kickoff, 48h run, alerts to PagerDuty on failure:
#   # 0 23 * * 5  /opt/spyder/Spyder/SpyderQ_Scripts/SpyderQ26_WeeklySoak.sh
#
# Design notes:
#   * Idempotent: a lock file under /tmp prevents overlapping runs.
#   * Self-contained: exits non-zero if T129 fails, if the process dies
#     mid-soak, or if the heartbeat goes stale.
#   * Observability: streams log + heartbeat deltas to stdout so an operator
#     can tail -f the cron log.
# ===================================================================
set -euo pipefail

SOAK_HOURS="${SOAK_HOURS:-48}"
SOAK_SECONDS=$((SOAK_HOURS * 3600))
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$HOME/.spyder_heartbeat}"
HEARTBEAT_MAX_AGE_SECS="${HEARTBEAT_MAX_AGE_SECS:-60}"
LOCK_FILE="${LOCK_FILE:-/tmp/spyder_weekly_soak.lock}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$REPO_ROOT/logs"
LOG_FILE="$REPO_ROOT/logs/weekly_soak_$(date +%Y%m%dT%H%M%S).log"

acquire_lock() {
    if [ -e "$LOCK_FILE" ]; then
        echo "ERR: lock $LOCK_FILE exists (another soak in flight?)" >&2
        exit 2
    fi
    echo "$$" > "$LOCK_FILE"
    trap "rm -f '$LOCK_FILE'" EXIT
}

run_t129_gate() {
    echo "== T129 regression gate =="
    python -m pytest "$REPO_ROOT/Spyder/SpyderT_Testing/SpyderT129_ProtocolCompliance.py" -q --no-cov
}

start_paper_headless() {
    echo "== launching paper trader (headless) =="
    python "$REPO_ROOT/Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py" --mode paper --headless &
    echo $!
}

check_heartbeat() {
    if [ ! -f "$HEARTBEAT_FILE" ]; then
        echo "ERR: heartbeat missing at $HEARTBEAT_FILE" >&2
        return 1
    fi
    age=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT_FILE") ))
    if [ "$age" -gt "$HEARTBEAT_MAX_AGE_SECS" ]; then
        echo "ERR: heartbeat stale ($age s > $HEARTBEAT_MAX_AGE_SECS s)" >&2
        return 1
    fi
    echo "OK: heartbeat age=${age}s"
}

main() {
    acquire_lock
    {
        echo "Spyder weekly soak: $(date)"
        echo "repo=$REPO_ROOT duration=${SOAK_HOURS}h heartbeat=$HEARTBEAT_FILE"
        run_t129_gate
        pid=$(start_paper_headless)
        echo "paper trader pid=$pid — monitoring for ${SOAK_SECONDS}s"

        deadline=$(( $(date +%s) + SOAK_SECONDS ))
        while [ "$(date +%s)" -lt "$deadline" ]; do
            if ! kill -0 "$pid" 2>/dev/null; then
                echo "ERR: paper trader pid=$pid died" >&2
                exit 3
            fi
            check_heartbeat || { kill "$pid" 2>/dev/null || true; exit 4; }
            sleep 30
        done

        echo "== soak complete — graceful shutdown =="
        kill -TERM "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        echo "Spyder weekly soak: done $(date)"
    } 2>&1 | tee -a "$LOG_FILE"
}

main "$@"
