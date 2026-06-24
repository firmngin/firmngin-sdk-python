"""Configuration for the Firmngin SDK."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal, get_args

ValidationMode = Literal["ca", "pin", "both"]
_VALIDATION_MODES = set(get_args(ValidationMode))

_PEM_RE = re.compile(
    r"^-----BEGIN [A-Z ]+-----\n.+\n-----END [A-Z ]+-----\n?$",
    re.DOTALL,
)
_FINGERPRINT_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31}$")


def _require_non_empty(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _validate_pem_shape(value: str, field_name: str) -> str:
    _require_non_empty(value, field_name)
    if not _PEM_RE.match(value.strip()):
        raise ValueError(f"{field_name} must be a PEM block")
    return value


def _validate_decryptor(value: str) -> str:
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("decryptor must be hex-encoded") from exc
    if len(key) not in {16, 32}:
        raise ValueError("decryptor must decode to 16 or 32 bytes")
    return value.lower()


def _validate_fingerprint(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.upper()
    if not _FINGERPRINT_RE.match(normalized):
        raise ValueError("fingerprint_sha256 must be 32 colon-separated hex bytes")
    return normalized


@dataclass(frozen=True)
class KeysConfig:
    """Device identity and cryptographic material from platform ``keys.json``."""

    device_id: str
    device_key: str
    decryptor: str
    service_ca_cert: str
    validation_mode: ValidationMode = "both"
    ca_cert: str | None = None
    client_cert: str | None = None
    private_key: str | None = None
    fingerprint_sha256: str | None = None
    decryptor_key: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "device_id", _require_non_empty(self.device_id, "device_id"))
        object.__setattr__(self, "device_key", _require_non_empty(self.device_key, "device_key"))
        object.__setattr__(self, "decryptor", _validate_decryptor(self.decryptor))
        object.__setattr__(
            self,
            "service_ca_cert",
            _validate_pem_shape(self.service_ca_cert, "service_ca_cert"),
        )
        if self.validation_mode not in _VALIDATION_MODES:
            raise ValueError("validation_mode must be ca, pin, or both")
        if self.ca_cert is not None:
            object.__setattr__(self, "ca_cert", _validate_pem_shape(self.ca_cert, "ca_cert"))
        if self.client_cert is not None:
            object.__setattr__(
                self,
                "client_cert",
                _validate_pem_shape(self.client_cert, "client_cert"),
            )
        if self.private_key is not None:
            _validate_pem_shape(self.private_key, "private_key")
            if "PRIVATE KEY" not in self.private_key:
                raise ValueError("private_key must be a private-key PEM block")
        object.__setattr__(
            self,
            "fingerprint_sha256",
            _validate_fingerprint(self.fingerprint_sha256),
        )
        if self.validation_mode in {"ca", "both"} and self.ca_cert is None:
            raise ValueError("ca_cert is required when validation_mode is ca or both")
        if self.validation_mode in {"pin", "both"} and self.fingerprint_sha256 is None:
            raise ValueError("fingerprint_sha256 is required when validation_mode is pin or both")
        object.__setattr__(self, "decryptor_key", bytes.fromhex(self.decryptor))

    @classmethod
    def from_file(cls, path: str | Path) -> KeysConfig:
        """Load a platform-issued keys.json file."""
        with Path(path).open("r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("keys.json must contain a JSON object")
        return cls.from_dict(raw)

    @classmethod
    def from_env(cls, prefix: str = "FIRMNGIN_") -> KeysConfig:
        """Load keys from environment variables using the given prefix."""
        names = (
            "device_id",
            "device_key",
            "decryptor",
            "validation_mode",
            "ca_cert",
            "service_ca_cert",
            "client_cert",
            "private_key",
            "fingerprint_sha256",
        )
        data: dict[str, str] = {}
        for name in names:
            value = os.environ.get(f"{prefix}{name}".upper())
            if value is not None:
                data[name] = value
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeysConfig:
        """Build and validate keys from a mapping."""
        allowed = {
            "device_id",
            "device_key",
            "decryptor",
            "validation_mode",
            "ca_cert",
            "service_ca_cert",
            "client_cert",
            "private_key",
            "fingerprint_sha256",
        }
        unknown = set(data) - allowed
        if unknown:
            unknown_name = next(iter(sorted(unknown)))
            raise ValueError(f"unexpected keys field: {unknown_name}")

        required = ("device_id", "device_key", "decryptor", "service_ca_cert")
        for name in required:
            if name not in data:
                raise ValueError(f"{name} is required")

        validation_mode = data.get("validation_mode", "both")
        if not isinstance(validation_mode, str):
            raise ValueError("validation_mode must be a string")

        return cls(
            device_id=str(data["device_id"]),
            device_key=str(data["device_key"]),
            decryptor=str(data["decryptor"]),
            service_ca_cert=str(data["service_ca_cert"]),
            validation_mode=validation_mode,  # type: ignore[arg-type]
            ca_cert=None if data.get("ca_cert") is None else str(data["ca_cert"]),
            client_cert=None if data.get("client_cert") is None else str(data["client_cert"]),
            private_key=None if data.get("private_key") is None else str(data["private_key"]),
            fingerprint_sha256=(
                None if data.get("fingerprint_sha256") is None else str(data["fingerprint_sha256"])
            ),
        )

    @property
    def has_mtls_material(self) -> bool:
        return self.client_cert is not None and self.private_key is not None

    def require_mtls_material(self) -> None:
        if self.client_cert is None:
            raise ValueError("client_cert is required for mTLS")
        if self.private_key is None:
            raise ValueError("private_key is required for mTLS")


@dataclass
class ClientConfig:
    """Runtime settings for :class:`~firmngin.AsyncClient`."""

    keys: KeysConfig
    api_base_url: str = "https://api.firmngin.dev/api/v1"
    queue_path: str | None = None
    queue_max_size: int | None = 500
    queue_max_bytes: int | None = 5_242_880
    queue_drain_batch_size: int | None = 50
    max_local_entity_values: int = 256
    connect_timeout_seconds: float = 10.0
    keepalive_seconds: int = 60
    reconnect_initial_delay_seconds: float = 1.0
    reconnect_max_delay_seconds: float = 30.0
    reconnect_max_attempts: int | None = None
    insecure: bool = False
    mtls: bool = True

    MQTT_SERVER: ClassVar[str] = "asia-jkt1.firmngin.dev"
    MQTT_PORT: ClassVar[int] = 58884

    def __post_init__(self) -> None:
        self.api_base_url = _require_non_empty(self.api_base_url, "api_base_url")
        if self.queue_path is not None:
            self.queue_path = _require_non_empty(self.queue_path, "queue_path")
        for name, value in (
            ("queue_max_size", self.queue_max_size),
            ("queue_max_bytes", self.queue_max_bytes),
            ("queue_drain_batch_size", self.queue_drain_batch_size),
            ("max_local_entity_values", self.max_local_entity_values),
            ("connect_timeout_seconds", self.connect_timeout_seconds),
            ("keepalive_seconds", self.keepalive_seconds),
            ("reconnect_initial_delay_seconds", self.reconnect_initial_delay_seconds),
            ("reconnect_max_delay_seconds", self.reconnect_max_delay_seconds),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.reconnect_max_attempts is not None and self.reconnect_max_attempts <= 0:
            raise ValueError("reconnect_max_attempts must be greater than zero")
        if self.mtls:
            self.keys.require_mtls_material()
        if self.insecure and self.mtls:
            raise ValueError("insecure cannot be enabled when mtls is true")
        if self.reconnect_initial_delay_seconds > self.reconnect_max_delay_seconds:
            raise ValueError(
                "reconnect_initial_delay_seconds cannot exceed reconnect_max_delay_seconds"
            )

    @classmethod
    def from_file(cls, path: str | Path, **options: Any) -> ClientConfig:
        """Load keys from ``keys.json`` and apply optional overrides."""
        return cls(keys=KeysConfig.from_file(path), **options)

    @property
    def mqtt_server(self) -> str:
        return self.MQTT_SERVER

    @property
    def mqtt_port(self) -> int:
        return self.MQTT_PORT


__all__ = ["ClientConfig", "KeysConfig", "ValidationMode"]
