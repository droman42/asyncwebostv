"""Model classes for WebOS TV entities."""
from typing import Any, Dict, Union


class Application:
    """Represents a WebOS TV application."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize the application object.
        
        Args:
            data: Application data dictionary from the TV
        """
        self.data = data

    def __getitem__(self, val: str) -> Any:
        """Get a value from the application data."""
        return self.data[val]

    def __repr__(self) -> str:
        """Return the string representation of the application."""
        title = self.data.get('title', self.data.get('appId', 'Unknown App'))
        return f"<Application '{title}'>"


class InputSource:
    """Represents an input source on the WebOS TV."""
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize the input source object.
        
        Args:
            data: Input source data dictionary from the TV
        """
        self.data = data
        self.label = data["label"]

    def __getitem__(self, val: str) -> Any:
        """Get a value from the input source data."""
        return self.data[val]

    def __repr__(self) -> str:
        """Return the string representation of the input source."""
        return f"<InputSource '{self['label']}'>"


class AudioOutputSource:
    """Represents an audio output source on the WebOS TV."""
    
    def __init__(self, data: Union[str, Dict[str, Any]]):
        """Initialize the audio output source object.
        
        Args:
            data: Audio output source data from the TV
        """
        self.data = data

    def __repr__(self) -> str:
        """Return the string representation of the audio output source."""
        return f"<AudioOutputSource '{self.data}'>"
