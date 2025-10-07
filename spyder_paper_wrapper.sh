#!/bin/bash
# Debug launcher - traces what actually runs
echo "=== LAUNCHER DEBUG $(date) ===" >> /tmp/spyder_launch_debug.log
echo "User: $(whoami)" >> /tmp/spyder_launch_debug.log
echo "PWD: $(pwd)" >> /tmp/spyder_launch_debug.log
echo "Command: $0 $@" >> /tmp/spyder_launch_debug.log
echo "" >> /tmp/spyder_launch_debug.log

cd /home/adam/Projects/Spyder
source .venv/bin/activate
exec python SpyderA_Core/SpyderA01_Main.py
