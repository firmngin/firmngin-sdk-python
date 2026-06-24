"""Internal MQTT transport for Firmngin device traffic."""

from __future__ import annotations

import contextlib
import ssl
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import aiomqtt

from firmngin._paths import get_path_lwt
from firmngin._pem import TempPemFiles
from firmngin.config import ClientConfig
from firmngin.exceptions import ConnectionError
from firmngin.tls import verify_mqtt_fingerprint

MqttError = aiomqtt.MqttError


@dataclass(frozen=True)
class MqttMessage:
    """Normalized MQTT message consumed by AsyncClient."""

    topic: str
    payload: bytes


def _payload_bytes(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    if isinstance(payload, memoryview):
        return payload.tobytes()
    return str(payload).encode("utf-8")


class MqttTransport:
    """Small aiomqtt wrapper with Firmngin defaults."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._pem_files = TempPemFiles()
        self._client: Any | None = None
        self._context: Any | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if self._connected:
            return
        await verify_mqtt_fingerprint(self._config)

        kwargs: dict[str, Any] = {
            "hostname": self._config.mqtt_server,
            "port": self._config.mqtt_port,
            "username": self._config.keys.device_id,
            "password": self._config.keys.device_key,
            "identifier": self._config.keys.device_id,
            "timeout": self._config.connect_timeout_seconds,
            "keepalive": self._config.keepalive_seconds,
            "clean_session": True,
        }
        will_factory = getattr(aiomqtt, "Will", None)
        if will_factory is not None:
            kwargs["will"] = will_factory(
                get_path_lwt(self._config.keys.device_id),
                payload=b"0",
                qos=1,
                retain=True,
            )

        tls_params = self._tls_params()
        if tls_params is not None:
            kwargs["tls_params"] = tls_params
        if self._config.insecure or self._config.keys.validation_mode == "pin":
            kwargs["tls_insecure"] = True

        try:
            self._context = aiomqtt.Client(**kwargs)
            self._client = await self._context.__aenter__()
            self._connected = True
        except Exception as exc:
            self._pem_files.cleanup()
            self._context = None
            self._client = None
            raise ConnectionError("MQTT connection failed") from exc

    async def disconnect(self) -> None:
        try:
            if self._context is not None:
                with contextlib.suppress(Exception):
                    await self._context.__aexit__(None, None, None)
        finally:
            self._context = None
            self._client = None
            self._connected = False
            self._pem_files.cleanup()

    async def subscribe(self, topic: str, qos: int = 0) -> None:
        client = self._require_client()
        await client.subscribe(topic, qos=qos)

    async def publish(
        self, topic: str, payload: bytes | str, *, qos: int = 1, retain: bool = False
    ) -> None:
        client = self._require_client()
        await client.publish(topic, payload=payload, qos=qos, retain=retain)

    async def messages(self) -> AsyncIterator[MqttMessage]:
        client = self._require_client()
        async for message in client.messages:
            yield MqttMessage(topic=str(message.topic), payload=_payload_bytes(message.payload))

    def _require_client(self) -> Any:
        if self._client is None:
            raise ConnectionError("MQTT transport is not connected")
        return self._client

    def _tls_params(self) -> Any | None:
        cert_file = self._pem_files.write(self._config.keys.client_cert)
        key_file = self._pem_files.write(self._config.keys.private_key)
        if self._config.insecure:
            return aiomqtt.TLSParameters(
                certfile=cert_file,
                keyfile=key_file,
                cert_reqs=ssl.CERT_NONE,
            )
        if self._config.keys.validation_mode == "pin":
            return aiomqtt.TLSParameters(
                certfile=cert_file,
                keyfile=key_file,
                cert_reqs=ssl.CERT_NONE,
            )

        ca_file = self._pem_files.write(self._config.keys.ca_cert)
        if ca_file is None and cert_file is None and key_file is None:
            return None
        return aiomqtt.TLSParameters(
            ca_certs=ca_file,
            certfile=cert_file,
            keyfile=key_file,
            cert_reqs=ssl.CERT_REQUIRED,
        )


__all__ = ["MqttError", "MqttMessage", "MqttTransport"]
