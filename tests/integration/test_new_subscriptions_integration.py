#!/usr/bin/env python3
"""
Integration test for new volume and power state subscriptions.
This test can be run against a real WebOS TV to verify functionality.
"""

import asyncio
import argparse
import logging
import signal
from typing import Optional, List, Dict, Any, Tuple

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, SystemControl

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag to indicate if the program should stop
stop_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle signals to gracefully shutdown."""
    logger.info("Received signal %s, shutting down...", signum)
    stop_event.set()


async def setup_client(ip_address: str, client_key: Optional[str] = None) -> Tuple[Optional[WebOSClient], Optional[str]]:
    """Set up the client by performing the registration process if needed.
    
    Args:
        ip_address: IP address of the TV
        client_key: Optional client key for authentication
        
    Returns:
        Tuple of (client, client_key) or (None, None) if setup failed
    """
    try:
        client = WebOSClient(ip_address, client_key=client_key)
        await client.connect()
        
        if not client.client_key:
            logger.info("No client key available, registering with TV...")
            store = {}
            
            async for status in client.register(store):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection request on your TV...")
                elif status == WebOSClient.REGISTERED:
                    logger.info("Registration successful!")
                    return client, store.get("client_key")
        else:
            logger.info("Using existing client key")
            return client, client.client_key
            
    except Exception as ex:
        logger.error("Failed to set up client: %s", ex)
        return None, None
    
    return client, client_key


async def test_volume_subscription_real(ip_address: str, client_key: Optional[str] = None) -> bool:
    """Test volume subscription against a real TV.
    
    Args:
        ip_address: IP address of the TV
        client_key: Optional client key for authentication
        
    Returns:
        True if test successful, False otherwise
    """
    logger.info("=== Testing Volume Subscription on Real TV ===")
    
    client, client_key = await setup_client(ip_address, client_key)
    if not client:
        return False
    
    try:
        media = MediaControl(client)
        volume_events = []
        
        async def volume_callback(success: bool, payload: Dict[str, Any]):
            if success:
                volume_events.append(payload)
                volume = payload.get("volume", "?")
                muted = payload.get("muted", False)
                logger.info(f"📻 Volume event: {volume}% {'(MUTED)' if muted else ''}")
            else:
                logger.error(f"❌ Volume subscription error: {payload}")
        
        # Subscribe to volume changes
        logger.info("Subscribing to volume changes...")
        await media.subscribe_get_volume(volume_callback)
        logger.info("✓ Volume subscription active")
        
        # Get initial volume to verify subscription is working
        initial_volume = await media.get_volume()
        logger.info(f"Initial volume: {initial_volume}")
        
        # Test volume changes to trigger subscription events
        logger.info("Testing volume changes (this will modify your TV volume)...")
        logger.info("Increasing volume...")
        await media.volume_up()
        await asyncio.sleep(2)
        
        logger.info("Decreasing volume...")
        await media.volume_down()
        await asyncio.sleep(2)
        
        # Test mute toggle
        logger.info("Testing mute toggle...")
        await media.set_mute(True)
        await asyncio.sleep(2)
        await media.set_mute(False)
        await asyncio.sleep(2)
        
        # Check if we received events
        if volume_events:
            logger.info(f"✓ Received {len(volume_events)} volume events during test")
            for i, event in enumerate(volume_events):
                logger.info(f"  Event {i+1}: {event}")
        else:
            logger.warning("⚠️  No volume events received during test")
        
        # Clean up subscription
        logger.info("Unsubscribing from volume changes...")
        await media.unsubscribe_get_volume()
        logger.info("✓ Volume subscription cleaned up")
        
        return len(volume_events) > 0
        
    except Exception as ex:
        logger.error(f"Volume subscription test failed: {ex}")
        return False
    finally:
        await client.close()


async def test_power_state_subscription_real(ip_address: str, client_key: Optional[str] = None) -> bool:
    """Test power state subscription against a real TV.
    
    Args:
        ip_address: IP address of the TV
        client_key: Optional client key for authentication
        
    Returns:
        True if test successful, False otherwise
    """
    logger.info("=== Testing Power State Subscription on Real TV ===")
    
    client, client_key = await setup_client(ip_address, client_key)
    if not client:
        return False
    
    try:
        system = SystemControl(client)
        power_events = []
        
        async def power_callback(success: bool, payload: Dict[str, Any]):
            if success:
                power_events.append(payload)
                state = payload.get("state", "unknown")
                processing = payload.get("processing", False)
                logger.info(f"⚡ Power event: {state} {'(processing)' if processing else ''}")
            else:
                logger.error(f"❌ Power state subscription error: {payload}")
        
        # Subscribe to power state changes
        logger.info("Subscribing to power state changes...")
        await system.subscribe_power_state(power_callback)
        logger.info("✓ Power state subscription active")
        
        # Get initial power state (if available as a command)
        try:
            initial_power = await system.power_state()
            logger.info(f"Initial power state: {initial_power}")
        except AttributeError:
            logger.info("Power state query not available as direct command")
        
        # Monitor for power events
        logger.info("Monitoring power state for 10 seconds...")
        logger.info("(Try using your TV remote to change inputs or settings)")
        
        # Wait and monitor
        await asyncio.sleep(10)
        
        # Check if we received events
        if power_events:
            logger.info(f"✓ Received {len(power_events)} power events during monitoring")
            for i, event in enumerate(power_events):
                logger.info(f"  Event {i+1}: {event}")
        else:
            logger.warning("⚠️  No power events received during monitoring")
            logger.info("This might be normal if the TV power state didn't change")
        
        # Clean up subscription
        logger.info("Unsubscribing from power state changes...")
        await system.unsubscribe_power_state()
        logger.info("✓ Power state subscription cleaned up")
        
        # Return true even if no events (power state might not change during test)
        return True
        
    except Exception as ex:
        logger.error(f"Power state subscription test failed: {ex}")
        return False
    finally:
        await client.close()


async def test_multiple_subscriptions_real(ip_address: str, client_key: Optional[str] = None) -> bool:
    """Test multiple simultaneous subscriptions.
    
    Args:
        ip_address: IP address of the TV
        client_key: Optional client key for authentication
        
    Returns:
        True if test successful, False otherwise
    """
    logger.info("=== Testing Multiple Simultaneous Subscriptions ===")
    
    client, client_key = await setup_client(ip_address, client_key)
    if not client:
        return False
    
    try:
        media = MediaControl(client)
        system = SystemControl(client)
        
        volume_events = []
        power_events = []
        
        async def volume_callback(success: bool, payload: Dict[str, Any]):
            if success:
                volume_events.append(payload)
                logger.info(f"📻 Volume: {payload.get('volume', '?')}% {'(MUTED)' if payload.get('muted') else ''}")
        
        async def power_callback(success: bool, payload: Dict[str, Any]):
            if success:
                power_events.append(payload)
                logger.info(f"⚡ Power: {payload.get('state', 'unknown')}")
        
        # Subscribe to both events
        logger.info("Setting up multiple subscriptions...")
        await media.subscribe_get_volume(volume_callback)
        await system.subscribe_power_state(power_callback)
        logger.info("✓ Both subscriptions active")
        
        # Verify subscription counts
        assert len(media.subscriptions) == 1, "Media should have 1 subscription"
        assert len(system.subscriptions) == 1, "System should have 1 subscription"
        logger.info("✓ Subscription tracking verified")
        
        # Trigger some events
        logger.info("Triggering events (changing volume)...")
        await media.volume_up()
        await asyncio.sleep(1)
        await media.volume_down()
        await asyncio.sleep(2)
        
        logger.info("Monitoring for any additional events...")
        await asyncio.sleep(5)
        
        # Clean up subscriptions one by one
        logger.info("Cleaning up volume subscription...")
        await media.unsubscribe_get_volume()
        assert len(media.subscriptions) == 0, "Media subscriptions should be empty"
        assert len(system.subscriptions) == 1, "System should still have 1 subscription"
        logger.info("✓ Volume subscription cleaned up")
        
        logger.info("Cleaning up power state subscription...")
        await system.unsubscribe_power_state()
        assert len(system.subscriptions) == 0, "System subscriptions should be empty"
        logger.info("✓ Power state subscription cleaned up")
        
        # Summary
        logger.info(f"Test summary:")
        logger.info(f"  Volume events received: {len(volume_events)}")
        logger.info(f"  Power events received: {len(power_events)}")
        
        return True
        
    except Exception as ex:
        logger.error(f"Multiple subscriptions test failed: {ex}")
        return False
    finally:
        await client.close()


async def main():
    """Main function to run subscription integration tests."""
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    parser = argparse.ArgumentParser(description="Test new volume and power state subscriptions")
    parser.add_argument("--ip", required=True, help="IP address of the TV")
    parser.add_argument("--client-key", help="Client key for authentication (optional)")
    parser.add_argument("--test", choices=["volume", "power", "multiple", "all"], 
                       default="all", help="Which test to run")
    args = parser.parse_args()
    
    logger.info(f"Starting subscription integration tests for TV at {args.ip}")
    
    results = {}
    
    try:
        if args.test in ["volume", "all"]:
            logger.info("\n" + "="*60)
            results["volume"] = await test_volume_subscription_real(args.ip, args.client_key)
        
        if args.test in ["power", "all"]:
            logger.info("\n" + "="*60)
            results["power"] = await test_power_state_subscription_real(args.ip, args.client_key)
        
        if args.test in ["multiple", "all"]:
            logger.info("\n" + "="*60)
            results["multiple"] = await test_multiple_subscriptions_real(args.ip, args.client_key)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("INTEGRATION TEST RESULTS:")
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {test_name.capitalize()} subscription: {status}")
        
        all_passed = all(results.values())
        if all_passed:
            logger.info("\n🎉 ALL INTEGRATION TESTS PASSED! 🎉")
            logger.info("New subscription functionality is working correctly with real TV!")
        else:
            logger.warning("\n⚠️  Some tests failed. Check the logs above for details.")
        
        return 0 if all_passed else 1
        
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        return 1
    except Exception as ex:
        logger.exception(f"Integration test failed: {ex}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 