# Spyder Trading System - Project Instructions

## Overview
Spyder is a modular algorithmic trading system designed for automated trading through Interactive Brokers (IBKR). The system follows a strict modular architecture with clear separation of concerns.

**📋 Related Documentation:**
- [Trading Standards](Standards/Trading/) - Comprehensive operational standards
- [System Standards](Standards/System/) - Infrastructure and system standards  
- [Python Standards](Standards/Python/) - Code quality and development standards

## Key Principles

### Architecture Guidelines
1. **Modular Design**: Each SpyderX module has a specific responsibility. Never mix concerns across modules.
2. **Module Naming**: All modules follow SpyderX_Name pattern where X is a letter (A-Z) indicating the module's role in the system hierarchy.
3. **File Naming**: Within each module, files follow SpyderX##_Purpose.py pattern (e.g., SpyderB01_IBConnection.py).
4. **Standards Compliance**: All development must follow [Trading Standards](Standards/Trading/) for performance, security, and deployment requirements.

### Code Standards
1. **Error Handling**: Always use try-except blocks for external API calls, especially IBKR API operations
2. **Logging**: Use the centralized logging system in SpyderU_Utilities. Never use print() for production code
3. **Type Hints**: Always include type hints for function parameters and returns
4. **Docstrings**: Use Google-style docstrings for all classes and public methods
5. **Performance**: Follow [Performance Standards](Standards/Trading/Performance.md) for latency and throughput requirements
6. **Security**: Implement [Security Standards](Standards/Trading/Security.md) for all trading system components

### IBKR Integration
1. **Connection Management**: All IBKR connections must go through SpyderB_Broker module
2. **Client IDs**: Use unique client IDs for different components (defined in SpyderB module)
3. **Error Codes**: Handle IBKR-specific error codes appropriately (see SpyderB_Broker/error_codes.py)
4. **Rate Limiting**: Respect IBKR API rate limits (50 messages/second)
5. **Integration Standards**: Follow [IBKR Integration Standards](Standards/Trading/IBKR-Integration.md) for best practices

### Testing Requirements
1. **Unit Tests**: Each module should have corresponding tests in SpyderT_Testing
2. **Paper Trading**: Always test strategies in paper trading mode first
3. **Connection Tests**: Run test_ib_connection.py before starting the system
4. **Testing Protocols**: Follow comprehensive [Testing Protocols](Standards/Trading/Testing-Protocols.md) for all strategies and systems

### Security & Configuration
1. **Credentials**: Never hardcode credentials. Use .env file for all sensitive data
2. **API Keys**: Store all API keys and passwords in .env (see .env.template)
3. **Port Configuration**: Default IB Gateway port is 4002 (paper) and 4001 (live)
4. **Security Compliance**: Implement all [Security Standards](Standards/Trading/Security.md) including encryption, access control, and monitoring

## Module Responsibilities

### Core System
- **SpyderA_Core**: Main entry point, system initialization, orchestration
- **SpyderB_Broker**: IBKR connection, order management, execution
- **SpyderC_MarketData**: Real-time and historical data handling

### Trading Logic
- **SpyderD_Strategies**: Strategy implementations and backtesting
- **SpyderE_Risk**: Risk management, position sizing, stop-loss
- **SpyderS_Signals**: Signal generation and validation

### Analysis & Intelligence
- **SpyderF_Analysis**: Technical indicators, market analysis
- **SpyderL_ML**: Machine learning models and predictions
- **SpyderO_TradingIntelligence**: Advanced analytics and insights
- **SpyderV_QuantModels**: Quantitative models and statistical analysis

### User Interface & Reporting
- **SpyderG_GUI**: PyQt6 graphical interface
- **SpyderK_Reports**: Performance reports and analytics
- **SpyderJ_Alerts**: Notification and alert system

### Infrastructure
- **SpyderH_Storage**: Data persistence and database operations
- **SpyderI_Integration**: Third-party service integrations
- **SpyderM_Monitoring**: System health and performance monitoring
- **SpyderR_Runtime**: Runtime configuration and management

### Support Modules
- **SpyderN_OptionsAnalytics**: Options-specific calculations and Greeks
- **SpyderP_PortfolioMgmt**: Portfolio optimization and management
- **SpyderQ_Scripts**: Utility scripts and tools
- **SpyderT_Testing**: Testing framework and test utilities
- **SpyderU_Utilities**: Shared utilities and helpers
- **SpyderX_Agents**: AI agents and automation
- **SpyderZ_Communication**: Inter-module communication

## Common Tasks

### Starting the System
```bash
# Activate virtual environment
source .venv/bin/activate

# Start with GUI
python SpyderA_Core/SpyderA01_Main.py

# Start in headless mode
python SpyderA_Core/SpyderA01_Main.py --headless
```

### Testing Connection
```bash
python test_ib_connection.py
```

### Running Tests
```bash
pytest SpyderT_Testing/
```

## Important Notes

1. **IB Gateway**: Must be running before starting Spyder (use IB Gateway, not TWS for better stability)
2. **Market Hours**: Some features only work during market hours
3. **Paper vs Live**: Always specify paper/live mode explicitly in configuration
4. **Logging**: Check logs/ directory for debugging information
5. **Performance**: Monitor system performance through SpyderM_Monitoring dashboards
6. **Risk Management**: All trading must comply with [Risk Management Standards](Standards/Trading/Risk-Management.md)
7. **Deployment**: Follow [Deployment Standards](Standards/Trading/Deployment.md) for production releases
8. **Monitoring**: Implement [Monitoring Standards](Standards/Trading/Monitoring.md) for system observability

## Development Workflow

1. Make changes in feature branches, not main
2. Test thoroughly in paper trading mode
3. Verify no hardcoded credentials or sensitive data
4. Run unit tests before committing
5. Update relevant documentation in docs/

## Troubleshooting

### Common Issues
1. **Connection Failed**: Check IB Gateway is running and ports match .env configuration
2. **No Market Data**: Verify market data subscriptions in IBKR account
3. **Order Rejected**: Check account permissions and trading hours
4. **High Memory Usage**: Review data retention settings in SpyderH_Storage

### Debug Mode
Set `DEBUG=True` in .env file for verbose logging

## AI Assistant Guidelines

When working on this project:
1. Always respect the modular architecture - don't mix concerns
2. Check existing implementations before creating new functionality
3. Follow the established naming conventions
4. Test IBKR API interactions carefully - they can affect real money
5. Document any new API integrations or complex logic
6. Consider performance implications for real-time trading operations
7. Ensure thread safety for concurrent operations
8. Validate all user inputs and API responses
9. Handle network failures and API disconnections gracefully
10. Keep the GUI responsive during long-running operations

### Standards Compliance for AI Development
- **Performance**: Ensure all code meets [Performance Standards](Standards/Trading/Performance.md) latency requirements (<500μs tick-to-trade)
- **Security**: Implement [Security Standards](Standards/Trading/Security.md) for authentication, encryption, and access control
- **Strategy Development**: Follow [Strategy Development Standards](Standards/Trading/Strategy-Development.md) for backtesting and validation
- **Risk Management**: Integrate [Risk Management Standards](Standards/Trading/Risk-Management.md) into all trading logic
- **Testing**: Use [Testing Protocols](Standards/Trading/Testing-Protocols.md) for comprehensive validation
- **Deployment**: Apply [Deployment Standards](Standards/Trading/Deployment.md) for production releases
- **Monitoring**: Implement [Monitoring Standards](Standards/Trading/Monitoring.md) for observability and alerting

### Key References
- For technical architecture: See `Spyder-Architecture.json` for module structure and dependencies
- For operational standards: Reference appropriate documents in `Standards/Trading/`
- For system requirements: Check `Standards/System/` for infrastructure and deployment standards
