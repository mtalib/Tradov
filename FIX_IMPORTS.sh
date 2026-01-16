#!/bin/bash
# Fix import errors by setting PYTHONPATH
# This resolves "No module named Spyder" errors

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Add project root to PYTHONPATH
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

echo "✅ PYTHONPATH set to: ${PYTHONPATH}"
echo "📝 To make this permanent, add this to your ~/.bashrc or ~/.zshrc:"
echo "   export PYTHONPATH=\"${SCRIPT_DIR}:\${PYTHONPATH}\""
echo ""
echo "🚀 Now you can run Spyder scripts from any directory with:"
echo "   python Spyder/SpyderT_Testing/SpyderT11_SharpeRatioCalculator.py"
