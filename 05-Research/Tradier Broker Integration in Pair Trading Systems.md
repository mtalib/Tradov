# Tradier Broker Integration in Pair Trading Systems

This document summarizes the integration status of Tradier Brokerage with various pair trading and algorithmic trading platforms, providing insights for the development of the HEDGER platform.

## 1. Dedicated Pair Trading Platforms

Dedicated commercial pair trading platforms, such as PairTrade Finder® and Pair Trading Lab, primarily focus their automated trading capabilities on Interactive Brokers.

### 1.1. PairTrade Finder®

PairTrade Finder® (PTF) is designed to integrate directly with **Interactive Brokers (IBKR)** for automated trading into the IB Trader Workstation. While PTF offers sophisticated pair selection and analysis, its core autotrading functionality is tied to IBKR [1]. There is no explicit mention or support for Tradier integration within their documentation or feature lists.

### 1.2. Pair Trading Lab (PTL Trader)

Similarly, Pair Trading Lab's automated trading application, PTL Trader, explicitly states that it currently supports **only Interactive Brokers** [2]. This indicates that native Tradier integration is not available for PTL Trader.

## 2. Algorithmic Trading Frameworks with Tradier Support

While dedicated pair trading platforms may not directly support Tradier, several broader algorithmic trading frameworks and libraries offer robust integration with Tradier Brokerage, making them suitable for building a custom pair trading system like HEDGER.

### 2.1. QuantConnect

QuantConnect, an open-source algorithmic trading platform, provides comprehensive support for Tradier Brokerage. Its LEAN algorithmic trading engine is designed to be brokerage-agnostic, and a dedicated **Tradier plugin** allows users to deploy live trading algorithms directly to their Tradier accounts [3]. This means that any pair trading strategy developed within the QuantConnect environment can be executed via Tradier.

### 2.2. LumiBot

LumiBot is a Python library for algorithmic trading that offers native and well-documented support for Tradier. Its modular architecture allows for easy implementation of custom trading strategies, including pair trading, and seamless execution through Tradier. LumiBot provides clear instructions for configuring Tradier API credentials and running strategies with Tradier as the broker [4].

### 2.3. Other Platforms with Tradier Integration

Several other platforms and tools integrate with Tradier, which could potentially be leveraged for aspects of pair trading or general algorithmic trading:

*   **Option Alpha:** This platform supports fully automated trading for options and stocks and integrates with Tradier [5].
*   **TradingView:** Tradier has a partnership with TradingView, enabling users to trade directly from TradingView charts [6]. While not a pair trading platform itself, TradingView's charting and analysis tools could complement a custom HEDGER system.
*   **TradersPost:** This service allows users to automate strategies from platforms like TradingView and TrendSpider, sending orders to their Tradier accounts [7].

## 3. Conclusion for HEDGER

Based on the research, while existing dedicated pair trading applications do not natively support Tradier, the **Tradier API is well-supported by powerful open-source algorithmic trading frameworks like QuantConnect and LumiBot**. This is a significant advantage for HEDGER, as it means you can leverage these robust frameworks to build your custom pair trading logic and execute trades directly through your Tradier account. The availability of native Python SDKs and comprehensive API documentation from Tradier further facilitates this integration.

## References

[1] PairTrade Finder®. (n.d.). *Leading Statistical Arbitrage Software for Online Traders*. Retrieved from [https://pairtradefinder.com/](https://pairtradefinder.com/)

[2] Pair Trading Lab. (n.d.). *Automated Trading*. Retrieved from [https://www.pairtradinglab.com/ptltrader](https://www.pairtradinglab.com/ptltrader)

[3] QuantConnect. (n.d.). *Tradier - QuantConnect.com*. Retrieved from [https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/tradier](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/tradier)

[4] LumiBot. (n.d.). *Tradier - Lumibot: Backtestable AI Agents and Python Algorithmic Trading*. Retrieved from [https://lumibot.lumiwealth.com/brokers.tradier.html](https://lumibot.lumiwealth.com/brokers.tradier.html)

[5] Option Alpha. (n.d.). *Broker Integrations*. Retrieved from [https://optionalpha.com/integrations](https://optionalpha.com/integrations)

[6] Tradier. (n.d.). *TradingView | Platforms*. Retrieved from [https://tradier.com/platforms/tradingview](https://tradier.com/platforms/tradingview)

[7] TradersPost. (n.d.). *Tradier Automated Trading Bots*. Retrieved from [https://traderspost.io/connections/tradier](https://traderspost.io/connections/tradier)
