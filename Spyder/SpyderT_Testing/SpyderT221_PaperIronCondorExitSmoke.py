#!/usr/bin/env python3
"""Focused paper-mode smoke for Iron Condor exit flow."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from Spyder.SpyderD_Strategies.SpyderD02_IronCondor import IronCondorStrategy
from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor


def _make_mock_broker(account_id: str = 'PAPER-ACCOUNT'):
    broker = MagicMock()
    broker.is_connected.return_value = True
    broker.get_account_info.return_value = {
        'account_id': account_id,
        'trading_enabled': True,
        'buying_power': 100_000.0,
    }
    broker.get_positions.return_value = []
    broker.get_account_balances.return_value = {'account': {'balance': 100000.0}}
    broker.heartbeat.return_value = True
    broker.cancel_order.return_value = True
    broker.close_position.return_value = True
    broker._last_prices = {}
    return broker


def _make_mock_risk_manager():
    risk_manager = MagicMock()
    risk_manager.check_daily_limits.return_value = True
    return risk_manager


def _make_paper_engine(account_id: str = 'PAPER-ACCOUNT'):
    from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine, LiveTradingConfig, TradingMode

    config = LiveTradingConfig(account_id=account_id)
    broker = _make_mock_broker(account_id)
    risk_manager = _make_mock_risk_manager()
    engine = LiveEngine(broker, risk_manager, config)
    engine.mode = TradingMode.PAPER
    return engine, broker


class _StrategyEventManagerStub:
    def subscribe(self, *_args, **_kwargs):
        return None

    def emit(self, *_args, **_kwargs):
        return None

    def publish(self, *_args, **_kwargs):
        return None


class _ExitEventManagerStub:
    def __init__(self) -> None:
        self.emitted: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:  # noqa: ANN003
        self.emitted.append(kwargs)


def test_paper_iron_condor_short_leg_smoke_flow() -> None:
    from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB

    with TemporaryDirectory() as tmpdir:
        db = TradingSessionDB(Path(tmpdir) / 'paper_iron_condor_smoke.db')
        engine, broker = _make_paper_engine()
        engine.set_session_db(db)

        symbol = 'SPY260619P00540000'
        entry_price = 8.5843
        mark_price = 4.2921

        engine.pending_orders = {
            'ORD-OPEN-1': {
                'order': {
                    'symbol': symbol,
                    'quantity': 1,
                    'side': 'sell_to_open',
                    'strategy': 'iron_condor',
                    'expiration': '2026-06-19',
                    'option_type': 'put',
                }
            }
        }

        engine._on_position_updated(
            MagicMock(
                source='PositionTracker',
                data={
                    'symbol': symbol,
                    'quantity': -1,
                    'fill_price': entry_price,
                    'order_id': 'ORD-OPEN-1',
                    'position': {
                        'average_fill_price': entry_price,
                        'expiration': '2026-06-19',
                        'option_type': 'put',
                        'strategy': 'iron_condor',
                    },
                },
            )
        )

        assert engine.active_positions[symbol]['quantity'] == -1
        open_rows = db.get_open_positions()
        assert len(open_rows) == 1
        assert open_rows[0]['symbol'] == symbol
        assert open_rows[0]['status'] == 'OPEN'

        broker._last_prices = {symbol: mark_price}
        engine._monitor_positions()

        open_rows = db.get_open_positions()
        latest_snapshot = db.get_latest_snapshot()
        assert len(open_rows) == 1
        assert open_rows[0]['symbol'] == symbol
        assert round(open_rows[0]['unrealized_pnl'], 2) == 429.22
        assert latest_snapshot is not None
        assert round(latest_snapshot['unrealized_pnl'], 2) == 429.22
        assert round(latest_snapshot['equity'], 2) == 100429.22

        strategy = IronCondorStrategy(event_manager=_StrategyEventManagerStub(), config={})
        exit_event_manager = _ExitEventManagerStub()
        monitor = create_exit_monitor(
            portfolio_manager=None,
            strategy_map={'iron_condor': strategy},
            event_manager=exit_event_manager,
            positions_provider=engine.get_active_positions_snapshot,
        )

        monitor._sweep_once()

        assert len(exit_event_manager.emitted) == 1
        close_event = exit_event_manager.emitted[0]
        close_data = close_event['data']
        assert close_data['action'] == 'close'
        assert close_data['symbol'] == symbol
        assert close_data['side'] == 'buy'
        assert close_data['quantity'] == 1

        engine.pending_orders['ORD-CLOSE-1'] = {
            'order': {
                'symbol': symbol,
                'quantity': 1,
                'side': 'buy_to_close',
                'strategy': 'iron_condor',
                'expiration': '2026-06-19',
                'option_type': 'put',
            }
        }

        engine._on_reconciler_fill(
            MagicMock(
                source='FillReconciler',
                data={
                    'order_id': 'ORD-CLOSE-1',
                    'quantity': 1,
                    'raw': {
                        'id': 'PAPER-CLOSE-1',
                        'symbol': symbol,
                        'avg_fill_price': mark_price,
                        'quantity': 1,
                        'transaction_date': '2026-05-14T19:22:05+00:00',
                    },
                },
            )
        )

        engine._on_position_updated(
            MagicMock(
                source='PositionTracker',
                data={
                    'symbol': symbol,
                    'quantity': 0,
                    'fill_price': mark_price,
                    'order_id': 'ORD-CLOSE-1',
                },
            )
        )

        engine._monitor_positions()

        recent_trade = db.get_recent_trades(limit=1)[0]
        latest_snapshot = db.get_latest_snapshot()
        open_rows = db.get_open_positions()

        assert open_rows == []
        assert recent_trade['symbol'] == symbol
        assert round(recent_trade['realized_pnl'], 2) == 429.22
        assert latest_snapshot is not None
        assert round(latest_snapshot['realized_pnl'], 2) == 429.22
        assert round(latest_snapshot['unrealized_pnl'], 2) == 0.0
        assert round(latest_snapshot['equity'], 2) == 100429.22

        with db._connect() as conn:
            row = conn.execute(
                'SELECT status, current_price, realized_pnl FROM positions WHERE position_id = ?',
                (f'paper:{symbol}',),
            ).fetchone()

        assert row is not None
        assert row['status'] == 'CLOSED'
        assert round(row['current_price'], 4) == round(mark_price, 4)
        assert round(row['realized_pnl'], 2) == 429.22
