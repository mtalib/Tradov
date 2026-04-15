#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR08_PaperTradingQtWorker.py
Purpose: Qt-threaded paper trading worker (extracted from SpyderG05)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-15

Module Description:
    Background QThread worker that runs a simple paper trading loop against
    live Tradier market data. Relocated from SpyderG05_TradingDashboard.py
    per audit §4 so the dashboard layer no longer owns trading-engine logic.
    Behavior is preserved exactly — this is a mechanical move, not a rewrite.

    The deeper goal of wrapping SpyderR02_PaperEngine with a Qt adapter is
    deferred until R02's API is aligned with this worker's needs (R02 uses
    plain threading and different dataclasses; converging the two requires
    contract negotiation beyond a GUI-scoped extraction).
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, Signal

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
    TradierClient,
    TradingEnvironment,
)


class PaperTradingQtWorker(QObject):
    """Runs paper trading with real Tradier market data in a background QThread.

    Polls SPY quotes from Tradier (sandbox or live) every poll_interval seconds,
    maintains a price history buffer, runs a simple momentum strategy, and
    tracks paper positions and P&L.  Emits Qt signals for the dashboard to
    display status, positions, and metrics in real time.
    """

    status_update = Signal(str)       # log messages for the system log
    position_update = Signal(dict)    # current positions + account state
    metrics_update = Signal(dict)     # P&L metrics for the paper P&L widget
    error = Signal(str)               # error messages
    stopped = Signal()                # emitted when the loop exits
    connection_ready = Signal(bool)   # True when Tradier connection verified

    POLL_INTERVAL = 30
    HISTORY_SIZE = 100
    MOMENTUM_THRESHOLD = 0.001  # 0.1% for 30-sec samples
    SHORT_MA_WINDOW = 5     # 5 x 30s = 2.5 min
    LONG_MA_WINDOW = 20     # 20 x 30s = 10 min

    def __init__(self, initial_capital: float = 100_000.0):
        super().__init__()
        self._running = False
        self._initial_capital = initial_capital

        self._cash = initial_capital
        self._position_qty = 0
        self._position_avg_price = 0.0
        self._total_commissions = 0.0
        self._trades_executed = 0
        self._winning_trades = 0
        self._losing_trades = 0
        self._total_realized_pnl = 0.0
        self._peak_equity = initial_capital
        self._max_drawdown = 0.0

        self._price_history: list[float] = []

        self._client = None

    def run(self):
        """Main paper trading loop — called when QThread starts."""
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            api_key = os.environ.get("TRADIER_API_KEY", "")
            account_id = os.environ.get("TRADIER_ACCOUNT_ID", "")
            env = os.environ.get("TRADIER_ENVIRONMENT", "sandbox")

            if not api_key or not account_id:
                self.error.emit(
                    "TRADIER_API_KEY and TRADIER_ACCOUNT_ID must be set in .env\n"
                    "Paper trading requires Tradier sandbox credentials.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.status_update.emit(f"Connecting to Tradier ({env})…")

            env_enum = (
                TradingEnvironment.LIVE
                if env.lower() == "live"
                else TradingEnvironment.SANDBOX
            )
            self._client = TradierClient(
                api_key=api_key,
                account_id=account_id,
                environment=env_enum,
            )

            if not self._client.test_connection():
                self.error.emit(
                    f"Failed to connect to Tradier API ({env}).\n"
                    "Check your API key and account ID.",
                )
                self.connection_ready.emit(False)
                self.stopped.emit()
                return

            self.connection_ready.emit(True)
            mode_label = "SANDBOX" if env == "sandbox" else "LIVE"
            self.status_update.emit(f"✅ Connected to Tradier ({mode_label})")
            self.status_update.emit(
                f"Paper trading started — ${self._initial_capital:,.0f} capital | "
                f"Polling every {self.POLL_INTERVAL}s",
            )

            self._running = True
            self._price_history = []

            while self._running:
                try:
                    self._poll_and_trade()
                except Exception as e:
                    self.status_update.emit(f"⚠️ Poll error: {e}")

                # Sleep in small increments so stop() is responsive
                for _ in range(self.POLL_INTERVAL * 10):
                    if not self._running:
                        break
                    time.sleep(0.1)

            self._emit_metrics()
            self.status_update.emit("Paper trading stopped")
            self.stopped.emit()

        except Exception as e:
            self.error.emit(f"Paper trading failed: {e}")
            self.stopped.emit()

    def stop(self):
        """Signal the trading loop to stop."""
        self._running = False

    def _poll_and_trade(self):
        """Fetch current SPY quote, run strategy, execute paper trades."""
        if not self._client:
            return

        try:
            resp = self._client.get_quotes(["SPY"])
            quote = resp.get("quotes", {}).get("quote", {})
            if isinstance(quote, list):
                quote = quote[0]
        except Exception as e:
            self.status_update.emit(f"⚠️ Quote fetch failed: {e}")
            return

        last_price = float(quote.get("last", 0))
        bid = float(quote.get("bid", 0))
        ask = float(quote.get("ask", 0))

        if last_price <= 0:
            return

        self._price_history.append(last_price)
        if len(self._price_history) > self.HISTORY_SIZE:
            self._price_history = self._price_history[-self.HISTORY_SIZE:]

        self._update_position_mtm(last_price)

        if len(self._price_history) >= self.LONG_MA_WINDOW:
            signal = self._generate_signal()
            if signal == "BUY" and self._position_qty == 0:
                self._execute_paper_buy(ask if ask > 0 else last_price)
            elif signal == "SELL" and self._position_qty > 0:
                self._execute_paper_sell(bid if bid > 0 else last_price)

        self._emit_position_update(last_price, bid, ask)
        self._emit_metrics()

    def _generate_signal(self) -> str | None:
        """Simple dual moving average crossover on poll-interval prices."""
        prices = self._price_history
        if len(prices) < self.LONG_MA_WINDOW:
            return None

        short_ma = sum(prices[-self.SHORT_MA_WINDOW:]) / self.SHORT_MA_WINDOW
        long_ma = sum(prices[-self.LONG_MA_WINDOW:]) / self.LONG_MA_WINDOW

        if long_ma <= 0:
            return None

        ratio = (short_ma - long_ma) / long_ma

        if ratio > self.MOMENTUM_THRESHOLD:
            return "BUY"
        if ratio < -self.MOMENTUM_THRESHOLD:
            return "SELL"
        return None

    def _execute_paper_buy(self, fill_price: float):
        """Execute a paper buy — 100 shares of SPY."""
        shares = 100
        cost = shares * fill_price
        commission = 0.0

        if cost > self._cash:
            shares = int(self._cash / fill_price)
            if shares <= 0:
                return
            cost = shares * fill_price

        self._cash -= cost + commission
        self._position_qty += shares
        self._position_avg_price = fill_price
        self._total_commissions += commission
        self._trades_executed += 1

        self.status_update.emit(
            f"📈 BUY {shares} SPY @ ${fill_price:.2f} | "
            f"Cost: ${cost:,.2f} | Cash: ${self._cash:,.2f}",
        )

    def _execute_paper_sell(self, fill_price: float):
        """Execute a paper sell — close entire position."""
        if self._position_qty <= 0:
            return

        shares = self._position_qty
        proceeds = shares * fill_price
        commission = 0.0

        pnl = (fill_price - self._position_avg_price) * shares - commission
        self._total_realized_pnl += pnl
        self._cash += proceeds - commission
        self._total_commissions += commission
        self._trades_executed += 1

        if pnl > 0:
            self._winning_trades += 1
        else:
            self._losing_trades += 1

        self.status_update.emit(
            f"📉 SELL {shares} SPY @ ${fill_price:.2f} | "
            f"P&L: ${pnl:+,.2f} | Cash: ${self._cash:,.2f}",
        )

        self._position_qty = 0
        self._position_avg_price = 0.0

    def _update_position_mtm(self, current_price: float):
        """Update peak equity and max drawdown."""
        equity = self._cash + self._position_qty * current_price
        self._peak_equity = max(self._peak_equity, equity)
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        self._max_drawdown = max(self._max_drawdown, drawdown)

    def _emit_position_update(self, last: float, bid: float, ask: float):
        """Emit current position state to the dashboard."""
        unrealized_pnl = 0.0
        if self._position_qty > 0:
            unrealized_pnl = (last - self._position_avg_price) * self._position_qty

        equity = self._cash + self._position_qty * last

        self.position_update.emit({
            "spy_last": last,
            "spy_bid": bid,
            "spy_ask": ask,
            "position_qty": self._position_qty,
            "position_avg_price": self._position_avg_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": self._total_realized_pnl,
            "cash": self._cash,
            "equity": equity,
            "initial_capital": self._initial_capital,
        })

    def _emit_metrics(self):
        """Emit performance metrics for the paper P&L widget."""
        equity = self._cash
        if self._position_qty > 0 and self._price_history:
            equity += self._position_qty * self._price_history[-1]

        total_return = equity - self._initial_capital
        return_pct = (total_return / self._initial_capital) * 100 if self._initial_capital > 0 else 0
        win_rate = (
            self._winning_trades / self._trades_executed
            if self._trades_executed > 0 else 0
        )

        self.metrics_update.emit({
            "total_return": f"{return_pct:.2f}%",
            "max_drawdown": f"{self._max_drawdown:.4f}",
            "win_rate": f"{win_rate:.4f}",
            "total_trades": str(self._trades_executed),
            "realized_pnl": f"${self._total_realized_pnl:+,.2f}",
            "equity": f"${equity:,.2f}",
        })


__all__ = ["PaperTradingQtWorker"]
