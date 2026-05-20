from pathlib import Path
import os
import sys

# Add current directory to path just in case
sys.path.append(os.getcwd())

from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
from Spyder.SpyderG_GUI.SpyderG17_PaperPositionResolver import restore_paper_spreads_from_positions

db_path = Path('data/spyder_paper.db')
if not db_path.exists():
    print(f"Error: Database not found at {db_path}")
    sys.exit(1)

db = TradingSessionDB(db_path=db_path)
positions = db.get_active_paper_open_positions()

restored_spreads, leftover_positions = restore_paper_spreads_from_positions(
    positions,
    default_lifecycle_state='MANAGED BY AI'
)

print(f'Active rows: {len(positions)}')
print(f'Restored spreads: {len(restored_spreads)}')
print(f'Leftover rows: {len(leftover_positions)}')

for i, spread in enumerate(restored_spreads):
    # The prompt asks for the raw 'legs' list from the returned dict
    legs = spread.get('legs') if isinstance(spread, dict) else getattr(spread, 'legs', 'N/A')
    print(f'Spread {i+1} legs: {legs}')
