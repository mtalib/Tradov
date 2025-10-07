#!/bin/bash
# -*- coding: utf-8 -*-
"""
DOCKER IB GATEWAY SETUP FOR SPYDER

SPYDER - Autonomous Options Trading System v1.0

Script: setup_docker_ib_gateway.sh
Purpose: Setup Docker-based IB Gateway for Spyder trading system
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 17:15:00

Description:
    This script sets up a Docker-based IB Gateway using the gnzsnz/ib-gateway-docker
    image with automated login, headless operation, and guaranteed API access.
    This replaces the problematic GUI Gateway setup with a clean, reproducible solution.

"""

set -e  # Exit on any error

echo "🕷️ SPYDER Docker IB Gateway Setup"
echo "🐳 Setting up automated, headless IB Gateway"
echo "=" * 60

# Create project structure
GATEWAY_DIR="$HOME/spyder-ib-gateway"
echo "📁 Creating directory structure in $GATEWAY_DIR"

mkdir -p "$GATEWAY_DIR/ibc"
cd "$GATEWAY_DIR"

# Create docker-compose.yml
echo "📝 Creating docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  ib_gateway:
    image: gnzsnz/ib-gateway-docker:latest
    container_name: spyder_ib_gateway
    restart: unless-stopped
    environment:
      # Trading Configuration
      TRADING_MODE: paper                    # paper or live
      TWS_API_PORT: 4002                    # API port
      
      # IBC Configuration
      IBC_INI: /ibc/config.ini              # IBC config file
      
      # Display Configuration (headless)
      DISPLAY: :0
      
      # Java Configuration
      TWS_MAJOR_VRSN: 1039                  # Gateway version
      
      # Optional: Enable logging
      IBC_LOGLEVEL: INFO
      
    ports:
      - "4002:4002"                         # Paper trading API
      - "5900:5900"                         # VNC access (optional)
      
    volumes:
      - ./ibc:/ibc                          # IBC configuration
      - ./logs:/opt/ibc/logs                # Log files
      - ib_gateway_data:/home/ibgateway     # Persistent data
      
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "4002"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s

volumes:
  ib_gateway_data:
    driver: local

networks:
  default:
    driver: bridge
EOF

echo "✅ docker-compose.yml created"

# Create IBC config template
echo "📝 Creating IBC configuration template..."
cat > ibc/config.ini << 'EOF'
# =============================================================================
# IBC CONFIGURATION FOR SPYDER TRADING SYSTEM
# =============================================================================

[Login]
# Your IBKR credentials (REPLACE WITH YOUR ACTUAL CREDENTIALS)
IbLoginId=YOUR_IBKR_USERNAME
IbPassword=YOUR_IBKR_PASSWORD

# Trading mode: paper or live
TradingMode=paper

# Login timeout
LoginTimeout=30

[StartUp]
# Start Gateway (not TWS)
GatewayOrTWS=Gateway

# Enable API only (no GUI trading interface needed)
EnableApiOnly=true

# API Configuration
ApiPort=4002
ApiOnly=true
ReadOnlyApi=no

# Automatic login
AutoLogoffTime=00:00
AutoRestart=yes

[API]
# Socket port for API connections
SocketPort=4002

# Enable socket connections
EnableSocketConnections=yes

# Master client ID (0 = allow any)
MasterClientId=0

# Download open orders on connection
DownloadOpenOrders=yes

# Enable ActiveX and Socket Clients
EnableActiveXAndSocketClients=yes

[Logging]
# Enable logging for debugging
LogLevel=Information
LogFile=/opt/ibc/logs/ibc.log

[Connection]
# Connection timeout
ConnectionTimeout=30

# Keep connection alive
KeepConnectionAlive=yes
EOF

echo "✅ IBC config template created"

# Create logs directory
mkdir -p logs

# Create helper scripts
echo "📝 Creating helper scripts..."

# Start script
cat > start_gateway.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Spyder IB Gateway..."

# Stop any existing container
docker-compose down

# Start the Gateway
docker-compose up -d

echo "⏳ Waiting for Gateway to initialize (2 minutes)..."
sleep 120

echo "🧪 Testing connection..."
docker logs spyder_ib_gateway --tail 20

echo "✅ Gateway should be ready!"
echo "🌐 VNC access available at: localhost:5900 (password: 'secretpassword')"
echo "🔌 API available at: localhost:4002"
EOF

# Stop script
cat > stop_gateway.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping Spyder IB Gateway..."
docker-compose down
echo "✅ Gateway stopped"
EOF

# Status script  
cat > status_gateway.sh << 'EOF'
#!/bin/bash
echo "📊 Spyder IB Gateway Status"
echo "=" * 40

# Check container status
if docker ps | grep -q spyder_ib_gateway; then
    echo "✅ Container: Running"
    
    # Check port 4002
    if docker exec spyder_ib_gateway nc -z localhost 4002 2>/dev/null; then
        echo "✅ API Port 4002: Open"
    else
        echo "❌ API Port 4002: Closed"
    fi
    
    # Show recent logs
    echo -e "\n📄 Recent logs:"
    docker logs spyder_ib_gateway --tail 10
    
else
    echo "❌ Container: Not running"
fi
EOF

# Test connection script
cat > test_connection.py << 'EOF'
#!/usr/bin/env python3
"""Test connection to Docker IB Gateway."""

import asyncio
from ib_async import IB

async def test_docker_gateway():
    """Test connection to Docker Gateway."""
    print("🧪 Testing Docker IB Gateway Connection")
    print("-" * 40)
    
    ib = IB()
    
    try:
        # Connect to Docker Gateway
        await ib.connectAsync('localhost', 4002, clientId=1, timeout=15)
        
        if ib.isConnected():
            print("✅ SUCCESS! Connected to Docker Gateway")
            print(f"📊 Server version: {ib.serverVersion()}")
            print(f"🕒 Connection time: {ib.reqCurrentTime()}")
            
            # Test managed accounts
            accounts = ib.managedAccounts()
            print(f"👤 Managed accounts: {accounts}")
            
            return True
        else:
            print("❌ Connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected")

if __name__ == "__main__":
    success = asyncio.run(test_docker_gateway())
    exit(0 if success else 1)
EOF

# Make scripts executable
chmod +x *.sh
chmod +x test_connection.py

# Create README
cat > README.md << 'EOF'
# Spyder IB Gateway Docker Setup

## Quick Start

1. **Configure credentials**: Edit `ibc/config.ini` with your IBKR username/password
2. **Start Gateway**: `./start_gateway.sh`  
3. **Test connection**: `python test_connection.py`
4. **Check status**: `./status_gateway.sh`
5. **Stop Gateway**: `./stop_gateway.sh`

## Configuration

- **API Port**: 4002 (paper trading)
- **VNC Access**: localhost:5900 (password: 'secretpassword')
- **Logs**: `./logs/` directory
- **Config**: `./ibc/config.ini`

## Troubleshooting

- **Check logs**: `docker logs spyder_ib_gateway`
- **Check status**: `./status_gateway.sh`
- **Restart**: `./stop_gateway.sh && ./start_gateway.sh`

## Integration with Spyder

Once working, use these connection parameters in your Spyder modules:
- Host: `localhost` or `127.0.0.1`  
- Port: `4002`
- Client ID: `1` (or any number 1-31)
EOF

echo "📋 Setup complete! Directory structure:"
echo "📁 $GATEWAY_DIR/"
echo "   ├── docker-compose.yml      # Docker configuration"
echo "   ├── ibc/config.ini          # IBC configuration (EDIT YOUR CREDENTIALS!)"
echo "   ├── start_gateway.sh        # Start Gateway"
echo "   ├── stop_gateway.sh         # Stop Gateway"
echo "   ├── status_gateway.sh       # Check status"
echo "   ├── test_connection.py      # Test connection"
echo "   ├── logs/                   # Gateway logs"
echo "   └── README.md               # Documentation"

echo ""
echo "🎯 NEXT STEPS:"
echo "1. Edit ibc/config.ini with your IBKR credentials"
echo "2. Run: ./start_gateway.sh"
echo "3. Run: python test_connection.py"
echo "4. Start building Spyder modules!"

echo ""
echo "🚨 IMPORTANT: Edit ibc/config.ini with your actual IBKR username and password!"
