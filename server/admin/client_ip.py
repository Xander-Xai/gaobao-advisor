"""Trusted-proxy-aware client identity resolution.

Default: ignore ``X-Forwarded-For`` completely and use the direct peer address.
Only when the direct peer is inside an explicitly configured trusted proxy
network do we walk the forwarding chain from right to left and return the first
untrusted hop. Invalid forwarding values fall back to the direct peer instead of
granting a spoofable identity.
"""

from __future__ import annotations

import ipaddress
import logging
import os

from fastapi import Request

logger = logging.getLogger(__name__)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_ip(value: str) -> IPAddress | None:
    value = value.strip()
    if not value:
        return None
    if value.startswith("[") and "]" in value:
        value = value[1 : value.index("]")]
    elif value.count(":") == 1 and "." in value:
        host, _, port = value.rpartition(":")
        if port.isdigit():
            value = host
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def trusted_proxy_networks() -> tuple[IPNetwork, ...]:
    # ``TRUSTED_PROXIES`` is the generic setting for public endpoints;
    # ADMIN_TRUSTED_PROXIES remains supported for existing deployments and
    # takes precedence when both are present.
    raw = os.getenv("ADMIN_TRUSTED_PROXIES", "").strip() or os.getenv("TRUSTED_PROXIES", "").strip()
    if not raw:
        return ()
    networks: list[IPNetwork] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("ignoring invalid ADMIN_TRUSTED_PROXIES entry: %s", item)
    return tuple(networks)


def resolve_client_ip(request: Request) -> str:
    peer_raw = request.client.host if request.client else ""
    peer = _parse_ip(peer_raw)
    networks = trusted_proxy_networks()
    if peer is None:
        return peer_raw or "unknown"
    if not networks or not any(peer in network for network in networks):
        return str(peer)

    forwarded = request.headers.get("x-forwarded-for", "")
    if not forwarded:
        return str(peer)
    hops = [_parse_ip(part) for part in forwarded.split(",")]
    if any(hop is None for hop in hops):
        return str(peer)
    # Right-to-left: skip our trusted proxies; the first untrusted hop is the
    # real client. Never use the left-most value directly.
    for hop in reversed(hops):
        assert hop is not None
        if not any(hop in network for network in networks):
            return str(hop)
    return str(hops[0]) if hops else str(peer)
