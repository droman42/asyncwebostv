#!/usr/bin/env python3
"""
Example demonstrating how to use subscriptions in asyncwebostv to monitor TV events.
"""

import asyncio
import json
import os
import logging
import signal

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl, 
    TvControl, 
    SystemControl
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to store client key
CLIENT_KEY_FILE = os.path.join(os.path.dirname(__file__), "client.json")

# Flag to indicate if the program should stop
stop_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle signals to gracefully shutdown."""
    logger.info("Received signal %s, shutting down...", signum)
    stop_event.set()


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


async def monitor_volume(media_control):
    """Monitor volume changes on the TV."""
    logger.info("Setting up volume monitoring...")
    
    async def volume_callback(success, payload):
        if success:
            logger.info("Volume changed: %s, muted: %s", 
                      payload.get("volume", "N/A"), 
                      payload.get("muted", "N/A"))
        else:
            logger.error("Volume callback error: %s", payload)
    
    # Subscribe to volume changes
    await media_control.subscribe_get_volume(volume_callback)
    logger.info("Volume monitoring active")


async def monitor_power_state(system_control):
    """Monitor power state changes on the TV."""
    logger.info("Setting up power state monitoring...")
    
    async def power_callback(success, payload):
        if success:
            logger.info("Power state changed: %s, processing: %s", 
                      payload.get("state", "N/A"), 
                      payload.get("processing", "N/A"))
        else:
            logger.error("Power state callback error: %s", payload)
    
    # Subscribe to power state changes
    await system_control.subscribe_power_state(power_callback)
    logger.info("Power state monitoring active")


async def monitor_channel(tv_control):
    """Monitor channel changes on the TV."""
    logger.info("Setting up channel monitoring...")
    
    async def channel_callback(success, payload):
        if success:
            logger.info("Channel changed: %s - %s", 
                      payload.get("channelNumber", "N/A"), 
                      payload.get("channelName", "N/A"))
        else:
            logger.error("Channel callback error: %s", payload)
    
    # Subscribe to channel changes
    await tv_control.subscribe_get_current_channel(channel_callback)
    logger.info("Channel monitoring active")


async def main():
    """Main function to demonstrate subscription-based monitoring of a WebOS TV."""
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Create a client with a direct IP address
    # Replace with your TV's IP address
    # Alternatively, use discovery:
    # clients = await WebOSClient.discover()
    # client = clients[0]
    client = WebOSClient("192.168.1.100")
    logger.info("Connecting to TV at %s", client.ws_url)
    
    try:
        # Connect to the TV
        await client.connect()
        
        # Set up client (register if needed)
        if not await setup_client(client):
            return
        
        # Create control interfaces
        media = MediaControl(client)
        system = SystemControl(client)
        tv = TvControl(client)
        
        # Set up subscription monitors
        await monitor_volume(media)
        await monitor_power_state(system)
        await monitor_channel(tv)
        
        # Show a notification to indicate we're monitoring
        await system.notify("AsyncWebOSTV Monitoring Active")
        
        # Keep running until stopped
        logger.info("Monitoring active. Press Ctrl+C to stop.")
        await stop_event.wait()
        
        # Clean up subscriptions before exiting
        logger.info("Cleaning up subscriptions...")
        await media.unsubscribe_get_volume()
        await system.unsubscribe_power_state()
        await tv.unsubscribe_get_current_channel()
        
    except Exception as ex:
        logger.exception("Error: %s", ex)
    finally:
        # Close the connection when done
        logger.info("Closing connection...")
        await client.close()
        logger.info("Exiting.")


if __name__ == "__main__":
    asyncio.run(main()) 