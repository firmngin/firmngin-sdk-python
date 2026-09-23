"""Unit tests for the internal MQTT transport."""

from __future__ import annotations

from firmngin.config import ClientConfig, KeysConfig
from firmngin.mqtt import MqttTransport


def test_plain_mqtt_does_not_build_tls_parameters() -> None:
    keys = KeysConfig.from_dict(
        {
            "device_id": "dev-1782217379-d5d1680b",
            "device_key": "key-kdxQXIXNmteivUYzzoNBT",
            "decryptor": "532b1b6c9701ef9be5b68f1d4ffd2343",
            "validation_mode": "both",
            "ca_cert": "-----BEGIN CERTIFICATE-----\nZmFrZS1jYQ==\n-----END CERTIFICATE-----\n",
            "service_ca_cert": (
                "-----BEGIN CERTIFICATE-----\nZmFrZS1zZXJ2aWNlLWNh\n-----END CERTIFICATE-----\n"
            ),
            "client_cert": (
                "-----BEGIN CERTIFICATE-----\nZmFrZS1jbGllbnQ=\n-----END CERTIFICATE-----\n"
            ),
            "private_key": "-----BEGIN PRIVATE KEY-----\nZmFrZS1rZXk=\n-----END PRIVATE KEY-----\n",
            "fingerprint_sha256": (
                "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:"
                "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
            ),
            "firmngin_broker_addr": "192.168.100.31",
            "firmngin_broker_port": 1883,
            "firmngin_no_tls": True,
        }
    )
    transport = MqttTransport(ClientConfig(keys=keys))

    assert transport._tls_params() is None
