#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/adam/Projects/Spyder"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
ENTRYPOINT="$PROJECT_ROOT/Spyder/SpyderA_Core/SpyderA01_Main.py"
LOG_DIR="$PROJECT_ROOT/logs/launcher"
LOG_FILE="$LOG_DIR/spyder-desktop-launch.log"

mkdir -p "$LOG_DIR"

{
  echo "============================================================"
  echo "[$(date -Iseconds)] Desktop launcher invoked"
  echo "PWD before cd: $PWD"
} >> "$LOG_FILE"

cd "$PROJECT_ROOT"

if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
  echo "[$(date -Iseconds)] Loaded .env" >> "$LOG_FILE"
else
  echo "[$(date -Iseconds)] WARNING: .env not found" >> "$LOG_FILE"
fi

# Desktop launcher defaults:
# - Paper SessionSupervisor autostart is enabled so the desktop launch resumes
#   the expected paper automation path by default.
# - Deferred GUI autostart remains enabled for the dashboard handoff path.
# - Keep it paper-only unless user explicitly overrides in environment.
export SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR="${SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR:-1}"
export SPYDER_A01_ALLOW_GUI_AUTOSTART="${SPYDER_A01_ALLOW_GUI_AUTOSTART:-1}"
export SPYDER_A01_AUTOSTART_MODE="${SPYDER_A01_AUTOSTART_MODE:-paper}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[$(date -Iseconds)] ERROR: Python binary missing: $PYTHON_BIN" >> "$LOG_FILE"
  exit 1
fi

if [[ ! -f "$ENTRYPOINT" ]]; then
  echo "[$(date -Iseconds)] ERROR: Entrypoint missing: $ENTRYPOINT" >> "$LOG_FILE"
  exit 1
fi

echo "[$(date -Iseconds)] Starting: $PYTHON_BIN $ENTRYPOINT" >> "$LOG_FILE"

# Append both stdout and stderr from Spyder startup/runtime to the launcher log.
exec "$PYTHON_BIN" "$ENTRYPOINT" >> "$LOG_FILE" 2>&1
