"""AES-GCM helpers for Firmngin E2EE packets."""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from firmngin.exceptions import CryptoError

NONCE_SIZE = 12
TAG_SIZE = 16
VALID_AES_KEY_SIZES = {16, 32}


def validate_aes_gcm_key(key: bytes) -> bytes:
    """Validate Arduino-compatible AES-GCM key length."""
    if len(key) not in VALID_AES_KEY_SIZES:
        raise CryptoError("AES-GCM key must be 16 or 32 bytes")
    return key


@lru_cache(maxsize=4)
def _aesgcm_for_key(key: bytes) -> AESGCM:
    return AESGCM(validate_aes_gcm_key(key))


def aes_gcm_encrypt(key: bytes, plaintext: bytes, *, nonce: bytes | None = None) -> bytes:
    """Encrypt plaintext as ``nonce[12] || ciphertext || tag[16]``.

    The optional nonce parameter exists for deterministic tests and protocol fixtures.
    Production callers should let this function generate a fresh random nonce.
    """
    validate_aes_gcm_key(key)
    packet_nonce = os.urandom(NONCE_SIZE) if nonce is None else nonce
    if len(packet_nonce) != NONCE_SIZE:
        raise CryptoError("AES-GCM nonce must be 12 bytes")
    ciphertext_with_tag = _aesgcm_for_key(key).encrypt(packet_nonce, plaintext, None)
    return packet_nonce + ciphertext_with_tag


def aes_gcm_decrypt(packet: bytes, key: bytes) -> bytes:
    """Decrypt an Arduino-compatible E2EE packet."""
    validate_aes_gcm_key(key)
    if len(packet) < NONCE_SIZE + TAG_SIZE:
        raise CryptoError("E2EE packet must contain nonce and tag")

    nonce = packet[:NONCE_SIZE]
    ciphertext_with_tag = packet[NONCE_SIZE:]
    try:
        return _aesgcm_for_key(key).decrypt(nonce, ciphertext_with_tag, None)
    except InvalidTag as exc:
        raise CryptoError("E2EE packet authentication failed") from exc


class AesGcmSession:
    """Reusable encrypt/decrypt session for one device key."""

    __slots__ = ("_key",)

    def __init__(self, key: bytes) -> None:
        self._key = validate_aes_gcm_key(key)

    def encrypt(self, plaintext: bytes, *, nonce: bytes | None = None) -> bytes:
        return aes_gcm_encrypt(self._key, plaintext, nonce=nonce)

    def decrypt(self, packet: bytes) -> bytes:
        return aes_gcm_decrypt(packet, self._key)


__all__ = [
    "NONCE_SIZE",
    "TAG_SIZE",
    "VALID_AES_KEY_SIZES",
    "AesGcmSession",
    "aes_gcm_decrypt",
    "aes_gcm_encrypt",
    "validate_aes_gcm_key",
]
