"""Exception hierarchy for the firmngin SDK.

All SDK-raised exceptions inherit from FirmnginError so callers can catch
the entire SDK's failure surface with a single ``except FirmnginError``.
Specific subclasses allow finer-grained handling.
"""

from __future__ import annotations

import re


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


def format_error(error: BaseException) -> str:
    """Return one concise user-facing message without a traceback."""
    message = str(error).strip() or type(error).__name__
    marker = " failed: "
    if message.startswith("device http ") and marker in message:
        return message.split(marker, 1)[1]

    cause = error.__cause__
    if message == "MQTT connection failed":
        errno = getattr(cause, "errno", None)
        if errno is None and cause is not None:
            match = re.search(r"\[Errno (\d+)\]", str(cause))
            errno = match.group(1) if match else None
        return f"connection failed [{errno}]" if errno is not None else "connection failed"

    if cause is not None:
        cause_message = str(cause).strip()
        if cause_message and cause_message not in message:
            return f"{message}: {cause_message}"
    return message


__all__ = [
    "AuthError",
    "ConfigError",
    "ConnectionError",
    "CryptoError",
    "FirmnginError",
    "format_error",
    "PayloadError",
    "QueueError",
    "ReconnectError",
    "TLSError",
]
