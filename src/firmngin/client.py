"""High-level Firmngin device client facade."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Any, Optional, cast, overload

from firmngin._banner import print_startup_banner
from firmngin._paths import (
    get_path_device_status,
    get_path_display_pin,
    get_path_entity_command,
    get_path_init,
    get_path_limit_exceeded,
    get_path_lwt,
    get_path_merchant_status,
    get_path_metadata_on_expired,
    get_path_metadata_on_pending,
    get_path_metadata_on_success,
    get_path_near_limit,
    get_path_payment,
    get_path_pending_payment,
    get_path_ping,
    get_path_pong,
    get_path_request_init,
    get_path_session_end,
    get_path_update_entities,
    get_path_update_entity,
    get_path_usage_response,
    get_path_verification_result,
)
from firmngin._version import __version__
from firmngin.builders import BatchState, LocationUpdate
from firmngin.config import ClientConfig
from firmngin.crypto import AesGcmSession
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
    Usage,
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

_LWT_ONLINE = b"1"
_LWT_OFFLINE = b"0"


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
    USAGE = "usage"
    METADATA_PENDING = "metadata.pending"
    METADATA_EXPIRED = "metadata.expired"
    METADATA_SUCCESS = "metadata.success"
    ERROR = "error"


_EVENT_CALLBACK_ATTRS: dict[Event, str] = {
    Event.PAYMENT: "_payment_callbacks",
    Event.PAYMENT_PENDING: "_payment_pending_callbacks",
    Event.PAYMENT_SUCCESS: "_payment_success_callbacks",
    Event.INIT: "_init_callbacks",
    Event.MERCHANT_STATUS: "_merchant_status_callbacks",
    Event.VERIFICATION: "_verification_callbacks",
    Event.PIN: "_pin_callbacks",
    Event.DEVICE_STATUS: "_device_status_callbacks",
    Event.ENTITY_COMMAND: "_entity_command_callbacks",
    Event.ACTIVE_SESSION: "_active_session_callbacks",
    Event.USAGE: "_usage_callbacks",
    Event.METADATA_PENDING: "_metadata_pending_callbacks",
    Event.METADATA_EXPIRED: "_metadata_expired_callbacks",
    Event.METADATA_SUCCESS: "_metadata_success_callbacks",
    Event.ERROR: "_error_callbacks",
}


class AsyncClient:
    """Async Firmngin device client."""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._mqtt = MqttTransport(config)
        self._http = DeviceHttpClient(config)
        self._crypto = AesGcmSession(config.keys.decryptor_key)
        self._offline_queue = (
            OfflineQueue(
                config.queue_path,
                max_size=config.queue_max_size,
                max_bytes=config.queue_max_bytes,
            )
            if config.queue_path is not None
            else None
        )
        self._stopped = False
        self._disconnect_completed = False
        self._debug = False
        self._startup_banner_printed = False
        self._logger = get_logger()
        self._payment_callbacks: list[EventCallback] = []
        self._payment_pending_callbacks: list[EventCallback] = []
        self._payment_success_callbacks: list[EventCallback] = []
        self._init_callbacks: list[EventCallback] = []
        self._merchant_status_callbacks: list[EventCallback] = []
        self._verification_callbacks: list[EventCallback] = []
        self._pin_callbacks: list[EventCallback] = []
        self._device_status_callbacks: list[EventCallback] = []
        self._entity_command_callbacks: list[EntityCommandCallback] = []
        self._entity_callbacks: dict[str, list[EntityCommandCallback]] = {}
        self._active_session_callbacks: list[EventCallback] = []
        self._usage_callbacks: list[EventCallback] = []
        self._metadata_pending_callbacks: list[EventCallback] = []
        self._metadata_expired_callbacks: list[EventCallback] = []
        self._metadata_success_callbacks: list[EventCallback] = []
        self._error_callbacks: list[EventCallback] = []
        self._local_entity_values: OrderedDict[str, str] = OrderedDict()
        self._current_order_id = ""
        self._merchant_status = ""
        self._session_end_requested = False
        self._last_session_end_at = 0.0
        self._firmware_version = "0.0.0"
        self._firmware_target_board = "PYTHON"
        self._firmware_target_model = ""
        self._last_synced_firmware_version = ""

    async def __aenter__(self) -> AsyncClient:
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
        """Register an event handler."""
        normalized = Event(event)

        def register(handler: EventCallback) -> EventCallback:
            self._callbacks_for_event(normalized).append(handler)
            return handler

        if callback is None:
            return register
        return register(callback)

    def off(self, event: Event | str, callback: EventCallback) -> None:
        """Remove one handler registered with :meth:`on`."""
        callbacks = self._callbacks_for_event(Event(event))
        with contextlib.suppress(ValueError):
            callbacks.remove(callback)

    def off_entity(self, entity: Entity | str | int, callback: EntityCommandCallback) -> None:
        """Remove one per-entity handler registered with :meth:`on_entity`."""
        target = entity_key(entity)
        handlers = self._entity_callbacks.get(target, [])
        with contextlib.suppress(ValueError):
            handlers.remove(callback)

    def clear_handlers(self, event: Event | str | None = None) -> None:
        """Remove all handlers for one event, or every event when omitted."""
        if event is None:
            self._payment_callbacks.clear()
            self._payment_pending_callbacks.clear()
            self._payment_success_callbacks.clear()
            self._init_callbacks.clear()
            self._merchant_status_callbacks.clear()
            self._verification_callbacks.clear()
            self._pin_callbacks.clear()
            self._device_status_callbacks.clear()
            self._entity_command_callbacks.clear()
            self._entity_callbacks.clear()
            self._active_session_callbacks.clear()
            self._usage_callbacks.clear()
            self._metadata_pending_callbacks.clear()
            self._metadata_expired_callbacks.clear()
            self._metadata_success_callbacks.clear()
            self._error_callbacks.clear()
            return
        self._callbacks_for_event(Event(event)).clear()

    def set_debug(self, enabled: bool = True) -> None:
        """Enable or disable SDK debug logging."""
        self._debug = enabled

    def _debug_print(self, message: str) -> None:
        if self._debug:
            print(f"[debug] {message}")

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
        """Register a handler for commands targeting one entity."""
        target = entity_key(entity)

        def register(handler: EntityCommandCallback) -> EntityCommandCallback:
            self._entity_callbacks.setdefault(target, []).append(handler)
            return handler

        if callback is None:
            return register
        return register(callback)

    async def connect(self) -> None:
        self._stopped = False
        self._disconnect_completed = False
        if self._debug and not self._startup_banner_printed:
            self._debug_print("debug is active")
            print_startup_banner(__version__)
            self._startup_banner_printed = True
        self._debug_print("starting")
        if self._offline_queue is not None:
            await self._offline_queue.setup()
        await self._mqtt.connect()
        self._debug_print("connected to server")
        await self._on_mqtt_connected()

    async def _on_mqtt_connected(self) -> None:
        await self._subscribe_default_topics()
        await self._publish_lwt(_LWT_ONLINE)
        await self.sync_firmware_info()
        await self.request_init()
        await self._drain_offline_queue()

    async def _publish_lwt(self, status: bytes) -> None:
        await self._mqtt.publish(
            get_path_lwt(self.config.keys.device_id),
            status,
            qos=1,
            retain=True,
        )

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
                if self._stopped:
                    break
            except asyncio.CancelledError:
                self._stopped = True
                break
            except MqttError as exc:
                if self._stopped:
                    break
                await self._handle_runtime_error(exc)
                await self._mqtt.disconnect()
                attempts += 1
                if self._reconnect_exhausted(attempts):
                    raise ReconnectError("MQTT reconnect attempts exhausted") from exc
                await self._sleep_before_reconnect(delay)
                delay = min(delay * 2, self.config.reconnect_max_delay_seconds)
            except ConnectionError as exc:
                if self._stopped:
                    break
                await self._handle_runtime_error(exc)
                attempts += 1
                if self._reconnect_exhausted(attempts):
                    raise ReconnectError("MQTT reconnect attempts exhausted") from exc
                await self._sleep_before_reconnect(delay)
                delay = min(delay * 2, self.config.reconnect_max_delay_seconds)

    async def disconnect(self) -> None:
        if self._disconnect_completed:
            return
        self._stopped = True
        self._debug_print("stopping")
        try:
            if self._mqtt.is_connected:
                try:
                    await self._publish_lwt(_LWT_OFFLINE)
                except Exception as exc:
                    await self._handle_runtime_error(exc)
        finally:
            await self._mqtt.disconnect()
            await self._http.aclose()
            self._disconnect_completed = True
            self._debug_print("stopped")

    def stop(self) -> None:
        self._stopped = True

    async def push_entity(
        self,
        entity: Entity | str | int,
        value: Any,
        *,
        decimals: int | None = None,
    ) -> None:
        """Publish one entity update."""
        key = entity_key(entity)
        serialized_value = entity_value(value, decimals=decimals)
        self._remember_entity_value(key, serialized_value)
        await self._publish_json(
            get_path_update_entity(self.config.keys.device_id),
            {"k": key, "v": serialized_value},
        )

    async def update_entities(self, entities: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Publish a batch entity update."""
        if not entities:
            raise ValueError("entities must not be empty")
        if isinstance(entities, dict):
            payload = [
                {"k": entity_key(key), "v": entity_value(value)} for key, value in entities.items()
            ]
        else:
            payload = [
                {"k": entity_key(item["k"]), "v": entity_value(item["v"])} for item in entities
            ]
        for item in payload:
            self._remember_entity_value(item["k"], item["v"])
        await self._publish_json(get_path_update_entities(self.config.keys.device_id), payload)

    async def upload_image(
        self,
        entity: Entity | str | int,
        image: str | Path,
    ) -> str:
        """Upload an image for an entity."""
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

    def _callbacks_for_event(self, event: Event) -> list[EventCallback]:
        attr = _EVENT_CALLBACK_ATTRS.get(event)
        if attr is None:
            raise ValueError(f"unknown event: {event}")
        return cast(list[EventCallback], getattr(self, attr))

    def _remember_entity_value(self, key: str, value: str) -> None:
        self._local_entity_values[key] = value
        self._local_entity_values.move_to_end(key)
        limit = self.config.max_local_entity_values
        while len(self._local_entity_values) > limit:
            self._local_entity_values.popitem(last=False)

    async def _drain_offline_queue(self) -> None:
        if self._offline_queue is None:
            return
        batch = self.config.queue_drain_batch_size
        while True:
            drained = await self._offline_queue.drain(self._publish_encrypted_bytes, limit=batch)
            if drained == 0:
                return
            if batch is not None and drained < batch:
                return
            await asyncio.sleep(0)

    async def _subscribe_default_topics(self) -> None:
        device_id = self.config.keys.device_id
        qos_0_topics = [
            get_path_merchant_status(device_id),
            get_path_device_status(device_id),
            get_path_init(device_id),
            get_path_display_pin(device_id),
            get_path_verification_result(device_id),
            get_path_usage_response(device_id),
            get_path_limit_exceeded(device_id),
            get_path_near_limit(device_id),
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
        encrypted = self._crypto.encrypt(encoded)
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

    async def _handle_message(self, message: MqttMessage) -> None:  # noqa: PLR0912
        topic = message.topic
        state = topic.rsplit("/", 1)[-1]

        try:
            payload = self._crypto.decrypt(message.payload).decode("utf-8")
        except Exception as exc:
            await self._handle_runtime_error(exc)
            return

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
                await self._mqtt.publish(
                    get_path_pong(self.config.keys.device_id), payload.encode("utf-8"), qos=0
                )
            elif state in {"ur", "le", "nl"}:
                usage = Usage.from_payload(
                    payload,
                    near_limit=state == "nl",
                    limit_exceeded=state == "le",
                )
                if usage.is_valid:
                    await self._dispatch_many(self._usage_callbacks, usage)
            elif state == "mop":
                await self._dispatch_many(self._metadata_pending_callbacks, payload)
            elif state == "moe":
                await self._dispatch_many(self._metadata_expired_callbacks, payload)
            elif state == "mos":
                await self._dispatch_many(self._metadata_success_callbacks, payload)
        except Exception as exc:
            await self._handle_runtime_error(exc)

    async def _dispatch_entity_command(self, topic: str, payload: str) -> None:
        key = topic.split("/rs/", 1)[1]
        command = EntityCommand.from_key_value(key, payload)
        if not command.is_valid:
            return
        self._remember_entity_value(key, payload)
        await self._dispatch_many(self._entity_callbacks.get(key, []), command)
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
        if not callbacks:
            return
        snapshot = list(callbacks)

        async def run_one(callback: EventCallback) -> None:
            result = callback(payload)
            if isinstance(result, Awaitable):
                await result

        await asyncio.gather(*(run_one(callback) for callback in snapshot))

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
        remaining = delay
        while remaining > 0 and not self._stopped:
            step = min(remaining, 0.2)
            await asyncio.sleep(step)
            remaining -= step


FirmnginClient = AsyncClient

__all__ = [
    "AsyncClient",
    "Event",
    "FirmnginClient",
]
