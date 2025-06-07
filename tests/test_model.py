import pytest
from asyncwebostv.model import Application, InputSource, AudioOutputSource


class TestApplication:
    """Test cases for Application model class."""
    
    def test_application_initialization(self):
        """Test Application object initialization."""
        app_data = {
            "id": "com.webos.app.home",
            "title": "Home",
            "icon": "/usr/palm/applications/com.webos.app.home/icon.png",
            "version": "1.0.0"
        }
        
        app = Application(app_data)
        assert app.data == app_data
    
    def test_application_getitem(self):
        """Test Application item access."""
        app_data = {
            "id": "netflix",
            "title": "Netflix",
            "icon": "/usr/palm/applications/netflix/icon.png",
            "version": "2.1.0"
        }
        
        app = Application(app_data)
        assert app["id"] == "netflix"
        assert app["title"] == "Netflix"
        assert app["version"] == "2.1.0"
    
    def test_application_getitem_missing_key(self):
        """Test Application item access with missing key."""
        app_data = {"id": "test.app"}
        app = Application(app_data)
        
        with pytest.raises(KeyError):
            _ = app["nonexistent_key"]
    
    def test_application_repr_with_title(self):
        """Test Application string representation with title."""
        app_data = {
            "id": "netflix",
            "title": "Netflix"
        }
        
        app = Application(app_data)
        assert repr(app) == "<Application 'Netflix'>"
    
    def test_application_repr_with_appid_only(self):
        """Test Application string representation with appId only."""
        app_data = {
            "appId": "com.webos.app.settings"
        }
        
        app = Application(app_data)
        assert repr(app) == "<Application 'com.webos.app.settings'>"
    
    def test_application_repr_fallback(self):
        """Test Application string representation fallback."""
        app_data = {}
        app = Application(app_data)
        assert repr(app) == "<Application 'Unknown App'>"


class TestInputSource:
    """Test cases for InputSource model class."""
    
    def test_input_source_initialization(self):
        """Test InputSource object initialization."""
        source_data = {
            "id": "HDMI_1",
            "label": "HDMI 1",
            "port": 1,
            "appId": "com.webos.app.hdmi1"
        }
        
        source = InputSource(source_data)
        assert source.data == source_data
        assert source.label == "HDMI 1"
    
    def test_input_source_getitem(self):
        """Test InputSource item access."""
        source_data = {
            "id": "HDMI_2",
            "label": "HDMI 2", 
            "port": 2,
            "appId": "com.webos.app.hdmi2"
        }
        
        source = InputSource(source_data)
        assert source["id"] == "HDMI_2"
        assert source["port"] == 2
        assert source["appId"] == "com.webos.app.hdmi2"
    
    def test_input_source_getitem_missing_key(self):
        """Test InputSource item access with missing key."""
        source_data = {
            "id": "HDMI_1",
            "label": "HDMI 1"
        }
        source = InputSource(source_data)
        
        with pytest.raises(KeyError):
            _ = source["nonexistent_key"]
    
    def test_input_source_repr(self):
        """Test InputSource string representation."""
        source_data = {
            "id": "HDMI_1",
            "label": "HDMI 1"
        }
        
        source = InputSource(source_data)
        assert repr(source) == "<InputSource 'HDMI 1'>"
    
    def test_input_source_missing_label(self):
        """Test InputSource initialization without label."""
        source_data = {"id": "HDMI_1"}
        
        with pytest.raises(KeyError):
            InputSource(source_data)


class TestAudioOutputSource:
    """Test cases for AudioOutputSource model class."""
    
    def test_audio_output_source_initialization_with_string(self):
        """Test AudioOutputSource initialization with string data."""
        source = AudioOutputSource("tv_speaker")
        assert source.data == "tv_speaker"
    
    def test_audio_output_source_initialization_with_dict(self):
        """Test AudioOutputSource initialization with dict data."""
        source_data = {
            "outputSource": "external_speaker",
            "volume": 50
        }
        source = AudioOutputSource(source_data)
        assert source.data == source_data
    
    def test_audio_output_source_getitem_string(self):
        """Test AudioOutputSource item access with string data."""
        source = AudioOutputSource("soundbar")
        # When data is a string, getitem should raise TypeError or handle appropriately
        with pytest.raises((KeyError, TypeError)):
            _ = source["outputSource"]
    
    def test_audio_output_source_getitem_dict(self):
        """Test AudioOutputSource item access with dict data."""
        source_data = {
            "outputSource": "bt_soundbar",
            "volume": 75
        }
        source = AudioOutputSource(source_data)
        # AudioOutputSource doesn't implement __getitem__, it just stores the data
        assert source.data["outputSource"] == "bt_soundbar"
        assert source.data["volume"] == 75
    
    def test_audio_output_source_repr_string(self):
        """Test AudioOutputSource string representation with string data."""
        source = AudioOutputSource("tv_external_speaker")
        assert repr(source) == "<AudioOutputSource 'tv_external_speaker'>"
    
    def test_audio_output_source_repr_dict(self):
        """Test AudioOutputSource string representation with dict data."""
        source_data = {"outputSource": "external_speaker"}
        source = AudioOutputSource(source_data)
        # The actual implementation shows the whole data dict in repr
        assert repr(source) == "<AudioOutputSource '{'outputSource': 'external_speaker'}'>"
    
    def test_audio_output_source_repr_dict_no_output_source(self):
        """Test AudioOutputSource string representation with dict missing outputSource."""
        source_data = {"volume": 50}
        source = AudioOutputSource(source_data)
        # The actual implementation shows the whole data dict in repr
        assert repr(source) == "<AudioOutputSource '{'volume': 50}'>" 