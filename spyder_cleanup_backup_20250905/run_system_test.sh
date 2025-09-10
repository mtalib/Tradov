#!/bin/bash

# ==============================================================================
# SPYDER SYSTEM TEST RUNNER
# Purpose: Quick and easy way to test the entire Spyder system
# Author: Mohamed Talib
# Date: 2025-08-13
# ==============================================================================

echo "======================================================================"
echo "SPYDER SYSTEM TEST RUNNER"
# Initialize test result
TEST_RESULT=1

echo "======================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${2}${1}${NC}"
}

# Check Python version
print_status "Checking Python version..." "$BLUE"
python_version=$(python3 --version 2>&1)
echo "  $python_version"

# Check if in correct directory
if [ ! -d "SpyderS_Signals" ]; then
    print_status "⚠️  Warning: SpyderS_Signals directory not found" "$YELLOW"
    print_status "   Make sure you're in the Spyder root directory" "$YELLOW"
fi

# Parse command line arguments
GUI_MODE=""
VERBOSE=""
QUICK_TEST=""

for arg in "$@"
do
    case $arg in
        --gui)
            GUI_MODE="--gui"
            print_status "GUI mode enabled" "$BLUE"
            shift
            ;;
        --verbose)
            VERBOSE="--verbose"
            print_status "Verbose mode enabled" "$BLUE"
            shift
            ;;
        --quick)
            QUICK_TEST="--quick"
            print_status "Quick test mode enabled" "$BLUE"
            shift
            ;;
        --help)
            echo "Usage: ./run_system_test.sh [options]"
            echo ""
            echo "Options:"
            echo "  --gui      Run with GUI dashboard"
            echo "  --verbose  Show detailed output"
            echo "  --quick    Run quick test (signals only)"
            echo "  --help     Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# ==============================================================================
# PRE-TEST CHECKS
# ==============================================================================

print_status "\n📋 Running Pre-Test Checks..." "$YELLOW"

# Check if S-Series migration is complete
echo -n "  Checking S-Series modules... "
if [ -f "SpyderS_Signals/SpyderS07_CustomMetricsOrchestrator.py" ]; then
    print_status "✅" "$GREEN"
else
    print_status "❌ S07 Orchestrator not found!" "$RED"
    print_status "   Run migration script first!" "$RED"
    exit 1
fi

# Check for test results directory
if [ ! -d "test_results" ]; then
    mkdir -p test_results
    print_status "  Created test_results directory" "$GREEN"
fi

# ==============================================================================
# RUN TESTS
# ==============================================================================

print_status "\n🚀 Starting System Test..." "$BLUE"
echo "======================================================================"

# Set Python path to include current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run the appropriate test
if [ "$QUICK_TEST" == "--quick" ]; then
    # Quick test - just signals
    print_status "Running quick signal test..." "$YELLOW"
    python3 -c "
from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import CustomMetricsOrchestrator
import time

print('Testing S-Series Signals...')
orchestrator = CustomMetricsOrchestrator()
orchestrator.update_all_metrics()
metrics = orchestrator.get_all_metrics()

print('\\nSignal Values:')
print(f'  GEX: {metrics[\"GEX\"]:.2f}B')
print(f'  DIX: {metrics[\"DIX\"]:.1f}%')
print(f'  SWAN: {metrics[\"SWAN\"]:.2f}')
print(f'  SKEW: {metrics[\"SKEW\"]:.1f}')
print('\\n✅ Quick test complete!')
"
else
    # Full system test
    if [ -f "SpyderT_Testing/SpyderT15_FullSystemTest.py" ]; then
        python3 SpyderT_Testing/SpyderT15_FullSystemTest.py $GUI_MODE $VERBOSE
        TEST_RESULT=$?
    else
        print_status "⚠️  T15 test file not found, running inline test..." "$YELLOW"
        
        # Inline test if file doesn't exist
        python3 << 'EOF'
import sys
import os
sys.path.insert(0, os.getcwd())

print("\n=== INLINE SYSTEM TEST ===\n")

# Test imports
test_results = {}

try:
    from SpyderS_Signals.SpyderS01_DIXCalculator import DIXCalculator
    test_results['S01_DIX'] = "✅"
    print("✅ S01_DIXCalculator imported")
except ImportError as e:
    test_results['S01_DIX'] = f"❌ {e}"
    print(f"❌ S01_DIXCalculator: {e}")

try:
    from SpyderS_Signals.SpyderS03_BlackSwanIndicator import BlackSwanIndicator
    test_results['S03_SWAN'] = "✅"
    print("✅ S03_BlackSwanIndicator imported")
except ImportError as e:
    test_results['S03_SWAN'] = f"❌ {e}"
    print(f"❌ S03_BlackSwanIndicator: {e}")

try:
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import GEXDEXCalculator
    test_results['S05_GEX'] = "✅"
    print("✅ S05_GEXDEXCalculator imported")
except ImportError as e:
    test_results['S05_GEX'] = f"❌ {e}"
    print(f"❌ S05_GEXDEXCalculator: {e}")

try:
    from SpyderS_Signals.SpyderS06_SKEWCalculator import SKEWCalculator
    test_results['S06_SKEW'] = "✅"
    print("✅ S06_SKEWCalculator imported")
except ImportError as e:
    test_results['S06_SKEW'] = f"❌ {e}"
    print(f"❌ S06_SKEWCalculator: {e}")

try:
    from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import CustomMetricsOrchestrator
    test_results['S07_Orchestrator'] = "✅"
    print("✅ S07_CustomMetricsOrchestrator imported")
    
    # Test orchestrator
    print("\n🔄 Testing Orchestrator Integration...")
    orchestrator = CustomMetricsOrchestrator()
    orchestrator.update_all_metrics()
    metrics = orchestrator.get_all_metrics()
    
    print("\n📊 Current Signal Values:")
    print(f"  GEX: {metrics.get('GEX', 0):.2f}B")
    print(f"  DIX: {metrics.get('DIX', 0):.1f}%")
    print(f"  SWAN: {metrics.get('SWAN', 0):.2f}")
    print(f"  SKEW: {metrics.get('SKEW', 0):.1f}")
    
except ImportError as e:
    test_results['S07_Orchestrator'] = f"❌ {e}"
    print(f"❌ S07_CustomMetricsOrchestrator: {e}")

# Summary
print("\n" + "="*50)
print("TEST SUMMARY")
print("="*50)

success_count = sum(1 for v in test_results.values() if v == "✅")
total_count = len(test_results)
success_rate = (success_count / total_count * 100) if total_count > 0 else 0

print(f"Success Rate: {success_rate:.1f}% ({success_count}/{total_count})")

if success_rate >= 80:
    print("\n✅ SYSTEM TEST PASSED!")
    sys.exit(0)
else:
    print("\n❌ SYSTEM TEST FAILED!")
    sys.exit(1)
EOF
        TEST_RESULT=$?
    fi
fi

# ==============================================================================
# POST-TEST ACTIONS
# ==============================================================================

echo ""
echo "======================================================================"

if [ "$TEST_RESULT" -eq 0 ]; then
    print_status "✅ SYSTEM TEST COMPLETED SUCCESSFULLY!" "$GREEN"
    
    # Show latest test results
    if [ -d "test_results" ]; then
        latest_result=$(ls -t test_results/*.json 2>/dev/null | head -1)
        if [ -n "$latest_result" ]; then
            print_status "\n📄 Test results saved to: $latest_result" "$BLUE"
        fi
    fi
    
    print_status "\n🎯 Next Steps:" "$YELLOW"
    echo "  1. Review test results in test_results/ directory"
    echo "  2. Check logs in logs/ directory"
    echo "  3. Run with --gui flag to see visual dashboard"
    echo "  4. Start paper trading test with ./SpyderQ10_StartAll.sh"
    
else
    print_status "❌ SYSTEM TEST FAILED!" "$RED"
    print_status "\n🔧 Troubleshooting:" "$YELLOW"
    echo "  1. Check import errors above"
    echo "  2. Verify all S-Series modules are in place"
    echo "  3. Run migration script if needed"
    echo "  4. Check Python dependencies"
fi

echo ""
echo "======================================================================"
