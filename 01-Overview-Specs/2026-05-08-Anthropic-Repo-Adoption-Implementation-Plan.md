# Anthropic Financial-Services Pattern Adoption Plan for Spyder

Last Updated: 2026-05-08
Status: Implementation Plan (paper-first, live-safe)
Scope: Adopt high-value agent safety/orchestration patterns from anthropics/financial-services into Spyder without replacing existing guardrails.

## 1) What We Are Adopting

The target patterns to adopt are:

1. Typed agent handoff contracts with schema validation.
2. Role/tier isolation and topic-level permissions for agent actions.
3. Explicit human sign-off checkpoints for high-risk decisions before live execution.
4. Dry-run contract linting and startup validation before activation.
5. Strong audit artifacts for replay, debugging, and post-trade review.

## 2) Existing Spyder Guardrails to Preserve

Spyder already has critical controls that we should extend, not replace:

- D31 pre-risk trust gating and regime policy checks.
  - Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py (subscribe/entry gates/regime policy)
- F09 event-clock and strategy allowlist policy checks.
  - Spyder/SpyderF_Analysis/SpyderF09_EntryFilters.py
- E01 Y03 veto integration with observe-only mode option.
  - Spyder/SpyderE_Risk/SpyderE01_RiskManager.py
- Live-mode environment confirmation gate.
  - Spyder/SpyderQ_Scripts/SpyderQ02_ValidateEnv.py
- Live submit fail-closed if no fill reconciler attached.
  - Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py
- Regime policy load and validation path.
  - Spyder/SpyderA_Core/SpyderA03_Configuration.py
  - config/regime_policy.json

## 3) Current Gaps to Close

1. Agent bus API contract drift: BaseAutoAgent publishes a Message object into an async bus API that expects topic/payload/sender args.
   - Spyder/SpyderY_AutoAgents/SpyderY00_BaseAutoAgent.py
   - Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py
2. No single canonical handoff schema for agent-to-agent and agent-to-orchestrator decision payloads.
3. No centralized role/topic permission matrix for agent actions.
4. Human escalation exists (Y08 Telegram) but no first-class approval token contract at execution boundaries.
5. No dedicated startup lint command that validates agent contracts/policies before enabling autonomous mode.

## 4) Phased Rollout (Paper-First)

### Phase 0 - Transport Compatibility and Stability (first)

Goal: Ensure agent messaging plumbing is deterministic before adding policy enforcement.

Primary files:

- Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py
- Spyder/SpyderY_AutoAgents/SpyderY00_BaseAutoAgent.py
- Spyder/SpyderE_Risk/SpyderE12_PortfolioVaR.py
- Spyder/SpyderP_PortfolioMgmt/SpyderP05_MultiStrategyAllocator.py
- Spyder/SpyderP_PortfolioMgmt/SpyderP06_StrategyRotation.py

Changes:

1. Add backward-compatible publish adapters in I06:
   - publish_message(message: Message) for object-based call sites.
   - publish_sync(...) wrapper for sync contexts that need fire-and-forget semantics.
2. Keep async publish(...) as canonical API.
3. Update Y00 publish() to call a supported bus method and avoid silent coroutine non-execution.
4. Add explicit telemetry when legacy publish adapters are used.

Exit criteria:

- No direct call path drops messages due to async/sync signature mismatch.
- Existing Y/X agent publish paths execute in paper mode without warnings/exceptions.

### Phase 1 - Handoff Contracts in Shadow Mode

Goal: Introduce strict message shape definitions without yet blocking flow.

Primary files:

- Spyder/SpyderZ_Communication/SpyderZ02_MessageProtocol.py
- Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderY_AutoAgents/SpyderY08_MetaOrchestratorAgent.py
- Spyder/SpyderX_Agents/SpyderX14_OrchestratorAgent.py

Changes:

1. Add schemas:
   - AGENT_HANDOFF_V1
   - AGENT_DECISION_V1
   - AGENT_ESCALATION_V1
2. Attach schema validation to bus publish/consume paths for agent topics in shadow mode.
3. Have Y08 and X14 emit normalized handoff envelopes while retaining legacy fields.
4. D31 parses and logs schema errors as advisory-only during this phase.

Exit criteria:

- 100% of agent decisions in paper session have a valid V1 envelope or a logged shadow violation reason.
- No execution behavior change from Phase 0.

### Phase 2 - Paper-Mode Enforcement (Role and Topic Policy)

Goal: Enforce trust tiers and permissions only in paper mode first.

Primary files:

- Spyder/SpyderA_Core/SpyderA03_Configuration.py
- Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py
- Spyder/SpyderY_AutoAgents/SpyderY00_BaseAutoAgent.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- config/agent_handoff_policy.json (new)

Changes:

1. Add policy file loader in A03 similar to regime_policy loading.
2. Define role tiers (observe, advisory, execution-advisory, execution-authorized).
3. Enforce sender-role to topic/action allowlists in I06.
4. D31 only accepts execution-relevant handoffs from approved roles/topics.

Exit criteria:

- Paper-mode rejects unauthorized handoffs with explicit reason codes.
- Authorized paths remain functional and auditable.

### Phase 3 - Approval Contract (Paper Enforced, Live Disabled)

Goal: Add explicit sign-off contract before execution-intent handoffs can pass.

Primary files:

- Spyder/SpyderX_Agents/SpyderX14_OrchestratorAgent.py
- Spyder/SpyderY_AutoAgents/SpyderY08_MetaOrchestratorAgent.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderE_Risk/SpyderE01_RiskManager.py
- Spyder/SpyderQ_Scripts/SpyderQ02_ValidateEnv.py

Changes:

1. Add approval_required flag and approval_token_ref fields to execution-intent envelopes.
2. Y08 escalation path issues token references after operator approval event (paper simulation allowed).
3. D31 pre-risk gate requires a valid token reference for execution-intent actions.
4. E01 records veto/approval interactions in risk reasons for auditability.
5. Q02 adds environment checks for approval-token settings whenever live mode is requested.

Exit criteria:

- In paper mode, execution-intent actions without approval are consistently dropped with reason.
- Approved paper actions continue through existing F09/E01/R04 path.

### Phase 4 - Limited Live Canary

Goal: Enable contract enforcement in tightly bounded live windows.

Primary files:

- Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py
- Spyder/SpyderQ_Scripts/SpyderQ02_ValidateEnv.py
- Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
- Spyder/SpyderE_Risk/SpyderE01_RiskManager.py

Changes:

1. Require valid approval token metadata on agent-originated live orders at R04 broker submit boundary.
2. Keep existing fail-closed reconciler requirement and live env confirmation checks.
3. Add canary feature flag and time-window constraints for first live rollout.

Exit criteria:

- Canary live sessions show no unauthorized order path crossing R04.
- Error budget and rollback trigger thresholds are met.

### Phase 5 - Full Live + Continuous Validation

Goal: Move from canary to full live with automated regression checks.

Primary files:

- Spyder/SpyderQ_Scripts/SpyderQ95_ValidateAgentContracts.py (new)
- Spyder/SpyderT_Testing/* (new/updated)

Changes:

1. Add pre-start lint command to validate schemas, role policy, and required env gates.
2. Add nightly replay check over decision logs to detect malformed or unauthorized handoffs.
3. Promote canary flags to default once stability targets are met.

Exit criteria:

- Contract lint is mandatory for startup in autonomous execution modes.
- Regression suite covers malformed envelopes, unauthorized sender/topic, missing approval token, and live-block behavior.

## 5) Exact Modules to Touch First (Priority Order)

1. Spyder/SpyderI_Integration/SpyderI06_AgentMessageBus.py
2. Spyder/SpyderY_AutoAgents/SpyderY00_BaseAutoAgent.py
3. Spyder/SpyderZ_Communication/SpyderZ02_MessageProtocol.py
4. Spyder/SpyderD_Strategies/SpyderD31_StrategyOrchestrator.py
5. Spyder/SpyderY_AutoAgents/SpyderY08_MetaOrchestratorAgent.py
6. Spyder/SpyderX_Agents/SpyderX14_OrchestratorAgent.py
7. Spyder/SpyderA_Core/SpyderA03_Configuration.py
8. config/agent_handoff_policy.json (new)
9. Spyder/SpyderE_Risk/SpyderE01_RiskManager.py
10. Spyder/SpyderR_Runtime/SpyderR04_LiveEngine.py
11. Spyder/SpyderQ_Scripts/SpyderQ02_ValidateEnv.py
12. Spyder/SpyderT_Testing/ (new targeted tests)

## 6) Testing Strategy

Run targeted tests at each phase boundary, then run broad suite before promotion.

Baseline to keep green:

- Spyder/SpyderT_Testing/test_d31_entry_trust_gate.py
- Spyder/SpyderT_Testing/test_f09_decision_path_controls.py
- Spyder/SpyderT_Testing/test_f09_event_clock_blackout.py
- Spyder/SpyderT_Testing/SpyderT193_D31_DispatchResultHardening.py
- Spyder/SpyderT_Testing/SpyderT194_R12_RiskManagerInjection.py
- Spyder/SpyderT_Testing/SpyderT195_D31_DispatchStateBadge.py

New tests to add:

1. test_i06_publish_compat.py
2. test_i06_role_topic_policy.py
3. test_z02_agent_handoff_schema_v1.py
4. test_d31_agent_handoff_contract_enforcement.py
5. test_r04_live_requires_approval_token_for_agent_origin.py
6. test_q02_live_mode_requires_approval_env.py

## 7) Rollback and Safety Controls

- Every phase ships behind feature flags default-off in live mode.
- Rollback point is Phase 0 compatibility layer (non-breaking adapters retained).
- If validation false-positive rate breaches threshold, revert enforcement to shadow mode while preserving logs.
- Existing hard safety constraints remain unchanged:
  - LIVE_TRADING_CONFIRMED gate
  - FillReconciler live fail-closed gate
  - D31/F09/E01 trust and risk gates

## 8) Recommended Execution Sequence

1. Complete Phase 0 and Phase 1 in one PR series (transport + shadow contracts).
2. Run at least 5 full paper sessions before Phase 2 enforcement.
3. Run at least 10 paper sessions with approval enforcement before any live canary.
4. Start live canary only during defined low-risk windows with operator present.
5. Promote to full live only after all Phase 5 checks are green for a sustained period.
