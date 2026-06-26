# Algov — Implementation Plan

> ⚠️ **SUPERSEDED (2026-06-26).** Decision reversed: Algov will **not** be built as a
> separate app. The one transferable OpenAlgo idea (an inbound webhook/command surface)
> is being folded into Tradov instead — it routes through Tradov's existing risk stack
> and reuses the embedded HTTP server pattern, avoiding a second codebase and the
> shared-account coordination risk. The standalone Algov scaffold was deleted.
> **Current direction:** see
> [`2026-06-26-Tradov-Inbound-Webhook-Receiver-Design.md`](2026-06-26-Tradov-Inbound-Webhook-Receiver-Design.md).
> This doc is retained only for the OpenAlgo evaluation, licensing analysis, and
> engine-reuse findings.

**Date:** 2026-06-26
**Author:** Mohamed Talib (with Claude)
**Status:** Superseded — see banner above
**Reference repo:** https://github.com/marketcalls/openalgo (AGPL-3.0)

---

## 0. Decisions locked in

1. **Reuse mode: inspiration-only.** OpenAlgo is read for *architecture and API shape*
   only. No OpenAlgo source is copied or forked into Algov.
2. **Distribution: private use only.** Algov is for the operator's own use on a local
   Ubuntu machine; it will not be resold or offered as a network service to third parties.
3. **MVP target: local Ubuntu machine**, headless API server first (webhook → order),
   GUI deferred.
4. **Paper trading: AlgovBox (internal), not Tradier sandbox.** Algov reuses Tradov's
   internal paper engine (`TradovR02_PaperEngine` + harness/monitor) — live market data,
   local fills/accounting, commission + slippage simulation. The Tradov-side name is
   *TradovBox*; the Algov instance is *AlgovBox*.
5. **Eventual GUI: PySide6 desktop, not web.** Algov is single-user/local, so a native
   desktop shell fits better than a React/browser stack (see §3 and §9).
6. **Doc location:** `05-Research/` (this file).

### Licensing note (why inspiration-only still makes sense)
AGPL-3.0 obligations (source disclosure) trigger only on **distribution** or on
**serving the software over a network to others**. Pure private/personal use of AGPL code
imposes no disclosure obligation. So even if OpenAlgo code were used, private use alone
would be fine. We still choose inspiration-only because:
- OpenAlgo's broker adapters target **Indian brokers** — useless for our **Tradier/US**
  use case, so there is little to copy anyway.
- Keeping Algov clean of AGPL code preserves the option to ever share/sell later without
  a relicensing problem.

---

## 1. What OpenAlgo is (and what transfers)

A self-hosted algo-trading **platform** for 30+ Indian brokers:
- **Unified Broker API** (`/api/v1/`) normalizing many brokers behind one REST interface
- **Python strategy host** (in-browser editor + scheduler)
- **Flow visual builder** (drag-and-drop, React Flow)
- **Options analytics suite** + **sandbox/paper mode** (virtual capital)
- Stack: Flask 3 + SQLAlchemy 2 + Flask-SocketIO + ZeroMQ; React 19 / Vite / Tailwind /
  shadcn; SQLite + DuckDB. **License: AGPL-3.0.**

**Transferable ideas (the blueprint):**
- A **unified broker-abstraction interface** (one API, swappable brokers).
- A clean **REST + WebSocket API surface** for orders/positions/quotes.
- A **webhook / strategy host** (e.g. TradingView alert → order) — highest value, lowest effort.
- A **sandbox/paper mode** with virtual capital.

**Not transferable:** the broker adapters themselves (India-specific), and we are not
bound to Flask/React just because OpenAlgo chose them.

---

## 2. What Algov reuses from Tradov (the engine)

Tradov already contains a mature, tested Tradier + market-data engine (~15k LOC):

| Module | LOC | Role |
|---|---|---|
| `TradovB_Broker/TradovB40_TradierClient.py` | 3,769 | Tradier REST + SSE/WS streaming, OCC option symbols, Greeks, multileg/spreads, sandbox+live, rate limiting, circuit breaker |
| `TradovB_Broker/TradovB02_OrderManager.py` | 2,546 | Order tracking, state persistence, fill updates |
| `TradovB_Broker/TradovB00_OrderTypes.py` | 951 | Order/enum types |
| `TradovB_Broker/TradovB04_AccountManager.py` | 1,344 | Balances, positions, account |
| `TradovB_Broker/TradovB03_PositionTracker.py` | 769 | Position tracking |
| `TradovC_MarketData/TradovC01_DataFeed.py` | 1,370 | `MarketDataProvider` ABC + orchestration |
| `TradovC_MarketData/TradovC16_MarketDataCache.py` | 920 | Quote cache |
| `TradovC_MarketData/TradovC02_HistoricalData.py` | 937 | Historical data + Databento |
| `TradovA_Core/TradovA03_Configuration.py` | 2,105 | Config |
| `TradovR_Runtime/TradovR02_PaperEngine.py` | — | **AlgovBox** core: paper fills, commission/slippage sim on live data |
| `TradovR_Runtime/TradovR06_PaperTradingHarness.py` | — | Paper harness (wiring) |
| `TradovR_Runtime/TradovR03_PaperMonitor.py` | — | Paper monitoring |

The paper engine depends only on `TradierClient` for market data — it does **not** import
the GUI/PySide6 — so it is reusable headless as AlgovBox.

The hard part — talking to Tradier correctly — is done. Algov's job is to put a clean,
broker-agnostic API in front of it.

---

## 3. Target architecture (MVP, local Ubuntu)

```
   TradingView alert / curl / scripts
                 │  HTTP (localhost)
   ┌─────────────▼──────────────────────────────────┐
   │  Algov API server (FastAPI, uvicorn)            │
   │   /api/v1/  orders · positions · quotes · hist  │
   │   /webhook  TradingView → order   [MVP core]    │
   │   API-key auth · AlgovBox paper mode · audit log│
   └───────────────┬─────────────────┬───────────────┘
                   │                 │
        ┌──────────▼───────┐ ┌───────▼──────────┐
        │ BrokerAdapter ABC│ │ MarketData ABC   │   ← Algov-owned interfaces
        │  TradierAdapter  │ │ TradierMDAdapter │
        └──────────┬───────┘ └───────┬──────────┘
                   │ wraps           │ wraps
        ┌──────────▼─────────────────▼──────────┐
        │  Tradov engine (imported as a package) │
        │  TradierClient · OrderManager · DataFeed│
        │  PaperEngine (→ AlgovBox)              │
        └─────────────────────────────────────────┘

Order routing: the `BrokerAdapter` sends to **AlgovBox** (paper engine) by default, or to
the live Tradier path only when an explicit live flag is set.
```

**Stack choice — FastAPI + uvicorn** (not Flask): Tradov's client is already async
(`aiohttp`, `get_running_loop()`); FastAPI matches it natively, gives typed
request/response schemas, and auto-generates OpenAPI docs at `/docs`. SQLite for the
local audit/order log. No ZeroMQ/DuckDB/React needed for MVP.

**Runtime:** single `uvicorn` process bound to `127.0.0.1` on the Ubuntu box; optional
`systemd --user` unit so it survives logout. No external exposure.

---

## 4. Reuse strategy (how Algov consumes the engine)

Staged, to avoid a big refactor before the interface is proven:

1. **Phase 1 — Adapter-wrap (start here).** Algov defines its *own* `BrokerAdapter` and
   `MarketDataProvider` interfaces and a `TradierAdapter` that calls Tradov's
   `TradierClient`. Algov imports Tradov as a dependency (editable install of the local
   repo, or `PYTHONPATH`). Fastest path; keeps Algov's API broker-agnostic from day one.
2. **Phase 4 — Extract `algotrade-core`.** Once the interface is stable, pull
   B40/B02/B00/B04 + C01/C16/C02 into a standalone package consumed by *both* Tradov and
   Algov. Removes `Tradov*` naming coupling and fixes dependency direction.
3. **Avoid: copy-and-diverge.** Don't fork the Tradier client into Algov — you'd maintain
   two.

---

## 5. Phased plan

### Phase 0 — Scaffolding (small)
- New repo/dir `Algov/` with its own license (operator's choice; not AGPL).
- FastAPI skeleton + `pyproject.toml`; `.env` for Tradier sandbox token + account id.
- Make Tradov importable from Algov (editable install / `PYTHONPATH`).
- Define Algov-owned interfaces: `BrokerAdapter`, `MarketDataProvider` (see §6).

### Phase 1 — MVP: headless execution API
- `TradierAdapter` wrapping `TradovB40_TradierClient` (+ `OrderManager`).
- Wire **AlgovBox** (reuse `TradovR02_PaperEngine` + harness/monitor) as the default
  order destination; live Tradier only behind an explicit flag.
- `/api/v1/` endpoints: place / cancel / modify order, list positions, balances,
  quotes, historical bars.
- **Paper mode default ON** (routes to AlgovBox) for safety.
- API-key auth (single local key in `.env`), request audit log to SQLite.
- `/webhook` endpoint: validates a shared secret, maps a TradingView alert payload to an
  order. **This is the MVP's headline feature.**
- Smoke test end-to-end through **AlgovBox** (live data, simulated fills).

### Phase 2 — Streaming + paper polish
- WebSocket fan-out for live quotes + order fills (reuse B40's SSE/WS streaming).
- AlgovBox polish: PnL tracking + paper account state persisted to SQLite.

### Phase 3 — GUI (optional, deferred): PySide6 desktop
- Algov is single-user/local → a **PySide6 desktop shell** fits better than a web stack.
- Build Algov's **own thin shell** that talks to the FastAPI core; reuse only the
  **generic** Tradov widgets — `TradovG29_ChartWidgetPlotly`, `G30_PlotlyDataBridge`,
  `G31_PlotlyTemplates`, `G13_EnhancedWidgets`.
- **Do NOT** reuse the domain-coupled dashboards (`G05_TradingDashboard` ~10.6k LOC,
  `G60_PairTradingWidgets`, `G20_DashboardBuilder`) — they pull in Tradov's pair-trading
  session model.
- OpenAlgo's web UI / Flow visual builder are out of scope (multi-user-server rationale
  doesn't apply here).

### Phase 4 — Hardening / extraction
- Extract `algotrade-core`; flip both Tradov and Algov to consume it.
- Add a second broker adapter (even a stub) to validate the abstraction.

---

## 6. Interface sketches (Phase 0/1 starting point)

```python
# algov/brokers/base.py
from abc import ABC, abstractmethod
from typing import Any

class BrokerAdapter(ABC):
    @abstractmethod
    async def place_order(self, req: "OrderRequest") -> "OrderResult": ...
    @abstractmethod
    async def cancel_order(self, order_id: str) -> "OrderResult": ...
    @abstractmethod
    async def modify_order(self, order_id: str, changes: dict[str, Any]) -> "OrderResult": ...
    @abstractmethod
    async def get_positions(self) -> list["Position"]: ...
    @abstractmethod
    async def get_balances(self) -> "Balances": ...

# algov/marketdata/base.py
class MarketDataProvider(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str) -> "Quote": ...
    @abstractmethod
    async def get_history(self, symbol: str, interval: str, start, end) -> list["Bar"]: ...
    @abstractmethod
    async def stream_quotes(self, symbols: list[str]): ...  # async iterator
```

`TradierAdapter` implements `BrokerAdapter` by delegating to
`TradovB40_TradierClient` / `TradovB02_OrderManager`. Algov defines its own thin
DTOs (`OrderRequest`, `OrderResult`, `Position`, `Quote`, `Bar`) so the API contract is
independent of Tradov's internal types.

---

## 7. Risks & open items

- **Dependency direction (Algov → Tradov).** Acceptable for MVP; must be resolved by the
  Phase 4 `algotrade-core` extraction before Algov is anything more than personal.
- **Tradov coupling.** Tradov modules lean on `TradovA03_Configuration` and `Tradov*`
  naming; the adapter layer (Phase 1) is what insulates Algov from that.
- **Safety.** Default to **AlgovBox paper mode**; require an explicit, separate flag to
  route live; bind the server to `127.0.0.1` only; webhook requires a shared secret.
- **AlgovBox reuse coupling.** `TradovR02_PaperEngine` may lean on Tradov runtime/session
  helpers — verify its dependency surface during Phase 1 and wrap (don't fork) it.
- **Scope creep.** OpenAlgo's Flow builder / 12 analytics tools / multi-broker matrix are
  out of scope for a private MVP — resist pulling them in early.

---

## 8. Immediate next steps

1. Create `Algov/` skeleton (FastAPI + pyproject) and the two ABCs in §6.
2. Implement `TradierAdapter` against Tradov's `TradierClient`; wire AlgovBox
   (`TradovR02_PaperEngine`) as default destination.
3. Stand up `/api/v1/orders` (place/cancel) + `/webhook`, end-to-end through AlgovBox.
4. Add API-key auth + SQLite audit log.
5. Demo: TradingView (or `curl`) alert → AlgovBox paper fill.
