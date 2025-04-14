#!/usr/bin/env python3
"""
Simple script to discover WebOS TVs on the network.
"""

import asyncio
import logging

from asyncwebostv.connection import WebOSClient

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Discover TVs on the network and display their information."""
    logger.info("Discovering WebOS TVs (non-secure mode)...")
    tvs = await WebOSClient.discover()
    
    if not tvs:
        logger.info("No TVs found using non-secure mode. Trying secure mode...")
        tvs = await WebOSClient.discover(secure=True)
        
    if not tvs:
        logger.error("No WebOS TVs found on the network!")
        return
    
    logger.info("Found %d WebOS TV(s):", len(tvs))
    
    for i, tv in enumerate(tvs, 1):
        logger.info("TV #%d: %s", i, tv.ws_url)
        
        # Try to connect to get more information
        try:
            await tv.connect()
            logger.info("  Successfully connected")
            
            # Close the connection
            await tv.close()
        except Exception as ex:
            logger.error("  Failed to connect: %s", ex)

if __name__ == "__main__":
    asyncio.run(main()) 