"""Unit tests for Arduino-compatible AES-GCM E2EE packets."""

from __future__ import annotations

import pytest

from firmngin.crypto import NONCE_SIZE, TAG_SIZE, aes_gcm_decrypt, aes_gcm_encrypt
from firmngin.exceptions import CryptoError


def test_aes_128_gcm_encrypt_matches_known_vector() -> None:
    key = bytes.fromhex("00" * 16)
    nonce = bytes.fromhex("00" * 12)
    plaintext = bytes.fromhex("00" * 16)

    packet = aes_gcm_encrypt(key, plaintext, nonce=nonce)

    assert packet.hex() == (
        "000000000000000000000000"
        "0388dace60b6a392f328c2b971b2fe78"
        "ab6e47d42cec13bdf53a67b21257bddf"
    )


def test_aes_256_gcm_round_trip() -> None:
    key = bytes.fromhex("11" * 32)
    plaintext = b'{"state":"ok","value":42}'

    packet = aes_gcm_encrypt(key, plaintext)

    assert len(packet) == NONCE_SIZE + len(plaintext) + TAG_SIZE
    assert aes_gcm_decrypt(packet, key) == plaintext


def test_decrypt_rejects_tampered_packet() -> None:
    key = bytes.fromhex("22" * 16)
    packet = bytearray(aes_gcm_encrypt(key, b"paid"))
    packet[-1] ^= 0x01

    with pytest.raises(CryptoError, match="authentication"):
        aes_gcm_decrypt(bytes(packet), key)


@pytest.mark.parametrize("key", [b"", b"0" * 24])
def test_invalid_key_size_raises(key: bytes) -> None:
    with pytest.raises(CryptoError, match="16 or 32 bytes"):
        aes_gcm_encrypt(key, b"payload")


def test_invalid_packet_size_raises() -> None:
    with pytest.raises(CryptoError, match="nonce and tag"):
        aes_gcm_decrypt(b"too-short", bytes.fromhex("33" * 16))
