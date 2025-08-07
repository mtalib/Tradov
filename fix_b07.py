# Create a proper fix file
#cat > /tmp/fix_b07.py << 'EOF'
#!/usr/bin/env python3
"""Fix for B07 to use ib_insync properly"""

from ib_insync import Stock, Index, Future, Option, Forex, Contract

# Market data configurations using ib_insync contract style
MARKET_DATA_CONFIG = {
    'SPY': lambda: Stock('SPY', 'SMART', 'USD'),
    'SPX': lambda: Index('SPX', 'CBOE'),
    '/ES': lambda: Future('ES', '202503', 'CME'),  # March 2025
    'VIX': lambda: Index('VIX', 'CBOE'),
    'QQQ': lambda: Stock('QQQ', 'SMART', 'USD'),
    'IWM': lambda: Stock('IWM', 'SMART', 'USD'),
    'DIA': lambda: Stock('DIA', 'SMART', 'USD'),
}

def create_contract(symbol: str) -> Contract:
    """Create ib_insync contract for symbol"""
    if symbol in MARKET_DATA_CONFIG:
        return MARKET_DATA_CONFIG[symbol]()
    else:
        # Default to stock
        return Stock(symbol, 'SMART', 'USD')
EOF
