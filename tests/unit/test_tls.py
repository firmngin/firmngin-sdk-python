"""Unit tests for internal TLS helpers."""

from __future__ import annotations

import pytest

from firmngin.exceptions import TLSError
from firmngin.tls import normalize_fingerprint


def test_normalize_fingerprint_accepts_compact_hex() -> None:
    fingerprint = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"

    assert normalize_fingerprint(fingerprint) == (
        "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:"
        "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
    )


def test_normalize_fingerprint_rejects_wrong_length() -> None:
    with pytest.raises(TLSError, match="fingerprint"):
        normalize_fingerprint("AA")
