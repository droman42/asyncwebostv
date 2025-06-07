import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from asyncwebostv.controls import MediaControl, standard_validation
from asyncwebostv.model import AudioOutputSource


class TestMediaControl:
    """Test cases for MediaControl class."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock WebOSClient for testing."""
        client = MagicMock()
        client.send_message = AsyncMock()
        return client
    
    @pytest.fixture
    def media_control(self, mock_client):
        """MediaControl instance for testing."""
        return MediaControl(mock_client)
    
    def test_media_control_commands_structure(self, media_control):
        """Test that MediaControl has all expected commands."""
        expected_commands = [
            "volume_up", "volume_down", "get_volume", "set_volume",
            "get_mute", "set_mute", "get_audio_status",
            "play", "pause", "stop", "rewind", "fast_forward"
        ]
        
        for command in expected_commands:
            assert command in media_control.COMMANDS
    
    def test_list_audio_output_sources(self, media_control):
        """Test list_audio_output_sources method."""
        sources = media_control.list_audio_output_sources()
        
        assert len(sources) == 5
        assert all(isinstance(source, AudioOutputSource) for source in sources)
        
        expected_sources = [
            'tv_speaker', 'external_speaker', 'soundbar', 
            'bt_soundbar', 'tv_external_speaker'
        ]
        for i, expected in enumerate(expected_sources):
            assert sources[i].data == expected
    
    @pytest.mark.asyncio
    async def test_volume_up_command(self, media_control, mock_successful_response):
        """Test volume up command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.volume_up()
            
            mock_request.assert_called_once_with(
                "ssap://audio/volumeUp", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_volume_down_command(self, media_control, mock_successful_response):
        """Test volume down command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.volume_down()
            
            mock_request.assert_called_once_with(
                "ssap://audio/volumeDown", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_get_volume_command(self, media_control, mock_volume_info):
        """Test get volume command."""
        response = {"type": "response", "payload": mock_volume_info}
        
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await media_control.get_volume()
            
            mock_request.assert_called_once_with(
                "ssap://audio/getVolume", None, block=True, timeout=60
            )
            assert result == mock_volume_info
    
    @pytest.mark.asyncio
    async def test_set_volume_command(self, media_control, mock_successful_response):
        """Test set volume command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.set_volume(25)
            
            mock_request.assert_called_once_with(
                "ssap://audio/setVolume", {"volume": 25}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_get_mute_command(self, media_control):
        """Test get mute command."""
        audio_status = {
            "returnValue": True,
            "mute": True,
            "volume": 20
        }
        response = {"type": "response", "payload": audio_status}
        
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await media_control.get_mute()
            
            mock_request.assert_called_once_with(
                "ssap://audio/getStatus", None, block=True, timeout=60
            )
            assert result is True  # Should return just the mute value
    
    @pytest.mark.asyncio
    async def test_set_mute_command(self, media_control, mock_successful_response):
        """Test set mute command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.set_mute(True)
            
            mock_request.assert_called_once_with(
                "ssap://audio/setMute", {"mute": True}, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_get_audio_status_command(self, media_control):
        """Test get audio status command."""
        audio_status = {
            "returnValue": True,
            "mute": False,
            "volume": 15,
            "scenario": "mastervolume_tv_speaker"
        }
        response = {"type": "response", "payload": audio_status}
        
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = response
            
            result = await media_control.get_audio_status()
            
            mock_request.assert_called_once_with(
                "ssap://audio/getStatus", None, block=True, timeout=60
            )
            assert result == audio_status
    
    @pytest.mark.asyncio
    async def test_play_command(self, media_control, mock_successful_response):
        """Test play command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.play()
            
            mock_request.assert_called_once_with(
                "ssap://media.controls/play", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_pause_command(self, media_control, mock_successful_response):
        """Test pause command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.pause()
            
            mock_request.assert_called_once_with(
                "ssap://media.controls/pause", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_stop_command(self, media_control, mock_successful_response):
        """Test stop command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.stop()
            
            mock_request.assert_called_once_with(
                "ssap://media.controls/stop", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_rewind_command(self, media_control, mock_successful_response):
        """Test rewind command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.rewind()
            
            mock_request.assert_called_once_with(
                "ssap://media.controls/rewind", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_fast_forward_command(self, media_control, mock_successful_response):
        """Test fast forward command."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.fast_forward()
            
            mock_request.assert_called_once_with(
                "ssap://media.controls/fastForward", None, block=True, timeout=60
            )
    
    @pytest.mark.asyncio
    async def test_set_volume_with_monitoring(self, media_control, mock_queue, mock_volume_info):
        """Test set_volume_with_monitoring method."""
        # Mock the enhanced monitoring response
        mock_volume_info.update({"status": "changed", "volumeStatus": {"volume": 25}})
        
        with patch.object(media_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock the queue responses - return value then timeout for subsequent calls
            initial_response = {"payload": {"returnValue": True, "volume": 25}}
            def mock_get_response():
                if not hasattr(mock_get_response, 'called'):
                    mock_get_response.called = True
                    return initial_response
                else:
                    raise asyncio.TimeoutError()
            
            mock_queue.get.side_effect = mock_get_response
            
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.return_value = 0
                
                result = await media_control.set_volume_with_monitoring(25)
                
                assert result["status"] == "changing"
                # Should call send_message twice: once for setVolume, once for getVolume
                assert mock_send.call_count == 2
                # First call should be setVolume
                mock_send.assert_any_call(
                    'request', 'ssap://audio/setVolume', {'volume': 25}, get_queue=True
                )
                # Second call should be getVolume
                mock_send.assert_any_call(
                    'request', 'ssap://audio/getVolume', None, get_queue=True
                )
    
    @pytest.mark.asyncio
    async def test_set_volume_with_monitoring_timeout(self, media_control, mock_queue):
        """Test set_volume_with_monitoring with timeout."""
        with patch.object(media_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock timeout on initial response
            mock_queue.get.side_effect = asyncio.TimeoutError()
            
            result = await media_control.set_volume_with_monitoring(25, timeout=0.1)
            
            assert result["status"] == "timeout"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_set_volume_with_monitoring_failure(self, media_control, mock_queue):
        """Test set_volume_with_monitoring with failure response."""
        with patch.object(media_control.client, 'send_message') as mock_send:
            mock_send.return_value = mock_queue
            
            # Mock failure response
            failure_response = {"payload": {"returnValue": False, "errorText": "Volume error"}}
            mock_queue.get.return_value = failure_response
            
            result = await media_control.set_volume_with_monitoring(25)
            
            # Should return early on failure
            assert result["returnValue"] is False
            assert result["errorText"] == "Volume error"
    
    @pytest.mark.asyncio
    async def test_command_validation_failure(self, media_control):
        """Test command execution with validation failure."""
        # Mock a response that fails validation
        failed_response = {
            "type": "response",
            "payload": {"returnValue": False, "errorText": "Invalid volume level"}
        }
        
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = failed_response
            
            # This should raise an IOError due to failed validation
            with pytest.raises(IOError, match="Invalid volume level"):
                await media_control.set_volume(150)  # Invalid volume
    
    @pytest.mark.asyncio
    async def test_command_with_callback(self, media_control):
        """Test command execution with callback."""
        callback = AsyncMock()
        
        with patch.object(media_control, 'request') as mock_request:
            await media_control.play(callback=callback)
            
            # Verify request was called with callback
            call_args = mock_request.call_args
            assert 'callback' in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_command_non_blocking(self, media_control):
        """Test command execution in non-blocking mode."""
        with patch.object(media_control, 'request') as mock_request:
            await media_control.play(block=False)
            
            # Verify request was called without block parameter (defaults to False in request method)
            mock_request.assert_called_once_with(
                "ssap://media.controls/play", None
            )
    
    @pytest.mark.asyncio
    async def test_command_custom_timeout(self, media_control, mock_successful_response):
        """Test command execution with custom timeout."""
        with patch.object(media_control, 'request') as mock_request:
            mock_request.return_value = mock_successful_response
            
            await media_control.get_volume(timeout=30)
            
            # Verify request was called with custom timeout
            call_args = mock_request.call_args
            assert call_args.kwargs['timeout'] == 30 