"""Control interfaces for WebOS TV."""

import base64
import asyncio
import json
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from uuid import uuid4
import websockets

from asyncwebostv.model import Application, InputSource, AudioOutputSource

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
    """Control for media playback on the TV."""
    
    def list_audio_output_sources(self):
        """List available audio output sources.
        
        Returns:
            List of AudioOutputSource objects
        """
        sources = ['tv_speaker', 'external_speaker', 'soundbar', 'bt_soundbar', 'tv_external_speaker']
        return [AudioOutputSource(x) for x in sources]

    COMMANDS = {
        "volume_up": {"uri": "ssap://audio/volumeUp"},
        "volume_down": {"uri": "ssap://audio/volumeDown"},
        "get_volume": {
            "uri": "ssap://audio/getVolume",
            "validation": standard_validation,
            "subscription": True,
        },
        "set_volume": {
            "uri": "ssap://audio/setVolume",
            "args": [int],
            "payload": {"volume": arguments(0)}
        },
        "mute": {
            "uri": "ssap://audio/setMute",
            "args": [bool],
            "payload": {"mute": arguments(0)}
        },
        "play": {"uri": "ssap://media.controls/play"},
        "pause": {"uri": "ssap://media.controls/pause"},
        "stop": {"uri": "ssap://media.controls/stop"},
        "rewind": {"uri": "ssap://media.controls/rewind"},
        "fast_forward": {"uri": "ssap://media.controls/fastForward"},
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
        "power_off": {"uri": "ssap://system/turnOff"},
        "info": {
            "uri": "ssap://system/getSystemInfo",
            "validation": standard_validation,
        },
        "notify": {
            "uri": "ssap://system.notifications/createToast",
            "args": [str],
            "payload": {"message": arguments(0)}
        },
        "launcher_close": {
            "uri": "ssap://com.webos.app.home/close"
        },
        "launcher_ready": {
            "uri": "ssap://com.webos.app.home/ready"
        },
        "power_state": {
            "uri": "ssap://com.webos.service.tvpower/power/getPowerState",
            "validation": standard_validation,
            "subscription": True,
        },
        "turn_on": {
            "uri": "ssap://system/turnOn"
        }
    }


class ApplicationControl(WebOSControlBase):
    """Control for application management."""
    
    COMMANDS = {
        "list_apps": {
            "uri": "ssap://com.webos.applicationManager/listApps",
            "args": [],
            "kwargs": {},
            "validation": standard_validation,
            "return": lambda p: [Application(x) for x in p["apps"]]
        },
        "get_app_status": {
            "uri": "ssap://system.launcher/getAppState",
            "args": [dict],
            "validation": standard_validation,
            "payload": arguments(0),
        },
        "launch": {
            "uri": "ssap://system.launcher/launch",
            "args": [dict],
            "validation": standard_validation,
            "payload": arguments(0),
        },
        "launch_app": {
            "uri": "ssap://system.launcher/launch",
            "args": [str, dict],
            "kwargs": {"content_id": str},
            "validation": standard_validation,
            "payload": {
                "id": arguments(0),
                "contentId": arguments("content_id", default=None)
            }
        },
        "close": {
            "uri": "ssap://system.launcher/close",
            "args": [dict],
            "validation": standard_validation,
            "payload": arguments(0),
        },
        "close_app": {
            "uri": "ssap://system.launcher/close",
            "args": [str],
            "validation": standard_validation,
            "payload": {"id": arguments(0)}
        }
    }


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

    INPUT_COMMANDS = {
        "move": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "payload": {"x": arguments(0), "y": arguments(1), "drag": arguments("drag", default=False)}
        },
        "click": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "payload": {"x": arguments(0), "y": arguments(1), "click": True}
        },
        "scroll": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "payload": {"x": arguments(0), "y": arguments(1), "wheelDirection": arguments(2),
                        "drag": arguments("drag", default=False)}
        },
        "button": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "payload": {"button": arguments(0), "press": arguments("press", default=True)}
        },
        "move_mouse": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "payload": {"dx": arguments(0), "dy": arguments(1), "drag": arguments("drag", default=False), "move": True}
        },
        "home": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "HOME"}
        },
        "back": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "BACK"}
        },
        "up": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "UP"}
        },
        "down": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "DOWN"}
        },
        "left": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "LEFT"}
        },
        "right": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "RIGHT"}
        },
        "ok": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "ENTER"}
        },
        "dash": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "DASH"}
        },
        "info": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "INFO"}
        },
        "num_1": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "1"}
        },
        "num_2": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "2"}
        },
        "num_3": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "3"}
        },
        "num_4": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "4"}
        },
        "num_5": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "5"}
        },
        "num_6": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "6"}
        },
        "num_7": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "7"}
        },
        "num_8": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "8"}
        },
        "num_9": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "9"}
        },
        "num_0": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "0"}
        },
        "asterisk": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "ASTERISK"}
        },
        "cc": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "CC"}
        },
        "exit": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "EXIT"}
        },
        "mute": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "MUTE"}
        },
        "red": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "RED"}
        },
        "green": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "GREEN"}
        },
        "yellow": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "YELLOW"}
        },
        "blue": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "BLUE"}
        },
        "volume_up": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "VOLUMEUP"}
        },
        "volume_down": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "VOLUMEDOWN"}
        },
        "channel_up": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "CHANNELUP"}
        },
        "channel_down": {
            "uri": "ssap://com.webos.service.networkinput/getPointerInputSocket",
            "args": [],
            "payload": {"button": "CHANNELDOWN"}
        }
    }

    def __init__(self, *args, **kwargs):
        """Initialize the input control."""
        super(InputControl, self).__init__(*args, **kwargs)
        self.ws_client = None

    def __getattr__(self, name):
        """Get an attribute, handling command execution for mouse input."""
        if name in self.INPUT_COMMANDS:
            return self.exec_mouse_command(name, self.INPUT_COMMANDS[name])

        return super(InputControl, self).__getattr__(name)

    async def connect_input(self):
        """Connect to the input socket."""
        uri = await self.request("ssap://com.webos.service.networkinput/getPointerInputSocket",
                          {}, block=True)
        
        socket_path = uri.get("payload", {}).get("socketPath")
        if not socket_path:
            raise ValueError("Failed to get pointer input socket path")
            
        self.ws_client = await websockets.client.connect(socket_path)
        return self.ws_client

    async def disconnect_input(self):
        """Disconnect from the input socket."""
        if self.ws_client:
            await self.ws_client.close()
            self.ws_client = None

    def exec_mouse_command(self, cmd_name, cmd_info):
        """Execute a mouse command.
        
        Args:
            cmd_name: Command name
            cmd_info: Command information
            
        Returns:
            Function that executes the command
        """
        async def request_func(*args, **kwargs):
            if not self.ws_client:
                await self.connect_input()
                
            payload = process_payload(cmd_info.get("payload"), *args, **kwargs)
            await self.ws_client.send(json.dumps(payload))
        return request_func


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
        }
    }
