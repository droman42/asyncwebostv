# Integration Tests for AsyncWebOSTV

This directory contains integration tests that require actual WebOS TV connections to run. These tests are separate from unit tests and are used to verify end-to-end functionality with real hardware.

## ⚠️ **Prerequisites**

Before running integration tests, you need:

1. **A WebOS TV** on the same network
2. **TV IP address** or discoverable TV
3. **Client key** (obtained through pairing process)
4. **TV powered on** and accessible

## Integration Test Files

### Core Integration Tests

- **`permissions_test.py`** - Tests system permissions and TV registration
- **`notification_test.py`** - Tests notification functionality with real TV
- **`get_client_key.py`** - Utility to obtain and save client keys for testing

### Input and Control Tests

- **`test_input_websocket.py`** - Tests input control via WebSocket connection
- **`compare_input_methods.py`** - Compares different input methods performance
- **`subscription_example.py`** - Tests subscription functionality with real events

## Running Integration Tests

### Setup

1. **Configure TV settings:**

   ```bash
   # Set your TV's IP address
   export WEBOS_TV_IP="192.168.1.100"

   # Or let discovery find it automatically
   ```

2. **Get client key (first time only):**
   ```bash
   python tests/integration/get_client_key.py
   ```
   Follow the on-screen prompts to pair with your TV.

### Running Tests

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run specific integration test
python tests/integration/permissions_test.py

# Run with TV IP specified
WEBOS_TV_IP=192.168.1.100 python tests/integration/notification_test.py
```

### Manual Execution

Most integration tests can be run directly:

```bash
# Test notifications
python tests/integration/notification_test.py

# Test input methods
python tests/integration/test_input_websocket.py

# Compare input performance
python tests/integration/compare_input_methods.py

# Test subscriptions
python tests/integration/subscription_example.py
```

## Test Descriptions

### `permissions_test.py`

- Tests TV pairing and registration process
- Verifies system permissions and access levels
- Tests various system commands requiring permissions

### `notification_test.py`

- Tests toast notification creation
- Verifies notification display on TV screen
- Tests different notification types and parameters

### `test_input_websocket.py`

- Tests remote control input functionality
- Verifies button presses, navigation, and text input
- Tests both individual commands and sequences

### `compare_input_methods.py`

- Performance comparison between different input methods
- Latency measurements for various input types
- Stress testing with rapid input sequences

### `subscription_example.py`

- Tests real-time event subscriptions
- Verifies volume change notifications
- Tests subscription lifecycle management

### `get_client_key.py`

- Utility for obtaining TV pairing keys
- Interactive pairing process
- Saves client keys for reuse in other tests

## Configuration

### Environment Variables

- `WEBOS_TV_IP` - Target TV IP address
- `WEBOS_CLIENT_KEY` - Stored client key (from pairing)
- `WEBOS_TIMEOUT` - Connection timeout (default: 60 seconds)

### TV Requirements

- **WebOS version:** 3.0+ (older versions may have limited functionality)
- **Network:** TV and test machine on same network
- **Developer mode:** Not required for basic tests
- **Apps:** No special apps need to be installed

## Expected Behavior

### Successful Test Run

- TV responds to commands
- Notifications appear on screen
- Input commands control TV interface
- Subscriptions receive real events

### Common Issues

1. **Connection timeout:**

   - Verify TV IP address
   - Check network connectivity
   - Ensure TV is powered on

2. **Permission denied:**

   - Re-run pairing process
   - Check client key validity
   - Verify TV allows external connections

3. **Command failures:**
   - Some commands may not work on all TV models
   - Check WebOS version compatibility
   - Verify TV state (e.g., app context)

## Integration vs Unit Tests

| Aspect           | Unit Tests               | Integration Tests             |
| ---------------- | ------------------------ | ----------------------------- |
| **Purpose**      | Test isolated components | Test end-to-end functionality |
| **Dependencies** | Mocked/stubbed           | Real TV hardware              |
| **Speed**        | Fast (milliseconds)      | Slower (seconds)              |
| **Reliability**  | Always consistent        | May vary by TV state          |
| **Coverage**     | Code paths               | User workflows                |
| **When to run**  | Every commit/PR          | Before releases               |

## Best Practices

1. **Test Environment:**

   - Use dedicated test TV when possible
   - Document TV model and WebOS version
   - Reset TV state between tests if needed

2. **Test Data:**

   - Use non-intrusive test notifications
   - Avoid changing critical TV settings
   - Clean up test data after runs

3. **Error Handling:**

   - Expect occasional network issues
   - Implement retry logic for flaky operations
   - Log detailed error information

4. **Timing:**
   - Allow sufficient time for TV responses
   - Account for TV boot/wake time
   - Consider TV performance variations

## Contributing

When adding new integration tests:

1. **Document requirements** - What TV features are needed
2. **Add error handling** - Network and TV state issues
3. **Make it non-destructive** - Don't change user settings
4. **Include cleanup** - Reset state after test
5. **Update this README** - Document new test purpose

## Troubleshooting

### Debug Mode

```bash
# Enable verbose logging
export WEBOS_DEBUG=1
python tests/integration/your_test.py
```

### Manual TV Testing

```bash
# Test basic connectivity
python -c "
import asyncio
from asyncwebostv import WebOSTV

async def test():
    tv = WebOSTV('YOUR_TV_IP')
    await tv.connect()
    info = await tv.system.info()
    print(f'Connected to: {info[\"product_name\"]}')
    await tv.close()

asyncio.run(test())
"
```

The integration tests provide confidence that the library works correctly with real WebOS TVs across different models and firmware versions.
