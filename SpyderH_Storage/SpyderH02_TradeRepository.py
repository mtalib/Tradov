#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderH02_TradeRepository.py
Group: H (Data Storage)
Purpose: Trade history storage and retrieval with SQLite

Description:
This module manages the persistent storage of trade history using SQLite.

Author: Mohamed Talib
Date: 2025-01-27
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import DATABASE_BATCH_SIZE


# ==============================================================================
# TRADE DATA CLASS
# ==============================================================================
@dataclass
class Trade:
    """
    Trade record data class.
    
    Represents a single trade with all relevant information.
    """
    trade_id: str
    symbol: str
    quantity: int
    price: float
    side: str  # 'BUY' or 'SELL'
    timestamp: datetime
    strategy: str = ""
    pnl: float = 0.0
    commission: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'side': self.side,
            'timestamp': self.timestamp.isoformat(),
            'strategy': self.strategy,
            'pnl': self.pnl,
            'commission': self.commission
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trade':
        """Create trade from dictionary."""
        from datetime import datetime
        return cls(
            trade_id=data['trade_id'],
            symbol=data['symbol'],
            quantity=data['quantity'],
            price=data['price'],
            side=data['side'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            strategy=data.get('strategy', ''),
            pnl=data.get('pnl', 0.0),
            commission=data.get('commission', 0.0)
        )



# ==============================================================================
# DATA CLASSES
# ==============================================================================
class TradeRecord:
    """Trade record for database storage"""
    trade_id: str
    strategy: str
    symbol: str
    trade_type: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    commission: float
    slippage: float
    pnl: float
    pnl_percent: float
    mae: Optional[float] = None
    mfe: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

# ==============================================================================
# TRADE REPOSITORY CLASS
# ==============================================================================
class TradeRepository:
    """Repository for storing and retrieving trade data with SQLite"""
    
    def __init__(self, database_path: str = "spyder.db"):
        """Initialize the trade repository"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.database_path = database_path
        self._connection = None
        
        # Initialize schema
        self._initialize_schema()
        
        self.logger.info("Trade repository initialized with SQLite")
    
    def _get_connection(self):
        """Get SQLite connection"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        return self._connection
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _initialize_schema(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE NOT NULL,
                    strategy TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission REAL NOT NULL,
                    slippage REAL NOT NULL,
                    pnl REAL NOT NULL,
                    pnl_percent REAL NOT NULL,
                    mae REAL,
                    mfe REAL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(exit_time)")
    
    def save_trade(self, trade: TradeRecord) -> bool:
        """Save a trade record to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO trades (
                        trade_id, strategy, symbol, trade_type,
                        entry_time, exit_time, entry_price, exit_price,
                        quantity, commission, slippage, pnl, pnl_percent,
                        mae, mfe, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id, trade.strategy, trade.symbol, trade.trade_type,
                    trade.entry_time, trade.exit_time, trade.entry_price, trade.exit_price,
                    trade.quantity, trade.commission, trade.slippage, trade.pnl, trade.pnl_percent,
                    trade.mae, trade.mfe, 
                    json.dumps(trade.metadata) if trade.metadata else None
                ))
                return True
        except Exception as e:
            self.logger.error(f"Failed to save trade: {e}")
            return False
    
    def get_trades(self, strategy: Optional[str] = None, 
                  symbol: Optional[str] = None,
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None,
                  limit: Optional[int] = None) -> List[TradeRecord]:
        """Get trades with optional filters"""
        try:
            with self.get_connection() as conn:
                query = "SELECT * FROM trades WHERE 1=1"
                params = []
                
                if strategy:
                    query += " AND strategy = ?"
                    params.append(strategy)
                
                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)
                
                if start_date:
                    query += " AND exit_time >= ?"
                    params.append(start_date)
                
                if end_date:
                    query += " AND exit_time <= ?"
                    params.append(end_date)
                
                query += " ORDER BY exit_time DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                trades = []
                for row in cursor.fetchall():
                    metadata = json.loads(row['metadata']) if row['metadata'] else None
                    trade = TradeRecord(
                        trade_id=row['trade_id'],
                        strategy=row['strategy'],
                        symbol=row['symbol'],
                        trade_type=row['trade_type'],
                        entry_time=datetime.fromisoformat(row['entry_time']),
                        exit_time=datetime.fromisoformat(row['exit_time']),
                        entry_price=row['entry_price'],
                        exit_price=row['exit_price'],
                        quantity=row['quantity'],
                        commission=row['commission'],
                        slippage=row['slippage'],
                        pnl=row['pnl'],
                        pnl_percent=row['pnl_percent'],
                        mae=row['mae'],
                        mfe=row['mfe'],
                        metadata=metadata
                    )
                    trades.append(trade)
                
                return trades
                
        except Exception as e:
            self.logger.error(f"Failed to get trades: {e}")
            return []
    
    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_repository_instance = None

def get_trade_repository() -> TradeRepository:
    """Get singleton instance of trade repository"""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = TradeRepository()
    return _repository_instance


__all__ = ["Trade", "TradeRepository"]