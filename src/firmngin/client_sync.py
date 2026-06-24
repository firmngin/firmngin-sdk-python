"""Blocking Firmngin device client."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Coroutine
from typing import Any, cast

from firmngin.client import AsyncClient, Event
from firmngin.config import ClientConfig
from firmngin.payloads import Entity


class Client:
    """Synchronous device client backed by one background event loop."""

    def __init__(self, config: ClientConfig) -> None:
        self._async_client = AsyncClient(config)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="firmngin-sync",
            daemon=True,
        )
        self._closed = False
        self._thread.start()

    @property
    def async_client(self) -> AsyncClient:
        return self._async_client

    def on(self, event: Event | str, callback: Any = None) -> Any:
        return self._async_client.on(event, callback)

    def on_entity(self, entity: Entity | str | int, callback: Any = None) -> Any:
        return self._async_client.on_entity(entity, callback)

    def off(self, event: Event | str, callback: Any) -> None:
        self._async_client.off(event, callback)

    def off_entity(self, entity: Entity | str | int, callback: Any) -> None:
        self._async_client.off_entity(entity, callback)

    def clear_handlers(self, event: Event | str | None = None) -> None:
        self._async_client.clear_handlers(event)

    def set_debug(self, enabled: bool = True) -> None:
        self._async_client.set_debug(enabled)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro: Coroutine[Any, Any, Any]) -> Any:
        if self._closed:
            raise RuntimeError("Client is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def connect(self) -> None:
        self._run(self._async_client.connect())

    def disconnect(self) -> None:
        self._run(self._async_client.disconnect())

    def push_entity(self, entity: Entity | str | int, value: Any) -> None:
        self._run(self._async_client.push_entity(entity, value))

    def update_entities(self, entities: dict[str, Any]) -> None:
        self._run(self._async_client.update_entities(entities))

    def request_init(self) -> None:
        self._run(self._async_client.request_init())

    def upload_image(self, entity: Entity | str | int, image: str) -> str:
        return cast(str, self._run(self._async_client.upload_image(entity, image)))

    def run(self) -> None:
        self._run(self._async_client.run())

    def stop(self) -> None:
        self._async_client.stop()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(Exception):
            self._run(self._async_client.disconnect())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


SyncClient = Client
SyncFirmnginClient = Client

__all__ = ["Client", "SyncClient", "SyncFirmnginClient"]
