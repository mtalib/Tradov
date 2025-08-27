#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IB GATEWAY HANDSHAKE ANALYZER

SPYDER - Autonomous Options Trading System v1.0

Module: temp_handshake_analyzer.py
Purpose: Deep analysis of IB Gateway handshake process to diagnose connection drops
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 16:30:00

Module Description:
    This diagnostic captures and analyzes the IB Gateway handshake process in detail.
    Since we can connect but get immediately disconnected, this will help identify
    the specific authentication or configuration issue causing the drop.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import sys
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("⚠️ nest_asyncio not available")

try:
    from ib_async import IB, util
    from ib_async.client import Client
    from ib_async.wrapper import Wrapper
except ImportError:
    print("❌ ib_async not available")
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST = "127.0.0.1"
PAPER_PORT = 4002

# ==============================================================================
# CUSTOM IB CLIENT WITH DETAILED LOGGING
# ==============================================================================

class DiagnosticIBClient:
    """
    Custom IB client that captures detailed handshake information.
    
    This class extends the standard IB client to provide detailed logging
    of the connection handshake process, authentication steps, and any
    error messages from the Gateway.
    """
    
    def __init__(self):
        """Initialize diagnostic client."""
        self.ib = None
        self.connection_events = []
        self.server_messages = []
        self.error_messages = []
        self.handshake_data = {}
        
        # Setup detailed logging
        self.logger = logging.getLogger('DiagnosticIB')
        self.logger.setLevel(logging.DEBUG)
        
        # Create handler if not exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def log_event(self, event: str, data: Any = None):
        """Log connection event with timestamp."""
        timestamp = datetime.now().isoformat()
        event_data = {
            'timestamp': timestamp,
            'event': event,
            'data': data
        }
        self.connection_events.append(event_data)
        self.logger.info(f"🔹 {event}: {data}")
    
    async def connect_with_detailed_logging(self, client_id: int, timeout: int = 30) -> Dict[str, Any]:
        """
        Connect with comprehensive logging of handshake process.
        
        Args:
            client_id: Client ID for connection
            timeout: Connection timeout
            
        Returns:
            Detailed connection results
        """
        result = {
            'client_id': client_id,
            'success': False,
            'error': None,
            'connection_events': [],
            'server_messages': [],
            'error_messages': [],
            'handshake_details': {},
            'timing_info': {}
        }
        
        start_time = time.time()
        
        try:
            self.log_event("CONNECTION_START", f"Client ID {client_id}, timeout {timeout}s")
            
            # Create IB instance with event handlers
            self.ib = IB()
            
            # Hook into IB events for detailed logging
            self.ib.connectedEvent += self._on_connected
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error
            self.ib.newOrderEvent += self._on_new_order
            
            # Capture wrapper events if possible
            if hasattr(self.ib, 'wrapper'):
                self.log_event("WRAPPER_AVAILABLE", "Can monitor wrapper events")
            
            self.log_event("IB_INSTANCE_CREATED", "IB object ready")
            
            # Start connection process
            connection_start = time.time()
            self.log_event("API_CONNECTION_START", f"Connecting to {DEFAULT_HOST}:{PAPER_PORT}")
            
            # Use a more detailed connection approach
            try:
                # This will attempt the connection
                await asyncio.wait_for(
                    self.ib.connectAsync(DEFAULT_HOST, PAPER_PORT, clientId=client_id, timeout=timeout),
                    timeout=timeout
                )
                
                connection_time = time.time() - connection_start
                self.log_event("CONNECTION_ATTEMPT_COMPLETE", f"Took {connection_time:.3f}s")
                
            except asyncio.TimeoutError:
                self.log_event("CONNECTION_TIMEOUT", f"After {timeout}s")
                result['error'] = f"Connection timeout after {timeout}s"
                return result
            
            # Check connection status
            if self.ib.isConnected():
                self.log_event("CONNECTION_VERIFIED", "isConnected() = True")
                result['success'] = True
                
                # Gather detailed server information
                try:
                    server_version = self.ib.serverVersion()
                    result['handshake_details']['server_version'] = server_version
                    self.log_event("SERVER_VERSION", server_version)
                    
                    connection_time = self.ib.reqCurrentTime()
                    result['handshake_details']['server_time'] = str(connection_time)
                    self.log_event("SERVER_TIME", connection_time)
                    
                    # Try to get managed accounts
                    accounts = self.ib.managedAccounts()
                    result['handshake_details']['managed_accounts'] = accounts
                    self.log_event("MANAGED_ACCOUNTS", accounts)
                    
                    # Try to get account summary
                    try:
                        account_values = self.ib.reqAccountSummary(
                            1, "All", "AccountType,TotalCashValue"
                        )
                        # Wait a bit for response
                        await asyncio.sleep(2)
                        result['handshake_details']['account_summary'] = len(account_values)
                        self.log_event("ACCOUNT_SUMMARY", f"Received {len(account_values)} values")
                        
                    except Exception as e:
                        self.log_event("ACCOUNT_SUMMARY_ERROR", str(e))
                        
                except Exception as e:
                    self.log_event("SERVER_INFO_ERROR", str(e))
                    result['handshake_details']['server_info_error'] = str(e)
                
            else:
                self.log_event("CONNECTION_FAILED", "isConnected() = False after connect()")
                result['error'] = "Connection not established"
            
        except Exception as e:
            self.log_event("CONNECTION_EXCEPTION", str(e))
            result['error'] = str(e)
        
        finally:
            # Capture all logged events
            result['connection_events'] = self.connection_events.copy()
            result['server_messages'] = self.server_messages.copy()
            result['error_messages'] = self.error_messages.copy()
            result['timing_info'] = {
                'total_time': time.time() - start_time,
                'start_time': start_time
            }
            
            # Disconnect if connected
            if self.ib and self.ib.isConnected():
                self.log_event("DISCONNECTING", "Cleaning up connection")
                self.ib.disconnect()
        
        return result
    
    def _on_connected(self):
        """Handler for connection events."""
        self.log_event("IB_CONNECTED_EVENT", "Connection established callback")
    
    def _on_disconnected(self):
        """Handler for disconnection events."""
        self.log_event("IB_DISCONNECTED_EVENT", "Disconnection callback")
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handler for error events."""
        error_info = {
            'reqId': reqId,
            'errorCode': errorCode,
            'errorString': errorString,
            'contract': str(contract) if contract else None
        }
        self.error_messages.append(error_info)
        self.log_event("IB_ERROR_EVENT", error_info)
        
        # Log specific error types
        if errorCode == 502:
            self.log_event("ERROR_502", "Couldn't connect to TWS - API not enabled?")
        elif errorCode == 503:
            self.log_event("ERROR_503", "The TWS is out of date")
        elif errorCode == 504:
            self.log_event("ERROR_504", "Not connected")
        elif errorCode == 1100:
            self.log_event("ERROR_1100", "Connectivity between IB and TWS has been lost")
        else:
            self.log_event(f"ERROR_{errorCode}", errorString)
    
    def _on_new_order(self, trade):
        """Handler for new order events."""
        self.log_event("NEW_ORDER_EVENT", str(trade))
    
    def print_detailed_report(self, result: Dict[str, Any]):
        """Print comprehensive diagnostic report."""
        print("\n" + "=" * 80)
        print("📊 DETAILED HANDSHAKE ANALYSIS REPORT")
        print("=" * 80)
        
        print(f"🆔 Client ID: {result['client_id']}")
        print(f"⏱️ Total Time: {result['timing_info']['total_time']:.3f}s")
        print(f"✅ Success: {result['success']}")
        
        if result['error']:
            print(f"❌ Error: {result['error']}")
        
        print("\n📅 CONNECTION EVENTS:")
        print("-" * 40)
        for event in result['connection_events']:
            timestamp = event['timestamp'].split('T')[1][:8]  # Just time part
            print(f"  {timestamp} | {event['event']}: {event['data']}")
        
        if result['error_messages']:
            print(f"\n🚨 ERROR MESSAGES ({len(result['error_messages'])}):")
            print("-" * 40)
            for error in result['error_messages']:
                print(f"  Code {error['errorCode']}: {error['errorString']}")
                if error['reqId'] != -1:
                    print(f"    Request ID: {error['reqId']}")
        
        if result['handshake_details']:
            print("\n🤝 HANDSHAKE DETAILS:")
            print("-" * 40)
            for key, value in result['handshake_details'].items():
                print(f"  {key}: {value}")
        
        print("\n💡 DIAGNOSTIC RECOMMENDATIONS:")
        print("-" * 40)
        
        if result['success']:
            print("  ✅ Connection successful! Gateway API is properly configured.")
            print("  🎯 This client ID can be used for Spyder integration.")
        else:
            # Analyze error patterns
            error_codes = [e['errorCode'] for e in result['error_messages']]
            
            if 502 in error_codes:
                print("  🔧 Error 502: API connection refused")
                print("     - Check Gateway API configuration")
                print("     - Ensure 'Enable ActiveX and Socket Clients' is checked")
                print("     - Verify socket port is 4002")
            
            if 503 in error_codes:
                print("  🔧 Error 503: Gateway version issue")
                print("     - Gateway may need updating")
                print("     - Check version compatibility")
            
            if not result['connection_events']:
                print("  🔧 No connection events recorded")
                print("     - Gateway may not be running")
                print("     - Check port accessibility")
            
            elif any("CONNECTION_TIMEOUT" in e['event'] for e in result['connection_events']):
                print("  🔧 Connection timeout detected")
                print("     - Gateway may be slow to respond")
                print("     - Check Gateway login status")
                print("     - Verify Gateway is fully initialized")
            
            else:
                print("  🔧 Connection established but failed during handshake")
                print("     - Authentication issue likely")
                print("     - Check Gateway login status")
                print("     - Verify account permissions")

# ==============================================================================
# MAIN DIAGNOSTIC FUNCTIONS
# ==============================================================================

async def analyze_handshake_for_client_id(client_id: int) -> Dict[str, Any]:
    """Analyze handshake process for specific client ID."""
    print(f"\n🔍 ANALYZING HANDSHAKE FOR CLIENT ID {client_id}")
    print("=" * 60)
    
    diagnostic_client = DiagnosticIBClient()
    result = await diagnostic_client.connect_with_detailed_logging(client_id, 20)
    
    diagnostic_client.print_detailed_report(result)
    
    return result

async def comprehensive_handshake_analysis():
    """Run comprehensive handshake analysis for multiple client IDs."""
    print("🕷️ SPYDER Gateway Handshake Analyzer")
    print("🔬 Deep dive into connection handshake process")
    print("=" * 70)
    
    successful_clients = []
    failed_analyses = []
    
    for client_id in range(1, 4):  # Test first 3 client IDs
        result = await analyze_handshake_for_client_id(client_id)
        
        if result['success']:
            successful_clients.append(client_id)
        else:
            failed_analyses.append(result)
    
    print("\n" + "=" * 70)
    print("📊 SUMMARY ANALYSIS")
    print("=" * 70)
    
    if successful_clients:
        print(f"✅ Successful Client IDs: {successful_clients}")
        print("🎯 Gateway API is working - use any successful client ID for Spyder")
    else:
        print("❌ No successful connections found")
        
        # Analyze common failure patterns
        all_errors = []
        for analysis in failed_analyses:
            all_errors.extend(analysis.get('error_messages', []))
        
        if all_errors:
            print(f"\n🚨 Found {len(all_errors)} total error messages")
            error_codes = [e['errorCode'] for e in all_errors]
            unique_codes = set(error_codes)
            
            print(f"🔢 Unique error codes: {sorted(unique_codes)}")
            
            for code in sorted(unique_codes):
                matching_errors = [e for e in all_errors if e['errorCode'] == code]
                print(f"   Code {code}: {matching_errors[0]['errorString']} (occurred {len(matching_errors)} times)")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

async def main():
    """Main execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="IB Gateway Handshake Analyzer")
    parser.add_argument("--client-id", type=int, help="Analyze specific client ID")
    
    args = parser.parse_args()
    
    if args.client_id:
        await analyze_handshake_for_client_id(args.client_id)
    else:
        await comprehensive_handshake_analysis()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Analysis interrupted by user")
