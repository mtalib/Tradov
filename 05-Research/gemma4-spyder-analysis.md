# Gemma 4 — Spyder Integration & Fine-Tuning Analysis

> **Date:** April 3, 2026
> **Status:** Research Complete — Ready to implement
> **Verdict: ✅ YES — Use Gemma 4 immediately; fine-tune E4B for Spyder domain**

---

## 1. What Is Gemma 4?

Gemma 4 is Google DeepMind's latest family of open-weight multimodal LLMs, released April 2–3, 2026. Licensed under **Apache 2.0** (no AGPL, no viral licensing), it is suitable for commercial use within Spyder.

### Model Sizes (all available via Ollama)

| Model | Ollama Tag | Download Size | Context | Modalities | Notes |
|-------|-----------|--------------|---------|------------|-------|
| E2B | `gemma4:e2b` | 7.2 GB | 128K | Text + Image + Audio | Edge/on-device |
| E4B | `gemma4:e4b` | 9.6 GB | 128K | Text + Image + Audio | Default / recommended fast |
| 26B A4B | `gemma4:26b` | 18 GB | 256K | Text + Image | MoE — only 4B active at inference |
| 31B | `gemma4:31b` | 20 GB | 256K | Text + Image | Dense — best quality |

> **E2B / E4B**: Per-Layer Embeddings (PLE) — total params higher than effective params but inference uses only the effective count. Fast on CPU.
>
> **26B A4B**: Mixture-of-Experts with 8 active / 128 total experts. Runs inference at ~4B-parameter speed despite 26B total. LMArena score 1441.

---

## 2. Hardware Assessment (Current Spyder host)

```
RAM:  30 GB total, ~20 GB available
GPU:  None (CPU-only)
OS:   Ubuntu 25.04
```

| Model | Fits in RAM? | CPU-only performance |
|-------|-------------|---------------------|
| gemma4:e2b (7.2 GB) | ✅ Comfortably | Fast (~5–10 tok/s) |
| gemma4:e4b (9.6 GB) | ✅ Comfortably | Good (~3–6 tok/s) |
| gemma4:26b (18 GB) | ✅ Fits (tight) | Slow on CPU (~0.5–1.5 tok/s) |
| gemma4:31b (20 GB) | ⚠️ Tight | Very slow on CPU |

> **Recommendation for CPU-only**: Use `gemma4:e4b` for interactive agents and `gemma4:26b` for non-real-time deep analysis tasks. Do **not** run both large models simultaneously.

---

## 3. Why Gemma 4 Is a Strong Upgrade for Spyder

### 3.1 Benchmark vs Current Spyder Models

| Benchmark | llama3.1:8b (FAST) | gemma4:e4b (replacement) | gemma4:26b (PRIMARY) |
|-----------|-------------------|--------------------------|----------------------|
| MMLU Pro | ~56% | **69.4%** | **82.6%** |
| GPQA Diamond | ~32% | **58.6%** | **82.3%** |
| LiveCodeBench v6 | ~28% | **52.0%** | **77.1%** |
| Codeforces ELO | ~300 | **940** | **1718** |
| Context Window | 128K | 128K | 256K |

### 3.2 Spyder-Specific Advantages

| Feature | Spyder Use Case | Agent(s) |
|---------|----------------|----------|
| **256K context window** (26b) | Feed complete options chain + intraday trade log + Greeks snapshot in a single prompt | X01, X03, X04 |
| **Native function calling** | Structured tool-use → directly map to `SpyderI06_AgentMessageBus` dispatch | All X/Y Agents |
| **Built-in thinking / reasoning mode** | Step-by-step risk reasoning before decisions | X04, X01, X06 |
| **Image / chart understanding** (E4B) | Analyse `SpyderG04_ChartWidget` screenshots for pattern recognition | X13, Y01 |
| **Coding capability** (Codeforces ELO 1718) | Code review, bug detection, strategy generation | Y09, X15 |
| **System prompt support** (new in Gemma 4) | Persistent Spyder persona + risk guidelines baked into `system` role | All agents |
| **Apache 2.0 license** | No AGPL, no viral licensing, safe for Spyder | — |

---

## 4. Recommended Model Mapping (Update .env)

Replace the current Ollama model assignments in `.env`:

```bash
# Current (recommended replacement → Gemma 4)

# PRIMARY: deep reasoning, multi-step analysis, complex risk decisions
OLLAMA_PRIMARY_MODEL=gemma4:26b          # was llama3.1:70b (not feasible on CPU anyway)

# FAST: real-time signal processing, quick lookups, low-latency responses  
OLLAMA_FAST_MODEL=gemma4:e4b             # was llama3.1:8b

# CODE: code generation, strategy code review, Y09_CodeReviewerAgent
OLLAMA_CODE_MODEL=gemma4:26b             # was codestral:22b (Codeforces ELO 1718 vs ~500)

# FINANCE: options Greeks analysis, risk reasoning, strategy decisions
OLLAMA_FINANCE_MODEL=gemma4:e4b          # was llama3.1:70b (not feasible); e4b viable on CPU

# Recommended temperature for financial reasoning (lower = more deterministic)
OLLAMA_DEFAULT_TEMPERATURE=0.3
```

> **Note on concurrent usage**: With 30 GB RAM, do not attempt to load `gemma4:26b` (18 GB) and `gemma4:e4b` (9.6 GB) simultaneously. The `PRIMARY` and `CODE` roles share `gemma4:26b`, so Ollama will reuse the same loaded model — only one instance needed.

### Immediate Pull Commands

```bash
ollama pull gemma4:e4b    # 9.6 GB — FAST + FINANCE roles
ollama pull gemma4:26b    # 18 GB — PRIMARY + CODE roles
```

---

## 5. Thinking Mode for Spyder Agents

Gemma 4 introduces a `<|think|>` token that enables internal step-by-step reasoning before the final answer. This is directly useful for:

- **SpyderX04_RiskGuardianAgent**: reason through Greek limits before issuing warnings
- **SpyderX01_GreeksAgent**: analyse complex multi-leg exposure before recommending adjustments
- **SpyderX03_StrategyDirectorAgent**: weigh regime signals before recommending a strategy
- **SpyderX06_BacktestingAgent**: reason through strategy logic before summarising results

To enable thinking in Ollama requests, prepend `<|think|>` to the system prompt or use the Ollama API's `think` option once Ollama exposes it. For now, prefix the system prompt:

```python
# In SpyderX agent Ollama calls — add to system prompt:
SYSTEM_PROMPT_PREFIX = "<|think|>\n"
```

Ollama handles chat template formatting automatically; do **not** manually inject thinking tokens unless you bypass the template API.

---

## 6. Fine-Tuning Gemma 4 for Spyder

### 6.1 Goal

Create `gemma4-spyder-e4b` — a Spyder-domain-specialized version of `gemma4:e4b` that:
- Understands SPY options terminology natively (Delta, Gamma, IV rank, Iron Condor legs, etc.)
- Knows Spyder's module names and inter-module contracts
- Reasons about Spyder-specific risk parameters (MAX_PORTFOLIO_RISK = 0.02, etc.)
- Responds in Spyder's structured output format (SpyderLogger-compatible, JSON tool calls)

### 6.2 Training Data Sources

Collect from existing Spyder infrastructure:

| Data Type | Source | Volume Estimate |
|-----------|--------|----------------|
| Trade decision logs | `SpyderH04_TradeRepository` + `logs/spyder.log` | 10K–100K entries |
| Agent Q&A pairs | X-Series agent outputs → format as instruction pairs | 5K–50K pairs |
| Strategy decisions with rationale | `SpyderD01_BaseStrategy` signal outputs | 2K–20K entries |
| Options chain annotation | `SpyderB30_SPYOptionsChainManager` snapshots | 1K–10K records |
| Risk validation outcomes | `SpyderE_Risk` pass/fail decisions with context | 5K–50K entries |
| Docstrings + module contracts | All Spyder source files | ~500K tokens of domain text |

**Minimum viable dataset**: ~2,000 high-quality instruction-response pairs for initial fine-tune.

### 6.3 Dataset Format (Alpaca / Chat format for TRL SFTTrainer)

```python
# Format for TRL SFTTrainer with chat template
{
    "messages": [
        {
            "role": "system",
            "content": (
                "You are the Spyder AI trading assistant specializing in SPY options. "
                "You understand Spyder's module architecture (A–Z series), risk parameters "
                "(MAX_PORTFOLIO_RISK=0.02, MAX_DAILY_RISK=0.05), and options Greeks. "
                "Always respond with deterministic, well-reasoned financial analysis. "
                "Never recommend live trades without explicit confirmation."
            )
        },
        {
            "role": "user",
            "content": "Current portfolio delta is -0.85 contracts. IV rank is 72. "
                       "We hold a short Iron Condor on SPY with 3 DTE. Assess risk."
        },
        {
            "role": "assistant",
            "content": (
                "Risk Assessment: ELEVATED\n\n"
                "1. Delta exposure (-0.85) approaches the short delta limit. "
                "   With 3 DTE and high IV rank (72), gamma risk is significant.\n"
                "2. Recommend delta hedge: buy 1 SPY call to reduce delta to ~0.0.\n"
                "3. Max loss scenario: gap move >2SD would breach MAX_PORTFOLIO_RISK.\n"
                "Action: Trigger SpyderE15_GreekLimitsManager review. "
                "Consider early close if delta exceeds ±1.0."
            )
        }
    ]
}
```

### 6.4 Fine-Tuning Method: QLoRA via TRL

**QLoRA** (Quantized LoRA) allows fine-tuning on consumer hardware. For CPU-only or a single GPU:

```bash
pip install -U transformers trl peft bitsandbytes datasets accelerate
```

**Recommended LoRA config for gemma4:e4b**:

```python
from peft import LoraConfig

lora_config = LoraConfig(
    r=16,                          # rank — higher = more capacity, more memory
    lora_alpha=32,                 # scaling factor
    target_modules=[               # gemma4 attention projection layers
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
```

**SFT training script skeleton** (`SpyderT_Testing/finetune_gemma4_spyder.py`):

```python
#!/usr/bin/env python3
"""Fine-tune Gemma 4 E4B on Spyder domain data using QLoRA + TRL SFTTrainer."""

import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

MODEL_ID = "google/gemma-4-E4B-it"
OUTPUT_DIR = "models/gemma4-spyder-e4b"

# 4-bit quantization — fits in 8 GB VRAM or runs on CPU
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.bfloat16,
)
processor = AutoProcessor.from_pretrained(MODEL_ID)

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

# Load Spyder training data (see Section 6.2 above for format)
dataset = Dataset.from_json("data/spyder_finetune_dataset.jsonl")

training_args = SFTConfig(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=1,      # CPU/single GPU constraint
    gradient_accumulation_steps=8,      # effective batch size = 8
    learning_rate=2e-4,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    logging_steps=10,
    save_strategy="epoch",
    bf16=True,
    max_seq_length=4096,               # limit context to save memory during training
    dataset_text_field="messages",
    packing=False,
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    peft_config=lora_config,
    processing_class=processor,
)

trainer.train()
trainer.save_model(OUTPUT_DIR)
processor.save_pretrained(OUTPUT_DIR)
print(f"Fine-tuned model saved to {OUTPUT_DIR}")
```

### 6.5 Export to GGUF for Ollama

After training, merge the LoRA adapter and export to GGUF so it can be loaded locally via Ollama:

```bash
# 1. Merge adapter into base model
python -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM
base = AutoModelForCausalLM.from_pretrained('google/gemma-4-E4B-it')
model = PeftModel.from_pretrained(base, 'models/gemma4-spyder-e4b')
merged = model.merge_and_unload()
merged.save_pretrained('models/gemma4-spyder-e4b-merged')
"

# 2. Convert to GGUF using llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && pip install -r requirements.txt
python convert_hf_to_gguf.py ../models/gemma4-spyder-e4b-merged \
    --outfile ../models/gemma4-spyder-e4b-Q4_K_M.gguf \
    --outtype q4_k_m

# 3. Create Ollama Modelfile
cat > Modelfile.spyder << 'EOF'
FROM ./models/gemma4-spyder-e4b-Q4_K_M.gguf

SYSTEM """
You are the Spyder AI trading assistant. You specialize in SPY options trading,
understand Spyder's A-Z module architecture, and follow strict risk management:
MAX_PORTFOLIO_RISK=0.02, MAX_DAILY_RISK=0.05, MAX_STRATEGY_ALLOCATION=0.20.
Never recommend live trades without explicit human confirmation.
"""

PARAMETER temperature 0.3
PARAMETER top_p 0.95
PARAMETER top_k 64
EOF

# 4. Register with Ollama
ollama create gemma4-spyder:e4b -f Modelfile.spyder

# 5. Update .env
# OLLAMA_FAST_MODEL=gemma4-spyder:e4b
# OLLAMA_FINANCE_MODEL=gemma4-spyder:e4b
```

### 6.6 Alternative: Unsloth Studio (No-Code Fine-Tuning)

For a simpler approach without writing training code:

```bash
# Install Unsloth Studio (runs locally on Ubuntu)
curl -fsSL https://unsloth.ai/install.sh | sh
unsloth studio -H 0.0.0.0 -p 8888
# Then open http://localhost:8888, select google/gemma-4-E4B-it, upload JSONL dataset
```

---

## 7. Data Collection Script Outline

To generate the fine-tuning dataset from live Spyder data:

```python
# SpyderQ_Scripts/collect_finetune_data.py
# Collects trade decision logs and formats them as instruction pairs

from SpyderH_Storage.SpyderH04_TradeRepository import TradeRepository
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
import json

logger = SpyderLogger.get_logger(__name__)

def collect_agent_interactions(output_path: str = "data/spyder_finetune_dataset.jsonl") -> int:
    """
    Collect Spyder agent interaction logs and format as fine-tuning pairs.

    Returns:
        Number of training examples collected.
    """
    repo = TradeRepository()
    examples = []

    # Collect trade decisions with context
    trades = repo.get_all_trades(limit=10000)
    for trade in trades:
        if trade.agent_reasoning:      # only include decisions with documented rationale
            examples.append({
                "messages": [
                    {"role": "system", "content": SPYDER_SYSTEM_PROMPT},
                    {"role": "user",   "content": trade.decision_context},
                    {"role": "assistant", "content": trade.agent_reasoning}
                ]
            })

    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    logger.info(f"Collected {len(examples)} fine-tuning examples → {output_path}")
    return len(examples)

SPYDER_SYSTEM_PROMPT = (
    "You are the Spyder AI trading assistant specializing in SPY 0DTE and short-term "
    "options strategies. You understand Iron Condors, Credit Spreads, IV rank, Greeks "
    "(delta/gamma/theta/vega), Spyder's risk limits (2% per trade, 5% daily), and the "
    "A–Z module architecture. Respond with structured, concise analysis. "
    "Use SpyderLogger format. Never execute live trades without explicit confirmation."
)
```

---

## 8. Integration Checklist

### Phase 1 — Drop-in Replacement (Today, ~30 min)

- [ ] `ollama pull gemma4:e4b` (9.6 GB)
- [ ] `ollama pull gemma4:26b` (18 GB)
- [ ] Update `.env`: set `OLLAMA_FAST_MODEL=gemma4:e4b`, `OLLAMA_PRIMARY_MODEL=gemma4:26b`, `OLLAMA_CODE_MODEL=gemma4:26b`, `OLLAMA_FINANCE_MODEL=gemma4:e4b`
- [ ] Smoke-test each X-Series agent with new models
- [ ] Verify JSON/tool-call response format is compatible with `SpyderI06_AgentMessageBus`

### Phase 2 — Thinking Mode (1–2 days)

- [ ] Add `<|think|>` prefix toggle to X-Series agent system prompts for high-stakes decisions
- [ ] Update `SpyderX04_RiskGuardianAgent` and `SpyderX01_GreeksAgent` to strip think-block from logged output
- [ ] Verify `SpyderY09_CodeReviewerAgent` uses 26b for code review

### Phase 3 — Fine-Tuning (1–2 weeks)

- [ ] Run `collect_finetune_data.py` — collect 2,000+ trade decision pairs from live/paper logs
- [ ] Augment with synthetic SPY options scenarios (ask `gemma4:26b` to generate 500+ examples)
- [ ] Fine-tune `gemma4:e4b` with QLoRA using TRL `SFTTrainer`
- [ ] Evaluate on held-out Spyder scenarios (accuracy of risk calls, Greek recommendations)
- [ ] Convert to GGUF → register as `gemma4-spyder:e4b` in Ollama
- [ ] A/B test fine-tuned vs base model on agent tasks — measure response quality improvement

### Phase 4 — Multimodal (Future, requires GPU)

- [ ] Use `gemma4:e4b` vision capability to analyse candlestick chart images from `SpyderG04`
- [ ] Feed options chain screenshots to `SpyderX01_GreeksAgent` for visual confirmation
- [ ] Consider upgrading to a GPU (RTX 4090 / A100) to unlock real-time vision + 31B model

---

## 9. Known Limitations & Risks

| Risk | Mitigation |
|------|-----------|
| **CPU inference is slow** for 26b (~0.5–1.5 tok/s) | Use for non-real-time tasks only (reports, deep analysis). Keep e4b for live agents. |
| **No GPU** limits fine-tuning batch size | Use `gradient_accumulation_steps=8` + `max_seq_length=4096` to compensate |
| **Knowledge cutoff Jan 2025** | Gemma 4 won't know post-Jan-2025 market events; always inject live data as context |
| **Hallucination on specific SPY data** | Always inject live data values explicitly; don't ask model to recall prices/strikes |
| **Memory pressure with 26b + e4b** | Ollama unloads models when idle; avoid calling both simultaneously |
| **Thinking mode verbosity** | Strip `<|channel>thought\n...<channel|>` blocks before logging or forwarding to MessageBus |

---

## 10. Summary

**Can we use Gemma 4 for Spyder? Yes, immediately.**

- Apache 2.0 license ✅
- Available in Ollama right now ✅ (`ollama pull gemma4:e4b`)
- Fits on 30 GB RAM (CPU) ✅
- Native function calling — maps directly to `SpyderI06_AgentMessageBus` ✅
- Dramatically better than current llama3.1:8b (Codeforces ELO 940 vs ~300) ✅
- 128K–256K context window — can ingest full options chain + trade history ✅

**Should we fine-tune it for Spyder? Yes, as Phase 3.**

- E4B (8B effective) is the right size for fine-tuning on CPU/consumer hardware
- QLoRA via TRL is the standard, well-supported path
- Training data is readily available from Spyder's own logs (`SpyderH04_TradeRepository`)
- Fine-tuned model can be exported to GGUF and loaded via Ollama with no architecture changes
