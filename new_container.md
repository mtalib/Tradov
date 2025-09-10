# Stop any existing container
docker stop ib_gateway_test 2>/dev/null
docker rm ib_gateway_test 2>/dev/null

# Run fresh container with explicit API enablement
docker run -d \
  --name ib_gateway_working \
  -p 4003:4002 \
  -p 5900:5900 \
  -e TWS_USERID="mtalib342" \
  -e TWS_PASSWORD="Gintaro007$" \
  -e TRADING_MODE="paper" \
  -e TWS_ACCEPT_INCOMING="accept" \
  -e VNC_SERVER_PASSWORD="password123" \
  ghcr.io/gnzsnz/ib-gateway:latest

# Wait for startup
sleep 30

# Check logs
docker logs ib_gateway_working

# Test connection on port 4003
python3 -c "
from ib_async import IB
import asyncio

async def test():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 4003, clientId=1)
        print('✅ Docker IB Gateway WORKING!')
        print(f'Account: {ib.managedAccounts()}')
        ib.disconnect()
    except Exception as e:
        print(f'Docker test failed: {e}')

asyncio.run(test())
"
