#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG24_PnlMetricsResolver.py
Purpose: Pure helpers for dashboard P&L metric normalization and aggregation
"""

from __future__ import annotations

import math
from datetime import date, datetime, tzinfo, timezone
from typing import Any, Iterable


def overlay_period_pnl_summary(
    stats: dict[str, Any],
    pnl_summary: dict[str, Any],
    *,
    preserve_existing_today: bool,
) -> dict[str, Any]:
    """Overlay period P&L buckets onto dashboard stats."""
    merged = dict(stats)
    for period in ("today", "week", "month", "year"):
        try:
            numeric_value = float(pnl_summary.get(period, 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if numeric_value == 0.0:
            continue

        key = f"{period}_pnl"
        if period == "today" and preserve_existing_today:
            existing = str(merged.get(key, "—")).strip()
            if existing not in {"", "—", "-"}:
                continue
        merged[key] = f"${numeric_value:+,.2f}"
    return merged


def normalize_today_worker_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Normalize worker-emitted paper metrics into today_* dashboard keys."""
    enriched = dict(metrics)
    realized_raw = enriched.get("realized_pnl", "")
    if realized_raw and not enriched.get("today_pnl"):
        enriched["today_pnl"] = str(realized_raw)

    win_rate_raw = enriched.get("win_rate")
    if win_rate_raw is not None and not enriched.get("today_win_rate"):
        try:
            win_rate_num = float(str(win_rate_raw).replace("%", ""))
            if win_rate_num <= 1.0:
                win_rate_num *= 100.0
            enriched["today_win_rate"] = f"{win_rate_num:.1f}%"
        except (TypeError, ValueError):
            pass

    if not enriched.get("today_win_loss"):
        try:
            wins = int(enriched.get("winning_trades")) if enriched.get("winning_trades") is not None else None
            losses = int(enriched.get("losing_trades")) if enriched.get("losing_trades") is not None else None
        except (TypeError, ValueError):
            wins = None
            losses = None

        if wins is not None and losses is not None:
            enriched["today_win_loss"] = f"{wins}/{losses}"
        else:
            try:
                total_trades = int(str(enriched.get("total_trades", "0")))
                win_rate = enriched.get("today_win_rate") or win_rate_raw
                win_rate_num = float(str(win_rate).replace("%", ""))
                if win_rate_num <= 1.0:
                    win_rate_num *= 100.0
                wins_inferred = int(round(total_trades * (win_rate_num / 100.0)))
                losses_inferred = max(0, total_trades - wins_inferred)
                if total_trades > 0:
                    enriched["today_win_loss"] = f"{wins_inferred}/{losses_inferred}"
            except (TypeError, ValueError):
                pass

    return enriched


def build_today_trade_analytics(
    trades: Iterable[dict[str, Any]],
    *,
    target_date: date,
    display_tz: tzinfo,
    calmar_mode: str,
    initial_capital: float = 0.0,
    realized_pnl_raw: Any = None,
    max_drawdown_raw: Any = None,
) -> dict[str, Any]:
    """Build today-scoped win/loss and risk metrics from trade records."""
    today_trades = _filter_trades_for_date(trades, target_date=target_date, display_tz=display_tz)
    if not today_trades:
        return {}

    enriched: dict[str, Any] = {}
    wins = sum(1 for trade in today_trades if _coerce_float(trade.get("realized_pnl"), 0.0) > 0.0)
    losses = sum(1 for trade in today_trades if _coerce_float(trade.get("realized_pnl"), 0.0) < 0.0)
    total = wins + losses
    if total > 0:
        enriched["today_win_loss"] = f"{wins}/{losses}"
        enriched["today_win_rate"] = f"{wins / total * 100:.1f}%"

    gross_profit = sum(
        _coerce_float(trade.get("realized_pnl"), 0.0)
        for trade in today_trades
        if _coerce_float(trade.get("realized_pnl"), 0.0) > 0.0
    )
    gross_loss = abs(
        sum(
            _coerce_float(trade.get("realized_pnl"), 0.0)
            for trade in today_trades
            if _coerce_float(trade.get("realized_pnl"), 0.0) < 0.0
        )
    )
    if gross_loss > 0.0:
        enriched["today_profit_factor"] = f"{gross_profit / gross_loss:.2f}"
    elif gross_profit > 0.0:
        enriched["today_profit_factor"] = "∞"

    returns: list[float] = []
    downside: list[float] = []
    for trade in today_trades:
        ret = trade.get("return_on_risk_pct")
        if ret is None:
            pnl = _coerce_float(trade.get("realized_pnl"), 0.0)
            max_loss = _coerce_float(trade.get("max_loss_dollars"), 0.0)
            if max_loss <= 0.0:
                continue
            ret = (pnl / max_loss) * 100.0
        try:
            normalized = float(ret) / 100.0
        except (TypeError, ValueError):
            continue
        returns.append(normalized)
        if normalized < 0.0:
            downside.append(normalized)

    if len(returns) >= 2:
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        std_dev = math.sqrt(max(variance, 0.0))
        if std_dev > 0.0:
            enriched["today_sharpe"] = f"{(mean_return / std_dev) * math.sqrt(len(returns)):.2f}"

        if downside:
            downside_variance = sum(value ** 2 for value in downside) / len(downside)
            downside_std = math.sqrt(max(downside_variance, 0.0))
            if downside_std > 0.0:
                enriched["today_sortino"] = f"{(mean_return / downside_std) * math.sqrt(len(returns)):.2f}"
            elif mean_return > 0.0:
                enriched["today_sortino"] = "∞"
        elif mean_return > 0.0:
            enriched["today_sortino"] = "∞"

    calmar = _compute_calmar(
        today_trades,
        calmar_mode=calmar_mode,
        initial_capital=initial_capital,
        realized_pnl_raw=realized_pnl_raw,
        max_drawdown_raw=max_drawdown_raw,
    )
    if calmar is not None:
        enriched["today_calmar"] = calmar
    return enriched


def _filter_trades_for_date(
    trades: Iterable[dict[str, Any]],
    *,
    target_date: date,
    display_tz: tzinfo,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        trade_dt = _coerce_trade_datetime(trade.get("closed_at") or trade.get("timestamp"), display_tz)
        if trade_dt is None:
            continue
        if trade_dt.date() == target_date:
            filtered.append(trade)
    return filtered


def _coerce_trade_datetime(value: Any, display_tz: tzinfo) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        trade_dt = value
    else:
        text = str(value).strip()
        try:
            trade_dt = datetime.fromisoformat(text)
        except ValueError:
            try:
                trade_dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (TypeError, ValueError, OSError, OverflowError):
                return None
    if trade_dt.tzinfo is None:
        trade_dt = trade_dt.replace(tzinfo=timezone.utc)
    return trade_dt.astimezone(display_tz)


def _compute_calmar(
    today_trades: list[dict[str, Any]],
    *,
    calmar_mode: str,
    initial_capital: float,
    realized_pnl_raw: Any,
    max_drawdown_raw: Any,
) -> str | None:
    if initial_capital <= 0.0:
        return None

    if calmar_mode == "drawdown_value":
        realized_pnl = _coerce_metric_money(realized_pnl_raw)
        max_drawdown_pct = _coerce_drawdown_percent(max_drawdown_raw)
        if max_drawdown_pct > 0.0:
            total_return_pct = (realized_pnl / initial_capital) * 100.0
            return f"{total_return_pct / max_drawdown_pct:.2f}"
        if realized_pnl > 0.0:
            return "∞"
        return None

    running_equity = initial_capital
    peak = initial_capital
    max_drawdown_pct = 0.0
    realized_total = 0.0
    for trade in sorted(today_trades, key=lambda item: str(item.get("closed_at") or item.get("timestamp") or "")):
        pnl = _coerce_float(trade.get("realized_pnl"), 0.0)
        realized_total += pnl
        running_equity += pnl
        if running_equity > peak:
            peak = running_equity
        if peak > 0.0:
            drawdown_pct = (peak - running_equity) / peak * 100.0
            if drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = drawdown_pct

    if max_drawdown_pct > 0.0:
        total_return_pct = (realized_total / initial_capital) * 100.0
        return f"{total_return_pct / max_drawdown_pct:.2f}"
    if realized_total > 0.0:
        return "∞"
    return None


def _coerce_metric_money(value: Any) -> float:
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").replace("+", "")
    return _coerce_float(value, 0.0)


def _coerce_drawdown_percent(value: Any) -> float:
    try:
        drawdown = float(str(value or "0").replace("%", "") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if 0.0 < drawdown < 1.0:
        return drawdown * 100.0
    return drawdown


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
