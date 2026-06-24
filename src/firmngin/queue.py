"""File-backed persistent publish queue.

This module intentionally avoids database dependencies. Each queued publish is
stored as one JSON file in a directory and made visible with an atomic rename.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from firmngin.exceptions import QueueError

PublishFn = Callable[[str, bytes, bool], Awaitable[None]]


@dataclass(frozen=True)
class QueuedMessage:
    """One queued MQTT publish."""

    id: str
    topic: str
    payload: bytes
    retained: bool
    created_at: int
    attempts: int = 0


class OfflineQueue:
    """Durable oldest-first publish queue backed by local files."""

    def __init__(
        self,
        path: str | Path,
        *,
        max_size: int | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._max_size = max_size
        self._max_bytes = max_bytes

    async def setup(self) -> None:
        """Create the queue directory if it does not exist."""
        await asyncio.to_thread(self._path.mkdir, parents=True, exist_ok=True)

    async def enqueue(self, topic: str, payload: bytes, retained: bool = False) -> QueuedMessage:
        """Append a message to the queue."""
        if not topic:
            raise QueueError("topic must be a non-empty string")

        await self.setup()
        if self._max_size is not None:
            count = await asyncio.to_thread(self._count_messages)
            if count >= self._max_size:
                raise QueueError("offline queue is full")
        if self._max_bytes is not None:
            total_bytes = await asyncio.to_thread(self._total_payload_bytes)
            if total_bytes + len(payload) > self._max_bytes:
                raise QueueError("offline queue byte limit exceeded")

        sequence = time.time_ns()
        message = QueuedMessage(
            id=f"{sequence}-{uuid.uuid4().hex[:8]}",
            topic=topic,
            payload=payload,
            retained=retained,
            created_at=int(time.time()),
        )
        await asyncio.to_thread(self._write_message, message, sequence)
        return message

    async def peek(self) -> QueuedMessage | None:
        """Return the oldest queued message without removing it."""
        await self.setup()
        path = await asyncio.to_thread(self._first_message_path)
        if path is None:
            return None
        return await asyncio.to_thread(self._read_message, path)

    async def drop(self, message_id: str | None = None) -> None:
        """Drop a queued message by id, or the oldest message if id is omitted."""
        await self.setup()
        path = await asyncio.to_thread(self._message_path_for_drop, message_id)
        if path is not None:
            await asyncio.to_thread(path.unlink)

    async def drain(self, publish_fn: PublishFn, *, limit: int | None = None) -> int:
        """Publish and remove queued messages until empty, publish fails, or limit is reached."""
        drained = 0
        while limit is None or drained < limit:
            message = await self.peek()
            if message is None:
                return drained
            try:
                await publish_fn(message.topic, message.payload, message.retained)
            except Exception as exc:
                await self._increment_attempts(message)
                raise QueueError(f"failed to publish queued message {message.id}") from exc
            await self.drop(message.id)
            drained += 1
        return drained

    def _write_message(self, message: QueuedMessage, sequence: int) -> None:
        payload = {
            "id": message.id,
            "topic": message.topic,
            "payload": base64.b64encode(message.payload).decode("ascii"),
            "retained": message.retained,
            "created_at": message.created_at,
            "attempts": message.attempts,
        }
        final_path = self._path / f"{sequence:020d}.json"
        tmp_path = self._path / f".{sequence:020d}.tmp"
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, separators=(",", ":"), sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, final_path)

    def _first_message_path(self) -> Path | None:
        return min(self._path.glob("*.json"), default=None, key=lambda path: path.name)

    def _message_path_for_drop(self, message_id: str | None) -> Path | None:
        if message_id is None:
            return self._first_message_path()
        for path in self._path.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            if str(raw.get("id")) == message_id:
                return path
        return None

    def _count_messages(self) -> int:
        return sum(1 for _ in self._path.glob("*.json"))

    def _total_payload_bytes(self) -> int:
        total = 0
        for path in self._path.glob("*.json"):
            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            total += len(base64.b64decode(str(raw["payload"])))
        return total

    @staticmethod
    def _read_message(path: Path) -> QueuedMessage:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        try:
            return QueuedMessage(
                id=str(raw["id"]),
                topic=str(raw["topic"]),
                payload=base64.b64decode(str(raw["payload"])),
                retained=bool(raw["retained"]),
                created_at=int(raw["created_at"]),
                attempts=int(raw.get("attempts", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise QueueError(f"invalid queued message file: {path.name}") from exc

    async def _increment_attempts(self, message: QueuedMessage) -> None:
        path = await asyncio.to_thread(self._message_path_for_drop, message.id)
        if path is None:
            return
        sequence = int(path.stem)
        updated = QueuedMessage(
            id=message.id,
            topic=message.topic,
            payload=message.payload,
            retained=message.retained,
            created_at=message.created_at,
            attempts=message.attempts + 1,
        )
        await asyncio.to_thread(self._write_message, updated, sequence)


__all__ = ["OfflineQueue", "PublishFn", "QueuedMessage"]
