# Advanced Subscriptions Roadmap

This document outlines the strategic plan for expanding AsyncWebOSTV's subscription capabilities based on research into webOS Luna Service (LS2) subscription ecosystem.

## Executive Summary

**Current State**: AsyncWebOSTV implements 5 carefully curated subscriptions covering basic media and power functions.

**Opportunity**: webOS supports subscription (`{"subscribe": true}`) on virtually every Luna Service method, enabling real-time monitoring of apps, network, settings, hardware, and system state.

**Vision**: Transform AsyncWebOSTV from a "basic TV control library" into a **comprehensive webOS system monitoring and automation platform**.

## Research Findings

### The webOS Subscription Principle

> **"Any Luna-service (LS2) method that documents a `subscribe: true` argument will push a JSON update every time its underlying value changes."**

This means AsyncWebOSTV can tap into **dozens of additional event sources** across the entire webOS ecosystem.

### Current Implementation Assessment

**Strengths** ✅:

- Robust subscription framework with UUID tracking
- Dynamic method generation via `__getattr__`
- Standardized callback pattern with error handling
- Well-documented API with typed return objects

**Limitations** ⚠️:

- Only 5 subscriptions implemented out of 30+ available
- Missing high-impact areas: apps, network, settings, hardware
- No coverage of system-wide events

## Gap Analysis

### High-Impact Missing Subscriptions

| **Category**           | **Current** | **Available**                       | **Business Impact** | **Technical Complexity** |
| ---------------------- | ----------- | ----------------------------------- | ------------------- | ------------------------ |
| **App Management**     | ❌ None     | ✅ Foreground changes, lifecycle    | **🔴 CRITICAL**     | 🟡 Medium                |
| **Network Monitoring** | ❌ None     | ✅ Connection status, Wi-Fi quality | **🔴 HIGH**         | 🟢 Low                   |
| **System Settings**    | ❌ None     | ✅ ALL settings subscribable        | **🔴 HIGH**         | 🟡 Medium                |
| **Hardware Events**    | ❌ None     | ✅ USB, Bluetooth, input changes    | **🟡 MEDIUM**       | 🟢 Low                   |
| **AV Pipeline**        | 🟡 Basic    | ✅ Video output, HDMI, full audio   | **🟡 MEDIUM**       | 🟡 Medium                |

### Use Case Impact Examples

#### 1. **Foreground App Subscription** 🎯

```python
# Instead of polling every 2 seconds:
while True:
    current = await app.get_current()
    await asyncio.sleep(2)

# Real-time app change detection:
async def app_changed(success, payload):
    if payload.get("appId") == "netflix":
        await home_automation.dim_lights()
        await music_player.pause()

await app.subscribe_get_foreground_app_info(app_changed)
```

#### 2. **Network Status Subscription** 🌐

```python
async def network_changed(success, payload):
    if not payload.get("isInternetConnectionAvailable"):
        await video_player.reduce_quality()
        await app_store.pause_downloads()
    elif payload.get("wifi", {}).get("signalStrength", 0) < 30:
        await video_player.switch_to_5ghz()

await network.subscribe_get_status(network_changed)
```

#### 3. **System Settings Subscription** ⚙️

```python
async def settings_changed(success, payload):
    if "picture" in payload:
        await dashboard.update_brightness_slider(payload["picture"]["brightness"])
    if "energySaving" in payload:
        await smart_home.adjust_for_energy_mode(payload["energySaving"])

await settings.subscribe_get_system_settings(settings_changed)
```

## Strategic Implementation Plan

### Phase 1: Foundation Enhancement (v0.2.0)

#### 1.1 Core Infrastructure

- [ ] **Generic Subscription Support**

  ```python
  # Allow direct LS2 subscription for power users
  await client.subscribe_raw("luna://service/method", callback, {"subscribe": True})
  ```

- [ ] **Subscription Categories Architecture**
  ```python
  class NetworkControl(WebOSControlBase):    # New
  class SettingsControl(WebOSControlBase):   # New
  class HardwareControl(WebOSControlBase):   # New
  class AppLifecycleControl(WebOSControlBase): # Extend ApplicationControl
  ```

#### 1.2 High-Impact Subscriptions

- [ ] **App Foreground Changes** (`getForegroundAppInfo`)
- [ ] **Network Connection Status** (`connectionmanager/getStatus`)
- [ ] **App Lifecycle Events** (`getAppLifeStatus`)

### Phase 2: System Integration (v0.3.0)

#### 2.1 Settings & Preferences

- [ ] **System Settings Monitoring** (`settings/getSystemSettings`)

  - Picture settings (brightness, contrast, color)
  - Audio settings (equalizer, sound mode)
  - Energy saving modes
  - Accessibility settings

- [ ] **System Preferences** (`systemservice/getPreferences`)
  - Locale and language changes
  - Time zone updates
  - Wallpaper changes

#### 2.2 Hardware & Device Monitoring

- [ ] **USB Device Events** (`pdm/getAttachedNonStorageDevices`)
- [ ] **Bluetooth Status** (`bluetooth2/adapter/getStatus`, `device/getStatus`)
- [ ] **Input Source Changes** (`tv/getCurrentExternalInput`)

### Phase 3: Advanced Features (v0.4.0)

#### 3.1 AV Pipeline Monitoring

- [ ] **Video Output Status** (`videooutput/getStatus`)

  - HDMI port status
  - HDR engagement
  - Resolution changes

- [ ] **Enhanced Audio Routing** (`audio/getStatus`)
  - ARC/eARC status
  - Audio format information
  - Speaker configuration

#### 3.2 System Performance

- [ ] **Memory Pressure** (`memorymanager/getInfo`)
- [ ] **Activity Manager** (`activitymanager/*`)
- [ ] **CEC Traffic** (`cec/sendCommand`)

#### 3.3 Advanced Features

- [ ] **Notification Events** (`notification/*`)
- [ ] **Wi-Fi Scanning** (`wifi/getStatus`)

## Technical Implementation Details

### Subscription Definition Pattern

```python
class NetworkControl(WebOSControlBase):
    """Control for network monitoring and management."""

    COMMANDS = {
        "get_connection_status": {
            "uri": "ssap://com.webos.service.connectionmanager/getStatus",
            "validation": standard_validation,
            "subscription": True,
            "return": lambda p: NetworkStatus(p)  # Typed wrapper
        },
        "get_wifi_status": {
            "uri": "ssap://com.webos.service.wifi/getStatus",
            "validation": standard_validation,
            "subscription": True,
            "return": lambda p: WiFiStatus(p)
        }
    }
```

### Enhanced ApplicationControl

```python
class ApplicationControl(WebOSControlBase):
    # ... existing commands ...

    COMMANDS = {
        # ... existing ...
        "get_foreground_app_info": {
            "uri": "ssap://com.webos.applicationManager/getForegroundAppInfo",
            "validation": standard_validation,
            "subscription": True,
            "return": lambda p: Application(p)
        },
        "get_app_life_status": {
            "uri": "ssap://com.webos.applicationManager/getAppLifeStatus",
            "validation": standard_validation,
            "subscription": True,
        }
    }
```

### Generic Raw Subscription Support

```python
class WebOSClient:
    async def subscribe_raw(self, uri: str, callback: Callable, payload: Dict = None):
        """Subscribe to any LS2 service directly.

        Args:
            uri: Full Luna service URI (luna://service/method)
            callback: Async callback function
            payload: Optional subscription payload

        Returns:
            Subscription UUID for unsubscribing
        """
        if not uri.startswith("luna://"):
            uri = f"ssap://{uri.replace('luna://', '')}"

        uid = str(uuid4())
        await self.subscribe(uri, uid, callback, payload or {"subscribe": True})
        return uid
```

## Data Models & Type Safety

### Network Status Models

```python
@dataclass
class NetworkStatus:
    is_connected: bool
    internet_available: bool
    wifi_info: Optional[WiFiInfo]
    ethernet_info: Optional[EthernetInfo]

@dataclass
class WiFiInfo:
    ssid: str
    signal_strength: int
    frequency: str  # "2.4GHz" or "5GHz"
    security: str
```

### Settings Models

```python
@dataclass
class PictureSettings:
    brightness: int
    contrast: int
    color: int
    energy_saving: bool

@dataclass
class AudioSettings:
    sound_mode: str
    bass: int
    treble: int
    balance: int
```

## Testing Strategy

### Unit Tests

- [ ] Subscription framework tests for new control classes
- [ ] Data model validation tests
- [ ] Callback error handling tests

### Integration Tests

- [ ] Real TV subscription lifecycle tests
- [ ] Network change simulation tests
- [ ] App switching detection tests
- [ ] Settings change monitoring tests

### Performance Tests

- [ ] Memory usage with 20+ active subscriptions
- [ ] Event throughput testing
- [ ] Subscription cleanup verification

## Documentation Plan

### User Documentation

- [ ] **Advanced Subscriptions Guide** - Complete reference
- [ ] **Use Case Examples** - Real-world automation scenarios
- [ ] **Migration Guide** - From polling to event-driven patterns
- [ ] **Performance Best Practices** - Subscription management

### Developer Documentation

- [ ] **Subscription Architecture** - Internal framework details
- [ ] **Adding New Subscriptions** - Development guide
- [ ] **Luna Service Reference** - Available LS2 endpoints

## Success Metrics

### v0.2.0 Targets

- [ ] 3 new high-impact subscriptions implemented
- [ ] Generic raw subscription support
- [ ] Zero breaking changes to existing API
- [ ] 95% test coverage for new functionality

### v0.3.0 Targets

- [ ] 10+ total subscriptions covering major system areas
- [ ] Comprehensive settings monitoring
- [ ] Hardware event detection
- [ ] Performance benchmarks established

### v0.4.0 Targets

- [ ] 20+ total subscriptions
- [ ] Complete AV pipeline monitoring
- [ ] Advanced system integration features
- [ ] Production-ready for automation platforms

## Risk Mitigation

### Technical Risks

- **Subscription Overload**: Implement subscription limits and monitoring
- **Memory Leaks**: Robust cleanup and testing procedures
- **TV Compatibility**: Graceful degradation for older webOS versions

### API Stability Risks

- **Luna Service Changes**: Version detection and fallback mechanisms
- **Breaking Changes**: Maintain existing API surface, extend only

### Performance Risks

- **Event Flooding**: Rate limiting and event batching
- **CPU Usage**: Efficient callback handling and background processing

## Conclusion

This roadmap transforms AsyncWebOSTV from a basic control library into a comprehensive webOS automation platform. By leveraging the full Luna Service subscription ecosystem, we can provide developers with real-time access to every aspect of the TV's state and behavior.

**The opportunity is massive** - webOS is designed to be event-driven, but most libraries only scratch the surface. AsyncWebOSTV can become the definitive library for webOS automation and integration.

**Next Steps**:

1. Review and approve this roadmap
2. Begin Phase 1 implementation with NetworkControl
3. Establish testing infrastructure for subscription lifecycle
4. Create proof-of-concept automation examples

---

_This document serves as the strategic blueprint for AsyncWebOSTV's evolution into a comprehensive webOS monitoring and automation platform._
