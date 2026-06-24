"""Entity update builders."""

from __future__ import annotations

from typing import Any, Protocol

from firmngin.payloads import Entity, entity_key, entity_value


class EntityBatchPublisher(Protocol):
    async def update_entities(self, entities: list[dict[str, str]]) -> None:
        """Publish batch entity payload."""


class BatchState:
    """Builder for Arduino-style batch entity updates."""

    def __init__(self, client: EntityBatchPublisher) -> None:
        self._client = client
        self._entries: list[dict[str, str]] = []

    def add(
        self, key: Entity | str | int, value: Any, *, decimals: int | None = None
    ) -> BatchState:
        self._entries.append({"k": entity_key(key), "v": entity_value(value, decimals=decimals)})
        return self

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    async def send(self) -> None:
        if not self._entries:
            raise ValueError("batch must contain at least one entity")
        await self._client.update_entities(self._entries)


class LocationUpdate:
    """Builder for location entity updates."""

    def __init__(self, client: EntityBatchPublisher) -> None:
        self._batch = BatchState(client)

    def lat(self, value: float) -> LocationUpdate:
        self._batch.add("lat", value)
        return self

    def lon(self, value: float) -> LocationUpdate:
        self._batch.add("lon", value)
        return self

    def accuracy(self, value: float) -> LocationUpdate:
        self._batch.add("accuracy", value)
        return self

    def alt(self, value: float) -> LocationUpdate:
        self._batch.add("alt", value)
        return self

    def speed(self, value: float) -> LocationUpdate:
        self._batch.add("speed", value)
        return self

    async def send(self) -> None:
        await self._batch.send()


__all__ = ["BatchState", "LocationUpdate"]
