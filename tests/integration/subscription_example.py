#!/usr/bin/env python3
"""
Example demonstrating how to use subscriptions in asyncwebostv to monitor TV events.
"""

import asyncio
import argparse
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

# Flag to indicate if the program should stop
stop_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle signals to gracefully shutdown."""
    logger.info("Received signal %s, shutting down...", signum)
    stop_event.set()


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
    
    # Subscribe to volume changes (NEW: now supports subscription!)
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
    
    # Subscribe to power state changes (NEW: now implemented!)
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
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Monitor a WebOS TV with subscriptions")
    parser.add_argument("--ip", help="IP address of the TV (required)")
    parser.add_argument("--secure", action="store_true", help="Use secure connection")
    parser.add_argument("--client-key", help="Client key for authentication (optional)")
    args = parser.parse_args()
    
    if not args.ip:
        logger.error("IP address is required. Use --ip to specify the TV's IP address.")
        return
    
    # Create client with provided IP address
    client = WebOSClient(args.ip, secure=args.secure, client_key=args.client_key)
    logger.info("Connecting to TV at %s", client.ws_url)
    
    try:
        # Connect to the TV
        await client.connect()
        
        # Set up client (register if needed)
        client_key = await setup_client(client, args.client_key)
        if not client_key:
            logger.error("Failed to set up client")
            return
            
        # Display the client key for future use
        logger.info("Client key for future use: %s", client_key)
        
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