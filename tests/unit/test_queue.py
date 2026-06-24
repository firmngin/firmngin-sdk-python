"""Unit tests for the file-backed offline publish queue."""

from __future__ import annotations

from pathlib import Path

import pytest

from firmngin.exceptions import QueueError
from firmngin.queue import OfflineQueue


@pytest.mark.asyncio
async def test_enqueue_and_peek_round_trip(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")

    saved = await queue.enqueue("/d/dev-1/ps", b'{"k":"v"}', retained=True)
    peeked = await queue.peek()

    assert peeked == saved
    assert peeked is not None
    assert peeked.payload == b'{"k":"v"}'


@pytest.mark.asyncio
async def test_queue_drains_oldest_first(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")
    await queue.enqueue("/d/dev-1/ps", b"one")
    await queue.enqueue("/d/dev-1/ps", b"two")
    published: list[tuple[str, bytes, bool]] = []

    async def publish(topic: str, payload: bytes, retained: bool) -> None:
        published.append((topic, payload, retained))

    drained = await queue.drain(publish)

    assert drained == 2
    assert published == [
        ("/d/dev-1/ps", b"one", False),
        ("/d/dev-1/ps", b"two", False),
    ]
    assert await queue.peek() is None


@pytest.mark.asyncio
async def test_drop_removes_oldest_message(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")
    first = await queue.enqueue("/d/dev-1/ps", b"one")
    second = await queue.enqueue("/d/dev-1/ps", b"two")

    await queue.drop()

    assert first.id != second.id
    assert await queue.peek() == second


@pytest.mark.asyncio
async def test_drain_preserves_message_and_increments_attempts_on_failure(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")
    saved = await queue.enqueue("/d/dev-1/ps", b"one")

    async def publish(_topic: str, _payload: bytes, _retained: bool) -> None:
        raise RuntimeError("broker offline")

    with pytest.raises(QueueError, match=saved.id):
        await queue.drain(publish)

    peeked = await queue.peek()
    assert peeked is not None
    assert peeked.id == saved.id
    assert peeked.attempts == 1


@pytest.mark.asyncio
async def test_enqueue_rejects_empty_topic(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")

    with pytest.raises(QueueError, match="topic"):
        await queue.enqueue("", b"payload")


@pytest.mark.asyncio
async def test_enqueue_rejects_when_queue_is_full(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue", max_size=1)
    await queue.enqueue("/d/dev-1/ps", b"one")

    with pytest.raises(QueueError, match="full"):
        await queue.enqueue("/d/dev-1/ps", b"two")


@pytest.mark.asyncio
async def test_drain_respects_batch_limit(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue")
    await queue.enqueue("/d/dev-1/ps", b"one")
    await queue.enqueue("/d/dev-1/ps", b"two")
    published: list[bytes] = []

    async def publish(_topic: str, payload: bytes, _retained: bool) -> None:
        published.append(payload)

    drained = await queue.drain(publish, limit=1)

    assert drained == 1
    assert published == [b"one"]
    peeked = await queue.peek()
    assert peeked is not None
    assert peeked.payload == b"two"
