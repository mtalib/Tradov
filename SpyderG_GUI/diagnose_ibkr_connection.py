

import asyncio
from ib_async import IB, util
import logging

# Configure logging for better visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HOST = '127.0.0.1'  # Assuming IB Gateway is running locally
PORT = 4002         # Default IB Gateway port (check your IB Gateway configuration)
NUM_CLIENTS = 8     # Number of clients to test
TIMEOUT = 10        # Connection timeout in seconds

async def test_connection(client_id: int):
    ib = IB()
    try:
        logging.info(f"Attempting to connect with clientId={client_id}...")
        await ib.connect(HOST, PORT, clientId=client_id, timeout=TIMEOUT)
        logging.info(f"Successfully connected with clientId={client_id}.")
        # Perform a simple request to confirm full handshake and data flow
        # For example, request current time or account summary
        # This helps verify that the connection is fully established and not just a partial handshake
        try:
            await ib.reqCurrentTime()
            logging.info(f"Successfully received current time with clientId={client_id}.")
        except Exception as e:
            logging.error(f"Error requesting current time with clientId={client_id}: {e}")

    except asyncio.TimeoutError:
        logging.error(f"Connection to IB Gateway timed out for clientId={client_id}. "
                      f"Ensure IB Gateway is running, API settings are correct (ActiveX/Sockets enabled), "
                      f"and the host/port are accurate.")
    except ConnectionRefusedError:
        logging.error(f"Connection refused for clientId={client_id}. "
                      f"IB Gateway might not be running or is not listening on {HOST}:{PORT}. "
                      f"Check firewall settings.")
    except Exception as e:
        logging.error(f"An unexpected error occurred for clientId={client_id}: {e}")
    finally:
        if ib.isConnected():
            ib.disconnect()
            logging.info(f"Disconnected clientId={client_id}.")

async def main():
    logging.info(f"Starting connection tests for {NUM_CLIENTS} clients...")
    tasks = [test_connection(i) for i in range(1, NUM_CLIENTS + 1)]
    await asyncio.gather(*tasks)
    logging.info("All connection tests completed.")

if __name__ == '__main__':
    # This is necessary for ib_async to run in a Jupyter/IPython environment,
    # but also good practice for standalone scripts using asyncio.
    util.startLoop()
    asyncio.run(main())
