
# ET Time Display Helper for Spyder Dashboard
import pytz
from datetime import datetime

class ETTimeDisplay:
    '''Display ET time on dashboard regardless of local timezone.'''
    
    def __init__(self):
        self.et_tz = pytz.timezone('US/Eastern')
        self.utc_tz = pytz.UTC
    
    def get_et_time_string(self):
        '''Get current ET time as formatted string.'''
        et_now = datetime.now(self.et_tz)
        return et_now.strftime('%H:%M:%S %Z')
    
    def get_market_status(self):
        '''Get current market status based on ET time.'''
        et_now = datetime.now(self.et_tz)
        hour = et_now.hour
        minute = et_now.minute
        weekday = et_now.weekday()  # 0=Monday, 6=Sunday
        
        # Weekend check
        if weekday >= 5:  # Saturday or Sunday
            return 'WEEKEND', '🏖️'
        
        # Weekday market hours
        if hour < 9 or (hour == 9 and minute < 30):
            return 'PRE-MARKET', '🌅'
        elif 9 <= hour < 16 or (hour == 9 and minute >= 30):
            return 'MARKET OPEN', '🔔'
        elif 16 <= hour < 20:
            return 'AFTER-HOURS', '🌆'
        else:
            return 'MARKET CLOSED', '🌙'
    
    def format_for_dashboard(self):
        '''Format ET time and market status for dashboard display.'''
        et_time = self.get_et_time_string()
        status, icon = self.get_market_status()
        return f"{icon} {et_time} | {status}"

# Usage in Spyder Dashboard:
# et_display = ETTimeDisplay()
# dashboard_time_text = et_display.format_for_dashboard()
# # Result: "🔔 14:45:24 EDT | MARKET OPEN"
