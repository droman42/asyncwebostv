#!/usr/bin/env python3
"""
Test for the InputControl WebSocket connection handling.

This test verifies that:
1. The InputControl class properly establishes a WebSocket connection
2. Button commands can be sent successfully
3. The connection is properly closed when the client is shut down
4. Secure connections work with certificates
"""

import asyncio
import argparse
import logging
import sys
from typing import Dict, Any, Optional, Tuple
import ssl

from asyncwebostv.connection import WebOSClient
from asyncwebostv.client import WebOSTV, SecureWebOSTV
from asyncwebostv.controls import InputControl, ApplicationControl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Enable debug logging for the connection module
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def setup_client(ip_address: str, client_key: Optional[str] = None) -> Tuple[Optional[WebOSClient], Optional[str]]:
    """Set up a client connection to the TV.
    
    Args:
        ip_address: TV's IP address
        client_key: Optional client key for authentication
        
    Returns:
        Tuple of (WebOSClient, client_key)
    """
    # Create client instance
    client = WebOSClient(ip_address, client_key=client_key)
    
    # Connect to the TV
    logger.info(f"Connecting to {client.ws_url}")
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
            logger.error(f"Authentication with existing client key failed: {ex}")
            return None, None
    else:
        logger.info("Registering with TV...")
        async for status in client.register(store):
            if status == WebOSClient.PROMPTED:
                logger.info("Please accept the connection request on your TV")
            elif status == WebOSClient.REGISTERED:
                logger.info("Registration successful!")
                client_key = store.get("client_key")
                logger.info(f"New client key: {client_key}")
    
    return client, client_key

async def test_button_commands(ip_address: str, client_key: Optional[str] = None) -> bool:
    """Test sending button commands to the TV.
    
    Args:
        ip_address: TV's IP address
        client_key: Optional client key for authentication
    
    Returns:
        True if all commands succeeded, False otherwise
    """
    # Set up client
    client, client_key = await setup_client(ip_address, client_key)
    if not client:
        logger.error("Failed to set up client")
        return False
    
    try:
        # Create input control
        input_control = InputControl(client)
        app_control = ApplicationControl(client)
        
        # Test button commands
        success = True
        try:
            # First command will establish the WebSocket connection
            logger.info("Testing HOME button command...")
            await input_control.home()
            logger.info("HOME button command successful")
            
            # Wait for user to confirm the HOME button worked
            await asyncio.sleep(2)
            
            # Test a few more buttons with the same connection
            logger.info("Testing UP button command...")
            await input_control.up()
            logger.info("UP button command successful")
            
            await asyncio.sleep(1)
            
            logger.info("Testing DOWN button command...")
            await input_control.down()
            logger.info("DOWN button command successful")
            
            await asyncio.sleep(1)
            
            logger.info("Testing LEFT button command...")
            await input_control.left()
            logger.info("LEFT button command successful")
            
            await asyncio.sleep(1)
            
            logger.info("Testing RIGHT button command...")
            await input_control.right()  
            logger.info("RIGHT button command successful")
            
            await asyncio.sleep(1)
            
            logger.info("Testing ENTER button command...")
            await input_control.enter()
            logger.info("ENTER button command successful")
            
            # Alternative implementation test (uncomment if needed)
            # logger.info("Testing HOME via application launch...")
            # await app_control.launch("com.webos.app.home")
            # logger.info("HOME app launch successful")
            
        except Exception as e:
            logger.error(f"Button command error: {e}")
            success = False
        
        # Explicitly close the input control's WebSocket connection
        try:
            logger.info("Closing InputControl WebSocket connection...")
            await input_control.close()
            logger.info("InputControl WebSocket connection closed successfully")
        except Exception as e:
            logger.error(f"Error closing InputControl connection: {e}")
            success = False
        
        return success
    finally:
        # Close the main client connection
        if client:
            await client.close()
            logger.info("Client connection closed")

async def test_with_webostv(host: str, client_key: Optional[str] = None) -> bool:
    """Test with the high-level WebOSTV API.
    
    Args:
        host: TV hostname or IP address
        client_key: Optional client key
        
    Returns:
        True if test was successful, False otherwise
    """
    tv = WebOSTV(host, client_key=client_key)
    
    try:
        # Connect to the TV (this now handles registration automatically)
        logger.info(f"Connecting to TV at {host}...")
        await tv.connect()
        
        # Test basic button commands
        logger.info("Testing HOME button...")
        await tv.input.home()
        logger.info("HOME button command successful")
        
        await asyncio.sleep(2)
        
        logger.info("Testing UP button...")
        await tv.input.up()
        logger.info("UP button command successful")
        
        await asyncio.sleep(1)
        
        logger.info("Testing DOWN button...")
        await tv.input.down()
        logger.info("DOWN button command successful")
        
        # Close connection properly
        logger.info("Closing connection...")
        await tv.close()
        logger.info("Connection closed")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        try:
            await tv.close()
        except:
            pass
        return False

async def test_with_secure_webostv(
    host: str, 
    client_key: Optional[str] = None,
    cert_file: Optional[str] = None,
    verify_ssl: bool = True,
    ssl_options: Optional[Dict[str, Any]] = None
) -> bool:
    """Test with the high-level SecureWebOSTV API.
    
    Args:
        host: TV hostname or IP address
        client_key: Optional client key
        cert_file: Path to the TV's certificate file
        verify_ssl: Whether to verify the SSL certificate
        ssl_options: Additional SSL options
        
    Returns:
        True if test was successful, False otherwise
    """
    # Create SSL context if needed
    ssl_context = None
    if not verify_ssl and not cert_file:
        logger.info("Creating SSL context with verification disabled")
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    
    # Create the secure TV client
    tv = SecureWebOSTV(
        host=host, 
        client_key=client_key,
        cert_file=cert_file,
        ssl_context=ssl_context,
        verify_ssl=verify_ssl,
        ssl_options=ssl_options
    )
    
    try:
        # Connect to the TV (this handles registration automatically)
        logger.info(f"Connecting securely to TV at {host}...")
        await tv.connect()
        logger.info("Secure connection established successfully!")
        
        # Test basic button commands
        logger.info("Testing HOME button...")
        await tv.input.home()
        logger.info("HOME button command successful")
        
        await asyncio.sleep(2)
        
        logger.info("Testing UP button...")
        await tv.input.up()
        logger.info("UP button command successful")
        
        await asyncio.sleep(1)
        
        logger.info("Testing DOWN button...")
        await tv.input.down()
        logger.info("DOWN button command successful")
        
        # Close connection properly
        logger.info("Closing secure connection...")
        await tv.close()
        logger.info("Secure connection closed")
        
        return True
        
    except Exception as e:
        logger.error(f"Secure test failed: {e}")
        try:
            await tv.close()
        except:
            pass
        return False

async def extract_and_save_certificate(host: str, save_path: str) -> bool:
    """Extract and save the TV's SSL certificate.
    
    Args:
        host: TV hostname or IP address
        save_path: Path to save the certificate to
        
    Returns:
        True if successful, False otherwise
    """
    from asyncwebostv.secure_connection import extract_certificate
    
    try:
        logger.info(f"Extracting certificate from {host}...")
        cert = await extract_certificate(host, output_file=save_path)
        logger.info(f"Certificate saved to {save_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract certificate: {e}")
        return False

async def main():
    """Main entry point for the test."""
    parser = argparse.ArgumentParser(description='Test InputControl WebSocket connection')
    parser.add_argument('--host', required=True, help='TV hostname or IP address')
    parser.add_argument('--client-key', help='Client key for authentication')
    parser.add_argument('--use-low-level', action='store_true', 
                       help='Use low-level WebOSClient API directly')
    parser.add_argument('--use-secure', action='store_true',
                       help='Use SecureWebOSTV with SSL/TLS')
    parser.add_argument('--cert-file', help='Path to TV certificate file for secure connection')
    parser.add_argument('--no-verify-ssl', action='store_true', 
                       help='Disable SSL certificate verification')
    parser.add_argument('--extract-cert', help='Extract and save TV certificate to specified path')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        websockets_logger.setLevel(logging.DEBUG)
    
    # Extract certificate if requested
    if args.extract_cert:
        success = await extract_and_save_certificate(args.host, args.extract_cert)
        return 0 if success else 1
    
    # Main testing
    if args.use_secure:
        # Test with secure connection
        logger.info("Testing with secure connection")
        ssl_options = None
        success = await test_with_secure_webostv(
            host=args.host,
            client_key=args.client_key,
            cert_file=args.cert_file,
            verify_ssl=not args.no_verify_ssl,
            ssl_options=ssl_options
        )
    elif args.use_low_level:
        # Test with low-level API
        success = await test_button_commands(args.host, args.client_key)
    else:
        # Test with high-level API (unsecured)
        success = await test_with_webostv(args.host, args.client_key)
    
    return 0 if success else 1

if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Test interrupted")
        sys.exit(1) 