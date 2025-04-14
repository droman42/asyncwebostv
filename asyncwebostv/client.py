from typing import Optional, Dict, Any
import logging

from .connection import WebOSClient

logger = logging.getLogger(__name__)

class WebOSTV:
    """WebOS TV client with high-level API."""

    def __init__(self, host: str, client_key: Optional[str] = None, secure: bool = False):
        """Initialize the WebOS TV client.
        
        Args:
            host: Hostname or IP address of the TV
            client_key: Optional client key for authentication
            secure: Use secure WebSocket connection (wss://)
        """
        self.host = host
        self.client_key = client_key
        self.client = WebOSClient(host, secure=secure, client_key=client_key)
        self._power_state = None
        self._volume = None
        self._current_app = None
        self._inputs = None
        self._channels = None
        self._channel = None

    async def register(self, timeout=60) -> str:
        """Register the client with the TV.
        
        Args:
            timeout: Timeout in seconds for registration
            
        Returns:
            The client key after registration
            
        Raises:
            Exception: If registration fails
        """
        # Store to hold the client key
        store: Dict[str, Any] = {}
        
        async for status in self.client.register(store, timeout=timeout):
            if status == WebOSClient.PROMPTED:
                logger.info("Please accept connection on the TV")
            elif status == WebOSClient.REGISTERED:
                logger.info("Registration successful!")
                # Update client_key and return it
                self.client_key = store["client_key"]
                return self.client_key
                
        return self.client_key

    async def connect(self) -> None:
        """Connect to the TV and optionally register if needed."""
        await self.client.connect()
        
    async def close(self) -> None:
        """Close the connection to the TV."""
        await self.client.close() 