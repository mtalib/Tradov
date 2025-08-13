(.venv) adam@Captova:~/Projects/Spyder$ #!/bin/bash
# ============================================================================
# Spyder S-Series Migration Script
# Purpose: Reorganize S-Series modules to eliminate duplication
# Author: Mohamed Talib
# Date: 2025-01-31
# ============================================================================

echo "======================================================================"
echo "SPYDER S-SERIES MIGRATION SCRIPT"
echo "======================================================================"
echo ""

# Create backup first
echo "📦 Creating backup of current state..."
cp -r SpyderS_Signals SpyderS_Signals_backup_$(date +%Y%m%d_%H%M%S)
echo "✅ Backup created"
echo ""

# ============================================================================
# PHASE 1: Move Test/Demo Modules to T-Series
# ============================================================================
echo "📋 Phase 1: Moving test/demo modules to T-Series..."

echo "✅ Migration script completed successfully!"ports if needed"=========="r"'
======================================================================
SPYDER S-SERIES MIGRATION SCRIPT
======================================================================

📦 Creating backup of current state...
✅ Backup created

📋 Phase 1: Moving test/demo modules to T-Series...
  ✅ Moved S02_DIXDemo to T20_DIXDemo
  ✅ Moved S04_DIXQuickStart to T21_DIXQuickStart

📋 Phase 2: Deleting redundant GUI modules...
  ✅ Deleted S03_DIXVisualizer (redundant with dashboard)
  ✅ Deleted S08_BlackSwanGUI (redundant with dashboard)

📋 Phase 3: Renumbering existing S-Series modules...
  ✅ Renamed S05_DIXScheduler to S02_DIXScheduler
  ✅ Renamed S11_BlackSwanScheduler to S04_BlackSwanScheduler

📋 Phase 4: Moving modules from other series...
  ✅ Copied N09_GammaExposure to S05_GEXDEXCalculator
  📌 Note: Original N09 kept for reference - delete manually after verification
  ✅ Copied C18_SKEWCalculator to S06_SKEWCalculator
  📌 Note: Original C18 kept for reference - delete manually after verification

📋 Phase 5: Deleting duplicate modules...
  ✅ Deleted C15_GEXDEXCalculator (duplicate of N09)
  ✅ Deleted B18_CustomMetricsClient (replaced by S07)

📋 Phase 6: Handling BlackSwanDataCollector...
  ✅ Backed up S06_BlackSwanDataCollector (already merged into S03)

📋 Phase 7: Creating import update script...
  ✅ Created update_imports.py script

======================================================================
MIGRATION COMPLETE!
======================================================================

📋 Next Steps:
  1. Run: python update_imports.py
  2. Verify all modules are working correctly
  3. Delete original N09 and C18 after verification
  4. Update S07_CustomMetricsOrchestrator imports if needed

📁 Final S-Series Structure:
  S01_DIXCalculator.py
  S02_DIXScheduler.py
  S03_BlackSwanIndicator.py
  S04_BlackSwanScheduler.py
  S05_GEXDEXCalculator.py
  S06_SKEWCalculator.py
  S07_CustomMetricsOrchestrator.py

✅ Migration script completed successfully!
(.venv) adam@Captova:~/Projects/Spyder$ 


