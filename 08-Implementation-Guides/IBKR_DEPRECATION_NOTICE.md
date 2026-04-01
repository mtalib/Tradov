# 🚨 DEPRECATION NOTICE

**This documentation contains outdated references to Interactive Brokers (IBKR) and IB Gateway.**

## Migration Complete

As of **February 2026**, Spyder has fully migrated from IBKR to:
- **Tradier API** for order execution
- **Databento** for market data

## What This Means

- ❌ **IB Gateway** is no longer required or supported
- ❌ **ib_insync** / **ib_async** libraries are not used
- ❌ **TWS API** references are outdated
- ✅ Use **Tradier API** for all broker operations
- ✅ Use **Databento** for market data

## Updated Documentation

For current architecture and setup instructions, see:
- [Architecture.md](../01-Overview/Architecture.md) - Updated system architecture
- [IBKR_TO_TRADIER_MIGRATION_GUIDE.md](../09-Implementation-History/IBKR_TO_TRADIER_MIGRATION_GUIDE.md) - Complete migration guide
- [Technical Specifications-Tradier-Databento.md](../08-Implementation-Guides/Technical%20Specifications-Tradier-Databento.md) - Tradier/Databento specs

## Historical Context

This document is preserved for historical reference only. The information about IBKR integration is **no longer applicable** to current Spyder development.

---

*Last Updated: March 16, 2026*
