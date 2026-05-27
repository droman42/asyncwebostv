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
    "volume": 25,           # Current volume level (0-100)
    "muted": false,         # Whether audio is muted
    "soundOutput": "tv_speaker",  # Active sound output (added v0.3.1)
    "returnValue": true     # Success indicator
}
```

> **Note (v0.3.1+):** webOS 4.x+ firmware actually delivers this event with
> the real fields wrapped inside a `volumeStatus` sub-dict and renames
> `muted` to `muteStatus`. The library normalises that to the flat shape
> shown above so consumers can always read `payload["volume"]` and
> `payload["muted"]` regardless of firmware version. See the v0.3.1
> changelog for the gory details.

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
**URI:** `ssap://com.webos.service.tvpower/power/getPowerState`
**Added:** v0.1.1 ✨ (switched from `com.webos.service.power` to `com.webos.service.tvpower` in v0.3.1 — see note below)

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

The following `state` values have been observed in production deployments
(values sourced from [aiowebostv](https://github.com/home-assistant-libs/aiowebostv)
and [aiopylgtv issue #56](https://github.com/bendavid/aiopylgtv/issues/56)):

- `"Active"` — TV is on and fully operational
- `"Screen Off"` — Display off, system still running and responsive
- `"Screen Saver"` — Screensaver currently active (TV still on)
- `"Active Standby"` — Standby with network on (treat as **off** for power-on/off semantics)
- `"Suspend"` — Suspended/sleeping (treat as **off**)
- `"Power Off"` — Fully powered off
- `None` / missing — Older webOS firmware that does not implement the
  power-state endpoint at all (fall back to "is a current app running?" check)

**Practical "is the TV on?" heuristic** (matches aiowebostv's logic):

```python
def is_tv_on(state: str | None) -> bool:
    return state not in (None, "Power Off", "Suspend", "Active Standby")
```

`"Screen Off"` and `"Screen Saver"` are considered "TV on, screen off" —
the TV continues to accept commands.

#### History note — URI moved in v0.3.1

Versions ≤ v0.3.0 targeted the older `ssap://com.webos.service.power/power/getPowerState`
URI (inherited from `pywebostv`). That endpoint is dead on webOS 4.x+
firmware — the subscribe call is accepted, the TV immediately replies
`"Unknown error"`, and no events ever fire. Hardware-verified on a
2021 LG OLED (webOS 6.x) on 2026-05-27.

v0.3.1+ targets `ssap://com.webos.service.tvpower/...` (matches
`aiowebostv`), which works on every TV from 2018 onward. If you maintain
a pre-2018 deployment and need the legacy URI, override `SystemControl.COMMANDS["power_state"]["uri"]`
at runtime.

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

### 6. Foreground App Subscription 📱

**Control Class:** `ApplicationControl`
**Methods:** `subscribe_get_current()` / `unsubscribe_get_current()`
**URI:** `ssap://com.webos.applicationManager/getForegroundAppInfo`
**Added:** v0.1.2 ✨

Monitor changes to the currently focused application (Live TV, Netflix,
YouTube, an HDMI input, etc.). Event fires whenever the user launches a new
app or switches inputs via the remote.

#### Callback Payload

The callback receives an `Application` object wrapping the raw payload:

```python
{
    "appId": "com.webos.app.hdmi1",  # Application identifier
    "windowId": "",
    "processId": "...",
    "returnValue": true
}
```

#### Usage Example

```python
async def foreground_app_handler(success, app):
    if success:
        # `app` is an Application model wrapping the payload
        app_id = app.data.get("appId", "unknown")
        print(f"Foreground app: {app_id}")
    else:
        print(f"Foreground app subscription error: {app}")

apps = ApplicationControl(client)
await apps.subscribe_get_current(foreground_app_handler)
```

#### Trigger Events

- User selects an app from the launcher
- User switches HDMI input
- App launches via `launch()` / `launch_with_monitoring()`
- App exits / TV returns to Home

---

## Current External Input (one-shot query)

This is not a subscription — it's a one-shot request — but it's documented
here because it's closely related to the foreground-app subscription above.

### Why there's no dedicated "current input" subscription

Per an LG webOS developer on LG's own forum
([thread](https://forum.webostv.developer.lge.com/t/get-set-current-source-in-lg-webos-tv-programatically-api/16338)):

> *"Currently, no APIs for getting TV input information are provided."*

webOS exposes the *list* of available inputs
(`ssap://tv/getExternalInputList`) and an *input-switch* command
(`ssap://tv/switchInput`), but **no documented endpoint that returns the
currently active external input**. The unofficial
`ssap://tv/getCurrentExternalInput` endpoint exists on some firmware but
its response is silent on current webOS (HW-verified on webOS 6.x).

### How the library reports current input (v0.3.2+)

`InputControl.get_input()` derives the current input from the foreground
app id. webOS surfaces external-input apps as synthetic launcher apps with
ids of the form `com.webos.app.hdmi<N>`. When the foreground is one of
these, the TV is rendering HDMI port N; when it's anything else (launcher,
Live TV, installed app), no external input is active.

```python
# Returned when foreground is com.webos.app.hdmi2:
{
    "appId":       "com.webos.app.hdmi2",
    "inputId":     "HDMI_2",      # synthesised by the library
    "windowId":    "",
    "processId":   "1234",
    "returnValue": True,
}

# Returned when foreground is the launcher (no external input active):
{
    "appId":       "com.webos.app.home",
    "windowId":    "",
    "processId":   "5678",
    "returnValue": True,
    # NOTE: no `inputId` key — there is no active external input to report.
}
```

This matches the model that [`aiowebostv`](https://github.com/home-assistant-libs/aiowebostv)
(the Home Assistant LG webOS integration) uses internally: its
`get_input()` is literally `return await self.get_current_app()` — same
single source of truth.

### Helper for derivation in callbacks

If you already subscribe to foreground-app changes (section #6 above) and
want to keep a single derivation site for both `current_app` and the
"current input" semantic, import the public helper:

```python
from asyncwebostv import app_id_to_input_id

async def on_foreground_app_change(success, payload):
    if not success:
        return
    app_id = payload.get("appId")
    input_id = app_id_to_input_id(app_id)  # "HDMI_2" or None
    # ... use input_id ...
```

`app_id_to_input_id(app_id)` returns `"HDMI_<N>"` for HDMI viewer apps,
`None` for everything else. It's the same parser `get_input()` uses
internally — there's no need to re-implement the regex.

### Last-remembered HDMI: not exposed

webOS provides no API for "last selected external input" — its model has
no concept of one. If your application needs that semantic (e.g. "which
HDMI was selected before the user opened the launcher"), track it
locally: remember the last `com.webos.app.hdmi<N>` your foreground-app
subscription saw before an internal-app foreground took over.

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

When the WebSocket connection is dropped via `await client.close()`, the
client-side subscription bookkeeping (`waiters` and `subscribers` on
`WebOSClient`) is cleared so nothing stale leaks into a reconnect. **However,
the per-control `subscriptions` dict on each `*Control` instance is NOT
cleared by `close()`.** Re-using the same control object after a reconnect
will raise `ValueError("Already subscribed.")` on the next `subscribe_*()`
call.

**Reconnect contract:** consumers are responsible for re-subscribing after a
reconnect. The recommended pattern is to **discard the old control objects
and create fresh ones** against the new client:

```python
await client.close()
# ... reconnect ...
await client.connect()

# Don't reuse the previous MediaControl / TvControl / SystemControl objects.
media = MediaControl(client)
tv = TvControl(client)
system = SystemControl(client)

# Now subscribe_* calls work cleanly.
await media.subscribe_get_volume(volume_handler)
```

Connection drops that originate from the TV side (network loss, TV powered
off) close the underlying websocket; the message-handling task ends and the
same rule applies — re-create controls before re-subscribing.

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

AsyncWebOSTV provides **6 comprehensive subscriptions** for real-time TV monitoring:

| Subscription          | Control            | Purpose                       | Added     |
| --------------------- | ------------------ | ----------------------------- | --------- |
| `get_volume`          | MediaControl       | Volume/mute changes           | v0.1.1 ✨ |
| `get_audio_output`    | MediaControl       | Audio device changes          | v0.1.0    |
| `get_sound_output`    | MediaControl       | Sound routing changes         | v0.1.0    |
| `get_current_channel` | TvControl          | Channel changes               | v0.1.0    |
| `get_current`         | ApplicationControl | Foreground app changes        | v0.1.2 ✨ |
| `power_state`         | SystemControl      | Power state changes           | v0.1.1 ✨ |

All subscriptions follow the **same consistent API pattern** with:

- ✅ **Dynamic method generation** via `__getattr__`
- ✅ **Standardized callback signatures**
- ✅ **Robust error handling**
- ✅ **Automatic cleanup**
- ✅ **Real-time event delivery**

This makes AsyncWebOSTV ideal for building responsive, real-time TV control applications! 🎯
