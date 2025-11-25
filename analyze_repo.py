#!/usr/bin/env python3
"""Repository analysis script for Spyder trading system."""

import os
from pathlib import Path
from collections import defaultdict
import subprocess

def count_lines_in_file(filepath):
    """Count non-empty lines in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

def analyze_repository():
    """Analyze the Spyder repository structure."""
    base_dir = Path('/home/user/Spyder')

    modules = {}
    total_lines = 0
    total_files = 0

    # Define module directories
    module_dirs = [
        'SpyderA_Core', 'SpyderB_Broker', 'SpyderC_MarketData', 'SpyderD_Strategies',
        'SpyderE_Risk', 'SpyderF_Analysis', 'SpyderG_GUI', 'SpyderH_Storage',
        'SpyderI_Integration', 'SpyderJ_Alerts', 'SpyderK_Reports', 'SpyderL_ML',
        'SpyderM_Monitoring', 'SpyderN_OptionsAnalytics', 'SpyderO_TradingIntelligence',
        'SpyderP_PortfolioMgmt', 'SpyderQ_Scripts', 'SpyderR_Runtime', 'SpyderS_Signals',
        'SpyderT_Testing', 'SpyderU_Utilities', 'SpyderV_QuantModels', 'SpyderX_Agents',
        'SpyderZ_Communication', 'config'
    ]

    for module_name in module_dirs:
        module_path = base_dir / module_name
        if module_path.exists():
            files = list(module_path.rglob('*.py'))
            lines = sum(count_lines_in_file(f) for f in files)
            modules[module_name] = {
                'files': len(files),
                'lines': lines
            }
            total_lines += lines
            total_files += len(files)

    # Print results
    print("=" * 70)
    print("SPYDER TRADING SYSTEM - REPOSITORY ANALYSIS")
    print("=" * 70)
    print(f"\n{'Module':<35} {'Lines':>10} {'Files':>8}")
    print("-" * 70)

    for module in sorted(modules.keys()):
        data = modules[module]
        print(f"{module:<35} {data['lines']:>10,} {data['files']:>8}")

    print("-" * 70)
    print(f"{'TOTAL':<35} {total_lines:>10,} {total_files:>8}")
    print("=" * 70)

    return modules, total_lines, total_files

if __name__ == '__main__':
    analyze_repository()
