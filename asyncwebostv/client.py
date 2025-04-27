from typing import Optional, Dict, Any, AsyncIterator
import logging

from .connection import WebOSClient
from .secure_connection import SecureWebOSClient
from .controls import (
    MediaControl,
    SystemControl,
    ApplicationControl,
    TvControl,
    InputControl,
    SourceControl
)

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
        
        # Control objects will be initialized later
        self.media: Optional[MediaControl] = None
        self.system: Optional[SystemControl] = None
        self.application: Optional[ApplicationControl] = None
        self.tv: Optional[TvControl] = None
        self.input: Optional[InputControl] = None
        self.source: Optional[SourceControl] = None

    async def register(self, timeout: int = 60) -> str:
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
        """Connect to the TV and register to ensure all permissions are granted."""
        # First establish the connection
        logger.debug("Connecting to TV...")
        await self.client.connect()
        logger.debug("Connected to TV...")

        # Always register with the TV, even with an existing client key
        # This ensures all permissions are granted for the current session
        store: Dict[str, Any] = {}
        if self.client_key:
            store["client_key"] = self.client_key
            
        try:
            logger.info("Registering with TV using client key...")
            async for status in self.client.register(store):
                if status == WebOSClient.PROMPTED:
                    logger.info("Please accept the connection on the TV")
                elif status == WebOSClient.REGISTERED:
                    # Update client_key in case it changed
                    self.client_key = store.get("client_key")
                    logger.info("Registration successful!")
        except Exception as e:
            logger.error(f"Registration error: {e}")
            await self.client.close()
            raise
        
        # Initialize control objects
        self.media = MediaControl(self.client)
        self.system = SystemControl(self.client)
        self.application = ApplicationControl(self.client)
        self.tv = TvControl(self.client)
        self.input = InputControl(self.client)
        self.source = SourceControl(self.client)
        
        # Initialize the input connection explicitly
        # This matches PyWebOSTV's behavior of connecting input during initialization
        try:
            logger.info("Establishing connection to pointer input socket...")
            await self.input.connect_input()
            logger.info("Pointer input socket connected successfully")
        except Exception as e:
            # Don't fail the entire connection if input socket fails
            # Some operations might still work without the input socket
            logger.warning(f"Failed to connect to pointer input socket: {e}")
            logger.warning("Some remote control functions may not work correctly")
            logger.warning("Direct input service will be used as fallback for button commands")

    async def close(self) -> None:
        """Close the connection to the TV and clean up resources."""
        # Close the input control's websocket connection if it exists
        if self.input:
            try:
                await self.input.close()
            except Exception as e:
                logger.error(f"Error closing input control: {e}")
        
        # Close the main WebOS client connection
        if self.client:
            await self.client.close()

    async def __aenter__(self) -> 'WebOSTV':
        """Enter async context manager."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self.close()


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
        
        # Initialize control interfaces as None
        self.media: Optional[MediaControl] = None
        self.system: Optional[SystemControl] = None
        self.application: Optional[ApplicationControl] = None
        self.tv: Optional[TvControl] = None
        self.input: Optional[InputControl] = None
        self.source: Optional[SourceControl] = None
        
    async def get_certificate(self, save_path: Optional[str] = None) -> str:
        """Get the TV's SSL certificate.
        
        Args:
            save_path: Optional path to save the certificate to
            
        Returns:
            The certificate in PEM format
        """
        return await self.client.get_certificate(save_path) 