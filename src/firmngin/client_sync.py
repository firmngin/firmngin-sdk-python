"""Blocking Firmngin device client."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import threading
from concurrent import futures
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
        self._session_shutdown = False
        self._interrupt_requested = False
        self._run_future: asyncio.Future[Any] | None = None
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
        try:
            return future.result()
        except KeyboardInterrupt:
            if self._interrupt_requested or self._session_shutdown:
                return None
            raise

    def _finish_run_future(self, run_future: futures.Future[Any]) -> None:
        if run_future.done():
            with contextlib.suppress(Exception):
                run_future.result(timeout=0)
            return
        cancel = getattr(run_future, "cancel", None)
        if callable(cancel):
            cancel()
        with contextlib.suppress(KeyboardInterrupt, futures.CancelledError, TimeoutError, Exception):
            run_future.result(timeout=1)

    def _shutdown_session(self) -> None:
        if self._session_shutdown:
            return
        self._session_shutdown = True
        self._async_client.stop()
        if self._closed:
            return
        future = asyncio.run_coroutine_threadsafe(
            self._async_client.disconnect(),
            self._loop,
        )
        with contextlib.suppress(Exception):
            future.result(timeout=10)

    def _stop_loop(self) -> None:
        if not self._loop.is_running():
            return

        async def _shutdown_loop() -> None:
            current = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if task is not current and not task.done()]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._loop.stop()

        future = asyncio.run_coroutine_threadsafe(_shutdown_loop(), self._loop)
        with contextlib.suppress(Exception):
            future.result(timeout=2)

    def connect(self) -> None:
        self._session_shutdown = False
        self._interrupt_requested = False
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
        if self._closed:
            raise RuntimeError("Client is closed")
        self._interrupt_requested = False
        run_future = asyncio.run_coroutine_threadsafe(self._async_client.run(), self._loop)
        self._run_future = run_future

        def on_sigint(_signum: int, _frame: object | None) -> None:
            self._interrupt_requested = True
            self._async_client.stop()

        prev_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, on_sigint)
        try:
            while not run_future.done():
                if self._interrupt_requested and not self._session_shutdown:
                    self._shutdown_session()
                try:
                    run_future.result(timeout=0.2)
                except TimeoutError:
                    continue
                except futures.CancelledError:
                    return
        except KeyboardInterrupt:
            self._interrupt_requested = True
            if not self._session_shutdown:
                self._shutdown_session()
        finally:
            signal.signal(signal.SIGINT, prev_handler)
            self._finish_run_future(run_future)
            self._run_future = None

    def stop(self) -> None:
        self._shutdown_session()

    def close(self) -> None:
        if self._closed:
            return
        self._shutdown_session()
        self._stop_loop()
        self._closed = True
        self._thread.join(timeout=1)

    def __enter__(self) -> Client:
        return self

    def __exit__(self, exc_type: object, exc: object, _tb: object) -> bool | None:
        self.close()
        if exc_type is KeyboardInterrupt or self._interrupt_requested:
            return True
        return None


SyncClient = Client
SyncFirmnginClient = Client

__all__ = ["Client", "SyncClient", "SyncFirmnginClient"]
