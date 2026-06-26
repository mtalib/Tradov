# Tradov — Inbound Webhook / Command Receiver (Design)

**Date:** 2026-06-26
**Author:** Mohamed Talib (with Claude)
**Status:** Design — no code yet
**Supersedes:** [`2026-06-26-Algov-Implementaion-Plan.md`](2026-06-26-Algov-Implementaion-Plan.md)
**Inspiration:** OpenAlgo (https://github.com/marketcalls/openalgo) — concept only, no code reused.

---

## 0. Decision & rationale

We are **not** building a separate "Algov" app. After evaluating OpenAlgo, exactly one of
its ideas is worth absorbing into Tradov: an **inbound webhook/command surface** that turns
external signals (e.g. TradingView alerts, scripts) into **risk-checked order proposals**.

Building it inside Tradov is strictly better than a standalone app because:

- **No shared-account coordination risk.** Orders flow *through* Tradov's existing risk
  stack and reconciliation, not around them. A separate app would be a second, blind
  writer on the same Tradier account.
- **The hard infrastructure already exists.** `TradovM08_HealthEndpoint` already runs an
  embedded stdlib `http.server` in a thread alongside the Qt GUI — the "web surface next
  to the event loop" problem is solved in-tree.
- **No second codebase / no `algotrade-core` extraction** needed just to share the engine.

Everything else in OpenAlgo is either a wrong fit (Flow visual builder, multi-broker
abstraction, single-user-irrelevant security stack, its own analytics) or already present
in Tradov (paper mode = TradovBox, dual-approval ≈ Telegram `RESUME_DUAL_APPROVAL` +
arming/readiness gates, outbound webhooks = `TradovJ03_WebhookNotifier`, metrics =
`TradovB15_PrometheusMetrics`, provider abstraction = DataFeed ABC).

## 1. Scope

**In scope (MVP):**
- A localhost HTTP endpoint that accepts authenticated POST signals.
- Translation of a signal into an internal **order proposal**.
- Routing the proposal through the existing **risk gates** and **arming/readiness** checks.
- Handoff to `TradovB02_OrderManager` (which already targets Tradier live or TradovBox paper).
- Audit of every inbound signal and its disposition.

**Out of scope:** any new execution/data logic (reuse Tradov's), a UI, multi-broker
support, public/internet exposure.

## 2. What already exists in Tradov (reuse, don't rebuild)

| Concern | Existing module | Role here |
|---|---|---|
| Embedded HTTP server | `TradovM08_HealthEndpoint` (stdlib `http.server`, threaded) | Pattern to extend with authenticated POST routes |
| Order execution | `TradovB02_OrderManager` → `TradovB40_TradierClient` | Final execution (live or TradovBox paper) |
| Paper account | `TradovR02_PaperEngine` (TradovBox) | Default destination in paper mode |
| Risk | `TradovE01_RiskManager`, `TradovE26_PairRiskManager`, `E02` sizing, `E03` stops, `E04` drawdown | Validate/clamp/reject proposals |
| Arming / readiness | `G48_TradingArmingPresenter`, `G57_StartTradingPrecheckPresenter`, `G71_ReadinessGateDecisionHelper` | Gate whether *any* order may flow |
| Manual approval | Telegram dual-approval (`TELEGRAM_RESUME_DUAL_APPROVAL`, allowed user IDs) | Approve external proposals before fill |
| Secrets | `TradovU46_SecretsManager` | Store/verify the webhook shared secret |
| Persistence / audit | `TradovH05_TradingSessionDB` | Record inbound signals + dispositions |
| Message types | `TradovZ02_MessageProtocol` | Reuse/extend for the signal envelope |

## 3. Proposed placement

A new module in **`TradovZ_Communication`** (inbound comms), e.g.
`TradovZ10_InboundSignalReceiver.py`, modeled on `TradovM08_HealthEndpoint`.
Rationale: Z is already the communication series and holds `MessageProtocol`; M is
monitoring/health (read-only probes). Keep the inbound *command* surface separate from
read-only health.

```
External signal (TradingView / curl)
        │ POST /signal  (localhost, shared-secret auth)
        ▼
TradovZ10_InboundSignalReceiver         ← new (HTTP server, modeled on M08)
        │ parse + validate -> SignalEnvelope (extends Z02_MessageProtocol)
        ▼
Order-proposal builder                  ← maps signal -> internal order request
        │
        ▼
Arming / readiness gate  ───reject──▶  audit + 4xx response
        │ (armed & ready)
        ▼
Risk stack  E01 / E26 / E02 / E03 / E04 ───reject/clamp──▶ audit + response
        │ (approved, sized)
        ▼
[optional] dual-approval (Telegram)     ← for live; bypass in paper
        │ (approved)
        ▼
TradovB02_OrderManager ──▶ TradovBox paper  (default)
                       └─▶ Tradier live      (only when live + confirmed)
        │
        ▼
TradovH05_TradingSessionDB  (audit: signal, decision, order id, fill)
```

## 4. API surface (MVP)

- `POST /signal/{secret}` — submit a trading signal. Returns a disposition
  (`accepted` / `proposed` / `rejected` with reason) and, when executed, the order id.
- `GET /healthz` — liveness (or reuse the existing M08 endpoint).

**Signal envelope (JSON):**
```json
{
  "source": "tradingview",
  "strategy": "manual",
  "symbol": "SPY",
  "side": "buy",
  "quantity": 10,            // optional; if omitted, E02 PositionSizer decides
  "order_type": "market",    // market | limit | stop
  "limit_price": null,
  "stop_price": null,
  "client_tag": "tv-12345"   // idempotency key -> Tradier tag (≤24h dedup)
}
```

Pair/stat-arb signals (Tradov's core) can extend this with a `legs[]` form routed to the
pair executor + `E26_PairRiskManager`; single-leg is the MVP.

## 5. Safety model

- **Bind localhost only** (`127.0.0.1`); never expose to the internet directly.
- **Shared-secret auth** via `TradovU46_SecretsManager`; constant-time compare; secret in
  the path or an `X-Tradov-Signal-Key` header.
- **Paper by default.** Live execution requires the existing `LIVE_TRADING_CONFIRMED` /
  `REQUIRE_LIVE_CONFIRMATION` flags AND passes through the same gates as any Tradov order.
- **Proposals, not fills.** External signals are *proposals* that enter the normal
  readiness + risk pipeline; for live, require dual-approval (reuse Telegram flow).
- **Idempotency.** `client_tag` → Tradier idempotency tag to prevent duplicate fills on
  retries.
- **Full audit.** Every signal + disposition persisted to `TradovH05_TradingSessionDB`.
- **Threading.** Receiver runs in its own daemon thread (like M08); all handoffs to
  OrderManager/risk go through the existing thread-safe entry points — no new shared state.

## 5a. Headless-gate feasibility — TRACE RESULT (2026-06-26) ✅ CONFIRMED

The design's main open question — *"can the readiness/arming decision run headless,
outside the Qt G-series?"* — was traced through the code. **Answer: yes, with only a
small, bounded extraction.**

Findings:

- **The readiness evaluation core is already pure.**
  `_evaluate_trading_readiness_snapshot()` is a one-line delegate to the module function
  `build_trading_readiness_evaluation(snapshot)` — snapshot dict in → `{decision, reasons,
  …}` out, **no Qt**. This is the actual GO/NO brain and it is reusable as-is.
- **The decision/cache/shape helpers are pure** (no Qt imports): `G46`, `G54`, `G55`,
  `G56`, `G57`, `G60`, `G61`, `G71` (`build_start_trading_readiness_gate_decision_plan`),
  and `build_readiness_cache_decision_plan`. They live in the `G_GUI` namespace but are
  plain functions over dicts/dataclasses.
- **The only GUI coupling is snapshot *assembly*.**
  `G05._build_preopen_check_snapshot()` reads a few values from Qt widgets (e.g.
  `self.data_status_label.text()`) alongside non-Qt state it already holds
  (`self.api_connected`, `self.mkt_data_connected`, `self.event_clock_state`,
  `self._session_supervisor`). The widget reads mirror state that originates in the
  session/connection layer — so a headless snapshot builder can source the same values
  directly from `R12_SessionSupervisor` + connection state instead of from labels.
- **Headless readiness infra already exists elsewhere**: `Q91_LiveReadiness`
  (pre-flight safety-test gate, pure CLI), `M08_HealthEndpoint.register_ready_gate()`
  (runtime gate registry served at `/ready`), and
  `A03.validate_autonomous_readiness_config()` (config-level readiness).

**Conclusion:** No refactor of the 10.6k-LOC dashboard is required. The headless path is:
build a snapshot from session/connection sources → call the existing pure
`build_trading_readiness_evaluation()` → apply the pure decision/cache helpers. The only
new code is a **headless snapshot builder** (a `ReadinessGateCoordinator`) that both the
receiver and, optionally later, the dashboard can share. This de-risks the whole design.

## 6. Risks & open questions

- **New error/attack surface on a live account.** Mitigated by localhost + secret +
  paper-default + dual-approval, but it is the main thing to get right.
- **Snapshot-builder extraction (small).** The one piece of GUI coupling is
  `_build_preopen_check_snapshot` reading a couple of Qt label values; the headless
  coordinator must re-source those from `R12_SessionSupervisor` / connection state.
  Bounded and low-risk (see §5a).
- **Sizing authority.** Decide whether external signals may specify `quantity` or must
  always defer to `E02_PositionSizer`. Recommendation: allow a requested size but let risk
  clamp/reject it.
- **Pair signals.** Single-leg MVP first; pair-leg routing through `B02_PairOrderExecutor`
  + `E26` is a follow-up.

## 7. Phased plan

1. ~~**Gate accessibility check.**~~ ✅ Done (see §5a) — readiness runs headless via the
   pure `build_trading_readiness_evaluation()`; only the snapshot builder needs lifting.
2. ~~**`ReadinessGateCoordinator` (headless).**~~ ✅ Done — `TradovR13_ReadinessGateCoordinator`
   reuses the pure G63/G67/G70 helpers; snapshot scalars via `ReadinessSnapshotInputs`;
   connection probe injected. Tests: T197 (11). Verified: imports load no Qt.
3. ~~**Receiver skeleton.**~~ ✅ Done — `TradovZ10_InboundSignalReceiver` (threaded
   `http.server`, `POST /signal/{secret}`, constant-time secret, self-contained
   `SignalEnvelope`, audit-on-receive, injectable handler). Plus
   `TradovC30_ConnectionProbe` (headless `check_api_connection`). Tests: T198, T199.
4. ~~**Proposal → paper.**~~ ✅ Done — `TradovZ11_SignalOrderHandler` runs envelope →
   readiness gate (R13+C30) → risk (`E01.check_trade`, injected) → **TradovBox paper**
   (R02 PaperEngine). Risk clamps/sizes quantity; fail-closed. Tests: T200 (incl.
   end-to-end POST). No live auto-fire.
5. **Live path** (pending). Currently blocked unless `live_enabled`, and even then
   returned as `pending_approval` (no auto-fire). To do: dual-approval loop (Telegram),
   idempotency tags, persist audit to `H05_TradingSessionDB`.
6. **Pair-leg support** (optional): `legs[]` → `B02_PairOrderExecutor` + `E26`.
7. **Cleanup**: point `G18.check_api_connection` at `C30` to remove the temporary
   probe duplication; wire `SignalOrderHandler` into `R12_SessionSupervisor` startup.

## 8. Status & next step

Phases 1–4 complete (50 tests passing, all headless — no Qt). The inbound pipeline is
functional end-to-end in **paper mode**: `POST /signal/{secret}` → gate → risk →
TradovBox fill.

Next: **Phase 5 — live path**. Wire the dual-approval loop and idempotency, persist audit
to `H05_TradingSessionDB`, and bootstrap the receiver+handler from `R12_SessionSupervisor`
(passing the session's configured `RiskManager.check_trade` as the injected risk check).
