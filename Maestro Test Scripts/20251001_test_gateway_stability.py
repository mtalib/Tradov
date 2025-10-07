#!/usr/bin/env python3
"""
IB Gateway Connection Stability Monitor
Investigate the "Gateway death" issue - connections dying after a few minutes
"""

import sys
import time
import asyncio
from datetime import datetime, timedelta
import threading

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB

    print("✅ Using ib_async 1.0.3 for Gateway 10.37 compatibility")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


class GatewayConnectionMonitor:
    """Monitor Gateway connection stability over time"""

    def __init__(self):
        self.ib = IB()
        self.client_id = 999  # Unique client ID for monitoring
        self.connection_start = None
        self.heartbeat_interval = 30  # Check every 30 seconds
        self.connection_events = []
        self.is_monitoring = False

    async def monitor_connection_stability(self, duration_minutes=10):
        """Monitor connection stability for specified duration"""
        print(f"🔍 GATEWAY CONNECTION STABILITY MONITOR")
        print(f"📅 Started: {datetime.now()}")
        print(f"⏱️  Duration: {duration_minutes} minutes")
        print(f"💓 Heartbeat interval: {self.heartbeat_interval} seconds")
        print("=" * 60)

        try:
            # Initial connection
            print(f"🔌 Connecting to Gateway...")
            await self.ib.connectAsync(
                host="127.0.0.1", port=4002, clientId=self.client_id, timeout=60
            )

            self.connection_start = datetime.now()
            self.log_event("CONNECTION_ESTABLISHED", "Initial connection successful")
            print(f"✅ Connected at {self.connection_start}")

            # Get initial account info
            accounts = self.ib.managedAccounts()
            self.log_event("ACCOUNTS_RETRIEVED", f"Accounts: {accounts}")

            self.is_monitoring = True
            end_time = self.connection_start + timedelta(minutes=duration_minutes)

            # Monitor connection health
            while datetime.now() < end_time and self.is_monitoring:
                try:
                    # Check connection status
                    is_connected = self.ib.isConnected()
                    uptime = datetime.now() - self.connection_start

                    if is_connected:
                        # Test heartbeat - try to get accounts again
                        try:
                            accounts = self.ib.managedAccounts()
                            status = f"✅ ALIVE - Uptime: {self.format_duration(uptime)} - Accounts: {accounts}"
                            self.log_event("HEARTBEAT_SUCCESS", status)
                            print(f"{datetime.now().strftime('%H:%M:%S')} | {status}")
                        except Exception as heartbeat_error:
                            status = f"⚠️  HEARTBEAT_FAILED - {str(heartbeat_error)}"
                            self.log_event("HEARTBEAT_FAILED", status)
                            print(f"{datetime.now().strftime('%H:%M:%S')} | {status}")
                    else:
                        status = f"❌ CONNECTION_LOST - Uptime was: {self.format_duration(uptime)}"
                        self.log_event("CONNECTION_LOST", status)
                        print(f"{datetime.now().strftime('%H:%M:%S')} | {status}")
                        break

                    # Wait for next heartbeat
                    await asyncio.sleep(self.heartbeat_interval)

                except Exception as monitor_error:
                    self.log_event(
                        "MONITOR_ERROR", f"Monitor error: {str(monitor_error)}"
                    )
                    print(f"❌ Monitor error: {monitor_error}")
                    break

            # Final status
            if self.ib.isConnected():
                final_uptime = datetime.now() - self.connection_start
                self.log_event(
                    "MONITOR_COMPLETED",
                    f"Connection survived {self.format_duration(final_uptime)}",
                )
                print(
                    f"\n🎉 SUCCESS! Connection survived {self.format_duration(final_uptime)}"
                )
            else:
                self.log_event("CONNECTION_DIED", "Connection died during monitoring")
                print(f"\n💀 CONNECTION DIED during monitoring")

        except Exception as e:
            self.log_event("CONNECTION_FAILED", f"Initial connection failed: {str(e)}")
            print(f"❌ Connection failed: {e}")

        finally:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
                    self.log_event("DISCONNECTED", "Clean disconnection")
                    print(f"🔌 Disconnected cleanly")
            except:
                pass

            self.print_summary()

    def log_event(self, event_type, description):
        """Log connection event with timestamp"""
        timestamp = datetime.now()
        uptime = (
            (timestamp - self.connection_start)
            if self.connection_start
            else timedelta(0)
        )

        event = {
            "timestamp": timestamp,
            "uptime": uptime,
            "event_type": event_type,
            "description": description,
        }
        self.connection_events.append(event)

    def format_duration(self, duration):
        """Format duration as human readable"""
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"

    def print_summary(self):
        """Print detailed connection event summary"""
        print(f"\n" + "=" * 60)
        print(f"📊 CONNECTION STABILITY REPORT")
        print(f"=" * 60)

        if not self.connection_events:
            print("❌ No connection events recorded")
            return

        total_duration = (
            self.connection_events[-1]["uptime"]
            if self.connection_events
            else timedelta(0)
        )
        print(f"⏱️  Total monitoring duration: {self.format_duration(total_duration)}")
        print(f"📈 Total events: {len(self.connection_events)}")

        # Count event types
        event_counts = {}
        for event in self.connection_events:
            event_type = event["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        print(f"\n📋 Event Summary:")
        for event_type, count in event_counts.items():
            print(f"   {event_type}: {count}")

        # Show timeline
        print(f"\n⏰ Event Timeline:")
        for event in self.connection_events:
            uptime_str = self.format_duration(event["uptime"])
            print(
                f"   {event['timestamp'].strftime('%H:%M:%S')} [{uptime_str:>8}] {event['event_type']}: {event['description']}"
            )

        # Analysis
        print(f"\n🔍 Analysis:")
        heartbeat_successes = event_counts.get("HEARTBEAT_SUCCESS", 0)
        heartbeat_failures = event_counts.get("HEARTBEAT_FAILED", 0)

        if heartbeat_successes > 0:
            success_rate = (
                heartbeat_successes / (heartbeat_successes + heartbeat_failures)
            ) * 100
            print(f"   💓 Heartbeat success rate: {success_rate:.1f}%")

        if "CONNECTION_LOST" in event_counts:
            print(f"   💀 Connection died during monitoring - ISSUE CONFIRMED")
        elif "CONNECTION_DIED" in event_counts:
            print(f"   💀 Connection died during monitoring - ISSUE CONFIRMED")
        else:
            print(f"   ✅ Connection remained stable throughout monitoring")


async def main():
    """Run the Gateway connection stability test"""
    print("🔍 Investigating IB Gateway 'death' after a few minutes...")
    print("This will help us understand if it's a heartbeat issue or something else")

    monitor = GatewayConnectionMonitor()

    # Monitor for 10 minutes to see if connection dies
    await monitor.monitor_connection_stability(duration_minutes=10)

    print(f"\n💡 Next steps based on results:")
    print(f"   • If connection dies: Investigate heartbeat/keepalive settings")
    print(f"   • If connection survives: Issue may be specific to dashboard usage")
    print(f"   • Look for patterns in event timeline")


if __name__ == "__main__":
    asyncio.run(main())
