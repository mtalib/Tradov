#!/usr/bin/env python3
"""
Gateway Health Monitor & Auto-Restart
Prevent and fix the "Gateway death after few minutes" issue
"""

import sys
import time
import asyncio
import subprocess
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional

sys.path.append("/home/adam/Projects/Spyder")

try:
    from ib_async import IB

    print("✅ Using ib_async 1.0.3 for health monitoring")
except ImportError as e:
    print(f"❌ Error importing ib_async: {e}")
    sys.exit(1)


class GatewayHealthMonitor:
    """Monitor Gateway health and auto-restart when needed"""

    def __init__(self):
        self.health_check_interval = 60  # Check every 60 seconds
        self.timeout_threshold = 3  # Consider dead after 3 failed checks
        self.consecutive_failures = 0
        self.gateway_process = None
        self.last_successful_check = None
        self.health_log = []

    def find_gateway_process(self):
        """Find the IB Gateway Java process"""
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info["name"] == "java" and proc.info["cmdline"]:
                        cmdline = " ".join(proc.info["cmdline"])
                        if "ibgateway" in cmdline.lower() and "install4j" in cmdline:
                            return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return None
        except Exception as e:
            print(f"Error finding Gateway process: {e}")
            return None

    async def check_gateway_health(self) -> bool:
        """Check if Gateway is responding to API requests"""
        test_client_id = 500  # Use unique client ID for health checks

        try:
            ib = IB()

            # Quick connection test with our proven 60s timeout
            await ib.connectAsync(
                host="127.0.0.1",
                port=4002,
                clientId=test_client_id,
                timeout=10,  # Use shorter timeout for health checks
            )

            # Test basic functionality
            accounts = ib.managedAccounts()

            # Clean disconnect
            ib.disconnect()

            if accounts:
                self.log_health_event(
                    "HEALTHY", f"Gateway responding - Accounts: {accounts}"
                )
                return True
            else:
                self.log_health_event(
                    "UNHEALTHY", "Gateway connected but no accounts returned"
                )
                return False

        except Exception as e:
            error_msg = str(e)
            self.log_health_event("UNHEALTHY", f"Health check failed: {error_msg}")
            return False

    def log_health_event(self, status: str, message: str):
        """Log health check event"""
        timestamp = datetime.now()
        event = {"timestamp": timestamp, "status": status, "message": message}
        self.health_log.append(event)

        # Keep only last 50 events
        if len(self.health_log) > 50:
            self.health_log = self.health_log[-50:]

        status_icon = "✅" if status == "HEALTHY" else "❌"
        print(f"{timestamp.strftime('%H:%M:%S')} | {status_icon} {status}: {message}")

    def kill_gateway_process(self):
        """Kill unresponsive Gateway process"""
        try:
            gateway_proc = self.find_gateway_process()
            if gateway_proc:
                print(
                    f"🔪 Killing unresponsive Gateway process (PID: {gateway_proc.pid})"
                )
                gateway_proc.kill()
                gateway_proc.wait(timeout=10)  # Wait up to 10 seconds for clean exit
                self.log_health_event(
                    "KILLED", f"Killed Gateway process PID: {gateway_proc.pid}"
                )
                return True
            else:
                self.log_health_event("NOT_FOUND", "Gateway process not found")
                return False
        except Exception as e:
            self.log_health_event("KILL_FAILED", f"Failed to kill Gateway: {e}")
            return False

    def restart_gateway(self):
        """Restart Gateway using IBC"""
        try:
            print("🔄 Restarting IB Gateway...")

            # Use the IBC startup script
            startup_script = "/home/adam/ibc/gatewaystart.sh"

            # Start Gateway in background
            process = subprocess.Popen(
                [startup_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd="/home/adam/ibc",
            )

            self.log_health_event(
                "RESTARTING", f"Gateway restart initiated (PID: {process.pid})"
            )

            # Wait a bit for Gateway to start
            time.sleep(10)

            return True

        except Exception as e:
            self.log_health_event("RESTART_FAILED", f"Gateway restart failed: {e}")
            return False

    async def run_health_monitor(self, duration_hours=24):
        """Run continuous health monitoring"""
        print("🏥 GATEWAY HEALTH MONITOR STARTED")
        print(f"📅 Started: {datetime.now()}")
        print(f"⏱️  Duration: {duration_hours} hours")
        print(f"💓 Check interval: {self.health_check_interval} seconds")
        print(f"🚨 Failure threshold: {self.timeout_threshold} consecutive failures")
        print("=" * 60)

        end_time = datetime.now() + timedelta(hours=duration_hours)

        while datetime.now() < end_time:
            try:
                # Check Gateway health
                is_healthy = await self.check_gateway_health()

                if is_healthy:
                    self.consecutive_failures = 0
                    self.last_successful_check = datetime.now()
                else:
                    self.consecutive_failures += 1

                    if self.consecutive_failures >= self.timeout_threshold:
                        print(
                            f"🚨 GATEWAY DEATH DETECTED! {self.consecutive_failures} consecutive failures"
                        )
                        self.log_health_event(
                            "GATEWAY_DEATH",
                            f"Gateway unresponsive for {self.consecutive_failures} checks",
                        )

                        # Attempt recovery
                        print("🔧 Attempting Gateway recovery...")

                        # Step 1: Kill unresponsive process
                        if self.kill_gateway_process():
                            time.sleep(5)  # Wait for clean shutdown

                            # Step 2: Restart Gateway
                            if self.restart_gateway():
                                print("✅ Gateway recovery initiated")
                                self.consecutive_failures = 0

                                # Wait longer after restart
                                await asyncio.sleep(30)
                            else:
                                print("❌ Gateway restart failed")
                        else:
                            print("❌ Gateway kill failed")

                # Wait for next check
                await asyncio.sleep(self.health_check_interval)

            except KeyboardInterrupt:
                print("\n🛑 Health monitor stopped by user")
                break
            except Exception as e:
                self.log_health_event("MONITOR_ERROR", f"Monitor error: {e}")
                await asyncio.sleep(self.health_check_interval)

        self.print_health_summary()

    def print_health_summary(self):
        """Print health monitoring summary"""
        print(f"\n" + "=" * 60)
        print(f"🏥 GATEWAY HEALTH MONITOR SUMMARY")
        print(f"=" * 60)

        if not self.health_log:
            print("No health events recorded")
            return

        # Count event types
        event_counts = {}
        for event in self.health_log:
            status = event["status"]
            event_counts[status] = event_counts.get(status, 0) + 1

        print(f"📊 Health Event Summary:")
        for status, count in event_counts.items():
            print(f"   {status}: {count}")

        # Calculate uptime
        healthy_events = event_counts.get("HEALTHY", 0)
        total_events = len(self.health_log)
        uptime_percentage = (
            (healthy_events / total_events * 100) if total_events > 0 else 0
        )

        print(f"\n📈 Gateway Uptime: {uptime_percentage:.1f}%")

        # Show recent events
        print(f"\n📋 Recent Health Events:")
        for event in self.health_log[-10:]:
            timestamp = event["timestamp"].strftime("%H:%M:%S")
            print(f"   {timestamp} | {event['status']}: {event['message']}")


async def main():
    """Run Gateway health monitoring"""
    print("🏥 Starting Gateway Health Monitor to prevent 'death after few minutes'")
    print("This will detect when Gateway becomes unresponsive and auto-restart it")

    monitor = GatewayHealthMonitor()

    # Run monitoring for 2 hours as a test
    await monitor.run_health_monitor(duration_hours=2)


if __name__ == "__main__":
    asyncio.run(main())
