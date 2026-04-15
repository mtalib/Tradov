# SpyderG04 Module Renumbering Strategy

## Overview
The SpyderG04 modules need to be renumbered to avoid conflicts with the new modular structure. Currently, there are 4 modules with the SpyderG04 prefix that need to be renumbered to unique identifiers.

## Current SpyderG04 Modules
1. SpyderG04_ChartWidget.py
2. SpyderG04_ChartWidgetPlotly.py
3. SpyderG04_PlotlyDataBridge.py
4. SpyderG04_PlotlyTemplates.py

## Renumbering Strategy
Based on our existing numbering scheme, the following renumbering is proposed:

| Current Module | New Module | Purpose |
|---------------|------------|---------|
| SpyderG04_ChartWidget.py | SpyderG28_ChartWidget.py | Basic chart widget implementation |
| SpyderG04_ChartWidgetPlotly.py | SpyderG29_ChartWidgetPlotly.py | Plotly-based chart widget |
| SpyderG04_PlotlyDataBridge.py | SpyderG30_PlotlyDataBridge.py | Data bridge for Plotly charts |
| SpyderG04_PlotlyTemplates.py | SpyderG31_PlotlyTemplates.py | Templates for Plotly charts |

## Implementation Steps

### 1. Create Backup Files
Before renaming, create backup files of each module:
- SpyderG04_ChartWidget.py.backup
- SpyderG04_ChartWidgetPlotly.py.backup
- SpyderG04_PlotlyDataBridge.py.backup
- SpyderG04_PlotlyTemplates.py.backup

### 2. Rename Files
Rename the files with their new numbers:
- SpyderG04_ChartWidget.py → SpyderG28_ChartWidget.py
- SpyderG04_ChartWidgetPlotly.py → SpyderG29_ChartWidgetPlotly.py
- SpyderG04_PlotlyDataBridge.py → SpyderG30_PlotlyDataBridge.py
- SpyderG04_PlotlyTemplates.py → SpyderG31_PlotlyTemplates.py

### 3. Update Module Headers
Update the module headers in each file to reflect the new module numbers:
- Update series and module names
- Update last updated timestamp
- Update module descriptions if needed

### 4. Update Import Statements
Find and update all import statements that reference the old module names:
- Search for "from SpyderG_GUI.SpyderG04_" in all files
- Replace with the new module names
- Update any relative imports within the modules

### 5. Update Documentation
Update any documentation that references the old module names:
- README files
- Code comments
- Docstrings
- External documentation

### 6. Test Functionality
Test that all functionality is preserved after renumbering:
- Run the main dashboard
- Test chart functionality
- Verify Plotly integration
- Check data bridge functionality
- Validate template usage

## Files to Update

### Direct Renames
1. SpyderG04_ChartWidget.py → SpyderG28_ChartWidget.py
2. SpyderG04_ChartWidgetPlotly.py → SpyderG29_ChartWidgetPlotly.py
3. SpyderG04_PlotlyDataBridge.py → SpyderG30_PlotlyDataBridge.py
4. SpyderG04_PlotlyTemplates.py → SpyderG31_PlotlyTemplates.py

### Import Updates
The following files may need import updates:
- SpyderG05_TradingDashboard.py
- Any other files that import from the SpyderG04 modules

## Benefits of Renumbering
1. **Eliminates Confusion**: Removes duplicate module numbers
2. **Improves Organization**: Groups related chart functionality
3. **Enhances Maintainability**: Makes it easier to identify module purposes
4. **Prevents Conflicts**: Avoids potential naming conflicts in the future

## Risk Mitigation
1. **Backup Creation**: Create backups before making changes
2. **Incremental Updates**: Update one module at a time
3. **Testing**: Test each module individually after renumbering
4. **Documentation**: Keep detailed records of all changes made

## Timeline
1. Day 1: Create backups and rename files
2. Day 1: Update module headers
3. Day 2: Update import statements
4. Day 2: Update documentation
5. Day 3: Test functionality and fix any issues

## Conclusion
This renumbering strategy will eliminate the duplicate SpyderG04 module numbers while preserving all functionality. The new numbering scheme follows our established pattern and makes the module purposes more clear.