#!/bin/bash
# Test Script to Verify Dock Launcher Setup

echo "============================================================"
echo "Spyder Dock Launcher Verification Test"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check wrapper script exists
echo "Test 1: Checking wrapper script..."
if [ -f "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh" ]; then
    echo -e "${GREEN}✅ Wrapper script exists${NC}"
else
    echo -e "${RED}❌ Wrapper script NOT found${NC}"
    exit 1
fi

# Test 2: Check wrapper is executable
echo ""
echo "Test 2: Checking wrapper permissions..."
if [ -x "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh" ]; then
    echo -e "${GREEN}✅ Wrapper is executable${NC}"
else
    echo -e "${RED}❌ Wrapper is NOT executable${NC}"
    echo "Fix with: chmod +x \"/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh\""
    exit 1
fi

# Test 3: Check what wrapper calls
echo ""
echo "Test 3: Checking wrapper content..."
if grep -q "SpyderA01_Main.py\|launch_spyder_smart.sh" "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"; then
    echo -e "${GREEN}✅ Wrapper calls correct launcher${NC}"
    grep -E "python.*Spyder|exec.*launch_spyder" "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh" | sed 's/^/   → /'
else
    echo -e "${RED}❌ Wrapper calls WRONG launcher${NC}"
    echo "Expected: SpyderA01_Main.py or launch_spyder_smart.sh"
    echo "Found:"
    cat "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"
    exit 1
fi

# Test 4: Check SpyderA01_Main.py exists
echo ""
echo "Test 4: Checking main launcher..."
if [ -f "/home/adam/Projects/Spyder/SpyderA_Core/SpyderA01_Main.py" ]; then
    echo -e "${GREEN}✅ Main launcher exists${NC}"
else
    echo -e "${RED}❌ Main launcher NOT found${NC}"
    exit 1
fi

# Test 5: Check virtual environment
echo ""
echo "Test 5: Checking virtual environment..."
if [ -f "/home/adam/Projects/Spyder/.venv/bin/python" ]; then
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
    PYTHON_VERSION=$(/home/adam/Projects/Spyder/.venv/bin/python --version 2>&1)
    echo "   → $PYTHON_VERSION"
else
    echo -e "${RED}❌ Virtual environment NOT found${NC}"
    exit 1
fi

# Test 6: Check for old launcher (should NOT be called)
echo ""
echo "Test 6: Verifying old launcher is not used..."
if grep -q "SpyderQ14_MainLauncher" "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"; then
    echo -e "${RED}❌ PROBLEM: Wrapper still calls OLD launcher${NC}"
    echo "   → SpyderQ14_MainLauncher_DockFixed.py should NOT be used"
    exit 1
else
    echo -e "${GREEN}✅ Old launcher is not referenced${NC}"
fi

# Test 7: Check Gateway connection capability
echo ""
echo "Test 7: Checking Gateway connection test utility..."
if [ -f "/home/adam/Projects/Spyder/test_gateway_connection.py" ]; then
    echo -e "${GREEN}✅ Gateway test utility exists${NC}"
else
    echo -e "${YELLOW}⚠️  Gateway test utility not found${NC}"
fi

# Test 8: Check available launchers
echo ""
echo "Test 8: Available launcher scripts..."
for launcher in launch_spyder_smart.sh launch_spyder_direct.sh launch_spyder_with_gateway.sh; do
    if [ -f "/home/adam/Projects/Spyder/$launcher" ]; then
        if [ -x "/home/adam/Projects/Spyder/$launcher" ]; then
            echo -e "   ${GREEN}✅${NC} $launcher (executable)"
        else
            echo -e "   ${YELLOW}⚠️${NC}  $launcher (not executable)"
        fi
    else
        echo -e "   ${RED}❌${NC} $launcher (missing)"
    fi
done

# Summary
echo ""
echo "============================================================"
echo "Test Summary"
echo "============================================================"
echo ""
echo -e "${GREEN}✅ All critical tests passed!${NC}"
echo ""
echo "Your dock launcher is correctly configured to use:"
echo "   → SpyderA01_Main.py (with proven retry logic)"
echo ""
echo "Next steps:"
echo "1. Ensure .env has TRADIER_API_KEY configured"
echo "2. Click your Spyder dock icon"
echo "3. Dashboard should show broker API connected"
echo ""
echo "To test manually:"
echo '   "/home/adam/Projects/Spyder/Maestro Test Scripts/20250823_spyder_paper_wrapper.sh"'
echo ""
