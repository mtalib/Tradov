# CLAUDE.md - AI Assistant Context for Spyder Trading System

## CRITICAL RULES

1. **NEVER commit to main branch** - Always use feature branches
2. **NEVER hardcode credentials** - Use .env file for all sensitive data
3. **NEVER execute live trades without explicit confirmation** - Default to sandbox
4. **ALWAYS test in sandbox mode first** - Validate before any live deployment
5. **ALWAYS validate API credentials before connecting** - Use validation scripts

## Project Context

You are working on **Spyder**, a sophisticated algorithmic trading system that:
- Connects to **Tradier API** for order execution (Bearer token auth)
- Uses **Polygon.io** for real-time and historical market data
- Processes real-time market data for automated decision making
- Manages risk and positions with real financial implications
- Uses a modular architecture with 20+ specialized components

**Remember**: This system handles REAL MONEY when in live mode. Every change must be thoroughly tested.

## API Architecture

### Tradier API (Order Execution)
- **Authentication**: Bearer token (simple API key)
- **Base URLs**:
  - Sandbox: `https://sandbox.tradier.com/v1`
  - Live: `https://api.tradier.com/v1`
- **Features**: Account management, positions, orders, option chains
- **Documentation**: https://documentation.tradier.com/

### Polygon.io (Market Data)
- **Authentication**: API key in query string or header
- **REST URL**: `https://api.polygon.io`
- **WebSocket URL**: `wss://socket.polygon.io`
- **Features**: Real-time trades/quotes, historical data, aggregates
- **Rate Limits**: Starter (5/min REST), Business (100/min REST)
- **Documentation**: https://polygon.io/docs

## Before Starting Any Task

1. **Check current mode**: Verify if system is in SANDBOX or LIVE mode (.env file)
2. **Verify API setup**: Ensure Tradier and Polygon API keys are configured
3. **Review recent logs**: Check logs/ directory for any recent errors
4. **Understand the module**: Each SpyderX module has specific responsibilities

## Architecture Quick Reference

```
SpyderA_Core         -> System orchestration & main entry
SpyderB_Broker       -> Tradier API integration (order execution)
  └─TradierClient    -> Primary broker interface (SpyderB40)
SpyderC_MarketData   -> Polygon.io data processing
  └─PolygonHandler   -> WebSocket streaming (SpyderC25)
SpyderD_Strategies   -> Trading strategy implementations
SpyderE_Risk         -> Risk management & position sizing
SpyderG_GUI          -> PyQt6 user interface
```

## Common Commands

```bash
# Validate environment configuration
python SpyderQ_Scripts/validate_tradier_polygon.py

# Test configuration
python config/config.py

# Start the system
cd /home/user/Spyder
source .venv/bin/activate
python SpyderA_Core/SpyderA01_Main.py

# Run all tests
pytest SpyderT_Testing/

# Run Tradier client tests
pytest SpyderT_Testing/SpyderT40_TradierClient_Test.py

# Run integration tests
pytest SpyderT_Testing/SpyderT42_Integration_Test.py
```

## Development Workflow

1. **Making Changes**:
   ```bash
   git checkout -b feature/your-feature-name
   # Make changes
   git add .
   git commit -m "feat: description"
   ```

2. **Testing Changes**:
   - Validate .env: `python SpyderQ_Scripts/validate_tradier_polygon.py`
   - Unit test: `pytest SpyderT_Testing/test_your_module.py`
   - Integration test: Run in sandbox mode first
   - Monitor logs: `tail -f logs/spyder.log`

3. **Before Committing**:
   - No hardcoded credentials
   - Tests pass
   - Sandbox trading tested
   - Logs are clean

## Debugging Tips

1. **GUI Logging** (NEW!):
   - All `logger.info()` calls now appear in dashboard automatically
   - System Log panel: Infrastructure, connections, errors
   - Automation Log panel: Strategies, trades, signals
   - Configure level: Set `GUI_LOG_LEVEL=INFO` in .env
   - See: `docs/GUI_LOGGING.md` for full documentation

2. **Tradier API Issues**:
   - Run validation: `python SpyderQ_Scripts/validate_tradier_polygon.py`
   - Check TRADIER_API_KEY in .env
   - Verify TRADIER_ACCOUNT_ID is correct
   - Check if market is open for order execution

3. **Polygon Connection Issues**:
   - Verify POLYGON_API_KEY in .env
   - Check WebSocket connection status
   - Review rate limits (Starter: 5/min REST)
   - Check subscription level for data access

4. **Market Data Issues**:
   - Verify Polygon subscription level
   - Check if market is open
   - Review SpyderC_MarketData logs

5. **Order Failures**:
   - Check Tradier account permissions
   - Verify trading hours for the instrument
   - Review risk limits in SpyderE_Risk
   - Ensure sufficient buying power

## Performance Considerations

- **Tradier Rate Limits**: No official limit, but be reasonable (~10 req/sec)
- **Polygon Rate Limits**: Starter (5/min), Business (100/min)
- **Memory Usage**: Monitor data retention in SpyderH_Storage
- **CPU Usage**: Strategy calculations should be optimized
- **Network Latency**: Consider latency for time-sensitive strategies

## Security Reminders

- API keys -> `.env` file only
- Use environment variables, never hardcode
- Validate all user inputs
- Sanitize data before storage
- Log sensitive operations but not sensitive data
- Never commit .env to git

## Data Flow

```
Polygon.io WebSocket -> SpyderC_MarketData/PolygonDataHandler
                        |
                        v
                  SpyderC_MarketData (normalization)
                        |
                        v
                  SpyderF_Analysis (indicators)
                        |
                        v
                  SpyderD_Strategies (signals)
                        |
                        v
                  SpyderE_Risk (validation)
                        |
                        v
                  SpyderB_Broker/TradierClient (execution)
```

## UI/GUI Guidelines

- Keep GUI responsive during long operations (use threading)
- Update status in real-time
- Show clear error messages to users
- Provide confirmation dialogs for critical actions
- Use color coding: RED for errors, YELLOW for warnings, GREEN for success

## Code Style Preferences

- **Docstrings**: Google style for all public methods
- **Type Hints**: Always include for function signatures
- **Error Handling**: Comprehensive try-except with specific exceptions
- **Logging**: Use module-specific loggers, not print()
- **Constants**: Define in module-level CAPS_WITH_UNDERSCORES
- **Private Methods**: Prefix with underscore (_method_name)

## Quick Wins

When improving the system, consider:
1. Adding more comprehensive error messages
2. Improving logging detail for debugging
3. Adding unit tests for uncovered code
4. Optimizing data structure usage
5. Caching frequently accessed data
6. Adding docstrings where missing

## API Setup Checklist

Before first run, ensure:
- [ ] Tradier account created at https://brokerage.tradier.com/
- [ ] Tradier API key generated (API Access section)
- [ ] Tradier account ID noted
- [ ] Polygon.io account created at https://polygon.io/
- [ ] Polygon API key generated
- [ ] All keys set in .env file
- [ ] TRADING_MODE set to "sandbox"
- [ ] Configuration validated: `python SpyderQ_Scripts/validate_tradier_polygon.py`

## Key Files Reference

| Purpose | File Path |
|---------|-----------|
| Main Entry | `SpyderA_Core/SpyderA01_Main.py` |
| Configuration | `config/config.py` |
| Environment | `.env` |
| Tradier Client | `SpyderB_Broker/SpyderB40_TradierClient.py` |
| Polygon Handler | `SpyderC_MarketData/SpyderC25_PolygonDataHandler.py` |
| Risk Manager | `SpyderE_Risk/SpyderE01_RiskManager.py` |
| Validation Script | `SpyderQ_Scripts/validate_tradier_polygon.py` |

## Testing

| Test Suite | Purpose |
|------------|---------|
| `SpyderT40_TradierClient_Test.py` | Tradier API client tests |
| `SpyderT42_Integration_Test.py` | End-to-end workflow tests |

## Current Priorities

1. Stability and reliability over new features
2. Risk management over profit maximization
3. Clear logging over performance optimization
4. Sandbox testing over live deployment

---

**Remember**: You're working with a financial trading system. Precision, safety, and thorough testing are paramount. When in doubt, ask for clarification rather than making assumptions.
