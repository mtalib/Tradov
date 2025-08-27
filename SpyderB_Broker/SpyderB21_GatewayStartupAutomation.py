#!/usr/bin/env python3
"""Gateway Startup for IB Gateway 10.39 with IBC"""

import os
import subprocess
import time
from pathlib import Path

# Configuration - Using your actual paths
IBC_JAR = Path.home() / "IBC" / "IBC.jar"
GATEWAY_DIR = Path.home() / "Jts" / "ibgateway" / "1039"
IBC_CONFIG = Path.home() / "ibc" / "config.ini"

def start_gateway():
    print("Starting IB Gateway 10.39 with IBC automation...")
    
    # Kill any existing Xvfb
    subprocess.run(["pkill", "Xvfb"], capture_output=True)
    time.sleep(1)
    
    # Start Xvfb
    print("Starting virtual display...")
    subprocess.Popen(["Xvfb", ":99", "-ac", "-screen", "0", "1600x1200x24"])
    time.sleep(2)
    
    # Set environment
    os.environ["DISPLAY"] = ":99"
    os.environ["TWS_MAJOR_VRSN"] = "1039"
    
    # Start with IBC
    cmd = [
        "java",
        "-cp", f"{IBC_JAR}:{GATEWAY_DIR}/jars/*",
        "ibcalpha.ibc.IbcGateway",
        str(IBC_CONFIG),
        str(GATEWAY_DIR),
        "gateway",
        "paper"
    ]
    
    print(f"Starting Gateway...")
    subprocess.run(cmd)

if __name__ == "__main__":
    start_gateway()
