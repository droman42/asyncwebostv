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
            # Use websockets.connect directly
            self.connection = await websockets.client.connect(self.ws_url)
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
        # Log received message for debugging
        logger.debug("Received message: %s", obj)
        
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
                
            # Only remove waiters for non-subscription responses 
            # Subscriptions are removed explicitly by unsubscribe
            if msg_id not in self.subscribers:
                self.waiters.pop(msg_id, None)
        
        # Clear old waiters periodically
        await self._clear_old_waiters()

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
            Exception: If registration fails
        """
        # Prepare registration payload
        reg_payload = dict(REGISTRATION_PAYLOAD)
        
        # Use client key if available
        if self.client_key:
            reg_payload["client-key"] = self.client_key
        
        # Ensure we're connected
        if not self.connection:
            await self.connect()
            
        # Create events to track registration status
        prompted_event = asyncio.Event()
        registered_event = asyncio.Event()
        
        # Variable to store registration results
        registration_result = {"client_key": None, "error": None, "already_registered": False}
        
        # Define callback to handle registration responses
        async def registration_callback(response):
            logger.debug("Registration response: %s", response)
            
            if response.get("payload", {}).get("pairingType") == "PROMPT":
                logger.info("Please accept the connection on the TV!")
                prompted_event.set()
                
            elif response.get("type") == "registered":
                if "client-key" in response.get("payload", {}):
                    registration_result["client_key"] = response["payload"]["client-key"]
                    logger.info("Registration successful! Client key received")
                    
                    # If prompted_event is not set, we're already registered (no prompt needed)
                    if not prompted_event.is_set():
                        logger.info("Already registered (using existing client key)")
                        registration_result["already_registered"] = True
                        prompted_event.set()  # Set this so we don't hang waiting for prompt
                        
                    registered_event.set()
                    
            elif response.get("type") == "error":
                registration_result["error"] = response.get("error", "Unknown error")
                logger.error("Registration error: %s", registration_result["error"])
                prompted_event.set()  # Make sure we don't hang
                registered_event.set()
        
        # Send registration request through send_message
        await self.send_message("register", None, reg_payload, 
                               callback=registration_callback)
        
        # Wait for prompt
        try:
            await asyncio.wait_for(prompted_event.wait(), timeout=timeout)
            
            # If we got an error, raise it now
            if registration_result["error"]:
                raise Exception(f"Registration failed: {registration_result['error']}")
                
            # If already registered, we still yield PROMPTED to maintain the API contract
            yield self.PROMPTED
            
            # If already registered, then we don't need to wait for the registered event
            if registration_result["already_registered"] and registration_result["client_key"]:
                client_key = registration_result["client_key"]
                store["client_key"] = client_key
                self.client_key = client_key
                yield self.REGISTERED
                return
                
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for TV to prompt for pairing")
            
        # Wait for registration to complete
        try:
            await asyncio.wait_for(registered_event.wait(), timeout=timeout)
            
            if registration_result["error"]:
                raise Exception(f"Registration failed: {registration_result['error']}")
                
            if registration_result["client_key"]:
                client_key = registration_result["client_key"]
                # Store the client key in the provided store dict
                store["client_key"] = client_key
                # Also update the instance's client_key
                self.client_key = client_key
                yield self.REGISTERED
            else:
                raise Exception("Registration completed but no client key received")
                
        except asyncio.TimeoutError:
            raise Exception("Timeout waiting for registration completion")

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
