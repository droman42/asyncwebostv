import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from unittest.mock import Mock
import socket

from asyncwebostv.discovery import read_location, validate_location, discover


def test_read_location():
    """Test the read_location function."""
    # Test with string input (note: actual format uses \r\n and "LOCATION:")
    test_resp = "Some data\r\nLOCATION: http://example.com\r\nMore data"
    assert read_location(test_resp) == "http://example.com"
    
    # Test with bytes input
    test_resp_bytes = b"Some data\r\nLOCATION: http://example.com\r\nMore data"
    assert read_location(test_resp_bytes) == "http://example.com"
    
    # Test with no location
    test_resp_no_location = "Some data\r\nNo location here\r\nMore data"
    assert read_location(test_resp_no_location) is None
    
    # Test with keyword filtering
    test_resp_with_keyword = "Some data\r\nLOCATION: http://lg-tv.com/desc.xml\r\nMore data"
    assert read_location(test_resp_with_keyword, keyword="lg") == "http://lg-tv.com/desc.xml"
    assert read_location(test_resp_with_keyword, keyword="samsung") is None
    
    # Test case insensitive location parsing
    test_resp_case = "Some data\r\nlocation: http://example.com\r\nMore data"
    assert read_location(test_resp_case) == "http://example.com"


@pytest.mark.asyncio
async def test_validate_location():
    """Test the validate_location function."""
    # Test with keyword match
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_response = AsyncMock()
        mock_response.read.return_value = b"content with LG keyword"
        
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        result = await validate_location("http://example.com", "LG")
        assert result is True
        
        # Test with no keyword
        result = await validate_location("http://example.com", None)
        assert result is True
        
        # Test with keyword mismatch
        mock_response.read.return_value = b"content without the keyword"
        result = await validate_location("http://example.com", "LG")
        assert result is False


@pytest.mark.asyncio
async def test_validate_location_timeout():
    """Test validate_location with timeout exception."""
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get.side_effect = asyncio.TimeoutError()
        mock_session_class.return_value = mock_session
        
        result = await validate_location("http://example.com", "LG")
        assert result is False


@pytest.mark.asyncio
async def test_discover_basic():
    """Test the discover function with basic functionality."""
    # Mock SSDP response
    ssdp_response = b"""HTTP/1.1 200 OK\r
CACHE-CONTROL: max-age=1800\r
LOCATION: http://192.168.1.100:8000/rootDesc.xml\r
SERVER: Linux/3.14.0 UPnP/1.0 IpBridge/1.26.0\r
ST: upnp:rootdevice\r
USN: uuid:test-device::upnp:rootdevice\r
\r
"""
    
    # Mock socket operations completely
    mock_socket = Mock()
    mock_socket.recv.return_value = ssdp_response
    
    # Mock validate_location to return True
    async def mock_validate_location(*args, **kwargs):
        return True
    
    # Mock asyncio functions
    mock_loop = Mock()
    mock_loop.time.side_effect = [0, 0.1, 0.2, 6.0]  # Simulate timeout after a few iterations
    
    # Track socket calls
    socket_calls = []
    def track_socket_creation(*args, **kwargs):
        socket_calls.append((args, kwargs))
        return mock_socket
    
    with patch("socket.socket", side_effect=track_socket_creation), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()), \
         patch("asyncwebostv.discovery.validate_location", side_effect=mock_validate_location):
        
        # Test discover with hosts=False
        result = await discover("urn:schemas-upnp-org:device:MediaRenderer:1", "LG", hosts=False, timeout=1)
        
        # Should return a set (even if empty due to timeout)
        assert isinstance(result, set)
        
        # Verify socket was created and configured
        assert len(socket_calls) == 1
        assert mock_socket.setsockopt.called
        assert mock_socket.settimeout.called
        assert mock_socket.sendto.called
        assert mock_socket.setblocking.called
        assert mock_socket.close.called


@pytest.mark.asyncio 
async def test_discover_with_successful_response():
    """Test discover when it successfully receives and processes a response."""
    ssdp_response = b"""HTTP/1.1 200 OK\r
LOCATION: http://192.168.1.100:8000/rootDesc.xml\r
\r
"""
    
    mock_socket = Mock()
    mock_socket.recv.return_value = ssdp_response
    
    async def mock_validate_location(*args, **kwargs):
        return True
    
    # Simulate receiving one response then timing out
    mock_loop = Mock()
    mock_loop.time.side_effect = [0, 0.1, 6.0]  # First call within timeout, second exceeds
    
    # Mock wait_for to succeed once then timeout
    wait_for_calls = []
    async def mock_wait_for(coro, timeout):
        wait_for_calls.append(timeout)
        if len(wait_for_calls) == 1:
            return None  # First call succeeds
        else:
            raise asyncio.TimeoutError()  # Subsequent calls timeout
    
    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("asyncio.wait_for", side_effect=mock_wait_for), \
         patch("asyncwebostv.discovery.validate_location", side_effect=mock_validate_location):
        
        # Test with hosts=False
        result = await discover("urn:schemas-upnp-org:device:MediaRenderer:1", "LG", hosts=False, timeout=5)
        assert isinstance(result, set)
        assert "http://192.168.1.100:8000/rootDesc.xml" in result
        
        # Test with hosts=True  
        result = await discover("urn:schemas-upnp-org:device:MediaRenderer:1", "LG", hosts=True, timeout=5)
        assert isinstance(result, set)
        assert "192.168.1.100" in result


@pytest.mark.asyncio
async def test_discover_no_responses():
    """Test discover when no devices respond."""
    mock_socket = Mock()
    
    mock_loop = Mock()
    mock_loop.time.side_effect = [0, 6.0]  # Immediately timeout
    
    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
        
        result = await discover("urn:schemas-upnp-org:device:MediaRenderer:1", "LG", timeout=5)
        assert isinstance(result, set)
        assert len(result) == 0


@pytest.mark.asyncio
async def test_discover_invalid_location():
    """Test discover when validation fails."""
    ssdp_response = b"""HTTP/1.1 200 OK\r
LOCATION: http://192.168.1.100:8000/rootDesc.xml\r
\r
"""
    
    mock_socket = Mock()
    mock_socket.recv.return_value = ssdp_response
    
    # Mock validate_location to return False
    async def mock_validate_location(*args, **kwargs):
        return False
    
    mock_loop = Mock()
    mock_loop.time.side_effect = [0, 0.1, 6.0]
    
    async def mock_wait_for(coro, timeout):
        return None  # Simulate successful recv
    
    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("asyncio.wait_for", side_effect=mock_wait_for), \
         patch("asyncwebostv.discovery.validate_location", side_effect=mock_validate_location):
        
        result = await discover("urn:schemas-upnp-org:device:MediaRenderer:1", "LG", timeout=5)
        assert isinstance(result, set)
        assert len(result) == 0  # Should be empty since validation failed 