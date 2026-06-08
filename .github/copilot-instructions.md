# Tradov Agent Instructions

## Safety-Critical Defaults

- This repository can affect real trades. Default every change, script, and validation step to paper-safe behavior.
- Never hardcode credentials or tokens. Use `.env`-backed configuration only.
- Do not enable live trading, change defaults toward live, or run live-only flows without explicit user confirmation.
- Current policy is live Tradier connectivity plus local paper execution. Treat legacy sandbox or paper Tradier routing as obsolete unless the current code under test explicitly supports it.

## How To Work

- Activate the project environment before Python tooling: `source .venv/bin/activate`.
- Install in editable mode when imports or entry points matter: `pip install -e .`.
- Prefer the owning module inside the existing A-Z series instead of adding duplicate helpers or new top-level entry points.
- Keep edits narrow. After the first substantive change, run the smallest relevant validation command before widening scope.
- If this environment exposes repository memories, check relevant `/memories/repo` notes before changing a module with known gotchas.

## Architecture Anchors

- Entry point: `Tradov/TradovA_Core/TradovA01_Main.py`
- Broker execution: `Tradov/TradovB_Broker/TradovB40_TradierClient.py`
- Market data: `Tradov/TradovC_MarketData/TradovC27_MassiveClient.py` and `Tradov/TradovC_MarketData/TradovC29_DataProviderRouter.py`
- Strategy and risk path: `Tradov/TradovD_Strategies` -> `Tradov/TradovE_Risk` -> `Tradov/TradovR_Runtime`
- GUI anchor: `Tradov/TradovG_GUI/TradovG05_TradingDashboard.py`
- Tests and fixtures: `Tradov/TradovT_Testing` and `conftest.py`

## Conventions

- Use `TradovLogger`; do not add `print()` to production modules.
- Add type hints for new or changed APIs. Use Google-style docstrings for new public classes and functions.
- Preserve the naming pattern `TradovXNN_Name.py` and the responsibility boundaries of each series.
- Reuse existing retry, rate-limiter, circuit-breaker, and validation utilities instead of adding parallel ad hoc implementations.
- When docs conflict, trust the current code path and current workflow or policy docs. Some older overview material still references IBKR or previous broker and data integrations.

## Commands

- Setup: `source .venv/bin/activate && pip install -e .`
- Dependencies: `pip install -r requirements.txt` plus optional `requirements-gui.txt`, `requirements-ai.txt`, or other extras only when the touched area needs them.
- Targeted tests: `pytest Tradov/TradovT_Testing/<target>`
- Full test suite: `pytest`
- Lint touched paths: `ruff check <paths>`
- Local single-regression check without the coverage gate: `pytest <target> --no-cov`

## References

- [README](../README.md)
- [pytest.ini](../pytest.ini)
- [ruff.toml](../ruff.toml)
- [Trading Decision Workflow v34](../01-Overview-Specs/2026-05-18-TRADING_DECISION_WORKFLOW-FULL-v34.md)
- [Rate Limiting and Circuit Breakers](../02-Standards-Instructions/RATE_LIMITING_CIRCUIT_BREAKER_GUIDE.md)
- [Threading Guide](../02-Standards-Instructions/THREADING_GUIDE.md)
- [Architecture](../01-Overview-Specs/Architecture.md) and [Developer Manual](../01-Overview-Specs/Tradov-Developer-Manual.md) for inventory and history; verify current broker and mode behavior against code when those docs conflict with runtime policy.