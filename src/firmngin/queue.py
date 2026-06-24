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

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def setup(self) -> None:
        """Create the queue directory if it does not exist."""
        await asyncio.to_thread(self._path.mkdir, parents=True, exist_ok=True)

    async def enqueue(self, topic: str, payload: bytes, retained: bool = False) -> QueuedMessage:
        """Append a message to the queue."""
        if not topic:
            raise QueueError("topic must be a non-empty string")

        await self.setup()
        message = QueuedMessage(
            id=f"{time.time_ns()}-{uuid.uuid4().hex}",
            topic=topic,
            payload=payload,
            retained=retained,
            created_at=int(time.time()),
        )
        await asyncio.to_thread(self._write_message, message)
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

    async def drain(self, publish_fn: PublishFn) -> int:
        """Publish and remove queued messages until the queue is empty or publish fails."""
        drained = 0
        while True:
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

    def _write_message(self, message: QueuedMessage) -> None:
        payload = {
            "id": message.id,
            "topic": message.topic,
            "payload": base64.b64encode(message.payload).decode("ascii"),
            "retained": message.retained,
            "created_at": message.created_at,
            "attempts": message.attempts,
        }
        final_path = self._path / f"{message.id}.json"
        tmp_path = self._path / f".{message.id}.tmp"
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, separators=(",", ":"), sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, final_path)

    def _first_message_path(self) -> Path | None:
        paths = sorted(self._path.glob("*.json"))
        return paths[0] if paths else None

    def _message_path_for_drop(self, message_id: str | None) -> Path | None:
        if message_id is None:
            return self._first_message_path()
        path = self._path / f"{message_id}.json"
        return path if path.exists() else None

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
        updated = QueuedMessage(
            id=message.id,
            topic=message.topic,
            payload=message.payload,
            retained=message.retained,
            created_at=message.created_at,
            attempts=message.attempts + 1,
        )
        await asyncio.to_thread(self._write_message, updated)


__all__ = ["OfflineQueue", "PublishFn", "QueuedMessage"]
