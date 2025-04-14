import pytest
import asyncio
from unittest.mock import patch, MagicMock

from asyncwebostv.discovery import read_location, validate_location, discover


def test_read_location():
    """Test the read_location function."""
    # Test with string input
    test_resp = "Some data\nlocation: http://example.com\nMore data"
    assert read_location(test_resp) == "http://example.com"
    
    # Test with bytes input
    test_resp_bytes = b"Some data\nlocation: http://example.com\nMore data"
    assert read_location(test_resp_bytes) == "http://example.com"
    
    # Test with no location
    test_resp_no_location = "Some data\nNo location here\nMore data"
    assert read_location(test_resp_no_location) is None


@pytest.mark.asyncio
async def test_validate_location():
    """Test the validate_location function."""
    # Mock aiohttp.ClientSession
    mock_response = MagicMock()
    mock_response.read.return_value = b"content with LG keyword"
    
    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    with patch("aiohttp.ClientSession", return_value=mock_session):
        # Test with keyword match
        assert await validate_location("http://example.com", "LG") is True
        
        # Test with no keyword
        assert await validate_location("http://example.com", None) is True
        
        # Test with keyword mismatch
        mock_response.read.return_value = b"content without the keyword"
        assert await validate_location("http://example.com", "LG") is False
        
        # Test with timeout exception
        mock_session.get.side_effect = asyncio.TimeoutError()
        assert await validate_location("http://example.com", "LG") is False


@pytest.mark.asyncio
async def test_discover():
    """Test the discover function."""
    # Mock socket operations
    mock_socket = MagicMock()
    mock_socket.recv.return_value = b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.100:8000/\r\n"
    
    # Mock validate_location to always return True
    async def mock_validate_location(*args, **kwargs):
        return True
    
    with patch("socket.socket", return_value=mock_socket), \
         patch("asyncio.get_event_loop") as mock_loop, \
         patch("asyncwebostv.discovery.validate_location", mock_validate_location):
        
        # Configure mock_loop
        mock_loop.return_value.time.return_value = 0
        mock_loop.return_value.sock_recv.return_value = asyncio.Future()
        mock_loop.return_value.sock_recv.return_value.set_result(None)
        
        # Test discover with hosts=False
        result = await discover("test-service", "LG", hosts=False)
        assert "http://192.168.1.100:8000/" in result
        
        # Test discover with hosts=True
        result = await discover("test-service", "LG", hosts=True)
        assert "192.168.1.100" in result 