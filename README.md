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
from asyncwebostv import WebOSClient

async def main():
    # Discover TV on the network
    client = await WebOSClient.discover()
    
    # Connect to TV
    await client.connect()
    
    # Control TV
    await client.media_control.pause()
    await client.system_control.power_off()
    
    # Close connection
    await client.disconnect()

asyncio.run(main())
```

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