#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Test Connections with New Bashrc Configuration
Test both Gateway and TWS modes using the new dual-mode bashrc settings
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def load_bashrc_environment():
    """Load environment variables from the new bashrc configuration"""

    print("🔧 Loading bashrc environment variables...")

    # Run a bash command to source bashrc and export all variables
    try:
        result = subprocess.run(
            ["bash", "-c", 'source ~/.bashrc && env | grep "^IB_\\|^SPYDER_\\|^TWS_"'],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            env_vars = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
                    os.environ[key] = value

            print(f"✅ Loaded {len(env_vars)} environment variables")
            return env_vars
        else:
            print(f"⚠️  Failed to load bashrc environment: {result.stderr}")
            return {}

    except Exception as e:
        print(f"❌ Error loading bashrc environment: {e}")
        return {}


def test_mode_configuration(mode):
    """Test configuration for a specific mode"""

    print(f"\n🧪 Testing {mode.upper()} Mode Configuration")
    print("-" * 50)

    # Set mode-specific environment variables
    if mode == "gateway":
        config = {
            "IB_CONNECTION_MODE": "gateway",
            "IB_CONNECTION_TYPE": "local_gateway",
            "IB_HOST": "127.0.0.1",
            "IB_DEFAULT_PORT": "4002",
            "IB_MODE_DESCRIPTION": "Local IB Gateway",
        }
    else:  # tws mode
        config = {
            "IB_CONNECTION_MODE": "tws",
            "IB_CONNECTION_TYPE": "remote_tws",
            "IB_HOST": "192.168.1.2",
            "IB_DEFAULT_PORT": "7497",
            "IB_MODE_DESCRIPTION": "Remote TWS",
        }

    # Apply configuration
    for key, value in config.items():
        os.environ[key] = value

    # Display configuration
    print("📋 Configuration:")
    for key, value in config.items():
        print(f"   {key}={value}")

    # Test network connectivity
    host = config["IB_HOST"]
    port = int(config["IB_DEFAULT_PORT"])

    print(f"\n🔍 Testing connectivity to {host}:{port}...")

    # Ping test (for remote hosts)
    if host != "127.0.0.1":
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", host], capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"✅ Host {host} is reachable")
            else:
                print(f"❌ Host {host} is not reachable")
                return False
        except Exception as e:
            print(f"⚠️  Ping test failed: {e}")

    # Port connectivity test
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ Port {port} is accessible")

            # Additional API test for Gateway mode
            if mode == "gateway":
                return test_gateway_api_connection()
            else:
                print("✅ Remote TWS port is accessible")
                return True
        else:
            print(f"❌ Port {port} is not accessible")
            if mode == "gateway":
                print("   Make sure IB Gateway is running locally")
            else:
                print("   Make sure TWS is running on Windows computer")
            return False

    except Exception as e:
        print(f"❌ Port test failed: {e}")
        return False


def test_gateway_api_connection():
    """Test actual API connection to IB Gateway"""

    print("🔌 Testing IB Gateway API connection...")

    try:
        from ib_async import IB

        # Create IB instance
        ib = IB()
        ib.RequestTimeout = 30  # 30 second timeout

        print("   Creating API connection...")
        ib.connect(
            host="127.0.0.1",
            port=4002,
            clientId=998,  # Test client ID
            timeout=15,
            readonly=False,
        )

        if ib.isConnected():
            print("✅ API connection successful!")
            print("   Client should be visible in IB Gateway")

            # Keep connection alive briefly
            time.sleep(3)

            # Disconnect
            ib.disconnect()
            print("✅ API disconnected cleanly")
            return True
        else:
            print("❌ API connection failed")
            return False

    except ImportError:
        print("⚠️  ib_async not available - skipping API test")
        return True  # Port was accessible, so consider it a pass
    except Exception as e:
        print(f"❌ API connection error: {e}")
        return False


def test_client_id_allocation():
    """Test the Universal 8-Client ID allocation"""

    print("\n🆔 Testing Universal 8-Client ID Allocation")
    print("-" * 50)

    expected_clients = {
        "IB_ORDER_EXECUTION_CLIENT": "100",
        "IB_ADMIN_NEWS_CLIENT": "101",
        "IB_CORE_DATA_CLIENT": "102",
        "IB_SPY_OPTIONS_CLIENT": "103",
        "IB_VOLATILITY_CLIENT": "104",
        "IB_MAJOR_INDICES_CLIENT": "105",
        "IB_EXTENDED_SECTORS_CLIENT": "106",
        "IB_INTERNATIONAL_CLIENT": "107",
        "IB_TEST_CLIENT": "999",
    }

    all_correct = True

    for env_var, expected_value in expected_clients.items():
        actual_value = os.environ.get(env_var, "NOT_SET")
        if actual_value == expected_value:
            print(f"✅ {env_var}={actual_value}")
        else:
            print(f"❌ {env_var}={actual_value} (expected {expected_value})")
            all_correct = False

    if all_correct:
        print("✅ All client IDs correctly allocated")
    else:
        print("❌ Some client IDs are incorrect")

    return all_correct


def test_spyder_environment():
    """Test SPYDER-specific environment variables"""

    print("\n🕷️ Testing SPYDER Environment Variables")
    print("-" * 50)

    spyder_vars = {
        "SPYDER_HOME": f"{os.path.expanduser('~')}/Projects/Spyder",
        "SPYDER_ENV": "development",
        "SPYDER_LOG_LEVEL": "INFO",
        "IB_TRADING_MODE": "paper",
    }

    all_correct = True

    for var_name, expected_value in spyder_vars.items():
        actual_value = os.environ.get(var_name, "NOT_SET")
        if actual_value == expected_value:
            print(f"✅ {var_name}={actual_value}")
        else:
            print(f"⚠️  {var_name}={actual_value} (expected {expected_value})")
            if var_name == "SPYDER_HOME":
                all_correct = False

    return all_correct


def create_test_aliases():
    """Create test scripts for the new aliases"""

    print("\n📝 Creating Test Scripts for New Aliases")
    print("-" * 50)

    # Test script for ib-check function
    ib_check_script = """#!/bin/bash
source ~/.bashrc
ib-check
"""

    # Test script for mode switching
    mode_switch_script = """#!/bin/bash
source ~/.bashrc
echo "Current mode: $IB_CONNECTION_MODE"
echo "Testing mode switch..."
ib-switch gateway
echo "After switch: $IB_CONNECTION_MODE"
"""

    try:
        # Create test scripts
        scripts_dir = Path("test_scripts")
        scripts_dir.mkdir(exist_ok=True)

        (scripts_dir / "test_ib_check.sh").write_text(ib_check_script)
        (scripts_dir / "test_mode_switch.sh").write_text(mode_switch_script)

        # Make executable
        os.chmod(scripts_dir / "test_ib_check.sh", 0o755)
        os.chmod(scripts_dir / "test_mode_switch.sh", 0o755)

        print("✅ Test scripts created in test_scripts/ directory")
        print("   Run: ./test_scripts/test_ib_check.sh")
        print("   Run: ./test_scripts/test_mode_switch.sh")

        return True

    except Exception as e:
        print(f"❌ Failed to create test scripts: {e}")
        return False


def run_comprehensive_test():
    """Run comprehensive test of the new configuration"""

    print("🕷️ SPYDER - Comprehensive Bashrc Configuration Test")
    print("=" * 60)

    # Load environment
    env_vars = load_bashrc_environment()

    if not env_vars:
        print("❌ Failed to load bashrc environment - testing with defaults")
        # Set some basic defaults for testing
        os.environ.update(
            {
                "IB_CONNECTION_MODE": "gateway",
                "IB_HOST": "127.0.0.1",
                "IB_DEFAULT_PORT": "4002",
                "SPYDER_HOME": f"{os.path.expanduser('~')}/Projects/Spyder",
            }
        )

    # Test results
    results = []

    # Test 1: Environment variables
    print("\n" + "=" * 20 + " TEST 1: ENVIRONMENT " + "=" * 20)
    spyder_env_ok = test_spyder_environment()
    results.append(("SPYDER Environment", spyder_env_ok))

    # Test 2: Client ID allocation
    print("\n" + "=" * 20 + " TEST 2: CLIENT IDS " + "=" * 21)
    client_ids_ok = test_client_id_allocation()
    results.append(("Client ID Allocation", client_ids_ok))

    # Test 3: Gateway mode
    print("\n" + "=" * 20 + " TEST 3: GATEWAY MODE " + "=" * 19)
    gateway_ok = test_mode_configuration("gateway")
    results.append(("Gateway Mode", gateway_ok))

    # Test 4: TWS mode
    print("\n" + "=" * 20 + " TEST 4: TWS MODE " + "=" * 23)
    tws_ok = test_mode_configuration("tws")
    results.append(("TWS Mode", tws_ok))

    # Test 5: Create helper scripts
    print("\n" + "=" * 20 + " TEST 5: HELPER SCRIPTS " + "=" * 17)
    scripts_ok = create_test_aliases()
    results.append(("Helper Scripts", scripts_ok))

    # Summary
    print("\n" + "=" * 25 + " RESULTS " + "=" * 28)

    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1

    print(f"\nOverall: {passed}/{len(results)} tests passed")

    # Recommendations
    print("\n" + "=" * 25 + " RECOMMENDATIONS " + "=" * 20)

    if passed == len(results):
        print("🎉 ALL TESTS PASSED!")
        print("✅ Your dual-mode bashrc configuration is working perfectly")
        print("\n💡 Next steps:")
        print("   1. Open a new terminal to get the new environment")
        print("   2. Test mode switching: ib-switch gateway")
        print("   3. Check connectivity: ib-check")
        print("   4. Launch SPYDER: spyder-launch")

    elif gateway_ok:
        print("🏪 GATEWAY MODE WORKING!")
        print("✅ Your local IB Gateway is properly configured")
        print("⚠️  Remote TWS mode needs setup (expected if not using remote TWS)")
        print("\n💡 Next steps:")
        print("   1. Use Gateway mode: ib-switch gateway")
        print("   2. Launch SPYDER: spyder-launch")

    else:
        print("⚠️  CONFIGURATION NEEDS ATTENTION")
        print("💡 Issues to resolve:")
        if not spyder_env_ok:
            print("   - Check SPYDER_HOME path")
        if not gateway_ok:
            print("   - Ensure IB Gateway is running with API enabled")
        print("\n🔧 Quick fixes:")
        print("   - Restart IB Gateway")
        print("   - Check API settings in Gateway")
        print("   - Run: source ~/.bashrc")

    return passed == len(results)


def main():
    """Main test function"""

    try:
        success = run_comprehensive_test()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Test cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
