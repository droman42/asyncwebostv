#!/usr/bin/env python3
"""
Test script for sending notifications to WebOS TV.
"""

import asyncio
import logging
import argparse

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import SystemControl

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def test_notifications(ip_address, client_key=None, secure=False):
    """Test sending notifications to the TV."""
    try:
        # Initialize client
        client = WebOSClient(ip_address, secure=secure)
        
        # Connect to TV
        logger.info("Connecting to TV at %s", ip_address)
        await client.connect()
        
        # Register if needed
        if not client_key:
            logger.info("Registering with TV...")
            store = {}
            async for status in client.register(store):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection request on your TV")
                elif status == WebOSClient.REGISTERED:
                    logger.info("Registration successful!")
                    client_key = store.get("client_key")
                    logger.info("New client key: %s", client_key)
        else:
            store = {"client_key": client_key}
            logger.info("Using existing client key")
        
        logger.info("Using client key: %s", client_key)
        
        # Create system control
        system = SystemControl(client)
        
        # Attempt to create toast notification
        logger.info("Testing toast notification...")
        try:
            await system.notify("Notification Test", "This is a test notification")
            logger.info("Notification sent successfully!")
        except Exception as ex:
            logger.error("Failed to send notification: %s", ex)
        
        # Directly use URI if available
        if hasattr(client, "send_message"):
            logger.info("Testing direct URI call for notification...")
            try:
                result = await client.send_message("request", 
                                                  "ssap://system.notifications/createToast", 
                                                  {"message": "Direct API Test"})
                logger.info("Direct notification result: %s", result)
            except Exception as ex:
                logger.error("Failed to send direct notification: %s", ex)
        
    except Exception as ex:
        logger.exception("Error during test: %s", ex)
    finally:
        if 'client' in locals() and client:
            await client.close()
            logger.info("Connection closed")

async def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Test WebOS TV notifications')
    parser.add_argument('ip_address', help='IP address of the WebOS TV')
    parser.add_argument('--client-key', help='Client key for authentication')
    parser.add_argument('--secure', action='store_true', help='Use secure connection')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        websockets_logger.setLevel(logging.DEBUG)
    
    await test_notifications(args.ip_address, args.client_key, args.secure)

if __name__ == "__main__":
    asyncio.run(main()) 