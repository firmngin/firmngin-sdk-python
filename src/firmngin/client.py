"""High-level Firmngin device client facade."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Any, Optional, overload

from firmngin._paths import (
    get_path_device_status,
    get_path_display_pin,
    get_path_entity_command,
    get_path_init,
    get_path_lwt,
    get_path_merchant_status,
    get_path_metadata_on_expired,
    get_path_metadata_on_pending,
    get_path_metadata_on_success,
    get_path_payment,
    get_path_ping,
    get_path_pending_payment,
    get_path_pong,
    get_path_request_init,
    get_path_session_end,
    get_path_update_entities,
    get_path_update_entity,
    get_path_verification_result,
)
from firmngin.builders import BatchState, LocationUpdate
from firmngin.config import ClientConfig
from firmngin.crypto import aes_gcm_decrypt, aes_gcm_encrypt
from firmngin.exceptions import ConnectionError, ReconnectError
from firmngin.http import DeviceHttpClient
from firmngin.logging import get_logger
from firmngin.mqtt import MqttError, MqttMessage, MqttTransport
from firmngin.payloads import (
    DeviceStatus,
    Entity,
    EntityCommand,
    EntityValue,
    Init,
    Payment,
    Verification,
    entity_key,
    entity_value,
)
from firmngin.queue import OfflineQueue
from firmngin.session import ActiveSession

PaymentCallback = Callable[[Payment], Optional[Awaitable[None]]]
InitCallback = Callable[[Init], Optional[Awaitable[None]]]
VerificationCallback = Callable[[Verification], Optional[Awaitable[None]]]
DeviceStatusCallback = Callable[[DeviceStatus], Optional[Awaitable[None]]]
EntityCommandCallback = Callable[[EntityCommand], Optional[Awaitable[None]]]
ActiveSessionCallback = Callable[[ActiveSession], Optional[Awaitable[None]]]
MerchantStatusCallback = Callable[[str], Optional[Awaitable[None]]]
ErrorCallback = Callable[[Exception], Optional[Awaitable[None]]]
EventCallback = Callable[[Any], Optional[Awaitable[None]]]
EventDecorator = Callable[[EventCallback], EventCallback]
EntityCommandDecorator = Callable[[EntityCommandCallback], EntityCommandCallback]


class Event(str, Enum):
    """High-level Firmngin device events."""

    PAYMENT = "payment"
    PAYMENT_PENDING = "payment.pending"
    PAYMENT_SUCCESS = "payment.success"
    INIT = "init"
    MERCHANT_STATUS = "merchant_status"
    VERIFICATION = "verification"
    PIN = "pin"
    DEVICE_STATUS = "device_status"
    ENTITY_COMMAND = "entity_command"
    ACTIVE_SESSION = "active_session"
    ERROR = "error"


class FirmnginClient:
    """Python-native Firmngin device client.

    Transport, encryption, and retry handling are internal implementation details.
    Public callers should interact through callbacks and device-level commands such
    as ``push_entity``.
    """

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._mqtt = MqttTransport(config)
        self._http = DeviceHttpClient(config)
        self._offline_queue = OfflineQueue(config.queue_path) if config.queue_path is not None else None
        self._stopped = False
        self._debug = False
        self._logger = get_logger()
        self._payment_callbacks: list[EventCallback] = []
        self._payment_pending_callbacks: list[EventCallback] = []
        self._payment_success_callbacks: list[EventCallback] = []
        self._init_callbacks: list[EventCallback] = []
        self._merchant_status_callbacks: list[EventCallback] = []
        self._verification_callbacks: list[EventCallback] = []
        self._pin_callbacks: list[EventCallback] = []
        self._device_status_callbacks: list[EventCallback] = []
        self._entity_command_callbacks: list[EventCallback] = []
        self._active_session_callbacks: list[EventCallback] = []
        self._error_callbacks: list[EventCallback] = []
        self._local_entity_values: dict[str, str] = {}
        self._current_order_id = ""
        self._merchant_status = ""
        self._session_end_requested = False
        self._last_session_end_at = 0.0
        self._firmware_version = "0.0.0"
        self._firmware_target_board = "PYTHON"
        self._firmware_target_model = ""
        self._last_synced_firmware_version = ""

    async def __aenter__(self) -> "FirmnginClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.disconnect()

    @overload
    def on(self, event: Event | str, callback: None = None) -> EventDecorator: ...

    @overload
    def on(self, event: Event | str, callback: EventCallback) -> EventCallback: ...

    def on(
        self,
        event: Event | str,
        callback: EventCallback | None = None,
    ) -> EventCallback | EventDecorator:
        """Register an event handler.

        This mirrors the Arduino library's event-driven style while keeping wire
        topics internal to the SDK.
        """
        normalized = Event(event)

        def register(handler: EventCallback) -> EventCallback:
            if normalized is Event.PAYMENT:
                self._payment_callbacks.append(handler)
            elif normalized is Event.PAYMENT_PENDING:
                self._payment_pending_callbacks.append(handler)
            elif normalized is Event.PAYMENT_SUCCESS:
                self._payment_success_callbacks.append(handler)
            elif normalized is Event.INIT:
                self._init_callbacks.append(handler)
            elif normalized is Event.MERCHANT_STATUS:
                self._merchant_status_callbacks.append(handler)
            elif normalized is Event.VERIFICATION:
                self._verification_callbacks.append(handler)
            elif normalized is Event.PIN:
                self._pin_callbacks.append(handler)
            elif normalized is Event.DEVICE_STATUS:
                self._device_status_callbacks.append(handler)
            elif normalized is Event.ENTITY_COMMAND:
                self._entity_command_callbacks.append(handler)
            elif normalized is Event.ACTIVE_SESSION:
                self._active_session_callbacks.append(handler)
            elif normalized is Event.ERROR:
                self._error_callbacks.append(handler)
            return handler

        if callback is None:
            return register
        return register(callback)

    def on_payment(self, callback: PaymentCallback) -> PaymentCallback:
        self._payment_callbacks.append(callback)
        return callback

    def on_payment_pending(self, callback: PaymentCallback) -> PaymentCallback:
        self._payment_pending_callbacks.append(callback)
        return callback

    def on_payment_success(self, callback: PaymentCallback) -> PaymentCallback:
        self._payment_success_callbacks.append(callback)
        return callback

    def on_init(self, callback: InitCallback) -> InitCallback:
        self._init_callbacks.append(callback)
        return callback

    def on_merchant_status(self, callback: MerchantStatusCallback) -> MerchantStatusCallback:
        self._merchant_status_callbacks.append(callback)
        return callback

    def on_verification(self, callback: VerificationCallback) -> VerificationCallback:
        self._verification_callbacks.append(callback)
        return callback

    def on_pin(self, callback: VerificationCallback) -> VerificationCallback:
        self._pin_callbacks.append(callback)
        return callback

    def on_device_status(self, callback: DeviceStatusCallback) -> DeviceStatusCallback:
        self._device_status_callbacks.append(callback)
        return callback

    def on_entity_command(self, callback: EntityCommandCallback) -> EntityCommandCallback:
        self._entity_command_callbacks.append(callback)
        return callback

    def on_active_session(self, callback: ActiveSessionCallback) -> ActiveSessionCallback:
        self._active_session_callbacks.append(callback)
        return callback

    def on_error(self, callback: ErrorCallback) -> ErrorCallback:
        self._error_callbacks.append(callback)
        return callback

    def set_debug(self, enabled: bool = True) -> None:
        """Enable or disable SDK debug logging."""
        self._debug = enabled

    def setDebug(self, enabled: bool = True) -> None:  # noqa: N802
        """Arduino-style alias for ``set_debug``."""
        self.set_debug(enabled)

    @overload
    def on_entity(
        self,
        entity: Entity | str | int,
        callback: None = None,
    ) -> EntityCommandDecorator: ...

    @overload
    def on_entity(
        self,
        entity: Entity | str | int,
        callback: EntityCommandCallback,
    ) -> EntityCommandCallback: ...

    def on_entity(
        self,
        entity: Entity | str | int,
        callback: EntityCommandCallback | None = None,
    ) -> EntityCommandCallback | EntityCommandDecorator:
        """Register a handler for commands targeting one entity.

        Can be used directly:

        ``client.on_entity(relay, handle_relay)``

        Or as a decorator:

        ``@client.on_entity(relay)``
        """
        target = entity_key(entity)

        def register(handler: EntityCommandCallback) -> EntityCommandCallback:
            async def filtered(command: EntityCommand) -> None:
                if command.key == target:
                    result = handler(command)
                    if isinstance(result, Awaitable):
                        await result

            self._entity_command_callbacks.append(filtered)
            return handler

        if callback is None:
            return register
        return register(callback)

    async def connect(self) -> None:
        self._stopped = False
        if self._offline_queue is not None:
            await self._offline_queue.setup()
        await self._mqtt.connect()
        await self._subscribe_default_topics()
        await self._mqtt.publish(get_path_lwt(self.config.keys.device_id), b"1", qos=1, retain=True)
        await self.sync_firmware_info()
        if self._offline_queue is not None:
            await self._offline_queue.drain(self._publish_encrypted_bytes)

    async def run(self) -> None:
        attempts = 0
        delay = self.config.reconnect_initial_delay_seconds
        while not self._stopped:
            try:
                if not self._mqtt.is_connected:
                    await self.connect()
                attempts = 0
                delay = self.config.reconnect_initial_delay_seconds
                async for message in self._mqtt.messages():
                    if self._stopped:
                        break
                    await self._handle_message(message)
            except asyncio.CancelledError:
                self._stopped = True
                raise
            except MqttError as exc:
                await self._handle_runtime_error(exc)
                await self._mqtt.disconnect()
                attempts += 1
                if self._reconnect_exhausted(attempts):
                    raise ReconnectError("MQTT reconnect attempts exhausted") from exc
                await self._sleep_before_reconnect(delay)
                delay = min(delay * 2, self.config.reconnect_max_delay_seconds)
            except ConnectionError as exc:
                await self._handle_runtime_error(exc)
                attempts += 1
                if self._reconnect_exhausted(attempts):
                    raise ReconnectError("MQTT reconnect attempts exhausted") from exc
                await self._sleep_before_reconnect(delay)
                delay = min(delay * 2, self.config.reconnect_max_delay_seconds)

    async def disconnect(self) -> None:
        self._stopped = True
        try:
            if self._mqtt.is_connected:
                try:
                    await self._mqtt.publish(get_path_lwt(self.config.keys.device_id), b"0", qos=1, retain=True)
                except Exception as exc:
                    await self._handle_runtime_error(exc)
        finally:
            await self._mqtt.disconnect()
            self._http.close()

    def stop(self) -> None:
        self._stopped = True

    async def push_entity(
        self,
        entity: Entity | str | int,
        value: Any,
        *,
        decimals: int | None = None,
    ) -> None:
        """Publish one entity update.

        Topic selection, serialization, encryption, queueing, and MQTT publish are
        handled inside the client implementation.
        """
        key = entity_key(entity)
        serialized_value = entity_value(value, decimals=decimals)
        self._local_entity_values[key] = serialized_value
        await self._publish_json(
            get_path_update_entity(self.config.keys.device_id),
            {"k": key, "v": serialized_value},
        )

    async def update_entities(self, entities: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Publish a batch entity update."""
        if not entities:
            raise ValueError("entities must not be empty")
        if isinstance(entities, dict):
            payload = [{"k": entity_key(key), "v": entity_value(value)} for key, value in entities.items()]
        else:
            payload = [
                {"k": entity_key(item["k"]), "v": entity_value(item["v"])}
                for item in entities
            ]
        for item in payload:
            self._local_entity_values[item["k"]] = item["v"]
        await self._publish_json(get_path_update_entities(self.config.keys.device_id), payload)

    async def upload_image(
        self,
        entity: Entity | str | int,
        image: str | Path,
    ) -> str:
        """Upload an image for an entity.

        API path, authentication headers, TLS, and multipart details are internal.
        """
        return await self._http.upload_image(entity, image)

    async def request_init(self) -> None:
        """Request the latest init state from Firmngin."""
        await self._publish_json(get_path_request_init(self.config.keys.device_id), {})

    def entity(self, entity: Entity | str | int) -> EntityValue:
        return EntityValue(self._local_entity_values.get(entity_key(entity), ""))

    async def end_session(self) -> bool:
        if self._current_order_id == "" or self._merchant_status != "on_active_service":
            return False
        now = time.monotonic()
        if self._session_end_requested or now - self._last_session_end_at < 3:
            return False
        self._last_session_end_at = now
        await self._publish_json(
            get_path_session_end(self.config.keys.device_id),
            {"oid": self._current_order_id, "src": "dev", "mid": str(int(now * 1000))},
        )
        self._session_end_requested = True
        return True

    def push_batch_entities(self) -> BatchState:
        return BatchState(self)

    def push_location(self) -> LocationUpdate:
        return LocationUpdate(self)

    async def push_location_values(
        self,
        *,
        lat: float,
        lon: float,
        accuracy: float | None = None,
        alt: float | None = None,
        speed: float | None = None,
    ) -> None:
        location = self.push_location().lat(lat).lon(lon)
        if accuracy is not None:
            location.accuracy(accuracy)
        if alt is not None:
            location.alt(alt)
        if speed is not None:
            location.speed(speed)
        await location.send()

    def set_firmware_info(
        self,
        version: str,
        target_board: str = "PYTHON",
        target_model: str = "",
    ) -> None:
        self._firmware_version = version
        self._firmware_target_board = target_board
        self._firmware_target_model = target_model

    def get_firmware_version(self) -> str:
        return self._firmware_version

    def get_firmware_target_board(self) -> str:
        return self._firmware_target_board

    def get_firmware_target_model(self) -> str:
        return self._firmware_target_model

    async def sync_firmware_info(self) -> bool:
        if not self._mqtt.is_connected:
            return False
        if self._firmware_version == self._last_synced_firmware_version:
            return True
        await self.push_entity(
            "versioning_firmware",
            json.dumps(
                {
                    "v": self._firmware_version,
                    "b": self._firmware_target_board,
                    "m": self._firmware_target_model,
                },
                separators=(",", ":"),
            ),
        )
        self._last_synced_firmware_version = self._firmware_version
        return True

    async def _subscribe_default_topics(self) -> None:
        device_id = self.config.keys.device_id
        qos_0_topics = [
            get_path_merchant_status(device_id),
            get_path_device_status(device_id),
            get_path_init(device_id),
            get_path_display_pin(device_id),
            get_path_verification_result(device_id),
            get_path_metadata_on_pending(device_id),
            get_path_metadata_on_expired(device_id),
            get_path_metadata_on_success(device_id),
            get_path_ping(device_id),
            get_path_entity_command(device_id),
        ]
        await self._mqtt.subscribe(get_path_payment(device_id), qos=1)
        await self._mqtt.subscribe(get_path_pending_payment(device_id), qos=1)
        for topic in qos_0_topics:
            await self._mqtt.subscribe(topic, qos=0)

    async def _publish_json(self, topic: str, payload: Any, *, retained: bool = False) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        encrypted = aes_gcm_encrypt(bytes.fromhex(self.config.keys.decryptor), encoded)
        if not self._mqtt.is_connected:
            if self._offline_queue is not None:
                await self._offline_queue.enqueue(topic, encrypted, retained)
                return
            raise ConnectionError("MQTT transport is not connected")
        try:
            await self._mqtt.publish(topic, encrypted, qos=1, retain=retained)
        except Exception as exc:
            if self._offline_queue is not None:
                await self._offline_queue.enqueue(topic, encrypted, retained)
                return
            raise ConnectionError("MQTT publish failed") from exc

    async def _publish_encrypted_bytes(self, topic: str, payload: bytes, retained: bool) -> None:
        await self._mqtt.publish(topic, payload, qos=1, retain=retained)

    async def _handle_message(self, message: MqttMessage) -> None:
        try:
            payload = aes_gcm_decrypt(message.payload, bytes.fromhex(self.config.keys.decryptor)).decode("utf-8")
        except Exception as exc:
            await self._handle_runtime_error(exc)
            return

        topic = message.topic
        state = topic.rsplit("/", 1)[-1]
        try:
            if "/rs/" in topic:
                await self._dispatch_entity_command(topic, payload)
                return
            if state == "pm":
                payment = Payment.from_payload(payload, is_success=True)
                if payment.is_valid:
                    self._current_order_id = payment.order_id
                    await self._dispatch_many(self._payment_callbacks, payment)
                    await self._dispatch_many(self._payment_success_callbacks, payment)
            elif state == "pp":
                payment = Payment.from_payload(payload, is_pending=True)
                if payment.is_valid:
                    await self._dispatch_many(self._payment_callbacks, payment)
                    await self._dispatch_many(self._payment_pending_callbacks, payment)
            elif state in {"dpin", "vr"}:
                verification = Verification.from_payload(payload)
                if verification.is_valid:
                    await self._dispatch_many(self._verification_callbacks, verification)
                    if state == "dpin":
                        await self._dispatch_many(self._pin_callbacks, verification)
            elif state == "ds":
                status = DeviceStatus.from_payload(payload)
                if status.is_valid:
                    self._merchant_status = status.state
                    await self._dispatch_many(self._device_status_callbacks, status)
                    await self._dispatch_many(self._merchant_status_callbacks, status.state)
            elif state == "init":
                init = Init.from_payload(payload)
                if init.is_valid:
                    self._merchant_status = init.merchant_status
                    if init.is_on_active_service and init.active_order_id:
                        self._current_order_id = init.active_order_id
                        await self._dispatch_active_session()
                    await self._dispatch_many(self._init_callbacks, init)
                    await self._dispatch_many(self._merchant_status_callbacks, init.merchant_status)
            elif state == "mi":
                await self._dispatch_many(self._merchant_status_callbacks, payload)
            elif state == "pi":
                await self._mqtt.publish(get_path_pong(self.config.keys.device_id), payload.encode("utf-8"), qos=0)
        except Exception as exc:
            await self._handle_runtime_error(exc)

    async def _dispatch_entity_command(self, topic: str, payload: str) -> None:
        key = topic.split("/rs/", 1)[1]
        command = EntityCommand.from_key_value(key, payload)
        if command.is_valid:
            self._local_entity_values[key] = payload
            await self._dispatch_many(self._entity_command_callbacks, command)

    async def _dispatch_active_session(self) -> None:
        if self._current_order_id == "" or self._merchant_status != "on_active_service":
            return
        session = ActiveSession(
            self,
            order_id=self._current_order_id,
            active=True,
            can_run=True,
        )
        await self._dispatch_many(self._active_session_callbacks, session)

    @staticmethod
    async def _dispatch_many(callbacks: list[EventCallback], payload: Any) -> None:
        for callback in list(callbacks):
            result = callback(payload)
            if isinstance(result, Awaitable):
                await result

    async def _handle_runtime_error(self, exc: Exception) -> None:
        if self._error_callbacks:
            await self._dispatch_many(self._error_callbacks, exc)
            return
        if self._debug:
            self._logger.error(
                "Firmngin runtime error",
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    def _reconnect_exhausted(self, attempts: int) -> bool:
        max_attempts = self.config.reconnect_max_attempts
        return max_attempts is not None and attempts >= max_attempts

    async def _sleep_before_reconnect(self, delay: float) -> None:
        if self._stopped:
            return
        await asyncio.sleep(delay)


__all__ = [
    "ActiveSessionCallback",
    "DeviceStatusCallback",
    "EntityCommandCallback",
    "EntityCommandDecorator",
    "Event",
    "EventCallback",
    "EventDecorator",
    "ErrorCallback",
    "FirmnginClient",
    "InitCallback",
    "MerchantStatusCallback",
    "PaymentCallback",
    "VerificationCallback",
]
