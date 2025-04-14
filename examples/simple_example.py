#!/usr/bin/env python3
"""
Simple example showing how to use asyncwebostv to control a WebOS TV.
"""

import asyncio
import json
import os
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

# Path to store client key
CLIENT_KEY_FILE = os.path.join(os.path.dirname(__file__), "client.json")


async def setup_client(client):
    """Set up the client by performing the registration process if needed."""
    
    # Load the client key if it exists
    client_key = {}
    if os.path.exists(CLIENT_KEY_FILE):
        try:
            with open(CLIENT_KEY_FILE, "r") as f:
                client_key = json.load(f)
                logger.info("Loaded client key from file")
        except Exception as ex:
            logger.warning("Failed to load client key: %s", ex)
    
    # Register the client
    registration = client.register(client_key)
    try:
        response = await anext(registration)
        if response == WebOSClient.PROMPTED:
            logger.info("Please accept the connection request on your TV...")
            response = await anext(registration)
            if response == WebOSClient.REGISTERED:
                logger.info("Registration successful!")
                # Save the client key for future use
                with open(CLIENT_KEY_FILE, "w") as f:
                    json.dump(client_key, f)
                    logger.info("Saved client key to file")
            else:
                logger.error("Registration failed with unexpected response: %s", response)
        else:
            logger.info("Already registered with key")
    except Exception as ex:
        logger.error("Registration failed: %s", ex)
        return False
    
    return True


async def main():
    """Main function to demonstrate controlling a WebOS TV."""
    
    # Discover TVs on the network
    # Alternatively, provide the TV's IP address directly:
    # client = WebOSClient("192.168.1.100")
    logger.info("Discovering TVs on the network...")
    clients = await WebOSClient.discover()
    if not clients:
        logger.error("No TVs found on the network")
        return
    
    client = clients[0]
    logger.info("Found TV at %s", client.ws_url)
    
    # Connect to the TV
    await client.connect()
    
    # Set up client (register if needed)
    if not await setup_client(client):
        return
    
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
    
    # Close the connection when done
    await client.close()


if __name__ == "__main__":
    asyncio.run(main()) 