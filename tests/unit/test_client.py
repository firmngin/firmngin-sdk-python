"""Unit tests for the high-level event-driven client facade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import firmngin.client as client_module
from firmngin import (
    ActiveSession,
    AsyncClient,
    ClientConfig,
    Dispense,
    Entity,
    EntityCommand,
    Event,
    KeysConfig,
    Payment,
)
from firmngin._paths import (
    get_path_dispense,
    get_path_init,
    get_path_metadata_on_active_service,
    get_path_metadata_postpaid_ready,
    get_path_postpaid_ready,
    get_path_request_init,
    get_path_session_end,
    get_path_update_entities,
    get_path_update_entity,
)
from firmngin.crypto import aes_gcm_encrypt
from firmngin.exceptions import ConnectionError, ReconnectError
from firmngin.mqtt import MqttMessage

from .test_config import _valid_keys_data


def _client() -> AsyncClient:
    keys = KeysConfig.from_dict(_valid_keys_data())
    return AsyncClient(ClientConfig(keys=keys))


def _plaintext_client() -> AsyncClient:
    data = _valid_keys_data()
    data["decryptor"] = ""
    return AsyncClient(ClientConfig(keys=KeysConfig.from_dict(data)))


def test_on_registers_payment_handler_by_event_enum() -> None:
    client = _client()

    def handle_payment(_payment: Payment) -> None:
        return None

    returned = client.on(Event.PAYMENT, handle_payment)

    assert returned is handle_payment
    assert client._payment_callbacks == [handle_payment]


def test_on_registers_payment_handler_by_event_string() -> None:
    client = _client()

    def handle_payment(_payment: Payment) -> None:
        return None

    client.on("payment", handle_payment)

    assert client._payment_callbacks == [handle_payment]


def test_on_rejects_unknown_event() -> None:
    client = _client()

    with pytest.raises(ValueError, match="unknown"):
        client.on("unknown", lambda _payload: None)


def test_set_debug_toggles_logging_flag() -> None:
    client = _client()

    client.set_debug(True)
    assert client._debug is True

    client.set_debug(False)
    assert client._debug is False


def test_timestamp_millis_converts_epoch_nanoseconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("firmngin.client.time.time_ns", lambda: 1_783_652_400_123_999_999)

    assert client_module._timestamp_millis() == 1_783_652_400_123


@pytest.mark.asyncio
async def test_connect_is_silent_when_debug_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = _client()

    async def noop_connect() -> None:
        return None

    async def noop_publish(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(client._mqtt, "connect", noop_connect)
    monkeypatch.setattr(client, "_on_mqtt_connected", noop_connect)

    await client.connect()

    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_connect_prints_lifecycle_messages_when_debug_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = _client()
    client.set_debug(True)

    async def noop_connect() -> None:
        return None

    monkeypatch.setattr(client._mqtt, "connect", noop_connect)
    monkeypatch.setattr(client, "_on_mqtt_connected", noop_connect)

    await client.connect()

    output = capsys.readouterr().out

    assert "[debug] debug is active" in output
    assert "|___/" in output
    assert "The AIoT Platform" in output
    assert "[debug] starting" in output
    assert "[debug] connected to server" in output


@pytest.mark.asyncio
async def test_disconnect_prints_lifecycle_messages_when_debug_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = _client()
    client.set_debug(True)
    client._mqtt._connected = True

    async def noop_disconnect() -> None:
        client._mqtt._connected = False

    async def noop_publish(*_args: object, **_kwargs: object) -> None:
        return None

    async def noop_aclose() -> None:
        return None

    monkeypatch.setattr(client._mqtt, "disconnect", noop_disconnect)
    monkeypatch.setattr(client, "_publish_lwt", noop_publish)
    monkeypatch.setattr(client._http, "aclose", noop_aclose)

    await client.disconnect()

    output = capsys.readouterr().out

    assert "[debug] stopping" in output
    assert "[debug] stopped" in output
    assert output.count("[debug] stopping") == 1
    assert output.count("[debug] stopped") == 1


@pytest.mark.asyncio
async def test_disconnect_is_idempotent_when_debug_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = _client()
    client.set_debug(True)
    client._mqtt._connected = True

    async def noop_disconnect() -> None:
        client._mqtt._connected = False

    async def noop_publish(*_args: object, **_kwargs: object) -> None:
        return None

    async def noop_aclose() -> None:
        return None

    monkeypatch.setattr(client._mqtt, "disconnect", noop_disconnect)
    monkeypatch.setattr(client, "_publish_lwt", noop_publish)
    monkeypatch.setattr(client._http, "aclose", noop_aclose)

    await client.disconnect()
    await client.disconnect()

    output = capsys.readouterr().out

    assert output.count("[debug] stopping") == 1
    assert output.count("[debug] stopped") == 1


@pytest.mark.parametrize(
    "event,callback_attr",
    [
        (Event.PAYMENT_PENDING, "_payment_pending_callbacks"),
        (Event.PAYMENT_SUCCESS, "_payment_success_callbacks"),
        (Event.POSTPAID_READY, "_postpaid_ready_callbacks"),
        (Event.DISPENSE, "_dispense_callbacks"),
        (Event.METADATA_POSTPAID_READY, "_metadata_postpaid_ready_callbacks"),
        (Event.METADATA_ACTIVE_SERVICE, "_metadata_active_service_callbacks"),
        (Event.MERCHANT_STATUS, "_merchant_status_callbacks"),
        (Event.PIN, "_pin_callbacks"),
        (Event.DEVICE_STATUS, "_device_status_callbacks"),
        (Event.ACTIVE_SESSION, "_active_session_callbacks"),
        (Event.ERROR, "_error_callbacks"),
    ],
)
def test_on_registers_granular_events(event: Event, callback_attr: str) -> None:
    client = _client()

    def handler(_payload: object) -> None:
        return None

    client.on(event, handler)

    assert getattr(client, callback_attr) == [handler]


def test_on_entity_direct_registration_returns_original_handler() -> None:
    client = _client()
    relay = Entity(1)

    def handle_relay(_command: EntityCommand) -> None:
        return None

    returned = client.on_entity(relay, handle_relay)

    assert returned is handle_relay
    assert client._entity_callbacks["1"] == [handle_relay]


def test_on_entity_decorator_returns_original_handler() -> None:
    client = _client()
    relay = Entity(1)

    @client.on_entity(relay)
    def handle_relay(_command: EntityCommand) -> None:
        return None

    assert handle_relay.__name__ == "handle_relay"
    assert client._entity_callbacks["1"] == [handle_relay]


@pytest.mark.asyncio
async def test_on_entity_filters_commands_by_entity_key() -> None:
    client = _client()
    relay = Entity(1)
    calls: list[str] = []

    @client.on_entity(relay)
    async def handle_relay(command: EntityCommand) -> None:
        calls.append(command.value)

    await client._dispatch_entity_command("/c/dev/rs/2", "off")
    await client._dispatch_entity_command("/c/dev/rs/1", "on")

    assert calls == ["on"]


@pytest.mark.asyncio
async def test_upload_image_accepts_entity_and_file_path() -> None:
    client = _client()
    camera = Entity("camera")

    with pytest.raises(FileNotFoundError):
        await client.upload_image(camera, "snapshot.jpg")


@pytest.mark.asyncio
async def test_upload_image_rejects_empty_entity_key() -> None:
    client = _client()

    with pytest.raises(ValueError, match="entity key"):
        await client.upload_image("", "snapshot.jpg")


@pytest.mark.asyncio
async def test_push_entity_publishes_encrypted_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    published: list[tuple[str, bytes]] = []

    monkeypatch.setattr(client._mqtt, "_connected", True)
    monkeypatch.setattr("firmngin.client._timestamp_millis", lambda: 1_783_652_400_123)

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    await client.push_entity(Entity(1), True)

    assert published[0][0] == get_path_update_entity(client.config.keys.device_id)
    assert json.loads(client._crypto.decrypt(published[0][1])) == {
        "k": "1",
        "v": "1",
        "t": 1_783_652_400_123,
    }
    assert client.entity(1).to_string() == "1"


@pytest.mark.asyncio
async def test_update_entities_wraps_items_with_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client()
    published: list[tuple[str, bytes]] = []
    monkeypatch.setattr(client._mqtt, "_connected", True)
    monkeypatch.setattr("firmngin.client._timestamp_millis", lambda: 1_783_652_400_123)

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    await client.update_entities({"temperature": 25.5, "relay": True})

    assert published[0][0] == get_path_update_entities(client.config.keys.device_id)
    assert json.loads(client._crypto.decrypt(published[0][1])) == {
        "t": 1_783_652_400_123,
        "items": [
            {"k": "temperature", "v": "25.5"},
            {"k": "relay", "v": "1"},
        ],
    }


@pytest.mark.asyncio
async def test_request_init_publishes_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    published: list[tuple[str, bytes]] = []
    monkeypatch.setattr(client._mqtt, "_connected", True)
    monkeypatch.setattr("firmngin.client._timestamp_millis", lambda: 1_783_652_400_123)

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    await client.request_init()

    assert published[0][0] == get_path_request_init(client.config.keys.device_id)
    assert json.loads(client._crypto.decrypt(published[0][1])) == {"t": 1_783_652_400_123}


@pytest.mark.asyncio
async def test_end_session_publishes_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    published: list[tuple[str, bytes]] = []
    client._current_order_id = "order-1"
    client._merchant_status = "on_active_service"
    monkeypatch.setattr(client._mqtt, "_connected", True)
    monkeypatch.setattr("firmngin.client._timestamp_millis", lambda: 1_783_652_400_123)

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    assert await client.end_session() is True

    assert published[0][0] == get_path_session_end(client.config.keys.device_id)
    payload = json.loads(client._crypto.decrypt(published[0][1]))
    assert payload["oid"] == "order-1"
    assert payload["src"] == "dev"
    assert payload["mid"].isdigit()
    assert payload["t"] == 1_783_652_400_123


@pytest.mark.asyncio
async def test_push_entity_queues_when_disconnected_and_queue_enabled(tmp_path: Path) -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())
    client = AsyncClient(ClientConfig(keys=keys, queue_path=str(tmp_path / "queue")))

    await client.push_entity(Entity(1), "on")

    assert client._offline_queue is not None
    queued = await client._offline_queue.peek()
    assert queued is not None
    assert queued.topic == get_path_update_entity(client.config.keys.device_id)


@pytest.mark.asyncio
async def test_run_raises_reconnect_error_when_attempts_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = KeysConfig.from_dict(_valid_keys_data())
    client = AsyncClient(
        ClientConfig(
            keys=keys,
            reconnect_initial_delay_seconds=0.01,
            reconnect_max_delay_seconds=0.01,
            reconnect_max_attempts=1,
        )
    )

    async def fail_connect() -> None:
        raise ConnectionError("offline")

    monkeypatch.setattr(client, "connect", fail_connect)

    with pytest.raises(ReconnectError):
        await client.run()


@pytest.mark.asyncio
async def test_dispatch_init_triggers_active_session_handler() -> None:
    client = _client()
    sessions: list[ActiveSession] = []
    payload = b'{"m":"on_active_service","oid":"ord-1","vf":0}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    @client.on(Event.ACTIVE_SESSION)
    async def handle_session(session: ActiveSession) -> None:
        sessions.append(session)

    await client._handle_message(
        MqttMessage(topic=get_path_init(client.config.keys.device_id), payload=encrypted)
    )

    assert sessions[0].order_id == "ord-1"
    assert sessions[0].is_active()


@pytest.mark.asyncio
async def test_dispatch_postpaid_ready_sets_current_order_without_payment_success() -> None:
    client = _client()
    ready: list[Payment] = []
    payment_success: list[Payment] = []
    payload = b'{"it":"Charging","pc":"44000","oid":"ord-pr-1","q":1}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    client.on(Event.POSTPAID_READY, ready.append)
    client.on(Event.PAYMENT_SUCCESS, payment_success.append)

    await client._handle_message(
        MqttMessage(
            topic=get_path_postpaid_ready(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert ready[0].order_id == "ord-pr-1"
    assert ready[0].is_post_paid is True
    assert ready[0].is_pre_paid is False
    assert client._current_order_id == "ord-pr-1"
    assert payment_success == []


@pytest.mark.asyncio
async def test_dispatch_postpaid_ready_metadata_as_raw_json() -> None:
    client = _client()
    metadata: list[str] = []
    payload = b'{"relay":true}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    client.on(Event.METADATA_POSTPAID_READY, metadata.append)

    await client._handle_message(
        MqttMessage(
            topic=get_path_metadata_postpaid_ready(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert metadata == ['{"relay":true}']


@pytest.mark.asyncio
async def test_dispatch_active_service_metadata_as_raw_json() -> None:
    client = _client()
    metadata: list[str] = []
    payload = b'{"relay":"on"}'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    client.on(Event.METADATA_ACTIVE_SERVICE, metadata.append)

    await client._handle_message(
        MqttMessage(
            topic=get_path_metadata_on_active_service(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert metadata == ['{"relay":"on"}']


def test_clear_handlers_clears_postpaid_ready_handlers() -> None:
    client = _client()
    client.on(Event.POSTPAID_READY, lambda _payload: None)
    client.on(Event.METADATA_POSTPAID_READY, lambda _payload: None)
    client.on(Event.METADATA_ACTIVE_SERVICE, lambda _payload: None)

    client.clear_handlers()

    assert client._postpaid_ready_callbacks == []
    assert client._metadata_postpaid_ready_callbacks == []
    assert client._metadata_active_service_callbacks == []


@pytest.mark.asyncio
async def test_dispatch_dispense_triggers_handler() -> None:
    client = _client()
    dispensed: list[Dispense] = []
    payload = b'["sku-1","sku-2"]'
    encrypted = aes_gcm_encrypt(bytes.fromhex(client.config.keys.decryptor), payload)

    client.on(Event.DISPENSE, dispensed.append)

    await client._handle_message(
        MqttMessage(
            topic=get_path_dispense(client.config.keys.device_id),
            payload=encrypted,
        )
    )

    assert dispensed[0].skus == ["sku-1", "sku-2"]


@pytest.mark.asyncio
async def test_dispatch_decrypt_error_goes_to_error_handler() -> None:
    client = _client()
    errors: list[Exception] = []

    @client.on(Event.ERROR)
    async def handle_error(exc: Exception) -> None:
        errors.append(exc)

    await client._handle_message(
        MqttMessage(topic=get_path_init(client.config.keys.device_id), payload=b"bad")
    )

    assert errors


@pytest.mark.asyncio
async def test_plaintext_mode_handles_inbound_payload_without_decryption() -> None:
    client = _plaintext_client()
    sessions: list[ActiveSession] = []

    @client.on(Event.ACTIVE_SESSION)
    async def handle_session(session: ActiveSession) -> None:
        sessions.append(session)

    await client._handle_message(
        MqttMessage(
            topic=get_path_init(client.config.keys.device_id),
            payload=b'{"m":"on_active_service","oid":"ord-plain","vf":0}',
        )
    )

    assert sessions[0].order_id == "ord-plain"


@pytest.mark.asyncio
async def test_plaintext_mode_publishes_unencrypted_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _plaintext_client()
    published: list[tuple[str, bytes]] = []
    monkeypatch.setattr(client._mqtt, "_connected", True)
    monkeypatch.setattr("firmngin.client._timestamp_millis", lambda: 1_783_652_400_123)

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    await client.request_init()

    assert published[0][0] == get_path_request_init(client.config.keys.device_id)
    assert json.loads(published[0][1]) == {"t": 1_783_652_400_123}
