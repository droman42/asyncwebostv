import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from asyncwebostv.controls import SystemControl, standard_validation


class TestSystemControl:
    """Test cases for SystemControl class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock WebOSClient for testing."""
        client = MagicMock()
        client.send_message = AsyncMock()
        return client
    
    @pytest.fixture
    def system_control(self, mock_client):
        """SystemControl instance for testing."""
        return SystemControl(mock_client)
    
    def test_system_control_commands_structure(self, system_control):
        """Test that SystemControl has all expected commands."""
        expected_commands = [
            "power_off", "power_on", "info", "notify", 
            "launcher", "get_settings"
        ]
        
        for command in expected_commands:
            assert command in system_control.COMMANDS
    
    @pytest.mark.asyncio
    async def test_power_off_command(self, system_control, mock_successful_response):
        """Test power off command."""
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await system_control.power_off()
            
            mock_request.assert_called_once_with(
                "ssap://system/turnOff", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_power_on_command(self, system_control, mock_successful_response):
        """Test power on command."""
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await system_control.power_on()
            
            mock_request.assert_called_once_with(
                "ssap://system/turnOn", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_info_command(self, system_control, mock_system_info):
        """Test system info command."""
        response = {"type": "response", "payload": mock_system_info}
        
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await system_control.info()
            
            mock_request.assert_called_once_with(
                "ssap://system/getSystemInfo", None, block=True, timeout=60
            )
            assert result == mock_system_info
            assert result["product_name"] == "webOS TV UH7700"
            assert result["major_ver"] == "3"
    
    @pytest.mark.asyncio
    async def test_notify_command_simple(self, system_control, mock_successful_response):
        """Test notification command with simple message."""
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await system_control.notify("Test notification")
            
            mock_request.assert_called_once_with(
                "ssap://system.notifications/createToast",
                {"message": "Test notification"},
                block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_notify_command_with_icon(self, system_control, mock_successful_response):
        """Test notification command with icon."""
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            icon_bytes = b"fake_icon_data"
            await system_control.notify("Test with icon", icon_bytes=icon_bytes, icon_ext="png")
            
            # Verify the call was made - the exact payload processing is tested in other tests
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "ssap://system.notifications/createToast"
            payload = call_args[0][1]
            assert payload["message"] == "Test with icon"
    
    @pytest.mark.asyncio
    async def test_launcher_command(self, system_control):
        """Test launcher command to get launch points."""
        launcher_response = {
            "returnValue": True,
            "launchPoints": [
                {
                    "id": "com.webos.app.home",
                    "title": "Home",
                    "icon": "/path/to/icon.png"
                },
                {
                    "id": "netflix",
                    "title": "Netflix",
                    "icon": "/path/to/netflix.png"
                }
            ]
        }
        response = {"type": "response", "payload": launcher_response}
        
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await system_control.launcher()
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/listLaunchPoints", None, block=True, timeout=60
            )
            assert result == launcher_response
    
    @pytest.mark.asyncio
    async def test_get_settings_command(self, system_control):
        """Test get system settings command."""
        settings_response = {
            "returnValue": True,
            "settings": {
                "country": "US",
                "language": "en-US",
                "timezone": "America/New_York"
            }
        }
        response = {"type": "response", "payload": settings_response}
        
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await system_control.get_settings()
            
            mock_request.assert_called_once_with(
                "ssap://settings/getSystemSettings", None, block=True, timeout=60
            )
            assert result == settings_response
    
    @pytest.mark.asyncio
    async def test_power_off_with_monitoring(self, system_control, mock_queue):
        """Test power_off_with_monitoring method."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock successful power off response
            initial_response = {"payload": {"returnValue": True}}
            def mock_get_response():
                if not hasattr(mock_get_response, 'called'):
                    mock_get_response.called = True
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get_response
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await system_control.power_off_with_monitoring()
                
                assert result["status"] == "succeeded"
                mock_send.assert_called_once_with(
                    'request', 'ssap://system/turnOff', {}, get_queue=True
                )
    
    @pytest.mark.asyncio
    async def test_power_off_with_monitoring_state_change(self, system_control, mock_queue):
        """Test power_off_with_monitoring with state change notification."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock responses - initial success, then power state change
            initial_response = {"payload": {"returnValue": True}}
            state_change = {"payload": {"state": "Off"}}
            mock_queue.get.side_effect = [initial_response, state_change]
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await system_control.power_off_with_monitoring(timeout=1.0)
                
                assert result["status"] == "powered_off"
                assert result["powerState"] == "Off"
    
    @pytest.mark.asyncio
    async def test_power_off_with_monitoring_timeout(self, system_control, mock_queue):
        """Test power_off_with_monitoring with timeout."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock timeout on initial response
            mock_queue.get.side_effect = asyncio.TimeoutError()
            
            result = await system_control.power_off_with_monitoring(timeout=0.1)
            
            assert result["status"] == "timeout"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_power_off_with_monitoring_failure(self, system_control, mock_queue):
        """Test power_off_with_monitoring with failure response."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock failure response
            failure_response = {"payload": {"returnValue": False, "errorText": "Power off failed"}}
            mock_queue.get.return_value = failure_response
            
            result = await system_control.power_off_with_monitoring()
            
            # Should return early on failure
            assert result["returnValue"] is False
            assert result["errorText"] == "Power off failed"
    
    @pytest.mark.asyncio
    async def test_power_on_with_monitoring(self, system_control, mock_queue):
        """Test power_on_with_monitoring method."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock successful power on response
            initial_response = {"payload": {"returnValue": True}}
            def mock_get_response():
                if not hasattr(mock_get_response, 'called'):
                    mock_get_response.called = True
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get_response
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await system_control.power_on_with_monitoring()
                
                assert result["status"] == "initiated"
                mock_send.assert_called_once_with(
                    'request', 'ssap://system/turnOn', {}, get_queue=True
                )
    
    @pytest.mark.asyncio
    async def test_power_on_with_monitoring_active_state(self, system_control, mock_queue):
        """Test power_on_with_monitoring with active state notification."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock responses - initial success, then power state change to active
            initial_response = {"payload": {"returnValue": True}}
            state_change = {"payload": {"state": "Active"}}
            mock_queue.get.side_effect = [initial_response, state_change]
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await system_control.power_on_with_monitoring(timeout=1.0)
                
                assert result["status"] == "powered_on"
                assert result["powerState"] == "Active"
    
    @pytest.mark.asyncio
    async def test_power_on_with_monitoring_timeout(self, system_control, mock_queue):
        """Test power_on_with_monitoring with timeout."""
        with patch.object(system_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock timeout on initial response
            mock_queue.get.side_effect = asyncio.TimeoutError()
            
            result = await system_control.power_on_with_monitoring(timeout=0.1)
            
            assert result["status"] == "timeout"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_command_validation_failure(self, system_control):
        """Test command execution with validation failure."""
        # Mock a response that fails validation
        failed_response = {
            "type": "response",
            "payload": {"returnValue": False, "errorText": "System error"}
        }
        
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = failed_response
            
            # This should raise an IOError due to failed validation
            with pytest.raises(IOError, match="System error"):
                await system_control.info()
    
    @pytest.mark.asyncio
    async def test_system_info_webos_version_detection(self, system_control):
        """Test that system info can be used for WebOS version detection."""
        system_info_with_version = {
            "returnValue": True,
            "product_name": "webOS TV",
            "model_name": "OLED55C1PUB",
            "sw_type": "FIRMWARE",
            "major_ver": "6",
            "minor_ver": "3", 
            "micro_ver": "1",
            "country": "US",
            "webos_version": "6.3.1",
            "device_os": "webOS 6.3.1"
        }
        response = {"type": "response", "payload": system_info_with_version}
        
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await system_control.info()
            
            # Verify we can extract WebOS version information
            assert result["major_ver"] == "6"
            assert result["minor_ver"] == "3"
            if "webos_version" in result:
                assert result["webos_version"] == "6.3.1"
            if "device_os" in result:
                assert "webOS" in result["device_os"]
    
    @pytest.mark.asyncio
    async def test_command_with_callback(self, system_control):
        """Test command execution with callback."""
        callback = AsyncMock()
        
        with patch.object(system_control, 'request') as mock_request:
            await system_control.power_off(callback=callback)
            
            # Verify request was called with callback
            call_args = mock_request.call_args
            assert 'callback' in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_command_non_blocking(self, system_control):
        """Test command execution in non-blocking mode."""
        with patch.object(system_control, 'request') as mock_request:
            await system_control.power_off(block=False)
            
            # Verify request was called without block parameter (defaults to False in request method)
            mock_request.assert_called_once_with(
                "ssap://system/turnOff", None
            )
    
    @pytest.mark.asyncio
    async def test_command_custom_timeout(self, system_control, mock_successful_response):
        """Test command execution with custom timeout."""
        with patch.object(system_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await system_control.info(timeout=30)
            
            # Verify request was called with custom timeout
            call_args = mock_request.call_args
            assert call_args.kwargs['timeout'] == 30 