#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR16_PaperSandboxReplay.py
Purpose: Legacy deferred replay service (disabled by live-only policy).

This module is kept for import compatibility only. Runtime creation of the
replay service is intentionally disabled so paper workflows never target
Tradier sandbox endpoints.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    OrderClass,
    OrderDuration,
    OrderSide,
    OrderType,
    TradierAPIError,
    TradierClient,
    TradingEnvironment,
)


logger = SpyderLogger.get_logger("SpyderR16_PaperSandboxReplay")


@dataclass
class DeferredReplayOrder:
    """Serializable deferred sandbox replay order."""

    replay_id: str
    created_at: str
    position_id: str
    strategy: str
    reason: str
    option_symbol: str
    side: str
    quantity: int
    tag: str
    status: str = "pending"  # pending | sent | failed
    attempts: int = 0
    tradier_order_id: str = ""
    last_error: str = ""
    last_attempt_at: str = ""


class PaperSandboxReplay:
    """Persistent deferred queue for sandbox order replay."""

    def __init__(
        self,
        client: TradierClient,
        queue_path: Path,
        reports_dir: Path,
    ) -> None:
        self._client = client
        self._queue_path = queue_path
        self._reports_dir = reports_dir
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _load_queue(self) -> list[DeferredReplayOrder]:
        if not self._queue_path.exists():
            return []
        try:
            raw = json.loads(self._queue_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            records: list[DeferredReplayOrder] = []
            for item in raw:
                if isinstance(item, dict):
                    records.append(DeferredReplayOrder(**item))
            return records
        except Exception as exc:
            logger.warning("Deferred replay queue read failed: %s", exc)
            return []

    def _save_queue(self, queue: list[DeferredReplayOrder]) -> None:
        payload = [asdict(item) for item in queue]
        self._queue_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def enqueue_close_legs(
        self,
        position_id: str,
        strategy: str,
        reason: str,
        legs: list[dict[str, Any]],
        contracts: int,
    ) -> int:
        """Queue one deferred sandbox order per leg for a simulated close."""
        queue = self._load_queue()
        created = 0
        now = self._utc_now_iso()
        for leg in legs:
            option_symbol = str(leg.get("option_symbol") or "").strip()
            side = str(leg.get("side") or "").strip().lower()
            if not option_symbol or side not in {"short", "long"}:
                continue
            close_side = "buy_to_close" if side == "short" else "sell_to_close"
            replay_id = f"RPL-{position_id}-{created+1}"
            tag = f"ppr-{position_id[:12]}-{created+1}"
            queue.append(
                DeferredReplayOrder(
                    replay_id=replay_id,
                    created_at=now,
                    position_id=position_id,
                    strategy=strategy,
                    reason=reason,
                    option_symbol=option_symbol,
                    side=close_side,
                    quantity=max(1, int(contracts)),
                    tag=tag,
                )
            )
            created += 1

        if created > 0:
            self._save_queue(queue)
            logger.info(
                "Deferred sandbox replay queued %d order(s) for %s (%s)",
                created,
                position_id,
                strategy,
            )
        return created

    def flush(self, max_records: int = 50) -> dict[str, Any]:
        """Replay pending queue items to Tradier sandbox and write a report."""
        queue = self._load_queue()
        pending = [q for q in queue if q.status in {"pending", "failed"}]
        to_process = pending[: max(0, int(max_records))]

        sent = 0
        failed = 0
        skipped = max(0, len(pending) - len(to_process))

        for item in to_process:
            item.attempts += 1
            item.last_attempt_at = self._utc_now_iso()
            try:
                side = OrderSide(item.side)
                resp = self._client.place_order(
                    symbol=item.option_symbol,
                    side=side,
                    quantity=int(item.quantity),
                    order_type=OrderType.MARKET,
                    duration=OrderDuration.DAY,
                    order_class=OrderClass.OPTION,
                    tag=item.tag,
                )
                order_block = (resp or {}).get("order", {}) if isinstance(resp, dict) else {}
                tradier_order_id = str(order_block.get("id") or "")
                item.status = "sent"
                item.tradier_order_id = tradier_order_id
                item.last_error = ""
                sent += 1
            except (ValueError, TradierAPIError, Exception) as exc:
                item.status = "failed"
                item.last_error = str(exc)
                failed += 1

        self._save_queue(queue)

        report = {
            "generated_at": self._utc_now_iso(),
            "queue_path": str(self._queue_path),
            "processed": len(to_process),
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "pending_total": len([q for q in queue if q.status in {"pending", "failed"}]),
        }
        report_path = self._reports_dir / (
            f"sandbox_replay_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.json"
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
        return report


def create_paper_sandbox_replay_from_env() -> PaperSandboxReplay | None:
    """Disabled under policy: paper flows must never target Tradier sandbox."""
    enabled = str(os.environ.get("SPYDER_DEFERRED_SANDBOX_REPLAY_ENABLED", "false")).lower()
    if enabled in {"1", "true", "yes", "on"}:
        logger.warning(
            "Deferred sandbox replay requested but disabled by live-only policy",
        )
    return None


__all__ = [
    "DeferredReplayOrder",
    "PaperSandboxReplay",
    "create_paper_sandbox_replay_from_env",
]
