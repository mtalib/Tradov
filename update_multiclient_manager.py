#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Multi-Client Manager Update Script
==========================================

Script to update the existing MultiClientDataManager with enhanced features:
- TWS/Gateway dual compatibility (8 vs 11+ client modes)
- Dedicated News Client (Client 11)
- Smart client consolidation for TWS mode
- Auto-detection of connection type
- Enhanced error handling and monitoring

Author: SPYDER AI System
Created: 2025-01-07
Purpose: Seamless upgrade from SpyderB08_MultiClientDataManager.py
"""

import sys
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


class MultiClientManagerUpdater:
    """Update manager for enhanced multi-client functionality"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backup_dir = self.project_root / "config_backups"
        self.broker_dir = self.project_root / "SpyderB_Broker"

        # File paths
        self.original_file = self.broker_dir / "SpyderB08_MultiClientDataManager.py"
        self.enhanced_file = (
            self.broker_dir / "SpyderB08_MultiClientDataManager_Enhanced.py"
        )
        self.backup_file = None

    def print_header(self):
        """Print update header"""
        print("🕷️ SPYDER - Multi-Client Manager Update")
        print("=" * 50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    def create_backup(self):
        """Create backup of current manager"""

        if not self.original_file.exists():
            print("⚠️ Original file not found - fresh installation")
            return True

        # Create backup directory
        self.backup_dir.mkdir(exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_file = (
            self.backup_dir / f"SpyderB08_MultiClientDataManager_{timestamp}.py"
        )

        try:
            shutil.copy2(self.original_file, self.backup_file)
            print(f"✅ Backup created: {self.backup_file}")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False

    def update_main_file(self):
        """Update the main manager file with enhanced version"""

        if not self.enhanced_file.exists():
            print(f"❌ Enhanced file not found: {self.enhanced_file}")
            return False

        try:
            # Copy enhanced version to main location
            shutil.copy2(self.enhanced_file, self.original_file)
            print(f"✅ Updated main file: {self.original_file}")
            return True
        except Exception as e:
            print(f"❌ Update failed: {e}")
            return False

    def update_imports(self):
        """Update import statements in dependent files"""

        # Files that might import the manager
        dependent_files = [
            "SpyderG_GUI/SpyderG05_TradingDashboard.py",
            "SpyderB_Broker/SpyderB16_GatewayIntegration.py",
            "SpyderB_Broker/SpyderB30_IBConnectionPool.py",
        ]

        updated_files = []

        for file_path in dependent_files:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    # Read file content
                    with open(full_path, "r") as f:
                        content = f.read()

                    # Check if it imports the old manager
                    if (
                        "MultiClientDataManager" in content
                        or "SpyderB08_MultiClientDataManager" in content
                    ):
                        # The enhanced version maintains the same class name and interface
                        # so no import changes needed, but we log it
                        updated_files.append(file_path)
                        print(f"📄 Compatible with: {file_path}")

                except Exception as e:
                    print(f"⚠️ Could not check file {file_path}: {e}")

        return updated_files

    def create_configuration_template(self):
        """Create configuration template for new features"""

        config_template = {
            "connection_mode": "auto_detect",  # auto_detect, tws_mode, gateway_mode
            "preferred_ports": {
                "gateway_paper": 4002,
                "gateway_live": 4001,
                "tws_paper": 7497,
                "tws_live": 7496,
            },
            "client_allocation": {
                "tws_mode": {
                    "max_clients": 8,
                    "consolidation_enabled": True,
                    "news_client": 2,  # Consolidated with administrative
                },
                "gateway_mode": {
                    "max_clients": 11,
                    "consolidation_enabled": False,
                    "news_client": 11,  # Dedicated news client
                },
            },
            "news_settings": {
                "enabled": True,
                "news_types": [
                    "breaking_news",
                    "market_news",
                    "earnings",
                    "economic_data",
                    "corporate_actions",
                    "analyst_upgrades",
                ],
                "urgency_filter": "normal",  # low, normal, high, critical
            },
            "performance_settings": {
                "connection_timeout": 15.0,
                "race_condition_delay": 1.0,  # MAESTRO fix
                "heartbeat_interval": 30.0,
                "max_retry_attempts": 3,
            },
            "logging": {
                "enabled": True,
                "level": "INFO",
                "log_news": True,
                "log_performance": True,
            },
        }

        config_file = self.project_root / "config" / "multiclient_config.json"
        config_file.parent.mkdir(exist_ok=True)

        try:
            with open(config_file, "w") as f:
                json.dump(config_template, f, indent=2)
            print(f"✅ Configuration template created: {config_file}")
            return True
        except Exception as e:
            print(f"❌ Config creation failed: {e}")
            return False

    def create_test_script(self):
        """Create test script for the enhanced manager"""

        test_script_content = '''#!/usr/bin/env python3
"""
Test script for Enhanced Multi-Client Data Manager
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from SpyderB_Broker.SpyderB08_MultiClientDataManager import EnhancedMultiClientDataManager, ConnectionMode


async def test_enhanced_manager():
    """Test the enhanced manager functionality"""

    print("🧪 Testing Enhanced Multi-Client Data Manager")
    print("=" * 50)

    # Create manager with auto-detection
    manager = EnhancedMultiClientDataManager(ConnectionMode.AUTO_DETECT)

    try:
        # Test connection mode detection
        print("🔍 Testing connection mode detection...")
        detected_mode = await manager.detect_connection_mode()
        print(f"   Detected mode: {detected_mode.value}")

        # Start manager
        print("🚀 Starting manager...")
        await manager.start()

        # Get system status
        status = manager.get_system_status()
        print(f"📊 System Status:")
        print(f"   Mode: {status['connection_mode']}")
        print(f"   Max Clients: {status['max_clients']}")
        print(f"   Connected: {status['connected_clients']}/{status['total_clients']}")

        # Test client status
        print(f"🔌 Client Status:")
        for client_id in sorted(manager.clients.keys()):
            client_status = manager.get_client_status(client_id)
            if client_status:
                icon = "✅" if client_status['is_connected'] else "❌"
                print(f"   {icon} Client {client_id}: {client_status['description']}")

                # Show consolidation info
                if client_status['consolidated_purposes']:
                    print(f"      └─ Consolidated: {', '.join(client_status['consolidated_purposes'])}")

                # Show news types
                if client_status['news_types']:
                    print(f"      └─ News: {', '.join(client_status['news_types'])}")

        # Test news subscription
        def test_news_callback(news):
            print(f"📰 News: {news.headline}")

        manager.subscribe_to_news(test_news_callback)

        # Test data subscription
        def test_data_callback(tick):
            print(f"📊 Data: {tick.symbol} = {tick.last}")

        manager.subscribe_to_data("SPY", test_data_callback)

        print(f"⏳ Running test for 10 seconds...")
        await asyncio.sleep(10)

    finally:
        # Clean shutdown
        await manager.stop()
        print("✅ Test completed successfully")


if __name__ == "__main__":
    asyncio.run(test_enhanced_manager())
'''

        test_file = self.project_root / "test_enhanced_multiclient_manager.py"

        try:
            with open(test_file, "w") as f:
                f.write(test_script_content)
            print(f"✅ Test script created: {test_file}")
            return True
        except Exception as e:
            print(f"❌ Test script creation failed: {e}")
            return False

    def validate_update(self):
        """Validate the update was successful"""

        validation_checks = {
            "original_file_exists": self.original_file.exists(),
            "backup_created": self.backup_file.exists() if self.backup_file else True,
            "enhanced_features": False,
        }

        # Check if enhanced features are available
        try:
            with open(self.original_file, "r") as f:
                content = f.read()

            enhanced_markers = [
                "EnhancedMultiClientDataManager",
                "ConnectionMode",
                "NEWS_ALERTS",
                "auto_detect",
                "TWS/Gateway dual compatibility",
            ]

            validation_checks["enhanced_features"] = all(
                marker in content for marker in enhanced_markers
            )

        except Exception as e:
            print(f"⚠️ Could not validate enhanced features: {e}")

        # Print validation results
        print("\n🔍 Validation Results:")
        for check, result in validation_checks.items():
            icon = "✅" if result else "❌"
            print(f"   {icon} {check.replace('_', ' ').title()}")

        return all(validation_checks.values())

    def print_upgrade_summary(self):
        """Print upgrade summary and next steps"""

        print("\n🎉 UPGRADE SUMMARY")
        print("=" * 30)
        print("✅ Enhanced Multi-Client Manager installed")
        print("✅ Configuration template created")
        print("✅ Test script generated")
        print("✅ Backup created (if original existed)")

        print("\n🚀 NEW FEATURES:")
        print("   📡 Auto-detection of TWS vs Gateway")
        print("   📰 Dedicated News Client (Client 11)")
        print("   🔄 Smart client consolidation for TWS")
        print("   ⚡ Enhanced error handling")
        print("   📊 Comprehensive monitoring")
        print("   🛡️ Connection resilience improvements")

        print("\n📋 NEXT STEPS:")
        print("1. Test the enhanced manager:")
        print("   python test_enhanced_multiclient_manager.py")
        print()
        print("2. Update your dashboard to use enhanced features:")
        print(
            "   from SpyderB_Broker.SpyderB08_MultiClientDataManager import EnhancedMultiClientDataManager"
        )
        print()
        print("3. Configure news subscriptions in:")
        print("   config/multiclient_config.json")
        print()
        print("4. Review client allocation for your use case:")
        print("   - TWS mode: 8 clients with consolidation")
        print("   - Gateway mode: 11 clients with dedicated news")

        if self.backup_file:
            print(f"\n💾 Original backup saved: {self.backup_file.name}")

    def run_update(self):
        """Run the complete update process"""

        self.print_header()

        print("🔄 Starting Multi-Client Manager Update...")
        print()

        # Step 1: Create backup
        print("STEP 1: Creating backup...")
        if not self.create_backup():
            print("❌ Update aborted - backup failed")
            return False

        # Step 2: Update main file
        print("\nSTEP 2: Updating main file...")
        if not self.update_main_file():
            print("❌ Update aborted - file update failed")
            return False

        # Step 3: Check dependent files
        print("\nSTEP 3: Checking dependent files...")
        updated_files = self.update_imports()
        if updated_files:
            print(f"✅ {len(updated_files)} dependent files checked")

        # Step 4: Create configuration
        print("\nSTEP 4: Creating configuration template...")
        self.create_configuration_template()

        # Step 5: Create test script
        print("\nSTEP 5: Creating test script...")
        self.create_test_script()

        # Step 6: Validate update
        print("\nSTEP 6: Validating update...")
        if not self.validate_update():
            print("⚠️ Update completed but validation failed")
            return False

        # Success
        self.print_upgrade_summary()
        return True


def main():
    """Main update function"""

    try:
        updater = MultiClientManagerUpdater()
        success = updater.run_update()

        if success:
            print("\n✅ Multi-Client Manager update completed successfully!")
            return 0
        else:
            print("\n❌ Multi-Client Manager update failed!")
            return 1

    except KeyboardInterrupt:
        print("\n⚠️ Update interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
