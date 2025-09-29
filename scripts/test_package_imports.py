#!/usr/bin/env python3
"""
Test script to verify all Spyder packages can be imported correctly
"""

import sys
import os

# Add Spyder root to path
spyder_root = "/home/adam/Projects/Spyder"
if spyder_root not in sys.path:
    sys.path.insert(0, spyder_root)


def test_package_import(package_name):
    """Test importing a single package"""
    try:
        __import__(package_name)
        return True, "OK"
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def main():
    packages = [
        "SpyderA_Core",
        "SpyderB_Broker",
        "SpyderC_MarketData",
        "SpyderD_Strategies",
        "SpyderE_Risk",
        "SpyderF_Analysis",
        "SpyderG_GUI",
        "SpyderH_Storage",
        "SpyderI_Integration",
        "SpyderJ_Alerts",
        "SpyderK_Reports",
        "SpyderL_ML",
        "SpyderM_Monitoring",
        "SpyderN_OptionsAnalytics",
        "SpyderO_TradingIntelligence",
        "SpyderP_PortfolioMgmt",
        "SpyderQ_Scripts",
        "SpyderR_Runtime",
        "SpyderS_Signals",
        "SpyderT_Testing",
        "SpyderU_Utilities",
        "SpyderV_QuantModels",
        "SpyderX_Agents",
        "SpyderZ_Communication",
    ]

    print("=== SPYDER PACKAGE IMPORT TEST ===\n")

    success_count = 0
    total_count = len(packages)
    failed_packages = []

    for package in packages:
        success, message = test_package_import(package)
        if success:
            print(f"✅ {package}: {message}")
            success_count += 1
        else:
            print(f"❌ {package}: {message}")
            failed_packages.append((package, message))

    print(f"\n=== SUMMARY ===")
    print(f"Total packages: {total_count}")
    print(f"Successfully imported: {success_count}")
    print(f"Failed imports: {total_count - success_count}")

    if failed_packages:
        print(f"\nFailed packages:")
        for package, error in failed_packages:
            print(f"  - {package}: {error}")

    success_rate = (success_count / total_count) * 100
    print(f"\nSuccess rate: {success_rate:.1f}%")

    return success_count == total_count


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
