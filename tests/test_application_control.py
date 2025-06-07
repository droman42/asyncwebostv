import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from typing import Dict, Any

from asyncwebostv.controls import ApplicationControl, standard_validation
from asyncwebostv.model import Application


class TestApplicationControl:
    """Test cases for ApplicationControl class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock WebOSClient for testing."""
        client = MagicMock()
        client.send_message = AsyncMock()
        return client
    
    @pytest.fixture
    def app_control(self, mock_client):
        """ApplicationControl instance for testing."""
        return ApplicationControl(mock_client)
    
    def test_application_control_commands_structure(self, app_control):
        """Test that ApplicationControl has all expected commands."""
        expected_commands = [
            "list_apps", "list_launcher", "get_app_status",
            "get_current", "launch", "launch_params", "close"
        ]
        
        for command in expected_commands:
            assert command in app_control.COMMANDS
    
    @pytest.mark.asyncio
    async def test_list_apps_command(self, app_control, mock_app_list):
        """Test list apps command."""
        response = {"type": "response", "payload": mock_app_list}
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await app_control.list_apps()
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/listApps", None, block=True, timeout=60
            )
            
            # Verify result is a list of Application objects
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(app, Application) for app in result)
            assert result[0]["id"] == "com.webos.app.home"
            assert result[1]["id"] == "netflix"
    
    @pytest.mark.asyncio
    async def test_list_launcher_command(self, app_control):
        """Test list launcher points command."""
        launcher_response = {
            "returnValue": True,
            "launchPoints": [
                {
                    "id": "com.webos.app.settings",
                    "title": "Settings",
                    "icon": "/path/to/settings.png"
                }
            ]
        }
        response = {"type": "response", "payload": launcher_response}
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await app_control.list_launcher()
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/listLaunchPoints", None, block=True, timeout=60
            )
            
            # Verify result is a list of Application objects
            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], Application)
            assert result[0]["id"] == "com.webos.app.settings"
    
    @pytest.mark.asyncio
    async def test_get_app_status_command(self, app_control):
        """Test get app status command."""
        status_response = {
            "returnValue": True,
            "appId": "netflix",
            "running": True,
            "visible": True
        }
        response = {"type": "response", "payload": status_response}
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await app_control.get_app_status("netflix")
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/getAppStatus",
                {"appId": "netflix"}, block=True, timeout=60
            )
            assert result == status_response
    
    @pytest.mark.asyncio
    async def test_get_current_command(self, app_control):
        """Test get current/foreground app command."""
        current_app_response = {
            "returnValue": True,
            "appId": "com.webos.app.home",
            "title": "Home",
            "version": "1.0.0"
        }
        response = {"type": "response", "payload": current_app_response}
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await app_control.get_current()
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/getForegroundAppInfo", None, block=True, timeout=60
            )
            
            # Verify result is an Application object
            assert isinstance(result, Application)
            assert result["appId"] == "com.webos.app.home"
    
    @pytest.mark.asyncio
    async def test_launch_command(self, app_control, mock_successful_response):
        """Test launch app command."""
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await app_control.launch("netflix")
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/launch",
                {"id": "netflix"}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_launch_params_command(self, app_control, mock_successful_response):
        """Test launch app with parameters command."""
        params = {"contentId": "movie123"}
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await app_control.launch_params("netflix", params)
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/launch",
                {"id": "netflix", "params": params}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_close_command(self, app_control, mock_successful_response):
        """Test close app command."""
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await app_control.close("netflix")
            
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/closeApp",
                {"id": "netflix"}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_launch_with_monitoring(self, app_control, mock_queue):
        """Test launch_with_monitoring method."""
        with patch.object(app_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock successful launch response
            initial_response = {"payload": {"returnValue": True}}
            
            # Create a counter to track calls
            call_count = 0
            async def mock_get():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await app_control.launch_with_monitoring("netflix")
                
                assert result["status"] == "launched"
                # Verify the launch call was made (there may be additional calls for get_current)
                launch_calls = [call for call in mock_send.call_args_list 
                               if 'launch' in str(call)]
                assert len(launch_calls) == 1
                assert launch_calls[0] == call(
                    'request', 'ssap://com.webos.applicationManager/launch',
                    {'id': 'netflix'}, get_queue=True
                )
    
    @pytest.mark.asyncio
    async def test_launch_with_monitoring_and_params(self, app_control, mock_queue):
        """Test launch_with_monitoring with parameters."""
        params = {"contentId": "movie123"}
        
        with patch.object(app_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock successful launch response
            initial_response = {"payload": {"returnValue": True}}
            
            # Create a counter to track calls
            call_count = 0
            async def mock_get():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await app_control.launch_with_monitoring("netflix", params)
                
                assert result["status"] == "launched"
                # Verify the launch call was made (there may be additional calls for get_current)
                launch_calls = [call for call in mock_send.call_args_list 
                               if 'launch' in str(call)]
                assert len(launch_calls) == 1
                assert launch_calls[0] == call(
                    'request', 'ssap://com.webos.applicationManager/launch',
                    {'id': 'netflix', 'params': params}, get_queue=True
                )
    
    @pytest.mark.asyncio
    async def test_launch_with_monitoring_foreground_check(self, app_control, mock_queue):
        """Test launch_with_monitoring with foreground app verification."""
        with patch.object(app_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock successful launch response
            initial_response = {"payload": {"returnValue": True}}
            
            # Create a counter to track calls
            call_count = 0
            async def mock_get():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get
            
            # Mock get_current to return the launched app
            mock_foreground_app = Application({"id": "netflix", "title": "Netflix"})
            # Add .id attribute to match how the code tries to access it
            mock_foreground_app.id = "netflix"
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                with patch.object(app_control, 'get_current') as mock_get_current:
                    mock_get_current.return_value = mock_foreground_app
                    
                    result = await app_control.launch_with_monitoring("netflix")
                    
                    assert result["status"] == "foreground"
                    assert "appInfo" in result
    
    @pytest.mark.asyncio
    async def test_launch_with_monitoring_timeout(self, app_control, mock_queue):
        """Test launch_with_monitoring with timeout."""
        with patch.object(app_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock timeout on initial response
            mock_queue.get.side_effect = asyncio.TimeoutError()
            
            result = await app_control.launch_with_monitoring("netflix", timeout=0.1)
            
            assert result["status"] == "timeout"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_launch_with_monitoring_failure(self, app_control, mock_queue):
        """Test launch_with_monitoring with failure response."""
        with patch.object(app_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock failure response
            failure_response = {"payload": {"returnValue": False, "errorText": "App not found"}}
            mock_queue.get.return_value = failure_response
            
            result = await app_control.launch_with_monitoring("invalid_app")
            
            # Should return early on failure
            assert result["returnValue"] is False
            assert result["errorText"] == "App not found"
    
    @pytest.mark.asyncio
    async def test_command_validation_failure(self, app_control):
        """Test command execution with validation failure."""
        # Mock a response that fails validation
        failed_response = {
            "type": "response",
            "payload": {"returnValue": False, "errorText": "App launch failed"}
        }
        
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = failed_response
            
            # This should raise an IOError due to failed validation
            with pytest.raises(IOError, match="App launch failed"):
                await app_control.launch("invalid_app")
    
    @pytest.mark.asyncio
    async def test_command_with_callback(self, app_control):
        """Test command execution with callback."""
        callback = AsyncMock()
        
        with patch.object(app_control, 'request') as mock_request:
            await app_control.launch("netflix", callback=callback)
            
            # Verify request was called with callback
            call_args = mock_request.call_args
            assert 'callback' in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_command_non_blocking(self, app_control):
        """Test command execution in non-blocking mode."""
        with patch.object(app_control, 'request') as mock_request:
            await app_control.launch("netflix", block=False)
            
            # Verify request was called without block parameter (defaults to False in request method)
            mock_request.assert_called_once_with(
                "ssap://com.webos.applicationManager/launch", {"id": "netflix"}
            )
    
    @pytest.mark.asyncio
    async def test_command_custom_timeout(self, app_control, mock_successful_response):
        """Test command execution with custom timeout."""
        with patch.object(app_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await app_control.get_current(timeout=30)
            
            # Verify request was called with custom timeout
            call_args = mock_request.call_args
            assert call_args.kwargs['timeout'] == 30 