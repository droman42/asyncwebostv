import socket
import asyncio
import aiohttp
from typing import Set, Optional, Union
from urllib.parse import urlparse


def read_location(resp, keyword=None):
    if not isinstance(resp, str):
        resp = resp.decode('utf-8')

    for line in resp.splitlines():
        line = line.lower()
        header = "location: "
        if line.startswith(header):
            return line[len(header):]


async def validate_location(location: str, keyword: Optional[Union[str, bytes]], timeout: float = 5) -> bool:
    """Asynchronously validate that a location is valid and contains the keyword."""
    if isinstance(keyword, str):
        keyword = keyword.encode()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(location, timeout=timeout) as response:
                content = await response.read()
                if not keyword:
                    return True
                return keyword in content
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return False


async def discover(service: str, keyword=None, hosts=False, retries=1, timeout=5, mx=3) -> Set[str]:
    """
    Asynchronously discover UPNP devices and services on the network.
    
    Args:
        service: UPNP service type to discover
        keyword: Filter results that contain this keyword in their description
        hosts: When True, return only hostnames instead of full URLs
        retries: Number of discovery attempts to make
        timeout: Timeout in seconds for each attempt
        mx: MX value in SSDP discovery message
        
    Returns:
        Set of discovered location URLs or hostnames
    """
    group = ('239.255.255.250', 1900)
    locations = set()
    seen = set()

    message = "\r\n".join([
        'M-SEARCH * HTTP/1.1',
        'HOST: {0}:{1}',
        'MAN: "ssdp:discover"',
        'ST: {st}',
        'MX: {mx}',
        '', '']).format(*group, st=service, mx=mx).encode('ascii')

    for _ in range(retries):
        # Create a datagram socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        sock.sendto(message, group)

        # Use asyncio with the socket in non-blocking mode
        sock.setblocking(False)
        
        # Set a deadline for discovery
        deadline = asyncio.get_event_loop().time() + timeout
        
        while asyncio.get_event_loop().time() < deadline:
            try:
                # Use asyncio to wait for data with a timeout
                try:
                    await asyncio.wait_for(
                        asyncio.get_event_loop().sock_recv(sock, 1024),
                        timeout=deadline - asyncio.get_event_loop().time()
                    )
                    data = sock.recv(1024)
                    location = read_location(data)
                    if location and location not in seen:
                        seen.add(location)
                        if await validate_location(location, keyword, timeout=timeout):
                            locations.add(location)
                except (asyncio.TimeoutError, BlockingIOError):
                    # No more responses or timed out
                    break
            except socket.timeout:
                # Socket timeout, break the inner loop
                break

        sock.close()

    if hosts:
        return {urlparse(x).hostname for x in locations}
    else:
        return locations


# For backwards compatibility, provide a synchronous wrapper around the async function
def discover_sync(service, keyword=None, hosts=False, retries=1, timeout=5, mx=3):
    """Synchronous wrapper for the async discover function."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(discover(service, keyword, hosts, retries, timeout, mx))
