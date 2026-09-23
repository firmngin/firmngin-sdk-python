"""Unit tests for internal TLS helpers."""

from __future__ import annotations

import pytest

from firmngin.config import ClientConfig, KeysConfig
from firmngin.exceptions import TLSError
from firmngin.tls import normalize_fingerprint, verify_mqtt_fingerprint


def _valid_keys_data() -> dict[str, object]:
    return {
        "device_id": "dev-1782217379-d5d1680b",
        "device_key": "key-kdxQXIXNmteivUYzzoNBT",
        "decryptor": "532b1b6c9701ef9be5b68f1d4ffd2343",
        "validation_mode": "both",
        "ca_cert": "-----BEGIN CERTIFICATE-----\nZmFrZS1jYQ==\n-----END CERTIFICATE-----\n",
        "service_ca_cert": (
            "-----BEGIN CERTIFICATE-----\nZmFrZS1zZXJ2aWNlLWNh\n-----END CERTIFICATE-----\n"
        ),
        "client_cert": "-----BEGIN CERTIFICATE-----\nZmFrZS1jbGllbnQ=\n-----END CERTIFICATE-----\n",
        "private_key": "-----BEGIN PRIVATE KEY-----\nZmFrZS1rZXk=\n-----END PRIVATE KEY-----\n",
        "fingerprint_sha256": (
            "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:"
            "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
        ),
        "firmngin_broker_addr": "192.168.100.31",
        "firmngin_broker_port": 1883,
        "firmngin_no_tls": True,
    }


def test_normalize_fingerprint_accepts_compact_hex() -> None:
    fingerprint = "aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899"

    assert normalize_fingerprint(fingerprint) == (
        "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:"
        "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
    )


def test_normalize_fingerprint_rejects_wrong_length() -> None:
    with pytest.raises(TLSError, match="fingerprint"):
        normalize_fingerprint("AA")


async def test_verify_mqtt_fingerprint_skips_plain_mqtt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("TLS fingerprint preflight must not run for plain MQTT")

    monkeypatch.setattr("firmngin.tls._fingerprint_for_host", fail_if_called)

    await verify_mqtt_fingerprint(config)
