#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderH_Storage
Module: SpyderH08_TradeJournal.py
Purpose: Trade journaling system for tracking decisions and outcomes

Author: Spyder Development Team
Year Created: 2026
Last Updated: 2026-03-17 Time: 00:00:00

Module Description:
    Comprehensive trade journaling system that captures the "why" behind
    trading decisions. Records strategy signals, risk check results,
    execution details, outcomes, and lessons learned. Provides analysis
    and review capabilities for continuous improvement.
    
Features:
    - Automatic journaling of all trades
    - Signal and decision metadata tracking
    - Risk override logging
    - Performance outcome tracking
    - Manual intervention recording
    - Search and filtering capabilities
    - Statistical analysis of journal entries
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


# ==============================================================================
# ENUMS
# ==============================================================================
class TradeOutcome(Enum):
    """Trade outcome classification"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"
    CANCELLED = "cancelled"


class SignalQuality(Enum):
    """Signal quality assessment"""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    UNCERTAIN = "uncertain"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TradeJournalEntry:
    """
    Complete trade journal entry capturing all decision context.
    
    Attributes:
        entry_id: Unique journal entry identifier
        order_id: Associated order ID
        timestamp: Entry creation timestamp
        symbol: Trading symbol
        strategy_name: Name of strategy that generated the signal
        signal_source: Specific signal/indicator that triggered the trade
        signal_strength: Quantified signal strength (0.0 to 1.0)
        signal_quality: Qualitative signal assessment
        entry_reason: Human-readable explanation of why trade was taken
        market_regime: Detected market regime at time of trade
        volatility_regime: Volatility regime classification
        risk_check_result: Outcome of risk validation
        position_size: Actual position size taken
        intended_size: Original intended position size
        size_adjustment_reason: Why size was adjusted (if applicable)
        entry_price: Actual entry price
        target_price: Initial profit target
        stop_loss: Initial stop loss level
        greeks_at_entry: Options Greeks at entry (delta, gamma, vega, theta)
        portfolio_impact: Expected impact on portfolio Greeks/risk
        confidence_level: Trader/system confidence in the trade (0.0 to 1.0)
        manual_override: Was this a manual override? (True/False)
        override_reason: Explanation for manual override
        outcome: Final trade outcome
        exit_price: Actual exit price
        exit_timestamp: Trade exit timestamp
        realized_pnl: Realized profit/loss in dollars
        realized_pnl_pct: Realized profit/loss percentage
        exit_reason: Why the trade was closed
        lesson_learned: Post-trade reflection and lessons
        tags: Custom tags for categorization
        metadata: Additional custom metadata
    """
    # Core Identification
    entry_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    
    # Strategy Context
    strategy_name: str
    signal_source: str
    signal_strength: float
    signal_quality: SignalQuality
    entry_reason: str
    
    # Market Context
    market_regime: str
    volatility_regime: str
    
    # Risk Management
    risk_check_result: str
    position_size: int
    intended_size: int
    size_adjustment_reason: Optional[str] = None
    
    # Pricing
    entry_price: float = 0.0
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    
    # Options Specific
    greeks_at_entry: dict[str, float] = field(default_factory=dict)
    portfolio_impact: dict[str, float] = field(default_factory=dict)
    
    # Decision Making
    confidence_level: float = 0.5
    manual_override: bool = False
    override_reason: Optional[str] = None
    
    # Outcome
    outcome: TradeOutcome = TradeOutcome.PENDING
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    exit_reason: Optional[str] = None
    lesson_learned: Optional[str] = None
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradeJournal:
    """
    Trade journaling system for comprehensive decision tracking.
    
    Example:
        >>> journal = TradeJournal()
        >>> entry = TradeJournalEntry(
        ...     entry_id="TJ_20260317_001",
        ...     order_id="ORD_12345",
        ...     timestamp=datetime.now(),
        ...     symbol="SPY 420C 2026-03-21",
        ...     strategy_name="IronCondor",
        ...     signal_source="IV_RANK_HIGH",
        ...     signal_strength=0.85,
        ...     signal_quality=SignalQuality.STRONG,
        ...     entry_reason="IV rank >80, neutral market regime, high premium",
        ...     market_regime="NEUTRAL",
        ...     volatility_regime="HIGH",
        ...     risk_check_result="PASSED",
        ...     position_size=10,
        ...     intended_size=10,
        ...     entry_price=2.50
        ... )
        >>> journal.add_entry(entry)
        >>> journal.update_outcome(
        ...     entry_id="TJ_20260317_001",
        ...     outcome=TradeOutcome.WIN,
        ...     exit_price=1.25,
        ...     realized_pnl=1250.0,
        ...     exit_reason="Target profit reached",
        ...     lesson_learned="IV crush worked as expected"
        ... )
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the trade journal.
        
        Args:
            db_path: Path to SQLite database (default: data/trade_journal.db)
        """
        self.logger = SpyderLogger.get_logger(__name__)
        
        # Database path
        if db_path is None:
            db_path = "data/trade_journal.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._initialize_database()
        
        self.logger.info(f"TradeJournal initialized with database: {self.db_path}")
    
    def _initialize_database(self) -> None:
        """Initialize the SQLite database schema."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Create trade journal table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trade_journal (
                        entry_id TEXT PRIMARY KEY,
                        order_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        strategy_name TEXT NOT NULL,
                        signal_source TEXT NOT NULL,
                        signal_strength REAL NOT NULL,
                        signal_quality TEXT NOT NULL,
                        entry_reason TEXT NOT NULL,
                        market_regime TEXT NOT NULL,
                        volatility_regime TEXT NOT NULL,
                        risk_check_result TEXT NOT NULL,
                        position_size INTEGER NOT NULL,
                        intended_size INTEGER NOT NULL,
                        size_adjustment_reason TEXT,
                        entry_price REAL NOT NULL,
                        target_price REAL,
                        stop_loss REAL,
                        greeks_at_entry TEXT,
                        portfolio_impact TEXT,
                        confidence_level REAL NOT NULL,
                        manual_override INTEGER NOT NULL,
                        override_reason TEXT,
                        outcome TEXT NOT NULL,
                        exit_price REAL,
                        exit_timestamp TEXT,
                        realized_pnl REAL NOT NULL,
                        realized_pnl_pct REAL NOT NULL,
                        exit_reason TEXT,
                        lesson_learned TEXT,
                        tags TEXT,
                        metadata TEXT
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON trade_journal(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON trade_journal(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategy ON trade_journal(strategy_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_outcome ON trade_journal(outcome)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_order_id ON trade_journal(order_id)")
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}", exc_info=True)
            raise
    
    def add_entry(self, entry: TradeJournalEntry) -> bool:
        """
        Add a new trade journal entry.
        
        Args:
            entry: TradeJournalEntry to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO trade_journal VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    entry.entry_id,
                    entry.order_id,
                    entry.timestamp.isoformat(),
                    entry.symbol,
                    entry.strategy_name,
                    entry.signal_source,
                    entry.signal_strength,
                    entry.signal_quality.value,
                    entry.entry_reason,
                    entry.market_regime,
                    entry.volatility_regime,
                    entry.risk_check_result,
                    entry.position_size,
                    entry.intended_size,
                    entry.size_adjustment_reason,
                    entry.entry_price,
                    entry.target_price,
                    entry.stop_loss,
                    json.dumps(entry.greeks_at_entry),
                    json.dumps(entry.portfolio_impact),
                    entry.confidence_level,
                    1 if entry.manual_override else 0,
                    entry.override_reason,
                    entry.outcome.value,
                    entry.exit_price,
                    entry.exit_timestamp.isoformat() if entry.exit_timestamp else None,
                    entry.realized_pnl,
                    entry.realized_pnl_pct,
                    entry.exit_reason,
                    entry.lesson_learned,
                    json.dumps(entry.tags),
                    json.dumps(entry.metadata)
                ))
                
                conn.commit()
                self.logger.info(f"Journal entry added: {entry.entry_id}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error adding journal entry: {e}", exc_info=True)
            return False
    
    def update_outcome(
        self,
        entry_id: str,
        outcome: TradeOutcome,
        exit_price: Optional[float] = None,
        realized_pnl: float = 0.0,
        realized_pnl_pct: float = 0.0,
        exit_reason: Optional[str] = None,
        lesson_learned: Optional[str] = None
    ) -> bool:
        """
        Update the outcome of a trade journal entry.
        
        Args:
            entry_id: Journal entry ID to update
            outcome: Final trade outcome
            exit_price: Exit price
            realized_pnl: Realized P&L in dollars
            realized_pnl_pct: Realized P&L percentage
            exit_reason: Reason for exit
            lesson_learned: Post-trade lesson
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE trade_journal
                    SET outcome = ?,
                        exit_price = ?,
                        exit_timestamp = ?,
                        realized_pnl = ?,
                        realized_pnl_pct = ?,
                        exit_reason = ?,
                        lesson_learned = ?
                    WHERE entry_id = ?
                """, (
                    outcome.value,
                    exit_price,
                    datetime.now().isoformat(),
                    realized_pnl,
                    realized_pnl_pct,
                    exit_reason,
                    lesson_learned,
                    entry_id
                ))
                
                conn.commit()
                self.logger.info(f"Journal entry updated: {entry_id}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating journal entry: {e}", exc_info=True)
            return False
    
    def get_entry(self, entry_id: str) -> Optional[TradeJournalEntry]:
        """Get a specific journal entry by ID."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM trade_journal WHERE entry_id = ?", (entry_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_entry(row)
                return None
                
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving journal entry: {e}", exc_info=True)
            return None
    
    def get_recent_entries(self, limit: int = 100) -> list[TradeJournalEntry]:
        """Get recent journal entries."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM trade_journal
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                
                return [self._row_to_entry(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving recent entries: {e}", exc_info=True)
            return []
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get journal statistics.
        
        Returns:
            Dictionary with win rate, average P&L, etc.
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Win rate
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                        AVG(realized_pnl) as avg_pnl,
                        SUM(realized_pnl) as total_pnl,
                        MAX(realized_pnl) as best_trade,
                        MIN(realized_pnl) as worst_trade
                    FROM trade_journal
                    WHERE outcome IN ('win', 'loss')
                """)
                
                row = cursor.fetchone()
                
                if row:
                    total, wins, losses, avg_pnl, total_pnl, best, worst = row
                    win_rate = (wins / total * 100) if total > 0 else 0.0
                    
                    return {
                        'total_trades': total or 0,
                        'wins': wins or 0,
                        'losses': losses or 0,
                        'win_rate': win_rate,
                        'average_pnl': avg_pnl or 0.0,
                        'total_pnl': total_pnl or 0.0,
                        'best_trade': best or 0.0,
                        'worst_trade': worst or 0.0
                    }
                    
                return {}
                
        except sqlite3.Error as e:
            self.logger.error(f"Error calculating statistics: {e}", exc_info=True)
            return {}
    
    def _row_to_entry(self, row: sqlite3.Row) -> TradeJournalEntry:
        """Convert SQLite row to TradeJournalEntry."""
        return TradeJournalEntry(
            entry_id=row['entry_id'],
            order_id=row['order_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            symbol=row['symbol'],
            strategy_name=row['strategy_name'],
            signal_source=row['signal_source'],
            signal_strength=row['signal_strength'],
            signal_quality=SignalQuality(row['signal_quality']),
            entry_reason=row['entry_reason'],
            market_regime=row['market_regime'],
            volatility_regime=row['volatility_regime'],
            risk_check_result=row['risk_check_result'],
            position_size=row['position_size'],
            intended_size=row['intended_size'],
            size_adjustment_reason=row['size_adjustment_reason'],
            entry_price=row['entry_price'],
            target_price=row['target_price'],
            stop_loss=row['stop_loss'],
            greeks_at_entry=json.loads(row['greeks_at_entry']) if row['greeks_at_entry'] else {},
            portfolio_impact=json.loads(row['portfolio_impact']) if row['portfolio_impact'] else {},
            confidence_level=row['confidence_level'],
            manual_override=bool(row['manual_override']),
            override_reason=row['override_reason'],
            outcome=TradeOutcome(row['outcome']),
            exit_price=row['exit_price'],
            exit_timestamp=datetime.fromisoformat(row['exit_timestamp']) if row['exit_timestamp'] else None,
            realized_pnl=row['realized_pnl'],
            realized_pnl_pct=row['realized_pnl_pct'],
            exit_reason=row['exit_reason'],
            lesson_learned=row['lesson_learned'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            metadata=json.loads(row['metadata']) if row['metadata'] else {}
        )


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_journal_instance: Optional[TradeJournal] = None


def get_trade_journal() -> TradeJournal:
    """Get the singleton TradeJournal instance."""
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = TradeJournal()
    return _journal_instance


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    # Demo usage
    journal = TradeJournal()
    
    # Create a journal entry
    entry = TradeJournalEntry(
        entry_id="TJ_DEMO_001",
        order_id="ORD_DEMO_001",
        timestamp=datetime.now(),
        symbol="SPY 420C 2026-03-21",
        strategy_name="IronCondor",
        signal_source="IV_RANK_HIGH",
        signal_strength=0.85,
        signal_quality=SignalQuality.STRONG,
        entry_reason="IV rank >80, neutral market regime, high premium available",
        market_regime="NEUTRAL",
        volatility_regime="HIGH",
        risk_check_result="PASSED",
        position_size=10,
        intended_size=10,
        entry_price=2.50,
        confidence_level=0.85
    )
    
    journal.add_entry(entry)
    
    # Update outcome
    journal.update_outcome(
        entry_id="TJ_DEMO_001",
        outcome=TradeOutcome.WIN,
        exit_price=1.25,
        realized_pnl=1250.0,
        realized_pnl_pct=50.0,
        exit_reason="Target profit reached after 2 days",
        lesson_learned="IV crush worked as expected, could have held longer"
    )
    
    # Get statistics
    stats = journal.get_statistics()
    print(f"\nJournal Statistics:")
    print(f"Total Trades: {stats.get('total_trades', 0)}")
    print(f"Win Rate: {stats.get('win_rate', 0):.1f}%")
    print(f"Average P&L: ${stats.get('average_pnl', 0):.2f}")
