#!/usr/bin/env python3
"""
Test script for the AsyncWebOSTV library.
This example demonstrates how to use the WebOSTV client without storing keys to files.
"""

import asyncio
import logging
import argparse
from pprint import pformat

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import SystemControl, MediaControl

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable debug logging for the connection module
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def setup_client(ip_address, secure=False, client_key=None, force_register=False):
    """Set up a client connection to the TV, without persistent storage.
    
    Args:
        ip_address: TV's IP address
        secure: Whether to use secure connection
        client_key: Optional client key for authentication
        force_register: Force registration even if client key is provided
        
    Returns:
        Tuple of (client, client_key)
    """
    # Create client instance
    client = WebOSClient(ip_address, secure=secure)
    
    # Connect to the TV
    logger.info("Connecting to %s", client.ws_url)
    await client.connect()
    
    # Register the client if no key is available, it's invalid, or force_register is True
    if not client_key or force_register:
        logger.info("Registering with TV...")
        try:
            # Store for collecting client key
            store = {}
            if client_key and not force_register:
                store["client_key"] = client_key
            
            # Set a timeout for registration (in seconds)
            registration_timeout = 120  # 2 minutes
            
            async for status in client.register(store, timeout=registration_timeout):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection request on your TV")
                elif status == WebOSClient.REGISTERED:
                    logger.info("Registration successful!")
            
            # Extract the new client key
            client_key = store.get("client_key")
            if client_key:
                logger.info("Obtained new client key: %s", client_key)
            else:
                logger.error("Registration completed but no client key was obtained")
                
        except Exception as ex:
            logger.error("Registration failed: %s", ex)
            await client.close()
            return None, None
    
    return client, client_key

async def run_test(ip_address, secure=False, client_key=None, force_register=False):
    """Run a test of the TV client.
    
    Args:
        ip_address: TV's IP address
        secure: Whether to use secure connection
        client_key: Optional client key for authentication
        force_register: Force registration even if client key is provided
    """
    try:
        logger.info("Setting up client...")
        client, client_key = await setup_client(ip_address, secure, client_key, force_register)
        if not client:
            logger.error("Failed to set up client")
            return
        
        # Display the client key that should be saved externally if needed
        logger.info("Active client key for future use: %s", client_key)
        
        # Create control interfaces
        system = SystemControl(client)
        media = MediaControl(client)
        
        # Get system info
        logger.info("Getting system info...")
        info = await system.info()
        logger.info("System Info:\n%s", pformat(info))
        
        # Get current volume
        try:
            logger.info("Getting current volume...")
            volume = await media.get_volume()
            logger.info("Current Volume: %s", volume)
        except Exception as ex:
            logger.error("Failed to get volume: %s", ex)
        
        # Show a notification on the TV
        try:
            logger.info("Sending notification to TV...")
            await system.notify("AsyncWebOSTV Test", "Connection successful!")
            logger.info("Displayed notification on TV")
        except Exception as ex:
            logger.error("Failed to show notification: %s", ex)
        
        # Wait a moment before disconnecting
        await asyncio.sleep(3)
        
    except Exception as ex:
        logger.exception("Error during test: %s", ex)
    finally:
        # Close the connection
        if 'client' in locals() and client:
            await client.close()
            logger.info("Connection closed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test the AsyncWebOSTV library')
    parser.add_argument('ip_address', help='IP address of the WebOS TV')
    parser.add_argument('--secure', action='store_true', help='Use secure connection')
    parser.add_argument('--client-key', help='Client key for authentication (optional)')
    parser.add_argument('--force-register', action='store_true', help='Force registration even if a client key is provided')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        websockets_logger.setLevel(logging.DEBUG)
    
    logger.info("Starting test with %s connection", "secure" if args.secure else "non-secure")
    logger.info("Client key provided: %s", args.client_key if args.client_key else "None")
    
    await run_test(args.ip_address, args.secure, args.client_key, args.force_register)
    
    if not args.client_key:
        logger.info("If you want to avoid the registration prompt in the future, use the client key shown above with --client-key")

if __name__ == "__main__":
    asyncio.run(main()) 