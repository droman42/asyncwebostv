# -*- coding: utf-8 -*-

import json
import time
import asyncio
from uuid import uuid4
from typing import Dict, Any, Optional, Tuple, Callable, List, Union
import logging

import websockets
from websockets.client import WebSocketClientProtocol

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

    def __init__(self, host: str, secure: bool = False):
        """Initialize the WebOS client.
        
        Args:
            host: Hostname or IP address of the TV
            secure: Use secure WebSocket connection (wss://)
        """
        if secure:
            self.ws_url = f"wss://{host}:3001/"
        else:
            self.ws_url = f"ws://{host}:3000/"

        self.waiters: Dict[str, Tuple[Callable, Optional[float]]] = {}
        self.subscribers: Dict[str, str] = {}
        self.connection: Optional[WebSocketClientProtocol] = None
        self.task: Optional[asyncio.Task] = None
        self._connecting = False

    @staticmethod
    def discover_sync(secure=False):
        """Synchronous discovery of WebOS TVs on the network."""
        res = discover_sync("urn:schemas-upnp-org:device:MediaRenderer:1",
                       keyword="LG", hosts=True, retries=3)
        return [WebOSClient(x, secure) for x in res]

    @staticmethod
    async def discover(secure=False):
        """Asynchronously discover WebOS TVs on the network."""
        res = await discover("urn:schemas-upnp-org:device:MediaRenderer:1",
                       keyword="LG", hosts=True, retries=3)
        return [WebOSClient(x, secure) for x in res]

    async def connect(self):
        """Connect to the WebOS TV."""
        if self._connecting:
            return
            
        self._connecting = True
        try:
            self.connection = await websockets.connect(self.ws_url)
            # Start the message handling task
            self.task = asyncio.create_task(self._handle_messages())
        finally:
            self._connecting = False

    async def close(self):
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
        # Handle responses to requests
        msg_id = obj.get("id")
        if msg_id and msg_id in self.waiters:
            callback, created_time = self.waiters[msg_id]
            if callable(callback):
                callback(obj)
        
        # Clear old waiters
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
            store: A dict-like object that stores the client key
            timeout: Timeout in seconds for registration
        
        Yields:
            PROMPTED when the TV shows the prompt
            REGISTERED when registration is complete
        
        Raises:
            Exception: If registration fails
        """
        if "client_key" in store:
            reg_payload = dict(REGISTRATION_PAYLOAD)
            reg_payload["client-key"] = store["client_key"]
        else:
            reg_payload = REGISTRATION_PAYLOAD

        if not self.connection:
            await self.connect()
            
        queue = await self.send_message('register', None, reg_payload, get_queue=True)
        
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError("Registration timed out")
                    
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    raise Exception("Timeout during registration")

                if item.get("payload", {}).get("pairingType") == "PROMPT":
                    yield WebOSClient.PROMPTED
                elif item["type"] == "registered":
                    store["client_key"] = item["payload"]["client-key"]
                    yield WebOSClient.REGISTERED
                    break
                else:
                    raise Exception(f"Failed to register: {item}")
        except Exception as ex:
            logger.exception("Registration failed: %s", ex)
            raise

    async def send_message(self, request_type, uri, payload, unique_id=None,
                    get_queue=False, callback=None, cur_time=time.time):
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

        wait_queue = None
        if get_queue:
            wait_queue = asyncio.Queue()
            
            # Create a callback that puts the response in the queue
            async def queue_callback(response):
                await wait_queue.put(response)
            callback = queue_callback

        if callback is not None:
            self.waiters[unique_id] = (callback, cur_time())

        obj = {"type": request_type, "id": unique_id}
        if uri is not None:
            obj["uri"] = uri
        if payload is not None:
            obj["payload"] = payload

        message = json.dumps(obj)
        await self.connection.send(message)

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
        async def wrapper(obj):
            await callback(obj.get("payload"))

        self.subscribers[unique_id] = uri
        await self.send_message('subscribe', uri, payload, unique_id=unique_id,
                          callback=wrapper, cur_time=lambda: None)
        return unique_id

    async def unsubscribe(self, unique_id):
        """Unsubscribe from updates.
        
        Args:
            unique_id: ID of the subscription to cancel
            
        Raises:
            ValueError: If the subscription is not found
        """
        uri = self.subscribers.pop(unique_id, None)

        if not uri:
            raise ValueError(f"Subscription not found: {unique_id}")

        if unique_id in self.waiters:
            self.waiters.pop(unique_id)

        await self.send_message('unsubscribe', uri, payload=None)

    async def __aenter__(self):
        """Enter async context manager."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.close()
