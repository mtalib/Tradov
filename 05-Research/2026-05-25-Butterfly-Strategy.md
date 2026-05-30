Here is a complete, modular implementation designed to be dropped into your existing application structure. It uses QRunnable and QThreadPool to handle the Tradier API calls asynchronously.

Prerequisites
You will need the requests library if you haven't already installed it.

bash

pip install requests
The Python Module (butterfly_strategy.py)
This file contains the logic to interact with Tradier and construct the Butterfly spread. It is designed as a "Worker" that runs in the background.

python

            # 4. Construct Legs
            # Long Call Butterfly: 
            # Buy 1 Lower Call (Debit)
            # Sell 2 ATM Calls (Credit)
            # Buy 1 Upper Call (Debit)
            
            legs = [
                {'symbol': calls[lower_strike], 'side': 'buy_to_open', 'quantity': qty},
                {'symbol': calls[atm_strike],   'side': 'sell_to_open', 'quantity': qty * 2},
                {'symbol': calls[upper_strike], 'side': 'buy_to_open', 'quantity': qty}
            ]
            
            self.signals.log.emit("Legs constructed. Calculating limit price...")

            # 5. Estimate Limit Price
            # This is a simplification. Real apps need real-time quotes per leg.
            # We fetch quotes for the specific options to estimate the debit.
            # For now, we use a conservative approach: Mid-price estimation logic would go here.
            # Since we don't have individual quotes in this simplified chain call, 
            # we will set a limit price slightly higher than theoretical max profit width to ensure fill,
            # or ideally calculate real pricing.
            
            # NOTE: For a real live order, fetch quotes for the 3 symbols above.
            # Calculating a reasonable debit (e.g., 0.50 debit):
            limit_price = 0.50 
            
            self.signals.log.emit(f"Submitting order: Debit ${limit_price}")
            
            # 6. Place Order
            if self.config.get('dry_run', True):
                self.signals.finished.emit(f"DRY RUN: Would place order for {symbol} Butterfly.\nLegs: {[l['symbol'] for l in legs]}")
            else:
                result = self.client.place_multileg_order(legs, limit_price, order_type='debit')
                self.signals.finished.emit(f"Order Placed! ID: {result.get('order', {}).get('id')}")

        except Exception as e:
            self.signals.error.emit(f"Strategy Error: {str(e)}")


# --- Helper Function for Integration ---
def execute_butterfly_strategy(parent_widget, api_key, account_id, sandbox=True):
    """
    Example function to wire this up into your main GUI window.
    """
    # 1. Setup Client
    client = TradierClient(api_key, account_id, sandbox=sandbox)
    
    # 2. Define Config
    config = {
        'symbol': 'SPY',
        'wing_width': 1.0, # $1 width wings
        'quantity': 1,
        'dry_run': True    # SET TO FALSE TO TRADE LIVE
    }
    
    # 3. Create Worker
    worker = ButterflyWorker(client, config)
    
    # 4. Connect Signals to your GUI slots (Example)
    worker.signals.log.connect(lambda msg: print(f"[LOG] {msg}")) # Replace with GUI status bar update
    worker.signals.error.connect(lambda msg: print(f"[ERR] {msg}")) # Replace with GUI popup
    worker.signals.finished.connect(lambda msg: print(f"[DONE] {msg}"))
    
    # 5. Start Thread
    QThreadPool.globalInstance().start(worker)
Integration Guide
Since you already have an application, here is how to integrate the code above.

1. Main Window Integration Example
In your main GUI file (e.g., main_window.py), you would add a button or menu action to trigger the strategy.

python

from PySide6.QtWidgets import QMainWindow, QPushButton, QTextEdit, QMessageBox
# Import the module created above
from butterfly_strategy import execute_butterfly_strategy

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ... your existing UI setup ...
        
        self.btn_trade = QPushButton("Execute 0DTE Butterfly", self)
        self.btn_trade.clicked.connect(self.on_start_butterfly)
        
        # Example placeholders for credentials
        # In reality, load these from a secure config file or environment variables
        self.api_key = "YOUR_TRADIER_ACCESS_TOKEN"
        self.account_id = "YOUR_ACCOUNT_ID"

    def on_start_butterfly(self):
        # Connect the logic
        # We pass 'self' if the worker needs to reference GUI elements, 
        # or just call the helper function.
        
        # Note: You should implement a 'log' slot to display output in your GUI
        # rather than printing to console.
        execute_butterfly_strategy(
            parent_widget=self,
            api_key=self.api_key,
            account_id=self.account_id,
            sandbox=True # Always test in Sandbox first!
        )
Key Technical Details for Ubuntu/Wayland/PySide6
Threading (QRunnable): Wayland and Qt are strict about not blocking the main GUI thread. The ButterflyWorker ensures that the HTTP requests to Tradier happen in the background, keeping your UI responsive.
Tradier Sandbox: The code defaults to sandbox=True. This is critical for testing algorithmic strategies. Tradier's sandbox environment is excellent for verifying order construction without risking capital.
Multileg Orders: Tradier handles complex options strategies via the multileg order class. The script builds the specific parameter structure (option_symbol[0], side[0], etc.) required for a Butterfly.
Legs:
Buy 1 Lower Strike Call
Sell 2 ATM Strike Calls
Buy 1 Upper Strike Call
Limit Price: Tradier requires a limit price for multileg orders. The script currently has a placeholder (0.50). You must implement logic to fetch the bid/ask for the individual legs and calculate a fair debit price, or the order might be rejected if the limit is too low or rejected as "market orders not supported" for complex options.
How to Run
Save the logic code as butterfly_strategy.py.
Ensure your main application file imports execute_butterfly_strategy.
Bind it to a UI event.
Run your application on Ubuntu. Click the button, and check your console/logs for the [LOG] outputs.
