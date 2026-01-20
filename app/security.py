"""
SSRF protection and URL validation utilities.

This module provides security features to prevent Server-Side Request Forgery attacks:
- URL scheme validation (only http/https)
- Private IP range detection and blocking
- Link-local address blocking
- IPv6 local address blocking
- Metadata endpoint blocking
- DNS resolution-based IP validation
"""

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from requests.exceptions import RequestException


# Private/reserved IP ranges as defined by various RFCs
# Complete blocking of all non-routable addresses
PRIVATE_IP_RANGES = [
    # RFC 1918 - Private Address Space
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    # RFC 3927 - Link-Local (APIPA)
    ipaddress.IPv4Network("169.254.0.0/16"),
    # RFC 5737 - Documentation Addresses (TEST-NET)
    ipaddress.IPv4Network("192.0.2.0/24"),
    ipaddress.IPv4Network("198.51.100.0/24"),
    ipaddress.IPv4Network("203.0.113.0/24"),
    # RFC 5737 - IPv4 Loopback
    ipaddress.IPv4Network("127.0.0.0/8"),
    # RFC 1700 - Reserved (former Class E)
    ipaddress.IPv4Network("240.0.0.0/4"),
    # RFC 6890 - "This" network
    ipaddress.IPv4Network("0.0.0.0/8"),
    # RFC 6598 - Carrier-Grade NAT (Shared Address Space)
    ipaddress.IPv4Network("100.64.0.0/10"),
    # RFC 2544 - Benchmark testing
    ipaddress.IPv4Network("198.18.0.0/15"),
    # RFC 5771 - Multicast (shouldn't be routable but blocking anyway)
    ipaddress.IPv4Network("224.0.0.0/4"),
    # IPv6 Loopback
    ipaddress.IPv6Network("::1/128"),
    # RFC 4291 - Link-Local Unicast
    ipaddress.IPv6Network("fe80::/10"),
    # RFC 4193 - Unique Local Addresses (ULA)
    ipaddress.IPv6Network("fc00::/7"),
    # RFC 2765 - IPv4-mapped IPv6 addresses (::ffff:x.x.x.x)
    ipaddress.IPv6Network("::ffff:0:0/96"),
    # RFC 4291 - IPv6 documentation/future use
    ipaddress.IPv6Network("2001:db8::/32"),
    # RFC 4048 - IPv6 unspecified address
    ipaddress.IPv6Network("::/128"),
]

# Blocked host patterns (metadata endpoints, etc.)
BLOCKED_HOSTS = [
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "127.0.0.2",
    "::1",
    "fe80::1",
    "169.254.169.254",  # AWS metadata
    "metadata.google.internal",  # GCP metadata
    "metadata",  # Generic metadata
    "0.0.0.0",
    "255.255.255.255",
]

# Blocked URL patterns
BLOCKED_URL_PATTERNS = [
    # File protocol attempts
    r"^file://",
    r"^data:",
    r"^javascript:",
    r"^vbscript:",
    # Internal network patterns
    r"//localhost",
    r"//127\.",
    r"//192\.168\.",
    r"//10\.",
    r"//172\.(1[6-9]|2[0-9]|3[01])\.",
    r"//169\.254\.",
]


@dataclass
class URLValidationResult:
    """Result of URL validation."""

    is_valid: bool
    error_message: Optional[str] = None
    parsed_url: Optional[str] = None
    resolved_ip: Optional[str] = None  # For DNS rebinding protection
    hostname: Optional[str] = None


def is_private_ip(ip: str) -> bool:
    """
    Check if an IP address is private/local.

    Args:
        ip: IP address string to check

    Returns:
        True if the IP is private/local, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        for network in PRIVATE_IP_RANGES:
            if ip_obj in network:
                return True
        return False
    except ValueError:
        return False


def validate_url(url: str) -> URLValidationResult:
    """
    Validate a URL for SSRF protection.

    This function performs multiple checks:
    1. URL scheme validation (only http/https allowed)
    2. URL pattern blocking (file:, data:, javascript:, etc.)
    3. Host validation (block localhost, metadata endpoints)
    4. DNS resolution and IP validation (block private IPs)

    IMPORTANT: To prevent DNS rebinding attacks, this function also
    returns the first resolved IP address. Callers should use this IP
    for navigation with Host header preservation.

    Args:
        url: The URL to validate

    Returns:
        URLValidationResult with validation status and any error message
    """
    if not url:
        return URLValidationResult(is_valid=False, error_message="URL is required")

    # Check for blocked URL patterns
    for pattern in BLOCKED_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return URLValidationResult(
                is_valid=False, error_message=f"URL blocked by pattern filter"
            )

    try:
        parsed = urlparse(url)
    except Exception:
        return URLValidationResult(is_valid=False, error_message="Invalid URL format")

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return URLValidationResult(
            is_valid=False, error_message="Only HTTP and HTTPS protocols are allowed"
        )

    # Get hostname (handle missing scheme or port)
    hostname = parsed.hostname
    if not hostname:
        return URLValidationResult(
            is_valid=False, error_message="Invalid URL: missing hostname"
        )

    # Check against blocked hosts
    hostname_lower = hostname.lower()
    for blocked in BLOCKED_HOSTS:
        if hostname_lower == blocked:
            return URLValidationResult(
                is_valid=False, error_message=f"Access to '{hostname}' is blocked"
            )

    # Resolve DNS and check IPs
    try:
        ip_addresses = resolve_dns(hostname)
        if not ip_addresses:
            return URLValidationResult(
                is_valid=False, error_message=f"Could not resolve hostname '{hostname}'"
            )

        # Check all resolved IPs for private ranges
        for ip in ip_addresses:
            if is_private_ip(ip):
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Hostname '{hostname}' resolves to private IP {ip}",
                )

        # Return first public IP for DNS rebinding protection
        # This IP should be used with Host header during navigation
        resolved_ip = ip_addresses[0]

    except socket.gaierror:
        return URLValidationResult(
            is_valid=False, error_message=f"Could not resolve hostname '{hostname}'"
        )
    except RequestException as e:
        return URLValidationResult(
            is_valid=False,
            error_message=f"DNS lookup failed for '{hostname}': {str(e)}",
        )

    return URLValidationResult(
        is_valid=True,
        parsed_url=parsed.geturl(),
        resolved_ip=resolved_ip,
        hostname=hostname,
    )


def is_internal_url(url: str) -> bool:
    """
    Check if a URL points to an internal/private address.

    This function resolves the hostname and checks if any IP is private.
    Used for validating redirect destinations and subresource requests.

    Args:
        url: The URL to check

    Returns:
        True if the URL points to an internal/private address
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True  # Assume invalid URLs are internal/blocked

        # Check blocked hosts first
        hostname_lower = hostname.lower()
        for blocked in BLOCKED_HOSTS:
            if hostname_lower == blocked:
                return True

        # Resolve and check IPs
        ip_addresses = resolve_dns(hostname)
        for ip in ip_addresses:
            if is_private_ip(ip):
                return True

        return False

    except Exception:
        return True  # Fail closed - treat resolution failures as internal

    try:
        parsed = urlparse(url)
    except Exception:
        return URLValidationResult(is_valid=False, error_message="Invalid URL format")

    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return URLValidationResult(
            is_valid=False, error_message="Only HTTP and HTTPS protocols are allowed"
        )

    # Get hostname (handle missing scheme or port)
    hostname = parsed.hostname
    if not hostname:
        return URLValidationResult(
            is_valid=False, error_message="Invalid URL: missing hostname"
        )

    # Check against blocked hosts
    hostname_lower = hostname.lower()
    for blocked in BLOCKED_HOSTS:
        if hostname_lower == blocked:
            return URLValidationResult(
                is_valid=False, error_message=f"Access to '{hostname}' is blocked"
            )

    # Resolve DNS and check IPs
    try:
        ip_addresses = resolve_dns(hostname)
        for ip in ip_addresses:
            if is_private_ip(ip):
                return URLValidationResult(
                    is_valid=False,
                    error_message=f"Hostname '{hostname}' resolves to private IP {ip}",
                )
    except socket.gaierror:
        # DNS resolution failed - could be internal hostname
        return URLValidationResult(
            is_valid=False, error_message=f"Could not resolve hostname '{hostname}'"
        )
    except RequestException as e:
        return URLValidationResult(
            is_valid=False,
            error_message=f"DNS lookup failed for '{hostname}': {str(e)}",
        )

    return URLValidationResult(is_valid=True, parsed_url=parsed.geturl())


def resolve_dns(hostname: str) -> list[str]:
    """
    Resolve a hostname to all associated IP addresses.

    Args:
        hostname: The hostname to resolve

    Returns:
        List of IP address strings (both IPv4 and IPv6)
    """
    ip_addresses = []

    # Try to resolve as IPv4
    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_INET,  # IPv4 only for now
            socket.SOCK_STREAM,
        )
        for family, _, _, _, sockaddr in results:
            ip = sockaddr[0]
            if ip not in ip_addresses:
                ip_addresses.append(ip)
    except socket.gaierror:
        pass

    # Try to resolve as IPv6
    try:
        results = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_INET6,  # IPv6
            socket.SOCK_STREAM,
        )
        for family, _, _, _, sockaddr in results:
            ip = sockaddr[0]
            if ip not in ip_addresses:
                ip_addresses.append(ip)
    except socket.gaierror:
        pass

    return ip_addresses
