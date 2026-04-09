#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: collect_finetune_data.py
Purpose: Collect trade decision examples from the Spyder trade repository and
         format them as JSONL instruction-tuning data for Gemma 4 fine-tuning.

Usage:
    python SpyderQ_Scripts/collect_finetune_data.py [--output OUTPUT] [--limit LIMIT] [--strategy STRATEGY]

Output format (each line is JSON):
    {
        "system": "<Spyder system prompt>",
        "user": "<market context + trade setup>",
        "assistant": "<structured trade decision JSON>"
    }

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
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ==============================================================================
# PATH SETUP — allow running from project root
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderH_Storage.SpyderH04_TradeRepository import (
    TradeRepository,
    TradeFilter,
    TradeStatus,
    Trade,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

logger = SpyderLogger.get_logger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "finetune" / "spyder_trades.jsonl"
DEFAULT_LIMIT = 5000

SYSTEM_PROMPT = (
    "You are Spyder, an autonomous SPY options trading system. "
    "Given market conditions, portfolio state, and risk constraints, "
    "you output a structured JSON trade decision covering: "
    "strategy selection, entry parameters, position sizing, "
    "Greeks targets, stop-loss levels, and risk rationale. "
    "Prioritise capital preservation. Never exceed 2% portfolio risk per trade."
)


# ==============================================================================
# HELPERS
# ==============================================================================

def _safe_str(value: Any) -> str:
    """Convert value to string, handling None."""
    return str(value) if value is not None else "N/A"


def trade_to_user_prompt(trade: Trade) -> str:
    """Build a user-style prompt from a trade record.

    This reconstructs the 'question' the model would have been asked at
    trade entry time, using the fields stored in the trade record.
    """
    lines = [
        "Analyse the following trade setup and provide a structured decision:",
        "",
        f"Symbol:        {trade.symbol}",
        f"Underlying:    {trade.underlying or trade.symbol[:3]}",
        f"Trade Type:    {trade.trade_type.value if trade.trade_type else 'N/A'}",
        f"Side:          {trade.side.value if trade.side else 'N/A'}",
        f"Strategy:      {trade.strategy_name or 'N/A'}",
        f"Quantity:      {trade.quantity}",
        f"Entry Price:   {trade.price:.4f}",
    ]
    if trade.strike is not None:
        lines.append(f"Strike:        {trade.strike:.2f}")
    if trade.expiration is not None:
        exp_str = trade.expiration.isoformat() if isinstance(trade.expiration, date) else str(trade.expiration)
        lines.append(f"Expiration:    {exp_str}")
    if trade.option_type:
        lines.append(f"Option Type:   {trade.option_type.upper()}")
    if trade.notes:
        lines.append(f"Notes:         {trade.notes}")
    if trade.metadata:
        for key, val in list(trade.metadata.items())[:5]:
            lines.append(f"{key.capitalize():<15}{val}")
    return "\n".join(lines)


def _pnl_label(pnl: float) -> str:
    if pnl > 50:
        return "WIN"
    elif pnl < -50:
        return "LOSS"
    return "BREAKEVEN"


def trade_to_assistant_response(trade: Trade) -> str:
    """Build the expected assistant JSON response from trade outcome data."""
    decision = {
        "strategy": trade.strategy_name or "unknown",
        "action": trade.side.value if trade.side else "buy",
        "symbol": trade.symbol,
        "quantity": trade.quantity,
        "entry_price": round(trade.price, 4),
        "commission": round(trade.commission, 4),
        "realized_pnl": round(trade.realized_pnl, 2),
        "outcome": _pnl_label(trade.realized_pnl),
        "risk_parameters": {
            "max_loss": round(abs(trade.cost_basis) * 0.5, 2) if trade.cost_basis else None,
            "cost_basis": round(trade.cost_basis, 2),
        },
        "rationale": (
            trade.notes
            or f"Executed {trade.trade_type.value if trade.trade_type else 'trade'} "
            f"via {trade.strategy_name or 'unspecified'} strategy."
        ),
    }
    if trade.strike is not None:
        decision["strike"] = trade.strike
    if trade.option_type:
        decision["option_type"] = trade.option_type
    if trade.expiration is not None:
        exp_str = trade.expiration.isoformat() if isinstance(trade.expiration, date) else str(trade.expiration)
        decision["expiration"] = exp_str
    return json.dumps(decision, ensure_ascii=False)


def trade_to_example(trade: Trade) -> dict[str, str]:
    """Convert a Trade record to an instruction-tuning example dict."""
    return {
        "system": SYSTEM_PROMPT,
        "user": trade_to_user_prompt(trade),
        "assistant": trade_to_assistant_response(trade),
    }


# ==============================================================================
# MAIN COLLECTION LOGIC
# ==============================================================================

def collect_examples(
    db_path: Path | None = None,
    limit: int = DEFAULT_LIMIT,
    strategy_filter: str | None = None,
    min_pnl: float | None = None,
) -> list[dict[str, str]]:
    """Collect trade examples from the repository.

    Args:
        db_path: Path to the SQLite database. If None, uses the configured default.
        limit: Maximum number of examples to collect.
        strategy_filter: If set, only include trades for this strategy name.
        min_pnl: If set, only include trades with realised PnL >= this value.

    Returns:
        List of instruction-tuning example dicts.
    """
    repo = TradeRepository(db_path=str(db_path) if db_path else None)

    filt = TradeFilter(
        status=TradeStatus.FILLED,
        strategy_name=strategy_filter,
        min_pnl=min_pnl,
    )

    trades = repo.get_trades(filters=filt, limit=limit)
    logger.info(f"Fetched {len(trades)} trades from repository")

    examples = []
    skipped = 0
    for trade in trades:
        try:
            if not trade.symbol or trade.quantity == 0:
                skipped += 1
                continue
            examples.append(trade_to_example(trade))
        except Exception as exc:
            logger.warning(f"Skipping trade {trade.trade_id}: {exc}")
            skipped += 1

    logger.info(f"Converted {len(examples)} examples ({skipped} skipped)")
    return examples


def write_jsonl(examples: list[dict[str, str]], output_path: Path) -> None:
    """Write examples to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {len(examples)} examples to {output_path}")


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect Spyder trade data for Gemma 4 fine-tuning"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output JSONL path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Max examples to collect (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--strategy", type=str, default=None,
        help="Filter by strategy name",
    )
    parser.add_argument(
        "--min-pnl", type=float, default=None,
        help="Minimum realised PnL to include a trade",
    )
    parser.add_argument(
        "--db", type=Path, default=None,
        help="Path to SQLite database (uses configured default if omitted)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    examples = collect_examples(
        db_path=args.db,
        limit=args.limit,
        strategy_filter=args.strategy,
        min_pnl=args.min_pnl,
    )

    if not examples:
        logger.warning("No examples collected — check database path and filters")
        sys.exit(1)

    write_jsonl(examples, args.output)
    print(f"\nDone. {len(examples)} examples written to {args.output}")
    print("Next step:")
    print(f"  python SpyderT_Testing/finetune_gemma4_spyder.py --data {args.output}")


if __name__ == "__main__":
    main()
