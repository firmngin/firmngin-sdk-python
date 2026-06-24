"""Unit tests for the high-level event-driven client facade."""

from __future__ import annotations

from pathlib import Path

import pytest

from firmngin import (
    ActiveSession,
    ClientConfig,
    Entity,
    EntityCommand,
    Event,
    FirmnginClient,
    Init,
    KeysConfig,
    Payment,
    Verification,
)
from firmngin._paths import get_path_init, get_path_update_entity
from firmngin.crypto import aes_gcm_encrypt
from firmngin.exceptions import ConnectionError, ReconnectError
from firmngin.mqtt import MqttMessage

from .test_config import _valid_keys_data


def _client() -> FirmnginClient:
    keys = KeysConfig.model_validate(_valid_keys_data())
    return FirmnginClient(ClientConfig(keys=keys))


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


def test_typed_helper_still_registers_payment_handler() -> None:
    client = _client()

    def handle_payment(_payment: Payment) -> None:
        return None

    returned = client.on_payment(handle_payment)

    assert returned is handle_payment
    assert client._payment_callbacks == [handle_payment]


@pytest.mark.parametrize(
    "event,callback_attr",
    [
        (Event.PAYMENT_PENDING, "_payment_pending_callbacks"),
        (Event.PAYMENT_SUCCESS, "_payment_success_callbacks"),
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


def test_typed_helpers_register_granular_handlers() -> None:
    client = _client()

    def payment_handler(_payment: Payment) -> None:
        return None

    def init_handler(_init: Init) -> None:
        return None

    def merchant_status_handler(_status: str) -> None:
        return None

    def verification_handler(_verification: Verification) -> None:
        return None

    client.on_payment_pending(payment_handler)
    client.on_payment_success(payment_handler)
    client.on_merchant_status(merchant_status_handler)
    client.on_pin(verification_handler)

    assert client._payment_pending_callbacks == [payment_handler]
    assert client._payment_success_callbacks == [payment_handler]
    assert client._merchant_status_callbacks == [merchant_status_handler]
    assert client._pin_callbacks == [verification_handler]


def test_set_debug_accepts_pythonic_and_arduino_style_names() -> None:
    client = _client()

    client.set_debug(True)
    assert client._debug is True

    client.setDebug(False)
    assert client._debug is False


def test_on_entity_direct_registration_returns_original_handler() -> None:
    client = _client()
    relay = Entity(1)

    def handle_relay(_command: EntityCommand) -> None:
        return None

    returned = client.on_entity(relay, handle_relay)

    assert returned is handle_relay
    assert len(client._entity_command_callbacks) == 1


def test_on_entity_decorator_returns_original_handler() -> None:
    client = _client()
    relay = Entity(1)

    @client.on_entity(relay)
    def handle_relay(_command: EntityCommand) -> None:
        return None

    assert handle_relay.__name__ == "handle_relay"
    assert len(client._entity_command_callbacks) == 1


@pytest.mark.asyncio
async def test_on_entity_filters_commands_by_entity_key() -> None:
    client = _client()
    relay = Entity(1)
    calls: list[str] = []

    @client.on_entity(relay)
    async def handle_relay(command: EntityCommand) -> None:
        calls.append(command.value)

    callback = client._entity_command_callbacks[0]
    result = callback(EntityCommand.from_key_value("2", "off"))
    if result is not None:
        await result
    result = callback(EntityCommand.from_key_value("1", "on"))
    if result is not None:
        await result

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

    async def publish(topic: str, payload: bytes, **_kwargs: object) -> None:
        published.append((topic, payload))

    monkeypatch.setattr(client._mqtt, "publish", publish)

    await client.push_entity(Entity(1), True)

    assert published[0][0] == get_path_update_entity(client.config.keys.device_id)
    assert client.entity(1).to_string() == "1"


@pytest.mark.asyncio
async def test_push_entity_queues_when_disconnected_and_queue_enabled(tmp_path: Path) -> None:
    keys = KeysConfig.model_validate(_valid_keys_data())
    client = FirmnginClient(ClientConfig(keys=keys, queue_path=str(tmp_path / "queue")))

    await client.push_entity(Entity(1), "on")

    assert client._offline_queue is not None
    queued = await client._offline_queue.peek()
    assert queued is not None
    assert queued.topic == get_path_update_entity(client.config.keys.device_id)


@pytest.mark.asyncio
async def test_run_raises_reconnect_error_when_attempts_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys = KeysConfig.model_validate(_valid_keys_data())
    client = FirmnginClient(
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
async def test_dispatch_decrypt_error_goes_to_error_handler() -> None:
    client = _client()
    errors: list[Exception] = []

    @client.on(Event.ERROR)
    async def handle_error(exc: Exception) -> None:
        errors.append(exc)

    await client._handle_message(MqttMessage(topic=get_path_init(client.config.keys.device_id), payload=b"bad"))

    assert errors
