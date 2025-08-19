
# Timezone Helper for Spyder (add to utilities)
import pytz
from datetime import datetime

class SpyderTimezoneHelper:
    """Timezone conversion helper for IBKR data."""
    
    def __init__(self):
        self.server_tz = pytz.timezone('Europe/Zurich')  # IBKR server
        self.market_tz = pytz.timezone('US/Eastern')     # US market
        self.utc = pytz.UTC
    
    def ibkr_to_utc(self, timestamp):
        """Convert IBKR timestamp to UTC."""
        if timestamp.tzinfo is None:
            # Assume server timezone
            aware_ts = self.server_tz.localize(timestamp)
        else:
            aware_ts = timestamp
        return aware_ts.astimezone(self.utc)
    
    def utc_to_market_time(self, utc_timestamp):
        """Convert UTC to US market time."""
        return utc_timestamp.astimezone(self.market_tz)
    
    def is_data_fresh(self, timestamp, max_age_seconds=60):
        """Check if data is fresh (timezone-aware)."""
        utc_timestamp = self.ibkr_to_utc(timestamp)
        now_utc = datetime.now(self.utc)
        age = (now_utc - utc_timestamp).total_seconds()
        return age <= max_age_seconds
    
    def format_for_display(self, timestamp, local_tz='Europe/Lisbon'):
        """Format timestamp for display in user's timezone."""
        utc_ts = self.ibkr_to_utc(timestamp)
        local_tz_obj = pytz.timezone(local_tz)
        local_ts = utc_ts.astimezone(local_tz_obj)
        return local_ts.strftime('%H:%M:%S %Z')

# Usage example:
# tz_helper = SpyderTimezoneHelper()
# fresh_data = tz_helper.is_data_fresh(ticker.time)
# display_time = tz_helper.format_for_display(ticker.time)
