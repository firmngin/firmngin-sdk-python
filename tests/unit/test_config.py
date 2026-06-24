"""Unit tests for Firmngin SDK configuration models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from firmngin.config import ClientConfig, KeysConfig


def _valid_keys_data() -> dict[str, str]:
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
    }


def test_keys_config_loads_keys_json_example(keys_example_path: Path) -> None:
    keys = KeysConfig.from_file(keys_example_path)

    assert keys.device_id == "dev-0000000000-aaaaaaaaaa"
    assert len(keys.decryptor_key) == 16
    assert keys.validation_mode == "both"


def test_keys_config_from_file_requires_json_object(tmp_path: Path) -> None:
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        KeysConfig.from_file(path)


def test_keys_config_rejects_missing_decryptor() -> None:
    data = _valid_keys_data()
    data.pop("decryptor")

    with pytest.raises(ValueError, match="decryptor"):
        KeysConfig.from_dict(data)


@pytest.mark.parametrize(
    "decryptor",
    [
        "not-hex",
        "00",
        "00" * 24,
    ],
)
def test_keys_config_rejects_invalid_decryptor(decryptor: str) -> None:
    data = _valid_keys_data()
    data["decryptor"] = decryptor

    with pytest.raises(ValueError, match="decryptor"):
        KeysConfig.from_dict(data)


def test_keys_config_accepts_32_byte_decryptor() -> None:
    data = _valid_keys_data()
    data["decryptor"] = "11" * 32

    keys = KeysConfig.from_dict(data)

    assert keys.decryptor_key == bytes.fromhex("11" * 32)


def test_keys_config_decryptor_key_is_cached() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    assert keys.decryptor_key == bytes.fromhex(keys.decryptor)
    assert keys.decryptor_key is keys.decryptor_key


def test_pin_mode_requires_fingerprint() -> None:
    data = _valid_keys_data()
    data["validation_mode"] = "pin"
    data.pop("fingerprint_sha256")

    with pytest.raises(ValueError, match="fingerprint_sha256"):
        KeysConfig.from_dict(data)


def test_ca_mode_requires_ca_cert() -> None:
    data = _valid_keys_data()
    data["validation_mode"] = "ca"
    data.pop("ca_cert")

    with pytest.raises(ValueError, match="ca_cert"):
        KeysConfig.from_dict(data)


def test_keys_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _valid_keys_data().items():
        monkeypatch.setenv(f"FIRMNGIN_{key.upper()}", value)

    keys = KeysConfig.from_env()

    assert keys.device_id == "dev-1782217379-d5d1680b"
    assert keys.has_mtls_material


def test_client_config_requires_mtls_material_when_mtls_enabled() -> None:
    data = _valid_keys_data()
    data.pop("client_cert")
    keys = KeysConfig.from_dict(data)

    with pytest.raises(ValueError, match="client_cert"):
        ClientConfig(keys=keys)


def test_client_config_rejects_insecure_mtls() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    with pytest.raises(ValueError, match="insecure"):
        ClientConfig(keys=keys, insecure=True)


def test_client_config_uses_fixed_mqtt_broker() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    config = ClientConfig(keys=keys)

    assert config.mqtt_server == "asia-jkt1.firmngin.dev"
    assert config.mqtt_port == 58884


@pytest.mark.parametrize("field_name", ["mqtt_server", "mqtt_port"])
def test_client_config_rejects_user_supplied_mqtt_broker_fields(field_name: str) -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    with pytest.raises(TypeError):
        ClientConfig(keys=keys, **{field_name: "not-user-configurable"})


def test_client_config_from_file(tmp_path: Path) -> None:
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(_valid_keys_data()), encoding="utf-8")

    config = ClientConfig.from_file(path)

    assert config.keys.device_id == "dev-1782217379-d5d1680b"


def test_client_config_queue_path_is_optional() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    config = ClientConfig(keys=keys)

    assert config.queue_path is None


def test_client_config_has_reconnect_defaults() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    config = ClientConfig(keys=keys)

    assert config.keepalive_seconds == 60
    assert config.reconnect_initial_delay_seconds == 1.0
    assert config.reconnect_max_delay_seconds == 30.0
    assert config.reconnect_max_attempts is None


def test_client_config_rejects_invalid_reconnect_delay_order() -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())

    with pytest.raises(ValueError, match="reconnect_initial_delay_seconds"):
        ClientConfig(
            keys=keys,
            reconnect_initial_delay_seconds=10,
            reconnect_max_delay_seconds=1,
        )
