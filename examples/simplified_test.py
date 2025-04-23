#!/usr/bin/env python3
"""
Simplified test script for the AsyncWebOSTV library after PyWebOSTV compatibility fixes.
"""

import asyncio
import logging
import argparse

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import SystemControl, MediaControl

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_test(ip_address, secure=False, client_key=None):
    """Run a simple test using the PyWebOSTV-compatible fixes."""
    store = {}
    if client_key:
        store["client_key"] = client_key
        
    # Create client instance with client key
    client = WebOSClient(ip_address, secure=secure, client_key=client_key)
    
    try:
        # Connect to the TV
        logger.info("Connecting to %s", client.ws_url)
        await client.connect()
        
        # Register with TV if needed
        if not client_key:
            logger.info("Registering with TV...")
            try:
                async for status in client.register(store):
                    if status == WebOSClient.PROMPTED:
                        logger.info("Please accept the connection request on your TV")
                    elif status == WebOSClient.REGISTERED:
                        logger.info("Registration successful!")
                
                client_key = store.get("client_key")
                if client_key:
                    logger.info("Obtained client key: %s", client_key)
                else:
                    logger.error("Registration completed but no client key was obtained")
                    return
            except Exception as ex:
                logger.error("Registration failed: %s", ex)
                return
        else:
            logger.info("Using provided client key: %s", client_key)
            # Always register with the TV when using an existing client key
            try:
                async for status in client.register(store):
                    if status == WebOSClient.REGISTERED:
                        logger.info("Successfully authenticated with existing client key")
            except Exception as ex:
                logger.error("Authentication with existing client key failed: %s", ex)
                return
            
        # Create control interfaces
        system = SystemControl(client)
        media = MediaControl(client)
        
        # Test System Info
        logger.info("Getting system info...")
        try:
            info = await system.info()
            logger.info("System Info: %s", info)
        except Exception as ex:
            logger.error("Failed to get system info: %s", ex)
        
        # Test Volume
        logger.info("Getting volume...")
        try:
            volume = await media.get_volume()
            logger.info("Current Volume: %s", volume)
        except Exception as ex:
            logger.error("Failed to get volume: %s", ex)
        
        # Test Notification
        logger.info("Sending notification...")
        try:
            result = await system.notify("Test", "AsyncWebOSTV Test")
            logger.info("Notification sent: %s", result)
        except Exception as ex:
            logger.error("Failed to send notification: %s", ex)
            
    except Exception as ex:
        logger.exception("Error during test: %s", ex)
    finally:
        # Close the connection
        await client.close()
        logger.info("Connection closed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test the AsyncWebOSTV library with PyWebOSTV compatibility fixes')
    parser.add_argument('ip_address', help='IP address of the WebOS TV')
    parser.add_argument('--secure', action='store_true', help='Use secure connection')
    parser.add_argument('--client-key', help='Client key for authentication')
    args = parser.parse_args()
    
    await run_test(args.ip_address, args.secure, args.client_key)

if __name__ == "__main__":
    asyncio.run(main()) 