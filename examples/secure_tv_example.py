#!/usr/bin/env python3
"""
Example demonstrating SecureWebOSTV high-level client.

This example shows how to use the SecureWebOSTV class for secure
connections with WebOS TVs.
"""

import asyncio
import argparse
import logging
import os
import sys
import json

from asyncwebostv import SecureWebOSTV

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("secure_tv_example")


async def main():
    parser = argparse.ArgumentParser(description="SecureWebOSTV Example")
    parser.add_argument("host", help="TV hostname or IP address")
    parser.add_argument("--port", type=int, default=3001, help="WebSocket port (default: 3001)")
    parser.add_argument("--client-key", help="Client key for authentication")
    parser.add_argument("--cert-file", help="Path to TV certificate file")
    parser.add_argument("--extract-cert", help="Extract and save certificate to specified path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("asyncwebostv").setLevel(logging.DEBUG)
    
    # Create TV client
    tv = SecureWebOSTV(
        host=args.host,
        port=args.port,
        client_key=args.client_key,
        cert_file=args.cert_file,
        verify_ssl=args.cert_file is not None
    )
    
    try:
        # Extract certificate if requested
        if args.extract_cert:
            logger.info(f"Extracting TV certificate to {args.extract_cert}")
            cert = await tv.get_certificate(args.extract_cert)
            logger.info("Certificate extracted successfully")
            # If this is the only operation, exit
            if not args.client_key:
                return 0
        
        # Connect to the TV
        logger.info("Connecting to the TV...")
        await tv.connect()
        logger.info("Connected successfully")
        
        # Register the client if needed
        if not tv.client_key:
            logger.info("No client key provided. Registering with the TV...")
            client_key = await tv.register()
            if client_key:
                logger.info(f"Successfully registered with client key: {client_key[:10]}...")
            else:
                logger.error("Registration failed")
                return 1
        
        # Access WebOSClient directly to send commands
        client = tv.client
        
        # Get system info
        logger.info("Getting system info...")
        response_queue = await client.send_message(
            "request", 
            "ssap://system/getSystemInfo", 
            None, 
            get_queue=True
        )
        system_info = await response_queue.get()
        if "payload" in system_info:
            logger.info("System Info:")
            payload = system_info["payload"]
            for key, value in payload.items():
                logger.info(f"  {key}: {value}")
                
        # Get current power state
        logger.info("Getting power state...")
        response_queue = await client.send_message(
            "request", 
            "ssap://system/getPowerState", 
            None, 
            get_queue=True
        )
        power_state = await response_queue.get()
        if "payload" in power_state:
            state = power_state["payload"].get("state")
            logger.info(f"Current power state: {state}")
            
        # Get external input list
        logger.info("Getting input sources...")
        response_queue = await client.send_message(
            "request", 
            "ssap://tv/getExternalInputList", 
            None, 
            get_queue=True
        )
        inputs = await response_queue.get()
        if "payload" in inputs and "devices" in inputs["payload"]:
            logger.info("Available Input Devices:")
            for device in inputs["payload"]["devices"]:
                logger.info(f"  {device.get('label', 'Unknown')}: {device.get('id', 'Unknown')}")
                
    except Exception as e:
        logger.error(f"Error in secure TV example: {e}")
        return 1
    finally:
        # Close the connection
        await tv.close()
        logger.info("Connection closed")
        
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
        sys.exit(0) 