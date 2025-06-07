import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional
import json

from asyncwebostv.connection import WebOSClient
from asyncwebostv.client import WebOSTV, SecureWebOSTV


@pytest.fixture
def mock_websocket():
    """Mock websocket connection."""
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock()
    mock_ws.close = AsyncMock()
    mock_ws.closed = False
    return mock_ws


@pytest.fixture
def mock_tv_response():
    """Factory for creating mock TV responses."""
    def _create_response(payload: Dict[str, Any], msg_type: str = "response") -> Dict[str, Any]:
        return {
            "type": msg_type,
            "id": "test-id",
            "payload": payload
        }
    return _create_response


@pytest.fixture
def mock_successful_response(mock_tv_response):
    """Standard successful TV response."""
    return mock_tv_response({"returnValue": True})


@pytest.fixture
def mock_error_response(mock_tv_response):
    """Standard error TV response."""
    return mock_tv_response({
        "returnValue": False,
        "errorText": "Test error message"
    })


@pytest.fixture
def mock_registration_response():
    """Mock registration response sequence."""
    return [
        {
            "type": "response",
            "payload": {"pairingType": "PROMPT"}
        },
        {
            "type": "registered",
            "payload": {"client-key": "test-client-key-12345"}
        }
    ]


@pytest.fixture
def mock_system_info():
    """Mock system information response."""
    return {
        "returnValue": True,
        "product_name": "webOS TV UH7700",
        "model_name": "UH7700",
        "sw_type": "FIRMWARE",
        "major_ver": "3",
        "minor_ver": "2",
        "country": "US",
        "device_id": "12345678-abcd-efgh-ijkl-123456789012",
        "auth_flag": "N",
        "ignore_disable": "N",
        "eco_info": "01",
        "config_key": "00",
        "language_code": "en-US"
    }


@pytest.fixture
def mock_volume_info():
    """Mock volume information response."""
    return {
        "returnValue": True,
        "volume": 15,
        "muted": False,
        "scenario": "mastervolume_tv_speaker"
    }


@pytest.fixture
def mock_app_list():
    """Mock application list response."""
    return {
        "returnValue": True,
        "apps": [
            {
                "id": "com.webos.app.home",
                "title": "Home",
                "icon": "/usr/palm/applications/com.webos.app.home/icon.png",
                "version": "1.0.0"
            },
            {
                "id": "netflix",
                "title": "Netflix",
                "icon": "/usr/palm/applications/netflix/icon.png", 
                "version": "2.1.0"
            }
        ]
    }


@pytest.fixture
def mock_input_sources():
    """Mock input sources response."""
    return {
        "returnValue": True,
        "devices": [
            {
                "id": "HDMI_1",
                "label": "HDMI 1",
                "port": 1,
                "appId": "com.webos.app.hdmi1"
            },
            {
                "id": "HDMI_2", 
                "label": "HDMI 2",
                "port": 2,
                "appId": "com.webos.app.hdmi2"
            }
        ]
    }


@pytest.fixture
def mock_channel_list():
    """Mock channel list response."""
    return {
        "returnValue": True,
        "channelList": [
            {
                "channelId": "1_1_1_0_0_1234_0",
                "channelNumber": "2-1",
                "channelName": "ABC",
                "majorNumber": 2,
                "minorNumber": 1
            },
            {
                "channelId": "1_1_1_0_0_5678_0", 
                "channelNumber": "7-1",
                "channelName": "NBC",
                "majorNumber": 7,
                "minorNumber": 1
            }
        ]
    }


@pytest.fixture
async def mock_webos_client(mock_websocket):
    """Mock WebOSClient with mocked websocket."""
    client = WebOSClient("192.168.1.100", client_key="test-key")
    
    # Mock the connection
    client.connection = mock_websocket
    client.task = AsyncMock()
    
    # Mock send_message method
    client.send_message = AsyncMock()
    
    return client


@pytest.fixture
async def mock_webos_tv(mock_webos_client):
    """Mock WebOSTV with mocked client."""
    tv = WebOSTV("192.168.1.100", client_key="test-key")
    tv.client = mock_webos_client
    return tv


@pytest.fixture
def mock_queue():
    """Mock asyncio Queue."""
    queue = AsyncMock()
    queue.get = AsyncMock()
    queue.put = AsyncMock()
    return queue


@pytest.fixture
def event_loop_mock():
    """Mock event loop for testing timeout scenarios."""
    loop = MagicMock()
    loop.time.return_value = 0
    return loop


@pytest.fixture
def mock_ssl_context():
    """Mock SSL context for secure connection tests."""
    context = MagicMock()
    context.check_hostname = True
    context.verify_mode = 1
    return context


# Async test helper
@pytest.fixture
def async_test():
    """Helper for running async test functions."""
    def _async_test(coro):
        return asyncio.get_event_loop().run_until_complete(coro)
    return _async_test 