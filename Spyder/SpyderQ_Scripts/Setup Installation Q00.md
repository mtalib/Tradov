# Setup & Installation (Q00-Q09)
SpyderQ01_Setup.sh              # Main installation script
SpyderQ02_Dependencies.sh       # Install system dependencies
SpyderQ03_Configure.sh          # Configuration wizard
SpyderQ04_Upgrade.sh            # Upgrade existing installation

# Start/Stop/Control (Q10-Q19)
SpyderQ10_StartAll.sh           # Start all components
SpyderQ11_StopAll.sh            # Stop all components
SpyderQ12_Restart.sh            # Restart everything
SpyderQ13_StartWatchdog.sh      # Start watchdog only
SpyderQ14_StartMetrics.sh       # Start metrics only
SpyderQ15_Emergency.sh          # Emergency shutdown

# Monitoring & Status (Q20-Q29)
SpyderQ20_Status.sh             # System status
SpyderQ21_Monitor.sh            # Live monitoring
SpyderQ22_HealthCheck.sh        # Health check
SpyderQ23_ClientStatus.sh       # Client-specific status
SpyderQ24_Logs.sh               # Log viewer

# Testing & Development (Q30-Q39)
SpyderQ30_TestAll.sh            # Run all tests
SpyderQ31_TestModules.sh        # Test module imports
SpyderQ32_TestConnections.sh    # Test IB connections
SpyderQ33_MockGateway.sh        # Start mock gateway
SpyderQ34_Debug.sh              # Debug mode launcher

# Maintenance & Cleanup (Q40-Q49)
SpyderQ40_Cleanup.sh            # Clean logs and temp files
SpyderQ41_Backup.sh             # Backup configuration
SpyderQ42_Restore.sh            # Restore from backup
SpyderQ43_UpdateModules.sh      # Update Python modules
SpyderQ44_RotateLogs.sh         # Rotate log files

# Data & Reports (Q50-Q59)
SpyderQ50_ExportData.sh         # Export trading data
SpyderQ51_ImportData.sh         # Import trading data
SpyderQ52_ArchiveReports.sh     # Archive reports

# Python Helper Scripts (Q60-Q69)
SpyderQ60_MetricsExporter.py    # Export Prometheus metrics
SpyderQ61_HealthReporter.py     # Generate health reports
SpyderQ62_ClientAnalyzer.py     # Analyze client performance

# Service Files (Q70-Q79)
SpyderQ70_Watchdog.service      # Systemd service files
SpyderQ71_Metrics.service
SpyderQ72_Integration.service

# Configuration Files (Q80-Q89)
SpyderQ80_Config.env            # Environment configuration
SpyderQ81_Prometheus.yml        # Prometheus config
SpyderQ82_Alerts.yml            # Alert rules
