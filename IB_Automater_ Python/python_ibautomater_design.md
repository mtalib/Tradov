# Python IBAutomater Design Document

## Overview

Python IBAutomater is a comprehensive automation tool for Interactive Brokers Gateway, providing startup, login, restart handling, and 2FA support. It aims to replicate and enhance the functionality of the C# IBAutomater in a Python-native implementation.

## Architecture

### Core Components

#### 1. IBAutomater Class (Main Controller)
```python
class IBAutomater:
    def __init__(self, ib_directory, ib_version, username, password, trading_mode, port, export_logs=False)
    def start(self, wait_for_connection=True)
    def stop()
    def restart()
    def get_last_start_result()
    def is_running()
```

#### 2. Process Manager
- **Purpose**: Handle IB Gateway process lifecycle
- **Responsibilities**:
  - Start IB Gateway with proper arguments
  - Monitor process health
  - Terminate process when needed
  - Detect unexpected exits

#### 3. UI Automation Engine
- **Technology**: Use `pyautogui` and `opencv-python` for GUI automation
- **Responsibilities**:
  - Detect login dialogs
  - Enter credentials automatically
  - Handle 2FA prompts
  - Dismiss popup dialogs
  - Navigate configuration screens

#### 4. Event System
- **Purpose**: Provide event-driven notifications to client applications
- **Events**:
  - `OutputDataReceived`
  - `ErrorDataReceived`
  - `Exited`
  - `Restarted`
  - `LoginCompleted`
  - `TwoFactorRequired`

#### 5. Configuration Manager
- **Purpose**: Handle IB Gateway configuration
- **Responsibilities**:
  - Set API port
  - Configure auto-restart settings
  - Manage trading mode (paper/live)
  - Handle regional settings

#### 6. Restart Handler
- **Purpose**: Manage daily auto-restarts
- **Responsibilities**:
  - Detect auto-restart events
  - Distinguish between soft and hard restarts
  - Handle weekly authentication requirements
  - Notify client applications

## Implementation Strategy

### Phase 1: Core Process Management
1. Basic process startup/shutdown
2. Command-line argument handling
3. Process monitoring
4. Basic event system

### Phase 2: UI Automation
1. Login dialog detection
2. Credential entry automation
3. Basic dialog handling
4. Screenshot-based UI recognition

### Phase 3: Advanced Features
1. 2FA automation
2. Auto-restart detection
3. Configuration management
4. Error handling and recovery

### Phase 4: Cross-Platform Support
1. Windows-specific implementations
2. macOS support
3. Linux support
4. Platform-specific UI automation

## Technical Specifications

### Dependencies
```python
# Core dependencies
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from enum import Enum
from dataclasses import dataclass

# UI Automation
import pyautogui
import cv2
import numpy as np
from PIL import Image

# Process monitoring
import psutil

# Event handling
from threading import Event
import queue
```

### Configuration Structure
```python
@dataclass
class IBConfig:
    ib_directory: str
    ib_version: str
    username: str
    password: str
    trading_mode: str  # 'paper' or 'live'
    port: int
    export_logs: bool = False
    auto_restart_time: str = "23:45"
    region: str = "us"
    java_heap_size: str = "4096m"
```

### Event System
```python
class IBEvent(Enum):
    OUTPUT_DATA_RECEIVED = "output_data_received"
    ERROR_DATA_RECEIVED = "error_data_received"
    EXITED = "exited"
    RESTARTED = "restarted"
    LOGIN_COMPLETED = "login_completed"
    TWO_FACTOR_REQUIRED = "two_factor_required"

@dataclass
class EventData:
    event_type: IBEvent
    data: Any
    timestamp: float
```

### UI Automation Strategy

#### Template Matching
- Store reference images for common UI elements
- Use OpenCV template matching for element detection
- Support multiple resolutions and DPI settings
- Implement fuzzy matching for slight variations

#### Text Recognition (OCR)
- Use `pytesseract` for text recognition when needed
- Detect error messages and status text
- Handle multi-language support

#### Coordinate-based Actions
- Click buttons and input fields
- Type credentials securely
- Handle dropdown menus
- Navigate dialog boxes

## Error Handling

### Error Categories
1. **Process Errors**: Gateway fails to start
2. **Authentication Errors**: Login failures, 2FA timeouts
3. **UI Errors**: Dialog detection failures
4. **Network Errors**: Connection issues
5. **Configuration Errors**: Invalid settings

### Recovery Strategies
1. **Retry Logic**: Automatic retries with exponential backoff
2. **Fallback Methods**: Alternative UI automation approaches
3. **User Notification**: Clear error messages and suggested actions
4. **Graceful Degradation**: Partial functionality when possible

## Security Considerations

### Credential Handling
- Support encrypted credential storage
- Environment variable support
- Secure memory handling for passwords
- Optional keyring integration

### 2FA Implementation
- IBKR Mobile app integration
- Timeout handling (3-minute limit)
- Retry logic for failed attempts
- Fallback to manual intervention

## Platform-Specific Implementations

### Windows
- Use Windows-specific process management
- Handle Windows UI scaling
- Support Windows service deployment

### macOS
- Handle macOS security permissions
- Support Retina display scaling
- Implement macOS-specific UI automation

### Linux
- Support various window managers
- Handle different display servers (X11, Wayland)
- Implement headless operation for servers

## Testing Strategy

### Unit Tests
- Process management functions
- Configuration parsing
- Event system
- Error handling

### Integration Tests
- Full startup/shutdown cycles
- UI automation workflows
- 2FA simulation
- Auto-restart scenarios

### Mock Testing
- Simulated IB Gateway responses
- UI element mocking
- Network condition simulation

## Performance Considerations

### Resource Usage
- Minimize CPU usage during idle periods
- Efficient image processing for UI automation
- Memory management for long-running processes

### Responsiveness
- Non-blocking UI automation
- Asynchronous event handling
- Quick response to user commands

## Future Enhancements

### Advanced Features
1. Multiple account support
2. Gateway health monitoring
3. Performance metrics collection
4. Remote management capabilities
5. Docker containerization support

### Integration Options
1. REST API for remote control
2. WebSocket event streaming
3. Prometheus metrics export
4. Logging integration (ELK stack)

## API Design

### Main Interface
```python
# Basic usage example
automater = IBAutomater(
    ib_directory="/path/to/ib",
    ib_version="10.19",
    username="your_username",
    password="your_password",
    trading_mode="paper",
    port=7497
)

# Event handlers
automater.on_output_data_received = lambda data: print(f"Output: {data}")
automater.on_error_data_received = lambda data: print(f"Error: {data}")
automater.on_exited = lambda: print("Gateway exited")
automater.on_restarted = lambda: print("Gateway restarted")

# Start the gateway
result = automater.start()
if result.success:
    print("Gateway started successfully")
else:
    print(f"Failed to start: {result.error_message}")

# Stop the gateway
automater.stop()
```

This design provides a comprehensive foundation for building a Python equivalent to IBAutomater while maintaining compatibility with the original's event-driven architecture and functionality.

