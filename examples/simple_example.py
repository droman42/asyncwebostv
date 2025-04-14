#!/usr/bin/env python3
"""
Simple example showing how to use asyncwebostv to control a WebOS TV.
"""

import asyncio
import argparse
import logging

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl, 
    TvControl, 
    SystemControl, 
    ApplicationControl,
    InputControl
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def setup_client(client, client_key=None):
    """Set up the client by performing the registration process if needed.
    
    Args:
        client: WebOSClient instance
        client_key: Optional client key for authentication
        
    Returns:
        The client key after registration or None if registration failed
    """
    if client_key:
        client.client_key = client_key
    
    # Only register if no client key is available
    if not client.client_key:
        logger.info("No client key available, registering with TV...")
        # Create a store dictionary to receive the client key
        store = {}
        
        try:
            async for status in client.register(store):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection request on your TV...")
                elif status == WebOSClient.REGISTERED:
                    logger.info("Registration successful!")
                    return store.get("client_key")
        except Exception as ex:
            logger.error("Registration failed: %s", ex)
            return None
    
    return client.client_key


async def main():
    """Main function to demonstrate controlling a WebOS TV."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Control a WebOS TV")
    parser.add_argument("--ip", help="IP address of the TV (optional, will use discovery if not provided)")
    parser.add_argument("--secure", action="store_true", help="Use secure connection")
    parser.add_argument("--client-key", help="Client key for authentication (optional)")
    args = parser.parse_args()
    
    client = None
    
    if args.ip:
        # Use provided IP address
        client = WebOSClient(args.ip, secure=args.secure, client_key=args.client_key)
        logger.info("Using TV at IP: %s", args.ip)
    else:
        # Discover TVs on the network
        logger.info("Discovering TVs on the network...")
        clients = await WebOSClient.discover(secure=args.secure)
        if not clients:
            logger.error("No TVs found on the network")
            return
        
        client = clients[0]
        logger.info("Found TV at %s", client.ws_url)
    
    # Connect to the TV
    await client.connect()
    
    # Set up client (register if needed)
    client_key = await setup_client(client, args.client_key)
    if not client_key:
        logger.error("Failed to set up client")
        await client.close()
        return
    
    # Display the client key for future use
    logger.info("Client key for future use: %s", client_key)
    
    try:
        # Create control interfaces
        media = MediaControl(client)
        system = SystemControl(client)
        app = ApplicationControl(client)
        tv = TvControl(client)
        
        # Get system info
        info = await system.info()
        logger.info("TV system info: %s", info)
        
        # Get volume
        volume = await media.get_volume()
        logger.info("Current volume: %s", volume)
        
        # Get list of apps
        apps = await app.list_apps()
        logger.info("Available apps:")
        for app_obj in apps:
            logger.info("  %s (%s)", app_obj["title"], app_obj["id"])
        
        # Demonstrate volume control
        logger.info("Increasing volume...")
        await media.volume_up()
        await asyncio.sleep(1)
        logger.info("Decreasing volume...")
        await media.volume_down()
        
        # Show a notification
        logger.info("Displaying notification on TV...")
        await system.notify("Hello from AsyncWebOSTV!")
    
    except Exception as ex:
        logger.error("Error: %s", ex)
    
    finally:
        # Close the connection when done
        await client.close()
        logger.info("Connection closed")


if __name__ == "__main__":
    asyncio.run(main()) 