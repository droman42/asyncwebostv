# -*- coding: utf-8 -*-

import json
import time
import asyncio
from uuid import uuid4
from typing import Dict, Any, Optional, Tuple, Callable, List, Union
import logging

import websockets
from websockets.sync.client import connect  # Import connect function directly

from asyncwebostv.discovery import discover, discover_sync

logger = logging.getLogger(__name__)

SIGNATURE = ("eyJhbGdvcml0aG0iOiJSU0EtU0hBMjU2Iiwia2V5SWQiOiJ0ZXN0LXNpZ25pbm" +
             "ctY2VydCIsInNpZ25hdHVyZVZlcnNpb24iOjF9.hrVRgjCwXVvE2OOSpDZ58hR" +
             "+59aFNwYDyjQgKk3auukd7pcegmE2CzPCa0bJ0ZsRAcKkCTJrWo5iDzNhMBWRy" +
             "aMOv5zWSrthlf7G128qvIlpMT0YNY+n/FaOHE73uLrS/g7swl3/qH/BGFG2Hu4" +
             "RlL48eb3lLKqTt2xKHdCs6Cd4RMfJPYnzgvI4BNrFUKsjkcu+WD4OO2A27Pq1n" +
             "50cMchmcaXadJhGrOqH5YmHdOCj5NSHzJYrsW0HPlpuAx/ECMeIZYDh6RMqaFM" +
             "2DXzdKX9NmmyqzJ3o/0lkk/N97gfVRLW5hA29yeAwaCViZNCP8iC9aO0q9fQoj" +
             "oa7NQnAtw==")

REGISTRATION_PAYLOAD = {
    "forcePairing": False,
    "manifest": {
        "appVersion": "1.1",
        "manifestVersion": 1,
        "permissions": [
            "LAUNCH",
            "LAUNCH_WEBAPP",
            "APP_TO_APP",
            "CLOSE",
            "TEST_OPEN",
            "TEST_PROTECTED",
            "CONTROL_AUDIO",
            "CONTROL_DISPLAY",
            "CONTROL_INPUT_JOYSTICK",
            "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_MEDIA_PLAYBACK",
            "CONTROL_INPUT_TV",
            "CONTROL_POWER",
            "READ_APP_STATUS",
            "READ_CURRENT_CHANNEL",
            "READ_INPUT_DEVICE_LIST",
            "READ_NETWORK_STATE",
            "READ_RUNNING_APPS",
            "READ_TV_CHANNEL_LIST",
            "WRITE_NOTIFICATION_TOAST",
            "READ_POWER_STATE",
            "READ_COUNTRY_INFO",
            "READ_SETTINGS",
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
            "READ_TV_CURRENT_TIME",
            "ADD_LAUNCHER_CHANNEL",
            "SET_CHANNEL_SKIP",
            "RELEASE_CHANNEL_SKIP",
            "CONTROL_CHANNEL_BLOCK",
            "DELETE_SELECT_CHANNEL",
            "CONTROL_CHANNEL_GROUP",
            "SCAN_TV_CHANNELS",
            "CONTROL_TV_POWER",
            "CONTROL_WOL"
        ],
        "signatures": [
            {
                "signature": SIGNATURE,
                "signatureVersion": 1
            }
        ],
        "signed": {
            "appId": "com.lge.test",
            "created": "20140509",
            "localizedAppNames": {
                "": "LG Remote App",
                "ko-KR": u"리모컨 앱",
                "zxx-XX": u"ЛГ Rэмotэ AПП"
            },
            "localizedVendorNames": {
                "": "LG Electronics"
            },
            "permissions": [
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
                "READ_TV_CURRENT_TIME"
            ],
            "serial": "2f930e2d2cfe083771f68e4fe7bb07",
            "vendorId": "com.lge"
        }
    },
    "pairingType": "PROMPT"
}


class WebOSClient:
    """Asynchronous WebOS TV client using websockets."""
    
    PROMPTED = 1
    REGISTERED = 2

    def __init__(self, host: str, secure: bool = False, client_key: Optional[str] = None):
        """Initialize the WebOS client.
        
        Args:
            host: Hostname or IP address of the TV
            secure: Use secure WebSocket connection (wss://)
            client_key: Optional client key for authentication
        """
        if secure:
            self.ws_url = f"wss://{host}:3001/"
        else:
            self.ws_url = f"ws://{host}:3000/"

        self.waiters: Dict[str, Tuple[Callable, Optional[float]]] = {}
        self.subscribers: Dict[str, str] = {}
        self.connection: Optional[Any] = None
        self.task: Optional[asyncio.Task] = None
        self._connecting = False
        self.client_key = client_key

    @staticmethod
    def discover_sync(secure=False) -> List["WebOSClient"]:
        """Synchronous discovery of WebOS TVs on the network."""
        res = discover_sync("urn:schemas-upnp-org:device:MediaRenderer:1",
                       keyword="LG", hosts=True, retries=3)
        return [WebOSClient(x, secure) for x in res]

    @staticmethod
    async def discover(secure=False) -> List["WebOSClient"]:
        """Asynchronously discover WebOS TVs on the network."""
        res = await discover("urn:schemas-upnp-org:device:MediaRenderer:1",
                       keyword="LG", hosts=True, retries=3)
        return [WebOSClient(x, secure) for x in res]

    async def connect(self) -> None:
        """Connect to the WebOS TV."""
        if self._connecting:
            return
            
        self._connecting = True
        try:
            # Use websockets.connect directly with custom headers that exclude Origin
            self.connection = await websockets.client.connect(
                self.ws_url,
                extra_headers=[], # Empty list to avoid default headers including Origin
                origin=None  # Explicitly set origin to None
            )
            # Start the message handling task
            self.task = asyncio.create_task(self._handle_messages())
        finally:
            self._connecting = False

    async def close(self) -> None:
        """Close the connection."""
        if self.connection:
            await self.connection.close()
            self.connection = None
        
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _handle_messages(self):
        """Handle incoming messages from the WebSocket."""
        if not self.connection:
            logger.error("Cannot handle messages: No connection")
            return
            
        try:
            async for message in self.connection:
                try:
                    obj = json.loads(message)
                    # Enhanced logging to capture all incoming messages
                    logger.debug("Received message: %s", obj)
                    await self._process_message(obj)
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON: %s", message)
                except Exception as ex:
                    logger.exception("Error processing message: %s", ex)
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as ex:
            logger.exception("WebSocket error: %s", ex)

    async def _process_message(self, obj):
        """Process a received message object."""
        try:
            # Handle responses to requests
            msg_id = obj.get("id")
            if msg_id and msg_id in self.waiters:
                callback, created_time = self.waiters[msg_id]
                
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(obj)
                    else:
                        callback(obj)
                except Exception as ex:
                    logger.exception("Error calling callback for message %s: %s", msg_id, ex)
                    
                # Only remove waiters for non-subscription responses and non-registration messages
                # Subscriptions are removed explicitly by unsubscribe
                # Registration waiters need to stay until the entire registration process completes
                if msg_id not in self.subscribers:
                    self.waiters.pop(msg_id, None)
            
            # Special handling for registration messages if no waiter was found
            # This is a fallback in case the waiter was somehow removed
            elif obj.get("type") == "registered":
                logger.warning("Received registration message with no matching waiter: %s", obj)
                
            # Clear old waiters periodically
            await self._clear_old_waiters()
        except Exception as ex:
            logger.exception("Unexpected error in _process_message: %s", ex)

    async def _clear_old_waiters(self, delta=60):
        """Clear waiters that are older than delta seconds."""
        to_clear = []
        cur_time = time.time()
        
        for key, value in self.waiters.items():
            callback, created_time = value
            if created_time and created_time + delta < cur_time:
                to_clear.append(key)

        for key in to_clear:
            self.waiters.pop(key)

    async def register(self, store, timeout=60):
        """Register the client with the TV.
        
        This is a generator that yields status updates. First, it yields
        PROMPTED when the TV shows the prompt, then REGISTERED when the
        registration is complete.
        
        Args:
            store: A dict-like object that will receive the client key
            timeout: Timeout in seconds for registration
        
        Yields:
            PROMPTED when the TV shows the prompt
            REGISTERED when registration is complete
        
        Raises:
            Exception: If registration fails or times out
        """
        # Make a copy of the registration payload
        reg_payload = dict(REGISTRATION_PAYLOAD)
        
        # Use client key if it's in the store or provided to the client constructor
        if "client_key" in store:
            reg_payload["client-key"] = store["client_key"]
        elif self.client_key:
            reg_payload["client-key"] = self.client_key
            
        # Ensure we're connected
        if not self.connection:
            await self.connect()
        
        # Create a queue to collect all registration-related messages
        queue = await self.send_message('register', None, reg_payload, get_queue=True)
        
        try:
            # Wait for prompt message
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    raise Exception("Timeout during registration")
                
                logger.debug("Registration message received: %s", item)
                
                if item.get("payload", {}).get("pairingType") == "PROMPT":
                    logger.info("Please accept the connection on the TV!")
                    yield self.PROMPTED
                elif item.get("type") == "registered":
                    # Extract client key and save to store
                    client_key = item.get("payload", {}).get("client-key")
                    if client_key:
                        store["client_key"] = client_key
                        self.client_key = client_key
                        logger.info("Registration successful! Client key received")
                        yield self.REGISTERED
                        break
                    else:
                        raise Exception("Registration failed: No client key received")
                elif item.get("type") == "error":
                    raise Exception(f"Registration failed: {item.get('error', 'Unknown error')}")
                
        except Exception as ex:
            logger.exception("Error during registration: %s", ex)
            raise

    async def send_message(
        self, 
        request_type: str, 
        uri: Optional[str], 
        payload: Optional[Dict[str, Any]] = None, 
        unique_id: Optional[str] = None,
        callback: Optional[Callable] = None,
        get_queue: bool = False, 
        cur_time: Callable[[], float] = time.time
    ) -> Optional[asyncio.Queue]:
        """Send a message to the TV.
        
        Args:
            request_type: Type of request (e.g., 'register', 'request')
            uri: URI for the request
            payload: Data to send
            unique_id: ID for the request, generated if None
            get_queue: If True, create a queue and return it
            callback: Function to call with the response
            cur_time: Function that returns the current time
            
        Returns:
            Queue if get_queue is True, otherwise None
        """
        if not self.connection:
            await self.connect()
            
        if unique_id is None:
            unique_id = str(uuid4())

        # Prepare the message object
        obj: Dict[str, Any] = {"type": request_type, "id": unique_id}
        if uri is not None:
            obj["uri"] = uri
        if payload is not None:
            obj["payload"] = payload
            
        # Handle queue case
        wait_queue = None
        if get_queue:
            wait_queue = asyncio.Queue()
            
            async def queue_callback(response):
                await wait_queue.put(response)
            
            # Use the queue callback instead of the provided one
            callback = queue_callback

        # Register callback if provided
        if callback is not None:
            # For registration requests, mark the callback with None as created_time
            # This prevents it from being removed by the cleaner and ensures it stays 
            # available for both the initial response and the "registered" message
            if request_type == "register":
                self.waiters[unique_id] = (callback, None)
                # Also add to subscribers to prevent removal after first response
                self.subscribers[unique_id] = "register"
            else:
                self.waiters[unique_id] = (callback, cur_time())

        # Send the message
        message = json.dumps(obj)
        logger.debug("Sending message: %s", message)
        await self.connection.send(message)

        # Return the queue if requested
        if get_queue:
            return wait_queue

    async def subscribe(self, uri, unique_id, callback, payload=None):
        """Subscribe to updates from a URI.
        
        Args:
            uri: URI to subscribe to
            unique_id: ID for the subscription
            callback: Function to call with updates
            payload: Optional payload for the subscription
            
        Returns:
            The subscription ID
        """
        # Create wrapper to handle subscription callbacks
        async def wrapper(obj):
            if "payload" in obj:
                if asyncio.iscoroutinefunction(callback):
                    await callback(obj["payload"])
                else:
                    callback(obj["payload"])

        # Add to subscribers list first
        self.subscribers[unique_id] = uri
        
        # Then register the callback
        self.waiters[unique_id] = (wrapper, None)
        
        # Send the subscription request
        await self.send_message('subscribe', uri, payload, unique_id=unique_id)
        
        return unique_id

    async def unsubscribe(self, unique_id):
        """Unsubscribe from updates.
        
        Args:
            unique_id: ID of the subscription to cancel
            
        Raises:
            ValueError: If the subscription is not found
        """
        # Check if subscription exists
        if unique_id not in self.subscribers:
            raise ValueError(f"Subscription not found: {unique_id}")
            
        # Get URI from subscribers list
        uri = self.subscribers.pop(unique_id)
        
        # Remove associated waiter
        if unique_id in self.waiters:
            self.waiters.pop(unique_id)
            
        # Send unsubscribe request
        await self.send_message('unsubscribe', uri, None)
        
        logger.debug("Unsubscribed from %s with ID %s", uri, unique_id)

    async def __aenter__(self):
        """Enter async context manager."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close()
