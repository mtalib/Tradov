#!/bin/bash
# fix_time_sync.sh - Fix time synchronization for IB Gateway

echo "=================================================="
echo "IB GATEWAY TIME SYNCHRONIZATION FIX"
echo "=================================================="

# Check current time settings
echo -e "\n[1] Current System Time:"
date
echo "Timezone: $(timedatectl | grep "Time zone" | awk '{print $3}')"

# Set correct timezone to Eastern Time
echo -e "\n[2] Setting timezone to US Eastern..."
sudo timedatectl set-timezone America/New_York

# Enable NTP time sync
echo -e "\n[3] Enabling automatic time synchronization..."
sudo timedatectl set-ntp true

# Force immediate sync
echo -e "\n[4] Forcing time sync..."
sudo systemctl restart systemd-timesyncd
sleep 2

# Verify new settings
echo -e "\n[5] New System Settings:"
timedatectl
echo -e "\nCurrent time: $(date)"

# Check time sync status
echo -e "\n[6] Time Sync Status:"
timedatectl timesync-status

# Compare with world time
echo -e "\n[7] Verifying against world clock..."
curl -s "http://worldtimeapi.org/api/timezone/America/New_York" | grep -E "(datetime|timezone)" || echo "Could not verify online"

echo -e "\n=================================================="
echo "IMPORTANT NEXT STEPS:"
echo "=================================================="
echo "1. RESTART IB Gateway completely"
echo "2. Log in again - you should now get 2FA prompt"
echo "3. Complete authentication on mobile app"
echo "4. Then run: python3 testIB_v2.py"
echo ""
echo "Time sync is CRITICAL for IB authentication!"
echo "=================================================="