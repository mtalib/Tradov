# CLAUDE.md - AI Assistant Context for Spyder Trading System

## 🚨 CRITICAL RULES

1. **NEVER commit to main branch** - Always use feature branches
2. **NEVER hardcode credentials** - Use .env file for all sensitive data
3. **NEVER execute live trades without explicit confirmation** - Default to paper trading
4. **ALWAYS test IBKR API changes in paper mode first**
5. **ALWAYS check if IB Gateway is running before making connections**

## 🎯 Project Context

You are working on **Spyder**, a sophisticated algorithmic trading system that:
- Connects to Interactive Brokers (IBKR) for live and paper trading
- Processes real-time market data for automated decision making
- Manages risk and positions with real financial implications
- Uses a modular architecture with 20+ specialized components

**Remember**: This system handles REAL MONEY when in live mode. Every change must be thoroughly tested.

## 📋 Before Starting Any Task

1. **Check current mode**: Verify if system is in PAPER or LIVE mode
2. **Verify IB Gateway status**: Ensure it's running on correct port (4002 for paper, 4001 for live)
3. **Review recent logs**: Check logs/ directory for any recent errors
4. **Understand the module**: Each SpyderX module has specific responsibilities - respect boundaries

## 🏗️ Architecture Quick Reference

```
SpyderA_Core         → System orchestration & main entry
SpyderB_Broker       → IBKR connection & order management  
SpyderC_MarketData   → Real-time data processing
SpyderD_Strategies   → Trading strategy implementations
SpyderE_Risk         → Risk management & position sizing
SpyderG_GUI          → PyQt6 user interface
```

## 💻 Common Commands

```bash
# Start the system
cd /home/adam/Projects/Spyder
source .venv/bin/activate
python SpyderA_Core/SpyderA01_Main.py

# Test IBKR connection
python test_ib_connection.py

# Run tests
pytest SpyderT_Testing/

# Check system status
python SpyderM_Monitoring/check_status.py
```

## 🔧 Development Workflow

1. **Making Changes**:
   ```bash
   git checkout -b feature/your-feature-name
   # Make changes
   git add .
   git commit -m "feat: description"
   ```

2. **Testing Changes**:
   - Unit test: `pytest SpyderT_Testing/test_your_module.py`
   - Integration test: Run in paper mode first
   - Monitor logs: `tail -f logs/spyder_main.log`

3. **Before Committing**:
   - ✅ No hardcoded credentials
   - ✅ Tests pass
   - ✅ Paper trading tested
   - ✅ Logs are clean

## 🐛 Debugging Tips

1. **Connection Issues**: 
   - Check IB Gateway is running: `ps aux | grep -i gateway`
   - Verify port in .env matches IB Gateway settings
   - Check firewall isn't blocking ports 4001/4002

2. **Market Data Issues**:
   - Verify market data subscriptions in IBKR account
   - Check if market is open
   - Review SpyderC_MarketData logs

3. **Order Failures**:
   - Check account permissions in IBKR
   - Verify trading hours for the instrument
   - Review risk limits in SpyderE_Risk

## ⚡ Performance Considerations

- **Rate Limits**: IBKR API has 50 msgs/sec limit - respect it
- **Memory Usage**: Monitor data retention in SpyderH_Storage
- **CPU Usage**: Strategy calculations should be optimized
- **Network Latency**: Consider latency for high-frequency strategies

## 🔐 Security Reminders

- API keys and passwords → `.env` file only
- Use environment variables, never hardcode
- Validate all user inputs
- Sanitize data before storage
- Log sensitive operations but not sensitive data

## 📊 Data Flow

```
Market Data (IBKR) → SpyderC_MarketData 
                   ↓
              SpyderF_Analysis (indicators)
                   ↓
              SpyderD_Strategies (signals)
                   ↓
              SpyderE_Risk (validation)
                   ↓
              SpyderB_Broker (execution)
```

## 🎨 UI/GUI Guidelines

- Keep GUI responsive during long operations (use threading)
- Update status in real-time
- Show clear error messages to users
- Provide confirmation dialogs for critical actions
- Use color coding: RED for errors, YELLOW for warnings, GREEN for success

## 📝 Code Style Preferences

- **Docstrings**: Google style for all public methods
- **Type Hints**: Always include for function signatures
- **Error Handling**: Comprehensive try-except with specific exceptions
- **Logging**: Use module-specific loggers, not print()
- **Constants**: Define in module-level CAPS_WITH_UNDERSCORES
- **Private Methods**: Prefix with underscore (_method_name)

## 🚀 Quick Wins

When improving the system, consider:
1. Adding more comprehensive error messages
2. Improving logging detail for debugging
3. Adding unit tests for uncovered code
4. Optimizing data structure usage
5. Caching frequently accessed data
6. Adding docstrings where missing

## ⚠️ Known Issues & Workarounds

1. **IB Gateway disconnects**: Implement auto-reconnection logic in SpyderB_Broker
2. **Memory leaks with long-running sessions**: Restart daily


## 💬 Communication Style

When responding about this project:
- Be precise about which module you're modifying
- Always mention if changes affect live trading
- Specify paper vs live mode explicitly
- Include relevant log snippets for debugging
- Suggest testing steps for any changes

## 🎯 Current Priorities

1. Stability and reliability over new features
2. Risk management over profit maximization
3. Clear logging over performance optimization
4. Paper testing over live deployment

---

**Remember**: You're working with a financial trading system. Precision, safety, and thorough testing are paramount. When in doubt, ask for clarification rather than making assumptions.
