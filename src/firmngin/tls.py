"""Internal TLS validation helpers."""

from __future__ import annotations

import asyncio
import hashlib
import socket
import ssl

from firmngin.config import ClientConfig
from firmngin.exceptions import TLSError


def normalize_fingerprint(value: str) -> str:
    """Normalize a SHA-256 fingerprint to uppercase colon-separated hex."""
    compact = value.replace(":", "").replace(" ", "").upper()
    if len(compact) != 64:
        raise TLSError("fingerprint_sha256 must contain 32 bytes")
    return ":".join(compact[index : index + 2] for index in range(0, 64, 2))


def _fingerprint_for_host(
    host: str,
    port: int,
    timeout: float,
    *,
    verify_chain: bool,
    ca_cert: str | None,
) -> str:
    if verify_chain:
        context = ssl.create_default_context(cadata=ca_cert)
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as tcp_socket:  # noqa: SIM117
        with context.wrap_socket(tcp_socket, server_hostname=host) as tls_socket:
            certificate = tls_socket.getpeercert(binary_form=True)
    if certificate is None:
        raise TLSError("server did not provide a certificate")
    digest = hashlib.sha256(certificate).hexdigest().upper()
    return ":".join(digest[index : index + 2] for index in range(0, 64, 2))


async def verify_mqtt_fingerprint(config: ClientConfig) -> None:
    """Validate the broker certificate fingerprint before connecting."""
    expected = config.keys.fingerprint_sha256
    if config.insecure or config.keys.validation_mode == "ca" or expected is None:
        return

    observed = await asyncio.to_thread(
        _fingerprint_for_host,
        config.mqtt_server,
        config.mqtt_port,
        config.connect_timeout_seconds,
        verify_chain=config.keys.validation_mode == "both",
        ca_cert=config.keys.ca_cert,
    )
    if observed != normalize_fingerprint(expected):
        raise TLSError("MQTT broker certificate fingerprint mismatch")


__all__ = ["normalize_fingerprint", "verify_mqtt_fingerprint"]
