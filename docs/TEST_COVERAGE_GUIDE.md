# Test Coverage Guide for Spyder Trading System

## Quick Start

### Measure Current Coverage

```bash
# Run all tests with coverage analysis
bash SpyderQ_Scripts/run_coverage.sh

# Or manually:
pytest SpyderT_Testing/ --cov=. --cov-report=html
```

### View Results

```bash
# Open HTML report in browser
xdg-open coverage_html/index.html

# Or view in terminal
cat coverage_output.txt
```

---

## Understanding Coverage Metrics

### Coverage Targets

| Coverage Level | Status | Action |
|----------------|--------|--------|
| 70%+ | ✅ Good | Maintain coverage |
| 50-70% | ⚠️ Fair | Add tests for critical paths |
| < 50% | ❌ Poor | Urgent testing needed |

### What Gets Measured

- **Statement Coverage**: % of code lines executed
- **Branch Coverage**: % of if/else paths taken
- **Function Coverage**: % of functions called
- **Missing Lines**: Specific lines not covered

---

## Coverage Reports

### 1. HTML Report (Detailed)

**Location**: `coverage_html/index.html`

**Features**:
- Visual coverage by file
- Line-by-line highlighting
- Branch coverage details
- Click to see source code

**Best for**: Deep analysis, finding specific gaps

### 2. Terminal Report (Quick)

**Location**: Console output / `coverage_output.txt`

**Features**:
- Overall percentage
- Per-file breakdown
- Missing line numbers

**Best for**: Quick checks, CI/CD pipelines

### 3. JSON Report (Programmatic)

**Location**: `coverage.json`

**Features**:
- Machine-readable format
- Detailed statistics
- Integration with tools

**Best for**: Automated analysis, dashboards

---

## Interpreting Results

### Example Output

```
Name                                   Stmts   Miss  Cover   Missing
--------------------------------------------------------------------
SpyderB_Broker/SpyderB40_TradierClient.py  663     45    93%   123-145, 234
SpyderE_Risk/SpyderE01_RiskManager.py      830    421    49%   156-234, 456-789
SpyderC_MarketData/SpyderC25_PolygonDataHandler.py  634    102    84%   45-67
--------------------------------------------------------------------
TOTAL                                   318430  89234    72%
```

**Reading**:
- **Stmts**: Total executable lines
- **Miss**: Lines not executed in tests
- **Cover**: Percentage covered
- **Missing**: Specific line numbers not covered

---

## Prioritizing Testing Efforts

### Critical Modules (Test First)

Based on analysis, prioritize:

1. **Broker Integration** (`SpyderB_Broker/`)
   - Order execution
   - Position tracking
   - Account management

2. **Risk Management** (`SpyderE_Risk/`)
   - Position sizing
   - Loss protection
   - Risk calculations

3. **Market Data** (`SpyderC_MarketData/`)
   - Data validation
   - WebSocket handling
   - Feed processing

### What to Skip

Lower priority for coverage:
- GUI code (hard to test, less critical)
- Utility scripts (`SpyderQ_Scripts/`)
- Test files themselves
- Configuration files

---

## Improving Coverage

### Strategy 1: Add Unit Tests

**For**: Individual functions and classes

```python
# SpyderT_Testing/SpyderT_NewModule_Test.py
import pytest
from SpyderE_Risk.SpyderE01_RiskManager import RiskManager

def test_position_size_calculation():
    """Test position size calculation logic"""
    manager = RiskManager(config)
    size = manager.calculate_position_size(account_value=100000, risk_pct=0.02)
    assert size == 2000
```

### Strategy 2: Add Integration Tests

**For**: Component interactions

```python
def test_order_submission_flow():
    """Test complete order submission workflow"""
    # Setup
    client = TradierClient()
    risk_manager = RiskManager()

    # Execute
    order = client.submit_order("SPY", 10, "buy")

    # Verify
    assert risk_manager.validate_order(order)
    assert order.status == "submitted"
```

### Strategy 3: Add Error Path Tests

**For**: Exception handling

```python
def test_api_failure_handling():
    """Test behavior when API call fails"""
    client = TradierClient()

    with pytest.raises(TradierAPIError):
        client.submit_order_with_invalid_symbol("INVALID")
```

---

## Configuration

### .coveragerc (Optional)

Create `.coveragerc` in project root:

```ini
[run]
source = .
omit =
    */tests/*
    */SpyderT_Testing/*
    */SpyderQ_Scripts/*
    */__init__.py
    */conftest.py

[report]
precision = 2
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = coverage_html
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Tests with Coverage
  run: |
    pytest SpyderT_Testing/ \
      --cov=. \
      --cov-report=xml \
      --cov-fail-under=70

- name: Upload Coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

### Fail Build if Coverage Drops

```bash
# In CI pipeline
pytest --cov --cov-fail-under=70
```

---

## Common Issues

### Issue: "No module named pytest_cov"

**Solution**:
```bash
pip install pytest-cov
```

### Issue: Coverage shows 0%

**Causes**:
- Tests not importing modules correctly
- Source files not in Python path
- .coveragerc excluding too much

**Solution**: Check imports and paths

### Issue: Some files not appearing

**Cause**: Files never imported by tests

**Solution**: Add tests that import those files

---

## Best Practices

### Do:
✅ Focus on critical business logic
✅ Test edge cases and error paths
✅ Maintain coverage as you add features
✅ Review coverage in code reviews
✅ Set coverage targets (e.g., 70% minimum)

### Don't:
❌ Chase 100% coverage (diminishing returns)
❌ Test trivial getters/setters
❌ Skip error handling tests
❌ Ignore coverage drops

---

## Coverage Goals by Module

| Module | Target | Priority |
|--------|--------|----------|
| SpyderB_Broker | 80%+ | Critical |
| SpyderE_Risk | 75%+ | Critical |
| SpyderC_MarketData | 75%+ | Critical |
| SpyderD_Strategies | 70%+ | High |
| SpyderF_Analysis | 65%+ | High |
| SpyderG_GUI | 30%+ | Low |
| SpyderU_Utilities | 60%+ | Medium |

---

## Useful Commands

```bash
# Quick coverage check
pytest --cov --cov-report=term-missing

# Generate HTML report
pytest --cov --cov-report=html

# Coverage for specific module
pytest SpyderT_Testing/SpyderT40* --cov=SpyderB_Broker

# Coverage with verbose test output
pytest --cov -v

# Show only files with < 70% coverage
pytest --cov --cov-report=term-missing:skip-covered

# Fail if coverage below threshold
pytest --cov --cov-fail-under=70
```

---

## Next Steps After Measuring

1. **Identify Gaps**: Review HTML report, find uncovered critical code
2. **Prioritize**: Focus on high-risk, low-coverage modules
3. **Write Tests**: Add unit/integration tests for gaps
4. **Track Progress**: Re-run coverage after adding tests
5. **Set Targets**: Establish minimum coverage for new code

---

## Resources

- **pytest-cov docs**: https://pytest-cov.readthedocs.io/
- **Coverage.py docs**: https://coverage.readthedocs.io/
- **Testing guide**: `docs/TESTING.md` (if exists)

---

**Last Updated**: 2025-11-24
**Version**: 1.0
**Status**: Ready for Use ✅
