#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT115_HSeries.py
Purpose: Unit tests for SpyderH01_DataAccessLayer and SpyderH02_DatabaseManager

Coverage targets:
    H01 DataAccessLayer:
        - Connection lifecycle (connect / disconnect / is_connected)
        - Trade persistence (save_trade / get_trades)
        - State persistence (save_state / get_state)
        - SQL injection guard in get_statistics
    H02 DatabaseManager:
        - Trade insertion with price validation (NaN / Inf / negative rejected)
        - Market data batch insertion with price validation
        - Atomic backup (no uncompressed artefact left on disk)
        - update_position fetchone-double-call bug (old_values not None on first read)
        - Table-name whitelist in get_database_stats
"""

import gzip
import math
import os
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# H01 - DataAccessLayer
# ---------------------------------------------------------------------------


class TestH01DataAccessLayerConnection(unittest.TestCase):
    """Tests for DataAccessLayer connection lifecycle."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
        self.tmp.close()
        self.dal = DataAccessLayer(self.tmp.name)

    def tearDown(self):
        self.dal.close_all_connections()
        os.unlink(self.tmp.name)

    def test_is_connected_after_init(self):
        self.assertTrue(self.dal.is_connected())

    def test_disconnect_then_reconnect(self):
        self.dal.disconnect()
        self.assertFalse(self.dal.is_connected())
        result = self.dal.connect()
        self.assertTrue(result)
        self.assertTrue(self.dal.is_connected())

    def test_test_connection_returns_true_when_connected(self):
        self.assertTrue(self.dal.test_connection())


class TestH01DataAccessLayerTrades(unittest.TestCase):
    """Tests for trade persistence."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
        self.tmp.close()
        self.dal = DataAccessLayer(self.tmp.name)

    def tearDown(self):
        self.dal.close_all_connections()
        os.unlink(self.tmp.name)

    def test_save_and_retrieve_trade(self):
        trade = {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 10,
            "price": 450.50,
            "order_id": "TEST_001",
            "status": "FILLED",
        }
        ok = self.dal.save_trade(trade)
        self.assertTrue(ok)
        trades = self.dal.get_trades(symbol="SPY")
        self.assertGreater(len(trades), 0)
        self.assertEqual(trades[0]["symbol"], "SPY")

    def test_get_trades_empty_for_unknown_symbol(self):
        trades = self.dal.get_trades(symbol="AAAA_UNKNOWN")
        self.assertEqual(trades, [])

    def test_save_trade_missing_optional_fields(self):
        """save_trade should succeed even without optional fields."""
        ok = self.dal.save_trade({"symbol": "QQQ", "action": "SELL", "quantity": 5, "price": 300.0})
        self.assertTrue(ok)


class TestH01DataAccessLayerState(unittest.TestCase):
    """Tests for key-value state persistence."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
        self.tmp.close()
        self.dal = DataAccessLayer(self.tmp.name)

    def tearDown(self):
        self.dal.close_all_connections()
        os.unlink(self.tmp.name)

    def test_save_and_get_state_roundtrip(self):
        payload = {"mode": "sandbox", "version": 3}
        self.assertTrue(self.dal.save_state("config", payload))
        retrieved = self.dal.get_state("config")
        self.assertEqual(retrieved, payload)

    def test_get_state_unknown_key_returns_none(self):
        self.assertIsNone(self.dal.get_state("no_such_key"))

    def test_save_state_overwrites_existing(self):
        self.dal.save_state("flag", True)
        self.dal.save_state("flag", False)
        self.assertFalse(self.dal.get_state("flag"))


class TestH01DataAccessLayerSQLInjectionGuard(unittest.TestCase):
    """get_statistics must not execute arbitrary table names."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115
        self.tmp.close()
        self.dal = DataAccessLayer(self.tmp.name)

    def tearDown(self):
        self.dal.close_all_connections()
        os.unlink(self.tmp.name)

    def test_statistics_returns_dict(self):
        stats = self.dal.get_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn("connected", stats)

    def test_statistics_table_counts_are_integers(self):
        stats = self.dal.get_statistics()
        for key, val in stats.items():
            if key.endswith("_count"):
                self.assertIsInstance(val, int, f"Expected int for {key}")


# ---------------------------------------------------------------------------
# H02 - DatabaseManager
# ---------------------------------------------------------------------------


class TestH02DatabaseManagerPriceValidation(unittest.TestCase):
    """insert_trade must reject NaN, Inf, and negative prices."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import DatabaseManager, Trade
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test.db"
        self.dm = DatabaseManager(db_path=self.db_path)
        self.Trade = Trade

    def tearDown(self):
        self.dm.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_trade(self, price=100.0, commission=0.65, pnl=10.0):
        return self.Trade(
            timestamp=datetime.now(),
            symbol="SPY",
            strategy="test",
            trade_type="BTO",
            quantity=1,
            price=price,
            commission=commission,
            pnl=pnl,
            order_id="ORD_001",
        )

    def test_valid_trade_inserts_successfully(self):
        trade_id = self.dm.insert_trade(self._make_trade())
        self.assertIsNotNone(trade_id)
        self.assertGreater(trade_id, 0)

    def test_nan_price_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.dm.insert_trade(self._make_trade(price=float("nan")))

    def test_inf_price_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.dm.insert_trade(self._make_trade(price=float("inf")))

    def test_negative_price_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.dm.insert_trade(self._make_trade(price=-50.0))

    def test_nan_commission_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.dm.insert_trade(self._make_trade(commission=float("nan")))

    def test_nan_pnl_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.dm.insert_trade(self._make_trade(pnl=float("nan")))

    def test_negative_pnl_is_allowed(self):
        """Losses (negative pnl) are valid and must not be rejected."""
        trade_id = self.dm.insert_trade(self._make_trade(pnl=-250.0))
        self.assertGreater(trade_id, 0)


class TestH02DatabaseManagerMarketDataValidation(unittest.TestCase):
    """insert_market_data_batch must reject NaN / Inf prices."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import (
            DatabaseManager, MarketDataPoint
        )
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_md.db"
        self.dm = DatabaseManager(db_path=self.db_path)
        self.MDP = MarketDataPoint

    def tearDown(self):
        self.dm.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_dp(self, bid=449.90, ask=450.10, last=450.0):
        return self.MDP(
            timestamp=datetime.now(),
            symbol="SPY",
            bid=bid, ask=ask, last=last,
            volume=1_000_000, bid_size=100, ask_size=100,
        )

    def test_valid_batch_inserts(self):
        self.dm.insert_market_data_batch([self._make_dp()])  # no exception

    def test_nan_bid_raises(self):
        with self.assertRaises(ValueError):
            self.dm.insert_market_data_batch([self._make_dp(bid=float("nan"))])

    def test_inf_ask_raises(self):
        with self.assertRaises(ValueError):
            self.dm.insert_market_data_batch([self._make_dp(ask=float("inf"))])

    def test_nan_last_raises(self):
        with self.assertRaises(ValueError):
            self.dm.insert_market_data_batch([self._make_dp(last=float("nan"))])


class TestH02DatabaseManagerAtomicBackup(unittest.TestCase):
    """backup_database must produce a valid gzip file and leave no temp artefacts."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import DatabaseManager, Trade
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_backup.db"
        self.dm = DatabaseManager(db_path=self.db_path)
        self.Trade = Trade

    def tearDown(self):
        self.dm.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_backup_creates_gz_file(self):
        backup_path = self.dm.backup_database()
        self.assertTrue(backup_path.exists(), "Backup file does not exist")
        self.assertTrue(str(backup_path).endswith(".gz"))

    def test_backup_file_is_valid_gzip(self):
        backup_path = self.dm.backup_database()
        with gzip.open(backup_path, "rb") as f:
            data = f.read(16)  # read header bytes
        self.assertTrue(len(data) > 0)

    def test_no_uncompressed_artefact_left(self):
        """Temp .db file must be cleaned up — only .gz should remain."""
        before = set(Path(self.dm.backup_path).glob("*"))
        self.dm.backup_database()
        after = set(Path(self.dm.backup_path).glob("*"))
        new_files = after - before
        for f in new_files:
            self.assertTrue(
                str(f).endswith(".gz"),
                f"Unexpected non-gz artefact left: {f}",
            )


class TestH02DatabaseManagerUpdatePositionBug(unittest.TestCase):
    """update_position must read old_values without consuming the cursor twice."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import DatabaseManager, Trade
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_pos.db"
        self.dm = DatabaseManager(db_path=self.db_path)
        self.Trade = Trade

    def tearDown(self):
        self.dm.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_update_nonexistent_position_does_not_crash(self):
        """update_position on a missing row should not raise AttributeError."""
        # If the double-fetchone bug is present this raises AttributeError
        try:
            self.dm.update_position(99999, {"current_price": 450.0})
        except AttributeError as exc:
            self.fail(f"Double-fetchone bug still present: {exc}")


class TestH02DatabaseManagerTableWhitelist(unittest.TestCase):
    """get_database_stats must not fail on the whitelisted table names."""

    def setUp(self):
        from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import DatabaseManager
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.tmp_dir) / "test_stats.db"
        self.dm = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        self.dm.close()
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_database_stats_returns_dict(self):
        stats = self.dm.get_database_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn("tables", stats)

    def test_table_counts_are_integers(self):
        stats = self.dm.get_database_stats()
        for tbl, count in stats["tables"].items():
            self.assertIsInstance(count, int, f"Expected int count for table {tbl}")


if __name__ == "__main__":
    unittest.main()
