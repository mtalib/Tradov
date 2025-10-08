#!/usr/bin/env python3
"""
Start Pooled Multi-Client Manager (brings up multiple IB clients via connection pool)

Usage:
    python start_pooled_clients.py [--mode=paper|live] [--pool-size=8]

This script attempts to start the PooledMultiClientManager with the requested
pool size and client types and will print active clients on success.

It handles ImportError and other issues gracefully and prints remediation steps.
"""
import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("paper", "live"), default="paper")
    p.add_argument("--pool-size", type=int, default=8)
    return p.parse_args()


async def main_async(mode: str, pool_size: int):
    # Determine port
    port = 4002 if mode == "paper" else 4001
    print(
        f"Starting pooled multi-client manager: mode={mode}, port={port}, pool_size={pool_size}"
    )

    try:
        from SpyderB_Broker.SpyderB31_PooledMultiClientManager import (
            PooledMultiClientManager,
            ClientType,
        )
    except Exception as e:
        print("❌ Failed to import pooled manager or dependencies:", e)
        print(
            "Possible causes:\n - Missing 'ib_async' package\n - Virtualenv not activated\n - PYTHONPATH not set to project root"
        )
        print(
            "Remediation:\n 1) Activate your SPYDER virtualenv (source .venv/bin/activate)\n 2) pip install -r requirements.txt or pip install ib_async\n 3) Ensure gateway is running and logged in (IB Gateway GUI)"
        )
        return 2

    # Build a list of client types up to pool_size (cycle through defined types)
    all_types = list(ClientType)
    client_types = [all_types[i % len(all_types)] for i in range(pool_size)]

    manager = PooledMultiClientManager(
        host="127.0.0.1", port=port, pool_size=pool_size, client_types=client_types
    )

    print("🔧 Initializing manager...")
    try:
        started = await manager.start()
    except Exception as e:
        print(f"❌ Manager.start() raised an exception: {e}")
        return 3

    if not started:
        print("❌ Failed to start pooled manager (see logs).")
        return 4

    print("✅ Manager started successfully")
    active = manager.list_active_clients()
    print(f"📋 Active clients: {active}")

    # Keep manager running until user interrupts
    print("Press Ctrl-C to stop the pooled manager and disconnect clients")
    try:
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping manager...")
        await manager.stop()
        print("✅ Manager stopped")
        return 0


if __name__ == "__main__":
    args = parse_args()
    exit_code = asyncio.run(main_async(args.mode, args.pool_size))
    sys.exit(exit_code)
