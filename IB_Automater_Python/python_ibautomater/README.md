# Python IBAutomater

A Python implementation of IBAutomater that provides comprehensive automation for Interactive Brokers Gateway including startup, login, restart handling, and 2FA support.

## Overview

Python IBAutomater fills a significant gap in the Python trading ecosystem by providing the same functionality as the C# IBAutomater but in a Python-native implementation. While existing Python libraries like `ib_async` and the official IB API handle communication with an already running IB Gateway, they don't provide automation for starting, logging in, and managing the gateway itself.

## Features

- **Gateway Process Management**: Start, stop, and restart IB Gateway programmatically
- **Automated Login**: Automatic username/password entry and login completion
- **Two-Factor Authentication**: Support for IBKR Mobile 2FA with timeout handling
- **Auto-Restart Detection**: Detect and handle daily auto-restarts vs. weekly full authentication
- **Event-Driven Architecture**: Comprehensive event system for monitoring gateway state
- **Cross-Platform Support**: Works on Windows, macOS, and Linux
- **UI Automation**: Robust dialog detection and handling using computer vision
- **Error Handling**: Comprehensive error handling with retry logic and recovery strategies

## Installation

### From Source

```bash
git clone https://github.com/your-repo/python-ibautomater.git
cd python-ibautomater
pip install -e .
```

### Dependencies

The package requires the following dependencies:

- `pyautogui>=0.9.54` - GUI automation
- `opencv-python>=4.5.0` - Computer vision for UI element detection
- `pillow>=8.0.0` - Image processing
- `psutil>=5.8.0` - Process monitoring
- `numpy>=1.20.0` - Numerical operations
- `pytesseract>=0.3.8` - OCR for text recognition (optional)

## Quick Start

### Basic Usage

```python
from ibautomater import IBAutomater

# Create IBAutomater instance
automater = IBAutomater(
    ib_directory="/path/to/ib/gateway",
    ib_version="10.19",
    username="your_username",
    password="your_password", 
    trading_mode="paper",  # or "live"
    port=7497
)

# Setup event handlers
automater.on_output_data_received = lambda data: print(f"Output: {data}")
automater.on_error_data_received = lambda data: print(f"Error: {data}")
automater.on_exited = lambda args: print(f"Gateway exited: {args.reason}")
automater.on_restarted = lambda data: print("Gateway restarted")

# Start the gateway
result = automater.start()
if result.success:
    print(f"Gateway started successfully (PID: {result.process_id})")
else:
    print(f"Failed to start: {result.error_message}")

# Stop the gateway
automater.stop()
```

### Using Context Manager

```python
with IBAutomater(
    ib_directory="/path/to/ib/gateway",
    ib_version="10.19",
    username="your_username",
    password="your_password",
    trading_mode="paper",
    port=7497
) as automater:
    
    result = automater.start()
    if result.success:
        # Do your trading work here
        time.sleep(60)
    
    # Gateway automatically stopped when exiting context
```

### Command Line Interface

```bash
# Start IB Gateway
python -m ibautomater start \
    --ib-directory "/path/to/ib/gateway" \
    --ib-version "10.19" \
    --username "your_username" \
    --password "your_password" \
    --trading-mode "paper" \
    --port 7497

# Check status
python -m ibautomater status \
    --ib-directory "/path/to/ib/gateway" \
    --ib-version "10.19" \
    --username "your_username" \
    --password "your_password" \
    --trading-mode "paper" \
    --port 7497

# Stop IB Gateway
python -m ibautomater stop \
    --ib-directory "/path/to/ib/gateway" \
    --ib-version "10.19" \
    --username "your_username" \
    --password "your_password" \
    --trading-mode "paper" \
    --port 7497
```

## Event Handling

Python IBAutomater provides a comprehensive event system to monitor gateway state:

### Available Events

- `output_data_received`: Gateway process output
- `error_data_received`: Gateway process errors  
- `exited`: Gateway process exited (unexpected)
- `restarted`: Gateway auto-restarted (daily restart)
- `login_completed`: Login process completed successfully
- `two_factor_required`: 2FA authentication required

### Event Handler Example

```python
def handle_exit(event_args):
    """Handle gateway exit events"""
    print(f"Gateway exited: {event_args.reason}")
    
    if event_args.unexpected:
        print("Unexpected exit, attempting restart...")
        result = automater.restart()
        if result.success:
            print("Restart successful")

def handle_restart(event_data):
    """Handle auto-restart events"""
    print("Gateway auto-restarted")
    # Reconnect your trading application here

automater.on_exited = handle_exit
automater.on_restarted = handle_restart
```

## Auto-Restart Handling

IB Gateway requires daily restarts. Python IBAutomater handles two types of restarts:

1. **Soft Restart** (Daily): Gateway restarts automatically, no re-authentication needed
2. **Hard Restart** (Weekly): Full authentication required

```python
def handle_exit(event_args):
    """Handle gateway exits"""
    result = automater.get_last_start_result()
    
    if not result.has_error:
        print("Gateway closed for restart, restarting...")
        time.sleep(10)  # Wait for gateway to fully close
        
        # Restart gateway
        result = automater.start()
        if result.success:
            print("Gateway restarted successfully")

def handle_restart(event_data):
    """Handle soft restarts"""
    print("Gateway soft restart detected")
    # Your trading application should reconnect here

automater.on_exited = handle_exit
automater.on_restarted = handle_restart
```

## Two-Factor Authentication

Python IBAutomater supports IBKR Mobile 2FA:

```python
def handle_2fa(event_data):
    """Handle 2FA requests"""
    print("2FA required - check your IBKR Mobile app")
    print("You have 3 minutes to complete authentication")

automater.on_two_factor_required = handle_2fa
```

The system will:
1. Detect 2FA dialog automatically
2. Wait for user to complete authentication on mobile device
3. Continue login process once 2FA is completed
4. Handle timeout and retry scenarios

## Configuration

### IBConfig Options

```python
from ibautomater import IBConfig, TradingMode

config = IBConfig(
    ib_directory="/path/to/ib/gateway",
    ib_version="10.19",
    username="your_username", 
    password="your_password",
    trading_mode=TradingMode.PAPER,
    port=7497,
    
    # Optional settings
    export_logs=False,
    auto_restart_time="23:45",
    timeout_seconds=300,
    max_login_attempts=3,
    two_factor_timeout=180,
    
    # UI automation settings
    ui_timeout=30.0,
    screenshot_interval=1.0,
    template_match_threshold=0.8
)

automater = IBAutomater(config)
```

## Integration with Trading Libraries

### With ib_async

```python
import asyncio
from ib_async import IB
from ibautomater import IBAutomater

async def trading_with_ibautomater():
    # Start gateway
    automater = IBAutomater(...)
    result = automater.start()
    
    if result.success:
        # Connect trading library
        ib = IB()
        await ib.connectAsync('127.0.0.1', 7497, clientId=1)
        
        # Your trading logic here
        contracts = await ib.reqContractDetailsAsync(Stock('AAPL', 'SMART', 'USD'))
        
        # Cleanup
        ib.disconnect()
        automater.stop()

# Run the async function
asyncio.run(trading_with_ibautomater())
```

### With Official IB API

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibautomater import IBAutomater

class TradingApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

# Start gateway first
automater = IBAutomater(...)
result = automater.start()

if result.success:
    # Connect trading app
    app = TradingApp()
    app.connect("127.0.0.1", 7497, clientId=1)
    app.run()
    
    # Cleanup
    automater.stop()
```

## Error Handling

Python IBAutomater provides comprehensive error handling:

```python
from ibautomater.exceptions import (
    IBAutomaterError,
    ProcessError, 
    AuthenticationError,
    UIError,
    TwoFactorError
)

try:
    result = automater.start()
    if not result.success:
        print(f"Start failed: {result.error_message}")
        
except ProcessError as e:
    print(f"Process error: {e}")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
except TwoFactorError as e:
    print(f"2FA error: {e}")
except UIError as e:
    print(f"UI automation error: {e}")
```

## Logging

Enable detailed logging for debugging:

```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ibautomater.log')
    ]
)

# Now run IBAutomater
automater = IBAutomater(...)
```

## Platform-Specific Notes

### Windows
- Ensure IB Gateway is installed in a standard location
- May require running as administrator for UI automation
- Windows Defender may need exclusions for the gateway directory

### macOS
- Grant accessibility permissions for UI automation
- Handle Retina display scaling automatically
- Support for both Intel and Apple Silicon

### Linux
- Works with X11 and Wayland display servers
- Requires appropriate permissions for process management
- Tested on Ubuntu, CentOS, and other major distributions

## Troubleshooting

### Common Issues

1. **Gateway fails to start**
   - Check IB directory path is correct
   - Verify IB Gateway version matches
   - Ensure Java runtime is available

2. **Login automation fails**
   - Check username/password are correct
   - Verify UI automation permissions
   - Check for display scaling issues

3. **2FA timeout**
   - Ensure IBKR Mobile app is installed and configured
   - Check network connectivity
   - Verify 2FA is enabled for API access

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('ibautomater').setLevel(logging.DEBUG)
```

## Comparison with C# IBAutomater

| Feature | C# IBAutomater | Python IBAutomater |
|---------|----------------|-------------------|
| Gateway startup | ✅ | ✅ |
| Automated login | ✅ | ✅ |
| 2FA support | ✅ | ✅ |
| Auto-restart detection | ✅ | ✅ |
| Event system | ✅ | ✅ |
| Cross-platform | ✅ | ✅ |
| Language | C#/.NET | Python |
| UI automation | Java agent | Computer vision |
| Installation | NuGet | pip |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is not affiliated with Interactive Brokers Group, Inc. Use at your own risk and ensure compliance with Interactive Brokers' terms of service.

## Support

For support and questions:
- Open an issue on GitHub
- Check the [examples](examples/) directory for usage patterns
- Review the [documentation](docs/) for detailed API reference

