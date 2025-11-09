#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - 8-Client Consolidation Analysis for TWS Mode
====================================================

Detailed analysis and visualization of how 11 clients are consolidated
into 8 clients for TWS API compatibility while maintaining full functionality.

Author: SPYDER AI System
Created: 2025-01-07
Purpose: Document and analyze client consolidation strategy

TWS LIMITATION: Maximum 8 concurrent client connections
GATEWAY CAPABILITY: 11+ concurrent client connections
SOLUTION: Smart consolidation with purpose grouping
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class ClientPurpose(Enum):
    """Client purposes for analysis"""

    ORDER_EXECUTION = "order_execution"
    ADMINISTRATIVE = "administrative"
    CORE_DATA = "core_data"
    OPTIONS_DATA = "options_data"
    VOLATILITY_DATA = "volatility_data"
    MARKET_INTERNALS = "market_internals"
    MAJOR_INDICES = "major_indices"
    EXTENDED_ASSETS = "extended_assets"
    SECTOR_ETFS = "sector_etfs"
    INTERNATIONAL = "international"
    NEWS_ALERTS = "news_alerts"


class DataPriority(Enum):
    """Data priority levels"""

    CRITICAL = 1  # Order execution
    SYSTEM = 2  # Administrative + News
    HIGH = 3  # Real-time trading data
    NORMAL = 4  # Important market data
    LOW = 5  # Background data
    BATCH = 6  # Bulk operations


@dataclass
class ClientConfiguration:
    """Client configuration details"""

    client_id: int
    purpose: ClientPurpose
    symbols: List[str]
    frequency: float
    priority: DataPriority
    description: str
    consolidated_purposes: List[ClientPurpose] = None
    news_types: List[str] = None


class ClientConsolidationAnalyzer:
    """Analyzer for client consolidation strategies"""

    def __init__(self):
        self.gateway_config = self._create_gateway_config()
        self.tws_config = self._create_tws_config()

    def _create_gateway_config(self) -> Dict[int, ClientConfiguration]:
        """Create Gateway mode configuration (11 clients)"""

        return {
            1: ClientConfiguration(
                client_id=1,
                purpose=ClientPurpose.ORDER_EXECUTION,
                symbols=[],
                frequency=0.0,
                priority=DataPriority.CRITICAL,
                description="Order execution - HIGHEST PRIORITY",
            ),
            2: ClientConfiguration(
                client_id=2,
                purpose=ClientPurpose.ADMINISTRATIVE,
                symbols=[],
                frequency=0.0,
                priority=DataPriority.SYSTEM,
                description="Account management, system control",
            ),
            3: ClientConfiguration(
                client_id=3,
                purpose=ClientPurpose.CORE_DATA,
                symbols=["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                frequency=1.0,
                priority=DataPriority.HIGH,
                description="Core market data - 1s updates",
            ),
            4: ClientConfiguration(
                client_id=4,
                purpose=ClientPurpose.OPTIONS_DATA,
                symbols=["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
                frequency=1.0,
                priority=DataPriority.HIGH,
                description="SPY options chains - 1s updates",
            ),
            5: ClientConfiguration(
                client_id=5,
                purpose=ClientPurpose.VOLATILITY_DATA,
                symbols=["VXV", "VXMT", "VVIX", "UVXY", "VIX9D"],
                frequency=5.0,
                priority=DataPriority.NORMAL,
                description="Volatility indicators - 5s updates",
            ),
            6: ClientConfiguration(
                client_id=6,
                purpose=ClientPurpose.MARKET_INTERNALS,
                symbols=["VUD", "TRIN", "ADD", "CPC", "PCALL", "SKEW"],
                frequency=5.0,
                priority=DataPriority.NORMAL,
                description="Market internals + VUD - 5s updates",
            ),
            7: ClientConfiguration(
                client_id=7,
                purpose=ClientPurpose.MAJOR_INDICES,
                symbols=["DIA", "QQQ", "IWM", "DIA_OPTIONS_1DTE", "QQQ_OPTIONS_1DTE"],
                frequency=5.0,
                priority=DataPriority.NORMAL,
                description="Major indices - 5s updates",
            ),
            8: ClientConfiguration(
                client_id=8,
                purpose=ClientPurpose.EXTENDED_ASSETS,
                symbols=["TLT", "LQD", "DXY", "GLD", "SPY_OPTIONS_WEEKLY"],
                frequency=15.0,
                priority=DataPriority.LOW,
                description="Extended assets - 15s updates",
            ),
            9: ClientConfiguration(
                client_id=9,
                purpose=ClientPurpose.SECTOR_ETFS,
                symbols=[
                    "XLF",
                    "XLK",
                    "XLE",
                    "XLV",
                    "XLI",
                    "XLY",
                    "XLP",
                    "XLU",
                    "XLRE",
                    "XLC",
                    "XLB",
                ],
                frequency=30.0,
                priority=DataPriority.LOW,
                description="Sector ETFs - 30s updates",
            ),
            10: ClientConfiguration(
                client_id=10,
                purpose=ClientPurpose.INTERNATIONAL,
                symbols=["FTLC", "AUD.JPY", "DAX", "HSI", "EWJ", "EWG", "EWU", "EWC"],
                frequency=60.0,
                priority=DataPriority.BATCH,
                description="International markets - 60s updates",
            ),
            11: ClientConfiguration(
                client_id=11,
                purpose=ClientPurpose.NEWS_ALERTS,
                symbols=[],
                frequency=0.0,
                priority=DataPriority.SYSTEM,
                description="News & Alerts - DEDICATED NEWS CLIENT",
                news_types=[
                    "breaking_news",
                    "market_news",
                    "earnings",
                    "economic_data",
                    "corporate_actions",
                    "analyst_upgrades",
                ],
            ),
        }

    def _create_tws_config(self) -> Dict[int, ClientConfiguration]:
        """Create TWS mode configuration (8 clients with consolidation)"""

        return {
            1: ClientConfiguration(
                client_id=1,
                purpose=ClientPurpose.ORDER_EXECUTION,
                symbols=[],
                frequency=0.0,
                priority=DataPriority.CRITICAL,
                description="Order execution - HIGHEST PRIORITY",
            ),
            2: ClientConfiguration(
                client_id=2,
                purpose=ClientPurpose.ADMINISTRATIVE,
                symbols=[],
                frequency=0.0,
                priority=DataPriority.SYSTEM,
                description="Administrative + News (CONSOLIDATED)",
                consolidated_purposes=[
                    ClientPurpose.ADMINISTRATIVE,
                    ClientPurpose.NEWS_ALERTS,
                ],
                news_types=["breaking_news", "market_news", "earnings"],
            ),
            3: ClientConfiguration(
                client_id=3,
                purpose=ClientPurpose.CORE_DATA,
                symbols=["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
                frequency=1.0,
                priority=DataPriority.HIGH,
                description="Core market data - 1s updates",
            ),
            4: ClientConfiguration(
                client_id=4,
                purpose=ClientPurpose.OPTIONS_DATA,
                symbols=["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
                frequency=1.0,
                priority=DataPriority.HIGH,
                description="SPY options chains - 1s updates",
            ),
            5: ClientConfiguration(
                client_id=5,
                purpose=ClientPurpose.VOLATILITY_DATA,
                symbols=[
                    "VXV",
                    "VXMT",
                    "VVIX",
                    "UVXY",
                    "VIX9D",
                    "VUD",
                    "TRIN",
                    "ADD",
                    "CPC",
                    "PCALL",
                    "SKEW",
                ],
                frequency=5.0,
                priority=DataPriority.NORMAL,
                description="Volatility + Market Internals (CONSOLIDATED)",
                consolidated_purposes=[
                    ClientPurpose.VOLATILITY_DATA,
                    ClientPurpose.MARKET_INTERNALS,
                ],
            ),
            6: ClientConfiguration(
                client_id=6,
                purpose=ClientPurpose.MAJOR_INDICES,
                symbols=["DIA", "QQQ", "IWM", "DIA_OPTIONS_1DTE", "QQQ_OPTIONS_1DTE"],
                frequency=5.0,
                priority=DataPriority.NORMAL,
                description="Major indices - 5s updates",
            ),
            7: ClientConfiguration(
                client_id=7,
                purpose=ClientPurpose.EXTENDED_ASSETS,
                symbols=[
                    "TLT",
                    "LQD",
                    "DXY",
                    "GLD",
                    "SPY_OPTIONS_WEEKLY",
                    "XLF",
                    "XLK",
                    "XLE",
                    "XLV",
                    "XLI",
                    "XLY",
                    "XLP",
                    "XLU",
                    "XLRE",
                    "XLC",
                    "XLB",
                ],
                frequency=30.0,
                priority=DataPriority.LOW,
                description="Extended Assets + Sectors (CONSOLIDATED)",
                consolidated_purposes=[
                    ClientPurpose.EXTENDED_ASSETS,
                    ClientPurpose.SECTOR_ETFS,
                ],
            ),
            8: ClientConfiguration(
                client_id=8,
                purpose=ClientPurpose.INTERNATIONAL,
                symbols=["FTLC", "AUD.JPY", "DAX", "HSI", "EWJ", "EWG", "EWU", "EWC"],
                frequency=60.0,
                priority=DataPriority.BATCH,
                description="International + Batch (CONSOLIDATED)",
                consolidated_purposes=[ClientPurpose.INTERNATIONAL],
            ),
        }

    def print_detailed_comparison(self):
        """Print detailed comparison between Gateway and TWS modes"""

        print("🕷️ SPYDER - 8-Client Consolidation Analysis")
        print("=" * 60)
        print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        print("🎯 CONSOLIDATION OVERVIEW")
        print("=" * 30)
        print("Gateway Mode: 11 clients (full separation)")
        print("TWS Mode: 8 clients (smart consolidation)")
        print("Consolidation Ratio: 11 → 8 clients (72.7% efficiency)")
        print()

        # Side-by-side comparison
        print("📊 DETAILED CLIENT MAPPING")
        print("=" * 40)
        print(f"{'GATEWAY MODE (11 clients)':<35} │ {'TWS MODE (8 clients)':<35}")
        print("─" * 35 + "┼" + "─" * 35)

        # Map Gateway clients to TWS clients
        gateway_to_tws_mapping = {
            1: 1,  # Order Execution → Order Execution
            2: 2,  # Administrative → Administrative + News
            3: 3,  # Core Data → Core Data
            4: 4,  # Options → Options
            5: 5,  # Volatility → Volatility + Market Internals
            6: 5,  # Market Internals → Volatility + Market Internals
            7: 6,  # Major Indices → Major Indices
            8: 7,  # Extended Assets → Extended Assets + Sectors
            9: 7,  # Sector ETFs → Extended Assets + Sectors
            10: 8,  # International → International + Batch
            11: 2,  # News → Administrative + News
        }

        # Print mapping
        for gw_id in sorted(self.gateway_config.keys()):
            gw_client = self.gateway_config[gw_id]
            tws_id = gateway_to_tws_mapping[gw_id]
            tws_client = self.tws_config[tws_id]

            gw_desc = f"Client {gw_id}: {gw_client.purpose.value}"
            tws_desc = f"Client {tws_id}: {tws_client.purpose.value}"

            # Add consolidation indicator
            if tws_client.consolidated_purposes:
                consolidation_marker = " (CONSOLIDATED)"
            else:
                consolidation_marker = ""

            print(f"{gw_desc:<35} │ {tws_desc + consolidation_marker:<35}")

        print()

        # Detailed consolidation breakdown
        print("🔀 CONSOLIDATION BREAKDOWN")
        print("=" * 35)

        for tws_id, tws_client in self.tws_config.items():
            print(f"\n🔌 TWS Client {tws_id}: {tws_client.description}")
            print(f"   Priority: {tws_client.priority.name}")
            print(f"   Update Frequency: {tws_client.frequency}s")
            print(f"   Symbols: {len(tws_client.symbols)} instruments")

            if tws_client.consolidated_purposes:
                print(f"   📦 CONSOLIDATES:")
                for purpose in tws_client.consolidated_purposes:
                    # Find original Gateway clients
                    original_clients = [
                        gw_id
                        for gw_id, gw_client in self.gateway_config.items()
                        if gw_client.purpose == purpose
                    ]
                    for orig_id in original_clients:
                        orig_client = self.gateway_config[orig_id]
                        print(
                            f"      └─ Gateway Client {orig_id}: {orig_client.description}"
                        )
                        if orig_client.symbols:
                            print(
                                f"         Symbols: {', '.join(orig_client.symbols[:3])}{'...' if len(orig_client.symbols) > 3 else ''}"
                            )

            if tws_client.news_types:
                print(f"   📰 NEWS TYPES: {', '.join(tws_client.news_types)}")

            if tws_client.symbols:
                print(
                    f"   📊 SAMPLE SYMBOLS: {', '.join(tws_client.symbols[:5])}{'...' if len(tws_client.symbols) > 5 else ''}"
                )

        print()

        # Performance impact analysis
        print("⚡ PERFORMANCE IMPACT ANALYSIS")
        print("=" * 40)

        gateway_total_symbols = sum(
            len(client.symbols) for client in self.gateway_config.values()
        )
        tws_total_symbols = sum(
            len(client.symbols) for client in self.tws_config.values()
        )

        print(f"Total Symbols:")
        print(f"   Gateway Mode: {gateway_total_symbols} symbols")
        print(f"   TWS Mode: {tws_total_symbols} symbols")
        print(
            f"   Symbol Retention: {(tws_total_symbols / gateway_total_symbols) * 100:.1f}%"
        )
        print()

        # Client load analysis
        print("📈 CLIENT LOAD ANALYSIS")
        print("─" * 25)

        for tws_id, tws_client in self.tws_config.items():
            symbol_count = len(tws_client.symbols)
            consolidated_count = len(tws_client.consolidated_purposes or [])

            load_level = "LOW"
            if symbol_count > 15 or consolidated_count > 1:
                load_level = "HIGH"
            elif symbol_count > 8 or consolidated_count > 0:
                load_level = "MEDIUM"

            print(
                f"Client {tws_id}: {symbol_count:2d} symbols, {consolidated_count} consolidations → {load_level} load"
            )

        print()

        # Consolidation benefits and risks
        print("✅ CONSOLIDATION BENEFITS")
        print("─" * 30)
        print("• ✅ TWS API compliance (8 client limit)")
        print("• ✅ Reduced connection overhead")
        print("• ✅ Simplified connection management")
        print("• ✅ Lower memory footprint")
        print("• ✅ Faster startup time")
        print("• ✅ Better resource utilization")
        print()

        print("⚠️ CONSOLIDATION CONSIDERATIONS")
        print("─" * 40)
        print("• ⚠️ Higher load per client connection")
        print("• ⚠️ Shared error handling between purposes")
        print("• ⚠️ News integrated with administrative functions")
        print("• ⚠️ Some update frequency compromises")
        print("• ⚠️ More complex client failure recovery")
        print()

        # Optimization recommendations
        print("🎯 OPTIMIZATION RECOMMENDATIONS")
        print("=" * 45)
        print("1. 🔄 Use Gateway mode when possible (11 clients)")
        print("2. 🤖 Implement auto-detection for seamless switching")
        print("3. 📊 Monitor client load and adjust symbol allocation")
        print("4. 🛡️ Implement robust error isolation within consolidated clients")
        print("5. 📰 Prioritize critical news types in consolidated news client")
        print("6. ⚡ Use connection pooling for better resource management")
        print("7. 📈 Consider adaptive frequency adjustment based on market conditions")
        print()

    def export_consolidation_matrix(self) -> Dict[str, Any]:
        """Export consolidation matrix for analysis"""

        # Create mapping matrix
        consolidation_matrix = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "gateway_clients": len(self.gateway_config),
                "tws_clients": len(self.tws_config),
                "consolidation_ratio": f"{len(self.tws_config)}/{len(self.gateway_config)}",
            },
            "gateway_mode": {},
            "tws_mode": {},
            "consolidation_mapping": {},
            "performance_metrics": {},
        }

        # Gateway mode details
        for client_id, client in self.gateway_config.items():
            consolidation_matrix["gateway_mode"][str(client_id)] = {
                "purpose": client.purpose.value,
                "description": client.description,
                "symbols": client.symbols,
                "frequency": client.frequency,
                "priority": client.priority.name,
                "symbol_count": len(client.symbols),
            }

        # TWS mode details
        for client_id, client in self.tws_config.items():
            consolidation_matrix["tws_mode"][str(client_id)] = {
                "purpose": client.purpose.value,
                "description": client.description,
                "symbols": client.symbols,
                "frequency": client.frequency,
                "priority": client.priority.name,
                "symbol_count": len(client.symbols),
                "consolidated_purposes": [
                    p.value for p in (client.consolidated_purposes or [])
                ],
                "news_types": client.news_types or [],
            }

        # Create reverse mapping (Gateway → TWS)
        gateway_to_tws = {
            1: 1,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
            6: 5,
            7: 6,
            8: 7,
            9: 7,
            10: 8,
            11: 2,
        }

        for gw_id, tws_id in gateway_to_tws.items():
            if str(tws_id) not in consolidation_matrix["consolidation_mapping"]:
                consolidation_matrix["consolidation_mapping"][str(tws_id)] = []

            consolidation_matrix["consolidation_mapping"][str(tws_id)].append(
                {
                    "gateway_client": gw_id,
                    "purpose": self.gateway_config[gw_id].purpose.value,
                    "symbols": len(self.gateway_config[gw_id].symbols),
                }
            )

        # Performance metrics
        gateway_symbols = sum(len(c.symbols) for c in self.gateway_config.values())
        tws_symbols = sum(len(c.symbols) for c in self.tws_config.values())

        consolidation_matrix["performance_metrics"] = {
            "total_symbols_gateway": gateway_symbols,
            "total_symbols_tws": tws_symbols,
            "symbol_retention_rate": (tws_symbols / gateway_symbols)
            if gateway_symbols > 0
            else 0,
            "average_symbols_per_client_gateway": gateway_symbols
            / len(self.gateway_config),
            "average_symbols_per_client_tws": tws_symbols / len(self.tws_config),
            "consolidation_efficiency": len(self.tws_config) / len(self.gateway_config),
        }

        return consolidation_matrix

    def save_analysis_report(self, filename: str = None):
        """Save detailed analysis report"""

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"client_consolidation_analysis_{timestamp}.json"

        consolidation_data = self.export_consolidation_matrix()

        try:
            with open(filename, "w") as f:
                json.dump(consolidation_data, f, indent=2)
            print(f"📄 Analysis report saved: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Failed to save report: {e}")
            return None


def main():
    """Main analysis function"""

    analyzer = ClientConsolidationAnalyzer()

    # Print detailed comparison
    analyzer.print_detailed_comparison()

    # Save analysis report
    report_file = analyzer.save_analysis_report()

    if report_file:
        print(f"\n💾 Detailed analysis data exported to: {report_file}")

    print("\n✅ Consolidation analysis completed")


if __name__ == "__main__":
    main()
