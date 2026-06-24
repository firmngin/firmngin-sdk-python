"""Unit tests for connect-time session setup and LWT handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from firmngin import AsyncClient, ClientConfig, Event, KeysConfig, Usage
from firmngin._paths import (
    get_path_limit_exceeded,
    get_path_lwt,
    get_path_metadata_on_pending,
    get_path_near_limit,
    get_path_request_init,
    get_path_usage_response,
)
from firmngin.crypto import aes_gcm_encrypt
from firmngin.mqtt import MqttMessage

from .test_config import _valid_keys_data


def _client() -> AsyncClient:
    return AsyncClient(ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data())))


@pytest.mark.asyncio
async def test_connect_publishes_lwt_online_and_requests_init(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    published: list[tuple[str, bytes, bool]] = []
    subscribed: list[str] = []

    async def capture_publish(
        topic: str,
        payload: bytes,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        published.append((topic, payload, retain))

    async def capture_subscribe(topic: str, qos: int = 0) -> None:
        subscribed.append(topic)

    monkeypatch.setattr(client._mqtt, "connect", AsyncMock())
    monkeypatch.setattr(client._mqtt, "_connected", True, raising=False)
    monkeypatch.setattr(client._mqtt, "publish", capture_publish)
    monkeypatch.setattr(client._mqtt, "subscribe", capture_subscribe)
    monkeypatch.setattr(client, "_drain_offline_queue", AsyncMock())

    await client.connect()

    lwt_topic = get_path_lwt(client.config.keys.device_id)
    assert (lwt_topic, b"1", True) in published
    assert any(topic == get_path_request_init(client.config.keys.device_id) for topic, _, _ in published)
    assert get_path_usage_response(client.config.keys.device_id) in subscribed
    assert get_path_limit_exceeded(client.config.keys.device_id) in subscribed
    assert get_path_near_limit(client.config.keys.device_id) in subscribed
    assert get_path_metadata_on_pending(client.config.keys.device_id) in subscribed


@pytest.mark.asyncio
async def test_disconnect_publishes_lwt_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    published: list[tuple[str, bytes]] = []

    async def capture_publish(
        topic: str,
        payload: bytes,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "_connected", True, raising=False)
    monkeypatch.setattr(client._mqtt, "publish", capture_publish)
    monkeypatch.setattr(client._mqtt, "disconnect", AsyncMock())
    monkeypatch.setattr(client._http, "aclose", AsyncMock())

    await client.disconnect()

    assert published == [(get_path_lwt(client.config.keys.device_id), b"0")]


@pytest.mark.asyncio
async def test_dispatch_usage_event() -> None:
    client = _client()
    usages: list[Usage] = []
    payload = b'{"u":1,"l":10}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    @client.on(Event.USAGE)
    async def handle_usage(usage: Usage) -> None:
        usages.append(usage)

    await client._handle_message(
        MqttMessage(
            topic=get_path_near_limit(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert usages[0].used == 1
    assert usages[0].near_limit is True


@pytest.mark.asyncio
async def test_dispatch_metadata_as_raw_json_string() -> None:
    client = _client()
    received: list[str] = []
    payload = b'{"custom":"value"}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    @client.on(Event.METADATA_PENDING)
    def handle_metadata(raw_json: str) -> None:
        received.append(raw_json)

    await client._handle_message(
        MqttMessage(
            topic=get_path_metadata_on_pending(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert received == ['{"custom":"value"}']
