#!/usr/bin/env python3
"""
Clean IBAPI Scanner - Exclude .venv and temp files
Focus only on actual Spyder project code
"""

import os
import re
from pathlib import Path

def clean_ibapi_scan():
    """Scan only Spyder project files (exclude .venv, temp files)"""
    print("🔍 CLEAN IBAPI SCAN - SPYDER PROJECT ONLY")
    print("=" * 60)
    
    # Pattern to match ibapi (case-insensitive)
    pattern = re.compile(r'\bibapi\b', re.IGNORECASE)
    
    # Directories to skip
    skip_dirs = {'.venv', 'venv', '.venv_py311', '__pycache__', '.git', 'build', 'dist'}
    
    # Files to skip
    skip_files = {'temp_scan_ibapi_systemwide.py', 'temp_ibapi_file_counter_simple.py', 'temp_clean_ibapi_scan.py'}
    
    file_counts = {}
    total_files_scanned = 0
    total_occurrences = 0
    
    # Scan Spyder project files only
    for root, dirs, files in os.walk('.'):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        
        for file in files:
            if file.endswith('.py') and file not in skip_files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, '.')
                
                # Skip if path contains any skip directory
                if any(skip_dir in relative_path for skip_dir in skip_dirs):
                    continue
                    
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
    print(f"📊 CLEAN SCAN RESULTS:")
    print(f"   • Spyder files scanned: {total_files_scanned}")
    print(f"   • Files with IBAPI: {len(file_counts)}")
    print(f"   • Total occurrences: {total_occurrences}")
    
    if not file_counts:
        print(f"\n🎉 NO IBAPI USAGE IN SPYDER CODE!")
        print(f"✅ Your Spyder project is clean!")
        print(f"✅ All modules using modern ib_async!")
        return
    
    print(f"\n📁 SPYDER FILES WITH IBAPI:")
    print("=" * 60)
    
    # Sort by count (descending)
    sorted_files = sorted(file_counts.items(), key=lambda x: (-x[1], x[0]))
    
    print(f"{'FILE':<50} {'COUNT':>8}")
    print("-" * 58)
    
    for file_path, count in sorted_files:
        print(f"{file_path:<50} {count:>8}")
    
    print("-" * 58)
    print(f"{'TOTAL':<50} {total_occurrences:>8}")
    
    # Show detailed analysis
    if sorted_files:
        print(f"\n🎯 MODERNIZATION TARGETS:")
        for i, (file_path, count) in enumerate(sorted_files, 1):
            if count >= 3:
                priority = "🔴 HIGH"
            elif count >= 2:
                priority = "🟡 MEDIUM"
            else:
                priority = "🟢 LOW"
            
            print(f"   {i}. {file_path} ({count} occurrences) - {priority}")
        
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   • Start with highest count files first")
        print(f"   • Focus on import statements: from ibapi → from ib_async")
        print(f"   • Update class usage: EClient/EWrapper → IB")
        print(f"   • Test each file after modernization")
        
        # Show most important file details
        top_file, top_count = sorted_files[0]
        print(f"\n🎯 PRIORITY FILE: {top_file}")
        print(f"   📍 {top_count} IBAPI references to modernize")
        print(f"   🔧 Open with: gedit {top_file}")

if __name__ == "__main__":
    clean_ibapi_scan()
