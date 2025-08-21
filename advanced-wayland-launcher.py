#!/usr/bin/env python3
"""
Advanced Wayland-compatible Spyder Dashboard Launcher
Handles PyAutoGUI/mouseinfo import issues
"""
import os
import sys

def setup_wayland_environment():
    """Set up Wayland environment and mock problematic imports"""
    
    # Set Wayland environment variables
    os.environ['XDG_SESSION_TYPE'] = 'wayland'
    os.environ['QT_QPA_PLATFORM'] = 'wayland'  
    os.environ['GDK_BACKEND'] = 'wayland'
    os.environ['QT_WAYLAND_DECORATION'] = 'adwaita'
    
    # Temporarily set DISPLAY to a dummy value for imports
    # This prevents the KeyError during mouseinfo import
    os.environ['DISPLAY'] = ':99'  # Dummy display
    
    # Disable PyAutoGUI features that won't work on Wayland
    os.environ['PYAUTOGUI_DISABLE_FAIL_SAFE'] = '1'
    
    print("🚀 Starting Spyder Dashboard (Advanced Wayland Mode)")
    print(f"🖥️ Session Type: {os.environ.get('XDG_SESSION_TYPE')}")
    print(f"🎨 QT Platform: {os.environ.get('QT_QPA_PLATFORM')}")

def mock_problematic_modules():
    """Mock problematic modules before they're imported"""
    
    # Add project to Python path first
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    # Mock the mouseinfo module to prevent X11 connection attempts
    import types
    
    class MockMouseInfo:
        def __init__(self):
            pass
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    
    # Install the mock before any real imports happen
    sys.modules['mouseinfo'] = MockMouseInfo()
    
    # Also mock the Display class if needed
    class MockDisplay:
        def __init__(self, *args, **kwargs):
            pass
        def __getattr__(self, name):
            return lambda *args, **kwargs: None
    
    # Create a mock Xlib module structure
    import types
    mock_xlib = types.ModuleType('Xlib')
    mock_display_module = types.ModuleType('Xlib.display')
    mock_display_module.Display = MockDisplay
    mock_xlib.display = mock_display_module
    sys.modules['Xlib'] = mock_xlib
    sys.modules['Xlib.display'] = mock_display_module

def main():
    """Main launcher function"""
    
    # Set up environment first
    setup_wayland_environment()
    
    # Mock problematic modules
    mock_problematic_modules()
    
    try:
        # Now import and run the dashboard
        from SpyderR_Runtime.SpyderR05_LiveDashboard import main as dashboard_main
        
        # Remove the dummy DISPLAY after imports are done
        if os.environ.get('DISPLAY') == ':99':
            del os.environ['DISPLAY']
        
        # Run the dashboard
        return dashboard_main()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Trying fallback execution...")
        
        # Fallback: execute directly
        dashboard_path = os.path.join(
            os.path.dirname(__file__), 
            'SpyderR_Runtime', 
            'SpyderR05_LiveDashboard.py'
        )
        
        if os.path.exists(dashboard_path):
            # Remove dummy DISPLAY before execution
            if os.environ.get('DISPLAY') == ':99':
                del os.environ['DISPLAY']
                
            with open(dashboard_path, 'r') as f:
                exec(f.read(), {'__name__': '__main__'})
        else:
            print(f"❌ Dashboard file not found: {dashboard_path}")
            return 1
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
