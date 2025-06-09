# AsyncWebOSTV Subscription Specification

This document provides a complete specification for all subscription functionality available in the AsyncWebOSTV library.

## Overview

AsyncWebOSTV supports **5 real-time subscriptions** that allow applications to monitor TV state changes without polling. All subscriptions use the same pattern with dynamically generated methods.

### Subscription Pattern

All subscriptions follow this consistent API:

```python
# Subscribe to events
await control.subscribe_<command_name>(callback_function)

# Unsubscribe from events
await control.unsubscribe_<command_name>()
```

### Callback Function Signature

All subscription callbacks must follow this signature:

```python
async def callback(success: bool, payload: Any) -> None:
    """Handle subscription events.

    Args:
        success: True if event is valid, False if error occurred
        payload: Event data (varies by subscription) or error message
    """
    if success:
        # Process the event data
        print(f"Event received: {payload}")
    else:
        # Handle the error
        print(f"Subscription error: {payload}")
```

---

## Available Subscriptions

### 1. Volume Subscription 🔊

**Control Class:** `MediaControl`  
**Methods:** `subscribe_get_volume()` / `unsubscribe_get_volume()`  
**URI:** `ssap://audio/getVolume`  
**Added:** v0.1.1 ✨

Monitor real-time volume level and mute status changes.

#### Callback Payload

```python
{
    "volume": 25,        # Current volume level (0-100)
    "muted": false,      # Whether audio is muted
    "returnValue": true  # Success indicator
}
```

#### Usage Example

```python
from asyncwebostv.controls import MediaControl

async def volume_handler(success: bool, payload: dict):
    if success:
        volume = payload.get("volume", 0)
        muted = payload.get("muted", False)
        status = "🔇 MUTED" if muted else f"🔊 {volume}%"
        print(f"Volume changed: {status}")
    else:
        print(f"Volume subscription error: {payload}")

# Setup
media = MediaControl(client)
await media.subscribe_get_volume(volume_handler)

# Cleanup
await media.unsubscribe_get_volume()
```

#### Trigger Events

- User changes volume via remote control
- App calls `set_volume()` or `volume_up()`/`volume_down()`
- User toggles mute via remote or `set_mute()`

---

### 2. Audio Output Subscription 🎵

**Control Class:** `MediaControl`  
**Methods:** `subscribe_get_audio_output()` / `unsubscribe_get_audio_output()`  
**URI:** `ssap://audio/getSoundOutput`  
**Return Type:** `AudioOutputSource` object

Monitor changes to the active audio output device.

#### Callback Payload

```python
# The callback receives an AudioOutputSource object
<AudioOutputSource 'tv_speaker'>
<AudioOutputSource 'soundbar'>
<AudioOutputSource 'bt_soundbar'>
```

#### Raw Data Structure

```python
{
    "soundOutput": "tv_speaker",  # Current audio output
    "returnValue": true          # Success indicator
}
```

#### Usage Example

```python
async def audio_output_handler(success: bool, audio_source):
    if success:
        # audio_source is an AudioOutputSource object
        output_type = str(audio_source.data)
        print(f"Audio output changed to: {output_type}")
    else:
        print(f"Audio output subscription error: {audio_source}")

await media.subscribe_get_audio_output(audio_output_handler)
```

#### Possible Output Values

- `"tv_speaker"` - Built-in TV speakers
- `"external_speaker"` - External speakers via audio jack
- `"soundbar"` - Connected soundbar
- `"bt_soundbar"` - Bluetooth soundbar
- `"tv_external_speaker"` - Combined TV and external

---

### 3. Sound Output Subscription 🎧

**Control Class:** `MediaControl`  
**Methods:** `subscribe_get_sound_output()` / `unsubscribe_get_sound_output()`  
**URI:** `ssap://audio/getSoundOutput`  
**Return Type:** Raw dictionary

Alternative sound output monitoring (same URI as audio output but returns raw data).

#### Callback Payload

```python
{
    "soundOutput": "tv_speaker",  # Current sound output
    "returnValue": true          # Success indicator
}
```

#### Usage Example

```python
async def sound_output_handler(success: bool, payload: dict):
    if success:
        output = payload.get("soundOutput", "unknown")
        print(f"Sound output: {output}")
    else:
        print(f"Sound output error: {payload}")

await media.subscribe_get_sound_output(sound_output_handler)
```

---

### 4. Channel Subscription 📺

**Control Class:** `TvControl`  
**Methods:** `subscribe_get_current_channel()` / `unsubscribe_get_current_channel()`  
**URI:** `ssap://tv/getCurrentChannel`

Monitor TV channel changes.

#### Callback Payload

```python
{
    "channelNumber": "1",           # Channel number as string
    "channelName": "NBC",           # Channel display name
    "channelId": "1_0_1_0_0_1234", # Internal channel ID
    "signalChannelId": "1_0_1_0_0_1234",
    "channelModeId": 0,
    "channelTypeId": 0,
    "physicalNumber": 1,
    "isInvisible": false,
    "favoriteGroup": null,
    "imgUrl": "",
    "display": true,
    "returnValue": true
}
```

#### Usage Example

```python
async def channel_handler(success: bool, payload: dict):
    if success:
        number = payload.get("channelNumber", "?")
        name = payload.get("channelName", "Unknown")
        print(f"Channel changed: {number} - {name}")
    else:
        print(f"Channel subscription error: {payload}")

# Setup
tv = TvControl(client)
await tv.subscribe_get_current_channel(channel_handler)
```

#### Trigger Events

- User changes channel via remote control
- App calls `set_channel()`
- Channel scanning or auto-tune events

---

### 5. Power State Subscription ⚡

**Control Class:** `SystemControl`  
**Methods:** `subscribe_power_state()` / `unsubscribe_power_state()`  
**URI:** `ssap://com.webos.service.power/power/getPowerState`  
**Added:** v0.1.1 ✨

Monitor TV power state and power management events.

#### Callback Payload

```python
{
    "state": "Active",           # Current power state
    "processing": false,         # Whether power operation in progress
    "powerOnReason": "",         # Reason for last power on
    "returnValue": true          # Success indicator
}
```

#### Power States

- `"Active"` - TV is on and fully operational
- `"Off"` - TV is completely powered off
- `"Suspend"` - TV is in standby/sleep mode
- `"Screen Off"` - Display off but system running
- `"Power Saving"` - Low power mode

#### Usage Example

```python
async def power_handler(success: bool, payload: dict):
    if success:
        state = payload.get("state", "unknown")
        processing = payload.get("processing", False)
        status = f"{state} {'(processing)' if processing else ''}"
        print(f"Power state: {status}")
    else:
        print(f"Power state error: {payload}")

# Setup
system = SystemControl(client)
await system.subscribe_power_state(power_handler)
```

#### Trigger Events

- User powers TV on/off via remote
- App calls `power_off()` or `power_on()`
- Sleep timer activation
- Energy saving mode changes
- Wake-on-LAN events

---

## Complete Usage Example

```python
import asyncio
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, TvControl, SystemControl

async def main():
    # Connect to TV
    client = WebOSClient("192.168.1.100")
    await client.connect()

    # Register if needed
    store = {}
    async for status in client.register(store):
        if status == WebOSClient.REGISTERED:
            break

    # Create control interfaces
    media = MediaControl(client)
    tv = TvControl(client)
    system = SystemControl(client)

    # Define event handlers
    async def volume_handler(success, payload):
        if success:
            vol = payload.get("volume", 0)
            muted = payload.get("muted", False)
            print(f"🔊 Volume: {vol}% {'🔇' if muted else ''}")

    async def channel_handler(success, payload):
        if success:
            num = payload.get("channelNumber", "?")
            name = payload.get("channelName", "Unknown")
            print(f"📺 Channel: {num} - {name}")

    async def power_handler(success, payload):
        if success:
            state = payload.get("state", "unknown")
            print(f"⚡ Power: {state}")

    async def audio_output_handler(success, audio_source):
        if success:
            print(f"🎵 Audio Output: {audio_source.data}")

    async def sound_output_handler(success, payload):
        if success:
            output = payload.get("soundOutput", "unknown")
            print(f"🎧 Sound Output: {output}")

    # Subscribe to all events
    await media.subscribe_get_volume(volume_handler)
    await media.subscribe_get_audio_output(audio_output_handler)
    await media.subscribe_get_sound_output(sound_output_handler)
    await tv.subscribe_get_current_channel(channel_handler)
    await system.subscribe_power_state(power_handler)

    print("🎯 Monitoring all TV events... (Press Ctrl+C to stop)")

    try:
        # Monitor for 60 seconds
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")

    # Clean up all subscriptions
    await media.unsubscribe_get_volume()
    await media.unsubscribe_get_audio_output()
    await media.unsubscribe_get_sound_output()
    await tv.unsubscribe_get_current_channel()
    await system.unsubscribe_power_state()

    # Close connection
    await client.close()
    print("✅ Cleanup complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Error Handling

### Common Error Scenarios

#### 1. Double Subscription

```python
await media.subscribe_get_volume(callback)
await media.subscribe_get_volume(callback)  # ❌ Raises ValueError
```

**Error:** `ValueError: Already subscribed.`

#### 2. Unsubscribe Without Subscription

```python
await media.unsubscribe_get_volume()  # ❌ Raises ValueError (if not subscribed)
```

**Error:** `ValueError: Not subscribed.`

#### 3. Invalid Subscription

```python
await media.subscribe_get_mute(callback)  # ❌ get_mute doesn't support subscription
```

**Error:** `AttributeError: Subscription not found or allowed.`

#### 4. Connection Lost

When the WebSocket connection is lost, all subscriptions are automatically cleaned up. Apps must re-subscribe after reconnection.

### Error Handling Best Practices

```python
async def robust_subscription_setup():
    try:
        await media.subscribe_get_volume(volume_handler)
        print("✅ Volume subscription active")
    except ValueError as e:
        if "Already subscribed" in str(e):
            print("⚠️ Already subscribed to volume events")
        else:
            print(f"❌ Subscription error: {e}")
    except AttributeError as e:
        print(f"❌ Invalid subscription: {e}")

async def robust_cleanup():
    try:
        await media.unsubscribe_get_volume()
        print("✅ Volume subscription cleaned up")
    except ValueError:
        print("⚠️ Volume subscription was not active")
```

---

## Testing & Debugging

### Test Subscription Setup

```python
# Check if subscription is active
if "get_volume" in media.subscriptions:
    print("✅ Volume subscription is active")

# Check subscription count
print(f"Active subscriptions: {len(media.subscriptions)}")

# List all active subscriptions
for name, uuid in media.subscriptions.items():
    print(f"  {name}: {uuid}")
```

### Debug Event Callbacks

```python
async def debug_volume_handler(success, payload):
    print(f"DEBUG - Volume callback:")
    print(f"  Success: {success}")
    print(f"  Payload: {payload}")
    print(f"  Payload type: {type(payload)}")

    if success:
        # Process normally
        volume = payload.get("volume", 0)
        print(f"  Extracted volume: {volume}")
```

---

## WebOS TV Compatibility

### Supported WebOS Versions

- **WebOS 3.0+** - All subscriptions supported
- **WebOS 2.x** - Limited subscription support
- **WebOS 1.x** - Subscription functionality unavailable

### TV Model Considerations

#### Volume Subscription

- ✅ **All models** - Universal support
- 🎯 **Update frequency** - Immediate on volume changes

#### Audio Output Subscription

- ✅ **Most models** - Wide support
- ⚠️ **Older models** - May not report Bluetooth devices

#### Channel Subscription

- ✅ **Cable/Antenna models** - Full support
- ⚠️ **Streaming-only models** - Limited channel data

#### Power State Subscription

- ✅ **Newer models (2018+)** - Full support
- ⚠️ **Older models** - May miss some state transitions

---

## Performance Notes

### Memory Usage

- Each subscription uses ~1KB memory overhead
- Callback payloads are typically 100-500 bytes
- No persistent storage required

### Network Impact

- Subscription setup: 1 WebSocket message
- Event notifications: Real-time, minimal overhead
- Unsubscribe: 1 WebSocket message

### CPU Impact

- Event processing: <1ms per event
- JSON parsing: Negligible overhead
- Callback execution: Depends on application logic

### Best Practices

- ✅ **Do:** Use specific subscriptions for your needs
- ✅ **Do:** Clean up subscriptions before app exit
- ✅ **Do:** Handle callback errors gracefully
- ❌ **Don't:** Subscribe to unused events
- ❌ **Don't:** Perform heavy processing in callbacks
- ❌ **Don't:** Block in callback functions

---

## Migration Guide

### From Polling to Subscriptions

**Before (Polling):**

```python
# ❌ Inefficient polling approach
while True:
    volume = await media.get_volume()
    if volume != last_volume:
        print(f"Volume changed: {volume}")
        last_volume = volume
    await asyncio.sleep(1)  # Poll every second
```

**After (Subscription):**

```python
# ✅ Efficient event-driven approach
async def volume_handler(success, payload):
    if success:
        print(f"Volume changed: {payload.get('volume')}")

await media.subscribe_get_volume(volume_handler)
# Events arrive immediately when changes occur
```

### Benefits of Migration

- **🚀 Real-time updates** - No polling delay
- **⚡ Reduced CPU usage** - No continuous polling
- **📡 Lower network traffic** - Events only when changes occur
- **🔋 Better battery life** - Less frequent wake-ups

---

## Summary

AsyncWebOSTV provides **5 comprehensive subscriptions** for real-time TV monitoring:

| Subscription          | Control       | Purpose               | Added     |
| --------------------- | ------------- | --------------------- | --------- |
| `get_volume`          | MediaControl  | Volume/mute changes   | v0.1.1 ✨ |
| `get_audio_output`    | MediaControl  | Audio device changes  | v0.1.0    |
| `get_sound_output`    | MediaControl  | Sound routing changes | v0.1.0    |
| `get_current_channel` | TvControl     | Channel changes       | v0.1.0    |
| `power_state`         | SystemControl | Power state changes   | v0.1.1 ✨ |

All subscriptions follow the **same consistent API pattern** with:

- ✅ **Dynamic method generation** via `__getattr__`
- ✅ **Standardized callback signatures**
- ✅ **Robust error handling**
- ✅ **Automatic cleanup**
- ✅ **Real-time event delivery**

This makes AsyncWebOSTV ideal for building responsive, real-time TV control applications! 🎯
