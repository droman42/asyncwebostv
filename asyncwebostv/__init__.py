"""Asynchronous client for LG webOS TVs."""

from asyncwebostv.connection import WebOSClient
from asyncwebostv.controls import (
    MediaControl,
    SystemControl,
    ApplicationControl,
    TvControl,
    InputControl,
    SourceControl
)
# Import the SecureWebOSClient
try:
    from asyncwebostv.secure_connection import SecureWebOSClient, extract_certificate, verify_certificate
except ImportError:
    # SecureWebOSClient may not be available in older versions
    pass

# Export version
__version__ = "0.1.1"

__all__ = [
    "WebOSClient",
    "MediaControl",
    "SystemControl",
    "ApplicationControl",
    "TvControl",
    "InputControl",
    "SourceControl",
    "SecureWebOSClient",
    "extract_certificate",
    "verify_certificate",
]

from .client import WebOSTV, SecureWebOSTV
from .model import Application, InputSource, AudioOutputSource
from .discovery import discover

