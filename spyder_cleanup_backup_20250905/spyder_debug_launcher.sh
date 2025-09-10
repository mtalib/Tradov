#!/bin/bash
# ==============================================================================
# SPYDER DEBUG AND TEST LAUNCHER
# Comprehensive testing and debugging workflow for Spyder system
# ==============================================================================

SPYDER_HOME="/home/adam/Projects/Spyder"
VENV_PATH="$SPYDER_HOME/.venv"
LOG_DIR="$SPYDER_HOME/logs/debug"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log_and_print() {
    local level=$1
    local message=$2
    local color=${3:-$NC}
    
    echo -e "${color}[$level] $message${NC}"
    echo "[$level $(date '+%Y-%m-%d %H:%M:%S')] $message" >> "$LOG_DIR/debug_session_$TIMESTAMP.log"
}

# Header
print_header() {
    clear
    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                      SPYDER SYSTEM DEBUG LAUNCHER                           ║"
    echo "║                    Comprehensive Testing & Debugging                        ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

# Check environment
check_environment() {
    log_and_print "INFO" "Checking environment setup..." $BLUE
    
    # Check if in Spyder directory
    if [ ! -d "$SPYDER_HOME" ]; then
        log_and_print "ERROR" "Spyder directory not found: $SPYDER_HOME" $RED
        echo "Please update SPYDER_HOME path in this script"
        exit 1
    fi
    
    cd "$SPYDER_HOME" || {
        log_and_print "ERROR" "Cannot change to Spyder directory" $RED
        exit 1
    }
    
    # Check virtual environment
    if [ -f "$VENV_PATH/bin/activate" ]; then
        log_and_print "INFO" "Activating virtual environment" $GREEN
        source "$VENV_PATH/bin/activate"
    else
        log_and_print "WARN" "No virtual environment found - using system Python" $YELLOW
    fi
    
    # Set environment variables for GUI
    export GDK_BACKEND=wayland,x11
    export QT_QPA_PLATFORM=wayland
    export DISPLAY=:0
    export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}
    export SPYDER_NO_AUTOMATION=1
    
    log_and_print "INFO" "Environment setup complete" $GREEN
}

# Quick fix test
run_quick_fix() {
    log_and_print "INFO" "Running quick fix analysis..." $BLUE
    echo ""
    
    if [ -f "SpyderT_Testing/temp_SpyderQuickFix.py" ]; then
        python SpyderT_Testing/temp_SpyderQuickFix.py 2>&1 | tee -a "$LOG_DIR/quickfix_$TIMESTAMP.log"
        local exit_code=${PIPESTATUS[0]}
        
        if [ $exit_code -eq 0 ]; then
            log_and_print "SUCCESS" "Quick fix analysis completed successfully" $GREEN
            return 0
        else
            log_and_print "ERROR" "Quick fix analysis found critical issues" $RED
            return 1
        fi
    else
        log_and_print "ERROR" "Quick fix script not found - please create temp_SpyderQuickFix.py first" $RED
        return 1
    fi
}

# Full diagnostic test
run_full_diagnostic() {
    log_and_print "INFO" "Running comprehensive diagnostic..." $BLUE
    echo ""
    
    if [ -f "SpyderT_Testing/SpyderT99_SystemDiagnostic.py" ]; then
        python SpyderT_Testing/SpyderT99_SystemDiagnostic.py 2>&1 | tee -a "$LOG_DIR/diagnostic_$TIMESTAMP.log"
        local exit_code=${PIPESTATUS[0]}
        
        if [ $exit_code -eq 0 ]; then
            log_and_print "SUCCESS" "Full diagnostic completed - system ready!" $GREEN
            return 0
        else
            log_and_print "ERROR" "Diagnostic found issues that need fixing" $RED
            return 1
        fi
    else
        log_and_print "ERROR" "Diagnostic script not found - please create SpyderT99_SystemDiagnostic.py first" $RED
        return 1
    fi
}

# Module-specific tests
run_module_tests() {
    local test_type=$1
    log_and_print "INFO" "Running $test_type module tests..." $BLUE
    
    case $test_type in
        "eventmanager")
            python -c "
import sys
sys.path.insert(0, '.')
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    em = EventManager(persist_events=False)
    if hasattr(em, 'start') and em.start():
        print('✅ EventManager: Started successfully')
        if em.stop():
            print('✅ EventManager: Stopped successfully')
        else:
            print('⚠️ EventManager: Stop had issues')
    else:
        print('❌ EventManager: Failed to start')
except Exception as e:
    print(f'❌ EventManager: {e}')
" 2>&1 | tee -a "$LOG_DIR/eventmanager_test_$TIMESTAMP.log"
            ;;
            
        "gui")
            python -c "
import sys
sys.path.insert(0, '.')
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    print('✅ PyQt6: Available')
    
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    print('✅ TradingDashboard: Import successful')
    
    dashboard = SpyderTradingDashboard()
    print('✅ TradingDashboard: Creation successful')
    
except Exception as e:
    print(f'❌ GUI Test: {e}')
" 2>&1 | tee -a "$LOG_DIR/gui_test_$TIMESTAMP.log"
            ;;
            
        "database")
            python -c "
import sys
sys.path.insert(0, '.')
try:
    from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
    from pathlib import Path
    
    db_path = Path.home() / '.spyder' / 'data' / 'test.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    dal = DataAccessLayer(str(db_path))
    print('✅ Database: Connection successful')
    
except Exception as e:
    print(f'❌ Database Test: {e}')
" 2>&1 | tee -a "$LOG_DIR/database_test_$TIMESTAMP.log"
            ;;
    esac
}

# Try launching with different methods
test_launch_methods() {
    log_and_print "INFO" "Testing different launch methods..." $BLUE
    
    echo "1. Testing direct Python launch..."
    timeout 10s python SpyderA_Core/SpyderA01_Main.py --test 2>&1 | head -20 | tee -a "$LOG_DIR/launch_test1_$TIMESTAMP.log"
    echo ""
    
    echo "2. Testing GUI-only mode..."
    timeout 10s python -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG01_MainWindow import MainWindow

app = QApplication([])
window = MainWindow()
print('GUI window created successfully')
# Don't show - just test creation
app.quit()
" 2>&1 | tee -a "$LOG_DIR/launch_test2_$TIMESTAMP.log"
    echo ""
    
    echo "3. Testing minimal system startup..."
    timeout 15s python -c "
import sys
sys.path.insert(0, '.')

print('Testing minimal system startup...')

# Test EventManager
from SpyderA_Core.SpyderA05_EventManager import EventManager
em = EventManager(persist_events=False)
print('✓ EventManager created')

if hasattr(em, 'start') and em.start():
    print('✓ EventManager started')
    
    # Test Configuration
    from SpyderA_Core.SpyderA03_Configuration import ConfigManager
    config = ConfigManager()
    print('✓ Configuration loaded')
    
    # Test Database
    from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
    from pathlib import Path
    db_path = Path.home() / '.spyder' / 'data' / 'test.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    dal = DataAccessLayer(str(db_path))
    print('✓ Database connected')
    
    em.stop()
    print('✓ System shutdown successful')
    print('🎉 Minimal startup test PASSED')
else:
    print('❌ EventManager failed to start')
" 2>&1 | tee -a "$LOG_DIR/launch_test3_$TIMESTAMP.log"
}

# Create missing files with emergency stubs
create_emergency_files() {
    log_and_print "INFO" "Creating emergency stub files..." $YELLOW
    
    # Create SpyderT_Testing directory if it doesn't exist
    mkdir -p SpyderT_Testing
    
    # Create emergency stub for missing modules
    python -c "
import sys
sys.path.insert(0, '.')
try:
    from SpyderT_Testing.temp_SpyderQuickFix import QuickFixTester
    fixer = QuickFixTester()
    fixer.create_emergency_stubs()
    print('✅ Emergency stubs created')
except Exception as e:
    print(f'⚠️ Could not create stubs: {e}')
" 2>&1 | tee -a "$LOG_DIR/emergency_stubs_$TIMESTAMP.log"
}

# Interactive menu
show_menu() {
    echo ""
    echo -e "${BOLD}${WHITE}DEBUGGING OPTIONS:${NC}"
    echo -e "${CYAN}1)${NC} Quick Fix Analysis (Targeted error resolution)"
    echo -e "${CYAN}2)${NC} Full System Diagnostic (Comprehensive testing)"
    echo -e "${CYAN}3)${NC} Test EventManager Only"
    echo -e "${CYAN}4)${NC} Test GUI Components Only"  
    echo -e "${CYAN}5)${NC} Test Database Only"
    echo -e "${CYAN}6)${NC} Test Launch Methods"
    echo -e "${CYAN}7)${NC} Create Emergency Stubs"
    echo -e "${CYAN}8)${NC} Try Normal Launch (Original script)"
    echo -e "${CYAN}9)${NC} View Recent Logs"
    echo -e "${CYAN}0)${NC} Exit"
    echo ""
}

# View logs
view_logs() {
    echo -e "${BLUE}Recent log files:${NC}"
    ls -la "$LOG_DIR"/*.log 2>/dev/null | tail -5
    echo ""
    
    echo "Which log would you like to view? (Enter filename or 'latest' for most recent):"
    read -r log_choice
    
    if [ "$log_choice" = "latest" ]; then
        latest_log=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
        if [ -n "$latest_log" ]; then
            echo -e "${GREEN}Showing latest log: $latest_log${NC}"
            tail -50 "$latest_log"
        else
            log_and_print "WARN" "No log files found" $YELLOW
        fi
    elif [ -f "$LOG_DIR/$log_choice" ]; then
        echo -e "${GREEN}Showing log: $log_choice${NC}"
        tail -50 "$LOG_DIR/$log_choice"
    else
        log_and_print "ERROR" "Log file not found: $log_choice" $RED
    fi
}

# Try original launch
try_original_launch() {
    log_and_print "INFO" "Attempting original launch method..." $BLUE
    
    if [ -f "launch_spyder_wayland.sh" ]; then
        chmod +x launch_spyder_wayland.sh
        ./launch_spyder_wayland.sh 2>&1 | tee -a "$LOG_DIR/original_launch_$TIMESTAMP.log"
    else
        python SpyderA_Core/SpyderA01_Main.py 2>&1 | tee -a "$LOG_DIR/direct_launch_$TIMESTAMP.log"
    fi
}

# Main execution
main() {
    print_header
    check_environment
    
    while true; do
        show_menu
        echo -n "Select option (1-9, 0 to exit): "
        read -r choice
        
        case $choice in
            1)
                echo ""
                run_quick_fix
                echo ""
                read -p "Press Enter to continue..."
                ;;
            2)
                echo ""
                run_full_diagnostic
                echo ""
                read -p "Press Enter to continue..."
                ;;
            3)
                echo ""
                run_module_tests "eventmanager"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            4)
                echo ""
                run_module_tests "gui"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            5)
                echo ""
                run_module_tests "database"
                echo ""
                read -p "Press Enter to continue..."
                ;;
            6)
                echo ""
                test_launch_methods
                echo ""
                read -p "Press Enter to continue..."
                ;;
            7)
                echo ""
                create_emergency_files
                echo ""
                read -p "Press Enter to continue..."
                ;;
            8)
                echo ""
                try_original_launch
                echo ""
                read -p "Press Enter to continue..."
                ;;
            9)
                echo ""
                view_logs
                echo ""
                read -p "Press Enter to continue..."
                ;;
            0)
                log_and_print "INFO" "Debug session ended" $GREEN
                echo "Debug logs saved in: $LOG_DIR/"
                exit 0
                ;;
            *)
                log_and_print "ERROR" "Invalid option: $choice" $RED
                ;;
        esac
        
        clear
        print_header
    done
}

# Handle command line arguments
if [ $# -gt 0 ]; then
    case $1 in
        "--quick")
            print_header
            check_environment
            run_quick_fix
            ;;
        "--diagnostic")
            print_header
            check_environment
            run_full_diagnostic
            ;;
        "--test-launch")
            print_header
            check_environment
            test_launch_methods
            ;;
        "--create-stubs")
            print_header
            check_environment
            create_emergency_files
            ;;
        "--help")
            print_header
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  --quick         Run quick fix analysis only"
            echo "  --diagnostic    Run full diagnostic only"
            echo "  --test-launch   Test different launch methods"
            echo "  --create-stubs  Create emergency stub files"
            echo "  --help          Show this help message"
            echo ""
            echo "Run without arguments for interactive mode"
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
else
    # Interactive mode
    main
fi