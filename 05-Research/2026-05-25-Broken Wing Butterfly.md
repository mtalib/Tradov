A **Broken Wing Butterfly (BWB)** is an advanced variation of the standard butterfly. The key difference is that the "wings" are set at different distances from the body (the short strikes).

*   **Standard Butterfly:** Symmetric risk. No initial cost (or small debit) usually.
*   **Broken Wing Butterfly:** Asymmetric risk. It is typically structured to enter for a **Net Credit** (you get paid to enter). This is achieved by selling a "closer" wing and buying a "further" wing.

Below is the implementation for a **0DTE Put Broken Wing Butterfly**. This is a common strategy for 0DTE because it profits if the market stays flat or rises (bullish/neutral bias) and you collect premium upfront.

### The Python Module (`bwb_strategy.py`)

You can append this to your existing strategy file or create a new module. It reuses the `TradierClient` from the previous example.

```python
import datetime
from PySide6.QtCore import QObject, Signal, QRunnable
# Assuming TradierClient is in the same file or imported
# from your_module import TradierClient 

class BrokenWingButterflyWorker(QRunnable):
    """
    Executes a 0DTE Broken Wing Butterfly (Put).
    
    Structure:
    - Buy 1 Put (Lower Wing - Further OTM)
    - Sell 2 Puts (Body - ATM/OTM)
    - Buy 1 Put (Upper Wing - Closer to Body)
    
    Goal: Enter for a Net Credit.
    """
    class Signals(QObject):
        finished = Signal(str)
        error = Signal(str)
        log = Signal(str)

    def __init__(self, client, config: dict):
        super().__init__()
        self.client = client
        self.config = config
        self.signals = self.Signals()
        self.setAutoDelete(True)

    def run(self):
        symbol = self.config.get('symbol', 'SPY')
        # Widths define the "Broken" aspect.
        # Upper_Width: Distance from Body to Upper Wing (The bought Put closer to money)
        # Lower_Width: Distance from Body to Lower Wing (The bought Put further out)
        # Usually Upper_Width < Lower_Width to generate Credit.
        upper_width = self.config.get('upper_width', 1.0) 
        lower_width = self.config.get('lower_width', 3.0) 
        qty = self.config.get('quantity', 1)
        
        try:
            self.signals.log.emit(f"[BWB] Fetching quote for {symbol}...")
            spot_price = self.client.get_quote(symbol)
            self.signals.log.emit(f"[BWB] Spot Price: {spot_price}")

            # 1. Determine Expiration (Today)
            today = datetime.date.today().strftime("%Y-%m-%d")

            # 2. Define Strikes
            # For a Put BWB, we usually center the "Body" slightly OTM (below spot)
            # to be safe/bullish.
            # Body Strike: Slightly below current price (e.g., 1 strike OTM)
            
            # Rounding to nearest integer for SPY (Assuming $1 strikes)
            # In production, you'd check the option chain for valid strike increments (0.5 vs 1.0)
            body_strike = round(spot_price) - 1.0 
            
            upper_wing_strike = body_strike + upper_width # Closer to money
            lower_wing_strike = body_strike - lower_width # Further OTM

            self.signals.log.emit(f"Strikes -> Upper: {upper_wing_strike} | Body: {body_strike} | Lower: {lower_wing_strike}")

            # 3. Fetch Chain
            self.signals.log.emit("[BWB] Fetching Option Chain...")
            chain = self.client.get_option_chain(symbol, today)
            
            # Map Puts
            puts = {float(opt['strike']): opt['symbol'] for opt in chain if opt['option_type'] == 'put'}

            required_strikes = [upper_wing_strike, body_strike, lower_wing_strike]
            for s in required_strikes:
                if s not in puts:
                    raise ValueError(f"Strike {s} not found in today's chain.")

            # 4. Construct Legs
            # Order matters for Tradier API, but logic is:
            # BUY 1 Upper Wing (Closer)
            # SELL 2 Body
            # BUY 1 Lower Wing (Further)
            
            legs = [
                {'symbol': puts[upper_wing_strike], 'side': 'buy_to_open',  'quantity': qty},
                {'symbol': puts[body_strike],        'side': 'sell_to_open', 'quantity': qty * 2},
                {'symbol': puts[lower_wing_strike],  'side': 'buy_to_open',  'quantity': qty}
            ]
            
            self.signals.log.emit("Legs constructed. Calculating Net Credit...")

            # 5. Estimate Limit Price (The Credit)
            # In a real app, fetch bid/ask for each leg:
            # Credit = (2 * Bid_Body) - Ask_Upper - Ask_Lower
            # Since we don't have detailed quotes here, we aim for a reasonable credit.
            # Example: Aim for $0.20 credit per share.
            limit_price = 0.20
            
            # For a Credit order, Tradier expects positive price? 
            # No, order type is 'credit', limit price is the minimum credit you want to collect.
            
            self.signals.log.emit(f"Targeting Net Credit: ${limit_price}")

            # 6. Place Order
            if self.config.get('dry_run', True):
                msg = f"DRY RUN SUCCESS\nStructure: Put BWB\nCredit: ${limit_price}"
                self.signals.finished.emit(msg)
            else:
                self.signals.log.emit("Placing Live Order...")
                # Note: Order type is 'credit' for BWB
                result = self.client.place_multileg_order(legs, limit_price, order_type='credit')
                self.signals.finished.emit(f"Order Placed! ID: {result.get('order', {}).get('id')}")

        except Exception as e:
            self.signals.error.emit(f"BWB Error: {str(e)}")


# --- Integration Function ---

def execute_bwb_strategy(parent_widget, client, sandbox=True):
    """
    Helper to launch the BWB worker.
    """
    config = {
        'symbol': 'SPY',
        'upper_width': 1.0,   # Distance from Body to Upper Wing
        'lower_width': 3.0,   # Distance from Body to Lower Wing (Wider = More Credit usually)
        'quantity': 1,
        'dry_run': True
    }

    worker = BrokenWingButterflyWorker(client, config)
    
    # Connect signals (Update these to point to your GUI status widgets)
    worker.signals.log.connect(lambda msg: print(f"[BWB LOG] {msg}"))
    worker.signals.error.connect(lambda msg: print(f"[BWB ERR] {msg}"))
    worker.signals.finished.connect(lambda msg: print(f"[BWB DONE] {msg}"))
    
    from PySide6.QtCore import QThreadPool
    QThreadPool.globalInstance().start(worker)
```

### How to Integrate into your Main Window

You can add a new button to your PySide6 GUI to trigger this specific strategy.

```python
# Inside your MainWindow class

def setup_buttons(self):
    # ... existing buttons ...
    
    self.btn_bwb = QPushButton("Launch 0DTE BWB (Put)", self)
    self.btn_bwb.clicked.connect(self.on_launch_bwb)

def on_launch_bwb(self):
    # Use the client initialized in the previous step
    # Assuming self.client is an instance of TradierClient
    
    print("Starting Broken Wing Butterfly Worker...")
    execute_bwb_strategy(self, self.client, sandbox=True)
```

### Key Differences in the Code

1.  **Strike Selection Logic**:
    *   The script calculates `body_strike` slightly below the current price (`round(spot) - 1`). This makes the strategy **Bullish/Neutral** (best case: market stays flat or rises, puts expire worthless, you keep the credit).
2.  **Wing Widths**:
    *   `upper_width = 1.0` (Narrower)
    *   `lower_width = 3.0` (Wider)
    *   This asymmetry allows you to sell the expensive body strikes and buy cheaper wings, resulting in a **Net Credit**.
3.  **Order Type**:
    *   Changed to `order_type='credit'`. Tradier requires you to specify the amount of credit you want to collect.
4.  **Leg Construction**:
    *   The quantities (1x2x1) remain the same, but the distances vary, creating the "Broken Wing" profile.

### Important Note on Pricing
In the `run` method, `limit_price = 0.20` is a hardcoded placeholder.
For a production bot, you **must** fetch the bid/ask for the three specific options:
*   `Credit Received = (Bid of Body * 2) - Ask of Upper Wing - Ask of Lower Wing`
*   You typically place the limit order slightly below this theoretical value to ensure execution (e.g., 0.05 or 0.10 less than the midpoint).
