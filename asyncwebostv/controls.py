"""Control interfaces for WebOS TV."""

import base64
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from uuid import uuid4
import websockets

from asyncwebostv.model import Application, InputSource, AudioOutputSource
from asyncwebostv.connection import WebOSClient

# Configure logger
logger = logging.getLogger(__name__)

ARGS_NONE = ()


def arguments(val, postprocess=lambda x: x, default=ARGS_NONE):
    """Create a function that extracts an argument from args or kwargs.
    
    Args:
        val: Index (for args) or key (for kwargs) to extract
        postprocess: Function to apply to the extracted value
        default: Default value if the argument doesn't exist
        
    Returns:
        Function that extracts the argument
    """
    if type(val) not in (str, int):
        raise ValueError("Only numeric indices, or string keys allowed.")

    def func(*args, **kwargs):
        try:
            if isinstance(val, int):
                if default is ARGS_NONE:
                    return postprocess(args[val])
                valid_index = 0 <= val < len(args)
                return postprocess(args[val]) if valid_index else default
            elif isinstance(val, str):
                if default is ARGS_NONE:
                    return postprocess(kwargs[val])
                return postprocess(kwargs[val]) if val in kwargs else default
        except (KeyError, IndexError):
            raise TypeError("Bad arguments.")
    return func


def process_payload(obj, *args, **kwargs):
    """Process a payload object, resolving callable values.
    
    Args:
        obj: Payload object to process
        *args: Arguments to pass to callable values
        **kwargs: Keyword arguments to pass to callable values
        
    Returns:
        Processed payload
    """
    if isinstance(obj, list):
        return [process_payload(item, *args, **kwargs) for item in obj]
    elif isinstance(obj, dict):
        return {k: process_payload(v, *args, **kwargs) for k, v in obj.items()}
    elif isinstance(obj, Callable):
        return obj(*args, **kwargs)
    else:
        return obj


def standard_validation(payload):
    """Standard validation for WebOS TV responses.
    
    Args:
        payload: Response payload to validate
        
    Returns:
        Tuple of (success, error_message)
    """
    if not payload.pop("returnValue", None):
        return False, payload.pop("errorText", "Unknown error.")
    return True, None


class WebOSControlBase:
    """Base class for WebOS TV controls."""
    
    COMMANDS: Dict[str, Dict[str, Any]] = {}

    def __init__(self, client):
        """Initialize the control base.
        
        Args:
            client: WebOSClient instance
        """
        self.client = client
        self.subscriptions = {}

    async def request(self, uri, params, callback=None, block=False, timeout=60):
        """Send a request to the TV.
        
        Args:
            uri: URI to request
            params: Parameters to send
            callback: Function to call with the response
            block: Whether to block until the response is received
            timeout: Timeout in seconds
            
        Returns:
            Response if block is True, otherwise None
        """
        if block:
            queue = await self.client.send_message('request', uri, params, get_queue=True)
            try:
                return await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                raise Exception("Request timed out.")
        else:
            await self.client.send_message('request', uri, params, callback=callback)

    def __getattr__(self, name):
        """Get an attribute, handling command execution and subscriptions.
        
        Args:
            name: Attribute name
            
        Returns:
            Command function or subscription function
            
        Raises:
            AttributeError: If the attribute doesn't exist
        """
        subscribe_prefix = "subscribe_"
        unsubscribe_prefix = "unsubscribe_"
        if name in self.COMMANDS:
            return self.exec_command(name, self.COMMANDS[name])
        elif name.startswith(subscribe_prefix):
            subscribe_name = name[len(subscribe_prefix):]
            sub_cmd_info = self.COMMANDS.get(subscribe_name)
            if not sub_cmd_info:
                raise AttributeError(name)
            elif not sub_cmd_info.get("subscription"):
                raise AttributeError("Subscription not found or allowed.")
            else:
                return self.subscribe(subscribe_name, sub_cmd_info)
        elif name.startswith(unsubscribe_prefix):
            unsubscribe_name = name[len(unsubscribe_prefix):]
            sub_cmd_info = self.COMMANDS.get(unsubscribe_name)
            if not sub_cmd_info:
                raise AttributeError(name)
            elif not sub_cmd_info.get("subscription"):
                raise AttributeError("Subscription not found or allowed.")
            else:
                return self.unsubscribe(unsubscribe_name, sub_cmd_info)
        else:
            raise AttributeError(name)

    def exec_command(self, cmd, cmd_info):
        """Execute a command.
        
        Args:
            cmd: Command name
            cmd_info: Command information
            
        Returns:
            Function that executes the command
        """
        async def request_func(*args, **kwargs):
            callback = kwargs.pop('callback', None)
            response_valid = cmd_info.get("validation", lambda p: (True, None))
            return_fn = cmd_info.get('return', lambda x: x)
            block = kwargs.pop('block', True)
            timeout = kwargs.pop('timeout', 60)
            params = process_payload(cmd_info.get("payload"), *args, **kwargs)

            # callback in the args has higher priority.
            if callback:
                async def callback_wrapper(res):
                    payload = res.get("payload")
                    if res.get("type", None) == "error":
                        await callback(False, res.get("error", "Unknown Communication Error"))
                        return
                    status, message = response_valid(payload)
                    if not status:
                        await callback(False, message)
                        return
                    await callback(True, return_fn(payload))

                await self.request(cmd_info["uri"], params, timeout=timeout,
                             callback=callback_wrapper)
            elif block:
                res = await self.request(cmd_info["uri"], params, block=block,
                                   timeout=timeout)
                if res.get("type", None) == "error":
                    raise IOError(res.get("error", "Unknown Communication Error"))
                payload = res.get("payload")
                status, message = response_valid(payload)
                if not status:
                    raise IOError(message)

                return return_fn(payload)
            else:
                await self.request(cmd_info["uri"], params)
        return request_func

    def subscribe(self, name, cmd_info):
        """Subscribe to updates from the TV.
        
        Args:
            name: Subscription name
            cmd_info: Command information
            
        Returns:
            Function that subscribes to updates
        """
        async def request_func(callback):
            response_valid = cmd_info.get("validation", lambda p: (True, None))
            return_fn = cmd_info.get('return', lambda x: x)

            async def callback_wrapper(payload):
                status, message = response_valid(payload)
                if not status:
                    await callback(False, message)
                    return
                await callback(True, return_fn(payload))

            if name in self.subscriptions:
                raise ValueError("Already subscribed.")

            uid = str(uuid4())
            self.subscriptions[name] = uid
            await self.client.subscribe(cmd_info["uri"], uid, callback_wrapper)
        return request_func

    def unsubscribe(self, name, cmd_info):
        """Unsubscribe from updates.
        
        Args:
            name: Subscription name
            cmd_info: Command information
            
        Returns:
            Function that unsubscribes from updates
        """
        async def request_func():
            uid = self.subscriptions.get(name)
            if not uid:
                raise ValueError("Not subscribed.")
            await self.client.unsubscribe(uid)
            del self.subscriptions[name]
        return request_func


class MediaControl(WebOSControlBase):
    """Control for media playback and volume."""
    
    COMMANDS = {
        "volume_up": {
            "uri": "ssap://audio/volumeUp",
            "validation": standard_validation,
        },
        "volume_down": {
            "uri": "ssap://audio/volumeDown",
            "validation": standard_validation,
        },
        "get_volume": {
            "uri": "ssap://audio/getVolume",
            "validation": standard_validation,
        },
        "set_volume": {
            "uri": "ssap://audio/setVolume",
            "payload": {"volume": arguments(0)},
            "validation": standard_validation,
        },
        "get_mute": {
            "uri": "ssap://audio/getStatus",
            "validation": standard_validation,
            "return": lambda payload: payload["mute"]
        },
        "set_mute": {
            "uri": "ssap://audio/setMute",
            "payload": {"mute": arguments(0)},
            "validation": standard_validation,
        },
        "get_audio_status": {
            "uri": "ssap://audio/getStatus",
            "validation": standard_validation,
        },
        "play": {
            "uri": "ssap://media.controls/play",
            "validation": standard_validation,
        },
        "pause": {
            "uri": "ssap://media.controls/pause",
            "validation": standard_validation,
        },
        "stop": {
            "uri": "ssap://media.controls/stop",
            "validation": standard_validation,
        },
        "rewind": {
            "uri": "ssap://media.controls/rewind",
            "validation": standard_validation,
        },
        "fast_forward": {
            "uri": "ssap://media.controls/fastForward",
            "validation": standard_validation,
        },
        "get_audio_output": {
            "uri": "ssap://audio/getSoundOutput",
            "validation": standard_validation,
            "subscription": True,
            "return": lambda p: AudioOutputSource(p["soundOutput"])
        },
        "set_audio_output": {
            "uri": "ssap://audio/changeSoundOutput",
            "args": [str],
            "payload": {"output": arguments(0)}
        },
        "get_sound_output": {
            "uri": "ssap://audio/getSoundOutput",
            "validation": standard_validation,
            "subscription": True,
        },
    }
    
    async def set_volume_with_monitoring(self, volume: int, timeout: float = 5.0) -> Dict[str, Any]:
        """Set volume with enhanced monitoring.
        
        This method uses our persistent callback pattern to set the volume and monitor
        until the volume change is complete.
        
        Args:
            volume: Volume level to set (0-100)
            timeout: Timeout in seconds to wait for the volume change to complete
            
        Returns:
            Response with volume change status and details
        """
        # Send volume change request with a persistent queue
        queue = await self.client.send_message('request', 'ssap://audio/setVolume', 
                                         {"volume": volume}, get_queue=True)
        
        # Monitor the volume change process
        start_time = asyncio.get_event_loop().time()
        volume_status = {"status": "unknown", "returnValue": False}
        
        try:
            # Get the initial response
            initial_response = await asyncio.wait_for(queue.get(), timeout=3.0)
            volume_status = initial_response.get('payload', {})
            
            # If the volume change failed immediately, return early
            if not volume_status.get("returnValue", False):
                return volume_status
                
            # Set status to changing based on initial response
            volume_status["status"] = "changing"
            
            # Wait for any additional messages that might indicate volume status
            try:
                while asyncio.get_event_loop().time() - start_time < timeout:
                    response = await asyncio.wait_for(queue.get(), timeout=0.5)
                    response_payload = response.get('payload', {})
                    
                    # Check for volume change notification
                    if 'volume' in response_payload and response_payload.get('volume') == volume:
                        volume_status["status"] = "changed"
                        volume_status["volumeStatus"] = response_payload
                        return volume_status
                    
                    # Short delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # No additional volume messages received
                # Try to get current volume to confirm the change
                try:
                    current_volume = await self.get_volume()
                    if current_volume.get("volume") == volume:
                        volume_status["status"] = "changed"
                        volume_status["volumeStatus"] = current_volume
                        return volume_status
                except Exception:
                    pass
                
        except asyncio.TimeoutError:
            # Timeout waiting for the initial response
            volume_status["status"] = "timeout"
            volume_status["error"] = "Timeout waiting for volume change response"
            
        return volume_status
    
    async def set_mute_with_monitoring(self, mute: bool, timeout: float = 5.0) -> Dict[str, Any]:
        """Set mute state with enhanced monitoring.
        
        This method uses our persistent callback pattern to set the mute state and monitor
        until the change is complete.
        
        Args:
            mute: True to mute, False to unmute
            timeout: Timeout in seconds to wait for the mute change to complete
            
        Returns:
            Response with mute change status and details
        """
        # Send mute change request with a persistent queue
        queue = await self.client.send_message('request', 'ssap://audio/setMute', 
                                         {"mute": mute}, get_queue=True)
        
        # Monitor the mute change process
        start_time = asyncio.get_event_loop().time()
        mute_status = {"status": "unknown", "returnValue": False}
        
        try:
            # Get the initial response
            initial_response = await asyncio.wait_for(queue.get(), timeout=3.0)
            mute_status = initial_response.get('payload', {})
            
            # If the mute change failed immediately, return early
            if not mute_status.get("returnValue", False):
                return mute_status
                
            # Set status to changing based on initial response
            mute_status["status"] = "changing"
            
            # Wait for any additional messages that might indicate mute status
            try:
                while asyncio.get_event_loop().time() - start_time < timeout:
                    response = await asyncio.wait_for(queue.get(), timeout=0.5)
                    response_payload = response.get('payload', {})
                    
                    # Check for mute change notification
                    if 'muted' in response_payload and response_payload.get('muted') == mute:
                        mute_status["status"] = "changed"
                        mute_status["muteStatus"] = response_payload
                        return mute_status
                    
                    # Short delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # No additional mute messages received
                # Try to get current audio status to confirm the change
                try:
                    current_status = await self.get_mute()
                    if current_status == mute:
                        mute_status["status"] = "changed"
                        mute_status["muteStatus"] = {"muted": current_status}
                        return mute_status
                except Exception:
                    pass
                
        except asyncio.TimeoutError:
            # Timeout waiting for the initial response
            mute_status["status"] = "timeout"
            mute_status["error"] = "Timeout waiting for mute change response"
            
        return mute_status
    
    def list_audio_output_sources(self):
        """List available audio output sources.
        
        Returns:
            List of AudioOutputSource objects
        """
        sources = ['tv_speaker', 'external_speaker', 'soundbar', 'bt_soundbar', 'tv_external_speaker']
        return [AudioOutputSource(x) for x in sources]


class TvControl(WebOSControlBase):
    """Control for TV specific functions."""
    
    COMMANDS = {
        "channel_up": {"uri": "ssap://tv/channelUp"},
        "channel_down": {"uri": "ssap://tv/channelDown"},
        "get_channels": {
            "uri": "ssap://tv/getChannelList",
            "validation": standard_validation,
            "return": lambda p: p["channelList"]
        },
        "get_current_channel": {
            "uri": "ssap://tv/getCurrentChannel",
            "validation": standard_validation,
            "subscription": True,
        },
        "get_channel_info": {
            "uri": "ssap://tv/getChannelProgramInfo",
            "validation": standard_validation,
        },
        "set_channel": {
            "uri": "ssap://tv/openChannel",
            "args": [dict],
            "payload": arguments(0),
        }
    }


class SystemControl(WebOSControlBase):
    """Control for system functions."""
    
    COMMANDS = {
        "power_off": {
            "uri": "ssap://system/turnOff",
            "validation": standard_validation,
        },
        "power_on": {
            "uri": "ssap://system/turnOn",
            "validation": standard_validation,
        },
        "info": {
            "uri": "ssap://system/getSystemInfo",
            "validation": standard_validation,
        },
        "notify": {
            "uri": "ssap://system.notifications/createToast",
            "payload": {"message": arguments(0)},
            "validation": standard_validation,
        },
        "launcher": {
            "uri": "ssap://com.webos.applicationManager/listLaunchPoints",
            "validation": standard_validation,
        },
        "get_settings": {
            "uri": "ssap://settings/getSystemSettings",
            "validation": standard_validation,
        },
    }

    async def power_off_with_monitoring(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Power off the TV with enhanced monitoring.
        
        This method sends the power off command and monitors the response to detect
        when the TV has fully powered off. It uses the persistent callback pattern
        to ensure all messages are properly processed.
        
        Args:
            timeout: Timeout in seconds to wait for power off to complete
            
        Returns:
            Response with power off status and details
        """
        # Call the send_message directly to bypass the standard command handling
        # This allows us to use the persistent callback pattern
        queue = await self.client.send_message('request', 'ssap://system/turnOff', {}, get_queue=True)
        
        # Monitor the power off process
        start_time = asyncio.get_event_loop().time()
        power_status = {"status": "unknown", "returnValue": False}
        
        try:
            # Get the initial response
            initial_response = await asyncio.wait_for(queue.get(), timeout=5.0)
            power_status = initial_response.get('payload', {})
            
            # If the command failed immediately, return early
            if not power_status.get("returnValue", False):
                return power_status
                
            # Set status to succeeded based on initial response
            power_status["status"] = "succeeded"
            
            # Wait for any additional messages (like power state change notifications)
            try:
                while asyncio.get_event_loop().time() - start_time < timeout:
                    response = await asyncio.wait_for(queue.get(), timeout=1.0)
                    response_payload = response.get('payload', {})
                    
                    # Update power status if we get additional information
                    if 'state' in response_payload:
                        power_status["powerState"] = response_payload.get('state')
                        if response_payload.get('state') == 'Off':
                            power_status["status"] = "powered_off"
                            return power_status
                    
                    # Short delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # No additional power state messages received
                pass
                
        except asyncio.TimeoutError:
            # Timeout waiting for the initial response
            power_status["status"] = "timeout"
            power_status["error"] = "Timeout waiting for power off response"
            
        return power_status
        
    async def power_on_with_monitoring(self, timeout: float = 20.0) -> Dict[str, Any]:
        """Power on the TV with enhanced monitoring.
        
        This method sends the power on command and monitors the response to detect
        when the TV has fully powered on. It uses the persistent callback pattern
        to ensure all messages are properly processed.
        
        Note: This may not work on all TV models and may require Wake-on-LAN instead.
        
        Args:
            timeout: Timeout in seconds to wait for power on to complete
            
        Returns:
            Response with power on status and details
        """
        # Call the send_message directly to bypass the standard command handling
        queue = await self.client.send_message('request', 'ssap://system/turnOn', {}, get_queue=True)
        
        # Monitor the power on process
        start_time = asyncio.get_event_loop().time()
        power_status = {"status": "unknown", "returnValue": False}
        
        try:
            # Get the initial response
            initial_response = await asyncio.wait_for(queue.get(), timeout=5.0)
            power_status = initial_response.get('payload', {})
            
            # If the command failed immediately, return early
            if not power_status.get("returnValue", False):
                return power_status
                
            # Set status to initiated based on initial response
            power_status["status"] = "initiated"
            
            # Wait for additional messages (like power state change notifications)
            try:
                while asyncio.get_event_loop().time() - start_time < timeout:
                    response = await asyncio.wait_for(queue.get(), timeout=1.0)
                    response_payload = response.get('payload', {})
                    
                    # Update power status if we get additional information
                    if 'state' in response_payload:
                        power_status["powerState"] = response_payload.get('state')
                        if response_payload.get('state') == 'Active':
                            power_status["status"] = "powered_on"
                            return power_status
                    
                    # Short delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # No additional power state messages received
                pass
                
        except asyncio.TimeoutError:
            # Timeout waiting for the initial response
            power_status["status"] = "timeout"
            power_status["error"] = "Timeout waiting for power on response"
            
        return power_status


class ApplicationControl(WebOSControlBase):
    """Control for application management."""
    
    COMMANDS = {
        "list_apps": {
            "uri": "ssap://com.webos.applicationManager/listApps",
            "validation": standard_validation,
            "return": lambda payload: [Application(x) for x in payload.get("apps", [])]
        },
        "list_launcher": {
            "uri": "ssap://com.webos.applicationManager/listLaunchPoints",
            "validation": standard_validation,
            "return": lambda payload: [Application(x) for x in payload.get("launchPoints", [])]
        },
        "get_app_status": {
            "uri": "ssap://com.webos.applicationManager/getAppStatus",
            "payload": {"appId": arguments(0)},
            "validation": standard_validation,
        },
        "get_current": {
            "uri": "ssap://com.webos.applicationManager/getForegroundAppInfo",
            "validation": standard_validation,
            "return": lambda payload: Application(payload),
        },
        "launch": {
            "uri": "ssap://com.webos.applicationManager/launch",
            "payload": {"id": arguments(0)},
            "validation": standard_validation,
        },
        "launch_params": {
            "uri": "ssap://com.webos.applicationManager/launch",
            "payload": {"id": arguments(0), "params": arguments(1)},
            "validation": standard_validation,
        },
        "close": {
            "uri": "ssap://com.webos.applicationManager/closeApp",
            "payload": {"id": arguments(0)},
            "validation": standard_validation,
        },
    }

    async def launch_with_monitoring(self, app_id: str, params: Optional[Dict[str, Any]] = None, 
                               timeout: float = 30.0) -> Dict[str, Any]:
        """Launch an app and monitor until it's fully loaded.
        
        This method uses our persistent callback pattern to monitor the app launch process
        and returns once the app is fully launched or the timeout is reached.
        
        Args:
            app_id: ID of the app to launch
            params: Parameters to pass to the app (optional)
            timeout: Timeout in seconds to wait for the app to launch
            
        Returns:
            Response with app launch status and details
        """
        # Prepare the payload
        payload = {"id": app_id}
        if params:
            payload["params"] = params
        
        # Send the launch request with a persistent queue
        queue = await self.client.send_message('request', 'ssap://com.webos.applicationManager/launch', 
                                         payload, get_queue=True)
        
        # Monitor the launch process
        start_time = asyncio.get_event_loop().time()
        launch_status = {"status": "unknown", "returnValue": False}
        
        try:
            # Get the initial response
            initial_response = await asyncio.wait_for(queue.get(), timeout=5.0)
            launch_status = initial_response.get('payload', {})
            
            # If the launch failed immediately, return early
            if not launch_status.get("returnValue", False):
                return launch_status
                
            # Set status to launched based on initial response
            launch_status["status"] = "launched"
            
            # Try to get foreground app info to confirm the app is in foreground
            try:
                foreground_info = await self.get_current()
                if foreground_info and foreground_info.id == app_id:
                    launch_status["status"] = "foreground"
                    launch_status["appInfo"] = foreground_info
                    return launch_status
            except Exception as e:
                # Couldn't get foreground app info, continue with monitoring
                pass
                
            # Wait for additional messages that might indicate app status
            try:
                while asyncio.get_event_loop().time() - start_time < timeout:
                    response = await asyncio.wait_for(queue.get(), timeout=1.0)
                    response_payload = response.get('payload', {})
                    
                    # Check if this looks like a foreground app change notification
                    if ('appId' in response_payload and response_payload.get('appId') == app_id) or \
                       ('id' in response_payload and response_payload.get('id') == app_id and 
                        'running' in response_payload and response_payload.get('running')):
                        launch_status["status"] = "foreground"
                        launch_status["appInfo"] = response_payload
                        return launch_status
                    
                    # Short delay to prevent tight loop
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                # No additional app status messages received
                # Try one more time to get foreground app info
                try:
                    foreground_info = await self.get_current()
                    if foreground_info and foreground_info.id == app_id:
                        launch_status["status"] = "foreground"
                        launch_status["appInfo"] = foreground_info
                except Exception:
                    pass
                
        except asyncio.TimeoutError:
            # Timeout waiting for the initial response
            launch_status["status"] = "timeout"
            launch_status["error"] = "Timeout waiting for launch response"
            
        return launch_status


class InputControl(WebOSControlBase):
    """Control for input handling."""
    
    COMMANDS = {
        "type": {
            "uri": "ssap://com.webos.service.ime/insertText",
            "args": [str],
            "payload": {"text": arguments(0), "replace": 0}
        },
        "delete": {
            "uri": "ssap://com.webos.service.ime/deleteCharacters",
            "args": [int],
            "payload": {"count": arguments(0)}
        },
        "enter": {"uri": "ssap://com.webos.service.ime/sendEnterKey"},
    }

    # Button command names for the TV
    BUTTON_COMMANDS = {
        "left": "LEFT",
        "right": "RIGHT",
        "up": "UP",
        "down": "DOWN",
        "home": "HOME",
        "back": "BACK",
        "menu": "MENU",
        "enter": "ENTER",
        "dash": "DASH",
        "info": "INFO",
        "num_0": "0",
        "num_1": "1",
        "num_2": "2",
        "num_3": "3",
        "num_4": "4",
        "num_5": "5",
        "num_6": "6",
        "num_7": "7",
        "num_8": "8",
        "num_9": "9",
        "asterisk": "ASTERISK",
        "cc": "CC",
        "exit": "EXIT",
        "mute": "MUTE",
        "red": "RED",
        "green": "GREEN",
        "yellow": "YELLOW",
        "blue": "BLUE",
        "volumeup": "VOLUMEUP",
        "volumedown": "VOLUMEDOWN",
        "channelup": "CHANNELUP",
        "channeldown": "CHANNELDOWN",
        "play": "PLAY",
        "pause": "PAUSE",
        "stop": "STOP",
        "rewind": "REWIND",
        "fastforward": "FASTFORWARD",
    }

    def __init__(self, client):
        """Initialize the input control.
        
        Args:
            client: WebOSClient instance
        """
        super(InputControl, self).__init__(client)
        self.pointer_socket_uri = None
        self._pointer_websocket = None
        self._pointer_lock = asyncio.Lock()
        self._is_connected = False
        self._connection_attempts = 0
        self._max_attempts = 3
        
        # Create methods for each button command
        for cmd_name, button in self.BUTTON_COMMANDS.items():
            setattr(self, cmd_name, self._create_button_method(button))
        
        # Create methods for pointer commands
        setattr(self, "click", self._create_click_method())
        setattr(self, "move", self._create_move_method())
        setattr(self, "scroll", self._create_scroll_method())

    def _create_button_method(self, button_name):
        """Create a method for a button command.
        
        Args:
            button_name: Name of the button
            
        Returns:
            Function that sends the button command
        """
        async def button_method():
            """Send a button press command to the TV."""
            # First try using the pointer socket method (preferred)
            try:
                if not self._is_connected:
                    await self.connect_input()
                
                if self._is_connected:
                    return await self._send_pointer_command({
                        "type": "button",
                        "name": button_name
                    })
            except Exception as e:
                logger.warning(f"Failed to send button via pointer socket: {e}, trying direct service")
                
            # Fallback to direct service request
            try:
                response = await self.request(
                    "ssap://com.webos.service.networkinput/sendInputButton",
                    {"buttonName": button_name},
                    block=True
                )
                return response
            except Exception as e:
                logger.error(f"All methods to send button {button_name} failed: {e}")
                raise
                
        return button_method
        
    def _create_click_method(self):
        """Create a method for clicking.
        
        Returns:
            Function that sends a click command
        """
        async def click_method(x=None, y=None, drag=False):
            """Send a click command to the TV.
            
            Args:
                x: X-coordinate (optional)
                y: Y-coordinate (optional)
                drag: Whether to drag (optional)
            """
            if not self._is_connected:
                await self.connect_input()
            
            payload = {"type": "click"}
            if x is not None and y is not None:
                payload["x"] = x
                payload["y"] = y
            
            if drag:
                payload["drag"] = True
                
            return await self._send_pointer_command(payload)
        return click_method
        
    def _create_move_method(self):
        """Create a method for moving the pointer.
        
        Returns:
            Function that sends a move command
        """
        async def move_method(x, y, drag=False):
            """Send a move command to the TV.
            
            Args:
                x: X-coordinate
                y: Y-coordinate
                drag: Whether to drag (optional)
            """
            if not self._is_connected:
                await self.connect_input()
            
            payload = {
                "type": "move",
                "x": x,
                "y": y
            }
            
            if drag:
                payload["drag"] = True
                
            return await self._send_pointer_command(payload)
        return move_method
    
    def _create_scroll_method(self):
        """Create a method for scrolling.
        
        Returns:
            Function that sends a scroll command
        """
        async def scroll_method(x, y, wheel_direction):
            """Send a scroll command to the TV.
            
            Args:
                x: X-coordinate
                y: Y-coordinate
                wheel_direction: Direction to scroll
            """
            if not self._is_connected:
                await self.connect_input()
            
            payload = {
                "type": "scroll",
                "x": x,
                "y": y,
                "wheelDirection": wheel_direction
            }
                
            return await self._send_pointer_command(payload)
        return scroll_method
    
    async def connect_input(self):
        """Connect to the TV's input socket.
        
        This method explicitly establishes a connection to the pointer input
        socket, using the same approach as PyWebOSTV. It should be called before
        sending input commands for reliable behavior.
        
        Raises:
            IOError: If connection to the input socket fails
        """
        async with self._pointer_lock:
            # Reset connection state
            self._is_connected = False
            self._connection_attempts = 0
            
            # Get the pointer socket URI
            try:
                logger.debug("Getting pointer input socket URI")
                response = await self.request(
                    "ssap://com.webos.service.networkinput/getPointerInputSocket", 
                    {}, 
                    block=True
                )
                
                logger.debug(f"Pointer socket response: {response}")
                
                if not response or not response.get("payload"):
                    raise IOError("No response or empty payload from getPointerInputSocket request")
                    
                socket_path = response.get("payload", {}).get("socketPath")
                if not socket_path:
                    raise IOError("No socketPath in response payload")
                    
                self.pointer_socket_uri = socket_path
                logger.debug(f"Got pointer socket URI: {socket_path}")
                
                # Establish WebSocket connection
                while self._connection_attempts < self._max_attempts:
                    self._connection_attempts += 1
                    try:
                        # Close any existing connection
                        if self._pointer_websocket:
                            try:
                                await self._pointer_websocket.close()
                            except Exception:
                                pass
                            self._pointer_websocket = None
                        
                        # Check if we have a secure client with SSL context
                        ssl_context = None
                        
                        # Access _create_ssl_context if available (from SecureWebOSClient)
                        if hasattr(self.client, '_create_ssl_context'):
                            try:
                                ssl_context = self.client._create_ssl_context()
                                logger.debug("Using SSL context from client for pointer socket")
                            except Exception as e:
                                logger.warning(f"Failed to get SSL context from client: {e}")
                        
                        # Create new connection with websockets 15.0.1 compatible parameters
                        # Using empty dict for extra_headers to avoid Origin header
                        logger.debug(f"Connecting to pointer socket (attempt {self._connection_attempts})")
                        
                        # Connection parameters
                        connect_kwargs = {
                            'extra_headers': {},  # Empty dict to avoid default headers including Origin
                            'open_timeout': 10,   # Add timeout for connection
                        }
                        
                        # Add SSL context if available
                        if ssl_context and self.pointer_socket_uri.startswith('wss://'):
                            connect_kwargs['ssl'] = ssl_context
                        
                        self._pointer_websocket = await websockets.client.connect(
                            self.pointer_socket_uri,
                            **connect_kwargs
                        )
                        
                        # Send a registration command exactly like PyWebOSTV does
                        # This is a critical step that was missing in the original implementation
                        logger.debug("Registering with pointer socket")
                        register_payload = "register\n\n"
                        await self._pointer_websocket.send(register_payload)
                        
                        # If we get here without exception, connection is successful
                        self._is_connected = True
                        logger.info("Successfully connected to pointer input socket")
                        break
                        
                    except Exception as e:
                        logger.warning(f"Attempt {self._connection_attempts} to connect to pointer socket failed: {e}")
                        if self._connection_attempts >= self._max_attempts:
                            raise IOError(f"Failed to connect to pointer socket after {self._max_attempts} attempts: {e}")
                        await asyncio.sleep(1)  # Brief delay before retry
                
                if not self._is_connected:
                    raise IOError("Failed to establish pointer socket connection")
                    
            except Exception as e:
                logger.error(f"Failed to connect to pointer input: {e}")
                self._is_connected = False
                raise IOError(f"Failed to connect to pointer input: {e}")
    
    async def _send_pointer_command(self, payload):
        """Send a command to the pointer socket.
        
        Args:
            payload: Payload to send
            
        Returns:
            Response from the TV
            
        Raises:
            IOError: If we couldn't send the command
        """
        if not self._is_connected or not self._pointer_websocket:
            await self.connect_input()
            
        try:
            # Format payload exactly like PyWebOSTV does
            formatted_payload = ""
            for key, value in payload.items():
                formatted_payload += f"{key}:{value}\n"
            formatted_payload += "\n"
            
            logger.debug(f"Sending pointer command: {formatted_payload}")
            await self._pointer_websocket.send(formatted_payload)
            return {"returnValue": True}
        except Exception as e:
            # If sending fails, mark connection as broken and propagate error
            self._is_connected = False
            raise IOError(f"Failed to send pointer command: {e}")
    
    async def disconnect_input(self):
        """Disconnect from the pointer input socket.
        
        This method explicitly closes the pointer input connection, mirroring
        PyWebOSTV's behavior. Call this when you're done with input commands.
        """
        async with self._pointer_lock:
            if self._pointer_websocket:
                try:
                    await self._pointer_websocket.close()
                    logger.debug("Disconnected from pointer input socket")
                except Exception as e:
                    logger.warning(f"Error disconnecting from pointer socket: {e}")
                finally:
                    self._pointer_websocket = None
                    self._is_connected = False
    
    async def close(self):
        """Close the pointer websocket connection if it exists.
        
        Call this method when shutting down to ensure all resources are released.
        """
        await self.disconnect_input()
    
    async def list_inputs(self) -> Dict[str, Any]:
        """Get a list of available input sources.
        
        Returns:
            Dict containing a list of input sources
        """
        queue = await self.client.send_message('request', 'ssap://tv/getExternalInputList', {}, get_queue=True)
        response = await queue.get()
        return response.get('payload', {})
        
    async def get_input(self) -> Dict[str, Any]:
        """Get the current input source.
        
        Returns:
            Dict containing information about the current input source
        """
        queue = await self.client.send_message('request', 'ssap://tv/getCurrentExternalInput', {}, get_queue=True)
        response = await queue.get()
        return response.get('payload', {})
    
    async def set_input(self, input_id: str) -> Dict[str, Any]:
        """Switch to a different input source.
        
        Args:
            input_id: ID of the input source to switch to
            
        Returns:
            Response from the TV
        """
        queue = await self.client.send_message('request', 'ssap://tv/switchInput', 
                                         {"inputId": input_id}, get_queue=True)
        response = await queue.get()
        return response.get('payload', {})


class SourceControl(WebOSControlBase):
    """Control for input sources."""
    
    COMMANDS = {
        "list_sources": {
            "uri": "ssap://tv/getExternalInputList",
            "validation": standard_validation,
            "return": lambda p: [InputSource(x) for x in p["devices"]]
        },
        "get_source": {
            "uri": "ssap://tv/getExternalInputList",
            "validation": standard_validation,
            "return": lambda p: p["devices"]
        },
        "set_source": {
            "uri": "ssap://tv/switchInput",
            "args": [dict],
            "validation": standard_validation,
            "payload": arguments(0)
        },
        "get_source_info": {
            "uri": "ssap://tv/getCurrentExternalInput",
            "validation": standard_validation
        }
    }
