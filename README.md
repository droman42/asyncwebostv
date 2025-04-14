# AsyncWebOSTV

An asynchronous Python library for controlling LG WebOS TVs. This is an async port of the popular `pywebostv` library.

## Features

- Asynchronous API for controlling LG WebOS TVs
- WebSocket-based communication
- Support for all major TV controls (media, system, input, etc.)
- Modern Python async/await syntax
- Type hints for better IDE support
- Comprehensive test coverage

## Installation

```bash
pip install asyncwebostv
```

## Quick Start

```python
import asyncio
from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import MediaControl, SystemControl

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

For detailed documentation, please visit our [documentation page](https://github.com/yourusername/asyncwebostv/wiki).

## Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/asyncwebostv.git
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