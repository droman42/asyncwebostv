import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from asyncwebostv.controls import (
    WebOSControlBase, 
    arguments, 
    process_payload, 
    standard_validation
)
from asyncwebostv.connection import WebOSClient


class TestArgumentsFunction:
    """Test cases for the arguments function."""
    
    def test_arguments_with_positional_index(self):
        """Test arguments function with positional index."""
        arg_func = arguments(0)
        result = arg_func("first", "second", "third")
        assert result == "first"
        
        arg_func = arguments(1)
        result = arg_func("first", "second", "third")
        assert result == "second"
    
    def test_arguments_with_keyword(self):
        """Test arguments function with keyword."""
        arg_func = arguments("volume")
        result = arg_func(volume=50)
        assert result == 50
    
    def test_arguments_with_postprocess(self):
        """Test arguments function with postprocessing."""
        arg_func = arguments(0, postprocess=lambda x: x * 2)
        result = arg_func(10)
        assert result == 20
    
    def test_arguments_with_default(self):
        """Test arguments function with default value."""
        arg_func = arguments(5, default="default_value")
        result = arg_func("a", "b", "c")  # Index 5 doesn't exist
        assert result == "default_value"
    
    def test_arguments_keyword_with_default(self):
        """Test arguments function with keyword and default."""
        arg_func = arguments("missing_key", default="default_value")
        result = arg_func(existing_key="value")
        assert result == "default_value"
    
    def test_arguments_invalid_type(self):
        """Test arguments function with invalid argument type."""
        with pytest.raises(ValueError, match="Only numeric indices, or string keys allowed"):
            arguments([1, 2, 3])
    
    def test_arguments_missing_required_positional(self):
        """Test arguments function with missing required positional argument."""
        arg_func = arguments(0)
        with pytest.raises(TypeError, match="Bad arguments"):
            arg_func()  # No arguments provided
    
    def test_arguments_missing_required_keyword(self):
        """Test arguments function with missing required keyword argument."""
        arg_func = arguments("required_key")
        with pytest.raises(TypeError, match="Bad arguments"):
            arg_func(other_key="value")


class TestProcessPayload:
    """Test cases for the process_payload function."""
    
    def test_process_payload_simple_dict(self):
        """Test processing a simple dictionary."""
        payload = {"key": "value"}
        result = process_payload(payload, "arg1", "arg2", keyword="kwarg")
        assert result == {"key": "value"}
    
    def test_process_payload_with_callable(self):
        """Test processing payload with callable values."""
        arg_func = arguments(0)
        payload = {"volume": arg_func, "static": "value"}
        
        result = process_payload(payload, 50)
        assert result == {"volume": 50, "static": "value"}
    
    def test_process_payload_nested_dict(self):
        """Test processing nested dictionary with callables."""
        arg_func = arguments("level")
        payload = {
            "settings": {
                "volume": arg_func,
                "mute": False
            },
            "other": "value"
        }
        
        result = process_payload(payload, level=75)
        assert result == {
            "settings": {
                "volume": 75,
                "mute": False
            },
            "other": "value"
        }
    
    def test_process_payload_list(self):
        """Test processing list with callables."""
        arg_func = arguments(0)
        payload = [arg_func, "static", {"nested": arg_func}]
        
        result = process_payload(payload, "dynamic")
        assert result == ["dynamic", "static", {"nested": "dynamic"}]
    
    def test_process_payload_callable_direct(self):
        """Test processing when payload itself is callable."""
        arg_func = arguments(0)
        result = process_payload(arg_func, "test_value")
        assert result == "test_value"
    
    def test_process_payload_primitive(self):
        """Test processing primitive values."""
        assert process_payload("string") == "string"
        assert process_payload(42) == 42
        assert process_payload(True) is True


class TestStandardValidation:
    """Test cases for the standard_validation function."""
    
    def test_standard_validation_success(self):
        """Test standard validation with successful response."""
        payload = {"returnValue": True, "data": "test"}
        success, error = standard_validation(payload)
        
        assert success is True
        assert error is None
        assert "returnValue" not in payload  # Should be popped
    
    def test_standard_validation_failure(self):
        """Test standard validation with failed response."""
        payload = {"returnValue": False, "errorText": "Test error"}
        success, error = standard_validation(payload)
        
        assert success is False
        assert error == "Test error"
        assert "returnValue" not in payload
        assert "errorText" not in payload
    
    def test_standard_validation_failure_no_error_text(self):
        """Test standard validation with failed response but no error text."""
        payload = {"returnValue": False}
        success, error = standard_validation(payload)
        
        assert success is False
        assert error == "Unknown error."
    
    def test_standard_validation_missing_return_value(self):
        """Test standard validation with missing returnValue."""
        payload = {"data": "test"}
        success, error = standard_validation(payload)
        
        assert success is False
        assert error == "Unknown error."
    
    def test_standard_validation_custom_key(self):
        """Test standard validation without returnValue."""
        # The actual standard_validation function doesn't take a key parameter
        # Let's test a different scenario - when returnValue is missing
        payload = {"data": "test", "subscribed": True}
        success, error = standard_validation(payload)
        
        assert success is False
        assert error == "Unknown error."


class TestWebOSControlBase:
    """Test cases for WebOSControlBase class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock WebOSClient for testing."""
        client = MagicMock(spec=WebOSClient)
        client.send_message = AsyncMock()
        return client
    
    @pytest.fixture
    def control_base(self, mock_client):
        """WebOSControlBase instance for testing."""
        return WebOSControlBase(mock_client)
    
    def test_initialization(self, mock_client):
        """Test WebOSControlBase initialization."""
        control = WebOSControlBase(mock_client)
        
        assert control.client == mock_client
        assert control.subscriptions == {}
    
    @pytest.mark.asyncio
    async def test_request_blocking(self, control_base, mock_queue):
        """Test blocking request method."""
        # Mock the client's send_message to return a queue
        control_base.client.send_message.return_value = mock_queue
        mock_queue.get.return_value = {"type": "response", "payload": {"returnValue": True}}
        
        result = await control_base.request("test://uri", {"param": "value"}, block=True, timeout=30)
        
        control_base.client.send_message.assert_called_once_with(
            'request', "test://uri", {"param": "value"}, get_queue=True
        )
        mock_queue.get.assert_called_once()
        assert result == {"type": "response", "payload": {"returnValue": True}}
    
    @pytest.mark.asyncio
    async def test_request_blocking_timeout(self, control_base, mock_queue):
        """Test blocking request with timeout."""
        control_base.client.send_message.return_value = mock_queue
        mock_queue.get.side_effect = asyncio.TimeoutError()
        
        with pytest.raises(Exception, match="Request timed out"):
            await control_base.request("test://uri", {}, block=True, timeout=1)
    
    @pytest.mark.asyncio
    async def test_request_non_blocking(self, control_base):
        """Test non-blocking request method."""
        callback = AsyncMock()
        
        await control_base.request("test://uri", {"param": "value"}, callback=callback, block=False)
        
        control_base.client.send_message.assert_called_once_with(
            'request', "test://uri", {"param": "value"}, callback=callback
        )
    
    def test_getattr_command_exists(self, control_base):
        """Test __getattr__ when command exists."""
        # Add a test command
        control_base.COMMANDS = {
            "test_command": {
                "uri": "test://command",
                "validation": standard_validation
            }
        }
        
        with patch.object(control_base, 'exec_command') as mock_exec:
            mock_exec.return_value = AsyncMock()
            
            result = control_base.test_command
            
            mock_exec.assert_called_once_with("test_command", control_base.COMMANDS["test_command"])
    
    def test_getattr_subscribe_command(self, control_base):
        """Test __getattr__ for subscribe commands."""
        control_base.COMMANDS = {
            "test_event": {
                "uri": "test://event",
                "subscription": True
            }
        }
        
        with patch.object(control_base, 'subscribe') as mock_subscribe:
            mock_subscribe.return_value = AsyncMock()
            
            result = control_base.subscribe_test_event
            
            mock_subscribe.assert_called_once_with("test_event", control_base.COMMANDS["test_event"])
    
    def test_getattr_unsubscribe_command(self, control_base):
        """Test __getattr__ for unsubscribe commands."""
        control_base.COMMANDS = {
            "test_event": {
                "uri": "test://event", 
                "subscription": True
            }
        }
        
        with patch.object(control_base, 'unsubscribe') as mock_unsubscribe:
            mock_unsubscribe.return_value = AsyncMock()
            
            result = control_base.unsubscribe_test_event
            
            mock_unsubscribe.assert_called_once_with("test_event", control_base.COMMANDS["test_event"])
    
    def test_getattr_subscribe_not_allowed(self, control_base):
        """Test __getattr__ for subscribe when subscription not allowed."""
        control_base.COMMANDS = {
            "test_command": {
                "uri": "test://command"
                # No subscription key
            }
        }
        
        with pytest.raises(AttributeError, match="Subscription not found or allowed"):
            control_base.subscribe_test_command
    
    def test_getattr_command_not_found(self, control_base):
        """Test __getattr__ when command doesn't exist."""
        with pytest.raises(AttributeError):
            control_base.nonexistent_command
    
    @pytest.mark.asyncio
    async def test_exec_command_blocking_success(self, control_base, mock_queue):
        """Test exec_command with blocking call and successful response."""
        cmd_info = {
            "uri": "test://uri",
            "validation": standard_validation,
            "return": lambda x: x["data"]
        }
        
        # Mock successful response
        response = {
            "type": "response",
            "payload": {"returnValue": True, "data": "success"}
        }
        
        with patch.object(control_base, 'request') as mock_request:
            mock_request.return_value = response
            
            command_func = control_base.exec_command("test", cmd_info)
            result = await command_func(block=True)
            
            mock_request.assert_called_once_with(
                "test://uri", None, block=True, timeout=60
            )
            assert result == "success"
    
    @pytest.mark.asyncio
    async def test_exec_command_blocking_error_response(self, control_base):
        """Test exec_command with error response."""
        cmd_info = {
            "uri": "test://uri",
            "validation": standard_validation
        }
        
        # Mock error response
        response = {
            "type": "error",
            "error": "Test error"
        }
        
        with patch.object(control_base, 'request') as mock_request:
            mock_request.return_value = response
            
            command_func = control_base.exec_command("test", cmd_info)
            
            with pytest.raises(IOError, match="Test error"):
                await command_func(block=True)
    
    @pytest.mark.asyncio
    async def test_exec_command_blocking_validation_failure(self, control_base):
        """Test exec_command with validation failure."""
        cmd_info = {
            "uri": "test://uri", 
            "validation": standard_validation
        }
        
        # Mock failed validation response
        response = {
            "type": "response",
            "payload": {"returnValue": False, "errorText": "Validation failed"}
        }
        
        with patch.object(control_base, 'request') as mock_request:
            mock_request.return_value = response
            
            command_func = control_base.exec_command("test", cmd_info)
            
            with pytest.raises(IOError, match="Validation failed"):
                await command_func(block=True)
    
    @pytest.mark.asyncio
    async def test_exec_command_with_payload(self, control_base):
        """Test exec_command with payload processing."""
        cmd_info = {
            "uri": "test://uri",
            "payload": {"volume": arguments(0)},
            "validation": standard_validation
        }
        
        response = {
            "type": "response", 
            "payload": {"returnValue": True}
        }
        
        with patch.object(control_base, 'request') as mock_request:
            mock_request.return_value = response
            
            command_func = control_base.exec_command("test", cmd_info)
            await command_func(50, block=True)
            
            # Verify the processed payload was sent
            mock_request.assert_called_once_with(
                "test://uri", {"volume": 50}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio 
    async def test_exec_command_with_callback(self, control_base):
        """Test exec_command with callback."""
        cmd_info = {
            "uri": "test://uri",
            "validation": standard_validation,
            "return": lambda x: x
        }
        
        callback = AsyncMock()
        
        with patch.object(control_base, 'request') as mock_request:
            command_func = control_base.exec_command("test", cmd_info)
            await command_func(callback=callback, block=True)
            
            # Should call request with a callback wrapper
            assert mock_request.called
            call_args = mock_request.call_args
            assert 'callback' in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_subscribe_function(self, control_base):
        """Test subscribe method."""
        cmd_info = {
            "uri": "test://subscribe",
            "subscription_validation": standard_validation,
            "return": lambda x: x
        }
        
        callback = AsyncMock()
        
        subscribe_func = control_base.subscribe("test_event", cmd_info)
        await subscribe_func(callback)
        
        # Verify subscription was registered
        assert "test_event" in control_base.subscriptions
        
        # Verify client subscribe was called
        control_base.client.subscribe.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_subscribe_already_subscribed(self, control_base):
        """Test subscribing when already subscribed."""
        control_base.subscriptions["test_event"] = "existing-uuid"
        
        cmd_info = {
            "uri": "test://subscribe",
            "subscription_validation": standard_validation
        }
        
        callback = AsyncMock()
        subscribe_func = control_base.subscribe("test_event", cmd_info)
        
        with pytest.raises(ValueError, match="Already subscribed"):
            await subscribe_func(callback)
    
    @pytest.mark.asyncio
    async def test_unsubscribe_function(self, control_base):
        """Test unsubscribe method."""
        # Set up existing subscription
        control_base.subscriptions["test_event"] = "test-uuid"
        
        cmd_info = {"uri": "test://unsubscribe"}
        
        unsubscribe_func = control_base.unsubscribe("test_event", cmd_info)
        await unsubscribe_func()
        
        # Verify subscription was removed
        assert "test_event" not in control_base.subscriptions
        
        # Verify client unsubscribe was called
        control_base.client.unsubscribe.assert_called_once_with("test-uuid")
    
    @pytest.mark.asyncio
    async def test_unsubscribe_not_subscribed(self, control_base):
        """Test unsubscribing when not subscribed."""
        cmd_info = {"uri": "test://unsubscribe"}
        
        unsubscribe_func = control_base.unsubscribe("test_event", cmd_info)
        
        with pytest.raises(ValueError, match="Not subscribed"):
            await unsubscribe_func() 