📋 **Complete Ticker List for IBKR Support**

The document `IBKR_ticker_symbols_list.md` contains:

### **🎯 Core Requirements (150+ symbols):**
- **ETFs & Indices:** SPY, QQQ, DIA, IWM, VIX, etc.
- **Sector ETFs:** All 11 SPDR sectors (XLF, XLE, XLK, etc.)
- **International:** EEM, FXI
- **Fixed Income:** TLT, LQD, HYG
- **Commodities:** GLD, SLV, DXY
- **Tech Stocks:** AAPL, MSFT, GOOGL, NVDA, TSLA, etc.

### **📊 Market Data Indicators:**
- **Market Internals:** $TICK, $TRIN, $ADD, $VOLD
- **Options Flow:** CPC, PCALL, VUD
- **Custom Metrics:** SKEW, GEX, DEX, DIX, OGL, SWAN

### **📈 Options Requirements:**
- Options on all major ETFs (SPY, QQQ, IWM, VIX)
- Weekly and monthly expiration cycles
- All strike prices for primary instruments

## 🎯 **Key Points for IBKR:**

1. **Current Issue:** "API handshake timeouts despite correct Gateway configuration"
2. **Suspected Cause:** "Account-level API permissions not enabled"  
3. **System:** Spyder Autonomous Options Trading System v1.0
4. **Platform:** Ubuntu 25.04, IB Gateway 10.39, Python ib_async

## 📞 **When Contacting IBKR Support:**

**Say:** *"I'm running an automated trading system that needs API access. The IB Gateway is configured correctly and listening on port 4002, but I'm getting API handshake timeouts. I believe my account needs API permissions enabled. Here's the complete list of ticker symbols my system requires..."
