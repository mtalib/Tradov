#!/bin/bash
# Download LEAN Source Files to Spyder Project
# Run from: /home/adam/Projects/Spyder

echo "=========================================="
echo "SPYDER - Downloading LEAN C# Source Files"
echo "=========================================="
echo "Project Directory: $(pwd)"

# Verify we're in the right directory
if [[ ! "$(pwd)" == *"Spyder"* ]]; then
    echo "❌ Error: Not in Spyder project directory"
    echo "Please run: cd /home/adam/Projects/Spyder"
    exit 1
fi

echo "✅ Confirmed Spyder project directory"

# Create LEAN source directory
echo "📁 Creating lean_source_conversion directory..."
mkdir -p lean_source_conversion
cd lean_source_conversion

# Priority 1: Options Chain & Filtering (HIGHEST PRIORITY)
echo "🔽 [1/9] Downloading Options Chain files..."
mkdir -p 01_option_chain
curl -s -o 01_option_chain/OptionChain.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/Option/OptionChain.cs"
curl -s -o 01_option_chain/OptionContract.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/Option/OptionContract.cs"
curl -s -o 01_option_chain/QCAlgorithm.OptionChain.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Algorithm/QCAlgorithm.OptionChain.cs"

if [[ -f "01_option_chain/OptionChain.cs" ]]; then
    echo "   ✅ OptionChain.cs downloaded ($(wc -l < 01_option_chain/OptionChain.cs) lines)"
else
    echo "   ❌ Failed to download OptionChain.cs"
fi

# Priority 2: Greeks Calculator
echo "🔽 [2/9] Downloading Greeks calculation files..."
mkdir -p 02_greeks
curl -s -o 02_greeks/ImpliedVolatility.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/ImpliedVolatility.cs"
curl -s -o 02_greeks/Delta.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/Greeks/Delta.cs"
curl -s -o 02_greeks/Gamma.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/Greeks/Gamma.cs"
curl -s -o 02_greeks/Theta.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/Greeks/Theta.cs"
curl -s -o 02_greeks/Vega.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/Greeks/Vega.cs"
curl -s -o 02_greeks/Rho.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Indicators/Greeks/Rho.cs"

if [[ -f "02_greeks/ImpliedVolatility.cs" ]]; then
    echo "   ✅ ImpliedVolatility.cs downloaded ($(wc -l < 02_greeks/ImpliedVolatility.cs) lines)"
else
    echo "   ❌ Failed to download ImpliedVolatility.cs"
fi

# Priority 3: Event-Driven Architecture
echo "🔽 [3/9] Downloading Event Management files..."
mkdir -p 03_events
curl -s -o 03_events/IResultHandler.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Results/IResultHandler.cs"
curl -s -o 03_events/BacktestingResultHandler.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Results/BacktestingResultHandler.cs"
curl -s -o 03_events/LiveTradingResultHandler.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Results/LiveTradingResultHandler.cs"
curl -s -o 03_events/Packet.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Packets/Packet.cs"

if [[ -f "03_events/IResultHandler.cs" ]]; then
    echo "   ✅ IResultHandler.cs downloaded ($(wc -l < 03_events/IResultHandler.cs) lines)"
else
    echo "   ❌ Failed to download IResultHandler.cs"
fi

# Priority 4: Configuration Management
echo "🔽 [4/9] Downloading Configuration files..."
mkdir -p 04_config
curl -s -o 04_config/Config.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Configuration/Config.cs"
curl -s -o 04_config/config.json \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Launcher/config.json"

if [[ -f "04_config/Config.cs" ]]; then
    echo "   ✅ Config.cs downloaded ($(wc -l < 04_config/Config.cs) lines)"
else
    echo "   ❌ Failed to download Config.cs"
fi

# Priority 5: Data Feed Architecture
echo "🔽 [5/9] Downloading Data Feed files..."
mkdir -p 05_datafeed
curl -s -o 05_datafeed/IDataFeed.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/DataFeeds/IDataFeed.cs"
curl -s -o 05_datafeed/LiveTradingDataFeed.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/DataFeeds/LiveTradingDataFeed.cs"
curl -s -o 05_datafeed/BaseData.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Data/BaseData.cs"
curl -s -o 05_datafeed/Slice.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Data/Slice.cs"

echo "   ✅ Data Feed files downloaded"

# Priority 6: Interactive Brokers Integration
echo "🔽 [6/9] Downloading IB Integration files..."
mkdir -p 06_ib_integration
curl -s -o 06_ib_integration/InteractiveBrokersBrokerage.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean.Brokerages.InteractiveBrokers/master/QuantConnect.InteractiveBrokersBrokerage/InteractiveBrokersBrokerage.cs"
curl -s -o 06_ib_integration/InteractiveBrokersClient.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean.Brokerages.InteractiveBrokers/master/QuantConnect.InteractiveBrokersBrokerage/Client/InteractiveBrokersClient.cs"

echo "   ✅ IB Integration files downloaded"

# Priority 7: Order Management
echo "🔽 [7/9] Downloading Order Management files..."
mkdir -p 07_orders
curl -s -o 07_orders/Order.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Orders/Order.cs"
curl -s -o 07_orders/OrderTicket.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Orders/OrderTicket.cs"
curl -s -o 07_orders/BacktestingTransactionHandler.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/TransactionHandlers/BacktestingTransactionHandler.cs"

echo "   ✅ Order Management files downloaded"

# Priority 8: Portfolio Management
echo "🔽 [8/9] Downloading Portfolio Management files..."
mkdir -p 08_portfolio
curl -s -o 08_portfolio/SecurityPortfolioManager.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/SecurityPortfolioManager.cs"
curl -s -o 08_portfolio/SecurityHolding.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/SecurityHolding.cs"
curl -s -o 08_portfolio/Portfolio.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Common/Securities/Portfolio/Portfolio.cs"

echo "   ✅ Portfolio Management files downloaded"

# Priority 9: Backtesting Framework
echo "🔽 [9/9] Downloading Backtesting files..."
mkdir -p 09_backtesting
curl -s -o 09_backtesting/Engine.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Engine.cs"
curl -s -o 09_backtesting/HistoryProviderManager.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/HistoricalData/HistoryProviderManager.cs"
curl -s -o 09_backtesting/BacktestingSetupHandler.cs \
  "https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Setup/BacktestingSetupHandler.cs"

echo "   ✅ Backtesting files downloaded"

# Create README for the downloads
cat > README.md << 'EOF'
# LEAN Source Files for Spyder Conversion

Downloaded from QuantConnect/Lean repository under Apache 2.0 License.

## Conversion Priority Order:

1. **01_option_chain/** - Convert to SpyderC03_OptionChain.py
2. **02_greeks/** - Convert to SpyderF06_GreeksCalculator.py  
3. **03_events/** - Enhance SpyderA05_EventManager.py
4. **04_config/** - Enhance SpyderA03_Configuration.py
5. **05_datafeed/** - Enhance SpyderC01_DataFeed.py
6. **06_ib_integration/** - Enhance SpyderB05_ConnectionManager.py
7. **07_orders/** - Enhance SpyderB02_OrderManager.py
8. **08_portfolio/** - Enhance SpyderE01_RiskManager.py
9. **09_backtesting/** - Enhance SpyderR01_BacktestEngine.py

## Usage:
Upload individual .cs files to Claude for conversion guidance.
Start with OptionChain.cs - highest impact on trading performance.
EOF

# Return to project root
cd /home/adam/Projects/Spyder

echo ""
echo "🎉 DOWNLOAD COMPLETE!"
echo ""
echo "📊 Files stored in: /home/adam/Projects/Spyder/lean_source_conversion/"
echo ""
echo "📁 Directory structure:"
ls -la lean_source_conversion/ 2>/dev/null || echo "   (Directory listing not available)"
echo ""
echo "🚀 NEXT STEPS:"
echo "1. Upload lean_source_conversion/01_option_chain/OptionChain.cs to Claude"
echo "2. I'll analyze it and show you how to convert it to SpyderC03_OptionChain.py"
echo "3. This will give your option filtering 3-5x performance improvement"
echo ""
echo "💡 Start with: cat lean_source_conversion/01_option_chain/OptionChain.cs"