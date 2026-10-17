"""Barreira contra SSRF: so hosts publicos podem ser buscados pelo radar.

As fontes RSS sao editaveis pelo painel; sem esta barreira, um ajuste poderia
fazer o servidor buscar metadados de nuvem ou servicos internos do cluster.
O mesmo checador roda na gravacao dos ajustes e a cada salto de redirect.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".cluster.local", ".svc")
BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata.goog", "instance-data"}


class InternalTargetError(ValueError):
    """Host que nao pode ser buscado (loopback, rede privada ou nome interno)."""


def normalize_host(value: str) -> str:
    return (value or "").strip().lower().strip("[]").rstrip(".")


def is_internal_address(address: str) -> bool:
    """Só aceita um IP literal; hostname levanta ValueError para o chamador decidir."""
    parsed = ipaddress.ip_address(address)
    return (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
        or parsed.is_unspecified
    )


def legacy_ipv4(host: str) -> str | None:
    """Formas alternativas que o glibc aceita: 127.1, 2130706433, 0x7f000001."""
    parts = host.split(".")
    if not parts or len(parts) > 4:
        return None
    value = 0
    for part in parts:
        if not part:
            return None
        try:
            if part.lower().startswith("0x"):
                chunk = int(part, 16)
            elif part.startswith("0") and part != "0":
                chunk = int(part, 8)
            else:
                chunk = int(part, 10)
        except ValueError:
            return None
        if chunk < 0 or chunk > 0xFFFFFFFF:
            return None
        value = (value << 8) + chunk
        if value > 0xFFFFFFFF:
            return None
    return str(ipaddress.IPv4Address(value))


def is_internal_host(host: str) -> bool:
    host = normalize_host(host)
    if not host or host in BLOCKED_HOSTS or host.endswith(BLOCKED_SUFFIXES):
        return True
    candidate = legacy_ipv4(host) or host
    try:
        return is_internal_address(candidate)
    except ValueError:
        return False


def resolves_internal(host: str) -> bool:
    """Resolve como o cliente HTTP vai resolver; falha de DNS nao bloqueia."""
    host = normalize_host(host)
    if not host:
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, OSError):
        return False
    return any(is_internal_address(info[4][0]) for info in infos)


def assert_public_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise InternalTargetError("use uma URL http(s)")
    host = normalize_host(parsed.hostname or "")
    if not host or is_internal_host(host) or resolves_internal(host):
        raise InternalTargetError(f"host interno nao permitido ({host or url})")
    return url
