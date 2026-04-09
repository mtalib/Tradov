#!/usr/bin/env bash
# ==============================================================================
# export_to_ollama.sh — Merge LoRA adapter, convert to GGUF, register in Ollama
# ==============================================================================
# Usage:
#   bash SpyderQ_Scripts/export_to_ollama.sh <adapter_dir> [base_model_hf_id]
#
# Example:
#   bash SpyderQ_Scripts/export_to_ollama.sh \
#       models/gemma4-spyder-e4b/adapter \
#       google/gemma-3-4b-it
#
# Requirements:
#   pip install transformers peft accelerate
#   git clone https://github.com/ggerganov/llama.cpp to $LLAMA_CPP_DIR (or set env var)
#   ollama 0.20.0+
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# Args / defaults
# ------------------------------------------------------------------------------
ADAPTER_DIR="${1:-}"
BASE_MODEL_HF="${2:-google/gemma-3-4b-it}"

if [[ -z "$ADAPTER_DIR" ]]; then
    echo "Usage: $0 <adapter_dir> [base_model_hf_id]"
    exit 1
fi

ADAPTER_DIR="$(realpath "$ADAPTER_DIR")"
if [[ ! -d "$ADAPTER_DIR" ]]; then
    echo "ERROR: adapter directory not found: $ADAPTER_DIR"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(realpath "$SCRIPT_DIR/..")"

# Where we'll write the merged model and GGUF
MERGED_DIR="${PROJECT_ROOT}/models/gemma4-spyder-e4b/merged"
GGUF_PATH="${PROJECT_ROOT}/models/gemma4-spyder-e4b/gemma4-spyder-e4b-q5_K_M.gguf"
MODELFILE_PATH="${PROJECT_ROOT}/models/gemma4-spyder-e4b/Modelfile.spyder"
OLLAMA_MODEL_NAME="gemma4-spyder:e4b"

# llama.cpp directory (clone if not present)
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-${PROJECT_ROOT}/tools/llama.cpp}"

PYTHON="${PROJECT_ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

# ------------------------------------------------------------------------------
# Step 1 — Merge LoRA adapter into base weights
# ------------------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════"
echo " Step 1: Merging LoRA adapter into base"
echo "═══════════════════════════════════════"
mkdir -p "$MERGED_DIR"

"$PYTHON" - <<PYEOF
import sys
from pathlib import Path

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    import torch
except ImportError:
    print("ERROR: transformers/peft not installed.")
    print("Run: pip install transformers peft accelerate")
    sys.exit(1)

adapter_dir = Path("${ADAPTER_DIR}")
merged_dir  = Path("${MERGED_DIR}")
base_model  = "${BASE_MODEL_HF}"
hf_token    = None  # set HUGGINGFACE_TOKEN env if needed

import os
hf_token = os.getenv("HUGGINGFACE_TOKEN")

print(f"Loading base model: {base_model}")
tokenizer = AutoTokenizer.from_pretrained(base_model, token=hf_token)
model = AutoModelForCausalLM.from_pretrained(
    base_model,
    device_map="cpu",
    torch_dtype=torch.float32,
    token=hf_token,
)

print(f"Loading LoRA adapter: {adapter_dir}")
model = PeftModel.from_pretrained(model, str(adapter_dir))
model = model.merge_and_unload()

print(f"Saving merged model to: {merged_dir}")
merged_dir.mkdir(parents=True, exist_ok=True)
model.save_pretrained(str(merged_dir))
tokenizer.save_pretrained(str(merged_dir))
print("Merge complete.")
PYEOF

# ------------------------------------------------------------------------------
# Step 2 — Clone / build llama.cpp if needed
# ------------------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════"
echo " Step 2: Ensuring llama.cpp is available"
echo "═══════════════════════════════════════════"

if [[ ! -d "$LLAMA_CPP_DIR" ]]; then
    echo "Cloning llama.cpp to $LLAMA_CPP_DIR ..."
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "$LLAMA_CPP_DIR"
fi

CONVERT_SCRIPT="${LLAMA_CPP_DIR}/convert_hf_to_gguf.py"
if [[ ! -f "$CONVERT_SCRIPT" ]]; then
    echo "ERROR: convert_hf_to_gguf.py not found in $LLAMA_CPP_DIR"
    echo "       Ensure llama.cpp is up to date: git -C $LLAMA_CPP_DIR pull"
    exit 1
fi

QUANTIZE_BIN="${LLAMA_CPP_DIR}/build/bin/llama-quantize"
if [[ ! -x "$QUANTIZE_BIN" ]]; then
    echo "Building llama.cpp quantize tool ..."
    cmake -S "$LLAMA_CPP_DIR" -B "${LLAMA_CPP_DIR}/build" -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON 2>&1 | tail -5
    cmake --build "${LLAMA_CPP_DIR}/build" --config Release -j"$(nproc)" 2>&1 | tail -10
fi

# ------------------------------------------------------------------------------
# Step 3 — Convert merged HF model to f16 GGUF
# ------------------------------------------------------------------------------
echo ""
echo "══════════════════════════════════════════════════"
echo " Step 3: Converting merged weights to GGUF (f16)"
echo "══════════════════════════════════════════════════"

F16_GGUF="${PROJECT_ROOT}/models/gemma4-spyder-e4b/gemma4-spyder-e4b-f16.gguf"

"$PYTHON" "$CONVERT_SCRIPT" \
    --outfile "$F16_GGUF" \
    --outtype f16 \
    "$MERGED_DIR"

echo "F16 GGUF written to: $F16_GGUF"

# ------------------------------------------------------------------------------
# Step 4 — Quantise to Q5_K_M (good quality/size balance on CPU)
# ------------------------------------------------------------------------------
echo ""
echo "════════════════════════════════════════"
echo " Step 4: Quantising to Q5_K_M"
echo "════════════════════════════════════════"

"$QUANTIZE_BIN" "$F16_GGUF" "$GGUF_PATH" Q5_K_M
echo "Q5_K_M GGUF written to: $GGUF_PATH"

# Optionally remove the large f16 file
read -r -p "Remove intermediate f16 GGUF (saves ~8 GB)? [y/N] " yn
if [[ "${yn,,}" == "y" ]]; then
    rm -f "$F16_GGUF"
    echo "Removed $F16_GGUF"
fi

# ------------------------------------------------------------------------------
# Step 5 — Write Ollama Modelfile
# ------------------------------------------------------------------------------
echo ""
echo "═══════════════════════════════════════════"
echo " Step 5: Writing Modelfile.spyder"
echo "═══════════════════════════════════════════"

cat > "$MODELFILE_PATH" <<MODELFILE
FROM ${GGUF_PATH}

# Spyder system identity
SYSTEM """You are Spyder, an autonomous SPY options trading AI.
Given market data, portfolio state, and risk constraints, output a structured
JSON trade decision covering: strategy, entry parameters, position sizing,
Greeks targets, stop-loss levels, and risk rationale.
Prioritise capital preservation. Never exceed 2% portfolio risk per trade."""

PARAMETER temperature 0.3
PARAMETER num_predict 1024
PARAMETER stop "<end_of_turn>"
PARAMETER stop "<eos>"
# Disable thinking tokens for deterministic JSON output
PARAMETER think false
MODELFILE

echo "Modelfile written to: $MODELFILE_PATH"

# ------------------------------------------------------------------------------
# Step 6 — Register in Ollama
# ------------------------------------------------------------------------------
echo ""
echo "══════════════════════════════════════════════"
echo " Step 6: Registering ${OLLAMA_MODEL_NAME} in Ollama"
echo "══════════════════════════════════════════════"

ollama create "${OLLAMA_MODEL_NAME}" -f "$MODELFILE_PATH"
echo "Model registered: ${OLLAMA_MODEL_NAME}"

# ------------------------------------------------------------------------------
# Smoke test
# ------------------------------------------------------------------------------
echo ""
echo "═══════════════════════════"
echo " Smoke test"
echo "═══════════════════════════"

RESPONSE=$(ollama run "${OLLAMA_MODEL_NAME}" "SPY at 580, VIX at 18, system stable. Recommend strategy." 2>&1 | head -10)
echo "$RESPONSE"

echo ""
echo "════════════════════════════════════════════════════════"
echo " All done!  Fine-tuned model: ${OLLAMA_MODEL_NAME}"
echo ""
echo " To use it in Spyder, add to .env:"
echo "   OLLAMA_FINANCE_MODEL=${OLLAMA_MODEL_NAME}"
echo "   OLLAMA_FAST_MODEL=${OLLAMA_MODEL_NAME}"
echo "════════════════════════════════════════════════════════"
