#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_PreMarketDiagnostic.py
Purpose: Pre-market diagnostic for Series C data feed issues
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 13:30:00  

Module Description:
    Quick diagnostic module to identify and resolve data feed issues in Series C
    modules before market open. This module checks IBKR connections, symbol
    subscriptions, market data permissions, and provides actionable solutions.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, deque
from dataclasses import dataclass

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
    import numpy as np
    from ib_insync import *
    IB_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Missing dependencies: {e}")
    IB_AVAILABLE = False

# ==============================================================================
# DIAGNOSTIC DATA STRUCTURES
# ==============================================================================

@dataclass
class SymbolStatus:
    """Status of a single symbol subscription"""
    symbol: str
    tier: str
    subscribed: bool = False
    has_data: bool = False
    last_update: Optional[datetime] = None
    error_message: str = ""
    subscription_required: str = ""

@dataclass
class DiagnosticReport:
    """Complete diagnostic report"""
    connection_status: str
    total_symbols_tested: int
    successful_subscriptions: int
    failed_subscriptions: int
    symbols_with_data: int
    symbols_needing_subscription: List[str]
    critical_issues: List[str]
    recommendations: List[str]
    symbol_details: Dict[str, SymbolStatus]

# ==============================================================================
# SYMBOL CONFIGURATION
# ==============================================================================

# Core symbols that must work for Spyder
CRITICAL_SYMBOLS = {
    'SPY': {'type': 'STK', 'exchange': 'SMART', 'currency': 'USD', 'tier': 'CRITICAL'},
    'SPX': {'type': 'IND', 'exchange': 'CBOE', 'currency': 'USD', 'tier': 'CRITICAL'},
    '/ES': {'type': 'FUT', 'exchange': 'CME', 'currency': 'USD', 'tier': 'CRITICAL', 'localSymbol': 'ESZ5'},
    'VIX': {'type': 'IND', 'exchange': 'CBOE', 'currency': 'USD', 'tier': 'CRITICAL'},
}

# High priority symbols
HIGH_PRIORITY_SYMBOLS = {
    'VIX9D': {'type': 'IND', 'exchange': 'CBOE', 'currency': 'USD', 'tier': 'HIGH'},
    'VXV': {'type': 'IND', 'exchange': 'CBOE', 'currency': 'USD', 'tier': 'HIGH'},
    'VXMT': {'type': 'IND', 'exchange': 'CBOE', 'currency': 'USD', 'tier': 'HIGH'},
    'UVXY': {'type': 'STK', 'exchange': 'SMART', 'currency': 'USD', 'tier': 'HIGH'},
    'TICK-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'currency': 'USD', 'tier': 'HIGH'},
    'TRIN-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'currency': 'USD', 'tier': 'HIGH'},
    'ADD-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'currency': 'USD', 'tier': 'HIGH'},
}

# Market data subscription requirements
SUBSCRIPTION_REQUIREMENTS = {
    'SPY': 'US Equity and Options Add-On Streaming Bundle',
    'SPX': 'CBOE One',
    '/ES': 'CME Market Data',
    'VIX': 'CBOE One',
    'VIX9D': 'CBOE One',
    'VXV': 'CBOE One',
    'VXMT': 'CBOE One',
    'TICK-NYSE': 'NYSE Market Data',
    'TRIN-NYSE': 'NYSE Market Data',
    'ADD-NYSE': 'NYSE Market Data',
}

# ==============================================================================
# DIAGNOSTIC CLASS
# ==============================================================================

class PreMarketDiagnostic:
    """
    Pre-market diagnostic system for Spyder data feeds.
    
    Quickly identifies and reports on data feed issues that could impact
    trading operations when market opens.
    """
    
    def __init__(self):
        """Initialize diagnostic system."""
        self.ib = None
        self.connected = False
        self.symbol_status = {}
        self.test_results = {}
        self.start_time = datetime.now()
        
    def run_complete_diagnostic(self) -> DiagnosticReport:
        """Run complete pre-market diagnostic."""
        print("=" * 80)
        print("🔍 SPYDER PRE-MARKET DIAGNOSTIC")
        print("=" * 80)
        print(f"🕐 Current Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        # Step 1: Check dependencies
        print("\n1️⃣ Checking Dependencies...")
        dep_status = self._check_dependencies()
        
        if not dep_status:
            return self._create_failure_report("Missing critical dependencies")
        
        # Step 2: Test IBKR connection
        print("\n2️⃣ Testing IBKR Connection...")
        conn_status = self._test_connection()
        
        if not conn_status:
            return self._create_failure_report("IBKR connection failed")
        
        # Step 3: Test symbol subscriptions
        print("\n3️⃣ Testing Symbol Subscriptions...")
        self._test_symbol_subscriptions()
        
        # Step 4: Wait for data
        print("\n4️⃣ Waiting for Market Data...")
        self._wait_for_data()
        
        # Step 5: Generate report
        print("\n5️⃣ Generating Report...")
        report = self._generate_report()
        
        # Cleanup
        self._cleanup()
        
        return report
    
    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are available."""
        if not IB_AVAILABLE:
            print("❌ ib_insync library not available")
            print("💡 Install with: pip install ib_insync")
            return False
        
        print("✅ All dependencies available")
        return True
    
    def _test_connection(self) -> bool:
        """Test connection to IBKR Gateway."""
        try:
            self.ib = IB()
            
            # Try multiple connection configurations
            connection_configs = [
                {'host': '127.0.0.1', 'port': 7497, 'clientId': 999, 'name': 'Paper Trading'},
                {'host': '127.0.0.1', 'port': 7496, 'clientId': 999, 'name': 'Live Trading'},
                {'host': '127.0.0.1', 'port': 4002, 'clientId': 999, 'name': 'Gateway Paper'},
                {'host': '127.0.0.1', 'port': 4001, 'clientId': 999, 'name': 'Gateway Live'},
            ]
            
            for config in connection_configs:
                try:
                    print(f"   Trying {config['name']} (port {config['port']})...")
                    self.ib.connect(
                        host=config['host'],
                        port=config['port'],
                        clientId=config['clientId'],
                        timeout=5
                    )
                    
                    if self.ib.isConnected():
                        print(f"✅ Connected via {config['name']}")
                        self.connected = True
                        
                        # Configure market data type (delayed is free)
                        self.ib.reqMarketDataType(3)
                        print("📊 Configured for delayed market data")
                        
                        return True
                        
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            print("❌ Could not connect to any IBKR interface")
            return False
            
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
    
    def _test_symbol_subscriptions(self):
        """Test symbol subscriptions."""
        all_symbols = {**CRITICAL_SYMBOLS, **HIGH_PRIORITY_SYMBOLS}
        
        for symbol, config in all_symbols.items():
            print(f"   Testing {symbol}...")
            status = self._test_single_symbol(symbol, config)
            self.symbol_status[symbol] = status
    
    def _test_single_symbol(self, symbol: str, config: Dict) -> SymbolStatus:
        """Test subscription for a single symbol."""
        status = SymbolStatus(symbol=symbol, tier=config['tier'])
        
        try:
            # Build contract
            contract = self._build_contract(symbol, config)
            
            # Qualify contract
            qualified = self.ib.qualifyContracts(contract)
            if not qualified:
                status.error_message = "Contract qualification failed"
                status.subscription_required = SUBSCRIPTION_REQUIREMENTS.get(symbol, "Unknown")
                return status
            
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            status.subscribed = True
            
            print(f"      ✅ {symbol} subscribed")
            return status
            
        except Exception as e:
            status.error_message = str(e)
            status.subscription_required = SUBSCRIPTION_REQUIREMENTS.get(symbol, "Unknown")
            print(f"      ❌ {symbol} failed: {e}")
            return status
    
    def _build_contract(self, symbol: str, config: Dict):
        """Build IBKR contract for symbol."""
        sec_type = config['type']
        
        if sec_type == 'STK':
            return Stock(symbol, config['exchange'], config['currency'])
        elif sec_type == 'IND':
            return Index(symbol, config['exchange'], config['currency'])
        elif sec_type == 'FUT':
            return Future(
                symbol=symbol.replace('/', ''),
                exchange=config['exchange'],
                currency=config['currency'],
                localSymbol=config.get('localSymbol', '')
            )
        else:
            raise ValueError(f"Unknown security type: {sec_type}")
    
    def _wait_for_data(self):
        """Wait for market data to arrive."""
        print("   Waiting 10 seconds for data...")
        
        for i in range(10):
            print(f"   {10-i}...", end=' ', flush=True)
            time.sleep(1)
        print("\n")
        
        # Check which symbols have data
        for ticker in self.ib.tickers():
            symbol = ticker.contract.symbol
            if symbol == 'ES':  # /ES shows as ES
                symbol = '/ES'
                
            if symbol in self.symbol_status:
                if ticker.last > 0 or ticker.bid > 0 or ticker.ask > 0:
                    self.symbol_status[symbol].has_data = True
                    self.symbol_status[symbol].last_update = datetime.now()
                    print(f"      ✅ {symbol} has data (Last: {ticker.last}, Bid: {ticker.bid}, Ask: {ticker.ask})")
                else:
                    print(f"      ⚠️  {symbol} no data yet")
    
    def _generate_report(self) -> DiagnosticReport:
        """Generate diagnostic report."""
        successful_subs = sum(1 for s in self.symbol_status.values() if s.subscribed)
        failed_subs = len(self.symbol_status) - successful_subs
        symbols_with_data = sum(1 for s in self.symbol_status.values() if s.has_data)
        
        symbols_needing_subscription = [
            s.symbol for s in self.symbol_status.values() 
            if not s.subscribed and s.subscription_required
        ]
        
        critical_issues = []
        recommendations = []
        
        # Check critical symbols
        critical_down = [s.symbol for s in self.symbol_status.values() 
                        if s.tier == 'CRITICAL' and not s.has_data]
        
        if critical_down:
            critical_issues.append(f"Critical symbols without data: {critical_down}")
        
        # Generate recommendations
        if symbols_needing_subscription:
            recommendations.append("Update IBKR market data subscriptions")
            recommendations.append("Check IBKR Account Management → Market Data Subscriptions")
        
        if symbols_with_data < len(self.symbol_status) * 0.5:
            recommendations.append("Less than 50% of symbols have data - check market hours")
        
        return DiagnosticReport(
            connection_status="Connected" if self.connected else "Disconnected",
            total_symbols_tested=len(self.symbol_status),
            successful_subscriptions=successful_subs,
            failed_subscriptions=failed_subs,
            symbols_with_data=symbols_with_data,
            symbols_needing_subscription=symbols_needing_subscription,
            critical_issues=critical_issues,
            recommendations=recommendations,
            symbol_details=self.symbol_status
        )
    
    def _create_failure_report(self, reason: str) -> DiagnosticReport:
        """Create a failure report."""
        return DiagnosticReport(
            connection_status="Failed",
            total_symbols_tested=0,
            successful_subscriptions=0,
            failed_subscriptions=0,
            symbols_with_data=0,
            symbols_needing_subscription=[],
            critical_issues=[reason],
            recommendations=["Fix critical infrastructure issues first"],
            symbol_details={}
        )
    
    def _cleanup(self):
        """Clean up resources."""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print("🧹 Cleanup completed")
    
    def print_detailed_report(self, report: DiagnosticReport):
        """Print detailed diagnostic report."""
        print("\n" + "=" * 80)
        print("📊 DIAGNOSTIC REPORT")
        print("=" * 80)
        
        # Summary
        print(f"\n🔗 Connection Status: {report.connection_status}")
        print(f"📈 Symbols Tested: {report.total_symbols_tested}")
        print(f"✅ Successful Subscriptions: {report.successful_subscriptions}")
        print(f"❌ Failed Subscriptions: {report.failed_subscriptions}")
        print(f"📊 Symbols With Data: {report.symbols_with_data}")
        
        # Critical Issues
        if report.critical_issues:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in report.critical_issues:
                print(f"   ⚠️  {issue}")
        
        # Symbol Details
        if report.symbol_details:
            print(f"\n📋 SYMBOL DETAILS:")
            print("-" * 80)
            
            for symbol, status in report.symbol_details.items():
                print(f"\n{symbol} ({status.tier}):")
                print(f"   Subscribed: {'✅' if status.subscribed else '❌'}")
                print(f"   Has Data: {'✅' if status.has_data else '❌'}")
                if status.error_message:
                    print(f"   Error: {status.error_message}")
                if status.subscription_required and not status.subscribed:
                    print(f"   Requires: {status.subscription_required}")
        
        # Recommendations
        if report.recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"   {i}. {rec}")
        
        # Next Steps
        print(f"\n🎯 NEXT STEPS:")
        if report.symbols_needing_subscription:
            print("   1. Log into IBKR Account Management")
            print("   2. Navigate to: Settings → User Settings → Market Data Subscriptions")
            print("   3. Subscribe to required data packages")
            print("   4. Restart Spyder after subscription changes")
        else:
            print("   1. All symbol subscriptions appear correct")
            print("   2. Check if market is open for live data")
            print("   3. Restart Spyder if issues persist")
        
        # Time to market open
        now = datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        if now.hour < 9 or (now.hour == 9 and now.minute < 30):
            time_to_open = market_open - now
            print(f"\n⏰ Time to Market Open: {time_to_open}")
        
        print("\n" + "=" * 80)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Run pre-market diagnostic."""
    diagnostic = PreMarketDiagnostic()
    
    try:
        report = diagnostic.run_complete_diagnostic()
        diagnostic.print_detailed_report(report)
        
        # Return status code
        if report.critical_issues:
            return 1  # Critical issues found
        elif report.symbols_with_data < report.total_symbols_tested * 0.8:
            return 2  # Warning - low data coverage
        else:
            return 0  # All good
            
    except KeyboardInterrupt:
        print("\n🛑 Diagnostic interrupted by user")
        return 3
    except Exception as e:
        print(f"\n💥 Diagnostic failed: {e}")
        return 4

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)