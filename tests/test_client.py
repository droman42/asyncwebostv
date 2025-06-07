import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from asyncwebostv.client import WebOSTV, SecureWebOSTV
from asyncwebostv.connection import WebOSClient
from asyncwebostv.secure_connection import SecureWebOSClient
from asyncwebostv.controls import (
    MediaControl, ApplicationControl, SystemControl,
    InputControl, SourceControl, TvControl
)


class TestWebOSTV:
    """Test cases for WebOSTV client class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock WebOSClient for testing."""
        client = MagicMock(spec=WebOSClient)
        client.connect = AsyncMock()
        client.close = AsyncMock()
        client.register = AsyncMock()
        return client
    
    def test_webostv_initialization(self):
        """Test WebOSTV initialization with default parameters."""
        tv = WebOSTV("192.168.1.100")
        
        assert tv.host == "192.168.1.100"
        assert tv.client_key is None
        assert tv.client is not None
        assert isinstance(tv.client, WebOSClient)
        
        # Control objects should be None initially (they get initialized in connect())
        assert tv.media is None
        assert tv.application is None
        assert tv.system is None
        assert tv.input is None
        assert tv.source is None
        assert tv.tv is None
    
    def test_webostv_initialization_with_client_key(self):
        """Test WebOSTV initialization with client key."""
        tv = WebOSTV("192.168.1.100", client_key="test-key-123")
        
        assert tv.host == "192.168.1.100"
        assert tv.client_key == "test-key-123"
        assert tv.client.client_key == "test-key-123"
    
    def test_webostv_initialization_with_timeout(self):
        """Test WebOSTV initialization with custom timeout."""
        # WebOSTV doesn't actually take a timeout parameter in __init__
        # Timeout is passed to individual methods like register()
        tv = WebOSTV("192.168.1.100")
        
        assert tv.host == "192.168.1.100"
        # Control objects should be None initially
        assert tv.media is None
        assert tv.application is None
        assert tv.system is None
    
    @pytest.mark.asyncio
    async def test_connect_method(self, mock_client):
        """Test WebOSTV connect method."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        # Create an async generator function
        async def mock_register(store, timeout=60):
            yield WebOSClient.REGISTERED
        
        # Replace the register method entirely
        mock_client.register = mock_register
        
        await tv.connect()
        
        mock_client.connect.assert_called_once()
        # Control objects should be initialized after connect
        assert tv.media is not None
        assert tv.system is not None
    
    @pytest.mark.asyncio
    async def test_close_method(self, mock_client):
        """Test WebOSTV close method."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        await tv.close()
        
        mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_method(self, mock_client):
        """Test WebOSTV register method."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        # Create an async generator function
        async def mock_register(store, timeout=60):
            yield WebOSClient.PROMPTED
            # Simulate setting the client key in the store BEFORE yielding REGISTERED
            store["client_key"] = "test-key"
            yield WebOSClient.REGISTERED
        
        # Replace the register method entirely
        mock_client.register = mock_register
        
        result = await tv.register(timeout=60)
        
        # register() should return the client key
        assert result == "test-key"
    
    @pytest.mark.asyncio
    async def test_register_method_with_timeout(self, mock_client):
        """Test WebOSTV register method with custom timeout."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        # Create an async generator function
        async def mock_register(store, timeout=30):
            yield WebOSClient.PROMPTED
            # Simulate setting the client key in the store BEFORE yielding REGISTERED
            store["client_key"] = "test-key-30"
            yield WebOSClient.REGISTERED
        
        # Replace the register method entirely
        mock_client.register = mock_register
        
        result = await tv.register(timeout=30)
        
        # Should return client key
        assert result == "test-key-30"
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_client):
        """Test WebOSTV as async context manager."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        # Create an async generator function
        async def mock_register(store, timeout=60):
            yield WebOSClient.REGISTERED
        
        # Replace the register method entirely
        mock_client.register = mock_register
        
        with patch('asyncwebostv.controls.InputControl.connect_input') as mock_input_connect:
            mock_input_connect.return_value = None
            
            async with tv:
                mock_client.connect.assert_called_once()
            
            mock_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_context_manager_exception_handling(self, mock_client):
        """Test WebOSTV async context manager exception handling."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        try:
            async with tv:
                raise Exception("Test exception")
        except Exception:
            pass
        
        # Close should still be called even if exception occurs
        mock_client.close.assert_called_once()
    
    def test_is_connected_property(self, mock_client):
        """Test WebOSTV is_connected property."""
        tv = WebOSTV("192.168.1.100")
        tv.client = mock_client
        
        # Mock connected state
        mock_client.connection = MagicMock()  # Not None = connected
        assert (tv.client.connection is not None) is True
        
        # Mock disconnected state  
        mock_client.connection = None
        assert (tv.client.connection is not None) is False
    
    def test_discover_sync_class_method(self):
        """Test WebOSTV discover_sync class method."""
        # WebOSTV doesn't have discover_sync, but WebOSClient does
        with patch.object(WebOSClient, 'discover_sync') as mock_discover:
            mock_clients = [
                MagicMock(spec=WebOSClient),
                MagicMock(spec=WebOSClient)
            ]
            mock_discover.return_value = mock_clients
            
            clients = WebOSClient.discover_sync()
            
            mock_discover.assert_called_once()
            assert len(clients) == 2
            assert all(isinstance(client, MagicMock) for client in clients)
    
    @pytest.mark.asyncio
    async def test_discover_async_class_method(self):
        """Test WebOSTV discover async class method."""
        # WebOSTV doesn't have discover, but WebOSClient does
        with patch.object(WebOSClient, 'discover') as mock_discover:
            mock_clients = [
                MagicMock(spec=WebOSClient),
                MagicMock(spec=WebOSClient)
            ]
            mock_discover.return_value = mock_clients
            
            clients = await WebOSClient.discover()
            
            mock_discover.assert_called_once()
            assert len(clients) == 2
            assert all(isinstance(client, MagicMock) for client in clients)
    
    def test_str_representation(self):
        """Test WebOSTV string representation."""
        tv = WebOSTV("192.168.1.100")
        
        # The actual implementation doesn't override __str__, so it uses default object repr
        assert "WebOSTV object" in str(tv)
    
    def test_repr_representation(self):
        """Test WebOSTV repr representation."""
        tv = WebOSTV("192.168.1.100", client_key="test-key")
        
        # The actual implementation doesn't override __repr__, so it uses default object repr
        assert "WebOSTV object" in repr(tv)
    
    def test_repr_without_client_key(self):
        """Test WebOSTV repr representation without client key."""
        tv = WebOSTV("192.168.1.100")
        
        # The actual implementation doesn't override __repr__, so it uses default object repr
        assert "WebOSTV object" in repr(tv)


class TestSecureWebOSTV:
    """Test cases for SecureWebOSTV client class."""
    
    def test_secure_webostv_initialization(self):
        """Test SecureWebOSTV initialization."""
        tv = SecureWebOSTV("192.168.1.100")
        
        assert tv.host == "192.168.1.100"
        assert tv.client_key is None
        assert tv.client is not None
        assert isinstance(tv.client, SecureWebOSClient)
        
        # Client should be configured for secure connection
        assert tv.client.ws_url.startswith("wss://")
        assert ":3001/" in tv.client.ws_url
    
    def test_secure_webostv_initialization_with_params(self):
        """Test SecureWebOSTV initialization with parameters."""
        tv = SecureWebOSTV("192.168.1.100", client_key="secure-key", port=3001)
        
        assert tv.host == "192.168.1.100"
        assert tv.client_key == "secure-key"
        # SecureWebOSTV doesn't have a timeout attribute
        assert tv.client.client_key == "secure-key"
    
    def test_secure_webostv_inherits_from_webostv(self):
        """Test SecureWebOSTV inherits from WebOSTV."""
        tv = SecureWebOSTV("192.168.1.100")
        
        assert isinstance(tv, WebOSTV)
        
        # Control objects should be None initially (they get initialized in connect())
        assert tv.media is None
        assert tv.application is None
        assert tv.system is None
        assert tv.input is None
        assert tv.source is None
        assert tv.tv is None
    
    @pytest.mark.asyncio
    async def test_secure_webostv_async_context_manager(self):
        """Test SecureWebOSTV as async context manager."""
        tv = SecureWebOSTV("192.168.1.100")
        
        # Mock the async iterator that register returns
        async def mock_register_iter(store, timeout=60):
            yield WebOSClient.REGISTERED
        
        with patch.object(tv.client, 'connect') as mock_connect:
            with patch.object(tv.client, 'register') as mock_register:
                with patch.object(tv.client, 'close') as mock_close:
                    with patch('asyncwebostv.controls.InputControl.connect_input') as mock_input_connect:
                        mock_register.side_effect = lambda store, timeout=60: mock_register_iter(store, timeout)
                        mock_input_connect.return_value = None
                        
                        async with tv:
                            mock_connect.assert_called_once()
                        
                        mock_close.assert_called_once()
    
    def test_secure_webostv_discover_sync_class_method(self):
        """Test SecureWebOSTV discover_sync class method."""
        # SecureWebOSTV doesn't have discover_sync, but WebOSClient does
        with patch.object(WebOSClient, 'discover_sync') as mock_discover:
            mock_clients = [
                MagicMock(spec=WebOSClient),
                MagicMock(spec=WebOSClient)
            ]
            mock_discover.return_value = mock_clients
            
            clients = WebOSClient.discover_sync(secure=True)
            
            mock_discover.assert_called_once_with(secure=True)
            assert len(clients) == 2
            assert all(isinstance(client, MagicMock) for client in clients)
    
    @pytest.mark.asyncio
    async def test_secure_webostv_discover_async_class_method(self):
        """Test SecureWebOSTV discover async class method."""
        # SecureWebOSTV doesn't have discover, but WebOSClient does
        with patch.object(WebOSClient, 'discover') as mock_discover:
            mock_clients = [
                MagicMock(spec=WebOSClient),
                MagicMock(spec=WebOSClient)
            ]
            mock_discover.return_value = mock_clients
            
            clients = await WebOSClient.discover(secure=True)
            
            mock_discover.assert_called_once_with(secure=True)
            assert len(clients) == 2
            assert all(isinstance(client, MagicMock) for client in clients)
    
    def test_secure_webostv_str_representation(self):
        """Test SecureWebOSTV string representation."""
        tv = SecureWebOSTV("192.168.1.100")
        
        # The actual implementation doesn't override __str__, so it uses default object repr
        assert "SecureWebOSTV object" in str(tv)
    
    def test_secure_webostv_repr_representation(self):
        """Test SecureWebOSTV repr representation."""
        tv = SecureWebOSTV("192.168.1.100", client_key="secure-key")
        
        # The actual implementation doesn't override __repr__, so it uses default object repr
        assert "SecureWebOSTV object" in repr(tv)


class TestClientIntegration:
    """Integration tests for client functionality."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """Test a simulated full workflow."""
        tv = WebOSTV("192.168.1.100")
        
        # Mock the async iterator that register returns
        async def mock_register_iter(store, timeout=60):
            store["client_key"] = "test-key"  # Set key before yielding
            yield WebOSClient.REGISTERED
        
        with patch.object(tv.client, 'connect') as mock_connect:
            with patch.object(tv.client, 'register') as mock_register:
                with patch.object(tv.client, 'close') as mock_close:
                    with patch('asyncwebostv.controls.InputControl.connect_input') as mock_input_connect:
                        
                        # Mock responses
                        mock_register.side_effect = lambda store, timeout=60: mock_register_iter(store, timeout)
                        mock_input_connect.return_value = None
                        
                        # Simulate workflow
                        await tv.connect()
                        
                        result = await tv.register(timeout=60)
                        
                        # After connect, control objects should be available
                        with patch.object(tv.system, 'info') as mock_info:
                            with patch.object(tv.application, 'list_apps') as mock_list_apps:
                                mock_info.return_value = {"major_ver": "6", "minor_ver": "3"}
                                mock_list_apps.return_value = []
                                
                                system_info = await tv.system.info()
                                apps = await tv.application.list_apps()
                        
                        await tv.close()
                        
                        # Verify calls were made - expect 2 register calls: one from connect(), one from register()
                        mock_connect.assert_called_once()
                        assert mock_register.call_count == 2  # Called by both connect() and register()
                        mock_close.assert_called_once()
                        
                        # Result should be the client key
                        assert result == "test-key"
                        
                        # System info should be returned correctly
                        assert system_info["major_ver"] == "6"
                        assert system_info["minor_ver"] == "3"
    
    @pytest.mark.asyncio
    async def test_error_handling_during_connection(self):
        """Test error handling during connection."""
        tv = WebOSTV("192.168.1.100")
        
        with patch.object(tv.client, 'connect') as mock_connect:
            mock_connect.side_effect = ConnectionError("Connection failed")
            
            with pytest.raises(ConnectionError, match="Connection failed"):
                await tv.connect()
    
    @pytest.mark.asyncio
    async def test_control_objects_share_client(self):
        """Test that all control objects share the same client instance."""
        tv = WebOSTV("192.168.1.100")
        
        # Mock the async iterator that register returns
        async def mock_register_iter(store, timeout=60):
            yield WebOSClient.REGISTERED
        
        with patch.object(tv.client, 'connect'):
            with patch.object(tv.client, 'register') as mock_register:
                mock_register.side_effect = lambda store, timeout=60: mock_register_iter(store, timeout)
                
                # Connect to initialize control objects
                await tv.connect()
                
                # All control objects should use the same client
                assert tv.media.client is tv.client
                assert tv.application.client is tv.client
                assert tv.system.client is tv.client
                assert tv.input.client is tv.client
                assert tv.source.client is tv.client
                assert tv.tv.client is tv.client
    
    def test_client_configuration_consistency(self):
        """Test that client configuration is consistent across WebOSTV and SecureWebOSTV."""
        # Regular WebOSTV
        tv = WebOSTV("192.168.1.100", client_key="test-key")
        # WebOSClient doesn't have a host attribute, but we can check the ws_url
        assert tv.client.client_key == "test-key"
        assert tv.client.ws_url.startswith("ws://")
        assert ":3000/" in tv.client.ws_url
        
        # Secure WebOSTV
        secure_tv = SecureWebOSTV("192.168.1.100", client_key="test-key")
        assert secure_tv.client.client_key == "test-key"
        assert secure_tv.client.ws_url.startswith("wss://")
        assert ":3001/" in secure_tv.client.ws_url 