"""Unit tests for the firmngin exception hierarchy.

Pure-Python, no I/O. Every SDK exception must inherit from FirmnginError so
callers can ``except FirmnginError`` once for the entire SDK surface.
"""

from __future__ import annotations

import pytest

from firmngin.exceptions import (
    AuthError,
    ConfigError,
    ConnectionError,
    CryptoError,
    FirmnginError,
    PayloadError,
    QueueError,
    ReconnectError,
    TLSError,
)


@pytest.mark.parametrize(
    "exc_cls",
    [
        ConfigError,
        ConnectionError,
        ReconnectError,
        TLSError,
        AuthError,
        PayloadError,
        CryptoError,
        QueueError,
    ],
)
def test_every_exception_inherits_from_firmngin_error(exc_cls: type[Exception]) -> None:
    """All SDK exceptions must be catchable as FirmnginError."""
    assert issubclass(exc_cls, FirmnginError)


def test_tls_error_inherits_from_connection_error() -> None:
    """TLSError is a ConnectionError so callers can catch either."""
    assert issubclass(TLSError, ConnectionError)


def test_auth_error_inherits_from_connection_error() -> None:
    """AuthError is a ConnectionError so callers can catch either."""
    assert issubclass(AuthError, ConnectionError)


def test_reconnect_error_inherits_from_connection_error() -> None:
    """ReconnectError is a ConnectionError so callers can catch either."""
    assert issubclass(ReconnectError, ConnectionError)


def test_firmngin_error_does_not_inherit_from_bare_exception_unexpectedly() -> None:
    """Sanity: FirmnginError is just Exception + identity, not stdlib-special."""
    assert FirmnginError.__bases__ == (Exception,)


def test_exception_message_is_preserved() -> None:
    err = ConfigError("device_id missing")
    assert str(err) == "device_id missing"


def test_exception_can_be_raised_and_caught_as_base() -> None:
    with pytest.raises(FirmnginError):
        raise QueueError("queue write failed")
