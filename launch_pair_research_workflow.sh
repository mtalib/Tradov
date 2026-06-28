#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: expected virtual environment Python at $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$ROOT_DIR/Tradov/TradovQ_Scripts/TradovQ95_PairResearchLauncher.py" "$@"
