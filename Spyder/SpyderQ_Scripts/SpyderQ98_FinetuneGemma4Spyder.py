#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: finetune_gemma4_spyder.py
Purpose: QLoRA fine-tuning script for Gemma 4 (e4b) on Spyder trade decision data.
         Uses HuggingFace TRL SFTTrainer with 4-bit quantisation via bitsandbytes.

Requirements:
    pip install transformers trl peft bitsandbytes datasets accelerate

Hardware recommendation:
    - GPU with >= 8 GB VRAM for gemma4:e4b (3B effective parameters)
    - CPU-only is possible but very slow (hours per epoch)

Usage:
    python SpyderT_Testing/finetune_gemma4_spyder.py --data data/finetune/spyder_trades.jsonl

HuggingFace base model id: google/gemma-3-4b-it  (same weights as gemma4:e4b in Ollama)

Author: Spyder
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ==============================================================================
# PATH SETUP
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_BASE_MODEL = "google/gemma-3-4b-it"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "models" / "gemma4-spyder-e4b"
DEFAULT_EPOCHS = 3
DEFAULT_BATCH_SIZE = 2          # CPU-safe; increase to 4-8 on GPU
DEFAULT_GRAD_ACCUM = 8          # effective batch = batch_size × grad_accum
DEFAULT_LR = 2e-4
DEFAULT_MAX_SEQ_LEN = 2048
DEFAULT_LORA_R = 16
DEFAULT_LORA_ALPHA = 32
DEFAULT_LORA_DROPOUT = 0.05


# ==============================================================================
# DATA LOADING
# ==============================================================================

def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file and return list of dicts."""
    examples = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                examples.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(f"Skipping line {line_no}: {exc}")
    logger.info(f"Loaded {len(examples)} examples from {path}")
    return examples


def format_chat_prompt(example: dict) -> str:
    """Format an example dict into a Gemma 4 chat prompt string.

    Gemma 4 uses the standard ChatML-style format with <start_of_turn> markers.
    """
    system = example.get("system", "")
    user = example.get("user", "")
    assistant = example.get("assistant", "")

    parts = []
    if system:
        parts.append(f"<start_of_turn>system\n{system}<end_of_turn>")
    parts.append(f"<start_of_turn>user\n{user}<end_of_turn>")
    parts.append(f"<start_of_turn>model\n{assistant}<end_of_turn>")
    return "\n".join(parts)


# ==============================================================================
# TRAINING
# ==============================================================================

def run_finetune(
    data_path: Path,
    output_dir: Path,
    base_model: str = DEFAULT_BASE_MODEL,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    grad_accum: int = DEFAULT_GRAD_ACCUM,
    lr: float = DEFAULT_LR,
    max_seq_len: int = DEFAULT_MAX_SEQ_LEN,
    lora_r: int = DEFAULT_LORA_R,
    lora_alpha: int = DEFAULT_LORA_ALPHA,
    lora_dropout: float = DEFAULT_LORA_DROPOUT,
    hf_token: str | None = None,
    dry_run: bool = False,
) -> None:
    """Run QLoRA fine-tuning using TRL SFTTrainer.

    Args:
        data_path: Path to .jsonl training data.
        output_dir: Directory to write checkpoints and final adapter.
        base_model: HuggingFace model id for the base model.
        epochs: Number of training epochs.
        batch_size: Per-device training batch size.
        grad_accum: Gradient accumulation steps.
        lr: Peak learning rate.
        max_seq_len: Maximum token sequence length.
        lora_r: LoRA rank.
        lora_alpha: LoRA scaling factor.
        lora_dropout: LoRA dropout probability.
        hf_token: HuggingFace access token (required for gated models like Gemma).
        dry_run: If True, validate setup without training.
    """
    # ---- late imports so the script can be imported without heavy deps ----
    try:
        import torch
        from datasets import Dataset
        from transformers import (
            AutoTokenizer,
            AutoModelForCausalLM,
            BitsAndBytesConfig,
        )
        from peft import LoraConfig, get_peft_model, TaskType
        from trl import SFTTrainer, SFTConfig
    except ImportError as exc:
        logger.error(
            f"Missing dependency: {exc}\n"
            "Install with: pip install transformers trl peft bitsandbytes datasets accelerate"
        )
        sys.exit(1)

    # ---- load data ----
    raw = load_jsonl(data_path)
    if not raw:
        logger.error("No training examples found — aborting")
        sys.exit(1)

    texts = [format_chat_prompt(ex) for ex in raw]
    dataset = Dataset.from_dict({"text": texts})

    train_val = dataset.train_test_split(test_size=0.05, seed=42)
    train_dataset = train_val["train"]
    eval_dataset  = train_val["test"]
    logger.info(f"Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

    if dry_run:
        logger.info("Dry-run mode — skipping training. Setup looks valid.")
        print(f"\nSample formatted prompt:\n{texts[0][:800]}\n...")
        return

    # ---- tokeniser ----
    tokenizer = AutoTokenizer.from_pretrained(
        base_model,
        token=hf_token,
        trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # ---- 4-bit quantisation config ----
    use_4bit = torch.cuda.is_available()
    bnb_config = None
    if use_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        logger.info("Using 4-bit QLoRA (GPU detected)")
    else:
        logger.info("No GPU detected — loading in fp32 (CPU, slow)")

    # ---- base model ----
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto" if use_4bit else "cpu",
        token=hf_token,
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    # ---- LoRA config ----
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ---- training arguments ----
    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = SFTConfig(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        max_seq_length=max_seq_len,
        logging_dir=str(output_dir / "logs"),
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        load_best_model_at_end=True,
        report_to="none",   # disable wandb/tensorboard by default
        dataset_text_field="text",
    )

    # ---- trainer ----
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
    )

    logger.info("Starting fine-tuning …")
    trainer.train()

    # ---- save LoRA adapter ----
    adapter_dir = output_dir / "adapter"
    trainer.model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    logger.info(f"LoRA adapter saved to {adapter_dir}")

    print(f"\nTraining complete. Adapter saved to {adapter_dir}")
    print("Next step:")
    print(f"  bash SpyderQ_Scripts/export_to_ollama.sh {adapter_dir}")


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="QLoRA fine-tune Gemma 4 e4b on Spyder trade data"
    )
    parser.add_argument(
        "--data", type=Path, required=True,
        help="Path to training JSONL (from collect_finetune_data.py)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for checkpoints (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--base-model", type=str, default=DEFAULT_BASE_MODEL,
        help=f"HuggingFace model id (default: {DEFAULT_BASE_MODEL})",
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--grad-accum", type=int, default=DEFAULT_GRAD_ACCUM)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    parser.add_argument("--max-seq-len", type=int, default=DEFAULT_MAX_SEQ_LEN)
    parser.add_argument("--lora-r", type=int, default=DEFAULT_LORA_R)
    parser.add_argument("--lora-alpha", type=int, default=DEFAULT_LORA_ALPHA)
    parser.add_argument("--lora-dropout", type=float, default=DEFAULT_LORA_DROPOUT)
    parser.add_argument(
        "--hf-token", type=str, default=os.getenv("HUGGINGFACE_TOKEN"),
        help="HuggingFace token (or set HUGGINGFACE_TOKEN env var)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate setup and show sample prompt without training",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.data.exists():
        logger.error(f"Data file not found: {args.data}")
        sys.exit(1)

    run_finetune(
        data_path=args.data,
        output_dir=args.output,
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum=args.grad_accum,
        lr=args.lr,
        max_seq_len=args.max_seq_len,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        hf_token=args.hf_token,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
