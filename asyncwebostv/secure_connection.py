import ssl
import asyncio
import logging
import socket
import time
from typing import Optional, Dict, Any, Union
import websockets

from .connection import WebOSClient

logger = logging.getLogger(__name__)

class SecureWebOSClient(WebOSClient):
    """WebOSClient with enhanced SSL certificate handling"""

    def __init__(
        self, 
        host: str, 
        port: int = 3001, 
        secure: bool = True, 
        client_key: Optional[str] = None,
        cert_file: Optional[str] = None,
        ssl_context: Optional[ssl.SSLContext] = None,
        verify_ssl: bool = True,
        ssl_options: Optional[Dict[str, Any]] = None
    ):
        """Initialize the WebOS client with enhanced SSL options.
        
        Args:
            host: Hostname or IP address of the TV
            port: WebSocket port, default=3001
            secure: Use secure WebSocket connection, default=True
            client_key: Optional client key for authentication
            cert_file: Path to the certificate file for SSL verification
            ssl_context: Custom SSL context, takes precedence over cert_file
            verify_ssl: Whether to verify the SSL certificate, default=True
            ssl_options: Additional SSL options to pass to the websockets library
        """
        # Always call super().__init__ first to set up basic attributes
        super().__init__(host, secure=secure, client_key=client_key)
        
        # Override ws_url to use the specified port
        if secure:
            self.ws_url = f"wss://{host}:{port}/"
        else:
            self.ws_url = f"ws://{host}:3000/"  # Non-secure stays at default port
            
        # Store SSL-specific attributes
        self.cert_file = cert_file
        self.ssl_context = ssl_context
        self.verify_ssl = verify_ssl
        self.ssl_options = ssl_options or {}
        self.port = port
        self.host = host  # Store host explicitly
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create an SSL context based on the provided parameters.
        
        Returns:
            SSL context configured according to the parameters
        """
        # Use the provided SSL context if available
        if self.ssl_context:
            logger.debug("Using provided SSL context")
            return self.ssl_context
            
        # Create a new SSL context
        context = ssl.create_default_context()
        
        # Configure verification
        if not self.verify_ssl:
            logger.warning("SSL certificate verification disabled - connection not secure!")
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        elif self.cert_file:
            logger.debug(f"Using certificate file: {self.cert_file}")
            context.load_verify_locations(self.cert_file)
            
            # LG TV certificates are often self-signed and may lack proper hostnames
            # Disable hostname checking but still verify certificate
            context.check_hostname = False
            
        # Apply additional SSL options
        for key, value in self.ssl_options.items():
            if hasattr(context, key):
                setattr(context, key, value)
                logger.debug(f"Set SSL option {key}={value}")
            else:
                logger.warning(f"Ignoring unknown SSL option: {key}")
                
        return context
        
    async def connect(self):
        """Connect to the WebOS TV with SSL configuration.
        
        Attempts to establish a secure connection with retries on failure.
        
        Raises:
            ssl.SSLError: If SSL verification fails
            ConnectionError: If connection cannot be established after retries
        """
        if self._connecting:
            return
            
        self._connecting = True
        attempts = 0
        max_attempts = 3
        retry_delay = 2  # seconds
        
        try:
            while attempts < max_attempts:
                attempts += 1
                try:
                    logger.debug(f"Connection attempt {attempts}/{max_attempts} to {self.ws_url}")
                    
                    if self.ws_url.startswith("wss://"):
                        ssl_context = self._create_ssl_context()
                        self.connection = await websockets.client.connect(
                            self.ws_url, 
                            ssl=ssl_context,
                            extra_headers=[], # Empty list to avoid default headers including Origin
                            origin=None  # Explicitly set origin to None
                        )
                    else:
                        self.connection = await websockets.client.connect(
                            self.ws_url,
                            extra_headers=[], # Empty list to avoid default headers including Origin
                            origin=None  # Explicitly set origin to None
                        )
                        
                    # Start the message handling task
                    self.task = asyncio.create_task(self._handle_messages())
                    logger.info("Successfully connected to WebOS TV")
                    break
                    
                except ssl.SSLError as e:
                    # Don't retry SSL verification errors, as they likely won't resolve
                    logger.error(f"SSL verification failed: {e}")
                    if self.verify_ssl:
                        logger.info("Consider using get_certificate() to obtain the TV's certificate")
                    raise
                    
                except (websockets.exceptions.WebSocketException, 
                        ConnectionRefusedError, 
                        socket.gaierror) as e:
                    if attempts < max_attempts:
                        logger.warning(f"Connection failed: {e}. Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                    else:
                        logger.error(f"Failed to connect after {max_attempts} attempts: {e}")
                        raise ConnectionError(f"Failed to connect to WebOS TV: {e}")
        finally:
            self._connecting = False
            
    async def register(self, store, timeout=60):
        """Register the client with the TV with enhanced error handling.
        
        Args:
            store: A dict-like object that will receive the client key
            timeout: Timeout in seconds for registration
            
        Yields:
            PROMPTED when the TV shows the prompt
            REGISTERED when registration is complete
            
        Raises:
            Exception: If registration fails due to SSL or other issues
        """
        try:
            async for status in super().register(store, timeout=timeout):
                yield status
        except ssl.SSLError as e:
            logger.error(f"SSL error during registration: {e}")
            raise Exception(f"Registration failed due to SSL error: {e}")
        except Exception as e:
            logger.error(f"Error during registration: {e}")
            raise
            
    async def get_certificate(self, save_path: Optional[str] = None) -> str:
        """Connect to the TV without verification and retrieve the server's certificate.
        
        Args:
            save_path: Optional path to save the certificate to
            
        Returns:
            The certificate in PEM format
            
        Raises:
            ConnectionError: If unable to connect to the TV
            Exception: If certificate retrieval fails
        """
        # Save current settings to restore later
        original_verify = self.verify_ssl
        original_context = self.ssl_context
        
        # Create a context with verification disabled
        temp_context = ssl.create_default_context()
        temp_context.check_hostname = False
        temp_context.verify_mode = ssl.CERT_NONE
        
        try:
            # Set temporary settings
            self.verify_ssl = False
            self.ssl_context = temp_context
            
            # Connect to get the certificate
            cert_pem = await extract_certificate(self.host, self.port, save_path)
            return cert_pem
            
        finally:
            # Restore original settings
            self.verify_ssl = original_verify
            self.ssl_context = original_context

# Utility functions

async def extract_certificate(host: str, port: int = 3001, output_file: Optional[str] = None) -> str:
    """Extract SSL certificate from a WebOS TV.
    
    Args:
        host: Hostname or IP address of the TV
        port: SSL port, default=3001
        output_file: Optional path to save the certificate
        
    Returns:
        Certificate in PEM format
        
    Raises:
        ConnectionError: If unable to connect to the TV
        Exception: If certificate retrieval fails
    """
    logger.info(f"Extracting certificate from {host}:{port}")
    
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    try:
        reader, writer = await asyncio.open_connection(
            host, port, ssl=context
        )
        
        # Get the certificate
        ssl_obj = writer.get_extra_info('ssl_object')
        cert_der = ssl_obj.getpeercert(binary_form=True)
        if not cert_der:
            raise Exception("Failed to retrieve certificate")
            
        # Convert DER to PEM format
        cert_pem = ssl.DER_cert_to_PEM_cert(cert_der)
        
        # Save to file if requested
        if output_file:
            logger.info(f"Saving certificate to {output_file}")
            with open(output_file, 'w') as f:
                f.write(cert_pem)
                
        writer.close()
        await writer.wait_closed()
        
        return cert_pem
        
    except (ConnectionRefusedError, socket.gaierror) as e:
        logger.error(f"Connection failed: {e}")
        raise ConnectionError(f"Failed to connect to {host}:{port}: {e}")
    except Exception as e:
        logger.error(f"Error extracting certificate: {e}")
        raise

async def verify_certificate(cert_file: str, host: str, port: int = 3001) -> bool:
    """Verify if a certificate file matches the one currently used by the TV.
    
    Args:
        cert_file: Path to the certificate file to verify
        host: Hostname or IP address of the TV
        port: SSL port, default=3001
        
    Returns:
        True if the certificate matches, False otherwise
        
    Raises:
        FileNotFoundError: If the certificate file is not found
        ConnectionError: If unable to connect to the TV
        Exception: If verification fails
    """
    logger.info(f"Verifying certificate for {host}:{port}")
    
    # Load the certificate file
    try:
        with open(cert_file, 'r') as f:
            stored_cert = f.read()
    except FileNotFoundError:
        logger.error(f"Certificate file not found: {cert_file}")
        raise
        
    try:
        # Get the current certificate
        current_cert = await extract_certificate(host, port)
        
        # Compare certificates
        matches = current_cert.strip() == stored_cert.strip()
        logger.info(f"Certificate {'matches' if matches else 'does not match'}")
        
        return matches
        
    except Exception as e:
        logger.error(f"Certificate verification failed: {e}")
        raise 