"""Configuration models for the Firmngin SDK."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import TypeAlias

ValidationMode: TypeAlias = Literal["ca", "pin", "both"]

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


class KeysConfig(BaseModel):
    """Device identity and cryptographic material loaded from platform keys.json."""

    device_id: str
    device_key: str
    decryptor: str
    validation_mode: ValidationMode = "both"
    ca_cert: str | None = None
    service_ca_cert: str
    client_cert: str | None = None
    private_key: str | None = None
    fingerprint_sha256: str | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> KeysConfig:
        """Load a platform-issued keys.json file."""
        with Path(path).open("r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            raise ValueError("keys.json must contain a JSON object")
        return cls.model_validate(raw)

    @classmethod
    def from_env(cls, prefix: str = "FIRMNGIN_") -> KeysConfig:
        """Load keys from environment variables using the given prefix."""
        fields = cls.model_fields
        data: dict[str, str] = {}
        for name in fields:
            env_name = f"{prefix}{name}".upper()
            value = os.environ.get(env_name)
            if value is not None:
                data[name] = value
        return cls.model_validate(data)

    @field_validator("device_id", "device_key")
    @classmethod
    def _validate_required_strings(cls, value: str, info: Any) -> str:
        return _require_non_empty(value, str(info.field_name))

    @field_validator("decryptor")
    @classmethod
    def _validate_decryptor(cls, value: str) -> str:
        try:
            key = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("decryptor must be hex-encoded") from exc
        if len(key) not in {16, 32}:
            raise ValueError("decryptor must decode to 16 or 32 bytes")
        return value.lower()

    @field_validator("ca_cert", "service_ca_cert", "client_cert")
    @classmethod
    def _validate_optional_pem(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return _validate_pem_shape(value, str(info.field_name))

    @field_validator("private_key")
    @classmethod
    def _validate_private_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _validate_pem_shape(value, "private_key")
        if "PRIVATE KEY" not in value:
            raise ValueError("private_key must be a private-key PEM block")
        return value

    @field_validator("fingerprint_sha256")
    @classmethod
    def _validate_fingerprint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper()
        if not _FINGERPRINT_RE.match(normalized):
            raise ValueError("fingerprint_sha256 must be 32 colon-separated hex bytes")
        return normalized

    @model_validator(mode="after")
    def _validate_mode_requirements(self) -> KeysConfig:
        if self.validation_mode in {"ca", "both"} and self.ca_cert is None:
            raise ValueError("ca_cert is required when validation_mode is ca or both")
        if self.validation_mode in {"pin", "both"} and self.fingerprint_sha256 is None:
            raise ValueError("fingerprint_sha256 is required when validation_mode is pin or both")
        return self

    @property
    def has_mtls_material(self) -> bool:
        """Return whether both mTLS client cert and private key are present."""
        return self.client_cert is not None and self.private_key is not None

    def require_mtls_material(self) -> None:
        """Raise if mTLS client material is incomplete."""
        if self.client_cert is None:
            raise ValueError("client_cert is required for mTLS")
        if self.private_key is None:
            raise ValueError("private_key is required for mTLS")


class ClientConfig(BaseModel):
    """Runtime configuration for FirmnginClient."""

    model_config = ConfigDict(extra="forbid")

    MQTT_SERVER: ClassVar[str] = "asia-jkt1.firmngin.dev"
    MQTT_PORT: ClassVar[int] = 58884

    keys: KeysConfig
    api_base_url: str = "https://api.firmngin.dev/api/v1"
    queue_path: str | None = None
    ntp_server: str = "pool.ntp.org"
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    keepalive_seconds: int = Field(default=60, gt=0)
    reconnect_initial_delay_seconds: float = Field(default=1.0, gt=0)
    reconnect_max_delay_seconds: float = Field(default=30.0, gt=0)
    reconnect_max_attempts: int | None = Field(default=None, gt=0)
    insecure: bool = False
    mtls: bool = True

    @field_validator("api_base_url", "ntp_server")
    @classmethod
    def _validate_strings(cls, value: str, info: Any) -> str:
        return _require_non_empty(value, str(info.field_name))

    @field_validator("queue_path")
    @classmethod
    def _validate_optional_queue_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "queue_path")

    @model_validator(mode="after")
    def _validate_tls_mode(self) -> ClientConfig:
        if self.mtls:
            self.keys.require_mtls_material()
        if self.insecure and self.mtls:
            raise ValueError("insecure cannot be enabled when mtls is true")
        if self.reconnect_initial_delay_seconds > self.reconnect_max_delay_seconds:
            raise ValueError("reconnect_initial_delay_seconds cannot exceed reconnect_max_delay_seconds")
        return self

    @property
    def mqtt_server(self) -> str:
        """Firmngin-managed MQTT broker hostname."""
        return self.MQTT_SERVER

    @property
    def mqtt_port(self) -> int:
        """Firmngin-managed MQTT broker port."""
        return self.MQTT_PORT


__all__ = ["ClientConfig", "KeysConfig", "ValidationMode"]
