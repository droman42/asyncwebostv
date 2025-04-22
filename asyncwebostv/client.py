from typing import Optional, Dict, Any
import logging

from .connection import WebOSClient
from .secure_connection import SecureWebOSClient

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


class SecureWebOSTV(WebOSTV):
    """WebOS TV client with SSL/TLS support."""
    
    def __init__(
        self, 
        host: str, 
        port: int = 3001,
        client_key: Optional[str] = None, 
        cert_file: Optional[str] = None,
        ssl_context: Optional[Any] = None,
        verify_ssl: bool = True,
        ssl_options: Optional[Dict[str, Any]] = None
    ):
        """Initialize the secure WebOS TV client.
        
        Args:
            host: Hostname or IP address of the TV
            port: WebSocket port, default=3001
            client_key: Optional client key for authentication
            cert_file: Path to the certificate file for SSL verification
            ssl_context: Custom SSL context, takes precedence over cert_file
            verify_ssl: Whether to verify the SSL certificate, default=True
            ssl_options: Additional SSL options to pass to the websockets library
        """
        # Don't call WebOSTV.__init__ since we need a different client instance
        self.host = host
        self.client_key = client_key
        self.client = SecureWebOSClient(
            host=host, 
            port=port,
            secure=True,  # Always use secure connection for this class
            client_key=client_key,
            cert_file=cert_file,
            ssl_context=ssl_context,
            verify_ssl=verify_ssl,
            ssl_options=ssl_options
        )
        self._power_state = None
        self._volume = None
        self._current_app = None
        self._inputs = None
        self._channels = None
        self._channel = None
        
    async def get_certificate(self, save_path=None):
        """Get the TV's SSL certificate.
        
        Args:
            save_path: Optional path to save the certificate to
            
        Returns:
            The certificate in PEM format
        """
        return await self.client.get_certificate(save_path) 