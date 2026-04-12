"""Network safety helpers for Motis Data MCP."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
    }
)
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    if ip in _CGNAT_NETWORK:
        return True
    return False


def ensure_safe_public_url(url: str) -> None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").strip().lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Only http/https URLs are allowed: {url}")
    if not hostname:
        raise ValueError(f"URL is missing a hostname: {url}")
    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Blocked internal hostname: {hostname}")

    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for hostname: {hostname}") from exc

    for family, _, _, _, sockaddr in addr_info:
        if family not in (socket.AF_INET, socket.AF_INET6):
            continue
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if _is_blocked_ip(ip):
            raise ValueError(f"Blocked private/internal address: {hostname} -> {ip_str}")


def ensure_safe_result_url(url: str) -> None:
    """Validate URLs that Motis may emit as search results.

    Search result URLs are not fetched by this validation path, so we only
    enforce scheme and hostname guards here. Actual fetches must still use
    ``ensure_safe_public_url`` before making a network request.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").strip().lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Only http/https URLs are allowed: {url}")
    if not hostname:
        raise ValueError(f"URL is missing a hostname: {url}")
    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Blocked internal hostname: {hostname}")


async def redirect_guard(response: httpx.Response) -> None:
    """Block redirect chains that jump from public URLs to private targets."""
    if response.is_redirect and response.next_request is not None:
        ensure_safe_public_url(str(response.next_request.url))
