#!/bin/bash
# Test Coverage Report Script for Spyder Trading System

echo "======================================================================"
echo "SPYDER TEST COVERAGE ANALYSIS"
echo "======================================================================"
echo ""

# Check if pytest and pytest-cov are installed
if ! python -m pytest --version &> /dev/null; then
    echo "❌ pytest not found. Installing..."
    pip install pytest pytest-cov
fi

# Create coverage directory if it doesn't exist
mkdir -p coverage_html

echo "Running tests with coverage analysis..."
echo "This may take a few minutes..."
echo ""

# Run pytest with coverage
python -m pytest \
    SpyderT_Testing/ \
    --cov=. \
    --cov-report=term-missing \
    --cov-report=html:coverage_html \
    --cov-report=json:coverage.json \
    -v \
    --tb=short \
    2>&1 | tee coverage_output.txt

# Check exit code
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "✅ TEST COVERAGE ANALYSIS COMPLETE"
    echo "======================================================================"
    echo ""
    echo "Reports generated:"
    echo "  📊 HTML Report: coverage_html/index.html"
    echo "  📄 JSON Report: coverage.json"
    echo "  📝 Terminal Output: coverage_output.txt"
    echo ""
    echo "To view HTML report:"
    echo "  xdg-open coverage_html/index.html"
    echo ""
else
    echo ""
    echo "======================================================================"
    echo "⚠️  TESTS COMPLETED WITH FAILURES"
    echo "======================================================================"
    echo ""
    echo "Some tests failed, but coverage report was generated."
    echo "Review coverage_output.txt for details."
    echo ""
fi

# Display coverage summary if available
if [ -f coverage.json ]; then
    echo "Coverage Summary:"
    echo "----------------------------------------------------------------------"
    python3 << 'PYTHON_SCRIPT'
import json
import sys

try:
    with open('coverage.json', 'r') as f:
        data = json.load(f)

    total = data['totals']
    percent = total['percent_covered']

    # Determine status emoji
    if percent >= 70:
        status = "✅ GOOD"
    elif percent >= 50:
        status = "⚠️  FAIR"
    else:
        status = "❌ NEEDS IMPROVEMENT"

    print(f"  Total Coverage: {percent:.2f}% {status}")
    print(f"  Lines Covered: {total['covered_lines']} / {total['num_statements']}")
    print(f"  Missing Lines: {total['missing_lines']}")
    print()

    # Show top 10 files with lowest coverage
    files = []
    for filename, filedata in data['files'].items():
        if filedata['summary']['num_statements'] > 0:
            files.append((
                filename,
                filedata['summary']['percent_covered'],
                filedata['summary']['missing_lines']
            ))

    files.sort(key=lambda x: x[1])  # Sort by coverage percentage

    if files:
        print("  Files Needing Most Coverage (bottom 10):")
        print("  " + "-" * 66)
        for filename, coverage, missing in files[:10]:
            # Shorten filename if too long
            short_name = filename[-60:] if len(filename) > 60 else filename
            print(f"    {coverage:5.1f}%  (-{missing:3d} lines)  {short_name}")

except FileNotFoundError:
    print("  ℹ️  Coverage JSON file not found")
except Exception as e:
    print(f"  ⚠️  Error parsing coverage data: {e}")
PYTHON_SCRIPT

    echo "----------------------------------------------------------------------"
fi

echo ""
echo "Next steps:"
echo "  1. Review HTML report for detailed coverage"
echo "  2. Identify critical files with low coverage"
echo "  3. Add tests for uncovered code paths"
echo ""
