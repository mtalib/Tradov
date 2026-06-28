TradovProject/Glossary.md (Complete)

```markdown
# Tradov Trading System - Glossary

## Trading & Financial Terms

### Pair Trading / Stat-Arb
- **Cointegration**: Statistical relationship indicating two price series move together over time
- **Hedge Ratio**: Relative sizing used to neutralize a spread between two assets
- **Mean Reversion**: Tendency of a spread or residual to move back toward its historical average
- **OU Process**: Ornstein-Uhlenbeck process, a mean-reverting stochastic model
- **Pair Key**: Canonical identifier for a tradable pair, usually `AAA/BBB`
- **Residual Spread**: Difference between observed spread and fitted fair-value spread
- **SSD**: Sum of squared distances, used to rank candidate pairs by similarity
- **Z-Score**: Standardized distance from the spread mean used for entries and exits
- **PCA Eigenportfolio**: Portfolio extracted from principal components for stat-arb signal generation
- **Stat-Arb**: Statistical arbitrage, trade signals derived from relative mispricing
- **SPY**: SPDR S&P 500 ETF Trust, a benchmark asset in this repo

### Market Data & Analysis
- **Ask**: Lowest price seller willing to accept
- **Bid**: Highest price buyer willing to pay
- **Bid-Ask Spread**: Difference between bid and ask prices
- **Dark Pool**: Private exchange for trading away from public order books
- **DIX**: Dark Index, measures dark pool buying vs selling pressure
- **GEX**: Gamma Exposure, market maker hedge flow indicator
- **Implied Volatility (IV)**: Market's expectation of future price volatility
- **Level II Data**: Market depth showing multiple bid/ask levels
- **Market Making**: Providing liquidity by continuously quoting bid/ask
- **Order Book**: List of buy and sell orders at different price levels
- **SKEW**: CBOE Skew Index, measures tail risk in S&P 500 markets
- **Tick**: Minimum price movement increment
- **Volume**: Number of shares/contracts traded
- **VIX**: CBOE Volatility Index, "fear gauge" of market

### Risk Management
- **Drawdown**: Peak-to-trough decline in account value
- **Max Drawdown**: Largest drawdown over a specific period
- **Position Sizing**: Determining appropriate trade size based on risk
- **Risk-Adjusted Return**: Return relative to risk taken (Sharpe ratio)
- **Risk Parity**: Equal risk contribution from each position
- **Sharpe Ratio**: Excess return per unit of volatility
- **Stop Loss**: Predetermined exit point to limit losses
- **Value at Risk (VaR)**: Maximum expected loss over given time period
- **Win Rate**: Percentage of profitable trades

## Technical Terms

### System Architecture
- **API (Application Programming Interface)**: Set of protocols for software communication
- **Asynchronous**: Non-blocking operations that don't wait for completion
- **Circuit Breaker**: Design pattern that prevents cascading failures
- **Event-Driven**: Architecture where components communicate via events
- **Microservices**: Architecture with small, independent services
- **Modular Design**: System composed of separate, interchangeable components
- **Observer Pattern**: Design pattern where objects notify subscribers of changes
- **Plugin Architecture**: System that allows adding features via plugins
- **Thread Pool**: Managed collection of threads for concurrent execution
- **Thread-Safe**: Code that functions correctly during simultaneous access

### Tradier & Databento Specific
- **Tradier API**: RESTful API used by Tradov for market data and execution connectivity
- **Bearer Token**: Authentication method for Tradier API requests
- **Databento**: Institutional-grade market data provider (OPRA feed)
- **OPRA.PILLAR**: Historical market-data channel identifier retained for reference
- **Paper Mode**: Simulated trading with the TradovBox local paper ledger while using live Tradier data
- **Account ID**: Unique identifier for Tradier trading account
- **Symbol**: Ticker symbol (e.g., SPY for S&P 500 ETF)
- **Tick Size**: Minimum price increment for an instrument

### Database & Storage
- **Cache**: High-speed data storage layer
- **Connection Pool**: Managed database connections for efficiency
- **Index**: Database structure to improve query performance
- **Normalization**: Database design to reduce redundancy
- **OLAP**: Online Analytical Processing for complex queries
- **OLTP**: Online Transaction Processing for day-to-day operations
- **Partitioning**: Dividing large tables into smaller, manageable pieces
- **Query Optimization**: Improving database query performance
- **SQLite**: Lightweight, file-based relational database
- **Time Series**: Data indexed by time, common in financial applications

### Programming & Development
- **Dependency Injection**: Design pattern for managing dependencies
- **Docstring**: Documentation string embedded in code
- **Exception Handling**: Managing and responding to runtime errors
- **Factory Pattern**: Creational design pattern for object creation
- **Logging**: Recording system events for debugging and monitoring
- **Mocking**: Creating fake objects for testing
- **Refactoring**: Improving code structure without changing functionality
- **Type Hints**: Annotations indicating expected data types
- **Unit Testing**: Testing individual components in isolation
- **Virtual Environment**: Isolated Python environment for dependencies

## Tradov-Specific Terms

### Module Series
- **A-Series (TradovA)**: Core system modules - orchestration and main entry
- **B-Series (TradovB)**: Broker integration modules - Tradier API connections and orders
- **C-Series (TradovC)**: Market data modules - real-time feeds and processing
- **D-Series (TradovD)**: Strategy modules - trading algorithm implementations
- **E-Series (TradovE)**: Risk management modules - position sizing and limits
- **F-Series (TradovF)**: Analysis modules - technical indicators and market analysis
- **G-Series (TradovG)**: GUI modules - user interface components
- **H-Series (TradovH)**: Storage modules - database and persistence
- **I-Series (TradovI)**: Integration modules - third-party service connections
- **J-Series (TradovJ)**: Alert modules - notifications and messaging
- **K-Series (TradovK)**: Report modules - performance analytics and reporting
- **L-Series (TradovL)**: Machine Learning modules - AI models and predictions
- **M-Series (TradovM)**: Monitoring modules - system health and metrics
- **N-Series (TradovN)**: Historical analytics modules retained for reference
- **O-Series (TradovO)**: Trading Intelligence modules - advanced analytics
- **P-Series (TradovP)**: Portfolio Management modules - optimization and allocation
- **Q-Series (TradovQ)**: Scripts - utility scripts and automation tools
- **R-Series (TradovR)**: Runtime modules - system execution and management
- **S-Series (TradovS)**: Signal modules - custom indicators and signals
- **T-Series (TradovT)**: Testing modules - unit tests and validation
- **U-Series (TradovU)**: Utility modules - shared functions and helpers
- **V-Series (TradovV)**: Quantitative Models - mathematical and statistical models
- **X-Series (TradovX)**: AI Agent modules - autonomous decision-making
- **Z-Series (TradovZ)**: Communication modules - inter-module messaging

### System Components
- **Event Manager**: Central coordinator for system events
- **Order Router**: Component that routes orders to appropriate destinations
- **Risk Engine**: System component that evaluates and manages risk
- **Strategy Engine**: Core component that executes trading strategies
- **Data Pipeline**: System for processing and distributing market data
- **Configuration Manager**: Component handling system settings and parameters

### Data Structures
- **Market Data**: Real-time price, volume, and order book information
- **Order Object**: Data structure representing a trade order
- **Position Object**: Data structure representing a market position
- **Portfolio Object**: Collection of positions and account information
- **Strategy State**: Current status and parameters of a trading strategy
- **Risk Metrics**: Calculated values representing portfolio risk

## Machine Learning & AI Terms

### Model Types
- **Ensemble Methods**: Combining multiple models for better predictions
- **LSTM (Long Short-Term Memory)**: Neural network for sequence data
- **Random Forest**: Ensemble method using multiple decision trees
- **Reinforcement Learning**: Learning through interaction with environment
- **Support Vector Machine (SVM)**: Classification and regression algorithm
- **Time Series Forecasting**: Predicting future values based on historical data

### Model Evaluation
- **Backtesting**: Testing strategy on historical data
- **Cross-Validation**: Method for assessing model generalization
- **Feature Engineering**: Creating input variables for machine learning
- **Hyperparameter Optimization**: Finding best model parameters
- **Overfitting**: Model too closely fitted to training data
- **Walk-Forward Analysis**: Sequential testing that avoids look-ahead bias

### Performance Metrics
- **Accuracy**: Percentage of correct predictions
- **F1 Score**: Harmonic mean of precision and recall
- **Mean Absolute Error (MAE)**: Average magnitude of prediction errors
- **Precision**: True positives / (True positives + False positives)
- **R-Squared**: Coefficient of determination, variance explained by model
- **Recall**: True positives / (True positives + False negatives)

## Environment & Infrastructure

### Operating System
- **GNOME**: Desktop environment for Linux
- **Ubuntu**: Linux distribution used for Tradov system
- **Virtual Environment**: Isolated Python runtime environment
- **Wayland**: Display server protocol replacing X11
- **systemd**: System and service manager for Linux

### Development Tools
- **Git**: Distributed version control system
- **pytest**: Python testing framework
- **PySide6**: Python binding for Qt6 GUI framework
- **Virtual Environment (.venv)**: Isolated Python dependency environment
- **VS Code**: Visual Studio Code integrated development environment

### Monitoring & Observability
- **Grafana**: Visualization platform for metrics and logs
- **Health Check**: Automated system status verification
- **Log Rotation**: Automatic archival and cleanup of log files
- **Metrics**: Quantitative measurements of system behavior
- **Prometheus**: Time-series database for monitoring data
- **Alerting**: Automated notification of system issues

## Regulatory & Compliance

### Trading Regulations
- **Best Execution**: Obligation to execute trades at best available price
- **Market Hours**: Official trading hours for exchanges
- **Pattern Day Trader (PDT)**: Rules for accounts with frequent day trading
- **Reg T**: Federal Reserve regulation governing margin accounts
- **Settlement**: Process of completing a trade transaction

### Risk Compliance
- **Audit Trail**: Complete record of all system activities
- **Know Your Customer (KYC)**: Customer identification requirements
- **Position Limits**: Maximum allowed position sizes
- **Risk Disclosure**: Required warnings about trading risks
- **Suitability**: Ensuring investments match customer profile

---

*This glossary is continuously updated as new terms and concepts are introduced to the Spyd
