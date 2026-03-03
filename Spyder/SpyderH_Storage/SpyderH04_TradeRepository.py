#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderH_Storage
Module: SpyderH04_TradeRepository.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Iterator
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import threading
from contextlib import contextmanager

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    LOCAL_IMPORTS = False

try:
    from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
except ImportError:
    DataAccessLayer = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_PAGE_SIZE = 100
MAX_BATCH_SIZE = 1000
TRADE_TABLE_NAME = "trades"


# ==============================================================================
# ENUMS
# ==============================================================================
class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "pending"
    EXECUTED = "executed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TradeSide(Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_OPEN = "buy_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_OPEN = "sell_to_open"
    SELL_TO_CLOSE = "sell_to_close"


class TradeType(Enum):
    """Type of trade instrument."""
    EQUITY = "equity"
    OPTION_CALL = "option_call"
    OPTION_PUT = "option_put"
    SPREAD = "spread"
    COMBO = "combo"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Trade:
    """Trade record structure."""
    trade_id: Optional[str] = None
    order_id: Optional[str] = None
    account_id: str = ""
    symbol: str = ""
    underlying: str = ""
    trade_type: TradeType = TradeType.EQUITY
    side: TradeSide = TradeSide.BUY
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    fees: float = 0.0

    # Execution details
    status: TradeStatus = TradeStatus.PENDING
    executed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    # P&L
    realized_pnl: float = 0.0
    cost_basis: float = 0.0

    # Strategy info
    strategy_name: str = ""
    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None

    # Option-specific
    expiration: Optional[date] = None
    strike: Optional[float] = None
    option_type: Optional[str] = None  # 'call' or 'put'

    # Metadata
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeFilter:
    """Filter criteria for querying trades."""
    account_id: Optional[str] = None
    symbol: Optional[str] = None
    underlying: Optional[str] = None
    strategy_name: Optional[str] = None
    trade_type: Optional[TradeType] = None
    side: Optional[TradeSide] = None
    status: Optional[TradeStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    min_pnl: Optional[float] = None
    max_pnl: Optional[float] = None
    tags: Optional[List[str]] = None


@dataclass
class TradeSummary:
    """Aggregated trade summary statistics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0
    total_pnl: float = 0.0
    total_commission: float = 0.0
    total_fees: float = 0.0
    net_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0


# ==============================================================================
# TRADE REPOSITORY
# ==============================================================================
class TradeRepository:
    """
    Repository for trade data storage and retrieval.

    Provides a clean interface for managing trade records with support for
    CRUD operations, filtering, pagination, and aggregation. Uses the
    DataAccessLayer for database operations.
    """

    def __init__(
        self,
        data_access_layer: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize trade repository.

        Args:
            data_access_layer: Optional DAL instance for database access
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.config = config or {}

        # Database access
        self._dal = data_access_layer
        self._in_memory_store: Dict[str, Trade] = {}
        self._use_memory = self._dal is None

        # Thread safety
        self._lock = threading.RLock()

        # Counters for ID generation
        self._trade_counter = 0

        # Initialize
        if not self._use_memory:
            self._ensure_table_exists()

        self.logger.info(
            f"TradeRepository initialized (mode: {'in-memory' if self._use_memory else 'database'})"
        )

    def _ensure_table_exists(self) -> None:
        """Ensure the trades table exists in the database."""
        if self._dal is None:
            return

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY,
            order_id TEXT,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            underlying TEXT,
            trade_type TEXT,
            side TEXT,
            quantity INTEGER,
            price REAL,
            commission REAL,
            fees REAL,
            status TEXT,
            executed_at TIMESTAMP,
            created_at TIMESTAMP,
            realized_pnl REAL,
            cost_basis REAL,
            strategy_name TEXT,
            strategy_id TEXT,
            signal_id TEXT,
            expiration DATE,
            strike REAL,
            option_type TEXT,
            notes TEXT,
            tags TEXT,
            metadata TEXT
        )
        """
        try:
            self._dal.execute(create_table_sql)
            # Create indexes for common queries
            self._dal.execute("CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id)")
            self._dal.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            self._dal.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_name)")
            self._dal.execute("CREATE INDEX IF NOT EXISTS idx_trades_executed ON trades(executed_at)")
        except Exception as e:
            self.logger.error(f"Error creating trades table: {e}")

    def _generate_trade_id(self) -> str:
        """Generate a unique trade ID."""
        with self._lock:
            self._trade_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"TRD-{timestamp}-{self._trade_counter:06d}"

    def save_trade(self, trade: Trade) -> str:
        """
        Save a trade to the repository.

        Args:
            trade: Trade object to save

        Returns:
            Trade ID of the saved trade
        """
        with self._lock:
            if trade.trade_id is None:
                trade.trade_id = self._generate_trade_id()

            if self._use_memory:
                self._in_memory_store[trade.trade_id] = trade
            else:
                self._save_to_database(trade)

            self.logger.debug(f"Trade saved: {trade.trade_id}")
            return trade.trade_id

    def _save_to_database(self, trade: Trade) -> None:
        """Save trade to database."""
        if self._dal is None:
            return

        sql = """
        INSERT OR REPLACE INTO trades (
            trade_id, order_id, account_id, symbol, underlying,
            trade_type, side, quantity, price, commission, fees,
            status, executed_at, created_at, realized_pnl, cost_basis,
            strategy_name, strategy_id, signal_id, expiration, strike,
            option_type, notes, tags, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            trade.trade_id,
            trade.order_id,
            trade.account_id,
            trade.symbol,
            trade.underlying,
            trade.trade_type.value if isinstance(trade.trade_type, TradeType) else trade.trade_type,
            trade.side.value if isinstance(trade.side, TradeSide) else trade.side,
            trade.quantity,
            trade.price,
            trade.commission,
            trade.fees,
            trade.status.value if isinstance(trade.status, TradeStatus) else trade.status,
            trade.executed_at.isoformat() if trade.executed_at else None,
            trade.created_at.isoformat() if trade.created_at else None,
            trade.realized_pnl,
            trade.cost_basis,
            trade.strategy_name,
            trade.strategy_id,
            trade.signal_id,
            trade.expiration.isoformat() if trade.expiration else None,
            trade.strike,
            trade.option_type,
            trade.notes,
            json.dumps(trade.tags),
            json.dumps(trade.metadata)
        )

        self._dal.execute(sql, params)

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """
        Get a trade by ID.

        Args:
            trade_id: Trade ID to retrieve

        Returns:
            Trade object if found, None otherwise
        """
        with self._lock:
            if self._use_memory:
                return self._in_memory_store.get(trade_id)
            else:
                return self._get_from_database(trade_id)

    def _get_from_database(self, trade_id: str) -> Optional[Trade]:
        """Retrieve trade from database."""
        if self._dal is None:
            return None

        sql = "SELECT * FROM trades WHERE trade_id = ?"
        result = self._dal.fetch_one(sql, (trade_id,))

        if result:
            return self._row_to_trade(result)
        return None

    def _row_to_trade(self, row: Dict[str, Any]) -> Trade:
        """Convert database row to Trade object."""
        return Trade(
            trade_id=row.get('trade_id'),
            order_id=row.get('order_id'),
            account_id=row.get('account_id', ''),
            symbol=row.get('symbol', ''),
            underlying=row.get('underlying', ''),
            trade_type=TradeType(row.get('trade_type', 'equity')),
            side=TradeSide(row.get('side', 'buy')),
            quantity=row.get('quantity', 0),
            price=row.get('price', 0.0),
            commission=row.get('commission', 0.0),
            fees=row.get('fees', 0.0),
            status=TradeStatus(row.get('status', 'pending')),
            executed_at=datetime.fromisoformat(row['executed_at']) if row.get('executed_at') else None,
            created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else datetime.now(),
            realized_pnl=row.get('realized_pnl', 0.0),
            cost_basis=row.get('cost_basis', 0.0),
            strategy_name=row.get('strategy_name', ''),
            strategy_id=row.get('strategy_id'),
            signal_id=row.get('signal_id'),
            expiration=date.fromisoformat(row['expiration']) if row.get('expiration') else None,
            strike=row.get('strike'),
            option_type=row.get('option_type'),
            notes=row.get('notes', ''),
            tags=json.loads(row.get('tags', '[]')),
            metadata=json.loads(row.get('metadata', '{}'))
        )

    def get_trades(
        self,
        filter: Optional[TradeFilter] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        order_by: str = 'executed_at',
        descending: bool = True
    ) -> List[Trade]:
        """
        Get trades with optional filtering and pagination.

        Args:
            filter: Optional filter criteria
            page: Page number (1-indexed)
            page_size: Number of records per page
            order_by: Field to order by
            descending: Sort descending if True

        Returns:
            List of Trade objects matching criteria
        """
        with self._lock:
            if self._use_memory:
                return self._get_trades_from_memory(filter, page, page_size, order_by, descending)
            else:
                return self._get_trades_from_database(filter, page, page_size, order_by, descending)

    def _get_trades_from_memory(
        self,
        filter: Optional[TradeFilter],
        page: int,
        page_size: int,
        order_by: str,
        descending: bool
    ) -> List[Trade]:
        """Get trades from in-memory store."""
        trades = list(self._in_memory_store.values())

        # Apply filters
        if filter:
            trades = [t for t in trades if self._matches_filter(t, filter)]

        # Sort
        if order_by and hasattr(Trade, order_by):
            trades.sort(key=lambda t: getattr(t, order_by) or datetime.min, reverse=descending)

        # Paginate
        start = (page - 1) * page_size
        end = start + page_size

        return trades[start:end]

    def _matches_filter(self, trade: Trade, filter: TradeFilter) -> bool:
        """Check if trade matches filter criteria."""
        if filter.account_id and trade.account_id != filter.account_id:
            return False
        if filter.symbol and trade.symbol != filter.symbol:
            return False
        if filter.underlying and trade.underlying != filter.underlying:
            return False
        if filter.strategy_name and trade.strategy_name != filter.strategy_name:
            return False
        if filter.trade_type and trade.trade_type != filter.trade_type:
            return False
        if filter.side and trade.side != filter.side:
            return False
        if filter.status and trade.status != filter.status:
            return False
        if filter.start_date and trade.executed_at and trade.executed_at < filter.start_date:
            return False
        if filter.end_date and trade.executed_at and trade.executed_at > filter.end_date:
            return False
        if filter.min_pnl is not None and trade.realized_pnl < filter.min_pnl:
            return False
        if filter.max_pnl is not None and trade.realized_pnl > filter.max_pnl:
            return False
        if filter.tags:
            if not any(tag in trade.tags for tag in filter.tags):
                return False
        return True

    def _get_trades_from_database(
        self,
        filter: Optional[TradeFilter],
        page: int,
        page_size: int,
        order_by: str,
        descending: bool
    ) -> List[Trade]:
        """Get trades from database with filtering."""
        if self._dal is None:
            return []

        # Build query
        sql = "SELECT * FROM trades WHERE 1=1"
        params = []

        if filter:
            if filter.account_id:
                sql += " AND account_id = ?"
                params.append(filter.account_id)
            if filter.symbol:
                sql += " AND symbol = ?"
                params.append(filter.symbol)
            if filter.underlying:
                sql += " AND underlying = ?"
                params.append(filter.underlying)
            if filter.strategy_name:
                sql += " AND strategy_name = ?"
                params.append(filter.strategy_name)
            if filter.trade_type:
                sql += " AND trade_type = ?"
                params.append(filter.trade_type.value)
            if filter.side:
                sql += " AND side = ?"
                params.append(filter.side.value)
            if filter.status:
                sql += " AND status = ?"
                params.append(filter.status.value)
            if filter.start_date:
                sql += " AND executed_at >= ?"
                params.append(filter.start_date.isoformat())
            if filter.end_date:
                sql += " AND executed_at <= ?"
                params.append(filter.end_date.isoformat())
            if filter.min_pnl is not None:
                sql += " AND realized_pnl >= ?"
                params.append(filter.min_pnl)
            if filter.max_pnl is not None:
                sql += " AND realized_pnl <= ?"
                params.append(filter.max_pnl)

        # Order and pagination
        order_dir = "DESC" if descending else "ASC"
        sql += f" ORDER BY {order_by} {order_dir}"
        sql += f" LIMIT {page_size} OFFSET {(page - 1) * page_size}"

        results = self._dal.fetch_all(sql, tuple(params))
        return [self._row_to_trade(row) for row in results]

    def update_trade(self, trade: Trade) -> bool:
        """
        Update an existing trade.

        Args:
            trade: Trade object with updated values

        Returns:
            True if update successful
        """
        with self._lock:
            if trade.trade_id is None:
                self.logger.error("Cannot update trade without trade_id")
                return False

            if self._use_memory:
                if trade.trade_id in self._in_memory_store:
                    self._in_memory_store[trade.trade_id] = trade
                    return True
                return False
            else:
                self._save_to_database(trade)
                return True

    def delete_trade(self, trade_id: str) -> bool:
        """
        Delete a trade by ID.

        Args:
            trade_id: Trade ID to delete

        Returns:
            True if deletion successful
        """
        with self._lock:
            if self._use_memory:
                if trade_id in self._in_memory_store:
                    del self._in_memory_store[trade_id]
                    return True
                return False
            else:
                if self._dal is None:
                    return False
                sql = "DELETE FROM trades WHERE trade_id = ?"
                self._dal.execute(sql, (trade_id,))
                return True

    def get_trade_summary(
        self,
        filter: Optional[TradeFilter] = None
    ) -> TradeSummary:
        """
        Get aggregated trade statistics.

        Args:
            filter: Optional filter criteria

        Returns:
            TradeSummary with aggregated statistics
        """
        trades = self.get_trades(filter, page=1, page_size=MAX_BATCH_SIZE)

        summary = TradeSummary()
        summary.total_trades = len(trades)

        if summary.total_trades == 0:
            return summary

        pnls = [t.realized_pnl for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]

        summary.winning_trades = len(winning)
        summary.losing_trades = len(losing)
        summary.break_even_trades = len([p for p in pnls if p == 0])

        summary.total_pnl = sum(pnls)
        summary.total_commission = sum(t.commission for t in trades)
        summary.total_fees = sum(t.fees for t in trades)
        summary.net_pnl = summary.total_pnl - summary.total_commission - summary.total_fees

        summary.avg_pnl_per_trade = summary.total_pnl / summary.total_trades
        summary.win_rate = summary.winning_trades / summary.total_trades if summary.total_trades > 0 else 0

        summary.avg_win = sum(winning) / len(winning) if winning else 0
        summary.avg_loss = abs(sum(losing) / len(losing)) if losing else 0

        total_wins = sum(winning) if winning else 0
        total_losses = abs(sum(losing)) if losing else 0
        summary.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        summary.largest_win = max(pnls) if pnls else 0
        summary.largest_loss = min(pnls) if pnls else 0

        return summary

    def get_trades_by_strategy(
        self,
        strategy_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Get all trades for a specific strategy.

        Args:
            strategy_name: Name of the strategy
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of trades for the strategy
        """
        filter = TradeFilter(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date
        )
        return self.get_trades(filter, page_size=MAX_BATCH_SIZE)

    def get_trades_by_symbol(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Get all trades for a specific symbol.

        Args:
            symbol: Trading symbol
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of trades for the symbol
        """
        filter = TradeFilter(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )
        return self.get_trades(filter, page_size=MAX_BATCH_SIZE)

    def get_recent_trades(self, count: int = 10) -> List[Trade]:
        """
        Get most recent trades.

        Args:
            count: Number of trades to return

        Returns:
            List of most recent trades
        """
        return self.get_trades(page=1, page_size=count, order_by='executed_at', descending=True)

    def to_dataframe(
        self,
        filter: Optional[TradeFilter] = None
    ) -> pd.DataFrame:
        """
        Export trades to pandas DataFrame.

        Args:
            filter: Optional filter criteria

        Returns:
            DataFrame with trade data
        """
        trades = self.get_trades(filter, page_size=MAX_BATCH_SIZE)

        if not trades:
            return pd.DataFrame()

        records = []
        for trade in trades:
            record = asdict(trade)
            # Convert enums to strings
            record['trade_type'] = record['trade_type'].value if hasattr(record['trade_type'], 'value') else record['trade_type']
            record['side'] = record['side'].value if hasattr(record['side'], 'value') else record['side']
            record['status'] = record['status'].value if hasattr(record['status'], 'value') else record['status']
            records.append(record)

        return pd.DataFrame(records)

    def count_trades(self, filter: Optional[TradeFilter] = None) -> int:
        """
        Count trades matching filter criteria.

        Args:
            filter: Optional filter criteria

        Returns:
            Number of matching trades
        """
        with self._lock:
            if self._use_memory:
                trades = list(self._in_memory_store.values())
                if filter:
                    trades = [t for t in trades if self._matches_filter(t, filter)]
                return len(trades)
            else:
                if self._dal is None:
                    return 0
                sql = "SELECT COUNT(*) as cnt FROM trades WHERE 1=1"
                params = []

                if filter:
                    if filter.account_id:
                        sql += " AND account_id = ?"
                        params.append(filter.account_id)
                    if filter.symbol:
                        sql += " AND symbol = ?"
                        params.append(filter.symbol)
                    if filter.strategy_name:
                        sql += " AND strategy_name = ?"
                        params.append(filter.strategy_name)

                result = self._dal.fetch_one(sql, tuple(params))
                return result['cnt'] if result else 0

    def clear_all(self) -> None:
        """Clear all trades from the repository."""
        with self._lock:
            if self._use_memory:
                self._in_memory_store.clear()
            else:
                if self._dal:
                    self._dal.execute("DELETE FROM trades")

            self.logger.warning("All trades cleared from repository")


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "TradeRepository",
    "Trade",
    "TradeFilter",
    "TradeSummary",
    "TradeStatus",
    "TradeSide",
    "TradeType",
]
