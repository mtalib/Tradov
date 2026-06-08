# Tradov — Local AI Model Architecture
> **Date:** 2026-03-18  
> **Author:** GitHub Copilot  
> **Status:** Proposal / Recommended Configuration  
> **Applies to:** `TradovX_Agents` (X-Series), `TradovY_AutoAgents` (Y-Series)

---

## 1. Overview

Tradov uses **Ollama** to run large language models (LLMs) locally on the trading machine. All AI agent reasoning — market analysis, risk review, code generation, trade journaling, news sentiment — is handled entirely on-device with **no data sent to external AI APIs**.

The models are accessed through a unified role system defined in
`TradovY_AutoAgents/TradovY00_BaseAutoAgent.py`. Each agent declares which **role**
it needs for a given task; Ollama resolves the role to the appropriate model.

**Key principles:**
- All models are AGPL-free (Meta Community License, Apache 2.0, MIT)
- One model runs at a time; Ollama queues concurrent requests
- All settings are overridable via `.env` without code changes
- If Ollama is unavailable, agents degrade gracefully (skip LLM calls, continue operating)

---

## 2. Hardware Context

| Component | Spec |
|-----------|------|
| **Machine** | ASUSTeK NUC14RVH-B |
| **CPU** | Intel Core Ultra 7 155H × 22 threads |
| **RAM** | 32 GiB |
| **GPU** | Intel Graphics MTL (integrated, shared RAM) |
| **OS** | Ubuntu 25.10 / Kernel 6.17 |

**Inference mode: CPU only.** The integrated Intel GPU shares system RAM and provides
no meaningful acceleration for these model sizes. Ollama defaults to CPU inference.

---

## 3. The Four Model Roles

The system defines four roles, each mapped to a specific Ollama model:

```python
class LLMRole(Enum):
    PRIMARY = "primary"    # General reasoning
    FAST    = "fast"       # Quick, low-latency tasks
    CODE    = "code"       # Code generation and review
    FINANCE = "finance"    # Financial domain reasoning
```

### 3.1 PRIMARY — `llama3.1:8b-instruct-q5_K_M`

| Property | Value |
|----------|-------|
| **Size on disk** | ~5.5 GB |
| **Est. RAM usage** | ~6.0 GB |
| **CPU speed** | ~5–10 tokens/sec |
| **License** | Meta Community License (commercial OK) |
| **Env var** | `OLLAMA_PRIMARY_MODEL` |

**Purpose:** The general-purpose workhorse. Used for complex multi-step reasoning
where response quality matters more than speed. This is the most heavily used role
(16 callsites across Y-Series agents).

**Used by:**
- `Y02_StrategyPilotAgent` — strategy selection reasoning (4× per cycle)
- `Y03_RiskSentinelAgent` — risk limit analysis and breach investigation (2×)
- `Y07_TradeJournalAgent` — trade rationale narratives and lessons learned (4×)
- `Y08_MetaOrchestratorAgent` — cross-agent coordination decisions (2×)

---

### 3.2 FAST — `llama3.2:3b-instruct-q4_K_M`

| Property | Value |
|----------|-------|
| **Size on disk** | ~2.0 GB |
| **Est. RAM usage** | ~2.2 GB |
| **CPU speed** | ~15–25 tokens/sec |
| **License** | Meta Community License (commercial OK) |
| **Env var** | `OLLAMA_FAST_MODEL` |
| **Status** | ✅ Already pulled locally |

**Purpose:** Time-sensitive tasks where a quick answer is more valuable than a
deeply reasoned one. The small model size also means it loads fastest (~8s on CPU),
making it suitable for any path where swap latency matters.

**Used by:**
- `Y01_MarketSenseAgent` — quick anomaly triage
- `Y05_ExecutionOptimizerAgent` — real-time execution decisions
- `Y08_MetaOrchestratorAgent` — routine status/health checks

---

### 3.3 CODE — `qwen2.5-coder:7b-instruct-q5_K_M`

| Property | Value |
|----------|-------|
| **Size on disk** | ~5.0 GB |
| **Est. RAM usage** | ~5.5 GB |
| **CPU speed** | ~5–10 tokens/sec |
| **License** | Apache 2.0 |
| **Env var** | `OLLAMA_CODE_MODEL` |

**Purpose:** A model specifically trained on code corpora. Produces significantly
better Python output compared to general-purpose models of the same size — better
variable naming, correct library usage, fewer hallucinated APIs.

**Used by:**
- `Y04_AlphaLearnerAgent` — generates and modifies strategy logic (2×)
- `Y09_CodeReviewerAgent` — code review for style, security, and correctness (1×)

---

### 3.4 FINANCE — `mistral:7b-instruct-v0.3-q5_K_M`

| Property | Value |
|----------|-------|
| **Size on disk** | ~5.0 GB |
| **Est. RAM usage** | ~5.5 GB |
| **CPU speed** | ~5–10 tokens/sec |
| **License** | Apache 2.0 |
| **Env var** | `OLLAMA_FINANCE_MODEL` |

**Purpose:** Mistral 7B shows stronger performance on financial terminology,
market context, and quantitative reasoning compared to Llama of the same size.
Used where domain accuracy matters more than code ability.

**Used by:**
- `Y01_MarketSenseAgent` — market condition analysis
- `Y03_RiskSentinelAgent` — position risk context
- `Y06_NewsSentinelAgent` — financial news interpretation (2×)

---

## 4. How Ollama Manages the Models

### 4.1 One Model at a Time

Ollama keeps **exactly one model loaded in RAM** by default. When a request arrives
for a different model, it:
1. Unloads the current model (frees RAM)
2. Loads the requested model (~8–30s on CPU depending on size)
3. Processes the request and returns a response

This means **models never run simultaneously** — they take turns through a queue.

```
┌─────────────────────────────────────────────────────────┐
│                     RAM (32 GiB)                        │
│                                                         │
│  ┌──────────────────────────────┐  ← Active model       │
│  │   llama3.1:8b (~6 GB)        │    (loaded)           │
│  └──────────────────────────────┘                       │
│                                                         │
│  Remaining ~26 GiB free for OS + Python + Trading app   │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Request Queue

All 9 Y-Series agents and 16 X-Series agents share the same Ollama server at
`http://localhost:11434`. Concurrent LLM requests are serialised:

```
Y07_TradeJournalAgent  → role=PRIMARY ──┐
Y02_StrategyPilotAgent → role=PRIMARY ──┤─→ [Ollama queue] → llama3.1:8b responds
Y03_RiskSentinelAgent  → role=PRIMARY ──┘                     (one at a time)

Y06_NewsSentinelAgent  → role=FINANCE ──→ [Ollama evicts PRIMARY, loads mistral]
                                           (~25s swap on CPU)
```

### 4.3 Model Swap Cost on CPU

| Model Size | Approximate Load Time (CPU) |
|------------|-----------------------------|
| 3B (FAST)  | ~8–12 seconds |
| 7–8B       | ~20–30 seconds |

This is a **one-time cost per switch**. Once a model is loaded, subsequent requests
to the same model respond at full inference speed with no swap overhead.

### 4.4 Cache Behaviour

```bash
OLLAMA_KEEP_ALIVE=5m   # Default: evict model after 5 minutes of inactivity
```

If no agent calls `FINANCE` for 5+ minutes, Ollama evicts it from RAM. The next
`FINANCE` request pays the full load time again. This is acceptable because Y-Series
agents run on minute/multi-minute cycles — not millisecond loops.

---

## 5. Code Architecture

### 5.1 OllamaConfig (TradovY00_BaseAutoAgent.py)

```python
@dataclass
class OllamaConfig:
    base_url:             str   = "http://localhost:11434"
    primary_model:        str   = "llama3.1:8b-instruct-q5_K_M"
    fast_model:           str   = "llama3.2:3b-instruct-q4_K_M"
    code_model:           str   = "qwen2.5-coder:7b-instruct-q5_K_M"
    finance_model:        str   = "mistral:7b-instruct-v0.3-q5_K_M"
    timeout:              int   = 60
    max_retries:          int   = 3
    temperature_default:  float = 0.3
    temperature_creative: float = 0.7
    max_context_tokens:   int   = 4096
```

All values are loaded from `.env` via `OllamaConfig.from_env()` with the hardcoded
defaults as fallback. No code changes are needed to switch models.

### 5.2 How an Agent Makes an LLM Call

```python
# Inside any Y-Series agent:
response = self.llm_query(
    prompt="Analyse the current risk exposure and flag any breaches.",
    role=LLMRole.PRIMARY,
    system_prompt="You are a risk management assistant for an options trading system.",
    temperature=0.3,
    max_tokens=1024,
)
```

Internally, `llm_query()`:
1. Checks `OLLAMA_AVAILABLE` — skips gracefully if Ollama is not running
2. Calls `_get_model_for_role(role)` to resolve the model name from config
3. Sends the request via `ollama.chat()` with retry + exponential backoff
4. Tracks latency and call count in `AgentHeartbeat` metrics
5. Returns the response string, or `None` on failure

For structured data, `llm_query_json()` wraps `llm_query()` and automatically
extracts valid JSON from the response (handles markdown fences, trailing text, etc.)

### 5.3 Graceful Degradation

If Ollama is not installed or not running:
```python
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
```

Every agent checks `OLLAMA_AVAILABLE` before making LLM calls. Agents continue
operating with their rule-based logic — LLM reasoning is an enhancement layer,
not a hard dependency for trading operation.

---

## 6. Environment Configuration

Add the following section to `.env` to make model selection explicit and easily
changeable without touching code:

```env
# ==============================================================================
# OLLAMA LOCAL LLM
# ==============================================================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_PRIMARY_MODEL=llama3.1:8b-instruct-q5_K_M
OLLAMA_FAST_MODEL=llama3.2:3b-instruct-q4_K_M
OLLAMA_CODE_MODEL=qwen2.5-coder:7b-instruct-q5_K_M
OLLAMA_FINANCE_MODEL=mistral:7b-instruct-v0.3-q5_K_M
OLLAMA_TIMEOUT=60
OLLAMA_MAX_RETRIES=3
OLLAMA_TEMPERATURE_DEFAULT=0.3
OLLAMA_TEMPERATURE_CREATIVE=0.7
```

---

## 7. Setup Instructions

### 7.1 Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify it is running:
```bash
ollama list
curl http://localhost:11434/api/tags
```

### 7.2 Pull the Required Models

```bash
# Already pulled ✅
ollama pull llama3.2:3b-instruct-q4_K_M

# Need to pull ❌
ollama pull llama3.1:8b-instruct-q5_K_M
ollama pull qwen2.5-coder:7b-instruct-q5_K_M
ollama pull mistral:7b-instruct-v0.3-q5_K_M
```

Approximate disk usage: **~17.5 GB total** for all four models.

### 7.3 Start Ollama as a Service (Recommended)

Ollama installs a systemd service by default. Confirm it is enabled:

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

To set `KEEP_ALIVE` system-wide (reduces unnecessary model eviction):

```bash
sudo systemctl edit ollama
```

Add:
```ini
[Service]
Environment="OLLAMA_KEEP_ALIVE=10m"
```

Then reload:
```bash
sudo systemctl daemon-reload && sudo systemctl restart ollama
```

### 7.4 Verify from Python

```bash
source .venv/bin/activate
python -c "import ollama; print(ollama.list())"
```

---

## 8. Performance Expectations (CPU)

### Expected Response Times

| Scenario | Latency |
|----------|---------|
| Model already loaded, FAST (3B) | 2–5 seconds |
| Model already loaded, PRIMARY/CODE/FINANCE (7–8B) | 8–20 seconds |
| Model swap required (3B → 8B) | 30–50 seconds total |
| Model swap required (8B → 8B different model) | 45–60 seconds total |

### Why This Is Acceptable

All Y-Series agents run on **asynchronous background loops**, not on the trading
critical path:

| Agent | Typical LLM call frequency |
|-------|---------------------------|
| `Y01_MarketSenseAgent` | Every 2–5 minutes |
| `Y02_StrategyPilotAgent` | On regime change / new signal |
| `Y03_RiskSentinelAgent` | Every 5 minutes or on breach |
| `Y04_AlphaLearnerAgent` | Post-session (EOD) |
| `Y05_ExecutionOptimizerAgent` | Per order (async, not blocking) |
| `Y06_NewsSentinelAgent` | On news event |
| `Y07_TradeJournalAgent` | Per trade close |
| `Y08_MetaOrchestratorAgent` | Every 10 minutes |
| `Y09_CodeReviewerAgent` | On-demand only |

Order execution, risk checks, and market data processing all run independently of
the LLM layer. A 30-second LLM response never blocks a trade.

---

## 9. CPU-Optimised Configuration (Recommended)

Given the single-CPU constraint, the most cache-friendly configuration is to
**minimise model switches** by consolidating roles down to two models. This is
optional but reduces swap overhead significantly during active trading hours.

### Option A — Full 4-Model Setup (Current Design)
- Best quality per task
- More model switching during peak hours
- ~17.5 GB disk

### Option B — 2-Model Consolidated (CPU-Optimised)
Map CODE and FINANCE roles to PRIMARY:

```env
OLLAMA_PRIMARY_MODEL=llama3.1:8b-instruct-q5_K_M
OLLAMA_FAST_MODEL=llama3.2:3b-instruct-q4_K_M
OLLAMA_CODE_MODEL=llama3.1:8b-instruct-q5_K_M     # same as PRIMARY
OLLAMA_FINANCE_MODEL=llama3.1:8b-instruct-q5_K_M  # same as PRIMARY
```

- Only 2 models loaded in rotation → far fewer swaps
- ~7.5 GB disk
- Slight quality reduction for code generation and financial terminology
- **No code changes required** — only `.env` changes

> **Recommendation for initial deployment:** Start with Option B. Switch to
> full Option A when/if a discrete GPU is added.

---

## 10. Future: GPU Upgrade Path

If an NVIDIA GPU is added (e.g. RTX 4060 via eGPU):

1. Install NVIDIA drivers and confirm `nvidia-smi` works
2. Ollama auto-detects CUDA — no configuration needed
3. All 4 models fit in 8 GB VRAM simultaneously (Ollama can hold multiple models
   in VRAM on GPU, unlike CPU)
4. Response times improve to ~50–70 tokens/sec for 7–8B models
5. Model switching overhead drops to near zero

At that point, the 4-model full setup becomes the clear recommendation with no
trade-offs.

---

## 11. Current Status

| Item | Status |
|------|--------|
| Ollama installed | ✅ |
| `llama3.2:3b-instruct-q4_K_M` (FAST) | ✅ Pulled |
| `llama3.1:8b-instruct-q5_K_M` (PRIMARY) | ❌ Not pulled |
| `qwen2.5-coder:7b-instruct-q5_K_M` (CODE) | ❌ Not pulled |
| `mistral:7b-instruct-v0.3-q5_K_M` (FINANCE) | ❌ Not pulled |
| Ollama section in `.env` | ❌ Not added |
| `phi3:mini` (pulled but unused) | ⚠️ Can be removed to save 2.2 GB |

---

*Document created: 2026-03-18 | Hardware: NUC14RVH-B, Intel Core Ultra 7 155H, 32 GiB RAM, Ubuntu 25.10*
