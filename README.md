# AsyncWebOSTV

An asynchronous Python library for controlling LG WebOS TVs. This is an async port of the popular `pywebostv` library.

## Features

- Asynchronous API for controlling LG WebOS TVs
- WebSocket-based communication
- Support for all major TV controls (media, system, input, applications, TV channels, sources, etc.)
- **Real-time event subscriptions** (volume, channel, foreground app, power state, audio output)
- SSDP-based network device discovery
- **Secure SSL/TLS connections with certificate handling**
- Modern Python async/await syntax
- Type hints for better IDE support
- Comprehensive test coverage

## Requirements

- Python 3.11+
- aiohttp>=3.8.0
- websockets>=15.0.1

## Installation

```bash
pip install asyncwebostv
```

## Quick Start

```python
import asyncio
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl, SystemControl, ApplicationControl, TvControl, InputControl, SourceControl
)

async def main():
    # Create a WebOS client
    client = WebOSClient("192.168.1.100")  # Replace with your TV's IP

    # Connect to TV
    await client.connect()

    # Register with the TV (if needed)
    store = {}  # Dictionary to receive the client key
    async for status in client.register(store):
        if status == WebOSClient.PROMPTED:
            print("Please accept the connection on your TV")
        elif status == WebOSClient.REGISTERED:
            print(f"Registration successful, client key: {store.get('client_key')}")

    # Use the client key for future sessions to avoid re-pairing
    # client_key = store.get("client_key")

    # Create control interfaces
    media = MediaControl(client)
    system = SystemControl(client)

    # Control TV
    await media.volume_up()
    await system.notify("Hello from AsyncWebOSTV!")

    # Close connection
    await client.close()

asyncio.run(main())
```

## Subscriptions

AsyncWebOSTV supports real-time event subscriptions so you don't have to poll
the TV. Six subscriptions are available: `get_volume`, `get_audio_output`,
`get_sound_output`, `get_current_channel`, `get_current` (foreground app),
and `power_state`.

```python
import asyncio
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, SystemControl

async def main():
    client = WebOSClient("192.168.1.100", client_key="your-client-key")
    await client.connect()

    media = MediaControl(client)
    system = SystemControl(client)

    async def on_volume(success, payload):
        if success:
            print(f"Volume: {payload.get('volume')} muted={payload.get('muted')}")

    async def on_power(success, payload):
        if success:
            print(f"Power state: {payload.get('state')}")

    await media.subscribe_get_volume(on_volume)
    await system.subscribe_power_state(on_power)

    try:
        await asyncio.sleep(60)  # receive events for a minute
    finally:
        await media.unsubscribe_get_volume()
        await system.unsubscribe_power_state()
        await client.close()

asyncio.run(main())
```

> **Reconnect note:** after `await client.close()`, discard your control
> objects (`MediaControl`, `SystemControl`, etc.) and create fresh ones
> against the new client before resubscribing. See the [subscription spec](docs/subscription_spec.md#4-connection-lost)
> for the full reconnect contract and the complete list of event payloads.

## Secure Connections

AsyncWebOSTV supports secure SSL/TLS connections to WebOS TVs. The library provides two classes for secure connections:

### SecureWebOSClient

Low-level secure client with enhanced SSL certificate handling:

```python
import asyncio
from asyncwebostv import SecureWebOSClient, extract_certificate

async def main():
    # Extract and save certificate from TV
    cert_file = "tv_cert.pem"
    await extract_certificate("192.168.1.100", 3001, cert_file)

    # Create secure client with certificate verification
    client = SecureWebOSClient(
        host="192.168.1.100",
        port=3001,
        secure=True,
        cert_file=cert_file,
        verify_ssl=True,
        client_key="your-client-key"  # Optional
    )

    # Connect and use as normal
    await client.connect()

    # Close connection
    await client.close()

asyncio.run(main())
```

### SecureWebOSTV

High-level secure client with SSL certificate handling:

```python
import asyncio
from asyncwebostv import SecureWebOSTV

async def main():
    # Create secure TV client
    tv = SecureWebOSTV(
        host="192.168.1.100",
        port=3001,
        cert_file="tv_cert.pem",  # Optional
        verify_ssl=True           # Set to False to skip verification
    )

    # Extract and save certificate
    # await tv.get_certificate("tv_cert.pem")

    # Connect and register if needed
    await tv.connect()
    if not tv.client_key:
        client_key = await tv.register()

    # Now use the client property to access lower-level API
    client = tv.client

    # Close connection
    await tv.close()

asyncio.run(main())
```

### Certificate Utilities

The library includes utility functions for working with TV certificates:

```python
from asyncwebostv import extract_certificate, verify_certificate

# Extract certificate from TV
cert_pem = await extract_certificate("192.168.1.100", 3001, "tv_cert.pem")

# Verify if a saved certificate matches the current one on the TV
matches = await verify_certificate("tv_cert.pem", "192.168.1.100", 3001)
```

## Client Key Management

Unlike some other libraries, AsyncWebOSTV does not save client keys to disk by default.
Instead, it returns the client key to the caller through a provided dictionary.

```python
# During registration
store = {}
async for status in client.register(store):
    pass

# After registration, the client key is in the store dictionary
client_key = store.get("client_key")
print(f"Your client key: {client_key}")

# Save it however you want (database, config file, etc.)
```

For subsequent connections, you can provide the client key directly:

```python
client = WebOSClient("192.168.1.100", client_key="your-client-key")
```

This approach gives you more control over how client keys are stored and managed in your application.

## Documentation

Detailed documentation lives in the [`docs/`](docs/) directory:

- [Subscription API](docs/subscription_spec.md) — real-time events (volume, channel, power state, foreground app, audio output) with payloads, callback contracts, and reconnect rules
- [SSL / Secure Connections](docs/SSL_spec.md) — certificate handling and secure-mode design
- [Async Migration Spec](docs/async_migration_spec.md) — the `pywebostv` → `asyncwebostv` port

## Development

1. Clone the repository:

```bash
git clone https://github.com/droman42/asyncwebostv.git
cd asyncwebostv
```

2. Install development dependencies:

```bash
pip install -e ".[dev]"
```

3. Run tests:

```bash
pytest
```

4. Format code:

```bash
black .
isort .
```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Original `pywebostv` library for inspiration
- LG for their WebOS platform
