# Unit Tests for AsyncWebOSTV

This directory contains comprehensive unit tests for the AsyncWebOSTV library, providing extensive coverage of all major components.

## Test Structure

### Core Test Files

- **`conftest.py`** - Shared pytest fixtures and mock data
- **`test_connection.py`** - WebOSClient connection functionality
- **`test_model.py`** - Model classes (Application, InputSource, AudioOutputSource)
- **`test_controls_base.py`** - Base control functionality and command execution
- **`test_client.py`** - High-level WebOSTV and SecureWebOSTV clients

### Control-Specific Tests

- **`test_media_control.py`** - Media control functionality (volume, playback)
- **`test_system_control.py`** - System control functionality (power, info, notifications)
- **`test_application_control.py`** - Application control functionality (launch, list, close)

### Discovery Tests

- `test_discovery.py` - TV discovery functionality (proper unit tests)

### Integration Tests

Integration tests that require real TV hardware have been moved to `tests/integration/`:

- `test_input_websocket.py` - Input control integration tests
- `permissions_test.py` - System permissions integration tests
- `notification_test.py` - Notification system integration tests
- `subscription_example.py` - Real-time subscription testing
- `compare_input_methods.py` - Input method performance comparison
- `get_client_key.py` - TV pairing utility

See `tests/integration/README.md` for detailed integration testing guide.

## Test Coverage

### ✅ Comprehensive Unit Test Coverage

1. **Connection Management** (`test_connection.py`)

   - WebSocket connection establishment
   - Registration flow and pairing
   - Message sending and receiving
   - Subscription handling
   - Error handling and timeouts
   - Discovery functionality

2. **Model Classes** (`test_model.py`)

   - Application object initialization and access
   - InputSource object behavior
   - AudioOutputSource handling
   - String representations and error cases

3. **Base Control System** (`test_controls_base.py`)

   - Command execution framework
   - Payload processing with arguments
   - Validation system
   - Subscription/unsubscription
   - Error handling and timeouts

4. **Media Control** (`test_media_control.py`)

   - Volume control (up/down/set/get)
   - Mute functionality
   - Audio status retrieval
   - Playback controls (play/pause/stop/rewind/fast forward)
   - Enhanced monitoring methods

5. **System Control** (`test_system_control.py`)

   - Power management (on/off with monitoring)
   - System information retrieval (including WebOS version detection)
   - Notifications with icon support
   - Settings and launcher functionality

6. **Application Control** (`test_application_control.py`)

   - App listing and status
   - Application launching with parameters
   - Current/foreground app detection
   - App closing functionality
   - Launch monitoring and verification

7. **High-Level Clients** (`test_client.py`)
   - WebOSTV and SecureWebOSTV initialization
   - Async context manager support
   - Discovery methods (sync and async)
   - Connection and registration workflows
   - Error handling and integration

## Test Features

### Mocking Strategy

- **AsyncMock** for async operations
- **MagicMock** for WebSocket connections
- **Patch decorators** for external dependencies
- **Fixture-based** mock data for consistent testing

### Async Testing

- Proper `@pytest.mark.asyncio` usage
- Async context manager testing
- Timeout and error scenario simulation
- Queue-based response handling

### Error Scenarios

- Connection failures
- Timeout handling
- Validation failures
- Registration errors
- Command execution failures

### Edge Cases

- Missing optional parameters
- Invalid command arguments
- Network interruptions
- State change monitoring

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Install the package in development mode
pip install -e .
```

### Running All Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run specific test file
pytest tests/test_model.py -v

# Run with coverage (if sqlite3 available)
pytest tests/ -v --cov=asyncwebostv
```

### Running Individual Test Categories

```bash
# Core functionality
pytest tests/test_connection.py tests/test_model.py tests/test_controls_base.py -v

# Control classes
pytest tests/test_media_control.py tests/test_system_control.py tests/test_application_control.py -v

# High-level clients
pytest tests/test_client.py -v

# Discovery (existing unit tests)
pytest tests/test_discovery.py -v

# Integration tests (requires real TV)
pytest tests/integration/ -v
```

## Mock Data Examples

The test suite includes realistic mock data for:

- System information responses
- Application lists
- Volume and audio status
- Input sources and channels
- Registration sequences
- Error responses

## Test Configuration

### pytest.ini Configuration

```ini
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v"
```

### Fixtures Available

- `mock_websocket` - WebSocket connection mock
- `mock_tv_response` - TV response factory
- `mock_successful_response` - Standard success response
- `mock_error_response` - Standard error response
- `mock_system_info` - System information data
- `mock_volume_info` - Volume status data
- `mock_app_list` - Application list data
- And many more...

## Benefits

1. **Reliability** - Comprehensive test coverage ensures library stability
2. **Development Speed** - Quick feedback on changes and regressions
3. **Documentation** - Tests serve as usage examples
4. **Refactoring Safety** - Safe to modify code with test verification
5. **Bug Prevention** - Edge cases and error scenarios are tested
6. **Integration Confidence** - Client workflows are validated

## Future Enhancements

- Performance benchmarking tests
- Memory usage validation
- Stress testing for concurrent operations
- Protocol compliance verification
- Real hardware integration tests (separate from unit tests)

The test suite provides a solid foundation for maintaining and extending the AsyncWebOSTV library with confidence.
