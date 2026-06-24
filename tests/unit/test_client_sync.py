"""Unit tests for the synchronous client wrapper."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import AsyncMock

from firmngin import Client, ClientConfig, KeysConfig

from .test_config import _valid_keys_data


def _client() -> Client:
    keys = KeysConfig.from_dict(_valid_keys_data())
    return Client(ClientConfig(keys=keys))


def test_shutdown_session_only_disconnects_once() -> None:
    client = _client()
    disconnect = AsyncMock()
    client._async_client.disconnect = disconnect

    client._shutdown_session()
    client._shutdown_session()

    disconnect.assert_awaited_once()


def test_close_disconnects_before_marking_client_closed() -> None:
    client = _client()
    disconnect = AsyncMock()
    client._async_client.disconnect = disconnect

    client.close()

    disconnect.assert_awaited_once()
    assert client._closed is True


def test_close_does_not_leave_disconnect_coroutine_unawaited() -> None:
    client = _client()
    client.close()


def test_run_exits_cleanly_after_stop() -> None:
    client = _client()

    async def fake_run() -> None:
        while not client._async_client._stopped:
            await asyncio.sleep(0.05)

    client._async_client.run = fake_run  # type: ignore[method-assign]

    def stop_soon() -> None:
        time.sleep(0.1)
        client.stop()

    threading.Thread(target=stop_soon, daemon=True).start()
    client.run()


def test_run_swallows_keyboard_interrupt(monkeypatch) -> None:
    client = _client()
    calls = {"n": 0}
    real_run_coroutine_threadsafe = asyncio.run_coroutine_threadsafe

    class InterruptingFuture:
        def done(self) -> bool:
            return False

        def result(self, timeout: float | None = None) -> None:
            raise KeyboardInterrupt

    def selective_mock(coro: object, loop: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            return InterruptingFuture()
        return real_run_coroutine_threadsafe(coro, loop)  # type: ignore[arg-type]

    monkeypatch.setattr(asyncio, "run_coroutine_threadsafe", selective_mock)
    client.run()


def test_exit_suppresses_keyboard_interrupt() -> None:
    client = _client()
    client._interrupt_requested = True

    suppressed = client.__exit__(KeyboardInterrupt, KeyboardInterrupt(), None)

    assert suppressed is True
    assert client._closed is True
