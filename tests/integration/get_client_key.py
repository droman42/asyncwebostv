#!/usr/bin/env python3
"""
Simple script to get a client key from a WebOS TV.
This is useful for first-time setup.
"""

import asyncio
import logging
import argparse
import sys
import os

from asyncwebostv.client import WebOSTV, SecureWebOSTV

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
websockets_logger = logging.getLogger('asyncwebostv.connection')
websockets_logger.setLevel(logging.DEBUG)

async def extract_certificate(ip_address, save_path):
    """Extract the SSL certificate from a WebOS TV."""
    logger.info(f"Extracting certificate from {ip_address}...")
    
    client = SecureWebOSTV(ip_address, verify_ssl=False)
    try:
        cert_pem = await client.get_certificate(save_path)
        logger.info(f"Certificate saved to {save_path}")
        return True
    except Exception as e:
        logger.error(f"Error extracting certificate: {e}")
        return False
    finally:
        await client.close()

async def get_client_key(ip_address, secure=False, cert_path=None):
    """Get a client key from a WebOS TV."""
    client = None
    
    try:
        # Create the client based on connection type
        if secure and cert_path:
            logger.info(f"Creating secure connection with certificate: {cert_path}")
            client = SecureWebOSTV(ip_address, cert_file=cert_path, verify_ssl=False)
        elif secure:
            logger.info(f"Creating secure connection without certificate verification")
            client = SecureWebOSTV(ip_address, verify_ssl=False)
        else:
            logger.info(f"Creating standard connection")
            client = WebOSTV(ip_address)
        
        # Connect to the TV
        logger.info(f"Connecting to {ip_address}...")
        await client.connect()
        
        # Register with the TV
        logger.info("Registering with TV. Look at your TV and accept the connection request...")
        
        # Use the register method - client.register() returns the client_key directly
        store = {}
        client_key = await client.register()
        
        if client_key:
            logger.info("Registration successful!")
            logger.info(f"Client key: {client_key}")
            return client_key
        
        logger.error("Failed to get client key - no confirmation from TV")
        return None
    except Exception as e:
        logger.error(f"Error connecting to TV: {e}")
        return None
    finally:
        # Disconnect
        if client:
            await client.close()
            logger.info("Connection closed")

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Get a client key from a WebOS TV')
    parser.add_argument('ip', help='IP address of the TV')
    parser.add_argument('--secure', action='store_true', help='Use secure connection (port 3001)')
    parser.add_argument('--cert', dest='cert_path', help='Path to certificate file for SSL verification')
    parser.add_argument('--get-cert', dest='get_cert_path', help='Extract TV certificate and save to the specified path')
    args = parser.parse_args()
    
    # Handle certificate extraction if requested
    if args.get_cert_path:
        success = await extract_certificate(args.ip, args.get_cert_path)
        if success:
            print(f"\nSUCCESS! Certificate saved to {args.get_cert_path}")
            print(f"You can now use it with: python {os.path.basename(__file__)} {args.ip} --secure --cert {args.get_cert_path}")
            return 0
        else:
            print("\nFAILED to extract certificate.")
            return 1
    
    # Get client key
    client_key = await get_client_key(args.ip, args.secure, args.cert_path)
    
    if client_key:
        print(f"\nSUCCESS! Your client key is: {client_key}")
        print("Add this to your configuration file.")
        return 0
    else:
        print("\nFAILED to get client key.")
        print("\nIf you're using a secure connection and having certificate issues, try:")
        print(f"python {os.path.basename(__file__)} {args.ip} --get-cert /path/to/save/certificate.pem")
        print("Then use that certificate for authentication.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 