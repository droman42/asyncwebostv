#!/usr/bin/env python3
"""
Test script to check permissions for LgTv class functions.
This example verifies that all required permissions are correctly configured.
"""

import asyncio
import logging
import argparse
from pprint import pformat

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    SystemControl, 
    MediaControl, 
    ApplicationControl, 
    InputControl,
    SourceControl,
    TvControl
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable debug logging for the connection module
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def setup_client(ip_address, secure=False, client_key=None):
    """Set up a client connection to the TV."""
    # Create client instance with client key
    client = WebOSClient(ip_address, secure=secure, client_key=client_key)
    
    # Connect to the TV
    logger.info("Connecting to %s", client.ws_url)
    await client.connect()
    
    # Register if needed
    store = {}
    if client_key:
        store["client_key"] = client_key
        # Always register with the TV when using an existing client key
        try:
            logger.info("Authenticating with existing client key...")
            async for status in client.register(store):
                if status == WebOSClient.REGISTERED:
                    logger.info("Successfully authenticated with existing client key")
        except Exception as ex:
            logger.error("Authentication with existing client key failed: %s", ex)
            return None, None
    else:
        logger.info("Registering with TV...")
        async for status in client.register(store):
            if status == WebOSClient.PROMPTED:
                logger.info("Please accept the connection request on your TV")
            elif status == WebOSClient.REGISTERED:
                logger.info("Registration successful!")
                client_key = store.get("client_key")
                logger.info("New client key: %s", client_key)
    
    return client, client_key

async def test_system_control(system):
    """Test SystemControl functions."""
    logger.info("=== Testing SystemControl ===")
    
    try:
        logger.info("Getting system info...")
        info = await system.info()
        logger.info("System Info: %s", pformat(info))
    except Exception as ex:
        logger.error("Error getting system info: %s", ex)
    
    try:
        logger.info("Sending notification...")
        await system.notify("Permission Test", "Testing system notifications")
        logger.info("Notification sent successfully")
    except Exception as ex:
        logger.error("Error sending notification: %s", ex)
    
    try:
        logger.info("Getting system settings...")
        settings = await system.get_settings()
        logger.info("System Settings: %s", pformat(settings))
    except Exception as ex:
        logger.error("Error getting system settings: %s", ex)

async def test_media_control(media):
    """Test MediaControl functions."""
    logger.info("=== Testing MediaControl ===")
    
    try:
        logger.info("Getting volume info...")
        volume = await media.get_volume()
        logger.info("Volume Info: %s", pformat(volume))
    except Exception as ex:
        logger.error("Error getting volume: %s", ex)
    
    try:
        logger.info("Getting audio status...")
        status = await media.get_audio_status()
        logger.info("Audio Status: %s", pformat(status))
    except Exception as ex:
        logger.error("Error getting audio status: %s", ex)
    
    # Don't actually change volume in test
    # logger.info("Setting volume to 10...")
    # await media.set_volume(10)

async def test_application_control(app_control):
    """Test ApplicationControl functions."""
    logger.info("=== Testing ApplicationControl ===")
    
    try:
        logger.info("Getting apps list...")
        apps = await app_control.list_apps()
        logger.info("Apps: %s", pformat(apps[:3]))  # Show only first 3 to avoid clutter
    except Exception as ex:
        logger.error("Error getting apps list: %s", ex)
    
    try:
        logger.info("Getting foreground app...")
        foreground = await app_control.get_current()
        logger.info("Foreground App: %s", pformat(foreground))
    except Exception as ex:
        logger.error("Error getting foreground app: %s", ex)

async def test_input_control(input_control):
    """Test InputControl functions."""
    logger.info("=== Testing InputControl ===")
    
    try:
        logger.info("Getting input list...")
        inputs = await input_control.list_inputs()
        logger.info("Inputs: %s", pformat(inputs))
    except Exception as ex:
        logger.error("Error getting input list: %s", ex)
    
    try:
        logger.info("Getting current input...")
        current = await input_control.get_input()
        logger.info("Current Input: %s", pformat(current))
    except Exception as ex:
        logger.error("Error getting current input: %s", ex)

async def test_source_control(source):
    """Test SourceControl functions."""
    logger.info("=== Testing SourceControl ===")
    
    try:
        logger.info("Getting source list...")
        sources = await source.list_sources()
        logger.info("Sources: %s", pformat(sources))
    except Exception as ex:
        logger.error("Error getting source list: %s", ex)
    
    try:
        logger.info("Getting current source...")
        current = await source.get_source_info()
        logger.info("Current Source: %s", pformat(current))
    except Exception as ex:
        logger.error("Error getting current source: %s", ex)

async def test_tv_control(tv):
    """Test TvControl functions."""
    logger.info("=== Testing TvControl ===")
    
    try:
        logger.info("Getting channel list...")
        channels = await tv.get_channels()
        if channels:
            logger.info("Channels: %s", pformat(channels[:3]))  # Show only first 3
        else:
            logger.info("No channels found or not currently on TV input")
    except Exception as ex:
        logger.error("Error getting channel list: %s", ex)
    
    try:
        logger.info("Getting current channel info...")
        channel = await tv.get_current_channel()
        logger.info("Current Channel: %s", pformat(channel))
    except Exception as ex:
        logger.error("Error getting current channel: %s", ex)

async def run_tests(ip_address, secure=False, client_key=None):
    """Run all permission tests."""
    try:
        # Setup client
        client, client_key = await setup_client(ip_address, secure, client_key)
        logger.info("Using client key: %s", client_key)
        
        # Create control instances
        system = SystemControl(client)
        media = MediaControl(client)
        app_control = ApplicationControl(client)
        input_control = InputControl(client)
        source = SourceControl(client)
        tv = TvControl(client)
        
        # Run tests
        await test_system_control(system)
        await asyncio.sleep(1)  # Add small delay between tests
        
        await test_media_control(media)
        await asyncio.sleep(1)
        
        await test_application_control(app_control)
        await asyncio.sleep(1)
        
        await test_input_control(input_control)
        await asyncio.sleep(1)
        
        await test_source_control(source)
        await asyncio.sleep(1)
        
        await test_tv_control(tv)
        
        # Display summary
        logger.info("\n=== Test Summary ===")
        logger.info("All permission tests completed. Check the logs for any errors.")
        logger.info("If you encountered '401 - insufficient permissions' errors, the permissions in REGISTRATION_PAYLOAD need updating.")
        logger.info("Client key for future use: %s", client_key)
        
    except Exception as ex:
        logger.exception("Error during tests: %s", ex)
    finally:
        # Close connection
        if 'client' in locals() and client:
            await client.close()
            logger.info("Connection closed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test permissions for LgTv class functions')
    parser.add_argument('ip_address', help='IP address of the WebOS TV')
    parser.add_argument('--secure', action='store_true', help='Use secure connection')
    parser.add_argument('--client-key', help='Client key for authentication')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        websockets_logger.setLevel(logging.DEBUG)
    
    logger.info("Starting permission tests with %s connection", "secure" if args.secure else "non-secure")
    
    await run_tests(args.ip_address, args.secure, args.client_key)

if __name__ == "__main__":
    asyncio.run(main()) 