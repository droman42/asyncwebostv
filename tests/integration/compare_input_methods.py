#!/usr/bin/env python3
"""
Compare input methods between asyncwebostv and PyWebOSTV to diagnose why
button commands are received but not causing TV reactions.
"""

import os
import sys
import asyncio
import argparse
import logging
import json
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add imports for asyncwebostv
try:
    from asyncwebostv.connection import WebOSClient
    from asyncwebostv.controls import InputControl
except ImportError:
    logger.error("asyncwebostv not installed. Run: pip install asyncwebostv")
    asyncwebostv_available = False
else:
    asyncwebostv_available = True

# Add imports for PyWebOSTV if available
try:
    from pywebostv.connection import WebOSClient as PyWebOSClient
    from pywebostv.controls import InputControl as PyInputControl
except ImportError:
    logger.error("PyWebOSTV not installed. To compare, install: pip install pywebostv")
    pywebostv_available = False
else:
    pywebostv_available = True

# Function to pause and allow user to observe TV reaction
async def pause_for_observation(seconds: int = 2, message: str = ""):
    """Pause execution to allow observation of TV reaction."""
    if message:
        logger.info(message)
    logger.info(f"Pausing for {seconds} seconds to observe TV...")
    await asyncio.sleep(seconds)

async def test_async_webostv(ip_address: str, client_key: Optional[str] = None) -> None:
    """Test button commands using asyncwebostv."""
    if not asyncwebostv_available:
        logger.error("Cannot test asyncwebostv as it's not installed")
        return
        
    logger.info("=== Testing asyncwebostv implementation ===")
    
    # Create and connect client
    client = WebOSClient(ip_address, client_key=client_key)
    await client.connect()
    
    try:
        # Register if needed
        store = {}
        if client_key:
            store["client_key"] = client_key
            
        logger.info("Registering with TV...")
        async for status in client.register(store):
            if status == WebOSClient.PROMPTED:
                logger.info("Please accept the connection request on your TV")
            elif status == WebOSClient.REGISTERED:
                logger.info("Registration successful!")
                if "client_key" in store:
                    logger.info(f"Client key: {store['client_key']}")
        
        # Create input control
        input_control = InputControl(client)
        
        # Test the new connect_input method directly (this is the core improvement)
        logger.info("\nMethod 0: Testing direct connect_input() method (new implementation)")
        try:
            logger.info("Explicitly connecting input using connect_input()...")
            await input_control.connect_input()
            
            logger.info("Connection successful, sending HOME button...")
            await input_control.home()
            await pause_for_observation(3, "Did the HOME button work with connect_input method?")
            
            # Test a second button to confirm consistent behavior
            logger.info("Sending UP button after explicit connect_input...")
            await input_control.up()
            await pause_for_observation(2, "Did the UP button work after connect_input?")
            
            # Test disconnect and reconnect
            logger.info("Testing disconnect_input() and reconnect...")
            await input_control.disconnect_input()
            await input_control.connect_input()
            
            logger.info("After reconnection, sending DOWN button...")
            await input_control.down()
            await pause_for_observation(2, "Did the DOWN button work after reconnection?")
            
        except Exception as e:
            logger.error(f"Error with connect_input method: {e}")
        
        # Method 1: Standard Input Control method
        logger.info("\nMethod 1: Standard InputControl.home() method")
        try:
            logger.info("Sending HOME button using InputControl...")
            await input_control.home()
            await pause_for_observation(3, "Did the HOME button work with standard method?")
        except Exception as e:
            logger.error(f"Error sending HOME via InputControl: {e}")
        
        # Method 2: Direct service call
        logger.info("\nMethod 2: Direct service call method")
        try:
            logger.info("Sending HOME button using direct service call...")
            button_payload = {
                "buttonName": "HOME"
            }
            response = await client.send_message(
                'request', 
                'ssap://com.webos.service.networkinput/sendInputButton', 
                button_payload
            )
            logger.info(f"Direct service call response: {json.dumps(response, indent=2) if response else 'None'}")
            await pause_for_observation(3, "Did the HOME button work with direct service call?")
        except Exception as e:
            logger.error(f"Error sending HOME via direct service: {e}")
        
        # Method 3: Try to connect to pointer socket first (if available)
        logger.info("\nMethod 3: Pointer socket connection method")
        try:
            logger.info("Trying to get pointer socket information...")
            response = await client.send_message(
                'request', 
                'ssap://com.webos.service.networkinput/getPointerInputSocket', 
                {}
            )
            logger.info(f"Pointer socket response: {json.dumps(response, indent=2) if response else 'None'}")
            
            if response and 'payload' in response and 'socketPath' in response['payload']:
                socket_path = response['payload']['socketPath']
                logger.info(f"Got pointer socket path: {socket_path}")
                
                # Connect to the socket
                logger.info("Establishing direct connection to input socket...")
                await client.send_message('register', None, None, uri=socket_path)
                
                # Send button with PyWebOSTV format
                logger.info("Sending HOME button using pointer socket...")
                formatted_payload = "type:button\nname:HOME\n\n"
                await client.send_message('request', None, None, 
                                         uri=socket_path,
                                         payload_override=formatted_payload)
                await pause_for_observation(3, "Did the HOME button work with pointer socket?")
            else:
                logger.warning("Could not get valid pointer socket path from TV")
        except Exception as e:
            logger.error(f"Error with pointer socket method: {e}")
            
        # Method 4: Launch home app directly as workaround
        logger.info("\nMethod 4: Launch HOME app as alternative")
        try:
            logger.info("Testing alternative - Launch HOME app directly...")
            from asyncwebostv.controls import ApplicationControl
            app_control = ApplicationControl(client)
            await app_control.launch("com.webos.app.home")
            await pause_for_observation(3, "Did launching HOME app work?")
        except Exception as e:
            logger.error(f"Error launching HOME app: {e}")
            
        # Also try UP and DOWN buttons with standard method
        logger.info("\nTesting UP/DOWN buttons with standard method")
        try:
            logger.info("Sending UP button...")
            await input_control.up()
            await pause_for_observation(2, "Did the UP button work?")
            
            logger.info("Sending DOWN button...")
            await input_control.down()
            await pause_for_observation(2, "Did the DOWN button work?")
        except Exception as e:
            logger.error(f"Error sending UP/DOWN: {e}")
            
    finally:
        # Close connection
        if 'input_control' in locals() and input_control:
            await input_control.close()
        await client.close()
        logger.info("asyncwebostv test completed\n")

async def test_pywebostv(ip_address: str, client_key: Optional[str] = None) -> None:
    """Test button commands using PyWebOSTV."""
    if not pywebostv_available:
        logger.error("Cannot test PyWebOSTV as it's not installed")
        return
        
    logger.info("=== Testing PyWebOSTV implementation ===")
    
    # Create and connect client
    client = PyWebOSClient(ip_address)
    client.connect()
    
    try:
        # Register if needed
        store = {}
        if client_key:
            store["client_key"] = client_key
            
        logger.info("Registering with TV...")
        for status in client.register(store):
            if status == PyWebOSClient.PROMPTED:
                logger.info("Please accept the connection request on your TV")
            elif status == PyWebOSClient.REGISTERED:
                logger.info("Registration successful!")
                if "client_key" in store:
                    logger.info(f"Client key: {store['client_key']}")
        
        # Create input control
        input_control = PyInputControl(client)
        
        # Connect input explicitly (PyWebOSTV needs this)
        logger.info("Connecting input control...")
        input_control.connect_input()
        
        # Test button commands with pauses
        logger.info("Sending HOME button...")
        input_control.home()
        await pause_for_observation(3, "Did the HOME button work?")
        
        logger.info("Sending UP button...")
        input_control.up()
        await pause_for_observation(2, "Did the UP button work?")
        
        logger.info("Sending DOWN button...")
        input_control.down()
        await pause_for_observation(2, "Did the DOWN button work?")
        
    finally:
        # Disconnect input explicitly
        if 'input_control' in locals():
            try:
                input_control.disconnect_input()
            except:
                pass
                
        # Close connection
        client.close()
        logger.info("PyWebOSTV test completed\n")

async def dump_packet_formats():
    """Debug helper to show the different packet formats used by each library."""
    
    logger.info("=== Button Command Packet Format Comparison ===")
    
    # asyncwebostv format
    logger.info("asyncwebostv formatted packet for HOME button:")
    payload = {"type": "button", "name": "HOME"}
    formatted_payload = ""
    for key, value in payload.items():
        formatted_payload += f"{key}:{value}\n"
    formatted_payload += "\n"
    logger.info(f"[asyncwebostv] Format:\n{formatted_payload}")
    
    # PyWebOSTV format (needs inspection of the actual library)
    logger.info("PyWebOSTV uses the following format for button commands:")
    if pywebostv_available:
        try:
            from pywebostv.controls import InputControl
            # We can't call the private method directly, but we can describe the format
            logger.info("[PyWebOSTV] Format (from code inspection):")
            logger.info("type:button\nname:HOME\n\n")
        except:
            logger.error("Could not inspect PyWebOSTV format")
    else:
        logger.info("[PyWebOSTV] Format (from code inspection):")
        logger.info("type:button\nname:HOME\n\n")
    
async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Compare input methods between libraries')
    parser.add_argument('--host', required=True, help='TV IP address')
    parser.add_argument('--client-key', help='Client key for authentication')
    parser.add_argument('--async-only', action='store_true', help='Only test asyncwebostv')
    parser.add_argument('--py-only', action='store_true', help='Only test PyWebOSTV')
    parser.add_argument('--debug', action='store_true', help='Show debug information')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Dump packet formats for comparison
    await dump_packet_formats()
    
    # Run requested tests
    if not args.py_only:
        await test_async_webostv(args.host, args.client_key)
    
    if not args.async_only and pywebostv_available:
        await test_pywebostv(args.host, args.client_key)
        
    logger.info("Testing completed. Check the logs for results.")
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted")
        sys.exit(1) 