import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env

def main():
    load_dotenv(REPO_ROOT / ".env")
    client = create_tradier_client_from_env()

    symbols = [
        "SPY260619P00690000",
        "SPY260619P00700000",
        "SPY260619C00770500",
        "SPY260619C00780500"
    ]

    print("--- Batch Request ---")
    batch_quotes = client.get_quotes(symbols)
    # Tradier get_quotes might return a list or a dict depending on implementation.
    # Assuming it returns a list of quote dicts or similar.
    for quote in batch_quotes:
        if quote:
            symbol = quote.get('symbol')
            bid = quote.get('bid')
            ask = quote.get('ask')
            last = quote.get('last')
            desc = quote.get('description')
            print(f"Symbol: {symbol}, Bid: {bid}, Ask: {ask}, Last: {last}, Description: {desc}")

    print("\n--- Individual Requests ---")
    for sym in symbols:
        individual_quotes = client.get_quotes([sym])
        for quote in individual_quotes:
            if quote:
                symbol = quote.get('symbol')
                bid = quote.get('bid')
                ask = quote.get('ask')
                last = quote.get('last')
                desc = quote.get('description')
                print(f"Symbol: {symbol}, Bid: {bid}, Ask: {ask}, Last: {last}, Description: {desc}")

if __name__ == "__main__":
    main()
