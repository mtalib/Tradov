#!/bin/bash
source ~/.bashrc
echo "Current mode: $IB_CONNECTION_MODE"
echo "Testing mode switch..."
ib-switch gateway
echo "After switch: $IB_CONNECTION_MODE"
