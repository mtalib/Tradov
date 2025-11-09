# CLAUDE.md - AI Assistant Context for Spyder Trading System

## 🚨 CRITICAL RULES

1. **NEVER commit to main branch** - Always use feature branches
2. **NEVER hardcode credentials** - Use .env file for all sensitive data
3. **NEVER execute live trades without explicit confirmation** - Default to paper trading
4. **ALWAYS test in paper mode first** - Validate before any live deployment
5. **ALWAYS validate OAuth credentials before connecting** - Use validation scripts

## 🎯 Project Context

You are working on **Spyder**, a sophisticated algorithmic trading system that:
- Connects to Interactive Brokers via **IBKR Web API** (OAuth 2.0)
- Processes real-time market data for automated decision making
- Manages risk and positions with real financial implications
- Uses a modular architecture with 20+ specialized components

**Remember**: This system handles REAL MONEY when in live mode. Every change must be thoroughly tested.

## 📡 IBKR Web API Architecture

**Connection Method**: OAuth 2.0 with `private_key_jwt` (RFC 7521/7523)

**Key Points**:
- Uses RESTful HTTP API + WebSocket for streaming
- Authentication via signed JWT tokens with RSA private keys
- No IB Gateway, TWS, or ib_async library - pure Web API
- Rate limit: 50 requests/second (OAuth 2.0)
- Session management: Auto-tickle every 4 minutes

**Documentation**: https://www.interactivebrokers.com/campus/ibkr-api-page/web-api/

## 📋 Before Starting Any Task

1. **Check current mode**: Verify if system is in PAPER or LIVE mode (.env file)
2. **Verify OAuth setup**: Ensure consumer key and private key are configured
3. **Review recent logs**: Check logs/ directory for any recent errors
4. **Understand the module**: Each SpyderX module has specific responsibilities - respect boundaries

## 🏗️ Architecture Quick Reference

```
SpyderA_Core         → System orchestration & main entry
SpyderB_Broker       → IBKR Web API integration (OAuth 2.0)
  └─ClientPortalAPI/ → Web API implementation (9 modules)
SpyderC_MarketData   → Real-time data processing
SpyderD_Strategies   → Trading strategy implementations
SpyderE_Risk         → Risk management & position sizing
SpyderG_GUI          → PyQt6 user interface
```

## 💻 Common Commands

```bash
# Validate environment configuration
python SpyderQ_Scripts/validate_env.py

# Test configuration
python config/config.py

# Run OAuth authentication tests
python SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py

# Start the system
cd /home/user/Spyder
source .venv/bin/activate
python SpyderA_Core/SpyderA01_Main.py

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
   - Validate .env: `python SpyderQ_Scripts/validate_env.py`
   - Unit test: `pytest SpyderT_Testing/test_your_module.py`
   - Integration test: Run in paper mode first
   - Monitor logs: `tail -f logs/spyder_webapi.log`

3. **Before Committing**:
   - ✅ No hardcoded credentials
   - ✅ Tests pass
   - ✅ Paper trading tested
   - ✅ Logs are clean
   - ✅ OAuth configuration validated

## 🐛 Debugging Tips

1. **OAuth Authentication Issues**:
   - Run validation: `python SpyderQ_Scripts/validate_env.py`
   - Check consumer key in .env matches IBKR app settings
   - Verify private key exists and has correct permissions (600)
   - Ensure public key is uploaded to IBKR OAuth app

2. **API Connection Issues**:
   - Check IBKR Web API status
   - Verify API base URL in .env
   - Test with: `python config/config.py`
   - Review SpyderB_Broker/ClientPortalAPI logs

3. **Session Expiry**:
   - Sessions last 24 hours maximum
   - Auto-tickle runs every 4 minutes
   - Check session management logs

4. **Rate Limiting**:
   - OAuth 2.0 limit: 50 requests/second
   - Monitor rate limiter logs
   - Adaptive backoff activates on 429 errors

5. **Market Data Issues**:
   - Verify market data subscriptions in IBKR account
   - Check if market is open
   - Review SpyderC_MarketData logs

6. **Order Failures**:
   - Check account permissions in IBKR
   - Verify trading hours for the instrument
   - Review risk limits in SpyderE_Risk

## ⚡ Performance Considerations

- **Rate Limits**: 50 requests/sec (OAuth 2.0) - adaptive backoff enabled
- **Session Management**: Auto-tickle every 4 minutes prevents 6-min timeout
- **Memory Usage**: Monitor data retention in SpyderH_Storage
- **CPU Usage**: Strategy calculations should be optimized
- **Network Latency**: Consider latency for high-frequency strategies

## 🔐 Security Reminders

- OAuth credentials → `.env` file only
- Private key file permissions: `chmod 600 config/keys/private_key.pem`
- Use environment variables, never hardcode
- Validate all user inputs
- Sanitize data before storage
- Log sensitive operations but not sensitive data
- Never commit .env or private keys to git

## 📊 Data Flow

```
IBKR Web API (OAuth 2.0) → SpyderB_Broker/ClientPortalAPI
                          ↓
                    SpyderC_MarketData
                          ↓
                    SpyderF_Analysis (indicators)
                          ↓
                    SpyderD_Strategies (signals)
                          ↓
                    SpyderE_Risk (validation)
                          ↓
                    SpyderB_Broker (execution via API)
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

1. **API Rate Limiting**: Adaptive backoff handles 429 errors automatically
2. **Session Expiry**: Auto-tickle prevents 6-minute timeout
3. **Token Refresh**: Automatic refresh 60 seconds before expiry
4. **Memory leaks with long-running sessions**: Restart daily recommended

## 🔄 OAuth 2.0 Setup Checklist

Before first run, ensure:
- [ ] OAuth app registered with IBKR
- [ ] RSA key pair generated
- [ ] Public key uploaded to IBKR
- [ ] Consumer key set in .env
- [ ] Private key path set in .env
- [ ] Account ID set in .env
- [ ] TRADING_MODE set to "paper"
- [ ] Configuration validated: `python SpyderQ_Scripts/validate_env.py`

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

## 📚 Key Files Reference

| Purpose | File Path |
|---------|-----------|
| Main Entry | `SpyderA_Core/SpyderA01_Main.py` |
| Configuration | `config/config.py` |
| Environment | `.env` |
| OAuth Auth | `SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_Auth.py` |
| REST Client | `SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_RESTClient.py` |
| WebSocket | `SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_WebSocket.py` |
| Session Manager | `SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_Session.py` |
| Rate Limiter | `SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_RateLimiter.py` |
| Risk Manager | `SpyderE_Risk/SpyderE01_RiskManager.py` |
| Validation Script | `SpyderQ_Scripts/validate_env.py` |

## 🧪 Testing

| Test Suite | Purpose |
|------------|---------|
| `SpyderT23_ClientPortal_Auth_Test.py` | OAuth authentication |
| `SpyderT24_ClientPortal_RateLimiter_Test.py` | Rate limiting |
| `SpyderT25_ClientPortal_Session_Test.py` | Session management |
| `SpyderT26_ClientPortal_RESTClient_Test.py` | REST API calls |
| `SpyderT27_ClientPortal_Integration_Test.py` | End-to-end workflows |

---

**Remember**: You're working with a financial trading system using OAuth 2.0 authentication. Precision, safety, and thorough testing are paramount. When in doubt, ask for clarification rather than making assumptions.
