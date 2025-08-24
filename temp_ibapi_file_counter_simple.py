#!/usr/bin/env python3
"""
Simple IBAPI File Counter - Quick Summary Only

Shows just the files and counts without detailed analysis.
"""

import os
import re
from pathlib import Path

def count_ibapi_in_files():
    """Simple counter for IBAPI occurrences in Python files"""
    print("🔍 IBAPI FILE COUNTER - SUMMARY ONLY")
    print("=" * 60)
    
    # Pattern to match ibapi (case-insensitive)
    pattern = re.compile(r'\bibapi\b', re.IGNORECASE)
    
    file_counts = {}
    total_files_scanned = 0
    total_occurrences = 0
    
    # Scan all Python files
    for root, dirs, files in os.walk('.'):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', '.venv', 'venv'}]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, '.')
                total_files_scanned += 1
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    matches = pattern.findall(content)
                    if matches:
                        count = len(matches)
                        file_counts[relative_path] = count
                        total_occurrences += count
                        
                except Exception as e:
                    print(f"⚠️ Error reading {relative_path}: {e}")
    
    # Display results
    print(f"📊 SCAN RESULTS:")
    print(f"   • Files scanned: {total_files_scanned}")
    print(f"   • Files with IBAPI: {len(file_counts)}")
    print(f"   • Total occurrences: {total_occurrences}")
    
    if not file_counts:
        print(f"\n🎉 NO IBAPI USAGE FOUND!")
        print(f"✅ Your system is clean!")
        return
    
    print(f"\n📁 FILES WITH IBAPI OCCURRENCES:")
    print("-" * 60)
    
    # Sort by count (descending)
    sorted_files = sorted(file_counts.items(), key=lambda x: (-x[1], x[0]))
    
    print(f"{'FILE':<45} {'COUNT':>8}")
    print("-" * 53)
    
    for file_path, count in sorted_files:
        # Truncate long paths
        display_path = file_path
        if len(display_path) > 40:
            display_path = "..." + display_path[-37:]
        print(f"{display_path:<45} {count:>8}")
    
    print("-" * 53)
    print(f"{'TOTAL':<45} {total_occurrences:>8}")
    
    print(f"\n🔥 TOP FILES:")
    for i, (file_path, count) in enumerate(sorted_files[:5], 1):
        print(f"   {i}. {file_path} ({count})")

if __name__ == "__main__":
    count_ibapi_in_files()
