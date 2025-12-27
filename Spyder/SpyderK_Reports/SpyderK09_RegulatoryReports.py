#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderK09_RegulatoryReports.py
Group: K (Reports)
Purpose: Compliance and regulatory reporting

Description:
    This module generates comprehensive regulatory and compliance reports including
    trade blotters, position limits compliance checks, risk limit breach reports,
    audit trail documentation, and month-end reconciliation. It ensures all trading
    activities comply with regulatory requirements and provides detailed documentation
    for audits, compliance reviews, and regulatory submissions.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-07
Last Updated: 2025-01-07 Time: 11:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from datetime import datetime, timedelta, date, time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import csv
from pathlib import Path
from collections import defaultdict
import hashlib
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import xlsxwriter

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderB_Broker.SpyderB04_AccountManager import AccountManager
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Regulatory limits
POSITION_LIMITS = {
    'SPY_OPTIONS': 75000,  # Contracts
    'SINGLE_EXPIRY': 25000,  # Contracts per expiry
    'DAILY_VOLUME': 50000,  # Contracts per day
    'NET_DELTA': 100000,  # Delta-adjusted shares
}

RISK_LIMITS = {
    'MAX_LOSS_DAILY': 50000,  # USD
    'MAX_LOSS_WEEKLY': 150000,  # USD
    'MAX_DRAWDOWN': 0.10,  # 10%
    'VAR_LIMIT': 100000,  # 95% VaR limit
    'MARGIN_USAGE': 0.80,  # 80% of available margin
}

# Report types
REPORT_FORMATS = ['PDF', 'CSV', 'EXCEL', 'JSON']

# Audit requirements
AUDIT_RETENTION_DAYS = 2555  # 7 years
AUDIT_FIELDS_REQUIRED = [
    'order_id', 'timestamp', 'symbol', 'quantity', 
    'price', 'side', 'order_type', 'status', 'user_id'
]

# ==============================================================================
# ENUMS
# ==============================================================================
class ComplianceStatus(Enum):
    """Compliance check status"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACH = "breach"
    UNDER_REVIEW = "under_review"

class ReportType(Enum):
    """Types of regulatory reports"""
    TRADE_BLOTTER = "trade_blotter"
    POSITION_LIMITS = "position_limits"
    RISK_LIMITS = "risk_limits"
    AUDIT_TRAIL = "audit_trail"
    RECONCILIATION = "reconciliation"
    COMPLIANCE_SUMMARY = "compliance_summary"

class AuditEventType(Enum):
    """Types of audit events"""
    ORDER_PLACED = "order_placed"
    ORDER_MODIFIED = "order_modified"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    RISK_BREACH = "risk_breach"
    LIMIT_BREACH = "limit_breach"
    SYSTEM_OVERRIDE = "system_override"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TradeBlotterEntry:
    """Single entry in trade blotter"""
    trade_id: str
    order_id: str
    timestamp: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: int
    price: float
    commission: float
    net_amount: float
    account_id: str
    execution_venue: str
    counterparty: Optional[str] = None
    settlement_date: Optional[date] = None
    
@dataclass
class PositionLimitCheck:
    """Position limit compliance check"""
    check_time: datetime
    limit_type: str
    current_value: float
    limit_value: float
    usage_percentage: float
    status: ComplianceStatus
    affected_positions: List[str]
    recommendation: Optional[str] = None
    
@dataclass
class RiskLimitBreach:
    """Risk limit breach event"""
    breach_id: str
    breach_time: datetime
    limit_type: str
    limit_value: float
    actual_value: float
    severity: str  # 'minor', 'major', 'critical'
    positions_affected: List[str]
    action_taken: str
    resolved: bool
    resolution_time: Optional[datetime] = None
    
@dataclass
class AuditTrailEntry:
    """Audit trail entry"""
    audit_id: str
    timestamp: datetime
    event_type: AuditEventType
    user_id: str
    system_id: str
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    hash_previous: Optional[str] = None
    hash_current: str = field(default="")
    
    def __post_init__(self):
        """Calculate hash after initialization"""
        if not self.hash_current:
            self.hash_current = self._calculate_hash()
            
    def _calculate_hash(self) -> str:
        """Calculate hash of audit entry"""
        content = f"{self.audit_id}{self.timestamp}{self.event_type.value}{self.action}"
        if self.hash_previous:
            content += self.hash_previous
        return hashlib.sha256(content.encode()).hexdigest()
        
@dataclass
class ReconciliationResult:
    """Reconciliation result"""
    reconciliation_date: date
    account_id: str
    broker_positions: Dict[str, float]
    system_positions: Dict[str, float]
    discrepancies: List[Dict[str, Any]]
    total_discrepancy_value: float
    status: ComplianceStatus
    notes: Optional[str] = None
    
@dataclass
class ComplianceSummary:
    """Overall compliance summary"""
    report_date: date
    reporting_period: Tuple[date, date]
    total_trades: int
    total_volume: float
    position_limit_checks: List[PositionLimitCheck]
    risk_limit_breaches: List[RiskLimitBreach]
    audit_completeness: float  # Percentage
    reconciliation_status: ComplianceStatus
    overall_status: ComplianceStatus
    issues_requiring_attention: List[str]
    regulatory_filings_due: List[Dict[str, Any]]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RegulatoryReports:
    """
    Regulatory reporting and compliance engine.
    
    This class generates all required regulatory reports, performs compliance checks,
    maintains audit trails, and ensures all trading activities meet regulatory
    requirements. It provides comprehensive documentation for audits and regulatory
    reviews.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        dal: Data access layer for trade and position data
        account_manager: Account management for position data
        risk_manager: Risk management for limit checks
        
    Example:
        >>> reg_reports = RegulatoryReports()
        >>> blotter = reg_reports.generate_trade_blotter(date.today())
        >>> reg_reports.export_trade_blotter(blotter, 'trade_blotter.pdf')
    """
    
    def __init__(self):
        """Initialize the regulatory reports module."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.dal = get_data_access_layer()
        self.account_manager = AccountManager()
        self.risk_manager = get_risk_manager()
        
        # Audit trail chain
        self.audit_chain: List[AuditTrailEntry] = []
        self.last_audit_hash: Optional[str] = None
        
        # Compliance cache
        self.compliance_cache: Dict[str, Any] = {}
        
        self.logger.info("RegulatoryReports initialized")
        
    # ==========================================================================
    # TRADE BLOTTER METHODS
    # ==========================================================================
    def generate_trade_blotter(self, report_date: date, 
                             account_id: Optional[str] = None) -> List[TradeBlotterEntry]:
        """
        Generate trade blotter for specified date.
        
        Args:
            report_date: Date for trade blotter
            account_id: Optional specific account (None for all)
            
        Returns:
            List of TradeBlotterEntry objects
        """
        try:
            # Get trades for the date
            trades = self.dal.get_trades_by_date(report_date, account_id)
            
            blotter_entries = []
            
            for trade in trades:
                # Calculate net amount
                if trade['side'] == 'buy':
                    net_amount = -(trade['quantity'] * trade['price'] + trade['commission'])
                else:
                    net_amount = trade['quantity'] * trade['price'] - trade['commission']
                    
                entry = TradeBlotterEntry(
                    trade_id=trade['trade_id'],
                    order_id=trade['order_id'],
                    timestamp=pd.to_datetime(trade['timestamp']),
                    symbol=trade['symbol'],
                    side=trade['side'],
                    quantity=trade['quantity'],
                    price=trade['price'],
                    commission=trade['commission'],
                    net_amount=net_amount,
                    account_id=trade['account_id'],
                    execution_venue=trade.get('venue', 'SMART'),
                    counterparty=trade.get('counterparty'),
                    settlement_date=report_date + timedelta(days=1)  # T+1 for options
                )
                
                blotter_entries.append(entry)
                
            # Sort by timestamp
            blotter_entries.sort(key=lambda x: x.timestamp)
            
            self.logger.info(f"Generated trade blotter with {len(blotter_entries)} entries for {report_date}")
            
            return blotter_entries
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_trade_blotter',
                'report_date': report_date
            })
            return []
            
    def export_trade_blotter(self, blotter_entries: List[TradeBlotterEntry],
                           output_path: str, format: str = 'PDF') -> bool:
        """
        Export trade blotter to file.
        
        Args:
            blotter_entries: List of blotter entries
            output_path: Output file path
            format: Export format ('PDF', 'CSV', 'EXCEL')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            format = format.upper()
            
            if format == 'PDF':
                return self._export_blotter_pdf(blotter_entries, output_path)
            elif format == 'CSV':
                return self._export_blotter_csv(blotter_entries, output_path)
            elif format == 'EXCEL':
                return self._export_blotter_excel(blotter_entries, output_path)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return False
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'export_trade_blotter',
                'format': format
            })
            return False
            
    # ==========================================================================
    # POSITION LIMITS COMPLIANCE
    # ==========================================================================
    def check_position_limits(self) -> List[PositionLimitCheck]:
        """
        Check current positions against regulatory limits.
        
        Returns:
            List of PositionLimitCheck results
        """
        try:
            checks = []
            current_time = datetime.now()
            
            # Get current positions
            positions = self.account_manager.get_all_positions()
            
            # Check total SPY options position
            total_spy_contracts = sum(
                abs(p['quantity']) for p in positions
                if p['symbol'].startswith('SPY') and p['asset_type'] == 'option'
            )
            
            spy_check = PositionLimitCheck(
                check_time=current_time,
                limit_type='SPY_OPTIONS_TOTAL',
                current_value=total_spy_contracts,
                limit_value=POSITION_LIMITS['SPY_OPTIONS'],
                usage_percentage=(total_spy_contracts / POSITION_LIMITS['SPY_OPTIONS']) * 100,
                status=self._determine_compliance_status(
                    total_spy_contracts, POSITION_LIMITS['SPY_OPTIONS']
                ),
                affected_positions=[p['symbol'] for p in positions if p['symbol'].startswith('SPY')],
                recommendation=self._generate_limit_recommendation(
                    total_spy_contracts, POSITION_LIMITS['SPY_OPTIONS'], 'position'
                )
            )
            checks.append(spy_check)
            
            # Check single expiry concentration
            expiry_positions = defaultdict(int)
            for position in positions:
                if position['asset_type'] == 'option':
                    expiry = position.get('expiry_date')
                    if expiry:
                        expiry_positions[expiry] += abs(position['quantity'])
                        
            for expiry, quantity in expiry_positions.items():
                if quantity > POSITION_LIMITS['SINGLE_EXPIRY'] * 0.5:  # Check if over 50%
                    expiry_check = PositionLimitCheck(
                        check_time=current_time,
                        limit_type=f'SINGLE_EXPIRY_{expiry}',
                        current_value=quantity,
                        limit_value=POSITION_LIMITS['SINGLE_EXPIRY'],
                        usage_percentage=(quantity / POSITION_LIMITS['SINGLE_EXPIRY']) * 100,
                        status=self._determine_compliance_status(
                            quantity, POSITION_LIMITS['SINGLE_EXPIRY']
                        ),
                        affected_positions=[
                            p['symbol'] for p in positions 
                            if p.get('expiry_date') == expiry
                        ],
                        recommendation=self._generate_limit_recommendation(
                            quantity, POSITION_LIMITS['SINGLE_EXPIRY'], 'expiry'
                        )
                    )
                    checks.append(expiry_check)
                    
            # Check daily volume
            today_trades = self.dal.get_trades_by_date(date.today())
            daily_volume = sum(t['quantity'] for t in today_trades)
            
            volume_check = PositionLimitCheck(
                check_time=current_time,
                limit_type='DAILY_VOLUME',
                current_value=daily_volume,
                limit_value=POSITION_LIMITS['DAILY_VOLUME'],
                usage_percentage=(daily_volume / POSITION_LIMITS['DAILY_VOLUME']) * 100,
                status=self._determine_compliance_status(
                    daily_volume, POSITION_LIMITS['DAILY_VOLUME']
                ),
                affected_positions=[],
                recommendation=self._generate_limit_recommendation(
                    daily_volume, POSITION_LIMITS['DAILY_VOLUME'], 'volume'
                )
            )
            checks.append(volume_check)
            
            # Check net delta exposure
            total_delta = sum(
                p.get('delta', 0) * p['quantity'] * 100  # Options are 100 shares
                for p in positions
                if p['asset_type'] == 'option'
            )
            
            delta_check = PositionLimitCheck(
                check_time=current_time,
                limit_type='NET_DELTA',
                current_value=abs(total_delta),
                limit_value=POSITION_LIMITS['NET_DELTA'],
                usage_percentage=(abs(total_delta) / POSITION_LIMITS['NET_DELTA']) * 100,
                status=self._determine_compliance_status(
                    abs(total_delta), POSITION_LIMITS['NET_DELTA']
                ),
                affected_positions=[],
                recommendation=self._generate_limit_recommendation(
                    abs(total_delta), POSITION_LIMITS['NET_DELTA'], 'delta'
                )
            )
            checks.append(delta_check)
            
            # Log any breaches
            breaches = [c for c in checks if c.status == ComplianceStatus.BREACH]
            if breaches:
                self.logger.warning(f"Position limit breaches detected: {len(breaches)}")
                for breach in breaches:
                    self._create_audit_entry(
                        AuditEventType.LIMIT_BREACH,
                        f"Position limit breach: {breach.limit_type}",
                        {'check': asdict(breach)}
                    )
                    
            return checks
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'check_position_limits'
            })
            return []
            
    # ==========================================================================
    # RISK LIMIT MONITORING
    # ==========================================================================
    def check_risk_limits(self) -> List[RiskLimitBreach]:
        """
        Check current risk metrics against limits.
        
        Returns:
            List of RiskLimitBreach events
        """
        try:
            breaches = []
            
            # Get current risk metrics
            risk_metrics = self.risk_manager.get_current_risk_metrics()
            
            # Check daily loss
            daily_pnl = risk_metrics.get('daily_pnl', 0)
            if daily_pnl < -RISK_LIMITS['MAX_LOSS_DAILY']:
                breach = RiskLimitBreach(
                    breach_id=str(uuid.uuid4()),
                    breach_time=datetime.now(),
                    limit_type='MAX_LOSS_DAILY',
                    limit_value=RISK_LIMITS['MAX_LOSS_DAILY'],
                    actual_value=abs(daily_pnl),
                    severity=self._determine_breach_severity(
                        abs(daily_pnl), RISK_LIMITS['MAX_LOSS_DAILY']
                    ),
                    positions_affected=self._get_losing_positions(),
                    action_taken="Trading halted pending review",
                    resolved=False
                )
                breaches.append(breach)
                
            # Check drawdown
            drawdown = risk_metrics.get('current_drawdown', 0)
            if abs(drawdown) > RISK_LIMITS['MAX_DRAWDOWN']:
                breach = RiskLimitBreach(
                    breach_id=str(uuid.uuid4()),
                    breach_time=datetime.now(),
                    limit_type='MAX_DRAWDOWN',
                    limit_value=RISK_LIMITS['MAX_DRAWDOWN'],
                    actual_value=abs(drawdown),
                    severity=self._determine_breach_severity(
                        abs(drawdown), RISK_LIMITS['MAX_DRAWDOWN']
                    ),
                    positions_affected=self._get_all_positions(),
                    action_taken="Risk reduction required",
                    resolved=False
                )
                breaches.append(breach)
                
            # Check VaR
            var_95 = risk_metrics.get('var_95', 0)
            if var_95 > RISK_LIMITS['VAR_LIMIT']:
                breach = RiskLimitBreach(
                    breach_id=str(uuid.uuid4()),
                    breach_time=datetime.now(),
                    limit_type='VAR_LIMIT',
                    limit_value=RISK_LIMITS['VAR_LIMIT'],
                    actual_value=var_95,
                    severity=self._determine_breach_severity(
                        var_95, RISK_LIMITS['VAR_LIMIT']
                    ),
                    positions_affected=self._get_high_risk_positions(),
                    action_taken="Position sizing review required",
                    resolved=False
                )
                breaches.append(breach)
                
            # Check margin usage
            margin_usage = risk_metrics.get('margin_usage_ratio', 0)
            if margin_usage > RISK_LIMITS['MARGIN_USAGE']:
                breach = RiskLimitBreach(
                    breach_id=str(uuid.uuid4()),
                    breach_time=datetime.now(),
                    limit_type='MARGIN_USAGE',
                    limit_value=RISK_LIMITS['MARGIN_USAGE'],
                    actual_value=margin_usage,
                    severity=self._determine_breach_severity(
                        margin_usage, RISK_LIMITS['MARGIN_USAGE']
                    ),
                    positions_affected=self._get_all_positions(),
                    action_taken="Reduce positions or add capital",
                    resolved=False
                )
                breaches.append(breach)
                
            # Log breaches
            for breach in breaches:
                self._create_audit_entry(
                    AuditEventType.RISK_BREACH,
                    f"Risk limit breach: {breach.limit_type}",
                    {'breach': asdict(breach)}
                )
                
            return breaches
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'check_risk_limits'
            })
            return []
            
    # ==========================================================================
    # AUDIT TRAIL METHODS
    # ==========================================================================
    def create_audit_trail(self, start_date: date, end_date: date) -> List[AuditTrailEntry]:
        """
        Create comprehensive audit trail for date range.
        
        Args:
            start_date: Start date for audit trail
            end_date: End date for audit trail
            
        Returns:
            List of AuditTrailEntry objects
        """
        try:
            audit_entries = []
            
            # Get all trading events
            trades = self.dal.get_trades_by_date_range(start_date, end_date)
            orders = self.dal.get_orders_by_date_range(start_date, end_date)
            
            # Process orders
            for order in orders:
                # Order placed
                entry = self._create_audit_entry(
                    AuditEventType.ORDER_PLACED,
                    f"Order placed: {order['symbol']} {order['quantity']} @ {order['order_type']}",
                    order
                )
                audit_entries.append(entry)
                
                # Order fills
                if order['status'] == 'filled':
                    fill_entry = self._create_audit_entry(
                        AuditEventType.ORDER_FILLED,
                        f"Order filled: {order['order_id']}",
                        {'order_id': order['order_id'], 'fill_price': order.get('fill_price')}
                    )
                    audit_entries.append(fill_entry)
                    
            # Process position changes
            position_changes = self._get_position_changes(start_date, end_date)
            for change in position_changes:
                if change['type'] == 'opened':
                    entry = self._create_audit_entry(
                        AuditEventType.POSITION_OPENED,
                        f"Position opened: {change['symbol']}",
                        change
                    )
                else:
                    entry = self._create_audit_entry(
                        AuditEventType.POSITION_CLOSED,
                        f"Position closed: {change['symbol']}",
                        change
                    )
                audit_entries.append(entry)
                
            # Add system events (limit breaches, etc.)
            system_events = self._get_system_events(start_date, end_date)
            audit_entries.extend(system_events)
            
            # Sort by timestamp
            audit_entries.sort(key=lambda x: x.timestamp)
            
            # Verify audit chain integrity
            if not self._verify_audit_chain(audit_entries):
                self.logger.error("Audit chain integrity check failed!")
                
            return audit_entries
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'create_audit_trail',
                'date_range': f"{start_date} to {end_date}"
            })
            return []
            
    def export_audit_trail(self, audit_entries: List[AuditTrailEntry],
                         output_path: str, format: str = 'PDF') -> bool:
        """
        Export audit trail to file.
        
        Args:
            audit_entries: List of audit entries
            output_path: Output file path
            format: Export format
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if format.upper() == 'PDF':
                return self._export_audit_pdf(audit_entries, output_path)
            elif format.upper() == 'CSV':
                return self._export_audit_csv(audit_entries, output_path)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return False
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'export_audit_trail',
                'format': format
            })
            return False
            
    # ==========================================================================
    # RECONCILIATION METHODS
    # ==========================================================================
    def perform_month_end_reconciliation(self, month: int, year: int) -> ReconciliationResult:
        """
        Perform month-end reconciliation.
        
        Args:
            month: Month to reconcile
            year: Year to reconcile
            
        Returns:
            ReconciliationResult object
        """
        try:
            # Get month-end date
            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)
            month_end = next_month - timedelta(days=1)
            
            # Get broker positions
            broker_positions = self.account_manager.get_broker_positions(month_end)
            
            # Get system positions
            system_positions = self._calculate_system_positions(month_end)
            
            # Find discrepancies
            discrepancies = []
            total_discrepancy = 0.0
            
            all_symbols = set(broker_positions.keys()) | set(system_positions.keys())
            
            for symbol in all_symbols:
                broker_qty = broker_positions.get(symbol, 0)
                system_qty = system_positions.get(symbol, 0)
                
                if abs(broker_qty - system_qty) > 0.01:  # Small tolerance
                    discrepancy = {
                        'symbol': symbol,
                        'broker_quantity': broker_qty,
                        'system_quantity': system_qty,
                        'difference': broker_qty - system_qty,
                        'value_impact': self._estimate_value_impact(
                            symbol, broker_qty - system_qty
                        )
                    }
                    discrepancies.append(discrepancy)
                    total_discrepancy += abs(discrepancy['value_impact'])
                    
            # Determine status
            if not discrepancies:
                status = ComplianceStatus.COMPLIANT
                notes = "Perfect reconciliation - no discrepancies found"
            elif total_discrepancy < 1000:
                status = ComplianceStatus.WARNING
                notes = f"Minor discrepancies found totaling ${total_discrepancy:.2f}"
            else:
                status = ComplianceStatus.BREACH
                notes = f"Significant discrepancies found totaling ${total_discrepancy:.2f}"
                
            result = ReconciliationResult(
                reconciliation_date=month_end,
                account_id='main',  # Could be per account
                broker_positions=broker_positions,
                system_positions=system_positions,
                discrepancies=discrepancies,
                total_discrepancy_value=total_discrepancy,
                status=status,
                notes=notes
            )
            
            # Create audit entry
            self._create_audit_entry(
                AuditEventType.SYSTEM_OVERRIDE,
                f"Month-end reconciliation completed for {month}/{year}",
                {'result': asdict(result)}
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'perform_month_end_reconciliation',
                'month': month,
                'year': year
            })
            return None
            
    # ==========================================================================
    # COMPLIANCE SUMMARY
    # ==========================================================================
    def generate_compliance_summary(self, start_date: date, end_date: date) -> ComplianceSummary:
        """
        Generate comprehensive compliance summary.
        
        Args:
            start_date: Start of reporting period
            end_date: End of reporting period
            
        Returns:
            ComplianceSummary object
        """
        try:
            # Get all trades in period
            trades = self.dal.get_trades_by_date_range(start_date, end_date)
            total_trades = len(trades)
            total_volume = sum(t['quantity'] for t in trades)
            
            # Perform checks
            position_checks = self.check_position_limits()
            risk_breaches = self.check_risk_limits()
            
            # Check audit completeness
            required_events = self._count_required_audit_events(start_date, end_date)
            actual_events = len(self.create_audit_trail(start_date, end_date))
            audit_completeness = (actual_events / required_events * 100) if required_events > 0 else 100
            
            # Get latest reconciliation
            latest_recon = self.perform_month_end_reconciliation(
                end_date.month, end_date.year
            )
            recon_status = latest_recon.status if latest_recon else ComplianceStatus.UNDER_REVIEW
            
            # Determine overall status
            if any(c.status == ComplianceStatus.BREACH for c in position_checks):
                overall_status = ComplianceStatus.BREACH
            elif risk_breaches:
                overall_status = ComplianceStatus.BREACH
            elif recon_status == ComplianceStatus.BREACH:
                overall_status = ComplianceStatus.BREACH
            elif any(c.status == ComplianceStatus.WARNING for c in position_checks):
                overall_status = ComplianceStatus.WARNING
            else:
                overall_status = ComplianceStatus.COMPLIANT
                
            # Identify issues
            issues = []
            
            for check in position_checks:
                if check.status in [ComplianceStatus.BREACH, ComplianceStatus.WARNING]:
                    issues.append(f"Position limit {check.limit_type}: {check.usage_percentage:.1f}% usage")
                    
            for breach in risk_breaches:
                issues.append(f"Risk limit breach: {breach.limit_type} ({breach.severity})")
                
            if audit_completeness < 95:
                issues.append(f"Audit trail incomplete: {audit_completeness:.1f}%")
                
            # Check regulatory filings
            filings_due = self._check_regulatory_filings(end_date)
            
            summary = ComplianceSummary(
                report_date=date.today(),
                reporting_period=(start_date, end_date),
                total_trades=total_trades,
                total_volume=total_volume,
                position_limit_checks=position_checks,
                risk_limit_breaches=risk_breaches,
                audit_completeness=audit_completeness,
                reconciliation_status=recon_status,
                overall_status=overall_status,
                issues_requiring_attention=issues,
                regulatory_filings_due=filings_due
            )
            
            return summary
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_compliance_summary',
                'period': f"{start_date} to {end_date}"
            })
            return None
            
    def export_compliance_report(self, summary: ComplianceSummary,
                               output_path: str, format: str = 'PDF') -> bool:
        """
        Export compliance summary report.
        
        Args:
            summary: Compliance summary data
            output_path: Output file path
            format: Export format
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if format.upper() == 'PDF':
                return self._export_compliance_pdf(summary, output_path)
            elif format.upper() == 'JSON':
                return self._export_compliance_json(summary, output_path)
            else:
                self.logger.error(f"Unsupported format: {format}")
                return False
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'export_compliance_report',
                'format': format
            })
            return False
            
    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _determine_compliance_status(self, current: float, limit: float) -> ComplianceStatus:
        """Determine compliance status based on usage."""
        usage_pct = (current / limit) * 100
        
        if usage_pct >= 100:
            return ComplianceStatus.BREACH
        elif usage_pct >= 80:
            return ComplianceStatus.WARNING
        else:
            return ComplianceStatus.COMPLIANT
            
    def _determine_breach_severity(self, actual: float, limit: float) -> str:
        """Determine breach severity."""
        excess_pct = ((actual - limit) / limit) * 100
        
        if excess_pct > 50:
            return 'critical'
        elif excess_pct > 20:
            return 'major'
        else:
            return 'minor'
            
    def _generate_limit_recommendation(self, current: float, limit: float, 
                                     limit_type: str) -> str:
        """Generate recommendation for limit usage."""
        usage_pct = (current / limit) * 100
        
        if usage_pct >= 100:
            return f"Immediate action required: Reduce {limit_type} exposure"
        elif usage_pct >= 90:
            return f"Critical: Approaching {limit_type} limit, reduce exposure"
        elif usage_pct >= 80:
            return f"Warning: High {limit_type} usage, monitor closely"
        elif usage_pct >= 70:
            return f"Caution: Elevated {limit_type} usage"
        else:
            return "Within normal limits"
            
    def _create_audit_entry(self, event_type: AuditEventType, 
                          action: str, details: Dict[str, Any]) -> AuditTrailEntry:
        """Create audit trail entry."""
        entry = AuditTrailEntry(
            audit_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=event_type,
            user_id='system',  # Would be actual user in production
            system_id='spyder_trading',
            action=action,
            details=details,
            hash_previous=self.last_audit_hash
        )
        
        self.last_audit_hash = entry.hash_current
        self.audit_chain.append(entry)
        
        # Save to database
        self.dal.save_audit_entry(asdict(entry))
        
        return entry
        
    def _verify_audit_chain(self, entries: List[AuditTrailEntry]) -> bool:
        """Verify audit chain integrity."""
        if not entries:
            return True
            
        for i in range(1, len(entries)):
            expected_hash = entries[i]._calculate_hash()
            if entries[i].hash_current != expected_hash:
                self.logger.error(f"Audit chain broken at entry {i}")
                return False
                
        return True
        
    def _get_losing_positions(self) -> List[str]:
        """Get positions with losses."""
        positions = self.account_manager.get_all_positions()
        return [
            p['symbol'] for p in positions
            if p.get('unrealized_pnl', 0) < 0
        ]
        
    def _get_all_positions(self) -> List[str]:
        """Get all position symbols."""
        positions = self.account_manager.get_all_positions()
        return [p['symbol'] for p in positions]
        
    def _get_high_risk_positions(self) -> List[str]:
        """Get high risk positions."""
        # This would use risk metrics to identify high-risk positions
        return self._get_all_positions()[:5]  # Placeholder
        
    def _get_position_changes(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get position changes in date range."""
        # This would track position opens/closes
        return []  # Placeholder
        
    def _get_system_events(self, start_date: date, end_date: date) -> List[AuditTrailEntry]:
        """Get system events for audit trail."""
        # This would retrieve system events from logs
        return []  # Placeholder
        
    def _calculate_system_positions(self, as_of_date: date) -> Dict[str, float]:
        """Calculate system positions as of date."""
        # This would calculate positions from trade history
        positions = self.account_manager.get_all_positions()
        return {p['symbol']: p['quantity'] for p in positions}
        
    def _estimate_value_impact(self, symbol: str, quantity_diff: float) -> float:
        """Estimate value impact of position discrepancy."""
        # Get current price
        current_price = 100.0  # Placeholder - would get actual price
        return abs(quantity_diff * current_price)
        
    def _count_required_audit_events(self, start_date: date, end_date: date) -> int:
        """Count expected audit events."""
        trades = self.dal.get_trades_by_date_range(start_date, end_date)
        orders = self.dal.get_orders_by_date_range(start_date, end_date)
        return len(trades) + len(orders)
        
    def _check_regulatory_filings(self, as_of_date: date) -> List[Dict[str, Any]]:
        """Check for required regulatory filings."""
        filings = []
        
        # Large trader report (if applicable)
        if self._requires_large_trader_report(as_of_date):
            filings.append({
                'filing_type': 'Large Trader Report',
                'due_date': self._next_business_day(as_of_date + timedelta(days=10)),
                'status': 'pending'
            })
            
        # Options position report
        if as_of_date.day == 15 or self._is_month_end(as_of_date):
            filings.append({
                'filing_type': 'Options Position Report',
                'due_date': self._next_business_day(as_of_date + timedelta(days=1)),
                'status': 'pending'
            })
            
        return filings
        
    def _requires_large_trader_report(self, as_of_date: date) -> bool:
        """Check if large trader report is required."""
        # Check if trading volume exceeds thresholds
        return False  # Placeholder
        
    def _is_month_end(self, check_date: date) -> bool:
        """Check if date is month end."""
        next_day = check_date + timedelta(days=1)
        return next_day.month != check_date.month
        
    def _next_business_day(self, check_date: date) -> date:
        """Get next business day."""
        next_day = check_date
        while next_day.weekday() >= 5:  # Saturday = 5, Sunday = 6
            next_day += timedelta(days=1)
        return next_day
        
    # ==========================================================================
    # EXPORT METHODS
    # ==========================================================================
    def _export_blotter_pdf(self, entries: List[TradeBlotterEntry], output_path: str) -> bool:
        """Export trade blotter as PDF."""
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Trade Blotter", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Date
            date_para = Paragraph(
                f"Report Date: {date.today().strftime('%Y-%m-%d')}",
                styles['Normal']
            )
            elements.append(date_para)
            elements.append(Spacer(1, 12))
            
            # Table data
            data = [['Time', 'Symbol', 'Side', 'Qty', 'Price', 'Commission', 'Net Amount']]
            
            for entry in entries:
                data.append([
                    entry.timestamp.strftime('%H:%M:%S'),
                    entry.symbol,
                    entry.side.upper(),
                    str(entry.quantity),
                    f"${entry.price:.2f}",
                    f"${entry.commission:.2f}",
                    f"${entry.net_amount:,.2f}"
                ])
                
            # Create table
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            
            # Build PDF
            doc.build(elements)
            
            self.logger.info(f"Trade blotter PDF exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting PDF: {e}")
            return False
            
    def _export_blotter_csv(self, entries: List[TradeBlotterEntry], output_path: str) -> bool:
        """Export trade blotter as CSV."""
        try:
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'trade_id', 'order_id', 'timestamp', 'symbol', 'side',
                    'quantity', 'price', 'commission', 'net_amount',
                    'account_id', 'execution_venue', 'settlement_date'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for entry in entries:
                    writer.writerow({
                        'trade_id': entry.trade_id,
                        'order_id': entry.order_id,
                        'timestamp': entry.timestamp.isoformat(),
                        'symbol': entry.symbol,
                        'side': entry.side,
                        'quantity': entry.quantity,
                        'price': entry.price,
                        'commission': entry.commission,
                        'net_amount': entry.net_amount,
                        'account_id': entry.account_id,
                        'execution_venue': entry.execution_venue,
                        'settlement_date': entry.settlement_date.isoformat() if entry.settlement_date else ''
                    })
                    
            self.logger.info(f"Trade blotter CSV exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting CSV: {e}")
            return False
            
    def _export_blotter_excel(self, entries: List[TradeBlotterEntry], output_path: str) -> bool:
        """Export trade blotter as Excel."""
        try:
            # Create DataFrame
            data = []
            for entry in entries:
                data.append({
                    'Trade ID': entry.trade_id,
                    'Order ID': entry.order_id,
                    'Timestamp': entry.timestamp,
                    'Symbol': entry.symbol,
                    'Side': entry.side.upper(),
                    'Quantity': entry.quantity,
                    'Price': entry.price,
                    'Commission': entry.commission,
                    'Net Amount': entry.net_amount,
                    'Account': entry.account_id,
                    'Venue': entry.execution_venue,
                    'Settlement': entry.settlement_date
                })
                
            df = pd.DataFrame(data)
            
            # Create Excel writer
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Trade Blotter', index=False)
                
                # Get workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Trade Blotter']
                
                # Add formats
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#D7E4BD',
                    'border': 1
                })
                
                money_format = workbook.add_format({'num_format': '$#,##0.00'})
                
                # Format columns
                worksheet.set_column('G:G', 12, money_format)  # Price
                worksheet.set_column('H:H', 12, money_format)  # Commission
                worksheet.set_column('I:I', 15, money_format)  # Net Amount
                
                # Format header
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                    
            self.logger.info(f"Trade blotter Excel exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting Excel: {e}")
            return False
            
    def _export_audit_pdf(self, entries: List[AuditTrailEntry], output_path: str) -> bool:
        """Export audit trail as PDF."""
        try:
            doc = SimpleDocTemplate(output_path, pagesize=A4)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Audit Trail Report", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Summary
            summary = Paragraph(
                f"Total Entries: {len(entries)}<br/>"
                f"Period: {entries[0].timestamp.date() if entries else 'N/A'} to "
                f"{entries[-1].timestamp.date() if entries else 'N/A'}",
                styles['Normal']
            )
            elements.append(summary)
            elements.append(Spacer(1, 24))
            
            # Entries
            for entry in entries[:100]:  # Limit to first 100 for PDF
                entry_text = f"""
                <b>ID:</b> {entry.audit_id}<br/>
                <b>Time:</b> {entry.timestamp}<br/>
                <b>Event:</b> {entry.event_type.value}<br/>
                <b>Action:</b> {entry.action}<br/>
                <b>User:</b> {entry.user_id}<br/>
                <b>Hash:</b> {entry.hash_current[:16]}...<br/>
                """
                
                entry_para = Paragraph(entry_text, styles['Normal'])
                elements.append(entry_para)
                elements.append(Spacer(1, 12))
                
            doc.build(elements)
            
            self.logger.info(f"Audit trail PDF exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting audit PDF: {e}")
            return False
            
    def _export_audit_csv(self, entries: List[AuditTrailEntry], output_path: str) -> bool:
        """Export audit trail as CSV."""
        try:
            with open(output_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'audit_id', 'timestamp', 'event_type', 'user_id',
                    'system_id', 'action', 'details', 'hash_current', 'hash_previous'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for entry in entries:
                    writer.writerow({
                        'audit_id': entry.audit_id,
                        'timestamp': entry.timestamp.isoformat(),
                        'event_type': entry.event_type.value,
                        'user_id': entry.user_id,
                        'system_id': entry.system_id,
                        'action': entry.action,
                        'details': json.dumps(entry.details),
                        'hash_current': entry.hash_current,
                        'hash_previous': entry.hash_previous or ''
                    })
                    
            self.logger.info(f"Audit trail CSV exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting audit CSV: {e}")
            return False
            
    def _export_compliance_pdf(self, summary: ComplianceSummary, output_path: str) -> bool:
        """Export compliance summary as PDF."""
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title = Paragraph("Compliance Summary Report", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 12))
            
            # Report info
            info_text = f"""
            <b>Report Date:</b> {summary.report_date}<br/>
            <b>Period:</b> {summary.reporting_period[0]} to {summary.reporting_period[1]}<br/>
            <b>Overall Status:</b> {summary.overall_status.value.upper()}<br/>
            """
            info_para = Paragraph(info_text, styles['Normal'])
            elements.append(info_para)
            elements.append(Spacer(1, 24))
            
            # Trading summary
            trading_text = f"""
            <b>Trading Activity</b><br/>
            Total Trades: {summary.total_trades}<br/>
            Total Volume: {summary.total_volume:,.0f} contracts<br/>
            """
            trading_para = Paragraph(trading_text, styles['Normal'])
            elements.append(trading_para)
            elements.append(Spacer(1, 12))
            
            # Compliance metrics
            compliance_text = f"""
            <b>Compliance Metrics</b><br/>
            Audit Completeness: {summary.audit_completeness:.1f}%<br/>
            Reconciliation Status: {summary.reconciliation_status.value}<br/>
            Position Limit Checks: {len(summary.position_limit_checks)} performed<br/>
            Risk Limit Breaches: {len(summary.risk_limit_breaches)}<br/>
            """
            compliance_para = Paragraph(compliance_text, styles['Normal'])
            elements.append(compliance_para)
            elements.append(Spacer(1, 12))
            
            # Issues
            if summary.issues_requiring_attention:
                issues_text = "<b>Issues Requiring Attention</b><br/>"
                for issue in summary.issues_requiring_attention:
                    issues_text += f"• {issue}<br/>"
                issues_para = Paragraph(issues_text, styles['Normal'])
                elements.append(issues_para)
                
            doc.build(elements)
            
            self.logger.info(f"Compliance PDF exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting compliance PDF: {e}")
            return False
            
    def _export_compliance_json(self, summary: ComplianceSummary, output_path: str) -> bool:
        """Export compliance summary as JSON."""
        try:
            # Convert to dict
            summary_dict = asdict(summary)
            
            # Convert dates to strings
            summary_dict['report_date'] = summary.report_date.isoformat()
            summary_dict['reporting_period'] = [
                summary.reporting_period[0].isoformat(),
                summary.reporting_period[1].isoformat()
            ]
            
            # Convert enums
            summary_dict['overall_status'] = summary.overall_status.value
            summary_dict['reconciliation_status'] = summary.reconciliation_status.value
            
            # Write to file
            with open(output_path, 'w') as f:
                json.dump(summary_dict, f, indent=2, default=str)
                
            self.logger.info(f"Compliance JSON exported to {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting compliance JSON: {e}")
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_regulatory_reports() -> RegulatoryReports:
    """
    Get singleton instance of RegulatoryReports.
    
    Returns:
        RegulatoryReports instance
    """
    global _regulatory_reports_instance
    if _regulatory_reports_instance is None:
        _regulatory_reports_instance = RegulatoryReports()
    return _regulatory_reports_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_regulatory_reports_instance: Optional[RegulatoryReports] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    reg_reports = get_regulatory_reports()
    
    # Generate trade blotter
    print("Generating trade blotter...")
    blotter = reg_reports.generate_trade_blotter(date.today())
    if blotter:
        print(f"  Found {len(blotter)} trades")
        reg_reports.export_trade_blotter(blotter, "trade_blotter.pdf")
        
    # Check position limits
    print("\nChecking position limits...")
    position_checks = reg_reports.check_position_limits()
    for check in position_checks:
        print(f"  {check.limit_type}: {check.usage_percentage:.1f}% ({check.status.value})")
        
    # Check risk limits
    print("\nChecking risk limits...")
    risk_breaches = reg_reports.check_risk_limits()
    if risk_breaches:
        print(f"  Found {len(risk_breaches)} risk limit breaches")
    else:
        print("  All risk limits within bounds")
        
    # Generate compliance summary
    print("\nGenerating compliance summary...")
    start_date = date.today() - timedelta(days=30)
    end_date = date.today()
    summary = reg_reports.generate_compliance_summary(start_date, end_date)
    
    if summary:
        print(f"  Overall Status: {summary.overall_status.value}")
        print(f"  Issues: {len(summary.issues_requiring_attention)}")
        
        # Export report
        reg_reports.export_compliance_report(summary, "compliance_summary.pdf")
        
    print("\nRegulatory reports completed")
