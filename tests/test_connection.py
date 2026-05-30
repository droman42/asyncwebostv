import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any
import json

from asyncwebostv.connection import WebOSClient


class TestWebOSClient:
    """Test cases for WebOSClient class."""
    
    def test_client_initialization_insecure(self):
        """Test WebOSClient initialization with insecure connection."""
        client = WebOSClient("192.168.1.100")
        
        assert client.ws_url == "ws://192.168.1.100:3000/"
        assert client.client_key is None
        assert client.waiters == {}
        assert client.subscribers == {}
        assert client.connection is None
        assert client.task is None
        assert client._connecting is False
    
    def test_client_initialization_secure(self):
        """Test WebOSClient initialization with secure connection."""
        client = WebOSClient("192.168.1.100", secure=True)
        
        assert client.ws_url == "wss://192.168.1.100:3001/"
    
    def test_client_initialization_with_client_key(self):
        """Test WebOSClient initialization with client key."""
        client = WebOSClient("192.168.1.100", client_key="test-key-123")
        
        assert client.client_key == "test-key-123"
    
    @pytest.mark.asyncio
    async def test_connect_success(self, mock_websocket):
        """Test successful connection to TV."""
        client = WebOSClient("192.168.1.100")
        
        with patch('websockets.client.connect', new_callable=AsyncMock, return_value=mock_websocket) as mock_connect:
            await client.connect()

        mock_connect.assert_called_once_with(
            "ws://192.168.1.100:3000/",
            extra_headers=[],
            origin=None,
            ping_interval=None
        )
        assert client.connection == mock_websocket
        assert client.task is not None
    
    @pytest.mark.asyncio
    async def test_connect_already_connecting(self):
        """Test connection when already connecting."""
        client = WebOSClient("192.168.1.100")
        client._connecting = True
        
        # Should not attempt to connect again
        with patch('websockets.client.connect') as mock_connect:
            await client.connect()
            mock_connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, mock_websocket):
        """Test connection when already connected."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        client.task = AsyncMock()
        
        # The connect method doesn't check for existing connection, only _connecting flag
        # So it will try to connect again, we need to mock websockets.connect
        with patch('websockets.client.connect', new_callable=AsyncMock, return_value=mock_websocket) as mock_connect:
            await client.connect()
            
            # Should have called websockets.connect
            mock_connect.assert_called_once_with(
                "ws://192.168.1.100:3000/",
                extra_headers=[],
                origin=None,
                ping_interval=None
            )
    
    @pytest.mark.asyncio
    async def test_close_connection(self, mock_websocket):
        """Test closing connection."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        # Create a real task that we can control
        async def dummy_task():
            await asyncio.sleep(10)  # This will be cancelled before it completes
        
        mock_task = asyncio.create_task(dummy_task())
        
        # Ensure the task is not done initially
        assert not mock_task.done()
        
        client.task = mock_task
        
        await client.close()
        
        mock_websocket.close.assert_called_once()
        # Verify the task was cancelled (real task, so we check if it's cancelled)
        assert mock_task.cancelled()
        assert client.connection is None
        assert client.task is None
    
    @pytest.mark.asyncio
    async def test_close_no_connection(self):
        """Test closing when no connection exists."""
        client = WebOSClient("192.168.1.100")

        # Should not raise an exception
        await client.close()

    @pytest.mark.asyncio
    async def test_close_clears_subscription_state(self, mock_websocket):
        """close() must drop waiters and subscribers so they cannot leak into
        a subsequent reconnect. Otherwise stale callbacks linger in memory and
        block re-subscribing to the same name."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket

        # Populate state as if a subscribe + an in-flight request had happened.
        client.waiters["sub-uuid"] = (AsyncMock(), None)
        client.waiters["req-uuid"] = (AsyncMock(), 12345.0)
        client.subscribers["sub-uuid"] = "ssap://audio/getVolume"

        assert client.waiters
        assert client.subscribers

        await client.close()

        assert client.waiters == {}
        assert client.subscribers == {}

    @pytest.mark.asyncio
    async def test_close_awaits_registered_callbacks(self, mock_websocket):
        """v0.3.4 close-callback registry: controls holding auxiliary
        resources (pointer socket) register a teardown coroutine, which
        close() must await before tearing down the main socket."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket

        teardown = AsyncMock()
        client.register_close_callback(teardown)

        await client.close()

        teardown.assert_awaited_once()
        # Registry must be cleared so re-using the same client doesn't
        # double-invoke stale callbacks.
        assert client._close_callbacks == []

    @pytest.mark.asyncio
    async def test_register_close_callback_dedupes(self, mock_websocket):
        """Idempotent registration: a control's lazy-connect path may run
        more than once. Multiple register_close_callback calls with the
        same callable must collapse to one invocation."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket

        teardown = AsyncMock()
        client.register_close_callback(teardown)
        client.register_close_callback(teardown)
        client.register_close_callback(teardown)

        await client.close()
        teardown.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_callback_failure_does_not_block_socket_close(self, mock_websocket):
        """If a registered callback raises, close() must still proceed to
        tear down the main socket and clear state. We log-and-continue."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket

        bad_teardown = AsyncMock(side_effect=RuntimeError("boom"))
        good_teardown = AsyncMock()
        client.register_close_callback(bad_teardown)
        client.register_close_callback(good_teardown)

        await client.close()

        bad_teardown.assert_awaited_once()
        good_teardown.assert_awaited_once()
        mock_websocket.close.assert_called_once()
        assert client._close_callbacks == []

    @pytest.mark.asyncio
    async def test_close_callbacks_fire_on_remote_close(self):
        """v0.3.5: when the remote side drops the socket, the message loop
        catches ConnectionClosed and must fire close callbacks so consumers
        learn the connection is gone — not just on explicit close()."""
        from websockets.exceptions import ConnectionClosed

        client = WebOSClient("192.168.1.100")

        # A connection whose async iteration dies mid-stream the way a
        # remote drop (standby / idle timeout / network blip) does.
        class _RemoteDrop:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionClosed(None, None)

        client.connection = _RemoteDrop()

        teardown = AsyncMock()
        client.register_close_callback(teardown)

        await client._handle_messages()

        teardown.assert_awaited_once()
        # Cleared so a later close() on the already-dead client can't
        # double-fire the same callback.
        assert client._close_callbacks == []

    @pytest.mark.asyncio
    async def test_concurrent_connect_second_caller_bails(self, mock_websocket):
        """Pins the current contract of the _connecting guard: a second
        connect() that races a first one returns immediately without dialing
        and without waiting. Callers relying on `await connect()` meaning
        "connection is ready" must serialize their own connect() calls."""
        client = WebOSClient("192.168.1.100")
        client._connecting = True  # simulate a connect() in flight

        with patch("websockets.client.connect", new_callable=AsyncMock) as mock_connect:
            await client.connect()
            mock_connect.assert_not_called()
            # Connection is NOT established for the second caller.
            assert client.connection is None
    
    @pytest.mark.asyncio
    async def test_send_message_basic(self, mock_websocket, mock_queue):
        """Test basic message sending."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        with patch('asyncio.Queue', return_value=mock_queue):
            with patch('asyncwebostv.connection.uuid4') as mock_uuid:
                mock_uuid.return_value.hex = 'test-uuid'
                result = await client.send_message('request', 'test://uri', {'param': 'value'})
                
                # Verify websocket.send was called with correct message
                mock_websocket.send.assert_called_once()
                sent_message = json.loads(mock_websocket.send.call_args[0][0])
                
                assert sent_message['type'] == 'request'
                assert sent_message['uri'] == 'test://uri'
                assert sent_message['payload'] == {'param': 'value'}
                # Check that the ID is set (don't rely on exact value)
                assert 'id' in sent_message
    
    @pytest.mark.asyncio
    async def test_send_message_with_queue(self, mock_websocket, mock_queue):
        """Test message sending with queue for response handling."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        with patch('asyncio.Queue', return_value=mock_queue):
            queue = await client.send_message('request', 'test://uri', {}, get_queue=True)
            
            assert queue == mock_queue
            # Check that a waiter was added (don't rely on exact UUID)
            assert len(client.waiters) == 1
    
    @pytest.mark.asyncio
    async def test_send_message_with_callback(self, mock_websocket):
        """Test message sending with callback."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        callback = AsyncMock()
        
        await client.send_message('request', 'test://uri', {}, callback=callback)
        
        # Check that a waiter was added with the callback
        assert len(client.waiters) == 1
        waiter_callback, _ = list(client.waiters.values())[0]
        assert waiter_callback == callback
    
    @pytest.mark.asyncio
    async def test_subscribe(self, mock_websocket):
        """Test subscription to TV events."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        callback = AsyncMock()
        
        await client.subscribe('test://uri', 'sub-id', callback)
        
        # Verify subscription message was sent
        mock_websocket.send.assert_called_once()
        sent_message = json.loads(mock_websocket.send.call_args[0][0])
        
        assert sent_message['type'] == 'subscribe'
        assert sent_message['uri'] == 'test://uri'
        assert 'id' in sent_message
        
        # Verify subscriber was registered  
        assert 'sub-id' in client.subscribers
        # The subscriber value should be the generated UUID
        assert len(client.subscribers['sub-id']) > 0
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, mock_websocket):
        """Test unsubscribing from TV events."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        client.subscribers['sub-id'] = 'test-uuid'
        
        await client.unsubscribe('sub-id')
        
        # Verify unsubscribe message was sent
        mock_websocket.send.assert_called_once()
        sent_message = json.loads(mock_websocket.send.call_args[0][0])
        
        assert sent_message['type'] == 'unsubscribe'
        assert sent_message['uri'] == 'test-uuid'  # URI should be the stored value
        assert 'id' in sent_message  # ID is generated, not the subscription ID
        
        # Verify subscriber was removed
        assert 'sub-id' not in client.subscribers
    
    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self, mock_websocket):
        """Test unsubscribing from non-existent subscription."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        # Should raise a ValueError for non-existent subscription
        with pytest.raises(ValueError, match="Subscription not found"):
            await client.unsubscribe('non-existent')
    
    @pytest.mark.asyncio
    async def test_registration_flow(self, mock_websocket, mock_queue, mock_registration_response):
        """Test complete registration flow."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        # Mock queue responses for registration flow
        mock_queue.get.side_effect = mock_registration_response
        
        store = {}
        
        with patch('asyncio.Queue', return_value=mock_queue):
            with patch('uuid.uuid4', return_value='reg-uuid'):
                results = []
                async for status in client.register(store):
                    results.append(status)
                
                assert WebOSClient.PROMPTED in results
                assert WebOSClient.REGISTERED in results
                assert store["client_key"] == "test-client-key-12345"
                assert client.client_key == "test-client-key-12345"
    
    @pytest.mark.asyncio
    async def test_registration_timeout(self, mock_websocket, mock_queue):
        """Test registration timeout."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        # Mock queue to raise timeout
        mock_queue.get.side_effect = asyncio.TimeoutError()
        
        with patch('asyncio.Queue', return_value=mock_queue):
            with patch('uuid.uuid4', return_value='reg-uuid'):
                store = {}
                
                with pytest.raises(Exception, match="Timeout during registration"):
                    async for status in client.register(store, timeout=1):
                        pass
    
    @pytest.mark.asyncio
    async def test_registration_error(self, mock_websocket, mock_queue):
        """Test registration error handling."""
        client = WebOSClient("192.168.1.100")
        client.connection = mock_websocket
        
        # Mock error response
        error_response = {
            "type": "error",
            "error": "Registration failed"
        }
        mock_queue.get.return_value = error_response
        
        with patch('asyncio.Queue', return_value=mock_queue):
            with patch('uuid.uuid4', return_value='reg-uuid'):
                store = {}
                
                with pytest.raises(Exception, match="Registration failed"):
                    async for status in client.register(store):
                        pass
    
    @pytest.mark.asyncio
    async def test_handle_message_response(self, mock_queue):
        """Test handling response messages."""
        client = WebOSClient("192.168.1.100")
        
        # Set up waiter
        callback = AsyncMock()
        client.waiters['test-id'] = (callback, None)
        
        message = {
            'type': 'response',
            'id': 'test-id',
            'payload': {'returnValue': True}
        }
        
        await client._process_message(message)
        
        # Verify callback was called
        callback.assert_called_once_with(message)
        
        # Verify waiter was removed
        assert 'test-id' not in client.waiters
    
    @pytest.mark.asyncio
    async def test_handle_message_callback(self):
        """Test handling messages with callbacks."""
        client = WebOSClient("192.168.1.100")
        
        callback = AsyncMock()
        client.waiters['test-id'] = (callback, None)
        
        message = {
            'type': 'response',
            'id': 'test-id',
            'payload': {'returnValue': True}
        }
        
        await client._process_message(message)
        
        # Verify callback was called
        callback.assert_called_once_with(message)
        
        # Verify waiter was removed
        assert 'test-id' not in client.waiters
    
    @pytest.mark.asyncio
    async def test_handle_message_subscription(self):
        """Test handling subscription messages."""
        client = WebOSClient("192.168.1.100")
        
        callback = AsyncMock()
        client.waiters['test-id'] = (callback, None)
        client.subscribers['test-id'] = 'test://uri'
        
        message = {
            'type': 'response',
            'id': 'test-id',
            'payload': {'subscribed': True, 'returnValue': True}
        }
        
        await client._process_message(message)
        
        # Verify callback was called
        callback.assert_called_once_with(message)
        
        # For subscriptions, waiter should NOT be removed
        assert 'test-id' in client.waiters
    
    def test_discover_sync(self):
        """Test synchronous TV discovery."""
        with patch('asyncwebostv.connection.discover_sync') as mock_discover:
            mock_discover.return_value = ["192.168.1.100", "192.168.1.101"]
            
            clients = WebOSClient.discover_sync()
            
            mock_discover.assert_called_once_with(
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                keyword="LG", 
                hosts=True, 
                retries=3
            )
            
            assert len(clients) == 2
            assert all(isinstance(client, WebOSClient) for client in clients)
    
    @pytest.mark.asyncio
    async def test_discover_async(self):
        """Test asynchronous TV discovery."""
        with patch('asyncwebostv.connection.discover') as mock_discover:
            mock_discover.return_value = ["192.168.1.100", "192.168.1.101"]
            
            clients = await WebOSClient.discover()
            
            mock_discover.assert_called_once_with(
                "urn:schemas-upnp-org:device:MediaRenderer:1",
                keyword="LG",
                hosts=True,
                retries=3
            )
            
            assert len(clients) == 2
            assert all(isinstance(client, WebOSClient) for client in clients) 