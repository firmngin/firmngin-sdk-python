"""Exception hierarchy for the firmngin SDK.

All SDK-raised exceptions inherit from FirmnginError so callers can catch
the entire SDK's failure surface with a single ``except FirmnginError``.
Specific subclasses allow finer-grained handling.
"""

from __future__ import annotations


class FirmnginError(Exception):
    """Base class for all firmngin SDK exceptions."""


# --------------------------------------------------------------------------------------
# Configuration / keys loading
# --------------------------------------------------------------------------------------
class ConfigError(FirmnginError):
    """Raised when KeysConfig or ClientConfig fails to load or validate.

    The ``field`` attribute names the offending config field when known.
    """


# --------------------------------------------------------------------------------------
# MQTT connection + transport
# --------------------------------------------------------------------------------------
class ConnectionError(FirmnginError):
    """Raised when MQTT connection cannot be established or is lost."""


class ReconnectError(ConnectionError):
    """Raised when reconnect policy is exhausted."""


class TLSError(ConnectionError):
    """Raised on TLS handshake failure, cert validation failure, or fingerprint mismatch."""


class AuthError(ConnectionError):
    """Raised on MQTT authentication failure (CONNACK return code 4 or 5)."""


# --------------------------------------------------------------------------------------
# Payload parsing
# --------------------------------------------------------------------------------------
class PayloadError(FirmnginError):
    """Raised when an incoming or outgoing payload fails to parse or serialize."""


# --------------------------------------------------------------------------------------
# Crypto / E2EE
# --------------------------------------------------------------------------------------
class CryptoError(FirmnginError):
    """Raised on encryption, decryption, or key validation failures."""


# --------------------------------------------------------------------------------------
# Offline queue
# --------------------------------------------------------------------------------------
class QueueError(FirmnginError):
    """Raised when the persistent offline queue cannot enqueue, dequeue, or drain."""


__all__ = [
    "FirmnginError",
    "ConfigError",
    "ConnectionError",
    "ReconnectError",
    "TLSError",
    "AuthError",
    "PayloadError",
    "CryptoError",
    "QueueError",
]
