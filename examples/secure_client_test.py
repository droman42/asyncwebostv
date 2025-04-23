#!/usr/bin/env python3
"""
Test script for secure connections to WebOS TV.
"""

import asyncio
import logging
import argparse
import os
import sys
import ssl

from asyncwebostv.client import SecureWebOSTV
from asyncwebostv.secure_connection import extract_certificate

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

def create_custom_ssl_context(cert_file=None, verify_hostname=False):
    """Create a custom SSL context that might not verify hostname."""
    context = ssl.create_default_context()
    context.check_hostname = verify_hostname
    
    if cert_file:
        try:
            context.load_verify_locations(cert_file)
            logger.info(f"Loaded certificate from {cert_file}")
        except Exception as e:
            logger.warning(f"Failed to load certificate: {e}")
    
    return context

async def test_secure_connection(ip_address, port=3001, client_key=None, cert_file=None, skip_cert_verify=False, verify_hostname=False):
    """Test a secure connection to the TV."""
    try:
        # Extract certificate if needed
        if not cert_file and not skip_cert_verify:
            logger.info("No certificate file provided. Extracting certificate from TV...")
            cert_path = f"{ip_address.replace('.', '_')}_cert.pem"
            cert_pem = await extract_certificate(ip_address, port, cert_path)
            logger.info(f"Certificate extracted and saved to {cert_path}")
            cert_file = cert_path
        
        # Create custom SSL context if requested
        ssl_context = None
        if cert_file and not skip_cert_verify:
            ssl_context = create_custom_ssl_context(cert_file, verify_hostname)
            logger.info(f"Created custom SSL context with hostname verification {'enabled' if verify_hostname else 'disabled'}")
        
        # Initialize secure client
        client = SecureWebOSTV(
            host=ip_address,
            port=port,
            client_key=client_key,
            cert_file=cert_file if not ssl_context else None,
            ssl_context=ssl_context,
            verify_ssl=not skip_cert_verify
        )
        
        # Connect to TV
        logger.info(f"Connecting to TV at wss://{ip_address}:{port}/")
        await client.connect()
        
        # Always register with the TV, even if we have a client key
        # This is needed to ensure a proper session is established
        logger.info("Registering with TV...")
        store = {}
        if client_key:
            store["client_key"] = client_key
            
        try:
            # Pass store to register method to manually handle registration
            async for status in client.client.register(store):
                if status == client.client.PROMPTED:
                    logger.info("Please accept the connection on the TV")
                elif status == client.client.REGISTERED:
                    logger.info("Registration successful!")
                    client_key = store.get("client_key")
            logger.info(f"Registration successful! Client key: {client_key}")
        except Exception as e:
            logger.warning(f"Registration error: {e}")
            if client_key:
                logger.info("Continuing with existing client key...")
            else:
                raise
        
        # Wait a bit to make sure the registration is processed
        await asyncio.sleep(1)
        
        # Test getting system info
        logger.info("Getting system info...")
        # Create a response queue to wait for the response
        system_queue = await client.client.send_message("request", "ssap://system/getSystemInfo", get_queue=True)
        
        # Wait for the response
        try:
            system_info = await asyncio.wait_for(system_queue.get(), timeout=5)
            logger.info(f"System info: {system_info}")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for system info response")
        
        # Test sending a notification
        logger.info("Sending test notification...")
        toast_queue = await client.client.send_message(
            "request", 
            "ssap://system.notifications/createToast", 
            payload={"message": "Secure connection test"},
            get_queue=True
        )
        
        # Wait for the response
        try:
            toast_result = await asyncio.wait_for(toast_queue.get(), timeout=5)
            logger.info(f"Notification result: {toast_result}")
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for notification response")
        
        # Close the connection
        await client.client.close()
        logger.info("Test completed successfully!")
        
        return client_key
        
    except Exception as e:
        logger.error(f"Error during secure connection test: {e}", exc_info=True)
        return None

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test secure connection to WebOS TV")
    parser.add_argument("ip", help="IP address of the TV")
    parser.add_argument("--port", type=int, default=3001, help="WebSocket port (default: 3001)")
    parser.add_argument("--client-key", help="Client key for authentication")
    parser.add_argument("--cert-file", help="Path to certificate file for verification")
    parser.add_argument("--skip-cert-verify", action="store_true", help="Skip certificate verification")
    parser.add_argument("--verify-hostname", action="store_true", help="Verify hostname in certificate")
    
    return parser.parse_args()

async def main():
    """Main entry point."""
    args = parse_args()
    
    result = await test_secure_connection(
        args.ip,
        port=args.port,
        client_key=args.client_key,
        cert_file=args.cert_file,
        skip_cert_verify=args.skip_cert_verify,
        verify_hostname=args.verify_hostname
    )
    
    if result:
        logger.info(f"Successfully connected to TV. Client key: {result}")
        return 0
    else:
        logger.error("Failed to connect to TV.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 