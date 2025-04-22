#!/usr/bin/env python3
"""
Example demonstrating SecureWebOSClient usage.

This example shows how to:
1. Extract and save a certificate from a TV
2. Connect using the certificate for verification
3. Basic operations with secure connection
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

from asyncwebostv import SecureWebOSClient, extract_certificate, verify_certificate

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("secure_example")


async def get_tv_certificate(host, output_file, port=3001):
    """Connect to the TV and save its certificate."""
    logger.info(f"Extracting certificate from {host}:{port}")
    
    try:
        cert = await extract_certificate(host, port, output_file)
        logger.info(f"Certificate extracted and saved to {output_file}")
        logger.debug(f"Certificate content: {cert[:100]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to extract certificate: {e}")
        return False


async def verify_tv_certificate(host, cert_file, port=3001):
    """Verify if the saved certificate matches the TV's current certificate."""
    logger.info(f"Verifying certificate for {host}:{port}")
    
    try:
        matches = await verify_certificate(cert_file, host, port)
        if matches:
            logger.info("Certificate matches the one currently used by the TV")
        else:
            logger.warning("Certificate does NOT match the current TV certificate")
        return matches
    except Exception as e:
        logger.error(f"Failed to verify certificate: {e}")
        return False


async def secure_tv_example(host, cert_file=None, client_key=None, port=3001):
    """Main example using SecureWebOSClient."""
    # Create secure client instance
    client = SecureWebOSClient(
        host=host,
        port=port,
        secure=True,
        client_key=client_key,
        cert_file=cert_file,
        verify_ssl=True if cert_file else False
    )
    
    try:
        # Connect to the TV
        logger.info("Connecting to the TV...")
        await client.connect()
        logger.info("Connected successfully")
        
        # Register if needed
        if not client.client_key:
            logger.info("Registering with the TV...")
            store = {}
            async for status in client.register(store):
                if status == SecureWebOSClient.PROMPTED:
                    logger.info("Please approve the connection on your TV")
                elif status == SecureWebOSClient.REGISTERED:
                    logger.info(f"Registration successful! Client key: {store['client_key'][:10]}...")
                    client_key = store["client_key"]
        
        # Send a simple command
        logger.info("Getting TV system info...")
        response_queue = await client.send_message(
            "request", 
            "ssap://system/getSystemInfo", 
            None, 
            get_queue=True
        )
        response = await response_queue.get()
        if "payload" in response:
            model_name = response["payload"].get("modelName", "Unknown")
            sw_version = response["payload"].get("swVersion", "Unknown")
            logger.info(f"TV Model: {model_name}, Software Version: {sw_version}")
        
        # Get volume info
        logger.info("Getting volume info...")
        response_queue = await client.send_message(
            "request", 
            "ssap://audio/getVolume", 
            None, 
            get_queue=True
        )
        response = await response_queue.get()
        if "payload" in response:
            volume = response["payload"].get("volume", 0)
            muted = response["payload"].get("muted", False)
            logger.info(f"Current Volume: {volume}, Muted: {muted}")
    
    except Exception as e:
        logger.error(f"Error in secure TV example: {e}")
    finally:
        # Close the connection
        await client.close()
        logger.info("Connection closed")


async def main():
    parser = argparse.ArgumentParser(description="SecureWebOSClient Example")
    parser.add_argument("host", help="TV hostname or IP address")
    parser.add_argument("--port", type=int, default=3001, help="WebSocket port (default: 3001)")
    parser.add_argument("--client-key", help="Client key for authentication")
    parser.add_argument("--cert-file", help="Path to TV certificate file")
    parser.add_argument("--get-cert", action="store_true", help="Extract and save TV certificate")
    parser.add_argument("--verify-cert", action="store_true", help="Verify TV certificate")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("asyncwebostv").setLevel(logging.DEBUG)
    
    # Default certificate path
    default_cert_path = os.path.join(os.path.expanduser("~"), f"{args.host}_cert.pem")
    cert_file = args.cert_file or default_cert_path
    
    # Extract certificate if requested
    if args.get_cert:
        success = await get_tv_certificate(args.host, cert_file, args.port)
        if not success:
            return 1
    
    # Verify certificate if requested
    if args.verify_cert:
        if not os.path.exists(cert_file):
            logger.error(f"Certificate file not found: {cert_file}")
            return 1
            
        success = await verify_tv_certificate(args.host, cert_file, args.port)
        if not success:
            return 1
    
    # If no specific operations requested, run the main example
    if not (args.get_cert or args.verify_cert):
        # Use cert_file if it exists
        cert_to_use = cert_file if os.path.exists(cert_file) else None
        await secure_tv_example(args.host, cert_to_use, args.client_key, args.port)
        
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0) 