#!/bin/bash
# SPYDER - Verify SpyderF is Working Correctly

echo "=========================================="
echo "SPYDER - SpyderF Verification Script"
echo "=========================================="

# Step 1: Navigate to project directory
echo -e "\n1. Navigating to project directory..."
cd ~/Projects/Spyder
pwd

# Step 2: Check SpyderF_Analysis exists
echo -e "\n2. Checking SpyderF_Analysis directory..."
if [ -d "SpyderF_Analysis" ]; then
    echo "✓ SpyderF_Analysis directory exists"
    echo "Contents:"
    ls -la SpyderF_Analysis/ | grep -E "\.py$"
else
    echo "✗ SpyderF_Analysis directory NOT FOUND!"
    exit 1
fi

# Step 3: Verify all SpyderF modules are present
echo -e "\n3. Verifying all 10 SpyderF modules..."
REQUIRED_MODULES=(
    "SpyderF01_Indicators.py"
    "SpyderF02_PriceAction.py"
    "SpyderF03_SupportResistance.py"
    "SpyderF04_VolatilityAnalysis.py"
    "SpyderF05_TrendDetection.py"
    "SpyderF06_GreeksCalculator.py"
    "SpyderF07_GapAnalyzer.py"
    "SpyderF08_VolatilityRegime.py"
    "SpyderF09_EntryFilters.py"
    "SpyderF10_MarketRegimeDetector.py"
    "__init__.py"
)

MISSING_COUNT=0
for module in "${REQUIRED_MODULES[@]}"; do
    if [ -f "SpyderF_Analysis/$module" ]; then
        echo "✓ $module"
    else
        echo "✗ $module is MISSING!"
        ((MISSING_COUNT++))
    fi
done

if [ $MISSING_COUNT -gt 0 ]; then
    echo -e "\n⚠️  WARNING: $MISSING_COUNT modules are missing!"
fi

# Step 4: Activate virtual environment
echo -e "\n4. Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"

# Step 5: Set PYTHONPATH
echo -e "\n5. Setting PYTHONPATH..."
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
echo "✓ PYTHONPATH set to include: $(pwd)"

# Step 6: Test Python imports
echo -e "\n6. Testing Python imports..."
python3 << EOF
import sys
print("Python version:", sys.version)
print("\nPython path includes:")
for path in sys.path:
    if "Spyder" in path:
        print(f"  ✓ {path}")

print("\n7. Testing SpyderF imports...")
try:
    # Test each SpyderF module
    from SpyderF_Analysis import TechnicalIndicators
    print("✓ SpyderF01_Indicators imported successfully")
    
    from SpyderF_Analysis import PriceActionAnalyzer
    print("✓ SpyderF02_PriceAction imported successfully")
    
    from SpyderF_Analysis import SupportResistanceAnalyzer
    print("✓ SpyderF03_SupportResistance imported successfully")
    
    from SpyderF_Analysis import VolatilityAnalyzer
    print("✓ SpyderF04_VolatilityAnalysis imported successfully")
    
    from SpyderF_Analysis import TrendDetector
    print("✓ SpyderF05_TrendDetection imported successfully")
    
    from SpyderF_Analysis import GreeksCalculator
    print("✓ SpyderF06_GreeksCalculator imported successfully")
    
    from SpyderF_Analysis import GapAnalyzer
    print("✓ SpyderF07_GapAnalyzer imported successfully")
    
    from SpyderF_Analysis import VolatilityRegimeAnalyzer
    print("✓ SpyderF08_VolatilityRegime imported successfully")
    
    from SpyderF_Analysis import EntryFilters
    print("✓ SpyderF09_EntryFilters imported successfully")
    
    from SpyderF_Analysis import MarketRegimeDetector
    print("✓ SpyderF10_MarketRegimeDetector imported successfully")
    
    print("\n✅ All SpyderF modules imported successfully!")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("\nTroubleshooting:")
    print("1. Make sure you're in the project root directory")
    print("2. Verify all SpyderF modules are in SpyderF_Analysis/")
    print("3. Check that __init__.py exists in SpyderF_Analysis/")
    sys.exit(1)

print("\n8. Testing a simple SpyderF function...")
try:
    # Create an instance of TechnicalIndicators
    indicators = TechnicalIndicators()
    print("✓ TechnicalIndicators instance created")
    
    # Test a simple calculation
    import pandas as pd
    test_data = pd.Series([100, 101, 102, 101, 103, 104, 103, 105, 106, 105])
    sma = indicators.sma(test_data, period=5)
    print(f"✓ SMA calculation successful: Last value = {sma.iloc[-1]:.2f}")
    
except Exception as e:
    print(f"❌ Function test failed: {e}")

print("\n✅ SpyderF verification complete!")
EOF

# Step 7: Try running the main application
echo -e "\n9. Attempting to run SpyderA01_Main.py..."
echo "This will test if the entire system can start with SpyderF..."
echo -e "\nPress Ctrl+C to stop if the application starts successfully.\n"

# Run with timeout to avoid hanging
timeout 10s python SpyderA_Core/SpyderA01_Main.py 2>&1 | head -20

echo -e "\n=========================================="
echo "Verification Summary:"
echo "=========================================="
echo "If you see:"
echo "  - All modules imported successfully ✓"
echo "  - No import errors"
echo "  - The application started (even if it shows other errors)"
echo "Then SpyderF is working correctly!"
echo ""
echo "Next steps:"
echo "1. Fix any remaining errors (like missing config files, API keys, etc.)"
echo "2. Test with paper trading first"
echo "3. Plan gradual migration to SpyderX agents"
