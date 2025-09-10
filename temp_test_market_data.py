#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Tests
Module: temp_test_market_data.py
Purpose: Comprehensive market data flow testing for IB Gateway connection
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-09 Time: 12:30:00

Module Description:
    Advanced market data testing module for validating IB Gateway connectivity
    and data flow in the Spyder trading system. Tests real-time quotes, historical
    data, options chains, and account information using the configured Master
    Client ID. Provides comprehensive validation of market data subscriptions,
    delayed vs real-time data, and SPY-specific options trading capabilities.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import json
import traceback

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ib_async import (
        IB, Stock, Index, Option, Contract,
        util, MarketOrder, LimitOrder, StopOrder
    )
    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("❌ ib_async not installed. Install with: pip install ib_async")
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
MASTER_CLIENT_ID = 2  # Master Client ID for Spyder system
PAPER_TRADING_PORT = 4002
LIVE_TRADING_PORT = 4001
CONNECTION_TIMEOUT = 30  # seconds
DATA_WAIT_TIME = 10  # seconds to wait for market data

# Market data types
class MarketDataType(Enum):
    """IB Market Data Types"""
    LIVE = 1
    FROZEN = 2
    DELAYED = 3
    DELAYED_FROZEN = 4

# ==============================================================================
# TEST RESULT DATA STRUCTURES
# ==============================================================================
class TestResult:
    """Container for test results"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.message = ""
        self.data = {}
        self.start_time = datetime.now()
        self.end_time = None
        
    def complete(self, passed: bool, message: str, data: Dict = None):
        """Mark test as complete"""
        self.passed = passed
        self.message = message
        self.data = data or {}
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        
    def __str__(self):
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return f"{status} - {self.test_name}: {self.message}"

# ==============================================================================
# MARKET DATA TEST CLASS
# ==============================================================================
class MarketDataTester:
    """
    Comprehensive market data testing for IB Gateway connection.
    
    This class provides extensive testing of market data capabilities
    including real-time quotes, historical data, options chains, and
    account information retrieval.
    """
    
    def __init__(self):
        """Initialize the market data tester"""
        self.ib = IB()
        self.results = []
        self.connection_details = {}
        
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    async def connect(self, port: int = PAPER_TRADING_PORT) -> bool:
        """
        Establish connection to IB Gateway.
        
        Args:
            port: Port number to connect to (default: paper trading)
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            print(f"🔌 Connecting to IB Gateway on port {port}...")
            print(f"   Using Master Client ID: {MASTER_CLIENT_ID}")
            
            await self.ib.connectAsync(
                '127.0.0.1', 
                port, 
                clientId=MASTER_CLIENT_ID, 
                timeout=CONNECTION_TIMEOUT
            )
            
            # Store connection details
            self.connection_details = {
                'port': port,
                'client_id': MASTER_CLIENT_ID,
                'server_version': getattr(self.ib.client, 'serverVersion', 'Unknown'),
                'connection_time': getattr(self.ib.client, 'connectionTime', 'Unknown'),
                'managed_accounts': self.ib.managedAccounts()
            }
            
            print(f"✅ Connected successfully!")
            print(f"   Server version: {self.connection_details['server_version']}")
            print(f"   Managed accounts: {self.connection_details['managed_accounts']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            
            # Try alternative port
            alt_port = LIVE_TRADING_PORT if port == PAPER_TRADING_PORT else PAPER_TRADING_PORT
            print(f"\n🔄 Trying alternative port {alt_port}...")
            
            try:
                await self.ib.connectAsync(
                    '127.0.0.1', 
                    alt_port, 
                    clientId=MASTER_CLIENT_ID, 
                    timeout=CONNECTION_TIMEOUT
                )
                print(f"⚠️  Connected on alternative port {alt_port}")
                self.connection_details['port'] = alt_port
                return True
            except:
                print(f"❌ Alternative port also failed")
                return False
    
    # ==========================================================================
    # TEST METHODS
    # ==========================================================================
    async def test_spy_stock_data(self) -> TestResult:
        """
        Test SPY stock market data retrieval.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("SPY Stock Data")
        print("\n1️⃣ Testing SPY stock data...")
        
        try:
            # Create and qualify SPY contract
            spy = Stock('SPY', 'SMART', 'USD')
            qualified_contracts = await self.ib.qualifyContractsAsync(spy)
            
            if not qualified_contracts:
                result.complete(False, "Failed to qualify SPY contract")
                return result
            
            spy = qualified_contracts[0]
            print(f"   Contract qualified: {spy}")
            
            # Check current market data type
            market_data_type = self.ib.reqMarketDataType()
            print(f"   Market Data Type: {MarketDataType(market_data_type).name}")
            
            # Request market data (not snapshot for continuous updates)
            print("   Requesting market data...")
            ticker = self.ib.reqMktData(spy, '', snapshot=False)
            
            # Wait for data with progress indicator
            print("   Waiting for market data", end="")
            for i in range(DATA_WAIT_TIME):
                print(".", end="", flush=True)
                await asyncio.sleep(1)
                
                # Check if we have data
                if ticker.last and ticker.last > 0:
                    break
            print()
            
            # Collect results
            data = {
                'symbol': 'SPY',
                'last': ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'close': ticker.close,
                'volume': ticker.volume,
                'time': str(ticker.time) if ticker.time else None,
                'bid_size': ticker.bidSize,
                'ask_size': ticker.askSize,
                'high': ticker.high,
                'low': ticker.low,
                'market_data_type': MarketDataType(market_data_type).name
            }
            
            # Display results
            print(f"   SPY Last: ${data['last'] if data['last'] else 'N/A'}")
            print(f"   SPY Bid/Ask: ${data['bid'] if data['bid'] else 'N/A'} / ${data['ask'] if data['ask'] else 'N/A'}")
            print(f"   SPY Volume: {data['volume'] if data['volume'] else 'N/A'}")
            
            # Cancel market data subscription
            self.ib.cancelMktData(ticker)
            
            # Determine if test passed
            if data['last'] and data['last'] > 0:
                result.complete(True, f"Successfully retrieved SPY data at ${data['last']}", data)
            elif data['bid'] and data['ask']:
                result.complete(True, f"Retrieved bid/ask: ${data['bid']}/{data['ask']}", data)
            else:
                result.complete(False, "No price data received", data)
                
        except Exception as e:
            result.complete(False, f"Error: {e}")
            traceback.print_exc()
            
        return result
    
    async def test_delayed_data(self) -> TestResult:
        """
        Test delayed market data retrieval.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("Delayed Market Data")
        print("\n2️⃣ Testing delayed market data...")
        
        try:
            # Switch to delayed data
            self.ib.reqMarketDataType(MarketDataType.DELAYED.value)
            await asyncio.sleep(2)
            
            current_type = self.ib.reqMarketDataType()
            print(f"   Market data type: {MarketDataType(current_type).name}")
            
            # Request SPY delayed data
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = await self.ib.qualifyContractsAsync(spy)
            
            if qualified:
                ticker = self.ib.reqMktData(qualified[0], '', snapshot=False)
                
                # Wait for delayed data
                print("   Waiting for delayed data...")
                await asyncio.sleep(8)
                
                data = {
                    'last': ticker.last,
                    'delayed': True,
                    'market_data_type': MarketDataType(current_type).name
                }
                
                print(f"   Delayed Last: ${ticker.last if ticker.last else 'N/A'}")
                
                self.ib.cancelMktData(ticker)
                
                if ticker.last:
                    result.complete(True, f"Delayed data received: ${ticker.last}", data)
                else:
                    result.complete(False, "No delayed data received", data)
            else:
                result.complete(False, "Failed to qualify contract")
                
        except Exception as e:
            result.complete(False, f"Error: {e}")
            
        # Switch back to live/frozen data
        self.ib.reqMarketDataType(MarketDataType.FROZEN.value)
        
        return result
    
    async def test_historical_data(self) -> TestResult:
        """
        Test historical data retrieval for SPY.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("Historical Data")
        print("\n3️⃣ Testing historical data...")
        
        try:
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = await self.ib.qualifyContractsAsync(spy)
            
            if not qualified:
                result.complete(False, "Failed to qualify SPY contract")
                return result
            
            spy = qualified[0]
            
            # Request 1 day of hourly bars
            print("   Requesting 1 day of hourly bars...")
            bars = await self.ib.reqHistoricalDataAsync(
                spy,
                endDateTime='',
                durationStr='1 D',
                barSizeSetting='1 hour',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if bars:
                latest = bars[-1]
                oldest = bars[0]
                
                data = {
                    'bar_count': len(bars),
                    'latest_bar': {
                        'date': str(latest.date),
                        'open': latest.open,
                        'high': latest.high,
                        'low': latest.low,
                        'close': latest.close,
                        'volume': latest.volume
                    },
                    'oldest_bar': {
                        'date': str(oldest.date),
                        'close': oldest.close
                    }
                }
                
                print(f"   Received {len(bars)} bars")
                print(f"   Latest: {latest.date} OHLC=${latest.open:.2f}/{latest.high:.2f}/{latest.low:.2f}/{latest.close:.2f}")
                print(f"   Volume: {latest.volume:,}")
                
                result.complete(True, f"Retrieved {len(bars)} historical bars", data)
            else:
                result.complete(False, "No historical data received")
                
        except Exception as e:
            result.complete(False, f"Error: {e}")
            traceback.print_exc()
            
        return result
    
    async def test_options_chain(self) -> TestResult:
        """
        Test SPY options chain retrieval.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("SPY Options Chain")
        print("\n4️⃣ Testing SPY options chain...")
        
        try:
            # Get SPY contract
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = await self.ib.qualifyContractsAsync(spy)
            
            if not qualified:
                result.complete(False, "Failed to qualify SPY contract")
                return result
            
            spy = qualified[0]
            
            # Get options chain
            print("   Requesting options chain...")
            chains = await self.ib.reqSecDefOptParamsAsync(
                spy.symbol,
                spy.exchange,
                spy.secType,
                spy.conId
            )
            
            if chains:
                chain = chains[0]
                
                data = {
                    'exchange': chain.exchange,
                    'underlying_conId': chain.underlyingConId,
                    'trading_class': chain.tradingClass,
                    'multiplier': chain.multiplier,
                    'expiration_count': len(chain.expirations),
                    'strike_count': len(chain.strikes),
                    'next_expiration': chain.expirations[0] if chain.expirations else None,
                    'sample_strikes': chain.strikes[:5] if len(chain.strikes) >= 5 else chain.strikes
                }
                
                print(f"   Exchange: {chain.exchange}")
                print(f"   Expirations available: {len(chain.expirations)}")
                print(f"   Strikes available: {len(chain.strikes)}")
                
                if chain.expirations:
                    print(f"   Next expiration: {chain.expirations[0]}")
                
                # Test creating a specific option contract
                if chain.expirations and chain.strikes:
                    # Get ATM strike (closest to middle)
                    mid_strike = chain.strikes[len(chain.strikes)//2]
                    
                    test_option = Option(
                        'SPY',
                        chain.expirations[0],
                        mid_strike,
                        'C',  # Call option
                        'SMART'
                    )
                    
                    # Qualify the option
                    qualified_opt = await self.ib.qualifyContractsAsync(test_option)
                    
                    if qualified_opt:
                        print(f"   Test option qualified: {qualified_opt[0]}")
                        data['test_option'] = str(qualified_opt[0])
                
                result.complete(True, f"Options chain retrieved: {len(chain.expirations)} expirations", data)
            else:
                result.complete(False, "No options chain data received")
                
        except Exception as e:
            result.complete(False, f"Error: {e}")
            traceback.print_exc()
            
        return result
    
    async def test_account_data(self) -> TestResult:
        """
        Test account data retrieval.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("Account Data")
        print("\n5️⃣ Testing account data...")
        
        try:
            # Request account summary
            print("   Requesting account summary...")
            account_summary = self.ib.reqAccountSummary()
            
            # Wait for data to populate
            await asyncio.sleep(3)
            
            if account_summary:
                # Collect key account metrics
                summary_dict = {}
                important_tags = [
                    'NetLiquidation', 'TotalCashValue', 'BuyingPower',
                    'AvailableFunds', 'MaintMarginReq', 'GrossPositionValue'
                ]
                
                for item in account_summary:
                    if item.tag in important_tags:
                        summary_dict[item.tag] = {
                            'value': item.value,
                            'currency': item.currency
                        }
                
                data = {
                    'account': account_summary[0].account if account_summary else None,
                    'summary_items': len(account_summary),
                    'key_metrics': summary_dict
                }
                
                print(f"   Account: {data['account']}")
                print(f"   Summary items received: {data['summary_items']}")
                
                # Display key metrics
                for tag, info in summary_dict.items():
                    print(f"   {tag}: {info['value']} {info['currency']}")
                
                result.complete(True, f"Account data retrieved: {len(account_summary)} items", data)
            else:
                # Try account values as fallback
                print("   No account summary, trying account values...")
                account_values = self.ib.accountValues()
                
                if account_values:
                    data = {
                        'account_values': len(account_values),
                        'sample_values': []
                    }
                    
                    for av in account_values[:5]:
                        data['sample_values'].append({
                            'tag': av.tag,
                            'value': av.value
                        })
                        print(f"   {av.tag}: {av.value}")
                    
                    result.complete(True, f"Account values retrieved: {len(account_values)} items", data)
                else:
                    result.complete(False, "No account data available", {})
                    
        except Exception as e:
            result.complete(False, f"Error: {e}")
            traceback.print_exc()
            
        return result
    
    async def test_market_depth(self) -> TestResult:
        """
        Test Level 2 market depth for SPY.
        
        Returns:
            TestResult object with test outcome
        """
        result = TestResult("Market Depth (Level 2)")
        print("\n6️⃣ Testing market depth...")
        
        try:
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = await self.ib.qualifyContractsAsync(spy)
            
            if not qualified:
                result.complete(False, "Failed to qualify SPY contract")
                return result
            
            spy = qualified[0]
            
            # Request market depth
            print("   Requesting Level 2 market depth...")
            self.ib.reqMktDepth(spy, numRows=5)
            
            # Wait for depth data
            await asyncio.sleep(5)
            
            # Get the ticker with depth
            ticker = self.ib.ticker(spy)
            
            if ticker and (ticker.domBids or ticker.domAsks):
                data = {
                    'has_bids': bool(ticker.domBids),
                    'has_asks': bool(ticker.domAsks),
                    'bid_levels': len(ticker.domBids) if ticker.domBids else 0,
                    'ask_levels': len(ticker.domAsks) if ticker.domAsks else 0
                }
                
                print(f"   Bid levels: {data['bid_levels']}")
                print(f"   Ask levels: {data['ask_levels']}")
                
                if ticker.domBids:
                    for i, bid in enumerate(ticker.domBids[:3]):
                        print(f"     Bid {i+1}: ${bid.price} x {bid.size}")
                
                result.complete(True, f"Market depth retrieved: {data['bid_levels']} bid levels", data)
            else:
                result.complete(False, "No market depth data available", {})
                print("   Note: Level 2 data may require additional market data subscriptions")
            
            # Cancel market depth
            self.ib.cancelMktDepth(spy)
            
        except Exception as e:
            result.complete(False, f"Error: {e}")
            
        return result
    
    # ==========================================================================
    # TEST EXECUTION
    # ==========================================================================
    async def run_all_tests(self) -> List[TestResult]:
        """
        Run all market data tests.
        
        Returns:
            List of TestResult objects
        """
        print("\n🚀 Starting comprehensive IB Gateway market data tests...")
        print("=" * 60)
        
        # Connect first
        if not await self.connect():
            print("\n❌ Cannot proceed without connection")
            return []
        
        # Run tests
        tests = [
            self.test_spy_stock_data(),
            self.test_delayed_data(),
            self.test_historical_data(),
            self.test_options_chain(),
            self.test_account_data(),
            self.test_market_depth()
        ]
        
        for test in tests:
            result = await test
            self.results.append(result)
            print(result)
            await asyncio.sleep(1)  # Brief pause between tests
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive test report.
        
        Returns:
            Dictionary containing test results and statistics
        """
        passed_count = sum(1 for r in self.results if r.passed)
        failed_count = len(self.results) - passed_count
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'connection': self.connection_details,
            'summary': {
                'total_tests': len(self.results),
                'passed': passed_count,
                'failed': failed_count,
                'success_rate': f"{(passed_count/len(self.results)*100):.1f}%" if self.results else "0%"
            },
            'tests': []
        }
        
        for result in self.results:
            report['tests'].append({
                'name': result.test_name,
                'passed': result.passed,
                'message': result.message,
                'duration': getattr(result, 'duration', 0),
                'data': result.data
            })
        
        return report
    
    async def cleanup(self):
        """Clean up and disconnect"""
        if self.ib.isConnected():
            print("\n🔌 Disconnecting from IB Gateway...")
            self.ib.disconnect()
            await asyncio.sleep(1)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main test execution function"""
    tester = MarketDataTester()
    
    try:
        # Run all tests
        results = await tester.run_all_tests()
        
        if not results:
            print("\n❌ No tests were run - check connection")
            return False
        
        # Generate report
        report = tester.generate_report()
        
        # Display summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']} ✅")
        print(f"Failed: {report['summary']['failed']} ❌")
        print(f"Success Rate: {report['summary']['success_rate']}")
        
        # Save report
        report_file = Path(f"market_data_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📝 Detailed report saved to: {report_file}")
        except Exception as e:
            print(f"\n⚠️  Could not save report: {e}")
        
        # Overall result
        all_passed = report['summary']['failed'] == 0
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED! Your IB Gateway connection and market data are working perfectly!")
        else:
            print(f"\n⚠️  Some tests failed. Check the detailed report for more information.")
            print("\nCommon issues:")
            print("  • Market closed: Some data may not be available outside market hours")
            print("  • Subscription required: Level 2 data needs additional subscriptions")
            print("  • Delayed data: Switch between live/delayed based on your subscription")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        traceback.print_exc()
        return False
        
    finally:
        await tester.cleanup()

# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    print("🚀 SPYDER Market Data Test Suite")
    print(f"   Master Client ID: {MASTER_CLIENT_ID}")
    print(f"   Default Port: {PAPER_TRADING_PORT} (Paper Trading)")
    print()
    
    # Run the async main function
    success = asyncio.run(main())
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)