#!/usr/bin/env python3
"""
Registration script with all possible permissions for LG WebOS TV.
This script attempts to register with an extensive list of permissions.
"""

import asyncio
import logging
import argparse
import json

from asyncwebostv.connection import WebOSClient, REGISTRATION_PAYLOAD

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

# Comprehensive permission list - combine all known permissions
ALL_PERMISSIONS = [
    "TEST_SECURE",
    "CONTROL_INPUT_TEXT",
    "CONTROL_MOUSE_AND_KEYBOARD",
    "READ_INSTALLED_APPS",
    "READ_LGE_SDX",
    "READ_NOTIFICATIONS",
    "SEARCH",
    "WRITE_SETTINGS",
    "WRITE_NOTIFICATION_ALERT",
    "CONTROL_POWER",
    "READ_CURRENT_CHANNEL",
    "READ_RUNNING_APPS",
    "READ_UPDATE_INFO",
    "UPDATE_FROM_REMOTE_APP",
    "READ_LGE_TV_INPUT_EVENTS",
    "READ_TV_CURRENT_TIME",
    "LAUNCH",
    "LAUNCH_WEBAPP",
    "APP_TO_APP",
    "CLOSE",
    "CONTROL_AUDIO",
    "CONTROL_INPUT_JOYSTICK",
    "CONTROL_INPUT_MEDIA_PLAYBACK",
    "CONTROL_INPUT_MEDIA_RECORDING",
    "CONTROL_INPUT_TV",
    "READ_APP_STATUS",
    "READ_INPUT_DEVICE_LIST",
    "READ_TV_CHANNEL_LIST",
    "READ_POWER_STATE",
    "CONTROL_TV_POWER",
    "READ_SETTINGS",
    "TEST_OPEN",
    "TEST_PROTECTED",
    "CONTROL_DISPLAY",
    "READ_NETWORK_STATE",
    "WRITE_NOTIFICATION_TOAST",
    "READ_COUNTRY_INFO",
    "CONTROL_TV_SCREEN",
    "CONTROL_TV_STANBY",
    "CONTROL_FAVORITE_GROUP",
    "CONTROL_USER_INFO",
    "CHECK_BLUETOOTH_DEVICE",
    "CONTROL_BLUETOOTH",
    "CONTROL_TIMER_INFO",
    "STB_INTERNAL_CONNECTION",
    "CONTROL_RECORDING",
    "READ_RECORDING_STATE",
    "WRITE_RECORDING_LIST",
    "READ_RECORDING_LIST",
    "READ_RECORDING_SCHEDULE",
    "WRITE_RECORDING_SCHEDULE",
    "READ_STORAGE_DEVICE_LIST",
    "READ_TV_PROGRAM_INFO",
    "CONTROL_BOX_CHANNEL",
    "READ_TV_ACR_AUTH_TOKEN",
    "READ_TV_CONTENT_STATE",
    "ADD_LAUNCHER_CHANNEL",
    "SET_CHANNEL_SKIP",
    "RELEASE_CHANNEL_SKIP",
    "CONTROL_CHANNEL_BLOCK",
    "DELETE_SELECT_CHANNEL",
    "CONTROL_CHANNEL_GROUP",
    "SCAN_TV_CHANNELS",
    "CONTROL_WOL"
]

async def register_with_all_permissions(ip_address, secure=False):
    """Register with the TV using all possible permissions."""
    client = WebOSClient(ip_address, secure=secure)
    
    # Connect to the TV
    logger.info("Connecting to %s", client.ws_url)
    await client.connect()
    
    # Create a modified registration payload with all permissions
    payload = json.loads(json.dumps(REGISTRATION_PAYLOAD))  # Deep copy
    
    # Set all permissions in both places
    payload["manifest"]["permissions"] = ALL_PERMISSIONS
    payload["manifest"]["signed"]["permissions"] = ALL_PERMISSIONS
    
    # Register with the TV using the modified payload
    logger.info("Registering with ALL permissions...")
    
    store = {}
    try:
        # Custom registration with modified payload
        response = await client.send_message(
            "register", 
            None, 
            payload
        )
        logger.info("Registration request sent. Please accept on TV screen.")
        
        # Wait for registration response
        success = False
        timeout = 60
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if response and "client-key" in response.get("payload", {}):
                client_key = response["payload"]["client-key"]
                store["client_key"] = client_key
                logger.info("Registration successful! Client key: %s", client_key)
                success = True
                break
            
            # Wait a bit for user input on TV
            await asyncio.sleep(1)
        
        if not success:
            logger.error("Registration failed - no response received within timeout")
    
    except Exception as ex:
        logger.exception("Error during registration: %s", ex)
    
    finally:
        # Close connection
        await client.close()
        logger.info("Connection closed")
    
    # Return client key if registration was successful
    return store.get("client_key")

async def verify_permissions(ip_address, client_key, secure=False):
    """Verify that permissions work with the registered client key."""
    logger.info("Verifying permissions with client key: %s", client_key)
    
    client = WebOSClient(ip_address, secure=secure, client_key=client_key)
    await client.connect()
    
    test_endpoints = [
        ("System Info", "ssap://system/getSystemInfo"),
        ("Volume", "ssap://audio/getVolume"),
        ("App List", "ssap://com.webos.applicationManager/listApps"),
        ("Channel List", "ssap://tv/getChannelList"),
        ("Input List", "ssap://tv/getExternalInputList"),
        ("Notification", "ssap://system.notifications/createToast", {"message": "Test Notification"})
    ]
    
    try:
        for test_name, uri, *payload_args in test_endpoints:
            payload = payload_args[0] if payload_args else None
            logger.info("Testing %s (%s)...", test_name, uri)
            
            try:
                response = await client.send_message("request", uri, payload)
                success = response and response.get("payload", {}).get("returnValue") == True
                logger.info("%s test %s", test_name, "SUCCESS" if success else "FAILED")
                if response:
                    logger.info("Response: %s", json.dumps(response))
            except Exception as ex:
                logger.error("%s test FAILED: %s", test_name, ex)
    
    finally:
        await client.close()
        logger.info("Verification completed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Register with LG WebOS TV using all permissions')
    parser.add_argument('ip_address', help='IP address of the WebOS TV')
    parser.add_argument('--verify-only', help='Skip registration and verify existing client key', action='store_true')
    parser.add_argument('--client-key', help='Client key for verification (only used with --verify-only)')
    parser.add_argument('--secure', help='Use secure connection', action='store_true')
    args = parser.parse_args()
    
    if args.verify_only:
        if not args.client_key:
            logger.error("--client-key is required when using --verify-only")
            return
        await verify_permissions(args.ip_address, args.client_key, args.secure)
    else:
        client_key = await register_with_all_permissions(args.ip_address, args.secure)
        if client_key:
            logger.info("Registration successful - verifying permissions...")
            await verify_permissions(args.ip_address, client_key, args.secure)
        else:
            logger.error("Registration failed - no client key obtained")

if __name__ == "__main__":
    asyncio.run(main()) 