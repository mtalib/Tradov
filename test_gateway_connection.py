#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - IB Gateway 10.37 Real-time Monitor
Monitors heap usage, connection health, and performance metrics
"""

import sys
import time
import psutil
import json
from datetime import datetime
from pathlib import Path
import threading
import curses

# Add Spyder to path
sys.path.insert(0, str(Path.home() / "Spyder"))

from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager

class GatewayMonitor:
    """Real-time monitor for IB Gateway"""
    
    def __init__(self):
        self.manager = None
        self.gateway_process = None
        self.running = True
        self.stats = {
            'heap_used': 0,
            'heap_max': 4096,
            'cpu_percent': 0,
            'memory_mb': 0,
            'threads': 0,
            'uptime': '00:00:00',
            'connections': 0,
            'errors': 0,
            'latency': 0
        }
        
    def find_gateway_process(self):
        """Find IB Gateway Java process"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'java' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info.get('cmdline', []))
                    if 'ibgateway' in cmdline:
                        return proc
            except:
                continue
        return None
    
    def update_process_stats(self):
        """Update process statistics"""
        self.gateway_process = self.find_gateway_process()
        
        if self.gateway_process:
            try:
                # CPU and memory
                self.stats['cpu_percent'] = self.gateway_process.cpu_percent(interval=0.1)
                mem_info = self.gateway_process.memory_info()
                self.stats['memory_mb'] = mem_info.rss / 1024 / 1024
                
                # Threads
                self.stats['threads'] = self.gateway_process.num_threads()
                
                # Estimate heap usage (approximation)
                # Real heap usage requires JMX or similar
                self.stats['heap_used'] = min(self.stats['memory_mb'], self.stats['heap_max'])
                
                # Uptime
                create_time = datetime.fromtimestamp(self.gateway_process.create_time())
                uptime = datetime.now() - create_time
                hours, remainder = divmod(int(uptime.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                self.stats['uptime'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.gateway_process = None
    
    def update_connection_stats(self):
        """Update connection statistics"""
        if self.manager and self.manager.is_connected():
            status = self.manager.get_status()
            self.stats['connections'] = 1
            self.stats['errors'] = status['metrics']['error_count']
            self.stats['latency'] = status['metrics']['latency_ms']
        else:
            self.stats['connections'] = 0
    
    def draw_dashboard(self, stdscr):
        """Draw monitoring dashboard using curses"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)    # Non-blocking input
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        
        while self.running:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Header
            header = "═" * width
            title = " SPYDER IB Gateway 10.37 Monitor "
            start_pos = (width - len(title)) // 2
            stdscr.addstr(0, 0, header)
            stdscr.addstr(0, start_pos, title, curses.A_BOLD)
            
            # Update stats
            self.update_process_stats()
            self.update_connection_stats()
            
            # Gateway Status
            y = 2
            stdscr.addstr(y, 2, "GATEWAY STATUS", curses.A_BOLD | curses.color_pair(4))
            y += 1
            
            if self.gateway_process:
                stdscr.addstr(y, 4, "● Status: ", curses.A_BOLD)
                stdscr.addstr(y, 14, "RUNNING", curses.color_pair(1))
                stdscr.addstr(y, 25, f"PID: {self.gateway_process.pid}")
            else:
                stdscr.addstr(y, 4, "● Status: ", curses.A_BOLD)
                stdscr.addstr(y, 14, "STOPPED", curses.color_pair(3))
            
            y += 1
            stdscr.addstr(y, 4, f"● Uptime: {self.stats['uptime']}")
            
            # Heap Memory
            y += 2
            stdscr.addstr(y, 2, "HEAP MEMORY (4GB CONFIGURED)", curses.A_BOLD | curses.color_pair(4))
            y += 1
            
            heap_percent = (self.stats['heap_used'] / self.stats['heap_max']) * 100
            heap_bar_width = 40
            heap_filled = int(heap_bar_width * heap_percent / 100)
            
            # Choose color based on usage
            if heap_percent < 60:
                color = curses.color_pair(1)  # Green
            elif heap_percent < 80:
                color = curses.color_pair(2)  # Yellow
            else:
                color = curses.color_pair(3)  # Red
            
            stdscr.addstr(y, 4, "Heap: [")
            stdscr.addstr(y, 11, "█" * heap_filled, color)
            stdscr.addstr(y, 11 + heap_filled, "░" * (heap_bar_width - heap_filled))
            stdscr.addstr(y, 51, f"] {self.stats['heap_used']:.0f}/{self.stats['heap_max']} MB ({heap_percent:.1f}%)")
            
            # System Resources
            y += 2
            stdscr.addstr(y, 2, "SYSTEM RESOURCES", curses.A_BOLD | curses.color_pair(4))
            y += 1
            
            # CPU
            cpu_color = curses.color_pair(1) if self.stats['cpu_percent'] < 50 else curses.color_pair(2)
            stdscr.addstr(y, 4, f"● CPU Usage: ")
            stdscr.addstr(y, 17, f"{self.stats['cpu_percent']:.1f}%", cpu_color)
            
            # Memory
            y += 1
            stdscr.addstr(y, 4, f"● Memory: {self.stats['memory_mb']:.0f} MB")
            
            # Threads
            y += 1
            stdscr.addstr(y, 4, f"● Threads: {self.stats['threads']}")
            
            # Connection Status
            y += 2
            stdscr.addstr(y, 2, "CONNECTION STATUS", curses.A_BOLD | curses.color_pair(4))
            y += 1
            
            if self.stats['connections'] > 0:
                stdscr.addstr(y, 4, "● Connection: ", curses.A_BOLD)
                stdscr.addstr(y, 18, "CONNECTED", curses.color_pair(1))
                y += 1
                stdscr.addstr(y, 4, f"● Latency: {self.stats['latency']:.1f} ms")
                y += 1
                stdscr.addstr(y, 4, f"● Errors: {self.stats['errors']}")
            else:
                stdscr.addstr(y, 4, "● Connection: ", curses.A_BOLD)
                stdscr.addstr(y, 18, "DISCONNECTED", curses.color_pair(3))
            
            # Performance Indicators
            y += 2
            stdscr.addstr(y, 2, "PERFORMANCE", curses.A_BOLD | curses.color_pair(4))
            y += 1
            
            # Health check
            health_status = "HEALTHY"
            health_color = curses.color_pair(1)
            
            if heap_percent > 90:
                health_status = "CRITICAL - High heap usage"
                health_color = curses.color_pair(3)
            elif self.stats['cpu_percent'] > 80:
                health_status = "WARNING - High CPU usage"
                health_color = curses.color_pair(2)
            elif self.stats['errors'] > 50:
                health_status = "WARNING - High error count"
                health_color = curses.color_pair(2)
            
            stdscr.addstr(y, 4, "● Health: ", curses.A_BOLD)
            stdscr.addstr(y, 14, health_status, health_color)
            
            # Footer
            y = height - 3
            stdscr.addstr(y, 0, "═" * width)
            y += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stdscr.addstr(y, 2, f"Last Update: {timestamp}")
            stdscr.addstr(y, width - 20, "Press 'q' to quit")
            
            # Refresh screen
            stdscr.refresh()
            
            # Check for quit
            key = stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                self.running = False
                break
            
            # Update every second
            time.sleep(1)
    
    def run_simple(self):
        """Run simple text-based monitor (non-curses)"""
        print("=" * 60)
        print("SPYDER IB Gateway 10.37 Monitor (Simple Mode)")
        print("Press Ctrl+C to stop")
        print("=" * 60)
        
        try:
            while self.running:
                self.update_process_stats()
                self.update_connection_stats()
                
                # Clear screen (works on most terminals)
                print("\033[2J\033[H", end='')
                
                print("=" * 60)
                print(f"IB Gateway Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 60)
                
                if self.gateway_process:
                    print(f"Gateway Status: RUNNING (PID: {self.gateway_process.pid})")
                else:
                    print("Gateway Status: STOPPED")
                
                print(f"Uptime: {self.stats['uptime']}")
                print()
                
                print("HEAP MEMORY:")
                heap_percent = (self.stats['heap_used'] / self.stats['heap_max']) * 100
                bar_width = 30
                filled = int(bar_width * heap_percent / 100)
                bar = '█' * filled + '░' * (bar_width - filled)
                print(f"  [{bar}] {heap_percent:.1f}%")
                print(f"  {self.stats['heap_used']:.0f} / {self.stats['heap_max']} MB")
                print()
                
                print("SYSTEM RESOURCES:")
                print(f"  CPU: {self.stats['cpu_percent']:.1f}%")
                print(f"  Memory: {self.stats['memory_mb']:.0f} MB")
                print(f"  Threads: {self.stats['threads']}")
                print()
                
                print("CONNECTION:")
                if self.stats['connections'] > 0:
                    print(f"  Status: CONNECTED")
                    print(f"  Latency: {self.stats['latency']:.1f} ms")
                    print(f"  Errors: {self.stats['errors']}")
                else:
                    print(f"  Status: DISCONNECTED")
                
                print("=" * 60)
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\nMonitor stopped")
    
    def start_with_connection(self):
        """Start monitor with connection manager"""
        print("Starting connection manager...")
        
        config = {
            "mode": "paper",
            "heap_min": "4096m",
            "heap_max": "4096m",
            "use_ibautomater": True
        }
        
        self.manager = get_connection_manager(config)
        
        # Start in a thread
        connect_thread = threading.Thread(target=self.manager.start)
        connect_thread.daemon = True
        connect_thread.start()
        
        # Give it time to start
        time.sleep(5)

def main():
    """Main entry point"""
    monitor = GatewayMonitor()
    
    # Check command line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--connect':
        monitor.start_with_connection()
    
    # Try curses mode first
    try:
        curses.wrapper(monitor.draw_dashboard)
    except Exception as e:
        # Fall back to simple mode
        print(f"Curses mode failed ({e}), using simple mode...")
        monitor.run_simple()

if __name__ == "__main__":
    main()
