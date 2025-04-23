#!/usr/bin/env python3
"""
Simple script to get a client key from a WebOS TV.
This is useful for first-time setup.
"""

import asyncio
import logging
import argparse
import sys

from asyncwebostv.connection import WebOSClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def get_client_key(ip_address, secure=False):
    """Get a client key from a WebOS TV."""
    # Create the client
    client = WebOSClient(ip_address, secure=secure)
    
    try:
        # Connect to the TV
        logger.info(f"Connecting to {'wss' if secure else 'ws'}://{ip_address}:{3001 if secure else 3000}/")
        await client.connect()
        
        # Register with the TV
        logger.info("Registering with TV. Look at your TV and accept the connection request...")
        store = {}
        async for status in client.register(store):
            if status == WebOSClient.PROMPTED:
                logger.info("Please accept the connection request on your TV!")
            elif status == WebOSClient.REGISTERED:
                client_key = store.get("client_key")
                logger.info("Registration successful!")
                logger.info(f"Client key: {client_key}")
                return client_key
        
        logger.error("Failed to get client key - no confirmation from TV")
        return None
    except Exception as e:
        logger.error(f"Error connecting to TV: {e}")
        return None
    finally:
        # Disconnect
        if client:
            await client.close()
            logger.info("Connection closed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Get a client key from a WebOS TV')
    parser.add_argument('ip', help='IP address of the TV')
    parser.add_argument('--secure', action='store_true', help='Use secure connection (port 3001)')
    args = parser.parse_args()
    
    client_key = await get_client_key(args.ip, args.secure)
    
    if client_key:
        print(f"\nSUCCESS! Your client key is: {client_key}")
        print("Add this to your configuration file.")
        return 0
    else:
        print("\nFAILED to get client key.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 