#!/usr/bin/env python3
"""Quick test to verify chart HTML generation"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("🧪 Testing Chart HTML Generation")
print("=" * 60)

# Test 1: Check Plotly availability
print("\n1. Checking Plotly...")
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    print("✅ Plotly is available")
except ImportError as e:
    print(f"❌ Plotly not available: {e}")
    sys.exit(1)

# Test 2: Generate chart data
print("\n2. Generating chart data...")
dates = pd.date_range(start="2025-09-20", end="2025-09-29", freq="H")[:100]
prices = 580 + np.cumsum(np.random.randn(100) * 0.5)
print(f"✅ Generated {len(prices)} data points")
print(f"   Price range: ${min(prices):.2f} - ${max(prices):.2f}")

# Test 3: Create Plotly figure
print("\n3. Creating Plotly figure...")
fig = make_subplots(
    rows=1,
    cols=1,
    subplot_titles=["SPY - Test Chart"],
)

fig.add_trace(
    go.Scatter(
        x=dates,
        y=prices,
        mode="lines",
        name="SPY Price",
        line=dict(color="#00E676", width=2),
    )
)

fig.update_layout(
    title="SPY Test Chart",
    paper_bgcolor="rgba(45, 45, 45, 1)",
    plot_bgcolor="rgba(30, 30, 30, 1)",
    font=dict(color="#FFFFFF"),
)

print("✅ Plotly figure created")

# Test 4: Generate HTML
print("\n4. Generating HTML...")
html_content = fig.to_html(include_plotlyjs=True, div_id="plotly-chart")
html_size = len(html_content)
print(f"✅ HTML generated: {html_size} characters ({html_size/1024:.1f} KB)")

# Test 5: Save to file for inspection
output_file = project_root / "test_chart.html"
with open(output_file, "w") as f:
    f.write(html_content)
print(f"✅ Chart saved to: {output_file}")
print(f"   You can open it in a browser to verify it works")

# Test 6: Check if HTML contains expected content
print("\n5. Validating HTML content...")
checks = [
    ("Plotly.js library", "plotly" in html_content.lower()),
    ("Chart data", "data" in html_content.lower()),
    ("Layout config", "layout" in html_content.lower()),
    ("Div container", "plotly-chart" in html_content),
]

all_passed = True
for check_name, result in checks:
    status = "✅" if result else "❌"
    print(f"   {status} {check_name}")
    if not result:
        all_passed = False

print("\n" + "=" * 60)
if all_passed:
    print("✅ All tests PASSED - Chart generation is working!")
    print(f"📄 Open {output_file} in a browser to see the chart")
else:
    print("❌ Some tests FAILED - Chart generation has issues")

print("\nNext step: Check if QtWebEngine can display this HTML")
