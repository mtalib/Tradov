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
