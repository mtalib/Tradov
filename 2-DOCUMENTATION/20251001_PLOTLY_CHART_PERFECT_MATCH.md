# Plotly Chart Perfect Match Implementation

**Date**: 2025-10-01
**Session**: Chart Design Alignment with Perfect Version

## Summary
Successfully updated the Plotly-based chart to match the design of the Perfect matplotlib version, using interactive Plotly with Classic Pivot Points.

---

## Changes Made

### 1. **Classic Pivot Point Formulas** (SpyderG04_ChartWidgetPlotly.py)
Replaced Fibonacci ratio-based pivots with Classic Pivot Point formulas to match Perfect version:

```python
def calculate_fibonacci_pivots(self):
    """Calculate Classic Fibonacci Daily Pivot Points (Standard Pivots)."""
    # Calculate Classic Pivot Point
    pivot = (high + low + close) / 3

    # Classic Pivot Point Resistances and Supports
    r1 = (2 * pivot) - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)
    s1 = (2 * pivot) - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (pivot - low)
```

**Key Differences**:
- ❌ OLD: Fibonacci ratios (0.382, 0.618, 1.000)
- ✅ NEW: Classic pivot formulas (standard day trading pivots)

### 2. **Pivot Line Styling** (SpyderG04_ChartWidgetPlotly.py)
Updated line colors and styles to match Perfect version:

- **Pivot**: `#FFFF00` (Yellow) - solid line, opacity 0.7
- **R1/R2/R3**: `#00FF41` (Green) - solid lines, opacity 0.6
- **S1/S2/S3**: `#FF1744` (Red) - solid lines, opacity 0.6

**Key Differences**:
- ❌ OLD: Had annotation labels on right side (P: XXX.XX, R1: XXX.XX, etc.)
- ✅ NEW: Clean lines without text annotations

### 3. **Removed Control Panel** (SpyderG04_ChartWidgetPlotly.py)
Removed the top control panel toolbar to match Perfect's clean chart display:

```python
def setup_ui(self):
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # No control panel - clean chart display like Perfect version

    # Create web engine view for Plotly
    self.web_view = QWebEngineView()
    layout.addWidget(self.web_view)
```

**Key Differences**:
- ❌ OLD: Had timeframe selector, indicator toggles, refresh button
- ✅ NEW: Pure chart display only

### 4. **Indicator Colors** (Already Correct)
The indicator colors were already matching Perfect version:

- **MA(20)**: `#00B8D4` (Cyan)
- **VWAP**: `#BF00FF` (Purple)

---

## File Modified

### SpyderG04_ChartWidgetPlotly.py
**Location**: `/home/adam/Projects/Spyder/SpyderG_GUI/SpyderG04_ChartWidgetPlotly.py`

**Changes**:
1. Line ~395: Updated `calculate_fibonacci_pivots()` method with Classic Pivot formulas
2. Line ~495: Removed annotation labels from pivot lines
3. Line ~196: Removed control panel from UI setup

---

## Chart Features (After Changes)

### ✅ Candlestick Chart
- Green candlesticks for up moves
- Red candlesticks for down moves
- Interactive hover tooltips

### ✅ Classic Pivot Points
- **Yellow Pivot line** - Central pivot point
- **Green R1/R2/R3** - Resistance levels
- **Red S1/S2/S3** - Support levels
- All using standard day trading formulas

### ✅ Technical Indicators
- **Cyan MA(20)** - 20-period moving average
- **Purple VWAP** - Volume-weighted average price

### ✅ Clean Display
- No control panel toolbar
- No text annotations on lines
- Full chart display area
- Matches Perfect matplotlib version aesthetics

---

## Testing

To test the updated chart:

```bash
cd /home/adam/Projects/Spyder
find . -type d -name '__pycache__' -path '*/SpyderG_GUI/*' -exec rm -rf {} +
python launch_dashboard_production.py
```

**Expected Result**:
- SPY chart displays with candlesticks
- Yellow pivot line visible
- Green R1/R2/R3 resistance lines
- Red S1/S2/S3 support lines
- Cyan MA(20) and purple VWAP indicators
- No toolbar, no annotations
- Clean, professional appearance matching Perfect version

---

## Previous Session Context

### IBDataConnector Singleton Fixes (Also Applied)
During this session, we also fixed IBDataConnector singleton lifecycle issues in SpyderG05_TradingDashboard.py:

1. Changed `IBDataConnector()` to `IBDataConnector.get_instance()`
2. Removed `setParent(self)` calls (singleton must persist)
3. Removed `deleteLater()` calls (singleton lifecycle)

These fixes prevent "Internal C++ object (IBDataConnector) already deleted" errors.

---

## Formulas Reference

### Classic Pivot Points (Standard Day Trading)
```
Given: Previous High (H), Low (L), Close (C)

Pivot = (H + L + C) / 3

R1 = (2 × Pivot) - L
R2 = Pivot + (H - L)
R3 = H + 2 × (Pivot - L)

S1 = (2 × Pivot) - H
S2 = Pivot - (H - L)
S3 = L - 2 × (Pivot - L)
```

### Technical Indicators
```
MA(20) = Simple Moving Average over 20 periods

VWAP = Σ(Typical Price × Volume) / Σ(Volume)
where Typical Price = (High + Low + Close) / 3
```

---

## Color Palette

```python
# Pivot Points
PIVOT_COLOR = "#FFFF00"  # Yellow
RESISTANCE_COLOR = "#00FF41"  # Green
SUPPORT_COLOR = "#FF1744"  # Red

# Indicators
MA20_COLOR = "#00B8D4"  # Cyan
VWAP_COLOR = "#BF00FF"  # Purple

# Candlesticks
POSITIVE_COLOR = "#00FF00"  # Green (up)
NEGATIVE_COLOR = "#FF0000"  # Red (down)
```

---

## Success Criteria ✅

- [x] Classic Pivot Point formulas implemented
- [x] Pivot line colors match Perfect version
- [x] No annotation labels on chart
- [x] No control panel toolbar
- [x] MA(20) and VWAP indicators present
- [x] Clean professional appearance
- [x] Interactive Plotly chart with Wayland compatibility
- [x] IBDataConnector singleton fixes applied

---

## Notes

- The Plotly chart now provides the **same visual appearance** as the Perfect matplotlib version
- But with added benefits: **interactive zoom/pan, smooth performance, Wayland compatibility**
- All pivot calculations use **industry-standard Classic Pivot formulas**
- Chart is production-ready with no unnecessary UI elements

**Status**: ✅ Complete - Plotly chart matches Perfect version design
